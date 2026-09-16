"""Narrative documents. Independent of video grammars and rendering engines."""
from copy import deepcopy
import json

RECIPE_ID = "story.brainrot"
RECIPE_VERSION = "1.0.0"
CONCEPT_FIELDS = ("title", "hook", "protagonist", "antagonist", "escalation", "reveal", "ending")


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
                if (following < len(text) and text[following] in "}]"
                        and previous and previous not in "[{,:"):
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


def validate_concepts(value):
    concepts = []
    for i, item in enumerate(_items(value, "Propositions", 3, 3), 1):
        if not isinstance(item, dict):
            raise ValueError("Proposition illisible.")
        identity = item.get("id", f"concept-{i}")
        if identity not in ("concept-1", "concept-2", "concept-3"):
            raise ValueError("Identifiant de proposition inconnu.")
        concepts.append(dict(id=identity, **{k: _text(item.get(k), k, 2000) for k in CONCEPT_FIELDS}))
    if len({c["id"] for c in concepts}) != 3:
        raise ValueError("Identifiants de proposition en double.")
    if len({c["title"].casefold() for c in concepts}) != 3:
        raise ValueError("Les trois propositions doivent avoir des titres distincts.")
    return concepts


def validate_scenario(value):
    if not isinstance(value, dict):
        raise ValueError("Scénario illisible.")
    result = {k: _text(value.get(k), k) for k in ("title", "logline")}
    for collection, maximum in (("characters", 12), ("locations", 8)):
        result[collection] = []
        for item in _items(value.get(collection), collection, 1, maximum):
            if not isinstance(item, dict):
                raise ValueError(f"Fiche {collection} illisible.")
            result[collection].append({k: _text(item.get(k), k, 3000 if k == "description" else 120)
                                       for k in ("id", "name", "description")})
        ids = [c["id"] for c in result[collection]]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Identifiants {collection} en double.")
    characters = {c["id"] for c in result["characters"]}
    locations = {c["id"] for c in result["locations"]}
    result["scenes"] = []
    for item in _items(value.get("scenes"), "Micro-scènes", 1, 18):
        if not isinstance(item, dict):
            raise ValueError("Micro-scène illisible.")
        scene = {k: _text(item.get(k), k) for k in ("title", "location_id", "action", "opening_state", "ending_state")}
        ids = _items(item.get("character_ids"), "Personnages de la scène", 1, 12)
        if any(not isinstance(c, str) or c not in characters for c in ids) or len(set(ids)) != len(ids):
            raise ValueError("Une scène utilise un personnage inconnu ou en double.")
        if scene["location_id"] not in locations:
            raise ValueError("Une scène utilise un décor inconnu.")
        scene["character_ids"] = list(ids)
        scene["dialogue"] = []
        for line in _items(item.get("dialogue"), "Répliques", 0, 10):
            if not isinstance(line, dict) or line.get("speaker_id") not in ids:
                raise ValueError("Une réplique doit appartenir à un personnage présent dans la scène.")
            scene["dialogue"].append(dict(speaker_id=line["speaker_id"], text=_text(line.get("text"), "réplique", 1500)))
        result["scenes"].append(scene)
    return result


def parse_response(value, operation, has_scenario, *, selected_id=None):
    if not isinstance(value, dict):
        raise ValueError("Le modèle doit renvoyer un objet JSON.")
    reply = _text(value.get("reply"), "réponse", 12000)
    if operation == "revise" and value.get("discussion_only") is True and set(value) == {"reply", "discussion_only"}:
        return reply, None
    field = "scenario" if operation == "develop" or (operation == "revise" and has_scenario) else "concepts"
    required = {"reply", field}
    extras = {"concepts", "selected_id"} if operation == "revise" and has_scenario else set()
    if not required.issubset(value) or set(value) - required - extras:
        raise ValueError(f"Réponse incomplète : reply et {field} sont attendus. Le brouillon reste disponible.")
    document = {field: validate_scenario(value[field]) if field == "scenario" else validate_concepts(value[field])}
    # Some writers return the surrounding current_document when revising a
    # scenario. Accept its known, validated fields without switching stories.
    if "selected_id" in value and value["selected_id"] != selected_id:
        raise ValueError("Une révision ne peut pas choisir une autre histoire à votre place.")
    if field == "scenario" and "concepts" in value:
        document["concepts"] = validate_concepts(value["concepts"])
    return reply, document


def response_contract(operation, has_scenario):
    """An explicit wire example, never a vendor response-format dependency."""
    if operation == "develop" or (operation == "revise" and has_scenario):
        example = {"reply": "Résumé des choix ou modifications, en français.", "scenario": {
            "title": "Titre", "logline": "Histoire complète résumée en une phrase.",
            "characters": [{"id": "c1", "name": "Nom", "description": "Identité visuelle stable, tenue et caractère."}],
            "locations": [{"id": "l1", "name": "Lieu", "description": "Repères visuels réutilisables."}],
            "scenes": [{"title": "Enjeu de cette micro-scène", "location_id": "l1", "character_ids": ["c1"],
                "opening_state": "Situation et objets au début.", "action": "Événements, actions et réactions enchaînés. Aucune caméra imposée.",
                "dialogue": [{"speaker_id": "c1", "text": "Réplique exacte, sans guillemets englobants."}],
                "ending_state": "Ce qui a changé et doit rester vrai dans la suite."}]}}
    else:
        example = {"reply": "Présentation des trois pistes et invitation à choisir ou ajuster.",
                   "concepts": [{"id": f"concept-{i}", **{field: f"Texte français : {field}" for field in CONCEPT_FIELDS}} for i in range(1, 4)]}
    return deepcopy(example)


def scene_intention(scenario, index, duration=None):
    scene = scenario["scenes"][index]
    people = {c["id"]: c for c in scenario["characters"]}
    location = next(l for l in scenario["locations"] if l["id"] == scene["location_id"])
    lines = [f"Durée cible : {duration:g} secondes."] if duration is not None else []
    lines += [f"Décor : {location['name']}. {location['description']}",
              "Personnages : " + " ; ".join(f"{people[c]['name']} : {people[c]['description']}" for c in scene["character_ids"]),
              f"Situation initiale : {scene['opening_state']}", scene["action"]]
    if scene["dialogue"]:
        lines.append("Répliques à prononcer exactement, en respectant cet ordre et ces locuteurs :\n" + "\n".join(
            f"{people[d['speaker_id']]['name']} : « {d['text']} »" for d in scene["dialogue"]))
    else:
        lines.append("Aucun dialogue.")
    lines += [f"À la fin : {scene['ending_state']}",
              "Invente une mise en scène créative, vivante et expressive. Les gestes et réactions accompagnent les paroles. "
              "Préserve les identités, les objets importants et la continuité. Sans dialogue supplémentaire, voix off, musique ni texte à l’écran."]
    return "\n\n".join(lines)


def scenario_text(scenario, duration):
    return f"{scenario['title']}\n\n{scenario['logline']}\n\n" + "\n\n".join(
        f"MICRO-SCÈNE {i+1} — {scene['title']}\n\n{scene_intention(scenario, i, duration)}"
        for i, scene in enumerate(scenario["scenes"]))
