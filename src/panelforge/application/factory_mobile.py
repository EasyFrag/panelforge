"""Mobile supervision reuses the factory; it never starts its own GPU worker."""
from copy import deepcopy
from threading import Event, RLock, Thread
from hashlib import sha256
import time

from panelforge.domain.factory_mobile import mobile_view, media_asset, alert_conditions, number


class FactoryMobile:
    def __init__(self, factory, store, sender, *, clock=time.time):
        self.factory, self.store, self.sender, self.clock = factory, store, sender, clock
        self._lock, self._stop = RLock(), Event()
        self._thread = None
        self._media = {}
        self.warning = None
        try:
            self._subscriptions = self.store.load()
        except (OSError, ValueError, KeyError):
            self._subscriptions = {}
            self.warning = "Le journal des notifications est illisible."
        self._writable = self.warning is None

    def snapshot(self, result_limit=24):
        state = self.factory.snapshot()
        machines = deepcopy(getattr(self.factory.adapter, "monitor_snapshot", {}))
        value = mobile_view(state, machines, self.clock(), result_limit=result_limit)
        value["alerts"] = list(alert_conditions(value, value["thresholds"]).values())
        value["notification_warning"] = self.warning
        return value

    def command(self, action, ids, revisions, active_runs=None):
        if action not in {"pause", "resume", "stop", "retry"}:
            raise ValueError("Commande mobile inconnue.")
        if action in {"pause", "resume"} and ids:
            raise ValueError("Cette commande concerne la file.")
        if action == "retry" and len(ids) != 1:
            raise ValueError("Choisissez une seule vidéo à reprendre.")
        if action == "stop":
            self.factory.action(action, ids, revisions, active_runs=active_runs)
        else:
            self.factory.action(action, ids, revisions)
        return self.snapshot()

    def asset(self, identity, kind):
        # Only assets explicitly belonging to a factory card are reachable.
        state = self.factory.snapshot()
        item = next((i for i in state["items"] if i["id"] == identity and i["status"] != "preparation"), None)
        asset_id = media_asset(item, kind) if item else None
        if not asset_id:
            raise KeyError(identity)
        with self._lock:
            cached = self._media.get(asset_id)
        if cached:
            asset, path, signature = cached
            stat = path.stat()
            if signature == (stat.st_mtime_ns, stat.st_size):
                return asset, path
        assets = self.factory.adapter.assets
        asset, path = assets.get(asset_id), assets.verified_path(asset_id)
        stat = path.stat()
        with self._lock:
            if len(self._media) >= 96:
                self._media.pop(next(iter(self._media)))
            self._media[asset_id] = (asset, path, (stat.st_mtime_ns, stat.st_size))
        return asset, path

    def push_config(self, identity=None):
        with self._lock:
            entry = deepcopy(self._subscriptions.get(identity))
        return dict(available=bool(self.sender.available) and self._writable,
                    public_key=self.sender.public_key if self.sender.available else None,
                    registered=entry is not None, thresholds=entry.get("thresholds") if entry else None,
                    last_error=entry.get("last_error") if entry else None,
                    warning=self.warning or self.sender.warning)

    def subscribe(self, subscription, thresholds, origin):
        if not self.sender.available or not self._writable:
            raise ValueError(self.warning or self.sender.warning or "Notifications indisponibles.")
        self.sender.validate(subscription)
        view = self.snapshot()
        identity = sha256(subscription["endpoint"].encode()).hexdigest()
        baseline = {key: self.clock() for key, alert in alert_conditions(view, thresholds).items()
                    if alert["kind"] != "temperature"}
        with self._lock:
            if identity not in self._subscriptions and len(self._subscriptions) >= 10:
                raise ValueError("Dix appareils sont déjà inscrits.")
            previous = self._subscriptions.get(identity, {})
            updated = deepcopy(self._subscriptions)
            updated[identity] = dict(subscription=deepcopy(subscription),
                thresholds=deepcopy(thresholds), origin=origin, sent=previous.get("sent", baseline),
                active=previous.get("active", []), retry_at=0, last_error=None)
            self.store.save(updated)
            self._subscriptions = updated
        return dict(id=identity, registered=True)

    def unsubscribe(self, identity):
        with self._lock:
            if identity in self._subscriptions:
                updated = deepcopy(self._subscriptions)
                del updated[identity]
                self.store.save(updated)
                self._subscriptions = updated

    def start(self):
        if self._thread is None:
            self._stop.clear()
            self._thread = Thread(target=self._loop, name="factory-mobile-alerts", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=7)
        self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.notify_once()
            except Exception:
                self.warning = "Le suivi des notifications est momentanément indisponible."
            self._stop.wait(5)

    def notify_once(self):
        with self._lock:
            entries = deepcopy(self._subscriptions)
        if not entries or not self.sender.available:
            return
        view, now = self.snapshot(), self.clock()
        for identity, entry in entries.items():
            if self._stop.is_set():
                return
            alerts = alert_conditions(view, entry["thresholds"], entry.get("active", []))
            # Missing/stale telemetry cannot rearm a temperature alert.
            active = set(alerts)
            unknown = {m["id"] for m in view["machines"] if not number(m["temperature_c"])}
            active.update(k for k in entry.get("active", []) if k.startswith("temperature:") and
                          (view["stale"] or k.split(":")[1] in unknown))
            sent = entry.get("sent", {})
            for key in list(sent):
                if key.startswith("temperature:") and key not in active:
                    del sent[key]
            if now >= entry.get("retry_at", 0):
                for key, alert in alerts.items():
                    if self._stop.is_set():
                        return
                    if key in sent:
                        continue
                    outcome = self.sender.send(entry["subscription"], alert, entry["origin"])
                    if outcome == "expired":
                        self.unsubscribe(identity)
                        entry = None
                        break
                    if outcome != "sent":
                        entry.update(retry_at=now + 60, last_error="Envoi différé ; nouvelle tentative dans une minute.")
                        break
                    sent[key] = now
                    entry.update(retry_at=0, last_error=None)
            if entry is None:
                continue
            if not active:
                entry.update(retry_at=0, last_error=None)
            entry.update(active=sorted(active), sent={key: stamp for key, stamp in sent.items() if key in active})
            with self._lock:
                current = self._subscriptions.get(identity)
                # Do not overwrite an unsubscribe or changed preferences during I/O.
                if current and current["thresholds"] == entry["thresholds"] and current["subscription"] == entry["subscription"]:
                    if current != entry:
                        self._subscriptions[identity] = entry
                        self.store.save(self._subscriptions)
