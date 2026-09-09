"""Compatibility and frozen-behavior checks for the assistance recipe boundary."""

from dataclasses import replace
import hashlib
import unittest

from panelforge.application import krea2_assisted_v1 as v1, krea2_assisted_v2 as v2, krea2_assisted_v3 as v3
from panelforge.application.krea2_assisted import assistance_recipe
from panelforge.domain.krea2_assisted import (
    Krea2AssistedProject, Krea2AssistedTurn, Krea2AssistedTurnMode,
    Krea2AssistedTurnRole,
)
from panelforge.infrastructure.storage.krea2_assisted import _serialize, _deserialize


class AssistanceVersionTest(unittest.TestCase):
    def project(self):
        return Krea2AssistedProject(
            project_id="version-test", name="Dragon", intention="A dragon", model_id="local",
            turns=(Krea2AssistedTurn(
                turn_id="turn-1", mode=Krea2AssistedTurnMode.CREATION,
                role=Krea2AssistedTurnRole.USER, content="An egg",
            ),),
        )

    def test_legacy_projects_and_turns_resume_as_v1_and_round_trip(self):
        for schema in (1, 2):
            with self.subTest(schema=schema):
                value = _serialize(self.project())
                value["schema_version"] = schema
                value.pop("assistance_recipe_version")
                for turn in value["turns"]:
                    turn.pop("assistance_recipe_version")
                loaded = _deserialize(value)
                self.assertEqual(loaded.assistance_recipe_version, "1.0.0")
                self.assertEqual(loaded.turns[0].assistance_recipe_version, "1.0.0")
                saved = _serialize(loaded)
                self.assertEqual(saved["schema_version"], 7)
                self.assertEqual(_deserialize(saved), loaded)

    def test_versioned_records_do_not_silently_default_missing_reference(self):
        value = _serialize(self.project())
        value.pop("assistance_recipe_version")
        with self.assertRaises(KeyError):
            _deserialize(value)

    def test_unimplemented_recipe_is_never_redirected_to_v1(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            assistance_recipe("99.0.0")

    def test_system_prompts_match_pre_astra_snapshot(self):
        # Hashes obtained from snapshot commit b63197f, not from the new module.
        for mode, expected in (
            ("creation", "059ff12d25713234652000a729e3f9462922a72f21c56f388292c5f1be43f798"),
            ("recipe", "84a02068779f5fcd349945dae062fa52fb50086faeabc00fafb69939a0c1c3cf"),
        ):
            self.assertEqual(hashlib.sha256(v1.system_prompt(mode).encode()).hexdigest(), expected)

    def test_v1_keeps_recent_context_and_explicit_current_guidance(self):
        project = self.project()
        turns = tuple(replace(project.turns[0], turn_id=f"history-{i}", content=f"MESSAGE_{i:02d}") for i in range(16))
        project = replace(project, turns=turns)
        text = v1.user_prompt(project, "NEW", selected="RESULT", memory="RECIPES",
                              resources="MODELS", language_instruction="ENGLISH")
        self.assertNotIn("MESSAGE_01", text)
        self.assertIn("MESSAGE_02", text)
        self.assertIn("MESSAGE_14", text)
        self.assertNotIn("MESSAGE_15", text)
        self.assertIn("NEW USER MESSAGE (authoritative):\nNEW", text)
        self.assertIn("SELECTED GENERATED RESULT AND EXACT SETTINGS:\nRESULT", text)
        self.assertIn("No turn-specific guidance image.", text)

    def test_v3_changes_creation_without_rewriting_v2_or_publication(self):
        # V2 prompt inspected before adding V3, preserving the comparison baseline.
        self.assertEqual(
            hashlib.sha256(v2.system_prompt("creation").encode()).hexdigest(),
            "5255b494ea0908345c472b60ad8efb2b62a6fa2c0b780b19ad06ba1f100d504a",
        )
        self.assertIs(assistance_recipe("3.0.0"), v3)
        self.assertNotEqual(v3.system_prompt("creation"), v2.system_prompt("creation"))
        self.assertEqual(v3.system_prompt("recipe"), v2.system_prompt("recipe"))
        self.assertEqual(v3.MAX_TOKENS, v2.MAX_TOKENS)
