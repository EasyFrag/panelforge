"""User-run checks for active features that depended on retired workshops."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from panelforge.application.video_outputs import extract_bound_video
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.storage import LocalKrea2BatchHistory, LocalVideoRunHistory
from panelforge.infrastructure.storage.local import StorageCorruptionError


class SharedImageResourceRoutesTest(unittest.TestCase):
    def test_resources_can_be_read_annotated_and_refreshed_without_a_batch_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models, loras = root / "models", root / "loras"
            models.mkdir()
            loras.mkdir()
            (models / "krea2_turbo_bf16.safetensors").write_bytes(b"model")
            (loras / "detail.safetensors").write_bytes(b"lora")
            catalog = LocalKrea2ResourceCatalog(models_root=models, loras_root=loras, workspace_root=root)
            resource = catalog.list_models()[0]
            # No Comfy/LLM or retired render service is injected.
            with TestClient(create_app(object(), krea2_resources=catalog)) as client:
                url = f"/api/image-lab/krea2-batch/resources/{resource.resource_id}"
                self.assertEqual(client.get(url).status_code, 200)
                response = client.post(url + "/preference", json={"favorite": True, "display_name": "My checkpoint"})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["favorite"])
                self.assertEqual(response.json()["display_name"], "My checkpoint")
                self.assertEqual(catalog.get(resource.resource_id).display_name, "My checkpoint")
                with patch.object(catalog, "refresh_remote", return_value=catalog.get(resource.resource_id)) as refresh:
                    self.assertEqual(client.post(url + "/refresh").status_code, 200)
                    refresh.assert_called_once_with(resource.resource_id)
                for route in ("/api/production/spec", "/api/production-v2/spec", "/api/image-lab/krea2/spec",
                              "/api/image-lab/krea2-batch/spec", "/api/video-lab/spec"):
                    with self.subTest(route=route):
                        self.assertEqual(client.get(route).status_code, 404)

    def test_missing_resource_catalog_returns_503(self):
        with TestClient(create_app(object())) as client:
            response = client.get("/api/image-lab/krea2-batch/resources/missing")
            self.assertEqual(response.status_code, 503)


class ImportedVideoHistoryTest(unittest.TestCase):
    def test_an_empty_history_does_not_create_a_retired_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            history = LocalVideoRunHistory(directory)
            self.assertEqual(history.list(), [])
            self.assertFalse((Path(directory) / "video_runs").exists())

    def test_reads_an_old_video_prompt_without_modifying_the_record(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "video_runs" / "video-1"
            folder.mkdir(parents=True)
            workflow = b'{"output": {}}'
            (folder / "compiled_workflow.json").write_bytes(workflow)
            record = {
                "schema_version": 1, "created_at": "2026-09-01T10:00:00Z", "updated_at": "2026-09-01T10:01:00Z",
                "run_id": "video-1", "recipe": {"operation_id": "video.generate.ref2v", "recipe_id": "minimax-h3-ref2v",
                                                 "version": "0.2.1", "workflow_sha256": "a" * 64},
                "preset_id": "balanced", "source_asset_ids": ["image-1"], "source_labels": ["Source"],
                "prompt": "The original video prompt.",
                "settings": {"aspect_ratio": "1:1 (Square)", "megapixels": 0.6, "duration_seconds": 10,
                             "steps": 32, "seed": 7, "seed_locked": False},
                "status": "succeeded", "execution_id": "execution-1", "output_asset_id": "clip-1", "error": None,
                "compiled_workflow_sha256": hashlib.sha256(workflow).hexdigest(),
            }
            path = folder / "run.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            before = path.read_bytes()
            history = LocalVideoRunHistory(directory)
            run = history.list()[0]
            self.assertEqual(run.prompt, record["prompt"])
            self.assertEqual(run.output_asset_id, "clip-1")
            self.assertEqual(history.get("video-1"), run)
            self.assertEqual(path.read_bytes(), before)
            (folder / "compiled_workflow.json").write_bytes(b"changed")
            with self.assertRaises(StorageCorruptionError):
                history.list()


class ImportedBatchHistoryTest(unittest.TestCase):
    def test_existing_successful_images_remain_available_to_edit_without_a_render_service(self):
        with tempfile.TemporaryDirectory() as directory:
            history = LocalKrea2BatchHistory(directory)
            self.assertEqual(history.list(), [])
            folder = Path(directory) / "krea2_batches" / "batch-1"
            self.assertFalse(folder.parent.exists())
            folder.mkdir(parents=True)
            record = {
                "schema_version": 1, "batch_id": "batch-1", "recipe_id": "fixture", "recipe_version": "0.1.0",
                "recipe_sha256": "a" * 64, "model_id": "fake", "image_count": 1, "direction": "", "status": "completed",
                "settings": {"model_name": "Krea2/base.safetensors", "aspect_ratio": "1:1 (Square)",
                             "megapixels": 1.0, "loras": []},
                "items": [{"item_id": "item-1", "index": 1, "prompt": "The original image prompt.",
                           "variation_signature": "first", "seed": "7", "status": "succeeded",
                           "execution_id": "execution-1", "compiled_workflow_sha256": "b" * 64,
                           "output_asset_id": "image-1", "error": None, "review": "neutral", "comment": ""}],
                "raw_prompt_response": None, "warnings": [], "error": None,
            }
            path = folder / "batch.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            before = path.read_bytes()
            batch = history.list()[0]
            self.assertEqual(batch.items[0].output_asset_id, "image-1")
            self.assertEqual(batch.items[0].prompt, "The original image prompt.")
            self.assertEqual(history.get("batch-1"), batch)
            self.assertEqual(path.read_bytes(), before)


class ManifestVideoOutputTest(unittest.TestCase):
    def test_uses_the_declared_node_and_field_among_multiple_outputs(self):
        history = {"outputs": {"wrong": {"videos": [{"filename": "preview.mp4"}]},
                               "final": {"saved": [{"filename": "final.mp4", "subfolder": "clips", "type": "output"}]}}}
        self.assertEqual(extract_bound_video(history, node_id="final", history_field="saved"),
                         {"filename": "final.mp4", "subfolder": "clips", "type": "output"})
        with self.assertRaises(ValueError):
            extract_bound_video(history, node_id="missing", history_field="saved")


if __name__ == "__main__":
    unittest.main()
