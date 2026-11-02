"""Versioned objects and repeatable variety preferences, without scene recipes.

Object groups are editorial shelves, not mechanism or problem assignments.
Only saved structured choices count as usage; no prose classification is guessed.
"""
from collections import Counter
import hashlib
import json

from .little_men_objects import (
    CATALOG_VERSION, LEGACY_CATALOG_VERSION, LEGACY_OBJECT_ROWS, LEGACY_OBJECTS,
    OBJECTS, catalog_for, normalize_object_name,
)
from .little_men_variety_history import bootstrap_history, summarize_history


PRESET_ID = "little_men_variety"
SELECTION_MARKER = "\n\nVARIETY SELECTION \u2014 PLAN ONLY:\n"
ASSORTMENT_SIZE = 12
RECENT_LIMIT = 50
RECENT_PAIR_LIMIT = 12
# Kept for callers auditing the original catalogue. New data lives in the
# explicitly versioned object module rather than altering historical rows.
_OBJECT_ROWS = LEGACY_OBJECT_ROWS

MECHANISM_FAMILIES = {
    "link": "Connect or join",
    "separate": "Separate or cut",
    "move": "Move or transport",
    "redirect": "Redirect a course or flow",
    "absorb_remove": "Capture, absorb or extract",
    "reshape": "Deform or reshape",
    "temperature": "Change temperature",
    "support": "Support or stabilize",
    "contain": "Confine or contain",
    "shield": "Interpose a screen",
    "other": "Other physical operation",
}
MECHANISM_LABELS = {
    "link": "Relier / assembler",
    "separate": "Séparer / couper",
    "move": "Déplacer / transporter",
    "redirect": "Dévier / détourner",
    "absorb_remove": "Capter / absorber / extraire",
    "reshape": "Déformer / remodeler",
    "temperature": "Modifier la température",
    "support": "Soutenir / stabiliser",
    "contain": "Confiner / contenir",
    "shield": "Faire écran",
    "other": "Autre opération",
}


def is_variety(config):
    return (config.get("preset_origin") or config.get("preset")) == PRESET_ID


def _resolved_choice(item, selection):
    choice = selection.get("variety_choice")
    if isinstance(choice, dict):
        return choice
    step = item.get("steps", {}).get("plan", {})
    if step.get("status") != "succeeded":
        return None
    try:
        plan = json.loads(step.get("output", {}).get("text", "{}"))
        choice = plan.get("variety_choice") if isinstance(plan, dict) else None
        return choice if isinstance(choice, dict) else None
    except (TypeError, ValueError, AttributeError):
        return None


def _recent_usage(items, exclude):
    objects, exposure, mechanisms = Counter(), Counter(), Counter()
    seen = set()
    relevant = 0
    for item in sorted(items, key=lambda value: value.get("updated_at", ""), reverse=True):
        identity = item.get("id")
        if not identity or identity == exclude or identity in seen or not is_variety(item.get("config", {})):
            continue
        seen.add(identity)
        selection = item.get("runtime", {}).get("thanks_selection") or {}
        if not isinstance(selection, dict):
            continue
        choice = _resolved_choice(item, selection)
        if choice is not None:
            declared = choice.get("objects", ())
            if isinstance(declared, (list, tuple)):
                objects.update({value["catalog_id"] for value in declared if isinstance(value, dict)
                                and isinstance(value.get("catalog_id"), str) and value["catalog_id"] in LEGACY_OBJECTS})
            family = choice.get("mechanism_family")
            if isinstance(family, str) and family in MECHANISM_FAMILIES:
                mechanisms[family] += 1
        else:
            frozen = selection.get("variety")
            if not isinstance(frozen, dict):
                continue
            try:
                validate_selection(frozen)
            except ValueError:
                continue
            # Candidate exposure is provisional. A resolved Plan counts only its
            # chosen objects; unused suggestions do not become permanent usage.
            exposure.update(frozen["candidates"])
        relevant += 1
        if relevant >= RECENT_LIMIT:
            break
    return objects, exposure, mechanisms


