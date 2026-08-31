"""Versioned MiniMax H3 Ref2V workflow used by Video Lab."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain import (
    H3_VIDEO_LORA_OVERLAY_VERSION,
    H3VideoLoraSelection,
    RecipeRef,
    VideoAspectRatio,
    VideoLabSettings,
)
from .render_progress import (
    RenderProgressProfile,
    validate_render_progress_profile,
)


VIDEO_OPERATION_ID = "video.generate.ref2v"
VIDEO_RECIPE_ID = "minimax-h3-ref2v"
DEFAULT_VIDEO_PRESET_ID = "h3-balanced"


class VideoPresetValidationError(ValueError):
    """A published Video Lab manifest disagrees with its workflow."""


@dataclass(frozen=True, slots=True)
class WorkflowInputBinding:
    node_id: str
    input_name: str


@dataclass(frozen=True, slots=True)
class NodeOutputBinding:
    node_id: str
    output_index: int


@dataclass(frozen=True, slots=True)
class VideoLoraOverlayBinding:
    version: str
    lora_node_id: str
    clip_last_layer_node_id: str
    model_source: NodeOutputBinding
    clip_source: NodeOutputBinding
    model_target: WorkflowInputBinding
    clip_targets: tuple[WorkflowInputBinding, ...]


@dataclass(frozen=True, slots=True)
class ReferenceImageBinding:
    load_node_id: str
    input_name: str
    target_node_id: str
    target_input: str
    sentinel: str


@dataclass(frozen=True, slots=True)
class VideoOutputBinding:
    node_id: str
    history_field: str


@dataclass(frozen=True, slots=True)
class VideoLabPreset:
    preset_id: str
    label: str
    aspect_ratio: VideoAspectRatio
    megapixels: float
    duration_seconds: float
    steps: int
    preview_frames: int
    preview_fps: int
    preview_jpeg_quality: int
    preview_max_resolution: int

    def settings(self, *, seed: int, seed_locked: bool = False) -> VideoLabSettings:
        return VideoLabSettings(
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            duration_seconds=self.duration_seconds,
            steps=self.steps,
            seed=seed,
            seed_locked=seed_locked,
        )


@dataclass(frozen=True, slots=True)
class ValidatedVideoLabWorkflow:
    recipe_id: str
    version: str
    status: str
    workflow_sha256: str
    inputs: Mapping[str, tuple[WorkflowInputBinding, ...]]
    video_lora_overlay: VideoLoraOverlayBinding | None
    reference_images: tuple[ReferenceImageBinding, ...]
    output_video: VideoOutputBinding
    progress_profile: RenderProgressProfile | None
    presets: Mapping[str, VideoLabPreset]
    _workflow_json: bytes = field(repr=False)

    @property
    def reference(self) -> RecipeRef:
        return RecipeRef(
            operation_id=VIDEO_OPERATION_ID,
            recipe_id=self.recipe_id,
            version=self.version,
            workflow_sha256=self.workflow_sha256,
        )

    @property
    def workflow(self) -> dict[str, Any]:
        value = json.loads(self._workflow_json)
        if not isinstance(value, dict):
            raise VideoPresetValidationError("stored workflow must be an object")
        return value


@dataclass(frozen=True, slots=True)
class VideoLabPresetRecipe:
    """Application-facing adapter around one validated workflow snapshot."""

    preset: ValidatedVideoLabWorkflow

    @property
    def reference(self) -> RecipeRef:
        return self.preset.reference

    @property
    def status(self) -> str:
        return self.preset.status

    @property
    def presets(self) -> Mapping[str, VideoLabPreset]:
        return self.preset.presets

    @property
    def output_node_id(self) -> str:
        return self.preset.output_video.node_id

    @property
    def output_history_field(self) -> str:
        return self.preset.output_video.history_field

    @property
    def progress_profile(self) -> RenderProgressProfile | None:
        return self.preset.progress_profile

    @property
    def supports_video_lora(self) -> bool:
        return self.preset.video_lora_overlay is not None

    def build_workflow(
        self,
        *,
        source_images: Sequence[str],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        spectrum_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
    ) -> dict[str, Any]:
        return build_video_lab_workflow(
            self.preset,
            source_images=source_images,
            prompt=prompt,
            settings=settings,
            output_filename_prefix=output_filename_prefix,
            spectrum_enabled=spectrum_enabled,
            video_lora=video_lora,
        )


@dataclass(frozen=True, slots=True)
class Ref2VH3RenderPresetRecipe:
    """Conversational-render adapter for the published Ref2V workflow.

    The published snapshot exposes three loader slots. Ref2V itself accepts up
    to nine references, so the adapter clones only the neutral LoadImage slot
    for references four to nine without mutating the versioned workflow.
    """

    recipe: VideoLabPresetRecipe
    keyframe_margin_ms: int = 500
    maximum_keyframes: int = 8
    minimum_reference_images: int = 1
    maximum_reference_images: int = 9

    @property
    def reference(self) -> RecipeRef:
        return self.recipe.reference

    @property
    def status(self) -> str:
        return self.recipe.status

    @property
    def presets(self) -> Mapping[str, VideoLabPreset]:
        return self.recipe.presets

    @property
    def output_node_id(self) -> str:
        return self.recipe.output_node_id

    @property
    def output_history_field(self) -> str:
        return self.recipe.output_history_field

    @property
    def progress_profile(self) -> RenderProgressProfile | None:
        return self.recipe.progress_profile

    @property
    def supports_video_lora(self) -> bool:
        return self.recipe.supports_video_lora

    def keyframe_output_nodes(self, count: int) -> tuple[str, ...]:
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= self.maximum_keyframes:
            raise ValueError("invalid Ref2V keyframe count")
        return tuple(str(20_100 + index) for index in range(count))

    def build_workflow(
        self,
        *,
        source_images: Sequence[str],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        keyframe_indices: tuple[int, ...],
        spectrum_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
    ) -> dict[str, Any]:
        if not self.minimum_reference_images <= len(source_images) <= self.maximum_reference_images:
            raise ValueError(
                "Ref2V render requires between "
                f"{self.minimum_reference_images} and "
                f"{self.maximum_reference_images} images"
            )
        if len(keyframe_indices) > self.maximum_keyframes:
            raise ValueError("too many Ref2V keyframes")
        workflow = self.recipe.build_workflow(
            source_images=source_images[:3],
            prompt=prompt,
            settings=settings,
            output_filename_prefix=output_filename_prefix,
            spectrum_enabled=spectrum_enabled,
            video_lora=video_lora,
        )
        binding = self.recipe.preset.reference_images[-1]
        template = self.recipe.preset.workflow[binding.load_node_id]
        target_inputs = workflow[binding.target_node_id]["inputs"]
        target_prefix = binding.target_input.rsplit("_", 1)[0]
        for index, source_image in enumerate(source_images[3:], 3):
            load_node_id = str(20_000 + index)
            loader = deepcopy(template)
            loader["inputs"][binding.input_name] = source_image
            loader.setdefault("_meta", {})["title"] = f"PanelForge reference {index + 1}"
            workflow[load_node_id] = loader
            target_inputs[f"{target_prefix}_{index}"] = [load_node_id, 0]

        source_node_id, source_output_index = _decoded_image_source(
            workflow,
            self.output_node_id,
        )
        for index, frame_index in enumerate(keyframe_indices):
            selector_id = str(20_050 + index)
            save_id = str(20_100 + index)
            workflow[selector_id] = {
                "inputs": {
                    "image": [source_node_id, source_output_index],
                    "batch_index": frame_index,
                    "length": 1,
                },
                "class_type": "ImageFromBatch",
                "_meta": {"title": f"PanelForge Ref2V keyframe {index + 1}"},
            }
            workflow[save_id] = {
                "inputs": {
                    "filename_prefix": f"{output_filename_prefix}_keyframe_{index + 1:02d}",
                    "images": [selector_id, 0],
                },
                "class_type": "SaveImage",
                "_meta": {"title": f"Save PanelForge Ref2V keyframe {index + 1}"},
            }
        return workflow


def _decoded_image_source(
    workflow: Mapping[str, Any],
    output_node_id: str,
) -> tuple[str, int]:
    output = _object(workflow.get(output_node_id), "Ref2V output node")
    video_link = _object(output.get("inputs"), "Ref2V output inputs").get("video")
    if not isinstance(video_link, list) or len(video_link) != 2:
        raise VideoPresetValidationError("Ref2V output video link is invalid")
    video = _object(workflow.get(str(video_link[0])), "Ref2V CreateVideo node")
    image_link = _object(video.get("inputs"), "Ref2V CreateVideo inputs").get("images")
    if (
        not isinstance(image_link, list)
        or len(image_link) != 2
        or not isinstance(image_link[0], str)
        or isinstance(image_link[1], bool)
        or not isinstance(image_link[1], int)
    ):
        raise VideoPresetValidationError("Ref2V decoded image link is invalid")
    return image_link[0], image_link[1]


def load_video_lab_workflow(directory: Path) -> ValidatedVideoLabWorkflow:
    manifest = _read_object(directory / "manifest.json")
    workflow_config = _object(manifest.get("workflow"), "workflow")
    workflow_filename = _text(workflow_config.get("file"), "workflow.file")
    expected_hash = _text(
        workflow_config.get("sha256"),
        "workflow.sha256",
    ).lower()
    workflow_content = (directory / workflow_filename).read_bytes()
    actual_hash = hashlib.sha256(workflow_content).hexdigest()
    if actual_hash != expected_hash:
        raise VideoPresetValidationError(
            f"workflow hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    workflow = _decode_object(workflow_content, workflow_filename)
    return validate_video_lab_workflow(
        manifest,
        workflow,
        workflow_sha256=actual_hash,
    )


def validate_video_lab_workflow(
    manifest: Mapping[str, Any],
    workflow: Mapping[str, Any],
    *,
    workflow_sha256: str = "0" * 64,
) -> ValidatedVideoLabWorkflow:
    if manifest.get("schema_version") != 1:
        raise VideoPresetValidationError("schema_version must be 1")
    if manifest.get("operation") != VIDEO_OPERATION_ID:
        raise VideoPresetValidationError(
            f"operation must be {VIDEO_OPERATION_ID!r}"
        )
    if manifest.get("recipe_id") != VIDEO_RECIPE_ID:
        raise VideoPresetValidationError(
            f"recipe_id must be {VIDEO_RECIPE_ID!r}"
        )
    version = _text(manifest.get("version"), "version")
    status = _text(manifest.get("status"), "status")

    scope = _object(manifest.get("scope"), "scope")
    if scope != {
        "minimum_reference_images": 1,
        "maximum_reference_images": 3,
        "fps": 24,
    }:
        raise VideoPresetValidationError("scope must declare 1-3 images at 24 fps")

    nodes = _object(workflow, "workflow JSON")
    if not nodes:
        raise VideoPresetValidationError("workflow JSON must not be empty")
    bindings = _object(manifest.get("bindings"), "bindings")
    required_inputs = {
        "positive_prompt",
        "aspect_ratio",
        "megapixels",
        "duration_seconds",
        "steps",
        "seed",
        "output_filename_prefix",
    }
    optional_inputs = {"spectrum_enabled"}
    optional_bindings = {"video_lora_overlay"}
    required_binding_keys = required_inputs | {"reference_images", "output_video"}
    expected_binding_keys = required_binding_keys | optional_inputs | optional_bindings
    binding_keys = set(bindings)
    if not required_binding_keys <= binding_keys or not binding_keys <= expected_binding_keys:
        raise VideoPresetValidationError(
            "bindings must define the required render inputs and only supported optional inputs"
        )

    input_bindings = {
        name: _input_bindings(bindings[name], nodes, f"bindings.{name}")
        for name in required_inputs | (optional_inputs & set(bindings))
    }
    prompt_config = _object(bindings["positive_prompt"], "positive_prompt")
    prompt_sentinel = _text(prompt_config.get("sentinel"), "positive_prompt.sentinel")
    prompt_bindings = input_bindings["positive_prompt"]
    if len(prompt_bindings) != 1:
        raise VideoPresetValidationError(
            "positive_prompt must define exactly one workflow binding"
        )
    prompt_binding = prompt_bindings[0]
    if _node_input(nodes, prompt_binding) != prompt_sentinel:
        raise VideoPresetValidationError("workflow prompt is not neutralized")

    references_raw = bindings["reference_images"]
    if not isinstance(references_raw, list) or len(references_raw) != 3:
        raise VideoPresetValidationError("reference_images must define exactly 3 slots")
    references = tuple(
        _reference_binding(value, nodes, index)
        for index, value in enumerate(references_raw)
    )
    video_lora_overlay = (
        _video_lora_overlay_binding(bindings["video_lora_overlay"], nodes)
        if "video_lora_overlay" in bindings
        else None
    )

    output_config = _object(bindings["output_video"], "output_video")
    output_node_id = _text(output_config.get("node_id"), "output_video.node_id")
    output_node = _object(nodes.get(output_node_id), f"workflow node {output_node_id}")
    if output_node.get("class_type") != "SaveVideo":
        raise VideoPresetValidationError("output_video must target SaveVideo")
    output = VideoOutputBinding(
        node_id=output_node_id,
        history_field=_text(
            output_config.get("history_field"),
            "output_video.history_field",
        ),
    )

    _validate_assertions(manifest.get("workflow_assertions"), nodes)
    _validate_no_orphans(nodes, output.node_id)
    progress_profile = validate_render_progress_profile(
        manifest.get("progress"),
        nodes,
        error_type=VideoPresetValidationError,
    )
    presets = _validate_presets(manifest.get("presets"))
    if DEFAULT_VIDEO_PRESET_ID not in presets:
        raise VideoPresetValidationError(
            f"presets must include {DEFAULT_VIDEO_PRESET_ID!r}"
        )

    serialized = json.dumps(
        nodes,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return ValidatedVideoLabWorkflow(
        recipe_id=VIDEO_RECIPE_ID,
        version=version,
        status=status,
        workflow_sha256=workflow_sha256,
        inputs=MappingProxyType(input_bindings),
        video_lora_overlay=video_lora_overlay,
        reference_images=references,
        output_video=output,
        progress_profile=progress_profile,
        presets=MappingProxyType(presets),
        _workflow_json=serialized,
    )


def build_video_lab_workflow(
    preset: ValidatedVideoLabWorkflow,
    *,
    source_images: Sequence[str],
    prompt: str,
    settings: VideoLabSettings,
    output_filename_prefix: str,
    spectrum_enabled: bool = False,
    video_lora: H3VideoLoraSelection | None = None,
) -> dict[str, Any]:
    """Compile an isolated workflow and prune unused reference slots."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must not be empty")
    if not isinstance(settings, VideoLabSettings):
        raise TypeError("settings must be VideoLabSettings")
    if not isinstance(spectrum_enabled, bool):
        raise TypeError("spectrum_enabled must be a boolean")
    if video_lora is not None and not isinstance(video_lora, H3VideoLoraSelection):
        raise TypeError("video_lora must be an H3VideoLoraSelection or None")
    if not 1 <= len(source_images) <= 3:
        raise ValueError("source_images must contain between 1 and 3 images")
    for source_image in source_images:
        if not isinstance(source_image, str) or not source_image.strip():
            raise ValueError("source_images items must not be empty")
    if not isinstance(output_filename_prefix, str) or not output_filename_prefix.strip():
        raise ValueError("output_filename_prefix must not be empty")

    workflow = preset.workflow
    values: Mapping[str, object] = {
        "positive_prompt": prompt,
        "aspect_ratio": settings.aspect_ratio.value,
        "megapixels": settings.megapixels,
        "duration_seconds": settings.duration_seconds,
        "steps": settings.steps,
        "seed": settings.seed,
        "output_filename_prefix": output_filename_prefix,
        "spectrum_enabled": spectrum_enabled,
    }
    for name, value in values.items():
        if name not in preset.inputs:
            if name == "spectrum_enabled" and value:
                raise ValueError("this Ref2V workflow does not support Spectrum")
            continue
        for binding in preset.inputs[name]:
            workflow[binding.node_id]["inputs"][binding.input_name] = value

    for index, binding in enumerate(preset.reference_images):
        target_inputs = workflow[binding.target_node_id]["inputs"]
        if index < len(source_images):
            workflow[binding.load_node_id]["inputs"][binding.input_name] = (
                source_images[index]
            )
        else:
            target_inputs.pop(binding.target_input, None)
            workflow.pop(binding.load_node_id, None)
    if video_lora is not None:
        if preset.video_lora_overlay is None:
            raise ValueError("this Ref2V workflow does not support video LoRAs")
        _apply_video_lora(workflow, preset.video_lora_overlay, video_lora)
    return workflow


