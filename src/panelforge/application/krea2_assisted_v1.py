"""KREA Assisted V1: frozen system prompts and pre-ASTRA conversation layout.

New writing behavior belongs in V2. Attachment status follows the shared
application policy so the text always describes the images actually sent.
The renderer workflow and published Batch recipes are independently versioned.
"""

from panelforge.domain.krea2_assisted import Krea2AssistedProject

_CREATION_SYSTEM = """You are a collaborative art director and KREA2 text-to-image prompt writer.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone KREA2 prompt in the TARGET PROMPT LANGUAGE","recommendations":["optional concise setting or iteration advice"]}

The prompt is always required, even when questions remain: it must be usable immediately. Treat any REFERENCE IMAGE only as visual evidence to describe or reverse-engineer. It will NOT be sent to the renderer, so never write edit instructions such as keep, change, replace, preserve from the image, or references to "this image". Produce a self-contained text-to-image description instead.

Use the conversation, the current prompt and the user's newest message as one evolving design brief. When GENERATED RESULT is supplied, compare it with the requested goal using the exact render prompt and settings, identify only relevant visible discrepancies, then rewrite the complete target prompt. Do not append contradictions. Cover concrete subject, framing/composition, pose/action, materials, environment, lighting, palette and finish when relevant. Ask only questions that materially change the result. Do not invent a second workflow or recommend KREA Edit.

Explicit sexual content may be described only when every depicted person is unambiguously an adult and the user requests it. Never infer adulthood from an ambiguous image, introduce youth-related traits, or add an unrequested sexual act or participant. Never output Markdown or commentary outside the JSON."""

_RECIPE_SYSTEM = """You help turn a proven KREA2 text-to-image result into an immutable reusable Batch recipe.
Return raw JSON only with exactly these fields:
{"message":"concise recipe-design reply in French","questions":["up to three material questions"],"recipe":null}
or:
{"message":"concise recipe-design reply in French","questions":["up to three material questions"],"recipe":{"recipe_id":"lowercase_slug","display_name":"human name","description":"short purpose","identity":"visual family identity","invariants":["fixed rules"],"variables":["safe variation axes"],"risks":["failure modes"],"canonical_prompt":"complete standalone KREA2 prompt in the TARGET PROMPT LANGUAGE"}}

The selected result's exact checkpoint, ratio, megapixels and ordered LoRA stack are controlled by PanelForge and must not be repeated as invented technical settings. Separate what defines the family from what may vary across a Batch. Keep the selected proven prompt architecture as the canonical prompt, generalizing only the variable subject details needed by the requested family. Ask questions when identity, invariants or allowed variation axes remain ambiguous. You may still provide a draft while questions remain. Never publish anything and never output Markdown."""


VERSION = "1.0.0"
LABEL = "V1 · classique"
HISTORY_ENTRIES = 13
RECIPE_LIMIT = 20
MODEL_LIMIT = 40
LORA_LIMIT = 80
MAX_TOKENS = 131_072
CREATION_OPERATION = "krea2.assisted.creation_chat@0.3.0"
RECIPE_OPERATION = "krea2.assisted.recipe_chat@0.3.0"


def system_prompt(mode: str) -> str:
    return _CREATION_SYSTEM if mode == "creation" else _RECIPE_SYSTEM


def user_prompt(
    project: Krea2AssistedProject,
    message: str,
    *,
    selected: str,
    memory: str,
    resources: str,
    language_instruction: str,
) -> str:
    current_turn = project.turns[-1]
    conversation = "\n".join(
        f"{turn.mode.value.upper()} {turn.role.value.upper()}: {turn.content}"
        + (
            f"\nTURN GUIDANCE IMAGE USED: {turn.guidance_filename or 'guidance-image'}"
            if turn.guidance_asset_id is not None
            else ""
        )
        + (f"\nPROMPT: {turn.prompt}" if turn.prompt else "")
        for turn in project.turns[-(HISTORY_ENTRIES + 1):-1]
    ) or "No earlier exchange."
    reference_status = "No reference image."
    if project.initial_reference_pending:
        reference_status = "A descriptive reference image is attached."
    elif project.reference_asset_id:
        reference_status = (
            "Initial reference not attached. Use the current prompt and available exchanges; "
            "do not claim to inspect its pixels."
        )
    user = "\n\n".join((
        f"PROJECT: {project.name}",
        f"TARGET PROMPT LANGUAGE (authoritative):\n{language_instruction}",
        f"ORIGINAL INTENTION:\n{project.intention}",
        f"REFERENCE STATUS:\n{reference_status}",
        (
            "TURN GUIDANCE STATUS:\nA TURN GUIDANCE IMAGE is attached only for the NEW USER MESSAGE. "
            "Use it as visual evidence or inspiration requested by that message. It does not replace "
            "REFERENCE IMAGE or GENERATED RESULT, and it does not become persistent project identity "
            "unless the user explicitly requests that."
            if current_turn.guidance_asset_id is not None
            else "TURN GUIDANCE STATUS:\nNo turn-specific guidance image."
        ),
        f"CURRENT TARGET PROMPT:\n{project.current_prompt or 'None yet.'}",
        f"RECENT PROJECT CONVERSATION:\n{conversation}",
        f"SELECTED GENERATED RESULT AND EXACT SETTINGS:\n{selected}",
        f"PUBLISHED RECIPE MEMORY (validated global knowledge only):\n{memory}",
        f"AVAILABLE KREA2 RENDER RESOURCES (advice only; never invent missing files):\n{resources}",
        f"NEW USER MESSAGE (authoritative):\n{message}",
    ))
    return user