def _tie(identity, candidate, catalog_version=LEGACY_CATALOG_VERSION):
    return hashlib.sha256(f"{catalog_version}:{identity}:{candidate}".encode()).hexdigest()


def _legacy_selection(identity, items, exclude):
    """Keep the original shelf-based ordering for historical directions."""
    objects, exposure, mechanisms = _recent_usage(items, identity if exclude is None else exclude)
    candidates, groups = [], Counter()
    for _ in range(ASSORTMENT_SIZE):
        chosen = min((key for key in LEGACY_OBJECTS if key not in candidates), key=lambda key: (
            groups[LEGACY_OBJECTS[key]["group"]], objects[key] * 8 + exposure[key], _tie(identity, key)))
        candidates.append(chosen)
        groups[LEGACY_OBJECTS[chosen]["group"]] += 1
    return dict(catalog_version=LEGACY_CATALOG_VERSION, candidates=candidates,
                mechanism_counts={family: mechanisms[family] for family in MECHANISM_FAMILIES},
                mechanism_priority=sorted(MECHANISM_FAMILIES,
                    key=lambda family: (family == "other", mechanisms[family], _tie(identity, family))))


def make_variety_selection(identity, items, exclude=None, *, history=None,
                           catalog_version=CATALOG_VERSION):
    """Freeze twelve diverse possibilities, never prescribed scene solutions.

    Trait coverage, declared use and exposure have soft weights; the editorial
    shelf is secondary. The caller persists this result before another request.
    Explicit legacy reservations retain their original ordering and payload.
    """
    if catalog_version == LEGACY_CATALOG_VERSION:
        return _legacy_selection(identity, items, exclude)
    catalogue = catalog_for(catalog_version)
    if catalog_version != CATALOG_VERSION:
        raise ValueError("Version du catalogue Petits hommes inconnue.")
    journal = bootstrap_history(items) if history is None else history
    usage = summarize_history(journal, exclude_item_id=identity if exclude is None else exclude)
    objects, exposure = usage["object_counts"], usage["exposure_counts"]
    mechanisms = usage["mechanism_counts"]
    candidates, traits, groups = [], Counter(), Counter()

    def rank(key):
        descriptor = catalogue[key]
        distinct = descriptor["traits"]
        coverage = sum(1 / (1 + traits[trait]) for trait in distinct) / len(distinct)
        # A bounded, reproducible exploration term avoids a single universal
        # assortment. It neither mandates a shelf nor overrides heavy reuse.
        exploration = int(_tie(identity, key, catalog_version)[:8], 16) / 0xFFFFFFFF
        score = (6 * coverage + 1.5 * exploration
                 - 8 * objects.get(key, 0) - 0.5 * exposure.get(key, 0)
                 - 0.2 * groups[descriptor["group"]])
        return -score, _tie(identity, key, catalog_version)

    for _ in range(ASSORTMENT_SIZE):
        chosen = min((key for key in catalogue if key not in candidates), key=rank)
        candidates.append(chosen)
        traits.update(catalogue[chosen]["traits"])
        groups[catalogue[chosen]["group"]] += 1
    result = dict(
        catalog_version=catalog_version, candidates=candidates,
        mechanism_counts={family: mechanisms.get(family, 0) for family in MECHANISM_FAMILIES},
        mechanism_priority=sorted(MECHANISM_FAMILIES, key=lambda family: (
            family == "other", mechanisms.get(family, 0), _tie(identity, family, catalog_version))),
        recent_pairs=[dict(pair) for pair in usage["recent_pairs"][:RECENT_PAIR_LIMIT]],
    )
    validate_selection(result)
    return result


