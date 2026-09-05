"""Validated compiler for the KREA2 community two-pass batch workflow."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.krea2_batch import (
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2BatchSettings,
)
from panelforge.domain.recipes import RecipeRef


@dataclass(frozen=True, slots=True)
class WorkflowBinding:
    node_id: str
    input_name: str


@dataclass(frozen=True, slots=True)
class LoraSlotBinding:
    node_id: str
    name_input: str
    strength_input: str


@dataclass(frozen=True, slots=True)
class ValidatedKrea2BatchWorkflow:
    reference: RecipeRef
    status: str
    inputs: Mapping[str, WorkflowBinding]
    lora_slots: tuple[LoraSlotBinding, ...]
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
        prompt: str,
        settings: Krea2BatchSettings,
        seed: int,
        output_prefix: str,
        sidecar_text: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if not isinstance(settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        if (
            isinstance(seed, bool)
            or not isinstance(seed, int)
            or not 0 <= seed <= KREA2_BATCH_RGTHREE_MAX_SEED
        ):
            raise ValueError(
                f"seed must be between 0 and {KREA2_BATCH_RGTHREE_MAX_SEED}"
            )
        if not isinstance(output_prefix, str) or not output_prefix.strip():
            raise ValueError("output_prefix must not be empty")
        workflow = self.workflow
        values: Mapping[str, object] = {
            "prompt": prompt,
            "model": settings.model_name,
            "aspect_ratio": settings.aspect_ratio.value,
            "megapixels": settings.megapixels,
            "seed": seed,
            "output_prefix": output_prefix,
        }
        if "sidecar_text" in self.inputs:
            if not isinstance(sidecar_text, str) or not sidecar_text.strip():
                raise ValueError("sidecar_text must not be empty")
            values = {**values, "sidecar_text": sidecar_text}
        for name, value in values.items():
            binding = self.inputs[name]
            workflow[binding.node_id]["inputs"][binding.input_name] = value
        if len(settings.loras) <= len(self.lora_slots):
            for index, slot in enumerate(self.lora_slots):
                lora = settings.loras[index] if index < len(settings.loras) else None
                inputs = workflow[slot.node_id]["inputs"]
                inputs[slot.name_input] = lora.name if lora is not None else "None"
                inputs[slot.strength_input] = lora.strength if lora is not None else 0.0
        else:
            # The historical graph exports rgthree's deprecated four-slot stack.
            # Its model/clip outputs are compatible with Power Lora Loader, whose
            # optional inputs are intentionally dynamic. Upgrade only the compiled
            # job when the user needs more than four entries; the immutable source
            # workflow and its hash remain untouched.
            node_ids = {slot.node_id for slot in self.lora_slots}
            if len(node_ids) != 1:
                raise ValueError("extended KREA2 LoRA stacks require one shared loader node")
            node = workflow[next(iter(node_ids))]
            previous = _mapping(node.get("inputs"), "LoRA inputs")
            node["class_type"] = "Power Lora Loader (rgthree)"
            node["inputs"] = {
                "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
                **{
                    f"lora_{index + 1}": {
                        "on": True,
                        "lora": lora.name,
                        "strength": lora.strength,
                    }
                    for index, lora in enumerate(settings.loras)
                },
                "➕ Add Lora": "",
                "model": previous["model"],
                "clip": previous["clip"],
            }
        return workflow


def load_krea2_batch_workflow(directory: str | Path) -> ValidatedKrea2BatchWorkflow:
    root = Path(directory)
    manifest_path = root / "manifest.json"
    manifest = _mapping(json.loads(manifest_path.read_text(encoding="utf-8")), "manifest")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported KREA2 batch workflow manifest")
    workflow_path = root / _text(manifest.get("workflow_file"), "workflow_file")
    workflow_bytes = workflow_path.read_bytes()
    expected_hash = _text(manifest.get("workflow_sha256"), "workflow_sha256")
    if hashlib.sha256(workflow_bytes).hexdigest() != expected_hash:
        raise ValueError("KREA2 batch workflow hash mismatch")
    workflow = _mapping(json.loads(workflow_bytes), "workflow")
    inputs = {
        name: _binding(raw, workflow, f"inputs.{name}")
        for name, raw in _mapping(manifest.get("inputs"), "inputs").items()
    }
    required = {"prompt", "model", "aspect_ratio", "megapixels", "seed", "output_prefix"}
    input_names = frozenset(inputs)
    if input_names not in (
        frozenset(required),
        frozenset((*required, "sidecar_text")),
    ):
        raise ValueError("KREA2 batch workflow has invalid input bindings")
    slots_raw = manifest.get("lora_slots")
    if not isinstance(slots_raw, list) or len(slots_raw) != 4:
        raise ValueError("KREA2 batch workflow requires exactly four LoRA slots")
    slots = tuple(_lora_slot(raw, workflow, index) for index, raw in enumerate(slots_raw))
    fixed = manifest.get("fixed_values")
    if not isinstance(fixed, list) or not fixed:
        raise ValueError("KREA2 batch workflow fixed_values must not be empty")
    for index, raw in enumerate(fixed):
        value = _mapping(raw, f"fixed_values[{index}]")
        binding = _binding(value, workflow, f"fixed_values[{index}]")
        if workflow[binding.node_id]["inputs"][binding.input_name] != value.get("equals"):
            raise ValueError(f"fixed workflow value changed at {binding.node_id}.{binding.input_name}")
    output = _mapping(manifest.get("output"), "output")
    output_id = _text(output.get("node_id"), "output.node_id")
    if output_id not in workflow:
        raise ValueError("KREA2 batch output node is missing")
    if "sidecar_text" in inputs and workflow[output_id].get("class_type") != "SaveImageKJ":
        raise ValueError("KREA2 batch sidecar output must use SaveImageKJ")
    _validate_no_orphans(workflow, output_id)
    return ValidatedKrea2BatchWorkflow(
        reference=RecipeRef(
            operation_id=_text(manifest.get("operation_id"), "operation_id"),
            recipe_id=_text(manifest.get("recipe_id"), "recipe_id"),
            version=_text(manifest.get("version"), "version"),
            workflow_sha256=expected_hash,
        ),
        status=_text(manifest.get("status"), "status"),
        inputs=MappingProxyType(inputs),
        lora_slots=slots,
        output_node_id=output_id,
        output_history_field=_text(output.get("history_field"), "output.history_field"),
        output_media_type=_text(output.get("media_type"), "output.media_type"),
        _workflow=MappingProxyType(dict(workflow)),
    )


def _binding(raw: object, workflow: Mapping[str, Any], label: str) -> WorkflowBinding:
    value = _mapping(raw, label)
    node_id = _text(value.get("node_id"), f"{label}.node_id")
    input_name = _text(value.get("input"), f"{label}.input")
    node = _mapping(workflow.get(node_id), f"workflow.{node_id}")
    inputs = _mapping(node.get("inputs"), f"workflow.{node_id}.inputs")
    if input_name not in inputs:
        raise ValueError(f"{label} points to a missing workflow input")
    return WorkflowBinding(node_id, input_name)


def _lora_slot(raw: object, workflow: Mapping[str, Any], index: int) -> LoraSlotBinding:
    value = _mapping(raw, f"lora_slots[{index}]")
    node_id = _text(value.get("node_id"), "LoRA node_id")
    name_input = _text(value.get("name_input"), "LoRA name_input")
    strength_input = _text(value.get("strength_input"), "LoRA strength_input")
    inputs = _mapping(_mapping(workflow.get(node_id), f"workflow.{node_id}").get("inputs"), "LoRA inputs")
    if name_input not in inputs or strength_input not in inputs:
        raise ValueError("LoRA slot points to missing inputs")
    return LoraSlotBinding(node_id, name_input, strength_input)


def _validate_no_orphans(workflow: Mapping[str, Any], output_node_id: str) -> None:
    reachable: set[str] = set()
    pending = [output_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node = _mapping(workflow.get(node_id), f"workflow.{node_id}")
        for dependency in _dependencies(node.get("inputs"), workflow):
            pending.append(dependency)
    orphaned = sorted(set(workflow) - reachable)
    if orphaned:
        raise ValueError(f"KREA2 batch workflow contains orphan nodes: {orphaned}")


def _dependencies(value: object, workflow: Mapping[str, Any]) -> set[str]:
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] in workflow and isinstance(value[1], int):
        return {value[0]}
    result: set[str] = set()
    if isinstance(value, Mapping):
        for item in value.values():
            result.update(_dependencies(item, workflow))
    elif isinstance(value, list):
        for item in value:
            result.update(_dependencies(item, workflow))
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()
