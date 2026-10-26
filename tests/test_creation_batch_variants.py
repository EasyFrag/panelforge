"""User-run regressions for task overlap, immutable variants and delivery receipts."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from uuid import uuid4

from panelforge.application.creation_batch import CreationBatchService, CreationBatchConflict
from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.application.work_context import llm_owner_prefix
from panelforge.application.prompt_lab import CompletionRequest, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain.krea2_art_direction import Krea2ArtDirection
from panelforge.domain.krea2_sampling import sampling_from_dict
from panelforge.domain.production import ComputeResource, ProductionWorkload
from panelforge.infrastructure.creation_batch_progress import CreationBatchProgress
from panelforge.infrastructure.llm.coordinated import CoordinatedMultimodalGateway
from panelforge.infrastructure.storage.creation_batch import LocalCreationBatchStore
from tests.test_creation_batch import AssistedDouble, request_values


class FactoryDouble:
    def __init__(self):
        self.items = {}

    def receive(self, entries, *, compact=False):
        key = entries[0]["source"]["id"]
        self.items.setdefault(key, "factory-" + str(len(self.items) + 1))
        return {"ids": [self.items[key]]}


class CreationBatchVariantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalCreationBatchStore(self.temp.name)
        self.assisted = AssistedDouble()
        self.factory = FactoryDouble()
        self.service = CreationBatchService(self.store, self.assisted, factory=self.factory)

    def finished(self):
        batch = self.service.create(**request_values())
        self.service.process_next()
        item = self.service.get(batch.batch_id).items[0]
        self.assisted.finish(item.project_id)
        self.service.process_renders()
        return self.service.get(batch.batch_id)

    def test_all_prompts_are_prepared_before_first_image_finishes(self):
        batch = self.service.create(**request_values(intentions=[dict(name=str(n), intention="idea") for n in range(3)]))
        for _ in range(3):
            self.service.process_next()
        items = self.service.get(batch.batch_id).items
        self.assertEqual(len(self.assisted.chat_calls), 3)
        self.assertEqual(len(self.assisted.queue_calls), 3)
        self.assertTrue(all(i.prompt_status == "succeeded" and i.image_status == "queued" for i in items))
        self.assertFalse(self.service.get(batch.batch_id).terminal)
        restarted = CreationBatchService(self.store, self.assisted)
        restarted.process_next()
        self.assertEqual(len(self.assisted.chat_calls), 3)

    def test_image_completion_is_followed_while_next_llm_is_blocked(self):
        batch = self.service.create(**request_values(intentions=[dict(name=str(n), intention="idea") for n in range(2)]))
        self.service.process_next()
        first = self.service.get(batch.batch_id).items[0]
        entered, release = Event(), Event()
        original = self.assisted.stream_chat
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            yield from original(*args, **kwargs)
        self.assisted.stream_chat = blocked
        thread = Thread(target=self.service.process_next)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assisted.finish(first.project_id)
            self.service.process_renders()
            self.assertEqual(self.service.get(batch.batch_id).items[0].image_status, "succeeded")
            self.assertTrue(thread.is_alive())
        finally:
            release.set()
            thread.join(3)

    def test_8_plus_4_is_new_seed_on_same_row_with_frozen_source_prompt(self):
        self.assisted.render_settings = replace(self.assisted.render_settings,
            sampling=sampling_from_dict(None, default_preset_id="moody_beta"))
        batch = self.finished()
        source = batch.items[0]
        original = self.assisted.projects.get(source.project_id).attempt(source.attempt_id)
        self.assertEqual(original.settings.sampling.preset_id, "moody_beta")
        values = dict(request_id=str(uuid4()), kind="render")
        updated = self.service.add_variant(batch.batch_id, "1", **values)
        self.assertEqual(updated.items[0].output_asset_id, source.output_asset_id)
        self.assertEqual(len(updated.items), 1)
        self.assertFalse(updated.terminal)
        self.assertEqual(updated.items[0].renders[0].config.settings.sampling.preset_id, "finish_4")
        self.assertEqual(updated.items[0].renders[0].config.settings.sampling.first_pass.sampler, "er_sde")
        self.assertEqual(updated.items[0].renders[0].config.settings.sampling.first_pass.scheduler, "simple")
        changed = self.assisted.projects.get(source.project_id).replace_attempt(replace(original, prompt="Changed prompt", canonical_prompt="Changed prompt"))
        self.assisted.projects.save(changed)
        self.service.process_renders()
        render = self.service.get(batch.batch_id).items[0].renders[0]
        attempt = self.assisted.projects.get(render.project_id).attempt(render.attempt_id)
        self.assertEqual(attempt.prompt, original.prompt)
        self.assertNotEqual(attempt.seed, original.seed)
        self.assertEqual(attempt.settings.workflow, original.settings.workflow)
        self.assertEqual(len(self.assisted.chat_calls), 1)
        self.service.add_variant(batch.batch_id, "1", **values)
        self.assertEqual(len(self.service.get(batch.batch_id).items[0].renders), 1)

    def test_concurrent_variant_receipts_create_one_render_and_reject_conflicts(self):
        batch = self.finished()
        values = dict(request_id=str(uuid4()), kind="render")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.service.add_variant(batch.batch_id, "1", **values), range(4)))
        self.assertEqual(len(self.store.get(batch.batch_id).items[0].renders), 1)
        with self.assertRaises(CreationBatchConflict):
            self.service.add_variant(batch.batch_id, "1", **{**values, "art_style_id": "different"})

    def test_art_and_preset_create_numbered_children_without_replacing_parent(self):
        old = Krea2ArtDirection("fixture", "old", "Old", "art", "Old visual medium", "1")
        new = Krea2ArtDirection("fixture", "new", "New", "art", "New visual medium", "1")
        self.assisted.style_catalog = SimpleNamespace(get=lambda identity: old if identity == "old" else new)
        batch = self.service.create(**request_values(art_style_id="old"))
        self.service.process_next()
        item = self.service.get(batch.batch_id).items[0]
        self.assisted.finish(item.project_id); self.service.process_renders()
        before = self.service.get(batch.batch_id).items[0]
        self.service.add_variant(batch.batch_id, "1", request_id=str(uuid4()), kind="art", art_style_id="new")
        self.service.process_renders()
        child = self.service.get(batch.batch_id).items[1]
        self.assertEqual(child.item_id, "1.1")
        attempt = self.assisted.projects.get(child.project_id).attempt(child.attempt_id)
        self.assertIn("New visual medium", attempt.prompt)
        self.assertNotIn("Old visual medium", attempt.prompt)
        self.assertEqual(len(self.assisted.chat_calls), 1)
        self.service.add_variant(batch.batch_id, "1", request_id=str(uuid4()), kind="preset",
                                 preset_id=self.assisted.preset.preset_id, preset_revision=1)
        self.service.process_next()
        updated = self.service.get(batch.batch_id)
        self.assertEqual([i.item_id for i in updated.items], ["1", "1.1", "1.2"])
        self.assertEqual(updated.items[0], before)
        self.assertEqual(len(self.assisted.chat_calls), 2)
        self.assertEqual(self.store.get(batch.batch_id), updated)

    def test_variant_attempt_is_adopted_after_failed_link_save(self):
        batch = self.finished()
        self.service.add_variant(batch.batch_id, "1", request_id=str(uuid4()), kind="render")
        save = self.store.save
        def fail_link(value):
            if value.items[0].renders[0].attempt_id:
                raise OSError("disk full")
            return save(value)
        self.store.save = fail_link
        with self.assertRaises(OSError):
            self.service.process_renders()
        self.assertEqual(len(self.assisted.queue_calls), 1)
        prepared = self.assisted.prepare_calls
        self.store.save = save
        restarted = CreationBatchService(self.store, self.assisted)
        restarted.process_renders()
        self.assertEqual(self.assisted.prepare_calls, prepared)
        self.assertEqual(len(self.assisted.queue_calls), 2)

    def test_factory_receipt_survives_reload_and_lost_receipt_retry(self):
        batch = self.finished()
        save = self.store.save
        self.store.save = lambda _: (_ for _ in ()).throw(OSError("lost receipt"))
        with self.assertRaises(OSError):
            self.service.send_to_factory(batch.batch_id, "1", "initial")
        self.store.save = save
        restarted = CreationBatchService(self.store, self.assisted, factory=self.factory)
        receipt = restarted.send_to_factory(batch.batch_id, "1", "initial")
        restarted.send_to_factory(batch.batch_id, "1", "initial")
        self.assertEqual(len(self.factory.items), 1)
        self.assertEqual(receipt.items[0].factory_item_id, "factory-1")
        self.assertEqual(self.store.get(batch.batch_id).items[0].factory_item_id, "factory-1")

    def test_legacy_schema_without_variants_still_loads(self):
        batch = self.finished()
        path = self.store._path(batch.batch_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema_version"] = 1
        for key in ("renders", "config", "parent_id", "source_prompt", "request_id", "request_digest", "factory_item_id"):
            data["items"][0].pop(key)
        path.write_text(json.dumps(data), encoding="utf-8")
        restored = self.store.get(batch.batch_id)
        self.assertEqual(restored.items[0].renders, ())
        self.assertEqual(restored.items[0].output_asset_id, batch.items[0].output_asset_id)

    def test_queue_position_is_from_shared_resource_and_polling_does_not_write(self):
        batch = self.service.create(**request_values())
        self.service._update(batch.batch_id, 0, prompt_status="running")
        coordinator = MachineWorkCoordinator()
        self.assisted.work_coordinator = coordinator
        coordinator.enqueue("dlss", ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "DLSS fixture")
        owner = f"batch-llm:{batch.batch_id}:1-fixture"
        coordinator.enqueue(owner, ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM fixture")
        before = self.store.get(batch.batch_id).revision
        progress = self.service.monitoring(self.service.get(batch.batch_id))["1"]["prompt"]
        self.assertEqual(progress["status"], "queued")
        self.assertEqual(progress["position"], 2)
        self.assertEqual(progress["progress"], 0)
        self.assertEqual(self.store.get(batch.batch_id).revision, before)
        coordinator.cancel_queued("dlss"); coordinator.cancel_queued(owner)


class BatchSamplerProgressTests(unittest.TestCase):
    def test_only_matching_execution_sampler_and_step_count_update_progress(self):
        reports = []
        owner = "krea2:project:attempt"
        coordinator = SimpleNamespace(activity_statuses=lambda: {owner: dict(status="running", execution_id="wanted")},
                                      report_progress=lambda *args: reports.append(args))
        watcher = CreationBatchProgress(SimpleNamespace(work_coordinator=coordinator))
        watcher._plans[owner] = (("sampler-a", 8, "Pass 1"), ("sampler-b", 4, "Pass 2"))
        def event(prompt, node, value, maximum):
            watcher.consume(dict(type="progress", data=dict(prompt_id=prompt, node=node, value=value, max=maximum)))
        event("other", "sampler-a", 4, 8)
        event("wanted", "loader", 4, 8)
        event("wanted", "sampler-a", 4, 100)
        self.assertEqual(reports, [])
        event("wanted", "sampler-a", 4, 8)
        event("wanted", "sampler-b", 2, 4)
        self.assertEqual(len(reports), 2)
        self.assertGreater(reports[1][1], reports[0][1])
        self.assertLess(reports[1][1], 1)
        self.assertIn("2/4", reports[1][2])
        event("wanted", "sampler-a", 1, 8)
        self.assertEqual(len(reports), 2)  # Late events cannot move the stage backwards.

    def test_llm_scope_identifies_the_row_and_releases_the_resource(self):
        coordinator = MachineWorkCoordinator()
        seen = []
        def stream(_):
            seen.extend(coordinator.activity_statuses())
            yield CompletionStreamEvent(StreamEventKind.STATUS, StreamPhase.GENERATING, "Writing")
        gateway = CoordinatedMultimodalGateway(SimpleNamespace(stream=stream), coordinator)
        token = llm_owner_prefix.set("batch-llm:batch-one:1")
        try:
            list(gateway.stream(CompletionRequest(model_id="fixture", system_prompt="System", user_prompt="User")))
        finally:
            llm_owner_prefix.reset(token)
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith("batch-llm:batch-one:1-"))
        self.assertEqual(coordinator.activity_statuses(), {})
        self.assertEqual(llm_owner_prefix.get(), "llm")
