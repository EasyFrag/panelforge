"""Bounded, immutable records of declared variety choices and proposed objects.

Callers supply stable preparation identities and timestamps, and persist the
returned journal. No scene prose is classified and no rendering result is
inferred from a declared choice.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

from .little_men_objects import (
    OBJECTS, catalog_for, normalize_object_name, object_identity,
)


HISTORY_VERSION = 1
HISTORY_LIMIT = 50
HAND_KEY = "__hand__"
HAND_NAME = "direct hand action"
KNOWN_MECHANISMS = frozenset({
    "link", "separate", "move", "redirect", "absorb_remove", "reshape",
    "temperature", "support", "contain", "shield", "other",
})


def empty_history():
    return {"schema_version": HISTORY_VERSION, "choices": [], "exposures": []}


def _text(value, *, maximum=512):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError("Invalid variety history identity or name.")
    return value.strip()


def _date(value):
    if not isinstance(value, str):
        raise ValueError("A stable dated variety event is required.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("A valid ISO variety event date is required.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Variety event dates must include their timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def plan_identity(content):
    """Whitespace and JSON key ordering do not turn a retry into a new Plan."""
    if isinstance(content, str):
        value = content.strip()
        if not value:
            raise ValueError("A non-empty Plan is required for variety history.")
        try:
            value = json.loads(value)
        except ValueError:
            pass
    elif isinstance(content, dict):
        value = content
    else:
        raise ValueError("Plan content must be text or a JSON object.")
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def preparation_identity(item):
    """Use an explicit reservation first; historical sessions remain identifiable."""
    if not isinstance(item, dict):
        raise ValueError("Invalid variety preparation.")
    identity = _text(item.get("id"))
    runtime = item.get("runtime") or {}
    if not isinstance(runtime, dict):
        raise ValueError("Invalid variety preparation runtime.")
    if runtime.get("variety_preparation_id"):
        return _text(runtime["variety_preparation_id"])
    if runtime.get("session_id"):
        session = _text(runtime["session_id"])
        digest = hashlib.sha256((identity + "\0" + session).encode("utf-8")).hexdigest()
        return "session:" + digest
    selection = runtime.get("thanks_selection") or {}
    if not isinstance(selection, dict):
        raise ValueError("Invalid variety preparation selection.")
    frozen = selection.get("variety")
    if not isinstance(frozen, dict):
        raise ValueError("A frozen assortment is required to identify this preparation.")
    digest = plan_identity({"item_id": identity, "variety": frozen}).split(":", 1)[1]
    return "legacy:" + digest


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid variety object.")
    name = _text(value.get("name"), maximum=120)
    catalog_id = value.get("catalog_id")
    if catalog_id is not None:
        if not isinstance(catalog_id, str) or catalog_id not in OBJECTS:
            raise ValueError("Unknown variety catalogue object.")
        if object_identity(name) != catalog_id:
            raise ValueError("The variety object name does not match its identity.")
    else:
        catalog_id = object_identity(name)
    if catalog_id is not None:
        return {"object_key": catalog_id, "name": OBJECTS[catalog_id]["name"]}
    normalized = _text(normalize_object_name(name), maximum=120)
    return {"object_key": "external:" + normalized, "name": normalized}


def _choice_event(preparation_id, item_id, plan_id, choice, accepted_at):
    if (not isinstance(choice, dict) or not isinstance(choice.get("mechanism_family"), str)
            or choice["mechanism_family"] not in KNOWN_MECHANISMS):
        raise ValueError("Unknown variety mechanism.")
    declared = choice.get("objects")
    if not isinstance(declared, (list, tuple)) or len(declared) > 95:
        raise ValueError("Invalid declared variety objects.")
    objects = {}
    for value in declared:
        obj = _object(value)
        objects[obj["object_key"]] = obj
    return {
        "preparation_id": _text(preparation_id), "item_id": _text(item_id),
        "plan_id": _text(plan_id), "accepted_at": _date(accepted_at),
        "mechanism_family": choice["mechanism_family"],
        "objects": sorted(objects.values(), key=lambda value: value["object_key"]),
    }


def _stored_choice(value):
    if not isinstance(value, dict) or not isinstance(value.get("objects"), list):
        raise ValueError("Invalid recorded variety choice.")
    declared = []
    for obj in value["objects"]:
        if not isinstance(obj, dict):
            raise ValueError("Invalid recorded variety object.")
        key, name = obj.get("object_key"), obj.get("name")
        if not isinstance(key, str):
            raise ValueError("Invalid recorded variety object key.")
        if key in OBJECTS:
            declared.append({"catalog_id": key, "name": name})
        elif key == "external:" + normalize_object_name(name):
            declared.append({"catalog_id": None, "name": name})
        else:
            raise ValueError("Invalid recorded variety object key.")
    return _choice_event(value.get("preparation_id"), value.get("item_id"),
                         value.get("plan_id"), {
                             "objects": declared,
                             "mechanism_family": value.get("mechanism_family"),
                         }, value.get("accepted_at"))


def _exposure_event(preparation_id, item_id, candidates, reserved_at):
    if (not isinstance(candidates, (list, tuple)) or len(candidates) != 12
            or any(not isinstance(key, str) or key not in OBJECTS for key in candidates)
            or len(set(candidates)) != len(candidates)):
        raise ValueError("An exposure must contain twelve distinct catalogue objects.")
    return {"preparation_id": _text(preparation_id), "item_id": _text(item_id),
            "reserved_at": _date(reserved_at), "candidates": list(candidates)}


def _stored_exposure(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid recorded variety exposure.")
    return _exposure_event(value.get("preparation_id"), value.get("item_id"),
                           value.get("candidates"), value.get("reserved_at"))


def _choice_key(value):
    return value["item_id"], value["preparation_id"], value["plan_id"]


def _exposure_key(value):
    return value["item_id"], value["preparation_id"]


def _bounded(values, parse, key, date_field):
    valid = []
    for value in values if isinstance(values, (list, tuple)) else ():
        try:
            valid.append(parse(value))
        except (ValueError, TypeError, AttributeError):
            continue
    # Preserve the original date when persisted data contains a retried event.
    unique = {}
    for value in sorted(valid, key=lambda entry: (entry[date_field], key(entry))):
        unique.setdefault(key(value), value)
    return sorted(unique.values(), key=lambda entry: (entry[date_field], key(entry)),
                  reverse=True)[:HISTORY_LIMIT]


def _history(history):
    if history is None:
        return empty_history()
    if (not isinstance(history, dict) or type(history.get("schema_version")) is not int
            or history["schema_version"] != HISTORY_VERSION):
        raise ValueError("Unsupported variety history version.")
    return {
        "schema_version": HISTORY_VERSION,
        "choices": _bounded(history.get("choices"), _stored_choice, _choice_key, "accepted_at"),
        "exposures": _bounded(history.get("exposures"), _stored_exposure, _exposure_key, "reserved_at"),
    }


def record_exposure(history, preparation_id, item_id, candidates, reserved_at):
    """Return a journal with one reservation, preserving its first date on retry."""
    result = _history(history)
    event = _exposure_event(preparation_id, item_id, candidates, reserved_at)
    previous = next((entry for entry in result["exposures"]
                     if _exposure_key(entry) == _exposure_key(event)), None)
    if previous is not None:
        if previous["candidates"] != event["candidates"]:
            raise ValueError("A reserved assortment cannot change within one preparation.")
        return result
    result["exposures"] = sorted(result["exposures"] + [event],
                                 key=lambda entry: (entry["reserved_at"], _exposure_key(entry)),
                                 reverse=True)[:HISTORY_LIMIT]
    return result


def record_choice(history, preparation_id, item_id, plan_id, choice, accepted_at):
    """A distinct accepted Plan counts once; a retry cannot refresh its date."""
    result = _history(history)
    event = _choice_event(preparation_id, item_id, plan_id, choice, accepted_at)
    previous = next((entry for entry in result["choices"]
                     if _choice_key(entry) == _choice_key(event)), None)
    if previous is not None:
        if (previous["objects"] != event["objects"]
                or previous["mechanism_family"] != event["mechanism_family"]):
            raise ValueError("An accepted Plan identity cannot describe a different choice.")
        return result
    result["choices"] = sorted(result["choices"] + [event],
                               key=lambda entry: (entry["accepted_at"], _choice_key(entry)),
                               reverse=True)[:HISTORY_LIMIT]
    return result


def bootstrap_history(items, history=None):
    """Import dated legacy facts once; an existing journal remains authoritative.

    finished_at and started_at are the only legacy time fallbacks. updated_at
    is deliberately ignored: rendering progress must not reorder old choices.
    """
    if history is not None:
        return _history(history)
    result = empty_history()
    for item in items:
        if not isinstance(item, dict):
            continue
        config = item.get("config") or {}
        if not isinstance(config, dict):
            continue
        if (config.get("preset_origin") or config.get("preset")) != "little_men_variety":
            continue
        runtime = item.get("runtime") or {}
        if not isinstance(runtime, dict):
            continue
        selection = runtime.get("thanks_selection") or {}
        steps = item.get("steps") or {}
        if not isinstance(selection, dict) or not isinstance(steps, dict):
            continue
        step = steps.get("plan") or {}
        if not isinstance(step, dict):
            continue
        try:
            preparation = preparation_identity(item)
            frozen = selection.get("variety") or {}
            catalogue = catalog_for(frozen.get("catalog_version"))
            candidates = frozen.get("candidates")
            if not isinstance(candidates, list) or any(key not in catalogue for key in candidates):
                raise ValueError("Invalid historical assortment.")
            result = record_exposure(result, preparation, item["id"], candidates,
                                     runtime.get("variety_reserved_at") or step.get("started_at"))
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
        if step.get("status") != "succeeded":
            continue
        try:
            content = (step.get("output") or {}).get("text")
            try:
                plan = json.loads(content)
            except (ValueError, TypeError):
                plan = {}
            choice = plan.get("variety_choice") if isinstance(plan, dict) else None
            if choice is None:
                choice = selection.get("variety_choice")
            result = record_choice(result, preparation_identity(item), item["id"],
                                   plan_identity(content), choice, step.get("finished_at"))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return result


def summarize_history(history, exclude_item_id=None):
    """Return declared-use counters and compact pairs, without interpreting prose."""
    journal = _history(history)
    objects, exposure, mechanisms, pairs = Counter(), Counter(), Counter(), Counter()
    names, last = {}, {}
    for event in journal["choices"]:
        if event["item_id"] == exclude_item_id:
            continue
        family = event["mechanism_family"]
        mechanisms[family] += 1
        declared = event["objects"] or [{"object_key": HAND_KEY, "name": HAND_NAME}]
        for obj in declared:
            key = obj["object_key"]
            objects[key] += 1
            pair = (key, family)
            pairs[pair] += 1
            names[key] = obj["name"]
            last[pair] = max(last.get(pair, ""), event["accepted_at"])
    for event in journal["exposures"]:
        if event["item_id"] != exclude_item_id:
            exposure.update(event["candidates"])
    ordered = sorted(pairs)
    # Frequency takes precedence; among equally frequent pairs, newest first.
    ordered.sort(key=lambda pair: last[pair], reverse=True)
    ordered.sort(key=lambda pair: pairs[pair], reverse=True)
    return {
        "object_counts": dict(objects), "exposure_counts": dict(exposure),
        "mechanism_counts": dict(mechanisms),
        "recent_pairs": [{"object_key": key, "name": names[key],
                          "mechanism_family": family, "count": pairs[(key, family)]}
                         for key, family in ordered],
    }
