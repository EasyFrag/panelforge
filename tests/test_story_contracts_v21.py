"""User-run contract regressions, using saved text and isolated stores only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest

from panelforge.application.stories import StoryService
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.application import story_attempts
from panelforge.domain import long_stories as narrative
from panelforge.domain import story_contracts as contracts
from panelforge.domain import story_draft_repairs
from panelforge.domain.story_diagnostics import normalize_scene_state, project_quality
from panelforge.domain.story_response_recovery import assert_format_only, decode_response
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/long_stories/development_failures_2026_09_22.json"


class NoModel:
    def stream(self, request):
        raise AssertionError("This recovery must remain local")


class StoryContractsV21Test(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.project = deepcopy(self.fixture["project"])
        self.project["job"].update(draft=self.fixture["reaction_draft"], narrative_input_hash=narrative.input_hash(self.project))

    def wire(self):
        project = deepcopy(self.project)
        project["job"]["response_contract_version"] = contracts.VERSION
        value = json.loads(self.fixture["reaction_draft"])
        state, _ = normalize_scene_state(project, value["scenario"], value["episode_state"])
        value["episode_state"] = state
        return project, contracts.wire_example(project, value)

    def test_recorded_json_repair_is_exact_and_now_local(self):
        original, correction = self.fixture["invalid_json"], self.fixture["syntax_correction"]
        self.assertEqual(original.replace('"delivery": "delivery": "spoken"', '"delivery": "spoken"'), correction)
        data, notes = decode_response(original)
        self.assertEqual(data, json.loads(correction))
        self.assertTrue(notes)
        assert_format_only(original, correction)
        narrative.parse(self.project, data)

    def test_recorded_coda_is_anchored_without_changing_the_story(self):
        value = json.loads(self.fixture["reaction_draft"])
        before = deepcopy(value)
        _, result = narrative.parse(self.project, value)
        coda = result["episode_state"]["scene_events"][4]
        self.assertEqual(coda["purpose"], "reaction")
        self.assertEqual(coda["anchor_scene_index"], 3)
        self.assertEqual(coda["event_ids"], [])
        for scene, received in zip(result["scenario"]["scenes"], before["scenario"]["scenes"]):
            self.assertEqual(scene["action"], received["action"])
            self.assertEqual(scene["dialogue"], received["dialogue"])
        self.assertEqual(value, before)

    def test_unrelated_empty_clip_is_not_assigned_to_the_last_event(self):
        value = json.loads(self.fixture["reaction_draft"])
        value["episode_state"]["scene_events"][4]["evidence"] = "Un inconnu achète une voiture."
        with self.assertRaises(contracts.StoryValidationError) as caught:
            narrative.parse(self.project, value)
        self.assertTrue(any(i["code"] == "scene_event_missing" for i in caught.exception.issues))

    def test_new_wire_assembles_cast_and_indexed_memory_without_model_copies(self):
        project, value = self.wire()
        self.assertNotIn("characters", value["scenario"])
        self.assertNotIn("scene_events", value["episode_state"])
        self.assertEqual(contracts.structural_issues(value, contracts.response_schema(project)), [])
        _, result = narrative.parse(project, value)
        self.assertEqual(result["scenario"]["characters"], project["document"]["series_outline"]["characters"])
        self.assertEqual([x["scene_index"] for x in result["episode_state"]["scene_events"]], list(range(5)))
        self.assertNotIn("narrative", result["scenario"]["scenes"][0])
        self.assertEqual(result["episode_state"]["knowledge"], [])  # Already known in the bible.

    def test_unknown_speaker_and_bad_anchor_are_reported_together(self):
        project, value = self.wire()
        value["scenario"]["scenes"][0]["dialogue"][0]["speaker_id"] = "series-c4"  # Known, absent here.
        value["scenario"]["scenes"][4]["narrative"]["anchor_scene_index"] = 4
        with self.assertRaises(contracts.StoryValidationError) as caught:
            narrative.parse(project, value)
        self.assertTrue({"absent_speaker", "scene_anchor"} <= {i["code"] for i in caught.exception.issues})

    def test_timing_blocks_fabrication_even_when_the_model_review_says_clear(self):
        _, result = narrative.parse(self.project, json.loads(self.fixture["reaction_draft"]))
        narrative.apply_document(self.project, result)
        issues = project_quality(self.project, "episode-1")
        self.assertEqual(sum(i["code"] == "clip_load" and i["level"] == "blocking" for i in issues), 4)
        review = narrative.validate_review(self.project, {"summary": "Tout est bon.", "issues": []}, "episode-1")
        self.project["document"]["reviews"]["episode-1"] = review
        self.assertFalse(narrative.review_clear(self.project, "episode-1"))
        with self.assertRaises(ValueError):
            narrative.fabrication_scenario(self.project)

    def test_audience_hint_does_not_teach_the_hero_or_confirm_a_secret(self):
        project, value = self.wire()
        value["scenario"]["scenes"][1]["narrative"]["hints"] = ["secret-1"]
        _, result = narrative.parse(project, value)
        self.assertEqual(result["episode_state"]["scene_events"][1]["reveals"], [])
        self.assertFalse(any("series-c1" in row["character_ids"] for row in result["episode_state"]["knowledge"]))
        value["scenario"]["scenes"][1]["narrative"].update(hints=[], reveals=["secret-1"])
        with self.assertRaises(contracts.StoryValidationError) as caught:
            narrative.parse(project, value)
        self.assertTrue(any(i["code"] == "early_reveal" for i in caught.exception.issues))

    def test_arc_edits_preserve_unmentioned_ids_dependencies_and_text(self):
        project = deepcopy(self.project)
        project["job"].update(operation="edit_outline", response_contract_version=contracts.VERSION)
        response = dict(reply="Un titre plus clair.", base_hash=narrative.source_hash(project, "outline"),
            edits=[dict(path="outline/title", value="Le dîner des dupes")], review=dict(summary="Arc relu.", issues=[]))
        _, result = narrative.parse(project, response)
        self.assertEqual(result["series_outline"]["title"], "Le dîner des dupes")
        self.assertEqual(result["series_outline"]["episodes"], project["document"]["series_outline"]["episodes"])
        self.assertTrue(any(i.get("code") == "language_residue" for i in result["review"]["issues"]))
        response["base_hash"] = "obsolete"
        with self.assertRaises(ValueError):
            narrative.parse(project, response)

    def test_changed_causality_does_not_recover_old_dependencies_by_id_only(self):
        project = deepcopy(self.project)
        project["job"]["operation"] = "edit_outline"
        outline = deepcopy(project["document"]["series_outline"])
        event = outline["episodes"][0]["events"][1]
        event.pop("depends_on")
        event["trigger"] = "Un incident complètement différent."
        recovered, _ = narrative.normalize_event_dependencies(project, outline)
        self.assertNotIn("depends_on", recovered["episodes"][0]["events"][1])

    def test_metadata_patch_cannot_rewrite_a_dialogue(self):
        project, value = self.wire()
        value["scenario"]["scenes"][4]["narrative"].update(purpose="progression", event_ids=[], anchor_scene_index=None)
        with self.assertRaises(contracts.StoryValidationError) as caught:
            narrative.parse(project, value)
        plan = story_draft_repairs.plan(json.dumps(value), caught.exception.issues)
        self.assertIsNotNone(plan)
        prefix = "scenario.scenes[4].narrative."
        patches = [{"path": prefix + key, "value_json": json.dumps(value)} for key, value in
                   (("purpose", "reaction"), ("anchor_scene_index", 3))]
        corrected = story_draft_repairs.apply(plan, json.dumps({"patches": patches}))
        _, result = narrative.parse(project, json.loads(corrected))
        self.assertEqual(result["episode_state"]["scene_events"][4]["event_ids"], [])
        for before, after in zip(value["scenario"]["scenes"], result["scenario"]["scenes"]):
            self.assertEqual(before["dialogue"], after["dialogue"])
            self.assertEqual(before["action"], after["action"])
        with self.assertRaises(ValueError):
            story_draft_repairs.apply(plan, json.dumps({"patches": [{"path": "scenario.scenes[0].dialogue[0].text", "value_json": '"Autre histoire"'}]}))

    def test_revalidation_exposes_preview_and_timing_without_a_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            service = StoryService(gateway=NoModel(), store=LocalStoryStore(directory),
                recipes=LocalStoryRecipeStore(directory, ROOT / "prompt_sources/story.brainrot/1.0.0"),
                long_recipes=LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0"))
            project = service.store.save(self.project)
            shown = service.get(project["project_id"])
            self.assertTrue(shown["job"]["can_revalidate"])
            self.assertEqual(len(shown["job"]["draft_preview"]["scenes"]), 5)
            self.assertEqual(sum(d["level"] == "blocking" for d in shown["job"]["draft_diagnostics"]), 4)
            recovered = service.revalidate(project["project_id"], project["version"])
            self.assertEqual(recovered["job"]["draft"], self.fixture["reaction_draft"])
            self.assertEqual(recovered["job"]["status"], "succeeded")
            self.assertTrue(any("réaction finale" in note for note in recovered["job"]["normalizations"]))
            self.assertFalse(service.get(project["project_id"])["long_status"]["fabrication_ready"])

    def test_scene_patch_preserves_archived_scenes_and_rejects_another_base(self):
        _, incoming = narrative.parse(self.project, json.loads(self.fixture["reaction_draft"]))
        narrative.apply_document(self.project, incoming)
        doc = self.project["document"]
        # An old scene can legitimately predate explicit delivery metadata.
        for line in doc["episode_scenarios"]["episode-1"]["scenes"][0]["dialogue"]:
            line.pop("delivery", None)
        previous = deepcopy(doc["episode_scenarios"]["episode-1"])
        self.project["job"].update(operation="revise", response_contract_version=contracts.VERSION,
            feedback_target=dict(unit_id="episode-1", scene_index=4))
        response = contracts.wire_example(self.project, {})
        response["scene_edits"][0]["scene"]["action"] += " Il sourit."
        _, changed = narrative.parse(self.project, response)
        self.assertEqual(changed["scenario"]["scenes"][:4], previous["scenes"][:4])
        self.assertEqual(changed["scenario"]["characters"], previous["characters"])
        self.assertEqual(changed["scenario"]["locations"], previous["locations"])
        response["base_hash"] = "previous-version"
        with self.assertRaises(ValueError):
            narrative.parse(self.project, response)

    def test_rejected_non_object_json_remains_readable_by_the_api(self):
        with tempfile.TemporaryDirectory() as directory:
            service = StoryService(gateway=NoModel(), store=LocalStoryStore(directory),
                recipes=LocalStoryRecipeStore(directory, ROOT / "prompt_sources/story.brainrot/1.0.0"),
                long_recipes=LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0"))
            self.project["job"]["draft"] = "[]"
            saved = service.store.save(self.project)
            shown = service.get(saved["project_id"])
            self.assertFalse(shown["job"]["can_revalidate"])
            self.assertEqual(shown["job"]["draft"], "[]")
            self.assertIsNone(shown["job"]["draft_preview"])

    def test_one_metadata_repair_keeps_separate_outcomes_and_original(self):
        project, response = self.wire()
        response["scenario"]["scenes"][4]["narrative"].update(purpose="progression", anchor_scene_index=None)
        original = json.dumps(response, ensure_ascii=False)
        prefix = "scenario.scenes[4].narrative."
        repair = json.dumps({"patches": [
            dict(path=prefix + "purpose", value_json='"reaction"'),
            dict(path=prefix + "anchor_scene_index", value_json="3")]})
        class Gateway:
            def __init__(self): self.requests = []
            def stream(self, request):
                self.requests.append(request)
                number = len(self.requests)
                if number > 2:
                    raise AssertionError("Only one recovery call is allowed")
                yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                    result=CompletionResult("local::fixture", original if number == 1 else repair,
                        call_id=f"fixture-{number}", finish_reason="stop"))
        class Outcomes:
            def __init__(self): self.items = []
            def report_application_outcome(self, call_id, outcome, **details):
                self.items.append((call_id, outcome.value))
        with tempfile.TemporaryDirectory() as directory:
            gateway, outcomes = Gateway(), Outcomes()
            recipes = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0")
            service = StoryService(gateway=gateway, store=LocalStoryStore(directory), application_outcomes=outcomes,
                recipes=LocalStoryRecipeStore(directory, ROOT / "prompt_sources/story.brainrot/1.0.0"), long_recipes=recipes)
            project["job"].update(status="running", draft="")
            saved = service.store.save(project)
            service._run(saved, recipes.snapshot(), Event())
            result = service.get(saved["project_id"])
            self.assertEqual(result["job"]["status"], "succeeded", result["job"].get("error"))
            self.assertEqual(outcomes.items, [("fixture-1", "rejected"), ("fixture-2", "accepted")])
            self.assertEqual(result["llm_usage"]["calls"], 2)
            self.assertEqual(result["llm_usage"]["repair_calls"], 1)
            self.assertEqual(result["job"]["original_draft"], original)
            self.assertTrue(result["job"]["format_repair"]["content_preserved"])
            self.assertEqual([attempt["status"] for attempt in result["llm_attempts"]], ["rejected", "accepted"])
            self.assertEqual(result["document"]["episode_states"]["episode-1"]["scene_events"][4]["event_ids"], [])
            story_attempts.archive_job(result)
            story_attempts.archive_job(result)
            self.assertEqual(len(result["draft_history"]), 1)
            self.assertEqual(result["draft_history"][0]["original_draft"], original)
