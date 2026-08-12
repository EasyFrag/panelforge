"""Strict three-shot action plan for the direct multimodal Ref2V route.

The planner owns semantic durations but never absolute clocks.  Shot starts,
hard-cut timestamps, camera identifiers and the total duration are derived by
the application so that there is only one timeline to validate.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from panelforge.domain import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
)

from .direct_ref2v_plan import DirectContinuityRisk
from .minimax_h3_protocol import compile_shot_heading


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class DirectRef2VMultiShotCamera(_StrictModel):
    """One plan-owned camera movement whose clock is application-derived."""

    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None = Field(
        default=None,
        description=(
            "Optional amplitude. Must be null for static_shot, shake.slightly, "
            "shake.strongly, and pov."
        ),
    )
    speed: H3CameraSpeed | None = Field(
        default=None,
        description=(
            "Optional speed. Must be null for static_shot, shake.slightly, "
            "shake.strongly, and pov."
        ),
    )
    target_clause: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional plain-English spatial or visual continuation. It must not "
            "repeat camera terminology and must be null for shake or pov."
        ),
    )
    visible_change: str = Field(
        min_length=1,
        description="The concrete framing change visible by the end of the shot.",
    )

    @model_validator(mode="after")
    def validate_protocol_vocabulary(self) -> DirectRef2VMultiShotCamera:
        H3CameraDirective(
            directive_id="camera_1",
            motion=self.motion,
            amplitude=self.amplitude,
            speed=self.speed,
            target_clause=self.target_clause or "",
        )
        return self


class DirectRef2VMultiShot(_StrictModel):
    """One authored shot; its start, end and cut marker are derived."""

    shot_id: Literal["shot_1", "shot_2", "shot_3"]
    duration_ms: int = Field(
        gt=0,
        description=(
            "Semantic action duration for this shot. Do not write a start, end, "
            "cut time, or absolute timestamp."
        ),
    )
    purpose: str = Field(
        min_length=1,
        description="Why this shot exists in the sequence.",
    )
    new_information: str = Field(
        min_length=1,
        description="The new visual or narrative information introduced by this shot.",
    )
    entry_state: str = Field(
        min_length=1,
        description="The observable state immediately after the hard cut into this shot.",
    )
    primary_action: str = Field(
        min_length=1,
        description="The single dominant action of this shot.",
    )
    observable_end_state: str = Field(
        min_length=1,
        description="The visible state reached before the next hard cut.",
    )
    active_picture_labels: tuple[str, ...] = Field(
        min_length=1,
        max_length=3,
        description=(
            "Unique active labels for this shot, using only <Picture 1>, "
            "<Picture 2>, and <Picture 3>."
        ),
    )
    camera: DirectRef2VMultiShotCamera | None = Field(
        default=None,
        description=(
            "At most one camera movement. When present, the application starts "
            "it exactly at this shot's derived beginning."
        ),
    )

    @field_validator("active_picture_labels")
    @classmethod
    def validate_picture_labels(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        allowed = {"<Picture 1>", "<Picture 2>", "<Picture 3>"}
        if any(value not in allowed for value in values):
            raise ValueError(
                "active_picture_labels may contain only <Picture 1> to <Picture 3>"
            )
        if len(values) != len(set(values)):
            raise ValueError("active_picture_labels must be unique within a shot")
        expected_order = tuple(sorted(values, key=lambda value: int(value[-2])))
        if values != expected_order:
            raise ValueError("active_picture_labels must be in ascending numeric order")
        return values


class DirectRef2VMultiShotFinalState(_StrictModel):
    description: str = Field(min_length=1)
    final_hold_ms: int = Field(
        ge=0,
        description=(
            "Duration added after Shot 3's primary action to hold the final state. "
            "Do not write an absolute timestamp."
        ),
    )


class DirectRef2VMultiShotPlan(_StrictModel):
    """V1 Ref2V multi-shot contract: exactly three hard-cut shots."""

    scene_setup: str = Field(min_length=1)
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    shots: tuple[DirectRef2VMultiShot, ...] = Field(min_length=3, max_length=3)
    final_state: DirectRef2VMultiShotFinalState
    risks: tuple[DirectContinuityRisk, ...]
    technical_adjustments: tuple[str, ...] = Field(
        default=(),
        description=(
            "Application-owned recovery provenance. The planner must output an "
            "empty array."
        ),
    )
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @field_validator("continuity_invariants")
    @classmethod
    def validate_invariants(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("continuity_invariants must contain non-empty values")
        if len(values) != len(set(values)):
            raise ValueError("continuity_invariants must not contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_risks(self) -> DirectRef2VMultiShotPlan:
        shot_ids = tuple(shot.shot_id for shot in self.shots)
        if shot_ids != ("shot_1", "shot_2", "shot_3"):
            raise ValueError("shot IDs must be exactly shot_1, shot_2, shot_3 in order")
        risk_ids = [risk.risk_id for risk in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk IDs must be unique")
        if len(self.technical_adjustments) != len(set(self.technical_adjustments)):
            raise ValueError("technical_adjustments must not contain duplicates")
        return self

    @property
    def shot_starts_ms(self) -> tuple[int, int, int]:
        first_duration = self.shots[0].duration_ms
        second_duration = self.shots[1].duration_ms
        return (0, first_duration, first_duration + second_duration)

    @property
    def hard_cut_times_ms(self) -> tuple[int, int]:
        return self.shot_starts_ms[1:]

    @property
    def final_state_start_ms(self) -> int:
        return sum(shot.duration_ms for shot in self.shots)

    @property
    def duration_ms(self) -> int:
        return self.final_state_start_ms + self.final_state.final_hold_ms


def direct_ref2v_multishot_plan_schema() -> str:
    """Return the exact closed schema supplied to the local planner."""

    schema = DirectRef2VMultiShotPlan.model_json_schema()
    schema["properties"]["technical_adjustments"]["maxItems"] = 0
    return json.dumps(schema, ensure_ascii=False, indent=2)


def parse_direct_ref2v_multishot_plan(content: str) -> DirectRef2VMultiShotPlan:
    """Extract and structurally validate one three-shot JSON plan."""

    value = _json_object(content)
    try:
        return DirectRef2VMultiShotPlan.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V multi-shot plan: {error}") from error


def canonical_direct_ref2v_multishot_plan(
    content: str,
    *,
    recover_invalid_target: bool = False,
) -> str:
    """Return stable JSON with optional target-only camera recovery.

    Recovery never changes a motion, modifier, duration, shot assignment or
    semantic action.  It removes an invalid optional target only when the same
    camera object validates without that target and records the adjustment.
    """

    value = _json_object(content)
    raw_adjustments = value.get("technical_adjustments", [])
    if raw_adjustments not in ([], ()):
        raise ValueError(
            "invalid direct Ref2V multi-shot plan: technical_adjustments is "
            "application-owned and must be empty"
        )
    if recover_invalid_target:
        _recover_invalid_camera_targets(value)
    try:
        plan = DirectRef2VMultiShotPlan.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V multi-shot plan: {error}") from error
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def lint_direct_ref2v_multishot_plan(content: str) -> tuple[str, ...]:
    """Return structural errors; semantic risks deliberately remain warnings."""

    try:
        parse_direct_ref2v_multishot_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def direct_ref2v_multishot_plan_warnings(content: str) -> tuple[str, ...]:
    """Return non-blocking duration and unresolved-arbitration warnings."""

    try:
        plan = parse_direct_ref2v_multishot_plan(content)
    except (TypeError, ValueError):
        return ()
    warnings: list[str] = []
    if plan.final_state.final_hold_ms == 0:
        warnings.append(
            "Aucune tenue finale n'est planifiée ; vérifiez que l'état final reste lisible."
        )
    elif plan.final_state.final_hold_ms < 1000:
        warnings.append(
            "La tenue finale planifiée est inférieure à 1 seconde ; vérifiez sa lisibilité."
        )
    if plan.duration_ms > 15_000:
        warnings.append(
            "La durée dérivée du montage dépasse 15 secondes ; vérifiez la durée "
            "acceptée par le moteur vidéo ciblé."
        )
    unresolved = [risk.risk_id for risk in plan.risks if risk.resolution is None]
    if unresolved:
        warnings.append("Arbitrage conseillé pour : " + ", ".join(unresolved) + ".")
    for adjustment in plan.technical_adjustments:
        if adjustment.startswith("camera_target_dropped:"):
            directive_id = adjustment.partition(":")[2]
            warnings.append(
                f"La cible optionnelle de {directive_id} a été omise après "
                "validation ; le mouvement de caméra est conservé."
            )
        else:
            warnings.append(f"Ajustement technique appliqué : {adjustment}.")
    return tuple(warnings)


def direct_ref2v_multishot_camera_directives(
    content: str,
) -> tuple[H3CameraDirective, ...]:
    """Compile chronological camera_N IDs tied to their owning shot number."""

    plan = parse_direct_ref2v_multishot_plan(content)
    directives: list[H3CameraDirective] = []
    for shot_number, shot in enumerate(plan.shots, 1):
        if shot.camera is None:
            continue
        camera = shot.camera
        directives.append(
            H3CameraDirective(
                directive_id=f"camera_{shot_number}",
                motion=camera.motion,
                amplitude=camera.amplitude,
                speed=camera.speed,
                target_clause=camera.target_clause or "",
            )
        )
    return tuple(directives)


def direct_ref2v_multishot_writer_projection(content: str) -> str:
    """Project a plan to writer-facing semantics plus derived hard-cut clocks.

    Risks are supervision metadata and are intentionally excluded.  Camera
    vocabulary also stays plan-owned: the writer receives only the placeholder
    and its derived shot window, while the compiler receives typed directives
    through :func:`direct_ref2v_multishot_camera_directives`.
    """

    plan = parse_direct_ref2v_multishot_plan(content)
    starts = plan.shot_starts_ms
    projected_shots: list[dict[str, object]] = []
    for shot_number, (shot, start_ms) in enumerate(zip(plan.shots, starts), 1):
        end_ms = start_ms + shot.duration_ms
        camera_window: dict[str, object] | None = None
        if shot.camera is not None:
            directive_id = f"camera_{shot_number}"
            camera_window = {
                "directive_id": directive_id,
                "placeholder": f"[[camera:{directive_id}]]",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "visible_change": shot.camera.visible_change,
            }
        projected_shots.append(
            {
                "shot_number": shot_number,
                "shot_id": shot.shot_id,
                "heading": compile_shot_heading(
                    shot_number,
                    None if shot_number == 1 else start_ms,
                ),
                "hard_cut_before": None
                if shot_number == 1
                else {"type": "hard_cut", "at_ms": start_ms},
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": shot.duration_ms,
                "purpose": shot.purpose,
                "new_information": shot.new_information,
                "entry_state": shot.entry_state,
                "primary_action": shot.primary_action,
                "observable_end_state": shot.observable_end_state,
                "active_picture_labels": list(shot.active_picture_labels),
                "camera": camera_window,
            }
        )
    projection = {
        "scene_setup": plan.scene_setup,
        "continuity_invariants": list(plan.continuity_invariants),
        "shots": projected_shots,
        "final_state": {
            "description": plan.final_state.description,
            "start_ms": plan.final_state_start_ms,
            "final_hold_ms": plan.final_state.final_hold_ms,
            "end_ms": plan.duration_ms,
        },
        "overall_soundscape": plan.overall_soundscape,
        "non_diegetic_music": plan.non_diegetic_music,
        "derived_timing": {
            "shot_starts_ms": list(starts),
            "hard_cut_times_ms": list(plan.hard_cut_times_ms),
            "final_state_start_ms": plan.final_state_start_ms,
            "duration_ms": plan.duration_ms,
            "duration_seconds": plan.duration_ms / 1000,
        },
    }
    return json.dumps(projection, ensure_ascii=False, indent=2)


def _json_object(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("direct Ref2V multi-shot plan must not be empty")
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("invalid direct Ref2V multi-shot JSON fence")
        if lines[0].strip().lower() not in {"```", "```json"}:
            raise ValueError("invalid direct Ref2V multi-shot JSON fence")
        value = "\n".join(lines[1:-1]).strip()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid direct Ref2V multi-shot plan JSON: {error}"
        ) from error
    if not isinstance(decoded, dict):
        raise ValueError("direct Ref2V multi-shot plan must be one JSON object")
    return decoded


def _recover_invalid_camera_targets(value: dict[str, object]) -> None:
    """Drop only a target clause whose absence makes the camera fully valid."""

    shots = value.get("shots")
    if not isinstance(shots, list):
        return
    adjustments = value.get("technical_adjustments")
    if not isinstance(adjustments, list):
        adjustments = []
        value["technical_adjustments"] = adjustments
    for shot_number, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            continue
        camera = shot.get("camera")
        if not isinstance(camera, dict) or not camera.get("target_clause"):
            continue
        try:
            DirectRef2VMultiShotCamera.model_validate(camera)
            continue
        except ValidationError:
            candidate = dict(camera)
            candidate["target_clause"] = None
            try:
                DirectRef2VMultiShotCamera.model_validate(candidate)
            except ValidationError:
                continue
        camera["target_clause"] = None
        marker = f"camera_target_dropped:camera_{shot_number}"
        if marker not in adjustments:
            adjustments.append(marker)


__all__ = [
    "DirectRef2VMultiShot",
    "DirectRef2VMultiShotCamera",
    "DirectRef2VMultiShotFinalState",
    "DirectRef2VMultiShotPlan",
    "canonical_direct_ref2v_multishot_plan",
    "direct_ref2v_multishot_camera_directives",
    "direct_ref2v_multishot_plan_schema",
    "direct_ref2v_multishot_plan_warnings",
    "direct_ref2v_multishot_writer_projection",
    "lint_direct_ref2v_multishot_plan",
    "parse_direct_ref2v_multishot_plan",
]
