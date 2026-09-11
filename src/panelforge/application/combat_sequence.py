"""Combat 1.1 sequence contracts. Explicit 1-6 shots, independent of density.

Uses the shared H3 camera/dialogue protocol; old mono/multishot contracts stay
unchanged. The one-call route never creates an approved synthetic plan.
"""
import json
import re

from pydantic import BaseModel, ConfigDict, Field

from panelforge.domain.video_preparation import CombatSettings
from panelforge.domain.minimax_h3 import H3CameraDirective, H3CameraMotion
from .direct_fl2va_prompt import H3BaseInputMode, compile_h3_base_header
from .minimax_h3_protocol import (
    H3IssueSeverity, H3ProtocolMode, compile_camera_motion, lint_h3_prompt,
    normalize_dialogue_language_tags, extract_compiled_camera_clauses,
)
from .revised_documents import strip_markdown_fence
from .vocal_policy import speech_lines, validate_speech
from .combat_orientation import orientation_policy

DIRECT_CONTRACT = "minimax.h3.combat.sequence_direct_v1"
PLAN_CONTRACT = "minimax.h3.combat.sequence_planned_v1"
CINEMATIC_PLAN_CONTRACT = "minimax.h3.combat.cinematic_planned_v1"
PLAN_CONTRACTS = {PLAN_CONTRACT, CINEMATIC_PLAN_CONTRACT}
CONTRACTS = {DIRECT_CONTRACT, *PLAN_CONTRACTS}
MARKER = "__PANELFORGE_COMBAT_SEQUENCE_V1__:"
IDENTITY_VERSION = "1.1.1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Shot(_Model):
    duration_ms: int = Field(gt=0, strict=True)
    camera_motion: H3CameraMotion
    opening_composition: str = Field(min_length=1)
    description: str = Field(min_length=1)
    end_state: str = Field(min_length=1)
    transition: str = Field(min_length=1)


class Sequence(_Model):
    shots: tuple[Shot, ...] = Field(min_length=1, max_length=6)
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


class PlannedShot(_Model):
    duration_ms: int = Field(gt=0, strict=True)
    camera_motion: H3CameraMotion
    opening_composition: str = Field(min_length=1)
    exchanges: tuple[str, ...] = Field(min_length=1)
    end_state: str = Field(min_length=1)
    transition: str = Field(min_length=1)


class SequencePlan(_Model):
    continuity_invariants: tuple[str, ...] = Field(min_length=1)
    shots: tuple[PlannedShot, ...] = Field(min_length=1, max_length=6)
    spoken_lines: tuple[str, ...]
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


class Writer(_Model):
    shots: tuple[str, ...] = Field(min_length=1, max_length=6)
    overall_soundscape: str = Field(min_length=1)
    non_diegetic_music: str = Field(min_length=1)


def schema(stage: str, planned: bool, version: str = "1.1.0") -> str:
    if version == "1.3.0":
        from .combat_cinematic import schema as cinematic_schema
        return cinematic_schema(stage)
    model = SequencePlan if stage == "beat_sheet" else Writer if planned else Sequence
    value = model.model_json_schema()
    if version in {IDENTITY_VERSION, "1.2.0"}:
        action = (
            "Actions of subjects and surroundings in playback order, including resulting motion and the action "
            "motivating the transition. No camera movement or view-following paraphrase. Inline <Picture N> "
            "mentions identifying supplied subjects are allowed; preserve their approved role and identity. "
            "Do not copy compiled reference headers, shot headings or timestamps."
        )
        if model is Writer:
            value["properties"]["shots"]["items"]["description"] = action + " The compiler inserts initial framing and the planned camera movement."
        else:
            fields = value["$defs"]["PlannedShot" if model is SequencePlan else "Shot"]["properties"]
            fields["camera_motion"]["description"] = "The sole field for this shot's camera movement. Choose one allowed enum; the application compiles its sentence."
            fields["opening_composition"]["description"] = (
                "Initial framing, visible subjects and spatial arrangement, without camera movement. "
                "At first introduction, link each referenced combatant to its actual <Picture N> and intended role; "
                "respect reference roles and retain the reference identity without inventing physical traits."
            )
            fields["end_state"]["description"] = "Resulting positions, momentum, weapon ownership and damage carried into the next shot. No camera instructions or freeze command."
            fields["transition"]["description"] = "Action motivating the cut and continuity into the next shot, without camera movement. For one/final shot, describe the requested ending."
            if model is SequencePlan:
                fields["exchanges"]["items"]["description"] = action
                value["properties"]["continuity_invariants"]["items"]["description"] = "Stable subject-to-<Picture N> associations, identities, abilities and weapon ownership, respecting supplied reference roles."
            else:
                fields["description"]["description"] = action
    return json.dumps(value, ensure_ascii=False)


