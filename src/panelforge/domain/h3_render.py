"""Pure state for conversational H3 Base video rendering projects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import re

from .video_lab import VideoAspectRatio, VideoLabSettings


_SHA256 = re.compile(r"[0-9a-f]{64}")


class H3RenderInputMode(StrEnum):
    T2VA = "t2va"
    I2VA = "i2va"
    L2VA = "l2va"
    FL2VA = "fl2va"
    REF2VA = "ref2va"


class H3RenderTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class H3RenderRevisionVersion(StrEnum):
    LEGACY = "0.1.0"
    CAMERA_LOCKED = "0.2.0"


class H3RenderAttemptStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class H3RenderTurn:
    turn_id: str
    role: H3RenderTurnRole
    content: str
    prompt: str | None = None
    questions: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    revision_version: H3RenderRevisionVersion | None = None

    def __post_init__(self) -> None:
        _text(self.turn_id, "turn_id")
        if not isinstance(self.role, H3RenderTurnRole):
            raise TypeError("role must be an H3RenderTurnRole")
        _text(self.content, "turn content")
        if self.prompt is not None:
            _text(self.prompt, "prompt")
        _strings(self.questions, "questions", maximum=3)
        _strings(self.recommendations, "recommendations", maximum=8)
        if self.revision_version is not None and not isinstance(
            self.revision_version,
            H3RenderRevisionVersion,
        ):
            raise TypeError("revision_version must be an H3RenderRevisionVersion or None")
        if self.role is H3RenderTurnRole.USER and self.revision_version is not None:
            raise ValueError("user turns cannot own a revision version")


@dataclass(frozen=True, slots=True)
class H3RenderKeyframe:
    asset_id: str
    timestamp_ms: int
    label: str

    def __post_init__(self) -> None:
        _text(self.asset_id, "asset_id")
        if (
            isinstance(self.timestamp_ms, bool)
            or not isinstance(self.timestamp_ms, int)
            or self.timestamp_ms < 0
        ):
            raise ValueError("timestamp_ms must be a non-negative integer")
        _text(self.label, "keyframe label")


@dataclass(frozen=True, slots=True)
class H3RenderAttempt:
    attempt_id: str
    index: int
    prompt: str
    effective_prompt: str
    settings: VideoLabSettings
    music_enabled: bool
    keyframe_timestamps_ms: tuple[int, ...]
    status: H3RenderAttemptStatus = H3RenderAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    keyframes: tuple[H3RenderKeyframe, ...] = ()
    error: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.attempt_id, "attempt_id")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("attempt index must be positive")
        _text(self.prompt, "prompt")
        _text(self.effective_prompt, "effective_prompt")
        if not isinstance(self.settings, VideoLabSettings):
            raise TypeError("settings must be VideoLabSettings")
        if not isinstance(self.music_enabled, bool):
            raise TypeError("music_enabled must be a boolean")
        if not isinstance(self.keyframe_timestamps_ms, tuple):
            raise TypeError("keyframe_timestamps_ms must be a tuple")
        if tuple(sorted(set(self.keyframe_timestamps_ms))) != self.keyframe_timestamps_ms:
            raise ValueError("keyframe timestamps must be unique and chronological")
        for value in self.keyframe_timestamps_ms:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("keyframe timestamps must be non-negative integers")
        if not isinstance(self.status, H3RenderAttemptStatus):
            raise TypeError("status must be an H3RenderAttemptStatus")
        if self.execution_id is not None:
            _text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None and _SHA256.fullmatch(self.compiled_workflow_sha256) is None:
            raise ValueError("compiled_workflow_sha256 must be a lowercase SHA-256")
        if self.output_asset_id is not None:
            _text(self.output_asset_id, "output_asset_id")
        if not isinstance(self.keyframes, tuple) or any(
            not isinstance(value, H3RenderKeyframe) for value in self.keyframes
        ):
            raise TypeError("keyframes must contain H3RenderKeyframe values")
        if self.error is not None:
            _text(self.error, "error")
        _strings(self.warnings, "warnings", maximum=32)
        self._validate_state()

    def queue(self) -> H3RenderAttempt:
        if self.status is not H3RenderAttemptStatus.CREATED:
            raise ValueError("only a created attempt can be queued")
        return replace(self, status=H3RenderAttemptStatus.QUEUED)

    def start(self, execution_id: str, digest: str) -> H3RenderAttempt:
        if self.status is not H3RenderAttemptStatus.QUEUED:
            raise ValueError("only a queued attempt can start")
        return replace(
            self,
            status=H3RenderAttemptStatus.RUNNING,
            execution_id=_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_digest(digest),
        )

    def succeed(
        self,
        asset_id: str,
        keyframes: tuple[H3RenderKeyframe, ...],
        warnings: tuple[str, ...] = (),
    ) -> H3RenderAttempt:
        if self.status not in {
            H3RenderAttemptStatus.RUNNING,
            H3RenderAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only an active attempt can succeed")
        return replace(
            self,
            status=H3RenderAttemptStatus.SUCCEEDED,
            output_asset_id=_text(asset_id, "asset_id"),
            keyframes=keyframes,
            error=None,
            warnings=warnings,
        )

    def fail(self, error: str) -> H3RenderAttempt:
        if self.status not in {
            H3RenderAttemptStatus.CREATED,
            H3RenderAttemptStatus.QUEUED,
            H3RenderAttemptStatus.RUNNING,
            H3RenderAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only a non-terminal attempt can fail")
        return replace(
            self,
            status=H3RenderAttemptStatus.FAILED,
            output_asset_id=None,
            keyframes=(),
            error=_text(error, "error"),
        )

    def cancel_pending(self, error: str) -> H3RenderAttempt:
        if self.status not in {
            H3RenderAttemptStatus.QUEUED,
            H3RenderAttemptStatus.RUNNING,
        }:
            raise ValueError("only a queued or running attempt can await cancellation")
        return replace(
            self,
            status=H3RenderAttemptStatus.CANCEL_PENDING,
            error=_text(error, "error"),
        )

    def cancel(self) -> H3RenderAttempt:
        if self.status not in {
            H3RenderAttemptStatus.CREATED,
            H3RenderAttemptStatus.QUEUED,
            H3RenderAttemptStatus.RUNNING,
            H3RenderAttemptStatus.CANCEL_PENDING,
        }:
            return self
        return replace(
            self,
            status=H3RenderAttemptStatus.CANCELLED,
            output_asset_id=None,
            keyframes=(),
            error=None,
        )

    def _validate_state(self) -> None:
        if self.status in {H3RenderAttemptStatus.CREATED, H3RenderAttemptStatus.QUEUED}:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)) or self.keyframes:
                raise ValueError("created or queued attempt contains execution fields")
        elif self.status in {H3RenderAttemptStatus.RUNNING, H3RenderAttemptStatus.CANCEL_PENDING}:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("active attempt requires execution fields")
            if self.output_asset_id is not None or self.keyframes:
                raise ValueError("active attempt cannot contain outputs")
            if self.status is H3RenderAttemptStatus.RUNNING and self.error is not None:
                raise ValueError("running attempt cannot contain an error")
            if self.status is H3RenderAttemptStatus.CANCEL_PENDING and self.error is None:
                raise ValueError("cancel-pending attempt requires an error")
        elif self.status is H3RenderAttemptStatus.SUCCEEDED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None or self.output_asset_id is None or self.error is not None:
                raise ValueError("succeeded attempt is incomplete")
        elif self.status is H3RenderAttemptStatus.FAILED:
            if self.output_asset_id is not None or self.keyframes or self.error is None:
                raise ValueError("failed attempt requires only an error")
        elif self.output_asset_id is not None or self.keyframes or self.error is not None:
            raise ValueError("cancelled attempt cannot contain outputs or error")


@dataclass(frozen=True, slots=True)
class H3RenderProject:
    project_id: str
    source_session_id: str
    source_prompt_revision_id: str
    model_id: str
    input_mode: H3RenderInputMode
    current_prompt: str
    planned_cut_times_ms: tuple[int, ...] = ()
    first_frame_asset_id: str | None = None
    first_frame_label: str | None = None
    last_frame_asset_id: str | None = None
    last_frame_label: str | None = None
    reference_asset_ids: tuple[str, ...] = ()
    reference_labels: tuple[str, ...] = ()
    turns: tuple[H3RenderTurn, ...] = ()
    attempts: tuple[H3RenderAttempt, ...] = ()
    feedback_attempt_id: str | None = None
    warnings: tuple[str, ...] = ()
    revision_version: H3RenderRevisionVersion | None = None
    camera_clauses: tuple[str, ...] = ()
    revision_draft: str | None = None
    revision_error: str | None = None
    revision_draft_version: H3RenderRevisionVersion | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.project_id, "project_id"),
            (self.source_session_id, "source_session_id"),
            (self.source_prompt_revision_id, "source_prompt_revision_id"),
            (self.model_id, "model_id"),
            (self.current_prompt, "current_prompt"),
        ):
            _text(value, label)
        if not isinstance(self.input_mode, H3RenderInputMode):
            raise TypeError("input_mode must be an H3RenderInputMode")
        if tuple(sorted(set(self.planned_cut_times_ms))) != self.planned_cut_times_ms:
            raise ValueError("planned cut times must be unique and chronological")
        for value in self.planned_cut_times_ms:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("planned cut times must be positive integers")
        for value, label in (
            (self.first_frame_asset_id, "first_frame_asset_id"),
            (self.first_frame_label, "first_frame_label"),
            (self.last_frame_asset_id, "last_frame_asset_id"),
            (self.last_frame_label, "last_frame_label"),
        ):
            if value is not None:
                _text(value, label)
        if (self.first_frame_asset_id is None) != (self.first_frame_label is None):
            raise ValueError("first frame identity is incomplete")
        if (self.last_frame_asset_id is None) != (self.last_frame_label is None):
            raise ValueError("last frame identity is incomplete")
        if len(self.reference_asset_ids) != len(self.reference_labels):
            raise ValueError("Ref2V reference identities are incomplete")
        if self.input_mode is H3RenderInputMode.REF2VA:
            if not 1 <= len(self.reference_asset_ids) <= 9:
                raise ValueError("Ref2V render projects require 1 to 9 references")
            if self.first_frame_asset_id is not None or self.last_frame_asset_id is not None:
                raise ValueError("Ref2V render projects do not use H3 Base frame fields")
        else:
            if self.reference_asset_ids or self.reference_labels:
                raise ValueError("H3 Base render projects cannot contain Ref2V references")
            expected_mode = _input_mode(self.first_frame_asset_id, self.last_frame_asset_id)
            if self.input_mode is not expected_mode:
                raise ValueError("input_mode disagrees with the available frame anchors")
        for value in (*self.reference_asset_ids, *self.reference_labels):
            _text(value, "Ref2V reference")
        if len(set(self.reference_asset_ids)) != len(self.reference_asset_ids):
            raise ValueError("Ref2V references must be distinct")
        if not isinstance(self.turns, tuple) or any(not isinstance(value, H3RenderTurn) for value in self.turns):
            raise TypeError("turns must contain H3RenderTurn values")
        if not isinstance(self.attempts, tuple) or any(not isinstance(value, H3RenderAttempt) for value in self.attempts):
            raise TypeError("attempts must contain H3RenderAttempt values")
        if len({value.turn_id for value in self.turns}) != len(self.turns):
            raise ValueError("turn IDs must be unique")
        if len({value.attempt_id for value in self.attempts}) != len(self.attempts):
            raise ValueError("attempt IDs must be unique")
        if self.feedback_attempt_id is not None:
            attempt = self.attempt(self.feedback_attempt_id)
            if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
                raise ValueError("feedback must reference a succeeded attempt")
        _strings(self.warnings, "warnings", maximum=32)
        if self.revision_version is not None and not isinstance(
            self.revision_version,
            H3RenderRevisionVersion,
        ):
            raise TypeError("revision_version must be an H3RenderRevisionVersion or None")
        _strings(self.camera_clauses, "camera_clauses", maximum=8)
        if self.input_mode is H3RenderInputMode.REF2VA and self.camera_clauses:
            raise ValueError("Ref2V render projects do not use H3 Base camera clauses")
        if self.revision_draft is not None:
            _text(self.revision_draft, "revision_draft")
        if self.revision_error is not None:
            _text(self.revision_error, "revision_error")
        if self.revision_draft_version is not None and not isinstance(
            self.revision_draft_version,
            H3RenderRevisionVersion,
        ):
            raise TypeError(
                "revision_draft_version must be an H3RenderRevisionVersion or None"
            )
        if self.revision_draft_version is not None and self.revision_error is None:
            raise ValueError("a revision draft version requires a revision error")

    def add_turn(self, turn: H3RenderTurn) -> H3RenderProject:
        if any(value.turn_id == turn.turn_id for value in self.turns):
            raise ValueError("turn already exists")
        prompt = turn.prompt if turn.role is H3RenderTurnRole.ASSISTANT and turn.prompt else self.current_prompt
        clear_draft = turn.role is H3RenderTurnRole.ASSISTANT
        return replace(
            self,
            turns=(*self.turns, turn),
            current_prompt=prompt,
            revision_draft=None if clear_draft else self.revision_draft,
            revision_error=None if clear_draft else self.revision_error,
            revision_draft_version=(
                None if clear_draft else self.revision_draft_version
            ),
        )

    def select_revision_version(
        self,
        version: H3RenderRevisionVersion,
    ) -> H3RenderProject:
        if not isinstance(version, H3RenderRevisionVersion):
            raise TypeError("version must be an H3RenderRevisionVersion")
        return replace(self, revision_version=version)

    def reject_revision(
        self,
        *,
        draft: str | None,
        error: str,
        version: H3RenderRevisionVersion,
    ) -> H3RenderProject:
        if draft is not None:
            _text(draft, "revision draft")
        return replace(
            self,
            revision_draft=draft,
            revision_error=_text(error, "revision error"),
            revision_draft_version=version,
        )

    def add_attempt(self, attempt: H3RenderAttempt) -> H3RenderProject:
        if any(value.attempt_id == attempt.attempt_id for value in self.attempts):
            raise ValueError("attempt already exists")
        return replace(self, attempts=(*self.attempts, attempt))

    def replace_attempt(self, attempt: H3RenderAttempt) -> H3RenderProject:
        if sum(value.attempt_id == attempt.attempt_id for value in self.attempts) != 1:
            raise KeyError(attempt.attempt_id)
        return replace(
            self,
            attempts=tuple(attempt if value.attempt_id == attempt.attempt_id else value for value in self.attempts),
        )

    def use_feedback(self, attempt_id: str | None) -> H3RenderProject:
        if attempt_id is None:
            return replace(self, feedback_attempt_id=None)
        attempt = self.attempt(attempt_id)
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise ValueError("feedback must reference a succeeded attempt")
        return replace(self, feedback_attempt_id=attempt_id)

    def resume_attempt(self, attempt_id: str) -> H3RenderProject:
        attempt = self.attempt(attempt_id)
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can be resumed")
        return replace(self, current_prompt=attempt.prompt, feedback_attempt_id=attempt_id)

    def attempt(self, attempt_id: str) -> H3RenderAttempt:
        for value in self.attempts:
            if value.attempt_id == attempt_id:
                return value
        raise KeyError(attempt_id)


def _input_mode(first: str | None, last: str | None) -> H3RenderInputMode:
    if first is None and last is None:
        return H3RenderInputMode.T2VA
    if first is not None and last is None:
        return H3RenderInputMode.I2VA
    if first is None:
        return H3RenderInputMode.L2VA
    return H3RenderInputMode.FL2VA


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _strings(values: object, label: str, *, maximum: int) -> tuple[str, ...]:
    if not isinstance(values, tuple) or len(values) > maximum:
        raise ValueError(f"{label} must be a tuple containing at most {maximum} values")
    for value in values:
        _text(value, label)
    return values


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("digest must be a lowercase SHA-256")
    return value


__all__ = [
    "H3RenderAttempt",
    "H3RenderAttemptStatus",
    "H3RenderInputMode",
    "H3RenderKeyframe",
    "H3RenderProject",
    "H3RenderTurn",
    "H3RenderTurnRole",
    "VideoAspectRatio",
    "VideoLabSettings",
]
