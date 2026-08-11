"""Small bounded local journal for technical LLM call inspection."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from panelforge.application import (
    LlmCallApplicationOutcome,
    LlmCallImage,
    LlmCallRecord,
    LlmCallStatus,
)

from .local import (
    StorageCorruptionError,
    _atomic_write,
    _format_timestamp,
    _json_bytes,
    _parse_timestamp,
    _read_json_object,
)


_SCHEMA_VERSION = 2
_RECORD_KEYS_V1 = {
    "call_id",
    "operation_id",
    "requested_model_id",
    "actual_model_id",
    "started_at",
    "duration_ms",
    "status",
    "system_prompt",
    "user_prompt",
    "images",
    "temperature",
    "max_tokens",
    "response_text",
    "finish_reason",
    "prompt_tokens",
    "completion_tokens",
    "error_type",
    "error_message",
}
_RECORD_KEYS_V2 = {
    *_RECORD_KEYS_V1,
    "application_outcome",
    "application_error_type",
    "application_error_message",
}
_IMAGE_KEYS = {"label", "media_type", "byte_size", "sha256"}


class LocalLlmCallStore:
    def __init__(self, workspace_root: str | Path, *, capacity: int = 20) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        root = Path(workspace_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        self._path = root / "llm_calls.json"
        self._capacity = capacity
        self._lock = Lock()

    def append(self, record: LlmCallRecord) -> None:
        if not isinstance(record, LlmCallRecord):
            raise TypeError("record must be an LlmCallRecord")
        with self._lock:
            records = self._load()
            records.append(record)
            _atomic_write(
                self._path,
                _json_bytes(
                    {
                        "schema_version": _SCHEMA_VERSION,
                        "calls": [
                            _record_to_dict(item)
                            for item in records[-self._capacity :]
                        ],
                    }
                ),
            )

    def list(self, limit: int = 20) -> tuple[LlmCallRecord, ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self._capacity
        ):
            raise ValueError(f"limit must be between 1 and {self._capacity}")
        with self._lock:
            return tuple(reversed(self._load()[-limit:]))

    def _load(self) -> list[LlmCallRecord]:
        if not self._path.exists():
            return []
        if self._path.is_symlink() or not self._path.is_file():
            raise StorageCorruptionError("LLM call journal must be a regular file")
        raw = _read_json_object(self._path)
        if set(raw) != {"schema_version", "calls"}:
            raise StorageCorruptionError("invalid LLM call journal keys")
        schema_version = raw["schema_version"]
        if schema_version not in {1, _SCHEMA_VERSION}:
            raise StorageCorruptionError("unsupported LLM call journal schema")
        calls = raw["calls"]
        if not isinstance(calls, list):
            raise StorageCorruptionError("LLM call journal calls must be a list")
        if len(calls) > self._capacity:
            raise StorageCorruptionError("LLM call journal exceeds its capacity")
        return [
            _record_from_dict(item, schema_version=schema_version)
            for item in calls
        ]


def _record_to_dict(record: LlmCallRecord) -> dict[str, object]:
    return {
        "call_id": record.call_id,
        "operation_id": record.operation_id,
        "requested_model_id": record.requested_model_id,
        "actual_model_id": record.actual_model_id,
        "started_at": _format_timestamp(record.started_at),
        "duration_ms": record.duration_ms,
        "status": record.status.value,
        "system_prompt": record.system_prompt,
        "user_prompt": record.user_prompt,
        "images": [
            {
                "label": image.label,
                "media_type": image.media_type,
                "byte_size": image.byte_size,
                "sha256": image.sha256,
            }
            for image in record.images
        ],
        "temperature": record.temperature,
        "max_tokens": record.max_tokens,
        "response_text": record.response_text,
        "finish_reason": record.finish_reason,
        "prompt_tokens": record.prompt_tokens,
        "completion_tokens": record.completion_tokens,
        "error_type": record.error_type,
        "error_message": record.error_message,
        "application_outcome": (
            record.application_outcome.value
            if record.application_outcome is not None
            else None
        ),
        "application_error_type": record.application_error_type,
        "application_error_message": record.application_error_message,
    }


def _record_from_dict(
    value: object,
    *,
    schema_version: int,
) -> LlmCallRecord:
    expected_keys = _RECORD_KEYS_V1 if schema_version == 1 else _RECORD_KEYS_V2
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise StorageCorruptionError("invalid LLM call record")
    raw_images = value["images"]
    if not isinstance(raw_images, list):
        raise StorageCorruptionError("invalid LLM call image metadata")
    images: list[LlmCallImage] = []
    for raw_image in raw_images:
        if not isinstance(raw_image, dict) or set(raw_image) != _IMAGE_KEYS:
            raise StorageCorruptionError("invalid LLM call image record")
        images.append(
            LlmCallImage(
                label=raw_image["label"],
                media_type=raw_image["media_type"],
                byte_size=raw_image["byte_size"],
                sha256=raw_image["sha256"],
            )
        )
    try:
        return LlmCallRecord(
            call_id=value["call_id"],
            operation_id=value["operation_id"],
            requested_model_id=value["requested_model_id"],
            actual_model_id=value["actual_model_id"],
            started_at=_parse_timestamp(value["started_at"]),
            duration_ms=value["duration_ms"],
            status=LlmCallStatus(value["status"]),
            system_prompt=value["system_prompt"],
            user_prompt=value["user_prompt"],
            images=tuple(images),
            temperature=value["temperature"],
            max_tokens=value["max_tokens"],
            response_text=value["response_text"],
            finish_reason=value["finish_reason"],
            prompt_tokens=value["prompt_tokens"],
            completion_tokens=value["completion_tokens"],
            error_type=value["error_type"],
            error_message=value["error_message"],
            application_outcome=(
                LlmCallApplicationOutcome(value["application_outcome"])
                if schema_version >= 2
                and value["application_outcome"] is not None
                else None
            ),
            application_error_type=(
                value["application_error_type"] if schema_version >= 2 else None
            ),
            application_error_message=(
                value["application_error_message"] if schema_version >= 2 else None
            ),
        )
    except (TypeError, ValueError) as error:
        raise StorageCorruptionError("invalid LLM call record values") from error
