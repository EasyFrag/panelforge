"""Minimal HTTP transport for the ComfyUI API."""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
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


class ComfyPromptPhase(StrEnum):
    """State observable through ComfyUI queue and history APIs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class ComfyCancelAction(StrEnum):
    """Server-side action (or no-op) chosen for cancellation."""

    CANCEL_JOB = "cancel_job"
    DELETE_PENDING = "delete_pending"
    INTERRUPT_RUNNING = "interrupt_running"
    ALREADY_FINISHED = "already_finished"
    NOT_FOUND = "not_found"


class ComfyCancellationError(RuntimeError):
    """Raised when PanelForge cannot prove it owns the target ComfyUI job."""


class ComfyBusyError(RuntimeError):
    """Raised when a destructive cleanup is unsafe while jobs are queued."""


@dataclass(frozen=True, slots=True)
class ComfyDeviceStats:
    """Stable GPU memory counters exposed by ComfyUI ``/system_stats``."""

    name: str
    device_type: str
    index: int
    vram_total: int
    vram_free: int
    torch_vram_total: int | None = None
    torch_vram_free: int | None = None


@dataclass(frozen=True, slots=True)
class ComfySystemStats:
    """Small read-only projection of ComfyUI runtime statistics."""

    comfyui_version: str | None
    devices: tuple[ComfyDeviceStats, ...]


@dataclass(frozen=True, slots=True)
class ComfyQueueEntry:
    """Relevant, stable fields extracted from ComfyUI's queue tuple."""

    prompt_id: str
    phase: ComfyPromptPhase
    queue_number: int | float | None
    client_id: str | None


@dataclass(frozen=True, slots=True)
class ComfyQueueSnapshot:
    """One atomic observation of the running and pending queues."""

    running: tuple[ComfyQueueEntry, ...]
    pending: tuple[ComfyQueueEntry, ...]

    def find(self, prompt_id: str) -> ComfyQueueEntry | None:
        for entry in (*self.running, *self.pending):
            if entry.prompt_id == prompt_id:
                return entry
        return None


@dataclass(frozen=True, slots=True)
class ComfyPromptStatus:
    """Normalized prompt status suitable for polling and persistence."""

    prompt_id: str
    phase: ComfyPromptPhase
    queue_number: int | float | None = None
    status_text: str | None = None


