"""DLSS progress and server copies: temporary files and fake gateways only."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.dlss import DlssService
from panelforge.domain.dlss import DlssSettings
from panelforge.features.lab.dlss_web import register_dlss_routes
from panelforge.infrastructure.dlss_progress import progress_update
from panelforge.infrastructure.dlss_video_exports import DlssVideoExporter
from panelforge.infrastructure.storage import LocalAssetStore
from panelforge.infrastructure.storage.dlss_jobs import LocalDlssJobs


ROOT = Path(__file__).resolve().parents[1]
STAGES = json.loads((ROOT / "workflows/video.upscale/dlss-smooth/0.1.0/manifest.json").read_text(encoding="utf-8"))["progress_stages"]


def event(kind="progress", *, execution="execution-a", stage=0, **values):
    return json.dumps({"type": kind, "data": {"prompt_id": execution, "node": STAGES[stage]["node"], **values}})


class DlssProgressTest(unittest.TestCase):
    def test_progress_is_scoped_and_not_an_invented_global_percentage(self):
        value = progress_update(event(value=250, max=1000), "execution-a", STAGES)
        self.assertEqual(value["percent"], 25)
        self.assertEqual(value["stage"], "upscale")
        value = progress_update(event(stage=1, value=10, max=100), "execution-a", STAGES)
        self.assertEqual(value["percent"], 10)
        self.assertEqual(value["stage"], "interpolation")
        self.assertIsNone(progress_update(event(execution="other", value=10, max=100), "execution-a", STAGES))
        for invalid in (b"preview image", "not JSON", "[]", '{}', '{"data":{"value":42}}'):
            self.assertIsNone(progress_update(invalid, "execution-a", STAGES))
        for values in ({}, {"value": 1, "max": 0}, {"value": float("nan"), "max": 100}, {"value": True, "max": 100}):
            self.assertIsNone(progress_update(event(**values), "execution-a", STAGES)["percent"])

    def test_snapshot_uses_latest_active_stage_and_ignores_pending_nodes(self):
        nodes = {STAGES[0]["node"]: {"state": "finished", "value": 1000, "max": 1000},
                 STAGES[1]["node"]: {"state": "running", "value": 400, "max": 1000},
                 STAGES[2]["node"]: {"state": "pending", "value": 0, "max": 1000}}
        value = progress_update(event("progress_state", nodes=nodes), "execution-a", STAGES)
        self.assertEqual((value["stage"], value["percent"]), ("interpolation", 40))
        value = progress_update(event("executing", stage=2), "execution-a", STAGES)
        self.assertEqual(value["stage"], "saving")
        self.assertIsNone(value["percent"])


class DlssExportTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.jobs = LocalDlssJobs(self.root)
        self.assets = LocalAssetStore(self.root)
        self.exporter = DlssVideoExporter(self.root / "video" / "Upscale")
        self.service = DlssService(jobs=self.jobs, runtime=Mock(), comfy=Mock(), assets=self.assets,
            media=Mock(), workflows={}, candidates=Mock(), video_exporter=self.exporter)
        self.service.wake = Mock()
        self.service.wake_exports = Mock()
        output = self.assets.create(b"exact finished video", "video/mp4")
        report = self.assets.create(b'{"diagnostic":"exact report"}', "application/json")
        self.job = {"schema_version": 1, "job_id": "dlss-" + "a" * 32, "status": "running", "execution_id": "execution-a",
            "created_at": datetime.now(timezone.utc).isoformat(), "settings": asdict(DlssSettings(size="1.724", interpolate=True)),
            "snapshot": {"owner": "h3", "owner_id": "project", "root_attempt_id": "original", "media_type": "video/mp4"},
            "output_asset_id": output.asset_id, "report_asset_id": report.asset_id}
        self.jobs.save(self.job)

    def finish(self):
        self.service._succeeded(self.job, "candidate")
        return self.jobs.get(self.job["job_id"])

    def test_persisted_progress_is_monotonic_and_survives_stale_worker_saves(self):
        def record(**kwargs):
            value = progress_update(event(**kwargs), "execution-a", STAGES)
            self.service._record_progress(self.job["job_id"], "execution-a", value)
        record(value=60, max=100)
        record(value=20, max=100)
        self.service._save(self.job, error=None)
        self.assertEqual(self.jobs.get(self.job["job_id"])["progress"]["percent"], 60)
        record(stage=1, value=10, max=100)
        record(value=100, max=100)
        saved = self.jobs.get(self.job["job_id"])
        self.assertEqual((saved["progress"]["stage"], saved["progress"]["percent"]), ("interpolation", 10))
        update = progress_update(event(stage=1, value=100, max=100), "execution-a", STAGES)
        self.service._record_progress(self.job["job_id"], "other-execution", update)
        self.assertEqual(self.jobs.get(self.job["job_id"]), saved)
        self.service._save(self.job, status="receiving", progress=None)
        record(stage=1, value=100, max=100)
        self.assertIsNone(self.jobs.get(self.job["job_id"])["progress"])

    def test_failed_share_preserves_candidate_and_retry_copies_without_rendering(self):
        job = self.finish()
        target = Path(job["video_export"]["path"])
        self.assertEqual(target.parent.name, datetime.now().astimezone().date().isoformat())
        self.service._drain_exports()  # Parent share deliberately unavailable.
        failed = self.jobs.get(job["job_id"])
        self.assertEqual(failed["status"], "succeeded")
        self.assertEqual(failed["candidate_id"], "candidate")
        self.assertEqual(failed["video_export"]["status"], "failed")
        self.assertEqual(self.assets.read_bytes(failed["output_asset_id"]), b"exact finished video")
        target.parent.parent.parent.mkdir()
        app = FastAPI()
        register_dlss_routes(app, self.service)
        with TestClient(app) as client:
            response = client.post(f"/api/dlss/jobs/{job['job_id']}/export")
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["video_export"]["path"], str(target))
            self.service._drain_exports()
            public = client.get("/api/dlss/jobs").json()["jobs"][0]
            self.assertEqual(public["video_export"]["status"], "succeeded")
            self.assertIsNotNone(public["finished_at"])
        self.assertEqual(target.read_bytes(), b"exact finished video")
        self.assertEqual(target.with_suffix(".json").read_bytes(), b'{"diagnostic":"exact report"}')
        self.service.comfy.submit_workflow.assert_not_called()
        self.service.runtime.ensure_ready.assert_not_called()
        self.service.candidates.attach.assert_not_called()
        self.service.wake.assert_not_called()

    def test_export_is_idempotent_after_partial_copy_and_keeps_its_saved_date(self):
        self.finish()
        day = "2026-09-08"
        target = self.exporter.target(self.job["job_id"], day)
        export = dict(self.job["video_export"], date=day, path=str(target))
        self.service._save(self.job, video_export=export)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"exact finished video")  # Crash after video copy, before report copy.
        timestamp = target.stat().st_mtime_ns
        self.service._drain_exports()
        self.assertEqual(target.stat().st_mtime_ns, timestamp)
        self.assertEqual(self.jobs.get(self.job["job_id"])["video_export"]["path"], str(target))
        self.assertTrue(target.with_suffix(".json").is_file())
        self.exporter.export(self.job, b"exact finished video", b'{"diagnostic":"exact report"}')
        with self.assertRaises(ValueError):
            self.exporter.export(self.job, b"different video", b"report")
        self.assertEqual(target.read_bytes(), b"exact finished video")
        with self.assertRaises(ValueError):
            self.exporter.target("../escape", day)

    def test_slow_copy_does_not_hold_the_service_or_render_worker_lock(self):
        self.finish()
        entered, release = Event(), Event()

        def slow_copy(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test failed to release copy")

        self.service.video_exporter = Mock(export=slow_copy)
        worker = Thread(target=self.service._drain_exports)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            acquired = self.service._lock.acquire(timeout=1)
            self.assertTrue(acquired, "copy blocks API requests")
            if acquired:
                self.service._lock.release()
            with self.jobs.lease("worker"), self.jobs.lease("requests"):
                self.assertEqual(self.jobs.get(self.job["job_id"])["status"], "succeeded")
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
