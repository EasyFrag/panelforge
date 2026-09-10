"""Input contracts and compact one-call compilation for mono video recipes."""

from dataclasses import asdict, dataclass
from collections import Counter
import hashlib
import json
import re

from panelforge.domain.prompt_composition import PromptComposition
from panelforge.domain.prompt_lab import CreativeFreedomAxes, PromptLabSession
from panelforge.domain.minimax_h3 import H3CameraDirective, H3CameraMotion
from .direct_fl2va_prompt import (
    DirectFL2VAContext, H3BaseInputMode, compile_h3_base_header,
    derive_h3_base_input_mode, lint_direct_fl2va_prompt, requested_h3_base_duration_ms,
)
from .minimax_h3_protocol import (
    H3IssueSeverity, H3ProtocolMode, compile_camera_motion,
    extract_compiled_camera_clauses, lint_h3_prompt,
)
from .minimax_h3_protocol import normalize_dialogue_language_tags
from .direct_ref2v_prompt import lint_direct_ref2v_prompt
from .direct_ref2v_plan import extract_explicit_dialogues
from .vocal_policy import speech_lines, validate_speech


DIRECT_PROMPT_CONTRACT = "minimax.h3.mono.prompt_direct_v1"


@dataclass(frozen=True, slots=True)
class PreparationSource:
    source_id: str
    source_text: str
    content: str
    creative_freedom: int
    creative_axes: CreativeFreedomAxes | None
    creative_audacity: int
    vocal_dialogues: tuple[str, ...] = ()


def preparation_source(session: PromptLabSession, composition: PromptComposition) -> PreparationSource:
    intent = composition.preparation_intent
    if intent is not None:
        snapshot = asdict(intent)
        # A new default field must not invalidate existing approved documents.
        if snapshot["creative_axes"] is not None and not snapshot["creative_axes"].get("dialogue"):
            snapshot["creative_axes"].pop("dialogue", None)
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return PreparationSource(f"intent:{digest}", intent.source_text, intent.source_text,
                                 intent.creative_freedom, intent.creative_axes, intent.creative_audacity)
    brief = session.active_brief_revision
    if not session.brief_complete or brief is None:
        raise ValueError("approve a current structured brief first")
    return PreparationSource(f"brief:{brief.revision_id}", brief.source_text, brief.content,
                             brief.creative_freedom, brief.creative_axes, brief.creative_audacity,
                             brief.vocal_dialogues)


def direct_prompt_context(session, mapping, source_text: str, *, reference_header: str | None = None) -> str:
    duration_ms = requested_h3_base_duration_ms(source_text) or 8000
    mode = "ref2va" if reference_header is not None else derive_h3_base_input_mode(session, mapping).value
    header = reference_header if reference_header is not None else compile_h3_base_header(
        derive_h3_base_input_mode(session, mapping), duration_ms,
    )
    return json.dumps({"mode": mode, "header": header, "duration_ms": duration_ms,
                       "dialogues": extract_explicit_dialogues(source_text)}, ensure_ascii=False)


