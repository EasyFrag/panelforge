"""Generic, supervised action plan for the direct multimodal Ref2V route."""

from __future__ import annotations

from enum import StrEnum
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


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class DirectRiskCategory(StrEnum):
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    IDENTITY = "identity"
    OBJECT = "object"
    PHYSICAL = "physical"
    REFERENCE = "reference"
    OTHER = "other"


class DirectActionStep(_StrictModel):
    step_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    action: str = Field(min_length=1)
    continuity_after: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self) -> DirectActionStep:
        if self.end_ms <= self.start_ms:
            raise ValueError("step end_ms must be greater than start_ms")
        return self


class DirectActionBeat(_StrictModel):
    beat_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    primary_action: str = Field(min_length=1)
    participants: tuple[str, ...] = Field(min_length=1)
    observable_end_state: str = Field(min_length=1)
    steps: tuple[DirectActionStep, ...] = Field(min_length=1)

    @field_validator("participants")
    @classmethod
    def validate_participants(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("participants must contain non-empty identifiers")
        return values

    @model_validator(mode="after")
    def validate_steps(self) -> DirectActionBeat:
        if self.end_ms <= self.start_ms:
            raise ValueError("beat end_ms must be greater than start_ms")
        if len(self.participants) != len(set(self.participants)):
            raise ValueError(f"beat {self.beat_id} participants must be unique")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError(f"beat {self.beat_id} step IDs must be unique")
        cursor = self.start_ms
        for step in self.steps:
            if step.start_ms != cursor:
                raise ValueError(f"beat {self.beat_id} steps must be contiguous")
            if step.end_ms > self.end_ms:
                raise ValueError(f"beat {self.beat_id} step exceeds its interval")
            cursor = step.end_ms
        if cursor != self.end_ms:
            raise ValueError(f"beat {self.beat_id} steps must cover the full beat")
        return self


class DirectFinalState(_StrictModel):
    start_ms: int = Field(ge=0)
    description: str = Field(min_length=1)
    hold_until_end: Literal[True]


class DirectFinalStateV2(_StrictModel):
    """Final state authored by the planner, without redundant timestamps."""

    description: str = Field(min_length=1)
    final_hold_ms: int = Field(ge=0)


class DirectCameraPlan(_StrictModel):
    directive_id: str = Field(pattern=r"^camera_[1-3]$")
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None = None
    speed: H3CameraSpeed | None = None
    target_clause: str | None = Field(default=None, min_length=1)
    visible_change: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_directive(self) -> DirectCameraPlan:
        if self.end_ms <= self.start_ms:
            raise ValueError("camera end_ms must be greater than start_ms")
        H3CameraDirective(
            directive_id=self.directive_id,
            motion=self.motion,
            amplitude=self.amplitude,
            speed=self.speed,
            target_clause=self.target_clause or "",
        )
        return self


class DirectContinuityRisk(_StrictModel):
    risk_id: str = Field(min_length=1)
    category: DirectRiskCategory
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    resolution: str | None = Field(default=None, min_length=1)


class DirectRef2VActionPlan(_StrictModel):
    duration_seconds: int = Field(ge=1)
    scene_setup: str = Field(min_length=1)
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    beats: tuple[DirectActionBeat, ...] = Field(min_length=1)
    final_state: DirectFinalState
    camera_directives: tuple[DirectCameraPlan, ...] = Field(max_length=3)
    risks: tuple[DirectContinuityRisk, ...]
    technical_adjustments: tuple[str, ...] = ()
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @field_validator("continuity_invariants", "technical_adjustments")
    @classmethod
    def validate_text_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("text lists must contain non-empty values")
        return values

    @model_validator(mode="after")
    def validate_timeline(self) -> DirectRef2VActionPlan:
        beat_ids = [beat.beat_id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("beat IDs must be unique")
        cursor = 0
        for beat in self.beats:
            if beat.start_ms < cursor:
                raise ValueError("beats must be sequential and non-overlapping")
            cursor = beat.end_ms
        duration_ms = self.duration_seconds * 1000
        if cursor > duration_ms:
            raise ValueError("a beat exceeds the planned duration")
        if self.final_state.start_ms < cursor:
            raise ValueError("final_state must start after the last beat")
        if self.final_state.start_ms >= duration_ms:
            raise ValueError("final_state must start before the video ends")
        directive_ids = [item.directive_id for item in self.camera_directives]
        if len(directive_ids) != len(set(directive_ids)):
            raise ValueError("camera directive IDs must be unique")
        expected_ids = [f"camera_{index}" for index in range(1, len(directive_ids) + 1)]
        if directive_ids != expected_ids:
            raise ValueError("camera directive IDs must be contiguous and chronological")
        camera_cursor = 0
        for directive in self.camera_directives:
            if directive.start_ms < camera_cursor:
                raise ValueError("camera directives must be chronological and non-overlapping")
            if directive.end_ms > duration_ms:
                raise ValueError("a camera directive exceeds the planned duration")
            camera_cursor = directive.end_ms
        risk_ids = [risk.risk_id for risk in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk IDs must be unique")
        if len(self.technical_adjustments) != len(set(self.technical_adjustments)):
            raise ValueError("technical_adjustments must not contain duplicates")
        return self


class DirectRef2VActionPlanV2(_StrictModel):
    """Direct plan whose total duration is derived from its authored actions."""

    scene_setup: str = Field(min_length=1)
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    beats: tuple[DirectActionBeat, ...] = Field(min_length=1)
    final_state: DirectFinalStateV2
    camera_directives: tuple[DirectCameraPlan, ...] = Field(max_length=3)
    risks: tuple[DirectContinuityRisk, ...]
    technical_adjustments: tuple[str, ...] = ()
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @field_validator("continuity_invariants", "technical_adjustments")
    @classmethod
    def validate_text_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("text lists must contain non-empty values")
        return values

    @property
    def final_start_ms(self) -> int:
        return self.beats[-1].end_ms

    @property
    def duration_ms(self) -> int:
        return self.final_start_ms + self.final_state.final_hold_ms

    @model_validator(mode="after")
    def validate_timeline(self) -> DirectRef2VActionPlanV2:
        beat_ids = [beat.beat_id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("beat IDs must be unique")
        cursor = 0
        for beat in self.beats:
            if beat.start_ms < cursor:
                raise ValueError("beats must be sequential and non-overlapping")
            cursor = beat.end_ms
        directive_ids = [item.directive_id for item in self.camera_directives]
        if len(directive_ids) != len(set(directive_ids)):
            raise ValueError("camera directive IDs must be unique")
        expected_ids = [f"camera_{index}" for index in range(1, len(directive_ids) + 1)]
        if directive_ids != expected_ids:
            raise ValueError("camera directive IDs must be contiguous and chronological")
        camera_cursor = 0
        for directive in self.camera_directives:
            if directive.start_ms < camera_cursor:
                raise ValueError("camera directives must be chronological and non-overlapping")
            if directive.end_ms > self.duration_ms:
                raise ValueError("a camera directive exceeds the derived duration")
            camera_cursor = directive.end_ms
        risk_ids = [risk.risk_id for risk in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk IDs must be unique")
        if len(self.technical_adjustments) != len(set(self.technical_adjustments)):
            raise ValueError("technical_adjustments must not contain duplicates")
        return self


def direct_ref2v_action_plan_schema() -> str:
    """Return the exact closed JSON schema supplied to the local planner."""

    schema = DirectRef2VActionPlan.model_json_schema()
    # The planner never owns this field. The application may add entries only
    # after a deterministic recovery, while persisted plans remain parseable.
    schema["properties"]["technical_adjustments"]["maxItems"] = 0
    return json.dumps(schema, ensure_ascii=False, indent=2)


def direct_ref2v_action_plan_schema_v2() -> str:
    """Return the V2 schema, excluding all application-derived timestamps."""

    schema = DirectRef2VActionPlanV2.model_json_schema()
    schema["properties"]["technical_adjustments"]["maxItems"] = 0
    return json.dumps(schema, ensure_ascii=False, indent=2)


def parse_direct_ref2v_action_plan(content: str) -> DirectRef2VActionPlan:
    """Extract and validate one direct Ref2V JSON plan."""

    value = _json_object(content)
    try:
        return DirectRef2VActionPlan.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V action plan: {error}") from error


def parse_direct_ref2v_action_plan_v2(content: str) -> DirectRef2VActionPlanV2:
    """Extract and validate one V2 direct Ref2V JSON plan."""

    value = _json_object(content)
    try:
        return DirectRef2VActionPlanV2.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V action plan V2: {error}") from error


def canonical_direct_ref2v_action_plan(
    content: str,
    *,
    recover_invalid_target: bool = False,
) -> str:
    """Validate and serialize a plan; optionally drop only invalid camera targets."""

    value = _json_object(content)
    raw_adjustments = value.get("technical_adjustments", [])
    if raw_adjustments not in ([], ()):
        raise ValueError(
            "invalid direct Ref2V action plan: technical_adjustments is "
            "application-owned and must be empty"
        )
    if recover_invalid_target:
        _drop_invalid_camera_targets(value)
    try:
        plan = DirectRef2VActionPlan.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V action plan: {error}") from error
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def canonical_direct_ref2v_action_plan_v2(
    content: str,
    *,
    recover_invalid_target: bool = False,
) -> str:
    """Validate V2 while optionally recovering only invalid camera targets."""

    value = _json_object(content)
    raw_adjustments = value.get("technical_adjustments", [])
    if raw_adjustments not in ([], ()):
        raise ValueError(
            "invalid direct Ref2V action plan V2: technical_adjustments is "
            "application-owned and must be empty"
        )
    if recover_invalid_target:
        _drop_invalid_camera_targets(value)
    try:
        plan = DirectRef2VActionPlanV2.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid direct Ref2V action plan V2: {error}") from error
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def lint_direct_ref2v_action_plan(content: str) -> tuple[str, ...]:
    try:
        parse_direct_ref2v_action_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def lint_direct_ref2v_action_plan_v2(content: str) -> tuple[str, ...]:
    try:
        parse_direct_ref2v_action_plan_v2(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def direct_ref2v_action_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_direct_ref2v_action_plan(content)
    except (TypeError, ValueError):
        return ()
    warnings: list[str] = []
    if plan.duration_seconds > 15:
        warnings.append(
            "La durée planifiée dépasse 15 secondes ; vérifiez la durée acceptée "
            "par le moteur vidéo ciblé."
        )
    unresolved = [risk.risk_id for risk in plan.risks if risk.resolution is None]
    if unresolved:
        warnings.append(
            "Arbitrage conseillé pour : " + ", ".join(unresolved) + "."
        )
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


def direct_ref2v_action_plan_warnings_v2(content: str) -> tuple[str, ...]:
    try:
        plan = parse_direct_ref2v_action_plan_v2(content)
    except (TypeError, ValueError):
        return ()
    warnings: list[str] = []
    final_hold_ms = plan.final_state.final_hold_ms
    if final_hold_ms == 0:
        warnings.append(
            "Aucune tenue finale n'est planifiee ; verifiez que l'etat final reste lisible."
        )
    elif final_hold_ms < 1000:
        warnings.append(
            "La tenue finale planifiee est inferieure a 1 seconde ; verifiez sa lisibilite."
        )
    if plan.duration_ms > 15_000:
        warnings.append(
            "La duree derivee depasse 15 secondes ; verifiez la duree acceptee "
            "par le moteur video cible."
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


def direct_ref2v_camera_directives(
    content: str,
) -> tuple[H3CameraDirective, ...]:
    plan = parse_direct_ref2v_action_plan(content)
    return tuple(
        H3CameraDirective(
            directive_id=item.directive_id,
            motion=item.motion,
            amplitude=item.amplitude,
            speed=item.speed,
            target_clause=item.target_clause or "",
        )
        for item in plan.camera_directives
    )


def direct_ref2v_camera_directives_v2(
    content: str,
) -> tuple[H3CameraDirective, ...]:
    plan = parse_direct_ref2v_action_plan_v2(content)
    return tuple(
        H3CameraDirective(
            directive_id=item.directive_id,
            motion=item.motion,
            amplitude=item.amplitude,
            speed=item.speed,
            target_clause=item.target_clause or "",
        )
        for item in plan.camera_directives
    )


def direct_ref2v_writer_plan(content: str) -> str:
    """Return stable canonical JSON for the prose writer."""

    plan = parse_direct_ref2v_action_plan(content)
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def direct_ref2v_writer_plan_v2(content: str) -> str:
    """Return canonical V2 JSON enriched only in the writer-facing copy."""

    plan = parse_direct_ref2v_action_plan_v2(content)
    writer_value = plan.model_dump(mode="json")
    writer_value["derived_timing"] = {
        "final_state_start_ms": plan.final_start_ms,
        "duration_ms": plan.duration_ms,
        "duration_seconds": plan.duration_ms / 1000,
    }
    return json.dumps(writer_value, ensure_ascii=False, indent=2)


def _json_object(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("direct Ref2V action plan must not be empty")
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1])
            if value.lstrip().lower().startswith("json\n"):
                value = value.lstrip()[5:]
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid direct Ref2V action-plan JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise ValueError("direct Ref2V action plan must be one JSON object")
    return decoded


def _drop_invalid_camera_targets(value: dict[str, object]) -> None:
    raw_directives = value.get("camera_directives")
    if not isinstance(raw_directives, list):
        return
    adjustments = value.get("technical_adjustments")
    if not isinstance(adjustments, list):
        adjustments = []
        value["technical_adjustments"] = adjustments
    for item in raw_directives:
        if not isinstance(item, dict) or not item.get("target_clause"):
            continue
        try:
            DirectCameraPlan.model_validate(item)
            continue
        except ValidationError:
            candidate = dict(item)
            candidate["target_clause"] = None
            try:
                DirectCameraPlan.model_validate(candidate)
            except ValidationError:
                continue
        item["target_clause"] = None
        marker = f"camera_target_dropped:{item.get('directive_id', 'unknown')}"
        if marker not in adjustments:
            adjustments.append(marker)
