"""User-run journey regressions using fake LLM and Comfy gateways only."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.image_journeys import ImageJourneyService, JourneyConflict
from panelforge.application.image_journey_rendering import MinimaxJourneyRenderer
from panelforge.application import image_journey_prompting as prompting
from panelforge.application.image_transitions import ImageTransitionService
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as policy
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.storage.image_journeys import LocalImageJourneyStore
from panelforge.infrastructure.storage.image_transitions import LocalImageTransitionStore
from test_minimax_edit import MinimaxFixture
from test_qwen_edit import Gateway, png


class JourneyGateway(Gateway):
    def __init__(self):
        super().__init__()
        self.assessment = "usable"
        self.progression_hook = None
        self.bad_progression = False
        self.truncated = False
        self.rewrite_plan = False

    def stream(self, request):
        if request.operation_id != prompting.OPERATION:
            yield from super().stream(request)
            return
        self.requests.append(request)
        context = json.loads(request.user_prompt)
        reviewing = context["reviewing_result"]
        milestones = context["milestones"] or ["Préparation", "Isolation", "Finitions"]
        destination = context["destination"] if context["existing_plan_locked"] else context["user_intention"] or "Un salon aménagé"
        if self.rewrite_plan and context["existing_plan_locked"]:
            milestones = ["Un autre chantier"]
        remaining = context["remaining_images"]
        done = min(context["total_new_images"] - remaining, len(milestones))
        if not remaining:
            done = len(milestones)
        assessment = self.assessment if reviewing else "initial"
        value = dict(destination=destination, milestones=milestones, completed_milestones=done,
            summary="Le décor visible est conservé ; le chantier progresse.",
            observation="État effectivement observé." if assessment != "unusable" else "Le point de vue est perdu.",
            assessment=assessment, next_action=None if not remaining or assessment == "unusable" else
                dict(title="Prochaine transformation", change="Installer une isolation nettement visible.",
                     preserve="Le cadrage, la porte et les travaux déjà réalisés.",
                     through_milestone=min(len(milestones), done + 1)))
        raw = "invalid {" if self.bad_progression else json.dumps(value, ensure_ascii=False)
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, raw)
        if self.progression_hook:
            self.progression_hook()
        yield CompletionStreamEvent(StreamEventKind.TRUNCATED if self.truncated else StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED, result=CompletionResult(request.model_id, raw, call_id="journey-call"))


class ImageJourneyTest(MinimaxFixture):
    def setUp(self):
        super().setUp()
        self.minimax = self.service
        self.gateway = JourneyGateway()
        self.minimax.gateway = self.gateway
        self.journey_store = LocalImageJourneyStore(self.temporary.name)
        self.transitions = ImageTransitionService(store=LocalImageTransitionStore(self.temporary.name),
            assets=self.assets, images=self.minimax.images, gateway=self.gateway, factory=None, sources=None)
        self.journeys = self.new_service()
        self.journey_id = None

    def new_service(self):
        return ImageJourneyService(store=self.journey_store, assets=self.assets, images=self.minimax.images,
            gateway=self.gateway, renderer=MinimaxJourneyRenderer(self.minimax), transitions=self.transitions)

    def create_journey(self, count=2, intention="Aménager la cave", command="create"):
        project = self.journeys.create(command=command, content=png(), intention=intention, count=count,
            progression_model_id="progression-vision", prompt_model_id="minimax-prompter")
        self.journey_id = project["id"]
        return project

    def current_journey(self):
        return self.journeys.get(self.journey_id)

    def resume_journey(self, **changes):
        project = self.current_journey()
        values = dict(version=project["version"], command=policy.identity("resume"), intention=project["intention"],
                      progression_model_id=project["progression_model_id"], prompt_model_id=project["prompt_model_id"])
        return self.journeys.resume(self.journey_id, **{**values, **changes})

    def render_current(self):
        step = self.current_journey()["steps"][-1]
        project = self.minimax.ensure_journey_step(step)
        stage = project["stages"][0]
        attempt = next(a for a in stage["attempts"] if a["request_id"] == step["render_request_id"])
        self.minimax.execute_attempt(project["id"], stage["id"], attempt["id"])

    def until(self, phase):
        for _ in range(60):
            project = self.current_journey()
            if project["phase"] == phase:
                return project
            self.assertNotEqual(project["status"], "paused", project["error"])
            if project["phase"] == "rendering":
                self.render_current()
            self.journeys.advance(self.journey_id)
        self.fail("The fake journey did not reach " + phase)

    def progression_calls(self):
        return [r for r in self.gateway.requests if r.operation_id == prompting.OPERATION]

    def prompt_calls(self):
        return [r for r in self.gateway.requests if r.operation_id == "minimax.edit.assistance@1.0.0"]

    def test_real_outputs_feed_next_source_and_last_image_is_reviewed(self):
        initial = self.create_journey()
        project = self.until("completed")
        self.assertEqual(len(project["steps"]), 2)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
        self.assertEqual(len(self.progression_calls()), 3)
        self.assertEqual(project["steps"][0]["source_asset_id"], initial["source_asset_id"])
        self.assertEqual(project["steps"][1]["source_asset_id"], project["steps"][0]["output_asset_id"])
        self.assertEqual(project["steps"][-1]["review"]["assessment"], "usable")
        self.assertIsNone(project["next_action"])
        self.assertEqual(len(self.journeys.sequence(self.journey_id)["frames"]), 3)
        self.assertTrue(all(r.model_id == "progression-vision" for r in self.progression_calls()))
        self.assertTrue(all(r.model_id == "minimax-prompter" for r in self.prompt_calls()))
        review = self.progression_calls()[1]
        self.assertEqual(review.images[1].content, self.assets.read_bytes(project["steps"][0]["output_asset_id"]))
        self.assertEqual(len(self.progression_calls()[-1].images), 3)
        self.assertEqual([p["id"] for p in self.minimax.list()], [self.project_id])

    def test_no_intention_chooses_a_destination_without_human_confirmation(self):
        self.create_journey(intention="")
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project["destination"], "Un salon aménagé")
        self.assertEqual(project["status"], "running")
        self.assertTrue(project["milestones"])

    def test_similar_image_continues_without_replay_or_extending_the_budget(self):
        self.gateway.assessment = "similar"
        self.create_journey()
        project = self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertTrue(all(s["review"]["assessment"] == "similar" for s in project["steps"]))
        context = json.loads(self.progression_calls()[-1].user_prompt)
        self.assertEqual(context["recent_actions"][0]["review"]["assessment"], "similar")
        self.assertIn("peu de changement", project["warning"])

    def test_unusable_result_is_saved_and_blocks_until_an_explicit_resume(self):
        self.gateway.assessment = "unusable"
        initial = self.create_journey()
        self.until("reviewing")
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project["status"], "paused")
        self.assertTrue(project["steps"][0]["output_asset_id"])
        self.assertEqual(project["current_asset_id"], initial["source_asset_id"])
        self.assertEqual(len(self.journeys.sequence(self.journey_id)["frames"]), 1)
        calls = len(self.gateway.requests)
        self.journeys.advance(self.journey_id)
        self.assertEqual(len(self.gateway.requests), calls)
        self.gateway.assessment = "usable"
        self.resume_journey(intention="Conserver cet état et aménager le décor")
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_pause_during_analysis_keeps_the_plan_without_starting_a_prompt(self):
        self.create_journey()
        self.gateway.progression_hook = lambda: self.journeys.pause(self.journey_id)
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual((project["status"], project["phase"]), ("paused", "ready"))
        self.assertTrue(project["destination"])
        self.assertEqual(self.prompt_calls(), [])
        self.assertEqual(self.comfy.submitted, [])
        self.gateway.progression_hook = None
        self.resume_journey(intention="Créer un atelier de menuiserie")
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["destination"], "Créer un atelier de menuiserie")
        self.assertFalse(json.loads(self.progression_calls()[-1].user_prompt)["existing_plan_locked"])

    def test_pause_during_prompt_does_not_queue_a_render_and_reuses_the_prompt(self):
        self.create_journey(count=1)
        self.until("prompting")
        self.gateway.hook = lambda: self.journeys.pause(self.journey_id)
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual((project["status"], project["phase"]), ("paused", "queueing"))
        self.assertTrue(project["steps"][0]["prompt"])
        self.assertEqual(len(self.minimax._render_queue), 0)
        self.gateway.hook = None
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.prompt_calls()), 1)

    def test_pause_during_render_collects_it_without_cancelling_or_starting_the_next(self):
        self.create_journey()
        self.until("rendering")
        self.assertEqual(self.journeys.pause(self.journey_id)["status"], "pausing")
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.comfy.cancelled, [])
        self.render_current()
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual((project["status"], project["phase"]), ("paused", "reviewing"))
        self.assertTrue(project["steps"][0]["output_asset_id"])
        self.assertIsNone(project["steps"][0]["review"])
        self.assertEqual(len(self.progression_calls()), 1)
        self.resume_journey(intention="Un salon avec des murs verts")
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_restart_collects_an_existing_render_but_waits_for_resume_to_continue(self):
        self.create_journey(count=1)
        self.until("rendering")
        self.journeys = self.new_service()
        self.journeys.recover()
        self.assertEqual(self.current_journey()["status"], "paused")
        self.render_current()
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["phase"], "reviewing")
        self.assertEqual(len(self.progression_calls()), 1)
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_interrupted_journal_after_prompt_success_does_not_repeat_the_call(self):
        self.create_journey(count=1)
        self.until("prompting")
        step = self.current_journey()["steps"][-1]
        self.journeys.renderer.prepare(step)  # Simulate a crash before the journey stores this result.
        self.journeys = self.new_service()
        self.journeys.recover()
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.prompt_calls()), 1)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_duplicate_queue_request_after_lost_confirmation_still_renders_once(self):
        self.create_journey(count=1)
        self.until("queueing")
        step = self.current_journey()["steps"][-1]
        first = self.journeys.renderer.queue(step)
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["steps"][-1]["attempt_id"], first["id"])
        self.assertEqual(len(self.minimax._render_queue), 1)
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_bad_analysis_is_retained_without_any_render_and_requires_manual_retry(self):
        self.gateway.bad_progression = True
        self.create_journey(count=1)
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project["status"], "paused")
        self.assertEqual(project["analyses"][-1]["raw"], "invalid {")
        self.assertEqual(self.comfy.submitted, [])
        self.gateway.bad_progression = False
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_bad_minimax_prompt_does_not_render_and_can_be_retried_on_resume(self):
        self.gateway.malformed = True
        self.create_journey(count=1)
        self.until("prompting")
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["status"], "paused")
        self.assertEqual(self.comfy.submitted, [])
        self.gateway.malformed = False
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.prompt_calls()), 2)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_failed_render_waits_for_explicit_resume_and_preserves_the_prompt(self):
        self.create_journey(count=1)
        self.until("rendering")
        step = self.current_journey()["steps"][-1]
        self.minimax._attempt_update(step["minimax_project_id"], step["minimax_stage_id"], step["attempt_id"],
                                     status="failed", error="Fake renderer unavailable")
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["status"], "paused")
        before = len(self.minimax._render_queue)
        self.journeys.advance(self.journey_id)
        self.assertEqual(len(self.minimax._render_queue), before)
        self.resume_journey()
        self.until("completed")
        self.assertEqual(len(self.prompt_calls()), 1)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_changed_intention_discards_only_the_unrendered_pending_instruction(self):
        self.create_journey(count=1)
        self.until("queueing")
        old_step = self.current_journey()["steps"][-1]["id"]
        self.journeys.pause(self.journey_id)
        self.resume_journey(intention="Créer une bibliothèque")
        self.until("completed")
        project = self.current_journey()
        self.assertNotEqual(project["steps"][0]["id"], old_step)
        self.assertEqual(project["abandoned_steps"][0]["id"], old_step)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_plan_rewrite_without_new_intention_is_rejected(self):
        self.create_journey()
        self.until("reviewing")
        self.gateway.rewrite_plan = True
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project["status"], "paused")
        self.assertEqual(project["milestones"], ["Préparation", "Isolation", "Finitions"])
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_truncated_analysis_never_applies_even_if_json_is_complete(self):
        self.gateway.truncated = True
        self.create_journey()
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()["status"], "paused")
        self.assertEqual(self.current_journey()["destination"], "")
        self.assertEqual(self.comfy.submitted, [])

    def test_creation_and_resume_commands_are_idempotent_with_revision_conflicts(self):
        project = self.create_journey()
        self.assertEqual(self.create_journey()["id"], project["id"])
        self.assertEqual(len(self.journeys.list()), 1)
        with self.assertRaises(JourneyConflict):
            self.create_journey(intention="Une autre commande")
        paused = self.journeys.pause(self.journey_id)
        body = dict(version=paused["version"], command="resume-one", intention=paused["intention"],
                    progression_model_id=paused["progression_model_id"], prompt_model_id=paused["prompt_model_id"])
        first = self.journeys.resume(self.journey_id, **body)
        self.assertEqual(self.journeys.resume(self.journey_id, **body)["version"], first["version"])
        self.journeys.pause(self.journey_id)
        with self.assertRaises(JourneyConflict):
            self.journeys.resume(self.journey_id, **{**body, "command":"stale-command"})

    def test_transition_handoff_is_ordered_idempotent_and_still_requires_review(self):
        self.create_journey()
        project = self.until("completed")
        calls = len(self.gateway.requests)
        first = self.journeys.prepare_transitions(self.journey_id)
        second = self.journeys.prepare_transitions(self.journey_id)
        self.assertEqual(first, second)
        target = self.transitions.public(self.transitions.get(first["project_id"]))
        self.assertEqual([f["asset_id"] for f in target["frames"]],
            [project["source_asset_id"], *[s["output_asset_id"] for s in project["steps"]]])
        self.assertEqual(len(target["transitions"]), 2)
        self.assertTrue(all(not t["reviewed"] for t in target["transitions"]))
        self.assertEqual(target["deliveries"], [])
        self.assertEqual(len(self.gateway.requests), calls)

    def test_journey_can_complete_without_the_transition_workshop(self):
        self.journeys.transitions = None
        self.create_journey(count=1)
        project = self.until("completed")
        public = self.journeys.public(project)
        self.assertFalse(public["transitions_available"])
        self.assertEqual(len(self.journeys.sequence(self.journey_id)["frames"]), 2)

    def test_http_create_pause_resume_and_validation_do_not_depend_on_a_browser_loop(self):
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        prefix = "/api/image-lab/journeys"
        with TestClient(app) as client:
            data = dict(command="http-create", intention="", count="2",
                        progression_model_id="progression-vision", prompt_model_id="minimax-prompter")
            response = client.post(prefix + "/projects", data=data, files={"source_image":("start.png", png(), "image/png")})
            self.assertEqual(response.status_code, 201, response.text)
            project = response.json()["project"]
            self.assertEqual(project["status"], "running")
            self.assertEqual(project["transferable_images"], 1)
            self.assertEqual(self.gateway.requests, [])
            url = prefix + "/projects/" + project["id"]
            paused = client.post(url + "/pause").json()["project"]
            self.assertEqual(paused["status"], "paused")
            response = client.post(url + "/resume", json=dict(version=paused["version"], command="http-resume",
                intention="Aménager la cave", progression_model_id="progression-vision", prompt_model_id="minimax-prompter"))
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(client.get(url + "/sequence").json()["schema_version"], 1)
            invalid = client.post(prefix + "/projects", data={**data, "count":"0"},
                files={"source_image":("start.png", png(), "image/png")})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(client.get(prefix + "/projects/../../escape").status_code, 404)

    def test_store_rejects_foreign_ids_and_configuration_rejects_boolean_count(self):
        with self.assertRaises(ValueError):
            self.journey_store.get("../elsewhere")
        with self.assertRaises(ValueError):
            self.create_journey(count=True)
