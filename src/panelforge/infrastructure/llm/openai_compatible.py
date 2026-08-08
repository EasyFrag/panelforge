"""Small OpenAI-compatible adapter for local multimodal model servers."""

from __future__ import annotations

import base64
from collections.abc import Iterator

from openai import OpenAI

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)

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
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                if not generating:
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
    marker = "llama-swap loading model:"
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    value_start = marker_index + len(marker)
    value_end = text.find("\n", value_start)
    if value_end < 0:
        return None
    value = text[value_start:value_end].strip()
    return value or None


def _llama_swap_queue_position(text: str) -> str | None:
    marker = "Queue position: #"
    marker_index = text.rfind(marker)
    if marker_index < 0:
        return None
    value_start = marker_index + len(marker)
    digits: list[str] = []
    for character in text[value_start:]:
        if not character.isdecimal():
            break
        digits.append(character)
    return "".join(digits) or None
