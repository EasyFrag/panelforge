"""V3: describe the visible replacement when the user removes an element.

Reuse V2's frozen context and publication contracts. Only the creation writer's
removal instruction changes; no extra call, inferred memory or output filtering.
"""

from . import krea2_assisted_v2
from .krea2_assisted_v2 import (
    needs_recipes,
    needs_resources,
    resource_memory,
    user_prompt,
)


VERSION = "3.0.0"
LABEL = "V3 · STABLE"
MAX_TOKENS = krea2_assisted_v2.MAX_TOKENS
CREATION_OPERATION = "krea2.assisted.creation_chat@3.0.0"
RECIPE_OPERATION = "krea2.assisted.recipe_chat@3.0.0"

# Replace the V2 exception, rather than appending a competing instruction.
_CREATION_SYSTEM = krea2_assisted_v2.system_prompt("creation").replace(
    "Use a short exclusion only to resolve ambiguity.",
    "For removal requests, describe the resulting visible state and what occupies "
    "the affected area: background, material, shape or empty space. Rewrite the "
    "complete prompt to remove the unwanted element and wording that still "
    "suggests it, including associated structures, actions or style cues; preserve "
    "unaffected user choices. Explain exclusions in the French reply instead of "
    "listing forbidden objects in the image prompt. After repeated removal "
    "failures, change the visual description rather than adding negations or synonyms.",
    1,
)


def system_prompt(mode: str) -> str:
    return _CREATION_SYSTEM if mode == "creation" else krea2_assisted_v2.system_prompt(mode)
