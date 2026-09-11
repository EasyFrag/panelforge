"""Cinematic compiler mechanics, v1.0.0: no creative-family policy.

Adopted explicitly by Combat 1.3 and Classic cinematic 1.0. Each family
owns its schema, instructions, validation policy and saved context marker.
"""
import re

from .direct_fl2va_prompt import H3BaseInputMode, compile_h3_base_header
from .minimax_h3_protocol import (
    H3IssueSeverity, H3ProtocolMode, compile_camera_motion, lint_h3_prompt,
    normalize_dialogue_language_tags, extract_compiled_camera_clauses,
)
from .vocal_policy import speech_lines

VERSION = "1.0.0"


def reference_header(context: dict, count: int) -> str:
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


def timestamp(ms: int) -> str:
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def reference_mentions(content: str, header: str) -> None:
    allowed = set(re.findall(r"\bPicture (\d+)\b", header))
    for mention in re.findall(r"<Picture\b[^>]*>", content, re.IGNORECASE):
        match = re.fullmatch(r"<Picture ([1-9]\d*)>", mention)
        if match is None or match[1] not in allowed:
            raise ValueError("Une mention Picture doit désigner une référence fournie, avec son numéro exact.")


def validate_prose(value: str, header: str) -> None:
    reference_mentions(value, header)
    if re.search(r"(?i)\[Shot\s+\d+\]|\bShot\s+\d+:|<Subject\s+\d+>|overall_soundscape:|\b\d{2}:\d{2}\.\d{3}\b", value):
        raise ValueError("Les champs créatifs ne doivent pas ajouter d’en-tête ou d’horodatage.")
    if extract_compiled_camera_clauses(value):
        raise ValueError("Les mouvements caméra appartiennent uniquement aux phases caméra.")
    if re.search(r"(?i)\b(?:camera|view|shot)\s+cuts?\s+to\b|\b(?:snap[- ]cuts?|cuts?)\s+to\s+(?:a|an|the)\s+(?:close[- ]up|wide|low[- ]angle|high[- ]angle|insert)\b", value):
        raise ValueError("Une coupe doit être un plan compté, pas une instruction dans une phase continue.")


def compile_sequence(plan, writer, context: dict, *, check_count, validate_final, encode_context, action_field: str) -> tuple[str, str]:
    check_count(plan.shots, context)
    if len(writer.shots) != len(plan.shots):
        raise ValueError("Le rédacteur doit conserver tous les plans approuvés.")
    header = reference_header(context, len(plan.shots))
    sections, starts, cameras, protected = [], [], [], []
    elapsed, camera_index = 0, 0
    for index, (shot, written) in enumerate(zip(plan.shots, writer.shots, strict=True), 1):
        if len(shot.phases) != len(written.phases):
            raise ValueError("Le rédacteur doit conserver les phases continues de chaque plan.")
        starts.append(elapsed)
        heading = "Shot 1:" if context["mode"] == "ref2va" and len(plan.shots) == 1 else f"[Shot {index}]"
        if index > 1:
            heading += f" At {timestamp(elapsed)},"
        chunks, shot_protected = [], []
        for phase_index, (phase, prose) in enumerate(zip(shot.phases, written.phases, strict=True)):
            if not prose.strip() or any(not e.strip() for e in getattr(phase, action_field)):
                raise ValueError("Les actions d’une phase ne doivent pas être vides.")
            camera_index += 1
            camera = compile_camera_motion(phase.camera.directive(camera_index))
            cameras.append(f"At {timestamp(elapsed)}, {camera}" if index > 1 and phase_index == 0 else camera)
            if phase_index == 0:
                chunks.extend((camera, shot.opening_composition, shot.pacing, phase.cue, prose))
            else:
                chunks.extend((phase.cue, camera, prose))
            shot_protected.append(phase.cue)
            validate_prose(phase.cue + " " + prose, header)
        validate_prose(" ".join((shot.opening_composition, shot.pacing, shot.end_state, shot.transition)), header)
        chunks.extend((shot.end_state, shot.transition))
        shot_protected.extend((shot.opening_composition, shot.pacing, shot.end_state, shot.transition))
        protected.append(shot_protected)
        sections.append(heading + " " + " ".join(chunks))
        elapsed += shot.duration_ms
    if elapsed != context["duration_ms"]:
        raise ValueError("Les durées du Plan doivent correspondre à la durée de l’atelier.")
    body = f"The target video lasts {elapsed / 1000:g} seconds.\n\n" + "\n\n".join(sections)
    if context["mode"] != "ref2va":
        body = "integrated_multimodal_description:\n" + body
    output = normalize_dialogue_language_tags((header + "\n\n" + body).strip()
        + f"\n\noverall_soundscape: {writer.overall_soundscape}\n\nnon_diegetic_music: {writer.non_diegetic_music}")
    context.update(compiled_header=header, shot_starts_ms=starts, cameras=cameras,
        locked_speech=list(plan.spoken_lines), cinematic_protected=protected,
        camera_phase_counts=[len(s.phases) for s in plan.shots])
    validate_final(output, context)
    context["chosen_speech"] = [line for _, line in speech_lines(output)]
    saved = plan.model_dump(mode="json")
    for shot, written in zip(saved["shots"], writer.shots, strict=True):
        for phase, prose in zip(shot["phases"], written.phases, strict=True):
            phase[action_field] = [prose]
    saved.update(spoken_lines=context["chosen_speech"], overall_soundscape=writer.overall_soundscape,
        non_diegetic_music=writer.non_diegetic_music)
    context["sequence_plan"] = saved
    return output, encode_context(context)


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


