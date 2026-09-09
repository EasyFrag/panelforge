"""Atomic journal plus a cross-process lease for the single local DLSS queue."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile
import time
from threading import RLock


class LocalDlssJobs:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "dlss"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _path(self, job_id):
        if not re.fullmatch(r"dlss-[0-9a-f]{32}", job_id):
            raise ValueError("Identifiant de tâche DLSS invalide.")
        return self.root / (job_id + ".json")

    def get(self, job_id):
        with self.lock:
            path = self._path(job_id)
            if path.is_symlink():
                raise ValueError("Lien de tâche DLSS interdit.")
            return json.loads(path.read_text(encoding="utf-8"))

    def save(self, job):
        with self.lock:
            atomic_json(self._path(job["job_id"]), job)
        return job

    def list(self):
        with self.lock:
            return sorted((self.get(p.stem) for p in self.root.glob("dlss-*.json")), key=lambda j: j["created_at"])

    @contextmanager
    def lease(self, name="worker", *, wait_timeout=0):
        # Handles are released by the OS even if the Lab is terminated.
        with (self.root / (name + ".lock")).open("a+b") as stream:
            stream.seek(0)
            deadline = time.monotonic() + wait_timeout
            if os.name == "nt":
                import msvcrt
                while True:
                    try:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError as error:
                        if time.monotonic() >= deadline:
                            raise BlockingIOError("Une opération DLSS est déjà active.") from error
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                while True:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)


def atomic_json(path, value):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".dlss-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
