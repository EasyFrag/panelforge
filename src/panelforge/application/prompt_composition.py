"""Supervised, cookbook-driven prompt composition use cases."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
import json
import logging
import re
from typing import Protocol
from uuid import uuid4

from panelforge.domain import (
    CompositionRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    H3CameraDirective,
    PromptComposition,
    PromptLabSession,
    PromptSessionMode,
    ReferenceEvidencePolicy,
    RevisionOrigin,
)

from .prompt_lab import (
    AssetStore,
    CompletionRequest,
    ImageInput,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    MultimodalGateway,
    PromptSessionStore,
    StreamEventKind,
    StreamPhase,
    creative_freedom_policy,
    project_reference_evidence,
)
from .direct_i2v_prompt import (
    I2VA_FIELDS as DIRECT_I2VA_FIELDS,
    I2VA_FIXED_INSTRUCTION,
    apply_direct_i2v_timing,
    insert_camera_owned_direct_i2v_clauses,
    normalize_direct_i2v_camera_placeholders,
    rehydrate_camera_owned_direct_i2v_document,
    rehydrate_direct_i2v_editable_document,
)
from .direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan,
    canonical_direct_ref2v_action_plan_v2,
    direct_ref2v_action_plan_schema,
    direct_ref2v_action_plan_schema_v2,
    direct_ref2v_action_plan_warnings,
    direct_ref2v_action_plan_warnings_v2,
    direct_ref2v_camera_directives,
    direct_ref2v_camera_directives_v2,
    direct_ref2v_writer_plan,
    direct_ref2v_writer_plan_v2,
    direct_ref2v_writer_plan_v2_compact,
    direct_ref2v_writer_plan_v2_camera_owned,
    lint_direct_ref2v_action_plan,
    lint_direct_ref2v_action_plan_v2,
    parse_direct_ref2v_action_plan_v2,
)
from .direct_ref2v_multishot_plan import (
    canonical_direct_ref2v_multishot_plan,
    direct_ref2v_multishot_camera_directives,
    direct_ref2v_multishot_plan_schema,
    direct_ref2v_multishot_plan_warnings,
    direct_ref2v_multishot_writer_projection,
    lint_direct_ref2v_multishot_plan,
    parse_direct_ref2v_multishot_plan,
)
from .direct_ref2v_multishot_plan_v2 import (
    auto_resolve_direct_ref2v_multishot_risks_v2,
    canonical_direct_ref2v_multishot_plan_v2,
    direct_ref2v_multishot_camera_directives_v2,
    direct_ref2v_multishot_plan_schema_v2,
    direct_ref2v_multishot_plan_warnings_v2,
    direct_ref2v_multishot_writer_projection_v2,
    lint_direct_ref2v_multishot_plan_v2,
    parse_direct_ref2v_multishot_plan_v2,
)
from .direct_ref2v_multishot_prompt import (
    MULTISHOT_EDITABLE_CONTRACT,
    compile_direct_ref2v_multishot_document,
    decode_direct_ref2v_multishot_context,
    encode_direct_ref2v_multishot_context,
    is_direct_ref2v_multishot_context,
    lint_direct_ref2v_multishot_prompt,
    rehydrate_direct_ref2v_multishot_editable_document,
)
from .direct_ref2v_multishot_prompt_v2 import (
    compile_direct_ref2v_multishot_document_v2,
    decode_direct_ref2v_multishot_context_v2,
    direct_ref2v_multishot_editable_contract_v2,
    direct_ref2v_multishot_editable_fields_v2,
    encode_direct_ref2v_multishot_context_v2,
    is_direct_ref2v_multishot_context_v2,
    lint_direct_ref2v_multishot_prompt_v2,
    rehydrate_direct_ref2v_multishot_editable_document_v2,
    render_direct_ref2v_multishot_writer_document_v2,
)
from .direct_ref2v_prompt import (
    apply_direct_ref2v_timing_v2,
    decode_direct_ref2v_context,
    direct_reference_header,
    direct_reference_mapping,
    encode_direct_ref2v_context,
    is_direct_ref2v_context,
    insert_camera_owned_direct_ref2v_clauses,
    lint_direct_ref2v_prompt,
    normalize_direct_ref2v_camera_placeholders,
    rehydrate_direct_ref2v_editable_document,
    rehydrate_camera_owned_direct_ref2v_document,
    validate_direct_ref2v_labels,
)
from .minimax_h3_protocol import (
    H3IssueSeverity,
    H3ProtocolMode,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    compile_camera_draft,
    compile_camera_motion,
    compile_camera_placeholders,
    lint_h3_prompt,
    normalize_dialogue_language_tags,
    parse_camera_directives,
)
from .timed_camera_compiler import (
    TimedCameraContext,
    TimedCameraPlacement,
    decode_timed_camera_context,
    encode_timed_camera_context,
    is_timed_camera_context,
)
from .ref2v_action_plan import (
    canonical_ref2v_action_plan,
    canonical_ref2v_action_plan_v2,
    lint_ref2v_advisory_action_plan,
    lint_ref2v_bounded_action_plan,
    lint_ref2v_elastic_action_plan,
    lint_ref2v_action_plan,
    lint_ref2v_action_plan_v2,
    lint_ref2v_supervised_compiled_plan,
    lint_ref2v_supervised_compiled_plan_v2,
    lint_ref2v_supervised_canonical_compiled_plan,
    parse_ref2v_advisory_action_plan,
    parse_ref2v_supervised_compiled_plan,
    parse_ref2v_supervised_compiled_plan_v2,
    parse_ref2v_supervised_canonical_compiled_plan,
    ref2v_advisory_action_plan_warnings,
    ref2v_advisory_writer_plan,
    ref2v_bounded_action_plan_warnings,
    ref2v_bounded_writer_plan,
    ref2v_elastic_action_plan_warnings,
    ref2v_elastic_writer_plan,
    ref2v_action_plan_warnings_v2,
    ref2v_action_plan_schema,
    ref2v_action_plan_schema_v2,
    ref2v_action_plan_schema_v3,
    ref2v_repairable_action_plan_schema,
    ref2v_supervised_action_plan_schema,
    ref2v_supervised_action_plan_schema_v2,
    ref2v_supervised_canonical_action_plan_schema,
    ref2v_supervised_action_plan_warnings,
    ref2v_supervised_action_plan_warnings_v2,
    ref2v_supervised_canonical_action_plan_warnings,
    ref2v_supervised_canonical_camera_directives,
    ref2v_supervised_canonical_writer_plan,
    ref2v_supervised_writer_plan,
    ref2v_supervised_writer_plan_v2,
    retime_ref2v_advisory_action_plan,
    retime_ref2v_bounded_action_plan,
    retime_ref2v_action_plan_v2,
    retime_ref2v_repairable_action_plan,
    retime_ref2v_supervised_action_plan,
    retime_ref2v_supervised_action_plan_v2,
    retime_ref2v_supervised_canonical_action_plan,
)
from .revised_documents import RevisedDocumentContract


_LOGGER = logging.getLogger(__name__)
_FINAL_SECTIONS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_STAGE_SECTIONS = {
    CompositionStage.REFERENCE_PLAN: (
        "subject_definitions",
        "retention_policy",
    ),
    CompositionStage.BEAT_SHEET: (
        "production_settings",
        "continuity_rules",
        "beat_sheet",
    ),
    CompositionStage.FINAL_PROMPT: _FINAL_SECTIONS,
}
_RETENTION_MARKERS = {
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "weak_reference",
}
_I2VA_INSTRUCTION = I2VA_FIXED_INSTRUCTION
_I2VA_FIELDS = DIRECT_I2VA_FIELDS
_I2VA_CANONICAL_CONTRACT = "minimax.h3.i2va.canonical_v1"
_I2VA_DIRECT_CONTRACT = "minimax.h3.i2va.direct_supervised_h3_v1"
_I2VA_DIRECT_CAMERA_OWNED_CONTRACT = "minimax.h3.i2va.direct_supervised_h3_v2"
_I2VA_DIRECT_CONTRACTS = {
    _I2VA_DIRECT_CONTRACT,
    _I2VA_DIRECT_CAMERA_OWNED_CONTRACT,
}
_REF2V_COMPILED_CONTRACT = "minimax.h3.ref2v.single_shot_compiled"
_REF2V_PLANNED_CONTRACT = "minimax.h3.ref2v.single_shot_planned"
_REF2V_PLANNED_V2_CONTRACT = "minimax.h3.ref2v.single_shot_planned_v2"
_REF2V_ELASTIC_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v1"
_REF2V_BOUNDED_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v2"
_REF2V_ADVISORY_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v3"
_REF2V_RECOVERABLE_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v4"
_REF2V_SUPERVISED_CONTRACT = "minimax.h3.ref2v.single_shot_supervised_v1"
_REF2V_SUPERVISED_V2_CONTRACT = "minimax.h3.ref2v.single_shot_supervised_v2"
_REF2V_SUPERVISED_CANONICAL_CONTRACT = (
    "minimax.h3.ref2v.single_shot_supervised_compact_h3_v1"
)
_REF2V_DIRECT_V1_CONTRACT = "minimax.h3.ref2v.direct_supervised_h3_v1"
_REF2V_DIRECT_V2_CONTRACT = "minimax.h3.ref2v.direct_supervised_h3_v2"
_REF2V_DIRECT_V3_CONTRACT = "minimax.h3.ref2v.direct_supervised_h3_v3"
_REF2V_DIRECT_MULTISHOT_CONTRACT = (
    "minimax.h3.ref2v.direct_multishot_compact_h3_v1"
)
_REF2V_DIRECT_MULTISHOT_V2_CONTRACT = (
    "minimax.h3.ref2v.direct_multishot_compact_h3_v2"
)
SUPER_FAST_REF2V_COOKBOOK_ID = "minimax.h3.ref2v.direct.multishot.superfast"
SUPER_FAST_REF2V_COOKBOOK_VERSION = "0.2.0"
_SUPER_FAST_REF2V_LEGACY_VERSION = "0.1.0"
_SUPER_FAST_REF2V_LEGACY_EXECUTION_MODE = "super_fast_ref2v_v1"
_SUPER_FAST_REF2V_EXECUTION_MODE = "super_fast_ref2v_direct_v2"
_SUPER_FAST_REF2V_DIRECT_CONTRACT = "minimax.h3.ref2v.direct_multishot_prompt_h3_v1"
_REF2V_DIRECT_MULTISHOT_CONTRACTS = {
    _REF2V_DIRECT_MULTISHOT_CONTRACT,
    _REF2V_DIRECT_MULTISHOT_V2_CONTRACT,
}
_REF2V_DIRECT_CONTRACTS = {
    _REF2V_DIRECT_V1_CONTRACT,
    _REF2V_DIRECT_V2_CONTRACT,
    _REF2V_DIRECT_V3_CONTRACT,
}
_REF2V_DIRECT_PLACEHOLDER_CONTRACTS = {
    _REF2V_DIRECT_V1_CONTRACT,
    _REF2V_DIRECT_V2_CONTRACT,
}
_CAMERA_OWNED_MONO_CONTRACTS = {
    _I2VA_DIRECT_CAMERA_OWNED_CONTRACT,
    _REF2V_DIRECT_V3_CONTRACT,
}
_REF2V_ALL_DIRECT_CONTRACTS = {
    *_REF2V_DIRECT_CONTRACTS,
    *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
}
_DIRECT_MULTIMODAL_CONTRACTS = {
    *_REF2V_DIRECT_CONTRACTS,
    *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
    *_I2VA_DIRECT_CONTRACTS,
}
_DIRECT_PLAN_V2_CONTRACTS = {
    _REF2V_DIRECT_V2_CONTRACT,
    _REF2V_DIRECT_V3_CONTRACT,
    *_I2VA_DIRECT_CONTRACTS,
}
_DIRECT_ARBITRABLE_CONTRACTS = {
    *_DIRECT_PLAN_V2_CONTRACTS,
    *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
}
_REF2V_SUPERVISED_CONTRACTS = {
    _REF2V_SUPERVISED_CONTRACT,
    _REF2V_SUPERVISED_V2_CONTRACT,
    _REF2V_SUPERVISED_CANONICAL_CONTRACT,
}
_H3_PROTOCOL_CONTRACTS = {
    _SUPER_FAST_REF2V_DIRECT_CONTRACT,
    _I2VA_CANONICAL_CONTRACT,
    *_I2VA_DIRECT_CONTRACTS,
    _REF2V_SUPERVISED_CANONICAL_CONTRACT,
    *_REF2V_DIRECT_CONTRACTS,
    *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
}
_REF2V_ADVISORY_CONTRACTS = {
    _REF2V_ADVISORY_CONTRACT,
    _REF2V_RECOVERABLE_CONTRACT,
}
_REF2V_SOFT_FINAL_CONTRACTS = {
    *_REF2V_ADVISORY_CONTRACTS,
    *_REF2V_SUPERVISED_CONTRACTS,
}
_REF2V_PLANNED_CONTRACTS = {
    _REF2V_PLANNED_CONTRACT,
    _REF2V_PLANNED_V2_CONTRACT,
    _REF2V_ELASTIC_CONTRACT,
    _REF2V_BOUNDED_CONTRACT,
    _REF2V_ADVISORY_CONTRACT,
    _REF2V_RECOVERABLE_CONTRACT,
    *_REF2V_SUPERVISED_CONTRACTS,
    *_REF2V_DIRECT_CONTRACTS,
    *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
}
_PLANNED_CONTRACTS = {
    *_REF2V_PLANNED_CONTRACTS,
    *_I2VA_DIRECT_CONTRACTS,
}
_REF2V_EDITABLE_FIELDS = (
    "scene_setup",
    "shot_1",
    "overall_soundscape",
    "non_diegetic_music",
)
_REF2V_COMPILED_HEADER = (
    "<Picture 1>: the exact fully preserved starting frame at 0.00 seconds, "
    "containing the subject in the dressed starting state and defining pose, "
    "framing, room, lighting, and visible composition.\n"
    "Use <Picture 2> only as a body and appearance reference for the same subject "
    "shown in <Picture 1>; do not use it as a frame, pose, background, composition, "
    "or target state."
)
_REF2V_APPEARANCE_ONLY_COMPILED_HEADER = (
    "<Picture 1>: the exact fully preserved starting frame at 0.00 seconds, "
    "containing the subject in the dressed starting state and defining pose, "
    "framing, room, lighting, and visible composition.\n"
    "Use <Picture 2> only for the identity, face, skin, body proportions, and stable "
    "physical appearance of the same adult subject shown in <Picture 1>; do not use "
    "it as a frame, pose, "
    "hand placement, expression, clothing state, lens, camera angle, lighting, "
    "background, composition, or target staging."
)
_REF2V_EDITABLE_CONTRACT = RevisedDocumentContract(
    "compiled Ref2V editable document",
    tuple(f"{field}:" for field in _REF2V_EDITABLE_FIELDS),
)
_I2VA_CANONICAL_EDITABLE_CONTRACT = RevisedDocumentContract(
    "canonical I2VA editable document",
    (
        "camera_directives:",
        *(f"{field}:" for field in _I2VA_FIELDS),
    ),
)
_I2VA_DIRECT_EDITABLE_CONTRACT = RevisedDocumentContract(
    "direct I2VA editable document",
    tuple(f"{field}:" for field in _I2VA_FIELDS),
)
_H3_CAMERA_CONTEXT_MARKER = "__PANELFORGE_H3_CAMERA_CONTEXT__:"
_REF2VA_CONTRACTS = {
    "minimax.h3.ref2va",
    "minimax.h3.ref2va.single_shot",
}


class CookbookSlotPort(Protocol):
    slot_id: str
    label: str
    description: str
    evidence_policy: ReferenceEvidencePolicy
    subject_label: str | None
    accepted_uses: tuple[str, ...]
    required_uses: tuple[str, ...]
    required_shots: tuple[int, ...]
    minimum_references: int
    maximum_references: int


class PromptCookbookPort(Protocol):
    schema_version: int
    reference: CookbookRef
    display_name: str
    description: str
    target_mode: str
    output_contract: str
    preset: str
    stages: tuple[str, ...]
    require_distinct_references: bool
    invalid_camera_target_policy: str
    writer_projection: str
    visibility: str
    execution_mode: str
    sources: tuple[str, ...]
    slots: tuple[CookbookSlotPort, ...]
    reference_plan_system_prompt: str | None
    reference_plan_user_prompt: str | None
    beat_sheet_system_prompt: str | None
    beat_sheet_user_prompt: str | None
    beat_sheet_reconcile_system_prompt: str | None
    beat_sheet_reconcile_user_prompt: str | None
    final_prompt_system_prompt: str
    final_prompt_user_prompt: str
    revision_system_prompt: str
    revision_user_prompt: str


class PromptCookbookCatalog(Protocol):
    def list(self) -> tuple[PromptCookbookPort, ...]: ...

    def get(self, cookbook_id: str, version: str) -> PromptCookbookPort: ...


class PromptCompositionStore(Protocol):
    def create(self, composition: PromptComposition) -> PromptComposition: ...

    def save(self, composition: PromptComposition) -> PromptComposition: ...

    def save_if_current(
        self,
        expected: PromptComposition,
        composition: PromptComposition,
    ) -> PromptComposition: ...

    def get(self, source_session_id: str) -> PromptComposition: ...


@dataclass(frozen=True, slots=True)
class CompositionStageStatus:
    stage: CompositionStage
    stale: bool
    complete: bool
    blocked_reason: str | None
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompositionStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    composition: PromptComposition | None = None
    finish_reason: str | None = None
    max_tokens: int | None = None
    document_stage: CompositionStage | None = None


def composition_picture_mapping(
    composition: PromptComposition,
) -> tuple[tuple[str, int], ...]:
    """Return the stable upload order and local <Picture N> number."""
    seen: set[str] = set()
    mapping: list[tuple[str, int]] = []
    for binding in composition.bindings:
        for reference_id in binding.reference_ids:
            if reference_id not in seen:
                seen.add(reference_id)
                mapping.append((reference_id, len(mapping) + 1))
    return tuple(mapping)


class PromptCompositionService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        cookbooks: PromptCookbookCatalog,
        sessions: PromptSessionStore,
        compositions: PromptCompositionStore,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        assets: AssetStore | None = None,
    ) -> None:
        self.gateway = gateway
        self.cookbooks = cookbooks
        self.sessions = sessions
        self.compositions = compositions
        self.application_outcomes = application_outcomes
        self.assets = assets

    def list_cookbooks(
        self,
        *,
        include_internal: bool = False,
    ) -> tuple[PromptCookbookPort, ...]:
        cookbooks = self.cookbooks.list()
        if include_internal:
            return cookbooks
        return tuple(
            cookbook
            for cookbook in cookbooks
            if getattr(cookbook, "visibility", "public") == "public"
        )

    def get(self, source_session_id: str) -> PromptComposition:
        return self.compositions.get(source_session_id)

    def configure(
        self,
        source_session_id: str,
        cookbook_id: str,
        cookbook_version: str,
        bindings: tuple[CookbookBinding, ...],
    ) -> PromptComposition:
        session = self.sessions.get(source_session_id)
        _approved_brief(session)
        cookbook = self.cookbooks.get(cookbook_id, cookbook_version)
        _validate_bindings(session, cookbook, bindings)
        by_slot = {binding.slot_id: binding for binding in bindings}
        bindings = tuple(by_slot[slot.slot_id] for slot in cookbook.slots)
        try:
            existing = self.compositions.get(source_session_id)
        except (KeyError, FileNotFoundError):
            return self.compositions.create(
                PromptComposition(
                    source_session_id=source_session_id,
                    cookbook=cookbook.reference,
                    bindings=bindings,
                )
            )
        if existing.cookbook != cookbook.reference:
            raise ValueError(
                "this session already uses another cookbook; create a new session to preserve its history"
            )
        return self.compositions.save_if_current(
            existing,
            existing.with_bindings(bindings),
        )

    def status(
        self,
        composition: PromptComposition,
    ) -> tuple[CompositionStageStatus, ...]:
        session = self.sessions.get(composition.source_session_id)
        statuses: list[CompositionStageStatus] = []
        for stage in CompositionStage:
            document = composition.document(stage)
            blocked_reason: str | None = None
            cookbook: PromptCookbookPort | None = None
            try:
                cookbook = self._validated_cookbook(session, composition)
                expected = self._expected_sources(session, composition, stage)
            except ValueError as error:
                expected = None
                blocked_reason = str(error)
            stale = document.active_revision is not None and (
                expected is None or document.is_stale(expected)
            )
            complete = expected is not None and document.is_complete(expected)
            validation_errors: tuple[str, ...] = ()
            if document.active_revision is not None and cookbook is not None:
                validation_errors = lint_cookbook_document(
                    cookbook,
                    stage,
                    document.active_revision.content,
                )
            statuses.append(
                CompositionStageStatus(
                    stage=stage,
                    stale=stale,
                    complete=complete,
                    blocked_reason=blocked_reason,
                    validation_errors=validation_errors,
                    validation_warnings=(
                        composition_document_warnings(
                            cookbook,
                            stage,
                            document.active_revision.content,
                            composition=composition,
                        )
                        if document.active_revision is not None and cookbook is not None
                        else ()
                    ),
                )
            )
        return tuple(statuses)

    def generate(
        self,
        source_session_id: str,
        stage: CompositionStage,
    ) -> PromptComposition:
        composition = self.compositions.get(source_session_id)
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if getattr(cookbook, "execution_mode", "supervised") != "supervised":
            raise ValueError(
                "this internal cookbook must be run with generate_super_fast"
            )
        if (
            cookbook.output_contract in _PLANNED_CONTRACTS
            and cookbook.output_contract not in _REF2V_SUPERVISED_CONTRACTS
            and cookbook.output_contract not in _DIRECT_MULTIMODAL_CONTRACTS
            and stage is CompositionStage.FINAL_PROMPT
        ):
            self._generate_stage(source_session_id, CompositionStage.BEAT_SHEET)
            self.approve(source_session_id, CompositionStage.BEAT_SHEET)
        return self._generate_stage(source_session_id, stage)

    def _generate_stage(
        self,
        source_session_id: str,
        stage: CompositionStage,
    ) -> PromptComposition:
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=None,
        )
        result = self.gateway.complete(request)
        content, compiler_context = _compile_content_with_context(
            cookbook,
            stage,
            prefix,
            result.content,
        )
        return self._persist_if_current(
            session,
            composition,
            stage,
            expected,
            content,
            RevisionOrigin.MODEL,
            compiler_context=compiler_context,
        )

    def stream_generate(
        self,
        source_session_id: str,
        stage: CompositionStage,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[CompositionStreamEvent]:
        composition = self.compositions.get(source_session_id)
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if getattr(cookbook, "execution_mode", "supervised") != "supervised":
            raise ValueError(
                "this internal cookbook must be run with stream_generate_super_fast"
            )
        if (
            cookbook.output_contract in _PLANNED_CONTRACTS
            and cookbook.output_contract not in _REF2V_SUPERVISED_CONTRACTS
            and cookbook.output_contract not in _DIRECT_MULTIMODAL_CONTRACTS
            and stage is CompositionStage.FINAL_PROMPT
        ):
            plan_request = self._request(
                source_session_id,
                CompositionStage.BEAT_SHEET,
                instruction=None,
                include_reasoning=include_reasoning,
            )
            return self._stream_planned_final(source_session_id, plan_request)
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=None,
            include_reasoning=include_reasoning,
        )
        return self._stream(
            request,
            cookbook,
            session,
            composition,
            stage,
            expected,
            prefix,
            RevisionOrigin.MODEL,
        )

    def generate_super_fast(self, source_session_id: str) -> PromptComposition:
        """Produce and approve a final H3 prompt with exactly one LLM call."""

        if self._is_legacy_super_fast(source_session_id):
            return self._generate_legacy_super_fast(source_session_id)

        request_values = self._super_fast_direct_request(source_session_id)
        result = self.gateway.complete(request_values[4])
        if result.finish_reason == "length":
            raise ValueError(
                "model response was truncated because its token budget was exhausted"
            )
        try:
            composition = self._complete_super_fast_direct(
                *request_values[:4],
                result.content,
            )
        except Exception as error:
            self._report_application_outcome(
                result.call_id,
                LlmCallApplicationOutcome.REJECTED,
                error,
            )
            raise
        self._report_application_outcome(
            result.call_id,
            LlmCallApplicationOutcome.ACCEPTED,
        )
        return composition

    def _generate_legacy_super_fast(
        self,
        source_session_id: str,
    ) -> PromptComposition:
        """Keep persisted 0.1.0 compositions executable without changing them."""

        plan_request = self._super_fast_plan_request(source_session_id)
        result = self.gateway.complete(plan_request[4])
        if result.finish_reason == "length":
            raise ValueError(
                "model response was truncated because its token budget was exhausted"
            )
        try:
            composition = self._complete_super_fast_plan(
                *plan_request[:4],
                result.content,
            )
        except Exception as error:
            self._report_application_outcome(
                result.call_id,
                LlmCallApplicationOutcome.REJECTED,
                error,
            )
            raise
        self._report_application_outcome(
            result.call_id,
            LlmCallApplicationOutcome.ACCEPTED,
        )
        return composition

    def stream_generate_super_fast(
        self,
        source_session_id: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[CompositionStreamEvent]:
        """Stream the sole direct H3 writer call and persist its approved prompt."""

        if self._is_legacy_super_fast(source_session_id):
            yield from self._stream_legacy_super_fast(
                source_session_id,
                include_reasoning=include_reasoning,
            )
            return

        request_values = self._super_fast_direct_request(
            source_session_id,
            include_reasoning=include_reasoning,
        )
        session, composition, cookbook, expected, request = request_values
        terminal = False
        for event in self.gateway.stream(request):
            if event.kind is StreamEventKind.COMPLETED:
                if event.result is None:
                    raise ValueError("stream completed without a result")
                try:
                    completed = self._complete_super_fast_direct(
                        session,
                        composition,
                        cookbook,
                        expected,
                        event.result.content,
                    )
                except Exception as error:
                    self._report_application_outcome(
                        event.result.call_id,
                        LlmCallApplicationOutcome.REJECTED,
                        error,
                    )
                    raise
                self._report_application_outcome(
                    event.result.call_id,
                    LlmCallApplicationOutcome.ACCEPTED,
                )
                terminal = True
                final = completed.final_prompt.active_revision
                if final is None:  # Defensive: guaranteed by the direct path.
                    raise ValueError("super-fast final prompt was not persisted")
                yield CompositionStreamEvent(
                    kind=StreamEventKind.COMPLETED,
                    phase=StreamPhase.COMPLETED,
                    text=final.content,
                    progress=1.0,
                    composition=completed,
                    finish_reason=event.result.finish_reason,
                    max_tokens=request.max_tokens,
                    document_stage=CompositionStage.FINAL_PROMPT,
                )
            elif event.kind is StreamEventKind.TRUNCATED:
                terminal = True
                yield CompositionStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=event.result.content if event.result else event.text,
                    finish_reason=(event.result.finish_reason if event.result else None),
                    max_tokens=request.max_tokens,
                    document_stage=CompositionStage.FINAL_PROMPT,
                )
            else:
                yield CompositionStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                    document_stage=CompositionStage.FINAL_PROMPT,
                )
        if not terminal:
            raise ValueError("model stream ended before completion")

    def _stream_legacy_super_fast(
        self,
        source_session_id: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[CompositionStreamEvent]:
        """Run the immutable 0.1.0 Plan-first implementation for old sessions."""

        plan_request = self._super_fast_plan_request(
            source_session_id,
            include_reasoning=include_reasoning,
        )
        session, composition, cookbook, expected, request, _ = plan_request
        terminal = False
        for event in self.gateway.stream(request):
            if event.kind is StreamEventKind.COMPLETED:
                if event.result is None:
                    raise ValueError("stream completed without a result")
                try:
                    completed = self._complete_super_fast_plan(
                        session,
                        composition,
                        cookbook,
                        expected,
                        event.result.content,
                    )
                except Exception as error:
                    self._report_application_outcome(
                        event.result.call_id,
                        LlmCallApplicationOutcome.REJECTED,
                        error,
                    )
                    raise
                self._report_application_outcome(
                    event.result.call_id,
                    LlmCallApplicationOutcome.ACCEPTED,
                )
                yield CompositionStreamEvent(
                    kind=StreamEventKind.STATUS,
                    phase=StreamPhase.PREPARING,
                    text="Plan arbitré et validé. Compilation déterministe du prompt H3…",
                    composition=completed,
                    document_stage=CompositionStage.FINAL_PROMPT,
                )
                terminal = True
                final = completed.final_prompt.active_revision
                if final is None:  # Defensive: guaranteed by the compiler path.
                    raise ValueError("super-fast final prompt was not persisted")
                yield CompositionStreamEvent(
                    kind=StreamEventKind.COMPLETED,
                    phase=StreamPhase.COMPLETED,
                    text=final.content,
                    progress=1.0,
                    composition=completed,
                    finish_reason=event.result.finish_reason,
                    max_tokens=request.max_tokens,
                    document_stage=CompositionStage.FINAL_PROMPT,
                )
            elif event.kind is StreamEventKind.TRUNCATED:
                terminal = True
                yield CompositionStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=event.result.content if event.result else event.text,
                    finish_reason=(event.result.finish_reason if event.result else None),
                    max_tokens=request.max_tokens,
                    document_stage=CompositionStage.BEAT_SHEET,
                )
            else:
                yield CompositionStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                    document_stage=CompositionStage.BEAT_SHEET,
                )
        if not terminal:
            raise ValueError("model stream ended before completion")

    def _is_legacy_super_fast(self, source_session_id: str) -> bool:
        composition = self.compositions.get(source_session_id)
        return (
            composition.cookbook.cookbook_id == SUPER_FAST_REF2V_COOKBOOK_ID
            and composition.cookbook.version == _SUPER_FAST_REF2V_LEGACY_VERSION
        )

    def _super_fast_direct_request(
        self,
        source_session_id: str,
        *,
        include_reasoning: bool = False,
    ):
        session = self.sessions.get(source_session_id)
        composition = self.compositions.get(source_session_id)
        cookbook = self._validated_cookbook(session, composition)
        if (
            cookbook.reference.cookbook_id != SUPER_FAST_REF2V_COOKBOOK_ID
            or cookbook.reference.version != SUPER_FAST_REF2V_COOKBOOK_VERSION
            or cookbook.output_contract != _SUPER_FAST_REF2V_DIRECT_CONTRACT
            or getattr(cookbook, "visibility", None) != "internal"
            or getattr(cookbook, "execution_mode", None)
            != _SUPER_FAST_REF2V_EXECUTION_MODE
        ):
            raise ValueError(
                "super-fast direct generation requires the internal Ref2V 0.2.0 cookbook"
            )
        expected = self._expected_sources(
            session,
            composition,
            CompositionStage.FINAL_PROMPT,
        )
        brief = _approved_brief(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=_required_prompt(
                cookbook.final_prompt_system_prompt,
                "final_prompt_system",
            ),
            user_prompt=_render(
                _required_prompt(
                    cookbook.final_prompt_user_prompt,
                    "final_prompt_user",
                ),
                BRIEF=brief.content,
                REFERENCES=direct_reference_mapping(
                    session,
                    composition_picture_mapping(composition),
                ),
                CREATIVE_FREEDOM=str(brief.creative_freedom),
                CREATIVE_POLICY=creative_freedom_policy(
                    brief.creative_freedom
                ),
            ),
            images=self._direct_reference_images(session, composition),
            temperature=0.2,
            max_tokens=32768,
            operation_id="ref2v.super_fast.prompt_direct.generate",
            include_reasoning=include_reasoning,
        )
        return session, composition, cookbook, expected, request

    def _complete_super_fast_direct(
        self,
        initial_session: PromptLabSession,
        initial_composition: PromptComposition,
        cookbook: PromptCookbookPort,
        expected: tuple[str, ...],
        result_content: str,
    ) -> PromptComposition:
        current_session = self.sessions.get(initial_session.session_id)
        current = self.compositions.get(initial_session.session_id)
        if current.cookbook != initial_composition.cookbook:
            raise ValueError("cookbook changed while the model was generating")
        if current.final_prompt.active_revision_id != initial_composition.final_prompt.active_revision_id:
            raise ValueError("the final prompt changed while the model was generating")
        if self._expected_sources(
            current_session,
            current,
            CompositionStage.FINAL_PROMPT,
        ) != expected:
            raise ValueError("an upstream input changed while the model was generating")
        content = _compile_super_fast_ref2v_prompt(
            current_session,
            current,
            cookbook,
            result_content,
        )
        completed = self._persist_if_current(
            current_session,
            current,
            CompositionStage.FINAL_PROMPT,
            expected,
            content,
            RevisionOrigin.MODEL,
        )
        generated_document = completed.final_prompt
        return self.compositions.save_if_current(
            completed,
            completed.update_document(generated_document.approve(expected)),
        )

    def _super_fast_plan_request(
        self,
        source_session_id: str,
        *,
        include_reasoning: bool = False,
    ):
        request_values = self._request(
            source_session_id,
            CompositionStage.BEAT_SHEET,
            instruction=None,
            include_reasoning=include_reasoning,
        )
        cookbook = request_values[2]
        if (
            cookbook.reference.cookbook_id != SUPER_FAST_REF2V_COOKBOOK_ID
            or cookbook.reference.version != _SUPER_FAST_REF2V_LEGACY_VERSION
            or getattr(cookbook, "visibility", None) != "internal"
            or getattr(cookbook, "execution_mode", None)
            != _SUPER_FAST_REF2V_LEGACY_EXECUTION_MODE
        ):
            raise ValueError(
                "super-fast generation requires the internal Ref2V V1 cookbook"
            )
        return (
            *request_values[:4],
            replace(
                request_values[4],
                operation_id="ref2v.super_fast.generate",
            ),
            request_values[5],
        )

    def _complete_super_fast_plan(
        self,
        initial_session: PromptLabSession,
        initial_composition: PromptComposition,
        cookbook: PromptCookbookPort,
        expected: tuple[str, ...],
        result_content: str,
    ) -> PromptComposition:
        plan_content, _ = _compile_content_with_context(
            cookbook,
            CompositionStage.BEAT_SHEET,
            "",
            result_content,
        )
        brief = _approved_brief(initial_session)
        plan_content = auto_resolve_direct_ref2v_multishot_risks_v2(
            plan_content,
            brief.creative_freedom,
        )
        _raise_lint(cookbook, CompositionStage.BEAT_SHEET, plan_content)
        generated_plan = self._persist_if_current(
            initial_session,
            initial_composition,
            CompositionStage.BEAT_SHEET,
            expected,
            plan_content,
            RevisionOrigin.MODEL,
        )
        approved_plan_document = generated_plan.beat_sheet
        self.compositions.save_if_current(
            generated_plan,
            generated_plan.update_document(
                approved_plan_document.approve(expected)
            ),
        )

        current_session = self.sessions.get(initial_session.session_id)
        current = self.compositions.get(initial_session.session_id)
        current_cookbook = self._validated_cookbook(current_session, current)
        final_expected = self._expected_sources(
            current_session,
            current,
            CompositionStage.FINAL_PROMPT,
        )
        approved_plan = _approved_stage(
            current,
            CompositionStage.BEAT_SHEET,
            self._expected_sources(
                current_session,
                current,
                CompositionStage.BEAT_SHEET,
            ),
        )
        compiler_context = _direct_ref2v_multishot_compiler_context_for(
            current_session,
            current,
            current_cookbook,
        )
        writer_content = render_direct_ref2v_multishot_writer_document_v2(
            approved_plan.content
        )
        final_content, final_context = _compile_content_with_context(
            current_cookbook,
            CompositionStage.FINAL_PROMPT,
            compiler_context,
            writer_content,
        )
        completed = self._persist_if_current(
            current_session,
            current,
            CompositionStage.FINAL_PROMPT,
            final_expected,
            final_content,
            RevisionOrigin.MODEL,
            compiler_context=final_context,
        )
        generated_final_document = completed.final_prompt
        return self.compositions.save_if_current(
            completed,
            completed.update_document(
                generated_final_document.approve(final_expected)
            ),
        )

    def _stream_planned_final(
        self,
        source_session_id: str,
        plan_request: tuple[
            PromptLabSession,
            PromptComposition,
            PromptCookbookPort,
            tuple[str, ...],
            CompletionRequest,
            str,
        ],
    ) -> Iterator[CompositionStreamEvent]:
        session, composition, cookbook, expected, request, prefix = plan_request
        yield CompositionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.PREPARING,
            text="Planification de la chorégraphie…",
        )
        plan_completed = False
        for event in self._stream(
            request,
            cookbook,
            session,
            composition,
            CompositionStage.BEAT_SHEET,
            expected,
            prefix,
            RevisionOrigin.MODEL,
        ):
            if event.kind is StreamEventKind.COMPLETED:
                plan_completed = True
            elif event.kind is StreamEventKind.TRUNCATED:
                yield CompositionStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=event.text,
                    finish_reason=event.finish_reason,
                    max_tokens=event.max_tokens,
                    document_stage=CompositionStage.BEAT_SHEET,
                )
                return
            elif event.kind in {
                StreamEventKind.DELTA,
                StreamEventKind.REASONING,
            }:
                yield CompositionStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                    document_stage=CompositionStage.BEAT_SHEET,
                )
            else:
                yield event
        if not plan_completed:
            raise ValueError("action-plan stream ended before completion")
        approved_plan = self.approve(
            source_session_id,
            CompositionStage.BEAT_SHEET,
        )
        yield CompositionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.PREPARING,
            text="Plan validé. Rédaction du prompt H3…",
            composition=approved_plan,
            document_stage=CompositionStage.BEAT_SHEET,
        )
        final_request = self._request(
            source_session_id,
            CompositionStage.FINAL_PROMPT,
            instruction=None,
            include_reasoning=request.include_reasoning,
        )
        yield from self._stream(
            final_request[4],
            final_request[2],
            final_request[0],
            final_request[1],
            CompositionStage.FINAL_PROMPT,
            final_request[3],
            final_request[5],
            RevisionOrigin.MODEL,
        )

    def edit(
        self,
        source_session_id: str,
        stage: CompositionStage,
        content: str,
    ) -> PromptComposition:
        session = self.sessions.get(source_session_id)
        composition = self.compositions.get(source_session_id)
        cookbook = self._validated_cookbook(session, composition)
        if stage.value not in cookbook.stages:
            raise ValueError(f"stage {stage.value} is not active for this cookbook")
        expected = self._expected_sources(session, composition, stage)
        if (
            stage is CompositionStage.FINAL_PROMPT
            and CompositionStage.REFERENCE_PLAN.value in cookbook.stages
        ):
            reference_plan = _approved_stage(
                composition,
                CompositionStage.REFERENCE_PLAN,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.REFERENCE_PLAN,
                ),
            )
            prefix, _ = _split_final_prompt(_strip_fence(content))
            if prefix.strip() != _reference_prefix(reference_plan.content).strip():
                raise ValueError(
                    "subject_definitions is locked by the approved reference plan"
                )
        _raise_lint(cookbook, stage, content)
        active = composition.document(stage).active_revision
        return self._append_revision(
            composition,
            stage,
            expected,
            _strip_fence(content),
            RevisionOrigin.MANUAL,
            compiler_context=(active.compiler_context if active is not None else None),
        )

    def revise(
        self,
        source_session_id: str,
        stage: CompositionStage,
        instruction: str,
    ) -> PromptComposition:
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=instruction,
        )
        result = self.gateway.complete(request)
        revised = result.content
        if cookbook.output_contract != _SUPER_FAST_REF2V_DIRECT_CONTRACT:
            revised = _revision_document_contract(
                cookbook,
                stage,
                compiler_context=prefix or None,
            ).extract(result.content)
        content, compiler_context = _compile_content_with_context(
            cookbook,
            stage,
            prefix,
            revised,
        )
        return self._persist_if_current(
            session,
            composition,
            stage,
            expected,
            content,
            RevisionOrigin.REWRITE,
            instruction,
            compiler_context=compiler_context,
        )

    def stream_revise(
        self,
        source_session_id: str,
        stage: CompositionStage,
        instruction: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[CompositionStreamEvent]:
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=instruction,
            include_reasoning=include_reasoning,
        )
        return self._stream(
            request,
            cookbook,
            session,
            composition,
            stage,
            expected,
            prefix,
            RevisionOrigin.REWRITE,
            instruction,
        )

    def stream_reconcile_action_plan(
        self,
        source_session_id: str,
        decisions: Mapping[str, str],
        instruction: str | None = None,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[CompositionStreamEvent]:
        """Rewrite a supervised plan so human arbitration changes its real timeline."""
        session = self.sessions.get(source_session_id)
        composition = self.compositions.get(source_session_id)
        cookbook = self._validated_cookbook(session, composition)
        if cookbook.output_contract in _DIRECT_MULTIMODAL_CONTRACTS:
            return self._stream_reconcile_direct_action_plan(
                session,
                composition,
                cookbook,
                decisions,
                instruction,
                include_reasoning=include_reasoning,
            )
        if cookbook.output_contract not in _REF2V_SUPERVISED_CONTRACTS:
            raise ValueError(
                "action-plan arbitration is only available for supervised Ref2V"
            )
        system_template = _required_prompt(
            cookbook.beat_sheet_reconcile_system_prompt,
            "beat_sheet_reconcile_system",
        )
        user_template = _required_prompt(
            cookbook.beat_sheet_reconcile_user_prompt,
            "beat_sheet_reconcile_user",
        )
        expected = self._expected_sources(
            session,
            composition,
            CompositionStage.BEAT_SHEET,
        )
        current = composition.beat_sheet.active_revision
        if current is None:
            raise ValueError("generate the action plan before arbitrating it")
        if current.source_ids != expected:
            raise ValueError("the current action plan is stale; regenerate it first")
        parse_compiled_plan = (
            parse_ref2v_supervised_canonical_compiled_plan
            if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
            else parse_ref2v_supervised_compiled_plan_v2
            if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
            else parse_ref2v_supervised_compiled_plan
        )
        current_plan = parse_compiled_plan(current.content)
        normalized_decisions = _normalize_arbitration_decisions(
            decisions,
            {concern.concern_id for concern in current_plan.continuity_concerns},
        )
        if instruction is not None and not isinstance(instruction, str):
            raise TypeError("the global arbitration instruction must be text")
        normalized_instruction = (
            instruction.strip() if instruction and instruction.strip() else None
        )
        if normalized_instruction is not None and len(normalized_instruction) > 4000:
            raise ValueError("the global arbitration instruction is too long")
        if not normalized_decisions and normalized_instruction is None:
            raise ValueError("provide at least one arbitration decision or instruction")
        decisions_json = json.dumps(
            [
                {"concern_id": concern_id, "decision": decision}
                for concern_id, decision in normalized_decisions.items()
            ],
            ensure_ascii=False,
            indent=2,
        )
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_template,
            user_prompt=_render(
                user_template,
                BRIEF=_approved_brief(session).content,
                CURRENT_PLAN=current.content,
                DECISIONS=decisions_json,
                GLOBAL_INSTRUCTION=normalized_instruction or "N/A",
                ACTION_PLAN_SCHEMA=(
                    ref2v_supervised_canonical_action_plan_schema()
                    if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
                    else ref2v_supervised_action_plan_schema_v2()
                    if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
                    else ref2v_supervised_action_plan_schema()
                ),
            ),
            temperature=0.2,
            max_tokens=32768,
            operation_id="action_plan.reconcile",
            include_reasoning=include_reasoning,
        )
        audit_instruction = json.dumps(
            {
                "decisions": normalized_decisions,
                "instruction": normalized_instruction,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        def validate_reconciliation(content: str) -> None:
            revised = parse_compiled_plan(content)
            original_resolutions = {
                concern.concern_id: concern.resolution
                for concern in current_plan.continuity_concerns
            }
            resolutions = {
                concern.concern_id: concern.resolution
                for concern in revised.continuity_concerns
            }
            removed = sorted(set(original_resolutions) - set(resolutions))
            if removed:
                raise ValueError(
                    "the reconciled plan removed continuity concern(s): "
                    + ", ".join(removed)
                )
            missing = [
                concern_id
                for concern_id, decision in normalized_decisions.items()
                if resolutions.get(concern_id) != decision
            ]
            if missing:
                raise ValueError(
                    "the reconciled plan did not apply decision(s): "
                    + ", ".join(missing)
                )
            silently_changed = [
                concern_id
                for concern_id, resolution in original_resolutions.items()
                if concern_id not in normalized_decisions
                and resolutions.get(concern_id) != resolution
            ]
            if silently_changed:
                raise ValueError(
                    "the reconciled plan changed undecided concern(s): "
                    + ", ".join(silently_changed)
                )

        return self._stream(
            request,
            cookbook,
            session,
            composition,
            CompositionStage.BEAT_SHEET,
            expected,
            "",
            RevisionOrigin.REWRITE,
            audit_instruction,
            extract_revision=False,
            validate_content=validate_reconciliation,
            document_stage=CompositionStage.BEAT_SHEET,
        )

    def _stream_reconcile_direct_action_plan(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
        cookbook: PromptCookbookPort,
        decisions: Mapping[str, str],
        instruction: str | None,
        *,
        include_reasoning: bool,
    ) -> Iterator[CompositionStreamEvent]:
        """Apply human decisions to a Direct V2 plan using its native images."""

        if (
            cookbook.output_contract not in _DIRECT_ARBITRABLE_CONTRACTS
            or cookbook.beat_sheet_reconcile_system_prompt is None
            or cookbook.beat_sheet_reconcile_user_prompt is None
        ):
            raise ValueError(
                "this direct cookbook version does not support plan arbitration"
            )
        expected = self._expected_sources(
            session,
            composition,
            CompositionStage.BEAT_SHEET,
        )
        current = composition.beat_sheet.active_revision
        if current is None:
            raise ValueError("generate the action plan before arbitrating it")
        if current.source_ids != expected:
            raise ValueError("the current action plan is stale; regenerate it first")
        current_plan = _parse_direct_arbitrable_plan(cookbook, current.content)
        normalized_decisions = _normalize_arbitration_decisions(
            decisions,
            {risk.risk_id for risk in current_plan.risks},
        )
        if instruction is not None and not isinstance(instruction, str):
            raise TypeError("the global arbitration instruction must be text")
        normalized_instruction = (
            instruction.strip() if instruction and instruction.strip() else None
        )
        if normalized_instruction is not None and len(normalized_instruction) > 4000:
            raise ValueError("the global arbitration instruction is too long")
        if not normalized_decisions and normalized_instruction is None:
            raise ValueError("provide at least one arbitration decision or instruction")
        decisions_json = json.dumps(
            [
                {"risk_id": risk_id, "decision": decision}
                for risk_id, decision in normalized_decisions.items()
            ],
            ensure_ascii=False,
            indent=2,
        )
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=cookbook.beat_sheet_reconcile_system_prompt,
            user_prompt=_render(
                cookbook.beat_sheet_reconcile_user_prompt,
                BRIEF=_approved_brief(session).content,
                REFERENCES=direct_reference_mapping(
                    session,
                    composition_picture_mapping(composition),
                ),
                CURRENT_PLAN=current.content,
                DECISIONS=decisions_json,
                GLOBAL_INSTRUCTION=normalized_instruction or "N/A",
                ACTION_PLAN_SCHEMA=_direct_action_plan_schema(cookbook),
            ),
            images=self._direct_reference_images(session, composition),
            temperature=0.2,
            max_tokens=32768,
            operation_id="action_plan.reconcile",
            include_reasoning=include_reasoning,
        )
        audit_instruction = json.dumps(
            {
                "decisions": normalized_decisions,
                "instruction": normalized_instruction,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        def validate_reconciliation(content: str) -> None:
            revised = _parse_direct_arbitrable_plan(cookbook, content)
            if (
                cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS
                and len(revised.shots) != len(current_plan.shots)
            ):
                raise ValueError(
                    "the reconciled multi-shot plan must preserve its approved "
                    "shot count"
                )
            original_resolutions = {
                risk.risk_id: risk.resolution for risk in current_plan.risks
            }
            resolutions = {risk.risk_id: risk.resolution for risk in revised.risks}
            removed = sorted(set(original_resolutions) - set(resolutions))
            if removed:
                raise ValueError(
                    "the reconciled plan removed risk(s): " + ", ".join(removed)
                )
            missing = [
                risk_id
                for risk_id, decision in normalized_decisions.items()
                if resolutions.get(risk_id) != decision
            ]
            if missing:
                raise ValueError(
                    "the reconciled plan did not apply decision(s): "
                    + ", ".join(missing)
                )
            silently_changed = [
                risk_id
                for risk_id, resolution in original_resolutions.items()
                if risk_id not in normalized_decisions
                and resolutions.get(risk_id) != resolution
            ]
            if silently_changed:
                raise ValueError(
                    "the reconciled plan changed undecided risk(s): "
                    + ", ".join(silently_changed)
                )

        return self._stream(
            request,
            cookbook,
            session,
            composition,
            CompositionStage.BEAT_SHEET,
            expected,
            "",
            RevisionOrigin.REWRITE,
            audit_instruction,
            extract_revision=False,
            validate_content=validate_reconciliation,
            document_stage=CompositionStage.BEAT_SHEET,
        )

    def approve(
        self,
        source_session_id: str,
        stage: CompositionStage,
    ) -> PromptComposition:
        session = self.sessions.get(source_session_id)
        composition = self.compositions.get(source_session_id)
        cookbook = self._validated_cookbook(session, composition)
        expected = self._expected_sources(session, composition, stage)
        document = composition.document(stage)
        if document.active_revision is not None:
            _raise_lint(cookbook, stage, document.active_revision.content)
        return self.compositions.save_if_current(
            composition,
            composition.update_document(document.approve(expected)),
        )

    def _request(
        self,
        source_session_id: str,
        stage: CompositionStage,
        *,
        instruction: str | None,
        include_reasoning: bool = False,
    ):
        session = self.sessions.get(source_session_id)
        composition = self.compositions.get(source_session_id)
        cookbook = self._validated_cookbook(session, composition)
        expected = self._expected_sources(session, composition, stage)
        prefix = ""
        if instruction is None:
            system_prompt, user_prompt = self._generation_prompts(
                session,
                composition,
                cookbook,
                stage,
            )
            origin_operation = "generate"
        else:
            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError("instruction must not be empty")
            if (
                cookbook.output_contract in _PLANNED_CONTRACTS
                and stage is CompositionStage.BEAT_SHEET
            ):
                raise ValueError(
                    "the internal action plan must be regenerated, not rewritten"
                )
            current = composition.document(stage).active_revision
            if current is None:
                raise ValueError("generate this stage before requesting a revision")
            if current.source_ids != expected:
                raise ValueError("the current document is stale; regenerate it first")
            editable_current = current.content
            if (
                cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT
                and stage is CompositionStage.FINAL_PROMPT
            ):
                prefix = direct_reference_header(
                    session,
                    composition_picture_mapping(composition),
                )
                expected_prefix = prefix + "\n\n"
                if not editable_current.startswith(expected_prefix):
                    raise ValueError("the direct super-fast prompt has the wrong header")
                editable_current = editable_current[len(expected_prefix) :]
            if (
                cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS
                and stage is CompositionStage.FINAL_PROMPT
            ):
                prefix = _direct_ref2v_multishot_compiler_context_for(
                    session,
                    composition,
                    cookbook,
                )
                editable_current = (
                    rehydrate_direct_ref2v_multishot_editable_document_v2(
                        current.content,
                        current.compiler_context,
                    )
                    if cookbook.output_contract
                    == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
                    else rehydrate_direct_ref2v_multishot_editable_document(
                        current.content,
                        current.compiler_context,
                    )
                )
            if (
                cookbook.output_contract in _REF2V_DIRECT_PLACEHOLDER_CONTRACTS
                and stage is CompositionStage.FINAL_PROMPT
            ):
                prefix = _direct_ref2v_compiler_context(
                    session,
                    composition,
                    cookbook,
                )
                editable_current = rehydrate_direct_ref2v_editable_document(
                    current.content,
                    current.compiler_context,
                )
            if (
                cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
                and stage is CompositionStage.FINAL_PROMPT
            ):
                editable_current = _rehydrate_i2v_editable_document(
                    current.content,
                    current.compiler_context,
                )
            if (
                cookbook.output_contract == _I2VA_DIRECT_CONTRACT
                and stage is CompositionStage.FINAL_PROMPT
            ):
                prefix = _direct_i2v_compiler_context(
                    session,
                    composition,
                    cookbook,
                )
                editable_current = rehydrate_direct_i2v_editable_document(
                    current.content,
                    _decode_direct_i2v_camera_context(
                        current.compiler_context or ""
                    ),
                )
            if (
                cookbook.output_contract in _CAMERA_OWNED_MONO_CONTRACTS
                and stage is CompositionStage.FINAL_PROMPT
            ):
                if cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT:
                    prefix = _direct_ref2v_compiler_context(
                        session,
                        composition,
                        cookbook,
                    )
                    context = decode_timed_camera_context(
                        current.compiler_context or ""
                    )
                    editable_current = rehydrate_camera_owned_direct_ref2v_document(
                        current.content,
                        context.header or "",
                        context.placements,
                    )
                else:
                    prefix = _direct_i2v_compiler_context(
                        session,
                        composition,
                        cookbook,
                    )
                    context = decode_timed_camera_context(
                        current.compiler_context or ""
                    )
                    editable_current = rehydrate_camera_owned_direct_i2v_document(
                        current.content,
                        context.placements,
                    )
            if (
                stage is CompositionStage.FINAL_PROMPT
                and CompositionStage.REFERENCE_PLAN.value in cookbook.stages
            ):
                prefix, editable_current = _split_final_prompt(current.content)
            system_prompt = _render(
                cookbook.revision_system_prompt,
                STAGE_CONTRACT=_stage_contract(
                    stage,
                    cookbook,
                    compiler_context=prefix or current.compiler_context,
                ),
            )
            revision_values = {
                "CURRENT": editable_current,
                "INSTRUCTION": instruction.strip(),
            }
            if (
                cookbook.output_contract in _PLANNED_CONTRACTS
                and stage is CompositionStage.FINAL_PROMPT
            ):
                action_plan = _approved_stage(
                    composition,
                    CompositionStage.BEAT_SHEET,
                    self._expected_sources(
                        session,
                        composition,
                        CompositionStage.BEAT_SHEET,
                    ),
                )
                revision_values["PLAN"] = _writer_action_plan(
                    cookbook,
                    action_plan.content,
                )
                if cookbook.output_contract in _DIRECT_MULTIMODAL_CONTRACTS:
                    revision_values["REFERENCE_MAPPING"] = (
                        direct_reference_mapping(
                            session,
                            composition_picture_mapping(composition),
                        )
                    )
            user_prompt = _render(
                cookbook.revision_user_prompt,
                **revision_values,
            )
            origin_operation = "revise"
        if (
            stage is CompositionStage.FINAL_PROMPT
            and instruction is None
            and CompositionStage.REFERENCE_PLAN.value in cookbook.stages
        ):
            reference_plan = _approved_stage(
                composition,
                CompositionStage.REFERENCE_PLAN,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.REFERENCE_PLAN,
                ),
            )
            prefix = _reference_prefix(reference_plan.content)
        if (
            stage is CompositionStage.FINAL_PROMPT
            and cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
        ):
            action_plan = _approved_stage(
                composition,
                CompositionStage.BEAT_SHEET,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.BEAT_SHEET,
                ),
            )
            prefix = _encode_h3_camera_context(
                ref2v_supervised_canonical_camera_directives(
                    action_plan.content,
                )
            )
        if (
            stage is CompositionStage.FINAL_PROMPT
            and cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS
        ):
            prefix = _direct_ref2v_multishot_compiler_context_for(
                session,
                composition,
                cookbook,
            )
        elif (
            stage is CompositionStage.FINAL_PROMPT
            and cookbook.output_contract in _REF2V_DIRECT_CONTRACTS
        ):
            prefix = _direct_ref2v_compiler_context(session, composition, cookbook)
        if (
            stage is CompositionStage.FINAL_PROMPT
            and cookbook.output_contract in _I2VA_DIRECT_CONTRACTS
        ):
            prefix = _direct_i2v_compiler_context(session, composition, cookbook)
        operation_stage = (
            "action_plan"
            if cookbook.output_contract in _PLANNED_CONTRACTS
            and stage is CompositionStage.BEAT_SHEET
            else stage.value
        )
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=(
                self._direct_reference_images(session, composition)
                if (
                    cookbook.output_contract in _DIRECT_MULTIMODAL_CONTRACTS
                    and stage is CompositionStage.BEAT_SHEET
                )
                or (
                    cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT
                    and stage is CompositionStage.FINAL_PROMPT
                )
                else ()
            ),
            temperature={
                CompositionStage.REFERENCE_PLAN: 0.15,
                CompositionStage.BEAT_SHEET: 0.3,
                CompositionStage.FINAL_PROMPT: 0.2,
            }[stage],
            max_tokens=32768,
            operation_id=f"{operation_stage}.{origin_operation}",
            include_reasoning=include_reasoning,
        )
        return session, composition, cookbook, expected, request, prefix

    def _direct_reference_images(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
    ) -> tuple[ImageInput, ...]:
        if self.assets is None:
            raise ValueError("direct multimodal image access is not configured")
        images: list[ImageInput] = []
        for reference_id, picture_index in composition_picture_mapping(composition):
            reference = session.reference(reference_id)
            asset = self.assets.get(reference.asset_id)
            images.append(
                ImageInput(
                    media_type=asset.media_type,
                    content=self.assets.read_bytes(reference.asset_id),
                    label=(
                        f"<Picture {picture_index}> · {reference.label} · "
                        f"role={reference.role}"
                    ),
                )
            )
        return tuple(images)

    def _generation_prompts(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
        cookbook: PromptCookbookPort,
        stage: CompositionStage,
    ) -> tuple[str, str]:
        brief = _approved_brief(session)
        if cookbook.output_contract in _DIRECT_MULTIMODAL_CONTRACTS:
            if stage is CompositionStage.BEAT_SHEET:
                return (
                    _required_prompt(
                        cookbook.beat_sheet_system_prompt,
                        "beat_sheet_system",
                    ),
                    _render(
                        _required_prompt(
                            cookbook.beat_sheet_user_prompt,
                            "beat_sheet_user",
                        ),
                        BRIEF=brief.content,
                        REFERENCES=direct_reference_mapping(
                            session,
                            composition_picture_mapping(composition),
                        ),
                        ACTION_PLAN_SCHEMA=_direct_action_plan_schema(cookbook),
                        CREATIVE_FREEDOM=str(brief.creative_freedom),
                        CREATIVE_POLICY=creative_freedom_policy(
                            brief.creative_freedom
                        ),
                    ),
                )
            if stage is not CompositionStage.FINAL_PROMPT:
                raise ValueError(f"stage {stage.value} is not active for this cookbook")
            action_plan = _approved_stage(
                composition,
                CompositionStage.BEAT_SHEET,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.BEAT_SHEET,
                ),
            )
            return (
                _required_prompt(
                    cookbook.final_prompt_system_prompt,
                    "final_prompt_system",
                ),
                _render(
                    _required_prompt(
                        cookbook.final_prompt_user_prompt,
                        "final_prompt_user",
                    ),
                    BRIEF=brief.content,
                    PLAN=_writer_action_plan(cookbook, action_plan.content),
                    REFERENCE_MAPPING=direct_reference_mapping(
                        session,
                        composition_picture_mapping(composition),
                    ),
                ),
            )
        if cookbook.output_contract in _REF2V_PLANNED_CONTRACTS:
            if stage is CompositionStage.BEAT_SHEET:
                return (
                    _required_prompt(
                        cookbook.beat_sheet_system_prompt,
                        "beat_sheet_system",
                    ),
                    _render(
                        _required_prompt(
                            cookbook.beat_sheet_user_prompt,
                            "beat_sheet_user",
                        ),
                        BRIEF=brief.content,
                        REFERENCES=_action_plan_reference_context(
                            session,
                            composition,
                            cookbook,
                        ),
                        ACTION_PLAN_SCHEMA=(
                            ref2v_supervised_canonical_action_plan_schema()
                            if cookbook.output_contract
                            == _REF2V_SUPERVISED_CANONICAL_CONTRACT
                            else ref2v_supervised_action_plan_schema_v2()
                            if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
                            else ref2v_supervised_action_plan_schema()
                            if cookbook.output_contract == _REF2V_SUPERVISED_CONTRACT
                            else ref2v_repairable_action_plan_schema()
                            if cookbook.output_contract == _REF2V_RECOVERABLE_CONTRACT
                            else ref2v_action_plan_schema_v3()
                            if cookbook.output_contract == _REF2V_ADVISORY_CONTRACT
                            else ref2v_action_plan_schema_v2()
                            if cookbook.output_contract in {
                                _REF2V_PLANNED_V2_CONTRACT,
                                _REF2V_ELASTIC_CONTRACT,
                                _REF2V_BOUNDED_CONTRACT,
                            }
                            else ref2v_action_plan_schema()
                        ),
                    ),
                )
            if stage is not CompositionStage.FINAL_PROMPT:
                raise ValueError(f"stage {stage.value} is not active for this cookbook")
            action_plan = _approved_stage(
                composition,
                CompositionStage.BEAT_SHEET,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.BEAT_SHEET,
                ),
            )
            return (
                _required_prompt(
                    cookbook.final_prompt_system_prompt,
                    "final_prompt_system",
                ),
                _render(
                    _required_prompt(
                        cookbook.final_prompt_user_prompt,
                        "final_prompt_user",
                    ),
                    BRIEF=brief.content,
                    BEAT_SHEET=_writer_action_plan(cookbook, action_plan.content),
                ),
            )
        if cookbook.stages == (CompositionStage.FINAL_PROMPT.value,):
            return (
                _required_prompt(
                    cookbook.final_prompt_system_prompt,
                    "final_prompt_system",
                ),
                _render(
                    _required_prompt(
                        cookbook.final_prompt_user_prompt,
                        "final_prompt_user",
                    ),
                    BRIEF=brief.content,
                    REFERENCES=_reference_context(session, composition, cookbook),
                ),
            )
        if stage is CompositionStage.REFERENCE_PLAN:
            return (
                _required_prompt(
                    cookbook.reference_plan_system_prompt,
                    "reference_plan_system",
                ),
                _render(
                    _required_prompt(
                        cookbook.reference_plan_user_prompt,
                        "reference_plan_user",
                    ),
                    BRIEF=brief.content,
                    REFERENCES=_reference_context(session, composition, cookbook),
                ),
            )
        reference_plan = _approved_stage(
            composition,
            CompositionStage.REFERENCE_PLAN,
            self._expected_sources(
                session,
                composition,
                CompositionStage.REFERENCE_PLAN,
            ),
        )
        if stage is CompositionStage.BEAT_SHEET:
            return (
                _required_prompt(
                    cookbook.beat_sheet_system_prompt,
                    "beat_sheet_system",
                ),
                _render(
                    _required_prompt(
                        cookbook.beat_sheet_user_prompt,
                        "beat_sheet_user",
                    ),
                    BRIEF=brief.content,
                    REFERENCE_PLAN=reference_plan.content,
                ),
            )
        beat_sheet = _approved_stage(
            composition,
            CompositionStage.BEAT_SHEET,
            self._expected_sources(
                session,
                composition,
                CompositionStage.BEAT_SHEET,
            ),
        )
        return (
            cookbook.final_prompt_system_prompt,
            _render(
                cookbook.final_prompt_user_prompt,
                BRIEF=brief.content,
                REFERENCE_PLAN=reference_plan.content,
                BEAT_SHEET=beat_sheet.content,
            ),
        )

    def _expected_sources(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
        stage: CompositionStage,
    ) -> tuple[str, ...]:
        brief = _approved_brief(session)
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if stage.value not in cookbook.stages:
            raise ValueError(f"stage {stage.value} is not active for this cookbook")
        if cookbook.output_contract in _PLANNED_CONTRACTS:
            action_plan_sources = (
                f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
                f"brief:{brief.revision_id}",
                *_binding_source_snapshots(session, composition),
            )
            if stage is CompositionStage.BEAT_SHEET:
                return action_plan_sources
            action_plan = _approved_stage(
                composition,
                CompositionStage.BEAT_SHEET,
                action_plan_sources,
            )
            return (
                f"brief:{brief.revision_id}",
                f"action_plan:{action_plan.revision_id}",
            )
        if cookbook.stages == (CompositionStage.FINAL_PROMPT.value,):
            values = [
                f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
                f"brief:{brief.revision_id}",
            ]
            values.extend(_binding_source_snapshots(session, composition))
            return tuple(values)
        if stage is CompositionStage.REFERENCE_PLAN:
            values = [
                f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
                f"brief:{brief.revision_id}",
            ]
            values.extend(_binding_source_snapshots(session, composition))
            return tuple(values)
        reference_sources = self._expected_sources(
            session,
            composition,
            CompositionStage.REFERENCE_PLAN,
        )
        reference_plan = _approved_stage(
            composition,
            CompositionStage.REFERENCE_PLAN,
            reference_sources,
        )
        if stage is CompositionStage.BEAT_SHEET:
            return (
                f"brief:{brief.revision_id}",
                f"reference_plan:{reference_plan.revision_id}",
            )
        beat_sources = (
            f"brief:{brief.revision_id}",
            f"reference_plan:{reference_plan.revision_id}",
        )
        beat_sheet = _approved_stage(
            composition,
            CompositionStage.BEAT_SHEET,
            beat_sources,
        )
        return (
            f"reference_plan:{reference_plan.revision_id}",
            f"beat_sheet:{beat_sheet.revision_id}",
        )

    def _persist_if_current(
        self,
        initial_session: PromptLabSession,
        initial_composition: PromptComposition,
        stage: CompositionStage,
        expected: tuple[str, ...],
        content: str,
        origin: RevisionOrigin,
        instruction: str | None = None,
        *,
        compiler_context: str | None = None,
    ) -> PromptComposition:
        current_session = self.sessions.get(initial_session.session_id)
        current = self.compositions.get(initial_session.session_id)
        if current.cookbook != initial_composition.cookbook:
            raise ValueError("cookbook changed while the model was generating")
        if current.document(stage).active_revision_id != initial_composition.document(stage).active_revision_id:
            raise ValueError("this stage changed while the model was generating")
        cookbook = self._validated_cookbook(current_session, current)
        if self._expected_sources(current_session, current, stage) != expected:
            raise ValueError("an upstream approval changed while the model was generating")
        _validate_compiler_context_change(
            cookbook,
            stage,
            origin,
            instruction,
            current.document(stage).active_revision,
            compiler_context,
        )
        return self._append_revision(
            current,
            stage,
            expected,
            content,
            origin,
            instruction,
            compiler_context=compiler_context,
        )

    def _validated_cookbook(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
    ) -> PromptCookbookPort:
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if cookbook.reference != composition.cookbook:
            raise ValueError("the cookbook engine contract changed")
        if cookbook.output_contract in _H3_PROTOCOL_CONTRACTS and (
            cookbook.reference.engine_contract_id,
            cookbook.reference.engine_contract_version,
        ) != (PROTOCOL_ID, PROTOCOL_VERSION):
            raise ValueError(
                "the cookbook requires an unsupported MiniMax H3 protocol version"
            )
        _validate_bindings(session, cookbook, composition.bindings)
        return cookbook

    def _append_revision(
        self,
        composition: PromptComposition,
        stage: CompositionStage,
        expected: tuple[str, ...],
        content: str,
        origin: RevisionOrigin,
        instruction: str | None = None,
        *,
        compiler_context: str | None = None,
    ) -> PromptComposition:
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if (
            cookbook.output_contract in _DIRECT_PLAN_V2_CONTRACTS
            and stage is CompositionStage.FINAL_PROMPT
        ):
            session = self.sessions.get(composition.source_session_id)
            action_plan = _approved_stage(
                composition,
                CompositionStage.BEAT_SHEET,
                self._expected_sources(
                    session,
                    composition,
                    CompositionStage.BEAT_SHEET,
                ),
            )
            content = (
                apply_direct_i2v_timing(
                    content,
                    action_plan.content,
                    preserve_field_linebreak=(
                        cookbook.output_contract
                        == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT
                    ),
                )
                if cookbook.output_contract in _I2VA_DIRECT_CONTRACTS
                else apply_direct_ref2v_timing_v2(content, action_plan.content)
            )
        if stage is CompositionStage.FINAL_PROMPT and cookbook.output_contract in {
            _I2VA_CANONICAL_CONTRACT,
            *_I2VA_DIRECT_CONTRACTS,
            _REF2V_SUPERVISED_CANONICAL_CONTRACT,
            *_REF2V_DIRECT_CONTRACTS,
            *_REF2V_DIRECT_MULTISHOT_CONTRACTS,
        }:
            if compiler_context is None:
                raise ValueError("canonical H3 revision is missing compiler context")
            mode = H3ProtocolMode.I2VA
            if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
                mode = H3ProtocolMode.REF2VA
                expected_context = _direct_ref2v_multishot_compiler_context_for(
                    self.sessions.get(composition.source_session_id),
                    composition,
                    cookbook,
                )
                if compiler_context != expected_context:
                    raise ValueError(
                        "direct Ref2V multi-shot compiler context must come from "
                        "the approved plan"
                    )
                if (
                    cookbook.output_contract
                    == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
                ):
                    context_v2 = decode_direct_ref2v_multishot_context_v2(
                        compiler_context
                    )
                    directives = context_v2.directives
                    errors = lint_direct_ref2v_multishot_prompt_v2(
                        content,
                        context_v2,
                    )
                else:
                    context = decode_direct_ref2v_multishot_context(compiler_context)
                    directives = context.directives
                    errors = lint_direct_ref2v_multishot_prompt(content, context)
                if errors:
                    raise ValueError(" ".join(errors))
            elif cookbook.output_contract in _REF2V_DIRECT_CONTRACTS:
                mode = H3ProtocolMode.REF2VA
                expected_context = _direct_ref2v_compiler_context(
                    self.sessions.get(composition.source_session_id),
                    composition,
                    cookbook,
                )
                if compiler_context != expected_context:
                    raise ValueError(
                        "direct Ref2V compiler context must come from the approved plan"
                    )
                if cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT:
                    context = decode_timed_camera_context(compiler_context)
                    directives = tuple(
                        item.directive for item in context.placements
                    )
                    rehydrate_camera_owned_direct_ref2v_document(
                        content,
                        context.header or "",
                        context.placements,
                    )
                else:
                    _, directives = decode_direct_ref2v_context(compiler_context)
            elif cookbook.output_contract in _I2VA_DIRECT_CONTRACTS:
                expected_context = _direct_i2v_compiler_context(
                    self.sessions.get(composition.source_session_id),
                    composition,
                    cookbook,
                )
                if compiler_context != expected_context:
                    raise ValueError(
                        "direct I2VA compiler context must come from the approved plan"
                    )
                if cookbook.output_contract == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT:
                    context = decode_timed_camera_context(compiler_context)
                    directives = tuple(
                        item.directive for item in context.placements
                    )
                    rehydrate_camera_owned_direct_i2v_document(
                        content,
                        context.placements,
                    )
                else:
                    directives = _decode_direct_i2v_camera_context(compiler_context)
            else:
                directives = _decode_h3_camera_context(compiler_context)
            if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT:
                mode = H3ProtocolMode.REF2VA
                action_plan = composition.beat_sheet.active_revision
                if action_plan is None:
                    raise ValueError("canonical Ref2V requires an approved action plan")
                plan_context = _encode_h3_camera_context(
                    ref2v_supervised_canonical_camera_directives(
                        action_plan.content,
                    )
                )
                if compiler_context != plan_context:
                    raise ValueError(
                        "canonical Ref2V compiler context must come from the approved plan"
                    )
            _raise_h3_protocol(
                mode,
                content,
                expected_directives=directives,
            )
        _raise_lint(cookbook, stage, content)
        if cookbook.output_contract in {
            _SUPER_FAST_REF2V_DIRECT_CONTRACT,
            *_REF2V_ALL_DIRECT_CONTRACTS,
        }:
            validate_direct_ref2v_labels(
                self.sessions.get(composition.source_session_id),
                composition_picture_mapping(composition),
                stage,
                content,
            )
        elif cookbook.output_contract in _REF2VA_CONTRACTS:
            _raise_cookbook_labels(
                self.sessions.get(composition.source_session_id),
                composition,
                cookbook,
                stage,
                content,
            )
        elif cookbook.output_contract in _I2VA_DIRECT_CONTRACTS:
            _raise_i2v_labels(composition, stage, content)
        elif cookbook.output_contract in {
            _REF2V_COMPILED_CONTRACT,
            *_REF2V_PLANNED_CONTRACTS,
        }:
            _raise_compiled_ref2v_labels(
                composition,
                stage,
                content,
                enforce_content=(
                    cookbook.output_contract not in _REF2V_SOFT_FINAL_CONTRACTS
                ),
            )
        elif cookbook.output_contract in {
            "minimax.h3.i2va",
            _I2VA_CANONICAL_CONTRACT,
        }:
            _raise_i2v_labels(composition, stage, content)
        else:
            raise ValueError(f"unsupported output contract: {cookbook.output_contract}")
        document = composition.document(stage)
        revision = CompositionRevision(
            revision_id=f"{stage.value}-{uuid4().hex}",
            content=_strip_fence(content),
            origin=origin,
            source_ids=expected,
            parent_revision_id=document.active_revision_id,
            instruction=instruction,
            compiler_context=compiler_context,
        )
        return self.compositions.save_if_current(
            composition,
            composition.update_document(document.add_revision(revision)),
        )

    def _stream(
        self,
        request: CompletionRequest,
        cookbook: PromptCookbookPort,
        initial_session: PromptLabSession,
        initial_composition: PromptComposition,
        stage: CompositionStage,
        expected: tuple[str, ...],
        prefix: str,
        origin: RevisionOrigin,
        instruction: str | None = None,
        *,
        extract_revision: bool = True,
        validate_content: Callable[[str], None] | None = None,
        document_stage: CompositionStage | None = None,
    ) -> Iterator[CompositionStreamEvent]:
        terminal = False
        if prefix and not _is_hidden_compiler_context(prefix):
            yield CompositionStreamEvent(
                kind=StreamEventKind.DELTA,
                phase=StreamPhase.GENERATING,
                text=prefix,
            )
        for event in self.gateway.stream(request):
            if event.kind is StreamEventKind.COMPLETED:
                if event.result is None:
                    raise ValueError("stream completed without a result")
                try:
                    result_content = event.result.content
                    if (
                        origin is RevisionOrigin.REWRITE
                        and extract_revision
                        and cookbook.output_contract
                        != _SUPER_FAST_REF2V_DIRECT_CONTRACT
                    ):
                        result_content = _revision_document_contract(
                            cookbook,
                            stage,
                            compiler_context=prefix or None,
                        ).extract(result_content)
                    content, compiler_context = _compile_content_with_context(
                        cookbook,
                        stage,
                        prefix,
                        result_content,
                    )
                    if validate_content is not None:
                        validate_content(content)
                    composition = self._persist_if_current(
                        initial_session,
                        initial_composition,
                        stage,
                        expected,
                        content,
                        origin,
                        instruction,
                        compiler_context=compiler_context,
                    )
                except Exception as error:
                    self._report_application_outcome(
                        event.result.call_id,
                        LlmCallApplicationOutcome.REJECTED,
                        error,
                    )
                    raise
                self._report_application_outcome(
                    event.result.call_id,
                    LlmCallApplicationOutcome.ACCEPTED,
                )
                terminal = True
                yield CompositionStreamEvent(
                    kind=StreamEventKind.COMPLETED,
                    phase=StreamPhase.COMPLETED,
                    text=content,
                    progress=1.0,
                    composition=composition,
                    finish_reason=event.result.finish_reason,
                    max_tokens=request.max_tokens,
                    document_stage=document_stage,
                )
            elif event.kind is StreamEventKind.TRUNCATED:
                terminal = True
                visible_prefix = "" if _is_hidden_compiler_context(prefix) else prefix
                partial = visible_prefix + (
                    event.result.content if event.result else event.text
                )
                yield CompositionStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=partial,
                    finish_reason=(event.result.finish_reason if event.result else None),
                    max_tokens=request.max_tokens,
                    document_stage=document_stage,
                )
            else:
                yield CompositionStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                    document_stage=(
                        document_stage
                        if document_stage is not None
                        else stage
                        if event.kind is StreamEventKind.REASONING
                        else None
                    ),
                )
        if not terminal:
            raise ValueError("model stream ended before completion")

    def _report_application_outcome(
        self,
        call_id: str | None,
        outcome: LlmCallApplicationOutcome,
        error: Exception | None = None,
    ) -> None:
        if self.application_outcomes is None or call_id is None:
            return
        try:
            self.application_outcomes.report_application_outcome(
                call_id,
                outcome,
                error_type=type(error).__name__ if error is not None else None,
                error_message=(str(error).strip() or None) if error is not None else None,
            )
        except Exception:
            _LOGGER.exception(
                "failed to persist application outcome for LLM call %s",
                call_id,
            )


def lint_composition_document(
    stage: CompositionStage,
    content: str,
) -> tuple[str, ...]:
    if not isinstance(content, str) or not content.strip():
        return ("Le document est vide.",)
    errors: list[str] = []
    sections = _STAGE_SECTIONS[stage]
    positions: list[int] = []
    for section in sections:
        matches = list(re.finditer(rf"(?m)^{re.escape(section)}:$", content))
        if not matches:
            errors.append(f"Section manquante : {section}:")
        else:
            positions.append(matches[0].start())
            if len(matches) > 1:
                errors.append(f"Section dupliquée : {section}:")
    unexpected_sections = sorted(
        set(re.findall(r"(?m)^([a-z][a-z0-9_]*):$", content)) - set(sections)
    )
    for section in unexpected_sections:
        errors.append(f"Section inattendue : {section}:")
    if len(positions) == len(sections) and positions != sorted(positions):
        errors.append("Les sections ne sont pas dans l’ordre attendu.")
    if stage is CompositionStage.REFERENCE_PLAN:
        if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>", content):
            errors.append("Le plan Ref2VA doit utiliser <Subject N> et <Picture N>, jamais @image ou <Image N>.")
        for forbidden in _FINAL_SECTIONS[1:]:
            if re.search(rf"(?im)^\s*{re.escape(forbidden)}\s*:\s*$", content):
                errors.append(f"Section prématurée dans le plan : {forbidden}:")
    elif stage is CompositionStage.BEAT_SHEET:
        errors.extend(_lint_six_shots(_section_body(content, "beat_sheet", None)))
    elif stage is CompositionStage.FINAL_PROMPT:
        lowered = content.lower()
        summary = _section_body(content, "summary", "retention_analysis")
        if not summary.lstrip().startswith("[reference generation]"):
            errors.append("Le summary doit commencer par [reference generation].")
        if "integrated_multimodal_description" in lowered:
            errors.append("Le prompt utilise un ancien contrat MiniMax incompatible.")
        if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>", content):
            errors.append("Le prompt final doit utiliser <Subject N> et <Picture N>, jamais @image ou <Image N>.")
        detailed = _section_body(
            content,
            "detailed_description",
            "overall_soundscape",
        )
        errors.extend(_lint_six_shots(detailed, require_style_lead=True))
        defined = set(re.findall(r"<Subject\s+\d+>", _before_section(content, "summary")))
        used = set(re.findall(r"<Subject\s+\d+>", content))
        for subject in sorted(used - defined):
            errors.append(f"Sujet utilisé mais non défini : {subject}")
    return tuple(errors)


def lint_cookbook_document(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    content: str,
) -> tuple[str, ...]:
    if cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT:
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"Stage {stage.value} does not belong to this cookbook.",)
        return _lint_super_fast_ref2v_prompt(content)
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return (
                lint_direct_ref2v_multishot_plan_v2(content)
                if cookbook.output_contract
                == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
                else lint_direct_ref2v_multishot_plan(content)
            )
        if stage is CompositionStage.FINAL_PROMPT:
            return (
                lint_direct_ref2v_multishot_prompt_v2(content)
                if cookbook.output_contract
                == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
                else lint_direct_ref2v_multishot_prompt(content)
            )
        return (f"Stage {stage.value} does not belong to this cookbook.",)
    if cookbook.output_contract in _I2VA_DIRECT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_direct_ref2v_action_plan_v2(content)
        if stage is CompositionStage.FINAL_PROMPT:
            errors = list(lint_i2v_prompt(content))
            errors.extend(_h3_protocol_errors(H3ProtocolMode.I2VA, content))
            return tuple(dict.fromkeys(errors))
        return (f"Stage {stage.value} does not belong to this cookbook.",)
    if cookbook.output_contract in _REF2V_DIRECT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return (
                lint_direct_ref2v_action_plan_v2(content)
                if cookbook.output_contract
                in {_REF2V_DIRECT_V2_CONTRACT, _REF2V_DIRECT_V3_CONTRACT}
                else lint_direct_ref2v_action_plan(content)
            )
        if stage is CompositionStage.FINAL_PROMPT:
            errors = list(lint_direct_ref2v_prompt(content))
            errors.extend(_h3_protocol_errors(H3ProtocolMode.REF2VA, content))
            return tuple(dict.fromkeys(errors))
        return (f"Stage {stage.value} does not belong to this cookbook.",)
    if cookbook.output_contract == "minimax.h3.ref2va":
        return lint_composition_document(stage, content)
    if cookbook.output_contract == "minimax.h3.ref2va.single_shot":
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
        return lint_ref2v_single_shot_prompt(content)
    if cookbook.output_contract == _REF2V_COMPILED_CONTRACT:
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
        return lint_compiled_ref2v_single_shot_prompt(content)
    if cookbook.output_contract == _REF2V_PLANNED_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_action_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            return lint_compiled_ref2v_single_shot_prompt(content)
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract == _REF2V_PLANNED_V2_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_action_plan_v2(content)
        if stage is CompositionStage.FINAL_PROMPT:
            return lint_compiled_ref2v_single_shot_prompt(content)
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract == _REF2V_ELASTIC_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_elastic_action_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            return lint_compiled_ref2v_single_shot_prompt(content)
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract == _REF2V_BOUNDED_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_bounded_action_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            return lint_compiled_ref2v_single_shot_prompt(content)
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_supervised_canonical_compiled_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            errors = [
                error
                for error in lint_compiled_ref2v_single_shot_prompt(
                    content,
                    expected_header=_ref2v_compiled_header(cookbook),
                )
                if "15 secondes" not in error
            ]
            errors.extend(_h3_protocol_errors(H3ProtocolMode.REF2VA, content))
            return tuple(dict.fromkeys(errors))
        return (f"Stage {stage.value} does not belong to this cookbook.",)
    if cookbook.output_contract in _REF2V_SUPERVISED_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return (
                lint_ref2v_supervised_compiled_plan_v2(content)
                if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
                else lint_ref2v_supervised_compiled_plan(content)
            )
        if stage is CompositionStage.FINAL_PROMPT:
            if not isinstance(content, str) or not content.strip():
                return ("Le prompt Ref2V compilé est vide.",)
            return ()
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_advisory_action_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            if not isinstance(content, str) or not content.strip():
                return ("Le prompt Ref2V compilé est vide.",)
            return ()
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract in {
        "minimax.h3.i2va",
        _I2VA_CANONICAL_CONTRACT,
    }:
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
        errors = list(lint_i2v_prompt(content))
        if cookbook.output_contract == _I2VA_CANONICAL_CONTRACT:
            errors.extend(_h3_protocol_errors(H3ProtocolMode.I2VA, content))
        return tuple(dict.fromkeys(errors))
    return (f"Contrat de sortie inconnu : {cookbook.output_contract}",)


def lint_ref2v_single_shot_prompt(content: str) -> tuple[str, ...]:
    """Validate the direct single-shot subset of the MiniMax Ref2VA contract."""
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt Ref2V est vide.",)
    value = _strip_fence(content).replace("\r\n", "\n")
    errors: list[str] = []
    positions: list[int] = []
    for section in _FINAL_SECTIONS:
        matches = list(re.finditer(rf"(?m)^{re.escape(section)}:$", value))
        if len(matches) != 1:
            errors.append(f"La section {section}: doit apparaître exactement une fois.")
        else:
            positions.append(matches[0].start())
    if len(positions) == len(_FINAL_SECTIONS) and positions != sorted(positions):
        errors.append("Les six sections Ref2VA ne sont pas dans l’ordre officiel.")
    unexpected = sorted(
        set(re.findall(r"(?m)^([a-z][a-z0-9_]*):$", value))
        - set(_FINAL_SECTIONS)
    )
    for section in unexpected:
        errors.append(f"Section Ref2VA inattendue : {section}:")
    if errors:
        return tuple(errors)

    summary = _section_body(value, "summary", "retention_analysis")
    if not summary.lstrip().startswith(
        "[keyframe completion + reference generation]"
    ):
        errors.append(
            "Le summary doit commencer par [keyframe completion + reference generation]."
        )
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>", value):
        errors.append(
            "Le prompt Ref2VA doit utiliser <Subject N> et <Picture N>, jamais @image ou <Image N>."
        )
    if "integrated_multimodal_description" in value.lower():
        errors.append("Le prompt utilise un ancien contrat MiniMax incompatible.")

    definitions = _section_body(value, "subject_definitions", "summary")
    subject_line = re.search(
        r"(?ms)^<Subject\s+1>(?:\s|:).*?"
        r"(?=^<(?:Subject|Picture)\s+\d+>(?:\s|:)|\Z)",
        definitions.strip(),
    )
    cited = (
        set(re.findall(r"<Picture\s+\d+>", subject_line.group(0)))
        if subject_line is not None
        else set()
    )
    if not {"<Picture 1>", "<Picture 2>"}.issubset(cited):
        errors.append(
            "La définition de <Subject 1> doit citer <Picture 1> et <Picture 2>."
        )
    if not re.search(r"(?m)^<Picture\s+1>(?:\s|:)", definitions):
        errors.append("<Picture 1> doit être définie comme ancre de première frame.")
    if re.search(r"(?m)^<Picture\s+2>(?:\s|:)", definitions):
        errors.append("<Picture 2> est une référence de sujet, pas une frame autonome.")

    detailed = _section_body(value, "detailed_description", "overall_soundscape")
    shot_numbers = [int(item) for item in re.findall(r"\[Shot\s+(\d+)\]", detailed)]
    if shot_numbers != [1]:
        errors.append("Le cookbook mono-plan doit contenir exactement un [Shot 1].")
    if re.search(r"\[Shot\s+1\]\s+At\s+", detailed):
        errors.append("[Shot 1] ne doit pas avoir de timestamp.")
    if not detailed.split("[Shot 1]", 1)[0].strip():
        errors.append("detailed_description doit établir le style avant [Shot 1].")
    if value.count("<d>") != value.count("</d>"):
        errors.append("Les balises de dialogue <d> ne sont pas équilibrées.")
    return tuple(errors)


def _ref2v_compiled_header(cookbook: PromptCookbookPort) -> str:
    body_slot = next(
        (slot for slot in cookbook.slots if slot.slot_id == "body_reference"),
        None,
    )
    if (
        body_slot is not None
        and body_slot.evidence_policy
        is ReferenceEvidencePolicy.APPEARANCE_ONLY_V1
    ):
        return _REF2V_APPEARANCE_ONLY_COMPILED_HEADER
    return _REF2V_COMPILED_HEADER


def lint_compiled_ref2v_single_shot_prompt(
    content: str,
    *,
    expected_header: str = _REF2V_COMPILED_HEADER,
) -> tuple[str, ...]:
    """Validate the compact, code-compiled Ref2V single-shot contract."""
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt Ref2V compilé est vide.",)
    value = _strip_fence(content).replace("\r\n", "\n")
    errors: list[str] = []
    expected_start = expected_header + "\n\n"
    if not value.startswith(expected_start):
        errors.append("Le mapping de références compilé a été modifié.")

    markers = ("Shot 1", "overall_soundscape", "non_diegetic_music")
    positions: list[int] = []
    for marker in markers:
        matches = list(re.finditer(rf"(?m)^{re.escape(marker)}:", value))
        if len(matches) != 1:
            errors.append(f"Le champ {marker}: doit apparaître exactement une fois.")
        else:
            positions.append(matches[0].start())
    if len(positions) == len(markers) and positions != sorted(positions):
        errors.append("Les champs du prompt Ref2V compilé ne sont pas dans l’ordre attendu.")
    if errors:
        return tuple(errors)

    shot_position = positions[0]
    if not value[len(expected_start) : shot_position].strip():
        errors.append("La mise en place de la scène ne doit pas être vide.")
    shot = _inline_field_body(value, "Shot 1", "overall_soundscape").strip()
    soundscape = _inline_field_body(
        value,
        "overall_soundscape",
        "non_diegetic_music",
    ).strip()
    music = _inline_field_body(value, "non_diegetic_music", None).strip()
    if not shot:
        errors.append("Shot 1 ne doit pas être vide.")
    if not soundscape:
        errors.append("overall_soundscape ne doit pas être vide.")
    if not music:
        errors.append("non_diegetic_music ne doit pas être vide ; utilisez N/A si nécessaire.")

    shot_numbers = [
        int(number)
        for number in re.findall(r"(?im)^\[?Shot\s+(\d+)\]?:", value)
    ]
    if shot_numbers != [1]:
        errors.append("Le cookbook compilé doit contenir exactement un Shot 1.")
    forbidden_fields = (*_REF2V_EDITABLE_FIELDS, *_FINAL_SECTIONS)
    for field in forbidden_fields:
        if re.search(rf"(?m)^{re.escape(field)}:$", value):
            errors.append(
                f"Le champ interne ou ancien {field}: ne doit pas apparaître dans le prompt final."
            )
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>", value):
        errors.append("Le prompt Ref2V compilé doit utiliser uniquement <Picture 1> et <Picture 2>.")
    picture_numbers = {int(item) for item in re.findall(r"<Picture\s+(\d+)>", value)}
    if picture_numbers != {1, 2}:
        errors.append("Le prompt Ref2V compilé doit référencer exactement <Picture 1> et <Picture 2>.")
    if value.count("<Picture 1>") != 2 or value.count("<Picture 2>") != 1:
        errors.append("Les labels Picture sont réservés au mapping compilé.")
    if not re.search(r"(?m)^<Picture\s+1>:", value):
        errors.append("<Picture 1> doit rester une définition autonome de la première frame.")
    if re.search(r"(?m)^<Picture\s+2>:", value):
        errors.append("<Picture 2> est une référence corporelle, pas une frame autonome.")

    timestamps: list[float] = []
    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3})\b", shot):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        if seconds >= 60:
            errors.append("Un timestamp de Shot 1 est invalide.")
        timestamps.append(minutes * 60 + seconds + milliseconds / 1000)
    if timestamps != sorted(timestamps):
        errors.append("Les timestamps de Shot 1 doivent être non décroissants.")
    if timestamps and timestamps[-1] > 15:
        errors.append("Un timestamp dépasse la durée maximale de 15 secondes.")
    if value.count("<d>") != value.count("</d>"):
        errors.append("Les balises de dialogue <d> ne sont pas équilibrées.")
    return tuple(errors)


def _ref2v_landmark_warnings(
    plan_content: str,
    prompt_content: str,
    *,
    major_only: bool = False,
) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_supervised_canonical_compiled_plan(plan_content)
    except (TypeError, ValueError):
        try:
            plan = parse_ref2v_advisory_action_plan(plan_content)
        except (TypeError, ValueError):
            try:
                plan = parse_ref2v_supervised_compiled_plan(plan_content)
            except (TypeError, ValueError):
                try:
                    plan = parse_ref2v_supervised_compiled_plan_v2(plan_content)
                except (TypeError, ValueError):
                    return ()
    landmarks_ms: list[int] = []
    if major_only:
        landmarks_ms.extend(beat.start_ms for beat in plan.beats[1:])
        landmarks_ms.append(plan.final_pose.start_ms)
        if plan.camera is not None and plan.camera.start_ms > 0:
            landmarks_ms.append(plan.camera.start_ms)
    else:
        for beat in plan.beats:
            landmarks_ms.extend((beat.start_ms, beat.end_ms))
            for substep in getattr(beat, "substeps", ()):
                landmarks_ms.extend((substep.start_ms, substep.end_ms))
        landmarks_ms.append(plan.final_pose.start_ms)
        if plan.camera is not None:
            landmarks_ms.extend((plan.camera.start_ms, plan.camera.end_ms))
        landmarks_ms.append(plan.duration_seconds * 1000)
    expected = tuple(dict.fromkeys(_format_landmark(value) for value in landmarks_ms))
    missing = tuple(value for value in expected if f"At {value}" not in prompt_content)
    warnings: list[str] = []
    if missing:
        label = "Jalons majeurs" if major_only else "Landmarks"
        warnings.append(
            f"{label} du plan absents sous la forme `At MM:SS.mmm` : "
            + ", ".join(missing)
            + ". Le prompt reste utilisable et approuvable."
        )
    if major_only:
        present = tuple(
            dict.fromkeys(
                match.group(1)
                for match in re.finditer(
                    r"\bAt\s+(\d{2}:\d{2}\.\d{3})\b",
                    prompt_content,
                )
            )
        )
        unexpected = tuple(value for value in present if value not in expected)
        if unexpected:
            warnings.append(
                "Le writer a exposé des micro-timestamps non requis : "
                + ", ".join(unexpected)
                + ". Le prompt reste utilisable, mais une rédaction par jalons majeurs est conseillée."
            )
    return tuple(warnings)


def _format_landmark(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def lint_i2v_prompt(content: str) -> tuple[str, ...]:
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt I2V est vide.",)
    value = _strip_fence(content).replace("\r\n", "\n")
    errors: list[str] = []
    if not value.startswith(_I2VA_INSTRUCTION + "\n\n"):
        errors.append(
            "Le prompt doit commencer par l’instruction I2VA officielle, suivie d’une ligne vide."
        )
    matches: dict[str, re.Match[str]] = {}
    positions: list[int] = []
    for field in _I2VA_FIELDS:
        found = list(re.finditer(rf"(?m)^{re.escape(field)}:\s*", value))
        if len(found) != 1:
            errors.append(f"Le champ {field}: doit apparaître exactement une fois.")
        else:
            matches[field] = found[0]
            positions.append(found[0].start())
    if len(positions) == len(_I2VA_FIELDS) and positions != sorted(positions):
        errors.append("Les trois champs I2VA ne sont pas dans l’ordre officiel.")
    unexpected = sorted(
        set(re.findall(r"(?m)^([a-z][a-z0-9_]*):", value))
        - set(_I2VA_FIELDS)
    )
    for field in unexpected:
        errors.append(f"Champ I2VA inattendu : {field}:")
    if len(matches) == len(_I2VA_FIELDS):
        integrated = value[
            matches[_I2VA_FIELDS[0]].end() : matches[_I2VA_FIELDS[1]].start()
        ].strip()
        soundscape = value[
            matches[_I2VA_FIELDS[1]].end() : matches[_I2VA_FIELDS[2]].start()
        ].strip()
        music = value[matches[_I2VA_FIELDS[2]].end() :].strip()
        if not integrated.startswith("[Shot 1]"):
            errors.append("integrated_multimodal_description doit commencer par [Shot 1].")
        errors.extend(_lint_i2v_shots(integrated))
        if not soundscape:
            errors.append("overall_soundscape ne doit pas être vide.")
        if not music:
            errors.append("non_diegetic_music ne doit pas être vide ; utilisez N/A si nécessaire.")
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>", value):
        errors.append("Le prompt I2VA doit utiliser seulement <Picture 1> comme label visuel.")
    picture_numbers = {int(item) for item in re.findall(r"<Picture\s+(\d+)>", value)}
    if picture_numbers != {1}:
        errors.append("Le prompt I2VA simple doit référencer uniquement <Picture 1>.")
    if value.count("<d>") != value.count("</d>"):
        errors.append("Les balises de dialogue <d> ne sont pas équilibrées.")
    return tuple(errors)


def composition_document_warnings(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    content: str,
    *,
    composition: PromptComposition | None = None,
) -> tuple[str, ...]:
    if cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT:
        if stage is CompositionStage.FINAL_PROMPT:
            return _super_fast_ref2v_prompt_warnings(content)
        return ()
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return (
                direct_ref2v_multishot_plan_warnings_v2(content)
                if cookbook.output_contract
                == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
                else direct_ref2v_multishot_plan_warnings(content)
            )
        if stage is CompositionStage.FINAL_PROMPT:
            return _h3_protocol_warnings(H3ProtocolMode.REF2VA, content)
        return ()
    if cookbook.output_contract in _I2VA_DIRECT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return direct_ref2v_action_plan_warnings_v2(content)
        if stage is CompositionStage.FINAL_PROMPT:
            return _h3_protocol_warnings(H3ProtocolMode.I2VA, content)
        return ()
    if cookbook.output_contract in _REF2V_DIRECT_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return (
                direct_ref2v_action_plan_warnings_v2(content)
                if cookbook.output_contract
                in {_REF2V_DIRECT_V2_CONTRACT, _REF2V_DIRECT_V3_CONTRACT}
                else direct_ref2v_action_plan_warnings(content)
            )
        if stage is CompositionStage.FINAL_PROMPT:
            warnings = list(_h3_protocol_warnings(H3ProtocolMode.REF2VA, content))
            timestamps = [
                int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
                for minutes, seconds, milliseconds in re.findall(
                    r"\bAt\s+(\d{2}):(\d{2})\.(\d{3})\b",
                    content,
                )
            ]
            if any(value > 15 for value in timestamps):
                warnings.append(
                    "Un timestamp dépasse 15 secondes ; vérifiez la durée acceptée "
                    "par le moteur vidéo ciblé."
                )
            return tuple(dict.fromkeys(warnings))
        return ()
    if (
        cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return _h3_protocol_warnings(H3ProtocolMode.I2VA, content)
    if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT:
        if stage is CompositionStage.BEAT_SHEET:
            warnings = list(
                ref2v_supervised_canonical_action_plan_warnings(content)
            )
            if composition is not None:
                warnings.extend(_supervised_reconciliation_warnings(composition))
            return tuple(dict.fromkeys(warnings))
        if stage is CompositionStage.FINAL_PROMPT:
            warnings = [
                error
                for error in lint_compiled_ref2v_single_shot_prompt(
                    content,
                    expected_header=_ref2v_compiled_header(cookbook),
                )
                if "15 secondes" in error
            ]
            warnings.extend(_h3_protocol_warnings(H3ProtocolMode.REF2VA, content))
            if composition is not None:
                plan = composition.beat_sheet.active_revision
                if plan is not None:
                    warnings.extend(
                        _ref2v_landmark_warnings(
                            plan.content,
                            content,
                            major_only=True,
                        )
                    )
            return tuple(dict.fromkeys(warnings))
        return ()
    if cookbook.output_contract in _REF2V_SUPERVISED_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            warnings = list(
                ref2v_supervised_action_plan_warnings_v2(content)
                if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
                else ref2v_supervised_action_plan_warnings(content)
            )
            if composition is not None:
                warnings.extend(_supervised_reconciliation_warnings(composition))
            return tuple(dict.fromkeys(warnings))
        if stage is CompositionStage.FINAL_PROMPT:
            warnings = [
                (
                    "Un timestamp dépasse 15 s. Le prompt reste utilisable ; "
                    "vérifiez la durée acceptée par le moteur vidéo ciblé."
                    if warning == "Un timestamp dépasse la durée maximale de 15 secondes."
                    else warning
                )
                for warning in lint_compiled_ref2v_single_shot_prompt(content)
            ]
            if composition is not None:
                plan = composition.beat_sheet.active_revision
                if plan is not None:
                    warnings.extend(
                        _ref2v_landmark_warnings(
                            plan.content,
                            content,
                            major_only=cookbook.reference.version == "0.9.0",
                        )
                    )
            return tuple(dict.fromkeys(warnings))
        return ()
    if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return ref2v_advisory_action_plan_warnings(content)
        if stage is CompositionStage.FINAL_PROMPT:
            warnings = [
                (
                    "Un timestamp dépasse 15 s. Le prompt reste utilisable ; "
                    "vérifiez la durée acceptée par le moteur vidéo ciblé."
                    if warning == "Un timestamp dépasse la durée maximale de 15 secondes."
                    else warning
                )
                for warning in lint_compiled_ref2v_single_shot_prompt(content)
            ]
            if composition is not None:
                plan = composition.beat_sheet.active_revision
                if plan is not None:
                    warnings.extend(
                        _ref2v_landmark_warnings(plan.content, content)
                    )
            return tuple(dict.fromkeys(warnings))
        return ()
    if (
        cookbook.output_contract == _REF2V_BOUNDED_CONTRACT
        and stage is CompositionStage.BEAT_SHEET
    ):
        return ref2v_bounded_action_plan_warnings(content)
    if (
        cookbook.output_contract == _REF2V_ELASTIC_CONTRACT
        and stage is CompositionStage.BEAT_SHEET
    ):
        return ref2v_elastic_action_plan_warnings(content)
    if (
        cookbook.output_contract == _REF2V_PLANNED_V2_CONTRACT
        and stage is CompositionStage.BEAT_SHEET
    ):
        return ref2v_action_plan_warnings_v2(content)
    if (
        cookbook.output_contract != "minimax.h3.ref2va"
        or stage is not CompositionStage.FINAL_PROMPT
    ):
        return ()
    detailed = _section_body(
        content,
        "detailed_description",
        "overall_soundscape",
    )
    word_count = len(re.findall(r"\b[\w’'-]+\b", detailed, flags=re.UNICODE))
    if not 350 <= word_count <= 500:
        return (
            f"detailed_description contient {word_count} mots ; la cible du guide est 350–500.",
        )
    return ()


def _supervised_reconciliation_warnings(
    composition: PromptComposition,
) -> tuple[str, ...]:
    document = composition.beat_sheet
    active = document.active_revision
    if (
        active is None
        or active.origin is not RevisionOrigin.REWRITE
        or active.parent_revision_id is None
        or active.instruction is None
    ):
        return ()
    try:
        instruction = json.loads(active.instruction)
    except json.JSONDecodeError:
        return ()
    if not isinstance(instruction, dict) or "decisions" not in instruction:
        return ()
    parent = next(
        (
            revision
            for revision in document.revisions
            if revision.revision_id == active.parent_revision_id
        ),
        None,
    )
    if parent is None:
        return ()
    try:
        before = _supervised_planning_payload(parent.content)
        after = _supervised_planning_payload(active.content)
    except (TypeError, ValueError):
        return ()
    if before != after:
        return ()
    return (
        "Les arbitrages ont été enregistrés, mais aucun geste, timing, état, décor "
        "ou mouvement de caméra du plan n’a changé.",
    )


def _supervised_planning_payload(content: str) -> dict[str, object]:
    try:
        plan = parse_ref2v_supervised_canonical_compiled_plan(content)
    except (TypeError, ValueError):
        try:
            plan = parse_ref2v_supervised_compiled_plan(content)
        except (TypeError, ValueError):
            plan = parse_ref2v_supervised_compiled_plan_v2(content)
    data = plan.model_dump(mode="json")
    return {
        key: data[key]
        for key in (
            "duration_seconds",
            "reference_policy",
            "scene_setup",
            "beats",
            "final_pose",
            "camera",
        )
    }


def _raise_lint(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    content: str,
) -> None:
    errors = lint_cookbook_document(cookbook, stage, _strip_fence(content))
    if errors:
        raise ValueError(" ".join(errors))


def _lint_i2v_shots(content: str) -> tuple[str, ...]:
    errors: list[str] = []
    numbers = [int(value) for value in re.findall(r"\[Shot\s+(\d+)\]", content)]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        errors.append("Les shots I2VA doivent être séquentiels, uniques et commencer à [Shot 1].")
    matches = list(re.finditer(
        r"\[Shot\s+(\d+)\](?:\s+At\s+(\d{2}):(\d{2})\.(\d{3}),)?",
        content,
    ))
    timestamps: list[float] = []
    for match in matches:
        shot = int(match.group(1))
        has_timestamp = match.group(2) is not None
        if shot == 1 and has_timestamp:
            errors.append("[Shot 1] ne doit pas avoir de timestamp.")
        if shot > 1 and not has_timestamp:
            errors.append(f"[Shot {shot}] doit commencer par `[Shot {shot}] At MM:SS.mmm,`.")
        if has_timestamp:
            seconds = int(match.group(3))
            if seconds >= 60:
                errors.append(f"Timestamp invalide pour [Shot {shot}].")
            timestamps.append(
                int(match.group(2)) * 60
                + seconds
                + int(match.group(4)) / 1000
            )
    if timestamps != sorted(set(timestamps)):
        errors.append("Les cut times I2VA doivent être strictement croissants.")
    return tuple(errors)


def _lint_six_shots(
    content: str,
    *,
    require_style_lead: bool = False,
) -> tuple[str, ...]:
    errors: list[str] = []
    raw_numbers = [int(value) for value in re.findall(r"\[Shot\s+(\d+)\]", content)]
    if raw_numbers != [1, 2, 3, 4, 5, 6]:
        errors.append("Le document doit contenir exactement [Shot 1] à [Shot 6], une fois et dans l’ordre.")
    matches = list(re.finditer(
        r"\[Shot\s+(\d+)\](?:\s+At\s+(\d{2}):(\d{2})\.(\d{3}),)?",
        content,
    ))
    timestamps: list[float] = []
    for match in matches:
        shot_number = int(match.group(1))
        has_timestamp = match.group(2) is not None
        if shot_number == 1 and has_timestamp:
            errors.append("[Shot 1] ne doit pas avoir de timestamp.")
        if shot_number > 1 and not has_timestamp:
            errors.append(
                f"[Shot {shot_number}] doit commencer par `[Shot {shot_number}] At MM:SS.mmm,`."
            )
        if has_timestamp:
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            milliseconds = int(match.group(4))
            if seconds >= 60:
                errors.append(f"Timestamp invalide pour [Shot {shot_number}].")
            timestamps.append(minutes * 60 + seconds + milliseconds / 1000)
    if timestamps != sorted(set(timestamps)):
        errors.append("Les cut times doivent être strictement croissants.")
    if timestamps and timestamps[-1] >= 15:
        errors.append("Un cut time atteint ou dépasse la durée de 15 secondes.")
    if require_style_lead:
        before_first_shot = content.split("[Shot 1]", 1)[0].strip()
        if not before_first_shot:
            errors.append("detailed_description doit établir le style avant [Shot 1].")
    return tuple(errors)


def _raise_cookbook_labels(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    content: str,
) -> None:
    allowed_picture_numbers = {
        number for _, number in composition_picture_mapping(composition)
    }
    used_picture_numbers = {
        int(value) for value in re.findall(r"<Picture\s+(\d+)>", content)
    }
    invalid_pictures = sorted(used_picture_numbers - allowed_picture_numbers)
    if invalid_pictures:
        labels = ", ".join(f"<Picture {value}>" for value in invalid_pictures)
        raise ValueError(f"unknown or unbound picture label(s): {labels}")
    allowed_subjects = {
        slot.subject_label for slot in cookbook.slots if slot.subject_label is not None
    }
    used_subjects = set(re.findall(r"<Subject\s+\d+>", content))
    invalid_subjects = sorted(used_subjects - allowed_subjects)
    if invalid_subjects:
        raise ValueError(
            "unknown subject label(s): " + ", ".join(invalid_subjects)
        )
    if stage in {CompositionStage.REFERENCE_PLAN, CompositionStage.FINAL_PROMPT}:
        definitions = _section_body(
            content,
            "subject_definitions",
            "summary" if stage is CompositionStage.FINAL_PROMPT else "retention_policy",
        )
        defined_subjects = set(re.findall(r"<Subject\s+\d+>", definitions))
        missing_subjects = sorted(allowed_subjects - defined_subjects)
        if missing_subjects:
            raise ValueError(
                "required subject definition(s) missing: " + ", ".join(missing_subjects)
            )
        definition_picture_numbers = {
            int(value) for value in re.findall(r"<Picture\s+(\d+)>", definitions)
        }
        missing_pictures = sorted(
            allowed_picture_numbers - definition_picture_numbers
        )
        if missing_pictures:
            labels = ", ".join(f"<Picture {value}>" for value in missing_pictures)
            raise ValueError(f"bound picture definition(s) missing: {labels}")
    if stage is CompositionStage.BEAT_SHEET:
        _raise_shot_appearances(
            cookbook,
            _section_body(content, "beat_sheet", None),
        )
    if stage is CompositionStage.FINAL_PROMPT:
        retention = _section_body(
            content,
            "retention_analysis",
            "detailed_description",
        )
        _raise_retention_contract(cookbook, retention)
        detailed = _section_body(
            content,
            "detailed_description",
            "overall_soundscape",
        )
        detailed_subjects = set(re.findall(r"<Subject\s+\d+>", detailed))
        missing_in_action = sorted(allowed_subjects - detailed_subjects)
        if missing_in_action:
            raise ValueError(
                "subject(s) absent from detailed_description: "
                + ", ".join(missing_in_action)
            )
        _raise_shot_appearances(cookbook, detailed)


def _raise_i2v_labels(
    composition: PromptComposition,
    stage: CompositionStage,
    content: str,
) -> None:
    mapping = composition_picture_mapping(composition)
    if len(mapping) != 1 or mapping[0][1] != 1:
        raise ValueError("I2VA simple requires exactly one local <Picture 1> binding")
    picture_numbers = {
        int(value) for value in re.findall(r"<Picture\s+(\d+)>", content)
    }
    if stage is CompositionStage.BEAT_SHEET:
        if not picture_numbers.issubset({1}):
            raise ValueError("I2VA direct plan may use only <Picture 1>")
        return
    if stage is not CompositionStage.FINAL_PROMPT:
        raise ValueError("I2VA direct exposes only beat_sheet and final_prompt")
    if picture_numbers != {1}:
        raise ValueError("I2VA simple must use exactly <Picture 1>")


def _raise_compiled_ref2v_labels(
    composition: PromptComposition,
    stage: CompositionStage,
    content: str,
    *,
    enforce_content: bool = True,
) -> None:
    mapping = composition_picture_mapping(composition)
    if len(mapping) != 2 or tuple(number for _, number in mapping) != (1, 2):
        raise ValueError("compiled Ref2V requires exactly two local picture bindings")
    if stage is CompositionStage.BEAT_SHEET:
        return
    if stage is not CompositionStage.FINAL_PROMPT:
        raise ValueError("compiled Ref2V exposes only its action plan and final_prompt")
    if not enforce_content:
        return
    picture_numbers = {
        int(value) for value in re.findall(r"<Picture\s+(\d+)>", content)
    }
    if picture_numbers != {1, 2}:
        raise ValueError("compiled Ref2V must use exactly <Picture 1> and <Picture 2>")


def _raise_retention_contract(
    cookbook: PromptCookbookPort,
    retention: str,
) -> None:
    lines = tuple(line.strip() for line in retention.splitlines() if line.strip())
    for slot in cookbook.slots:
        subject = slot.subject_label
        if subject is None:
            continue
        subject_lines = tuple(
            line
            for line in lines
            if re.match(rf"^{re.escape(subject)}(?:\s|:)", line)
        )
        if len(subject_lines) != 1:
            raise ValueError(
                f"retention_analysis must contain exactly one line for {subject}"
            )
        line = subject_lines[0]
        shots = tuple(
            int(value) for value in re.findall(r"\[Shot\s+(\d+)\]", line)
        )
        if shots != slot.required_shots:
            expected = ", ".join(f"[Shot {value}]" for value in slot.required_shots)
            raise ValueError(
                f"retention_analysis for {subject} must declare appearances in {expected}"
            )
        markers = tuple(
            marker
            for marker in _RETENTION_MARKERS
            if re.search(rf"(?<![A-Za-z0-9_]){marker}(?![A-Za-z0-9_])", line)
        )
        if len(markers) != 1:
            allowed = ", ".join(sorted(_RETENTION_MARKERS))
            raise ValueError(
                f"retention_analysis for {subject} must use exactly one marker: {allowed}"
            )


def _raise_shot_appearances(
    cookbook: PromptCookbookPort,
    content: str,
) -> None:
    matches = list(re.finditer(r"\[Shot\s+(\d+)\]", content))
    segments = {
        int(match.group(1)): content[
            match.start() : matches[index + 1].start()
            if index + 1 < len(matches)
            else len(content)
        ]
        for index, match in enumerate(matches)
    }
    for slot in cookbook.slots:
        subject = slot.subject_label
        if subject is None:
            continue
        for shot in slot.required_shots:
            if subject not in segments.get(shot, ""):
                raise ValueError(f"{subject} must appear explicitly in [Shot {shot}]")


def _approved_brief(session: PromptLabSession):
    if not session.brief_complete or session.active_brief_revision is None:
        raise ValueError("approve a current structured brief first")
    return session.active_brief_revision


def _approved_stage(
    composition: PromptComposition,
    stage: CompositionStage,
    expected: tuple[str, ...],
) -> CompositionRevision:
    document = composition.document(stage)
    if not document.is_complete(expected) or document.active_revision is None:
        raise ValueError(f"approve a current {stage.value} first")
    return document.active_revision


def _validate_bindings(
    session: PromptLabSession,
    cookbook: PromptCookbookPort,
    bindings: tuple[CookbookBinding, ...],
) -> None:
    if not isinstance(bindings, tuple):
        raise TypeError("bindings must be a tuple")
    direct_session = session.session_mode is PromptSessionMode.DIRECT_MULTIMODAL
    direct_target = cookbook.target_mode in {"ref2v_direct", "i2v_direct"}
    if direct_target != direct_session:
        raise ValueError(
            "direct video cookbooks require a direct multimodal prompt session"
        )
    by_slot = {binding.slot_id: binding for binding in bindings}
    expected_slots = {slot.slot_id for slot in cookbook.slots}
    if set(by_slot) != expected_slots or len(bindings) != len(expected_slots):
        raise ValueError("bindings must match the cookbook slots exactly")
    all_reference_ids: list[str] = []
    for slot in cookbook.slots:
        binding = by_slot[slot.slot_id]
        count = len(binding.reference_ids)
        if not slot.minimum_references <= count <= slot.maximum_references:
            raise ValueError(f"invalid reference count for slot {slot.slot_id}")
        for reference_id in binding.reference_ids:
            reference = session.reference(reference_id)
            if (
                not direct_session
                and reference.approved_revision_id != reference.active_revision_id
            ):
                raise ValueError("approve every bound visual analysis first")
            if reference.evidence_policy is not slot.evidence_policy:
                raise ValueError(
                    f"slot {slot.slot_id} requires evidence policy "
                    f"{slot.evidence_policy.value}"
                )
            unsupported_uses = sorted(
                use.value
                for use in reference.uses
                if use.value not in slot.accepted_uses
            )
            if unsupported_uses:
                raise ValueError(
                    f"slot {slot.slot_id} does not support uses "
                    + ", ".join(unsupported_uses)
                    + " in this cookbook version"
                )
            actual_uses = {use.value for use in reference.uses}
            missing_uses = sorted(set(slot.required_uses) - actual_uses)
            if missing_uses:
                raise ValueError(
                    f"slot {slot.slot_id} requires uses "
                    + ", ".join(missing_uses)
                )
            all_reference_ids.append(reference_id)
    if (
        cookbook.require_distinct_references
        and len(all_reference_ids) != len(set(all_reference_ids))
    ):
        raise ValueError("this cookbook requires distinct references for every slot")
    if cookbook.target_mode == "i2v_direct" and set(all_reference_ids) != {
        reference.reference_id for reference in session.references
    }:
        raise ValueError(
            "direct video cookbooks must bind every reference in the session"
        )


def _reference_context(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
) -> str:
    slots = {slot.slot_id: slot for slot in cookbook.slots}
    picture_numbers = dict(composition_picture_mapping(composition))
    chunks: list[str] = []
    for binding in composition.bindings:
        slot = slots[binding.slot_id]
        chunks.append(f"SLOT {binding.slot_id} — {slot.label}")
        chunks.append(f"fixed subject label: {slot.subject_label or 'none'}")
        for reference_id in binding.reference_ids:
            reference = session.reference(reference_id)
            picture_index = picture_numbers[reference_id]
            observation = project_reference_evidence(
                reference.active_revision.content,
                reference.evidence_policy,
            )
            projection = (
                ""
                if reference.evidence_policy is ReferenceEvidencePolicy.FULL
                else f" ({reference.evidence_policy.value} projection)"
            )
            chunks.extend(
                (
                    f"<Picture {picture_index}> / {reference.label}{projection}",
                    "uses: " + ", ".join(use.value for use in reference.uses),
                    "approved visual observation:",
                    observation,
                )
            )
            if (
                reference.evidence_policy is ReferenceEvidencePolicy.FULL
                and reference.interpretation_review_status.value == "approved"
                and reference.active_interpretation is not None
            ):
                chunks.extend(
                    (
                        "optional approved MiniMax interpretation:",
                        reference.active_interpretation.content,
                    )
                )
        chunks.append("")
    return "\n".join(chunks).strip()


_LEGACY_BODY_REFERENCE_SECTIONS = {
    "SUJETS VISIBLES",
    "ÂGE APPARENT ET INCERTITUDE",
    "APPARENCE ET TRAITS DISTINCTIFS",
    "VÊTEMENTS, ACCESSOIRES ET OBJETS",
    "CONTENU SENSIBLE OU ADULTE VISIBLE",
    "ÉLÉMENTS À PRÉSERVER",
    "INCERTITUDES",
}


def _action_plan_reference_context(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
) -> str:
    """Build planner evidence under each reference's immutable evidence policy."""
    slots = {slot.slot_id: slot for slot in cookbook.slots}
    picture_numbers = dict(composition_picture_mapping(composition))
    chunks: list[str] = []
    for binding in composition.bindings:
        slot = slots[binding.slot_id]
        chunks.append(f"SLOT {binding.slot_id} — {slot.label}")
        chunks.append(f"fixed role: {slot.description}")
        for reference_id in binding.reference_ids:
            reference = session.reference(reference_id)
            picture_index = picture_numbers[reference_id]
            legacy_body_projection = (
                cookbook.schema_version == 2
                and binding.slot_id == "body_reference"
                and reference.evidence_policy is ReferenceEvidencePolicy.FULL
            )
            if legacy_body_projection:
                observation = _legacy_body_reference_observation(
                    reference.active_revision.content
                )
                projection = " (legacy appearance-only projection)"
            else:
                observation = project_reference_evidence(
                    reference.active_revision.content,
                    reference.evidence_policy,
                )
                projection = (
                    ""
                    if reference.evidence_policy is ReferenceEvidencePolicy.FULL
                    else f" ({reference.evidence_policy.value} projection)"
                )
            chunks.append(f"<Picture {picture_index}> / {reference.label}{projection}")
            chunks.extend(
                (
                    "uses: " + ", ".join(use.value for use in reference.uses),
                    "approved visual observation:",
                    observation,
                )
            )
            if (
                reference.evidence_policy is ReferenceEvidencePolicy.FULL
                and not legacy_body_projection
                and reference.interpretation_review_status.value == "approved"
                and reference.active_interpretation is not None
            ):
                chunks.extend(
                    (
                        "optional approved MiniMax interpretation:",
                        reference.active_interpretation.content,
                    )
                )
        chunks.append("")
    return "\n".join(chunks).strip()


