"""Local structural, continuity and feasibility checks for narrative drafts."""
from copy import deepcopy
import re
import unicodedata

from .story_contracts import (array, character_schema, choice, issue, nullable, obj,
                              scene_schema, state_schema, string, structural_issues)


def words(text):
    folded = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z]+", "".join(c for c in folded if not unicodedata.combining(c)))


def normalize_scene_state(project, scenario, state):
    """Upgrade legacy metadata only when its existing ending anchors the coda."""
    from .long_stories import scope
    result, notes = deepcopy(state), []
    if not isinstance(result, dict) or not isinstance(result.get("scene_events"), list) or not isinstance(scenario, dict):
        return result, notes
    unit = next(u for u in project["document"]["series_outline"]["episodes"] if u["id"] == scope(project))
    required = {e["id"] for e in unit["events"]}
    seen = set()
    ignored = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "est", "avec", "dans", "en", "a", "il", "elle", "que", "qui", "se", "son", "sa", "ses"}
    ending = set(words(unit["ending_state"])) - ignored
    scenes = scenario.get("scenes", [])
    for index, item in enumerate(result["scene_events"]):
        if not isinstance(item, dict):
            continue
        ids = item.get("event_ids")
        if isinstance(ids, list):
            seen.update(e for e in ids if isinstance(e, str))
        if "purpose" not in item:
            item["purpose"] = "progression"
            if ids == [] and index > 0 and index == len(scenes) - 1 and required <= seen:
                visible = set(words(str(item.get("evidence", "")))) - ignored
                common = ending & visible
                if len(common) >= 4 and len(common) >= .6 * len(visible):
                    item.update(purpose="reaction", anchor_scene_index=index - 1)
                    notes.append(f"Clip {index + 1} : réaction finale rattachée au clip précédent ; état final déjà demandé par l’arc, texte conservé.")
        item.setdefault("anchor_scene_index", None)
        item.setdefault("hints", [])
    return result, notes


