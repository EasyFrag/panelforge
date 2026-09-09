"""Offline regression cases for the experimental assistance context."""

from dataclasses import replace
from types import SimpleNamespace
import unittest

from panelforge.application import krea2_assisted_v1 as v1, krea2_assisted_v2 as v2
from panelforge.application.krea2_assisted import assistance_recipe, Krea2AssistedService
from panelforge.domain.krea2_assisted import (
    Krea2AssistedProject, Krea2AssistedTurn, Krea2AssistedTurnMode,
    Krea2AssistedTurnRole,
)
from panelforge.infrastructure.storage.krea2_assisted import _serialize, _deserialize


class Krea2AssistedV2Test(unittest.TestCase):
    def project(self):
        return Krea2AssistedProject(
            project_id="shoe", name="Shoe", intention="A glass shoe in the foreground",
            model_id="fake", current_prompt="A red glass shoe on a dark floor.",
            assistance_recipe_version="2.0.0",
            turns=(
                Krea2AssistedTurn("t1", Krea2AssistedTurnMode.CREATION,
                                 Krea2AssistedTurnRole.USER, "Keep the red glass."),
                Krea2AssistedTurn("t2", Krea2AssistedTurnMode.CREATION,
                                 Krea2AssistedTurnRole.ASSISTANT, "Glass retained.",
                                 prompt="OBSOLETE_PROMPT " * 40),
                Krea2AssistedTurn("t3", Krea2AssistedTurnMode.CREATION,
                                 Krea2AssistedTurnRole.USER, "Now put it on the floor.",
                                 assistance_recipe_version="2.0.0"),
            ),
        )

    def test_older_prompt_copies_are_removed_but_feedback_and_current_design_remain(self):
        arguments = dict(selected="None", memory="None", resources="None", language_instruction="English")
        new = v2.user_prompt(self.project(), "Now put it on the floor.", **arguments)
        old = v1.user_prompt(self.project(), "Now put it on the floor.", **arguments)
        self.assertNotIn("OBSOLETE_PROMPT", new)
        self.assertIn("Keep the red glass.", new)
        self.assertIn("A red glass shoe on a dark floor.", new)
        self.assertLess(len(new), len(old))

    def test_new_project_and_each_recorded_recipe_round_trip_without_rewriting_old_turns(self):
        project = self.project()
        loaded = _deserialize(_serialize(project))
        self.assertEqual(loaded, project)
        self.assertEqual(loaded.turns[0].assistance_recipe_version, "1.0.0")
        self.assertEqual(loaded.turns[-1].assistance_recipe_version, "2.0.0")
        self.assertIs(assistance_recipe("2.0.0"), v2)
        self.assertIs(assistance_recipe("1.0.0"), v1)

    def test_catalogues_are_requested_for_technical_advice_not_visual_corrections(self):
        self.assertFalse(v2.needs_resources("Make the shoe transparent and put it on the floor."))
        self.assertTrue(v2.needs_resources("Quel modèle et quelle force LoRA ?"))
        self.assertTrue(v2.needs_recipes("Utilise une recette publiée"))
        models = [SimpleNamespace(comfy_name=f"model_{i}") for i in range(20)]
        models.append(SimpleNamespace(comfy_name="glass_model"))
        text = v2.resource_memory(models, [], "glass")
        self.assertIn("glass_model", text)
        self.assertNotIn("model_19", text)
        self.assertIn("not an exhaustive inventory", text)

    def test_reference_is_not_confused_with_renderer_input_or_a_memory_rewind(self):
        prompt = v2.system_prompt("creation")
        self.assertIn("shoe, hand", prompt)
        self.assertIn("never inputs to this text-to-image renderer", prompt)
        self.assertIn("Selecting an old result does not rewind", prompt)
        self.assertIn("Replacing a scene state removes incompatible previous states", prompt)

    def test_visual_chat_does_not_fetch_catalogues_or_make_a_memory_call(self):
        class UnusedCatalogue:
            def __getattr__(self, name):
                raise AssertionError(f"unexpected catalogue access: {name}")

        service = SimpleNamespace(resources=UnusedCatalogue(), recipes=UnusedCatalogue())
        for version in ("2.0.0", "3.0.0"):
            with self.subTest(version=version):
                request = Krea2AssistedService._completion_request(
                    service, replace(self.project(), assistance_recipe_version=version),
                    "Remove the shoe; the floor is empty.",
                    Krea2AssistedTurnMode.CREATION, False,
                )
                self.assertEqual(request.operation_id, f"krea2.assisted.creation_chat@{version}")
                self.assertEqual(request.images, ())
                self.assertIn("Not requested", request.user_prompt)
                self.assertIn("Keep the red glass.", request.user_prompt)
                self.assertIn("Remove the shoe; the floor is empty.", request.user_prompt)
                self.assertNotIn("OBSOLETE_PROMPT", request.user_prompt)
