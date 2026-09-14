"""Pure contracts for iterative KREA2 image editing."""

from __future__ import annotations

from .edit_subject_reference import EditSubjectReference
from .dlss import DlssResult, validate_dlss_attempt, validate_dlss_lineage

from .krea2_edit_versions import Krea2EditRevision

from dataclasses import dataclass, replace
from enum import StrEnum
import math
import re

from .krea2_batch import Krea2LoraSelection, Krea2PromptLanguage
from .krea2_lab import Krea2AspectRatio, Krea2LabSettings
from .recipes import RecipeRef
from .firered_edit import FireRedEditSettings


_SHA256 = re.compile(r"[0-9a-f]{64}")
KREA2_EDIT_REF_BOOST_MAX = 1000.0


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
    ref_boost: float | None = None
    steps: int | None = None
    firered_settings: FireRedEditSettings | None = None

    def __post_init__(self) -> None:
        if self.firered_settings is not None and not isinstance(self.firered_settings, FireRedEditSettings):
            raise TypeError("firered_settings must be FireRedEditSettings")
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
        if not isinstance(self.loras, tuple) or len(self.loras) > 10:
            raise ValueError("metadata supports at most ten LoRAs")
        if any(not isinstance(value, Krea2LoraSelection) for value in self.loras):
            raise TypeError("metadata loras must contain Krea2LoraSelection values")
        _text(self.origin, "metadata origin")
        if self.ref_boost is not None:
            _finite_range(self.ref_boost, "ref_boost", 0.0, KREA2_EDIT_REF_BOOST_MAX)
        if self.steps is not None and (
            isinstance(self.steps, bool) or not isinstance(self.steps, int) or not 1 <= self.steps <= 100
        ):
            raise ValueError("steps must be an integer between 1 and 100")
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
        _finite_range(self.ref_boost, "ref_boost", 0.0, KREA2_EDIT_REF_BOOST_MAX)
        if isinstance(self.steps, bool) or not isinstance(self.steps, int):
            raise TypeError("steps must be an integer")
        if not 1 <= self.steps <= 100:
            raise ValueError("steps must be between 1 and 100")
        if not isinstance(self.loras, tuple) or len(self.loras) > 10:
            raise ValueError("at most ten general LoRAs are supported")
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


def validate_retouch_harmonization(enabled: bool, strength: int) -> None:
    if not isinstance(enabled, bool):
        raise ValueError("L’harmonisation doit être activée ou désactivée.")
    if type(strength) is not int or not 0 <= strength <= 100:
        raise ValueError("L’intensité d’harmonisation doit être un entier entre 0 et 100.")


@dataclass(frozen=True, slots=True)
class Krea2EditRetouch:
    """Immutable provenance; every composition uses the original generation."""

    original_attempt_id: str
    parent_attempt_id: str
    source_asset_id: str
    generated_asset_id: str
    mask_asset_id: str
    width: int
    height: int
    request_id: str
    submitted_mask_sha256: str
    version: str = "1.0.0"
    harmonize: bool = False
    harmonize_strength: int = 100
    color_method: str = "reinhard_lab_rgb@1.0.0"

    def __post_init__(self) -> None:
        validate_retouch_harmonization(self.harmonize, self.harmonize_strength)
        if self.color_method != "reinhard_lab_rgb@1.0.0":
            raise ValueError("unsupported retouch color method")
        for name in ("original_attempt_id", "parent_attempt_id", "source_asset_id",
                     "generated_asset_id", "mask_asset_id", "request_id"):
            _text(getattr(self, name), name)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("invalid retouch request_id")
        for value in (self.width, self.height):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("retouch dimensions must be positive integers")
        if self.width * self.height > 16_000_000:
            raise ValueError("retouch exceeds 16 MP")
        _digest(self.submitted_mask_sha256, "submitted_mask_sha256")
        if self.version != "1.0.0":
            raise ValueError("unsupported retouch version")


