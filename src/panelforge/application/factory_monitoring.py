"""Factory monitoring: durable measurements and side-effect-free forecasts."""
from copy import deepcopy
from threading import RLock
from uuid import uuid4
import time

from panelforge.domain.video_factory import STAGES, fingerprint
from panelforge.domain.factory_cycle import delivered, OPEN
from panelforge.domain.video_factory_results import delivery_material
from panelforge.domain.factory_timing import DurationModel, duration_profile, epoch, observation
from panelforge.domain.factory_forecast import forecast


class FactoryMonitoring:
    def __init__(self, store, *, clock=time.time):
        self.store, self.clock = store, clock
        self._lock = RLock()
        self.warning = None
        self._writable = True
        self._bootstrapped = False
        self._forecasts = {}
        self._forecast_at = 0
        try:
            value = store.load()
            self.records, self.seen = value["records"], set(value["seen"])
            self.model = DurationModel(self.records)
        except Exception:
            # Never overwrite a damaged journal or prevent production.
            self.records, self.seen, self.model = [], set(), DurationModel()
            self._writable = False
            self.warning = "Historique des durées indisponible ; vérifier le journal du monitoring."

    def profile(self, adapter, item, stage, *, historical=False):
        recipe = None
        if stage == "video":
            resolve = getattr(adapter, "timing_recipe", None)
            if resolve:
                recipe = resolve(item, historical=historical)
        return duration_profile(item, stage, "export" if stage == "export" else adapter.lane(item, stage), recipe)

    def bootstrap(self, adapter, items):
        with self._lock:
            if self._bootstrapped:
                return
            self._bootstrapped = True
            changed = False
            for item in items:
                for stage in (*STAGES, "export"):
                    try:
                        step = item.get("delivery", {}) if stage == "export" else item["steps"][stage]
                        if step.get("status") != "succeeded":
                            continue
                        record = observation(item, stage, self.profile(adapter, item, stage, historical=True),
                                             legacy=not bool(step.get("timing")))
                        changed = self._add(record) or changed
                    except (KeyError, ValueError, FileNotFoundError, OSError, AttributeError):
                        # Missing child manifests are not replaced by a guessed recipe.
                        continue
            if changed:
                self._persist()

    def begin(self, item, stage):
        runtime = item.get("runtime", {})
        child = runtime.get("attempt_id" if stage == "video" else "dlss_job_id") if stage in {"video", "dlss"} else None
        quality = "recovered" if item.get("recover_stage") == stage or child else "complete"
        if stage == "plan" and runtime.get("saved_plan"):
            quality = "reused"
        item["steps"][stage]["timing"] = dict(id=uuid4().hex, quality=quality)

    def record(self, adapter, item, stage):
        with self._lock:
            try:
                record = observation(item, stage, self.profile(adapter, item, stage, historical=True))
                if self._add(record):
                    self._persist()
            except Exception:
                self.warning = "Une mesure de durée n’a pas pu être enregistrée."

    def _add(self, record):
        if not record or record["id"] in self.seen:
            return False
        self.seen.add(record["id"])
        self.records.append(record)
        return True

    def _persist(self):
        self.records = sorted(self.records, key=lambda r: r["finished_at"])[-4000:]
        self.model = DurationModel(self.records)
        if self._writable:
            try:
                self.store.save(dict(schema_version=1, records=self.records, seen=sorted(self.seen)))
            except Exception:
                self.warning = "Durées disponibles en mémoire ; leur sauvegarde a échoué."

    def snapshot(self, adapter, state, *, target_ids=None, assume_resumed=False):
        with self._lock:
            model, warning = self.model, self.warning
        now = self.clock()
        machine_snapshot = deepcopy(getattr(adapter, "monitor_snapshot", {}))
        estimates, lanes = {}, {}
        for item in state["items"]:
            if item["status"] == "preparation" or item.get("archived_at"):
                continue
            identity = item["id"]
            estimates[identity], lanes[identity] = {}, {}
            for stage in (*STAGES, "export"):
                lanes[identity][stage] = "export" if stage == "export" else adapter.lane(item, stage)
                step = item.get("delivery", {}) if stage == "export" else item["steps"][stage]
                complete = delivered(item) if stage == "export" else step["status"] in {"succeeded", "skipped"}
                if complete:
                    estimates[identity][stage] = dict(seconds=0, low=0, high=0, samples=0,
                                                     confidence="medium", source="completed", reason="Terminé")
                    continue
                start = epoch(step.get("started_at"))
                running = step.get("status") in {"running", "copying", "publishing"}
                elapsed = max(0, now - start) if running and start is not None else 0
                try:
                    profile = self.profile(adapter, item, stage)
                    estimate = model.estimate(profile, elapsed=elapsed)
                    if stage == "export" and running:
                        material = delivery_material(item)
                        final = item["status"] == "succeeded" and material and step.get("key") == material["key"]
                        if not final:
                            reservation = estimate
                            estimate = model.estimate(profile)
                            estimate["reservation"] = reservation
                except (KeyError, ValueError, OSError, AttributeError):
                    estimate = dict(seconds=None, low=None, high=None, samples=0, confidence="unknown",
                                    source="missing", reason="Configuration non comparable")
                if running and (step.get("timing") or {}).get("quality") in {"recovered", "reused"}:
                    # Partial measurements are excluded from learning, but comparable
                    # history still supplies a useful (less certain) forecast.
                    if estimate["seconds"] is not None:
                        reason = estimate["reason"] if estimate.get("indicative") else "Durée indicative"
                        estimate.update(confidence="low", indicative=True,
                                        reason=reason + " · chronométrage partiel de cette étape")
                machine = machine_snapshot.get("machines", {}).get(lanes[identity][stage], {})
                thermal_wait = (machine.get("active") or {}).get("stage") == "Attente thermique"
                runtime = item.get("runtime", {})
                children = [runtime.get(key) for key in ("attempt_id", "render_project_id", "dlss_job_id")]
                owner = machine.get("owner_id")
                foreign_gpu = (running and stage in {"video", "dlss"} and owner
                               and any(children) and not any(child and child in owner for child in children))
                if foreign_gpu:
                    estimate.update(seconds=None, low=None, high=None, confidence="unknown",
                                    reason="Machine occupée par un autre atelier")
                if running and thermal_wait:
                    estimate.update(seconds=None, low=None, high=None, confidence="unknown",
                                    reason="Attente thermique · reprise selon la température")
                estimates[identity][stage] = estimate
        candidate = dict(state, paused=False) if assume_resumed else state
        value = forecast(candidate, estimates, lanes, machine_snapshot, now, target_ids=target_ids)
        if target_ids is None:
            self._retain_forecasts(state, value)
        value.update(warning=warning, samples=len(self.records), conditional_on_resume=assume_resumed)
        return value

    def _retain_forecasts(self, state, value):
        """Keep a frozen reference through waits; never pass it to the scheduler."""
        cycle = state.get("production_cycle") or {}
        items = [i for i in state["items"] if i["status"] in {"queued", "active", "succeeded"}
                 and not i.get("archived_at") and not i.get("cancel_requested")
                 and not i.get("remove_requested") and not delivered(i)
                 and i.get("delivery", {}).get("status") != "failed"]
        # Changing the queue/order/configuration invalidates dependent dates.
        queue = [(i["id"], i.get("launch_snapshot") or i["config"]) for i in items]
        scope = fingerprint([cycle.get("id"), queue])
        fields = ("remaining_seconds", "low_seconds", "high_seconds", "video_start_in", "video_ready_in")
        with self._lock:
            if value["generated_at"] < self._forecast_at:
                return
            saved = {}
            for item in items:
                identity = item["id"]
                row = value["items"].get(identity)
                if row is None:
                    continue
                # A new attempt/retry must not inherit an older attempt’s clock.
                runs = [(s, item["steps"][s].get("started_at"),
                         (item["steps"][s].get("timing") or {}).get("id")) for s in STAGES]
                key = fingerprint([scope, runs, item.get("delivery", {}).get("key")])
                previous_key, previous = self._forecasts.get(identity, (None, None))
                if previous_key == key:
                    for stage, estimate in row["steps"].items():
                        old = previous["steps"][stage]
                        if estimate["seconds"] is None and old["seconds"] is not None:
                            estimate.update({k: old[k] for k in ("seconds", "low", "high", "samples")})
                            estimate.update(retained=True, confidence="low", indicative=True,
                                            reason="Dernière estimation conservée · " + estimate["reason"])
                    if row["remaining_seconds"] is None and previous["remaining_seconds"] is not None:
                        row.update({k: previous[k] for k in fields})
                        row.update(retained=True, confidence="low",
                                   estimated_at=previous.get("estimated_at", self._forecast_at),
                                   indicative_reason="Dernière estimation conservée · " + (row["reason"] or "attente en cours"))
                if not row.get("retained"):
                    row["estimated_at"] = value["generated_at"]
                saved[identity] = (key, deepcopy(row))
            self._forecasts, self._forecast_at = saved, value["generated_at"]
        targets = [value["items"].get(k, {}) for k, member in cycle.get("members", {}).items()
                   if member["status"] in OPEN]
        for field in fields[:3]:
            value[field] = None if any(row.get(field) is None for row in targets) else max(
                (row[field] for row in targets), default=0)
        value["retained"] = any(row.get("retained") for row in targets)
        if value["retained"]:
            value.update(confidence="low", indicative_reason=next(
                row["indicative_reason"] for row in targets if row.get("retained")))

