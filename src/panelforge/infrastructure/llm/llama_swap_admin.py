"""Minimal administrative client for llama.swap."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class LlamaSwapAdminClient:
    """Unload model processes without exposing llama.swap to the browser."""

    def __init__(
        self,
        openai_base_url: str,
        *,
        api_key: str = "",
        timeout: float = 30.0,
        opener=None,
    ) -> None:
        self.base_url = _llama_swap_base_url(openai_base_url)
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def unload_all(self) -> None:
        headers = self._headers()
        request = urllib.request.Request(
            f"{self.base_url}/api/models/unload",
            data=b"",
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                response.read(1024 * 1024)
        except urllib.error.URLError as error:
            raise ConnectionError(f"llama.swap is unreachable: {error.reason}") from error
        if not 200 <= status < 300:
            raise RuntimeError(f"llama.swap returned HTTP {status}")

    def running_models(self) -> tuple[str, ...]:
        """Return the model identifiers currently loaded by llama.swap."""
        request = urllib.request.Request(
            f"{self.base_url}/running",
            headers=self._headers(),
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read(1024 * 1024)
        except urllib.error.URLError as error:
            raise ConnectionError(f"llama.swap is unreachable: {error.reason}") from error
        if not 200 <= status < 300:
            raise RuntimeError(f"llama.swap returned HTTP {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("llama.swap returned invalid JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("running"), list):
            raise ValueError("llama.swap returned an invalid running-model list")
        identifiers: list[str] = []
        for entry in payload["running"]:
            if isinstance(entry, str):
                identifier = entry
            elif isinstance(entry, dict):
                identifier = next(
                    (
                        entry.get(key)
                        for key in ("model", "model_id", "id")
                        if isinstance(entry.get(key), str)
                    ),
                    None,
                )
            else:
                identifier = None
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("llama.swap returned an invalid running model")
            if identifier not in identifiers:
                identifiers.append(identifier)
        return tuple(identifiers)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _llama_swap_base_url(openai_base_url: str) -> str:
    if not isinstance(openai_base_url, str) or not openai_base_url.strip():
        raise ValueError("openai_base_url must not be empty")
    parsed = urllib.parse.urlsplit(openai_base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("openai_base_url must be an HTTP(S) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("openai_base_url must not contain a query or fragment")
    path = parsed.path.rstrip("/")
    if path == "/v1":
        path = ""
    elif path.endswith("/v1"):
        path = path[:-3]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
