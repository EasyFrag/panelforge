"""Strict local persistence for immutable assets and recipe runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from typing import Any

from panelforge.domain import (
    Asset,
    ControlValue,
    PromptPolicy,
    PromptSnapshot,
    RecipeRef,
    RunRecord,
    RunReview,
    RunStatus,
)


_SCHEMA_VERSION = 1
_SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_ASSET_KEYS = {
    "schema_version",
    "asset_id",
    "media_type",
    "content_sha256",
    "size_bytes",
    "storage_key",
    "source_run_id",
}
_RUN_KEYS = {
    "schema_version",
    "created_at",
    "updated_at",
    "run_id",
    "recipe",
    "source_asset_ids",
    "prompt",
    "controls",
    "experimental_overrides",
    "status",
    "review_status",
    "parent_run_id",
    "execution_id",
    "compiled_workflow_sha256",
    "output_asset_ids",
    "error",
}
_RECIPE_KEYS = {"operation_id", "recipe_id", "version", "workflow_sha256"}
_PROMPT_KEYS = {"positive", "negative", "policy", "protected_fragments"}
_CONTROL_KEYS = {"control_id", "value"}


class StorageCorruptionError(ValueError):
    """Stored bytes or metadata no longer satisfy their recorded contract."""


class LocalAssetStore:
    """Store asset bytes below ``<workspace_root>/assets``.

    ``id_factory`` is injected so tests and later application policies can own
    identifier generation without putting filesystem concepts in the domain.
    """

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._assets_root = self._workspace_root / "assets"
        self._assets_root.mkdir(parents=True, exist_ok=True)
        self._id_factory = id_factory or _new_asset_id

    def create(
        self,
        content: bytes,
        media_type: str,
        source_run_id: str | None = None,
    ) -> Asset:
        """Create one asset exclusively and return its path-free metadata."""
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        if not content:
            raise ValueError("content must not be empty")

        asset_id = self._id_factory()
        _require_safe_id(asset_id, "generated asset_id")
        asset_dir = self._entry_dir(self._assets_root, asset_id)
        asset = Asset(
            asset_id=asset_id,
            media_type=media_type,
            content_sha256=_sha256(content),
            size_bytes=len(content),
            storage_key=f"assets/{asset_id}/content.bin",
            source_run_id=source_run_id,
        )
        asset_dir.mkdir(exist_ok=False)
        content_path = asset_dir / "content.bin"
        metadata_path = asset_dir / "asset.json"
        try:
            with content_path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            _atomic_write(metadata_path, _json_bytes(_asset_to_dict(asset)))
        except BaseException:
            metadata_path.unlink(missing_ok=True)
            content_path.unlink(missing_ok=True)
            asset_dir.rmdir()
            raise
        return asset

    def get(self, asset_id: str) -> Asset:
        """Load metadata and verify the stored content's size and digest."""
        asset, _ = self._read_verified(asset_id)
        return asset

    def read_bytes(self, asset_id: str) -> bytes:
        """Return content only after validating it against ``asset.json``."""
        _, content = self._read_verified(asset_id)
        return content

    def _read_verified(self, asset_id: str) -> tuple[Asset, bytes]:
        asset_dir = self._entry_dir(self._assets_root, asset_id)
        metadata_path = asset_dir / "asset.json"
        content_path = asset_dir / "content.bin"
        _require_regular_file(metadata_path)
        _require_regular_file(content_path)

        data = _read_json_object(metadata_path)
        if set(data) != _ASSET_KEYS:
            raise StorageCorruptionError(
                f"invalid asset metadata fields for {asset_id!r}"
            )
        if data.get("schema_version") != _SCHEMA_VERSION:
            raise StorageCorruptionError(
                f"unsupported asset schema for {asset_id!r}"
            )
        try:
            asset = Asset(
                asset_id=data["asset_id"],
                media_type=data["media_type"],
                content_sha256=data["content_sha256"],
                size_bytes=data["size_bytes"],
                storage_key=data["storage_key"],
                source_run_id=data["source_run_id"],
            )
        except (TypeError, ValueError) as error:
            raise StorageCorruptionError(
                f"invalid asset metadata for {asset_id!r}"
            ) from error

        expected_storage_key = f"assets/{asset_id}/content.bin"
        if asset.asset_id != asset_id or asset.storage_key != expected_storage_key:
            raise StorageCorruptionError(
                f"asset identity mismatch for {asset_id!r}"
            )
        content = content_path.read_bytes()
        if len(content) != asset.size_bytes or _sha256(content) != asset.content_sha256:
            raise StorageCorruptionError(
                f"asset content does not match metadata for {asset_id!r}"
            )
        return asset, content

    @staticmethod
    def _entry_dir(root: Path, asset_id: str) -> Path:
        _require_safe_id(asset_id, "asset_id")
        return _contained_entry(root, asset_id)


