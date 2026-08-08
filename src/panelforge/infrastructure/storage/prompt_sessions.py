"""Strict local persistence for supervised Prompt Lab sessions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from panelforge.domain import (
    AnalysisRevision,
    PromptLabSession,
    PromptReference,
    RevisionOrigin,
)

from .local import (
    StorageCorruptionError,
    _atomic_write,
    _contained_entry,
    _format_timestamp,
    _json_bytes,
    _parse_timestamp,
    _read_json_object,
    _require_regular_file,
    _require_safe_id,
    _require_timestamp,
)


_SCHEMA_VERSION = 1
_SESSION_KEYS = {
    "schema_version",
    "created_at",
    "updated_at",
    "session_id",
    "model_id",
    "profile_id",
    "profile_version",
    "references",
}
_REFERENCE_KEYS = {
    "reference_id",
    "asset_id",
    "role",
    "label",
    "revisions",
    "active_revision_id",
    "approved_revision_id",
}
_REVISION_KEYS = {
    "revision_id",
    "content",
    "origin",
    "parent_revision_id",
    "instruction",
}


class LocalPromptSessionStore:
    """Store Prompt Lab state below ``<workspace>/prompt_sessions``."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions_root = Path(workspace_root).resolve() / "prompt_sessions"
        self._sessions_root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, session: PromptLabSession) -> PromptLabSession:
        _require_session(session)
        session_dir = self._entry_dir(session.session_id)
        session_dir.mkdir(exist_ok=False)
        session_path = session_dir / "session.json"
        try:
            timestamp = _format_timestamp(self._clock())
            _atomic_write(
                session_path,
                _json_bytes(
                    _session_to_dict(
                        session,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                ),
            )
        except BaseException:
            session_path.unlink(missing_ok=True)
            session_dir.rmdir()
            raise
        return session

    def save(self, session: PromptLabSession) -> PromptLabSession:
        _require_session(session)
        session_path = self._entry_dir(session.session_id) / "session.json"
        stored, created_at, _ = self._read_file(session_path, session.session_id)
        if stored.session_id != session.session_id:
            raise StorageCorruptionError(
                f"prompt session identity mismatch for {session.session_id!r}"
            )
        _atomic_write(
            session_path,
            _json_bytes(
                _session_to_dict(
                    session,
                    created_at=created_at,
                    updated_at=_format_timestamp(self._clock()),
                )
            ),
        )
        return session

    def get(self, session_id: str) -> PromptLabSession:
        session, _, _ = self._read_file(
            self._entry_dir(session_id) / "session.json",
            session_id,
        )
        return session

    def list(self, limit: int) -> list[PromptLabSession]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []

        indexed: list[tuple[datetime, str, PromptLabSession]] = []
        for directory in self._sessions_root.iterdir():
            if not directory.is_dir() or directory.is_symlink():
                continue
            _require_safe_id(directory.name, "stored prompt session ID")
            session, _, updated_at = self._read_file(
                directory / "session.json",
                directory.name,
            )
            indexed.append(
                (_parse_timestamp(updated_at), session.session_id, session)
            )
        indexed.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [session for _, _, session in indexed[:limit]]

    def _read_file(
        self,
        path: Path,
        expected_id: str,
    ) -> tuple[PromptLabSession, str, str]:
        _require_regular_file(path)
        data = _read_json_object(path)
        if set(data) != _SESSION_KEYS:
            raise StorageCorruptionError(
                f"invalid prompt session fields for {expected_id!r}"
            )
        if data.get("schema_version") != _SCHEMA_VERSION:
            raise StorageCorruptionError(
                f"unsupported prompt session schema for {expected_id!r}"
            )
        created_at = _require_timestamp(data.get("created_at"), "created_at")
        updated_at = _require_timestamp(data.get("updated_at"), "updated_at")
        try:
            session = _session_from_dict(data)
        except (KeyError, TypeError, ValueError) as error:
            raise StorageCorruptionError(
                f"invalid prompt session metadata for {expected_id!r}"
            ) from error
        if session.session_id != expected_id:
            raise StorageCorruptionError(
                f"prompt session identity mismatch for {expected_id!r}"
            )
        return session, created_at, updated_at

    def _entry_dir(self, session_id: str) -> Path:
        _require_safe_id(session_id, "prompt session ID")
        return _contained_entry(self._sessions_root, session_id)


def _require_session(value: object) -> PromptLabSession:
    if not isinstance(value, PromptLabSession):
        raise TypeError("session must be a PromptLabSession")
    _require_safe_id(value.session_id, "prompt session ID")
    return value


def _session_to_dict(
    session: PromptLabSession,
    *,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": created_at,
        "updated_at": updated_at,
        "session_id": session.session_id,
        "model_id": session.model_id,
        "profile_id": session.profile_id,
        "profile_version": session.profile_version,
        "references": [
            {
                "reference_id": reference.reference_id,
                "asset_id": reference.asset_id,
                "role": reference.role,
                "label": reference.label,
                "revisions": [
                    {
                        "revision_id": revision.revision_id,
                        "content": revision.content,
                        "origin": revision.origin.value,
                        "parent_revision_id": revision.parent_revision_id,
                        "instruction": revision.instruction,
                    }
                    for revision in reference.revisions
                ],
                "active_revision_id": reference.active_revision_id,
                "approved_revision_id": reference.approved_revision_id,
            }
            for reference in session.references
        ],
    }


def _session_from_dict(data: dict[str, object]) -> PromptLabSession:
    raw_references = data["references"]
    if not isinstance(raw_references, list):
        raise TypeError("references must be a list")
    references: list[PromptReference] = []
    for raw_reference in raw_references:
        if not isinstance(raw_reference, dict) or set(raw_reference) != _REFERENCE_KEYS:
            raise ValueError("reference contains invalid fields")
        raw_revisions = raw_reference["revisions"]
        if not isinstance(raw_revisions, list):
            raise TypeError("revisions must be a list")
        revisions: list[AnalysisRevision] = []
        for raw_revision in raw_revisions:
            if not isinstance(raw_revision, dict) or set(raw_revision) != _REVISION_KEYS:
                raise ValueError("revision contains invalid fields")
            revisions.append(
                AnalysisRevision(
                    revision_id=raw_revision["revision_id"],
                    content=raw_revision["content"],
                    origin=RevisionOrigin(raw_revision["origin"]),
                    parent_revision_id=raw_revision["parent_revision_id"],
                    instruction=raw_revision["instruction"],
                )
            )
        references.append(
            PromptReference(
                reference_id=raw_reference["reference_id"],
                asset_id=raw_reference["asset_id"],
                role=raw_reference["role"],
                label=raw_reference["label"],
                revisions=tuple(revisions),
                active_revision_id=raw_reference["active_revision_id"],
                approved_revision_id=raw_reference["approved_revision_id"],
            )
        )
    return PromptLabSession(
        session_id=data["session_id"],
        model_id=data["model_id"],
        profile_id=data["profile_id"],
        profile_version=data["profile_version"],
        references=tuple(references),
    )
