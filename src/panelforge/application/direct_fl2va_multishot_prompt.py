"""Deterministic compiler for structured multi-shot H3 Base prompts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import re

from panelforge.domain import H3CameraDirective

from .direct_fl2va_prompt import H3BaseInputMode
from .direct_ref2v_plan import DirectDialogueCue
from .minimax_h3_protocol import (
    H3IssueSeverity,
    H3ProtocolMode,
    compile_camera_motion,
    compile_dialogue_tag,
    compile_shot_heading,
    lint_h3_prompt,
    parse_camera_directives,
)
from .revised_documents import RevisedDocumentContract, strip_markdown_fence
from .timed_camera_compiler import insert_ref2v_camera_clauses


FL2VA_MULTISHOT_CONTEXT_MARKER = "__PANELFORGE_FL2VA_MULTISHOT_CONTEXT_V1__:"
_MIN_SHOTS = 2
_MAX_SHOTS = 4
_WRITER_FIELD = re.compile(r"(?m)^([a-z][a-z0-9_]*):[ \t]*")
_SHOT_HEADING = re.compile(
    r"(?m)^\[Shot\s+\d+\](?:[ \t]+At\s+[^\r\n,]+,)?"
)
_TIMESTAMP = re.compile(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3}),")
_DIALOGUE_PLACEHOLDER = re.compile(
    r"\[\[dialogue:(dialogue_[1-9][0-9]*)\]\]"
)
_PICTURE = re.compile(r"<Picture\s+(\d+)>|(?<!<)\bPicture\s+(\d+)\b")
_LEGACY_LABEL = re.compile(r"(?i)@image\s*\d+|<Image\s+\d+>|<Subject\s+\d+>")
_CUT_PROSE = re.compile(r"(?i)\b(?:the\s+camera\s+cuts?|hard\s+cuts?|cut\s+to)\b")


@dataclass(frozen=True, slots=True)
class DirectFL2VAMultiShotCompilerContext:
    mode: H3BaseInputMode
    shot_starts_ms: tuple[int, ...]
    shot_cameras: tuple[H3CameraDirective | None, ...]
    opening_compositions: tuple[str, ...]
    final_state_description: str
    final_state_start_ms: int
    duration_ms: int
    dialogue_cues: tuple[DirectDialogueCue, ...]

    @property
    def shot_count(self) -> int:
        return len(self.shot_starts_ms)

    @property
    def header(self) -> str:
        return compile_h3_base_multishot_header(
            self.mode,
            self.duration_ms,
            self.shot_count,
        )

    @property
    def directives(self) -> tuple[H3CameraDirective, ...]:
        return tuple(camera for camera in self.shot_cameras if camera is not None)


def compile_h3_base_multishot_header(
    mode: H3BaseInputMode,
    duration_ms: int,
    shot_count: int,
) -> str:
    """Compile the official Base picture-to-shot alignment for multiple shots."""

    _validate_shot_count(shot_count)
    if not isinstance(mode, H3BaseInputMode):
        raise TypeError("mode must be an H3BaseInputMode")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
        raise ValueError("H3 Base multi-shot duration must be positive")
    seconds = f"{duration_ms / 1000:.2f}"
    if mode is H3BaseInputMode.T2VA:
        return ""
    if mode is H3BaseInputMode.I2VA:
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    if mode is H3BaseInputMode.L2VA:
        return (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot {shot_count}]) aligns with the "
            f"{seconds}-second mark of the target video."
        )
    return (
        "How the reference pictures align with the target video — Picture 1 "
        "(from Shot 1) aligns with the 0.00-second mark of the target video; "
        f"Picture 2 (from Shot {shot_count}) aligns with the {seconds}-second "
        "mark of the target video."
    )


def direct_fl2va_multishot_editable_fields(shot_count: int) -> tuple[str, ...]:
    _validate_shot_count(shot_count)
    return (
        *(f"shot_{number}" for number in range(1, shot_count + 1)),
        "overall_soundscape",
        "non_diegetic_music",
    )


def direct_fl2va_multishot_editable_contract(
    shot_count: int,
) -> RevisedDocumentContract:
    fields = direct_fl2va_multishot_editable_fields(shot_count)
    return RevisedDocumentContract(
        f"H3 Base {shot_count}-shot editable document",
        tuple(f"{field}:" for field in fields),
    )


def encode_direct_fl2va_multishot_context(
    context: DirectFL2VAMultiShotCompilerContext,
) -> str:
    context = _validated_context(context)
    payload = {
        "version": 1,
        "mode": context.mode.value,
        "shot_starts_ms": list(context.shot_starts_ms),
        "shot_cameras": [
            None if camera is None else _camera_payload(camera)
            for camera in context.shot_cameras
        ],
        "opening_compositions": list(context.opening_compositions),
        "final_state_description": context.final_state_description,
        "final_state_start_ms": context.final_state_start_ms,
        "duration_ms": context.duration_ms,
        "dialogue_cues": [cue.model_dump(mode="json") for cue in context.dialogue_cues],
    }
    return FL2VA_MULTISHOT_CONTEXT_MARKER + json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    )


def decode_direct_fl2va_multishot_context(
    value: str,
) -> DirectFL2VAMultiShotCompilerContext:
    if not isinstance(value, str) or not value.startswith(FL2VA_MULTISHOT_CONTEXT_MARKER):
        raise ValueError("H3 Base multi-shot compiler context is missing")
    try:
        payload = json.loads(value[len(FL2VA_MULTISHOT_CONTEXT_MARKER) :])
    except json.JSONDecodeError as error:
        raise ValueError("H3 Base multi-shot compiler context is invalid") from error
    expected = {
        "version",
        "mode",
        "shot_starts_ms",
        "shot_cameras",
        "opening_compositions",
        "final_state_description",
        "final_state_start_ms",
        "duration_ms",
        "dialogue_cues",
    }
    if not isinstance(payload, dict) or set(payload) != expected or payload["version"] != 1:
        raise ValueError("H3 Base multi-shot compiler context has invalid fields")
    cameras = tuple(
        None if item is None else parse_camera_directives([item])[0]
        for item in payload["shot_cameras"]
    )
    try:
        cues = tuple(DirectDialogueCue.model_validate(item) for item in payload["dialogue_cues"])
        mode = H3BaseInputMode(payload["mode"])
    except (TypeError, ValueError) as error:
        raise ValueError("H3 Base multi-shot compiler context is invalid") from error
    return _validated_context(
        DirectFL2VAMultiShotCompilerContext(
            mode=mode,
            shot_starts_ms=tuple(payload["shot_starts_ms"]),
            shot_cameras=cameras,
            opening_compositions=tuple(payload["opening_compositions"]),
            final_state_description=payload["final_state_description"],
            final_state_start_ms=payload["final_state_start_ms"],
            duration_ms=payload["duration_ms"],
            dialogue_cues=cues,
        )
    )


def compile_direct_fl2va_multishot_document(
    writer_content: str,
    compiler_context: str | DirectFL2VAMultiShotCompilerContext,
) -> str:
    context = _context(compiler_context)
    editable = direct_fl2va_multishot_editable_contract(context.shot_count).extract(
        writer_content
    )
    fields = _extract_fields(editable, context.shot_count)
    _validate_writer_fields(fields, context)

    shot_blocks: list[str] = []
    for shot_number in range(1, context.shot_count + 1):
        heading = compile_shot_heading(
            shot_number,
            None if shot_number == 1 else context.shot_starts_ms[shot_number - 1],
        )
        owned: list[str] = []
        if shot_number > 1:
            owned.append("the camera cuts to a new view.")
        owned.append(_as_sentence(context.opening_compositions[shot_number - 1]))
        camera = context.shot_cameras[shot_number - 1]
        if camera is not None:
            owned.append(compile_camera_motion(camera))
        body = _compile_shot_dialogues(
            fields[f"shot_{shot_number}"],
            context,
            shot_number,
        )
        if shot_number == context.shot_count:
            final = _as_sentence(context.final_state_description)
            if context.final_state_start_ms > context.shot_starts_ms[-1]:
                final = f"{_timestamp(context.final_state_start_ms)} {_sentence_continuation(final)}"
            body = f"{body.rstrip()} {final}"
        shot_blocks.append(f"{heading} {' '.join(owned)} {body}".strip())

    integrated = "\n\n".join(shot_blocks)
    body = (
        "integrated_multimodal_description:\n"
        f"{integrated}\n\n"
        "overall_soundscape:\n"
        f"{fields['overall_soundscape']}\n\n"
        "non_diegetic_music:\n"
        f"{fields['non_diegetic_music']}"
    )
    content = f"{context.header}\n\n{body}" if context.header else body
    errors = lint_direct_fl2va_multishot_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def rehydrate_direct_fl2va_multishot_document(
    content: str,
    compiler_context: str | DirectFL2VAMultiShotCompilerContext,
) -> str:
    context = _context(compiler_context)
    errors = lint_direct_fl2va_multishot_prompt(content, context)
    if errors:
        raise ValueError(" ".join(errors))
    parts = _split_document(content, context)
    for shot_number in range(1, context.shot_count + 1):
        value = parts[f"shot_{shot_number}"]
        owned: list[str] = []
        if shot_number > 1:
            owned.append("the camera cuts to a new view.")
        owned.append(_as_sentence(context.opening_compositions[shot_number - 1]))
        camera = context.shot_cameras[shot_number - 1]
        if camera is not None:
            owned.append(compile_camera_motion(camera))
        prefix = " ".join(owned) + " "
        if not value.startswith(prefix):
            raise ValueError(f"H3 Base Shot {shot_number} compiler prefix was edited")
        value = value[len(prefix) :]
        if shot_number == context.shot_count:
            final = _as_sentence(context.final_state_description)
            if context.final_state_start_ms > context.shot_starts_ms[-1]:
                final = f"{_timestamp(context.final_state_start_ms)} {_sentence_continuation(final)}"
            suffix = " " + final
            if not value.endswith(suffix):
                raise ValueError("H3 Base multi-shot final state was edited")
            value = value[: -len(suffix)]
        for cue in _cues_for_shot(context, shot_number):
            clause = _compiled_dialogue(cue, context.shot_starts_ms[shot_number - 1])
            if value.count(clause) != 1:
                raise ValueError(f"H3 Base dialogue {cue.cue_id} was edited")
            value = value.replace(clause, f"[[dialogue:{cue.cue_id}]]", 1)
        parts[f"shot_{shot_number}"] = value.strip()
    fields = direct_fl2va_multishot_editable_fields(context.shot_count)
    return "\n\n".join(f"{field}:\n{parts[field]}" for field in fields)


def lint_direct_fl2va_multishot_prompt(
    content: str,
    compiler_context: str | DirectFL2VAMultiShotCompilerContext | None = None,
) -> tuple[str, ...]:
    if not isinstance(content, str) or not content.strip():
        return ("Le prompt H3 Base multi-plan est vide.",)
    errors: list[str] = []
    value = strip_markdown_fence(content).replace("\r\n", "\n")
    raw_headings = list(re.finditer(r"(?m)^\[Shot\s+([^\]]+)\]", value))
    if not _MIN_SHOTS <= len(raw_headings) <= _MAX_SHOTS:
        errors.append("Le prompt H3 Base multi-plan doit contenir 2 a 4 plans.")
    elif tuple(match.group(1) for match in raw_headings) != tuple(
        str(number) for number in range(1, len(raw_headings) + 1)
    ):
        errors.append("Les plans H3 Base doivent etre contigus et ordonnes.")
    if "<scenetrans>" in value:
        errors.append("La recette H3 Base multi-plan V1 ne coupe pas un dialogue.")
    if "[[" in value or "]]" in value:
        errors.append("Un placeholder interne reste dans le prompt compile.")
    if _LEGACY_LABEL.search(re.sub(r"<d>.*?</d>", "", value, flags=re.DOTALL)):
        errors.append("Le prompt H3 Base contient un label visuel non autorise.")
    if re.search(r"(?m)^shot_\d+:[ \t]*", value):
        errors.append("Les champs internes du writer restent dans le prompt compile.")
    if compiler_context is None:
        return tuple(dict.fromkeys(errors))
    try:
        context = _context(compiler_context)
        parts = _split_document(value, context)
    except (TypeError, ValueError) as error:
        errors.append(str(error))
        return tuple(dict.fromkeys(errors))
    expected_times = context.shot_starts_ms[1:]
    actual_cut_times: list[int] = []
    for number in range(2, context.shot_count + 1):
        expected = compile_shot_heading(number, context.shot_starts_ms[number - 1])
        if value.count(expected) != 1:
            errors.append(f"Le heading compile du plan {number} est incorrect.")
        else:
            actual_cut_times.append(context.shot_starts_ms[number - 1])
    if tuple(actual_cut_times) != expected_times:
        errors.append("Les horloges de coupe ne correspondent pas au Plan.")
    for match in _TIMESTAMP.finditer(value):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if seconds >= 60 or timestamp_ms > context.duration_ms:
            errors.append("Un timestamp H3 Base depasse la duree derivee.")
    for shot_number in range(1, context.shot_count + 1):
        shot = parts[f"shot_{shot_number}"]
        camera = context.shot_cameras[shot_number - 1]
        expected = Counter(() if camera is None else (compile_camera_motion(camera),))
        for clause in {compile_camera_motion(item) for item in context.directives}:
            if shot.count(clause) != expected[clause]:
                errors.append(f"La camera compilee du plan {shot_number} a ete modifiee.")
        for cue in _cues_for_shot(context, shot_number):
            if shot.count(_compiled_dialogue(cue, context.shot_starts_ms[shot_number - 1])) != 1:
                errors.append(f"Le dialogue {cue.cue_id} manque ou est duplique.")
    visual_body = re.sub(
        r"<d>.*?</d>",
        "",
        "\n".join(parts.values()),
        flags=re.DOTALL,
    )
    bracketed = list(re.finditer(r"<Picture\s+([0-9]+)>", visual_body, re.IGNORECASE))
    plain = list(
        re.finditer(r"(?<!<)\bPicture\s+([0-9]+)\b", visual_body, re.IGNORECASE)
    )
    if context.mode is H3BaseInputMode.T2VA:
        if bracketed or plain:
            errors.append("Le mode T2VA ne doit contenir aucun label Picture.")
    elif context.mode in {H3BaseInputMode.I2VA, H3BaseInputMode.L2VA}:
        if plain or any(
            int(match.group(1)) != 1 or match.group(0) != "<Picture 1>"
            for match in bracketed
        ):
            errors.append(
                "I2VA/L2VA utilisent uniquement le label canonique <Picture 1>."
            )
    elif bracketed or any(
        int(match.group(1)) not in {1, 2}
        or match.group(0) != f"Picture {int(match.group(1))}"
        for match in plain
    ):
        errors.append(
            "FL2VA utilise uniquement les labels canoniques Picture 1 et Picture 2."
        )
    errors.extend(
        issue.message
        for issue in lint_h3_prompt(
            H3ProtocolMode(context.mode.value),
            value,
            expected_directives=context.directives,
        )
        if issue.severity is H3IssueSeverity.ERROR
    )
    return tuple(dict.fromkeys(errors))


def _validated_context(
    context: DirectFL2VAMultiShotCompilerContext,
) -> DirectFL2VAMultiShotCompilerContext:
    if not isinstance(context, DirectFL2VAMultiShotCompilerContext):
        raise TypeError("invalid H3 Base multi-shot compiler context")
    _validate_shot_count(context.shot_count)
    starts = context.shot_starts_ms
    if starts[0] != 0 or any(left >= right for left, right in zip(starts, starts[1:])):
        raise ValueError("H3 Base multi-shot starts must begin at zero and increase")
    if len(context.shot_cameras) != context.shot_count:
        raise ValueError("H3 Base multi-shot requires one optional camera per shot")
    if len(context.opening_compositions) != context.shot_count or any(
        not isinstance(item, str) or not item.strip() for item in context.opening_compositions
    ):
        raise ValueError("H3 Base multi-shot requires one opening composition per shot")
    for number, camera in enumerate(context.shot_cameras, 1):
        if camera is not None and camera.directive_id != f"camera_{number}":
            raise ValueError("H3 Base multi-shot camera IDs must match shot numbers")
    if (
        isinstance(context.final_state_start_ms, bool)
        or not isinstance(context.final_state_start_ms, int)
        or context.final_state_start_ms <= starts[-1]
        or isinstance(context.duration_ms, bool)
        or not isinstance(context.duration_ms, int)
        or context.duration_ms < context.final_state_start_ms
    ):
        raise ValueError("H3 Base multi-shot final timing is invalid")
    if not isinstance(context.final_state_description, str) or not context.final_state_description.strip():
        raise ValueError("H3 Base multi-shot final state is empty")
    cue_ids = tuple(cue.cue_id for cue in context.dialogue_cues)
    if cue_ids != tuple(f"dialogue_{number}" for number in range(1, len(cue_ids) + 1)):
        raise ValueError("H3 Base multi-shot dialogue IDs must be contiguous")
    for cue in context.dialogue_cues:
        shot_number = _shot_for_cue(context, cue)
        shot_end = (
            context.shot_starts_ms[shot_number]
            if shot_number < context.shot_count
            else context.final_state_start_ms
        )
        if cue.start_ms >= shot_end:
            raise ValueError("H3 Base multi-shot dialogue cannot cross a cut")
    compile_h3_base_multishot_header(context.mode, context.duration_ms, context.shot_count)
    return context


def _context(
    value: str | DirectFL2VAMultiShotCompilerContext,
) -> DirectFL2VAMultiShotCompilerContext:
    return (
        decode_direct_fl2va_multishot_context(value)
        if isinstance(value, str)
        else _validated_context(value)
    )


def _extract_fields(content: str, shot_count: int) -> dict[str, str]:
    fields = direct_fl2va_multishot_editable_fields(shot_count)
    matches = list(_WRITER_FIELD.finditer(content))
    if tuple(match.group(1) for match in matches) != fields:
        raise ValueError("H3 Base multi-shot writer fields have the wrong number or order")
    result: dict[str, str] = {}
    for index, field in enumerate(fields):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        result[field] = content[matches[index].end() : end].strip()
        if not result[field]:
            raise ValueError(f"H3 Base multi-shot writer field {field}: is empty")
    return result


def _validate_writer_fields(
    fields: dict[str, str],
    context: DirectFL2VAMultiShotCompilerContext,
) -> None:
    combined = "\n".join(fields.values())
    if _PICTURE.search(combined) or _LEGACY_LABEL.search(combined):
        raise ValueError("H3 Base multi-shot writer must not emit image labels")
    if _SHOT_HEADING.search(combined) or _TIMESTAMP.search(combined):
        raise ValueError("H3 Base multi-shot writer must not emit headings or timestamps")
    if _CUT_PROSE.search(combined):
        raise ValueError("H3 Base multi-shot writer must not emit cut prose")
    if "<scenetrans>" in combined:
        raise ValueError("H3 Base multi-shot V1 does not split dialogue across cuts")
    known = {cue.cue_id for cue in context.dialogue_cues}
    found = [match.group(1) for match in _DIALOGUE_PLACEHOLDER.finditer(combined)]
    if any(cue_id not in known for cue_id in found) or len(found) != len(set(found)):
        raise ValueError("H3 Base multi-shot writer contains an invalid dialogue placeholder")
    hidden = _DIALOGUE_PLACEHOLDER.sub("pending dialogue", combined)
    if "[[" in hidden or "]]" in hidden:
        raise ValueError("H3 Base multi-shot writer contains an internal placeholder")
    try:
        insert_ref2v_camera_clauses(hidden, ())
    except ValueError as error:
        raise ValueError("H3 Base multi-shot writer emitted free camera motion") from error


def _compile_shot_dialogues(
    body: str,
    context: DirectFL2VAMultiShotCompilerContext,
    shot_number: int,
) -> str:
    value = body
    for cue in _cues_for_shot(context, shot_number):
        placeholder = f"[[dialogue:{cue.cue_id}]]"
        clause = _compiled_dialogue(cue, context.shot_starts_ms[shot_number - 1])
        if placeholder in value:
            value = value.replace(placeholder, clause, 1)
        else:
            value = f"{value.rstrip()} {clause}"
    return value


def _compiled_dialogue(cue: DirectDialogueCue, shot_start_ms: int) -> str:
    speaker = cue.speaker.rstrip(" .:")
    delivery = re.sub(r"(?i)^(?:says?|speaks?)\s+", "", cue.delivery.rstrip(" .:"))
    spoken = compile_dialogue_tag(cue.language, cue.text)
    clause = f"{speaker} ({cue.speaker_id}) says"
    if delivery:
        clause += f" {delivery}"
    clause += f": {spoken}."
    return clause if cue.start_ms == shot_start_ms else f"{_timestamp(cue.start_ms)} {clause}"


def _shot_for_cue(
    context: DirectFL2VAMultiShotCompilerContext,
    cue: DirectDialogueCue,
) -> int:
    for index, start in enumerate(context.shot_starts_ms):
        next_start = (
            context.shot_starts_ms[index + 1]
            if index + 1 < context.shot_count
            else context.final_state_start_ms + 1
        )
        if start <= cue.start_ms < next_start:
            return index + 1
    raise ValueError(f"dialogue {cue.cue_id} is outside the action timeline")


def _cues_for_shot(
    context: DirectFL2VAMultiShotCompilerContext,
    shot_number: int,
) -> tuple[DirectDialogueCue, ...]:
    return tuple(cue for cue in context.dialogue_cues if _shot_for_cue(context, cue) == shot_number)


def _split_document(
    content: str,
    context: DirectFL2VAMultiShotCompilerContext,
) -> dict[str, str]:
    value = strip_markdown_fence(content).replace("\r\n", "\n")
    if context.header:
        prefix = context.header + "\n\n"
        if not value.startswith(prefix):
            raise ValueError("Le header H3 Base multi-plan ne correspond pas aux frames.")
        value = value[len(prefix) :]
    elif value.startswith("How the reference pictures align") or value.startswith("For the target video,"):
        raise ValueError("Le mode T2VA ne doit pas contenir de header image.")
    markers = {
        field: list(re.finditer(rf"(?m)^{field}:[ \t]*", value))
        for field in (
            "integrated_multimodal_description",
            "overall_soundscape",
            "non_diegetic_music",
        )
    }
    if any(len(matches) != 1 for matches in markers.values()):
        raise ValueError("Les trois champs H3 Base doivent apparaitre exactement une fois.")
    integrated_marker = markers["integrated_multimodal_description"][0]
    overall_marker = markers["overall_soundscape"][0]
    music_marker = markers["non_diegetic_music"][0]
    if not integrated_marker.start() < overall_marker.start() < music_marker.start():
        raise ValueError("Les trois champs H3 Base sont dans le mauvais ordre.")
    integrated = value[integrated_marker.end() : overall_marker.start()].strip()
    headings = tuple(
        compile_shot_heading(
            number,
            None if number == 1 else context.shot_starts_ms[number - 1],
        )
        for number in range(1, context.shot_count + 1)
    )
    matches: list[re.Match[str]] = []
    for heading in headings:
        found = list(re.finditer(rf"(?m)^{re.escape(heading)}(?=\s|$)", integrated))
        if len(found) != 1:
            raise ValueError(f"Le heading H3 Base doit apparaitre une fois : {heading}")
        matches.append(found[0])
    if tuple(match.group(0) for match in _SHOT_HEADING.finditer(integrated)) != headings:
        raise ValueError("Le prompt H3 Base contient un heading inattendu.")
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(integrated)
        result[f"shot_{index + 1}"] = integrated[match.end() : end].strip()
    result["overall_soundscape"] = value[overall_marker.end() : music_marker.start()].strip()
    result["non_diegetic_music"] = value[music_marker.end() :].strip()
    if any(not item for item in result.values()):
        raise ValueError("Un champ H3 Base multi-plan est vide.")
    return result


def _camera_payload(directive: H3CameraDirective) -> dict[str, str]:
    payload = {"id": directive.directive_id, "motion": directive.motion.value}
    if directive.amplitude is not None:
        payload["amplitude"] = directive.amplitude.value
    if directive.speed is not None:
        payload["speed"] = directive.speed.value
    if directive.target_clause:
        payload["target_clause"] = directive.target_clause
    return payload


def _timestamp(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"At {minutes:02d}:{seconds:02d}.{millis:03d},"


def _as_sentence(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if normalized and normalized[0].isalpha():
        normalized = normalized[0].upper() + normalized[1:]
    return normalized if normalized.endswith((".", "!", "?")) else normalized + "."


def _sentence_continuation(value: str) -> str:
    if value and value[0].isalpha():
        return value[0].lower() + value[1:]
    return value


def _validate_shot_count(shot_count: int) -> None:
    if isinstance(shot_count, bool) or not isinstance(shot_count, int):
        raise TypeError("shot count must be an integer")
    if not _MIN_SHOTS <= shot_count <= _MAX_SHOTS:
        raise ValueError("shot count must be between 2 and 4")


__all__ = [
    "DirectFL2VAMultiShotCompilerContext",
    "FL2VA_MULTISHOT_CONTEXT_MARKER",
    "compile_direct_fl2va_multishot_document",
    "compile_h3_base_multishot_header",
    "decode_direct_fl2va_multishot_context",
    "direct_fl2va_multishot_editable_contract",
    "direct_fl2va_multishot_editable_fields",
    "encode_direct_fl2va_multishot_context",
    "lint_direct_fl2va_multishot_prompt",
    "rehydrate_direct_fl2va_multishot_document",
]
