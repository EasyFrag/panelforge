import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from fastapi.testclient import TestClient

from panelforge.application import (
    ChangeViewRunner,
    CompletionResult,
    CompletionStreamEvent,
    Krea2EditService,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.comfy import ComfyImageRef
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
    load_krea2_edit_workflow,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalKrea2EditStore,
    LocalRunStore,
)


ROOT = Path(__file__).resolve().parents[1]
CHANGE_VIEW = (
    ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
EDIT_WORKFLOW = (
    ROOT / "workflows" / "image.edit" / "krea2-identity" / "0.1.0"
)
PNG = b"\x89PNG\r\n\x1a\nresult"


class Gateway:
    def __init__(self) -> None:
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("Qwen3.8-27B"),)

    def stream(self, request):
        self.requests.append(request)
        reasoning = "I will preserve the material language and change the pose."
        prompt = (
            "A vertical full-body studio photograph of the same clearly adult "
            "gem-covered gorilla, standing upright and striking its chest, with "
            "the original black background, reflective stones, lighting, and finish."
        )
        yield CompletionStreamEvent(
            StreamEventKind.REASONING,
            StreamPhase.GENERATING,
            reasoning,
        )
        yield CompletionStreamEvent(
            StreamEventKind.DELTA,
            StreamPhase.GENERATING,
            prompt,
        )
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(
                model_id=request.model_id,
                content=prompt,
                finish_reason="stop",
                call_id="edit-call",
            ),
        )


class Comfy:
    def __init__(self) -> None:
        self.submitted = []

    def upload_image(self, content, *, filename, subfolder="", overwrite=False):
        return ComfyImageRef(filename, subfolder, "input")

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return "edit-execution"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"completed": True, "status_str": "success"},
                "outputs": {},
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return PNG

    def cancel_execution(self, prompt_id):
        return None


def decode_sse(text: str) -> list[dict[str, object]]:
    values = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].lstrip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if data:
            values.append(json.loads(data))
    return values


