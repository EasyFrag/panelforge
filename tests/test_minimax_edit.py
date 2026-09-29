"""MiniMax workshop regressions. All model/render gateways are local fakes."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import unittest
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.minimax_edit import MinimaxEditService
from panelforge.application.dlss_candidates import DlssCandidates
from panelforge.application.qwen_edit import QwenEditConflict
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.minimax_edit import MinimaxEditSettings, render_inputs, validate_prompt
from panelforge.features.lab.minimax_edit_web import minimax_edit_router
from panelforge.features.lab.qwen_edit_web import qwen_edit_router
from panelforge.infrastructure.minimax_edit_images import PillowMinimaxEditImages
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from panelforge.infrastructure.storage.minimax_edits import LocalMinimaxEditStore
from panelforge.infrastructure.qwen_project_exports import project_zip
from test_qwen_edit import QwenEditFixture, Comfy, png

ROOT = Path(__file__).resolve().parents[1]


class MinimaxComfy(Comfy):
    def __init__(self, output_node_id):
        super().__init__()
        self.output_node_id = output_node_id

    def get_history(self, execution_id):
        value = super().get_history(execution_id)
        outputs = value[execution_id]["outputs"]
        value[execution_id]["outputs"] = {self.output_node_id: next(iter(outputs.values()))}
        return value


class MinimaxFixture(QwenEditFixture):
    def setUp(self):
        super().setUp()
        self.qwen = self.service
        self.qwen_project_id = self.project_id
        self.workflow = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.0.0")
        self.comfy = MinimaxComfy(self.workflow.output_node_id)
        self.store = LocalMinimaxEditStore(self.temporary.name)
        self.service = MinimaxEditService(gateway=self.gateway, workflow=self.workflow, comfy=self.comfy,
            assets=self.assets, projects=self.store, images=PillowMinimaxEditImages(),
            edit_images=self.qwen.edit_images, retouch_compositor=self.qwen.retouch_compositor,
            exporter=self.qwen.exporter, poll_interval=.001)
        self.project = self.service.create(name="Atelier Minimax", content=png())
        self.project_id, self.stage_id = self.project["id"], self.project["active_stage_id"]

    def guide(self, request_id="guide"):
        stage = self.current()
        self.service.save_guide(self.project_id, self.stage_id, png("white", mode="L"),
            revision=stage["revision"], request_id=request_id,
            source_asset_id=stage["source_asset_id"], source_width=160, source_height=96)


class MinimaxEditTest(MinimaxFixture):
    def test_guide_and_render_roles_match_compiled_picture_order_and_frozen_context(self):
        self.guide()
        self.reference("Palette assistant", "assistant")
        reference = self.reference("Costume", "render")
        message = self.message()
        self.assertEqual(message["policy_version"], "1.0.0")
        self.assertEqual(self.gateway.requests[-1].operation_id, "minimax.edit.assistance@1.0.0")
        self.assertEqual([r["tag"] for r in message["context"]["render_inputs"]],
                         ["<Picture 1>", "<Picture 2>", "<Picture 3>"])
        attempt = self.queue()
        refs = deepcopy(self.current()["references"])
        next(r for r in refs if r["id"] == reference["id"])["active"] = False
        self.update(references=refs)
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        result = self.current()["attempts"][-1]
        self.assertEqual(result["status"], "succeeded", result["error"])
        self.assertEqual(result["engine"], "minimax")
        self.assertEqual(result["finish"]["status"], "raw")
        self.assertEqual(result["output_asset_id"], result["raw_output_asset_id"])
        self.assertEqual(len(self.comfy.uploads), 2)  # Source+guide RGBA, costume; assistant excluded.
        graph = self.comfy.submitted[-1]
        manifest = self.workflow.manifest
        encoder = graph[manifest["conditioning_node"]]["inputs"]
        slots = manifest["image_slots"]
        self.assertEqual([encoder[s["input"]] for s in slots[:3]],
                         [[s["scale_node"], 0] for s in slots[:3]])
        self.assertEqual(graph[manifest["guide"]["mask_node"]]["inputs"]["mask"], [slots[0]["load_node"], 1])
        self.assertNotIn("negative_prompt", encoder)
        self.assertEqual(len(self.gateway.requests), 1)
        self.service.restore_attempt(self.project_id, self.stage_id, result["id"], revision=self.current()["revision"])
        restored = self.service.public(self.service.get(self.project_id))["stages"][0]
        self.assertTrue(restored["prompt_ready"])
        self.assertEqual(len(restored["render_inputs"]), 3)

    def test_projects_and_endpoints_are_isolated_from_qwen(self):
        with self.assertRaises(ValueError):
            self.store.get(self.qwen_project_id)
        with self.assertRaises(ValueError):
            self.qwen.projects.get(self.project_id)
        app = FastAPI()
        app.include_router(qwen_edit_router(self.qwen))
        app.include_router(minimax_edit_router(self.service))
        with TestClient(app) as client:
            spec = client.get("/api/image-lab/minimax-edit/spec").json()
            self.assertEqual(spec["defaults"]["steps"], 18)
            self.assertNotIn("cfg", spec["defaults"])
            self.assertNotIn("negative_prompt", spec["defaults"])
            self.assertEqual(spec["max_render_images"], 9)
            self.assertEqual(spec["fixed"]["scheduler"], "beta")
            for engine, project_id in (("qwen", self.qwen_project_id), ("minimax", self.project_id)):
                projects = client.get(f"/api/image-lab/{engine}-edit/projects").json()["projects"]
                self.assertEqual([p["id"] for p in projects], [project_id])
            url = f"/api/image-lab/minimax-edit/projects/{self.project_id}/stages/{self.stage_id}"
            settings = {**self.current()["settings"], "cfg": 2}
            response = client.patch(url, json={"revision": self.current()["revision"], "changes": {"settings": settings}})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("cfg", self.current()["settings"])
        self.assertEqual(self.comfy.submitted, [])

    def test_baseline_models_sampling_and_geometry_survive_reference_expansion(self):
        before = deepcopy(self.workflow.template)
        settings = MinimaxEditSettings(seed=str(2**64 - 1))
        self.assertEqual(settings.dimensions((2016, 3584)), (2016, 3584))
        landscape = settings.dimensions((1600, 900))
        self.assertGreater(landscape[0], landscape[1])
        graph = self.workflow.build(images=["base.png"], prompt="Edit <Picture 1>.", settings=settings,
            dimensions=landscape, composition=False, output_prefix="test/minimax")
        for binding in self.workflow.manifest["components"].values():
            self.assertEqual(graph[binding["node_id"]], before[binding["node_id"]])
        for dimension, value in zip(("width", "height"), landscape):
            for binding in self.workflow.manifest["inputs"][dimension]:
                self.assertEqual(graph[binding["node_id"]]["inputs"][binding["input"]], value)
        self.assertEqual(self.workflow.template, before)
        self.assertEqual(self.workflow.reference.workflow_sha256,
                         "dca8614c053ce994f45c26c97288118fc4833ca058cfa266dfebcb8296b2215c")

    def test_nine_reference_limit_counts_source_and_guide_and_rejects_foreign_tags(self):
        self.guide()
        for i in range(7):
            self.reference(f"Reference {i}", "render")
        self.assertEqual(len(render_inputs(self.current())), 9)
        with self.assertRaisesRegex(ValueError, "9 images"):
            self.reference("Overflow", "render")
        self.assertEqual(len(render_inputs(self.current())), 9)
        for text in ("Edit <image1>.", "Edit <Picture 10>.", "Edit <Picture 1>."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_prompt(text, render_inputs(self.current()))

    def test_guide_changes_invalidate_prompt_and_no_call_is_implicit(self):
        self.message()
        self.guide()
        with self.assertRaisesRegex(ValueError, "actualiser"):
            self.queue()
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(self.comfy.submitted, [])

    def test_composition_requires_reference_and_accept_resume_exports_preserve_engine(self):
        project = self.service.create(name="Composition", composition=True)
        self.project_id, self.stage_id = project["id"], project["active_stage_id"]
        self.update(draft="Compose une image.", model_id="fake-vision")
        with self.assertRaisesRegex(ValueError, "référence"):
            self.service.begin_message(self.project_id, self.stage_id, revision=self.current()["revision"], request_id="empty")
        self.reference("Personnage", "render")
        self.message()
        result = self.render()
        self.assertEqual(result["status"], "succeeded", result["error"])
        self.assertNotIn(self.workflow.manifest["guide"]["mask_node"], self.comfy.submitted[-1])
        project = self.service.accept(self.project_id, self.stage_id, result["id"], revision=self.current()["revision"])
        self.assertEqual(project["stages"][-1]["source_asset_id"], result["output_asset_id"])
        self.assertEqual(project["stages"][-1]["settings"]["steps"], 18)
        resumed = self.service.resume(self.project_id, project["active_stage_id"], request_id="resume")
        self.assertTrue(resumed["id"].startswith("minimax-"))
        self.assertEqual(resumed["engine"], "minimax")
        archive = zipfile.ZipFile(BytesIO(project_zip(resumed, self.assets, self.store)))
        saved = json.loads(archive.read("project.json"))
        self.assertEqual(saved["engine"], "minimax")
        self.assertTrue(any(name.startswith("workflows/") for name in archive.namelist()))

    def test_cancel_crop_and_dlss_keep_the_workshop_identity(self):
        self.update(prompt="Recolor the wall in <Picture 1>.")
        queued = self.queue()
        self.service.cancel_attempt(self.project_id, self.stage_id, queued["id"])
        self.assertEqual(self.current()["attempts"][-1]["status"], "cancelled")
        attempt = self.queue("second")
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        candidates = DlssCandidates(edit=None, assisted=None, h3=None, qwen=self.qwen, minimax=self.service)
        snapshot = candidates.prepare("minimax", self.project_id, attempt["id"], DlssSettings(size="source"))
        self.assertEqual(snapshot["owner"], "minimax")
        candidates.validate_current(snapshot)
        output = self.assets.create(png("gold"), media_type="image/png")
        job = {"job_id": "dlss-" + "a"*32, "snapshot": snapshot, "report_asset_id": "report",
               "output_metadata": {"width": 160, "height": 96}, "settings": {"size": "source"},
               "output_asset_id": output.asset_id, "created_at": attempt["created_at"], "finished_at": attempt["created_at"]}
        candidate = candidates.attach(job, self.workflow)
        self.assertEqual(candidates.attach(job, self.workflow), candidate)
        self.assertEqual(self.current()["attempts"][-1]["kind"], "dlss")
        self.assertEqual(self.qwen.get(self.qwen_project_id)["stages"][0]["attempts"], [])
        stage = self.current()
        project = self.service.crop_source(self.project_id, self.stage_id, revision=stage["revision"],
            request_id="crop", source_asset_id=stage["source_asset_id"],
            source_width=160, source_height=96, x=0, y=0, width=96, height=96)
        self.assertEqual(project["stages"][-1]["source_dimensions"], [96, 96])
        with self.assertRaises(ValueError):
            candidates.validate_current(snapshot)
        self.assertEqual(len(self.comfy.submitted), 1)


class MinimaxUnavailableTest(unittest.TestCase):
    def test_unconfigured_endpoint_fails_without_affecting_the_other_workshops(self):
        app = FastAPI()
        app.include_router(minimax_edit_router(None))
        with TestClient(app) as client:
            response = client.get("/api/image-lab/minimax-edit/spec")
            self.assertEqual(response.status_code, 503)
            self.assertIn("Minimax", response.json()["detail"])
