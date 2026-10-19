from dataclasses import dataclass, replace
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest

from panelforge.application.video_lab import VideoLabRunRequest, VideoLabRunner
from panelforge.domain import VideoLabRunStatus
from panelforge.infrastructure.presets import (
    VideoLabPresetRecipe,
    load_video_lab_workflow,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalVideoRunStore


PRESET_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.2.0"
)
MP4 = b"\x00\x00\x00\x18ftypisom" + b"video"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str


class FakeComfy:
    def __init__(self) -> None:
        self.submitted: list[dict] = []
        self.cancelled: list[str] = []
        self.output = MP4
        self.cancel_error: Exception | None = None
        self.history_complete = True
        self.submit_entered: Event | None = None
        self.submit_release: Event | None = None
        self.history_release: Event | None = None

    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded(f"{subfolder}/{filename}")

    def submit_workflow(self, workflow):
        self.submitted.append(dict(workflow))
        if self.submit_entered is not None:
            self.submit_entered.set()
        if self.submit_release is not None:
            self.submit_release.wait(2)
        return "prompt-1"

    def get_history(self, prompt_id):
        if self.history_release is not None:
            self.history_release.wait(2)
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
                    "5": {
                        "images": [
                            {
                                "filename": "PanelForge_H3_00001_.mp4",
                                "subfolder": "video",
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
        self.cancelled.append(prompt_id)


class VideoLabRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(
            self.directory.name,
            id_factory=iter(("asset-1", "asset-2", "asset-video")).__next__,
        )
        self.source = self.assets.create(b"image", media_type="image/png")
        self.comfy = FakeComfy()
        self.runner = VideoLabRunner(
            recipe=VideoLabPresetRecipe(load_video_lab_workflow(PRESET_DIRECTORY)),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalVideoRunStore(self.directory.name),
            run_id_factory=lambda: "video-1",
            seed_factory=lambda: 99,
            sleep=lambda _: None,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_prepare_and_execute_successful_video(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                source_labels=("reference.png",),
                prompt="The subject slowly turns toward the window.",
                preset_id="h3-balanced",
            )
        )
        self.assertEqual(created.settings.seed, 99)
        self.assertEqual(created.status, VideoLabRunStatus.CREATED)

        queued = self.runner.queue(created.run_id)
        result = self.runner.execute(queued.run_id)

        self.assertEqual(result.status, VideoLabRunStatus.SUCCEEDED)
        self.assertEqual(result.output_asset_id, "asset-2")
        self.assertEqual(self.assets.read_bytes(result.output_asset_id), MP4)
        workflow = self.comfy.submitted[0]
        self.assertIn("9", workflow)
        self.assertNotIn("47", workflow)
        self.assertNotIn("48", workflow)

    def test_cancel_created_run_without_contacting_comfy(self) -> None:
        run = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        cancelled = self.runner.cancel(run.run_id)
        self.assertEqual(cancelled.status, VideoLabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.cancelled, [])

    def test_only_one_run_can_be_queued(self) -> None:
        first = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="First prompt.",
                preset_id="h3-balanced",
            )
        )
        self.runner.queue(first.run_id)
        self.runner._run_id_factory = lambda: "video-2"
        second = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="Second prompt.",
                preset_id="h3-balanced",
            )
        )
        with self.assertRaisesRegex(ValueError, "already active"):
            self.runner.queue(second.run_id)

    def test_cancel_running_run_targets_its_comfy_execution(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        queued = self.runner.queue(created.run_id)
        workflow_hash = self.runner.runs.save_compiled_workflow(
            queued.run_id,
            {"5": {}},
        )
        running = queued.start("prompt-running", workflow_hash)
        self.runner.runs.save(running)
        self.comfy.history_complete = False

        cancelled = self.runner.cancel(running.run_id)

        self.assertEqual(cancelled.status, VideoLabRunStatus.CANCELLED)
        self.assertEqual(self.comfy.cancelled, ["prompt-running"])

    def test_post_submit_failure_cancels_remote_job_before_freeing_slot(self) -> None:
        run = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        self.runner.queue(run.run_id)
        self.comfy.output = b"not a video"

        failed = self.runner.execute(run.run_id)

        self.assertEqual(failed.status, VideoLabRunStatus.FAILED)
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])

    def test_failed_remote_cancellation_keeps_slot_active_for_retry(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        queued = self.runner.queue(created.run_id)
        workflow_hash = self.runner.runs.save_compiled_workflow(
            queued.run_id,
            {"5": {}},
        )
        self.runner.runs.save(queued.start("prompt-running", workflow_hash))
        self.comfy.history_complete = False
        self.comfy.cancel_error = RuntimeError("GPU host unavailable")

        pending = self.runner.cancel(created.run_id)

        self.assertEqual(pending.status, VideoLabRunStatus.CANCEL_PENDING)
        self.assertIn("GPU host unavailable", pending.error)
        self.runner._run_id_factory = lambda: "video-2"
        second = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="Second prompt.",
                preset_id="h3-balanced",
            )
        )
        with self.assertRaisesRegex(ValueError, "already active"):
            self.runner.queue(second.run_id)

        self.comfy.cancel_error = None
        cancelled = self.runner.cancel(created.run_id)
        self.assertEqual(cancelled.status, VideoLabRunStatus.CANCELLED)

    def test_refuses_to_queue_a_run_from_an_unloaded_recipe_version(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        self.runner.recipe = VideoLabPresetRecipe(
            replace(
                self.runner.recipe.preset,
                version="0.3.0",
                workflow_sha256="f" * 64,
            )
        )

        with self.assertRaisesRegex(ValueError, "recipe version is not loaded"):
            self.runner.queue(created.run_id)

    def test_cancel_waits_for_submit_then_targets_the_known_execution(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        self.runner.queue(created.run_id)
        submit_entered = Event()
        submit_release = Event()
        history_release = Event()
        cancel_done = Event()
        self.comfy.submit_entered = submit_entered
        self.comfy.submit_release = submit_release
        self.comfy.history_release = history_release
        execute_thread = Thread(target=lambda: self.runner.execute(created.run_id))
        cancel_thread = Thread(
            target=lambda: (self.runner.cancel(created.run_id), cancel_done.set())
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
        self.assertEqual(
            self.runner.get(created.run_id).status,
            VideoLabRunStatus.CANCELLED,
        )
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])

    def test_known_submission_is_cancelled_if_running_state_cannot_be_saved(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        self.runner.queue(created.run_id)
        original_save = self.runner.runs.save
        fail_running_once = True

        def save_with_one_failure(run):
            nonlocal fail_running_once
            if run.status is VideoLabRunStatus.RUNNING and fail_running_once:
                fail_running_once = False
                raise OSError("temporary metadata failure")
            return original_save(run)

        self.runner.runs.save = save_with_one_failure

        failed = self.runner.execute(created.run_id)

        self.assertEqual(failed.status, VideoLabRunStatus.FAILED)
        self.assertEqual(failed.execution_id, "prompt-1")
        self.assertEqual(self.comfy.cancelled, ["prompt-1"])

    def test_detached_running_run_ingests_completed_output_after_restart(self) -> None:
        created = self.runner.prepare(
            VideoLabRunRequest(
                source_asset_ids=(self.source.asset_id,),
                prompt="A quiet shot.",
                preset_id="h3-balanced",
            )
        )
        queued = self.runner.queue(created.run_id)
        workflow_hash = self.runner.runs.save_compiled_workflow(
            queued.run_id,
            {"5": {}},
        )
        self.runner.runs.save(queued.start("prompt-1", workflow_hash))
        restarted = VideoLabRunner(
            recipe=self.runner.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runner.runs,
            run_id_factory=lambda: "video-after-restart",
            sleep=lambda _: None,
        )

        recovered = restarted.get(created.run_id)

        self.assertEqual(recovered.status, VideoLabRunStatus.SUCCEEDED)
        self.assertEqual(self.assets.read_bytes(recovered.output_asset_id), MP4)
        self.assertEqual(self.comfy.cancelled, [])


if __name__ == "__main__":
    unittest.main()
