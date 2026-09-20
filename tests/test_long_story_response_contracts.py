"""Replay recorded failed responses locally, without a model or a live workspace."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application.stories import StoryService
from panelforge.domain import long_stories as narrative
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/long_stories"


class NoCallsGateway:
    def stream(self, request):
        raise AssertionError("Recovering an existing response must not call a model")


class LongStoryResponseContractsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.recipes = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0")
        self.service = StoryService(gateway=NoCallsGateway(), store=LocalStoryStore(temp.name),
            recipes=LocalStoryRecipeStore(temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0"),
            long_recipes=self.recipes)

    def recorded(self, name="compose_market_plain_rules"):
        fixture = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        project = self.service.create(**fixture["create"],
            architect_model_id="local::fixture", writer_model_id="local::fixture")
        package = self.recipes.snapshot()
        project["job"] = dict(operation="compose", request_id="recorded-failure", status="failed",
            error=fixture["observed_error"], draft=fixture["response_raw"], instruction="",
            model_role="architect_model_id", recipe_revision=package["revision"],
            editorial_fingerprint=package["fingerprint"], narrative_input_hash=narrative.input_hash(project))
        project["workflow"].update(status="blocked", calls=1, message="Previous failure")
        return self.service.store.save(project), fixture

    def test_both_recorded_failures_can_be_revalidated_without_regeneration(self):
        for name in ("compose_market_plain_rules", "compose_water_plain_rules"):
            with self.subTest(name=name):
                project, fixture = self.recorded(name)
                response = json.loads(fixture["response_raw"])
                result = self.service.revalidate(project["project_id"], project["version"])
                self.assertEqual(result["job"]["status"], "succeeded")
                self.assertEqual(result["job"]["draft"], fixture["response_raw"])
                self.assertTrue(result["job"]["normalizations"])
                rules = result["document"]["series_outline"]["world_rules"]
                self.assertEqual([r["rule"] for r in rules], response["series_outline"]["world_rules"])
                self.assertEqual([r["id"] for r in rules], [f"rule-{i+1}" for i in range(len(rules))])
                self.assertTrue(all(r["limits"] is None for r in rules))
                for key in ("title", "premise", "overall_arc", "ending", "characters", "contract", "secrets"):
                    self.assertEqual(result["document"]["series_outline"][key], response["series_outline"][key])
                self.assertEqual(result["workflow"]["status"], "paused")
                self.assertFalse(narrative.review_clear(result, "outline"))
                self.assertIsNone(result["document"]["scenario"])
                self.assertEqual(result["workflow"]["calls"], 1)
                self.assertEqual(len(result["revisions"]), 1)

    def test_invalid_content_is_still_rejected_without_changing_the_saved_draft(self):
        project, fixture = self.recorded()
        raw = json.loads(fixture["response_raw"])
        raw["series_outline"]["episodes"][0]["events"][0]["depends_on"] = ["event-does-not-exist"]
        project["job"]["draft"] = json.dumps(raw, ensure_ascii=False)
        project = self.service.store.save(project)
        with self.assertRaisesRegex(ValueError, "référence inconnue"):
            self.service.revalidate(project["project_id"], project["version"])
        saved = self.service.get(project["project_id"])
        self.assertEqual(saved["job"]["draft"], project["job"]["draft"])
        self.assertIsNone(saved["document"]["series_outline"])

    def test_plain_rules_preserve_existing_ids_and_limits_and_reserve_new_ids(self):
        project, _ = self.recorded()
        rules = ["First rule", {"id": "rule-1", "rule": "Second rule", "limits": "Only at night"}]
        before = deepcopy(rules)
        normalized = narrative.normalize_world_rules(project, rules)
        self.assertEqual(normalized[0], {"id": "rule-2", "rule": "First rule", "limits": None})
        self.assertEqual(rules, before)
        previous = {"id": "rule-original", "rule": "First rule", "limits": "Only twice"}
        project["document"]["series_outline"] = {"world_rules": [previous]}
        self.assertEqual(narrative.normalize_world_rules(project, ["First rule"]), [previous])
        with self.assertRaisesRegex(ValueError, "sans ambiguïté"):
            narrative.normalize_world_rules(project, ["Changed rule with no ID"])

    def test_secrets_and_structured_rules_are_not_guessed_or_silently_reduced(self):
        project, fixture = self.recorded()
        for collection, values in (
            ("secrets", ["A truth without knowledge or reveal timing"]),
            ("world_rules", [{"id": "rule-1", "rule": "A rule", "limits": None, "unexpected": "keep me"}]),
            ("world_rules", [{"id": "rule-1", "rule": "A rule"}]),
        ):
            with self.subTest(collection=collection, values=values):
                response = json.loads(fixture["response_raw"])
                response["series_outline"][collection] = values
                with self.assertRaisesRegex(ValueError, "doit contenir exactement"):
                    narrative.parse(project, response)

    def test_outline_requests_describe_entries_even_when_optional_lists_are_empty(self):
        project, fixture = self.recorded()
        _, incoming = narrative.parse(project, json.loads(fixture["response_raw"]))
        for operation in ("compose", "outline", "edit_outline", "revise_outline", "repair_outline"):
            with self.subTest(operation=operation):
                candidate = deepcopy(project)
                if operation != "compose":
                    narrative.apply_document(candidate, deepcopy(incoming))
                candidate["job"]["operation"] = operation
                if operation == "repair_outline":
                    candidate["document"]["reviews"]["outline"] = {"summary": "Check", "issues": []}
                request = self.service._request(candidate, self.recipes.snapshot())
                context = json.loads(request.user_prompt)
                self.assertEqual(context["response_contract"]["series_outline"]["world_rules"], [])
                self.assertEqual(context["response_contract"]["series_outline"]["secrets"], [])
                contracts = context["outline_entry_contracts"]
                self.assertEqual(set(contracts["world_rules"]), {"id", "rule", "limits"})
                self.assertEqual(set(contracts["secrets"]), {"id", "truth", "known_by", "reveal_episode_id"})
                self.assertIn("outline_entry_contracts", request.system_prompt)

    def test_auto_choices_are_not_prefilled_as_social_dialogue_and_reversal(self):
        project, _ = self.recorded()
        context = json.loads(self.service._request(project, self.recipes.snapshot()).user_prompt)
        choices = context["response_contract"]["resolved_options"]
        self.assertTrue(all(value.startswith("CHOISIR_") for value in choices.values()))
        project["long_options"].update(profile="fantasy", narration="visual", ending_type="open")
        context = json.loads(self.service._request(project, self.recipes.snapshot()).user_prompt)
        self.assertEqual(context["response_contract"]["resolved_options"],
                         {"profile": "fantasy", "narration": "visual", "ending_type": "open"})


if __name__ == "__main__":
    unittest.main()