class LocalRunStore:
    """Store run provenance below ``<workspace_root>/runs``."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._runs_root = self._workspace_root / "runs"
        self._runs_root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, record: RunRecord) -> RunRecord:
        """Persist a new run, failing rather than replacing an existing run."""
        _require_run_record(record)
        run_dir = self._entry_dir(record.run_id)
        run_dir.mkdir(exist_ok=False)
        run_path = run_dir / "run.json"
        try:
            timestamp = _format_timestamp(self._clock())
            _atomic_write(
                run_path,
                _json_bytes(
                    _run_to_dict(
                        record,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                ),
            )
        except BaseException:
            run_path.unlink(missing_ok=True)
            run_dir.rmdir()
            raise
        return record

    def save(self, record: RunRecord) -> RunRecord:
        """Atomically replace mutable run metadata while preserving creation time."""
        _require_run_record(record)
        run_dir = self._entry_dir(record.run_id)
        run_path = run_dir / "run.json"
        existing, created_at, _ = self._read_run_file(run_path, record.run_id)
        if existing.run_id != record.run_id:
            raise StorageCorruptionError(
                f"run identity mismatch for {record.run_id!r}"
            )
        self._verify_compiled_workflow(run_dir, record)
        updated_at = _format_timestamp(self._clock())
        _atomic_write(
            run_path,
            _json_bytes(
                _run_to_dict(
                    record,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            ),
        )
        return record

    def get(self, run_id: str) -> RunRecord:
        """Load one complete domain record and verify workflow provenance."""
        run_dir = self._entry_dir(run_id)
        record, _, _ = self._read_run_file(run_dir / "run.json", run_id)
        self._verify_compiled_workflow(run_dir, record)
        return record

    def list(self, limit: int) -> list[RunRecord]:
        """Return the most recently updated runs, newest first."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []

        indexed: list[tuple[datetime, str, RunRecord]] = []
        for run_dir in self._runs_root.iterdir():
            if not run_dir.is_dir() or run_dir.is_symlink():
                continue
            _require_safe_id(run_dir.name, "stored run_id")
            record, _, updated_at = self._read_run_file(
                run_dir / "run.json",
                run_dir.name,
            )
            self._verify_compiled_workflow(run_dir, record)
            indexed.append((_parse_timestamp(updated_at), record.run_id, record))

        indexed.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in indexed[:limit]]

    def save_compiled_workflow(
        self,
        run_id: str,
        workflow: Mapping[str, Any],
    ) -> str:
        """Atomically persist deterministic JSON and return its exact SHA-256."""
        if not isinstance(workflow, Mapping):
            raise TypeError("workflow must be a mapping")
        run_dir = self._entry_dir(run_id)
        self._read_run_file(run_dir / "run.json", run_id)
        try:
            workflow_bytes = (
                json.dumps(
                    workflow,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        except (TypeError, ValueError) as error:
            raise TypeError("workflow must contain JSON-compatible values") from error

        workflow_path = run_dir / "compiled_workflow.json"
        _atomic_write(workflow_path, workflow_bytes)
        return _sha256(workflow_bytes)

    def _read_run_file(
        self,
        path: Path,
        expected_run_id: str,
    ) -> tuple[RunRecord, str, str]:
        _require_regular_file(path)
        data = _read_json_object(path)
        if set(data) != _RUN_KEYS:
            raise StorageCorruptionError(
                f"invalid run metadata fields for {expected_run_id!r}"
            )
        if data.get("schema_version") != _SCHEMA_VERSION:
            raise StorageCorruptionError(
                f"unsupported run schema for {expected_run_id!r}"
            )
        created_at = _require_timestamp(data.get("created_at"), "created_at")
        updated_at = _require_timestamp(data.get("updated_at"), "updated_at")
        try:
            record = _run_from_dict(data)
        except (KeyError, TypeError, ValueError) as error:
            raise StorageCorruptionError(
                f"invalid run metadata for {expected_run_id!r}"
            ) from error
        if record.run_id != expected_run_id:
            raise StorageCorruptionError(
                f"run identity mismatch for {expected_run_id!r}"
            )
        return record, created_at, updated_at

    @staticmethod
    def _verify_compiled_workflow(run_dir: Path, record: RunRecord) -> None:
        if record.compiled_workflow_sha256 is None:
            return
        workflow_path = run_dir / "compiled_workflow.json"
        _require_regular_file(workflow_path)
        if _sha256(workflow_path.read_bytes()) != record.compiled_workflow_sha256:
            raise StorageCorruptionError(
                f"compiled workflow does not match run {record.run_id!r}"
            )

    def _entry_dir(self, run_id: str) -> Path:
        _require_safe_id(run_id, "run_id")
        return _contained_entry(self._runs_root, run_id)


def _new_asset_id() -> str:
    return f"asset-{uuid.uuid4().hex}"


def _asset_to_dict(asset: Asset) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "asset_id": asset.asset_id,
        "media_type": asset.media_type,
        "content_sha256": asset.content_sha256,
        "size_bytes": asset.size_bytes,
        "storage_key": asset.storage_key,
        "source_run_id": asset.source_run_id,
    }


def _run_to_dict(
    record: RunRecord,
    *,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": created_at,
        "updated_at": updated_at,
        "run_id": record.run_id,
        "recipe": {
            "operation_id": record.recipe.operation_id,
            "recipe_id": record.recipe.recipe_id,
            "version": record.recipe.version,
            "workflow_sha256": record.recipe.workflow_sha256,
        },
        "source_asset_ids": list(record.source_asset_ids),
        "prompt": {
            "positive": record.prompt.positive,
            "negative": record.prompt.negative,
            "policy": record.prompt.policy.value,
            "protected_fragments": list(record.prompt.protected_fragments),
        },
        "controls": [
            {"control_id": control.control_id, "value": control.value}
            for control in record.controls
        ],
        "experimental_overrides": list(record.experimental_overrides),
        "status": record.status.value,
        "review_status": record.review_status.value,
        "parent_run_id": record.parent_run_id,
        "execution_id": record.execution_id,
        "compiled_workflow_sha256": record.compiled_workflow_sha256,
        "output_asset_ids": list(record.output_asset_ids),
        "error": record.error,
    }


def _run_from_dict(data: dict[str, object]) -> RunRecord:
    recipe = _require_object(data["recipe"], "recipe")
    prompt = _require_object(data["prompt"], "prompt")
    controls_data = _require_list(data["controls"], "controls")
    if set(recipe) != _RECIPE_KEYS:
        raise ValueError("recipe contains invalid fields")
    if set(prompt) != _PROMPT_KEYS:
        raise ValueError("prompt contains invalid fields")
    controls: list[ControlValue] = []
    for item in controls_data:
        control = _require_object(item, "control")
        if set(control) != _CONTROL_KEYS:
            raise ValueError("control contains invalid fields")
        controls.append(
            ControlValue(
                control_id=control["control_id"],
                value=control["value"],
            )
        )
    return RunRecord(
        run_id=data["run_id"],
        recipe=RecipeRef(
            operation_id=recipe["operation_id"],
            recipe_id=recipe["recipe_id"],
            version=recipe["version"],
            workflow_sha256=recipe["workflow_sha256"],
        ),
        source_asset_ids=tuple(_require_list(data["source_asset_ids"], "source_asset_ids")),
        prompt=PromptSnapshot(
            positive=prompt["positive"],
            negative=prompt["negative"],
            policy=PromptPolicy(prompt["policy"]),
            protected_fragments=tuple(
                _require_list(prompt["protected_fragments"], "protected_fragments")
            ),
        ),
        controls=tuple(controls),
        experimental_overrides=tuple(
            _require_list(data["experimental_overrides"], "experimental_overrides")
        ),
        status=RunStatus(data["status"]),
        review_status=RunReview(data["review_status"]),
        parent_run_id=data["parent_run_id"],
        execution_id=data["execution_id"],
        compiled_workflow_sha256=data["compiled_workflow_sha256"],
        output_asset_ids=tuple(
            _require_list(data["output_asset_ids"], "output_asset_ids")
        ),
        error=data["error"],
    )


def _contained_entry(root: Path, entry_id: str) -> Path:
    candidate = root / entry_id
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("storage entry escapes its configured root") from error
    if candidate.is_symlink():
        raise StorageCorruptionError(f"storage entry {entry_id!r} is a symlink")
    return candidate


def _require_safe_id(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _SAFE_ID_PATTERN.fullmatch(value) is None or value in {".", ".."}:
        raise ValueError(f"{name} contains unsafe path characters")
    return value


def _require_run_record(record: object) -> RunRecord:
    if not isinstance(record, RunRecord):
        raise TypeError("record must be a RunRecord")
    _require_safe_id(record.run_id, "run_id")
    return record


def _require_regular_file(path: Path) -> None:
    if path.is_symlink():
        raise StorageCorruptionError(f"stored path is a symlink: {path.name}")
    if not path.is_file():
        raise FileNotFoundError(path)


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StorageCorruptionError(f"invalid JSON in {path.name}") from error
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise StorageCorruptionError(f"expected a JSON object in {path.name}")
    return value


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _format_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise StorageCorruptionError("invalid stored timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StorageCorruptionError("stored timestamp must include a timezone")
    return parsed


def _require_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise StorageCorruptionError(f"{name} must be a string")
    _parse_timestamp(value)
    return value


def _require_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise TypeError(f"{name} must be an object")
    return value


def _require_list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    return value
