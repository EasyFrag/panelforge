"""Flexible camera-owned action plan for the direct multimodal Ref2V route.

V2 authors two to six ordered shots.  Their array positions are authoritative:
the application derives ``shot_N``, ``camera_N``, hard-cut clocks and the total
duration instead of asking the planner to repeat those values.
"""

from __future__ import annotations

import json

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


class DirectRef2VMultiShotOpeningCompositionV2(_StrictModel):
    """Observable framing at the opening of one shot."""

    scale: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    axis: str = Field(min_length=1)
    perspective: str = Field(min_length=1)


class DirectRef2VMultiShotContinuityV2(_StrictModel):
    """Explicit spatial and motion hand-off from the preceding hard cut."""

    spatial_anchor: str = Field(min_length=1)
    subject_position: str = Field(min_length=1)
    travel_direction: str = Field(min_length=1)
    motion_phase: str = Field(min_length=1)


class DirectRef2VMultiShotCameraV2(_StrictModel):
    """One plan-owned camera movement with an application-derived ID."""

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
    def validate_protocol_vocabulary(self) -> DirectRef2VMultiShotCameraV2:
        H3CameraDirective(
            directive_id="camera_1",
            motion=self.motion,
            amplitude=self.amplitude,
            speed=self.speed,
            target_clause=self.target_clause or "",
        )
        return self


class DirectRef2VMultiShotV2(_StrictModel):
    """One authored shot; its identity and absolute clocks are derived."""

    duration_ms: int = Field(
        gt=0,
        description=(
            "Semantic duration for this shot. Do not write a shot ID, start, end, "
            "cut time, transition, or absolute timestamp."
        ),
    )
    opening_composition: DirectRef2VMultiShotOpeningCompositionV2
    purpose: str = Field(min_length=1)
    new_information: str = Field(min_length=1)
    continuity_from_previous: DirectRef2VMultiShotContinuityV2 | None = Field(
        description=(
            "Null for the first shot. Every later shot must describe the spatial "
            "and motion hand-off from the preceding hard cut."
        )
    )
    actions: tuple[str, ...] = Field(
        min_length=1,
        description="Ordered observable subject actions within this shot.",
    )
    observable_end_state: str = Field(min_length=1)
    active_picture_labels: tuple[str, ...] = Field(
        min_length=1,
        max_length=3,
        description=(
            "Unique active labels for this shot, using only <Picture 1>, "
            "<Picture 2>, and <Picture 3>."
        ),
    )
    camera: DirectRef2VMultiShotCameraV2 | None = Field(
        default=None,
        description=(
            "At most one camera movement. Its camera_N identifier and start at "
            "this shot's derived opening are application-owned."
        ),
    )

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("actions must contain non-empty values")
        if len(values) != len(set(values)):
            raise ValueError("actions must not contain duplicates within a shot")
        return values

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


class DirectRef2VMultiShotFinalStateV2(_StrictModel):
    description: str = Field(min_length=1)
    final_hold_ms: int = Field(
        ge=0,
        description=(
            "Duration added after the last shot's actions to hold the final state. "
            "Do not write an absolute timestamp."
        ),
    )


