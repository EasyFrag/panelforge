"""User-run factory tests. No real model, GPU, ComfyUI or production workspace."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory import VideoFactoryService, FactoryConflict
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.video_factory import (
    PRESETS, configuration, apply_preset, new_item, next_steps, settle, invalidate, readiness,
)
from panelforge.infrastructure.storage.video_factory import LocalVideoFactoryStore


class MemoryStore:
    def __init__(self): self.value = dict(schema_version=1, revision=0, paused=False, items=[])
    def load(self): return deepcopy(self.value)
    def save(self, value): self.value = deepcopy(value)


class FakeWorkflows:
    def __init__(self):
        self.calls = []
        self.available = ["local_gpu", "remote_gpu"]
        self.machines = {}
    def validate(self, config, launching=False): pass
    def source_issues(self, item): return item.get("source_issues", [])
    def available_lanes(self): return self.available
    def lane(self, item, stage): return "remote_gpu" if stage == "video" else "local_gpu"
    def run(self, item, stage, checkpoint, cancelled, progress):
        self.calls.append((item["id"], stage))
        checkpoint(child_id="persisted-before-completion")
        return {"text": stage, "asset_id": "asset-video"} if stage == "video" else {"text": stage}
    def cancel(self, item): self.calls.append((item["id"], "cancel"))
    recoverable = staticmethod(FactoryWorkflows.recoverable)


class DeferredThread:
    pending = []
    def __init__(self, *, target, args=(), **kwargs): self.target, self.args = target, args
    def start(self): self.pending.append(self)
    @classmethod
    def finish(cls, index=0):
        thread = cls.pending.pop(index)
        thread.target(*thread.args)


class FactoryDomainTest(unittest.TestCase):
    def test_four_presets_image_role_lips_and_instagram_defaults(self):
        self.assertEqual(set(PRESETS), {"source", "lips", "little_men", "custom"})
        config = configuration()
        config["references"] = [dict(asset_id="asset-image", role="unassigned")]
        self.assertTrue(readiness(config))
        lips = apply_preset(config, "lips", config)
        self.assertFalse(readiness(lips))
        self.assertEqual(lips["references"][0]["role"], "last_frame")
        self.assertEqual(lips["shot_count"], 1)
        self.assertEqual(lips["render"]["recipe"]["id"], "minimax-h3-bunny")
        self.assertIn("Motion_Repair", lips["render"]["video_loras"]["entries"][0]["name"])
        self.assertEqual(lips["social"], dict(enabled=False, language="en", variant_count=3,
                                            model_id="local::unsloth/gemma-4-31B-it-qat-GGUF"))
        little = apply_preset(config, "little_men", config)
        self.assertEqual(little["references"][0]["role"], "first_frame")
        self.assertIn("main géante", little["intention"])
        self.assertEqual(apply_preset(lips, "source", config), config)
        self.assertEqual(config["references"][0]["role"], "unassigned")

    def test_dlss_failure_does_not_block_social_or_discard_video(self):
        config = configuration(); config["social"]["enabled"] = True; config["dlss"]["enabled"] = True
        item = new_item("Vidéo", config, {}, "dedupe"); item["status"] = "queued"
        for stage in ("plan", "prompt", "video"): item["steps"][stage]["status"] = "succeeded"
        item["steps"]["video"]["output"] = {"asset_id": "asset-video"}
        item["steps"]["dlss"]["status"] = "failed"
        settle(item)
        self.assertEqual(next_steps(item), ["social"])
        item["steps"]["social"]["status"] = "succeeded"; settle(item)
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["steps"]["video"]["output"]["asset_id"], "asset-video")

    def test_undo_restores_matching_video_and_child_identity(self):
        original = configuration(); original["intention"] = "Une personne marche."
        item = new_item("Vidéo", original, {}, "dedupe")
        item["steps"]["video"].update(status="succeeded", output={"asset_id": "asset-kept"})
        item["runtime"] = {"render_project_id": "render-kept", "attempt_id": "attempt-kept"}
        item["config"]["render"]["settings"]["duration_seconds"] = 10
        invalidate(item, original)
        edited = deepcopy(item["config"])
        item["config"] = deepcopy(original)
        invalidate(item, edited)
        self.assertEqual(item["steps"]["video"]["status"], "succeeded")
        self.assertEqual(item["steps"]["video"]["output"]["asset_id"], "asset-kept")
        self.assertEqual(item["runtime"]["attempt_id"], "attempt-kept")

    def test_instagram_enable_and_render_change_invalidate_only_dependents(self):
        config = configuration(); config["intention"] = "Une personne marche."
        item = new_item("Vidéo", config, {}, "dedupe")
        for stage in ("plan", "prompt", "video"):
            item["steps"][stage].update(status="succeeded", output={"text": stage})
        item["runtime"] = dict(session_id="prompt-child", attempt_id="attempt-old", render_project_id="render-old")
        item["config"]["social"]["enabled"] = True
        self.assertEqual(invalidate(item, config), {"social"})
        self.assertEqual(item["steps"]["video"]["status"], "succeeded")
        before = deepcopy(item["config"])
        item["config"]["render"]["settings"]["duration_seconds"] = 10
        self.assertEqual(invalidate(item, before), {"video", "dlss", "social"})
        self.assertEqual(item["steps"]["prompt"]["status"], "succeeded")
        self.assertEqual(item["runtime"], {"session_id": "prompt-child"})
        self.assertEqual(item["history"][-1]["stage"], "video")


class FactoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.store, self.adapter = MemoryStore(), FakeWorkflows()
        self.service = VideoFactoryService(store=self.store, adapter=self.adapter)
        DeferredThread.pending = []
        self.thread_patch = patch("panelforge.application.video_factory.Thread", DeferredThread)
        self.thread_patch.start(); self.addCleanup(self.thread_patch.stop)

    def receive(self, name="Vidéo", final=False, refs=1, issues=None):
        config = configuration(); config["intention"] = name
        config["references"] = [dict(asset_id=f"asset-{i}", role="first_frame" if i == 0 else "last_frame") for i in range(refs)]
        if final: config["final_prompt"] = "A prepared final video prompt."
        result = self.service.receive([dict(name=name, source={"kind": "h3", "id": name}, config=config, issues=issues or [])])
        return result["ids"][0]

    def select(self, *ids):
        revisions = {i["id"]: i["revision"] for i in self.service.snapshot()["items"] if i["id"] in ids}
        return list(ids), revisions

    def item(self, identity): return next(i for i in self.service.snapshot()["items"] if i["id"] == identity)

    def test_receive_is_idempotent_and_never_launches(self):
        first = self.receive(); again = self.receive()
        self.assertEqual(first, again)
        self.assertEqual(len(self.service.snapshot()["items"]), 1)
        self.service.dispatch()
        self.assertFalse(DeferredThread.pending)
        self.assertFalse(self.adapter.calls)
        self.assertEqual(self.store.value["items"][0]["status"], "preparation")

    def test_bulk_preset_is_atomic_when_any_row_is_incompatible(self):
        first, second = self.receive("A"), self.receive("B", refs=2)
        before = self.service.snapshot()
        with self.assertRaises(ValueError): self.service.update(*self.select(first, second), preset="lips")
        self.assertEqual(self.service.snapshot(), before)

    def test_bulk_changes_preserve_untouched_fields_and_can_be_undone(self):
        first, second = self.receive("A"), self.receive("B")
        before = [self.item(i)["config"] for i in (first, second)]
        result = self.service.update(*self.select(first, second), changes={"social": {"enabled": True}})
        for index, identity in enumerate((first, second)):
            item = self.item(identity)
            self.assertEqual(item["config"]["intention"], before[index]["intention"])
            self.assertEqual(item["config"]["render"], before[index]["render"])
            self.assertEqual(item["config"]["social"]["language"], "en")
            self.assertEqual(item["config"]["preset"], "custom")
        self.service.update([first, second], result["revisions"], replacements=result["undo"])
        self.assertEqual([self.item(i)["config"] for i in (first, second)], before)

    def test_stale_and_missing_revisions_cannot_overwrite(self):
        identity = self.receive(); ids, old = self.select(identity)
        self.service.update(ids, old, changes={"shot_count": 2})
        with self.assertRaises(FactoryConflict): self.service.update(ids, old, changes={"shot_count": 3})
        with self.assertRaises(FactoryConflict): self.service.launch(ids, None)
        self.assertEqual(self.item(identity)["config"]["shot_count"], 2)

    def test_changing_intention_clears_stale_final_but_social_keeps_it(self):
        identity = self.receive(final=True)
        self.service.update(*self.select(identity), changes={"social": {"enabled": True}})
        self.assertEqual(self.item(identity)["steps"]["prompt"]["status"], "succeeded")
        self.service.update(*self.select(identity), changes={"intention": "A different scene."})
        self.assertEqual(self.item(identity)["config"]["final_prompt"], "")
        self.assertEqual(self.item(identity)["steps"]["prompt"]["status"], "pending")

    def test_machine_order_skips_blocked_first_row_then_returns_to_it(self):
        first = self.receive("A", final=True); second = self.receive("B")
        self.service.launch(*self.select(first, second))
        self.adapter.available = ["local_gpu"]
        self.service.dispatch()
        self.assertEqual(DeferredThread.pending[0].args, ("local_gpu", second, "plan"))
        DeferredThread.finish()
        self.adapter.available = ["local_gpu", "remote_gpu"]
        self.service.dispatch()
        self.assertEqual({t.args for t in DeferredThread.pending},
                         {("remote_gpu", first, "video"), ("local_gpu", second, "prompt")})

    def test_pause_finishes_active_step_without_chaining(self):
        identity = self.receive()
        self.service.launch(*self.select(identity)); self.service.dispatch()
        self.service.action("pause"); DeferredThread.finish(); self.service.dispatch()
        self.assertFalse(DeferredThread.pending)
        self.assertEqual(self.item(identity)["steps"]["plan"]["status"], "succeeded")
        self.assertEqual(self.item(identity)["steps"]["prompt"]["status"], "pending")
        self.service.action("resume"); self.service.dispatch()
        self.assertEqual(DeferredThread.pending[0].args[-1], "prompt")

    def test_cancel_is_not_blocked_by_progress_since_last_browser_poll(self):
        identity = self.receive(final=True)
        self.service.launch(*self.select(identity))
        ids, previous_revisions = self.select(identity)
        self.service.dispatch()
        self.service.action("cancel", ids, previous_revisions)
        self.assertTrue(self.item(identity)["cancel_requested"])

    def test_cancel_queued_and_retry_keep_prepared_prompt(self):
        identity = self.receive(final=True)
        self.service.launch(*self.select(identity)); self.service.action("cancel", *self.select(identity))
        self.assertEqual(self.item(identity)["status"], "cancelled")
        self.service.action("retry", *self.select(identity))
        item = self.item(identity)
        self.assertEqual(item["steps"]["prompt"]["status"], "succeeded")
        self.assertEqual(item["steps"]["plan"]["status"], "skipped")
        self.assertEqual(next_steps(item), ["video"])
        self.assertTrue(item["runtime"]["explicit_retry"])

    def test_restart_reconciles_child_even_with_pause_and_busy_machine(self):
        identity = self.receive(final=True)
        self.service.launch(*self.select(identity)); self.service.dispatch()
        item = self.store.value["items"][0]
        item["runtime"] = {"render_project_id": "h3-existing", "attempt_id": "attempt-existing"}
        self.store.value["paused"] = True
        self.adapter.available = []
        restarted = VideoFactoryService(store=self.store, adapter=self.adapter)
        DeferredThread.pending = []; restarted.dispatch()
        self.assertEqual(DeferredThread.pending[0].args, ("remote_gpu", identity, "video"))
        self.assertEqual(restarted.snapshot()["items"][0]["runtime"]["attempt_id"], "attempt-existing")

    def test_restart_does_not_blindly_resubmit_interrupted_llm(self):
        identity = self.receive(); self.service.launch(*self.select(identity)); self.service.dispatch()
        restarted = VideoFactoryService(store=self.store, adapter=self.adapter)
        DeferredThread.pending = []; restarted.dispatch()
        self.assertFalse(DeferredThread.pending)
        item = restarted.snapshot()["items"][0]
        self.assertEqual(item["status"], "failed")
        self.assertIn("redémarrage", item["steps"]["plan"]["error"])

    def test_duplicate_preserves_missing_story_reference_guard(self):
        identity = self.receive(issues=["Image de référence manquante dans l’histoire."])
        self.service.action("duplicate", *self.select(identity))
        duplicate = self.service.snapshot()["items"][-1]
        self.assertFalse(duplicate["ready"])
        with self.assertRaises(ValueError): self.service.launch(*self.select(duplicate["id"]))

    def test_order_revision_guards_concurrent_additions(self):
        first, second = self.receive("A"), self.receive("B")
        version = self.service.snapshot()["revision"]
        self.receive("C")
        with self.assertRaises(FactoryConflict): self.service.reorder([second, first], version)


class FactoryStoreTest(unittest.TestCase):
    def test_atomic_state_round_trip_preserves_ids_and_pause(self):
        with TemporaryDirectory() as directory:
            store = LocalVideoFactoryStore(directory)
            state = store.load(); state.update(paused=True, revision=7)
            item = new_item("Persistante", configuration(), {}, "key")
            item["runtime"] = {"attempt_id": "attempt-1", "dlss_job_id": "dlss-1"}
            state["items"].append(item); store.save(state)
            self.assertEqual(LocalVideoFactoryStore(directory).load(), state)
            self.assertEqual(list(Path(directory).rglob("*.tmp")), [])


class FactoryWorkflowTest(unittest.TestCase):
    def test_five_story_scenes_are_five_drafts_and_capture_does_not_start_jobs(self):
        from tests.test_episodes import SCENARIO
        from panelforge.domain.episodes import initial_episode
        scenario = deepcopy(SCENARIO)
        scenario["scenes"] *= 5
        story = dict(project_id="story-" + "a" * 32, clip_seconds=8,
                     document={"scenario": scenario}, revisions=[{"revision": 1}])
        episode = initial_episode(story, "episode-" + "b" * 32)
        for ref in episode["references"]: ref["image_asset_id"] = "asset-image"
        episodes = NS(store=NS(get=lambda identity: deepcopy(episode)))
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=Mock(), dlss=Mock(),
                                   social=Mock(), episodes=episodes, assets=Mock(), coordinator=None)
        entries = adapter.capture_episode(episode["episode_id"])
        self.assertEqual(len(entries), 5)
        self.assertEqual(len({e["source"]["scene_id"] for e in entries}), 5)
        self.assertTrue(all(e["source"]["id"] == episode["episode_id"] for e in entries))
        self.assertTrue(all(e["config"]["dlss"]["enabled"] for e in entries))
        self.assertTrue(all(not e["config"]["social"]["enabled"] for e in entries))
        adapter.prompt_lab.create_session.assert_not_called()
        adapter.render.prepare_attempt.assert_not_called()
        adapter.social.create_project.assert_not_called()

    def test_existing_successful_video_is_reconciled_without_preparing_or_queuing(self):
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=Mock(), dlss=None,
                                   social=None, episodes=None, assets=None, coordinator=None)
        attempt = NS(attempt_id="existing", status=NS(value="succeeded"), output_asset_id="asset-video", keyframes=[])
        project = NS(project_id="h3-existing", input_mode=NS(value="fl2va"), attempt=lambda identity: attempt)
        adapter.render.get.return_value = project
        adapter.render.projects.get.return_value = project
        adapter.render.run_timeout = 5
        item = new_item("Reprise", configuration(), {}, "key")
        item["runtime"] = dict(render_project_id=project.project_id, attempt_id=attempt.attempt_id)
        output = adapter._video(item, Mock(), lambda: False, Mock())
        self.assertEqual(output["asset_id"], "asset-video")
        adapter.render.prepare_attempt.assert_not_called()
        adapter.render.queue_attempt.assert_not_called()
        adapter.render.execute_attempt.assert_not_called()


if __name__ == "__main__": unittest.main()