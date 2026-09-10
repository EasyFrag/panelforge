"""Explicit controls for the BUNNY two-pass render recipe."""

from dataclasses import dataclass, replace
import math

from .video_lab import VideoLabSettings

BUNNY_RECIPE_ID = "minimax-h3-bunny"


@dataclass(frozen=True, slots=True)
class H3BunnySettings:
    turbo_enabled: bool = True
    base_steps: int = 9
    coarse_steps: int = 4
    refine_steps: int = 5
    lora_second_strength: float = 0.2
    preview_enabled: bool = True

    def __post_init__(self) -> None:
        if type(self.turbo_enabled) is not bool or type(self.preview_enabled) is not bool:
            raise ValueError("Turbo et preview doivent être des booléens.")
        if any(type(v) is not int for v in (self.base_steps, self.coarse_steps, self.refine_steps)):
            raise ValueError("Les nombres de steps doivent être entiers.")
        if not 2 <= self.base_steps <= 100 or not 1 <= self.coarse_steps < self.base_steps:
            raise ValueError("BUNNY : 2–100 steps de base, et 1 ≤ première passe < base.")
        if self.refine_steps not in {3, 4, 5}:
            raise ValueError("BUNNY : la seconde passe accepte 3, 4 ou 5 steps.")
        if (isinstance(self.lora_second_strength, bool)
                or not isinstance(self.lora_second_strength, (int, float))
                or not math.isfinite(self.lora_second_strength)
                or not 0 <= self.lora_second_strength <= 1):
            raise ValueError("La force du LoRA de seconde passe doit être comprise entre 0 et 1.")


def bunny_geometry(settings: VideoLabSettings, initial_megapixels: float) -> dict[str, object]:
    """Match T8 target_dimensions/preserve_source on the H3 32-pixel grid.

    ResolutionSelector uses 1024² pixels/MP. Passing dimensions avoids mixing
    that convention with T8's decimal target_megapixels control.
    """
    width, height = replace(settings, megapixels=initial_megapixels).resolution
    target_width, target_height = settings.resolution
    ratio = width / height
    ideal_width = math.sqrt(target_width * target_height * ratio)
    ideal_height = ideal_width / ratio
    candidates = [
        (max(32, w * 32), max(32, h * 32))
        for w in {math.floor(ideal_width / 32), math.ceil(ideal_width / 32)}
        for h in {math.floor(ideal_height / 32), math.ceil(ideal_height / 32)}
    ]
    out_w, out_h = min(candidates, key=lambda s: (
        abs(math.log((s[0] / s[1]) / ratio)),
        math.hypot((s[0] - ideal_width) / ideal_width, (s[1] - ideal_height) / ideal_height),
    ))
    sx, sy = out_w / width, out_h / height
    if min(sx, sy) < 1 or max(sx, sy) > 4 or max(sx, sy) / min(sx, sy) > 1.05:
        raise ValueError("BUNNY : la sortie doit conserver les proportions et agrandir de ×1 à ×4, sans réduction.")
    if max(target_width, target_height) > 4096:
        raise ValueError("BUNNY : les dimensions cibles doivent rester inférieures ou égales à 4096 px.")
    return {
        "initial_width": width, "initial_height": height,
        "width": out_w, "height": out_h,
        "scale": math.sqrt(sx * sy), "actual_megapixels": out_w * out_h / 1_000_000,
    }
