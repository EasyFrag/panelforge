"""Compilation helpers for the supervised single-frame I2VA path."""

from __future__ import annotations

from collections import Counter
import re

from panelforge.domain import H3CameraDirective

from .direct_ref2v_plan import (
    DirectDialogueCue,
    DirectMotionEndBehavior,
    DirectRef2VActionPlanV4,
    direct_ref2v_camera_clean_motion_fields,
    parse_direct_ref2v_action_plan_v2,
    parse_direct_ref2v_action_plan_v3,
    parse_direct_ref2v_action_plan_v4,
)
from .minimax_h3_protocol import compile_camera_motion
from .timed_camera_compiler import (
    TimedCameraPlacement,
    insert_i2v_camera_clauses,
    remove_i2v_camera_clauses,
)


I2VA_FIXED_INSTRUCTION = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
I2VA_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)


def apply_direct_i2v_timing(
    content: str,
    plan_content: str,
    *,
    preserve_field_linebreak: bool = False,
    contract_name: str = "direct I2VA",
    dialogue_aware: bool = False,
    motion_aware: bool = False,
    camera_clean: bool = False,
    insert_missing_final_landmark: bool = False,
) -> str:
    """Compile the derived duration and validate plan-owned landmarks.

    The LLM owns the semantic plan but not the redundant clocks.  The plan V2
    derives its final-state start and duration from the last beat plus
    ``final_hold_ms``; this function makes those values authoritative in the
    editable I2VA document.
    """

    if motion_aware:
        plan = parse_direct_ref2v_action_plan_v4(plan_content)
    elif dialogue_aware:
        plan = parse_direct_ref2v_action_plan_v3(plan_content)
    else:
        plan = parse_direct_ref2v_action_plan_v2(plan_content)
    clean_motion_fields = (
        direct_ref2v_camera_clean_motion_fields(plan_content)
        if motion_aware and camera_clean
        else None
    )
    value = _strip_fence(content).replace("\r\n", "\n")
    integrated = _field_body(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
        contract_name=contract_name,
    )
    duration_pattern = re.compile(
        r"The target video is one continuous [^\r\n]+?-second shot\."
    )
    matches = list(duration_pattern.finditer(integrated))
    if len(matches) != 1:
        raise ValueError(
            f"{contract_name} requires exactly one continuous-shot duration sentence"
        )
    duration_seconds = _format_duration_seconds(plan.duration_ms)
    replacement = (
        f"The target video is one continuous {duration_seconds}-second shot."
    )
    integrated = duration_pattern.sub(replacement, integrated, count=1)

    if (
        motion_aware
        and plan.motion_contract.end_behavior is DirectMotionEndBehavior.CONTINUE
    ):
        integrated = _insert_continuing_motion_contract(
            integrated,
            (
                clean_motion_fields[0]
                if clean_motion_fields is not None
                else plan.motion_contract.primary_motion
            ),
        )

    final_landmark = _format_timestamp(plan.final_start_ms)
    if motion_aware:
        final_sentence = _compiled_motion_final_sentence(
            plan,
            final_landmark,
            primary_motion=(
                clean_motion_fields[0]
                if clean_motion_fields is not None
                else None
            ),
            final_snapshot=(
                clean_motion_fields[1]
                if clean_motion_fields is not None
                else None
            ),
        )
        final_position = integrated.find(final_landmark)
        integrated = (
            f"{integrated[:final_position].rstrip()} {final_sentence}"
            if final_position >= 0
            else f"{integrated.rstrip()} {final_sentence}"
        )
    elif final_landmark not in integrated:
        if not insert_missing_final_landmark:
            raise ValueError(
                f"{contract_name} final prompt must contain the derived final-state "
                f"landmark {final_landmark}"
            )
        final_description = _as_sentence(plan.final_state.description)
        integrated = f"{integrated.rstrip()} {final_landmark} {final_description}"

    for camera in plan.camera_directives:
        if camera.start_ms == 0:
            continue
        expected_landmark = _format_timestamp(camera.start_ms)
        placeholder = f"[[camera:{camera.directive_id}]]"
        compiled_clause = compile_camera_motion(
            H3CameraDirective(
                directive_id=camera.directive_id,
                motion=camera.motion,
                amplitude=camera.amplitude,
                speed=camera.speed,
                target_clause=camera.target_clause or "",
            )
        )
        if not (
            re.search(
                rf"{re.escape(expected_landmark)}\s+(?:{re.escape(placeholder)}|"
                rf"{re.escape(compiled_clause)})",
                integrated,
            )
        ):
            raise ValueError(
                f"{contract_name} camera directive "
                f"{camera.directive_id} must start at {expected_landmark}"
            )

    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3}),", integrated):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if seconds >= 60 or timestamp_ms > plan.duration_ms:
            raise ValueError(
                f"{contract_name} final prompt contains a timestamp beyond the "
                "derived duration"
            )

    start, end = _field_span(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
        contract_name=contract_name,
    )
    separator = "\n" if preserve_field_linebreak else ""
    return value[:start] + separator + integrated.strip() + "\n" + value[end:]


