"""Monitoring regressions. Run explicitly; no real workers or GPU services."""
from copy import deepcopy
from datetime import datetime, UTC
import tempfile
import unittest

from panelforge.domain.video_factory import configuration, initial_steps, new_item, STAGES
from panelforge.domain.video_factory_results import delivery_material
from panelforge.domain.factory_timing import DurationModel, duration_profile, observation
from panelforge.domain.factory_cycle import admit_cycle, sync_cycle, cycle_counts, delivered
from panelforge.domain.factory_forecast import forecast
from panelforge.application.factory_monitoring import FactoryMonitoring
from panelforge.application.video_factory import VideoFactoryService, FactoryConflict
from panelforge.infrastructure.storage.factory_timings import LocalFactoryTimingsStore
from tests.test_video_factory import MemoryStore, FakeWorkflows

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC).timestamp()
STAMP = datetime.fromtimestamp(NOW, UTC).isoformat()


def card(name="A", *, final=False, options=True):
    config = configuration()
    config.update(intention="Une personne marche.", references=[dict(asset_id="asset-image", role="first_frame")])
    config["dlss"]["enabled"] = options
    config["social"]["enabled"] = options
    if final:
        config["final_prompt"] = "A person walks."
    item = new_item(name, config, {"kind": "image"}, name)
    item.update(status="queued", launch_snapshot=deepcopy(config))
    return item


def inputs(items):
    state = dict(items=items, paused=False)
    admit_cycle(state, items)
    sync_cycle(state)
    estimates, lanes = {}, {}
    for item in items:
        identity = item["id"]
        estimates[identity], lanes[identity] = {}, {}
        for stage, seconds in dict(plan=20, prompt=10, video=100, dlss=40, social=10, export=5).items():
            if stage in STAGES and item["steps"][stage]["status"] in {"skipped", "succeeded"}:
                seconds = 0
            estimates[identity][stage] = dict(seconds=seconds, low=seconds, high=seconds,
                                              confidence="medium", samples=12, reason="Comparable")
            lanes[identity][stage] = "remote_gpu" if stage == "video" else "local_gpu"
    machine = dict(observed_at=STAMP, settings=dict(remote_video_cooldown_seconds=30),
                   machines={lane: dict(state="idle", queue_count=0) for lane in ("local_gpu", "remote_gpu")})
    return state, estimates, lanes, machine


class MemoryTimings:
    def __init__(self):
        self.value = dict(schema_version=1, records=[], seen=[])
        self.saves = 0
    def load(self): return deepcopy(self.value)
    def save(self, value):
        self.saves += 1
        self.value = deepcopy(value)


