"""Small OpenAI-compatible adapter for local multimodal model servers."""

from __future__ import annotations

import base64
from collections.abc import Iterator
import re

from openai import OpenAI

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)


_LLAMA_SWAP_SEPARATOR = "━━━━━"
_LLAMA_SWAP_MODEL_PREFIX = "llama-swap loading model:"
_LLAMA_SWAP_QUEUE_PREFIX = "Queue position: #"
_LLAMA_SWAP_MODEL_LINE = re.compile(
    rf"{re.escape(_LLAMA_SWAP_MODEL_PREFIX)} ([^\r\n]+)"
)
_LLAMA_SWAP_QUEUE_LINE = re.compile(
    rf"{re.escape(_LLAMA_SWAP_QUEUE_PREFIX)}([0-9]+)"
)
_MAX_OPERATIONAL_LINE = 4096


class OpenAICompatibleGateway:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "panelforge-local",
        timeout: float = 300.0,
        client=None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must not be empty")
        self._client = client or OpenAI(
            base_url=base_url.rstrip("/") + "/",
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        response = self._client.models.list()
        identifiers = sorted({item.id for item in response.data})
        return tuple(ModelDescriptor(model_id=value) for value in identifiers)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if not isinstance(request, CompletionRequest):
            raise TypeError("request must be a CompletionRequest")
        response = self._client.chat.completions.create(
            model=request.model_id,
            messages=_messages(request),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )
        choice = response.choices[0]
        content = choice.message.content
        finish_reason = _finish_reason(getattr(choice, "finish_reason", None))
        if (
            (not isinstance(content, str) or not content.strip())
            and finish_reason != "length"
        ):
            raise ValueError("model returned an empty text response")
        usage = getattr(response, "usage", None)
        return CompletionResult(
            model_id=getattr(response, "model", request.model_id),
            content=content.strip() if isinstance(content, str) else "",
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            finish_reason=finish_reason,
        )

    def stream(
        self,
        request: CompletionRequest,
    ) -> Iterator[CompletionStreamEvent]:
        if not isinstance(request, CompletionRequest):
            raise TypeError("request must be a CompletionRequest")
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.PREPARING,
            text="Préparation ou chargement du modèle…",
        )
        stream = self._client.chat.completions.create(
            model=request.model_id,
            messages=_messages(request),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )
        content_parts: list[str] = []
        generating = False
        model_id = request.model_id
        prompt_tokens = None
        completion_tokens = None
        loading_buffer = ""
        loading_announced = False
        queue_position: str | None = None
        finish_reason: str | None = None
        reasoning_filter = (
            _ReasoningTraceFilter() if request.include_reasoning else None
        )
        for chunk in stream:
            chunk_model = getattr(chunk, "model", None)
            if isinstance(chunk_model, str) and chunk_model:
                model_id = chunk_model
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_tokens = getattr(usage, "prompt_tokens", prompt_tokens)
                completion_tokens = getattr(
                    usage,
                    "completion_tokens",
                    completion_tokens,
                )
            choices = getattr(chunk, "choices", None) or ()
            if not choices:
                continue
            choice = choices[0]
            chunk_finish_reason = _finish_reason(
                getattr(choice, "finish_reason", None)
            )
            if chunk_finish_reason is not None:
                finish_reason = chunk_finish_reason
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            reasoning = _reasoning_text(delta)
            if reasoning and not generating:
                loading_buffer = (loading_buffer + reasoning)[-4096:]
                model_name = _llama_swap_model_name(loading_buffer)
                if model_name is not None and not loading_announced:
                    loading_announced = True
                    yield CompletionStreamEvent(
                        kind=StreamEventKind.STATUS,
                        phase=StreamPhase.LOADING,
                        text=f"Chargement du modèle {model_name}…",
                    )
                if loading_announced:
                    new_queue_position = _llama_swap_queue_position(loading_buffer)
                    if (
                        new_queue_position is not None
                        and new_queue_position != queue_position
                    ):
                        queue_position = new_queue_position
                        yield CompletionStreamEvent(
                            kind=StreamEventKind.STATUS,
                            phase=StreamPhase.LOADING,
                            text=f"Position dans la file : {queue_position}",
                        )
            if reasoning and reasoning_filter is not None:
                visible_reasoning = reasoning_filter.feed(reasoning)
                if visible_reasoning:
                    yield CompletionStreamEvent(
                        kind=StreamEventKind.REASONING,
                        phase=StreamPhase.GENERATING,
                        text=visible_reasoning,
                    )
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                if not generating:
                    if reasoning_filter is not None:
                        visible_reasoning = reasoning_filter.finish()
                        if visible_reasoning:
                            yield CompletionStreamEvent(
                                kind=StreamEventKind.REASONING,
                                phase=StreamPhase.GENERATING,
                                text=visible_reasoning,
                            )
                    generating = True
                    yield CompletionStreamEvent(
                        kind=StreamEventKind.STATUS,
                        phase=StreamPhase.GENERATING,
                        text="Génération…",
                    )
                content_parts.append(text)
                yield CompletionStreamEvent(
                    kind=StreamEventKind.DELTA,
                    phase=StreamPhase.GENERATING,
                    text=text,
                )

        if reasoning_filter is not None:
            visible_reasoning = reasoning_filter.finish()
            if visible_reasoning:
                yield CompletionStreamEvent(
                    kind=StreamEventKind.REASONING,
                    phase=StreamPhase.GENERATING,
                    text=visible_reasoning,
                )

        content = "".join(content_parts).strip()
        if not content and finish_reason != "length":
            raise ValueError("model returned an empty text response")
        result = CompletionResult(
            model_id=model_id,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
        )
        if finish_reason == "length":
            yield CompletionStreamEvent(
                kind=StreamEventKind.TRUNCATED,
                phase=StreamPhase.TRUNCATED,
                text=content,
                result=result,
            )
            return
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=content,
            progress=1.0,
            result=result,
        )