@dataclass(frozen=True, slots=True)
class ComfyCancellationResult:
    """Outcome of a safe, prompt-scoped cancellation request."""

    prompt_id: str
    action: ComfyCancelAction


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
        self._owned_prompt_ids: set[str] = set()
        self._ownership_lock = Lock()

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
        with self._ownership_lock:
            self._owned_prompt_ids.add(prompt_id)
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
        _validate_prompt_id(prompt_id)
        encoded_prompt_id = urllib.parse.quote(prompt_id, safe="")
        request = urllib.request.Request(
            f"{self.base_url}/history/{encoded_prompt_id}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        return self._read_json(request)

    def list_unet_models(self) -> tuple[str, ...]:
        """Return the diffusion checkpoints exposed by ComfyUI's UNET loader.

        ``/object_info/UNETLoader`` is the source closest to the workflow node
        and therefore remains the preferred contract. Recent ComfyUI builds
        also expose the underlying model folder through
        ``/models/diffusion_models``; that route is used as a compatibility
        fallback when the node description is unavailable or malformed.
        Network and unexpected HTTP failures remain visible to callers.
        """
        request = urllib.request.Request(
            f"{self.base_url}/object_info/UNETLoader",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            return _parse_unet_loader_models(self._read_json(request))
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 405}:
                raise
        except (KeyError, TypeError, ValueError):
            pass

        fallback = urllib.request.Request(
            f"{self.base_url}/models/diffusion_models",
            headers={"Accept": "application/json"},
            method="GET",
        )
        return _parse_model_list(self._read_json(fallback))

    def list_lora_models(self) -> tuple[str, ...]:
        """Return the LoRA paths exposed by ComfyUI's model inventory."""
        request = urllib.request.Request(
            f"{self.base_url}/models/loras",
            headers={"Accept": "application/json"},
            method="GET",
        )
        return _parse_model_list(self._read_json(request))

    def get_queue(self) -> ComfyQueueSnapshot:
        """Return a normalized snapshot of ComfyUI's execution queue."""
        request = urllib.request.Request(
            f"{self.base_url}/queue",
            headers={"Accept": "application/json"},
            method="GET",
        )
        response = self._read_json(request)
        if not isinstance(response, Mapping):
            raise ValueError("ComfyUI returned an invalid queue response")
        return ComfyQueueSnapshot(
            running=_parse_queue_entries(
                response.get("queue_running"),
                phase=ComfyPromptPhase.RUNNING,
            ),
            pending=_parse_queue_entries(
                response.get("queue_pending"),
                phase=ComfyPromptPhase.PENDING,
            ),
        )

    def get_system_stats(self) -> ComfySystemStats:
        """Return GPU memory counters without exposing ComfyUI's raw payload."""
        request = urllib.request.Request(
            f"{self.base_url}/system_stats",
            headers={"Accept": "application/json"},
            method="GET",
        )
        response = self._read_json(request)
        if not isinstance(response, Mapping):
            raise ValueError("ComfyUI returned an invalid system_stats response")
        system = response.get("system")
        version = system.get("comfyui_version") if isinstance(system, Mapping) else None
        if version is not None and not isinstance(version, str):
            raise ValueError("ComfyUI returned an invalid version")
        raw_devices = response.get("devices")
        if not isinstance(raw_devices, Sequence) or isinstance(raw_devices, (str, bytes)):
            raise ValueError("ComfyUI returned invalid device statistics")
        devices = tuple(_parse_device_stats(device) for device in raw_devices)
        return ComfySystemStats(comfyui_version=version, devices=devices)

    def free_vram(self) -> None:
        """Unload ComfyUI models and caches only when its queue is idle."""
        snapshot = self.get_queue()
        if snapshot.running or snapshot.pending:
            raise ComfyBusyError(
                "ComfyUI exécute ou attend encore un rendu ; nettoyage refusé."
            )
        self._post_json_without_response(
            "/free",
            {"unload_models": True, "free_memory": True},
        )

    def get_prompt_status(self, prompt_id: str) -> ComfyPromptStatus:
        """Resolve queue state first, then terminal state from history."""
        _validate_prompt_id(prompt_id)
        queued = self.get_queue().find(prompt_id)
        if queued is not None:
            return ComfyPromptStatus(
                prompt_id=prompt_id,
                phase=queued.phase,
                queue_number=queued.queue_number,
            )

        history = self.get_history(prompt_id)
        record = history.get(prompt_id)
        if not isinstance(record, Mapping):
            return ComfyPromptStatus(prompt_id, ComfyPromptPhase.UNKNOWN)
        phase, status_text = _history_phase(record)
        return ComfyPromptStatus(
            prompt_id=prompt_id,
            phase=phase,
            status_text=status_text,
        )

    def cancel_job(self, prompt_id: str) -> ComfyCancellationResult:
        """Cancel one exact ComfyUI job identifier.

        Current ComfyUI builds get the targeted, idempotent Jobs API. A legacy
        queue/delete or interrupt fallback is used only when that route itself
        is unavailable (HTTP 404/405). The legacy running fallback is deliberately
        conservative because old ``/interrupt`` implementations are global. The
        application must obtain ``prompt_id`` from its own persisted run rather
        than accepting an arbitrary client-supplied identifier.
        """
        _validate_prompt_id(prompt_id)
        encoded_prompt_id = urllib.parse.quote(prompt_id, safe="")
        try:
            response = self._post_json(
                f"/api/jobs/{encoded_prompt_id}/cancel",
                {},
            )
            cancelled = response.get("cancelled")
            if cancelled is True:
                action = ComfyCancelAction.CANCEL_JOB
            elif cancelled is False:
                history = self.get_history(prompt_id)
                if isinstance(history.get(prompt_id), Mapping):
                    action = ComfyCancelAction.ALREADY_FINISHED
                else:
                    action = ComfyCancelAction.NOT_FOUND
            else:
                raise ValueError("ComfyUI returned an invalid job cancellation response")
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 405}:
                raise
            action = self._cancel_prompt_legacy(prompt_id)

        return ComfyCancellationResult(prompt_id=prompt_id, action=action)

    def cancel_prompt(self, prompt_id: str) -> ComfyCancellationResult:
        """Backward-compatible name for :meth:`cancel_job`."""
        return self.cancel_job(prompt_id)

    def cancel_execution(self, prompt_id: str) -> ComfyCancellationResult:
        """Application-gateway facade for idempotent execution cancellation."""
        result = self.cancel_job(prompt_id)
        if result.action == ComfyCancelAction.NOT_FOUND:
            raise ValueError(f"ComfyUI job {prompt_id!r} was not found")
        return result

    @property
    def websocket_url(self) -> str:
        """Upstream ComfyUI WebSocket URL for live progress and previews."""
        return build_websocket_url(self.base_url, client_id=self.client_id)

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

    def _post_json_without_response(
        self,
        path: str,
        payload: Mapping[str, Any],
    ) -> None:
        body = json.dumps(dict(payload)).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()

    def _post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
    ) -> JsonObject:
        body = json.dumps(dict(payload)).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self._read_json(request)
        if not isinstance(response, Mapping):
            raise ValueError("ComfyUI returned a non-object JSON response")
        return dict(response)

    def _require_owned(self, entry: ComfyQueueEntry) -> None:
        if entry.client_id is not None:
            owned = entry.client_id == self.client_id
        else:
            with self._ownership_lock:
                owned = entry.prompt_id in self._owned_prompt_ids
        if not owned:
            raise ComfyCancellationError(
                "Refusing to cancel a ComfyUI prompt not owned by this client"
            )

    def _cancel_prompt_legacy(self, prompt_id: str) -> ComfyCancelAction:
        snapshot = self.get_queue()
        entry = snapshot.find(prompt_id)
        if entry is None:
            history = self.get_history(prompt_id)
            if isinstance(history.get(prompt_id), Mapping):
                return ComfyCancelAction.ALREADY_FINISHED
            return ComfyCancelAction.NOT_FOUND

        self._require_owned(entry)
        if entry.phase == ComfyPromptPhase.PENDING:
            self._post_json_without_response("/queue", {"delete": [prompt_id]})
            return ComfyCancelAction.DELETE_PENDING

        # Re-read immediately before a potentially global legacy interrupt. This
        # also refuses multi-runner configurations where another job could be hit.
        latest = self.get_queue()
        current = latest.find(prompt_id)
        if (
            current is None
            or current.phase != ComfyPromptPhase.RUNNING
            or len(latest.running) != 1
        ):
            history = self.get_history(prompt_id)
            if isinstance(history.get(prompt_id), Mapping):
                return ComfyCancelAction.ALREADY_FINISHED
            raise ComfyCancellationError(
                "Refusing a legacy global interrupt because the target is no longer "
                "the sole running ComfyUI prompt"
            )
        self._require_owned(current)
        self._post_json_without_response("/interrupt", {"prompt_id": prompt_id})
        return ComfyCancelAction.INTERRUPT_RUNNING


