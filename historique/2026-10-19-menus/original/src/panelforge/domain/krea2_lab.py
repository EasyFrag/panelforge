"""Pure contracts for KREA2 text-to-image renders."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import math
import re

from .recipes import RecipeRef


KREA2_RESOLUTION_MULTIPLE = 8
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class Krea2AspectRatio(StrEnum):
    """Aspect-ratio values accepted by ComfyUI's ResolutionSelector."""

    SQUARE = "1:1 (Square)"
    PORTRAIT_PHOTO = "2:3 (Portrait Photo)"
    PHOTO = "3:2 (Photo)"
    PORTRAIT_STANDARD = "3:4 (Portrait Standard)"
    STANDARD = "4:3 (Standard)"
    PORTRAIT_WIDESCREEN = "9:16 (Portrait Widescreen)"
    WIDESCREEN = "16:9 (Widescreen)"
    ULTRAWIDE = "21:9 (Ultrawide)"

    @property
    def dimensions(self) -> tuple[int, int]:
        width, height = self.value.split(" ", 1)[0].split(":", 1)
        return int(width), int(height)


class Krea2LabRunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def normalize_krea2_model_name(value: str) -> str:
    """Compare ComfyUI model paths without rewriting the server value."""
    _require_text(value, "model_name")
    return value.strip().replace("\\", "/").casefold()


@dataclass(frozen=True, slots=True)
class Krea2LabSettings:
    """Validated KREA2 controls and their deterministic pixel dimensions."""

    model_name: str
    aspect_ratio: Krea2AspectRatio
    megapixels: float
    seed: int
    seed_locked: bool = False

    def __post_init__(self) -> None:
        _require_text(self.model_name, "model_name")
        if not isinstance(self.aspect_ratio, Krea2AspectRatio):
            raise TypeError("aspect_ratio must be a Krea2AspectRatio")
        _require_finite_range(self.megapixels, "megapixels", 0.5, 4.0)
        if not math.isclose(self.megapixels * 10, round(self.megapixels * 10)):
            raise ValueError("megapixels must use increments of 0.1")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if not isinstance(self.seed_locked, bool):
            raise TypeError("seed_locked must be a boolean")

    @property
    def resolution(self) -> tuple[int, int]:
        width_ratio, height_ratio = self.aspect_ratio.dimensions
        total_pixels = self.megapixels * 1024 * 1024
        scale = math.sqrt(total_pixels / (width_ratio * height_ratio))
        width = round(width_ratio * scale / KREA2_RESOLUTION_MULTIPLE)
        height = round(height_ratio * scale / KREA2_RESOLUTION_MULTIPLE)
        return (
            width * KREA2_RESOLUTION_MULTIPLE,
            height * KREA2_RESOLUTION_MULTIPLE,
        )


