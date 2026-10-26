"""Queue index regressions, with temporary files and no external engines."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from panelforge.domain.krea2_assisted import Krea2AssistedAttempt, Krea2AssistedProject
from panelforge.domain.krea2_batch import Krea2BatchSettings
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore


class Krea2AssistedIndexTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = LocalKrea2AssistedProjectStore(self.root)

    def create(self, identity, order=None):
        attempt = Krea2AssistedAttempt(
            attempt_id="attempt-1", index=1, prompt="Private prompt",
            settings=Krea2BatchSettings(model_name="Krea2/a.safetensors",
                                        aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                                        megapixels=0.8), seed=0,
        )
        if order is not None:
            attempt = attempt.queue(order)
        return self.store.create(Krea2AssistedProject(
            project_id=identity, name=identity, intention="Private intention",
            model_id="local", attempts=(attempt,),
        ))

    def test_warm_queue_and_order_do_no_disk_io_with_large_history(self):
        # The assertion counts I/O, independent of machine speed.
        for index in range(80):
            self.create(f"archived-{index}")
        active = self.create("active", 100)
        self.assertEqual(len(self.store.pending_renders()), 1)
        with patch.object(Path, "iterdir", side_effect=AssertionError("rescan")), \
                patch.object(Path, "read_text", side_effect=AssertionError("reread")), \
                patch.object(Path, "stat", side_effect=AssertionError("restat")):
            for _ in range(20):
                entries = self.store.pending_renders()
                self.assertEqual(entries[0].project_id, active.project_id)
            self.assertEqual(self.store.next_queue_order(1), 101)
            self.assertEqual(self.store.next_queue_order(1), 102)
        self.assertNotIn("Private prompt", repr(entries))
        self.assertNotIn("Private intention", repr(entries))

    def test_snapshots_are_immutable_and_follow_durable_changes(self):
        project = self.create("active", 10)
        before = self.store.pending_renders()
        self.store.save(replace(project, name="Renamed"))
        self.assertEqual(before[0].project_name, "active")
        self.assertEqual(self.store.pending_renders()[0].project_name, "Renamed")
        self.store.save(project.replace_attempt(project.attempts[0].cancel()))
        self.assertEqual(self.store.pending_renders(), ())
        self.assertEqual(before[0].project_name, "active")

    def test_restart_restores_priority_and_maximum_from_terminal_attempts(self):
        queued = self.create("queued", 10)
        running = self.create("running", 20)
        completed = self.create("completed", 200)
        self.store.save(running.replace_attempt(running.attempts[0].start("remote", "a" * 64)))
        self.store.save(completed.replace_attempt(
            completed.attempts[0].start("done", "a" * 64).succeed("asset-done")))
        restarted = LocalKrea2AssistedProjectStore(self.root)
        self.assertEqual([e.project_id for e in restarted.pending_renders()], [running.project_id, queued.project_id])
        self.assertEqual(restarted.next_queue_order(1), 201)

    def test_failed_write_never_publishes_new_queue_state(self):
        project = self.create("active", 10)
        before = self.store.pending_renders()
        with patch("panelforge.infrastructure.storage.krea2_assisted._atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save(project.replace_attempt(project.attempts[0].cancel()))
        self.assertEqual(self.store.pending_renders(), before)
        self.assertEqual(self.store.get(project.project_id).attempts[0].status, before[0].status)

    def test_restart_recovers_write_before_memory_publication(self):
        project = self.create("active", 10)
        self.store.pending_renders()
        with patch.object(self.store, "_saved", side_effect=RuntimeError("process interrupted")):
            with self.assertRaises(RuntimeError):
                self.store.save(project.replace_attempt(project.attempts[0].cancel()))
        self.assertEqual(LocalKrea2AssistedProjectStore(self.root).pending_renders(), ())

    def test_recent_list_reads_only_selected_projects_after_initial_scan(self):
        first = self.create("first")
        second = self.create("second")
        os.utime(self.root / "krea2_assisted" / first.project_id / "project.json", (1, 1))
        os.utime(self.root / "krea2_assisted" / second.project_id / "project.json", (2, 2))
        self.assertEqual(self.store.list(1)[0].project_id, second.project_id)
        self.store.save(first)
        original = Path.read_text
        reads = []

        def read(path, *args, **kwargs):
            reads.append(path.parent.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, "iterdir", side_effect=AssertionError("rescan")), \
                patch.object(Path, "read_text", read):
            self.assertEqual(self.store.list(1)[0].project_id, first.project_id)
            self.assertEqual(self.store.list(0), [])
        self.assertEqual(reads, [first.project_id])
        self.assertNotIn(second.project_id, reads)

    def test_corrupt_history_blocks_queue_without_repeated_recovery(self):
        good = self.create("good", 10)
        bad = self.create("broken", 20)
        path = self.root / "krea2_assisted" / bad.project_id / "project.json"
        original = path.read_bytes()
        path.write_text("invalid JSON", encoding="utf-8")
        restarted = LocalKrea2AssistedProjectStore(self.root)
        with self.assertRaisesRegex(ValueError, "broken"):
            restarted.pending_renders()
        with patch.object(Path, "read_text", side_effect=AssertionError("retry scan")):
            with self.assertRaisesRegex(ValueError, "broken"):
                restarted.pending_renders()
        path.write_bytes(original)
        restarted.rebuild_index()
        self.assertEqual([e.project_id for e in restarted.pending_renders()], [good.project_id, bad.project_id])

    def test_external_import_is_visible_after_explicit_rebuild(self):
        self.assertEqual(self.store.pending_renders(), ())
        imported = LocalKrea2AssistedProjectStore(self.root)
        project = Krea2AssistedProject(project_id="imported", name="Imported", intention="Photo", model_id="local")
        imported.create(project)
        self.assertEqual(self.store.list(10), [])
        self.store.rebuild_index()
        self.assertEqual(self.store.list(10), [project])

    def test_legacy_queue_order_remains_optional(self):
        project = self.create("legacy", 10)
        path = self.root / "krea2_assisted" / project.project_id / "project.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema_version"] = 5
        data["attempts"][0].pop("queue_order")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(LocalKrea2AssistedProjectStore(self.root).pending_renders()[0].queue_order)

    def test_slow_read_of_another_project_does_not_block_a_save(self):
        archived = self.create("archived")
        active = self.create("active", 10)
        self.store.pending_renders()
        entered, release = Event(), Event()
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.parent.name == archived.project_id:
                entered.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("reader not released")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read), ThreadPoolExecutor(max_workers=2) as pool:
            reader = pool.submit(self.store.get, archived.project_id)
            try:
                self.assertTrue(entered.wait(timeout=2))
                writer = pool.submit(self.store.save, replace(active, name="Updated"))
                self.assertEqual(writer.result(timeout=2).name, "Updated")
            finally:
                release.set()
            self.assertEqual(reader.result(timeout=2).project_id, archived.project_id)


if __name__ == "__main__":
    unittest.main()
