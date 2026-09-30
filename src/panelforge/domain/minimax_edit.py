"""MiniMax H3 Still settings and explicit reference identities."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re

from .qwen_edit import MAX_ASSISTANT_IMAGES, RATIOS, validate_references
from .qwen_edit import render_inputs as _render_inputs, context_snapshot as _context_snapshot

ENGINE = "minimax"
LABEL = "Minimax"
DEFAULT_ASSISTANT_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
MAX_RENDER_IMAGES = 9
COMPOSITION_RESOLUTION = "preset"
PRESET_PIXELS = 2016 * 3584


@dataclass(frozen=True, slots=True)
class MinimaxEditSettings:
    resolution: str = "preset"
    aspect_ratio: str = "9:16"
    steps: int = 18
    seed: str = "699635426837388"
    reuse_seed: bool = True
    color_finish: str = "raw"
    reference_megapixels: int = 1
    reference_mode: str = "resize"

    def __post_init__(self):
        if self.reference_mode not in {"resize", "native"}:
            raise ValueError("Mode de référence MiniMax invalide.")
        if self.reference_mode == "native" and self.resolution not in {"source", "double"}:
            raise ValueError("La référence native exige une sortie à la taille source ou un essai HQ ×2.")
        if type(self.reference_megapixels) is not int or self.reference_megapixels not in {1, 2}:
            raise ValueError("La référence MiniMax doit être de 1 ou 2 MP.")
        if self.resolution not in {"source", "double", "preset", "1", "2", "4", "8"} or self.aspect_ratio not in RATIOS:
            raise ValueError("Résolution ou format Minimax invalide.")
        if type(self.steps) is not int or not 1 <= self.steps <= 100:
            raise ValueError("Les steps doivent être compris entre 1 et 100.")
        if not isinstance(self.seed, str) or not re.fullmatch(r"[0-9]{1,20}", self.seed) or int(self.seed) >= 2**64:
            raise ValueError("Seed invalide : entier positif inférieur à 2⁶⁴.")
        if type(self.reuse_seed) is not bool or self.color_finish not in {"natural", "raw"}:
            raise ValueError("Réglages Minimax invalides.")

    def dimensions(self, source_size=None):
        if self.resolution == 'double':
            if not source_size or any(type(v) is not int or v < 64 or v % 32 for v in source_size):
                raise ValueError('L’essai HQ ×2 nécessite une image aux dimensions multiples de 32.')
            if max(source_size) * 2 > 4096:
                raise ValueError('L’essai HQ ×2 dépasse 4096 pixels. Choisis une image de 2048 pixels maximum par côté.')
            return source_size[0] * 2, source_size[1] * 2
        width, height = source_size if source_size else tuple(map(int, self.aspect_ratio.split(":")))
        if width <= 0 or height <= 0:
            raise ValueError("Dimensions de source invalides.")
        if self.resolution == "source" and source_size:
            scale = 1
        else:
            pixels = PRESET_PIXELS if self.resolution in {"preset", "source"} else float(self.resolution) * 1024**2
            scale = math.sqrt(pixels / (width * height))
        # Fizgig accepts 64..4096 in multiples of 32. Preserve the ratio when
        # an unusually long side would exceed the node's maximum.
        scale = min(scale, 4096 / max(width, height))
        return max(64, round(width * scale / 32) * 32), max(64, round(height * scale / 32) * 32)

    def record(self):
        return asdict(self)


Settings = MinimaxEditSettings


def render_inputs(stage):
    return _render_inputs(stage, max_images=MAX_RENDER_IMAGES, engine_label=LABEL, tag_template="<Picture {}>")


def context_snapshot(stage):
    return {**_context_snapshot(stage, inputs=render_inputs(stage)), "engine": ENGINE, "prompt_contract": "1.0.0"}


def context_fingerprint(stage):
    return hashlib.sha256(json.dumps(context_snapshot(stage), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_prompt(prompt, inputs):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
        raise ValueError("Écris ou prépare une instruction de rendu (24 000 caractères maximum).")
    if re.search(r"<image\d+>|<(?:Video|Audio)\s+\d+>", prompt, re.IGNORECASE):
        raise ValueError("Ce preset Minimax utilise uniquement des références <Picture N>.")
    indexes = {int(value) for value in re.findall(r"<Picture (\d+)>", prompt)}
    if indexes != set(range(1, len(inputs) + 1)):
        raise ValueError("Le prompt doit préciser l’usage de chaque référence Minimax avec son label <Picture N>.")


def prompt_is_ready(stage):
    return bool(stage["prompt"].strip()) and stage.get("prompt_fingerprint") == context_fingerprint(stage)


def journey_child_id(step_id):
    """Explicit, stable identity shared by creation and read-only collection."""
    from uuid import NAMESPACE_URL, uuid5
    from .image_journeys import request_id
    return "minimax-" + uuid5(NAMESPACE_URL, "panelforge/journey-step/" + request_id(step_id)).hex