def compile_direct_prompt(result: str, context_text: str) -> str:
    context = json.loads(context_text)
    value = result.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.split("\n", 1)[1][:-3].strip()
    try:
        fields = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("Le prompt direct doit contenir l'objet JSON demandé.") from error
    keys = ("camera_motion", "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
    if not isinstance(fields, dict) or set(fields) != set(keys):
        raise ValueError("Le prompt direct attend la caméra et les trois champs vidéo.")
    if any(not isinstance(fields[key], str) or not fields[key].strip() for key in keys):
        raise ValueError("Les quatre champs du prompt direct doivent être du texte non vide.")
    camera = compile_camera_motion(H3CameraDirective("camera_1", H3CameraMotion(fields["camera_motion"])))
    description = fields["integrated_multimodal_description"].strip()
    if re.search(r"(?i)<(?:Picture|Image|Subject)\s*\d+>|@image\s*\d+|\bPicture\s+\d+|\[Shot\s+\d+\]", description):
        raise ValueError("La description directe ne doit pas répéter les labels ou headings compilés.")
    seconds = f"{context['duration_ms'] / 1000:g}"
    opening = f"The target video is one continuous {seconds}-second shot."
    if context["mode"] == "ref2va":
        body = f"{opening}\n\nShot 1: {camera} {description}"
    else:
        body = f"integrated_multimodal_description: [Shot 1] {opening} {camera} {description}"
    body += f"\n\noverall_soundscape: {fields['overall_soundscape'].strip()}\n\nnon_diegetic_music: {fields['non_diegetic_music'].strip()}"
    content = normalize_dialogue_language_tags((context["header"] + "\n\n" + body).strip())
    errors = direct_prompt_errors(content, context=context)
    if errors:
        raise ValueError(" ".join(errors))
    return content


def direct_prompt_errors(content: str, *, context: dict | None = None, ref2v: bool = False) -> tuple[str, ...]:
    if context is not None:
        mode = context["mode"]
        header = context["header"]
        if header and not content.startswith(header + "\n\n"):
            return ("Le header du prompt direct ne correspond pas aux références du run.",)
    else:
        mode = "ref2va" if ref2v else (
            "fl2va" if "Picture 2 (from Shot 1)" in content else
            "l2va" if content.startswith("How the reference pictures align") else
            "i2va" if content.startswith("For the target video,") else "t2va"
        )
    errors = [issue.message for issue in lint_h3_prompt(H3ProtocolMode(mode), content) if issue.severity is H3IssueSeverity.ERROR]
    if len(extract_compiled_camera_clauses(content)) != 1:
        errors.append("Cette recette directe requiert une seule directive caméra canonique.")
    if mode == "ref2va":
        errors.extend(lint_direct_ref2v_prompt(content))
    elif len(re.findall(r"\[Shot 1\]", content)) != (2 if mode in {"i2va", "l2va"} else 1):
        errors.append("Le prompt direct doit contenir un seul plan vidéo.")
    if re.search(r"\[Shot\s+(?:[2-9]|\d{2,})\]", content):
        errors.append("Cette recette directe est mono-plan.")
    fields = ("overall_soundscape", "non_diegetic_music")
    if mode != "ref2va":
        fields = ("integrated_multimodal_description", *fields)
    positions = []
    for field in fields:
        matches = list(re.finditer(rf"(?m)^{field}:[ \t]*", content))
        if len(matches) != 1:
            errors.append(f"Le champ {field}: doit apparaître exactement une fois.")
        else:
            positions.append(matches[0].start())
    if positions != sorted(positions):
        errors.append("Les champs du prompt direct ne sont pas dans l'ordre attendu.")
    if context is not None:
        duration_sentence = f"The target video is one continuous {context['duration_ms'] / 1000:g}-second shot."
        if content.count(duration_sentence) != 1:
            errors.append("La durée du prompt direct doit rester celle de l'intention enregistrée.")
        if mode != "ref2va":
            errors.extend(lint_direct_fl2va_prompt(content, DirectFL2VAContext(
                H3BaseInputMode(mode), context["header"], context["duration_ms"], (),
            )))
        actual_dialogues = Counter(re.findall(r"<d>\s*\[[^\]]+\]\s*(.*?)\s*</d>", content, flags=re.DOTALL))
        if context.get("vocal_policy_version"):
            try:
                validate_speech(speech_lines(content), context.get("dialogues", ()),
                    level=context.get("dialogue_level", 0), source_text=context.get("source_text", ""),
                    duration_ms=context["duration_ms"], locked=context.get("chosen_dialogues"))
            except ValueError as error:
                errors.append(str(error))
        elif actual_dialogues != Counter(context.get("dialogues", ())):
            errors.append("Le prompt direct doit préserver les paroles exactes de l'intention, sans dialogue supplémentaire.")
        times = [int(m) * 60000 + int(s) * 1000 + int(ms) for m, s, ms in re.findall(r"\b(\d{2}):(\d{2})\.(\d{3})\b", content)]
        if times != sorted(times) or any(time > context["duration_ms"] for time in times):
            errors.append("Les jalons du prompt direct doivent être chronologiques et dans la durée du clip.")
    return tuple(dict.fromkeys(errors))
