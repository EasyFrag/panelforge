"""Enhancement contracts with fake ComfyUI; never contact a renderer or LLM."""

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner
from panelforge.domain.krea2_edit import Krea2EditAttemptStatus as Status
from panelforge.features.lab.web import create_app, serialize_krea2_edit_source
from panelforge.infrastructure.comfy import ComfyHttpClient, ComfyImageRef
from panelforge.infrastructure.krea2_upscale import PillowUpscaleImages
from panelforge.infrastructure.presets.image_upscale import load_image_upscale_workflow
from panelforge.infrastructure.storage import LocalKrea2EditStore, LocalRunStore
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset
from tests import test_krea2_retouch as fixtures


ROOT = Path(__file__).resolve().parents[1]
UPSCALER = ROOT / "workflows/image.upscale/esrgan/0.1.0"


class FakeUpscaleComfy:
    def __init__(self):
        self.submitted = []
        self.uploads = []
        self.models = ("4x-ClearRealityV1.pth", "alternative.pth")
        self.output = fixtures.png(Image.new("RGB", (8, 12), "red"))
        self.fail = False

    def list_upscale_models(self):
        return self.models

    def upload_image(self, content, **kwargs):
        self.uploads.append(content)
        return ComfyImageRef("upscale.png", "tests", "input")

    def submit_workflow(self, graph):
        self.submitted.append(graph)
        return f"upscale-{len(self.submitted)}"

    def get_history(self, execution_id):
        return {execution_id: {"status": {"completed": True, "status_str": "error" if self.fail else "success"}, "outputs": {}}}

    def download_output(self, **kwargs):
        return self.output

    def cancel_execution(self, execution_id):
        return None


