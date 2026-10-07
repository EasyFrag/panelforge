"""Scene evidence, repeatable language preferences and balanced local choices.

This module reads descriptions, not pixels. The existing visual Plan handles
images whose saved descriptions supply no usable location or atmosphere.
"""
from collections import Counter
import hashlib
import json
import re
import unicodedata

from .localized_speech import STABLE_THANKS_LANGUAGES

LANGUAGE_POOLS = {
    "east_asia": ("Chinese", "Korean", "Japanese"),
    "western_europe": ("French", "English", "German"),
    "southern_europe": ("Italian", "Spanish", "Portuguese"),
    "iberia": ("Spanish", "Portuguese"),
    "europe": ("French", "English", "German", "Italian", "Spanish", "Portuguese"),
    "eastern_europe": ("Russian",),
    "arabic_desert": ("Arabic",),
    "unknown": STABLE_THANKS_LANGUAGES,
}
POOL_LABELS = {
    "east_asia": "Asie de l’Est", "western_europe": "Europe occidentale",
    "southern_europe": "Europe du Sud", "iberia": "Péninsule ibérique",
    "europe": "Europe", "eastern_europe": "Europe de l’Est",
    "arabic_desert": "Ambiance arabe / désert", "unknown": "Sans indice",
    "country": "Pays / lieu explicite", "manual": "Choix manuel",
    "visual": "Ambiance à préciser dans le Plan",
}
_COUNTRIES = {
    "French": r"france|francais\w*|french|paris|parisian|haussmann\w*",
    "English": r"united kingdom|great britain|royaume uni|grande bretagne|angleterre|england|english|british|britannique\w*|london|londres|united states|etats unis|usa|american|americain\w*|australia|australie|new zealand|nouvelle zelande",
    "German": r"germany|allemagne|german|allemand\w*|berlin|germanique\w*|germanic|autriche|austria|austrian",
    "Italian": r"italy|italie|italian|italien\w*|tuscany|tuscan|toscane|venice|venise|venetian|rome|florence",
    "Spanish": r"spain|espagne|spanish|espagnol\w*|andalusi\w*|andalou\w*|mexico|mexique|mexican|mexicain\w*|argentina|argentine|colombia|colombie|peru|perou|chile|chili",
    "Portuguese": r"portugal|portuguese|portugais\w*|lisbon|lisbonne|porto|brazil|brasil|bresil|brazilian|bresilien\w*",
    "Russian": r"russia|russie|russian|russe\w*|moscow|moscou|saint petersburg",
    "Chinese": r"china|chine|chinese|chinois\w*|beijing|pekin|shanghai|siheyuan",
    "Korean": r"korea|coree|korean|coreen\w*|seoul|hanok\w*",
    "Japanese": r"japan|japon|japanese|japonais\w*|tokyo|kyoto|torii|machiya",
    "Arabic": r"algeria|algerie|algerian|algerien\w*|morocco|maroc|moroccan|marocain\w*|tunisia|tunisie|tunisian|tunisien\w*|egypt|egypte|egyptian|egyptien\w*|saudi arabia|arabie saoudite|jordan|jordanie|iraq|irak|syria|syrie|united arab emirates|emirats arabes unis",
}
_GROUPS = (
    ("eastern_europe", r"eastern europe|east european|europe de l est|europe orientale|slavic|slave|slavique|architecture russe"),
    ("iberia", r"iberi\w*|azulejo\w*"),
    ("southern_europe", r"southern europe|south european|europe du sud|mediterrane\w*"),
    ("western_europe", r"western europe|west european|europe occidentale|europe de l ouest|colombage\w*|half timber\w*"),
    ("east_asia", r"asia\w*|asie|asiatique\w*|east asian|far east|extreme orient|malaysia\w*|malais\w*|singapore|singapour|pagoda\w*|pagode\w*"),
    ("arabic_desert", r"arab\w*|arabe\w*|maghreb\w*|middle east\w*|moyen orient|desert\w*|sahara\w*"),
    ("europe", r"europe\w*"),
)


def _normalized(text):
    text = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return re.sub(r"[-'’_]", " ", text)


def _matches(pattern, text):
    return re.search(r"\b(?:" + pattern + r")\b", text)


def classify_context(text):
    """Return an eligible pool from positive location evidence, never text language."""
    text = _normalized(text)
    language_words = r"french|francais|english|anglais|german|allemand|italian|italien|spanish|espagnol|portuguese|portugais|russian|russe|chinese|chinois|korean|coreen|japanese|japonais|arabic|arabe"
    # A writing-language annotation is not location evidence.
    text = re.sub(r"\b(?:" + language_words + r")\s+(?:title|text|prompt|language|dialogue)\b", "", text)
    text = re.sub(r"\b(?:written|redige|texte|titre|prompt|dialogue|text|title)\s+(?:in|en)\s+(?:" + language_words + r")\b", "", text)
    explicit = re.findall(r"(?m)^\s*(?:pays|country)\s*:\s*([^\n.;]+)", text)
    for evidence in (" ".join(explicit), text):
        if not evidence:
            continue
        found = tuple(language for language, pattern in _COUNTRIES.items() if _matches(pattern, evidence))
        if found:
            return "country", found, evidence[:180]
        if "canada" in evidence or "quebec" in evidence:
            return "country", ("French",) if "quebec" in evidence else ("French", "English"), evidence[:180]
        if _matches(r"switzerland|suisse", evidence):
            return "country", ("French", "German", "Italian"), evidence[:180]
        if _matches(r"belgium|belgique", evidence):
            return "country", ("French", "German"), evidence[:180]
    for group, pattern in _GROUPS:
        match = _matches(pattern, text)
        if match:
            return group, LANGUAGE_POOLS[group], match.group(0)
    return None


