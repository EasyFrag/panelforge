"""User-run regressions: language balance, frozen provenance and retry stability.

All services are fake or temporary. No model, renderer or production media used.
"""
from copy import deepcopy
import json
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application import classic_cinematic as classic
from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.application.vocal_policy import validate_speech, vocal_policy
from panelforge.domain.localized_speech import (
    LOCALIZED_THANKS_V1, LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4, STABLE_THANKS_LANGUAGES, THANKS_LANGUAGES, FIXED_THANKS,
)
from panelforge.domain.little_men_languages import (
    LANGUAGE_POOLS, classify_context, make_selection, recent_languages, selection_instructions,
)
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.video_factory import (
    apply_preset, configuration, invalidate, new_item, preparation_text, validate_shape,
)
from panelforge.infrastructure.factory_image_context import FactoryImageContext
from panelforge.infrastructure.krea2_image_metadata import recover_krea2_metadata, recover_krea2_scene_context
from panelforge.infrastructure.storage.prompt_compositions import intent_from_dict, intent_to_dict
from tests.test_video_factory import FakeWorkflows, MemoryStore


def config_for(context="", image_context=None):
    source = configuration()
    source["references"] = [dict(asset_id="asset-image", role="unassigned", label="Titre français")]
    config = apply_preset(source, "little_men_experimental", source)
    config["little_men_context"] = context
    if image_context:
        config["references"][0]["scene_context"] = dict(asset_id="asset-image", origin="PNG KREA",
            prompt=image_context.get("prompt", ""), intention=image_context.get("intention", ""),
            style=image_context.get("style", ""))
    return config


def png(graph):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + b"\x00" * 4
    return b"\x89PNG\r\n\x1a\n" + chunk(b"tEXt", b"prompt\x00" + json.dumps(graph).encode()) + chunk(b"IEND", b"")


def caption_graph(country="Japon", prompt="A Japanese mountain scene", project="krea2-create-test", attempt="attempt-first"):
    payload = dict(schema_version=1, prompt="Style: wool. " + prompt, canonical_prompt=prompt,
                   assisted_creation=dict(project_id=project, attempt_id=attempt, intention="Pays : " + country),
                   art_direction=dict(name="Wool", prompt="A wool diorama"))
    # IDs deliberately differ from production: only explicit node contracts matter.
    return {"text-value": dict(class_type="PrimitiveStringMultiline", inputs=dict(value=prompt)),
            "encoder": dict(class_type="CLIPTextEncode", inputs=dict(text=["text-value", 0])),
            "save-result": dict(class_type="SaveImageKJ", inputs=dict(caption=json.dumps(payload)))}


