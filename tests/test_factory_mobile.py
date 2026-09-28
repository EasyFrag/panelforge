"""Mobile regressions for user execution; all workers and push transports are fake."""
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import base64
import json
import unittest

from fastapi.testclient import TestClient
from panelforge.application.factory_mobile import FactoryMobile
from panelforge.application.video_factory import VideoFactoryService, FactoryConflict
from panelforge.domain.factory_mobile import mobile_view, alert_conditions, media_asset, active_run_key
from panelforge.domain.factory_cycle import admit_cycle, sync_cycle
from panelforge.features.lab.factory_mobile_web import create_mobile_app
from panelforge.infrastructure.factory_mobile import LocalMobileStore, WebPushSender
from tests.test_factory_monitoring import card, inputs, NOW, STAMP
from tests.test_video_factory import MemoryStore, FakeWorkflows, DeferredThread


class MobileStore:
    def __init__(self):
        self.value = {}
    def load(self): return deepcopy(self.value)
    def save(self, value): self.value = deepcopy(value)


def subscription():
    return dict(endpoint="https://fcm.googleapis.com/fcm/send/fake-test-endpoint",
                keys={k: base64.urlsafe_b64encode(v).decode().rstrip("=")
                      for k, v in dict(p256dh=b"\x04" + b"x" * 64, auth=b"a" * 16).items()})


class Sender:
    available, public_key, warning = True, "test-public-key", None
    validate = staticmethod(WebPushSender.validate)
    def __init__(self): self.calls, self.outcome = [], "sent"
    def send(self, sub, message, origin):
        self.calls.append((deepcopy(sub), deepcopy(message), origin))
        return self.outcome


def fixture():
    item = card("Mobile", final=True)
    state, _, _, machines = inputs([item])
    state["revision"] = 1
    machines["machines"]["local_gpu"]["temperature_c"] = 45
    machines["machines"]["remote_gpu"]["temperature_c"] = 60
    factory = Mock()
    factory.snapshot.side_effect = lambda: deepcopy(state)
    factory.adapter = SimpleNamespace(monitor_snapshot=machines, assets=Mock())
    return factory, state, machines, item


class MobileViewTest(unittest.TestCase):
    def test_projection_excludes_prompts_paths_and_runtime_secrets(self):
        _, state, machines, item = fixture()
        item["config"]["intention"] = "private-story"
        item["runtime"]["password"] = "secret-runtime"
        item["steps"]["video"]["error"] = "C:/private/file"
        result = mobile_view(state, machines, NOW)
        text = json.dumps(result)
        for secret in ("private-story", "secret-runtime", "C:/private/file"):
            self.assertNotIn(secret, text)
        self.assertEqual(result["work"][0]["name"], item["name"])
        self.assertEqual(result["machines"][1]["temperature_c"], 60)

    def test_mobile_media_remains_raw_after_dlss_finishes(self):
        _, _, _, item = fixture()
        self.assertIsNone(media_asset(item, "video"))
        item["steps"]["video"].update(status="succeeded", output={"asset_id": "raw"})
        self.assertEqual(media_asset(item, "video"), "raw")
        item["steps"]["dlss"].update(status="succeeded", output={"asset_id": "upscaled"})
        self.assertEqual(media_asset(item, "video"), "raw")
        self.assertIsNone(media_asset(item, "../private"))


    def test_dlss_only_result_remains_visible_without_a_mobile_playback_url(self):
        _, state, machines, item = fixture()
        item["steps"]["video"].update(status="succeeded", output={"asset_id": "raw"})
        item["steps"]["dlss"].update(status="succeeded", output={"asset_id": "upscaled"})
        before = deepcopy(state)
        result = mobile_view(state, machines, NOW)
        self.assertEqual(result["results"][0]["quality"], "Vidéo brute")
        self.assertEqual(result["results"][0]["video_url"], f"/api/items/{item['id']}/video")
        self.assertEqual(state, before)
        item["steps"]["video"]["output"] = None
        result = mobile_view(state, machines, NOW)
        self.assertEqual(result["result_total"], 1)
        self.assertEqual(result["results"][0]["id"], item["id"])
        self.assertIsNone(result["results"][0]["video_url"])
        self.assertIsNone(media_asset(item, "video"))
        item["steps"]["video"].update(status="running", output={"asset_id": "old-raw"})
        self.assertIsNone(media_asset(item, "video"))

    def test_stale_telemetry_keeps_estimate_but_suppresses_end_and_thermal_alerts(self):
        _, state, machines, _ = fixture()
        state["monitoring"] = dict(remaining_seconds=600, status="running")
        machines["machines"]["remote_gpu"]["temperature_c"] = 99
        result = mobile_view(state, machines, NOW + 30)
        self.assertTrue(result["stale"])
        self.assertEqual(result["remaining_seconds"], 600)
        self.assertIsNone(result["finish_at"])
        self.assertFalse(alert_conditions(result, result["thresholds"]))

    def test_result_pagination_preserves_total_and_includes_archived_videos(self):
        _, state, machines, item = fixture()
        for i in range(3):
            value = deepcopy(item);value["id"] = f"result-{i}";value["archived_at"] = STAMP
            value["steps"]["video"].update(status="succeeded", output={"asset_id": "raw"})
            state["items"].append(value)
        result = mobile_view(state, machines, NOW, result_limit=2)
        self.assertEqual(result["result_total"], 3)
        self.assertEqual(len(result["results"]), 2)


