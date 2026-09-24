"""Pure state for conversational H3 Base video rendering projects."""

from __future__ import annotations
from .dlss import DlssResult, validate_dlss_attempt, validate_dlss_lineage

from panelforge.domain.h3_checkpoint import H3ModelLoading, validate_h3_model_selection

from dataclasses import dataclass, replace
from enum import StrEnum
import math
import re

from .video_lab import VideoAspectRatio, VideoLabSettings
from .video_preparation import (
    VideoPreparationRef, CombatSettings, ClassicCinematicSettings, SensualSettings,
    validate_combat_settings, validate_cinematic_settings, validate_sensual_settings,
)
from .recipes import RecipeRef
from .h3_bunny import BUNNY_RECIPE_ID, H3BunnySettings, bunny_geometry


_SHA256 = re.compile(r"[0-9a-f]{64}")
H3_VIDEO_LORA_PREFIX = "minmax_nsfw/"
H3_VIDEO_LORA_OVERLAY_VERSION = "0.1.0"


def validate_h3_initial_megapixels(value: float) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0.1 <= value <= 16.0):
        raise ValueError("Les MP avant upscale doivent être compris entre 0,1 et 16.")
    if not math.isclose(value * 10, round(value * 10)):
        raise ValueError("Les MP avant upscale doivent utiliser un pas de 0,1.")


def h3_upscale_plan(
    settings: VideoLabSettings,
    initial_megapixels: float,
    *,
    force_upscale: bool = False,
) -> dict[str, object]:
    """Resolve the effective H3 output branch on the shared 32-pixel grid."""
    if not isinstance(settings, VideoLabSettings):
        raise TypeError("settings must be VideoLabSettings")
    validate_h3_initial_megapixels(initial_megapixels)
    if type(force_upscale) is not bool:
        raise TypeError("force_upscale must be a boolean")
    initial_resolution = replace(settings, megapixels=initial_megapixels).resolution
    target_resolution = settings.resolution
    initial_pixels = initial_resolution[0] * initial_resolution[1]
    target_pixels = target_resolution[0] * target_resolution[1]
    if force_upscale and target_resolution != initial_resolution:
        raise ValueError(
            "L’upscale ne peut être forcé que lorsque les résolutions initiale et cible sont égales."
        )
    bypassed = target_pixels <= initial_pixels and not force_upscale
    return {
        "initial_resolution": initial_resolution,
        "target_resolution": target_resolution,
        "effective_resolution": initial_resolution if bypassed else target_resolution,
        "same_resolution": target_resolution == initial_resolution,
        "target_is_lower": target_pixels < initial_pixels,
        "bypassed": bypassed,
    }


class H3RenderInputMode(StrEnum):
    T2VA = "t2va"
    I2VA = "i2va"
    L2VA = "l2va"
    FL2VA = "fl2va"
    REF2VA = "ref2va"


def derive_h3_render_input_mode(first_frame: bool, last_frame: bool) -> H3RenderInputMode:
    """Resolve the frame-conditioned mode shared by projects and render recipes."""
    if not first_frame and not last_frame:
        return H3RenderInputMode.T2VA
    if first_frame and not last_frame:
        return H3RenderInputMode.I2VA
    if not first_frame:
        return H3RenderInputMode.L2VA
    return H3RenderInputMode.FL2VA


class H3RenderTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class H3RenderRevisionVersion(StrEnum):
    COMBAT = "1.0.0"
    COMBAT_1_1 = "1.1.0"
    COMBAT_1_1_1 = "1.1.1"
    COMBAT_1_2 = "1.2.0"
    COMBAT_1_3 = "1.3.0"
    LEGACY = "0.1.0"
    CAMERA_LOCKED = "0.2.0"
    VOCAL = "0.3.0"
    CLASSIC_CINEMATIC = "0.4.0"
    SENSUAL = "0.5.0"


