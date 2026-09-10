"""Compact one-call H3 multi-shot preparation and V2 plan presentation.

Both paths use the existing shot compiler; no synthetic approved Plan or LLM
call is created by the direct path.
"""

import json
import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from panelforge.domain import H3CameraDirective, H3CameraMotion
from .direct_fl2va_prompt import H3BaseInputMode
from .direct_fl2va_multishot_plan import (
    direct_fl2va_multishot_plan_warnings, parse_direct_fl2va_multishot_plan,
)
from .direct_fl2va_multishot_prompt import (
    DirectFL2VAMultiShotCompilerContext, compile_direct_fl2va_multishot_document,
    decode_direct_fl2va_multishot_context, encode_direct_fl2va_multishot_context,
    lint_direct_fl2va_multishot_prompt, rehydrate_direct_fl2va_multishot_document,
)
from .direct_ref2v_plan import DirectDialogueCue
from .revised_documents import strip_markdown_fence
from .vocal_policy import validate_speech


MULTISHOT_PLAN_CONTRACT = "minimax.h3.fl2va.direct_multishot_compact_h3_v2"
MULTISHOT_DIRECT_CONTRACT = "minimax.h3.multishot.prompt_direct_v1"


class _CompactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CompactShot(_CompactModel):
    duration_ms: int = Field(gt=0, strict=True)
    opening_composition: str = Field(min_length=1)
    camera_motion: H3CameraMotion
    description: str = Field(min_length=1)


class CompactMultiShot(_CompactModel):
    shots: tuple[CompactShot, ...] = Field(min_length=2, max_length=4)
    final_state: str = Field(min_length=1)
    dialogue_cues: tuple[DirectDialogueCue, ...]
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


def compact_multishot_schema() -> str:
    return json.dumps(CompactMultiShot.model_json_schema(), ensure_ascii=False)


def compile_compact_multishot(result: str, input_context: str) -> tuple[str, str]:
    source = json.loads(input_context)
    value = CompactMultiShot.model_validate_json(strip_markdown_fence(result))
    duration = source["duration_ms"]
    if source.get("vocal_policy_version"):
        validate_speech(tuple((cue.language, cue.text) for cue in value.dialogue_cues), source["dialogues"],
            level=source.get("dialogue_level", 0), source_text=source.get("source_text", ""), duration_ms=duration)
    elif tuple(cue.text for cue in value.dialogue_cues) != tuple(source["dialogues"]):
        raise ValueError("Les dialogues doivent reprendre exactement les paroles de l'intention, dans leur ordre.")
    # Durations are weights, aligned to the requested total without asking the
    # model to sum clocks. Cue timestamps are already in that requested timeline.
    total = sum(shot.duration_ms for shot in value.shots)
    starts = [0]
    elapsed = 0
    for shot in value.shots[:-1]:
        elapsed += shot.duration_ms
        starts.append(round(elapsed * duration / total))
    context = DirectFL2VAMultiShotCompilerContext(
        mode=H3BaseInputMode(source["mode"]),
        shot_starts_ms=tuple(starts),
        shot_cameras=tuple(H3CameraDirective(f"camera_{index}", shot.camera_motion)
                           for index, shot in enumerate(value.shots, 1)),
        opening_compositions=tuple(shot.opening_composition for shot in value.shots),
        final_state_description=value.final_state,
        final_state_start_ms=duration,
        duration_ms=duration,
        dialogue_cues=value.dialogue_cues,
        cut_policy="neutral",
    )
    encoded = encode_direct_fl2va_multishot_context(context)
    fields = [(f"shot_{index}", shot.description) for index, shot in enumerate(value.shots, 1)]
    fields += [("overall_soundscape", value.overall_soundscape),
               ("non_diegetic_music", value.non_diegetic_music)]
    document = "\n\n".join(f"{key}:\n{text}" for key, text in fields)
    content = compile_direct_fl2va_multishot_document(document, context)
    validate_compact_multishot(content, encoded, input_context)
    return content, encoded


def validate_compact_multishot(content: str, encoded: str, input_context: str) -> None:
    source = json.loads(input_context)
    context = decode_direct_fl2va_multishot_context(encoded)
    if (context.mode.value != source["mode"] or context.duration_ms != source["duration_ms"]
            or context.cut_policy != "neutral"):
        raise ValueError("Le découpage doit conserver le mode, les références et la durée du parcours.")
    if source.get("vocal_policy_version"):
        validate_speech(tuple((cue.language, cue.text) for cue in context.dialogue_cues), source["dialogues"],
            level=source.get("dialogue_level", 0), source_text=source.get("source_text", ""), duration_ms=source["duration_ms"])
    elif tuple(cue.text for cue in context.dialogue_cues) != tuple(source["dialogues"]):
        raise ValueError("Les dialogues du découpage ne correspondent pas à l'intention.")
    actual = Counter(re.findall(r"<d>\s*\[[^\]]+\]\s*(.*?)\s*</d>", content, flags=re.DOTALL))
    if actual != Counter(cue.text for cue in context.dialogue_cues):
        raise ValueError("Le prompt multi-plan doit conserver exactement les paroles prévues, sans ajout.")
    errors = lint_direct_fl2va_multishot_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    rehydrate_direct_fl2va_multishot_document(content, context)


def multishot_state_warnings(content: str) -> tuple[str, ...]:
    try:
        plan = parse_direct_fl2va_multishot_plan(content)
    except (TypeError, ValueError):
        return ()
    warnings = direct_fl2va_multishot_plan_warnings(content)
    # These V1 heuristics confuse a requested temporal cut with a redundant
    # viewpoint, and a readable end state with a compulsory frozen ending.
    result = tuple(warning for warning in warnings if not (
        warning.startswith("Aucune tenue finale")
        or warning.startswith("La tenue finale est inferieure")
        or "ont la meme composition" in warning
    ))
    if any(value.startswith("timeline_scaled:") for value in plan.technical_adjustments):
        result += ("Les durées des plans ont été ajustées proportionnellement à la durée demandée.",)
    return result


def align_state_multishot_duration(content: str, requested_duration_ms: int) -> str:
    if type(requested_duration_ms) is not int or requested_duration_ms <= 0:
        raise ValueError("H3 Base requested duration must be positive")
    plan = parse_direct_fl2va_multishot_plan(content)
    if plan.duration_ms == requested_duration_ms:
        return content
    scale = requested_duration_ms / plan.duration_ms
    ends = [round((start + shot.duration_ms) * scale)
            for start, shot in zip(plan.shot_starts_ms, plan.shots, strict=True)]
    starts = [0, *ends[:-1]]
    value = plan.model_dump(mode="json")
    for shot, start, end in zip(value["shots"], starts, ends, strict=True):
        shot["duration_ms"] = end - start
    value["final_state"]["final_hold_ms"] = requested_duration_ms - ends[-1]
    for cue in value["dialogue_cues"]:
        cue["start_ms"] = round(cue["start_ms"] * scale)
    value["technical_adjustments"].append(f"timeline_scaled:{plan.duration_ms}:{requested_duration_ms}")
    return parse_direct_fl2va_multishot_plan(json.dumps(value)).model_dump_json(indent=2)
