"""Durable preparation and non-preemptive, ordered factory dispatch."""
from copy import deepcopy
from threading import Event, RLock, Thread
from uuid import uuid4
import time

from panelforge.domain.video_factory import (
    STAGES, PRESETS, configuration, fingerprint, initial_steps, invalidate, merge_settings,
    new_item, next_steps, readiness, settle, timestamp, validate_shape, apply_preset,
)


class FactoryConflict(ValueError):
    pass


class FactoryWait(Exception):
    pass


class FactoryCancelled(Exception):
    pass


class VideoFactoryService:
    def __init__(self, *, store, adapter, coordinator=None, interval=0.5):
        self.store, self.adapter, self.coordinator = store, adapter, coordinator
        self.interval = interval
        self._lock = RLock()
        self._state = store.load()
        self._workers = {}
        self._stop = Event()
        self._wake = Event()
        self._thread = None
        self._scheduler_error = None
        # Restart reconciliation uses persisted child IDs, never blind resubmission.
        for item in self._state["items"]:
            if item["status"] in {"queued", "active"}:
                for stage, step in item["steps"].items():
                    if step["status"] == "running":
                        child_key = "attempt_id" if stage == "video" else "dlss_job_id"
                        if stage in {"video", "dlss"} and item["runtime"].get(child_key):
                            step.update(status="pending", error=None)
                            item["recover_stage"] = stage
                        else:
                            step.update(status="failed", error="Étape interrompue au redémarrage. Reprendre la chaîne.")
                if item["cancel_requested"] and not item.get("recover_stage"):
                    for step in item["steps"].values():
                        if step["status"] == "pending":
                            step["status"] = "cancelled"
                settle(item)

    def _save(self, items=()):
        for item in items:
            item["revision"] += 1
            item["updated_at"] = timestamp()
        self._state["revision"] += 1
        self.store.save(self._state)

    def _get(self, identity):
        value = next((item for item in self._state["items"] if item["id"] == identity), None)
        if value is None:
            raise FileNotFoundError("Traitement introuvable.")
        return value

    def _selected(self, identities, revisions=None):
        if not identities or len(identities) != len(set(identities)) or len(identities) > 500:
            raise ValueError("Sélection invalide (1 à 500 éléments).")
        items = [self._get(identity) for identity in identities]
        if revisions is None:
            raise FactoryConflict("La révision de chaque ligne est requise. Actualisez la sélection.")
        for item in items:
            if revisions is not None and revisions.get(item["id"]) != item["revision"]:
                raise FactoryConflict("Un traitement a changé. Actualisez la sélection.")
        return items

    def snapshot(self):
        with self._lock:
            result = deepcopy(self._state)
        for item in result["items"]:
            item["issues"] = readiness(item["config"]) + item.get("source_issues", [])
            item["ready"] = not item["issues"]
        machines = deepcopy(getattr(self.adapter, "machines", {}))
        for item in result["items"]:
            if item["status"] == "queued" and not item.get("waiting_reason"):
                steps = next_steps(item)
                lane = self.adapter.lane(item, steps[0]) if steps else None
                machine = machines.get(lane, {})
                item["waiting_reason"] = ("File en pause" if result["paused"] else
                    "Refroidissement de la machine" if machine.get("state") in {"cooling", "hot"} else
                    "Machine en pause" if machine.get("paused") else
                    "Machine indisponible · vérifier le moniteur" if machine.get("state") == "unavailable" else
                    "Attend la machine locale" if lane == "local_gpu" else "Attend le serveur")
        result.update(presets=PRESETS, machines=machines, scheduler_error=self._scheduler_error)
        return result

    def receive(self, entries):
        if not entries or len(entries) > 500:
            raise ValueError("Envoi vide ou trop volumineux.")
        with self._lock:
            added = []
            prepared = []
            for entry in entries:
                config = merge_settings(configuration(entry.get("config", {}).get("mode", "h3")), entry.get("config", {}))
                validate_shape(config)
                self.adapter.validate(config)
                source = entry.get("source", {})
                key = fingerprint({"source": source, "config": config})
                existing = next((i for i in self._state["items"] + prepared if i["dedupe_key"] == key), None)
                if existing:
                    added.append(existing["id"])
                    continue
                item = new_item(str(entry.get("name") or "Vidéo à préparer"), config, source, key)
                item["source_issues"] = entry.get("issues", [])
                item["runtime"] = deepcopy(entry.get("runtime", {}))
                for stage, output in entry.get("outputs", {}).items():
                    if stage in STAGES:
                        item["steps"][stage].update(status="succeeded", output=deepcopy(output))
                prepared.append(item)
                added.append(item["id"])
            self._state["items"].extend(prepared)
            self._save()
            return dict(ids=added, added=len(prepared), state=self.snapshot())

    def update(self, identities, revisions, changes=None, preset=None, replacements=None):
        with self._lock:
            items = self._selected(identities, revisions)
            if any(i["status"] != "preparation" for i in items):
                raise FactoryConflict("Remettez les lignes en préparation avant de modifier leurs réglages.")
            if replacements is None and set(changes or {}) - {"name", *configuration().keys()}:
                raise ValueError("Réglage inconnu.")
            pending, undo = [], {}
            for item in items:
                candidate = deepcopy(item)
                undo[item["id"]] = {"name": item["name"], "config": deepcopy(item["config"])}
                before = candidate["config"]
                if replacements is not None:
                    replacement = replacements.get(item["id"])
                    if not isinstance(replacement, dict):
                        raise ValueError("Valeurs d’annulation manquantes.")
                    candidate["name"] = str(replacement["name"])[:160]
                    candidate["config"] = deepcopy(replacement["config"])
                elif preset is not None:
                    candidate["config"] = apply_preset(before, preset, item["source_config"])
                else:
                    patch = dict(changes or {})
                    name = patch.pop("name", None)
                    if name is not None:
                        if len(items) != 1 or not isinstance(name, str) or not name.strip():
                            raise ValueError("Renommez une ligne à la fois.")
                        candidate["name"] = name[:160]
                    config = merge_settings(before, patch)
                    if "mode" in patch and config["mode"] != before["mode"]:
                        mode_defaults = configuration(config["mode"])
                        for key in ("profile", "cookbook", "cinematic_settings", "combat_settings", "sensual_settings"):
                            config[key] = mode_defaults[key]
                    if "shot_count" in patch:
                        for key in ("cinematic_settings", "sensual_settings", "combat_settings"):
                            if isinstance(config.get(key), dict):
                                config[key]["shot_count"] = patch["shot_count"]
                    substantive = {key for key in patch if config.get(key) != before.get(key)} - {"preset", "preset_origin"}
                    if substantive:
                        config["preset_origin"] = before.get("preset_origin") or before["preset"]
                        config["preset"] = "custom"
                    candidate["config"] = config
                changed_inputs = {key for key in candidate["config"] if candidate["config"][key] != before.get(key)} - {
                    "render", "dlss", "social", "preset", "preset_origin", "final_prompt"}
                if changed_inputs and candidate["config"]["final_prompt"] == before["final_prompt"]:
                    candidate["config"]["final_prompt"] = ""
                validate_shape(candidate["config"])
                self.adapter.validate(candidate["config"])
                affected = invalidate(candidate, before)
                if affected:
                    candidate["source_issues"] = self.adapter.source_issues(candidate)
                pending.append(candidate)
            for old, replacement in zip(items, pending):
                old.clear()
                old.update(replacement)
            self._save(items)
            return dict(state=self.snapshot(), undo=undo, revisions={i["id"]: i["revision"] for i in items})

    def launch(self, identities, revisions):
        with self._lock:
            items = self._selected(identities, revisions)
            for item in items:
                if item["status"] != "preparation":
                    raise FactoryConflict("Cette sélection contient déjà une production.")
                errors = readiness(item["config"]) + self.adapter.source_issues(item)
                if errors:
                    raise ValueError(f"{item['name']} : {' '.join(errors)}")
                self.adapter.validate(item["config"], launching=True)
            for item in items:
                item.update(status="queued", cancel_requested=False, source_issues=[],
                            launch_snapshot=deepcopy(item["config"]), launched_at=timestamp())
                for stage in STAGES:
                    if item["steps"][stage]["status"] in {"failed", "cancelled"}:
                        item["steps"][stage] = initial_steps(item["config"])[stage]
                        item["runtime"]["explicit_retry"] = True
                settle(item)
            self._save(items)
        self._wake.set()
        return self.snapshot()

    def action(self, action, identities=(), revisions=None):
        cancel = []
        with self._lock:
            if action in {"pause", "resume"}:
                self._state["paused"] = action == "pause"
                self._save()
            else:
                # Cancellation targets identities, not a stale progress revision.
                # Keep revision guards for configuration and other state transitions.
                if action == "cancel" and revisions is not None:
                    revisions = {identity: self._get(identity)["revision"] for identity in identities}
                items = self._selected(list(identities), revisions)
                active = {identity for identity, _ in self._workers.values()}
                if action in {"edit", "remove"} and any(i["id"] in active for i in items):
                    raise FactoryConflict("Une étape est active. Attendez sa fin ou annulez-la.")
                if action == "remove" and any(i["status"] != "preparation" for i in items):
                    raise FactoryConflict("Seuls les éléments en préparation peuvent être retirés.")
                if action == "cancel" and any(i["status"] not in {"queued", "active"} for i in items):
                    raise FactoryConflict("Seuls les traitements en production peuvent être annulés.")
                if action == "edit" and any(i.get("recover_stage") for i in items):
                    raise FactoryConflict("La reprise du traitement actif est en cours. Attendez son résultat.")
                if action == "retry" and any(i["status"] not in {"failed", "cancelled"} for i in items):
                    raise FactoryConflict("Seules les chaînes en erreur ou annulées peuvent être reprises.")
                if action == "edit":
                    for item in items:
                        item.update(status="preparation", cancel_requested=False, waiting_reason=None)
                elif action == "remove":
                    self._state["items"] = [i for i in self._state["items"] if i not in items]
                elif action == "duplicate":
                    for item in items:
                        duplicate = new_item(item["name"] + " · copie", item["config"], item["source"], uuid4().hex)
                        duplicate["source_config"] = deepcopy(item["source_config"])
                        duplicate["source_issues"] = deepcopy(item.get("source_issues", []))
                        self._state["items"].append(duplicate)
                elif action == "retry":
                    for item in items:
                        for stage in STAGES:
                            if item["steps"][stage]["status"] in {"failed", "cancelled"}:
                                item["steps"][stage].update(status="pending", error=None, progress=None)
                        item.update(status="queued", cancel_requested=False, waiting_reason=None)
                        item["runtime"]["explicit_retry"] = True
                elif action == "cancel":
                    for item in items:
                        item["cancel_requested"] = True
                        for step in item["steps"].values():
                            if step["status"] == "pending":
                                step["status"] = "cancelled"
                        settle(item)
                        if item["id"] in active:
                            cancel.append(deepcopy(item))
                else:
                    if action not in {"edit", "remove", "duplicate", "retry", "cancel"}:
                        raise ValueError("Action inconnue.")
                self._save(items)
        for item in cancel:
            Thread(target=self._cancel_external, args=(item,), daemon=True).start()
        self._wake.set()
        return self.snapshot()

    def _cancel_external(self, item):
        try:
            self.adapter.cancel(item)
        except Exception as error:
            with self._lock:
                current = self._get(item["id"])
                current["waiting_reason"] = f"Arrêt demandé : {error}"
                self._save((current,))

    def refresh_source(self, identity, revisions):
        with self._lock:
            item = self._selected([identity], revisions)[0]
            if item["status"] != "preparation" or item["source"].get("kind") != "episode":
                raise FactoryConflict("Seule une scène en préparation peut être rechargée.")
            entry = self.adapter.capture_episode(item["source"]["id"], [item["source"]["scene_id"]])[0]
            before = item["config"]
            item["config"] = deepcopy(entry["config"])
            invalidate(item, before)
            item["source_config"] = deepcopy(entry["config"])
            item["source_issues"] = entry.get("issues", [])
            item["runtime"] = deepcopy(entry.get("runtime", {}))
            item["steps"] = initial_steps(item["config"])
            for stage, output in entry.get("outputs", {}).items():
                item["steps"][stage].update(status="succeeded", output=deepcopy(output))
            self._save((item,))
        return self.snapshot()

    def reorder(self, identities, expected_revision):
        with self._lock:
            if self._state["revision"] != expected_revision:
                raise FactoryConflict("La file a changé. Actualisez son ordre.")
            if len(identities) != len(set(identities)) or set(identities) != {i["id"] for i in self._state["items"]}:
                raise ValueError("L’ordre doit contenir chaque traitement une seule fois.")
            self._state["items"] = [self._get(identity) for identity in identities]
            self._save()
        self._wake.set()
        return self.snapshot()

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            claim = getattr(self.store, "claim", None)
            if claim:
                claim()
            self._stop.clear()
            self._thread = Thread(target=self._loop, name="panelforge-video-factory", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread:
            thread.join(timeout=3)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.dispatch()
                self._scheduler_error = None
            except Exception as error:
                self._scheduler_error = str(error)
            self._wake.wait(self.interval)
            self._wake.clear()

    def dispatch(self):
        # Existing machine leases remain authoritative; never flood their FIFO.
        available = self.adapter.available_lanes()
        with self._lock:
            if self._stop.is_set():
                return
            active_ids = {identity for identity, _ in self._workers.values()}
            for lane in ("local_gpu", "remote_gpu"):
                if lane in self._workers:
                    continue
                recoverable = getattr(self.adapter, "recoverable", lambda item, stage: False)
                choice = next(((item, item["recover_stage"]) for item in self._state["items"]
                               if item["id"] not in active_ids and item.get("recover_stage")
                               and recoverable(item, item["recover_stage"])
                               and self.adapter.lane(item, item["recover_stage"]) == lane), None)
                if choice is None and lane in available and not self._state["paused"]:
                    choice = next(((item, stage) for item in self._state["items"]
                                   if item["id"] not in active_ids and item.get("retry_after", 0) <= time.time()
                                   for stage in next_steps(item)
                                   if self.adapter.lane(item, stage) == lane), None)
                if choice is None:
                    continue
                item, stage = choice
                item.update(status="active", waiting_reason=None)
                item["steps"][stage].update(status="running", started_at=timestamp(), error=None)
                self._workers[lane] = (item["id"], stage)
                active_ids.add(item["id"])
                self._save((item,))
                Thread(target=self._execute, args=(lane, item["id"], stage), daemon=True,
                       name=f"factory-{stage}-{item['id'][-8:]}").start()

    def _execute(self, lane, identity, stage):
        def cancelled():
            with self._lock:
                return self._get(identity)["cancel_requested"]

        def checkpoint(**values):
            with self._lock:
                item = self._get(identity)
                item["runtime"].update(deepcopy(values))
                self._save((item,))

        def progress(message, value=None):
            with self._lock:
                item = self._get(identity)
                step = item["steps"][stage]
                if step.get("message") == message and step.get("progress") == value:
                    return
                step.update(message=str(message)[:400], progress=value)
                self._save((item,))

        try:
            with self._lock:
                snapshot = deepcopy(self._get(identity))
            output = self.adapter.run(snapshot, stage, checkpoint, cancelled, progress)
            outcome, error = "succeeded", None
        except FactoryWait as exc:
            output, outcome, error = {}, "pending", str(exc)
        except FactoryCancelled:
            output, outcome, error = {}, "cancelled", "Annulé."
        except Exception as exc:
            output, outcome, error = {}, "failed", str(exc) or type(exc).__name__
        with self._lock:
            item = self._get(identity)
            if item["cancel_requested"] and outcome in {"pending", "failed"}:
                outcome, error = "cancelled", "Annulé."
            item["steps"][stage].update(status=outcome, error=error, output=output, finished_at=timestamp())
            if outcome == "pending":
                item["waiting_reason"] = error
                item["retry_after"] = time.time() + 2
            else:
                item.pop("recover_stage", None)
                item.pop("retry_after", None)
                item["waiting_reason"] = None
            settle(item)
            self._workers.pop(lane, None)
            self._save((item,))
        self._wake.set()
