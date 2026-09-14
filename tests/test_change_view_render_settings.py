import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panelforge.application import ChangeViewRunRequest, ChangeViewRunner
from panelforge.domain.change_view_settings import ChangeViewRenderSettings
from panelforge.domain.character import CameraAzimuth, CameraElevation, ChangeView, ShotSize
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe, PresetValidationError, build_change_view_workflow,
    load_change_view_preset, validate_change_view_preset,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalRunStore
from test_execute_change_view import FakeComfy

PRESETS = ROOT / "workflows/character.change_view/qwen-edit-2511-multiple-angles"


class ChangeViewRenderSettingsTest(unittest.TestCase):
    def setUp(self):
        self.preset = load_change_view_preset(PRESETS / "0.3.0")
        self.change = ChangeView("source", CameraAzimuth.BACK, CameraElevation.LOW, ShotSize.WIDE)

    def build(self, settings=None, preset=None):
        return build_change_view_workflow(
            self.change, preset or self.preset, source_image="input.png", seed=42,
            multiple_angles_lora_strength=1.0, render_settings=settings,
        )

    def test_defaults_keep_the_exact_previous_workflow(self):
        previous = load_change_view_preset(PRESETS / "0.2.0")
        self.assertEqual(self.build(), self.build(preset=previous))
        self.assertEqual(self.build(ChangeViewRenderSettings()), self.build(preset=previous))

    def test_steps_alone_do_not_change_sizing_or_other_sampler_settings(self):
        expected = self.build()
        binding = self.preset.render_bindings["steps"]
        expected[binding.node_id]["inputs"][binding.input_name] = 12
        self.assertEqual(self.build(ChangeViewRenderSettings(steps=12)), expected)
        self.assertEqual(self.build(), self.build(preset=load_change_view_preset(PRESETS / "0.2.0")))

    def test_megapixels_preserve_source_ratio_and_all_image_consumers(self):
        before = self.build()
        after = self.build(ChangeViewRenderSettings(megapixels=2))
        binding = self.preset.render_bindings["image_size"]
        expected = copy.deepcopy(before)
        expected[binding.node_id].update(class_type="ImageScaleToTotalPixels", inputs={
            "image": before[binding.node_id]["inputs"][binding.input_name],
            "megapixels": 2, "resolution_steps": 32, "upscale_method": "lanczos",
        })
        self.assertEqual(after, expected)

    def test_forced_format_uses_a_crop_not_a_stretch(self):
        binding = self.preset.render_bindings["image_size"]
        settings = ChangeViewRenderSettings(megapixels=1.048576, aspect_ratio="1:1")
        node = self.build(settings)[binding.node_id]
        self.assertEqual(node["class_type"], "ImageScale")
        self.assertEqual(node["inputs"]["crop"], "center")
        self.assertEqual((node["inputs"]["width"], node["inputs"]["height"]), (1024, 1024))
        auto = ChangeViewRenderSettings(aspect_ratio="9:16").fixed_dimensions()
        self.assertGreater(auto[1], auto[0])
        self.assertTrue(all(value % 32 == 0 for value in auto))

    def test_rejects_invalid_controls_and_overrides_on_archived_recipe(self):
        for kwargs in ({"steps": True}, {"steps": 8.5}, {"steps": 0}, {"steps": 51},
                       {"megapixels": float("nan")}, {"megapixels": float("inf")},
                       {"megapixels": False}, {"megapixels": 0}, {"megapixels": 4.1},
                       {"aspect_ratio": "invalid"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ChangeViewRenderSettings(**kwargs)
        with self.assertRaises(ValueError):
            self.build(ChangeViewRenderSettings(steps=12), load_change_view_preset(PRESETS / "0.2.0"))

    def test_render_bindings_are_validated_at_load(self):
        manifest = json.loads((PRESETS / "0.3.0/manifest.json").read_text(encoding="utf-8"))
        manifest["render_bindings"]["steps"]["node_id"] = self.preset.bindings["output_image"].node_id
        with self.assertRaises(PresetValidationError):
            validate_change_view_preset(manifest, self.preset.workflow, self.preset.prompt_template)

    def test_saved_settings_survive_reopening_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = LocalAssetStore(directory)
            source = assets.create(b"source", media_type="image/png")
            recipe = ChangeViewPresetRecipe(self.preset)
            runner = ChangeViewRunner(recipe=recipe, assets=assets, runs=LocalRunStore(directory), comfy=FakeComfy())
            run = runner.prepare(ChangeViewRunRequest(
                source_asset_id=source.asset_id, azimuth=self.change.azimuth,
                elevation=self.change.elevation, shot_size=self.change.shot_size,
                lora_strength=1.0, seed=42,
                render_settings=ChangeViewRenderSettings(steps=12, megapixels=2, aspect_ratio="16:9"),
            ))
            comfy = FakeComfy()
            reopened = ChangeViewRunner(recipe=recipe, assets=assets, runs=LocalRunStore(directory), comfy=comfy)
            self.assertEqual(reopened.execute(run.run_id).status.value, "succeeded")
            step_node = self.preset.render_bindings["steps"].node_id
            image_node = self.preset.render_bindings["image_size"].node_id
            self.assertEqual(comfy.submitted_workflow[step_node]["inputs"]["steps"], 12)
            image_inputs = comfy.submitted_workflow[image_node]["inputs"]
            self.assertGreater(image_inputs["width"], image_inputs["height"])
            stored = {c.control_id: c.value for c in reopened.runs.get(run.run_id).controls}
            self.assertEqual((stored["steps"], stored["megapixels"], stored["aspect_ratio"]), (12, 2, "16:9"))