class DurationTest(unittest.TestCase):
    def test_profiles_ignore_seed_but_separate_recipe_machine_and_geometry(self):
        item = card()
        profile = duration_profile(item, "video", "remote_gpu", {"id": "recipe", "version": "effective-1"})
        changed = deepcopy(item)
        changed["launch_snapshot"]["render"]["settings"]["seed"] = 1234
        self.assertEqual(profile, duration_profile(changed, "video", "remote_gpu", {"id": "recipe", "version": "effective-1"}))
        changed["launch_snapshot"]["render"]["settings"]["duration_seconds"] = 10
        self.assertNotEqual(profile, duration_profile(changed, "video", "remote_gpu", {"id": "recipe", "version": "effective-1"}))
        self.assertNotEqual(profile, duration_profile(item, "video", "local_gpu", {"id": "recipe", "version": "effective-1"}))
        self.assertNotEqual(profile, duration_profile(item, "video", "remote_gpu", {"id": "recipe", "version": "effective-2"}))

    def test_outliers_missing_history_and_overrun_are_explicit(self):
        profile = duration_profile(card(), "video", "remote_gpu")
        records = [dict(profile=profile, seconds=v, finished_at=STAMP) for v in (1, 98, 99, 100, 101, 102, 5000)]
        model = DurationModel(records)
        self.assertEqual(model.estimate(profile)["seconds"], 100)
        overdue = model.estimate(profile, elapsed=103)
        self.assertGreater(overdue["seconds"], 0)
        self.assertTrue(overdue["indicative"])
        self.assertEqual(overdue["confidence"], "low")
        self.assertLessEqual(overdue["low"], overdue["seconds"])
        self.assertGreaterEqual(overdue["high"], overdue["seconds"])
        self.assertGreater(DurationModel().estimate(dict(profile, stage="export"), elapsed=120)["seconds"], 0)
        self.assertIsNone(model.estimate(dict(profile, lane="local_gpu"))["seconds"])
        self.assertEqual(DurationModel().estimate(dict(profile, stage="export"))["source"], "allowance")

    def test_recovered_and_ambiguous_legacy_samples_are_not_learned(self):
        item = card()
        step = item["steps"]["video"]
        step.update(status="succeeded", started_at=STAMP,
                    finished_at=datetime.fromtimestamp(NOW + 100, UTC).isoformat(),
                    timing=dict(id="recovery", quality="recovered"))
        profile = duration_profile(item, "video", "remote_gpu")
        self.assertIsNone(observation(item, "video", profile))
        step.pop("timing")
        step["message"] = "Rendu vidéo · running"
        self.assertIsNone(observation(item, "video", profile, legacy=True))
        step["message"] = ""
        self.assertEqual(observation(item, "video", profile, legacy=True)["seconds"], 100)

    def test_history_is_idempotent_and_survives_card_deletion(self):
        adapter, store, item = FakeWorkflows(), MemoryTimings(), card()
        item["steps"]["prompt"].update(status="succeeded", started_at=STAMP,
            finished_at=datetime.fromtimestamp(NOW + 20, UTC).isoformat())
        monitor = FactoryMonitoring(store)
        monitor.bootstrap(adapter, [item])
        second = FactoryMonitoring(store)
        second.bootstrap(adapter, [item])
        self.assertEqual(len(store.value["records"]), 1)
        self.assertEqual(store.saves, 1)
        third = FactoryMonitoring(store)
        third.bootstrap(adapter, [])
        self.assertEqual(len(third.records), 1)

    def test_corrupt_journal_is_not_overwritten(self):
        class Broken(MemoryTimings):
            def load(self): raise ValueError("Corrupt")
        store = Broken()
        monitor = FactoryMonitoring(store)
        monitor._persist()
        self.assertEqual(store.saves, 0)
        self.assertIsNotNone(monitor.warning)

    def test_local_journal_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalFactoryTimingsStore(directory)
            value = dict(schema_version=1, records=[], seen=["already-imported"])
            store.save(value)
            self.assertEqual(LocalFactoryTimingsStore(directory).load(), value)


