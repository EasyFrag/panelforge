"""User-run standard-H3 integration with scripted replies and temporary stores."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelforge.application import classic_cinematic as classic
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import PRESET_ID, SELECTION_MARKER, make_variety_selection
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V8, LOCALIZED_THANKS_VARIETY_V8
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import apply_preset, preparation_text
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from panelforge.infrastructure.storage.prompt_recipes import CAMERA_CONTRACT, LocalPromptRecipeStore
from tests.test_classic_cinematic import fixture as classic_fixture
from tests.test_little_men_standard_contract import add_object, ordinary_writer, standard_fixture
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


ROOT = Path(__file__).resolve().parents[1]
H3 = ("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0")


def recipe_store(directory):
    return LocalPromptRecipeStore(directory, LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks"),
                                 ROOT / "prompt_sources/_defaults")


def standard_input(*, variety=False, language="Portuguese"):
    original = config_for("Pays : Brésil", image_context={
        "intention": "ORIGINAL_IMAGE_GOAL_ONLY. The inhabitants already help an immobilized animal.",
        "prompt": "ORIGINAL_IMAGE_PROMPT_ONLY. The inhabitants support a quiet animal. "
                  'Durée totale : 12 secondes. Previous voice-over: <d>[English] Run away</d>.',
        "style": "ORIGINAL_IMAGE_STYLE_ONLY",
    })
    config = apply_preset(original, PRESET_ID if variety else "little_men_experimental", original)
    config["little_men_language"] = language
    selection = make_selection(config, "standard-request-fixture")
    if variety:
        selection["variety"] = make_variety_selection("standard-request-fixture", [])
    return config, selection


def standard_service(directory, config, selection, responses, *, language="Portuguese", variety=False):
    service, gateway, session, composition = preparation_service(
        directory, "fl2va", "planned", responses,
        source_text=preparation_text(config, thanks_selection=selection),
        creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
        cinematic_settings=ClassicCinematicSettings(1))
    intent = replace(composition.preparation_intent,
        speech_policy=LOCALIZED_THANKS_VARIETY_V8 if variety else LOCALIZED_THANKS_V8,
        speech_language=language)
    composition = service.configure(session.session_id, composition.cookbook.cookbook_id,
        composition.cookbook.version, composition.bindings, preparation_intent=intent)
    service.prompt_recipes = recipe_store(directory)
    return service, gateway, session, composition


def prepare(service, session, stage):
    service.generate(session.session_id, stage)
    service.approve(session.session_id, stage)


class StandardHelpRequestTest(unittest.TestCase):
    def test_both_presets_use_standard_plan_and_writer_and_editable_camera_contract(self):
        for variety in (False, True):
            with self.subTest(variety=variety), TemporaryDirectory() as directory:
                config, selection = standard_input(variety=variety)
                plan, writer, _ = standard_fixture(variety=variety)
                service, gateway, session, _ = standard_service(
                    directory, config, selection, [json.dumps(plan), json.dumps(writer)], variety=variety)
                prepare(service, session, CompositionStage.BEAT_SHEET)
                service.compositions = LocalPromptCompositionStore(directory)
                prepare(service, session, CompositionStage.FINAL_PROMPT)
                self.assertEqual(len(gateway.requests), 2)
                planner, writer_request = gateway.requests
                self.assertIn("CALL 1 OF 2: CLASSIC DIRECTION PLAN", planner.system_prompt)
                self.assertIn("CALL 2 OF 2: CLASSIC SCENE WRITER", writer_request.system_prompt)
                self.assertIn(CAMERA_CONTRACT, planner.system_prompt)
                self.assertIn("never 'alongside'", planner.user_prompt)
                self.assertIn("CLASSIC CINEMATIC 1.0", planner.system_prompt)
                for request in gateway.requests:
                    self.assertEqual(request.trace_context["recipe_revision"], 2)
                    self.assertNotIn("PETITS HOMMES CAUSAL DIRECTION", request.system_prompt)
                    self.assertNotIn("PETITS HOMMES ADAPTIVE DIRECTION", request.system_prompt)
                    self.assertNotIn("CAUSAL ACTION TRANSPORT", request.system_prompt)
                    self.assertNotIn("[[help:", request.user_prompt)
                revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
                self.assertEqual(revision.content.count("<d>[Portuguese] Obrigado</d>"), 1)
                self.assertEqual(revision.prompt_recipe_revision, 2)
                context = classic.decode_context(revision.compiler_context)
                self.assertEqual(context["duration_ms"], 10000)
                self.assertNotIn("help_contract", context["sequence_plan"])

    def test_image_metadata_and_candidates_go_only_to_plan_but_approved_choice_reaches_writer(self):
        config, selection = standard_input(variety=True)
        plan, _, _ = standard_fixture(variety=True)
        identity = selection["variety"]["candidates"][0]
        chosen_name = add_object(plan, identity)
        with TemporaryDirectory() as directory:
            service, gateway, session, _ = standard_service(directory, config, selection,
                [json.dumps(plan), json.dumps(ordinary_writer(plan))], variety=True)
            prepare(service, session, CompositionStage.BEAT_SHEET)
            prepare(service, session, CompositionStage.FINAL_PROMPT)
            planner, writer_request = gateway.requests
            writer_input = writer_request.system_prompt + writer_request.user_prompt
            self.assertEqual((len(planner.images), len(writer_request.images)), (1, 0))
            for marker in ("ORIGINAL_IMAGE_GOAL_ONLY", "ORIGINAL_IMAGE_PROMPT_ONLY", "ORIGINAL_IMAGE_STYLE_ONLY"):
                self.assertIn(marker, planner.user_prompt)
                self.assertNotIn(marker, writer_input)
            self.assertIn(SELECTION_MARKER, planner.user_prompt)
            self.assertNotIn(SELECTION_MARKER, writer_input)
            self.assertNotIn("mechanism_counts", writer_input)
            self.assertNotIn("mechanism_priority", writer_input)
            self.assertIn(chosen_name, writer_input)
            self.assertNotIn("Run away", writer_input)
            revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
            context = classic.decode_context(revision.compiler_context)
            self.assertEqual(context["variety_selection"], selection["variety"])
            self.assertEqual(context["sequence_plan"]["variety_choice"], plan["variety_choice"])
            self.assertEqual(context["duration_ms"], 10000)

    def test_writer_keeps_plan_recipe_revision_if_shared_recipe_is_edited_in_between(self):
        config, selection = standard_input()
        plan, writer, _ = standard_fixture()
        with TemporaryDirectory() as directory:
            service, gateway, session, _ = standard_service(
                directory, config, selection, [json.dumps(plan), json.dumps(writer)])
            prepare(service, session, CompositionStage.BEAT_SHEET)
            package = service.prompt_recipes.get(*H3)
            fields = {**package["fields"], "writer.system": package["fields"]["writer.system"] + "\nNEW_WRITER_REVISION_ONLY."}
            service.prompt_recipes.save(*H3, base_revision=2, expected_active=2, fields=fields)
            prepare(service, session, CompositionStage.FINAL_PROMPT)
            self.assertEqual(gateway.requests[-1].trace_context["recipe_revision"], 2)
            self.assertNotIn("NEW_WRITER_REVISION_ONLY", gateway.requests[-1].system_prompt)

    def test_automatic_language_can_be_resaved_and_changed_image_context_invalidates_final_prompt(self):
        config, selection = standard_input(variety=True, language="auto")
        self.assertIsNone(selection.get("requested_language"))
        self.assertNotIn("<d>[Portuguese]", preparation_text(config, thanks_selection=selection))
        plan, writer, _ = standard_fixture(variety=True)
        with TemporaryDirectory() as directory:
            service, gateway, session, composition = standard_service(directory, config, selection,
                [json.dumps(plan), json.dumps(writer)], language=None, variety=True)
            prepare(service, session, CompositionStage.BEAT_SHEET)
            prepare(service, session, CompositionStage.FINAL_PROMPT)
            revision = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
            context = classic.decode_context(revision.compiler_context)
            self.assertEqual(context["speech_language"], "Portuguese")
            service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revision.content)
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            changed = deepcopy(config)
            changed["references"][0]["scene_context"]["intention"] += " A changed original objective."
            new_intent = replace(composition.preparation_intent,
                source_text=preparation_text(changed, thanks_selection=selection))
            service.configure(session.session_id, composition.cookbook.cookbook_id,
                composition.cookbook.version, composition.bindings, preparation_intent=new_intent)
            service.edit(session.session_id, CompositionStage.BEAT_SHEET, json.dumps(plan))
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            with self.assertRaises(ValueError):
                service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revision.content)
            self.assertEqual(len(gateway.requests), 2)

    def test_unrelated_classic_preparation_keeps_ordinary_recipe_without_little_men_rules(self):
        plan, writer, _ = classic_fixture(mode="i2va", count=1)
        with TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "planned",
                [json.dumps(plan), json.dumps(writer)],
                source_text="A quiet object reveal lasting eight seconds. No music or speech.",
                cinematic_settings=ClassicCinematicSettings(1))
            service.prompt_recipes = recipe_store(directory)
            prepare(service, session, CompositionStage.BEAT_SHEET)
            prepare(service, session, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)
            for request in gateway.requests:
                self.assertEqual(request.trace_context["recipe_revision"], 2)
                self.assertNotIn("LOCALIZED THANK-YOU", request.system_prompt)
                self.assertNotIn("variety_choice", request.user_prompt)
                self.assertNotIn("help_contract", request.user_prompt)


if __name__ == "__main__":
    unittest.main()
