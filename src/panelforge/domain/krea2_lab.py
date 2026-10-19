"""Pure contracts for KREA2 text-to-image renders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math


KREA2_RESOLUTION_MULTIPLE = 8


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


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
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