def _identity_contract(context: dict) -> bool:
    return context.get("preparation") in (
        {"family": "combat", "version": IDENTITY_VERSION},
        {"family": "combat", "version": "1.2.0"},
        {"family": "combat", "version": "1.3.0"},
    )


def _reference_mentions(content: str, header: str) -> None:
    allowed = set(re.findall(r"\bPicture (\d+)\b", header))
    for mention in re.findall(r"<Picture\b[^>]*>", content, re.IGNORECASE):
        match = re.fullmatch(r"<Picture ([1-9]\d*)>", mention)
        if match is None or match[1] not in allowed:
            raise ValueError("Une mention Picture doit désigner une référence fournie, avec son numéro exact.")


def decode_context(value: str) -> dict:
    if not value or not value.startswith(MARKER):
        raise ValueError("Le contexte de la chorégraphie Combat 1.1 est absent.")
    return json.loads(value[len(MARKER):])


def encode_context(value: dict) -> str:
    return MARKER + json.dumps(value, ensure_ascii=False)


def check_intention(text: str, settings: CombatSettings) -> int | None:
    """Only flag explicit, affirmative shot requests, not every use of 'plan'."""
    numbers = {"un": 1, "one": 1, "deux": 2, "two": 2, "trois": 3, "three": 3,
               "quatre": 4, "four": 4, "cinq": 5, "five": 5, "six": 6}
    counts = set()
    if re.search(r"(?i)\b(?:en un seul plan|in one continuous shot|mono[- ]plan|sans coupures?)\b", text):
        counts.add(1)
    for word in re.findall(r"(?i)\b(?:en|in|avec|with)\s+(\d+|un|one|deux|two|trois|three|quatre|four|cinq|five|six)\s+(?:plans?|shots?)\b", text):
        counts.add(int(word) if word.isdigit() else numbers[word.lower()])
    if counts and (len(counts) > 1 or (settings.shot_count is not None and counts != {settings.shot_count})):
        raise ValueError("Le nombre de plans de l'intention contredit le réglage. Harmonisez le texte et le sélecteur de plans.")
    if any(not 1 <= count <= 6 for count in counts):
        raise ValueError("Combat 1.1 accepte de 1 à 6 plans dans un clip.")
    return next(iter(counts)) if counts else settings.shot_count


def action_policy(settings: CombatSettings | None, version: str | None = None) -> str:
    if version == "1.3.0" and settings is not None:
        from .combat_cinematic_policy import action_policy as cinematic_policy
        return cinematic_policy(settings)
    if settings is None:
        return ""
    level = (
        "MODERATE: spaced readable exchanges and visible recovery; retain requested actions.",
        "DYNAMIC: linked combinations, meaningful footwork and a reversal of initiative. Each response opens the next action.",
        "INTENSE: sustained pressure with multi-action combinations, rapid re-entry and travelling exchanges. Defense prepares counterattack; do not spend the ending merely returning to guard.",
        "UNLEASHED: ambitious densely linked combinations, pursuit, crossing passes and repeated reversals. Use large spatial progression and compatible environmental interaction; keep identities and physical causality legible.",
    )[settings.action_level]
    count = "Choose 1-6 shots to serve the encounter and its duration." if settings.shot_count is None else f"Use exactly {settings.shot_count} shot(s)."
    version = "1.2" if settings.orientation is not None else "1.1"
    return (
        f"\n\nCOMBAT {version} SAVED CONTROLS\nACTION QUANTITY: " + level + "\nSHOT COUNT: " + count
        + " Action quantity and shot count are independent. A shot contains a combination, not one gesture. "
        "Do not add an extra fight at each cut or reset positions. Amount of action is not gore, magic, explosions, "
        "camera freedom or audacity. Several compatible actions can overlap. No fixed hit quota or evenly spaced micro-timestamps. "
        "The user delegates techniques; invent connected mechanics from the global arc, without demanding a list of moves."
    ) + orientation_policy(settings)


def _count(shots, context: dict) -> None:
    requested = check_intention(context.get("source_text", ""), CombatSettings.from_dict(context["settings"]))
    if requested is not None and len(shots) != requested:
        raise ValueError(f"Combat attend {requested} plan(s), le candidat en contient {len(shots)}.")


