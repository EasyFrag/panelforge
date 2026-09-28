"""User-run archive and output regressions. Memory/fake services or temporary files only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.video_factory import FactoryConflict, VideoFactoryService
from panelforge.domain.video_factory import configuration, new_item
from panelforge.domain.video_factory_results import can_archive, delivery_material
from panelforge.features.lab.video_factory_web import video_factory_router
from panelforge.infrastructure.storage.video_factory import LocalVideoFactoryStore
from tests.test_video_factory import MemoryStore, FakeWorkflows


def delivered(name="Result"):
    config = configuration("ref2v")
    config.update(intention="Intention française conservée", final_prompt="<d>[English] Thank you.</d>")
    config["references"] = [dict(asset_id="asset-image", role="subject_reference")]
    item = new_item(name, config, dict(kind="episode", id="english-copy", index=0, group="English"), name)
    item["status"] = "succeeded"
    for stage in ("plan", "prompt", "video"):
        item["steps"][stage].update(status="succeeded", started_at="2026-09-26T08:00:00Z", finished_at="2026-09-26T08:00:30Z")
    item["steps"]["prompt"]["output"] = {"text": config["final_prompt"]}
    item["steps"]["video"]["output"] = dict(asset_id="asset-" + "a" * 32, attempt_id="attempt-kept", project_id="render-kept")
    item["runtime"] = dict(attempt_id="attempt-kept", render_project_id="render-kept",
        episode_inputs=dict(localization=dict(language="English")), episode_preparation_id="translated")
    item["delivery"] = dict(status="succeeded", key=delivery_material(item)["key"], folder="D:/output/date")
    return item


class FactoryArchivesTest(unittest.TestCase):
    def setUp(self):
        self.store, self.adapter = MemoryStore(), FakeWorkflows()
        self.first, self.second = delivered("First"), delivered("Second")
        self.store.value["items"] = [self.first, self.second]
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter, outputs=Mock())

    def selection(self, *ids):
        return list(ids), {i["id"]: i["revision"] for i in self.service.snapshot()["items"] if i["id"] in ids}

    def test_archive_restore_preserves_outputs_config_timing_and_never_dispatches(self):
        before = deepcopy(self.service._get(self.first["id"]))
        self.service.action("archive", *self.selection(self.first["id"]))
        item = self.service._get(self.first["id"])
        self.assertTrue(item["archived_at"])
        self.assertEqual(item["status"], "succeeded")
        for field in ("config", "source", "runtime", "steps", "history", "delivery"):
            self.assertEqual(item[field], before[field])
        self.service.dispatch()
        self.assertFalse(self.service._workers)
        self.service.action("restore", *self.selection(item["id"]))
        self.assertIsNone(item["archived_at"])
        self.assertEqual(item["steps"], before["steps"])
        self.service.dispatch()
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.service.snapshot()["items"][0]["can_archive"], True)

    def test_bulk_archive_is_atomic_with_failed_active_or_unpublished_rows(self):
        variants = [dict(status="failed"), dict(status="active"), dict(status="cancelled"),
                    dict(delivery={}), dict(delivery={"status":"copying"}),
                    dict(delivery={"status":"failed"})]
        for changes in variants:
            with self.subTest(changes=changes):
                current = self.service._get(self.second["id"])
                current.clear()
                current.update(deepcopy(self.second))
                current.update(changes)
                before = deepcopy(self.service._state)
                with self.assertRaises(FactoryConflict):
                    self.service.action("archive", *self.selection(self.first["id"], self.second["id"]))
                self.assertEqual(self.service._state, before)

    def test_pending_stage_or_late_instagram_keeps_result_unarchivable_until_published(self):
        item = self.service._get(self.first["id"])
        item["steps"]["social"].update(status="pending")
        self.assertFalse(can_archive(item))
        item["steps"]["social"].update(status="succeeded", output={"variants":[{"caption":"New text 🌱"}]})
        self.assertFalse(can_archive(item))
        with self.assertRaises(FactoryConflict): self.service.action("archive", *self.selection(item["id"]))
        item["delivery"]["key"] = delivery_material(item)["key"]
        self.assertTrue(can_archive(item))

    def test_worker_guard_and_revision_checks_prevent_stale_archive_or_restore(self):
        identity = self.first["id"]
        ids, stale = self.selection(identity)
        self.service._workers["local_gpu"] = (identity, "social")
        with self.assertRaises(FactoryConflict): self.service.action("archive", ids, stale)
        self.service._workers.clear()
        self.service.action("archive", ids, stale)
        with self.assertRaises(FactoryConflict): self.service.action("restore", ids, stale)
        with self.assertRaises(FactoryConflict): self.service.action("restore", [identity], None)
        self.assertTrue(self.service._get(identity)["archived_at"])

    def test_archive_is_durable_and_legacy_journals_need_no_migration(self):
        with TemporaryDirectory() as directory:
            store = LocalVideoFactoryStore(Path(directory))
            old = deepcopy(self.store.value)
            old["items"][0].pop("archived_at", None)
            store.save(old)
            service = VideoFactoryService(store=store, adapter=self.adapter)
            item = service.snapshot()["items"][0]
            self.assertFalse(item.get("archived_at"))
            service.action("archive", [item["id"]], {item["id"]:item["revision"]})
            restarted = VideoFactoryService(store=LocalVideoFactoryStore(Path(directory)), adapter=self.adapter)
            archived = restarted.snapshot()["items"][0]
            self.assertTrue(archived["archived_at"])
            self.assertFalse(archived["can_archive"])
            self.assertEqual(archived["steps"], item["steps"])

    def test_archived_duplicate_receive_is_explicit_and_never_reactivates(self):
        config = configuration()
        config.update(intention="Intent", final_prompt="Prepared prompt")
        entry = dict(name="Original", config=config, source=dict(kind="h3", id="source"))
        identity = self.service.receive([entry])["ids"][0]
        item = self.service._get(identity)
        item["status"] = "succeeded"
        item["steps"]["video"].update(status="succeeded", output={"asset_id":"asset-"+"b"*32})
        item["delivery"] = dict(status="succeeded", key=delivery_material(item)["key"])
        self.service.action("archive", *self.selection(identity))
        timestamp = item["archived_at"]
        response = self.service.receive([entry])
        self.assertEqual(response["added"], 0)
        self.assertEqual(response["ids"], [identity])
        self.assertEqual(response["existing"][0]["archived_at"], timestamp)
        self.assertEqual(item["archived_at"], timestamp)
        self.assertEqual(self.adapter.calls, [])

    def test_duplicate_archive_creates_preparation_with_translation_but_no_old_job(self):
        identity = self.first["id"]
        self.service.action("archive", *self.selection(identity))
        self.service.action("duplicate", *self.selection(identity))
        original, copy = self.service._get(identity), self.service.snapshot()["items"][-1]
        self.assertTrue(original["archived_at"])
        self.assertIsNone(copy["archived_at"])
        self.assertEqual(copy["status"], "preparation")
        self.assertEqual(copy["config"], original["config"])
        self.assertEqual(copy["runtime"]["episode_inputs"], original["runtime"]["episode_inputs"])
        self.assertNotIn("attempt_id", copy["runtime"])
        self.assertNotIn("render_project_id", copy["runtime"])
        self.assertEqual(copy["steps"]["video"]["status"], "pending")
        self.assertEqual(self.adapter.calls, [])

    def test_archived_items_cannot_edit_retry_or_publish_but_can_be_removed(self):
        identity = self.first["id"]
        self.service.action("archive", *self.selection(identity))
        for action in ("edit", "retry", "cancel", "archive"):
            with self.subTest(action=action), self.assertRaises(FactoryConflict):
                self.service.action(action, *self.selection(identity))
        with self.assertRaises(FactoryConflict): self.service.launch(*self.selection(identity))
        with self.assertRaises(FactoryConflict): self.service.update(*self.selection(identity), changes={"name":"New"})
        with self.assertRaises(FactoryConflict): self.service.retry_delivery(identity)
        # Archived records never re-export, even if their old material changed.
        self.service._state["items"] = [self.service._get(identity)]
        self.service._get(identity)["delivery"]["key"] = "old-key"
        self.service._start_delivery()
        self.service.outputs.plan.assert_not_called()
        self.service.action("remove", *self.selection(identity))
        self.assertEqual(self.service.snapshot()["items"], [])
        self.assertEqual(self.adapter.calls, [])

    def test_restore_selection_requires_only_archived_items_atomically(self):
        self.service.action("archive", *self.selection(self.first["id"]))
        before = deepcopy(self.service._state)
        with self.assertRaises(FactoryConflict):
            self.service.action("restore", *self.selection(self.first["id"], self.second["id"]))
        self.assertEqual(self.service._state, before)

    def test_http_archive_restore_and_stale_request_contract(self):
        app = FastAPI()
        app.include_router(video_factory_router(self.service, validate_image=lambda _: "image/png"))
        with TestClient(app) as client:
            identity = self.first["id"]
            ids, revisions = self.selection(identity)
            body = dict(ids=ids, revisions=revisions)
            response = client.post("/api/video-factory/actions/archive", json=body)
            self.assertEqual(response.status_code, 200)
            archived = next(i for i in response.json()["items"] if i["id"] == identity)
            self.assertTrue(archived["archived_at"])
            self.assertFalse(archived["can_archive"])
            self.assertEqual(client.post("/api/video-factory/actions/restore", json=body).status_code, 409)
            restored = client.post("/api/video-factory/actions/restore", json=dict(ids=ids, revisions={identity:archived["revision"]}))
            self.assertEqual(restored.status_code, 200)
            self.assertIsNone(restored.json()["items"][0]["archived_at"])
            self.assertEqual(self.adapter.calls, [])


if __name__ == "__main__":
    unittest.main()
