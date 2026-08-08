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
class PromptReference:
    reference_id: str
    asset_id: str
    role: str
    label: str
    revisions: tuple[AnalysisRevision, ...] = ()
    active_revision_id: str | None = None
    approved_revision_id: str | None = None

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
        )

    def approve(self) -> PromptReference:
        if self.active_revision_id is None:
            raise ValueError("cannot approve a reference without an analysis")
        return replace(self, approved_revision_id=self.active_revision_id)

    def __post_init__(self) -> None:
        for value, name in (
            (self.reference_id, "reference_id"),
            (self.asset_id, "asset_id"),
            (self.role, "role"),
            (self.label, "label"),
        ):
            _require_text(value, name)
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
