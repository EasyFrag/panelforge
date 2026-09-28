"""Story wire contracts: one schema for prompts, transport and structural validation.

Storage/fabrication remain V2. The 2.1 wire format carries each scene's narrative
metadata alongside its text and does not ask the writer to copy the cast.
"""
from copy import deepcopy
import math

from .stories import story_recipe_spec
from .story_editions import refined

VERSION = "2.2.0"  # Default retained for existing projects; new sparse visual states use 2.4.0.
SUPPORTED_VERSIONS = {"2.1.0", VERSION, "2.3.0", "2.4.0", "2.5.0"}


def has_continuity(project):
    return (project.get("job") or {}).get("response_contract_version") in {VERSION, "2.3.0", "2.4.0", "2.5.0"}


def structured(project):
    return (project.get("job") or {}).get("response_contract_version") in SUPPORTED_VERSIONS


def obj(**properties):
    return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)


def string(limit=3000):
    return dict(type="string", minLength=1, maxLength=limit)


def array(item, minimum=0, maximum=24):
    return dict(type="array", items=item, minItems=minimum, maxItems=maximum)


def choice(values):
    values = list(values)
    return dict(type="string", enum=values) if values else dict(type="string", enum=["__aucune_reference_autorisee__"])


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def issue(code, path, message, level="blocking", **extra):
    return dict(code=code, path=path, message=message, level=level, **extra)


class StoryValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("\n".join(f"{item['path']} : {item['message']}" for item in issues if item["level"] == "blocking"))


def structural_issues(value, schema, path="response"):
    """Validate exactly the JSON Schema subset emitted below; collect sibling errors."""
    if "anyOf" in schema:
        alternatives = [structural_issues(value, item, path) for item in schema["anyOf"]]
        return [] if any(not errors for errors in alternatives) else min(alternatives, key=len)
    kind = schema.get("type")
    valid = {"object": type(value) is dict, "array": type(value) is list,
             "string": type(value) is str, "integer": type(value) is int,
             "number": type(value) is int or (type(value) is float and math.isfinite(value)),
             "boolean": type(value) is bool, "null": value is None}.get(kind, True)
    if not valid:
        return [issue("field_type", path, f"Type attendu : {kind}.")]
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(issue("field_choice", path, "Valeur absente des choix autorisés."))
    if kind == "object":
        for key in schema["required"]:
            if key not in value:
                errors.append(issue("field_required", f"{path}.{key}", "Champ obligatoire absent."))
        for key, item in value.items():
            if key not in schema["properties"]:
                errors.append(issue("field_extra", f"{path}.{key}", "Champ inattendu."))
            else:
                errors.extend(structural_issues(item, schema["properties"][key], f"{path}.{key}"))
    elif kind == "array":
        minimum, maximum = schema.get("minItems", 0), schema.get("maxItems", math.inf)
        if not minimum <= len(value) <= maximum:
            errors.append(issue("list_size", path, f"Liste de {minimum} à {maximum} éléments attendue."))
        for index, item in enumerate(value):
            errors.extend(structural_issues(item, schema["items"], f"{path}[{index}]"))
    elif kind == "string" and (len(value.strip()) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 240000)):
        errors.append(issue("text_size", path, "Texte vide ou trop long."))
    elif kind in {"number", "integer"} and not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
        errors.append(issue("number_range", path, "Nombre hors limites."))
    return errors


def character_schema(project):
    fields = dict(id=string(120), name=string(120), description=string())
    result = obj(**fields)
    result["properties"]["adult"] = dict(type="boolean", enum=[True])
    if story_recipe_spec(project["recipe"]["id"], project["recipe"]["version"]).get("adult_required"):
        result["required"].append("adult")
    return result


