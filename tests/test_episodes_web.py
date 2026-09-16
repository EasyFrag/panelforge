"""User-run API validation checks; no LLM or renderer is called."""
from dataclasses import asdict
from types import SimpleNamespace as NS
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.domain.krea2_sampling import Krea2AssistedSampling
from panelforge.domain.krea2_assisted_workflows import KREA2_FLUX_KLEIN_WORKFLOW
from panelforge.features.lab.episodes_web import episodes_router
from panelforge.features.lab.web import Krea2AssistedAttemptBody, H3RenderAttemptBody


class EpisodeWebTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def visual(identity, expected_revision, style, settings):
            self.calls.append(settings)
            return {"settings": settings}
        app = FastAPI()
        app.include_router(episodes_router(NS(update_visual=visual), serialize_image_project=lambda p: p,
            validate_image=lambda content: "image/png", image_body=Krea2AssistedAttemptBody, render_body=H3RenderAttemptBody))
        self.client = TestClient(app)

    def test_common_sampling_and_loras_use_assisted_validation(self):
        settings = dict(model_id="krea.safetensors", loras=[dict(name="style.safetensors", strength=0.65)],
                        sampling=asdict(Krea2AssistedSampling()), workflow=KREA2_FLUX_KLEIN_WORKFLOW.key)
        body = dict(expected_revision=1, style="Animation 3D", settings=settings)
        response = self.client.put("/api/episodes/episode-test/visual", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["settings"], {**settings, "workflow": asdict(KREA2_FLUX_KLEIN_WORKFLOW)})
        for invalid in ({**settings, "surprise": 1},
                        {**settings, "loras": [dict(name="style.safetensors", strength=21)]},
                        {**settings, "sampling": {**settings["sampling"], "preset_id": "moody_beta"}}):
            response = self.client.put("/api/episodes/episode-test/visual", json={**body, "settings": invalid})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(self.calls), 1)

    def test_out_of_range_or_boolean_creative_axes_are_rejected_before_service(self):
        body = dict(expected_revision=1, intention="Action", duration=10,
                    references=[dict(reference_id="character-1", role="subject_reference")],
                    plan_model_id="Qwen", writer_model_id="Gemma", audacity=2,
                    creative_axes=dict(scene_life=1, camera=4, extra_motion=2, dialogue=0))
        for bad in (4, -1, True):
            body["creative_axes"]["camera"] = bad
            response = self.client.put("/api/episodes/episode-test/scenes/scene-1", json=body)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
