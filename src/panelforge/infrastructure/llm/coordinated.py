"""Serialize all LLM calls on the local machine lane."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from panelforge.application import CompletionRequest, CompletionResult, CompletionStreamEvent
from panelforge.domain.production import ComputeResource, ProductionWorkload


class CoordinatedMultimodalGateway:
    def __init__(self, delegate, coordinator) -> None:
        self._delegate = delegate
        self._coordinator = coordinator

    def list_models(self):
        return self._delegate.list_models()

    def complete(self, request: CompletionRequest) -> CompletionResult:
        owner = f"llm-{uuid4().hex}"
        with self._coordinator.lease(
            owner, ComputeResource.LOCAL_GPU, ProductionWorkload.LLM,
            request.operation_id or "LLM",
        ):
            return self._delegate.complete(request)

    def stream(self, request: CompletionRequest) -> Iterator[CompletionStreamEvent]:
        owner = f"llm-{uuid4().hex}"
        with self._coordinator.lease(
            owner, ComputeResource.LOCAL_GPU, ProductionWorkload.LLM,
            request.operation_id or "LLM",
        ):
            yield from self._delegate.stream(request)


__all__ = ["CoordinatedMultimodalGateway"]
