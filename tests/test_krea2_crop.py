"""Local crop stages: native pixels, clean next prompt and retry-safe history."""

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

from panelforge.application.krea2_edit import Krea2EditService, RetouchConflictError
from panelforge.domain.krea2_edit import Krea2EditCrop, Krea2EditMetadata, Krea2EditPromptStatus
from panelforge.features.lab.web import serialize_krea2_edit_source
from panelforge.infrastructure.edit_images import PillowEditImages
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore
from tests.test_krea2_edit import WORKFLOW


class NoExternal:
    def __getattr__(self, name):
        raise AssertionError(f"Crop must not use a model or renderer: {name}")


def png(image, **kwargs):
    output = BytesIO()
    image.save(output, format="PNG", **kwargs)
    return output.getvalue()


class Krea2CropTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = LocalAssetStore(self.root)
        self.store = LocalKrea2EditStore(self.root)
        self.image = Image.new("RGBA", (13, 9))
        self.image.putdata([(x * 17, y * 27, x + y, (x * 19 + y) % 256) for y in range(9) for x in range(13)])
        self.content = png(self.image)
        asset = self.assets.create(self.content, media_type="image/png")
        self.service = Krea2EditService(
            gateway=NoExternal(), comfy=NoExternal(),
            workflow=load_krea2_edit_workflow(WORKFLOW), assets=self.assets, sources=self.store,
            edit_images=PillowEditImages(), project_exporter=LocalKrea2ProjectExporter(self.root / "exports"),
        )
        self.source = self.service.add_source(asset_id=asset.asset_id, filename="landscape.png",
            metadata=Krea2EditMetadata(prompt="A garden and a tree beyond the selected rectangle.", seed=42))
        self.crop = Krea2EditCrop("crop-1", asset.asset_id, 0, 13, 9, 2, 1, 7, 5)

    def test_crop_preserves_pixels_history_and_clears_next_prompt(self):
        child = self.service.crop_source(self.source.source_id, self.crop, project_name="Garden")
        parent = self.store.get(self.source.source_id)
        self.assertEqual(parent.source_asset_id, self.source.source_asset_id)
        self.assertEqual(self.assets.read_bytes(parent.source_asset_id), self.content)
        self.assertEqual(parent.state.value, "advanced")
        self.assertEqual(parent.accepted_label, "Recadrage")
        attempt = parent.attempts[-1]
        self.assertEqual(parent.accepted_attempt_id, attempt.attempt_id)
        self.assertEqual(attempt.kind, "crop")
        self.assertIsNone(attempt.execution_id)
        self.assertEqual(attempt.crop, self.crop)
        self.assertEqual(child.source_asset_id, attempt.output_asset_id)
        self.assertEqual(child.parent_attempt_id, attempt.attempt_id)
        self.assertEqual(child.stage_index, 2)
        self.assertEqual(child.metadata.origin, "crop")
        self.assertEqual(child.metadata.seed, 42)
        self.assertIsNone(child.metadata.prompt)
        self.assertIsNone(child.generated_prompt)
        self.assertEqual(child.prompt_status, Krea2EditPromptStatus.IDLE)
        self.assertEqual(child.revisions, ())
        with Image.open(BytesIO(self.assets.read_bytes(child.source_asset_id))) as result:
            self.assertEqual(result.size, (7, 5))
            self.assertEqual(result.tobytes(), self.image.crop((2, 1, 9, 6)).tobytes())
        self.assertEqual(LocalKrea2EditStore(self.root).get(parent.source_id), parent)
        self.assertEqual(serialize_krea2_edit_source(parent)["attempts"][0]["output_dimensions"], {"width": 7, "height": 5})
        self.assertIsNone(child.export_error)
        records = [json.loads(f.read_text(encoding="utf-8")) for f in (self.root / "exports").rglob("*.json")]
        self.assertTrue(any(r.get("operation") == "image.crop@1.0.0" and r.get("crop", {}).get("width") == 7 for r in records))

    def test_same_request_returns_same_stage_and_conflicting_rectangle_is_rejected(self):
        first = self.service.crop_source(self.source.source_id, self.crop)
        again = self.service.crop_source(self.source.source_id, self.crop)
        self.assertEqual(first, again)
        self.assertEqual(len(self.service.project_stages(first.project_id)), 2)
        self.assertEqual(len(self.store.get(self.source.source_id).attempts), 1)
        with self.assertRaises(RetouchConflictError):
            self.service.crop_source(self.source.source_id, replace(self.crop, width=6))

    def test_retry_after_failed_child_creation_reuses_the_saved_crop(self):
        with patch.object(self.store, "create", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.service.crop_source(self.source.source_id, self.crop)
        pending = self.store.get(self.source.source_id)
        self.assertEqual(pending.state.value, "pending")
        self.assertEqual(len(pending.attempts), 1)
        child = self.service.crop_source(self.source.source_id, self.crop)
        self.assertEqual(child.source_asset_id, pending.attempts[0].output_asset_id)
        self.assertEqual(len(self.service.project_stages(child.project_id)), 2)

    def test_changed_source_dimensions_restart_and_busy_stage_do_not_mutate_history(self):
        for changes in ({"source_asset_id": "another-asset"}, {"source_width": 14}, {"restart_count": 1}):
            with self.subTest(changes=changes), self.assertRaises(RetouchConflictError):
                self.service.crop_source(self.source.source_id, replace(self.crop, **changes))
        busy = self.store.save(replace(self.source, prompt_status=Krea2EditPromptStatus.GENERATING,
                                      prompt_model_id="fake", instruction="Change light"))
        with self.assertRaises(RetouchConflictError):
            self.service.crop_source(self.source.source_id, self.crop)
        self.assertEqual(self.store.get(self.source.source_id), busy)
        self.assertEqual(len(list((self.root / "assets").iterdir())), 1)

    def test_rectangles_are_bounded_and_exif_orientation_matches_the_preview(self):
        for changes in ({"x": -1}, {"width": 0}, {"width": 12}, {"x": True}, {"height": 2.5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.crop, **changes)
        exif = Image.Exif()
        exif[274] = 6
        oriented = png(self.image, exif=exif)
        adapter = PillowEditImages()
        self.assertEqual(adapter.dimensions(oriented), (9, 13))
        cropped = adapter.crop(oriented, x=1, y=2, width=4, height=6)
        with Image.open(BytesIO(oriented)) as original, Image.open(BytesIO(cropped)) as actual:
            expected = ImageOps.exif_transpose(original).convert("RGBA").crop((1, 2, 5, 8))
            self.assertEqual(actual.tobytes(), expected.tobytes())
            self.assertEqual(actual.size, (4, 6))
        with self.assertRaises(ValueError):
            adapter.crop(self.content, x=12, y=0, width=2, height=1)
