"""Passive timing contracts; all transports and GPU work are simulated."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from threading import Barrier, Event, RLock
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panelforge.application.image_timings import (
    MAX_PHASES, annotate, image_trace, observe_history, phase, queue_age, timed_lease,
    timed_lock,
)
from panelforge.infrastructure.comfy.client import ComfyHttpClient
from panelforge.infrastructure.storage.image_timings import LocalImageTimings


def trace(sink, attempt="attempt-test"):
    return image_trace(sink, engine="krea2", project_id="project-test", attempt_id=attempt)


class ImageTimingsTest(unittest.TestCase):
    def test_lock_wait_is_distinct_from_hold_and_cpu_time(self):
        clock, cpu_clock, records, events = [0.0], [0.0], [], []

        class Lock:
            def __enter__(self):
                events.append("acquire")
                clock[0] += 2

            def __exit__(self, *args):
                events.append("release")

        lock = Lock()

        def sink(record):
            events.append("write")
            records.append(record)

        with patch("panelforge.application.image_timings.time.perf_counter", side_effect=lambda: clock[0]), \
                patch("panelforge.application.image_timings.time.thread_time", side_effect=lambda: cpu_clock[0]):
            with timed_lock(lock, "krea2.service.render_queue", sink=sink):
                clock[0] += 3
                cpu_clock[0] += 0.5
        self.assertEqual(events, ["acquire", "release", "write"])
        record = records[0]
        wait, held = record["phases"]
        self.assertEqual((wait["duration_ms"], held["duration_ms"]), (2000, 3000))
        self.assertEqual((wait["cpu_ms"], held["cpu_ms"]), (0, 500))
        self.assertEqual(wait["lock_id"], held["lock_id"])
        self.assertEqual(record["kind"], "operation")
        self.assertEqual(record["operation"], "krea2.service.render_queue")
        self.assertEqual(record["monotonic_start_ms"], 0)

    def test_fast_operations_are_filtered_but_errors_survive_and_unlock(self):
        records, lock = [], RLock()
        failure = ValueError("private project name")
        with patch("panelforge.application.image_timings.time.perf_counter", return_value=0):
            with timed_lock(lock, "quick", sink=records.append):
                pass
            self.assertEqual(records, [])
            with self.assertRaises(ValueError) as caught:
                with timed_lock(lock, "failed", sink=records.append):
                    raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "raised")
        self.assertNotIn("private project name", json.dumps(records))
        # Acquire from another thread to detect a leaked recursive acquisition.
        def acquire_after_failure():
            acquired = lock.acquire(timeout=1)
            if acquired:
                lock.release()
            return acquired
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertTrue(pool.submit(acquire_after_failure).result(timeout=3))

    def test_reentrant_locks_reuse_trace_and_write_only_after_outer_release(self):
        clock, records, events, lock = [0.0], [], [], RLock()

        def sink(record):
            records.append(record)
            events.append("write")
            raise OSError("diagnostic sink unavailable")

        with patch("panelforge.application.image_timings.time.perf_counter", side_effect=lambda: clock[0]):
            with timed_lock(lock, "outer", sink=sink):
                with timed_lock(lock, "inner", sink=sink):
                    clock[0] += 1
                self.assertEqual(records, [])
                events.append("body")
        self.assertEqual(events, ["body", "write"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["operation"], "outer")
        self.assertEqual(len(records[0]["phases"]), 4)

    def test_worker_keeps_lock_phases_without_extra_operation_records(self):
        records = []
        with trace(records.append):
            with timed_lock(RLock(), "worker", sink=records.append):
                with phase("projects.read", aggregate=True, cpu=True) as metrics:
                    metrics.update(bytes=20, projects=1, prompt="private")
                with phase("projects.read", aggregate=True, cpu=True) as metrics:
                    metrics.update(bytes=30, projects=2)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "image")
        group = records[0]["aggregates"]["projects.read"]
        self.assertEqual((group["bytes"], group["projects"]), (50, 3))
        self.assertIn("cpu_ms", group)
        self.assertNotIn("private", json.dumps(records))

    def test_disabled_lock_tracing_does_not_read_clocks(self):
        with patch("panelforge.application.image_timings.time.perf_counter", side_effect=AssertionError), \
                patch("panelforge.application.image_timings.time.thread_time", side_effect=AssertionError):
            with timed_lock(RLock(), "disabled"):
                with phase("disabled", cpu=True):
                    pass

    def test_contending_threads_can_be_correlated_on_the_same_lock(self):
        records, clock = [], [0.0]
        held, waiting = Event(), Event()

        class Lock:
            def __init__(self):
                self.inner = RLock()

            def __enter__(self):
                if held.is_set():
                    waiting.set()
                self.inner.acquire()

            def __exit__(self, *args):
                self.inner.release()

        lock = Lock()

        def holder():
            with timed_lock(lock, "queue_poll", sink=records.append):
                held.set()
                if not waiting.wait(timeout=5):
                    raise TimeoutError("waiter did not enter")
                clock[0] = 2

        def worker():
            if not held.wait(timeout=5):
                raise TimeoutError("holder did not enter")
            with trace(records.append):
                with timed_lock(lock, "worker", sink=records.append):
                    clock[0] += 1

        with patch("panelforge.application.image_timings.time.perf_counter", side_effect=lambda: clock[0]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(holder)
                second = pool.submit(worker)
                first.result(timeout=10)
                second.result(timeout=10)
        self.assertEqual(len(records), 2)
        poll = next(r for r in records if r["kind"] == "operation")
        render = next(r for r in records if r["kind"] == "image")
        hold_phase = next(p for p in poll["phases"] if p["name"] == "queue_poll.lock_held")
        wait_phase = next(p for p in render["phases"] if p["name"] == "worker.lock_wait")
        self.assertEqual(wait_phase["duration_ms"], 2000)
        self.assertEqual(hold_phase["duration_ms"], 2000)
        self.assertEqual(wait_phase["lock_id"], hold_phase["lock_id"])
        self.assertNotEqual(render["thread_id"], poll["thread_id"])
        self.assertEqual(render["monotonic_start_ms"] + wait_phase["start_ms"],
                         poll["monotonic_start_ms"] + hold_phase["start_ms"])

    def test_sink_runs_after_resource_release_and_cannot_fail_the_work(self):
        events = []
        records = []

        @contextmanager
        def lease():
            events.append("acquire")
            try:
                yield
            finally:
                events.append("release")

        def broken_sink(record):
            events.append("write")
            records.append(record)
            raise OSError("diagnostic disk full")

        with trace(broken_sink):
            with timed_lease(lease()):
                events.append("work")
                annotate(status="succeeded")
        self.assertEqual(events, ["acquire", "work", "release", "write"])
        self.assertEqual(records[0]["status"], "succeeded")

    def test_original_exception_survives_a_broken_sink_without_logging_its_message(self):
        records = []
        failure = ValueError("private prompt or path")

        def sink(record):
            records.append(record)
            raise OSError("disk unavailable")

        with self.assertRaises(ValueError) as caught:
            with trace(sink):
                with phase("catalog.validate"):
                    raise failure
        self.assertIs(caught.exception, failure)
        self.assertNotIn("private prompt", json.dumps(records))
        self.assertEqual(records[0]["phases"][0]["error_type"], "ValueError")

    def test_repeated_polls_are_aggregated_and_phase_memory_is_bounded(self):
        records = []
        with trace(records.append):
            for _ in range(1000):
                with phase("comfy.history", aggregate=True):
                    pass
            for index in range(MAX_PHASES + 3):
                with phase("bounded"):
                    pass
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]["phases"]), MAX_PHASES)
        self.assertEqual(records[0]["dropped_phases"], 3)
        self.assertEqual(records[0]["aggregates"]["comfy.history"]["count"], 1000)

    def test_contexts_are_isolated_between_workers_and_disabled_scopes(self):
        records = []
        barrier = Barrier(2)

        def worker(identity):
            with trace(records.append, identity):
                barrier.wait(timeout=5)
                annotate(execution_id=identity)
                with trace(None, "disabled"):
                    with phase("must-not-leak"):
                        annotate(execution_id="disabled")
                with phase("own-work"):
                    pass

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker, ["first", "second"]))
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["attempt_id"], record["execution_id"])
            self.assertEqual([p["name"] for p in record["phases"]], ["own-work"])
        self.assertEqual(len({r["thread_id"] for r in records}), 2)
        self.assertEqual(len({r["process_id"] for r in records}), 1)

    def test_download_response_and_transfer_are_separate_without_extra_requests(self):
        clock = [0.0]
        records, requests = [], []

        class Response(BytesIO):
            def read(self, *args):
                clock[0] += 3
                return super().read(*args)

        def opener(request, timeout):
            requests.append(request)
            clock[0] += 2
            return Response(b"image-bytes")

        client = ComfyHttpClient("http://private-server:8188", client_id="test", opener=opener)
        with patch("panelforge.application.image_timings.time.perf_counter", side_effect=lambda: clock[0]):
            with trace(records.append):
                result = client.download_output(filename="private-name.png")
        self.assertEqual(result, b"image-bytes")
        self.assertEqual(len(requests), 1)
        phases = {p["name"]: p for p in records[0]["phases"]}
        self.assertEqual(phases["download.response"]["duration_ms"], 2000)
        self.assertEqual(phases["download.body"]["duration_ms"], 3000)
        self.assertEqual(phases["download.body"]["bytes"], len(result))
        for secret in ("private-server", "private-name", "image-bytes"):
            self.assertNotIn(secret, json.dumps(records))

    def test_server_duration_uses_only_server_timestamps_and_tolerates_bad_history(self):
        records = []
        with trace(records.append):
            observe_history({"id": {"status": {"messages": [
                ["execution_start", {"timestamp": 1000}],
                ["execution_success", {"timestamp": 16250}],
            ]}}}, "id")
            for bad in (None, [], {"id": None}, {"id": {"status": {"messages": [None]}}}):
                observe_history(bad, "id")
        self.assertEqual(records[0]["server_execution_ms"], 15250)

    def test_history_polls_do_not_add_requests_or_unbounded_phase_rows(self):
        calls, records = [], []

        def opener(request, timeout):
            calls.append(request)
            return BytesIO(b'{}')

        client = ComfyHttpClient("http://fake:8188", client_id="test", opener=opener)
        with trace(records.append):
            for _ in range(10):
                self.assertEqual(client.get_history("execution-test"), {})
        self.assertEqual(len(calls), 10)
        self.assertEqual(records[0]["phases"], [])
        self.assertEqual(records[0]["aggregates"]["comfy.history"]["count"], 10)

    def test_queue_age_distinguishes_resumption_from_fresh_wait(self):
        records = []
        with patch("panelforge.application.image_timings.time.time", return_value=100):
            with trace(records.append):
                queue_age(90)
            with trace(records.append):
                queue_age(90, resumed=True)
        self.assertEqual(records[0]["queue_wait_ms"], 10000)
        self.assertNotIn("queue_wait_ms", records[1])
        self.assertEqual(records[1]["queue_age_ms"], 10000)

    def test_journal_rotation_and_unavailable_directory(self):
        with tempfile.TemporaryDirectory() as root:
            sink = LocalImageTimings(root, max_bytes=1024, backups=2)
            try:
                for _ in range(12):
                    with trace(sink):
                        with phase("work"):
                            pass
            finally:
                sink.close()
            files = list((Path(root) / "system").glob("image-timings.jsonl*"))
            self.assertEqual(len(files), 3)
            self.assertTrue(all(p.stat().st_size <= 1024 for p in files))
            for path in files:
                for line in path.read_text(encoding="utf-8").splitlines():
                    self.assertEqual(json.loads(line)["attempt_id"], "attempt-test")
            blocked = Path(root) / "blocked"
            blocked.write_text("file, not directory", encoding="utf-8")
            unavailable = LocalImageTimings(blocked)
            with trace(unavailable):
                annotate(status="succeeded")


if __name__ == "__main__":
    unittest.main()
