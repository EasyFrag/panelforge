"""Best-effort technical logging around any multimodal gateway."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
import hashlib
import logging
from time import perf_counter
from uuid import uuid4

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    LlmCallImage,
    LlmCallLogStore,
    LlmCallRecord,
    LlmCallStatus,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
)


_LOGGER = logging.getLogger(__name__)


class LoggedMultimodalGateway:
    def __init__(
        self,
        delegate: MultimodalGateway,
        store: LlmCallLogStore,
        *,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._delegate = delegate
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timer = timer or perf_counter
        self._id_factory = id_factory or (lambda: f"llm-{uuid4().hex}")

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self._delegate.list_models()

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started_at = self._clock()
        started_timer = self._timer()
        try:
            result = self._delegate.complete(request)
        except Exception as error:
            self._append(
                self._record(
                    request,
                    started_at,
                    started_timer,
                    status=LlmCallStatus.FAILED,
                    error=error,
                )
            )
            raise
        status = (
            LlmCallStatus.TRUNCATED
            if result.finish_reason == "length"
            else LlmCallStatus.SUCCEEDED
        )
        self._append(
            self._record(
                request,
                started_at,
                started_timer,
                status=status,
                result=result,
            )
        )
        return result

    def stream(
        self,
        request: CompletionRequest,
    ) -> Iterator[CompletionStreamEvent]:
        started_at = self._clock()
        started_timer = self._timer()
        parts: list[str] = []
        result: CompletionResult | None = None
        status = LlmCallStatus.FAILED
        error: BaseException | None = None
        try:
            for event in self._delegate.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind in {
                    StreamEventKind.COMPLETED,
                    StreamEventKind.TRUNCATED,
                }:
                    result = event.result
                yield event
            if result is None:
                error = RuntimeError("model stream ended without a terminal result")
            elif result.finish_reason == "length":
                status = LlmCallStatus.TRUNCATED
            else:
                status = LlmCallStatus.SUCCEEDED
        except GeneratorExit as caught:
            if result is None:
                status = LlmCallStatus.CANCELLED
                error = caught
            elif result.finish_reason == "length":
                status = LlmCallStatus.TRUNCATED
            else:
                status = LlmCallStatus.SUCCEEDED
            raise
        except Exception as caught:
            status = LlmCallStatus.FAILED
            error = caught
            raise
        finally:
            self._append(
                self._record(
                    request,
                    started_at,
                    started_timer,
                    status=status,
                    result=result,
                    response_text=(
                        result.content if result is not None else "".join(parts)
                    ),
                    error=error,
                )
            )

    def _record(
        self,
        request: CompletionRequest,
        started_at: datetime,
        started_timer: float,
        *,
        status: LlmCallStatus,
        result: CompletionResult | None = None,
        response_text: str | None = None,
        error: BaseException | None = None,
    ) -> LlmCallRecord:
        return LlmCallRecord(
            call_id=self._id_factory(),
            operation_id=request.operation_id,
            requested_model_id=request.model_id,
            actual_model_id=result.model_id if result is not None else None,
            started_at=started_at,
            duration_ms=max(0, round((self._timer() - started_timer) * 1000)),
            status=status,
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            images=tuple(
                LlmCallImage(
                    label=image.label,
                    media_type=image.media_type,
                    byte_size=len(image.content),
                    sha256=hashlib.sha256(image.content).hexdigest(),
                )
                for image in request.images
            ),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_text=(
                response_text
                if response_text is not None
                else (result.content if result is not None else "")
            ),
            finish_reason=result.finish_reason if result is not None else None,
            prompt_tokens=result.prompt_tokens if result is not None else None,
            completion_tokens=(
                result.completion_tokens if result is not None else None
            ),
            error_type=type(error).__name__ if error is not None else None,
            error_message=(str(error).strip() or None) if error is not None else None,
        )

    def _append(self, record: LlmCallRecord) -> None:
        try:
            self._store.append(record)
        except Exception:
            _LOGGER.exception("failed to persist LLM call log %s", record.call_id)