def outline_schema(project):
    from .long_stories import ENDINGS
    count = project["long_options"]["unit_count"]
    texts = array(string())
    event = obj(id=string(120), trigger=string(1500), change=string(1500), evidence=string(1500), depends_on=array(string(120)))
    unit = obj(id=choice(f"episode-{i}" for i in range(1, count + 1)), title=string(), promise=string(),
               opening_state=string(), conflict=string(), events=array(event, 1, 12), local_payoff=string(),
               ending_state=string(), carry_forward=string(), ending_type=choice(sorted(ENDINGS)))
    secret = obj(id=string(120), truth=string(), known_by=array(string(120)),
                 reveal_episode_id=nullable(choice(f"episode-{i}" for i in range(1, count + 1))))
    result = obj(title=string(6000), premise=string(6000), overall_arc=string(6000), ending=string(6000),
        characters=array(character_schema(project), 1, 12), episodes=array(unit, count, count),
        contract=obj(promise=string(), protagonist_goal=string(), stakes=string(), must_keep=texts, freedoms=texts),
        world_rules=array(obj(id=string(120), rule=string(), limits=nullable(string()))), secrets=array(secret))
    from .story_editions import experimental
    if count > 1 and (experimental(project) or
            "author_requirements" in (project["document"].get("series_outline") or {})):
        # Single units use the original brief directly; only multiple units need attribution.
        result["properties"]["author_requirements"] = array(obj(
            unit_id=choice(f"episode-{i}" for i in range(1, count + 1)), quote=string(6000)), 0, 60)
        if experimental(project) and (project.get("job") or {}).get("operation") == "compose":
            result["required"].append("author_requirements")
    if refined(project):
        from .story_exact_lines import catalog
        lines = catalog(project)
        if lines or "author_line_assignments" in (project["document"].get("series_outline") or {}):
            result["properties"]["author_line_assignments"] = array(obj(
                line_id=choice(line["id"] for line in lines),
                unit_id=choice(f"episode-{i}" for i in range(1, count + 1)),
                event_id=string(120), speaker_id=string(120)), len(lines), len(lines))
            result["required"].append("author_line_assignments")
    return result


def state_schema(project):
    from .long_stories import scope
    outline = project["document"]["series_outline"]
    unit = next(u for u in outline["episodes"] if u["id"] == scope(project))
    events = choice(e["id"] for e in unit["events"])
    return obj(facts=array(obj(id=string(120), text=string(), event_id=events)),
        knowledge=array(obj(secret_id=choice(s["id"] for s in outline["secrets"]),
            character_ids=array(choice(c["id"] for c in outline["characters"]), 1, 12), event_id=events), 0, 24 if outline["secrets"] else 0),
        open_threads=array(string()), resolved_threads=array(string()))


def scene_schema(project, *, canonical=False):
    from .long_stories import scope
    doc = project["document"]
    unit = next(u for u in doc["series_outline"]["episodes"] if u["id"] == scope(project))
    characters = choice(c["id"] for c in doc["series_outline"]["characters"])
    secret = choice(s["id"] for s in doc["series_outline"]["secrets"])
    fmt = doc["episode_formats"][scope(project)]
    dialogue = obj(speaker_id=characters, text=string(1500),
                   delivery=choice(["spoken", "voice_over", "off_screen", "thought", "mediated"]))
    dialogue["properties"].update(dialogue_id=string(120), delivery_note=string(240))
    if refined(project) and not canonical:
        from .story_exact_lines import for_unit
        lines = for_unit(project, scope(project))
        # Provenance IDs are produced by hydration, never supplied alongside free text.
        dialogue["properties"].pop("dialogue_id")
        if lines:
            reference = obj(speaker_id=characters, line_ref=choice(row["line_id"] for row in lines),
                delivery=choice(["spoken", "voice_over", "off_screen", "thought", "mediated"]))
            reference["properties"]["delivery_note"] = string(240)
            dialogue = {"anyOf": [dialogue, reference]}
    family = story_recipe_spec(project["recipe"]["id"], project["recipe"]["version"])
    fields = dict(title=string(), location_id=string(120), character_ids=array(characters, 0 if refined(project) else 1, 12),
        opening_state=string(), action=string(), dialogue=array(dialogue, 0, 0 if family.get("dialogue_policy") == "forbidden" else 10),
        ending_state=string(), visual_transition=nullable(obj(before=string(1500), trigger=string(1500), visible_change=string(1500), after=string(1500))))
    if project["job"].get("response_contract_version") in {"2.4.0", "2.5.0"}:
        transition = fields["visual_transition"]["anyOf"][0]
        transition["properties"]["timing"] = choice(["within_scene", "between_scenes"])
        transition["required"].append("timing")
    fields.update({field["id"]: string() for field in family["scene_fields"]})
    fields["narrative"] = obj(purpose=choice(["progression", "reaction", "transition"]),
        event_ids=array(choice(e["id"] for e in unit["events"])),
        anchor_scene_index=nullable(dict(type="integer", minimum=0, maximum=fmt["scene_count"] - 1)),
        evidence=string(1500), action_seconds=dict(type="number", minimum=0, maximum=fmt["clip_seconds"]),
        reveals=array(secret, 0, 24 if doc["series_outline"]["secrets"] else 0),
        hints=array(secret, 0, 24 if doc["series_outline"]["secrets"] else 0))
    return obj(**fields)


