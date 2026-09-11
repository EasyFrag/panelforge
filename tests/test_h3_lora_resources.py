"""User-run metadata/API checks: temporary files, fake inventory and CivitAI."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from panelforge.features.lab.web import create_app
from panelforge.infrastructure.h3_lora_resources import H3LoraResourceCatalog


class H3LoraResourcesTest(unittest.TestCase):
    def test_on_demand_card_annotations_refresh_and_krea_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "minmax_nsfw/Motion_Repair.safetensors"
            inventory = Mock(return_value=((name,), None))
            remote = Mock()
            remote.inspect.return_value = {"display_name": "Motion Repair", "base_model": "MiniMax H3",
                "source_url": "https://civitai.com/models/123", "preview_urls": ["https://example.com/preview.png"]}
            krea = Path(tmp) / "krea2_resources.json"
            krea.write_text('{"schema_version":1,"preferences":{},"remote":{}}', encoding="utf8")
            original = krea.read_bytes()
            catalog = H3LoraResourceCatalog(workspace_root=tmp, inventory=inventory, civitai=remote)
            client = TestClient(create_app(object(), h3_lora_resources=catalog))
            inventory.assert_not_called()
            root = "/api/h3-render/video-loras/resources"
            response = client.get(root, params={"name": name})
            self.assertEqual(response.status_code, 200, response.text)
            resource = response.json()
            self.assertEqual(resource["comfy_name"], name)
            self.assertEqual(resource["filename"], "Motion_Repair.safetensors")
            remote.inspect.assert_not_called()
            self.assertEqual(client.get(root, params={"name": "../other.safetensors"}).status_code, 404)
            path = root + "/" + resource["resource_id"]
            response = client.post(path + "/preference", json={"notes": "First pass 0.6, second pass 0.2", "favorite": True})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["favorite"])
            response = client.post(path + "/refresh")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["base_model"], "MiniMax H3")
            remote.inspect.assert_called_once_with(filename="Motion_Repair.safetensors", sha256=None, known_version_id=None)
            reopened = H3LoraResourceCatalog(workspace_root=tmp, inventory=inventory, civitai=remote).get_by_name(name)
            self.assertTrue(reopened.favorite)
            self.assertEqual(reopened.notes, "First pass 0.6, second pass 0.2")
            self.assertEqual(reopened.display_name, "Motion Repair")
            self.assertEqual(krea.read_bytes(), original)
            self.assertTrue((Path(tmp) / "h3_lora_resources.json").exists())
            self.assertEqual(client.post(path + "/preference", json={"strength_min": .8, "strength_max": .2}).status_code, 422)

    def test_missing_catalog_and_offline_inventory_are_explicit(self):
        path = "/api/h3-render/video-loras/resources"
        self.assertEqual(TestClient(create_app(object())).get(path, params={"name": "missing"}).status_code, 503)
        with tempfile.TemporaryDirectory() as tmp:
            catalog = H3LoraResourceCatalog(workspace_root=tmp, inventory=lambda: ((), "Bucket indisponible"))
            response = TestClient(create_app(object(), h3_lora_resources=catalog)).get(path, params={"name": "missing"})
            self.assertEqual(response.status_code, 422)
            self.assertIn("Bucket indisponible", response.text)
