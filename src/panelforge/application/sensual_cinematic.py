"""Sensual 1.0: an independent two-call, explicit-maximal direction contract.

Only cinematic_core_v1 and the shared H3/vocal protocols are adopted. Classic
and Combat prompts, schemas, examples and policies are deliberately not used.
"""

from .prompt_recipe_text import prompt_text
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from panelforge.domain.minimax_h3 import H3CameraAmplitude, H3CameraDirective, H3CameraMotion, H3CameraSpeed
from panelforge.domain.video_preparation import SensualSettings
from . import cinematic_core_v1 as core
from .minimax_h3_protocol import extract_compiled_camera_clauses, compile_dialogue_tag, normalize_dialogue_language_tags
from .revised_documents import strip_markdown_fence
from .vocal_policy import speech_lines, validate_speech

VERSION = "1.0.0"
PLAN_CONTRACT = "minimax.h3.sensual.cinematic_planned_v1"
CONTRACTS = PLAN_CONTRACTS = {PLAN_CONTRACT}
MARKER = "__PANELFORGE_SENSUAL_CINEMATIC_V1__:"
CAMERA_TARGET_PREFIXES = (
    "to", "toward", "onto", "into", "from", "behind", "beside", "above", "below",
    "away from", "around", "along", "across", "past", "through", "following", "keeping",
    "maintaining", "revealing", "showing", "centered on", "focused on", "ending on", "framing",
    "holding", "leaving", "placing", "as", "while", "until", "with",
)
_CAMERA_TARGET_PREFIX_TEXT = ", ".join(CAMERA_TARGET_PREFIXES)

