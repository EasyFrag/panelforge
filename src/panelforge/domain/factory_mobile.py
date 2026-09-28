"""Small, path-free mobile views and alert conditions."""
from math import isfinite
from .video_factory import STAGES, fingerprint
from .factory_cycle import cycle_counts, delivered
from .factory_timing import epoch

LABELS = dict(plan="Plan", prompt="Prompt", video="Vidéo", dlss="DLSS", social="Texte IG")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def active_run_key(item):
    return fingerprint([(stage, item["steps"][stage].get("started_at"),
                         (item["steps"][stage].get("timing") or {}).get("id"))
                        for stage in STAGES if item["steps"][stage]["status"] == "running"])


def media_asset(item, kind):
    if kind == "poster":
        refs = (item.get("launch_snapshot") or item["config"]).get("references", [])
        return next((ref.get("asset_id") for ref in refs if ref.get("asset_id")), None)
    if kind == "video":
        # Mobile streams the original render only, even after DLSS completes.
        step = item["steps"]["video"]
        if step["status"] == "succeeded":
            return (step.get("output") or {}).get("asset_id")
    return None


def mobile_view(state, machine_snapshot, now, *, result_limit=24):
    monitor = state.get("monitoring") or {}
    observed = epoch(machine_snapshot.get("observed_at"))
    stale = observed is None or now - observed > 20
    settings = machine_snapshot.get("settings", {})
    thresholds = dict(local_gpu=settings.get("local_cooldown_temperature_c", 80),
                      remote_gpu=settings.get("thermal", {}).get("stop_temperature_c", 85))
    machines = []
    for lane, label in (("local_gpu", "PC"), ("remote_gpu", "Serveur")):
        raw = machine_snapshot.get("machines", {}).get(lane, {})
        machines.append(dict(id=lane, name=label, temperature_c=raw.get("temperature_c"),
            state="stale" if stale else raw.get("state", "unavailable"), threshold=thresholds[lane],
            operation=raw.get("operation"), cooldown_seconds=raw.get("cooldown_remaining_seconds", 0)))
    def view(item):
        estimate = monitor.get("items", {}).get(item["id"], {})
        steps = []
        for key in STAGES:
            step = item["steps"][key]
            predicted = estimate.get("steps", {}).get(key, {})
            start = epoch(step.get("started_at"))
            steps.append(dict(id=key, label=LABELS[key], status=step["status"],
                remaining_seconds=predicted.get("seconds"), retained=bool(predicted.get("retained")),
                elapsed_seconds=max(0, now - start) if start and step["status"] == "running" else None))
        remaining = estimate.get("remaining_seconds")
        held = bool(estimate.get("retained")) or stale
        finished = delivered(item)
        return dict(id=item["id"], name=item["name"], revision=item["revision"], status=item["status"],
            active_run=active_run_key(item),
            group=item.get("source", {}).get("group"), steps=steps,
            stopping=bool(item.get("cancel_requested")), delivered=finished,
            remaining_seconds=remaining, retained=held,
            finish_at=now + remaining if number(remaining) and not held and not state["paused"] else None,
            hint=estimate.get("indicative_reason") or estimate.get("reason") or item.get("waiting_reason"),
            video_url="/api/items/" + item["id"] + "/video" if media_asset(item, "video") else None,
            poster_url="/api/items/" + item["id"] + "/poster" if media_asset(item, "poster") else None,
            quality="Vidéo brute",
            completed_at=item["steps"]["dlss"].get("finished_at") or item["steps"]["video"].get("finished_at"),
            # Do not expose raw error strings, prompts, runtime paths or tokens.
            failed=any(s["status"] == "failed" for s in item["steps"].values()) or item.get("delivery", {}).get("status") == "failed",
            failure_key="|".join(str(item["steps"][s].get("started_at") or "") for s in STAGES),
            can_retry=item["status"] in {"failed", "cancelled"} and not item.get("recover_stage")
                      or item["status"] == "succeeded" and item.get("delivery", {}).get("status") == "failed")
    visible = [i for i in state["items"] if i["status"] != "preparation" and not i.get("remove_requested")]
    rows = [view(i) for i in visible]
    work = [r for i, r in zip(visible, rows) if not i.get("archived_at") and
            (r["status"] in {"queued", "active", "failed", "cancelled"} or not r["delivered"])]
    # Keep produced cards visible if only their DLSS output remains available.
    results = sorted((row for item, row in zip(visible, rows) if any(
        item["steps"][stage]["status"] == "succeeded" and
        (item["steps"][stage].get("output") or {}).get("asset_id") for stage in ("video", "dlss"))),
                     key=lambda r: r["completed_at"] or "", reverse=True)
    remaining = monitor.get("remaining_seconds")
    held = bool(monitor.get("retained")) or stale
    counts = monitor.get("counts") or cycle_counts(state)
    status = monitor.get("status") or ("paused" if state["paused"] else "running" if work else "empty")
    return dict(version=1, generated_at=now, revision=state.get("revision", 0), paused=state["paused"],
        cycle_id=(state.get("production_cycle") or {}).get("id"), status=status, counts=counts,
        remaining_seconds=remaining, retained=held, hint=monitor.get("indicative_reason"),
        finish_at=now + remaining if number(remaining) and not held and not state["paused"] else None,
        stale=stale, machines=machines, thresholds=thresholds, work=work,
        results=results[:result_limit], result_total=len(results))


def alert_conditions(view, thresholds, previous=()):
    """Hysteresis prevents repeated alerts while a GPU hovers at its threshold."""
    alerts = {}
    if not view["stale"]:
        for machine in view["machines"]:
            limit = thresholds.get(machine["id"], machine["threshold"])
            key = "temperature:" + machine["id"] + ":" + str(limit)
            temperature = machine["temperature_c"]
            if number(temperature) and (temperature >= limit or key in previous and temperature > limit - 3):
                alerts[key] = dict(kind="temperature", title=machine["name"] + " : température élevée",
                    body=f"{temperature:g} °C · seuil {limit:g} °C", tag=key)
    for item in view["work"]:
        if item["failed"]:
            key = "failure:" + item["id"] + ":" + item["failure_key"]
            alerts[key] = dict(kind="failure", title="Une vidéo demande votre attention",
                              body=item["name"], tag=key)
    if view["status"] == "complete" and view["cycle_id"]:
        key = "complete:" + view["cycle_id"]
        alerts[key] = dict(kind="complete", title="Lot terminé",
                          body=f'{view["counts"]["delivered"]} vidéo(s) livrée(s).', tag=key)
    return alerts


def mobile_thermal_history(history, now):
    """Six-hour view of the existing maxima, without runtime event details."""
    start = now - 6 * 3600
    lanes = []
    for identity, name in (("remote_gpu", "Serveur"), ("local_gpu", "PC local")):
        points = {}
        for point in history.get("series", {}).get(identity, []):
            stamp = epoch(point.get("timestamp"))
            temperature = point.get("max_temperature_c")
            if stamp is None or not start <= stamp <= now or not number(temperature) or not 0 <= temperature <= 150:
                continue
            points[stamp] = max(points.get(stamp, temperature), temperature)
        lanes.append(dict(id=identity, name=name,
                          points=[[stamp, round(value, 1)] for stamp, value in sorted(points.items())]))
    bucket = history.get("bucket_seconds")
    bucket = bucket if number(bucket) and 1 <= bucket <= 300 else 15
    return dict(available=True, generated_at=now, start_at=start, end_at=now,
                window_seconds=6 * 3600, bucket_seconds=bucket, machines=lanes,
                warning="Historique partiel ; certaines mesures sont indisponibles."
                        if history.get("error") else None)
