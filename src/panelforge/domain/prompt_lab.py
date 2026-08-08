"""Pure, vendor-neutral state for supervised prompt work."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class RevisionOrigin(StrEnum):
    MODEL = "model"
    MANUAL = "manual"
    REWRITE = "rewrite"


class ReferenceReview(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"


class ReferenceUse(StrEnum):
    SUBJECT = "subject"
    FIRST_FRAME = "first_frame"
    KEYFRAME = "keyframe"
    LAST_FRAME = "last_frame"
    COMPOSITION = "composition"
    ENVIRONMENT = "environment"
    STYLE = "style"


@dataclass(frozen=True, slots=True)
class AnalysisRevision:
    revision_id: str
    content: str
    origin: RevisionOrigin
    parent_revision_id: str | None = None
    instruction: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.revision_id, "revision_id")
        _require_text(self.content, "content")
        if not isinstance(self.origin, RevisionOrigin):
            raise TypeError("origin must be a RevisionOrigin")
        if self.parent_revision_id is not None:
            _require_text(self.parent_revision_id, "parent_revision_id")
            if self.parent_revision_id == self.revision_id:
                raise ValueError("a revision cannot be its own parent")
        if self.instruction is not None:
            _require_text(self.instruction, "instruction")


@dataclass(frozen=True, slots=True)
class InterpretationRevision:
    revision_id: str
    content: str
    origin: RevisionOrigin
    source_analysis_revision_id: str
    uses: tuple[ReferenceUse, ...]
    parent_revision_id: str | None = None
    instruction: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.revision_id, "revision_id"),
            (self.content, "content"),
            (self.source_analysis_revision_id, "source_analysis_revision_id"),
        ):
            _require_text(value, name)
        if not isinstance(self.origin, RevisionOrigin):
            raise TypeError("origin must be a RevisionOrigin")
        _require_uses(self.uses)
        if self.parent_revision_id is not None:
            _require_text(self.parent_revision_id, "parent_revision_id")
            if self.parent_revision_id == self.revision_id:
                raise ValueError("an interpretation cannot be its own parent")
        if self.instruction is not None:
            _require_text(self.instruction, "instruction")


@dataclass(frozen=True, slots=True)
class PromptReference:
    reference_id: str
    asset_id: str
    role: str
    label: str
    revisions: tuple[AnalysisRevision, ...] = ()
    active_revision_id: str | None = None
    approved_revision_id: str | None = None
    uses: tuple[ReferenceUse, ...] = (ReferenceUse.SUBJECT,)
    interpretations: tuple[InterpretationRevision, ...] = ()
    active_interpretation_id: str | None = None
    approved_interpretation_id: str | None = None

    @property
    def review_status(self) -> ReferenceReview:
        if self.approved_revision_id is None:
            return ReferenceReview.PENDING
        return ReferenceReview.APPROVED

    @property
    def active_revision(self) -> AnalysisRevision | None:
        if self.active_revision_id is None:
            return None
        return next(
            revision
            for revision in self.revisions
            if revision.revision_id == self.active_revision_id
        )

    @property
    def active_interpretation(self) -> InterpretationRevision | None:
        if self.active_interpretation_id is None:
            return None
        return next(
            interpretation
            for interpretation in self.interpretations
            if interpretation.revision_id == self.active_interpretation_id
        )

    @property
    def interpretation_is_stale(self) -> bool:
        active = self.active_interpretation
        if active is None:
            return False
        return (
            active.source_analysis_revision_id != self.active_revision_id
            or set(active.uses) != set(self.uses)
        )

    @property
    def interpretation_review_status(self) -> ReferenceReview:
        if self.approved_interpretation_id is None or self.interpretation_is_stale:
            return ReferenceReview.PENDING
        return ReferenceReview.APPROVED

    def add_revision(self, revision: AnalysisRevision) -> PromptReference:
        if not isinstance(revision, AnalysisRevision):
            raise TypeError("revision must be an AnalysisRevision")
        if any(item.revision_id == revision.revision_id for item in self.revisions):
            raise ValueError("revision_id already exists")
        if revision.parent_revision_id != self.active_revision_id:
            raise ValueError("revision parent must be the active revision")
        return replace(
            self,
            revisions=(*self.revisions, revision),
            active_revision_id=revision.revision_id,
            approved_revision_id=None,
            approved_interpretation_id=None,
        )

    def approve(self) -> PromptReference:
        if self.active_revision_id is None:
            raise ValueError("cannot approve a reference without an analysis")
        return replace(self, approved_revision_id=self.active_revision_id)

    def set_uses(self, uses: tuple[ReferenceUse, ...]) -> PromptReference:
        _require_uses(uses)
        if set(uses) == set(self.uses):
            return self
        return replace(
            self,
            uses=uses,
            approved_interpretation_id=None,
        )

    def add_interpretation(
        self,
        interpretation: InterpretationRevision,
    ) -> PromptReference:
        if not isinstance(interpretation, InterpretationRevision):
            raise TypeError("interpretation must be an InterpretationRevision")
        if self.approved_revision_id != self.active_revision_id:
            raise ValueError("approve the visual analysis before interpreting it")
        if interpretation.source_analysis_revision_id != self.active_revision_id:
            raise ValueError("interpretation must use the active visual analysis")
        if set(interpretation.uses) != set(self.uses):
            raise ValueError("interpretation must use the current reference roles")
        if any(
            item.revision_id == interpretation.revision_id
            for item in self.interpretations
        ):
            raise ValueError("interpretation revision_id already exists")
        if interpretation.parent_revision_id != self.active_interpretation_id:
            raise ValueError("interpretation parent must be the active interpretation")
        return replace(
            self,
            interpretations=(*self.interpretations, interpretation),
            active_interpretation_id=interpretation.revision_id,
            approved_interpretation_id=None,
        )

    def approve_interpretation(self) -> PromptReference:
        if self.active_interpretation_id is None:
            raise ValueError("cannot approve a missing interpretation")
        if self.interpretation_is_stale:
            raise ValueError("cannot approve a stale interpretation")
        return replace(
            self,
            approved_interpretation_id=self.active_interpretation_id,
        )

    def __post_init__(self) -> None:
        for value, name in (
            (self.reference_id, "reference_id"),
            (self.asset_id, "asset_id"),
            (self.role, "role"),
            (self.label, "label"),
        ):
            _require_text(value, name)
        _require_uses(self.uses)
        if not isinstance(self.revisions, tuple):
            raise TypeError("revisions must be a tuple")
        revision_ids: set[str] = set()
        for index, revision in enumerate(self.revisions):
            if not isinstance(revision, AnalysisRevision):
                raise TypeError("revisions items must be AnalysisRevision values")
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
            raise ValueError("the active revision must be the latest revision")
        if self.approved_revision_id is not None:
            if self.approved_revision_id != self.active_revision_id:
                raise ValueError("only the active revision can be approved")
        if not isinstance(self.interpretations, tuple):
            raise TypeError("interpretations must be a tuple")
        interpretation_ids: set[str] = set()
        for index, interpretation in enumerate(self.interpretations):
            if not isinstance(interpretation, InterpretationRevision):
                raise TypeError(
                    "interpretations items must be InterpretationRevision values"
                )
            if interpretation.revision_id in interpretation_ids:
                raise ValueError("interpretations must have unique IDs")
            interpretation_ids.add(interpretation.revision_id)
            expected_parent = (
                self.interpretations[index - 1].revision_id if index else None
            )
            if interpretation.parent_revision_id != expected_parent:
                raise ValueError("interpretations must form one linear history")
        if self.active_interpretation_id is None:
            if self.interpretations:
                raise ValueError(
                    "an interpretation history requires an active interpretation"
                )
        elif self.active_interpretation_id not in interpretation_ids:
            raise ValueError("active_interpretation_id is not in interpretations")
        elif self.interpretations[-1].revision_id != self.active_interpretation_id:
            raise ValueError("the active interpretation must be the latest")
        if self.approved_interpretation_id is not None:
            if self.approved_interpretation_id != self.active_interpretation_id:
                raise ValueError("only the active interpretation can be approved")
            if self.interpretation_is_stale:
                raise ValueError("a stale interpretation cannot be approved")


@dataclass(frozen=True, slots=True)
class PromptLabSession:
    session_id: str
    model_id: str
    profile_id: str
    profile_version: str
    references: tuple[PromptReference, ...]

    @property
    def analysis_complete(self) -> bool:
        return all(
            reference.review_status is ReferenceReview.APPROVED
            for reference in self.references
        )

    @property
    def interpretation_complete(self) -> bool:
        return all(
            reference.interpretation_review_status is ReferenceReview.APPROVED
            for reference in self.references
        )

    def reference(self, reference_id: str) -> PromptReference:
        _require_text(reference_id, "reference_id")
        for reference in self.references:
            if reference.reference_id == reference_id:
                return reference
        raise KeyError(reference_id)

    def update_reference(self, updated: PromptReference) -> PromptLabSession:
        if not isinstance(updated, PromptReference):
            raise TypeError("updated must be a PromptReference")
        current = self.reference(updated.reference_id)
        if current.asset_id != updated.asset_id:
            raise ValueError("a reference asset cannot be replaced in place")
        return replace(
            self,
            references=tuple(
                updated if item.reference_id == updated.reference_id else item
                for item in self.references
            ),
        )

    def __post_init__(self) -> None:
        for value, name in (
            (self.session_id, "session_id"),
            (self.model_id, "model_id"),
            (self.profile_id, "profile_id"),
            (self.profile_version, "profile_version"),
        ):
            _require_text(value, name)
        if not isinstance(self.references, tuple):
            raise TypeError("references must be a tuple")
        if not self.references:
            raise ValueError("references must not be empty")
        reference_ids: set[str] = set()
        for reference in self.references:
            if not isinstance(reference, PromptReference):
                raise TypeError("references items must be PromptReference values")
            if reference.reference_id in reference_ids:
                raise ValueError("references must have unique IDs")
            reference_ids.add(reference.reference_id)


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_uses(value: object) -> tuple[ReferenceUse, ...]:
    if not isinstance(value, tuple):
        raise TypeError("uses must be a tuple")
    if not value:
        raise ValueError("uses must not be empty")
    seen: set[ReferenceUse] = set()
    for use in value:
        if not isinstance(use, ReferenceUse):
            raise TypeError("uses items must be ReferenceUse values")
        if use in seen:
            raise ValueError("uses must not contain duplicates")
        seen.add(use)
    return value