def _legacy_body_reference_observation(content: str) -> str:
    headings = list(re.finditer(r"(?m)^-\s+([^\r\n]+?)\s*$", content))
    selected: list[str] = []
    for index, heading in enumerate(headings):
        if heading.group(1).strip() not in _LEGACY_BODY_REFERENCE_SECTIONS:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        selected.append(content[heading.start() : end].strip())
    return "\n\n".join(selected) if selected else content


def _binding_source_snapshots(
    session: PromptLabSession,
    composition: PromptComposition,
) -> tuple[str, ...]:
    values: list[str] = []
    for binding in composition.bindings:
        snapshots: list[str] = []
        for reference_id in binding.reference_ids:
            reference = session.reference(reference_id)
            if session.session_mode is PromptSessionMode.DIRECT_MULTIMODAL:
                uses = ",".join(sorted(use.value for use in reference.uses))
                snapshots.append(
                    f"{reference_id}@asset:{reference.asset_id}"
                    f"[role={reference.role};uses={uses};"
                    f"evidence={reference.evidence_policy.value}]"
                )
                continue
            if reference.approved_revision_id != reference.active_revision_id:
                raise ValueError("approve every bound visual analysis first")
            uses = ",".join(sorted(use.value for use in reference.uses))
            interpretation_id = (
                reference.active_interpretation_id
                if reference.interpretation_review_status.value == "approved"
                else "none"
            )
            evidence_snapshot = (
                ""
                if reference.evidence_policy is ReferenceEvidencePolicy.FULL
                else f";evidence={reference.evidence_policy.value}"
            )
            snapshots.append(
                f"{reference_id}@{reference.active_revision_id}"
                f"[uses={uses}{evidence_snapshot};interpretation={interpretation_id}]"
            )
        values.append(f"slot:{binding.slot_id}=" + ",".join(snapshots))
    return tuple(values)


