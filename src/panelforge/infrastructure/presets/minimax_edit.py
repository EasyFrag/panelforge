"""Versioned adapter for the user's working MiniMax H3 hybrid still graph."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from panelforge.domain.minimax_edit import MinimaxEditSettings, MAX_RENDER_IMAGES, validate_prompt
from panelforge.domain.recipes import RecipeRef
from .krea2_edit import _binding, _validate_no_orphans


@dataclass(frozen=True)
class MinimaxEditWorkflow:
    reference: RecipeRef
    manifest: dict
    template: dict

    @property
    def output_node_id(self):
        return self.manifest["output"]["node_id"]

    def build(self, *, images, prompt, settings, dimensions, composition, output_prefix, guide=None):
        count = len(images) + (2 if guide else 0)
        if (not isinstance(settings, MinimaxEditSettings) or not 1 <= count <= MAX_RENDER_IMAGES
                or (guide and composition)):
            raise ValueError("Réglages ou nombre de références Minimax invalide.")
        if any(not isinstance(value, str) or not value for value in images) or (
                guide is not None and (not isinstance(guide, str) or not guide)):
            raise ValueError("Une référence Minimax n’a pas été téléversée.")
        if (len(dimensions) != 2 or any(type(value) is not int or not 64 <= value <= 4096
                                      or value % 32 for value in dimensions)):
            raise ValueError("Minimax attend des dimensions de 64 à 4096 pixels, multiples de 32.")
        validate_prompt(prompt, [{}] * count)
        if ("reference_megapixels" not in self.manifest["inputs"]
                and settings.reference_megapixels != self.manifest["fixed"]["reference_megapixels"]):
            raise ValueError("Ce workflow ne permet pas de changer la résolution de référence.")
        native = settings.reference_mode == "native"
        if native and (not self.manifest["capabilities"].get("native_reference") or composition or guide
                       or count != 1 and not self.manifest["capabilities"].get("native_multi_reference")):
            raise ValueError("Ce workflow ne prend pas en charge ces références en mode natif.")
        graph = deepcopy(self.template)
        values = {"prompt": prompt, "seed": int(settings.seed), "steps": settings.steps,
                  "width": dimensions[0], "height": dimensions[1], "output_prefix": output_prefix,
                  "reference_megapixels": settings.reference_megapixels}
        for name, bindings in self.manifest["inputs"].items():
            for binding in bindings:
                graph[binding["node_id"]]["inputs"][binding["input"]] = values[name]
        slots = self.manifest["image_slots"]
        encoder = graph[self.manifest["conditioning_node"]]["inputs"]
        for slot in slots:
            encoder.pop(slot["input"], None)
        # The manifest binds reference size; every slot keeps the same interpolation.
        graph[slots[0]["load_node"]]["inputs"]["image"] = guide if guide else images[0]
        encoder[slots[0]["input"]] = [slots[0]["scale_node"], 0]
        offset = 1
        if guide:
            binding = self.manifest["guide"]
            graph[binding["mask_node"]] = {"class_type": "MaskToImage",
                                           "inputs": {"mask": [slots[0]["load_node"], 1]}}
            slot = slots[1]
            graph[slot["scale_node"]] = deepcopy(graph[slots[0]["scale_node"]])
            graph[slot["scale_node"]]["inputs"]["image"] = [binding["mask_node"], 0]
            encoder[slot["input"]] = [slot["scale_node"], 0]
            remaining, offset = images, 2
        else:
            remaining = images[1:]
        for slot, filename in zip(slots[offset:], remaining):
            graph[slot["load_node"]] = {"class_type": "LoadImage", "inputs": {"image": filename}}
            graph[slot["scale_node"]] = deepcopy(graph[slots[0]["scale_node"]])
            graph[slot["scale_node"]]["inputs"]["image"] = [slot["load_node"], 0]
            encoder[slot["input"]] = [slot["scale_node"], 0]
        if native:
            for slot in slots[:count]:
                encoder[slot["input"]] = [slot["load_node"], 0]
                del graph[slot["scale_node"]]
        _validate_no_orphans(graph, self.output_node_id)
        return graph


def load_minimax_edit_workflow(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("operation_id") != "image.edit"
            or manifest.get("recipe_id") != "minimax.h3_still_edit" or manifest.get("engine") != "minimax"):
        raise ValueError("Manifeste Minimax non pris en charge.")
    path = (root / manifest["workflow_file"]).resolve()
    if path.parent != root:
        raise ValueError("Chemin de workflow Minimax invalide.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["workflow_sha256"]:
        raise ValueError("Empreinte du workflow Minimax invalide.")
    graph = json.loads(raw)
    for name, bindings in manifest["inputs"].items():
        for binding in bindings:
            _binding(binding, graph, name)
    for name, binding in manifest["components"].items():
        _binding(binding, graph, name)
    for node_id, class_type in manifest["required_nodes"].items():
        if graph.get(node_id, {}).get("class_type") != class_type:
            raise ValueError("Nœud Minimax incompatible avec le manifeste.")
    slots = manifest["image_slots"]
    if (len(slots) != MAX_RENDER_IMAGES
            or len({slot["load_node"] for slot in slots}) != len(slots)
            or len({slot["scale_node"] for slot in slots}) != len(slots)
            or [slot["input"] for slot in slots] != [f"ref_images.ref_image_{i}" for i in range(len(slots))]):
        raise ValueError("Les références Minimax doivent avoir des identités et un ordre explicites.")
    _validate_no_orphans(graph, manifest["output"]["node_id"])
    return MinimaxEditWorkflow(RecipeRef(operation_id=manifest["operation_id"], recipe_id=manifest["recipe_id"],
        version=manifest["version"], workflow_sha256=manifest["workflow_sha256"]), manifest, graph)
