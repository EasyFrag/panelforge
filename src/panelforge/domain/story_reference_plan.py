"""Sparse image requirements for policy 2; the authored timeline stays intact.

An image identifies an appearance, not a scene boundary. Equality is deliberately
conservative: same entity and same resolved body/outfit, ignoring case/spacing.
We never guess that two different descriptions or two people are equivalent.
"""
from copy import deepcopy
import hashlib
import json
import unicodedata

from . import story_continuity as ledger


def appearance(state):
    return {key: state.get(key) for key in ("appearance", "clothing")}


def appearance_key(state):
    return tuple(" ".join(unicodedata.normalize("NFC", state.get(key) or "").casefold().split())
                 for key in ("appearance", "clothing"))


def inheritance_appearance_key(state):
    """Typography only, for inheritance. Never change appearance_key or media IDs."""
    table = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "“": '"', "”": '"'})
    return tuple(part.translate(table) for part in appearance_key(state))


def image_id(element_id, state):
    digest = hashlib.sha256(json.dumps([element_id, appearance_key(state)],
        ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:20]
    return "appearance-" + digest


def identity_description(description, state):
    label = ledger.state_description(appearance(state), [])
    if not label:
        return description
    return (description + "\nAPPARENCE DE CETTE IMAGE, À LA PREMIÈRE APPARITION : " + label
        + ". Cet état prime sur toute évolution évoquée dans la description. "
          "Une seule apparence, sans montrer ni anticiper une transformation.")


def build(scenario):
    identities, references, bindings = {}, [], {}
    for element in ledger.elements(scenario):
        visible = sorted(set(element["scene_indices"]))
        if not visible:
            continue
        first = visible[0]
        baseline = ledger.state_at(element, first)
        identities[element["id"]] = dict(state=appearance(baseline), scene_index=first,
            description=identity_description(element["description"], baseline))
        if element["tracking"] != "reference":
            continue
        base_id = ledger.reference_id(element["id"]) if element["kind"] == "object" else None
        if element["kind"] == "object":
            references.append(dict(id=base_id, source_id=element["id"], kind="object", name=element["name"],
                description=identities[element["id"]]["description"], continuity_element_id=element["id"],
                continuity_state_id=None, continuity_appearance=appearance(baseline)))
        states = {}
        representatives = {}
        for change in element["states"]:
            if not change["reference"]:
                continue
            resolved = ledger.state_at(element, change["scene_index"], end=change["at"] == "end")
            key = appearance_key(resolved)
            target = base_id if key == appearance_key(baseline) else image_id(element["id"], resolved)
            states[change["id"]] = target
            representatives.setdefault(target, (change, resolved))
        used = set()
        for index in visible:
            current = ledger.state_at(element, index)
            anchor = current["reference_state_id"]
            # An explicit return to the initial appearance reuses the identity.
            target = base_id if appearance_key(current) == appearance_key(baseline) else states.get(anchor, base_id)
            bindings[(element["id"], index)] = target
            if target != base_id:
                used.add(target)
        for target, (change, resolved) in representatives.items():
            if target not in used:
                continue  # End states remain in memory; no unused image job now.
            label = ledger.state_description(appearance(resolved), [])
            references.append(dict(id=target, source_id=element["id"], kind=element["kind"],
                name=(element["name"] + " · " + (label or "variante"))[:120],
                description="Même identité que l'image source. Apparence demandée : " + label,
                continuity_element_id=element["id"], continuity_state_id=change["id"],
                continuity_appearance=appearance(resolved)))
    return dict(identities=identities, references=references, bindings=bindings)


def reader_projection(scenario):
    """Give the reader resolved visible states, not a persistence puzzle."""
    plan = build(scenario)
    return dict(identity_states=[dict(element_id=identity, scene_index=value["scene_index"], state=deepcopy(value["state"]))
                for identity, value in plan["identities"].items()],
        scene_states=[dict(scene_index=index, element_id=row["element_id"],
            start=appearance(row["before"]), end=appearance(row["after"]))
            for index in range(len(scenario["scenes"]))
            for row in ledger.scene_rows(scenario, index, explicit_presence=True)])
