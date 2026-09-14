"""Atomic local persistence for KREA2 edit backlog entries and attempts."""

from __future__ import annotations
from panelforge.domain.dlss import DlssResult

from datetime import datetime, timezone
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from panelforge.domain.krea2_batch import Krea2LoraSelection, Krea2PromptLanguage
from panelforge.domain.krea2_edit import (
    Krea2EditAttempt,
    Krea2EditCrop,
    Krea2EditAttemptStatus,
    Krea2EditMetadata,
    Krea2EditPromptRevision,
    Krea2EditPromptStatus,
    Krea2EditRetouch,
    Krea2EditUpscale,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.krea2_edit_versions import Krea2EditRevision
from panelforge.domain.edit_subject_reference import EditSubjectReference
from panelforge.domain.recipes import RecipeRef
from panelforge.domain.firered_edit import FireRedEditSettings
from panelforge.domain.edit_settings import edit_settings_record


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalKrea2EditStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "krea2_edits"
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, source: Krea2EditSource) -> Krea2EditSource:
        _source(source)
        directory = self._entry(source.source_id)
        directory.mkdir(exist_ok=False)
        try:
            _atomic_write(directory / "source.json", _json_bytes(_to_dict(source)))
        except BaseException:
            (directory / "source.json").unlink(missing_ok=True)
            directory.rmdir()
            raise
        return source

    def save(self, source: Krea2EditSource) -> Krea2EditSource:
        _source(source)
        path = self._entry(source.source_id) / "source.json"
        if not path.is_file():
            raise KeyError(source.source_id)
        existing = _from_dict(_read(path))
        if existing.source_id != source.source_id:
            raise ValueError("stored KREA2 edit source identity mismatch")
        _atomic_write(path, _json_bytes(_to_dict(source)))
        return source

    def get(self, source_id: str) -> Krea2EditSource:
        source = _from_dict(_read(self._entry(source_id) / "source.json"))
        if not self._revision_visible(source):
            raise KeyError(source_id)
        return source

    def _revision_visible(self, source: Krea2EditSource) -> bool:
        if source.revision is None:
            return True
        path = self._entry(source.project_id) / "source.json"
        if not path.is_file():
            return False
        root = _from_dict(_read(path))
        return root.source_id == source.project_id and root.revision == source.revision

    def create_revision(self, stages: tuple[Krea2EditSource, ...]) -> Krea2EditSource:
        # Publish the root last. Partial copies are invisible and a retry can
        # finish them; no existing project or image is overwritten/deleted.
        root = stages[0]
        if (root.revision is None or root.source_id != root.project_id
                or [s.stage_index for s in stages] != list(range(1, len(stages) + 1))
                or len(stages) != root.revision.stage_index
                or any(s.project_id != root.project_id or s.revision != root.revision for s in stages)):
            raise ValueError("invalid revised chain")
        root_path = self._entry(root.source_id) / "source.json"
        if root_path.is_file():
            existing = self.get(root.source_id)
            if existing.revision != root.revision:
                raise ValueError("revision identity conflict")
            return self.get(stages[-1].source_id)
        for stage in reversed(stages):
            directory = self._entry(stage.source_id)
            directory.mkdir(exist_ok=True)
            path = directory / "source.json"
            if path.is_file():
                previous = _from_dict(_read(path))
                if previous.project_id != root.project_id or previous.revision is None:
                    raise ValueError("revision source identity conflict")
            _atomic_write(path, _json_bytes(_to_dict(stage)))
        return stages[-1]

    def save_restart(self, previous: Krea2EditSource, restarted: Krea2EditSource) -> Krea2EditSource:
        if restarted != previous.restart() or self.get(previous.source_id) != previous:
            raise ValueError("L’étape a changé avant son enregistrement. Recharge l’atelier.")
        directory = self._entry(previous.source_id) / "restarts"
        directory.mkdir(exist_ok=True)
        # Archive first: a failed archive/save leaves the active state untouched.
        _atomic_write(directory / f"before-{restarted.restart_count}.json", _json_bytes(_to_dict(previous)))
        return self.save(restarted)

    def list(self, limit: int = 100, *, include_hidden: bool = False) -> list[Krea2EditSource]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        indexed: list[tuple[float, str, Krea2EditSource]] = []
        for directory in self._root.iterdir():
            if not directory.is_dir() or directory.is_symlink():
                continue
            path = directory / "source.json"
            if not path.is_file():
                continue
            source = _from_dict(_read(path))
            if not self._revision_visible(source):
                continue
            if source.state is Krea2EditSourceState.HIDDEN and not include_hidden:
                continue
            indexed.append((path.stat().st_mtime, source.source_id, source))
        indexed.sort(key=lambda value: (value[0], value[1]), reverse=True)
        return [value[2] for value in indexed[:limit]]

    def find_batch_source(self, batch_id: str, item_id: str) -> Krea2EditSource | None:
        for source in self.list(2**31 - 1, include_hidden=True):
            if source.source_batch_id == batch_id and source.source_batch_item_id == item_id:
                return source
        return None

    def save_compiled_workflow(
        self,
        source_id: str,
        attempt_id: str,
        workflow: dict[str, Any],
    ) -> str:
        import hashlib

        _safe(attempt_id)
        directory = self._entry(source_id) / "attempts" / attempt_id
        directory.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            workflow,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        _atomic_write(directory / "compiled_workflow.json", content)
        return hashlib.sha256(content).hexdigest()

    def _entry(self, source_id: str) -> Path:
        _safe(source_id)
        path = (self._root / source_id).resolve()
        if path.parent != self._root:
            raise ValueError("unsafe KREA2 edit source path")
        return path


