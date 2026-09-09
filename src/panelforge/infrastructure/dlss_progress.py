"""Observe only the local execution; an unavailable progress socket never stops rendering."""

from contextlib import contextmanager
import json
import math
from threading import Event, Thread
import time


def progress_update(message, execution_id, stages):
    if not isinstance(message, str):
        return None
    try:
        event = json.loads(message)
    except ValueError:
        return None
    data = event.get("data") if isinstance(event, dict) else None
    if not isinstance(data, dict) or data.get("prompt_id") != execution_id:
        return None
    nodes = {stage["node"]: (index, stage) for index, stage in enumerate(stages)}
    candidates = []
    if event.get("type") == "progress_state" and isinstance(data.get("nodes"), dict):
        candidates = [(str(node), value) for node, value in data["nodes"].items() if isinstance(value, dict)]
    elif event.get("type") in {"progress", "executing"}:
        candidates = [(str(data.get("node")), data)]
    result = None
    for node, value in candidates:
        if node not in nodes or value.get("prompt_id", execution_id) != execution_id or value.get("state") == "pending":
            continue
        index, stage = nodes[node]
        amount, maximum = value.get("value"), value.get("max")
        valid = all(type(v) in (int, float) and math.isfinite(v) for v in (amount, maximum))
        percent = min(100, max(0, amount / maximum * 100)) if valid and maximum > 0 else None
        if result is None or index >= result["stage_index"]:
            result = {"stage": stage["key"], "label": stage["label"], "stage_index": index,
                      "stage_count": len(stages), "percent": percent}
    return result


class ComfyDlssProgress:
    def __init__(self, url, *, connector=None):
        self.url = url
        self.connector = connector or _connect

    @contextmanager
    def watch(self, execution_id, stages, publish):
        stop, connected = Event(), Event()

        def follow():
            last_sent, last_value = 0, None
            while not stop.is_set():
                try:
                    with self.connector(self.url) as socket:
                        connected.set()
                        while not stop.is_set():
                            try:
                                message = socket.recv(timeout=0.5)
                            except TimeoutError:
                                continue
                            value = progress_update(message, execution_id, stages)
                            if value is None:
                                continue
                            now = time.monotonic()
                            changed_stage = last_value is None or value["stage"] != last_value["stage"]
                            if changed_stage or now - last_sent >= 0.5 or value["percent"] == 100:
                                publish(value)
                                last_sent, last_value = now, value
                except Exception:
                    connected.set()  # Rendering is independent of this optional connection.
                    stop.wait(2)

        thread = Thread(target=follow, name="panelforge-dlss-progress", daemon=True)
        thread.start()
        connected.wait(1)
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=4)


def _connect(url):
    from websockets.sync.client import connect
    return connect(url, open_timeout=3, close_timeout=0.5, max_size=2**20)
