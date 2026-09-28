"""Pure art-direction snapshots and deterministic KREA2 prompt compilation."""

from __future__ import annotations

from dataclasses import dataclass
import re


_PROVIDER_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_NUMERIC_SUFFIX = re.compile(r"\s*\(\d+\)$")


@dataclass(frozen=True, slots=True)
class Krea2ArtDirection:
    """Portable style prose pinned to a project, branch and render attempt."""

    provider_id: str
    style_id: str
    name: str
    category: str
    prompt: str
    catalog_revision: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or _PROVIDER_ID.fullmatch(self.provider_id) is None:
            raise ValueError("invalid art-direction provider")
        for value, label, maximum in (
            (self.style_id, "style_id", 240),
            (self.name, "style name", 240),
            (self.category, "style category", 120),
            (self.prompt, "style prompt", 8_000),
            (self.catalog_revision, "catalog revision", 128),
        ):
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
                raise ValueError(f"invalid {label}")

    @property
    def display_name(self) -> str:
        """Hide catalogue-only duplicate suffixes from the compiled prose."""
        return _NUMERIC_SUFFIX.sub("", self.name).strip()


def compile_krea2_art_direction(
    subject_prompt: str,
    direction: Krea2ArtDirection | None,
) -> str:
    """Compile a render prompt without mutating the canonical scene prompt."""
    if not isinstance(subject_prompt, str) or not subject_prompt.strip():
        raise ValueError("subject prompt must not be empty")
    subject = subject_prompt.strip()
    if direction is None:
        return subject
    style = direction.prompt.strip()
    separator = " " if style.endswith((".", "!", "?", ";", ":")) else ". "
    return f"Style: {direction.display_name}: {style}{separator}Subject: {subject}"


def validate_art_sources(style_preset: object | None, direction: Krea2ArtDirection | None) -> None:
    if direction is not None and not isinstance(direction, Krea2ArtDirection):
        raise TypeError("art_direction must be a Krea2ArtDirection")
