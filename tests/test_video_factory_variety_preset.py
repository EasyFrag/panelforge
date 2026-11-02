"""User-run regressions for the separate Petits hommes experimental preset."""
from panelforge.domain.little_men_objects import LEGACY_CATALOG_VERSION
from copy import deepcopy
import unittest

from panelforge.application.vocal_policy import validate_speech, vocal_policy
from panelforge.domain.little_men_direction import (
    SOLUTION_PLAN_POLICY_V5, SOLUTION_PLAN_POLICY_V6, writer_intention,
)
from panelforge.domain.little_men_languages import make_selection, recent_languages
from panelforge.domain.little_men_variety import (
    PRESET_ID, SELECTION_MARKER, is_variety, make_variety_selection, selection_from_text,
)
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V5, LOCALIZED_THANKS_V6
from panelforge.domain.video_factory import (
    LITTLE_MEN_EXPERIMENTAL_INTENT, LITTLE_MEN_EXPERIMENTAL_INTENT_V2,
    LITTLE_MEN_EXPERIMENTAL_INTENT_V3, LITTLE_MEN_EXPERIMENTAL_INTENT_V4,
    LITTLE_MEN_VARIETY_INTENT, LITTLE_MEN_ADAPTIVE_INTENT,
    LITTLE_MEN_STANDARD_INTENT, LITTLE_MEN_STANDARD_VARIETY_INTENT,
    PRESETS, apply_preset, configuration,
    current_experimental_intent, current_variety_intent, invalidate,
    is_experimental_little_men, new_item, preparation_text, stage_signature, validate_shape,
)


def source_config():
    config = configuration()
    config.update(intention="Un village miniature.")
    config["references"] = [{"asset_id": "asset-variety", "role": "unassigned", "label": "Village"}]
    return config


def variety_item(identity="variety-test"):
    source = source_config()
    config = apply_preset(source, PRESET_ID, source)
    config.update(little_men_direction_version=6, intention=LITTLE_MEN_VARIETY_INTENT)
    item = new_item("Village", config, source, identity)
    selected = make_selection(config, item["id"])
    selected["variety"] = make_variety_selection(item["id"], [], catalog_version=LEGACY_CATALOG_VERSION)
    item["runtime"]["thanks_selection"] = selected
    return item


class VarietyPresetTest(unittest.TestCase):
    def test_current_presets_remain_distinct_with_standard_h3_defaults(self):
        source = source_config()
        original = deepcopy(source)
        current = apply_preset(source, "little_men_experimental", source)
        experimental = apply_preset(source, PRESET_ID, source)
        self.assertEqual(source, original)
        self.assertEqual(PRESETS["little_men_experimental"], "Petits hommes")
        self.assertEqual(PRESETS[PRESET_ID], "Petits hommes experimental")
        self.assertEqual(current["intention"], LITTLE_MEN_STANDARD_INTENT)
        self.assertEqual(experimental["intention"], LITTLE_MEN_STANDARD_VARIETY_INTENT)
        self.assertEqual(current["little_men_direction_version"], 8)
        self.assertEqual(experimental["little_men_direction_version"], 8)
        self.assertEqual(make_selection(current, "current")["version"], 8)
        self.assertEqual(make_selection(experimental, "new")["version"], 8)
        for config in (current, experimental):
            validate_shape(config)
            self.assertTrue(is_experimental_little_men(config))
            self.assertEqual(config["render"]["settings"]["duration_seconds"], 10)
            self.assertEqual(config["shot_count"], 1)
            self.assertEqual(config["references"][0]["role"], "first_frame")
        self.assertFalse(is_variety(current))
        self.assertTrue(is_variety(experimental))
        custom = apply_preset(experimental, "custom", source)
        self.assertTrue(is_variety(custom))
        self.assertEqual(custom["little_men_direction_version"], 8)
        self.assertEqual(apply_preset(experimental, "source", source), source)

    def test_default_upgrade_is_opt_in_and_preserves_personal_intentions(self):
        for old in (LITTLE_MEN_EXPERIMENTAL_INTENT_V2, LITTLE_MEN_EXPERIMENTAL_INTENT_V3,
                    LITTLE_MEN_EXPERIMENTAL_INTENT_V4, LITTLE_MEN_EXPERIMENTAL_INTENT):
            with self.subTest(intention=old[:35]):
                self.assertEqual(current_variety_intent(old), LITTLE_MEN_VARIETY_INTENT)
                self.assertEqual(current_experimental_intent(old), LITTLE_MEN_EXPERIMENTAL_INTENT)
        custom = "Garder tous les habitants visibles pendant l’intervention."
        self.assertEqual(current_variety_intent(custom), custom)
        self.assertEqual(current_experimental_intent(custom), custom)

    def test_frozen_assortment_is_plan_only_and_resolved_choice_cannot_rewrite_input(self):
        item = variety_item()
        selection = item["runtime"]["thanks_selection"]
        original = deepcopy(selection)
        text = preparation_text(item["config"], thanks_selection=selection)
        self.assertEqual(selection_from_text(text), selection["variety"])
        self.assertEqual(selection, original)
        self.assertIn(SELECTION_MARKER, text)
        self.assertIn("LANGUAGE CHOICE — PLAN ONLY", text)
        self.assertNotIn(SELECTION_MARKER, writer_intention(text))
        self.assertNotIn("LANGUAGE CHOICE — PLAN ONLY", writer_intention(text))
        self.assertNotIn('"candidates"', writer_intention(text))
        resolved = {**selection, "language": "French", "words": "Merci",
                    "variety_choice": {"objects": [], "mechanism_family": "move",
                                       "departure_reason": "Direct contact is sufficient."}}
        self.assertEqual(preparation_text(item["config"], thanks_selection=resolved), text)
        self.assertEqual(SOLUTION_PLAN_POLICY_V5.count("or an object catalogue"), 1)
        self.assertNotIn("or an object catalogue", SOLUTION_PLAN_POLICY_V6)

    def test_v6_refuses_a_missing_frozen_assortment(self):
        item = variety_item()
        selection = item["runtime"]["thanks_selection"]
        selection.pop("variety")
        with self.assertRaisesRegex(ValueError, "assortiment"):
            preparation_text(item["config"], thanks_selection=selection)

    def test_version_markers_are_strict_and_distinguish_stage_signatures(self):
        item = variety_item()
        config = item["config"]
        for value in (True, "6", 6.0, 9):
            with self.subTest(marker=value), self.assertRaises(ValueError):
                validate_shape({**config, "little_men_direction_version": value})
        self.assertNotEqual(stage_signature(config, "plan"),
                            stage_signature({**config, "little_men_direction_version": 5}, "plan"))


