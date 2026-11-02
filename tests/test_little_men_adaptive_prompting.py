"""User-run v7 context and prompting regressions; no model or render adapters."""
from panelforge.domain.little_men_objects import LEGACY_CATALOG_VERSION
from copy import deepcopy
import unittest

from panelforge.application import little_men_prompting
from panelforge.application.direct_ref2v_plan import extract_explicit_dialogues
from panelforge.application.vocal_policy import speech_lines, validate_speech, vocal_policy
from panelforge.domain.little_men_direction import (
    SCENE_CONTEXT_MARKER, SOLUTION_PLAN_POLICY_V7, SOLUTION_WRITER_POLICY_V7,
    preparation_text_v6, preparation_text_v7, scene_context_v7,
    writer_intention, writer_intention_v7,
)
from panelforge.domain.little_men_variety import (
    SELECTION_MARKER, make_variety_selection, selection_from_text,
    selection_instructions, selection_instructions_v7,
)
from panelforge.domain.localized_speech import (
    FIXED_THANKS, LOCALIZED_THANKS_V6, LOCALIZED_THANKS_V7,
    STABLE_THANKS_LANGUAGES,
)
from panelforge.domain.prompt_lab import CreativeFreedomAxes


def adaptive_source_fixture():
    config = {
        "render": {"settings": {"duration_seconds": 10}},
        "little_men_context": "Préserver l'effort déjà engagé.",
        "references": [{"asset_id": "asset-current", "role": "first_frame",
                        "scene_context": {
                            "asset_id": "asset-current", "origin": "PNG KREA / ComfyUI",
                            "intention": "Objectif initial : faciliter une tâche, sans urgence.",
                            "prompt": "Visible initial state and ongoing activity.",
                            "style": "Preserve the initial material treatment.",
                        }}],
    }
    selection = {
        "version": 7, "priority": list(STABLE_THANKS_LANGUAGES),
        "requested_language": None,
        "variety": make_variety_selection("adaptive-context-fixture", [], catalog_version=LEGACY_CATALOG_VERSION),
    }
    return config, selection


class AdaptiveContextTest(unittest.TestCase):
    def test_full_middle_context_is_plan_only_and_old_dialogue_is_not_protected(self):
        config, selection = adaptive_source_fixture()
        context = config["references"][0]["scene_context"]
        middle = "THE_ORIGINAL_GOAL_AND_WORLD_PROPERTY"
        context["prompt"] = ("Descriptive preface. " * 100 + middle
                             + " Descriptive continuation." * 100
                             + ' Anciennes paroles : «Fuyez !» "Stop!" '
                             + "<d>[English] An old line.</d>")
        config_before, selection_before = deepcopy(config), deepcopy(selection)
        source = "Aider les habitants dans leur activité actuelle."
        prepared = preparation_text_v7(config, source, selection)
        self.assertIn(middle, prepared)
        self.assertIn(context["intention"], prepared)
        self.assertIn(context["style"], prepared)
        self.assertIn(SCENE_CONTEXT_MARKER, prepared)
        self.assertEqual(extract_explicit_dialogues(prepared), ())
        self.assertEqual(speech_lines(prepared), ())
        self.assertEqual(selection_from_text(prepared), selection["variety"])
        writer = writer_intention_v7(prepared)
        self.assertIn(source, writer)
        for excluded in (middle, context["intention"], context["style"], SCENE_CONTEXT_MARKER,
                         SELECTION_MARKER, "mechanism_counts", "Frozen order", "An old line."):
            self.assertNotIn(excluded, writer)
        self.assertEqual(config, config_before)
        self.assertEqual(selection, selection_before)

    def test_only_context_bound_to_the_current_asset_is_used(self):
        config, selection = adaptive_source_fixture()
        config["references"][0]["scene_context"]["asset_id"] = "asset-previous"
        prepared = preparation_text_v7(config, "Une aide utile.", selection)
        self.assertNotIn("Objectif initial : faciliter", prepared)
        self.assertNotIn("Visible initial state", prepared)
        self.assertIn("Préserver l'effort déjà engagé.", prepared)

    def test_missing_metadata_is_not_an_error_and_user_instruction_is_preserved(self):
        config, selection = adaptive_source_fixture()
        config["little_men_context"] = ""
        config["references"][0].pop("scene_context")
        source = 'Une demande actuelle contenant "des mots exacts".'
        prepared = preparation_text_v7(config, source, selection)
        self.assertIn("l’image et la demande actuelle peuvent suffire", prepared)
        self.assertEqual(writer_intention_v7(prepared),
                         "Durée cible : 10 secondes. Un seul plan continu.\n\n" + source)

    def test_scene_context_obeys_existing_field_bounds(self):
        config, _ = adaptive_source_fixture()
        context = config["references"][0]["scene_context"]
        config["little_men_context"] = "M" * 2001
        context.update(intention="I" * 4001, prompt="P" * 12001, style="S" * 3001)
        text = scene_context_v7(config)
        for character, limit in (("M", 2000), ("I", 4000), ("P", 12000), ("S", 3000)):
            self.assertIn(character * limit, text)
            self.assertNotIn(character * (limit + 1), text)

    def test_v6_keeps_its_existing_writer_context_and_selection_contract(self):
        config, selection = adaptive_source_fixture()
        selection["version"] = 6
        prepared = preparation_text_v6(config, "Aider les habitants.", selection)
        self.assertNotIn(SCENE_CONTEXT_MARKER, prepared)
        self.assertIn(config["references"][0]["scene_context"]["intention"], writer_intention(prepared))
        self.assertIn("Identify the principal danger", selection_instructions(selection["variety"]))
        self.assertNotIn("Identify the principal danger", selection_instructions_v7(selection["variety"]))
        self.assertEqual(selection_from_text(prepared), selection["variety"])


