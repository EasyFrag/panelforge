"""User-run variety lifecycle regressions with memory storage and fake workflows."""
from copy import deepcopy
import json
from threading import RLock
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import PRESET_ID, make_variety_selection
from panelforge.domain.localized_speech import FIXED_THANKS
from panelforge.domain.video_factory import apply_preset, LITTLE_MEN_VARIETY_INTENT
from tests.test_little_men_causal import causal_fixture
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_languages import config_for


def variety_config():
    source = config_for("Pays : Japon")
    config = apply_preset(source, PRESET_ID, source)
    config.update(little_men_direction_version=6, intention=LITTLE_MEN_VARIETY_INTENT)
    return config


class ObservedLock:
    """Expose ownership in these single-threaded tests while retaining a real RLock."""
    def __init__(self):
        self.lock = RLock()
        self.depth = 0

    def __enter__(self):
        self.lock.acquire()
        self.depth += 1
        return self

    def __exit__(self, *_error):
        self.depth -= 1
        self.lock.release()


class VarietyFactoryLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.store, self.adapter = MemoryStore(), FakeWorkflows()
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)

    def receive(self, name="Experimental", *, config=None, runtime=None):
        response = self.service.receive([dict(name=name, config=config or variety_config(),
            source={"kind": "image", "id": name}, runtime=runtime or {})])
        return response["ids"][0]

    def item(self, identity):
        return next(item for item in self.service.snapshot()["items"] if item["id"] == identity)

    def stored(self, identity):
        return next(item for item in self.store.value["items"] if item["id"] == identity)

    def selection(self, *identities):
        return list(identities), {identity: self.item(identity)["revision"] for identity in identities}

    def launch(self, *identities):
        self.service.launch(*self.selection(*identities))

    def test_assortment_is_reserved_under_lock_and_persisted_before_adapter_entry(self):
        identity = self.receive()
        self.launch(identity)
        observed = ObservedLock()
        self.service._lock = observed
        events = []
        reserved = []
        original_save = self.store.save

        def allocate(*args, **kwargs):
            self.assertGreater(observed.depth, 0)
            events.append("allocate")
            frozen = make_variety_selection(*args, **kwargs)
            reserved.append(deepcopy(frozen))
            return frozen

        def persist(state):
            if any(item["runtime"].get("thanks_selection", {}).get("variety") for item in state["items"]):
                self.assertGreater(observed.depth, 0)
                events.append("persist")
            original_save(state)

        def run(snapshot, stage, checkpoint, cancelled, progress):
            self.assertEqual(stage, "plan")
            self.assertEqual(observed.depth, 0)
            self.assertEqual(events[:2], ["allocate", "persist"])
            frozen = snapshot["runtime"]["thanks_selection"]["variety"]
            self.assertEqual(frozen, reserved[0])
            self.assertEqual(self.stored(identity)["runtime"]["thanks_selection"]["variety"], frozen)
            events.append("adapter")
            # An adapter receives a snapshot, not the persisted selection object.
            frozen["candidates"].reverse()
            return {"text": "mock plan"}

        self.adapter.run = Mock(side_effect=run)
        with (patch("panelforge.application.video_factory.make_variety_selection", side_effect=allocate) as allocator,
              patch.object(self.store, "save", side_effect=persist)):
            self.service._execute("local_gpu", identity, "plan")
        allocator.assert_called_once()
        self.adapter.run.assert_called_once()
        self.assertEqual(self.item(identity)["steps"]["plan"]["status"], "succeeded")
        self.assertEqual(self.stored(identity)["runtime"]["thanks_selection"]["variety"], reserved[0])

    def test_restart_and_retry_preserve_the_reserved_assortment(self):
        identity = self.receive()
        self.launch(identity)
        inputs = []

        def interrupted(snapshot, stage, checkpoint, cancelled, progress):
            inputs.append(deepcopy(snapshot["runtime"]["thanks_selection"]))
            checkpoint(session_id="existing-preparation")
            raise RuntimeError("Temporary fake gateway failure")

        self.adapter.run = Mock(side_effect=interrupted)
        self.service._execute("local_gpu", identity, "plan")
        failed = self.item(identity)
        self.assertEqual(failed["status"], "failed")
        original = deepcopy(failed["runtime"]["thanks_selection"])
        self.assertEqual(failed["runtime"]["session_id"], "existing-preparation")

        resumed = FakeWorkflows()

        def finish(snapshot, stage, checkpoint, cancelled, progress):
            inputs.append(deepcopy(snapshot["runtime"]["thanks_selection"]))
            self.assertEqual(snapshot["runtime"]["session_id"], "existing-preparation")
            return {"text": "resumed mock plan"}

        resumed.run = Mock(side_effect=finish)
        self.service = VideoFactoryService(store=self.store, adapter=resumed)
        self.service.action("retry", *self.selection(identity))
        with patch("panelforge.application.video_factory.make_variety_selection",
                   side_effect=AssertionError("Retry must not draw another assortment")):
            self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(inputs, [original, original])
        self.assertEqual(self.item(identity)["steps"]["plan"]["status"], "succeeded")
        self.assertEqual(self.stored(identity)["runtime"]["thanks_selection"], original)

    def test_explicit_v5_migration_allocates_v7_assortment_without_rechoosing_language(self):
        config = config_for("Pays : Japon")
        selected = make_selection(config, "old-language")
        selected.update(language="Japanese", words=FIXED_THANKS["Japanese"])
        identity = self.receive(config=config, runtime={"thanks_selection": selected})
        self.service.update(*self.selection(identity), preset=PRESET_ID)
        migrated = self.item(identity)["runtime"]["thanks_selection"]
        self.assertEqual(migrated["version"], 7)
        self.assertNotIn("variety", migrated)
        self.assertEqual(migrated["requested_language"], "Japanese")
        self.launch(identity)
        self.service._execute("local_gpu", identity, "plan")
        final = self.item(identity)["runtime"]["thanks_selection"]
        self.assertEqual(final["version"], 7)
        self.assertEqual(len(final["variety"]["candidates"]), 12)
        self.assertEqual(final["priority"], selected["priority"])
        self.assertEqual(final["language"], "Japanese")
        self.assertEqual(final["requested_language"], "Japanese")
        self.assertEqual(final["words"], FIXED_THANKS["Japanese"])
        self.assertNotIn("variety", selected)

    def test_duplicate_gets_a_fresh_reservation_while_original_remains_frozen(self):
        identity = self.receive()
        self.launch(identity)
        self.adapter.run = Mock(side_effect=RuntimeError("Fake stop before Plan choice"))
        self.service._execute("local_gpu", identity, "plan")
        original = deepcopy(self.item(identity)["runtime"]["thanks_selection"]["variety"])
        self.service.action("duplicate", *self.selection(identity))
        duplicate = next(item for item in self.service.snapshot()["items"] if item["id"] != identity)
        self.assertNotIn("thanks_selection", duplicate["runtime"])
        self.assertNotIn("session_id", duplicate["runtime"])
        self.assertEqual(duplicate["config"]["preset"], PRESET_ID)
        duplicate_id = duplicate["id"]
        self.adapter.run = Mock(return_value={"text": "new mock plan"})
        self.launch(duplicate_id)
        self.service._execute("local_gpu", duplicate_id, "plan")
        new = self.item(duplicate_id)["runtime"]["thanks_selection"]["variety"]
        self.assertTrue(set(original["candidates"]).isdisjoint(new["candidates"]))
        self.assertEqual(self.item(identity)["runtime"]["thanks_selection"]["variety"], original)

    def test_next_plan_receives_actual_accepted_mechanism_once(self):
        first, second = self.receive("First"), self.receive("Second")
        self.launch(first, second)
        observed = []
        plan, _, _ = causal_fixture(language="Japanese")
        choice = {"objects": [], "mechanism_family": "redirect",
                  "departure_reason": "The hand can directly move the threatening subject clear of the inhabitants."}
        plan["variety_choice"] = choice

        def accepted(snapshot, stage, checkpoint, cancelled, progress):
            selected = deepcopy(snapshot["runtime"]["thanks_selection"])
            observed.append(deepcopy(selected["variety"]))
            selected.update(language="Japanese", words=FIXED_THANKS["Japanese"],
                            variety_choice=deepcopy(choice))
            checkpoint(thanks_selection=selected)
            return {"text": json.dumps(plan)}

        self.adapter.run = Mock(side_effect=accepted)
        self.service._execute("local_gpu", first, "plan")
        self.service._execute("local_gpu", second, "plan")
        self.assertEqual(self.adapter.run.call_count, 2)
        self.assertEqual(sum(observed[0]["mechanism_counts"].values()), 0)
        self.assertEqual(observed[1]["mechanism_counts"]["redirect"], 1)
        self.assertEqual(sum(observed[1]["mechanism_counts"].values()), 1)
        self.assertEqual(observed[1]["mechanism_priority"][-1], "redirect")
        for identity in (first, second):
            saved = self.item(identity)
            self.assertEqual(saved["runtime"]["thanks_selection"]["variety_choice"], choice)
            self.assertEqual(json.loads(saved["steps"]["plan"]["output"]["text"])["variety_choice"], choice)

    def test_current_v5_preset_never_allocates_an_assortment(self):
        config = config_for("Pays : Japon")
        original = deepcopy(config)
        identity = self.receive(config=config)
        self.launch(identity)
        with patch("panelforge.application.video_factory.make_variety_selection",
                   side_effect=AssertionError("The current preset must remain independent")) as allocator:
            self.service._execute("local_gpu", identity, "plan")
        allocator.assert_not_called()
        saved = self.item(identity)
        self.assertEqual(saved["steps"]["plan"]["status"], "succeeded")
        self.assertEqual(saved["config"], original)
        self.assertEqual(saved["runtime"]["thanks_selection"]["version"], 5)
        self.assertNotIn("variety", saved["runtime"]["thanks_selection"])
        self.assertNotIn("variety_choice", saved["runtime"]["thanks_selection"])


if __name__ == "__main__":
    unittest.main()
