"""Deterministic compiler for fragile MiniMax H3 prompt syntax."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
import json
import re

from panelforge.domain.minimax_h3 import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
    H3MediaKind,
    h3_media_label,
)


PROTOCOL_ID = "minimax.h3.protocol"
PROTOCOL_VERSION = "0.1.0"
UPSTREAM_COMMIT = "05d91ff89f58b665e56424fd66db9ef0351b3015"
UPSTREAM_BLOBS = {
    "SKILL.md": "066429d78f72b080a52350a5b165e52cb31b0bca",
    "references/base-en.txt": "40cf586a634d677d6b7107b367cf0ec9621be728",
    "references/ref-en.txt": "7ae1b2d07d743fd2392258a96449be9e9e322d35",
}


class H3ProtocolMode(StrEnum):
    I2VA = "i2va"
    REF2VA = "ref2va"


class H3IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class H3ProtocolIssue:
    severity: H3IssueSeverity
    code: str
    message: str


_CAMERA_PHRASES = {
    H3CameraMotion.ZOOM_IN: "The camera zooms in",
    H3CameraMotion.ZOOM_OUT: "The camera zooms out",
    H3CameraMotion.PUSH_IN: "The camera pushes in",
    H3CameraMotion.PULL_OUT: "The camera pulls out",
    H3CameraMotion.PAN_LEFT: "The camera pans left",
    H3CameraMotion.PAN_RIGHT: "The camera pans right",
    H3CameraMotion.TRUCK_LEFT: "The camera trucks left",
    H3CameraMotion.TRUCK_RIGHT: "The camera trucks right",
    H3CameraMotion.TILT_UP: "The camera tilts up",
    H3CameraMotion.TILT_DOWN: "The camera tilts down",
    H3CameraMotion.PEDESTAL_UP: "The camera pedestals up",
    H3CameraMotion.PEDESTAL_DOWN: "The camera pedestals down",
    H3CameraMotion.ARC_SHOT: "The camera performs an arc shot",
    H3CameraMotion.TRACKING_SHOT: "The camera performs a tracking shot",
    H3CameraMotion.STATIC_SHOT: "The camera holds a static shot",
    H3CameraMotion.SHAKE_SLIGHTLY: "The camera shakes slightly",
    H3CameraMotion.SHAKE_STRONGLY: "The camera shakes strongly",
    H3CameraMotion.POV: "The shot adopts the subject's POV",
    H3CameraMotion.ROLL_CLOCKWISE: "The camera rolls clockwise",
    H3CameraMotion.ROLL_COUNTERCLOCKWISE: "The camera rolls counterclockwise",
}
_AMPLITUDE_PHRASES = {
    H3CameraAmplitude.SMALL: "with small amplitude",
    H3CameraAmplitude.LARGE: "with large amplitude",
}
_SPEED_PHRASES = {
    H3CameraSpeed.SLOW: "at slow speed",
    H3CameraSpeed.FAST: "at fast speed",
}
_PLACEHOLDER = re.compile(r"\[\[camera:(?P<id>[a-z0-9_]+)\]\]")
_FREE_CAMERA_MOTION = re.compile(
    r"(?i)\b(?:the\s+)?(?:camera|shot|lens)\s+(?:zooms?|pushes?|pulls?|pans?|trucks?|"
    r"tilts?|pedestals?|moves?|arcs?|tracks?|follows?|shakes?|rolls?|"
    r"orbits?|dollies|cranes?|drifts?)\b"
)
_FREE_CAMERA_NOUN = re.compile(
    r"(?i)\b(?:(?:slow|fast|subtle|gentle|visible)\s+)?(?:dolly|handheld)\s+"
    r"(?:shot|move|movement|in|out|left|right)\b|"
    r"\b(?:slow|fast|subtle|gentle|visible)\s+(?:orbit|crane)\b|"
    r"\bPOV\s+shot\b"
)
_NONCANONICAL_CAMERA_MODIFIER = re.compile(
    r"(?i)\bwith\s+(?!(?:small|large)\s+amplitude\b)\w+\s+amplitude\b|"
    r"\bat\s+(?!(?:slow|fast)\s+speed\b)\w+\s+speed\b"
)
_LANGUAGE_ALIASES = {
    "ar": "Arabic",
    "ara": "Arabic",
    "arabic": "Arabic",
    "zh": "Chinese",
    "zho": "Chinese",
    "chinese": "Chinese",
    "en": "English",
    "eng": "English",
    "english": "English",
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "french": "French",
    "de": "German",
    "deu": "German",
    "ger": "German",
    "german": "German",
    "it": "Italian",
    "ita": "Italian",
    "italian": "Italian",
    "ja": "Japanese",
    "jpn": "Japanese",
    "japanese": "Japanese",
    "ko": "Korean",
    "kor": "Korean",
    "korean": "Korean",
    "pt": "Portuguese",
    "por": "Portuguese",
    "portuguese": "Portuguese",
    "ru": "Russian",
    "rus": "Russian",
    "russian": "Russian",
    "es": "Spanish",
    "spa": "Spanish",
    "spanish": "Spanish",
}


def compile_camera_motion(directive: H3CameraDirective) -> str:
    if not isinstance(directive, H3CameraDirective):
        raise TypeError("directive must be an H3CameraDirective")
    parts = [_CAMERA_PHRASES[directive.motion]]
    if directive.amplitude is not None:
        parts.append(_AMPLITUDE_PHRASES[directive.amplitude])
    if directive.speed is not None:
        parts.append(_SPEED_PHRASES[directive.speed])
    target = directive.target_clause.rstrip(". ")
    clause = " ".join(parts)
    if target:
        separator = (
            ", "
            if re.match(
                r"(?i)^(?:revealing|following|keeping|maintaining|showing)\b",
                target,
            )
            else " "
        )
        clause += separator + target
    return clause.rstrip(". ") + "."


def parse_camera_directives(value: str | object) -> tuple[H3CameraDirective, ...]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("camera_directives must contain valid JSON") from error
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError("camera_directives must be a JSON array of 1 to 8 items")
    directives: list[H3CameraDirective] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each camera directive must be a JSON object")
        allowed = {"id", "motion", "amplitude", "speed", "target_clause"}
        if set(raw) - allowed or not {"id", "motion"}.issubset(raw):
            raise ValueError("camera directive fields do not match the protocol")
        try:
            directive = H3CameraDirective(
                directive_id=raw["id"],
                motion=H3CameraMotion(raw["motion"]),
                amplitude=(
                    H3CameraAmplitude(raw["amplitude"])
                    if raw.get("amplitude") is not None
                    else None
                ),
                speed=(
                    H3CameraSpeed(raw["speed"])
                    if raw.get("speed") is not None
                    else None
                ),
                target_clause=raw.get("target_clause") or "",
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid camera directive: {error}") from error
        directives.append(directive)
    ids = [directive.directive_id for directive in directives]
    if len(ids) != len(set(ids)):
        raise ValueError("camera directive IDs must be unique")
    return tuple(directives)


def compile_camera_placeholders(
    content: str,
    directives: tuple[H3CameraDirective, ...],
    *,
    require_all: bool = True,
) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("camera draft content must not be empty")
    by_id = {directive.directive_id: directive for directive in directives}
    if len(by_id) != len(directives):
        raise ValueError("camera directive IDs must be unique")
    placeholder_matches = list(_PLACEHOLDER.finditer(content))
    occurrences = [match.group("id") for match in placeholder_matches]
    unknown = sorted(set(occurrences) - set(by_id))
    if unknown:
        raise ValueError(f"unknown camera placeholder(s): {', '.join(unknown)}")
    if require_all:
        for directive_id in by_id:
            count = occurrences.count(directive_id)
            if count != 1:
                raise ValueError(
                    f"camera placeholder {directive_id} must appear exactly once"
                )
    for directive_id in set(occurrences):
        if occurrences.count(directive_id) != 1:
            raise ValueError(
                f"camera placeholder {directive_id} must appear exactly once"
            )
    placeholder_free = _PLACEHOLDER.sub("", content)
    if "[[" in placeholder_free or "]]" in placeholder_free:
        raise ValueError("unresolved or malformed compiler placeholder")
    _validate_camera_placeholder_context(content, placeholder_matches)
    compiled = _PLACEHOLDER.sub(
        lambda match: compile_camera_motion(by_id[match.group("id")]),
        content,
    )
    if "[[" in compiled or "]]" in compiled:
        raise ValueError("unresolved or malformed compiler placeholder")
    return compiled


def _validate_camera_placeholder_context(
    content: str,
    matches: list[re.Match[str]],
) -> None:
    """Keep compiled camera clauses as complete, readable sentences."""

    for match in matches:
        before = content[: match.start()]
        line_before = before.rsplit("\n", 1)[-1].rstrip()
        starts_sentence = (
            not line_before
            or re.search(r"[.!?]$", line_before) is not None
            or re.search(r"[.!?]</d>$", line_before) is not None
            or re.search(r"\[Shot\s+\d+\]$", line_before) is not None
            or re.search(r"At\s+\d{2}:\d{2}\.\d{3},$", line_before) is not None
        )
        if not starts_sentence:
            raise ValueError(
                "camera placeholder must be a standalone sentence or follow an "
                "exact At MM:SS.mmm, landmark"
            )

        after = content[match.end() :]
        if not after:
            continue
        if not after[0].isspace():
            raise ValueError("camera placeholder must be followed by a sentence boundary")
        same_line = after.split("\n", 1)[0].strip()
        if not same_line:
            continue
        first = same_line[0]
        if first.islower() or first in ",;:":
            raise ValueError(
                "text after a camera placeholder must begin a new sentence"
            )


def compile_camera_draft(content: str) -> tuple[str, tuple[H3CameraDirective, ...]]:
    """Compile an internal I2V draft and remove its JSON directive field."""
    value = _strip_fence(content).replace("\r\n", "\n")
    marker = "integrated_multimodal_description:"
    if not value.startswith("camera_directives:"):
        raise ValueError("canonical draft must start with camera_directives:")
    marker_match = re.search(rf"(?m)^{re.escape(marker)}", value)
    if marker_match is None:
        raise ValueError(f"canonical draft is missing {marker}")
    raw_directives = value[len("camera_directives:") : marker_match.start()].strip()
    directives = parse_camera_directives(raw_directives)
    body = value[marker_match.start() :].strip()
    return (
        normalize_dialogue_language_tags(
            compile_camera_placeholders(body, directives)
        ),
        directives,
    )


def normalize_dialogue_language_tags(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("dialogue content must be a string")

    def bracketed(match: re.Match[str]) -> str:
        raw = match.group("language")
        normalized = _LANGUAGE_ALIASES.get(raw.casefold(), raw)
        return f"<d>[{normalized}] "

    value = re.sub(
        r"<d>\s*\[(?P<language>[A-Za-z]{2,20})\]\s*",
        bracketed,
        content,
    )

    def abbreviated(match: re.Match[str]) -> str:
        normalized = _LANGUAGE_ALIASES[match.group("language").casefold()]
        return f"<d>[{normalized}] "

    return re.sub(
        r"<d>\s*(?P<language>ar|zh|en|fr|de|it|ja|ko|pt|ru|es)\s*[:\-]\s*",
        abbreviated,
        value,
        flags=re.IGNORECASE,
    )


def compile_dialogue_tag(language: str, text: str) -> str:
    if not isinstance(language, str) or not language.strip():
        raise ValueError("dialogue language must not be empty")
    raw_language = language.strip()
    canonical = _LANGUAGE_ALIASES.get(raw_language.casefold())
    if canonical is None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z -]{3,39}", raw_language):
            raise ValueError("dialogue language must use its full English name")
        canonical = raw_language
    if not isinstance(text, str) or not text.strip():
        raise ValueError("dialogue text must not be empty")
    return f"<d>[{canonical}] {text.strip()}</d>"


def compile_shot_heading(number: int, timestamp_ms: int | None = None) -> str:
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("shot number must be a positive integer")
    if number == 1:
        if timestamp_ms is not None:
            raise ValueError("[Shot 1] must not carry a timestamp")
        return "[Shot 1]"
    if isinstance(timestamp_ms, bool) or not isinstance(timestamp_ms, int):
        raise ValueError("later shots require a timestamp in milliseconds")
    if timestamp_ms < 0:
        raise ValueError("shot timestamp must not be negative")
    minutes, remainder = divmod(timestamp_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"[Shot {number}] At {minutes:02d}:{seconds:02d}.{milliseconds:03d},"


def compile_media_label(kind: H3MediaKind, number: int) -> str:
    return h3_media_label(kind, number)


def lint_h3_prompt(
    mode: H3ProtocolMode | str,
    content: str,
    *,
    expected_directives: tuple[H3CameraDirective, ...] = (),
) -> tuple[H3ProtocolIssue, ...]:
    try:
        mode = H3ProtocolMode(mode)
    except ValueError as error:
        raise ValueError("unsupported H3 protocol mode") from error
    if not isinstance(content, str) or not content.strip():
        return (
            H3ProtocolIssue(H3IssueSeverity.ERROR, "empty", "H3 prompt is empty"),
        )
    issues: list[H3ProtocolIssue] = []
    if "[[" in content or "]]" in content:
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "camera_placeholder",
                "an unresolved camera placeholder remains",
            )
        )
    expected_camera_clauses = Counter(
        compile_camera_motion(directive) for directive in expected_directives
    )
    for clause, expected_count in expected_camera_clauses.items():
        if content.count(clause) != expected_count:
            directive_ids = ", ".join(
                directive.directive_id
                for directive in expected_directives
                if compile_camera_motion(directive) == clause
            )
            issues.append(
                H3ProtocolIssue(
                    H3IssueSeverity.ERROR,
                    "camera_clause",
                    "compiled camera clause for "
                    f"{directive_ids} must appear {expected_count} time(s)",
                )
            )
    prose_without_canonical_camera = content
    phrases_to_remove = (
        tuple(compile_camera_motion(item) for item in expected_directives)
        if expected_directives
        else tuple(_CAMERA_PHRASES.values())
    )
    for phrase in phrases_to_remove:
        prose_without_canonical_camera = prose_without_canonical_camera.replace(
            phrase,
            "",
        )
    modifier_source = (
        prose_without_canonical_camera if expected_directives else content
    )
    if (
        _FREE_CAMERA_MOTION.search(prose_without_canonical_camera)
        or _FREE_CAMERA_NOUN.search(prose_without_canonical_camera)
        or _has_noncanonical_camera_modifier(modifier_source)
    ):
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "free_camera_motion",
                "camera movement must come from a canonical compiled directive",
            )
        )
    if content.count("<d>") != content.count("</d>"):
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "dialogue_balance",
                "dialogue tags are not balanced",
            )
        )
    dialogue_blocks = re.findall(r"<d>(.*?)</d>", content, flags=re.DOTALL)
    for block in dialogue_blocks:
        if not re.match(r"\s*\[[A-Za-z][A-Za-z -]{3,39}\]\s+\S", block):
            issues.append(
                H3ProtocolIssue(
                    H3IssueSeverity.ERROR,
                    "dialogue_format",
                    "every <d> block must begin with a full [Language] tag",
                )
            )
            break
    scenetrans_count = content.count("<scenetrans>")
    if scenetrans_count % 2:
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "scenetrans_pair",
                "<scenetrans> must appear at both connecting points of a cut",
            )
        )
    for voiceover in re.finditer(
        r"(?i)says in an off-screen voiceover[^<]*<d>.*?</d>",
        content,
        flags=re.DOTALL,
    ):
        following = content[voiceover.end() : voiceover.end() + 180]
        if re.search(r"(?i)lips remain completely closed", following) is None:
            issues.append(
                H3ProtocolIssue(
                    H3IssueSeverity.WARNING,
                    "voiceover_lips",
                    "voiceover dialogue should state that the on-screen lips remain completely closed",
                )
            )
    for label in re.findall(r"<d>\s*\[([^\]]+)\]", content):
        if (
            label.casefold() in _LANGUAGE_ALIASES
            and len(label) <= 3
        ) or not re.fullmatch(r"[A-Za-z][A-Za-z -]{3,39}", label):
            issues.append(
                H3ProtocolIssue(
                    H3IssueSeverity.ERROR,
                    "dialogue_language",
                    f"dialogue language must use a full canonical name: {label}",
                )
            )
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>", content):
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "legacy_image_label",
                "use canonical <Picture N> labels instead of @image or <Image N>",
            )
        )
    if mode is H3ProtocolMode.I2VA and re.search(r"<Subject\s+\d+>", content):
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.ERROR,
                "i2va_subject_label",
                "the simple I2VA contract does not use <Subject N>",
            )
        )
    if "<|cutoff|>" in content:
        issues.append(
            H3ProtocolIssue(
                H3IssueSeverity.WARNING,
                "tokenizer_cutoff",
                "the guide documents <cutoff>; <|cutoff|> requires a targeted engine test",
            )
        )
    return tuple(issues)


def _has_noncanonical_camera_modifier(content: str) -> bool:
    for pattern in (_FREE_CAMERA_MOTION, _FREE_CAMERA_NOUN):
        for camera_match in pattern.finditer(content):
            sentence_end = re.search(r"[.!?\n]", content[camera_match.end() :])
            end = (
                camera_match.end() + sentence_end.start()
                if sentence_end is not None
                else len(content)
            )
            tail = content[camera_match.end() : end]
            modifier = _NONCANONICAL_CAMERA_MODIFIER.search(tail)
            if modifier is not None and modifier.start() <= 80:
                return True
    return False


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    return value


__all__ = [
    "H3IssueSeverity",
    "H3ProtocolIssue",
    "H3ProtocolMode",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "UPSTREAM_BLOBS",
    "UPSTREAM_COMMIT",
    "compile_camera_draft",
    "compile_camera_motion",
    "compile_camera_placeholders",
    "compile_dialogue_tag",
    "compile_media_label",
    "compile_shot_heading",
    "lint_h3_prompt",
    "normalize_dialogue_language_tags",
    "parse_camera_directives",
]
