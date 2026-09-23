"""HTTP roles and persistence; no external calls or worker are started."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.features.lab.qwen_edit_web import qwen_edit_router
from test_qwen_edit import QwenEditFixture, png


class QwenEditWebTest(QwenEditFixture):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(qwen_edit_router(self.service))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.url = f"/api/image-lab/qwen-edit/projects/{self.project_id}/stages/{self.stage_id}"

    def test_upload_defaults_to_assistant_and_explicit_promotion_invalidates_prompt(self):
        self.update(prompt="Recolor the wall.")
        response = self.client.post(self.url + "/references", data={"revision": self.current()["revision"], "name": "Inspiration"},
            files={"image": ("palette.png", png("yellow"), "image/png")})
        self.assertEqual(response.status_code, 201, response.text)
        stage = response.json()["project"]["stages"][0]
        self.assertEqual(stage["references"][0]["usage"], "assistant")
        self.assertEqual(len(stage["render_inputs"]), 1)
        stage["references"][0]["usage"] = "render"
        response = self.client.patch(self.url, json={"revision": stage["revision"], "changes": {"references": stage["references"]}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["project"]["stages"][0]["render_inputs"]), 2)
        self.assertFalse(response.json()["project"]["stages"][0]["prompt_ready"])
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.comfy.submitted, [])

    def test_conflicting_autosave_returns_409_and_keeps_the_user_draft(self):
        revision = self.current()["revision"]
        self.update(draft="Conserver ceci")
        response = self.client.patch(self.url, json={"revision": revision, "changes": {"draft": "Périmé"}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.current()["draft"], "Conserver ceci")

    def test_source_upload_and_composition_creation_are_distinct(self):
        response = self.client.post("/api/image-lab/qwen-edit/projects", data={"name": "Duo", "composition": "true"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["project"]["stages"][0]["source_asset_id"])
        response = self.client.post("/api/image-lab/qwen-edit/projects", data={"name": "Sans source"})
        self.assertEqual(response.status_code, 422)

    def test_generate_endpoint_queues_only_and_does_not_make_a_model_call(self):
        self.update(prompt="Recolor only the wall.")
        response = self.client.post(self.url + "/attempts", json={"revision": self.current()["revision"], "request_id": "web-render"})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["project"]["stages"][0]["attempts"][0]["status"], "queued")
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.comfy.submitted, [])

    def test_message_endpoint_runs_one_fake_call_and_exposes_the_received_trace(self):
        self.update(draft="Recolore le mur.", model_id="fake-vision")
        response = self.client.post(self.url + "/messages", json={"revision": self.current()["revision"], "request_id": "web-message"})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(len(self.gateway.requests), 1)
        message = self.current()["messages"][0]
        detail = self.client.get(self.url + "/messages/" + message["id"])
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["message"]["raw"])
        self.assertTrue(detail.json()["message"]["reasoning"])

    def test_disabled_service_explains_setup(self):
        app = FastAPI()
        app.include_router(qwen_edit_router(None))
        with TestClient(app) as client:
            response = client.get("/api/image-lab/qwen-edit/spec")
        self.assertEqual(response.status_code, 503)
