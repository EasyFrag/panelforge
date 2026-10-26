"""User-run HTTP contracts, with no workers or external services."""
from io import BytesIO
import tempfile
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from panelforge.application.creation_batch import CreationBatchService
from panelforge.features.lab.creation_batch_web import creation_batch_router
from panelforge.infrastructure.creation_batch_thumbnails import PillowBatchThumbnails
from panelforge.infrastructure.storage.creation_batch import LocalCreationBatchStore
from tests.test_creation_batch import AssistedDouble, request_values
from tests.test_creation_batch_variants import FactoryDouble


class CreationBatchWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.assisted = AssistedDouble()
        self.service = CreationBatchService(LocalCreationBatchStore(self.temp.name), self.assisted,
                                            thumbnails=lambda asset_id: b"jpeg-fixture")
        app = FastAPI()
        app.include_router(creation_batch_router(self.service))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.api = "/api/image-lab/creation-batch"

    def test_import_reports_count_without_creating_or_generating(self):
        response = self.client.post(self.api + "/csv", files={"file": ("lips.csv", b'intention\n"red, gold"\nblue\n', "text/csv")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertIsNone(self.service.latest())
        self.assertEqual(self.assisted.chat_calls, [])
        response = self.client.post(self.api + "/csv", files={"file": ("bad.csv", b"prompt\nbad")})
        self.assertEqual(response.status_code, 422)

    def test_repeated_post_and_revision_polling_do_not_repeat_work(self):
        values = request_values()
        response = self.client.post(self.api + "/batches", json=values)
        self.assertEqual(response.status_code, 201)
        batch = response.json()["batch"]
        again = self.client.post(self.api + "/batches", json=values)
        self.assertEqual(again.json()["batch"]["batch_id"], batch["batch_id"])
        conflict = self.client.post(self.api + "/batches", json={**values, "name": "Changed"})
        self.assertEqual(conflict.status_code, 409)
        url = self.api + "/batches/" + batch["batch_id"]
        self.assertTrue(self.client.get(url, params={"known_revision": batch["revision"]}).json()["unchanged"])
        self.service.process_next()
        changed = self.client.get(url, params={"known_revision": batch["revision"]}).json()["batch"]
        self.assertTrue(changed["statuses_only"])
        self.assertNotIn("intention", changed["items"][0])
        self.assertEqual(changed["items"][0]["prompt_status"], "succeeded")
        full = self.client.get(url).json()["batch"]
        self.assertEqual(full["items"][0]["intention"], "Jewels")
        self.assertEqual(len(self.assisted.chat_calls), 1)
        self.assertEqual(len(self.assisted.queue_calls), 1)

    def test_presets_are_required_and_render_overrides_are_rejected(self):
        for changes in ({"preset_id": ""}, {"settings": {"model_name": "override"}},
                        {"request_id": "../outside"}, {"intentions": []}, {"model_id": "unknown"}):
            with self.subTest(changes=changes):
                response = self.client.post(self.api + "/batches", json=request_values(**changes))
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.assisted.chat_calls, [])

    def test_current_and_previews_only_reference_the_selected_batch(self):
        self.assertIsNone(self.client.get(self.api + "/current").json()["batch"])
        batch = self.service.create(**request_values())
        missing = self.client.get(self.api + "/batches/creation-batch-" + uuid4().hex)
        self.assertEqual(missing.status_code, 404)
        self.service.process_next()
        self.assisted.finish(self.service.get(batch.batch_id).items[0].project_id)
        self.service.process_next()
        item = self.client.get(self.api + "/current").json()["batch"]["items"][0]
        self.assertTrue(item["image_url"].endswith("/content"))
        self.assertEqual(self.client.get(item["thumbnail_url"]).content, b"jpeg-fixture")
        self.assertEqual(self.client.get(item["thumbnail_url"].replace("/1/", "/99/")).status_code, 404)

    def test_unconfigured_returns_503(self):
        app = FastAPI()
        app.include_router(creation_batch_router(None))
        with TestClient(app) as client:
            self.assertEqual(client.get(self.api + "/current").status_code, 503)

    def test_variants_and_factory_receipts_are_scoped_to_the_selected_image(self):
        self.service.factory = FactoryDouble()
        batch = self.service.create(**request_values())
        self.service.process_next()
        self.assisted.finish(self.service.get(batch.batch_id).items[0].project_id)
        self.service.process_renders()
        url = self.api + "/batches/" + batch.batch_id + "/items/1"
        body = dict(request_id=str(uuid4()), kind="render")
        first = self.client.post(url + "/variants", json=body)
        self.assertEqual(first.status_code, 201)
        self.client.post(url + "/variants", json=body)
        item = first.json()["batch"]["items"][0]
        self.assertEqual(len(item["renders"]), 2)
        self.assertNotIn("config", item)  # Polling does not serialize preset examples/settings snapshots.
        self.assertNotIn("prompt", item["renders"][1])
        receipt = self.client.post(url + "/renders/initial/factory")
        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt.json()["batch"]["items"][0]["renders"][0]["factory_item_id"], "factory-1")
        self.assertEqual(self.client.post(url + "/renders/unknown/factory").status_code, 404)
        self.assertEqual(self.client.post(url + "/variants", json={**body, "settings": {}}).status_code, 422)

    def test_live_progress_is_returned_even_when_durable_revision_is_unchanged(self):
        batch = self.service.create(**request_values())
        url = self.api + "/batches/" + batch.batch_id
        response = self.client.get(url, params={"known_revision": batch.revision}).json()
        self.assertTrue(response["unchanged"])
        self.assertEqual(response["monitor"]["1"]["prompt"]["status"], "waiting")

    def test_new_child_rows_include_their_names_during_revision_polling(self):
        batch = self.service.create(**request_values())
        self.service.process_next()
        self.assisted.finish(self.service.get(batch.batch_id).items[0].project_id)
        self.service.process_renders()
        before = self.service.get(batch.batch_id)
        self.service.add_variant(batch.batch_id, "1", request_id=str(uuid4()), kind="preset",
                                 preset_id="style-test", preset_revision=1)
        result = self.client.get(self.api + "/batches/" + batch.batch_id,
            params={"known_revision": before.revision, "known_count": 1}).json()["batch"]
        self.assertFalse(result["statuses_only"])
        self.assertTrue(result["items"][1]["name"])


class BatchThumbnailTests(unittest.TestCase):
    def test_preview_is_small_cached_and_does_not_modify_original(self):
        source = BytesIO()
        Image.new("RGB", (900, 1600), "red").save(source, "PNG")
        content = source.getvalue()
        reads = []
        class Assets:
            def read_bytes(self, asset_id):
                reads.append(asset_id)
                return content
        renderer = PillowBatchThumbnails(Assets())
        preview = renderer("asset-one")
        self.assertEqual(renderer("asset-one"), preview)
        self.assertEqual(reads, ["asset-one"])
        with Image.open(BytesIO(preview)) as image:
            self.assertLessEqual(max(image.size), 420)
        with Image.open(BytesIO(renderer("asset-one", size=840))) as image:
            self.assertEqual(max(image.size), 840)
        self.assertEqual(source.getvalue(), content)
