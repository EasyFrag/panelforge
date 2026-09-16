"""Atomic fabrication documents, separate from editable story history."""
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import re
from threading import RLock

from .local import _atomic_write, _json_bytes, _read_json_object


class LocalEpisodeStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "episodes"
        self._lock = RLock()

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"episode-[a-f0-9]{32}", identity):
            raise ValueError("Identifiant de fabrication invalide.")
        path = self.root / f"{identity}.json"
        if path.is_symlink():
            raise ValueError("Lien de stockage non autorisé.")
        return path

    def get(self, identity):
        with self._lock:
            value = _read_json_object(self._path(identity))
        if value.get("schema_version") != 1 or value.get("episode_id") != identity:
            raise ValueError("Format de fabrication indisponible.")
        return value

    def save(self, value):
        with self._lock:
            value = deepcopy(value)
            path = self._path(value["episode_id"])
            self.root.mkdir(parents=True, exist_ok=True)
            value.update(schema_version=1, updated_at=datetime.now(UTC).isoformat())
            value.setdefault("created_at", value["updated_at"])
            _atomic_write(path, _json_bytes(value))
            return value

    def list(self, story_id):
        with self._lock:
            result = []
            for path in self.root.glob("episode-*.json"):
                try:
                    value = self.get(path.stem)
                    if value["story_id"] == story_id:
                        result.append({k: value[k] for k in ("episode_id", "story_id", "title", "story_revision", "source_hash", "updated_at")})
                except (OSError, ValueError):
                    continue
            return sorted(result, key=lambda item: item["updated_at"], reverse=True)