def _speech(content: str, context: dict, locked=None) -> None:
    validate_speech(speech_lines(content), context.get("dialogues", ()),
        level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
        duration_ms=context["duration_ms"], locked=locked if locked is not None else context.get("locked_speech"))


def canonical_plan(content: str, context: dict) -> str:
    if context.get("preparation", {}).get("version") == "1.3.0":
        from .combat_cinematic import canonical_plan as cinematic_plan
        return cinematic_plan(content, context)
    plan = SequencePlan.model_validate_json(strip_markdown_fence(content))
    _count(plan.shots, context)
    if _identity_contract(context):
        _reference_mentions(plan.model_dump_json(), _header(context, len(plan.shots)))
    if any(not x.strip() for x in plan.continuity_invariants) or any(not x.strip() for shot in plan.shots for x in shot.exchanges):
        raise ValueError("Les invariants et échanges du plan ne doivent pas être vides.")
    # Plain strings here are a ledger, not invented dialogue placeholders.
    validate_speech(tuple(("English", line) for line in plan.spoken_lines), context.get("dialogues", ()),
        level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
        duration_ms=context["duration_ms"], locked=context.get("locked_speech"))
    value = plan.model_dump(mode="json")
    total = sum(s.duration_ms for s in plan.shots)
    elapsed = 0
    starts = [0]
    for shot in plan.shots:
        elapsed += shot.duration_ms
        starts.append(round(elapsed * context["duration_ms"] / total))
    for index, shot in enumerate(value["shots"]):
        shot["duration_ms"] = starts[index + 1] - starts[index]
        if shot["duration_ms"] <= 0:
            raise ValueError("La durée ne laisse pas de place à chaque plan.")
    return SequencePlan.model_validate(value).model_dump_json(indent=2)


def _header(context: dict, count: int) -> str:
    if context["mode"] == "ref2va":
        return context["header"]
    mode = H3BaseInputMode(context["mode"])
    if count == 1:
        return compile_h3_base_header(mode, context["duration_ms"])
    if mode is H3BaseInputMode.T2VA:
        return ""
    if mode is H3BaseInputMode.I2VA:
        return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    seconds = f"{context['duration_ms'] / 1000:.2f}"
    if mode is H3BaseInputMode.L2VA:
        return f"How the reference pictures align with the target video — <Picture 1> (from [Shot {count}]) aligns with the {seconds}-second mark of the target video."
    return ("How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {count}) aligns with the {seconds}-second mark of the target video.")


def _time(ms: int) -> str:
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def compile_result(content: str, encoded: str, stage: str) -> tuple[str, str]:
    context = decode_context(encoded)
    if stage == "beat_sheet":
        return canonical_plan(content, context), encoded
    if context.get("preparation", {}).get("version") == "1.3.0":
        from .combat_cinematic import compile_result as cinematic_compile
        return cinematic_compile(content, context)
    if context.get("plan"):
        plan = SequencePlan.model_validate(context["plan"])
        value = Writer.model_validate_json(strip_markdown_fence(content))
        if len(value.shots) != len(plan.shots):
            raise ValueError("Le rédacteur doit conserver tous les plans approuvés.")
        shots = [Shot(**{k: v for k, v in s.model_dump().items() if k != "exchanges"}, description=d)
                 for s, d in zip(plan.shots, value.shots, strict=True)]
        context["locked_speech"] = list(plan.spoken_lines)
    else:
        value = Sequence.model_validate_json(strip_markdown_fence(content))
        shots = value.shots
    _count(shots, context)
    total = sum(s.duration_ms for s in shots)
    elapsed, sections, starts, cameras = 0, [], [], []
    for index, shot in enumerate(shots, 1):
        start = round(elapsed * context["duration_ms"] / total)
        elapsed += shot.duration_ms
        starts.append(start)
        camera = compile_camera_motion(H3CameraDirective(f"camera_{index}", shot.camera_motion))
        # The shared camera reader includes an immediately preceding cut time.
        # Store that same compiler-owned sentence, keeping exact comparisons
        # for camera order, motion and timing during later revisions.
        cameras.append(f"At {_time(start)}, {camera}" if index > 1 else camera)
        if _identity_contract(context):
            prose = shot.opening_composition + " " + shot.description
            header = _header(context, len(shots))
            _reference_mentions(prose, header)
            if (re.search(r"(?i)\[Shot\s+\d+\]|\bShot\s+\d+:|<Subject\s+\d+>|overall_soundscape:", prose)
                    or any(line in prose for line in header.splitlines() if line.strip())):
                raise ValueError("Les en-têtes compilés restent séparés des mentions Picture dans les actions.")
        elif re.search(r"(?i)\[Shot\s+\d+\]|<Picture\s+\d+>|<Subject\s+\d+>|overall_soundscape:", shot.description):
            raise ValueError("Les descriptions ne doivent pas répéter les en-têtes ou références compilés.")
        heading = "Shot 1:" if context["mode"] == "ref2va" and len(shots) == 1 else f"[Shot {index}]"
        if index > 1:
            heading += f" At {_time(start)},"
        sections.append(f"{heading} {camera} {shot.opening_composition} {shot.description}")
    if any(a >= b for a, b in zip(starts, starts[1:])) or starts[-1] >= context["duration_ms"]:
        raise ValueError("Les durées proposées ne laissent pas de place à chaque plan.")
    body = f"The target video lasts {context['duration_ms'] / 1000:g} seconds.\n\n" + "\n\n".join(sections)
    if context["mode"] != "ref2va":
        body = "integrated_multimodal_description:\n" + body
    header = _header(context, len(shots))
    output = normalize_dialogue_language_tags((header + "\n\n" + body).strip()
        + f"\n\noverall_soundscape: {value.overall_soundscape}\n\nnon_diegetic_music: {value.non_diegetic_music}")
    context.update(compiled_header=header, shot_starts_ms=starts, cameras=cameras)
    validate_final(output, context)
    context["chosen_speech"] = [line for _, line in speech_lines(output)]
    context["sequence_plan"] = {
        "continuity_invariants": context.get("plan", {}).get("continuity_invariants", ["Preserve the approved identities and encounter."]),
        "shots": [{**{k: v for k, v in s.model_dump(mode="json").items() if k != "description"}, "exchanges": [s.description]} for s in shots],
        "spoken_lines": context["chosen_speech"],
        "overall_soundscape": value.overall_soundscape, "non_diegetic_music": value.non_diegetic_music,
    }
    return output, encode_context(context)