def _apply_video_lora(
    workflow: dict[str, Any],
    binding: VideoLoraOverlayBinding,
    selection: H3VideoLoraSelection,
) -> None:
    if selection.overlay_version != binding.version:
        raise ValueError("H3 video LoRA overlay version disagrees with the Ref2V workflow")
    workflow[binding.lora_node_id] = {
        "inputs": {
            "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
            "lora_1": {
                "on": True,
                "lora": selection.name,
                "strength": selection.strength,
            },
            "\u2795 Add Lora": "",
            "model": [binding.model_source.node_id, binding.model_source.output_index],
            "clip": [binding.clip_source.node_id, binding.clip_source.output_index],
        },
        "class_type": "Power Lora Loader (rgthree)",
        "_meta": {"title": "PanelForge MiniMax Ref2V LoRA"},
    }
    workflow[binding.model_target.node_id]["inputs"][binding.model_target.input_name] = [
        binding.lora_node_id,
        0,
    ]
    clip_output: list[object] = [binding.lora_node_id, 1]
    if selection.clip_last_layer is not None:
        workflow[binding.clip_last_layer_node_id] = {
            "inputs": {
                "stop_at_clip_layer": selection.clip_last_layer,
                "clip": clip_output,
            },
            "class_type": "CLIPSetLastLayer",
            "_meta": {"title": "PanelForge MiniMax Ref2V LoRA CLIP layer"},
        }
        clip_output = [binding.clip_last_layer_node_id, 0]
    for target in binding.clip_targets:
        workflow[target.node_id]["inputs"][target.input_name] = clip_output


