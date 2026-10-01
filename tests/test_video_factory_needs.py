"""User-run offline regressions for targeted needs. No real LLM or rendering."""
from copy import deepcopy
from dataclasses import replace
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application import classic_cinematic as classic
from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.application.vocal_policy import validate_speech
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_direction import (
    NEED_DIRECTIONS, SOLUTION_PLAN_POLICY, SOLUTION_PLAN_POLICY_V4, preparation_text_v3, scene_need,
)
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import (
    LITTLE_MEN_EXPERIMENTAL_INTENT, LITTLE_MEN_EXPERIMENTAL_INTENT_V3,
    apply_preset, invalidate, new_item, preparation_text,
)
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_experimental import speech_fixture
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


class SceneNeedTest(unittest.TestCase):
    def test_four_goals_use_context_in_french_and_english(self):
        for text, expected in (
            ("Sécheresse en Corée", "drought"), ("A parched city street", "drought"),
            ("Un tsunami à Rome", "wave"), ("A tidal wave flooding a city", "wave"),
            ("Une innondation en ville", "flood"), ("A flooded town", "flood"),
            ("Un incendie en laine", "fire"), ("A burning building", "fire"),
        ):
            with self.subTest(text=text):
                config = config_for(text)
                before = deepcopy(config)
                self.assertEqual(scene_need(config), expected)
                source = preparation_text(config, thanks_selection=make_selection(config, "new"))
                for kind, phrase in NEED_DIRECTIONS.items():
                    self.assertEqual(source.count(phrase), int(kind == expected))
                self.assertEqual(config, before)

    def test_tsunami_image_intent_beats_misleading_fire_label_and_style(self):
        config = config_for(image_context={"intention": "Un tsunami, Rome, Colisée",
            "prompt": "A towering wave floods a city", "style": "A fiery resin aesthetic"})
        config["references"][0]["label"] = "Petits_hommes_incendie_DLSS"
        self.assertEqual(scene_need(config), "wave")
        config["references"][0]["scene_context"]["intention"] = "Sécheresse en Corée"
        config["references"][0]["scene_context"]["prompt"] = "Cracked asphalt across a city street."
        self.assertEqual(scene_need(config), "drought")

    def test_author_notes_and_custom_intent_precede_image_metadata(self):
        config = config_for("Sécheresse : manque d’eau", {"intention": "Inondation"})
        self.assertEqual(scene_need(config), "drought")
        config["intention"] = "Réparer le pont cassé."
        self.assertEqual(scene_need(config), "repair")
        source = preparation_text(config, thanks_selection=make_selection(config, "new"))
        self.assertFalse(any(phrase in source for phrase in NEED_DIRECTIONS.values()))

    def test_tornado_repair_unknown_and_conflicting_scenes_add_no_forced_water_goal(self):
        for text, expected in (
            ("Une tornade en laine", "tornado"), ("Pont brisé", "repair"),
            ("Un village miniature", "unknown"), ("Sécheresse et incendie", "ambiguous"),
            ("Pas d’incendie", "ambiguous"), ("No fire", "ambiguous"),
        ):
            with self.subTest(text=text):
                config = config_for(text)
                self.assertEqual(scene_need(config), expected)
                source = preparation_text(config, thanks_selection=make_selection(config, "new"))
                self.assertFalse(any(phrase in source for phrase in NEED_DIRECTIONS.values()))

    def test_description_is_read_before_excerpt_but_wrong_asset_and_style_are_ignored(self):
        description = "A quiet village. " + "Some tiny buildings. " * 200 + "Water shortage."
        config = config_for(image_context={"prompt": description, "style": "Fire"})
        self.assertEqual(scene_need(config), "drought")
        config["references"][0]["scene_context"]["asset_id"] = "asset-wrong"
        self.assertEqual(scene_need(config), "unknown")
        config = config_for(image_context={"style": "A landscape with fire and drought"})
        config["references"][0]["label"] = "Incendie"
        self.assertEqual(scene_need(config), "unknown")