def outline_edit_targets(project):
    outline = project["document"]["series_outline"]
    targets = {f"outline/{key}": (outline, key) for key in ("title", "premise", "overall_arc", "ending")}
    targets.update({f"contract/{key}": (outline["contract"], key) for key in outline["contract"]})
    if refined(project) and "author_line_assignments" in outline_schema(project)["properties"]:
        targets["outline/author_line_assignments"] = (outline, "author_line_assignments")
    for label, entries in (("character", outline["characters"]), ("unit", outline["episodes"]),
                           ("event", [e for u in outline["episodes"] for e in u["events"]]),
                           ("secret", outline["secrets"]), ("rule", outline["world_rules"])):
        for entry in entries:
            for key in entry:
                if key not in {"id", "events", "beats", "adult"}:
                    targets[f"{label}/{entry['id']}/{key}"] = (entry, key)
    return targets


def review_schema(project, target=None):
    from .long_stories import review_targets
    result = obj(summary=string(6000), issues=array(obj(severity=choice(["blocking", "warning"]),
        target_id=choice(sorted(review_targets(project, target))), problem=string(), suggestion=string()), 0, 5))
    from . import story_direction, story_visual_states
    if story_direction.enabled(project):
        item = result["properties"]["issues"]["items"]
        item["properties"]["category"] = choice(story_direction.REVIEW_CATEGORIES)
        item["required"].append("category")
        from .story_editions import experimental
        if experimental(project):
            language = deepcopy(item)
            language["properties"]["category"] = choice(["dialogue_language"])
            language["properties"]["dialogue_quote"] = string(1500)
            language["required"].append("dialogue_quote")
            result["properties"]["issues"]["items"] = {"anyOf": [item, language]}
    if story_visual_states.enabled(project) and target not in {None, "outline", "ideas"}:
        result["properties"]["visual_patch"] = nullable(story_visual_states.patch_schema(project, target))
    return result


def response_schema(project):
    from .long_stories import scope, source_hash, PROFILES, NARRATIONS, ENDINGS
    operation, target = project["job"]["operation"], scope(project)
    reply = string(12000)
    if operation == "discuss":
        return obj(reply=reply, discussion_only=dict(type="boolean", enum=[True]))
    if operation == "compose":
        resolved = {}
        for key, choices in (("profile", PROFILES), ("narration", NARRATIONS), ("ending_type", sorted(ENDINGS))):
            selected = project["long_options"][key]
            resolved[key] = choice(choices if selected == "auto" else [selected])
        return obj(reply=reply, series_outline=outline_schema(project), resolved_options=obj(**resolved))
    if operation == "edit_outline":
        values = [string(6000), array(string()), {"type": "null"}]
        assignments = outline_schema(project)["properties"].get("author_line_assignments")
        if refined(project) and assignments:
            values.append(assignments)
        return obj(reply=reply, base_hash=choice([source_hash(project, "outline")]),
            edits=array(obj(path=choice(sorted(outline_edit_targets(project))), value={"anyOf": values}), 0, 80),
            review=review_schema(project, "outline"))
    if operation == "review_block":
        identities = project["job"]["review_unit_ids"]
        entries = []
        for identity in identities:
            review = review_schema(project, identity)
            entry = obj(unit_id=choice([identity]), **review["properties"])
            if "visual_patch" in entry["required"]:
                entry["required"].remove("visual_patch")
            entries.append(entry)
        return obj(reply=reply, reviews=array({"anyOf": entries}, len(identities), len(identities)))
    if operation.startswith("review_"):
        return obj(reply=reply, review=review_schema(project, target))
    if target == "outline":
        schema = obj(reply=reply, series_outline=outline_schema(project))
    elif target == "ideas":
        return None  # Legacy one-proposal entry point, outside the structured workflow.
    elif operation == "repair_episode" or (operation == "revise" and project["job"].get("feedback_target", {}).get("scene_index") is not None):
        count = len(project["document"]["episode_scenarios"][target]["scenes"])
        selected = project["job"].get("feedback_target", {}).get("scene_index")
        indices = [selected] if selected is not None else list(range(count))
        schema = obj(reply=reply, base_hash=choice([source_hash(project, target)]),
            scene_edits=array(obj(scene_index=dict(type="integer", enum=indices), scene=scene_schema(project)), 1, count),
            episode_state=state_schema(project))
        if refined(project):
            from .story_exact_lines import memory_unchanged
            schema["properties"]["episode_state"] = ({"type": "null"} if memory_unchanged(project)
                else nullable(state_schema(project)))
    else:
        location = obj(id=string(120), name=string(120), description=string())
        schema = obj(reply=reply, scenario=obj(title=string(), logline=string(), locations=array(location, 1, 8),
            scenes=array(scene_schema(project), 1, project["document"]["episode_formats"][target]["scene_count"])),
            episode_state=state_schema(project))
    if has_continuity(project) and "episode_state" in schema.get("properties", {}):
        from .story_continuity import schema as continuity_schema
        visual = continuity_schema(project["document"]["episode_formats"][target]["scene_count"],
            character_ids=[c["id"] for c in project["document"]["series_outline"]["characters"]] if refined(project) else None)
        if "scene_edits" in schema["properties"]:
            schema["properties"]["visual_continuity"] = visual
        else:
            schema["properties"]["scenario"]["properties"]["visual_continuity"] = visual
    if operation in {"revise", "revise_outline"}:
        return {"anyOf": [schema, obj(reply=reply, discussion_only=dict(type="boolean", enum=[True]))]}
    return schema


