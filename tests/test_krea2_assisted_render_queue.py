"""Queue regressions using only fake renderers and temporary project stores."""

from dataclasses import asdict, replace
from itertools import count
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
import tempfile
import unittest

from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus as Status
from panelforge.domain.krea2_batch import Krea2BatchSettings, Krea2LoraSelection
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore


class NoLlm:
    def stream(self, _request):
        raise AssertionError("Rendering must not call the LLM")


class Workflow:
    reference = SimpleNamespace(operation_id="image.generate.batch", recipe_id="fake", version="1", workflow_sha256="a" * 64)
    output_node_id = "output"
    output_history_field = "images"
    output_media_type = "image/png"

    def build(self, *, settings, **values):
        return {**values, "settings": asdict(settings)}


class Comfy:
    def __init__(self):
        self.workflows = []
        self.cancelled = []
        self.tracked = []
        self.offline = False
        self.fail_first = False
        self.ambiguous = False
        self.entered = Event()
        self.release = Event()
        self.block_first = False

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        if self.ambiguous:
            raise TimeoutError("response lost after submission")
        return f"remote-{len(self.workflows)}"

    def get_history(self, execution_id):
        self.tracked.append(execution_id)
        if self.offline:
            raise ConnectionError("offline")
        if self.block_first and execution_id == "remote-1":
            self.entered.set()
            if not self.release.wait(timeout=3):
                raise TimeoutError("fake renderer was not released")
        return {execution_id: {
            "status": {"completed": True, "status_str": "error" if self.fail_first and execution_id == "remote-1" else "success"},
            "outputs": {"output": {"images": [{"filename": "fake.png", "type": "output"}]}},
        }}

    def download_output(self, **_kwargs):
        return b"\x89PNG\r\n\x1a\nFAKE"

    def cancel_execution(self, execution_id):
        self.cancelled.append(execution_id)
        return SimpleNamespace(action="removed_from_queue")


class Resources:
    models = ("Krea2/a.safetensors", "Krea2/b.safetensors")
    loras = ("krea2/style.safetensors",)

    def list_models(self):
        return tuple(SimpleNamespace(comfy_name=name) for name in self.models)

    def list_loras(self):
        return tuple(SimpleNamespace(comfy_name=name) for name in self.loras)


class AssistedRenderQueueTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.comfy = Comfy()
        self.resources = Resources()
        self.services = []
        self.service = self.make_service()
        self.project = self.service.create_project(name="A", intention="Photo", model_id="local")
        self.settings = Krea2BatchSettings(model_name="Krea2/a.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN, megapixels=0.8)

    def tearDown(self):
        self.comfy.release.set()
        for service in self.services:
            service.stop_render_worker()
        self.temporary.cleanup()

    def make_service(self):
        numbers = count(1)
        service = Krea2AssistedService(
            gateway=NoLlm(), recipes=SimpleNamespace(current=lambda: ()), workflow=Workflow(),
            comfy=self.comfy, assets=LocalAssetStore(self.root),
            projects=LocalKrea2AssistedProjectStore(self.root), resources=self.resources,
            attempt_id_factory=lambda: f"attempt-{next(numbers)}", seed_factory=lambda: 42,
            poll_interval=0.001,
        )
        self.services.append(service)
        return service

    def prepare(self, *, project=None, prompt="A photo", settings=None, seed=0, enqueue=True):
        value = self.service.prepare_attempt(
            (project or self.project).project_id, prompt=prompt, settings=settings or self.settings,
            seed=seed, enqueue=enqueue, expected_branch_id="main",
        )
        return value.attempts[-1]

    def test_fifo_across_projects_keeps_snapshots_and_never_starts_drafts(self):
        other = self.service.create_project(name="B", intention="Object", model_id="local")
        draft = self.prepare(enqueue=False, prompt="Do not render this")
        first = self.prepare(prompt="First photo")
        second = self.prepare(project=other, prompt="Second photo", seed=17, settings=replace(
            self.settings, model_name="Krea2/b.safetensors", megapixels=2.1,
            loras=(Krea2LoraSelection("krea2/style.safetensors", 0.4),),
        ))
        third = self.prepare(prompt="Third photo", seed=None)
        # Changing the current editor doesn't affect the previously queued snapshots.
        current = self.service.projects.get(self.project.project_id)
        self.service.projects.save(replace(current, current_prompt="Unsent later text"))
        queue = self.service.render_queue()["items"]
        self.assertEqual([item["attempt_id"] for item in queue], [first.attempt_id, second.attempt_id, third.attempt_id])
        self.assertEqual([item["position"] for item in queue], [1, 2, 3])
        self.assertEqual(self.comfy.workflows, [])
        result = self.service.execute_attempt(other.project_id, second.attempt_id)
        self.assertEqual(result.attempt(second.attempt_id).status, Status.SUCCEEDED)
        self.assertEqual([w["prompt"] for w in self.comfy.workflows], ["First photo", "Second photo"])
        self.assertEqual([w["seed"] for w in self.comfy.workflows], [0, 17])
        self.assertEqual(self.comfy.workflows[1]["settings"], asdict(second.settings))
        self.assertEqual(self.service.projects.get(self.project.project_id).attempt(draft.attempt_id).status, Status.CREATED)
        self.assertTrue(self.service.process_next_render())
        self.assertEqual(self.comfy.workflows[-1]["seed"], 42)
        self.assertEqual(self.service.render_queue()["items"], [])

    def test_queued_cancel_is_local_and_repeated_start_is_idempotent(self):
        first = self.prepare()
        second = self.prepare()
        self.service.queue_attempt(self.project.project_id, first.attempt_id)
        self.assertEqual(len(self.service.render_queue()["items"]), 2)
        self.service.cancel_attempt(self.project.project_id, first.attempt_id)
        self.assertEqual(self.comfy.cancelled, [])
        self.assertEqual(self.service.render_queue()["items"][0]["position"], 1)
        self.service.execute_attempt(self.project.project_id, second.attempt_id)
        self.assertEqual(len(self.comfy.workflows), 1)

    def test_restart_resumes_existing_remote_id_before_queued_jobs(self):
        first = self.prepare()
        second = self.prepare()
        current = self.service.projects.get(self.project.project_id)
        self.service.projects.save(current.replace_attempt(first.start("existing-remote", "b" * 64)))
        restarted = self.make_service()
        self.assertTrue(restarted.process_next_render())
        self.assertEqual(self.comfy.workflows, [])
        self.assertIn("existing-remote", self.comfy.tracked)
        self.assertTrue(restarted.process_next_render())
        self.assertEqual(len(self.comfy.workflows), 1)
        self.assertEqual(restarted.projects.get(self.project.project_id).attempt(second.attempt_id).status, Status.SUCCEEDED)

    def test_tracking_failure_blocks_next_job_and_does_not_resubmit(self):
        first = self.prepare()
        self.prepare()
        self.comfy.offline = True
        self.assertFalse(self.service.process_next_render())
        current = self.service.projects.get(self.project.project_id).attempt(first.attempt_id)
        self.assertEqual(current.status, Status.RUNNING)
        self.assertEqual(current.execution_id, "remote-1")
        self.assertIn("Suivi ComfyUI", current.error)
        self.assertFalse(self.service.process_next_render())
        self.assertEqual(len(self.comfy.workflows), 1)
        self.comfy.offline = False
        self.assertTrue(self.service.process_next_render())
        self.assertEqual(len(self.comfy.workflows), 1)
        self.assertTrue(self.service.process_next_render())
        self.assertEqual(len(self.comfy.workflows), 2)

    def test_failed_render_does_not_block_the_next_one(self):
        first = self.prepare()
        second = self.prepare()
        self.comfy.fail_first = True
        self.service.execute_attempt(self.project.project_id, second.attempt_id)
        current = self.service.projects.get(self.project.project_id)
        self.assertEqual(current.attempt(first.attempt_id).status, Status.FAILED)
        self.assertEqual(current.attempt(second.attempt_id).status, Status.SUCCEEDED)

    def test_ambiguous_dispatch_waits_for_explicit_removal(self):
        first = self.prepare()
        self.prepare()
        self.comfy.ambiguous = True
        self.assertFalse(self.service.process_next_render())
        restarted = self.make_service()
        self.assertFalse(restarted.process_next_render())
        self.assertEqual(len(self.comfy.workflows), 1)
        self.assertEqual(restarted.projects.get(self.project.project_id).attempt(first.attempt_id).status, Status.SUBMITTING)
        restarted.cancel_attempt(self.project.project_id, first.attempt_id)
        self.assertEqual(self.comfy.cancelled, [])
        self.comfy.ambiguous = False
        self.assertTrue(restarted.process_next_render())

    def test_missing_lora_fails_instead_of_silently_changing_queued_settings(self):
        first = self.prepare(settings=replace(self.settings, loras=(Krea2LoraSelection("krea2/style.safetensors", 0.4),)))
        self.prepare()
        self.resources.loras = ()
        self.assertTrue(self.service.process_next_render())
        self.assertEqual(self.comfy.workflows, [])
        self.assertIn("LoRA indisponible", self.service.projects.get(self.project.project_id).attempt(first.attempt_id).error)
        self.assertTrue(self.service.process_next_render())

    def test_known_selection_queues_without_discovery_but_worker_revalidates(self):
        from unittest.mock import patch

        self.resources.selection_in_last_inventory = lambda model, loras: model == self.settings.model_name and not loras
        with patch.object(self.resources, "list_models", side_effect=AssertionError("enqueue scanned checkpoints")), \
             patch.object(self.resources, "list_loras", side_effect=AssertionError("enqueue scanned LoRAs")):
            first = self.prepare()
            prepared = self.prepare(enqueue=False)
            self.service.queue_attempt(self.project.project_id, prepared.attempt_id)
        self.assertEqual(first.status, Status.QUEUED)
        # A removed file is caught before ComfyUI, even if admission used the old catalogue.
        self.resources.models = ()
        self.assertTrue(self.service.process_next_render())
        failed = self.service.projects.get(self.project.project_id).attempt(first.attempt_id)
        self.assertEqual(failed.status, Status.FAILED)
        self.assertIn("checkpoint", failed.error)
        self.assertEqual(self.comfy.workflows, [])

    def test_unknown_selection_still_uses_fresh_discovery_before_enqueue(self):
        from unittest.mock import patch

        self.resources.selection_in_last_inventory = lambda *_: False
        with patch.object(self.resources, "list_models", wraps=self.resources.list_models) as discover:
            first = self.prepare()
        discover.assert_called_once()
        self.assertEqual(first.status, Status.QUEUED)

    def test_running_cancel_is_targeted_and_concurrent_drainers_stay_serial(self):
        first = self.prepare()
        self.comfy.block_first = True
        errors = []
        def drain(target=None):
            try:
                if target:
                    self.service.execute_attempt(self.project.project_id, target)
                else:
                    self.service.process_next_render()
            except Exception as error:
                errors.append(error)
        first_thread = Thread(target=drain)
        second_thread = None
        first_thread.start()
        try:
            self.assertTrue(self.comfy.entered.wait(timeout=2))
            # Enqueue while the first job is genuinely being tracked.
            second = self.prepare(prompt="Queued during render")
            second_thread = Thread(target=drain, args=(second.attempt_id,))
            second_thread.start()
            self.assertEqual(len(self.comfy.workflows), 1)
            self.service.cancel_attempt(self.project.project_id, first.attempt_id)
            self.assertEqual(self.comfy.cancelled, ["remote-1"])
        finally:
            self.comfy.release.set()
            first_thread.join(timeout=3)
            if second_thread is not None:
                second_thread.join(timeout=3)
        self.assertFalse(first_thread.is_alive())
        self.assertIsNotNone(second_thread)
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(errors, [])
        current = self.service.projects.get(self.project.project_id)
        self.assertEqual(current.attempt(first.attempt_id).status, Status.CANCELLED)
        self.assertEqual(current.attempt(second.attempt_id).status, Status.SUCCEEDED)
        self.assertEqual(len(self.comfy.workflows), 2)

    def test_storage_preserves_queue_order_and_reads_previous_schema(self):
        attempt = self.prepare()
        path = self.root / "krea2_assisted" / self.project.project_id / "project.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 8)
        self.assertEqual(data["attempts"][0]["queue_order"], str(attempt.queue_order))
        data["schema_version"] = 5
        data["attempts"][0].pop("queue_order")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(self.service.projects.get(self.project.project_id).attempt(attempt.attempt_id).queue_order)

    def test_worker_runs_without_browser_polling_and_stop_keeps_remote_job(self):
        first = self.prepare()
        self.comfy.block_first = True
        self.service.start_render_worker()
        try:
            self.assertTrue(self.comfy.entered.wait(timeout=2))
            second = self.prepare(prompt="After restart")
            # Simulate an orderly server stop between two remote history polls.
            self.service._render_stop.set()
            self.comfy.offline = True
        finally:
            self.comfy.release.set()
            self.service.stop_render_worker()
        # If the in-flight response completed during shutdown, it may already
        # have saved the first image. The next queued job must never be submitted.
        self.assertEqual(len(self.comfy.workflows), 1)
        self.assertEqual(self.comfy.cancelled, [])
        current = self.service.projects.get(self.project.project_id)
        self.assertIn(current.attempt(first.attempt_id).status, {Status.RUNNING, Status.SUCCEEDED})
        self.assertEqual(current.attempt(second.attempt_id).status, Status.QUEUED)
        self.comfy.block_first = False
        self.comfy.offline = False
        restarted = self.make_service()
        completed = Event()
        execute = restarted._execute_render
        def observe(project_id, attempt_id):
            result = execute(project_id, attempt_id)
            if attempt_id == second.attempt_id and result.attempt(attempt_id).status is Status.SUCCEEDED:
                completed.set()
            return result
        restarted._execute_render = observe
        restarted.start_render_worker()
        self.assertTrue(completed.wait(timeout=3))
        restarted.stop_render_worker()
        self.assertEqual(len(self.comfy.workflows), 2)


if __name__ == "__main__":
    unittest.main()
