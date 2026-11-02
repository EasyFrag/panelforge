"""User-run history regressions; pure data, with no LLM or rendering calls."""
from copy import deepcopy
import json
import unittest

from panelforge.domain.little_men_objects import OBJECTS, LEGACY_OBJECTS
from panelforge.domain.little_men_variety_history import (
    HAND_KEY, HISTORY_LIMIT, bootstrap_history, empty_history, plan_identity,
    preparation_identity, record_choice, record_exposure, summarize_history,
)


def choice(*objects, family="link"):
    return {"objects": [{"catalog_id": identity, "name": OBJECTS[identity]["name"]}
                        for identity in objects], "mechanism_family": family,
            "departure_reason": None if objects else "Direct action is sufficient."}


def legacy_item(identity, selected=None, *, day=1, updated="2099-01-01T00:00:00Z",
                status="succeeded", finished=True):
    selected = selected if selected is not None else choice("zipper")
    candidates = list(LEGACY_OBJECTS)[:12]
    return {
        "id": identity, "updated_at": updated,
        "config": {"preset": "little_men_variety"},
        "runtime": {"session_id": "session-" + identity,
                    "thanks_selection": {
                        "version": 8, "variety_choice": selected,
                        "variety": {"catalog_version": "1.0.0", "candidates": candidates},
                    }},
        "steps": {"plan": {"status": status,
                            "started_at": f"2026-01-{day:02}T09:00:00Z",
                            "finished_at": f"2026-01-{day:02}T10:00:00Z" if finished else None,
                            "output": {"text": json.dumps({"variety_choice": selected})}}},
    }


