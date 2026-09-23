"""Versioned narrative contracts and provenance; no LLM or rendering dependencies."""
from copy import deepcopy
import hashlib
import json

from .stories import response_contract, parse_response, validate_scenario
from . import story_contracts as contracts
from .story_diagnostics import normalize_scene_state, episode_issues, project_quality, outline_reference_issues

ENGINE = {"id": "story.long", "version": "2.0.0"}
PROFILES = {"melodrama": "Mélodrame", "social": "Conflit du quotidien / joute verbale", "transformation": "Transformation / quête",
            "suspense": "Suspense / révélation", "fantasy": "Aventure à règle fantastique"}
DELIVERIES = {"serial": "Feuilleton", "continuous": "Récit continu"}
NARRATIONS = {"dialogue": "Dialogues", "audio": "Narration explicite", "visual": "Narration visuelle"}
ENDINGS = {"resolution", "open", "reversal", "cost"}
EXTRA_OPERATIONS = {"review_outline", "review_episode", "repair_outline", "repair_episode", "revise_outline",
                    "compose", "edit_outline", "review_block", "discuss"}


def is_v2(project):
    return project.get("narrative_engine") == ENGINE and project.get("narrative_format") == "long"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def text(value, label, limit=3000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} : texte requis, au maximum {limit} caractères.")
    return value.strip()


def items(value, label, maximum=24, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label} : liste de {minimum} à {maximum} éléments attendue.")
    return value


def strings(value, label, maximum=24):
    return [text(item, label) for item in items(value, label, maximum)]


def refs(value, allowed, label):
    values = strings(value, label)
    if len(values) != len(set(values)) or set(values) - set(allowed):
        raise ValueError(f"{label} : référence inconnue ou répétée.")
    return values


def fields(value, required, label, *, path=None):
    if not isinstance(value, dict) or set(value) != set(required.split()):
        message = f"{label} doit contenir exactement : {required}."
        if path:
            message += f" Emplacement : {path}."
            if isinstance(value, dict):
                missing, extra = set(required.split()) - set(value), set(value) - set(required.split())
                if missing:
                    message += " Champs manquants : " + ", ".join(sorted(missing)) + "."
                if extra:
                    message += " Champs inattendus : " + ", ".join(sorted(extra)) + "."
            else:
                message += " Un objet JSON est attendu."
        raise ValueError(message)


def options(value):
    fields(value, "profile delivery narration unit_count ending_type", "Options longues")
    result = dict(value)
    for key, allowed in (("profile", {"auto", *PROFILES}), ("delivery", DELIVERIES),
                         ("narration", {"auto", *NARRATIONS}), ("ending_type", ENDINGS | {"auto"})):
        if not isinstance(value[key], str) or value[key] not in allowed:
            raise ValueError(f"Option narrative inconnue : {key}.")
    if type(value["unit_count"]) is not int or not 1 <= value["unit_count"] <= 12:
        raise ValueError("Choisissez 1 à 12 épisodes ou séquences.")
    return result


def scope(project, operation=None):
    operation = operation or project["job"]["operation"]
    if operation == "compose":
        return "outline"
    if operation == "review_block":
        return "block"
    if operation in {"revise", "discuss"} and project.get("job", {}).get("feedback_target"):
        return project["job"]["feedback_target"]["unit_id"]
    if "outline" in operation:
        return "outline"
    if operation in {"develop", "review_episode", "repair_episode"}:
        return project["document"].get("selected_episode_id")
    if operation == "revise":
        doc = project["document"]
        return doc.get("selected_episode_id") if doc.get("scenario") else ("outline" if doc.get("series_outline") else "ideas")
    return "ideas"


def previous_ids(project, episode_id):
    ordered = [e["id"] for e in (project["document"].get("series_outline") or {}).get("episodes", [])]
    return ordered[:ordered.index(episode_id)] if episode_id in ordered else []


def dependency_hash(project, episode_id):
    doc = project["document"]
    return fingerprint({"outline": doc.get("series_outline"), "options": project["long_options"],
        "format": doc.get("episode_formats", {}).get(episode_id),
        "previous": [{"id": identity, "scenario": doc.get("episode_scenarios", {}).get(identity),
                      "state": doc.get("episode_states", {}).get(identity)}
                     for identity in previous_ids(project, episode_id)]})


