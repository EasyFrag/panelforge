"""Pure contracts for iterative KREA2 image editing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import math
import re

from .krea2_batch import Krea2LoraSelection, Krea2PromptLanguage
from .krea2_lab import Krea2AspectRatio, Krea2LabSettings
from .recipes import RecipeRef


_SHA256 = re.compile(r"[0-9a-f]{64}")


class Krea2EditSourceState(StrEnum):
    PENDING = "pending"
    ADVANCED = "advanced"
    PROCESSED = "processed"
    HIDDEN = "hidden"


class Krea2EditPromptStatus(StrEnum):
    IDLE = "idle"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    TRUNCATED = "truncated"


class Krea2EditAttemptStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Krea2EditMetadata:
    """Best-effort provenance recovered from an image or a batch record."""

    prompt: str | None = None
    model_name: str | None = None
    aspect_ratio: Krea2AspectRatio | None = None
    megapixels: float | None = None
    seed: int | None = None
    loras: tuple[Krea2LoraSelection, ...] = ()
    origin: str = "none"
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.prompt is not None:
            _text(self.prompt, "metadata prompt")
        if self.model_name is not None:
            _text(self.model_name, "metadata model_name")
        if self.aspect_ratio is not None and not isinstance(
            self.aspect_ratio, Krea2AspectRatio
        ):
            raise TypeError("aspect_ratio must be a Krea2AspectRatio")
        if self.megapixels is not None:
            _finite_range(self.megapixels, "metadata megapixels", 0.1, 16.0)
        if self.seed is not None and (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed < 2**64
        ):
            raise ValueError("metadata seed must be between 0 and 2^64 - 1")
        if not isinstance(self.loras, tuple) or len(self.loras) > 4:
            raise ValueError("metadata supports at most four LoRAs")
        if any(not isinstance(value, Krea2LoraSelection) for value in self.loras):
            raise TypeError("metadata loras must contain Krea2LoraSelection values")
        _text(self.origin, "metadata origin")
        if not isinstance(self.warnings, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in self.warnings
        ):
            raise TypeError("metadata warnings must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class Krea2EditSettings:
    model_name: str
    aspect_ratio: Krea2AspectRatio
    megapixels: float
    seed: int
    ref_boost: float = 2.5
    steps: int = 10
    loras: tuple[Krea2LoraSelection, ...] = ()

    def __post_init__(self) -> None:
        # Reuse the canonical KREA2 range and resolution calculation.
        Krea2LabSettings(
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            seed=self.seed,
        )
        _finite_range(self.ref_boost, "ref_boost", 0.0, 10.0)
        if isinstance(self.steps, bool) or not isinstance(self.steps, int):
            raise TypeError("steps must be an integer")
        if not 1 <= self.steps <= 100:
            raise ValueError("steps must be between 1 and 100")
        if not isinstance(self.loras, tuple) or len(self.loras) > 4:
            raise ValueError("at most four general LoRAs are supported")
        if any(not isinstance(value, Krea2LoraSelection) for value in self.loras):
            raise TypeError("loras must contain Krea2LoraSelection values")
        normalized = [value.name.replace("\\", "/").casefold() for value in self.loras]
        if len(normalized) != len(set(normalized)):
            raise ValueError("the same LoRA cannot be selected twice")

    @property
    def resolution(self) -> tuple[int, int]:
        return Krea2LabSettings(
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            seed=self.seed,
        ).resolution


@dataclass(frozen=True, slots=True)
class Krea2EditAttempt:
    attempt_id: str
    prompt: str
    settings: Krea2EditSettings
    status: Krea2EditAttemptStatus = Krea2EditAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _text(self.attempt_id, "attempt_id")
        _text(self.prompt, "attempt prompt")
        if not isinstance(self.settings, Krea2EditSettings):
            raise TypeError("settings must be Krea2EditSettings")
        if not isinstance(self.status, Krea2EditAttemptStatus):
            raise TypeError("status must be Krea2EditAttemptStatus")
        if self.execution_id is not None:
            _text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None:
            _digest(self.compiled_workflow_sha256, "compiled_workflow_sha256")
        if self.output_asset_id is not None:
            _text(self.output_asset_id, "output_asset_id")
        if self.error is not None:
            _text(self.error, "attempt error")
        self._validate_state()

    def queue(self) -> Krea2EditAttempt:
        self._require(Krea2EditAttemptStatus.CREATED, "queue")
        return replace(self, status=Krea2EditAttemptStatus.QUEUED)

    def start(self, execution_id: str, digest: str) -> Krea2EditAttempt:
        self._require(Krea2EditAttemptStatus.QUEUED, "start")
        return replace(
            self,
            status=Krea2EditAttemptStatus.RUNNING,
            execution_id=_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_digest(digest, "workflow digest"),
        )

    def succeed(self, asset_id: str) -> Krea2EditAttempt:
        if self.status not in {
            Krea2EditAttemptStatus.RUNNING,
            Krea2EditAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only an active attempt can succeed")
        return replace(
            self,
            status=Krea2EditAttemptStatus.SUCCEEDED,
            output_asset_id=_text(asset_id, "output_asset_id"),
            error=None,
        )

    def fail(self, error: str) -> Krea2EditAttempt:
        if self.status not in {
            Krea2EditAttemptStatus.CREATED,
            Krea2EditAttemptStatus.QUEUED,
            Krea2EditAttemptStatus.RUNNING,
            Krea2EditAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only a non-terminal attempt can fail")
        return replace(
            self,
            status=Krea2EditAttemptStatus.FAILED,
            error=_text(error, "attempt error"),
        )

    def cancel(self) -> Krea2EditAttempt:
        if self.status not in {
            Krea2EditAttemptStatus.CREATED,
            Krea2EditAttemptStatus.QUEUED,
            Krea2EditAttemptStatus.RUNNING,
            Krea2EditAttemptStatus.CANCEL_PENDING,
        }:
            return self
        return replace(
            self,
            status=Krea2EditAttemptStatus.CANCELLED,
            output_asset_id=None,
            error=None,
        )

    def cancel_pending(self, error: str) -> Krea2EditAttempt:
        self._require(Krea2EditAttemptStatus.RUNNING, "mark cancellation pending")
        return replace(
            self,
            status=Krea2EditAttemptStatus.CANCEL_PENDING,
            error=_text(error, "cancellation error"),
        )

    def _validate_state(self) -> None:
        active_identity = self.execution_id is not None and self.compiled_workflow_sha256 is not None
        if self.status in {Krea2EditAttemptStatus.CREATED, Krea2EditAttemptStatus.QUEUED}:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("unstarted attempt contains later-state fields")
        elif self.status is Krea2EditAttemptStatus.RUNNING:
            if not active_identity or self.output_asset_id is not None or self.error is not None:
                raise ValueError("running attempt has invalid state")
        elif self.status is Krea2EditAttemptStatus.CANCEL_PENDING:
            if not active_identity or self.output_asset_id is not None or self.error is None:
                raise ValueError("cancel-pending attempt has invalid state")
        elif self.status is Krea2EditAttemptStatus.SUCCEEDED:
            if not active_identity or self.output_asset_id is None or self.error is not None:
                raise ValueError("succeeded attempt has invalid state")
        elif self.status is Krea2EditAttemptStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed attempt requires only an error")
        elif self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled attempt cannot contain output or error")

    def _require(self, status: Krea2EditAttemptStatus, action: str) -> None:
        if self.status is not status:
            raise ValueError(f"cannot {action} a {self.status.value} attempt")


@dataclass(frozen=True, slots=True)
class Krea2EditPromptRevision:
    """One compact turn in the persisted prompt-edit exchange."""

    revision_id: str
    instruction: str
    base_prompt: str | None
    prompt: str
    model_id: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    feedback_attempt_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.revision_id, "revision_id")
        _text(self.instruction, "revision instruction")
        if self.base_prompt is not None:
            _text(self.base_prompt, "revision base_prompt")
        _text(self.prompt, "revision prompt")
        _text(self.model_id, "revision model_id")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("revision prompt_language must be Krea2PromptLanguage")
        if self.feedback_attempt_id is not None:
            _text(self.feedback_attempt_id, "revision feedback_attempt_id")


@dataclass(frozen=True, slots=True)
class Krea2EditSource:
    source_id: str
    recipe: RecipeRef
    source_asset_id: str
    filename: str
    metadata: Krea2EditMetadata
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    project_id: str | None = None
    stage_index: int = 1
    parent_source_id: str | None = None
    parent_attempt_id: str | None = None
    accepted_attempt_id: str | None = None
    project_name: str | None = None
    accepted_label: str | None = None
    export_path: str | None = None
    export_error: str | None = None
    state: Krea2EditSourceState = Krea2EditSourceState.PENDING
    source_batch_id: str | None = None
    source_batch_item_id: str | None = None
    prompt_status: Krea2EditPromptStatus = Krea2EditPromptStatus.IDLE
    instruction: str = ""
    generated_prompt: str | None = None
    raw_prompt_response: str | None = None
    prompt_model_id: str | None = None
    prompt_error: str | None = None
    revisions: tuple[Krea2EditPromptRevision, ...] = ()
    attempts: tuple[Krea2EditAttempt, ...] = ()

    def __post_init__(self) -> None:
        _text(self.source_id, "source_id")
        if self.project_id is None:
            object.__setattr__(self, "project_id", self.source_id)
        _text(self.project_id, "project_id")
        if not isinstance(self.recipe, RecipeRef):
            raise TypeError("recipe must be RecipeRef")
        _text(self.source_asset_id, "source_asset_id")
        _text(self.filename, "filename")
        if not isinstance(self.metadata, Krea2EditMetadata):
            raise TypeError("metadata must be Krea2EditMetadata")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be Krea2PromptLanguage")
        if not isinstance(self.state, Krea2EditSourceState):
            raise TypeError("state must be Krea2EditSourceState")
        if isinstance(self.stage_index, bool) or not isinstance(self.stage_index, int):
            raise TypeError("stage_index must be an integer")
        if self.stage_index < 1:
            raise ValueError("stage_index must be positive")
        for value, label in (
            (self.parent_source_id, "parent_source_id"),
            (self.parent_attempt_id, "parent_attempt_id"),
            (self.accepted_attempt_id, "accepted_attempt_id"),
            (self.project_name, "project_name"),
            (self.accepted_label, "accepted_label"),
            (self.export_path, "export_path"),
            (self.export_error, "export_error"),
        ):
            if value is not None:
                _text(value, label)
        if self.stage_index == 1:
            if self.project_id != self.source_id:
                raise ValueError("the first KREA2 edit stage must own its project")
            if self.parent_source_id is not None or self.parent_attempt_id is not None:
                raise ValueError("the first KREA2 edit stage cannot have a parent")
        elif (
            self.project_id == self.source_id
            or self.parent_source_id is None
            or self.parent_attempt_id is None
        ):
            raise ValueError("a later KREA2 edit stage requires its project and parent")
        if self.source_batch_id is not None:
            _text(self.source_batch_id, "source_batch_id")
        if self.source_batch_item_id is not None:
            _text(self.source_batch_item_id, "source_batch_item_id")
        if not isinstance(self.prompt_status, Krea2EditPromptStatus):
            raise TypeError("prompt_status must be Krea2EditPromptStatus")
        if not isinstance(self.instruction, str):
            raise TypeError("instruction must be a string")
        for value, label in (
            (self.generated_prompt, "generated_prompt"),
            (self.raw_prompt_response, "raw_prompt_response"),
            (self.prompt_model_id, "prompt_model_id"),
            (self.prompt_error, "prompt_error"),
        ):
            if value is not None:
                _text(value, label)
        if not isinstance(self.attempts, tuple) or any(
            not isinstance(value, Krea2EditAttempt) for value in self.attempts
        ):
            raise TypeError("attempts must contain Krea2EditAttempt values")
        attempt_ids = [value.attempt_id for value in self.attempts]
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("attempt ids must be unique")
        if not isinstance(self.revisions, tuple) or any(
            not isinstance(value, Krea2EditPromptRevision) for value in self.revisions
        ):
            raise TypeError("revisions must contain Krea2EditPromptRevision values")
        revision_ids = [value.revision_id for value in self.revisions]
        if len(revision_ids) != len(set(revision_ids)):
            raise ValueError("revision ids must be unique")
        succeeded = {
            value.attempt_id
            for value in self.attempts
            if value.status is Krea2EditAttemptStatus.SUCCEEDED
        }
        if self.accepted_attempt_id is not None and self.accepted_attempt_id not in succeeded:
            raise ValueError("accepted_attempt_id must reference a succeeded attempt")
        if self.state is Krea2EditSourceState.ADVANCED and self.accepted_attempt_id is None:
            raise ValueError("an advanced stage requires an accepted attempt")
        for revision in self.revisions:
            if (
                revision.feedback_attempt_id is not None
                and revision.feedback_attempt_id not in succeeded
            ):
                raise ValueError(
                    "revision feedback_attempt_id must reference a succeeded attempt"
                )

    def begin_prompt(
        self,
        instruction: str,
        model_id: str,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> Krea2EditSource:
        if self.prompt_status is Krea2EditPromptStatus.GENERATING:
            raise ValueError("a prompt is already being generated")
        selected_language = prompt_language or self.prompt_language
        if not isinstance(selected_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be Krea2PromptLanguage")
        return replace(
            self,
            prompt_language=selected_language,
            prompt_status=Krea2EditPromptStatus.GENERATING,
            instruction=_text(instruction, "instruction").strip(),
            raw_prompt_response=None,
            prompt_model_id=_text(model_id, "model_id").strip(),
            prompt_error=None,
        )

    def finish_prompt(
        self,
        raw: str,
        prompt: str,
        revision: Krea2EditPromptRevision,
    ) -> Krea2EditSource:
        if self.prompt_status is not Krea2EditPromptStatus.GENERATING:
            raise ValueError("prompt generation is not active")
        if not isinstance(revision, Krea2EditPromptRevision):
            raise TypeError("revision must be a Krea2EditPromptRevision")
        if revision.prompt.strip() != prompt.strip():
            raise ValueError("revision prompt must match the generated prompt")
        if revision.prompt_language is not self.prompt_language:
            raise ValueError("revision language must match the active prompt language")
        return replace(
            self,
            prompt_status=Krea2EditPromptStatus.READY,
            raw_prompt_response=_text(raw, "raw response"),
            generated_prompt=_text(prompt, "generated prompt").strip(),
            prompt_error=None,
            revisions=(*self.revisions, revision),
        )

    def fail_prompt(self, raw: str | None, error: str, *, truncated: bool = False) -> Krea2EditSource:
        if self.prompt_status is not Krea2EditPromptStatus.GENERATING:
            raise ValueError("prompt generation is not active")
        return replace(
            self,
            prompt_status=(Krea2EditPromptStatus.TRUNCATED if truncated else Krea2EditPromptStatus.FAILED),
            raw_prompt_response=raw.strip() if isinstance(raw, str) and raw.strip() else None,
            prompt_error=_text(error, "prompt error"),
        )

    def add_attempt(self, attempt: Krea2EditAttempt) -> Krea2EditSource:
        if not isinstance(attempt, Krea2EditAttempt):
            raise TypeError("attempt must be Krea2EditAttempt")
        if any(value.attempt_id == attempt.attempt_id for value in self.attempts):
            raise ValueError("attempt already exists")
        return replace(
            self,
            prompt_status=Krea2EditPromptStatus.READY,
            generated_prompt=attempt.prompt.strip(),
            prompt_error=None,
            attempts=(*self.attempts, attempt),
        )

    def replace_attempt(self, attempt: Krea2EditAttempt) -> Krea2EditSource:
        if not isinstance(attempt, Krea2EditAttempt):
            raise TypeError("attempt must be Krea2EditAttempt")
        found = False
        values: list[Krea2EditAttempt] = []
        for current in self.attempts:
            if current.attempt_id == attempt.attempt_id:
                values.append(attempt)
                found = True
            else:
                values.append(current)
        if not found:
            raise KeyError(attempt.attempt_id)
        return replace(self, attempts=tuple(values))

    def advance(
        self,
        attempt_id: str,
        *,
        project_name: str | None = None,
        accepted_label: str | None = None,
    ) -> Krea2EditSource:
        if self.state is not Krea2EditSourceState.PENDING:
            raise ValueError("only a pending KREA2 edit stage can advance")
        attempt = next(
            (value for value in self.attempts if value.attempt_id == attempt_id),
            None,
        )
        if attempt is None:
            raise KeyError(attempt_id)
        if attempt.status is not Krea2EditAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can advance the project")
        return replace(
            self,
            state=Krea2EditSourceState.ADVANCED,
            accepted_attempt_id=attempt.attempt_id,
            project_name=(
                _text(project_name, "project_name").strip()
                if project_name is not None
                else self.project_name
            ),
            accepted_label=(
                _text(accepted_label, "accepted_label").strip()
                if accepted_label is not None
                else self.accepted_label
            ),
        )

    def with_export(
        self,
        *,
        project_name: str,
        path: str | None,
        error: str | None,
    ) -> Krea2EditSource:
        return replace(
            self,
            project_name=_text(project_name, "project_name").strip(),
            export_path=(
                _text(path, "export_path").strip() if path is not None else None
            ),
            export_error=(
                _text(error, "export_error").strip() if error is not None else None
            ),
        )

    def with_state(self, state: Krea2EditSourceState) -> Krea2EditSource:
        if not isinstance(state, Krea2EditSourceState):
            raise TypeError("state must be Krea2EditSourceState")
        return replace(self, state=state)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _finite_range(value: object, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
    return number
