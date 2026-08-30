"""Atomic local storage for automated production jobs."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain.krea2_batch import (
    Krea2AspectRatio,
    Krea2BatchSettings,
    Krea2LoraSelection,
)
from panelforge.domain.production import (
    ProductionCandidateAssessment,
    ProductionConfig,
    ProductionDecision,
    ProductionDecisionKind,
    ProductionDecisionOutcome,
    ProductionEvent,
    ProductionEventLevel,
    ProductionJob,
    ProductionLoraChoice,
    ProductionLoraChoiceSource,
    ProductionLoraPlan,
    ProductionMode,
    ProductionStage,
    ProductionStatus,
    ThermalPolicy,
)
from panelforge.domain.prompt_lab import CreativeFreedomAxes


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalProductionJobStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "production_jobs"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(self, job: ProductionJob) -> ProductionJob:
        with self._lock:
            directory = self._directory(job.job_id)
            directory.mkdir(exist_ok=False)
            timestamp = _timestamp()
            _atomic_write(
                directory / "job.json",
                _json_bytes(_serialize_job(job, timestamp, timestamp)),
            )
        return job

    def save(self, job: ProductionJob) -> ProductionJob:
        with self._lock:
            path = self._directory(job.job_id) / "job.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(job.job_id)
            current = _read_object(path)
            created_at = current.get("created_at")
            if not isinstance(created_at, str):
                raise ValueError("stored production job has no created_at")
            _atomic_write(
                path,
                _json_bytes(_serialize_job(job, created_at, _timestamp())),
            )
        return job

    def get(self, job_id: str) -> ProductionJob:
        with self._lock:
            path = self._directory(job_id) / "job.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(job_id)
            return _deserialize_job(_read_object(path))

    def list(self, limit: int = 30) -> list[ProductionJob]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if limit == 0:
            return []
        values: list[tuple[float, str, ProductionJob]] = []
        with self._lock:
            for directory in self._root.iterdir():
                path = directory / "job.json"
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append(
                        (path.stat().st_mtime, directory.name, _deserialize_job(_read_object(path)))
                    )
        values.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [value for _, _, value in values[:limit]]

    def _directory(self, identifier: str) -> Path:
        if not isinstance(identifier, str) or _SAFE_ID.fullmatch(identifier) is None:
            raise ValueError("unsafe production job identifier")
        candidate = self._root / identifier
        candidate.resolve().relative_to(self._root)
        if candidate.is_symlink():
            raise ValueError("production job directory cannot be a symlink")
        return candidate


def _serialize_job(job: ProductionJob, created_at: str, updated_at: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "created_at": created_at,
        "updated_at": updated_at,
        "job_id": job.job_id,
        "name": job.name,
        "intention": job.intention,
        "source_asset_id": job.source_asset_id,
        "source_filename": job.source_filename,
        "config": _serialize_config(job.config),
        "status": job.status.value,
        "stage": job.stage.value,
        "krea_project_id": job.krea_project_id,
        "krea_attempt_ids": list(job.krea_attempt_ids),
        "krea_feedback_attempt_ids": list(job.krea_feedback_attempt_ids),
        "lora_plan": _serialize_lora_plan(job.lora_plan),
        "selected_image_attempt_id": job.selected_image_attempt_id,
        "selected_image_asset_id": job.selected_image_asset_id,
        "image_review_approved": job.image_review_approved,
        "prompt_session_id": job.prompt_session_id,
        "h3_project_id": job.h3_project_id,
        "video_seed": job.video_seed,
        "preview_attempt_ids": list(job.preview_attempt_ids),
        "selected_preview_attempt_id": job.selected_preview_attempt_id,
        "video_review_approved": job.video_review_approved,
        "manual_revision_instruction": job.manual_revision_instruction,
        "final_attempt_id": job.final_attempt_id,
        "active_child_kind": job.active_child_kind,
        "active_child_attempt_id": job.active_child_attempt_id,
        "decisions": [_serialize_decision(value) for value in job.decisions],
        "events": [_serialize_event(value) for value in job.events],
        "pause_reason": job.pause_reason,
        "error": job.error,
        "cancel_requested": job.cancel_requested,
    }


def _deserialize_job(value: dict[str, Any]) -> ProductionJob:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported production job schema")
    return ProductionJob(
        job_id=value["job_id"],
        name=value["name"],
        intention=value["intention"],
        source_asset_id=value["source_asset_id"],
        source_filename=value["source_filename"],
        config=_deserialize_config(_object(value.get("config"), "config")),
        status=ProductionStatus(value.get("status", "draft")),
        stage=ProductionStage(value.get("stage", "setup")),
        krea_project_id=value.get("krea_project_id"),
        krea_attempt_ids=tuple(value.get("krea_attempt_ids", [])),
        krea_feedback_attempt_ids=tuple(value.get("krea_feedback_attempt_ids", [])),
        lora_plan=_deserialize_lora_plan(value.get("lora_plan")),
        selected_image_attempt_id=value.get("selected_image_attempt_id"),
        selected_image_asset_id=value.get("selected_image_asset_id"),
        image_review_approved=bool(value.get("image_review_approved", False)),
        prompt_session_id=value.get("prompt_session_id"),
        h3_project_id=value.get("h3_project_id"),
        video_seed=value.get("video_seed"),
        preview_attempt_ids=tuple(value.get("preview_attempt_ids", [])),
        selected_preview_attempt_id=value.get("selected_preview_attempt_id"),
        video_review_approved=bool(value.get("video_review_approved", False)),
        manual_revision_instruction=value.get("manual_revision_instruction"),
        final_attempt_id=value.get("final_attempt_id"),
        active_child_kind=value.get("active_child_kind"),
        active_child_attempt_id=value.get("active_child_attempt_id"),
        decisions=tuple(_deserialize_decision(_object(item, "decision")) for item in value.get("decisions", [])),
        events=tuple(_deserialize_event(_object(item, "event")) for item in value.get("events", [])),
        pause_reason=value.get("pause_reason"),
        error=value.get("error"),
        cancel_requested=bool(value.get("cancel_requested", False)),
    )


def _serialize_config(config: ProductionConfig) -> dict[str, object]:
    return {
        "model_id": config.model_id,
        "image_settings": {
            "model_name": config.image_settings.model_name,
            "aspect_ratio": config.image_settings.aspect_ratio.value,
            "megapixels": config.image_settings.megapixels,
            "loras": [
                {"name": value.name, "strength": value.strength}
                for value in config.image_settings.loras
            ],
        },
        "mode": config.mode.value,
        "creative_freedom": config.creative_freedom,
        "creative_axes": {
            "scene_life": config.creative_axes.scene_life,
            "camera": config.creative_axes.camera,
            "extra_motion": config.creative_axes.extra_motion,
        },
        "image_attempt_count": config.image_attempt_count,
        "video_preview_limit": config.video_preview_limit,
        "video_acceptance_score": config.video_acceptance_score,
        "duration_seconds": config.duration_seconds,
        "video_steps": config.video_steps,
        "preview_megapixels": config.preview_megapixels,
        "final_megapixels": config.final_megapixels,
        "music_enabled": config.music_enabled,
        "assisted_lora_selection": config.assisted_lora_selection,
        "creative_direction_enabled": config.creative_direction_enabled,
        "creative_audacity": config.creative_audacity,
        "thermal": {
            "stop_temperature_c": config.thermal.stop_temperature_c,
            "resume_temperature_c": config.thermal.resume_temperature_c,
            "cooldown_seconds": config.thermal.cooldown_seconds,
            "monitor_local": config.thermal.monitor_local,
            "monitor_remote": config.thermal.monitor_remote,
            "pause_when_unavailable": config.thermal.pause_when_unavailable,
        },
    }


def _deserialize_config(value: dict[str, Any]) -> ProductionConfig:
    image = _object(value.get("image_settings"), "image_settings")
    axes = _object(value.get("creative_axes"), "creative_axes")
    thermal = _object(value.get("thermal"), "thermal")
    return ProductionConfig(
        model_id=value["model_id"],
        image_settings=Krea2BatchSettings(
            model_name=image["model_name"],
            aspect_ratio=Krea2AspectRatio(image["aspect_ratio"]),
            megapixels=image["megapixels"],
            loras=tuple(
                Krea2LoraSelection(name=item["name"], strength=item["strength"])
                for item in image.get("loras", [])
            ),
        ),
        mode=ProductionMode(value.get("mode", "full_auto")),
        creative_freedom=value.get("creative_freedom", 100),
        creative_axes=CreativeFreedomAxes(
            scene_life=axes.get("scene_life", 3),
            camera=axes.get("camera", 3),
            extra_motion=axes.get("extra_motion", 3),
        ),
        image_attempt_count=value.get("image_attempt_count", 3),
        video_preview_limit=value.get("video_preview_limit", 3),
        video_acceptance_score=value.get("video_acceptance_score", 80),
        duration_seconds=value.get("duration_seconds", 10.0),
        video_steps=value.get("video_steps", 10),
        preview_megapixels=value.get("preview_megapixels", 0.2),
        final_megapixels=value.get("final_megapixels", 1.2),
        music_enabled=bool(value.get("music_enabled", False)),
        assisted_lora_selection=bool(value.get("assisted_lora_selection", False)),
        creative_direction_enabled=bool(
            value.get("creative_direction_enabled", False)
        ),
        creative_audacity=value.get(
            "creative_audacity",
            1 if value.get("creative_direction_enabled", False) else 0,
        ),
        thermal=ThermalPolicy(
            stop_temperature_c=thermal.get("stop_temperature_c", 85.0),
            resume_temperature_c=thermal.get("resume_temperature_c", 40.0),
            cooldown_seconds=thermal.get("cooldown_seconds", 120),
            monitor_local=bool(thermal.get("monitor_local", True)),
            monitor_remote=bool(thermal.get("monitor_remote", True)),
            pause_when_unavailable=bool(thermal.get("pause_when_unavailable", True)),
        ),
    )


def _serialize_decision(value: ProductionDecision) -> dict[str, object]:
    return {
        "decision_id": value.decision_id,
        "timestamp": value.timestamp,
        "kind": value.kind.value,
        "outcome": value.outcome.value,
        "attempt_id": value.attempt_id,
        "score": value.score,
        "rationale": value.rationale,
        "revision_instruction": value.revision_instruction,
        "assessments": [
            {
                "attempt_id": assessment.attempt_id,
                "score": assessment.score,
                "summary": assessment.summary,
            }
            for assessment in value.assessments
        ],
    }


def _deserialize_decision(value: dict[str, Any]) -> ProductionDecision:
    return ProductionDecision(
        decision_id=value["decision_id"],
        timestamp=value["timestamp"],
        kind=ProductionDecisionKind(value["kind"]),
        outcome=ProductionDecisionOutcome(value["outcome"]),
        attempt_id=value["attempt_id"],
        score=value["score"],
        rationale=value["rationale"],
        revision_instruction=value.get("revision_instruction"),
        assessments=tuple(
            ProductionCandidateAssessment(
                attempt_id=item["attempt_id"],
                score=item["score"],
                summary=item["summary"],
            )
            for item in value.get("assessments", [])
        ),
    )


def _serialize_lora_plan(value: ProductionLoraPlan | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "choices": [
            {
                "name": choice.name,
                "strength": choice.strength,
                "source": choice.source.value,
                "expected_effect": choice.expected_effect,
            }
            for choice in value.choices
        ],
        "rationale": value.rationale,
    }


def _deserialize_lora_plan(value: object) -> ProductionLoraPlan | None:
    if value is None:
        return None
    raw = _object(value, "lora_plan")
    return ProductionLoraPlan(
        choices=tuple(
            ProductionLoraChoice(
                name=item["name"],
                strength=item["strength"],
                source=ProductionLoraChoiceSource(item["source"]),
                expected_effect=item["expected_effect"],
            )
            for item in raw.get("choices", [])
        ),
        rationale=raw["rationale"],
    )


def _serialize_event(value: ProductionEvent) -> dict[str, object]:
    return {
        "event_id": value.event_id,
        "timestamp": value.timestamp,
        "stage": value.stage.value,
        "level": value.level.value,
        "message": value.message,
    }


def _deserialize_event(value: dict[str, Any]) -> ProductionEvent:
    return ProductionEvent(
        event_id=value["event_id"],
        timestamp=value["timestamp"],
        stage=ProductionStage(value["stage"]),
        level=ProductionEventLevel(value["level"]),
        message=value["message"],
    )


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("production job document must be an object")
    return value


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = ["LocalProductionJobStore"]
