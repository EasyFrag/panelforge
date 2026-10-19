from pathlib import Path
import sys
from threading import Event, Lock, Thread
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application.production_resources import (
    ResourceLeaseManager,
    ResourceRequirement,
    ResourceWaitCancelled,
    llm_compute_resource,
)
from panelforge.domain import (
    ComputeResource,
    ProductionWorkload,
)


class ResourceLeaseManagerTest(unittest.TestCase):

    def test_local_and_remote_lanes_can_be_used_at_the_same_time(self):
        manager = ResourceLeaseManager(wait_interval=0.001)
        local = ResourceRequirement(ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "local LLM")
        remote = ResourceRequirement(ComputeResource.REMOTE_GPU, ProductionWorkload.IMAGE_RENDER, "KREA2")

        with manager.lease("job-1", local, cancelled=lambda: False):
            with manager.lease("job-2", remote, cancelled=lambda: False):
                owners = manager.owners()
                self.assertEqual(owners[ComputeResource.LOCAL_GPU].job_id, "job-1")
                self.assertEqual(owners[ComputeResource.REMOTE_GPU].job_id, "job-2")

    def test_same_lane_is_fifo_and_non_preemptive(self):
        manager = ResourceLeaseManager(wait_interval=0.001)
        requirement = ResourceRequirement(ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM")
        entered = Event()

        def second_job():
            with manager.lease("job-2", requirement, cancelled=lambda: False):
                entered.set()

        with manager.lease("job-1", requirement, cancelled=lambda: False):
            worker = Thread(target=second_job)
            worker.start()
            self.assertFalse(entered.wait(0.02))
        worker.join(1)
        self.assertTrue(entered.is_set())

    def test_service_callbacks_do_not_block_reservations_or_status(self):
        for callback_name in ("cancelled", "on_wait"):
            with self.subTest(callback=callback_name):
                manager = ResourceLeaseManager(wait_interval=0.001)
                resource = ComputeResource.REMOTE_GPU
                requirement = ResourceRequirement(resource, ProductionWorkload.IMAGE_RENDER, "MiniMax")
                manager.set_paused(resource, True)
                service_lock = Lock()
                callback_entered = Event()
                stop = Event()
                cancelled = Event()
                producer_done = Event()
                failures = []
                snapshots = []

                def service_callback():
                    callback_entered.set()
                    with service_lock:
                        stop.set()
                    return True

                def waiting_render():
                    try:
                        with manager.lease(
                            "render", requirement,
                            cancelled=service_callback if callback_name == "cancelled" else stop.is_set,
                            on_wait=service_callback if callback_name == "on_wait" else None,
                        ):
                            failures.append("cancelled render was admitted")
                    except ResourceWaitCancelled:
                        cancelled.set()
                    except BaseException as error:
                        failures.append(error)

                def enqueue_next():
                    try:
                        manager.reserve("next", requirement)
                        snapshots.append((manager.owners(), manager.waiters()[resource]))
                    except BaseException as error:
                        failures.append(error)
                    finally:
                        producer_done.set()

                waiter = Thread(target=waiting_render, daemon=True)
                producer = Thread(target=enqueue_next, daemon=True)
                try:
                    # The callback waits on a service lock while another thread
                    # queues work, just as prompt completion queues an image.
                    with service_lock:
                        waiter.start()
                        self.assertTrue(callback_entered.wait(1))
                        producer.start()
                        self.assertTrue(producer_done.wait(1), "service callback locked the shared queue")
                finally:
                    # Release the service lock before joining, even on failure.
                    # This also lets the pre-fix implementation exit cleanly.
                    stop.set()
                    if waiter.ident is not None:
                        waiter.join(1)
                    if producer.ident is not None:
                        producer.join(1)
                self.assertFalse(waiter.is_alive())
                self.assertFalse(producer.is_alive())
                self.assertEqual(failures, [])
                self.assertTrue(cancelled.is_set())
                self.assertEqual(snapshots[0][0], {})
                self.assertEqual([value.job_id for value in snapshots[0][1]], ["render", "next"])
                self.assertEqual([value.job_id for value in manager.waiters()[resource]], ["next"])
                with manager.lease("local", ResourceRequirement(
                    ComputeResource.LOCAL_GPU, ProductionWorkload.LLM, "LLM",
                ), cancelled=lambda: False):
                    self.assertEqual(manager.owners()[ComputeResource.LOCAL_GPU].job_id, "local")
                manager.set_paused(resource, False)
                with manager.lease("next", requirement, cancelled=lambda: False):
                    self.assertEqual(manager.owners()[resource].job_id, "next")

    def test_callback_failures_release_the_ticket_or_owner(self):
        for callback_name in ("cancelled", "on_wait", "on_acquired"):
            with self.subTest(callback=callback_name):
                manager = ResourceLeaseManager(wait_interval=0.001)
                resource = ComputeResource.REMOTE_GPU
                requirement = ResourceRequirement(resource, ProductionWorkload.IMAGE_RENDER, "MiniMax")
                manager.set_paused(resource, callback_name == "on_wait")

                def fail():
                    raise RuntimeError("service callback failed")

                callbacks = {"cancelled": lambda: False, callback_name: fail}
                with self.assertRaisesRegex(RuntimeError, "service callback failed"):
                    with manager.lease("broken", requirement, **callbacks):
                        self.fail("failing callback admitted the job")
                self.assertEqual(manager.owners(), {})
                self.assertEqual(manager.waiters()[resource], ())
                manager.set_paused(resource, False)
                with manager.lease("next", requirement, cancelled=lambda: False):
                    self.assertEqual(manager.owners()[resource].job_id, "next")

    def test_model_sources_map_to_their_physical_machine(self):
        self.assertEqual(llm_compute_resource("local::qwen"), ComputeResource.LOCAL_GPU)
        self.assertEqual(llm_compute_resource("server-model"), ComputeResource.REMOTE_GPU)


if __name__ == "__main__":
    unittest.main()
