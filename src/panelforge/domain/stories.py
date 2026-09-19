"""Narrative documents. Independent of video grammars and rendering engines."""
from copy import deepcopy
import json
import re
import unicodedata


# Keep the historical ID stable for existing projects and recipe archives.
RECIPE_ID = "story.brainrot"
RECIPE_VERSION = "1.0.0"
SENSUAL_RECIPE_ID = "story.sensual-light"
SENSUAL_RECIPE_VERSION = "1.0.0"
EXPLICIT_RECIPE_ID = "story.explicit-hard"
EXPLICIT_RECIPE_VERSION = "1.0.0"
SILENT_CATS_RECIPE_ID = "story.silent-cats"
SILENT_CATS_RECIPE_VERSION = "1.0.0"
MAX_STORY_REPLY_CHARS = 144_000
DIALOGUE_DELIVERIES = frozenset({"spoken", "voice_over", "off_screen", "thought", "mediated"})
DEFAULT_DIALOGUE_LANGUAGE = "French"
DIALOGUE_LANGUAGES = {
    "French": "Français",
    "English": "English",
    "Korean": "한국어 · Coréen",
    "Japanese": "日本語 · Japonais",
    "Russian": "Русский · Russe",
}
VISUAL_TRANSITION_FIELDS = ("before", "trigger", "visible_change", "after")
CONTINUITY_FIELDS = (
    "series_summary", "latest_ending", "established_facts", "character_states",
    "unresolved_threads", "available_elements",
)
CONTINUATION_PLAN_FIELDS = ("carry_over", "obstacle", "payoff", "introduced_elements")
DEFAULT_NARRATIVE_FORMAT = "short"
NARRATIVE_FORMATS = frozenset({"short", "long"})
SERIES_EPISODE_COUNT = 4
FRUIT_AUDIO_MAX_LINES_PER_SCENE = 4

# Fruit stories use coined stage names, not a human first name followed by
# the species (for example, "Nour Myrtille"). Three or four stable letters
# support playful suffixes while keeping the rule deterministic.
_FRUIT_NAME_ROOTS = (
    ("fruit de la passion", ("pass",)),
    ("pamplemousse", ("pamplem",)),
    ("carambole", ("caramb",)),
    ("canneberge", ("canneb",)),
    ("clementine", ("clement",)),
    ("framboise", ("framb",)),
    ("groseille", ("groseill",)),
    ("mangoustan", ("mangoust",)),
    ("mirabelle", ("mirab",)),
    ("myrtille", ("myrt",)),
    ("mandarine", ("mandar",)),
    ("nectarine", ("nectar",)),
    ("pasteque", ("pasteq",)),
    ("abricot", ("abric",)),
    ("ananas", ("anan",)),
    ("banane", ("banan",)),
    ("cerise", ("ceris",)),
    ("citron", ("citr",)),
    ("grenade", ("grenad",)),
    ("goyave", ("goyav",)),
    ("litchi", ("litch",)),
    ("mangue", ("mang",)),
    ("orange", ("orang",)),
    ("papaye", ("papay",)),
    ("ramboutan", ("rambout",)),
    ("raisin", ("rais",)),
    ("avocat", ("avoc",)),
    ("cassis", ("cass",)),
    ("durian", ("duri",)),
    ("fraise", ("frais", "fraz")),
    ("figue", ("fig",)),
    ("melon", ("melon",)),
    ("mure", ("mur",)),
    ("peche", ("pech",)),
    ("poire", ("poir",)),
    ("pomme", ("pom",)),
    ("prune", ("prun",)),
    ("pitaya", ("pitay",)),
    ("physalis", ("phys",)),
    ("kumquat", ("kumq",)),
    ("coing", ("coin",)),
    ("datte", ("datt",)),
    ("kaki", ("kaki",)),
    ("kiwi", ("kiwi",)),
    ("coco", ("coco",)),
)

