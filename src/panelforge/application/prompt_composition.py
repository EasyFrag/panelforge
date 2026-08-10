"""Supervised, cookbook-driven prompt composition use cases."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import re
from typing import Protocol
from uuid import uuid4

from panelforge.domain import (
    CompositionRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    PromptComposition,
    PromptLabSession,
    RevisionOrigin,
)

from .prompt_lab import (
    CompletionRequest,
    MultimodalGateway,
    PromptSessionStore,
    StreamEventKind,
    StreamPhase,
)
from .ref2v_action_plan import (
    canonical_ref2v_action_plan,
    canonical_ref2v_action_plan_v2,
    lint_ref2v_advisory_action_plan,
    lint_ref2v_bounded_action_plan,
    lint_ref2v_elastic_action_plan,
    lint_ref2v_action_plan,
    lint_ref2v_action_plan_v2,
    parse_ref2v_advisory_action_plan,
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
    retime_ref2v_advisory_action_plan,
    retime_ref2v_bounded_action_plan,
    retime_ref2v_action_plan_v2,
    retime_ref2v_repairable_action_plan,
)
from .revised_documents import RevisedDocumentContract


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
_I2VA_INSTRUCTION = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
_I2VA_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_REF2V_COMPILED_CONTRACT = "minimax.h3.ref2v.single_shot_compiled"
_REF2V_PLANNED_CONTRACT = "minimax.h3.ref2v.single_shot_planned"
_REF2V_PLANNED_V2_CONTRACT = "minimax.h3.ref2v.single_shot_planned_v2"
_REF2V_ELASTIC_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v1"
_REF2V_BOUNDED_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v2"
_REF2V_ADVISORY_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v3"
_REF2V_RECOVERABLE_CONTRACT = "minimax.h3.ref2v.single_shot_elastic_v4"
_REF2V_ADVISORY_CONTRACTS = {
    _REF2V_ADVISORY_CONTRACT,
    _REF2V_RECOVERABLE_CONTRACT,
}
_REF2V_PLANNED_CONTRACTS = {
    _REF2V_PLANNED_CONTRACT,
    _REF2V_PLANNED_V2_CONTRACT,
    _REF2V_ELASTIC_CONTRACT,
    _REF2V_BOUNDED_CONTRACT,
    _REF2V_ADVISORY_CONTRACT,
    _REF2V_RECOVERABLE_CONTRACT,
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
_REF2V_EDITABLE_CONTRACT = RevisedDocumentContract(
    "compiled Ref2V editable document",
    tuple(f"{field}:" for field in _REF2V_EDITABLE_FIELDS),
)
_REF2VA_CONTRACTS = {
    "minimax.h3.ref2va",
    "minimax.h3.ref2va.single_shot",
}


class CookbookSlotPort(Protocol):
    slot_id: str
    label: str
    description: str
    subject_label: str | None
    accepted_uses: tuple[str, ...]
    required_uses: tuple[str, ...]
    required_shots: tuple[int, ...]
    minimum_references: int
    maximum_references: int


class PromptCookbookPort(Protocol):
    reference: CookbookRef
    display_name: str
    description: str
    target_mode: str
    output_contract: str
    preset: str
    stages: tuple[str, ...]
    require_distinct_references: bool
    sources: tuple[str, ...]
    slots: tuple[CookbookSlotPort, ...]
    reference_plan_system_prompt: str | None
    reference_plan_user_prompt: str | None
    beat_sheet_system_prompt: str | None
    beat_sheet_user_prompt: str | None
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
    ) -> None:
        self.gateway = gateway
        self.cookbooks = cookbooks
        self.sessions = sessions
        self.compositions = compositions

    def list_cookbooks(self) -> tuple[PromptCookbookPort, ...]:
        return self.cookbooks.list()

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
        if (
            cookbook.output_contract in _REF2V_PLANNED_CONTRACTS
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
        content = _compile_content(cookbook, stage, prefix, result.content)
        return self._persist_if_current(
            session,
            composition,
            stage,
            expected,
            content,
            RevisionOrigin.MODEL,
        )

    def stream_generate(
        self,
        source_session_id: str,
        stage: CompositionStage,
    ) -> Iterator[CompositionStreamEvent]:
        composition = self.compositions.get(source_session_id)
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        if (
            cookbook.output_contract in _REF2V_PLANNED_CONTRACTS
            and stage is CompositionStage.FINAL_PROMPT
        ):
            plan_request = self._request(
                source_session_id,
                CompositionStage.BEAT_SHEET,
                instruction=None,
            )
            return self._stream_planned_final(source_session_id, plan_request)
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=None,
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
            elif event.kind is StreamEventKind.DELTA:
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
        return self._append_revision(
            composition,
            stage,
            expected,
            _strip_fence(content),
            RevisionOrigin.MANUAL,
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
        revised = _revision_document_contract(cookbook, stage).extract(
            result.content
        )
        content = _compile_content(cookbook, stage, prefix, revised)
        return self._persist_if_current(
            session,
            composition,
            stage,
            expected,
            content,
            RevisionOrigin.REWRITE,
            instruction,
        )

    def stream_revise(
        self,
        source_session_id: str,
        stage: CompositionStage,
        instruction: str,
    ) -> Iterator[CompositionStreamEvent]:
        session, composition, cookbook, expected, request, prefix = self._request(
            source_session_id,
            stage,
            instruction=instruction,
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
                cookbook.output_contract in _REF2V_PLANNED_CONTRACTS
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
                stage is CompositionStage.FINAL_PROMPT
                and CompositionStage.REFERENCE_PLAN.value in cookbook.stages
            ):
                prefix, editable_current = _split_final_prompt(current.content)
            system_prompt = _render(
                cookbook.revision_system_prompt,
                STAGE_CONTRACT=_stage_contract(stage, cookbook),
            )
            revision_values = {
                "CURRENT": editable_current,
                "INSTRUCTION": instruction.strip(),
            }
            if (
                cookbook.output_contract in _REF2V_PLANNED_CONTRACTS
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
        operation_stage = (
            "action_plan"
            if cookbook.output_contract in _REF2V_PLANNED_CONTRACTS
            and stage is CompositionStage.BEAT_SHEET
            else stage.value
        )
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature={
                CompositionStage.REFERENCE_PLAN: 0.15,
                CompositionStage.BEAT_SHEET: 0.3,
                CompositionStage.FINAL_PROMPT: 0.2,
            }[stage],
            max_tokens=32768,
            operation_id=f"{operation_stage}.{origin_operation}",
        )
        return session, composition, cookbook, expected, request, prefix

    def _generation_prompts(
        self,
        session: PromptLabSession,
        composition: PromptComposition,
        cookbook: PromptCookbookPort,
        stage: CompositionStage,
    ) -> tuple[str, str]:
        brief = _approved_brief(session)
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
                            ref2v_repairable_action_plan_schema()
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
        if cookbook.output_contract in _REF2V_PLANNED_CONTRACTS:
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
    ) -> PromptComposition:
        current_session = self.sessions.get(initial_session.session_id)
        current = self.compositions.get(initial_session.session_id)
        if current.cookbook != initial_composition.cookbook:
            raise ValueError("cookbook changed while the model was generating")
        if current.document(stage).active_revision_id != initial_composition.document(stage).active_revision_id:
            raise ValueError("this stage changed while the model was generating")
        self._validated_cookbook(current_session, current)
        if self._expected_sources(current_session, current, stage) != expected:
            raise ValueError("an upstream approval changed while the model was generating")
        return self._append_revision(
            current,
            stage,
            expected,
            content,
            origin,
            instruction,
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
    ) -> PromptComposition:
        cookbook = self.cookbooks.get(
            composition.cookbook.cookbook_id,
            composition.cookbook.version,
        )
        _raise_lint(cookbook, stage, content)
        if cookbook.output_contract in _REF2VA_CONTRACTS:
            _raise_cookbook_labels(
                self.sessions.get(composition.source_session_id),
                composition,
                cookbook,
                stage,
                content,
            )
        elif cookbook.output_contract in {
            _REF2V_COMPILED_CONTRACT,
            *_REF2V_PLANNED_CONTRACTS,
        }:
            _raise_compiled_ref2v_labels(
                composition,
                stage,
                content,
                enforce_content=(
                    cookbook.output_contract not in _REF2V_ADVISORY_CONTRACTS
                ),
            )
        elif cookbook.output_contract == "minimax.h3.i2va":
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
    ) -> Iterator[CompositionStreamEvent]:
        terminal = False
        if prefix:
            yield CompositionStreamEvent(
                kind=StreamEventKind.DELTA,
                phase=StreamPhase.GENERATING,
                text=prefix,
            )
        for event in self.gateway.stream(request):
            if event.kind is StreamEventKind.COMPLETED:
                if event.result is None:
                    raise ValueError("stream completed without a result")
                result_content = event.result.content
                if origin is RevisionOrigin.REWRITE:
                    result_content = _revision_document_contract(
                        cookbook,
                        stage,
                    ).extract(result_content)
                content = _compile_content(
                    cookbook,
                    stage,
                    prefix,
                    result_content,
                )
                composition = self._persist_if_current(
                    initial_session,
                    initial_composition,
                    stage,
                    expected,
                    content,
                    origin,
                    instruction,
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
                )
            elif event.kind is StreamEventKind.TRUNCATED:
                terminal = True
                partial = prefix + (event.result.content if event.result else event.text)
                yield CompositionStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=partial,
                    finish_reason=(event.result.finish_reason if event.result else None),
                    max_tokens=request.max_tokens,
                )
            else:
                yield CompositionStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                )
        if not terminal:
            raise ValueError("model stream ended before completion")


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
    if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
        if stage is CompositionStage.BEAT_SHEET:
            return lint_ref2v_advisory_action_plan(content)
        if stage is CompositionStage.FINAL_PROMPT:
            if not isinstance(content, str) or not content.strip():
                return ("Le prompt Ref2V compilé est vide.",)
            return ()
        return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
    if cookbook.output_contract == "minimax.h3.i2va":
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
        return lint_i2v_prompt(content)
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


def lint_compiled_ref2v_single_shot_prompt(content: str) -> tuple[str, ...]:
    """Validate the compact, code-compiled Ref2V single-shot contract."""
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt Ref2V compilé est vide.",)
    value = _strip_fence(content).replace("\r\n", "\n")
    errors: list[str] = []
    expected_start = _REF2V_COMPILED_HEADER + "\n\n"
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
) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_advisory_action_plan(plan_content)
    except (TypeError, ValueError):
        return ()
    landmarks_ms: list[int] = []
    for beat in plan.beats:
        landmarks_ms.extend((beat.start_ms, beat.end_ms))
    landmarks_ms.append(plan.final_pose.start_ms)
    if plan.camera is not None:
        landmarks_ms.extend((plan.camera.start_ms, plan.camera.end_ms))
    landmarks_ms.append(plan.duration_seconds * 1000)
    expected = tuple(dict.fromkeys(_format_landmark(value) for value in landmarks_ms))
    missing = tuple(value for value in expected if f"At {value}" not in prompt_content)
    if not missing:
        return ()
    return (
        "Landmarks du plan absents sous la forme `At MM:SS.mmm` : "
        + ", ".join(missing)
        + ". Le prompt reste utilisable et approuvable.",
    )


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
    if stage is not CompositionStage.FINAL_PROMPT:
        raise ValueError("I2VA simple exposes only final_prompt")
    mapping = composition_picture_mapping(composition)
    if len(mapping) != 1 or mapping[0][1] != 1:
        raise ValueError("I2VA simple requires exactly one local <Picture 1> binding")
    picture_numbers = {
        int(value) for value in re.findall(r"<Picture\s+(\d+)>", content)
    }
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
            if reference.approved_revision_id != reference.active_revision_id:
                raise ValueError("approve every bound visual analysis first")
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
            chunks.extend(
                (
                    f"<Picture {picture_index}> / {reference.label}",
                    "uses: " + ", ".join(use.value for use in reference.uses),
                    "approved visual observation:",
                    reference.active_revision.content,
                )
            )
            if (
                reference.interpretation_review_status.value == "approved"
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


_BODY_REFERENCE_SECTIONS = {
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
    """Build planner evidence while excluding pose/composition leakage from Picture 2."""
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
            observation = reference.active_revision.content
            if binding.slot_id == "body_reference":
                observation = _appearance_only_observation(observation)
                chunks.append(
                    f"<Picture {picture_index}> / {reference.label} "
                    "(appearance-only projection)"
                )
            else:
                chunks.append(f"<Picture {picture_index}> / {reference.label}")
            chunks.extend(
                (
                    "uses: " + ", ".join(use.value for use in reference.uses),
                    "approved visual observation:",
                    observation,
                )
            )
            if (
                binding.slot_id != "body_reference"
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


def _appearance_only_observation(content: str) -> str:
    headings = list(re.finditer(r"(?m)^-\s+([^\r\n]+?)\s*$", content))
    selected: list[str] = []
    for index, heading in enumerate(headings):
        if heading.group(1).strip() not in _BODY_REFERENCE_SECTIONS:
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
            if reference.approved_revision_id != reference.active_revision_id:
                raise ValueError("approve every bound visual analysis first")
            uses = ",".join(sorted(use.value for use in reference.uses))
            interpretation_id = (
                reference.active_interpretation_id
                if reference.interpretation_review_status.value == "approved"
                else "none"
            )
            snapshots.append(
                f"{reference_id}@{reference.active_revision_id}"
                f"[uses={uses};interpretation={interpretation_id}]"
            )
        values.append(f"slot:{binding.slot_id}=" + ",".join(snapshots))
    return tuple(values)


def _render(template: str, **values: str) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = re.findall(r"\{\{[A-Z_]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"unresolved cookbook template values: {unresolved}")
    return rendered


def _compile_content(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
    prefix: str,
    result: str,
) -> str:
    body = _strip_fence(result)
    if (
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
        and cookbook.output_contract
        in {_REF2V_COMPILED_CONTRACT, *_REF2V_PLANNED_CONTRACTS}
    ):
        if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
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
    if cookbook.output_contract in _REF2V_ADVISORY_CONTRACTS:
        return ref2v_advisory_writer_plan(content)
    if cookbook.output_contract == _REF2V_BOUNDED_CONTRACT:
        return ref2v_bounded_writer_plan(content)
    if cookbook.output_contract == _REF2V_ELASTIC_CONTRACT:
        return ref2v_elastic_writer_plan(content)
    return content


def _revision_document_contract(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
) -> RevisedDocumentContract:
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
) -> str:
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


def _compile_ref2v_single_shot(editable: str) -> str:
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
        f"{_REF2V_COMPILED_HEADER}\n\n"
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
    parse_ref2v_advisory_action_plan,
    ref2v_advisory_action_plan_warnings,
    ref2v_advisory_writer_plan,
