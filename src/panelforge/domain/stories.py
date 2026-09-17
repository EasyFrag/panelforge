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

_STORY_RECIPES = {
    (RECIPE_ID, RECIPE_VERSION): {
        "id": RECIPE_ID, "version": RECIPE_VERSION, "label": "Mélodrame fruits",
        "description": "Fruits anthropomorphes, conflits frontaux et retournements visuels.",
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


def validate_concepts(value, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION, expected_count=3):
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
        concepts.append(dict(id=identity, **{key: _text(item.get(key), key, 2000) for key in fields}))
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
                   target_scene_count=None):
    if not isinstance(value, dict):
        raise ValueError("Le modèle doit renvoyer un objet JSON.")
    reply = _text(value.get("reply"), "réponse", MAX_STORY_REPLY_CHARS)
    if operation == "revise" and value.get("discussion_only") is True and set(value) == {"reply", "discussion_only"}:
        return reply, None
    field = "scenario" if operation in {"develop", "script"} or (operation == "revise" and has_scenario) else "concepts"
    required = {"reply", field}
    extras = {"concepts", "selected_id"} if operation == "revise" and has_scenario else set()
    if not required.issubset(value) or set(value) - required - extras:
        raise ValueError(f"Réponse incomplète : reply et {field} sont attendus. Le brouillon reste disponible.")
    document = {field: validate_scenario(value[field], recipe_id, recipe_version) if field == "scenario"
                else validate_concepts(value[field], recipe_id, recipe_version, proposal_count)}
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
        document["concepts"] = validate_concepts(value["concepts"], recipe_id, recipe_version, proposal_count)
    return reply, document


def response_contract(operation, has_scenario, recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION,
                      proposal_count=3):
    """An explicit wire example, never a vendor response-format dependency."""
    recipe_spec = _STORY_RECIPES[(recipe_id, recipe_version)]
    adult_required = recipe_spec.get("adult_required", False)
    if operation in {"develop", "script"} or (operation == "revise" and has_scenario):
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
                 "ending_state": "Ce qui a changé et doit rester vrai dans la suite."}
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
        example = {"reply": (f"Présentation de {proposal_count} proposition"
                             f"{'s' if proposal_count > 1 else ''} et invitation à choisir ou ajuster."),
                   "concepts": [{"id": f"concept-{index}", **{field: f"Texte français : {field}" for field in fields}}
                                for index in range(1, proposal_count + 1)]}
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


def scene_intention(scenario, index, duration=None):
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
    if scene["dialogue"]:
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


def scenario_text(scenario, duration):
    return f"{scenario['title']}\n\n{scenario['logline']}\n\n" + "\n\n".join(
        f"MICRO-SCÈNE {index + 1} — {scene['title']}\n\n{scene_intention(scenario, index, duration)}"
        for index, scene in enumerate(scenario["scenes"]))
