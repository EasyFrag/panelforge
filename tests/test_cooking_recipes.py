"""Culinary contracts and durable orchestration. All rendering ports are fakes."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest
from unittest.mock import Mock
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.cooking_recipe_prompting import image_instruction, planned_breakdown, krea_image_instruction
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
        self.received_batches, self.launches = [], []

    def presets(self):
        return [dict(id="wool", name="Wool", image_asset_id="asset-master")]

    def recent_images(self):
        return []

    def prepare_image(self, snapshot, shot, role, start, feedback, key):
        link = dict(engine="krea" if shot.get("image_engine") == "krea2" else "minimax", project_id=key, role=role)
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
        self.launches.append(identity)
        return identity

    def receive_clips(self, entries):
        self.received_batches.append(deepcopy(entries))
        ids, added = [], 0
        for entry in entries:
            identity = "factory-" + entry["source"]["attempt_id"]
            if identity not in self.items:
                added += 1
                self.items[identity] = dict(id=identity, status="preparation", config=deepcopy(entry["config"]),
                    steps={s:dict(status="pending", output={}) for s in ("plan", "prompt", "video", "dlss", "social")})
            ids.append(identity)
        return dict(ids=ids, added=added)

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

    def review(self, ids=None):
        self.p = self.service.review_images(self.p["id"], self.p["version"], ids or [s["id"] for s in self.p["shots"]])
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
        self.assertTrue(entry["config"]["dlss"]["enabled"])
        self.assertNotIn("chantier", entry["config"]["intention"])

    def test_cannot_start_another_clip_while_current_is_active(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        with self.assertRaises(RecipeConflict):
            self.generate("clip", "clips-again")

    def test_send_deposits_both_image_modes_without_starting_production(self):
        self.ready([shot(), shot("shot-2", "endpoints")])
        self.generate("image", "images-command"); self.drain()
        self.review()
        jobs_before = len(self.p["jobs"])
        result = self.service.send(self.p["id"], self.p["version"], ["shot-2", "shot-1"])
        self.p = result["project"]
        self.assertEqual(result["added"], 2)
        entries = self.production.received_batches[0]
        self.assertEqual([e["source"]["shot_id"] for e in entries], ["shot-1", "shot-2"])
        self.assertEqual([[r["role"] for r in e["config"]["references"]] for e in entries],
                         [["first_frame"], ["first_frame", "last_frame"]])
        self.assertTrue(all(i["status"] == "preparation" for i in self.production.items.values()))
        self.assertTrue(all(e["config"]["dlss"]["enabled"] for e in entries))
        self.assertEqual(len(self.p["jobs"]), jobs_before)
        self.service.tick()
        self.planner.propose.assert_not_called()
        self.assertFalse(self.production.launches)

    def test_send_reuses_version_even_after_factory_edit_or_completion(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.review()
        first = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        item = self.production.items[first["factory_ids"][0]]
        item["config"]["intention"] += " Adjusted in the factory."
        self.production.finish_clips(); self.load()
        second = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(second["factory_ids"], first["factory_ids"])
        self.assertEqual(second["added"], 0)
        self.assertEqual(len(self.production.received_batches), 1)
        self.assertIn("Adjusted in the factory.", item["config"]["intention"])

    def test_send_blocks_incomplete_endpoint_before_transmitting_other_ready_plans(self):
        self.ready([shot(), shot("shot-2", "endpoints")])
        self.generate("image", "images-command"); self.drain()
        self.review()
        stored = self.store.get(self.p["id"])
        stored["media"]["shot-2"]["images"][0]["end_asset_id"] = None
        self.store.save(stored); self.load()
        self.assertFalse(self.p["shots"][1]["image_ready"])
        with self.assertRaisesRegex(ValueError, "arrivée manquante"):
            self.service.send(self.p["id"], self.p["version"], ["shot-1", "shot-2"])
        self.assertFalse(self.production.received_batches)
        self.assertFalse(self.store.get(self.p["id"])["media"]["shot-1"]["clips"])

    def test_send_refuses_images_from_an_old_breakdown(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        changed = dict(shot(), opening="Un autre cadrage de départ.")
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], [changed])
        self.p = self.service.approve(self.p["id"], self.p["version"])
        with self.assertRaisesRegex(ValueError, "images de ce plan"):
            self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertFalse(self.production.received_batches)

    def test_send_ready_plan_while_another_image_is_pending(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-command")
        self.service.tick(); self.load()
        self.assertTrue(self.p["active"])
        self.review(["shot-1"])
        result = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(result["added"], 1)
        self.assertTrue(result["project"]["active"])
        self.assertFalse(self.production.launches)

    def test_send_recovers_lost_acknowledgement_with_same_reserved_entries(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.review()
        receive = self.production.receive_clips
        def interrupted(entries):
            receive(entries)
            raise RuntimeError("Acknowledgement lost")
        self.production.receive_clips = interrupted
        with self.assertRaisesRegex(RuntimeError, "lost"):
            self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.production.receive_clips = receive
        self.service = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        self.load()
        recovered = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(recovered["added"], 0)
        self.assertEqual(len(self.production.items), 1)
        self.assertEqual(len(recovered["project"]["media"]["shot-1"]["clips"]), 1)
        self.assertEqual(self.production.received_batches[0], self.production.received_batches[1])
        self.assertFalse(self.production.launches)

    def test_send_preserves_per_plan_corrections_and_versions(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-command"); self.drain()
        self.review()
        corrections = {"shot-1":"Geste plus lent.", "shot-2":"Vapeur plus légère."}
        first = self.service.send(self.p["id"], self.p["version"], ["shot-1", "shot-2"], feedbacks=corrections)
        entries = self.production.received_batches[0]
        self.assertIn(corrections["shot-1"], entries[0]["config"]["intention"])
        self.assertIn(corrections["shot-2"], entries[1]["config"]["intention"])
        self.p = first["project"]
        again = self.service.send(self.p["id"], self.p["version"], ["shot-1", "shot-2"], feedbacks=corrections)
        self.assertEqual(again["factory_ids"], first["factory_ids"])
        self.load()
        changed = self.service.send(self.p["id"], self.p["version"], ["shot-1"], "Autre geste.")
        self.assertNotEqual(changed["factory_ids"][0], first["factory_ids"][0])
        self.assertEqual(len(changed["project"]["media"]["shot-1"]["clips"]), 2)

    def test_send_reuses_historical_launched_clip_and_replaces_removed_card(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.review()
        self.generate("clip", "legacy-clip-command"); self.drain()
        old_id = next(iter(self.production.items))
        sent = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(sent["factory_ids"], [old_id])
        self.assertFalse(self.production.received_batches)
        self.production.items.clear(); self.load()
        sent = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertNotEqual(sent["factory_ids"], [old_id])
        self.assertEqual(sent["added"], 1)

    def test_real_delivery_adapter_never_calls_launch(self):
        from panelforge.application.cooking_recipe_production import CookingRecipeProduction
        factory = Mock()
        factory.receive.return_value = dict(ids=["factory-card"], added=1)
        adapter = CookingRecipeProduction(Mock(), Mock(), factory)
        entries = [dict(name="Ready dish", config={})]
        self.assertEqual(adapter.receive_clips(entries), dict(ids=["factory-card"], added=1))
        factory.receive.assert_called_once_with(entries)
        factory.launch.assert_not_called()

    def test_http_send_is_separate_from_legacy_automatic_launch(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.review()
        app = FastAPI(); app.include_router(cooking_recipes_router(self.service))
        url = "/api/recipes/projects/" + self.p["id"]
        with TestClient(app) as client:
            response = client.post(url + "/generate/clip", json=dict(version=self.p["version"], command="old-tab-command", ids=["shot-1"]))
            self.assertEqual(response.status_code, 409)
            response = client.post(url + "/send", json=dict(version=self.p["version"], ids=["shot-1"]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["added"], 1)
            self.assertFalse(self.production.launches)

    def test_scene_contract_carries_identity_action_and_both_states_to_each_frame(self):
        self.ready([dict(shot(mode="endpoints"), purpose="preparation",
            scene="Morceaux de bœuf en crochet dans une cocotte, carottes encore dans la main.",
            action="Ajouter les carottes au bœuf.", opening="Carottes au-dessus de la cocotte.",
            ending="Carottes dans la cocotte, parmi les morceaux de bœuf.")])
        snapshot = dict(self.p, settings=dict(self.p["settings"], intention="Bœuf bourguignon en laine"))
        for role, state_key in [("start", "opening"), ("end", "ending")]:
            with self.subTest(role=role):
                draft = image_instruction(snapshot, self.p["shots"][0], role, "Conserver la cocotte.")
                contract = json.loads(draft.split("SCENE CONTRACT:\n", 1)[1])
                self.assertEqual(contract["dish"], "Bœuf bourguignon en laine")
                for key in ("title", "scene", "action", "opening", "ending", "purpose"):
                    self.assertEqual(contract[key], self.p["shots"][0][key])
                self.assertEqual(contract["visible_state"], self.p["shots"][0][state_key])
                self.assertEqual(contract["frame_to_create"], role)
                self.assertEqual(contract["correction"], "Conserver la cocotte.")

    def test_planner_defaults_to_one_image_and_requires_reason_for_two(self):
        simple = shot(); simple.pop("mode")
        unjustified = shot("shot-2", "endpoints")
        justified = dict(shot("shot-3", "endpoints"), mode_reason="Départ : pâte entière ; arrivée : quatre bandes égales.")
        result = planned_breakdown(dict(title="Plat", shots=[simple, unjustified, justified]))
        self.assertEqual([s["mode"] for s in result["shots"]], ["animate", "animate", "endpoints"])
        self.assertEqual([s["purpose"] for s in result["shots"]], ["preparation", "preparation", "presentation"])
        # Manual choices in an existing breakdown remain valid without a model justification.
        self.assertEqual(policy.Shot.model_validate(unjustified).mode, "endpoints")

    def test_image_adapter_uses_full_scene_and_opening_as_arrival_composition(self):
        from panelforge.application.cooking_recipe_production import CookingRecipeProduction
        self.ready([dict(shot(mode="endpoints"), purpose="presentation", scene="Plat terminé servi dans son assiette.")])
        minimax = Mock()
        minimax.ensure_managed_image.return_value = dict(id="minimax-child", stages=[dict(id="stage-first")])
        adapter = CookingRecipeProduction(Mock(), minimax, Mock())
        for role in ("start", "end"):
            with self.subTest(role=role):
                adapter.prepare_image(self.p, self.p["shots"][0], role, "asset-opening", "Plat entier.", "frame-"+role)
                request = minimax.ensure_managed_image.call_args.kwargs
                self.assertEqual(request["source_asset_id"], "asset-opening" if role == "end" else None)
                self.assertEqual([r["asset_id"] for r in request["references"]], ["asset-master"])
                context = json.loads(request["draft"].split("SCENE CONTRACT:\n", 1)[1])
                self.assertEqual(context["scene"], "Plat terminé servi dans son assiette.")
                self.assertEqual(context["purpose"], "presentation")
                self.assertEqual(context["correction"], "Plat entier.")
        minimax.execute_message.assert_not_called()
        minimax.queue_attempt.assert_not_called()

    def test_technical_image_success_does_not_allow_unreviewed_factory_delivery(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        with self.assertRaisesRegex(ValueError, "revois et valide"):
            self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertFalse(self.production.received_batches)
        self.review()
        self.assertTrue(self.p["shots"][0]["image_reviewed"])
        self.p = self.service.review_images(self.p["id"], self.p["version"], ["shot-1"], False)
        self.load()
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        self.assertEqual(len(self.production.calls), 1)

    def test_review_changes_with_retained_image_and_cannot_validate_partial_batch(self):
        self.ready([shot(), shot("shot-2")])
        self.generate("image", "images-first", ["shot-1"]); self.drain()
        with self.assertRaisesRegex(ValueError, "complètes"):
            self.service.review_images(self.p["id"], self.p["version"], ["shot-1", "shot-2"])
        self.load()
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        old = policy.selected_image(self.p, self.p["shots"][0])["id"]
        self.review(["shot-1"])
        self.generate("image", "images-next", ["shot-1"]); self.drain()
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        self.review(["shot-1"])
        self.service.choose(self.p["id"], self.p["version"], "shot-1", "image", old)
        self.load()
        self.assertFalse(self.p["shots"][0]["image_reviewed"])

    def test_context_changes_invalidate_images_but_timing_and_mode_preserve_start(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain(); self.review()
        current = self.p["shots"][0]
        image = policy.selected_image(self.p, current)
        for key, value in [("title", "Autre geste"), ("action", "Retourner le poisson."),
                           ("scene", "Poisson dans une poêle."), ("purpose", "presentation")]:
            with self.subTest(key=key):
                self.assertFalse(policy.start_matches(self.p, dict(current, **{key:value}), image))
        for key, value in [("duration", 8), ("mode", "animate"), ("ending", "Une autre arrivée.")]:
            with self.subTest(key=key):
                self.assertTrue(policy.start_matches(self.p, dict(current, **{key:value}), image))
        different_dish = dict(self.p, settings=dict(self.p["settings"], intention="Latte"))
        self.assertFalse(policy.start_matches(different_dish, current, image))
        changed_end = dict(current, ending="Une autre arrivée.")
        self.assertFalse(policy.image_matches(self.p, changed_end, image))
        self.assertFalse(policy.images_reviewed(self.p, changed_end, image))

    def test_review_cannot_approve_an_unseen_image_completed_during_refresh(self):
        self.ready()
        self.generate("image", "first-images"); self.drain()
        self.generate("image", "newer-images")
        self.service.tick()  # Submitted result will be collected by the next refresh.
        version = self.store.get(self.p["id"])["version"]
        with self.assertRaisesRegex(RecipeConflict, "images ont changé"):
            self.service.review_images(self.p["id"], version, ["shot-1"])
        self.load()
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        self.assertEqual(len(self.p["media"]["shot-1"]["images"]), 2)

    def test_arrival_only_uses_retained_start_and_creates_one_new_frame(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain(); self.review()
        first = deepcopy(policy.selected_image(self.p, self.p["shots"][0]))
        count = len(self.production.calls)
        version = self.p["version"]
        self.service.enqueue(self.p["id"], version, "arrival-command", "image", ["shot-1"], "Sauce textile.", "end")
        # A lost response reuses the exact command, even with the original version.
        self.service.enqueue(self.p["id"], version, "arrival-command", "image", ["shot-1"], "Sauce textile.", "end")
        with self.assertRaises(RecipeConflict):
            self.service.enqueue(self.p["id"], version, "arrival-command", "image", ["shot-1"], "Sauce textile.")
        self.drain()
        current = policy.selected_image(self.p, self.p["shots"][0])
        self.assertEqual(len(self.production.calls), count + 1)
        self.assertEqual(self.production.calls[-1]["role"], "end")
        self.assertEqual(self.production.calls[-1]["start"], first["start_asset_id"])
        self.assertEqual(current["start_asset_id"], first["start_asset_id"])
        self.assertNotEqual(current["end_asset_id"], first["end_asset_id"])
        self.assertEqual(self.p["media"]["shot-1"]["images"][0]["outputs"], first["outputs"])
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        self.assertFalse(self.production.launches)

    def test_changing_only_arrival_keeps_departure_available_for_repair(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain()
        first = policy.selected_image(self.p, self.p["shots"][0])["start_asset_id"]
        self.ready([dict(shot(mode="endpoints"), ending="Poisson dans la même assiette avec un peu de sauce.")])
        self.load()
        self.assertFalse(self.p["shots"][0]["image_ready"])
        self.assertTrue(self.p["shots"][0]["start_ready"])
        self.service.enqueue(self.p["id"], self.p["version"], "repair-arrival", "image", ["shot-1"], image_part="end")
        self.drain()
        self.assertEqual(policy.selected_image(self.p, self.p["shots"][0])["start_asset_id"], first)
        self.assertTrue(self.p["shots"][0]["image_ready"])

    def test_arrival_only_validates_every_selected_plan_before_queueing(self):
        self.ready([shot(mode="endpoints"), shot("shot-2")])
        self.generate("image", "images-command"); self.drain()
        jobs = deepcopy(self.store.get(self.p["id"])["jobs"])
        with self.assertRaisesRegex(ValueError, "deux images"):
            self.service.enqueue(self.p["id"], self.p["version"], "bad-arrivals", "image", ["shot-1", "shot-2"], image_part="end")
        self.assertEqual(self.store.get(self.p["id"])["jobs"], jobs)
        self.ready([dict(shot(mode="endpoints"), action="Changer complètement de geste.")])
        with self.assertRaisesRegex(ValueError, "départ correspondant"):
            self.service.enqueue(self.p["id"], self.p["version"], "stale-arrival", "image", ["shot-1"], image_part="end")

    def test_failed_arrival_can_resume_after_restart_without_regenerating_start(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command")
        self.service.tick(); self.load()  # Start ready, arrival queued.
        first = self.p["shots"][0]["start_asset_id"]
        self.service.tick()
        key = next(reversed(self.production.results))
        self.production.results[key] = dict(status="failed", error="Arrival failed")
        self.load()
        self.assertFalse(self.p["shots"][0]["image_ready"])
        self.assertTrue(self.p["shots"][0]["start_ready"])
        self.service = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        self.load()
        self.service.enqueue(self.p["id"], self.p["version"], "retry-arrival", "image", ["shot-1"], image_part="end")
        self.service.tick()  # Arrival submitted; restarting must only collect the result.
        calls = len(self.production.calls)
        self.service = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        self.load()
        self.assertEqual(len(self.production.calls), calls)
        self.assertEqual([c["role"] for c in self.production.calls], ["start", "end", "end"])
        self.assertEqual(policy.selected_image(self.p, self.p["shots"][0])["start_asset_id"], first)
        self.assertTrue(self.p["shots"][0]["image_ready"])

    def test_switching_pair_to_animation_keeps_assets_and_sends_only_departure(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain(); self.review()
        image = deepcopy(policy.selected_image(self.p, self.p["shots"][0]))
        self.ready([shot()]); self.load()
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.assertFalse(self.p["shots"][0]["image_reviewed"])
        self.assertEqual(policy.selected_image(self.p, self.p["shots"][0])["end_asset_id"], image["end_asset_id"])
        self.review()
        self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        refs = self.production.received_batches[0][0]["config"]["references"]
        self.assertEqual([(r["asset_id"], r["role"]) for r in refs], [(image["start_asset_id"], "first_frame")])
        self.assertEqual(len(self.production.calls), 2)

    def test_abandoned_arrival_can_become_single_image_without_rendering(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command")
        self.service.tick(); self.load()
        first = self.p["shots"][0]["start_asset_id"]
        self.service.pause(self.p["id"], abandon=True); self.load()
        self.ready([shot()]); self.load()
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.assertEqual(policy.selected_image(self.p, self.p["shots"][0])["start_asset_id"], first)
        self.assertEqual(len(self.production.calls), 1)

    def test_legacy_images_keep_provenance_and_delivery_identity_without_migration(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "legacy-video"); self.drain()
        stored = self.store.get(self.p["id"])
        for record in stored["shots"]:
            for key in ("scene", "purpose", "mode_reason", "image_engine"):
                record.pop(key, None)
        for job in stored["jobs"]:
            for key in ("scene", "purpose", "mode_reason", "image_engine"):
                job["shot"].pop(key, None)
                for record in job["snapshot"]["shots"]:
                    record.pop(key, None)
            job.pop("start_context_key", None)
            if job["kind"] == "image":
                job["context_key"] = "old-image-context"
        image = stored["media"]["shot-1"]["images"][0]
        for key in ("start_context_key", "recipe_name", "shot_title", "image_policy_version", "image_engine"):
            image.pop(key, None)
        image["context_key"] = "old-image-context"
        self.store.save(stored)
        self.load()
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.assertFalse(self.p["media"]["shot-1"]["clips"][0]["stale"])
        self.assertEqual(self.p["media"]["shot-1"]["images"][0]["label"], "Poisson · Assaisonner")
        self.assertEqual(self.store.get(self.p["id"]), stored)
        self.p = self.service.approve(self.p["id"], self.p["version"])
        self.review()
        sent = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(sent["added"], 0)
        self.assertFalse(self.production.received_batches)
        self.assertEqual(len(self.production.calls), 2)

    def test_new_dish_archives_previous_images_and_clips_with_original_labels(self):
        self.ready()
        self.generate("image", "fish-images"); self.drain()
        self.generate("clip", "fish-video"); self.drain()
        self.production.finish_clips(); self.load()
        original = deepcopy(self.store.get(self.p["id"])["media"]["shot-1"])
        self.p = self.service.update(self.p["id"], self.p["version"], "Latte", dict(self.p["settings"], intention="Latte en laine"))
        self.p = self.service.set_master(self.p["id"], self.p["version"], "asset-latte")
        self.p = self.service.approve(self.p["id"], self.p["version"])
        self.generate("image", "latte-images"); self.drain()
        holder = self.p["media"]["shot-1"]
        self.assertEqual([i["stale"] for i in holder["images"]], [True, False])
        self.assertEqual(holder["images"][0]["label"], "Poisson · Assaisonner")
        self.assertTrue(holder["clips"][0]["stale"])
        stored = self.store.get(self.p["id"])["media"]["shot-1"]
        self.assertEqual(stored["images"][0], original["images"][0])
        for kind, old_id in [("image", original["selected_image"]), ("clip", original["selected_clip"])]:
            with self.assertRaisesRegex(ValueError, "ancienne version"):
                self.service.choose(self.p["id"], self.p["version"], "shot-1", kind, old_id)

    def test_http_review_and_arrival_only_are_explicit_separate_actions(self):
        self.ready([shot(mode="endpoints")])
        self.generate("image", "images-command"); self.drain()
        app = FastAPI(); app.include_router(cooking_recipes_router(self.service))
        url = "/api/recipes/projects/" + self.p["id"]
        with TestClient(app) as client:
            response = client.post(url + "/send", json=dict(version=self.p["version"], ids=["shot-1"]))
            self.assertEqual(response.status_code, 422)
            response = client.post(url + "/review-images", json=dict(version=self.p["version"], ids=["shot-1"]))
            self.assertEqual(response.status_code, 200)
            self.p = response.json()["project"]
            self.assertTrue(self.p["shots"][0]["image_reviewed"])
            response = client.post(url + "/generate/image", json=dict(version=self.p["version"], command="arrival-http", ids=["shot-1"], image_part="end"))
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["project"]["jobs"][-1]["phase"], "end")
        self.assertEqual(len(self.production.calls), 2)
        self.assertFalse(self.production.received_batches)

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

    def test_completed_factory_dlss_is_used_for_preview_and_export(self):
        self.ready()
        self.generate("image", "images-command"); self.drain(); self.review()
        self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        item = next(iter(self.production.items.values()))
        self.production.finish_clips(); self.load()
        raw = item["steps"]["video"]["output"]["asset_id"]
        self.assertEqual(self.p["media"]["shot-1"]["clips"][0]["asset_id"], raw)
        item["steps"]["dlss"].update(status="succeeded", output=dict(asset_id="asset-enhanced"))
        self.load()
        clip = self.p["media"]["shot-1"]["clips"][0]
        self.assertEqual(clip["asset_id"], "asset-enhanced")
        self.assertFalse(clip["stale"])
        exported = self.service.export_selection(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(exported["clips"][0]["asset_id"], "asset-enhanced")
        # A retry of the delivery neither overwrites factory choices nor duplicates it.
        item["config"]["dlss"]["enabled"] = False
        self.load()
        result = self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.assertEqual(result["added"], 0)
        self.assertFalse(item["config"]["dlss"]["enabled"])
        self.assertEqual(result["project"]["media"]["shot-1"]["clips"][0]["asset_id"], raw)
        self.assertFalse(self.production.launches)

    def test_pending_or_failed_dlss_preserves_available_raw_video(self):
        self.ready()
        self.generate("image", "images-command"); self.drain()
        self.generate("clip", "clips-command"); self.drain()
        self.production.finish_clips()
        item = next(iter(self.production.items.values()))
        raw = item["steps"]["video"]["output"]["asset_id"]
        for status in ("pending", "running", "failed"):
            item["steps"]["dlss"].update(status=status, output=dict(asset_id="asset-old-enhancement"))
            self.load()
            self.assertEqual(self.p["media"]["shot-1"]["clips"][0]["asset_id"], raw)

    def test_krea_validates_converts_selected_plans_and_replays_without_duplication(self):
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson",
            dict(self.p["settings"], style_preset_id="wool"), [shot(mode="endpoints"), shot("shot-2", "endpoints")])
        version = self.p["version"]
        self.p = self.service.enqueue(self.p["id"], version, "krea-batch", "image", ["shot-1"], image_engine="krea2")
        replay = self.service.enqueue(self.p["id"], version, "krea-batch", "image", ["shot-1"], image_engine="krea2")
        self.assertEqual(replay, self.p)
        with self.assertRaises(RecipeConflict):
            self.service.enqueue(self.p["id"], version, "krea-batch", "image", ["shot-1"], image_engine="h3")
        self.assertEqual([(s["image_engine"], s["mode"]) for s in self.p["shots"]], [("krea2", "animate"), ("h3", "endpoints")])
        self.assertEqual(self.p["breakdown_history"][-1]["shots"][0]["mode"], "endpoints")
        self.assertTrue(self.service.public(self.p)["approved_current"])
        self.drain()
        self.assertEqual(len(self.production.calls), 1)
        self.assertEqual(self.production.calls[0]["role"], "start")
        self.assertIsNone(self.p["media"]["shot-1"]["images"][0]["end_asset_id"])
        self.assertFalse(self.production.launches)
        self.assertFalse(self.production.received_batches)

    def test_krea_missing_or_removed_preset_leaves_recipe_and_queue_unchanged(self):
        self.ready([shot(mode="endpoints")])
        for preset in (None, "removed-preset"):
            self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", dict(self.p["settings"], style_preset_id=preset))
            before = self.store.get(self.p["id"])
            with self.assertRaisesRegex(ValueError, "preset"):
                self.service.enqueue(self.p["id"], self.p["version"], "missing-preset", "image", ["shot-1"], image_engine="krea2")
            self.assertEqual(self.store.get(self.p["id"]), before)
        self.assertFalse(self.production.calls)

    def test_krea_retry_and_restart_keep_engine_and_review_boundary(self):
        self.ready([dict(shot(mode="endpoints"), image_engine="krea2")])
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", dict(self.p["settings"], style_preset_id="wool"))
        self.p = self.service.approve(self.p["id"], self.p["version"])
        self.generate("image", "krea-first"); self.service.tick()
        self.service = CookingRecipeService(self.store, self.assets, self.images, self.planner, self.production)
        self.load()
        self.assertEqual(len(self.production.calls), 1)
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.generate("image", "krea-retry"); self.drain()
        self.assertEqual([c["shot"]["image_engine"] for c in self.production.calls], ["krea2", "krea2"])
        self.assertEqual(len(self.p["media"]["shot-1"]["images"]), 2)
        with self.assertRaisesRegex(ValueError, "revois"):
            self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        self.review()
        self.service.send(self.p["id"], self.p["version"], ["shot-1"])
        entry = self.production.received_batches[-1][0]
        self.assertEqual([r["role"] for r in entry["config"]["references"]], ["first_frame"])
        self.assertTrue(entry["config"]["dlss"]["enabled"])
        self.assertFalse(self.production.launches)

    def test_h3_button_keeps_endpoint_mode_without_krea_preset(self):
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], [shot(mode="endpoints")])
        self.p = self.service.enqueue(self.p["id"], self.p["version"], "h3-button", "image", ["shot-1"], image_engine="h3")
        self.drain()
        self.assertEqual([c["role"] for c in self.production.calls], ["start", "end"])
        self.assertTrue(self.p["shots"][0]["image_ready"])
        self.assertEqual(self.p["shots"][0]["mode"], "endpoints")

    def test_krea_fingerprint_is_distinct_and_h3_history_remains_reusable(self):
        self.ready(); self.generate("image", "h3-original"); self.drain(); self.review()
        original = deepcopy(self.p["media"]["shot-1"]["images"][0])
        original_key = policy.start_key(self.p, self.p["shots"][0])
        for preset in ("wool", "other"):
            updated = dict(self.p, settings=dict(self.p["settings"], style_preset_id=preset, model_id="other-model"))
            self.assertEqual(policy.start_key(updated, updated["shots"][0]), original_key)
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson",
            dict(self.p["settings"], style_preset_id="wool"), [dict(shot(), image_engine="krea2")])
        self.assertFalse(self.service.public(self.p)["shots"][0]["image_ready"])
        key = policy.start_key(self.p, self.p["shots"][0])
        self.assertNotEqual(key, original_key)
        changed = dict(self.p, settings=dict(self.p["settings"], style_preset_id="other"))
        self.assertNotEqual(key, policy.start_key(changed, changed["shots"][0]))
        changed = dict(self.p, settings=dict(self.p["settings"], edit_model_id="irrelevant-h3-model"))
        self.assertEqual(key, policy.start_key(changed, changed["shots"][0]))
        self.p = self.service.approve(self.p["id"], self.p["version"])
        self.generate("image", "krea-alternative"); self.drain()
        self.assertEqual(len(self.p["media"]["shot-1"]["images"]), 2)
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson", self.p["settings"], [shot()])
        self.p = self.service.choose(self.p["id"], self.p["version"], "shot-1", "image", original["id"])
        self.assertTrue(self.service.public(self.p)["shots"][0]["image_ready"])
        self.assertFalse(self.service.public(self.p)["shots"][0]["image_reviewed"])

    def test_breakdown_revision_preserves_user_engine_without_adding_a_finale(self):
        self.ready([dict(shot(), image_engine="krea2")])
        self.planner.propose.return_value = dict(title="Poisson révisé", shots=[shot(mode="endpoints"), shot("shot-2")])
        self.generate("plan", "revise-with-krea"); self.drain()
        self.assertEqual([(s["image_engine"], s["mode"]) for s in self.p["shots"]], [("krea2", "animate"), ("h3", "animate")])
        self.assertFalse(self.production.calls)

    def test_krea_adapter_passes_universe_breakdown_and_correction_to_creation(self):
        from panelforge.application.cooking_recipe_production import CookingRecipeProduction
        self.ready([dict(shot(), image_engine="krea2"), dict(shot("shot-2"), title="Servir le plat")])
        snapshot = dict(self.p, settings=dict(self.p["settings"], style_preset_id="wool"))
        krea, minimax = Mock(), Mock()
        krea.create_project.return_value = SimpleNamespace(project_id="krea-child")
        adapter = CookingRecipeProduction(krea, minimax, Mock())
        link = adapter.prepare_image(snapshot, snapshot["shots"][0], "start", None, "La salière doit être visible.", "job-start")
        request = krea.create_project.call_args.kwargs
        self.assertEqual(request["reference_asset_id"], "asset-master")
        self.assertEqual(request["style_preset_id"], "wool")
        self.assertEqual(request["model_id"], snapshot["settings"]["model_id"])
        self.assertEqual(request["assistance_recipe_version"], "6.0.0")
        self.assertFalse(request["local_inspiration_enabled"])
        self.assertEqual(request["managed_key"], "job-start")
        self.assertIn("La salière doit être visible.", request["intention"])
        self.assertIn("Servir le plat", request["intention"])
        self.assertIn("ONE NEW opening image", request["intention"])
        self.assertEqual(link["engine"], "krea")
        self.assertEqual(link["aspect_ratio"], snapshot["settings"]["aspect_ratio"])
        minimax.ensure_managed_image.assert_not_called()
        krea.stream_chat.assert_not_called()
        with self.assertRaisesRegex(ValueError, "départ"):
            adapter.prepare_image(snapshot, snapshot["shots"][0], "end", "asset-start", "", "job-end")

    def test_krea_submission_uses_flux_workflow_and_recovers_prepared_attempt(self):
        from panelforge.application.cooking_recipe_production import CookingRecipeProduction
        from panelforge.domain.krea2_batch import Krea2BatchSettings, Krea2AspectRatio, Krea2LoraSelection
        krea, minimax = Mock(), Mock()
        preset = SimpleNamespace(settings=Krea2BatchSettings("krea2-model.safetensors", Krea2AspectRatio.SQUARE, 1.0,
            (Krea2LoraSelection("wool.safetensors", 0.75),)))
        child = SimpleNamespace(project_id="child", current_prompt=None, intention="Opening scene", active_branch_id="main", style_preset=preset, attempts=[])
        krea.get.return_value = child
        def prompt(*args, **kwargs):
            child.current_prompt = "A new opening before cooking."
            return iter(())
        def prepare(*args, **kwargs):
            child.attempts.append(SimpleNamespace(attempt_id="attempt-1", status="created"))
            return child
        def queue(*args):
            child.attempts[0].status = "queued"
        krea.stream_chat.side_effect = prompt
        krea.prepare_attempt.side_effect = prepare
        krea.queue_attempt.side_effect = queue
        adapter = CookingRecipeProduction(krea, minimax, Mock())
        link = dict(engine="krea", project_id="child", aspect_ratio=self.p["settings"]["aspect_ratio"])
        saved = []
        adapter.submit_image(link, lambda value:saved.append(deepcopy(value)))
        settings = krea.prepare_attempt.call_args.kwargs["settings"]
        self.assertEqual(settings.workflow.recipe_id, "krea2-flux-klein")
        self.assertEqual(settings.workflow.version, "1.0.0")
        self.assertEqual(settings.megapixels, 2.1)
        self.assertEqual(settings.model_name, preset.settings.model_name)
        self.assertEqual(settings.loras, preset.settings.loras)
        self.assertEqual(settings.aspect_ratio.value, link["aspect_ratio"])
        self.assertEqual(settings.sampling.preset_id, "finish_4")
        self.assertFalse(krea.prepare_attempt.call_args.kwargs["enqueue"])
        self.assertEqual(saved[0]["attempt_id"], "attempt-1")
        # Reconstruct the link from before its checkpoint: reuse the managed child.
        recovered = dict(engine="krea", project_id="child", aspect_ratio=link["aspect_ratio"])
        adapter.submit_image(recovered, lambda value:None)
        self.assertEqual(recovered["attempt_id"], "attempt-1")
        krea.prepare_attempt.assert_called_once()
        krea.stream_chat.assert_called_once()
        krea.queue_attempt.assert_called_once_with("child", "attempt-1")
        minimax.queue_attempt.assert_not_called()

    def test_krea_prompt_failure_does_not_queue_a_render(self):
        from panelforge.application.cooking_recipe_production import CookingRecipeProduction
        krea = Mock()
        krea.get.return_value = SimpleNamespace(project_id="child", current_prompt=None, intention="Opening", active_branch_id="main")
        krea.stream_chat.return_value = iter(())
        with self.assertRaisesRegex(ValueError, "prompt exploitable"):
            CookingRecipeProduction(krea, Mock(), Mock()).submit_image(
                dict(engine="krea", project_id="child", aspect_ratio=self.p["settings"]["aspect_ratio"]), lambda value:None)
        krea.prepare_attempt.assert_not_called()
        krea.queue_attempt.assert_not_called()

    def test_krea_prompt_shortens_only_overview_to_fit_existing_chat_contract(self):
        self.ready([dict(shot("shot-"+str(n)), action="Un long geste culinaire. "*100) for n in range(30)])
        target = self.p["shots"][0]
        prompt = krea_image_instruction(self.p, target, "Préserver la cocotte.")
        self.assertLessEqual(len(prompt), 12000)
        contract = json.loads(prompt.split("SCENE CONTRACT:\n", 1)[1].split("\nSELECTED SHOT:", 1)[0])
        self.assertEqual(contract["action"], target["action"])
        self.assertEqual(contract["correction"], "Préserver la cocotte.")
        overview = json.loads(prompt.split("ORDERED BREAKDOWN (context only):\n", 1)[1])
        self.assertEqual([s["id"] for s in overview], [s["id"] for s in self.p["shots"]])
        with self.assertRaisesRegex(ValueError, "limite KREA2"):
            krea_image_instruction(self.p, target, "Correction très longue. "*1000)

    def test_http_engine_choice_is_explicit_and_replayable(self):
        self.p = self.service.update(self.p["id"], self.p["version"], "Poisson",
            dict(self.p["settings"], style_preset_id="wool"), [shot(mode="endpoints")])
        app = FastAPI(); app.include_router(cooking_recipes_router(self.service))
        url = "/api/recipes/projects/" + self.p["id"] + "/generate/image"
        body = dict(version=self.p["version"], command="http-krea", ids=["shot-1"], image_engine="krea2")
        with TestClient(app) as client:
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["project"]["shots"][0]["mode"], "animate")
            self.assertEqual(client.post(url, json=body).json(), response.json())
            self.assertEqual(client.post(url, json=dict(body, image_engine="unknown")).status_code, 422)
            self.assertEqual(client.post(url, json=dict(body, image_part="end")).status_code, 422)
        self.assertFalse(self.production.calls)

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
