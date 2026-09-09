"""Manifest-bound ComfyUI image upscaling, without a diffusion pass or prompt."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from panelforge.domain.recipes import RecipeRef


@dataclass(frozen=True)
class ImageUpscaleWorkflow:
    reference: RecipeRef
    manifest: dict
    template: dict

    @property
    def output_node_id(self):
        return self.manifest["output"]["node_id"]

    output_history_field = "images"
    output_media_type = "image/png"

    @property
    def preferred_model(self):
        return self.manifest["preferred_model"]

    def build(self, *, source_image, model_name, width, height, output_prefix):
        if any(not isinstance(v, str) or not v.strip() for v in (source_image, model_name, output_prefix)):
            raise ValueError("upscale inputs must not be empty")
        if any(type(v) is not int or v <= 0 for v in (width, height)) or width * height > 16_000_000:
            raise ValueError("invalid upscale dimensions")
        values = dict(source_image=source_image, model_name=model_name, width=width, height=height, output_prefix=output_prefix)
        graph = deepcopy(self.template)
        for name, binding in self.manifest["inputs"].items():
            graph[binding["node_id"]]["inputs"][binding["input"]] = values[name]
        return graph


def load_image_upscale_workflow(directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / "workflow_api.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if manifest["schema_version"] != 1 or digest != manifest["workflow_sha256"]:
        raise ValueError("invalid image upscale workflow manifest or hash")
    graph = json.loads(raw)
    if set(manifest["inputs"]) != {"source_image", "model_name", "width", "height", "output_prefix"}:
        raise ValueError("invalid image upscale input bindings")
    for binding in manifest["inputs"].values():
        if binding["input"] not in graph[binding["node_id"]]["inputs"]:
            raise ValueError("missing image upscale binding")
    if manifest["output"]["node_id"] not in graph:
        raise ValueError("missing image upscale output")
    return ImageUpscaleWorkflow(RecipeRef(operation_id="image.upscale", recipe_id=manifest["recipe_id"],
                                         version=manifest["version"], workflow_sha256=digest), manifest, graph)