def _input_binding(
    value: Any,
    workflow: Mapping[str, Any],
    label: str,
) -> WorkflowInputBinding:
    config = _object(value, label)
    node_id = _text(config.get("node_id"), f"{label}.node_id")
    input_name = _text(config.get("input"), f"{label}.input")
    node = _object(workflow.get(node_id), f"workflow node {node_id}")
    inputs = _object(node.get("inputs"), f"workflow node {node_id}.inputs")
    if input_name not in inputs:
        raise VideoPresetValidationError(
            f"workflow node {node_id} has no input {input_name!r}"
        )
    return WorkflowInputBinding(node_id=node_id, input_name=input_name)


def _input_bindings(
    value: Any,
    workflow: Mapping[str, Any],
    label: str,
) -> tuple[WorkflowInputBinding, ...]:
    values = value if isinstance(value, list) else [value]
    if not values:
        raise VideoPresetValidationError(f"{label} must not be empty")
    return tuple(
        _input_binding(item, workflow, f"{label}[{index}]")
        for index, item in enumerate(values)
    )


def _video_lora_overlay_binding(
    value: Any,
    workflow: Mapping[str, Any],
) -> VideoLoraOverlayBinding:
    label = "bindings.video_lora_overlay"
    config = _object(value, label)
    version = _text(config.get("version"), f"{label}.version")
    if version != H3_VIDEO_LORA_OVERLAY_VERSION:
        raise VideoPresetValidationError("unsupported Ref2V video LoRA overlay version")
    lora_node_id = _text(config.get("lora_node_id"), f"{label}.lora_node_id")
    clip_node_id = _text(
        config.get("clip_last_layer_node_id"),
        f"{label}.clip_last_layer_node_id",
    )
    if lora_node_id == clip_node_id or lora_node_id in workflow or clip_node_id in workflow:
        raise VideoPresetValidationError("Ref2V video LoRA overlay node IDs must be unused")

    def source(raw: Any, source_label: str) -> NodeOutputBinding:
        source_config = _object(raw, source_label)
        node_id = _text(source_config.get("node_id"), f"{source_label}.node_id")
        if node_id not in workflow:
            raise VideoPresetValidationError(f"{source_label} node is missing")
        output_index = source_config.get("output_index")
        if isinstance(output_index, bool) or not isinstance(output_index, int) or output_index < 0:
            raise VideoPresetValidationError(
                f"{source_label}.output_index must be a non-negative integer"
            )
        return NodeOutputBinding(node_id=node_id, output_index=output_index)

    model_source = source(config.get("model_source"), f"{label}.model_source")
    clip_source = source(config.get("clip_source"), f"{label}.clip_source")
    model_target = _input_binding(
        config.get("model_target"),
        workflow,
        f"{label}.model_target",
    )
    clip_targets = _input_bindings(
        config.get("clip_targets"),
        workflow,
        f"{label}.clip_targets",
    )
    if _node_input(workflow, model_target) != [
        model_source.node_id,
        model_source.output_index,
    ]:
        raise VideoPresetValidationError(
            "Ref2V video LoRA model target does not consume the declared source"
        )
    for target in clip_targets:
        if _node_input(workflow, target) != [
            clip_source.node_id,
            clip_source.output_index,
        ]:
            raise VideoPresetValidationError(
                "Ref2V video LoRA CLIP target does not consume the declared source"
            )
    return VideoLoraOverlayBinding(
        version=version,
        lora_node_id=lora_node_id,
        clip_last_layer_node_id=clip_node_id,
        model_source=model_source,
        clip_source=clip_source,
        model_target=model_target,
        clip_targets=clip_targets,
    )


