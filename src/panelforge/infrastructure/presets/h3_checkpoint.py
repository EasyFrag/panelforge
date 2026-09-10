"""Versioned model-source replacement, after the recipe has wired its samplers/LoRA."""
from copy import deepcopy
import json
from pathlib import Path

from panelforge.domain.h3_checkpoint import H3ModelLoading, validate_h3_checkpoint
from panelforge.domain.h3_render import H3RenderInputMode


class CheckpointH3RenderRecipe:
    supports_checkpoint_selection = True

    def __init__(self, recipe, directory: Path):
        self.recipe = recipe
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if (manifest["recipe_id"], manifest["version"], manifest["workflow"]["sha256"]) != (
                recipe.reference.recipe_id, recipe.reference.version, recipe.reference.workflow_sha256):
            raise ValueError("Le manifeste de sélection ne correspond pas à la recette de rendu.")
        self.config = manifest["checkpoint_selection"]
        if self.config["schema_version"] != 1:
            raise ValueError("Unsupported checkpoint binding schema")
        graph = json.loads((directory / manifest["workflow"]["file"]).read_text(encoding="utf-8"))
        self._defaults = {}
        for mode, binding in self.config["sources"].items():
            if mode not in {"h3-base", "ref2va"}:
                raise ValueError("Mode inconnu dans les liaisons de checkpoints.")
            node = graph[binding["node_id"]]
            values = node["inputs"]
            overlay = values[binding["overlay_input"]] if binding.get("overlay_input") else None
            self._defaults[mode] = H3ModelLoading(values[binding["checkpoint_input"]],
                                                  "hybrid" if overlay else "direct", overlay)

    def __getattr__(self, name):
        return getattr(self.recipe, name)

    def _mode(self, mode):
        return "ref2va" if mode is H3RenderInputMode.REF2VA else "h3-base"

    def model_loading(self, mode, checkpoint=None):
        validate_h3_checkpoint(checkpoint)
        key = self._mode(mode)
        if key not in self._defaults:
            raise ValueError("Checkpoint incompatible avec le mode de cette recette.")
        return H3ModelLoading(checkpoint) if checkpoint is not None else self._defaults[key]

    def checkpoint_spec(self, mode):
        loading = self.model_loading(mode)
        return {"supported": True, "default_label": " + ".join(filter(None, (loading.checkpoint, loading.overlay)))}

    def build_workflow(self, *, checkpoint=None, **kwargs):
        mode = kwargs.get("input_mode", H3RenderInputMode.REF2VA)
        self.model_loading(mode, checkpoint)
        graph = self.recipe.build_workflow(**kwargs)
        if checkpoint is not None:
            binding = self.config["sources"][self._mode(mode)]
            node_id = binding["node_id"]
            if node_id not in graph:
                raise ValueError("La source du modèle vidéo est absente du workflow compilé.")
            replacement = deepcopy(self.config["direct_loader"])
            replacement["inputs"][self.config["direct_checkpoint_input"]] = checkpoint
            graph[node_id] = replacement
        return graph

    def validate_dependencies(self, comfy, workflow, *, additional_resources=None):
        resources = deepcopy(self.recipe.manifest["resources"])
        resources.update(additional_resources or {})
        for binding in self.config["sources"].values():
            node_id = binding["node_id"]
            if node_id in workflow and workflow[node_id]["class_type"] == self.config["direct_loader"]["class_type"]:
                resources[node_id] = [self.config["direct_checkpoint_input"]]
        self.recipe.validate_dependencies(comfy, workflow, resources=resources)
