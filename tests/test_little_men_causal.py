"""User-run v5 contracts with local fixtures only; no model or render calls."""
from copy import deepcopy
import json
import unittest

from panelforge.application import classic_cinematic as classic
from panelforge.application import little_men_causal as causal
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V4, LOCALIZED_THANKS_V5
from tests.test_classic_cinematic import fixture
from tests.test_video_factory_experimental import speech_fixture


def causal_fixture(language="French", words=None):
    words = FIXED_THANKS[language] if words is None else words
    plan, _, context = fixture(mode="i2va", count=1, source="Un plan continu de dix secondes, aide aux petits hommes.")
    shot = plan["shots"][0]
    shot["duration_ms"] = 10000
    shot["opening_composition"] = "A miniature street contains the same inhabitants, a large animal and fragile buildings."
    shot["phases"] = [deepcopy(shot["phases"][0])]
    shot["phases"][0]["cue"] = "The animal begins moving from its initial position."
    shot["phases"][0]["actions"] = [
        "The animal advances into the narrow street, pressing against the occupied buildings as inhabitants retreat.",
        "The giant hand reaches the animal's flank and applies steady lateral pressure away from the buildings.",
        "The animal turns away under the hand's pressure and moves clear of the buildings, ending the contact.",
        "The inhabitants return to the cleared street and resume carrying their belongings through it.",
        "The hand rises out of the scene while the animal stays beyond the occupied street.",
        f"The inhabitants continue their activity and briefly say together <d>[{language}] {words}</d>.",
    ]
    shot["pacing"] = "The threat continues during the hand's approach; intervention and use take most of the time, with a brief final thanks."
    shot["end_state"] = "The occupied street remains clear, the inhabitants use it freely, and the hand is gone."
    shot["transition"] = "The result remains visible at the end."
    plan["continuity_invariants"] = ["Keep the inhabitants, animal, buildings and their relative scale recognizable."]
    plan["spoken_lines"], plan["spoken_languages"] = [words], [language]
    plan["overall_soundscape"] = "Footsteps, building creaks and the hand's contact, ending in the inhabitants' short thanks."
    plan["non_diegetic_music"] = "N/A"
    plan["help_contract"] = {
        "danger": "The moving animal threatens the occupied street and presses its buildings.",
        "target": "The animal's path next to the inhabitants and their buildings.",
        "mechanism": "Direct lateral pressure redirects the animal away from the occupied street.",
        "lasting_result": "The animal stays outside the street after the hand leaves.",
        "residents_benefit": "The inhabitants use the cleared street again before thanking.",
        "active_threat": {"phase": 1, "action": 1},
        "intervention": [{"phase": 1, "action": 2}],
        "resolution": {"phase": 1, "action": 3},
        "benefit": {"phase": 1, "action": 4},
        "thanks": {"phase": 1, "action": 6},
    }
    context.update(duration_ms=10000, dialogue_level=1, speech_policy=LOCALIZED_THANKS_V5,
                   speech_language=language)
    context.pop("locked_speech", None)
    return plan, causal.canonical_writer(plan), context


def compiled_causal(language="French"):
    plan, writer, context = causal_fixture(language)
    context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
    final, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
    return plan, writer, final, classic.decode_context(encoded)


