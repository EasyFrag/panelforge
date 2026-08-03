"""Minimal HTTP transport for the ComfyUI API."""

from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast


JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ComfyImageRef:
    """Reference returned by ComfyUI for an uploaded input image."""

    filename: str
    subfolder: str
    folder_type: str

    @property
    def workflow_value(self) -> str:
        """Value expected by a ComfyUI LoadImage node."""
        if self.subfolder:
            return f"{self.subfolder}/{self.filename}"
        return self.filename


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

    def upload_image(
        self,
        content: bytes,
        *,
        filename: str,
        subfolder: str = "",
    ) -> ComfyImageRef:
        """Upload immutable image bytes to ComfyUI's input folder."""
        if not isinstance(content, bytes) or not content:
            raise ValueError("content must be non-empty bytes")
        _validate_filename(filename)
        _validate_subfolder(subfolder)

        boundary = f"PanelForge-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = _build_multipart_body(
            boundary=boundary,
            fields={
                "type": "input",
                "subfolder": subfolder,
                "overwrite": "false",
            },
            filename=filename,
            content_type=content_type,
            content=content,
        )
        request = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        response = self._read_json(request)
        if not isinstance(response, dict):
            raise ValueError("ComfyUI returned an invalid upload response")
        uploaded_filename = response.get("name")
        uploaded_subfolder = response.get("subfolder")
        uploaded_type = response.get("type")
        if not isinstance(uploaded_filename, str) or not uploaded_filename:
            raise ValueError("ComfyUI returned an invalid uploaded image name")
        if not isinstance(uploaded_subfolder, str):
            raise ValueError("ComfyUI returned an invalid uploaded image subfolder")
        _validate_subfolder(uploaded_subfolder)
        if uploaded_type != "input":
            raise ValueError("ComfyUI returned an unexpected uploaded image type")
        return ComfyImageRef(
            filename=uploaded_filename,
            subfolder=uploaded_subfolder,
            folder_type=uploaded_type,
        )

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


def _build_multipart_body(
    *,
    boundary: str,
    fields: Mapping[str, str],
    filename: str,
    content_type: str,
    content: bytes,
) -> bytes:
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            'Content-Disposition: form-data; name="image"; '
            f'filename="{filename}"\r\n'
        ).encode("utf-8")
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body)


def _validate_filename(filename: str) -> None:
    if not isinstance(filename, str) or not filename:
        raise ValueError("filename must not be empty")
    _validate_form_value(filename, "filename")
    if "/" in filename or "\\" in filename:
        raise ValueError("filename must not contain path separators")


def _validate_form_value(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if "\r" in value or "\n" in value:
        raise ValueError(f"{label} must not contain line breaks")
    if '"' in value:
        raise ValueError(f"{label} must not contain double quotes")


def _validate_subfolder(subfolder: str) -> None:
    _validate_form_value(subfolder, "subfolder")
    if not subfolder:
        return
    if "\\" in subfolder or subfolder.startswith("/") or subfolder.endswith("/"):
        raise ValueError("subfolder must be a canonical relative POSIX path")
    if any(part in {"", ".", ".."} for part in subfolder.split("/")):
        raise ValueError("subfolder must be a canonical relative POSIX path")
