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
            user_prompt = _render(
                cookbook.revision_user_prompt,
                CURRENT=editable_current,
                INSTRUCTION=instruction.strip(),
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
            operation_id=f"{stage.value}.{origin_operation}",
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
        if cookbook.output_contract == "minimax.h3.ref2va":
            _raise_cookbook_labels(
                self.sessions.get(composition.source_session_id),
                composition,
                cookbook,
                stage,
                content,
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
    if cookbook.output_contract == "minimax.h3.i2va":
        if stage is not CompositionStage.FINAL_PROMPT:
            return (f"L’étape {stage.value} n’appartient pas à ce cookbook.",)
        return lint_i2v_prompt(content)
    return (f"Contrat de sortie inconnu : {cookbook.output_contract}",)


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
) -> tuple[str, ...]:
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
        stage is CompositionStage.FINAL_PROMPT
        and cookbook.output_contract == "minimax.h3.ref2va"
    ):
        _raise_sections(body, _FINAL_SECTIONS[1:])
        content = prefix + body
    else:
        content = body
    _raise_lint(cookbook, stage, content)
    return content


def _revision_document_contract(
    cookbook: PromptCookbookPort,
    stage: CompositionStage,
) -> RevisedDocumentContract:
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
    if cookbook.output_contract == "minimax.h3.i2va":
        return (
            "Preserve the exact official first-frame instruction, then output exactly "
            "integrated_multimodal_description:, overall_soundscape:, and "
            "non_diegetic_music:. Use only <Picture 1>; [Shot 1] has no timestamp."
        )
    subjects = ", ".join(
        slot.subject_label for slot in cookbook.slots if slot.subject_label is not None
    )
    if stage is CompositionStage.REFERENCE_PLAN:
        return f"Output exactly subject_definitions:, retention_policy:. Keep the fixed subjects {subjects}; do not write the official summary or retention_analysis yet."
    if stage is CompositionStage.BEAT_SHEET:
        return "Output exactly production_settings:, continuity_rules:, beat_sheet:. Use [Shot 1] without a timestamp, then [Shot N] At MM:SS.mmm, with strictly increasing cut times below 00:15.000."
    return "Output only summary:, retention_analysis:, detailed_description:, overall_soundscape:, non_diegetic_music:. Reconcile subject appearances with the beat sheet, establish style before [Shot 1], then use [Shot N] At MM:SS.mmm, for shots 2–6 with cut times below 00:15.000."


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
