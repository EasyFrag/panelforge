import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panelforge.infrastructure.storage.cooking_recipes import LocalCookingRecipeStore
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from panelforge.infrastructure.storage import project_index
from panelforge.application.cooking_recipes import CookingRecipeService
from panelforge.domain.cooking_recipes import new_project


STORES = ((LocalCookingRecipeStore, "recipe-"), (LocalStoryV2Store, "storyv2-"))


def project(prefix, digit="a"):
    return {"schema_version": 1, "id": prefix + digit * 32, "updated_at": "2026-10-22T12:00:00Z",
            "jobs": [{"status": "succeeded", "link": {"project_id": "child-existing"}, "asset_id": "asset-existing"}]}


class ProjectIndexTests(unittest.TestCase):
    def test_recovered_recipe_keeps_child_ids_and_outputs_without_resubmitting(self):
        with TemporaryDirectory() as directory:
            store = LocalCookingRecipeStore(directory)
            value = new_project("recovery-command", "Recette", {})
            value["jobs"] = [
                {"kind": "image", "status": "working", "link": {"project_id": "image-already-submitted"}},
                {"kind": "clip", "status": "working", "link": {"factory_id": "video-already-submitted"}},
                {"kind": "image", "status": "succeeded", "asset_id": "asset-already-produced"},
            ]
            write = project_index._atomic_write

            def interrupt(path, content):
                if path.name == "index.json":
                    raise OSError("interrupted index update")
                write(path, content)

            with patch.object(project_index, "_atomic_write", side_effect=interrupt):
                with self.assertRaises(OSError):
                    store.save(value)
            production, assets, images, planner = Mock(), Mock(), Mock(), Mock()
            restarted = LocalCookingRecipeStore(directory)
            CookingRecipeService(restarted, assets, images, planner, production)
            recovered = restarted.get(value["id"])
            self.assertTrue(recovered["paused"])
            self.assertEqual([job["status"] for job in recovered["jobs"]], ["waiting", "queued", "succeeded"])
            self.assertEqual(recovered["jobs"][0]["link"], value["jobs"][0]["link"])
            self.assertEqual(recovered["jobs"][1]["link"], value["jobs"][1]["link"])
            self.assertEqual(recovered["jobs"][2], value["jobs"][2])
            for dependency in (production, assets, images, planner):
                self.assertEqual(dependency.mock_calls, [])

    def test_interrupted_creation_recovers_only_durable_projects_once(self):
        for store_type, prefix in STORES:
            for phase in ("pending-index.json", "project", "index.json"):
                for after in (False, True):
                    with self.subTest(store=prefix, phase=phase, after=after), TemporaryDirectory() as directory:
                        store = store_type(directory)
                        value = project(prefix)
                        target = value["id"] + ".json" if phase == "project" else phase
                        original_write = project_index._atomic_write

                        def interrupt(path, content):
                            if path.name == target:
                                if after:
                                    original_write(path, content)
                                raise OSError("simulated interruption")
                            original_write(path, content)

                        with patch.object(project_index, "_atomic_write", side_effect=interrupt):
                            with self.assertRaises(OSError):
                                store.save(value)
                        durable = (store.root / (value["id"] + ".json")).exists()
                        restarted = store_type(directory)
                        expected = [value] if durable else []
                        self.assertEqual(restarted.list(), expected)
                        self.assertEqual(restarted.list(), expected)
                        self.assertFalse((store.root / "pending-index.json").exists())
                        restarted.save(value)
                        self.assertEqual(restarted.list(), [value])
                        self.assertEqual(json.loads((store.root / "index.json").read_text()), [value["id"]])

    def test_failed_repair_keeps_pending_and_later_save_recovers_before_new_intent(self):
        for store_type, prefix in STORES:
            with self.subTest(store=prefix), TemporaryDirectory() as directory:
                store = store_type(directory)
                value, next_value = project(prefix), project(prefix, "b")
                write = project_index._atomic_write

                def fail_index(path, content):
                    if path.name == "index.json":
                        raise OSError("index unavailable")
                    write(path, content)

                with patch.object(project_index, "_atomic_write", side_effect=fail_index):
                    with self.assertRaises(OSError):
                        store.save(value)
                    with self.assertRaises(OSError):
                        store_type(directory).list()
                self.assertTrue((store.root / "pending-index.json").exists())
                store_type(directory).save(next_value)
                self.assertEqual({p["id"] for p in store.list()}, {value["id"], next_value["id"]})
                self.assertEqual(store.get(value["id"]), value)

    def test_invalid_pending_is_retained_and_never_used_as_a_path(self):
        for store_type, prefix in STORES:
            for intent in ({"schema_version": 1, "id": "../escape"},
                           {"schema_version": 99, "id": prefix + "a" * 32}):
                with self.subTest(store=prefix, intent=intent), TemporaryDirectory() as directory:
                    store = store_type(directory)
                    store.root.mkdir()
                    pending = store.root / "pending-index.json"
                    pending.write_text(json.dumps(intent), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        store.list()
                    self.assertTrue(pending.exists())
                    self.assertFalse((store.root / "index.json").exists())

    def test_corrupt_index_is_not_replaced_and_existing_project_is_not_rewritten(self):
        for store_type, prefix in STORES:
            with self.subTest(store=prefix), TemporaryDirectory() as directory:
                store = store_type(directory)
                value = project(prefix)
                store.save(value)
                index = store.root / "index.json"
                index.write_text('{"wrong": true}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    store.save({**value, "jobs": []})
                self.assertEqual(store.get(value["id"]), value)
                self.assertEqual(index.read_text(), '{"wrong": true}')