def source_hash(project, target):
    doc = project["document"]
    if target == "outline":
        return fingerprint([project["brief"], project["long_options"], doc.get("series_outline"), doc.get("episode_formats")])
    return fingerprint([dependency_hash(project, target), doc.get("episode_scenarios", {}).get(target),
                        doc.get("episode_states", {}).get(target)])


def review_current(project, target):
    review = project["document"].get("reviews", {}).get(target)
    return bool(review and review.get("source_hash") == source_hash(project, target))


def review_clear(project, target):
    return review_current(project, target) and not any(
        issue["severity"] == "blocking" for issue in project["document"]["reviews"][target]["issues"]) and not any(
        item["level"] == "blocking" for item in project_quality(project, target))


def status(project):
    doc = project["document"]
    result = {"outline_reviewed": review_clear(project, "outline"), "units": {},
              "reviews": {key: {"current": review_current(project, key)} for key in doc.get("reviews", {})}}
    previous_ready = True
    for episode in (doc.get("series_outline") or {}).get("episodes", []):
        identity = episode["id"]
        written = bool(doc.get("episode_scenarios", {}).get(identity))
        stale = written and doc.get("episode_provenance", {}).get(identity) != dependency_hash(project, identity)
        reviewed = review_clear(project, identity)
        ready = bool(written and not stale and reviewed and previous_ready and result["outline_reviewed"])
        result["units"][identity] = {"written": written, "stale": bool(stale), "reviewed": reviewed,
                                     "ready": ready, "previous_ready": previous_ready}
        previous_ready = ready
    result["fabrication_ready"] = result["units"].get(doc.get("selected_episode_id"), {}).get("ready", False)
    return result


def check_start(project, operation):
    target, doc = scope(project, operation), project["document"]
    if operation in EXTRA_OPERATIONS - {"compose"} and not doc.get("series_outline"):
        raise ValueError("Construisez d’abord le contrat et l’arc.")
    if operation.startswith("review_") and target not in {"outline", "block"} and not doc.get("scenario"):
        raise ValueError("Rédigez d’abord cette unité.")
    if operation.startswith("repair_"):
        if not review_current(project, target) or not doc["reviews"][target]["issues"]:
            raise ValueError("Une relecture actuelle avec des remarques est nécessaire pour cette correction.")
    if target not in {"outline", "ideas", "block", None} and operation != "discuss":
        state = status(project)
        if not state["outline_reviewed"]:
            raise ValueError("Relisez et corrigez l’arc avant de développer ses unités.")
        provisional = project.get("workflow") and operation == "develop" and all(
            state["units"][identity]["written"] and not state["units"][identity]["stale"]
            for identity in previous_ids(project, target))
        if not state["units"].get(target, {}).get("previous_ready") and not provisional:
            raise ValueError("Validez la relecture des unités précédentes avant de poursuivre ; leur canon doit être à jour.")
        if operation == "review_episode" and state["units"][target]["stale"]:
            raise ValueError("Le passé a changé : réécrivez cette unité avant de la relire.")


def outline_example(project):
    count = project["long_options"]["unit_count"]
    sample = response_contract("outline", False, project["recipe"]["id"], project["recipe"]["version"])["series_outline"]
    sample["overall_arc"] = "Progression causale globale des unités, jusqu’au type de fin demandé."
    sample["contract"] = {"promise": "Expérience promise", "protagonist_goal": "Désir concret",
        "stakes": "Ce qui peut être perdu", "must_keep": ["Élément du brief à préserver"], "freedoms": ["Ajout autorisé"]}
    sample["world_rules"] = []
    sample["secrets"] = []
    base = sample["episodes"][0]
    sample["episodes"] = []
    for index in range(1, count + 1):
        unit = deepcopy(base)
        unit.update(id=f"episode-{index}", title=f"Unité {index}",
                    promise="Question ou progression attendue dans cette unité.",
                    local_payoff="Changement accompli, sans résoudre forcément la quête globale.",
                    carry_forward="Conséquence à transmettre à la suite, ou aboutissement global.",
                    ending_type=project["long_options"]["ending_type"] if index == count else "open")
        unit.pop("beats")
        unit["events"] = [{"id": f"event-{index}", "trigger": "Cause, indice ou objectif",
            "change": "Décision, découverte ou conséquence", "evidence": "Ce que le public doit voir ou entendre",
            "depends_on": [] if index == 1 else [f"event-{index-1}"]}]
        sample["episodes"].append(unit)
    return {"reply": "Choix narratifs", "series_outline": sample}


