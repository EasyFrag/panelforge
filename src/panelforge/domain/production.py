"""Durable contracts for the automated Image -> KREA2 -> H3 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
import math

from .krea2_batch import Krea2BatchSettings
from .h3_render import H3VideoLoraSelection
from .prompt_lab import CreativeFreedomAxes


class ProductionMode(StrEnum):
    FULL_AUTO = "full_auto"
    HUMAN_REVIEW = "human_review"


class ProductionStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    WAITING_RESOURCE = "waiting_resource"
    PAUSED_THERMAL = "paused_thermal"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProductionStage(StrEnum):
    SETUP = "setup"
    IMAGE_GENERATION = "image_generation"
    IMAGE_SELECTION = "image_selection"
    H3_PROMPT = "h3_prompt"
    VIDEO_PREVIEW = "video_preview"
    VIDEO_EVALUATION = "video_evaluation"
    VIDEO_FINAL = "video_final"
    COMPLETE = "complete"


class ProductionDecisionKind(StrEnum):
    IMAGE_SELECTION = "image_selection"
    VIDEO_EVALUATION = "video_evaluation"


class ProductionDecisionOutcome(StrEnum):
    SELECT = "select"
    ACCEPT = "accept"
    REVISE = "revise"
    FALLBACK = "fallback"


class ProductionLoraChoiceSource(StrEnum):
    MANUAL = "manual"
    MODEL = "model"


class ProductionEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ComputeResource(StrEnum):
    LOCAL_GPU = "local_gpu"
    REMOTE_GPU = "remote_gpu"


class ProductionWorkload(StrEnum):
    LLM = "llm"
    IMAGE_RENDER = "image_render"
    VIDEO_RENDER = "video_render"
    VIDEO_COOLDOWN = "video_cooldown"


class ComputeResourceState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    HOT = "hot"
    COOLING = "cooling"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ComputeResourceStatus:
    resource: ComputeResource
    state: ComputeResourceState
    temperature_c: float | None = None
    owner_job_id: str | None = None
    operation: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if not isinstance(self.state, ComputeResourceState):
            raise TypeError("state must be a ComputeResourceState")
        if self.temperature_c is not None:
            temperature = _finite(self.temperature_c, "temperature_c")
            if not 0 <= temperature <= 150:
                raise ValueError("temperature_c must be between 0 and 150")
        for value, label, maximum in (
            (self.owner_job_id, "owner_job_id", 128),
            (self.operation, "operation", 200),
            (self.error, "resource error", 1_000),
        ):
            if value is not None:
                _text(value, label, maximum)


@dataclass(frozen=True, slots=True)
class ThermalPolicy:
    stop_temperature_c: float = 85.0
    resume_temperature_c: float = 40.0
    cooldown_seconds: int = 120
    monitor_local: bool = True
    monitor_remote: bool = True
    pause_when_unavailable: bool = True

    def __post_init__(self) -> None:
        _finite(self.stop_temperature_c, "stop_temperature_c")
        _finite(self.resume_temperature_c, "resume_temperature_c")
        if not 30 <= float(self.stop_temperature_c) <= 110:
            raise ValueError("stop_temperature_c must be between 30 and 110")
        if not 15 <= float(self.resume_temperature_c) < float(self.stop_temperature_c):
            raise ValueError("resume_temperature_c must be below the stop temperature")
        if (
            isinstance(self.cooldown_seconds, bool)
            or not isinstance(self.cooldown_seconds, int)
            or not 0 <= self.cooldown_seconds <= 86_400
        ):
            raise ValueError("cooldown_seconds must be between 0 and 86400")
        for value, label in (
            (self.monitor_local, "monitor_local"),
            (self.monitor_remote, "monitor_remote"),
            (self.pause_when_unavailable, "pause_when_unavailable"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{label} must be a boolean")
        if not self.monitor_local and not self.monitor_remote:
            raise ValueError("at least one thermal source must be monitored")


@dataclass(frozen=True, slots=True)
class ThermalSnapshot:
    local_temperature_c: float | None = None
    remote_temperature_c: float | None = None
    local_error: str | None = None
    remote_error: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.local_temperature_c, "local_temperature_c"),
            (self.remote_temperature_c, "remote_temperature_c"),
        ):
            if value is not None:
                temperature = _finite(value, label)
                if not 0 <= temperature <= 150:
                    raise ValueError(f"{label} must be between 0 and 150")
        for value, label in (
            (self.local_error, "local_error"),
            (self.remote_error, "remote_error"),
        ):
            if value is not None:
                _text(value, label, 1_000)


@dataclass(frozen=True, slots=True)
class ProductionConfig:
    model_id: str
    image_settings: Krea2BatchSettings
    mode: ProductionMode = ProductionMode.FULL_AUTO
    creative_freedom: int = 100
    creative_axes: CreativeFreedomAxes = CreativeFreedomAxes(3, 3, 3)
    image_attempt_count: int = 3
    video_preview_limit: int = 3
    video_acceptance_score: int = 80
    duration_seconds: float = 10.0
    video_steps: int = 25
    preview_megapixels: float = 0.2
    final_megapixels: float = 1.2
    music_enabled: bool = False
    assisted_lora_selection: bool = False
    creative_direction_enabled: bool = False
    creative_audacity: int = 2
    h3_video_lora: H3VideoLoraSelection | None = None
    thermal: ThermalPolicy = field(default_factory=ThermalPolicy)

    def __post_init__(self) -> None:
        _text(self.model_id, "model_id", 300)
        if not isinstance(self.image_settings, Krea2BatchSettings):
            raise TypeError("image_settings must be Krea2BatchSettings")
        if not isinstance(self.mode, ProductionMode):
            raise TypeError("mode must be a ProductionMode")
        if (
            isinstance(self.creative_freedom, bool)
            or not isinstance(self.creative_freedom, int)
            or not 0 <= self.creative_freedom <= 100
        ):
            raise ValueError("creative_freedom must be between 0 and 100")
        if not isinstance(self.creative_axes, CreativeFreedomAxes):
            raise TypeError("creative_axes must be CreativeFreedomAxes")
        for value, label, minimum, maximum in (
            (self.image_attempt_count, "image_attempt_count", 1, 6),
            (self.video_preview_limit, "video_preview_limit", 1, 6),
            (self.video_acceptance_score, "video_acceptance_score", 1, 100),
            (self.video_steps, "video_steps", 1, 100),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError(f"{label} must be between {minimum} and {maximum}")
        _range(self.duration_seconds, "duration_seconds", 5.0, 15.0)
        _range(self.preview_megapixels, "preview_megapixels", 0.1, 16.0)
        _range(self.final_megapixels, "final_megapixels", 0.1, 16.0)
        if self.final_megapixels < self.preview_megapixels:
            raise ValueError("final_megapixels must not be below preview_megapixels")
        if not isinstance(self.music_enabled, bool):
            raise TypeError("music_enabled must be a boolean")
        if not isinstance(self.assisted_lora_selection, bool):
            raise TypeError("assisted_lora_selection must be a boolean")
        if not isinstance(self.creative_direction_enabled, bool):
            raise TypeError("creative_direction_enabled must be a boolean")
        if (
            isinstance(self.creative_audacity, bool)
            or not isinstance(self.creative_audacity, int)
            or not 0 <= self.creative_audacity <= 3
        ):
            raise ValueError("creative_audacity must be between 0 and 3")
        if self.h3_video_lora is not None and not isinstance(
            self.h3_video_lora, H3VideoLoraSelection
        ):
            raise TypeError("h3_video_lora must be an H3VideoLoraSelection or None")
        if not isinstance(self.thermal, ThermalPolicy):
            raise TypeError("thermal must be a ThermalPolicy")


@dataclass(frozen=True, slots=True)
class ProductionCandidateAssessment:
    attempt_id: str
    score: int
    summary: str

    def __post_init__(self) -> None:
        _text(self.attempt_id, "assessment attempt_id", 128)
        if isinstance(self.score, bool) or not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise ValueError("assessment score must be between 0 and 100")
        _text(self.summary, "assessment summary", 2_000)


@dataclass(frozen=True, slots=True)
class ProductionLoraChoice:
    name: str
    strength: float
    source: ProductionLoraChoiceSource
    expected_effect: str

    def __post_init__(self) -> None:
        _text(self.name, "LoRA name", 500)
        _range(self.strength, "LoRA strength", -20.0, 20.0, step=None)
        if not isinstance(self.source, ProductionLoraChoiceSource):
            raise TypeError("LoRA source must be a ProductionLoraChoiceSource")
        _text(self.expected_effect, "LoRA expected effect", 2_000)


@dataclass(frozen=True, slots=True)
class ProductionLoraPlan:
    choices: tuple[ProductionLoraChoice, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.choices, tuple) or any(
            not isinstance(value, ProductionLoraChoice) for value in self.choices
        ):
            raise TypeError("LoRA plan choices must contain ProductionLoraChoice values")
        if len(self.choices) > 4:
            raise ValueError("a LoRA plan supports at most four choices")
        normalized = [value.name.replace("\\", "/").casefold() for value in self.choices]
        if len(normalized) != len(set(normalized)):
            raise ValueError("a LoRA plan cannot select the same LoRA twice")
        _text(self.rationale, "LoRA plan rationale", 4_000)


@dataclass(frozen=True, slots=True)
class ProductionEvent:
    event_id: str
    timestamp: str
    stage: ProductionStage
    level: ProductionEventLevel
    message: str

    def __post_init__(self) -> None:
        _text(self.event_id, "event_id", 128)
        _text(self.timestamp, "timestamp", 64)
        if not isinstance(self.stage, ProductionStage):
            raise TypeError("stage must be a ProductionStage")
        if not isinstance(self.level, ProductionEventLevel):
            raise TypeError("level must be a ProductionEventLevel")
        _text(self.message, "event message", 4_000)


@dataclass(frozen=True, slots=True)
class ProductionDecision:
    decision_id: str
    timestamp: str
    kind: ProductionDecisionKind
    outcome: ProductionDecisionOutcome
    attempt_id: str
    score: int
    rationale: str
    revision_instruction: str | None = None
    assessments: tuple[ProductionCandidateAssessment, ...] = ()

    def __post_init__(self) -> None:
        _text(self.decision_id, "decision_id", 128)
        _text(self.timestamp, "timestamp", 64)
        if not isinstance(self.kind, ProductionDecisionKind):
            raise TypeError("kind must be a ProductionDecisionKind")
        if not isinstance(self.outcome, ProductionDecisionOutcome):
            raise TypeError("outcome must be a ProductionDecisionOutcome")
        _text(self.attempt_id, "attempt_id", 128)
        if isinstance(self.score, bool) or not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        _text(self.rationale, "decision rationale", 4_000)
        if self.revision_instruction is not None:
            _text(self.revision_instruction, "revision_instruction", 8_000)
        if self.outcome is ProductionDecisionOutcome.REVISE and self.revision_instruction is None:
            raise ValueError("a revision decision requires an instruction")
        if not isinstance(self.assessments, tuple) or any(
            not isinstance(value, ProductionCandidateAssessment) for value in self.assessments
        ):
            raise TypeError("assessments must contain ProductionCandidateAssessment values")
        assessment_ids = [value.attempt_id for value in self.assessments]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ValueError("assessment attempt IDs must be unique")


@dataclass(frozen=True, slots=True)
class ProductionJob:
    job_id: str
    name: str
    intention: str
    source_asset_id: str
    source_filename: str
    config: ProductionConfig
    status: ProductionStatus = ProductionStatus.DRAFT
    stage: ProductionStage = ProductionStage.SETUP
    krea_project_id: str | None = None
    krea_attempt_ids: tuple[str, ...] = ()
    krea_feedback_attempt_ids: tuple[str, ...] = ()
    lora_plan: ProductionLoraPlan | None = None
    selected_image_attempt_id: str | None = None
    selected_image_asset_id: str | None = None
    image_review_approved: bool = False
    prompt_session_id: str | None = None
    h3_project_id: str | None = None
    video_seed: int | None = None
    preview_attempt_ids: tuple[str, ...] = ()
    selected_preview_attempt_id: str | None = None
    video_review_approved: bool = False
    manual_revision_instruction: str | None = None
    final_attempt_id: str | None = None
    active_child_kind: str | None = None
    active_child_attempt_id: str | None = None
    decisions: tuple[ProductionDecision, ...] = ()
    events: tuple[ProductionEvent, ...] = ()
    pause_reason: str | None = None
    error: str | None = None
    cancel_requested: bool = False

    def __post_init__(self) -> None:
        for value, label, maximum in (
            (self.job_id, "job_id", 128),
            (self.name, "name", 120),
            (self.intention, "intention", 20_000),
            (self.source_asset_id, "source_asset_id", 128),
            (self.source_filename, "source_filename", 240),
        ):
            _text(value, label, maximum)
        if not isinstance(self.config, ProductionConfig):
            raise TypeError("config must be a ProductionConfig")
        if not isinstance(self.status, ProductionStatus):
            raise TypeError("status must be a ProductionStatus")
        if not isinstance(self.stage, ProductionStage):
            raise TypeError("stage must be a ProductionStage")
        for value, label in (
            (self.krea_project_id, "krea_project_id"),
            (self.selected_image_attempt_id, "selected_image_attempt_id"),
            (self.selected_image_asset_id, "selected_image_asset_id"),
            (self.prompt_session_id, "prompt_session_id"),
            (self.h3_project_id, "h3_project_id"),
            (self.selected_preview_attempt_id, "selected_preview_attempt_id"),
            (self.final_attempt_id, "final_attempt_id"),
            (self.active_child_kind, "active_child_kind"),
            (self.active_child_attempt_id, "active_child_attempt_id"),
        ):
            if value is not None:
                _text(value, label, 128)
        _ids(self.krea_attempt_ids, "krea_attempt_ids")
        _ids(self.krea_feedback_attempt_ids, "krea_feedback_attempt_ids")
        _ids(self.preview_attempt_ids, "preview_attempt_ids")
        if self.lora_plan is not None and not isinstance(self.lora_plan, ProductionLoraPlan):
            raise TypeError("lora_plan must be a ProductionLoraPlan")
        if not set(self.krea_feedback_attempt_ids).issubset(self.krea_attempt_ids):
            raise ValueError("KREA2 feedback attempts must belong to the job")
        if (self.selected_image_attempt_id is None) != (self.selected_image_asset_id is None):
            raise ValueError("selected image identity is incomplete")
        if self.selected_image_attempt_id is not None and self.selected_image_attempt_id not in self.krea_attempt_ids:
            raise ValueError("selected image attempt does not belong to the job")
        if self.selected_preview_attempt_id is not None and self.selected_preview_attempt_id not in self.preview_attempt_ids:
            raise ValueError("selected preview attempt does not belong to the job")
        if self.final_attempt_id is not None and self.h3_project_id is None:
            raise ValueError("a final attempt requires an H3 project")
        if self.video_seed is not None:
            if isinstance(self.video_seed, bool) or not isinstance(self.video_seed, int) or not 0 <= self.video_seed < 2**64:
                raise ValueError("video_seed must be between 0 and 2^64 - 1")
        for value, label in (
            (self.image_review_approved, "image_review_approved"),
            (self.video_review_approved, "video_review_approved"),
            (self.cancel_requested, "cancel_requested"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{label} must be a boolean")
        if self.manual_revision_instruction is not None:
            _text(self.manual_revision_instruction, "manual_revision_instruction", 8_000)
        if not isinstance(self.decisions, tuple) or any(not isinstance(value, ProductionDecision) for value in self.decisions):
            raise TypeError("decisions must contain ProductionDecision values")
        if not isinstance(self.events, tuple) or any(not isinstance(value, ProductionEvent) for value in self.events):
            raise TypeError("events must contain ProductionEvent values")
        if len({value.decision_id for value in self.decisions}) != len(self.decisions):
            raise ValueError("decision IDs must be unique")
        if len({value.event_id for value in self.events}) != len(self.events):
            raise ValueError("event IDs must be unique")
        if self.pause_reason is not None:
            _text(self.pause_reason, "pause_reason", 4_000)
        if self.error is not None:
            _text(self.error, "error", 8_000)
        if self.status is ProductionStatus.SUCCEEDED:
            if self.stage is not ProductionStage.COMPLETE or self.final_attempt_id is None:
                raise ValueError("a succeeded job requires a completed final attempt")
        if self.status is ProductionStatus.FAILED and self.error is None:
            raise ValueError("a failed job requires an error")

    def with_event(self, event: ProductionEvent) -> ProductionJob:
        if any(value.event_id == event.event_id for value in self.events):
            raise ValueError("event already exists")
        return replace(self, events=(*self.events[-199:], event))

    def with_decision(self, decision: ProductionDecision) -> ProductionJob:
        if any(value.decision_id == decision.decision_id for value in self.decisions):
            raise ValueError("decision already exists")
        return replace(self, decisions=(*self.decisions, decision))


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _ids(values: object, label: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    for value in values:
        _text(value, f"{label} item", 128)


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _range(
    value: object,
    label: str,
    minimum: float,
    maximum: float,
    *,
    step: float | None = 0.1,
) -> float:
    number = _finite(value, label)
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    if step is not None and not math.isclose(number / step, round(number / step)):
        raise ValueError(f"{label} must use increments of {step:g}")
    return number


__all__ = [
    "ComputeResource",
    "ComputeResourceState",
    "ComputeResourceStatus",
    "ProductionConfig",
    "ProductionCandidateAssessment",
    "ProductionDecision",
    "ProductionDecisionKind",
    "ProductionDecisionOutcome",
    "ProductionEvent",
    "ProductionEventLevel",
    "ProductionJob",
    "ProductionLoraChoice",
    "ProductionLoraChoiceSource",
    "ProductionLoraPlan",
    "ProductionMode",
    "ProductionStage",
    "ProductionStatus",
    "ProductionWorkload",
    "ThermalPolicy",
    "ThermalSnapshot",
]
