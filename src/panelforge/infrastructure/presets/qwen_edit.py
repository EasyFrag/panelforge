"""Qwen 2.1 multi-image adapter; all node identities live in its manifest."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from panelforge.domain.qwen_edit import QwenEditSettings, MAX_RENDER_IMAGES
from panelforge.domain.recipes import RecipeRef
from .krea2_edit import _binding, _validate_no_orphans


@dataclass(frozen=True)
class QwenEditWorkflow:
    reference: RecipeRef
    manifest: dict
    template: dict

    @property
    def output_node_id(self):
        return self.manifest["output"]["node_id"]

    def build(self, *, images, prompt, settings, dimensions, composition, output_prefix):
        if not isinstance(settings, QwenEditSettings) or not 1 <= len(images) <= MAX_RENDER_IMAGES:
            raise ValueError("Réglages ou nombre de références Qwen invalide.")
        if any(not isinstance(image, str) or not image for image in images):
            raise ValueError("Une référence Qwen n’a pas été téléversée.")
        graph = deepcopy(self.template)
        bindings = self.manifest["inputs"]
        values = {"prompt": prompt, "negative_prompt": settings.negative_prompt if settings.cfg > 1 else "",
                  "resolution": 0, "seed": int(settings.seed), "steps": settings.steps, "cfg": settings.cfg,
                  "output_prefix": output_prefix}
        for name, value in values.items():
            binding = bindings[name]
            graph[binding["node_id"]]["inputs"][binding["input"]] = value
        encoder = graph[self.manifest["conditioning_node"]]["inputs"]
        for slot in self.manifest["image_slots"]:
            encoder.pop(slot["input"], None)
        for slot, image in zip(self.manifest["image_slots"], images):
            graph[slot["node_id"]] = {"class_type": "LoadImage", "inputs": {"image": image}}
            encoder[slot["input"]] = [slot["node_id"], 0]
        for node_id in self.manifest["replaced_nodes"]:
            graph.pop(node_id, None)
        sampler = graph[self.manifest["sampler_node"]]["inputs"]
        if composition:
            latent = graph[self.manifest["latent_node"]]["inputs"]
            latent.update(width=dimensions[0], height=dimensions[1])
            sampler["latent_image"] = [self.manifest["latent_node"], 0]
        else:
            # Native node returns a latent matching its first, prepared reference.
            sampler["latent_image"] = [self.manifest["conditioning_node"], 2]
            graph.pop(self.manifest["latent_node"])
        _validate_no_orphans(graph, self.output_node_id)
        return graph


def load_qwen_edit_workflow(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("recipe_id") != "qwen.image_edit"
            or manifest.get("engine") != "qwen" or manifest.get("operation_id") != "image.edit"):
        raise ValueError("Manifeste Qwen non pris en charge.")
    path = (root / manifest["workflow_file"]).resolve()
    if path.parent != root:
        raise ValueError("Chemin de workflow Qwen invalide.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["workflow_sha256"]:
        raise ValueError("Empreinte du workflow Qwen invalide.")
    graph = json.loads(raw)
    for section in ("inputs", "components"):
        for name, binding in manifest[section].items():
            _binding(binding, graph, name)
    slots = manifest["image_slots"]
    if len(slots) != MAX_RENDER_IMAGES or len({s["node_id"] for s in slots}) != MAX_RENDER_IMAGES:
        raise ValueError("Les 16 entrées Qwen doivent avoir des identités distinctes.")
    for key, expected in (("conditioning_node", "TextEncodeQwenImage21"), ("sampler_node", "KSampler"),
                          ("latent_node", "EmptyLatentImage")):
        if graph[manifest[key]]["class_type"] != expected:
            raise ValueError("Nœud Qwen incompatible avec le manifeste.")
    return QwenEditWorkflow(RecipeRef(operation_id=manifest["operation_id"], recipe_id=manifest["recipe_id"],
        version=manifest["version"], workflow_sha256=manifest["workflow_sha256"]), manifest, graph)
