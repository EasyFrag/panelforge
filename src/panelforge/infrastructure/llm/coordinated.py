"""Serialize all LLM calls on the local machine lane."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    StreamEventKind,
    StreamPhase,
)
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
            self._coordinator.reconcile_llm_tokens(
                owner,
                result.completion_tokens,
                result.reasoning_tokens,
            )
            self._coordinator.report_progress(owner, 1.0, "Réponse LLM terminée")
            return result

    def stream(self, request: CompletionRequest) -> Iterator[CompletionStreamEvent]:
        owner = f"llm-{uuid4().hex}"
        yield CompletionStreamEvent(StreamEventKind.STATUS, StreamPhase.QUEUED,
                                    "Planifié · en attente du LLM")
        with self._coordinator.lease(
            owner, ComputeResource.LOCAL_GPU, ProductionWorkload.LLM,
            request.operation_id or "LLM",
        ):
            self._coordinator.report_stage(owner, "Génération LLM")
            yield CompletionStreamEvent(StreamEventKind.STATUS, StreamPhase.STARTING,
                                        "Démarrage du LLM")
            terminal_was_yielded = False
            try:
                for event in self._delegate.stream(request):
                    if event.kind is StreamEventKind.REASONING and event.text:
                        self._coordinator.report_llm_tokens(owner, 'thinking')
                    elif event.kind is StreamEventKind.DELTA and event.text:
                        self._coordinator.report_llm_tokens(owner, 'writing')
                    self._coordinator.report_progress(
                        owner,
                        event.progress,
                        getattr(event.phase, "value", event.phase) if event.phase else "Génération LLM",
                    )
                    if (
                        event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}
                        and event.result is not None
                    ):
                        self._coordinator.reconcile_llm_tokens(
                            owner,
                            event.result.completion_tokens,
                            event.result.reasoning_tokens,
                        )
                    terminal_was_yielded = event.kind in {
                        StreamEventKind.COMPLETED,
                        StreamEventKind.TRUNCATED,
                    }
                    yield event
            except GeneratorExit:
                # Most browser consumers stop as soon as they receive the terminal
                # event. Closing the Python generator at that suspended yield is a
                # successful end of the call, not a scheduler failure.
                if terminal_was_yielded:
                    return
                raise


__all__ = ["CoordinatedMultimodalGateway"]