def _messages(request: CompletionRequest) -> list[dict[str, object]]:
    user_content: str | list[dict[str, object]]
    if request.images:
        parts: list[dict[str, object]] = [
            {"type": "text", "text": request.user_prompt}
        ]
        for image in request.images:
            encoded = base64.b64encode(image.content).decode("ascii")
            parts.extend(
                (
                    {"type": "text", "text": f"REFERENCE: {image.label}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image.media_type};base64,{encoded}"
                        },
                    },
                )
            )
        user_content = parts
    else:
        user_content = request.user_prompt
    return [
        {"role": "system", "content": request.system_prompt},
        {"role": "user", "content": user_content},
    ]


def _reasoning_text(delta) -> str | None:
    for name in ("reasoning_content", "reasoning"):
        value = getattr(delta, name, None)
        if isinstance(value, str) and value:
            return value
    extra = getattr(delta, "model_extra", None)
    if isinstance(extra, dict):
        for name in ("reasoning_content", "reasoning"):
            value = extra.get(name)
            if isinstance(value, str) and value:
                return value
    return None


def _finish_reason(value) -> str | None:
    if isinstance(value, str) and value:
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str) and enum_value:
        return enum_value
    return None


def _llama_swap_model_name(text: str) -> str | None:
    for line in text.splitlines(keepends=True):
        if not line.endswith(("\n", "\r")):
            continue
        match = _LLAMA_SWAP_MODEL_LINE.fullmatch(line.rstrip("\r\n"))
        if match is not None:
            value = match.group(1)
            return value if value == value.strip() else None
    return None


def _llama_swap_queue_position(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        match = _LLAMA_SWAP_QUEUE_LINE.fullmatch(line.rstrip("\r"))
        if match is not None:
            return match.group(1)
    return None


class _ReasoningTraceFilter:
    """Remove only a verified leading llama.swap operational preamble.

    llama.swap uses the provider reasoning field for its loading separator,
    model name and queue position. Those records are transport diagnostics, not
    model reasoning. Filtering stops permanently at the first non-operational
    text so a later model sentence that merely discusses llama.swap is kept.
    """

    def __init__(self) -> None:
        self._pending = ""
        self._filtering_preamble = True

    def feed(self, text: str) -> str:
        if not self._filtering_preamble:
            return text
        self._pending += text
        return self._drain(final=False)

    def finish(self) -> str:
        if not self._filtering_preamble:
            return ""
        visible = self._drain(final=True)
        self._filtering_preamble = False
        return visible

    def _drain(self, *, final: bool) -> str:
        while self._pending:
            line_end = self._pending.find("\n")
            if line_end >= 0:
                line = self._pending[:line_end].rstrip("\r")
                if _is_llama_swap_operational_line(line):
                    self._pending = self._pending[line_end + 1 :]
                    continue
                return self._reveal()

            if _is_possible_llama_swap_operational_prefix(self._pending):
                if not final and len(self._pending) <= _MAX_OPERATIONAL_LINE:
                    return ""
                if final and _is_llama_swap_operational_line(self._pending):
                    self._pending = ""
                    return ""
            return self._reveal()
        return ""

    def _reveal(self) -> str:
        visible = self._pending
        self._pending = ""
        self._filtering_preamble = False
        return visible


def _is_llama_swap_operational_line(text: str) -> bool:
    if text == _LLAMA_SWAP_SEPARATOR:
        return True
    model = _LLAMA_SWAP_MODEL_LINE.fullmatch(text)
    if model is not None:
        value = model.group(1)
        return value == value.strip()
    return _LLAMA_SWAP_QUEUE_LINE.fullmatch(text) is not None


def _is_possible_llama_swap_operational_prefix(text: str) -> bool:
    if _LLAMA_SWAP_SEPARATOR.startswith(text):
        return True
    if _LLAMA_SWAP_MODEL_PREFIX.startswith(text):
        return True
    if text.startswith(_LLAMA_SWAP_MODEL_PREFIX):
        return "\r" not in text and "\n" not in text
    if _LLAMA_SWAP_QUEUE_PREFIX.startswith(text):
        return True
    if text.startswith(_LLAMA_SWAP_QUEUE_PREFIX):
        return text.removeprefix(_LLAMA_SWAP_QUEUE_PREFIX).isdecimal()
    return False