def _parse_queue_entries(
    raw_entries: Any,
    *,
    phase: ComfyPromptPhase,
) -> tuple[ComfyQueueEntry, ...]:
    if raw_entries is None:
        return ()
    if not isinstance(raw_entries, Sequence) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        raise ValueError("ComfyUI returned an invalid queue list")

    entries: list[ComfyQueueEntry] = []
    for raw_entry in raw_entries:
        if isinstance(raw_entry, Mapping):
            prompt_id = raw_entry.get("prompt_id")
            queue_number = raw_entry.get("number")
            extra_data = raw_entry.get("extra_data")
        elif isinstance(raw_entry, Sequence) and not isinstance(
            raw_entry, (str, bytes, bytearray)
        ):
            if len(raw_entry) < 2:
                raise ValueError("ComfyUI returned a truncated queue entry")
            queue_number = raw_entry[0]
            prompt_id = raw_entry[1]
            extra_data = raw_entry[3] if len(raw_entry) > 3 else None
        else:
            raise ValueError("ComfyUI returned an invalid queue entry")

        _validate_prompt_id(prompt_id)
        if not isinstance(queue_number, (int, float)) or isinstance(queue_number, bool):
            queue_number = None
        client_id: str | None = None
        if isinstance(extra_data, Mapping):
            raw_client_id = extra_data.get("client_id")
            if isinstance(raw_client_id, str) and raw_client_id:
                client_id = raw_client_id
        entries.append(
            ComfyQueueEntry(
                prompt_id=prompt_id,
                phase=phase,
                queue_number=queue_number,
                client_id=client_id,
            )
        )
    return tuple(entries)