class UpscaleTest(unittest.TestCase):
    def setUp(self):
        fixtures.RetouchServiceTest.setUp(self)
        self.comfy = FakeUpscaleComfy()
        self.service.comfy = self.comfy
        self.service.upscale_workflow = load_image_upscale_workflow(UPSCALER)
        self.service.upscale_images = PillowUpscaleImages()

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, parent="original", request_id="enhance", model="4x-ClearRealityV1.pth"):
        return self.service.prepare_upscale(self.source.source_id, parent, request_id=request_id, model_name=model)

    def complete(self, parent="original", request_id="enhance", model="4x-ClearRealityV1.pth"):
        source, attempt = self.prepare(parent, request_id, model)
        self.service.queue_attempt(source.source_id, attempt.attempt_id)
        result = self.service.execute_attempt(source.source_id, attempt.attempt_id)
        completed = next(a for a in result.attempts if a.attempt_id == attempt.attempt_id)
        self.assertEqual(completed.status, Status.SUCCEEDED, completed.error)
        return result, completed

    def test_selected_generation_becomes_distinct_candidate_without_changing_prompt(self):
        source, pending = self.prepare()
        self.assertEqual(source.generated_prompt, "CURRENT EDITOR PROMPT")
        self.assertEqual(self.prepare()[1], pending)
        self.assertEqual(self.comfy.submitted, [])
        source, enhanced = self.complete()
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual(source.attempts[0], self.original)
        self.assertEqual(source.attempt_label(enhanced.attempt_id), "Essai 1 — Amélioré 1")
        self.assertEqual(fixtures.decoded(self.comfy.uploads[0]).size, (16, 24))
        self.assertEqual(fixtures.decoded(self.assets.read_bytes(enhanced.output_asset_id)).size, (8, 12))
        self.assertEqual(self.prepare()[1], enhanced, "HTTP retry returns the completed candidate")
        next_generation = replace(self.original, attempt_id="next-generation")
        self.assertEqual(replace(source, attempts=(*source.attempts, next_generation)).attempt_label("next-generation"), "Essai 2")
        self.assertEqual(LocalKrea2EditStore(self.root).get(source.source_id), source)
        graph = self.comfy.submitted[0]
        self.assertEqual({node["class_type"] for node in graph.values()},
                         {"LoadImage", "UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScale", "SaveImage"})

    def test_mask_and_harmonization_reapplied_and_reopened_without_composite_accumulation(self):
        for index, level in enumerate((0, 255, 128)):
            with self.subTest(level=level):
                mask = Image.new("L", (8, 12), level)
                mask.putpixel((0, 0), 0)
                mask.putpixel((1, 0), 128)
                source, retouch = self.service.save_retouch(self.source.source_id, "original", fixtures.png(mask),
                    request_id=f"mask-{index}", harmonize=True, harmonize_strength=50)
                source, improved = self.complete(retouch.attempt_id, f"enhance-{index}")
                self.assertEqual(improved.upscale.mask_asset_id, retouch.retouch.mask_asset_id)
                expected = self.service.retouch_compositor.compose(self.source_bytes, self.comfy.output,
                    fixtures.png(mask), harmonize=True, harmonize_strength=50)
                actual = self.assets.read_bytes(improved.output_asset_id)
                self.assertEqual(actual, expected.output_png)
                self.assertEqual(fixtures.decoded(actual).getpixel((0, 0)), fixtures.decoded(self.source_bytes).getpixel((0, 0)))
                reopened = self.service.prepare_retouch(source.source_id, improved.attempt_id)
                self.assertEqual(reopened["mask_png"], self.assets.read_bytes(retouch.retouch.mask_asset_id))
                self.assertTrue(reopened["harmonize"])
                self.assertEqual(fixtures.decoded(reopened["generated_png"]).getpixel((0, 0)), (255, 0, 0, 255))
                source, saved = self.service.save_retouch(source.source_id, improved.attempt_id, reopened["mask_png"],
                    request_id=f"reopened-{index}", harmonize=True, harmonize_strength=50)
                self.assertEqual(self.assets.read_bytes(saved.output_asset_id), actual)
                _, alternative = self.complete(saved.attempt_id, f"alternative-{index}", "alternative.pth")
                self.assertEqual(alternative.upscale.input_asset_id, self.original.output_asset_id)
                self.assertEqual(fixtures.decoded(self.comfy.uploads[-1]).tobytes(), fixtures.decoded(self.generated_bytes).tobytes())

    def test_feedback_promotion_and_export_use_selected_enhanced_candidate(self):
        source, chosen = self.complete()
        from tests.test_krea2_edit import FakeGateway
        self.service.gateway = FakeGateway(json.dumps({"message": "Modification proposée", "prompt": self.original.prompt}))
        list(self.service.stream_prepare_prompt(source.source_id, "Improve the opening", "fake",
            feedback_attempt_id=chosen.attempt_id, assistance_version="3.0.0"))
        self.assertEqual(self.service.gateway.requests[-1].images[-1].content, self.assets.read_bytes(chosen.output_asset_id))
        child = self.service.promote_attempt(source.source_id, chosen.attempt_id, project_name="Wall", step_name="Opening")
        self.assertEqual(child.source_asset_id, chosen.output_asset_id)
        project = Path(child.export_path)
        entry = json.loads((project / "project.json").read_text(encoding="utf-8"))["accepted_chain"][0]
        self.assertEqual((project / entry["image"]).read_bytes(), self.assets.read_bytes(chosen.output_asset_id))
        sidecar = json.loads((project / entry["sidecar"]).read_text(encoding="utf-8"))
        self.assertEqual(sidecar["operation"], "image.upscale")
        self.assertEqual(sidecar["upscale"]["model_name"], chosen.upscale.model_name)
        self.assertEqual(sidecar["output_dimensions"], {"width": 8, "height": 12})
        self.assertEqual(serialize_krea2_edit_source(source)["attempts"][-1]["output_asset_id"], chosen.output_asset_id)
        with self.assertRaises(ValueError):
            self.prepare(request_id="after-validation")

    def test_failed_job_missing_model_and_queue_conflicts_preserve_original(self):
        with self.assertRaises(ValueError):
            self.prepare(model="missing.pth")
        self.assertEqual(len(self.store.get(self.source.source_id).attempts), 1)
        source, attempt = self.prepare()
        with self.assertRaises(ValueError):
            self.prepare(model="alternative.pth")
        self.service.queue_attempt(source.source_id, attempt.attempt_id)
        with self.assertRaises(ValueError):
            self.service.restart_stage(source.source_id, expected_restart_count=0)
        _, second = self.prepare(request_id="second")
        with self.assertRaises(ValueError):
            self.service.queue_attempt(source.source_id, second.attempt_id)
        self.comfy.fail = True
        failed = self.service.execute_attempt(source.source_id, attempt.attempt_id)
        self.assertEqual(failed.attempts[1].status, Status.FAILED)
        self.assertEqual(failed.attempts[0], self.original)
        self.assertEqual(self.assets.read_bytes(self.original.output_asset_id), self.generated_bytes)

    def test_detached_completion_and_cancellation_use_upscale_workflow(self):
        source, attempt = self.prepare()
        self.service.queue_attempt(source.source_id, attempt.attempt_id)
        source = self.store.get(source.source_id)
        running = source.attempts[-1].start("detached", "b" * 64)
        self.store.save(source.replace_attempt(running))
        recovered = self.service.get(source.source_id)
        self.assertEqual(recovered.attempts[-1].status, Status.SUCCEEDED)
        self.assertEqual(self.comfy.submitted, [])
        source, cancel = self.prepare(request_id="cancel")
        self.service.queue_attempt(source.source_id, cancel.attempt_id)
        cancelled = self.service.cancel_attempt(source.source_id, cancel.attempt_id)
        self.assertEqual(cancelled.attempts[-1].status, Status.CANCELLED)

    def test_old_project_schemas_and_image_orientation(self):
        path = self.root / "krea2_edits" / self.source.source_id / "source.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 11)
        for schema in range(1, 9):
            legacy = {**data, "schema_version": schema}
            for attempt in legacy["attempts"]:
                attempt.pop("upscale", None)
            path.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertEqual(self.store.get(self.source.source_id).attempts[0], self.original)
        image = Image.new("RGB", (12, 8), "green")
        exif = Image.Exif(); exif[274] = 6
        buffer = BytesIO(); image.save(buffer, format="PNG", exif=exif)
        prepared = self.service.upscale_images.prepare(buffer.getvalue(), self.generated_bytes)
        self.assertEqual((prepared.width, prepared.height), (8, 12))
        for invalid in (b"not an image", fixtures.png(Image.new("RGB", (12, 8)))):
            with self.assertRaises(ValueError):
                self.service.upscale_images.prepare(self.source_bytes, invalid)
        with self.assertRaises(ValueError):
            self.service.upscale_images.normalize_output(self.generated_bytes, 8, 12)

    def test_http_selection_catalogue_and_idempotent_launch(self):
        change = ChangeViewRunner(recipe=ChangeViewPresetRecipe(load_change_view_preset(
            ROOT / "workflows/character.change_view/qwen-edit-2511-multiple-angles/0.2.0")),
            comfy=self.comfy, assets=self.assets, runs=LocalRunStore(self.root))
        with TestClient(create_app(change, krea2_edit=self.service)) as client:
            catalog = client.get("/api/image-lab/krea2-edit/upscalers")
            self.assertEqual(catalog.status_code, 200)
            self.assertEqual(catalog.json()["default"], self.comfy.models[0])
            url = f"/api/image-lab/krea2-edit/sources/{self.source.source_id}/attempts/original/upscale"
            body = {"model_name": self.comfy.models[0], "request_id": "http"}
            first = client.post(url, json=body)
            self.assertEqual(first.status_code, 202, first.text)
            retry = client.post(url, json=body)
            self.assertEqual(first.json()["attempt_id"], retry.json()["attempt_id"])
            self.assertEqual(len(self.comfy.submitted), 1)
            self.assertEqual(retry.json()["source"]["attempts"][-1]["status"], "succeeded")
            self.assertEqual(client.post(url, json={**body, "request_id": "missing", "model_name": "absent"}).status_code, 422)


class UpscaleCatalogueTest(unittest.TestCase):
    def test_old_and_new_comfy_combo_schemas(self):
        client = ComfyHttpClient("http://unused", client_id="test")
        for field in ((["photo.pth"],), ("COMBO", {"options": ["photo.pth"]})):
            payload = {"UpscaleModelLoader": {"input": {"required": {"model_name": field}}}}
            with patch.object(client, "_read_json", return_value=payload):
                self.assertEqual(client.list_upscale_models(), ("photo.pth",))
