"""Optional model-only adapters for MiniMax still images."""
from dataclasses import dataclass
import math

from .h3_render import canonical_h3_video_lora_name

MAX_LORAS = 4


@dataclass(frozen=True, slots=True)
class MinimaxLora:
    name: str
    strength: float = 0.5
    enabled: bool = True

    def __post_init__(self):
        try:
            object.__setattr__(self, "name", canonical_h3_video_lora_name(self.name))
        except (TypeError, ValueError) as error:
            raise ValueError("Choisis un fichier LoRA MiniMax .safetensors du catalogue.") from error
        if (type(self.strength) not in {int, float} or not math.isfinite(self.strength)
                or not 0 <= self.strength <= 1):
            raise ValueError("La force d’un LoRA MiniMax doit être comprise entre 0 et 1.")
        if type(self.enabled) is not bool:
            raise ValueError("L’activation d’un LoRA MiniMax doit être un booléen.")


def lora_slots(values):
    if not isinstance(values, (list, tuple)) or len(values) > MAX_LORAS:
        raise ValueError("Choisis au maximum quatre LoRA MiniMax.")
    entries = tuple(MinimaxLora(**value) if isinstance(value, dict) else value for value in values)
    if any(not isinstance(entry, MinimaxLora) for entry in entries):
        raise ValueError("Sélection de LoRA MiniMax invalide.")
    if len({entry.name.casefold() for entry in entries}) != len(entries):
        raise ValueError("Chaque LoRA MiniMax ne peut être choisi qu’une fois.")
    return entries
