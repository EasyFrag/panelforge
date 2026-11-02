"""User-run v8 lifecycle regressions; memory stores and fake adapters only."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import PRESET_ID, OBJECTS, is_variety, make_variety_selection
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V8, LOCALIZED_THANKS_VARIETY_V8
from panelforge.domain.video_factory import (
    LITTLE_MEN_ADAPTIVE_INTENT, LITTLE_MEN_EXPERIMENTAL_INTENT, LITTLE_MEN_VARIETY_INTENT,
    LITTLE_MEN_STANDARD_INTENT, LITTLE_MEN_STANDARD_VARIETY_INTENT,
    apply_preset, invalidate, new_item, preparation_text,
)
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_languages import config_for


def standard_config(variety=False):
    source = config_for("Pays : Japon")
    return apply_preset(source, PRESET_ID if variety else "little_men_experimental", source)


def selected_item(variety=False):
    config = standard_config(variety)
    item = new_item("Standard H3", config, {}, "standard-variety" if variety else "standard")
    selection = make_selection(config, item["id"])
    if variety:
        selection["variety"] = make_variety_selection(item["id"], [])
    item["runtime"]["thanks_selection"] = selection
    return item


class StandardLifecycleTest(unittest.TestCase):
    def service(self, config):
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        item = service.receive([dict(name="Standard H3", config=config,
            source={"kind": "image", "id": "source"})])["state"]["items"][0]
        service.launch([item["id"]], {item["id"]: item["revision"]})
        return service, store, adapter, item["id"]

    def test_v8_reserves_only_experimental_assortment_before_call_and_keeps_it_on_retry(self):
        for variety in (False, True):
            with self.subTest(variety=variety):
                service, store, adapter, identity = self.service(standard_config(variety))
                observed = []

                def interrupted(snapshot, stage, checkpoint, cancelled, progress):
                    selection = snapshot["runtime"]["thanks_selection"]
                    self.assertEqual(selection["version"], 8)
                    self.assertEqual("variety" in selection, variety)
                    if variety:
                        self.assertEqual(len(selection["variety"]["candidates"]), 12)
                    self.assertEqual(selection, store.value["items"][0]["runtime"]["thanks_selection"])
                    observed.append(deepcopy(selection))
                    checkpoint(session_id="interrupted-session")
                    raise RuntimeError("Fake interrupted Plan")

                adapter.run = Mock(side_effect=interrupted)
                service._execute("local_gpu", identity, "plan")
                service = VideoFactoryService(store=store, adapter=adapter)
                item = service.snapshot()["items"][0]
                service.action("retry", [identity], {identity: item["revision"]})
                with patch("panelforge.application.video_factory.make_variety_selection",
                           side_effect=AssertionError("Retry must preserve its frozen input")):
                    service._execute("local_gpu", identity, "plan")
                self.assertEqual(len(observed), 2)
                self.assertEqual(observed[0], observed[1])

    def test_unprepared_historical_versions_do_not_silently_select_v8(self):
        for version, variety, intention in (
            (5, False, LITTLE_MEN_EXPERIMENTAL_INTENT),
            (6, True, LITTLE_MEN_VARIETY_INTENT),
            (7, True, LITTLE_MEN_ADAPTIVE_INTENT),
        ):
            with self.subTest(version=version):
                config = standard_config(variety)
                config.update(little_men_direction_version=version, intention=intention)
                service, store, _adapter, identity = self.service(config)
                service._execute("local_gpu", identity, "plan")
                saved = store.value["items"][0]
                self.assertEqual(saved["runtime"]["thanks_selection"]["version"], version)
                self.assertEqual(saved["config"]["intention"], intention)

    def test_explicit_migration_preserves_language_context_and_clears_previous_preparation(self):
        for version, variety, intention in (
            (5, False, LITTLE_MEN_EXPERIMENTAL_INTENT),
            (7, True, LITTLE_MEN_ADAPTIVE_INTENT),
        ):
            with self.subTest(version=version):
                config = standard_config(variety)
                config.update(little_men_direction_version=version, intention=intention,
                              little_men_language="French", little_men_context="But saisi par l’utilisateur")
                item = new_item("Historical", config, {}, "migration")
                selected = make_selection(config, item["id"])
                selected.update(words="Merci", variety_choice={"objects": [],
                    "mechanism_family": "move", "departure_reason": "Direct contact is sufficient."})
                if variety:
                    selected["variety"] = make_variety_selection(item["id"], [])
                item["runtime"].update(session_id="previous-session", thanks_selection=selected)
                before = deepcopy(config)
                item["config"] = apply_preset(config, PRESET_ID if variety else "little_men_experimental", {})
                invalidate(item, before)
                migrated = item["runtime"]["thanks_selection"]
                self.assertEqual((migrated["version"], migrated["requested_language"], migrated["words"]),
                                 (8, "French", "Merci"))
                self.assertEqual(item["config"]["little_men_context"], before["little_men_context"])
                self.assertEqual(item["config"]["intention"],
                                 LITTLE_MEN_STANDARD_VARIETY_INTENT if variety else LITTLE_MEN_STANDARD_INTENT)
                self.assertNotIn("session_id", item["runtime"])
                self.assertNotIn("variety", migrated)
                self.assertNotIn("variety_choice", migrated)
                self.assertEqual(selected["version"], version)

    def test_same_version_switch_to_normal_removes_assortment_and_custom_keeps_origin(self):
        item = selected_item(True)
        before = deepcopy(item["config"])
        custom = apply_preset(before, "custom", {})
        self.assertTrue(is_variety(custom))
        item["config"] = apply_preset(before, "little_men_experimental", {})
        invalidate(item, before)
        selection = item["runtime"]["thanks_selection"]
        self.assertEqual(selection["version"], 8)
        self.assertNotIn("variety", selection)
        self.assertNotIn("VARIETY SELECTION", preparation_text(item["config"], thanks_selection=selection))
        lips = apply_preset(custom, "lips", {})
        self.assertIsNone(lips["little_men_direction_version"])
        self.assertFalse(is_variety(lips))

    def test_model_change_preserves_v8_assortment_but_discards_resolved_choice(self):
        item = selected_item(True)
        selection = item["runtime"]["thanks_selection"]
        selection["variety_choice"] = {"objects": [], "mechanism_family": "move",
                                       "departure_reason": "Direct contact is sufficient."}
        source = preparation_text(item["config"], thanks_selection=selection)
        before = deepcopy(item["config"])
        item["config"]["writer_model_id"] = "another-writer"
        invalidate(item, before)
        saved = item["runtime"]["thanks_selection"]
        self.assertEqual(saved["version"], 8)
        self.assertEqual(saved["variety"], selection["variety"])
        self.assertNotIn("variety_choice", saved)
        self.assertEqual(preparation_text(item["config"], thanks_selection=saved), source)


class StandardWorkflowTest(unittest.TestCase):
    def test_standard_policy_and_variety_choice_are_saved_without_causal_contract(self):
        for variety in (False, True):
            with self.subTest(variety=variety):
                item = selected_item(variety)
                selection = item["runtime"]["thanks_selection"]
                plan = {"spoken_languages": ["Japanese"], "spoken_lines": ["ありがとう"],
                        "shots": [{"phases": [{"actions": ["The hand helps the inhabitants."]}]}]}
                if variety:
                    identity = selection["variety"]["candidates"][0]
                    name = OBJECTS[identity]["name"]
                    plan["variety_choice"] = {"objects": [{"catalog_id": identity, "name": name}],
                        "mechanism_family": "move", "departure_reason": None}
                    plan["shots"][0]["phases"][0]["actions"] = [f"The giant hand uses a {name} to move the load."]
                adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
                    dlss=None, social=None, episodes=None, assets=None, coordinator=None)
                adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
                adapter.composition.cookbooks.get.return_value = NS(
                    preparation_steps=2, slots=[], stages=("beat_sheet",))
                adapter.composition.get.return_value.document.return_value = NS(
                    approved_revision_id="approved", active_revision=NS(content=json.dumps(plan)))
                item["runtime"]["session_id"] = "session"
                original_source = preparation_text(item["config"], thanks_selection=selection)
                checkpoint = Mock()
                adapter._plan(item, checkpoint, lambda: False, Mock())
                intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
                self.assertEqual(intent.speech_policy,
                                 LOCALIZED_THANKS_VARIETY_V8 if variety else LOCALIZED_THANKS_V8)
                saved = checkpoint.call_args.kwargs["thanks_selection"]
                self.assertEqual((saved["version"], saved["language"], saved["words"]),
                                 (8, "Japanese", "ありがとう"))
                self.assertEqual(saved.get("variety_choice"), plan.get("variety_choice"))
                self.assertEqual(preparation_text(item["config"], thanks_selection=saved), original_source)
                adapter.composition.stream_generate.assert_not_called()

    def test_custom_direct_prompt_still_bans_umbrella_before_submission(self):
        for variety in (False, True):
            for frozen in (False, True):
                with self.subTest(variety=variety, frozen=frozen):
                    item = selected_item(variety)
                    item["config"].update(preset="custom", final_prompt="The hand opens an umbrella.")
                    if not frozen:
                        item["runtime"].pop("thanks_selection")
                    item["runtime"]["render_project_id"] = "project"
                    adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=Mock(),
                        dlss=None, social=None, episodes=None, assets=None, coordinator=None)
                    adapter.render.get.return_value = NS(project_id="project")
                    with self.assertRaises(ValueError):
                        adapter._video(item, Mock(), lambda: False, Mock())
                    adapter.render.prepare_attempt.assert_not_called()
                    adapter.render.queue_attempt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