def outline_entry_contracts():
    """Describe optional list entries without requiring the model to invent any."""
    return {
        "world_rules": {"id": "rule-1", "rule": "Règle utile, avec ses conditions connues", "limits": None},
        "secrets": {"id": "secret-1", "truth": "Vérité réservée", "known_by": [], "reveal_episode_id": None},
    }


def normalize_world_rules(project, rules):
    """Preserve plain rules from older prompts; missing limits remain explicitly unknown."""
    if not isinstance(rules, list) or not any(isinstance(rule, str) for rule in rules):
        return rules
    previous = (project["document"].get("series_outline") or {}).get("world_rules", [])
    reserved = {rule["id"] for rule in previous}
    reserved.update(rule["id"] for rule in rules if isinstance(rule, dict) and isinstance(rule.get("id"), str))
    normalized, index = [], 1
    for rule in rules:
        if not isinstance(rule, str):
            normalized.append(deepcopy(rule))
            continue
        content = text(rule, "règle")
        matches = [old for old in previous if old["rule"] == content]
        if previous:
            if len(matches) != 1:
                raise ValueError("Une règle révisée a perdu son identifiant : impossible de la rattacher sans ambiguïté. Le brouillon est conservé.")
            normalized.append(deepcopy(matches[0]))
            continue
        while f"rule-{index}" in reserved:
            index += 1
        identity = f"rule-{index}"
        reserved.add(identity)
        normalized.append(dict(id=identity, rule=content, limits=None))
    return normalized


def normalize_event_dependencies(project, value):
    """An editorial pass may omit, but must not implicitly erase, the saved causal graph."""
    previous = project["document"].get("series_outline")
    if ((project.get("job") or {}).get("operation") != "edit_outline"
            or not isinstance(previous, dict) or not isinstance(value, dict)):
        return value, []
    old_units, new_units = previous.get("episodes"), value.get("episodes")
    if not isinstance(old_units, list) or not isinstance(new_units, list) or len(old_units) != len(new_units):
        return value, []
    pairs, identities = [], set()
    for old_unit, new_unit in zip(old_units, new_units):
        if (not isinstance(old_unit, dict) or not isinstance(new_unit, dict)
                or old_unit.get("id") != new_unit.get("id")):
            return value, []
        old_events, new_events = old_unit.get("events"), new_unit.get("events")
        if not isinstance(old_events, list) or not isinstance(new_events, list) or len(old_events) != len(new_events):
            return value, []
        for old, new in zip(old_events, new_events):
            if not isinstance(old, dict) or not isinstance(new, dict):
                return value, []
            identity = new.get("id")
            if not isinstance(identity, str) or identity != old.get("id") or identity in identities:
                return value, []
            identities.add(identity)
            pairs.append((old, new))
    restored = {new["id"]: deepcopy(old["depends_on"]) for old, new in pairs
                if set(new) == {"id", "trigger", "change", "evidence"}
                and old.get("trigger") == new.get("trigger") and old.get("change") == new.get("change")
                and isinstance(old.get("depends_on"), list)}
    if not restored:
        return value, []
    result = deepcopy(value)
    for unit in result["episodes"]:
        for event in unit["events"]:
            if event["id"] in restored:
                event["depends_on"] = restored[event["id"]]
    return result, ["Liens de causalité repris de l’arc enregistré pour " + ", ".join(restored)
                    + " : identifiants, séquences et ordre inchangés ; texte reçu et brouillon original conservés."]


