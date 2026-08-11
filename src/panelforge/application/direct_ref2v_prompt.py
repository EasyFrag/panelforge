"""Pure prompt-envelope and compiler helpers for direct multimodal Ref2V."""

from __future__ import annotations

from collections import Counter
import json
import re

from panelforge.domain import (
    CompositionStage,
    H3CameraDirective,
    PromptLabSession,
)

from .minimax_h3_protocol import (
    compile_camera_motion,
    parse_camera_directives,
)
from .direct_ref2v_plan import parse_direct_ref2v_action_plan_v2


PictureMapping = tuple[tuple[str, int], ...]

_CONTEXT_MARKER = "__PANELFORGE_DIRECT_REF2V_CONTEXT__:"
_EDITABLE_FIELDS = (
    "scene_setup",
    "shot_1",
    "overall_soundscape",
    "non_diegetic_music",
)
_REFERENCE_RULES = {
    "first_frame": (
        "<Picture {number}>: the exact fully preserved starting frame at 0.00 "
        "seconds; it owns the visible opening subjects, state, pose, framing, "
        "perspective, environment, lighting and composition."
    ),
    "keyframe_reference": (
        "<Picture {number}>: a concrete keyframe anchor at the time assigned by "
        "the approved Brief and plan; preserve its declared frame state and only "
        "the attributes explicitly assigned to it."
    ),
    "last_frame": (
        "<Picture {number}>: the exact final-frame anchor; reach its declared "
        "visible state at the planned final time without treating it as the opening frame."
    ),
    "subject_reference": (
        "Use <Picture {number}> only for subject identity, stable appearance and "
        "attributes explicitly assigned by the approved Brief; do not automatically "
        "transfer pose, expression, action, clothing state, lens, camera angle, "
        "lighting, background, composition or temporal state."
    ),
    "environment_reference": (
        "Use <Picture {number}> only for the environment, materials, spatial "
        "geometry, lighting and atmosphere explicitly assigned by the approved "
        "Brief; do not transfer its subjects, pose, action or temporal state."
    ),
    "style_reference": (
        "Use <Picture {number}> only for the visual style, palette, texture and "
        "cinematographic treatment assigned by the approved Brief; do not transfer "
        "identity, pose, action, environment geometry or temporal state."
    ),
    "composition_reference": (
        "Use <Picture {number}> only for composition, framing and spatial balance "
        "assigned by the approved Brief; do not transfer identity, action, clothing, "
        "background content or temporal state."
    ),
    "motion_reference": (
        "Use <Picture {number}> only for the action mechanics, body dynamics and "
        "motion qualities assigned by the approved Brief; do not transfer identity, "
        "clothing, environment, lighting, lens, composition or target pose."
    ),
}


def direct_reference_mapping(
    session: PromptLabSession,
    mapping: PictureMapping,
) -> str:
    """Render the Brief-to-local-picture evidence map supplied to the planner."""

    session_numbers = {
        reference.reference_id: index
        for index, reference in enumerate(session.references, 1)
    }
    chunks: list[str] = []
    for reference_id, picture_number in mapping:
        reference = session.reference(reference_id)
        rule = _reference_rule(reference.role, picture_number)
        chunks.extend(
            (
                f"<Picture {picture_number}> = <Image {session_numbers[reference_id]}>",
                f"label: {reference.label}",
                f"role: {reference.role}",
                "uses: " + ", ".join(use.value for use in reference.uses),
                f"compiled influence rule: {rule}",
                "native image: attached to the planner request",
                "",
            )
        )
    return "\n".join(chunks).strip()


def direct_reference_header(
    session: PromptLabSession,
    mapping: PictureMapping,
) -> str:
    """Compile the immutable one-to-three-reference H3 header."""

    return "\n".join(
        _reference_rule(session.reference(reference_id).role, picture_number)
        for reference_id, picture_number in mapping
    )


def lint_direct_ref2v_prompt(content: str) -> tuple[str, ...]:
    """Validate the dynamic one-to-three-picture compact Ref2V envelope."""

    if not isinstance(content, str) or not content.strip():
        return ("Le prompt Ref2V direct est vide.",)
    value = _strip_fence(content).replace("\r\n", "\n")
    errors: list[str] = []
    markers = ("Shot 1", "overall_soundscape", "non_diegetic_music")
    positions: list[int] = []
    for marker in markers:
        matches = list(re.finditer(rf"(?m)^{re.escape(marker)}:[ \t]*", value))
        if len(matches) != 1:
            errors.append(f"Le champ {marker}: doit apparaître exactement une fois.")
        else:
            positions.append(matches[0].start())
    if len(positions) == len(markers) and positions != sorted(positions):
        errors.append("Les champs du prompt Ref2V direct sont dans le mauvais ordre.")
    if errors:
        return tuple(errors)
    if re.search(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>", value):
        errors.append(
            "Le prompt Ref2V direct doit utiliser uniquement ses labels <Picture N>."
        )
    picture_numbers = sorted(
        {int(number) for number in re.findall(r"<Picture\s+(\d+)>", value)}
    )
    if not picture_numbers or picture_numbers != list(
        range(1, len(picture_numbers) + 1)
    ) or len(picture_numbers) > 3:
        errors.append("Les labels Picture doivent être contigus entre 1 et 3.")
    for number in picture_numbers:
        if value.count(f"<Picture {number}>") != 1:
            errors.append(
                f"<Picture {number}> doit apparaître exactement une fois dans le mapping."
            )
    header_and_scene = value[: positions[0]].strip()
    if not header_and_scene:
        errors.append("Le mapping et la mise en place de scène ne doivent pas être vides.")
    shot = _inline_field_body(value, "Shot 1", "overall_soundscape").strip()
    soundscape = _inline_field_body(
        value,
        "overall_soundscape",
        "non_diegetic_music",
    ).strip()
    music = _inline_field_body(value, "non_diegetic_music", None).strip()
    if not shot:
        errors.append("Shot 1 ne doit pas être vide.")
    if not soundscape:
        errors.append("overall_soundscape ne doit pas être vide.")
    if not music:
        errors.append("non_diegetic_music ne doit pas être vide ; utilisez N/A.")
    timestamps: list[int] = []
    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3})\b", shot):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        if seconds >= 60:
            errors.append("Un timestamp de Shot 1 est invalide.")
        timestamps.append(minutes * 60_000 + seconds * 1_000 + milliseconds)
    if timestamps != sorted(timestamps):
        errors.append("Les timestamps de Shot 1 doivent être non décroissants.")
    for field in _EDITABLE_FIELDS:
        if re.search(rf"(?m)^{re.escape(field)}:$", value):
            errors.append(f"Le champ interne {field}: ne doit pas être compilé tel quel.")
    return tuple(dict.fromkeys(errors))


def apply_direct_ref2v_timing_v2(content: str, plan_content: str) -> str:
    """Compile the derived duration and verify the final-state landmark."""

    plan = parse_direct_ref2v_action_plan_v2(plan_content)
    value = _strip_fence(content).replace("\r\n", "\n")
    duration_pattern = re.compile(
        r"(?m)^The target video is one continuous [^\r\n]+?-second shot\."
    )
    matches = list(duration_pattern.finditer(value))
    if len(matches) != 1:
        raise ValueError(
            "direct Ref2V V2 requires exactly one continuous-shot duration sentence"
        )
    duration_seconds = _format_duration_seconds(plan.duration_ms)
    value = duration_pattern.sub(
        f"The target video is one continuous {duration_seconds}-second shot.",
        value,
        count=1,
    )
    shot = _inline_field_body(value, "Shot 1", "overall_soundscape")
    final_landmark = _format_timestamp(plan.final_start_ms)
    if final_landmark not in shot:
        raise ValueError(
            "direct Ref2V V2 final prompt must contain the derived final-state "
            f"landmark {final_landmark}"
        )
    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3})\b", shot):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if timestamp_ms > plan.duration_ms:
            raise ValueError(
                "direct Ref2V V2 final prompt contains a timestamp beyond the "
                "derived duration"
            )
    return value


