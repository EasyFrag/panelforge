"""Shared KREA2 render settings and validation of historical batch records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re

from .krea2_lab import Krea2AspectRatio, Krea2LabSettings


_SHA256 = re.compile(r"[0-9a-f]{64}")

# The community workflow uses ``Seed (rgthree)``, whose live ComfyUI schema
# caps integer inputs at 2**50. Keep this separate from the generic KREA2
# single-image seed range: that workflow uses a regular KSampler seed input.
KREA2_BATCH_RGTHREE_MAX_SEED = 2**50


class Krea2BatchStatus(StrEnum):
    CREATED = "created"
    GENERATING_PROMPTS = "generating_prompts"
    READY = "ready"
    RENDERING = "rendering"
    COMPLETED = "completed"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Krea2BatchItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Krea2ReviewDecision(StrEnum):
    NEUTRAL = "neutral"
    LIKE = "like"
    DISLIKE = "dislike"


class Krea2PromptLanguage(StrEnum):
    ENGLISH = "en"
    CHINESE_SIMPLIFIED = "zh"


@dataclass(frozen=True, slots=True)
class Krea2LoraSelection:
    name: str
    strength: float

    def __post_init__(self) -> None:
        _text(self.name, "lora name")
        if self.name.casefold() == "none":
            raise ValueError("a selected LoRA cannot be None")
        if isinstance(self.strength, bool) or not isinstance(self.strength, (int, float)):
            raise TypeError("LoRA strength must be a number")
        if not math.isfinite(float(self.strength)) or not -20 <= float(self.strength) <= 20:
            raise ValueError("LoRA strength must be between -20 and 20")


@dataclass(frozen=True, slots=True)
class Krea2BatchSettings:
    model_name: str
    aspect_ratio: Krea2AspectRatio
    megapixels: float
    loras: tuple[Krea2LoraSelection, ...] = ()

    def __post_init__(self) -> None:
        _text(self.model_name, "model_name")
        Krea2LabSettings(
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            seed=0,
        )
        if not isinstance(self.loras, tuple):
            raise TypeError("loras must be a tuple")
        if len(self.loras) > 10:
            raise ValueError("at most ten LoRAs are supported")
        seen: set[str] = set()
        for lora in self.loras:
            if not isinstance(lora, Krea2LoraSelection):
                raise TypeError("loras must contain Krea2LoraSelection values")
            normalized = lora.name.replace("\\", "/").casefold()
            if normalized in seen:
                raise ValueError("the same LoRA cannot be selected twice")
            seen.add(normalized)

    @property
    def resolution(self) -> tuple[int, int]:
        return Krea2LabSettings(
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            seed=0,
        ).resolution


@dataclass(frozen=True, slots=True)
class Krea2BatchItem:
    item_id: str
    index: int
    prompt: str
    variation_signature: str
    seed: int
    status: Krea2BatchItemStatus = Krea2BatchItemStatus.PENDING
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None
    review: Krea2ReviewDecision = Krea2ReviewDecision.NEUTRAL
    comment: str = ""

    def __post_init__(self) -> None:
        _text(self.item_id, "item_id")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("item index must be a positive integer")
        _text(self.prompt, "prompt")
        _text(self.variation_signature, "variation_signature")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed < 2**64:
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if not isinstance(self.status, Krea2BatchItemStatus):
            raise TypeError("status must be a Krea2BatchItemStatus")
        if self.execution_id is not None:
            _text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None:
            _digest(self.compiled_workflow_sha256, "compiled_workflow_sha256")
        if self.output_asset_id is not None:
            _text(self.output_asset_id, "output_asset_id")
        if self.error is not None:
            _text(self.error, "error")
        if not isinstance(self.review, Krea2ReviewDecision):
            raise TypeError("review must be a Krea2ReviewDecision")
        if not isinstance(self.comment, str):
            raise TypeError("comment must be a string")
        self._validate_state()


    def _validate_state(self) -> None:
        if self.status is Krea2BatchItemStatus.PENDING:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("pending item contains execution fields")
        elif self.status is Krea2BatchItemStatus.RUNNING:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("running item requires execution and workflow IDs")
            if self.output_asset_id is not None or self.error is not None:
                raise ValueError("running item contains terminal fields")
        elif self.status is Krea2BatchItemStatus.SUCCEEDED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None or self.output_asset_id is None or self.error is not None:
                raise ValueError("succeeded item is incomplete")
        elif self.status is Krea2BatchItemStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed item requires only an error")
        elif self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled item cannot contain output or error")


@dataclass(frozen=True, slots=True)
class Krea2Batch:
    batch_id: str
    recipe_id: str
    recipe_version: str
    recipe_sha256: str
    model_id: str
    image_count: int
    direction: str
    settings: Krea2BatchSettings
    status: Krea2BatchStatus
    items: tuple[Krea2BatchItem, ...] = ()
    raw_prompt_response: str | None = None
    warnings: tuple[str, ...] = ()
    error: str | None = None
    recipe_revision_draft: str | None = None
    recipe_workshop: str | None = None
    workshop_source_batch_id: str | None = None
    recipe_snapshot: str | None = None


    def __post_init__(self) -> None:
        for value, label in (
            (self.batch_id, "batch_id"),
            (self.recipe_id, "recipe_id"),
            (self.recipe_version, "recipe_version"),
            (self.model_id, "model_id"),
        ):
            _text(value, label)
        _digest(self.recipe_sha256, "recipe_sha256")
        if isinstance(self.image_count, bool) or not isinstance(self.image_count, int) or not 1 <= self.image_count <= 10:
            raise ValueError("image_count must be between 1 and 10")
        if not isinstance(self.direction, str):
            raise TypeError("direction must be a string")
        if not isinstance(self.settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        if not isinstance(self.status, Krea2BatchStatus):
            raise TypeError("status must be a Krea2BatchStatus")
        if not isinstance(self.items, tuple) or any(not isinstance(item, Krea2BatchItem) for item in self.items):
            raise TypeError("items must be a tuple of Krea2BatchItem")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("item IDs must be unique")
        if self.raw_prompt_response is not None and not isinstance(self.raw_prompt_response, str):
            raise TypeError("raw_prompt_response must be a string or None")
        if not isinstance(self.warnings, tuple) or any(not isinstance(w, str) or not w.strip() for w in self.warnings):
            raise TypeError("warnings must contain non-empty strings")
        if self.error is not None:
            _text(self.error, "error")
        if self.recipe_revision_draft is not None:
            _text(self.recipe_revision_draft, "recipe_revision_draft")
        if self.recipe_workshop is not None:
            _text(self.recipe_workshop, "recipe_workshop")
        if self.workshop_source_batch_id is not None:
            _text(self.workshop_source_batch_id, "workshop_source_batch_id")
            if self.workshop_source_batch_id == self.batch_id:
                raise ValueError("a workshop test batch cannot reference itself")
        if self.recipe_snapshot is not None:
            _text(self.recipe_snapshot, "recipe_snapshot")
        if (self.workshop_source_batch_id is None) != (self.recipe_snapshot is None):
            raise ValueError("workshop source and recipe snapshot must be set together")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value
