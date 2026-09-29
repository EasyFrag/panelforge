"""Small, versioned visual ledger. No model calls and no media dependencies."""
from copy import deepcopy
import hashlib
import re


VERSION = 1
ATTRIBUTES = ("appearance", "clothing", "holder_id")


def empty():
    return dict(version=VERSION, dramatic_summary="", elements=[])


def schema(scene_count=18, *, character_ids=None):
    # Optional at the scenario boundary, complete when supplied by a writer.
    def obj(**properties):
        return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)
    def string(maximum=1500):
        return dict(type="string", minLength=1, maxLength=maximum)
    def nullable(value):
        return {"anyOf": [value, {"type": "null"}]}
    state = obj(id=string(120), scene_index=dict(type="integer", minimum=0, maximum=scene_count - 1),
                at=dict(type="string", enum=["start", "end"]), appearance=nullable(string()),
                clothing=nullable(string()), holder_id=nullable(string(120)), reference=dict(type="boolean"))
    element = obj(id=string(120), kind=dict(type="string", enum=["character", "object"]),
                  name=string(120), description=string(3000), reason=string(),
                  tracking=dict(type="string", enum=["text", "reference"]),
                  scene_indices=dict(type="array", items=dict(type="integer", minimum=0, maximum=scene_count - 1), maxItems=18),
                  states=dict(type="array", items=state, minItems=1, maxItems=scene_count * 2))
    element["properties"]["enabled"] = dict(type="boolean")
    if character_ids is not None:
        state["properties"]["holder_id"] = nullable(dict(type="string", enum=[*character_ids, "none"]))
        person, prop = deepcopy(element), deepcopy(element)
        person["properties"]["kind"] = dict(type="string", enum=["character"])
        person["properties"]["id"] = dict(type="string", enum=list(character_ids))
        prop["properties"]["kind"] = dict(type="string", enum=["object"])
        element = {"anyOf": [person, prop]}
    result = obj(version=dict(type="integer", enum=[VERSION]),
               dramatic_summary=dict(type="string", maxLength=1500),
               elements=dict(type="array", items=element, maxItems=24))
    result["properties"]["warnings"] = dict(type="array", items=string(3000), maxItems=4)
    return result


def isolate_optional_ledger(project, response):
    """A bad visual appendix must not discard playable writing or trigger a repair loop.

    The exact received appendix remains in the job's original draft. The caller
    retains the previous valid ledger (local edit) or inherited baseline (write).
    Author edits use normalize directly and must resolve their invalid entries.
    """
    container = response.get("scenario") if "scenario" in response else response if "scene_edits" in response else None
    if not isinstance(container, dict) or "visual_continuity" not in container:
        return None
    doc = project["document"]
    outline = doc.get("series_outline")
    if not isinstance(outline, dict) or not isinstance(outline.get("characters"), list):
        return None  # Let the operation's primary contract report a wrong response.
    target = (project.get("job", {}).get("feedback_target") or {}).get("unit_id") or doc.get("selected_episode_id")
    scenes = (container.get("scenes") if "scenario" in response else
              doc.get("episode_scenarios", {}).get(target, {}).get("scenes"))
    if not isinstance(scenes, list) or not scenes:
        return None  # The primary structural diagnostics handle malformed scenes.
    source = dict(scenes=scenes, characters=outline["characters"])
    from .story_editions import refined
    if refined(project):
        previous = doc.get("episode_scenarios", {}).get(target, {}).get("visual_continuity") if "scene_edits" in response else None
        container["visual_continuity"], warning = salvage(container["visual_continuity"], source, previous)
        return warning
    try:
        container["visual_continuity"] = normalize(container["visual_continuity"], source)
    except ValueError as error:
        container.pop("visual_continuity")
        return ("Le suivi visuel proposé doit être corrigé dans Continuité : " + str(error)[:2000]
                + " Le scénario est conservé ; l'annexe originale reste dans le brouillon reçu. Aucun état invalide n'a été appliqué.")
    return None