REVISION_SYSTEM = """You revise a Sensual 1.0 explicit-maximal MiniMax H3 prompt collaboratively.
Return raw JSON with exactly message (concise French reply), questions (up to three strings),
prompt (complete English runnable prompt), recommendations (up to eight strings), camera_directives (null or array).
All depicted participants are consenting adults. Preserve the exact requested sexual acts, actor ownership,
anatomical contacts, observable responses, progressive body positions and resulting states. Use direct, standard
anatomical and sexual vocabulary; never censor, euphemize, fade out, summarize or replace an explicit act with
generic sensuality. Maximal explicitness is a writing obligation, not permission to invent an unrequested act,
participant, coercion, injury, bodily fluid or escalation.
Rewrite the current prompt directly. Keep the exact reference header, Picture associations, duration, shot count,
cut timestamps, ordered sections and continuous phases inside their original shots. H3 keeps
integrated_multimodal_description; REF2VA keeps its reference rules and shot body without that field. Both keep
overall_soundscape and non_diegetic_music. Preserve visible identity, setting, object ownership and causal state.
Camera tokens [[camera:camera_N]] belong to the application. Retain each exactly once at its chronological position,
within its original shot. No camera movement or lens instruction outside tokens. camera_directives is null unless the
user explicitly changes camera motion; otherwise return one object per token in order using the supplied CAMERA CONTRACT.
Preserve exact speech unless explicitly changed; honor dialogue and music policies. Generated keyframes are visual,
not audio evidence. Keep the final prompt chronological, literal and internally consistent. No markdown, diff or Plan JSON."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Camera(_Model):
    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None
    speed: H3CameraSpeed | None
    target_clause: str = Field(
        max_length=240,
        description=(
            "English spatial continuation. Empty for shake/pov. When non-empty, begin with exactly one "
            f"allowed prefix: {_CAMERA_TARGET_PREFIX_TEXT}. Do not repeat a direction already encoded by "
            "the motion; for tilt.down use 'ending on the subject' or 'toward the floor', never 'down ...'. "
            "No second movement or camera-control words."
        ),
    )

    def directive(self, index=1):
        return H3CameraDirective(f"camera_{index}", self.motion, self.target_clause, self.amplitude, self.speed)

    @model_validator(mode="after")
    def valid_motion(self):
        self.directive()
        return self


class Participant(_Model):
    designation: str = Field(min_length=1, description="Stable English actor designation used throughout, explicitly identifying this person as an adult.")
    adult: Literal[True] = Field(description="Must be true. Sensual 1.0 depicts adults only.")
    reference_picture: str | None = Field(default=None, description="Exact supplied label such as <Picture 2>, or null when no identity reference applies.")

    @model_validator(mode="after")
    def valid_reference(self):
        if self.reference_picture is not None and re.fullmatch(r"<Picture [1-9]\d*>", self.reference_picture) is None:
            raise ValueError("reference_picture must be an exact <Picture N> label or null")
        return self


class InteractionBeat(_Model):
    beat_id: str = Field(pattern=r"^beat_[1-9]\d*$", description="Globally sequential ID: beat_1, beat_2, ...")
    actor: str = Field(min_length=1, description="Exact adult participant who initiates this beat; do not rely on an ambiguous pronoun.")
    action: str = Field(min_length=1, description="Direct English verb phrase naming the exact requested sensual or sexual action. No euphemism or generic summary.")
    contact: str = Field(min_length=1, description="Exact visible anatomy/object contact, placement, direction and continuity. State literally when contact has not begun yet.")
    response: str = Field(min_length=1, description="Observable voluntary physical response of the other adult or the initiating adult; no inferred inner thoughts.")
    resulting_state: str = Field(min_length=1, description="Concrete visible body positions, contact and ongoing motion after this beat, inherited by the next beat.")

    def strip(self) -> str:
        return " ".join((self.actor, self.action, self.contact, self.response, self.resulting_state)).strip()


class Phase(_Model):
    cue: str = Field(min_length=1, description="Complete English sentence anchoring the phase to a visible event. No camera, cut or timestamp.")
    camera: Camera
    interactions: tuple[InteractionBeat, ...] = Field(min_length=1, max_length=5, description="Chronological causal beats. Each names actor, exact act, anatomical contact, response and resulting state.")


class PlannedShot(_Model):
    duration_ms: int = Field(gt=0, strict=True)
    opening_composition: str = Field(min_length=1, description="English initial static framing, adult positions, clothing/body state and existing contact. Preserve actual <Picture N> roles. No camera movement.")
    phases: tuple[Phase, ...] = Field(min_length=1, max_length=2, description="One or two continuous phases. A phase is not a cut; the second inherits every position and contact from the first.")
    pacing: str = Field(min_length=1, description="English rhythm of approach, contact, repetition, pause or acceleration. No camera instruction.")
    end_state: str = Field(min_length=1, description="Exact visible adult positions, anatomy, contact and ongoing or completed action at the shot end.")
    transition: str = Field(min_length=1, description="Visible causal bridge into the next shot, or exact requested final moment. No extra cut, camera or timestamp.")


class Plan(_Model):
    participants: tuple[Participant, ...] = Field(min_length=1, max_length=8)
    consent_confirmed: Literal[True] = Field(description="Must be true: every depicted participant is an adult and the interaction is voluntary and ongoing.")
    continuity_invariants: tuple[str, ...] = Field(min_length=1, description="English identity/reference associations, adult bodies, setting, requested limits, ownership and state continuity.")
    shots: tuple[PlannedShot, ...] = Field(min_length=1, max_length=6)
    spoken_lines: tuple[str, ...] = Field(description="Exact spoken words in chronological order, without tags. Empty when nobody speaks.")
    spoken_languages: tuple[str, ...] = Field(default=(), description="One full English language name per spoken line, same order. Empty only when silent.")
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_ledger(self):
        if self.spoken_languages and len(self.spoken_languages) != len(self.spoken_lines):
            raise ValueError("Indiquez une langue pour chaque réplique, dans le même ordre.")
        for language in self.spoken_languages:
            compile_dialogue_tag(language, "fixture")
            if language.casefold() in ("language", "unknown", "auto"):
                raise ValueError("Indiquez le nom réel de la langue de la réplique.")
        ids = [beat.beat_id for shot in self.shots for phase in shot.phases for beat in phase.interactions]
        if ids != [f"beat_{index}" for index in range(1, len(ids) + 1)]:
            raise ValueError("Les beat_id doivent être uniques et consécutifs depuis beat_1.")
        designations = [participant.designation.casefold() for participant in self.participants]
        if len(designations) != len(set(designations)):
            raise ValueError("Chaque participant doit avoir une désignation stable et unique.")
        allowed = set(designations)
        for shot in self.shots:
            for phase in shot.phases:
                for beat in phase.interactions:
                    if beat.actor.casefold() not in allowed:
                        raise ValueError("Chaque actor doit reprendre exactement une désignation adulte déclarée.")
        return self


class WrittenPhase(_Model):
    beat_ids: tuple[str, ...] = Field(min_length=1, max_length=5, description="All approved beat IDs for this phase, unchanged and in order.")
    prose: str = Field(min_length=1, description="One chronological English paragraph spelling out every listed act, anatomy/contact, response and resulting state directly. No euphemism, camera, cut, timestamp or invented act.")


class WrittenShot(_Model):
    phases: tuple[WrittenPhase, ...] = Field(min_length=1, max_length=2)


class Writer(_Model):
    shots: tuple[WrittenShot, ...] = Field(min_length=1, max_length=6)
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


class _CompiledShot(_Model):
    phases: tuple[str, ...]


class _CompiledWriter(_Model):
    shots: tuple[_CompiledShot, ...]
    overall_soundscape: str
    non_diegetic_music: str


def schema(stage: str, _planned=True, _version=None, *, plan: dict | None = None) -> str:
    value = (Plan if stage == "beat_sheet" else Writer).model_json_schema()
    if stage == "beat_sheet":
        value.setdefault("required", []).append("spoken_languages")
    elif plan:
        approved = Plan.model_validate(plan)
        shots = value["properties"]["shots"]
        shots["minItems"] = shots["maxItems"] = len(approved.shots)
        shots.pop("items", None)
        shots["prefixItems"] = []
        for shot_index, shot in enumerate(approved.shots, 1):
            phases = []
            for phase_index, phase in enumerate(shot.phases, 1):
                ids = [beat.beat_id for beat in phase.interactions]
                phases.append({"type": "object", "additionalProperties": False,
                    "required": ["beat_ids", "prose"], "properties": {
                        "beat_ids": {"type": "array", "prefixItems": [{"const": item} for item in ids],
                            "minItems": len(ids), "maxItems": len(ids),
                            "description": f"Shot {shot_index}, phase {phase_index}: preserve these IDs exactly."},
                        "prose": {"type": "string", "minLength": 1}}})
            shots["prefixItems"].append({"type": "object", "additionalProperties": False,
                "required": ["phases"], "properties": {"phases": {"type": "array",
                    "prefixItems": phases, "minItems": len(phases), "maxItems": len(phases)}}})
    return json.dumps(value, ensure_ascii=False)


def writer_layout(plan: dict) -> str:
    approved = Plan.model_validate(plan)
    layout = {"shots": [{"phases": [{"beat_ids": [beat.beat_id for beat in phase.interactions],
        "prose": prompt_text('sensual_cinematic.writer_layout.01', 'Direct action paragraph for shot {value1}, phase {value2}', value1=shot_index, value2=phase_index)}
        for phase_index, phase in enumerate(shot.phases, 1)]}
        for shot_index, shot in enumerate(approved.shots, 1)]}
    return (prompt_text('sensual_cinematic.writer_layout.02', '\nAPPROVED SENSUAL WRITER LAYOUT — preserve this exact nesting and every beat_id. Replace only each prose placeholder. One shot object contains its continuous phase objects; never turn phases into cuts, merge beats, omit a contact/response/state, or add a numbered property. Keep soundscape and music at root.\n')
        + json.dumps(layout, ensure_ascii=False))


def requested_count(text: str, settings: SensualSettings) -> int | None:
    if settings.shot_count is not None:
        return settings.shot_count
    numbers = {"un": 1, "one": 1, "deux": 2, "two": 2, "trois": 3, "three": 3,
               "quatre": 4, "four": 4, "cinq": 5, "five": 5, "six": 6}
    counts = set()
    if re.search(r"(?i)\b(?:en un seul plan|in one continuous shot|mono[- ]plan|sans coupures?)\b", text):
        counts.add(1)
    for word in re.findall(r"(?i)\b(?:en|in|avec|with)\s+(\d+|un|one|deux|two|trois|three|quatre|four|cinq|five|six)\s+(?:plans?|shots?)\b", text):
        counts.add(int(word) if word.isdigit() else numbers[word.lower()])
    if len(counts) > 1:
        raise ValueError("L’intention demande plusieurs nombres de plans. Choisissez un nombre ou clarifiez le texte.")
    if counts and not 1 <= next(iter(counts)) <= 6:
        raise ValueError("Sensual 1.0 accepte de 1 à 6 plans par clip.")
    return next(iter(counts)) if counts else None


def check_count(shots, context: dict) -> None:
    count = requested_count(context.get("source_text", ""), SensualSettings.from_dict(context["settings"]))
    if count is not None and len(shots) != count:
        raise ValueError(f"Le Plan Sensuel doit contenir exactement {count} plan(s).")


def policy(settings: SensualSettings, text: str) -> str:
    if settings.explicitness != "explicit_maximal":
        raise ValueError(prompt_text('sensual_cinematic.policy.01', 'Sensual 1.0 attend le niveau explicite maximal verrouillé.'))
    count = requested_count(text, settings)
    choice = f"Use exactly {count} shot(s)." if count else prompt_text('sensual_cinematic.policy.02', 'Choose 1-6 shots from the intention, duration and physical progression; prefer fewer when they suffice.')
    return ("\nSENSUAL 1.0 — EXPLICIT MAXIMAL (PINNED)\n" + choice
        + (prompt_text('sensual_cinematic.policy.03', ' The explicit UI count overrides conflicting count wording.') if settings.shot_count is not None else prompt_text('sensual_cinematic.policy.04', ' Auto follows an explicit requested count when present.'))
        + prompt_text('sensual_cinematic.policy.05', ' All depicted people must be clearly adults and every interaction voluntary and ongoing. Maximal is mandatory literal specificity: use standard anatomical names and exact sexual-action verbs wherever the requested act requires them. Never censor, euphemize, fade out, imply off-screen completion, or collapse an action into labels such as intimate activity, sensual movement, pleasure or making love. For every chronological beat state actor, exact action, anatomical/object contact, observable response and resulting position/contact. Maintain contact, body orientation, clothing state and repetitive motion until a visible action changes them. Do not invent an unrequested act category, participant, coercion, injury, fluid, climax or escalation. Explicitness and shot count are independent. Camera fields alone own camera motion; phases are continuous, not hidden cuts. Respect first/last anchors and every Ref2V role. All non-dialogue output is English. Declare spoken_languages and preserve exact speech with canonical <d>[Language] words</d> tags.'))


def encode_context(value: dict) -> str:
    return MARKER + json.dumps(value, ensure_ascii=False)


def decode_context(value: str) -> dict:
    if not value or not value.startswith(MARKER):
        raise ValueError("Le contexte Sensuel est absent.")
    context = json.loads(value[len(MARKER):])
    if context.get("preparation") != {"family": "sensual", "version": VERSION}:
        raise ValueError("Version de préparation Sensuel incompatible.")
    return context


def _speech_languages(plan: Plan) -> dict[str, set[str]]:
    languages: dict[str, set[str]] = {}
    for line, language in zip(plan.spoken_lines, plan.spoken_languages):
        canonical = speech_lines(compile_dialogue_tag(language, line))[0][0]
        languages.setdefault(line, set()).add(canonical)
    declared = {line: set(names) for line, names in languages.items()}
    for shot in plan.shots:
        for phase in shot.phases:
            for beat in phase.interactions:
                for language, line in speech_lines(normalize_dialogue_language_tags(beat.strip())):
                    if line in declared and language not in declared[line]:
                        raise ValueError("Langues contradictoires pour une réplique approuvée.")
                    languages.setdefault(line, set()).add(language)
    return languages


def _normalize_speech(value, languages):
    if isinstance(value, dict):
        return {key: item if key in ("spoken_lines", "spoken_languages") else _normalize_speech(item, languages) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_speech(item, languages) for item in value]
    if not isinstance(value, str):
        return value

    def complete(match):
        words = match[1].strip()
        if words.startswith("["):
            for language, line in speech_lines(match[0]):
                if languages.get(line) and language not in languages[line]:
                    raise ValueError("Conservez la langue déclarée pour chaque réplique approuvée.")
            return match[0]
        choices = languages.get(words, set())
        if len(choices) != 1:
            raise ValueError("Langue manquante ou ambiguë pour une réplique Sensuel.")
        return compile_dialogue_tag(next(iter(choices)), words)

    return re.sub(r"<d>(.*?)</d>", complete, normalize_dialogue_language_tags(value), flags=re.DOTALL)


def canonical_plan(content: str, context: dict) -> str:
    plan = Plan.model_validate_json(strip_markdown_fence(content))
    plan = Plan.model_validate(_normalize_speech(plan.model_dump(mode="json"), _speech_languages(plan)))
    check_count(plan.shots, context)
    header = core.reference_header(context, len(plan.shots))
    for participant in plan.participants:
        core.validate_prose(" ".join(x for x in (participant.designation, participant.reference_picture) if x), header)
    for text in plan.continuity_invariants:
        core.validate_prose(text, header)
    declared = _speech_languages(plan)
    validate_speech(tuple((next(iter(declared.get(line, {"English"}))) if len(declared.get(line, {"English"})) == 1 else "ambiguous", line)
        for line in plan.spoken_lines), context.get("dialogues", ()), level=context.get("dialogue_level", 0),
        source_text=context.get("source_text", ""), duration_ms=context["duration_ms"], locked=context.get("locked_speech"))
    value = plan.model_dump(mode="json")
    total, elapsed = sum(shot.duration_ms for shot in plan.shots), 0
    for shot in value["shots"]:
        start = round(elapsed * context["duration_ms"] / total)
        elapsed += shot["duration_ms"]
        shot["duration_ms"] = round(elapsed * context["duration_ms"] / total) - start
        if shot["duration_ms"] < 500 * len(shot["phases"]):
            raise ValueError("Prévoyez au moins une demi-seconde par phase Sensuel ou simplifiez le Plan.")
    normalized = Plan.model_validate(value)
    draft = Writer(shots=tuple(WrittenShot(phases=tuple(WrittenPhase(
        beat_ids=tuple(beat.beat_id for beat in phase.interactions),
        prose=" ".join(beat.strip() for beat in phase.interactions)) for phase in shot.phases)) for shot in normalized.shots),
        overall_soundscape=normalized.overall_soundscape, non_diegetic_music=normalized.non_diegetic_music)
    _compile(normalized, draft, dict(context))
    return normalized.model_dump_json(indent=2)


def compile_result(content: str, encoded: str, stage: str) -> tuple[str, str]:
    context = decode_context(encoded)
    if stage == "beat_sheet":
        return canonical_plan(content, context), encoded
    if not context.get("plan"):
        raise ValueError("Approuvez le Plan Sensuel avant la rédaction (deux appels).")
    plan = Plan.model_validate(context["plan"])
    writer = Writer.model_validate_json(strip_markdown_fence(content))
    return _compile(plan, writer, context)


def _compile(plan: Plan, writer: Writer, context: dict) -> tuple[str, str]:
    if len(writer.shots) != len(plan.shots):
        raise ValueError("Le Writer Sensuel doit conserver tous les plans approuvés.")
    compiled_shots = []
    for shot_index, (planned_shot, written_shot) in enumerate(zip(plan.shots, writer.shots, strict=True), 1):
        if len(written_shot.phases) != len(planned_shot.phases):
            raise ValueError(f"Plan {shot_index} : conservez toutes les phases approuvées.")
        prose = []
        for phase_index, (planned_phase, written_phase) in enumerate(zip(planned_shot.phases, written_shot.phases, strict=True), 1):
            expected = tuple(beat.beat_id for beat in planned_phase.interactions)
            if written_phase.beat_ids != expected:
                raise ValueError(f"Plan {shot_index}, phase {phase_index} : conservez chaque beat_id dans l’ordre.")
            prose.append(written_phase.prose)
        compiled_shots.append(_CompiledShot(phases=tuple(prose)))
    compiled = _CompiledWriter(shots=tuple(compiled_shots), overall_soundscape=writer.overall_soundscape,
        non_diegetic_music=writer.non_diegetic_music)
    output, _ = core.compile_sequence(plan, compiled, context, check_count=check_count,
        validate_final=validate_final, encode_context=encode_context, action_field="interactions")
    # Keep the independent structured beat contract for any later Writer revision.
    context["sequence_plan"] = plan.model_dump(mode="json")
    return output, encode_context(context)


def prompt_errors(content: str, mode: str) -> tuple[str, ...]:
    return core.prompt_errors(content, mode, continuous_phases=True, phase_label=" Sensuel 1.0")


def validate_final(content: str, context: dict) -> None:
    errors = list(prompt_errors(content, context["mode"]))
    if list(map(len, core.camera_layout(content))) != context["camera_phase_counts"]:
        errors.append("Conservez les phases Sensuel dans leur plan.")
    bodies = core.shot_bodies(content)
    if len(bodies) != len(context["cinematic_protected"]) or any(
            item not in body for body, fields in zip(bodies, context["cinematic_protected"]) for item in fields):
        errors.append("Conservez les cadrages, rythmes et raccords approuvés.")
    header = context["compiled_header"]
    core.reference_mentions(content, header)
    if header and not content.startswith(header + "\n\n"):
        errors.append("Les références compilées doivent rester identiques.")
    starts = [0] + [int(m) * 60000 + int(s) * 1000 + int(ms) for m, s, ms in re.findall(
        r"(?m)^\[Shot \d+\] At (\d{2}):(\d{2})\.(\d{3}),", content)]
    if starts != context["shot_starts_ms"]:
        errors.append("Conservez les plans et instants de coupe enregistrés.")
    if tuple(extract_compiled_camera_clauses(content)) != tuple(context["cameras"]):
        errors.append("Conservez les directives caméra approuvées.")
    if f"The target video lasts {context['duration_ms'] / 1000:g} seconds." not in content:
        errors.append("Conservez la durée enregistrée.")
    if errors:
        raise ValueError(" ".join(errors))
    validate_speech(speech_lines(content), context.get("dialogues", ()), level=context.get("dialogue_level", 0),
        source_text=context.get("source_text", ""), duration_ms=context["duration_ms"],
        locked=context.get("chosen_speech", context.get("locked_speech")))


def lint_document(content: str, stage: str, mode: str, *_unused) -> tuple[str, ...]:
    try:
        if stage == "beat_sheet":
            Plan.model_validate_json(strip_markdown_fence(content))
            return ()
        return prompt_errors(content, mode)
    except ValueError as error:
        return (str(error),)
