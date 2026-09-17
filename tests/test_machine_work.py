from threading import Event, Lock, Thread
import unittest

from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.application.prompt_lab import CompletionRequest, CompletionResult
from panelforge.domain.production import ComputeResource, ProductionWorkload, ThermalPolicy, ThermalSnapshot
from panelforge.infrastructure.llm.coordinated import CoordinatedMultimodalGateway


class Monitor:
    def __init__(self, values): self.values = iter(values)
    def snapshot(self): return next(self.values)


class MachineWorkCoordinatorTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