def salvage(value, scenario, previous=None):
    """Keep independently valid elements; reject ambiguous IDs, never guess holders.

    A local repair merges replacements into the last valid ledger. Invalid
    replacements leave that existing element untouched. Raw input is kept by
    the caller in the received draft, including every rejected element.
    """
    from collections import Counter
    from .story_contracts import structural_issues
    base = deepcopy(previous) if previous else empty()
    known = {e["id"]: e for e in base["elements"]}
    rejected = []
    header = deepcopy(value) if isinstance(value, dict) else {}
    entries = header.get("elements")
    header["elements"] = []
    if not isinstance(entries, list) or structural_issues(header, schema(len(scenario["scenes"]))):
        rejected.append("annexe mal formée")
        entries = []
    else:
        base["dramatic_summary"] = header["dramatic_summary"]
    ids = Counter(e.get("id") for e in entries if isinstance(e, dict) and isinstance(e.get("id"), str))
    for entry in entries:
        identity = entry.get("id") if isinstance(entry, dict) else None
        try:
            if not isinstance(identity, str) or ids[identity] != 1:
                raise ValueError("identifiant absent ou ambigu")
            candidate = normalize(dict(version=VERSION, dramatic_summary="", elements=[entry]), scenario)["elements"][0]
            old = known.get(identity)
            if old and (old["kind"] != candidate["kind"] or not old.get("enabled", True)):
                raise ValueError("identité ou désactivation précédente à préserver")
            if identity not in known and len(known) >= 24:
                raise ValueError("limite des éléments dépassée")
            known[identity] = candidate
        except (ValueError, TypeError, KeyError) as error:
            rejected.append(f"{identity if isinstance(identity, str) else 'élément'} : {error}")
    base["elements"] = list(known.values())
    warning = None
    if rejected:
        warning = ("Continuité partiellement conservée : " + "; ".join(rejected))[:2100]
        warning += ". Éléments indépendants valides conservés ; originaux dans le brouillon reçu. Vérifie Continuité."
        base["warnings"] = (base.get("warnings", []) + [warning])[-4:]
    return normalize(base, scenario), warning


def normalize(value, scenario):
    """Validate edits without inferring new appearances or merging distinct objects."""
    if value is None:
        return empty()
    from .story_contracts import structural_issues
    issues = structural_issues(value, schema(len(scenario["scenes"])))
    if issues:
        raise ValueError("Continuité : " + "; ".join(x["message"] for x in issues[:5]))
    result = deepcopy(value)
    characters = {c["id"]: c for c in scenario["characters"]}
    used = set()
    for element in result["elements"]:
        identity = element["id"]
        if identity in used:
            raise ValueError("Un élément de continuité est présent deux fois.")
        used.add(identity)
        if element["kind"] == "character":
            if identity not in characters:
                raise ValueError(f"Personnage de continuité inconnu : {element['name']}.")
            element["name"] = characters[identity]["name"]
        elif identity in characters:
            raise ValueError("Un objet doit avoir son propre identifiant, distinct des personnages.")
        element["scene_indices"] = sorted(set(element["scene_indices"]))
        ids, boundaries = set(), set()
        for state in element["states"]:
            boundary = (state["scene_index"], state["at"])
            if state["id"] in ids or boundary in boundaries:
                raise ValueError(f"Deux états de {element['name']} désignent la même étape.")
            ids.add(state["id"])
            boundaries.add(boundary)
            if state["holder_id"] is not None and state["holder_id"] not in characters and state["holder_id"] != "none":
                raise ValueError(f"Détenteur inconnu pour {element['name']}. Utilisez un personnage ou none.")
        element["states"].sort(key=lambda x: (x["scene_index"], x["at"] == "end"))
    return result


def elements(scenario):
    return [e for e in (scenario.get("visual_continuity") or {}).get("elements", []) if e.get("enabled", True)]


def state_at(element, index, *, end=False):
    """Null means unchanged. Clothing therefore survives a later body-only change."""
    result = dict(appearance=None, clothing=None, holder_id=None, reference_state_id=None)
    for change in element["states"]:
        if change["scene_index"] > index or (change["scene_index"] == index and change["at"] == "end" and not end):
            continue
        for key in ATTRIBUTES:
            if change.get(key) is not None:
                result[key] = change[key]
        # Keep the closest established visual anchor for minor textual changes.
        # Falling back to the original frail body merely because a later scene
        # mentions broader shoulders would recreate the visual reset we avoid.
        if change.get("reference") and element["tracking"] == "reference":
            result["reference_state_id"] = change["id"]
    return result