def _reference_binding(
    value: Any,
    workflow: Mapping[str, Any],
    index: int,
) -> ReferenceImageBinding:
    label = f"reference_images[{index}]"
    config = _object(value, label)
    load_node_id = _text(config.get("load_node_id"), f"{label}.load_node_id")
    input_name = _text(config.get("input"), f"{label}.input")
    target_node_id = _text(
        config.get("target_node_id"),
        f"{label}.target_node_id",
    )
    target_input = _text(config.get("target_input"), f"{label}.target_input")
    sentinel = _text(config.get("sentinel"), f"{label}.sentinel")
    load_node = _object(workflow.get(load_node_id), f"workflow node {load_node_id}")
    if load_node.get("class_type") != "LoadImage":
        raise VideoPresetValidationError(f"{label} must target a LoadImage node")
    load_inputs = _object(load_node.get("inputs"), f"node {load_node_id}.inputs")
    if load_inputs.get(input_name) != sentinel:
        raise VideoPresetValidationError(f"{label} is not neutralized")
    target = _object(workflow.get(target_node_id), f"workflow node {target_node_id}")
    target_inputs = _object(target.get("inputs"), f"node {target_node_id}.inputs")
    if target_inputs.get(target_input) != [load_node_id, 0]:
        raise VideoPresetValidationError(f"{label} target is not wired to its loader")
    return ReferenceImageBinding(
        load_node_id=load_node_id,
        input_name=input_name,
        target_node_id=target_node_id,
        target_input=target_input,
        sentinel=sentinel,
    )


