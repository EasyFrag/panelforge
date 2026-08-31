"""Durable local store for conversational KREA2 creation projects."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain.krea2_assisted import (
    Krea2AssistedAttempt,
    Krea2AssistedAttemptStatus,
    Krea2AssistedProject,
    Krea2AssistedRecipeDraft,
    Krea2AssistedTurn,
    Krea2AssistedTurnMode,
    Krea2AssistedTurnRole,
)
from panelforge.domain.krea2_batch import (
    Krea2BatchSettings,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalKrea2AssistedProjectStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "krea2_assisted"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(self, project: Krea2AssistedProject) -> Krea2AssistedProject:
        with self._lock:
            directory = self._directory(project.project_id)
            directory.mkdir(exist_ok=False)
            _atomic_write(directory / "project.json", _json_bytes(_serialize(project)))
        return project

    def save(self, project: Krea2AssistedProject) -> Krea2AssistedProject:
        with self._lock:
            path = self._directory(project.project_id) / "project.json"
            if not path.is_file():
                raise FileNotFoundError(project.project_id)
            _atomic_write(path, _json_bytes(_serialize(project)))
        return project

    def get(self, project_id: str) -> Krea2AssistedProject:
        with self._lock:
            path = self._directory(project_id) / "project.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(project_id)
            return _deserialize(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 30) -> list[Krea2AssistedProject]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        values: list[tuple[float, str, Krea2AssistedProject]] = []
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

    def save_compiled_workflow(
        self,
        project_id: str,
        attempt_id: str,
        workflow: dict[str, Any],
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


def _serialize(project: Krea2AssistedProject) -> dict[str, object]:
    return {
        "schema_version": 2,
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "project_id": project.project_id,
        "name": project.name,
        "intention": project.intention,
        "model_id": project.model_id,
        "revision_model_id": project.revision_model_id,
        "prompt_language": project.prompt_language.value,
        "reference_asset_id": project.reference_asset_id,
        "reference_filename": project.reference_filename,
        "turns": [
            {
                "turn_id": turn.turn_id,
                "mode": turn.mode.value,
                "role": turn.role.value,
                "content": turn.content,
                "guidance_asset_id": turn.guidance_asset_id,
                "guidance_filename": turn.guidance_filename,
                "questions": list(turn.questions),
                "prompt": turn.prompt,
                "recommendations": list(turn.recommendations),
                "model_id": turn.model_id,
            }
            for turn in project.turns
        ],
        "current_prompt": project.current_prompt,
        "attempts": [
            {
                "attempt_id": attempt.attempt_id,
                "index": attempt.index,
                "prompt": attempt.prompt,
                "settings": _settings(attempt.settings),
                "seed": str(attempt.seed),
                "status": attempt.status.value,
                "execution_id": attempt.execution_id,
                "compiled_workflow_sha256": attempt.compiled_workflow_sha256,
                "output_asset_id": attempt.output_asset_id,
                "error": attempt.error,
                "accepted": attempt.accepted,
            }
            for attempt in project.attempts
        ],
        "feedback_attempt_id": project.feedback_attempt_id,
        "accepted_attempt_id": project.accepted_attempt_id,
        "recipe_draft": _draft(project.recipe_draft),
        "published_recipe_id": project.published_recipe_id,
        "published_recipe_version": project.published_recipe_version,
        "export_path": project.export_path,
        "export_error": project.export_error,
        "warnings": list(project.warnings),
    }


def _deserialize(value: dict[str, Any]) -> Krea2AssistedProject:
    if value.get("schema_version") not in {1, 2}:
        raise ValueError("unsupported KREA2 assisted project schema")
    return Krea2AssistedProject(
        project_id=value["project_id"],
        name=value["name"],
        intention=value["intention"],
        model_id=value["model_id"],
        revision_model_id=value.get("revision_model_id"),
        prompt_language=Krea2PromptLanguage(value.get("prompt_language", "en")),
        reference_asset_id=value.get("reference_asset_id"),
        reference_filename=value.get("reference_filename"),
        turns=tuple(
            Krea2AssistedTurn(
                turn_id=item["turn_id"],
                mode=Krea2AssistedTurnMode(item["mode"]),
                role=Krea2AssistedTurnRole(item["role"]),
                content=item["content"],
                guidance_asset_id=item.get("guidance_asset_id"),
                guidance_filename=item.get("guidance_filename"),
                questions=tuple(item.get("questions", [])),
                prompt=item.get("prompt"),
                recommendations=tuple(item.get("recommendations", [])),
                model_id=item.get("model_id"),
            )
            for item in value.get("turns", [])
        ),
        current_prompt=value.get("current_prompt"),
        attempts=tuple(
            Krea2AssistedAttempt(
                attempt_id=item["attempt_id"],
                index=item["index"],
                prompt=item["prompt"],
                settings=_load_settings(item["settings"]),
                seed=int(item["seed"]),
                status=Krea2AssistedAttemptStatus(item["status"]),
                execution_id=item.get("execution_id"),
                compiled_workflow_sha256=item.get("compiled_workflow_sha256"),
                output_asset_id=item.get("output_asset_id"),
                error=item.get("error"),
                accepted=item.get("accepted", False),
            )
            for item in value.get("attempts", [])
        ),
        feedback_attempt_id=value.get("feedback_attempt_id"),
        accepted_attempt_id=value.get("accepted_attempt_id"),
        recipe_draft=_load_draft(value.get("recipe_draft")),
        published_recipe_id=value.get("published_recipe_id"),
        published_recipe_version=value.get("published_recipe_version"),
        export_path=value.get("export_path"),
        export_error=value.get("export_error"),
        warnings=tuple(value.get("warnings", [])),
    )


def _settings(settings: Krea2BatchSettings) -> dict[str, object]:
    return {
        "model_name": settings.model_name,
        "aspect_ratio": settings.aspect_ratio.value,
        "megapixels": settings.megapixels,
        "loras": [
            {"name": lora.name, "strength": lora.strength}
            for lora in settings.loras
        ],
    }


def _load_settings(value: dict[str, Any]) -> Krea2BatchSettings:
    return Krea2BatchSettings(
        model_name=value["model_name"],
        aspect_ratio=Krea2AspectRatio(value["aspect_ratio"]),
        megapixels=value["megapixels"],
        loras=tuple(
            Krea2LoraSelection(name=item["name"], strength=item["strength"])
            for item in value.get("loras", [])
        ),
    )


def _draft(value: Krea2AssistedRecipeDraft | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "recipe_id": value.recipe_id,
        "display_name": value.display_name,
        "description": value.description,
        "identity": value.identity,
        "invariants": list(value.invariants),
        "variables": list(value.variables),
        "risks": list(value.risks),
        "canonical_prompt": value.canonical_prompt,
        "prompt_language": value.prompt_language.value,
    }


def _load_draft(value: object) -> Krea2AssistedRecipeDraft | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("recipe_draft must be an object")
    return Krea2AssistedRecipeDraft(
        recipe_id=value["recipe_id"],
        display_name=value["display_name"],
        description=value["description"],
        identity=value["identity"],
        invariants=tuple(value["invariants"]),
        variables=tuple(value["variables"]),
        risks=tuple(value["risks"]),
        canonical_prompt=value["canonical_prompt"],
        prompt_language=Krea2PromptLanguage(value.get("prompt_language", "en")),
    )


def _safe(value: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("unsafe KREA2 assisted identifier")


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