class LanguageSelectionTest(unittest.TestCase):
    def test_all_eleven_have_an_explicit_scene_context(self):
        cases = {"French": "France", "English": "United Kingdom", "German": "Allemagne",
                 "Italian": "Italie", "Spanish": "Espagne", "Portuguese": "Portugal",
                 "Russian": "Russie", "Chinese": "Chine", "Korean": "Corée", "Japanese": "Japon",
                 "Arabic": "Algérie"}
        self.assertEqual(set(cases), set(STABLE_THANKS_LANGUAGES))
        self.assertEqual(len(THANKS_LANGUAGES), 12)  # Auto plus eleven.
        for language, country in cases.items():
            with self.subTest(language=language):
                selected = make_selection(config_for("Pays : " + country), "fiche", [language] * 50)
                self.assertEqual(selected["requested_language"], language)

    def test_east_asia_includes_japanese_and_portuguese_is_not_eastern_europe(self):
        self.assertEqual(set(LANGUAGE_POOLS["east_asia"]), {"Chinese", "Korean", "Japanese"})
        self.assertEqual(classify_context("Une ambiance Europe de l’Est")[1], ("Russian",))
        self.assertIn("Portuguese", classify_context("Une architecture ibérique")[1])
        self.assertEqual(classify_context("Brazil")[1], ("Portuguese",))

    def test_balances_each_ambiguous_pool_without_leaving_it(self):
        for label, group in (("Asie", "east_asia"), ("Europe occidentale", "western_europe"),
                             ("Europe du Sud", "southern_europe"), ("Europe", "europe")):
            with self.subTest(group=group):
                recent = []
                for index in range(len(LANGUAGE_POOLS[group]) * 2):
                    choice = make_selection(config_for(label), f"fiche-{index}", recent)
                    recent.append(choice["language"])
                self.assertEqual(set(recent), set(LANGUAGE_POOLS[group]))
                self.assertTrue(all(recent.count(language) == 2 for language in LANGUAGE_POOLS[group]))

    def test_precise_location_precedes_desert_and_generic_style(self):
        choice = make_selection(config_for(image_context={
            "intention": "Pays : États-Unis\nUn désert", "prompt": "A sandy landscape",
            "style": "Asian diorama"}), "fiche")
        self.assertEqual(choice["language"], "English")
        choice = make_selection(config_for("Une ambiance européenne", {
            "prompt": "A Japanese mountain scene"}), "fiche")
        self.assertEqual(choice["language"], "Japanese")

    def test_manual_language_precedes_all_scene_evidence(self):
        config = config_for("Pays : Japon", {"intention": "Pays : Algérie"})
        config["little_men_language"] = "Korean"
        self.assertEqual(make_selection(config, "fiche")["language"], "Korean")

    def test_no_country_inferred_from_french_title_or_prompt_language(self):
        choice = make_selection(config_for(), "fiche", ["English"] * 10)
        self.assertIsNone(choice["requested_language"])
        self.assertEqual(choice["group"], "visual")
        self.assertNotEqual(choice["priority"][0], "English")
        self.assertIsNone(classify_context("English prompt. Titre en français. A tiny bridge."))
        self.assertEqual(set(choice["priority"]), set(STABLE_THANKS_LANGUAGES))

    def test_repeatable_draw_and_prompt_do_not_change_after_visual_resolution(self):
        config = config_for()
        first = make_selection(config, "fiche", ["English", "French"])
        self.assertEqual(first, make_selection(config, "fiche", ["English", "French"]))
        frozen_text = preparation_text(config, thanks_selection=first)
        resolved = {**first, "language": "Japanese", "words": "ありがとう！"}
        self.assertEqual(preparation_text(config, thanks_selection=resolved), frozen_text)
        self.assertIn(", ".join(first["priority"]), selection_instructions(first))

    def test_model_edit_keeps_resolved_language_context_edit_releases_it(self):
        config = config_for()
        item = new_item("Image", config, {}, "key")
        item["runtime"]["thanks_selection"] = {**make_selection(config, item["id"]), "language": "Korean"}
        before = deepcopy(config)
        item["config"]["plan_model_id"] = "another-model"
        invalidate(item, before)
        self.assertEqual(item["runtime"]["thanks_selection"]["requested_language"], "Korean")
        before = deepcopy(item["config"])
        item["config"]["little_men_context"] = "Pays : Japon"
        invalidate(item, before)
        self.assertNotIn("thanks_selection", item["runtime"])

    def test_recent_count_includes_reserved_rows_and_legacy_plans_once(self):
        rows = []
        for index, language in enumerate(("Korean", "French")):
            item = new_item(str(index), config_for(), {}, str(index))
            item["steps"]["plan"]["output"] = {"text": json.dumps({"spoken_languages": [language]})}
            rows.append(item)
        rows[0]["runtime"]["thanks_selection"] = {"language": "Korean"}
        self.assertCountEqual(recent_languages(rows), ["Korean", "French"])
        self.assertEqual(recent_languages(rows, exclude=rows[0]["id"]), ["French"])