def _validate_assertions(value: Any, workflow: Mapping[str, Any]) -> None:
    if not isinstance(value, list) or not value:
        raise VideoPresetValidationError("workflow_assertions must not be empty")
    seen: set[str] = set()
    for index, raw in enumerate(value):
        label = f"workflow_assertions[{index}]"
        assertion = _object(raw, label)
        assertion_id = _text(assertion.get("id"), f"{label}.id")
        if assertion_id in seen:
            raise VideoPresetValidationError(
                f"duplicate workflow assertion {assertion_id!r}"
            )
        seen.add(assertion_id)
        binding = _input_binding(assertion, workflow, label)
        if "equals" not in assertion:
            raise VideoPresetValidationError(f"{label}.equals is required")
        actual = _node_input(workflow, binding)
        if actual != assertion["equals"]:
            raise VideoPresetValidationError(
                f"{assertion_id} expected {assertion['equals']!r}, got {actual!r}"
            )


def _validate_no_orphans(workflow: Mapping[str, Any], output_node_id: str) -> None:
    reachable: set[str] = set()
    pending = [output_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node = _object(workflow.get(node_id), f"workflow node {node_id}")
        for dependency in _node_dependencies(node.get("inputs"), workflow):
            if dependency not in reachable:
                pending.append(dependency)
    orphans = set(workflow) - reachable
    if orphans:
        raise VideoPresetValidationError(
            f"workflow contains orphan nodes: {sorted(orphans)!r}"
        )


def _node_dependencies(value: Any, workflow: Mapping[str, Any]) -> set[str]:
    dependencies: set[str] = set()
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and value[0] in workflow
        and isinstance(value[1], int)
    ):
        dependencies.add(value[0])
    elif isinstance(value, Mapping):
        for nested in value.values():
            dependencies.update(_node_dependencies(nested, workflow))
    elif isinstance(value, list):
        for nested in value:
            dependencies.update(_node_dependencies(nested, workflow))
    return dependencies


