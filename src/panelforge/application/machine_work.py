"""Application-wide exclusive machine lanes with a configurable thermal gate."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from threading import RLock
import time
from typing import Callable, Iterator

from panelforge.domain.production import (
    ComputeResource,
    ComputeResourceState,
    ProductionWorkload,
    ThermalPolicy,
)
from .production_resources import ResourceLeaseManager, ResourceRequirement


class MachineWorkCoordinator:
    """Serialize work per physical machine, independently across machines.

    The coordinator deliberately owns execution capacity rather than submission
    capacity: a remote lease is retained until the Comfy job is terminal.
    """

    def __init__(
        self,
        *,
        thermal_monitor=None,
        policy: ThermalPolicy | None = None,
        leases: ResourceLeaseManager | None = None,
        monitor_interval: float = 2.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if monitor_interval <= 0:
            raise ValueError("monitor_interval must be positive")
        self.thermal_monitor = thermal_monitor
        self.leases = leases or ResourceLeaseManager(wait_interval=min(monitor_interval, 0.2))
        self.monitor_interval = monitor_interval
        self._policy = policy or ThermalPolicy(pause_when_unavailable=False)
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = RLock()
        self._thermal_state: dict[ComputeResource, str | None] = {
            resource: None for resource in ComputeResource
        }

    def configure(self, policy: ThermalPolicy) -> ThermalPolicy:
        if not isinstance(policy, ThermalPolicy):
            raise TypeError("policy must be a ThermalPolicy")
        with self._lock:
            self._policy = policy
        return policy

    @property
    def policy(self) -> ThermalPolicy:
        with self._lock:
            return self._policy

    @contextmanager
    def lease(
        self,
        owner_id: str,
        resource: ComputeResource,
        workload: ProductionWorkload,
        operation: str,
        *,
        cancelled: Callable[[], bool] | None = None,
        on_wait: Callable[[], None] | None = None,
        on_acquired: Callable[[], None] | None = None,
        on_thermal: Callable[[], None] | None = None,
    ) -> Iterator[None]:
        cancelled = cancelled or (lambda: False)
        requirement = ResourceRequirement(resource, workload, operation)
        with self.leases.lease(
            owner_id,
            requirement,
            cancelled=cancelled,
            on_wait=on_wait,
            on_acquired=on_acquired,
        ):
            self._wait_until_safe(resource, cancelled=cancelled, on_thermal=on_thermal)
            yield

    def _wait_until_safe(
        self,
        resource: ComputeResource,
        *,
        cancelled: Callable[[], bool],
        on_thermal: Callable[[], None] | None,
    ) -> None:
        if self.thermal_monitor is None or not self._monitored(resource):
            return
        policy = self.policy
        snapshot = self.thermal_monitor.snapshot()
        temperature = self._temperature(snapshot, resource)
        unavailable = temperature is None
        if not ((temperature is not None and temperature >= policy.stop_temperature_c)
                or (unavailable and policy.pause_when_unavailable)):
            return
        with self._lock:
            self._thermal_state[resource] = "cooling"
        if on_thermal is not None:
            on_thermal()
        below_since: float | None = None
        try:
            while True:
                if cancelled():
                    from .production_resources import ResourceWaitCancelled
                    raise ResourceWaitCancelled()
                snapshot = self.thermal_monitor.snapshot()
                temperature = self._temperature(snapshot, resource)
                safe = (
                    temperature is not None and temperature <= policy.resume_temperature_c
                ) or (temperature is None and not policy.pause_when_unavailable)
                now = self._monotonic()
                if safe:
                    below_since = now if below_since is None else below_since
                    if now - below_since >= policy.cooldown_seconds:
                        return
                else:
                    below_since = None
                self._sleep(self.monitor_interval)
        finally:
            with self._lock:
                self._thermal_state[resource] = None

    def public_status(self) -> dict[str, object]:
        owners = self.leases.owners()
        snapshot = self.thermal_monitor.snapshot() if self.thermal_monitor is not None else None
        policy = self.policy
        machines: dict[str, object] = {}
        for resource in ComputeResource:
            owner = owners.get(resource)
            temperature = self._temperature(snapshot, resource) if snapshot is not None else None
            with self._lock:
                thermal_state = self._thermal_state[resource]
            state = (
                ComputeResourceState.COOLING.value if thermal_state else
                ComputeResourceState.BUSY.value if owner is not None else
                ComputeResourceState.HOT.value if temperature is not None and temperature >= policy.stop_temperature_c else
                ComputeResourceState.UNAVAILABLE.value if snapshot is not None and temperature is None else
                ComputeResourceState.IDLE.value
            )
            machines[resource.value] = {
                "state": state,
                "temperature_c": temperature,
                "owner_id": owner.job_id if owner else None,
                "operation": owner.requirement.operation if owner else None,
                "workload": owner.requirement.workload.value if owner else None,
            }
        return {"policy": asdict(policy), "machines": machines}

    def _monitored(self, resource: ComputeResource) -> bool:
        policy = self.policy
        return policy.monitor_local if resource is ComputeResource.LOCAL_GPU else policy.monitor_remote

    @staticmethod
    def _temperature(snapshot, resource: ComputeResource) -> float | None:
        return snapshot.local_temperature_c if resource is ComputeResource.LOCAL_GPU else snapshot.remote_temperature_c


__all__ = ["MachineWorkCoordinator"]
