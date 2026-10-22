"""Recover the project/index write gap. Callers hold their store's lock."""

import json
from pathlib import Path

from .local import _atomic_write, _json_bytes


def _control_path(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Chemin d’index de projets invalide.")
    return path


def load_project_ids(root, project_path, get_project):
    index = _control_path(root, "index.json")
    ids = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
        raise ValueError("Format d’index de projets invalide.")
    if len(set(ids)) != len(ids):
        raise ValueError("Identifiants de projets dupliqués dans l’index.")
    pending = _control_path(root, "pending-index.json")
    if pending.exists():
        intent = json.loads(pending.read_text(encoding="utf-8"))
        if not isinstance(intent, dict) or set(intent) != {"schema_version", "id"} or intent["schema_version"] != 1:
            raise ValueError("Journal d’index de projets invalide.")
        identity = intent["id"]
        project_path(identity)
        try:
            get_project(identity)
        except FileNotFoundError:
            # Interrupted before the project was written: there is nothing to index.
            if identity in ids:
                raise
        else:
            if identity not in ids:
                ids.append(identity)
                _atomic_write(index, _json_bytes(ids))
        # A failed repair leaves the intent in place for the next attempt.
        pending.unlink()
    return ids


def save_indexed_project(root, value, project_path, get_project):
    path = project_path(value["id"])
    if value.get("schema_version") != 1:
        raise ValueError("Format de projet inconnu.")
    content = _json_bytes(value)
    root.mkdir(parents=True, exist_ok=True)
    ids = load_project_ids(root, project_path, get_project)
    if value["id"] in ids:
        _atomic_write(path, content)
        return

    pending = _control_path(root, "pending-index.json")
    _atomic_write(pending, _json_bytes({"schema_version": 1, "id": value["id"]}))
    _atomic_write(path, content)
    _atomic_write(_control_path(root, "index.json"), _json_bytes([*ids, value["id"]]))
    pending.unlink()