def prompt_errors(content: str, mode: str, *, continuous_phases: bool = False, phase_label: str = "") -> tuple[str, ...]:
    errors = [x.message for x in lint_h3_prompt(H3ProtocolMode(mode), content) if x.severity is H3IssueSeverity.ERROR]
    # Anchor references may mention [Shot N]; count only actual body headings.
    matches = list(re.finditer(r"(?m)^(?:\[Shot (\d+)\]|Shot (\d+):)(?: At (\d{2}):(\d{2})\.(\d{3}),)?", content))
    nums = [int(m[1] or m[2]) for m in matches]
    if not 1 <= len(nums) <= 6 or nums != list(range(1, len(nums) + 1)):
        errors.append("La séquence doit contenir 1 à 6 plans consécutifs.")
    if matches and (matches[0][3] is not None or any(m[3] is None for m in matches[1:])):
        errors.append("Seules les coupures après le premier plan doivent être horodatées.")
    times = [int(m[3]) * 60000 + int(m[4]) * 1000 + int(m[5]) for m in matches[1:] if m[3]]
    if any(t <= 0 for t in times) or any(a >= b for a, b in zip(times, times[1:])):
        errors.append("Les instants de coupe doivent être strictement croissants.")
    for name in ("overall_soundscape", "non_diegetic_music"):
        if len(re.findall(rf"(?m)^{name}:\s*\S", content)) != 1:
            errors.append(f"Le champ {name} doit apparaître une fois.")
    fields = re.findall(r"(?m)^(integrated_multimodal_description|overall_soundscape|non_diegetic_music):", content)
    expected = (["integrated_multimodal_description"] if mode != "ref2va" else []) + ["overall_soundscape", "non_diegetic_music"]
    if fields != expected:
        errors.append("Conservez les champs visuels et audio dans leur ordre canonique.")
    if matches and content.find("\noverall_soundscape:") < matches[-1].end():
        errors.append("Les champs audio doivent suivre tous les plans.")
    if continuous_phases:
        layout = camera_layout(content)
        if any(not 1 <= len(phase) <= 2 for phase in layout):
            errors.append(f"Chaque plan{phase_label} contient une ou deux phases caméra continues.")
        if sum(map(len, layout)) != len(extract_compiled_camera_clauses(content)):
            errors.append("Les phases caméra doivent appartenir aux plans.")
    elif len(extract_compiled_camera_clauses(content)) != len(nums):
        errors.append("Chaque plan doit contenir une directive caméra compilée.")
    return tuple(dict.fromkeys(errors))