class VarietyHistoryTest(unittest.TestCase):
    def test_recording_does_not_mutate_input_and_retry_preserves_original_date(self):
        journal = empty_history()
        before = deepcopy(journal)
        first = record_choice(journal, "prep", "item", "plan", choice("zipper"),
                              "2026-01-01T10:00:00Z")
        retry = record_choice(first, "prep", "item", "plan", choice("zipper"),
                              "2026-02-01T10:00:00Z")
        self.assertEqual(journal, before)
        self.assertEqual(first, retry)
        self.assertEqual(first["choices"][0]["accepted_at"], "2026-01-01T10:00:00.000000+00:00")
        newer = record_choice(first, "prep", "item", "plan-2", choice("zipper"),
                              "2026-01-02T10:00:00Z")
        self.assertEqual(summarize_history(newer)["object_counts"]["zipper"], 2)

    def test_exposures_remain_distinct_after_selection_and_are_not_usage(self):
        candidates = list(OBJECTS)[:12]
        pending = record_exposure(empty_history(), "prep", "item", candidates,
                                  "2026-01-01T09:00:00Z")
        summary = summarize_history(pending)
        self.assertEqual(summary["object_counts"], {})
        self.assertEqual(summary["mechanism_counts"], {})
        self.assertEqual(summary["exposure_counts"], dict.fromkeys(candidates, 1))
        resolved = record_choice(pending, "prep", "item", "plan", choice("zipper"),
                                 "2026-01-01T10:00:00Z")
        self.assertEqual(summarize_history(resolved)["exposure_counts"], summary["exposure_counts"])
        self.assertEqual(summarize_history(resolved)["object_counts"], {"zipper": 1})
        self.assertEqual(record_exposure(resolved, "prep", "item", candidates,
                                         "2026-02-01T10:00:00Z"), resolved)

    def test_aliases_external_names_and_empty_hand_form_distinct_counted_pairs(self):
        journal = empty_history()
        entries = [
            {"objects": [{"catalog_id": None, "name": "Scotch tape"}], "mechanism_family": "link"},
            {"objects": [{"catalog_id": "adhesive_tape", "name": "roll of adhesive tape"}],
             "mechanism_family": "link"},
            {"objects": [{"catalog_id": None, "name": "WOODEN   SLED"}], "mechanism_family": "move"},
            {"objects": [{"catalog_id": None, "name": "wooden sled"}], "mechanism_family": "move"},
            choice(family="support"),
        ]
        for index, selected in enumerate(entries):
            journal = record_choice(journal, str(index), str(index), "plan", selected,
                                     f"2026-01-0{index + 1}T10:00:00Z")
        summary = summarize_history(journal)
        self.assertEqual(summary["object_counts"], {"adhesive_tape": 2,
                         "external:wooden sled": 2, HAND_KEY: 1})
        pairs = {(row["object_key"], row["mechanism_family"]): row["count"]
                 for row in summary["recent_pairs"]}
        self.assertEqual(pairs[("adhesive_tape", "link")], 2)
        self.assertEqual(pairs[("external:wooden sled", "move")], 2)
        self.assertEqual(pairs[(HAND_KEY, "support")], 1)

    def test_same_object_multiple_mechanisms_and_duplicates_in_one_choice(self):
        journal = record_choice(empty_history(), "a", "one", "plan", choice("zipper", "zipper"),
                                 "2026-01-01T10:00:00Z")
        journal = record_choice(journal, "b", "two", "plan", choice("zipper", family="separate"),
                                 "2026-01-02T10:00:00Z")
        summary = summarize_history(journal)
        self.assertEqual(summary["object_counts"], {"zipper": 2})
        self.assertEqual(summary["mechanism_counts"], {"link": 1, "separate": 1})
        self.assertEqual(len(summary["recent_pairs"]), 2)
        self.assertEqual(summarize_history(journal, exclude_item_id="one")["object_counts"], {"zipper": 1})

    def test_windows_are_bounded_by_event_time_not_insertion_or_item_update(self):
        journal = empty_history()
        candidates = list(OBJECTS)[:12]
        for index in reversed(range(HISTORY_LIMIT + 5)):
            date = f"2026-01-01T10:{index:02}:00Z"
            journal = record_choice(journal, str(index), str(index), "plan", choice("zipper"), date)
            journal = record_exposure(journal, str(index), str(index), candidates, date)
        self.assertEqual(len(journal["choices"]), HISTORY_LIMIT)
        self.assertEqual(len(journal["exposures"]), HISTORY_LIMIT)
        self.assertNotIn("0", {entry["item_id"] for entry in journal["choices"]})
        self.assertEqual(summarize_history(journal)["object_counts"]["zipper"], HISTORY_LIMIT)
        self.assertEqual(bootstrap_history([], journal), journal)

    def test_legacy_bootstrap_uses_stable_dates_and_never_scans_fiche_revisions(self):
        old = legacy_item("old", day=1)
        recent = legacy_item("recent", choice("hair_dryer", family="temperature"), day=2,
                             updated="2000-01-01T00:00:00Z")
        pending = legacy_item("pending", day=3, status="pending")
        undated = legacy_item("undated", day=4, finished=False)
        other = legacy_item("other", day=5)
        other["config"]["preset"] = "little_men_experimental"
        old["history"] = [legacy_item("irrelevant", choice("glue_tube"), day=6)]
        original = deepcopy([old, recent, pending, undated, other])
        journal = bootstrap_history(original)
        self.assertEqual([row["item_id"] for row in journal["choices"]], ["recent", "old"])
        self.assertEqual(summarize_history(journal)["mechanism_counts"], {"temperature": 1, "link": 1})
        self.assertEqual(original, [old, recent, pending, undated, other])
        # Deleting or resetting a fiche does not erase or re-import persisted usage.
        self.assertEqual(bootstrap_history([], journal), journal)
        reset = legacy_item("old", choice("glue_tube"), day=7)
        self.assertEqual(bootstrap_history([reset], journal), journal)

    def test_preparation_and_plan_identity_are_stable_without_using_updated_at(self):
        item = legacy_item("one")
        before = preparation_identity(item)
        item["updated_at"] = "2099-12-31T10:00:00Z"
        self.assertEqual(preparation_identity(item), before)
        item["runtime"]["variety_preparation_id"] = "explicit-reservation"
        self.assertEqual(preparation_identity(item), "explicit-reservation")
        self.assertEqual(plan_identity('{"b": 2, "a": 1}'), plan_identity('{"a":1,"b":2}'))
        self.assertNotEqual(plan_identity('{"a":1}'), plan_identity('{"a":2}'))
        fallback = legacy_item("two")
        fallback["runtime"].pop("session_id")
        self.assertTrue(preparation_identity(fallback).startswith("legacy:"))

    def test_invalid_events_are_rejected_or_ignored_during_legacy_import(self):
        with self.assertRaises(ValueError):
            record_choice(empty_history(), "prep", "item", "plan", choice("zipper"), "2026-01-01")
        with self.assertRaises(ValueError):
            record_choice(empty_history(), "prep", "item", "plan", choice(family="unknown"),
                          "2026-01-01T10:00:00Z")
        invalid = legacy_item("bad", choice(family="unknown"))
        self.assertEqual(bootstrap_history([invalid])["choices"], [])
        journal = record_choice(empty_history(), "prep", "item", "plan", choice("zipper"),
                                 "2026-01-01T10:00:00Z")
        with self.assertRaises(ValueError):
            record_choice(journal, "prep", "item", "plan", choice("hair_dryer"),
                          "2026-01-02T10:00:00Z")
        corrupted = deepcopy(journal)
        corrupted["choices"].append({"accepted_at": "2099-01-01T00:00:00Z"})
        self.assertEqual(bootstrap_history([], corrupted), journal)
        with self.assertRaises(ValueError):
            plan_identity(None)
        with self.assertRaises(ValueError):
            plan_identity("  ")
        malformed = legacy_item("malformed")
        malformed["runtime"] = ["invalid"]
        self.assertEqual(bootstrap_history([malformed]), empty_history())


if __name__ == "__main__":
    unittest.main()
