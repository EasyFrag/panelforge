"""Lossless request-only history compaction; stored snapshots remain untouched."""
from copy import deepcopy
import json

HISTORY_FIELDS = {"previous_story_read_only", "previous_episode_read_only", "previous_history",
                  "visual_state_inherited", "canonical_history"}


def compact(value, *, history_root=False):
    """Decode known JSON history wrappers and alias identical large containers.

    References are absolute JSON pointers to earlier content in this request.
    Their enclosing project/unit scopes are kept, even when content is identical.
    Never parse quoted dialogue or arbitrary author prose as JSON.
    """
    known = {}
    def walk(item, path, history=False, field=""):
        if isinstance(item, str) and (field in HISTORY_FIELDS or history_root and path == "#"):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, (dict, list)):
                    item = parsed
            except (ValueError, TypeError):
                pass
        active = history or field in HISTORY_FIELDS
        key = None
        if active and isinstance(item, (dict, list)):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(key) < 400:
                key = None
            elif key in known:
                return {"same_content_as": known[key]}
        if isinstance(item, dict):
            result = {k: walk(v, path + "/" + k.replace("~", "~0").replace("/", "~1"), active, k)
                      for k, v in item.items()}
        elif isinstance(item, list):
            result = [walk(v, path + "/" + str(i), active) for i, v in enumerate(item)]
        else:
            return deepcopy(item)
        if key is not None:
            known[key] = path
        return result
    return walk(value, "#", history_root)
