import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.domain import (
    ControlValue,
    PromptPolicy,
    PromptSnapshot,
    RecipeRef,
    RunRecord,
    RunReview,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalRunStore,
    StorageCorruptionError,
)


SHA_A = "a" * 64
START = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


class SequenceClock:
    def __init__(self) -> None:
        self._next = START

    def __call__(self) -> datetime:
        value = self._next
        self._next += timedelta(seconds=1)
        return value


def new_run(run_id: str = "run-1") -> RunRecord:
    return RunRecord.create(
        run_id=run_id,
        recipe=RecipeRef(
            operation_id="character.change_view",
            recipe_id="qwen-edit-2511-multiple-angles",
            version="0.2.0",
            workflow_sha256=SHA_A,
        ),
        source_asset_ids=("asset-source",),
        prompt=PromptSnapshot(
            positive="<sks> front view eye-level shot medium shot",
            negative="text, watermark",
            policy=PromptPolicy.LOCKED,
        ),
        controls=(
            ControlValue("azimuth", "front"),
            ControlValue("multiple_angles_lora_strength", 1.0),
            ControlValue("seed", 42),
        ),
    )


class LocalAssetStoreTest(unittest.TestCase):
    def test_create_get_and_read_bytes_use_expected_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAssetStore(
                directory,
                id_factory=lambda: "asset-1",
            )
            content = b"not really a png"

            asset = store.create(content, "image/png", source_run_id="run-1")

            self.assertEqual(asset.asset_id, "asset-1")
            self.assertEqual(asset.storage_key, "assets/asset-1/content.bin")
            self.assertEqual(asset.content_sha256, hashlib.sha256(content).hexdigest())
            self.assertEqual(asset.source_run_id, "run-1")
            self.assertEqual(store.get("asset-1"), asset)
            self.assertEqual(store.read_bytes("asset-1"), content)
            root = Path(directory)
            self.assertTrue((root / "assets" / "asset-1" / "asset.json").is_file())
            self.assertTrue((root / "assets" / "asset-1" / "content.bin").is_file())

    def test_creation_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAssetStore(directory, id_factory=lambda: "same-id")
            store.create(b"first", "image/png")

            with self.assertRaises(FileExistsError):
                store.create(b"second", "image/png")

            self.assertEqual(store.read_bytes("same-id"), b"first")

    def test_rejects_traversal_from_factory_and_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAssetStore(directory, id_factory=lambda: "../escape")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                store.create(b"content", "image/png")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                store.get("../escape")

    def test_failed_domain_validation_does_not_reserve_generated_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAssetStore(directory, id_factory=lambda: "asset-1")
            with self.assertRaisesRegex(ValueError, "media_type"):
                store.create(b"content", "")

            self.assertFalse((Path(directory) / "assets" / "asset-1").exists())

    def test_detects_changed_content_and_metadata_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAssetStore(directory, id_factory=lambda: "asset-1")
            store.create(b"original", "image/png")
            asset_dir = Path(directory) / "assets" / "asset-1"
            (asset_dir / "content.bin").write_bytes(b"tampered")

            with self.assertRaisesRegex(StorageCorruptionError, "content"):
                store.read_bytes("asset-1")

            metadata_path = asset_dir / "asset.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["asset_id"] = "asset-other"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(StorageCorruptionError, "identity"):
                store.get("asset-1")


class LocalRunStoreTest(unittest.TestCase):
    def test_round_trips_full_nested_run_and_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            record = new_run()

            self.assertEqual(store.create(record), record)
            run_path = Path(directory) / "runs" / "run-1" / "run.json"
            raw = json.loads(run_path.read_text(encoding="utf-8"))

            self.assertEqual(raw["schema_version"], 1)
            self.assertEqual(raw["created_at"], "2026-08-05T10:00:00Z")
            self.assertEqual(raw["updated_at"], raw["created_at"])
            self.assertEqual(raw["prompt"]["policy"], "locked")
            self.assertEqual(raw["controls"][1]["value"], 1.0)
            self.assertEqual(store.get("run-1"), record)

    def test_create_is_exclusive_and_save_is_atomic_metadata_update(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            record = new_run()
            store.create(record)
            with self.assertRaises(FileExistsError):
                store.create(record)

            failed = record.fail("upload failed")
            store.save(failed)
            raw = json.loads(
                (Path(directory) / "runs" / "run-1" / "run.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(raw["created_at"], "2026-08-05T10:00:00Z")
            self.assertEqual(raw["updated_at"], "2026-08-05T10:00:01Z")
            self.assertEqual(store.get("run-1"), failed)
            self.assertEqual(list((Path(directory) / "runs" / "run-1").glob("*.tmp")), [])

    def test_saves_workflow_deterministically_and_verifies_its_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            record = new_run()
            store.create(record)
            workflow = {"2": {"inputs": {"seed": 42}}, "1": {"class_type": "A"}}

            digest = store.save_compiled_workflow("run-1", workflow)
            workflow_path = (
                Path(directory) / "runs" / "run-1" / "compiled_workflow.json"
            )
            self.assertEqual(digest, hashlib.sha256(workflow_path.read_bytes()).hexdigest())

            submitted = record.submit("comfy-prompt-1", digest)
            store.save(submitted)
            self.assertEqual(store.get("run-1"), submitted)

            workflow_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(StorageCorruptionError, "workflow"):
                store.get("run-1")

    def test_list_is_newest_first_and_applies_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            first = new_run("run-1")
            second = new_run("run-2")
            store.create(first)
            store.create(second)

            self.assertEqual(store.list(1), [second])
            self.assertEqual(store.list(2), [second, first])
            self.assertEqual(store.list(0), [])

    def test_round_trips_terminal_enums_and_optional_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            record = RunRecord.create(
                run_id="run-child",
                recipe=new_run().recipe,
                source_asset_ids=("asset-parent-output",),
                prompt=new_run().prompt,
                parent_run_id="run-parent",
                experimental_overrides=("multiple_angles_lora_strength",),
            )
            store.create(record)
            digest = store.save_compiled_workflow("run-child", {"node": {}})
            kept = (
                record.submit("comfy-prompt-child", digest)
                .succeed(("asset-output",))
                .review(RunReview.KEPT)
            )

            store.save(kept)

            self.assertEqual(store.get("run-child"), kept)

    def test_rejects_traversal_and_corrupt_nested_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalRunStore(directory, clock=SequenceClock())
            with self.assertRaisesRegex(ValueError, "unsafe"):
                store.get("../outside")

            store.create(new_run())
            run_path = Path(directory) / "runs" / "run-1" / "run.json"
            raw = json.loads(run_path.read_text(encoding="utf-8"))
            raw["status"] = "unknown"
            run_path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(StorageCorruptionError, "metadata"):
                store.get("run-1")


if __name__ == "__main__":
    unittest.main()
