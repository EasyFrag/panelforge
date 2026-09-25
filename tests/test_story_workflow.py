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
from panelforge.domain.story_contracts import wire_scene
from panelforge.domain.story_visual_states import CONTRACT_VERSION as VERSION
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
        self.warnings = False
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
                for unit in c.get("reader_units", c.get("units_to_review", []))]
            if self.warnings:
                for review in result["reviews"]:
                    review["issues"].append(dict(severity="warning", target_id="scene-1",
                        problem="Le propriétaire est absent du casting.", suggestion="Retirer le propriétaire."))
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
            if "reader_units" not in json.loads(request.user_prompt):
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

    def blocked_project(self, mode="automatic", count=1):
        self.gateway.blocking = True
        self.gateway.warnings = True
        project = self.advance(self.create(mode, count))
        if mode == "manual":
            project = self.advance(project)
        self.assertEqual(project["workflow"]["status"], "blocked")
        return project

    def test_explicit_correction_reviews_once_then_continues_without_optional_edits(self):
        project = self.blocked_project()
        project["document"]["reviews"]["episode-1"]["issues"].append(dict(severity="blocking", target_id="scene-1",
            problem="Le geste ne montre pas le refus.", suggestion="Clarifier le geste."))
        project = self.service.store.save(project)
        before = len(self.gateway.requests)
        self.gateway.blocking = False
        self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
        project = self.settle(project)
        calls = [json.loads(r.user_prompt) for r in self.gateway.requests[before:]]
        self.assertEqual([c["operation"] for c in calls], ["repair_episode", "review_block"])
        self.assertTrue(all(i["severity"] == "blocking" for i in calls[0]["review_to_address"]["issues"]))
        self.assertEqual(len(calls[0]["review_to_address"]["issues"]), 2)
        self.assertNotIn("Retirer le propriétaire", json.dumps(calls[0], ensure_ascii=False))
        self.assertEqual(calls[1]["review_followup"][0]["unit_id"], "episode-1")
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(project["workflow"]["mode"], "automatic")
        self.assertNotIn("correction", project["workflow"])
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_explicit_correction_does_not_repeat_when_the_review_still_blocks(self):
        project = self.blocked_project()
        for _ in range(2):
            before = len(self.gateway.requests)
            self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
            project = self.settle(project)
            calls = [json.loads(r.user_prompt)["operation"] for r in self.gateway.requests[before:]]
            self.assertEqual(calls, ["repair_episode", "review_block"])
            self.assertEqual(project["workflow"]["status"], "blocked")
            self.assertFalse(project["long_status"]["fabrication_ready"])
            self.assertNotIn("correction", project["workflow"])
            count = len(self.gateway.requests)
            project = self.advance(project)
            self.assertEqual(len(self.gateway.requests), count)

    def test_correction_reviews_before_developing_next_unit_and_preserves_manual_mode(self):
        project = self.blocked_project(mode="manual", count=2)
        self.gateway.blocking = False
        before = len(self.gateway.requests)
        self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
        project = self.settle(project)
        calls = [json.loads(r.user_prompt) for r in self.gateway.requests[before:]]
        self.assertEqual([c["operation"] for c in calls], ["repair_episode", "review_block", "develop", "review_block"])
        self.assertEqual(calls[1]["response_contract"]["reviews"][0]["unit_id"], "episode-1")
        self.assertEqual(project["workflow"]["mode"], "manual")
        self.assertEqual(project["workflow"]["status"], "awaiting_author")
        self.assertEqual(project["workflow"]["wait_target"], "episode-2")
        self.assertEqual(project["workflow"]["approvals"]["episode-1"], narrative.source_hash(project, "episode-1"))

    def test_correction_rejects_outdated_reviews_and_optional_only_reviews_without_calls(self):
        project = self.blocked_project()
        original = deepcopy(project)
        project["document"]["episode_scenarios"]["episode-1"]["scenes"][0]["action"] += " Le regard change."
        project = self.service.store.save(project)
        before = len(self.gateway.requests)
        with self.assertRaisesRegex(ValueError, "changé depuis sa relecture"):
            self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
        original["document"]["reviews"]["episode-1"]["issues"] = [i for i in original["document"]["reviews"]["episode-1"]["issues"] if i["severity"] == "warning"]
        original["version"] = project["version"]
        project = self.service.store.save(original)
        with self.assertRaisesRegex(ValueError, "observations facultatives"):
            self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
        self.assertEqual(len(self.gateway.requests), before)
        self.assertEqual(self.service.store.get(project["project_id"])["version"], project["version"])

    def test_correction_failure_does_not_rewrite_again_or_run_review(self):
        project = self.blocked_project()
        document = deepcopy(project["document"])
        self.gateway.fail_operation = "repair_episode"
        before = len(self.gateway.requests)
        self.service.workflow.correct_and_continue(project["project_id"], expected_version=project["version"], unit_id="episode-1")
        project = self.settle(project)
        self.assertEqual(len(self.gateway.requests), before + 1)
        self.assertEqual(project["job"]["status"], "failed")
        self.assertEqual(project["workflow"]["status"], "blocked")
        self.assertNotIn("correction", project["workflow"])
        self.assertEqual(project["document"], document)

    def test_correction_route_rejects_double_click_and_can_be_paused(self):
        project = self.blocked_project()
        app = FastAPI()
        app.include_router(stories_router(self.service))
        client = TestClient(app)
        url = f"/api/stories/projects/{project['project_id']}/correct-and-continue"
        body = dict(expected_version=project["version"], unit_id="episode-1")
        self.gateway.entered.clear()
        self.gateway.release.clear()
        self.addCleanup(self.gateway.release.set)
        before = len(self.gateway.requests)
        self.assertEqual(client.post(url, json=body).status_code, 202)
        self.assertTrue(self.gateway.entered.wait(2))
        self.assertEqual(client.post(url, json=body).status_code, 409)
        self.service.workflow.pause(project["project_id"])
        self.gateway.release.set()
        project = self.settle(project)
        self.assertEqual(len(self.gateway.requests), before + 1)
        self.assertEqual(project["workflow"]["status"], "paused")
        self.assertNotIn("correction", project["workflow"])

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
        self.assertEqual([u["unit_id"] for u in last.get("reader_units", last.get("units_to_review", []))], ["episode-1", "episode-2"])


    def test_automatic_repair_ignores_warnings_and_next_review_sees_actual_changes(self):
        self.gateway.blocking = True
        self.gateway.warnings = True
        project = self.advance(self.create(count=1))
        self.assertEqual(project["workflow"]["status"], "blocked")
        requests = [json.loads(r.user_prompt) for r in self.gateway.requests]
        repair = next(c for c in requests if c["operation"] == "repair_episode")
        self.assertEqual([i["severity"] for i in repair["review_to_address"]["issues"]], ["blocking"])
        self.assertNotIn("Retirer le propriétaire", json.dumps(repair, ensure_ascii=False))
        self.assertTrue(all(i["level"] == "blocking" for i in repair["local_diagnostics"]))
        followup = requests[-1]["review_followup"][0]
        self.assertEqual(followup["unit_id"], "episode-1")
        self.assertEqual([i["severity"] for i in followup["previous_issues"]], ["blocking", "warning"])
        changed = followup["changes"][0]
        self.assertNotIn("Le refus est explicite.", changed["before"]["action"])
        self.assertIn("Le refus est explicite.", changed["after"]["action"])
        self.assertNotIn("ending_state", changed["after"])
        self.assertEqual(sum(c["operation"] == "repair_episode" for c in requests), 1)

    def test_warning_alone_does_not_launch_a_correction(self):
        self.gateway.warnings = True
        project = self.advance(self.create(count=1))
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertFalse(any(".repair_" in r.operation_id for r in self.gateway.requests))

    def test_question_preserves_automatic_block_and_explains_its_real_reason(self):
        self.gateway.blocking = True
        project = self.advance(self.create(count=1))
        before, flow, calls = deepcopy(project["document"]), deepcopy(project["workflow"]), len(self.gateway.requests)
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="episode-1", scene_index=None, instruction="Quel retour attends-tu ?", question=True)
        project = self.settle(project)
        self.assertEqual(project["document"], before)
        for key in ("mode", "status", "wait_target", "message", "approvals", "repairs"):
            self.assertEqual(project["workflow"][key], flow[key], key)
        self.assertEqual(project["workflow"]["budget_calls"], flow["budget_calls"] + 1)
        self.assertEqual(len(self.gateway.requests), calls + 1)
        context = json.loads(self.gateway.requests[-1].user_prompt)["workflow_context"]
        self.assertEqual(context["status"], "blocked")
        self.assertEqual(context["blocking_issues"][0]["problem"], "Un refus manque.")
        self.assertEqual(context["previous_step"]["operation"], "review_block")
        self.assertIn("ne promets aucune réécriture", self.gateway.requests[-1].system_prompt)

    def test_question_retry_keeps_the_pending_approval_and_original_context(self):
        project = self.advance(self.create("manual", 1))
        flow = deepcopy(project["workflow"])
        self.gateway.fail_operation = "discuss"
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="outline", scene_index=None, instruction="Pourquoi cette fin ?", question=True)
        project = self.settle(project)
        self.assertEqual(project["job"]["status"], "failed")
        self.gateway.fail_operation = None
        self.service.retry(project["project_id"], project["version"])
        project = self.settle(project)
        for key in ("mode", "status", "wait_target", "approvals", "repairs"):
            self.assertEqual(project["workflow"][key], flow[key], key)
        contexts = [json.loads(r.user_prompt)["workflow_context"] for r in self.gateway.requests if ".discuss@" in r.operation_id]
        self.assertEqual(contexts[0], contexts[1])
        calls = len(self.gateway.requests)
        project = self.advance(project)
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")
        self.assertEqual([r.operation_id.split(".")[2].split("@")[0] for r in self.gateway.requests[calls:]],
                         ["develop", "review_block"])

    def test_question_about_another_unit_neither_selects_it_nor_restarts_writing(self):
        project = self.advance(self.create())
        before = deepcopy(project["document"])
        calls = len(self.gateway.requests)
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="episode-1", scene_index=None, instruction="Ça me va.", question=True)
        project = self.settle(project)
        self.assertEqual(project["document"], before)
        self.assertEqual(project["workflow"]["mode"], "automatic")
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(len(self.gateway.requests), calls + 1)

    def test_cancelling_a_question_keeps_the_author_checkpoint(self):
        project = self.advance(self.create("manual", 1))
        before = deepcopy(project["document"])
        self.gateway.entered.clear()
        self.gateway.release.clear()
        self.addCleanup(self.gateway.release.set)
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="outline", scene_index=None, instruction="Pourquoi cette fin ?", question=True)
        self.assertTrue(self.gateway.entered.wait(2))
        self.service.cancel(project["project_id"])
        self.gateway.release.set()
        project = self.settle(project)
        self.assertEqual(project["job"]["status"], "cancelled")
        self.assertEqual(project["workflow"]["status"], "awaiting_author")
        self.assertEqual(project["workflow"]["wait_target"], "outline")
        self.assertEqual(project["document"], before)
        calls = len(self.gateway.requests)
        project = self.advance(project)
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")
        self.assertEqual(len(self.gateway.requests), calls + 2)

    def test_question_receives_the_technical_error_that_preceded_it(self):
        self.gateway.fail_operation = "develop"
        project = self.advance(self.create(count=1))
        self.assertEqual(project["workflow"]["status"], "blocked")
        self.gateway.fail_operation = None
        self.service.workflow.feedback(project["project_id"], expected_version=project["version"],
            unit_id="outline", scene_index=None, instruction="Pourquoi cet arrêt ?", question=True)
        project = self.settle(project)
        previous = json.loads(self.gateway.requests[-1].user_prompt)["workflow_context"]["previous_step"]
        self.assertEqual(previous["operation"], "develop")
        self.assertEqual(previous["error"], "Erreur de fixture à reprendre.")
        self.assertEqual(project["workflow"]["status"], "blocked")

    def test_new_fruit_names_are_checked_in_the_existing_outline_edit(self):
        project = self.create("manual", 1)
        project["visual_universe"] = "Fruits anthropomorphes"
        project = self.advance(self.service.store.save(project))
        self.assertEqual(len(self.gateway.requests), 2)
        contexts = [json.loads(r.user_prompt) for r in self.gateway.requests]
        self.assertEqual([c["fruit_naming"]["mode"] for c in contexts], ["invent", "check_new_cast"])
        for request in self.gateway.requests:
            self.assertIn("Bananito, Kiwina, Cerisa, Cerisetto, Noisettine", request.system_prompt)
            self.assertIn("Conserve les noms explicitement fournis", request.system_prompt)
            self.assertIn("Un univers humain, animal ou de gouttes", request.system_prompt)

    def test_existing_and_written_characters_are_exempt_from_the_new_naming_rule(self):
        project = self.advance(self.create("manual", 1))
        project["document"]["series_outline"]["characters"][0]["name"] = "Noisette"
        project["document"]["reviews"].pop("outline", None)
        project["job"]["operation"] = "edit_outline"
        project.pop("fruit_naming_version")
        before = deepcopy(project["document"])
        request = self.service._request(project, self.service.long_recipes.snapshot())
        self.assertEqual(json.loads(request.user_prompt)["fruit_naming"]["mode"], "preserve")
        self.assertNotIn("Bananito", request.system_prompt)
        self.assertEqual(project["document"], before)
        # A previously written cast is also protected even if its review is absent.
        project = self.advance(self.advance(self.create("manual", 1)))
        project["document"]["reviews"].pop("outline", None)
        project["job"]["operation"] = "edit_outline"
        request = self.service._request(project, self.service.long_recipes.snapshot())
        self.assertEqual(json.loads(request.user_prompt)["fruit_naming"]["mode"], "preserve")


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
