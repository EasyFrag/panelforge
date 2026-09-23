"""Experimental subject-first assistance with a smaller, explicit context.

No summarization call or persistent inferred memory: the current prompt and
verbatim recent feedback remain the source of truth. V1 is an immutable witness.
"""

from collections.abc import Sequence
import re
import unicodedata

from panelforge.domain.krea2_assisted import Krea2AssistedProject
from . import krea2_assisted_v1


VERSION = "2.0.0"
LABEL = "V2 · sujet et contexte compact · expérimental"
MAX_TOKENS = krea2_assisted_v1.MAX_TOKENS
CREATION_OPERATION = "krea2.assisted.creation_chat@2.0.0"
RECIPE_OPERATION = "krea2.assisted.recipe_chat@2.0.0"
HISTORY_ENTRIES = 13

_CREATION_SYSTEM = """You are a collaborative KREA2 text-to-image prompt writer.
Return raw JSON only with exactly these fields:
{"message":"brief French reply explaining the proposed prompt changes","questions":["up to three material questions"],"prompt":"complete standalone prompt in the TARGET PROMPT LANGUAGE","recommendations":["optional concise advice"]}

A subject can be an object, shoe, hand or other body part, animal, creature, person, landscape, or several interacting elements. Never assume a human protagonist. Describe the visible subject, not an invented biography.

Use NEW USER MESSAGE as authoritative. CURRENT TARGET PROMPT carries the current design; recent exchanges explain requested changes, not cumulative instructions to reinstate. ORIGINAL INTENTION is only the starting point and yields to later corrections. Separate stable visual traits (shape, proportions, material, color, environment, lighting and framing the user wants to keep) from the current scene state (pose, contact, props, damage, egg open/closed, before/after an action). Preserve unaffected traits, but change any of them when explicitly requested. Replacing a scene state removes incompatible previous states; do not keep them as a growing list of negative clauses. Do not infer a new prop, hand position or setting simply to bridge two images.

Images are evidence for the LLM only, never inputs to this text-to-image renderer. REFERENCE IMAGE provides source evidence; GENERATED RESULT is the explicitly selected output with its actual prompt/settings; TURN GUIDANCE IMAGE applies to the newest request only unless the user asks to retain its traits. Selecting an old result does not rewind the conversation. If asked to start again from that result, use its visible traits and exact prompt as the baseline, then apply the newest request without importing incompatible later scene states. Distinguish visual evidence from hypotheses; do not claim to see an earlier image whose pixels are not attached.

When a result is attached, identify relevant visible deviations. After repeated spatial failures reported by the user or shown in attached results, change one concrete framing, scale or position choice within the user's constraints; do not just strengthen synonyms. Write one complete positive still-image description: subject and required state, spatial relations, setting, finish. Preserve distinctive details; omit repetition and quality padding. Minimum 80 characters (40 for Chinese). Use a short exclusion only to resolve ambiguity. No edit instructions ('keep the same', 'replace', 'as before', 'from this image'), contradictory poses or impossible contacts.

In French, explain preserved traits, the proposed prompt change and uncertainty; never claim the render is already corrected. Ask only material questions and always provide a usable prompt. Do not invent resource names, infer capabilities from filenames or change settings automatically. A strong LoRA can reduce adherence; do not promise exact continuity. Do not invent workflows or recommend KREA Edit.

Explicit sexual content may be described only when every depicted person is unambiguously an adult and the user requests it. Never infer adulthood from an ambiguous image, introduce youth-related traits, or add an unrequested sexual act or participant. Never output Markdown or commentary outside the JSON."""


def system_prompt(mode: str) -> str:
    # Publication contracts are unchanged; only the conversation context is compacted.
    return _CREATION_SYSTEM if mode == "creation" else krea2_assisted_v1.system_prompt(mode)


def _words(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("_", " ")
    return set(re.findall(r"[\w]+", normalized))


def needs_resources(message: str) -> bool:
    return bool(_words(message) & {
        "lora", "loras", "checkpoint", "checkpoints", "modele", "modeles",
        "model", "models", "ressource", "ressources", "resource", "resources",
        "bf16", "fp8", "int8", "strength", "poids", "force", "catalogue", "catalog",
    })


def needs_recipes(message: str) -> bool:
    return bool(_words(message) & {"recipe", "recipes", "recette", "recettes"})


def resource_memory(models: Sequence[object], loras: Sequence[object], message: str) -> str:
    requested = _words(message)

    def names(values: Sequence[object], limit: int) -> str:
        available = [getattr(value, "comfy_name", "") for value in values
                     if getattr(value, "selectable", True) and getattr(value, "comfy_name", "")]
        ranked = sorted(dict.fromkeys(available), key=lambda name: -len(_words(name) & requested))
        return "\n".join(f"- {name}" for name in ranked[:limit]) or "none exposed"

    return "PARTIAL CATALOGUE (not an exhaustive inventory)\nCHECKPOINTS:\n" + names(models, 12) + "\nLORAS:\n" + names(loras, 16)


def user_prompt(
    project: Krea2AssistedProject,
    message: str,
    *,
    selected: str,
    memory: str,
    resources: str,
    language_instruction: str,
) -> str:
    # Keep every recent correction and reply verbatim; omit only obsolete full
    # prompt copies. This is context selection, not an inferred memory summary.
    turns = []
    for turn in project.turns[-(HISTORY_ENTRIES + 1):-1]:
        text = f"{turn.mode.value.upper()} {turn.role.value.upper()}: {turn.content}"
        if turn.guidance_asset_id:
            text += "\nA guidance image was attached to that turn; its pixels are not retransmitted here."
        turns.append(text)
    current = project.current_prompt or "None yet."
    # The selected result block already carries its exact prompt. Never remove
    # a merely similar prompt or claim an old result used the current prompt.
    if project.feedback_attempt_id:
        attempt = project.attempt(project.feedback_attempt_id)
        if project.current_prompt and attempt.prompt == project.current_prompt:
            current = "Identical to the exact prompt in SELECTED GENERATED RESULT below."
    guidance = bool(project.turns and project.turns[-1].guidance_asset_id)
    reference_status = "No source image. "
    if project.initial_reference_pending:
        reference_status = "REFERENCE IMAGE attached. "
    elif project.reference_asset_id:
        reference_status = (
            "Initial reference not attached. Use the current prompt and available exchanges; "
            "do not claim to inspect its pixels. "
        )
    return "\n\n".join((
        f"PROJECT: {project.name}",
        f"TARGET PROMPT LANGUAGE (authoritative):\n{language_instruction}",
        f"ORIGINAL INTENTION (historical starting point):\n{project.intention}",
        "IMAGE EVIDENCE:\n"
        + reference_status
        + ("TURN GUIDANCE IMAGE attached for this message only." if guidance else "No turn-specific guidance image."),
        f"CURRENT TARGET PROMPT:\n{current}",
        "RECENT EXCHANGES (full older prompt copies omitted; no conversation rewind):\n"
        + ("\n".join(turns) or "No earlier exchange."),
        f"SELECTED GENERATED RESULT AND EXACT SETTINGS:\n{selected}",
        f"PUBLISHED RECIPE CONTEXT:\n{memory}",
        f"RENDER RESOURCE ADVICE:\n{resources}",
        f"NEW USER MESSAGE (authoritative):\n{message}",
    ))