class CausalPlanTest(unittest.TestCase):
    def test_plan_lint_accepts_v5_and_checks_its_action_contract(self):
        plan, _, _ = causal_fixture()
        self.assertEqual(classic.lint_document(json.dumps(plan), "beat_sheet", "i2va"), ())
        plan["help_contract"]["benefit"] = {"phase": 1, "action": 2}
        self.assertTrue(classic.lint_document(json.dumps(plan), "beat_sheet", "i2va"))
        legacy, _, _ = speech_fixture("French", "Merci")
        self.assertEqual(classic.lint_document(json.dumps(legacy), "beat_sheet", "i2va"), ())

    def test_schema_is_opt_in_without_canned_object_examples(self):
        old = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V4))
        new = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V5))
        self.assertNotIn("help_contract", old["properties"])
        self.assertIn("help_contract", new["required"])
        self.assertEqual(new["properties"]["shots"]["maxItems"], 1)
        self.assertNotIn("open box", json.dumps(new))
        self.assertNotIn("lid reaches", json.dumps(new))
        self.assertIn("open box", json.dumps(old))

    def test_contract_requires_real_references_and_causal_order(self):
        plan, _, context = causal_fixture()
        for field, bad in (
            ("active_threat", {"phase": 2, "action": 1}),
            ("resolution", {"phase": 1, "action": 1}),
            ("benefit", {"phase": 1, "action": 2}),
            ("thanks", {"phase": 1, "action": 5}),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                changed = deepcopy(plan)
                changed["help_contract"][field] = bad
                classic.canonical_plan(json.dumps(changed), context)
        changed = deepcopy(plan)
        changed.pop("help_contract")
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(changed), context)

    def test_one_or_multiple_useful_gestures_without_tool_requirement(self):
        for gestures in ([2], [2, 3]):
            with self.subTest(gestures=gestures):
                plan, _, context = causal_fixture()
                plan["help_contract"]["intervention"] = [{"phase": 1, "action": a} for a in gestures]
                saved = json.loads(classic.canonical_plan(json.dumps(plan), context))
                self.assertEqual(saved["help_contract"], plan["help_contract"])
        for gestures in ([3, 2], [2, 2]):
            with self.subTest(gestures=gestures), self.assertRaises(ValueError):
                plan, _, context = causal_fixture()
                plan["help_contract"]["intervention"] = [{"phase": 1, "action": a} for a in gestures]
                classic.canonical_plan(json.dumps(plan), context)

    def test_benefit_must_exist_before_thanks_and_only_last_action_speaks(self):
        plan, _, context = causal_fixture()
        plan["shots"][0]["phases"][0]["actions"][1] += " <d>[French] Merci</d>"
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(plan), context)

    def test_legacy_plan_without_causal_contract_keeps_compilation(self):
        plan, writer, context = speech_fixture("French", "Merci")
        context["speech_policy"] = LOCALIZED_THANKS_V4
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        final, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertIn("<d>[French] Merci</d>", final)
        self.assertNotIn("help_contract", classic.decode_context(saved)["sequence_plan"])


