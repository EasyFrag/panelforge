"""Atomic culinary projects with an explicit index."""
import json
from pathlib import Path
import re
from threading import RLock
from .local import _atomic_write, _json_bytes


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
            index = self.root / "index.json"
            ids = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
            return sorted([self.get(i) for i in ids], key=lambda p:p["updated_at"], reverse=True)

    def save(self, p):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._path(p["id"]), _json_bytes(p))
            index = self.root / "index.json"
            ids = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
            if p["id"] not in ids:
                _atomic_write(index, _json_bytes([*ids, p["id"]]))
