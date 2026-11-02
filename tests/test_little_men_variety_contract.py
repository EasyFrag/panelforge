"""User-run contracts for the optional experimental Petits hommes preset."""
from panelforge.domain.little_men_objects import LEGACY_CATALOG_VERSION
from copy import deepcopy
import json
import unittest

from panelforge.application import classic_cinematic as classic
from panelforge.application import little_men_causal as causal
from panelforge.application import little_men_prompting as prompting
from panelforge.domain.little_men_variety import MECHANISM_FAMILIES, OBJECTS, make_variety_selection
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V5, LOCALIZED_THANKS_V6
from tests.test_little_men_causal import causal_fixture


def variety_fixture(language="French", *, object_id=None):
    plan, _, context = causal_fixture(language)
    selection = make_variety_selection("contract-fixture", [], catalog_version=LEGACY_CATALOG_VERSION)
    plan["variety_choice"] = {"objects": [], "mechanism_family": "redirect",
                              "departure_reason": "Direct contact gives the hand precise control of the moving target."}
    context.update(speech_policy=LOCALIZED_THANKS_V6, variety_selection=selection)
    if object_id is not None:
        put_object(plan, object_id)
        if object_id not in selection["candidates"]:
            plan["variety_choice"]["departure_reason"] = "This object's geometry provides the contact the target requires."
    return plan, causal.canonical_writer(plan), context


def put_object(plan, object_id, *, name=None):
    name = OBJECTS[object_id]["name"] if name is None else name
    plan["variety_choice"].update(objects=[{"catalog_id": object_id, "name": name}], departure_reason=None)
    plan["shots"][0]["phases"][0]["actions"][1] = (
        f"The giant hand presses the {name} against the animal's flank, steadily directing it away from the buildings.")
    plan["help_contract"]["mechanism"] = (
        f"The {name} transmits lateral pressure from the giant hand to redirect the animal away from the occupied street.")


def canonical(plan, context):
    return json.loads(classic.canonical_plan(json.dumps(plan), context))


class VarietySchemaTest(unittest.TestCase):
    def test_v6_schema_is_explicit_and_v5_remains_strict(self):
        old = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V5))
        new = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V6))
        self.assertNotIn("variety_choice", old["properties"])
        self.assertIn("variety_choice", new["required"])
        self.assertIn("help_contract", new["required"])
        self.assertEqual(new["properties"]["shots"]["maxItems"], 1)
        families = new["$defs"]["VarietyChoice"]["properties"]["mechanism_family"]["enum"]
        self.assertEqual(set(families), set(MECHANISM_FAMILIES))
        self.assertNotIn("open box", json.dumps(new))
        self.assertNotIn("lid reaches", json.dumps(new))
        plan, _, context = variety_fixture()
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(plan), {**context, "speech_policy": LOCALIZED_THANKS_V5})
        plan.pop("variety_choice")
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(plan), context)

    def test_lint_infers_both_contracts_without_requiring_private_assortment(self):
        v5, _, _ = causal_fixture()
        v6, _, _ = variety_fixture()
        for plan in (v5, v6):
            self.assertEqual(classic.lint_document(json.dumps(plan), "beat_sheet", "i2va"), ())
        v6["variety_choice"]["mechanism_family"] = "solve_the_problem"
        self.assertTrue(classic.lint_document(json.dumps(v6), "beat_sheet", "i2va"))

    def test_v6_compilation_requires_frozen_assortment(self):
        plan, _, context = variety_fixture()
        context.pop("variety_selection")
        with self.assertRaisesRegex(ValueError, "assortiment"):
            canonical(plan, context)
        for selection in ({}, {"catalog_version": "future", "candidates": ["unknown"]}):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                canonical(plan, {**context, "variety_selection": selection})