def _history_phase(record: Mapping[str, Any]) -> tuple[ComfyPromptPhase, str | None]:
    raw_status = record.get("status")
    if not isinstance(raw_status, Mapping):
        return ComfyPromptPhase.UNKNOWN, None

    raw_status_text = raw_status.get("status_str")
    status_text = raw_status_text if isinstance(raw_status_text, str) else None
    normalized_status = status_text.casefold() if status_text else ""
    event_names: set[str] = set()
    messages = raw_status.get("messages")
    if isinstance(messages, Sequence) and not isinstance(messages, (str, bytes)):
        for message in messages:
            if isinstance(message, Mapping):
                event_name = message.get("type")
            elif isinstance(message, Sequence) and not isinstance(
                message, (str, bytes)
            ):
                event_name = message[0] if message else None
            else:
                event_name = None
            if isinstance(event_name, str):
                event_names.add(event_name.casefold())

    if normalized_status in {"interrupted", "cancelled", "canceled"} or (
        "execution_interrupted" in event_names
    ):
        return ComfyPromptPhase.INTERRUPTED, status_text
    if normalized_status in {"error", "failed", "failure"} or (
        "execution_error" in event_names
    ):
        return ComfyPromptPhase.FAILED, status_text
    if raw_status.get("completed") is True or normalized_status in {
        "success",
        "completed",
    }:
        return ComfyPromptPhase.COMPLETED, status_text
    return ComfyPromptPhase.UNKNOWN, status_text


def _parse_device_stats(payload: Any) -> ComfyDeviceStats:
    if not isinstance(payload, Mapping):
        raise ValueError("ComfyUI returned an invalid device entry")
    name = payload.get("name")
    device_type = payload.get("type")
    index = payload.get("index")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("ComfyUI returned an invalid device name")
    if not isinstance(device_type, str) or not device_type.strip():
        raise ValueError("ComfyUI returned an invalid device type")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("ComfyUI returned an invalid device index")

    def memory_value(key: str, *, optional: bool = False) -> int | None:
        value = payload.get(key)
        if optional and value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"ComfyUI returned an invalid {key}")
        return value

    total = memory_value("vram_total")
    free = memory_value("vram_free")
    assert total is not None and free is not None
    if free > total:
        raise ValueError("ComfyUI returned impossible VRAM counters")
    return ComfyDeviceStats(
        name=name.strip(),
        device_type=device_type.strip(),
        index=index,
        vram_total=total,
        vram_free=free,
        torch_vram_total=memory_value("torch_vram_total", optional=True),
        torch_vram_free=memory_value("torch_vram_free", optional=True),
    )


def _validate_prompt_id(prompt_id: Any) -> None:
    if not isinstance(prompt_id, str) or not prompt_id:
        raise ValueError("prompt_id must not be empty")


def _parse_unet_loader_models(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        raise ValueError("ComfyUI returned an invalid UNETLoader description")
    node = payload.get("UNETLoader")
    if not isinstance(node, Mapping):
        raise ValueError("ComfyUI did not describe UNETLoader")
    inputs = node.get("input")
    if not isinstance(inputs, Mapping):
        raise ValueError("ComfyUI returned invalid UNETLoader inputs")
    required = inputs.get("required")
    if not isinstance(required, Mapping):
        raise ValueError("ComfyUI returned invalid UNETLoader required inputs")
    model_input = required.get("unet_name")
    if not isinstance(model_input, Sequence) or isinstance(
        model_input, (str, bytes, bytearray)
    ) or not model_input:
        raise ValueError("ComfyUI returned an invalid UNETLoader model input")
    return _parse_model_list(model_input[0])


def _parse_model_list(payload: Any) -> tuple[str, ...]:
    if isinstance(payload, Mapping):
        payload = payload.get("models")
    if not isinstance(payload, Sequence) or isinstance(
        payload, (str, bytes, bytearray)
    ):
        raise ValueError("ComfyUI returned an invalid diffusion model list")

    models: list[str] = []
    seen: set[str] = set()
    for value in payload:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ComfyUI returned an invalid diffusion model name")
        model_name = value.strip()
        if model_name not in seen:
            models.append(model_name)
            seen.add(model_name)
    return tuple(models)


def build_websocket_url(base_url: str, *, client_id: str) -> str:
    """Translate a ComfyUI HTTP base URL into its client-scoped WS endpoint."""
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must not be empty")
    if not client_id:
        raise ValueError("client_id must not be empty")
    parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
    scheme = {"http": "ws", "https": "wss"}.get(parsed.scheme)
    if scheme is None or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    path = f"{parsed.path.rstrip('/')}/ws"
    query = urllib.parse.urlencode({"clientId": client_id})
    return urllib.parse.urlunsplit((scheme, parsed.netloc, path, query, ""))


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
