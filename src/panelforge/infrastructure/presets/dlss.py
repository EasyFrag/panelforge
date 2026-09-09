"""Versioned DLSS graphs; all node IDs and patch points live in manifests."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from panelforge.domain.recipes import RecipeRef


MODES = {"1": "1× (DLAA / native)", "1.5": "1.5× (Quality)", "1.724": "1.724× (Balanced)",
         "2": "2× (Performance)", "3": "3× (Ultra Performance)", "source": "2× (Performance)"}


class DlssWorkflow:
    def __init__(self, directory):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        content = (directory / self.manifest["workflow"]["file"]).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != self.manifest["workflow"]["sha256"]:
            raise ValueError("Empreinte du workflow DLSS incorrecte.")
        self.graph = json.loads(content)
        self.reference = RecipeRef(operation_id=self.manifest["operation"], recipe_id=self.manifest["recipe_id"],
                                   version=self.manifest["version"], workflow_sha256=digest)
        for points in self.manifest["bindings"].values():
            for point in points if isinstance(points, list) else [points]:
                if point["input"] not in self.graph[point["node"]]["inputs"]:
                    raise ValueError("Liaison DLSS absente du graphe.")
        for stage in self.manifest.get("progress_stages", []):
            if stage["node"] not in self.graph or not stage["key"] or not stage["label"]:
                raise ValueError("Phase de progression DLSS invalide.")

    def build(self, source, prefix, settings):
        graph = deepcopy(self.graph)
        values = {"source": source, "prefix": prefix, "size": MODES[settings.size]}
        for name, points in self.manifest["bindings"].items():
            value = values[name] if name in values else getattr(settings, name)
            for point in points if isinstance(points, list) else [points]:
                graph[point["node"]]["inputs"][point["input"]] = value
        return graph

    def output(self, record):
        values = record.get("outputs", {}).get(self.manifest["output_node"], {})
        files = [item for field in ("images", "videos", "gifs") for item in values.get(field, [])
                 if isinstance(item, dict) and item.get("filename") and item.get("type", "output") == "output"]
        if len(files) != 1:
            raise ValueError("Le workflow DLSS n’a pas renvoyé un fichier final unique.")
        return files[0]

    def reports(self, record):
        result = []
        for node in self.manifest["report_nodes"]:
            texts = record.get("outputs", {}).get(node, {}).get("text", [])
            if isinstance(texts, str):
                texts = [texts]
            for value in texts:
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, dict):
                    result.append(parsed)
        if len(result) != len(self.manifest["report_nodes"]):
            raise ValueError("Le rapport DLSS manque ; le résultat n’est pas encore importé.")
        return result
