"""One atomic index with explicit series/template/fabrication links."""
from copy import deepcopy
from pathlib import Path
from .local import _atomic_write, _json_bytes, _read_json_object, _require_regular_file


class LocalEpisodeThumbnailStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "episode-thumbnails"

    def _path(self):
        path = self.root / "index.json"
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("Lien de stockage de miniatures non autorisé.")
        return path

    def load(self):
        path = self._path()
        if not path.exists():
            return dict(schema_version=1, templates={}, series={}, episodes={})
        _require_regular_file(path)
        value = _read_json_object(path)
        if value.get("schema_version") != 1 or any(not isinstance(value.get(k), dict) for k in ("templates", "series", "episodes")):
            raise ValueError("Index des miniatures invalide.")
        return value

    def save(self, value):
        path = self._path()
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, _json_bytes(deepcopy(value)))
