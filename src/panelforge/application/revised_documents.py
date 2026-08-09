"""Deterministic extraction of one revised document from a model response."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class RevisedDocumentContract:
    """Describe the stable line markers of one editable document."""

    name: str
    markers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("document contract name must not be empty")
        if not isinstance(self.markers, tuple) or not self.markers:
            raise ValueError("document contract markers must not be empty")
        if len(set(self.markers)) != len(self.markers):
            raise ValueError("document contract markers must be unique")
        for marker in self.markers:
            if not isinstance(marker, str) or not marker.strip() or "\n" in marker:
                raise ValueError("document contract markers must be single non-empty lines")

    def extract(self, response: str, *, strict: bool = True) -> str:
        """Return the single structured document and drop any leading envelope."""

        value = strip_markdown_fence(response).replace("\r\n", "\n")
        marker_matches: list[tuple[str, list[re.Match[str]]]] = []
        for marker in self.markers:
            matches = list(
                re.finditer(
                    rf"(?m)^{re.escape(marker)}(?=$|[ \t])",
                    value,
                )
            )
            marker_matches.append((marker, matches))
        if not strict and not any(matches for _, matches in marker_matches):
            return value
        positions: list[int] = []
        for marker, matches in marker_matches:
            if not matches:
                raise ValueError(
                    f"{self.name} revision is missing marker: {marker}"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"{self.name} revision contains multiple documents: {marker}"
                )
            positions.append(matches[0].start())
        if positions != sorted(positions):
            raise ValueError(f"{self.name} revision markers are out of order")
        return value[positions[0] :].strip()


def strip_markdown_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    if not value:
        raise ValueError("revised document must not be empty")
    return value