@dataclass(frozen=True, slots=True)
class Krea2LabRun:
    """Persistent state of one independently managed KREA2 render."""

    run_id: str
    recipe: RecipeRef
    preset_id: str
    prompt: str
    settings: Krea2LabSettings
    status: Krea2LabRunStatus
    source_storyboard_run_id: str | None = None
    source_prompt_sha256: str | None = None
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        recipe: RecipeRef,
        preset_id: str,
        prompt: str,
        settings: Krea2LabSettings,
        source_storyboard_run_id: str | None = None,
        source_prompt_sha256: str | None = None,
    ) -> Krea2LabRun:
        return cls(
            run_id=run_id,
            recipe=recipe,
            preset_id=preset_id,
            prompt=prompt,
            settings=settings,
            status=Krea2LabRunStatus.CREATED,
            source_storyboard_run_id=source_storyboard_run_id,
            source_prompt_sha256=source_prompt_sha256,
        )

    def queue(self) -> Krea2LabRun:
        self._require_status(Krea2LabRunStatus.CREATED, "queue")
        return replace(self, status=Krea2LabRunStatus.QUEUED)

    def start(
        self,
        execution_id: str,
        compiled_workflow_sha256: str,
    ) -> Krea2LabRun:
        self._require_status(Krea2LabRunStatus.QUEUED, "start")
        return replace(
            self,
            status=Krea2LabRunStatus.RUNNING,
            execution_id=_require_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_require_sha256(
                compiled_workflow_sha256,
                "compiled_workflow_sha256",
            ),
        )

    def succeed(self, output_asset_id: str) -> Krea2LabRun:
        if self.status not in {
            Krea2LabRunStatus.RUNNING,
            Krea2LabRunStatus.CANCEL_PENDING,
        }:
            raise ValueError(f"cannot succeed a {self.status.value} run")
        return replace(
            self,
            status=Krea2LabRunStatus.SUCCEEDED,
            output_asset_id=_require_text(output_asset_id, "output_asset_id"),
            error=None,
        )

    def fail(self, error: str) -> Krea2LabRun:
        if self.status not in {
            Krea2LabRunStatus.CREATED,
            Krea2LabRunStatus.QUEUED,
            Krea2LabRunStatus.RUNNING,
            Krea2LabRunStatus.CANCEL_PENDING,
        }:
            raise ValueError(f"cannot fail a {self.status.value} run")
        return replace(
            self,
            status=Krea2LabRunStatus.FAILED,
            error=_require_text(error, "error"),
        )

    def cancel(self) -> Krea2LabRun:
        if self.status not in {
            Krea2LabRunStatus.CREATED,
            Krea2LabRunStatus.QUEUED,
            Krea2LabRunStatus.RUNNING,
            Krea2LabRunStatus.CANCEL_PENDING,
        }:
            raise ValueError(f"cannot cancel a {self.status.value} run")
        return replace(
            self,
            status=Krea2LabRunStatus.CANCELLED,
            error=None,
        )

    def mark_cancel_pending(self, error: str) -> Krea2LabRun:
        self._require_status(
            Krea2LabRunStatus.RUNNING,
            "mark cancellation pending",
        )
        return replace(
            self,
            status=Krea2LabRunStatus.CANCEL_PENDING,
            error=_require_text(error, "error"),
        )

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if not isinstance(self.recipe, RecipeRef):
            raise TypeError("recipe must be a RecipeRef")
        _require_text(self.preset_id, "preset_id")
        _require_text(self.prompt, "prompt")
        if not isinstance(self.settings, Krea2LabSettings):
            raise TypeError("settings must be Krea2LabSettings")
        if not isinstance(self.status, Krea2LabRunStatus):
            raise TypeError("status must be a Krea2LabRunStatus")
        if self.source_storyboard_run_id is not None:
            _require_text(
                self.source_storyboard_run_id,
                "source_storyboard_run_id",
            )
        if self.source_prompt_sha256 is not None:
            _require_sha256(self.source_prompt_sha256, "source_prompt_sha256")
            actual_prompt_hash = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
            if self.source_prompt_sha256 != actual_prompt_hash:
                raise ValueError("source_prompt_sha256 does not match prompt")
        if self.execution_id is not None:
            _require_text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None:
            _require_sha256(
                self.compiled_workflow_sha256,
                "compiled_workflow_sha256",
            )
        if self.output_asset_id is not None:
            _require_text(self.output_asset_id, "output_asset_id")
        if self.error is not None:
            _require_text(self.error, "error")
        self._validate_state()

    def _validate_state(self) -> None:
        if self.status in {
            Krea2LabRunStatus.CREATED,
            Krea2LabRunStatus.QUEUED,
        }:
            if any(
                value is not None
                for value in (
                    self.execution_id,
                    self.compiled_workflow_sha256,
                    self.output_asset_id,
                    self.error,
                )
            ):
                raise ValueError(f"{self.status.value} run contains later-state fields")
            return
        if self.status is Krea2LabRunStatus.RUNNING:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("running run requires execution and workflow IDs")
            if self.output_asset_id is not None or self.error is not None:
                raise ValueError("running run contains terminal fields")
            return
        if self.status is Krea2LabRunStatus.SUCCEEDED:
            if (
                self.execution_id is None
                or self.compiled_workflow_sha256 is None
                or self.output_asset_id is None
            ):
                raise ValueError(
                    "succeeded run requires execution, workflow and output IDs"
                )
            if self.error is not None:
                raise ValueError("succeeded run cannot contain an error")
            return
        if self.status is Krea2LabRunStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed run requires only an error")
            return
        if self.status is Krea2LabRunStatus.CANCEL_PENDING:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError(
                    "cancel-pending run requires execution and workflow IDs"
                )
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("cancel-pending run requires only an error")
            return
        if self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled run cannot contain output or error")

    def _require_status(self, expected: Krea2LabRunStatus, action: str) -> None:
        if self.status is not expected:
            raise ValueError(f"cannot {action} a {self.status.value} run")


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


def _require_finite_range(
    value: object,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return number
