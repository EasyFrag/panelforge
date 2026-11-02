"""Catalogue compatibility and metadata regressions, run by the user."""
from collections import Counter
import hashlib
import json
import unittest

from panelforge.domain.little_men_objects import (
    CATALOGS, CATALOG_VERSION, LEGACY_CATALOG_VERSION, LEGACY_OBJECT_ROWS,
    LEGACY_OBJECTS, OBJECT_ROWS, OBJECTS, TRAITS, catalog_for,
    normalize_object_name, object_identity,
)


class ObjectCataloguesTest(unittest.TestCase):
    def test_legacy_rows_and_metadata_remain_exactly_the_approved_v1_catalogue(self):
        # Frozen before the properties/sports addition; covers names, IDs, labels
        # and shelf membership used by previously prepared selections.
        checksum = hashlib.sha256(json.dumps(
            LEGACY_OBJECT_ROWS, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        self.assertEqual(checksum, "4b53553b6af0e19db06933f7450de6f62a74d9540d5be7aeb5749ecdecc0e94c")
        self.assertEqual(len(LEGACY_OBJECTS), 80)
        self.assertEqual(set(Counter(obj["group"] for obj in LEGACY_OBJECTS.values()).values()), {10})
        for obj in LEGACY_OBJECTS.values():
            self.assertEqual(set(obj), {"name", "label", "group"})

    def test_current_catalogue_preserves_identities_and_adds_fifteen_distinct_objects(self):
        self.assertEqual(len(OBJECT_ROWS), 95)
        self.assertEqual(len(OBJECTS), 95)
        self.assertEqual(len({row[0] for row in OBJECT_ROWS}), 95)
        self.assertEqual(len({obj["name"] for obj in OBJECTS.values()}), 95)
        for identity, old in LEGACY_OBJECTS.items():
            self.assertEqual(OBJECTS[identity]["name"], old["name"])
            self.assertEqual(OBJECTS[identity]["group"], old["group"])
            self.assertIsNot(OBJECTS[identity], old)
            if identity != "adhesive_tape":
                self.assertEqual(OBJECTS[identity]["label"], old["label"])
        self.assertEqual(set(OBJECTS) - set(LEGACY_OBJECTS), {
            "glue_tube", "bellows", "needleless_syringe", "retractable_tape_measure",
            "hook_and_loop_tape", "clothes_iron", "piping_bag", "tennis_racket",
            "basketball", "jump_rope", "frisbee", "dumbbell", "swim_fin", "yoga_mat", "roller_skate",
        })

    def test_sports_have_the_eight_agreed_objects_without_reclassifying_legacy_items(self):
        self.assertEqual({key for key, obj in OBJECTS.items() if obj["group"] == "sports"}, {
            "tennis_racket", "basketball", "jump_rope", "frisbee",
            "dumbbell", "swim_fin", "yoga_mat", "roller_skate",
        })
        self.assertEqual(OBJECTS["juggling_ball"]["group"], "leisure")

    def test_properties_are_bounded_descriptions_and_traits_use_one_shared_vocabulary(self):
        for identity, obj in OBJECTS.items():
            with self.subTest(object=identity):
                self.assertEqual(set(obj), {"name", "label", "group", "properties", "traits"})
                for field in ("properties", "traits"):
                    values = obj[field]
                    self.assertIsInstance(values, tuple)
                    self.assertGreaterEqual(len(values), 2)
                    self.assertLessEqual(len(values), 4)
                    self.assertEqual(len(values), len(set(values)))
                    self.assertTrue(all(isinstance(value, str) and 0 < len(value) <= 80 for value in values))
                self.assertLessEqual(set(obj["traits"]), set(TRAITS))
        # Features are shared across shelves, without assigning a mechanism or
        # problem to each item. These contrasts matter to assortment diversity.
        self.assertIn("elastic", OBJECTS["tennis_racket"]["traits"])
        self.assertIn("elastic", OBJECTS["elastic_band"]["traits"])
        self.assertIn("extrudable", OBJECTS["glue_tube"]["traits"])
        self.assertIn("extrudable", OBJECTS["piping_bag"]["traits"])
        self.assertNotEqual(OBJECTS["glue_tube"]["traits"], OBJECTS["adhesive_tape"]["traits"])
        for field in ("mechanism", "mechanism_family", "problem", "solution", "scene"):
            self.assertTrue(all(field not in obj for obj in OBJECTS.values()))
        descriptions = json.dumps(OBJECTS, ensure_ascii=False).casefold()
        for forbidden in ("umbrella", "parasol", "ombrelle"):
            self.assertNotIn(forbidden, descriptions)

    def test_version_lookup_keeps_old_preparations_without_new_properties(self):
        self.assertEqual(LEGACY_CATALOG_VERSION, "1.0.0")
        self.assertEqual(CATALOG_VERSION, "2.0.0")
        self.assertEqual(set(CATALOGS), {LEGACY_CATALOG_VERSION, CATALOG_VERSION})
        self.assertIs(catalog_for(LEGACY_CATALOG_VERSION), LEGACY_OBJECTS)
        self.assertIs(catalog_for(CATALOG_VERSION), OBJECTS)
        self.assertNotIn("glue_tube", catalog_for(LEGACY_CATALOG_VERSION))
        self.assertNotIn("properties", catalog_for(LEGACY_CATALOG_VERSION)["zipper"])
        self.assertIn("properties", catalog_for(CATALOG_VERSION)["zipper"])
        for invalid in (None, "future", [], 2):
            with self.subTest(version=invalid), self.assertRaises(ValueError):
                catalog_for(invalid)

    def test_scotch_is_one_object_with_stable_canonical_name_and_legacy_label(self):
        self.assertEqual(OBJECTS["adhesive_tape"]["name"], "roll of adhesive tape")
        self.assertEqual(OBJECTS["adhesive_tape"]["label"], "Rouleau de scotch")
        self.assertEqual(LEGACY_OBJECTS["adhesive_tape"]["label"], "Rouleau adhésif")
        for name in ("roll of adhesive tape", "Rouleau adhésif", "Rouleau de scotch", "SCOTCH TAPE"):
            self.assertEqual(object_identity(name), "adhesive_tape")

    def test_declared_names_and_known_aliases_normalize_without_guessing_from_prose(self):
        self.assertEqual(normalize_object_name("  ÉPINGLE-de SÛRETÉ  "), "epingle de surete")
        self.assertEqual(normalize_object_name("hook-and-loop tape"), "hook and loop tape")
        for identity, obj in OBJECTS.items():
            self.assertEqual(object_identity(obj["name"]), identity)
            self.assertEqual(object_identity(obj["label"]), identity)
        self.assertEqual(object_identity("tube de glue"), "glue_tube")
        self.assertEqual(object_identity("glue tube"), "glue_tube")
        self.assertEqual(object_identity("skipping rope"), "jump_rope")
        for ambiguous in ("scotch", "tape", "glue", "giant novel glowing tool", "a hand uses a zipper", None, 7):
            self.assertIsNone(object_identity(ambiguous))


if __name__ == "__main__":
    unittest.main()
