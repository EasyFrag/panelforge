"""User-run checks for the optional H3/REF2V upscale branch; no render is submitted."""

from pathlib import Path
import unittest

from panelforge.domain import (
    H3RenderInputMode,
    VideoAspectRatio,
    VideoLabSettings,
    h3_upscale_plan,
)
from panelforge.infrastructure.presets import (
    H3RenderPresetRecipe,
    Ref2VH3RenderPresetRecipe,
    VideoLabPresetRecipe,
    load_h3_render_workflow,
    load_video_lab_workflow,
)


WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
H3_CURRENT = WORKFLOWS / "video.generate.h3-base/minimax-h3-latent-speed/0.1.7"
REF2V_CURRENT = WORKFLOWS / "video.generate.ref2v/minimax-h3-ref2v/0.2.5"


class H3UpscaleBypassTest(unittest.TestCase):
    def settings(self, megapixels=0.2):
        return VideoLabSettings(
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=megapixels,
            duration_seconds=9,
            steps=25,
            seed=123,
        )

    def test_new_bypass_recipes_are_the_runtime_defaults(self):
        from scripts import run_lab

        self.assertEqual(run_lab.H3_RENDER_WORKFLOW_DIRECTORY.resolve(), H3_CURRENT.resolve())
        self.assertEqual(run_lab.REF2V_RENDER_WORKFLOW_DIRECTORY.resolve(), REF2V_CURRENT.resolve())

    def test_plan_bypasses_equal_and_lower_targets_without_downscaling(self):
        equal = h3_upscale_plan(self.settings(0.2), 0.2)
        self.assertTrue(equal["same_resolution"])
        self.assertTrue(equal["bypassed"])
        self.assertEqual(equal["effective_resolution"], equal["initial_resolution"])

        lower = h3_upscale_plan(self.settings(0.2), 0.6)
        self.assertTrue(lower["target_is_lower"])
        self.assertTrue(lower["bypassed"])
        self.assertEqual(lower["effective_resolution"], lower["initial_resolution"])

        forced = h3_upscale_plan(self.settings(0.2), 0.2, force_upscale=True)
        self.assertFalse(forced["bypassed"])
        with self.assertRaisesRegex(ValueError, "résolutions initiale et cible sont égales"):
            h3_upscale_plan(self.settings(0.2), 0.6, force_upscale=True)
        with self.assertRaisesRegex(ValueError, "résolutions initiale et cible sont égales"):
            h3_upscale_plan(self.settings(0.6), 0.2, force_upscale=True)

    def test_h3_graph_prunes_or_retains_upscale_branch(self):
        recipe = H3RenderPresetRecipe(load_h3_render_workflow(H3_CURRENT))
        common = dict(
            input_mode=H3RenderInputMode.T2VA,
            first_frame=None,
            last_frame=None,
            prompt="A continuous shot.",
            settings=self.settings(),
            initial_megapixels=0.2,
            output_filename_prefix="video/test",
            keyframe_indices=(),
        )
        bypassed = recipe.build_workflow(**common)
        self.assertTrue(recipe.supports_upscale_bypass)
        self.assertNotIn("28", bypassed)
        self.assertNotIn("25", bypassed)
        self.assertEqual(bypassed["11"]["inputs"]["samples"], ["26", 0])
        self.assertEqual(bypassed["12"]["inputs"]["samples"], ["26", 0])

        forced = recipe.build_workflow(**common, force_upscale=True)
        self.assertIn("28", forced)
        self.assertIn("25", forced)
        self.assertEqual(forced["11"]["inputs"]["samples"], ["25", 0])
        self.assertEqual(forced["12"]["inputs"]["samples"], ["25", 0])

    def test_ref2v_graph_prunes_or_retains_upscale_branch(self):
        recipe = Ref2VH3RenderPresetRecipe(
            VideoLabPresetRecipe(load_video_lab_workflow(REF2V_CURRENT))
        )
        common = dict(
            source_images=("reference.png",),
            prompt="A continuous shot.",
            settings=self.settings(),
            initial_megapixels=0.2,
            output_filename_prefix="video/test",
            keyframe_indices=(),
        )
        bypassed = recipe.build_workflow(**common)
        self.assertTrue(recipe.supports_upscale_bypass)
        self.assertNotIn("26", bypassed)
        self.assertNotIn("16", bypassed)
        self.assertEqual(bypassed["25"]["inputs"]["samples"], ["21", 0])
        self.assertEqual(bypassed["14"]["inputs"]["samples"], ["21", 0])

        extended = recipe.build_workflow(
            **{
                **common,
                "source_images": tuple(f"reference-{index}.png" for index in range(1, 5)),
                "keyframe_indices": (0,),
            }
        )
        self.assertEqual(extended["11"]["inputs"]["ref_images.ref_image_3"], ["20003", 0])
        self.assertIn("20100", extended)
        self.assertEqual(extended["20050"]["inputs"]["image"], ["25", 0])

        forced = recipe.build_workflow(**common, force_upscale=True)
        self.assertIn("26", forced)
        self.assertIn("16", forced)
        self.assertEqual(forced["25"]["inputs"]["samples"], ["16", 0])
        self.assertEqual(forced["14"]["inputs"]["samples"], ["16", 0])


if __name__ == "__main__":
    unittest.main()
