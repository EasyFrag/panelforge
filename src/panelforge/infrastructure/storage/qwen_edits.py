"""Atomic Qwen project journal with an explicit project index."""

import hashlib
import json
from pathlib import Path
import re
from threading import RLock

from .local import _atomic_write, _json_bytes


class LocalQwenEditStore:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve() / "qwen_edits"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _directory(self, project_id):
        if not isinstance(project_id, str) or not re.fullmatch(r"qwen-[0-9a-f]{32}", project_id):
            raise ValueError("Identifiant de projet Qwen invalide.")
        path = self.root / project_id
        if path.is_symlink():
            raise ValueError("Lien de projet interdit.")
        return path

    def get(self, project_id):
        with self.lock:
            path = self._directory(project_id) / "project.json"
            if path.is_symlink():
                raise ValueError("Lien de projet interdit.")
            project = json.loads(path.read_text(encoding="utf-8"))
            if project.get("schema_version") != 1 or project.get("id") != project_id:
                raise ValueError("Version ou identité du projet Qwen invalide.")
            return project

    def list(self):
        with self.lock:
            path = self.root / "index.json"
            ids = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            return sorted((self.get(project_id) for project_id in ids), key=lambda p: p["updated_at"], reverse=True)

    def save(self, project):
        with self.lock:
            directory = self._directory(project["id"])
            directory.mkdir(exist_ok=True)
            _atomic_write(directory / "project.json", _json_bytes(project))
            path = self.root / "index.json"
            ids = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if project["id"] not in ids:
                _atomic_write(path, _json_bytes([*ids, project["id"]]))
            return project

    def save_workflow(self, project_id, attempt_id, workflow):
        if not re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_id):
            raise ValueError("Identifiant d’essai invalide.")
        content = _json_bytes(workflow)
        directory = self._directory(project_id)
        directory.mkdir(exist_ok=True)
        _atomic_write(directory / (attempt_id + ".workflow.json"), content)
        return hashlib.sha256(content).hexdigest()

    def read_workflow(self, project_id, attempt_id):
        if not re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_id):
            raise ValueError("Identifiant d’essai invalide.")
        return (self._directory(project_id) / (attempt_id + ".workflow.json")).read_bytes()
