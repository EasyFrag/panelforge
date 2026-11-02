"""User-run import regression tests; synthetic PNGs only, no network or models."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from panelforge.infrastructure.personal_pose_import import digest, import_poses, rollback
from panelforge.infrastructure.pose_catalog import LocalPoseCatalog, PERSONAL_INDEX_NAME
from panelforge.infrastructure.storage.local import LocalAssetStore, _json_bytes
from tests.test_pose_catalog import install_personal_fixture


class PersonalPoseImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.catalog = LocalPoseCatalog(self.workspace, downloader=lambda *args: self.fail("No network"))
        self.original, _ = install_personal_fixture(self.catalog)
        self.legacy_path = self.catalog.root / "personal/catalog.json"
        self.index_path = self.catalog.root / "personal" / PERSONAL_INDEX_NAME
        self.before = self.legacy_path.read_bytes()
        output = BytesIO()
        Image.new("RGB", (600, 900), "white").save(output, "PNG")
        self.content = output.getvalue()
        asset = LocalAssetStore(self.workspace).create(self.content, media_type="image/png")
        self.source = dict(batch_id="creation-batch-fixture", item_id="45", render_id="second",
                           attempt_id="attempt-second", asset_id=asset.asset_id)
        item = dict(item_id="45", image_status="succeeded", output_asset_id="excluded-original",
                    attempt_id="attempt-first", renders=[dict(render_id="second", status="succeeded",
                        attempt_id="attempt-second", output_asset_id=asset.asset_id)])
        folder = self.workspace / "creation_batches"
        folder.mkdir()
        (folder / "creation-batch-fixture.json").write_bytes(_json_bytes(dict(batch_id="creation-batch-fixture", items=[item])))
        self.manifest = dict(schema_version=1, import_id="fixture-import", batch_id="creation-batch-fixture",
            exclude_entire_items=["13"], exclude_initial_only=["45"], entries=[dict(
                id="personal_fixture2_second", pose_id="personal_fixture2", number="K045", name="Fixture",
                family="Mes poses", category="Assis", angle="Dos", elevation="Plongée", confidence="low",
                view_label="Dos · plongée · ligne 45 · rendu 2", review_note="Cadrage partiel.",
                sha256=digest(self.content), provenance=self.source)])

    def test_dry_run_apply_frozen_original_thumbnail_idempotence_and_rollback(self):
        report = import_poses(self.workspace, self.manifest)
        self.assertFalse(report["applied"])
        self.assertFalse(self.index_path.exists())
        self.assertEqual(self.legacy_path.read_bytes(), self.before)
        self.assertFalse((self.catalog.root / "personal/thumbs").exists())
        # Reuse a reader that has cached the old index: replacement must invalidate it.
        self.assertEqual(len(self.catalog.entries()), 1)
        report = import_poses(self.workspace, self.manifest, apply=True)
        self.assertEqual(report["added_images"], 1)
        self.assertEqual(self.legacy_path.read_bytes(), self.before)
        self.assertEqual(len(self.catalog.entries()), 2)
        selected = self.manifest["entries"][0]["id"]
        metadata, original = self.catalog.reference(selected)
        self.assertEqual(original, self.content)
        self.assertEqual(metadata["provenance"], self.source)
        self.assertEqual(metadata["view_label"], self.manifest["entries"][0]["view_label"])
        self.assertIn("Dos", self.catalog.status()["angles"])
        self.assertIn("Plongée", self.catalog.status()["angles"])
        with Image.open(self.catalog.image_path(selected, thumbnail=True)) as thumbnail:
            self.assertLessEqual(max(thumbnail.size), 480)
        frozen = self.index_path.read_bytes()
        report = import_poses(self.workspace, self.manifest, apply=True)
        self.assertEqual(report["added_images"], 0)
        self.assertEqual(self.index_path.read_bytes(), frozen)
        rollback(self.workspace, "fixture-import", apply=True)
        self.assertEqual(self.index_path.read_bytes(), self.before)
        self.assertEqual(len(self.catalog.entries()), 1)

    def test_exclusion_source_drift_or_digest_mismatch_leaves_catalogue_unchanged(self):
        for mutation in ("excluded", "initial", "attempt", "digest"):
            manifest = deepcopy(self.manifest)
            entry = manifest["entries"][0]
            if mutation == "excluded": manifest["exclude_entire_items"].append("45")
            elif mutation == "initial": entry["provenance"]["render_id"] = "initial"
            elif mutation == "attempt": entry["provenance"]["attempt_id"] = "wrong-attempt"
            else: entry["sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                import_poses(self.workspace, manifest, apply=True)
            self.assertFalse(self.index_path.exists())
            self.assertEqual(self.legacy_path.read_bytes(), self.before)

    def test_duplicate_ids_and_conflicting_reimport_are_rejected(self):
        duplicate = deepcopy(self.manifest)
        duplicate["entries"].append(deepcopy(duplicate["entries"][0]))
        with self.assertRaises(ValueError): import_poses(self.workspace, duplicate, apply=True)
        import_poses(self.workspace, self.manifest, apply=True)
        frozen = self.index_path.read_bytes()
        changed = deepcopy(self.manifest)
        changed["entries"][0]["angle"] = "Face"
        with self.assertRaises(ValueError): import_poses(self.workspace, changed, apply=True)
        self.assertEqual(self.index_path.read_bytes(), frozen)

    def test_rollback_refuses_to_overwrite_a_later_catalogue_change(self):
        import_poses(self.workspace, self.manifest, apply=True)
        index = json.loads(self.index_path.read_bytes())
        index["entries"][0]["name"] = "Modification ultérieure"
        index["revision"] = digest(_json_bytes(index["entries"]))
        self.index_path.write_bytes(_json_bytes(index))
        changed = self.index_path.read_bytes()
        with self.assertRaises(ValueError): rollback(self.workspace, "fixture-import", apply=True)
        self.assertEqual(self.index_path.read_bytes(), changed)

    def test_tampered_thumbnail_is_rejected_without_affecting_original(self):
        import_poses(self.workspace, self.manifest, apply=True)
        identity = self.manifest["entries"][0]["id"]
        self.catalog.image_path(identity, thumbnail=True).write_bytes(b"changed")
        with self.assertRaises(ValueError): self.catalog.image_path(identity, thumbnail=True)
        self.assertEqual(self.catalog.reference(identity)[1], self.content)
