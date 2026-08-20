"""Versioned MiniMax H3 Ref2V workflow used by Video Lab."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain import RecipeRef, VideoAspectRatio, VideoLabSettings


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
    inputs: Mapping[str, WorkflowInputBinding]
    reference_images: tuple[ReferenceImageBinding, ...]
    output_video: VideoOutputBinding
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

    def build_workflow(
        self,
        *,
        source_images: Sequence[str],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
    ) -> dict[str, Any]:
        return build_video_lab_workflow(
            self.preset,
            source_images=source_images,
            prompt=prompt,
            settings=settings,
            output_filename_prefix=output_filename_prefix,
        )


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
    expected_binding_keys = required_inputs | {"reference_images", "output_video"}
    if set(bindings) != expected_binding_keys:
        raise VideoPresetValidationError(
            f"bindings must define exactly {sorted(expected_binding_keys)!r}"
        )

    input_bindings = {
        name: _input_binding(bindings[name], nodes, f"bindings.{name}")
        for name in required_inputs
    }
    prompt_config = _object(bindings["positive_prompt"], "positive_prompt")
    prompt_sentinel = _text(prompt_config.get("sentinel"), "positive_prompt.sentinel")
    prompt_binding = input_bindings["positive_prompt"]
    if _node_input(nodes, prompt_binding) != prompt_sentinel:
        raise VideoPresetValidationError("workflow prompt is not neutralized")

    references_raw = bindings["reference_images"]
    if not isinstance(references_raw, list) or len(references_raw) != 3:
        raise VideoPresetValidationError("reference_images must define exactly 3 slots")
    references = tuple(
        _reference_binding(value, nodes, index)
        for index, value in enumerate(references_raw)
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
        reference_images=references,
        output_video=output,
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
) -> dict[str, Any]:
    """Compile an isolated workflow and prune unused reference slots."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must not be empty")
    if not isinstance(settings, VideoLabSettings):
        raise TypeError("settings must be VideoLabSettings")
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
    }
    for name, value in values.items():
        binding = preset.inputs[name]
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
    return workflow


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
