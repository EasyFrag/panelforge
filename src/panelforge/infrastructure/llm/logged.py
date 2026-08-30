"""Best-effort technical logging around any multimodal gateway."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import logging
from threading import Lock
from time import perf_counter
from uuid import uuid4

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    LlmCallApplicationOutcome,
    LlmCallImage,
    LlmCallLogStore,
    LlmCallRecord,
    LlmCallStatus,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
)


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LlmActiveCall:
    call_id: str
    operation_id: str
    model_id: str


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
        self._application_outcomes: dict[
            str,
            tuple[LlmCallApplicationOutcome, str | None, str | None],
        ] = {}
        self._outcome_lock = Lock()
        self._active_calls: dict[str, LlmActiveCall] = {}
        self._active_lock = Lock()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self._delegate.list_models()

    def active_calls(self) -> tuple[LlmActiveCall, ...]:
        with self._active_lock:
            return tuple(self._active_calls.values())

    def complete(self, request: CompletionRequest) -> CompletionResult:
        call_id = self._id_factory()
        started_at = self._clock()
        started_timer = self._timer()
        self._start_call(call_id, request)
        try:
            try:
                result = self._delegate.complete(request)
            except Exception as error:
                self._append(
                    self._record(
                        request,
                        call_id,
                        started_at,
                        started_timer,
                        status=LlmCallStatus.FAILED,
                        error=error,
                    )
                )
                raise
            result = replace(result, call_id=call_id)
            status = (
                LlmCallStatus.TRUNCATED
                if result.finish_reason == "length"
                else LlmCallStatus.SUCCEEDED
            )
            self._append(
                self._record(
                    request,
                    call_id,
                    started_at,
                    started_timer,
                    status=status,
                    result=result,
                )
            )
            return result
        finally:
            self._finish_call(call_id)

    def stream(
        self,
        request: CompletionRequest,
    ) -> Iterator[CompletionStreamEvent]:
        call_id = self._id_factory()
        started_at = self._clock()
        started_timer = self._timer()
        parts: list[str] = []
        result: CompletionResult | None = None
        status = LlmCallStatus.FAILED
        error: BaseException | None = None
        self._start_call(call_id, request)
        try:
            for event in self._delegate.stream(request):
                # Reasoning events are deliberately pass-through only. The
                # journal stores the model's final answer, never its trace.
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind in {
                    StreamEventKind.COMPLETED,
                    StreamEventKind.TRUNCATED,
                }:
                    result = (
                        replace(event.result, call_id=call_id)
                        if event.result is not None
                        else None
                    )
                    event = replace(event, result=result)
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
            try:
                self._append(
                    self._record(
                        request,
                        call_id,
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
            finally:
                self._finish_call(call_id)

    def _start_call(self, call_id: str, request: CompletionRequest) -> None:
        with self._active_lock:
            self._active_calls[call_id] = LlmActiveCall(
                call_id=call_id,
                operation_id=request.operation_id,
                model_id=request.model_id,
            )

    def _finish_call(self, call_id: str) -> None:
        with self._active_lock:
            self._active_calls.pop(call_id, None)

    def _record(
        self,
        request: CompletionRequest,
        call_id: str,
        started_at: datetime,
        started_timer: float,
        *,
        status: LlmCallStatus,
        result: CompletionResult | None = None,
        response_text: str | None = None,
        error: BaseException | None = None,
    ) -> LlmCallRecord:
        with self._outcome_lock:
            application_outcome = self._application_outcomes.pop(call_id, None)
        return LlmCallRecord(
            call_id=call_id,
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
            application_outcome=(
                application_outcome[0]
                if application_outcome is not None
                else None
            ),
            application_error_type=(
                application_outcome[1]
                if application_outcome is not None
                else None
            ),
            application_error_message=(
                application_outcome[2]
                if application_outcome is not None
                else None
            ),
        )

    def report_application_outcome(
        self,
        call_id: str,
        outcome: LlmCallApplicationOutcome,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if not isinstance(call_id, str) or not call_id.strip():
            raise ValueError("call_id must not be empty")
        if not isinstance(outcome, LlmCallApplicationOutcome):
            raise TypeError("outcome must be an LlmCallApplicationOutcome")
        if outcome is not LlmCallApplicationOutcome.REJECTED and (
            error_type is not None or error_message is not None
        ):
            raise ValueError("application errors require a rejected outcome")
        with self._outcome_lock:
            self._application_outcomes[call_id] = (
                outcome,
                error_type,
                error_message,
            )

    def _append(self, record: LlmCallRecord) -> None:
        try:
            self._store.append(record)
        except Exception:
            _LOGGER.exception("failed to persist LLM call log %s", record.call_id)
