import unittest

from panelforge.domain import (
    RecipeRef,
    VideoAspectRatio,
    VideoLabSettings,
)


class VideoLabDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio.PORTRAIT_PHOTO,
            megapixels=0.6,
            duration_seconds=10.0,
            steps=32,
            seed=7,
        )
        self.recipe = RecipeRef(
            operation_id="video.generate.ref2v",
            recipe_id="minimax-h3-ref2v",
            version="0.1.0",
            workflow_sha256="a" * 64,
        )

    def test_balanced_settings_derive_resolution_and_effective_duration(self) -> None:
        self.assertEqual(self.settings.resolution, (640, 960))
        self.assertEqual(self.settings.frame_count, 243)
        self.assertEqual(self.settings.effective_duration_seconds, 10.125)

    def test_h3_duration_range_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 5 and 15"):
            VideoLabSettings(
                aspect_ratio=VideoAspectRatio.SQUARE,
                megapixels=0.6,
                duration_seconds=16.0,
                steps=32,
                seed=1,
            )


if __name__ == "__main__":
    unittest.main()