@dataclass(frozen=True, slots=True)
class Krea2EditUpscale:
    """An enhancement always starts from the original generation, before masking."""

    original_attempt_id: str
    parent_attempt_id: str
    input_asset_id: str
    model_name: str
    request_id: str
    workflow: RecipeRef
    width: int
    height: int
    mask_asset_id: str | None = None
    harmonize: bool = False
    harmonize_strength: int = 100
    enhanced_asset_id: str | None = None
    color_method: str = "reinhard_lab_rgb@1.0.0"
    preserve_source_size: bool = True

    def __post_init__(self) -> None:
        if type(self.preserve_source_size) is not bool:
            raise ValueError("invalid upscale size policy")
        for name in ("original_attempt_id", "parent_attempt_id", "input_asset_id", "model_name", "request_id"):
            _text(getattr(self, name), name)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("invalid upscale request_id")
        if not isinstance(self.workflow, RecipeRef) or self.workflow.operation_id != "image.upscale":
            raise ValueError("invalid upscale workflow")
        if any(type(v) is not int or v < 1 for v in (self.width, self.height)) or self.width * self.height > 16_000_000:
            raise ValueError("upscale target must fit within 16 MP")
        for value in (self.mask_asset_id, self.enhanced_asset_id):
            if value is not None:
                _text(value, "upscale asset")
        validate_retouch_harmonization(self.harmonize, self.harmonize_strength)
        if self.color_method != "reinhard_lab_rgb@1.0.0":
            raise ValueError("unsupported upscale color method")


@dataclass(frozen=True, slots=True)
class Krea2EditCrop:
    """Rectangle in the oriented source's native pixels; no render is involved."""

    request_id: str
    source_asset_id: str
    restart_count: int
    source_width: int
    source_height: int
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("Identifiant de recadrage invalide.")
        _text(self.source_asset_id, "crop source")
        for name in ("restart_count", "x", "y", "width", "height", "source_width", "source_height"):
            value = getattr(self, name)
            minimum = 0 if name in {"restart_count", "x", "y"} else 1
            if type(value) is not int or value < minimum:
                raise ValueError("Le rectangle doit utiliser des coordonnées entières valides.")
        if self.x + self.width > self.source_width or self.y + self.height > self.source_height:
            raise ValueError("Le rectangle dépasse les limites de l’image.")