class NeedLifecycleTest(unittest.TestCase):
    def test_existing_v4_needs_keep_locked_source_and_new_selections_use_current_goals(self):
        for context, kind, marker, old_goal in (
            ("Une inondation en ville", "flood", "flood_first_action",
             "Évacuer l’eau hors de la zone protégée et montrer une baisse durable du niveau."),
            ("Une sécheresse en ville", "drought", "drought_result",
             "Apporter de l’eau pour soulager la sécheresse et rendre son bénéfice visible."),
        ):
            with self.subTest(kind=kind):
                config = config_for(context)
                selection = make_selection(config, kind)
                old_selection = {key: value for key, value in selection.items() if key != marker}
                old_source = config["intention"] + "\n\n" + old_goal
                self.assertEqual(preparation_text(config, thanks_selection=old_selection),
                                 preparation_text_v3(config, old_source, old_selection))
                new_source = preparation_text(config, thanks_selection=selection)
                self.assertIn(NEED_DIRECTIONS[kind], new_source)
                self.assertNotEqual(new_source, preparation_text(config, thanks_selection=old_selection))
                resolved = {**selection, "language": "French", "words": "Merci"}
                self.assertEqual(preparation_text(config, thanks_selection=resolved), new_source)

    def test_old_v3_session_is_unchanged_and_duplicate_upgrades_only_default(self):
        for original_intent in (LITTLE_MEN_EXPERIMENTAL_INTENT_V3, "Sécheresse : mon idée personnalisée."):
            with self.subTest(custom=original_intent != LITTLE_MEN_EXPERIMENTAL_INTENT_V3):
                config = config_for("Sécheresse, Corée")
                config["intention"] = original_intent
                old = new_item("Old", config, {}, "old")
                selected = {**make_selection(config, old["id"]), "version": 3}
                old["runtime"].update(session_id="existing", thanks_selection=selected)
                old["status"] = "active"
                store, adapter = MemoryStore(), FakeWorkflows()
                store.value["items"] = [old]
                service = VideoFactoryService(store=store, adapter=adapter)
                service._execute("local_gpu", old["id"], "plan")
                saved = store.value["items"][0]
                self.assertEqual(saved["config"]["intention"], original_intent)
                self.assertEqual(saved["runtime"]["thanks_selection"], selected)
                service.action("duplicate", [saved["id"]], {saved["id"]: saved["revision"]})
                original, duplicate = store.value["items"]
                expected = LITTLE_MEN_EXPERIMENTAL_INTENT if original_intent == LITTLE_MEN_EXPERIMENTAL_INTENT_V3 else original_intent
                self.assertEqual(duplicate["config"]["intention"], expected)
                self.assertEqual(original["config"]["intention"], original_intent)
                self.assertEqual(duplicate["config"]["render"], config["render"])
                self.assertFalse(duplicate["config"]["social"]["enabled"])
                self.assertNotIn("thanks_selection", duplicate["runtime"])

    def test_adapter_keeps_v3_policy_and_explicit_reapply_upgrades_to_v4(self):
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
        config = config_for("Sécheresse, Corée")
        config["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V3
        item = new_item("Image", config, {}, "old")
        selection = {**make_selection(config, "old"), "version": 3}
        selection.pop("flood_first_action")  # Fields absent in historical selections.
        selection.pop("drought_result")
        item["runtime"].update(session_id="session", thanks_selection=selection)
        adapter._session(item, Mock(), lambda: False, Mock())
        intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        self.assertEqual(intent.speech_policy, LOCALIZED_THANKS_V3)
        self.assertNotIn(NEED_DIRECTIONS["drought"], intent.source_text)
        before = deepcopy(item["config"])
        item["config"] = apply_preset(before, "little_men_experimental", item["source_config"])
        invalidate(item, before)
        self.assertEqual(item["runtime"]["thanks_selection"]["version"], 4)
        self.assertEqual(item["runtime"]["thanks_selection"]["flood_first_action"], "plunger")
        self.assertEqual(item["runtime"]["thanks_selection"]["drought_result"], "lush_growth")
        self.assertEqual(item["runtime"]["thanks_selection"]["language"], selection["language"])
        self.assertIn(NEED_DIRECTIONS["drought"],
                      preparation_text(item["config"], thanks_selection=item["runtime"]["thanks_selection"]))


class NeedRequestTest(unittest.TestCase):
    def test_plan_and_writer_receive_one_goal_with_frozen_language_and_short_policy(self):
        for context, kind, country in (("Sécheresse", "drought", "Pays : Japon"),
                                       ("Un tsunami", "wave", ""), ("Une inondation", "flood", ""),
                                       ("Un incendie", "fire", "")):
            with self.subTest(kind=kind), TemporaryDirectory() as directory:
                config = config_for(context + "\n" + country)
                selection = make_selection(config, "image")
                source = preparation_text(config, thanks_selection=selection)
                plan, writer, _ = speech_fixture("Japanese", "ありがとう！")
                service, gateway, session, composition = preparation_service(
                    directory, "fl2va", "planned", [json.dumps(plan), json.dumps(writer)],
                    source_text=source, creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
                    cinematic_settings=ClassicCinematicSettings(1))
                intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V4,
                                 speech_language=selection["requested_language"])
                service.configure(session.session_id, composition.cookbook.cookbook_id,
                                  composition.cookbook.version, composition.bindings, preparation_intent=intent)
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                service.compositions = LocalPromptCompositionStore(directory)
                resolved = {**selection, "language": "Japanese", "words": "ありがとう！"}
                self.assertEqual(preparation_text(config, thanks_selection=resolved), source)
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                self.assertEqual(service.get(session.session_id).preparation_intent, intent)
                self.assertEqual(len(gateway.requests), 2)
                planner, writer_request = gateway.requests
                self.assertIn(SOLUTION_PLAN_POLICY_V4, planner.system_prompt)
                self.assertNotIn(SOLUTION_PLAN_POLICY, planner.system_prompt)
                self.assertNotIn("HELP MECHANISM:", writer_request.system_prompt)
                for request in gateway.requests:
                    self.assertEqual(request.user_prompt.count(NEED_DIRECTIONS[kind]), 1)
                    self.assertFalse(any(phrase in request.user_prompt for other, phrase in NEED_DIRECTIONS.items() if other != kind))
                self.assertNotIn("Frozen order", writer_request.user_prompt + writer_request.system_prompt)
                self.assertIn("Japanese: ありがとう", writer_request.system_prompt)
                self.assertNotIn("English: Thank you", writer_request.system_prompt)
                self.assertEqual(len(planner.images), 1)
                self.assertEqual(writer_request.images, ())
                final = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision.content
                self.assertIn("<d>[Japanese] ありがとう！</d>", final)

    def test_all_eleven_formulas_remain_strict_in_v4(self):
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                self.assertEqual(validate_speech(((language, words),), (), level=1, source_text="Scene",
                    speech_policy=LOCALIZED_THANKS_V4, speech_language=language), (words,))
                for wrong in (words + " kind hand", words + " " + words):
                    with self.assertRaises(ValueError):
                        validate_speech(((language, wrong),), (), level=1, source_text="Scene",
                            speech_policy=LOCALIZED_THANKS_V4, speech_language=language, locked=(wrong,))

    def test_compiler_preserves_words_and_rejects_changed_formula_or_language(self):
        plan, writer, context = speech_fixture("French", "Merci!")
        context.update(speech_policy=LOCALIZED_THANKS_V4, speech_language="French")
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        prompt, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        for wrong in (prompt.replace("Merci!", "Merci beaucoup!"), prompt.replace("[French]", "[English]")):
            with self.assertRaises(ValueError):
                classic.validate_final(wrong, classic.decode_context(encoded))


if __name__ == "__main__":
    unittest.main()
