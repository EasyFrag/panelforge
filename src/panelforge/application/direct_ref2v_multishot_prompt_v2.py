"""Camera-owned compiler for flexible Direct Ref2V multi-shot prompts.

The V2 prose writer owns only the scene, subject actions and sound fields.
Shot headings, cut timestamps and canonical H3 camera sentences remain in this
deterministic compiler context and are never exposed to a writer revision.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import re

from panelforge.domain import H3CameraDirective

from .direct_ref2v_multishot_plan_v2 import (
    parse_direct_ref2v_multishot_plan_v2,
)
from .minimax_h3_protocol import (
    compile_camera_motion,
    compile_shot_heading,
    parse_camera_directives,
)
from .revised_documents import RevisedDocumentContract
from .timed_camera_compiler import (
    TimedCameraPlacement,
    insert_ref2v_camera_clauses,
    remove_ref2v_camera_clauses,
)


_MIN_SHOTS = 2
_MAX_SHOTS = 6
_CONTEXT_MARKER = "__PANELFORGE_DIRECT_REF2V_MULTISHOT_CONTEXT_V2__:"
_CONTEXT_FIELDS = {
    "version",
    "header",
    "shot_starts_ms",
    "hard_cut_times_ms",
    "shot_cameras",
    "final_state_start_ms",
    "duration_ms",
}
_PLACEHOLDER = re.compile(r"\[\[\s*camera\s*:", re.IGNORECASE)
_PICTURE_LABEL = re.compile(r"<Picture\s+\d+>")
_LEGACY_LABEL = re.compile(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>")
_ANY_TIMESTAMP = re.compile(r"\bAt\s+\d{2}:\d{2}\.\d{3}\b")
_EXACT_TIMESTAMP = re.compile(r"\bAt\s+\d{2}:\d{2}\.\d{3},")
_ANY_SHOT_HEADING = re.compile(
    r"(?m)^\[Shot\s+\d+\](?:[ \t]+At\s+[^\r\n,]+,)?"
)
_WRITER_FIELD = re.compile(r"(?m)^([a-z][a-z0-9_]*):[ \t]*")


@dataclass(frozen=True, slots=True)
class DirectRef2VMultiShotCompilerContextV2:
    """Immutable application-owned context for two to six shots."""

    header: str
    shot_starts_ms: tuple[int, ...]
    hard_cut_times_ms: tuple[int, ...]
    shot_cameras: tuple[H3CameraDirective | None, ...]
    final_state_start_ms: int
    duration_ms: int

    @property
    def shot_count(self) -> int:
        return len(self.shot_starts_ms)

    @property
    def directives(self) -> tuple[H3CameraDirective, ...]:
        return tuple(camera for camera in self.shot_cameras if camera is not None)

    def camera_for(self, shot_number: int) -> H3CameraDirective | None:
        if isinstance(shot_number, bool) or not isinstance(shot_number, int):
            raise TypeError("shot number must be an integer")
        if not 1 <= shot_number <= self.shot_count:
            raise ValueError("shot number is outside the compiler context")
        return self.shot_cameras[shot_number - 1]


def direct_ref2v_multishot_editable_fields_v2(
    shot_count: int,
) -> tuple[str, ...]:
    """Return the exact dynamic writer fields for one V2 shot count."""

    _validate_shot_count(shot_count)
    return (
        "scene_setup",
        *(f"shot_{number}" for number in range(1, shot_count + 1)),
        "overall_soundscape",
        "non_diegetic_music",
    )


def direct_ref2v_multishot_editable_contract_v2(
    shot_count: int,
) -> RevisedDocumentContract:
    """Build the strict dynamic document envelope used by writer revisions."""

    fields = direct_ref2v_multishot_editable_fields_v2(shot_count)
    return RevisedDocumentContract(
        f"direct Ref2V {shot_count}-shot camera-owned editable document",
        tuple(f"{field}:" for field in fields),
    )


def encode_direct_ref2v_multishot_context_v2(
    header: str,
    shot_starts_ms: tuple[int, ...],
    hard_cut_times_ms: tuple[int, ...],
    shot_cameras: tuple[H3CameraDirective | None, ...],
    final_state_start_ms: int,
    duration_ms: int,
) -> str:
    """Serialize and validate the opaque flexible multi-shot V2 context."""

    context = _validated_context(
        header=header,
        shot_starts_ms=shot_starts_ms,
        hard_cut_times_ms=hard_cut_times_ms,
        shot_cameras=shot_cameras,
        final_state_start_ms=final_state_start_ms,
        duration_ms=duration_ms,
    )
    payload = {
        "version": 2,
        "header": context.header,
        "shot_starts_ms": list(context.shot_starts_ms),
        "hard_cut_times_ms": list(context.hard_cut_times_ms),
        "shot_cameras": [
            None if camera is None else _directive_payload(camera)
            for camera in context.shot_cameras
        ],
        "final_state_start_ms": context.final_state_start_ms,
        "duration_ms": context.duration_ms,
    }
    return _CONTEXT_MARKER + json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def is_direct_ref2v_multishot_context_v2(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_CONTEXT_MARKER)


def decode_direct_ref2v_multishot_context_v2(
    value: str,
) -> DirectRef2VMultiShotCompilerContextV2:
    """Decode one V2 context and reject V1, mono-shot and foreign contexts."""

    if not is_direct_ref2v_multishot_context_v2(value):
        raise ValueError("direct Ref2V multi-shot V2 compiler context is missing")
    try:
        payload = json.loads(value[len(_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError(
            "direct Ref2V multi-shot V2 compiler context is invalid"
        ) from error
    if not isinstance(payload, dict) or set(payload) != _CONTEXT_FIELDS:
        raise ValueError(
            "direct Ref2V multi-shot V2 compiler context has invalid fields"
        )
    if payload["version"] != 2:
        raise ValueError("unsupported direct Ref2V multi-shot V2 context version")
    raw_cameras = payload["shot_cameras"]
    if not isinstance(raw_cameras, list):
        raise ValueError("multi-shot V2 shot_cameras must be an array")
    cameras: list[H3CameraDirective | None] = []
    for raw_camera in raw_cameras:
        if raw_camera is None:
            cameras.append(None)
        else:
            cameras.append(parse_camera_directives([raw_camera])[0])
    return _validated_context(
        header=payload["header"],
        shot_starts_ms=payload["shot_starts_ms"],
        hard_cut_times_ms=payload["hard_cut_times_ms"],
        shot_cameras=tuple(cameras),
        final_state_start_ms=payload["final_state_start_ms"],
        duration_ms=payload["duration_ms"],
    )


def compile_direct_ref2v_multishot_document_v2(
    writer_content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContextV2,
) -> str:
    """Compile writer-only fields into the exact flexible multi-shot prompt."""

    context = _context(compiler_context)
    editable = direct_ref2v_multishot_editable_contract_v2(
        context.shot_count
    ).extract(writer_content)
    fields = _extract_writer_fields(editable, context.shot_count)
    _validate_writer_fields(fields, context)

    shot_blocks: list[str] = []
    for shot_number in range(1, context.shot_count + 1):
        camera = context.camera_for(shot_number)
        placements = (
            (TimedCameraPlacement(camera, 0),) if camera is not None else ()
        )
        shot = insert_ref2v_camera_clauses(
            fields[f"shot_{shot_number}"],
            placements,
        )
        heading = compile_shot_heading(
            shot_number,
            None if shot_number == 1 else context.shot_starts_ms[shot_number - 1],
        )
        shot_blocks.append(f"{heading} {shot}")

    content = (
        f"{context.header}\n\n"
        f"{fields['scene_setup']}\n\n"
        + "\n\n".join(shot_blocks)
        + "\n\n"
        f"overall_soundscape:\n{fields['overall_soundscape']}\n\n"
        f"non_diegetic_music:\n{fields['non_diegetic_music']}"
    )
    errors = lint_direct_ref2v_multishot_prompt_v2(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def render_direct_ref2v_multishot_writer_document_v2(plan_content: str) -> str:
    """Render V2 plan semantics into camera-free writer fields.

    This intentionally performs no creative rewrite: the super-fast planner is
    asked for English, render-ready values and this renderer only gives them a
    stable sentence order before the existing H3 compiler takes ownership of
    mappings, headings, cuts, clocks, and camera clauses.
    """

    plan = parse_direct_ref2v_multishot_plan_v2(plan_content)
    sections = [
        "scene_setup:\n"
        + _render_sentences((plan.scene_setup, *plan.continuity_invariants))
    ]
    for shot_number, shot in enumerate(plan.shots, 1):
        composition = shot.opening_composition
        fragments: list[str] = [
            (
                "The visible opening composition is "
                f"{composition.scale}; {composition.angle}; {composition.axis}; "
                f"{composition.perspective}"
            ),
        ]
        if shot.continuity_from_previous is not None:
            continuity = shot.continuity_from_previous
            fragments.extend((
                continuity.spatial_anchor,
                continuity.subject_position,
                continuity.travel_direction,
                continuity.motion_phase,
            ))
        fragments.extend((shot.purpose, shot.new_information, *shot.actions))
        fragments.append(shot.observable_end_state)
        if shot_number == len(plan.shots):
            fragments.extend((
                plan.final_state.description,
                (
                    "The resulting state remains clearly readable while movement, "
                    "materials, and sound settle"
                ),
            ))
        sections.append(
            f"shot_{shot_number}:\n" + _render_sentences(tuple(fragments))
        )
    sections.extend((
        "overall_soundscape:\n" + _render_sentences((plan.overall_soundscape,)),
        "non_diegetic_music:\n" + _render_sentences((plan.non_diegetic_music,)),
    ))
    rendered = "\n\n".join(sections)
    direct_ref2v_multishot_editable_contract_v2(len(plan.shots)).extract(rendered)
    return rendered


def _render_sentences(values: tuple[str, ...]) -> str:
    sentences: list[str] = []
    for raw in values:
        value = " ".join(raw.split()).strip()
        if not value:
            raise ValueError("super-fast plan prose must not be empty")
        if value[0].isalpha():
            value = value[0].upper() + value[1:]
        if not value.endswith((".", "!", "?")):
            value += "."
        sentences.append(value)
    return " ".join(sentences)


def lint_direct_ref2v_multishot_prompt_v2(
    content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContextV2 | None = None,
) -> tuple[str, ...]:
    """Validate flexible structure and, when known, exact compiler ownership."""

    try:
        value = _strip_fence(content).replace("\r\n", "\n")
    except (TypeError, ValueError) as error:
        return (str(error),)

    errors = list(_lint_compiled_structure(value))
    if compiler_context is None:
        return tuple(errors)
    try:
        context = _context(compiler_context)
    except (TypeError, ValueError) as error:
        errors.append(str(error))
        return tuple(dict.fromkeys(errors))

    actual_timestamps = tuple(_EXACT_TIMESTAMP.findall(value))
    expected_timestamps = tuple(
        _timestamp_text(timestamp_ms) for timestamp_ms in context.hard_cut_times_ms
    )
    if actual_timestamps != expected_timestamps:
        errors.append(
            "Compiled multi-shot V2 cut timestamps must match the derived shot starts."
        )
    try:
        parts = _split_compiled_document(value, context)
    except (TypeError, ValueError) as error:
        errors.append(str(error))
        return tuple(dict.fromkeys(errors))

    canonical_clauses = {
        compile_camera_motion(camera) for camera in context.directives
    }
    for shot_number in range(1, context.shot_count + 1):
        shot = parts[f"shot_{shot_number}"]
        camera = context.camera_for(shot_number)
        expected = Counter(
            () if camera is None else (compile_camera_motion(camera),)
        )
        for clause in canonical_clauses:
            if shot.count(clause) != expected[clause]:
                errors.append(
                    "Compiled camera clause occurrence count does not match "
                    f"Shot {shot_number} ownership."
                )
        try:
            if camera is not None:
                writer_shot = remove_ref2v_camera_clauses(
                    shot,
                    (TimedCameraPlacement(camera, 0),),
                )
            else:
                writer_shot = shot
            insert_ref2v_camera_clauses(writer_shot, ())
        except (TypeError, ValueError) as error:
            errors.append(f"Shot {shot_number}: {error}")
    return tuple(dict.fromkeys(errors))


def rehydrate_direct_ref2v_multishot_editable_document_v2(
    content: str,
    compiler_context: str | DirectRef2VMultiShotCompilerContextV2 | None,
) -> str:
    """Recover camera-free dynamic writer fields for edit or LLM revision."""

    if compiler_context is None:
        raise ValueError(
            "direct Ref2V multi-shot V2 revision is missing compiler context"
        )
    context = _context(compiler_context)
    errors = lint_direct_ref2v_multishot_prompt_v2(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    parts = _split_compiled_document(content, context)
    for shot_number in range(1, context.shot_count + 1):
        camera = context.camera_for(shot_number)
        if camera is not None:
            parts[f"shot_{shot_number}"] = remove_ref2v_camera_clauses(
                parts[f"shot_{shot_number}"],
                (TimedCameraPlacement(camera, 0),),
            )
    fields = direct_ref2v_multishot_editable_fields_v2(context.shot_count)
    return "\n\n".join(f"{field}:\n{parts[field]}" for field in fields)


def _validated_context(
    *,
    header: object,
    shot_starts_ms: object,
    hard_cut_times_ms: object,
    shot_cameras: object,
    final_state_start_ms: object,
    duration_ms: object,
) -> DirectRef2VMultiShotCompilerContextV2:
    if not isinstance(header, str) or not header.strip():
        raise ValueError("direct Ref2V multi-shot V2 compiler header is empty")
    normalized_header = header.strip().replace("\r\n", "\n")
    if "\n\n" in normalized_header:
        raise ValueError(
            "direct Ref2V multi-shot V2 compiler header contains an empty line"
        )
    if not isinstance(shot_starts_ms, (tuple, list)):
        raise TypeError("shot_starts_ms must be a tuple or list")
    starts = tuple(shot_starts_ms)
    _validate_shot_count(len(starts))
    if any(isinstance(item, bool) or not isinstance(item, int) for item in starts):
        raise TypeError("shot_starts_ms must contain integers")
    if starts[0] != 0 or any(
        left >= right for left, right in zip(starts, starts[1:])
    ):
        raise ValueError("shot_starts_ms must begin at zero and increase strictly")

    if not isinstance(hard_cut_times_ms, (tuple, list)):
        raise TypeError("hard_cut_times_ms must be a tuple or list")
    cuts = tuple(hard_cut_times_ms)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in cuts):
        raise TypeError("hard_cut_times_ms must contain integers")
    if cuts != starts[1:]:
        raise ValueError("hard_cut_times_ms must equal the derived later shot starts")

    if not isinstance(shot_cameras, (tuple, list)):
        raise TypeError("shot_cameras must be a tuple or list")
    cameras = tuple(shot_cameras)
    if len(cameras) != len(starts):
        raise ValueError("shot_cameras must contain one optional value per shot")
    for shot_number, camera in enumerate(cameras, 1):
        if camera is None:
            continue
        if not isinstance(camera, H3CameraDirective):
            raise TypeError("shot_cameras values must be H3CameraDirective or None")
        if camera.directive_id != f"camera_{shot_number}":
            raise ValueError(
                "multi-shot V2 camera IDs must match their owning shot number"
            )
    directive_ids = [camera.directive_id for camera in cameras if camera is not None]
    if len(directive_ids) != len(set(directive_ids)):
        raise ValueError("multi-shot V2 camera directive IDs must be unique")

    if (
        isinstance(final_state_start_ms, bool)
        or not isinstance(final_state_start_ms, int)
        or final_state_start_ms <= starts[-1]
    ):
        raise ValueError("final_state_start_ms must follow the final shot start")
    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, int)
        or duration_ms < final_state_start_ms
    ):
        raise ValueError("duration_ms must not precede the final state")
    return DirectRef2VMultiShotCompilerContextV2(
        header=normalized_header,
        shot_starts_ms=starts,
        hard_cut_times_ms=cuts,
        shot_cameras=cameras,
        final_state_start_ms=final_state_start_ms,
        duration_ms=duration_ms,
    )


def _context(
    value: str | DirectRef2VMultiShotCompilerContextV2,
) -> DirectRef2VMultiShotCompilerContextV2:
    if isinstance(value, DirectRef2VMultiShotCompilerContextV2):
        return _validated_context(
            header=value.header,
            shot_starts_ms=value.shot_starts_ms,
            hard_cut_times_ms=value.hard_cut_times_ms,
            shot_cameras=value.shot_cameras,
            final_state_start_ms=value.final_state_start_ms,
            duration_ms=value.duration_ms,
        )
    return decode_direct_ref2v_multishot_context_v2(value)


def _directive_payload(directive: H3CameraDirective) -> dict[str, str]:
    payload = {"id": directive.directive_id, "motion": directive.motion.value}
    if directive.amplitude is not None:
        payload["amplitude"] = directive.amplitude.value
    if directive.speed is not None:
        payload["speed"] = directive.speed.value
    if directive.target_clause:
        payload["target_clause"] = directive.target_clause
    return payload


def _extract_writer_fields(content: str, shot_count: int) -> dict[str, str]:
    fields = direct_ref2v_multishot_editable_fields_v2(shot_count)
    matches = list(_WRITER_FIELD.finditer(content))
    actual = tuple(match.group(1) for match in matches)
    if actual != fields:
        raise ValueError(
            "direct Ref2V multi-shot V2 writer fields have the wrong number or order"
        )
    result: dict[str, str] = {}
    for index, field in enumerate(fields):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        field_value = content[matches[index].end() : end].strip()
        if not field_value:
            raise ValueError(f"direct Ref2V multi-shot V2 field {field}: is empty")
        result[field] = field_value
    return result


def _validate_writer_fields(
    fields: dict[str, str],
    context: DirectRef2VMultiShotCompilerContextV2,
) -> None:
    combined = "\n".join(fields.values())
    if _PICTURE_LABEL.search(combined) or _LEGACY_LABEL.search(combined):
        raise ValueError("multi-shot V2 writer fields must not contain reference labels")
    if _ANY_SHOT_HEADING.search(combined):
        raise ValueError("multi-shot V2 writer fields must not contain shot headings")
    if _ANY_TIMESTAMP.search(combined):
        raise ValueError("multi-shot V2 writer fields must not contain timestamps")
    if "<scenetrans>" in combined:
        raise ValueError("direct Ref2V multi-shot V2 prompts must not use <scenetrans>")
    if _PLACEHOLDER.search(combined) or "[[" in combined or "]]" in combined:
        raise ValueError("camera-owned multi-shot V2 writer must not use placeholders")
    for field, field_value in fields.items():
        try:
            insert_ref2v_camera_clauses(field_value, ())
        except ValueError as error:
            raise ValueError(f"camera-owned writer field {field}: {error}") from error


def _lint_compiled_structure(content: str) -> tuple[str, ...]:
    errors: list[str] = []
    if _LEGACY_LABEL.search(content):
        errors.append(
            "The compiled multi-shot V2 prompt must use only canonical <Picture N> labels."
        )
    if "<scenetrans>" in content:
        errors.append("Direct Ref2V multi-shot V2 prompts must not use <scenetrans>.")
    if "[[" in content or "]]" in content:
        errors.append("An unresolved or malformed compiler placeholder remains.")
    if re.search(r"(?m)^(?:scene_setup|shot_\d+):[ \t]*", content):
        errors.append("Internal multi-shot V2 writer fields must not remain compiled.")

    raw_headings = list(re.finditer(r"(?m)^\[Shot\s+([^\]]+)\]", content))
    shot_count = len(raw_headings)
    if not _MIN_SHOTS <= shot_count <= _MAX_SHOTS:
        errors.append("The compiled multi-shot V2 prompt must contain 2 to 6 shots.")
        return tuple(dict.fromkeys(errors))
    expected_numbers = tuple(str(number) for number in range(1, shot_count + 1))
    if tuple(match.group(1) for match in raw_headings) != expected_numbers:
        errors.append("Compiled V2 shots must be contiguous and in numeric order.")

    first = list(re.finditer(r"(?m)^\[Shot 1\](?![ \t]+At\b)(?=\s|$)", content))
    if len(first) != 1:
        errors.append("[Shot 1] must appear exactly once without a timestamp.")
    later_times: list[int] = []
    for shot_number in range(2, shot_count + 1):
        pattern = re.compile(
            rf"(?m)^\[Shot {shot_number}\] At (\d{{2}}):(\d{{2}})\.(\d{{3}}),(?=\s|$)"
        )
        matches = list(pattern.finditer(content))
        if len(matches) != 1:
            errors.append(
                f"[Shot {shot_number}] must begin with one exact At MM:SS.mmm, timestamp."
            )
            continue
        minutes, seconds, milliseconds = (int(value) for value in matches[0].groups())
        if seconds >= 60:
            errors.append(f"[Shot {shot_number}] has an invalid timestamp.")
        else:
            later_times.append(minutes * 60_000 + seconds * 1_000 + milliseconds)
    if len(later_times) == shot_count - 1 and any(
        left >= right for left, right in zip(later_times, later_times[1:])
    ):
        errors.append("Multi-shot V2 cut timestamps must increase strictly.")
    if len(_ANY_TIMESTAMP.findall(content)) != shot_count - 1:
        errors.append("The compiled multi-shot V2 prompt contains unexpected timestamps.")

    first_heading_start = raw_headings[0].start()
    opening = content[:first_heading_start].strip()
    opening_parts = opening.split("\n\n", 1)
    header = opening_parts[0] if opening_parts else opening
    if len(opening_parts) != 2 or not all(part.strip() for part in opening_parts):
        errors.append(
            "The compiled multi-shot V2 prompt requires a non-empty header and scene setup."
        )
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
            errors.append(f"{label} must appear exactly once in the compiled header.")

    audio = {
        field: list(re.finditer(rf"(?m)^{field}:[ \t]*", content))
        for field in ("overall_soundscape", "non_diegetic_music")
    }
    for field, matches in audio.items():
        if len(matches) != 1:
            errors.append(f"The compiled field {field}: must appear exactly once.")
    overall = audio["overall_soundscape"]
    music = audio["non_diegetic_music"]
    if len(overall) == len(music) == 1:
        if not raw_headings[-1].start() < overall[0].start() < music[0].start():
            errors.append("Compiled multi-shot V2 audio fields are out of order.")
        if not content[overall[0].end() : music[0].start()].strip():
            errors.append("overall_soundscape must not be empty.")
        if not content[music[0].end() :].strip():
            errors.append("non_diegetic_music must not be empty; use N/A.")
    return tuple(dict.fromkeys(errors))


def _split_compiled_document(
    content: str,
    context: DirectRef2VMultiShotCompilerContextV2,
) -> dict[str, str]:
    value = _strip_fence(content).replace("\r\n", "\n")
    prefix = context.header + "\n\n"
    if not value.startswith(prefix):
        raise ValueError("direct Ref2V multi-shot V2 prompt has the wrong header")
    body = value[len(prefix) :]
    headings = tuple(
        compile_shot_heading(
            number,
            None if number == 1 else context.shot_starts_ms[number - 1],
        )
        for number in range(1, context.shot_count + 1)
    )
    heading_matches: list[re.Match[str]] = []
    for heading in headings:
        matches = list(re.finditer(rf"(?m)^{re.escape(heading)}(?=\s|$)", body))
        if len(matches) != 1:
            raise ValueError(f"compiled V2 heading must appear exactly once: {heading}")
        heading_matches.append(matches[0])
    if [match.start() for match in heading_matches] != sorted(
        match.start() for match in heading_matches
    ):
        raise ValueError("compiled multi-shot V2 headings are out of order")
    all_headings = list(_ANY_SHOT_HEADING.finditer(body))
    if len(all_headings) != context.shot_count or tuple(
        match.group(0) for match in all_headings
    ) != headings:
        raise ValueError("compiled multi-shot V2 document has an unexpected heading")

    overall = list(re.finditer(r"(?m)^overall_soundscape:[ \t]*", body))
    music = list(re.finditer(r"(?m)^non_diegetic_music:[ \t]*", body))
    if len(overall) != 1 or len(music) != 1:
        raise ValueError("compiled multi-shot V2 audio fields must appear exactly once")
    if not heading_matches[-1].start() < overall[0].start() < music[0].start():
        raise ValueError("compiled multi-shot V2 audio fields are out of order")

    result = {"scene_setup": body[: heading_matches[0].start()].strip()}
    for index, match in enumerate(heading_matches):
        end = (
            heading_matches[index + 1].start()
            if index + 1 < len(heading_matches)
            else overall[0].start()
        )
        result[f"shot_{index + 1}"] = body[match.end() : end].strip()
    result["overall_soundscape"] = body[overall[0].end() : music[0].start()].strip()
    result["non_diegetic_music"] = body[music[0].end() :].strip()
    for field, field_value in result.items():
        if not field_value:
            raise ValueError(f"compiled multi-shot V2 field {field} is empty")
    return result


def _timestamp_text(timestamp_ms: int) -> str:
    return compile_shot_heading(2, timestamp_ms).split("] ", 1)[1]


def _validate_shot_count(shot_count: int) -> None:
    if isinstance(shot_count, bool) or not isinstance(shot_count, int):
        raise TypeError("shot count must be an integer")
    if not _MIN_SHOTS <= shot_count <= _MAX_SHOTS:
        raise ValueError("shot count must be between 2 and 6")


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    if not value:
        raise ValueError("direct Ref2V multi-shot V2 document must not be empty")
    return value


__all__ = [
    "DirectRef2VMultiShotCompilerContextV2",
    "compile_direct_ref2v_multishot_document_v2",
    "decode_direct_ref2v_multishot_context_v2",
    "direct_ref2v_multishot_editable_contract_v2",
    "direct_ref2v_multishot_editable_fields_v2",
    "encode_direct_ref2v_multishot_context_v2",
    "is_direct_ref2v_multishot_context_v2",
    "lint_direct_ref2v_multishot_prompt_v2",
    "rehydrate_direct_ref2v_multishot_editable_document_v2",
    "render_direct_ref2v_multishot_writer_document_v2",
]
