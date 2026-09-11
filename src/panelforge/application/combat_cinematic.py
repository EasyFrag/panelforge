"""Combat 1.3: two-call direction contract, with continuous camera phases.

No model calls here. Only this pinned version adopts the richer contract.
"""
import json
import re

from pydantic import Field, model_validator

from panelforge.domain.minimax_h3 import H3CameraAmplitude, H3CameraDirective, H3CameraMotion, H3CameraSpeed
from .combat_sequence import _Model
from .minimax_h3_protocol import compile_camera_motion, extract_compiled_camera_clauses, normalize_dialogue_language_tags
from .revised_documents import strip_markdown_fence
from .vocal_policy import speech_lines, validate_speech

VERSION = "1.3.0"
PLAN_CONTRACT = "minimax.h3.combat.cinematic_planned_v1"


class Camera(_Model):
    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None
    speed: H3CameraSpeed | None
    target_clause: str = Field(max_length=240, description="English spatial continuation, e.g. 'beside the blade'. Empty for shake/pov. No second movement or camera-control words.")

    def directive(self, index=1):
        return H3CameraDirective(f"camera_{index}", self.motion, self.target_clause, self.amplitude, self.speed)

    @model_validator(mode="after")
    def valid_motion(self):
        self.directive()
        return self


class Phase(_Model):
    cue: str = Field(min_length=1, description="Complete English sentence anchoring this phase to a visible action, e.g. 'The blade clears the pillar.' No cut or camera instruction. Opening phase may use the initial attack.")
    camera: Camera
    exchanges: tuple[str, ...] = Field(min_length=1, max_length=6, description="English connected combinations, explicit attacker, attack path, opponent response and resulting momentum. Powers can be the main ranged weapons. No camera instructions, timestamps or hidden cuts.")


class PlannedShot(_Model):
    duration_ms: int = Field(gt=0, strict=True)
    opening_composition: str = Field(min_length=1, description="English initial static framing and positions. Link supplied identities to their actual <Picture N>. No camera movement.")
    phases: tuple[Phase, ...] = Field(min_length=1, max_length=2, description="One or two successive continuous phases in this shot. A phase is not a cut. Use two only when action and duration support a meaningful change.")
    pacing: str = Field(min_length=1, description="Complete English sentence describing action rhythm: acceleration, brief resistance or speed contrast. No camera controls or invented cut.")
    end_state: str = Field(min_length=1, description="English resulting positions, momentum and ownership, carried directly into the next opening. Not an instruction to freeze.")
    transition: str = Field(min_length=1, description="English visible action motivating the next cut and matching into the next shot; final shot describes the requested ending. No additional cut, timestamp or camera movement.")


class Plan(_Model):
    continuity_invariants: tuple[str, ...] = Field(min_length=1, description="English subject/reference associations, unchanged morphology, powers, weapons and global advantage/reversal/outcome. Do not infer new anatomy from effects or costumes.")
    shots: tuple[PlannedShot, ...] = Field(min_length=1, max_length=6)
    spoken_lines: tuple[str, ...]
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


class WrittenShot(_Model):
    phases: tuple[str, ...] = Field(min_length=1, max_length=2, description="One English action paragraph per approved phase, in the same order. Preserve named actor ownership and every connected combination. No camera, framing, cue, pacing, end-state or transition repetition: the compiler inserts those fields.")


class Writer(_Model):
    shots: tuple[WrittenShot, ...] = Field(min_length=1, max_length=6)
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


def schema(stage: str) -> str:
    return json.dumps((Plan if stage == "beat_sheet" else Writer).model_json_schema(), ensure_ascii=False)


