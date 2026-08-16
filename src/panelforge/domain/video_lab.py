"""Pure contracts for local video generation experiments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import math
import re

from .recipes import RecipeRef


VIDEO_FPS = 24
RESOLUTION_MULTIPLE = 32
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class VideoAspectRatio(StrEnum):
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


class VideoLabRunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class VideoLabSettings:
    """Validated controls and deterministic derived video properties."""

    aspect_ratio: VideoAspectRatio
    megapixels: float
    duration_seconds: float
    steps: int
    seed: int
    seed_locked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.aspect_ratio, VideoAspectRatio):
            raise TypeError("aspect_ratio must be a VideoAspectRatio")
        _require_finite_range(self.megapixels, "megapixels", 0.1, 16.0)
        if not math.isclose(self.megapixels * 10, round(self.megapixels * 10)):
            raise ValueError("megapixels must use increments of 0.1")
        _require_finite_range(
            self.duration_seconds,
            "duration_seconds",
            5.0,
            15.0,
        )
        if isinstance(self.steps, bool) or not isinstance(self.steps, int):
            raise TypeError("steps must be an integer")
        if not 1 <= self.steps <= 100:
            raise ValueError("steps must be between 1 and 100")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if not isinstance(self.seed_locked, bool):
            raise TypeError("seed_locked must be a boolean")

    @property
    def frame_count(self) -> int:
        requested = max(5, round(self.duration_seconds * VIDEO_FPS))
        return requested + (5 - requested % 17) % 17

    @property
    def effective_duration_seconds(self) -> float:
        return self.frame_count / VIDEO_FPS

    @property
    def resolution(self) -> tuple[int, int]:
        width_ratio, height_ratio = self.aspect_ratio.dimensions
        total_pixels = self.megapixels * 1024 * 1024
        scale = math.sqrt(total_pixels / (width_ratio * height_ratio))
        width = round(width_ratio * scale / RESOLUTION_MULTIPLE)
        height = round(height_ratio * scale / RESOLUTION_MULTIPLE)
        return width * RESOLUTION_MULTIPLE, height * RESOLUTION_MULTIPLE


@dataclass(frozen=True, slots=True)
class VideoLabRun:
    """Persistent state of one independently managed Video Lab render."""

    run_id: str
    recipe: RecipeRef
    preset_id: str
    source_asset_ids: tuple[str, ...]
    source_labels: tuple[str, ...]
    prompt: str
    settings: VideoLabSettings
    status: VideoLabRunStatus
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
        source_asset_ids: tuple[str, ...],
        source_labels: tuple[str, ...],
        prompt: str,
        settings: VideoLabSettings,
    ) -> VideoLabRun:
        return cls(
            run_id=run_id,
            recipe=recipe,
            preset_id=preset_id,
            source_asset_ids=source_asset_ids,
            source_labels=source_labels,
            prompt=prompt,
            settings=settings,
            status=VideoLabRunStatus.CREATED,
        )

    def queue(self) -> VideoLabRun:
        self._require_status(VideoLabRunStatus.CREATED, "queue")
        return replace(self, status=VideoLabRunStatus.QUEUED)

    def start(
        self,
        execution_id: str,
        compiled_workflow_sha256: str,
    ) -> VideoLabRun:
        self._require_status(VideoLabRunStatus.QUEUED, "start")
        return replace(
            self,
            status=VideoLabRunStatus.RUNNING,
            execution_id=_require_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_require_sha256(
                compiled_workflow_sha256,
                "compiled_workflow_sha256",
            ),
        )

    def succeed(self, output_asset_id: str) -> VideoLabRun:
        self._require_status(VideoLabRunStatus.RUNNING, "succeed")
        return replace(
            self,
            status=VideoLabRunStatus.SUCCEEDED,
            output_asset_id=_require_text(output_asset_id, "output_asset_id"),
        )

    def fail(self, error: str) -> VideoLabRun:
        if self.status not in {
            VideoLabRunStatus.CREATED,
            VideoLabRunStatus.QUEUED,
            VideoLabRunStatus.RUNNING,
        }:
            raise ValueError(f"cannot fail a {self.status.value} run")
        return replace(
            self,
            status=VideoLabRunStatus.FAILED,
            error=_require_text(error, "error"),
        )

    def cancel(self) -> VideoLabRun:
        if self.status not in {
            VideoLabRunStatus.CREATED,
            VideoLabRunStatus.QUEUED,
            VideoLabRunStatus.RUNNING,
            VideoLabRunStatus.CANCEL_PENDING,
        }:
            raise ValueError(f"cannot cancel a {self.status.value} run")
        return replace(
            self,
            status=VideoLabRunStatus.CANCELLED,
            error=None,
        )

    def mark_cancel_pending(self, error: str) -> VideoLabRun:
        """Keep the slot active when a remote job could not be stopped safely."""
        self._require_status(VideoLabRunStatus.RUNNING, "mark cancellation pending")
        return replace(
            self,
            status=VideoLabRunStatus.CANCEL_PENDING,
            error=_require_text(error, "error"),
        )

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if not isinstance(self.recipe, RecipeRef):
            raise TypeError("recipe must be a RecipeRef")
        _require_text(self.preset_id, "preset_id")
        if not isinstance(self.source_asset_ids, tuple):
            raise TypeError("source_asset_ids must be a tuple")
        if not 1 <= len(self.source_asset_ids) <= 3:
            raise ValueError("source_asset_ids must contain between 1 and 3 images")
        if len(set(self.source_asset_ids)) != len(self.source_asset_ids):
            raise ValueError("source_asset_ids must not contain duplicates")
        for asset_id in self.source_asset_ids:
            _require_text(asset_id, "source_asset_ids item")
        if not isinstance(self.source_labels, tuple):
            raise TypeError("source_labels must be a tuple")
        if len(self.source_labels) != len(self.source_asset_ids):
            raise ValueError("source_labels must align with source_asset_ids")
        for label in self.source_labels:
            _require_text(label, "source_labels item")
        _require_text(self.prompt, "prompt")
        if not isinstance(self.settings, VideoLabSettings):
            raise TypeError("settings must be VideoLabSettings")
        if not isinstance(self.status, VideoLabRunStatus):
            raise TypeError("status must be a VideoLabRunStatus")
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
        if self.status in {VideoLabRunStatus.CREATED, VideoLabRunStatus.QUEUED}:
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
        if self.status is VideoLabRunStatus.RUNNING:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("running run requires execution and workflow IDs")
            if self.output_asset_id is not None or self.error is not None:
                raise ValueError("running run contains terminal fields")
            return
        if self.status is VideoLabRunStatus.SUCCEEDED:
            if (
                self.execution_id is None
                or self.compiled_workflow_sha256 is None
                or self.output_asset_id is None
            ):
                raise ValueError("succeeded run requires execution, workflow and output IDs")
            if self.error is not None:
                raise ValueError("succeeded run cannot contain an error")
            return
        if self.status is VideoLabRunStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed run requires only an error")
            return
        if self.status is VideoLabRunStatus.CANCEL_PENDING:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError(
                    "cancel-pending run requires execution and workflow IDs"
                )
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("cancel-pending run requires only an error")
            return
        if self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled run cannot contain output or error")

    def _require_status(self, expected: VideoLabRunStatus, action: str) -> None:
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
