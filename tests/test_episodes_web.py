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
        def batch(identity, **values):
            self.calls.append((identity, values))
            return {"batch_id": "reference-batch-test"}
        def video_defaults(identity, revision, setup):
            self.calls.append(("video-defaults", identity, revision, setup))
            return {"video_revision": revision + 1, "render_revisions": {}}
        def inheritance(identity, scene_id, revision, inherit):
            self.calls.append(("inheritance", identity, scene_id, revision, inherit))
            return {"episode_id": identity}
        def chain(identity, **values):
            self.calls.append(("video-chain", identity, values))
            return {"video_chain": {"status": "running"}}
        def pause(identity, chain_id):
            self.calls.append(("pause", identity, chain_id)); return {"video_chain": {"status": "pausing"}}
        def resume(identity, chain_id):
            self.calls.append(("resume", identity, chain_id)); return {"video_chain": {"status": "running"}}
        app = FastAPI()
        app.include_router(episodes_router(NS(update_visual=visual, start_reference_batch=batch,
            save_video_defaults=video_defaults, set_scene_video_inheritance=inheritance, start_video_chain=chain,
            pause_video_chain=pause, resume_video_chain=resume), serialize_image_project=lambda p: p,
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

    def test_reference_batch_validates_two_complete_profiles_and_thermal_policy(self):
        settings = dict(model_id="krea.safetensors", aspect_ratio="9:16 (Portrait Widescreen)",
                        megapixels=2.1, seed="42", loras=[],
                        sampling=asdict(Krea2AssistedSampling()), workflow=KREA2_FLUX_KLEIN_WORKFLOW.key)
        response = self.client.post("/api/episodes/episode-test/reference-batches", json={
            "expected_visual_revision": 3, "request_id": "batch-request-123",
            "reference_ids": ["character-1", "location-1"],
            "profiles": {
                "character": {"model_id": "local::gemma", "settings": settings, "inherit_technical": True},
                "location": {"model_id": "local::qwen", "settings": {**settings, "workflow": "krea2-sampling@1.0.0"}},
            },
            "thermal": {"stop_temperature_c": 82, "resume_temperature_c": 44,
                        "cooldown_seconds": 30, "monitor_local": True,
                        "monitor_remote": True, "pause_when_unavailable": False},
        })
        self.assertEqual(response.status_code, 202, response.text)
        identity, values = self.calls[-1]
        self.assertEqual(identity, "episode-test")
        self.assertEqual(values["profiles"]["character"]["settings"].workflow,
                         KREA2_FLUX_KLEIN_WORKFLOW)
        self.assertTrue(values["profiles"]["character"]["inherit_technical"])
        self.assertEqual(values["profiles"]["location"]["model_id"], "local::qwen")
        self.assertEqual(values["thermal"].cooldown_seconds, 30)

        invalid = self.client.post("/api/episodes/episode-test/reference-batches", json={
            "expected_visual_revision": 3, "request_id": "batch-request-456",
            "reference_ids": ["character-1"],
            "profiles": {"character": {"model_id": "local::gemma", "settings": settings}},
        })
        self.assertEqual(invalid.status_code, 422, invalid.text)
        unexpected = self.client.post("/api/episodes/episode-test/reference-batches", json={
            "expected_visual_revision": 3, "request_id": "batch-request-789",
            "reference_ids": ["character-1"],
            "profiles": {
                "character": {"model_id": "local::gemma", "settings": {**settings, "surprise": True}},
                "location": {"model_id": "local::qwen", "settings": settings},
            },
        })
        self.assertEqual(unexpected.status_code, 422, unexpected.text)

    def test_video_defaults_inheritance_and_chain_use_explicit_revisions(self):
        parameters = dict(prompt="", aspect_ratio="9:16 (Portrait Widescreen)", megapixels=0.9,
            duration_seconds=10, steps=9, seed="42", seed_locked=True, music_enabled=False,
            spectrum_enabled=False, initial_megapixels=0.9, recipe_id="minimax-h3-bunny",
            recipe_version="0.1.3", checkpoint=None,
            bunny=dict(turbo_enabled=True, base_steps=9, coarse_steps=4, refine_steps=5,
                       lora_second_strength=0.2, preview_enabled=True),
            video_loras=dict(version="0.2.0", enabled=True, clip_last_layer=None, entries=[]),
            video_lora=None)
        response = self.client.put("/api/episodes/episode-test/video-defaults", json={
            "expected_video_revision": 4, "parameters": parameters})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.calls[-1][2], 4)
        self.assertEqual(self.calls[-1][3]["settings"]["seed"], "42")

        response = self.client.put("/api/episodes/episode-test/scenes/scene-1/render-inheritance",
            json={"expected_revision": 7, "inherit": False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.calls[-1], ("inheritance", "episode-test", "scene-1", 7, False))

        response = self.client.post("/api/episodes/episode-test/video-chain", json={
            "expected_video_revision": 4, "request_id": "video-chain-request", "scene_ids": ["scene-1", "scene-2"],
            "inter_video_cooldown_seconds": 45, "auto_dlss": True})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1][2]["scene_ids"], ["scene-1", "scene-2"])
        self.assertEqual(self.calls[-1][2]["inter_video_cooldown_seconds"], 45)
        self.assertIs(self.calls[-1][2]["auto_dlss"], True)
        invalid = self.client.post("/api/episodes/episode-test/video-chain", json={
            "expected_video_revision": 4, "request_id": "video-chain-invalid", "scene_ids": ["scene-1"],
            "inter_video_cooldown_seconds": True})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        invalid = self.client.post("/api/episodes/episode-test/video-chain", json={
            "expected_video_revision": 4, "request_id": "video-chain-invalid", "scene_ids": ["scene-1"],
            "auto_dlss": 1})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        response = self.client.post("/api/episodes/episode-test/video-chains/chain-1/pause")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1], ("pause", "episode-test", "chain-1"))
        response = self.client.post("/api/episodes/episode-test/video-chains/chain-1/resume")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1], ("resume", "episode-test", "chain-1"))


if __name__ == "__main__":
    unittest.main()
