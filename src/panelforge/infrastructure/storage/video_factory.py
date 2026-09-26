"""One atomically replaced factory journal with explicit item IDs."""
from copy import deepcopy
import os
from pathlib import Path
from threading import RLock

from .local import _atomic_write, _json_bytes, _read_json_object


class LocalVideoFactoryStore:
    def __init__(self, workspace_root):
        self.path = Path(workspace_root).resolve() / "video_factory" / "state.json"
        self._lock = RLock()
        self._runner_lock = None

    def claim(self):
        """Retain an OS lease for the process lifetime, including in-flight shutdown work."""
        with self._lock:
            if self._runner_lock is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = (self.path.parent / "runner.lock").open("a+b")
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                handle.close()
                raise RuntimeError("L’usine utilise déjà ce workspace dans un autre processus.") from error
            self._runner_lock = handle

    def load(self):
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("Lien de stockage non autorisé.")
            if not self.path.exists():
                return dict(schema_version=1, revision=0, paused=False, items=[])
            value = _read_json_object(self.path)
            if value.get("schema_version") != 1 or not isinstance(value.get("items"), list):
                raise ValueError("Journal d’usine invalide.")
            return value

    def save(self, value):
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("Lien de stockage non autorisé.")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.path, _json_bytes(value))
            return deepcopy(value)