class NearbyGpuDurationTest(unittest.TestCase):
    @staticmethod
    def story(references):
        item = card()
        config = item["config"]
        config["mode"] = "ref2v"
        config["references"] = [dict(asset_id="environment", role="environment_reference")] + [
            dict(asset_id=f"subject-{i}", role="subject_reference") for i in range(references - 1)]
        item["launch_snapshot"] = deepcopy(config)
        return item

    def test_adjacent_reference_count_is_indicative_and_exact_history_wins(self):
        history = duration_profile(self.story(6), "video", "remote_gpu")
        target = duration_profile(self.story(7), "video", "remote_gpu")
        records = [dict(profile=history, seconds=v, finished_at=STAMP) for v in (380, 420)]
        result = DurationModel(records).estimate(target)
        self.assertEqual(result["seconds"], 400)
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["source"], "similar")
        self.assertEqual(result["confidence"], "low")
        self.assertTrue(result["indicative"])
        self.assertLess(result["low"], result["seconds"])
        self.assertGreater(result["high"], result["seconds"])
        self.assertEqual(DurationModel(records).estimate(target, elapsed=100)["seconds"], 300)
        records.append(dict(profile=target, seconds=500, finished_at=STAMP))
        exact = DurationModel(records).estimate(target)
        self.assertEqual(exact["source"], "comparable")
        self.assertEqual(exact["seconds"], 500)
        self.assertEqual(exact["samples"], 1)

    def test_video_fallback_keeps_compute_contract_and_limits_reference_distance(self):
        recipe = dict(id="ref2v", version="1", workflow_sha256="workflow-a")
        history = duration_profile(self.story(6), "video", "remote_gpu", recipe)
        target = duration_profile(self.story(7), "video", "remote_gpu", recipe)
        model = DurationModel([dict(profile=history, seconds=400, finished_at=STAMP)])
        for field, value in (
            ("lane", "local_gpu"), ("recipe", dict(recipe, workflow_sha256="workflow-b")),
            ("input_mode", "h3"), ("checkpoint", "other-model"), ("version", 2),
            ("settings", dict(target["settings"], duration_seconds=20)),
            ("settings", dict(target["settings"], megapixels=1.8)),
            ("settings", dict(target["settings"], steps=12)),
            ("bunny", dict(target["bunny"], coarse_steps=8)),
            ("roles", ["subject_reference"] * 7),
            ("roles", ["environment_reference"] + ["subject_reference"] * 8),
        ):
            with self.subTest(field=field, value=value):
                self.assertIsNone(model.estimate(dict(target, **{field: value}))["seconds"])
        self.assertIsNone(DurationModel().estimate(target)["seconds"])

    def test_dlss_uses_same_video_format_without_reference_count_partition(self):
        target = duration_profile(self.story(7), "dlss", "local_gpu")
        records = [dict(profile=duration_profile(self.story(n), "dlss", "local_gpu"),
                        seconds=seconds, finished_at=STAMP) for n, seconds in ((3, 150), (6, 160))]
        model = DurationModel(records)
        result = model.estimate(target)
        self.assertEqual(result["seconds"], 155)
        self.assertEqual(result["samples"], 2)
        self.assertTrue(result["indicative"])
        self.assertEqual(result["confidence"], "low")
        for field, value in (
            ("lane", "remote_gpu"), ("dlss_contract", "other-dlss"),
            ("settings", dict(target["settings"], duration_seconds=20)),
            ("settings", dict(target["settings"], megapixels=1.8)),
            ("options", dict(target["options"], target_fps=120)),
        ):
            with self.subTest(field=field):
                self.assertIsNone(model.estimate(dict(target, **{field: value}))["seconds"])

    def test_nearby_history_unblocks_later_story_and_global_forecast_without_mutation(self):
        first, following = self.story(7), self.story(3)
        following["id"] = "following-story"
        state, _, lanes, machine = inputs([first, following])
        adapter, store = FakeWorkflows(), MemoryTimings()
        adapter.monitor_snapshot = machine
        for references in (6, 3):
            past = self.story(references)
            for stage, seconds in dict(plan=20, prompt=10, video=400, dlss=150, social=10, export=5).items():
                store.value["records"].append(dict(
                    profile=duration_profile(past, stage, "export" if stage == "export" else lanes[first["id"]][stage]),
                    seconds=seconds, finished_at=STAMP))
        before = deepcopy(state)
        monitor = FactoryMonitoring(store, clock=lambda: NOW)
        value = monitor.snapshot(adapter, state)
        self.assertGreater(value["remaining_seconds"], 0)
        self.assertIsNotNone(value["low_seconds"])
        self.assertIsNotNone(value["high_seconds"])
        self.assertIsNotNone(value["indicative_reason"])
        for item in (first, following):
            self.assertGreater(value["items"][item["id"]]["remaining_seconds"], 0)
        self.assertEqual(value["items"][first["id"]]["steps"]["video"]["source"], "similar")
        self.assertEqual(value["items"][following["id"]]["steps"]["video"]["source"], "comparable")
        self.assertEqual(state, before)
        self.assertEqual(store.saves, 0)
        self.assertFalse(adapter.calls)


