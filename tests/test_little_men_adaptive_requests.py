"""User-run v7 integration with scripted gateways and temporary stores only."""
from panelforge.domain.little_men_objects import LEGACY_CATALOG_VERSION
from copy import deepcopy
from dataclasses import replace
import json
from tempfile import TemporaryDirectory
import unittest

from panelforge.application import classic_cinematic as classic, little_men_causal as causal
from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import PRESET_ID, OBJECTS, SELECTION_MARKER, make_variety_selection
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V7
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import LITTLE_MEN_ADAPTIVE_INTENT, apply_preset, preparation_text
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_little_men_adaptive_contract import adaptive_fixture
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


def adaptive_input():
    original = config_for("Pays : Japon", image_context={
        "intention": "ORIGINAL_IMAGE_INTENTION_ONLY. The inhabitants already assist the immobilized animal.",
        "prompt": "Original image description. " * 85
                  + "MIDDLE_IMAGE_CAUSE_ONLY. Existing efforts support the intended beneficiary. "
                  + 'Durée totale : 12 secondes. Previous speech: <d>[English] Run away</d>. '
                  + "Original image description. " * 85,
        "style": "ORIGINAL_IMAGE_STYLE_ONLY",
    })
    config = apply_preset(original, PRESET_ID, original)
    config.update(little_men_direction_version=7, intention=LITTLE_MEN_ADAPTIVE_INTENT)
    selection = make_selection(config, "adaptive-request-fixture")
    selection["variety"] = make_variety_selection("adaptive-request-fixture", [], catalog_version=LEGACY_CATALOG_VERSION)
    return config, selection


def adaptive_service(directory, config, selection, responses, *, speech_language="Japanese"):
    service, gateway, session, composition = preparation_service(
        directory, "fl2va", "planned", responses,
        source_text=preparation_text(config, thanks_selection=selection),
        creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
        cinematic_settings=ClassicCinematicSettings(1))
    intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V7,
                     speech_language=speech_language)
    composition = service.configure(session.session_id, composition.cookbook.cookbook_id,
        composition.cookbook.version, composition.bindings, preparation_intent=intent)
    return service, gateway, session, composition


class AdaptiveRequestTest(unittest.TestCase):
    def test_automatic_language_resolution_can_compile_and_resave_the_prompt(self):
        config, selection = adaptive_input()
        plan, writer, _ = adaptive_fixture("Japanese")
        with TemporaryDirectory() as directory:
            service, gateway, session, _ = adaptive_service(
                directory, config, selection, [json.dumps(plan), json.dumps(writer)],
                speech_language=None)
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
            context = classic.decode_context(revision.compiler_context)
            self.assertEqual(context["speech_language"], "Japanese")
            service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revision.content)
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)

    def test_two_calls_keep_metadata_in_plan_and_preserve_approved_help_in_writer(self):
        config, selection = adaptive_input()
        plan, _, _ = adaptive_fixture("Japanese")
        chosen_id = selection["variety"]["candidates"][0]
        name = OBJECTS[chosen_id]["name"]
        plan["variety_choice"].update(
            objects=[{"catalog_id": chosen_id, "name": name}], departure_reason=None)
        plan["shots"][0]["phases"][0]["actions"][1] = (
            f"The giant hand uses the {name} to ease the restraint away from the animal while the inhabitants support it.")
        plan["help_contract"]["mechanism"] = (
            f"The {name} transmits the hand's controlled movement to separate the restraint from the beneficiary.")
        writer = causal.canonical_writer(plan)
        with TemporaryDirectory() as directory:
            service, gateway, session, composition = adaptive_service(
                directory, config, selection, [json.dumps(plan), json.dumps(writer)])
            source = composition.preparation_intent.source_text
            self.assertEqual(extract_explicit_dialogues(source), ())
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            service.compositions = LocalPromptCompositionStore(directory)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)
            planner, writer_request = gateway.requests
            self.assertEqual((len(planner.images), len(writer_request.images)), (1, 0))
            writer_input = writer_request.system_prompt + writer_request.user_prompt
            for marker in ("ORIGINAL_IMAGE_INTENTION_ONLY", "MIDDLE_IMAGE_CAUSE_ONLY"):
                self.assertIn(marker, planner.user_prompt)
                self.assertNotIn(marker, writer_input)
            self.assertIn(SELECTION_MARKER, planner.user_prompt)
            self.assertNotIn(SELECTION_MARKER, writer_input)
            self.assertNotIn("mechanism_counts", writer_input)
            self.assertNotIn("mechanism_priority", writer_input)
            for object_id in selection["variety"]["candidates"]:
                self.assertIn(OBJECTS[object_id]["name"], planner.user_prompt)
            self.assertIn(name, writer_input)
            self.assertIn(plan["help_contract"]["beneficiary"], writer_input)
            self.assertIn("Japanese: ありがとう", writer_request.system_prompt)
            self.assertNotIn("English: Thank you", writer_request.system_prompt)
            for request in gateway.requests:
                self.assertNotIn("necessary threat", request.system_prompt)
                self.assertNotIn("must first benefit from", request.system_prompt)
            revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
            saved = classic.decode_context(revision.compiler_context)
            self.assertEqual(saved["duration_ms"], 10000)
            self.assertEqual(saved["speech_policy"], LOCALIZED_THANKS_V7)
            self.assertEqual(saved["variety_selection"], selection["variety"])
            self.assertIsNone(saved["sequence_plan"]["help_contract"]["threat"])
            self.assertEqual(saved["sequence_plan"]["variety_choice"], plan["variety_choice"])
            self.assertNotIn("[[help:", revision.content)
            self.assertEqual(revision.content.count("<d>[Japanese] ありがとう</d>"), 1)
            cursor = 0
            for action in plan["shots"][0]["phases"][0]["actions"]:
                self.assertEqual(revision.content.count(action), 1)
                position = revision.content.index(action)
                self.assertGreaterEqual(position, cursor)
                cursor = position + len(action)

            # Even the same approved solution must not reuse an old compiler
            # context after its input metadata changes.
            changed = deepcopy(config)
            changed["references"][0]["scene_context"]["intention"] += " Additional source context."
            new_intent = replace(composition.preparation_intent,
                source_text=preparation_text(changed, thanks_selection=selection))
            service.configure(session.session_id, composition.cookbook.cookbook_id,
                composition.cookbook.version, composition.bindings, preparation_intent=new_intent)
            service.edit(session.session_id, CompositionStage.BEAT_SHEET, json.dumps(plan))
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            with self.assertRaises(ValueError):
                service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revision.content)
            self.assertEqual(len(gateway.requests), 2)

    def test_needs_context_stops_after_one_request_and_cannot_be_approved(self):
        config, selection = adaptive_input()
        diagnostic = {"status": "needs_context", "reason": "Aucun objectif utile ne peut être établi à partir des données disponibles."}
        with TemporaryDirectory() as directory:
            service, gateway, session, _ = adaptive_service(
                directory, config, selection, [json.dumps(diagnostic)])
            with self.assertRaises(ValueError) as raised:
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            self.assertIn(diagnostic["reason"], str(raised.exception))
            composition = service.get(session.session_id)
            self.assertIsNone(composition.document(CompositionStage.BEAT_SHEET).active_revision)
            self.assertIsNone(composition.document(CompositionStage.FINAL_PROMPT).active_revision)
            with self.assertRaises(ValueError):
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            with self.assertRaises(ValueError):
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 1)
            self.assertIn("needs_context", gateway.requests[0].user_prompt)


if __name__ == "__main__":
    unittest.main()
