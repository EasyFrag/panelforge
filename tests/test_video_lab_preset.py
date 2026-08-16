from copy import deepcopy
from pathlib import Path
import unittest

from panelforge.domain import VideoAspectRatio, VideoLabSettings
from panelforge.infrastructure.presets import (
    VideoPresetValidationError,
    build_video_lab_workflow,
    load_video_lab_workflow,
    validate_video_lab_workflow,
)


PRESET_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.1.0"
)


class VideoLabPresetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.preset = load_video_lab_workflow(PRESET_DIRECTORY)
        self.settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio.WIDESCREEN,
            megapixels=0.8,
            duration_seconds=12.0,
            steps=40,
            seed=123,
        )

    def test_loads_neutral_versioned_workflow(self) -> None:
        workflow = self.preset.workflow
        self.assertEqual(self.preset.version, "0.1.0")
        self.assertEqual(workflow["138"]["inputs"]["value"], "PANELFORGE_PROMPT_REQUIRED")
        self.assertNotIn("149", workflow)
        self.assertNotIn("150", workflow)

    def test_compiles_one_image_and_prunes_unused_slots(self) -> None:
        workflow = build_video_lab_workflow(
            self.preset,
            source_images=("panelforge/one.png",),
            prompt="The subject turns toward the light.",
            settings=self.settings,
            output_filename_prefix="video/run-1",
        )

        self.assertEqual(workflow["137"]["inputs"]["image"], "panelforge/one.png")
        self.assertNotIn("139", workflow)
        self.assertNotIn("141", workflow)
        self.assertNotIn("ref_images.ref_image_1", workflow["136"]["inputs"])
        self.assertEqual(workflow["115"]["inputs"]["aspect_ratio"], "16:9 (Widescreen)")
        self.assertEqual(workflow["115"]["inputs"]["megapixels"], 0.8)
        self.assertEqual(workflow["132"]["inputs"]["value"], 12.0)
        self.assertEqual(workflow["124"]["inputs"]["steps"], 40)
        self.assertEqual(workflow["129"]["inputs"]["noise_seed"], 123)

    def test_compiles_three_images_in_picture_order(self) -> None:
        workflow = build_video_lab_workflow(
            self.preset,
            source_images=("one.png", "two.png", "three.png"),
            prompt="A restrained camera move.",
            settings=self.settings,
            output_filename_prefix="video/run-2",
        )
        self.assertEqual(workflow["137"]["inputs"]["image"], "one.png")
        self.assertEqual(workflow["139"]["inputs"]["image"], "two.png")
        self.assertEqual(workflow["141"]["inputs"]["image"], "three.png")

    def test_rejects_an_orphan_node(self) -> None:
        manifest = __import__("json").loads(
            (PRESET_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
        )
        workflow = deepcopy(self.preset.workflow)
        workflow["999"] = {"class_type": "PrimitiveString", "inputs": {"value": ""}}
        with self.assertRaisesRegex(VideoPresetValidationError, "orphan"):
            validate_video_lab_workflow(manifest, workflow)


if __name__ == "__main__":
    unittest.main()