def wire_scene(scene, metadata, *, transition_timing=False):
    value = deepcopy(scene)
    value.setdefault("visual_transition", None)
    if transition_timing and value["visual_transition"]:
        value["visual_transition"].setdefault("timing", "within_scene")
    for line in value.get("dialogue", []):
        line.setdefault("delivery", "spoken")
    value["narrative"] = {k: deepcopy(v) for k, v in metadata.items() if k != "scene_index"}
    value["narrative"].setdefault("purpose", "progression")
    value["narrative"].setdefault("anchor_scene_index", None)
    value["narrative"].setdefault("hints", [])
    return value


def wire_example(project, example):
    from .long_stories import source_hash, scope
    operation, target = project["job"]["operation"], scope(project)
    if operation == "edit_outline":
        return dict(reply="Bilan des changements utiles.", base_hash=source_hash(project, "outline"),
                    edits=[], review=dict(summary="Évaluation du résultat, justifiée par les passages examinés.", issues=[]))
    if operation == "repair_episode" or (operation == "revise" and project["job"].get("feedback_target", {}).get("scene_index") is not None):
        index = project["job"].get("feedback_target", {}).get("scene_index") or 0
        doc = project["document"]
        scene = wire_scene(doc["episode_scenarios"][target]["scenes"][index], doc["episode_states"][target]["scene_events"][index],
                           transition_timing=project["job"].get("response_contract_version") in {"2.4.0", "2.5.0"})
        state = {k: deepcopy(v) for k, v in doc["episode_states"][target].items() if k != "scene_events"}
        if refined(project):
            state = None
            for line in scene["dialogue"]:
                identity = line.pop("dialogue_id", None)
                if identity and identity.startswith("author-line-"):
                    line.pop("text", None)
                    line["line_ref"] = identity
        result = dict(reply="Corrections ciblées.", base_hash=source_hash(project, target),
                      scene_edits=[dict(scene_index=index, scene=scene)], episode_state=state)
        if has_continuity(project):
            result["visual_continuity"] = deepcopy(doc["episode_scenarios"][target].get("visual_continuity", {
                "version": 1, "dramatic_summary": "Ce que le public doit comprendre ; ce que le héros ignore.", "elements": []}))
        return result
    result = deepcopy(example)
    from . import story_visual_states
    if story_visual_states.enabled(project):
        for review in result.get("reviews", []):
            review["visual_patch"] = None
        if "review" in result and target not in {"outline", "ideas"}:
            result["review"]["visual_patch"] = None
    if "scenario" in result and "episode_state" in result:
        result["scenario"].pop("characters", None)
        metadata = result["episode_state"].pop("scene_events")
        result["scenario"]["scenes"] = [wire_scene(scene, metadata[i],
            transition_timing=project["job"].get("response_contract_version") in {"2.4.0", "2.5.0"})
            for i, scene in enumerate(result["scenario"]["scenes"])]
        if has_continuity(project):
            result["scenario"].setdefault("visual_continuity", dict(version=1, dramatic_summary="Le drame compréhensible à l'écran.", elements=[]))
    return result