class DirectRef2VMultiShotPlanV2(_StrictModel):
    """V2 Ref2V multi-shot contract: two to six hard-cut shots."""

    scene_setup: str = Field(min_length=1)
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    shots: tuple[DirectRef2VMultiShotV2, ...] = Field(min_length=2, max_length=6)
    final_state: DirectRef2VMultiShotFinalStateV2
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
    def validate_sequence(self) -> DirectRef2VMultiShotPlanV2:
        if self.shots[0].continuity_from_previous is not None:
            raise ValueError("Shot 1 continuity_from_previous must be null")
        for shot_number, shot in enumerate(self.shots[1:], 2):
            if shot.continuity_from_previous is None:
                raise ValueError(
                    f"Shot {shot_number} continuity_from_previous must be provided"
                )
        risk_ids = [risk.risk_id for risk in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk IDs must be unique")
        if len(self.technical_adjustments) != len(set(self.technical_adjustments)):
            raise ValueError("technical_adjustments must not contain duplicates")
        return self

    @property
    def shot_ids(self) -> tuple[str, ...]:
        return tuple(f"shot_{number}" for number in range(1, len(self.shots) + 1))

    @property
    def shot_starts_ms(self) -> tuple[int, ...]:
        starts: list[int] = []
        cursor = 0
        for shot in self.shots:
            starts.append(cursor)
            cursor += shot.duration_ms
        return tuple(starts)

    @property
    def hard_cut_times_ms(self) -> tuple[int, ...]:
        return self.shot_starts_ms[1:]

    @property
    def final_state_start_ms(self) -> int:
        return sum(shot.duration_ms for shot in self.shots)

    @property
    def duration_ms(self) -> int:
        return self.final_state_start_ms + self.final_state.final_hold_ms


def direct_ref2v_multishot_plan_schema_v2() -> str:
    """Return the exact closed V2 schema supplied to the local planner."""

    schema = DirectRef2VMultiShotPlanV2.model_json_schema()
    schema["properties"]["technical_adjustments"]["maxItems"] = 0
    return json.dumps(schema, ensure_ascii=False, indent=2)


def parse_direct_ref2v_multishot_plan_v2(
    content: str,
) -> DirectRef2VMultiShotPlanV2:
    """Extract and structurally validate one flexible multi-shot JSON plan."""

    value = _json_object_v2(content)
    try:
        return DirectRef2VMultiShotPlanV2.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V multi-shot plan V2: {error}") from error


def canonical_direct_ref2v_multishot_plan_v2(
    content: str,
    *,
    recover_invalid_target: bool = False,
) -> str:
    """Return stable V2 JSON with optional target-only camera recovery."""

    value = _json_object_v2(content)
    raw_adjustments = value.get("technical_adjustments", [])
    if raw_adjustments not in ([], ()):
        raise ValueError(
            "invalid direct Ref2V multi-shot plan V2: technical_adjustments is "
            "application-owned and must be empty"
        )
    if recover_invalid_target:
        _recover_invalid_camera_targets_v2(value)
    try:
        plan = DirectRef2VMultiShotPlanV2.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V multi-shot plan V2: {error}") from error
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def lint_direct_ref2v_multishot_plan_v2(content: str) -> tuple[str, ...]:
    """Return structural errors; semantic risks deliberately remain warnings."""

    try:
        parse_direct_ref2v_multishot_plan_v2(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def direct_ref2v_multishot_plan_warnings_v2(content: str) -> tuple[str, ...]:
    """Return non-blocking duration and unresolved-arbitration warnings."""

    try:
        plan = parse_direct_ref2v_multishot_plan_v2(content)
    except (TypeError, ValueError):
        return ()
    warnings: list[str] = []
    if plan.final_state.final_hold_ms == 0:
        warnings.append(
            "Aucune tenue finale n'est planifiee ; verifiez que l'etat final reste lisible."
        )
    elif plan.final_state.final_hold_ms < 1000:
        warnings.append(
            "La tenue finale planifiee est inferieure a 1 seconde ; verifiez sa lisibilite."
        )
    if plan.duration_ms > 15_000:
        warnings.append(
            "La duree derivee du montage depasse 15 secondes ; verifiez la duree "
            "acceptee par le moteur video cible."
        )
    for shot_number, (previous, current) in enumerate(
        zip(plan.shots, plan.shots[1:]),
        2,
    ):
        if current.opening_composition == previous.opening_composition:
            warnings.append(
                f"Les plans {shot_number - 1} et {shot_number} ont la meme "
                "composition d'ouverture ; verifiez que la coupe apporte un "
                "changement visuel lisible."
            )
        if current.new_information == previous.new_information:
            warnings.append(
                f"Les plans {shot_number - 1} et {shot_number} declarent la meme "
                "information nouvelle ; verifiez que la coupe est necessaire."
            )
    unresolved = [risk.risk_id for risk in plan.risks if risk.resolution is None]
    if unresolved:
        warnings.append("Arbitrage conseille pour : " + ", ".join(unresolved) + ".")
    for adjustment in plan.technical_adjustments:
        if adjustment.startswith("camera_target_dropped:"):
            directive_id = adjustment.partition(":")[2]
            warnings.append(
                f"La cible optionnelle de {directive_id} a ete omise apres "
                "validation ; le mouvement de camera est conserve."
            )
        else:
            warnings.append(f"Ajustement technique applique : {adjustment}.")
    return tuple(warnings)


def direct_ref2v_multishot_camera_directives_v2(
    content: str,
) -> tuple[H3CameraDirective, ...]:
    """Compile camera_N IDs from the owning shot's array position."""

    plan = parse_direct_ref2v_multishot_plan_v2(content)
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


def direct_ref2v_multishot_writer_projection_v2(content: str) -> str:
    """Expose dynamic shot semantics and derived cuts, but no camera semantics."""

    plan = parse_direct_ref2v_multishot_plan_v2(content)
    starts = plan.shot_starts_ms
    projected_shots: list[dict[str, object]] = []
    for shot_number, (shot, shot_id, start_ms) in enumerate(
        zip(plan.shots, plan.shot_ids, starts, strict=True),
        1,
    ):
        end_ms = start_ms + shot.duration_ms
        projected_shots.append(
            {
                "shot_number": shot_number,
                "shot_id": shot_id,
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
                "opening_composition": shot.opening_composition.model_dump(mode="json"),
                "purpose": shot.purpose,
                "new_information": shot.new_information,
                "continuity_from_previous": None
                if shot.continuity_from_previous is None
                else shot.continuity_from_previous.model_dump(mode="json"),
                "actions": list(shot.actions),
                "observable_end_state": shot.observable_end_state,
                "active_picture_labels": list(shot.active_picture_labels),
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
            "shot_ids": list(plan.shot_ids),
            "shot_starts_ms": list(starts),
            "hard_cut_times_ms": list(plan.hard_cut_times_ms),
            "final_state_start_ms": plan.final_state_start_ms,
            "duration_ms": plan.duration_ms,
            "duration_seconds": plan.duration_ms / 1000,
        },
    }
    return json.dumps(projection, ensure_ascii=False, indent=2)


def _json_object_v2(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("direct Ref2V multi-shot plan V2 must not be empty")
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("invalid direct Ref2V multi-shot V2 JSON fence")
        if lines[0].strip().lower() not in {"```", "```json"}:
            raise ValueError("invalid direct Ref2V multi-shot V2 JSON fence")
        value = "\n".join(lines[1:-1]).strip()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid direct Ref2V multi-shot plan V2 JSON: {error}"
        ) from error
    if not isinstance(decoded, dict):
        raise ValueError("direct Ref2V multi-shot plan V2 must be one JSON object")
    return decoded


def _recover_invalid_camera_targets_v2(value: dict[str, object]) -> None:
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
            DirectRef2VMultiShotCameraV2.model_validate(camera)
            continue
        except ValidationError:
            candidate = dict(camera)
            candidate["target_clause"] = None
            try:
                DirectRef2VMultiShotCameraV2.model_validate(candidate)
            except ValidationError:
                continue
        camera["target_clause"] = None
        marker = f"camera_target_dropped:camera_{shot_number}"
        if marker not in adjustments:
            adjustments.append(marker)


__all__ = [
    "DirectRef2VMultiShotCameraV2",
    "DirectRef2VMultiShotContinuityV2",
    "DirectRef2VMultiShotFinalStateV2",
    "DirectRef2VMultiShotOpeningCompositionV2",
    "DirectRef2VMultiShotPlanV2",
    "DirectRef2VMultiShotV2",
    "canonical_direct_ref2v_multishot_plan_v2",
    "direct_ref2v_multishot_camera_directives_v2",
    "direct_ref2v_multishot_plan_schema_v2",
    "direct_ref2v_multishot_plan_warnings_v2",
    "direct_ref2v_multishot_writer_projection_v2",
    "lint_direct_ref2v_multishot_plan_v2",
    "parse_direct_ref2v_multishot_plan_v2",
]