def _validate_presets(value: Any) -> dict[str, VideoLabPreset]:
    if not isinstance(value, list) or not value:
        raise VideoPresetValidationError("presets must not be empty")
    result: dict[str, VideoLabPreset] = {}
    for index, raw in enumerate(value):
        label = f"presets[{index}]"
        config = _object(raw, label)
        preview = _object(config.get("preview"), f"{label}.preview")
        preset_id = _text(config.get("id"), f"{label}.id")
        if preset_id in result:
            raise VideoPresetValidationError(f"duplicate preset {preset_id!r}")
        try:
            aspect_ratio = VideoAspectRatio(config.get("aspect_ratio"))
            defaults = VideoLabSettings(
                aspect_ratio=aspect_ratio,
                megapixels=config.get("megapixels"),
                duration_seconds=config.get("duration_seconds"),
                steps=config.get("steps"),
                seed=0,
            )
        except (TypeError, ValueError) as error:
            raise VideoPresetValidationError(f"invalid {label}: {error}") from error
        result[preset_id] = VideoLabPreset(
            preset_id=preset_id,
            label=_text(config.get("label"), f"{label}.label"),
            aspect_ratio=defaults.aspect_ratio,
            megapixels=defaults.megapixels,
            duration_seconds=defaults.duration_seconds,
            steps=defaults.steps,
            preview_frames=_integer(preview.get("frames"), f"{label}.preview.frames"),
            preview_fps=_integer(preview.get("fps"), f"{label}.preview.fps"),
            preview_jpeg_quality=_integer(
                preview.get("jpeg_quality"),
                f"{label}.preview.jpeg_quality",
            ),
            preview_max_resolution=_integer(
                preview.get("max_resolution"),
                f"{label}.preview.max_resolution",
            ),
        )
    return result


def _node_input(
    workflow: Mapping[str, Any],
    binding: WorkflowInputBinding,
) -> Any:
    return workflow[binding.node_id]["inputs"][binding.input_name]


def _read_object(path: Path) -> dict[str, Any]:
    return _decode_object(path.read_bytes(), str(path))


def _decode_object(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VideoPresetValidationError(f"invalid JSON in {label}") from error
    return dict(_object(value, label))


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoPresetValidationError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoPresetValidationError(f"{label} must be a non-empty string")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VideoPresetValidationError(f"{label} must be a positive integer")
    return value
