"""Durable contracts for the human-guided Production V2 workshop."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .krea2_batch import Krea2BatchSettings
from .h3_render import H3VideoLoraSelection
from .video_lab import VideoAspectRatio


class ProductionV2Stage(StrEnum):
    IMAGE_CALIBRATION = "image_calibration"
    ANCHOR_WORKSHOP = "anchor_workshop"
    VIDEO_PROMPT = "video_prompt"
    VIDEO_PREVIEW = "video_preview"
    COMPLETE = "complete"


class ProductionV2Status(StrEnum):
    READY = "ready"
    BUSY = "busy"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProductionV2CandidateStatus(StrEnum):
    PROMPTING = "prompting"
    RENDERING = "rendering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProductionV2CandidateKind(StrEnum):
    CREATIVE = "creative"
    RESOLUTION_CLONE = "resolution_clone"
    TECHNICAL_LORA = "technical_lora"


class ProductionV2PromptStrategy(StrEnum):
    PRESERVE_CURRENT = "preserve_current"
    REWRITE_ONCE = "rewrite_once"
    EVOLVE_BETWEEN = "evolve_between"


class ProductionV2ReferenceMode(StrEnum):
    NONE = "none"
    RECIPE = "recipe"
    RECIPE_AND_GUIDANCE = "recipe_and_guidance"


class ProductionV2LlmTraceStatus(StrEnum):
    PENDING = "pending"
    THINKING = "thinking"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProductionV2AnchorRole(StrEnum):
    CALIBRATION = "calibration"
    FIRST_FRAME = "first_frame"
    LAST_FRAME = "last_frame"
    REFERENCE = "reference"


class ProductionV2Preference(StrEnum):
    NONE = "none"
    LIKE = "like"
    DISLIKE = "dislike"


class ProductionV2Route(StrEnum):
    PENDING = "pending"
    I2VA = "i2va"
    L2VA = "l2va"
    FL2VA = "fl2va"
    REF2VA = "ref2va"


@dataclass(frozen=True, slots=True)
class ProductionV2MemoryObservation:
    project_id: str
    candidate_id: str
    timestamp: str
    preference: ProductionV2Preference
    comment: str
    prompt: str
    model_id: str
    settings: Krea2BatchSettings
    role: ProductionV2AnchorRole = ProductionV2AnchorRole.CALIBRATION


@dataclass(frozen=True, slots=True)
class ProductionV2MemoryProfile:
    profile_id: str
    name: str
    created_at: str
    observations: tuple[ProductionV2MemoryObservation, ...] = ()

    def with_observation(
        self,
        observation: ProductionV2MemoryObservation,
    ) -> "ProductionV2MemoryProfile":
        values = tuple(
            value
            for value in self.observations
            if not (
                value.project_id == observation.project_id
                and value.candidate_id == observation.candidate_id
            )
        )
        return replace(self, observations=(*values, observation))


@dataclass(frozen=True, slots=True)
class ProductionV2VisualRecipeRevision:
    revision_id: str
    index: int
    created_at: str
    source_candidate_id: str
    settings: Krea2BatchSettings
    prompt: str = ""
    seed: int | None = None
    asset_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionV2Candidate:
    candidate_id: str
    index: int
    round_index: int
    role: ProductionV2AnchorRole
    memory_profile_id: str
    requested_model_id: str
    actual_model_id: str | None
    settings: Krea2BatchSettings
    status: ProductionV2CandidateStatus
    generation_kind: ProductionV2CandidateKind = ProductionV2CandidateKind.CREATIVE
    feedback_parent_id: str | None = None
    child_project_id: str | None = None
    child_attempt_id: str | None = None
    prompt: str | None = None
    seed: int | None = None
    output_asset_id: str | None = None
    preference: ProductionV2Preference = ProductionV2Preference.NONE
    comment: str = ""
    instruction: str = ""
    assisted_lora_names: tuple[str, ...] = ()
    assisted_lora_rationale: str = ""
    batch_id: str | None = None
    prompt_strategy: ProductionV2PromptStrategy = ProductionV2PromptStrategy.EVOLVE_BETWEEN
    reference_mode: ProductionV2ReferenceMode = ProductionV2ReferenceMode.RECIPE
    guidance_candidate_id: str | None = None
    preserve_seed: bool = False
    preserve_model: bool = False
    preserve_loras: bool = False
    prompt_trace_id: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionV2Anchor:
    anchor_id: str
    role: ProductionV2AnchorRole
    asset_id: str
    label: str
    source_kind: str
    candidate_id: str | None
    recipe_revision_id: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class ProductionV2Event:
    event_id: str
    timestamp: str
    stage: ProductionV2Stage
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class ProductionV2LlmTrace:
    trace_id: str
    batch_id: str
    sequence: int
    total: int
    purpose: str
    label: str
    model_id: str
    status: ProductionV2LlmTraceStatus
    created_at: str
    candidate_id: str | None = None
    reference_asset_ids: tuple[str, ...] = ()
    input_text: str = ""
    thinking: str = ""
    output: str = ""
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionV2Project:
    project_id: str
    name: str
    intention: str
    source_asset_id: str
    source_filename: str
    initial_model_id: str
    memory_profile_id: str
    video_compile_model_id: str | None = None
    preset_id: str = "human_exploration"
    stage: ProductionV2Stage = ProductionV2Stage.IMAGE_CALIBRATION
    status: ProductionV2Status = ProductionV2Status.READY
    candidates: tuple[ProductionV2Candidate, ...] = ()
    recipe_revisions: tuple[ProductionV2VisualRecipeRevision, ...] = ()
    active_recipe_revision_id: str | None = None
    anchors: tuple[ProductionV2Anchor, ...] = ()
    prompt_session_id: str | None = None
    h3_project_id: str | None = None
    archived_prompt_session_ids: tuple[str, ...] = ()
    archived_h3_project_ids: tuple[str, ...] = ()
    video_seed: int | None = None
    video_seed_locked: bool = True
    video_intention: str | None = None
    video_aspect_ratio: VideoAspectRatio | None = None
    duration_seconds: float = 6.0
    preview_megapixels: float = 0.2
    final_megapixels: float = 1.2
    video_steps: int = 25
    spectrum_enabled: bool = True
    music_enabled: bool = False
    video_lora: H3VideoLoraSelection | None = None
    creative_audacity: int = 3
    revision_audacity: int = 3
    stop_temperature_c: float = 85.0
    resume_temperature_c: float = 40.0
    cooldown_seconds: int = 120
    remote_thermal_latched: bool = False
    remote_thermal_latched_at: str | None = None
    preview_attempt_ids: tuple[str, ...] = ()
    selected_preview_attempt_id: str | None = None
    final_attempt_id: str | None = None
    active_operation: str | None = None
    active_operation_id: str | None = None
    active_child_project_id: str | None = None
    active_child_attempt_id: str | None = None
    llm_traces: tuple[ProductionV2LlmTrace, ...] = ()
    active_llm_trace_id: str | None = None
    events: tuple[ProductionV2Event, ...] = ()
    error: str | None = None

    @property
    def active_recipe(self) -> ProductionV2VisualRecipeRevision | None:
        if self.active_recipe_revision_id is None:
            return None
        return next(
            value
            for value in self.recipe_revisions
            if value.revision_id == self.active_recipe_revision_id
        )

    @property
    def route(self) -> ProductionV2Route:
        if any(value.role is ProductionV2AnchorRole.REFERENCE for value in self.anchors):
            return ProductionV2Route.REF2VA
        first = any(value.role is ProductionV2AnchorRole.FIRST_FRAME for value in self.anchors)
        last = any(value.role is ProductionV2AnchorRole.LAST_FRAME for value in self.anchors)
        if first and last:
            return ProductionV2Route.FL2VA
        if first:
            return ProductionV2Route.I2VA
        if last:
            return ProductionV2Route.L2VA
        return ProductionV2Route.PENDING

    @property
    def effective_video_intention(self) -> str:
        return self.video_intention or self.intention

    @property
    def effective_video_compile_model_id(self) -> str:
        return self.video_compile_model_id or self.initial_model_id

    @property
    def effective_video_aspect_ratio(self) -> VideoAspectRatio:
        if self.video_aspect_ratio is not None:
            return self.video_aspect_ratio
        if self.active_recipe is not None:
            return VideoAspectRatio(self.active_recipe.settings.aspect_ratio.value)
        return VideoAspectRatio.PORTRAIT_WIDESCREEN

    def candidate(self, candidate_id: str) -> ProductionV2Candidate:
        return next(value for value in self.candidates if value.candidate_id == candidate_id)

    def replace_candidate(self, candidate: ProductionV2Candidate) -> "ProductionV2Project":
        if sum(value.candidate_id == candidate.candidate_id for value in self.candidates) != 1:
            raise KeyError(candidate.candidate_id)
        return replace(
            self,
            candidates=tuple(
                candidate if value.candidate_id == candidate.candidate_id else value
                for value in self.candidates
            ),
        )

    def trace(self, trace_id: str) -> ProductionV2LlmTrace:
        return next(value for value in self.llm_traces if value.trace_id == trace_id)

    def replace_trace(self, trace: ProductionV2LlmTrace) -> "ProductionV2Project":
        if sum(value.trace_id == trace.trace_id for value in self.llm_traces) != 1:
            raise KeyError(trace.trace_id)
        return replace(
            self,
            llm_traces=tuple(
                trace if value.trace_id == trace.trace_id else value
                for value in self.llm_traces
            ),
        )


__all__ = [name for name in globals() if name.startswith("ProductionV2")]