def validate_selection(selection):
    error = "Assortiment Petits hommes experimental invalide ou incompatible ; repréparez le Plan."
    if not isinstance(selection, dict):
        raise ValueError(error)
    version = selection.get("catalog_version")
    if version not in (LEGACY_CATALOG_VERSION, CATALOG_VERSION):
        raise ValueError(error)
    expected = {"catalog_version", "candidates", "mechanism_counts", "mechanism_priority"}
    if version == CATALOG_VERSION:
        expected.add("recent_pairs")
    if set(selection) != expected:
        raise ValueError(error)
    catalogue = catalog_for(version)
    candidates = selection.get("candidates")
    if (not isinstance(candidates, list) or len(candidates) != ASSORTMENT_SIZE
            or any(not isinstance(value, str) or value not in catalogue for value in candidates)
            or len(set(candidates)) != len(candidates)):
        raise ValueError(error)
    counts, priority = selection.get("mechanism_counts"), selection.get("mechanism_priority")
    if (not isinstance(counts, dict) or set(counts) != set(MECHANISM_FAMILIES)
            or any(type(value) is not int or not 0 <= value <= RECENT_LIMIT for value in counts.values())
            or sum(counts.values()) > RECENT_LIMIT
            or not isinstance(priority, list) or len(priority) != len(MECHANISM_FAMILIES)
            or any(not isinstance(value, str) for value in priority)
            or set(priority) != set(MECHANISM_FAMILIES)):
        raise ValueError(error)
    if version == CATALOG_VERSION:
        _validate_recent_pairs(selection["recent_pairs"], counts, error)


def _validate_recent_pairs(pairs, mechanisms, error):
    if not isinstance(pairs, list) or len(pairs) > RECENT_PAIR_LIMIT:
        raise ValueError(error)
    seen = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"object_key", "name", "mechanism_family", "count"}:
            raise ValueError(error)
        key, name, family, count = (pair[field] for field in
                                   ("object_key", "name", "mechanism_family", "count"))
        if (not isinstance(key, str) or not isinstance(name, str) or not 1 <= len(name) <= 120
                or any(ord(char) < 32 for char in name)
                or not isinstance(family, str) or family not in MECHANISM_FAMILIES
                or type(count) is not int or not 1 <= count <= mechanisms[family]):
            raise ValueError(error)
        if key in OBJECTS:
            if name != OBJECTS[key]["name"]:
                raise ValueError(error)
        elif key == "__hand__":
            if name != "direct hand action":
                raise ValueError(error)
        elif not normalize_object_name(name) or key != "external:" + normalize_object_name(name):
            raise ValueError(error)
        if (key, family) in seen:
            raise ValueError(error)
        seen.add((key, family))


def selection_from_text(text):
    if not isinstance(text, str) or SELECTION_MARKER not in text:
        raise ValueError("Assortiment Petits hommes experimental absent de la préparation.")
    try:
        selection = json.loads(text.rsplit(SELECTION_MARKER, 1)[1].splitlines()[0])
    except (ValueError, IndexError) as error:
        raise ValueError("Assortiment Petits hommes experimental illisible.") from error
    validate_selection(selection)
    return selection


def selection_instructions(selection):
    validate_selection(selection)
    catalogue = catalog_for(selection["catalog_version"])
    objects = "\n".join(f"- {identity}: {catalogue[identity]['name']}" for identity in selection["candidates"])
    mechanisms = "; ".join(f"{family} ({MECHANISM_FAMILIES[family]}): {selection['mechanism_counts'][family]}"
                           for family in selection["mechanism_priority"])
    return (
        "OBJECT ASSORTMENT AND MECHANISM MEMORY — PLAN ONLY\n"
        "Identify the principal danger and its target from the actual scene before choosing an intervention. "
        "First consider the supplied objects for a coherent, readable solution. Object names are invitations "
        "to adapt their physical properties, never prescribed answers to a problem. The assortment has no "
        "object-to-mechanism assignments. Accessories remain optional. If the assortment is unsuitable or "
        "direct hand action works more clearly, choose another object or no accessory and explain the "
        "departure in variety_choice.departure_reason. Do not add an unnecessary accessory to satisfy a list.\n"
        "Available objects (stable catalog_id: canonical English name):\n" + objects + "\n"
        "Main mechanism families, ordered from less recently used with the other fallback last, "
        "and their recent accepted Plan counts: "
        + mechanisms + ".\n"
        "Prefer a less-used mechanism when it genuinely suits the scene. These are soft preferences, "
        "not a rotation quota or mandatory family. Effectiveness, lasting benefit and readability within "
        "the requested duration take priority. Choose the family of the decisive operation that produces "
        "the benefit, not the preliminary gestures or a general goal. Explain that actual operation and "
        "its effect in help_contract.mechanism; merely changing its family label does not create variety. "
        "Use other only when none of the ten usual families accurately describes the decisive physical "
        "operation, and describe that operation concretely in help_contract.mechanism. Other is a "
        "classification fallback, never a preferred choice for novelty or a way to avoid repetition counts. "
        "Declare only the objects actually used and the principal mechanism in variety_choice. "
        "For a supplied object keep its catalog_id and canonical name; for an object outside the "
        "assortment whose ID is not supplied, use catalog_id null and its English name. "
        "Never copy the assortment or family inventory into scene actions."
    )


