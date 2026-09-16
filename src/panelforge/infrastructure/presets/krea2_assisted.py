"""Assisted-only sampling overlay on an explicitly pinned Batch workflow."""

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from panelforge.domain.krea2_batch import Krea2BatchSettings
from panelforge.domain.krea2_sampling import Krea2AssistedSampling, sampling_for
from panelforge.domain.krea2_assisted_workflows import Krea2AssistedWorkflowOutput
from panelforge.domain.recipes import RecipeRef
from .krea2_batch import ValidatedKrea2BatchWorkflow, WorkflowBinding


@dataclass(frozen=True, slots=True)
class ValidatedKrea2AssistedWorkflow:
    base: ValidatedKrea2BatchWorkflow
    reference: RecipeRef
    sampling_inputs: Mapping[str, WorkflowBinding]
    supports_sampling: bool = True
    display_name: str = "KREA2 · deux passes"
    description: str = "Workflow KREA2 historique, sans finition Flux."
    default_sampling_preset_id: str = "current"

    @property
    def output_node_id(self) -> str:
        return self.base.output_node_id

    @property
    def output_history_field(self) -> str:
        return self.base.output_history_field

    @property
    def output_media_type(self) -> str:
        return self.base.output_media_type

    @property
    def outputs(self) -> tuple[Krea2AssistedWorkflowOutput, ...]:
        return (Krea2AssistedWorkflowOutput(
            role="final",
            node_id=self.output_node_id,
            history_field=self.output_history_field,
            media_type=self.output_media_type,
        ),)

    @staticmethod
    def seed_metadata(seed: int) -> dict[str, int]:
        return {"root": seed, "krea_first": seed, "krea_refine": seed}

    def build(self, *, prompt: str, settings: Krea2BatchSettings, seed: int,
              output_prefix: str, sidecar_text: str | None = None) -> dict[str, Any]:
        graph = self.base.build(prompt=prompt, settings=settings, seed=seed,
                                output_prefix=output_prefix, sidecar_text=sidecar_text)
        sampling = sampling_for(settings)
        for name, binding in self.sampling_inputs.items():
            stage, field = name.split(".")
            graph[binding.node_id]["inputs"][binding.input_name] = getattr(getattr(sampling, stage), field)
        return graph


def load_krea2_assisted_workflow(directory: str | Path, base: ValidatedKrea2BatchWorkflow) -> ValidatedKrea2AssistedWorkflow:
    manifest = json.loads((Path(directory) / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported KREA2 Assisted sampling manifest")
    expected_base = {name: getattr(base.reference, name)
                     for name in ("operation_id", "recipe_id", "version", "workflow_sha256")}
    if manifest.get("base_workflow") != expected_base:
        raise ValueError("KREA2 Assisted base workflow does not match the pinned version")
    raw_inputs = manifest.get("sampling_inputs", {})
    expected = {f"{stage}.{field}" for stage in ("first_pass", "second_pass")
                for field in ("steps", "sampler", "scheduler")}
    if set(raw_inputs) != expected:
        raise ValueError("KREA2 Assisted requires six sampling bindings")
    graph = base.workflow
    bindings = {}
    default = Krea2AssistedSampling()
    for name, raw in raw_inputs.items():
        binding = WorkflowBinding(raw["node_id"], raw["input"])
        node = graph.get(binding.node_id, {})
        stage, field = name.split(".")
        expected_input = "sampler_name" if field == "sampler" else field
        if (node.get("class_type") != "KSampler" or binding.input_name != expected_input
                or node.get("inputs", {}).get(binding.input_name) != getattr(getattr(default, stage), field)):
            raise ValueError(f"invalid KREA2 Assisted sampling binding: {name}")
        bindings[name] = binding
    if len({(b.node_id, b.input_name) for b in bindings.values()}) != 6:
        raise ValueError("KREA2 Assisted sampling bindings must be distinct")
    for stage in ("first_pass", "second_pass"):
        if len({bindings[f"{stage}.{field}"].node_id for field in ("steps", "sampler", "scheduler")}) != 1:
            raise ValueError("each KREA2 Assisted pass must bind one sampler node")
    return ValidatedKrea2AssistedWorkflow(
        base=base,
        reference=RecipeRef(operation_id=manifest["operation_id"], recipe_id=manifest["recipe_id"],
                            version=manifest["version"], workflow_sha256=base.reference.workflow_sha256),
        sampling_inputs=MappingProxyType(bindings),
    )
