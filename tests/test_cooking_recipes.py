"""Culinary contracts and durable orchestration. All rendering ports are fakes."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.cooking_recipes import CookingRecipeService, RecipeConflict
from panelforge.domain import cooking_recipes as policy
from panelforge.domain.video_factory import validate_shape, readiness
from panelforge.features.lab.cooking_recipes_web import cooking_recipes_router
from panelforge.infrastructure.storage.cooking_recipes import LocalCookingRecipeStore
from panelforge.infrastructure.cooking_recipe_exports import CookingRecipeExports


def shot(identity="shot-1", mode="animate"):
    return policy.Shot(id=identity, title="Assaisonner", action="Les doigts saupoudrent les épices.",
        framing="Gros plan stable", opening="Poisson sur une planche, doigts prêts à saupoudrer.",
        ending="Poisson assaisonné.", duration=6, mode=mode).model_dump()


class FakeProduction:
    def __init__(self):
        self.calls, self.results, self.items = [], {}, {}

    def presets(self):
        return [dict(id="wool", name="Wool", image_asset_id="asset-master")]

    def recent_images(self):
        return []

    def prepare_image(self, snapshot, shot, role, start, feedback, key):
        link = dict(engine="minimax", project_id=key, role=role)
        self.calls.append(dict(snapshot=deepcopy(snapshot), shot=shot, role=role, start=start, feedback=feedback))
        self.results[key] = dict(status="succeeded", asset_id="asset-" + key, prompt="Prepared frame")
        return link

    def submit_image(self, link, checkpoint):
        checkpoint(link)
        return link

    def prepare_master(self, snapshot, key, feedback):
        self.results[key] = dict(status="succeeded", asset_id="asset-" + key, prompt="Dish")
        return dict(engine="krea", project_id=key)

    def submit_master(self, link, snapshot, checkpoint):
        checkpoint(link)
        return link

    def image_result(self, link):
        return self.results[link["project_id"]]

    def video_items(self, ids):
        return {i:deepcopy(self.items[i]) for i in ids if i in self.items}

    def submit_clip(self, entry, checkpoint):
        identity = "factory-" + entry["source"]["attempt_id"]
        self.items.setdefault(identity, dict(id=identity, status="queued", config=deepcopy(entry["config"]),
            steps={s:dict(status="pending", output={}) for s in ("plan", "prompt", "video", "dlss", "social")}))
        checkpoint(dict(factory_id=identity))
        return identity

    def finish_clips(self):
        for item in self.items.values():
            item["status"] = "succeeded"
            item["steps"]["video"].update(status="succeeded", output=dict(asset_id="asset-" + item["id"]))


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = LocalCookingRecipeStore(self.tmp.name)
        self.assets = Mock()
        self.assets.get.return_value = SimpleNamespace(media_type="image/png")
        self.assets.read_bytes.return_value = b"image"
        self.images = Mock()
        self.images.dimensions.return_value = (72, 128)
        self.planner = Mock()
        self.planner.propose.return_value = dict(title="Poisson", shots=[shot()])
        self.production = FakeProduction()
        self.service = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        self.p = self.service.create("create-command", "Poisson", {}, "asset-master")

    def load(self):
        self.p = self.service.get(self.p["id"])
        return self.p

    def ready(self, shots=None):
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], shots or [shot()])
        self.p = self.service.approve(self.p["id"], self.p["version"])

    def generate(self, kind, command, ids=None):
        self.load()
        self.p = self.service.enqueue(self.p["id"], self.p["version"], command, kind,
            ids or [s["id"] for s in self.p["shots"]] if kind in {"image", "clip"} else [])

    def drain(self, count=6):
        for _ in range(count):
            self.service.tick()
        self.load()

    def test_creation_has_no_model_or_render_side_effects(self):
        self.assertEqual(self.service.create("create-command", "Poisson", {}, "asset-master")["id"], self.p["id"])
        self.assertFalse(self.p["jobs"])
        self.planner.propose.assert_not_called()
        self.assertFalse(self.production.calls)

    def test_generation_requires_approved_current_breakdown(self):
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], [shot()])
        with self.assertRaisesRegex(ValueError, "Accepte"):
            self.generate("image", "images-command")

    def test_creation_key_cannot_be_reused_for_a_different_project(self):
        with self.assertRaises(RecipeConflict):
            self.service.create("create-command", "Autre plat", {}, "asset-master")

    def test_external_factory_reference_change_is_not_silently_exported(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        item = next(iter(self.production.items.values()))
        item["config"]["references"][0]["asset_id"] = "asset-other"
        self.production.finish_clips(); self.load()
        self.assertTrue(self.p["media"]["shot-1"]["clips"][0]["stale"])
        with self.assertRaisesRegex(ValueError, "ancienne version"):
            self.service.export_selection(self.p["id"], self.p["version"], ["shot-1"])

    def test_image_batch_stops_before_any_video(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-command")
        self.drain()
        self.assertEqual(len(self.production.calls), 2)
        self.assertFalse(self.production.items)
        self.assertTrue(all(s["image_ready"] for s in self.p["shots"]))
        self.assertTrue(all(c["snapshot"]["master_asset_id"] == "asset-master" and c["start"] is None for c in self.production.calls))

    def test_endpoints_use_generated_start_and_keep_master(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command")
        self.drain()
        first, last = self.production.calls
        selected = policy.selected_image(self.p, self.p["shots"][0])
        self.assertEqual(last["start"], selected["start_asset_id"])
        self.assertEqual(last["snapshot"]["master_asset_id"], "asset-master")
        self.assertTrue(selected["end_asset_id"])

    def test_command_replay_does_not_add_jobs_even_with_old_version(self):
        self.ready()
        version = self.p["version"]
        self.generate("image", "images-command")
        p = self.service.enqueue(self.p["id"], version, "images-command", "image", ["shot-1"])
        self.assertEqual(len(p["jobs"]), 1)
        with self.assertRaises(RecipeConflict):
            self.service.enqueue(p["id"], version, "images-command", "image", ["shot-1"], "other")

    def test_reading_projects_does_not_start_work(self):
        self.ready()
        self.generate("image", "images-command")
        for _ in range(3):
            self.load()
        self.assertFalse(self.production.calls)

    def test_pause_abandon_never_submits_remaining_images(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-command")
        self.service.pause(self.p["id"])
        self.service.tick()
        self.assertFalse(self.production.calls)
        self.service.pause(self.p["id"], abandon=True)
        self.load()
        self.assertFalse(self.p["active"])
        self.assertTrue(all(j["status"] == "cancelled" for j in self.p["jobs"]))

    def test_restart_inspects_submitted_image_without_resubmission(self):
        self.ready()
        self.generate("image", "images-command")
        self.service.tick()
        before = len(self.production.calls)
        restarted = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        p = restarted.get(self.p["id"])
        self.assertTrue(p["paused"])
        self.assertTrue(p["shots"][0]["image_ready"])
        self.assertEqual(len(self.production.calls), before)

    def test_restart_before_submission_does_not_wait_forever_or_auto_submit(self):
        settings = dict(self.p["settings"], style_preset_id="wool", intention="Poisson en laine")
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", settings)
        self.generate("master", "master-command")
        stored = self.store.get(self.p["id"])
        job = stored["jobs"][-1]
        job.update(status="working", link=dict(engine="krea", project_id="prepared-only"))
        self.store.save(stored)
        self.production.results["prepared-only"] = dict(status="created")
        restarted = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        p = restarted.get(self.p["id"])
        self.assertEqual(p["jobs"][-1]["status"], "failed")
        self.assertFalse(p["active"])
        self.assertFalse(self.production.calls)

    def test_managed_images_keep_story_identity_and_isolate_recipes(self):
        from uuid import NAMESPACE_URL, uuid5
        from panelforge.application.minimax_edit import MinimaxEditService
        from panelforge.infrastructure.storage.minimax_edits import LocalMinimaxEditStore
        service = MinimaxEditService(gateway=Mock(), workflow=Mock(), comfy=Mock(), assets=self.assets,
            projects=LocalMinimaxEditStore(self.tmp.name), images=self.images)
        args = dict(key="same-key", name="Frame", source_asset_id=None, model_id="model",
            draft="One culinary frame", settings={"resolution":"2"},
            references=[dict(asset_id="asset-master", name="Dish", role="Texture and ingredients")])
        story = service.ensure_story_image(**args)
        recipe = service.ensure_managed_image(owner="cooking-recipes", **args)
        self.assertEqual(story["id"], "minimax-" + uuid5(NAMESPACE_URL, "panelforge/story-image/same-key").hex)
        self.assertNotEqual(story["id"], recipe["id"])
        self.assertEqual(recipe["id"], service.ensure_managed_image(owner="cooking-recipes", **args)["id"])
        self.assertEqual(recipe["managed_by"], "cooking-recipes")
        self.assertEqual(recipe["stages"][0]["mode"], "composition")
        self.assertFalse(recipe["stages"][0]["attempts"])
        service.gateway.stream.assert_not_called()

    def test_managed_krea_creation_is_reused_without_touching_normal_creation(self):
        from panelforge.application.krea2_assisted import Krea2AssistedService
        from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore
        store = LocalKrea2AssistedProjectStore(self.tmp.name)
        service = SimpleNamespace(projects=store, _inventory_warnings=lambda:(),
                                  _project_id_factory=lambda:"assisted-ordinary")
        args = dict(name="Dish", intention="Crochet fish", model_id="model",
                    assistance_recipe_version="1.0.0", local_inspiration_enabled=False)
        first = Krea2AssistedService.create_project(service, managed_key="recipe-request", **args)
        same = Krea2AssistedService.create_project(service, managed_key="recipe-request", **args)
        normal = Krea2AssistedService.create_project(service, **args)
        self.assertEqual(first.project_id, same.project_id)
        self.assertEqual(normal.project_id, "assisted-ordinary")
        self.assertNotEqual(normal.project_id, first.project_id)
        self.assertEqual(len(store.list()), 2)

    def test_stale_revision_cannot_replace_user_work(self):
        self.ready()
        with self.assertRaises(RecipeConflict):
            self.service.update(self.p["id"], 1, "Other", self.p["settings"], [shot()])

    def test_new_attempt_preserves_old_image_and_stales_clip(self):
        self.ready()
        self.generate("image", "images-1"); self.drain()
        self.generate("clip", "clips-1"); self.drain()
        self.production.finish_clips(); self.load()
        old = policy.selected_image(self.p, self.p["shots"][0])["id"]
        self.assertFalse(self.p["media"]["shot-1"]["clips"][0]["stale"])
        self.generate("image", "images-2"); self.drain()
        self.assertEqual(len(self.p["media"]["shot-1"]["images"]), 2)
        self.assertTrue(self.p["media"]["shot-1"]["clips"][0]["stale"])
        self.service.choose(self.p["id"], self.p["version"], "shot-1", "image", old)
        self.load()
        self.assertFalse(self.p["media"]["shot-1"]["clips"][0]["stale"])

    def test_factory_contract_is_silent_culinary_single_shot(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain()
        image = policy.selected_image(self.p, self.p["shots"][0])
        entry = policy.factory_entry(self.p, self.p["shots"][0], image, "attempt")
        validate_shape(entry["config"])
        self.assertFalse(readiness(entry["config"]))
        self.assertEqual([r["role"] for r in entry["config"]["references"]], ["first_frame", "last_frame"])
        self.assertEqual(entry["config"]["creative_axes"]["dialogue"], 0)
        self.assertFalse(entry["config"]["render"]["music_enabled"])
        self.assertNotIn("chantier", entry["config"]["intention"])

    def test_cannot_start_another_clip_while_current_is_active(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        with self.assertRaises(RecipeConflict):
            self.generate("clip", "clips-again")

    def test_removed_factory_item_allows_explicit_new_attempt(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        self.production.items.clear()
        self.load()
        self.assertEqual(self.p["media"]["shot-1"]["clips"][0]["status"], "failed")
        self.generate("clip", "clips-again"); self.drain()
        self.assertEqual(len(self.p["media"]["shot-1"]["clips"]), 2)

    def test_export_uses_order_and_exact_selected_versions(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        self.production.finish_clips(); self.load()
        selected = self.service.export_selection(self.p["id"], self.p["version"], ["shot-2", "shot-1"])
        self.assertEqual([c["shot_id"] for c in selected["clips"]], ["shot-1", "shot-2"])
        reordered = [shot("shot-2"), shot()]
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], reordered)
        self.load()
        selected = self.service.export_selection(self.p["id"], self.p["version"], ["shot-1", "shot-2"])
        self.assertEqual([c["shot_id"] for c in selected["clips"]], ["shot-2", "shot-1"])

    def test_partial_export_does_not_silently_skip_missing_clip(self):
        self.ready()
        with self.assertRaisesRegex(ValueError, "clip terminé"):
            self.service.export_selection(self.p["id"], self.p["version"], ["shot-1"])

    def test_breakdown_contract_rejects_missing_endpoint_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            policy.Shot.model_validate(dict(shot(mode="endpoints"), ending=""))
        with self.assertRaises(ValueError):
            policy.Breakdown(title="Recipe", shots=[shot(), shot()])

    def test_http_create_and_disabled_backend(self):
        app = FastAPI(); app.include_router(cooking_recipes_router(self.service))
        with TestClient(app) as client:
            response = client.post("/api/recipes/projects", json=dict(command="api-create-command", name="Plat"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["project"]["shots"], [])
            self.assertEqual(client.post("/api/recipes/projects", json=dict(command="short")).status_code, 422)
        app = FastAPI(); app.include_router(cooking_recipes_router(None))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/recipes/spec").status_code, 503)

    def test_storage_rejects_traversal_and_preserves_index(self):
        with self.assertRaises(ValueError):
            self.store.get("../other")
        self.assertEqual(len(self.store.list()), 1)
        self.assertEqual(LocalCookingRecipeStore(self.tmp.name).get(self.p["id"])["name"], "Poisson")

    def test_zip_contains_numbered_clips_and_manifest(self):
        video = Path(self.tmp.name) / "clip.mp4"; video.write_bytes(b"fake-video")
        assets = Mock(); assets.get.return_value = SimpleNamespace(media_type="video/mp4")
        assets.verified_path.return_value = video
        selection = dict(project_id="recipe-test", name="Poisson", clips=[dict(index=2,title="../../Dresser",asset_id="asset-video",duration=6)])
        path, filename = CookingRecipeExports(assets).create(selection)
        self.addCleanup(lambda:path.unlink(missing_ok=True))
        with ZipFile(path) as archive:
            self.assertEqual(archive.namelist(), ["02_Dresser.mp4", "ordre_des_clips.json"])
            self.assertEqual(archive.read("02_Dresser.mp4"), b"fake-video")


if __name__ == "__main__":
    unittest.main()
