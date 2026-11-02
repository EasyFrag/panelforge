"""Offline regressions to be run by the user; no model or renderer required."""
from collections import Counter
from copy import deepcopy
import json
import unittest

from panelforge.domain.little_men_variety import (
    ASSORTMENT_SIZE, MECHANISM_FAMILIES, MECHANISM_LABELS, PRESET_ID,
    RECENT_LIMIT, SELECTION_MARKER, _OBJECT_ROWS, is_variety,
    make_variety_selection as _make_variety_selection, selection_from_text, selection_instructions, validate_selection,
)
from panelforge.domain.little_men_objects import (
    LEGACY_CATALOG_VERSION as CATALOG_VERSION, LEGACY_OBJECTS as OBJECTS,
)


def make_variety_selection(*args, **kwargs):
    """Keep these historical shelf-selection regressions pinned to catalogue 1."""
    return _make_variety_selection(*args, **kwargs, catalog_version=CATALOG_VERSION)


def item(identity, *, selection=None, choice=None, plan=None, status="succeeded", updated="2026-10-29"):
    frozen = {"version": 6}
    if selection is not None:
        frozen["variety"] = selection
    if choice is not None:
        frozen["variety_choice"] = choice
    return {"id": identity, "updated_at": updated, "config": {"preset": PRESET_ID},
            "runtime": {"thanks_selection": frozen}, "history": [],
            "steps": {"plan": {"status": status, "output": {"text": json.dumps(plan or {})}}}}


def choice(*objects, family="link"):
    return {"objects": [{"catalog_id": key, "name": OBJECTS[key]["name"]} for key in objects],
            "mechanism_family": family,
            "departure_reason": None if objects else "Direct hand action is sufficient."}


