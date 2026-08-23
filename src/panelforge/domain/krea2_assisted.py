"""Pure contracts for conversational KREA2 image creation projects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import re

from .krea2_batch import Krea2BatchSettings, Krea2PromptLanguage


_SHA256 = re.compile(r"[0-9a-f]{64}")


class Krea2AssistedTurnMode(StrEnum):
    CREATION = "creation"
    RECIPE = "recipe"


class Krea2AssistedTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Krea2AssistedAttemptStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Krea2AssistedTurn:
    turn_id: str
    mode: Krea2AssistedTurnMode
    role: Krea2AssistedTurnRole
    content: str
    guidance_asset_id: str | None = None
    guidance_filename: str | None = None
    questions: tuple[str, ...] = ()
    prompt: str | None = None
    recommendations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.turn_id, "turn_id")
        if not isinstance(self.mode, Krea2AssistedTurnMode):
            raise TypeError("mode must be a Krea2AssistedTurnMode")
        if not isinstance(self.role, Krea2AssistedTurnRole):
            raise TypeError("role must be a Krea2AssistedTurnRole")
        _text(self.content, "turn content")
        if self.guidance_asset_id is not None:
            _text(self.guidance_asset_id, "guidance_asset_id")
        if self.guidance_filename is not None:
            _text(self.guidance_filename, "guidance_filename")
        if self.guidance_filename is not None and self.guidance_asset_id is None:
            raise ValueError("guidance_filename requires guidance_asset_id")
        if self.role is Krea2AssistedTurnRole.ASSISTANT and self.guidance_asset_id is not None:
            raise ValueError("only user turns can attach a guidance image")
        _strings(self.questions, "questions", maximum=3)
        _strings(self.recommendations, "recommendations", maximum=8)
        if self.prompt is not None:
            _text(self.prompt, "prompt")


@dataclass(frozen=True, slots=True)
class Krea2AssistedAttempt:
    attempt_id: str
    index: int
    prompt: str
    settings: Krea2BatchSettings
    seed: int
    status: Krea2AssistedAttemptStatus = Krea2AssistedAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None
    accepted: bool = False

    def __post_init__(self) -> None:
        _text(self.attempt_id, "attempt_id")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("attempt index must be positive")
        _text(self.prompt, "prompt")
        if not isinstance(self.settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed <= 2**50:
            raise ValueError("seed must be between 0 and 2^50")
        if not isinstance(self.status, Krea2AssistedAttemptStatus):
            raise TypeError("status must be Krea2AssistedAttemptStatus")
        if self.execution_id is not None:
            _text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None and _SHA256.fullmatch(self.compiled_workflow_sha256) is None:
            raise ValueError("compiled_workflow_sha256 must be a lowercase SHA-256")
        if self.output_asset_id is not None:
            _text(self.output_asset_id, "output_asset_id")
        if self.error is not None:
            _text(self.error, "error")
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a boolean")
        self._validate_state()

    def queue(self) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.CREATED:
            raise ValueError("only a created attempt can be queued")
        return replace(self, status=Krea2AssistedAttemptStatus.QUEUED)

    def start(self, execution_id: str, digest: str) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.QUEUED:
            raise ValueError("only a queued attempt can start")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.RUNNING,
            execution_id=_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_digest(digest),
        )

    def succeed(self, asset_id: str) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only an active attempt can succeed")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.SUCCEEDED,
            output_asset_id=_text(asset_id, "asset_id"),
            error=None,
        )

    def fail(self, error: str) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.CREATED,
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only a non-terminal attempt can fail")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.FAILED,
            output_asset_id=None,
            error=_text(error, "error"),
        )

    def cancel_pending(self, error: str | None = None) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.RUNNING,
        }:
            raise ValueError("only a queued or running attempt can await cancellation")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.CANCEL_PENDING,
            error=error.strip() if isinstance(error, str) and error.strip() else None,
        )

    def cancel(self) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.CREATED,
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            return self
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.CANCELLED,
            output_asset_id=None,
            error=None,
        )

    def accept(self) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can be accepted")
        return replace(self, accepted=True)

    def _validate_state(self) -> None:
        if self.status is Krea2AssistedAttemptStatus.CREATED:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("created attempt contains execution fields")
        elif self.status is Krea2AssistedAttemptStatus.QUEUED:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("queued attempt contains execution fields")
        elif self.status in {Krea2AssistedAttemptStatus.RUNNING, Krea2AssistedAttemptStatus.CANCEL_PENDING}:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("active attempt requires execution fields")
            if self.output_asset_id is not None:
                raise ValueError("active attempt cannot contain output")
        elif self.status is Krea2AssistedAttemptStatus.SUCCEEDED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None or self.output_asset_id is None or self.error is not None:
                raise ValueError("succeeded attempt is incomplete")
        elif self.status is Krea2AssistedAttemptStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed attempt requires only an error")
        elif self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled attempt cannot contain output or error")
        if self.accepted and self.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can be accepted")


@dataclass(frozen=True, slots=True)
class Krea2AssistedRecipeDraft:
    recipe_id: str
    display_name: str
    description: str
    identity: str
    invariants: tuple[str, ...]
    variables: tuple[str, ...]
    risks: tuple[str, ...]
    canonical_prompt: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH

    def __post_init__(self) -> None:
        for value, label in (
            (self.recipe_id, "recipe_id"),
            (self.display_name, "display_name"),
            (self.description, "description"),
            (self.identity, "identity"),
            (self.canonical_prompt, "canonical_prompt"),
        ):
            _text(value, label)
        if re.fullmatch(r"[a-z0-9][a-z0-9_]{1,63}", self.recipe_id) is None:
            raise ValueError("recipe_id must use lowercase letters, digits and underscores")
        _strings(self.invariants, "invariants", minimum=1, maximum=24)
        _strings(self.variables, "variables", minimum=1, maximum=24)
        _strings(self.risks, "risks", minimum=1, maximum=24)
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be a Krea2PromptLanguage")


@dataclass(frozen=True, slots=True)
class Krea2AssistedProject:
    project_id: str
    name: str
    intention: str
    model_id: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    reference_asset_id: str | None = None
    reference_filename: str | None = None
    turns: tuple[Krea2AssistedTurn, ...] = ()
    current_prompt: str | None = None
    attempts: tuple[Krea2AssistedAttempt, ...] = ()
    feedback_attempt_id: str | None = None
    accepted_attempt_id: str | None = None
    recipe_draft: Krea2AssistedRecipeDraft | None = None
    published_recipe_id: str | None = None
    published_recipe_version: str | None = None
    export_path: str | None = None
    export_error: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, label in (
            (self.project_id, "project_id"),
            (self.name, "name"),
            (self.intention, "intention"),
            (self.model_id, "model_id"),
        ):
            _text(value, label)
        if self.reference_asset_id is not None:
            _text(self.reference_asset_id, "reference_asset_id")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be a Krea2PromptLanguage")
        if self.reference_filename is not None:
            _text(self.reference_filename, "reference_filename")
        if not isinstance(self.turns, tuple) or any(not isinstance(value, Krea2AssistedTurn) for value in self.turns):
            raise TypeError("turns must contain Krea2AssistedTurn values")
        if not isinstance(self.attempts, tuple) or any(not isinstance(value, Krea2AssistedAttempt) for value in self.attempts):
            raise TypeError("attempts must contain Krea2AssistedAttempt values")
        if len({value.turn_id for value in self.turns}) != len(self.turns):
            raise ValueError("turn IDs must be unique")
        if len({value.attempt_id for value in self.attempts}) != len(self.attempts):
            raise ValueError("attempt IDs must be unique")
        if self.current_prompt is not None:
            _text(self.current_prompt, "current_prompt")
        attempt_ids = {value.attempt_id for value in self.attempts}
        if self.feedback_attempt_id is not None and self.feedback_attempt_id not in attempt_ids:
            raise ValueError("feedback_attempt_id does not exist")
        if self.accepted_attempt_id is not None and self.accepted_attempt_id not in attempt_ids:
            raise ValueError("accepted_attempt_id does not exist")
        if (self.published_recipe_id is None) != (self.published_recipe_version is None):
            raise ValueError("published recipe identity is incomplete")
        if self.export_error is not None:
            _text(self.export_error, "export_error")
        _strings(self.warnings, "warnings", maximum=64)

    def add_turns(
        self,
        user: Krea2AssistedTurn,
        assistant: Krea2AssistedTurn,
    ) -> Krea2AssistedProject:
        if user.role is not Krea2AssistedTurnRole.USER or assistant.role is not Krea2AssistedTurnRole.ASSISTANT:
            raise ValueError("a conversation exchange requires user then assistant")
        if user.mode is not assistant.mode:
            raise ValueError("conversation exchange modes differ")
        return replace(
            self,
            turns=(*self.turns, user, assistant),
            current_prompt=(assistant.prompt or self.current_prompt),
        )

    def add_attempt(self, attempt: Krea2AssistedAttempt) -> Krea2AssistedProject:
        if any(value.attempt_id == attempt.attempt_id for value in self.attempts):
            raise ValueError("attempt already exists")
        return replace(self, attempts=(*self.attempts, attempt))

    def replace_attempt(self, attempt: Krea2AssistedAttempt) -> Krea2AssistedProject:
        if sum(value.attempt_id == attempt.attempt_id for value in self.attempts) != 1:
            raise KeyError(attempt.attempt_id)
        return replace(
            self,
            attempts=tuple(attempt if value.attempt_id == attempt.attempt_id else value for value in self.attempts),
        )

    def use_feedback(self, attempt_id: str | None) -> Krea2AssistedProject:
        if attempt_id is None:
            return replace(self, feedback_attempt_id=None)
        attempt = self.attempt(attempt_id)
        if attempt.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("feedback must reference a succeeded attempt")
        return replace(self, feedback_attempt_id=attempt_id)

    def accept_attempt(self, attempt_id: str) -> Krea2AssistedProject:
        attempt = self.attempt(attempt_id).accept()
        return replace(
            self.replace_attempt(attempt),
            accepted_attempt_id=attempt_id,
            current_prompt=attempt.prompt,
            feedback_attempt_id=attempt_id,
            attempts=tuple(
                replace(value, accepted=(value.attempt_id == attempt_id))
                for value in self.replace_attempt(attempt).attempts
            ),
        )

    def with_recipe_draft(self, draft: Krea2AssistedRecipeDraft) -> Krea2AssistedProject:
        return replace(self, recipe_draft=draft)

    def with_prompt_language(self, language: Krea2PromptLanguage) -> Krea2AssistedProject:
        if not isinstance(language, Krea2PromptLanguage):
            raise TypeError("language must be a Krea2PromptLanguage")
        return replace(self, prompt_language=language)

    def with_published_recipe(self, recipe_id: str, version: str) -> Krea2AssistedProject:
        return replace(
            self,
            published_recipe_id=_text(recipe_id, "recipe_id"),
            published_recipe_version=_text(version, "version"),
        )

    def with_export(self, path: str | None, error: str | None) -> Krea2AssistedProject:
        return replace(self, export_path=path, export_error=error)

    def attempt(self, attempt_id: str) -> Krea2AssistedAttempt:
        for value in self.attempts:
            if value.attempt_id == attempt_id:
                return value
        raise KeyError(attempt_id)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _strings(
    values: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if not minimum <= len(values) <= maximum:
        raise ValueError(f"{label} must contain between {minimum} and {maximum} values")
    for value in values:
        _text(value, label)
    return values


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("digest must be a lowercase SHA-256")
    return value
