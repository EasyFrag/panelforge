"""Validated choreography plan for the planned Ref2V cookbook."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class MotionType(StrEnum):
    OVER_HEAD_REMOVAL = "over_head_removal"
    STEP_OUT_REMOVAL = "step_out_removal"
    SIMPLE_REMOVAL = "simple_removal"
    OTHER = "other"


class ActionComplexity(StrEnum):
    SIMPLE = "simple"
    MULTI_STEP = "multi_step"


class CameraPath(StrEnum):
    PEDESTAL = "pedestal"
    DOLLY = "dolly"
    ORBIT = "orbit"
    CRANE = "crane"
    HANDHELD = "handheld"
    OTHER = "other"


class ContinuityConcernCategory(StrEnum):
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"
    HAND_OBJECT_CONTINUITY = "hand_object_continuity"
    STATE_VISIBILITY_CONFLICT = "state_visibility_conflict"
    REFERENCE_INFLUENCE = "reference_influence"
    PHYSICAL_PLAUSIBILITY = "physical_plausibility"
    OTHER = "other"


class RetimingAdjustment(StrEnum):
    DURATION_EXTENDED = "duration_extended"
    FINAL_HOLD_REPAIRED = "final_hold_repaired"
    FINAL_HOLD_REDUCED = "final_hold_reduced"
    CAMERA_RESCHEDULED = "camera_rescheduled"
    CAMERA_SHORTENED = "camera_shortened"
    MARGINS_CAPPED = "margins_capped"
    DURATION_OVER_15 = "duration_over_15"


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ReferencePolicy(_StrictModel):
    picture_1: Literal["exact_first_frame"]
    picture_2: Literal["appearance_only"]


class ActionBeat(_StrictModel):
    beat_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    action: str = Field(min_length=1)
    object: str = Field(min_length=1)
    motion_type: MotionType
    hand_contact: str = Field(min_length=1)
    motion_path: str = Field(min_length=1)
    required_end_state: str = Field(min_length=1)
    expression: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self) -> ActionBeat:
        if self.end_ms <= self.start_ms:
            raise ValueError("action beat end_ms must be greater than start_ms")
        return self


class FinalPose(_StrictModel):
    start_ms: int = Field(ge=0)
    description: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    hold_until_end: Literal[True]


class CameraPlan(_StrictModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    movement: str = Field(min_length=1)
    visible_perspective_change: str = Field(min_length=1)
    frontal_axis: Literal[True]
    during: Literal["held_final_pose"]

    @model_validator(mode="after")
    def validate_interval(self) -> CameraPlan:
        if self.end_ms <= self.start_ms:
            raise ValueError("camera end_ms must be greater than start_ms")
        return self


class ActionBeatV2(ActionBeat):
    complexity: ActionComplexity


class ActionSubstep(_StrictModel):
    substep_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    action: str = Field(min_length=1)
    left_hand: str = Field(min_length=1)
    right_hand: str = Field(min_length=1)
    object_state_after: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self) -> ActionSubstep:
        if self.end_ms <= self.start_ms:
            raise ValueError("action substep end_ms must be greater than start_ms")
        return self


class ActionBeatV3(ActionBeatV2):
    substeps: tuple[ActionSubstep, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_substeps(self) -> ActionBeatV3:
        substep_ids = [substep.substep_id for substep in self.substeps]
        if len(substep_ids) != len(set(substep_ids)):
            raise ValueError(f"action beat {self.beat_id} has duplicate substep IDs")
        cursor_ms = self.start_ms
        for substep in self.substeps:
            if substep.start_ms != cursor_ms:
                raise ValueError(
                    f"action beat {self.beat_id} substeps must be contiguous"
                )
            if substep.end_ms > self.end_ms:
                raise ValueError(
                    f"action beat {self.beat_id} substep exceeds its beat"
                )
            cursor_ms = substep.end_ms
        if cursor_ms != self.end_ms:
            raise ValueError(
                f"action beat {self.beat_id} substeps must cover the complete beat"
            )
        return self


class ContinuityConcern(_StrictModel):
    concern_id: str = Field(min_length=1)
    category: ContinuityConcernCategory
    description: str = Field(min_length=1)
    proposed_resolution: str = Field(min_length=1)
    resolution: str | None = Field(default=None, min_length=1)


class CameraPlanV2(_StrictModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    path_type: CameraPath
    movement: str = Field(min_length=1)
    visible_perspective_change: str = Field(min_length=1)
    during: Literal["held_final_pose"]

    @model_validator(mode="after")
    def validate_interval(self) -> CameraPlanV2:
        if self.end_ms <= self.start_ms:
            raise ValueError("camera end_ms must be greater than start_ms")
        return self


class Ref2VActionPlan(_StrictModel):
    duration_seconds: int = Field(ge=4, le=15)
    reference_policy: ReferencePolicy
    scene_setup: str = Field(min_length=1)
    beats: tuple[ActionBeat, ...] = Field(min_length=1, max_length=6)
    final_pose: FinalPose
    camera: CameraPlan | None
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timeline(self) -> Ref2VActionPlan:
        _validate_timeline(
            self.duration_seconds,
            self.beats,
            self.final_pose,
            self.camera,
            lambda beat: _BASE_MINIMUM_DURATIONS[beat.motion_type],
        )
        return self


class Ref2VActionPlanV2(_StrictModel):
    duration_seconds: int = Field(ge=4, le=15)
    reference_policy: ReferencePolicy
    scene_setup: str = Field(min_length=1)
    beats: tuple[ActionBeatV2, ...] = Field(min_length=1, max_length=6)
    final_pose: FinalPose
    camera: CameraPlanV2 | None
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timeline(self) -> Ref2VActionPlanV2:
        _validate_timeline(
            self.duration_seconds,
            self.beats,
            self.final_pose,
            self.camera,
            lambda beat: _BASE_MINIMUM_DURATIONS[beat.motion_type]
            + (1500 if beat.complexity is ActionComplexity.MULTI_STEP else 0),
            enforce_motion_margins=False,
        )
        return self


class Ref2VElasticActionPlan(Ref2VActionPlanV2):
    requested_duration_seconds: int = Field(ge=4, le=15)

    @model_validator(mode="after")
    def validate_requested_duration(self) -> Ref2VElasticActionPlan:
        if self.requested_duration_seconds > self.duration_seconds:
            raise ValueError("requested duration must not exceed planned duration")
        return self


class Ref2VBoundedActionPlan(Ref2VElasticActionPlan):
    timing_adjustments: tuple[RetimingAdjustment, ...] = ()


class Ref2VActionPlanV3(Ref2VActionPlanV2):
    """V0.7 planner contract: duration has no artificial 15-second ceiling."""

    duration_seconds: int = Field(ge=4)


class Ref2VRepairableActionPlan(_StrictModel):
    """V0.7.1 planner input: structurally ordered, but not duration-bound."""

    duration_seconds: int = Field(ge=4)
    reference_policy: ReferencePolicy
    scene_setup: str = Field(min_length=1)
    beats: tuple[ActionBeatV2, ...] = Field(min_length=1, max_length=6)
    final_pose: FinalPose
    camera: CameraPlanV2 | None
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_structure(self) -> Ref2VRepairableActionPlan:
        _validate_repairable_structure(self.beats, self.final_pose, self.camera)
        return self


class Ref2VSupervisedActionPlan(_StrictModel):
    """V0.8 planner output with editable atomic motion and continuity concerns."""

    duration_seconds: int = Field(ge=4)
    reference_policy: ReferencePolicy
    scene_setup: str = Field(min_length=1)
    beats: tuple[ActionBeatV3, ...] = Field(min_length=1, max_length=6)
    final_pose: FinalPose
    camera: CameraPlanV2 | None
    continuity_concerns: tuple[ContinuityConcern, ...] = Field(max_length=12)
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_structure(self) -> Ref2VSupervisedActionPlan:
        _validate_repairable_structure(self.beats, self.final_pose, self.camera)
        concern_ids = [concern.concern_id for concern in self.continuity_concerns]
        if len(concern_ids) != len(set(concern_ids)):
            raise ValueError("continuity concerns must have unique IDs")
        return self


class Ref2VAdvisoryActionPlan(Ref2VActionPlanV3):
    requested_duration_seconds: int = Field(ge=4)
    timing_adjustments: tuple[RetimingAdjustment, ...] = ()

    @model_validator(mode="after")
    def validate_requested_duration(self) -> Ref2VAdvisoryActionPlan:
        if self.requested_duration_seconds > self.duration_seconds:
            raise ValueError("requested duration must not exceed planned duration")
        return self


class Ref2VSupervisedCompiledPlan(Ref2VSupervisedActionPlan):
    requested_duration_seconds: int = Field(ge=4)
    timing_adjustments: tuple[RetimingAdjustment, ...] = ()

    @model_validator(mode="after")
    def validate_compiled_timeline(self) -> Ref2VSupervisedCompiledPlan:
        if self.requested_duration_seconds > self.duration_seconds:
            raise ValueError("requested duration must not exceed planned duration")
        duration_ms = self.duration_seconds * 1000
        if self.final_pose.start_ms >= duration_ms:
            raise ValueError("final pose must start before the video ends")
        if duration_ms - self.final_pose.start_ms < 2000:
            raise ValueError("final pose must remain visible for at least 2000 ms")
        if self.camera is not None and self.camera.end_ms > duration_ms:
            raise ValueError("camera movement exceeds the video duration")
        return self


_BASE_MINIMUM_DURATIONS = {
    MotionType.OVER_HEAD_REMOVAL: 3000,
    MotionType.STEP_OUT_REMOVAL: 3000,
    MotionType.SIMPLE_REMOVAL: 2000,
    MotionType.OTHER: 1000,
}


def _validate_repairable_structure(
    beats: tuple[ActionBeatV2, ...] | tuple[ActionBeatV3, ...],
    final_pose: FinalPose,
    camera: CameraPlanV2 | None,
) -> None:
    beat_ids = [beat.beat_id for beat in beats]
    if len(beat_ids) != len(set(beat_ids)):
        raise ValueError("action beat IDs must be unique")
    previous_end = 0
    for beat in beats:
        if beat.start_ms < previous_end:
            raise ValueError("action beats must be sequential and non-overlapping")
        previous_end = beat.end_ms
    if final_pose.start_ms < previous_end:
        raise ValueError("final pose must start after the last primary action")
    if camera is not None and camera.start_ms < final_pose.start_ms:
        raise ValueError("camera movement must start during the held final pose")


def _validate_timeline(
    duration_seconds: int,
    beats: tuple[ActionBeat, ...] | tuple[ActionBeatV2, ...],
    final_pose: FinalPose,
    camera: CameraPlan | CameraPlanV2 | None,
    minimum_duration: Callable[[ActionBeat | ActionBeatV2], int],
    *,
    enforce_motion_margins: bool = True,
) -> None:
    duration_ms = duration_seconds * 1000
    beat_ids = [beat.beat_id for beat in beats]
    if len(beat_ids) != len(set(beat_ids)):
        raise ValueError("action beat IDs must be unique")
    previous_end = 0
    for beat in beats:
        if beat.start_ms < previous_end:
            raise ValueError("action beats must be sequential and non-overlapping")
        if beat.end_ms > duration_ms:
            raise ValueError("action beat exceeds the video duration")
        if (
            enforce_motion_margins
            and beat.end_ms - beat.start_ms < minimum_duration(beat)
        ):
            raise ValueError(
                f"action beat {beat.beat_id} is too short for its motion and complexity"
            )
        previous_end = beat.end_ms
    if final_pose.start_ms < previous_end:
        raise ValueError("final pose must start after the last primary action")
    if final_pose.start_ms >= duration_ms:
        raise ValueError("final pose must start before the video ends")
    if duration_ms - final_pose.start_ms < 2000:
        raise ValueError("final pose must remain visible for at least 2000 ms")
    if camera is not None:
        if camera.start_ms < final_pose.start_ms:
            raise ValueError("camera movement must start during the held final pose")
        if camera.end_ms > duration_ms:
            raise ValueError("camera movement exceeds the video duration")
        if camera.end_ms - camera.start_ms < 1000:
            raise ValueError("camera movement must remain readable for at least 1000 ms")


def parse_ref2v_action_plan(content: str) -> Ref2VActionPlan:
    """Extract and validate one JSON action plan from a model response."""
    return _parse_plan(content, Ref2VActionPlan)


def canonical_ref2v_action_plan(content: str) -> str:
    plan = parse_ref2v_action_plan(content)
    return json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )


def ref2v_action_plan_schema() -> str:
    return json.dumps(
        Ref2VActionPlan.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )


def lint_ref2v_action_plan(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_action_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def parse_ref2v_action_plan_v2(content: str) -> Ref2VActionPlanV2:
    return _parse_plan(content, Ref2VActionPlanV2)


def canonical_ref2v_action_plan_v2(content: str) -> str:
    plan = parse_ref2v_action_plan_v2(content)
    return json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )


def ref2v_action_plan_schema_v2() -> str:
    return json.dumps(
        Ref2VActionPlanV2.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )


def parse_ref2v_action_plan_v3(content: str) -> Ref2VActionPlanV3:
    return _parse_plan(content, Ref2VActionPlanV3)


def ref2v_action_plan_schema_v3() -> str:
    return json.dumps(
        Ref2VActionPlanV3.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )


def parse_ref2v_repairable_action_plan(content: str) -> Ref2VRepairableActionPlan:
    return _parse_plan(content, Ref2VRepairableActionPlan)


def ref2v_repairable_action_plan_schema() -> str:
    return json.dumps(
        Ref2VRepairableActionPlan.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )


def parse_ref2v_supervised_action_plan(content: str) -> Ref2VSupervisedActionPlan:
    return _parse_plan(content, Ref2VSupervisedActionPlan)


def ref2v_supervised_action_plan_schema() -> str:
    return json.dumps(
        Ref2VSupervisedActionPlan.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )


def lint_ref2v_action_plan_v2(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_action_plan_v2(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def ref2v_action_plan_warnings_v2(content: str) -> tuple[str, ...]:
    """Report motion-readability margins without rejecting a V0.4 plan."""
    try:
        plan = parse_ref2v_action_plan_v2(content)
    except (TypeError, ValueError):
        return ()
    short_beats: list[str] = []
    minimum_actions_ms = 0
    for beat in plan.beats:
        minimum_ms = _BASE_MINIMUM_DURATIONS[beat.motion_type]
        if beat.complexity is ActionComplexity.MULTI_STEP:
            minimum_ms += 1500
        minimum_actions_ms += minimum_ms
        if beat.end_ms - beat.start_ms < minimum_ms:
            short_beats.append(beat.beat_id)
    if not short_beats:
        return ()
    estimated_ms = minimum_actions_ms + 2000
    beat_list = ", ".join(short_beats)
    if estimated_ms > plan.duration_seconds * 1000:
        return (
            "Chronologie dense : "
            f"{beat_list} passe sous les marges de mouvement recommandées. "
            f"Durée minimale estimée : {estimated_ms / 1000:g} s au lieu de "
            f"{plan.duration_seconds} s. Le prompt est généré sans blocage.",
        )
    return (
        "Chronologie serrée : "
        f"{beat_list} passe sous les marges de mouvement recommandées. "
        "Le prompt est généré sans blocage ; une redistribution des timings est conseillée.",
    )


def retime_ref2v_action_plan_v2(content: str) -> str:
    """Expand short V0.4 beats deterministically while preserving their order."""
    plan = parse_ref2v_action_plan_v2(content)
    data = plan.model_dump(mode="json")
    requested_duration_ms = plan.duration_seconds * 1000
    cursor_ms = 0
    previous_original_end_ms = 0
    for beat, beat_data in zip(plan.beats, data["beats"], strict=True):
        gap_ms = beat.start_ms - previous_original_end_ms
        cursor_ms += gap_ms
        duration_ms = max(
            beat.end_ms - beat.start_ms,
            _recommended_motion_duration_ms(beat),
        )
        beat_data["start_ms"] = cursor_ms
        beat_data["end_ms"] = cursor_ms + duration_ms
        cursor_ms += duration_ms
        previous_original_end_ms = beat.end_ms

    final_gap_ms = plan.final_pose.start_ms - previous_original_end_ms
    final_start_ms = cursor_ms + final_gap_ms
    original_hold_ms = requested_duration_ms - plan.final_pose.start_ms
    planned_duration_ms = final_start_ms + max(2000, original_hold_ms)
    planned_duration_seconds = math.ceil(planned_duration_ms / 1000)
    if planned_duration_seconds > 15:
        raise ValueError(
            "elastic Ref2V timeline exceeds the supported 15 second maximum"
        )
    data["final_pose"]["start_ms"] = final_start_ms
    if plan.camera is not None:
        camera_start_offset_ms = plan.camera.start_ms - plan.final_pose.start_ms
        camera_end_offset_ms = plan.camera.end_ms - plan.final_pose.start_ms
        data["camera"]["start_ms"] = final_start_ms + camera_start_offset_ms
        data["camera"]["end_ms"] = final_start_ms + camera_end_offset_ms
    data["requested_duration_seconds"] = plan.duration_seconds
    data["duration_seconds"] = planned_duration_seconds
    elastic = Ref2VElasticActionPlan.model_validate(data)
    return json.dumps(elastic.model_dump(mode="json"), ensure_ascii=False, indent=2)


def retime_ref2v_bounded_action_plan(content: str) -> str:
    """Fit multi-step readability margins into the existing timeline before extending it."""
    plan = parse_ref2v_action_plan_v2(content)
    data = plan.model_dump(mode="json")
    requested_duration_ms = plan.duration_seconds * 1000
    maximum_duration_ms = 15_000
    minimum_final_hold_ms = 2_000

    desired_expansions = tuple(
        max(
            0,
            _recommended_motion_duration_ms(beat)
            - (beat.end_ms - beat.start_ms),
        )
        if beat.complexity is ActionComplexity.MULTI_STEP
        else 0
        for beat in plan.beats
    )
    expansion_capacity_ms = max(
        0,
        maximum_duration_ms - minimum_final_hold_ms - plan.final_pose.start_ms,
    )
    applied_expansions = _allocate_expansions(
        desired_expansions,
        expansion_capacity_ms,
    )
    adjustments: list[RetimingAdjustment] = []
    if sum(applied_expansions) < sum(desired_expansions):
        adjustments.append(RetimingAdjustment.MARGINS_CAPPED)

    cursor_ms = 0
    previous_original_end_ms = 0
    for beat, beat_data, expansion_ms in zip(
        plan.beats,
        data["beats"],
        applied_expansions,
        strict=True,
    ):
        gap_ms = beat.start_ms - previous_original_end_ms
        cursor_ms += gap_ms
        duration_ms = beat.end_ms - beat.start_ms + expansion_ms
        beat_data["start_ms"] = cursor_ms
        beat_data["end_ms"] = cursor_ms + duration_ms
        cursor_ms += duration_ms
        previous_original_end_ms = beat.end_ms

    final_gap_ms = plan.final_pose.start_ms - previous_original_end_ms
    final_start_ms = cursor_ms + final_gap_ms
    minimum_planned_duration_ms = final_start_ms + minimum_final_hold_ms
    planned_duration_ms = max(
        requested_duration_ms,
        _ceil_to_second(minimum_planned_duration_ms),
    )
    planned_duration_ms = min(maximum_duration_ms, planned_duration_ms)
    if planned_duration_ms > requested_duration_ms:
        adjustments.append(RetimingAdjustment.DURATION_EXTENDED)

    original_hold_ms = requested_duration_ms - plan.final_pose.start_ms
    planned_hold_ms = planned_duration_ms - final_start_ms
    if planned_hold_ms < original_hold_ms:
        adjustments.append(RetimingAdjustment.FINAL_HOLD_REDUCED)
    data["final_pose"]["start_ms"] = final_start_ms

    if plan.camera is not None:
        original_camera_delay_ms = plan.camera.start_ms - plan.final_pose.start_ms
        original_camera_duration_ms = plan.camera.end_ms - plan.camera.start_ms
        camera_duration_ms = min(original_camera_duration_ms, planned_hold_ms)
        camera_delay_ms = min(
            original_camera_delay_ms,
            planned_hold_ms - camera_duration_ms,
        )
        camera_start_ms = final_start_ms + camera_delay_ms
        data["camera"]["start_ms"] = camera_start_ms
        data["camera"]["end_ms"] = camera_start_ms + camera_duration_ms
        if camera_delay_ms != original_camera_delay_ms:
            adjustments.append(RetimingAdjustment.CAMERA_RESCHEDULED)
        if camera_duration_ms != original_camera_duration_ms:
            adjustments.append(RetimingAdjustment.CAMERA_SHORTENED)

    data["requested_duration_seconds"] = plan.duration_seconds
    data["duration_seconds"] = planned_duration_ms // 1000
    data["timing_adjustments"] = [adjustment.value for adjustment in adjustments]
    bounded = Ref2VBoundedActionPlan.model_validate(data)
    return json.dumps(bounded.model_dump(mode="json"), ensure_ascii=False, indent=2)


def retime_ref2v_advisory_action_plan(content: str) -> str:
    """Preserve requested motion and camera margins, extending without a hard ceiling."""
    plan = parse_ref2v_action_plan_v3(content)
    data = plan.model_dump(mode="json")
    requested_duration_ms = plan.duration_seconds * 1000

    cursor_ms = 0
    previous_original_end_ms = 0
    for beat, beat_data in zip(plan.beats, data["beats"], strict=True):
        gap_ms = beat.start_ms - previous_original_end_ms
        cursor_ms += gap_ms
        desired_expansion_ms = (
            max(
                0,
                _recommended_motion_duration_ms(beat)
                - (beat.end_ms - beat.start_ms),
            )
            if beat.complexity is ActionComplexity.MULTI_STEP
            else 0
        )
        duration_ms = beat.end_ms - beat.start_ms + desired_expansion_ms
        beat_data["start_ms"] = cursor_ms
        beat_data["end_ms"] = cursor_ms + duration_ms
        cursor_ms += duration_ms
        previous_original_end_ms = beat.end_ms

    final_gap_ms = plan.final_pose.start_ms - previous_original_end_ms
    final_start_ms = cursor_ms + final_gap_ms
    original_hold_ms = requested_duration_ms - plan.final_pose.start_ms
    planned_duration_ms = final_start_ms + max(2000, original_hold_ms)
    data["final_pose"]["start_ms"] = final_start_ms

    if plan.camera is not None:
        original_camera_delay_ms = plan.camera.start_ms - plan.final_pose.start_ms
        original_camera_duration_ms = plan.camera.end_ms - plan.camera.start_ms
        camera_start_ms = final_start_ms + original_camera_delay_ms
        camera_end_ms = camera_start_ms + original_camera_duration_ms
        data["camera"]["start_ms"] = camera_start_ms
        data["camera"]["end_ms"] = camera_end_ms
        planned_duration_ms = max(planned_duration_ms, camera_end_ms)

    planned_duration_ms = _ceil_to_second(planned_duration_ms)
    adjustments: list[RetimingAdjustment] = []
    if planned_duration_ms > requested_duration_ms:
        adjustments.append(RetimingAdjustment.DURATION_EXTENDED)
    if planned_duration_ms > 15_000:
        adjustments.append(RetimingAdjustment.DURATION_OVER_15)

    data["requested_duration_seconds"] = plan.duration_seconds
    data["duration_seconds"] = planned_duration_ms // 1000
    data["timing_adjustments"] = [adjustment.value for adjustment in adjustments]
    advisory = Ref2VAdvisoryActionPlan.model_validate(data)
    return json.dumps(advisory.model_dump(mode="json"), ensure_ascii=False, indent=2)


def retime_ref2v_repairable_action_plan(content: str) -> str:
    """Repair a missing final hold, then apply the V0.7 advisory retiming policy."""
    plan = parse_ref2v_repairable_action_plan(content)
    data = plan.model_dump(mode="json")
    requested_duration_ms = plan.duration_seconds * 1000

    cursor_ms = 0
    previous_original_end_ms = 0
    for beat, beat_data in zip(plan.beats, data["beats"], strict=True):
        gap_ms = beat.start_ms - previous_original_end_ms
        cursor_ms += gap_ms
        desired_expansion_ms = (
            max(
                0,
                _recommended_motion_duration_ms(beat)
                - (beat.end_ms - beat.start_ms),
            )
            if beat.complexity is ActionComplexity.MULTI_STEP
            else 0
        )
        duration_ms = beat.end_ms - beat.start_ms + desired_expansion_ms
        beat_data["start_ms"] = cursor_ms
        beat_data["end_ms"] = cursor_ms + duration_ms
        cursor_ms += duration_ms
        previous_original_end_ms = beat.end_ms

    final_gap_ms = plan.final_pose.start_ms - previous_original_end_ms
    final_start_ms = cursor_ms + final_gap_ms
    original_hold_ms = max(0, requested_duration_ms - plan.final_pose.start_ms)
    planned_duration_ms = final_start_ms + max(2000, original_hold_ms)
    data["final_pose"]["start_ms"] = final_start_ms

    if plan.camera is not None:
        original_camera_delay_ms = plan.camera.start_ms - plan.final_pose.start_ms
        original_camera_duration_ms = plan.camera.end_ms - plan.camera.start_ms
        camera_start_ms = final_start_ms + original_camera_delay_ms
        camera_end_ms = camera_start_ms + original_camera_duration_ms
        data["camera"]["start_ms"] = camera_start_ms
        data["camera"]["end_ms"] = camera_end_ms
        planned_duration_ms = max(planned_duration_ms, camera_end_ms)

    planned_duration_ms = _ceil_to_second(planned_duration_ms)
    adjustments: list[RetimingAdjustment] = []
    if original_hold_ms < 2000:
        adjustments.append(RetimingAdjustment.FINAL_HOLD_REPAIRED)
    if planned_duration_ms > requested_duration_ms:
        adjustments.append(RetimingAdjustment.DURATION_EXTENDED)
    if planned_duration_ms > 15_000:
        adjustments.append(RetimingAdjustment.DURATION_OVER_15)

    data["requested_duration_seconds"] = plan.duration_seconds
    data["duration_seconds"] = planned_duration_ms // 1000
    data["timing_adjustments"] = [adjustment.value for adjustment in adjustments]
    repaired = Ref2VAdvisoryActionPlan.model_validate(data)
    return json.dumps(repaired.model_dump(mode="json"), ensure_ascii=False, indent=2)


def retime_ref2v_supervised_action_plan(content: str) -> str:
    """Compile user-editable timings without guessing how long an action should take."""
    plan = parse_ref2v_supervised_action_plan(content)
    data = plan.model_dump(mode="json")
    requested_duration_ms = plan.duration_seconds * 1000
    original_hold_ms = max(0, requested_duration_ms - plan.final_pose.start_ms)
    planned_duration_ms = plan.final_pose.start_ms + max(2000, original_hold_ms)

    if plan.camera is not None:
        planned_duration_ms = max(planned_duration_ms, plan.camera.end_ms)

    planned_duration_ms = _ceil_to_second(planned_duration_ms)
    adjustments: list[RetimingAdjustment] = []
    if original_hold_ms < 2000:
        adjustments.append(RetimingAdjustment.FINAL_HOLD_REPAIRED)
    if planned_duration_ms > requested_duration_ms:
        adjustments.append(RetimingAdjustment.DURATION_EXTENDED)
    if planned_duration_ms > 15_000:
        adjustments.append(RetimingAdjustment.DURATION_OVER_15)

    data["requested_duration_seconds"] = plan.duration_seconds
    data["duration_seconds"] = planned_duration_ms // 1000
    data["timing_adjustments"] = [adjustment.value for adjustment in adjustments]
    compiled = Ref2VSupervisedCompiledPlan.model_validate(data)
    return json.dumps(compiled.model_dump(mode="json"), ensure_ascii=False, indent=2)


def parse_ref2v_elastic_action_plan(content: str) -> Ref2VElasticActionPlan:
    return _parse_plan(content, Ref2VElasticActionPlan)


def parse_ref2v_bounded_action_plan(content: str) -> Ref2VBoundedActionPlan:
    return _parse_plan(content, Ref2VBoundedActionPlan)


def parse_ref2v_advisory_action_plan(content: str) -> Ref2VAdvisoryActionPlan:
    return _parse_plan(content, Ref2VAdvisoryActionPlan)


def parse_ref2v_supervised_compiled_plan(content: str) -> Ref2VSupervisedCompiledPlan:
    return _parse_plan(content, Ref2VSupervisedCompiledPlan)


def lint_ref2v_elastic_action_plan(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_elastic_action_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def lint_ref2v_bounded_action_plan(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_bounded_action_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def lint_ref2v_advisory_action_plan(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_advisory_action_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def lint_ref2v_supervised_compiled_plan(content: str) -> tuple[str, ...]:
    try:
        parse_ref2v_supervised_compiled_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def ref2v_elastic_action_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_elastic_action_plan(content)
    except (TypeError, ValueError):
        return ()
    if plan.duration_seconds == plan.requested_duration_seconds:
        return ()
    return (
        f"Durée planifiée étendue automatiquement de "
        f"{plan.requested_duration_seconds} s à {plan.duration_seconds} s "
        "pour préserver la lisibilité des gestes.",
    )


def ref2v_bounded_action_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_bounded_action_plan(content)
    except (TypeError, ValueError):
        return ()
    messages = {
        RetimingAdjustment.FINAL_HOLD_REDUCED: (
            "La marge de la pose finale a été utilisée pour préserver la lisibilité "
            "des transformations."
        ),
        RetimingAdjustment.CAMERA_RESCHEDULED: (
            "La caméra a été recalée dans la fenêtre restante de la pose finale."
        ),
        RetimingAdjustment.CAMERA_SHORTENED: (
            "La caméra a été raccourcie avant de prolonger davantage la vidéo."
        ),
        RetimingAdjustment.MARGINS_CAPPED: (
            "Le plafond de 15 s est atteint : certaines marges recommandées restent "
            "partiellement compressées, sans bloquer la génération."
        ),
    }
    warnings: list[str] = []
    if RetimingAdjustment.DURATION_EXTENDED in plan.timing_adjustments:
        warnings.append(
            "Durée planifiée étendue automatiquement de "
            f"{plan.requested_duration_seconds} s à {plan.duration_seconds} s."
        )
    warnings.extend(
        messages[adjustment]
        for adjustment in plan.timing_adjustments
        if adjustment in messages
    )
    return tuple(warnings)


def ref2v_advisory_action_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_advisory_action_plan(content)
    except (TypeError, ValueError):
        return ()
    return _advisory_timing_warnings(
        plan.requested_duration_seconds,
        plan.duration_seconds,
        plan.timing_adjustments,
    )


def _advisory_timing_warnings(
    requested_duration_seconds: int,
    duration_seconds: int,
    adjustments: tuple[RetimingAdjustment, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if RetimingAdjustment.FINAL_HOLD_REPAIRED in adjustments:
        warnings.append(
            "Le plan LLM ne réservait pas les 2 s nécessaires à la pose finale ; "
            "la chronologie a été prolongée automatiquement sans relancer le planner."
        )
    if RetimingAdjustment.DURATION_EXTENDED in adjustments:
        warnings.append(
            "Durée planifiée étendue automatiquement de "
            f"{requested_duration_seconds} s à {duration_seconds} s."
        )
    if RetimingAdjustment.DURATION_OVER_15 in adjustments:
        warnings.append(
            f"La durée planifiée de {duration_seconds} s dépasse 15 s. "
            "La génération reste autorisée ; vérifiez la capacité du moteur vidéo ciblé."
        )
    return tuple(warnings)


def ref2v_supervised_action_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_ref2v_supervised_compiled_plan(content)
    except (TypeError, ValueError):
        return ()
    warnings = list(_advisory_timing_warnings(
        plan.requested_duration_seconds,
        plan.duration_seconds,
        plan.timing_adjustments,
    ))
    for concern in plan.continuity_concerns:
        if concern.resolution is None:
            warnings.append(
                f"Arbitrage conseillé [{concern.category.value} / {concern.concern_id}] : "
                f"{concern.description} Proposition : {concern.proposed_resolution}"
            )
    if plan.camera is not None and plan.camera.end_ms - plan.camera.start_ms < 1000:
        warnings.append(
            "Le mouvement de caméra proposé dure moins d’une seconde ; il peut être "
            "peu lisible, mais le plan reste validable."
        )
    return tuple(warnings)


def ref2v_elastic_writer_plan(content: str) -> str:
    """Hide planning provenance from the writer's timing contract."""
    plan = parse_ref2v_elastic_action_plan(content)
    data = plan.model_dump(mode="json", exclude={"requested_duration_seconds"})
    return json.dumps(data, ensure_ascii=False, indent=2)


