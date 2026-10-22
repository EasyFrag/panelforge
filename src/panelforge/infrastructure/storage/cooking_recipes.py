"""Atomic culinary projects with an explicit index."""
import json
from pathlib import Path
import re
from threading import RLock
from .project_index import load_project_ids, save_indexed_project


class LocalCookingRecipeStore:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "cooking_recipes"
        self._lock = RLock()

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"recipe-[a-f0-9]{32}", identity):
            raise ValueError("Identifiant de recette invalide.")
        path = self.root / (identity + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Chemin de recette invalide.")
        return path

    def get(self, identity):
        with self._lock:
            p = json.loads(self._path(identity).read_text(encoding="utf-8"))
            if p.get("schema_version") != 1 or p.get("id") != identity:
                raise ValueError("Format de recette inconnu.")
            return p

    def list(self):
        with self._lock:
            ids = load_project_ids(self.root, self._path, self.get)
            return sorted([self.get(i) for i in ids], key=lambda p:p["updated_at"], reverse=True)

    def save(self, p):
        with self._lock:
            save_indexed_project(self.root, p, self._path, self.get)