def _direct_ref2v_compiler_context(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
) -> str:
    plan = _approved_stage(
        composition,
        CompositionStage.BEAT_SHEET,
        (
            f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
            f"brief:{_approved_brief(session).revision_id}",
            *_binding_source_snapshots(session, composition),
        ),
    )
    if cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT:
        return encode_timed_camera_context(
            TimedCameraContext(
                mode="ref2v",
                header=direct_reference_header(
                    session,
                    composition_picture_mapping(composition),
                ),
                placements=_direct_timed_camera_placements(plan.content),
            )
        )
    directives = (
        direct_ref2v_camera_directives_v2(plan.content)
        if cookbook.output_contract == _REF2V_DIRECT_V2_CONTRACT
        else direct_ref2v_camera_directives(plan.content)
    )
    return encode_direct_ref2v_context(
        direct_reference_header(
            session,
            composition_picture_mapping(composition),
        ),
        directives,
    )


def _direct_i2v_compiler_context(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
) -> str:
    plan = _approved_stage(
        composition,
        CompositionStage.BEAT_SHEET,
        (
            f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
            f"brief:{_approved_brief(session).revision_id}",
            *_binding_source_snapshots(session, composition),
        ),
    )
    if cookbook.output_contract == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT:
        return encode_timed_camera_context(
            TimedCameraContext(
                mode="i2v",
                placements=_direct_timed_camera_placements(plan.content),
            )
        )
    return _encode_h3_camera_context(direct_ref2v_camera_directives_v2(plan.content))