class AdaptivePromptPolicyTest(unittest.TestCase):
    def test_aggregated_v7_instructions_do_not_reintroduce_mandatory_danger_or_human_benefit(self):
        _, selection = adaptive_source_fixture()
        axes = CreativeFreedomAxes(3, 1, 3, 1)
        instructions = "\n".join((
            little_men_prompting.system_prompt(writer=False, version=7),
            SOLUTION_PLAN_POLICY_V7,
            little_men_prompting.creative_policy(axes, 2, version=7),
            selection_instructions_v7(selection["variety"]),
            vocal_policy(1, speech_policy=LOCALIZED_THANKS_V7),
        ))
        for old_clause in ("Identify the principal danger", "this scene's actual danger",
                           "the necessary threat", "The danger stays active",
                           "after visibly benefiting from the solution", "without freezing",
                           "Material styling must not immobilize"):
            self.assertNotIn(old_clause, instructions)
        self.assertIn("threat=null", instructions)
        self.assertIn("needs_context", instructions)
        self.assertIn("The beneficiary need not be human", instructions)
        self.assertIn("static condition", instructions)
        self.assertIn("about one second", instructions)
        self.assertIn("no object-to-problem or mechanism mapping", instructions)

    def test_writer_preserves_choice_and_has_no_context_request_branch(self):
        writer = (little_men_prompting.system_prompt(writer=True, version=7)
                  + SOLUTION_WRITER_POLICY_V7
                  + vocal_policy(1, locked=True, speech_policy=LOCALIZED_THANKS_V7,
                                 speech_language="French"))
        self.assertIn("Keep a threat only when the approved contract contains one", writer)
        self.assertIn("The benefit persists", writer)
        self.assertIn("Do not choose again", writer)
        self.assertNotIn("needs_context", writer)
        self.assertIn("French: Merci", writer)
        self.assertNotIn("English: Thank you", writer)

    def test_v7_recognizes_all_eleven_fixed_formulas_and_rejects_old_v1_fallback(self):
        self.assertEqual(len(STABLE_THANKS_LANGUAGES), 11)
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                result = validate_speech(((language, words),), (), level=0, source_text="",
                    speech_policy=LOCALIZED_THANKS_V7, speech_language=language)
                self.assertEqual(result, (words,))
                with self.assertRaises(ValueError):
                    validate_speech(((language, words + " extra"),), (), level=0, source_text="",
                        speech_policy=LOCALIZED_THANKS_V7, speech_language=language)
        with self.assertRaises(ValueError):
            validate_speech((("Hindi", "Thanks"),), (), level=0, source_text="",
                            speech_policy=LOCALIZED_THANKS_V7)
        with self.assertRaises(ValueError):
            validate_speech((), (), level=0, source_text="", speech_policy=LOCALIZED_THANKS_V7)

    def test_v6_creative_and_vocal_directions_are_preserved(self):
        axes = CreativeFreedomAxes(3, 1, 3, 1)
        self.assertEqual(little_men_prompting.creative_policy(axes, 2),
                         little_men_prompting.creative_policy(axes, 2, version=6))
        self.assertIn("the necessary threat", little_men_prompting.creative_policy(axes, 2))
        old = vocal_policy(1, speech_policy=LOCALIZED_THANKS_V6)
        self.assertIn("LOCALIZED THANK-YOU v6", old)
        self.assertIn("after visibly benefiting from the solution", old)
        self.assertNotIn("needs_context", old)


if __name__ == "__main__":
    unittest.main()
