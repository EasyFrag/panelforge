"""User-run v7 contract regressions; fixtures only, no live model or render calls."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from panelforge.application import classic_cinematic as classic
from panelforge.application import little_men_causal as causal
from panelforge.domain.little_men_variety import OBJECTS
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V6, LOCALIZED_THANKS_V7
from tests.test_little_men_variety_contract import variety_fixture


def adaptive_fixture(language="French", *, threat=False):
    plan, _, context = variety_fixture(language)
    previous = plan.pop("help_contract")
    if threat:
        plan["help_contract"] = {
            "initial_goal": "Keep the occupied street usable by its inhabitants.",
            "help_need": previous["danger"],
            "beneficiary": "The inhabitants of the occupied street.",
            **{key: previous[key] for key in ("target", "mechanism", "lasting_result",
                                              "intervention", "resolution", "benefit", "thanks")},
            "benefit_description": previous["residents_benefit"],
            "initial_state": previous["active_threat"],
            "threat": {"description": previous["danger"], "evidence": previous["active_threat"]},
        }
    else:
        shot = plan["shots"][0]
        shot.update(
            opening_composition="An animal rests beside two rigid supports while miniature inhabitants steady them.",
            pacing="Allow a measured intervention and visible benefit, followed by brief natural thanks.",
            end_state="The animal moves freely beside the separated supports, with the same inhabitants nearby.",
            transition="The improved situation remains visible.",
        )
        shot["phases"][0].update(
            cue="The animal rests with its paw lodged between the supports.",
            camera={"motion": "static_shot", "amplitude": None, "speed": None, "target_clause": ""},
            actions=[
                "The animal rests with its paw lodged between two rigid supports; the inhabitants already steady both supports.",
                "The giant hand gently pulls one support sideways while the inhabitants keep the other steady.",
                "The supports separate under the hand's pull and the animal's paw comes free.",
                "The animal places its freed paw on the ground and walks comfortably beside the inhabitants.",
                "The hand withdraws while the inhabitants finish securing the separated supports.",
                f"The inhabitants watch the animal move freely and briefly say <d>[{language}] {FIXED_THANKS[language]}</d>.",
            ],
        )
        plan["continuity_invariants"] = [
            "Keep the same animal, inhabitants, supports and relative scale.",
            "The inhabitants' existing effort steadies the supports; the animal is the beneficiary, not an adversary.",
        ]
        plan["overall_soundscape"] = "Gentle contact against the supports, footsteps and the inhabitants' brief thanks."
        plan["help_contract"] = {
            "initial_goal": "Help the animal move its paw freely.",
            "help_need": "The supports hold the resting animal's paw while the inhabitants struggle to separate them.",
            "beneficiary": "The animal whose paw is lodged between the supports.",
            "target": "The gap between the two supports.",
            "mechanism": "Controlled lateral hand pressure separates the supports while the inhabitants steady them.",
            "lasting_result": "The supports remain separated and the animal's paw stays free.",
            "benefit_description": "The animal walks comfortably with its freed paw before the inhabitants thank the hand.",
            "initial_state": {"phase": 1, "action": 1},
            "threat": None,
            "intervention": [{"phase": 1, "action": 2}],
            "resolution": {"phase": 1, "action": 3},
            "benefit": {"phase": 1, "action": 4},
            "thanks": {"phase": 1, "action": 6},
        }
        plan["variety_choice"].update(
            mechanism_family="separate",
            departure_reason="Direct hand contact allows controlled separation while supporting the existing effort.",
        )
    context.update(speech_policy=LOCALIZED_THANKS_V7)
    return plan, causal.canonical_writer(plan), context


def canonical(plan, context):
    return json.loads(classic.canonical_plan(json.dumps(plan), context))


class AdaptiveSchemaTest(unittest.TestCase):
    def test_v7_exposes_complete_plan_or_strict_diagnostic_without_examples(self):
        schema = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V7))
        ready, diagnostic = schema["oneOf"]
        self.assertIn("help_contract", ready["required"])
        self.assertIn("variety_choice", ready["required"])
        self.assertIn("spoken_languages", ready["required"])
        self.assertEqual(ready["properties"]["shots"]["maxItems"], 1)
        self.assertEqual(set(diagnostic["required"]), {"status", "reason"})
        self.assertFalse(diagnostic["additionalProperties"])
        contract = schema["$defs"]["AdaptiveHelpContract"]
        self.assertIn("threat", contract["required"])
        self.assertIn({"type": "null"}, contract["properties"]["threat"]["anyOf"])
        self.assertNotIn("danger", contract["properties"])
        self.assertNotIn("residents_benefit", contract["properties"])
        self.assertNotIn("open box", json.dumps(schema))
        self.assertNotIn("lid reaches", json.dumps(schema))
        old = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V6))
        self.assertNotIn("oneOf", old)
        self.assertIn("danger", old["$defs"]["HelpContract"]["required"])

    def test_policy_does_not_silently_convert_historical_and_adaptive_contracts(self):
        new, _, context = adaptive_fixture()
        old, _, old_context = variety_fixture()
        with self.assertRaises(ValueError):
            canonical(new, old_context)
        with self.assertRaises(ValueError):
            canonical(old, context)
        self.assertEqual(classic.lint_document(json.dumps(new), "beat_sheet", "i2va"), ())
        self.assertEqual(classic.lint_document(json.dumps(old), "beat_sheet", "i2va"), ())


class AdaptiveCausalityTest(unittest.TestCase):
    def test_static_initial_state_and_nonhuman_beneficiary_need_no_threat(self):
        plan, _, context = adaptive_fixture()
        approved = canonical(plan, context)
        self.assertIsNone(approved["help_contract"]["threat"])
        self.assertEqual(approved["help_contract"], plan["help_contract"])
        self.assertEqual(approved["continuity_invariants"], plan["continuity_invariants"])
        self.assertEqual(approved["shots"][0]["duration_ms"], 10000)

    def test_established_threat_requires_description_and_evidence_before_intervention(self):
        plan, _, context = adaptive_fixture(threat=True)
        self.assertEqual(canonical(plan, context)["help_contract"]["threat"], plan["help_contract"]["threat"])
        for threat in (
            {"description": "The danger remains active."},
            {"description": "", "evidence": {"phase": 1, "action": 1}},
            {"description": "The danger remains active.", "evidence": {"phase": 1, "action": 2}},
            {"description": "The danger remains active.", "evidence": {"phase": 2, "action": 1}},
        ):
            with self.subTest(threat=threat), self.assertRaises(ValueError):
                altered = deepcopy(plan)
                altered["help_contract"]["threat"] = threat
                canonical(altered, context)

    def test_bad_references_order_duplicate_gestures_and_missing_need_are_rejected(self):
        plan, _, context = adaptive_fixture()
        for field, value in (
            ("initial_state", {"phase": 1, "action": 2}),
            ("initial_state", {"phase": 2, "action": 1}),
            ("resolution", {"phase": 1, "action": 1}),
            ("benefit", {"phase": 1, "action": 3}),
            ("thanks", {"phase": 1, "action": 5}),
            ("intervention", [{"phase": 1, "action": 2}, {"phase": 1, "action": 2}]),
            ("intervention", [{"phase": 1, "action": 3}, {"phase": 1, "action": 2}]),
            ("help_need", ""),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                altered = deepcopy(plan)
                altered["help_contract"][field] = value
                canonical(altered, context)

    def test_multiple_gestures_and_shared_final_benefit_are_accepted(self):
        plan, _, context = adaptive_fixture()
        plan["help_contract"]["intervention"].append({"phase": 1, "action": 3})
        plan["help_contract"]["benefit"] = {"phase": 1, "action": 6}
        approved = canonical(plan, context)
        self.assertEqual(len(approved["help_contract"]["intervention"]), 2)
        self.assertEqual(approved["help_contract"]["benefit"], approved["help_contract"]["thanks"])

    def test_contract_metadata_cannot_add_speech_or_action_tokens(self):
        plan, _, context = adaptive_fixture(threat=True)
        for field in ("initial_goal", "help_need", "beneficiary", "benefit_description"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                altered = deepcopy(plan)
                altered["help_contract"][field] += " <d>[French] Encore</d>"
                canonical(altered, context)
        plan["help_contract"]["threat"]["description"] += " [[help:1:1]]"
        with self.assertRaises(ValueError):
            canonical(plan, context)


class AdaptiveContextDiagnosticTest(unittest.TestCase):
    def test_context_request_stops_before_compilation_or_speech_validation(self):
        _, _, context = adaptive_fixture()
        value = {"status": "needs_context", "reason": "L'objectif de l'aide n'est pas identifiable dans cette scène."}
        with patch.object(classic, "_compile") as compiler, patch.object(classic, "validate_speech") as speech:
            with self.assertRaisesRegex(ValueError, "contexte à préciser"):
                classic.canonical_plan(json.dumps(value), context)
            compiler.assert_not_called()
            speech.assert_not_called()
        errors = classic.lint_document(json.dumps(value), "beat_sheet", "i2va")
        self.assertEqual(len(errors), 1)
        self.assertIn(value["reason"], errors[0])

    def test_diagnostic_never_accepts_a_partial_plan_or_empty_reason(self):
        _, _, context = adaptive_fixture()
        for value in (
            {"status": "needs_context", "reason": ""},
            {"status": "needs_context", "reason": "x" * 601},
            {"status": "needs_context", "reason": "Objectif manquant.", "spoken_lines": []},
            {"status": "needs_context", "reason": "Objectif manquant.", "shots": []},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                classic.canonical_plan(json.dumps(value), context)


class AdaptiveTransportTest(unittest.TestCase):
    def test_each_fixed_language_and_protected_action_survives_compilation(self):
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                plan, writer, context = adaptive_fixture(language)
                approved = canonical(plan, context)
                context["plan"] = approved
                final, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
                saved = classic.decode_context(encoded)
                self.assertEqual(saved["sequence_plan"], approved)
                self.assertEqual(saved["chosen_speech"], [words])
                self.assertEqual(final.count(f"<d>[{language}] {words}</d>"), 1)
                self.assertNotIn("[[help:", final)
                self.assertNotIn("help_contract", final)
                self.assertNotIn("variety_choice", final)
                for action in causal.protected_actions(approved).values():
                    self.assertEqual(final.count(action), 1)
                classic.validate_final(final, saved)
                changed = final.replace(approved["shots"][0]["phases"][0]["actions"][3], "The animal waits.")
                with self.assertRaises(ValueError):
                    classic.validate_final(changed, saved)

    def test_two_phases_keep_initial_state_benefit_and_thanks_references(self):
        plan, _, context = adaptive_fixture()
        first = plan["shots"][0]["phases"][0]
        second = deepcopy(first)
        first["actions"], second["actions"] = first["actions"][:3], second["actions"][3:]
        second["cue"] = "The paw is free and the animal resumes movement."
        plan["shots"][0]["phases"] = [first, second]
        plan["help_contract"].update(benefit={"phase": 2, "action": 1}, thanks={"phase": 2, "action": 3})
        writer = causal.canonical_writer(plan)
        self.assertIn("Petits hommes v7", causal.writer_instructions(plan))
        context["plan"] = canonical(plan, context)
        final, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertNotIn("[[help:", final)
        self.assertEqual(classic.decode_context(saved)["sequence_plan"]["help_contract"], plan["help_contract"])
        writer["shots"][0]["phases"][0] = writer["shots"][0]["phases"][0].replace("[[help:1:1]]", "")
        with self.assertRaises(ValueError):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")

    def test_assortment_traceability_and_umbrella_ban_apply_to_adaptive_contract(self):
        plan, _, context = adaptive_fixture()
        with self.assertRaisesRegex(ValueError, "assortiment"):
            canonical(plan, {key: value for key, value in context.items() if key != "variety_selection"})
        identity = context["variety_selection"]["candidates"][0]
        name = OBJECTS[identity]["name"]
        plan["variety_choice"].update(objects=[{"catalog_id": identity, "name": name}], departure_reason=None)
        with self.assertRaisesRegex(ValueError, "action d’intervention"):
            canonical(plan, context)
        plan["shots"][0]["phases"][0]["actions"][1] = (
            f"The giant hand uses the {name} to separate the supports while the inhabitants steady them.")
        self.assertEqual(canonical(plan, context)["variety_choice"]["objects"][0]["catalog_id"], identity)
        plan["variety_choice"].update(objects=[{"catalog_id": None, "name": "umbrella"}],
                                      departure_reason="Its surface would cover the animal.")
        plan["shots"][0]["phases"][0]["actions"][1] = "The giant hand opens an umbrella above the animal."
        with self.assertRaisesRegex(ValueError, "parapluie"):
            canonical(plan, context)


if __name__ == "__main__":
    unittest.main()