class ForecastTest(unittest.TestCase):
    def test_parallel_machines_dependency_order_and_video_cooldown(self):
        a, b = card("A", final=True), card("B")
        state, estimates, lanes, machine = inputs([a, b])
        result = forecast(state, estimates, lanes, machine, NOW)
        self.assertEqual(result["items"][a["id"]]["remaining_seconds"], 155)
        self.assertEqual(result["items"][b["id"]]["video_start_in"], 130)
        self.assertEqual(result["remaining_seconds"], 285)
        self.assertEqual(state["items"][0]["steps"]["video"]["status"], "pending")

    def test_paused_queue_keeps_active_step_but_no_global_finish(self):
        item = card(final=True)
        item["steps"]["video"]["status"] = "running"
        item["status"] = "active"
        state, estimates, lanes, machine = inputs([item])
        state["paused"] = True
        result = forecast(state, estimates, lanes, machine, NOW)
        self.assertIsNone(result["remaining_seconds"])
        self.assertEqual(result["items"][item["id"]]["steps"]["video"]["finish_in"], 100)
        self.assertIsNone(result["items"][item["id"]]["steps"]["dlss"]["start_in"])

    def test_other_work_and_unknown_duration_do_not_block_independent_lane(self):
        a, b = card("A", final=True), card("B")
        state, estimates, lanes, machine = inputs([a, b])
        machine["machines"]["remote_gpu"]["state"] = "busy"
        result = forecast(state, estimates, lanes, machine, NOW)
        self.assertIsNone(result["remaining_seconds"])
        self.assertEqual(result["items"][b["id"]]["steps"]["prompt"]["finish_in"], 30)
        machine["machines"]["remote_gpu"]["state"] = "idle"
        estimates[a["id"]]["video"].update(seconds=None, low=None, high=None)
        result = forecast(state, estimates, lanes, machine, NOW)
        self.assertEqual(result["items"][b["id"]]["steps"]["prompt"]["finish_in"], 30)
        self.assertIsNone(result["items"][b["id"]]["video_start_in"])

    def test_known_cooling_is_counted_and_indefinite_cooling_is_unknown(self):
        item = card(final=True)
        state, estimates, lanes, machine = inputs([item])
        machine["machines"]["remote_gpu"].update(state="cooling", cooldown_remaining_seconds=60)
        self.assertEqual(forecast(state, estimates, lanes, machine, NOW)["remaining_seconds"], 215)
        machine["machines"]["remote_gpu"]["cooldown_remaining_seconds"] = 0
        self.assertIsNone(forecast(state, estimates, lanes, machine, NOW)["remaining_seconds"])

    def test_stale_machines_never_look_idle(self):
        state, estimates, lanes, machine = inputs([card(final=True)])
        result = forecast(state, estimates, lanes, machine, NOW + 25)
        self.assertTrue(result["stale"])
        self.assertIsNone(result["remaining_seconds"])

    def test_delivered_requires_matching_final_export_and_is_archive_independent(self):
        item = card(final=True)
        for stage in STAGES:
            item["steps"][stage].update(status="succeeded", output={"asset_id": "asset-video"})
        item["status"] = "succeeded"
        item["delivery"] = dict(status="succeeded", key="old-key")
        self.assertFalse(delivered(item))
        item["delivery"]["key"] = delivery_material(item)["key"]
        self.assertTrue(delivered(item))
        state, _, _, _ = inputs([item])
        item["archived_at"] = STAMP
        sync_cycle(state)
        state["items"] = []
        sync_cycle(state)
        self.assertEqual(cycle_counts(state)["total"], 1)
        self.assertEqual(cycle_counts(state)["delivered"], 1)

    def test_unknown_serialized_export_never_leaks_infinity_to_json(self):
        import json
        a, b = card("A"), card("B")
        for item in (a, b):
            item["status"] = "succeeded"
            for step in item["steps"].values():
                step.update(status="succeeded", output={"asset_id": "asset-video"})
        state, estimates, lanes, machine = inputs([a, b])
        estimates[a["id"]]["export"].update(seconds=None, low=None, high=None)
        result = forecast(state, estimates, lanes, machine, NOW)
        self.assertIsNone(result["items"][b["id"]]["steps"]["export"]["start_in"])
        json.dumps(result, allow_nan=False)

    def test_export_started_before_social_finishes_needs_final_publication(self):
        item = card()
        item["status"] = "succeeded"
        for step in item["steps"].values():
            step.update(status="succeeded", output={"asset_id": "asset-video"})
        item["delivery"] = dict(status="copying", key="old-video-only-key")
        state, estimates, lanes, machine = inputs([item])
        estimates[item["id"]]["export"]["reservation"] = dict(seconds=2, low=2, high=2)
        self.assertEqual(forecast(state, estimates, lanes, machine, NOW)["remaining_seconds"], 7)
        item["delivery"]["key"] = delivery_material(item)["key"]
        estimates[item["id"]]["export"].pop("reservation")
        self.assertEqual(forecast(state, estimates, lanes, machine, NOW)["remaining_seconds"], 5)

    def test_export_error_does_not_close_cycle_while_pipeline_is_active(self):
        item = card()
        state, _, _, _ = inputs([item])
        item["status"] = "active"
        item["delivery"] = dict(status="failed")
        sync_cycle(state)
        self.assertEqual(cycle_counts(state)["active"], 1)
        self.assertIsNone(state["production_cycle"]["finished_at"])

    def test_removal_retains_denominator_and_retry_retains_cycle(self):
        a, b = card("A"), card("B")
        state, _, _, _ = inputs([a, b])
        cycle_id = state["production_cycle"]["id"]
        state["items"].remove(a)
        b["status"] = "failed"
        sync_cycle(state)
        self.assertEqual(cycle_counts(state)["total"], 2)
        self.assertEqual(cycle_counts(state)["removed"], 1)
        admit_cycle(state, [b], resume=True)
        b["status"] = "queued"
        sync_cycle(state)
        self.assertEqual(state["production_cycle"]["id"], cycle_id)
        self.assertEqual(cycle_counts(state)["queued"], 1)

