from threading import Event, Lock, Thread
from tempfile import TemporaryDirectory
import unittest

from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.application.prompt_lab import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    StreamEventKind,
    StreamPhase,
)
from panelforge.domain.production import (
    ComputeResource,
    ProductionWorkload,
    ThermalPolicy,
    ThermalSnapshot,
    WorkSchedulerSettings,
)
from panelforge.infrastructure.llm.coordinated import CoordinatedMultimodalGateway
from panelforge.infrastructure.storage.work_scheduler_settings import LocalWorkSchedulerSettings


class Monitor:
    def __init__(self, values): self.values = iter(values)
    def snapshot(self): return next(self.values)


class MachineWorkCoordinatorTest(unittest.TestCase):
    def test_fixed_cooldown_keeps_remote_lane_reserved_and_reports_countdown(self):
        now = [100.0]
        observed = []

        def monotonic():
            return now[0]

        def sleep(seconds):
            observed.append(coordinator.public_status()["machines"]["remote_gpu"])
            now[0] += seconds

        coordinator = MachineWorkCoordinator(
            monitor_interval=1,
            monotonic=monotonic,
            sleep=sleep,
        )
        started, finished = [], []
        with coordinator.lease(
            "video-1",
            ComputeResource.REMOTE_GPU,
            ProductionWorkload.VIDEO_RENDER,
            "H3",
        ):
            coordinator.cooldown_while_owned(
                ComputeResource.REMOTE_GPU,
                3,
                "Refroidissement entre vidéos",
                on_started=started.append,
                on_finished=lambda: finished.append(True),
            )
            inside = coordinator.public_status()["machines"]["remote_gpu"]
            self.assertEqual(inside["state"], "busy")
        after = coordinator.public_status()["machines"]["remote_gpu"]

        self.assertEqual(started, [3.0])
        self.assertEqual(finished, [True])
        self.assertEqual([item["cooldown_remaining_seconds"] for item in observed], [3, 2, 1])
        self.assertTrue(all(item["state"] == "cooling" for item in observed))
        self.assertTrue(all(item["operation"] == "Refroidissement entre vidéos" for item in observed))
        self.assertTrue(all(item["owner_id"] == "video-1" for item in observed))
        self.assertEqual(after["state"], "idle")

    def test_same_machine_is_exclusive_while_other_machine_can_run(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        local_entered, release_local, second_entered, remote_entered = Event(), Event(), Event(), Event()

        def first():
            with coordinator.lease("llm-1", ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM 1"):
                local_entered.set(); release_local.wait(2)

        def second():
            local_entered.wait(2)
            with coordinator.lease("llm-2", ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM 2"):
                second_entered.set()

        def remote():
            local_entered.wait(2)
            with coordinator.lease("krea", ComputeResource.REMOTE_GPU, ProductionWorkload.IMAGE_RENDER, "KREA2"):
                remote_entered.set()

        threads = [Thread(target=target) for target in (first, second, remote)]
        for thread in threads: thread.start()
        self.assertTrue(local_entered.wait(2)); self.assertTrue(remote_entered.wait(2))
        self.assertFalse(second_entered.wait(.05))
        release_local.set()
        self.assertTrue(second_entered.wait(2))
        for thread in threads: thread.join(2)

    def test_thermal_gate_waits_for_resume_threshold(self):
        monitor = Monitor([
            ThermalSnapshot(local_temperature_c=90, remote_temperature_c=40),
            ThermalSnapshot(local_temperature_c=70, remote_temperature_c=40),
            ThermalSnapshot(local_temperature_c=39, remote_temperature_c=40),
            ThermalSnapshot(local_temperature_c=39, remote_temperature_c=40),
        ])
        coordinator = MachineWorkCoordinator(thermal_monitor=monitor,
            policy=ThermalPolicy(stop_temperature_c=85, resume_temperature_c=40, cooldown_seconds=0,
                                 pause_when_unavailable=False), monitor_interval=.01, sleep=lambda _: None)
        with coordinator.lease("llm", ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM"):
            self.assertEqual(coordinator.public_status()["machines"]["local_gpu"]["state"], "busy")

    def test_waiters_keep_fifo_order(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        release, first_entered, second_waiting, third_waiting = Event(), Event(), Event(), Event()
        order, guard = [], Lock()

        def work(name, waiting=None):
            with coordinator.lease(name, ComputeResource.REMOTE_GPU,
                    ProductionWorkload.IMAGE_RENDER, name,
                    on_wait=waiting.set if waiting is not None else None):
                with guard: order.append(name)
                if name == "first":
                    first_entered.set(); release.wait(2)

        first = Thread(target=work, args=("first",))
        second = Thread(target=work, args=("second", second_waiting))
        third = Thread(target=work, args=("third", third_waiting))
        first.start(); self.assertTrue(first_entered.wait(2))
        second.start(); self.assertTrue(second_waiting.wait(2))
        third.start(); self.assertTrue(third_waiting.wait(2))
        release.set()
        for thread in (first, second, third): thread.join(2)
        self.assertEqual(order, ["first", "second", "third"])

    def test_prequeued_jobs_are_visible_and_keep_their_reserved_order(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        for name in ("first", "second"):
            coordinator.enqueue(
                name,
                ComputeResource.REMOTE_GPU,
                ProductionWorkload.IMAGE_RENDER,
                f"KREA2 {name}",
            )
        queued = coordinator.public_status()["machines"]["remote_gpu"]
        self.assertEqual(queued["queue_count"], 2)
        self.assertEqual([value["id"] for value in queued["queue"]], ["first", "second"])

        order = []
        second_entered = Event()

        def work(name):
            with coordinator.lease(
                name,
                ComputeResource.REMOTE_GPU,
                ProductionWorkload.IMAGE_RENDER,
                f"KREA2 {name}",
            ):
                order.append(name)
                if name == "second":
                    second_entered.set()

        second = Thread(target=work, args=("second",))
        first = Thread(target=work, args=("first",))
        second.start()
        self.assertFalse(second_entered.wait(.05))
        first.start()
        self.assertTrue(second_entered.wait(2))
        first.join(2); second.join(2)
        self.assertEqual(order, ["first", "second"])

    def test_prequeued_job_can_be_cancelled_before_its_worker_starts(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        coordinator.enqueue(
            "queued",
            ComputeResource.LOCAL_GPU,
            ProductionWorkload.LLM,
            "Prompt",
        )
        self.assertTrue(coordinator.cancel_queued("queued"))
        machine = coordinator.public_status()["machines"]["local_gpu"]
        self.assertEqual(machine["queue_count"], 0)
        self.assertEqual(coordinator.public_status()["recent"][0]["status"], "cancelled")

    def test_public_status_exposes_active_job_and_described_fifo(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        release, first_entered, second_waiting = Event(), Event(), Event()

        def first():
            with coordinator.lease("dlss-1", ComputeResource.LOCAL_GPU,
                    ProductionWorkload.DLSS, "DLSS vidéo"):
                first_entered.set(); release.wait(2)

        def second():
            with coordinator.lease("llm-1", ComputeResource.LOCAL_GPU,
                    ProductionWorkload.LLM, "Prompt scène 2", on_wait=second_waiting.set):
                pass

        threads = [Thread(target=first), Thread(target=second)]
        threads[0].start(); self.assertTrue(first_entered.wait(2))
        threads[1].start(); self.assertTrue(second_waiting.wait(2))
        machine = coordinator.public_status()["machines"]["local_gpu"]
        self.assertEqual(machine["active"]["workload"], "dlss")
        self.assertEqual(machine["queue_count"], 1)
        self.assertEqual(machine["queue"][0]["operation"], "Prompt scène 2")
        self.assertEqual(machine["queue"][0]["position"], 1)
        release.set()
        for thread in threads: thread.join(2)

    def test_pause_after_current_holds_fifo_until_resume(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        release, first_entered, second_entered = Event(), Event(), Event()

        def first():
            with coordinator.lease("first", ComputeResource.REMOTE_GPU,
                    ProductionWorkload.IMAGE_RENDER, "KREA2"):
                first_entered.set(); release.wait(2)

        def second():
            with coordinator.lease("second", ComputeResource.REMOTE_GPU,
                    ProductionWorkload.VIDEO_RENDER, "H3"):
                second_entered.set()

        first_thread = Thread(target=first); second_thread = Thread(target=second)
        first_thread.start(); self.assertTrue(first_entered.wait(2))
        coordinator.pause(ComputeResource.REMOTE_GPU)
        second_thread.start(); release.set()
        self.assertFalse(second_entered.wait(.05))
        machine = coordinator.public_status()["machines"]["remote_gpu"]
        self.assertTrue(machine["paused"])
        self.assertEqual(machine["queue_count"], 1)
        coordinator.resume(ComputeResource.REMOTE_GPU)
        self.assertTrue(second_entered.wait(2))
        first_thread.join(2); second_thread.join(2)

    def test_global_video_cooldown_runs_before_the_next_remote_video(self):
        now, observed = [100.0], []

        def monotonic(): return now[0]
        def sleep(seconds):
            observed.append(coordinator.public_status()["machines"]["remote_gpu"])
            now[0] += seconds

        coordinator = MachineWorkCoordinator(
            settings=WorkSchedulerSettings(
                thermal=ThermalPolicy(pause_when_unavailable=False),
                remote_video_cooldown_seconds=30,
            ),
            monitor_interval=10,
            monotonic=monotonic,
            sleep=sleep,
        )
        with coordinator.lease("video-1", ComputeResource.REMOTE_GPU,
                ProductionWorkload.VIDEO_RENDER, "H3 scène 1"):
            pass
        with coordinator.lease("video-2", ComputeResource.REMOTE_GPU,
                ProductionWorkload.VIDEO_RENDER, "H3 scène 2"):
            pass
        self.assertEqual([value["cooldown_remaining_seconds"] for value in observed], [30, 20, 10])
        self.assertTrue(all(value["state"] == "cooling" for value in observed))

    def test_queued_video_cannot_enter_before_the_previous_completion_is_recorded(self):
        now, observed = [100.0], []
        first_entered, second_waiting, second_entered, release = Event(), Event(), Event(), Event()

        def monotonic(): return now[0]
        def sleep(seconds):
            observed.append(coordinator.public_status()["machines"]["remote_gpu"])
            now[0] += seconds

        coordinator = MachineWorkCoordinator(
            settings=WorkSchedulerSettings(
                thermal=ThermalPolicy(pause_when_unavailable=False),
                remote_video_cooldown_seconds=30,
            ),
            monitor_interval=10,
            monotonic=monotonic,
            sleep=sleep,
        )

        def first():
            with coordinator.lease("video-1", ComputeResource.REMOTE_GPU,
                    ProductionWorkload.VIDEO_RENDER, "H3 scène 1"):
                first_entered.set()
                release.wait(2)

        def second():
            with coordinator.lease("video-2", ComputeResource.REMOTE_GPU,
                    ProductionWorkload.VIDEO_RENDER, "H3 scène 2",
                    on_wait=second_waiting.set):
                second_entered.set()

        first_thread, second_thread = Thread(target=first), Thread(target=second)
        first_thread.start(); self.assertTrue(first_entered.wait(2))
        second_thread.start()
        self.assertTrue(second_waiting.wait(2))
        release.set()
        first_thread.join(2); second_thread.join(2)

        self.assertTrue(second_entered.is_set())
        self.assertEqual([value["cooldown_remaining_seconds"] for value in observed], [30, 20, 10])
        self.assertTrue(all(value["state"] == "cooling" for value in observed))

    def test_global_settings_are_persisted(self):
        with TemporaryDirectory() as directory:
            store = LocalWorkSchedulerSettings(directory)
            coordinator = MachineWorkCoordinator(settings_store=store)
            settings = WorkSchedulerSettings(
                thermal=ThermalPolicy(stop_temperature_c=82, resume_temperature_c=45,
                                      cooldown_seconds=15, pause_when_unavailable=False),
                remote_video_cooldown_seconds=42,
                pause_after_failure=True,
                history_limit=12,
            )
            coordinator.update_settings(settings)
            restored = MachineWorkCoordinator(settings_store=store).settings
            self.assertEqual(restored, settings)

    def test_llm_gateway_holds_local_lane_until_stream_is_consumed(self):
        stream_entered, release_stream, complete_entered = Event(), Event(), Event()

        class Gateway:
            def list_models(self): return ()
            def stream(self, _request):
                stream_entered.set(); release_stream.wait(2)
                if False: yield None
            def complete(self, request):
                complete_entered.set()
                return CompletionResult(request.model_id, "done")

        gateway = CoordinatedMultimodalGateway(Gateway(), MachineWorkCoordinator(monitor_interval=.01))
        request = CompletionRequest("model", "system", "user")
        stream = Thread(target=lambda: list(gateway.stream(request)))
        complete = Thread(target=lambda: gateway.complete(request))
        stream.start(); self.assertTrue(stream_entered.wait(2)); complete.start()
        self.assertFalse(complete_entered.wait(.05))
        release_stream.set(); self.assertTrue(complete_entered.wait(2))
        stream.join(2); complete.join(2)

    def test_closing_llm_stream_after_terminal_event_is_completed_not_failed(self):
        class Gateway:
            def list_models(self): return ()
            def complete(self, _request): raise AssertionError("not used")
            def stream(self, _request):
                yield CompletionStreamEvent(
                    StreamEventKind.COMPLETED,
                    StreamPhase.COMPLETED,
                    progress=1.0,
                )
                raise AssertionError("the consumer stops at the terminal event")

        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        gateway = CoordinatedMultimodalGateway(Gateway(), coordinator)
        stream = gateway.stream(CompletionRequest("model", "system", "user"))
        self.assertEqual(next(stream).kind, StreamEventKind.COMPLETED)
        stream.close()

        recent = coordinator.public_status()["recent"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["status"], "completed")
        self.assertNotIn("error", recent[0])

    def test_real_failure_keeps_a_short_error_in_history(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.01)
        with self.assertRaisesRegex(RuntimeError, "Comfy hors ligne"):
            with coordinator.lease(
                "render-1",
                ComputeResource.REMOTE_GPU,
                ProductionWorkload.VIDEO_RENDER,
                "H3",
            ):
                raise RuntimeError("Comfy hors ligne")

        recent = coordinator.public_status()["recent"]
        self.assertEqual(recent[0]["status"], "failed")
        self.assertEqual(recent[0]["error_type"], "RuntimeError")
        self.assertEqual(recent[0]["error"], "Comfy hors ligne")


if __name__ == "__main__":
    unittest.main()
