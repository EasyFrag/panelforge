"""Two ordered creative LoRAs, wired by the recipe's versioned manifest."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from panelforge.domain.h3_render import H3VideoLoraSelection, H3VideoLoraStack, validate_video_lora_stack
from .h3_checkpoint import CheckpointH3RenderRecipe


class MultiLoraH3RenderRecipe(CheckpointH3RenderRecipe):
    supports_video_lora_stack = True

    def __init__(self, recipe, directory: Path):
        super().__init__(recipe, directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        self.lora_config = manifest["video_lora_stack"]
        if self.lora_config["version"] != "0.1.0" or self.lora_config["mode"] not in {"shared", "per_pass"}:
            raise ValueError("Contrat de LoRA multiples indisponible.")
        self.per_pass = self.lora_config["mode"] == "per_pass"
        defaults = H3VideoLoraStack.from_dict(self.lora_config["defaults"])
        defaults.validate_mode(self.per_pass)
        graph = json.loads((directory / manifest["workflow"]["file"]).read_text(encoding="utf-8"))
        if self.per_pass:
            branches = self.lora_config["branches"]
            if len(branches) != 2 or len({b["extra_node_id"] for b in branches}) != 2:
                raise ValueError("Deux branches LoRA indépendantes sont requises.")
            for branch in branches:
                if branch["head_node_id"] not in graph or branch["extra_node_id"] in graph:
                    raise ValueError("Liaisons de branche LoRA invalides.")

    def video_lora_stack_spec(self):
        return {"supported": True, "maximum": 2, "mode": self.lora_config["mode"],
                "defaults": deepcopy(self.lora_config["defaults"])}

    def build_workflow(self, *, video_loras=None, video_lora=None, **kwargs):
        if video_loras is None:
            return super().build_workflow(video_lora=video_lora, **kwargs)
        validate_video_lora_stack(video_loras, video_lora, self.per_pass)
        entries = video_loras.active_entries
        first = H3VideoLoraSelection(entries[0].name, entries[0].strength, video_loras.clip_last_layer) if entries else None
        if self.per_pass and entries:
            # The legacy field is used only to seed the first loader of each branch.
            # Saved per-slot values remain the authority for all four forces.
            kwargs["bunny"] = replace(kwargs["bunny"], lora_second_strength=entries[0].second_strength)
        graph = super().build_workflow(video_lora=first, **kwargs)
        if len(entries) < 2:
            return graph
        if not self.per_pass:
            graph[self.lora_config["loader_node_id"]]["inputs"]["lora_2"] = {
                "on": True, "lora": entries[1].name, "strength": entries[1].strength,
            }
            return graph
        for index, branch in enumerate(self.lora_config["branches"]):
            head, extra = branch["head_node_id"], branch["extra_node_id"]
            node = deepcopy(graph[head])
            node["inputs"]["model"] = [head, 0]
            node["inputs"]["lora_name"] = entries[1].name
            node["inputs"]["strength_model"] = entries[1].strength if index == 0 else entries[1].second_strength
            node["_meta"] = {"title": f"PanelForge LoRA 2 · passe {index + 1}"}
            for target in branch["targets"]:
                if target["node_id"] in graph:
                    inputs = graph[target["node_id"]]["inputs"]
                    if inputs.get(target["input"]) == [head, 0]:
                        inputs[target["input"]] = [extra, 0]
            graph[extra] = node
        return graph

    def validate_dependencies(self, comfy, workflow):
        additional = {b["extra_node_id"]: ["lora_name"] for b in self.lora_config.get("branches", [])}
        super().validate_dependencies(comfy, workflow, additional_resources=additional)
