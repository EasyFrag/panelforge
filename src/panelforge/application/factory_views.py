"""Small read models for the factory list; full recipes stay in item details."""
from copy import deepcopy
from datetime import datetime

from panelforge.domain.video_factory import STAGES, readiness
from panelforge.domain.video_factory_results import can_archive


def item_tab(item):
    if item.get("remove_requested"):
        return "production"
    if item.get("archived_at"):
        return "archives"
    if item["status"] == "preparation":
        return "preparation"
    return "production" if item["status"] in {"queued", "active"} else "results"


def has_errors(item):
    return any(s["status"] == "failed" for s in item["steps"].values()) or item.get("delivery", {}).get("status") == "failed"


def descriptor(item):
    return dict(id=item["id"], revision=item["revision"], tab=item_tab(item), status=item["status"],
                ready=not (readiness(item["config"]) + item.get("source_issues", [])),
                can_archive=can_archive(item), archived_at=item.get("archived_at"),
                remove_requested=bool(item.get("remove_requested")), recover_stage=item.get("recover_stage"),
                delivery={"status": item.get("delivery", {}).get("status")}, has_errors=has_errors(item))


def list_row(item, position):
    value = descriptor(item)
    value.update(summary=True, position=position, name=item["name"], source=deepcopy(item["source"]),
                 cancel_requested=bool(item.get("cancel_requested")), waiting_reason=item.get("waiting_reason"),
                 created_at=item.get("created_at"), launched_at=item.get("launched_at"),
                 issues=readiness(item["config"]) + item.get("source_issues", []),
                 config={"mode": item["config"]["mode"], "preset": item["config"]["preset"],
                         "social": {k: item["config"]["social"][k] for k in ("language", "variant_count")},
                         "references": [{k: r.get(k) for k in ("asset_id", "label")} for r in item["config"]["references"][:1]]},
                 runtime={"episode_inputs": {"localization": {"language": item.get("runtime", {}).get("episode_inputs", {}).get("localization", {}).get("language")}}},
                 delivery={k: deepcopy(item.get("delivery", {}).get(k)) for k in ("status", "folder", "error", "finished_at")},
                 steps={})
    for name in STAGES:
        step = item["steps"][name]
        value["steps"][name] = {k: deepcopy(step.get(k)) for k in ("status", "progress", "message", "error", "started_at", "finished_at")}
        value["steps"][name]["output"] = {"asset_id": step.get("output", {}).get("asset_id"),
                                                "variant_count": len(step.get("output", {}).get("variants", []))}
    return value


def result_date(item):
    def stamp(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (AttributeError, TypeError, ValueError):
            return 0
    values = [stamp(item.get("delivery", {}).get("finished_at")),
              *(stamp(s.get("finished_at")) for s in item["steps"].values())]
    return max(values) or stamp(item.get("launched_at") or item.get("created_at"))


def ordered_rows(items, tab, filter, sort):
    selected = []
    for item in items:
        if item_tab(item) != tab:
            continue
        if filter in {"ready", "incomplete"}:
            ready = not (readiness(item["config"]) + item.get("source_issues", []))
            if item["status"] != "preparation" or ready != (filter == "ready"):
                continue
        if filter == "failed" and not has_errors(item) or filter == "archivable" and not can_archive(item):
            continue
        selected.append(item)
    if tab != "results" or sort != "newest":
        return selected
    blocks = {}
    for item in selected:
        source = item["source"]
        key = ("episode", source["id"]) if source["kind"] == "episode" else ("item", item["id"])
        blocks.setdefault(key, []).append(item)
    return [item for block in sorted(blocks.values(), key=lambda b: max(map(result_date, b)), reverse=True) for item in block]
