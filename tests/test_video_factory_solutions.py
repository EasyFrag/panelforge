"""User-run offline regressions for v3 and the current preset. No real LLM, renderer or production state."""
from copy import deepcopy
from dataclasses import replace
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application import classic_cinematic as classic
from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.application.direct_fl2va_prompt import requested_h3_base_duration_ms
from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.application.vocal_policy import validate_speech
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_direction import compact_scene_context
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.localized_speech import (
    FIXED_THANKS, LOCALIZED_THANKS_V1, LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3,
)
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import (
    LITTLE_MEN_EXPERIMENTAL_INTENT, LITTLE_MEN_EXPERIMENTAL_INTENT_V2,
    apply_preset, invalidate, new_item, preparation_text,
)
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_experimental import speech_fixture
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


class CompactSceneTest(unittest.TestCase):
    def test_scene_materials_and_problem_survive_without_repeated_style_or_speech(self):
        intent = "Pays : Corée. Ville en laine menacée par un tsunami en résine."
        config = config_for(intent, {"intention": intent,
            "prompt": 'A wool city faces a resin wave. Old dialogue: "thank you kind hand".',
            "style": "A repeated long textile style. " * 90})
        original = deepcopy(config)
        text = preparation_text(config, thanks_selection=make_selection(config, "new"))
        self.assertEqual(config, original)
        self.assertEqual(text.count(intent), 1)
        self.assertIn("wool city", text)
        self.assertIn("resin wave", text)
        self.assertNotIn("repeated long textile style", text)
        self.assertEqual(extract_explicit_dialogues(text), ())
        self.assertNotIn("Frozen order", text)

    def test_full_context_drives_country_selection_before_display_excerpt(self):
        config = config_for(image_context={"prompt":
            "A textile village. " + "Tactile material details. " * 200 + " Country: Japan."})
        original = deepcopy(config)
        selection = make_selection(config, "new")
        self.assertEqual(selection["language"], "Japanese")
        compact = compact_scene_context(config)
        self.assertLess(len(compact), 1300)
        self.assertIn("[…]", compact)
        self.assertIn("Japan", compact)
        self.assertEqual(config, original)

    def test_render_duration_precedes_incidental_duration_in_source_description(self):
        config = config_for(image_context={"prompt": "An old 4-second movement in a wool city."})
        config["render"]["settings"]["duration_seconds"] = 12
        source = preparation_text(config, thanks_selection=make_selection(config, "new"))
        self.assertEqual(requested_h3_base_duration_ms(source), 12000)

    def test_missing_description_uses_style_and_stale_asset_is_ignored(self):
        config = config_for(image_context={"style": "A wool diorama"})
        self.assertIn("wool diorama", compact_scene_context(config))
        config["references"][0]["scene_context"]["asset_id"] = "asset-other"
        self.assertEqual(compact_scene_context(config), "")


