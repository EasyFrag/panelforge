"""Compile the known two-image journey roles without inventing or renumbering references."""
import json
import re

from . import minimax_edit_assistance as assistance
from .revised_documents import strip_markdown_fence
from panelforge.domain.minimax_edit import validate_prompt

VERSION = "1.0.0"
ROLES = (
    "Reference roles: <Picture 1> is the current state and the only image to edit. "
    "<Picture 2> is the supplied finished building: use it only for the geometry, proportions "
    "and materials of parts retained or explicitly requested by this edit. "
    "The requested transformation determines how much of the building remains. "
    "Do not copy the finished state, restore removed parts outside the requested edit, "
    "or restore the original positions of people and vehicles from <Picture 2>."
)
SYSTEM = (
    "This is an autonomous journey with TWO actual render references. "
    "The English prompt must use both <Picture 1> (current edit source) and <Picture 2> "
    "(finished-building reference), including for a simple edit. "
    "The application also appends their fixed roles to the rendering prompt. "
    "Do not confuse <Subject N> identities with <Picture N> references."
)


def supports(context):
    inputs = context.get("render_inputs", [])
    return (context.get("mode") == "edit" and not context.get("guide") and len(inputs) == 2
            and [(r.get("id"), r.get("tag")) for r in inputs]
            == [("source", "<Picture 1>"), ("journey-finished", "<Picture 2>")]
            and inputs[0].get("asset_id") == context.get("source_asset_id")
            and bool(inputs[0].get("asset_id")) and bool(inputs[1].get("asset_id"))
            and inputs[0]["asset_id"] != inputs[1]["asset_id"])


def decode(raw, context):
    if not supports(context):
        raise ValueError("Les références du parcours ne correspondent plus au contrat du prompt.")
    value = json.loads(strip_markdown_fence(raw))
    if not isinstance(value, dict) or not isinstance(value.get("message"), str):
        raise ValueError("La réponse ne contient pas d’explication. Le brouillon reste consultable.")
    prompt = value.get("prompt")
    inputs = context["render_inputs"]
    # Accept only the exact omission observed: a valid source-only instruction for a known pair.
    # Invented tags, a missing source, Qwen tags, malformed/oversized prompts still fail.
    source_only = isinstance(prompt, str) and set(re.findall(r"<Picture (\d+)>", prompt)) == {"1"}
    validate_prompt(prompt, inputs[:1] if source_only else inputs)
    value["prompt"] = prompt.strip() + "\n\n" + ROLES
    return assistance.decode(json.dumps(value, ensure_ascii=False), inputs)
