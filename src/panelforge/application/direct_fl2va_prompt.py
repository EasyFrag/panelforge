"""Deterministic envelope for the four H3-Base-FL2VA input modes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
import re

from panelforge.domain import PromptLabSession

from .direct_i2v_prompt import (
    I2VA_FIELDS,
    insert_camera_owned_direct_i2v_clauses,
    rehydrate_camera_owned_direct_i2v_document,
)
from .minimax_h3_protocol import (
    H3IssueSeverity,
    H3ProtocolMode,
    lint_h3_prompt,
)
from .timed_camera_compiler import TimedCameraPlacement


FL2VA_CONTEXT_MARKER = "__PANELFORGE_FL2VA_CONTEXT_V1__:"

_DURATION_NUMBER = r"\d{1,3}(?:[.,]\d{1,3})?"
_DURATION_UNIT = r"(?:s(?:ec(?:onde)?s?)?|secondes?|seconds?)"
_EXPLICIT_TOTAL_DURATION_RE = re.compile(
    rf"(?:"
    rf"\b(?:dur[ée]e|duration)\s*(?:totale?|total)?\s*"
    rf"(?:[:=]|\b(?:de|of|est|is)\b)?\s*"
    rf"(?P<label>{_DURATION_NUMBER})\s*-?\s*{_DURATION_UNIT}(?!\w)"
    rf"|"
    rf"\b(?:plan|clip|animation|vid[ée]o|video)\b"
    rf"[^\n.!?;:]{{0,48}}?\b(?:de|for)\s*"
    rf"(?P<plan>{_DURATION_NUMBER})\s*-?\s*{_DURATION_UNIT}(?!\w)"
    rf")",
    flags=re.IGNORECASE,
)
_ANY_DURATION_RE = re.compile(
    rf"(?<![\w.])(?P<value>{_DURATION_NUMBER})\s*-?\s*"
    rf"{_DURATION_UNIT}(?!\w)",
    flags=re.IGNORECASE,
)


class H3BaseInputMode(StrEnum):
    T2VA = "t2va"
    I2VA = "i2va"
    L2VA = "l2va"
    FL2VA = "fl2va"


@dataclass(frozen=True, slots=True)
class DirectFL2VAContext:
    mode: H3BaseInputMode
    header: str
    duration_ms: int
    placements: tuple[TimedCameraPlacement, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mode, H3BaseInputMode):
            raise TypeError("H3 Base mode must be an H3BaseInputMode")
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
            raise TypeError("H3 Base duration_ms must be an integer")
        if self.duration_ms <= 0:
            raise ValueError("H3 Base duration_ms must be positive")
        expected = compile_h3_base_header(self.mode, self.duration_ms)
        if self.header != expected:
            raise ValueError("H3 Base compiler header does not match its input mode")
        starts = [item.start_ms for item in self.placements]
        if starts != sorted(starts) or len(starts) != len(set(starts)):
            raise ValueError("H3 Base camera placements must be distinct and chronological")

    @property
    def protocol_mode(self) -> H3ProtocolMode:
        return H3ProtocolMode(self.mode.value)


def derive_h3_base_input_mode(
    session: PromptLabSession,
    mapping: tuple[tuple[str, int], ...],
) -> H3BaseInputMode:
    roles = [session.reference(reference_id).role for reference_id, _ in mapping]
    if any(role not in {"first_frame", "last_frame"} for role in roles):
        raise ValueError("H3 Base accepts only first_frame and last_frame bindings")
    if len(roles) != len(set(roles)):
        raise ValueError("H3 Base accepts at most one frame of each kind")
    if roles == []:
        return H3BaseInputMode.T2VA
    if roles == ["first_frame"]:
        return H3BaseInputMode.I2VA
    if roles == ["last_frame"]:
        return H3BaseInputMode.L2VA
    if roles == ["first_frame", "last_frame"]:
        return H3BaseInputMode.FL2VA
    raise ValueError("H3 Base frame bindings must keep first frame before last frame")


def compile_h3_base_header(mode: H3BaseInputMode, duration_ms: int) -> str:
    if not isinstance(mode, H3BaseInputMode):
        raise TypeError("mode must be an H3BaseInputMode")
    seconds = f"{duration_ms / 1000:.2f}"
    if mode is H3BaseInputMode.T2VA:
        return ""
    if mode is H3BaseInputMode.I2VA:
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    if mode is H3BaseInputMode.L2VA:
        return (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot 1]) aligns with the {seconds}-second "
            "mark of the target video."
        )
    return (
        "How the reference pictures align with the target video — Picture 1 "
        "(from Shot 1) aligns with the 0.00-second mark of the target video; "
        f"Picture 2 (from Shot 1) aligns with the {seconds}-second mark of the "
        "target video."
    )


def requested_h3_base_duration_ms(source_text: str) -> int | None:
    """Extract one unambiguous duration explicitly written by the user."""

    if not isinstance(source_text, str):
        raise TypeError("H3 Base source_text must be text")
    # Prefer explicit total-duration clauses over incidental durations found in
    # pasted former prompts or counterexamples. For example, a current
    # instruction ``plan de 12 secondes`` remains authoritative even if a
    # quoted rejected output later says ``one continuous 13-second shot``.
    explicit_matches = [
        match.group("label") or match.group("plan")
        for match in _EXPLICIT_TOTAL_DURATION_RE.finditer(source_text)
    ]
    matches = explicit_matches or [
        match.group("value") for match in _ANY_DURATION_RE.finditer(source_text)
    ]
    durations: set[int] = set()
    for raw in matches:
        try:
            milliseconds = int(
                (Decimal(raw.replace(",", ".")) * Decimal(1000)).to_integral_value()
            )
        except InvalidOperation as error:
            raise ValueError("H3 Base duration is invalid") from error
        # Ignore frame-origin timestamps such as "at 0.00 seconds"; they are
        # anchors, not a requested total duration.
        if milliseconds == 0:
            continue
        if milliseconds < 0:
            raise ValueError("H3 Base duration must be positive")
        durations.add(milliseconds)
    if not durations:
        return None
    if len(durations) > 1:
        raise ValueError("H3 Base intention contains conflicting explicit durations")
    return durations.pop()


def direct_h3_base_reference_mapping(
    session: PromptLabSession,
    mapping: tuple[tuple[str, int], ...],
) -> str:
    mode = derive_h3_base_input_mode(session, mapping)
    if mode is H3BaseInputMode.T2VA:
        return "MODE: T2VA. No input image is attached; generate the full visible scene from text."
    session_numbers = {
        reference.reference_id: index
        for index, reference in enumerate(session.references, 1)
    }
    chunks = [f"MODE: {mode.value.upper()}."]
    for reference_id, picture_number in mapping:
        reference = session.reference(reference_id)
        anchor = (
            "exact visible frame at 0.00 seconds"
            if reference.role == "first_frame"
            else "exact visible frame at the final instant"
        )
        chunks.extend(
            (
                f"<Picture {picture_number}> = <Image {session_numbers[reference_id]}>",
                f"role: {reference.role}",
                f"ownership: {anchor}; preserve all visible state owned by this anchor",
            )
        )
    return "\n".join(chunks)


def encode_direct_fl2va_context(context: DirectFL2VAContext) -> str:
    from .timed_camera_compiler import encode_timed_camera_context, TimedCameraContext

    camera = encode_timed_camera_context(
        TimedCameraContext(mode="i2v", placements=context.placements)
    )
    return FL2VA_CONTEXT_MARKER + json.dumps(
        {
            "mode": context.mode.value,
            "header": context.header,
            "duration_ms": context.duration_ms,
            "camera": camera,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def decode_direct_fl2va_context(value: str) -> DirectFL2VAContext:
    from .timed_camera_compiler import decode_timed_camera_context

    if not isinstance(value, str) or not value.startswith(FL2VA_CONTEXT_MARKER):
        raise ValueError("H3 Base compiler context is missing")
    try:
        payload = json.loads(value[len(FL2VA_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError("H3 Base compiler context is invalid") from error
    if not isinstance(payload, dict) or set(payload) != {
        "mode", "header", "duration_ms", "camera"
    }:
        raise ValueError("H3 Base compiler context has invalid fields")
    camera = decode_timed_camera_context(payload["camera"])
    if camera.mode != "i2v" or camera.header is not None:
        raise ValueError("H3 Base compiler context has an invalid camera envelope")
    return DirectFL2VAContext(
        mode=H3BaseInputMode(payload["mode"]),
        header=payload["header"],
        duration_ms=payload["duration_ms"],
        placements=camera.placements,
    )


def compile_direct_fl2va_document(
    editable: str,
    context: DirectFL2VAContext,
) -> str:
    body = insert_camera_owned_direct_i2v_clauses(
        editable,
        context.placements,
        contract_name="H3 Base",
    )
    content = f"{context.header}\n\n{body}" if context.header else body
    errors = lint_direct_fl2va_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def rehydrate_direct_fl2va_document(
    content: str,
    context: DirectFL2VAContext,
) -> str:
    value = content.strip().replace("\r\n", "\n")
    if context.header:
        prefix = context.header + "\n\n"
        if not value.startswith(prefix):
            raise ValueError("H3 Base prompt is missing its compiled mode header")
        value = value[len(prefix) :]
    return rehydrate_camera_owned_direct_i2v_document(
        (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced.\n\n" + value
        ),
        context.placements,
        contract_name="H3 Base",
    )


def lint_direct_fl2va_prompt(
    content: str,
    context: DirectFL2VAContext,
) -> tuple[str, ...]:
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt H3 Base est vide.",)
    value = content.strip().replace("\r\n", "\n")
    body = value
    if context.header:
        prefix = context.header + "\n\n"
        if not value.startswith(prefix):
            return ("Le header H3 Base ne correspond pas aux frames sélectionnées.",)
        body = value[len(prefix) :]
    elif value.startswith("How the reference pictures align") or value.startswith(
        "For the target video,"
    ):
        return ("Le mode T2VA ne doit pas contenir de header image.",)

    errors: list[str] = []
    positions: list[int] = []
    matches: dict[str, re.Match[str]] = {}
    for field in I2VA_FIELDS:
        found = list(re.finditer(rf"(?m)^{re.escape(field)}:[ \t]*", body))
        if len(found) != 1:
            errors.append(f"Le champ {field}: doit apparaître exactement une fois.")
        else:
            matches[field] = found[0]
            positions.append(found[0].start())
    if len(positions) == len(I2VA_FIELDS) and positions != sorted(positions):
        errors.append("Les trois champs H3 Base ne sont pas dans l'ordre officiel.")
    if len(matches) == len(I2VA_FIELDS):
        integrated = body[
            matches[I2VA_FIELDS[0]].end() : matches[I2VA_FIELDS[1]].start()
        ].strip()
        soundscape = body[
            matches[I2VA_FIELDS[1]].end() : matches[I2VA_FIELDS[2]].start()
        ].strip()
        music = body[matches[I2VA_FIELDS[2]].end() :].strip()
        if not integrated.startswith("[Shot 1]"):
            errors.append("La description H3 Base doit commencer par [Shot 1].")
        if "[Shot 2]" in integrated:
            errors.append("Cette recette H3 Base compacte est mono-plan.")
        if not soundscape:
            errors.append("overall_soundscape ne doit pas être vide.")
        if not music:
            errors.append("non_diegetic_music ne doit pas être vide.")
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>", value):
        errors.append("Le prompt final H3 Base contient un label visuel non autorisé.")
    if re.search(r"(?i)<Picture\s+\d+>", body):
        errors.append("Les labels Picture appartiennent uniquement au header compilé.")
    expected_directives = tuple(item.directive for item in context.placements)
    errors.extend(
        issue.message
        for issue in lint_h3_prompt(
            context.protocol_mode,
            value,
            expected_directives=expected_directives,
        )
        if issue.severity is H3IssueSeverity.ERROR
    )
    return tuple(dict.fromkeys(errors))


__all__ = [
    "DirectFL2VAContext",
    "FL2VA_CONTEXT_MARKER",
    "H3BaseInputMode",
    "compile_direct_fl2va_document",
    "compile_h3_base_header",
    "decode_direct_fl2va_context",
    "derive_h3_base_input_mode",
    "direct_h3_base_reference_mapping",
    "encode_direct_fl2va_context",
    "lint_direct_fl2va_prompt",
    "requested_h3_base_duration_ms",
    "rehydrate_direct_fl2va_document",
]
