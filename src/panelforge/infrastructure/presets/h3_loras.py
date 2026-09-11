"""Ordered creative LoRAs, wired by each recipe's versioned manifest."""
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
        version = self.lora_config["version"]
        if version not in {"0.1.0", "0.2.0"} or self.lora_config["mode"] not in {"shared", "per_pass"}:
            raise ValueError("Contrat de LoRA multiples indisponible.")
        self.maximum_loras = 2 if version == "0.1.0" else self.lora_config["maximum"]
        if type(self.maximum_loras) is not int or self.maximum_loras != (2 if version == "0.1.0" else 4):
            raise ValueError("Limite de LoRA incompatible avec le contrat.")
        self.per_pass = self.lora_config["mode"] == "per_pass"
        defaults = H3VideoLoraStack.from_dict(self.lora_config["defaults"])
        defaults.validate_mode(self.per_pass)
        if defaults.version != version or len(defaults.entries) > self.maximum_loras:
            raise ValueError("Réglages LoRA par défaut incompatibles avec le contrat.")
        graph = json.loads((directory / manifest["workflow"]["file"]).read_text(encoding="utf-8"))
        if self.per_pass:
            branches = self.lora_config["branches"]
            extra_ids = [node_id for branch in branches for node_id in self._extra_nodes(branch)]
            if (len(branches) != 2 or len({b["head_node_id"] for b in branches}) != 2
                    or len(extra_ids) != 2 * (self.maximum_loras - 1) or len(set(extra_ids)) != len(extra_ids)):
                raise ValueError("Deux branches LoRA indépendantes sont requises.")
            for branch in branches:
                if (branch["head_node_id"] not in graph or len(self._extra_nodes(branch)) != self.maximum_loras - 1
                        or any(node_id in graph for node_id in self._extra_nodes(branch))):
                    raise ValueError("Liaisons de branche LoRA invalides.")

    def _extra_nodes(self, branch):
        return [branch["extra_node_id"]] if self.lora_config["version"] == "0.1.0" else branch["extra_node_ids"]

    def video_lora_stack_spec(self):
        return {"supported": True, "maximum": self.maximum_loras, "mode": self.lora_config["mode"],
                "defaults": deepcopy(self.lora_config["defaults"])}

    def build_workflow(self, *, video_loras=None, video_lora=None, **kwargs):
        if video_loras is None:
            return super().build_workflow(video_lora=video_lora, **kwargs)
        validate_video_lora_stack(video_loras, video_lora, self.per_pass)
        if len(video_loras.entries) > self.maximum_loras:
            raise ValueError(f"Cette recette accepte au maximum {self.maximum_loras} LoRA.")
        entries = video_loras.active_entries
        first = H3VideoLoraSelection(entries[0].name, entries[0].strength, video_loras.clip_last_layer) if entries else None
        if self.per_pass and entries:
            # The legacy field is used only to seed the first loader of each branch.
            # Saved per-slot values remain the authority for both passes.
            kwargs["bunny"] = replace(kwargs["bunny"], lora_second_strength=entries[0].second_strength)
        graph = super().build_workflow(video_lora=first, **kwargs)
        if len(entries) < 2:
            return graph
        if not self.per_pass:
            for slot, entry in enumerate(entries[1:], 2):
                graph[self.lora_config["loader_node_id"]]["inputs"][f"lora_{slot}"] = {
                    "on": True, "lora": entry.name, "strength": entry.strength,
                }
            return graph
        for index, branch in enumerate(self.lora_config["branches"]):
            head = branch["head_node_id"]
            previous = head
            for slot, (entry, extra) in enumerate(zip(entries[1:], self._extra_nodes(branch)), 2):
                node = deepcopy(graph[head])
                node["inputs"]["model"] = [previous, 0]
                node["inputs"]["lora_name"] = entry.name
                node["inputs"]["strength_model"] = entry.strength if index == 0 else entry.second_strength
                node["_meta"] = {"title": f"PanelForge LoRA {slot} · passe {index + 1}"}
                graph[extra] = node
                previous = extra
            for target in branch["targets"]:
                if target["node_id"] in graph:
                    inputs = graph[target["node_id"]]["inputs"]
                    if inputs.get(target["input"]) == [head, 0]:
                        inputs[target["input"]] = [previous, 0]
        return graph

    def validate_dependencies(self, comfy, workflow):
        additional = {node_id: ["lora_name"] for branch in self.lora_config.get("branches", [])
                      for node_id in self._extra_nodes(branch)}
        super().validate_dependencies(comfy, workflow, additional_resources=additional)
