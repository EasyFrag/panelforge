"""User-run contracts for bounded factory reads; no real workflows or services."""
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.video_factory import VideoFactoryService, FactoryConflict
from panelforge.domain.video_factory import configuration, new_item
from panelforge.features.lab.video_factory_web import video_factory_router
from tests.test_video_factory import MemoryStore, FakeWorkflows


class FactoryViewsTest(unittest.TestCase):
    def setUp(self):
        self.service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
        self.items = [new_item("Item " + str(i), configuration(), {"kind": "image", "id": str(i)}, str(i)) for i in range(125)]
        self.service._state["items"] = self.items

    def test_summary_never_copies_or_serializes_outputs(self):
        class Uncopyable:
            def __deepcopy__(self, memo):
                raise AssertionError("Heavy output was copied")
        self.items[0]["history"] = Uncopyable()
        self.items[0]["steps"]["plan"]["output"]["text"] = Uncopyable()
        with patch.object(self.service, "snapshot", side_effect=AssertionError("Full snapshot")):
            value = self.service.summary()
        self.assertEqual(value["counts"]["preparation"], 125)
        self.assertNotIn("items", value)
        self.assertLess(len(json.dumps(value)), 500)

    def test_pages_omit_prompts_history_and_full_settings(self):
        self.items[0]["history"] = [{"text": "private " * 10000}]
        self.items[0]["steps"]["plan"]["output"]["text"] = "private plan"
        with patch.object(self.service, "snapshot", side_effect=AssertionError("Full snapshot")):
            value = self.service.browse(limit=20)
        self.assertEqual(len(value["items"]), 20)
        self.assertEqual(len(value["inventory"]), 125)
        self.assertEqual(value["page"]["total"], 125)
        encoded = json.dumps(value)
        self.assertNotIn("private", encoded)
        self.assertNotIn("history", encoded)
        self.assertNotIn("source_config", encoded)
        self.assertNotIn("render", value["items"][0]["config"])
        self.assertEqual(value["items"][0]["config"]["social"]["language"], self.items[0]["config"]["social"]["language"])
        page2 = self.service.browse(offset=20, limit=20)
        self.assertEqual(page2["items"][0]["id"], self.items[20]["id"])
        self.assertEqual(page2["items"][0]["position"], 21)

    def test_detail_is_explicit_and_detached_from_durable_state(self):
        self.items[0]["steps"]["plan"]["output"]["text"] = "full plan"
        detail = self.service.item_detail(self.items[0]["id"])
        self.assertEqual(detail["steps"]["plan"]["output"]["text"], "full plan")
        detail["config"]["intention"] = "edited in browser"
        self.assertNotEqual(self.items[0]["config"]["intention"], "edited in browser")

    def test_unchanged_poll_sends_no_page_or_global_inventory(self):
        value = self.service.browse()
        result = self.service.browse(known_revision=value["revision"])
        self.assertTrue(result["unchanged"])
        self.assertNotIn("items", result)
        self.assertNotIn("inventory", result)
        self.assertEqual(result["counts"], value["counts"])

    def test_anchor_and_details_allow_opening_an_item_outside_first_page(self):
        item = self.items[110]
        value = self.service.browse(focus=item["id"], anchor=True)
        self.assertEqual(value["page"]["offset"], 100)
        self.assertEqual(value["detail"]["id"], item["id"])
        unchanged = self.service.browse(offset=100, focus=item["id"], detail_revision=item["revision"])
        self.assertNotIn("detail", unchanged)

    def test_newest_sort_keeps_episode_scenes_together(self):
        self.items = self.items[:4]
        self.service._state["items"] = self.items
        for i, item in enumerate(self.items):
            item["status"] = "succeeded"
            item["steps"]["video"]["finished_at"] = f"2026-10-26T10:0{i}:00Z"
        self.items[0]["source"] = {"kind": "episode", "id": "story", "index": 0}
        self.items[3]["source"] = {"kind": "episode", "id": "story", "index": 1}
        value = self.service.browse(tab="results", sort="newest")
        self.assertEqual([i["id"] for i in value["items"]], [self.items[i]["id"] for i in (0, 3, 2, 1)])

    def test_filter_counts_and_out_of_range_page(self):
        self.items[100]["status"] = "failed"
        self.items[100]["steps"]["plan"]["status"] = "failed"
        value = self.service.browse(tab="results", filter="failed", offset=500)
        self.assertEqual(value["page"]["offset"], 0)
        self.assertEqual(len(value["items"]), 1)
        self.assertEqual(value["error_count"], 1)
        self.assertEqual(value["counts"]["preparation"], 124)

    def test_descriptor_cache_updates_after_save_and_keeps_conflict_checks(self):
        first = self.service.browse()
        item = self.items[100]
        revision = item["revision"]
        with patch.object(self.service, "snapshot", side_effect=AssertionError("Full snapshot")):
            receipt = self.service.update([item["id"]], {item["id"]: revision}, {"name": "Changed"}, compact=True)
        self.assertNotIn("items", receipt["state"])
        second = self.service.browse()
        self.assertGreater(second["inventory"][100]["revision"], first["inventory"][100]["revision"])
        with self.assertRaises(FactoryConflict):
            self.service.update([item["id"]], {item["id"]: revision}, {"name": "Stale"}, compact=True)

    def test_http_compact_reads_and_legacy_snapshot_coexist(self):
        app = FastAPI()
        app.include_router(video_factory_router(self.service, validate_image=lambda _: "image/png"))
        with TestClient(app) as client:
            self.assertEqual(len(client.get("/api/video-factory").json()["items"]), 125)
            with patch.object(self.service, "snapshot", side_effect=AssertionError("Full snapshot")):
                self.assertEqual(client.get("/api/video-factory/summary").status_code, 200)
                page = client.get("/api/video-factory/browse?offset=50&limit=10").json()
                self.assertEqual(len(page["items"]), 10)
                item = self.items[100]
                response = client.patch("/api/video-factory/items?compact=true", json=dict(
                    ids=[item["id"]], revisions={item["id"]: item["revision"]}, changes={"name": "New"}))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("items", response.json()["state"])
            self.assertEqual(client.get("/api/video-factory/browse?limit=100000").status_code, 422)
            self.assertEqual(client.get("/api/video-factory/browse?offset=-1").status_code, 422)
            self.assertEqual(client.get("/api/video-factory/browse?tab=unknown").status_code, 422)
            self.assertEqual(client.get("/api/video-factory/items/missing").status_code, 404)

    def test_monitoring_keeps_pending_work_outside_the_page(self):
        class Monitor:
            def snapshot(self, adapter, state, **options):
                self.identities = {i["id"] for i in state["items"]}
                return {"items": {i["id"]: {} for i in state["items"]}}
        monitor = Monitor()
        self.service.monitoring = monitor
        self.items[110]["status"] = "queued"
        value = self.service.browse(limit=10)
        self.assertIn(self.items[110]["id"], monitor.identities)
        self.assertNotIn(self.items[110]["id"], value["monitoring"]["items"])
        self.assertEqual(len(value["monitoring"]["items"]), 10)

    def test_page_preserves_paused_queue_explanation(self):
        self.items[0]["status"] = "queued"
        self.service._state["paused"] = True
        row = self.service.browse(tab="production")["items"][0]
        self.assertEqual(row["waiting_reason"], "File en pause")

    def test_machine_changes_refresh_waiting_reason_without_item_revision(self):
        self.items[0]["status"] = "queued"
        first = self.service.browse(tab="production")
        self.service.adapter.machines = {"local_gpu": {"state": "cooling"}}
        second = self.service.browse(tab="production", known_revision=first["revision"])
        self.assertTrue(second["unchanged"])
        self.assertEqual(second["waiting_reasons"][self.items[0]["id"]], "Refroidissement de la machine")
