"""Atomic local catalogue retaining all immutable preset revisions."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

from panelforge.domain.krea2_style_presets import Krea2StylePreset, Krea2StylePresetCategory
from panelforge.domain.krea2_batch import Krea2BatchSettings, Krea2LoraSelection, Krea2PromptLanguage
from panelforge.domain.krea2_lab import Krea2AspectRatio


def preset_dict(preset):
    if preset is None:
        return None
    value = asdict(preset)
    value["source_seed"] = str(preset.source_seed)
    value["prompt_language"] = preset.prompt_language.value
    value["category"] = preset.category.value
    return value


def load_preset(value):
    if value is None:
        return None
    settings = value["settings"]
    return Krea2StylePreset(
        preset_id=value["preset_id"], revision=value["revision"], name=value["name"],
        prompt=value["prompt"], image_asset_id=value["image_asset_id"],
        source_project_id=value["source_project_id"], source_attempt_id=value["source_attempt_id"],
        source_seed=int(value["source_seed"]), prompt_language=Krea2PromptLanguage(value["prompt_language"]),
        category=Krea2StylePresetCategory(value.get("category", "work")),
        settings=Krea2BatchSettings(
            model_name=settings["model_name"], aspect_ratio=Krea2AspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"], loras=tuple(Krea2LoraSelection(**lora) for lora in settings["loras"]),
        ),
    )


class LocalKrea2StylePresetStore:
    def __init__(self, workspace_root):
        self.path = Path(workspace_root).resolve() / "krea2_style_presets.json"
        self._lock = RLock()

    def _read(self):
        if not self.path.exists():
            return [], set()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema_version") not in {1, 2}:
            raise ValueError("unsupported style preset catalogue")
        deleted = value.get("deleted", []) if value.get("schema_version") >= 2 else []
        if not isinstance(deleted, list) or any(not isinstance(item, str) for item in deleted):
            raise ValueError("invalid deleted style preset list")
        return [load_preset(item) for item in value["revisions"]], set(deleted)

    def _write(self, revisions, deleted):
        content = json.dumps({
            "schema_version": 2,
            "revisions": [preset_dict(preset) for preset in revisions],
            "deleted": sorted(deleted),
        }, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".krea2-presets-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def list(self):
        with self._lock:
            revisions, deleted = self._read()
            latest = {}
            for preset in revisions:
                latest[preset.preset_id] = preset
            return tuple(sorted((preset for preset_id, preset in latest.items() if preset_id not in deleted),
                                key=lambda p: (list(Krea2StylePresetCategory).index(p.category), p.name.casefold())))

    def get(self, preset_id):
        return next((p for p in self.list() if p.preset_id == preset_id), None) or self._missing(preset_id)

    @staticmethod
    def _missing(preset_id):
        raise KeyError(preset_id)

    def save(self, preset):
        with self._lock:
            revisions, deleted = self._read()
            if preset.preset_id in deleted:
                raise ValueError("Ce preset a été supprimé du catalogue.")
            current = {p.preset_id: p for p in revisions}
            previous = current.get(preset.preset_id)
            if preset.revision != (previous.revision + 1 if previous else 1):
                raise ValueError("Le preset a changé. Recharge la liste avant de le mettre à jour.")
            if any(preset_id not in deleted and p.preset_id != preset.preset_id
                   and p.name.casefold() == preset.name.casefold()
                   for preset_id, p in current.items()):
                raise ValueError("Ce nom existe déjà. Choisis Mettre à jour ou un autre nom.")
            self._write([*revisions, preset], deleted)
            return preset

    def delete(self, preset_id, expected_revision):
        with self._lock:
            revisions, deleted = self._read()
            latest = {preset.preset_id: preset for preset in revisions}
            current = latest.get(preset_id)
            if current is None or preset_id in deleted:
                raise KeyError(preset_id)
            if current.revision != expected_revision:
                raise ValueError("Le preset a changé. Recharge la liste avant de le supprimer.")
            deleted.add(preset_id)
            self._write(revisions, deleted)
            return current
