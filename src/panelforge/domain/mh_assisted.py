"""Still-image composition contracts for Creation Assistee MH."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from .minimax_edit import (
    DEFAULT_ASSISTANT_MODEL, MAX_ASSISTANT_IMAGES, MAX_RENDER_IMAGES, RATIOS,
    MinimaxEditSettings, render_inputs, validate_prompt, validate_references,
    context_snapshot as minimax_context,
)

ENGINE = "mh"
LABEL = "Création Assistée MH"
COMPOSITION_RESOLUTION = "2"
POSE_ROLE = ("Pose et point de vue uniquement : reproduire la posture et la disposition des corps. "
             "L'intention définit les sujets, la direction artistique leur style. "
             "Ne pas copier le mannequin gris, son absence de visage ni son fond.")


@dataclass(frozen=True, slots=True)
class Settings(MinimaxEditSettings):
    resolution: str = "2"
    reuse_seed: bool = False

    def __post_init__(self):
        MinimaxEditSettings.__post_init__(self)
        if self.resolution not in {"1", "2", "4", "8", "preset"} or self.reference_mode != "resize":
            raise ValueError("Choisis une résolution de composition MiniMax.")
        if self.color_finish != "raw":
            raise ValueError("La création MH utilise les couleurs du rendu MiniMax.")


def context_snapshot(stage):
    return {**minimax_context(stage), "engine": ENGINE, "prompt_contract": "mh.assisted@1.0.0",
            "creative": deepcopy(stage.get("creative", {}))}


def context_fingerprint(stage):
    return hashlib.sha256(json.dumps(context_snapshot(stage), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prompt_is_ready(stage):
    return bool(stage["prompt"].strip()) and stage.get("prompt_fingerprint") == context_fingerprint(stage)


def language(value):
    if value not in {"en", "zh"}:
        raise ValueError("Choisis la langue du prompt : anglais ou chinois.")
    return value
