"""One read-only ComfyUI event connection for batch sampler progress."""
import json
import logging
from threading import Event, Lock, Thread

logger = logging.getLogger(__name__)


class CreationBatchProgress:
    def __init__(self, assisted, *, connector=None):
        self.assisted = assisted
        self.connector = connector
        self._lock = Lock()
        self._stop, self._wake = Event(), Event()
        self._plans = {}
        self._reported = {}
        self._thread = None
        self._current = None
        self._node = None

    def watch(self, project_id, attempt):
        owner = f"krea2:{project_id}:{attempt.attempt_id}"
        with self._lock:
            if attempt.status.value in {"succeeded", "failed", "cancelled"}:
                self._plans.pop(owner, None)
                self._reported.pop(owner, None)
                return
            if owner not in self._plans:
                plan = self.assisted.render_progress_plan(attempt)
                if not plan:
                    return
                self._plans[owner] = plan
            if not self._thread or not self._thread.is_alive():
                self._stop.clear()
                self._thread = Thread(target=self._loop, name="creation-batch-progress", daemon=True)
                self._thread.start()
        self._wake.set()

    def forget(self, project_id, attempt_id):
        owner = f"krea2:{project_id}:{attempt_id}"
        with self._lock:
            self._plans.pop(owner, None)
            self._reported.pop(owner, None)

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        from websockets.sync.client import connect
        while not self._stop.is_set():
            with self._lock:
                pending = bool(self._plans)
            if not pending:
                self._wake.wait(2)
                self._wake.clear()
                continue
            try:
                with (self.connector or connect)(self.assisted.comfy.websocket_url,
                        open_timeout=5, close_timeout=1, max_size=16 * 1024 * 1024) as socket:
                    self._current = self._node = None
                    while not self._stop.is_set():
                        with self._lock:
                            if not self._plans:
                                break
                        try:
                            raw = socket.recv(timeout=1)
                        except TimeoutError:
                            continue
                        if isinstance(raw, str):
                            try:
                                self.consume(json.loads(raw))
                            except (ValueError, TypeError, KeyError):
                                continue
            except Exception:
                logger.debug("Batch progress channel unavailable; retaining stage monitoring", exc_info=True)
                self._stop.wait(3)

    def consume(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return
        data, kind = payload["data"], payload.get("type")
        if kind not in {"executing", "progress", "progress_state", "execution_start"}:
            return
        coordinator = self.assisted.work_coordinator
        activities = coordinator.activity_statuses()
        event_id = data.get("prompt_id")
        if isinstance(event_id, str):
            if event_id != self._current:
                self._node = None
            self._current = event_id
        if kind == "execution_start":
            self._node = None
        if not self._current:
            return
        owner = next((key for key, value in activities.items()
                      if value.get("execution_id") == self._current and value.get("status") == "running"), None)
        with self._lock:
            plan = self._plans.get(owner)
        if not plan:
            return
        if kind == "executing":
            self._node = str(data["node"]) if data.get("node") is not None else None
            return
        if kind == "progress_state":
            nodes = data.get("nodes")
            if not isinstance(nodes, dict):
                return
            for node, state in nodes.items():
                if isinstance(state, dict) and state.get("state") != "pending" and state.get("prompt_id", self._current) == self._current:
                    self._report(coordinator, owner, plan, str(node), state)
        elif kind == "progress":
            node = str(data["node"]) if data.get("node") is not None else self._node
            self._report(coordinator, owner, plan, node, data)

    def _report(self, coordinator, owner, plan, node, data):
        current, maximum = data.get("value"), data.get("max")
        if type(current) not in {int, float} or type(maximum) not in {int, float}:
            return
        offset, total = 0, sum(steps for _, steps, _ in plan)
        for identity, steps, label in plan:
            if node == identity and maximum == steps and 0 <= current <= maximum:
                # Sampling occupies 8–80%; later workflow finishing/import retain their own milestones.
                progress = .08 + .72 * (offset + current) / total
                with self._lock:
                    if progress < self._reported.get(owner, 0):
                        return
                    self._reported[owner] = progress
                coordinator.report_progress(owner, progress, f"{label} · étape {int(current)}/{steps}")
                return
            offset += steps