class CausalWriterTest(unittest.TestCase):
    def test_two_continuous_phases_preserve_action_references_and_speech(self):
        plan, _, context = causal_fixture()
        first = plan["shots"][0]["phases"][0]
        second = deepcopy(first)
        first["actions"], second["actions"] = first["actions"][:3], second["actions"][3:]
        second["cue"] = "The danger is resolved and the inhabitants begin using the result."
        plan["shots"][0]["phases"] = [first, second]
        plan["help_contract"]["benefit"] = {"phase": 2, "action": 1}
        plan["help_contract"]["thanks"] = {"phase": 2, "action": 3}
        writer = causal.canonical_writer(plan)
        self.assertIn("[[help:2:3]]", writer["shots"][0]["phases"][1])
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        final, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertNotIn("[[help:", final)
        self.assertEqual(final.count("<d>[French] Merci</d>"), 1)
        self.assertEqual(classic.decode_context(saved)["sequence_plan"]["help_contract"], plan["help_contract"])

    def test_compilation_preserves_each_causal_action_once_and_removes_tokens(self):
        for language in ("French", "Japanese", "Arabic"):
            with self.subTest(language=language):
                plan, _, final, context = compiled_causal(language)
                self.assertNotIn("[[help:", final)
                self.assertEqual(context["sequence_plan"]["help_contract"], plan["help_contract"])
                cursor = 0
                for action in plan["shots"][0]["phases"][0]["actions"]:
                    self.assertEqual(final.count(action), 1)
                    cursor = final.index(action, cursor) + len(action)
                self.assertEqual(context["chosen_speech"], [FIXED_THANKS[language]])

    def test_writer_missing_reordered_repeated_or_wrong_phase_token_is_rejected(self):
        plan, writer, context = causal_fixture()
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        original = writer["shots"][0]["phases"][0]
        changes = (
            original.replace("[[help:1:3]]", ""),
            original.replace("[[help:1:2]] [[help:1:3]]", "[[help:1:3]] [[help:1:2]]"),
            original + " [[help:1:4]]",
            original.replace("[[help:1:2]]", "[[help:2:2]]"),
            original.replace("[[help:1:2]]", "[[help:bad]]"),
            original + " " + plan["shots"][0]["phases"][0]["actions"][0],
        )
        for prose in changes:
            with self.subTest(prose=prose), self.assertRaises(ValueError):
                changed = deepcopy(writer)
                changed["shots"][0]["phases"][0] = prose
                classic.compile_result(json.dumps(changed), classic.encode_context(context), "final_prompt")

    def test_saved_sequence_plan_is_indexed_for_subsequent_writer_revision(self):
        plan, writer, original, context = compiled_causal()
        context["plan"] = context["sequence_plan"]
        self.assertEqual(len(context["plan"]["shots"][0]["phases"][0]["actions"]), 6)
        self.assertIn("[[help:1:6]]", causal.writer_instructions(context["plan"]))
        revised, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertEqual(revised, original)
        self.assertEqual(classic.decode_context(saved)["sequence_plan"]["help_contract"], plan["help_contract"])

    def test_manual_final_edit_cannot_lose_or_reorder_protected_actions(self):
        plan, _, final, context = compiled_causal()
        action = plan["shots"][0]["phases"][0]["actions"][3]
        for changed in (final.replace(action, "The people merely watch."), final + " " + action):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                classic.validate_final(changed, context)

    def test_localized_delivery_is_preserved_without_voiceover_retargeting(self):
        plan, _, context = causal_fixture()
        context["source_text"] += '\nInhabitants (voix off) : "Merci"'
        action = "The inhabitants, still busy, say softly and naturally <d>[French] Merci</d>."
        plan["shots"][0]["phases"][0]["actions"][-1] = action
        writer = causal.canonical_writer(plan)
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        final, _ = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertEqual(final.count(action), 1)
        self.assertNotIn("off-screen voiceover", final)

    def test_plan_writer_and_final_all_reject_positive_umbrella(self):
        plan, writer, context = causal_fixture()
        changed = deepcopy(plan)
        changed["shots"][0]["phases"][0]["actions"][1] = "The hand opens an umbrella above the animal."
        with self.assertRaisesRegex(ValueError, "parapluie"):
            classic.canonical_plan(json.dumps(changed), context)
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        writer["shots"][0]["phases"][0] += " The hand also carries a transparent umbrella."
        with self.assertRaisesRegex(ValueError, "parapluie"):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        _, _, final, saved = compiled_causal()
        with self.assertRaisesRegex(ValueError, "parapluie"):
            classic.validate_final(final + " A parasol stays nearby.", saved)


class UmbrellaGuardTest(unittest.TestCase):
    def test_explicit_absence_and_organizational_meaning_are_allowed(self):
        for text in (
            "No umbrella is present.", "No transparent umbrella is used.",
            "The hand works without an umbrella.", "Do not use any umbrella.",
            "Umbrellas are forbidden.", "Aucun parapluie.", "Pas de parapluie.",
            "Sans ombrelle.", "Ne pas utiliser un parasol.",
            "No umbrellas or parasols.", "Umbrellas and parasols are forbidden.",
            "Aucun parapluie ni ombrelle.",
            "An umbrella organization coordinates the teams.",
        ):
            with self.subTest(text=text):
                causal.validate_no_umbrella(text)

    def test_positive_mentions_and_distant_negations_are_rejected(self):
        for text in (
            "The hand opens a transparent umbrella.", "La main pose une ombrelle.",
            "A parasol covers the area.", "Une main tient un parapluie.", "手拿着雨伞。",
            "No umbrella at first; later the hand opens an umbrella.",
            "No umbrella, but the hand opens a parasol.",
            "No rain reaches the umbrella.", "Without moving the umbrella, the hand rises.",
            "The hand is not without an umbrella.",
            "The hand plants a parasol banned in the intention.",
            "The hand opens an umbrella absent from the first frame.",
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "parapluie"):
                causal.validate_no_umbrella(text)


if __name__ == "__main__":
    unittest.main()
