"""Global pause uses fake temperature probes and never calls a compute engine."""

from dataclasses import replace
import json
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic
import unittest
from unittest.mock import patch

from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.application.production_resources import ResourceWaitCancelled
from panelforge.domain.production import (
    ComputeResource, ProductionWorkload, ThermalPolicy, ThermalSnapshot, WorkSchedulerSettings,
)
from panelforge.infrastructure.storage.work_scheduler_settings import LocalWorkSchedulerSettings


class Monitor:
    def __init__(self, local=50, remote=50):
        self.value = ThermalSnapshot(local_temperature_c=local, remote_temperature_c=remote)

    def snapshot(self):
        return self.value


class GlobalThermalPauseTest(unittest.TestCase):
    def make_coordinator(self, monitor, **kwargs):
        return MachineWorkCoordinator(
            thermal_monitor=monitor,
            settings=WorkSchedulerSettings(
                thermal=ThermalPolicy(stop_temperature_c=100, pause_when_unavailable=False),
                local_cooldown_seconds=0, remote_non_video_cooldown_seconds=0,
                remote_video_cooldown_seconds=0,
            ),
            monitor_interval=.01,
            **kwargs,
        )

    def wait_until(self, predicate):
        deadline = monotonic() + 2
        while not predicate() and monotonic() < deadline:
            Event().wait(.005)
        self.assertTrue(predicate())

    def sample(self, coordinator):
        coordinator._thermal_snapshot(force=True)
        return coordinator.public_status()

    def test_strict_threshold_on_either_gpu_latches_both_lanes(self):
        for resource in ComputeResource:
            with self.subTest(resource=resource):
                monitor = Monitor(86, 86)
                coordinator = self.make_coordinator(monitor)
                self.assertFalse(self.sample(coordinator)['global_thermal_pause']['paused'])
                monitor.value = ThermalSnapshot(
                    local_temperature_c=86.1 if resource is ComputeResource.LOCAL_GPU else 50,
                    remote_temperature_c=86.1 if resource is ComputeResource.REMOTE_GPU else 50,
                )
                status = self.sample(coordinator)
                self.assertEqual(status['global_thermal_pause']['incident']['resource'], resource.value)
                self.assertTrue(all(machine['paused'] for machine in status['machines'].values()))
                self.assertFalse(status['global_thermal_pause']['can_resume'])

    def test_cooling_lane_resume_and_settings_edits_do_not_clear_latch(self):
        monitor = Monitor(87, 50)
        coordinator = self.make_coordinator(monitor)
        incident = self.sample(coordinator)['global_thermal_pause']['incident']
        monitor.value = ThermalSnapshot(local_temperature_c=60, remote_temperature_c=60)
        self.sample(coordinator)
        for resource in ComputeResource:
            coordinator.resume(resource)
        coordinator.update_settings(replace(coordinator.settings, global_thermal_pause_enabled=False))
        status = coordinator.public_status()
        self.assertEqual(status['global_thermal_pause']['incident'], incident)
        self.assertTrue(all(machine['paused'] for machine in status['machines'].values()))
        self.assertTrue(status['global_thermal_pause']['can_resume'])
        coordinator.pause(ComputeResource.REMOTE_GPU)
        coordinator.resume_global_thermal_pause()
        status = coordinator.public_status()
        self.assertFalse(status['global_thermal_pause']['paused'])
        self.assertFalse(status['machines']['local_gpu']['paused'])
        self.assertTrue(status['machines']['remote_gpu']['paused'])

    def test_resume_requires_fresh_known_readings_strictly_below_threshold(self):
        monitor = Monitor(50, 87)
        now = [0.0]
        coordinator = self.make_coordinator(monitor, monotonic=lambda: now[0])
        self.sample(coordinator)
        monitor.value = ThermalSnapshot(local_temperature_c=60, remote_temperature_c=60)
        self.assertTrue(self.sample(coordinator)['global_thermal_pause']['can_resume'])
        now[0] = 3
        self.assertFalse(coordinator._global_thermal_pause_view()['can_resume'])
        for value in (86, 87, None):
            monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=value)
            with self.subTest(temperature=value), self.assertRaises(ValueError):
                coordinator.resume_global_thermal_pause()
            self.assertTrue(coordinator.public_status()['global_thermal_pause']['paused'])
        monitor.value = ThermalSnapshot(local_temperature_c=85, remote_temperature_c=85)
        coordinator.resume_global_thermal_pause()
        self.assertFalse(coordinator.public_status()['global_thermal_pause']['paused'])

    def test_global_monitoring_is_independent_of_cooldown_monitoring_switches(self):
        coordinator = self.make_coordinator(Monitor(87, 50))
        coordinator.update_settings(replace(coordinator.settings,
            thermal=replace(coordinator.policy, monitor_local=False)))
        self.assertTrue(self.sample(coordinator)['global_thermal_pause']['paused'])

    def test_disabled_protection_does_not_latch_and_enabling_checks_current_sample(self):
        coordinator = self.make_coordinator(Monitor(87, 50))
        coordinator.update_settings(replace(coordinator.settings, global_thermal_pause_enabled=False))
        self.assertFalse(self.sample(coordinator)['global_thermal_pause']['paused'])
        coordinator.update_settings(replace(coordinator.settings, global_thermal_pause_enabled=True))
        self.assertTrue(coordinator.public_status()['global_thermal_pause']['paused'])

    def test_active_work_finishes_and_both_queues_wait_in_order_until_manual_resume(self):
        monitor = Monitor()
        coordinator = self.make_coordinator(monitor)
        entered = {resource: Event() for resource in ComputeResource}
        release, cancel = Event(), Event()
        following = {resource: [] for resource in ComputeResource}
        failures = []

        def active(resource):
            try:
                with coordinator.lease('active-' + resource, resource, ProductionWorkload.LLM, 'En cours'):
                    entered[resource].set()
                    release.wait(3)
            except Exception as error:
                failures.append(error)

        def next_job(resource, index):
            try:
                with coordinator.lease(f'{resource}-{index}', resource, ProductionWorkload.LLM,
                                       'Suivant', cancelled=cancel.is_set):
                    following[resource].append(index)
            except ResourceWaitCancelled:
                pass
            except Exception as error:
                failures.append(error)

        threads = [Thread(target=active, args=(resource,), daemon=True) for resource in ComputeResource]
        try:
            for thread in threads:
                thread.start()
            self.assertTrue(all(event.wait(2) for event in entered.values()))
            for index in (1, 2):
                for resource in ComputeResource:
                    coordinator.enqueue(f'{resource}-{index}', resource, ProductionWorkload.LLM, 'Suivant')
                    thread = Thread(target=next_job, args=(resource, index), daemon=True)
                    threads.append(thread)
                    thread.start()
            monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=87)
            status = self.sample(coordinator)
            self.assertTrue(all(machine['active']['status'] == 'running' for machine in status['machines'].values()))
            release.set()
            self.wait_until(lambda: not coordinator.leases.owners())
            self.assertFalse(any(following.values()))
            self.assertTrue(all(len(queue) == 2 for queue in coordinator.leases.waiters().values()))
            monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=50)
            self.sample(coordinator)
            self.assertFalse(any(following.values()))
            coordinator.resume_global_thermal_pause()
            self.wait_until(lambda: all(values == [1, 2] for values in following.values()))
            self.assertEqual(failures, [])
            self.wait_until(lambda: len(coordinator.public_status()['recent']) == 6)
            self.assertTrue(all(item['status'] == 'completed' for item in coordinator.public_status()['recent']))
        finally:
            release.set()
            cancel.set()
            for thread in threads:
                thread.join(2)

    def test_pause_during_admission_blocks_owner_already_waiting_for_safety(self):
        monitor = Monitor()
        coordinator = self.make_coordinator(monitor)
        checking, continue_check, running, cancel = Event(), Event(), Event(), Event()
        failures = []

        def safety(*args, **kwargs):
            checking.set()
            continue_check.wait(2)

        def work():
            try:
                with coordinator.lease('waiting', ComputeResource.LOCAL_GPU, ProductionWorkload.LLM,
                                       'LLM', cancelled=cancel.is_set):
                    running.set()
            except ResourceWaitCancelled:
                pass
            except Exception as error:
                failures.append(error)

        with patch.object(coordinator, '_wait_until_safe', side_effect=safety):
            thread = Thread(target=work, daemon=True)
            try:
                thread.start()
                self.assertTrue(checking.wait(2))
                monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=87)
                self.sample(coordinator)
                continue_check.set()
                self.assertFalse(running.wait(.05))
                self.assertEqual(coordinator.public_status()['machines']['local_gpu']['state'], 'paused')
                monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=50)
                coordinator.resume_global_thermal_pause()
                self.assertTrue(running.wait(2))
                self.assertEqual(failures, [])
            finally:
                continue_check.set()
                cancel.set()
                thread.join(2)

    def test_background_sampler_triggers_without_a_browser_or_status_request(self):
        coordinator = self.make_coordinator(Monitor(87, 50))
        try:
            coordinator.start_temperature_sampling()
            self.wait_until(lambda: coordinator._global_thermal_pause is not None)
            self.assertTrue(coordinator._global_thermal_pause_view()['paused'])
        finally:
            coordinator.stop_temperature_sampling()

    def test_settings_and_latched_incident_survive_restart(self):
        with TemporaryDirectory() as directory:
            store = LocalWorkSchedulerSettings(directory)
            store.save(WorkSchedulerSettings(local_cooldown_seconds=42))
            legacy = json.loads(store.path.read_text(encoding='utf-8'))
            legacy.pop('global_thermal_pause_enabled')
            legacy.pop('global_thermal_pause_temperature_c')
            store.path.write_text(json.dumps(legacy), encoding='utf-8')
            self.assertTrue(store.load().global_thermal_pause_enabled)
            self.assertEqual(store.load().global_thermal_pause_temperature_c, 86)
            self.assertEqual(store.load().local_cooldown_seconds, 42)
            monitor = Monitor(87, 50)
            coordinator = MachineWorkCoordinator(thermal_monitor=monitor, settings_store=store)
            incident = self.sample(coordinator)['global_thermal_pause']['incident']
            monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=50)
            restored = MachineWorkCoordinator(thermal_monitor=monitor, settings_store=store)
            self.assertEqual(restored.public_status()['global_thermal_pause']['incident'], incident)
            restored.update_settings(replace(restored.settings, global_thermal_pause_temperature_c=85))
            self.assertEqual(store.load().global_thermal_pause_temperature_c, 85)
            self.assertIsNotNone(store.load_global_thermal_pause())
            restored.resume_global_thermal_pause()
            self.assertIsNone(store.load_global_thermal_pause())
            self.assertFalse(MachineWorkCoordinator(settings_store=store)._global_thermal_pause_view()['paused'])

    def test_persistence_failure_keeps_pause_and_failed_acknowledgement_cannot_resume(self):
        with TemporaryDirectory() as directory:
            store = LocalWorkSchedulerSettings(directory)
            monitor = Monitor(87, 50)
            coordinator = self.make_coordinator(monitor, settings_store=store)
            with patch.object(store, 'save_global_thermal_pause', side_effect=OSError('disk unavailable')):
                status = self.sample(coordinator)
                self.assertTrue(status['global_thermal_pause']['paused'])
                self.assertIn('disk unavailable', status['global_thermal_pause']['persistence_error'])
            self.sample(coordinator)
            self.assertIsNotNone(store.load_global_thermal_pause())
            monitor.value = ThermalSnapshot(local_temperature_c=50, remote_temperature_c=50)
            with patch.object(store, 'save_global_thermal_pause', side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):
                    coordinator.resume_global_thermal_pause()
            self.assertTrue(coordinator.public_status()['global_thermal_pause']['paused'])

    def test_invalid_global_settings_are_rejected(self):
        for temperature in (float('nan'), float('inf'), 29, 111, True):
            with self.subTest(temperature=temperature), self.assertRaises((TypeError, ValueError)):
                WorkSchedulerSettings(global_thermal_pause_temperature_c=temperature)
        with self.assertRaises(TypeError):
            WorkSchedulerSettings(global_thermal_pause_enabled=1)


if __name__ == '__main__':
    unittest.main()