class VarietyChoiceTest(unittest.TestCase):
    def test_direct_hand_and_outside_objects_require_a_reason(self):
        plan, _, context = variety_fixture()
        canonical(plan, context)
        plan["variety_choice"]["departure_reason"] = None
        with self.assertRaises(ValueError):
            canonical(plan, context)
        choice = {"objects": [{"catalog_id": None, "name": "woven copper cradle"}],
                  "mechanism_family": "support", "departure_reason": None}
        with self.assertRaises(ValueError):
            causal.VarietyChoice.model_validate(choice)
        choice["departure_reason"] = "Its fitted shape supports the target without displacing the inhabitants."
        self.assertIsNone(causal.VarietyChoice.model_validate(choice).objects[0].catalog_id)

    def test_candidate_choice_is_valid_and_canonical_name_must_match(self):
        plan, _, context = variety_fixture()
        identity = context["variety_selection"]["candidates"][0]
        put_object(plan, identity)
        saved = canonical(plan, context)
        self.assertEqual(saved["variety_choice"], plan["variety_choice"])
        plan["variety_choice"]["objects"][0]["name"] = "different object"
        with self.assertRaises(ValueError):
            canonical(plan, context)
        plan["variety_choice"]["objects"][0]["catalog_id"] = "invented_catalog_id"
        with self.assertRaises(ValueError):
            canonical(plan, context)

    def test_exact_known_name_without_id_is_resolved_without_guessing(self):
        plan, _, context = variety_fixture()
        identity = next(identity for identity in OBJECTS if identity not in context["variety_selection"]["candidates"])
        put_object(plan, identity, name=OBJECTS[identity]["name"].upper())
        plan["variety_choice"]["objects"][0]["catalog_id"] = None
        with self.assertRaises(ValueError):
            canonical(plan, context)
        plan["variety_choice"]["departure_reason"] = "The selected contact surface suits this target better than the proposed assortment."
        saved = canonical(plan, context)
        self.assertEqual(saved["variety_choice"]["objects"][0]["catalog_id"], identity)
        self.assertIsNone(plan["variety_choice"]["objects"][0]["catalog_id"])
        unknown = causal.ChosenObject.model_validate({"catalog_id": None, "name": "custom woven copper cradle"})
        self.assertIsNone(unknown.catalog_id)

    def test_objects_must_be_used_in_referenced_actions_and_declared_once(self):
        plan, _, context = variety_fixture()
        identity = context["variety_selection"]["candidates"][0]
        name = OBJECTS[identity]["name"]
        plan["variety_choice"].update(objects=[{"catalog_id": identity, "name": name}], departure_reason=None)
        with self.assertRaisesRegex(ValueError, "action d’intervention"):
            canonical(plan, context)
        put_object(plan, identity)
        plan["variety_choice"]["objects"].append(deepcopy(plan["variety_choice"]["objects"][0]))
        with self.assertRaises(ValueError):
            canonical(plan, context)

    def test_case_and_simple_plural_do_not_hide_a_used_object(self):
        plan, _, context = variety_fixture()
        identity = next(identity for identity in OBJECTS if OBJECTS[identity]["name"].endswith("comb"))
        put_object(plan, identity)
        name = OBJECTS[identity]["name"]
        plan["shots"][0]["phases"][0]["actions"][1] = (
            f"The giant hand presses two {name.upper()}S against the animal's flank, directing it away from the buildings.")
        plan["variety_choice"]["departure_reason"] = "Its contact surface suits the target."
        canonical(plan, context)

    def test_mechanism_frequency_is_soft_and_never_a_compulsory_rotation(self):
        plan, _, context = variety_fixture()
        context["variety_selection"]["mechanism_counts"]["redirect"] = 50
        saved = canonical(plan, context)
        self.assertEqual(saved["variety_choice"]["mechanism_family"], "redirect")
        plan["variety_choice"]["mechanism_family"] = "rescue"
        with self.assertRaises(ValueError):
            canonical(plan, context)

    def test_an_outside_object_cannot_reintroduce_an_umbrella(self):
        plan, _, context = variety_fixture()
        plan["variety_choice"]["objects"] = [{"catalog_id": None, "name": "umbrella"}]
        plan["shots"][0]["phases"][0]["actions"][1] = "The hand uses an umbrella to press the animal away."
        with self.assertRaises(ValueError):
            canonical(plan, context)


class VarietyPromptTransportTest(unittest.TestCase):
    def test_native_speech_and_choices_survive_compilation_and_revision_context(self):
        for language in ("French", "Japanese", "Arabic"):
            with self.subTest(language=language):
                plan, writer, context = variety_fixture(language)
                approved = canonical(plan, context)
                context["plan"] = approved
                output, encoded = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
                saved = classic.decode_context(encoded)
                self.assertEqual(saved["sequence_plan"], approved)
                self.assertEqual(saved["variety_selection"], context["variety_selection"])
                self.assertNotIn("variety_choice", output)
                self.assertNotIn("[[help:", output)
                for action in causal.protected_actions(approved).values():
                    self.assertEqual(output.count(action), 1)
                classic.validate_final(output, saved)
                with self.assertRaises(ValueError):
                    classic.validate_final(output.replace(approved["shots"][0]["phases"][0]["actions"][1], "The hand waits."), saved)

    def test_v6_prompting_preserves_v5_and_keeps_assortment_out_of_writer(self):
        for writer in (False, True):
            self.assertEqual(prompting.system_prompt(writer=writer), prompting.system_prompt(writer=writer, version=5))
        planner = prompting.system_prompt(writer=False, version=6)
        writer = prompting.system_prompt(writer=True, version=6)
        self.assertIn("variety_choice", planner)
        self.assertIn("without a quota", planner)
        self.assertIn("departure_reason", planner)
        self.assertIn("Do not choose again", writer)
        self.assertNotIn("EXPERIMENTAL VARIETY CONTRACT", writer)
        plan, _, _ = variety_fixture()
        self.assertIn("Petits hommes v6", causal.writer_instructions(plan))


if __name__ == "__main__":
    unittest.main()
