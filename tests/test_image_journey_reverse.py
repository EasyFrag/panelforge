"""User-run reverse journey regressions; fake LLM/Comfy only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application import image_journey_policies as policies
from panelforge.application import image_journey_prompting as forward
from panelforge.application.image_journey_reverse_prompting import REVERSE_POLICIES
from panelforge.application.image_journeys import JourneyConflict
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as policy
from panelforge.domain.minimax_edit import MinimaxEditSettings, journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_edits as manual_tests
from test_qwen_edit import png

ROOT = Path(__file__).resolve().parents[1]


class ReverseGateway(manual_tests.EditGateway):
    def stream(self, request):
        if not request.operation_id.startswith("image.journey.reverse-"):
            yield from super().stream(request)
            return
        self.requests.append(request)
        context = json.loads(request.user_prompt)
        if "manual-review" in request.operation_id:
            value = dict(assessment="usable", observation="État intermédiaire observé.")
        elif "manual-plan" in request.operation_id:
            value = dict(title="Structure partielle", change="Remettre uniquement la moitié de l’ossature.",
                         preserve="Le cadrage et les bâtiments voisins.")
        else:
            remaining = context["remaining_images"]
            milestones = context["milestones"] or ["Structure dégagée", "Terrain plat"]
            done = min(len(milestones), context["total_new_images"] - remaining)
            value = dict(destination=context["destination"] or "Terrain plat sans bâtiment",
                milestones=milestones, completed_milestones=done,
                summary="Les parties retirées restent absentes.", observation="État réellement observé.",
                assessment="usable" if context["reviewing_result"] else "initial",
                next_action=None if not remaining else dict(title="Retrait visible",
                    change="Retirer le bâtiment et restituer le sol plat." if remaining == 1 else "Retirer les façades.",
                    preserve="Le cadrage et les bâtiments voisins.", through_milestone=min(len(milestones), done + 1)))
        raw = "invalid" if self.bad_manual_review and "manual-review" in request.operation_id else json.dumps(value)
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, raw, call_id="reverse-call"))


class ImageJourneyReverseTest(ImageJourneyFixture):
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    render_operation = manual_tests.ImageJourneyEditsTest.render_operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.3.0")
        self.gateway = ReverseGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def reverse(self, **values):
        return self.create_journey(**{"journey_direction": "reverse", "journey_version": "2", **values})

    def test_default_and_legacy_creation_retries_preserve_forward_contract(self):
        project = self.create_journey(count=1)
        self.assertEqual(project["journey_direction"], "forward")
        self.assertEqual(self.create_journey(count=1, journey_direction="forward"), project)
        with self.assertRaises(JourneyConflict):
            self.reverse(count=1, journey_version="1")
        project.pop("journey_direction")
        config = policy.configuration(project["intention"], 1, "progression-vision", "minimax-prompter")
        config.update(auto_mask=False, journey_version="1")
        project["creation_key"] = policy.fingerprint(dict(config=config, source=hashlib.sha256(png()).hexdigest()))
        self.journey_store.save(project)
        path = self.journey_store._path(project["id"])
        original = path.read_bytes()
        self.assertEqual(self.journeys.public(project)["journey_direction"], "forward")
        self.assertEqual(self.create_journey(count=1, journey_direction="forward"), project)
        self.assertEqual(path.read_bytes(), original)
        self.assertIs(policies.progression(project), forward)

    def test_invalid_direction_and_old_workflow_fail_before_creating_a_journey(self):
        for value in ("", "backward", 1, True, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.create_journey(journey_direction=value)
        self.minimax.workflow = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.2.0")
        with self.assertRaisesRegex(ValueError, "1.3.0"):
            self.reverse()
        self.assertEqual(self.journeys.list(), [])
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.comfy.submitted, [])

    def test_chain_freezes_finished_reference_and_uploads_native_pixels(self):
        initial = self.reverse()
        self.assertFalse(initial["auto_mask"])
        self.assertEqual(self.create_journey(journey_version=None), initial)
        self.until("queueing")
        self.journeys = self.new_service()
        result = self.until("completed")
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
        analyses = [r for r in self.gateway.requests if "reverse-progression" in r.operation_id]
        self.assertEqual(len(analyses), 3)
        self.assertEqual(json.loads(analyses[-1].user_prompt)["remaining_images"], 0)
        self.assertIsNone(result["next_action"])
        self.assertTrue(result["steps"][-1]["review"])
        upload = 0
        slots = self.minimax.workflow.manifest["image_slots"]
        for index, step in enumerate(result["steps"]):
            self.assertEqual(step["journey_direction"], "reverse")
            self.assertEqual(step["finished_reference_asset_id"], initial["source_asset_id"])
            expected = [initial["source_asset_id"]] if index == 0 else [
                result["steps"][index - 1]["output_asset_id"], initial["source_asset_id"]]
            child = self.minimax.get(journey_child_id(step["id"]))
            attempt = child["stages"][0]["attempts"][-1]
            self.assertEqual([r["asset_id"] for r in attempt["context"]["render_inputs"]], expected)
            self.assertEqual([r["tag"] for r in attempt["context"]["render_inputs"]],
                             ["<Picture 1>"] if index == 0 else ["<Picture 1>", "<Picture 2>"])
            self.assertEqual(step["settings"]["reference_mode"], "native")
            self.assertEqual(step["settings"]["steps"], 18)
            graph = self.comfy.submitted[index]
            encoder = graph[self.minimax.workflow.manifest["conditioning_node"]]["inputs"]
            for slot, asset_id in zip(slots, expected):
                self.assertNotIn(slot["scale_node"], graph)
                self.assertEqual(encoder[slot["input"]], [slot["load_node"], 0])
                self.assertEqual(self.comfy.uploads[upload][0], self.assets.read_bytes(asset_id))
                upload += 1
        self.assertEqual(len(self.comfy.uploads), 3)
        self.assertIn("FINISHED_REFERENCE", analyses[-1].images[-1].label)
        frames = self.journeys.sequence(self.journey_id)["frames"]
        self.assertEqual([f["asset_id"] for f in frames],
                         [initial["source_asset_id"], *[s["output_asset_id"] for s in result["steps"]]])

    def test_single_step_v1_reverse_uses_one_reference_without_extra_output(self):
        self.reverse(count=1, journey_version="1")
        result = self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual(len(self.comfy.uploads), 1)
        call = next(r for r in self.gateway.requests if "reverse-progression" in r.operation_id)
        self.assertEqual(call.operation_id, REVERSE_POLICIES["1"].OPERATION)
        self.assertIn("With one output, go directly to flat ground.", call.system_prompt)
        self.assertNotIn("<Picture 2>", self.prompt_calls()[0].user_prompt)
        self.assertTrue(result["steps"][-1]["review"])

    def test_manual_review_retry_keeps_reference_prompt_and_existing_render(self):
        self.reverse(count=1)
        self.until("completed")
        self.start_operation(intention="Retrouver une structure partielle.")
        self.operation_until("reviewing")
        self.gateway.bad_manual_review = True
        self.journeys.edits.advance(self.journey_id)
        paused = deepcopy(self.operation())
        self.assertEqual(paused["status"], "paused")
        calls, renders = len(self.prompt_calls()), len(self.comfy.submitted)
        self.gateway.bad_manual_review = False
        self.journeys = self.new_service()
        self.journeys.edits.control(self.journey_id, paused["id"], action="resume")
        self.operation_until("completed")
        self.assertEqual(self.operation()["finished_reference_asset_id"], paused["finished_reference_asset_id"])
        self.assertEqual(self.operation()["output_asset_id"], paused["output_asset_id"])
        self.assertEqual(len(self.prompt_calls()), calls)
        self.assertEqual(len(self.comfy.submitted), renders)

    def test_insertion_sees_neighbors_and_finished_image_and_keeps_neighbors(self):
        self.reverse()
        original = deepcopy(self.until("completed")["steps"])
        op = self.start_operation("insert", after_frame_id=original[0]["id"], before_frame_id=original[1]["id"],
                                  intention="Une moitié de l’ossature avant le terrain plat.")
        self.operation_until("completed")
        project = self.current_journey()
        self.assertEqual(project["steps"], original)
        self.assertEqual(project["count"], 2)
        self.assertEqual(op["source_asset_id"], original[1]["output_asset_id"])
        plan = next(r for r in self.gateway.requests if "reverse-manual-plan" in r.operation_id)
        self.assertEqual(len(plan.images), 3)
        self.assertIn("MORE built than LATER", plan.system_prompt)
        self.assertEqual(plan.images[-1].content, self.assets.read_bytes(project["source_asset_id"]))
        self.assertEqual([s["id"] for s in policy.ordered_steps(project)],
                         [original[0]["id"], op["id"], original[1]["id"]])
        inputs = json.loads(self.prompt_calls()[-1].user_prompt)["CURRENT INPUTS"]["render_inputs"]
        self.assertEqual([r["asset_id"] for r in inputs], [op["source_asset_id"], project["source_asset_id"]])

    def test_existing_child_reference_cannot_be_rebound_on_retry(self):
        self.reverse()
        self.until("reviewing")
        self.journeys.advance(self.journey_id)
        self.until("queueing")
        step = deepcopy(self.current_journey()["steps"][-1])
        child = self.minimax.ensure_journey_step(step)
        step["finished_reference_asset_id"] = step["source_asset_id"]
        with self.assertRaises(ValueError):
            self.minimax.ensure_journey_step(step)
        self.assertEqual(self.minimax.get(child["id"])["stages"][0]["references"], child["stages"][0]["references"])

    def test_native_multi_reference_graph_preserves_legacy_paths(self):
        old = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.2.0")
        new = self.minimax.workflow
        values = dict(images=["source.png"], prompt="Edit <Picture 1>.", dimensions=(1344, 2368),
                      composition=False, output_prefix="regression")
        for settings in (MinimaxEditSettings(), MinimaxEditSettings(resolution="source", reference_mode="native")):
            self.assertEqual(new.build(**values, settings=settings), old.build(**values, settings=settings))
        for count in (2, 9):
            request = {**values, "images": [f"{i}.png" for i in range(count)],
                       "prompt": "Use " + ", ".join(f"<Picture {i}>" for i in range(1, count + 1))}
            settings = MinimaxEditSettings(resolution="source", reference_mode="native")
            with self.assertRaises(ValueError):
                old.build(**request, settings=settings)
            graph = new.build(**request, settings=settings)
            for slot in new.manifest["image_slots"][:count]:
                self.assertNotIn(slot["scale_node"], graph)
                self.assertEqual(graph[new.manifest["conditioning_node"]]["inputs"][slot["input"]], [slot["load_node"], 0])

    def test_http_direction_is_validated_and_frozen_across_resume(self):
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        prefix = "/api/image-lab/journeys"
        with TestClient(app) as client:
            self.assertEqual(client.get(prefix + "/spec").json()["default_journey_direction"], "forward")
            body = dict(command="reverse-api", count="2", progression_model_id="vision", prompt_model_id="writer",
                        journey_direction="reverse", journey_version="2")
            files = {"source_image": ("finished.png", png(), "image/png")}
            invalid = client.post(prefix + "/projects", data={**body, "journey_direction": "unknown"}, files=files)
            self.assertEqual(invalid.status_code, 422)
            response = client.post(prefix + "/projects", data=body, files=files)
            self.assertEqual(response.status_code, 201, response.text)
            project = response.json()["project"]
            self.assertEqual(project["journey_direction"], "reverse")
            url = prefix + "/projects/" + project["id"]
            paused = client.post(url + "/pause").json()["project"]
            resume = dict(version=paused["version"], command="resume", intention="Terrain plat.",
                          progression_model_id="vision", prompt_model_id="writer")
            self.assertEqual(client.post(url + "/resume", json={**resume, "journey_direction": "forward"}).status_code, 422)
            resumed = client.post(url + "/resume", json=resume)
            self.assertEqual(resumed.status_code, 202, resumed.text)
            self.assertEqual(resumed.json()["project"]["journey_direction"], "reverse")
        self.assertEqual(self.gateway.requests, [])
