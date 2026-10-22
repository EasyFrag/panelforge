"""Bounded, optional timings carried by a worker or local operation's context.

No I/O here. The injected sink runs after the measured lease/lock is released.
Diagnostics never suppress or replace an application exception.
"""
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
import os
from threading import get_ident
import time
from uuid import uuid4


_current = ContextVar("image_timings", default=None)
MAX_PHASES = 96
_FIELDS = {"status", "execution_id", "resumed", "queue_wait_ms", "queue_age_ms",
           "server_execution_ms"}


def annotate(**values):
    record = _current.get()
    if record is not None:
        for key, value in values.items():
            if key in _FIELDS and isinstance(value, (str, int, float, bool)):
                record[key] = value[:160] if isinstance(value, str) else value


def queue_age(created, *, resumed=False):
    """Persisted queue age uses wall time; phase durations use a monotonic clock."""
    record = _current.get()
    if record is None or not created:
        return
    try:
        stamp = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp() if isinstance(created, str) else created
        age = round(max(0, record["_wall"] - stamp) * 1000, 3)
        annotate(resumed=resumed, **{"queue_age_ms" if resumed else "queue_wait_ms": age})
    except (TypeError, ValueError, OverflowError, OSError):
        pass


@contextmanager
def image_trace(sink, *, engine, project_id, attempt_id, kind="image",
                operation=None, min_duration_ms=0):
    if sink is None:
        token = _current.set(None)
        try:
            yield
        finally:
            _current.reset(token)
        return
    start = time.perf_counter()
    record = {"schema_version": 2, "trace_id": uuid4().hex, "engine": engine,
              "kind": kind, "operation": operation, "process_id": os.getpid(),
              "thread_id": get_ident(), "monotonic_start_ms": round(start * 1000, 3),
              "project_id": project_id, "attempt_id": attempt_id,
              "started_at": datetime.now(UTC).isoformat(), "status": "returned",
              "phases": [], "aggregates": {}, "dropped_phases": 0,
              "_start": start, "_wall": time.time()}
    token = _current.set(record)
    try:
        yield
    except BaseException as error:
        record.update(status="raised", error_type=type(error).__name__)
        raise
    finally:
        _current.reset(token)
        record["duration_ms"] = round((time.perf_counter() - record.pop("_start")) * 1000, 3)
        record.pop("_wall")
        if record["duration_ms"] >= min_duration_ms or record["status"] == "raised":
            try:
                sink(record)
            except Exception:
                # A full/unavailable diagnostic disk must not fail a generation.
                pass


@contextmanager
def phase(name, *, aggregate=False, cpu=False):
    record = _current.get()
    metrics = {}
    if record is None:
        yield metrics
        return
    start = time.perf_counter()
    cpu_start = time.thread_time() if cpu else None
    error_type = None
    try:
        yield metrics
    except BaseException as error:
        error_type = type(error).__name__
        raise
    finally:
        end = time.perf_counter()
        cpu_ms = (time.thread_time() - cpu_start) * 1000 if cpu_start is not None else None
        elapsed = (end - start) * 1000
        values = {"name": name, "start_ms": round((start - record["_start"]) * 1000, 3),
                  "end_ms": round((end - record["_start"]) * 1000, 3),
                  "duration_ms": round(elapsed, 3)}
        if error_type:
            values["error_type"] = error_type
        for key in ("bytes", "projects", "entries", "lock_id"):
            if isinstance(metrics.get(key), int):
                values[key] = metrics[key]
        if cpu_ms is not None:
            values["cpu_ms"] = round(cpu_ms, 3)
        if aggregate:
            groups = record["aggregates"]
            if name in groups or len(groups) < MAX_PHASES:
                group = groups.setdefault(name, {"count": 0, "duration_ms": 0, "max_ms": 0,
                                                "start_ms": values["start_ms"], "errors": 0})
                group["count"] += 1
                group["duration_ms"] = round(group["duration_ms"] + elapsed, 3)
                group["max_ms"] = round(max(group["max_ms"], elapsed), 3)
                group["end_ms"] = values["end_ms"]
                group["errors"] += bool(error_type)
                for key in ("bytes", "projects", "entries", "cpu_ms"):
                    if key in values:
                        group[key] = round(group.get(key, 0) + values[key], 3)
                if "lock_id" in values:
                    group["lock_id"] = values["lock_id"]
            else:
                record["dropped_phases"] += 1
        elif len(record["phases"]) < MAX_PHASES:
            record["phases"].append(values)
        else:
            record["dropped_phases"] += 1


def timed(name, *, aggregate=False, cpu=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if _current.get() is None:
                return function(*args, **kwargs)
            with phase(name, aggregate=aggregate, cpu=cpu):
                return function(*args, **kwargs)
        return wrapped
    return decorate


@contextmanager
def timed_lock(lock, name, *, sink=None, aggregate=False):
    """Preserve the original lock, recording wait and hold separately.

    Outside a worker, retain only slow (>=250 ms) or failing critical sections.
    Nested/reentrant sections reuse the outer context: no sink under the lock.
    """
    with ExitStack() as traces:
        if _current.get() is None and sink is not None:
            traces.enter_context(image_trace(
                sink, engine="krea2", project_id=None, attempt_id=None,
                kind="operation", operation=name, min_duration_ms=250,
            ))
        if _current.get() is None:
            with lock:
                yield
            return
        with ExitStack() as locks:
            with phase(f"{name}.lock_wait", aggregate=aggregate, cpu=True) as metrics:
                metrics["lock_id"] = id(lock)
                locks.enter_context(lock)
            with phase(f"{name}.lock_held", aggregate=aggregate, cpu=True) as metrics:
                metrics["lock_id"] = id(lock)
                yield


@contextmanager
def timed_lease(lease):
    with ExitStack() as stack:
        with phase("resource.wait"):
            stack.enter_context(lease)
        with phase("resource.owned"):
            yield


def observe_history(history, execution_id):
    """Use server-to-server timestamps, never subtract clocks across machines."""
    if _current.get() is None:
        return
    try:
        messages = history.get(execution_id, {}).get("status", {}).get("messages", [])
        stamps = {name: data["timestamp"] for name, data in messages
                  if isinstance(data, dict) and isinstance(data.get("timestamp"), (int, float))}
        start, end = stamps.get("execution_start"), stamps.get("execution_success")
        if start is not None and end is not None and end >= start:
            annotate(server_execution_ms=round(end - start, 3))
    except (AttributeError, TypeError, ValueError, KeyError):
        pass
