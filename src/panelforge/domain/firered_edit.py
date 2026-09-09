"""Rendering controls specific to the FireRed image-edit engine."""

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class FireRedEditSettings:
    model_name: str
    megapixels: float
    seed: int
    mode: str = "lightning"
    steps: int | None = None
    cfg: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("FireRed model_name must not be empty")
        if self.mode not in {"lightning", "standard"}:
            raise ValueError("FireRed mode must be lightning or standard")
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if self.steps is None:
            object.__setattr__(self, "steps", 8 if self.mode == "lightning" else 40)
        if self.cfg is None:
            object.__setattr__(self, "cfg", 1.0 if self.mode == "lightning" else 4.0)
        if type(self.steps) is not int or not 1 <= self.steps <= 100:
            raise ValueError("steps must be an integer between 1 and 100")
        for name, low, high in (("megapixels", 0.1, 16.0), ("cfg", 0.0, 100.0)):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError(f"{name} must be finite and between {low} and {high}")

