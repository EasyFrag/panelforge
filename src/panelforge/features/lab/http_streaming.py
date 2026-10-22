"""Http streaming for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Literal
from fastapi.responses import StreamingResponse
import json


def _encode_sse(event: str, payload: dict[str, object]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"
    )


def stream_response(
    events: Iterator[Any],
    *,
    serialize: Callable[[Any], Mapping[str, object]],
    entity: Literal["project", "source", "session", "composition"] = "project",
    fields: tuple[str, ...] = ("error",),
    document_stage: bool = False,
) -> StreamingResponse:
    """Stream the existing workshop payloads without buffering or coercion.

    KREA2/H3/Social include ``error``; Edit omits it. Prompt streams instead
    include finish_reason/max_tokens, and composition adds document_stage.
    A related entity is omitted until the service supplies it.
    """
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                }
                payload.update((name, getattr(event, name)) for name in fields)
                if document_stage:
                    payload["document_stage"] = event.document_stage.value if event.document_stage is not None else None
                related = getattr(event, entity)
                if related is not None:
                    payload[entity] = serialize(related)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse("error", {"kind": "error", "phase": "failed", "message": str(error)})

    return StreamingResponse(
        encoded_events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
