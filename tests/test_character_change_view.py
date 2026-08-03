import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.domain.character import (
    OPERATION_ID,
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)


class CharacterChangeViewTest(unittest.TestCase):
    def test_operation_exposes_closed_camera_dimensions(self):
        self.assertEqual(OPERATION_ID, "character.change_view")
        self.assertEqual(len(CameraAzimuth), 8)
        self.assertEqual(len(CameraElevation), 4)
        self.assertEqual(len(ShotSize), 3)

    def test_change_view_is_a_pure_semantic_request(self):
        change = ChangeView(
            source_asset_id="character.anna.base.v1",
            azimuth=CameraAzimuth.BACK,
            elevation=CameraElevation.LOW,
            shot_size=ShotSize.WIDE,
        )

        self.assertEqual(change.source_asset_id, "character.anna.base.v1")
        self.assertFalse(hasattr(change, "seed"))
        self.assertFalse(hasattr(change, "prompt"))

    def test_change_view_rejects_an_empty_source_asset_id(self):
        with self.assertRaisesRegex(ValueError, "source_asset_id"):
            ChangeView(
                source_asset_id="  ",
                azimuth=CameraAzimuth.FRONT,
                elevation=CameraElevation.EYE_LEVEL,
                shot_size=ShotSize.MEDIUM,
            )

    def test_change_view_rejects_untyped_camera_values(self):
        with self.assertRaisesRegex(TypeError, "azimuth"):
            ChangeView(
                source_asset_id="asset-1",
                azimuth="front",  # type: ignore[arg-type]
                elevation=CameraElevation.EYE_LEVEL,
                shot_size=ShotSize.MEDIUM,
            )


if __name__ == "__main__":
    unittest.main()
