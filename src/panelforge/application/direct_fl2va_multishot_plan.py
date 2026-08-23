"""Structured two-to-four-shot plan for MiniMax H3 Base modes."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from panelforge.domain import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
)

from .direct_ref2v_plan import DirectContinuityRisk, DirectDialogueCue


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class DirectFL2VAMultiShotCamera(_StrictModel):
    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None = None
    speed: H3CameraSpeed | None = None
    target_clause: str | None = Field(default=None, min_length=1)
    visible_change: str = Field(min_length=1)

    def directive(self, shot_number: int) -> H3CameraDirective:
        return H3CameraDirective(
            directive_id=f"camera_{shot_number}",
            motion=self.motion,
            amplitude=self.amplitude,
            speed=self.speed,
            target_clause=self.target_clause or "",
        )

    @model_validator(mode="after")
    def validate_protocol(self) -> "DirectFL2VAMultiShotCamera":
        self.directive(1)
        return self


class DirectFL2VAMultiShot(_StrictModel):
    duration_ms: int = Field(gt=0)
    opening_composition: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    new_information: str = Field(min_length=1)
    continuity_from_previous: str | None = Field(default=None, min_length=1)
    actions: tuple[str, ...] = Field(min_length=1)
    observable_end_state: str = Field(min_length=1)
    camera: DirectFL2VAMultiShotCamera | None = None

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("actions must contain non-empty values")
        if len(values) != len(set(values)):
            raise ValueError("actions must not contain duplicates within a shot")
        return values


class DirectFL2VAMultiShotFinalState(_StrictModel):
    description: str = Field(min_length=1)
    final_hold_ms: int = Field(ge=0)


class DirectFL2VAMultiShotPlan(_StrictModel):
    scene_setup: str = Field(min_length=1)
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    shots: tuple[DirectFL2VAMultiShot, ...] = Field(min_length=2, max_length=4)
    final_state: DirectFL2VAMultiShotFinalState
    dialogue_cues: tuple[DirectDialogueCue, ...]
    risks: tuple[DirectContinuityRisk, ...]
    technical_adjustments: tuple[str, ...] = ()
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @field_validator("continuity_invariants", "technical_adjustments")
    @classmethod
    def validate_text_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("text lists must contain non-empty values")
        if len(values) != len(set(values)):
            raise ValueError("text lists must not contain duplicates")
        return values

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

    @property
    def camera_directives(self) -> tuple[H3CameraDirective, ...]:
        return tuple(
            shot.camera.directive(number)
            for number, shot in enumerate(self.shots, 1)
            if shot.camera is not None
        )

    @model_validator(mode="after")
    def validate_timeline(self) -> "DirectFL2VAMultiShotPlan":
        if self.shots[0].continuity_from_previous is not None:
            raise ValueError("Shot 1 continuity_from_previous must be null")
        for number, shot in enumerate(self.shots[1:], 2):
            if shot.continuity_from_previous is None:
                raise ValueError(
                    f"Shot {number} continuity_from_previous must be provided"
                )
        risk_ids = [risk.risk_id for risk in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk IDs must be unique")
        expected_cues = [
            f"dialogue_{number}" for number in range(1, len(self.dialogue_cues) + 1)
        ]
        if [cue.cue_id for cue in self.dialogue_cues] != expected_cues:
            raise ValueError("dialogue cue IDs must be contiguous and chronological")
        if any(cue.start_ms >= self.final_state_start_ms for cue in self.dialogue_cues):
            raise ValueError("dialogue cues must start before the final hold")
        speaker_names: dict[str, str] = {}
        for cue in self.dialogue_cues:
            previous = speaker_names.setdefault(cue.speaker_id, cue.speaker)
            if previous != cue.speaker:
                raise ValueError("one speaker ID must keep one speaker description")
        return self


def direct_fl2va_multishot_plan_schema() -> str:
    schema = DirectFL2VAMultiShotPlan.model_json_schema()
    schema["properties"]["technical_adjustments"]["maxItems"] = 0
    return json.dumps(schema, ensure_ascii=False, indent=2)


def parse_direct_fl2va_multishot_plan(content: str) -> DirectFL2VAMultiShotPlan:
    try:
        return DirectFL2VAMultiShotPlan.model_validate(_json_object(content))
    except ValidationError as error:
        raise ValueError(f"invalid H3 Base multi-shot plan: {error}") from error


def canonical_direct_fl2va_multishot_plan(
    content: str,
    *,
    recover_invalid_target: bool = False,
    expected_dialogues: tuple[str, ...] = (),
    **_: object,
) -> str:
    value = _json_object(content)
    if value.get("technical_adjustments", []) not in ([], ()):
        raise ValueError(
            "invalid H3 Base multi-shot plan: technical_adjustments is "
            "application-owned and must be empty"
        )
    value["technical_adjustments"] = []
    if recover_invalid_target:
        _recover_camera_fields(value)
    _canonicalize_dialogues(value, expected_dialogues)
    try:
        plan = DirectFL2VAMultiShotPlan.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"invalid H3 Base multi-shot plan: {error}") from error
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def align_direct_fl2va_multishot_duration(
    content: str,
    requested_duration_ms: int,
) -> str:
    if (
        isinstance(requested_duration_ms, bool)
        or not isinstance(requested_duration_ms, int)
        or requested_duration_ms <= 0
    ):
        raise ValueError("H3 Base requested duration must be positive")
    plan = parse_direct_fl2va_multishot_plan(content)
    if plan.final_state_start_ms > requested_duration_ms:
        raise ValueError(
            "H3 Base multi-shot actions exceed the explicitly requested duration"
        )
    hold = requested_duration_ms - plan.final_state_start_ms
    if hold == plan.final_state.final_hold_ms:
        return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)
    adjustments = list(plan.technical_adjustments)
    adjustments.append(
        "final_hold_adjusted:"
        f"{plan.final_state.final_hold_ms}:{hold}"
    )
    aligned = plan.model_copy(
        update={
            "final_state": plan.final_state.model_copy(update={"final_hold_ms": hold}),
            "technical_adjustments": tuple(adjustments),
        }
    )
    return json.dumps(aligned.model_dump(mode="json"), ensure_ascii=False, indent=2)


def lint_direct_fl2va_multishot_plan(content: str) -> tuple[str, ...]:
    try:
        parse_direct_fl2va_multishot_plan(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    return ()


def direct_fl2va_multishot_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_direct_fl2va_multishot_plan(content)
    except (TypeError, ValueError):
        return ()
    warnings: list[str] = []
    if plan.final_state.final_hold_ms == 0:
        warnings.append("Aucune tenue finale n'est planifiee ; verifiez sa lisibilite.")
    elif plan.final_state.final_hold_ms < 1000:
        warnings.append("La tenue finale est inferieure a 1 seconde.")
    if plan.duration_ms > 15_000:
        warnings.append("La duree derivee depasse 15 secondes.")
    for number, shot in enumerate(plan.shots, 1):
        if shot.duration_ms < 1000:
            warnings.append(f"Le plan {number} dure moins d'une seconde.")
    for number, (previous, current) in enumerate(zip(plan.shots, plan.shots[1:]), 2):
        if previous.opening_composition == current.opening_composition:
            warnings.append(
                f"Les plans {number - 1} et {number} ont la meme composition ; "
                "verifiez que la coupe apporte une information nouvelle."
            )
        if previous.new_information == current.new_information:
            warnings.append(
                f"Les plans {number - 1} et {number} declarent la meme information."
            )
    unresolved = [risk.risk_id for risk in plan.risks if risk.resolution is None]
    if unresolved:
        warnings.append("Arbitrage conseille pour : " + ", ".join(unresolved) + ".")
    for adjustment in plan.technical_adjustments:
        if adjustment.startswith("dialogue_cues_compiler_owned"):
            warnings.append("Les dialogues explicites sont compiles mot pour mot.")
        elif adjustment.startswith("dialogue_cue_recovered:"):
            warnings.append(
                adjustment.partition(":")[2] + " a ete restaure depuis l'intention."
            )
        elif adjustment.startswith("dialogue_text_restored:"):
            warnings.append(
                "Le texte de " + adjustment.partition(":")[2] + " a ete restaure."
            )
        elif adjustment.startswith("dialogue_metadata_recovered:"):
            warnings.append(
                "Les metadonnees de " + adjustment.partition(":")[2] + " ont ete completees."
            )
        elif adjustment.startswith("camera_target_dropped:"):
            warnings.append(
                "La cible optionnelle de " + adjustment.partition(":")[2] + " a ete omise."
            )
        elif adjustment.startswith("camera_modifiers_dropped:"):
            warnings.append(
                "Les modificateurs incompatibles de "
                + adjustment.partition(":")[2]
                + " ont ete omis."
            )
        elif adjustment.startswith("final_hold_adjusted:"):
            _, old, new = adjustment.split(":", 2)
            warnings.append(f"La tenue finale a ete ajustee de {old} ms a {new} ms.")
    return tuple(dict.fromkeys(warnings))


def direct_fl2va_multishot_writer_plan(content: str) -> str:
    plan = parse_direct_fl2va_multishot_plan(content)
    shots: list[dict[str, object]] = []
    for number, shot in enumerate(plan.shots, 1):
        start = plan.shot_starts_ms[number - 1]
        end = start + shot.duration_ms
        shots.append(
            {
                "shot_number": number,
                "start_ms": start,
                "end_ms": end,
                "purpose": shot.purpose,
                "new_information": shot.new_information,
                "continuity_from_previous": shot.continuity_from_previous,
                "actions": list(shot.actions),
                "observable_end_state": shot.observable_end_state,
                "dialogue_cues": [
                    cue.model_dump(mode="json")
                    for cue in plan.dialogue_cues
                    if start <= cue.start_ms < end
                    or (number == len(plan.shots) and cue.start_ms == end)
                ],
            }
        )
    value = {
        "scene_setup": plan.scene_setup,
        "continuity_invariants": list(plan.continuity_invariants),
        "shots": shots,
        "final_state": plan.final_state.model_dump(mode="json"),
        "derived_timing": {
            "cut_times_ms": list(plan.hard_cut_times_ms),
            "final_state_start_ms": plan.final_state_start_ms,
            "duration_ms": plan.duration_ms,
        },
        "overall_soundscape": plan.overall_soundscape,
        "non_diegetic_music": plan.non_diegetic_music,
    }
    return json.dumps(value, ensure_ascii=False, indent=2)


def validate_direct_fl2va_multishot_dialogues(
    content: str,
    expected_dialogues: tuple[str, ...],
) -> None:
    plan = parse_direct_fl2va_multishot_plan(content)
    actual = tuple(cue.text for cue in plan.dialogue_cues)
    if actual != expected_dialogues:
        raise ValueError(
            "H3 Base multi-shot dialogue cues must preserve every explicit "
            "quotation exactly once and in source order"
        )


def _recover_camera_fields(value: dict[str, object]) -> None:
    shots = value.get("shots")
    if not isinstance(shots, list):
        return
    adjustments = value["technical_adjustments"]
    assert isinstance(adjustments, list)
    without_dynamics = {"static_shot", "shake.slightly", "shake.strongly", "pov"}
    without_target = {"shake.slightly", "shake.strongly", "pov"}
    for number, shot in enumerate(shots, 1):
        if not isinstance(shot, dict) or not isinstance(shot.get("camera"), dict):
            continue
        camera = shot["camera"]
        motion = camera.get("motion")
        camera_id = f"camera_{number}"
        if motion in without_dynamics and (
            camera.get("amplitude") is not None or camera.get("speed") is not None
        ):
            camera["amplitude"] = None
            camera["speed"] = None
            _append_adjustment(adjustments, f"camera_modifiers_dropped:{camera_id}")
        if motion in without_target and camera.get("target_clause") is not None:
            camera["target_clause"] = None
            _append_adjustment(adjustments, f"camera_target_dropped:{camera_id}")
        try:
            DirectFL2VAMultiShotCamera.model_validate(camera).directive(number)
        except (TypeError, ValueError, ValidationError):
            if camera.get("target_clause") is None:
                continue
            candidate = dict(camera)
            candidate["target_clause"] = None
            try:
                DirectFL2VAMultiShotCamera.model_validate(candidate).directive(number)
            except (TypeError, ValueError, ValidationError):
                continue
            camera["target_clause"] = None
            _append_adjustment(adjustments, f"camera_target_dropped:{camera_id}")


def _canonicalize_dialogues(
    value: dict[str, object],
    expected_dialogues: tuple[str, ...],
) -> None:
    raw = value.get("dialogue_cues")
    raw_cues = raw if isinstance(raw, list) else []
    adjustments = value["technical_adjustments"]
    assert isinstance(adjustments, list)
    final_start = _raw_final_start(value)
    normalized: list[dict[str, object]] = []
    used: set[int] = set()
    for index, exact_text in enumerate(expected_dialogues, 1):
        cue_id = f"dialogue_{index}"
        match_index = next(
            (
                candidate_index
                for candidate_index, candidate in enumerate(raw_cues)
                if candidate_index not in used
                and isinstance(candidate, dict)
                and (candidate.get("cue_id") == cue_id or candidate.get("text") == exact_text)
            ),
            None,
        )
        fallback = _fallback_cue(cue_id, exact_text, index, len(expected_dialogues), final_start)
        if match_index is None:
            cue = fallback
            _append_adjustment(adjustments, f"dialogue_cue_recovered:{cue_id}")
        else:
            used.add(match_index)
            cue = dict(raw_cues[match_index])
            cue["cue_id"] = cue_id
            metadata_recovered = False
            if not isinstance(cue.get("speaker_id"), str) or re.fullmatch(
                r"S[1-9][0-9]*", cue["speaker_id"]
            ) is None:
                cue["speaker_id"] = fallback["speaker_id"]
                metadata_recovered = True
            for field in ("speaker", "language", "delivery"):
                if not isinstance(cue.get(field), str) or not str(cue[field]).strip():
                    cue[field] = fallback[field]
                    metadata_recovered = True
            start_ms = cue.get("start_ms")
            if (
                isinstance(start_ms, bool)
                or not isinstance(start_ms, int)
                or start_ms < 0
                or start_ms > final_start
            ):
                cue["start_ms"] = fallback["start_ms"]
                metadata_recovered = True
            if metadata_recovered:
                _append_adjustment(adjustments, f"dialogue_metadata_recovered:{cue_id}")
            if cue.get("text") != exact_text:
                _append_adjustment(adjustments, f"dialogue_text_restored:{cue_id}")
            cue["text"] = exact_text
        normalized.append(cue)
    for candidate_index, candidate in enumerate(raw_cues):
        if candidate_index in used or not isinstance(candidate, dict):
            continue
        extra = dict(candidate)
        extra["cue_id"] = f"dialogue_{len(normalized) + 1}"
        normalized.append(extra)
    value["dialogue_cues"] = normalized
    if expected_dialogues:
        _append_adjustment(adjustments, "dialogue_cues_compiler_owned")


def _fallback_cue(
    cue_id: str,
    text: str,
    index: int,
    total: int,
    final_start: int,
) -> dict[str, object]:
    return {
        "cue_id": cue_id,
        "speaker_id": f"S{index}",
        "speaker": f"speaker associated with {cue_id} in the intention",
        "start_ms": max(0, (index * final_start) // (total + 1)),
        "language": "French",
        "delivery": "as requested",
        "text": text,
    }


def _raw_final_start(value: dict[str, object]) -> int:
    shots = value.get("shots")
    if not isinstance(shots, list):
        return 1000
    total = 0
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        duration = shot.get("duration_ms")
        if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0:
            total += duration
    return total or 1000


def _append_adjustment(adjustments: list[object], value: str) -> None:
    if value not in adjustments:
        adjustments.append(value)


def _json_object(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("H3 Base multi-shot plan must not be empty")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("H3 Base multi-shot plan must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("H3 Base multi-shot plan must be one JSON object")
    return parsed


__all__ = [
    "DirectFL2VAMultiShotPlan",
    "align_direct_fl2va_multishot_duration",
    "canonical_direct_fl2va_multishot_plan",
    "direct_fl2va_multishot_plan_schema",
    "direct_fl2va_multishot_plan_warnings",
    "direct_fl2va_multishot_writer_plan",
    "lint_direct_fl2va_multishot_plan",
    "parse_direct_fl2va_multishot_plan",
    "validate_direct_fl2va_multishot_dialogues",
]