def episode_issues(project, scenario, state):
    from .long_stories import scope, previous_ids
    target, doc = scope(project), project["document"]
    outline = doc["series_outline"]
    unit = next(u for u in outline["episodes"] if u["id"] == target)
    fmt = doc["episode_formats"][target]
    scene = scene_schema(project)
    metadata = scene["properties"].pop("narrative")
    scene["required"].remove("narrative")
    scene["required"].remove("visual_transition")
    # Archived dialogue fields are retained, not silently erased by the adapter.
    line = scene["properties"]["dialogue"]["items"]
    line["required"].remove("delivery")
    line["properties"].update(dialogue_id=string(120), delivery_note=string(240))
    canonical = obj(title=string(), logline=string(), characters=array(character_schema(project), 1, 12),
        locations=array(obj(id=string(120), name=string(120), description=string()), 1, 8), scenes=array(scene, 1, fmt["scene_count"]))
    memory = state_schema(project)
    # Historical empty-secret entries are handled by the existing lossless compatibility rule.
    if not outline["secrets"]:
        memory["properties"]["knowledge"]["maxItems"] = 24
        memory["properties"]["knowledge"]["items"]["properties"]["secret_id"] = nullable(string(120))
    metadata["properties"]["scene_index"] = dict(type="integer", minimum=0)
    metadata["required"].append("scene_index")
    memory["properties"]["scene_events"] = array(metadata, 1, fmt["scene_count"])
    memory["required"].append("scene_events")
    errors = structural_issues(scenario, canonical, "scenario") + structural_issues(state, memory, "episode_state")
    # Do not manufacture secondary errors from malformed objects; sibling structural errors remain visible.
    if errors:
        return errors + quality_issues(project, scenario=scenario, state=state, target=target)
    chars = {c["id"]: c for c in outline["characters"]}
    location_ids = {loc["id"] for loc in scenario["locations"]}
    for collection in ("characters", "locations"):
        ids = [x["id"] for x in scenario[collection]]
        if len(ids) != len(set(ids)):
            errors.append(issue("duplicate_id", f"scenario.{collection}", "Identifiants en double."))
    for index, char in enumerate(scenario["characters"]):
        if char["id"] not in chars or char["name"] != chars[char["id"]]["name"]:
            errors.append(issue("cast_changed", f"scenario.characters[{index}]", "Identité différente de la bible."))
    for index, item in enumerate(scenario["scenes"]):
        path = f"scenario.scenes[{index}]"
        if item["location_id"] not in location_ids:
            errors.append(issue("unknown_location", path + ".location_id", "Décor inconnu."))
        if len(set(item["character_ids"])) != len(item["character_ids"]):
            errors.append(issue("duplicate_character", path + ".character_ids", "Personnage répété."))
        if set(item["character_ids"]) - {c["id"] for c in scenario["characters"]}:
            errors.append(issue("missing_cast_entry", path + ".character_ids", "Personnage absent du casting reçu."))
        for n, line in enumerate(item["dialogue"]):
            if line["speaker_id"] not in item["character_ids"]:
                errors.append(issue("absent_speaker", f"{path}.dialogue[{n}].speaker_id", "Locuteur absent de la scène."))
    events = {e["id"]: e for e in unit["events"]}
    secrets = {s["id"]: s for s in outline["secrets"]}
    past = {s for identity in previous_ids(project, target)
            for item in doc.get("episode_states", {}).get(identity, {}).get("scene_events", []) for s in item["reveals"]}
    due = {s["id"] for s in secrets.values() if s["reveal_episode_id"] == target}
    seen, revealed = set(), set()
    if len(state["scene_events"]) != len(scenario["scenes"]):
        errors.append(issue("scene_mapping_count", "episode_state.scene_events", "Une affectation est nécessaire par clip."))
    for index, item in enumerate(state["scene_events"]):
        path = f"episode_state.scene_events[{index}]"
        for key in ("event_ids", "reveals", "hints"):
            if len(item[key]) != len(set(item[key])):
                errors.append(issue("duplicate_reference", path + "." + key, "Référence répétée."))
        if item["scene_index"] != index:
            errors.append(issue("scene_order", path + ".scene_index", "Index de scène incorrect."))
        anchor = item["anchor_scene_index"]
        if anchor is not None and not 0 <= anchor < index:
            errors.append(issue("scene_anchor", path + ".anchor_scene_index", "Le rattachement doit viser une scène antérieure."))
        if not item["event_ids"] and (item["purpose"] == "progression" or anchor is None):
            errors.append(issue("scene_event_missing", path + ".event_ids", f"Clip {index + 1} : préciser l’événement servi ou rattacher cette réaction/transition à une scène antérieure."))
        for identity in item["event_ids"]:
            if (set(events[identity]["depends_on"]) & set(events)) - seen:
                errors.append(issue("event_order", path + ".event_ids", f"{identity} est utilisé avant sa préparation."))
            seen.add(identity)
        if set(item["reveals"]) - (past | due):
            errors.append(issue("early_reveal", path + ".reveals", "Confirmation publique prématurée ; un indice doit figurer dans hints."))
        if set(item["reveals"]) & set(item["hints"]):
            errors.append(issue("ambiguous_reveal", path, "Une vérité ne peut être à la fois simple indice et confirmation dans la même scène."))
        revealed.update(item["reveals"])
        if len(scenario["scenes"]) > index and len(scenario["scenes"][index]["action"] + item["evidence"]) > 5900:
            errors.append(issue("production_text_size", path + ".evidence", "Action et preuve cumulées trop longues pour la fabrication."))
    if set(events) - seen:
        errors.append(issue("event_coverage", "episode_state.scene_events", "Événements non montrés : " + ", ".join(sorted(set(events) - seen))))
    if due - revealed:
        errors.append(issue("reveal_coverage", "episode_state.scene_events", "Confirmations réservées non montrées : " + ", ".join(sorted(due - revealed))))
    fact_ids = [f["id"] for f in state["facts"]]
    if len(fact_ids) != len(set(fact_ids)):
        errors.append(issue("duplicate_fact", "episode_state.facts", "Identifiants de faits en double."))
    for index, row in enumerate(state["knowledge"]):
        path = f"episode_state.knowledge[{index}]"
        if len(row["character_ids"]) != len(set(row["character_ids"])):
            errors.append(issue("duplicate_knower", path + ".character_ids", "Personnage informé répété."))
        if row["secret_id"] is not None and row["secret_id"] not in secrets:
            errors.append(issue("unknown_secret", path + ".secret_id", "Secret inconnu dans l’arc."))
    return errors


