"""Local image and persistence scenarios. No real renderer, LLM or network."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps
from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner
from panelforge.application.krea2_edit import Krea2EditService, RetouchConflictError
from panelforge.domain.krea2_edit import Krea2EditAttempt, Krea2EditAttemptStatus as Status, Krea2EditMetadata, Krea2EditSettings
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.features.lab.web import create_app, serialize_krea2_edit_source
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.krea2_retouch import PillowRetouchCompositor
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset, load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore, LocalRunStore


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows/image.edit/krea2-identity/0.1.0"


def png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def decoded(content):
    with Image.open(BytesIO(content)) as image:
        return image.convert("RGBA")


class NoExternal:
    def __getattr__(self, name):
        raise AssertionError(f"External call forbidden in retouch: {name}")


class CompositorTest(unittest.TestCase):
    def setUp(self):
        self.compositor = PillowRetouchCompositor()
        self.source_image = Image.new("RGBA", (8, 12), (23, 67, 109, 255))
        self.generated_image = Image.new("RGBA", (16, 24), (211, 177, 41, 255))
        self.source = png(self.source_image)
        self.generated = png(self.generated_image)

    def test_empty_and_full_masks_preserve_originals_and_source_size(self):
        prepared = self.compositor.prepare(self.source, self.generated)
        self.assertEqual((prepared.width, prepared.height), (8, 12))
        for level, expected in ((0, self.source_image), (255, decoded(prepared.generated_png))):
            with self.subTest(level=level):
                result = self.compositor.compose(self.source, self.generated, png(Image.new("L", (8, 12), level)))
                self.assertEqual(decoded(result.output_png).size, (8, 12))
                self.assertEqual(decoded(result.output_png).tobytes(), expected.tobytes())

    def test_partial_mask_keeps_unpainted_pixels_and_blends_soft_edge(self):
        mask = Image.new("L", (8, 12), 0)
        mask.putpixel((3, 4), 255)
        mask.putpixel((4, 4), 128)
        result = self.compositor.compose(self.source, self.generated, png(mask))
        image = decoded(result.output_png)
        self.assertEqual(image.getpixel((3, 4)), (211, 177, 41, 255))
        self.assertEqual(image.getpixel((4, 4)), (117, 122, 75, 255))
        for row in range(12):
            for col in range(8):
                if (col, row) not in {(3, 4), (4, 4)}:
                    self.assertEqual(image.getpixel((col, row)), self.source_image.getpixel((col, row)))

    def test_browser_alpha_mask_is_saved_as_grayscale(self):
        mask = Image.new("RGBA", (8, 12), (255, 255, 255, 0))
        mask.putpixel((1, 2), (255, 255, 255, 255))
        result = self.compositor.compose(self.source, self.generated, png(mask))
        with Image.open(BytesIO(result.mask_png)) as saved:
            self.assertEqual(saved.mode, "L")
            self.assertEqual(saved.getpixel((0, 0)), 0)
            self.assertEqual(saved.getpixel((1, 2)), 255)

    def test_harmonization_moves_color_toward_source_and_matches_preview_interpolation(self):
        prepared = self.compositor.prepare(self.source, self.generated)
        corrected, original = decoded(prepared.harmonized_png), decoded(prepared.generated_png)
        self.assertEqual(corrected.size, self.source_image.size)
        distance = lambda image: sum(abs(a - b) for a, b in zip(image.getpixel((0, 0))[:3], self.source_image.getpixel((0, 0))[:3]))
        self.assertLess(distance(corrected), distance(original) / 4)
        mask = Image.new("L", (8, 12), 0)
        mask.putpixel((3, 4), 255)
        mask.putpixel((4, 4), 128)
        for strength in (0, 1, 50, 100):
            with self.subTest(strength=strength):
                result = decoded(self.compositor.compose(self.source, self.generated, png(mask),
                    harmonize=True, harmonize_strength=strength).output_png)
                level = (strength * 255 + 50) // 100
                for row in range(12):
                    for col in range(8):
                        m = mask.getpixel((col, row))
                        target, fixed = original.getpixel((col, row)), corrected.getpixel((col, row))
                        source = self.source_image.getpixel((col, row))
                        mixed = [(c * level + g * (255 - level) + 127) // 255 for c, g in zip(fixed, target)]
                        expected = tuple((g * m + s * (255 - m) + 127) // 255 for g, s in zip(mixed, source))
                        self.assertEqual(result.getpixel((col, row)), expected)

    def test_harmonization_preserves_protected_rgba_and_generated_alpha(self):
        source = self.source_image.copy()
        source.putpixel((0, 0), (3, 66, 110, 0))
        generated = self.source_image.copy()
        generated.putpixel((4, 4), (220, 110, 22, 99))
        mask = Image.new("L", source.size)
        mask.putpixel((4, 4), 255)
        result = decoded(self.compositor.compose(png(source), png(generated), png(mask), harmonize=True).output_png)
        self.assertEqual(result.getpixel((0, 0)), source.getpixel((0, 0)))
        self.assertEqual(result.getpixel((4, 4))[3], 99)
        for enabled, strength in ((True, -1), (True, 101), (True, 1.5), (True, True), ("false", 50)):
            with self.assertRaises(ValueError):
                self.compositor.compose(self.source, self.generated, png(mask), harmonize=enabled, harmonize_strength=strength)

    def test_orientation_is_applied_before_geometry_and_composition(self):
        exif = Image.Exif()
        exif[274] = 6
        buffer = BytesIO()
        patterned = self.source_image.convert("RGB")
        patterned.paste("red", (0, 0, 3, 5))
        patterned.save(buffer, format="JPEG", exif=exif)
        source = buffer.getvalue()
        with Image.open(BytesIO(source)) as raw:
            expected = ImageOps.exif_transpose(raw).convert("RGBA")
        result = self.compositor.compose(source, png(Image.new("RGB", (24, 16))), png(Image.new("L", (12, 8))))
        self.assertEqual(decoded(result.output_png).tobytes(), expected.tobytes())
        self.assertEqual((result.width, result.height), (12, 8))

    def test_generated_orientation_and_protected_alpha_pixels(self):
        source = self.source_image.copy()
        source.putpixel((0, 0), (1, 53, 211, 0))
        source.putpixel((1, 0), (121, 33, 1, 99))
        generated = self.generated_image.transpose(Image.Transpose.ROTATE_90)
        generated.putpixel((0, 0), (240, 10, 90, 150))
        exif = Image.Exif()
        exif[274] = 6
        buffer = BytesIO()
        generated.save(buffer, format="PNG", exif=exif)
        result = self.compositor.compose(png(source), buffer.getvalue(), png(Image.new("L", (8, 12))))
        self.assertEqual(decoded(result.output_png).tobytes(), source.tobytes())
        prepared = self.compositor.prepare(png(source), buffer.getvalue())
        expected = generated.transpose(Image.Transpose.ROTATE_270).resize(source.size, Image.Resampling.LANCZOS)
        self.assertEqual(decoded(prepared.generated_png).tobytes(), expected.tobytes())

    def test_small_ratio_rounding_allowed_but_wrong_ratio_or_mask_rejected(self):
        source = png(Image.new("RGB", (100, 100)))
        self.compositor.prepare(source, png(Image.new("RGB", (101, 100))))
        for generated in (png(Image.new("RGB", (102, 100))), b"not an image"):
            with self.assertRaises(ValueError):
                self.compositor.prepare(source, generated)
        for mask in (b"not png", png(Image.new("L", (1, 1))), png(Image.new("RGB", (8, 12)))):
            with self.assertRaises(ValueError):
                self.compositor.compose(self.source, self.generated, mask)


class RetouchServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = LocalAssetStore(self.root)
        self.store = LocalKrea2EditStore(self.root)
        self.source_bytes = png(Image.new("RGB", (8, 12), "navy"))
        self.generated_bytes = png(Image.new("RGB", (16, 24), "gold"))
        source_asset = self.assets.create(self.source_bytes, media_type="image/png")
        output = self.assets.create(self.generated_bytes, media_type="image/png")
        self.service = Krea2EditService(gateway=NoExternal(), comfy=NoExternal(),
            workflow=load_krea2_edit_workflow(WORKFLOW), assets=self.assets, sources=self.store,
            retouch_compositor=PillowRetouchCompositor(), project_exporter=LocalKrea2ProjectExporter(self.root / "exports"))
        self.source = self.service.add_source(asset_id=source_asset.asset_id, filename="wall.png", metadata=Krea2EditMetadata())
        self.original = Krea2EditAttempt(attempt_id="original", prompt="A realistic wall with a small opening in natural daylight.",
            settings=Krea2EditSettings(model_name="model", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN, megapixels=1, seed=0),
            status=Status.SUCCEEDED, execution_id="existing-execution", compiled_workflow_sha256="a" * 64, output_asset_id=output.asset_id)
        self.source = self.store.save(replace(self.source, attempts=(self.original,), generated_prompt="CURRENT EDITOR PROMPT"))
        self.mask = png(Image.new("L", (8, 12), 128))

    def tearDown(self):
        self.temp.cleanup()

    def save(self, request_id="first", parent="original", mask=None, **options):
        return self.service.save_retouch(self.source.source_id, parent, self.mask if mask is None else mask,
                                         request_id=request_id, **options)

    def test_color_settings_persist_reopen_without_accumulation_and_participate_in_idempotence(self):
        source, first = self.save(harmonize=True, harmonize_strength=50)
        self.assertEqual(self.save(harmonize=True, harmonize_strength=50), (source, first))
        for options in ({"harmonize": False, "harmonize_strength": 50}, {"harmonize": True, "harmonize_strength": 80}):
            with self.assertRaises(RetouchConflictError):
                self.save(**options)
        prepared = self.service.prepare_retouch(source.source_id, first.attempt_id)
        self.assertTrue(prepared["harmonize"])
        self.assertEqual(prepared["harmonize_strength"], 50)
        self.assertEqual(decoded(prepared["generated_png"]).getpixel((0, 0)), (255, 215, 0, 255))
        _, second = self.save("again", parent=first.attempt_id, harmonize=True, harmonize_strength=50)
        self.assertEqual(self.assets.read_bytes(first.output_asset_id), self.assets.read_bytes(second.output_asset_id))
        stored = LocalKrea2EditStore(self.root).get(source.source_id)
        self.assertEqual(stored.attempts[-1].retouch.harmonize_strength, 50)
        path = self.root / "krea2_edits" / source.source_id / "source.json"
        legacy = json.loads(path.read_text(encoding="utf-8"))
        for attempt in legacy["attempts"][1:]:
            for key in ("harmonize", "harmonize_strength", "color_method"):
                attempt["retouch"].pop(key)
        path.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertFalse(self.store.get(source.source_id).attempts[-1].retouch.harmonize)

    def test_save_is_distinct_preserves_editor_and_is_idempotent(self):
        source, attempt = self.save()
        self.assertEqual(len(source.attempts), 2)
        self.assertEqual(source.attempts[0], self.original)
        self.assertEqual(source.generated_prompt, "CURRENT EDITOR PROMPT")
        self.assertEqual(source.attempt_label(attempt.attempt_id), "Essai 1 — Retouche 1")
        self.assertEqual(attempt.kind, "retouch")
        self.assertEqual(attempt.settings.seed, 0)
        self.assertIsNone(attempt.execution_id)
        self.assertIsNone(attempt.compiled_workflow_sha256)
        self.assertEqual(self.save(), (source, attempt))
        self.assertEqual(self.assets.read_bytes(self.original.output_asset_id), self.generated_bytes)
        self.assertEqual(self.assets.read_bytes(source.source_asset_id), self.source_bytes)
        self.assertEqual(LocalKrea2EditStore(self.root).get(source.source_id), source)
        with self.assertRaises(RetouchConflictError):
            self.save(mask=png(Image.new("L", (8, 12), 0)))

    def test_retouch_and_export_keep_the_generation_workflow_even_in_an_old_stage(self):
        imported = load_krea2_edit_workflow(WORKFLOW.parent / "0.2.0")
        self.original = replace(self.original, recipe=imported.reference)
        self.source = self.store.save(replace(self.source, attempts=(self.original,)))
        source, candidate = self.save()
        self.assertNotEqual(source.recipe, candidate.recipe)
        self.assertEqual(candidate.recipe, imported.reference)
        _, resumed = self.save("resumed", parent=candidate.attempt_id)
        self.assertEqual(resumed.recipe, imported.reference)
        child = self.service.promote_attempt(source.source_id, candidate.attempt_id)
        self.assertEqual(child.recipe, imported.reference)
        project_path = Path(child.export_path) / "project.json"
        entry = json.loads(project_path.read_text(encoding="utf-8"))["accepted_chain"][0]
        sidecar = json.loads((project_path.parent / entry["sidecar"]).read_text(encoding="utf-8"))
        self.assertEqual(sidecar["workflow"]["version"], "0.2.0")
        self.assertEqual(sidecar["workflow"]["sha256"], imported.reference.workflow_sha256)

    def test_reopen_uses_original_generation_and_same_mask_not_previous_composite(self):
        source, first = self.save()
        prepared = self.service.prepare_retouch(source.source_id, first.attempt_id)
        self.assertEqual(decoded(prepared["generated_png"]).getpixel((0, 0)), (255, 215, 0, 255))
        self.assertEqual(prepared["mask_png"], self.assets.read_bytes(first.retouch.mask_asset_id))
        source, second = self.save("second", first.attempt_id)
        self.assertEqual(second.retouch.original_attempt_id, self.original.attempt_id)
        self.assertEqual(self.assets.read_bytes(second.output_asset_id), self.assets.read_bytes(first.output_asset_id))
        self.assertEqual(source.attempt_label(second.attempt_id), "Essai 1 — Retouche 2")
        next_generation = replace(self.original, attempt_id="next-generation")
        source = replace(source, attempts=(*source.attempts, next_generation))
        self.assertEqual(source.attempt_label(next_generation.attempt_id), "Essai 2")

    def test_bad_mask_is_atomic_and_retouch_cannot_enter_gpu_queue(self):
        with self.assertRaises(ValueError):
            self.save(mask=b"invalid png")
        self.assertEqual(self.store.get(self.source.source_id), self.source)
        source, candidate = self.save()
        with self.assertRaises(ValueError):
            self.service.queue_attempt(source.source_id, candidate.attempt_id)
        self.assertEqual(self.service.execute_attempt(source.source_id, candidate.attempt_id), source)

    def test_concurrent_retry_creates_one_candidate(self):
        barrier = Barrier(2)
        compositor = self.service.retouch_compositor
        class ConcurrentCompositor:
            def compose(inner, *args, **kwargs):
                result = compositor.compose(*args, **kwargs)
                barrier.wait(timeout=5)
                return result
        self.service.retouch_compositor = ConcurrentCompositor()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.save(), range(2)))
        self.assertEqual(results[0][1].attempt_id, results[1][1].attempt_id)
        self.assertEqual(len(self.store.get(self.source.source_id).attempts), 2)

    def test_stage_validation_during_composition_rejects_stale_save(self):
        compositor = self.service.retouch_compositor
        class AdvancingCompositor:
            def compose(inner, *args, **kwargs):
                result = compositor.compose(*args, **kwargs)
                self.service.promote_attempt(self.source.source_id, self.original.attempt_id,
                                             project_name="Wall", step_name="Opening")
                return result
        self.service.retouch_compositor = AdvancingCompositor()
        with self.assertRaises(RetouchConflictError):
            self.save()
        stored = self.store.get(self.source.source_id)
        self.assertEqual(len(stored.attempts), 1)
        self.assertEqual(stored.accepted_attempt_id, self.original.attempt_id)

    def test_domain_rejects_forged_provenance_or_gpu_identity(self):
        source, candidate = self.save()
        for kwargs in ({"execution_id": "gpu"}, {"status": Status.QUEUED}, {"kind": "generation"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(candidate, **kwargs)
        for kwargs in ({"source_asset_id": "another-source"}, {"original_attempt_id": "another-stage"},
                       {"generated_asset_id": candidate.output_asset_id}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                forged = replace(candidate, retouch=replace(candidate.retouch, **kwargs))
                replace(source, attempts=(self.original, forged))

    def test_feedback_promotion_and_export_use_composite_and_freeze_stage(self):
        from tests.test_krea2_edit import FakeGateway
        source, candidate = self.save(harmonize=True, harmonize_strength=50)
        source, newer = self.save("newer", mask=png(Image.new("L", (8, 12))))
        self.assertNotEqual(self.assets.read_bytes(newer.output_asset_id), self.assets.read_bytes(candidate.output_asset_id))
        self.service.gateway = FakeGateway(self.original.prompt)
        list(self.service.stream_prepare_prompt(source.source_id, "Refine the opening", "fake", feedback_attempt_id=candidate.attempt_id))
        images = self.service.gateway.requests[-1].images
        self.assertEqual(images[1].content, self.assets.read_bytes(candidate.output_asset_id))
        child = self.service.promote_attempt(source.source_id, candidate.attempt_id, project_name="Wall", step_name="Opening")
        self.assertEqual(child.source_asset_id, candidate.output_asset_id)
        self.assertEqual(child.metadata.origin, "retouch")
        manifest_path = Path(child.export_path) / "project.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = manifest["accepted_chain"][0]
        self.assertEqual((manifest_path.parent / entry["image"]).read_bytes(), self.assets.read_bytes(candidate.output_asset_id))
        self.assertEqual(entry["kind"], "retouch")
        for key, expected in (("mask_file", self.assets.read_bytes(candidate.retouch.mask_asset_id)),
                              ("source_file", self.source_bytes), ("generated_file", self.generated_bytes)):
            self.assertEqual((manifest_path.parent / entry["retouch_files"][key]).read_bytes(), expected)
        sidecar = json.loads((manifest_path.parent / entry["sidecar"]).read_text(encoding="utf-8"))
        self.assertEqual(sidecar["operation"], "image.compose.mask@1.0.0")
        self.assertEqual(sidecar["composition"]["width"], 8)
        self.assertTrue(sidecar["composition"]["render_settings_are_inherited"])
        self.assertTrue(sidecar["composition"]["harmonize"])
        self.assertEqual(sidecar["composition"]["harmonize_strength"], 50)
        self.assertEqual(sidecar["composition"]["color_method"], "reinhard_lab_rgb@1.0.0")
        advanced = self.store.get(source.source_id)
        serialized = serialize_krea2_edit_source(advanced)
        selected = next(value for value in serialized["attempts"] if value["attempt_id"] == candidate.attempt_id)
        self.assertEqual(selected["output_asset_id"], child.source_asset_id)
        self.assertTrue(selected["accepted"])
        self.assertFalse(self.service.prepare_retouch(source.source_id, candidate.attempt_id)["editable"])
        with self.assertRaises(RetouchConflictError):
            self.save("late", candidate.attempt_id)
        self.assertEqual(self.save(harmonize=True, harmonize_strength=50)[1].attempt_id, candidate.attempt_id)

    def test_legacy_schemas_are_read_as_generations(self):
        path = self.root / "krea2_edits" / self.source.source_id / "source.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 11)
        for version in (1, 2, 3, 4, 5):
            with self.subTest(version=version):
                data["schema_version"] = version
                data.pop("restart_count", None)
                data["attempts"][0].pop("kind", None)
                data["attempts"][0].pop("retouch", None)
                path.write_text(json.dumps(data), encoding="utf-8")
                loaded = self.store.get(self.source.source_id)
                self.assertEqual(loaded.attempts[0].kind, "generation")
                self.assertIsNone(loaded.attempts[0].retouch)
                self.assertEqual(loaded.restart_count, 0)

    def test_restart_removes_stage_memory_and_attempts_and_archives_the_old_state(self):
        from tests.test_krea2_edit import FakeGateway
        source, retouch = self.save()
        self.service.gateway = FakeGateway(json.dumps({"message": "OLD_DOOR_DIRECTION", "prompt": self.original.prompt}))
        list(self.service.stream_prepare_prompt(source.source_id, "OLD_DOOR_DIRECTION", "fake",
            feedback_attempt_id=retouch.attempt_id, assistance_version="2.0.0"))
        restarted = self.service.restart_stage(source.source_id, expected_restart_count=0)
        self.assertEqual((restarted.source_asset_id, restarted.project_id, restarted.stage_index),
                         (source.source_asset_id, source.project_id, source.stage_index))
        self.assertEqual(restarted.metadata, source.metadata)
        self.assertEqual(restarted.restart_count, 1)
        self.assertEqual(restarted.attempts, ())
        self.assertEqual(restarted.revisions, ())
        self.assertEqual(restarted.instruction, "")
        self.assertEqual(restarted.prompt_status.value, "idle")
        for name in ("generated_prompt", "raw_prompt_response", "prompt_model_id", "prompt_error"):
            self.assertIsNone(getattr(restarted, name))
        archive = self.root / "krea2_edits" / source.source_id / "restarts" / "before-1.json"
        archived = json.loads(archive.read_text(encoding="utf-8"))
        self.assertEqual(archived["revisions"][0]["instruction"], "OLD_DOOR_DIRECTION")
        self.assertEqual(len(archived["attempts"]), 2)
        self.assertEqual(len(self.store.list()), 1)
        self.service.gateway = FakeGateway(json.dumps({"message": "New start", "prompt": self.original.prompt}))
        list(self.service.stream_prepare_prompt(source.source_id, "NEW_DIRECTION", "fake", assistance_version="2.0.0"))
        request = self.service.gateway.requests[-1]
        self.assertNotIn("OLD_DOOR_DIRECTION", request.user_prompt)
        self.assertIn("[]", request.user_prompt)
        self.assertEqual(len(request.images), 1)
        current = self.store.get(source.source_id)
        self.assertEqual(self.service.restart_stage(source.source_id, expected_restart_count=0), current)
        self.assertEqual(len(current.revisions), 1, "retry must not erase new work")
        self.assertEqual(self.service.restart_stage(source.source_id, expected_restart_count=1).restart_count, 2)

    def test_restart_rejects_busy_or_validated_stages_and_preserves_parent(self):
        source_id = self.source.source_id
        self.store.save(self.source.begin_prompt("Busy", "fake"))
        with self.assertRaises(RetouchConflictError):
            self.service.restart_stage(source_id, expected_restart_count=0)
        for status in (Status.QUEUED, Status.RUNNING, Status.CANCEL_PENDING):
            active = replace(self.original, status=status, output_asset_id=None,
                execution_id=None if status is Status.QUEUED else "gpu",
                error="cancel pending" if status is Status.CANCEL_PENDING else None,
                compiled_workflow_sha256=None if status is Status.QUEUED else "a" * 64)
            self.store.save(replace(self.source, attempts=(active,)))
            with self.assertRaises(RetouchConflictError):
                self.service.restart_stage(source_id, expected_restart_count=0)
        self.store.save(self.source)
        child = self.service.promote_attempt(source_id, self.original.attempt_id, project_name="Wall", step_name="Door")
        parent = self.store.get(source_id)
        with self.assertRaises(RetouchConflictError):
            self.service.restart_stage(source_id, expected_restart_count=0)
        restarted = self.service.restart_stage(child.source_id, expected_restart_count=0)
        self.assertEqual(self.store.get(source_id), parent)
        self.assertEqual((restarted.stage_index, restarted.parent_source_id, restarted.source_asset_id),
                         (child.stage_index, child.parent_source_id, child.source_asset_id))

    def test_restart_storage_failure_preserves_state_and_concurrent_retouch_is_rejected(self):
        with patch("panelforge.infrastructure.storage.krea2_edits._atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.service.restart_stage(self.source.source_id, expected_restart_count=0)
        self.assertEqual(self.store.get(self.source.source_id), self.source)
        compositor = self.service.retouch_compositor
        class RestartingCompositor:
            def compose(inner, *args, **kwargs):
                result = compositor.compose(*args, **kwargs)
                self.service.restart_stage(self.source.source_id, expected_restart_count=0)
                return result
        self.service.retouch_compositor = RestartingCompositor()
        with self.assertRaises(RetouchConflictError):
            self.save()
        self.assertEqual(self.store.get(self.source.source_id).attempts, ())

    def test_http_prepare_save_retry_and_validation(self):
        runner = ChangeViewRunner(recipe=ChangeViewPresetRecipe(load_change_view_preset(
            ROOT / "workflows/character.change_view/qwen-edit-2511-multiple-angles/0.2.0")),
            comfy=NoExternal(), assets=self.assets, runs=LocalRunStore(self.root))
        with TestClient(create_app(runner, krea2_edit=self.service)) as client:
            url = f"/api/image-lab/krea2-edit/sources/{self.source.source_id}/attempts/original/retouch"
            prepared = client.get(url)
            self.assertEqual(prepared.status_code, 200, prepared.text)
            self.assertEqual(decoded(base64.b64decode(prepared.json()["source_url"].split(",", 1)[1])).size, (8, 12))
            send = lambda mask, key: client.post(url, files={"mask": ("mask.png", mask, "image/png")}, data={"request_id": key})
            saved = send(self.mask, "http-save")
            self.assertEqual(saved.status_code, 201, saved.text)
            self.assertEqual(send(self.mask, "http-save").json()["attempt_id"], saved.json()["attempt_id"])
            self.assertEqual(send(png(Image.new("L", (8, 12))), "http-save").status_code, 409)
            self.assertEqual(send(b"bad mask", "bad").status_code, 422)
            self.assertEqual(send(self.mask, "../bad").status_code, 422)
            self.assertTrue(prepared.json()["harmonized_url"].startswith("data:image/png;base64,"))
            for value in ("-1", "101", "1.2", "bad"):
                response = client.post(url, files={"mask": ("mask.png", self.mask, "image/png")},
                    data={"request_id": "bad-color", "harmonize": "true", "harmonize_strength": value})
                self.assertEqual(response.status_code, 422, response.text)
            form = {"request_id": "color", "harmonize": "true", "harmonize_strength": "50"}
            files = {"mask": ("mask.png", self.mask, "image/png")}
            colored = client.post(url, files=files, data=form)
            self.assertEqual(colored.status_code, 201, colored.text)
            self.assertEqual(client.post(url, files=files, data=form).json()["attempt_id"], colored.json()["attempt_id"])
            self.assertEqual(client.post(url, files=files, data={**form, "harmonize_strength": "70"}).status_code, 409)
            restart_url = f"/api/image-lab/krea2-edit/sources/{self.source.source_id}/restart"
            self.assertEqual(client.post(restart_url, json={"expected_restart_count": -1}).status_code, 422)
            self.assertEqual(client.post(restart_url, json={"expected_restart_count": 99}).status_code, 409)
            reset = client.post(restart_url, json={"expected_restart_count": 0})
            self.assertEqual(reset.status_code, 200, reset.text)
            self.assertEqual(reset.json()["source"]["restart_count"], 1)
            self.assertEqual(reset.json()["source"]["attempts"], [])
            self.assertEqual(client.post(restart_url, json={"expected_restart_count": 0}).json(), reset.json())