def present_ids(scenario, index):
    """Explicit presence includes tracked silent participants; dialogue is not evidence of presence."""
    scene = scenario["scenes"][index]
    ids = list(scene["character_ids"])
    for e in elements(scenario):
        if e["kind"] == "character" and index in e["scene_indices"] and e["id"] not in ids:
            ids.append(e["id"])
    return ids


def missing_mentions(scenario, index):
    """A diagnostic, never a guessed cast mutation (names can describe absent people)."""
    scene = scenario["scenes"][index]
    prose = scene["opening_state"] + "\n" + scene["action"]
    return [c for c in scenario["characters"] if c["id"] not in present_ids(scenario, index)
            and re.search(r"(?<!\w)" + re.escape(c["name"]) + r"(?!\w)", prose, re.I)]


def state_description(state, characters):
    names = {c["id"]: c["name"] for c in characters}
    parts = [state.get("appearance"), state.get("clothing")]
    holder = state.get("holder_id")
    if holder:
        parts.append("Sans détenteur" if holder == "none" else "Détenu par " + names.get(holder, holder))
    return " · ".join(p for p in parts if p)


def scene_rows(scenario, index, *, explicit_presence=False):
    rows = []
    for e in elements(scenario):
        if index not in e["scene_indices"] and (explicit_presence or not (e["kind"] == "character" and e["id"] in present_ids(scenario, index))):
            continue
        before, after = state_at(e, index), state_at(e, index, end=True)
        rows.append(dict(element_id=e["id"], name=e["name"], kind=e["kind"], reason=e["reason"],
                         description=e["description"], tracking=e["tracking"], before=before, after=after,
                         start=state_description(before, scenario["characters"]),
                         end=state_description(after, scenario["characters"])))
    return rows


def reference_id(element_id, state_id=None):
    digest = hashlib.sha256((element_id + "\0" + (state_id or "identity")).encode()).hexdigest()[:20]
    return "continuity-" + digest


def reference_specs(scenario):
    """Only explicit visual anchors create media tasks; text-only objects cost nothing."""
    result = []
    for e in elements(scenario):
        if e["tracking"] != "reference":
            continue
        if e["kind"] == "object":
            result.append(dict(id=reference_id(e["id"]), source_id=e["id"], kind="object",
                               name=e["name"], description=e["description"], continuity_element_id=e["id"],
                               continuity_state_id=None))
        for change in e["states"]:
            if not change["reference"]:
                continue
            resolved = state_at(e, change["scene_index"], end=change["at"] == "end")
            label = state_description(resolved, scenario["characters"])
            result.append(dict(id=reference_id(e["id"], change["id"]), source_id=e["id"], kind=e["kind"],
                name=(e["name"] + " · " + (label or "variante"))[:120],
                description=e["description"] + "\nApparence de cette variante : " + label,
                continuity_element_id=e["id"], continuity_state_id=change["id"]))
    return result


def instructions(scenario, index, *, explicit_presence=False):
    rows = scene_rows(scenario, index, explicit_presence=explicit_presence)
    if not rows:
        return ""
    lines = ["CONTINUITÉ VISUELLE — états acquis, prioritaires sur l'apparence initiale des images :"]
    for row in rows:
        lines.append(f"{row['name']} — identité : {row['description']}")
        if row["start"]:
            lines.append("Au début, déjà acquis : " + row["start"] + ". Ne rejoue pas cette acquisition.")
        if row["start"] != row["end"]:
            lines.append("Changement raconté dans ce clip, état à la fin : " + row["end"])
        else:
            lines.append("Conserver cet état pendant tout le clip.")
    lines.append("La forme physique, la tenue et le détenteur sont indépendants : aucun retour à l'état initial sans transition racontée.")
    return "\n".join(lines)


def reader_view(scenario, *, include_transitions=False):
    """Remove privileged knowledge. The reviewer sees only playable material."""
    result = dict(characters=[dict(id=c["id"], name=c["name"]) for c in scenario["characters"]],
        scenes=[dict(scene_index=i, character_ids=s["character_ids"], location_id=s["location_id"],
                     opening_state=s["opening_state"], action=s["action"].split("\nInformation indispensable")[0],
                     dialogue=deepcopy(s["dialogue"])) for i, s in enumerate(scenario["scenes"])])
    if include_transitions:
        for row, scene in zip(result["scenes"], scenario["scenes"]):
            row["visual_transition"] = deepcopy(scene.get("visual_transition"))
    return result


