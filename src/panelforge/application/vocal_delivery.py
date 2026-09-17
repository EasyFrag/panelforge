"""Conservative local normalization of explicitly requested voice-over cues.

This module does not infer delivery from prose.  It only acts when the user
source labels a quoted line as voice-over/thought and the Writer uses a known,
unambiguous voice-over wrapper around the exact same dialogue tag.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


_DIALOGUE = re.compile(r"<d>\s*\[[^\]]+\]\s*(.*?)\s*</d>", re.DOTALL)
_QUOTED_LINE = re.compile(
    r"(?m)^(?P<label>[^\r\n:]{1,180})\s*:\s*(?:"
    r"«\s*(?P<french>[^»\r\n]+?)\s*»|"
    r"“\s*(?P<curly>[^”\r\n]+?)\s*”|"
    r'"\s*(?P<straight>[^"\r\n]+?)\s*")\s*$'
)
_CANONICAL_WRAPPER = re.compile(r"(?i)\bsays\s+in\s+an\s+off-screen\s+voiceover\s*:\s*$")
_CLOSED_LIPS = re.compile(r"(?is)\blips\b.{0,80}\b(?:closed|still)\b")


@dataclass(frozen=True, slots=True)
class VoiceoverCue:
    speaker: str
    text: str
    delivery: str
    speaker_id: str


@dataclass(frozen=True, slots=True)
class VoiceoverNormalization:
    content: str
    applied: int = 0
    warnings: tuple[str, ...] = ()
    speaker_ids: tuple[tuple[str, str], ...] = ()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", "".join(
        char for char in normalized.upper() if not unicodedata.combining(char))).split())


def _label_parts(label: str) -> tuple[str, str]:
    value = label.strip()
    voice_first = re.fullmatch(
        r"(?:VOIX\s+OFF|VOICE\s*OVER|V\.?\s*O\.?|NARRATION)\s+(?:DE|:)\s+(.+)",
        value, re.IGNORECASE,
    )
    if voice_first:
        return voice_first.group(1).strip(), "voice_over"
    parenthetical = re.fullmatch(r"(.+?)\s*(?:\(([^()]*)\)|\[([^\[\]]*)\])", value)
    if parenthetical:
        speaker = parenthetical.group(1).strip()
        note = parenthetical.group(2) or parenthetical.group(3)
    else:
        separated = re.fullmatch(r"(.+?)\s*[—–-]\s*(.+)", value)
        if not separated:
            return value, "spoken"
        speaker, note = separated.group(1).strip(), separated.group(2).strip()
    marker = _fold(note)
    if any(item in marker for item in ("VOIX OFF", "VOICE OVER", "NARRATION")) or marker in {"VO", "V O"}:
        return speaker, "voice_over"
    if any(item in marker for item in ("PENSEE", "VOIX INTERIEURE", "MONOLOGUE INTERIEUR", "INNER VOICE")):
        return speaker, "thought"
    return speaker, "spoken"


def voiceover_cues(source_text: str) -> tuple[VoiceoverCue, ...]:
    """Read explicit quoted delivery labels without interpreting free prose."""
    if not isinstance(source_text, str) or not source_text:
        return ()
    raw = []
    speaker_ids: dict[str, str] = {}
    for match in _QUOTED_LINE.finditer(source_text):
        speaker, delivery = _label_parts(match.group("label"))
        if not speaker:
            continue
        key = _fold(speaker)
        speaker_ids.setdefault(key, f"S{len(speaker_ids) + 1}")
        text = next(value for value in (match.group("french"), match.group("curly"), match.group("straight")) if value)
        raw.append(VoiceoverCue(speaker, text.strip(), delivery, speaker_ids[key]))
    return tuple(raw)


def _known_wrapper(prefix: str, cue: VoiceoverCue):
    speaker = re.escape(cue.speaker).replace(r"\ ", r"\s+")
    subject = rf"(?:(?:{speaker})(?:['’]s)?|(?:her|his|their))"
    reference = r"(?P<reference>\s+\(<Picture\s+[1-9]\d*>\))?"
    forms = (
        r"(?:off[- ]screen\s+voice|inner\s+voice(?:[- ]over)?|voice[- ]over|voiceover)\s+"
        r"(?:narrates|reads|says|speaks)",
        r"voice\s+is\s+heard\s+in\s+voice[- ]over",
        r"(?:narrates|reads|says|speaks)\s+in\s+(?:an?\s+)?(?:off[- ]screen\s+)?voice[- ]over",
    )
    return re.search(rf"(?i)(?P<wrapper>{subject}{reference}\s+(?:{'|'.join(forms)})\s*:?\s*)$", prefix)


def normalize_voiceovers(content: str, source_text: str) -> VoiceoverNormalization:
    """Normalize only exact, explicitly labelled and structurally recognized cues.

    Ambiguous Writer prose is retained byte-for-byte and reported as a warning;
    this function never rejects a prompt.
    """
    cues = voiceover_cues(source_text)
    requested = [cue for cue in cues if cue.delivery in {"voice_over", "thought"}]
    if not requested:
        return VoiceoverNormalization(content)

    queues: dict[str, list[VoiceoverCue]] = {}
    for cue in cues:
        queues.setdefault(cue.text, []).append(cue)
    chunks: list[str] = []
    cursor = 0
    applied = 0
    warnings = []
    for match in _DIALOGUE.finditer(content):
        text = match.group(1).strip()
        candidates = queues.get(text)
        cue = candidates.pop(0) if candidates else None
        prefix = content[cursor:match.start()]
        if cue is None or cue.delivery not in {"voice_over", "thought"}:
            chunks.extend((prefix, match.group(0)))
            cursor = match.end()
            continue

        known = _known_wrapper(prefix, cue)
        canonical = _CANONICAL_WRAPPER.search(prefix)
        if known:
            reference = known.group("reference") or ""
            replacement = f"{cue.speaker}{reference} ({cue.speaker_id}) says in an off-screen voiceover: "
            prefix = prefix[:known.start("wrapper")] + replacement
        elif not canonical:
            warnings.append(
                f"Voix off {cue.speaker_id} ({cue.speaker}) : formulation du Rédacteur non reconnue ; prompt conservé."
            )
            chunks.extend((prefix, match.group(0)))
            cursor = match.end()
            continue

        chunks.extend((prefix, match.group(0)))
        following = content[match.end():match.end() + 180]
        if not _CLOSED_LIPS.search(following):
            chunks.append(" while all visible characters keep their lips completely closed and still")
        cursor = match.end()
        applied += 1
    chunks.append(content[cursor:])
    ids = tuple(dict.fromkeys((cue.speaker, cue.speaker_id) for cue in requested))
    return VoiceoverNormalization("".join(chunks), applied, tuple(warnings), ids)
