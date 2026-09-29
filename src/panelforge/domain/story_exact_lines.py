"""Explicit author lines, with source-bound IDs and validated narrative placement."""
from copy import deepcopy
import hashlib

from . import story_direction


def catalog(project):
    return [{"id": "author-line-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24], "text": text}
            for text in story_direction.settings(project)["protected_lines"]]


def validate_assignments(project, outline):
    source = {line["id"] for line in catalog(project)}
    rows = outline.get("author_line_assignments", [])
    if not isinstance(rows, list):
        raise ValueError("Attribution des répliques d’auteur illisible.")
    units = {u["id"]: {e["id"] for e in u["events"]} for u in outline["episodes"]}
    characters = {c["id"] for c in outline["characters"]}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"line_id", "unit_id", "event_id", "speaker_id"}:
            raise ValueError("Une réplique protégée doit préciser son ID, son unité, son événement et son locuteur.")
        identity = row["line_id"]
        if not isinstance(identity, str) or identity not in source or identity in seen:
            raise ValueError("Référence de réplique d’auteur inconnue, périmée ou attribuée deux fois.")
        if (any(not isinstance(row[key], str) for key in ("unit_id", "event_id", "speaker_id"))
                or row["unit_id"] not in units or row["event_id"] not in units[row["unit_id"]] or row["speaker_id"] not in characters):
            raise ValueError("Attribution de réplique hors de son unité, événement ou casting.")
        seen.add(identity)
    if seen != source:
        raise ValueError("Attribue les répliques protégées dans author_line_assignments en corrigeant l’arc avec la v3 ; aucune attribution n’est devinée.")
    return deepcopy(rows)


def for_unit(project, identity):
    outline = project["document"]["series_outline"]
    texts = {line["id"]: line["text"] for line in catalog(project)}
    return [dict(row, text=texts[row["line_id"]]) for row in validate_assignments(project, outline)
            if row["unit_id"] == identity]


def hydrate(project, scenario, state, identity):
    """Resolve references before review, duration checks, persistence or fabrication.

    Already canonical untouched scenes retain their provenance. Free-form wire
    dialogue cannot impersonate an author line using a dialogue_id.
    """
    source = {row["line_id"]: row for row in for_unit(project, identity)}
    result = deepcopy(scenario)
    seen = set()
    metadata = {row["scene_index"]: row for row in state["scene_events"]}
    for index, scene in enumerate(result["scenes"]):
        for line in scene["dialogue"]:
            reference = line.pop("line_ref", None)
            if reference is None and str(line.get("dialogue_id", "")).startswith("author-line-"):
                reference = line["dialogue_id"]
            if reference is None:
                continue
            row = source.get(reference)
            if row is None or row["speaker_id"] != line["speaker_id"] or row["event_id"] not in metadata[index]["event_ids"]:
                raise ValueError("Réplique protégée inconnue, périmée ou déplacée hors de son attribution.")
            if "text" in line and line["text"] != row["text"]:
                raise ValueError("Une réplique protégée ne peut pas être reformulée.")
            line.update(text=row["text"], dialogue_id=reference)
            seen.add(reference)
    if seen != set(source):
        raise ValueError("Une réplique protégée manque : utilise son line_ref dans le dialogue de l’événement prévu.")
    return result


def memory_unchanged(project):
    """Only an explicitly classified language-only repair freezes story memory."""
    from .long_stories import scope
    if (project.get("job") or {}).get("operation") != "repair_episode":
        return False
    issues = project["document"].get("reviews", {}).get(scope(project), {}).get("issues", [])
    blocking = [item for item in issues if item.get("severity") == "blocking"]
    return bool(blocking) and all(item.get("category") == "dialogue_language" for item in blocking)