class MobileNotificationTest(unittest.TestCase):
    def setUp(self):
        self.factory, self.state, self.machines, self.item = fixture()
        self.store, self.sender = MobileStore(), Sender()
        self.now = NOW
        self.service = FactoryMobile(self.factory, self.store, self.sender, clock=lambda: self.now)
        self.thresholds = dict(local_gpu=80, remote_gpu=85)
        self.identity = self.service.subscribe(subscription(), self.thresholds, "https://pc.tailtest.ts.net")["id"]

    def notify(self):
        self.machines["observed_at"] = datetime.fromtimestamp(self.now, UTC).isoformat()
        self.service.notify_once()

    def test_threshold_hysteresis_deduplication_and_restart(self):
        remote = self.machines["machines"]["remote_gpu"]
        remote["temperature_c"] = 90
        self.notify(); self.notify()
        self.assertEqual(len(self.sender.calls), 1)
        self.service = FactoryMobile(self.factory, self.store, self.sender, clock=lambda: self.now)
        remote["temperature_c"] = 84
        self.notify()
        self.assertEqual(len(self.sender.calls), 1)
        remote["temperature_c"] = 81
        self.notify()
        remote["temperature_c"] = 90
        self.notify()
        self.assertEqual(len(self.sender.calls), 2)

    def test_failed_send_retries_without_marking_alert_as_delivered(self):
        self.machines["machines"]["remote_gpu"]["temperature_c"] = 90
        self.sender.outcome = "retry"
        self.notify(); self.notify()
        self.assertEqual(len(self.sender.calls), 1)
        self.assertTrue(self.service.push_config(self.identity)["last_error"])
        self.now += 61; self.sender.outcome = "sent"
        self.notify()
        self.assertEqual(len(self.sender.calls), 2)
        self.assertIsNone(self.service.push_config(self.identity)["last_error"])

    def test_expired_subscription_is_removed_and_disable_is_persistent(self):
        self.machines["machines"]["remote_gpu"]["temperature_c"] = 90
        self.sender.outcome = "expired"
        self.notify()
        self.assertEqual(self.store.value, {})
        identity = self.service.subscribe(subscription(), self.thresholds, "https://pc.tailtest.ts.net")["id"]
        self.service.unsubscribe(identity)
        self.assertEqual(self.store.value, {})

    def test_stale_measurement_does_not_rearm_alarm(self):
        self.machines["machines"]["remote_gpu"]["temperature_c"] = 90
        self.notify()
        self.now += 30
        self.service.notify_once()
        self.notify()
        self.assertEqual(len(self.sender.calls), 1)

    def test_temporarily_missing_sensor_does_not_rearm_alarm(self):
        remote = self.machines["machines"]["remote_gpu"]
        remote["temperature_c"] = 90
        self.notify()
        remote["temperature_c"] = None
        self.notify()
        remote["temperature_c"] = 90
        self.notify()
        self.assertEqual(len(self.sender.calls), 1)

    def test_old_failures_are_not_notified_on_subscription_but_new_failures_are(self):
        self.item["status"] = "failed"
        self.item["steps"]["video"]["status"] = "failed"
        self.service.unsubscribe(self.identity)
        self.service.subscribe(subscription(), self.thresholds, "https://pc.tailtest.ts.net")
        self.notify()
        self.assertEqual(len(self.sender.calls), 0)
        self.item["steps"]["video"]["started_at"] = STAMP
        self.notify(); self.notify()
        self.assertEqual(len(self.sender.calls), 1)

    def test_corrupt_notification_journal_is_not_overwritten(self):
        store = Mock();store.load.side_effect = ValueError("corrupt")
        broken = FactoryMobile(self.factory, store, self.sender, clock=lambda: NOW)
        self.assertFalse(broken.push_config()["available"])
        with self.assertRaises(ValueError):
            broken.subscribe(subscription(), self.thresholds, "https://pc.tailtest.ts.net")
        store.save.assert_not_called()

    def test_push_endpoint_cannot_target_local_network_or_arbitrary_web_servers(self):
        for endpoint in ("http://fcm.googleapis.com/test", "https://127.0.0.1/test",
                         "https://192.168.1.1/test", "https://example.org/test",
                         "https://fcm.googleapis.com:8188/test", "https://name@fcm.googleapis.com/test"):
            with self.subTest(endpoint=endpoint):
                value = subscription();value["endpoint"] = endpoint
                with self.assertRaises(ValueError): WebPushSender.validate(value)

    def test_journal_round_trip(self):
        with TemporaryDirectory() as directory:
            store = LocalMobileStore(directory)
            store.save(self.store.value)
            self.assertEqual(store.load(), self.store.value)


