"""Prompt rendering and workflow preparation for character view changes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panelforge.domain.character import ChangeView

from .change_view_manifest import PresetValidationError, ValidatedChangeViewPreset


JsonObject = dict[str, Any]


def render_change_view_prompt(
    change: ChangeView,
    preset: ValidatedChangeViewPreset,
) -> str:
    """Render the protected LoRA grammar without an LLM rewrite."""
    return preset.prompt_template.format_map(
        {
            "azimuth": preset.azimuth_phrases[change.azimuth.value],
            "elevation": preset.elevation_phrases[change.elevation.value],
            "shot_size": preset.shot_size_phrases[change.shot_size.value],
        }
    )


def build_change_view_workflow(
    change: ChangeView,
    preset: ValidatedChangeViewPreset,
    *,
    source_image: str,
    seed: int,
) -> JsonObject:
    """Build one isolated workflow with this run's explicit inputs."""
    if not isinstance(source_image, str) or not source_image.strip():
        raise ValueError("source_image must not be empty")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed must be an integer between 0 and 2^64 - 1")

    workflow = preset.workflow
    values: Mapping[str, Any] = {
        "source_image": source_image,
        "positive_prompt": render_change_view_prompt(change, preset),
        "negative_prompt": preset.negative_prompt,
        "seed": seed,
    }
    for binding_name, value in values.items():
        binding = preset.bindings[binding_name]
        if binding.input_name is None:
            raise PresetValidationError(
                f"binding {binding_name!r} is not a workflow input"
            )
        workflow[binding.node_id]["inputs"][binding.input_name] = value
    return workflow
