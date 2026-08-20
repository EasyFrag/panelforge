"""Versioned KREA2 text-to-image workflow used by Image Lab."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.krea2_lab import (
    Krea2AspectRatio,
    Krea2LabSettings,
    normalize_krea2_model_name,
)
from panelforge.domain.recipes import RecipeRef


KREA2_OPERATION_ID = "image.generate.t2i"
KREA2_RECIPE_ID = "krea2"
DEFAULT_KREA2_PRESET_ID = "krea2-base"


class Krea2PresetValidationError(ValueError):
    """A published KREA2 manifest disagrees with its workflow."""


@dataclass(frozen=True, slots=True)
class WorkflowInputBinding:
    node_id: str
    input_name: str


@dataclass(frozen=True, slots=True)
class ImageOutputBinding:
    node_id: str
    history_field: str


@dataclass(frozen=True, slots=True)
class Krea2LabPreset:
    preset_id: str
    label: str
    aspect_ratio: Krea2AspectRatio
    megapixels: float
    model_name: str

    def settings(
        self,
        *,
        seed: int,
        seed_locked: bool = False,
    ) -> Krea2LabSettings:
        return Krea2LabSettings(
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            megapixels=self.megapixels,
            seed=seed,
            seed_locked=seed_locked,
        )


@dataclass(frozen=True, slots=True)
class ValidatedKrea2Workflow:
    recipe_id: str
    version: str
    status: str
    workflow_sha256: str
    inputs: Mapping[str, WorkflowInputBinding]
    output_image: ImageOutputBinding
    presets: Mapping[str, Krea2LabPreset]
    qualified_models: tuple[str, ...]
    default_model: str
    _workflow_json: bytes = field(repr=False)

    @property
    def reference(self) -> RecipeRef:
        return RecipeRef(
            operation_id=KREA2_OPERATION_ID,
            recipe_id=self.recipe_id,
            version=self.version,
            workflow_sha256=self.workflow_sha256,
        )

    @property
    def workflow(self) -> dict[str, Any]:
        value = json.loads(self._workflow_json)
        if not isinstance(value, dict):
            raise Krea2PresetValidationError("stored workflow must be an object")
        return value


@dataclass(frozen=True, slots=True)
class Krea2T2IRecipe:
    """Application-facing adapter around one validated workflow snapshot."""

    preset: ValidatedKrea2Workflow

    @property
    def reference(self) -> RecipeRef:
        return self.preset.reference

    @property
    def status(self) -> str:
        return self.preset.status

    @property
    def presets(self) -> Mapping[str, Krea2LabPreset]:
        return self.preset.presets

    @property
    def qualified_models(self) -> tuple[str, ...]:
        return self.preset.qualified_models

    @property
    def default_model(self) -> str:
        return self.preset.default_model

    @property
    def output_node_id(self) -> str:
        return self.preset.output_image.node_id

    @property
    def output_history_field(self) -> str:
        return self.preset.output_image.history_field

    def build_workflow(
        self,
        *,
        prompt: str,
        settings: Krea2LabSettings,
        output_filename_prefix: str,
    ) -> dict[str, Any]:
        return build_krea2_t2i_workflow(
            self.preset,
            prompt=prompt,
            settings=settings,
            output_filename_prefix=output_filename_prefix,
        )


def load_krea2_t2i_workflow(directory: Path) -> ValidatedKrea2Workflow:
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
        raise Krea2PresetValidationError(
            f"workflow hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    workflow = _decode_object(workflow_content, workflow_filename)
    return validate_krea2_t2i_workflow(
        manifest,
        workflow,
        workflow_sha256=actual_hash,
    )


def validate_krea2_t2i_workflow(
    manifest: Mapping[str, Any],
    workflow: Mapping[str, Any],
    *,
    workflow_sha256: str = "0" * 64,
) -> ValidatedKrea2Workflow:
    if manifest.get("schema_version") != 1:
        raise Krea2PresetValidationError("schema_version must be 1")
    if manifest.get("operation") != KREA2_OPERATION_ID:
        raise Krea2PresetValidationError(
            f"operation must be {KREA2_OPERATION_ID!r}"
        )
    if manifest.get("recipe_id") != KREA2_RECIPE_ID:
        raise Krea2PresetValidationError(
            f"recipe_id must be {KREA2_RECIPE_ID!r}"
        )
    version = _text(manifest.get("version"), "version")
    status = _text(manifest.get("status"), "status")
    scope = _object(manifest.get("scope"), "scope")
    if scope != {
        "output_media_type": "image/png",
        "minimum_megapixels": 0.5,
        "maximum_megapixels": 4.0,
        "resolution_multiple": 8,
    }:
        raise Krea2PresetValidationError("scope must declare the KREA2 V1 limits")

    nodes = _object(workflow, "workflow JSON")
    if not nodes:
        raise Krea2PresetValidationError("workflow JSON must not be empty")
    bindings = _object(manifest.get("bindings"), "bindings")
    required_inputs = {
        "positive_prompt",
        "aspect_ratio",
        "megapixels",
        "model_name",
        "seed",
        "output_filename_prefix",
    }
    if set(bindings) != required_inputs | {"output_image"}:
        raise Krea2PresetValidationError(
            "bindings must define exactly the KREA2 V1 inputs and output"
        )
    input_bindings = {
        name: _input_binding(bindings[name], nodes, f"bindings.{name}")
        for name in required_inputs
    }
    for name in ("positive_prompt", "output_filename_prefix"):
        config = _object(bindings[name], f"bindings.{name}")
        sentinel = _text(config.get("sentinel"), f"bindings.{name}.sentinel")
        if _node_input(nodes, input_bindings[name]) != sentinel:
            raise Krea2PresetValidationError(f"workflow {name} is not neutralized")

    output_config = _object(bindings["output_image"], "output_image")
    output_node_id = _text(output_config.get("node_id"), "output_image.node_id")
    output_node = _object(nodes.get(output_node_id), f"workflow node {output_node_id}")
    if output_node.get("class_type") != "SaveImage":
        raise Krea2PresetValidationError("output_image must target SaveImage")
    output = ImageOutputBinding(
        node_id=output_node_id,
        history_field=_text(
            output_config.get("history_field"),
            "output_image.history_field",
        ),
    )

    model_config = _object(manifest.get("models"), "models")
    if set(model_config) != {"default", "qualified"}:
        raise Krea2PresetValidationError(
            "models must define exactly default and qualified"
        )
    default_model = _text(model_config.get("default"), "models.default")
    qualified_raw = model_config.get("qualified")
    if not isinstance(qualified_raw, list) or not qualified_raw:
        raise Krea2PresetValidationError("models.qualified must not be empty")
    qualified_models = tuple(
        _text(value, f"models.qualified[{index}]")
        for index, value in enumerate(qualified_raw)
    )
    if len({normalize_krea2_model_name(value) for value in qualified_models}) != len(
        qualified_models
    ):
        raise Krea2PresetValidationError("models.qualified contains duplicates")
    if default_model not in qualified_models:
        raise Krea2PresetValidationError("models.default must be qualified")
    if _node_input(nodes, input_bindings["model_name"]) != default_model:
        raise Krea2PresetValidationError("workflow model must equal models.default")

    _validate_assertions(manifest.get("workflow_assertions"), nodes)
    _validate_no_orphans(nodes, output.node_id)
    presets = _validate_presets(manifest.get("presets"), qualified_models)
    if DEFAULT_KREA2_PRESET_ID not in presets:
        raise Krea2PresetValidationError(
            f"presets must include {DEFAULT_KREA2_PRESET_ID!r}"
        )
    if presets[DEFAULT_KREA2_PRESET_ID].model_name != default_model:
        raise Krea2PresetValidationError(
            "the base preset model must equal models.default"
        )

    serialized = json.dumps(
        nodes,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return ValidatedKrea2Workflow(
        recipe_id=KREA2_RECIPE_ID,
        version=version,
        status=status,
        workflow_sha256=workflow_sha256,
        inputs=MappingProxyType(input_bindings),
        output_image=output,
        presets=MappingProxyType(presets),
        qualified_models=qualified_models,
        default_model=default_model,
        _workflow_json=serialized,
    )


def build_krea2_t2i_workflow(
    preset: ValidatedKrea2Workflow,
    *,
    prompt: str,
    settings: Krea2LabSettings,
    output_filename_prefix: str,
) -> dict[str, Any]:
    """Compile an isolated KREA2 workflow from explicit validated controls."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must not be empty")
    if not isinstance(settings, Krea2LabSettings):
        raise TypeError("settings must be Krea2LabSettings")
    qualified_keys = {
        normalize_krea2_model_name(value)
        for value in preset.qualified_models
    }
    if normalize_krea2_model_name(settings.model_name) not in qualified_keys:
        raise ValueError(f"unqualified KREA2 model {settings.model_name!r}")
    if not isinstance(output_filename_prefix, str) or not output_filename_prefix.strip():
        raise ValueError("output_filename_prefix must not be empty")

    workflow = preset.workflow
    values: Mapping[str, object] = {
        "positive_prompt": prompt,
        "aspect_ratio": settings.aspect_ratio.value,
        "megapixels": settings.megapixels,
        "model_name": settings.model_name,
        "seed": settings.seed,
        "output_filename_prefix": output_filename_prefix,
    }
    for name, value in values.items():
        binding = preset.inputs[name]
        workflow[binding.node_id]["inputs"][binding.input_name] = value
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
        raise Krea2PresetValidationError(
            f"workflow node {node_id} has no input {input_name!r}"
        )
    return WorkflowInputBinding(node_id=node_id, input_name=input_name)