def validate_outline(project, value):
    fields(value, "title premise overall_arc ending characters episodes contract world_rules secrets", "Arc V2")
    value, _normalizations = normalize_event_dependencies(project, value)
    structural = deepcopy(value)
    structural["world_rules"] = normalize_world_rules(project, value["world_rules"])
    problems = contracts.structural_issues(structural, contracts.outline_schema(project), "series_outline")
    if not problems:
        problems.extend(outline_reference_issues(project, structural))
    if problems:
        raise contracts.StoryValidationError(problems)
    result = {key: text(value[key], key, 6000) for key in ("title", "premise", "overall_arc", "ending")}
    fields(value["contract"], "promise protagonist_goal stakes must_keep freedoms", "Contrat")
    result["contract"] = {key: text(value["contract"][key], key) for key in ("promise", "protagonist_goal", "stakes")}
    result["contract"].update({key: strings(value["contract"][key], key) for key in ("must_keep", "freedoms")})
    # Reuse identity and family constraints without the legacy fixed four-unit arc.
    shell = response_contract("develop", False, project["recipe"]["id"], project["recipe"]["version"])["scenario"]
    shell["characters"] = deepcopy(items(value["characters"], "Personnages", 12, 1))
    first_id = shell["characters"][0].get("id") if isinstance(shell["characters"][0], dict) else None
    shell["scenes"][0].update(character_ids=[first_id], dialogue=[])
    result["characters"] = validate_scenario(shell, project["recipe"]["id"], project["recipe"]["version"])["characters"]
    characters = {item["id"] for item in result["characters"]}
    count = project["long_options"]["unit_count"]
    units = items(value["episodes"], "Unités", count, count)
    result["episodes"], all_events = [], set()
    for index, unit in enumerate(units, 1):
        fields(unit, "id title promise opening_state conflict events local_payoff ending_state carry_forward ending_type", "Unité")
        if unit["id"] != f"episode-{index}" or unit["ending_type"] not in ENDINGS:
            raise ValueError("Identifiant ordonné ou type de fin invalide.")
        record = {key: text(unit[key], key) for key in unit if key != "events"}
        record["events"] = []
        for event_index, event in enumerate(items(unit["events"], "Événements", 12, 1)):
            fields(event, "id trigger change evidence depends_on", "Événement",
                   path=f"series_outline.episodes[{index - 1}].events[{event_index}]")
            e = {key: text(event[key], key, 1500) for key in ("id", "trigger", "change", "evidence")}
            if e["id"] in all_events:
                raise ValueError("Identifiant d’événement en double.")
            e["depends_on"] = refs(event["depends_on"], all_events, "Dépendances causales antérieures")
            all_events.add(e["id"])
            record["events"].append(e)
        record["beats"] = [e["change"] for e in record["events"]]
        result["episodes"].append(record)
    if result["episodes"][-1]["ending_type"] != project["long_options"]["ending_type"]:
        raise ValueError("La fin globale doit respecter le type choisi.")
    for collection, required in (("world_rules", "id rule limits"), ("secrets", "id truth known_by reveal_episode_id")):
        result[collection], identities = [], set()
        entries = normalize_world_rules(project, value[collection]) if collection == "world_rules" else value[collection]
        for raw in items(entries, collection, 24):
            fields(raw, required, collection)
            identity = text(raw["id"], "identifiant", 120)
            if identity in identities:
                raise ValueError(f"Identifiant {collection} en double.")
            identities.add(identity)
            if collection == "world_rules":
                item = dict(id=identity, rule=text(raw["rule"], "règle"),
                            limits=None if raw["limits"] is None else text(raw["limits"], "limites"))
            else:
                target = raw["reveal_episode_id"]
                if target not in [u["id"] for u in result["episodes"]] and target is not None:
                    raise ValueError("Un secret doit être réservé à une unité existante ou rester ouvert (null).")
                item = dict(id=identity, truth=text(raw["truth"], "vérité"),
                            known_by=refs(raw["known_by"], characters, "Personnages informés"), reveal_episode_id=target)
            result[collection].append(item)
    return result