def ref2v_bounded_writer_plan(content: str) -> str:
    """Hide deterministic scheduling metadata from the prose writer."""
    plan = parse_ref2v_bounded_action_plan(content)
    data = plan.model_dump(
        mode="json",
        exclude={"requested_duration_seconds", "timing_adjustments"},
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


def ref2v_advisory_writer_plan(content: str) -> str:
    """Hide V0.7 scheduling provenance from the prose writer."""
    plan = parse_ref2v_advisory_action_plan(content)
    data = plan.model_dump(
        mode="json",
        exclude={"requested_duration_seconds", "timing_adjustments"},
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


def ref2v_supervised_writer_plan(content: str) -> str:
    """Hide compilation provenance while preserving the supervised choreography."""
    plan = parse_ref2v_supervised_compiled_plan(content)
    data = plan.model_dump(
        mode="json",
        exclude={"requested_duration_seconds", "timing_adjustments"},
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


def _recommended_motion_duration_ms(beat: ActionBeatV2) -> int:
    return _BASE_MINIMUM_DURATIONS[beat.motion_type] + (
        1500 if beat.complexity is ActionComplexity.MULTI_STEP else 0
    )


def _allocate_expansions(
    desired: tuple[int, ...],
    capacity_ms: int,
) -> tuple[int, ...]:
    total = sum(desired)
    if total <= capacity_ms:
        return desired
    if total == 0 or capacity_ms <= 0:
        return tuple(0 for _ in desired)
    allocated = [value * capacity_ms // total for value in desired]
    remainder = capacity_ms - sum(allocated)
    for index, value in enumerate(desired):
        if remainder == 0:
            break
        if value > allocated[index]:
            allocated[index] += 1
            remainder -= 1
    return tuple(allocated)


def _ceil_to_second(milliseconds: int) -> int:
    return math.ceil(milliseconds / 1000) * 1000


def _parse_plan(content: str, model_type):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ref2V action plan is empty")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Ref2V action plan does not contain a JSON object")
    try:
        raw = json.loads(value[start : end + 1])
        return model_type.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"invalid Ref2V action plan: {error}") from error