class VarietySelectionLifecycleTest(unittest.TestCase):
    def test_switching_to_variety_keeps_resolved_language_but_requests_new_assortment(self):
        source = source_config()
        config = apply_preset(source, "little_men_experimental", source)
        config.update(little_men_direction_version=5, intention=LITTLE_MEN_EXPERIMENTAL_INTENT)
        item = new_item("Existing", config, source, "old-five")
        selected = make_selection(config, item["id"])
        selected.update(language="Japanese", words=FIXED_THANKS["Japanese"])
        item["runtime"].update(session_id="old-session", thanks_selection=selected)
        before = deepcopy(config)
        item["config"] = apply_preset(config, PRESET_ID, source)
        invalidate(item, before)
        upgraded = item["runtime"]["thanks_selection"]
        self.assertEqual(upgraded["version"], 8)
        self.assertEqual(upgraded["requested_language"], "Japanese")
        self.assertEqual(upgraded["words"], FIXED_THANKS["Japanese"])
        self.assertNotIn("variety", upgraded)
        self.assertNotIn("variety_choice", upgraded)
        self.assertNotIn("session_id", item["runtime"])
        self.assertEqual(selected["version"], 5)

    def test_switching_back_to_current_preset_removes_experimental_choices(self):
        item = variety_item()
        selection = item["runtime"]["thanks_selection"]
        selection.update(language="French", words="Merci", variety_choice={"objects": [],
            "mechanism_family": "move", "departure_reason": "Direct contact is sufficient."})
        before = deepcopy(item["config"])
        item["config"] = apply_preset(before, "little_men_experimental", item["source_config"])
        invalidate(item, before)
        saved = item["runtime"]["thanks_selection"]
        self.assertEqual(saved["version"], 8)
        self.assertEqual(saved["requested_language"], "French")
        self.assertNotIn("variety", saved)
        self.assertNotIn("variety_choice", saved)
        self.assertNotIn(SELECTION_MARKER, preparation_text(item["config"], thanks_selection=saved))

    def test_plan_invalidation_keeps_input_assortment_and_discards_its_old_output_choice(self):
        item = variety_item()
        item["runtime"]["thanks_selection"]["variety_choice"] = {"objects": [],
            "mechanism_family": "move", "departure_reason": "Direct contact is sufficient."}
        selected = deepcopy(item["runtime"]["thanks_selection"])
        before = deepcopy(item["config"])
        item["config"]["writer_model_id"] = "another-writer"
        invalidate(item, before)
        saved = item["runtime"]["thanks_selection"]
        self.assertEqual(saved["version"], 6)
        self.assertEqual(saved["variety"], selected["variety"])
        self.assertNotIn("variety_choice", saved)
        self.assertIn("variety_choice", selected)

    def test_language_change_discards_the_whole_previous_selection(self):
        item = variety_item()
        before = deepcopy(item["config"])
        item["config"]["little_men_language"] = "Japanese"
        invalidate(item, before)
        self.assertNotIn("thanks_selection", item["runtime"])

    def test_recent_language_balance_includes_current_and_variety_presets(self):
        varied = variety_item("varied")
        current = variety_item("current")
        current["config"] = apply_preset(current["config"], "little_men_experimental", current["source_config"])
        varied["runtime"]["thanks_selection"]["language"] = "Japanese"
        current["runtime"]["thanks_selection"]["language"] = "French"
        self.assertCountEqual(recent_languages([varied, current]), ["Japanese", "French"])
        self.assertEqual(recent_languages([varied, current], exclude=varied["id"]), ["French"])


class VarietyVocalPolicyTest(unittest.TestCase):
    def test_v6_preserves_all_eleven_brief_formulas_and_v5_delivery(self):
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                self.assertEqual(validate_speech(((language, words),), (), level=1, source_text="Scene",
                    speech_policy=LOCALIZED_THANKS_V6, speech_language=language), (words,))
                with self.assertRaises(ValueError):
                    validate_speech(((language, words + " " + words),), (), level=1, source_text="Scene",
                                    speech_policy=LOCALIZED_THANKS_V6, speech_language=language)
                v5 = vocal_policy(1, locked=True, speech_policy=LOCALIZED_THANKS_V5, speech_language=language)
                v6 = vocal_policy(1, locked=True, speech_policy=LOCALIZED_THANKS_V6, speech_language=language)
                self.assertEqual(v6, v5.replace("v5:", "v6:"))


if __name__ == "__main__":
    unittest.main()
