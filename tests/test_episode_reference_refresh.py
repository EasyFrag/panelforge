"""User-run regressions: no LLM, ComfyUI or live workspace access."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application.episodes import EpisodeConflict
from panelforge.application.h3_render import H3RenderService
from panelforge.domain.episodes import only_reference_images_changed, scene_inputs
from panelforge.domain.h3_render import H3RenderProject, H3RenderInputMode
from panelforge.infrastructure.storage.h3_render_projects import LocalH3RenderProjectStore
from tests import test_episodes as fixtures


class EpisodeImageRefreshTest(unittest.TestCase):
    create = fixtures.EpisodeTest.create
    ready = fixtures.EpisodeTest.ready

    def setUp(self):
        fixtures.EpisodeTest.setUp(self)
        create_render = self.service.render.get_or_create_from_session
        def create(session_id):
            project = create_render(session_id)
            project.reference_asset_ids = tuple(r.asset_id for r in self.prompt.sessions[session_id].references)
            return project
        def fork(project_id, *, expected_asset_ids, asset_ids):
            source = self.rendered[project_id]
            self.assertEqual(source.reference_asset_ids, expected_asset_ids)
            project = NS(project_id=f"refreshed-{len(self.rendered)}", current_prompt=source.current_prompt,
                         reference_asset_ids=tuple(asset_ids), attempts=[])
            project.attempt = lambda identity: next(a for a in project.attempts if a.attempt_id == identity)
            self.rendered[project.project_id] = project
            return project
        self.service.render.get_or_create_from_session = create
        self.service.render.fork_reference_images = Mock(side_effect=fork)
        value = self.ready()
        self.identity = value["episode_id"]
        self.value = self.service.prepare_scene(self.identity, "scene-1", 1, "original-prompt")
        self.prior = deepcopy(self.value["scenes"][0]["preparations"][-1])
        self.setup = deepcopy(self.value["scenes"][0]["effective_render_setup"])
        self.initial_calls = deepcopy(self.composition.calls)

    def change_image(self):
        value = self.service.get(self.identity)
        ref = value["references"][0]
        return self.service.import_image(self.identity, ref["id"], ref["revision"], b"new", "image/png", "new.png")

    def render(self, preparation=None, prompt="My exact render prompt"):
        preparation = preparation or self.prior
        return self.service.prepare_scene_render(self.identity, "scene-1",
            preparation_id=preparation["id"], render_project_id=preparation["render_project_id"],
            prompt=prompt, setup=self.setup)

    def test_manual_image_refresh_keeps_prompt_settings_history_and_original_session(self):
        old_project, _ = self.render(prompt="First prompt")
        old_attempts = deepcopy(old_project.attempts)
        value = self.change_image()
        self.assertEqual(value["scenes"][0]["image_refresh_names"], [value["references"][0]["name"]])
        self.setup["settings"].update(duration_seconds=8, seed=42)
        self.setup["seed_locked"] = True
        project, preparation_id = self.render()
        saved = self.service.get(self.identity)
        scene = saved["scenes"][0]
        latest = scene["preparations"][-1]
        self.assertFalse(scene["stale"])
        self.assertEqual(scene["image_refresh_names"], [])
        self.assertEqual(scene["preparations"][0], self.prior)
        self.assertEqual(latest["id"], preparation_id)
        self.assertEqual(latest["source_preparation_id"], self.prior["id"])
        self.assertEqual(latest["session_id"], self.prior["session_id"])
        self.assertEqual(latest["inputs"], scene_inputs(saved, scene))
        self.assertEqual(project.reference_asset_ids[0], value["references"][0]["image_asset_id"])
        attempt = project.attempts[-1]
        self.assertEqual(attempt.prompt, "My exact render prompt")
        self.assertEqual(attempt.settings.duration_seconds, 8)
        self.assertEqual(attempt.settings.seed, 42)
        self.assertEqual(attempt.recipe_id, self.setup["recipe"]["id"])
        self.assertEqual(attempt.bunny.coarse_steps, self.setup["bunny"]["coarse_steps"])
        self.assertEqual([a.prompt for a in old_project.attempts], [a.prompt for a in old_attempts])
        self.assertNotEqual(old_project.reference_asset_ids, project.reference_asset_ids)
        self.assertEqual(self.composition.calls, self.initial_calls)
        self.assertEqual(len(self.prompt.sessions), 1)
        # Repeated launch on the new version does not fork again.
        self.render(latest)
        self.assertEqual(self.service.render.fork_reference_images.call_count, 1)

    def test_unchanged_references_use_the_existing_render_project(self):
        project, preparation_id = self.render()
        self.assertEqual(project.project_id, self.prior["render_project_id"])
        self.assertEqual(preparation_id, self.prior["id"])
        self.service.render.fork_reference_images.assert_not_called()
        self.assertEqual(self.composition.calls, self.initial_calls)

    def test_narrative_edit_and_missing_image_never_reuse_the_old_prompt(self):
        self.change_image()
        value = self.service.store.get(self.identity)
        value["scenes"][0]["intention"] += " Une autre action."
        self.service.store.save(value)
        self.assertEqual(self.service.get(self.identity)["scenes"][0]["image_refresh_names"], [])
        with self.assertRaisesRegex(EpisodeConflict, "nouveau prompt"):
            self.render()
        value["scenes"][0]["intention"] = self.value["scenes"][0]["intention"]
        value["references"][0]["image_asset_id"] = None
        self.service.store.save(value)
        with self.assertRaisesRegex(ValueError, "Choisissez une image"):
            self.render()
        self.service.render.fork_reference_images.assert_not_called()
        self.assertEqual(self.composition.calls, self.initial_calls)

    def test_historical_or_foreign_render_binding_is_rejected(self):
        with self.assertRaises(EpisodeConflict):
            self.render({**self.prior, "render_project_id": "unrelated-project"})
        self.change_image()
        self.render()
        with self.assertRaisesRegex(EpisodeConflict, "dernière préparation"):
            self.render()
        self.assertEqual(self.service.render.fork_reference_images.call_count, 1)

    def test_video_chain_reuses_prompt_with_new_images_without_any_llm_call(self):
        value = self.change_image()
        result = self.service.start_video_chain(self.identity,
            expected_video_revision=value["video_revision"], request_id="chain-refreshed-images",
            scene_ids=["scene-1"], inter_video_cooldown_seconds=0)
        self.assertEqual(result["video_chain"]["status"], "completed")
        item = result["video_chain"]["items"][0]
        project = self.rendered[item["render_project_id"]]
        self.assertEqual(project.reference_asset_ids[0], value["references"][0]["image_asset_id"])
        self.assertNotEqual(project.project_id, self.prior["render_project_id"])
        self.assertEqual(self.composition.calls, self.initial_calls)

    def test_image_changed_after_prompt_selection_is_checked_before_chained_attempt(self):
        value = self.change_image()
        raw = self.service.store.get(self.identity)
        raw["video_chain"] = dict(chain_id="queued-chain", status="running", pause_requested=False,
            items=[dict(scene_id="scene-1", index=0, title="Scene", attempt_id=None)])
        self.service.store.save(raw)
        # The chain still holds the previous preparation; launch must recheck it.
        with self.assertRaisesRegex(EpisodeConflict, "chaîne vidéo"):
            self.render()
        result = self.service._start_chain_video(self.identity, "queued-chain", "scene-1",
            self.prior, self.setup, cooldown_after=False)
        self.assertEqual(self.rendered[result[0]].reference_asset_ids[0], value["references"][0]["image_asset_id"])
        self.assertEqual(self.composition.calls, self.initial_calls)

    def test_only_image_changes_are_eligible_not_roles_order_labels_or_story_contract(self):
        before = self.prior["inputs"]
        after = deepcopy(before)
        after["references"][0]["asset_id"] = "replacement-image"
        self.assertTrue(only_reference_images_changed(before, after))
        for field, replacement in [("role", "style_reference"), ("reference_id", "another-person"),
                                   ("name", "Someone else"), ("kind", "location")]:
            with self.subTest(field=field):
                changed = deepcopy(after)
                changed["references"][0][field] = replacement
                self.assertFalse(only_reference_images_changed(before, changed))
        reordered = deepcopy(after)
        reordered["references"].reverse()
        self.assertFalse(only_reference_images_changed(before, reordered))
        for field in ("source_text", "plan_model_id", "writer_model_id", "shot_count", "visual_continuity"):
            with self.subTest(field=field):
                self.assertFalse(only_reference_images_changed(before, {**after, field: "changed"}))


class RenderImageForkTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalH3RenderProjectStore(self.temp.name)
        self.source = self.store.create(H3RenderProject(project_id="old-render", source_session_id="session-1",
            source_prompt_revision_id="prompt-1", model_id="model", input_mode=H3RenderInputMode.REF2VA,
            current_prompt="An unchanged prompt", reference_asset_ids=("old-image", "decor"),
            reference_labels=("Pêchette", "Couloir"), planned_cut_times_ms=(3500,)))
        self.service = object.__new__(H3RenderService)
        self.service._lock = RLock()
        self.service.projects = self.store
        self.service._project_id_factory = lambda: "new-render"
        self.service.assets = NS(get=lambda key: NS(media_type="video/mp4" if key == "video" else "image/png"))

    def test_fork_roundtrip_keeps_source_and_original_revision_lookup_unchanged(self):
        original_path = Path(self.temp.name) / "h3_render_projects/old-render/project.json"
        original_bytes = original_path.read_bytes()
        result = self.service.fork_reference_images("old-render", expected_asset_ids=("old-image", "decor"),
            asset_ids=("new-image", "decor"))
        self.assertEqual(self.store.get(result.project_id), result)
        self.assertEqual(result.reference_parent_project_id, self.source.project_id)
        self.assertEqual(result.current_prompt, self.source.current_prompt)
        self.assertEqual(result.planned_cut_times_ms, (3500,))
        self.assertEqual(result.reference_asset_ids, ("new-image", "decor"))
        self.assertEqual(result.source_prompt_revision_id, "prompt-1")
        self.assertEqual(result.attempts, ())
        self.assertEqual(self.store.find_source_revision("session-1", "prompt-1"), self.source)
        self.assertEqual(original_path.read_bytes(), original_bytes)

    def test_wrong_mapping_or_non_image_is_rejected_before_creating_a_fork(self):
        for expected, assets in [(("wrong", "decor"), ("new", "decor")),
                                 (("old-image", "decor"), ("new",)),
                                 (("old-image", "decor"), ("video", "decor"))]:
            with self.subTest(expected=expected, assets=assets), self.assertRaises(ValueError):
                self.service.fork_reference_images("old-render", expected_asset_ids=expected, asset_ids=assets)
        self.assertEqual(len(self.store.list()), 1)

    def test_historical_schema_remains_readable_without_parent_metadata(self):
        path = Path(self.temp.name) / "h3_render_projects/old-render/project.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["schema_version"] = 15
        value.pop("reference_parent_project_id")
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(self.store.get("old-render"), self.source)