def _direct_timed_camera_placements(
    plan_content: str,
) -> tuple[TimedCameraPlacement, ...]:
    plan = parse_direct_ref2v_action_plan_v2(plan_content)
    directives = direct_ref2v_camera_directives_v2(plan_content)
    return tuple(
        TimedCameraPlacement(directive, camera.start_ms)
        for directive, camera in zip(directives, plan.camera_directives, strict=True)
    )


def _direct_ref2v_multishot_compiler_context(
    session: PromptLabSession,
    composition: PromptComposition,
) -> str:
    plan_revision = _approved_stage(
        composition,
        CompositionStage.BEAT_SHEET,
        (
            f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
            f"brief:{_approved_brief(session).revision_id}",
            *_binding_source_snapshots(session, composition),
        ),
    )
    plan = parse_direct_ref2v_multishot_plan(plan_revision.content)
    directives = direct_ref2v_multishot_camera_directives(plan_revision.content)
    return encode_direct_ref2v_multishot_context(
        direct_reference_header(
            session,
            composition_picture_mapping(composition),
        ),
        directives,
        {directive.directive_id: int(directive.directive_id.rsplit("_", 1)[1])
         for directive in directives},
        plan.shot_starts_ms,
        plan.final_state_start_ms,
        plan.duration_ms,
    )


