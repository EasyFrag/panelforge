"""Durable local store for conversational H3 Base render projects."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any, Mapping

from panelforge.domain.h3_render import (
    H3RenderAttempt,
    H3RenderAttemptStatus,
    H3RenderInputMode,
    H3RenderKeyframe,
    H3RenderProject,
    H3RenderRevisionVersion,
    H3RenderTurn,
    H3RenderTurnRole,
    H3VideoLoraSelection,
)
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalH3RenderProjectStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "h3_render_projects"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(self, project: H3RenderProject) -> H3RenderProject:
        with self._lock:
            directory = self._directory(project.project_id)
            directory.mkdir(exist_ok=False)
            _atomic_write(directory / "project.json", _json_bytes(_serialize(project)))
        return project

    def save(self, project: H3RenderProject) -> H3RenderProject:
        with self._lock:
            path = self._directory(project.project_id) / "project.json"
            if not path.is_file():
                raise FileNotFoundError(project.project_id)
            _atomic_write(path, _json_bytes(_serialize(project)))
        return project

    def get(self, project_id: str) -> H3RenderProject:
        with self._lock:
            path = self._directory(project_id) / "project.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(project_id)
            return _deserialize(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 30) -> list[H3RenderProject]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        values: list[tuple[float, str, H3RenderProject]] = []
        with self._lock:
            for directory in self._root.iterdir():
                path = directory / "project.json"
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append((
                        path.stat().st_mtime,
                        directory.name,
                        _deserialize(json.loads(path.read_text(encoding="utf-8"))),
                    ))
        values.sort(key=lambda value: (value[0], value[1]), reverse=True)
        return [project for _, _, project in values[:limit]]

    def find_source_revision(
        self,
        source_session_id: str,
        source_prompt_revision_id: str,
    ) -> H3RenderProject | None:
        for project in self.list(2**31 - 1):
            if (
                project.source_session_id == source_session_id
                and project.source_prompt_revision_id == source_prompt_revision_id
            ):
                return project
        return None

    def save_compiled_workflow(
        self,
        project_id: str,
        attempt_id: str,
        workflow: Mapping[str, Any],
    ) -> str:
        _safe(attempt_id)
        directory = self._directory(project_id) / "workflows"
        directory.mkdir(exist_ok=True)
        content = json.dumps(
            workflow,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        _atomic_write(directory / f"{attempt_id}.json", content)
        return hashlib.sha256(content).hexdigest()

    def _directory(self, project_id: str) -> Path:
        _safe(project_id)
        candidate = self._root / project_id
        candidate.resolve().relative_to(self._root)
        if candidate.is_symlink():
            raise ValueError("project directory cannot be a symlink")
        return candidate


def _serialize(project: H3RenderProject) -> dict[str, object]:
    return {
        "schema_version": 3,
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "project_id": project.project_id,
        "source_session_id": project.source_session_id,
        "source_prompt_revision_id": project.source_prompt_revision_id,
        "model_id": project.model_id,
        "revision_model_id": project.revision_model_id,
        "input_mode": project.input_mode.value,
        "current_prompt": project.current_prompt,
        "planned_cut_times_ms": list(project.planned_cut_times_ms),
        "first_frame_asset_id": project.first_frame_asset_id,
        "first_frame_label": project.first_frame_label,
        "last_frame_asset_id": project.last_frame_asset_id,
        "last_frame_label": project.last_frame_label,
        "reference_asset_ids": list(project.reference_asset_ids),
        "reference_labels": list(project.reference_labels),
        "revision_version": (
            project.revision_version.value if project.revision_version else None
        ),
        "camera_clauses": list(project.camera_clauses),
        "revision_draft": project.revision_draft,
        "revision_error": project.revision_error,
        "revision_draft_version": (
            project.revision_draft_version.value
            if project.revision_draft_version else None
        ),
        "turns": [
            {
                "turn_id": turn.turn_id,
                "role": turn.role.value,
                "content": turn.content,
                "prompt": turn.prompt,
                "questions": list(turn.questions),
                "recommendations": list(turn.recommendations),
                "revision_version": (
                    turn.revision_version.value if turn.revision_version else None
                ),
                "model_id": turn.model_id,
            }
            for turn in project.turns
        ],
        "attempts": [_serialize_attempt(attempt) for attempt in project.attempts],
        "feedback_attempt_id": project.feedback_attempt_id,
        "warnings": list(project.warnings),
    }


def _serialize_attempt(attempt: H3RenderAttempt) -> dict[str, object]:
    return {
        "attempt_id": attempt.attempt_id,
        "index": attempt.index,
        "prompt": attempt.prompt,
        "effective_prompt": attempt.effective_prompt,
        "settings": {
            "aspect_ratio": attempt.settings.aspect_ratio.value,
            "megapixels": attempt.settings.megapixels,
            "duration_seconds": attempt.settings.duration_seconds,
            "steps": attempt.settings.steps,
            "seed": str(attempt.settings.seed),
            "seed_locked": attempt.settings.seed_locked,
        },
        "music_enabled": attempt.music_enabled,
        "spectrum_enabled": attempt.spectrum_enabled,
        "video_lora": (
            {
                "name": attempt.video_lora.name,
                "strength": attempt.video_lora.strength,
                "clip_last_layer": attempt.video_lora.clip_last_layer,
                "overlay_version": attempt.video_lora.overlay_version,
            }
            if attempt.video_lora is not None
            else None
        ),
        "keyframe_timestamps_ms": list(attempt.keyframe_timestamps_ms),
        "status": attempt.status.value,
        "execution_id": attempt.execution_id,
        "compiled_workflow_sha256": attempt.compiled_workflow_sha256,
        "output_asset_id": attempt.output_asset_id,
        "keyframes": [
            {
                "asset_id": frame.asset_id,
                "timestamp_ms": frame.timestamp_ms,
                "label": frame.label,
            }
            for frame in attempt.keyframes
        ],
        "error": attempt.error,
        "warnings": list(attempt.warnings),
    }


def _deserialize(value: dict[str, Any]) -> H3RenderProject:
    if value.get("schema_version") not in {1, 2, 3}:
        raise ValueError("unsupported H3 render project schema")
    return H3RenderProject(
        project_id=value["project_id"],
        source_session_id=value["source_session_id"],
        source_prompt_revision_id=value["source_prompt_revision_id"],
        model_id=value["model_id"],
        revision_model_id=value.get("revision_model_id"),
        input_mode=H3RenderInputMode(value["input_mode"]),
        current_prompt=value["current_prompt"],
        planned_cut_times_ms=tuple(value.get("planned_cut_times_ms", [])),
        first_frame_asset_id=value.get("first_frame_asset_id"),
        first_frame_label=value.get("first_frame_label"),
        last_frame_asset_id=value.get("last_frame_asset_id"),
        last_frame_label=value.get("last_frame_label"),
        reference_asset_ids=tuple(value.get("reference_asset_ids", [])),
        reference_labels=tuple(value.get("reference_labels", [])),
        revision_version=(
            H3RenderRevisionVersion(value["revision_version"])
            if value.get("revision_version") else None
        ),
        camera_clauses=tuple(value.get("camera_clauses", [])),
        revision_draft=value.get("revision_draft"),
        revision_error=value.get("revision_error"),
        revision_draft_version=(
            H3RenderRevisionVersion(value["revision_draft_version"])
            if value.get("revision_draft_version") else None
        ),
        turns=tuple(
            H3RenderTurn(
                turn_id=item["turn_id"],
                role=H3RenderTurnRole(item["role"]),
                content=item["content"],
                prompt=item.get("prompt"),
                questions=tuple(item.get("questions", [])),
                recommendations=tuple(item.get("recommendations", [])),
                revision_version=(
                    H3RenderRevisionVersion(item["revision_version"])
                    if item.get("revision_version") else None
                ),
                model_id=item.get("model_id"),
            )
            for item in value.get("turns", [])
        ),
        attempts=tuple(_deserialize_attempt(item) for item in value.get("attempts", [])),
        feedback_attempt_id=value.get("feedback_attempt_id"),
        warnings=tuple(value.get("warnings", [])),
    )


def _deserialize_attempt(value: dict[str, Any]) -> H3RenderAttempt:
    settings = value["settings"]
    video_lora = value.get("video_lora")
    return H3RenderAttempt(
        attempt_id=value["attempt_id"],
        index=value["index"],
        prompt=value["prompt"],
        effective_prompt=value["effective_prompt"],
        settings=VideoLabSettings(
            aspect_ratio=VideoAspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"],
            duration_seconds=settings["duration_seconds"],
            steps=settings["steps"],
            seed=int(settings["seed"]),
            seed_locked=settings.get("seed_locked", False),
        ),
        music_enabled=value["music_enabled"],
        spectrum_enabled=value.get("spectrum_enabled", False),
        video_lora=(
            H3VideoLoraSelection(
                name=video_lora["name"],
                strength=video_lora.get("strength", 0.5),
                clip_last_layer=video_lora.get("clip_last_layer", -2),
                overlay_version=video_lora.get("overlay_version", "0.1.0"),
            )
            if isinstance(video_lora, dict)
            else None
        ),
        keyframe_timestamps_ms=tuple(value.get("keyframe_timestamps_ms", [])),
        status=H3RenderAttemptStatus(value["status"]),
        execution_id=value.get("execution_id"),
        compiled_workflow_sha256=value.get("compiled_workflow_sha256"),
        output_asset_id=value.get("output_asset_id"),
        keyframes=tuple(
            H3RenderKeyframe(
                asset_id=item["asset_id"],
                timestamp_ms=item["timestamp_ms"],
                label=item["label"],
            )
            for item in value.get("keyframes", [])
        ),
        error=value.get("error"),
        warnings=tuple(value.get("warnings", [])),
    )


def _safe(value: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("identifier contains unsupported characters")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8") + b"\n"


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


__all__ = ["LocalH3RenderProjectStore"]
