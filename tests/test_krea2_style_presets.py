"""Offline preset scenarios. No real model, image renderer or network client."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted import Krea2AssistedTurn, Krea2AssistedTurnMode as Mode, Krea2AssistedTurnRole as Role
from panelforge.domain.krea2_batch import Krea2LoraSelection, Krea2PromptLanguage
from panelforge.domain.krea2_style_presets import Krea2StylePresetCategory
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore
from panelforge.infrastructure.storage.krea2_style_presets import LocalKrea2StylePresetStore
from tests.test_krea2_assisted import Gateway, PNG, PROMPT
from tests.test_krea2_assisted_branches import fixture, SETTINGS


class StylePresetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.assets = LocalAssetStore(root)
        self.image = self.assets.create(PNG, media_type="image/png")
        self.projects = LocalKrea2AssistedProjectStore(root)
        project = fixture()
        project = project.replace_attempt(replace(project.attempt("image-1"), output_asset_id=self.image.asset_id))
        self.projects.create(project)
        self.catalog = LocalKrea2StylePresetStore(root)
        self.gateway = Gateway(())
        self.service = Krea2AssistedService(
            gateway=self.gateway, comfy=None, workflow=None, assets=self.assets, projects=self.projects,
            presets=self.catalog, recipes=SimpleNamespace(current=lambda: ()),
            resources=SimpleNamespace(list_models=lambda: (), list_loras=lambda: (), inventory_warnings=lambda: ()),
        )
        self.a = self.service.save_style_preset(project.project_id, "image-1", "Style A")

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, preset, **overrides):
        values = dict(expected_branch_id="main", current_prompt=PROMPT + " USER_EDIT", settings=SETTINGS, seed=0)
        values.update(overrides)
        return self.service.apply_style_preset("branch-test", preset.preset_id if preset else None, **values)

    def test_save_uses_successful_attempt_and_update_does_not_mutate_pinned_projects(self):
        self.assertEqual(self.a.prompt, self.projects.get("branch-test").attempt("image-1").prompt)
        self.assertNotEqual(self.a.prompt, self.projects.get("branch-test").current_prompt)
        pinned = self.apply(self.a)
        updated = self.service.save_style_preset("branch-test", "image-1", "Style A", preset_id=self.a.preset_id, expected_revision=1)
        self.assertEqual(updated.revision, 2)
        reopened = LocalKrea2StylePresetStore(self.temp.name).get(self.a.preset_id)
        self.assertEqual(reopened, updated)
        self.assertEqual(self.projects.get("branch-test").style_preset, pinned.style_preset)
        self.assertEqual(pinned.style_preset.revision, 1)
        self.assertEqual(len(json.loads(self.catalog.path.read_text(encoding="utf-8"))["revisions"]), 2)
        with self.assertRaisesRegex(ValueError, "chang"):
            self.service.save_style_preset("branch-test", "image-1", "Style A", preset_id=self.a.preset_id, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "nom existe"):
            self.service.save_style_preset("branch-test", "image-1", "style a")
        self.assertEqual(self.gateway.requests, [])

    def test_selecting_b_replaces_pending_a_without_changing_prompt_ratio_seed_or_history(self):
        b = self.catalog.save(replace(self.a, preset_id="style-b", name="Style B", prompt="B_EXAMPLE_ONLY",
                                      settings=replace(SETTINGS, model_name="different-model", loras=(Krea2LoraSelection("b.safetensors", .7),))))
        first = self.apply(self.a)
        second = self.apply(b)
        self.assertEqual(second.current_prompt, first.current_prompt)
        self.assertEqual(second.turns, first.turns)
        self.assertEqual(second.render_settings.aspect_ratio, SETTINGS.aspect_ratio)
        self.assertEqual(second.render_seed, 0)
        self.assertEqual(second.render_settings.model_name, "different-model")
        self.assertEqual(second.render_settings.loras, b.settings.loras)
        user = Krea2AssistedTurn("pending", Mode.CREATION, Role.USER, "A different subject")
        request = self.service._completion_request(replace(second, turns=(*second.turns, user)), user.content, Mode.CREATION, False)
        self.assertIn("B_EXAMPLE_ONLY", request.user_prompt)
        self.assertNotIn('"name": "Style A"', request.user_prompt)
        self.assertEqual([i.label for i in request.images], ["GENERATED RESULT", "STYLE PRESET EXAMPLE"])
        self.assertEqual(len(second.branches), 1)
        self.assertEqual(self.gateway.requests, [])

    def test_pending_example_survives_failure_and_is_consumed_only_on_accepted_exchange(self):
        project = self.apply(self.a)
        response = json.dumps({"message": "Proposition", "questions": [], "prompt": PROMPT, "recommendations": []})
        self.gateway.responses = iter(("invalid JSON", response, response))
        first = list(self.service.stream_chat(project.project_id, "Continue"))[-1]
        self.assertTrue(first.error)
        self.assertTrue(self.projects.get(project.project_id).preset_pending)
        second = list(self.service.stream_chat(project.project_id, "Continue"))[-1]
        self.assertIsNone(second.error)
        self.assertFalse(second.project.preset_pending)
        self.assertEqual(second.project.turns[-2].style_preset, self.a)
        list(self.service.stream_chat(project.project_id, "Change the background"))
        self.assertIn("STYLE PRESET EXAMPLE", [i.label for i in self.gateway.requests[1].images])
        self.assertNotIn("STYLE PRESET EXAMPLE", [i.label for i in self.gateway.requests[2].images])
        cleared = self.apply(None)
        self.assertIsNone(cleared.style_preset)
        self.assertFalse(cleared.preset_pending)

    def test_creation_and_branch_restore_pin_the_example_without_automatic_calls(self):
        created = self.service.create_project(name="New subject", intention="A shoe", model_id="local", style_preset_id=self.a.preset_id)
        self.assertTrue(created.preset_pending)
        self.assertIsNone(created.current_prompt)
        self.assertIsNone(created.render_seed)
        self.assertEqual(created.render_settings.model_name, self.a.settings.model_name)
        main = self.apply(self.a)
        fork = self.service.change_branch("branch-test", expected_branch_id="main", attempt_id="image-1")
        self.assertIsNone(fork.style_preset)  # This image predates the preset selection.
        restored = self.service.change_branch("branch-test", expected_branch_id=fork.active_branch_id, branch_id="main")
        self.assertEqual(restored.style_preset, main.style_preset)
        self.assertTrue(restored.preset_pending)
        self.assertEqual(self.projects.get(restored.project_id).style_preset, self.a)
        with self.assertRaises(ValueError):
            self.apply(self.a, expected_branch_id="stale")
        self.assertEqual(self.gateway.requests, [])

    def test_category_updates_and_catalog_deletion_leave_project_copy_intact(self):
        pinned = self.apply(self.a)
        updated = self.service.update_style_preset(
            self.a.preset_id,
            name="Style A rangé",
            category=Krea2StylePresetCategory.NSFW,
            expected_revision=1,
        )
        self.assertEqual(updated.revision, 2)
        self.assertEqual(updated.category, Krea2StylePresetCategory.NSFW)
        self.assertEqual(self.catalog.list(), (updated,))
        deleted = self.service.delete_style_preset(updated.preset_id, expected_revision=2)
        self.assertEqual(deleted, updated)
        self.assertEqual(self.catalog.list(), ())
        with self.assertRaises(KeyError):
            self.catalog.get(updated.preset_id)
        self.assertEqual(self.projects.get("branch-test").style_preset, pinned.style_preset)
        self.assertEqual(self.projects.get("branch-test").style_preset.revision, 1)
        stored = json.loads(self.catalog.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["schema_version"], 2)
        self.assertEqual(stored["deleted"], [updated.preset_id])

    def test_preset_language_is_the_creation_default_but_can_be_overridden(self):
        chinese = self.catalog.save(replace(
            self.a,
            preset_id="style-chinese",
            name="Style chinois",
            prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
        ))
        inherited = self.service.create_project(
            name="Chinese", intention="Portrait", model_id="local", style_preset_id=chinese.preset_id,
        )
        overridden = self.service.create_project(
            name="English", intention="Portrait", model_id="local", style_preset_id=chinese.preset_id,
            prompt_language=Krea2PromptLanguage.ENGLISH,
        )
        self.assertEqual(inherited.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
        self.assertEqual(overridden.prompt_language, Krea2PromptLanguage.ENGLISH)

    def test_schema_one_catalogue_defaults_existing_presets_to_work(self):
        value = json.loads(self.catalog.path.read_text(encoding="utf-8"))
        value["schema_version"] = 1
        value.pop("deleted", None)
        for preset in value["revisions"]:
            preset.pop("category", None)
        self.catalog.path.write_text(json.dumps(value), encoding="utf-8")
        loaded = LocalKrea2StylePresetStore(self.temp.name).get(self.a.preset_id)
        self.assertEqual(loaded.category, Krea2StylePresetCategory.WORK)
