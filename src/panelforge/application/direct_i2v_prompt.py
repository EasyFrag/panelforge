"""Compilation helpers for the supervised single-frame I2VA path."""

from __future__ import annotations

from collections import Counter
import re

from panelforge.domain import H3CameraDirective

from .direct_ref2v_plan import parse_direct_ref2v_action_plan_v2
from .minimax_h3_protocol import compile_camera_motion


I2VA_FIXED_INSTRUCTION = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
I2VA_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)


def apply_direct_i2v_timing(content: str, plan_content: str) -> str:
    """Compile the derived duration and validate plan-owned landmarks.

    The LLM owns the semantic plan but not the redundant clocks.  The plan V2
    derives its final-state start and duration from the last beat plus
    ``final_hold_ms``; this function makes those values authoritative in the
    editable I2VA document.
    """

    plan = parse_direct_ref2v_action_plan_v2(plan_content)
    value = _strip_fence(content).replace("\r\n", "\n")
    integrated = _field_body(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
    )
    duration_pattern = re.compile(
        r"The target video is one continuous [^\r\n]+?-second shot\."
    )
    matches = list(duration_pattern.finditer(integrated))
    if len(matches) != 1:
        raise ValueError(
            "direct I2VA requires exactly one continuous-shot duration sentence"
        )
    duration_seconds = _format_duration_seconds(plan.duration_ms)
    replacement = (
        f"The target video is one continuous {duration_seconds}-second shot."
    )
    integrated = duration_pattern.sub(replacement, integrated, count=1)

    final_landmark = _format_timestamp(plan.final_start_ms)
    if final_landmark not in integrated:
        raise ValueError(
            "direct I2VA final prompt must contain the derived final-state "
            f"landmark {final_landmark}"
        )

    for camera in plan.camera_directives:
        if camera.start_ms == 0:
            continue
        expected_landmark = _format_timestamp(camera.start_ms)
        placeholder = f"[[camera:{camera.directive_id}]]"
        compiled_clause = compile_camera_motion(
            H3CameraDirective(
                directive_id=camera.directive_id,
                motion=camera.motion,
                amplitude=camera.amplitude,
                speed=camera.speed,
                target_clause=camera.target_clause or "",
            )
        )
        if not (
            re.search(
                rf"{re.escape(expected_landmark)}\s+(?:{re.escape(placeholder)}|"
                rf"{re.escape(compiled_clause)})",
                integrated,
            )
        ):
            raise ValueError(
                "direct I2VA camera directive "
                f"{camera.directive_id} must start at {expected_landmark}"
            )

    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3}),", integrated):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if seconds >= 60 or timestamp_ms > plan.duration_ms:
            raise ValueError(
                "direct I2VA final prompt contains a timestamp beyond the "
                "derived duration"
            )

    start, end = _field_span(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
    )
    return value[:start] + integrated.strip() + "\n" + value[end:]


def normalize_direct_i2v_camera_placeholders(content: str) -> str:
    """Recover the harmless period writers sometimes append to placeholders."""

    value = _strip_fence(content).replace("\r\n", "\n")
    placeholder = r"\[\[camera:camera_\d+\]\]"
    return re.sub(rf"({placeholder})\.(?=\s|$)", r"\1", value)


def rehydrate_direct_i2v_editable_document(
    content: str,
    directives: tuple[H3CameraDirective, ...],
) -> str:
    """Restore plan-owned placeholders without asking the LLM to infer them."""

    value = _strip_fence(content).replace("\r\n", "\n")
    prefix = I2VA_FIXED_INSTRUCTION + "\n\n"
    if not value.startswith(prefix):
        raise ValueError("direct I2VA prompt is missing its fixed instruction")
    body = value[len(prefix) :]
    expected_clauses = Counter(compile_camera_motion(item) for item in directives)
    for clause, expected_count in expected_clauses.items():
        if body.count(clause) != expected_count:
            raise ValueError(
                "compiled camera clause occurrence count does not match the "
                "direct I2VA plan"
            )
    for directive in directives:
        body = body.replace(
            compile_camera_motion(directive),
            f"[[camera:{directive.directive_id}]]",
            1,
        )
    return body.strip()


def _field_body(content: str, field: str, next_field: str | None) -> str:
    start, end = _field_span(content, field, next_field)
    return content[start:end].strip()


def _field_span(content: str, field: str, next_field: str | None) -> tuple[int, int]:
    marker = re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content)
    if marker is None:
        raise ValueError(f"direct I2VA document is missing {field}:")
    if next_field is None:
        return marker.end(), len(content)
    next_marker = re.search(rf"(?m)^{re.escape(next_field)}:[ \t]*", content)
    if next_marker is None or next_marker.start() <= marker.end():
        raise ValueError(f"direct I2VA document is missing {next_field}:")
    return marker.end(), next_marker.start()


def _format_duration_seconds(milliseconds: int) -> str:
    if milliseconds % 1000 == 0:
        return str(milliseconds // 1000)
    return f"{milliseconds / 1000:.3f}".rstrip("0").rstrip(".")


def _format_timestamp(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"At {minutes:02d}:{seconds:02d}.{millis:03d},"


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    return value