def prompt_errors(content: str, mode: str, version: str | None = None) -> tuple[str, ...]:
    from .cinematic_core_v1 import prompt_errors as shared_errors
    return shared_errors(content, mode, continuous_phases=version == "1.3.0", phase_label=" Combat 1.3")


def validate_final(content: str, context: dict, *, preserve_cameras: bool = True) -> None:
    errors = list(prompt_errors(content, context["mode"], context.get("preparation", {}).get("version")))
    if context.get("preparation", {}).get("version") == "1.3.0":
        from .combat_cinematic import camera_layout, shot_bodies
        if list(map(len, camera_layout(content))) != context["camera_phase_counts"]:
            errors.append("Conservez les phases dans leur plan.")
        bodies = shot_bodies(content)
        if len(bodies) != len(context["cinematic_protected"]) or any(
                item not in body for body, fields in zip(bodies, context["cinematic_protected"]) for item in fields):
            errors.append("Conservez les cadrages, rythmes et raccords approuvés.")
    header = context["compiled_header"]
    if _identity_contract(context):
        _reference_mentions(content, header)
    if header and not content.startswith(header + "\n\n"):
        errors.append("Les références compilées doivent rester identiques.")
    starts = [0] + [int(m) * 60000 + int(s) * 1000 + int(ms) for m,s,ms in re.findall(
        r"(?m)^\[Shot \d+\] At (\d{2}):(\d{2})\.(\d{3}),", content)]
    if starts != context["shot_starts_ms"]:
        errors.append("Conservez le nombre de plans et les instants de coupe enregistrés.")
    if preserve_cameras and tuple(extract_compiled_camera_clauses(content)) != tuple(context["cameras"]):
        errors.append("Conservez les directives caméra de la séquence.")
    if f"The target video lasts {context['duration_ms'] / 1000:g} seconds." not in content:
        errors.append("Conservez la durée enregistrée de la séquence.")
    if errors:
        raise ValueError(" ".join(errors))
    _speech(content, context, locked=context.get("chosen_speech"))


def lint_document(content: str, stage: str, mode: str, version: str | None = None) -> tuple[str, ...]:
    try:
        if stage == "beat_sheet":
            if version == "1.3.0":
                from .combat_cinematic import Plan
                Plan.model_validate_json(strip_markdown_fence(content))
            else:
                SequencePlan.model_validate_json(strip_markdown_fence(content))
            return ()
        return prompt_errors(content, mode, version)
    except ValueError as error:
        return (str(error),)
