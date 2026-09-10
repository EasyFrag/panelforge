"""Strict loader for immutable, versioned prompt profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path

from panelforge.application import BriefPromptVariant, PromptProfile
from panelforge.domain import PromptSessionMode
from panelforge.domain.video_preparation import VideoPreparationRef


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
_BRIEF_VARIANT_KEYS = {
    "schema_version",
    "variant_id",
    "version",
    "display_name",
    "prompts",
}
_BRIEF_VARIANT_PROMPT_KEYS = {
    "brief_system",
    "brief_user",
    "brief_revision_system",
    "brief_revision_user",
}


class LocalPromptProfileCatalog:
    def __init__(self, root: str | Path, *, shared_blocks_root: str | Path | None = None) -> None:
        self._root = Path(root).resolve()
        self._shared_blocks_root = Path(shared_blocks_root).resolve() if shared_blocks_root else self._root.parent / "prompt_cookbooks" / "_blocks"
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
            if schema_version not in {1, 2, 3, 4, 5, 6}:
                raise ValueError("unsupported prompt profile schema")
            expected_manifest_keys = (
                (_MANIFEST_KEYS_V4 | {"vocal_policy_version", "preparation"}) if schema_version == 6 else
                (_MANIFEST_KEYS_V4 | {"vocal_policy_version"}) if schema_version == 5 else _MANIFEST_KEYS_V4 if schema_version == 4 else _MANIFEST_KEYS
            )
            if set(data) != expected_manifest_keys:
                raise ValueError(f"invalid prompt profile manifest: {manifest_path}")
            if schema_version >= 5 and data["vocal_policy_version"] != "1.0.0":
                raise ValueError("unsupported vocal policy version")
            prompts = data["prompts"]
            expected_prompt_keys = {
                1: _PROMPT_KEYS_V1,
                2: _PROMPT_KEYS_V2,
                3: _PROMPT_KEYS_V3,
                4: _PROMPT_KEYS_V4,
                5: _PROMPT_KEYS_V4,
                6: _PROMPT_KEYS_V4,
            }[schema_version]
            if not isinstance(prompts, dict) or set(prompts) != expected_prompt_keys:
                raise ValueError("invalid prompt profile prompt bindings")
            directory = manifest_path.parent.resolve()

            def read_prompt(key: str) -> str:
                if schema_version >= 6 and isinstance(prompts[key], list):
                    parts = []
                    for part in prompts[key]:
                        if not isinstance(part, dict) or set(part) != {"block", "version", "file"}:
                            raise ValueError("invalid profile shared block binding")
                        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", part["block"]) or not re.fullmatch(r"\d+\.\d+\.\d+", part["version"]):
                            raise ValueError("profile blocks require an exact version")
                        block_root = (self._shared_blocks_root / part["block"] / part["version"]).resolve()
                        block_root.relative_to(self._shared_blocks_root.resolve())
                        path = (block_root / part["file"]).resolve()
                        path.relative_to(block_root)
                        value = path.read_text(encoding="utf-8").strip()
                        if not value:
                            raise ValueError("empty profile shared block")
                        parts.append(value)
                    if not parts:
                        raise ValueError("empty profile prompt")
                    return "\n\n".join(parts)
                path = (directory / prompts[key]).resolve()
                try:
                    path.relative_to(directory)
                except ValueError as error:
                    raise ValueError("prompt file escapes its profile") from error
                text = path.read_text(encoding="utf-8").strip()
                if not text:
                    raise ValueError(f"empty prompt file: {path.name}")
                return text

            brief_variants = self._load_brief_variants(directory)

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
                brief_variants=brief_variants,
                vocal_policy_version=data.get("vocal_policy_version"),
                preparation=VideoPreparationRef.from_dict(data["preparation"]) if schema_version >= 6 else VideoPreparationRef(),
                session_mode=(
                    PromptSessionMode(data["session_mode"])
                    if schema_version >= 4
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

    @staticmethod
    def _load_brief_variants(directory: Path) -> tuple[BriefPromptVariant, ...]:
        root = directory / "brief_variants"
        if not root.is_dir():
            return ()
        variants: list[BriefPromptVariant] = []
        for definition_path in sorted(root.rglob("variant.json")):
            if definition_path.is_symlink():
                raise ValueError("brief variant definitions must not be symlinks")
            data = json.loads(definition_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) != _BRIEF_VARIANT_KEYS:
                raise ValueError(f"invalid brief variant definition: {definition_path}")
            if data["schema_version"] != 1:
                raise ValueError("unsupported brief variant schema")
            prompts = data["prompts"]
            if (
                not isinstance(prompts, dict)
                or set(prompts) != _BRIEF_VARIANT_PROMPT_KEYS
            ):
                raise ValueError("invalid brief variant prompt bindings")
            variant_directory = definition_path.parent.resolve()

            def read_variant_prompt(key: str) -> str:
                path = (variant_directory / prompts[key]).resolve()
                try:
                    path.relative_to(variant_directory)
                except ValueError as error:
                    raise ValueError("brief variant prompt escapes its directory") from error
                text = path.read_text(encoding="utf-8").strip()
                if not text:
                    raise ValueError(f"empty brief variant prompt: {path.name}")
                return text

            variants.append(BriefPromptVariant(
                variant_id=data["variant_id"],
                version=data["version"],
                display_name=data["display_name"],
                brief_system_prompt=read_variant_prompt("brief_system"),
                brief_user_prompt=read_variant_prompt("brief_user"),
                brief_revision_system_prompt=read_variant_prompt(
                    "brief_revision_system"
                ),
                brief_revision_user_prompt=read_variant_prompt(
                    "brief_revision_user"
                ),
            ))
        keys = [(value.variant_id, value.version) for value in variants]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate brief variant")
        return tuple(variants)
