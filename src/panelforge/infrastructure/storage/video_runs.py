"""Read-only compatibility for prompts of imported legacy Video Lab clips."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any

from panelforge.domain import (
    RecipeRef,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabRunStatus,
    VideoLabSettings,
)

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
    "source_asset_ids",
    "source_labels",
    "prompt",
    "settings",
    "status",
    "execution_id",
    "compiled_workflow_sha256",
    "output_asset_id",
    "error",
}
_RECIPE_FIELDS = {"operation_id", "recipe_id", "version", "workflow_sha256"}
_SETTINGS_FIELDS = {
    "aspect_ratio",
    "megapixels",
    "duration_seconds",
    "steps",
    "seed",
    "seed_locked",
}


class LocalVideoRunHistory:
    """Read existing Video Lab records below ``workspace/video_runs``."""

    def __init__(
        self,
        workspace_root: str | Path,
    ) -> None:
        self._root = Path(workspace_root).resolve() / "video_runs"
        self._lock = RLock()


    def get(self, run_id: str) -> VideoLabRun:
        with self._lock:
            directory = self._directory(run_id)
            run, _, _ = self._read(directory / "run.json", run_id)
            self._verify_workflow(directory, run)
            return run

    def list(self, limit: int = 20) -> list[VideoLabRun]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0 or not self._root.is_dir():
            return []
        with self._lock:
            values: list[tuple[datetime, str, VideoLabRun]] = []
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


    def _read(
        self,
        path: Path,
        expected_run_id: str,
    ) -> tuple[VideoLabRun, str, str]:
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
                f"invalid video run metadata for {expected_run_id!r}"
            ) from error
        if run.run_id != expected_run_id:
            raise StorageCorruptionError(
                f"video run identity mismatch for {expected_run_id!r}"
            )
        return run, created_at, updated_at

    @staticmethod
    def _verify_workflow(directory: Path, run: VideoLabRun) -> None:
        if run.compiled_workflow_sha256 is None:
            return
        path = directory / "compiled_workflow.json"
        if path.is_symlink() or not path.is_file():
            raise StorageCorruptionError("compiled video workflow is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != run.compiled_workflow_sha256:
            raise StorageCorruptionError(
                f"compiled workflow does not match video run {run.run_id!r}"
            )

    def _directory(self, run_id: str) -> Path:
        _safe_id(run_id, "run_id")
        candidate = self._root / run_id
        try:
            candidate.resolve().relative_to(self._root)
        except ValueError as error:
            raise ValueError("video run escapes its storage root") from error
        if candidate.is_symlink():
            raise StorageCorruptionError("video run directory is a symlink")
        return candidate


def _deserialize(value: Mapping[str, Any]) -> VideoLabRun:
    recipe = _mapping(value["recipe"])
    settings = _mapping(value["settings"])
    if set(recipe) != _RECIPE_FIELDS or set(settings) != _SETTINGS_FIELDS:
        raise ValueError("invalid nested metadata fields")
    return VideoLabRun(
        run_id=value["run_id"],
        recipe=RecipeRef(
            operation_id=recipe["operation_id"],
            recipe_id=recipe["recipe_id"],
            version=recipe["version"],
            workflow_sha256=recipe["workflow_sha256"],
        ),
        preset_id=value["preset_id"],
        source_asset_ids=tuple(_list(value["source_asset_ids"])),
        source_labels=tuple(_list(value["source_labels"])),
        prompt=value["prompt"],
        settings=VideoLabSettings(
            aspect_ratio=VideoAspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"],
            duration_seconds=settings["duration_seconds"],
            steps=settings["steps"],
            seed=int(settings["seed"]),
            seed_locked=settings["seed_locked"],
        ),
        status=VideoLabRunStatus(value["status"]),
        execution_id=value["execution_id"],
        compiled_workflow_sha256=value["compiled_workflow_sha256"],
        output_asset_id=value["output_asset_id"],
        error=value["error"],
    )


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} contains unsafe path characters")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("stored value must be an object")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("stored value must be a list")
    return value


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
