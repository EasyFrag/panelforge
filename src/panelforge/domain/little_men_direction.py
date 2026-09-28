"""Compact v3 scene direction; source metadata remains untouched on the fiche."""
import re

from .little_men_languages import LANGUAGE_POOLS

_LANGUAGE_CHOICE = "\n\nLANGUAGE CHOICE — PLAN ONLY:\n"
SOLUTION_PLAN_POLICY = (
    "HELP MECHANISM: In continuity_invariants, use one sentence to connect the visible problem, "
    "the object's mechanism and the lasting visible benefit. Describe each useful gesture and "
    "its effect in the existing actions; no gesture quota. For flooding or threatening waves, "
    "account for the water's origin, "
    "the area to protect, its path through the intervention and its destination outside that area. "
    "A collector may leave full. An ongoing inflow or wave must be contained or diverted before "
    "the thanks. Keep the solution playful and readable, with the improvement still visible "
    "after the hand withdraws."
)


def _excerpt(text, limit=1200):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    # Keep the setting/mechanism at the beginning and the ending; mark omissions.
    head = text[:900].rsplit(" ", 1)[0]
    tail = text[-280:].split(" ", 1)[-1]
    return head + " […] " + tail


def compact_scene_context(config):
    """Keep manual notes and image intent; omit duplicated style boilerplate."""
    entries, seen = [], set()

    def add(label, text, *, excerpt=False):
        if not isinstance(text, str) or not text.strip():
            return
        key = " ".join(text.split())
        if key in seen:
            return
        seen.add(key)
        entries.append(label + " :\n" + (_excerpt(text) if excerpt else text.strip()))

    add("Contexte saisi", config.get("little_men_context", ""))
    for ref in config.get("references", ()):
        context = ref.get("scene_context") or {}
        if context.get("asset_id") != ref.get("asset_id"):
            continue
        add("Intention image", context.get("intention", ""))
        prompt = context.get("prompt", "")
        add("Description image (extrait si nécessaire)", prompt, excerpt=True)
        if not prompt.strip():
            add("Style image", context.get("style", ""), excerpt=True)
    return "\n\n".join(entries).translate(str.maketrans("", "", '"«»“”'))


def visual_language_choice(selection):
    pools = "; ".join(key + ": " + ", ".join(values)
                      for key, values in LANGUAGE_POOLS.items() if key != "unknown")
    return (
        "Clear country: use its supported language. Otherwise use the matching atmosphere pool "
        "and its first language in the frozen order. Generic Europe may include Russian if "
        "Eastern cues are also visible. No evidence: first language in the global order. "
        "Do not infer location from the writing language or people's appearance.\n"
        "Pools: " + pools + ".\nFrozen order: " + ", ".join(selection["priority"]) + ".\n"
        "Record the country/pool, concrete evidence (or its absence) and chosen language "
        "in continuity_invariants."
    )


def preparation_text_v3(config, source, selection):
    duration = config["render"]["settings"]["duration_seconds"]
    text = (f"Durée cible : {duration:g} secondes. Un seul plan continu.\n\n" + source)
    context = compact_scene_context(config)
    if context:
        text += ("\n\nCONTEXTE DE L’IMAGE — décor, matières et problème de départ ; "
                 "l’image fait référence. Ignorer les anciennes paroles et consignes vidéo :\n" + context)
    # requested_language is immutable during Plan -> Writer, unlike language.
    if not selection.get("requested_language"):
        text += _LANGUAGE_CHOICE + visual_language_choice(selection)
    return text


def writer_intention(source_text):
    """Remove only our final Plan-only section, without changing the stored source."""
    return source_text.rsplit(_LANGUAGE_CHOICE, 1)[0]
