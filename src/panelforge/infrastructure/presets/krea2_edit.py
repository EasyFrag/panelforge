"""Validated adapter for the immutable KREA2 identity-edit workflow."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.krea2_edit import Krea2EditSettings
from panelforge.domain.recipes import RecipeRef


@dataclass(frozen=True, slots=True)
class EditBinding:
    node_id: str
    input_name: str


@dataclass(frozen=True, slots=True)
class ValidatedKrea2EditWorkflow:
    reference: RecipeRef
    status: str
    inputs: Mapping[str, EditBinding]
    lora_node_id: str
    lora_inputs: tuple[str, ...]
    output_node_id: str
    output_history_field: str
    output_media_type: str
    _workflow: Mapping[str, Any]

    @property
    def workflow(self) -> dict[str, Any]:
        return deepcopy(dict(self._workflow))

    def build(
        self,
        *,
        source_image: str,
        prompt: str,
        settings: Krea2EditSettings,
        output_prefix: str,
        sidecar_text: str,
    ) -> dict[str, Any]:
        for value, label in (
            (source_image, "source_image"),
            (prompt, "prompt"),
            (output_prefix, "output_prefix"),
            (sidecar_text, "sidecar_text"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must not be empty")
        if not isinstance(settings, Krea2EditSettings):
            raise TypeError("settings must be Krea2EditSettings")
        workflow = self.workflow
        values: Mapping[str, object] = {
            "source_image": source_image,
            "prompt": prompt,
            "model": settings.model_name,
            "aspect_ratio": settings.aspect_ratio.value,
            "megapixels": settings.megapixels,
            "seed": settings.seed,
            "steps": settings.steps,
            "ref_boost": settings.ref_boost,
            "output_prefix": output_prefix,
            "sidecar_text": sidecar_text,
        }
        for name, value in values.items():
            binding = self.inputs[name]
            workflow[binding.node_id]["inputs"][binding.input_name] = value
        lora_inputs = workflow[self.lora_node_id]["inputs"]
        for index, input_name in enumerate(self.lora_inputs):
            if index < len(settings.loras):
                lora = settings.loras[index]
                lora_inputs[input_name] = {
                    "on": True,
                    "lora": lora.name,
                    "strength": lora.strength,
                }
            else:
                lora_inputs[input_name] = {
                    "on": False,
                    "lora": "None",
                    "strength": 0,
                }
        return workflow


def load_krea2_edit_workflow(directory: str | Path) -> ValidatedKrea2EditWorkflow:
    root = Path(directory)
    manifest = _mapping(json.loads((root / "manifest.json").read_text(encoding="utf-8")), "manifest")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported KREA2 edit workflow manifest")
    workflow_path = root / _text(manifest.get("workflow_file"), "workflow_file")
    raw = workflow_path.read_bytes()
    expected = _text(manifest.get("workflow_sha256"), "workflow_sha256")
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("KREA2 edit workflow hash mismatch")
    workflow = _mapping(json.loads(raw), "workflow")
    inputs = {
        name: _binding(value, workflow, f"inputs.{name}")
        for name, value in _mapping(manifest.get("inputs"), "inputs").items()
    }
    required = {
        "source_image", "prompt", "model", "aspect_ratio", "megapixels",
        "seed", "steps", "ref_boost", "output_prefix", "sidecar_text",
    }
    if set(inputs) != required:
        raise ValueError("KREA2 edit workflow has invalid input bindings")
    lora_node_id = _text(manifest.get("lora_node_id"), "lora_node_id")
    lora_node = _mapping(workflow.get(lora_node_id), "LoRA node")
    lora_node_inputs = _mapping(lora_node.get("inputs"), "LoRA inputs")
    lora_inputs_raw = manifest.get("lora_inputs")
    if not isinstance(lora_inputs_raw, list) or len(lora_inputs_raw) != 4:
        raise ValueError("KREA2 edit workflow requires four LoRA inputs")
    lora_inputs = tuple(_text(value, "LoRA input") for value in lora_inputs_raw)
    if any(value not in lora_node_inputs for value in lora_inputs):
        raise ValueError("KREA2 edit LoRA binding is missing")
    fixed = manifest.get("fixed_values")
    if not isinstance(fixed, list) or not fixed:
        raise ValueError("KREA2 edit fixed_values must not be empty")
    for index, raw_value in enumerate(fixed):
        value = _mapping(raw_value, f"fixed_values[{index}]")
        binding = _binding(value, workflow, f"fixed_values[{index}]")
        if workflow[binding.node_id]["inputs"][binding.input_name] != value.get("equals"):
            raise ValueError(f"fixed workflow value changed at {binding.node_id}.{binding.input_name}")
    output = _mapping(manifest.get("output"), "output")
    output_node_id = _text(output.get("node_id"), "output.node_id")
    if output_node_id not in workflow:
        raise ValueError("KREA2 edit output node is missing")
    _validate_no_orphans(workflow, output_node_id)
    return ValidatedKrea2EditWorkflow(
        reference=RecipeRef(
            operation_id=_text(manifest.get("operation_id"), "operation_id"),
            recipe_id=_text(manifest.get("recipe_id"), "recipe_id"),
            version=_text(manifest.get("version"), "version"),
            workflow_sha256=expected,
        ),
        status=_text(manifest.get("status"), "status"),
        inputs=MappingProxyType(inputs),
        lora_node_id=lora_node_id,
        lora_inputs=lora_inputs,
        output_node_id=output_node_id,
        output_history_field=_text(output.get("history_field"), "output.history_field"),
        output_media_type=_text(output.get("media_type"), "output.media_type"),
        _workflow=MappingProxyType(dict(workflow)),
    )


def _binding(raw: object, workflow: Mapping[str, Any], label: str) -> EditBinding:
    value = _mapping(raw, label)
    node_id = _text(value.get("node_id"), f"{label}.node_id")
    input_name = _text(value.get("input"), f"{label}.input")
    inputs = _mapping(_mapping(workflow.get(node_id), f"workflow.{node_id}").get("inputs"), "node inputs")
    if input_name not in inputs:
        raise ValueError(f"{label} points to a missing input")
    return EditBinding(node_id, input_name)


def _validate_no_orphans(workflow: Mapping[str, Any], output_node_id: str) -> None:
    reachable: set[str] = set()
    pending = [output_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node = _mapping(workflow.get(node_id), f"workflow.{node_id}")
        pending.extend(_dependencies(node.get("inputs"), workflow))
    orphaned = sorted(set(workflow) - reachable)
    if orphaned:
        raise ValueError(f"KREA2 edit workflow contains orphan nodes: {orphaned}")


def _dependencies(value: object, workflow: Mapping[str, Any]) -> set[str]:
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] in workflow and isinstance(value[1], int):
        return {value[0]}
    found: set[str] = set()
    if isinstance(value, Mapping):
        for child in value.values():
            found.update(_dependencies(child, workflow))
    elif isinstance(value, list):
        for child in value:
            found.update(_dependencies(child, workflow))
    return found


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()
