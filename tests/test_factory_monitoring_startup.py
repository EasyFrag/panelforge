"""User-run startup regressions; memory journals and fake recipe resolution."""
from copy import deepcopy
from datetime import datetime, UTC
import unittest
from unittest.mock import Mock, patch

from panelforge.application.factory_monitoring import FactoryMonitoring
from panelforge.domain.factory_timing import duration_profile, observation
from panelforge.domain.video_factory import fingerprint
from tests.test_factory_monitoring import card, MemoryTimings, NOW, STAMP
from tests.test_video_factory import FakeWorkflows


RECIPE = dict(id="recorded-recipe", version="1.0.0", workflow_sha256="recorded-hash")


def completed(name, *, stage="video", legacy=False, seconds=100):
    item = card(name)
    step = item.setdefault("delivery", {}) if stage == "export" else item["steps"][stage]
    step.update(status="succeeded", started_at=STAMP,
                finished_at=datetime.fromtimestamp(NOW + seconds, UTC).isoformat(), message="")
    if not legacy:
        step["timing"] = dict(id=name + "-timing-" + stage, quality="complete")
    item["runtime"].update(render_project_id=name + "-project", attempt_id=name + "-attempt")
    return item


def adapter():
    value = FakeWorkflows()
    value.timing_recipe = Mock(return_value=deepcopy(RECIPE))
    return value


def record_for(item, *, legacy=False):
    return observation(item, "video", duration_profile(item, "video", "remote_gpu", RECIPE), legacy=legacy)


class FactoryMonitoringStartupTests(unittest.TestCase):
    def test_known_archived_legacy_and_trimmed_samples_need_no_child_reads(self):
        store = MemoryTimings()
        modern, legacy, trimmed = completed("modern"), completed("legacy", legacy=True), completed("trimmed")
        for item in (modern, legacy, trimmed):
            item["archived_at"] = STAMP
        store.value["records"] = [record_for(modern), record_for(legacy, legacy=True)]
        store.value["seen"] = [r["id"] for r in store.value["records"]] + [record_for(trimmed)["id"]]
        original = deepcopy(store.value)
        workflows = adapter()
        workflows.timing_recipe.side_effect = AssertionError("known sample must not reread a child")
        monitor = FactoryMonitoring(store)
        with patch.object(monitor, "profile", side_effect=AssertionError("known profile must not be rebuilt")):
            monitor.bootstrap(workflows, [modern, legacy, trimmed])
        self.assertEqual(store.value, original)
        self.assertEqual(store.saves, 0)
        workflows.timing_recipe.assert_not_called()

    def test_unseen_archives_are_still_learned_once_with_the_effective_recipe(self):
        modern, legacy = completed("new"), completed("old", legacy=True)
        modern["archived_at"] = STAMP
        legacy["archived_at"] = STAMP
        original = deepcopy([modern, legacy])
        store, workflows = MemoryTimings(), adapter()
        monitor = FactoryMonitoring(store)
        monitor.bootstrap(workflows, [modern, legacy, modern, legacy])
        self.assertEqual(workflows.timing_recipe.call_count, 2)
        self.assertEqual(store.saves, 1)
        records = {r["item_id"]: r for r in store.value["records"]}
        self.assertEqual(records[modern["id"]], record_for(modern))
        self.assertEqual(records[legacy["id"]], record_for(legacy, legacy=True))
        step = legacy["steps"]["video"]
        self.assertEqual(records[legacy["id"]]["id"], fingerprint([legacy["id"], "video", step["started_at"], step["finished_at"]]))
        self.assertEqual(records[modern["id"]]["profile"]["recipe"], RECIPE)
        self.assertEqual([modern, legacy], original)
        monitor.bootstrap(workflows, [modern, legacy])
        self.assertEqual(workflows.timing_recipe.call_count, 2)

    def test_ineligible_samples_do_not_resolve_profiles(self):
        items = []
        for quality in ("recovered", "reused"):
            item = completed(quality)
            item["steps"]["video"]["timing"]["quality"] = quality
            items.append(item)
        for field, value in [("started_at", None), ("finished_at", "invalid"),
                             ("finished_at", STAMP), ("status", "running")]:
            item = completed(field + str(value))
            item["steps"]["video"][field] = value
            items.append(item)
        items.append(completed("short", legacy=True, seconds=2))
        ambiguous = completed("ambiguous", legacy=True)
        ambiguous["steps"]["video"]["message"] = "Rendu vidéo · running"
        items.append(ambiguous)
        saved_plan = completed("plan", stage="plan", legacy=True)
        saved_plan["runtime"]["saved_plan"] = {"id": "already-made"}
        items.append(saved_plan)
        store, workflows = MemoryTimings(), adapter()
        monitor = FactoryMonitoring(store)
        with patch.object(monitor, "profile", side_effect=AssertionError("ineligible profile must not be resolved")):
            monitor.bootstrap(workflows, items)
        self.assertEqual(monitor.records, [])
        self.assertEqual(monitor.seen, set())
        self.assertEqual(store.saves, 0)

    def test_missing_child_remains_recoverable_and_does_not_block_other_samples(self):
        missing, available = completed("missing"), completed("available")
        store, workflows = MemoryTimings(), adapter()
        workflows.timing_recipe.side_effect = [FileNotFoundError("missing child"), deepcopy(RECIPE)]
        first = FactoryMonitoring(store)
        first.bootstrap(workflows, [missing, available])
        self.assertEqual(len(first.records), 1)
        self.assertNotIn(record_for(missing)["id"], first.seen)
        workflows.timing_recipe.reset_mock(side_effect=True)
        second = FactoryMonitoring(store)
        second.bootstrap(workflows, [missing, available])
        self.assertEqual(len(second.records), 2)
        self.assertEqual(workflows.timing_recipe.call_count, 1)
        self.assertEqual(store.saves, 2)

    def test_live_duplicate_is_free_but_new_attempt_is_recorded(self):
        item, store, workflows = completed("live"), MemoryTimings(), adapter()
        monitor = FactoryMonitoring(store)
        monitor.record(workflows, item, "video")
        workflows.timing_recipe.side_effect = AssertionError("duplicate must not reread child")
        monitor.record(workflows, item, "video")
        self.assertEqual(workflows.timing_recipe.call_count, 1)
        self.assertEqual(store.saves, 1)
        self.assertIsNone(monitor.warning)
        workflows.timing_recipe.side_effect = None
        item["steps"]["video"]["timing"]["id"] = "new-attempt"
        item["runtime"]["attempt_id"] = "new-child"
        monitor.record(workflows, item, "video")
        self.assertEqual(workflows.timing_recipe.call_count, 2)
        self.assertEqual(store.saves, 2)
        self.assertEqual(monitor.records[-1]["child_id"], "new-child")

    def test_known_export_does_not_rebuild_profile_or_remove_history(self):
        item, store, workflows = completed("export", stage="export"), MemoryTimings(), adapter()
        monitor = FactoryMonitoring(store)
        monitor.bootstrap(workflows, [item])
        before = deepcopy(store.value)
        restored = FactoryMonitoring(store)
        with patch.object(restored, "profile", side_effect=AssertionError("export already measured")):
            restored.bootstrap(workflows, [item])
        self.assertEqual(store.value, before)
        self.assertEqual(store.saves, 1)
        self.assertEqual(before["records"][0]["profile"]["stage"], "export")


if __name__ == "__main__":
    unittest.main()