class MobileStopTest(unittest.TestCase):
    def setUp(self):
        DeferredThread.pending.clear()
        self.addCleanup(DeferredThread.pending.clear)

    def make_factory(self):
        factory = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
        active, queued = card("active", final=True), card("queued", final=True)
        active["status"] = "active"
        active["steps"]["video"].update(status="running", started_at=STAMP)
        factory._state["items"] = [active, queued]
        factory._workers["remote_gpu"] = (active["id"], "video")
        admit_cycle(factory._state, [active, queued]);sync_cycle(factory._state)
        return factory, active, queued

    def test_stop_pauses_queue_and_cancels_only_confirmed_active_cards(self):
        factory, active, queued = self.make_factory()
        with patch("panelforge.application.video_factory.Thread", DeferredThread):
            factory.action("stop", [active["id"]], {active["id"]: active["revision"]})
        self.assertTrue(factory._state["paused"])
        self.assertTrue(active["cancel_requested"])
        self.assertEqual(queued["status"], "queued")
        self.assertFalse(queued["cancel_requested"])
        factory.action("resume")
        self.assertFalse(factory._state["paused"])

    def test_changed_active_selection_or_revision_leaves_everything_unchanged(self):
        for wrong in ("revision", "selection"):
            factory, active, queued = self.make_factory()
            before = deepcopy(factory._state)
            ids = [queued["id"]] if wrong == "selection" else [active["id"]]
            revisions = {i["id"]: i["revision"] for i in (active, queued)}
            if wrong == "revision": revisions[active["id"]] -= 1
            with self.assertRaises(FactoryConflict):
                factory.action("stop", ids, revisions)
            self.assertEqual(factory._state, before)
            self.assertEqual(factory.adapter.calls, [])



    def test_progress_update_does_not_invalidate_stop_but_a_new_stage_does(self):
        factory, active, _ = self.make_factory()
        token, revision = active_run_key(active), active["revision"]
        active["revision"] += 1
        with patch("panelforge.application.video_factory.Thread", DeferredThread):
            factory.action("stop", [active["id"]], {active["id"]: revision},
                           active_runs={active["id"]: token})
        self.assertTrue(factory._state["paused"])
        factory, active, _ = self.make_factory()
        token = active_run_key(active)
        active["steps"]["video"]["started_at"] = "2026-09-28T12:00:00Z"
        before = deepcopy(factory._state)
        with self.assertRaises(FactoryConflict):
            factory.action("stop", [active["id"]], {active["id"]: active["revision"]},
                           active_runs={active["id"]: token})
        self.assertEqual(factory._state, before)