def compile_direct_i2v_dialogue_cues(
    content: str,
    plan_content: str,
    *,
    contract_name: str = "H3 Base",
    motion_aware: bool = False,
    description_field: str = "integrated_multimodal_description",
    next_field: str = "overall_soundscape",
) -> tuple[str, tuple[str, ...]]:
    """Replace cue placeholders and restore omitted exact quotations."""

    plan = (
        parse_direct_ref2v_action_plan_v4(plan_content)
        if motion_aware
        else parse_direct_ref2v_action_plan_v3(plan_content)
    )
    value = _strip_fence(content).replace("\r\n", "\n")
    start, end = _field_span(
        value,
        description_field,
        next_field,
        contract_name=contract_name,
    )
    integrated = value[start:end].strip()
    recovered: list[str] = []
    for cue in plan.dialogue_cues:
        speaker = cue.speaker.rstrip(" .:")
        delivery = re.sub(
            r"(?i)^(?:says?|speaks?)\s+",
            "",
            cue.delivery.strip().rstrip(" .:"),
        )
        delivery_clause = f" {delivery}" if delivery else ""
        clause = (
            f"{speaker} ({cue.speaker_id}) says{delivery_clause}: "
            f"<d>[{cue.language}] {cue.text}</d>"
        )
        placeholder = f"[[dialogue:{cue.cue_id}]]"
        count = integrated.count(placeholder)
        if count > 1:
            raise ValueError(f"{contract_name} repeats {placeholder}")
        if count == 1:
            if re.search(
                rf"<d>\[[^\]\r\n]+\]\s*{re.escape(cue.text)}</d>",
                integrated,
            ):
                integrated, _ = _remove_exact_dialogue_copy(integrated, cue)
            integrated = re.sub(
                rf"(?:\bAt\s+\d{{2}}:\d{{2}}\.\d{{3}},\s*)?"
                rf"{re.escape(placeholder)}\.?\s*",
                "",
                integrated,
                count=1,
            )
            integrated = _insert_timed_dialogue(integrated, cue.start_ms, clause)
            continue
        tagged = re.compile(
            rf"<d>\[[^\]\r\n]+\]\s*{re.escape(cue.text)}</d>"
        )
        tagged_matches = list(tagged.finditer(integrated))
        if len(tagged_matches) > 1:
            raise ValueError(
                f"{contract_name} repeats the exact text of {cue.cue_id}"
            )
        if tagged_matches:
            match = tagged_matches[0]
            canonical_tag = f"<d>[{cue.language}] {cue.text}</d>"
            nearby = integrated[max(0, match.start() - 120) : match.start()]
            replacement = (
                canonical_tag
                if f"({cue.speaker_id})" in nearby
                else f"({cue.speaker_id}) {canonical_tag}"
            )
            integrated = (
                integrated[: match.start()]
                + replacement
                + integrated[match.end() :]
            )
            continue
        plain_count = integrated.count(cue.text)
        if plain_count > 1:
            raise ValueError(
                f"{contract_name} repeats the exact text of {cue.cue_id}"
            )
        if plain_count == 1:
            integrated = integrated.replace(
                cue.text,
                f"({cue.speaker_id}) <d>[{cue.language}] {cue.text}</d>",
                1,
            )
            recovered.append(cue.cue_id)
            continue
        integrated = _insert_timed_dialogue(integrated, cue.start_ms, clause)
        recovered.append(cue.cue_id)
    return (
        value[:start] + "\n" + integrated.strip() + "\n" + value[end:],
        tuple(recovered),
    )