def normalize_direct_ref2v_camera_placeholders(content: str) -> str:
    """Recover two unambiguous writer-only camera layout variants.

    The protocol compiler owns the sentence punctuation.  Local writers still
    occasionally add one period after the placeholder or keep the placeholder
    on the ``shot_1:`` line.  Both layouts carry exactly the same semantics, so
    normalize them before the strict protocol validation.  Embedded
    placeholders elsewhere remain untouched and therefore fail closed.
    """

    value = _strip_fence(content).replace("\r\n", "\n")
    placeholder = r"\[\[camera:camera_\d+\]\]"
    value = re.sub(rf"({placeholder})\.(?=\s|$)", r"\1", value)
    value = re.sub(
        rf"(?m)^(shot_1:)[ \t]+({placeholder})(?=\s|$)",
        r"\1\n\2",
        value,
    )
    return value


def validate_direct_ref2v_labels(
    session: PromptLabSession,
    mapping: PictureMapping,
    stage: CompositionStage,
    content: str,
) -> None:
    """Validate labels against the actual bindings and lock the compiled header."""

    expected_numbers = tuple(range(1, len(mapping) + 1))
    if not 1 <= len(mapping) <= 3 or tuple(
        number for _, number in mapping
    ) != expected_numbers:
        raise ValueError(
            "direct Ref2V requires one to three contiguous local picture bindings"
        )
    used_numbers = {
        int(value) for value in re.findall(r"<Picture\s+(\d+)>", content)
    }
    unexpected = sorted(used_numbers - set(expected_numbers))
    if unexpected:
        labels = ", ".join(f"<Picture {number}>" for number in unexpected)
        raise ValueError(f"unknown or unbound direct picture label(s): {labels}")
    if stage is CompositionStage.BEAT_SHEET:
        return
    if stage is not CompositionStage.FINAL_PROMPT:
        raise ValueError("direct Ref2V exposes only its action plan and final_prompt")
    missing = sorted(set(expected_numbers) - used_numbers)
    if missing:
        labels = ", ".join(f"<Picture {number}>" for number in missing)
        raise ValueError(f"required direct picture label(s) missing: {labels}")
    expected_header = direct_reference_header(session, mapping)
    normalized = _strip_fence(content).replace("\r\n", "\n")
    if not normalized.startswith(expected_header + "\n\n"):
        raise ValueError(
            "direct Ref2V final prompt must preserve the exact compiled reference header"
        )


def encode_direct_ref2v_context(
    header: str,
    directives: tuple[H3CameraDirective, ...],
) -> str:
    """Serialize immutable reference and camera compiler inputs."""

    payload = {
        "header": header,
        "camera_directives": [
            {
                "id": directive.directive_id,
                "motion": directive.motion.value,
                **(
                    {"amplitude": directive.amplitude.value}
                    if directive.amplitude is not None
                    else {}
                ),
                **(
                    {"speed": directive.speed.value}
                    if directive.speed is not None
                    else {}
                ),
                **(
                    {"target_clause": directive.target_clause}
                    if directive.target_clause
                    else {}
                ),
            }
            for directive in directives
        ],
    }
    return _CONTEXT_MARKER + json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def is_direct_ref2v_context(value: str) -> bool:
    return value.startswith(_CONTEXT_MARKER)


