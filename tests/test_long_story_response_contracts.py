"""Replay recorded failed responses locally, without a model or a live workspace."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
import tempfile
import unittest

from panelforge.application.stories import StoryService
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
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

    def event_dependencies_draft(self):
        project, _ = self.recorded()
        project = self.service.revalidate(project["project_id"], project["version"])
        outline = deepcopy(project["document"]["series_outline"])
        for unit in outline["episodes"]:
            unit.pop("beats", None)
            for event in unit["events"]:
                event.pop("depends_on")
        outline["episodes"][0]["events"][0]["evidence"] += " Un geste plus lisible accompagne la réplique."
        response = dict(reply="Arc relu.", series_outline=outline, review=dict(summary="Relecture terminée.", issues=[]))
        project["job"].update(operation="edit_outline", status="failed", error="Missing event fields",
            draft=json.dumps(response, ensure_ascii=False), narrative_input_hash=narrative.input_hash(project))
        project["workflow"]["status"] = "blocked"
        return self.service.store.save(project), response

    def test_editorial_pass_recovers_saved_dependencies_without_a_call_or_rewriting_text(self):
        project, response = self.event_dependencies_draft()
        before = deepcopy(project)
        self.assertTrue(self.service.get(project["project_id"])["job"]["can_revalidate"])
        result = self.service.revalidate(project["project_id"], project["version"])
        self.assertEqual(result["job"]["status"], "succeeded")
        self.assertEqual(result["job"]["draft"], before["job"]["draft"])
        self.assertEqual(result["workflow"]["calls"], before["workflow"]["calls"])
        self.assertTrue(any("Liens de causalité" in note for note in result["job"]["normalizations"]))
        for old_unit, incoming_unit, saved_unit in zip(before["document"]["series_outline"]["episodes"],
                response["series_outline"]["episodes"], result["document"]["series_outline"]["episodes"]):
            for old, incoming, saved in zip(old_unit["events"], incoming_unit["events"], saved_unit["events"]):
                self.assertEqual(saved, {**incoming, "depends_on": old["depends_on"]})
        self.assertEqual(project, before)

    def test_missing_dependencies_are_not_inferred_for_creation_or_changed_event_structure(self):
        project, response = self.event_dependencies_draft()
        for case in ("compose", "revise_outline", "no_previous", "new_id", "reordered", "duplicate", "new_unit"):
            with self.subTest(case=case):
                candidate, outline = deepcopy(project), deepcopy(response["series_outline"])
                events = outline["episodes"][0]["events"]
                if case in {"compose", "revise_outline"}:
                    candidate["job"]["operation"] = case
                elif case == "no_previous":
                    candidate["document"]["series_outline"] = None
                elif case == "new_id":
                    events[0]["id"] = "new-event"
                elif case == "reordered":
                    events[0], events[1] = events[1], events[0]
                elif case == "duplicate":
                    events[1]["id"] = events[0]["id"]
                elif case == "new_unit":
                    outline["episodes"].append(deepcopy(outline["episodes"][0]))
                recovered, notes = narrative.normalize_event_dependencies(candidate, outline)
                self.assertEqual(recovered, outline)
                self.assertFalse(notes)
                with self.assertRaises(ValueError):
                    narrative.validate_outline(candidate, outline)

    def test_explicit_dependencies_and_other_contract_errors_are_preserved(self):
        project, response = self.event_dependencies_draft()
        outline = response["series_outline"]
        outline["episodes"][0]["events"][1]["depends_on"] = []
        result = narrative.validate_outline(project, outline)
        self.assertEqual(result["episodes"][0]["events"][1]["depends_on"], [])
        outline["episodes"][0]["events"][1]["depends_on"] = ["unknown-event"]
        with self.assertRaisesRegex(ValueError, "(?i)dépendance|référence inconnue"):
            narrative.validate_outline(project, outline)
        for field, value in (("evidence", None), ("surprise", "Extra field")):
            broken = deepcopy(response["series_outline"])
            event = broken["episodes"][0]["events"][0]
            if value is None:
                event.pop(field)
            else:
                event[field] = value
            with self.assertRaisesRegex(ValueError, r"series_outline\.episodes\[0\]\.events\[0\].*" + field):
                narrative.validate_outline(project, broken)

    def knowledge_draft(self, **changes):
        project, _ = self.recorded()
        project = self.service.revalidate(project["project_id"], project["version"])
        project["document"]["series_outline"]["secrets"] = []
        project["job"].update(operation="develop", status="failed", error="Old validation error")
        response = narrative.episode_example(project)
        entry = dict(secret_id=None, character_ids=[project["document"]["series_outline"]["characters"][0]["id"]],
                     event_id=response["episode_state"]["scene_events"][0]["event_ids"][0])
        entry.update(changes)
        response["episode_state"]["knowledge"] = [entry]
        project["job"].update(draft=json.dumps(response, ensure_ascii=False),
                              narrative_input_hash=narrative.input_hash(project))
        return self.service.store.save(project), response

    def test_null_secret_is_recovered_without_regenerating_or_editing_the_scenario(self):
        project, response = self.knowledge_draft()
        self.assertTrue(self.service.get(project["project_id"])["job"]["can_revalidate"])
        result = self.service.revalidate(project["project_id"], project["version"])
        self.assertEqual(result["job"]["status"], "succeeded")
        unit = result["document"]["selected_episode_id"]
        self.assertEqual(result["document"]["episode_states"][unit]["knowledge"], [])
        self.assertEqual(result["document"]["scenario"], response["scenario"])
        self.assertEqual(result["job"]["draft"], project["job"]["draft"])
        self.assertTrue(any("aucun secret déclaré" in message for message in result["job"]["normalizations"]))

    def test_null_secret_does_not_hide_invalid_events_characters_or_non_null_secrets(self):
        for changes in ({"event_id": "unknown"}, {"character_ids": ["unknown"]}, {"secret_id": "unknown"}):
            with self.subTest(changes=changes):
                project, _ = self.knowledge_draft(**changes)
                self.assertFalse(self.service.get(project["project_id"])["job"]["can_revalidate"])
                with self.assertRaises(ValueError):
                    self.service.revalidate(project["project_id"], project["version"])

    def test_null_reference_is_not_removed_when_the_outline_declares_a_real_secret(self):
        project, _ = self.knowledge_draft()
        project["document"]["series_outline"]["secrets"] = [
            {"id": "secret-real", "truth": "Le document est caché.", "known_by": [], "reveal_episode_id": None}]
        project["job"]["narrative_input_hash"] = narrative.input_hash(project)
        project = self.service.store.save(project)
        with self.assertRaisesRegex(ValueError, "secret_id"):
            self.service.revalidate(project["project_id"], project["version"])

    def test_ambiguous_or_incomplete_json_stops_without_an_unverifiable_model_rewrite(self):
        project, _ = self.recorded()
        class Gateway:
            def __init__(self): self.calls = []
            def stream(self, request):
                self.calls.append(request)
                yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                    result=CompletionResult("local::fixture", '{"reply": "incomplet"', finish_reason="stop"))
        gateway = self.service.gateway = Gateway()
        project["workflow"]["status"] = "paused"
        project["job"]["status"] = "running"
        project = self.service.store.save(project)
        self.service._run(project, self.recipes.snapshot(), Event())
        result = self.service.get(project["project_id"])
        self.assertEqual(len(gateway.calls), 1)
        self.assertEqual(result["job"]["status"], "failed")
        self.assertNotIn("format_repair", result["job"])
        self.assertEqual(result["job"]["draft"], '{"reply": "incomplet"')

    def test_missing_separator_is_recovered_locally_and_preserves_original(self):
        project, fixture = self.recorded()
        valid = json.dumps(json.loads(fixture["response_raw"]), ensure_ascii=False)
        broken = valid.replace(', "series_outline":', ' "series_outline":', 1)
        self.assertNotEqual(broken, valid)
        class Gateway:
            def __init__(self): self.calls = []
            def stream(self, request):
                self.calls.append(request)
                yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                    result=CompletionResult("local::fixture", broken if len(self.calls) == 1 else valid,
                                            call_id=f"fixture-{len(self.calls)}", finish_reason="stop"))
        gateway = self.service.gateway = Gateway()
        project["workflow"]["status"] = "paused"
        project["job"]["status"] = "running"
        project = self.service.store.save(project)
        self.service._run(project, self.recipes.snapshot(), Event())
        result = self.service.get(project["project_id"])
        self.assertEqual(len(gateway.calls), 1)
        self.assertEqual(result["job"]["status"], "succeeded", result["job"].get("error"))
        self.assertEqual(result["job"]["original_draft"], broken)
        self.assertNotIn("format_repair", result["job"])
        self.assertTrue(result["job"]["normalizations"])

    def test_invalid_content_is_still_rejected_without_changing_the_saved_draft(self):
        project, fixture = self.recorded()
        raw = json.loads(fixture["response_raw"])
        raw["series_outline"]["episodes"][0]["events"][0]["depends_on"] = ["event-does-not-exist"]
        project["job"]["draft"] = json.dumps(raw, ensure_ascii=False)
        project = self.service.store.save(project)
        with self.assertRaisesRegex(ValueError, "(?i)dépendance|référence inconnue"):
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
                with self.assertRaisesRegex(ValueError, "Type attendu|Champ obligatoire|Champ inattendu"):
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
                self.assertEqual(set(contracts["events"]), {"id", "trigger", "change", "evidence", "depends_on"})
                self.assertIn("outline_entry_contracts", request.system_prompt)
                self.assertIn("depends_on est obligatoire", request.system_prompt)

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
