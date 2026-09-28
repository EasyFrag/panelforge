"""Durable timing samples, independent of removable factory cards."""
from pathlib import Path
from threading import RLock
from .local import _atomic_write, _json_bytes, _read_json_object


class LocalFactoryTimingsStore:
    def __init__(self, workspace_root):
        self.path = Path(workspace_root).resolve() / "video_factory" / "timings.json"
        self._lock = RLock()

    def load(self):
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("Le journal des durées ne peut pas être un lien.")
            if not self.path.exists():
                return dict(schema_version=1, records=[], seen=[])
            value = _read_json_object(self.path)
            if value.get("schema_version") != 1 or not isinstance(value.get("records"), list) or not isinstance(value.get("seen"), list):
                raise ValueError("Journal des durées incompatible.")
            return value

    def save(self, value):
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("Le journal des durées ne peut pas être un lien.")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.path, _json_bytes(value))
