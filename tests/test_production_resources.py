from dataclasses import replace
from pathlib import Path
import sys
from threading import Event, Lock, Thread
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application.production import ProductionService, _resource_operation_label
from panelforge.application.production_resources import (
    ResourceLeaseManager,
    ResourceRequirement,
    llm_compute_resource,
)
from panelforge.domain import (
    ComputeResource,
    CreativeFreedomAxes,
    Krea2AspectRatio,
    Krea2BatchSettings,
    ProductionConfig,
    ProductionJob,
    ProductionStage,
    ProductionStatus,
    ProductionWorkload,
    ThermalPolicy,
    ThermalSnapshot,
)


class ResourceLeaseManagerTest(unittest.TestCase):
    def test_runtime_operations_use_stable_user_facing_phase_names(self):
        self.assertEqual(
            _resource_operation_label(ProductionStage.IMAGE_GENERATION, ProductionWorkload.LLM),
            "KREA2",
        )
        self.assertEqual(
            _resource_operation_label(ProductionStage.H3_PROMPT, ProductionWorkload.LLM),
            "H3_plan",
        )
        self.assertEqual(
            _resource_operation_label(ProductionStage.VIDEO_PREVIEW, ProductionWorkload.VIDEO_RENDER),
            "H3_low",
        )
        self.assertEqual(
            _resource_operation_label(ProductionStage.VIDEO_FINAL, ProductionWorkload.VIDEO_RENDER),
            "H3_high",
        )

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

    def test_model_sources_map_to_their_physical_machine(self):
        self.assertEqual(llm_compute_resource("local::qwen"), ComputeResource.LOCAL_GPU)
        self.assertEqual(llm_compute_resource("server-model"), ComputeResource.REMOTE_GPU)


class _Jobs:
    def __init__(self, job):
        self.job = job

    def get(self, _job_id):
        return self.job

    def save(self, job):
        self.job = job
        return job


class _Monitor:
    def __init__(self, snapshot):
        self.value = snapshot

    def snapshot(self):
        return self.value


def _job() -> ProductionJob:
    return ProductionJob(
        job_id="job-1",
        name="Test",
        intention="Animate the image.",
        source_asset_id="source",
        source_filename="source.png",
        config=ProductionConfig(
            model_id="local::qwen",
            image_settings=Krea2BatchSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=2.1,
            ),
            creative_axes=CreativeFreedomAxes(3, 3, 3),
            thermal=ThermalPolicy(cooldown_seconds=0),
        ),
        status=ProductionStatus.RUNNING,
    )


class ResourceThermalIsolationTest(unittest.TestCase):
    def _service(self, snapshot):
        job = _job()
        return ProductionService(
            gateway=None,
            assets=None,
            jobs=_Jobs(job),
            krea2=None,
            prompt_lab=None,
            composition=None,
            h3_render=None,
            thermal_monitor=_Monitor(snapshot),
            monitor_interval=0.001,
        )

    def test_hot_local_gpu_does_not_block_remote_render_lane(self):
        service = self._service(ThermalSnapshot(local_temperature_c=90, remote_temperature_c=30))
        service._wait_until_safe("job-1", ComputeResource.REMOTE_GPU)
        self.assertEqual(service.get("job-1").status, ProductionStatus.RUNNING)

    def test_hot_remote_gpu_does_not_block_local_llm_lane(self):
        service = self._service(ThermalSnapshot(local_temperature_c=30, remote_temperature_c=90))
        service._wait_until_safe("job-1", ComputeResource.LOCAL_GPU)
        self.assertEqual(service.get("job-1").status, ProductionStatus.RUNNING)

    def test_missing_local_telemetry_does_not_block_remote_lane(self):
        service = self._service(ThermalSnapshot(local_error="offline", remote_temperature_c=30))
        service._wait_until_safe("job-1", ComputeResource.REMOTE_GPU)
        self.assertEqual(service.get("job-1").status, ProductionStatus.RUNNING)


class _ManyJobs:
    def __init__(self, jobs):
        self.values = {job.job_id: job for job in jobs}
        self.lock = Lock()

    def get(self, job_id):
        with self.lock:
            return self.values[job_id]

    def save(self, job):
        with self.lock:
            self.values[job.job_id] = job
        return job


class ProductionJobConcurrencyTest(unittest.TestCase):
    def test_at_most_two_jobs_are_active(self):
        jobs = [
            replace(_job(), job_id=f"job-{index}", status=ProductionStatus.QUEUED)
            for index in range(3)
        ]
        store = _ManyJobs(jobs)
        service = ProductionService(
            gateway=None,
            assets=None,
            jobs=store,
            krea2=None,
            prompt_lab=None,
            composition=None,
            h3_render=None,
            thermal_monitor=_Monitor(ThermalSnapshot(local_temperature_c=30, remote_temperature_c=30)),
            monitor_interval=0.001,
            max_active_jobs=2,
        )
        lock = Lock()
        release = Event()
        two_active = Event()
        active = 0
        maximum = 0

        def advance(job):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                if active == 2:
                    two_active.set()
            release.wait(1)
            with lock:
                active -= 1
            return replace(job, status=ProductionStatus.WAITING_FOR_REVIEW)

        service._advance = advance
        workers = [Thread(target=service.run, args=(job.job_id,)) for job in jobs]
        for worker in workers:
            worker.start()
        self.assertTrue(two_active.wait(1))
        with lock:
            self.assertEqual(active, 2)
        release.set()
        for worker in workers:
            worker.join(1)
        self.assertEqual(maximum, 2)

if __name__ == "__main__":
    unittest.main()
