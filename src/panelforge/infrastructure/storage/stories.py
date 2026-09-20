"""Atomic story projects and an isolated, versioned editorial recipe."""
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import re
from threading import RLock

from panelforge.domain.stories import (
    RECIPE_ID, RECIPE_VERSION, story_recipe_spec,
)
from .local import _atomic_write, _json_bytes, _read_json_object
from .prompt_recipes import LocalPromptRecipeStore
from panelforge.domain.long_stories import ENGINE, is_v2


class LocalStoryStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "stories"
        self._lock = RLock()

    def _path(self, project_id):
        if not isinstance(project_id, str) or not re.fullmatch(r"story-[a-f0-9]{32}", project_id):
            raise ValueError("Identifiant d’histoire invalide.")
        path = self.root / f"{project_id}.json"
        if path.is_symlink():
            raise ValueError("Lien de stockage non autorisé.")
        return path

    def get(self, project_id):
        with self._lock:
            value = _read_json_object(self._path(project_id))
        if value.get("schema_version") not in {1, 2} or value.get("project_id") != project_id:
            raise ValueError("Format d’histoire indisponible.")
        if value.get("schema_version") == 2 and value.get("narrative_engine") != ENGINE:
            raise ValueError("Version de moteur narratif indisponible.")
        return value

    def save(self, project):
        with self._lock:
            path = self._path(project["project_id"])
            self.root.mkdir(parents=True, exist_ok=True)
            value = deepcopy(project)
            value["updated_at"] = datetime.now(UTC).isoformat()
            value.setdefault("created_at", value["updated_at"])
            value["schema_version"] = 2 if is_v2(value) else 1
            value["version"] = value.get("version", 0) + 1
            persisted = deepcopy(value)
            persisted.pop("long_status", None)  # Derived on read; not an authoritative approval.
            _atomic_write(path, _json_bytes(persisted))
            return value

    def list(self, limit=30):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limite de liste invalide.")
        with self._lock:
            paths = sorted(self.root.glob("story-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            results = []
            for path in paths:
                try:
                    value = self.get(path.stem)
                    results.append({k: value[k] for k in ("project_id", "title", "updated_at", "version")})
                except (ValueError, OSError):
                    continue
                if len(results) == limit:
                    break
            return results


class LocalStoryRecipeStore(LocalPromptRecipeStore):
    """Reuse revision storage without adding a recipe to the H3 catalogs."""
    def __init__(self, workspace_root, defaults_root):
        # A single path remains accepted by tests and old launchers. The
        # runtime passes a catalog so every family keeps a separate archive.
        if isinstance(defaults_root, dict):
            self.defaults_roots = {key: Path(path).resolve() for key, path in defaults_root.items()}
        else:
            self.defaults_roots = {(RECIPE_ID, RECIPE_VERSION): Path(defaults_root).resolve()}
        super().__init__(workspace_root, None, next(iter(self.defaults_roots.values())))

    def _directory(self, key, version):
        if (key, version) not in self.defaults_roots:
            raise KeyError("Recette d’histoire inconnue.")
        return self.root / key / version

    def _defaults(self, key, version):
        root = self.defaults_roots.get((key, version))
        if root is None:
            raise KeyError("Recette d’histoire inconnue.")
        fields = {field: (root / filename).read_text(encoding="utf-8") for field, filename in (
            ("plan.system", "concepts.txt"), ("writer.system", "scenario.txt"), ("revision.system", "revision.txt"))}
        return {**fields, "render.system": "", "camera_contract": ""}, []

    def _ensure(self, key, version):
        directory, index = super()._ensure(key, version)
        if (key, version) != (RECIPE_ID, RECIPE_VERSION):
            return directory, index
        if index.get("story_editorial_revision") == 3:
            return directory, index
        root = self.defaults_roots[(key, version)]
        initial, templates = self._defaults(key, version)
        r2 = {**initial, **{field: (root / "editorial-r2" / filename).read_text(encoding="utf-8")
            for field, filename in (("plan.system", "concepts.txt"), ("writer.system", "scenario.txt"), ("revision.system", "revision.txt"))}}
        # Only upgrade untouched factory instructions. Explicit edits or a
        # rollback remain authoritative, including after process restart.
        if (index.get("story_editorial_revision") != 2 and index["active"] == 1 and index["last"] == 1
                and self._read_revision(directory, 1)["fields"] == initial):
            self._write_revision(directory, 2, r2, templates, "Mélodrame : fruits, trahison, enjeux et relations cohérentes")
            index = {**index, "active": 2, "last": 2}
        if (index["active"] == 2 and index["last"] == 2
                and self._read_revision(directory, 1)["fields"] == initial
                and self._read_revision(directory, 2)["fields"] == r2):
            fields = {**initial, **{field: (root / "editorial-r3" / filename).read_text(encoding="utf-8")
                for field, filename in (("plan.system", "concepts.txt"), ("writer.system", "scenario.txt"), ("revision.system", "revision.txt"))}}
            self._write_revision(directory, 3, fields, templates, "Scènes concrètes : exemples JSON, actes, conséquences et continuité")
            index = {**index, "active": 3, "last": 3}
        index = {**index, "story_editorial_revision": 3}
        _atomic_write(directory / "active.json", _json_bytes(index))
        return directory, index

    def list(self):
        return [story_recipe_spec(key, version) | {"id": key} for key, version in self.defaults_roots]
