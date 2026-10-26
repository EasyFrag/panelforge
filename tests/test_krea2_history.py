"""User-run history regressions: local temporary stores, no model or renderer."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.features.lab.krea2_assisted_web import krea2_assisted_router
from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore
from tests.test_krea2_assisted_branches import fixture


class Krea2HistoryTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = LocalKrea2AssistedProjectStore(self.root)

    def test_startup_populates_summaries_during_existing_recovery_and_warm_reads_do_no_io(self):
        for index in range(40):
            self.store.create(replace(fixture(), project_id=f"project-{index}"))
        restarted = LocalKrea2AssistedProjectStore(self.root)
        original = Path.read_text
        reads = []

        def read(path, *args, **kwargs):
            reads.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            self.assertEqual(restarted.pending_renders(), ())
        self.assertEqual(len(reads), 40)
        with patch.object(Path, "read_text", side_effect=AssertionError("reread")), \
                patch.object(Path, "stat", side_effect=AssertionError("restat")), \
                patch.object(Path, "iterdir", side_effect=AssertionError("rescan")):
            for _ in range(4):
                rows = restarted.summaries(30)
        self.assertEqual(len(rows), 30)
        encoded = json.dumps([asdict(row) for row in rows])
        self.assertNotIn("EGG_FUTURE", encoded)
        self.assertNotIn("MANUAL_EDIT", encoded)
        self.assertLess(len(encoded), 14000)

    def test_rows_follow_branches_feedback_and_new_results_without_mutating_previous_rows(self):
        project = self.store.create(fixture())
        first = self.store.summaries()[0]
        self.assertEqual((first.turn_count, first.render_count, first.preview_asset_id), (4, 1, "asset-result"))
        with self.assertRaises(FrozenInstanceError):
            first.name = "invalid"
        fork = project.branch_from_attempt("image-1", "child")
        self.store.save(replace(fork, name="Child"))
        second = self.store.summaries()[0]
        self.assertEqual((second.name, second.turn_count), ("Child", 2))
        self.assertEqual(first.turn_count, 4)
        next_attempt = replace(fork.attempts[0], attempt_id="image-2", index=2, output_asset_id="new-asset")
        changed = fork.add_attempt(next_attempt).use_feedback("image-2")
        self.store.save(changed)
        latest = self.store.summaries()[0]
        self.assertEqual((latest.render_count, latest.attempt_count, latest.last_status, latest.preview_asset_id),
                         (2, 2, "succeeded", "new-asset"))
        restarted = LocalKrea2AssistedProjectStore(self.root)
        restarted.pending_renders()
        self.assertEqual(restarted.summaries(), self.store.summaries())

    def test_cold_limited_history_does_not_load_unselected_corrupt_project(self):
        old = self.store.create(replace(fixture(), project_id="old"))
        path = self.root / "krea2_assisted" / old.project_id / "project.json"
        path.write_text("broken", encoding="utf-8")
        os.utime(path, (1, 1))
        self.store.create(replace(fixture(), project_id="recent"))
        restarted = LocalKrea2AssistedProjectStore(self.root)
        self.assertEqual(restarted.summaries(1)[0].project_id, "recent")
        with patch.object(restarted, "get", side_effect=AssertionError("read")):
            self.assertEqual(restarted.summaries(1)[0].project_id, "recent")
        with self.assertRaisesRegex(ValueError, "old"):
            restarted.pending_renders()  # Queue recovery still refuses unknown work.

    def test_save_during_cold_read_cannot_be_overwritten_by_old_summary(self):
        project = self.store.create(fixture())
        path = self.root / "krea2_assisted" / project.project_id / "project.json"
        os.utime(path, (1, 1))
        restarted = LocalKrea2AssistedProjectStore(self.root)
        entered, release = Event(), Event()
        original = restarted.get

        def slow_read(identity):
            old = original(identity)
            entered.set()
            if not release.wait(3):
                raise TimeoutError("fixture read not released")
            return old

        with patch.object(restarted, "get", slow_read), ThreadPoolExecutor(max_workers=1) as pool:
            reader = pool.submit(restarted.summaries)
            try:
                self.assertTrue(entered.wait(2))
                restarted.save(replace(project, name="New name"))
            finally:
                release.set()
            self.assertEqual(reader.result(3)[0].name, "New name")

    def test_failed_durable_write_does_not_publish_a_new_summary(self):
        project = self.store.create(fixture())
        first = self.store.summaries()
        with patch("panelforge.infrastructure.storage.krea2_assisted._atomic_write", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.store.save(replace(project, name="Not saved"))
        self.assertEqual(self.store.summaries(), first)

    def test_failed_display_projection_does_not_fail_a_committed_save_or_queue(self):
        project = self.store.create(fixture())
        self.store.pending_renders()
        with patch("panelforge.infrastructure.storage.krea2_assisted.project_summary", side_effect=ValueError("projection")):
            self.store.save(replace(project, name="Durable name"))
            self.assertEqual(self.store.pending_renders(), ())
            self.assertEqual(self.store.get(project.project_id).name, "Durable name")
            with self.assertRaisesRegex(ValueError, "Historique"):
                self.store.summaries()
        self.assertEqual(self.store.summaries()[0].name, "Durable name")

    def test_explicit_rebuild_includes_external_import_and_limit_is_bounded(self):
        self.store.pending_renders()
        imported = LocalKrea2AssistedProjectStore(self.root)
        imported.create(fixture())
        self.assertEqual(self.store.summaries(), ())
        self.store.rebuild_index()
        self.assertEqual(len(self.store.summaries()), 1)
        self.assertEqual(self.store.summaries(0), ())
        for limit in (True, -1, 101, 1.5):
            with self.assertRaises(ValueError):
                self.store.summaries(limit)

    def test_http_summary_is_read_only_and_old_full_route_is_compatible(self):
        self.store.create(fixture())
        service = object.__new__(Krea2AssistedService)
        service.projects, service.image_timings = self.store, None
        app = FastAPI()
        app.include_router(krea2_assisted_router(image_catalogs=None, krea2_assisted=service,
                                                 krea2_edit=None, runner=SimpleNamespace()))
        with TestClient(app) as client:
            with patch.object(service, "_refresh_detached", side_effect=AssertionError("renderer reconciliation")):
                response = client.get("/api/image-lab/krea2-assisted/project-summaries?limit=30")
                self.assertEqual(response.status_code, 200)
                row = response.json()["projects"][0]
                self.assertEqual(row["preview_url"], "/api/assets/asset-result/thumbnail?v=1")
                self.assertNotIn("attempts", row)
                self.assertNotIn("turns", row)
                self.assertEqual(client.get("/api/image-lab/krea2-assisted/project-summaries?limit=101").status_code, 422)
            full = client.get("/api/image-lab/krea2-assisted/projects?limit=1")
            self.assertEqual(full.status_code, 200)
            self.assertIn("attempts", full.json()["projects"][0])
