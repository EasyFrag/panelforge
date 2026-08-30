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


class ResourceLeaseManager:
    """One FIFO, non-preemptive execution slot per physical GPU."""

    def __init__(self, *, wait_interval: float = 0.2) -> None:
        if wait_interval <= 0:
            raise ValueError("wait_interval must be positive")
        self._condition = Condition(RLock())
        self._owners: dict[ComputeResource, ResourceOwner] = {}
        self._waiters: dict[ComputeResource, list[object]] = {
            resource: [] for resource in ComputeResource
        }
        self._wait_interval = wait_interval

    def owners(self) -> dict[ComputeResource, ResourceOwner]:
        with self._condition:
            return dict(self._owners)

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
        token = object()
        resource = requirement.resource
        announced = False
        acquired = False
        with self._condition:
            self._waiters[resource].append(token)
            try:
                while (
                    resource in self._owners
                    or self._waiters[resource][0] is not token
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
                self._owners[resource] = ResourceOwner(job_id, requirement)
                acquired = True
            except BaseException:
                if token in self._waiters[resource]:
                    self._waiters[resource].remove(token)
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
    if separator and source in {"local", "vllm"}:
        return ComputeResource.LOCAL_GPU
    return server_resource


__all__ = [
    "ResourceLeaseManager",
    "ResourceOwner",
    "ResourceRequirement",
    "ResourceWaitCancelled",
    "llm_compute_resource",
]
