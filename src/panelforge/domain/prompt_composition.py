"""Pure state for cookbook-driven prompt composition."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .prompt_lab import RevisionOrigin


class CompositionStage(StrEnum):
    REFERENCE_PLAN = "reference_plan"
    BEAT_SHEET = "beat_sheet"
    FINAL_PROMPT = "final_prompt"


@dataclass(frozen=True, slots=True)
class CookbookRef:
    cookbook_id: str
    version: str
    engine_contract_id: str
    engine_contract_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.cookbook_id, "cookbook_id"),
            (self.version, "version"),
            (self.engine_contract_id, "engine_contract_id"),
            (self.engine_contract_version, "engine_contract_version"),
        ):
            _require_text(value, name)


@dataclass(frozen=True, slots=True)
class CookbookBinding:
    slot_id: str
    reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.slot_id, "slot_id")
        if not isinstance(self.reference_ids, tuple) or not self.reference_ids:
            raise ValueError("reference_ids must be a non-empty tuple")
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("reference_ids must not contain duplicates")
        for reference_id in self.reference_ids:
            _require_text(reference_id, "reference_id")


@dataclass(frozen=True, slots=True)
class CompositionRevision:
    revision_id: str
    content: str
    origin: RevisionOrigin
    source_ids: tuple[str, ...]
    parent_revision_id: str | None = None
    instruction: str | None = None
    compiler_context: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.revision_id, "revision_id")
        _require_text(self.content, "content")
        if not isinstance(self.origin, RevisionOrigin):
            raise TypeError("origin must be a RevisionOrigin")
        if not isinstance(self.source_ids, tuple) or not self.source_ids:
            raise ValueError("source_ids must be a non-empty tuple")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source_ids must not contain duplicates")
        for source_id in self.source_ids:
            _require_text(source_id, "source_id")
        if self.parent_revision_id is not None:
            _require_text(self.parent_revision_id, "parent_revision_id")
            if self.parent_revision_id == self.revision_id:
                raise ValueError("a revision cannot be its own parent")
        if self.instruction is not None:
            _require_text(self.instruction, "instruction")
        if self.compiler_context is not None:
            _require_text(self.compiler_context, "compiler_context")


@dataclass(frozen=True, slots=True)
class StageDocument:
    stage: CompositionStage
    revisions: tuple[CompositionRevision, ...] = ()
    active_revision_id: str | None = None
    approved_revision_id: str | None = None

    @property
    def active_revision(self) -> CompositionRevision | None:
        if self.active_revision_id is None:
            return None
        return next(
            revision
            for revision in self.revisions
            if revision.revision_id == self.active_revision_id
        )

    def is_stale(self, expected_source_ids: tuple[str, ...]) -> bool:
        active = self.active_revision
        return active is not None and active.source_ids != expected_source_ids

    def is_complete(self, expected_source_ids: tuple[str, ...]) -> bool:
        return (
            self.approved_revision_id is not None
            and not self.is_stale(expected_source_ids)
        )

    def add_revision(self, revision: CompositionRevision) -> StageDocument:
        if not isinstance(revision, CompositionRevision):
            raise TypeError("revision must be a CompositionRevision")
        if revision.parent_revision_id != self.active_revision_id:
            raise ValueError("revision parent must be the active revision")
        if any(item.revision_id == revision.revision_id for item in self.revisions):
            raise ValueError("revision_id already exists")
        return replace(
            self,
            revisions=(*self.revisions, revision),
            active_revision_id=revision.revision_id,
            approved_revision_id=None,
        )

    def approve(self, expected_source_ids: tuple[str, ...]) -> StageDocument:
        if self.active_revision_id is None:
            raise ValueError("cannot approve a missing document")
        if self.is_stale(expected_source_ids):
            raise ValueError("cannot approve a stale document")
        return replace(self, approved_revision_id=self.active_revision_id)

    def __post_init__(self) -> None:
        if not isinstance(self.stage, CompositionStage):
            raise TypeError("stage must be a CompositionStage")
        if not isinstance(self.revisions, tuple):
            raise TypeError("revisions must be a tuple")
        revision_ids: set[str] = set()
        for index, revision in enumerate(self.revisions):
            if not isinstance(revision, CompositionRevision):
                raise TypeError("revisions must contain CompositionRevision values")
            if revision.revision_id in revision_ids:
                raise ValueError("revisions must have unique IDs")
            revision_ids.add(revision.revision_id)
            expected_parent = self.revisions[index - 1].revision_id if index else None
            if revision.parent_revision_id != expected_parent:
                raise ValueError("revisions must form one linear history")
        if self.active_revision_id is None:
            if self.revisions:
                raise ValueError("a revision history requires an active revision")
        elif self.active_revision_id not in revision_ids:
            raise ValueError("active_revision_id is not in revisions")
        elif self.revisions[-1].revision_id != self.active_revision_id:
            raise ValueError("the active revision must be the latest")
        if (
            self.approved_revision_id is not None
            and self.approved_revision_id != self.active_revision_id
        ):
            raise ValueError("only the active revision can be approved")


@dataclass(frozen=True, slots=True)
class PromptComposition:
    source_session_id: str
    cookbook: CookbookRef
    bindings: tuple[CookbookBinding, ...]
    reference_plan: StageDocument = StageDocument(CompositionStage.REFERENCE_PLAN)
    beat_sheet: StageDocument = StageDocument(CompositionStage.BEAT_SHEET)
    final_prompt: StageDocument = StageDocument(CompositionStage.FINAL_PROMPT)

    def document(self, stage: CompositionStage) -> StageDocument:
        if stage is CompositionStage.REFERENCE_PLAN:
            return self.reference_plan
        if stage is CompositionStage.BEAT_SHEET:
            return self.beat_sheet
        if stage is CompositionStage.FINAL_PROMPT:
            return self.final_prompt
        raise ValueError(f"unsupported composition stage: {stage}")

    def update_document(self, document: StageDocument) -> PromptComposition:
        if not isinstance(document, StageDocument):
            raise TypeError("document must be a StageDocument")
        field = {
            CompositionStage.REFERENCE_PLAN: "reference_plan",
            CompositionStage.BEAT_SHEET: "beat_sheet",
            CompositionStage.FINAL_PROMPT: "final_prompt",
        }[document.stage]
        return replace(self, **{field: document})

    def with_bindings(
        self,
        bindings: tuple[CookbookBinding, ...],
    ) -> PromptComposition:
        return replace(self, bindings=bindings)

    def __post_init__(self) -> None:
        _require_text(self.source_session_id, "source_session_id")
        if not isinstance(self.cookbook, CookbookRef):
            raise TypeError("cookbook must be a CookbookRef")
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise ValueError("bindings must be a non-empty tuple")
        slot_ids: set[str] = set()
        for binding in self.bindings:
            if not isinstance(binding, CookbookBinding):
                raise TypeError("bindings must contain CookbookBinding values")
            if binding.slot_id in slot_ids:
                raise ValueError("bindings must have unique slot IDs")
            slot_ids.add(binding.slot_id)
        for document, stage in (
            (self.reference_plan, CompositionStage.REFERENCE_PLAN),
            (self.beat_sheet, CompositionStage.BEAT_SHEET),
            (self.final_prompt, CompositionStage.FINAL_PROMPT),
        ):
            if not isinstance(document, StageDocument) or document.stage is not stage:
                raise ValueError(f"invalid document for stage {stage.value}")


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value