def _direct_ref2v_multishot_compiler_context_for(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
) -> str:
    if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_CONTRACT:
        return _direct_ref2v_multishot_compiler_context(session, composition)
    if cookbook.output_contract != _REF2V_DIRECT_MULTISHOT_V2_CONTRACT:
        raise ValueError("this cookbook does not use a multi-shot compiler context")
    plan_revision = _approved_stage(
        composition,
        CompositionStage.BEAT_SHEET,
        (
            f"cookbook:{composition.cookbook.cookbook_id}@{composition.cookbook.version}",
            f"brief:{_approved_brief(session).revision_id}",
            *_binding_source_snapshots(session, composition),
        ),
    )
    plan = parse_direct_ref2v_multishot_plan_v2(plan_revision.content)
    directives = direct_ref2v_multishot_camera_directives_v2(plan_revision.content)
    by_id = {directive.directive_id: directive for directive in directives}
    shot_cameras = tuple(
        by_id.get(f"camera_{shot_number}")
        for shot_number in range(1, len(plan.shots) + 1)
    )
    return encode_direct_ref2v_multishot_context_v2(
        direct_reference_header(
            session,
            composition_picture_mapping(composition),
        ),
        plan.shot_starts_ms,
        plan.hard_cut_times_ms,
        shot_cameras,
        plan.final_state_start_ms,
        plan.duration_ms,
    )


