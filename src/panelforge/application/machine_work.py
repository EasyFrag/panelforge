"""Application-wide FIFO machine lanes, monitoring and thermal admission."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
import math
from threading import Event, RLock, Thread
import time
from typing import Callable, Iterator, Protocol
from uuid import uuid4

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


_TEMPERATURE_HISTORY_SECONDS = 3_600
_PERSISTENT_TEMPERATURE_HISTORY_SECONDS = 86_400
_TEMPERATURE_BUCKET_SECONDS = 15
_TEMPERATURE_SAMPLE_SECONDS = 2.0
_LLM_RATE_WINDOW_SECONDS = 5.0
_THERMAL_EVENT_MARKERS = {
    ProductionWorkload.LLM: 'P',
    ProductionWorkload.IMAGE_RENDER: 'I',
    ProductionWorkload.VIDEO_RENDER: 'V',
    ProductionWorkload.DLSS: 'D',
}


class WorkSchedulerSettingsStore(Protocol):
    def load(self) -> WorkSchedulerSettings: ...
    def save(self, settings: WorkSchedulerSettings) -> WorkSchedulerSettings: ...


class ThermalHistoryStore(Protocol):
    def record_sample(
        self,
        observed_at: datetime,
        *,
        local_temperature_c: float | None,
        remote_temperature_c: float | None,
    ) -> None: ...
    def record_event_start(
        self,
        event_id: str,
        *,
        resource: ComputeResource,
        workload: ProductionWorkload,
        operation: str,
        started_at: datetime,
    ) -> None: ...
    def record_event_finish(
        self,
        event_id: str,
        *,
        finished_at: datetime,
        status: str,
        peak_temperature_c: float | None,
    ) -> None: ...
    def recover_open_events(self, observed_at: datetime) -> None: ...
    def load(self, *, since: datetime, until: datetime) -> dict[str, list[dict[str, object]]]: ...


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
        thermal_history_store: ThermalHistoryStore | None = None,
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
        self._thermal_history_store = thermal_history_store
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
        self._temperature_history: dict[ComputeResource, deque[tuple[float, float]]] = {
            resource: deque() for resource in ComputeResource
        }
        self._latest_thermal_snapshot = None
        self._latest_thermal_at: float | None = None
        self._temperature_sampler_stop = Event()
        self._temperature_sampler_thread: Thread | None = None
        self._thermal_read_lock = RLock()
        self._llm_token_windows: dict[str, deque[tuple[float, int]]] = {}
        self._llm_started_at: dict[str, float] = {}
        self._persistent_temperature_bucket_at: datetime | None = None
        self._persistent_temperature_maxima: dict[ComputeResource, float | None] = {
            resource: None for resource in ComputeResource
        }
        self._thermal_event_ids: dict[str, str] = {}
        self._thermal_history_error: str | None = None
        if self._thermal_history_store is not None:
            try:
                self._thermal_history_store.recover_open_events(self._utc_now())
            except Exception as error:
                self._thermal_history_error = str(error)[:500]

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

    def start_temperature_sampling(self) -> None:
        if self.thermal_monitor is None:
            return
        with self._lock:
            thread = self._temperature_sampler_thread
            if thread is not None and thread.is_alive():
                return
            self._temperature_sampler_stop.clear()
            thread = Thread(
                target=self._temperature_sampling_loop,
                name='panelforge-temperature-history',
                daemon=True,
            )
            self._temperature_sampler_thread = thread
        thread.start()

    def stop_temperature_sampling(self) -> None:
        self._temperature_sampler_stop.set()
        with self._lock:
            thread = self._temperature_sampler_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=7.0)
        with self._lock:
            if self._temperature_sampler_thread is thread:
                self._temperature_sampler_thread = None
        self._flush_persistent_temperature_bucket()

    def _temperature_sampling_loop(self) -> None:
        while not self._temperature_sampler_stop.is_set():
            try:
                self._thermal_snapshot(force=True)
            except Exception:
                pass
            self._temperature_sampler_stop.wait(_TEMPERATURE_SAMPLE_SECONDS)

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

    def has_activity(self, owner_id: str) -> bool:
        """Return whether this process currently owns or queues the work item."""
        if not isinstance(owner_id, str) or not owner_id.strip():
            return False
        with self._lock:
            return owner_id in self._activities

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

    def report_llm_tokens(self, owner_id: str, channel: str, count: int = 1) -> None:
        if channel not in {'thinking', 'writing'}:
            raise ValueError('channel must be thinking or writing')
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError('count must be a positive integer')
        now = self._monotonic()
        with self._lock:
            activity = self._activities.get(owner_id)
            if activity is None:
                return
            metrics = activity.setdefault('llm_metrics', {
                'thinking_tokens': 0,
                'writing_tokens': 0,
                'tokens_per_second': 0.0,
                'estimated': True,
            })
            key = f'{channel}_tokens'
            metrics[key] = int(metrics[key]) + count
            started = self._llm_started_at.setdefault(owner_id, now)
            window = self._llm_token_windows.setdefault(owner_id, deque())
            window.append((now, count))
            cutoff = now - _LLM_RATE_WINDOW_SECONDS
            while window and window[0][0] < cutoff:
                window.popleft()
            elapsed = max(1.0, min(_LLM_RATE_WINDOW_SECONDS, now - started))
            metrics['tokens_per_second'] = round(sum(value for _, value in window) / elapsed, 1)
            activity['updated_at'] = self._timestamp()

    def reconcile_llm_tokens(
        self,
        owner_id: str,
        total_tokens: int | None,
        reasoning_tokens: int | None = None,
    ) -> None:
        if total_tokens is None:
            return
        if isinstance(total_tokens, bool) or not isinstance(total_tokens, int) or total_tokens < 0:
            return
        if (
            reasoning_tokens is not None
            and (
                isinstance(reasoning_tokens, bool)
                or not isinstance(reasoning_tokens, int)
                or not 0 <= reasoning_tokens <= total_tokens
            )
        ):
            reasoning_tokens = None
        with self._lock:
            activity = self._activities.get(owner_id)
            metrics = activity.get('llm_metrics') if activity is not None else None
            if not isinstance(metrics, dict):
                return
            thinking = int(metrics.get('thinking_tokens') or 0)
            writing = int(metrics.get('writing_tokens') or 0)
            observed = thinking + writing
            if reasoning_tokens is not None:
                metrics['thinking_tokens'] = reasoning_tokens
                metrics['writing_tokens'] = total_tokens - reasoning_tokens
            elif observed:
                exact_thinking = round(total_tokens * thinking / observed)
                metrics['thinking_tokens'] = exact_thinking
                metrics['writing_tokens'] = max(0, total_tokens - exact_thinking)
            else:
                metrics['writing_tokens'] = total_tokens
            metrics['estimated'] = reasoning_tokens is None and thinking > 0

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
                self._start_thermal_event(owner_id, requirement)
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
                        self._schedule_local_cooldown(owner_id, requirement)
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
        with self._lock:
            fixed_deadline = self._fixed_cooldown_until[requirement.resource]
        fixed_remaining = (
            fixed_deadline - self._monotonic()
            if fixed_deadline is not None
            else 0
        )
        if fixed_remaining > 0:
            while fixed_remaining > 0:
                if cancelled():
                    raise ResourceWaitCancelled()
                self._sleep(min(self.monitor_interval, fixed_remaining))
                fixed_remaining = fixed_deadline - self._monotonic()
            with self._lock:
                if self._fixed_cooldown_until[requirement.resource] == fixed_deadline:
                    self._fixed_cooldown_until[requirement.resource] = None
                    self._fixed_cooldown_operation[requirement.resource] = None
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

    def _schedule_local_cooldown(
        self,
        owner_id: str,
        requirement: ResourceRequirement,
    ) -> None:
        settings = self.settings
        if (
            requirement.resource is not ComputeResource.LOCAL_GPU
            or not settings.thermal.monitor_local
            or settings.local_cooldown_seconds == 0
        ):
            return
        with self._lock:
            activity = self._activities.get(owner_id)
            peak = activity.get('peak_temperature_c') if activity is not None else None
            if peak is None or float(peak) < settings.local_cooldown_temperature_c:
                return
            self._fixed_cooldown_until[ComputeResource.LOCAL_GPU] = (
                self._monotonic() + settings.local_cooldown_seconds
            )
            self._fixed_cooldown_operation[ComputeResource.LOCAL_GPU] = (
                f'Refroidissement local après un pic à {round(float(peak))} °C'
            )
            activity['cooldown_triggered'] = True

    def _wait_until_safe(
        self,
        resource: ComputeResource,
        *,
        cancelled: Callable[[], bool],
        on_thermal: Callable[[], None] | None,
    ) -> None:
        if (
            resource is ComputeResource.LOCAL_GPU
            or self.thermal_monitor is None
            or not self._monitored(resource)
        ):
            return
        policy = self.policy
        snapshot = self._thermal_snapshot()
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
                snapshot = self._thermal_snapshot(force=True)
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

    def _thermal_snapshot(self, *, force: bool = False):
        if self.thermal_monitor is None:
            return None
        now = self._monotonic()
        with self._lock:
            cached = self._latest_thermal_snapshot
            cached_at = self._latest_thermal_at
        if not force and cached is not None and cached_at is not None:
            if now - cached_at < _TEMPERATURE_SAMPLE_SECONDS:
                return cached
        with self._thermal_read_lock:
            now = self._monotonic()
            with self._lock:
                cached = self._latest_thermal_snapshot
                cached_at = self._latest_thermal_at
            if not force and cached is not None and cached_at is not None:
                if now - cached_at < _TEMPERATURE_SAMPLE_SECONDS:
                    return cached
            snapshot = self.thermal_monitor.snapshot()
            self._record_temperature_snapshot(snapshot, self._monotonic())
            return snapshot

    def _record_temperature_snapshot(self, snapshot, observed_at: float) -> None:
        owners = self.leases.owners()
        cutoff = observed_at - _TEMPERATURE_HISTORY_SECONDS
        persistent_sample = None
        with self._lock:
            self._latest_thermal_snapshot = snapshot
            self._latest_thermal_at = observed_at
            for resource in ComputeResource:
                temperature = self._temperature(snapshot, resource)
                if temperature is None or not math.isfinite(float(temperature)):
                    continue
                history = self._temperature_history[resource]
                history.append((observed_at, float(temperature)))
                while history and history[0][0] < cutoff:
                    history.popleft()
                owner = owners.get(resource)
                activity = self._activities.get(owner.job_id) if owner is not None else None
                if activity is None or activity.get('status') != 'running':
                    continue
                previous = activity.get('peak_temperature_c')
                activity['peak_temperature_c'] = max(float(previous or temperature), float(temperature))
            if self._thermal_history_store is not None:
                persistent_sample = self._advance_persistent_temperature_bucket_locked(
                    snapshot,
                    self._utc_now(),
                )
        if persistent_sample is not None:
            self._persist_temperature_sample(*persistent_sample)

    def _advance_persistent_temperature_bucket_locked(
        self,
        snapshot,
        observed_at: datetime,
    ) -> tuple[datetime, float | None, float | None] | None:
        bucket_epoch = int(observed_at.timestamp() // _TEMPERATURE_BUCKET_SECONDS) * _TEMPERATURE_BUCKET_SECONDS
        bucket_at = datetime.fromtimestamp(bucket_epoch, UTC)
        completed = None
        current = self._persistent_temperature_bucket_at
        if current is None:
            self._persistent_temperature_bucket_at = bucket_at
        elif bucket_at > current:
            completed = (
                current,
                self._persistent_temperature_maxima[ComputeResource.LOCAL_GPU],
                self._persistent_temperature_maxima[ComputeResource.REMOTE_GPU],
            )
            self._persistent_temperature_bucket_at = bucket_at
            self._persistent_temperature_maxima = {resource: None for resource in ComputeResource}
        elif bucket_at < current:
            return None
        for resource in ComputeResource:
            temperature = self._temperature(snapshot, resource)
            if temperature is None or not math.isfinite(float(temperature)):
                continue
            previous = self._persistent_temperature_maxima[resource]
            self._persistent_temperature_maxima[resource] = max(
                float(previous if previous is not None else temperature),
                float(temperature),
            )
        if completed is not None and completed[1] is None and completed[2] is None:
            return None
        return completed

    def _flush_persistent_temperature_bucket(self) -> None:
        with self._lock:
            bucket_at = self._persistent_temperature_bucket_at
            local = self._persistent_temperature_maxima[ComputeResource.LOCAL_GPU]
            remote = self._persistent_temperature_maxima[ComputeResource.REMOTE_GPU]
            self._persistent_temperature_bucket_at = None
            self._persistent_temperature_maxima = {resource: None for resource in ComputeResource}
        if bucket_at is not None and (local is not None or remote is not None):
            self._persist_temperature_sample(bucket_at, local, remote)

    def _persist_temperature_sample(
        self,
        observed_at: datetime,
        local_temperature_c: float | None,
        remote_temperature_c: float | None,
    ) -> None:
        store = self._thermal_history_store
        if store is None:
            return
        try:
            store.record_sample(
                observed_at,
                local_temperature_c=local_temperature_c,
                remote_temperature_c=remote_temperature_c,
            )
        except Exception as error:
            with self._lock:
                self._thermal_history_error = str(error)[:500]
        else:
            with self._lock:
                self._thermal_history_error = None

    def _temperature_history_view(self) -> dict[str, object]:
        now = self._monotonic()
        cutoff = now - _TEMPERATURE_HISTORY_SECONDS
        series: dict[str, list[dict[str, float]]] = {}
        with self._lock:
            for resource in ComputeResource:
                history = self._temperature_history[resource]
                while history and history[0][0] < cutoff:
                    history.popleft()
                buckets: dict[int, float] = {}
                for observed_at, temperature in history:
                    age = max(0.0, now - observed_at)
                    bucket = min(
                        int(age // _TEMPERATURE_BUCKET_SECONDS),
                        (_TEMPERATURE_HISTORY_SECONDS // _TEMPERATURE_BUCKET_SECONDS) - 1,
                    )
                    buckets[bucket] = max(buckets.get(bucket, temperature), temperature)
                series[resource.value] = [
                    {
                        'age_seconds': float(bucket * _TEMPERATURE_BUCKET_SECONDS),
                        'max_temperature_c': round(buckets[bucket], 1),
                    }
                    for bucket in sorted(buckets, reverse=True)
                ]
        return {
            'window_seconds': _TEMPERATURE_HISTORY_SECONDS,
            'bucket_seconds': _TEMPERATURE_BUCKET_SECONDS,
            'series': series,
        }

    def public_status(self) -> dict[str, object]:
        owners = self.leases.owners()
        waiters = self.leases.waiters()
        paused = self.leases.paused()
        snapshot = self._thermal_snapshot()
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
                if activity is not None and isinstance(activity.get('llm_metrics'), dict):
                    activity['llm_metrics'] = dict(activity['llm_metrics'])
            fixed_remaining = (
                max(0, math.ceil(fixed_deadline - self._monotonic()))
                if fixed_deadline is not None
                else 0
            )
            hot_threshold = (
                settings.local_cooldown_temperature_c
                if resource is ComputeResource.LOCAL_GPU
                else policy.stop_temperature_c
            )
            state = (
                ComputeResourceState.COOLING.value if thermal_state or fixed_remaining else
                ComputeResourceState.BUSY.value if owner is not None else
                ComputeResourceState.PAUSED.value if resource in paused else
                ComputeResourceState.HOT.value if temperature is not None and temperature >= hot_threshold else
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
        temperature_history = self._temperature_history_view()
        return {
            'temperature_history': temperature_history,
            "settings": self._settings_dict(settings),
            "policy": asdict(policy),
            "machines": machines,
            "recent": recent,
        }

    def thermal_history(self) -> dict[str, object]:
        now = self._utc_now()
        since = now - timedelta(seconds=_PERSISTENT_TEMPERATURE_HISTORY_SECONDS)
        loaded: dict[str, list[dict[str, object]]] = {"samples": [], "events": []}
        store = self._thermal_history_store
        if store is not None:
            try:
                loaded = store.load(since=since, until=now)
            except Exception as error:
                with self._lock:
                    self._thermal_history_error = str(error)[:500]

        samples = list(loaded.get("samples") or [])
        with self._lock:
            bucket_at = self._persistent_temperature_bucket_at
            pending = dict(self._persistent_temperature_maxima)
            history_error = self._thermal_history_error
        if bucket_at is not None and bucket_at >= since:
            sample: dict[str, object] = {"timestamp": self._format_timestamp(bucket_at)}
            for resource in ComputeResource:
                if pending[resource] is not None:
                    sample[resource.value] = round(float(pending[resource]), 1)
            samples.append(sample)

        series: dict[str, list[dict[str, object]]] = {resource.value: [] for resource in ComputeResource}
        points: dict[ComputeResource, dict[str, float]] = {resource: {} for resource in ComputeResource}
        for sample in samples:
            timestamp = sample.get("timestamp")
            if not isinstance(timestamp, str):
                continue
            for resource in ComputeResource:
                temperature = sample.get(resource.value)
                if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                    continue
                points[resource][timestamp] = max(
                    points[resource].get(timestamp, float(temperature)),
                    float(temperature),
                )
        for resource in ComputeResource:
            series[resource.value] = [
                {"timestamp": timestamp, "max_temperature_c": round(temperature, 1)}
                for timestamp, temperature in sorted(points[resource].items())
            ]

        events: dict[str, list[dict[str, object]]] = {resource.value: [] for resource in ComputeResource}
        for value in loaded.get("events") or []:
            resource_value = value.get("resource")
            workload_value = value.get("workload")
            try:
                resource = ComputeResource(resource_value)
                workload = ProductionWorkload(workload_value)
            except (TypeError, ValueError):
                continue
            marker = _THERMAL_EVENT_MARKERS.get(workload)
            if marker is None:
                continue
            event = dict(value)
            event["marker"] = marker
            events[resource.value].append(event)

        return {
            "window_seconds": _PERSISTENT_TEMPERATURE_HISTORY_SECONDS,
            "bucket_seconds": _TEMPERATURE_BUCKET_SECONDS,
            "from": self._format_timestamp(since),
            "to": self._format_timestamp(now),
            "persistent": store is not None,
            "series": series,
            "events": events,
            "error": history_error,
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
        event_id = None
        event_peak = None
        finished_at = self._utc_now()
        with self._lock:
            activity = self._activities.pop(owner_id, None)
            self._llm_token_windows.pop(owner_id, None)
            self._llm_started_at.pop(owner_id, None)
            event_id = self._thermal_event_ids.pop(owner_id, None)
            if activity is None:
                return
            timestamp = self._format_timestamp(finished_at)
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
            event_peak = activity.get("peak_temperature_c")
            self._recent.append(activity)
            self._recent = self._recent[-self._settings.history_limit:]
        if event_id is not None:
            self._finish_thermal_event(event_id, finished_at, status, event_peak)

    def _start_thermal_event(self, owner_id: str, requirement: ResourceRequirement) -> None:
        store = self._thermal_history_store
        if store is None or requirement.workload not in _THERMAL_EVENT_MARKERS:
            return
        event_id = f"thermal-{uuid4().hex}"
        started_at = self._utc_now()
        with self._lock:
            self._thermal_event_ids[owner_id] = event_id
        try:
            store.record_event_start(
                event_id,
                resource=requirement.resource,
                workload=requirement.workload,
                operation=requirement.operation,
                started_at=started_at,
            )
        except Exception as error:
            with self._lock:
                self._thermal_event_ids.pop(owner_id, None)
                self._thermal_history_error = str(error)[:500]
        else:
            with self._lock:
                self._thermal_history_error = None

    def _finish_thermal_event(
        self,
        event_id: str,
        finished_at: datetime,
        status: str,
        peak_temperature_c,
    ) -> None:
        store = self._thermal_history_store
        if store is None:
            return
        peak = (
            float(peak_temperature_c)
            if isinstance(peak_temperature_c, (int, float)) and not isinstance(peak_temperature_c, bool)
            else None
        )
        try:
            store.record_event_finish(
                event_id,
                finished_at=finished_at,
                status=status,
                peak_temperature_c=peak,
            )
        except Exception as error:
            with self._lock:
                self._thermal_history_error = str(error)[:500]
        else:
            with self._lock:
                self._thermal_history_error = None

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
            'local_cooldown_temperature_c': settings.local_cooldown_temperature_c,
            'local_cooldown_seconds': settings.local_cooldown_seconds,
            "thermal": asdict(settings.thermal),
            "remote_video_cooldown_seconds": settings.remote_video_cooldown_seconds,
            "pause_after_failure": settings.pause_after_failure,
            "history_limit": settings.history_limit,
        }

    def _timestamp(self) -> str:
        return self._format_timestamp(self._utc_now())

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _monitored(self, resource: ComputeResource) -> bool:
        policy = self.policy
        return policy.monitor_local if resource is ComputeResource.LOCAL_GPU else policy.monitor_remote

    @staticmethod
    def _temperature(snapshot, resource: ComputeResource) -> float | None:
        return snapshot.local_temperature_c if resource is ComputeResource.LOCAL_GPU else snapshot.remote_temperature_c


__all__ = ["MachineWorkCoordinator", "WorkSchedulerSettingsStore"]