def scene_contexts(config):
    """Manual notes, then immutable image evidence; no inference from a title's language."""
    notes = config.get("little_men_context", "").strip()
    if notes:
        yield "Contexte saisi", notes
    for ref in config.get("references", ()):
        context = ref.get("scene_context") or {}
        if context.get("asset_id") != ref.get("asset_id"):
            continue
        for key, label in (("intention", "Intention image"), ("prompt", "Description image"), ("style", "Style image")):
            text = context.get(key, "")
            if isinstance(text, str) and text.strip():
                yield f"{label} ({context.get('origin', 'source')})", text.strip()


def selection_input(config):
    value = {"language": config.get("little_men_language", "auto"),
             "context": list(scene_contexts(config)),
             "images": [ref.get("asset_id") for ref in config.get("references", ())]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def preference_order(identity, recent=()):
    counts = Counter(language for language in recent if language in STABLE_THANKS_LANGUAGES)
    return sorted(STABLE_THANKS_LANGUAGES, key=lambda language: (
        counts[language], hashlib.sha256((identity + ":" + language).encode()).hexdigest()))


def make_selection(config, identity, recent=()):
    priority = preference_order(identity, recent)
    manual = config.get("little_men_language", "auto")
    group, candidates, evidence = "visual", tuple(priority), ""
    if manual != "auto":
        if manual not in STABLE_THANKS_LANGUAGES:
            raise ValueError("Choisissez une des 11 langues stables pour ce nouveau remerciement.")
        group, candidates, evidence = "manual", (manual,), "Langue parlée"
    else:
        matches = [(origin, result) for origin, text in scene_contexts(config)
                   if (result := classify_context(text))]
        # A precise location beats a broad atmosphere in another source field.
        match = next((entry for entry in matches if entry[1][0] == "country"),
                     matches[0] if matches else None)
        if match:
            origin, (group, candidates, evidence) = match
            evidence = origin + " : " + evidence
    ordered = [language for language in priority if language in candidates]
    chosen = ordered[0] if group != "visual" else None
    return dict(version=4, flood_first_action="plunger", drought_result="lush_growth", weather_direction="v1",
                input_hash=selection_input(config), priority=priority,
                candidates=ordered, group=group, reason=POOL_LABELS[group], evidence=evidence,
                requested_language=chosen, language=chosen)


def recent_languages(items, *, exclude=None, limit=50):
    """Count other prepared/reserved choices, including queued work, once per fiche."""
    values = []
    for item in sorted(items, key=lambda i: i.get("updated_at", ""), reverse=True):
        if item["id"] == exclude or (item["config"].get("preset_origin") or item["config"].get("preset")) != "little_men_experimental":
            continue
        selection = item.get("runtime", {}).get("thanks_selection") or {}
        language = selection.get("language")
        if not language:
            try:
                language = json.loads(item["steps"]["plan"]["output"].get("text", "{}")).get("spoken_languages", [None])[0]
            except (ValueError, TypeError, IndexError, AttributeError):
                language = None
        if language in STABLE_THANKS_LANGUAGES:
            values.append(language)
            if len(values) >= limit:
                break
    return values


def selection_instructions(selection):
    """Frozen order is reused by both calls; resolved output never rewrites the input."""
    if selection["requested_language"]:
        return ("Langue imposée pour le remerciement : " + selection["requested_language"] + ".\n"
                "Choix fixé pour cette fiche : " + POOL_LABELS[selection["group"]] + ".\n"
                "Indice : " + selection["evidence"])
    pools = "; ".join(key + " = " + ", ".join(values) for key, values in LANGUAGE_POOLS.items())
    return (
        "CHOIX DE LANGUE PAR L'IMAGE : identifier un pays évident, sinon l'ambiance architecturale "
        "ou paysagère. Ne pas déduire le pays de la langue du titre ou du prompt. "
        "Un pays évident impose sa langue si elle fait partie des 11 langues proposées. "
        "Sinon choisir le groupe approprié puis la PREMIÈRE langue admissible dans l'ordre ci-dessous. "
        "Asie de l'Est : chinois, coréen et japonais ; Europe de l'Est : russe, pas portugais. "
        "Portugal/Brésil : portugais. Désert sans pays précis : arabe. "
        "Europe très générique : groupe europe, étendu au russe si des indices évoquent aussi l'Est. "
        "Sans indice, prendre la première langue de l'ordre global, sans repli privilégié sur l'anglais.\n"
        "Groupes : " + pools + ".\n"
        "Ordre de préférence fixé, langues récemment moins utilisées en premier : "
        + ", ".join(selection["priority"]) + ".\n"
        "Dans continuity_invariants, indiquer le pays ou le groupe retenu et son indice concret "
        "(ou absence d'indice), ainsi que la langue choisie."
    )