class H3RenderAttemptStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class H3VideoLoraSelection:
    """A validated MiniMax video LoRA overlay for an H3 Base render."""

    name: str
    strength: float = 0.5
    clip_last_layer: int | None = -2
    overlay_version: str = H3_VIDEO_LORA_OVERLAY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", canonical_h3_video_lora_name(self.name))
        if (
            isinstance(self.strength, bool)
            or not isinstance(self.strength, (int, float))
            or not math.isfinite(float(self.strength))
            or not 0 <= float(self.strength) <= 1
        ):
            raise ValueError("H3 video LoRA strength must be between 0 and 1")
        object.__setattr__(self, "strength", float(self.strength))
        if self.clip_last_layer not in {None, -2}:
            raise ValueError("H3 video LoRA clip_last_layer must be -2 or None")
        if self.overlay_version != H3_VIDEO_LORA_OVERLAY_VERSION:
            raise ValueError("unsupported H3 video LoRA overlay version")


def canonical_h3_video_lora_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("H3 video LoRA name must not be empty")
    normalized = value.strip().replace("\\", "/")
    parts = normalized.split("/")
    if (
        len(parts) < 2
        or any(not part or part in {".", ".."} for part in parts)
        or not normalized.casefold().startswith(H3_VIDEO_LORA_PREFIX.casefold())
        or not normalized.casefold().endswith(".safetensors")
    ):
        raise ValueError(
            f"H3 video LoRA must be a .safetensors file below {H3_VIDEO_LORA_PREFIX}"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class H3VideoLoraSlot:
    name: str
    strength: float = 0.5
    second_strength: float | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        validated = H3VideoLoraSelection(self.name, self.strength, None)
        object.__setattr__(self, "name", validated.name)
        object.__setattr__(self, "strength", validated.strength)
        if self.second_strength is not None:
            second = H3VideoLoraSelection(self.name, self.second_strength, None)
            object.__setattr__(self, "second_strength", second.strength)
        if type(self.enabled) is not bool:
            raise TypeError("L’activation d’un LoRA doit être un booléen.")


@dataclass(frozen=True, slots=True)
class H3VideoLoraStack:
    entries: tuple[H3VideoLoraSlot, ...] = ()
    enabled: bool = True
    clip_last_layer: int | None = -2
    version: str = "0.2.0"

    def __post_init__(self) -> None:
        maximum = {"0.1.0": 2, "0.2.0": 4}.get(self.version)
        if maximum is None:
            raise ValueError("Version de configuration LoRA indisponible.")
        if not isinstance(self.entries, tuple) or len(self.entries) > maximum:
            raise ValueError(f"La configuration accepte au maximum {maximum} LoRA.")
        if any(not isinstance(entry, H3VideoLoraSlot) for entry in self.entries):
            raise TypeError("Sélection LoRA invalide.")
        if len({entry.name.casefold() for entry in self.entries}) != len(self.entries):
            raise ValueError("Un même LoRA ne peut pas occuper plusieurs emplacements.")
        if type(self.enabled) is not bool:
            raise TypeError("L’activation des LoRA doit être un booléen.")
        if self.clip_last_layer is not None and (type(self.clip_last_layer) is not int or self.clip_last_layer != -2):
            raise ValueError("CLIP Last Layer doit être -2 ou désactivé.")

    @property
    def active_entries(self) -> tuple[H3VideoLoraSlot, ...]:
        return tuple(entry for entry in self.entries if entry.enabled) if self.enabled else ()

    def validate_mode(self, per_pass: bool) -> None:
        if per_pass and self.clip_last_layer is not None:
            raise ValueError("BUNNY ne prend pas en charge CLIP Last Layer.")
        if any((entry.second_strength is not None) != per_pass for entry in self.entries):
            raise ValueError("Chaque LoRA BUNNY nécessite deux forces ; le rendu basique utilise une seule force.")

    @classmethod
    def from_dict(cls, value: dict | None) -> H3VideoLoraStack | None:
        if value is None:
            return None
        data = dict(value)
        data["entries"] = tuple(H3VideoLoraSlot(**entry) for entry in data.get("entries", ()))
        return cls(**data)


def validate_video_lora_stack(stack, legacy, per_pass: bool) -> None:
    if stack is None:
        return
    if not isinstance(stack, H3VideoLoraStack):
        raise TypeError("video_loras must be H3VideoLoraStack or None")
    if legacy is not None:
        raise ValueError("Utilisez la configuration LoRA unique ou multiple, pas les deux simultanément.")
    stack.validate_mode(per_pass)


@dataclass(frozen=True, slots=True)
class H3RenderTurn:
    turn_id: str
    role: H3RenderTurnRole
    content: str
    prompt: str | None = None
    questions: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    revision_version: H3RenderRevisionVersion | None = None
    model_id: str | None = None

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
        if self.model_id is not None:
            _text(self.model_id, "model_id")
        if self.role is H3RenderTurnRole.USER and self.model_id is not None:
            raise ValueError("user turns cannot own a model ID")


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
    spectrum_enabled: bool = False
    video_lora: H3VideoLoraSelection | None = None
    status: H3RenderAttemptStatus = H3RenderAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    keyframes: tuple[H3RenderKeyframe, ...] = ()
    error: str | None = None
    warnings: tuple[str, ...] = ()
    initial_megapixels: float = 0.2
    dlss: DlssResult | None = None
    recipe: RecipeRef | None = None
    bunny: H3BunnySettings | None = None
    checkpoint: str | None = None
    model_loading: H3ModelLoading | None = None
    video_loras: H3VideoLoraStack | None = None
    force_upscale: bool = False
    upscale_bypassed: bool = False

    def __post_init__(self) -> None:
        validate_h3_model_selection(self.checkpoint, self.model_loading)
        _text(self.attempt_id, "attempt_id")
        validate_h3_initial_megapixels(self.initial_megapixels)
        if not isinstance(self.settings, VideoLabSettings):
            raise TypeError("settings must be VideoLabSettings")
        if self.recipe is not None and not isinstance(self.recipe, RecipeRef):
            raise TypeError("recipe must be a RecipeRef or None")
        is_bunny = self.recipe is not None and self.recipe.recipe_id == BUNNY_RECIPE_ID
        validate_video_lora_stack(self.video_loras, self.video_lora, is_bunny)
        if is_bunny != (self.bunny is not None):
            raise ValueError("Les réglages BUNNY doivent appartenir à une recette BUNNY.")
        if self.bunny is not None:
            if not isinstance(self.bunny, H3BunnySettings):
                raise TypeError("bunny must be H3BunnySettings")
            if self.spectrum_enabled or (self.video_lora and self.video_lora.clip_last_layer is not None):
                raise ValueError("BUNNY ne prend pas en charge Spectrum ou CLIP Last Layer.")
            if self.settings.steps != self.bunny.coarse_steps + self.bunny.refine_steps:
                raise ValueError("Les steps BUNNY doivent correspondre au total des deux passes.")
            bunny_geometry(self.settings, self.initial_megapixels)
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("attempt index must be positive")
        _text(self.prompt, "prompt")
        _text(self.effective_prompt, "effective_prompt")
        if not isinstance(self.music_enabled, bool):
            raise TypeError("music_enabled must be a boolean")
        if not isinstance(self.spectrum_enabled, bool):
            raise TypeError("spectrum_enabled must be a boolean")
        if type(self.force_upscale) is not bool:
            raise TypeError("force_upscale must be a boolean")
        if type(self.upscale_bypassed) is not bool:
            raise TypeError("upscale_bypassed must be a boolean")
        if self.force_upscale and self.upscale_bypassed:
            raise ValueError("forced upscale and bypass cannot both be active")
        if is_bunny and self.force_upscale:
            raise ValueError("BUNNY ne prend pas en charge le forçage de l’upscale.")
        if is_bunny and self.upscale_bypassed:
            raise ValueError("BUNNY does not use the automatic upscale bypass")
        if not is_bunny:
            h3_upscale_plan(
                self.settings,
                self.initial_megapixels,
                force_upscale=self.force_upscale,
            )
        if self.video_lora is not None and not isinstance(
            self.video_lora, H3VideoLoraSelection
        ):
            raise TypeError("video_lora must be an H3VideoLoraSelection or None")
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
            warnings=tuple(dict.fromkeys((*self.warnings, *warnings))),
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
        if self.dlss is not None:
            validate_dlss_attempt(self)
            return
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
class H3RenderSetup:
    settings: VideoLabSettings
    initial_megapixels: float
    music_enabled: bool
    spectrum_enabled: bool
    video_lora: H3VideoLoraSelection | None
    recipe: RecipeRef
    bunny: H3BunnySettings | None = None
    checkpoint: str | None = None
    model_loading: H3ModelLoading | None = None
    video_loras: H3VideoLoraStack | None = None
    force_upscale: bool = False

    def __post_init__(self) -> None:
        validate_h3_model_selection(self.checkpoint, self.model_loading)
        if not isinstance(self.settings, VideoLabSettings) or not isinstance(self.recipe, RecipeRef):
            raise TypeError("invalid render setup")
        validate_video_lora_stack(self.video_loras, self.video_lora, self.recipe.recipe_id == BUNNY_RECIPE_ID)
        validate_h3_initial_megapixels(self.initial_megapixels)
        if type(self.music_enabled) is not bool or type(self.spectrum_enabled) is not bool:
            raise TypeError("render switches must be booleans")
        if type(self.force_upscale) is not bool:
            raise TypeError("force_upscale must be a boolean")
        if self.video_lora is not None and not isinstance(self.video_lora, H3VideoLoraSelection):
            raise TypeError("invalid video LoRA")
        if (self.recipe.recipe_id == BUNNY_RECIPE_ID) != (self.bunny is not None):
            raise ValueError("render setup recipe and BUNNY parameters disagree")
        if self.bunny is not None:
            if not isinstance(self.bunny, H3BunnySettings):
                raise TypeError("invalid BUNNY settings")
            if self.settings.steps != self.bunny.coarse_steps + self.bunny.refine_steps:
                raise ValueError("render steps must match the BUNNY schedule")
            bunny_geometry(self.settings, self.initial_megapixels)
            if self.spectrum_enabled or (self.video_lora and self.video_lora.clip_last_layer is not None):
                raise ValueError("BUNNY does not support Spectrum or CLIP last layer")
            if self.force_upscale:
                raise ValueError("BUNNY does not support forced upscale")
        else:
            h3_upscale_plan(
                self.settings,
                self.initial_megapixels,
                force_upscale=self.force_upscale,
            )


@dataclass(frozen=True, slots=True)
class H3Ref2VAdaptation:
    request_id: str
    source_project_id: str
    source_prompt: str
    reference_roles: tuple[str, ...]
    render_setup: H3RenderSetup
    status: str = "pending"
    raw_response: str | None = None
    error: str | None = None
    call_id: str | None = None
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        for value in (self.request_id, self.source_project_id, self.source_prompt):
            _text(value, "adaptation source")
        if self.version != "1.0.0" or self.status not in {"pending", "running", "ready", "failed"}:
            raise ValueError("invalid adaptation version or status")
        if not isinstance(self.render_setup, H3RenderSetup):
            raise TypeError("invalid adaptation render setup")
        if not isinstance(self.reference_roles, tuple) or not self.reference_roles or any(
            role not in {"first_frame", "last_frame", "subject_reference"} for role in self.reference_roles
        ):
            raise ValueError("invalid adaptation reference roles")


@dataclass(frozen=True, slots=True)
class H3RenderProject:
    project_id: str
    source_session_id: str
    source_prompt_revision_id: str
    model_id: str
    input_mode: H3RenderInputMode
    current_prompt: str
    revision_model_id: str | None = None
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
    dialogue_level: int = 0
    adaptation: H3Ref2VAdaptation | None = None
    reference_parent_project_id: str | None = None
    preparation: VideoPreparationRef = VideoPreparationRef()
    combat_settings: CombatSettings | None = None
    cinematic_settings: ClassicCinematicSettings | None = None
    sensual_settings: SensualSettings | None = None
    localization_parent_project_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.preparation, VideoPreparationRef):
            raise TypeError("preparation must be a VideoPreparationRef")
        validate_combat_settings(self.preparation, self.combat_settings)
        validate_cinematic_settings(self.preparation, self.cinematic_settings)
        validate_sensual_settings(self.preparation, self.sensual_settings)
        if type(self.dialogue_level) is not int or not 0 <= self.dialogue_level <= 3:
            raise ValueError("dialogue_level must be between 0 and 3")
        if self.localization_parent_project_id is not None:
            _text(self.localization_parent_project_id, "localization_parent_project_id")
            if self.localization_parent_project_id == self.project_id:
                raise ValueError("localization parent must be another project")
        if self.reference_parent_project_id is not None:
            _text(self.reference_parent_project_id, "reference_parent_project_id")
            if self.reference_parent_project_id == self.project_id:
                raise ValueError("reference parent must be another project")
        if self.adaptation is not None:
            if not isinstance(self.adaptation, H3Ref2VAdaptation) or self.input_mode is not H3RenderInputMode.REF2VA:
                raise TypeError("adaptations require a REF2VA project")
            if len(self.adaptation.reference_roles) != len(self.reference_asset_ids):
                raise ValueError("adaptation roles disagree with its reference images")
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
        if self.revision_model_id is not None:
            _text(self.revision_model_id, "revision_model_id")
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
        validate_dlss_lineage(self.attempts)
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
        _strings(self.camera_clauses, "camera_clauses", maximum=12 if self.preparation.uses_cinematic_phases else 8)
        if self.revision_version is not None and self.preparation.is_combat != (
            self.revision_version in {H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3}
        ):
            raise ValueError("revision version belongs to a different preparation family")
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
        if self.revision_draft_version is not None and self.preparation.is_combat != (
            self.revision_draft_version in {H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3}
        ):
            raise ValueError("revision draft belongs to a different preparation family")
        for version in (self.revision_version, self.revision_draft_version):
            if version is not None and self.preparation.is_classic_cinematic != (version is H3RenderRevisionVersion.CLASSIC_CINEMATIC):
                raise ValueError("Classic cinematic revisions must keep their pinned preparation")
            if version is not None and self.preparation.is_sensual != (version is H3RenderRevisionVersion.SENSUAL):
                raise ValueError("Sensual revisions must keep their pinned preparation")
        if self.preparation.is_combat and any(version is not None and version.value != self.preparation.version
                                             for version in (self.revision_version, self.revision_draft_version)):
            raise ValueError("Combat revisions must keep the saved preparation version")

    def add_turn(self, turn: H3RenderTurn) -> H3RenderProject:
        if any(value.turn_id == turn.turn_id for value in self.turns):
            raise ValueError("turn already exists")
        prompt = turn.prompt if turn.role is H3RenderTurnRole.ASSISTANT and turn.prompt else self.current_prompt
        clear_draft = turn.role is H3RenderTurnRole.ASSISTANT
        return replace(
            self,
            turns=(*self.turns, turn),
            current_prompt=prompt,
            revision_model_id=(
                turn.model_id
                if turn.role is H3RenderTurnRole.ASSISTANT and turn.model_id
                else self.revision_model_id
            ),
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

    def select_revision_model(self, model_id: str) -> H3RenderProject:
        return replace(
            self,
            revision_model_id=_text(model_id, "revision_model_id"),
        )

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
    return derive_h3_render_input_mode(first is not None, last is not None)


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
    "H3_VIDEO_LORA_OVERLAY_VERSION",
    "H3_VIDEO_LORA_PREFIX",
    "H3RenderAttempt",
    "H3RenderAttemptStatus",
    "H3RenderInputMode",
    "H3RenderKeyframe",
    "H3RenderProject",
    "H3RenderTurn",
    "H3RenderTurnRole",
    "H3VideoLoraSelection",
    "VideoAspectRatio",
    "VideoLabSettings",
    "canonical_h3_video_lora_name",
]
