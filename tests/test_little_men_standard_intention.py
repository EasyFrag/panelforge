"""User-run v8 intention regressions; no model or rendering adapters."""
from copy import deepcopy
import unittest

from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.application.vocal_policy import speech_lines, validate_speech, vocal_policy
from panelforge.domain.little_men_direction import (
    LITTLE_MEN_STANDARD_INTENT, LITTLE_MEN_STANDARD_VARIETY_INTENT,
    SCENE_CONTEXT_MARKER, preparation_text_v8, writer_intention_v8,
)
from panelforge.domain.little_men_variety import (
    PRESET_ID, SELECTION_MARKER, make_variety_selection, selection_from_text,
    selection_instructions_v8,
)
from panelforge.domain.localized_speech import FIXED_THANKS, STANDARD_HELP_POLICIES, STABLE_THANKS_LANGUAGES


def standard_intention_fixture(*, variety=False, language="Portuguese"):
    config = {
        "preset": PRESET_ID if variety else "little_men_experimental",
        "little_men_direction_version": 8,
        "render": {"settings": {"duration_seconds": 10}},
        "little_men_context": "Respecter les efforts actuels.",
        "references": [{
            "asset_id": "asset-current", "role": "first_frame",
            "scene_context": {
                "asset_id": "asset-current",
                "intention": "IMAGE_GOAL: aider le bénéficiaire sans urgence.",
                "prompt": 'IMAGE_DESCRIPTION. Durée : 12 secondes. <d>[English] Run away</d> «Stop!»',
                "style": "IMAGE_STYLE",
            },
        }],
    }
    selection = {"version": 8, "requested_language": language, "language": language,
                 "priority": list(STABLE_THANKS_LANGUAGES)}
    if variety:
        selection["variety"] = make_variety_selection("standard-intention-fixture", [])
    return config, selection


class StandardIntentionTest(unittest.TestCase):
    def test_known_thanks_has_one_exact_tag_and_survives_writer_context_filter(self):
        config, selection = standard_intention_fixture()
        config_before, selection_before = deepcopy(config), deepcopy(selection)
        prepared = preparation_text_v8(config, LITTLE_MEN_STANDARD_INTENT, selection)
        self.assertEqual(speech_lines(prepared), (("Portuguese", "Obrigado"),))
        self.assertEqual(extract_explicit_dialogues(prepared), ())
        self.assertIn("Durée cible : 10 secondes", prepared)
        self.assertIn("IMAGE_GOAL", prepared)
        self.assertIn("IMAGE_DESCRIPTION", prepared)
        self.assertNotIn("Run away", prepared)
        self.assertNotIn(SELECTION_MARKER, prepared)
        writer = writer_intention_v8(prepared)
        self.assertIn(LITTLE_MEN_STANDARD_INTENT, writer)
        self.assertEqual(speech_lines(writer), (("Portuguese", "Obrigado"),))
        for excluded in (SCENE_CONTEXT_MARKER, "IMAGE_GOAL", "IMAGE_DESCRIPTION", "IMAGE_STYLE", "12 secondes"):
            self.assertNotIn(excluded, writer)
        self.assertEqual(config, config_before)
        self.assertEqual(selection, selection_before)

    def test_automatic_language_alternatives_never_become_requested_dialogue(self):
        config, selection = standard_intention_fixture(variety=True, language=None)
        prepared = preparation_text_v8(config, LITTLE_MEN_STANDARD_VARIETY_INTENT, selection)
        self.assertEqual(speech_lines(prepared), ())
        self.assertEqual(extract_explicit_dialogues(prepared), ())
        self.assertEqual(selection_from_text(prepared), selection["variety"])
        for language, words in FIXED_THANKS.items():
            self.assertIn(f"{language}: {words}", prepared)
        writer = writer_intention_v8(prepared)
        for excluded in (SELECTION_MARKER, "mechanism_counts", "Frozen order", "Authorized formulas"):
            self.assertNotIn(excluded, writer)
        self.assertNotIn("Portuguese: Obrigado", writer)
        # A resolved output must not change the frozen source of a running preparation.
        selection["language"] = "Japanese"
        self.assertEqual(preparation_text_v8(config, LITTLE_MEN_STANDARD_VARIETY_INTENT, selection), prepared)

    def test_context_for_a_different_asset_is_ignored_and_missing_context_is_allowed(self):
        config, selection = standard_intention_fixture()
        config["references"][0]["scene_context"]["asset_id"] = "asset-old"
        config["little_men_context"] = ""
        prepared = preparation_text_v8(config, "Une aide utile.", selection)
        self.assertNotIn("IMAGE_GOAL", prepared)
        self.assertNotIn("IMAGE_DESCRIPTION", prepared)
        self.assertIn("l’image et la demande actuelle peuvent suffire", prepared)

    def test_experimental_requires_its_frozen_assortment_but_normal_has_none(self):
        config, selection = standard_intention_fixture(variety=True)
        selection.pop("variety")
        with self.assertRaisesRegex(ValueError, "assortiment"):
            preparation_text_v8(config, LITTLE_MEN_STANDARD_VARIETY_INTENT, selection)
        config["preset"] = "little_men_experimental"
        prepared = preparation_text_v8(config, LITTLE_MEN_STANDARD_INTENT, selection)
        self.assertNotIn(SELECTION_MARKER, prepared)
        selection["requested_language"] = "Hindi"
        with self.assertRaisesRegex(ValueError, "11 langues"):
            preparation_text_v8(config, LITTLE_MEN_STANDARD_INTENT, selection)

    def test_variety_guidance_uses_standard_plan_fields_without_causal_contract(self):
        _, selection = standard_intention_fixture(variety=True)
        guidance = selection_instructions_v8(selection["variety"])
        self.assertIn("continuity_invariants", guidance)
        self.assertIn("variety_choice", guidance)
        self.assertIn("Direct hand action or another object remains valid", guidance)
        for obsolete in ("help_contract", "needs_context", "principal danger", "threat=null"):
            self.assertNotIn(obsolete, guidance)


class StandardSpeechPolicyTest(unittest.TestCase):
    def test_both_v8_presets_keep_exactly_the_generic_system_speech_policy(self):
        for policy in STANDARD_HELP_POLICIES:
            for locked in (False, True):
                with self.subTest(policy=policy, locked=locked):
                    self.assertEqual(
                        vocal_policy(1, locked=locked, speech_policy=policy, speech_language="Portuguese"),
                        vocal_policy(1, locked=locked))

    def test_localized_validation_remains_strict_without_a_specific_system_prompt(self):
        for policy in STANDARD_HELP_POLICIES:
            for language, words in FIXED_THANKS.items():
                with self.subTest(policy=policy, language=language):
                    self.assertEqual(validate_speech(((language, words),), (), level=0,
                        source_text="", speech_policy=policy, speech_language=language), (words,))
                    with self.assertRaises(ValueError):
                        validate_speech(((language, words + " extra"),), (), level=0,
                                        source_text="", speech_policy=policy, speech_language=language)
            for invalid in ((), (("Hindi", "Thanks"),), (("French", "Merci"), ("English", "Thank you"))):
                with self.subTest(policy=policy, invalid=invalid), self.assertRaises(ValueError):
                    validate_speech(invalid, (), level=0, source_text="", speech_policy=policy)
            with self.assertRaises(ValueError):
                validate_speech((("French", "Merci"),), (), level=0,
                                source_text="", speech_policy=policy, speech_language="Portuguese")


if __name__ == "__main__":
    unittest.main()
