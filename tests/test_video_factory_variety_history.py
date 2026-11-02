"""User-run catalogue/history integration regressions; fake workflows only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import Mock, patch

from panelforge.application.little_men_standard import ChosenObject
from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.little_men_objects import CATALOG_VERSION, LEGACY_CATALOG_VERSION, OBJECTS
from panelforge.domain.little_men_variety_history import record_choice, summarize_history
from panelforge.domain.video_factory import invalidate
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_standard import standard_config


class CatalogueHistoryLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.store, self.adapter = MemoryStore(), FakeWorkflows()
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)

    def receive(self, name="New catalogue", config=None):
        return self.service.receive([dict(
            name=name, config=config or standard_config(True),
            source={"kind": "image", "id": name})])["ids"][0]

    def item(self, identity):
        return next(item for item in self.service.snapshot()["items"] if item["id"] == identity)

    def launch(self, identity):
        self.service.launch([identity], {identity: self.item(identity)["revision"]})

    def load_historical_plan(self, *, choice_in_runtime=True):
        from panelforge.domain.little_men_languages import make_selection
        from panelforge.domain.little_men_variety import make_variety_selection
        identity = self.receive("Legacy")
        item = self.service._get(identity)
        selection = make_selection(item["config"], identity)
        selection["variety"] = make_variety_selection(identity, [], catalog_version=LEGACY_CATALOG_VERSION)
        object_id = selection["variety"]["candidates"][0]
        choice = dict(objects=[dict(catalog_id=object_id, name=OBJECTS[object_id]["name"])],
                      mechanism_family="link", departure_reason=None)
        if choice_in_runtime:
            selection["variety_choice"] = choice
        text = json.dumps({"variety_choice": choice})
        item["runtime"].update(thanks_selection=selection, session_id="legacy-session")
        item["steps"]["plan"].update(status="succeeded", output={"text": text},
                                    started_at="2026-10-01T00:00:00+00:00",
                                    finished_at="2026-10-01T00:01:00+00:00")
        self.service._save((item,))
        self.store.value.pop("variety_history", None)
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)
        return identity, text, choice

    def accepted(self, snapshot, stage, checkpoint, cancelled, progress):
        self.assertEqual(stage, "plan")
        selection = deepcopy(snapshot["runtime"]["thanks_selection"])
        object_id = selection["variety"]["candidates"][0]
        choice = dict(objects=[dict(catalog_id=object_id, name=OBJECTS[object_id]["name"])],
                      mechanism_family="link", departure_reason=None)
        selection["variety_choice"] = choice
        checkpoint(thanks_selection=selection)
        return {"text": json.dumps({"variety_choice": choice})}

    def test_reservation_and_exposure_are_durable_before_call_and_not_duplicated_by_retry(self):
        identity = self.receive()
        self.launch(identity)
        observed = []

        def fail(snapshot, stage, checkpoint, cancelled, progress):
            selected = snapshot["runtime"]["thanks_selection"]["variety"]
            self.assertEqual(selected["catalog_version"], CATALOG_VERSION)
            history = self.store.value["variety_history"]
            self.assertEqual(len(history["exposures"]), 1)
            self.assertEqual(history["choices"], [])
            self.assertEqual(history["exposures"][0]["candidates"], selected["candidates"])
            observed.append(deepcopy(history))
            raise RuntimeError("Fake interrupted preparation")

        self.adapter.run = Mock(side_effect=fail)
        self.service._execute("local_gpu", identity, "plan")
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)
        self.service.action("retry", [identity], {identity: self.item(identity)["revision"]})
        self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0], observed[1])

    def test_accepted_choices_survive_fiche_removal_and_feed_later_assortments(self):
        identity = self.receive("First")
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        self.service._execute("local_gpu", identity, "plan")
        history = deepcopy(self.store.value["variety_history"])
        self.assertEqual(len(history["choices"]), 1)
        self.assertEqual(len(history["exposures"]), 1)
        self.service.action("remove", [identity], {identity: self.item(identity)["revision"]})
        self.assertEqual(self.store.value["variety_history"], history)
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)
        second = self.receive("Second")
        self.launch(second)
        self.service._execute("local_gpu", second, "plan")
        frozen = self.item(second)["runtime"]["thanks_selection"]["variety"]
        self.assertEqual(frozen["mechanism_counts"]["link"], 1)
        self.assertEqual(frozen["recent_pairs"][0]["count"], 1)
        self.assertEqual(len(self.store.value["variety_history"]["choices"]), 2)

    def test_same_plan_keeps_its_first_date_after_rendering_and_reexecution(self):
        identity = self.receive()
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        self.service._execute("local_gpu", identity, "plan")
        before = deepcopy(self.store.value["variety_history"])
        marker = deepcopy(self.item(identity)["runtime"]["variety_choice_record"])
        self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(self.store.value["variety_history"], before)
        self.assertEqual(self.item(identity)["runtime"]["variety_choice_record"], marker)
        item = self.service._get(identity)
        item["steps"]["video"].update(status="succeeded", finished_at="2099-01-01T00:00:00+00:00")
        self.service._save((item,))
        restarted = VideoFactoryService(store=self.store, adapter=self.adapter)
        self.assertEqual(restarted.snapshot()["variety_history"], before)

    def test_retry_after_history_eviction_does_not_make_an_old_plan_recent(self):
        identity = self.receive()
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        with patch("panelforge.application.video_factory.timestamp", return_value="2026-10-01T00:00:00+00:00"):
            self.service._execute("local_gpu", identity, "plan")
        marker = deepcopy(self.item(identity)["runtime"]["variety_choice_record"])
        history = self.service._state["variety_history"]
        for index in range(50):
            accepted_at = (datetime(2026, 10, 2, tzinfo=timezone.utc)
                           + timedelta(minutes=index)).isoformat()
            history = record_choice(history, f"prep-{index}", f"item-{index}", f"plan-{index}",
                                    {"objects": [], "mechanism_family": "move"}, accepted_at)
        self.service._state["variety_history"] = history
        self.assertNotIn(identity, {event["item_id"] for event in history["choices"]})
        self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(self.store.value["variety_history"], history)
        self.assertEqual(self.item(identity)["runtime"]["variety_choice_record"], marker)

    def test_missing_runtime_marker_uses_the_existing_journals_original_date(self):
        identity = self.receive()
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        with patch("panelforge.application.video_factory.timestamp", return_value="2026-10-01T00:00:00+00:00"):
            self.service._execute("local_gpu", identity, "plan")
        original = deepcopy(self.item(identity)["runtime"]["variety_choice_record"])
        self.service._get(identity)["runtime"].pop("variety_choice_record")
        self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(self.item(identity)["runtime"]["variety_choice_record"], original)

    def test_invalidated_choice_keeps_preparation_provenance_when_assortment_is_retained(self):
        identity = self.receive()
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        self.service._execute("local_gpu", identity, "plan")
        item = self.item(identity)
        original = deepcopy(item)
        item["config"]["writer_model_id"] = "different-writer"
        invalidate(item, original["config"])
        for key in ("variety_preparation_id", "variety_reserved_at", "variety_choice_record"):
            self.assertEqual(item["runtime"][key], original["runtime"][key])
        self.assertNotIn("variety_choice", item["runtime"]["thanks_selection"])
        changed = deepcopy(item["config"])
        item["config"] = deepcopy(original["config"])
        invalidate(item, changed)
        self.assertEqual(item["steps"]["plan"]["status"], "succeeded")
        self.assertEqual(item["runtime"]["variety_choice_record"],
                         original["runtime"]["variety_choice_record"])

    def test_existing_legacy_assortment_is_not_replaced_or_enriched(self):
        from panelforge.domain.little_men_languages import make_selection
        from panelforge.domain.little_men_variety import make_variety_selection
        identity = self.receive()
        item = self.service._get(identity)
        selected = make_selection(item["config"], identity)
        selected["variety"] = make_variety_selection(identity, [], catalog_version=LEGACY_CATALOG_VERSION)
        item["runtime"]["thanks_selection"] = selected
        original = deepcopy(selected["variety"])
        self.service._save((item,))
        self.launch(identity)
        self.adapter.run = Mock(side_effect=self.accepted)
        with patch("panelforge.application.video_factory.make_variety_selection",
                   side_effect=AssertionError("A frozen legacy assortment must be retained")):
            self.service._execute("local_gpu", identity, "plan")
        self.assertEqual(self.item(identity)["runtime"]["thanks_selection"]["variety"], original)
        self.assertEqual(summarize_history(self.store.value["variety_history"])["mechanism_counts"]["link"], 1)

    def test_legacy_preparation_keeps_identity_when_its_session_is_recreated(self):
        identity, text, choice = self.load_historical_plan()
        item = self.service._get(identity)
        marker = deepcopy(item["runtime"]["variety_choice_record"])
        before = deepcopy(self.service._state["variety_history"])
        previous = deepcopy(item["config"])
        item["config"]["writer_model_id"] = "different-writer"
        invalidate(item, previous)
        item["runtime"]["session_id"] = "replacement-session"
        item["runtime"]["thanks_selection"]["variety_choice"] = choice
        self.service._remember_variety_choice(item, text, "2026-10-30T12:00:00+00:00")
        self.assertEqual(self.service._state["variety_history"], before)
        self.assertEqual(item["runtime"]["variety_choice_record"], marker)
        self.assertEqual(item["runtime"]["variety_preparation_id"], marker["preparation_id"])

    def test_legacy_choice_missing_from_runtime_is_anchored_before_history_eviction(self):
        identity, text, choice = self.load_historical_plan(choice_in_runtime=False)
        item = self.service._get(identity)
        marker = deepcopy(item["runtime"]["variety_choice_record"])
        self.assertNotIn("variety_choice", item["runtime"]["thanks_selection"])
        history = self.service._state["variety_history"]
        for index in range(50):
            accepted_at = (datetime(2026, 10, 2, tzinfo=timezone.utc)
                           + timedelta(minutes=index)).isoformat()
            history = record_choice(history, f"prep-{index}", f"item-{index}", f"plan-{index}",
                                    {"objects": [], "mechanism_family": "move"}, accepted_at)
        self.service._state["variety_history"] = history
        item["runtime"]["thanks_selection"]["variety_choice"] = choice
        self.service._remember_variety_choice(item, text, "2026-10-30T12:00:00+00:00")
        self.assertEqual(self.service._state["variety_history"], history)
        self.assertEqual(item["runtime"]["variety_choice_record"], marker)

    def test_normal_preset_does_not_reserve_or_record_variety(self):
        identity = self.receive(config=standard_config(False))
        self.launch(identity)
        self.service._execute("local_gpu", identity, "plan")
        self.assertNotIn("variety_preparation_id", self.item(identity)["runtime"])
        self.assertEqual(self.store.value["variety_history"]["choices"], [])
        self.assertEqual(self.store.value["variety_history"]["exposures"], [])


class HistoricalObjectIdentityTest(unittest.TestCase):
    def test_catalogue_growth_does_not_reclassify_an_old_external_object(self):
        self.assertIsNone(ChosenObject.model_validate({"catalog_id": None, "name": "bellows"}).catalog_id)
        self.assertEqual(ChosenObject.model_validate({"catalog_id": None, "name": "zipper"}).catalog_id,
                         "zipper")
        self.assertEqual(ChosenObject.model_validate({"catalog_id": "bellows", "name": "bellows"}).catalog_id,
                         "bellows")


if __name__ == "__main__":
    unittest.main()
