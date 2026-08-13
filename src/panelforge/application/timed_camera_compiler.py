"""Deterministic placement of plan-owned H3 camera clauses.

Camera-owned Direct cookbooks deliberately keep camera wording out of the prose
writer.  This module stores the typed directive together with its approved
start time, inserts the canonical H3 sentence, and removes it again for a later
writer revision.  Historical placeholder-based cookbooks do not use it.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from panelforge.domain import H3CameraDirective, H3CameraMotion

from .minimax_h3_protocol import compile_camera_motion, parse_camera_directives


TIMED_CAMERA_CONTEXT_MARKER = "__PANELFORGE_TIMED_CAMERA_CONTEXT_V1__:"
_PLACEHOLDER = re.compile(r"\[\[\s*camera\s*:", re.IGNORECASE)
_DYNAMIC_CAMERA_SUBJECT = re.compile(
    r"(?i)\b(?:the\s+)?(?:camera|lens)\s+"
    r"(?:(?:now|slowly|quickly|gradually|subtly|gently|steadily)\s+){0,2}"
    r"(?:initiates?|begins?|starts?|executes?|performs?|moves?|zooms?|pushes?|"
    r"pulls?|pans?|tilts?|tracks?|orbits?|doll(?:y|ies)|cranes?|drifts?|"
    r"tightens?|widens?)\b|"
    r"\b(?:the\s+)?(?:shot|framing)\s+"
    r"(?:(?:now|slowly|quickly|gradually|subtly|gently|steadily)\s+){0,2}"
    r"(?:moves?|zooms?|pushes?|pulls?|pans?|tilts?|tracks?|orbits?|"
    r"doll(?:y|ies)|cranes?|drifts?|tightens?|widens?)\b"
)
_DYNAMIC_CAMERA_NOUN = re.compile(
    r"(?i)\b(?:(?:slow|fast|subtle|gentle|small|large)\s+)?(?:push[- ]in|"
    r"pull[- ]out|zoom[- ](?:in|out)|pan\s+(?:left|right)|tilt\s+(?:up|down)|"
    r"dolly\s+(?:in|out)|arc\s+shot|tracking\s+shot|POV\s+shot)\b"
    r"[^.!?\r\n]{0,80}\b(?:begins?|starts?|initiates?|occurs?|continues?)\b"
)
_DURATION_SENTENCE = re.compile(
    r"\[Shot 1\]\s+The target video is one continuous "
    r"[^\r\n]+?-second shot\."
)
_CANONICAL_CAMERA_BASES = tuple(
    compile_camera_motion(
        H3CameraDirective(
            directive_id="camera_1",
            motion=motion,
        )
    ).removesuffix(".").casefold()
    for motion in H3CameraMotion
)


@dataclass(frozen=True, slots=True)
class TimedCameraPlacement:
    directive: H3CameraDirective
    start_ms: int

    def __post_init__(self) -> None:
        if isinstance(self.start_ms, bool) or not isinstance(self.start_ms, int):
            raise TypeError("camera start_ms must be an integer")
        if self.start_ms < 0:
            raise ValueError("camera start_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class TimedCameraContext:
    mode: str
    placements: tuple[TimedCameraPlacement, ...]
    header: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"i2v", "ref2v"}:
            raise ValueError("timed camera mode must be i2v or ref2v")
        if self.mode == "ref2v" and (
            not isinstance(self.header, str) or not self.header.strip()
        ):
            raise ValueError("timed Ref2V camera context requires a header")
        if self.mode == "i2v" and self.header is not None:
            raise ValueError("timed I2V camera context must not contain a header")
        ids = [item.directive.directive_id for item in self.placements]
        if len(ids) != len(set(ids)):
            raise ValueError("timed camera directive IDs must be unique")
        starts = [item.start_ms for item in self.placements]
        if starts != sorted(starts):
            raise ValueError("timed camera placements must be chronological")
        if len(starts) != len(set(starts)):
            raise ValueError("timed camera placements must have distinct start times")


def encode_timed_camera_context(context: TimedCameraContext) -> str:
    payload = {
        "mode": context.mode,
        "header": context.header,
        "placements": [
            {
                "start_ms": placement.start_ms,
                "directive": _directive_payload(placement.directive),
            }
            for placement in context.placements
        ],
    }
    return TIMED_CAMERA_CONTEXT_MARKER + json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def is_timed_camera_context(value: str) -> bool:
    return isinstance(value, str) and value.startswith(TIMED_CAMERA_CONTEXT_MARKER)


def decode_timed_camera_context(value: str) -> TimedCameraContext:
    if not is_timed_camera_context(value):
        raise ValueError("timed camera compiler context is missing")
    try:
        payload = json.loads(value[len(TIMED_CAMERA_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError("timed camera compiler context is invalid") from error
    if not isinstance(payload, dict) or set(payload) != {
        "mode",
        "header",
        "placements",
    }:
        raise ValueError("timed camera compiler context has invalid fields")
    raw_placements = payload["placements"]
    if not isinstance(raw_placements, list):
        raise ValueError("timed camera placements must be a list")
    placements: list[TimedCameraPlacement] = []
    for raw in raw_placements:
        if not isinstance(raw, dict) or set(raw) != {"start_ms", "directive"}:
            raise ValueError("timed camera placement has invalid fields")
        directives = parse_camera_directives(
            json.dumps([raw["directive"]], ensure_ascii=True)
        )
        placements.append(TimedCameraPlacement(directives[0], raw["start_ms"]))
    return TimedCameraContext(
        mode=payload["mode"],
        header=payload["header"],
        placements=tuple(placements),
    )


def insert_i2v_camera_clauses(
    integrated: str,
    placements: tuple[TimedCameraPlacement, ...],
) -> str:
    return _transform(integrated, placements, mode="i2v", insert=True)


def remove_i2v_camera_clauses(
    integrated: str,
    placements: tuple[TimedCameraPlacement, ...],
) -> str:
    return _transform(integrated, placements, mode="i2v", insert=False)


def insert_ref2v_camera_clauses(
    shot: str,
    placements: tuple[TimedCameraPlacement, ...],
) -> str:
    return _transform(shot, placements, mode="ref2v", insert=True)


def remove_ref2v_camera_clauses(
    shot: str,
    placements: tuple[TimedCameraPlacement, ...],
) -> str:
    return _transform(shot, placements, mode="ref2v", insert=False)


def _transform(
    content: str,
    placements: tuple[TimedCameraPlacement, ...],
    *,
    mode: str,
    insert: bool,
) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("camera-owned writer content must not be empty")
    if _PLACEHOLDER.search(content):
        raise ValueError("camera-owned writer must not output camera placeholders")
    if insert and _has_dynamic_camera_prose(content):
        raise ValueError("camera-owned writer must not output camera movement prose")
    TimedCameraContext(mode=mode, placements=placements, header=("header" if mode == "ref2v" else None))
    value = content.strip()
    edits: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for placement in placements:
        clause = compile_camera_motion(placement.directive)
        if placement.start_ms == 0:
            start, end = _zero_anchor(value, mode, clause, insert)
        else:
            start, end = _timestamp_anchor(
                value,
                placement.start_ms,
                clause,
                insert,
            )
        if insert:
            value = _capitalize_at(value, start)
        if any(not (end <= left or start >= right) for left, right in occupied):
            raise ValueError("camera placements resolve to an ambiguous shared anchor")
        occupied.append((start, end))
        edits.append((start, end, clause + " " if insert else ""))
    for start, end, replacement in sorted(edits, reverse=True):
        value = value[:start] + replacement + value[end:]
    return value.strip()


def _zero_anchor(
    content: str,
    mode: str,
    clause: str,
    insert: bool,
) -> tuple[int, int]:
    if mode == "ref2v":
        if insert:
            return 0, 0
        if not content.startswith(clause + " "):
            raise ValueError("the 0 ms camera clause is not at the start of Shot 1")
        return 0, len(clause) + 1
    matches = list(_DURATION_SENTENCE.finditer(content))
    if len(matches) != 1:
        raise ValueError("I2V camera insertion requires one opening duration sentence")
    anchor = _after_whitespace(content, matches[0].end())
    if insert:
        return anchor, anchor
    if not content.startswith(clause + " ", anchor):
        raise ValueError("the 0 ms camera clause is not after the I2V duration sentence")
    return anchor, anchor + len(clause) + 1


def _timestamp_anchor(
    content: str,
    start_ms: int,
    clause: str,
    insert: bool,
) -> tuple[int, int]:
    landmark = _format_timestamp(start_ms)
    matches = list(re.finditer(re.escape(landmark), content))
    if len(matches) != 1:
        raise ValueError(
            f"camera-owned writer requires exactly one landmark {landmark}"
        )
    anchor = _after_whitespace(content, matches[0].end())
    if insert:
        return anchor, anchor
    if not content.startswith(clause + " ", anchor):
        raise ValueError(f"camera clause is not placed at {landmark}")
    return anchor, anchor + len(clause) + 1


def _after_whitespace(content: str, index: int) -> int:
    while index < len(content) and content[index].isspace():
        index += 1
    return index


def _capitalize_at(content: str, index: int) -> str:
    """Canonicalize the prose sentence that follows an inserted camera clause."""

    if index < len(content) and "a" <= content[index] <= "z":
        return content[:index] + content[index].upper() + content[index + 1 :]
    return content


def _has_dynamic_camera_prose(content: str) -> bool:
    normalized = content.casefold()
    return bool(
        _DYNAMIC_CAMERA_SUBJECT.search(content)
        or _DYNAMIC_CAMERA_NOUN.search(content)
        or any(base in normalized for base in _CANONICAL_CAMERA_BASES)
    )


def _format_timestamp(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"At {minutes:02d}:{seconds:02d}.{millis:03d},"


def _directive_payload(directive: H3CameraDirective) -> dict[str, str]:
    payload = {"id": directive.directive_id, "motion": directive.motion.value}
    if directive.amplitude is not None:
        payload["amplitude"] = directive.amplitude.value
    if directive.speed is not None:
        payload["speed"] = directive.speed.value
    if directive.target_clause:
        payload["target_clause"] = directive.target_clause
    return payload


__all__ = [
    "TimedCameraContext",
    "TimedCameraPlacement",
    "decode_timed_camera_context",
    "encode_timed_camera_context",
    "insert_i2v_camera_clauses",
    "insert_ref2v_camera_clauses",
    "is_timed_camera_context",
    "remove_i2v_camera_clauses",
    "remove_ref2v_camera_clauses",
]
