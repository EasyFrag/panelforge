"""Atomic transition projects, addressed through an explicit index."""
import json
from pathlib import Path
import re
from threading import RLock
from .local import _atomic_write, _json_bytes


class LocalImageTransitionStore:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "image_transitions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"transitions-[0-9a-f]{32}", identity):
            raise ValueError("Identifiant de frise invalide.")
        path = self.root / (identity + ".json")
        if path.is_symlink():
            raise ValueError("Lien de projet interdit.")
        return path

    def get(self, identity):
        with self.lock:
            value = json.loads(self._path(identity).read_text(encoding="utf-8"))
            if value.get("schema_version") != 1 or value.get("id") != identity:
                raise ValueError("Version de frise inconnue.")
            return value

    def list(self):
        with self.lock:
            path = self.root / "index.json"
            identities = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            return sorted((self.get(i) for i in identities), key=lambda p: p["updated_at"], reverse=True)

    def save(self, project):
        with self.lock:
            _atomic_write(self._path(project["id"]), _json_bytes(project))
            path = self.root / "index.json"
            identities = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if project["id"] not in identities:
                _atomic_write(path, _json_bytes([*identities, project["id"]]))
