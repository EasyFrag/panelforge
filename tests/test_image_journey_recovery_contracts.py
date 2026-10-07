"""User-run regressions for the observed reverse Resume failures. All gateways are fakes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application import image_journey_reference_prompting as references
from panelforge.application.image_journey_reverse_prompting import REVERSE_POLICIES
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain.minimax_edit import journey_child_id
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_reverse as reverse_tests

ROOT = Path(__file__).resolve().parents[1]


class ContractGateway(reverse_tests.ReverseGateway):
    omit_finished = False
    invented_reference = False
    planning_verdict = None
    review_verdict = None

    def stream(self, request):
        if request.operation_id == "minimax.edit.assistance@1.0.0":
            inputs = json.loads(request.user_prompt)["CURRENT INPUTS"]["render_inputs"]
            if len(inputs) == 2 and (self.omit_finished or self.invented_reference):
                self.requests.append(request)
                prompt = "Based on <Picture 1>, remove the walls and stairs. Preserve the pillars and framing."
                if self.invented_reference:
                    prompt += " Use <Picture 3> for the textures."
                yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                    result=CompletionResult(request.model_id, json.dumps(dict(message="Retirer les murs.", prompt=prompt)),
                                            call_id="prompt-contract"))
                return
        for event in super().stream(request):
            if "reverse-progression" in request.operation_id and event.result:
                context = json.loads(request.user_prompt)
                verdict = self.review_verdict if context["reviewing_result"] else self.planning_verdict
                if verdict:
                    value = json.loads(event.result.content)
                    value["assessment"] = verdict
                    yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                        result=CompletionResult(request.model_id, json.dumps(value), call_id="planning-contract"))
                    continue
            yield event


class ReverseRecoveryTest(ImageJourneyFixture):
    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.3.0")
        self.gateway = ContractGateway()
        self.minimax.gateway = self.journeys.gateway = self.gateway

    def reverse(self, **values):
        return self.create_journey(**{"journey_direction": "reverse", "journey_version": "2", **values})

    def second_prompt(self):
        self.until("reviewing")
        self.journeys.advance(self.journey_id)
        return self.until("prompting")["steps"][-1]

    def test_missing_finished_tag_is_compiled_once_with_no_extra_llm_or_image_calls(self):
        self.gateway.omit_finished = True
        self.reverse()
        self.second_prompt()
        self.until("queueing")
        step = deepcopy(self.current_journey()["steps"][-1])
        child = self.minimax.get(journey_child_id(step["id"]))
        message = child["stages"][0]["messages"][-1]
        self.assertNotIn("<Picture 2>", json.loads(message["raw"])["prompt"])
        self.assertIn("<Picture 2>", message["prompt"])
        self.assertIn("only image to edit", message["prompt"])
        self.assertIn("outside the requested edit", message["prompt"])
        self.assertEqual(message["journey_reference_policy"], references.VERSION)
        self.assertIn("journey-reference", message["policy_version"])
        self.journeys = self.new_service()
        self.journeys.recover()
        self.resume_journey()
        result = self.until("completed")
        self.assertEqual(len(self.prompt_calls()), 2)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(result["steps"][-1]["prompt"], message["prompt"])

    def test_newline_only_resume_keeps_the_action_plan_and_prompt_retry(self):
        initial = self.reverse(intention="Revenir au terrain plat.\r\n\r\nConserver le décor.")
        step = self.second_prompt()
        self.gateway.malformed = True
        self.journeys.advance(self.journey_id)
        paused = self.current_journey()
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["phase"], "prompting")
        analyses = len(paused["analyses"])
        resumed = self.resume_journey(intention=initial["intention"].replace("\r\n", "\n"))
        self.assertEqual(resumed["phase"], "prompting")
        self.assertEqual(resumed["intent_revision"], 0)
        self.assertEqual(resumed["plan_revision"], 0)
        self.assertEqual(resumed["abandoned_steps"], [])
        self.assertEqual(resumed["steps"][-1]["id"], step["id"])
        self.assertNotEqual(resumed["steps"][-1]["prompt_request_id"], step["prompt_request_id"])
        self.assertEqual(len(resumed["analyses"]), analyses)
        self.gateway.malformed = False
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_real_intention_change_still_replans_without_rerendering_the_saved_image(self):
        self.reverse()
        original = self.second_prompt()
        self.journeys.pause(self.journey_id)
        resumed = self.resume_journey(intention="Retirer aussi la base en bois.")
        self.assertEqual(resumed["phase"], "planning")
        self.assertEqual(resumed["intent_revision"], 1)
        self.assertEqual(resumed["abandoned_steps"][-1]["id"], original["id"])
        self.assertEqual(len(resumed["steps"]), 1)
        self.assertTrue(resumed["steps"][0]["output_asset_id"])

    def test_already_stuck_in_planning_accepts_neutral_verdict_without_fabricating_a_review(self):
        self.reverse()
        self.second_prompt()
        self.journeys.pause(self.journey_id)
        self.resume_journey(intention="Même parcours, conserver le sol en bois.")
        self.journeys.pause(self.journey_id)
        before = deepcopy(self.current_journey()["steps"][0])
        self.journeys = self.new_service()
        self.gateway.planning_verdict = "usable"
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        current = self.current_journey()
        self.assertEqual(current["phase"], "ready")
        self.assertEqual(current["steps"][0], before)
        self.assertEqual(json.loads(current["analyses"][-1]["raw"])["assessment"], "usable")
        call = self.gateway.requests[-1]
        self.assertEqual(call.output_schema["properties"]["assessment"]["enum"], ["initial"])
        self.assertEqual(json.loads(call.user_prompt)["analysis_task"], "plan_next_edit_without_new_result")
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_a_real_generated_result_still_requires_a_review(self):
        self.reverse(count=1)
        self.until("reviewing")
        self.gateway.review_verdict = "initial"
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project["status"], "paused")
        self.assertIsNone(project["steps"][0]["review"])
        self.assertTrue(project["steps"][0]["output_asset_id"])
        schema = self.gateway.requests[-1].output_schema
        self.assertEqual(schema["properties"]["assessment"]["enum"], ["usable", "similar", "unusable"])
        self.assertEqual(schema["properties"]["next_action"], {"type": "null"})

    def test_an_invented_reference_is_still_refused_and_resume_retries_only_the_prompt(self):
        self.gateway.invented_reference = True
        self.reverse()
        self.second_prompt()
        self.journeys.advance(self.journey_id)
        paused = self.current_journey()
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(len(self.comfy.submitted), 1)
        child = self.minimax.get(journey_child_id(paused["steps"][-1]["id"]))
        self.assertEqual(child["stages"][0]["attempts"], [])
        self.gateway.invented_reference = False
        self.gateway.omit_finished = True
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)


class ReferenceCompilerTest(unittest.TestCase):
    def context(self):
        return dict(mode="edit", source_asset_id="current", guide=None, render_inputs=[
            dict(id="source", asset_id="current", tag="<Picture 1>"),
            dict(id="journey-finished", asset_id="finished", tag="<Picture 2>")])

    def test_rejects_missing_source_unknown_tags_and_foreign_reference_contracts(self):
        context = self.context()
        for prompt in ("Retirer les murs.", "Use <Picture 2>.", "Use <Picture 1> and <Picture 3>.",
                       "Use <image1> and <Picture 1>.", "Use <Picture 1>." + "x" * 24000):
            with self.subTest(prompt=prompt[:55]), self.assertRaises(ValueError):
                references.decode(json.dumps(dict(message="Demande", prompt=prompt)), context)
        for change in ("reordered", "foreign", "guide"):
            other = deepcopy(context)
            if change == "reordered":
                other["render_inputs"].reverse()
            elif change == "foreign":
                other["render_inputs"][1]["id"] = "ref-other"
            else:
                other["guide"] = {"mask_asset_id": "mask"}
            with self.subTest(change=change), self.assertRaises(ValueError):
                references.decode(json.dumps(dict(message="Demande", prompt="Edit <Picture 1>.")), other)

    def test_new_role_contract_does_not_relax_shared_minimax_validation(self):
        from panelforge.application import minimax_edit_assistance
        raw = json.dumps(dict(message="Demande", prompt="Edit <Picture 1>."))
        with self.assertRaises(ValueError):
            minimax_edit_assistance.decode(raw, self.context()["render_inputs"])
        reply, compiled = references.decode(raw, self.context())
        self.assertEqual(reply, "Demande")
        self.assertIn("<Picture 2>", compiled)
