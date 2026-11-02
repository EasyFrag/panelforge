"""User-run experimental preset integration; fake model and render adapters only."""
from panelforge.domain.little_men_objects import LEGACY_CATALOG_VERSION
from copy import deepcopy
from dataclasses import replace
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application import classic_cinematic as classic, little_men_causal as causal
from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import (
    PRESET_ID, SELECTION_MARKER, OBJECTS, make_variety_selection,
)
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V6
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import apply_preset, new_item, preparation_text, LITTLE_MEN_VARIETY_INTENT
from panelforge.domain.video_factory_results import delivery_material
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_little_men_variety_contract import variety_fixture, put_object
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


def prepared_input(identity="request-fixture"):
    source = config_for("Pays : Japon")
    config = apply_preset(source, PRESET_ID, source)
    config.update(little_men_direction_version=6, intention=LITTLE_MEN_VARIETY_INTENT)
    selection = make_selection(config, identity)
    selection["variety"] = make_variety_selection(identity, [], catalog_version=LEGACY_CATALOG_VERSION)
    return config, selection


class VarietyRequestTest(unittest.TestCase):
    def test_two_calls_preserve_the_choice_and_hide_unused_candidates_from_writer(self):
        with TemporaryDirectory() as directory:
            config, selection = prepared_input()
            source = preparation_text(config, thanks_selection=selection)
            self.assertEqual(extract_explicit_dialogues(source), ())
            chosen_id = selection["variety"]["candidates"][0]
            plan, _, _ = variety_fixture("Japanese")
            put_object(plan, chosen_id)
            writer = causal.canonical_writer(plan)
            service, gateway, session, composition = preparation_service(
                directory, "fl2va", "planned", [json.dumps(plan), json.dumps(writer)],
                source_text=source, creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
                cinematic_settings=ClassicCinematicSettings(1))
            intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V6,
                             speech_language="Japanese")
            service.configure(session.session_id, composition.cookbook.cookbook_id,
                composition.cookbook.version, composition.bindings, preparation_intent=intent)
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            service.compositions = LocalPromptCompositionStore(directory)
            reopened = service.get(session.session_id)
            approved = json.loads(reopened.document(CompositionStage.BEAT_SHEET).active_revision.content)
            self.assertEqual(approved["variety_choice"], plan["variety_choice"])
            self.assertEqual(reopened.preparation_intent, intent)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)
            planner, writer_request = gateway.requests
            self.assertEqual((len(planner.images), len(writer_request.images)), (1, 0))
            self.assertIn(SELECTION_MARKER, planner.user_prompt)
            for identity in selection["variety"]["candidates"]:
                self.assertIn(OBJECTS[identity]["name"], planner.user_prompt)
            writer_input = writer_request.user_prompt + writer_request.system_prompt
            self.assertNotIn(SELECTION_MARKER, writer_input)
            self.assertNotIn("mechanism_counts", writer_input)
            self.assertNotIn("mechanism_priority", writer_input)
            self.assertIn(OBJECTS[chosen_id]["name"], writer_input)
            self.assertIn("Japanese: ありがとう", writer_request.system_prompt)
            self.assertNotIn("English: Thank you", writer_request.system_prompt)
            for request in gateway.requests:
                self.assertNotIn("ceramic bowl", request.system_prompt + request.user_prompt)
                self.assertNotIn("Do not supply alternative scenarios, example mechanisms or an object catalogue",
                                 request.system_prompt)
            revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
            saved = classic.decode_context(revision.compiler_context)
            self.assertEqual(saved["variety_selection"], selection["variety"])
            self.assertEqual(saved["sequence_plan"]["variety_choice"], plan["variety_choice"])
            self.assertIn("<d>[Japanese] ありがとう</d>", revision.content)
            self.assertNotIn("[[help:", revision.content)
            self.assertNotIn("variety_choice", revision.content)
            self.assertNotIn("mechanism_counts", revision.content)
            self.assertEqual(revision.content.count(plan["shots"][0]["phases"][0]["actions"][1]), 1)
            # A manual re-save cannot approve an old Prompt against a new draw.
            new_selection = deepcopy(selection)
            new_selection["variety"] = make_variety_selection("a-different-fiche", [], catalog_version=LEGACY_CATALOG_VERSION)
            new_intent = replace(intent, source_text=preparation_text(config, thanks_selection=new_selection))
            service.configure(session.session_id, composition.cookbook.cookbook_id,
                composition.cookbook.version, composition.bindings, preparation_intent=new_intent)
            with self.assertRaises(ValueError):
                service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revision.content)

    def test_workflow_saves_actual_choice_without_rewriting_preparation_input(self):
        config, selection = prepared_input()
        plan, _, _ = variety_fixture("Japanese")
        put_object(plan, selection["variety"]["candidates"][0])
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(
            preparation_steps=2, slots=[], stages=("beat_sheet",))
        document = NS(approved_revision_id="approved", active_revision=NS(content=json.dumps(plan)))
        adapter.composition.get.return_value.document.return_value = document
        item = new_item("Image", config, {}, "image")
        item["runtime"].update(session_id="session", thanks_selection=selection)
        original = deepcopy(selection)
        source = preparation_text(config, thanks_selection=selection)
        checkpoint = Mock()
        adapter._plan(item, checkpoint, lambda: False, Mock())
        saved = checkpoint.call_args.kwargs["thanks_selection"]
        self.assertEqual(saved["variety_choice"], plan["variety_choice"])
        self.assertEqual(saved["variety"], original["variety"])
        self.assertEqual(selection, original)
        self.assertEqual(preparation_text(config, thanks_selection=saved), source)
        intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        self.assertEqual(intent.speech_policy, LOCALIZED_THANKS_V6)

    def test_custom_direct_prompt_keeps_umbrella_guard_without_a_plan(self):
        config, _ = prepared_input()
        config.update(preset="custom", intention="Une aide adaptée à la scène.",
                      final_prompt="The hand opens an umbrella above the residents.")
        project = NS(project_id="existing")
        render = Mock()
        render.get.return_value = project
        render.projects.get.return_value = project
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=render,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        item = new_item("Image", config, {}, "image")
        item["runtime"]["render_project_id"] = project.project_id
        with self.assertRaises(ValueError):
            adapter._video(item, Mock(), lambda: False, Mock())
        render.prepare_attempt.assert_not_called()
        render.queue_attempt.assert_not_called()

    def test_new_preset_is_exposed_separately_and_delivered_in_little_men_family(self):
        config, selection = prepared_input()
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        state = service.snapshot()
        self.assertEqual(state["presets"]["little_men_experimental"], "Petits hommes")
        self.assertEqual(state["presets"][PRESET_ID], "Petits hommes experimental")
        self.assertEqual(len(state["variety_objects"]), 80)
        self.assertEqual(state["variety_mechanisms"]["temperature"], "Modifier la température")
        item = new_item("Image", config, {}, "image")
        item["runtime"]["thanks_selection"] = selection
        item["status"] = "succeeded"
        item["steps"]["video"].update(status="succeeded", output={"asset_id": "asset-video"})
        item["steps"]["dlss"]["status"] = "skipped"
        self.assertEqual(delivery_material(item)["family"], "Petits hommes")


if __name__ == "__main__":
    unittest.main()