def _render(template: str, **values: str) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = re.findall(r"\{\{[A-Z_]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"unresolved cookbook template values: {unresolved}")
    return rendered


def _encode_h3_camera_context(
    directives: tuple[H3CameraDirective, ...],
) -> str:
    payload: list[dict[str, str]] = []
    for directive in directives:
        item = {
            "id": directive.directive_id,
            "motion": directive.motion.value,
        }
        if directive.amplitude is not None:
            item["amplitude"] = directive.amplitude.value
        if directive.speed is not None:
            item["speed"] = directive.speed.value
        if directive.target_clause:
            item["target_clause"] = directive.target_clause
        payload.append(item)
    return _H3_CAMERA_CONTEXT_MARKER + json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _is_h3_camera_context(value: str) -> bool:
    return value.startswith(_H3_CAMERA_CONTEXT_MARKER)


def _is_hidden_compiler_context(value: str) -> bool:
    return (
        _is_h3_camera_context(value)
        or is_timed_camera_context(value)
        or is_direct_ref2v_context(value)
        or is_direct_ref2v_multishot_context(value)
        or is_direct_ref2v_multishot_context_v2(value)
    )


def _decode_h3_camera_context(value: str) -> tuple[H3CameraDirective, ...]:
    if not _is_h3_camera_context(value):
        raise ValueError("canonical H3 camera context is missing")
    return parse_camera_directives(value[len(_H3_CAMERA_CONTEXT_MARKER) :])


def _decode_direct_i2v_camera_context(
    value: str,
) -> tuple[H3CameraDirective, ...]:
    if not _is_h3_camera_context(value):
        raise ValueError("direct I2VA camera context is missing")
    payload = value[len(_H3_CAMERA_CONTEXT_MARKER) :]
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("direct I2VA camera context is invalid") from error
    if raw == []:
        return ()
    return parse_camera_directives(payload)


def _rehydrate_i2v_editable_document(
    content: str,
    compiler_context: str | None,
) -> str:
    if compiler_context is None:
        raise ValueError("canonical I2VA revision is missing compiler context")
    directives = _decode_h3_camera_context(compiler_context)
    value = _strip_fence(content).replace("\r\n", "\n")
    fixed_prefix = _I2VA_INSTRUCTION + "\n\n"
    if not value.startswith(fixed_prefix):
        raise ValueError("canonical I2VA prompt is missing its fixed instruction")
    body = value[len(fixed_prefix) :]
    expected_clauses = Counter(
        compile_camera_motion(directive) for directive in directives
    )
    for clause, expected_count in expected_clauses.items():
        if body.count(clause) != expected_count:
            raise ValueError(
                "compiled camera clause occurrence count does not match "
                "the I2VA compiler context"
            )
    for directive in directives:
        clause = compile_camera_motion(directive)
        body = body.replace(
            clause,
            f"[[camera:{directive.directive_id}]]",
            1,
        )
    raw_directives = compiler_context[len(_H3_CAMERA_CONTEXT_MARKER) :]
    return f"camera_directives:\n{raw_directives}\n{body}"


def _validate_compiler_context_change(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    origin: RevisionOrigin,
    instruction: str | None,
    parent: CompositionRevision | None,
    compiler_context: str | None,
) -> None:
    if not (
        cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
        and origin is RevisionOrigin.REWRITE
    ):
        return
    if parent is None or parent.compiler_context is None:
        raise ValueError("canonical I2VA revision is missing its parent compiler context")
    if compiler_context == parent.compiler_context:
        return
    if _instruction_requests_camera_change(instruction or ""):
        return
    raise ValueError(
        "an I2VA revision may change camera directives only when the instruction "
        "explicitly mentions the camera, angle, framing, view, or shot"
    )


def _instruction_requests_camera_change(instruction: str) -> bool:
    return re.search(
        r"(?i)(?:\b(?:cam(?:e|\u00e9)ra|angle|zoom|pan|travell?ing|cadrage|vue|shot|"
        r"tilt|truck|pedestal|roll|pov|tracking|panoramique|inclinaison|suivi|"
        r"roulis|rotation)\b|contre[- ]plong(?:\u00e9e|ee|e)|"
        r"plong(?:\u00e9e|ee|e)|"
        r"point\s+de\s+vue)",
        instruction,
    ) is not None


def _h3_protocol_errors(
    mode: H3ProtocolMode,
    content: str,
    *,
    expected_directives: tuple[H3CameraDirective, ...] = (),
) -> tuple[str, ...]:
    return tuple(
        issue.message
        for issue in lint_h3_prompt(
            mode,
            content,
            expected_directives=expected_directives,
        )
        if issue.severity is H3IssueSeverity.ERROR
    )


def _h3_protocol_warnings(
    mode: H3ProtocolMode,
    content: str,
) -> tuple[str, ...]:
    return tuple(
        issue.message
        for issue in lint_h3_prompt(mode, content)
        if issue.severity is H3IssueSeverity.WARNING
    )


def _lint_super_fast_ref2v_prompt(content: str) -> tuple[str, ...]:
    """Keep the direct fast path usable without recreating a Plan parser."""

    if not isinstance(content, str) or not content.strip():
        return ("Le prompt MiniMax direct est vide.",)
    value = content.strip().replace("\r\n", "\n")
    errors: list[str] = []
    if "[[" in value or "]]" in value:
        errors.append("Un placeholder non résolu reste dans le prompt direct.")
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>", value):
        errors.append("Le prompt direct doit utiliser uniquement les labels <Picture N>.")
    if len(re.findall(r"(?m)^\[Shot 1\](?=\s|$)", value)) != 1:
        errors.append("Le prompt direct doit contenir exactement un heading [Shot 1].")
    for field in ("overall_soundscape", "non_diegetic_music"):
        if len(re.findall(rf"(?m)^{field}:[ \t]*", value)) != 1:
            errors.append(f"Le champ {field}: doit apparaître exactement une fois.")
    if value.count("<d>") != value.count("</d>"):
        errors.append("Les balises de dialogue <d> ne sont pas équilibrées.")
    picture_numbers = sorted(
        {int(item) for item in re.findall(r"<Picture\s+(\d+)>", value)}
    )
    if not picture_numbers or picture_numbers != list(
        range(1, len(picture_numbers) + 1)
    ) or len(picture_numbers) > 3:
        errors.append("Les labels Picture doivent être contigus de 1 à 3.")
    for number in picture_numbers:
        if value.count(f"<Picture {number}>") != 1:
            errors.append(f"<Picture {number}> doit apparaître exactement une fois.")
    return tuple(dict.fromkeys(errors))


def _normalize_super_fast_ref2v_body(content: str) -> str:
    """Remove common response wrappers without parsing or rewriting H3 prose."""

    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip().replace("\r\n", "\n")
    fence_count = value.count("```")
    if fence_count:
        if fence_count != 2:
            raise ValueError(
                "the direct super-fast response contains an incomplete or ambiguous Markdown fence"
            )
        match = re.search(r"```[^\n`]*\n(.*?)```", value, flags=re.DOTALL)
        if match is None:
            raise ValueError(
                "the direct super-fast response contains an invalid Markdown fence"
            )
        value = match.group(1).strip()

    leading_wrapper = re.compile(
        r"[ \t]*(?:(?:certainly|sure|of course)[!,.:—\- ]*)?"
        r"(?:here(?:'s| is)(?: the| your)?|below is(?: the)?|"
        r"(?:the[ \t]+)?(?:final|revised|updated|complete))"
        r"[^\n]*\bprompt\b[ \t]*:?[ \t]*",
        flags=re.IGNORECASE,
    )
    trailing_wrapper = re.compile(
        r"[ \t]*(?:i hope (?:this|that) helps|"
        r"(?:please[ \t]+)?let me know if[^\n]*|"
        r"(?:this (?:prompt )?is )?ready to use|done)[.!]?[ \t]*",
        flags=re.IGNORECASE,
    )
    lines = value.splitlines()
    while lines and (
        re.fullmatch(r"[ \t]*#{1,6}[ \t]+.*", lines[0])
        or leading_wrapper.fullmatch(lines[0])
    ):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    if lines and trailing_wrapper.fullmatch(lines[-1]):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    value = "\n".join(lines).strip()
    if "```" in value or re.search(r"(?m)^\s*#{1,6}\s+", value):
        raise ValueError(
            "the direct super-fast response still contains Markdown wrapper text"
        )
    return value


def _super_fast_ref2v_prompt_warnings(content: str) -> tuple[str, ...]:
    """Report likely H3 issues without blocking the experimental direct result."""

    warnings = [issue.message for issue in lint_h3_prompt(H3ProtocolMode.REF2VA, content)]
    headings = [
        int(number)
        for number in re.findall(r"(?m)^\[Shot\s+(\d+)\]", content)
    ]
    if len(headings) < 2:
        warnings.append(
            "Le mode multi-plan a produit moins de deux plans ; le prompt reste copiable."
        )
    elif headings != list(range(1, len(headings) + 1)):
        warnings.append(
            "Les numéros de plans ne sont pas contigus ; vérifiez le montage MiniMax."
        )
    if len(headings) > 6:
        warnings.append(
            "Le mode direct a produit plus de six plans ; vérifiez la densité du montage."
        )
    if re.search(r"(?m)^\[Shot 1\][ \t]+At[ \t]+\d{2}:\d{2}\.\d{3},", content):
        warnings.append(
            "[Shot 1] ne doit pas porter de timestamp H3 ; le prompt reste copiable."
        )
    for number in headings[1:]:
        if re.search(
            rf"(?m)^\[Shot {number}\] At \d{{2}}:\d{{2}}\.\d{{3}},",
            content,
        ) is None:
            warnings.append(
                f"[Shot {number}] n'a pas de timestamp H3 exact ; vérifiez la coupe."
            )
    timestamps = [
        int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
        for minutes, seconds, milliseconds in re.findall(
            r"\bAt\s+(\d{2}):(\d{2})\.(\d{3})\b",
            content,
        )
    ]
    if (
        (timestamps and timestamps[0] <= 0)
        or any(
            current <= previous
            for previous, current in zip(timestamps, timestamps[1:])
        )
    ):
        warnings.append(
            "Les timestamps de coupe ne sont pas strictement croissants."
        )
    if any(value > 15 for value in timestamps):
        warnings.append(
            "Un timestamp dépasse 15 secondes ; vérifiez la durée du moteur ciblé."
        )
    first_shot = re.search(r"(?m)^\[Shot 1\](?=\s|$)", content)
    if first_shot is not None:
        prefix_lines = [
            line.strip()
            for line in content[: first_shot.start()].splitlines()
            if line.strip() and not line.startswith("For the target video,")
        ]
        if not prefix_lines:
            warnings.append(
                "Le prompt direct ne contient pas de mise en place visible avant [Shot 1]."
            )
    soundscape = re.search(
        r"(?ms)^overall_soundscape:[ \t]*\n(.*?)(?=^non_diegetic_music:)",
        content,
    )
    music = re.search(r"(?ms)^non_diegetic_music:[ \t]*\n(.*)\Z", content)
    if soundscape is None or not soundscape.group(1).strip():
        warnings.append("Le champ overall_soundscape: est vide ou mal ordonné.")
    if music is None or not music.group(1).strip():
        warnings.append("Le champ non_diegetic_music: est vide ou mal ordonné.")
    return tuple(dict.fromkeys(warnings))


def _raise_h3_protocol(
    mode: H3ProtocolMode,
    content: str,
    *,
    expected_directives: tuple[H3CameraDirective, ...] = (),
) -> None:
    errors = _h3_protocol_errors(
        mode,
        content,
        expected_directives=expected_directives,
    )
    if errors:
        raise ValueError(" ".join(errors))


def _normalize_arbitration_decisions(
    decisions: Mapping[str, str],
    known_concern_ids: set[str],
) -> dict[str, str]:
    if not isinstance(decisions, Mapping):
        raise TypeError("arbitration decisions must be a mapping")
    if len(decisions) > 12:
        raise ValueError("at most 12 arbitration decisions are supported")
    normalized: dict[str, str] = {}
    for raw_concern_id, raw_decision in decisions.items():
        if not isinstance(raw_concern_id, str) or not raw_concern_id.strip():
            raise ValueError("arbitration concern IDs must not be empty")
        concern_id = raw_concern_id.strip()
        if concern_id not in known_concern_ids:
            raise ValueError(f"unknown continuity concern: {concern_id}")
        if not isinstance(raw_decision, str) or not raw_decision.strip():
            raise ValueError(f"decision for {concern_id} must not be empty")
        decision = raw_decision.strip()
        if len(decision) > 2000:
            raise ValueError(f"decision for {concern_id} is too long")
        normalized[concern_id] = decision
    return normalized


def _compile_content_with_context(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    prefix: str,
    result: str,
) -> tuple[str, str | None]:
    content = _compile_content(cookbook, stage, prefix, result)
    compiler_context: str | None = None
    if (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
    ):
        _, directives = compile_camera_draft(_strip_fence(result))
        compiler_context = _encode_h3_camera_context(directives)
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract in _I2VA_DIRECT_CONTRACTS
    ):
        if cookbook.output_contract == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT:
            decode_timed_camera_context(prefix)
        else:
            _decode_direct_i2v_camera_context(prefix)
        compiler_context = prefix
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
    ):
        _decode_h3_camera_context(prefix)
        compiler_context = prefix
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS
    ):
        if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT:
            decode_direct_ref2v_multishot_context_v2(prefix)
        else:
            decode_direct_ref2v_multishot_context(prefix)
        compiler_context = prefix
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract in _REF2V_DIRECT_CONTRACTS
    ):
        if cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT:
            decode_timed_camera_context(prefix)
        else:
            decode_direct_ref2v_context(prefix)
        compiler_context = prefix
    return content, compiler_context


