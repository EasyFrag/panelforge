"""Scene/subject integration with fake gateways only; run by the user."""

from dataclasses import replace
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from panelforge.application import ChangeViewRunner, Krea2AssistedService, Krea2EditService, Krea2EditAttemptRequest
from panelforge.application.krea2_restage import DEFAULT_INSTRUCTION, RestagingConflictError
from panelforge.domain.assisted_composition import AssistedComposition
from panelforge.domain.krea2_edit import Krea2EditMetadata, Krea2EditSettings
from panelforge.features.lab.web import create_app, serialize_krea2_edit_source
from panelforge.infrastructure.comfy import ComfyImageRef
from panelforge.infrastructure.edit_images import PillowEditImages
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.presets import load_krea2_edit_workflow, load_krea2_batch_workflow, ChangeViewPresetRecipe, load_change_view_preset
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore, LocalKrea2AssistedProjectStore, LocalRunStore
from panelforge.infrastructure.storage.krea2_edits import _to_dict, _from_dict
from tests.test_krea2_assisted_branches import fixture
from tests.test_krea2_assisted import WORKFLOW as ASSISTED_WORKFLOW, Gateway
from tests.test_krea2_assisted_web import CHANGE_VIEW
from tests.test_krea2_edit import ROOT, FakeGateway


def png(image, **kwargs):
    output = BytesIO()
    image.save(output, format="PNG", **kwargs)
    return output.getvalue()


class NoComfy:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected ComfyUI operation: {name}")


class FakeRender:
    def __init__(self):
        self.uploads = []
        self.workflows = []
        self.output = png(Image.new("RGB", (96, 64), "orange"))

    def upload_image(self, content, *, filename, subfolder=""):
        self.uploads.append((content, filename))
        return ComfyImageRef(filename, subfolder, "input")

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        return "fake-execution"

    def get_history(self, prompt_id):
        return {prompt_id: {"status": {"completed": True, "status_str": "success"},
                           "outputs": {"29": {"images": [{"filename": "generated.png", "subfolder": "", "type": "output"}]}}}}

    def download_output(self, **kwargs):
        return self.output


class RestagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = LocalAssetStore(self.root)
        self.store = LocalKrea2EditStore(self.root)
        self.assisted_store = LocalKrea2AssistedProjectStore(self.root)
        image = Image.new("RGB", (64, 96), "blue")
        exif = Image.Exif(); exif[274] = 6
        self.scene_bytes = png(image, exif=exif)
        self.scene = self.assets.create(self.scene_bytes, media_type="image/png")
        self.subject_bytes = png(Image.new("RGB", (32, 32), "green"))
        self.subject = self.assets.create(self.subject_bytes, media_type="image/png")
        project = fixture()
        self.project = self.assisted_store.create(replace(project,
            attempts=(replace(project.attempts[0], output_asset_id=self.subject.asset_id),)))
        base = ROOT / "workflows/image.edit/krea2-identity"
        self.single = load_krea2_edit_workflow(base / "0.2.0")
        self.dual = load_krea2_edit_workflow(base / "0.3.0")
        self.gateway = FakeGateway(json.dumps({"message": "Je replace le sujet dans la pièce.", "prompt": DEFAULT_INSTRUCTION}))
        self.service = Krea2EditService(gateway=self.gateway, workflow=self.single,
            historical_workflows=(self.dual,), comfy=NoComfy(), assets=self.assets, sources=self.store,
            edit_images=PillowEditImages(), project_exporter=LocalKrea2ProjectExporter(self.root / "exports"), poll_interval=0.001)
        self.assisted = Krea2AssistedService(gateway=Gateway([]), recipes=SimpleNamespace(current=lambda: ()),
            workflow=load_krea2_batch_workflow(ASSISTED_WORKFLOW), comfy=NoComfy(), assets=self.assets,
            projects=self.assisted_store, resources=SimpleNamespace(list_models=lambda: (), list_loras=lambda: ()),
            exporter=LocalKrea2CreationExporter(self.root / "creations"))

    def prepare(self, *, instruction=DEFAULT_INSTRUCTION, request_id="one", scene_asset_id=None):
        return self.service.restage_assisted(self.project, self.project.attempts[0].attempt_id,
            scene_asset_id=scene_asset_id or self.scene.asset_id, instruction=instruction, request_id=request_id)

    def settings(self, source):
        return Krea2EditSettings(model_name=source.metadata.model_name, aspect_ratio=source.metadata.aspect_ratio,
            megapixels=1, seed=42, ref_boost=4, steps=10)

    def complete(self):
        source = self.prepare()
        source = self.service.prepare_attempt(source.source_id, Krea2EditAttemptRequest(DEFAULT_INSTRUCTION, self.settings(source)))
        attempt_id = source.attempts[-1].attempt_id
        comfy = FakeRender(); self.service.comfy = comfy
        self.service.queue_attempt(source.source_id, attempt_id)
        result = self.service.execute_attempt(source.source_id, attempt_id)
        self.assertEqual(result.attempts[-1].status.value, "succeeded", result.attempts[-1].error)
        return result, comfy

    def test_preparation_is_idempotent_and_preserves_assisted_without_rendering(self):
        source = self.prepare()
        self.assertEqual(source.recipe, self.dual.reference)
        self.assertEqual(source.source_asset_id, self.scene.asset_id)
        self.assertEqual(source.subject_reference.asset_id, self.subject.asset_id)
        self.assertEqual(source.metadata.aspect_ratio.dimensions, (3, 2))
        self.assertEqual(source.metadata.loras, ())
        self.assertEqual(source.metadata.model_name, self.single.defaults["model_id"])
        self.assertEqual(source.attempts, ())
        self.assertEqual(source.revisions, ())
        self.assertEqual(self.prepare(), source)
        with self.assertRaises(RestagingConflictError):
            self.prepare(instruction="Different action")
        with self.assertRaises(RestagingConflictError):
            self.prepare(scene_asset_id=self.subject.asset_id)
        self.assertNotEqual(self.prepare(request_id="two").source_id, source.source_id)
        self.assertEqual(self.assisted_store.get(self.project.project_id), self.project)
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.assets.read_bytes(self.scene.asset_id), self.scene_bytes)

    def test_graph_roles_pixel_path_and_wrong_workflow_rejection(self):
        source = self.prepare()
        args = dict(source_image="scene.png", subject_image="subject.png", prompt=DEFAULT_INSTRUCTION,
                    settings=self.settings(source), output_prefix="test", sidecar_text="provenance")
        graph = self.dual.build(**args)
        scene_node = self.dual.inputs["source_image"].node_id
        subject_node = self.dual.inputs["subject_image"].node_id
        self.assertEqual(graph[scene_node]["inputs"]["image"], "scene.png")
        self.assertEqual(graph[subject_node]["inputs"]["image"], "subject.png")
        encoders = [node for node in graph.values() if node["class_type"] == "Krea2EditGroundedEncode"]
        self.assertEqual(len(encoders), 2)
        for node in encoders:
            self.assertEqual(node["inputs"]["image"], [scene_node, 0])
            self.assertEqual(node["inputs"]["image_b"], [subject_node, 0])
        patch_inputs = next(node["inputs"] for node in graph.values() if node["class_type"] == "Krea2EditModelPatch")
        self.assertEqual(patch_inputs["source_image"], [scene_node, 0])
        self.assertEqual(patch_inputs["source_image_b"], [subject_node, 0])
        self.assertEqual(graph[patch_inputs["source_latent_b"][0]]["inputs"]["pixels"], [subject_node, 0])
        sampler = next(node for node in graph.values() if node["class_type"] == "KSampler")
        self.assertEqual(patch_inputs["target_latent"], sampler["inputs"]["latent_image"])
        with self.assertRaises(ValueError):
            self.single.build(**args)
        with self.assertRaises(ValueError):
            self.dual.build(**{**args, "subject_image": None})
        with self.assertRaises(ValueError):
            self.service.prepare_attempt(source.source_id, Krea2EditAttemptRequest(DEFAULT_INSTRUCTION, self.settings(source), "0.2.0"))
        single = self.service.add_source(asset_id=self.scene.asset_id, filename="scene.png", metadata=Krea2EditMetadata())
        with self.assertRaises(ValueError):
            self.service.prepare_attempt(single.source_id, Krea2EditAttemptRequest(DEFAULT_INSTRUCTION, self.settings(source), "0.3.0"))

    def test_two_uploads_feedback_export_and_next_stage(self):
        source, comfy = self.complete()
        self.assertEqual(len(comfy.uploads), 2)
        with Image.open(BytesIO(comfy.uploads[0][0])) as image:
            self.assertEqual(image.size, (96, 64))
            self.assertNotIn(274, image.getexif())
        with Image.open(BytesIO(comfy.uploads[1][0])) as image:
            self.assertEqual(image.size, (32, 32))
        result = source.attempts[-1]
        self.assertEqual(result.output_dimensions, (96, 64))
        list(self.service.stream_prepare_prompt(source.source_id, "Move her closer to the wall", "fake",
            feedback_attempt_id=result.attempt_id, assistance_version="3.0.0"))
        request = self.gateway.requests[-1]
        self.assertEqual([image.label for image in request.images], ["STAGE SOURCE", "SUBJECT REFERENCE", "GENERATED FEEDBACK"])
        self.assertEqual([image.content for image in request.images], [comfy.uploads[0][0], comfy.uploads[1][0], comfy.output])
        self.assertIn("TWO-IMAGE IDENTITY EDIT CONTRACT", request.system_prompt)
        child = self.service.promote_attempt(source.source_id, result.attempt_id, project_name="Room", step_name="Diamonds")
        self.assertIsNone(child.subject_reference)
        self.assertIsNone(child.metadata.prompt)
        self.assertIsNone(child.generated_prompt)
        self.assertEqual(child.recipe, self.single.reference)
        self.assertEqual(child.source_asset_id, result.output_asset_id)
        self.assertIsNone(child.export_error, child.export_error)
        folder = Path(child.export_path)
        manifest = json.loads((folder / "project.json").read_text(encoding="utf-8"))
        entry = manifest["accepted_chain"][0]
        self.assertEqual((folder / entry["image"]).read_bytes(), comfy.output)
        self.assertEqual((folder / entry["subject_reference"]["file"]).read_bytes(), self.subject_bytes)

    def test_schema_ten_reopens_and_old_stages_have_no_subject(self):
        source = self.prepare()
        self.assertEqual(_to_dict(source)["schema_version"], 12)
        self.assertEqual(LocalKrea2EditStore(self.root).get(source.source_id), source)
        single = self.service.add_source(asset_id=self.scene.asset_id, filename="old.png", metadata=Krea2EditMetadata())
        for schema in range(1, 10):
            raw = _to_dict(single); raw["schema_version"] = schema; raw.pop("subject_reference")
            self.assertIsNone(_from_dict(raw).subject_reference)
        self.assertEqual(serialize_krea2_edit_source(source)["subject_reference"]["asset_id"], self.subject.asset_id)
        self.assertEqual(source.restart().subject_reference, source.subject_reference)

    def test_http_preparation_and_removed_mask_api(self):
        runner = ChangeViewRunner(recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=NoComfy(), assets=self.assets, runs=LocalRunStore(self.root))
        prefix = f"/api/image-lab/krea2-assisted/projects/{self.project.project_id}"
        attempt = self.project.attempts[0].attempt_id
        with patch.object(self.assisted, "start_render_worker"), TestClient(create_app(runner, krea2_assisted=self.assisted, krea2_edit=self.service)) as client:
            form = {"scene_asset_id": self.scene.asset_id, "instruction": DEFAULT_INSTRUCTION, "request_id": "http"}
            first = client.post(f"{prefix}/attempts/{attempt}/restage", json=form)
            self.assertEqual(first.status_code, 201, first.text)
            self.assertEqual(first.json()["source"]["attempts"], [])
            retry = client.post(f"{prefix}/attempts/{attempt}/restage", json=form)
            self.assertEqual(first.json()["source"]["source_id"], retry.json()["source"]["source_id"])
            self.assertEqual(client.post(f"{prefix}/attempts/{attempt}/restage", json={**form, "instruction": "Changed"}).status_code, 409)
            self.assertEqual(client.post(f"{prefix}/attempts/{attempt}/composition").status_code, 404)
            self.assertEqual(client.post(f"{prefix}/composition-images").status_code, 404)
            upload = client.post(f"{prefix}/scene-images", files={"image": ("scene.png", self.scene_bytes, "image/png")})
            self.assertEqual(upload.status_code, 201, upload.text)
        self.assertEqual(self.assisted_store.get(self.project.project_id), self.project)
        self.assertEqual(self.gateway.requests, [])

    def test_legacy_assisted_compositions_still_open_export_and_restore_memory(self):
        original = self.project.attempts[0]
        mask = self.assets.create(png(Image.new("L", (32, 32), 128)), media_type="image/png")
        output = self.assets.create(png(Image.new("RGB", (32, 32), "yellow")), media_type="image/png")
        candidate = replace(original, attempt_id="old-composition", kind="composition", execution_id=None,
            compiled_workflow_sha256=None, queue_order=None, output_asset_id=output.asset_id,
            composition=AssistedComposition(original.attempt_id, original.attempt_id, self.scene.asset_id,
                self.subject.asset_id, mask.asset_id, "legacy", hashlib.sha256(b"legacy-mask").hexdigest(), 32, 32))
        project = self.assisted_store.save(self.project.add_attempt(candidate))
        self.assertEqual(LocalKrea2AssistedProjectStore(self.root).get(project.project_id), project)
        feedback = self.assisted.select_feedback(project.project_id, candidate.attempt_id)
        self.assertEqual(feedback.feedback_attempt_id, candidate.attempt_id)
        saved = self.assisted.save_image(project.project_id, candidate.attempt_id)
        self.assertIsNone(saved.export_error)
        self.assertEqual((Path(saved.export_path) / "creation_001_composition_001.png").read_bytes(), self.assets.read_bytes(output.asset_id))
        self.assertEqual(saved.branch_from_attempt(candidate.attempt_id, "past").turns, self.project.turns[:2])
