"""Atomic batch records in their own namespace, independent from legacy Batch."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import tempfile

from panelforge.domain.creation_batch import CreationBatch, CreationBatchConfig, CreationBatchItem, CreationBatchRender
from panelforge.domain.krea2_art_direction import Krea2ArtDirection
from panelforge.domain.krea2_batch import Krea2PromptLanguage
from .krea2_assisted import _settings, _load_settings
from .krea2_style_presets import preset_dict, load_preset


def _config(value):
    return CreationBatchConfig(
        model_id=value["model_id"], recipe_version=value["recipe_version"],
        language=Krea2PromptLanguage(value["language"]), local_inspiration=value["local_inspiration"],
        preset=load_preset(value["preset"]), settings=_load_settings(value["settings"]),
        art_direction=Krea2ArtDirection(**value["art_direction"]) if value.get("art_direction") else None,
    )


def _config_dict(config):
    value = asdict(config)
    value.update(preset=preset_dict(config.preset), settings=_settings(config.settings), language=config.language.value)
    return value


def _item(value):
    value = dict(value)
    value["config"] = _config(value["config"]) if value.get("config") else None
    value["renders"] = tuple(CreationBatchRender(**{**r, "config": _config(r["config"])})
                             for r in value.get("renders", ()))
    return CreationBatchItem(**value)


class LocalCreationBatchStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "creation_batches"

    def _path(self, batch_id):
        if not re.fullmatch(r"creation-batch-[0-9a-f]{32}", batch_id):
            raise ValueError("Identifiant de batch invalide.")
        path = self.root / (batch_id + ".json")
        path.resolve().relative_to(self.root)
        if path.is_symlink():
            raise ValueError("Un batch ne peut pas être un lien symbolique.")
        return path

    def get(self, batch_id):
        value = json.loads(self._path(batch_id).read_text(encoding="utf-8"))
        if value.get("schema_version") not in {1, 2} or value.get("batch_id") != batch_id:
            raise ValueError("Fichier de batch invalide.")
        return CreationBatch(
            batch_id=value["batch_id"], request_digest=value["request_digest"], name=value["name"],
            created_at=value["created_at"], revision=value["revision"],
            config=_config(value["config"]), items=tuple(_item(item) for item in value["items"]),
        )

    def list(self):
        # Enumerated once on service startup, never from a polling HTTP endpoint.
        return tuple(self.get(path.stem) for path in sorted(self.root.glob("creation-batch-*.json")))

    def save(self, batch):
        value = asdict(batch)
        value["schema_version"] = 2
        value["config"] = _config_dict(batch.config)
        for item, encoded in zip(batch.items, value["items"]):
            encoded["config"] = _config_dict(item.config) if item.config else None
            for render, render_value in zip(item.renders, encoded["renders"]):
                render_value["config"] = _config_dict(render.config)
        content = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
        path = self._path(batch.batch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".creation-batch-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return batch