class MobileHttpTest(unittest.TestCase):
    def setUp(self):
        self.factory, self.state, self.machines, self.item = fixture()
        self.service = FactoryMobile(self.factory, MobileStore(), Sender(), clock=lambda: NOW)
        self.service.start = Mock();self.service.stop = Mock()
        self.client = TestClient(create_mobile_app(self.service), base_url="http://localhost")
        self.addCleanup(self.client.close)
        self.headers = {"Origin": "http://localhost", "X-PanelForge-Mobile": "1"}

    def test_mutations_require_same_origin_and_explicit_header(self):
        for headers in ({}, {"Origin": "https://elsewhere.example", "X-PanelForge-Mobile": "1"},
                        {"Origin": "http://localhost"}):
            response = self.client.post("/api/commands/pause", json={}, headers=headers)
            self.assertEqual(response.status_code, 403)
        self.factory.action.assert_not_called()
        response = self.client.post("/api/commands/pause", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.factory.action.assert_called_once_with("pause", [], None)

    def test_only_mobile_surface_is_exposed_and_no_arbitrary_asset_is_served(self):
        for path in ("/api/assets/secret/content", "/api/work-scheduler/settings", "/docs"):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/api/items/unrelated/video").status_code, 404)
        self.factory.adapter.assets.get.assert_not_called()
        self.assertEqual(self.client.post("/api/commands/remove", json={}, headers=self.headers).status_code, 422)

    def test_ranges_stream_raw_bytes_even_when_dlss_is_available(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "video.bin";path.write_bytes(b"0123456789")
            upscaled = Path(directory) / "dlss.bin";upscaled.write_bytes(b"DLSS-LARGE")
            self.item["steps"]["video"].update(status="succeeded", output={"asset_id": "raw"})
            self.item["steps"]["dlss"].update(status="succeeded", output={"asset_id": "upscaled"})
            assets = self.factory.adapter.assets
            assets.get.return_value = SimpleNamespace(media_type="video/mp4")
            assets.verified_path.side_effect = lambda identity: {"raw": path, "upscaled": upscaled}[identity]
            response = self.client.get(f"/api/items/{self.item['id']}/video", headers={"Range": "bytes=2-5"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.content, b"2345")
            assets.get.assert_called_once_with("raw")
            assets.verified_path.assert_called_once_with("raw")
            self.assertEqual(self.client.get(f"/api/items/{self.item['id']}/private").status_code, 404)


    def test_missing_raw_file_never_reads_the_available_dlss_file(self):
        with TemporaryDirectory() as directory:
            upscaled = Path(directory) / "upscaled.mp4"
            upscaled.write_bytes(b"large-dlss-file")
            self.item["steps"]["video"].update(status="succeeded", output={"asset_id": "raw"})
            self.item["steps"]["dlss"].update(status="succeeded", output={"asset_id": "upscaled"})
            assets = self.factory.adapter.assets
            assets.get.return_value = SimpleNamespace(media_type="video/mp4")
            def verified(identity):
                if identity == "raw":
                    raise FileNotFoundError("missing raw video")
                return upscaled
            assets.verified_path.side_effect = verified
            response = self.client.get(f"/api/items/{self.item['id']}/video")
            self.assertEqual(response.status_code, 404)
            assets.get.assert_called_once_with("raw")
            assets.verified_path.assert_called_once_with("raw")
            self.factory.action.assert_not_called()

    def test_pwa_assets_and_notification_validation(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/sw.js").headers["content-type"], "text/javascript; charset=utf-8")
        self.assertEqual(self.client.get("/manifest.webmanifest").json()["display"], "standalone")
        response = self.client.post("/api/push", headers=self.headers, json={
            "subscription": subscription(), "thresholds": {"local_gpu": 10, "remote_gpu": 85}})
        self.assertEqual(response.status_code, 422)
        response = self.client.get("/api/state", headers={"Host": "attacker.example"})
        self.assertEqual(response.status_code, 403)



class MobileThermalHistoryTest(unittest.TestCase):
    def sample(self, offset, temperature):
        return dict(timestamp=datetime.fromtimestamp(NOW + offset, UTC).isoformat(),
                    max_temperature_c=temperature)

    def test_six_hour_projection_preserves_peaks_gaps_and_does_not_expose_events(self):
        from panelforge.domain.factory_mobile import mobile_thermal_history
        raw = dict(bucket_seconds=15, error="C:/private/log", events=[{"operation": "secret prompt"}],
                   series=dict(remote_gpu=[
                       self.sample(-21615, 99), self.sample(-21600, 40),
                       self.sample(-120, 55), self.sample(-120, 96),
                       self.sample(-60, 27), self.sample(0, 84), self.sample(15, 100)],
                       local_gpu=[self.sample(-600, 42), self.sample(0, 38)]))
        before = deepcopy(raw)
        result = mobile_thermal_history(raw, NOW)
        self.assertEqual(result["window_seconds"], 21600)
        self.assertEqual(result["start_at"], NOW - 21600)
        self.assertEqual([m["id"] for m in result["machines"]], ["remote_gpu", "local_gpu"])
        self.assertEqual(result["machines"][0]["points"],
                         [[NOW - 21600, 40], [NOW - 120, 96], [NOW - 60, 27], [NOW, 84]])
        self.assertEqual(result["machines"][1]["points"], [[NOW - 600, 42], [NOW, 38]])
        self.assertTrue(result["warning"])
        self.assertNotIn("C:/private", json.dumps(result))
        self.assertNotIn("secret prompt", json.dumps(result))
        self.assertEqual(raw, before)

    def test_invalid_values_are_omitted_without_inventing_measurements(self):
        from panelforge.domain.factory_mobile import mobile_thermal_history
        points = [self.sample(-15, value) for value in (None, True, float("nan"), float("inf"), -1, 151)]
        points += [dict(timestamp="invalid", max_temperature_c=84), self.sample(0, 84)]
        result = mobile_thermal_history(dict(series=dict(remote_gpu=points)), NOW)
        self.assertEqual(result["machines"][0]["points"], [[NOW, 84]])
        self.assertEqual(result["machines"][1]["points"], [])
        self.assertEqual(result["bucket_seconds"], 15)

    def test_mobile_history_is_read_only_and_independent_of_factory_snapshot(self):
        factory, _, _, _ = fixture()
        history = Mock(return_value=dict(series=dict(remote_gpu=[self.sample(0, 84)])))
        service = FactoryMobile(factory, MobileStore(), Sender(), clock=lambda: NOW, thermal_history=history)
        with TestClient(create_mobile_app(service)) as client:
            response = client.get("/api/thermal-history", headers={"Host": "localhost"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["machines"][0]["points"], [[NOW, 84]])
            self.assertEqual(client.get("/thermal.js", headers={"Host": "localhost"}).status_code, 200)
        history.assert_called_once_with()
        factory.snapshot.assert_not_called()
        factory.action.assert_not_called()

    def test_missing_or_failing_history_has_a_safe_mobile_message(self):
        factory, _, _, _ = fixture()
        for provider in (None, Mock(side_effect=OSError("private filesystem error"))):
            service = FactoryMobile(factory, MobileStore(), Sender(), clock=lambda: NOW, thermal_history=provider)
            value = service.thermal_history()
            self.assertFalse(value["available"])
            self.assertNotIn("private", json.dumps(value))
        factory.snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
