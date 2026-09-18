"""Independent capacity lanes for automated production workloads."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Condition, RLock
from typing import Protocol

from panelforge.domain.production import ComputeResource, ProductionWorkload


class ResourceWaitCancelled(RuntimeError):
    """Raised when a queued lease is cancelled before acquisition."""


@dataclass(frozen=True, slots=True)
class ResourceRequirement:
    resource: ComputeResource
    workload: ProductionWorkload
    operation: str

    def __post_init__(self) -> None:
        if not isinstance(self.resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if not isinstance(self.workload, ProductionWorkload):
            raise TypeError("workload must be a ProductionWorkload")
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("operation must not be empty")


@dataclass(frozen=True, slots=True)
class ResourceOwner:
    job_id: str
    requirement: ResourceRequirement


@dataclass(slots=True)
class _ResourceWaiter:
    token: object
    owner: ResourceOwner
    claimed: bool = False


class ResourceLeaseManager:
    """One FIFO, non-preemptive execution slot per physical GPU."""

    def __init__(self, *, wait_interval: float = 0.2) -> None:
        if wait_interval <= 0:
            raise ValueError("wait_interval must be positive")
        self._condition = Condition(RLock())
        self._owners: dict[ComputeResource, ResourceOwner] = {}
        self._waiters: dict[ComputeResource, list[_ResourceWaiter]] = {
            resource: [] for resource in ComputeResource
        }
        self._paused: set[ComputeResource] = set()
        self._wait_interval = wait_interval

    def owners(self) -> dict[ComputeResource, ResourceOwner]:
        with self._condition:
            return dict(self._owners)

    def waiters(self) -> dict[ComputeResource, tuple[ResourceOwner, ...]]:
        with self._condition:
            return {
                resource: tuple(waiter.owner for waiter in values)
                for resource, values in self._waiters.items()
            }

    def paused(self) -> frozenset[ComputeResource]:
        with self._condition:
            return frozenset(self._paused)

    def set_paused(self, resource: ComputeResource, paused: bool) -> None:
        if not isinstance(resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if not isinstance(paused, bool):
            raise TypeError("paused must be a boolean")
        with self._condition:
            if paused:
                self._paused.add(resource)
            else:
                self._paused.discard(resource)
            self._condition.notify_all()

    def reserve(self, job_id: str, requirement: ResourceRequirement) -> None:
        """Place a durable in-process ticket in the lane before its worker starts."""
        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("job_id must not be empty")
        if not isinstance(requirement, ResourceRequirement):
            raise TypeError("requirement must be a ResourceRequirement")
        with self._condition:
            current = next(
                (owner for owner in self._owners.values() if owner.job_id == job_id),
                None,
            )
            if current is not None:
                if current.requirement != requirement:
                    raise ValueError("job_id already uses another resource requirement")
                return
            existing = next(
                (
                    waiter
                    for waiters in self._waiters.values()
                    for waiter in waiters
                    if waiter.owner.job_id == job_id
                ),
                None,
            )
            if existing is not None:
                if existing.owner.requirement != requirement:
                    raise ValueError("job_id already uses another resource requirement")
                return
            self._waiters[requirement.resource].append(
                _ResourceWaiter(object(), ResourceOwner(job_id, requirement))
            )
            self._condition.notify_all()

    def cancel_reservation(self, job_id: str) -> bool:
        """Remove a ticket that has not yet entered ``lease``."""
        with self._condition:
            for waiters in self._waiters.values():
                for waiter in tuple(waiters):
                    if waiter.owner.job_id == job_id and not waiter.claimed:
                        waiters.remove(waiter)
                        self._condition.notify_all()
                        return True
        return False

    @contextmanager
    def lease(
        self,
        job_id: str,
        requirement: ResourceRequirement,
        *,
        cancelled: Callable[[], bool],
        on_wait: Callable[[], None] | None = None,
        on_acquired: Callable[[], None] | None = None,
    ) -> Iterator[None]:
        resource = requirement.resource
        announced = False
        acquired = False
        with self._condition:
            waiter = next(
                (
                    value
                    for values in self._waiters.values()
                    for value in values
                    if value.owner.job_id == job_id
                ),
                None,
            )
            if waiter is not None:
                if waiter.owner.requirement != requirement:
                    raise ValueError("job_id already uses another resource requirement")
                if waiter.claimed:
                    raise ValueError("job_id is already waiting for a resource")
                waiter.claimed = True
            else:
                waiter = _ResourceWaiter(
                    object(),
                    ResourceOwner(job_id, requirement),
                    claimed=True,
                )
                self._waiters[resource].append(waiter)
            try:
                while (
                    resource in self._owners
                    or resource in self._paused
                    or self._waiters[resource][0].token is not waiter.token
                ):
                    if cancelled():
                        raise ResourceWaitCancelled()
                    if not announced and on_wait is not None:
                        on_wait()
                        announced = True
                    self._condition.wait(self._wait_interval)
                if cancelled():
                    raise ResourceWaitCancelled()
                self._waiters[resource].pop(0)
                self._owners[resource] = waiter.owner
                acquired = True
            except BaseException:
                if waiter in self._waiters[resource]:
                    self._waiters[resource].remove(waiter)
                self._condition.notify_all()
                raise
        try:
            if on_acquired is not None:
                on_acquired()
            yield
        finally:
            if acquired:
                with self._condition:
                    owner = self._owners.get(resource)
                    if owner is not None and owner.job_id == job_id:
                        del self._owners[resource]
                    self._condition.notify_all()


def llm_compute_resource(
    model_id: str,
    *,
    server_resource: ComputeResource = ComputeResource.REMOTE_GPU,
) -> ComputeResource:
    """Map routed model IDs to the GPU that physically serves the request."""

    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must not be empty")
    source, separator, _ = model_id.partition("::")
    if separator and source == "local":
        return ComputeResource.LOCAL_GPU
    return server_resource


__all__ = [
    "ResourceLeaseManager",
    "ResourceOwner",
    "ResourceRequirement",
    "ResourceWaitCancelled",
    "llm_compute_resource",
]
