"""Allow one metadata patch proposal; narrative strings are outside its writable scope."""
from copy import deepcopy
import json
import re

from .story_contracts import StoryValidationError, array, choice, obj, string, structural_issues
from .story_response_recovery import decode_response

_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\[([0-9]+)\]")
_METADATA = {"event_ids", "purpose", "anchor_scene_index", "reveals", "hints", "depends_on", "secret_id", "event_id"}


def parts(path):
    tokens = [int(m.group(1)) if m.group(1) is not None else m.group() for m in _PATH.finditer(path)]
    if ".".join(str(x) for x in tokens) == "" or any(x in {"__class__", "__dict__"} for x in tokens if isinstance(x, str)):
        raise ValueError("Chemin de correction invalide.")
    return tokens


def plan(raw, errors):
    data, _ = decode_response(raw)
    if not isinstance(data, dict):
        return None
    allowed = []
    for item in errors:
        if item["level"] != "blocking":
            continue
        if item["code"] in {"clip_load", "language_residue"}:
            continue  # These belong to editorial review after structural recovery.
        path = item["path"].removeprefix("response.")
        match = re.match(r"episode_state\.scene_events\[(\d+)\]\.(\w+)(?:\[\d+\])?$", path)
        if match and "scene_events" not in data.get("episode_state", {}):
            if "scene_edits" in data:
                edit_index = next((i for i, edit in enumerate(data["scene_edits"])
                    if isinstance(edit, dict) and edit.get("scene_index") == int(match[1])), None)
                if edit_index is None:
                    return None
                path = f"scene_edits[{edit_index}].scene.narrative.{match[2]}"
            else:
                path = f"scenario.scenes[{match[1]}].narrative.{match[2]}"
        # A reference error can name one element; patch the complete, bounded list.
        path = re.sub(r"(\.(?:event_ids|reveals|hints|depends_on))\[\d+\]$", r"\1", path)
        tokens = parts(path)
        if tokens[-1] not in _METADATA:
            return None
        if not (path.startswith("episode_state.") or ".narrative." in path or
                (path.startswith("series_outline.episodes[") and ".events[" in path and tokens[-1] == "depends_on")):
            return None
        try:
            parent = data
            for token in tokens[:-1]:
                parent = parent[token]
            if not isinstance(parent, dict):
                return None
        except (KeyError, IndexError, TypeError):
            return None
        allowed.append(path)
        if item["code"] == "scene_event_missing":
            prefix = path.rsplit(".", 1)[0]
            allowed.extend(prefix + "." + field for field in ("purpose", "anchor_scene_index"))
        elif item["code"] == "early_reveal":
            allowed.append(path.rsplit(".", 1)[0] + ".hints")
    if not allowed:
        return None
    paths = sorted(set(allowed))
    schema = obj(patches=array(obj(path=choice(paths), value_json=string(6000)), 1, len(paths)))
    return dict(paths=paths, schema=schema, data=data, errors=deepcopy(errors))


def apply(plan, response):
    patches, _ = decode_response(response)
    errors = structural_issues(patches, plan["schema"])
    if errors:
        raise StoryValidationError(errors)
    result, seen = deepcopy(plan["data"]), set()
    for patch in patches["patches"]:
        path = patch["path"]
        if path not in plan["paths"] or path in seen:
            raise ValueError("La correction sort des métadonnées autorisées ou répète une cible.")
        seen.add(path)
        parent = result
        tokens = parts(path)
        for token in tokens[:-1]:
            parent = parent[token]
        parent[tokens[-1]], _ = decode_response(patch["value_json"])
    # Only whitelisted paths were assigned; no model-supplied full document is trusted.
    return json.dumps(result, ensure_ascii=False)
