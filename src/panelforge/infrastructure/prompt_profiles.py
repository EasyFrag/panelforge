"""Strict loader for immutable, versioned prompt profiles."""

from __future__ import annotations

import json
from pathlib import Path

from panelforge.application import PromptProfile
from panelforge.domain import PromptSessionMode


_MANIFEST_KEYS = {
    "schema_version",
    "profile_id",
    "version",
    "display_name",
    "target_model_family",
    "source_guides",
    "prompts",
    "status",
}
_MANIFEST_KEYS_V4 = _MANIFEST_KEYS | {"session_mode"}
_PROMPT_KEYS_V1 = {
    "analysis_system",
    "analysis_user",
    "revision_system",
    "revision_user",
}
_PROMPT_KEYS_V2 = _PROMPT_KEYS_V1 | {
    "interpretation_system",
    "interpretation_user",
    "interpretation_revision_system",
    "interpretation_revision_user",
}
_PROMPT_KEYS_V3 = _PROMPT_KEYS_V2 | {
    "brief_system",
    "brief_user",
    "brief_revision_system",
    "brief_revision_user",
}
_PROMPT_KEYS_V4 = _PROMPT_KEYS_V1 | {
    "brief_system",
    "brief_user",
    "brief_revision_system",
    "brief_revision_user",
}


class LocalPromptProfileCatalog:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._profiles = self._load_all()

    def list(self) -> tuple[PromptProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def get(self, profile_id: str, version: str) -> PromptProfile:
        try:
            return self._profiles[(profile_id, version)]
        except KeyError as error:
            raise KeyError(f"unknown prompt profile {profile_id}@{version}") from error

    def _load_all(self) -> dict[tuple[str, str], PromptProfile]:
        profiles: dict[tuple[str, str], PromptProfile] = {}
        if not self._root.is_dir():
            raise FileNotFoundError(self._root)
        for manifest_path in sorted(self._root.rglob("manifest.json")):
            if manifest_path.is_symlink():
                raise ValueError("prompt profile manifests must not be symlinks")
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"invalid prompt profile manifest: {manifest_path}")
            schema_version = data.get("schema_version")
            if schema_version not in {1, 2, 3, 4}:
                raise ValueError("unsupported prompt profile schema")
            expected_manifest_keys = (
                _MANIFEST_KEYS_V4 if schema_version == 4 else _MANIFEST_KEYS
            )
            if set(data) != expected_manifest_keys:
                raise ValueError(f"invalid prompt profile manifest: {manifest_path}")
            prompts = data["prompts"]
            expected_prompt_keys = {
                1: _PROMPT_KEYS_V1,
                2: _PROMPT_KEYS_V2,
                3: _PROMPT_KEYS_V3,
                4: _PROMPT_KEYS_V4,
            }[schema_version]
            if not isinstance(prompts, dict) or set(prompts) != expected_prompt_keys:
                raise ValueError("invalid prompt profile prompt bindings")
            directory = manifest_path.parent.resolve()

            def read_prompt(key: str) -> str:
                path = (directory / prompts[key]).resolve()
                try:
                    path.relative_to(directory)
                except ValueError as error:
                    raise ValueError("prompt file escapes its profile") from error
                text = path.read_text(encoding="utf-8").strip()
                if not text:
                    raise ValueError(f"empty prompt file: {path.name}")
                return text

            profile = PromptProfile(
                profile_id=data["profile_id"],
                version=data["version"],
                display_name=data["display_name"],
                target_model_family=data["target_model_family"],
                analysis_system_prompt=read_prompt("analysis_system"),
                analysis_user_prompt=read_prompt("analysis_user"),
                revision_system_prompt=read_prompt("revision_system"),
                revision_user_prompt=read_prompt("revision_user"),
                interpretation_system_prompt=(
                    read_prompt("interpretation_system")
                    if schema_version in {2, 3}
                    else None
                ),
                interpretation_user_prompt=(
                    read_prompt("interpretation_user")
                    if schema_version in {2, 3}
                    else None
                ),
                interpretation_revision_system_prompt=(
                    read_prompt("interpretation_revision_system")
                    if schema_version in {2, 3}
                    else None
                ),
                interpretation_revision_user_prompt=(
                    read_prompt("interpretation_revision_user")
                    if schema_version in {2, 3}
                    else None
                ),
                brief_system_prompt=(
                    read_prompt("brief_system")
                    if schema_version >= 3
                    else None
                ),
                brief_user_prompt=(
                    read_prompt("brief_user")
                    if schema_version >= 3
                    else None
                ),
                brief_revision_system_prompt=(
                    read_prompt("brief_revision_system")
                    if schema_version >= 3
                    else None
                ),
                brief_revision_user_prompt=(
                    read_prompt("brief_revision_user")
                    if schema_version >= 3
                    else None
                ),
                session_mode=(
                    PromptSessionMode(data["session_mode"])
                    if schema_version == 4
                    else PromptSessionMode.ANALYZED
                ),
            )
            key = (profile.profile_id, profile.version)
            if key in profiles:
                raise ValueError(f"duplicate prompt profile {key}")
            profiles[key] = profile
        if not profiles:
            raise ValueError("no prompt profiles found")
        return profiles