def carry_forward(scenario, *, require_references=False):
    """Carry the ledger at the last written boundary, never its earlier variants."""
    if not scenario.get("visual_continuity"):
        return None
    result = empty()
    for element in elements(scenario):
        e = deepcopy(element)
        state = state_at(e, len(scenario["scenes"]) - 1, end=True)
        e["scene_indices"] = []
        inherited_id = "inherited-" + hashlib.sha256(e["id"].encode()).hexdigest()[:16]
        e["states"] = [dict(id=inherited_id, scene_index=0,
            at="start", **{k: state[k] for k in ATTRIBUTES},
            reference=bool(require_references and state["reference_state_id"]))]
        result["elements"].append(e)
    return result


def inherit_independent(scenario, previous):
    """V3: a conflicting inherited entity cannot discard unrelated valid memory."""
    result = deepcopy(scenario)
    if not previous:
        return result
    for old in previous["elements"]:
        try:
            merged = inherit(result, dict(elements=[old]))
            merged["visual_continuity"] = normalize(merged["visual_continuity"], merged)
            result = merged
        except (ValueError, TypeError, KeyError) as error:
            visual = result.setdefault("visual_continuity", empty())
            warning = f"Héritage de {old.get('name', 'cet élément')} à vérifier : {error}. État courant conservé."
            visual["warnings"] = (visual.get("warnings", []) + [warning[:2500]])[-4:]
    return result


def inherit(scenario, previous):
    """Fill unchanged attributes from the previous unit; never invent a transition."""
    if not previous:
        return scenario
    result = deepcopy(scenario)
    current = result.setdefault("visual_continuity", empty())
    known = {e["id"]: e for e in current["elements"]}
    character_ids = {c["id"] for c in scenario["characters"]}
    for old in previous["elements"]:
        if old["kind"] == "character" and old["id"] not in character_ids:
            continue
        baseline = deepcopy(old["states"][0])
        entry = known.get(old["id"])
        if entry is None:
            entry = deepcopy(old)
            entry["scene_indices"] = [i for i, s in enumerate(scenario["scenes"]) if old["id"] in s["character_ids"]]
            current["elements"].append(entry)
            continue
        if entry["kind"] != old["kind"]:
            raise ValueError("L'identité d'un élément de continuité ne peut pas changer de type.")
        inherited = [s for s in entry["states"] if s["id"] == baseline["id"]]
        if len(inherited) > 1:
            raise ValueError("Un état hérité est présent plusieurs fois.")
        visible = sorted(set(entry["scene_indices"]) | {i for i, scene in enumerate(scenario["scenes"])
                                                     if entry["id"] in scene["character_ids"]})
        first = visible[0] if visible else 0
        opening = inherited[0] if inherited else next((s for s in entry["states"]
            if s["scene_index"] <= first and s["at"] == "start"), None)
        if inherited:
            from .story_reference_plan import inheritance_appearance_key
            filled = {k: opening.get(k) if opening.get(k) is not None else baseline.get(k) for k in ATTRIBUTES}
            if (opening["at"] != "start" or inheritance_appearance_key(filled) != inheritance_appearance_key(baseline)
                    or filled["holder_id"] != baseline.get("holder_id")):
                raise ValueError("Un ID hérité décrit des états contradictoires ; utilise un nouvel ID pour une transition.")
        if opening:
            for key in ATTRIBUTES:
                if opening.get(key) is None:
                    opening[key] = baseline.get(key)
            from .story_reference_plan import inheritance_appearance_key
            same_appearance = inheritance_appearance_key(opening) == inheritance_appearance_key(baseline)
            if same_appearance:
                for key in ("appearance", "clothing"):
                    opening[key] = baseline.get(key)
            if baseline.get("reference") and same_appearance:
                opening["reference"] = True
                entry["tracking"] = "reference"
        else:
            earliest = min(s["scene_index"] for s in entry["states"])
            baseline["scene_index"] = min(first, earliest)
            entry["states"].insert(0, baseline)
    return result