def _compile_super_fast_ref2v_prompt(
    session: PromptLabSession,
    composition: PromptComposition,
    cookbook: PromptCookbookPort,
    result: str,
) -> str:
    if cookbook.output_contract != _SUPER_FAST_REF2V_DIRECT_CONTRACT:
        raise ValueError("the cookbook does not use the direct super-fast contract")
    header = direct_reference_header(
        session,
        composition_picture_mapping(composition),
    )
    body = normalize_dialogue_language_tags(
        _normalize_super_fast_ref2v_body(result)
    )
    exact_prefix = header + "\n\n"
    if body.startswith(exact_prefix):
        body = body[len(exact_prefix) :]
    elif re.search(r"(?i)<\s*picture\b", body):
        raise ValueError(
            "the direct super-fast model body must not repeat application-owned Picture labels"
        )
    content = f"{header}\n\n{body}"
    errors = _lint_super_fast_ref2v_prompt(content)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def _compile_content(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    prefix: str,
    result: str,
) -> str:
    body = (
        _normalize_super_fast_ref2v_body(result)
        if cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT
        else _strip_fence(result)
    )
    if (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT
    ):
        if not prefix.strip():
            raise ValueError("direct super-fast prompt header is missing")
        exact_prefix = prefix.strip() + "\n\n"
        if body.startswith(exact_prefix):
            body = body[len(exact_prefix) :]
        elif re.search(r"(?i)<\s*picture\b", body):
            raise ValueError(
                "the direct super-fast model body must not repeat application-owned Picture labels"
            )
        content = normalize_dialogue_language_tags(f"{prefix.strip()}\n\n{body}")
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
    ):
        editable, directives = compile_camera_draft(body)
        content = normalize_dialogue_language_tags(
            f"{_I2VA_INSTRUCTION}\n\n{editable}"
        )
        _raise_h3_protocol(
            H3ProtocolMode.I2VA,
            content,
            expected_directives=directives,
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _I2VA_DIRECT_CONTRACT
    ):
        directives = _decode_direct_i2v_camera_context(prefix)
        body = normalize_direct_i2v_camera_placeholders(body)
        editable = _I2VA_DIRECT_EDITABLE_CONTRACT.extract(body)
        editable = compile_camera_placeholders(
            normalize_dialogue_language_tags(editable),
            directives,
        )
        content = normalize_dialogue_language_tags(
            f"{_I2VA_INSTRUCTION}\n\n{editable}"
        )
        _raise_h3_protocol(
            H3ProtocolMode.I2VA,
            content,
            expected_directives=directives,
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT
    ):
        context = decode_timed_camera_context(prefix)
        if context.mode != "i2v":
            raise ValueError("camera-owned I2VA context has the wrong mode")
        editable = _I2VA_DIRECT_EDITABLE_CONTRACT.extract(body)
        editable = insert_camera_owned_direct_i2v_clauses(
            normalize_dialogue_language_tags(editable),
            context.placements,
        )
        content = normalize_dialogue_language_tags(
            f"{_I2VA_INSTRUCTION}\n\n{editable}"
        )
        _raise_h3_protocol(
            H3ProtocolMode.I2VA,
            content,
            expected_directives=tuple(
                item.directive for item in context.placements
            ),
        )
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract in _DIRECT_MULTIMODAL_CONTRACTS
    ):
        canonicalizer = _direct_action_plan_canonicalizer(cookbook)
        recovery_options = {
            "recover_invalid_target": (
                cookbook.invalid_camera_target_policy == "drop_with_warning"
            )
        }
        if cookbook.output_contract not in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
            recovery_options["recover_parallel_steps"] = True
        content = canonicalizer(body, **recovery_options)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
    ):
        content = retime_ref2v_supervised_canonical_action_plan(
            body,
            recover_invalid_target=(
                cookbook.invalid_camera_target_policy == "drop_with_warning"
            ),
        )
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT
    ):
        content = retime_ref2v_supervised_action_plan_v2(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_SUPERVISED_CONTRACT
    ):
        content = retime_ref2v_supervised_action_plan(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_RECOVERABLE_CONTRACT
    ):
        content = retime_ref2v_repairable_action_plan(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_ADVISORY_CONTRACT
    ):
        content = retime_ref2v_advisory_action_plan(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_BOUNDED_CONTRACT
    ):
        content = retime_ref2v_bounded_action_plan(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_ELASTIC_CONTRACT
    ):
        content = retime_ref2v_action_plan_v2(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_PLANNED_V2_CONTRACT
    ):
        content = canonical_ref2v_action_plan_v2(body)
    elif (
        stage is CompositionStage.BEAT_SHEET
        and cookbook.output_contract == _REF2V_PLANNED_CONTRACT
    ):
        content = canonical_ref2v_action_plan(body)
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
    ):
        directives = _decode_h3_camera_context(prefix)
        body = _normalize_ref2v_model_labels(body)
        editable = _REF2V_EDITABLE_CONTRACT.extract(body)
        editable = compile_camera_placeholders(
            normalize_dialogue_language_tags(editable),
            directives,
        )
        content = normalize_dialogue_language_tags(
            _compile_ref2v_single_shot(
                editable,
                compiled_header=_ref2v_compiled_header(cookbook),
            )
        )
        _raise_h3_protocol(
            H3ProtocolMode.REF2VA,
            content,
            expected_directives=directives,
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT
    ):
        context = decode_timed_camera_context(prefix)
        if context.mode != "ref2v" or context.header is None:
            raise ValueError("camera-owned Ref2V context has the wrong mode")
        editable = _REF2V_EDITABLE_CONTRACT.extract(body)
        editable = insert_camera_owned_direct_ref2v_clauses(
            normalize_dialogue_language_tags(editable),
            context.placements,
        )
        content = normalize_dialogue_language_tags(
            _compile_ref2v_single_shot(
                editable,
                compiled_header=context.header,
            )
        )
        _raise_h3_protocol(
            H3ProtocolMode.REF2VA,
            content,
            expected_directives=tuple(
                item.directive for item in context.placements
            ),
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS
    ):
        if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT:
            context_v2 = decode_direct_ref2v_multishot_context_v2(prefix)
            content = normalize_dialogue_language_tags(
                compile_direct_ref2v_multishot_document_v2(
                    normalize_dialogue_language_tags(body),
                    context_v2,
                )
            )
            directives = context_v2.directives
        else:
            context = decode_direct_ref2v_multishot_context(prefix)
            content = normalize_dialogue_language_tags(
                compile_direct_ref2v_multishot_document(
                    normalize_dialogue_language_tags(body),
                    context,
                )
            )
            directives = context.directives
        _raise_h3_protocol(
            H3ProtocolMode.REF2VA,
            content,
            expected_directives=directives,
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract in _REF2V_DIRECT_PLACEHOLDER_CONTRACTS
    ):
        header, directives = decode_direct_ref2v_context(prefix)
        body = normalize_direct_ref2v_camera_placeholders(body)
        editable = _REF2V_EDITABLE_CONTRACT.extract(body)
        editable = compile_camera_placeholders(
            normalize_dialogue_language_tags(editable),
            directives,
        )
        content = normalize_dialogue_language_tags(
            _compile_ref2v_single_shot(
                editable,
                compiled_header=header,
            )
        )
        _raise_h3_protocol(
            H3ProtocolMode.REF2VA,
            content,
            expected_directives=directives,
        )
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract
        in {_REF2V_COMPILED_CONTRACT, *_REF2V_PLANNED_CONTRACTS}
    ):
        if cookbook.output_contract in _REF2V_SOFT_FINAL_CONTRACTS:
            body = _normalize_ref2v_model_labels(body)
        editable = _REF2V_EDITABLE_CONTRACT.extract(body)
        content = _compile_ref2v_single_shot(editable)
    elif (
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == "minimax.h3.ref2va"
    ):
        _raise_sections(body, _FINAL_SECTIONS[1:])
        content = prefix + body
    else:
        content = body
    _raise_lint(cookbook, stage, content)
    return content