def _validate_assertions(value: Any, workflow: Mapping[str, Any]) -> None:
    if not isinstance(value, list) or not value:
        raise Krea2PresetValidationError("workflow_assertions must not be empty")
    seen: set[str] = set()
    for index, raw in enumerate(value):
        label = f"workflow_assertions[{index}]"
        assertion = _object(raw, label)
        assertion_id = _text(assertion.get("id"), f"{label}.id")
        if assertion_id in seen:
            raise Krea2PresetValidationError(
                f"duplicate workflow assertion {assertion_id!r}"
            )
        seen.add(assertion_id)
        binding = _input_binding(assertion, workflow, label)
        if "equals" not in assertion:
            raise Krea2PresetValidationError(f"{label}.equals is required")
        actual = _node_input(workflow, binding)
        if actual != assertion["equals"]:
            raise Krea2PresetValidationError(
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
        raise Krea2PresetValidationError(
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


def _validate_presets(
    value: Any,
    qualified_models: tuple[str, ...],
) -> dict[str, Krea2LabPreset]:
    if not isinstance(value, list) or not value:
        raise Krea2PresetValidationError("presets must not be empty")
    result: dict[str, Krea2LabPreset] = {}
    for index, raw in enumerate(value):
        label = f"presets[{index}]"
        config = _object(raw, label)
        if set(config) != {
            "id",
            "label",
            "aspect_ratio",
            "megapixels",
            "model_name",
        }:
            raise Krea2PresetValidationError(f"{label} has invalid fields")
        preset_id = _text(config.get("id"), f"{label}.id")
        if preset_id in result:
            raise Krea2PresetValidationError(f"duplicate preset {preset_id!r}")
        model_name = _text(config.get("model_name"), f"{label}.model_name")
        if model_name not in qualified_models:
            raise Krea2PresetValidationError(f"{label} model is not qualified")
        try:
            defaults = Krea2LabSettings(
                model_name=model_name,
                aspect_ratio=Krea2AspectRatio(config.get("aspect_ratio")),
                megapixels=config.get("megapixels"),
                seed=0,
            )
        except (TypeError, ValueError) as error:
            raise Krea2PresetValidationError(f"invalid {label}: {error}") from error
        result[preset_id] = Krea2LabPreset(
            preset_id=preset_id,
            label=_text(config.get("label"), f"{label}.label"),
            aspect_ratio=defaults.aspect_ratio,
            megapixels=defaults.megapixels,
            model_name=defaults.model_name,
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
        raise Krea2PresetValidationError(f"invalid JSON in {label}") from error
    return dict(_object(value, label))


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Krea2PresetValidationError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Krea2PresetValidationError(f"{label} must be a non-empty string")
    return value
