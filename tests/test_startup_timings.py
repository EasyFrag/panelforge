"""User-run startup observations; fake services, no real workers or requests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.startup_timings import StartupTimings, trace_startup_build


class StartupTimingsTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)

    def test_one_bounded_record_and_rotation(self):
        trace = StartupTimings(self.workspace)
        trace.path.parent.mkdir(parents=True)
        trace.path.write_text("x" * (256 * 1024), encoding="utf-8")
        for number in range(80):
            trace.mark("build." + str(number))
        trace.finish("ready")
        trace.finish("ready")
        records = trace.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(records), 1)
        record = json.loads(records[0])
        self.assertEqual(len(record["phases"]), 64)
        self.assertEqual(record["scope"], "build_app_and_lifespan")
        self.assertTrue(all(p["duration_ms"] >= 0 and p["cpu_ms"] >= 0 for p in record["phases"]))
        self.assertEqual(trace.path.with_name(trace.path.name + ".1").stat().st_size, 256 * 1024)

    def test_observation_write_failure_cannot_block_startup(self):
        trace = StartupTimings(self.workspace)
        with patch.object(Path, "mkdir", side_effect=OSError("read only")):
            trace.finish("ready")
        self.assertTrue(trace.finished)

    def test_build_failure_is_reported_and_original_error_propagates(self):
        failure = RuntimeError("fixture")

        @trace_startup_build
        def build(args, *, startup):
            startup.mark("build.fixture")
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            build(SimpleNamespace(workspace=self.workspace))
        self.assertIs(caught.exception, failure)
        record = json.loads((self.workspace / "system/startup-timings.jsonl").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual([p["name"] for p in record["phases"]], ["build.fixture", "build.interrupted"])

    def test_service_order_and_shutdown_remain_sequential(self):
        calls = []

        def fake(name, start, stop):
            return SimpleNamespace(**{start: lambda: calls.append(name), stop: lambda: calls.append("stop." + name)})

        trace = StartupTimings(self.workspace)
        app = create_app(SimpleNamespace(), startup_timings=trace,
                         machine_work=fake("thermal", "start_temperature_sampling", "stop_temperature_sampling"),
                         krea2_assisted=fake("krea2", "start_render_worker", "stop_render_worker"),
                         qwen_edit=fake("qwen", "start_worker", "stop_worker"),
                         video_factory=fake("factory", "start", "stop"))
        with TestClient(app):
            self.assertEqual(calls, ["thermal", "krea2", "qwen", "factory"])
            record = json.loads(trace.path.read_text())
            self.assertEqual(record["status"], "ready")
            self.assertEqual([p["name"] for p in record["phases"]], ["startup." + n for n in calls])
        self.assertEqual(calls[4:], ["stop.factory", "stop.thermal", "stop.qwen", "stop.krea2"])

    def test_failed_service_phase_is_retained(self):
        trace = StartupTimings(self.workspace)
        with self.assertRaises(ValueError):
            with trace.phase("startup.fixture"):
                raise ValueError("fixture")
        trace.finish("failed")
        self.assertEqual(json.loads(trace.path.read_text())["phases"][0]["status"], "failed")
