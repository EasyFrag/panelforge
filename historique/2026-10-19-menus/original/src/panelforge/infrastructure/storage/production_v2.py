"""Atomic JSON storage for Production V2 projects and memory profiles."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain import (
    Krea2AspectRatio,
    Krea2BatchSettings,
    Krea2LoraSelection,
    H3VideoLoraSelection,
    ProductionV2Anchor,
    ProductionV2AnchorRole,
    ProductionV2Candidate,
    ProductionV2CandidateKind,
    ProductionV2CandidateStatus,
    ProductionV2Event,
    ProductionV2LlmTrace,
    ProductionV2LlmTraceStatus,
    ProductionV2MemoryObservation,
    ProductionV2MemoryProfile,
    ProductionV2Preference,
    ProductionV2PromptStrategy,
    ProductionV2Project,
    ProductionV2ReferenceMode,
    ProductionV2Stage,
    ProductionV2Status,
    ProductionV2VisualRecipeRevision,
    VideoAspectRatio,
)


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalProductionV2Store:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "production_v2"
        self._projects = self._root / "projects"
        self._profiles = self._root / "memory_profiles"
        self._projects.mkdir(parents=True, exist_ok=True)
        self._profiles.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create_project(self, project: ProductionV2Project) -> ProductionV2Project:
        with self._lock:
            directory = self._directory(self._projects, project.project_id)
            directory.mkdir(exist_ok=False)
            now = _timestamp()
            _write(directory / "project.json", {
                "schema_version": 6,
                "created_at": now,
                "updated_at": now,
                "project": _serialize_project(project),
            })
        return project

    def save_project(self, project: ProductionV2Project) -> ProductionV2Project:
        with self._lock:
            path = self._directory(self._projects, project.project_id) / "project.json"
            value = _read(path)
            _write(path, {
                "schema_version": 6,
                "created_at": value["created_at"],
                "updated_at": _timestamp(),
                "project": _serialize_project(project),
            })
        return project

    def get_project(self, project_id: str) -> ProductionV2Project:
        with self._lock:
            path = self._directory(self._projects, project_id) / "project.json"
            return _deserialize_project(_object(_read(path)["project"]))

    def list_projects(self, limit: int = 30) -> list[ProductionV2Project]:
        values: list[tuple[float, ProductionV2Project]] = []
        with self._lock:
            for directory in self._projects.iterdir():
                path = directory / "project.json"
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append((path.stat().st_mtime, _deserialize_project(_object(_read(path)["project"]))))
        values.sort(key=lambda item: item[0], reverse=True)
        return [value for _, value in values[:max(0, limit)]]

    def create_profile(self, profile: ProductionV2MemoryProfile) -> ProductionV2MemoryProfile:
        with self._lock:
            path = self._profile_path(profile.profile_id)
            if path.exists():
                raise FileExistsError(profile.profile_id)
            _write(path, {"schema_version": 1, "profile": _serialize_profile(profile)})
        return profile

    def save_profile(self, profile: ProductionV2MemoryProfile) -> ProductionV2MemoryProfile:
        with self._lock:
            path = self._profile_path(profile.profile_id)
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(profile.profile_id)
            _write(path, {"schema_version": 1, "profile": _serialize_profile(profile)})
        return profile

    def get_profile(self, profile_id: str) -> ProductionV2MemoryProfile:
        with self._lock:
            return _deserialize_profile(_object(_read(self._profile_path(profile_id))["profile"]))

    def list_profiles(self) -> list[ProductionV2MemoryProfile]:
        values: list[ProductionV2MemoryProfile] = []
        with self._lock:
            for path in self._profiles.glob("*.json"):
                if path.is_file() and not path.is_symlink():
                    values.append(_deserialize_profile(_object(_read(path)["profile"])))
        return sorted(values, key=lambda value: (value.name.casefold(), value.profile_id))

    def _profile_path(self, identifier: str) -> Path:
        self._directory(self._profiles, identifier)
        path = self._profiles / f"{identifier}.json"
        path.resolve().relative_to(self._profiles)
        return path

    @staticmethod
    def _directory(root: Path, identifier: str) -> Path:
        if not isinstance(identifier, str) or _SAFE_ID.fullmatch(identifier) is None:
            raise ValueError("unsafe Production V2 identifier")
        path = root / identifier
        path.resolve().relative_to(root)
        if path.is_symlink():
            raise ValueError("Production V2 storage entry cannot be a symlink")
        return path


def _serialize_project(value: ProductionV2Project) -> dict[str, object]:
    return {
        "project_id": value.project_id,
        "name": value.name,
        "intention": value.intention,
        "source_asset_id": value.source_asset_id,
        "source_filename": value.source_filename,
        "initial_model_id": value.initial_model_id,
        "video_compile_model_id": value.video_compile_model_id,
        "memory_profile_id": value.memory_profile_id,
        "preset_id": value.preset_id,
        "stage": value.stage.value,
        "status": value.status.value,
        "candidates": [_serialize_candidate(item) for item in value.candidates],
        "recipe_revisions": [_serialize_recipe(item) for item in value.recipe_revisions],
        "active_recipe_revision_id": value.active_recipe_revision_id,
        "anchors": [_serialize_anchor(item) for item in value.anchors],
        "prompt_session_id": value.prompt_session_id,
        "h3_project_id": value.h3_project_id,
        "archived_prompt_session_ids": list(value.archived_prompt_session_ids),
        "archived_h3_project_ids": list(value.archived_h3_project_ids),
        "video_seed": value.video_seed,
        "video_seed_locked": value.video_seed_locked,
        "video_intention": value.video_intention,
        "video_aspect_ratio": (
            value.video_aspect_ratio.value if value.video_aspect_ratio is not None else None
        ),
        "duration_seconds": value.duration_seconds,
        "preview_megapixels": value.preview_megapixels,
        "final_megapixels": value.final_megapixels,
        "video_steps": value.video_steps,
        "spectrum_enabled": value.spectrum_enabled,
        "music_enabled": value.music_enabled,
        "video_lora": ({
            "name": value.video_lora.name,
            "strength": value.video_lora.strength,
            "clip_last_layer": value.video_lora.clip_last_layer,
        } if value.video_lora is not None else None),
        "creative_audacity": value.creative_audacity,
        "revision_audacity": value.revision_audacity,
        "stop_temperature_c": value.stop_temperature_c,
        "resume_temperature_c": value.resume_temperature_c,
        "cooldown_seconds": value.cooldown_seconds,
        "remote_thermal_latched": value.remote_thermal_latched,
        "remote_thermal_latched_at": value.remote_thermal_latched_at,
        "preview_attempt_ids": list(value.preview_attempt_ids),
        "selected_preview_attempt_id": value.selected_preview_attempt_id,
        "final_attempt_id": value.final_attempt_id,
        "active_operation": value.active_operation,
        "active_operation_id": value.active_operation_id,
        "active_child_project_id": value.active_child_project_id,
        "active_child_attempt_id": value.active_child_attempt_id,
        "llm_traces": [_serialize_trace(item) for item in value.llm_traces],
        "active_llm_trace_id": value.active_llm_trace_id,
        "events": [item.__dict__ if hasattr(item, "__dict__") else {
            "event_id": item.event_id, "timestamp": item.timestamp,
            "stage": item.stage.value, "level": item.level, "message": item.message,
        } for item in value.events],
        "error": value.error,
    }


def _deserialize_project(value: dict[str, Any]) -> ProductionV2Project:
    return ProductionV2Project(
        project_id=value["project_id"], name=value["name"], intention=value["intention"],
        source_asset_id=value["source_asset_id"], source_filename=value["source_filename"],
        initial_model_id=value["initial_model_id"], memory_profile_id=value["memory_profile_id"],
        video_compile_model_id=value.get("video_compile_model_id", value["initial_model_id"]),
        preset_id=value.get("preset_id", "human_exploration"),
        stage=ProductionV2Stage(value.get("stage", "image_calibration")),
        status=ProductionV2Status(value.get("status", "ready")),
        candidates=tuple(_deserialize_candidate(_object(item)) for item in value.get("candidates", [])),
        recipe_revisions=tuple(_deserialize_recipe(_object(item)) for item in value.get("recipe_revisions", [])),
        active_recipe_revision_id=value.get("active_recipe_revision_id"),
        anchors=tuple(_deserialize_anchor(_object(item)) for item in value.get("anchors", [])),
        prompt_session_id=value.get("prompt_session_id"), h3_project_id=value.get("h3_project_id"),
        archived_prompt_session_ids=tuple(value.get("archived_prompt_session_ids", [])),
        archived_h3_project_ids=tuple(value.get("archived_h3_project_ids", [])),
        video_seed=value.get("video_seed"),
        video_seed_locked=bool(value.get("video_seed_locked", True)),
        video_intention=value.get("video_intention"),
        video_aspect_ratio=(
            VideoAspectRatio(value["video_aspect_ratio"])
            if value.get("video_aspect_ratio") is not None else None
        ),
        duration_seconds=value.get("duration_seconds", 6.0),
        preview_megapixels=value.get("preview_megapixels", 0.2),
        final_megapixels=value.get("final_megapixels", 1.2),
        video_steps=value.get("video_steps", 25),
        spectrum_enabled=bool(value.get("spectrum_enabled", True)),
        music_enabled=bool(value.get("music_enabled", False)),
        video_lora=(H3VideoLoraSelection(
            name=value["video_lora"]["name"],
            strength=value["video_lora"].get("strength", 0.5),
            clip_last_layer=value["video_lora"].get("clip_last_layer", -2),
        ) if isinstance(value.get("video_lora"), dict) else None),
        creative_audacity=value.get("creative_audacity", 3),
        revision_audacity=value.get("revision_audacity", 3),
        stop_temperature_c=value.get("stop_temperature_c", 85.0),
        resume_temperature_c=value.get("resume_temperature_c", 40.0),
        cooldown_seconds=value.get("cooldown_seconds", 120),
        remote_thermal_latched=bool(value.get("remote_thermal_latched", False)),
        remote_thermal_latched_at=value.get("remote_thermal_latched_at"),
        preview_attempt_ids=tuple(value.get("preview_attempt_ids", [])),
        selected_preview_attempt_id=value.get("selected_preview_attempt_id"),
        final_attempt_id=value.get("final_attempt_id"), active_operation=value.get("active_operation"),
        active_operation_id=value.get("active_operation_id"),
        active_child_project_id=value.get("active_child_project_id"),
        active_child_attempt_id=value.get("active_child_attempt_id"),
        llm_traces=tuple(
            _deserialize_trace(_object(item)) for item in value.get("llm_traces", [])
        ),
        active_llm_trace_id=value.get("active_llm_trace_id"),
        events=tuple(ProductionV2Event(
            event_id=item["event_id"], timestamp=item["timestamp"],
            stage=ProductionV2Stage(item["stage"]), level=item["level"], message=item["message"],
        ) for item in value.get("events", [])), error=value.get("error"),
    )


def _serialize_candidate(value: ProductionV2Candidate) -> dict[str, object]:
    return {
        "candidate_id": value.candidate_id, "index": value.index, "round_index": value.round_index,
        "role": value.role.value, "memory_profile_id": value.memory_profile_id,
        "requested_model_id": value.requested_model_id, "actual_model_id": value.actual_model_id,
        "settings": _serialize_settings(value.settings),
        "status": value.status.value, "feedback_parent_id": value.feedback_parent_id,
        "generation_kind": value.generation_kind.value,
        "child_project_id": value.child_project_id, "child_attempt_id": value.child_attempt_id,
        "prompt": value.prompt, "seed": value.seed, "output_asset_id": value.output_asset_id,
        "preference": value.preference.value, "comment": value.comment,
        "instruction": value.instruction,
        "assisted_lora_names": list(value.assisted_lora_names),
        "assisted_lora_rationale": value.assisted_lora_rationale,
        "batch_id": value.batch_id,
        "prompt_strategy": value.prompt_strategy.value,
        "reference_mode": value.reference_mode.value,
        "guidance_candidate_id": value.guidance_candidate_id,
        "preserve_seed": value.preserve_seed,
        "preserve_model": value.preserve_model,
        "preserve_loras": value.preserve_loras,
        "prompt_trace_id": value.prompt_trace_id,
        "error": value.error,
    }


def _deserialize_candidate(value: dict[str, Any]) -> ProductionV2Candidate:
    return ProductionV2Candidate(
        candidate_id=value["candidate_id"], index=value["index"], round_index=value["round_index"],
        role=ProductionV2AnchorRole(value["role"]), memory_profile_id=value["memory_profile_id"],
        requested_model_id=value["requested_model_id"], actual_model_id=value.get("actual_model_id"),
        settings=_deserialize_settings(_object(value["settings"])),
        status=ProductionV2CandidateStatus(value["status"]),
        generation_kind=ProductionV2CandidateKind(value.get("generation_kind", "creative")),
        feedback_parent_id=value.get("feedback_parent_id"),
        child_project_id=value.get("child_project_id"), child_attempt_id=value.get("child_attempt_id"),
        prompt=value.get("prompt"), seed=value.get("seed"), output_asset_id=value.get("output_asset_id"),
        preference=ProductionV2Preference(value.get("preference", "none")),
        comment=value.get("comment", ""), instruction=value.get("instruction", ""),
        assisted_lora_names=tuple(value.get("assisted_lora_names", [])),
        assisted_lora_rationale=value.get("assisted_lora_rationale", ""),
        batch_id=value.get("batch_id"),
        prompt_strategy=ProductionV2PromptStrategy(
            value.get("prompt_strategy", "evolve_between")
        ),
        reference_mode=ProductionV2ReferenceMode(
            value.get("reference_mode", "recipe")
        ),
        guidance_candidate_id=value.get("guidance_candidate_id"),
        preserve_seed=bool(value.get("preserve_seed", False)),
        preserve_model=bool(value.get("preserve_model", False)),
        preserve_loras=bool(value.get("preserve_loras", False)),
        prompt_trace_id=value.get("prompt_trace_id"),
        error=value.get("error"),
    )


def _serialize_trace(value: ProductionV2LlmTrace) -> dict[str, object]:
    return {
        "trace_id": value.trace_id,
        "batch_id": value.batch_id,
        "sequence": value.sequence,
        "total": value.total,
        "purpose": value.purpose,
        "label": value.label,
        "model_id": value.model_id,
        "status": value.status.value,
        "created_at": value.created_at,
        "candidate_id": value.candidate_id,
        "reference_asset_ids": list(value.reference_asset_ids),
        "input_text": value.input_text,
        "thinking": value.thinking,
        "output": value.output,
        "error": value.error,
        "started_at": value.started_at,
        "completed_at": value.completed_at,
    }


def _deserialize_trace(value: dict[str, Any]) -> ProductionV2LlmTrace:
    return ProductionV2LlmTrace(
        trace_id=value["trace_id"],
        batch_id=value["batch_id"],
        sequence=int(value["sequence"]),
        total=int(value["total"]),
        purpose=value["purpose"],
        label=value["label"],
        model_id=value["model_id"],
        status=ProductionV2LlmTraceStatus(value.get("status", "pending")),
        created_at=value["created_at"],
        candidate_id=value.get("candidate_id"),
        reference_asset_ids=tuple(value.get("reference_asset_ids", [])),
        input_text=value.get("input_text", ""),
        thinking=value.get("thinking", ""),
        output=value.get("output", ""),
        error=value.get("error"),
        started_at=value.get("started_at"),
        completed_at=value.get("completed_at"),
    )


def _serialize_recipe(value: ProductionV2VisualRecipeRevision) -> dict[str, object]:
    return {"revision_id": value.revision_id, "index": value.index, "created_at": value.created_at,
            "source_candidate_id": value.source_candidate_id, "settings": _serialize_settings(value.settings),
            "prompt": value.prompt, "seed": value.seed, "asset_id": value.asset_id}


def _deserialize_recipe(value: dict[str, Any]) -> ProductionV2VisualRecipeRevision:
    return ProductionV2VisualRecipeRevision(
        revision_id=value["revision_id"], index=value["index"], created_at=value["created_at"],
        source_candidate_id=value["source_candidate_id"], settings=_deserialize_settings(_object(value["settings"])),
        prompt=value.get("prompt", ""), seed=value.get("seed"), asset_id=value.get("asset_id"),
    )


def _serialize_anchor(value: ProductionV2Anchor) -> dict[str, object]:
    return {"anchor_id": value.anchor_id, "role": value.role.value, "asset_id": value.asset_id,
            "label": value.label, "source_kind": value.source_kind, "candidate_id": value.candidate_id,
            "recipe_revision_id": value.recipe_revision_id, "created_at": value.created_at}


def _deserialize_anchor(value: dict[str, Any]) -> ProductionV2Anchor:
    return ProductionV2Anchor(
        anchor_id=value["anchor_id"], role=ProductionV2AnchorRole(value["role"]),
        asset_id=value["asset_id"], label=value["label"], source_kind=value["source_kind"],
        candidate_id=value.get("candidate_id"), recipe_revision_id=value.get("recipe_revision_id"),
        created_at=value["created_at"],
    )


def _serialize_profile(value: ProductionV2MemoryProfile) -> dict[str, object]:
    return {"profile_id": value.profile_id, "name": value.name, "created_at": value.created_at,
            "observations": [{
                "project_id": item.project_id, "candidate_id": item.candidate_id,
                "timestamp": item.timestamp, "preference": item.preference.value,
                "comment": item.comment, "prompt": item.prompt, "model_id": item.model_id,
                "settings": _serialize_settings(item.settings), "role": item.role.value,
            } for item in value.observations]}


def _deserialize_profile(value: dict[str, Any]) -> ProductionV2MemoryProfile:
    return ProductionV2MemoryProfile(
        profile_id=value["profile_id"], name=value["name"], created_at=value["created_at"],
        observations=tuple(ProductionV2MemoryObservation(
            project_id=item["project_id"], candidate_id=item["candidate_id"], timestamp=item["timestamp"],
            preference=ProductionV2Preference(item["preference"]), comment=item.get("comment", ""),
            prompt=item.get("prompt", ""), model_id=item.get("model_id", "unknown"),
            settings=_deserialize_settings(_object(item["settings"])),
            role=ProductionV2AnchorRole(item.get("role", "calibration")),
        ) for item in value.get("observations", [])),
    )


def _serialize_settings(value: Krea2BatchSettings) -> dict[str, object]:
    return {"model_name": value.model_name, "aspect_ratio": value.aspect_ratio.value,
            "megapixels": value.megapixels,
            "loras": [{"name": item.name, "strength": item.strength} for item in value.loras]}


def _deserialize_settings(value: dict[str, Any]) -> Krea2BatchSettings:
    return Krea2BatchSettings(
        model_name=value["model_name"], aspect_ratio=Krea2AspectRatio(value["aspect_ratio"]),
        megapixels=value["megapixels"],
        loras=tuple(Krea2LoraSelection(name=item["name"], strength=item["strength"])
                    for item in value.get("loras", [])),
    )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Production V2 document contains a non-object")
    return value


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(path.name)
    return _object(json.loads(path.read_text(encoding="utf-8")))


def _write(path: Path, value: object) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = ["LocalProductionV2Store"]
