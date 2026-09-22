"""User-run regression suite. The gateway is synthetic; no real model or media work."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from threading import Event
from time import monotonic, sleep
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.application.stories import StoryService
from panelforge.domain import long_stories as narrative
from panelforge.domain.story_contracts import VERSION, wire_scene
from panelforge.features.lab.stories_web import stories_router
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore

ROOT = Path(__file__).resolve().parents[1]


class WorkflowGateway:
    def __init__(self):
        self.requests = []
        self.entered, self.release = Event(), Event()
        self.release.set()
        self.blocking = False
        self.nested = False
        self.mutate_discussion = False
        self.fail_operation = None
        self.responses = []
        self.overlong = False

    def stream(self, request):
        self.requests.append(request)
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("Fixture timed out")
        c = json.loads(request.user_prompt)
        op = c["operation"]
        if op == self.fail_operation:
            raise ValueError("Erreur de fixture à reprendre.")
        result = deepcopy(c["response_contract"])
        if op == "compose":
            choices = {"profile": "social", "narration": "dialogue", "ending_type": "reversal"}
            result["resolved_options"] = {k: choices[k] if c["long_options"][k] == "auto" else c["long_options"][k] for k in choices}
            for unit in result["series_outline"]["episodes"]:
                unit["ending_type"] = "open"
            result["series_outline"]["episodes"][-1]["ending_type"] = result["resolved_options"]["ending_type"]
        elif op == "edit_outline":
            result["edits"] = []
            result["review"] = {"summary": "Arc cohérent.", "issues": []}
        elif op == "review_block":
            result["reviews"] = [{"unit_id": unit["unit_id"], "summary": "Raccord examiné.",
                "issues": [{"severity": "blocking", "target_id": "scene-1", "problem": "Un refus manque.",
                            "suggestion": "Montrer le refus."}] if self.blocking else []}
                for unit in c["units_to_review"]]
        elif op == "discuss":
            result = {"reply": "La scène prépare le refus.", "discussion_only": not self.mutate_discussion}
        else:
            if op == "develop" and self.overlong:
                for scene in result["scenario"]["scenes"]:
                    scene["dialogue"] = [dict(speaker_id=scene["character_ids"][0],
                        text=" ".join(["Pourquoi"] * 60), delivery="spoken")]
            if op in {"revise", "repair_episode"} and c.get("current_scenario"):
                index = (c.get("feedback_target") or {}).get("scene_index") or 0
                if "scene_edits" in result:
                    result["scene_edits"][0]["scene"]["action"] += " Le refus est explicite."
                    if self.overlong:
                        result["scene_edits"][0]["scene"]["dialogue"] = []
                else:
                    result["scenario"] = deepcopy(c["current_scenario"])
                    result["scenario"].pop("characters", None)
                    result["scenario"]["scenes"] = [wire_scene(scene, c["current_episode_state"]["scene_events"][i])
                        for i, scene in enumerate(result["scenario"]["scenes"])]
                    result["episode_state"] = {k: deepcopy(v) for k, v in c["current_episode_state"].items() if k != "scene_events"}
                    result["scenario"]["scenes"][index]["action"] += " Le refus est explicite."
            if self.nested:
                result["scenario"]["episode_state"] = result.pop("episode_state")
        self.responses.append(deepcopy(result))
        yield CompletionStreamEvent(kind=StreamEventKind.COMPLETED, phase=StreamPhase.COMPLETED,
            result=CompletionResult(model_id="local::fixture", content=json.dumps(result), finish_reason="stop"))


class StoryWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gateway = WorkflowGateway()
        self.service = StoryService(gateway=self.gateway, store=LocalStoryStore(self.temp.name),
            recipes=LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0"),
            long_recipes=LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0"))

    def create(self, mode="automatic", count=2):
        return self.service.create(brief="Une addition provoque une dispute.", narrative_format="long",
            long_options=dict(profile="auto", delivery="continuous", narration="auto", ending_type="auto", unit_count=count),
            workflow_mode=mode, visual_universe="Gouttes d’eau", target_seconds=80,
            architect_model_id="local::fixture", writer_model_id="local::fixture")

    def settle(self, project):
        deadline = monotonic() + 8
        while monotonic() < deadline:
            with self.service._lock:
                if project["project_id"] not in self.service._active:
                    return self.service.get(project["project_id"])
            sleep(.005)
        self.fail("Le parcours fictif n’a pas terminé.")

    def advance(self, project):
        self.service.workflow.advance(project["project_id"], project["version"])
        return self.settle(project)

    def test_automatic_two_sequences_use_five_calls_and_review_before_fabrication(self):
        project = self.advance(self.create())
        self.assertEqual(project["workflow"]["status"], "ready", project["workflow"])
        self.assertEqual([r.operation_id.split('.')[2].split('@')[0] for r in self.gateway.requests],
                         ["compose", "edit_outline", "develop", "develop", "review_block"])
        self.assertEqual(project["long_options"]["profile"], "social")
        self.assertTrue(all(u["ready"] for u in project["long_status"]["units"].values()))
        self.assertEqual(len(project["document"]["concepts"]), 0)  # One architecture, no parallel pitch list.
        for request in self.gateway.requests:
            self.assertIn("Gouttes d’eau", request.system_prompt)
        budget = json.loads(self.gateway.requests[0].user_prompt)["clip_budget"]
        self.assertEqual(budget["max_seconds_total"], 120)
        self.assertEqual(budget["scope"], "per_unit")
        self.assertEqual(json.loads(self.gateway.requests[0].user_prompt)["target_seconds_total"], 80)
        self.assertEqual(project["llm_usage"]["calls"], 5)
        self.assertEqual(project["workflow"]["calls"], 5)
        self.assertEqual(len(project["draft_history"]), 4)
        self.assertTrue(all(entry["status"] == "accepted" for entry in project["llm_attempts"]))

    def test_local_duration_problem_is_corrected_before_paying_for_editorial_review(self):
        self.gateway.overlong = True
        project = self.advance(self.create(count=1))
        self.assertEqual(project["workflow"]["status"], "ready", project["job"].get("error"))
        operations = [r.operation_id.split('.')[2].split('@')[0] for r in self.gateway.requests]
        self.assertEqual(operations, ["compose", "edit_outline", "develop", "repair_episode", "review_block"])
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_manual_pauses_for_direction_and_each_sequence(self):
        project = self.advance(self.create("manual"))
        self.assertEqual(len(self.gateway.requests), 2)
        self.assertEqual(project["workflow"]["wait_target"], "outline")
        project = self.advance(project)
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")
        self.assertNotIn("episode-2", project["document"]["episode_scenarios"])
        project = self.advance(project)
        self.assertEqual(project["workflow"]["wait_target"], "episode-2")
        calls = len(self.gateway.requests)
        project = self.advance(project)
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(project["llm_usage"]["calls"], calls)
        self.assertEqual(project["workflow"]["calls"], calls)

    def test_pause_finishes_active_call_and_does_not_start_another(self):
        project = self.create()
        self.gateway.release.clear()
        self.addCleanup(self.gateway.release.set)
        self.service.workflow.advance(project["project_id"], project["version"])
        self.assertTrue(self.gateway.entered.wait(2))
        self.service.workflow.pause(project["project_id"])
        self.gateway.release.set()
        project = self.settle(project)
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(project["workflow"]["status"], "paused")
        self.assertIsNotNone(project["document"]["series_outline"])

    def test_existing_written_story_resumes_its_review_without_developing_again(self):
        project = self.advance(self.create("manual", 1))
        project = self.advance(project)
        before = deepcopy(project["document"]["scenario"])
        project["document"]["reviews"].pop("episode-1")
        project["workflow"].update(approvals={}, status="awaiting_author", wait_target="outline")
        project = self.service.store.save(project)
        calls = len(self.gateway.requests)
        project = self.advance(project)
        self.assertEqual([r.operation_id for r in self.gateway.requests[calls:]], [f"story.long.review_block@{VERSION}"])
        self.assertEqual(project["document"]["scenario"], before)
        self.assertTrue(project["long_status"]["fabrication_ready"])
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")

    def test_persistent_criticism_does_not_loop_or_approve(self):
        self.gateway.blocking = True
        project = self.advance(self.create(count=1))
        self.assertEqual(project["workflow"]["status"], "blocked")
        self.assertFalse(project["long_status"]["fabrication_ready"])
        operations = [r.operation_id for r in self.gateway.requests]
        self.assertEqual(sum("repair_episode" in x for x in operations), 1)
        calls = len(operations)
        project = self.advance(project)
        self.assertEqual(len(self.gateway.requests), calls)

    def test_nested_state_is_recovered_and_raw_is_preserved(self):
        self.gateway.nested = True
        project = self.advance(self.create("manual", 1))
        self.gateway.entered.clear()
        self.gateway.release.clear()
        self.addCleanup(self.gateway.release.set)
        self.service.workflow.advance(project["project_id"], project["version"])
        self.assertTrue(self.gateway.entered.wait(2))
        self.service.workflow.pause(project["project_id"])
        self.gateway.release.set()
        project = self.settle(project)
        self.assertEqual(project["job"]["status"], "succeeded", project["job"].get("error"))
        revisions = project["revisions"]
        self.assertTrue(any(r["label"] == "Unité rédigée V2" for r in revisions))
        self.assertIn("episode-1", project["document"]["episode_states"])
        draft = json.loads(project["job"]["draft"])
        self.assertIn("episode_state", draft["scenario"])
        self.assertNotIn("episode_state", draft)
        self.assertTrue(project["job"]["normalizations"])

    def test_retry_preserves_local_feedback_and_marks_it_applied(self):
        project = self.advance(self.create("manual", 1))
        project = self.advance(project)
        self.gateway.fail_operation = "revise"
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="episode-1", scene_index=0, instruction="Rends ce refus visible.")
        project = self.settle(project)
        self.assertEqual(project["job"]["status"], "failed")
        target = deepcopy(project["job"]["feedback_target"])
        self.gateway.fail_operation = None
        self.service.retry(project["project_id"], project["version"])
        project = self.settle(project)
        revisions = [json.loads(r.user_prompt) for r in self.gateway.requests if ".revise@" in r.operation_id]
        self.assertEqual(revisions[-1]["feedback_target"], target)
        self.assertEqual(revisions[-1]["author_feedback"], "Rends ce refus visible.")
        turns = [t for t in project["turns"] if t.get("feedback_status")]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["feedback_status"], "applied")
        self.assertEqual(project["workflow"]["status"], "awaiting_author")

    def test_retry_preserves_both_units_in_failed_block(self):
        self.gateway.fail_operation = "review_block"
        project = self.advance(self.create())
        self.assertEqual(project["job"]["review_unit_ids"], ["episode-1", "episode-2"])
        self.gateway.fail_operation = None
        self.service.retry(project["project_id"], project["version"])
        project = self.settle(project)
        self.assertEqual(project["workflow"]["status"], "ready")
        last = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertEqual([u["unit_id"] for u in last["units_to_review"]], ["episode-1", "episode-2"])

    def test_question_cannot_apply_a_document(self):
        project = self.advance(self.create("manual", 1))
        before = deepcopy(project["document"])
        self.gateway.mutate_discussion = True
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="outline", scene_index=None, instruction="Pourquoi cette fin ?", question=True)
        project = self.settle(project)
        self.assertEqual(project["job"]["status"], "failed")
        self.assertEqual(project["document"], before)

    def test_normalization_never_invents_missing_memory_or_picks_a_conflicting_one(self):
        original = {"reply": "Ok", "scenario": {"episode_state": {"facts": []}}}
        recovered = narrative.normalize_episode_response(original)
        self.assertNotIn("episode_state", recovered["scenario"])
        self.assertIn("episode_state", original["scenario"])
        with self.assertRaisesRegex(ValueError, "Deux mémoires"):
            narrative.normalize_episode_response({**original, "episode_state": {"facts": ["different"]}})
        self.assertNotIn("episode_state", narrative.normalize_episode_response({"scenario": {}}))

    def test_scene_feedback_rejects_changes_to_another_scene(self):
        project = self.advance(self.create("manual", 1))
        project = self.advance(project)
        doc = project["document"]
        # A second valid scene serves the same event; only scene zero is targeted.
        doc["episode_scenarios"]["episode-1"]["scenes"].append(deepcopy(doc["scenario"]["scenes"][0]))
        doc["scenario"] = deepcopy(doc["episode_scenarios"]["episode-1"])
        memory = doc["episode_states"]["episode-1"]
        memory["scene_events"].append(dict(deepcopy(memory["scene_events"][0]), scene_index=1))
        project["job"] = {"operation": "revise", "feedback_target": {"unit_id": "episode-1", "scene_index": 0}}
        response = {"reply": "Révision", "scenario": deepcopy(doc["scenario"]), "episode_state": deepcopy(memory)}
        response["scenario"]["scenes"][1]["action"] += " Un changement hors cible."
        with self.assertRaisesRegex(ValueError, "ciblait une scène"):
            narrative.parse(project, response)

    def test_question_preserves_document_and_scoped_feedback_has_a_version(self):
        project = self.advance(self.create("manual", 1))
        project = self.advance(project)
        before = deepcopy(project["document"])
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"], unit_id="episode-1",
                                       scene_index=0, instruction="Pourquoi ce refus ?", question=True)
        project = self.settle(project)
        self.assertEqual(project["document"], before)
        context = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertEqual(context["author_feedback"], "Pourquoi ce refus ?")
        self.assertEqual(context["feedback_target"]["scene_index"], 0)
        self.assertIn("source_hash", context["feedback_target"])
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"], unit_id="episode-1",
                                       scene_index=0, instruction="Rends le refus visible.")
        project = self.settle(project)
        self.assertIn("refus est explicite", project["document"]["scenario"]["scenes"][0]["action"])
        self.assertEqual(project["workflow"]["status"], "awaiting_author")
        self.assertEqual([t["feedback_status"] for t in project["turns"] if t.get("target") and t["role"] == "user"], ["answered", "applied"])

    def test_individual_secret_rule_and_character_are_valid_review_targets(self):
        project = self.advance(self.create("manual", 1))
        outline = project["document"]["series_outline"]
        outline["secrets"] = [{"id": "secret-1", "truth": "Un mensonge.", "known_by": [], "reveal_episode_id": None}]
        outline["world_rules"] = [{"id": "rule-1", "rule": "Règle", "limits": "Limite"}]
        for target in ["secret-1", "rule-1", outline["characters"][0]["id"]]:
            review = narrative.validate_review(project, {"summary": "Remarque", "issues": [{"severity": "warning",
                "target_id": target, "problem": "À préciser.", "suggestion": "Clarifier."}]}, "outline")
            self.assertEqual(review["issues"][0]["target_id"], target)
        with self.assertRaisesRegex(ValueError, "inconnue"):
            narrative.validate_review(project, {"summary": "Remarque", "issues": [{"severity": "warning",
                "target_id": "secret-absent", "problem": "Faux", "suggestion": "Faux"}]}, "outline")

    def test_api_rejects_invalid_feedback_and_does_not_expose_internal_step_parameters(self):
        app = FastAPI(); app.include_router(stories_router(self.service))
        client = TestClient(app)
        project = self.create("manual")
        url = f"/api/stories/projects/{project['project_id']}"
        self.assertEqual(client.post(url + "/advance", json={"expected_version": project["version"], "mode": "invalid"}).status_code, 422)
        self.assertEqual(client.post(url + "/write", json={"expected_version": project["version"], "operation": "compose",
            "request_id": "fixture-request", "workflow_step": True}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
