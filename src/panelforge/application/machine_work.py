"""Application-wide FIFO machine lanes, monitoring and thermal admission."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime
import math
from threading import RLock
import time
from typing import Callable, Iterator, Protocol

from panelforge.domain.production import (
    ComputeResource,
    ComputeResourceState,
    ProductionWorkload,
    ThermalPolicy,
    WorkSchedulerSettings,
)
from .production_resources import (
    ResourceLeaseManager,
    ResourceRequirement,
    ResourceWaitCancelled,
)


class WorkSchedulerSettingsStore(Protocol):
    def load(self) -> WorkSchedulerSettings: ...
    def save(self, settings: WorkSchedulerSettings) -> WorkSchedulerSettings: ...


class MachineWorkCoordinator:
    """PanelForge's single admission authority for both physical machines.

    Callers queue before talking to ComfyUI or the LLM server. Each lane is
    FIFO and non-preemptive; local and remote lanes remain independent.
    """

    def __init__(
        self,
        *,
        thermal_monitor=None,
        policy: ThermalPolicy | None = None,
        settings: WorkSchedulerSettings | None = None,
        settings_store: WorkSchedulerSettingsStore | None = None,
        leases: ResourceLeaseManager | None = None,
        monitor_interval: float = 2.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if monitor_interval <= 0:
            raise ValueError("monitor_interval must be positive")
        if settings is not None and policy is not None:
            raise ValueError("use settings or policy, not both")
        if settings is None and settings_store is not None:
            settings = settings_store.load()
        if settings is None:
            settings = WorkSchedulerSettings(
                thermal=policy or ThermalPolicy(pause_when_unavailable=False)
            )
        if not isinstance(settings, WorkSchedulerSettings):
            raise TypeError("settings must be WorkSchedulerSettings")
        self.thermal_monitor = thermal_monitor
        self.leases = leases or ResourceLeaseManager(wait_interval=min(monitor_interval, 0.2))
        self.monitor_interval = monitor_interval
        self._settings = settings
        self._settings_store = settings_store
        self._monotonic = monotonic
        self._sleep = sleep
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._thermal_state: dict[ComputeResource, str | None] = {
            resource: None for resource in ComputeResource
        }
        self._fixed_cooldown_until: dict[ComputeResource, float | None] = {
            resource: None for resource in ComputeResource
        }
        self._fixed_cooldown_operation: dict[ComputeResource, str | None] = {
            resource: None for resource in ComputeResource
        }
        self._last_completed: dict[tuple[ComputeResource, ProductionWorkload], float] = {}
        self._activities: dict[str, dict[str, object]] = {}
        self._recent: list[dict[str, object]] = []

    def configure(self, policy: ThermalPolicy) -> ThermalPolicy:
        """Compatibility entry point; global UI should update all settings."""
        if not isinstance(policy, ThermalPolicy):
            raise TypeError("policy must be a ThermalPolicy")
        self.update_settings(replace(self.settings, thermal=policy))
        return policy

    @property
    def policy(self) -> ThermalPolicy:
        return self.settings.thermal

    @property
    def settings(self) -> WorkSchedulerSettings:
        with self._lock:
            return self._settings

    def update_settings(self, settings: WorkSchedulerSettings) -> WorkSchedulerSettings:
        if not isinstance(settings, WorkSchedulerSettings):
            raise TypeError("settings must be WorkSchedulerSettings")
        if self._settings_store is not None:
            self._settings_store.save(settings)
        with self._lock:
            self._settings = settings
            if len(self._recent) > settings.history_limit:
                self._recent = self._recent[-settings.history_limit:]
        return settings

    def pause(self, resource: ComputeResource) -> None:
        self.leases.set_paused(resource, True)

    def resume(self, resource: ComputeResource) -> None:
        self.leases.set_paused(resource, False)

    def enqueue(
        self,
        owner_id: str,
        resource: ComputeResource,
        workload: ProductionWorkload,
        operation: str,
    ) -> None:
        """Reserve a FIFO position before an application's worker starts."""
        requirement = ResourceRequirement(resource, workload, operation)
        self._register(owner_id, requirement)
        try:
            self.leases.reserve(owner_id, requirement)
        except BaseException:
            with self._lock:
                activity = self._activities.get(owner_id)
                if activity is not None and activity.get("status") == "queued":
                    self._activities.pop(owner_id, None)
            raise

    def cancel_queued(self, owner_id: str) -> bool:
        """Cancel a reservation that has not entered its lease yet."""
        removed = self.leases.cancel_reservation(owner_id)
        if removed:
            self._finish(owner_id, "cancelled")
        return removed

    def report_progress(
        self,
        owner_id: str,
        progress: float | None,
        stage: str | None = None,
    ) -> None:
        if progress is not None:
            if isinstance(progress, bool) or not isinstance(progress, (int, float)) or not math.isfinite(progress):
                raise ValueError("progress must be a finite number or None")
            progress = min(1.0, max(0.0, float(progress)))
        with self._lock:
            activity = self._activities.get(owner_id)
            if activity is None:
                return
            if progress is not None:
                previous = activity.get("progress")
                activity["progress"] = max(float(previous or 0), progress)
            if isinstance(stage, str) and stage.strip():
                activity["stage"] = stage.strip()[:200]
            activity["updated_at"] = self._timestamp()

    def report_stage(self, owner_id: str, stage: str) -> None:
        self.report_progress(owner_id, None, stage)

    def report_execution_id(self, owner_id: str, execution_id: str) -> None:
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValueError("execution_id must not be empty")
        self._update_activity(owner_id, execution_id=execution_id.strip())

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
        self._register(owner_id, requirement)
        started = False

        def acquired() -> None:
            self._update_activity(owner_id, status="admitted", started_at=self._timestamp())
            if on_acquired is not None:
                on_acquired()

        try:
            with self.leases.lease(
                owner_id,
                requirement,
                cancelled=cancelled,
                on_wait=on_wait,
                on_acquired=acquired,
            ):
                self._update_activity(owner_id, status="waiting_safety", stage="Contrôle de la machine")
                self._wait_for_inter_job_cooldown(requirement, cancelled=cancelled)
                self._wait_until_safe(resource, cancelled=cancelled, on_thermal=on_thermal)
                self._update_activity(owner_id, status="running", stage=operation)
                started = True
                try:
                    yield
                finally:
                    # Publish the completion time before releasing the physical
                    # lane. Otherwise the next FIFO owner can enter between the
                    # lease release and the outer finally block, and miss the
                    # mandatory inter-video cooldown entirely.
                    if started:
                        with self._lock:
                            self._last_completed[(resource, workload)] = self._monotonic()
        except ResourceWaitCancelled:
            self._finish(owner_id, "cancelled")
            raise
        except BaseException as error:
            self._finish(owner_id, "failed", error=error)
            if self.settings.pause_after_failure:
                self.pause(resource)
            raise
        else:
            self._finish(owner_id, "completed")

    def cooldown_while_owned(
        self,
        resource: ComputeResource,
        seconds: float,
        operation: str,
        *,
        on_started: Callable[[float], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        """Keep an already-owned machine idle for a fixed inter-job pause."""
        if not isinstance(resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("cooldown seconds must be a non-negative finite number")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("cooldown operation must not be empty")
        if seconds == 0:
            return
        deadline = self._monotonic() + float(seconds)
        with self._lock:
            self._fixed_cooldown_until[resource] = deadline
            self._fixed_cooldown_operation[resource] = operation.strip()
        if on_started is not None:
            on_started(float(seconds))
        try:
            while True:
                if cancelled is not None and cancelled():
                    raise ResourceWaitCancelled()
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    return
                self._sleep(min(self.monitor_interval, remaining))
        finally:
            with self._lock:
                if self._fixed_cooldown_until[resource] == deadline:
                    self._fixed_cooldown_until[resource] = None
                    self._fixed_cooldown_operation[resource] = None
            if on_finished is not None:
                on_finished()

    def _wait_for_inter_job_cooldown(
        self,
        requirement: ResourceRequirement,
        *,
        cancelled: Callable[[], bool],
    ) -> None:
        seconds = (
            self.settings.remote_video_cooldown_seconds
            if requirement.resource is ComputeResource.REMOTE_GPU
            and requirement.workload is ProductionWorkload.VIDEO_RENDER
            else 0
        )
        with self._lock:
            previous = self._last_completed.get((requirement.resource, requirement.workload))
        if not seconds or previous is None:
            return
        remaining = previous + seconds - self._monotonic()
        if remaining > 0:
            self.cooldown_while_owned(
                requirement.resource,
                remaining,
                "Refroidissement avant la prochaine vidéo",
                cancelled=cancelled,
            )

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
        waiters = self.leases.waiters()
        paused = self.leases.paused()
        snapshot = self.thermal_monitor.snapshot() if self.thermal_monitor is not None else None
        settings = self.settings
        policy = settings.thermal
        machines: dict[str, object] = {}
        for resource in ComputeResource:
            owner = owners.get(resource)
            temperature = self._temperature(snapshot, resource) if snapshot is not None else None
            with self._lock:
                thermal_state = self._thermal_state[resource]
                fixed_deadline = self._fixed_cooldown_until[resource]
                fixed_operation = self._fixed_cooldown_operation[resource]
                activity = dict(self._activities.get(owner.job_id, {})) if owner else None
            fixed_remaining = (
                max(0, math.ceil(fixed_deadline - self._monotonic()))
                if fixed_deadline is not None
                else 0
            )
            state = (
                ComputeResourceState.COOLING.value if thermal_state or fixed_remaining else
                ComputeResourceState.BUSY.value if owner is not None else
                ComputeResourceState.PAUSED.value if resource in paused else
                ComputeResourceState.HOT.value if temperature is not None and temperature >= policy.stop_temperature_c else
                ComputeResourceState.UNAVAILABLE.value if snapshot is not None and temperature is None else
                ComputeResourceState.IDLE.value
            )
            if activity is not None and (thermal_state or fixed_remaining):
                activity["status"] = "cooling"
                activity["stage"] = fixed_operation or "Attente thermique"
            queue = [
                self._activity_view(value.job_id, value.requirement, index + 1)
                for index, value in enumerate(waiters.get(resource, ()))
            ]
            machines[resource.value] = {
                "state": state,
                "temperature_c": temperature,
                "owner_id": owner.job_id if owner else None,
                "operation": fixed_operation if fixed_remaining else owner.requirement.operation if owner else None,
                "workload": owner.requirement.workload.value if owner else None,
                "cooldown_remaining_seconds": fixed_remaining,
                "paused": resource in paused,
                "active": activity,
                "queue": queue,
                "queue_count": len(queue),
            }
        with self._lock:
            recent = [dict(value) for value in reversed(self._recent)]
        return {
            "settings": self._settings_dict(settings),
            "policy": asdict(policy),
            "machines": machines,
            "recent": recent,
        }

    def _register(self, owner_id: str, requirement: ResourceRequirement) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must not be empty")
        now = self._timestamp()
        with self._lock:
            existing = self._activities.get(owner_id)
            if existing is not None:
                expected = (
                    requirement.resource.value,
                    requirement.workload.value,
                    requirement.operation,
                )
                actual = (
                    existing.get("resource"),
                    existing.get("workload"),
                    existing.get("operation"),
                )
                if actual != expected:
                    raise ValueError("owner_id already uses another resource requirement")
                return
            self._activities[owner_id] = {
                "id": owner_id,
                "resource": requirement.resource.value,
                "workload": requirement.workload.value,
                "operation": requirement.operation,
                "status": "queued",
                "stage": "En attente",
                "progress": None,
                "queued_at": now,
                "started_at": None,
                "finished_at": None,
                "updated_at": now,
            }

    def _update_activity(self, owner_id: str, **changes) -> None:
        with self._lock:
            activity = self._activities.get(owner_id)
            if activity is None:
                return
            activity.update(changes, updated_at=self._timestamp())

    def _finish(
        self,
        owner_id: str,
        status: str,
        *,
        error: BaseException | None = None,
    ) -> None:
        with self._lock:
            activity = self._activities.pop(owner_id, None)
            if activity is None:
                return
            timestamp = self._timestamp()
            activity.update(
                status=status,
                progress=1.0 if status == "completed" else activity.get("progress"),
                finished_at=timestamp,
                updated_at=timestamp,
            )
            if error is not None:
                activity["error_type"] = type(error).__name__
                message = str(error).strip()
                activity["error"] = (message or type(error).__name__)[:1000]
            self._recent.append(activity)
            self._recent = self._recent[-self._settings.history_limit:]

    def _activity_view(
        self,
        owner_id: str,
        requirement: ResourceRequirement,
        position: int,
    ) -> dict[str, object]:
        with self._lock:
            activity = dict(self._activities.get(owner_id, {}))
        if not activity:
            activity = {
                "id": owner_id,
                "resource": requirement.resource.value,
                "workload": requirement.workload.value,
                "operation": requirement.operation,
                "status": "queued",
                "stage": "En attente",
                "progress": None,
            }
        activity["position"] = position
        return activity

    @staticmethod
    def _settings_dict(settings: WorkSchedulerSettings) -> dict[str, object]:
        return {
            "thermal": asdict(settings.thermal),
            "remote_video_cooldown_seconds": settings.remote_video_cooldown_seconds,
            "pause_after_failure": settings.pause_after_failure,
            "history_limit": settings.history_limit,
        }

    def _timestamp(self) -> str:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must return a timezone-aware datetime")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _monitored(self, resource: ComputeResource) -> bool:
        policy = self.policy
        return policy.monitor_local if resource is ComputeResource.LOCAL_GPU else policy.monitor_remote

    @staticmethod
    def _temperature(snapshot, resource: ComputeResource) -> float | None:
        return snapshot.local_temperature_c if resource is ComputeResource.LOCAL_GPU else snapshot.remote_temperature_c


__all__ = ["MachineWorkCoordinator", "WorkSchedulerSettingsStore"]