def _prose(value: str, header: str) -> None:
    from .combat_sequence import _reference_mentions
    _reference_mentions(value, header)
    if re.search(r"(?i)\[Shot\s+\d+\]|\bShot\s+\d+:|<Subject\s+\d+>|overall_soundscape:|\b\d{2}:\d{2}\.\d{3}\b", value):
        raise ValueError("Les champs créatifs ne doivent pas ajouter d’en-tête ou d’horodatage.")
    if extract_compiled_camera_clauses(value):
        raise ValueError("Les mouvements caméra appartiennent uniquement aux phases caméra.")
    if re.search(r"(?i)\b(?:camera|view|shot)\s+cuts?\s+to\b|\b(?:snap[- ]cuts?|cuts?)\s+to\s+(?:a|an|the)\s+(?:close[- ]up|wide|low[- ]angle|high[- ]angle|insert)\b", value):
        raise ValueError("Une coupe doit être un plan compté, pas une instruction dans une phase continue.")


def canonical_plan(content: str, context: dict) -> str:
    from . import combat_sequence as legacy
    plan = Plan.model_validate_json(strip_markdown_fence(content))
    legacy._count(plan.shots, context)
    header = legacy._header(context, len(plan.shots))
    for text in plan.continuity_invariants:
        if not text.strip():
            raise ValueError("Les invariants ne doivent pas être vides.")
        _prose(text, header)
    validate_speech(tuple(("English", line) for line in plan.spoken_lines), context.get("dialogues", ()),
        level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
        duration_ms=context["duration_ms"], locked=context.get("locked_speech"))
    value = plan.model_dump(mode="json")
    total, elapsed = sum(s.duration_ms for s in plan.shots), 0
    for shot in value["shots"]:
        start = round(elapsed * context["duration_ms"] / total)
        elapsed += shot["duration_ms"]
        shot["duration_ms"] = round(elapsed * context["duration_ms"] / total) - start
        # Avoid changing phase count behind the user's back on short shots.
        if shot["duration_ms"] < 500 * len(shot["phases"]):
            raise ValueError("Prévoyez au moins une demi-seconde par phase continue, ou simplifiez le plan.")
    normalized = Plan.model_validate(value)
    # Compile the planned action once, locally, to catch the same camera/prose
    # errors before approving the Plan instead of failing on the second call.
    draft = Writer(shots=tuple(WrittenShot(phases=tuple(" ".join(p.exchanges) for p in s.phases)) for s in normalized.shots),
        overall_soundscape=normalized.overall_soundscape, non_diegetic_music=normalized.non_diegetic_music)
    _compile(normalized, draft, dict(context))
    return normalized.model_dump_json(indent=2)


def compile_result(content: str, context: dict) -> tuple[str, str]:
    if not context.get("plan"):
        raise ValueError("Combat 1.3 exige le Plan approuvé avant la rédaction (deux appels).")
    plan = Plan.model_validate(context["plan"])
    writer = Writer.model_validate_json(strip_markdown_fence(content))
    return _compile(plan, writer, context)


def _compile(plan: Plan, writer: Writer, context: dict) -> tuple[str, str]:
    from . import combat_sequence as legacy
    from .cinematic_core_v1 import compile_sequence
    return compile_sequence(plan, writer, context, check_count=legacy._count,
        validate_final=legacy.validate_final, encode_context=legacy.encode_context,
        action_field="exchanges")


def shot_bodies(content: str) -> tuple[str, ...]:
    """Ignore anchor references and audio when locating actual visual shots."""
    visual = re.split(r"(?m)^overall_soundscape:", content, maxsplit=1)[0]
    headings = list(re.finditer(r"(?m)^(?:\[Shot \d+\]|Shot \d+:)", visual))
    return tuple(visual[m.end():headings[i+1].start() if i+1 < len(headings) else len(visual)]
                 for i, m in enumerate(headings))


def camera_layout(content: str) -> tuple[tuple[str, ...], ...]:
    return tuple(extract_compiled_camera_clauses(body) for body in shot_bodies(content))


def preserve_camera_layout(current: str, candidate: str) -> None:
    if tuple(map(len, camera_layout(current))) != tuple(map(len, camera_layout(candidate))):
        raise ValueError("Conservez les phases caméra dans leur plan d’origine.")