class DirectionLifecycleTest(unittest.TestCase):
    def test_first_preparation_upgrades_only_untouched_default(self):
        for intention in (LITTLE_MEN_EXPERIMENTAL_INTENT_V2, "Mon idée personnelle : une passerelle."):
            with self.subTest(custom=intention != LITTLE_MEN_EXPERIMENTAL_INTENT_V2):
                config = config_for("Pays : Japon")
                config["intention"] = intention
                store, adapter = MemoryStore(), FakeWorkflows()
                service = VideoFactoryService(store=store, adapter=adapter)
                item = service.receive([dict(name="Image", config=config,
                    source={"kind": "image", "id": "source"})])["state"]["items"][0]
                service.launch([item["id"]], {item["id"]: item["revision"]})
                service._execute("local_gpu", item["id"], "plan")
                saved = store.value["items"][0]
                expected = LITTLE_MEN_EXPERIMENTAL_INTENT if intention == LITTLE_MEN_EXPERIMENTAL_INTENT_V2 else intention
                self.assertEqual(saved["config"]["intention"], expected)
                self.assertEqual(saved["source_config"]["intention"], intention)
                self.assertEqual(saved["runtime"]["thanks_selection"]["version"], 4)
                self.assertEqual(saved["config"]["render"], config["render"])
                reopened = VideoFactoryService(store=store, adapter=adapter).snapshot()["items"][0]
                self.assertEqual(reopened["runtime"]["thanks_selection"], saved["runtime"]["thanks_selection"])

    def test_started_v2_is_preserved_but_duplicate_gets_new_direction(self):
        config = config_for("Pays : Japon")
        config["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V2
        old = new_item("Old", config, {}, "old")
        selection = {**make_selection(config, old["id"]), "version": 2}
        old["runtime"].update(session_id="existing", thanks_selection=selection)
        old["status"] = "active"
        store, adapter = MemoryStore(), FakeWorkflows()
        store.value["items"] = [old]
        service = VideoFactoryService(store=store, adapter=adapter)
        service._execute("local_gpu", old["id"], "plan")
        saved = store.value["items"][0]
        self.assertEqual(saved["config"]["intention"], LITTLE_MEN_EXPERIMENTAL_INTENT_V2)
        self.assertEqual(saved["runtime"]["thanks_selection"], selection)
        service.action("duplicate", [saved["id"]], {saved["id"]: saved["revision"]})
        original, duplicate = store.value["items"]
        self.assertEqual(original["config"]["intention"], LITTLE_MEN_EXPERIMENTAL_INTENT_V2)
        self.assertEqual(duplicate["config"]["intention"], LITTLE_MEN_EXPERIMENTAL_INTENT)
        self.assertNotIn("session_id", duplicate["runtime"])
        self.assertNotIn("thanks_selection", duplicate["runtime"])
        self.assertEqual(duplicate["config"]["render"], config["render"])

    def test_model_edit_keeps_v2_but_explicit_preset_reapply_uses_current_version(self):
        config = config_for("Pays : Japon")
        config["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V2
        item = new_item("Image", config, {}, "old")
        item["runtime"]["thanks_selection"] = {**make_selection(config, item["id"]), "version": 2}
        before = deepcopy(item["config"])
        item["config"]["writer_model_id"] = "another-model"
        invalidate(item, before)
        self.assertEqual(item["runtime"]["thanks_selection"]["version"], 2)
        before = deepcopy(item["config"])
        item["config"] = apply_preset(before, "little_men_experimental", item["source_config"])
        invalidate(item, before)
        self.assertEqual(item["runtime"]["thanks_selection"]["version"], 4)
        self.assertEqual(item["runtime"]["thanks_selection"]["requested_language"], "Japanese")

    def test_adapter_preserves_v1_and_v2_preparation_inputs(self):
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
        for version, policy in ((1, LOCALIZED_THANKS_V1), (2, LOCALIZED_THANKS_V2)):
            with self.subTest(version=version):
                config = config_for("Pays : Japon")
                config["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V2
                item = new_item("Old", config, {}, str(version))
                item["runtime"]["session_id"] = "session"
                selection = None if version == 1 else {**make_selection(config, item["id"]), "version": 2}
                if selection:
                    item["runtime"]["thanks_selection"] = selection
                expected = preparation_text(config, thanks_selection=selection)
                adapter._session(item, Mock(), lambda: False, Mock())
                intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
                self.assertEqual(intent.speech_policy, policy)
                self.assertEqual(intent.source_text, expected)
                self.assertIn("Prévoir deux gestes", intent.source_text)


class PreparedRequestTest(unittest.TestCase):
    def test_known_and_visual_choices_keep_source_stable_but_writer_never_selects_again(self):
        for country in ("Pays : Japon", ""):
            with self.subTest(country=country), TemporaryDirectory() as directory:
                config = config_for(country)
                selection = {**make_selection(config, "image"), "version": 3}
                source = preparation_text(config, thanks_selection=selection)
                plan, writer, _ = speech_fixture("Japanese", "ありがとう！")
                service, gateway, session, composition = preparation_service(
                    directory, "fl2va", "planned", [json.dumps(plan), json.dumps(writer)],
                    source_text=source, creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
                    cinematic_settings=ClassicCinematicSettings(1))
                intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V3,
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
                self.assertIn("HELP MECHANISM:", planner.system_prompt)
                self.assertNotIn("HELP MECHANISM:", writer_request.system_prompt)
                self.assertEqual("Frozen order:" in planner.user_prompt, not bool(country))
                self.assertNotIn("LANGUAGE CHOICE", writer_request.user_prompt)
                self.assertNotIn("Frozen order", writer_request.user_prompt + writer_request.system_prompt)
                self.assertIn("Japanese: ありがとう", writer_request.system_prompt)
                self.assertNotIn("English: Thank you", writer_request.system_prompt)
                if country:
                    self.assertNotIn("English: Thank you", planner.system_prompt)
                self.assertEqual(len(planner.images), 1)
                self.assertEqual(writer_request.images, ())
                final = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision.content
                self.assertIn("<d>[Japanese] ありがとう！</d>", final)

    def test_all_eleven_still_require_the_exact_minimal_formula(self):
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                self.assertEqual(validate_speech(((language, words),), (), level=1, source_text="Scene",
                    speech_policy=LOCALIZED_THANKS_V3, speech_language=language), (words,))
                with self.assertRaises(ValueError):
                    validate_speech(((language, words + " kind hand"),), (), level=1, source_text="Scene",
                        speech_policy=LOCALIZED_THANKS_V3, speech_language=language, locked=(words + " kind hand",))

    def test_plan_and_writer_block_extra_words_and_language_changes(self):
        plan, writer, context = speech_fixture("English", "Thank you, kind hand.")
        context.update(speech_policy=LOCALIZED_THANKS_V3, speech_language="English")
        with self.assertRaisesRegex(ValueError, "sans aucun ajout"):
            classic.canonical_plan(json.dumps(plan), context)
        context["plan"] = plan
        with self.assertRaisesRegex(ValueError, "sans aucun ajout"):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        plan, writer, context = speech_fixture("English", "Thank you!")
        context.update(speech_policy=LOCALIZED_THANKS_V3, speech_language="English")
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        prompt, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        for invalid in (prompt.replace("Thank you!", "Thank you, kind hand."),
                        prompt.replace("[English]", "[French]")):
            with self.assertRaises(ValueError):
                classic.validate_final(invalid, classic.decode_context(encoded))

    def test_one_or_four_helping_gestures_fit_existing_plan_contract(self):
        gestures = [
            "The hand lowers a shallow tray across the incoming wave.",
            "The hand tilts the tray toward the empty basin outside the city.",
            "The hand steadies the tray while the water drains into the basin.",
            "The hand lifts the filled tray away; the protected street remains clear.",
        ]
        for count in (1, 4):
            with self.subTest(count=count):
                plan, _, context = speech_fixture("French", "Merci!")
                actions = gestures[:count] + ["The little people say together <d>[French] Merci!</d>"]
                plan["shots"][0]["phases"][0]["actions"] = actions
                context.update(speech_policy=LOCALIZED_THANKS_V3, speech_language="French")
                canonical = json.loads(classic.canonical_plan(json.dumps(plan), context))
                self.assertEqual(canonical["shots"][0]["phases"][0]["actions"], actions)


if __name__ == "__main__":
    unittest.main()