_STORY_RECIPES = {
    (RECIPE_ID, RECIPE_VERSION): {
        "id": RECIPE_ID, "version": RECIPE_VERSION, "label": "Mélodrame fruits",
        "description": "Fruits anthropomorphes aux noms fruités, mélodrame compréhensible à l’écoute.",
        "concept_fields": (("title", "Titre"), ("hook", "Accroche"),
            ("protagonist", "Personnage principal"), ("antagonist", "Antagoniste"),
            ("escalation", "Escalade"), ("reveal", "Révélation"), ("ending", "Fin")),
        "scene_fields": (),
        "adult_required": False,
    },
    (SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION): {
        "id": SENSUAL_RECIPE_ID, "version": SENSUAL_RECIPE_VERSION, "label": "Sensuel light",
        "description": "Désir, tension et proximité entre personnages clairement adultes, sans description sexuelle graphique.",
        "concept_fields": (("title", "Titre"), ("hook", "Accroche"),
            ("characters_and_dynamic", "Personnages et dynamique"), ("desire", "Désir"),
            ("obstacle", "Obstacle"), ("sensual_escalation", "Montée sensuelle"),
            ("turning_point", "Bascule"), ("ending", "Fin")),
        "scene_fields": (("relationship_state", "Dynamique relationnelle"),
                         ("appearance_state", "Tenues et continuité visuelle")),
        "adult_required": True,
    },
    (EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION): {
        "id": EXPLICIT_RECIPE_ID, "version": EXPLICIT_RECIPE_VERSION, "label": "Cru ++",
        "description": "Scènes pornographiques explicites : actes, anatomie, contacts, mouvements et continuité physique décrits sans euphémisme.",
        "concept_fields": (("title", "Titre"), ("hook", "Accroche"),
            ("participants_and_dynamic", "Participants et dynamique"),
            ("explicit_premise", "Situation sexuelle"),
            ("acts_and_progression", "Actes et progression"),
            ("physical_escalation", "Escalade physique"),
            ("turning_point", "Bascule"), ("ending", "Fin")),
        "scene_fields": (("relationship_state", "Dynamique entre participants"),
                         ("appearance_state", "Nudité, tenues et accessoires"),
                         ("sexual_state", "Position et contacts sexuels")),
        "adult_required": True,
    },
    (SILENT_CATS_RECIPE_ID, SILENT_CATS_RECIPE_VERSION): {
        "id": SILENT_CATS_RECIPE_ID, "version": SILENT_CATS_RECIPE_VERSION,
        "label": "Chats de couple · muet",
        "description": "Chats anthropomorphes photoréalistes, comédie de couple tendre et entièrement non verbale.",
        "concept_fields": (("title", "Titre"), ("hook", "Accroche"),
            ("couple_and_dynamic", "Le couple et sa dynamique"),
            ("domestic_setup", "Situation quotidienne"),
            ("visual_gag", "Gag visuel"),
            ("comic_escalation", "Escalade comique"),
            ("tender_turn", "Bascule tendre"), ("ending", "Fin")),
        "scene_fields": (("relationship_state", "Dynamique relationnelle"),
                         ("appearance_state", "Tenues, pelage et accessoires")),
        "adult_required": False,
        "dialogue_policy": "forbidden",
    },
}
CONCEPT_FIELDS = tuple(field for field, _ in _STORY_RECIPES[(RECIPE_ID, RECIPE_VERSION)]["concept_fields"])


def dialogue_language_selection(value=DEFAULT_DIALOGUE_LANGUAGE):
    if not isinstance(value, str) or value not in DIALOGUE_LANGUAGES:
        raise ValueError("Langue parlée inconnue.")
    return value


def dialogue_language_label(value=DEFAULT_DIALOGUE_LANGUAGE):
    return DIALOGUE_LANGUAGES[dialogue_language_selection(value)]


def narrative_format_selection(value=DEFAULT_NARRATIVE_FORMAT):
    if not isinstance(value, str) or value not in NARRATIVE_FORMATS:
        raise ValueError("Format narratif inconnu.")
    return value


def story_recipe_spec(recipe_id=RECIPE_ID, version=RECIPE_VERSION):
    try:
        spec = _STORY_RECIPES[(recipe_id, version)]
    except KeyError as error:
        raise ValueError("Famille d’histoire ou version inconnue.") from error
    return {
        **{key: value for key, value in spec.items() if key not in {"concept_fields", "scene_fields"}},
        "concept_fields": [{"id": key, "label": label} for key, label in spec["concept_fields"]],
        "scene_fields": [{"id": key, "label": label} for key, label in spec["scene_fields"]],
    }


def story_recipe_specs():
    return [story_recipe_spec(*key) for key in _STORY_RECIPES]


def story_recipe_selection(value=None):
    if value is None:
        recipe_id, version = RECIPE_ID, RECIPE_VERSION
    elif isinstance(value, str):
        recipe_id, separator, version = value.partition("@")
        if not separator:
            raise ValueError("La famille d’histoire doit inclure sa version.")
    elif isinstance(value, dict) and set(value) in ({"id", "version"}, {"recipe_id", "version"}):
        recipe_id, version = value.get("id", value.get("recipe_id")), value["version"]
    else:
        raise ValueError("Référence de famille d’histoire invalide.")
    story_recipe_spec(recipe_id, version)
    return {"id": recipe_id, "version": version}


def _recipe_fields(recipe_id, version=RECIPE_VERSION):
    try:
        return tuple(field for field, _ in _STORY_RECIPES[(recipe_id, version)]["concept_fields"])
    except KeyError as error:
        raise ValueError("Famille d’histoire ou version inconnue.") from error


def _fold_fruit_words(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char)).casefold()
    return " ".join(re.sub(r"[^a-z]+", " ", ascii_value).split())


def _fruit_species(value):
    description = _fold_fruit_words(value)
    candidates = []
    for species, roots in _FRUIT_NAME_ROOTS:
        token = re.escape(species)
        matches = [
            re.search(rf"\bespece\s+(?:de\s+)?{token}\b", description),
            re.search(rf"\b{token}\s+anthropomorph[a-z]*\b", description),
        ]
        for priority, match in enumerate(matches):
            if match:
                candidates.append((priority, match.start(), -len(species), species, roots))
    if not candidates:
        return None
    _, _, _, species, roots = min(candidates)
    return species, roots


def _validate_fruit_character_names(characters):
    for character in characters:
        name = character.get("name", "")
        species = _fruit_species(character.get("description", ""))
        if species is None:
            continue
        species_name, roots = species
        folded_name = _fold_fruit_words(name)
        if (not name.isalpha() or " " in folded_name or folded_name == species_name
                or not any(folded_name.startswith(root) and len(folded_name) >= len(root) + 2
                           for root in roots)):
            examples = "Figos, Figette, Pomitto, Pomitta, Mangotino, Manguette, Ananito ou Ananette"
            raise ValueError(
                f"Le nom « {name} » doit être un seul nom inventé dérivé de l’espèce {species_name}, "
                f"sans prénom humain ni nom de famille. Exemples : {examples}."
            )


