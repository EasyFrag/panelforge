"""Source-grounded editorial requirements and compact reader context (edition 2)."""
from copy import deepcopy
from .story_editions import experimental


def normalize_author_requirements(project, outline):
    """Single-unit source is the original brief, never a model's redundant recopy."""
    if (project["long_options"]["unit_count"] != 1 or not isinstance(outline, dict)
            or "author_requirements" not in outline
            or not (experimental(project) or
                    "author_requirements" in (project["document"].get("series_outline") or {}))):
        return outline, []
    result = deepcopy(outline)
    result.pop("author_requirements")
    return result, ["Séquence unique : citations redondantes écartées ; le point de départ original reste la source auteur."]


def validate_requirements(project, rows):
    """Only verbatim author excerpts can become source requirements; never generated evidence."""
    valid = []
    source = project.get("brief", "")
    units = {f"episode-{i}" for i in range(1, project["long_options"]["unit_count"] + 1)}
    for row in rows:
        if row["unit_id"] not in units or not row["quote"].strip() or row["quote"] not in source:
            raise ValueError("Une contrainte d’auteur doit citer un extrait exact du point de départ et une unité existante.")
        if row not in valid:
            valid.append(deepcopy(row))
    return valid


def author_requirements(project, identities):
    doc = project["document"]
    units = (doc.get("series_outline") or {}).get("episodes", [])
    scoped = (doc.get("series_outline") or {}).get("author_requirements", [])
    result = []
    for identity in identities:
        if len(units) == 1:
            excerpts = [project["brief"]] if project.get("brief") else []
        else:
            excerpts = [row["quote"] for row in scoped
                        if row["unit_id"] == identity and row["quote"] in project.get("brief", "")]
        item = dict(unit_id=identity, source_excerpts=excerpts)
        direction = doc.get("continuation_directions", {}).get(identity, {}).get("brief")
        if direction:
            item["author_followup"] = direction
        # Only explicit options belong to the author, not auto choices resolved by conception.
        preferences = project.get("narrative_preferences", {})
        item["explicit_choices"] = {k:v for k,v in preferences.items() if k in {"profile", "narration"} and v != "auto"}
        if units and identity == units[-1]["id"] and preferences.get("ending_type") not in {None, "auto"}:
            item["explicit_choices"]["ending_type"] = preferences["ending_type"]
        if len(units) > 1 and not excerpts and not direction:
            item["scope_note"] = "Aucune contrainte source attribuée à cette unité ; ne déduis aucune exigence de l’auteur à partir des choix du plan."
        result.append(item)
    return result


def compact_visual(values):
    result = deepcopy(values)
    for unit in result:
        for row in unit.get("scene_states", []):
            if row.get("start") == row.get("end"):
                row["state"] = row.pop("start")
                row.pop("end", None)
    return result


def language_severity(project, item, target):
    """Verify cited evidence. Semantic language judgement stays with the existing reader."""
    scenario = project["document"].get("episode_scenarios", {}).get(target) or {}
    try:
        index = int(item["target_id"].removeprefix("scene-")) - 1
    except ValueError:
        index = -1
    scenes = scenario.get("scenes", [])
    quote = item["dialogue_quote"]
    if not item["target_id"].startswith("scene-") or not 0 <= index < len(scenes) or not any(line["text"] == quote for line in scenes[index].get("dialogue", [])):
        raise ValueError("Le défaut de langue doit citer exactement une réplique de la scène indiquée.")
    protected = (project.get("writing_direction") or {}).get("protected_lines", [])
    if quote in protected:
        item.update(severity="warning", suggestion="Cette réplique est imposée mot pour mot par l’auteur. Clarifier sa demande avant de la traduire.")
    else:
        item["severity"] = "blocking"
    return item
