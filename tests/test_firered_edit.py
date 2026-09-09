"""FireRed contracts, using in-memory PNGs and fake transports only."""

from copy import deepcopy
from dataclasses import replace
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from panelforge.application import ChangeViewRunner, Krea2EditAttemptRequest, Krea2EditService
from panelforge.application import firered_edit_assistance, krea2_edit_assistance_v3
from panelforge.domain import Krea2AspectRatio, Krea2EditMetadata, Krea2EditSettings
from panelforge.domain.edit_settings import edit_output_dimensions
from panelforge.domain.firered_edit import FireRedEditSettings
from panelforge.features.lab.web import create_app, serialize_krea2_edit_source
from panelforge.infrastructure.edit_images import PillowEditImages
from panelforge.infrastructure.krea2_image_metadata import recover_krea2_metadata
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter, _accepted_sidecar
from panelforge.infrastructure.krea2_retouch import PillowRetouchCompositor
from panelforge.infrastructure.krea2_upscale import PillowUpscaleImages
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset, load_krea2_edit_workflow
from panelforge.infrastructure.presets.firered_edit import load_firered_edit_workflow
from panelforge.infrastructure.presets.image_upscale import load_image_upscale_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore, LocalRunStore
from panelforge.infrastructure.storage.krea2_edits import _to_dict, _from_dict
from tests.test_krea2_edit import FakeGateway, WORKFLOW, ROOT
from tests.test_krea2_edit_web import CHANGE_VIEW
from tests.test_krea2_upscale import FakeUpscaleComfy


FIRE = ROOT / "workflows/image.edit/firered/0.1.0"
PROMPT = "Replace the white paint inside the outline with exposed brown soil."


def png(image, **kwargs):
    stream = BytesIO()
    image.save(stream, format="PNG", **kwargs)
    return stream.getvalue()


class FireRedTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = LocalAssetStore(self.root)
        self.store = LocalKrea2EditStore(self.root)
        self.fire = load_firered_edit_workflow(FIRE)
        self.old = load_krea2_edit_workflow(WORKFLOW)
        self.current = load_krea2_edit_workflow(WORKFLOW.parent / "0.2.0")
        self.comfy = FakeUpscaleComfy()
        self.gateway = FakeGateway(json.dumps({"message": "Je propose une terre brune.", "prompt": PROMPT}))
        self.service = Krea2EditService(
            gateway=self.gateway, workflow=self.current, historical_workflows=(self.old, self.fire),
            comfy=self.comfy, assets=self.assets, sources=self.store, poll_interval=0.001,
            edit_images=PillowEditImages(), retouch_compositor=PillowRetouchCompositor(),
            upscale_workflow=load_image_upscale_workflow(ROOT / "workflows/image.upscale/esrgan/0.1.0"),
            upscale_images=PillowUpscaleImages(),
            project_exporter=LocalKrea2ProjectExporter(self.root / "exports"),
        )
        self.source_bytes = png(Image.new("RGB", (16, 24), "blue"))
        asset = self.assets.create(self.source_bytes, media_type="image/png")
        self.source = self.service.add_source(asset_id=asset.asset_id, filename="wall.png", metadata=Krea2EditMetadata())
        self.settings = FireRedEditSettings(self.fire.defaults["model_id"], 1, 2**64 - 1)

    def prepare(self, settings=None, **kwargs):
        source = self.service.prepare_attempt(self.source.source_id,
            Krea2EditAttemptRequest(PROMPT, settings or self.settings, **kwargs))
        return source, source.attempts[-1]

    def complete(self, settings=None):
        source, attempt = self.prepare(settings)
        self.service.queue_attempt(source.source_id, attempt.attempt_id)
        source = self.service.execute_attempt(source.source_id, attempt.attempt_id)
        result = next(a for a in source.attempts if a.attempt_id == attempt.attempt_id)
        self.assertEqual(result.status.value, "succeeded", result.error)
        return source, result

    def test_import_is_exact_and_mode_switch_only_changes_manifest_controls(self):
        raw = (FIRE / "workflow_api.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "dd1e6ea1668edb64de057e1dc900dfe3fd2951685e2f91dd2d7cbc5fd6456660")
        original = json.loads(raw)
        def value(name):
            binding = self.fire.manifest["inputs"][name]
            return original[binding["node_id"]]["inputs"][binding["input"]]
        def compile(settings):
            return self.fire.build(source_image=value("source_image"), prompt=value("prompt"),
                settings=settings, output_prefix=value("output_prefix"), sidecar_text="local only")
        initial = replace(self.settings, seed=value("seed"))
        self.assertEqual(compile(initial), original)
        for mode, steps, cfg in (("lightning", 8, 1), ("standard", 40, 4)):
            settings = FireRedEditSettings(initial.model_name, 2.5, initial.seed, mode)
            self.assertEqual((settings.steps, settings.cfg), (steps, cfg))
            graph = compile(settings)
            expected = deepcopy(original)
            for name, data in {"lightning": mode == "lightning", "megapixels": 2.5}.items():
                b = self.fire.manifest["inputs"][name]
                expected[b["node_id"]]["inputs"][b["input"]] = data
            self.assertEqual(graph, expected)
        custom = replace(initial, mode="standard", steps=31, cfg=3.5)
        graph = compile(custom)
        for name, expected in (("steps_standard", 31), ("cfg_standard", 3.5), ("steps_lightning", 8)):
            b = self.fire.manifest["inputs"][name]
            self.assertEqual(graph[b["node_id"]]["inputs"][b["input"]], expected)
        self.assertEqual(self.comfy.submitted, [])

    def test_engine_and_recipe_id_disambiguate_identical_versions(self):
        krea = Krea2EditSettings(self.old.defaults["model_id"], Krea2AspectRatio.SQUARE, 1, 42)
        for settings, recipe in ((krea, self.old), (self.settings, self.fire)):
            source, attempt = self.prepare(settings, workflow_version="0.1.0", workflow_id=recipe.reference.recipe_id)
            self.assertEqual(self.service.workflow_for_attempt(source, attempt).reference, recipe.reference)
        before = self.store.get(self.source.source_id)
        for bad in ({"workflow_id": self.old.reference.recipe_id}, {"workflow_version": "99.0.0"}):
            with self.assertRaises(ValueError):
                self.prepare(**bad)
        with self.assertRaises(ValueError):
            self.prepare(replace(self.settings, model_name="unrelated.safetensors"))
        self.assertEqual(self.store.get(self.source.source_id), before)
        for fields in ({"megapixels": float("nan")}, {"steps": True}, {"cfg": float("inf")}, {"seed": -1}, {"mode": "unknown"}):
            with self.assertRaises((ValueError, TypeError)):
                replace(self.settings, **fields)

    def test_orientation_native_output_and_roundtrip_without_modifying_source(self):
        image = Image.new("RGB", (24, 16), "blue")
        image.putpixel((0, 0), (255, 255, 0))
        exif = Image.Exif(); exif[274] = 6
        encoded = png(image, exif=exif)
        asset = self.assets.create(encoded, media_type="image/png")
        self.source = self.service.add_source(asset_id=asset.asset_id, filename="rotated.png", metadata=Krea2EditMetadata())
        source, attempt = self.complete()
        with Image.open(BytesIO(self.comfy.uploads[-1])) as normalized:
            self.assertEqual(normalized.size, (16, 24))
            self.assertEqual(normalized.getexif().get(274, 1), 1)
            self.assertEqual(normalized.getpixel((15, 0))[:3], (255, 255, 0))
        self.assertEqual(self.assets.read_bytes(asset.asset_id), encoded)
        self.assertEqual(attempt.output_dimensions, (8, 12))
        self.assertEqual(self.assets.read_bytes(attempt.output_asset_id), self.comfy.output)
        self.assertEqual(LocalKrea2EditStore(self.root).get(source.source_id), source)
        ui = serialize_krea2_edit_source(source)["attempts"][-1]
        self.assertEqual(ui["settings"]["seed"], str(2**64 - 1))
        self.assertEqual(ui["settings"]["resolution"], {"width": 8, "height": 12})
        self.assertNotIn("loras", ui["settings"])
        self.assertNotIn("ref_boost", ui["settings"])

    def test_detached_completion_uses_native_dimensions_too(self):
        source, candidate = self.prepare()
        running = candidate.queue().start("detached-fire", "a" * 64)
        self.store.save(source.replace_attempt(running))
        recovered = self.service.get(source.source_id)
        self.assertEqual(recovered.attempts[-1].status.value, "succeeded")
        self.assertEqual(recovered.attempts[-1].output_dimensions, (8, 12))
        self.assertEqual(self.comfy.submitted, [])

    def test_invalid_source_or_output_does_not_create_a_successful_candidate(self):
        corrupt = self.assets.create(b"\x89PNG\r\n\x1a\ninvalid", media_type="image/png")
        bad_source = self.service.add_source(asset_id=corrupt.asset_id, filename="bad.png", metadata=Krea2EditMetadata())
        with self.assertRaises(ValueError):
            self.service.prepare_attempt(bad_source.source_id, Krea2EditAttemptRequest(PROMPT, self.settings))
        self.assertEqual(self.store.get(bad_source.source_id).attempts, ())
        source, attempt = self.prepare()
        self.comfy.output = b"\x89PNG\r\n\x1a\ninvalid"
        self.service.queue_attempt(source.source_id, attempt.attempt_id)
        failed = self.service.execute_attempt(source.source_id, attempt.attempt_id).attempts[-1]
        self.assertEqual(failed.status.value, "failed")
        self.assertIsNone(failed.output_asset_id)
        self.assertIsNone(failed.output_dimensions)

    def test_retouch_feedback_upscale_and_promotion_keep_exact_selected_candidate(self):
        source, generation = self.complete()
        mask = png(Image.new("L", (16, 24), 128))
        source, retouch = self.service.save_retouch(source.source_id, generation.attempt_id, mask, request_id="paint")
        self.assertEqual(len(self.comfy.submitted), 1)
        with self.assertRaises(ValueError):
            self.service.queue_attempt(source.source_id, retouch.attempt_id)
        reopened = self.service.prepare_retouch(source.source_id, retouch.attempt_id)
        self.assertEqual(reopened["original_attempt_id"], generation.attempt_id)
        self.assertEqual(self.service.save_retouch(source.source_id, generation.attempt_id, mask, request_id="paint")[1], retouch)
        result = list(self.service.stream_prepare_prompt(source.source_id, "Keep this shape", "fake",
            assistance_version="3.0.0", render_engine="firered", feedback_attempt_id=retouch.attempt_id))[-1].source
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, firered_edit_assistance.OPERATION)
        self.assertEqual(request.images[1].content, self.assets.read_bytes(retouch.output_asset_id))
        self.assertEqual(result.revisions[-1].render_engine, "firered")
        source, improved = self.service.prepare_upscale(source.source_id, retouch.attempt_id,
            model_name=self.comfy.models[0], request_id="improve")
        self.comfy.output = png(Image.new("RGB", (16, 24), "red"))
        self.service.queue_attempt(source.source_id, improved.attempt_id)
        source = self.service.execute_attempt(source.source_id, improved.attempt_id)
        improved = next(a for a in source.attempts if a.attempt_id == improved.attempt_id)
        self.assertEqual(improved.status.value, "succeeded", improved.error)
        self.assertEqual(improved.settings, generation.settings)
        self.assertEqual(improved.upscale.mask_asset_id, retouch.retouch.mask_asset_id)
        self.assertEqual(edit_output_dimensions(improved), (16, 24))
        child = self.service.promote_attempt(source.source_id, retouch.attempt_id, step_name="Earth", project_name="Fire project")
        self.assertEqual(child.source_asset_id, retouch.output_asset_id, "later unused upscale must not win")
        self.assertEqual(child.metadata.firered_settings, generation.settings)
        self.assertEqual(child.recipe, self.fire.reference)
        self.assertEqual(child.metadata.loras, ())
        self.assertIsNone(child.metadata.ref_boost)
        parent = self.store.get(source.source_id)
        self.assertIsNone(parent.export_error)
        exported = list(Path(child.export_path).rglob("*.png"))
        self.assertIn(self.assets.read_bytes(retouch.output_asset_id), [p.read_bytes() for p in exported])
        sidecar = _accepted_sidecar("Fire project", parent, retouch)
        self.assertEqual(sidecar["output_dimensions"], {"width": 16, "height": 24})
        self.assertEqual(sidecar["render"]["base_width"], 8)
        self.assertEqual(sidecar["render"]["engine"], "firered")
        restored = recover_krea2_metadata(b"", sidecar=json.dumps(sidecar).encode())
        self.assertEqual(restored.firered_settings, generation.settings)
        self.assertEqual(LocalKrea2EditStore(self.root).get(child.source_id), child)

    def test_shared_conversation_keeps_versions_and_switch_does_not_rewrite_history(self):
        first = list(self.service.stream_prepare_prompt(self.source.source_id, "FIRST_EDIT", "fake",
            assistance_version="3.0.0"))[-1].source
        self.assertEqual(self.gateway.requests[-1].system_prompt, krea2_edit_assistance_v3.SYSTEM)
        second = list(self.service.stream_prepare_prompt(self.source.source_id, "SECOND_EDIT", "fake",
            assistance_version="3.0.0", render_engine="firered"))[-1].source
        self.assertEqual(second.revisions[0], first.revisions[0])
        self.assertEqual(second.revisions[-1].render_engine, "firered")
        self.assertIn("FIRST_EDIT", self.gateway.requests[-1].user_prompt)
        self.assertIn("FireRed Image Edit 1.1", self.gateway.requests[-1].system_prompt)
        self.assertEqual(_from_dict(_to_dict(second)), second)
        self.assertEqual(self.comfy.submitted, [])

    def test_schema_nine_reads_old_krea_projects_without_new_fields(self):
        settings = Krea2EditSettings(self.old.defaults["model_id"], Krea2AspectRatio.SQUARE, 1, 42)
        source, _ = self.prepare(settings)
        current = _to_dict(source)
        self.assertEqual(current["schema_version"], 11)
        for version in range(1, 9):
            raw = deepcopy(current); raw["schema_version"] = version
            raw["metadata"].pop("firered_settings")
            raw["attempts"][0]["settings"].pop("engine")
            raw["attempts"][0].pop("output_dimensions")
            self.assertEqual(_from_dict(raw).attempts[0].settings, settings)

    def test_native_png_metadata_reads_selected_branch_without_executing_graph(self):
        for mode in ("lightning", "standard"):
            settings = FireRedEditSettings(self.settings.model_name, 1.7, 123, mode)
            graph = self.fire.build(source_image="source.png", prompt=PROMPT, settings=settings,
                output_prefix="unused", sidecar_text="unused")
            info = PngImagePlugin.PngInfo(); info.add_text("prompt", json.dumps(graph))
            metadata = recover_krea2_metadata(png(Image.new("RGB", (8, 12)), pnginfo=info))
            self.assertEqual(metadata.firered_settings, settings)
            self.assertEqual(metadata.prompt, PROMPT)
        self.assertEqual(self.comfy.submitted, [])

    def test_http_defaults_routing_and_cross_engine_controls(self):
        runner = ChangeViewRunner(recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=self.comfy, assets=self.assets, runs=LocalRunStore(self.root))
        with TestClient(create_app(runner, krea2_edit=self.service)) as client:
            spec = client.get("/api/image-lab/krea2-edit/spec").json()
            self.assertEqual([w["engine"] for w in spec["workflows"]], ["krea2", "krea2", "firered"])
            endpoint = f"/api/image-lab/krea2-edit/sources/{self.source.source_id}/attempts"
            body = {"engine": "firered", "model_id": self.settings.model_name, "prompt": PROMPT,
                    "megapixels": 1, "seed": str(self.settings.seed), "workflow_version": "0.1.0"}
            for mode, steps, cfg in (("lightning", 8, 1), ("standard", 40, 4)):
                response = client.post(endpoint, json={**body, "mode": mode})
                self.assertEqual(response.status_code, 201, response.text)
                attempt = response.json()["source"]["attempts"][-1]
                self.assertEqual(attempt["workflow_id"], "firered.image_edit")
                self.assertEqual((attempt["settings"]["steps"], attempt["settings"]["cfg"]), (steps, cfg))
                self.assertIsNone(attempt["output_dimensions"])
            for bad in ({"ref_boost": 4}, {"loras": [{"name": "style", "strength": 1}]},
                        {"aspect_ratio": "1:1 (Square)"}, {"workflow_id": self.old.reference.recipe_id},
                        {"engine": "unknown"}, {"megapixels": 17}):
                response = client.post(endpoint, json={**body, **bad})
                self.assertEqual(response.status_code, 422, response.text)
            legacy = {"model_id": self.old.defaults["model_id"], "prompt": PROMPT,
                      "megapixels": 1, "seed": "42", "aspect_ratio": Krea2AspectRatio.SQUARE.value}
            response = client.post(endpoint, json=legacy)
            self.assertEqual(response.status_code, 201, response.text)
            saved = response.json()["source"]["attempts"][-1]
            self.assertEqual((saved["engine"], saved["workflow_version"]), ("krea2", "0.2.0"))
            self.assertEqual(client.post(endpoint, json={**legacy, "cfg": 4}).status_code, 422)
        self.assertEqual(len(self.store.get(self.source.source_id).attempts), 3)
        self.assertEqual(self.comfy.submitted, [])
        self.assertEqual(self.gateway.requests, [])

    def test_http_prompt_engine_reaches_the_profile_and_persisted_revision(self):
        runner = ChangeViewRunner(recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=self.comfy, assets=self.assets, runs=LocalRunStore(self.root))
        with TestClient(create_app(runner, krea2_edit=self.service)) as client:
            response = client.post(f"/api/image-lab/krea2-edit/sources/{self.source.source_id}/prompt/stream",
                json={"instruction": "Replace paint with soil", "model_id": "fake",
                      "render_engine": "firered", "assistance_version": "3.0.0"})
            self.assertEqual(response.status_code, 200, response.text)
        source = self.store.get(self.source.source_id)
        self.assertEqual(source.generated_prompt, PROMPT)
        self.assertEqual(source.revisions[-1].render_engine, "firered")
        self.assertEqual(self.gateway.requests[-1].operation_id, firered_edit_assistance.OPERATION)
        self.assertEqual(self.comfy.submitted, [])