def episode_example(project):
    example = response_contract("develop", False, project["recipe"]["id"], project["recipe"]["version"])
    unit = next(u for u in project["document"]["series_outline"]["episodes"] if u["id"] == scope(project))
    example["scenario"]["characters"] = deepcopy(project["document"]["series_outline"]["characters"])
    first_id = example["scenario"]["characters"][0]["id"]
    example["scenario"]["scenes"][0]["character_ids"] = [first_id]
    for line in example["scenario"]["scenes"][0]["dialogue"]:
        line["speaker_id"] = first_id
    example["episode_state"] = {
        "scene_events": [{"scene_index": 0, "event_ids": [e["id"] for e in unit["events"]],
                          "evidence": "Preuve visible ou audible indispensable", "action_seconds": 3, "reveals": []}],
        "facts": [{"id": "fact-1", "text": "Fait désormais établi", "event_id": unit["events"][0]["id"]}],
        "knowledge": [], "open_threads": ["Question qui reste ouverte"], "resolved_threads": []}
    return example


def production_action(action, evidence):
    return text(action + "\nInformation indispensable à rendre visible ou audible : " + evidence,
                "Action et information indispensable cumulées", 6000)


def validate_episode(project, scenario, state):
    state, _notes = normalize_scene_state(project, scenario, state)
    problems = episode_issues(project, scenario, state)
    if any(item["level"] == "blocking" for item in problems):
        raise contracts.StoryValidationError(problems)
    scenario = validate_scenario(scenario, project["recipe"]["id"], project["recipe"]["version"])
    # A knowledge row represents an acquisition, not a repetition of the initial bible.
    secrets = project["document"]["series_outline"]["secrets"]
    known = {s["id"]: set(s["known_by"]) for s in secrets}
    for identity in previous_ids(project, scope(project)):
        for row in project["document"].get("episode_states", {}).get(identity, {}).get("knowledge", []):
            known.setdefault(row["secret_id"], set()).update(row["character_ids"])
    parsed = deepcopy(state)
    parsed["knowledge"] = []
    for row in state["knowledge"]:
        if row["secret_id"] is None and not secrets:
            continue
        if row["secret_id"] not in known:
            raise contracts.StoryValidationError([contracts.issue("unknown_secret", "episode_state.knowledge", "Secret inconnu.")])
        learned = [identity for identity in row["character_ids"] if identity not in known[row["secret_id"]]]
        if learned:
            parsed["knowledge"].append(dict(row, character_ids=learned))
            known[row["secret_id"]].update(learned)
    return scenario, parsed


def review_example():
    return {"reply": "Résultat de la relecture", "review": {"summary": "Évaluation justifiée",
        "issues": [{"severity": "blocking", "target_id": "contract", "problem": "Problème précis observé",
                    "suggestion": "Correction ciblée, sans réécrire toute l’histoire"}]}}


def review_targets(project, target=None):
    target = target or scope(project)
    doc = project["document"]
    outline = doc["series_outline"]
    targets = {"contract", "world_rules", "secrets"} | {u["id"] for u in outline["episodes"]}
    targets |= {e["id"] for u in outline["episodes"] for e in u["events"]}
    targets |= {item["id"] for key in ("world_rules", "secrets", "characters") for item in outline[key]}
    if target != "outline":
        scenario = doc.get("episode_scenarios", {}).get(target) or doc.get("scenario") or {}
        targets |= {f"scene-{i+1}" for i in range(len(scenario.get("scenes", [])))}
    return targets


def validate_review(project, value, target=None):
    fields(value, "summary issues", "Relecture")
    target = target or scope(project)
    targets = review_targets(project, target)
    issues = []
    for raw in items(value["issues"], "Remarques", 24):
        fields(raw, "severity target_id problem suggestion", "Remarque")
        if raw["severity"] not in {"blocking", "warning"}:
            raise ValueError("Une remarque doit être blocking ou warning.")
        if raw["target_id"] not in targets:
            raise ValueError(f"Cible de relecture inconnue : {raw['target_id']}. Choisissez un élément présent dans le document.")
        issues.append({key: text(raw[key], key) for key in raw})
    for diagnostic in project_quality(project, target):
        target_id = diagnostic.get("target_id", "contract")
        if not any(item["problem"] == diagnostic["message"] for item in issues):
            issues.append(dict(severity=diagnostic["level"], target_id=target_id,
                problem=diagnostic["message"], suggestion="Corriger localement ce passage et vérifier sa faisabilité.",
                code=diagnostic["code"], path=diagnostic["path"]))
    return dict(summary=text(value["summary"], "bilan", 6000), issues=issues,
                source_hash=source_hash(project, target), contract_version=contracts.VERSION)