class ForecastContinuityTest(unittest.TestCase):
    def setUp(self):
        self.item = card(final=True)
        self.item["status"] = "active"
        self.item["steps"]["video"].update(status="running", started_at=STAMP,
                                          timing=dict(id="attempt-clock", quality="complete"))
        self.state, _, _, machine = inputs([self.item])
        self.adapter = FakeWorkflows()
        self.adapter.monitor_snapshot = machine
        self.now = NOW
        self.store = MemoryTimings()
        self.monitor = FactoryMonitoring(self.store, clock=lambda: self.now)
        self.store.value["records"] = [
            dict(profile=self.monitor.profile(self.adapter, self.item, stage),
                 seconds=seconds, finished_at=STAMP)
            for stage, seconds in dict(video=100, dlss=40, social=10, export=5).items()]
        self.monitor = FactoryMonitoring(self.store, clock=lambda: self.now)

    def snapshot(self, advance=0, **kwargs):
        self.now += advance
        self.adapter.monitor_snapshot["observed_at"] = datetime.fromtimestamp(self.now, UTC).isoformat()
        return self.monitor.snapshot(self.adapter, self.state, **kwargs)

    def test_partial_clock_keeps_stage_and_batch_estimates(self):
        self.item["steps"]["video"]["timing"]["quality"] = "recovered"
        before = deepcopy(self.state)
        value = self.snapshot(40)
        step = value["items"][self.item["id"]]["steps"]["video"]
        self.assertEqual(step["seconds"], 60)
        self.assertEqual(step["confidence"], "low")
        self.assertIsNotNone(value["remaining_seconds"])
        self.assertIn("partiel", value["indicative_reason"])
        self.assertEqual(self.state, before)
        self.assertEqual(self.store.saves, 0)
        # A new monitor can reconstruct this forecast from the durable history.
        self.monitor = FactoryMonitoring(self.store, clock=lambda: self.now)
        self.assertEqual(self.snapshot()["remaining_seconds"], value["remaining_seconds"])

    def test_overrun_remains_numeric_for_every_dependent_video(self):
        second = card("B", final=True)
        self.state["items"].append(second)
        admit_cycle(self.state, [second])
        sync_cycle(self.state)
        value = self.snapshot(150)
        self.assertIsNotNone(value["items"][second["id"]]["remaining_seconds"])
        self.assertGreater(value["remaining_seconds"], 0)
        self.assertIn("dépassée", value["indicative_reason"])

    def test_thermal_wait_freezes_known_budget_then_live_calculation_resumes(self):
        first = self.snapshot()
        machine = self.adapter.monitor_snapshot["machines"]["remote_gpu"]
        machine.update(state="busy", active={"stage": "Attente thermique"})
        for _ in range(2):
            value = self.snapshot(10)
            self.assertTrue(value["retained"])
            self.assertEqual(value["remaining_seconds"], first["remaining_seconds"])
            step = value["items"][self.item["id"]]["steps"]["video"]
            self.assertTrue(step["retained"])
            self.assertEqual(step["seconds"], 100)
        machine.update(state="busy", active={})
        resumed = self.snapshot()
        self.assertFalse(resumed["retained"])
        self.assertEqual(resumed["items"][self.item["id"]]["steps"]["video"]["seconds"], 80)

    def test_pause_and_stale_telemetry_keep_reference_without_new_finish(self):
        first = self.snapshot()
        self.state["paused"] = True
        paused = self.snapshot(10)
        self.assertEqual(paused["status"], "paused")
        self.assertTrue(paused["retained"])
        self.assertEqual(paused["remaining_seconds"], first["remaining_seconds"])
        self.state["paused"] = False
        self.now += 30
        stale = self.monitor.snapshot(self.adapter, self.state)
        self.assertTrue(stale["stale"])
        self.assertTrue(stale["retained"])
        self.assertEqual(stale["remaining_seconds"], first["remaining_seconds"])

    def test_no_reference_is_invented_and_preview_does_not_seed_live_cache(self):
        preview = self.snapshot(target_ids=[self.item["id"]])
        self.assertIsNotNone(preview["remaining_seconds"])
        self.state["paused"] = True
        value = self.snapshot()
        self.assertIsNone(value["remaining_seconds"])
        self.assertFalse(value["retained"])

    def test_old_forecast_is_invalidated_for_new_cycle_retry_configuration_or_queue(self):
        for change in ("cycle", "retry", "configuration", "queue"):
            with self.subTest(change=change):
                self.setUp()
                self.snapshot()
                self.state["paused"] = True
                if change == "cycle":
                    self.state["production_cycle"]["id"] = "new-cycle"
                elif change == "retry":
                    self.item["steps"]["video"]["timing"]["id"] = "new-attempt-clock"
                elif change == "configuration":
                    self.item["launch_snapshot"]["render"]["settings"]["duration_seconds"] += 1
                else:
                    second = card("new-video")
                    self.state["items"].append(second)
                    admit_cycle(self.state, [second])
                    sync_cycle(self.state)
                self.assertIsNone(self.snapshot()["remaining_seconds"])

    def test_delivered_video_cannot_keep_an_old_remaining_budget(self):
        self.snapshot()
        for step in self.item["steps"].values():
            step.update(status="succeeded", output={"asset_id": "asset-video"})
        self.item["status"] = "succeeded"
        self.item["delivery"] = dict(status="succeeded", key=delivery_material(self.item)["key"])
        sync_cycle(self.state)
        value = self.snapshot()
        self.assertEqual(value["remaining_seconds"], 0)
        self.assertEqual(value["status"], "complete")
        self.assertFalse(value["retained"])