def _to_dict(source: Krea2EditSource) -> dict[str, object]:
    return {
        "schema_version": 12,
        "subject_reference": asdict(source.subject_reference) if source.subject_reference else None,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_id": source.source_id,
        "restart_count": source.restart_count,
        "revision": asdict(source.revision) if source.revision else None,
        "copied_from_source_id": source.copied_from_source_id,
        "revision_activation": source.revision_activation,
        "recipe": {
            "operation_id": source.recipe.operation_id,
            "recipe_id": source.recipe.recipe_id,
            "version": source.recipe.version,
            "workflow_sha256": source.recipe.workflow_sha256,
        },
        "source_asset_id": source.source_asset_id,
        "filename": source.filename,
        "prompt_language": source.prompt_language.value,
        "project_id": source.project_id,
        "stage_index": source.stage_index,
        "parent_source_id": source.parent_source_id,
        "parent_attempt_id": source.parent_attempt_id,
        "accepted_attempt_id": source.accepted_attempt_id,
        "project_name": source.project_name,
        "accepted_label": source.accepted_label,
        "export_path": source.export_path,
        "export_error": source.export_error,
        "source_batch_id": source.source_batch_id,
        "source_batch_item_id": source.source_batch_item_id,
        "metadata": _metadata_dict(source.metadata),
        "state": source.state.value,
        "prompt_status": source.prompt_status.value,
        "instruction": source.instruction,
        "generated_prompt": source.generated_prompt,
        "raw_prompt_response": source.raw_prompt_response,
        "prompt_model_id": source.prompt_model_id,
        "prompt_error": source.prompt_error,
        "revisions": [_revision_dict(value) for value in source.revisions],
        "attempts": [_attempt_dict(value) for value in source.attempts],
    }


