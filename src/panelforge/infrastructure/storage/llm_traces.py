"""Durable video-preparation calls, independent of the rolling diagnostic journal."""
from pathlib import Path
from threading import RLock

from .local import _atomic_write, _json_bytes, _read_json_object, _require_safe_id
from .llm_calls import _record_to_dict


class LocalLlmTraceStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "video_llm_traces"
        self._lock = RLock()

    def _path(self, call_id):
        _require_safe_id(call_id, "call_id")
        return self.root / "calls" / (call_id + ".json")

    def begin(self, call_id, context):
        if not context:
            return
        with self._lock:
            path = self._path(call_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, _json_bytes({"context": context, "call": None}))
            for kind in ("session_id", "project_id"):
                identity = context.get(kind)
                if not identity:
                    continue
                _require_safe_id(identity, kind)
                index = self.root / kind / (identity + ".json")
                index.parent.mkdir(parents=True, exist_ok=True)
                data = _read_json_object(index) if index.exists() else {"calls": []}
                if call_id not in data["calls"]:
                    data["calls"].append(call_id)
                _atomic_write(index, _json_bytes(data))

    def finish(self, record):
        with self._lock:
            path = self._path(record.call_id)
            if not path.exists():
                return
            data = _read_json_object(path)
            call = _record_to_dict(record)
            # A synchronous consumer may report validation before/after persistence.
            if data.get("outcome"):
                call.update(data["outcome"])
            data["call"] = call
            _atomic_write(path, _json_bytes(data))

    def outcome(self, call_id, outcome, error_type, error_message):
        with self._lock:
            path = self._path(call_id)
            if not path.exists():
                return
            data = _read_json_object(path)
            fields = {"application_outcome": outcome.value,
                      "application_error_type": error_type, "application_error_message": error_message}
            data["outcome"] = fields
            if data.get("call"):
                data["call"].update(fields)
            _atomic_write(path, _json_bytes(data))

    def list(self, *, session_id=None, project_id=None):
        with self._lock:
            calls = []
            for kind, identity in (("session_id", session_id), ("project_id", project_id)):
                if identity is None:
                    continue
                _require_safe_id(identity, kind)
                index = self.root / kind / (identity + ".json")
                if index.exists():
                    calls.extend(_read_json_object(index)["calls"])
            return [dict(_read_json_object(self._path(key)), call_id=key) for key in dict.fromkeys(calls)]

    def snapshot(self, project, attempt, *, preparation_calls=()):
        with self._lock:
            _require_safe_id(attempt.attempt_id, "attempt_id")
            path = self.root / "renders" / (attempt.attempt_id + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            # Match an explicitly resumed earlier prompt, not the last conversation turn.
            matching = next((i for i in range(len(project.turns) - 1, -1, -1)
                             if project.turns[i].prompt == attempt.prompt), None)
            turns = project.turns[:matching + 1] if matching is not None else project.turns
            _atomic_write(path, _json_bytes({
                "project_id": project.project_id, "source_session_id": project.source_session_id,
                "source_prompt_revision_id": project.source_prompt_revision_id,
                "turn_ids": [turn.turn_id for turn in turns],
                "preparation_call_ids": list(preparation_calls),
                "manual_prompt": matching is None and (bool(project.turns) or attempt.prompt != project.current_prompt),
            }))

    def render_snapshot(self, attempt_id):
        _require_safe_id(attempt_id, "attempt_id")
        path = self.root / "renders" / (attempt_id + ".json")
        return _read_json_object(path) if path.exists() else None