def _writer_action_plan(cookbook: PromptCookbookPort, content: str) -> str:
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        return (
            direct_ref2v_multishot_writer_projection_v2(content)
            if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
            else direct_ref2v_multishot_writer_projection(content)
        )
    if cookbook.output_contract in _CAMERA_OWNED_MONO_CONTRACTS:
        return direct_ref2v_writer_plan_v2_camera_owned(content)
    if cookbook.output_contract in _DIRECT_PLAN_V2_CONTRACTS:
        if cookbook.writer_projection == "compact_v1":
            return direct_ref2v_writer_plan_v2_compact(content)
        return direct_ref2v_writer_plan_v2(content)
    if cookbook.output_contract == _REF2V_DIRECT_V1_CONTRACT:
        return direct_ref2v_writer_plan(content)
    if cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT:
        return ref2v_supervised_canonical_writer_plan(content)
    if cookbook.output_contract == _REF2V_SUPERVISED_V2_CONTRACT:
        return ref2v_supervised_writer_plan_v2(content)
    if cookbook.output_contract == _REF2V_SUPERVISED_CONTRACT:
        return ref2v_supervised_writer_plan(content)
    if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
        return ref2v_advisory_writer_plan(content)
    if cookbook.output_contract == _REF2V_BOUNDED_CONTRACT:
        return ref2v_bounded_writer_plan(content)
    if cookbook.output_contract == _REF2V_ELASTIC_CONTRACT:
        return ref2v_elastic_writer_plan(content)
    return content


def _direct_action_plan_schema(cookbook: PromptCookbookPort) -> str:
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        return (
            direct_ref2v_multishot_plan_schema_v2()
            if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
            else direct_ref2v_multishot_plan_schema()
        )
    if cookbook.output_contract in _DIRECT_PLAN_V2_CONTRACTS:
        return direct_ref2v_action_plan_schema_v2()
    if cookbook.output_contract == _REF2V_DIRECT_V1_CONTRACT:
        return direct_ref2v_action_plan_schema()
    raise ValueError("this cookbook does not expose a direct action-plan schema")


def _direct_action_plan_canonicalizer(cookbook: PromptCookbookPort):
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        return (
            canonical_direct_ref2v_multishot_plan_v2
            if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
            else canonical_direct_ref2v_multishot_plan
        )
    if cookbook.output_contract in _DIRECT_PLAN_V2_CONTRACTS:
        return canonical_direct_ref2v_action_plan_v2
    if cookbook.output_contract == _REF2V_DIRECT_V1_CONTRACT:
        return canonical_direct_ref2v_action_plan
    raise ValueError("this cookbook does not expose a direct action-plan compiler")


def _parse_direct_arbitrable_plan(
    cookbook: PromptCookbookPort,
    content: str,
):
    if cookbook.output_contract in _REF2V_DIRECT_MULTISHOT_CONTRACTS:
        return (
            parse_direct_ref2v_multishot_plan_v2(content)
            if cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
            else parse_direct_ref2v_multishot_plan(content)
        )
    if cookbook.output_contract in _DIRECT_PLAN_V2_CONTRACTS:
        return parse_direct_ref2v_action_plan_v2(content)
    raise ValueError("this cookbook does not expose an arbitrable direct action plan")


def _revision_document_contract(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    *,
    compiler_context: str | None = None,
) -> RevisedDocumentContract:
    if (
        cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        if compiler_context is None:
            raise ValueError(
                "flexible multi-shot revision is missing compiler context"
            )
        context = decode_direct_ref2v_multishot_context_v2(compiler_context)
        return direct_ref2v_multishot_editable_contract_v2(context.shot_count)
    if (
        cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return MULTISHOT_EDITABLE_CONTRACT
    if (
        cookbook.output_contract in _I2VA_DIRECT_CONTRACTS
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return _I2VA_DIRECT_EDITABLE_CONTRACT
    if (
        cookbook.output_contract in _REF2V_DIRECT_CONTRACTS
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return _REF2V_EDITABLE_CONTRACT
    if (
        cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return _I2VA_CANONICAL_EDITABLE_CONTRACT
    if (
        cookbook.output_contract
        in {_REF2V_COMPILED_CONTRACT, *_REF2V_PLANNED_CONTRACTS}
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return _REF2V_EDITABLE_CONTRACT
    if cookbook.output_contract == "minimax.h3.i2va":
        markers = (
            _I2VA_INSTRUCTION,
            *(f"{field}:" for field in _I2VA_FIELDS),
        )
    else:
        sections = _STAGE_SECTIONS[stage]
        if (
            stage is CompositionStage.FINAL_PROMPT
            and CompositionStage.REFERENCE_PLAN.value in cookbook.stages
        ):
            sections = sections[1:]
        markers = tuple(f"{section}:" for section in sections)
    return RevisedDocumentContract(f"{stage.value} document", tuple(markers))


def _split_final_prompt(content: str) -> tuple[str, str]:
    match = re.search(
        r"(?m)^summary:$",
        content,
    )
    if match is None:
        raise ValueError("final prompt is missing summary")
    return content[: match.start()].rstrip() + "\n\n", content[match.start() :]


def _reference_prefix(content: str) -> str:
    match = re.search(r"(?m)^retention_policy:$", content)
    if match is None:
        raise ValueError("reference plan is missing retention_policy")
    return content[: match.start()].rstrip() + "\n\n"


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    return value


def _normalize_ref2v_model_labels(content: str) -> str:
    """Neutralize recoverable model-owned labels before adding the fixed mapping."""
    value = re.sub(
        r"(?i)(?:<Image\s+1>|@image\s*1\b)",
        "the supplied starting frame",
        content,
    )
    return re.sub(
        r"(?i)(?:<Image\s+2>|@image\s*2\b)",
        "the supplied body-appearance reference",
        value,
    )


def _raise_sections(content: str, sections: tuple[str, ...]) -> None:
    positions: list[int] = []
    for section in sections:
        match = re.search(rf"(?m)^{re.escape(section)}:$", content)
        if match is None:
            raise ValueError(f"Section manquante : {section}:")
        positions.append(match.start())
    if positions != sorted(positions):
        raise ValueError("Les sections ne sont pas dans l’ordre attendu.")


def _stage_contract(
    stage: CompositionStage,
    cookbook: PromptCookbookPort,
    *,
    compiler_context: str | None = None,
) -> str:
    if (
        cookbook.output_contract == _SUPER_FAST_REF2V_DIRECT_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return (
            "Return only the complete H3 body: an unlabeled scene setup, contiguous "
            "[Shot N] blocks, then overall_soundscape: and non_diegetic_music:. "
            "Do not repeat any Picture label or reference header."
        )
    if (
        cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_V2_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        if compiler_context is None:
            raise ValueError(
                "flexible multi-shot revision is missing compiler context"
            )
        context = decode_direct_ref2v_multishot_context_v2(compiler_context)
        fields = direct_ref2v_multishot_editable_fields_v2(context.shot_count)
        markers = ", ".join(f"{field}:" for field in fields)
        return (
            f"Return exactly {markers}, once each and in that order. Output no "
            "camera placeholder, directive ID, camera-motion prose, shot heading, "
            "cut timestamp, or reference mapping. PanelForge compiles the exact "
            f"{context.shot_count} shot headings, cuts, mapping, and canonical "
            "camera clauses from the approved plan."
        )
    if (
        cookbook.output_contract == _REF2V_DIRECT_MULTISHOT_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return (
            "Return exactly scene_setup:, shot_1:, shot_2:, shot_3:, "
            "overall_soundscape:, and non_diegetic_music:. Preserve every "
            "plan-owned [[camera:camera_N]] placeholder exactly once, at the "
            "start of its owning shot field. PanelForge compiles the dynamic "
            "reference header, all three official shot headings, hard-cut "
            "timestamps, and camera clauses."
        )
    if (
        cookbook.output_contract in _I2VA_DIRECT_CONTRACTS
        and stage is CompositionStage.FINAL_PROMPT
    ):
        if cookbook.output_contract == _I2VA_DIRECT_CAMERA_OWNED_CONTRACT:
            return (
                "Return exactly integrated_multimodal_description:, "
                "overall_soundscape:, and non_diegetic_music:. Output no camera "
                "placeholder, directive ID, or camera-motion prose. Preserve one "
                "exact At MM:SS.mmm, subject/state landmark for every distinct "
                "positive PLAN.camera_landmarks_ms value; PanelForge inserts the "
                "canonical camera clauses."
            )
        return (
            "Return exactly integrated_multimodal_description:, "
            "overall_soundscape:, and non_diegetic_music:. Preserve every "
            "plan-owned [[camera:camera_N]] placeholder exactly once. PanelForge "
            "compiles the official <Picture 1> first-frame instruction and camera "
            "clauses."
        )
    if (
        cookbook.output_contract in _REF2V_DIRECT_CONTRACTS
        and stage is CompositionStage.FINAL_PROMPT
    ):
        if cookbook.output_contract == _REF2V_DIRECT_V3_CONTRACT:
            return (
                "Return exactly scene_setup:, shot_1:, overall_soundscape:, and "
                "non_diegetic_music:. Output no camera placeholder, directive ID, "
                "or camera-motion prose. Preserve one exact At MM:SS.mmm, "
                "subject/state landmark for every distinct positive "
                "PLAN.camera_landmarks_ms value; PanelForge compiles the reference "
                "mapping, Shot 1 heading, and canonical camera clauses."
            )
        return (
            "Return exactly scene_setup:, shot_1:, overall_soundscape:, and "
            "non_diegetic_music:. Preserve every plan-owned [[camera:camera_N]] "
            "placeholder exactly once. PanelForge compiles the dynamic one-to-three "
            "picture mapping, camera clauses, and Shot 1 heading."
        )
    if (
        cookbook.output_contract == _I2VA_CANONICAL_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return (
            "Return exactly camera_directives:, integrated_multimodal_description:, "
            "overall_soundscape:, and non_diegetic_music:. camera_directives is a "
            "valid JSON array. Declare every [[camera:camera_N]] placeholder once "
            "and use each exactly once. PanelForge compiles the official first-frame "
            "instruction and camera clauses."
        )
    if (
        cookbook.output_contract == _REF2V_SUPERVISED_CANONICAL_CONTRACT
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return (
            "Return exactly scene_setup:, shot_1:, overall_soundscape:, and "
            "non_diegetic_music:. Insert [[camera:camera_1]] exactly once and do "
            "not paraphrase camera motion. PanelForge compiles the plan-owned "
            "camera clause, fixed reference mapping, and Shot 1 heading."
        )
    if (
        cookbook.output_contract
        in {_REF2V_COMPILED_CONTRACT, *_REF2V_PLANNED_CONTRACTS}
        and stage is CompositionStage.FINAL_PROMPT
    ):
        return (
            "Return exactly scene_setup:, shot_1:, overall_soundscape:, and "
            "non_diegetic_music:. PanelForge compiles the fixed <Picture 1> first-frame "
            "definition, the <Picture 2> body-reference rule, and the Shot 1 heading."
        )
    if cookbook.output_contract == "minimax.h3.i2va":
        return (
            "Preserve the exact official first-frame instruction, then output exactly "
            "integrated_multimodal_description:, overall_soundscape:, and "
            "non_diegetic_music:. Use only <Picture 1>; [Shot 1] has no timestamp."
        )
    if cookbook.output_contract == "minimax.h3.ref2va.single_shot":
        return (
            "Output exactly subject_definitions:, summary:, retention_analysis:, "
            "detailed_description:, overall_soundscape:, and non_diegetic_music:. "
            "Keep <Picture 1> as the first-frame anchor, <Picture 2> only inside "
            "the <Subject 1> definition, and use exactly one untimestamped [Shot 1]."
        )
    subjects = ", ".join(
        slot.subject_label for slot in cookbook.slots if slot.subject_label is not None
    )
    if stage is CompositionStage.REFERENCE_PLAN:
        return f"Output exactly subject_definitions:, retention_policy:. Keep the fixed subjects {subjects}; do not write the official summary or retention_analysis yet."
    if stage is CompositionStage.BEAT_SHEET:
        return "Output exactly production_settings:, continuity_rules:, beat_sheet:. Use [Shot 1] without a timestamp, then [Shot N] At MM:SS.mmm, with strictly increasing cut times below 00:15.000."
    return "Output only summary:, retention_analysis:, detailed_description:, overall_soundscape:, non_diegetic_music:. Reconcile subject appearances with the beat sheet, establish style before [Shot 1], then use [Shot N] At MM:SS.mmm, for shots 2–6 with cut times below 00:15.000."


def _compile_ref2v_single_shot(
    editable: str,
    *,
    compiled_header: str = _REF2V_COMPILED_HEADER,
) -> str:
    scene = _inline_field_body(editable, "scene_setup", "shot_1").strip()
    shot = _inline_field_body(editable, "shot_1", "overall_soundscape").strip()
    soundscape = _inline_field_body(
        editable,
        "overall_soundscape",
        "non_diegetic_music",
    ).strip()
    music = _inline_field_body(editable, "non_diegetic_music", None).strip()
    for value, name in (
        (scene, "scene_setup"),
        (shot, "shot_1"),
        (soundscape, "overall_soundscape"),
        (music, "non_diegetic_music"),
    ):
        if not value:
            raise ValueError(f"compiled Ref2V field must not be empty: {name}")
    return (
        f"{compiled_header}\n\n"
        f"{scene}\n\n"
        f"Shot 1: {shot}\n\n"
        f"overall_soundscape: {soundscape}\n\n"
        f"non_diegetic_music: {music}"
    )


def _required_prompt(value: str | None, name: str) -> str:
    if value is None:
        raise ValueError(f"cookbook is missing template {name}")
    return value


def _before_section(content: str, section: str) -> str:
    match = re.search(rf"(?m)^{re.escape(section)}:$", content)
    return content[: match.start()] if match else content


def _section_body(
    content: str,
    section: str,
    next_section: str | None,
) -> str:
    start = re.search(rf"(?m)^{re.escape(section)}:$", content)
    if start is None:
        return ""
    if next_section is None:
        return content[start.end() :]
    end = re.search(
        rf"(?m)^{re.escape(next_section)}:$",
        content[start.end() :],
    )
    if end is None:
        return content[start.end() :]
    return content[start.end() : start.end() + end.start()]


def _inline_field_body(
    content: str,
    field: str,
    next_field: str | None,
) -> str:
    start = re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content)
    if start is None:
        return ""
    if next_field is None:
        return content[start.end() :]
    end = re.search(
        rf"(?m)^{re.escape(next_field)}:[ \t]*",
        content[start.end() :],
    )
    if end is None:
        return content[start.end() :]
    return content[start.end() : start.end() + end.start()]
