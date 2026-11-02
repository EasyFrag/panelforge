"""User-run regressions for Petits hommes on the standard H3 contract.

Fixtures only. No live model, generation or service is used by this suite.
"""
from copy import deepcopy
import json
import unittest

from panelforge.application import classic_cinematic as classic
from panelforge.domain.little_men_direction import SCENE_CONTEXT_MARKER
from panelforge.domain.little_men_variety import OBJECTS
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V8, LOCALIZED_THANKS_VARIETY_V8
from tests.test_little_men_adaptive_contract import adaptive_fixture


def standard_fixture(language="Portuguese", *, variety=False):
    plan, _, context = adaptive_fixture(language)
    plan.pop("help_contract")
    if variety:
        context["speech_policy"] = LOCALIZED_THANKS_VARIETY_V8
    else:
        plan.pop("variety_choice")
        context.pop("variety_selection", None)
        context["speech_policy"] = LOCALIZED_THANKS_V8
    return plan, ordinary_writer(plan), context


def ordinary_writer(plan):
    return {
        "shots": [{"phases": [" ".join(phase["actions"]) for phase in shot["phases"]]}
                  for shot in plan["shots"]],
        "overall_soundscape": plan["overall_soundscape"],
        "non_diegetic_music": plan["non_diegetic_music"],
    }


def canonical(plan, context):
    return json.loads(classic.canonical_plan(json.dumps(plan), context))


def add_object(plan, identity):
    name = OBJECTS[identity]["name"]
    plan["variety_choice"].update(
        objects=[{"catalog_id": identity, "name": name}], departure_reason=None)
    plan["shots"][0]["phases"][0]["actions"][1] = (
        f"The giant hand uses the {name} to move one support sideways while the inhabitants hold the other steady.")
    return name


class StandardHelpContractTest(unittest.TestCase):
    def test_normal_schema_is_standard_and_variety_adds_only_its_choice(self):
        normal = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_V8))
        baseline = json.loads(classic.schema("beat_sheet"))
        self.assertEqual(normal, baseline)
        varied = json.loads(classic.schema("beat_sheet", speech_policy=LOCALIZED_THANKS_VARIETY_V8))
        self.assertEqual(set(varied["properties"]), set(normal["properties"]) | {"variety_choice"})
        self.assertIn("variety_choice", varied["required"])
        for schema in (normal, varied):
            self.assertNotIn("oneOf", schema)
            self.assertNotIn("help_contract", json.dumps(schema))
            self.assertNotIn("ActionRef", schema["$defs"])
            self.assertEqual(schema["$defs"]["Camera"], baseline["$defs"]["Camera"])

    def test_quiet_help_compiles_with_ordinary_writer_and_no_protected_action_tokens(self):
        for variety in (False, True):
            with self.subTest(variety=variety):
                plan, writer, context = standard_fixture(variety=variety)
                context["plan"] = canonical(plan, context)
                # Ordinary Writer prose may paraphrase the approved subject action.
                original = plan["shots"][0]["phases"][0]["actions"][1]
                rephrased = "The giant hand carefully shifts one support sideways while the inhabitants steady the other."
                writer["shots"][0]["phases"][0] = writer["shots"][0]["phases"][0].replace(original, rephrased)
                final, encoded = classic.compile_result(
                    json.dumps(writer), classic.encode_context(context), "final_prompt")
                self.assertIn(rephrased, final)
                self.assertEqual(final.count("<d>[Portuguese] Obrigado</d>"), 1)
                self.assertNotIn("[[help:", final)
                saved = classic.decode_context(encoded)
                self.assertNotIn("little_men_causal_actions", saved)
                self.assertEqual(saved["sequence_plan"], context["plan"])
                classic.validate_final(final, saved)

    def test_explicit_policy_rejects_old_contract_instead_of_guessing_from_fields(self):
        old, _, old_context = adaptive_fixture()
        with self.assertRaises(ValueError):
            canonical(old, {**old_context, "speech_policy": LOCALIZED_THANKS_VARIETY_V8})
        plan, _, context = standard_fixture(variety=True)
        with self.assertRaises(ValueError):
            canonical(plan, {**context, "speech_policy": LOCALIZED_THANKS_V8})
        with self.assertRaises(ValueError):
            canonical(plan, {**context, "speech_policy": old_context["speech_policy"]})
        self.assertEqual(classic.lint_document(json.dumps(plan), "beat_sheet", "i2va"), ())
        self.assertEqual(classic.lint_document(json.dumps(old), "beat_sheet", "i2va"), ())

    def test_shared_speech_and_camera_validation_stays_strict(self):
        plan, _, context = standard_fixture()
        for bad in ("<d>Portuguese Obrigado</d>", "<d>Portuguese</d>Obrigado</d>"):
            with self.subTest(speech=bad), self.assertRaises(ValueError):
                changed = deepcopy(plan)
                changed["shots"][0]["phases"][0]["actions"][-1] = "The inhabitants say " + bad
                canonical(changed, context)
        changed = deepcopy(plan)
        changed["shots"][0]["phases"][0]["camera"].update(
            motion="push.in", amplitude="small", speed="slow", target_clause="the resting animal")
        with self.assertRaises(ValueError):
            canonical(changed, context)

    def test_old_image_shot_count_does_not_override_video_count_in_auto(self):
        plan, _, context = standard_fixture()
        context["settings"] = {"shot_count": None}
        context["source_text"] = (
            "Show the requested help in one continuous shot lasting ten seconds."
            + SCENE_CONTEXT_MARKER + "Previous video instructions: in three shots lasting twelve seconds.")
        self.assertEqual(len(canonical(plan, context)["shots"]), 1)

    def test_umbrella_stays_banned_in_plan_and_manual_final_prompt(self):
        for variety in (False, True):
            with self.subTest(variety=variety):
                plan, writer, context = standard_fixture(variety=variety)
                changed = deepcopy(plan)
                changed["shots"][0]["phases"][0]["actions"][1] = "The hand opens an umbrella above the inhabitants."
                with self.assertRaisesRegex(ValueError, "parapluie"):
                    canonical(changed, context)
                context["plan"] = canonical(plan, context)
                final, encoded = classic.compile_result(
                    json.dumps(writer), classic.encode_context(context), "final_prompt")
                with self.assertRaisesRegex(ValueError, "parapluie"):
                    classic.validate_final(final + " The giant hand opens an umbrella.", classic.decode_context(encoded))