class VarietyCatalogueTest(unittest.TestCase):
    def test_eighty_unique_objects_without_scene_or_mechanism_assignments(self):
        self.assertEqual(len(_OBJECT_ROWS), 80)
        self.assertEqual(len(OBJECTS), 80)
        self.assertEqual(len({value["name"] for value in OBJECTS.values()}), 80)
        groups = Counter(value["group"] for value in OBJECTS.values())
        self.assertEqual(len(groups), 8)
        self.assertEqual(set(groups.values()), {10})
        self.assertEqual(set(MECHANISM_LABELS), set(MECHANISM_FAMILIES))
        self.assertEqual(len(MECHANISM_FAMILIES), 11)
        self.assertEqual(MECHANISM_FAMILIES["other"], "Other physical operation")
        self.assertEqual(MECHANISM_LABELS["other"], "Autre opération")
        self.assertIn("zipper", OBJECTS)
        self.assertIn("hair_dryer", OBJECTS)
        for value in OBJECTS.values():
            self.assertEqual(set(value), {"name", "label", "group"})
        serialized = json.dumps(OBJECTS, ensure_ascii=False).casefold()
        for forbidden in ("umbrella", "parasol", "ombrelle", "parapluie", "crevasse", "snow", "neige"):
            self.assertNotIn(forbidden, serialized)

    def test_preset_is_distinct_and_custom_origin_is_retained(self):
        self.assertTrue(is_variety({"preset": PRESET_ID}))
        self.assertTrue(is_variety({"preset": "custom", "preset_origin": PRESET_ID}))
        self.assertFalse(is_variety({"preset": "little_men_experimental"}))
        self.assertFalse(is_variety({"preset": "custom", "preset_origin": "little_men_experimental"}))

    def test_assortment_is_deterministic_and_covers_editorial_groups(self):
        first = make_variety_selection("one", [])
        self.assertEqual(first, make_variety_selection("one", []))
        self.assertNotEqual(first["candidates"], make_variety_selection("two", [])["candidates"])
        self.assertEqual(len(first["candidates"]), ASSORTMENT_SIZE)
        self.assertEqual(len(set(first["candidates"])), ASSORTMENT_SIZE)
        groups = Counter(OBJECTS[key]["group"] for key in first["candidates"])
        self.assertEqual(len(groups), 8)
        self.assertTrue(all(count in (1, 2) for count in groups.values()))
        validate_selection(first)

    def test_pending_reservations_reduce_repeated_candidates_without_claiming_usage(self):
        first = make_variety_selection("one", [])
        reserved = item("reserved", selection=first, status="running")
        second = make_variety_selection("one", [reserved])
        self.assertTrue(set(first["candidates"]).isdisjoint(second["candidates"]))
        self.assertEqual(set(second["mechanism_counts"].values()), {0})
        self.assertEqual(reserved["runtime"]["thanks_selection"]["variety"], first)

    def test_resolved_choice_replaces_provisional_exposure(self):
        frozen = make_variety_selection("one", [])
        selected = frozen["candidates"][0]
        completed = item("done", selection=frozen, choice=choice(selected, family="shield"))
        with_exposure = make_variety_selection("one", [completed])
        only_choice = make_variety_selection("one", [item("done", choice=choice(selected, family="shield"))])
        self.assertEqual(with_exposure, only_choice)
        self.assertNotIn(selected, with_exposure["candidates"])
        self.assertEqual(with_exposure["mechanism_counts"]["shield"], 1)
        self.assertEqual(with_exposure["mechanism_priority"][-2], "shield")
        self.assertEqual(with_exposure["mechanism_priority"][-1], "other")

    def test_other_is_counted_but_never_promoted_by_novelty(self):
        selection = make_variety_selection("new", [item("known", choice=choice(family="link"))])
        self.assertEqual(selection["mechanism_counts"]["other"], 0)
        self.assertEqual(selection["mechanism_priority"][-1], "other")
        selected_other = make_variety_selection("new", [item("unusual", choice=choice(family="other"))])
        self.assertEqual(selected_other["mechanism_counts"]["other"], 1)
        self.assertEqual(selected_other["mechanism_priority"][-1], "other")
        self.assertEqual(set(selected_other["mechanism_priority"]), set(MECHANISM_FAMILIES))
        self.assertIn("Use other only when none of the ten usual families", selection_instructions(selection))

    def test_actual_usage_has_more_weight_than_provisional_exposure(self):
        first = make_variety_selection("one", [])
        used = first["candidates"][0]
        group = OBJECTS[used]["group"]
        alternatives = [key for key, value in OBJECTS.items() if value["group"] == group and key != used]
        items = [item("used", choice=choice(used))]
        for index, alternative in enumerate(alternatives):
            reservation = deepcopy(first)
            reservation["candidates"] = [alternative] + [key for key in OBJECTS
                if key != alternative and OBJECTS[key]["group"] != group][:ASSORTMENT_SIZE - 1]
            items.append(item(f"reservation-{index}", selection=reservation, status="running"))
        selected = make_variety_selection("one", items)
        self.assertNotIn(used, selected["candidates"])

    def test_counts_once_per_fiche_and_ignores_self_other_presets_and_history(self):
        current = item("same", choice=choice("zipper", "zipper", family="link"))
        current["history"] = [{"variety_choice": choice("hair_dryer", family="temperature")}]
        current["archived_at"] = "2026-10-29"
        other = item("other", choice=choice("zipper", family="link"))
        other["config"]["preset"] = "little_men_experimental"
        selection = make_variety_selection("self", [current, current, other,
            item("self", choice=choice("hair_dryer", family="temperature"))])
        self.assertEqual(selection["mechanism_counts"]["link"], 1)
        self.assertEqual(selection["mechanism_counts"]["temperature"], 0)
        self.assertEqual(sum(selection["mechanism_counts"].values()), 1)

    def test_current_approved_plan_is_a_fallback_but_pending_stale_output_is_not(self):
        plan = {"variety_choice": choice("zipper", family="link")}
        approved = item("approved", plan=plan)
        pending = item("pending", plan=plan, status="pending")
        self.assertEqual(make_variety_selection("new", [approved, pending])["mechanism_counts"]["link"], 1)
        approved["runtime"]["thanks_selection"]["variety_choice"] = choice("hair_dryer", family="temperature")
        selected = make_variety_selection("new", [approved])
        self.assertEqual(selected["mechanism_counts"]["link"], 0)
        self.assertEqual(selected["mechanism_counts"]["temperature"], 1)

    def test_recent_window_is_bounded(self):
        history = [item(str(index), choice=choice(family="link"), updated=f"{index:04}")
                   for index in range(RECENT_LIMIT + 5)]
        selection = make_variety_selection("new", history)
        self.assertEqual(selection["mechanism_counts"]["link"], RECENT_LIMIT)

    def test_frozen_selection_parsing_uses_last_internal_block(self):
        selection = make_variety_selection("one", [])
        source = "Original source" + SELECTION_MARKER + "invalid previous example"
        source += SELECTION_MARKER + json.dumps(selection) + "\n" + selection_instructions(selection)
        self.assertEqual(selection_from_text(source), selection)
        instructions = selection_instructions(selection)
        self.assertIn("Accessories remain optional", instructions)
        self.assertIn("soft preferences", instructions)
        self.assertIn("departure_reason", instructions)
        self.assertNotIn("zipper for", instructions)
        self.assertNotIn("hair dryer for", instructions)

    def test_invalid_frozen_selections_are_rejected(self):
        original = make_variety_selection("one", [])
        mutations = [lambda s: s.update(catalog_version="future"),
                     lambda s: s["candidates"].append("zipper"),
                     lambda s: s["candidates"].__setitem__(0, s["candidates"][1]),
                     lambda s: s["candidates"].__setitem__(0, "unknown"),
                     lambda s: s["mechanism_counts"].__setitem__("link", True),
                     lambda s: s["mechanism_counts"].__setitem__("link", -1),
                     lambda s: s["mechanism_priority"].__setitem__(0, "unknown"),
                     lambda s: s["mechanism_priority"].pop(),
                     lambda s: s.update(extra="not frozen input")]
        for mutate in mutations:
            candidate = deepcopy(original)
            mutate(candidate)
            with self.subTest(selection=candidate), self.assertRaises(ValueError):
                validate_selection(candidate)
        for text in ("No selection", SELECTION_MARKER, SELECTION_MARKER + "not JSON"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                selection_from_text(text)


if __name__ == "__main__":
    unittest.main()