def _from_dict(value: dict[str, Any]) -> Krea2EditSource:
    schema_version = value.get("schema_version")
    if schema_version not in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}:
        raise ValueError("unsupported KREA2 edit source schema")
    recipe = value["recipe"]
    return Krea2EditSource(
        source_id=value["source_id"],
        restart_count=value.get("restart_count", 0),
        revision=Krea2EditRevision(**value["revision"]) if schema_version >= 6 and value.get("revision") else None,
        copied_from_source_id=value.get("copied_from_source_id") if schema_version >= 6 else None,
        revision_activation=value.get("revision_activation", 0) if schema_version >= 6 else 0,
        recipe=RecipeRef(
            operation_id=recipe["operation_id"],
            recipe_id=recipe["recipe_id"],
            version=recipe["version"],
            workflow_sha256=recipe["workflow_sha256"],
        ),
        source_asset_id=value["source_asset_id"],
        subject_reference=EditSubjectReference(**value["subject_reference"]) if value.get("subject_reference") else None,
        filename=value["filename"],
        prompt_language=Krea2PromptLanguage(value.get("prompt_language", "en")),
        project_id=(value.get("project_id") if schema_version >= 2 else value["source_id"]),
        stage_index=(value.get("stage_index", 1) if schema_version >= 2 else 1),
        parent_source_id=(value.get("parent_source_id") if schema_version >= 2 else None),
        parent_attempt_id=(value.get("parent_attempt_id") if schema_version >= 2 else None),
        accepted_attempt_id=(value.get("accepted_attempt_id") if schema_version >= 2 else None),
        project_name=(value.get("project_name") if schema_version >= 3 else None),
        accepted_label=(value.get("accepted_label") if schema_version >= 3 else None),
        export_path=(value.get("export_path") if schema_version >= 3 else None),
        export_error=(value.get("export_error") if schema_version >= 3 else None),
        source_batch_id=value["source_batch_id"],
        source_batch_item_id=value["source_batch_item_id"],
        metadata=_metadata_from_dict(value["metadata"]),
        state=Krea2EditSourceState(value["state"]),
        prompt_status=Krea2EditPromptStatus(value["prompt_status"]),
        instruction=value["instruction"],
        generated_prompt=value["generated_prompt"],
        raw_prompt_response=value["raw_prompt_response"],
        prompt_model_id=value["prompt_model_id"],
        prompt_error=value["prompt_error"],
        revisions=(
            tuple(_revision_from_dict(raw) for raw in value.get("revisions", []))
            if schema_version >= 2
            else ()
        ),
        attempts=tuple(_attempt_from_dict(raw) for raw in value["attempts"]),
    )


def _revision_dict(value: Krea2EditPromptRevision) -> dict[str, object]:
    return {
        "revision_id": value.revision_id,
        "instruction": value.instruction,
        "base_prompt": value.base_prompt,
        "prompt": value.prompt,
        "model_id": value.model_id,
        "prompt_language": value.prompt_language.value,
        "feedback_attempt_id": value.feedback_attempt_id,
        "assistant_message": value.assistant_message,
        "assistance_version": value.assistance_version,
        "render_engine": value.render_engine,
    }


def _revision_from_dict(value: dict[str, Any]) -> Krea2EditPromptRevision:
    return Krea2EditPromptRevision(
        revision_id=value["revision_id"],
        instruction=value["instruction"],
        base_prompt=value["base_prompt"],
        prompt=value["prompt"],
        model_id=value["model_id"],
        prompt_language=Krea2PromptLanguage(value.get("prompt_language", "en")),
        feedback_attempt_id=value.get("feedback_attempt_id"),
        assistant_message=value.get("assistant_message"),
        assistance_version=value.get("assistance_version", "1.0.0"),
        render_engine=value.get("render_engine", "krea2"),
    )


def _metadata_dict(value: Krea2EditMetadata) -> dict[str, object]:
    return {
        "prompt": value.prompt,
        "model_name": value.model_name,
        "aspect_ratio": value.aspect_ratio.value if value.aspect_ratio else None,
        "megapixels": value.megapixels,
        "seed": str(value.seed) if value.seed is not None else None,
        "loras": [_lora_dict(lora) for lora in value.loras],
        "origin": value.origin,
        "warnings": list(value.warnings),
        "ref_boost": value.ref_boost,
        "steps": value.steps,
        "firered_settings": edit_settings_record(value.firered_settings) if value.firered_settings else None,
    }


