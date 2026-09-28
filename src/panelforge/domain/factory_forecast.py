"""Read-only simulation of the factory's ordered, two-lane scheduler."""
from copy import deepcopy
from math import inf, isfinite
from .video_factory import STAGES, DEPENDENCIES
from .factory_timing import LANES, epoch
from .factory_cycle import delivered, OPEN, cycle_counts
from .video_factory_results import delivery_material

DONE = {"succeeded", "skipped"}


def _simulate(items, estimates, lanes, machines, settings, now, bound, paused):
    states = {i["id"]: {s: i["steps"][s]["status"] for s in STAGES} for i in items}
    timeline = {i["id"]: {} for i in items}
    busy_items, occupied, events = set(), {}, []
    ready_at = {lane: max(0, machines.get(lane, {}).get("cooldown_remaining_seconds") or 0) for lane in LANES}
    video_after = 0
    barriers = set()
    for lane in LANES:
        machine = machines.get(lane, {})
        if (machine.get("paused") or machine.get("state") in {"hot", "unavailable", "stale"}
                or machine.get("state") == "cooling" and not ready_at[lane]
                or machine.get("queue_count", 0)):
            barriers.add(lane)
        running = any(i["steps"][s]["status"] == "running" and lanes[i["id"]][s] == lane
                      for i in items for s in STAGES)
        if machine.get("state") == "busy" and not running:
            barriers.add(lane)
    def start(item, stage, at, running=False):
        identity = item["id"]
        lane = lanes[identity][stage]
        duration = estimates[identity][stage].get(bound)
        finish = at + duration if duration is not None else inf
        timeline[identity][stage] = dict(start=at, finish=finish)
        states[identity][stage] = "running"
        busy_items.add(identity)
        occupied[lane] = finish
        if isfinite(finish):
            events.append((finish, identity, stage, lane, running))

    for item in items:
        for stage in STAGES:
            if states[item["id"]][stage] == "running":
                start(item, stage, 0, running=True)
    t = 0
    # Each finite event completes one stage. Unknown durations block only the
    # affected lane and dependencies; independent work still gets a forecast.
    for _ in range(len(items) * len(STAGES) * 3 + 4):
        due = [e for e in events if e[0] <= t]
        for event in due:
            end, identity, stage, lane, was_running = event
            events.remove(event)
            states[identity][stage] = "succeeded"
            busy_items.discard(identity)
            occupied.pop(lane, None)
            if stage == "video":
                video_after = end + (settings.get("remote_video_cooldown_seconds") or 0)
                # The factory admits no remote work while public_status is cooling.
                ready_at["remote_gpu"] = max(ready_at["remote_gpu"], video_after)
            machine = machines.get(lane, {})
            threshold = settings.get("local_cooldown_temperature_c", 80) if lane == "local_gpu" else settings.get("remote_non_video_cooldown_temperature_c", 80)
            peak = (machine.get("active") or {}).get("peak_temperature_c") if was_running else None
            cooldown = settings.get("local_cooldown_seconds", 0) if lane == "local_gpu" else settings.get("remote_non_video_cooldown_seconds", 0)
            monitored = settings.get("thermal", {}).get("monitor_local" if lane == "local_gpu" else "monitor_remote", True)
            if monitored and stage != "video" and (bound == "high" or peak is not None and peak >= threshold):
                ready_at[lane] = max(ready_at[lane], end + cooldown)
        started = False
        if not paused:
            for lane in LANES:
                if lane in occupied or lane in barriers or ready_at[lane] > t:
                    continue
                choice = None
                for item in items:
                    identity = item["id"]
                    if (identity in busy_items or item.get("cancel_requested") or item.get("remove_requested")
                            or item["status"] not in {"queued", "active"}
                            or (item.get("retry_after", 0) - now) > t):
                        continue
                    for stage in STAGES:
                        if (states[identity][stage] == "pending" and lanes[identity][stage] == lane
                                and all(states[identity][dep] in DONE for dep in DEPENDENCIES[stage])):
                            choice = (item, stage)
                            break
                    if choice:
                        break
                if choice:
                    item, stage = choice
                    # Dispatch would reserve the lane for this render's cooldown.
                    at = max(t, video_after) if stage == "video" else t
                    start(item, stage, at)
                    started = True
        futures = [e[0] for e in events if e[0] > t]
        if not paused:
            futures += [value for lane, value in ready_at.items()
                        if value > t and lane not in occupied and lane not in barriers]
            futures += [i.get("retry_after", 0) - now for i in items
                        if i.get("retry_after", 0) - now > t]
        if not futures:
            if started and any(e[0] == t for e in events):
                continue
            break
        t = min(futures)

    # Publication is serialized and can continue while the factory is paused.
    # Forecast the final delivery (including the last social text), not raw video.
    export_free = 0
    for item in items:
        delivery = item.get("delivery", {})
        if delivery.get("status") in {"running", "copying", "publishing"}:
            estimate = estimates[item["id"]]["export"]
            value = estimate.get("reservation", estimate).get(bound)
            export_free = max(export_free, value if value is not None else inf)
    candidates = []
    for index, item in enumerate(items):
        identity = item["id"]
        if delivered(item):
            timeline[identity]["ready"] = 0
        elif item["status"] not in {"failed", "cancelled", "preparation"} and not item.get("cancel_requested") and not item.get("remove_requested"):
            complete = all(states[identity][s] in DONE for s in STAGES)
            if complete and item.get("delivery", {}).get("status") != "failed":
                finish = max((v["finish"] for v in timeline[identity].values() if isinstance(v, dict)), default=0)
                candidates.append((finish, index, item))
    for finish, _, item in sorted(candidates, key=lambda value: (value[0], value[1])):
        identity = item["id"]
        duration = estimates[identity]["export"].get(bound)
        # An already-running final export is its own reservation, not an extra copy.
        material = delivery_material(item)
        active_final = (item.get("delivery", {}).get("status") in {"running", "copying", "publishing"}
                        and item["status"] == "succeeded" and material
                        and item.get("delivery", {}).get("key") == material["key"])
        end = (duration if duration is not None else inf) if active_final else max(finish, export_free) + (duration if duration is not None else inf)
        timeline[identity]["export"] = dict(start=max(finish, export_free) if not active_final else 0, finish=end)
        timeline[identity]["ready"] = end
        export_free = max(export_free, end)
    return timeline