def validate_fruit_story_contract(document):
    """Validate generated Fruit identities and their listen-only scene budget.

    StoryService deliberately skips this collection contract for faithful
    scripts so a pasted human script is never silently rewritten.
    """
    if not isinstance(document, dict):
        return document
    outline = document.get("series_outline")
    if isinstance(outline, dict):
        _validate_fruit_character_names(outline.get("characters") or [])
    scenario = document.get("scenario")
    if isinstance(scenario, dict):
        _validate_fruit_character_names(scenario.get("characters") or [])
        for index, scene in enumerate(scenario.get("scenes") or [], 1):
            count = len(scene.get("dialogue") or [])
            if not 1 <= count <= FRUIT_AUDIO_MAX_LINES_PER_SCENE:
                raise ValueError(
                    f"La scène {index} d’une histoire Fruit doit contenir entre une et "
                    f"{FRUIT_AUDIO_MAX_LINES_PER_SCENE} répliques ou monologues brefs afin de rester "
                    "compréhensible à l’écoute."
                )
    return document


def decode_story_json(text):
    """Accept trailing container commas only; never edit quoted story content."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        result = []
        quoted = escaped = False
        whitespace = " \t\r\n"
        for index, char in enumerate(text):
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == ",":
                following = index + 1
                while following < len(text) and text[following] in whitespace:
                    following += 1
                previous = next((c for c in reversed(result) if c not in whitespace), "")
                if following < len(text) and text[following] in "]}" and previous and previous not in "[{,:":
                    continue
            result.append(char)
        return json.loads("".join(result))


def _text(value, name, limit=6000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Le champ {name} doit contenir du texte (maximum {limit} caractères).")
    return value.strip()


def _items(value, name, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} : entre {minimum} et {maximum} éléments attendus.")
    return value


def _visual_transition(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != set(VISUAL_TRANSITION_FIELDS):
        raise ValueError(
            "visual_transition doit contenir exactement before, trigger, visible_change et after."
        )
    return {field: _text(value.get(field), f"visual_transition.{field}", 1500)
            for field in VISUAL_TRANSITION_FIELDS}


def validate_story_continuity(value):
    """Compact cumulative memory shared by successive episodes."""
    if not isinstance(value, dict) or set(value) != set(CONTINUITY_FIELDS):
        raise ValueError(
            "La mémoire de saga doit contenir exactement series_summary, latest_ending, "
            "established_facts, character_states, unresolved_threads et available_elements."
        )
    result = {
        "series_summary": _text(value.get("series_summary"), "series_summary", 3000),
        "latest_ending": _text(value.get("latest_ending"), "latest_ending", 1500),
    }
    for field, maximum in (("established_facts", 16), ("character_states", 12),
                           ("unresolved_threads", 10), ("available_elements", 12)):
        result[field] = [_text(item, field, 500) for item in _items(value.get(field), field, 0, maximum)]
    return result


def _continuation_plan(value):
    if not isinstance(value, dict) or set(value) != set(CONTINUATION_PLAN_FIELDS):
        raise ValueError(
            "continuation_plan doit contenir exactement carry_over, obstacle, payoff et introduced_elements."
        )
    return {
        "carry_over": _text(value.get("carry_over"), "continuation_plan.carry_over", 2000),
        "obstacle": _text(value.get("obstacle"), "continuation_plan.obstacle", 2000),
        "payoff": _text(value.get("payoff"), "continuation_plan.payoff", 2000),
        "introduced_elements": [
            _text(item, "continuation_plan.introduced_elements", 1000)
            for item in _items(value.get("introduced_elements"), "introduced_elements", 0, 4)
        ],
    }


def validate_series_outline(value, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION):
    """Validate the stable four-episode map used only by long stories."""
    if not isinstance(value, dict) or set(value) != {
            "title", "premise", "overall_arc", "ending", "characters", "episodes"}:
        raise ValueError(
            "L’arc long doit contenir exactement title, premise, overall_arc, ending, characters et episodes."
        )
    recipe_spec = _STORY_RECIPES.get((recipe_id, recipe_version))
    if recipe_spec is None:
        raise ValueError("Famille d’histoire ou version inconnue.")
    adult_required = recipe_spec.get("adult_required", False)
    result = {key: _text(value.get(key), key, 6000)
              for key in ("title", "premise", "overall_arc", "ending")}
    result["characters"] = []
    for item in _items(value.get("characters"), "Personnages de la série", 1, 12):
        if not isinstance(item, dict):
            raise ValueError("Fiche de personnage de série illisible.")
        character = {key: _text(item.get(key), key, 3000 if key == "description" else 120)
                     for key in ("id", "name", "description")}
        if "adult" in item or adult_required:
            if item.get("adult") is not True:
                raise ValueError("Chaque personnage de cette famille doit être explicitement identifié comme adulte.")
            character["adult"] = True
        result["characters"].append(character)
    character_ids = [item["id"] for item in result["characters"]]
    if len(set(character_ids)) != len(character_ids):
        raise ValueError("Identifiants de personnages de série en double.")
    result["episodes"] = []
    for index, item in enumerate(_items(
            value.get("episodes"), "Épisodes de l’arc", SERIES_EPISODE_COUNT, SERIES_EPISODE_COUNT), 1):
        if not isinstance(item, dict) or set(item) != {
                "id", "title", "promise", "opening_state", "conflict", "beats",
                "local_payoff", "ending_state", "carry_forward"}:
            raise ValueError(
                "Chaque épisode doit contenir exactement id, title, promise, opening_state, conflict, beats, "
                "local_payoff, ending_state et carry_forward."
            )
        if item.get("id") != f"episode-{index}":
            raise ValueError("Les épisodes doivent être identifiés de episode-1 à episode-4, dans cet ordre.")
        episode = {key: _text(item.get(key), key, 3000) for key in (
            "id", "title", "promise", "opening_state", "conflict",
            "local_payoff", "ending_state", "carry_forward",
        )}
        episode["beats"] = [_text(beat, "beat", 1500)
                            for beat in _items(item.get("beats"), "Étapes causales", 2, 6)]
        result["episodes"].append(episode)
    return result


def validate_concepts(value, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION, expected_count=3,
                      *, continuation=False):
    if type(expected_count) is not int or not 1 <= expected_count <= 3:
        raise ValueError("Le nombre de propositions doit être compris entre 1 et 3.")
    fields = _recipe_fields(recipe_id, recipe_version)
    concepts = []
    for index, item in enumerate(_items(value, "Propositions", expected_count, expected_count), 1):
        if not isinstance(item, dict):
            raise ValueError("Proposition illisible.")
        identity = item.get("id", f"concept-{index}")
        if identity != f"concept-{index}":
            raise ValueError("Identifiant de proposition inconnu.")
        concept = dict(id=identity, **{key: _text(item.get(key), key, 2000) for key in fields})
        if continuation:
            concept["continuation_plan"] = _continuation_plan(item.get("continuation_plan"))
        concepts.append(concept)
    if len({concept["id"] for concept in concepts}) != expected_count:
        raise ValueError("Identifiants de proposition en double.")
    if len({concept["title"].casefold() for concept in concepts}) != expected_count:
        raise ValueError("Les propositions doivent avoir des titres distincts.")
    return concepts


_SCRIPT_HEADING_PREFIXES = (
    "ACTE", "CHAPITRE", "EXT.", "EXT ", "FIN", "FORMAT", "INT.", "INT ",
    "LIEU", "PERSONNAGES", "SCENE", "SCÈNE", "SEQUENCE", "SÉQUENCE", "TITRE",
)


def _fold_dialogue_marker(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", "".join(
        char for char in normalized.upper() if not unicodedata.combining(char))).split())


def _dialogue_delivery(note):
    marker = _fold_dialogue_marker(note)
    if not marker:
        return "spoken"
    if marker in {"VO", "V O"} or any(value in marker for value in ("VOIX OFF", "VOICE OVER", "NARRATION")):
        return "voice_over"
    if any(value in marker for value in ("PENSEE", "VOIX INTERIEURE", "MONOLOGUE INTERIEUR")):
        return "thought"
    if marker in {"OFF", "OS", "O S", "HC", "H C"} or any(value in marker for value in (
            "HORS CHAMP", "OFF SCREEN", "DERRIERE", "DEPUIS LA PIECE", "DE LOIN")):
        return "off_screen"
    if any(value in marker for value in ("TELEPHONE", "INTERPHONE", "HAUT PARLEUR", "RADIO", "MESSAGE VOCAL")):
        return "mediated"
    return "spoken"


def _script_speaker_heading(value):
    heading = value.strip().rstrip("\\").strip()
    voice_first = re.fullmatch(
        r"(?:VOIX\s+OFF|VOICE\s*OVER|V\.?\s*O\.?|NARRATION)\s+(?:DE|:)\s+(.+)", heading, re.IGNORECASE)
    if voice_first:
        return voice_first.group(1).strip(), "VOIX OFF"
    parenthetical = re.fullmatch(r"(.+?)\s*(?:\(([^()]*)\)|\[([^\[\]]*)\])\s*:?", heading)
    if parenthetical:
        return parenthetical.group(1).strip(), (parenthetical.group(2) or parenthetical.group(3)).strip()
    separated = re.fullmatch(r"(.+?)\s*[—–-]\s*(.+)", heading)
    if separated:
        return separated.group(1).strip(), separated.group(2).strip()
    colon = re.fullmatch(r"(.+?)\s*:\s*(.+)", heading)
    if colon and len(colon.group(2)) <= 40 and colon.group(2) == colon.group(2).upper():
        return colon.group(1).strip(), colon.group(2).strip()
    return heading.rstrip(":").strip(), ""


def extract_script_dialogue_cues(script):
    """Extract spoken text and delivery metadata from conventional screenplay blocks."""
    if not isinstance(script, str):
        return []
    lines = script.splitlines()
    dialogues = []
    index = 0
    while index < len(lines):
        raw_heading = lines[index].strip()
        base, note = _script_speaker_heading(raw_heading)
        upper = base.upper()
        is_speaker = (
            bool(base) and not raw_heading.startswith(("-", "*", "•"))
            and len(base) <= 60 and ":" not in base
            and any(char.isalpha() for char in base) and base == upper
            and not upper.startswith(_SCRIPT_HEADING_PREFIXES)
            and upper not in {"FADE IN", "FADE OUT", "CUT", "COUPURE", "NOIR"}
        )
        if not is_speaker:
            index += 1
            continue
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        block = []
        while cursor < len(lines) and lines[cursor].strip():
            text = lines[cursor].strip().rstrip("\\").strip()
            if text and not (text.startswith("(") and text.endswith(")")):
                block.append(text)
            cursor += 1
        if block:
            record = dict(dialogue_id=f"dialogue-{len(dialogues) + 1}", speaker=base,
                          text=" ".join(block), delivery=_dialogue_delivery(note))
            if note:
                record["delivery_note"] = note
            dialogues.append(record)
            index = cursor
        else:
            index += 1
    return dialogues


def extract_script_dialogues(script):
    """Compatibility view returning only the exact spoken text."""
    return [dialogue["text"] for dialogue in extract_script_dialogue_cues(script)]


def _delivery_prefixes(cue):
    values = [cue.get("delivery_note", "")]
    values.extend({
        "voice_over": ("voix off", "v.o.", "vo", "narration", "en voix off"),
        "off_screen": ("hors champ", "off screen", "off"),
        "thought": ("pensée", "pensée intérieure", "voix intérieure"),
        "mediated": ("au téléphone", "téléphone", "interphone", "radio", "haut-parleur"),
    }.get(cue["delivery"], ()))
    return tuple(value for value in dict.fromkeys(values) if value)


def _without_delivery_prefix(text, cue):
    for marker in _delivery_prefixes(cue):
        escaped = re.escape(marker)
        match = re.match(rf"^\s*(?:\(\s*{escaped}\s*\)|\[\s*{escaped}\s*\]|{escaped}\s*[:—–-])\s*(.+)$",
                         text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()


def validate_script_dialogue_coverage(script, scenario):
    """Canonicalize delivery cues while rejecting spoken-word or speaker changes."""
    expected = extract_script_dialogue_cues(script)
    if not expected:
        return scenario
    actual = [line for scene in scenario["scenes"] for line in scene["dialogue"]]
    if len(actual) != len(expected):
        raise ValueError(
            "Le scénario n’a pas conservé l’intégralité des dialogues du script, mot pour mot et dans le même ordre. "
            "Le brouillon est conservé pour diagnostic."
        )
    characters = {character["id"]: character for character in scenario["characters"]}
    compact = lambda value: " ".join(value.split())
    for cue, line in zip(expected, actual):
        speaker = characters[line["speaker_id"]]["name"]
        if _fold_dialogue_marker(speaker) != _fold_dialogue_marker(cue["speaker"]):
            raise ValueError(
                "Le scénario a changé le locuteur d’une réplique du script. Le brouillon est conservé pour diagnostic."
            )
        if line.get("dialogue_id") not in (None, cue["dialogue_id"]):
            raise ValueError(
                "Le scénario a changé l’identifiant ou l’ordre d’une réplique du script. Le brouillon est conservé pour diagnostic."
            )
        spoken = _without_delivery_prefix(line["text"], cue)
        if compact(spoken) != compact(cue["text"]):
            raise ValueError(
                "Le scénario n’a pas conservé l’intégralité des dialogues du script, mot pour mot et dans le même ordre. "
                "Le brouillon est conservé pour diagnostic."
            )
        if "delivery" in line and line["delivery"] != cue["delivery"]:
            raise ValueError(
                "Le scénario a changé le mode de restitution d’une réplique du script. Le brouillon est conservé pour diagnostic."
            )
        line.update(dialogue_id=cue["dialogue_id"], text=cue["text"], delivery=cue["delivery"])
        if cue.get("delivery_note"):
            line["delivery_note"] = cue["delivery_note"]
        else:
            line.pop("delivery_note", None)
    return scenario


def validate_scenario(value, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION):
    if not isinstance(value, dict):
        raise ValueError("Scénario illisible.")
    story_recipe_spec(recipe_id, recipe_version)
    recipe_spec = _STORY_RECIPES[(recipe_id, recipe_version)]
    adult_required = recipe_spec.get("adult_required", False)
    result = {key: _text(value.get(key), key) for key in ("title", "logline")}
    for collection, maximum in (("characters", 12), ("locations", 8)):
        result[collection] = []
        for item in _items(value.get(collection), collection, 1, maximum):
            if not isinstance(item, dict):
                raise ValueError(f"Fiche {collection} illisible.")
            record = {key: _text(item.get(key), key, 3000 if key == "description" else 120)
                      for key in ("id", "name", "description")}
            if collection == "characters" and ("adult" in item or adult_required):
                if item.get("adult") is not True:
                    raise ValueError("Chaque personnage de cette famille doit être explicitement identifié comme adulte.")
                record["adult"] = True
            result[collection].append(record)
        ids = [record["id"] for record in result[collection]]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Identifiants {collection} en double.")
    characters = {character["id"] for character in result["characters"]}
    locations = {location["id"] for location in result["locations"]}
    scene_extensions = tuple(field for field, _ in recipe_spec["scene_fields"])
    result["scenes"] = []
    for item in _items(value.get("scenes"), "Micro-scènes", 1, 18):
        if not isinstance(item, dict):
            raise ValueError("Micro-scène illisible.")
        scene = {key: _text(item.get(key), key) for key in
                 ("title", "location_id", "action", "opening_state", "ending_state")}
        for field in scene_extensions:
            scene[field] = _text(item.get(field), field, 3000)
        transition = _visual_transition(item.get("visual_transition"))
        if transition is not None:
            scene["visual_transition"] = transition
        ids = _items(item.get("character_ids"), "Personnages de la scène", 1, 12)
        if any(not isinstance(character, str) or character not in characters for character in ids) or len(set(ids)) != len(ids):
            raise ValueError("Une scène utilise un personnage inconnu ou en double.")
        if scene["location_id"] not in locations:
            raise ValueError("Une scène utilise un décor inconnu.")
        scene["character_ids"] = list(ids)
        scene["dialogue"] = []
        for line in _items(item.get("dialogue"), "Répliques", 0, 10):
            if not isinstance(line, dict) or line.get("speaker_id") not in ids:
                raise ValueError("Une réplique doit appartenir à un personnage présent dans la scène.")
            record = dict(speaker_id=line["speaker_id"], text=_text(line.get("text"), "réplique", 1500))
            if "dialogue_id" in line:
                record["dialogue_id"] = _text(line.get("dialogue_id"), "identifiant de réplique", 120)
            if "delivery" in line:
                if line.get("delivery") not in DIALOGUE_DELIVERIES:
                    raise ValueError("Mode de restitution d’une réplique inconnu.")
                record["delivery"] = line["delivery"]
            if "delivery_note" in line:
                record["delivery_note"] = _text(line.get("delivery_note"), "indication de jeu", 240)
            scene["dialogue"].append(record)
        if recipe_spec.get("dialogue_policy") == "forbidden" and scene["dialogue"]:
            raise ValueError("Cette famille est strictement sans paroles : dialogue doit rester vide.")
        result["scenes"].append(scene)
    return result


def parse_response(value, operation, has_scenario, *, selected_id=None, recipe_id=RECIPE_ID,
                   recipe_version=RECIPE_VERSION, proposal_count=3, source_script="",
                   target_scene_count=None, creation_mode="ideas",
                   narrative_format=DEFAULT_NARRATIVE_FORMAT, has_series_outline=False):
    if not isinstance(value, dict):
        raise ValueError("Le modèle doit renvoyer un objet JSON.")
    reply = _text(value.get("reply"), "réponse", MAX_STORY_REPLY_CHARS)
    if operation == "revise" and value.get("discussion_only") is True and set(value) == {"reply", "discussion_only"}:
        return reply, None
    narrative_format = narrative_format_selection(narrative_format)
    if operation == "outline" or (
            operation == "revise" and narrative_format == "long" and has_series_outline and not has_scenario):
        field = "series_outline"
    else:
        field = "scenario" if operation in {"develop", "script"} or (operation == "revise" and has_scenario) else "concepts"
    continuation = creation_mode == "continuation"
    required = {"reply", field} | ({"continuity"} if continuation else set())
    extras = {"concepts", "selected_id"} if operation == "revise" and has_scenario else set()
    if not required.issubset(value) or set(value) - required - extras:
        raise ValueError(f"Réponse incomplète : reply et {field} sont attendus. Le brouillon reste disponible.")
    if field == "scenario":
        parsed = validate_scenario(value[field], recipe_id, recipe_version)
    elif field == "series_outline":
        parsed = validate_series_outline(value[field], recipe_id, recipe_version)
    else:
        parsed = validate_concepts(value[field], recipe_id, recipe_version, proposal_count,
                                   continuation=continuation)
    document = {field: parsed}
    if continuation:
        document["continuity"] = validate_story_continuity(value["continuity"])
    if field == "scenario" and target_scene_count is not None:
        scenes = document["scenario"]["scenes"]
        if len(scenes) != target_scene_count:
            raise ValueError(
                f"Le scénario doit contenir exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''}, mais le modèle en a renvoyé {len(scenes)}. "
                "Le brouillon est conservé pour diagnostic."
            )
    if operation == "script":
        validate_script_dialogue_coverage(source_script, document["scenario"])
    if "selected_id" in value and value["selected_id"] != selected_id:
        raise ValueError("Une révision ne peut pas choisir une autre histoire à votre place.")
    if field == "scenario" and "concepts" in value:
        document["concepts"] = validate_concepts(
            value["concepts"], recipe_id, recipe_version, proposal_count,
            continuation=continuation,
        )
    return reply, document


def response_contract(operation, has_scenario, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION,
                      proposal_count=3, *, creation_mode="ideas",
                      narrative_format=DEFAULT_NARRATIVE_FORMAT, has_series_outline=False):
    """An explicit wire example, never a vendor response-format dependency."""
    recipe_spec = _STORY_RECIPES[(recipe_id, recipe_version)]
    adult_required = recipe_spec.get("adult_required", False)
    narrative_format = narrative_format_selection(narrative_format)
    if operation == "outline" or (
            operation == "revise" and narrative_format == "long" and has_series_outline and not has_scenario):
        character = {"id": "series-c1", "name": "Nom stable", "description": "Identité visuelle et rôle stables dans la série."}
        if adult_required:
            character["adult"] = True
        episodes = []
        for index in range(1, SERIES_EPISODE_COUNT + 1):
            episodes.append({
                "id": f"episode-{index}",
                "title": f"Titre de l’épisode {index}",
                "promise": "Question locale compréhensible sans connaître les autres épisodes.",
                "opening_state": "État concret au début de cet épisode.",
                "conflict": "Obstacle principal de cet épisode.",
                "beats": ["Cause visible.", "Réaction ou tentative visible.", "Conséquence visible."],
                "local_payoff": "Résolution satisfaisante de la question locale.",
                "ending_state": "État exact et observable à la fin de l’épisode.",
                "carry_forward": "Élément transmis à l’épisode suivant, ou conclusion pour le quatrième.",
            })
        example = {
            "reply": "Présentation de l’arc long en quatre épisodes.",
            "series_outline": {
                "title": "Titre de la série",
                "premise": "Promesse générale de la série.",
                "overall_arc": "Progression causale globale des quatre épisodes.",
                "ending": "Aboutissement prévu de l’histoire globale.",
                "characters": [character],
                "episodes": episodes,
            },
        }
    elif operation in {"develop", "script"} or (operation == "revise" and has_scenario):
        character = {"id": "c1", "name": "Nom", "description": "Identité visuelle stable, tenue et caractère."}
        if adult_required:
            character["adult"] = True
        dialogue = {"speaker_id": "c1", "text": "Réplique exacte, sans guillemets englobants.", "delivery": "spoken"}
        if operation == "script":
            dialogue["dialogue_id"] = "dialogue-1"
        dialogue_items = [] if recipe_spec.get("dialogue_policy") == "forbidden" else [dialogue]
        scene = {"title": "Enjeu de cette micro-scène", "location_id": "l1", "character_ids": ["c1"],
                 "opening_state": "Situation et objets au début.",
                 "action": "Événements, actions et réactions enchaînés. Aucune caméra imposée.",
                 "dialogue": dialogue_items,
                 "ending_state": "Ce qui a changé et doit rester vrai dans la suite.",
                 "visual_transition": None}
        scene_examples = {
            "relationship_state": "Désir, rapport entre participants et degré de proximité à cet instant.",
            "appearance_state": "Tenues, nudité, vêtements déplacés et accessoires, sans ambiguïté de continuité.",
            "sexual_state": "Position exacte des corps et contacts sexuels déjà établis au début de la scène.",
        }
        for field, _ in recipe_spec["scene_fields"]:
            scene[field] = scene_examples[field]
        example = {"reply": "Résumé des choix ou modifications, en français.", "scenario": {
            "title": "Titre", "logline": "Histoire complète résumée en une phrase.",
            "characters": [character],
            "locations": [{"id": "l1", "name": "Lieu", "description": "Repères visuels réutilisables."}],
            "scenes": [scene]}}
    else:
        fields = _recipe_fields(recipe_id, recipe_version)
        concepts = [{"id": f"concept-{index}", **{field: f"Texte français : {field}" for field in fields}}
                    for index in range(1, proposal_count + 1)]
        if creation_mode == "continuation":
            for concept in concepts:
                concept["continuation_plan"] = {
                    "carry_over": "Fait, relation ou preuve déjà établi qui déclenche cette suite.",
                    "obstacle": "Nouvel obstacle directement causé par la situation héritée.",
                    "payoff": "Conséquence finale préparée par les scènes précédentes.",
                    "introduced_elements": [],
                }
        example = {"reply": (f"Présentation de {proposal_count} proposition"
                             f"{'s' if proposal_count > 1 else ''} et invitation à choisir ou ajuster."),
                   "concepts": concepts}
    if creation_mode == "continuation":
        example["continuity"] = {
            "series_summary": "Résumé cumulatif des épisodes antérieurs et du nouvel épisode si celui-ci est développé.",
            "latest_ending": "État exact à la fin du dernier épisode couvert par cette mémoire.",
            "established_facts": ["Fait canonique qui ne doit pas être redécouvert ni contredit."],
            "character_states": ["Personnage : situation, connaissance, relation ou objectif actuel."],
            "unresolved_threads": ["Conflit ou promesse encore ouvert."],
            "available_elements": ["Objet, preuve, lieu ou allié déjà introduit et encore mobilisable."],
        }
    return deepcopy(example)


def story_diagnostics(scenario, *, clip_seconds, target_scene_count, recipe_id=RECIPE_ID):
    if not scenario:
        return []
    diagnostics = []
    scenes = scenario["scenes"]
    if len(scenes) != target_scene_count:
        diagnostics.append(dict(code="scene_count", level="info",
            message=f"Le scénario contient {len(scenes)} scènes pour {target_scene_count} visées."))
    used_people, used_locations = set(), set()
    for index, scene in enumerate(scenes):
        used_people.update(scene["character_ids"])
        used_locations.add(scene["location_id"])
        words = sum(len(line["text"].split()) for line in scene["dialogue"])
        limit = max(6, int(clip_seconds * 2.4))
        if words > limit:
            diagnostics.append(dict(code="dialogue_density", level="warning", scene_index=index,
                message=f"Scène {index + 1} : {words} mots de dialogue pour {clip_seconds:g} s ; les gestes risquent de manquer d’espace."))
        if len(scene["character_ids"]) + 1 > 9:
            diagnostics.append(dict(code="reference_limit", level="warning", scene_index=index,
                message=f"Scène {index + 1} : personnages + décor dépassent les 9 références de Fabrication."))
        if len(scene["action"]) < 45:
            diagnostics.append(dict(code="thin_action", level="info", scene_index=index,
                message=f"Scène {index + 1} : l’action est très brève ; vérifie qu’elle décrit un changement observable."))
        for field, label in _STORY_RECIPES[(recipe_id, RECIPE_VERSION)]["scene_fields"]:
            if len(scene.get(field, "")) < 20:
                diagnostics.append(dict(code=f"thin_{field}", level="info", scene_index=index,
                    message=f"Scène {index + 1} : précise davantage « {label.lower()} »."))
    unused_people = [item["name"] for item in scenario["characters"] if item["id"] not in used_people]
    unused_locations = [item["name"] for item in scenario["locations"] if item["id"] not in used_locations]
    if unused_people:
        diagnostics.append(dict(code="unused_characters", level="info",
            message="Personnages jamais utilisés : " + ", ".join(unused_people) + "."))
    if unused_locations:
        diagnostics.append(dict(code="unused_locations", level="info",
            message="Décors jamais utilisés : " + ", ".join(unused_locations) + "."))
    return diagnostics


_DIALOGUE_DELIVERY_LABELS = {
    "spoken": "parlé",
    "voice_over": "voix off",
    "off_screen": "hors champ",
    "thought": "pensée / voix intérieure",
    "mediated": "voix transmise",
}


def dialogue_instruction(line, speaker):
    """Render exact speech and its delivery without merging metadata into the words."""
    delivery = line.get("delivery", "spoken")
    note = line.get("delivery_note")
    indication = note or (None if delivery == "spoken" else _DIALOGUE_DELIVERY_LABELS[delivery])
    label = f"{speaker} — {indication}" if indication else speaker
    return f"{label} : « {line['text']} »"


def visual_transition_instruction(scene, *, silent=False):
    transition = scene.get("visual_transition")
    if not transition:
        return None
    lines = [
        "TRANSITION VISUELLE À MONTRER DANS CE CLIP :",
        f"Avant visible : {transition['before']}",
        f"Déclencheur : {transition['trigger']}",
        f"Changement observable : {transition['visible_change']}",
        f"Après visible : {transition['after']}",
        "Montre ces quatre temps dans cet ordre, sans commencer après le changement ni sauter directement au résultat.",
    ]
    if silent:
        lines.append("La transformation doit être comprise sans parole, narration ni texte à l’écran.")
    return "\n".join(lines)


def scene_intention(scenario, index, duration=None, recipe_id=RECIPE_ID,
                    dialogue_language=DEFAULT_DIALOGUE_LANGUAGE):
    scene = scenario["scenes"][index]
    people = {character["id"]: character for character in scenario["characters"]}
    location = next(location for location in scenario["locations"] if location["id"] == scene["location_id"])
    lines = [f"Durée cible : {duration:g} secondes."] if duration is not None else []
    lines += [f"Décor : {location['name']}. {location['description']}",
              "Personnages : " + " ; ".join(f"{people[identity]['name']} : {people[identity]['description']}"
                                               for identity in scene["character_ids"]),
              f"Situation initiale : {scene['opening_state']}"]
    if scene.get("relationship_state"):
        lines.append(f"Dynamique relationnelle : {scene['relationship_state']}")
    if scene.get("appearance_state"):
        lines.append(f"Continuité des tenues : {scene['appearance_state']}")
    if scene.get("sexual_state"):
        lines.append(f"Position et contacts sexuels au début : {scene['sexual_state']}")
    lines.append(scene["action"])
    transition = visual_transition_instruction(
        scene, silent=recipe_id == SILENT_CATS_RECIPE_ID
    )
    if transition:
        lines.append(transition)
    if scene["dialogue"]:
        language = dialogue_language_selection(dialogue_language)
        lines.append(f"Langue parlée des dialogues : {dialogue_language_label(language)}.")
        lines.append("Répliques à prononcer exactement, en respectant cet ordre et ces locuteurs :\n" + "\n".join(
            dialogue_instruction(line, people[line["speaker_id"]]["name"]) for line in scene["dialogue"]))
    else:
        lines.append("Aucun dialogue.")
    requested_delivery = any(line.get("delivery", "spoken") != "spoken" for line in scene["dialogue"])
    restrictions = ("Respecte exactement les modes de restitution indiqués et n’ajoute aucune autre voix off. "
                    if requested_delivery else "N’ajoute aucune voix off. ")
    performance = ("Les gestes et réactions accompagnent les paroles. " if scene["dialogue"] else
                   "Les gestes, regards, postures et réactions portent toute l’action. ")
    speech_rule = ("Sans dialogue supplémentaire. " if scene["dialogue"] else
                   "Aucune parole, aucun dialogue, aucune voix off et aucune narration. ")
    lines += [f"À la fin : {scene['ending_state']}",
              "Invente une mise en scène créative, vivante et expressive. " + performance +
              "Préserve les identités, les objets importants et la continuité. " + speech_rule +
              (restrictions if scene["dialogue"] else "") + "Sans musique ni texte à l’écran."]
    return "\n\n".join(lines)


def scenario_text(scenario, duration, recipe_id=RECIPE_ID,
                  dialogue_language=DEFAULT_DIALOGUE_LANGUAGE):
    return f"{scenario['title']}\n\n{scenario['logline']}\n\n" + "\n\n".join(
        f"MICRO-SCÈNE {index + 1} — {scene['title']}\n\n"
        f"{scene_intention(scenario, index, duration, recipe_id, dialogue_language)}"
        for index, scene in enumerate(scenario["scenes"]))