class ImageContextTest(unittest.TestCase):
    def test_assisted_caption_recovers_country_even_with_linked_encoder(self):
        image = png(caption_graph())
        context = recover_krea2_scene_context(image)
        self.assertEqual(context["intention"], "Pays : Japon")
        self.assertEqual(context["prompt"], "A Japanese mountain scene")
        self.assertIn("Japanese", recover_krea2_metadata(image).prompt)

    def test_bad_or_conflicting_metadata_is_ignored_without_execution(self):
        for content in (b"not PNG", png({"save": {"class_type": "SaveImageKJ",
                                               "inputs": {"caption": "__import__('os').system('bad')"}}})):
            self.assertEqual(recover_krea2_scene_context(content), {})
        graph = caption_graph()
        graph["other-output"] = caption_graph("France", "A French village")["save-result"]
        self.assertEqual(recover_krea2_scene_context(png(graph)), {})

    def test_exact_asset_selects_attempt_not_latest_project_prompt(self):
        assets, projects = Mock(), Mock()
        assets.read_bytes.return_value = png(caption_graph())
        first = NS(output_asset_id="asset-image", pre_flux_asset_id="asset-pre",
                   attempt_id="attempt-first", canonical_prompt="Original Japanese mountain",
                   prompt="Original", art_direction=None)
        last = NS(output_asset_id="asset-later", pre_flux_asset_id=None,
                  attempt_id="attempt-later", canonical_prompt="A French city", prompt="Later")
        projects.get.return_value = NS(attempts=[first, last], intention="Pays : France")
        provider = FactoryImageContext(assets=assets, projects=projects)
        context = provider("asset-image", "krea2-create-test")
        self.assertEqual(context["prompt"], "Original Japanese mountain")
        self.assertEqual(context["intention"], "Pays : Japon")
        self.assertNotIn("France", json.dumps(context))
        self.assertEqual(provider("asset-pre", "krea2-create-test")["intention"], "Pays : Japon")

    def test_mismatched_caption_does_not_override_known_attempt(self):
        assets, projects = Mock(), Mock()
        assets.read_bytes.return_value = png(caption_graph("France", "French town", attempt="attempt-wrong"))
        projects.get.return_value = NS(attempts=[NS(output_asset_id="asset-image",
            attempt_id="attempt-right", canonical_prompt="A Japanese mountain", prompt="Image", art_direction=None)])
        context = FactoryImageContext(assets=assets, projects=projects)("asset-image", "krea2-create-test")
        self.assertEqual(context["intention"], "")
        self.assertIn("Japanese", context["prompt"])

    def test_png_import_without_project_and_without_metadata(self):
        assets, projects = Mock(), Mock()
        provider = FactoryImageContext(assets=assets, projects=projects)
        assets.read_bytes.return_value = png(caption_graph("Algérie", "Algerian desert"))
        self.assertEqual(provider("asset-image")["intention"], "Pays : Algérie")
        projects.get.assert_not_called()
        assets.read_bytes.return_value = b"ordinary JPEG"
        self.assertEqual(provider("asset-other")["origin"], "none")

    def test_stale_or_oversized_reference_context_is_rejected(self):
        config = config_for(image_context={"intention": "Pays : Japon"})
        validate_shape(config)
        config["references"][0]["scene_context"]["asset_id"] = "asset-wrong"
        with self.assertRaises(ValueError):
            validate_shape(config)


