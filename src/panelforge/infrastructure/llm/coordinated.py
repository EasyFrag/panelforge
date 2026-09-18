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
            self._coordinator.report_stage(owner, "Génération LLM")
            result = self._delegate.complete(request)
            self._coordinator.report_progress(owner, 1.0, "Réponse LLM terminée")
            return result

    def stream(self, request: CompletionRequest) -> Iterator[CompletionStreamEvent]:
        owner = f"llm-{uuid4().hex}"
        with self._coordinator.lease(
            owner, ComputeResource.LOCAL_GPU, ProductionWorkload.LLM,
            request.operation_id or "LLM",
        ):
            self._coordinator.report_stage(owner, "Génération LLM")
            for event in self._delegate.stream(request):
                self._coordinator.report_progress(
                    owner,
                    event.progress,
                    getattr(event.phase, "value", event.phase) if event.phase else "Génération LLM",
                )
                yield event


__all__ = ["CoordinatedMultimodalGateway"]
