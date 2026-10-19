"""Local, separate history for KREA2 Image Lab renders."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain.krea2_lab import (
    Krea2AspectRatio,
    Krea2LabRun,
    Krea2LabRunStatus,
    Krea2LabSettings,
)
from panelforge.domain.recipes import RecipeRef

from .local import StorageCorruptionError


_SCHEMA_VERSION = 1
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_RUN_FIELDS = {
    "schema_version",
    "created_at",
    "updated_at",
    "run_id",
    "recipe",
    "preset_id",
    "prompt",
    "settings",
    "source_storyboard_run_id",
    "source_prompt_sha256",
    "status",
    "execution_id",
    "compiled_workflow_sha256",
    "output_asset_id",
    "error",
}
_RECIPE_FIELDS = {"operation_id", "recipe_id", "version", "workflow_sha256"}
_SETTINGS_FIELDS = {
    "model_name",
    "aspect_ratio",
    "megapixels",
    "seed",
    "seed_locked",
}


class LocalKrea2RunStore:
    """Persist KREA2 render state below ``workspace/krea2_runs``."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(workspace_root).resolve() / "krea2_runs"
        self._root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    def create(self, run: Krea2LabRun) -> Krea2LabRun:
        _require_run(run)
        with self._lock:
            directory = self._directory(run.run_id)
            directory.mkdir(exist_ok=False)
            path = directory / "run.json"
            try:
                now = _timestamp(self._clock())
                _atomic_write(path, _json_bytes(_serialize(run, now, now)))
            except BaseException:
                path.unlink(missing_ok=True)
                directory.rmdir()
                raise
        return run

    def save(self, run: Krea2LabRun) -> Krea2LabRun:
        _require_run(run)
        with self._lock:
            directory = self._directory(run.run_id)
            _, created_at, _ = self._read(directory / "run.json", run.run_id)
            self._verify_workflow(directory, run)
            updated_at = _timestamp(self._clock())
            _atomic_write(
                directory / "run.json",
                _json_bytes(_serialize(run, created_at, updated_at)),
            )
        return run

    def get(self, run_id: str) -> Krea2LabRun:
        with self._lock:
            directory = self._directory(run_id)
            run, _, _ = self._read(directory / "run.json", run_id)
            self._verify_workflow(directory, run)
            return run

    def list(self, limit: int = 20) -> list[Krea2LabRun]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []
        with self._lock:
            values: list[tuple[datetime, str, Krea2LabRun]] = []
            for directory in self._root.iterdir():
                if not directory.is_dir() or directory.is_symlink():
                    continue
                _safe_id(directory.name, "stored run_id")
                run, _, updated_at = self._read(
                    directory / "run.json",
                    directory.name,
                )
                self._verify_workflow(directory, run)
                values.append((_parse_timestamp(updated_at), run.run_id, run))
            values.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return [run for _, _, run in values[:limit]]

    def save_compiled_workflow(
        self,
        run_id: str,
        workflow: Mapping[str, Any],
    ) -> str:
        if not isinstance(workflow, Mapping):
            raise TypeError("workflow must be a mapping")
        with self._lock:
            directory = self._directory(run_id)
            self._read(directory / "run.json", run_id)
            try:
                content = (
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
            _atomic_write(directory / "compiled_workflow.json", content)
            return hashlib.sha256(content).hexdigest()

    def _read(
        self,
        path: Path,
        expected_run_id: str,
    ) -> tuple[Krea2LabRun, str, str]:
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(path)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TypeError("metadata must be an object")
            if set(value) != _RUN_FIELDS:
                raise ValueError("invalid metadata fields")
            if value.get("schema_version") != _SCHEMA_VERSION:
                raise ValueError("unsupported schema")
            created_at = _valid_timestamp(value["created_at"])
            updated_at = _valid_timestamp(value["updated_at"])
            run = _deserialize(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StorageCorruptionError(
                f"invalid KREA2 run metadata for {expected_run_id!r}"
            ) from error
        if run.run_id != expected_run_id:
            raise StorageCorruptionError(
                f"KREA2 run identity mismatch for {expected_run_id!r}"
            )
        return run, created_at, updated_at

    @staticmethod
    def _verify_workflow(directory: Path, run: Krea2LabRun) -> None:
        if run.compiled_workflow_sha256 is None:
            return
        path = directory / "compiled_workflow.json"
        if path.is_symlink() or not path.is_file():
            raise StorageCorruptionError("compiled KREA2 workflow is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != run.compiled_workflow_sha256:
            raise StorageCorruptionError(
                f"compiled workflow does not match KREA2 run {run.run_id!r}"
            )

    def _directory(self, run_id: str) -> Path:
        _safe_id(run_id, "run_id")
        candidate = self._root / run_id
        try:
            candidate.resolve().relative_to(self._root)
        except ValueError as error:
            raise ValueError("KREA2 run escapes its storage root") from error
        if candidate.is_symlink():
            raise StorageCorruptionError("KREA2 run directory is a symlink")
        return candidate


def _serialize(
    run: Krea2LabRun,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": created_at,
        "updated_at": updated_at,
        "run_id": run.run_id,
        "recipe": {
            "operation_id": run.recipe.operation_id,
            "recipe_id": run.recipe.recipe_id,
            "version": run.recipe.version,
            "workflow_sha256": run.recipe.workflow_sha256,
        },
        "preset_id": run.preset_id,
        "prompt": run.prompt,
        "settings": {
            "model_name": run.settings.model_name,
            "aspect_ratio": run.settings.aspect_ratio.value,
            "megapixels": run.settings.megapixels,
            "seed": str(run.settings.seed),
            "seed_locked": run.settings.seed_locked,
        },
        "source_storyboard_run_id": run.source_storyboard_run_id,
        "source_prompt_sha256": run.source_prompt_sha256,
        "status": run.status.value,
        "execution_id": run.execution_id,
        "compiled_workflow_sha256": run.compiled_workflow_sha256,
        "output_asset_id": run.output_asset_id,
        "error": run.error,
    }


def _deserialize(value: Mapping[str, Any]) -> Krea2LabRun:
    recipe = _mapping(value["recipe"])
    settings = _mapping(value["settings"])
    if set(recipe) != _RECIPE_FIELDS or set(settings) != _SETTINGS_FIELDS:
        raise ValueError("invalid nested metadata fields")
    return Krea2LabRun(
        run_id=value["run_id"],
        recipe=RecipeRef(
            operation_id=recipe["operation_id"],
            recipe_id=recipe["recipe_id"],
            version=recipe["version"],
            workflow_sha256=recipe["workflow_sha256"],
        ),
        preset_id=value["preset_id"],
        prompt=value["prompt"],
        settings=Krea2LabSettings(
            model_name=settings["model_name"],
            aspect_ratio=Krea2AspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"],
            seed=int(settings["seed"]),
            seed_locked=settings["seed_locked"],
        ),
        status=Krea2LabRunStatus(value["status"]),
        source_storyboard_run_id=value["source_storyboard_run_id"],
        source_prompt_sha256=value["source_prompt_sha256"],
        execution_id=value["execution_id"],
        compiled_workflow_sha256=value["compiled_workflow_sha256"],
        output_asset_id=value["output_asset_id"],
        error=value["error"],
    )


def _require_run(run: object) -> Krea2LabRun:
    if not isinstance(run, Krea2LabRun):
        raise TypeError("run must be a Krea2LabRun")
    _safe_id(run.run_id, "run_id")
    return run


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} contains unsafe path characters")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("stored value must be an object")
    return value


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    _parse_timestamp(value)
    return value


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
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
