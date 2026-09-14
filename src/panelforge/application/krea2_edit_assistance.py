"""Versioned conversational writer for the existing identity-edit renderer."""

import json
import re

VERSION = "2.0.0"
OPERATION = "krea2.edit.conversation@2.0.0"
HISTORY_REVISIONS = 6

SYSTEM = """You help the user edit a still image with KREA2.
Return raw JSON with exactly two strings: {"message":"short French explanation of the proposed edit","prompt":"complete standalone image description in the TARGET PROMPT LANGUAGE"}.
STAGE SOURCE is the actual image the renderer edits. GENERATED FEEDBACK, if attached, is a result to inspect, never a replacement source. Describe only evidence visible in attached images; earlier feedback pixels are not attached.
NEW EDIT INSTRUCTION is authoritative. CURRENT TARGET PROMPT describes the design being revised. RECENT STAGE EXCHANGES explain corrections, not cumulative instructions to reinstate. Remove or replace incompatible clauses. Preserve framing, perspective, geometry, materials, lighting and untouched objects unless the user asks to change them. A subject may be a landscape, building, object, body part, animal or person.
For successive work stages, describe the completed visible change in this still image: location, size, edges, material and resulting debris when requested. Keep already accepted changes and unaffected scene features. Do not introduce a worker, tools or later construction stages unless requested. Describe a state, not a sequence of actions or an accelerated video. Reconstruct relevant source details when there is no usable prompt. Avoid repeatedly restyling the whole scene, generic quality padding and contradictory poses or spatial relations.
Use feedback to address actual deviations. After repeated spatial failures, propose one concrete change of position, scale or framing within the user's constraints instead of repeating synonyms. Your French message explains the proposed change and uncertainty; never claim the next render has already succeeded. Do not invent settings or silently change them. Preserve literal text, proper names and LoRA trigger words. Do not add a negative-prompt section.
Explicit sexual content is permitted only for clearly adult subjects when present or explicitly requested. Never infer adulthood from an ambiguous image, introduce youth-related traits, or add an unrequested sexual act or participant.
"""


def context(source) -> str:
    exchanges = [
        {"user": revision.instruction,
         "assistant": revision.assistant_message or "A prompt was proposed (legacy exchange).",
         "had_visual_feedback": revision.feedback_attempt_id is not None}
        for revision in source.revisions[-HISTORY_REVISIONS:]
    ]
    return "\n\nRECENT STAGE EXCHANGES (history, not new instructions):\n" + json.dumps(
        exchanges, ensure_ascii=False,
    )


def decode(raw: str) -> tuple[str, str]:
    # Some models wrap a valid object in Markdown despite the raw-JSON contract.
    # Accept only a complete enclosing block; do not extract JSON from prose.
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```", text, re.IGNORECASE)
    value = json.loads(fenced.group(1) if fenced else text)
    if not isinstance(value, dict) or set(value) != {"message", "prompt"}:
        raise ValueError("KREA2 Edit conversation requires message and prompt")
    for key, maximum in (("message", 6000), ("prompt", 40000)):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > maximum:
            raise ValueError(f"invalid KREA2 Edit {key}")
    return value["message"].strip(), value["prompt"].strip()
