"""User-run route/contract checks; no model or rendering service."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.episodes import EpisodeConflict
from panelforge.features.lab.episodes_web import episodes_router
from panelforge.features.lab.web import Krea2AssistedAttemptBody, H3RenderAttemptBody


class EpisodeLocalizationWebTest(unittest.TestCase):
    def setUp(self):
        self.service = NS(localization_catalog=Mock(return_value={"sources": [], "groups": []}),
            create_localization=Mock(return_value={"group_id": "language-1", "episode_ids": ["copy"]}),
            start_localization=Mock(return_value={"episode_ids": ["copy"]}),
            save_localized_dialogues=Mock(return_value={"episode_id": "copy"}))
        app = FastAPI()
        app.include_router(episodes_router(self.service, serialize_image_project=lambda p: p,
            serialize_render_project=lambda p: p, validate_image=lambda b: "image/png",
            image_body=Krea2AssistedAttemptBody, render_body=H3RenderAttemptBody))
        self.client = TestClient(app)

    def test_copy_contract_passes_explicit_source_ids_and_language(self):
        body = dict(language="English", model_id="local::gemma", request_id="copy-request",
            selections=[dict(episode_id="source", scenes=[dict(scene_id="scene", preparation_id="prep",
                project_id="render", attempt_id="attempt", token="a" * 64)])])
        response = self.client.post("/api/episodes/source/localizations", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        self.service.create_localization.assert_called_once_with("source", **body)
        response = self.client.post("/api/episodes/source/localizations", json={**body, "rewrite_scene": True})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.service.create_localization.call_count, 1)

    def test_start_exposes_no_plan_or_writer_mode_and_propagates_conflicts(self):
        body = dict(expected_revisions={"copy": 1}, model_id="local::gemma", request_id="translate-request", mode="translate")
        self.assertEqual(self.client.post("/api/episodes/copy/localizations/start", json=body).status_code, 202)
        self.assertEqual(self.client.post("/api/episodes/copy/localizations/start", json={**body, "mode": "rewrite"}).status_code, 422)
        self.service.start_localization.side_effect = EpisodeConflict("La traduction a changé.")
        self.assertEqual(self.client.post("/api/episodes/copy/localizations/start", json=body).status_code, 409)

    def test_review_update_and_lightweight_polling(self):
        body = dict(expected_revision=2, lines=[dict(id="scene:d1", text="Hello.")])
        response = self.client.put("/api/episodes/copy/scenes/scene/localized-dialogues", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.service.save_localized_dialogues.assert_called_once_with("copy", "scene", **body)
        self.client.get("/api/episodes/source/localizations?include_sources=false")
        self.service.localization_catalog.assert_called_once_with("source", include_sources=False)