def quality_issues(project, *, scenario=None, state=None, target=None, outline=None):
    """Heuristics are explicit estimates; only a large timing excess blocks approval."""
    issues = []
    if isinstance(scenario, dict) and isinstance(state, dict):
        fmt = project["document"].get("episode_formats", {}).get(target, {})
        seconds = fmt.get("clip_seconds", project["clip_seconds"])
        scenes = scenario.get("scenes", [])
        mappings = state.get("scene_events", [])
        for item in mappings if isinstance(mappings, list) else []:
            if not isinstance(item, dict):
                continue
            index, action = item.get("scene_index"), item.get("action_seconds")
            if type(index) is not int or not isinstance(scenes, list) or not 0 <= index < len(scenes) or type(action) not in (int, float):
                continue
            clip = scenes[index]
            if not isinstance(clip, dict) or not isinstance(clip.get("dialogue"), list):
                continue
            count = sum(len(line["text"].split()) for line in clip["dialogue"] if isinstance(line, dict) and isinstance(line.get("text"), str))
            estimate = count / 2.4 + action
            if estimate > seconds:
                severe = count / 3.5 + action > seconds * 1.3
                issues.append(issue("clip_load", f"scenario.scenes[{index}]",
                    f"Clip {index + 1} : {count} mots + {action:g} s d’actions successives, environ {estimate:.1f} s pour {seconds} s disponibles. "
                    "Raccourcir les répliques ou redistribuer les actions en préservant les réactions.",
                    "blocking" if severe else "warning", scene_index=index, target_id=f"scene-{index + 1}", estimated_seconds=round(estimate, 1)))
    # Several English function words in a narrative sentence, never IDs or names.
    markers = {"the", "with", "while", "without", "their", "they", "together", "behind", "from", "into", "was", "were", "because", "that", "this", "her", "his", "and", "for", "after", "having", "heard", "leave", "leaves", "discovers"}
    prose = {"title", "premise", "overall_arc", "ending", "description", "promise", "opening_state", "conflict", "local_payoff", "ending_state", "carry_forward", "trigger", "change", "evidence", "protagonist_goal", "stakes", "truth", "rule", "limits", "action", "logline", "must_keep", "freedoms"}
    def walk(value, path, field=""):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}", key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", field)
        elif isinstance(value, str) and (field in prose or (field == "text" and project.get("dialogue_language", "French") == "French")):
            tokens = words(value)
            found = markers & set(tokens)
            if len(tokens) >= 8 and len(found) >= 3 and sum(t in markers for t in tokens) / len(tokens) >= .14:
                issues.append(issue("language_residue", path, "Passage potentiellement anglais dans un champ français : " + value[:160], "warning"))
    walk(outline if outline is not None else scenario, "series_outline" if outline is not None else "scenario")
    return issues


def project_quality(project, target):
    doc = project["document"]
    if target == "outline":
        return quality_issues(project, outline=doc.get("series_outline"))
    return quality_issues(project, scenario=doc.get("episode_scenarios", {}).get(target),
                          state=doc.get("episode_states", {}).get(target), target=target)


def outline_reference_issues(project, outline):
    errors, earlier = [], set()
    for collection in ("characters", "secrets", "world_rules"):
        ids = [entry["id"] for entry in outline[collection]]
        if len(ids) != len(set(ids)):
            errors.append(issue("duplicate_id", "series_outline." + collection, "Identifiants en double."))
    for index, unit in enumerate(outline["episodes"]):
        path = f"series_outline.episodes[{index}]"
        if unit["id"] != f"episode-{index + 1}":
            errors.append(issue("unit_order", path + ".id", "Identifiant de séquence hors ordre."))
        for n, event in enumerate(unit["events"]):
            event_path = f"{path}.events[{n}]"
            if event["id"] in earlier:
                errors.append(issue("duplicate_event", event_path + ".id", "Identifiant d’événement en double."))
            if set(event["depends_on"]) - earlier or len(event["depends_on"]) != len(set(event["depends_on"])):
                errors.append(issue("event_dependency", event_path + ".depends_on", "Dépendance inconnue, répétée ou postérieure."))
            earlier.add(event["id"])
    if outline["episodes"][-1]["ending_type"] != project["long_options"]["ending_type"]:
        errors.append(issue("ending_choice", "series_outline.episodes[-1].ending_type", "La fin ne respecte pas le choix narratif."))
    characters = {c["id"] for c in outline["characters"]}
    for index, secret in enumerate(outline["secrets"]):
        if set(secret["known_by"]) - characters or len(secret["known_by"]) != len(set(secret["known_by"])):
            errors.append(issue("secret_knowers", f"series_outline.secrets[{index}].known_by", "Personnage informé inconnu ou répété."))
    return errors
