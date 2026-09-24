"""Manifest-owned video VAE revisions; original recipes remain executable."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path


def _graph_bytes(graph):
    return json.dumps(graph, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class VideoVaeRecipe:
    """Change one declared loader after the original recipe compiles its graph."""

    def __init__(self, recipe, entry, replacement):
        self.recipe = recipe
        self.source_reference = recipe.reference
        self.reference = replace(
            recipe.reference,
            version=entry["version"],
            workflow_sha256=entry["workflow_sha256"],
        )
        self._node_id = entry["node_id"]
        self._replacement = replacement

    def __getattr__(self, name):
        return getattr(self.recipe, name)

    def _apply(self, graph):
        node = graph.get(self._node_id)
        if (not isinstance(node, dict) or node.get("class_type") != "VAELoader"
                or node.get("inputs", {}).get("vae_name") != self._replacement["from"]):
            raise ValueError("The video VAE loader no longer matches its versioned contract.")
        node["inputs"]["vae_name"] = self._replacement["to"]
        return graph

    def build_workflow(self, **kwargs):
        return self._apply(self.recipe.build_workflow(**kwargs))


class H3VideoVaeUpdates:
    """An explicit list of source identities, bindings and effective graph hashes."""

    def __init__(self, workflows_root: Path, manifest_path: Path):
        self.root = workflows_root.resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1:
            raise ValueError("Unsupported video VAE update manifest.")
        self.replacement = manifest["replacement"]
        self.entries = {}
        for entry in manifest["recipes"]:
            source = entry["source"]
            key = (source["operation_id"], source["recipe_id"], source["version"],
                   source["workflow_sha256"])
            if key in self.entries:
                raise ValueError("Duplicate video VAE source recipe.")
            self.entries[key] = entry

    def upgrade(self, recipe):
        ref = recipe.reference
        key = (ref.operation_id, ref.recipe_id, ref.version, ref.workflow_sha256)
        entry = self.entries.get(key)
        if entry is None:
            raise ValueError("The recipe has no pinned video VAE update.")
        source = entry["source"]
        directory = (self.root / source["directory"]).resolve()
        if not directory.is_relative_to(self.root):
            raise ValueError("Video VAE source is outside the workflow directory.")
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        path = (directory / manifest["workflow"]["file"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Invalid source workflow path.")
        content = path.read_bytes()
        if (manifest.get("operation", manifest.get("operation_id")),
                manifest["recipe_id"], manifest["version"],
                manifest["workflow"]["sha256"]) != key or hashlib.sha256(content).hexdigest() != ref.workflow_sha256:
            raise ValueError("The video VAE source recipe fingerprint has changed.")
        updated = VideoVaeRecipe(recipe, entry, self.replacement)
        graph = updated._apply(json.loads(content))
        if hashlib.sha256(_graph_bytes(graph)).hexdigest() != updated.reference.workflow_sha256:
            raise ValueError("The updated video VAE workflow fingerprint is invalid.")
        return updated
