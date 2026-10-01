"""Versioned scene direction; source metadata remains untouched on the fiche."""
import re
import unicodedata

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


SOLUTION_PLAN_POLICY_V4 = (
    "HELP MECHANISM: Follow the author's stated problem; otherwise infer the need from the image. "
    "In continuity_invariants, connect need, mechanism and lasting benefit in one sentence. "
    "Respect specified tools; otherwise keep object choice free. No gesture quota. "
    "Material styling must not immobilize water or fire."
)
NEED_DIRECTIONS = {
    'drought': 'La main irrigue le sol desséché. Partout où l’eau touche la terre, une végétation luxuriante pousse aussitôt comme par magie, suit la progression de l’arrosage et reste visible après le retrait de la main.',
    'wave': 'Intercepter ou détourner la vague avant les habitants, avec une protection qui reste efficace.',
    'flood': 'Premier geste d’aide : utiliser une ventouse de débouchage pour évacuer l’eau et abaisser durablement son niveau ; gestes suivants libres si nécessaires.',
    'fire': 'Les flammes vacillent et la fumée monte, puis le feu s’éteint sous l’effet de l’aide.',
}
# Only scene descriptions are evidence; labels, filenames and style boilerplate are not.
_NEED_PATTERNS = {
    "drought": r"secheresse|drought|arid(?:e|ity)?|parched|manque d[' ]eau|penurie d[' ]eau|lack of water|water shortage",
    "wave": r"tsunami|raz de maree|tidal wave|(?:giant|massive|towering|incoming) wave|vague (?:geante|de submersion)",
    "flood": r"in+ondations?|flood(?:s|ed|ing)?",
    "fire": r"incendies?|feu|flammes?|fire|wildfire|flames?|blaze|burning",
    "tornado": r"tornades?|tornado(?:es)?|twister|cyclone|ouragan|hurricane",
    "repair": r"reparations?|reparer|repairs?|broken|brise(?:e|s|es)?|casse(?:e|s|es)?",
}
_NEGATED_NEED = re.compile(r"\b(?:sans|aucune?|pas|no|not|without)\s*(?:d[' ]|de\s+|any\s+|a\s+|an\s+)?$")


def _need_in_text(text):
    text = "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c)).replace("’", "'").replace("-", " ")
    found, denied = set(), False
    for kind, pattern in _NEED_PATTERNS.items():
        for match in re.finditer(r"\b(?:" + pattern + r")\b", text):
            if _NEGATED_NEED.search(text[max(0, match.start() - 40):match.start()]):
                denied = True
            else:
                found.add(kind)
    # A flood caused by a wave is governed by the incoming threat.
    if "wave" in found:
        found.discard("flood")
    if len(found) == 1:
        return next(iter(found))
    return "ambiguous" if found or denied else None


def scene_need(config):
    """Use author intent first, then the exact image's intent and full description."""
    contexts = [config.get("intention", ""), config.get("little_men_context", "")]
    refs = [ref.get("scene_context") or {} for ref in config.get("references", ())
            if (ref.get("scene_context") or {}).get("asset_id") == ref.get("asset_id")]
    for key in ("intention", "prompt"):
        contexts.extend(context.get(key, "") for context in refs)
    for text in contexts:
        if isinstance(text, str) and (kind := _need_in_text(text)) is not None:
            return kind
    return "unknown"


def preparation_text_v4(config, source, selection):
    # This goal is deterministic and stays identical from Plan to Writer.
    need = scene_need(config)
    goal = NEED_DIRECTIONS.get(need)
    # Older selections must reproduce their locked Plan/Writer input exactly.
    if need == "flood" and selection.get("flood_first_action") != "plunger":
        goal = "Évacuer l’eau hors de la zone protégée et montrer une baisse durable du niveau."
    if need == "drought" and selection.get("drought_result") != "lush_growth":
        goal = "Apporter de l’eau pour soulager la sécheresse et rendre son bénéfice visible."
    if goal:
        source += "\n\n" + goal
    return preparation_text_v3(config, source, selection)


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