class StandardVarietyChoiceTest(unittest.TestCase):
    def test_choice_requires_frozen_assortment_at_compilation_but_not_context_free_lint(self):
        plan, _, context = standard_fixture(variety=True)
        self.assertEqual(classic.lint_document(json.dumps(plan), "beat_sheet", "i2va"), ())
        missing = {key: value for key, value in context.items() if key != "variety_selection"}
        with self.assertRaisesRegex(ValueError, "assortiment"):
            canonical(plan, missing)

    def test_selected_accessory_must_be_named_in_actions_not_only_in_choice_metadata(self):
        plan, _, context = standard_fixture(variety=True)
        identity = context["variety_selection"]["candidates"][0]
        name = add_object(plan, identity)
        accepted = canonical(plan, context)
        self.assertEqual(accepted["variety_choice"]["objects"][0]["catalog_id"], identity)
        plan["shots"][0]["phases"][0]["actions"][1] = "The giant hand moves one support sideways."
        plan["continuity_invariants"].append("The selected accessory is the " + name + ".")
        with self.assertRaises(ValueError):
            canonical(plan, context)

    def test_direct_hand_or_outside_assortment_requires_an_explanation(self):
        plan, _, context = standard_fixture(variety=True)
        canonical(plan, context)
        plan["variety_choice"]["departure_reason"] = None
        with self.assertRaises(ValueError):
            canonical(plan, context)
        identity = next(key for key in OBJECTS if key not in context["variety_selection"]["candidates"])
        add_object(plan, identity)
        with self.assertRaises(ValueError):
            canonical(plan, context)
        plan["variety_choice"]["departure_reason"] = "Its shape permits controlled contact with the support."
        self.assertEqual(canonical(plan, context)["variety_choice"], plan["variety_choice"])

    def test_writer_cannot_remove_the_accessory_recorded_for_variety(self):
        plan, _, context = standard_fixture(variety=True)
        identity = context["variety_selection"]["candidates"][0]
        name = add_object(plan, identity)
        context["plan"] = canonical(plan, context)
        writer = ordinary_writer(plan)
        final, encoded = classic.compile_result(
            json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertIn(name, final)
        with self.assertRaises(ValueError):
            classic.validate_final(final.replace(name, "another implement"), classic.decode_context(encoded))
        writer["shots"][0]["phases"][0] = writer["shots"][0]["phases"][0].replace(name, "another implement")
        with self.assertRaises(ValueError):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")


if __name__ == "__main__":
    unittest.main()
