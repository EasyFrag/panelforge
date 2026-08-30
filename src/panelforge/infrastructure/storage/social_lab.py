"""Durable local storage for Social Lab projects and channel profiles."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain.social_lab import (
    SocialChannelProfile,
    SocialLanguage,
    SocialProject,
    SocialTurn,
    SocialTurnRole,
    SocialVariant,
)


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalSocialLabStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "social_lab"
        self._projects = self._root / "projects"
        self._profiles = self._root / "profiles"
        self._projects.mkdir(parents=True, exist_ok=True)
        self._profiles.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create_project(self, project: SocialProject) -> SocialProject:
        with self._lock:
            directory = self._directory(self._projects, project.project_id)
            directory.mkdir(exist_ok=False)
            timestamp = _timestamp()
            _atomic_write(
                directory / "project.json",
                _json_bytes(_serialize_project(project, timestamp, timestamp)),
            )
        return project

    def save_project(self, project: SocialProject) -> SocialProject:
        with self._lock:
            path = self._directory(self._projects, project.project_id) / "project.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(project.project_id)
            current = _read_object(path)
            created_at = current.get("created_at")
            if not isinstance(created_at, str):
                raise ValueError("stored Social Lab project has no created_at")
            _atomic_write(
                path,
                _json_bytes(_serialize_project(project, created_at, _timestamp())),
            )
        return project

    def get_project(self, project_id: str) -> SocialProject:
        with self._lock:
            path = self._directory(self._projects, project_id) / "project.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(project_id)
            return _deserialize_project(_read_object(path))

    def list_projects(self, limit: int = 30) -> list[SocialProject]:
        return self._list(self._projects, "project.json", _deserialize_project, limit)

    def save_profile(self, profile: SocialChannelProfile) -> SocialChannelProfile:
        with self._lock:
            directory = self._directory(self._profiles, profile.profile_id)
            directory.mkdir(exist_ok=True)
            _atomic_write(
                directory / "profile.json",
                _json_bytes(_serialize_profile(profile, _timestamp())),
            )
        return profile

    def get_profile(self, profile_id: str) -> SocialChannelProfile:
        with self._lock:
            path = self._directory(self._profiles, profile_id) / "profile.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(profile_id)
            return _deserialize_profile(_read_object(path))

    def list_profiles(self, limit: int = 100) -> list[SocialChannelProfile]:
        return self._list(self._profiles, "profile.json", _deserialize_profile, limit)

    def _list(self, root: Path, filename: str, loader, limit: int) -> list[Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if limit == 0:
            return []
        values: list[tuple[float, str, Any]] = []
        with self._lock:
            for directory in root.iterdir():
                path = directory / filename
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append((path.stat().st_mtime, directory.name, loader(_read_object(path))))
        values.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [value for _, _, value in values[:limit]]

    @staticmethod
    def _directory(root: Path, identifier: str) -> Path:
        _safe(identifier)
        candidate = root / identifier
        candidate.resolve().relative_to(root.resolve())
        if candidate.is_symlink():
            raise ValueError("Social Lab storage directory cannot be a symlink")
        return candidate


def _serialize_project(
    project: SocialProject,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "created_at": created_at,
        "updated_at": updated_at,
        "project_id": project.project_id,
        "name": project.name,
        "model_id": project.model_id,
        "language": project.language.value,
        "variant_count": project.variant_count,
        "video_asset_id": project.video_asset_id,
        "video_filename": project.video_filename,
        "keyframe_asset_ids": list(project.keyframe_asset_ids),
        "mood": project.mood,
        "vibe": project.vibe,
        "example": project.example,
        "instructions": project.instructions,
        "channel_profile_id": project.channel_profile_id,
        "source_prompt": project.source_prompt,
        "turns": [_serialize_turn(turn) for turn in project.turns],
    }


def _deserialize_project(value: dict[str, Any]) -> SocialProject:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported Social Lab project schema")
    return SocialProject(
        project_id=value["project_id"],
        name=value["name"],
        model_id=value["model_id"],
        language=SocialLanguage(value["language"]),
        variant_count=value["variant_count"],
        video_asset_id=value["video_asset_id"],
        video_filename=value["video_filename"],
        keyframe_asset_ids=tuple(value["keyframe_asset_ids"]),
        mood=value.get("mood", ""),
        vibe=value.get("vibe", ""),
        example=value.get("example", ""),
        instructions=value.get("instructions", ""),
        channel_profile_id=value.get("channel_profile_id"),
        source_prompt=value.get("source_prompt"),
        turns=tuple(_deserialize_turn(item) for item in value.get("turns", [])),
    )


def _serialize_turn(turn: SocialTurn) -> dict[str, object]:
    return {
        "turn_id": turn.turn_id,
        "role": turn.role.value,
        "content": turn.content,
        "variants": [_serialize_variant(value) for value in turn.variants],
    }


def _deserialize_turn(value: dict[str, Any]) -> SocialTurn:
    return SocialTurn(
        turn_id=value["turn_id"],
        role=SocialTurnRole(value["role"]),
        content=value["content"],
        variants=tuple(_deserialize_variant(item) for item in value.get("variants", [])),
    )


def _serialize_variant(value: SocialVariant) -> dict[str, object]:
    return {
        "angle": value.angle,
        "hook": value.hook,
        "caption": value.caption,
        "hashtags": list(value.hashtags),
        "emojis": list(value.emojis),
    }


def _deserialize_variant(value: dict[str, Any]) -> SocialVariant:
    return SocialVariant(
        angle=value["angle"],
        hook=value["hook"],
        caption=value["caption"],
        hashtags=tuple(value.get("hashtags", [])),
        emojis=tuple(value.get("emojis", [])),
    )


def _serialize_profile(profile: SocialChannelProfile, updated_at: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "updated_at": updated_at,
        "profile_id": profile.profile_id,
        "name": profile.name,
        "language": profile.language.value,
        "mood": profile.mood,
        "vibe": profile.vibe,
        "example": profile.example,
        "instructions": profile.instructions,
    }


def _deserialize_profile(value: dict[str, Any]) -> SocialChannelProfile:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported Social Lab profile schema")
    return SocialChannelProfile(
        profile_id=value["profile_id"],
        name=value["name"],
        language=SocialLanguage(value.get("language", "en")),
        mood=value.get("mood", ""),
        vibe=value.get("vibe", ""),
        example=value.get("example", ""),
        instructions=value.get("instructions", ""),
    )


def _safe(value: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("unsafe Social Lab identifier")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Social Lab storage document must be an object")
    return value


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = ["LocalSocialLabStore"]