def _metadata_from_dict(value: dict[str, Any]) -> Krea2EditMetadata:
    return Krea2EditMetadata(
        prompt=value["prompt"],
        model_name=value["model_name"],
        aspect_ratio=Krea2AspectRatio(value["aspect_ratio"]) if value["aspect_ratio"] else None,
        megapixels=value["megapixels"],
        seed=int(value["seed"]) if value["seed"] is not None else None,
        loras=tuple(Krea2LoraSelection(**raw) for raw in value["loras"]),
        origin=value["origin"],
        warnings=tuple(value["warnings"]),
        ref_boost=value.get("ref_boost"),
        steps=value.get("steps"),
        firered_settings=_settings_from_dict(value["firered_settings"]) if value.get("firered_settings") else None,
    )


def _attempt_dict(value: Krea2EditAttempt) -> dict[str, object]:
    return {
        "attempt_id": value.attempt_id,
        "recipe": asdict(value.recipe) if value.recipe else None,
        "kind": value.kind,
        "crop": asdict(value.crop) if value.crop else None,
        "dlss": asdict(value.dlss) if value.dlss else None,
        "retouch": asdict(value.retouch) if value.retouch else None,
        "upscale": asdict(value.upscale) if value.upscale else None,
        "prompt": value.prompt,
        "settings": edit_settings_record(value.settings),
        "output_dimensions": list(value.output_dimensions) if value.output_dimensions else None,
        "status": value.status.value,
        "execution_id": value.execution_id,
        "compiled_workflow_sha256": value.compiled_workflow_sha256,
        "output_asset_id": value.output_asset_id,
        "error": value.error,
    }


def _attempt_from_dict(value: dict[str, Any]) -> Krea2EditAttempt:
    settings = value["settings"]
    return Krea2EditAttempt(
        attempt_id=value["attempt_id"],
        recipe=RecipeRef(**value["recipe"]) if value.get("recipe") else None,
        kind=value.get("kind", "generation"),
        crop=Krea2EditCrop(**value["crop"]) if value.get("crop") else None,
        dlss=DlssResult(**value["dlss"]) if value.get("dlss") else None,
        retouch=Krea2EditRetouch(**value["retouch"]) if value.get("retouch") is not None else None,
        upscale=(Krea2EditUpscale(**{**value["upscale"], "workflow": RecipeRef(**value["upscale"]["workflow"])})
                 if value.get("upscale") else None),
        prompt=value["prompt"],
        settings=_settings_from_dict(settings),
        output_dimensions=tuple(value["output_dimensions"]) if value.get("output_dimensions") else None,
        status=Krea2EditAttemptStatus(value["status"]),
        execution_id=value["execution_id"],
        compiled_workflow_sha256=value["compiled_workflow_sha256"],
        output_asset_id=value["output_asset_id"],
        error=value["error"],
    )


def _settings_from_dict(value: dict):
    engine = value.get("engine", "krea2")
    if engine == "firered":
        return FireRedEditSettings(model_name=value["model_name"], megapixels=value["megapixels"],
            seed=int(value["seed"]), mode=value["mode"], steps=value["steps"], cfg=value["cfg"])
    if engine != "krea2":
        raise ValueError("unsupported image-edit engine")
    return Krea2EditSettings(model_name=value["model_name"], aspect_ratio=Krea2AspectRatio(value["aspect_ratio"]),
        megapixels=value["megapixels"], seed=int(value["seed"]), ref_boost=value["ref_boost"],
        steps=value["steps"], loras=tuple(Krea2LoraSelection(**raw) for raw in value["loras"]))


def _lora_dict(value: Krea2LoraSelection) -> dict[str, object]:
    return {"name": value.name, "strength": value.strength}


def _source(value: object) -> Krea2EditSource:
    if not isinstance(value, Krea2EditSource):
        raise TypeError("source must be a Krea2EditSource")
    return value


def _safe(value: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("unsafe KREA2 edit identifier")


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise KeyError(path.parent.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("stored KREA2 edit source must be an object")
    return value


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