class FactoryLanguageLifecycleTest(unittest.TestCase):
    def test_frozen_choice_is_saved_before_plan_and_survives_service_restart(self):
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        item = service.receive([dict(name="Image", config=config_for("Pays : Japon"),
                                     source={"kind": "image", "id": "source"})])["state"]["items"][0]
        service.launch([item["id"]], {item["id"]: item["revision"]})
        service._execute("local_gpu", item["id"], "plan")
        saved = store.value["items"][0]
        self.assertEqual(saved["runtime"]["thanks_selection"]["language"], "Japanese")
        reopened = VideoFactoryService(store=store, adapter=adapter).snapshot()["items"][0]
        self.assertEqual(reopened["runtime"]["thanks_selection"], saved["runtime"]["thanks_selection"])

    def test_old_started_session_keeps_legacy_policy_without_new_draw(self):
        store, adapter = MemoryStore(), FakeWorkflows()
        config = config_for()
        item = new_item("Old", config, {}, "key")
        item["runtime"]["session_id"] = "legacy-session"
        item["status"] = "active"
        store.value["items"] = [item]
        service = VideoFactoryService(store=store, adapter=adapter)
        service._execute("local_gpu", item["id"], "plan")
        self.assertNotIn("thanks_selection", store.value["items"][0]["runtime"])

    def test_duplicate_of_old_row_recovers_context_without_changing_original(self):
        class ContextAdapter(FakeWorkflows):
            def enrich_image_context(self, config, source):
                config = deepcopy(config)
                config["references"][0]["scene_context"] = dict(asset_id="asset-image", origin="PNG",
                    prompt="A Japanese scene", intention="Pays : Japon", style="")
                return config
        store = MemoryStore()
        old = new_item("Old image", config_for(), {"kind": "image", "id": "project"}, "key")
        old["status"] = "succeeded"
        store.value["items"] = [old]
        service = VideoFactoryService(store=store, adapter=ContextAdapter())
        service.action("duplicate", [old["id"]], {old["id"]: old["revision"]})
        original, duplicate = store.value["items"]
        self.assertNotIn("scene_context", original["config"]["references"][0])
        self.assertEqual(make_selection(duplicate["config"], duplicate["id"])["language"], "Japanese")

    def test_context_enrichment_is_captured_once_per_reference(self):
        provider = Mock(return_value=dict(asset_id="asset-image", origin="PNG KREA",
            prompt="A Korean village", intention="Pays : Corée", style="Wool"))
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=None, dlss=None,
            social=None, episodes=None, assets=None, coordinator=None, image_context=provider)
        config = adapter.enrich_image_context(config_for(), {"id": "project"})
        again = adapter.enrich_image_context(config, {"id": "project"})
        self.assertEqual(config, again)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(make_selection(config, "fiche")["language"], "Korean")

    def test_adapter_passes_frozen_language_to_both_preparation_calls(self):
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
        config = config_for("Pays : Japon")
        item = new_item("Image", config, {}, "key")
        selection = make_selection(config, item["id"])
        item["runtime"].update(session_id="session", thanks_selection=selection)
        adapter._session(item, Mock(), lambda: False, Mock())
        first = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        item["runtime"]["thanks_selection"] = {**selection, "words": "ありがとう！"}
        adapter._session(item, Mock(), lambda: False, Mock())
        second = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        self.assertEqual(first, second)
        self.assertEqual((first.speech_policy, first.speech_language), (LOCALIZED_THANKS_V4, "Japanese"))
        adapter.composition.stream_generate.assert_not_called()
        adapter.prompt_lab.stream_structure_brief.assert_not_called()


