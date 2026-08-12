"""Deterministic final-document compiler for three-shot Direct Ref2V."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
import json
import re

from panelforge.domain import H3CameraDirective

from .minimax_h3_protocol import (
    compile_camera_motion,
    compile_camera_placeholders,
    compile_shot_heading,
    parse_camera_directives,
)
from .revised_documents import RevisedDocumentContract


MULTISHOT_EDITABLE_FIELDS = (
    "scene_setup",
    "shot_1",
    "shot_2",
    "shot_3",
    "overall_soundscape",
    "non_diegetic_music",
)
MULTISHOT_EDITABLE_CONTRACT = RevisedDocumentContract(
    "direct Ref2V multi-shot editable document",
    tuple(f"{field}:" for field in MULTISHOT_EDITABLE_FIELDS),
)

_CONTEXT_MARKER = "__PANELFORGE_DIRECT_REF2V_MULTISHOT_CONTEXT_V1__:"
_CONTEXT_FIELDS = {
    "version",
    "header",
    "camera_directives",
    "directive_shots",
    "shot_starts_ms",
    "final_state_start_ms",
    "duration_ms",
}
_PLACEHOLDER = re.compile(r"\[\[camera:(camera_\d+)\]\]")
_PICTURE_LABEL = re.compile(r"<Picture\s+\d+>")
_LEGACY_LABEL = re.compile(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>")
_ANY_TIMESTAMP = re.compile(r"\bAt\s+\d{2}:\d{2}\.\d{3}\b")
_EXACT_TIMESTAMP = re.compile(r"\bAt\s+\d{2}:\d{2}\.\d{3},")
_ANY_SHOT_HEADING = re.compile(r"(?m)^\[Shot\s+\d+\](?:\s+At\s+[^\r\n,]+,)?")


@dataclass(frozen=True, slots=True)
class DirectRef2VMultiShotCompilerContext:
    """Immutable inputs owned by the three-shot application compiler."""

    header: str
    directives: tuple[H3CameraDirective, ...]
    directive_shots: tuple[tuple[str, int], ...]
    shot_starts_ms: tuple[int, int, int]
    final_state_start_ms: int
    duration_ms: int

    def shot_for(self, directive_id: str) -> int:
        try:
            return dict(self.directive_shots)[directive_id]
        except KeyError as error:
            raise ValueError(
                f"multi-shot camera directive has no shot: {directive_id}"
            ) from error

    def directives_for(self, shot_number: int) -> tuple[H3CameraDirective, ...]:
        return tuple(
            directive
            for directive in self.directives
            if self.shot_for(directive.directive_id) == shot_number
        )


def encode_direct_ref2v_multishot_context(
    header: str,
    directives: tuple[H3CameraDirective, ...],
    directive_shots: Mapping[str, int] | tuple[tuple[str, int], ...],
    shot_starts_ms: tuple[int, int, int],
    final_state_start_ms: int,
    duration_ms: int,
) -> str:
    """Serialize and validate the distinct V1 three-shot compiler context."""

    context = _validated_context(
        header=header,
        directives=directives,
        directive_shots=directive_shots,
        shot_starts_ms=shot_starts_ms,
        final_state_start_ms=final_state_start_ms,
        duration_ms=duration_ms,
    )
    payload = {
        "version": 1,
        "header": context.header,
        "camera_directives": [_directive_payload(item) for item in context.directives],
        "directive_shots": dict(context.directive_shots),
        "shot_starts_ms": list(context.shot_starts_ms),
        "final_state_start_ms": context.final_state_start_ms,
        "duration_ms": context.duration_ms,
    }
    return _CONTEXT_MARKER + json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def is_direct_ref2v_multishot_context(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_CONTEXT_MARKER)


def decode_direct_ref2v_multishot_context(
    value: str,
) -> DirectRef2VMultiShotCompilerContext:
    """Decode one V1 context and reject mono-shot or foreign contexts."""

    if not is_direct_ref2v_multishot_context(value):
        raise ValueError("direct Ref2V multi-shot compiler context is missing")
    try:
        payload = json.loads(value[len(_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError(
            "direct Ref2V multi-shot compiler context is invalid"
        ) from error
    if not isinstance(payload, dict) or set(payload) != _CONTEXT_FIELDS:
        raise ValueError("direct Ref2V multi-shot compiler context has invalid fields")
    if payload["version"] != 1:
        raise ValueError("unsupported direct Ref2V multi-shot context version")
    raw_directives = payload["camera_directives"]
    if not isinstance(raw_directives, list):
        raise ValueError("multi-shot camera_directives must be an array")
    directives = (
        ()
        if raw_directives == []
        else parse_camera_directives(raw_directives)
    )
    return _validated_context(
        header=payload["header"],
        directives=directives,
        directive_shots=payload["directive_shots"],
        shot_starts_ms=payload["shot_starts_ms"],
        final_state_start_ms=payload["final_state_start_ms"],
        duration_ms=payload["duration_ms"],
    )


def normalize_direct_ref2v_multishot_camera_placeholders(content: str) -> str:
    """Recover only harmless placeholder punctuation and field-line layouts."""

    value = _strip_fence(content).replace("\r\n", "\n")
    placeholder = r"\[\[camera:camera_\d+\]\]"
    value = re.sub(rf"({placeholder})\.(?=\s|$)", r"\1", value)
    value = re.sub(
        rf"(?m)^(shot_[123]:)[ \t]+({placeholder})(?=\s|$)",
        r"\1\n\2",
        value,
    )
    return value


def compile_direct_ref2v_multishot_document(
    writer_content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContext,
) -> str:
    """Compile the six writer fields into the exact three-shot H3 document."""

    context = _context(compiler_context)
    normalized = normalize_direct_ref2v_multishot_camera_placeholders(writer_content)
    editable = MULTISHOT_EDITABLE_CONTRACT.extract(normalized)
    fields = _extract_editable_fields(editable)
    _validate_writer_fields(fields, context)

    compiled_shots: list[str] = []
    for shot_number in range(1, 4):
        shot = fields[f"shot_{shot_number}"]
        directives = context.directives_for(shot_number)
        compiled_shots.append(
            compile_camera_placeholders(shot, directives, require_all=True)
        )

    headings = (
        compile_shot_heading(1),
        compile_shot_heading(2, context.shot_starts_ms[1]),
        compile_shot_heading(3, context.shot_starts_ms[2]),
    )
    content = (
        f"{context.header}\n\n"
        f"{fields['scene_setup']}\n\n"
        f"{headings[0]} {compiled_shots[0]}\n\n"
        f"{headings[1]} {compiled_shots[1]}\n\n"
        f"{headings[2]} {compiled_shots[2]}\n\n"
        f"overall_soundscape:\n{fields['overall_soundscape']}\n\n"
        f"non_diegetic_music:\n{fields['non_diegetic_music']}"
    )
    errors = lint_direct_ref2v_multishot_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def lint_direct_ref2v_multishot_prompt(
    content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContext | None = None,
) -> tuple[str, ...]:
    """Validate the compiled document, with exact ownership when context is known."""

    try:
        value = _strip_fence(content).replace("\r\n", "\n")
    except (TypeError, ValueError) as error:
        return (str(error),)

    structural_errors = list(_lint_compiled_structure(value))
    if compiler_context is None:
        return tuple(structural_errors)

    try:
        context = _context(compiler_context)
        parts = _split_compiled_document(value, context)
    except (TypeError, ValueError) as error:
        structural_errors.append(str(error))
        return tuple(dict.fromkeys(structural_errors))

    errors = structural_errors
    body_without_header = value[
        len(context.header + "\n\n") :
    ]

    expected_timestamps = (
        _timestamp_text(context.shot_starts_ms[1]),
        _timestamp_text(context.shot_starts_ms[2]),
    )
    actual_timestamps = tuple(_EXACT_TIMESTAMP.findall(body_without_header))
    if actual_timestamps != expected_timestamps:
        errors.append(
            "Compiled multi-shot cut timestamps must match the two derived shot starts."
        )

    all_clauses = {
        compile_camera_motion(directive) for directive in context.directives
    }
    for shot_number in range(1, 4):
        shot_body = parts[f"shot_{shot_number}"]
        shot_directives = context.directives_for(shot_number)
        expected_clauses = Counter(
            compile_camera_motion(directive)
            for directive in shot_directives
        )
        for clause in all_clauses:
            actual_count = shot_body.count(clause)
            expected_count = expected_clauses[clause]
            if actual_count != expected_count:
                errors.append(
                    "Compiled camera clause occurrence count does not match "
                    f"Shot {shot_number} ownership."
                )
        if shot_directives:
            opening_clause = compile_camera_motion(shot_directives[0])
            if not shot_body.lstrip().startswith(opening_clause):
                errors.append(
                    f"Compiled camera clause must begin Shot {shot_number}."
                )
    return tuple(dict.fromkeys(errors))


def rehydrate_direct_ref2v_multishot_editable_document(
    content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContext | None,
) -> str:
    """Recover the six-field writer envelope for manual edit or LLM revision."""

    if compiler_context is None:
        raise ValueError("direct Ref2V multi-shot revision is missing compiler context")
    context = _context(compiler_context)
    errors = lint_direct_ref2v_multishot_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    parts = _split_compiled_document(content, context)

    for shot_number in range(1, 4):
        field = f"shot_{shot_number}"
        shot = parts[field]
        for directive in context.directives_for(shot_number):
            clause = compile_camera_motion(directive)
            if shot.count(clause) != 1:
                raise ValueError(
                    f"compiled camera {directive.directive_id} does not match Shot {shot_number}"
                )
            shot = shot.replace(
                clause,
                f"[[camera:{directive.directive_id}]]",
                1,
            )
        parts[field] = shot

    return "\n\n".join(
        f"{field}:\n{parts[field]}" for field in MULTISHOT_EDITABLE_FIELDS
    )


def _validated_context(
    *,
    header: object,
    directives: object,
    directive_shots: object,
    shot_starts_ms: object,
    final_state_start_ms: object,
    duration_ms: object,
) -> DirectRef2VMultiShotCompilerContext:
    if not isinstance(header, str) or not header.strip():
        raise ValueError("direct Ref2V multi-shot compiler header is empty")
    normalized_header = header.strip().replace("\r\n", "\n")
    if "\n\n" in normalized_header:
        raise ValueError("direct Ref2V multi-shot compiler header contains an empty line")
    if not isinstance(directives, tuple) or any(
        not isinstance(item, H3CameraDirective) for item in directives
    ):
        raise TypeError("directives must be a tuple of H3CameraDirective values")
    directive_ids = tuple(item.directive_id for item in directives)
    if len(directive_ids) != len(set(directive_ids)):
        raise ValueError("multi-shot camera directive IDs must be unique")

    if isinstance(directive_shots, Mapping):
        raw_shots = tuple(directive_shots.items())
    elif isinstance(directive_shots, (tuple, list)):
        raw_shots = tuple(directive_shots)
    else:
        raise TypeError("directive_shots must map camera IDs to shot numbers")
    normalized_shots: list[tuple[str, int]] = []
    for item in raw_shots:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("directive_shots entries must contain an ID and shot")
        directive_id, shot_number = item
        if not isinstance(directive_id, str):
            raise TypeError("directive shot IDs must be strings")
        if isinstance(shot_number, bool) or not isinstance(shot_number, int):
            raise TypeError("directive shot numbers must be integers")
        if shot_number not in {1, 2, 3}:
            raise ValueError("directive shot numbers must be between 1 and 3")
        if directive_id != f"camera_{shot_number}":
            raise ValueError(
                "multi-shot camera IDs must match their owning shot number"
            )
        normalized_shots.append((directive_id, shot_number))
    if len({key for key, _ in normalized_shots}) != len(normalized_shots):
        raise ValueError("directive_shots must not contain duplicate IDs")
    if set(directive_ids) != {key for key, _ in normalized_shots}:
        raise ValueError("directive_shots must associate every camera directive once")

    if not isinstance(shot_starts_ms, (tuple, list)) or len(shot_starts_ms) != 3:
        raise ValueError("shot_starts_ms must contain exactly three values")
    starts = tuple(shot_starts_ms)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in starts):
        raise TypeError("shot_starts_ms must contain integers")
    if starts[0] != 0 or not (starts[0] < starts[1] < starts[2]):
        raise ValueError("shot_starts_ms must begin at zero and increase strictly")
    if (
        isinstance(final_state_start_ms, bool)
        or not isinstance(final_state_start_ms, int)
        or final_state_start_ms <= starts[2]
    ):
        raise ValueError("final_state_start_ms must follow the start of Shot 3")
    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, int)
        or duration_ms < final_state_start_ms
    ):
        raise ValueError("duration_ms must not precede the final state")
    return DirectRef2VMultiShotCompilerContext(
        header=normalized_header,
        directives=directives,
        directive_shots=tuple(sorted(normalized_shots, key=lambda item: item[1])),
        shot_starts_ms=starts,
        final_state_start_ms=final_state_start_ms,
        duration_ms=duration_ms,
    )


def _context(
    value: str | DirectRef2VMultiShotCompilerContext,
) -> DirectRef2VMultiShotCompilerContext:
    if isinstance(value, DirectRef2VMultiShotCompilerContext):
        return _validated_context(
            header=value.header,
            directives=value.directives,
            directive_shots=value.directive_shots,
            shot_starts_ms=value.shot_starts_ms,
            final_state_start_ms=value.final_state_start_ms,
            duration_ms=value.duration_ms,
        )
    return decode_direct_ref2v_multishot_context(value)


def _directive_payload(directive: H3CameraDirective) -> dict[str, str]:
    payload = {"id": directive.directive_id, "motion": directive.motion.value}
    if directive.amplitude is not None:
        payload["amplitude"] = directive.amplitude.value
    if directive.speed is not None:
        payload["speed"] = directive.speed.value
    if directive.target_clause:
        payload["target_clause"] = directive.target_clause
    return payload


def _extract_editable_fields(content: str) -> dict[str, str]:
    markers = [
        re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content)
        for field in MULTISHOT_EDITABLE_FIELDS
    ]
    if any(marker is None for marker in markers):
        raise ValueError("direct Ref2V multi-shot writer fields are incomplete")
    fields: dict[str, str] = {}
    for index, field in enumerate(MULTISHOT_EDITABLE_FIELDS):
        marker = markers[index]
        assert marker is not None
        end = markers[index + 1].start() if index + 1 < len(markers) else len(content)
        value = content[marker.end() : end].strip()
        if not value:
            raise ValueError(f"direct Ref2V multi-shot field {field}: is empty")
        fields[field] = value
    return fields


def _validate_writer_fields(
    fields: Mapping[str, str],
    context: DirectRef2VMultiShotCompilerContext,
) -> None:
    combined = "\n".join(fields.values())
    if _PICTURE_LABEL.search(combined) or _LEGACY_LABEL.search(combined):
        raise ValueError("multi-shot writer fields must not contain reference labels")
    if _ANY_SHOT_HEADING.search(combined):
        raise ValueError("multi-shot writer fields must not contain compiled shot headings")
    if _ANY_TIMESTAMP.search(combined):
        raise ValueError("multi-shot writer fields must not contain compiled timestamps")
    if "<scenetrans>" in combined:
        raise ValueError("direct Ref2V three-shot prompts must not use <scenetrans>")
    occurrences = _PLACEHOLDER.findall(combined)
    expected = {directive.directive_id for directive in context.directives}
    if set(occurrences) - expected:
        unknown = ", ".join(sorted(set(occurrences) - expected))
        raise ValueError(f"unknown multi-shot camera placeholder(s): {unknown}")
    for directive in context.directives:
        if occurrences.count(directive.directive_id) != 1:
            raise ValueError(
                f"camera placeholder {directive.directive_id} must appear exactly once"
            )
        owner = context.shot_for(directive.directive_id)
        placeholder = f"[[camera:{directive.directive_id}]]"
        owner_body = fields[f"shot_{owner}"]
        if placeholder not in owner_body:
            raise ValueError(
                f"camera placeholder {directive.directive_id} must remain in Shot {owner}"
            )
        if not owner_body.lstrip().startswith(placeholder):
            raise ValueError(
                f"camera placeholder {directive.directive_id} must begin Shot {owner}"
            )
    if "[[" in combined or "]]" in combined:
        placeholder_free = _PLACEHOLDER.sub("", combined)
        if "[[" in placeholder_free or "]]" in placeholder_free:
            raise ValueError("unresolved or malformed compiler placeholder")


def _lint_compiled_structure(content: str) -> tuple[str, ...]:
    """Lint invariants that do not require hidden compiler ownership data."""

    errors: list[str] = []
    if _LEGACY_LABEL.search(content):
        errors.append(
            "The compiled multi-shot prompt must use only canonical <Picture N> labels."
        )
    if "<scenetrans>" in content:
        errors.append("Direct Ref2V three-shot prompts must not use <scenetrans>.")
    if "[[" in content or "]]" in content:
        errors.append("An unresolved or malformed compiler placeholder remains.")
    for field in MULTISHOT_EDITABLE_FIELDS[:4]:
        if re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content):
            errors.append(f"The internal field {field}: must not remain compiled.")

    raw_headings = list(re.finditer(r"(?m)^\[Shot\s+([^\]]+)\]", content))
    if len(raw_headings) != 3:
        errors.append("The compiled multi-shot prompt must contain exactly three shots.")
        return tuple(dict.fromkeys(errors))
    if tuple(match.group(1) for match in raw_headings) != ("1", "2", "3"):
        errors.append("Compiled shots must appear exactly in the order 1, 2, 3.")

    exact_patterns = (
        re.compile(r"(?m)^\[Shot 1\](?![ \t]+At\b)(?=\s|$)"),
        re.compile(r"(?m)^\[Shot 2\] At (\d{2}):(\d{2})\.(\d{3}),(?=\s|$)"),
        re.compile(r"(?m)^\[Shot 3\] At (\d{2}):(\d{2})\.(\d{3}),(?=\s|$)"),
    )
    exact_matches = [list(pattern.finditer(content)) for pattern in exact_patterns]
    if len(exact_matches[0]) != 1:
        errors.append("[Shot 1] must appear exactly once without a timestamp.")
    later_times: list[int] = []
    for shot_number, matches in enumerate(exact_matches[1:], 2):
        if len(matches) != 1:
            errors.append(
                f"[Shot {shot_number}] must begin with one exact At MM:SS.mmm, timestamp."
            )
            continue
        minutes, seconds, milliseconds = (
            int(value) for value in matches[0].groups()
        )
        if seconds >= 60:
            errors.append(f"[Shot {shot_number}] has an invalid timestamp.")
            continue
        later_times.append(minutes * 60_000 + seconds * 1_000 + milliseconds)
    if len(later_times) == 2 and not later_times[0] < later_times[1]:
        errors.append("Shot 2 and Shot 3 timestamps must increase strictly.")
    timestamps = _ANY_TIMESTAMP.findall(content)
    if len(timestamps) != 2:
        errors.append(
            "The compiled multi-shot prompt must contain only its two cut timestamps."
        )

    first_heading_start = raw_headings[0].start()
    opening = content[:first_heading_start].strip()
    opening_parts = opening.split("\n\n", 1)
    if len(opening_parts) != 2 or not all(part.strip() for part in opening_parts):
        errors.append(
            "The compiled multi-shot prompt requires a non-empty header and scene setup."
        )
        header = opening
    else:
        header = opening_parts[0]
    picture_numbers = sorted(
        {int(number) for number in re.findall(r"<Picture\s+(\d+)>", content)}
    )
    if (
        not picture_numbers
        or len(picture_numbers) > 3
        or picture_numbers != list(range(1, len(picture_numbers) + 1))
    ):
        errors.append("Picture labels must be contiguous from 1 to at most 3.")
    for number in picture_numbers:
        label = f"<Picture {number}>"
        if content.count(label) != 1 or label not in header:
            errors.append(
                f"{label} must appear exactly once in the compiled reference header."
            )

    audio_matches = {
        field: list(re.finditer(rf"(?m)^{re.escape(field)}:[ \t]*", content))
        for field in ("overall_soundscape", "non_diegetic_music")
    }
    for field, matches in audio_matches.items():
        if len(matches) != 1:
            errors.append(f"The compiled field {field}: must appear exactly once.")
    overall = audio_matches["overall_soundscape"]
    music = audio_matches["non_diegetic_music"]
    if len(overall) == len(music) == 1:
        if not raw_headings[2].start() < overall[0].start() < music[0].start():
            errors.append("Compiled multi-shot audio fields are out of order.")
        soundscape = content[overall[0].end() : music[0].start()].strip()
        score = content[music[0].end() :].strip()
        if not soundscape:
            errors.append("overall_soundscape must not be empty.")
        if not score:
            errors.append("non_diegetic_music must not be empty; use N/A.")

    return tuple(dict.fromkeys(errors))


def _split_compiled_document(
    content: str,
    context: DirectRef2VMultiShotCompilerContext,
) -> dict[str, str]:
    value = _strip_fence(content).replace("\r\n", "\n")
    prefix = context.header + "\n\n"
    if not value.startswith(prefix):
        raise ValueError("direct Ref2V multi-shot prompt is missing its compiled mapping")
    body = value[len(prefix) :]
    headings = (
        compile_shot_heading(1),
        compile_shot_heading(2, context.shot_starts_ms[1]),
        compile_shot_heading(3, context.shot_starts_ms[2]),
    )
    matches: list[re.Match[str]] = []
    for heading in headings:
        found = list(re.finditer(rf"(?m)^{re.escape(heading)}(?=\s|$)", body))
        if len(found) != 1:
            raise ValueError(
                f"compiled multi-shot heading must appear exactly once: {heading}"
            )
        matches.append(found[0])
    if [item.start() for item in matches] != sorted(item.start() for item in matches):
        raise ValueError("compiled multi-shot headings are out of order")
    all_headings = list(_ANY_SHOT_HEADING.finditer(body))
    if len(all_headings) != 3 or {
        match.group(0) for match in all_headings
    } != set(headings):
        raise ValueError("compiled multi-shot document has an unexpected shot heading")

    overall = list(re.finditer(r"(?m)^overall_soundscape:[ \t]*", body))
    music = list(re.finditer(r"(?m)^non_diegetic_music:[ \t]*", body))
    if len(overall) != 1 or len(music) != 1:
        raise ValueError("compiled multi-shot audio fields must appear exactly once")
    if not (matches[2].start() < overall[0].start() < music[0].start()):
        raise ValueError("compiled multi-shot audio fields are out of order")

    scene = body[: matches[0].start()].strip()
    shot_1 = body[matches[0].end() : matches[1].start()].strip()
    shot_2 = body[matches[1].end() : matches[2].start()].strip()
    shot_3 = body[matches[2].end() : overall[0].start()].strip()
    soundscape = body[overall[0].end() : music[0].start()].strip()
    non_diegetic_music = body[music[0].end() :].strip()
    result = {
        "scene_setup": scene,
        "shot_1": shot_1,
        "shot_2": shot_2,
        "shot_3": shot_3,
        "overall_soundscape": soundscape,
        "non_diegetic_music": non_diegetic_music,
    }
    for field, value in result.items():
        if not value:
            raise ValueError(f"compiled multi-shot field {field} is empty")
    return result


def _timestamp_text(timestamp_ms: int) -> str:
    return compile_shot_heading(2, timestamp_ms).split("] ", 1)[1]


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    if not value:
        raise ValueError("direct Ref2V multi-shot document must not be empty")
    return value


__all__ = [
    "DirectRef2VMultiShotCompilerContext",
    "MULTISHOT_EDITABLE_CONTRACT",
    "MULTISHOT_EDITABLE_FIELDS",
    "compile_direct_ref2v_multishot_document",
    "decode_direct_ref2v_multishot_context",
    "encode_direct_ref2v_multishot_context",
    "is_direct_ref2v_multishot_context",
    "lint_direct_ref2v_multishot_prompt",
    "normalize_direct_ref2v_multishot_camera_placeholders",
    "rehydrate_direct_ref2v_multishot_editable_document",
]
