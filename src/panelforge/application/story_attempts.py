"""Durable call accounting and draft provenance, independent of workflow resumes."""
from copy import deepcopy
from datetime import UTC, datetime


def archive_job(project):
    job = project.get("job") or {}
    if not job.get("draft") and not job.get("format_repair", {}).get("draft"):
        return
    history = project.setdefault("draft_history", [])
    if any(item.get("request_id") == job.get("request_id") for item in history):
        return
    keys = ("request_id", "operation", "status", "call_id", "draft", "original_draft", "normalized_draft", "format_repair",
            "error", "source_error", "draft_diagnostics", "narrative_input_hash", "response_contract_version",
            "started_at", "finished_at", "feedback_target", "model_role", "normalizations", "output_mode")
    history.append({key: deepcopy(job[key]) for key in keys if key in job})


def begin(project, request, identity):
    usage = project.setdefault("llm_usage", dict(calls=0, elapsed_ms=0, repair_calls=0,
        since=datetime.now(UTC).isoformat(), earlier_calls_unknown=bool(project.get("turns"))))
    history = project.setdefault("llm_attempts", [])
    if any(item["id"] == identity for item in history):
        return
    usage["calls"] += 1
    usage["repair_calls"] += int("repair_json" in request.operation_id or "repair_contract" in request.operation_id)
    history.append(dict(id=identity, operation=request.operation_id, model_id=request.model_id,
        started_at=datetime.now(UTC).isoformat(), status="running", call_id=None, elapsed_ms=0))


def finish(project, identity, *, call_id, elapsed_ms, accepted, error=None):
    entry = next((item for item in project.get("llm_attempts", []) if item["id"] == identity), None)
    if entry is None or entry["status"] != "running":
        return
    entry.update(status="accepted" if accepted else "rejected", call_id=call_id,
        elapsed_ms=elapsed_ms, error=error, finished_at=datetime.now(UTC).isoformat())
    project["llm_usage"]["elapsed_ms"] += elapsed_ms
