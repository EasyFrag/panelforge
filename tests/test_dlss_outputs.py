"""Referenced DLSS media: temporary files only; no renderer or subprocess."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.infrastructure.dlss_outputs import DlssOutputs
from panelforge.infrastructure.storage.local import LocalAssetStore, StorageCorruptionError


class DlssOutputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "LocalOutput"
        self.fallback = self.root / "ComfyUI" / "output"
        self.workspace = self.root / "workspace"
        self.store = LocalAssetStore(self.workspace, external_roots=(self.output, self.fallback))
        self.outputs = DlssOutputs(self.output, self.store, fallback_roots=(self.fallback,))
        self.job = {"job_id": "dlss-" + "a" * 32, "snapshot": {"media_type": "video/mp4"}}
        self.file = self.output / "dlss" / "render_00001_.mp4"
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"finished video bytes")
        self.source = {"filename": self.file.name, "subfolder": "dlss", "type": "output"}

    def test_registration_reopening_and_old_assets_coexist_without_media_duplication(self):
        old = self.store.create(b"legacy image", "image/png")
        asset, path = self.outputs.save(self.job, self.file.read_bytes(), role="enhanced", source=self.source)
        self.assertEqual(path, str(self.file))
        metadata_dir = self.workspace / "assets" / asset.asset_id
        self.assertEqual([p.name for p in metadata_dir.iterdir()], ["asset.json"])
        self.assertEqual(json.loads((metadata_dir / "asset.json").read_text())["schema_version"], 2)
        reopened = LocalAssetStore(self.workspace, external_roots=(self.output, self.fallback))
        self.assertEqual(reopened.get(asset.asset_id), asset)
        self.assertEqual(reopened.read_bytes(asset.asset_id), b"finished video bytes")
        self.assertEqual(reopened.read_bytes(old.asset_id), b"legacy image")
        self.assertEqual(len(list(self.output.rglob("*.mp4"))), 1)

    def test_changed_missing_or_unapproved_files_are_not_silently_served(self):
        asset, _ = self.outputs.save(self.job, self.file.read_bytes(), role="enhanced", source=self.source)
        outside = self.root / "outside.mp4"
        outside.write_bytes(self.file.read_bytes())
        with self.assertRaises(StorageCorruptionError):
            self.store.register_file(outside, "video/mp4")
        with self.assertRaises(StorageCorruptionError):
            self.store.register_file(self.file, "video/mp4", expected_sha256="0" * 64)
        self.file.write_bytes(b"changed content")
        with self.assertRaises(StorageCorruptionError):
            self.store.read_bytes(asset.asset_id)
        self.file.unlink()
        with self.assertRaises(FileNotFoundError):
            self.store.read_bytes(asset.asset_id)
        self.assertTrue((self.workspace / "assets" / asset.asset_id / "asset.json").is_file())

    def test_metadata_cannot_redirect_to_an_unconfigured_folder(self):
        asset, _ = self.outputs.save(self.job, self.file.read_bytes(), role="enhanced", source=self.source)
        metadata = self.workspace / "assets" / asset.asset_id / "asset.json"
        outside = self.root / "outside.mp4"
        outside.write_bytes(self.file.read_bytes())
        data = json.loads(metadata.read_text())
        data["external_path"] = str(outside)
        metadata.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(StorageCorruptionError):
            self.store.read_bytes(asset.asset_id)
        data["external_path"] = str(self.file)
        data["storage_key"] = "external/wrong-identity"
        metadata.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(StorageCorruptionError):
            self.store.read_bytes(asset.asset_id)

    def test_comfy_output_must_stay_within_known_roots_and_match_downloaded_bytes(self):
        for changes in ({"subfolder": "../"}, {"filename": "../secret.mp4"}, {"subfolder": "C:\\outside"}, {"type": "input"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.outputs.save(self.job, b"bytes", role="enhanced", source=dict(self.source, **changes))
        with self.assertRaises(StorageCorruptionError):
            self.outputs.save(self.job, b"different download", role="enhanced", source=self.source)
        with self.assertRaises(FileNotFoundError):
            self.outputs.save(self.job, b"bytes", role="enhanced", source=dict(self.source, filename="missing.mp4"))

    def test_old_comfy_output_root_can_be_reused_without_copy(self):
        path = self.fallback / "dlss" / "old.mp4"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"old runtime output")
        asset, saved = self.outputs.save(self.job, path.read_bytes(), role="enhanced", source=dict(self.source, filename=path.name))
        self.assertEqual(saved, str(path))
        self.assertEqual(self.store.read_bytes(asset.asset_id), path.read_bytes())
        self.assertFalse((self.output / "dlss" / "old.mp4").exists())

    def test_remasked_image_is_saved_visibly_and_retry_does_not_replace_it(self):
        job = dict(self.job, snapshot={"media_type": "image/png"})
        asset, saved = self.outputs.save(job, b"different composed PNG bytes", role="result")
        path = Path(saved)
        before = path.stat().st_mtime_ns
        self.outputs.save(job, b"different composed PNG bytes", role="result")
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(self.store.read_bytes(asset.asset_id), path.read_bytes())
        self.assertFalse((self.workspace / "assets" / asset.asset_id / "content.bin").exists())
        with self.assertRaises(ValueError):
            self.outputs.save(job, b"another result", role="result")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), asset.content_sha256)


if __name__ == "__main__":
    unittest.main()
