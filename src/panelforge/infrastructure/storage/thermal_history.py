"""Small append-only journal for the scheduler's rolling thermal history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import math
import os
from pathlib import Path
import tempfile
from threading import RLock

from panelforge.domain.production import ComputeResource, ProductionWorkload


_SCHEMA_VERSION = 1
_RETENTION = timedelta(hours=24)
_COMPACTION_INTERVAL = timedelta(hours=1)
_EVENT_WORKLOADS = {
    ProductionWorkload.LLM,
    ProductionWorkload.IMAGE_RENDER,
    ProductionWorkload.VIDEO_RENDER,
    ProductionWorkload.DLSS,
}
_EVENT_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


class LocalThermalHistoryStore:
    """Persist bounded temperature buckets and scheduler events as JSONL."""

    def __init__(self, workspace) -> None:
        root = Path(workspace).resolve() / "system"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "thermal-history.jsonl"
        self._lock = RLock()
        self._last_compacted_at: datetime | None = None

    def record_sample(
        self,
        observed_at: datetime,
        *,
        local_temperature_c: float | None,
        remote_temperature_c: float | None,
    ) -> None:
        observed_at = _utc(observed_at, "sample timestamp")
        record = {
            "schema_version": _SCHEMA_VERSION,
            "type": "sample",
            "at": _iso(observed_at),
            ComputeResource.LOCAL_GPU.value: _temperature(local_temperature_c),
            ComputeResource.REMOTE_GPU.value: _temperature(remote_temperature_c),
        }
        self._append(record, observed_at)

    def record_event_start(
        self,
        event_id: str,
        *,
        resource: ComputeResource,
        workload: ProductionWorkload,
        operation: str,
        started_at: datetime,
    ) -> None:
        if not isinstance(resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if workload not in _EVENT_WORKLOADS:
            raise ValueError("workload is not a visible thermal event")
        started_at = _utc(started_at, "event start")
        record = {
            "schema_version": _SCHEMA_VERSION,
            "type": "event_start",
            "event_id": _text(event_id, "event id", 160),
            "resource": resource.value,
            "workload": workload.value,
            "operation": _text(operation, "operation", 200),
            "started_at": _iso(started_at),
        }
        self._append(record, started_at)

    def record_event_finish(
        self,
        event_id: str,
        *,
        finished_at: datetime,
        status: str,
        peak_temperature_c: float | None,
    ) -> None:
        if status not in _EVENT_STATUSES:
            raise ValueError("unsupported thermal event status")
        finished_at = _utc(finished_at, "event finish")
        record = {
            "schema_version": _SCHEMA_VERSION,
            "type": "event_finish",
            "event_id": _text(event_id, "event id", 160),
            "finished_at": _iso(finished_at),
            "status": status,
            "peak_temperature_c": _temperature(peak_temperature_c),
        }
        self._append(record, finished_at)

    def recover_open_events(self, observed_at: datetime) -> None:
        """Close events left open by a previous process without hiding the gap."""
        observed_at = _utc(observed_at, "recovery timestamp")
        with self._lock:
            records = self._read_records_unlocked()
            opened = {
                value.get("event_id")
                for value in records
                if value.get("type") == "event_start" and isinstance(value.get("event_id"), str)
            }
            closed = {
                value.get("event_id")
                for value in records
                if value.get("type") == "event_finish" and isinstance(value.get("event_id"), str)
            }
            for event_id in sorted(opened - closed):
                self.record_event_finish(
                    event_id,
                    finished_at=observed_at,
                    status="interrupted",
                    peak_temperature_c=None,
                )

    def load(self, *, since: datetime, until: datetime) -> dict[str, list[dict[str, object]]]:
        since = _utc(since, "history start")
        until = _utc(until, "history end")
        if since >= until:
            raise ValueError("history start must be before history end")
        with self._lock:
            records = self._read_records_unlocked()

        samples_by_time: dict[str, dict[str, object]] = {}
        starts: dict[str, dict[str, object]] = {}
        finishes: dict[str, dict[str, object]] = {}
        for value in records:
            kind = value.get("type")
            if kind == "sample":
                observed_at = _parse_timestamp(value.get("at"))
                if observed_at is None or not since <= observed_at <= until:
                    continue
                timestamp = _iso(observed_at)
                sample = samples_by_time.setdefault(timestamp, {"timestamp": timestamp})
                for resource in ComputeResource:
                    temperature = _stored_temperature(value.get(resource.value))
                    if temperature is not None:
                        previous = sample.get(resource.value)
                        sample[resource.value] = max(float(previous or temperature), temperature)
            elif kind == "event_start":
                event_id = value.get("event_id")
                if isinstance(event_id, str):
                    starts[event_id] = value
            elif kind == "event_finish":
                event_id = value.get("event_id")
                if isinstance(event_id, str):
                    finishes[event_id] = value

        events: list[dict[str, object]] = []
        for event_id, start in starts.items():
            started_at = _parse_timestamp(start.get("started_at"))
            if started_at is None or not since <= started_at <= until:
                continue
            resource = start.get("resource")
            workload = start.get("workload")
            operation = start.get("operation")
            if resource not in {value.value for value in ComputeResource}:
                continue
            if workload not in {value.value for value in _EVENT_WORKLOADS}:
                continue
            if not isinstance(operation, str) or not operation.strip():
                continue
            finish = finishes.get(event_id, {})
            finished_at = _parse_timestamp(finish.get("finished_at"))
            status = finish.get("status") if finish.get("status") in _EVENT_STATUSES else "running"
            peak = _stored_temperature(finish.get("peak_temperature_c"))
            events.append({
                "id": event_id,
                "resource": resource,
                "workload": workload,
                "operation": operation,
                "started_at": _iso(started_at),
                "finished_at": _iso(finished_at) if finished_at is not None else None,
                "status": status,
                "peak_temperature_c": peak,
            })

        samples = [samples_by_time[key] for key in sorted(samples_by_time)]
        events.sort(key=lambda value: (str(value["started_at"]), str(value["id"])))
        return {"samples": samples, "events": events}

    def _append(self, record: dict[str, object], observed_at: datetime) -> None:
        content = (json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            with self.path.open("a+b") as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell() > 0:
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) != b"\n":
                        stream.write(b"\n")
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if (
                self._last_compacted_at is None
                or observed_at - self._last_compacted_at >= _COMPACTION_INTERVAL
            ):
                self._compact_unlocked(observed_at)
                self._last_compacted_at = observed_at

    def _compact_unlocked(self, observed_at: datetime) -> None:
        records = self._read_records_unlocked()
        cutoff = observed_at - _RETENTION
        retained_starts = {
            value.get("event_id")
            for value in records
            if value.get("type") == "event_start"
            and isinstance(value.get("event_id"), str)
            and (_parse_timestamp(value.get("started_at")) or datetime.min.replace(tzinfo=UTC)) >= cutoff
        }
        retained: list[dict[str, object]] = []
        for value in records:
            kind = value.get("type")
            if kind == "sample":
                timestamp = _parse_timestamp(value.get("at"))
                if timestamp is not None and timestamp >= cutoff:
                    retained.append(value)
            elif kind == "event_start" and value.get("event_id") in retained_starts:
                retained.append(value)
            elif kind == "event_finish" and value.get("event_id") in retained_starts:
                retained.append(value)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                for value in retained:
                    stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_records_unlocked(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                if len(line) > 16_384:
                    continue
                try:
                    value = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, dict) and value.get("schema_version") == _SCHEMA_VERSION:
                    records.append(value)
        return records


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _temperature(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("temperature must be finite or None")
    if not 0 <= float(value) <= 150:
        raise ValueError("temperature must be between 0 and 150")
    return round(float(value), 1)


def _stored_temperature(value) -> float | None:
    try:
        return _temperature(value)
    except ValueError:
        return None


def _text(value: str, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()[:maximum]


__all__ = ["LocalThermalHistoryStore"]
