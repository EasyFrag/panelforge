"""Atomic story V2 projects and explicit index, isolated from legacy stories."""
import json
from pathlib import Path
import re
from threading import RLock
from .local import _atomic_write, _json_bytes
from .project_index import load_project_ids, save_indexed_project

class LocalStoryV2Store:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "stories_v2"
        self._lock = RLock()

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"storyv2-[a-f0-9]{32}", identity):
            raise ValueError("Identifiant Histoire V2 invalide.")
        path = self.root / (identity + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Lien de projet interdit.")
        return path

    def get(self, identity):
        with self._lock:
            value = json.loads(self._path(identity).read_text(encoding="utf-8"))
            if value.get("schema_version") != 1 or value.get("id") != identity:
                raise ValueError("Format Histoire V2 inconnu.")
            return value

    def list(self):
        with self._lock:
            ids = load_project_ids(self.root, self._path, self.get)
            return sorted([self.get(i) for i in ids], key=lambda p:p["updated_at"], reverse=True)

    def save(self, value):
        with self._lock:
            save_indexed_project(self.root, value, self._path, self.get)

    def preferences(self):
        with self._lock:
            path = self.root / "preferences.json"
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def save_preferences(self, settings):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.root / "preferences.json", _json_bytes({k:v for k,v in settings.items() if k != "idea"}))