class Krea2EditWebTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(self.temporary.name)
        self.comfy = Comfy()
        self.gateway = Gateway()
        source_ids = iter(("edit-source", "edit-stage-2"))
        change_runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalRunStore(self.temporary.name),
        )
        edit = Krea2EditService(
            gateway=self.gateway,
            workflow=load_krea2_edit_workflow(EDIT_WORKFLOW),
            comfy=self.comfy,
            assets=self.assets,
            sources=LocalKrea2EditStore(self.temporary.name),
            poll_interval=0.001,
            source_id_factory=lambda: next(source_ids),
            attempt_id_factory=lambda: "edit-attempt",
        )
        self.client = TestClient(create_app(change_runner, krea2_edit=edit))

    def tearDown(self) -> None:
        self.client.close()
        self.temporary.cleanup()

    def test_upload_prompt_once_render_iteratively_and_archive(self):
        graph = {
            "55": {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": "Krea2/kroma-v0.2-turbo.safetensors"},
            },
            "53": {"class_type": "KSampler", "inputs": {"seed": 91}},
            "83": {
                "class_type": "ResolutionSelector",
                "inputs": {
                    "aspect_ratio": "9:16 (Portrait Widescreen)",
                    "megapixels": 0.8,
                },
            },
            "84": {
                "class_type": "Krea2EditGroundedEncode",
                "inputs": {
                    "prompt": "A detailed black-gem gorilla bust on a black studio background."
                },
            },
        }
        uploaded = self.client.post(
            "/api/image-lab/krea2-edit/sources",
            files={
                "source_image": (
                    "gorilla.png",
                    _png_with_text("prompt", json.dumps(graph)),
                    "image/png",
                )
            },
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        source = uploaded.json()["source"]
        self.assertEqual(source["metadata"]["origin"], "png")
        self.assertEqual(source["metadata"]["seed"], "91")

        streamed = self.client.post(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}/prompt/stream"
            "?include_reasoning=true",
            json={
                "instruction": "Show the gorilla full body, beating its chest.",
                "model_id": "Qwen3.8-27B",
                "prompt_language": "zh",
            },
        )
        self.assertEqual(streamed.status_code, 200)
        events = decode_sse(streamed.text)
        self.assertTrue(any(event["kind"] == "reasoning" for event in events))
        terminal = events[-1]["source"]
        self.assertEqual(terminal["prompt_status"], "ready")
        self.assertEqual(terminal["prompt_language"], "zh")
        self.assertEqual(terminal["revisions"][0]["prompt_language"], "zh")
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(len(self.gateway.requests[0].images), 1)
        self.assertEqual(terminal["revisions"][0]["instruction"], "Show the gorilla full body, beating its chest.")

        prepared = self.client.post(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}/attempts",
            json={
                "prompt": terminal["generated_prompt"],
                "model_id": "Krea2/kroma-v0.2-turbo.safetensors",
                "aspect_ratio": "9:16 (Portrait Widescreen)",
                "megapixels": 1.0,
                "seed": "92",
                "ref_boost": 3.0,
                "steps": 12,
                "loras": [],
            },
        )
        self.assertEqual(prepared.status_code, 201, prepared.text)
        started = self.client.post(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}"
            "/attempts/edit-attempt/start"
        )
        self.assertEqual(started.status_code, 202, started.text)
        completed = self.client.get(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}"
        ).json()["source"]
        self.assertEqual(completed["attempts"][-1]["status"], "succeeded")
        self.assertTrue(completed["attempts"][-1]["output_url"])
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(self.comfy.submitted[0]["79"]["inputs"]["ref_boost"], 3.0)
        self.assertEqual(self.comfy.submitted[0]["53"]["inputs"]["steps"], 12)

        long_step_name = "Plein pied\n" + ("avec continuité visuelle " * 8)
        promoted = self.client.post(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}"
            f"/attempts/{completed['attempts'][-1]['attempt_id']}/promote",
            json={
                "project_name": "Gorille bijoux",
                "step_name": long_step_name,
            },
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        next_stage = promoted.json()["source"]
        self.assertEqual(next_stage["project_id"], source["source_id"])
        self.assertEqual(next_stage["stage_index"], 2)
        self.assertEqual(next_stage["parent_attempt_id"], completed["attempts"][-1]["attempt_id"])
        self.assertEqual(next_stage["project_name"], "Gorille bijoux")
        self.assertEqual(next_stage["prompt_language"], "zh")
        self.assertEqual(next_stage["export"]["status"], "pending")
        parent = self.client.get(
            f"/api/image-lab/krea2-edit/sources/{source['source_id']}"
        ).json()["source"]
        self.assertEqual(len(parent["accepted_label"]), 120)
        self.assertTrue(parent["accepted_label"].startswith("Plein pied avec continuité"))
        self.assertTrue(parent["accepted_label"].endswith("…"))
        self.assertNotIn("\n", parent["accepted_label"])

        archived = self.client.post(
            f"/api/image-lab/krea2-edit/sources/{next_stage['source_id']}/state",
            json={"state": "processed"},
        )
        self.assertEqual(archived.status_code, 200)
        pending = self.client.get(
            "/api/image-lab/krea2-edit/sources?limit=10"
        ).json()["sources"]
        self.assertFalse(any(value["state"] == "pending" for value in pending))

    def test_ui_is_single_workspace_with_backlog_reasoning_and_ten_loras(self):
        html = (ROOT / "src/panelforge/features/lab/static/index.html").read_text(
            encoding="utf-8"
        )
        script = (
            ROOT / "src/panelforge/features/lab/static/krea2-edit-lab.js"
        ).read_text(encoding="utf-8")
        resources = (
            ROOT / "src/panelforge/features/lab/static/krea2-resource-ui.js"
        ).read_text(encoding="utf-8")
        css = (ROOT / "src/panelforge/features/lab/static/lab.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="krea2-edit-lab-workspace"', html)
        self.assertIn('/static/krea2-edit-lab.js?v=20260903.2', html)
        self.assertIn('id="krea2-edit-prompt-language"', html)
        self.assertIn('id="krea2-edit-show-reasoning"', html)
        self.assertIn('id="krea2-edit-backlog"', html)
        self.assertIn('id="krea2-edit-processed"', html)
        self.assertIn('id="krea2-edit-hide"', html)
        self.assertLess(
            html.index('id="krea2-edit-build-prompt"'),
            html.index('class="krea2-edit-images"'),
        )
        self.assertLess(
            html.index('id="krea2-edit-render"'),
            html.index('class="krea2-edit-images"'),
        )
        self.assertIn("renderLoraPickerStack", script)
        self.assertIn("maximum: 10", script)
        self.assertIn("renderModelPicker", script)
        self.assertIn("function applyDefaultRenderSettings()", script)
        self.assertIn("function renderSettingsComplete()", script)
        self.assertIn("state.initialized = false", script)
        self.assertIn("state.busy && !force", script)
        self.assertIn("{ hydrate: true, force: true }", script)
        self.assertIn("feedback_attempt_id", script)
        self.assertIn("core.createLlmOutcomeTone()", script)
        self.assertIn("outcomeTone.success()", script)
        self.assertIn("outcomeTone.failure()", script)
        self.assertIn("Valider et continuer", script)
        self.assertIn("promoteAttempt", script)
        self.assertIn("function validationLabel", script)
        self.assertIn('Ref boost ${attempt.settings.ref_boost}', script)
        self.assertNotIn('`seed ${attempt.settings.seed}`', script)
        self.assertIn('id="krea2-edit-timeline"', html)
        self.assertIn('id="krea2-edit-revisions"', html)
        self.assertIn('id="krea2-edit-show-original"', html)
        self.assertIn('id="krea2-edit-original-image"', html)
        self.assertIn('id="krea2-edit-lightbox"', html)
        self.assertIn('id="krea2-edit-lightbox-image"', html)
        self.assertIn('id="krea2-edit-project-name"', html)
        self.assertIn('id="krea2-edit-step-name"', html)
        self.assertIn('class="krea2-edit-prompt-details"', html)
        self.assertIn('id="krea2-edit-prompt" rows="4"', html)
        self.assertNotIn('<details class="krea2-edit-prompt-details" open>', html)
        self.assertIn('id="krea2-edit-retry-export"', html)
        self.assertIn('source.stage_index > 1', script)
        self.assertIn('rootSource.source_url', script)
        self.assertIn('classList.toggle("show-original", showOriginal)', script)
        self.assertIn("makeZoomable(elements.originalImage", script)
        self.assertIn("makeZoomable(elements.sourceImage", script)
        self.assertIn("makeZoomable(elements.resultImage", script)
        self.assertIn("makeZoomable(image, `Essai", script)
        self.assertIn("await loadSources();\n          render();", script)
        self.assertIn("project_name: elements.projectName.value.trim()", script)
        self.assertIn("step_name: elements.stepName.value.trim()", script)
        self.assertIn("/export`", script)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn(".krea2-edit-lightbox-body img", css)
        self.assertIn("max-width: none; max-height: none", css)
        self.assertIn("renderModelPicker(elements.model", script)
        self.assertIn("renderLoraPickerStack", script)
        for label in ("Favoris · BF16", "Favoris · INT8", "SFW", "NSFW"):
            self.assertIn(label, resources)
        self.assertIn("reasoningTrace.streamUrl", script)
        self.assertNotIn("WebSocket", script)
        self.assertIn("max-width: 100%", css)
        self.assertIn("#krea2-edit-build-prompt", css)
        self.assertIn("#krea2-edit-render", css)
        self.assertIn("#krea2-edit-message:empty { display: none; }", css)
        self.assertIn(".krea2-edit-editor > .actions", css)
        self.assertIn("height: 31px; min-height: 31px", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn("object-fit: contain", css)
        self.assertIn("max-height: 75vh", css)
        self.assertIn("#krea2-edit-loras { grid-template-columns: 1fr", css)
        self.assertIn(".krea2-edit-settings .krea2-catalog-manager", css)
        self.assertNotIn("height: clamp(260px, 52vh, 480px)", css)
        self.assertIn('id="krea2-edit-catalog-manager"', html)
        self.assertIn("renderResourceManager", script)
        self.assertIn("updateResourcePreference", script)


def _png_with_text(key: str, value: str) -> bytes:
    data = key.encode("latin-1") + b"\0" + value.encode("latin-1")
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data
    chunk += struct.pack(">I", zlib.crc32(b"tEXt" + data) & 0xFFFFFFFF)
    end = struct.pack(">I", 0) + b"IEND"
    end += struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk + end


if __name__ == "__main__":
    unittest.main()
