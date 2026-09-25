"""Library identities and editorial numbering, independent of writing/provider state."""
from copy import deepcopy
import re


class LibraryConflict(ValueError):
    pass


def empty_metadata():
    return dict(schema_version=1, revision=0, groups={}, projects={})


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"story-[a-f0-9]{32}", value):
        raise ValueError("Identifiant d’histoire invalide.")
    return value


def episode_count(project):
    if project.get("narrative_format") != "long":
        return 1
    options = project.get("long_options") or {}
    if options.get("delivery", "serial") == "continuous":
        return 1
    return max(1, len((project.get("document", {}).get("series_outline") or {}).get("episodes", []))
               or options.get("unit_count", 4))


def memberships(projects, metadata):
    """Follow explicit parent/organization links, retaining trashed ancestors and branches."""
    by_id = {p["project_id"]: p for p in projects}
    assigned, visiting = {}, set()
    def resolve(key):
        if key in assigned:
            return assigned[key]
        if key in visiting:
            raise ValueError("Les liens de série forment une boucle.")
        visiting.add(key)
        project = by_id[key]
        choice = metadata.get("projects", {}).get(key, {})
        parent = project.get("parent_story_id")
        if choice.get("group_id"):
            result = (choice["group_id"], choice["episode_number"])
        elif parent in by_id:
            group, first = resolve(parent)
            # A sequel can branch from a particular published episode of a serial project.
            source = (project.get("continuation_origin") or {}).get("source_unit_id")
            units = (by_id[parent].get("document", {}).get("series_outline") or {}).get("episodes", [])
            offset = next((i + 1 for i, unit in enumerate(units) if unit["id"] == source), episode_count(by_id[parent]))
            if (by_id[parent].get("long_options") or {}).get("delivery") == "continuous":
                offset = 1
            result = (group, first + offset)
        else:
            result = (key, 1)
        visiting.remove(key)
        assigned[key] = result
        return result
    for key in by_id:
        resolve(key)
    return assigned


def metadata_change(current, projects, *, kind, target, values):
    """Validate an explicit organization action without rewriting any narrative."""
    result = deepcopy(current)
    by_id = {p["project_id"]: p for p in projects}
    links = memberships(projects, current)
    identity(target)
    if kind == "group":
        if target not in {group for group, _ in links.values()}:
            raise ValueError("Cette série n’existe plus dans la bibliothèque.")
        if not values or set(values) - {"title", "favorite"}:
            raise ValueError("Modification de série invalide.")
        if "title" in values and (not isinstance(values["title"], str) or not 1 <= len(values["title"].strip()) <= 160):
            raise ValueError("Le titre doit contenir de 1 à 160 caractères.")
        if "favorite" in values and type(values["favorite"]) is not bool:
            raise ValueError("Favori invalide.")
        group = result["groups"].setdefault(target, {})
        group.update({k: v.strip() if k == "title" else v for k, v in values.items()})
    elif kind == "project":
        if target not in by_id:
            raise FileNotFoundError(target)
        if not values or set(values) - {"trashed", "group_id", "episode_number"}:
            raise ValueError("Modification d’histoire invalide.")
        if "trashed" in values and type(values["trashed"]) is not bool:
            raise ValueError("État de corbeille invalide.")
        if ("group_id" in values) != ("episode_number" in values):
            raise ValueError("Choisis une série et un numéro d’épisode ensemble.")
        if "group_id" in values:
            identity(values["group_id"])
            if values["group_id"] != target and values["group_id"] not in {g for g, _ in links.values()}:
                raise ValueError("Série de destination inconnue.")
            if type(values["episode_number"]) is not int or not 1 <= values["episode_number"] <= 9999:
                raise ValueError("Numéro d’épisode invalide.")
            # Do not let descendants silently jump series when their parent is reorganized.
            for key, (group, number) in links.items():
                result["projects"].setdefault(key, {}).update(group_id=group, episode_number=number)
        result["projects"].setdefault(target, {}).update(values)
    else:
        raise ValueError("Action de bibliothèque inconnue.")
    return result
