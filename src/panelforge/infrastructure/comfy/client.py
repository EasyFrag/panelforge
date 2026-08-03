"""Minimal HTTP transport for the ComfyUI API."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any, cast


JsonObject = dict[str, Any]


class ComfyHttpClient:
    """Send workflows to ComfyUI and retrieve their raw outputs."""

    def __init__(
        self,
        base_url: str,
        *,
        client_id: str,
        timeout: float = 30.0,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must not be empty")
        if not client_id:
            raise ValueError("client_id must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.base_url = normalized_base_url
        self.client_id = client_id
        self.timeout = timeout

    def submit_workflow(self, workflow: Mapping[str, Any]) -> str:
        """Queue a workflow and return the ComfyUI prompt identifier."""
        body = json.dumps(
            {
                "prompt": dict(workflow),
                "client_id": self.client_id,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        response = self._read_json(request)
        prompt_id = response["prompt_id"]
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ValueError("ComfyUI returned an invalid prompt_id")
        return prompt_id

    def get_history(self, prompt_id: str) -> JsonObject:
        """Return the raw history payload for one queued workflow."""
        encoded_prompt_id = urllib.parse.quote(prompt_id, safe="")
        request = urllib.request.Request(
            f"{self.base_url}/history/{encoded_prompt_id}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        return self._read_json(request)

    def download_output(
        self,
        *,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes:
        """Download one output referenced by a ComfyUI history payload."""
        query = urllib.parse.urlencode(
            {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}/view?{query}",
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _read_json(self, request: urllib.request.Request) -> JsonObject:
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return cast(JsonObject, json.load(response))
