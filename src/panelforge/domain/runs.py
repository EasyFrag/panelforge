"""Immutable lifecycle for one recipe execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import re

from .recipes import ControlValue, PromptSnapshot, RecipeRef


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class RunStatus(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunReview(StrEnum):
    PENDING = "pending"
    KEPT = "kept"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class RunRecord:
    """Provenance and state of one immutable recipe execution attempt."""

    run_id: str
    recipe: RecipeRef
    source_asset_ids: tuple[str, ...]
    prompt: PromptSnapshot
    controls: tuple[ControlValue, ...]
    experimental_overrides: tuple[str, ...]
    status: RunStatus
    review_status: RunReview
    parent_run_id: str | None = None
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_ids: tuple[str, ...] = ()
    error: str | None = None

    @classmethod
    def create(
        cls,
        run_id: str,
        recipe: RecipeRef,
        source_asset_ids: tuple[str, ...],
        prompt: PromptSnapshot,
        compiled_workflow_sha256: str | None = None,
        controls: tuple[ControlValue, ...] = (),
        experimental_overrides: tuple[str, ...] = (),
        parent_run_id: str | None = None,
    ) -> RunRecord:
        """Create a run before upload or workflow compilation has completed."""
        return cls(
            run_id=run_id,
            recipe=recipe,
            source_asset_ids=source_asset_ids,
            prompt=prompt,
            controls=controls,
            experimental_overrides=experimental_overrides,
            status=RunStatus.CREATED,
            review_status=RunReview.PENDING,
            parent_run_id=parent_run_id,
            compiled_workflow_sha256=compiled_workflow_sha256,
        )

    def submit(
        self,
        execution_id: str,
        compiled_workflow_sha256: str,
    ) -> RunRecord:
        """Record the executor acknowledgement and exact compiled workflow."""
        self._require_status(RunStatus.CREATED, "submit")
        return replace(
            self,
            status=RunStatus.SUBMITTED,
            execution_id=execution_id,
            compiled_workflow_sha256=compiled_workflow_sha256,
        )

    def succeed(self, output_asset_ids: tuple[str, ...]) -> RunRecord:
        """Finish a submitted run with one or more generated assets."""
        self._require_status(RunStatus.SUBMITTED, "succeed")
        return replace(
            self,
            status=RunStatus.SUCCEEDED,
            output_asset_ids=output_asset_ids,
        )

    def fail(self, error: str) -> RunRecord:
        """Fail before or after submission while retaining known provenance."""
        if self.status not in (RunStatus.CREATED, RunStatus.SUBMITTED):
            raise ValueError(f"cannot fail a {self.status.value} run")
        return replace(self, status=RunStatus.FAILED, error=error)

    def review(self, decision: RunReview) -> RunRecord:
        """Keep or reject a successful candidate without mutating its run."""
        self._require_status(RunStatus.SUCCEEDED, "review")
        if not isinstance(decision, RunReview):
            raise TypeError("decision must be a RunReview")
        if decision is RunReview.PENDING:
            raise ValueError("review decision must be kept or rejected")
        return replace(self, review_status=decision)

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if not isinstance(self.recipe, RecipeRef):
            raise TypeError("recipe must be a RecipeRef")
        _require_id_tuple(self.source_asset_ids, "source_asset_ids", required=True)
        if not isinstance(self.prompt, PromptSnapshot):
            raise TypeError("prompt must be a PromptSnapshot")
        if not isinstance(self.controls, tuple):
            raise TypeError("controls must be a tuple")
        seen_controls: set[str] = set()
        for control in self.controls:
            if not isinstance(control, ControlValue):
                raise TypeError("controls items must be ControlValue values")
            if control.control_id in seen_controls:
                raise ValueError("controls must have unique control_id values")
            seen_controls.add(control.control_id)
        _require_id_tuple(
            self.experimental_overrides,
            "experimental_overrides",
            required=False,
        )
        if not isinstance(self.status, RunStatus):
            raise TypeError("status must be a RunStatus")
        if not isinstance(self.review_status, RunReview):
            raise TypeError("review_status must be a RunReview")
        if self.parent_run_id is not None:
            _require_text(self.parent_run_id, "parent_run_id")
            if self.parent_run_id == self.run_id:
                raise ValueError("a run cannot be its own parent")
        if self.execution_id is not None:
            _require_text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None:
            _require_sha256(
                self.compiled_workflow_sha256,
                "compiled_workflow_sha256",
            )
        _require_id_tuple(self.output_asset_ids, "output_asset_ids", required=False)
        if self.error is not None:
            _require_text(self.error, "error")

        self._validate_state_shape()

    def _validate_state_shape(self) -> None:
        if self.status is RunStatus.CREATED:
            if self.execution_id is not None or self.output_asset_ids or self.error:
                raise ValueError("created run contains fields from a later state")
            self._require_pending_review()
            return
        if self.status is RunStatus.SUBMITTED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("submitted run requires execution and workflow IDs")
            if self.output_asset_ids or self.error:
                raise ValueError("submitted run contains terminal fields")
            self._require_pending_review()
            return
        if self.status is RunStatus.SUCCEEDED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("succeeded run requires execution and workflow IDs")
            if not self.output_asset_ids:
                raise ValueError("succeeded run requires output assets")
            if self.error is not None:
                raise ValueError("succeeded run cannot contain an error")
            return

        if self.output_asset_ids:
            raise ValueError("failed run cannot contain output assets")
        if self.error is None:
            raise ValueError("failed run requires an error")
        self._require_pending_review()

    def _require_pending_review(self) -> None:
        if self.review_status is not RunReview.PENDING:
            raise ValueError("only succeeded runs can be reviewed")

    def _require_status(self, expected: RunStatus, action: str) -> None:
        if self.status is not expected:
            raise ValueError(f"cannot {action} a {self.status.value} run")


def _require_id_tuple(
    values: object,
    name: str,
    *,
    required: bool,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    if required and not values:
        raise ValueError(f"{name} must not be empty")
    seen: set[str] = set()
    for value in values:
        _require_text(value, f"{name} item")
        if value in seen:
            raise ValueError(f"{name} must not contain duplicates")
        seen.add(value)
    return values


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value
