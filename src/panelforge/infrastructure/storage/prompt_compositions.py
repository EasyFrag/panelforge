"""Strict local persistence for cookbook-driven prompt compositions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from panelforge.domain import (
    CompositionRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    PromptComposition,
    PromptLanguageVariant,
    RevisionOrigin,
    StageDocument,
)
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes

from .local import (
    StorageCorruptionError,
    _atomic_write,
    _contained_entry,
    _format_timestamp,
    _json_bytes,
    _read_json_object,
    _require_regular_file,
    _require_safe_id,
    _require_timestamp,
)


_SCHEMA_VERSION = 7
_COMPOSITION_KEYS = {
    "schema_version",
    "created_at",
    "updated_at",
    "source_session_id",
    "cookbook",
    "bindings",
    "reference_plan",
    "beat_sheet",
    "final_prompt",
}
_COOKBOOK_KEYS = {
    "cookbook_id",
    "version",
    "engine_contract_id",
    "engine_contract_version",
}
_BINDING_KEYS = {"slot_id", "reference_ids"}
_DOCUMENT_KEYS = {
    "stage",
    "revisions",
    "active_revision_id",
    "approved_revision_id",
}
_REVISION_KEYS_V1 = {
    "revision_id",
    "content",
    "origin",
    "source_ids",
    "parent_revision_id",
    "instruction",
}
_REVISION_KEYS_V2 = {*_REVISION_KEYS_V1, "compiler_context"}
_REVISION_KEYS_V6 = {*_REVISION_KEYS_V2, "llm_call_id", "prompt_recipe_revision"}
_VARIANT_KEYS_V7 = {
    "variant_id",
    "source_revision_id",
    "language",
    "content",
    "model_id",
    "llm_call_id",
}


class LocalPromptCompositionStore:
    """Store compositions below ``<workspace>/prompt_compositions``."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._compositions_root = (
            Path(workspace_root).resolve() / "prompt_compositions"
        )
        self._compositions_root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    def create(self, composition: PromptComposition) -> PromptComposition:
        _require_composition(composition)
        with self._lock:
            composition_dir = self._entry_dir(composition.source_session_id)
            composition_dir.mkdir(exist_ok=False)
            composition_path = composition_dir / "composition.json"
            try:
                timestamp = _format_timestamp(self._clock())
                _atomic_write(
                    composition_path,
                    _json_bytes(
                        _composition_to_dict(
                            composition,
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    ),
                )
            except BaseException:
                composition_path.unlink(missing_ok=True)
                composition_dir.rmdir()
                raise
        return composition

    def save(self, composition: PromptComposition) -> PromptComposition:
        _require_composition(composition)
        with self._lock:
            self._save_unlocked(composition)
        return composition

    def save_if_current(
        self,
        expected: PromptComposition,
        composition: PromptComposition,
    ) -> PromptComposition:
        _require_composition(expected)
        _require_composition(composition)
        if expected.source_session_id != composition.source_session_id:
            raise ValueError("composition identities must match")
        with self._lock:
            composition_path = (
                self._entry_dir(composition.source_session_id) / "composition.json"
            )
            stored, _, _ = self._read_file(
                composition_path,
                composition.source_session_id,
            )
            if stored != expected:
                raise ValueError("prompt composition changed concurrently")
            self._save_unlocked(composition)
        return composition

    def _save_unlocked(self, composition: PromptComposition) -> None:
        composition_path = (
            self._entry_dir(composition.source_session_id) / "composition.json"
        )
        stored, created_at, _ = self._read_file(
            composition_path,
            composition.source_session_id,
        )
        if stored.source_session_id != composition.source_session_id:
            raise StorageCorruptionError(
                "prompt composition source session identity mismatch"
            )
        _atomic_write(
            composition_path,
            _json_bytes(
                _composition_to_dict(
                    composition,
                    created_at=created_at,
                    updated_at=_format_timestamp(self._clock()),
                )
            ),
        )

    def get(self, source_session_id: str) -> PromptComposition:
        composition, _, _ = self._read_file(
            self._entry_dir(source_session_id) / "composition.json",
            source_session_id,
        )
        return composition

    def _read_file(
        self,
        path: Path,
        expected_source_session_id: str,
    ) -> tuple[PromptComposition, str, str]:
        _require_regular_file(path)
        data = _read_json_object(path)
        expected_keys = _COMPOSITION_KEYS | ({"preparation_intent"} if data.get("schema_version") in {3, 4, 5, 6, 7} else set())
        if data.get("schema_version") in {5, 6, 7}:
            expected_keys |= {"writer_model_id"}
        if data.get("schema_version") == 7:
            expected_keys |= {"prompt_variants"}
        if set(data) != expected_keys:
            raise StorageCorruptionError(
                "invalid prompt composition fields for "
                f"{expected_source_session_id!r}"
            )
        schema_version = data.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or schema_version not in {1, 2, 3, 4, 5, 6, _SCHEMA_VERSION}
        ):
            raise StorageCorruptionError(
                "unsupported prompt composition schema for "
                f"{expected_source_session_id!r}"
            )
        created_at = _require_timestamp(data.get("created_at"), "created_at")
        updated_at = _require_timestamp(data.get("updated_at"), "updated_at")
        try:
            composition = _composition_from_dict(
                data,
                schema_version=schema_version,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StorageCorruptionError(
                "invalid prompt composition metadata for "
                f"{expected_source_session_id!r}"
            ) from error
        if composition.source_session_id != expected_source_session_id:
            raise StorageCorruptionError(
                "prompt composition source session identity mismatch for "
                f"{expected_source_session_id!r}"
            )
        return composition, created_at, updated_at

    def _entry_dir(self, source_session_id: str) -> Path:
        _require_safe_id(source_session_id, "source session ID")
        return _contained_entry(self._compositions_root, source_session_id)


def _require_composition(value: object) -> PromptComposition:
    if not isinstance(value, PromptComposition):
        raise TypeError("composition must be a PromptComposition")
    _require_safe_id(value.source_session_id, "source session ID")
    return value


def _composition_to_dict(
    composition: PromptComposition,
    *,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": created_at,
        "updated_at": updated_at,
        "source_session_id": composition.source_session_id,
        "preparation_intent": intent_to_dict(composition.preparation_intent),
        "writer_model_id": composition.writer_model_id,
        "prompt_variants": [
            {
                "variant_id": variant.variant_id,
                "source_revision_id": variant.source_revision_id,
                "language": variant.language,
                "content": variant.content,
                "model_id": variant.model_id,
                "llm_call_id": variant.llm_call_id,
            }
            for variant in composition.prompt_variants
        ],
        "cookbook": {
            "cookbook_id": composition.cookbook.cookbook_id,
            "version": composition.cookbook.version,
            "engine_contract_id": composition.cookbook.engine_contract_id,
            "engine_contract_version": composition.cookbook.engine_contract_version,
        },
        "bindings": [
            {
                "slot_id": binding.slot_id,
                "reference_ids": list(binding.reference_ids),
            }
            for binding in composition.bindings
        ],
        "reference_plan": _document_to_dict(composition.reference_plan),
        "beat_sheet": _document_to_dict(composition.beat_sheet),
        "final_prompt": _document_to_dict(composition.final_prompt),
    }


def _document_to_dict(document: StageDocument) -> dict[str, object]:
    return {
        "stage": document.stage.value,
        "revisions": [
            {
                "revision_id": revision.revision_id,
                "content": revision.content,
                "origin": revision.origin.value,
                "source_ids": list(revision.source_ids),
                "parent_revision_id": revision.parent_revision_id,
                "instruction": revision.instruction,
                "compiler_context": revision.compiler_context,
                "llm_call_id": revision.llm_call_id,
                "prompt_recipe_revision": revision.prompt_recipe_revision,
            }
            for revision in document.revisions
        ],
        "active_revision_id": document.active_revision_id,
        "approved_revision_id": document.approved_revision_id,
    }


def _composition_from_dict(
    data: dict[str, object],
    *,
    schema_version: int,
) -> PromptComposition:
    raw_cookbook = _require_object(data["cookbook"], "cookbook")
    if set(raw_cookbook) != _COOKBOOK_KEYS:
        raise ValueError("cookbook contains invalid fields")

    raw_bindings = _require_list(data["bindings"], "bindings")
    bindings: list[CookbookBinding] = []
    for raw_binding in raw_bindings:
        binding = _require_object(raw_binding, "binding")
        if set(binding) != _BINDING_KEYS:
            raise ValueError("binding contains invalid fields")
        bindings.append(
            CookbookBinding(
                slot_id=binding["slot_id"],
                reference_ids=tuple(
                    _require_list(binding["reference_ids"], "reference_ids")
                ),
            )
        )

    raw_variants = _require_list(data.get("prompt_variants", []), "prompt_variants")
    variants: list[PromptLanguageVariant] = []
    for raw_variant in raw_variants:
        variant = _require_object(raw_variant, "prompt_variant")
        if set(variant) != _VARIANT_KEYS_V7:
            raise ValueError("prompt variant contains invalid fields")
        variants.append(PromptLanguageVariant(**variant))

    return PromptComposition(
        source_session_id=data["source_session_id"],
        preparation_intent=intent_from_dict(data.get("preparation_intent")),
        writer_model_id=data.get("writer_model_id"),
        cookbook=CookbookRef(
            cookbook_id=raw_cookbook["cookbook_id"],
            version=raw_cookbook["version"],
            engine_contract_id=raw_cookbook["engine_contract_id"],
            engine_contract_version=raw_cookbook["engine_contract_version"],
        ),
        bindings=tuple(bindings),
        reference_plan=_document_from_dict(
            data["reference_plan"],
            CompositionStage.REFERENCE_PLAN,
            schema_version=schema_version,
        ),
        beat_sheet=_document_from_dict(
            data["beat_sheet"],
            CompositionStage.BEAT_SHEET,
            schema_version=schema_version,
        ),
        final_prompt=_document_from_dict(
            data["final_prompt"],
            CompositionStage.FINAL_PROMPT,
            schema_version=schema_version,
        ),
        prompt_variants=tuple(variants),
    )


def intent_to_dict(intent: PreparationIntent | None) -> dict[str, object] | None:
    if intent is None:
        return None
    return {
        "source_text": intent.source_text,
        "creative_freedom": intent.creative_freedom,
        "creative_audacity": intent.creative_audacity,
        "creative_axes": (
            {name: getattr(intent.creative_axes, name) for name in ("scene_life", "camera", "extra_motion", "dialogue")}
            if intent.creative_axes is not None else None
        ),
    }


def intent_from_dict(value: object) -> PreparationIntent | None:
    if value is None:
        return None
    data = _require_object(value, "preparation_intent")
    if set(data) != {"source_text", "creative_freedom", "creative_audacity", "creative_axes"}:
        raise ValueError("invalid preparation_intent fields")
    axes = data["creative_axes"]
    return PreparationIntent(
        source_text=data["source_text"],
        creative_freedom=data["creative_freedom"],
        creative_audacity=data["creative_audacity"],
        creative_axes=CreativeFreedomAxes(**_require_object(axes, "creative_axes")) if axes is not None else None,
    )


def _document_from_dict(
    value: object,
    expected_stage: CompositionStage,
    *,
    schema_version: int,
) -> StageDocument:
    document = _require_object(value, expected_stage.value)
    if set(document) != _DOCUMENT_KEYS:
        raise ValueError(f"{expected_stage.value} contains invalid fields")
    stage = CompositionStage(document["stage"])
    if stage is not expected_stage:
        raise ValueError(f"expected {expected_stage.value}, got {stage.value}")
    raw_revisions = _require_list(document["revisions"], "revisions")
    revisions: list[CompositionRevision] = []
    revision_keys = (
        _REVISION_KEYS_V6 if schema_version >= 6 else (_REVISION_KEYS_V1 if schema_version == 1 else _REVISION_KEYS_V2)
    )
    for raw_revision in raw_revisions:
        revision = _require_object(raw_revision, "revision")
        if set(revision) != revision_keys:
            raise ValueError("revision contains invalid fields")
        revisions.append(
            CompositionRevision(
                revision_id=revision["revision_id"],
                llm_call_id=revision.get("llm_call_id"),
                prompt_recipe_revision=revision.get("prompt_recipe_revision"),
                content=revision["content"],
                origin=RevisionOrigin(revision["origin"]),
                source_ids=tuple(
                    _require_list(revision["source_ids"], "source_ids")
                ),
                parent_revision_id=revision["parent_revision_id"],
                instruction=revision["instruction"],
                compiler_context=(
                    revision["compiler_context"]
                    if schema_version >= 2
                    else None
                ),
            )
        )
    return StageDocument(
        stage=stage,
        revisions=tuple(revisions),
        active_revision_id=document["active_revision_id"],
        approved_revision_id=document["approved_revision_id"],
    )


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
