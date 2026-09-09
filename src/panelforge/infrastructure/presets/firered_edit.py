"""Exact imported FireRed workflow, with controls bound only by its manifest."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from panelforge.domain.firered_edit import FireRedEditSettings
from panelforge.domain.recipes import RecipeRef
from .krea2_edit import _binding, _validate_no_orphans


@dataclass(frozen=True)
class FireRedEditWorkflow:
    reference: RecipeRef
    manifest: dict
    template: dict
    engine: str = "firered"

    @property
    def status(self):
        return self.manifest["status"]

    @property
    def display_name(self):
        return self.manifest["display_name"]

    @property
    def output_node_id(self):
        return self.manifest["output"]["node_id"]

    @property
    def output_history_field(self):
        return self.manifest["output"]["history_field"]

    @property
    def output_media_type(self):
        return self.manifest["output"]["media_type"]

    def _value(self, section, name):
        binding = self.manifest[section][name]
        return self.template[binding["node_id"]]["inputs"][binding["input"]]

    @property
    def defaults(self):
        mode = "lightning" if self._value("inputs", "lightning") else "standard"
        return {"engine": self.engine, "model_id": self._value("components", "model"),
                "mode": mode, "megapixels": self._value("inputs", "megapixels"),
                "aspect_ratio": "source", "steps": self._value("inputs", f"steps_{mode}"),
                "cfg": self._value("inputs", f"cfg_{mode}"),
                "modes": {key: {"steps": self._value("inputs", f"steps_{key}"),
                                "cfg": self._value("inputs", f"cfg_{key}")}
                          for key in ("lightning", "standard")},
                "components": {name: self._value("components", name) for name in self.manifest["components"]}}

    def build(self, *, source_image, prompt, settings, output_prefix, sidecar_text):
        if not isinstance(settings, FireRedEditSettings):
            raise TypeError("FireRed workflow requires FireRed settings")
        if settings.model_name != self._value("components", "model"):
            raise ValueError("Le modèle sélectionné ne correspond pas à cette recette FireRed.")
        for value in (source_image, prompt, output_prefix):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("FireRed source, prompt and output prefix must not be empty")
        graph = deepcopy(self.template)
        values = {"source_image": source_image, "prompt": prompt, "megapixels": settings.megapixels,
                  "seed": settings.seed, "lightning": settings.mode == "lightning",
                  f"steps_{settings.mode}": settings.steps, f"cfg_{settings.mode}": settings.cfg,
                  "output_prefix": output_prefix}
        for name, value in values.items():
            binding = self.manifest["inputs"][name]
            graph[binding["node_id"]]["inputs"][binding["input"]] = value
        return graph


def load_firered_edit_workflow(directory: str | Path) -> FireRedEditWorkflow:
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("engine") != "firered"
            or manifest.get("operation_id") != "image.edit" or manifest.get("recipe_id") != "firered.image_edit"):
        raise ValueError("unsupported FireRed workflow manifest")
    path = (root / manifest["workflow_file"]).resolve()
    if path.parent != root.resolve():
        raise ValueError("unsafe FireRed workflow path")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["workflow_sha256"]:
        raise ValueError("FireRed workflow hash mismatch")
    graph = json.loads(raw)
    required = {"source_image", "prompt", "megapixels", "seed", "lightning", "steps_lightning",
                "steps_standard", "cfg_lightning", "cfg_standard", "output_prefix"}
    if set(manifest["inputs"]) != required or set(manifest["components"]) != {"model", "clip", "vae", "lightning_lora"}:
        raise ValueError("invalid FireRed workflow bindings")
    for section in ("inputs", "components"):
        for name, binding in manifest[section].items():
            _binding(binding, graph, name)
    output = manifest["output"]
    if output["history_field"] != "images" or output["media_type"] != "image/png":
        raise ValueError("FireRed output must be a PNG image")
    _validate_no_orphans(graph, output["node_id"])
    return FireRedEditWorkflow(RecipeRef(operation_id=manifest["operation_id"], recipe_id=manifest["recipe_id"],
        version=manifest["version"], workflow_sha256=manifest["workflow_sha256"]), manifest, graph)

