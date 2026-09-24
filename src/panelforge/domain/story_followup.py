"""Small author directions and explicit, immutable continuation context."""
from copy import deepcopy
import hashlib
import json

from .stories import dialogue_language_selection
from .story_continuity import carry_forward

FIELDS = {"start": 1500, "beats": 4000, "ending": 1500, "constraints": 2000}
LABELS = {"start": "Point de départ", "beats": "Moments importants", "ending": "Fin souhaitée", "constraints": "Contraintes"}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def draft_id(project_id, unit_id):
    return "followup-" + fingerprint([project_id, unit_id])[:32]


def direction(value):
    if not isinstance(value, dict) or set(value) - FIELDS.keys():
        raise ValueError("Direction de l’épisode invalide.")
    result = {}
    for key, maximum in FIELDS.items():
        text = value.get(key, "")
        if key == "beats" and isinstance(text, list) and all(isinstance(x, str) for x in text):
            text = "\n".join(text)
        if not isinstance(text, str) or len(text) > maximum:
            raise ValueError(f"{LABELS[key]} : {maximum} caractères maximum.")
        result[key] = text.strip()
    return result


def brief(value):
    value = direction(value)
    return "\n\n".join(f"{LABELS[key]} :\n{text}" for key, text in value.items() if text)


def settings(value):
    if not isinstance(value, dict):
        raise ValueError("Réglages de suite invalides.")
    result = deepcopy(value)
    result["dialogue_language"] = dialogue_language_selection(value.get("dialogue_language", "French"))
    for key, minimum, maximum in (("scene_count", 1, 12), ("clip_seconds", 5, 15), ("target_seconds", 10, 2160)):
        number = value.get(key)
        if type(number) is not int or not minimum <= number <= maximum:
            raise ValueError(f"Réglage {key} : valeur entre {minimum} et {maximum} attendue.")
    if value.get("workflow_mode") not in {"automatic", "manual"}:
        raise ValueError("Choisissez Automatique ou Manuel guidé.")
    for key in ("architect_model_id", "writer_model_id"):
        if not isinstance(value.get(key), str) or len(value[key]) > 300:
            raise ValueError("Modèle d’écriture invalide.")
    return result


def source_context(project, unit_id=None):
    """Only written units up to the chosen boundary are facts; the arc is separate."""
    doc = project["document"]
    outline = doc.get("series_outline") or {}
    units = outline.get("episodes", [])
    if units:
        unit_id = unit_id or doc.get("selected_episode_id")
        index = next((i for i, u in enumerate(units) if u["id"] == unit_id), None)
        if index is None:
            raise ValueError("Choisissez l’épisode dont la suite doit partir.")
        scenario = doc.get("episode_scenarios", {}).get(unit_id)
        if not scenario and doc.get("selected_episode_id") == unit_id:
            scenario = doc.get("scenario")
        written = []
        for unit in units[:index + 1]:
            identity = unit["id"]
            previous = doc.get("episode_scenarios", {}).get(identity)
            if not previous and identity == unit_id:
                previous = scenario
            if not previous:
                raise ValueError("Écrivez les épisodes précédents avant de préparer cette suite.")
            # Preserve events and knowledge without duplicating the selected full scenario.
            written.append(dict(unit_id=identity, title=previous.get("title"),
                scenes=[{k: s.get(k) for k in ("opening_state", "action", "dialogue", "ending_state")}
                        for s in previous["scenes"]] if identity != unit_id else [],
                state=deepcopy(doc.get("episode_states", {}).get(identity))))
        next_unit = deepcopy(units[index + 1]) if index + 1 < len(units) else None
        source_label = units[index].get("title") or unit_id
    else:
        if unit_id not in {None, "standalone"}:
            raise ValueError("Cet épisode source n’existe pas.")
        unit_id, scenario, written, next_unit = "standalone", doc.get("scenario"), [], None
        source_label = project["title"]
    if not scenario or not scenario.get("scenes"):
        raise ValueError("Un scénario écrit est nécessaire pour préparer sa suite.")
    history = (doc.get("continuity") if not units else None) or project.get("prior_story") or {}
    if isinstance(history, str):
        try:
            decoded = json.loads(history)
            if isinstance(decoded, (dict, list)):
                history = decoded  # Avoid repeatedly escaping previous JSON at each sequel.
        except ValueError:
            pass
    context = dict(source_story_id=project["project_id"], source_unit_id=unit_id,
        source_title=project["title"], source_label=source_label,
        previous_history=deepcopy(history),
        written_episodes=written, latest_scenario=deepcopy(scenario),
        visual_state=carry_forward(scenario), planned_arc=deepcopy(outline) or None,
        next_unit=next_unit, episode_formats=deepcopy(doc.get("episode_formats", {})), next_written=bool(next_unit and doc.get("episode_scenarios", {}).get(next_unit["id"])),
        original_intention=project.get("brief", ""), recipe=deepcopy(project["recipe"]),
        source_format={k: project.get(k) for k in ("scene_count", "clip_seconds", "target_seconds", "narrative_format")},
        visual_universe=project.get("visual_universe", ""), long_options=deepcopy(project.get("long_options")),
        dialogue_language=project["dialogue_language"], dialogue_register=project.get("dialogue_register", 0))
    return context


def history_text(context):
    facts = {k: context[k] for k in ("previous_history", "written_episodes", "latest_scenario", "visual_state")}
    result = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
    if len(result) > 60000:
        raise ValueError("L’historique dépasse 60 000 caractères. Réduisez le résumé antérieur avant de créer la suite ; aucun fait n’a été supprimé.")
    return result


def response_schema():
    fields = {key: {"type": "string", "maxLength": maximum} for key, maximum in FIELDS.items()}
    return {"type": "object", "additionalProperties": False, "required": ["reply", "direction"],
        "properties": {"reply": {"type": "string", "maxLength": 5000}, "direction": {"anyOf": [
            {"type": "null"}, {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}]}}}