class MonitoringServiceTest(unittest.TestCase):
    def test_preview_is_read_only_respects_revision_and_keeps_pause(self):
        store, adapter = MemoryStore(), FakeWorkflows()
        adapter.monitor_snapshot = dict(observed_at=STAMP, settings={},
            machines={lane: dict(state="idle") for lane in ("local_gpu", "remote_gpu")})
        monitor = FactoryMonitoring(MemoryTimings(), clock=lambda: NOW)
        service = VideoFactoryService(store=store, adapter=adapter, monitoring=monitor)
        item = card(final=True)
        result = service.receive([dict(name=item["name"], config=item["config"], source=item["source"])])
        identity = result["ids"][0]
        service.action("pause")
        before = deepcopy(store.value)
        revisions = {identity: before["items"][0]["revision"]}
        forecast_value = service.estimate([identity], revisions)
        self.assertTrue(forecast_value["conditional_on_resume"])
        self.assertEqual(store.value, before)
        self.assertFalse(adapter.calls)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from panelforge.features.lab.video_factory_web import video_factory_router
        app = FastAPI()
        app.include_router(video_factory_router(service, validate_image=lambda content: "image/png"))
        with TestClient(app) as client:
            response = client.post("/api/video-factory/estimate", json=dict(ids=[identity], revisions=revisions))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["conditional_on_resume"])
            self.assertEqual(client.post("/api/video-factory/estimate", json=dict(ids=[identity], revisions={identity: -1})).status_code, 409)
        self.assertEqual(store.value, before)
        self.assertFalse(adapter.calls)
        with self.assertRaises(FactoryConflict):
            service.estimate([identity], {identity: -1})
