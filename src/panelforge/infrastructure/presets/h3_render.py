"""Versioned Latent Speed workflow for conversational H3 Base renders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.h3_render import (
    H3_VIDEO_LORA_OVERLAY_VERSION,
    H3RenderInputMode,
    H3VideoLoraSelection,
)
from panelforge.domain.recipes import RecipeRef
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings


H3_RENDER_OPERATION_ID = "video.generate.h3-base"
H3_RENDER_RECIPE_ID = "minimax-h3-latent-speed"
DEFAULT_H3_RENDER_PRESET_ID = "h3-latent-speed"


class H3RenderPresetValidationError(ValueError):
    """A published H3 render manifest disagrees with its workflow."""


@dataclass(frozen=True, slots=True)
class InputBinding:
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
    model_target: InputBinding
    clip_targets: tuple[InputBinding, ...]


@dataclass(frozen=True, slots=True)
class FrameBinding:
    load_node_id: str
    input_name: str
    targets: tuple[InputBinding, ...]


@dataclass(frozen=True, slots=True)
class OutputBinding:
    node_id: str
    history_field: str


@dataclass(frozen=True, slots=True)
class KeyframeBinding:
    source_node_id: str
    source_output_index: int
    selector_node_base: int
    save_node_base: int
    history_field: str
    margin_ms: int
    maximum: int


@dataclass(frozen=True, slots=True)
class H3RenderPreset:
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


@dataclass(frozen=True, slots=True)
class ValidatedH3RenderWorkflow:
    version: str
    status: str
    workflow_sha256: str
    scalar_inputs: Mapping[str, InputBinding]
    multi_inputs: Mapping[str, tuple[InputBinding, ...]]
    first_frame: FrameBinding
    last_frame: FrameBinding
    output_video: OutputBinding
    keyframes: KeyframeBinding
    video_lora_overlay: VideoLoraOverlayBinding | None
    presets: Mapping[str, H3RenderPreset]
    _workflow_json: bytes = field(repr=False)

    @property
    def reference(self) -> RecipeRef:
        return RecipeRef(
            operation_id=H3_RENDER_OPERATION_ID,
            recipe_id=H3_RENDER_RECIPE_ID,
            version=self.version,
            workflow_sha256=self.workflow_sha256,
        )

    @property
    def workflow(self) -> dict[str, Any]:
        value = json.loads(self._workflow_json)
        if not isinstance(value, dict):
            raise H3RenderPresetValidationError("stored workflow must be an object")
        return value


@dataclass(frozen=True, slots=True)
class H3RenderPresetRecipe:
    preset: ValidatedH3RenderWorkflow

    @property
    def reference(self) -> RecipeRef:
        return self.preset.reference

    @property
    def status(self) -> str:
        return self.preset.status

    @property
    def presets(self) -> Mapping[str, H3RenderPreset]:
        return self.preset.presets

    @property
    def output_node_id(self) -> str:
        return self.preset.output_video.node_id

    @property
    def output_history_field(self) -> str:
        return self.preset.output_video.history_field

    @property
    def keyframe_margin_ms(self) -> int:
        return self.preset.keyframes.margin_ms

    @property
    def maximum_keyframes(self) -> int:
        return self.preset.keyframes.maximum

    def keyframe_output_nodes(self, count: int) -> tuple[str, ...]:
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("keyframe count must be a non-negative integer")
        if count > self.maximum_keyframes:
            raise ValueError("too many keyframes")
        return tuple(
            str(self.preset.keyframes.save_node_base + index)
            for index in range(count)
        )

    def build_workflow(
        self,
        *,
        input_mode: H3RenderInputMode,
        first_frame: str | None,
        last_frame: str | None,
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        keyframe_indices: tuple[int, ...],
        video_lora: H3VideoLoraSelection | None = None,
    ) -> dict[str, Any]:
        return build_h3_render_workflow(
            self.preset,
            input_mode=input_mode,
            first_frame=first_frame,
            last_frame=last_frame,
            prompt=prompt,
            settings=settings,
            output_filename_prefix=output_filename_prefix,
            keyframe_indices=keyframe_indices,
            video_lora=video_lora,
        )


def load_h3_render_workflow(directory: Path) -> ValidatedH3RenderWorkflow:
    manifest = _read_object(directory / "manifest.json")
    workflow_config = _object(manifest.get("workflow"), "workflow")
    workflow_filename = _text(workflow_config.get("file"), "workflow.file")
    expected_hash = _text(workflow_config.get("sha256"), "workflow.sha256").lower()
    workflow_content = (directory / workflow_filename).read_bytes()
    actual_hash = hashlib.sha256(workflow_content).hexdigest()
    if actual_hash != expected_hash:
        raise H3RenderPresetValidationError(
            f"workflow hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    workflow = _decode_object(workflow_content, workflow_filename)
    return validate_h3_render_workflow(
        manifest,
        workflow,
        workflow_sha256=actual_hash,
    )


def validate_h3_render_workflow(
    manifest: Mapping[str, Any],
    workflow: Mapping[str, Any],
    *,
    workflow_sha256: str = "0" * 64,
) -> ValidatedH3RenderWorkflow:
    if manifest.get("schema_version") != 1:
        raise H3RenderPresetValidationError("schema_version must be 1")
    if manifest.get("operation") != H3_RENDER_OPERATION_ID:
        raise H3RenderPresetValidationError("invalid H3 render operation")
    if manifest.get("recipe_id") != H3_RENDER_RECIPE_ID:
        raise H3RenderPresetValidationError("invalid H3 render recipe")
    scope = _object(manifest.get("scope"), "scope")
    if scope.get("fps") != 24 or scope.get("input_modes") != [
        "t2va", "i2va", "l2va", "fl2va"
    ]:
        raise H3RenderPresetValidationError("scope must expose all H3 Base modes at 24 fps")
    nodes = _object(workflow, "workflow JSON")
    bindings = _object(manifest.get("bindings"), "bindings")
    scalar_names = {
        "positive_prompt",
        "megapixels",
        "duration_seconds",
        "seed",
        "output_filename_prefix",
    }
    scalar_inputs = {
        name: _input_binding(bindings.get(name), nodes, f"bindings.{name}")
        for name in scalar_names
    }
    multi_inputs = {
        name: _input_bindings(bindings.get(name), nodes, f"bindings.{name}")
        for name in ("aspect_ratio", "steps")
    }
    first = _frame_binding(bindings.get("first_frame"), nodes, "bindings.first_frame", synthetic=False)
    last = _frame_binding(bindings.get("last_frame"), nodes, "bindings.last_frame", synthetic=False)
    output_config = _object(bindings.get("output_video"), "bindings.output_video")
    output = OutputBinding(
        node_id=_text(output_config.get("node_id"), "output_video.node_id"),
        history_field=_text(output_config.get("history_field"), "output_video.history_field"),
    )
    if _object(nodes.get(output.node_id), f"workflow node {output.node_id}").get("class_type") != "SaveVideo":
        raise H3RenderPresetValidationError("output_video must target SaveVideo")
    decoded = _object(bindings.get("decoded_images"), "bindings.decoded_images")
    source_node_id = _text(decoded.get("node_id"), "decoded_images.node_id")
    if source_node_id not in nodes:
        raise H3RenderPresetValidationError("decoded image source node is missing")
    source_output_index = _non_negative_integer(decoded.get("output_index"), "decoded_images.output_index")
    keyframes = _object(bindings.get("keyframes"), "bindings.keyframes")
    keyframe_binding = KeyframeBinding(
        source_node_id=source_node_id,
        source_output_index=source_output_index,
        selector_node_base=_positive_integer(keyframes.get("selector_node_base"), "keyframes.selector_node_base"),
        save_node_base=_positive_integer(keyframes.get("save_node_base"), "keyframes.save_node_base"),
        history_field=_text(keyframes.get("history_field"), "keyframes.history_field"),
        margin_ms=_positive_integer(keyframes.get("margin_ms"), "keyframes.margin_ms"),
        maximum=_positive_integer(keyframes.get("maximum"), "keyframes.maximum"),
    )
    video_lora_overlay = (
        _video_lora_overlay_binding(bindings.get("video_lora_overlay"), nodes)
        if "video_lora_overlay" in bindings
        else None
    )
    _validate_assertions(manifest.get("workflow_assertions"), nodes)
    presets = _validate_presets(manifest.get("presets"))
    if DEFAULT_H3_RENDER_PRESET_ID not in presets:
        raise H3RenderPresetValidationError("default H3 render preset is missing")
    serialized = json.dumps(nodes, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return ValidatedH3RenderWorkflow(
        version=_text(manifest.get("version"), "version"),
        status=_text(manifest.get("status"), "status"),
        workflow_sha256=workflow_sha256,
        scalar_inputs=MappingProxyType(scalar_inputs),
        multi_inputs=MappingProxyType(multi_inputs),
        first_frame=first,
        last_frame=last,
        output_video=output,
        keyframes=keyframe_binding,
        video_lora_overlay=video_lora_overlay,
        presets=MappingProxyType(presets),
        _workflow_json=serialized,
    )


def build_h3_render_workflow(
    preset: ValidatedH3RenderWorkflow,
    *,
    input_mode: H3RenderInputMode,
    first_frame: str | None,
    last_frame: str | None,
    prompt: str,
    settings: VideoLabSettings,
    output_filename_prefix: str,
    keyframe_indices: tuple[int, ...],
    video_lora: H3VideoLoraSelection | None = None,
) -> dict[str, Any]:
    if not isinstance(input_mode, H3RenderInputMode):
        raise TypeError("input_mode must be an H3RenderInputMode")
    expected = {
        H3RenderInputMode.T2VA: (False, False),
        H3RenderInputMode.I2VA: (True, False),
        H3RenderInputMode.L2VA: (False, True),
        H3RenderInputMode.FL2VA: (True, True),
    }[input_mode]
    if (first_frame is not None, last_frame is not None) != expected:
        raise ValueError("frame values disagree with input_mode")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must not be empty")
    if not isinstance(settings, VideoLabSettings):
        raise TypeError("settings must be VideoLabSettings")
    if not isinstance(output_filename_prefix, str) or not output_filename_prefix.strip():
        raise ValueError("output_filename_prefix must not be empty")
    if not isinstance(keyframe_indices, tuple):
        raise TypeError("keyframe_indices must be a tuple")
    if tuple(sorted(set(keyframe_indices))) != keyframe_indices:
        raise ValueError("keyframe indices must be unique and chronological")
    if len(keyframe_indices) > preset.keyframes.maximum:
        raise ValueError("too many keyframes")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in keyframe_indices):
        raise ValueError("keyframe indices must be non-negative integers")
    if video_lora is not None and not isinstance(video_lora, H3VideoLoraSelection):
        raise TypeError("video_lora must be an H3VideoLoraSelection or None")

    workflow = preset.workflow
    scalar_values: Mapping[str, object] = {
        "positive_prompt": prompt,
        "megapixels": settings.megapixels,
        "duration_seconds": settings.duration_seconds,
        "seed": settings.seed,
        "output_filename_prefix": output_filename_prefix,
    }
    for name, value in scalar_values.items():
        binding = preset.scalar_inputs[name]
        workflow[binding.node_id]["inputs"][binding.input_name] = value
    for binding in preset.multi_inputs["aspect_ratio"]:
        workflow[binding.node_id]["inputs"][binding.input_name] = settings.aspect_ratio.value
    for binding in preset.multi_inputs["steps"]:
        workflow[binding.node_id]["inputs"][binding.input_name] = settings.steps

    _apply_frame(workflow, preset.first_frame, first_frame, synthetic=False)
    _apply_frame(workflow, preset.last_frame, last_frame, synthetic=False)
    if video_lora is not None:
        if preset.video_lora_overlay is None:
            raise ValueError("this H3 render workflow does not support video LoRAs")
        _apply_video_lora(workflow, preset.video_lora_overlay, video_lora)
    for index, frame_index in enumerate(keyframe_indices):
        selector_id = str(preset.keyframes.selector_node_base + index)
        save_id = str(preset.keyframes.save_node_base + index)
        workflow[selector_id] = {
            "inputs": {
                "image": [preset.keyframes.source_node_id, preset.keyframes.source_output_index],
                "batch_index": frame_index,
                "length": 1,
            },
            "class_type": "ImageFromBatch",
            "_meta": {"title": f"PanelForge keyframe {index + 1}"},
        }
        workflow[save_id] = {
            "inputs": {
                "filename_prefix": f"{output_filename_prefix}_keyframe_{index + 1:02d}",
                "images": [selector_id, 0],
            },
            "class_type": "SaveImage",
            "_meta": {"title": f"Save PanelForge keyframe {index + 1}"},
        }
    return workflow


def _apply_video_lora(
    workflow: dict[str, Any],
    binding: VideoLoraOverlayBinding,
    selection: H3VideoLoraSelection,
) -> None:
    if selection.overlay_version != binding.version:
        raise ValueError("H3 video LoRA overlay version disagrees with the workflow")
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
        "_meta": {"title": "PanelForge MiniMax video LoRA"},
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
            "_meta": {"title": "PanelForge MiniMax LoRA CLIP layer"},
        }
        clip_output = [binding.clip_last_layer_node_id, 0]
    for target in binding.clip_targets:
        workflow[target.node_id]["inputs"][target.input_name] = clip_output


def _apply_frame(
    workflow: dict[str, Any],
    binding: FrameBinding,
    value: str | None,
    *,
    synthetic: bool,
) -> None:
    for target in binding.targets:
        workflow[target.node_id]["inputs"].pop(target.input_name, None)
    loader = workflow.pop(binding.load_node_id, None)
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError("frame workflow value must not be empty")
    if synthetic:
        workflow[binding.load_node_id] = {
            "inputs": {binding.input_name: value},
            "class_type": "LoadImage",
            "_meta": {"title": "Load last frame"},
        }
    else:
        if not isinstance(loader, dict):
            raise ValueError("frame loader is missing from the workflow")
        workflow[binding.load_node_id] = loader
        workflow[binding.load_node_id]["inputs"][binding.input_name] = value
    for target in binding.targets:
        workflow[target.node_id]["inputs"][target.input_name] = [binding.load_node_id, 0]


def _frame_binding(
    value: Any,
    workflow: Mapping[str, Any],
    label: str,
    *,
    synthetic: bool,
) -> FrameBinding:
    config = _object(value, label)
    load_node_id = _text(config.get("load_node_id"), f"{label}.load_node_id")
    input_name = _text(config.get("input"), f"{label}.input")
    if not synthetic:
        loader = _object(workflow.get(load_node_id), f"workflow node {load_node_id}")
        if loader.get("class_type") != "LoadImage" or input_name not in _object(loader.get("inputs"), f"node {load_node_id}.inputs"):
            raise H3RenderPresetValidationError(f"{label} must target a LoadImage node")
    targets = _input_bindings(config.get("targets"), workflow, f"{label}.targets", require_input=not synthetic)
    if not targets:
        raise H3RenderPresetValidationError(f"{label} requires targets")
    return FrameBinding(load_node_id, input_name, targets)


def _video_lora_overlay_binding(
    value: Any,
    workflow: Mapping[str, Any],
) -> VideoLoraOverlayBinding:
    label = "bindings.video_lora_overlay"
    config = _object(value, label)
    version = _text(config.get("version"), f"{label}.version")
    if version != H3_VIDEO_LORA_OVERLAY_VERSION:
        raise H3RenderPresetValidationError("unsupported video LoRA overlay version")
    lora_node_id = _text(config.get("lora_node_id"), f"{label}.lora_node_id")
    clip_node_id = _text(
        config.get("clip_last_layer_node_id"),
        f"{label}.clip_last_layer_node_id",
    )
    if lora_node_id == clip_node_id or lora_node_id in workflow or clip_node_id in workflow:
        raise H3RenderPresetValidationError("video LoRA overlay node IDs must be unused")

    def source(raw: Any, source_label: str) -> NodeOutputBinding:
        source_config = _object(raw, source_label)
        node_id = _text(source_config.get("node_id"), f"{source_label}.node_id")
        if node_id not in workflow:
            raise H3RenderPresetValidationError(f"{source_label} node is missing")
        return NodeOutputBinding(
            node_id=node_id,
            output_index=_non_negative_integer(
                source_config.get("output_index"),
                f"{source_label}.output_index",
            ),
        )

    model_source = source(config.get("model_source"), f"{label}.model_source")
    clip_source = source(config.get("clip_source"), f"{label}.clip_source")
    model_target = _input_binding(
        config.get("model_target"), workflow, f"{label}.model_target"
    )
    clip_targets = _input_bindings(
        config.get("clip_targets"), workflow, f"{label}.clip_targets"
    )
    if workflow[model_target.node_id]["inputs"][model_target.input_name] != [
        model_source.node_id,
        model_source.output_index,
    ]:
        raise H3RenderPresetValidationError(
            "video LoRA model target does not consume the declared source"
        )
    for target in clip_targets:
        if workflow[target.node_id]["inputs"][target.input_name] != [
            clip_source.node_id,
            clip_source.output_index,
        ]:
            raise H3RenderPresetValidationError(
                "video LoRA CLIP target does not consume the declared source"
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


def _input_binding(value: Any, workflow: Mapping[str, Any], label: str, *, require_input: bool = True) -> InputBinding:
    config = _object(value, label)
    node_id = _text(config.get("node_id"), f"{label}.node_id")
    input_name = _text(config.get("input"), f"{label}.input")
    node = _object(workflow.get(node_id), f"workflow node {node_id}")
    inputs = _object(node.get("inputs"), f"workflow node {node_id}.inputs")
    if require_input and input_name not in inputs:
        raise H3RenderPresetValidationError(f"workflow node {node_id} has no input {input_name!r}")
    return InputBinding(node_id, input_name)


def _input_bindings(
    value: Any,
    workflow: Mapping[str, Any],
    label: str,
    *,
    require_input: bool = True,
) -> tuple[InputBinding, ...]:
    if not isinstance(value, list) or not value:
        raise H3RenderPresetValidationError(f"{label} must be a non-empty list")
    return tuple(
        _input_binding(item, workflow, f"{label}[{index}]", require_input=require_input)
        for index, item in enumerate(value)
    )


def _validate_assertions(value: Any, workflow: Mapping[str, Any]) -> None:
    if not isinstance(value, list) or not value:
        raise H3RenderPresetValidationError("workflow_assertions must not be empty")
    for index, raw in enumerate(value):
        label = f"workflow_assertions[{index}]"
        assertion = _object(raw, label)
        binding = _input_binding(assertion, workflow, label)
        actual = workflow[binding.node_id]["inputs"][binding.input_name]
        if actual != assertion.get("equals"):
            raise H3RenderPresetValidationError(
                f"{_text(assertion.get('id'), f'{label}.id')} expected {assertion.get('equals')!r}, got {actual!r}"
            )


def _validate_presets(value: Any) -> dict[str, H3RenderPreset]:
    if not isinstance(value, list) or not value:
        raise H3RenderPresetValidationError("presets must not be empty")
    result: dict[str, H3RenderPreset] = {}
    for index, raw in enumerate(value):
        label = f"presets[{index}]"
        config = _object(raw, label)
        preview = _object(config.get("preview"), f"{label}.preview")
        preset_id = _text(config.get("id"), f"{label}.id")
        settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio(config.get("aspect_ratio")),
            megapixels=config.get("megapixels"),
            duration_seconds=config.get("duration_seconds"),
            steps=config.get("steps"),
            seed=0,
        )
        result[preset_id] = H3RenderPreset(
            preset_id=preset_id,
            label=_text(config.get("label"), f"{label}.label"),
            aspect_ratio=settings.aspect_ratio,
            megapixels=settings.megapixels,
            duration_seconds=settings.duration_seconds,
            steps=settings.steps,
            preview_frames=_positive_integer(preview.get("frames"), f"{label}.preview.frames"),
            preview_fps=_positive_integer(preview.get("fps"), f"{label}.preview.fps"),
            preview_jpeg_quality=_positive_integer(preview.get("jpeg_quality"), f"{label}.preview.jpeg_quality"),
            preview_max_resolution=_positive_integer(preview.get("max_resolution"), f"{label}.preview.max_resolution"),
        )
    return result


def _read_object(path: Path) -> dict[str, Any]:
    return _decode_object(path.read_bytes(), str(path))


def _decode_object(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H3RenderPresetValidationError(f"invalid JSON in {label}") from error
    return dict(_object(value, label))


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise H3RenderPresetValidationError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise H3RenderPresetValidationError(f"{label} must be a non-empty string")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise H3RenderPresetValidationError(f"{label} must be a positive integer")
    return value


def _non_negative_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise H3RenderPresetValidationError(f"{label} must be a non-negative integer")
    return value


__all__ = [
    "DEFAULT_H3_RENDER_PRESET_ID",
    "H3RenderPresetRecipe",
    "H3RenderPresetValidationError",
    "ValidatedH3RenderWorkflow",
    "build_h3_render_workflow",
    "load_h3_render_workflow",
    "validate_h3_render_workflow",
]
