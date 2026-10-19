from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest

from panelforge.application import Krea2LabRunRequest, Krea2LabRunner
from panelforge.domain import Krea2AspectRatio, Krea2LabRunStatus
from panelforge.infrastructure.comfy import (
    ComfyCancelAction,
    ComfyCancellationResult,
)
from panelforge.infrastructure.presets import (
    Krea2T2IRecipe,
    load_krea2_t2i_workflow,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2RunStore


PRESET_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "image.generate.t2i"
    / "krea2"
    / "0.1.0"
)
DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)
PNG = b"\x89PNG\r\n\x1a\n" + b"rendered image"


class FakeComfy:
    def __init__(self) -> None:
        self.submitted: list[dict] = []
        self.cancelled: list[str] = []
        self.output = PNG
        self.output_filename = "PanelForge_KREA2_00001_.png"
        self.cancel_error: Exception | None = None
        self.cancel_result: ComfyCancellationResult | None = None
        self.complete_on_cancel = False
        self.hide_history_once_after_cancel = False
        self.history_exception_once_after_cancel: Exception | None = None
        self._hide_history_once = False
        self._history_exception_once: Exception | None = None
        self.history_complete = True
        self.history_error = False
        self.history_interrupted = False
        self.submit_entered: Event | None = None
        self.submit_release: Event | None = None
        self.history_release: Event | None = None

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        if self.submit_entered is not None:
            self.submit_entered.set()
        if self.submit_release is not None:
            self.submit_release.wait(2)
        return "prompt-1"

    def get_history(self, prompt_id):
        if self.history_release is not None:
            self.history_release.wait(2)
        if self._history_exception_once is not None:
            error = self._history_exception_once
            self._history_exception_once = None
            raise error
        if self._hide_history_once:
            self._hide_history_once = False
            return {}
        if self.history_interrupted:
            return {
                prompt_id: {
                    "status": {
                        "completed": False,
                        "status_str": "interrupted",
                        "messages": [["execution_interrupted", {}]],
                    },
                    "outputs": {},
                }
            }
        if self.history_error:
            return {
                prompt_id: {
                    "status": {
                        "completed": True,
                        "status_str": "error",
                        "messages": ["GPU failure"],
                    },
                    "outputs": {},
                }
            }
        if not self.history_complete:
            return {
                prompt_id: {
                    "status": {"completed": False, "status_str": "running"},
                    "outputs": {},
                }
            }
        return {
            prompt_id: {
                "status": {"completed": True, "status_str": "success"},
                "outputs": {
                    "29": {
                        "images": [
                            {
                                "filename": self.output_filename,
                                "subfolder": "image/krea2",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return self.output

    def cancel_execution(self, prompt_id):
        if self.cancel_error is not None:
            raise self.cancel_error
        if self.complete_on_cancel:
            self.history_complete = True
        if self.hide_history_once_after_cancel:
            self._hide_history_once = True
        if self.history_exception_once_after_cancel is not None:
            self._history_exception_once = self.history_exception_once_after_cancel
        self.cancelled.append(prompt_id)
        return self.cancel_result


class BlockingRecipe:
    def __init__(self, delegate: Krea2T2IRecipe) -> None:
        self.delegate = delegate
        self.build_entered = Event()
        self.build_release = Event()

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def build_workflow(self, **kwargs):
        self.build_entered.set()
        self.build_release.wait(2)
        return self.delegate.build_workflow(**kwargs)


class Krea2LabRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(
            self.directory.name,
            id_factory=iter(
                ("asset-output-1", "asset-output-2", "asset-output-3")
            ).__next__,
        )
        self.runs = LocalKrea2RunStore(self.directory.name)
        self.comfy = FakeComfy()
        self.recipe = Krea2T2IRecipe(load_krea2_t2i_workflow(PRESET_DIRECTORY))
        self.runner = Krea2LabRunner(
            recipe=self.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runs,
            run_id_factory=lambda: "krea2-1",
            seed_factory=lambda: 99,
            sleep=lambda _: None,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _prepare(self, prompt: str = "A six-panel storyboard."):
        return self.runner.prepare(Krea2LabRunRequest(prompt=prompt))

    def _persist_running(self, execution_id: str = "prompt-1"):
        queued = self.runner.queue(self._prepare().run_id)
        workflow_hash = self.runs.save_compiled_workflow(
            queued.run_id,
            {"29": {"class_type": "SaveImage", "inputs": {}}},
        )
        running = queued.start(execution_id, workflow_hash)
        self.runs.save(running)
        return running

    def test_prepare_and_execute_imports_one_final_png(self) -> None:
        created = self._prepare("STRICT FORMAT: six separate frames.")

        self.assertEqual(created.status, Krea2LabRunStatus.CREATED)
        self.assertEqual(created.settings.seed, 99)
        self.assertEqual(created.settings.model_name, DEFAULT_MODEL)
        result = self.runner.execute(self.runner.queue(created.run_id).run_id)

        self.assertEqual(result.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(result.output_asset_id, "asset-output-1")
        self.assertEqual(self.assets.read_bytes(result.output_asset_id), PNG)
        self.assertEqual(
            self.runner.output_asset(result.run_id).source_run_id,
            result.run_id,
        )
        workflow = self.comfy.submitted[0]
        self.assertEqual(
            workflow["30:19"]["inputs"]["value"],
            "STRICT FORMAT: six separate frames.",
        )
        self.assertEqual(workflow["30:10"]["inputs"]["unet_name"], DEFAULT_MODEL)
        self.assertEqual(workflow["30:3"]["inputs"]["seed"], 99)
        self.assertIn(created.run_id, workflow["29"]["inputs"]["filename_prefix"])

    def test_prepare_preserves_exact_server_model_and_explicit_controls(self) -> None:
        server_model = (
            "kREA2\\KREA2gptgrandpussytruth_gptint4int8convrot.safetensors"
        )
        run = self.runner.prepare(
            Krea2LabRunRequest(
                prompt="A square page.",
                model_name=server_model,
                aspect_ratio=Krea2AspectRatio.SQUARE,
                megapixels=1.2,
                seed=42,
                seed_locked=True,
            )
        )

        self.assertEqual(run.settings.model_name, server_model)
        self.assertEqual(run.settings.aspect_ratio, Krea2AspectRatio.SQUARE)
        self.assertEqual(run.settings.megapixels, 1.2)
        self.assertEqual(run.settings.seed, 42)
        self.assertTrue(run.settings.seed_locked)

    def test_prepare_rejects_an_unqualified_model(self) -> None:
        with self.assertRaisesRegex(ValueError, "unqualified"):
            self.runner.prepare(
                Krea2LabRunRequest(
                    prompt="A page.",
                    model_name="unrelated/model.safetensors",
                )
            )

    def test_only_one_render_can_be_queued(self) -> None:
        first = self._prepare("First page.")
        self.runner.queue(first.run_id)
        self.runner._run_id_factory = lambda: "krea2-2"
        second = self._prepare("Second page.")

        with self.assertRaisesRegex(ValueError, "already active"):
            self.runner.queue(second.run_id)

    def test_two_execute_calls_cannot_submit_the_same_run_twice(self) -> None:
        run = self.runner.queue(self._prepare().run_id)
        history_release = Event()
        self.comfy.history_release = history_release
        first = Thread(target=lambda: self.runner.execute(run.run_id))
        first.start()
        while not self.comfy.submitted:
            Event().wait(0.001)

        with self.assertRaisesRegex(ValueError, "already being executed"):
            self.runner.execute(run.run_id)

        history_release.set()
        first.join(1)
        self.assertFalse(first.is_alive())
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_cancel_created_run_never_contacts_comfy(self) -> None:
        run = self._prepare()

        cancelled = self.runner.cancel(run.run_id)

        self.assertEqual(cancelled.status, Krea2LabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.cancelled, [])

    def test_cancel_during_compilation_prevents_remote_submission(self) -> None:
        blocking_recipe = BlockingRecipe(self.recipe)
        self.runner.recipe = blocking_recipe
        run = self.runner.queue(self._prepare().run_id)
        execute_thread = Thread(target=lambda: self.runner.execute(run.run_id))
        execute_thread.start()
        self.assertTrue(blocking_recipe.build_entered.wait(1))

        cancelled = self.runner.cancel(run.run_id)
        blocking_recipe.build_release.set()
        execute_thread.join(1)

        self.assertFalse(execute_thread.is_alive())
        self.assertEqual(cancelled.status, Krea2LabRunStatus.CANCELLED)
        self.assertEqual(self.runner.get(run.run_id).status, Krea2LabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.submitted, [])

    def test_cancel_waits_for_submit_then_targets_the_known_execution(self) -> None:
        run = self.runner.queue(self._prepare().run_id)
        submit_entered = Event()
        submit_release = Event()
        history_release = Event()
        cancel_done = Event()
        self.comfy.submit_entered = submit_entered
        self.comfy.submit_release = submit_release
        self.comfy.history_release = history_release
        execute_thread = Thread(target=lambda: self.runner.execute(run.run_id))
        cancel_thread = Thread(
            target=lambda: (self.runner.cancel(run.run_id), cancel_done.set())
        )

        execute_thread.start()
        self.assertTrue(submit_entered.wait(1))
        cancel_thread.start()
        self.assertFalse(cancel_done.wait(0.05))
        submit_release.set()
        self.assertTrue(cancel_done.wait(1))
        history_release.set()
        execute_thread.join(1)
        cancel_thread.join(1)

        self.assertFalse(execute_thread.is_alive())
        self.assertFalse(cancel_thread.is_alive())
        self.assertEqual(self.runner.get(run.run_id).status, Krea2LabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])

    def test_cancel_imports_output_when_comfy_reports_already_finished(self) -> None:
        running = self._persist_running("prompt-finished-during-cancel")
        self.comfy.history_complete = False
        self.comfy.complete_on_cancel = True
        self.comfy.cancel_result = ComfyCancellationResult(
            prompt_id=running.execution_id,
            action=ComfyCancelAction.ALREADY_FINISHED,
        )

        recovered = self.runner.cancel(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), PNG)
        self.assertEqual(self.comfy.cancelled, [running.execution_id])

    def test_already_finished_with_missing_history_stays_pending_until_recovery(
        self,
    ) -> None:
        running = self._persist_running("prompt-finished-during-cancel")
        self.comfy.history_complete = False
        self.comfy.complete_on_cancel = True
        self.comfy.hide_history_once_after_cancel = True
        self.comfy.cancel_result = ComfyCancellationResult(
            prompt_id=running.execution_id,
            action=ComfyCancelAction.ALREADY_FINISHED,
        )

        pending = self.runner.cancel(running.run_id)
        recovered = self.runner.get(running.run_id)

        self.assertEqual(pending.status, Krea2LabRunStatus.CANCEL_PENDING)
        self.assertIn("terminal history", pending.error)
        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), PNG)

    def test_already_finished_with_history_error_stays_pending_until_recovery(
        self,
    ) -> None:
        running = self._persist_running("prompt-finished-during-cancel")
        self.comfy.history_complete = False
        self.comfy.complete_on_cancel = True
        self.comfy.history_exception_once_after_cancel = OSError(
            "temporary history outage"
        )
        self.comfy.cancel_result = ComfyCancellationResult(
            prompt_id=running.execution_id,
            action=ComfyCancelAction.ALREADY_FINISHED,
        )

        pending = self.runner.cancel(running.run_id)
        recovered = self.runner.get(running.run_id)

        self.assertEqual(pending.status, Krea2LabRunStatus.CANCEL_PENDING)
        self.assertIn("terminal history", pending.error)
        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), PNG)

    def test_failed_remote_cancellation_keeps_the_slot_active_for_retry(self) -> None:
        running = self._persist_running("prompt-running")
        self.comfy.history_complete = False
        self.comfy.cancel_error = RuntimeError("GPU host unavailable")

        pending = self.runner.cancel(running.run_id)

        self.assertEqual(pending.status, Krea2LabRunStatus.CANCEL_PENDING)
        self.assertIn("GPU host unavailable", pending.error)
        self.runner._run_id_factory = lambda: "krea2-2"
        second = self._prepare("Second page.")
        with self.assertRaisesRegex(ValueError, "already active"):
            self.runner.queue(second.run_id)

        self.comfy.cancel_error = None
        cancelled = self.runner.cancel(running.run_id)
        self.assertEqual(cancelled.status, Krea2LabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.cancelled, ["prompt-running"])

    def test_invalid_png_fails_and_cancels_the_remote_job(self) -> None:
        run = self.runner.queue(self._prepare().run_id)
        self.comfy.output = b"not a PNG"

        failed = self.runner.execute(run.run_id)

        self.assertEqual(failed.status, Krea2LabRunStatus.FAILED)
        self.assertIn("PNG file signature", failed.error)
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])
        self.assertIsNone(failed.output_asset_id)

    def test_non_png_filename_is_rejected_even_with_png_bytes(self) -> None:
        run = self.runner.queue(self._prepare().run_id)
        self.comfy.output_filename = "unexpected.webp"

        failed = self.runner.execute(run.run_id)

        self.assertEqual(failed.status, Krea2LabRunStatus.FAILED)
        self.assertIn("not a PNG", failed.error)

    def test_known_submission_is_cancelled_if_running_state_cannot_be_saved(self) -> None:
        run = self.runner.queue(self._prepare().run_id)
        original_save = self.runs.save
        fail_running_once = True

        def save_with_one_failure(candidate):
            nonlocal fail_running_once
            if candidate.status is Krea2LabRunStatus.RUNNING and fail_running_once:
                fail_running_once = False
                raise OSError("temporary metadata failure")
            return original_save(candidate)

        self.runs.save = save_with_one_failure

        failed = self.runner.execute(run.run_id)

        self.assertEqual(failed.status, Krea2LabRunStatus.FAILED)
        self.assertEqual(failed.execution_id, "prompt-1")
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])

    def test_refuses_a_run_from_an_unloaded_recipe_snapshot(self) -> None:
        run = self._prepare()
        self.runner.recipe = Krea2T2IRecipe(
            replace(
                self.recipe.preset,
                version="0.2.0",
                workflow_sha256="f" * 64,
            )
        )

        with self.assertRaisesRegex(ValueError, "recipe version is not loaded"):
            self.runner.queue(run.run_id)

    def test_restart_recovery_imports_an_already_completed_png(self) -> None:
        running = self._persist_running()
        restarted = Krea2LabRunner(
            recipe=self.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runs,
            run_id_factory=lambda: "krea2-after-restart",
            sleep=lambda _: None,
        )

        recovered = restarted.get(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), PNG)
        self.assertEqual(self.comfy.cancelled, [])

    def test_restart_recovery_keeps_a_remote_running_job_active(self) -> None:
        running = self._persist_running()
        self.comfy.history_complete = False
        restarted = Krea2LabRunner(
            recipe=self.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runs,
            run_id_factory=lambda: "krea2-2",
            sleep=lambda _: None,
        )

        self.assertEqual(restarted.get(running.run_id).status, Krea2LabRunStatus.RUNNING)
        second = restarted.prepare(Krea2LabRunRequest(prompt="Second page."))
        with self.assertRaisesRegex(ValueError, "already active"):
            restarted.queue(second.run_id)

    def test_restart_recovery_records_a_remote_failure(self) -> None:
        running = self._persist_running()
        self.comfy.history_error = True
        restarted = Krea2LabRunner(
            recipe=self.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runs,
            run_id_factory=lambda: "krea2-2",
            sleep=lambda _: None,
        )

        recovered = restarted.get(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.FAILED)
        self.assertIn("GPU failure", recovered.error)

    def test_cancel_pending_get_imports_a_late_success(self) -> None:
        running = self._persist_running("prompt-late-success")
        self.runs.save(running.mark_cancel_pending("Cancellation unavailable"))

        recovered = self.runner.get(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), PNG)
        self.assertEqual(self.comfy.cancelled, [])

    def test_cancel_pending_is_reconciled_before_claiming_the_next_slot(self) -> None:
        running = self._persist_running("prompt-late-success")
        self.runs.save(running.mark_cancel_pending("Cancellation unavailable"))
        self.runner._run_id_factory = lambda: "krea2-2"
        second = self._prepare("Second page.")

        queued = self.runner.queue(second.run_id)

        self.assertEqual(queued.status, Krea2LabRunStatus.QUEUED)
        self.assertEqual(
            self.runs.get(running.run_id).status,
            Krea2LabRunStatus.SUCCEEDED,
        )

    def test_cancel_pending_is_reconciled_before_retrying_cancel(self) -> None:
        running = self._persist_running("prompt-late-success")
        self.runs.save(running.mark_cancel_pending("Cancellation unavailable"))

        recovered = self.runner.cancel(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(self.comfy.cancelled, [])

    def test_cancel_pending_interruption_becomes_cancelled(self) -> None:
        running = self._persist_running("prompt-interrupted")
        self.runs.save(running.mark_cancel_pending("Cancellation unavailable"))
        self.comfy.history_interrupted = True

        recovered = self.runner.get(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.CANCELLED)

    def test_cancel_pending_remote_error_becomes_failed(self) -> None:
        running = self._persist_running("prompt-failed")
        self.runs.save(running.mark_cancel_pending("Cancellation unavailable"))
        self.comfy.history_error = True

        recovered = self.runner.get(running.run_id)

        self.assertEqual(recovered.status, Krea2LabRunStatus.FAILED)
        self.assertIn("GPU failure", recovered.error)


if __name__ == "__main__":
    unittest.main()
