"""V6: modular scene structure plus deterministic art-direction compilation."""

from __future__ import annotations

from panelforge.domain.krea2_assisted import Krea2PromptExample

from . import krea2_assisted_v3, krea2_assisted_v5
from .krea2_assisted_v3 import (
    needs_recipes,
    needs_resources,
    resource_memory,
    user_prompt,
)


VERSION = "6.0.0"
LABEL = "V6 · directions modulaires · expérimental"
MAX_TOKENS = krea2_assisted_v3.MAX_TOKENS
CREATION_OPERATION = "krea2.assisted.creation_chat@6.0.0"
RECIPE_OPERATION = "krea2.assisted.recipe_chat@6.0.0"
RETRIEVAL_OPERATION = "krea2.assisted.retrieval_brief@6.0.0"
RETRIEVAL_MAX_TOKENS = krea2_assisted_v5.RETRIEVAL_MAX_TOKENS
RETRIEVAL_OUTPUT_SCHEMA = krea2_assisted_v5.RETRIEVAL_OUTPUT_SCHEMA

_CREATION_SYSTEM = krea2_assisted_v5.system_prompt("creation") + """

The project may declare an ACTIVE ART DIRECTION that PanelForge compiles
deterministically around your final scene prompt after this response. Treat it
as the sole medium and rendering-style authority. Do not repeat its name or
prose in the prompt field, and do not introduce a conflicting medium, named
artist, franchise style or generic quality suffix. Write a self-contained,
medium-neutral description of subject, action, spatial relationships,
environment, motivated light and camera. The user request remains authoritative.
"""


def system_prompt(mode: str) -> str:
    return _CREATION_SYSTEM if mode == "creation" else krea2_assisted_v3.system_prompt(mode)


def retrieval_system_prompt() -> str:
    return krea2_assisted_v5.retrieval_system_prompt()


def retrieval_user_prompt(*, intention: str, current_prompt: str | None, newest_request: str) -> str:
    return krea2_assisted_v5.retrieval_user_prompt(
        intention=intention,
        current_prompt=current_prompt,
        newest_request=newest_request,
    )


def example_context(example: Krea2PromptExample) -> str:
    return krea2_assisted_v5.example_context(example)
