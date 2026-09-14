"""File-backed, immutable instruction packages and a persistent active pointer."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock

from panelforge.application.prompt_recipes import EDITABLE_RECIPES, EDITABLE_KEYS
from panelforge.application.prompt_recipe_text import validate_template
from .local import _atomic_write, _json_bytes, _read_json_object


CAMERA_CONTRACT = (
    "CAMERA TARGET CONTRACT (technical revision 2): target_clause must be empty for shake and POV. "
    "When non-empty, it must be an English spatial or visual continuation beginning with exactly one of: "
    "to, toward, onto, into, from, behind, beside, above, below, away from, around, along, across, "
    "past, through, following, keeping, maintaining, revealing, showing, centered on, focused on, "
    "ending on, framing, holding, leaving, placing, as, while, until, with. "
    "Use 'beside' or 'along ... beside ...', never 'alongside'. "
    "Motion, amplitude and speed belong only in their dedicated fields."
)


class LocalPromptRecipeStore:
    def __init__(self, workspace_root, cookbooks, defaults_root, *, render_systems=None):
        self.root = Path(workspace_root).resolve() / "prompt_recipes"
        self.cookbooks = cookbooks
        self.defaults_root = Path(defaults_root).resolve()
        self.render_systems = render_systems or {}
        self._lock = RLock()

    def _directory(self, key, version):
        if (key, version) not in EDITABLE_KEYS:
            raise KeyError("Cette recette historique n'est pas éditable dans cette version.")
        return self.root / key / version

    def _defaults(self, key, version):
        cookbook = self.cookbooks.get(key, version)
        fields = {
            "plan.system": cookbook.beat_sheet_system_prompt,
            "writer.system": cookbook.final_prompt_system_prompt,
            "revision.system": cookbook.revision_system_prompt,
            "render.system": self.render_systems.get((key, version), ""),
            "camera_contract": "",
        }
        modules = {"vocal_policy"}
        if ".combat." in key:
            modules |= {"combat_preparation", "combat_cinematic_policy"}
        else:
            modules |= {"prompt_lab", "classic_cinematic" if ".classic." in key else "sensual_cinematic"}
        templates = []
        entries = json.loads((self.defaults_root / "manifest.json").read_text(encoding="utf-8"))
        for field, info in entries.items():
            if field.split(".")[0] in modules:
                source = (self.defaults_root / info["file"]).resolve()
                if not source.is_relative_to(self.defaults_root):
                    raise ValueError("invalid default instruction path")
                fields[field] = source.read_text(encoding="utf-8")
                if info["template"]:
                    templates.append(field)
        return fields, templates

    def _ensure(self, key, version):
        directory = self._directory(key, version)
        index = directory / "active.json"
        if not index.exists():
            fields, templates = self._defaults(key, version)
            # Revision 1 always preserves the pre-editor content for existing Plans.
            self._write_revision(directory, 1, fields, templates, "Consignes initiales")
            active = 1
            if ".classic." in key:
                fields = {**fields, "camera_contract": CAMERA_CONTRACT}
                self._write_revision(directory, 2, fields, templates, "Contrat caméra explicite")
                active = 2
            _atomic_write(index, _json_bytes({"active": active, "last": active}))
        return directory, _read_json_object(index)

    def _write_revision(self, directory, revision, fields, templates, note):
        archive = directory / "revisions" / str(revision)
        archive.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for field, value in fields.items():
            payload = value.encode("utf-8")
            _atomic_write(archive / (field + ".txt"), payload)
            hashes[field] = hashlib.sha256(payload).hexdigest()
        _atomic_write(archive / "manifest.json", _json_bytes({
            "revision": revision, "created_at": datetime.now(timezone.utc).isoformat(),
            "note": note, "hashes": hashes, "templates": templates,
        }))

    def _read_revision(self, directory, revision):
        if type(revision) is not int or revision < 1:
            raise ValueError("Révision invalide.")
        archive = directory / "revisions" / str(revision)
        if not (archive / "manifest.json").is_file():
            raise KeyError("Révision introuvable.")
        manifest = _read_json_object(archive / "manifest.json")
        fields = {}
        for name, checksum in manifest["hashes"].items():
            path = (archive / (name + ".txt")).resolve()
            if not path.is_relative_to(archive.resolve()):
                raise ValueError("invalid instruction path")
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != checksum:
                raise ValueError("Une révision archivée a été modifiée sur disque. Restaurez le fichier puis utilisez l'éditeur pour créer une nouvelle révision.")
            fields[name] = payload.decode("utf-8")
        return {**manifest, "fields": fields}

    def get(self, cookbook_id, version, revision=None):
        with self._lock:
            directory, index = self._ensure(cookbook_id, version)
            package = self._read_revision(directory, index["active"] if revision is None else revision)
            return {**package, "cookbook_id": cookbook_id, "version": version, "active": index["active"]}

    def list(self):
        return [{"id": key, "version": version, "label": label} for key, version, label in EDITABLE_RECIPES]

    def history(self, key, version):
        with self._lock:
            directory, index = self._ensure(key, version)
            result = []
            for revision in range(index["last"], 0, -1):
                item = _read_json_object(directory / "revisions" / str(revision) / "manifest.json")
                result.append({name: item[name] for name in ("revision", "created_at", "note")})
            return result

    def save(self, key, version, *, base_revision, expected_active, fields, note=""):
        with self._lock:
            directory, index = self._ensure(key, version)
            if expected_active != index["active"]:
                raise ValueError("La version active a changé. Rechargez la recette avant d'enregistrer.")
            baseline = self._read_revision(directory, base_revision)
            if not isinstance(fields, dict) or set(fields) != set(baseline["fields"]):
                raise ValueError("Les composants de la recette doivent être conservés.")
            if any(not isinstance(text, str) for text in fields.values()):
                raise ValueError("Les consignes doivent être du texte.")
            if sum(len(text) for text in fields.values()) > 2_000_000:
                raise ValueError("Consignes trop volumineuses.")
            for field in ("plan.system", "writer.system", "revision.system"):
                if not fields[field].strip():
                    raise ValueError("Les consignes principales ne peuvent pas être vides.")
            if baseline["fields"]["render.system"] and not fields["render.system"].strip():
                raise ValueError("Les consignes d'ajustement après rendu ne peuvent pas être vides.")
            for field in baseline["templates"]:
                validate_template(fields[field], baseline["fields"][field])
            revision = index["last"] + 1
            self._write_revision(directory, revision, fields, baseline["templates"], note.strip()[:200] or "Modification utilisateur")
            _atomic_write(directory / "active.json", _json_bytes({"active": revision, "last": revision}))
            return self.get(key, version, revision)

    def activate(self, key, version, revision, expected_active):
        with self._lock:
            directory, index = self._ensure(key, version)
            if index["active"] != expected_active:
                raise ValueError("La version active a changé. Rechargez la recette.")
            self._read_revision(directory, revision)
            _atomic_write(directory / "active.json", _json_bytes({**index, "active": revision}))
            return self.get(key, version, revision)
