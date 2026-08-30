import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.infrastructure.production_thermal import (
    CombinedProductionThermalMonitor,
    CrystoolsRemoteGpuMonitor,
)


class FakeConnection:
    def __init__(self, messages):
        self.messages = iter(messages)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def recv(self, timeout):
        return next(self.messages)


class LocalMonitor:
    def get_stats(self):
        return type("Stats", (), {"temperature_c": 47.0})()


class ProductionThermalTest(unittest.TestCase):
    def test_crystools_monitor_ignores_other_websocket_events(self):
        clock = iter((0.0, 0.1, 0.2, 0.3))
        monitor = CrystoolsRemoteGpuMonitor(
            "ws://gpu.test/ws",
            timeout=2,
            cache_seconds=0,
            monotonic=lambda: next(clock),
            connector=lambda _url, _timeout: FakeConnection((
                json.dumps({"type": "progress", "data": {}}),
                json.dumps({
                    "type": "crystools.monitor",
                    "data": {"gpus": [{"gpu_temperature": 63}]},
                }),
            )),
        )

        self.assertEqual(monitor.get_temperature(), 63)

    def test_combined_monitor_keeps_partial_telemetry(self):
        remote = type("Remote", (), {
            "get_temperature": lambda self: (_ for _ in ()).throw(OSError("offline")),
        })()
        snapshot = CombinedProductionThermalMonitor(
            local=LocalMonitor(),
            remote=remote,
        ).snapshot()

        self.assertEqual(snapshot.local_temperature_c, 47)
        self.assertIsNone(snapshot.remote_temperature_c)
        self.assertIn("offline", snapshot.remote_error)


if __name__ == "__main__":
    unittest.main()
