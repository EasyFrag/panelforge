"""User-run prompt/render chaining regressions; fake LLM and Comfy gateways only."""
from copy import deepcopy
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.domain.minimax_edit import DEFAULT_ASSISTANT_MODEL
from panelforge.features.lab.minimax_edit_web import minimax_edit_router
from test_minimax_edit import MinimaxFixture


class MinimaxPromptRenderTest(MinimaxFixture):
    def begin(self, request_id="automatic"):
        stage = self.update(draft="Recolore uniquement le mur.")
        _, message_id = self.service.begin_message(self.project_id, self.stage_id,
            revision=stage["revision"], request_id=request_id, render_after_prompt=True)
        return message_id

    def execute(self, message_id):
        self.service.execute_message(self.project_id, self.stage_id, message_id)
        return next(m for m in self.current()["messages"] if m["id"] == message_id)

    def test_default_model_is_local_gemma_and_explicit_choice_survives_restart(self):
        self.assertEqual(self.current()["model_id"], DEFAULT_ASSISTANT_MODEL)
        self.assertEqual(self.qwen.get(self.qwen_project_id)["stages"][0]["model_id"], "")
        self.update(model_id="chosen-by-user")
        self.service.restart_stage(self.project_id, self.stage_id,
            revision=self.current()["revision"], request_id="restart")
        self.assertEqual(self.current()["model_id"], "chosen-by-user")

    def test_http_create_prompt_queues_one_render_without_browser_followup(self):
        app = FastAPI()
        app.include_router(minimax_edit_router(self.service))
        stage = self.update(draft="Recolore le mur.")
        url = f"/api/image-lab/minimax-edit/projects/{self.project_id}/stages/{self.stage_id}/messages"
        body = {"revision": stage["revision"], "request_id": "one-click"}
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/image-lab/minimax-edit/models").json()["default_model_id"],
                             DEFAULT_ASSISTANT_MODEL)
            self.assertEqual(client.post(url, json=body).status_code, 202)
            current = self.current()
            self.assertEqual(len(current["attempts"]), 1)
            message, attempt = current["messages"][-1], current["attempts"][-1]
            self.assertEqual(message["status"], "succeeded")
            self.assertEqual(message["auto_render"]["status"], "queued")
            self.assertEqual(message["auto_render"]["attempt_id"], attempt["id"])
            self.assertEqual(attempt["prompt"], message["prompt"])
            self.assertEqual(attempt["status"], "queued")
            self.assertEqual(attempt["settings"], message["auto_render"]["settings"])
            self.assertEqual(self.gateway.requests[-1].model_id, DEFAULT_ASSISTANT_MODEL)
            # The original revision is stale, but retrying the same command is idempotent.
            self.assertEqual(client.post(url, json=body).status_code, 202)
        self.service.execute_message(self.project_id, self.stage_id, message["id"])
        self.assertEqual(len(self.current()["attempts"]), 1)
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(len(self.service._render_queue), 1)
        self.assertEqual(self.comfy.submitted, [])

    def test_invalid_llm_response_does_not_queue_any_render(self):
        self.gateway.malformed = True
        message = self.execute(self.begin())
        self.assertEqual(message["status"], "failed")
        self.assertEqual(message["auto_render"]["status"], "skipped")
        self.assertEqual(self.current()["attempts"], [])

    def test_recovering_interrupted_prompt_does_not_relaunch_its_automatic_render(self):
        self.gateway.fail_after_delta = True
        message = self.execute(self.begin())
        self.assertEqual(message["status"], "failed")
        self.service.recover_message(self.project_id, self.stage_id, message["id"],
                                    revision=self.current()["revision"])
        self.assertTrue(self.service.public(self.service.get(self.project_id))["stages"][0]["prompt_ready"])
        self.assertEqual(self.current()["attempts"], [])

    def test_changed_references_prevent_the_original_prompt_from_triggering_a_render(self):
        message_id = self.begin()
        self.gateway.hook = lambda: self.reference("Nouvelle référence", "render")
        message = self.execute(message_id)
        self.assertEqual(message["status"], "succeeded")
        self.assertFalse(message["applied"])
        self.assertEqual(message["auto_render"]["status"], "skipped")
        self.assertEqual(self.current()["attempts"], [])

    def test_changed_settings_keep_the_prompt_available_without_rendering(self):
        message_id = self.begin()
        settings = {**deepcopy(self.current()["settings"]), "steps": 21}
        self.gateway.hook = lambda: self.update(settings=settings)
        message = self.execute(message_id)
        self.assertEqual(message["status"], "succeeded")
        self.assertTrue(message["applied"])
        self.assertEqual(message["auto_render"]["status"], "skipped")
        self.assertEqual(self.current()["settings"]["steps"], 21)
        self.assertEqual(self.current()["attempts"], [])

    def test_new_draft_prevents_rendering_the_previous_request(self):
        message_id = self.begin()
        self.gateway.hook = lambda: self.update(draft="Attends, utilise plutôt du bleu.")
        message = self.execute(message_id)
        self.assertEqual(message["status"], "succeeded")
        self.assertEqual(message["auto_render"]["status"], "failed")
        self.assertIn("bleu", self.current()["draft"])
        self.assertEqual(self.current()["attempts"], [])

    def test_queue_failure_does_not_erase_or_reject_the_accepted_prompt(self):
        message_id = self.begin()
        with patch.object(self.service, "queue_attempt", side_effect=RuntimeError("queue unavailable")):
            message = self.execute(message_id)
        self.assertEqual(message["status"], "succeeded")
        self.assertEqual(self.current()["prompt"], message["prompt"])
        self.assertEqual(message["auto_render"]["status"], "failed")
        self.assertIn("queue unavailable", message["auto_render"]["error"])
        self.service.execute_message(self.project_id, self.stage_id, message_id)
        self.assertEqual(self.current()["attempts"], [])
        self.assertEqual(len(self.gateway.requests), 1)

    def test_next_message_waits_for_the_current_automatic_render(self):
        self.execute(self.begin())
        stage = self.update(draft="Une autre modification.")
        with self.assertRaisesRegex(ValueError, "fin du rendu"):
            self.service.begin_message(self.project_id, self.stage_id,
                revision=stage["revision"], request_id="second", render_after_prompt=True)
        self.assertEqual(len(self.current()["messages"]), 1)
        self.assertEqual(len(self.current()["attempts"]), 1)