@dataclass(frozen=True, slots=True)
class Krea2EditAttempt:
    attempt_id: str
    prompt: str
    settings: Krea2EditSettings | FireRedEditSettings
    status: Krea2EditAttemptStatus = Krea2EditAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None
    kind: str = "generation"
    retouch: Krea2EditRetouch | None = None
    recipe: RecipeRef | None = None
    upscale: Krea2EditUpscale | None = None
    output_dimensions: tuple[int, int] | None = None
    dlss: DlssResult | None = None
    crop: Krea2EditCrop | None = None

    def __post_init__(self) -> None:
        _text(self.attempt_id, "attempt_id")
        if self.recipe is not None and not isinstance(self.recipe, RecipeRef):
            raise TypeError("attempt recipe must be RecipeRef")
        _text(self.prompt, "attempt prompt")
        if not isinstance(self.settings, (Krea2EditSettings, FireRedEditSettings)):
            raise TypeError("settings must belong to a supported image-edit engine")
        if isinstance(self.settings, FireRedEditSettings) and (
                self.recipe is None or self.recipe.operation_id != "image.edit"
                or self.recipe.recipe_id != "firered.image_edit"):
            raise ValueError("FireRed settings require a FireRed recipe")
        if isinstance(self.settings, Krea2EditSettings) and self.recipe is not None and self.recipe.recipe_id == "firered.image_edit":
            raise ValueError("A FireRed recipe cannot use KREA2 settings")
        if self.output_dimensions is not None:
            if (not isinstance(self.output_dimensions, tuple) or len(self.output_dimensions) != 2
                    or any(type(v) is not int or v < 1 for v in self.output_dimensions)
                    or self.status is not Krea2EditAttemptStatus.SUCCEEDED):
                raise ValueError("output_dimensions require a successful image and positive dimensions")
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

    def succeed(self, asset_id: str, *, dimensions: tuple[int, int] | None = None) -> Krea2EditAttempt:
        if self.status not in {
            Krea2EditAttemptStatus.RUNNING,
            Krea2EditAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only an active attempt can succeed")
        return replace(
            self,
            status=Krea2EditAttemptStatus.SUCCEEDED,
            output_asset_id=_text(asset_id, "output_asset_id"),
            output_dimensions=dimensions,
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
        if self.kind == "crop":
            if (not isinstance(self.crop, Krea2EditCrop)
                    or self.status is not Krea2EditAttemptStatus.SUCCEEDED
                    or self.output_asset_id is None
                    or self.output_dimensions != (self.crop.width, self.crop.height)
                    or any(value is not None for value in (self.execution_id, self.compiled_workflow_sha256,
                                                          self.error, self.retouch, self.upscale, self.dlss))):
                raise ValueError("crop requires a local image and rectangle, without a GPU execution")
            return
        if self.crop is not None:
            raise ValueError("crop provenance requires a crop attempt")
        if self.upscale is not None and not isinstance(self.upscale, Krea2EditUpscale):
            raise ValueError("invalid upscale provenance")
        if (self.kind == "upscale") != isinstance(self.upscale, Krea2EditUpscale):
            raise ValueError("invalid upscale provenance")
        if self.upscale and ((self.status is Krea2EditAttemptStatus.SUCCEEDED) != (self.upscale.enhanced_asset_id is not None)):
            raise ValueError("only a successful upscale has an enhanced image")
        if self.dlss is not None:
            validate_dlss_attempt(self)
            if self.kind != "upscale" or self.retouch is not None or self.upscale.workflow.recipe_id != "image.upscale.dlss":
                raise ValueError("invalid DLSS image provenance")
            if ((self.dlss.width, self.dlss.height) != (self.upscale.width, self.upscale.height)
                    or self.dlss.parent_attempt_id != self.upscale.parent_attempt_id
                    or self.dlss.input_asset_id != self.upscale.input_asset_id
                    or (self.dlss.size == "source") != self.upscale.preserve_source_size):
                raise ValueError("inconsistent DLSS image provenance")
            return
        if self.upscale and not self.upscale.preserve_source_size:
            raise ValueError("native-size finishing requires DLSS provenance")
        if self.kind == "retouch":
            if (not isinstance(self.retouch, Krea2EditRetouch)
                    or self.status is not Krea2EditAttemptStatus.SUCCEEDED
                    or self.output_asset_id is None
                    or any(value is not None for value in
                           (self.execution_id, self.compiled_workflow_sha256, self.error))):
                raise ValueError("retouch requires a local result and provenance, without a GPU execution")
            return
        if self.kind not in {"generation", "upscale"} or self.retouch is not None:
            raise ValueError("invalid edit attempt kind or provenance")
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
    assistant_message: str | None = None
    assistance_version: str = "1.0.0"
    render_engine: str = "krea2"

    def __post_init__(self) -> None:
        if self.render_engine not in {"krea2", "firered"}:
            raise ValueError("unsupported edit prompt engine")
        _text(self.revision_id, "revision_id")
        _text(self.instruction, "revision instruction")
        if self.base_prompt is not None:
            _text(self.base_prompt, "revision base_prompt")
        _text(self.prompt, "revision prompt")
        _text(self.model_id, "revision model_id")
        if self.assistant_message is not None:
            _text(self.assistant_message, "assistant_message")
        if self.assistance_version not in {"1.0.0", "2.0.0", "3.0.0"}:
            raise ValueError("unsupported edit assistance version")
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
    restart_count: int = 0
    revision: Krea2EditRevision | None = None
    copied_from_source_id: str | None = None
    revision_activation: int = 0
    subject_reference: EditSubjectReference | None = None

    def __post_init__(self) -> None:
        _text(self.source_id, "source_id")
        if self.subject_reference is not None and not isinstance(self.subject_reference, EditSubjectReference):
            raise TypeError("subject_reference must be an EditSubjectReference")
        if type(self.restart_count) is not int or self.restart_count < 0:
            raise ValueError("restart_count must be a non-negative integer")
        if self.project_id is None:
            object.__setattr__(self, "project_id", self.source_id)
        _text(self.project_id, "project_id")
        if self.revision is not None:
            if not isinstance(self.revision, Krea2EditRevision):
                raise TypeError("revision must be Krea2EditRevision")
            if self.project_id in {self.revision.family_id, self.revision.source_project_id}:
                raise ValueError("a revised chain must own a distinct project")
        if self.copied_from_source_id is not None:
            _text(self.copied_from_source_id, "copied_from_source_id")
            if self.revision is None:
                raise ValueError("a copied stage requires revision provenance")
        if type(self.revision_activation) is not int or self.revision_activation < 0:
            raise ValueError("revision_activation must be a non-negative integer")
        if self.revision_activation and (
            self.revision is None or self.stage_index != self.revision.stage_index
            or self.accepted_attempt_id is None
        ):
            raise ValueError("only the validated resumed stage can activate a revision")
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
        validate_dlss_lineage(self.attempts)
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("attempt ids must be unique")
        previous: dict[str, Krea2EditAttempt] = {}
        request_ids: set[str] = set()
        for attempt in self.attempts:
            if attempt.crop:
                if attempt.crop.source_asset_id != self.source_asset_id or attempt.crop.request_id in request_ids:
                    raise ValueError("crop must reference its stage source and a unique request")
                request_ids.add(attempt.crop.request_id)
            if attempt.upscale is not None:
                info = attempt.upscale
                original = previous.get(info.original_attempt_id)
                parent = previous.get(info.parent_attempt_id)
                if (original is None or original.kind != "generation"
                        or original.status is not Krea2EditAttemptStatus.SUCCEEDED
                        or parent is None or parent.status is not Krea2EditAttemptStatus.SUCCEEDED
                        or info.input_asset_id != (original.output_asset_id if info.preserve_source_size else parent.output_asset_id)
                        or attempt.prompt != original.prompt or attempt.settings != original.settings):
                    raise ValueError("upscale must reference its original successful generation")
                ancestor = parent
                while ancestor.kind != "generation":
                    ancestor = previous[ancestor.upscale.original_attempt_id if ancestor.upscale
                                        else ancestor.retouch.original_attempt_id]
                inherited_mask = (parent.retouch or parent.upscale) if info.preserve_source_size else None
                if (ancestor.attempt_id != original.attempt_id
                        or info.mask_asset_id != (inherited_mask.mask_asset_id if inherited_mask else None)
                        or info.harmonize != (inherited_mask.harmonize if inherited_mask else False)
                        or info.harmonize_strength != (inherited_mask.harmonize_strength if inherited_mask else 100)):
                    raise ValueError("upscale must preserve the selected candidate mask and ancestry")
                if info.request_id in request_ids:
                    raise ValueError("duplicate upscale request_id")
                request_ids.add(info.request_id)
            if attempt.retouch is not None:
                retouch = attempt.retouch
                original = previous.get(retouch.original_attempt_id)
                parent = previous.get(retouch.parent_attempt_id)
                if (original is None or original.kind not in {"generation", "upscale"}
                        or original.status is not Krea2EditAttemptStatus.SUCCEEDED
                        or parent is None or parent.status is not Krea2EditAttemptStatus.SUCCEEDED
                        or retouch.source_asset_id != self.source_asset_id
                        or retouch.generated_asset_id != (original.upscale.enhanced_asset_id if original.upscale else original.output_asset_id)
                        or attempt.prompt != original.prompt or attempt.settings != original.settings
                        or (parent.retouch.original_attempt_id if parent.retouch else parent.attempt_id)
                        != original.attempt_id):
                    raise ValueError("retouch must reference its stage source and original successful generation")
                if retouch.request_id in request_ids:
                    raise ValueError("duplicate retouch request_id")
                request_ids.add(retouch.request_id)
            previous[attempt.attempt_id] = attempt
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

    def restart(self) -> Krea2EditSource:
        if self.state is not Krea2EditSourceState.PENDING or self.accepted_attempt_id is not None:
            raise ValueError("Seule l’étape en cours peut être recommencée. Les étapes validées sont figées.")
        if self.prompt_status is Krea2EditPromptStatus.GENERATING or any(
            attempt.status in {Krea2EditAttemptStatus.QUEUED, Krea2EditAttemptStatus.RUNNING,
                               Krea2EditAttemptStatus.CANCEL_PENDING} for attempt in self.attempts
        ):
            raise ValueError("Attends la fin de l’échange ou du rendu avant de recommencer cette étape.")
        return replace(self, instruction="", generated_prompt=None, raw_prompt_response=None,
                       prompt_model_id=None, prompt_error=None, prompt_status=Krea2EditPromptStatus.IDLE,
                       revisions=(), attempts=(), restart_count=self.restart_count + 1)

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

    def attempt_label(self, attempt_id: str) -> str:
        generations = [value for value in self.attempts if value.kind == "generation"]
        attempt = next(value for value in self.attempts if value.attempt_id == attempt_id)
        if attempt.crop:
            return "Recadrage"
        if attempt.upscale:
            variants = [value for value in self.attempts if value.upscale
                        and value.upscale.parent_attempt_id == attempt.upscale.parent_attempt_id]
            revision = next(i + 1 for i, value in enumerate(variants) if value.attempt_id == attempt_id)
            treatment = "DLSS" if attempt.dlss else "Amélioré"
            return f"{self.attempt_label(attempt.upscale.parent_attempt_id)} — {treatment} {revision}"
        original_id = attempt.retouch.original_attempt_id if attempt.retouch else attempt_id
        if attempt.retouch is None:
            number = next(i + 1 for i, value in enumerate(generations) if value.attempt_id == original_id)
            return f"Essai {number}"
        variants = [value for value in self.attempts
                    if value.retouch and value.retouch.original_attempt_id == original_id]
        revision = next(i + 1 for i, value in enumerate(variants) if value.attempt_id == attempt_id)
        return f"{self.attempt_label(original_id)} — Retouche {revision}"

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
