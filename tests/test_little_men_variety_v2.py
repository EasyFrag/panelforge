"""User-run regressions for versioned assortment data; no model or renderer."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from panelforge.domain import little_men_variety as variety
from panelforge.domain.little_men_direction import writer_intention_v8
from panelforge.domain.little_men_objects import (
    CATALOG_VERSION, LEGACY_CATALOG_VERSION, LEGACY_OBJECTS, OBJECTS,
)
from panelforge.domain.little_men_variety_history import (
    empty_history, record_choice, record_exposure,
)


def with_choice(history, index, identity=None, *, family="support", outside=None):
    objects = ([{"catalog_id": identity, "name": OBJECTS[identity]["name"]}]
               if identity else [{"catalog_id": None, "name": outside}] if outside else [])
    return record_choice(
        history, preparation_id=f"preparation-{index}", item_id=f"item-{index}",
        plan_id=f"plan-{index}", accepted_at=f"2026-10-30T10:{index:02}:00+00:00",
        choice={"objects": objects, "mechanism_family": family,
                "departure_reason": "A relevant direct choice."},
    )


class VersionedAssortmentTest(unittest.TestCase):
    def test_legacy_payload_and_instructions_match_prechange_golden_data(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/little_men_variety_v1.json")
                             .read_text(encoding="utf-8"))
        selection = fixture["selection"]
        variety.validate_selection(selection)
        self.assertEqual(variety.selection_instructions(selection), fixture["selection_instructions"])
        self.assertEqual(variety.selection_instructions_v8(selection), fixture["selection_instructions_v8"])
        self.assertNotIn("Recent combinations:", variety.selection_instructions_v8(selection))

    def test_catalogue_version_limits_membership_and_metadata_shape(self):
        legacy = variety.make_variety_selection("legacy", [], catalog_version=LEGACY_CATALOG_VERSION)
        current = variety.make_variety_selection("current", [])
        self.assertEqual(current["catalog_version"], CATALOG_VERSION)
        self.assertIn("recent_pairs", current)
        self.assertNotIn("recent_pairs", legacy)
        bad = deepcopy(legacy)
        bad["candidates"][0] = "glue_tube"
        with self.assertRaises(ValueError):
            variety.validate_selection(bad)
        bad = deepcopy(current)
        del bad["recent_pairs"]
        with self.assertRaises(ValueError):
            variety.validate_selection(bad)
        self.assertTrue(set(legacy["candidates"]).issubset(LEGACY_OBJECTS))

    def test_selection_is_frozen_reproducible_and_has_twelve_distinct_candidates(self):
        history = with_choice(empty_history(), 1, "zipper", family="link")
        before = deepcopy(history)
        first = variety.make_variety_selection("one", [], history=history)
        self.assertEqual(first, variety.make_variety_selection("one", [], history=history))
        self.assertNotEqual(first["candidates"],
                            variety.make_variety_selection("two", [], history=history)["candidates"])
        self.assertEqual(len(set(first["candidates"])), 12)
        self.assertEqual(history, before)
        restored = json.loads(json.dumps(first))
        variety.validate_selection(restored)
        self.assertEqual(first, restored)

    def test_trait_diversity_works_within_a_single_editorial_shelf(self):
        # Identical shelves cannot account for the diversity in this fixture.
        catalogue = {
            **{f"brush-{i}": {"group": "one", "traits": ("bristles",)} for i in range(12)},
            **{f"distinct-{i}": {"group": "one", "traits": (f"trait-{i}",)} for i in range(8)},
        }
        with patch.object(variety, "catalog_for", return_value=catalogue):
            selection = variety.make_variety_selection("coverage", [], history=empty_history())
        self.assertTrue({f"distinct-{i}" for i in range(8)}.issubset(selection["candidates"]))
        self.assertEqual(len(selection["candidates"]), 12)

    def test_actual_uses_reduce_selection_more_than_one_exposure(self):
        baseline = variety.make_variety_selection("usage", [], history=empty_history())
        used = baseline["candidates"][0]
        history = record_exposure(
            empty_history(), preparation_id="offered", item_id="offered", candidates=baseline["candidates"],
            reserved_at="2026-10-30T09:00:00+00:00",
        )
        for index in range(1, 5):
            history = with_choice(history, index, used)
        selected = variety.make_variety_selection("usage", [], history=history)
        self.assertNotIn(used, selected["candidates"])
        self.assertEqual(selected["mechanism_counts"]["support"], 4)
        self.assertEqual(selected["mechanism_priority"][-1], "other")

    def test_new_preparation_can_include_previous_choices_from_the_same_fiche(self):
        history = with_choice(empty_history(), 1, "zipper", family="link")
        same = variety.make_variety_selection("item-1", [], exclude="", history=history)
        self.assertEqual(same["mechanism_counts"]["link"], 1)
        self.assertEqual(same["recent_pairs"][0]["object_key"], "zipper")

    def test_only_twelve_objects_properties_and_bounded_pairs_reach_plan_context(self):
        history = with_choice(empty_history(), 1, "glue_tube", family="link")
        selection = variety.make_variety_selection("properties", [], history=history)
        instructions = variety.selection_instructions_v8(selection)
        self.assertEqual(sum(line.startswith("- ") for line in instructions.splitlines()), 12)
        for identity in selection["candidates"]:
            self.assertIn(f"- {identity}: {OBJECTS[identity]['name']} — "
                          + "; ".join(OBJECTS[identity]["properties"]), instructions)
        for identity in set(OBJECTS) - set(selection["candidates"]):
            self.assertNotIn(f"- {identity}:", instructions)
        self.assertIn("not exhaustive uses", instructions)
        self.assertIn("not observed video success", instructions)
        source = "Author video intention." + variety.SELECTION_MARKER + json.dumps(selection) + "\n" + instructions
        self.assertEqual(variety.selection_from_text(source), selection)
        self.assertEqual(writer_intention_v8(source), "Author video intention.")

    def test_main_hand_outside_names_and_object_mechanism_pairs_are_preserved(self):
        history = with_choice(empty_history(), 1, family="support")
        history = with_choice(history, 2, outside='Wooden "beam"', family="link")
        history = with_choice(history, 3, "zipper", family="link")
        history = with_choice(history, 4, "zipper", family="separate")
        selection = variety.make_variety_selection("pairs", [], history=history)
        pairs = {(p["object_key"], p["mechanism_family"]): p for p in selection["recent_pairs"]}
        self.assertIn(("__hand__", "support"), pairs)
        self.assertIn(("zipper", "link"), pairs)
        self.assertIn(("zipper", "separate"), pairs)
        outside = next(p for p in selection["recent_pairs"] if p["object_key"].startswith("external:"))
        rendered = variety.selection_instructions_v8(selection).split("Recent combinations: ", 1)[1]
        self.assertEqual(json.loads(rendered), selection["recent_pairs"])
        self.assertIn(outside, json.loads(rendered))

    def test_bad_recent_pairs_are_rejected_without_changing_plan_fields(self):
        history = with_choice(empty_history(), 1, "zipper", family="link")
        original = variety.make_variety_selection("invalid", [], history=history)
        mutations = (
            lambda s: s["recent_pairs"][0].update(count=True),
            lambda s: s["recent_pairs"][0].update(count=51),
            lambda s: s["recent_pairs"][0].update(name="a different accessory"),
            lambda s: s["recent_pairs"][0].update(mechanism_family="unknown"),
            lambda s: s["recent_pairs"].append(dict(s["recent_pairs"][0])),
            lambda s: s.update(recent_pairs=original["recent_pairs"] * 13),
        )
        for mutate in mutations:
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(selection=changed), self.assertRaises(ValueError):
                variety.validate_selection(changed)


if __name__ == "__main__":
    unittest.main()
