from __future__ import annotations

import unittest

from panelforge.domain.storyboard import (
    StoryboardSpec,
    storyboard_layout,
)


def storyboard_payload(panel_count: int) -> dict[str, object]:
    return {
        "sequence_context": (
            "Mira crosses the same workshop while assembling a small paper glider."
        ),
        "avoid_repeats": [],
        "characters": [
            {
                "label": "Mira",
                "identity_lock": (
                    "An adult engineer with short black hair and round glasses."
                ),
                "wardrobe_lock": "The same blue coveralls and brown boots.",
                "allowed_progression": (
                    "Sleeves may be rolled up, but no garment is replaced."
                ),
            }
        ],
        "environment": {
            "location_lock": "The same compact aircraft workshop.",
            "lighting_lock": "Soft morning light from the north window.",
            "layout_lock": "Workbench left, tool wall behind, window right.",
            "props_lock": ["red toolbox", "paper glider", "desk lamp"],
        },
        "panels": [
            {
                "present_characters": ["Mira"],
                "framing": "three-quarter portrait shot",
                "camera_angle": "eye-level front angle",
                "visual_beat": f"Mira completes assembly step {number}.",
                "emotional_beat": f"Her concentration changes subtly at step {number}.",
                "continuity_from_previous": (
                    None
                    if number == 1
                    else f"She continues directly from assembly step {number - 1}."
                ),
                "visible_anchors": ["red toolbox", "paper glider"],
            }
            for number in range(1, panel_count + 1)
        ],
    }


class StoryboardContractTests(unittest.TestCase):
    def test_supported_counts_derive_grid_page_ratio_and_positions(self) -> None:
        expected = {
            2: (2, 1, "4:3", "landscape", ("left", "right")),
            4: (
                2,
                2,
                "2:3",
                "portrait",
                ("top-left", "top-right", "bottom-left", "bottom-right"),
            ),
            6: (
                3,
                2,
                "1:1",
                "square",
                (
                    "top-left",
                    "top-middle",
                    "top-right",
                    "bottom-left",
                    "bottom-middle",
                    "bottom-right",
                ),
            ),
            9: (
                3,
                3,
                "2:3",
                "portrait",
                (
                    "top-left",
                    "top-middle",
                    "top-right",
                    "middle-left",
                    "center",
                    "middle-right",
                    "bottom-left",
                    "bottom-middle",
                    "bottom-right",
                ),
            ),
        }
        for panel_count, values in expected.items():
            with self.subTest(panel_count=panel_count):
                layout = storyboard_layout(panel_count)
                self.assertEqual(
                    (layout.columns, layout.rows, layout.page_aspect_ratio, layout.page_orientation),
                    values[:4],
                )
                self.assertEqual(
                    tuple(layout.position(number) for number in range(1, panel_count + 1)),
                    values[4],
                )

    def test_only_product_panel_counts_are_supported(self) -> None:
        for value in (0, 1, 3, 5, 8, 10):
            with self.subTest(value=value), self.assertRaises(ValueError):
                storyboard_layout(value)
        with self.assertRaises(TypeError):
            storyboard_layout(True)

    def test_payload_round_trip_is_exact(self) -> None:
        payload = storyboard_payload(4)
        spec = StoryboardSpec.from_payload(payload, expected_panel_count=4)

        self.assertEqual(spec.panel_count, 4)
        self.assertEqual(spec.to_payload(), payload)

    def test_panel_count_continuity_and_character_references_are_strict(self) -> None:
        payload = storyboard_payload(4)
        with self.assertRaisesRegex(ValueError, "exactly 6"):
            StoryboardSpec.from_payload(payload, expected_panel_count=6)

        payload = storyboard_payload(4)
        payload["panels"][0]["continuity_from_previous"] = "Earlier moment."
        with self.assertRaisesRegex(ValueError, "Panel 1"):
            StoryboardSpec.from_payload(payload)

        payload = storyboard_payload(4)
        payload["panels"][2]["continuity_from_previous"] = None
        with self.assertRaisesRegex(ValueError, "Panel 3"):
            StoryboardSpec.from_payload(payload)

        payload = storyboard_payload(4)
        payload["panels"][1]["present_characters"] = ["Unknown"]
        with self.assertRaisesRegex(ValueError, "unknown characters"):
            StoryboardSpec.from_payload(payload)

    def test_unknown_fields_and_unsupported_framing_are_rejected(self) -> None:
        payload = storyboard_payload(4)
        payload["panels"][0]["panel_number"] = 1
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            StoryboardSpec.from_payload(payload)

        for framing in ("wide shot", "landscape full-body shot", "close-up"):
            payload = storyboard_payload(4)
            payload["panels"][0]["framing"] = framing
            with self.subTest(framing=framing), self.assertRaisesRegex(
                ValueError,
                "full-body or three-quarter",
            ):
                StoryboardSpec.from_payload(payload)


if __name__ == "__main__":
    unittest.main()