def compile_animal_interview_dialogue_cues(
    content: str,
    plan_content: str,
    *,
    contract_name: str = "H3 Base animal interview",
    juvenile_animal_voice: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """Compile exact two-speaker interview turns with plan-derived end times.

    The prose writer is intentionally not trusted with dialogue text, speaker
    activity, or speech intervals.  Each cue inherits its end from the action
    step that contains its start timestamp, so the final prompt can state which
    mouth is moving for the complete interval rather than at one point in time.
    """

    plan = parse_direct_ref2v_action_plan_v4(plan_content)
    value = _strip_fence(content).replace("\r\n", "\n")
    start, end = _field_span(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
        contract_name=contract_name,
    )
    integrated = value[start:end].strip()
    recovered: list[str] = []
    animal_turn_index = 0
    for index, cue in enumerate(plan.dialogue_cues):
        placeholder = f"[[dialogue:{cue.cue_id}]]"
        placeholder_count = integrated.count(placeholder)
        if placeholder_count > 1:
            raise ValueError(f"{contract_name} repeats {placeholder}")

        # Some smaller writers echo both the placeholder and an inline <d>
        # clause. Remove only the exact cue-owned copy before deterministic
        # insertion; unrelated prose and other quotations remain untouched.
        integrated, removed_inline = _remove_exact_dialogue_copy(integrated, cue)
        cue_end_ms = _animal_interview_cue_end_ms(plan, index)
        clause = _animal_interview_dialogue_clause(
            cue,
            cue_end_ms,
            juvenile_animal_voice=juvenile_animal_voice,
            first_animal_turn=animal_turn_index == 0,
        )
        if cue.speaker_id == "S2":
            animal_turn_index += 1
        sentence = _timed_interval_sentence(cue.start_ms, cue_end_ms, clause)
        if placeholder_count == 1:
            integrated = re.sub(
                rf"(?:\bAt\s+\d{{2}}:\d{{2}}\.\d{{3}},\s*)?"
                rf"{re.escape(placeholder)}\.?\s*",
                sentence + " ",
                integrated,
                count=1,
            )
        else:
            recovered.append(cue.cue_id)
            integrated = _insert_timed_interval(
                integrated,
                cue.start_ms,
                cue_end_ms,
                clause,
            )
        if removed_inline and cue.cue_id not in recovered:
            recovered.append(cue.cue_id)

    return (
        value[:start] + "\n" + integrated.strip() + "\n" + value[end:],
        tuple(dict.fromkeys(recovered)),
    )


def lint_animal_interview_action_plan(content: str) -> tuple[str, ...]:
    """Validate the recipe-specific two-speaker timing contract."""

    try:
        plan = parse_direct_ref2v_action_plan_v4(content)
    except (TypeError, ValueError) as error:
        return (str(error),)
    errors: list[str] = []
    if len(plan.dialogue_cues) < 2:
        errors.append("animal interview requires at least one question and one answer")
    expected_speakers = tuple(
        "S1" if index % 2 == 0 else "S2"
        for index in range(len(plan.dialogue_cues))
    )
    actual_speakers = tuple(cue.speaker_id for cue in plan.dialogue_cues)
    if actual_speakers != expected_speakers:
        errors.append(
            "animal interview dialogue must alternate S1 interviewer and S2 animal"
        )
    starts = tuple(cue.start_ms for cue in plan.dialogue_cues)
    if starts != tuple(sorted(set(starts))):
        errors.append("animal interview dialogue starts must be unique and chronological")
    languages = {cue.language for cue in plan.dialogue_cues}
    if not languages.issubset({"French", "English"}) or len(languages) > 1:
        errors.append("animal interview dialogue must use one language: French or English")
    for index, cue in enumerate(plan.dialogue_cues):
        try:
            _animal_interview_cue_end_ms(plan, index)
        except ValueError as error:
            errors.append(str(error))
    if plan.motion_contract.end_behavior is not DirectMotionEndBehavior.CONTINUE:
        errors.append("animal interview final action must continue through the final frame")
    if plan.non_diegetic_music.strip().lower() not in {"n/a", "none", "no music"}:
        errors.append("animal interview non_diegetic_music must be N/A")
    return tuple(dict.fromkeys(errors))


def normalize_direct_i2v_camera_placeholders(content: str) -> str:
    """Recover the harmless period writers sometimes append to placeholders."""

    value = _strip_fence(content).replace("\r\n", "\n")
    placeholder = r"\[\[camera:camera_\d+\]\]"
    return re.sub(rf"({placeholder})\.(?=\s|$)", r"\1", value)


def insert_camera_owned_direct_i2v_clauses(
    content: str,
    placements: tuple[TimedCameraPlacement, ...],
    *,
    contract_name: str = "direct I2VA",
) -> str:
    """Insert plan-owned camera clauses into the I2VA writer envelope."""

    value = _strip_fence(content).replace("\r\n", "\n")
    start, end = _field_span(
        value,
        "integrated_multimodal_description",
        "overall_soundscape",
        contract_name=contract_name,
    )
    integrated = insert_i2v_camera_clauses(value[start:end].strip(), placements)
    return value[:start] + "\n" + integrated + "\n" + value[end:]


def rehydrate_camera_owned_direct_i2v_document(
    content: str,
    placements: tuple[TimedCameraPlacement, ...],
    *,
    contract_name: str = "direct I2VA",
) -> str:
    """Remove only compiler-inserted camera clauses for a writer revision."""

    value = _strip_fence(content).replace("\r\n", "\n")
    prefix = I2VA_FIXED_INSTRUCTION + "\n\n"
    if not value.startswith(prefix):
        raise ValueError(f"{contract_name} prompt is missing its fixed instruction")
    body = value[len(prefix) :]
    start, end = _field_span(
        body,
        "integrated_multimodal_description",
        "overall_soundscape",
        contract_name=contract_name,
    )
    integrated = remove_i2v_camera_clauses(body[start:end].strip(), placements)
    return (body[:start] + "\n" + integrated + "\n" + body[end:]).strip()


def rehydrate_direct_i2v_editable_document(
    content: str,
    directives: tuple[H3CameraDirective, ...],
) -> str:
    """Restore plan-owned placeholders without asking the LLM to infer them."""

    value = _strip_fence(content).replace("\r\n", "\n")
    prefix = I2VA_FIXED_INSTRUCTION + "\n\n"
    if not value.startswith(prefix):
        raise ValueError("direct I2VA prompt is missing its fixed instruction")
    body = value[len(prefix) :]
    expected_clauses = Counter(compile_camera_motion(item) for item in directives)
    for clause, expected_count in expected_clauses.items():
        if body.count(clause) != expected_count:
            raise ValueError(
                "compiled camera clause occurrence count does not match the "
                "direct I2VA plan"
            )
    for directive in directives:
        body = body.replace(
            compile_camera_motion(directive),
            f"[[camera:{directive.directive_id}]]",
            1,
        )
    return body.strip()


def _field_body(
    content: str,
    field: str,
    next_field: str | None,
    *,
    contract_name: str = "direct I2VA",
) -> str:
    start, end = _field_span(
        content,
        field,
        next_field,
        contract_name=contract_name,
    )
    return content[start:end].strip()


def _field_span(
    content: str,
    field: str,
    next_field: str | None,
    *,
    contract_name: str = "direct I2VA",
) -> tuple[int, int]:
    marker = re.search(rf"(?m)^{re.escape(field)}:[ \t]*", content)
    if marker is None:
        raise ValueError(f"{contract_name} document is missing {field}:")
    if next_field is None:
        return marker.end(), len(content)
    next_marker = re.search(rf"(?m)^{re.escape(next_field)}:[ \t]*", content)
    if next_marker is None or next_marker.start() <= marker.end():
        raise ValueError(f"{contract_name} document is missing {next_field}:")
    return marker.end(), next_marker.start()


def _format_duration_seconds(milliseconds: int) -> str:
    if milliseconds % 1000 == 0:
        return str(milliseconds // 1000)
    return f"{milliseconds / 1000:.3f}".rstrip("0").rstrip(".")


def _format_timestamp(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"At {minutes:02d}:{seconds:02d}.{millis:03d},"


def _insert_continuing_motion_contract(integrated: str, primary_motion: str) -> str:
    action = _sentence_continuation(primary_motion).rstrip(".!?")
    sentence = (
        f"Throughout the entire shot, {action}; this primary motion continues "
        "without interruption through the final frame."
    )
    if sentence in integrated:
        return integrated
    duration = re.search(
        r"The target video is one continuous [^\r\n]+?-second shot\.",
        integrated,
    )
    if duration is None:
        return integrated
    after_duration = integrated[duration.end() :]
    scene_end = re.search(r"[.!?](?=\s|$)", after_duration)
    insertion = (
        duration.end() + scene_end.end()
        if scene_end is not None
        else duration.end()
    )
    return (
        integrated[:insertion].rstrip()
        + " "
        + sentence
        + " "
        + integrated[insertion:].lstrip()
    )


def _compiled_motion_final_sentence(
    plan: DirectRef2VActionPlanV4,
    final_landmark: str,
    *,
    primary_motion: str | None = None,
    final_snapshot: str | None = None,
) -> str:
    snapshot = _sentence_continuation(
        final_snapshot or plan.final_state.description
    ).rstrip(".!?")
    if plan.motion_contract.end_behavior is DirectMotionEndBehavior.CONTINUE:
        motion = _sentence_continuation(
            primary_motion or plan.motion_contract.primary_motion
        ).rstrip(".!?")
        return (
            f"{final_landmark} while {motion}, {snapshot}. The video ends during "
            "the same ongoing motion, without a pause, freeze, or held pose."
        )
    return f"{final_landmark} {snapshot}."


def _as_sentence(value: str) -> str:
    stripped = value.strip()
    return stripped if stripped.endswith((".", "!", "?")) else stripped + "."


def _sentence_continuation(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[:1].lower() + stripped[1:]


def _insert_timed_dialogue(integrated: str, start_ms: int, clause: str) -> str:
    clause_sentence = clause + "."
    if start_ms == 0:
        opening = re.match(
            r"^\[Shot 1\]\s+The target video is one continuous "
            r"[^\r\n]+?-second shot\.",
            integrated,
        )
        if opening is not None:
            return (
                integrated[: opening.end()]
                + " "
                + clause_sentence
                + " "
                + integrated[opening.end() :].lstrip()
            )
        marker = "[Shot 1]"
        if integrated.startswith(marker):
            return (
                marker
                + " "
                + clause_sentence
                + " "
                + integrated[len(marker) :].lstrip()
            )
        return clause_sentence + " " + integrated
    later = None
    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3}),", integrated):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if timestamp_ms == start_ms:
            return (
                integrated[: match.end()]
                + " "
                + clause_sentence
                + " "
                + integrated[match.end() :].lstrip()
            )
        if timestamp_ms > start_ms:
            later = match.start()
            break
    sentence = f"{_format_timestamp(start_ms)} {clause_sentence}"
    if later is None:
        return integrated.rstrip() + " " + sentence
    return integrated[:later].rstrip() + " " + sentence + " " + integrated[later:]


def _animal_interview_cue_end_ms(
    plan: DirectRef2VActionPlanV4,
    cue_index: int,
) -> int:
    cue = plan.dialogue_cues[cue_index]
    steps = tuple(step for beat in plan.beats for step in beat.steps)
    containing = next(
        (
            step
            for step in steps
            if step.start_ms <= cue.start_ms < step.end_ms
        ),
        None,
    )
    if containing is None:
        raise ValueError(
            f"H3 Base animal interview cue {cue.cue_id} does not belong to an action step"
        )
    next_start = (
        plan.dialogue_cues[cue_index + 1].start_ms
        if cue_index + 1 < len(plan.dialogue_cues)
        else plan.duration_ms
    )
    if next_start < containing.end_ms:
        raise ValueError(
            f"H3 Base animal interview cue {cue.cue_id} does not have a dedicated action step"
        )
    end_ms = containing.end_ms
    if end_ms <= cue.start_ms:
        raise ValueError(
            f"H3 Base animal interview cue {cue.cue_id} has no positive speech interval"
        )
    return end_ms


def _animal_interview_dialogue_clause(
    cue: DirectDialogueCue,
    end_ms: int,
    *,
    juvenile_animal_voice: bool = False,
    first_animal_turn: bool = False,
) -> str:
    speaker = cue.speaker.rstrip(" .:")
    delivery = re.sub(
        r"(?i)^(?:says?|speaks?|asks?)\s+",
        "",
        cue.delivery.strip().rstrip(" .:"),
    )
    delivery_clause = f" {delivery}" if delivery else ""
    tag = f"<d>[{cue.language}] {cue.text}</d>"
    if cue.speaker_id == "S1":
        return (
            "the interviewed animal remains silent with its mouth closed while "
            f"{speaker} ({cue.speaker_id}) asks{delivery_clause}: {tag}"
        )
    if juvenile_animal_voice:
        emotional_delivery = f", {delivery}" if delivery else ""
        voice_identity = (
            "in an unmistakably very young childlike voice with a small, light, "
            "noticeably high-pitched timbre and gentle youthful cadence, natural "
            "and clearly intelligible rather than squeaky or cartoonish, never "
            "adult, deep or mature"
            if first_animal_turn
            else "again in the same very young, small, light, noticeably "
            "high-pitched childlike voice"
        )
        return (
            f"only {speaker} ({cue.speaker_id}) speaks {voice_identity}"
            f"{emotional_delivery}: {tag} Only the interviewed animal's mouth "
            "moves during this response; the interviewer remains silent"
        )
    return (
        f"only {speaker} ({cue.speaker_id}) speaks{delivery_clause}: {tag} "
        "Only the interviewed animal's mouth moves during this response; the "
        "interviewer remains silent"
    )


def _remove_exact_dialogue_copy(
    integrated: str,
    cue: DirectDialogueCue,
) -> tuple[str, bool]:
    tag = re.compile(rf"<d>\[[^\]\r\n]+\]\s*{re.escape(cue.text)}</d>")
    matches = list(tag.finditer(integrated))
    if len(matches) > 1:
        raise ValueError(
            "H3 Base animal interview repeats the exact text of " + cue.cue_id
        )
    if not matches:
        if cue.text in integrated:
            raise ValueError(
                "H3 Base animal interview writer copied dialogue without its "
                f"placeholder for {cue.cue_id}"
            )
        return integrated, False
    match = matches[0]
    delivery = cue.delivery.strip().rstrip(" .:")
    prefix = re.compile(
        rf"(?:{re.escape(cue.speaker.rstrip(' .:'))}\s*)?"
        rf"\({re.escape(cue.speaker_id)}\)\s*"
        rf"(?:says?|speaks?|asks?)?\s*"
        rf"(?:{re.escape(delivery)})?\s*:?\s*$",
        re.IGNORECASE,
    )
    nearby_start = max(0, match.start() - 180)
    nearby = integrated[nearby_start:match.start()]
    prefix_match = prefix.search(nearby)
    remove_start = (
        nearby_start + prefix_match.start()
        if prefix_match is not None
        else match.start()
    )
    remove_end = match.end()
    punctuation = re.match(r"[\s,;:.]*", integrated[remove_end:])
    if punctuation is not None:
        remove_end += punctuation.end()
    return (
        (integrated[:remove_start].rstrip() + " " + integrated[remove_end:].lstrip()).strip(),
        True,
    )


def _insert_timed_interval(
    integrated: str,
    start_ms: int,
    end_ms: int,
    clause: str,
) -> str:
    sentence = _timed_interval_sentence(start_ms, end_ms, clause)
    if start_ms == 0:
        opening = re.match(
            r"^\[Shot 1\]\s+The target video is one continuous "
            r"[^\r\n]+?-second shot\.",
            integrated,
        )
        if opening is not None:
            after_opening = integrated[opening.end() :]
            scene_end = re.search(r"[.!?](?=\s|$)", after_opening)
            insertion = (
                opening.end() + scene_end.end()
                if scene_end is not None
                else opening.end()
            )
            return (
                integrated[:insertion]
                + " "
                + sentence
                + " "
                + integrated[insertion:].lstrip()
            )
        return sentence + " " + integrated

    later = None
    for match in re.finditer(r"\bAt\s+(\d{2}):(\d{2})\.(\d{3}),", integrated):
        minutes, seconds, milliseconds = (int(part) for part in match.groups())
        timestamp_ms = minutes * 60_000 + seconds * 1_000 + milliseconds
        if timestamp_ms > start_ms:
            later = match.start()
            break
    if later is None:
        return integrated.rstrip() + " " + sentence
    return integrated[:later].rstrip() + " " + sentence + " " + integrated[later:]


def _timed_interval_sentence(start_ms: int, end_ms: int, clause: str) -> str:
    return (
        f"From {_format_timestamp_value(start_ms)} to "
        f"{_format_timestamp_value(end_ms)}, {clause}."
    )


def _format_timestamp_value(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def _strip_fence(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 : -3].strip()
    return value
