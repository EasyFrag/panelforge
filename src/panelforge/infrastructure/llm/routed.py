"""Route namespaced model identifiers across OpenAI-compatible servers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
import logging

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    MultimodalGateway,
)


_LOGGER = logging.getLogger(__name__)
_SEPARATOR = "::"
DEFAULT_LLM_SOURCE = "server"
LOCAL_LLM_SOURCE = "local"


class RoutedMultimodalGateway:
    """Expose several gateways as one catalog without changing old model IDs."""

    def __init__(
        self,
        gateways: Mapping[str, MultimodalGateway],
        *,
        default_source: str = DEFAULT_LLM_SOURCE,
    ) -> None:
        normalized = dict(gateways)
        if not normalized or default_source not in normalized:
            raise ValueError("the default LLM source must have a gateway")
        for source in normalized:
            if (
                not isinstance(source, str)
                or not source.strip()
                or _SEPARATOR in source
            ):
                raise ValueError("LLM source names must be non-empty and unnamespaced")
        self._gateways = normalized
        self._default_source = default_source

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        models: list[ModelDescriptor] = []
        for source, gateway in self._gateways.items():
            try:
                discovered = gateway.list_models()
            except Exception as error:
                _LOGGER.warning(
                    "LLM source %s is unavailable: %s",
                    source,
                    error,
                )
                continue
            for model in discovered:
                raw_id = model.model_id
                models.append(
                    ModelDescriptor(
                        model_id=namespaced_model_id(
                            source,
                            raw_id,
                            default_source=self._default_source,
                        ),
                        source=source,
                        display_name=model.display_name or raw_id,
                    )
                )
        return tuple(models)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        source, routed_request = self._route(request)
        result = self._gateways[source].complete(routed_request)
        return replace(
            result,
            model_id=namespaced_model_id(
                source,
                result.model_id,
                default_source=self._default_source,
            ),
        )

    def stream(
        self,
        request: CompletionRequest,
    ) -> Iterator[CompletionStreamEvent]:
        source, routed_request = self._route(request)
        for event in self._gateways[source].stream(routed_request):
            if event.result is None:
                yield event
                continue
            result = replace(
                event.result,
                model_id=namespaced_model_id(
                    source,
                    event.result.model_id,
                    default_source=self._default_source,
                ),
            )
            yield replace(event, result=result)

    def _route(
        self,
        request: CompletionRequest,
    ) -> tuple[str, CompletionRequest]:
        source, raw_id = split_model_id(
            request.model_id,
            sources=self._gateways,
            default_source=self._default_source,
        )
        return source, replace(request, model_id=raw_id)


def namespaced_model_id(
    source: str,
    model_id: str,
    *,
    default_source: str = DEFAULT_LLM_SOURCE,
) -> str:
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must not be empty")
    return model_id if source == default_source else f"{source}{_SEPARATOR}{model_id}"


def split_model_id(
    model_id: str,
    *,
    sources: Mapping[str, object],
    default_source: str = DEFAULT_LLM_SOURCE,
) -> tuple[str, str]:
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must not be empty")
    source, separator, raw_id = model_id.partition(_SEPARATOR)
    if not separator:
        return default_source, model_id
    if source not in sources:
        raise ValueError(f"unknown LLM source: {source}")
    if not raw_id:
        raise ValueError("namespaced model_id must include a model")
    return source, raw_id
