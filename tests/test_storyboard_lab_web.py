import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (  # noqa: E402
    ChangeViewRunner,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    StoryboardLabService,
    StreamEventKind,
    StreamPhase,
)
from panelforge.features.lab.web import create_app  # noqa: E402
from panelforge.infrastructure.presets import (  # noqa: E402
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.storage import (  # noqa: E402
    LocalAssetStore,
    LocalRunStore,
    LocalStoryboardRunStore,
)
from panelforge.infrastructure.storyboard_recipes import (  # noqa: E402
    LocalStoryboardRecipeCatalog,
)
from tests.test_storyboard_contract import storyboard_payload  # noqa: E402


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
STORYBOARD_RECIPES = PROJECT_ROOT / "storyboard_recipes"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str = "panelforge/unused.png"


class UnusedComfy:
    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded()


class StoryboardGateway:
    def __init__(self) -> None:
        self.content = json.dumps(storyboard_payload(6))
        self.complete_requests = []
        self.stream_requests = []

    def list_models(self):
        return (
            ModelDescriptor("Qwen3.8-27B"),
            ModelDescriptor("vision-small"),
        )

    def complete(self, request):
        self.complete_requests.append(request)
        return CompletionResult(model_id=request.model_id, content=self.content)

    def stream(self, request):
        self.stream_requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.GENERATING,
            text="Generating",
        )
        if request.include_reasoning:
            yield CompletionStreamEvent(
                kind=StreamEventKind.REASONING,
                phase=StreamPhase.GENERATING,
                text="Storyboard debug trace",
            )
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=self.content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=self.content,
            result=CompletionResult(
                model_id=request.model_id,
                content=self.content,
                call_id="storyboard-web-call",
            ),
        )


def decode_sse(response_text):
    events = []
    normalized = response_text.replace("\r\n", "\n")
    for block in normalized.split("\n\n"):
        data = "\n".join(
            line[5:].lstrip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if data:
            events.append(json.loads(data))
    return events


class StoryboardLabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        workspace = self.temporary_directory.name
        assets = LocalAssetStore(workspace)
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY)),
            comfy=UnusedComfy(),
            assets=assets,
            runs=LocalRunStore(workspace),
        )
        self.gateway = StoryboardGateway()
        storyboard_lab = StoryboardLabService(
            gateway=self.gateway,
            recipes=LocalStoryboardRecipeCatalog(STORYBOARD_RECIPES),
            runs=LocalStoryboardRunStore(workspace),
        )
        self.client = TestClient(create_app(runner, storyboard_lab=storyboard_lab))

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def create_run(self, panel_count=6):
        response = self.client.post(
            "/api/storyboard-lab/runs",
            json={
                "source_text": "A traveler follows the last train through one station.",
                "panel_count": panel_count,
                "model_id": "Qwen3.8-27B",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["run"]

    def test_spec_create_stream_get_and_list_form_one_prompt_run(self):
        spec = self.client.get("/api/storyboard-lab/spec")

        self.assertEqual(spec.status_code, 200, spec.text)
        self.assertEqual(spec.json()["recipe"]["id"], "krea2.storyboard.from_text")
        self.assertEqual(spec.json()["models"][0]["id"], "Qwen3.8-27B")
        six = next(
            option
            for option in spec.json()["panel_options"]
            if option["panel_count"] == 6
        )
        self.assertEqual((six["columns"], six["rows"]), (3, 2))
        self.assertEqual(six["page_aspect_ratio"], "1:1")

        created = self.create_run()
        run_id = created["run_id"]
        self.assertEqual(created["status"], "created")
        self.assertIsNone(created["compiled_prompt"])

        streamed = self.client.post(
            f"/api/storyboard-lab/runs/{run_id}/generate/stream",
            headers={"Accept": "text/event-stream"},
        )
        events = decode_sse(streamed.text)

        self.assertEqual(streamed.status_code, 200, streamed.text)
        self.assertEqual(len(self.gateway.stream_requests), 1)
        self.assertEqual(self.gateway.complete_requests, [])
        self.assertEqual(events[-1]["kind"], "completed")
        self.assertEqual(events[-1]["run"]["status"], "succeeded")
        self.assertIn(
            "THREE COLUMNS × TWO ROWS",
            events[-1]["run"]["compiled_prompt"],
        )

        fetched = self.client.get(f"/api/storyboard-lab/runs/{run_id}")
        listed = self.client.get("/api/storyboard-lab/runs?limit=30")
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["run"]["status"], "succeeded")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()["runs"][0]["run_id"], run_id)

    def test_invalid_model_candidate_remains_a_failed_raw_draft(self):
        self.gateway.content = "not valid storyboard JSON"
        created = self.create_run()
        run_id = created["run_id"]

        streamed = self.client.post(
            f"/api/storyboard-lab/runs/{run_id}/generate/stream",
            headers={"Accept": "text/event-stream"},
        )
        events = decode_sse(streamed.text)

        self.assertEqual(streamed.status_code, 200, streamed.text)
        self.assertEqual(len(self.gateway.stream_requests), 1)
        self.assertEqual(self.gateway.complete_requests, [])
        failed = events[-1]["run"]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["raw_response"], self.gateway.content)
        self.assertIsNone(failed["compiled_prompt"])
        self.assertTrue(failed["error"])

        reopened = self.client.get(f"/api/storyboard-lab/runs/{run_id}")
        self.assertEqual(reopened.json()["run"]["raw_response"], self.gateway.content)
        self.assertEqual(reopened.json()["run"]["status"], "failed")

    def test_reasoning_is_exposed_only_when_the_stream_opts_in(self):
        default_run = self.create_run()
        default_response = self.client.post(
            f"/api/storyboard-lab/runs/{default_run['run_id']}/generate/stream",
            headers={"Accept": "text/event-stream"},
        )
        self.assertNotIn(
            "reasoning",
            [event["kind"] for event in decode_sse(default_response.text)],
        )
        self.assertFalse(self.gateway.stream_requests[-1].include_reasoning)

        opted_in_run = self.create_run()
        opted_in_response = self.client.post(
            f"/api/storyboard-lab/runs/{opted_in_run['run_id']}/generate/stream"
            "?include_reasoning=true",
            headers={"Accept": "text/event-stream"},
        )
        events = decode_sse(opted_in_response.text)

        self.assertIn("reasoning", [event["kind"] for event in events])
        self.assertTrue(self.gateway.stream_requests[-1].include_reasoning)
        completed = events[-1]["run"]
        self.assertNotIn("Storyboard debug trace", completed["raw_response"])
        self.assertNotIn("Storyboard debug trace", completed["compiled_prompt"])


if __name__ == "__main__":
    unittest.main()