def decode_direct_ref2v_context(
    value: str,
) -> tuple[str, tuple[H3CameraDirective, ...]]:
    """Validate and decode one immutable direct-Ref2V compiler context."""

    if not is_direct_ref2v_context(value):
        raise ValueError("direct Ref2V compiler context is missing")
    try:
        payload = json.loads(value[len(_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError("direct Ref2V compiler context is invalid") from error
    if not isinstance(payload, dict) or set(payload) != {
        "header",
        "camera_directives",
    }:
        raise ValueError("direct Ref2V compiler context has invalid fields")
    header = payload["header"]
    directives = payload["camera_directives"]
    if not isinstance(header, str) or not header.strip():
        raise ValueError("direct Ref2V compiler header is empty")
    if directives == []:
        return header, ()
    return header, parse_camera_directives(
        json.dumps(directives, ensure_ascii=True)
    )


def rehydrate_direct_ref2v_editable_document(
    content: str,
    compiler_context: str | None,
) -> str:
    """Recover the editable writer envelope from a compiled final prompt."""

    if compiler_context is None:
        raise ValueError("direct Ref2V revision is missing compiler context")
    header, directives = decode_direct_ref2v_context(compiler_context)
    prefix = header + "\n\n"
    value = _strip_fence(content).replace("\r\n", "\n")
    if not value.startswith(prefix):
        raise ValueError("direct Ref2V prompt is missing its compiled mapping")
    body = value[len(prefix) :]
    shot_marker = re.search(r"(?m)^Shot 1:[ \t]*", body)
    if shot_marker is None:
        raise ValueError("direct Ref2V prompt is missing Shot 1")
    scene = body[: shot_marker.start()].strip()
    shot_and_audio = body[shot_marker.start() :]
    shot = _inline_field_body(
        shot_and_audio,
        "Shot 1",
        "overall_soundscape",
    ).strip()
    soundscape = _inline_field_body(
        shot_and_audio,
        "overall_soundscape",
        "non_diegetic_music",
    ).strip()
    music = _inline_field_body(
        shot_and_audio,
        "non_diegetic_music",
        None,
    ).strip()
    editable = (
        f"scene_setup:\n{scene}\n\n"
        f"shot_1:\n{shot}\n\n"
        f"overall_soundscape:\n{soundscape}\n\n"
        f"non_diegetic_music:\n{music}"
    )
    expected = Counter(compile_camera_motion(item) for item in directives)
    for clause, count in expected.items():
        if editable.count(clause) != count:
            raise ValueError(
                "compiled camera clauses do not match the direct Ref2V plan"
            )
    for directive in directives:
        editable = editable.replace(
            compile_camera_motion(directive),
            f"[[camera:{directive.directive_id}]]",
            1,
        )
    return editable


def _reference_rule(role: str, picture_number: int) -> str:
    try:
        return _REFERENCE_RULES[role].format(number=picture_number)
    except KeyError as error:
        raise ValueError(
            f"unsupported direct Ref2V reference role: {role}"
        ) from error


def _inline_field_body(
    content: str,
    field: str,
    next_field: str | None,
) -> str:
    start = re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content)
    if start is None:
        return ""
    if next_field is None:
        return content[start.end() :]
    end = re.search(
        rf"(?m)^{re.escape(next_field)}:[ \t]*",
        content[start.end() :],
    )
    if end is None:
        return content[start.end() :]
    return content[start.end() : start.end() + end.start()]


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    return value


def _format_duration_seconds(duration_ms: int) -> str:
    whole, remainder = divmod(duration_ms, 1000)
    if remainder == 0:
        return str(whole)
    return f"{whole}.{remainder:03d}".rstrip("0")


def _format_timestamp(timestamp_ms: int) -> str:
    total_seconds, milliseconds = divmod(timestamp_ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"At {minutes:02d}:{seconds:02d}.{milliseconds:03d},"


__all__ = [
    "PictureMapping",
    "apply_direct_ref2v_timing_v2",
    "decode_direct_ref2v_context",
    "direct_reference_header",
    "direct_reference_mapping",
    "encode_direct_ref2v_context",
    "is_direct_ref2v_context",
    "lint_direct_ref2v_prompt",
    "normalize_direct_ref2v_camera_placeholders",
    "rehydrate_direct_ref2v_editable_document",
    "validate_direct_ref2v_labels",
]
