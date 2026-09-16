"""Validated standalone KREA2 two-pass + fixed Flux Klein workflow."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.krea2_assisted_workflows import Krea2AssistedWorkflowOutput
from panelforge.domain.krea2_batch import KREA2_BATCH_RGTHREE_MAX_SEED, Krea2BatchSettings
from panelforge.domain.krea2_sampling import sampling_for
from panelforge.domain.recipes import RecipeRef
from .krea2_batch import WorkflowBinding


@dataclass(frozen=True, slots=True)
class PowerLoraLoaderBinding:
    node_id: str
    capacity: int


@dataclass(frozen=True, slots=True)
class ValidatedKrea2FluxKleinWorkflow:
    reference: RecipeRef
    status: str
    display_name: str
    description: str
    default_sampling_preset_id: str
    inputs: Mapping[str, WorkflowBinding]
    sampling_inputs: Mapping[str, WorkflowBinding]
    lora_loaders: tuple[PowerLoraLoaderBinding, ...]
    outputs: tuple[Krea2AssistedWorkflowOutput, ...]
    _workflow: Mapping[str, Any]
    supports_sampling: bool = True

    @property
    def workflow(self) -> dict[str, Any]:
        return deepcopy(dict(self._workflow))

    @property
    def output_node_id(self) -> str:
        return self.outputs[0].node_id

    @property
    def output_history_field(self) -> str:
        return self.outputs[0].history_field

    @property
    def output_media_type(self) -> str:
        return self.outputs[0].media_type

    @staticmethod
    def seed_metadata(seed: int) -> dict[str, int]:
        return {
            "root": seed,
            "krea_first": seed,
            "krea_refine": _derived_seed(seed, "krea-refine"),
            "flux_klein": _derived_seed(seed, "flux-klein"),
        }

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
        if (isinstance(seed, bool) or not isinstance(seed, int)
                or not 0 <= seed <= KREA2_BATCH_RGTHREE_MAX_SEED):
            raise ValueError(f"seed must be between 0 and {KREA2_BATCH_RGTHREE_MAX_SEED}")
        if not isinstance(output_prefix, str) or not output_prefix.strip():
            raise ValueError("output_prefix must not be empty")
        if not isinstance(sidecar_text, str) or not sidecar_text.strip():
            raise ValueError("sidecar_text must not be empty")

        workflow = self.workflow
        width, height = settings.resolution
        values: Mapping[str, object] = {
            "prompt": prompt,
            "model": settings.model_name,
            "aspect_ratio": settings.aspect_ratio.value,
            # The latent refinement expands both axes by 1.5. The only MP
            # exposed to the user therefore remains the final Flux size.
            "krea_megapixels": round(settings.megapixels / (1.5 * 1.5), 4),
            "final_long_side": max(width, height),
            "first_seed": seed,
            "second_seed": _derived_seed(seed, "krea-refine"),
            "flux_seed": _derived_seed(seed, "flux-klein"),
            "final_prefix": output_prefix,
            "pre_flux_prefix": f"{output_prefix}-pre-flux",
            "final_sidecar": sidecar_text,
            "pre_flux_sidecar": sidecar_text,
        }
        for name, value in values.items():
            binding = self.inputs[name]
            workflow[binding.node_id]["inputs"][binding.input_name] = value

        sampling = sampling_for(settings)
        for name, binding in self.sampling_inputs.items():
            stage, field = name.split(".")
            value = getattr(getattr(sampling, stage), "steps" if field == "end_at_step" else field)
            workflow[binding.node_id]["inputs"][binding.input_name] = value

        remaining = list(settings.loras)
        for loader in self.lora_loaders:
            node_inputs = workflow[loader.node_id]["inputs"]
            for key in tuple(node_inputs):
                if key.startswith("lora_"):
                    del node_inputs[key]
            for index, lora in enumerate(remaining[:loader.capacity], start=1):
                node_inputs[f"lora_{index}"] = {
                    "on": True,
                    "lora": lora.name,
                    "strength": lora.strength,
                }
            remaining = remaining[loader.capacity:]
        if remaining:
            raise ValueError("The KREA2 Flux Klein workflow supports at most ten LoRAs")
        return workflow


def load_krea2_flux_klein_workflow(directory: str | Path) -> ValidatedKrea2FluxKleinWorkflow:
    root = Path(directory)
    manifest = _mapping(json.loads((root / "manifest.json").read_text(encoding="utf-8")), "manifest")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported KREA2 Flux Klein workflow manifest")
    workflow_path = root / _text(manifest.get("workflow_file"), "workflow_file")
    workflow_bytes = workflow_path.read_bytes()
    expected_hash = _text(manifest.get("workflow_sha256"), "workflow_sha256")
    if hashlib.sha256(workflow_bytes).hexdigest() != expected_hash:
        raise ValueError("KREA2 Flux Klein workflow hash mismatch")
    workflow = _mapping(json.loads(workflow_bytes), "workflow")

    inputs = {name: _binding(raw, workflow, f"inputs.{name}")
              for name, raw in _mapping(manifest.get("inputs"), "inputs").items()}
    expected_inputs = {
        "prompt", "model", "aspect_ratio", "krea_megapixels", "final_long_side",
        "first_seed", "second_seed", "flux_seed", "final_prefix", "pre_flux_prefix",
        "final_sidecar", "pre_flux_sidecar",
    }
    if set(inputs) != expected_inputs:
        raise ValueError("KREA2 Flux Klein workflow has invalid input bindings")

    raw_sampling = _mapping(manifest.get("sampling_inputs"), "sampling_inputs")
    expected_sampling = {f"{stage}.{field}" for stage in ("first_pass", "second_pass")
                         for field in ("steps", "sampler", "scheduler")}
    expected_sampling.add("first_pass.end_at_step")
    if set(raw_sampling) != expected_sampling:
        raise ValueError("KREA2 Flux Klein workflow requires six sampling bindings")
    sampling_inputs = {name: _binding(raw, workflow, f"sampling_inputs.{name}")
                       for name, raw in raw_sampling.items()}

    raw_loaders = manifest.get("lora_loaders")
    if not isinstance(raw_loaders, list) or len(raw_loaders) != 2:
        raise ValueError("KREA2 Flux Klein workflow requires two LoRA loaders")
    lora_loaders = []
    for index, raw in enumerate(raw_loaders):
        value = _mapping(raw, f"lora_loaders[{index}]")
        node_id = _text(value.get("node_id"), "LoRA node_id")
        capacity = value.get("capacity")
        node = _mapping(workflow.get(node_id), f"workflow.{node_id}")
        if node.get("class_type") != "Power Lora Loader (rgthree)" or capacity != 5:
            raise ValueError("invalid KREA2 Flux Klein LoRA loader")
        lora_loaders.append(PowerLoraLoaderBinding(node_id, capacity))
    first, second = lora_loaders
    if workflow[second.node_id]["inputs"].get("model") != [first.node_id, 0]:
        raise ValueError("KREA2 Flux Klein LoRA loaders must be chained")

    outputs = []
    raw_outputs = manifest.get("outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise ValueError("KREA2 Flux Klein outputs must not be empty")
    for index, raw in enumerate(raw_outputs):
        value = _mapping(raw, f"outputs[{index}]")
        node_id = _text(value.get("node_id"), "output.node_id")
        if _mapping(workflow.get(node_id), f"workflow.{node_id}").get("class_type") != "SaveImageKJ":
            raise ValueError("KREA2 Flux Klein outputs must use SaveImageKJ")
        outputs.append(Krea2AssistedWorkflowOutput(
            role=_text(value.get("role"), "output.role"),
            node_id=node_id,
            history_field=_text(value.get("history_field"), "output.history_field"),
            media_type=_text(value.get("media_type"), "output.media_type"),
            prefix_suffix=str(value.get("prefix_suffix", "")),
            required=value.get("required", True),
        ))
    if outputs[0].role != "final" or not outputs[0].required or len({o.role for o in outputs}) != len(outputs):
        raise ValueError("KREA2 Flux Klein requires one primary final output")

    fixed = manifest.get("fixed_values")
    if not isinstance(fixed, list) or not fixed:
        raise ValueError("KREA2 Flux Klein fixed_values must not be empty")
    for index, raw in enumerate(fixed):
        value = _mapping(raw, f"fixed_values[{index}]")
        binding = _binding(value, workflow, f"fixed_values[{index}]")
        if workflow[binding.node_id]["inputs"][binding.input_name] != value.get("equals"):
            raise ValueError(f"fixed workflow value changed at {binding.node_id}.{binding.input_name}")
    _validate_no_orphans(workflow, tuple(output.node_id for output in outputs))

    return ValidatedKrea2FluxKleinWorkflow(
        reference=RecipeRef(
            operation_id=_text(manifest.get("operation_id"), "operation_id"),
            recipe_id=_text(manifest.get("recipe_id"), "recipe_id"),
            version=_text(manifest.get("version"), "version"),
            workflow_sha256=expected_hash,
        ),
        status=_text(manifest.get("status"), "status"),
        display_name=_text(manifest.get("display_name"), "display_name"),
        description=_text(manifest.get("description"), "description"),
        default_sampling_preset_id=_text(manifest.get("default_sampling_preset_id"), "default_sampling_preset_id"),
        inputs=MappingProxyType(inputs),
        sampling_inputs=MappingProxyType(sampling_inputs),
        lora_loaders=tuple(lora_loaders),
        outputs=tuple(outputs),
        _workflow=MappingProxyType(dict(workflow)),
    )


def _derived_seed(seed: int, role: str) -> int:
    digest = hashlib.sha256(f"krea2-assisted-v1:{seed}:{role}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") % (KREA2_BATCH_RGTHREE_MAX_SEED + 1)


def _binding(raw: object, workflow: Mapping[str, Any], label: str) -> WorkflowBinding:
    value = _mapping(raw, label)
    node_id = _text(value.get("node_id"), f"{label}.node_id")
    input_name = _text(value.get("input"), f"{label}.input")
    inputs = _mapping(_mapping(workflow.get(node_id), f"workflow.{node_id}").get("inputs"), "node inputs")
    if input_name not in inputs:
        raise ValueError(f"{label} points to a missing workflow input")
    return WorkflowBinding(node_id, input_name)


def _validate_no_orphans(workflow: Mapping[str, Any], output_node_ids: tuple[str, ...]) -> None:
    reachable: set[str] = set()
    pending = list(output_node_ids)
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node = _mapping(workflow.get(node_id), f"workflow.{node_id}")
        pending.extend(_dependencies(node.get("inputs"), workflow))
    orphaned = sorted(set(workflow) - reachable)
    if orphaned:
        raise ValueError(f"KREA2 Flux Klein workflow contains orphan nodes: {orphaned}")


def _dependencies(value: object, workflow: Mapping[str, Any]) -> set[str]:
    if (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            and value[0] in workflow and isinstance(value[1], int)):
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