def parse(project, value):
    operation, target = project["job"]["operation"], scope(project)
    if not isinstance(value, dict):
        raise ValueError("Objet JSON narratif attendu.")
    value = normalize_episode_response(deepcopy(value))
    continuity_warning = None
    if project["job"].get("response_contract_version") == contracts.VERSION:
        from .story_continuity import isolate_optional_ledger
        continuity_warning = isolate_optional_ledger(project, value)
    if contracts.structured(project):
        schema = contracts.response_schema(project)
        if schema is not None:
            problems = contracts.structural_issues(value, schema)
            if problems:
                raise contracts.StoryValidationError(problems)
        value = contracts.canonical_response(project, value)
        if continuity_warning and "scenario" in value:
            from .story_continuity import empty
            visual = value["scenario"].setdefault("visual_continuity", empty())
            visual["warnings"] = (visual.get("warnings", []) + [continuity_warning])[-4:]
    reply = text(value.get("reply"), "réponse", 12000)
    if operation == "discuss":
        fields(value, "reply discussion_only", "Discussion")
        if value["discussion_only"] is not True:
            raise ValueError("Une question ne doit pas modifier l’histoire.")
        return reply, None
    if operation in {"revise", "revise_outline"} and value.get("discussion_only") is True:
        fields(value, "reply discussion_only", "Discussion")
        return reply, None
    if target == "ideas":
        return parse_response(value, "ideas", False, recipe_id=project["recipe"]["id"],
                              recipe_version=project["recipe"]["version"])
    if operation == "compose":
        fields(value, "reply series_outline resolved_options", "Conception")
        fields(value["resolved_options"], "profile narration ending_type", "Choix narratifs")
        resolved = dict(project["long_options"])
        for key, allowed in (("profile", PROFILES), ("narration", NARRATIONS), ("ending_type", ENDINGS)):
            choice = value["resolved_options"][key]
            if choice not in allowed or resolved[key] not in {"auto", choice}:
                raise ValueError(f"Choix narratif incompatible avec votre préférence : {key}.")
            resolved[key] = choice
        candidate = deepcopy(project)
        candidate["long_options"] = resolved
        return reply, {"series_outline": validate_outline(candidate, value["series_outline"]), "resolved_options": resolved}
    if operation == "edit_outline":
        fields(value, "reply series_outline review", "Édition de l’histoire")
        outline = validate_outline(project, value["series_outline"])
        candidate = deepcopy(project)
        candidate["document"]["series_outline"] = outline
        return reply, {"series_outline": outline, "review": validate_review(candidate, value["review"], "outline")}
    if operation == "review_block":
        fields(value, "reply reviews", "Relecture des séquences")
        identities = project["job"]["review_unit_ids"]
        reviews = {}
        for item in items(value["reviews"], "Relectures", len(identities), len(identities)):
            fields(item, "unit_id summary issues", "Relecture de séquence")
            identity = item["unit_id"]
            if identity not in identities or identity in reviews:
                raise ValueError("Une relecture est requise pour chaque séquence du bloc, sans doublon.")
            reviews[identity] = validate_review(project, {k: item[k] for k in ("summary", "issues")}, identity)
        return reply, {"block_reviews": reviews}
    if operation.startswith("review_"):
        fields(value, "reply review", "Réponse de relecture")
        return reply, {"review": validate_review(project, value["review"])}
    if target == "outline":
        fields(value, "reply series_outline", "Réponse d’arc")
        return reply, {"series_outline": validate_outline(project, value["series_outline"])}
    value = normalize_episode_response(value)
    fields(value, "reply scenario episode_state", "Réponse de scénario")
    scenario, state = validate_episode(project, value["scenario"], value["episode_state"])
    feedback = project["job"].get("feedback_target") or {}
    scene_index = feedback.get("scene_index")
    if operation == "revise" and scene_index is not None:
        previous = project["document"]["episode_scenarios"][target]
        previous_memory = normalize_scene_state(project, previous,
            project["document"]["episode_states"][target])[0]["scene_events"]
        metadata_changed = {key: value for key, value in scenario.items() if key not in {"scenes", "visual_continuity"}} != {
            key: value for key, value in previous.items() if key not in {"scenes", "visual_continuity"}}
        if metadata_changed or len(scenario["scenes"]) != len(previous["scenes"]) or any(
                scene != previous["scenes"][index] or state["scene_events"][index] != previous_memory[index]
                for index, scene in enumerate(scenario["scenes"]) if index != scene_index):
            raise ValueError("Le retour ciblait une scène, mais le reste du scénario ou de sa continuité a aussi changé. Le brouillon est conservé ; élargis la cible si nécessaire.")
    return reply, {"scenario": scenario, "episode_state": state}


