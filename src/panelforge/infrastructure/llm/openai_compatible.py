"""Small OpenAI-compatible adapter for local multimodal model servers."""

from __future__ import annotations

import base64

from openai import OpenAI

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    ModelDescriptor,
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

        response = self._client.chat.completions.create(
            model=request.model_id,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("model returned an empty text response")
        usage = getattr(response, "usage", None)
        return CompletionResult(
            model_id=getattr(response, "model", request.model_id),
            content=content.strip(),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )
