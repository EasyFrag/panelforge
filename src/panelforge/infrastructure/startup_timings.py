"""Bounded, best-effort startup observations; never change service ordering."""
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
from threading import Lock
from time import perf_counter, thread_time


class StartupTimings:
    def __init__(self, workspace):
        self.path = Path(workspace) / "system" / "startup-timings.jsonl"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started = self.previous = perf_counter()
        self.previous_cpu = thread_time()
        self.phases = []
        self.finished = False
        self._lock = Lock()

    def mark(self, name):
        now, cpu = perf_counter(), thread_time()
        if len(self.phases) < 64:
            self.phases.append(dict(name=name, duration_ms=round((now-self.previous)*1000, 3),
                                    cpu_ms=round((cpu-self.previous_cpu)*1000, 3)))
        self.previous, self.previous_cpu = now, cpu

    @contextmanager
    def phase(self, name):
        start, cpu = perf_counter(), thread_time()
        status = "returned"
        try:
            yield
        except BaseException:
            status = "failed"
            raise
        finally:
            if len(self.phases) < 64:
                self.phases.append(dict(name=name, duration_ms=round((perf_counter()-start)*1000, 3),
                                        cpu_ms=round((thread_time()-cpu)*1000, 3), status=status))

    def finish(self, status):
        with self._lock:
            if self.finished:
                return
            self.finished = True
            record = dict(schema_version=1, process_id=os.getpid(), started_at=self.started_at,
                          scope="build_app_and_lifespan", status=status, phases=self.phases,
                          duration_ms=round((perf_counter()-self.started)*1000, 3))
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= 256*1024:
                    os.replace(self.path, self.path.with_name(self.path.name+".1"))
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=True)+"\n")
            except OSError:
                pass  # Observability must never prevent startup, including a read-only disk.


def trace_startup_build(function):
    @wraps(function)
    def build(args):
        trace = StartupTimings(args.workspace)
        try:
            app = function(args, startup=trace)
            trace.mark("build.http_app")
            return app
        except BaseException:
            trace.mark("build.interrupted")
            trace.finish("failed")
            raise
    return build
