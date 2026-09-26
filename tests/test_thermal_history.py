from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
import unittest

from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.domain.production import (
    ComputeResource,
    ProductionWorkload,
    ThermalSnapshot,
)
from panelforge.infrastructure.storage.thermal_history import LocalThermalHistoryStore


class LocalThermalHistoryStoreTest(unittest.TestCase):
    def test_history_survives_instances_prunes_old_samples_and_recovers_open_events(self):
        now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
        with TemporaryDirectory() as directory:
            store = LocalThermalHistoryStore(directory)
            store.record_sample(
                now - timedelta(hours=25),
                local_temperature_c=40,
                remote_temperature_c=50,
            )
            store.record_sample(
                now - timedelta(minutes=1),
                local_temperature_c=72,
                remote_temperature_c=81,
            )
            store.record_event_start(
                "event-complete",
                resource=ComputeResource.REMOTE_GPU,
                workload=ProductionWorkload.VIDEO_RENDER,
                operation="H3 scène 1",
                started_at=now - timedelta(minutes=10),
            )
            store.record_event_finish(
                "event-complete",
                finished_at=now - timedelta(minutes=4),
                status="completed",
                peak_temperature_c=84,
            )
            store.record_event_start(
                "event-open",
                resource=ComputeResource.LOCAL_GPU,
                workload=ProductionWorkload.DLSS,
                operation="DLSS vidéo",
                started_at=now - timedelta(minutes=3),
            )
            with store.path.open("a", encoding="utf-8") as stream:
                stream.write('{"schema_version":1,"type":"sample"')

            restored = LocalThermalHistoryStore(directory)
            restored.recover_open_events(now)
            history = restored.load(since=now - timedelta(hours=24), until=now)

            self.assertEqual(len(history["samples"]), 1)
            self.assertEqual(history["samples"][0]["local_gpu"], 72.0)
            self.assertEqual(history["samples"][0]["remote_gpu"], 81.0)
            events = {value["id"]: value for value in history["events"]}
            self.assertEqual(events["event-complete"]["status"], "completed")
            self.assertEqual(events["event-complete"]["peak_temperature_c"], 84.0)
            self.assertEqual(events["event-open"]["status"], "interrupted")

    def test_coordinator_exposes_two_persistent_series_and_typed_markers(self):
        current = [datetime(2026, 9, 25, 12, 0, 1, tzinfo=UTC)]
        monotonic = [0.0]
        with TemporaryDirectory() as directory:
            coordinator = MachineWorkCoordinator(
                thermal_history_store=LocalThermalHistoryStore(directory),
                now=lambda: current[0],
                monotonic=lambda: monotonic[0],
                monitor_interval=.01,
            )
            coordinator._record_temperature_snapshot(
                ThermalSnapshot(local_temperature_c=60, remote_temperature_c=50),
                monotonic[0],
            )
            current[0] = current[0].replace(second=8)
            monotonic[0] = 7
            coordinator._record_temperature_snapshot(
                ThermalSnapshot(local_temperature_c=75, remote_temperature_c=55),
                monotonic[0],
            )
            current[0] = current[0].replace(second=16)
            monotonic[0] = 15
            coordinator._record_temperature_snapshot(
                ThermalSnapshot(local_temperature_c=65, remote_temperature_c=52),
                monotonic[0],
            )
            with coordinator.lease(
                "prompt-1",
                ComputeResource.LOCAL_GPU,
                ProductionWorkload.LLM,
                "Rédaction du synopsis",
            ):
                pass

            history = coordinator.thermal_history()

            self.assertTrue(history["persistent"])
            self.assertEqual(history["window_seconds"], 86_400)
            self.assertEqual(
                [value["max_temperature_c"] for value in history["series"]["local_gpu"]],
                [75.0, 65.0],
            )
            self.assertEqual(
                [value["max_temperature_c"] for value in history["series"]["remote_gpu"]],
                [55.0, 52.0],
            )
            self.assertEqual(history["events"]["local_gpu"][0]["marker"], "P")
            self.assertEqual(history["events"]["local_gpu"][0]["status"], "completed")
            self.assertEqual(history["events"]["local_gpu"][0]["operation"], "Rédaction du synopsis")


if __name__ == "__main__":
    unittest.main()
