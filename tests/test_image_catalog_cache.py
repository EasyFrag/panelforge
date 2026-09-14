"""Offline regressions for cache-first Image Lab metadata (user-run only)."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from panelforge.features.lab.image_catalog import ImageLabCatalogs
from panelforge.infrastructure.background_snapshot import BackgroundSnapshot
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog


def settled(cache):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        value, status = cache.read()
        if not status["refreshing"]:
            return value, status
        sleep(.005)
    raise AssertionError("Background metadata refresh did not finish")


class BackgroundSnapshotTest(unittest.TestCase):
    def test_concurrent_reads_share_one_refresh_and_return_without_waiting(self):
        started, release = Event(), Event()
        def load():
            started.set()
            if not release.wait(2):
                raise TimeoutError()
            return {"models": ["a"]}
        loader = Mock(side_effect=load)
        cache = BackgroundSnapshot(loader)
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                replies = list(pool.map(lambda _: cache.read(), range(20)))
            self.assertTrue(started.wait(1))
            self.assertTrue(all(value is None and status["refreshing"] for value, status in replies))
            self.assertEqual(loader.call_count, 1)
        finally:
            release.set()
        self.assertEqual(settled(cache)[0], {"models": ["a"]})

    def test_restart_uses_persisted_catalog_and_failure_keeps_it_with_backoff(self):
        with TemporaryDirectory() as temporary:
            now = [1000.0]
            path = Path(temporary) / "cache.json"
            first = BackgroundSnapshot(lambda: {"models": ["a"]}, path=path, scope="bucket", clock=lambda: now[0])
            settled(first)
            offline = Mock(side_effect=OSError("offline"))
            cache = BackgroundSnapshot(offline, path=path, scope="bucket", clock=lambda: now[0])
            self.assertEqual(cache.read()[0], {"models": ["a"]})
            offline.assert_not_called()
            now[0] += 301
            cache.read()
            value, status = settled(cache)
            self.assertEqual(value, {"models": ["a"]})
            self.assertTrue(status["stale"])
            self.assertIn("Catalogue précédent conservé", status["error"])
            for _ in range(10):
                cache.read()
            self.assertEqual(offline.call_count, 1)
            cache.read(force=True)
            settled(cache)
            self.assertEqual(offline.call_count, 2)
            other = BackgroundSnapshot(lambda: {"models": ["b"]}, path=path, scope="other", clock=lambda: now[0])
            self.assertEqual(settled(other)[0], {"models": ["b"]})

    def test_readers_cannot_mutate_shared_snapshot(self):
        cache = BackgroundSnapshot(lambda: {"models": ["a"]})
        value, _ = settled(cache)
        value["models"].clear()
        self.assertEqual(cache.read()[0]["models"], ["a"])

    def test_explicit_edit_wins_over_older_inflight_scan(self):
        started, release = Event(), Event()
        current = {"name": "old"}
        def load():
            value = dict(current)
            if started.is_set():
                release.wait(2)
            return value
        cache = BackgroundSnapshot(load)
        settled(cache)
        started.set()
        cache.read(force=True)
        # Publish an annotation while the scan is still running.
        current["name"] = "edited"
        cache.patch(lambda _: dict(current))
        self.assertEqual(cache.read()[0]["name"], "edited")
        release.set()
        self.assertEqual(settled(cache)[0]["name"], "edited")


class ImageCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.models, self.loras = self.root / "models", self.root / "loras"
        self.models.mkdir()
        self.loras.mkdir()
        (self.models / "a.safetensors").write_bytes(b"fixture")
        (self.loras / "style.safetensors").write_bytes(b"fixture")
        self.comfy = SimpleNamespace(base_url="http://fixture", list_unet_models=Mock(return_value=("Krea2/a.safetensors",)),
                                     list_lora_models=Mock(return_value=("krea2/style.safetensors",)))
        self.catalog = self.make_catalog()

    def make_catalog(self):
        return LocalKrea2ResourceCatalog(models_root=self.models, loras_root=self.loras,
                                         workspace_root=self.root, comfy=self.comfy)

    def tearDown(self):
        if self.catalog._ui_cache:
            settled(self.catalog._ui_cache)
        self.temporary.cleanup()

    def inventory(self, force=False):
        self.catalog.ui_snapshot(force=force)
        settled(self.catalog._ui_cache)
        return self.catalog.ui_snapshot()[0]

    def test_discovery_never_reads_sidecars_and_i_reads_only_selected_card(self):
        with patch("panelforge.infrastructure.krea2_resources._read_rgthree_sidecar", return_value=({"name": "Style card"}, None)) as read:
            inventory = self.inventory()
            read.assert_not_called()
            self.assertNotIn("description", inventory["loras"][0])
            resource_id = inventory["loras"][0]["resource_id"]
            self.catalog.get_ui_detail(resource_id)
            self.catalog.get_ui_detail(resource_id)
            read.assert_called_once_with(self.loras / "style.safetensors")
            with self.assertRaises(KeyError):
                self.catalog.get_ui_detail("../outside")
        self.catalog.validate_selection("Krea2/a.safetensors", ("krea2/style.safetensors",))

    def test_annotations_are_immediate_and_survive_restart(self):
        inventory = self.inventory()
        resource_id = inventory["loras"][0]["resource_id"]
        resource = self.catalog.set_preference(resource_id, favorite=True)
        resource = self.catalog.set_annotations(resource_id, {"display_name": "My style", "notes": "Keep this"})
        self.catalog.publish_ui_resource(resource)
        restored = self.make_catalog()
        value, status = restored.ui_snapshot()
        self.assertFalse(status["refreshing"])
        self.assertEqual(value["loras"][0]["display_name"], "My style")
        self.assertTrue(value["loras"][0]["favorite"])

    def test_malformed_persisted_inventory_is_rebuilt(self):
        self.inventory()
        path = self.root / "krea2_inventory_cache.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["value"] = {"render_models": "broken"}
        path.write_text(json.dumps(saved), encoding="utf-8")
        self.catalog = self.make_catalog()
        self.assertTrue(self.inventory()["render_models"])

    def test_deleted_resource_is_removed_and_worker_refuses_old_selection(self):
        self.inventory()
        (self.loras / "style.safetensors").unlink()
        self.comfy.list_lora_models.return_value = ()
        self.assertEqual(self.inventory(force=True)["loras"], [])
        with self.assertRaisesRegex(ValueError, "LoRA indisponible"):
            self.catalog.validate_selection("Krea2/a.safetensors", ("krea2/style.safetensors",))

    def test_offline_refresh_retains_models_and_does_not_persist_empty_list(self):
        before = self.inventory()
        self.comfy.list_unet_models.side_effect = OSError("offline")
        self.catalog.ui_snapshot(force=True)
        settled(self.catalog._ui_cache)
        value, status = self.catalog.ui_snapshot()
        self.assertEqual(value, before)
        self.assertTrue(status["error"])
        saved = json.loads((self.root / "krea2_inventory_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["value"]["render_models"], before["render_models"])

    def test_shared_llm_discovery_never_delays_static_specs_or_resource_snapshot(self):
        self.inventory()
        release = Event()
        gateway = SimpleNamespace()
        def models():
            release.wait(2)
            return [{"id": "fixture"}]
        service = SimpleNamespace(gateway=gateway, list_models=Mock(side_effect=models))
        catalogs = ImageLabCatalogs()
        try:
            first = catalogs.read(self.catalog, service, lambda m: m)
            second = catalogs.read(self.catalog, service, lambda m: m)
            self.assertTrue(first["render_models"])
            self.assertTrue(second["catalog_status"]["llm"]["refreshing"])
        finally:
            release.set()
        settled(catalogs._llm[id(gateway)])
        self.assertEqual(service.list_models.call_count, 1)
