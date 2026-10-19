import unittest

from panelforge.domain import (
    KREA2_RESOLUTION_MULTIPLE,
    Krea2AspectRatio,
    Krea2LabSettings,
    RecipeRef,
    normalize_krea2_model_name,
)


DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)


class Krea2LabDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Krea2LabSettings(
            model_name=DEFAULT_MODEL,
            aspect_ratio=Krea2AspectRatio.PORTRAIT_PHOTO,
            megapixels=3.0,
            seed=2**63,
            seed_locked=True,
        )
        self.recipe = RecipeRef(
            operation_id="image.generate.t2i",
            recipe_id="krea2",
            version="0.1.0",
            workflow_sha256="a" * 64,
        )

    def test_default_portrait_settings_derive_expected_resolution(self) -> None:
        self.assertEqual(self.settings.resolution, (1448, 2176))
        self.assertEqual(self.settings.resolution[0] % KREA2_RESOLUTION_MULTIPLE, 0)
        self.assertEqual(self.settings.resolution[1] % KREA2_RESOLUTION_MULTIPLE, 0)

    def test_every_ratio_stays_aligned_and_keeps_its_orientation(self) -> None:
        for ratio in Krea2AspectRatio:
            with self.subTest(ratio=ratio.value):
                settings = Krea2LabSettings(DEFAULT_MODEL, ratio, 1.0, 7)
                width, height = settings.resolution
                expected_width, expected_height = ratio.dimensions
                self.assertEqual(width % 8, 0)
                self.assertEqual(height % 8, 0)
                self.assertEqual(
                    (width > height) - (width < height),
                    (expected_width > expected_height)
                    - (expected_width < expected_height),
                )

    def test_megapixels_are_bounded_and_use_tenths(self) -> None:
        for value in (0.4, 4.1, 1.25, float("nan")):
            with self.subTest(megapixels=value):
                with self.assertRaises(ValueError):
                    Krea2LabSettings(
                        DEFAULT_MODEL,
                        Krea2AspectRatio.SQUARE,
                        value,
                        1,
                    )

    def test_model_normalization_does_not_rewrite_the_stored_name(self) -> None:
        server_name = (
            "kREA2\\KREA2gptgrandpussytruth_gptint4int8convrot.safetensors"
        )
        settings = Krea2LabSettings(
            server_name,
            Krea2AspectRatio.SQUARE,
            1.0,
            1,
        )

        self.assertEqual(
            normalize_krea2_model_name(server_name),
            normalize_krea2_model_name(DEFAULT_MODEL),
        )
        self.assertEqual(settings.model_name, server_name)


if __name__ == "__main__":
    unittest.main()