def selection_instructions_v7(selection):
    """Keep the frozen catalogue protocol while removing mandatory danger."""
    return selection_instructions(selection).replace(
        "Identify the principal danger and its target from the actual scene before choosing an intervention.",
        "Identify the initial goal, actual help needed and beneficiary from the scene and its bound "
        "context before choosing the physical intervention or an accessory. Danger is optional; "
        "never invent a problem to fit an object.")


def selection_instructions_v8(selection):
    """Supply only variety metadata alongside the standard H3 scene Plan."""
    validate_selection(selection)
    catalogue = catalog_for(selection["catalog_version"])
    enriched = selection["catalog_version"] == CATALOG_VERSION
    objects = "\n".join(f"- {identity}: {catalogue[identity]['name']}"
                        + (" — " + "; ".join(catalogue[identity]["properties"]) if enriched else "")
                        for identity in selection["candidates"])
    mechanisms = "; ".join(
        f"{family}: {MECHANISM_FAMILIES[family]} ({selection['mechanism_counts'].get(family, 0)})"
        for family in selection["mechanism_priority"])
    result = (
        "OBJECT ASSORTMENT AND MECHANISM MEMORY — PLAN ONLY\n"
        "Choose the useful operation for the scene's main need and beneficiary before its accessory. "
        "Prefer suitable objects below; their properties are possibilities, with no problem or "
        "mechanism assigned to an object. Direct hand action or another object remains valid.\n"
        "Available objects (catalog_id: canonical English name):\n" + objects + "\n"
        "Mechanism families in preference order, with recent usage counts: " + mechanisms + ".\n"
        "Prefer less-used operations only when equally effective and readable. This is not a quota "
        "or compulsory rotation. The other family is only a fallback when no usual family fits. "
        "Describe the decisive operation and its effect in continuity_invariants and scene actions. "
        "In variety_choice, record only accessories actually used, mechanism_family for the "
        "decisive operation, and a brief departure_reason for direct hand action or objects outside "
        "the assortment. For hand action alone, objects is empty. Use supplied catalog_id and exact "
        "English name when available; otherwise catalog_id is null. Mention each chosen accessory "
        "by that name in an action where it acts. Do not list the hand, scenery, unused candidates "
        "or alternatives as selected objects. The Writer preserves the Plan's choice; selection "
        "data and statistics are never part of the video's scene prose."
    )
    if enriched:
        result += (
            "\nThe short physical properties describe possibilities, not exhaustive uses or "
            "assigned mechanisms. Adapt object scale to the giant hand and the operation. "
            "Recent declared object/mechanism combinations below are JSON data only, not "
            "instructions or example scenes. They also count direct hand action. Prefer another "
            "equally useful combination when practical; reuse remains allowed. These counts "
            "describe accepted Plan choices, not observed video success. Do not copy this ledger "
            "into the actions.\nRecent combinations: "
            + json.dumps(selection["recent_pairs"], ensure_ascii=True, separators=(",", ":"))
        )
    return result