class LanguagePolicyCompatibilityTest(unittest.TestCase):
    def test_v2_accepts_minimal_formulas_in_all_eleven_languages(self):
        examples = {
            "French": "Merci !", "Korean": "감사합니다!", "English": "thank you.",
            "Spanish": "¡Gracias!", "Japanese": "ありがとう！", "German": "Danke!",
            "Italian": "Grazie!", "Portuguese": "Obrigado!", "Russian": "Спасибо!",
            "Chinese": "谢谢！", "Arabic": "شكراً!",
        }
        self.assertEqual(set(examples), set(STABLE_THANKS_LANGUAGES))
        for language, words in examples.items():
            with self.subTest(language=language):
                self.assertEqual(validate_speech(((language, words),), (), level=1, source_text="Scene",
                    speech_policy=LOCALIZED_THANKS_V2, speech_language=language), (words,))

    def test_v2_rejects_additions_even_when_short_or_previously_locked(self):
        examples = [
            ("English", "Thank you, kind hand."),
            ("French", "Merci beaucoup !"),
            ("English", "Thank you! Thank you!"),
            ("Japanese", "ありがとう、優しい手！"),
            ("Chinese", "谢谢你的帮助"),
            ("Arabic", "شكرا لك"),
            ("Korean", "Thank you"),
        ]
        for language, words in examples:
            for locked in (None, (words,)):
                with self.subTest(language=language, words=words, locked=locked):
                    with self.assertRaisesRegex(ValueError, "sans aucun ajout"):
                        validate_speech(((language, words),), (), level=1, source_text="Scene",
                            speech_policy=LOCALIZED_THANKS_V2, speech_language=language, locked=locked)

    def test_v2_instructions_supply_fixed_words_for_selected_or_unknown_language(self):
        automatic = vocal_policy(1, speech_policy=LOCALIZED_THANKS_V2)
        self.assertEqual(set(FIXED_THANKS), set(STABLE_THANKS_LANGUAGES))
        for language, words in FIXED_THANKS.items():
            self.assertIn(f"{language}: {words}", automatic)
        self.assertNotIn("At most 12 words", automatic)
        manual = vocal_policy(1, speech_policy=LOCALIZED_THANKS_V2, speech_language="English")
        self.assertIn("English: Thank you", manual)
        self.assertNotIn("French: Merci", manual)
        words = "Thank you, kind hand."
        self.assertEqual(validate_speech((("English", words),), (), level=1, source_text="Scene",
            speech_policy=LOCALIZED_THANKS_V1), (words,))

    def test_v2_compiler_blocks_extended_thanks_in_plan_and_final_prompt(self):
        from tests.test_video_factory_experimental import speech_fixture
        plan, writer, context = speech_fixture("English", "Thank you, kind hand.")
        context.update(speech_policy=LOCALIZED_THANKS_V2, speech_language="English")
        with self.assertRaisesRegex(ValueError, "sans aucun ajout"):
            classic.canonical_plan(json.dumps(plan), context)
        # A saved permissive Plan cannot bypass the rule during compilation.
        context["plan"] = plan
        with self.assertRaisesRegex(ValueError, "sans aucun ajout"):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        plan, writer, context = speech_fixture("English", "Thank you!")
        context.update(speech_policy=LOCALIZED_THANKS_V2, speech_language="English")
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        prompt, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        with self.assertRaises(ValueError):
            classic.validate_final(prompt.replace("Thank you!", "Thank you, kind hand."),
                                   classic.decode_context(encoded))

    def test_v2_compiler_keeps_native_words_and_language_through_writer(self):
        from tests.test_video_factory_experimental import speech_fixture
        plan, writer, context = speech_fixture("Japanese", "ありがとう！")
        context.update(speech_policy=LOCALIZED_THANKS_V2, speech_language="Japanese")
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        prompt, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertIn("<d>[Japanese] ありがとう！</d>", prompt)
        self.assertEqual(classic.decode_context(encoded)["speech_language"], "Japanese")
        with self.assertRaises(ValueError):
            classic.validate_final(prompt.replace("[Japanese]", "[English]"), classic.decode_context(encoded))

    def test_v2_supersedes_only_the_exact_legacy_language_paragraph(self):
        from panelforge.domain.video_factory import _LEGACY_THANKS_INSTRUCTIONS
        config = config_for("Pays : Japon")
        config["intention"] = "Deux gestes utiles. " + _LEGACY_THANKS_INSTRUCTIONS + "Remercier à la fin."
        original = deepcopy(config)
        legacy = preparation_text(config)
        current = preparation_text(config, thanks_selection={**make_selection(config, "fiche"), "version": 2})
        self.assertIn("choisir l’anglais", legacy)
        self.assertNotIn("choisir l’anglais", current)
        self.assertIn("Deux gestes utiles.", current)
        self.assertIn("Langue imposée pour le remerciement : Japanese", current)
        self.assertEqual(config, original)

    def test_v2_serializes_and_rejects_unsupported_speech_while_v1_reopens(self):
        intent = PreparationIntent("Scene", speech_policy=LOCALIZED_THANKS_V2, speech_language="Japanese")
        self.assertEqual(intent_from_dict(intent_to_dict(intent)), intent)
        with self.assertRaises(ValueError):
            PreparationIntent("Scene", speech_policy=LOCALIZED_THANKS_V2, speech_language="Hindi")
        legacy = PreparationIntent("Scene", speech_policy=LOCALIZED_THANKS_V1, speech_language="Hindi")
        self.assertEqual(intent_from_dict(intent_to_dict(legacy)), legacy)
        with self.assertRaises(ValueError):
            validate_speech((("Hindi", "धन्यवाद"),), (), level=1, source_text="Scene",
                            speech_policy=LOCALIZED_THANKS_V2)
        self.assertIn("first eligible language", vocal_policy(1, speech_policy=LOCALIZED_THANKS_V2))
        self.assertIn("English for uncertain", vocal_policy(1, speech_policy=LOCALIZED_THANKS_V1))


if __name__ == "__main__":
    unittest.main()
