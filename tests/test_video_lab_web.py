import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner, VideoLabRunner
from panelforge.features.lab.web import create_app
from panelforge.features.lab.web import _RenderProgressTracker
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    VideoLabPresetRecipe,
    load_change_view_preset,
    load_video_lab_workflow,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalRunStore,
    LocalVideoRunStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHANGE_VIEW_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
VIDEO_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.2.0"
)
PNG = b"\x89PNG\r\n\x1a\nimage"
MP4 = b"\x00\x00\x00\x18ftypisomvideo"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str


class ImmediateVideoComfy:
    websocket_url = "ws://gpu.test:8188/ws?clientId=video-lab"

    def __init__(self):
        self.submitted = []
        self.cancelled = []

    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded(f"{subfolder}/{filename}")

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return "video-prompt-1"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "5": {
                        "images": [
                            {
                                "filename": "PanelForge_H3_00001_.mp4",
                                "subfolder": "video",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return MP4

    def cancel_execution(self, prompt_id):
        self.cancelled.append(prompt_id)


class FakePreviewConnection:
    def __init__(self):
        self.messages = [
            json.dumps({
                "type": "progress",
                "data": {
                    "prompt_id": "video-prompt-1",
                    "node": "21",
                    "value": 1,
                    "max": 4,
                },
            }),
            b"binary-preview",
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        await asyncio.Future()


class FakePreviewConnector:
    def __init__(self):
        self.urls = []
        self.connection = FakePreviewConnection()

    def __call__(self, url):
        self.urls.append(url)
        return self.connection


class VideoLabWebTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(self.directory.name)
        self.comfy = ImmediateVideoComfy()
        change_runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(
                load_change_view_preset(CHANGE_VIEW_DIRECTORY)
            ),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalRunStore(self.directory.name),
        )
        self.video_lab = VideoLabRunner(
            recipe=VideoLabPresetRecipe(load_video_lab_workflow(VIDEO_DIRECTORY)),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalVideoRunStore(self.directory.name),
            run_id_factory=iter(("video-1", "video-2", "video-3")).__next__,
            sleep=lambda _: None,
        )
        self.preview_connector = FakePreviewConnector()
        self.client = TestClient(
            create_app(
                change_runner,
                video_lab=self.video_lab,
                video_preview_connector=self.preview_connector,
            )
        )

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def test_spec_exposes_versioned_recipe_controls_and_live_preview(self):
        response = self.client.get("/api/video-lab/spec")

        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(value["recipe"]["id"], "minimax-h3-ref2v")
        self.assertEqual(value["recipe"]["version"], "0.2.0")
        self.assertEqual(value["defaults"]["preset_id"], "h3-balanced")
        self.assertEqual(value["presets"][0]["megapixels"], 1.2)
        self.assertEqual(value["presets"][0]["duration_seconds"], 10.0)
        self.assertEqual(value["limits"]["reference_images"], {"minimum": 1, "maximum": 3})
        self.assertIn("16:9 (Widescreen)", value["aspect_ratios"])
        self.assertEqual(
            value["preview_ws_url"],
            "/api/video-lab/runs/{run_id}/events",
        )
        self.assertEqual(value["preview_transport"], "same-origin-relay")

    def test_prepare_then_start_preserves_order_and_persists_final_video(self):
        prepared_response = self.client.post(
            "/api/video-lab/runs",
            files=[
                ("images", ("first.png", PNG, "image/png")),
                ("images", ("second.png", PNG, "image/png")),
            ],
            data={
                "prompt": "A two-reference MiniMax H3 prompt.",
                "preset_id": "h3-balanced",
                "aspect_ratio": "16:9 (Widescreen)",
                "megapixels": "0.6",
                "duration_seconds": "10",
                "steps": "32",
                "seed": "18446744073709551615",
                "seed_locked": "true",
            },
        )

        self.assertEqual(prepared_response.status_code, 201)
        prepared = prepared_response.json()
        self.assertEqual(prepared["status"], "created")
        self.assertEqual(prepared["source_labels"], ["first.png", "second.png"])
        self.assertEqual(prepared["seed"], "18446744073709551615")
        self.assertEqual(
            prepared["events_url"],
            f"/api/video-lab/runs/{prepared['run_id']}/events",
        )
        self.assertEqual(self.comfy.submitted, [])

        started_response = self.client.post(
            f"/api/video-lab/runs/{prepared['run_id']}/start"
        )
        self.assertEqual(started_response.status_code, 202)
        completed = self.client.get(
            f"/api/video-lab/runs/{prepared['run_id']}"
        ).json()

        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["frames"], 243)
        self.assertAlmostEqual(completed["effective_duration_seconds"], 10.125)
        self.assertIsNotNone(completed["output_url"])
        workflow = self.comfy.submitted[0]
        self.assertIn("9", workflow)
        self.assertIn("47", workflow)
        self.assertNotIn("48", workflow)
        output = self.client.get(completed["output_url"])
        self.assertEqual(output.status_code, 200)
        self.assertEqual(output.headers["content-type"], "video/mp4")
        self.assertEqual(output.content, MP4)

    def test_preview_relay_forwards_comfy_text_and_binary_events(self):
        source = self.assets.create(PNG, media_type="image/png")
        prepared = self.client.post(
            "/api/video-lab/runs",
            data={
                "source_asset_ids": source.asset_id,
                "prompt": "A quiet reference-to-video shot.",
                "preset_id": "h3-balanced",
            },
        ).json()
        self.client.post(f"/api/video-lab/runs/{prepared['run_id']}/start")

        with self.client.websocket_connect(prepared["events_url"]) as websocket:
            status_event = websocket.receive_json()
            raw_progress_event = websocket.receive_json()
            progress_event = websocket.receive_json()
            preview = websocket.receive_bytes()
            websocket.close()

        self.assertEqual(status_event["type"], "panelforge_preview_status")
        self.assertEqual(status_event["data"]["status"], "connected")
        self.assertEqual(raw_progress_event["type"], "progress")
        self.assertEqual(progress_event["type"], "panelforge_render_progress")
        self.assertEqual(progress_event["data"]["phase_id"], "base_sampling")
        self.assertEqual(progress_event["data"]["percent"], 16.75)
        self.assertEqual(progress_event["data"]["current_step"], 1)
        self.assertEqual(progress_event["data"]["total_steps"], 4)
        self.assertEqual(preview, b"binary-preview")
        self.assertEqual(self.preview_connector.urls, [self.comfy.websocket_url])

    def test_progress_tracker_keeps_the_two_sampling_passes_distinct(self):
        tracker = _RenderProgressTracker(
            self.video_lab.recipe.progress_profile,
            lambda: "video-prompt-1",
        )

        main_start = tracker.consume({
            "type": "executing",
            "data": {"prompt_id": "video-prompt-1", "node": "21"},
        })
        main_end = tracker.consume({
            "type": "progress",
            "data": {"prompt_id": "video-prompt-1", "node": "21", "value": 25, "max": 25},
        })
        upscale_end = tracker.consume({
            "type": "executed",
            "data": {"prompt_id": "video-prompt-1", "node": "26"},
        })
        refinement = tracker.consume({
            "type": "progress",
            "data": {"prompt_id": "video-prompt-1", "node": "16", "value": 1, "max": 3},
        })
        ignored = tracker.consume({
            "type": "progress",
            "data": {"prompt_id": "another-prompt", "node": "16", "value": 3, "max": 3},
        })
        complete = tracker.consume({
            "type": "execution_success",
            "data": {"prompt_id": "video-prompt-1"},
        })

        self.assertEqual(main_start["data"]["percent"], 8.0)
        self.assertEqual(main_end["data"]["percent"], 43.0)
        self.assertEqual(upscale_end["data"]["percent"], 50.0)
        self.assertEqual(refinement["data"]["phase_id"], "refinement")
        self.assertEqual(refinement["data"]["percent"], 65.0)
        self.assertIsNone(ignored)
        self.assertEqual(complete["data"]["percent"], 100.0)
        self.assertFalse(complete["data"]["estimated"])

    def test_asset_prefill_path_and_created_cancellation(self):
        source = self.assets.create(PNG, media_type="image/png")
        prepared = self.client.post(
            "/api/video-lab/runs",
            data={
                "source_asset_ids": source.asset_id,
                "source_labels": "original reference.png",
                "prompt": "A quiet reference-to-video shot.",
                "preset_id": "h3-balanced",
            },
        )
        self.assertEqual(prepared.status_code, 201)
        value = prepared.json()
        self.assertEqual(value["references"][0]["asset_id"], source.asset_id)
        self.assertEqual(value["references"][0]["label"], "original reference.png")

        cancelled = self.client.post(
            f"/api/video-lab/runs/{value['run_id']}/cancel"
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        history = self.client.get("/api/video-lab/runs?limit=30").json()["runs"]
        self.assertEqual(history[0]["run_id"], value["run_id"])

    def test_rejects_more_than_three_images_without_preparing_a_run(self):
        response = self.client.post(
            "/api/video-lab/runs",
            files=[
                ("images", (f"{index}.png", PNG, "image/png"))
                for index in range(4)
            ],
            data={"prompt": "Too many references."},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.video_lab.list(), [])


if __name__ == "__main__":
    unittest.main()
