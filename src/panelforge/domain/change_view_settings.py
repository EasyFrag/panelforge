"""Optional rendering controls for a Qwen camera change, independent of its prompt."""

from dataclasses import dataclass
import math


CHANGE_VIEW_ASPECT_RATIOS = ("source", "1:1", "9:16", "16:9", "3:4", "4:3", "2:3", "3:2")


@dataclass(frozen=True, slots=True)
class ChangeViewRenderSettings:
    steps: int = 8
    megapixels: float | None = None
    aspect_ratio: str = "source"

    def __post_init__(self) -> None:
        if type(self.steps) is not int or not 1 <= self.steps <= 50:
            raise ValueError("steps must be an integer between 1 and 50")
        if self.megapixels is not None:
            if (
                isinstance(self.megapixels, bool)
                or not isinstance(self.megapixels, (int, float))
                or not math.isfinite(self.megapixels)
                or not 0.1 <= self.megapixels <= 4
            ):
                raise ValueError("megapixels must be between 0.1 and 4, or automatic")
        if self.aspect_ratio not in CHANGE_VIEW_ASPECT_RATIOS:
            raise ValueError("unsupported change-view aspect ratio")

    @property
    def is_default(self) -> bool:
        return self.steps == 8 and self.megapixels is None and self.aspect_ratio == "source"

    def fixed_dimensions(self) -> tuple[int, int] | None:
        """Round a requested canvas to latent-compatible dimensions."""
        if self.aspect_ratio == "source":
            return None
        width_ratio, height_ratio = map(int, self.aspect_ratio.split(":"))
        pixels = (self.megapixels if self.megapixels is not None else 1.0) * 1_000_000
        width = math.sqrt(pixels * width_ratio / height_ratio)
        height = math.sqrt(pixels * height_ratio / width_ratio)
        return tuple(max(32, round(value / 32) * 32) for value in (width, height))