def forecast(state, estimates, lanes, machine_snapshot, now, *, target_ids=None):
    items = [i for i in state["items"] if i["status"] != "preparation" and not i.get("archived_at")]
    machines = deepcopy(machine_snapshot.get("machines", {}))
    observed = epoch(machine_snapshot.get("observed_at"))
    stale = observed is None or now - observed > 20
    if stale:
        for machine in machines.values():
            machine["state"] = "stale"
        if not machines:
            machines = {lane: {"state": "stale"} for lane in LANES}
    for lane in LANES:
        machines.setdefault(lane, dict(state="unavailable"))
    settings = machine_snapshot.get("settings", {})
    simulations = {bound: _simulate(items, estimates, lanes, machines, settings, now, bound, state["paused"])
                   for bound in ("seconds", "low", "high")}
    rows = {}
    for item in items:
        identity = item["id"]
        central = simulations["seconds"][identity]
        steps = {}
        for stage in (*STAGES, "export"):
            estimate = dict(estimates[identity][stage])
            scheduled = central.get(stage, {})
            estimate.update(start_in=_finite(scheduled.get("start")),
                            finish_in=_finite(scheduled.get("finish")))
            steps[stage] = estimate
        values = {key: _finite(simulations[key][identity].get("ready")) for key in simulations}
        if all(v is not None for v in values.values()):
            bounds = list(values.values())
            values.update(low=min(bounds), high=max(bounds))
        video = central.get("video", {})
        unknown = [v["reason"] for s, v in estimates[identity].items()
                   if v["seconds"] is None and (s == "export" or item["steps"][s]["status"] in {"pending", "running"})]
        reason = ("File en pause · fin suspendue" if state["paused"] and values["seconds"] is None else
                  "Données machines anciennes" if stale and values["seconds"] is None else
                  unknown[0] if unknown else "En attente de la machine ou d’un traitement précédent")
        rows[identity] = dict(remaining_seconds=values["seconds"], low_seconds=values["low"],
                              high_seconds=values["high"], steps=steps,
                              video_start_in=_finite(video.get("start")),
                              video_ready_in=0 if item["steps"]["video"]["status"] in DONE else _finite(video.get("finish")),
                              reason=reason if values["seconds"] is None else None,
                              indicative_reason=next((v["reason"] for s, v in estimates[identity].items()
                                  if v.get("indicative") and (s == "export" or item["steps"][s]["status"] not in DONE)), None),
                              confidence="low" if any(v["confidence"] in {"low", "unknown"} for s, v in estimates[identity].items()
                                                      if s == "export" or item["steps"][s]["status"] not in DONE) else "medium")
    members = (state.get("production_cycle") or {}).get("members", {})
    targets = set(target_ids) if target_ids is not None else {k for k, v in members.items() if v["status"] in OPEN}
    values = [rows.get(identity, {}) for identity in targets]
    totals = {}
    for field in ("remaining_seconds", "low_seconds", "high_seconds"):
        totals[field] = None if any(v.get(field) is None for v in values) else max((v[field] for v in values), default=0)
    counts = cycle_counts(state)
    status = ("paused" if state["paused"] and targets else "running" if targets else
              "attention" if counts["failed"] or counts["cancelled"] or counts["removed"] or counts["withdrawn"] else
              "complete" if counts["total"] else "empty")
    return dict(version=1, generated_at=now, machine_observed_at=machine_snapshot.get("observed_at"),
                stale=stale, machines=machines, settings=settings, items=rows,
                cycle=state.get("production_cycle"), counts=counts, status=status, **totals,
                confidence="low" if any(v.get("confidence") != "medium" for v in values) else "medium",
                indicative_reason=next((v["indicative_reason"] for v in values if v.get("indicative_reason")), None),
                note="Fourchette indicative ; refroidissements futurs variables. Livré = vidéo, options et export terminés.")


def _finite(value):
    return value if value is not None and isfinite(value) else None
