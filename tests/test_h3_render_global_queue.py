from dataclasses import replace
from threading import Lock, Thread
import tempfile
import unittest

from panelforge.application.h3_render import H3RenderService
from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.domain.h3_render import (
    H3RenderAttempt,
    H3RenderAttemptStatus,
    H3RenderInputMode,
    H3RenderProject,
)
from panelforge.domain.production import ThermalPolicy, WorkSchedulerSettings
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.infrastructure.presets import H3RenderPresetRecipe, load_h3_render_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from tests.test_h3_render import ImmediateH3Comfy, WORKFLOW_DIRECTORY


PROMPT = (
    "integrated_multimodal_description:\n"
    "[Shot 1] The camera holds a static shot. A cat walks.\n"
    "overall_soundscape:\nFootsteps.\n"
    "non_diegetic_music:\nN/A"
)


class OrderedH3Comfy(ImmediateH3Comfy):
    def __init__(self) -> None:
        super().__init__()
        self._submission_lock = Lock()

    def submit_workflow(self, workflow):
        with self._submission_lock:
            self.submitted.append(workflow)
            return f"execution-{len(self.submitted)}"


class H3RenderGlobalQueueTest(unittest.TestCase):
    def _service(self, root: str):
        projects = LocalH3RenderProjectStore(root)
        settings = VideoLabSettings(
            VideoAspectRatio.PORTRAIT_WIDESCREEN,
            0.2,
            9,
            25,
            42,
            seed_locked=True,
        )
        for index, name in enumerate(("first", "second"), start=1):
            prompt = PROMPT.replace("A cat walks.", f"The {name} cat walks.")
            attempt = H3RenderAttempt(
                f"attempt-{index}",
                1,
                prompt,
                prompt,
                replace(settings, seed=40 + index),
                False,
                (),
            )
            projects.create(H3RenderProject(
                project_id=f"project-{index}",
                source_session_id=f"session-{index}",
                source_prompt_revision_id=f"prompt-{index}",
                model_id="model-1",
                input_mode=H3RenderInputMode.T2VA,
                current_prompt=prompt,
                attempts=(attempt,),
            ))
        coordinator = MachineWorkCoordinator(
            settings=WorkSchedulerSettings(
                thermal=ThermalPolicy(pause_when_unavailable=False),
                remote_video_cooldown_seconds=0,
            ),
            monitor_interval=.01,
        )
        comfy = OrderedH3Comfy()
        service = H3RenderService(
            gateway=object(),
            workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
            comfy=comfy,
            assets=LocalAssetStore(root),
            projects=projects,
            sessions=object(),
            compositions=object(),
            sleep=lambda _: None,
            work_coordinator=coordinator,
        )
        return service, comfy, coordinator

    def test_two_direct_renders_enter_the_global_fifo_before_workers_start(self):
        with tempfile.TemporaryDirectory() as root:
            service, comfy, coordinator = self._service(root)
            service.queue_attempt("project-1", "attempt-1")
            service.queue_attempt("project-2", "attempt-2")

            queued = coordinator.public_status()["machines"]["remote_gpu"]
            self.assertEqual(queued["queue_count"], 2)
            self.assertEqual(
                [item["id"] for item in queued["queue"]],
                ["h3:project-1:attempt-1", "h3:project-2:attempt-2"],
            )

            second = Thread(target=service.execute_attempt, args=("project-2", "attempt-2"))
            first = Thread(target=service.execute_attempt, args=("project-1", "attempt-1"))
            second.start()
            first.start()
            first.join(2)
            second.join(2)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(
                [workflow["14"]["inputs"]["value"].strip() for workflow in comfy.submitted],
                [
                    service.projects.get("project-1").current_prompt,
                    service.projects.get("project-2").current_prompt,
                ],
            )
            self.assertEqual(
                service.projects.get("project-1").attempt("attempt-1").status,
                H3RenderAttemptStatus.SUCCEEDED,
            )
            self.assertEqual(
                service.projects.get("project-2").attempt("attempt-2").status,
                H3RenderAttemptStatus.SUCCEEDED,
            )
            self.assertEqual(
                coordinator.public_status()["machines"]["remote_gpu"]["queue_count"],
                0,
            )

    def test_cancelling_a_waiting_render_removes_its_fifo_ticket(self):
        with tempfile.TemporaryDirectory() as root:
            service, _, coordinator = self._service(root)
            service.queue_attempt("project-1", "attempt-1")
            cancelled = service.cancel_attempt("project-1", "attempt-1")

            self.assertEqual(
                cancelled.attempt("attempt-1").status,
                H3RenderAttemptStatus.CANCELLED,
            )
            self.assertEqual(
                coordinator.public_status()["machines"]["remote_gpu"]["queue_count"],
                0,
            )

    def test_repeated_start_does_not_duplicate_a_fifo_ticket(self):
        with tempfile.TemporaryDirectory() as root:
            service, _, coordinator = self._service(root)
            service.queue_attempt("project-1", "attempt-1")
            repeated = service.queue_attempt("project-1", "attempt-1")

            self.assertEqual(
                repeated.attempt("attempt-1").status,
                H3RenderAttemptStatus.QUEUED,
            )
            self.assertEqual(
                coordinator.public_status()["machines"]["remote_gpu"]["queue_count"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