def normalize_episode_response(value):
    """Recover the observed envelope mistake without inventing canon or dropping conflicts."""
    if not isinstance(value.get("scenario"), dict) or "episode_state" not in value["scenario"]:
        return value
    result = deepcopy(value)
    nested = result["scenario"].pop("episode_state")
    if "episode_state" in result and result["episode_state"] != nested:
        raise ValueError("Deux mémoires de continuité différentes ont été renvoyées ; le brouillon est conservé.")
    result["episode_state"] = nested
    return result


def input_hash(project):
    parts = [project["document"], project["brief"], project["long_options"]]
    if project.get("prior_story"):
        parts.append(project["prior_story"])
    return fingerprint(parts)


def apply_document(project, incoming):
    doc, target = project["document"], scope(project)
    if "resolved_options" in incoming:
        project["long_options"] = incoming["resolved_options"]
    if "concepts" in incoming:
        doc.update(concepts=incoming["concepts"], selected_id=incoming["concepts"][0]["id"],
                   scenario=None, series_outline=None, selected_episode_id=None, episode_scenarios={}, episode_formats={},
                   episode_states={}, episode_provenance={}, reviews={})
    elif "series_outline" in incoming:
        doc["series_outline"] = incoming["series_outline"]
        doc.setdefault("episode_scenarios", {})
        for unit in incoming["series_outline"]["episodes"]:
            doc.setdefault("episode_formats", {}).setdefault(unit["id"],
                {"scene_count": project["scene_count"], "clip_seconds": project["clip_seconds"]})
        doc["selected_episode_id"] = doc.get("selected_episode_id") or "episode-1"
        doc["scenario"] = deepcopy(doc["episode_scenarios"].get(doc["selected_episode_id"]))
    elif "block_reviews" in incoming:
        doc.setdefault("reviews", {}).update(incoming["block_reviews"])
    elif "review" in incoming:
        doc.setdefault("reviews", {})[target] = incoming["review"]
    else:
        doc["scenario"] = deepcopy(incoming["scenario"])
        doc.setdefault("episode_scenarios", {})[target] = deepcopy(incoming["scenario"])
        doc.setdefault("episode_states", {})[target] = incoming["episode_state"]
        doc.setdefault("episode_provenance", {})[target] = dependency_hash(project, target)
    if "series_outline" in incoming and "review" in incoming:
        doc.setdefault("reviews", {})["outline"] = dict(incoming["review"], source_hash=source_hash(project, "outline"))


def fabrication_scenario(project, *, require_review=True, episode_id=None):
    doc = project["document"]
    target = episode_id or doc.get("selected_episode_id")
    scenario = deepcopy(doc.get("episode_scenarios", {}).get(target) if episode_id is not None else doc.get("scenario"))
    if not is_v2(project):
        return scenario
    if require_review and not status(project)["units"].get(target, {}).get("ready"):
        raise ValueError("La rédaction longue doit être à jour et relue sans problème bloquant avant Fabrication.")
    if scenario is None:
        return None
    for item in doc.get("episode_states", {}).get(target, {}).get("scene_events", []):
        scene = scenario["scenes"][item["scene_index"]]
        scene["action"] = production_action(scene["action"], item["evidence"])
    return scenario
