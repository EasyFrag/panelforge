from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain import (
    Krea2AspectRatio,
    Krea2LabRun,
    Krea2LabSettings,
    RecipeRef,
)
from panelforge.infrastructure.storage import (
    LocalKrea2RunStore,
    StorageCorruptionError,
)


DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)


class AdvancingClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 17, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class Krea2RunStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.store = LocalKrea2RunStore(
            self.directory.name,
            clock=AdvancingClock(),
        )
        self.recipe = RecipeRef(
            "image.generate.t2i",
            "krea2",
            "0.1.0",
            "a" * 64,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _run(self, run_id: str = "krea2-1") -> Krea2LabRun:
        prompt = "STRICT FORMAT: a 3x2 storyboard page."
        return Krea2LabRun.create(
            run_id=run_id,
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt=prompt,
            settings=Krea2LabSettings(
                model_name=DEFAULT_MODEL,
                aspect_ratio=Krea2AspectRatio.PORTRAIT_PHOTO,
                megapixels=3.0,
                seed=2**64 - 1,
                seed_locked=True,
            ),
            source_storyboard_run_id="storyboard-1",
            source_prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        )

    def test_round_trip_uses_a_separate_history_and_preserves_provenance(self) -> None:
        run = self._run()
        self.store.create(run)

        self.assertEqual(self.store.get(run.run_id), run)
        self.assertEqual(self.store.list(), [run])
        run_path = Path(
            self.directory.name,
            "krea2_runs",
            run.run_id,
            "run.json",
        )
        metadata = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["settings"]["seed"], str(2**64 - 1))
        self.assertEqual(metadata["source_storyboard_run_id"], "storyboard-1")
        self.assertFalse(Path(self.directory.name, "runs", run.run_id).exists())

    def test_compiled_workflow_hash_is_persisted_and_verified(self) -> None:
        run = self._run()
        self.store.create(run)
        queued = self.store.save(run.queue())
        workflow_hash = self.store.save_compiled_workflow(
            run.run_id,
            {"29": {"class_type": "SaveImage", "inputs": {}}},
        )
        running = queued.start("prompt-1", workflow_hash)
        self.store.save(running)

        self.assertEqual(self.store.get(run.run_id), running)
        workflow_path = Path(
            self.directory.name,
            "krea2_runs",
            run.run_id,
            "compiled_workflow.json",
        )
        self.assertEqual(
            hashlib.sha256(workflow_path.read_bytes()).hexdigest(),
            workflow_hash,
        )

        workflow_path.write_bytes(workflow_path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(StorageCorruptionError, "does not match"):
            self.store.get(run.run_id)

    def test_running_state_cannot_reference_a_missing_workflow(self) -> None:
        run = self._run()
        self.store.create(run)
        queued = self.store.save(run.queue())

        with self.assertRaisesRegex(StorageCorruptionError, "missing"):
            self.store.save(queued.start("prompt-1", "b" * 64))

    def test_list_orders_by_last_update_and_honours_limit(self) -> None:
        first = self._run("krea2-1")
        second = self._run("krea2-2")
        self.store.create(first)
        self.store.create(second)
        self.store.save(first.queue())

        self.assertEqual(
            [run.run_id for run in self.store.list()],
            ["krea2-1", "krea2-2"],
        )
        self.assertEqual(self.store.list(1), [first.queue()])
        self.assertEqual(self.store.list(0), [])

    def test_duplicate_and_unsafe_run_ids_are_rejected(self) -> None:
        run = self._run()
        self.store.create(run)
        with self.assertRaises(FileExistsError):
            self.store.create(run)
        with self.assertRaisesRegex(ValueError, "unsafe path"):
            self.store.get("../outside")


if __name__ == "__main__":
    unittest.main()
