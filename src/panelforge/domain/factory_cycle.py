"""A persisted production-cycle ledger, independent of filtering and deletion."""
from uuid import uuid4
from .video_factory import STAGES, timestamp
from .video_factory_results import delivery_material

OPEN = {"queued", "active", "exporting", "stopping"}


def delivered(item):
    if item["status"] != "succeeded" or item.get("cancel_requested") or item.get("remove_requested"):
        return False
    if any(item["steps"][s]["status"] not in {"succeeded", "skipped"} for s in STAGES):
        return False
    delivery = item.get("delivery", {})
    material = delivery_material(item)
    return bool(material and delivery.get("status") == "succeeded" and delivery.get("key") == material["key"])


def member_status(item):
    if item.get("remove_requested") or item.get("cancel_requested"):
        return "stopping" if item["status"] == "active" else "cancelled"
    if delivered(item):
        return "delivered"
    if item["status"] in {"queued", "active"}:
        return item["status"]
    if item.get("delivery", {}).get("status") == "failed" or item["status"] == "failed":
        return "failed"
    if item["status"] == "succeeded":
        return "exporting"
    if item["status"] == "preparation":
        return "withdrawn"
    return item["status"]


def sync_cycle(state):
    cycle = state.get("production_cycle")
    if not cycle:
        return
    items = {i["id"]: i for i in state["items"]}
    for identity, member in cycle["members"].items():
        item = items.get(identity)
        if item:
            member.update(name=item["name"], status=member_status(item))
        elif member["status"] not in {"delivered", "failed", "cancelled", "withdrawn"}:
            member["status"] = "removed"
    if any(m["status"] in OPEN for m in cycle["members"].values()):
        cycle["finished_at"] = None
    elif not cycle.get("finished_at"):
        cycle["finished_at"] = timestamp()


def admit_cycle(state, items, *, resume=False):
    sync_cycle(state)
    cycle = state.get("production_cycle")
    if not cycle or cycle.get("finished_at") and not resume:
        cycle = dict(id=uuid4().hex, started_at=timestamp(), finished_at=None, members={})
        state["production_cycle"] = cycle
    for item in items:
        cycle["members"][item["id"]] = dict(name=item["name"], status="queued")


def bootstrap_cycle(state):
    if not state.get("production_cycle"):
        items = [i for i in state["items"] if member_status(i) in OPEN and not i.get("archived_at")]
        if items:
            admit_cycle(state, items)
    sync_cycle(state)


def cycle_counts(state):
    members = (state.get("production_cycle") or {}).get("members", {})
    counts = dict(total=len(members), delivered=0, active=0, queued=0, exporting=0,
                  failed=0, cancelled=0, removed=0, withdrawn=0, stopping=0)
    for member in members.values():
        key = member["status"]
        if key in counts:
            counts[key] += 1
    return counts
