"""Atomic journey journals with explicit identities and index."""
import json
from pathlib import Path
import re
from threading import RLock
from .local import _atomic_write, _json_bytes


class LocalImageJourneyStore:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "image_journeys"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"journey-[0-9a-f]{32}", identity):
            raise ValueError("Identifiant de parcours invalide.")
        path = self.root / (identity + ".json")
        if path.is_symlink():
            raise ValueError("Lien de parcours interdit.")
        return path

    def _index(self):
        path = self.root / "index.json"
        if path.is_symlink():
            raise ValueError("Lien d’index interdit.")
        return path

    def get(self, identity):
        with self.lock:
            value = json.loads(self._path(identity).read_text(encoding="utf-8"))
            if value.get("schema_version") != 1 or value.get("id") != identity:
                raise ValueError("Version ou identité du parcours invalide.")
            return value

    def list(self):
        with self.lock:
            path = self._index()
            ids = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            return sorted((self.get(i) for i in ids), key=lambda p: p["updated_at"], reverse=True)

    def save(self, project):
        with self.lock:
            _atomic_write(self._path(project["id"]), _json_bytes(project))
            path = self._index()
            ids = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if project["id"] not in ids:
                _atomic_write(path, _json_bytes([*ids, project["id"]]))
