"""User-run localized thank-you regressions; fake models, no real generation."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application import classic_cinematic as classic
from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.application.video_preparation import preparation_source
from panelforge.application.vocal_policy import validate_speech, vocal_policy
from panelforge.domain import CompositionStage
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V1, THANKS_LANGUAGES
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import (
    apply_preset, configuration, new_item, preparation_text, validate_shape,
)
from panelforge.domain.video_factory_results import delivery_material
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from panelforge.infrastructure.storage.prompt_compositions import intent_from_dict, intent_to_dict
from tests.test_classic_cinematic import fixture
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_preparation_recipes import preparation_service


def source_config():
    config = configuration()
    config["references"] = [dict(asset_id="asset-image", role="unassigned", label="Sécheresse Corée")]
    config["intention"] = 'Un village en Corée. Ancien exemple : "thank you". Sans parole.'
    return config


def localized_config():
    source = source_config()
    return apply_preset(source, "little_men_experimental", source, name="Sécheresse Corée")


def speech_fixture(language="Korean", words="감사합니다!"):
    plan, _, context = fixture(mode="i2va", count=1)
    phase = deepcopy(plan["shots"][0]["phases"][0])
    phase["actions"] = [
        "The same giant hand places a plank over the gap.",
        "The hand presses the support into place; the plank remains fixed.",
        f"The hand withdraws and the little people say together <d>[{language}] {words}</d>",
    ]
    plan["shots"][0]["phases"] = [phase]
    plan["shots"][0]["duration_ms"] = 10000
    plan["spoken_lines"], plan["spoken_languages"] = [words], [language]
    writer = {"shots": [{"phases": [" ".join(phase["actions"])]}],
              "overall_soundscape": plan["overall_soundscape"],
              "non_diegetic_music": plan["non_diegetic_music"]}
    context.update(source_text=preparation_text(localized_config()), duration_ms=10000,
                   speech_policy=LOCALIZED_THANKS_V1, speech_language=None, dialogue_level=1)
    context.pop("locked_speech")
    return plan, writer, context


class ExperimentalLittleMenTest(unittest.TestCase):
    def test_preset_source_restoration_and_classic_remain_independent(self):
        source = source_config()
        original = deepcopy(source)
        config = apply_preset(source, "little_men_experimental", source, name="Corée")
        self.assertEqual(source, original)
        self.assertEqual(config["render"]["settings"]["duration_seconds"], 10)
        self.assertEqual(config["references"][0]["role"], "first_frame")
        self.assertEqual(config["shot_count"], 1)
        self.assertTrue(config["dlss"]["enabled"])
        self.assertEqual((config["social"]["language"], config["social"]["variant_count"]), ("en", 3))
        config["little_men_language"] = "Korean"
        classic_config = apply_preset(config, "little_men", source)
        self.assertEqual(classic_config["render"]["settings"]["duration_seconds"], 8)
        self.assertIn('disent en anglais : "thank you"', classic_config["intention"])
        self.assertEqual(classic_config["little_men_language"], "auto")
        self.assertEqual(apply_preset(config, "source", source), original)

    def test_geographical_context_does_not_create_a_spoken_ledger(self):
        config = localized_config()
        config["little_men_context"] += '\n«France» “Merci” "Seoul"'
        before = deepcopy(config)
        text = preparation_text(config)
        self.assertIn("Corée", text)
        self.assertEqual(extract_explicit_dialogues(text), ())
        self.assertEqual(config, before)
        config.update(preset="custom", little_men_language="French")
        config["render"]["settings"]["duration_seconds"] = 12
        text = preparation_text(config)
        self.assertIn("12 secondes", text)
        self.assertIn("Langue imposée pour le remerciement : French.", text)
        self.assertNotIn("8 secondes", text)
        config["intention"] = 'Les personnages disent en français : "Merci beaucoup !"'
        self.assertEqual(extract_explicit_dialogues(preparation_text(config)), ("Merci beaucoup !",))

    def test_legacy_configuration_and_invalid_language(self):
        config = source_config()
        config.pop("little_men_language")
        config.pop("little_men_context")
        validate_shape(config)
        config["little_men_language"] = "unsupported"
        with self.assertRaises(ValueError):
            validate_shape(config)

    def test_language_change_invalidates_preparation_but_keeps_source_and_ig(self):
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        item = service.receive([dict(name="Incendie France", config=source_config(),
                                     source={"kind": "image"})])["state"]["items"][0]
        identity = item["id"]
        service.update([identity], {identity: item["revision"]}, preset="little_men_experimental")
        saved = store.value["items"][0]
        self.assertIn("Un village en Corée", saved["config"]["little_men_context"])
        self.assertNotIn("Incendie France", saved["config"]["little_men_context"])
        saved["steps"]["plan"].update(status="succeeded", output={"text": "old plan"})
        saved["steps"]["prompt"].update(status="succeeded", output={"text": "old prompt"})
        saved["runtime"] = {"session_id": "old"}
        service = VideoFactoryService(store=store, adapter=adapter)
        result = service.update([identity], {identity: saved["revision"]},
                                changes={"little_men_language": "French"})
        changed = result["state"]["items"][0]
        self.assertEqual(changed["steps"]["plan"]["status"], "pending")
        self.assertEqual(changed["steps"]["prompt"]["status"], "pending")
        self.assertEqual(changed["runtime"], {})
        self.assertEqual(changed["config"]["preset_origin"], "little_men_experimental")
        self.assertEqual(changed["config"]["social"]["language"], "en")
        self.assertEqual(changed["source_config"], source_config())
        self.assertEqual(adapter.calls, [])
        self.assertEqual(result["state"]["thanks_languages"], THANKS_LANGUAGES)

    def test_adapter_passes_typed_policy_and_manual_language_without_extra_call(self):
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
                                   dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
        config = localized_config()
        config.update(preset="custom", little_men_language="Korean")
        item = new_item("Corée", config, {}, "key")
        item["runtime"]["session_id"] = "session"
        adapter._session(item, Mock(), lambda: False, Mock())
        intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        self.assertEqual((intent.speech_policy, intent.speech_language), (LOCALIZED_THANKS_V1, "Korean"))
        adapter.prompt_lab.stream_structure_brief.assert_not_called()
        adapter.composition.stream_generate.assert_not_called()

    def test_experimental_outputs_stay_in_little_men_family_after_customization(self):
        config = localized_config()
        config["preset"] = "custom"
        item = new_item("Corée", config, {"kind": "image"}, "key")
        item["status"] = "succeeded"
        item["steps"]["video"].update(status="succeeded", output={"asset_id": "asset-video"})
        item["steps"]["dlss"]["status"] = "skipped"
        self.assertEqual(delivery_material(item)["family"], "Petits hommes")


class LocalizedSpeechContractTest(unittest.TestCase):
    def test_legacy_intent_serialization_and_hash_are_unchanged(self):
        intent = PreparationIntent("A scene", creative_axes=CreativeFreedomAxes(1, 0, 1))
        saved = intent_to_dict(intent)
        self.assertNotIn("speech_policy", saved)
        self.assertEqual(intent_from_dict(saved), intent)
        snapshot = asdict(intent)
        snapshot.pop("speech_policy")
        snapshot.pop("speech_language")
        snapshot["creative_axes"].pop("dialogue")
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(preparation_source(None, NS(preparation_intent=intent)).source_id, "intent:" + digest)
        localized = replace(intent, speech_policy=LOCALIZED_THANKS_V1, speech_language="Korean")
        self.assertEqual(intent_from_dict(intent_to_dict(localized)), localized)
        self.assertNotEqual(preparation_source(None, NS(preparation_intent=localized)).source_id, "intent:" + digest)

    def test_localized_request_does_not_relax_other_vocal_policies(self):
        lines = (("Korean", "감사합니다!"),)
        with self.assertRaises(ValueError):
            validate_speech(lines, (), level=1, source_text="A scene")
        self.assertEqual(validate_speech(lines, (), level=1, source_text="A scene",
                                        speech_policy=LOCALIZED_THANKS_V1), ("감사합니다!",))
        for invalid in ((), lines + (("English", "Hello"),)):
            with self.assertRaises(ValueError):
                validate_speech(invalid, (), level=1, source_text="A scene",
                                speech_policy=LOCALIZED_THANKS_V1)
        with self.assertRaises(ValueError):
            validate_speech(lines, (), level=1, source_text="A scene",
                            speech_policy=LOCALIZED_THANKS_V1, speech_language="French")
        self.assertIn("Additions use [English]", vocal_policy(2))
        self.assertNotIn("Additions use [English]", vocal_policy(1, speech_policy=LOCALIZED_THANKS_V1))

    def test_compiler_preserves_native_words_and_resolved_language(self):
        for language, words in (("French", "Merci !"), ("Korean", "감사합니다!"), ("English", "Thank you!")):
            with self.subTest(language=language):
                plan, writer, context = speech_fixture(language, words)
                context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
                prompt, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
                saved = classic.decode_context(encoded)
                self.assertIn(f"<d>[{language}] {words}</d>", prompt)
                self.assertEqual(saved["speech_language"], language)
                self.assertEqual(saved["chosen_speech"], [words])
                self.assertEqual(len(saved["sequence_plan"]["shots"]), 1)
                with self.assertRaises(ValueError):
                    classic.validate_final(prompt.replace(words, "Changed words"), saved)
                if language != "English":
                    with self.assertRaises(ValueError):
                        classic.validate_final(prompt.replace(f"[{language}]", "[English]"), saved)
                    wrong_writer = deepcopy(writer)
                    wrong_writer["shots"][0]["phases"][0] = wrong_writer["shots"][0]["phases"][0].replace(f"[{language}]", "[English]")
                    with self.assertRaises(ValueError):
                        classic.compile_result(json.dumps(wrong_writer), classic.encode_context(context), "final_prompt")

    def test_two_calls_survive_reopening_with_language_and_gestures(self):
        with TemporaryDirectory() as directory:
            plan, writer, context = speech_fixture()
            service, gateway, session, composition = preparation_service(
                directory, "fl2va", "planned", [json.dumps(plan), json.dumps(writer)],
                source_text=context["source_text"], creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
                cinematic_settings=ClassicCinematicSettings(1))
            intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V1)
            service.configure(session.session_id, composition.cookbook.cookbook_id,
                              composition.cookbook.version, composition.bindings, preparation_intent=intent)
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            service.compositions = LocalPromptCompositionStore(directory)
            self.assertEqual(service.get(session.session_id).preparation_intent, intent)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            final = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision.content
            self.assertEqual(len(gateway.requests), 2)
            for request in gateway.requests:
                self.assertIn("REQUESTED LOCALIZED THANK-YOU v1", request.system_prompt)
                self.assertNotIn("Additions use [English]", request.system_prompt)
            self.assertIn("<d>[Korean] 감사합니다!</d>", final)
            self.assertLess(final.index("places a plank"), final.index("presses the support"))
            self.assertLess(final.index("presses the support"), final.index("감사합니다!"))


if __name__ == "__main__":
    unittest.main()
