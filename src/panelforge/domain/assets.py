"""Vendor-neutral metadata for content managed by PanelForge."""

from __future__ import annotations

from dataclasses import dataclass
import re


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class Asset:
    """One immutable piece of content known by the asset catalogue.

    ``storage_key`` is deliberately opaque to the domain.  A storage adapter may
    resolve it to a local file, an object-store key, or another representation.
    """

    asset_id: str
    media_type: str
    content_sha256: str
    size_bytes: int
    storage_key: str
    source_run_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.asset_id, "asset_id")
        _require_identifier(self.media_type, "media_type")
        _require_sha256(self.content_sha256, "content_sha256")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise TypeError("size_bytes must be an integer")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be greater than zero")
        _require_identifier(self.storage_key, "storage_key")
        if self.source_run_id is not None:
            _require_identifier(self.source_run_id, "source_run_id")


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value
