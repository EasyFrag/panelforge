"""Strict local history for Storyboard Lab prompt generations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from panelforge.domain.storyboard import StoryboardSpec
from panelforge.domain.storyboard_runs import StoryboardRun, StoryboardRunStatus

from .local import (
    StorageCorruptionError,
    _atomic_write,
    _contained_entry,
    _format_timestamp,
    _json_bytes,
    _parse_timestamp,
    _read_json_object,
    _require_regular_file,
    _require_safe_id,
    _require_timestamp,
)


_SCHEMA_VERSION = 1
_RUN_FIELDS = {
    "schema_version",
    "created_at",
    "updated_at",
    "run_id",
    "intention",
    "panel_count",
    "model_id",
    "recipe_id",
    "recipe_version",
    "template_sha256",
    "status",
    "raw_response",
    "spec",
    "compiled_prompt",
    "warnings",
    "error",
}
class LocalStoryboardRunStore:
    """Persist storyboard prompt runs below ``workspace/storyboard_runs``."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(workspace_root).resolve() / "storyboard_runs"
        self._root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    def create(self, run: StoryboardRun) -> StoryboardRun:
        _require_run(run)
        with self._lock:
            directory = self._directory(run.run_id)
            directory.mkdir(exist_ok=False)
            path = directory / "run.json"
            try:
                now = _format_timestamp(self._clock())
                _atomic_write(path, _json_bytes(_serialize(run, now, now)))
            except BaseException:
                path.unlink(missing_ok=True)
                directory.rmdir()
                raise
        return run

    def save(self, run: StoryboardRun) -> StoryboardRun:
        _require_run(run)
        with self._lock:
            path = self._directory(run.run_id) / "run.json"
            stored, created_at, _ = self._read(path, run.run_id)
            if stored.run_id != run.run_id:
                raise StorageCorruptionError(
                    f"storyboard run identity mismatch for {run.run_id!r}"
                )
            _atomic_write(
                path,
                _json_bytes(
                    _serialize(
                        run,
                        created_at,
                        _format_timestamp(self._clock()),
                    )
                ),
            )
        return run

    def get(self, run_id: str) -> StoryboardRun:
        with self._lock:
            run, _, _ = self._read(
                self._directory(run_id) / "run.json",
                run_id,
            )
            return run

    def list(self, limit: int = 20) -> list[StoryboardRun]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []
        with self._lock:
            values: list[tuple[datetime, str, StoryboardRun]] = []
            for directory in self._root.iterdir():
                if not directory.is_dir() or directory.is_symlink():
                    continue
                _require_safe_id(directory.name, "stored storyboard run ID")
                run, _, updated_at = self._read(
                    directory / "run.json",
                    directory.name,
                )
                values.append(
                    (_parse_timestamp(updated_at), run.run_id, run)
                )
            values.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return [run for _, _, run in values[:limit]]

    def _read(
        self,
        path: Path,
        expected_run_id: str,
    ) -> tuple[StoryboardRun, str, str]:
        _require_regular_file(path)
        value = _read_json_object(path)
        try:
            if set(value) != _RUN_FIELDS:
                raise ValueError("invalid metadata fields")
            if value.get("schema_version") != _SCHEMA_VERSION:
                raise ValueError("unsupported schema")
            created_at = _require_timestamp(value["created_at"], "created_at")
            updated_at = _require_timestamp(value["updated_at"], "updated_at")
            run = _deserialize(value)
        except (KeyError, TypeError, ValueError) as error:
            raise StorageCorruptionError(
                f"invalid storyboard run metadata for {expected_run_id!r}"
            ) from error
        if run.run_id != expected_run_id:
            raise StorageCorruptionError(
                f"storyboard run identity mismatch for {expected_run_id!r}"
            )
        return run, created_at, updated_at

    def _directory(self, run_id: str) -> Path:
        _require_safe_id(run_id, "storyboard run ID")
        candidate = _contained_entry(self._root, run_id)
        if candidate.is_symlink():
            raise StorageCorruptionError("storyboard run directory is a symlink")
        return candidate


def _serialize(
    run: StoryboardRun,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": created_at,
        "updated_at": updated_at,
        "run_id": run.run_id,
        "intention": run.intention,
        "panel_count": run.panel_count,
        "model_id": run.model_id,
        "recipe_id": run.recipe_id,
        "recipe_version": run.recipe_version,
        "template_sha256": run.template_sha256,
        "status": run.status.value,
        "raw_response": run.raw_response,
        "spec": run.spec.to_payload() if run.spec is not None else None,
        "compiled_prompt": run.compiled_prompt,
        "warnings": list(run.warnings),
        "error": run.error,
    }


def _deserialize(value: Mapping[str, Any]) -> StoryboardRun:
    raw_warnings = _list(value["warnings"], "warnings")
    raw_spec = value["spec"]
    return StoryboardRun(
        run_id=value["run_id"],
        intention=value["intention"],
        panel_count=value["panel_count"],
        model_id=value["model_id"],
        recipe_id=value["recipe_id"],
        recipe_version=value["recipe_version"],
        template_sha256=value["template_sha256"],
        status=StoryboardRunStatus(value["status"]),
        raw_response=value["raw_response"],
        spec=(
            StoryboardSpec.from_payload(
                _mapping(raw_spec, "spec"),
                expected_panel_count=value["panel_count"],
            )
            if raw_spec is not None
            else None
        ),
        compiled_prompt=value["compiled_prompt"],
        warnings=tuple(raw_warnings),
        error=value["error"],
    )
def _require_run(value: object) -> StoryboardRun:
    if not isinstance(value, StoryboardRun):
        raise TypeError("run must be a StoryboardRun")
    _require_safe_id(value.run_id, "storyboard run ID")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a list")
    return value
