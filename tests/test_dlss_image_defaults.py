"""Image defaults at the API/workflow boundary; no runtime or generation calls."""
from dataclasses import asdict
from pathlib import Path
import unittest

from panelforge.domain.dlss import DlssSettings
from panelforge.features.lab.dlss_web import DlssRequestBody
from panelforge.infrastructure.presets.dlss import DlssWorkflow


ROOT = Path(__file__).resolve().parents[1]


class DlssImageDefaultsTest(unittest.TestCase):
    def body(self, owner, settings):
        return DlssRequestBody(owner=owner, owner_id="workshop", attempt_id="original", settings=settings)

    def test_image_defaults_reach_the_node_including_fixed_controls(self):
        workflow = DlssWorkflow(ROOT / "workflows/image.upscale/dlss/0.1.0")
        for owner in ("assisted", "edit"):
            with self.subTest(owner=owner):
                settings = self.body(owner, {}).resolved_settings()
                self.assertEqual(settings, DlssSettings(size="1.5", skin=-1))
                graph = workflow.build("test.png", "test", settings)
                inputs = next(node["inputs"] for node in graph.values() if node["class_type"] == "NvidiaDLSSImageUpscale")
                self.assertEqual({key: value for key, value in inputs.items() if key != "image"}, {
                    "upscale_mode": "1.5× (Quality)", "require_neural_upscaling": False,
                    "nr_preset": "Default", "nr_style": "Default", "nr_intensity": 1,
                    "local_tone_strength": 1, "local_structure_strength": 1, "skin_structure_strength": -1,
                    "automatic_mask": False, "dlss_model_preset": "Default", "output_detail_strength": 1})
                # Compiling a new request never rewrites a versioned graph.
                self.assertEqual(next(node["inputs"]["nr_intensity"] for node in workflow.graph.values()
                    if node["class_type"] == "NvidiaDLSSImageUpscale"), 2)

    def test_explicit_image_settings_and_existing_saved_settings_are_preserved(self):
        for owner in ("assisted", "edit"):
            for size in ("source", "2"):
                previous = DlssSettings(size=size, skin=2, intensity=2, tone=2, structure=2)
                self.assertEqual(self.body(owner, asdict(previous)).resolved_settings(), previous)
            partial = self.body(owner, {"intensity": 0.5, "skin": 0, "strict_neural": False}).resolved_settings()
            self.assertEqual(partial, DlssSettings(size="1.5", skin=0, intensity=0.5))

    def test_video_defaults_and_explicit_quick_settings_are_unchanged(self):
        quick = DlssSettings(size="1.724", interpolate=True, skin=-1)
        for owner in ("h3", "ref2v"):
            self.assertEqual(self.body(owner, {}).resolved_settings(), DlssSettings())
            self.assertEqual(self.body(owner, asdict(quick)).resolved_settings(), quick)