def canonical_response(project, value):
    """Adapt new responses to the existing storage/fabrication shape, atomically."""
    from .long_stories import scope, source_hash
    result = deepcopy(value)
    target = scope(project)
    if "edits" in result:
        if result["base_hash"] != source_hash(project, "outline"):
            raise StoryValidationError([issue("stale_patch", "base_hash", "La version de base a changé.")])
        candidate = deepcopy(project)
        targets = outline_edit_targets(candidate)
        seen = set()
        for edit in result.pop("edits"):
            path = edit["path"]
            if path not in targets or path in seen:
                raise StoryValidationError([issue("patch_path", path, "Cible inconnue ou modifiée deux fois.")])
            seen.add(path)
            holder, key = targets[path]
            holder[key] = deepcopy(edit["value"])
        result.pop("base_hash")
        result["series_outline"] = candidate["document"]["series_outline"]
        for unit in result["series_outline"]["episodes"]:
            unit.pop("beats", None)
    if "scene_edits" in result:
        if result["base_hash"] != source_hash(project, target):
            raise StoryValidationError([issue("stale_patch", "base_hash", "La version de base a changé.")])
        scenario = deepcopy(project["document"]["episode_scenarios"][target])
        if "visual_continuity" in result:
            scenario["visual_continuity"] = result.pop("visual_continuity")
        metadata = deepcopy(project["document"]["episode_states"][target]["scene_events"])
        seen = set()
        for edit in result.pop("scene_edits"):
            index = edit["scene_index"]
            if index in seen or not 0 <= index < len(scenario["scenes"]):
                raise StoryValidationError([issue("patch_scene", "scene_edits", "Scène inconnue ou modifiée deux fois.")])
            seen.add(index)
            changed = deepcopy(edit["scene"])
            metadata[index] = dict(scene_index=index, **changed.pop("narrative"))
            scenario["scenes"][index] = changed
        result.pop("base_hash")
        result["scenario"] = scenario
        if refined(project):
            from .story_exact_lines import memory_unchanged
            if result.get("episode_state") is None or memory_unchanged(project):
                result["episode_state"] = deepcopy(project["document"]["episode_states"][target])
        result["episode_state"]["scene_events"] = metadata
        if refined(project):
            from .story_exact_lines import hydrate
            result["scenario"]["presence_policy"] = 1
            result["scenario"] = hydrate(project, result["scenario"], result["episode_state"], target)
        return result  # Preserve the existing cast and every untouched scene exactly.
    if "scenario" in result and any("narrative" in scene for scene in result["scenario"].get("scenes", [])):
        result["scenario"]["characters"] = deepcopy(project["document"]["series_outline"]["characters"])
        result["episode_state"]["scene_events"] = [dict(scene_index=i, **scene.pop("narrative"))
            for i, scene in enumerate(result["scenario"]["scenes"])]
    if "scenario" in result and refined(project):
        from .story_exact_lines import hydrate
        result["scenario"]["presence_policy"] = 1
        result["scenario"] = hydrate(project, result["scenario"], result["episode_state"], target)
    if "scenario" in result and has_continuity(project):
        from .long_stories import previous_ids
        from .story_continuity import carry_forward, inherit, inherit_independent, empty, normalize
        doc = project["document"]
        previous = previous_ids(project, target)
        inherited = carry_forward(doc["episode_scenarios"][previous[-1]],
            require_references=project.get("visual_state_policy") in {1, 2}) if previous else doc.get("visual_state_inherited")
        result["scenario"].setdefault("visual_continuity", empty())
        try:
            merger = inherit_independent if refined(project) else inherit
            merged = merger(result["scenario"], inherited)
            merged["visual_continuity"] = normalize(merged["visual_continuity"], merged)
        except (ValueError, TypeError, KeyError) as error:
            # A prior object's owner may be absent from a new cast, for example.
            # Keep the writer's valid current ledger and expose the unresolved
            # inheritance rather than reject the new playable episode.
            try:
                current = normalize(result["scenario"]["visual_continuity"], result["scenario"])
            except ValueError:
                current = empty()
            current["warnings"] = (current.get("warnings", []) + [
                "La mémoire visuelle précédente n'a pas pu être reprise entièrement : " + str(error)[:2000]
                + " Vérifie les états de départ dans Continuité."])[-4:]
            result["scenario"]["visual_continuity"] = current
        else:
            result["scenario"] = merged
    return result
