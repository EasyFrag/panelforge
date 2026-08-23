"""Atomic local persistence for KREA2 edit backlog entries and attempts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from panelforge.domain.krea2_batch import Krea2LoraSelection, Krea2PromptLanguage
from panelforge.domain.krea2_edit import (
    Krea2EditAttempt,
    Krea2EditAttemptStatus,
    Krea2EditMetadata,
    Krea2EditPromptRevision,
    Krea2EditPromptStatus,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.recipes import RecipeRef


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
        return _from_dict(_read(self._entry(source_id) / "source.json"))

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
        "schema_version": 3,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_id": source.source_id,
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
    if schema_version not in {1, 2, 3}:
        raise ValueError("unsupported KREA2 edit source schema")
    recipe = value["recipe"]
    return Krea2EditSource(
        source_id=value["source_id"],
        recipe=RecipeRef(
            operation_id=recipe["operation_id"],
            recipe_id=recipe["recipe_id"],
            version=recipe["version"],
            workflow_sha256=recipe["workflow_sha256"],
        ),
        source_asset_id=value["source_asset_id"],
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
    )


def _attempt_dict(value: Krea2EditAttempt) -> dict[str, object]:
    return {
        "attempt_id": value.attempt_id,
        "prompt": value.prompt,
        "settings": {
            "model_name": value.settings.model_name,
            "aspect_ratio": value.settings.aspect_ratio.value,
            "megapixels": value.settings.megapixels,
            "seed": str(value.settings.seed),
            "ref_boost": value.settings.ref_boost,
            "steps": value.settings.steps,
            "loras": [_lora_dict(lora) for lora in value.settings.loras],
        },
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
        prompt=value["prompt"],
        settings=Krea2EditSettings(
            model_name=settings["model_name"],
            aspect_ratio=Krea2AspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"],
            seed=int(settings["seed"]),
            ref_boost=settings["ref_boost"],
            steps=settings["steps"],
            loras=tuple(Krea2LoraSelection(**raw) for raw in settings["loras"]),
        ),
        status=Krea2EditAttemptStatus(value["status"]),
        execution_id=value["execution_id"],
        compiled_workflow_sha256=value["compiled_workflow_sha256"],
        output_asset_id=value["output_asset_id"],
        error=value["error"],
    )


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
