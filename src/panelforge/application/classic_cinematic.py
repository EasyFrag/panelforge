"""Classic cinematic 1.0: Plan then Writer, with its own creative contract.

Only neutral compiler v1.0 and shared H3/vocal protocols are adopted. No
Combat schema, instruction, example, density or orientation is imported.
"""

from .prompt_recipe_text import prompt_text
import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from panelforge.domain.minimax_h3 import H3CameraAmplitude, H3CameraDirective, H3CameraMotion, H3CameraSpeed
from panelforge.domain.video_preparation import ClassicCinematicSettings
from . import cinematic_core_v1 as core
from .minimax_h3_protocol import extract_compiled_camera_clauses, compile_dialogue_tag, normalize_dialogue_language_tags
from .revised_documents import strip_markdown_fence
from .vocal_policy import speech_lines, validate_speech
from .vocal_delivery import normalize_voiceovers

VERSION = "1.0.0"
PLAN_CONTRACT = "minimax.h3.classic.cinematic_planned_v1"
CONTRACTS = PLAN_CONTRACTS = {PLAN_CONTRACT}
MARKER = "__PANELFORGE_CLASSIC_CINEMATIC_V1__:"

# Render revision 0.4.0 adopts this exact Classic 1.0 policy, independently of
# the historical Classique and Combat conversational prompt policies.
REVISION_SYSTEM = """You revise a Classic cinematic 1.0 MiniMax H3 prompt collaboratively.
Return raw JSON with exactly message (concise French reply), questions (up to three strings),
prompt (complete English runnable prompt), recommendations (up to eight strings), camera_directives (null or array).
Rewrite the current prompt directly. Keep the exact reference header, Picture associations, duration,
shot count, cut timestamps, ordered sections and continuous phases inside their original shots.
H3 keeps integrated_multimodal_description; REF2VA keeps its reference rules and shot body without that field.
Both keep overall_soundscape and non_diegetic_music. Preserve visible identity, setting, object ownership,
causal state changes and intended tone. A calm scene stays calm. Apply the user's change without adding spectacle.
Camera tokens [[camera:camera_N]] belong to the application. Retain each exactly once at its chronological
position, within its original shot. No camera movement or lens instruction outside tokens. Static framing
and subject action remain editable. camera_directives is null unless the user explicitly changes camera motion;
otherwise return one object per token in order with exactly id, start_ms, motion, amplitude, speed, target_clause,
using the supplied CAMERA CONTRACT and all motion-specific null/target requirements. Never add or remove a token.
Preserve exact speech unless explicitly changed; honor the supplied dialogue and music policies.
Generated keyframes are sampled visual evidence, not audio evidence. Do not claim to have heard the video.
Keep the final prompt chronological, concrete and internally consistent. No markdown, diff or Plan JSON in prompt."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Camera(_Model):
    motion: H3CameraMotion
    amplitude: H3CameraAmplitude | None
    speed: H3CameraSpeed | None
    target_clause: str = Field(max_length=240, description="English spatial continuation, e.g. 'toward the open box'. Empty for shake/pov. No second movement or camera-control words. Static is valid.")

    def directive(self, index=1):
        return H3CameraDirective(f"camera_{index}", self.motion, self.target_clause, self.amplitude, self.speed)

    @model_validator(mode="after")
    def valid_motion(self):
        self.directive()
        return self


class Phase(_Model):
    cue: str = Field(min_length=1, description="English sentence anchoring this phase to a visible event, e.g. 'The lid reaches its open position.' First phase may begin with the initial state. No camera or cut instruction.")
    camera: Camera
    actions: tuple[str, ...] = Field(min_length=1, max_length=6, description="English visible actions, reactions or evolving states in causal order. A quiet observation is valid. Name each actor and object ownership; respect reference roles. No camera, cut or timestamp. Every spoken line uses <d>[English] exact words</d> (or its actual full language name); never a bare <d>words</d>. Declare the same exact words and language in spoken_lines and spoken_languages.")


class PlannedShot(_Model):
    duration_ms: int = Field(gt=0, strict=True)
    opening_composition: str = Field(min_length=1, description="English initial static framing, positions and visible state. Preserve actual <Picture N> associations where supplied. No camera movement.")
    phases: tuple[Phase, ...] = Field(min_length=1, max_length=2, description="One or optionally two continuous phases. A phase is not a cut. Use two only when a visible change motivates it; calm scenes need no added movement.")
    pacing: str = Field(min_length=1, description="English sentence specifying suitable rhythm, observation, pause, reaction or acceleration. Do not force action density. No camera instruction.")
    end_state: str = Field(min_length=1, description="English visible resulting positions and states; carry these into the next shot, including persistent modifications. Respect any supplied last frame.")
    transition: str = Field(min_length=1, description="English visible relationship into the next shot, or the requested final moment. No extra cut, camera movement or timestamp. A stable ending is allowed.")


class Plan(_Model):
    continuity_invariants: tuple[str, ...] = Field(min_length=1, description="English reference-to-subject associations, stable appearance, setting, object ownership and intended progression. Do not invent identities, costumes or extra events.")
    shots: tuple[PlannedShot, ...] = Field(min_length=1, max_length=6)
    spoken_lines: tuple[str, ...] = Field(description="Exact spoken words, in chronological order, without <d> tags or language prefixes. Empty when nobody speaks.")
    spoken_languages: tuple[str, ...] = Field(default=(), description="One full English language name per spoken_lines entry, in the same order, e.g. ['English', 'French']. Preserve each requested line's original language. Empty only when spoken_lines is empty. This explicit metadata lets the compiler supply a missing language tag without guessing from the words.")
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_languages(self):
        # Saved 1.0 Plans may omit this metadata; explicit tags remain sufficient.
        if self.spoken_languages and len(self.spoken_languages) != len(self.spoken_lines):
            raise ValueError("Indiquez une langue pour chaque réplique, dans le même ordre.")
        for language in self.spoken_languages:
            compile_dialogue_tag(language, "fixture")
            if language.casefold() in ("language", "unknown", "auto"):
                raise ValueError("Indiquez le nom réel de la langue de la réplique.")
        return self


class WrittenShot(_Model):
    phases: tuple[str, ...] = Field(min_length=1, max_length=2, description="One English action paragraph per approved phase, same order. Preserve actions, reactions, state changes and identities. Every spoken line keeps its exact <d>[English] words</d> tag or its approved original language. No camera, framing, cue, pacing, end-state or transition repetition: the compiler inserts those fields.")


class Writer(_Model):
    shots: tuple[WrittenShot, ...] = Field(min_length=1, max_length=6, description="Exactly one object per approved SHOT, not per phase. A continuous shot with two phases is one object containing two strings in phases.")
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


def schema(stage: str, *_unused, plan: dict | None = None) -> str:
    value = (Plan if stage == "beat_sheet" else Writer).model_json_schema()
    if stage == "beat_sheet":
        value.setdefault("required", []).append("spoken_languages")
    elif plan:
        approved = Plan.model_validate(plan)
        shots = value["properties"]["shots"]
        shots["minItems"] = shots["maxItems"] = len(approved.shots)
        shots.pop("items", None)
        shots["prefixItems"] = [
            {"type": "object", "additionalProperties": False, "required": ["phases"], "properties": {
                "phases": {"type": "array", "items": {"type": "string"},
                    "minItems": len(shot.phases), "maxItems": len(shot.phases),
                    "description": f"Shot {index + 1}: {len(shot.phases)} continuous phase(s) as strings inside this ONE array, same order, no extra cut. Never create a phases2 key."}}}
            for index, shot in enumerate(approved.shots)
        ]
    return json.dumps(value, ensure_ascii=False)


def writer_layout(plan: dict) -> str:
    approved = Plan.model_validate(plan)
    layout = {"shots": [{"phases": [prompt_text('classic_cinematic.writer_layout.01', 'Action paragraph for shot {value1}, phase {value2}', value1=i + 1, value2=j + 1)
               for j in range(len(shot.phases))]} for i, shot in enumerate(approved.shots)]}
    return (prompt_text('classic_cinematic.writer_layout.02', '\nAPPROVED WRITER LAYOUT — preserve this nesting exactly. Shots are camera cuts; phases inside a shot are continuous, never separate shots. Replace each placeholder with its action paragraph; keep soundscape and music at the root. Each shot object has exactly one key, phases. For two phases, write two strings separated by a comma INSIDE that array; do not create phases1, phases2 or any numbered property.\n') + json.dumps(layout))


def _speech_languages(plan: Plan) -> dict[str, set[str]]:
    languages: dict[str, set[str]] = {}
    for line, language in zip(plan.spoken_lines, plan.spoken_languages):
        canonical = speech_lines(compile_dialogue_tag(language, line))[0][0]
        languages.setdefault(line, set()).add(canonical)
    declared = {line: set(names) for line, names in languages.items()}
    # Old saved Plans already express the language in their action tags.
    for shot in plan.shots:
        for phase in shot.phases:
            for action in phase.actions:
                for language, line in speech_lines(normalize_dialogue_language_tags(action)):
                    if line in declared and language not in declared[line]:
                        raise ValueError("Langues contradictoires pour une réplique : alignez spoken_languages et sa balise <d>.")
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
            raise ValueError("Langue manquante ou ambiguë pour une réplique : renseignez spoken_languages ou utilisez <d>[English] texte</d> / <d>[French] texte</d>. Les paroles ne sont pas modifiées.")
        return compile_dialogue_tag(next(iter(choices)), words)
    return re.sub(r"<d>(.*?)</d>", complete, normalize_dialogue_language_tags(value), flags=re.DOTALL)


def requested_count(text: str, settings: ClassicCinematicSettings) -> int | None:
    # The explicit UI control is authoritative, even if old intention text says otherwise.
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
        raise ValueError("L’intention demande plusieurs nombres de plans. Choisissez un nombre dans le sélecteur ou clarifiez le texte.")
    if counts and not 1 <= next(iter(counts)) <= 6:
        raise ValueError("La mise en scène accepte de 1 à 6 plans par clip.")
    return next(iter(counts)) if counts else None


def check_count(shots, context: dict) -> None:
    count = requested_count(context.get("source_text", ""), ClassicCinematicSettings.from_dict(context["settings"]))
    if count is not None and len(shots) != count:
        raise ValueError(f"Le Plan doit contenir exactement {count} plan(s).")


def policy(settings: ClassicCinematicSettings, text: str) -> str:
    count = requested_count(text, settings)
    choice = f"Use exactly {count} shot(s)." if count else prompt_text('classic_cinematic.policy.01', 'Choose 1-6 shots from the intention, duration and visible progression; prefer fewer when they suffice.')
    return ("\nCLASSIC CINEMATIC 1.0 — SAVED SHOT CONTROL\n" + choice
        + (prompt_text('classic_cinematic.policy.02', ' The explicit UI count overrides any conflicting shot count in the intention.') if settings.shot_count is not None else prompt_text('classic_cinematic.policy.03', ' Auto follows the explicitly requested count when present.'))
        + prompt_text('classic_cinematic.policy.04', ' Shot count and number of actions are independent. Several related actions may share one shot. Match the requested tone: calm, contemplative, practical or lively. Do not force spectacle, confrontation, rapid movement, extra dialogue or a cliffhanger. A pause or stable final state can be meaningful. Camera phases are continuous, not extra shots. Only camera fields own camera motion; opening_composition owns static framing; actions own subject/environment changes. Respect supplied first/last frames and reference roles. In the Plan, spoken_languages must declare the full language name of each spoken_lines entry, in the same order (both arrays empty when silent). Put the exact words in actions as <d>[English] words</d>, or the declared original language. The Writer preserves these tags and words; never omit the language prefix.'))


def encode_context(value: dict) -> str:
    return MARKER + json.dumps(value, ensure_ascii=False)


def decode_context(value: str) -> dict:
    if not value or not value.startswith(MARKER):
        raise ValueError("Le contexte Classique Mise en scène est absent.")
    context = json.loads(value[len(MARKER):])
    if context.get("preparation") != {"family": "classic", "version": VERSION}:
        raise ValueError("Version de préparation Classique incompatible.")
    return context


def canonical_plan(content: str, context: dict) -> str:
    plan = Plan.model_validate_json(strip_markdown_fence(content))
    plan = Plan.model_validate(_normalize_speech(plan.model_dump(mode="json"), _speech_languages(plan)))
    check_count(plan.shots, context)
    header = core.reference_header(context, len(plan.shots))
    for text in plan.continuity_invariants:
        if not text.strip():
            raise ValueError("Les invariants ne doivent pas être vides.")
        core.validate_prose(text, header)
    declared_languages = _speech_languages(plan)
    validate_speech(tuple((next(iter(declared_languages.get(line, {"English"}))) if len(declared_languages.get(line, {"English"})) == 1 else "ambiguous", line) for line in plan.spoken_lines), context.get("dialogues", ()),
        level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
        duration_ms=context["duration_ms"], locked=context.get("locked_speech"))
    value = plan.model_dump(mode="json")
    total, elapsed = sum(s.duration_ms for s in plan.shots), 0
    for shot in value["shots"]:
        start = round(elapsed * context["duration_ms"] / total)
        elapsed += shot["duration_ms"]
        shot["duration_ms"] = round(elapsed * context["duration_ms"] / total) - start
        if shot["duration_ms"] < 500 * len(shot["phases"]):
            raise ValueError("Prévoyez au moins une demi-seconde par phase ou simplifiez le Plan.")
    normalized = Plan.model_validate(value)
    draft = Writer(shots=tuple(WrittenShot(phases=tuple(" ".join(p.actions) for p in s.phases)) for s in normalized.shots),
        overall_soundscape=normalized.overall_soundscape, non_diegetic_music=normalized.non_diegetic_music)
    _compile(normalized, draft, dict(context))
    return normalized.model_dump_json(indent=2)


def compile_result(content: str, encoded: str, stage: str) -> tuple[str, str]:
    context = decode_context(encoded)
    if stage == "beat_sheet":
        return canonical_plan(content, context), encoded
    if not context.get("plan"):
        raise ValueError("Approuvez le Plan avant la rédaction Classique (deux appels).")
    plan = Plan.model_validate(context["plan"])
    raw = json.loads(strip_markdown_fence(content))
    writer = Writer.model_validate(_normalize_numbered_phase_key(raw, plan))
    return _compile(plan, writer, context)


def _normalize_numbered_phase_key(value, plan: Plan):
    """Repair the observed phases + phases2 spelling only against an exact Plan.

    No prose is discarded, edited or reordered; unknown keys still go through
    Writer's extra-forbidden validation. Do not infer missing shots/phases.
    """
    if not isinstance(value, dict) or not isinstance(value.get("shots"), list) or len(value["shots"]) != len(plan.shots):
        return value
    shots = []
    for index, (raw, approved) in enumerate(zip(value["shots"], plan.shots, strict=True)):
        if isinstance(raw, dict) and set(raw) == {"phases", "phases2"}:
            groups = (raw["phases"], raw["phases2"])
            if len(approved.phases) != 2 or not all(
                isinstance(group, list) and len(group) == 1 and isinstance(group[0], str) and group[0].strip()
                for group in groups
            ):
                raise ValueError(f"Plan {index + 1} : phases2 est ambigu. Utilisez un seul tableau phases avec un paragraphe par phase approuvée.")
            raw = {"phases": [groups[0][0], groups[1][0]]}
        shots.append(raw)
    return {**value, "shots": shots}


def _compile(plan: Plan, writer: Writer, context: dict) -> tuple[str, str]:
    # Unambiguous packaging mistake observed with local Writer: one approved
    # continuous shot / two phases returned as two singleton shot objects.
    # Keep exact prose/order; all camera, speech and content checks still run.
    if len(plan.shots) == 1 and len(plan.shots[0].phases) == 2 and len(writer.shots) == 2 and all(len(s.phases) == 1 for s in writer.shots):
        writer = writer.model_copy(update={"shots": (WrittenShot(phases=tuple(s.phases[0] for s in writer.shots)),)})
    languages = _speech_languages(plan)
    plan = Plan.model_validate(_normalize_speech(plan.model_dump(mode="json"), languages))
    writer = Writer.model_validate(_normalize_speech(writer.model_dump(mode="json"), languages))
    return core.compile_sequence(plan, writer, context, check_count=check_count,
        validate_final=validate_final, encode_context=encode_context, action_field="actions",
        normalize_final=_normalize_vocal_delivery)


def _normalize_vocal_delivery(content: str, context: dict) -> str:
    result = normalize_voiceovers(content, context.get("source_text", ""))
    if result.applied or result.warnings:
        context["vocal_normalization"] = dict(
            version="1.0.0", applied=result.applied, warnings=list(result.warnings),
            speaker_ids=[dict(speaker=speaker, speaker_id=speaker_id)
                         for speaker, speaker_id in result.speaker_ids],
        )
    return result.content


def prompt_errors(content: str, mode: str) -> tuple[str, ...]:
    return core.prompt_errors(content, mode, continuous_phases=True)


def validate_final(content: str, context: dict) -> None:
    errors = list(prompt_errors(content, context["mode"]))
    if list(map(len, core.camera_layout(content))) != context["camera_phase_counts"]:
        errors.append("Conservez les phases dans leur plan.")
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
    validate_speech(speech_lines(content), context.get("dialogues", ()),
        level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
        duration_ms=context["duration_ms"], locked=context.get("chosen_speech", context.get("locked_speech")))


def lint_document(content: str, stage: str, mode: str, *_unused) -> tuple[str, ...]:
    try:
        if stage == "beat_sheet":
            Plan.model_validate_json(strip_markdown_fence(content))
            return ()
        return prompt_errors(content, mode)
    except ValueError as error:
        return (str(error),)
