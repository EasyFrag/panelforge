"""Offline regressions prepared for user execution; no real model or render calls."""

from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore
from tests.test_krea2_assisted_branches import fixture


class AssistedPerformanceTest(unittest.TestCase):
    def test_admission_snapshot_does_not_read_disk_or_network_and_refresh_discovers_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models, loras = root / "models", root / "loras"
            models.mkdir(); loras.mkdir()
            comfy = SimpleNamespace(
                list_unet_models=Mock(return_value=("Krea2/a.safetensors",)),
                list_lora_models=Mock(return_value=("krea2/style.safetensors",)),
            )
            catalog = LocalKrea2ResourceCatalog(models_root=models, loras_root=loras, workspace_root=root, comfy=comfy)
            self.assertFalse(catalog.selection_in_last_inventory("Krea2/a.safetensors", ()))
            catalog.list_models(); catalog.list_loras()
            comfy.list_unet_models.reset_mock(); comfy.list_lora_models.reset_mock()
            for _ in range(5):
                self.assertTrue(catalog.selection_in_last_inventory("Krea2/a.safetensors", ("krea2/style.safetensors",)))
                self.assertFalse(catalog.selection_in_last_inventory("Krea2/new.safetensors", ()))
                self.assertFalse(catalog.selection_in_last_inventory("Krea2/a.safetensors", ("krea2/unknown.safetensors",)))
            comfy.list_unet_models.assert_not_called(); comfy.list_lora_models.assert_not_called()
            comfy.list_unet_models.return_value = ("Krea2/new.safetensors",)
            catalog.list_models()
            self.assertTrue(catalog.selection_in_last_inventory("Krea2/new.safetensors", ()))
            self.assertFalse(catalog.selection_in_last_inventory("Krea2/a.safetensors", ()))

    def test_limited_history_does_not_deserialize_archived_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = LocalKrea2AssistedProjectStore(root)
            recent = store.create(fixture())
            archived = store.create(replace(recent, project_id="archived"))
            archived_path = root / "krea2_assisted" / archived.project_id / "project.json"
            archived_path.write_text("invalid old JSON", encoding="utf-8")
            os.utime(archived_path, (1, 1))
            self.assertEqual(store.list(1), [store.get(recent.project_id)])
            self.assertEqual(store.list(0), [])
            # Explicit loading still reports corrupt history, never silently drops it.
            with self.assertRaises(json.JSONDecodeError):
                store.get(archived.project_id)


if __name__ == "__main__":
    unittest.main()
