from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

from panelforge.infrastructure.storyboard_recipes import (
    LocalStoryboardRecipeCatalog,
)

from tests.test_storyboard_contract import storyboard_payload


ROOT = Path(__file__).resolve().parents[1]


class StoryboardRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = LocalStoryboardRecipeCatalog(ROOT / "storyboard_recipes")
        cls.recipe = cls.catalog.get("krea2.storyboard.from_text", "0.1.0")

    def test_recipe_is_versioned_and_fingerprinted(self) -> None:
        self.assertEqual(len(self.catalog.list()), 1)
        self.assertEqual(self.recipe.recipe_id, "krea2.storyboard.from_text")
        self.assertEqual(self.recipe.version, "0.1.0")
        self.assertEqual(self.recipe.panel_counts, (2, 4, 6, 9))
        self.assertRegex(self.recipe.template_sha256, r"^[0-9a-f]{64}$")

    def test_request_uses_source_and_derived_geometry_with_exact_schema_count(self) -> None:
        system, user = self.recipe.build_request_prompts(
            "Mira builds and launches a paper glider.",
            6,
        )

        self.assertIn("exactly 6 consecutive visual beats", system)
        self.assertIn('"minItems": 6', system)
        self.assertIn('"maxItems": 6', system)
        self.assertIn("3 columns by 2 rows", user)
        self.assertIn("square 1:1 page", user)
        self.assertIn("Mira builds and launches a paper glider.", user)

    def test_raw_and_complete_json_fence_parse_without_repair(self) -> None:
        payload = storyboard_payload(4)
        raw = json.dumps(payload)
        fenced = "```json\n" + raw + "\n```"

        self.assertEqual(self.recipe.parse_spec(raw, 4).to_payload(), payload)
        self.assertEqual(self.recipe.parse_spec(fenced, 4).to_payload(), payload)

        with self.assertRaisesRegex(ValueError, "JSON"):
            self.recipe.parse_spec("Here it is:\n" + raw, 4)
        with self.assertRaisesRegex(ValueError, "fence"):
            self.recipe.parse_spec("```json\n" + raw, 4)
        with self.assertRaisesRegex(ValueError, "one JSON object"):
            self.recipe.parse_spec("[]", 4)

    def test_parser_rejects_wrong_panel_count_and_extra_fields(self) -> None:
        payload = storyboard_payload(4)
        with self.assertRaisesRegex(ValueError, "exactly 6"):
            self.recipe.parse_spec(json.dumps(payload), 6)

        payload = storyboard_payload(4)
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            self.recipe.parse_spec(json.dumps(payload), 4)

    def test_compiler_preserves_fixed_skeleton_and_derives_all_panel_positions(self) -> None:
        for panel_count, geometry in {
            2: "landscape 4:3",
            4: "portrait 2:3",
            6: "square 1:1",
            9: "portrait 2:3",
        }.items():
            with self.subTest(panel_count=panel_count):
                spec = self.recipe.parse_spec(
                    json.dumps(storyboard_payload(panel_count)),
                    panel_count,
                )
                prompt = self.recipe.compile_prompt(spec, panel_count)

                self.assertIn("Every single panel MUST be a vertical 2:3", prompt)
                self.assertIn(f"an overall {geometry} storyboard page", prompt)
                self.assertIn("LOCKED CONTINUITY", prompt)
                self.assertIn("Thin even black gutters", prompt)
                self.assertIn("no text, no watermark, no captions", prompt)
                self.assertEqual(
                    len(re.findall(r"(?m)^Panel \d+, row \d+, column \d+,", prompt)),
                    panel_count,
                )
                for panel_number in range(1, panel_count + 1):
                    self.assertEqual(prompt.count(f"Panel {panel_number}, row"), 1)

        six = self.recipe.compile_prompt(
            self.recipe.parse_spec(json.dumps(storyboard_payload(6)), 6),
            6,
        )
        self.assertIn("THREE COLUMNS × TWO ROWS", six)
        self.assertIn("Panel 5, row 2, column 2, bottom-middle", six)

    def test_compile_rejects_a_different_requested_count(self) -> None:
        spec = self.recipe.parse_spec(json.dumps(storyboard_payload(4)), 4)
        with self.assertRaisesRegex(ValueError, "exactly 6"):
            self.recipe.compile_prompt(spec, 6)

    def test_compiled_prompts_are_golden_for_every_supported_layout(self) -> None:
        expected = {
            2: "b1dfce2f6647784ec948145be22d1334a9d4415ebb876e7a467279b3ceee7736",
            4: "1ee2c361d907b4e1eb18b93470f8499d1e0cb5908e862ba7c0be347053fd8346",
            6: "47abb3d515f98e542ab615875d740f08c6e805f7aa947202485b256731e60bb8",
            9: "7aa945786a172e0e9184f3c630901bb8dd260483529f01f0073c2cdbd26b31d4",
        }
        for panel_count, expected_sha256 in expected.items():
            with self.subTest(panel_count=panel_count):
                spec = self.recipe.parse_spec(
                    json.dumps(storyboard_payload(panel_count)),
                    panel_count,
                )
                prompt = self.recipe.compile_prompt(spec, panel_count)
                self.assertEqual(
                    hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    expected_sha256,
                )

    def test_quality_warnings_are_non_blocking_and_deterministic(self) -> None:
        payload = storyboard_payload(4)
        payload["panels"][1]["framing"] = payload["panels"][0]["framing"]
        payload["panels"][1]["camera_angle"] = payload["panels"][0]["camera_angle"]
        payload["panels"][1]["visual_beat"] = payload["panels"][0]["visual_beat"]
        for index in range(2, 6):
            character = copy.deepcopy(payload["characters"][0])
            character["label"] = f"Engineer {index}"
            payload["characters"].append(character)
        spec = self.recipe.parse_spec(json.dumps(payload), 4)

        warnings = self.recipe.warnings_for_spec(spec, 4)

        self.assertTrue(any("quatre personnages" in item for item in warnings))
        self.assertTrue(any("cadrage" in item for item in warnings))
        self.assertTrue(any("temps visuel" in item for item in warnings))
        self.assertTrue(self.recipe.compile_prompt(spec, 4))


if __name__ == "__main__":
    unittest.main()
