"""Versioned, low-confidence memory for experimental Production LoRA choices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any

from panelforge.domain.production import ProductionLoraPlan


class LocalProductionLoraMemory:
    """Keep declared profiles separate from observational rendering evidence."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._path = Path(workspace_root).resolve() / "production_lora_memory.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def context(self, names: Sequence[str], *, observations_per_lora: int = 3) -> tuple[dict[str, object], ...]:
        if observations_per_lora < 0:
            raise ValueError("observations_per_lora must be non-negative")
        with self._lock:
            state = self._load()
        profiles = state.get("profiles", {})
        observations = state.get("observations", [])
        values: list[dict[str, object]] = []
        for name in names:
            normalized = _normalized(name)
            profile = profiles.get(normalized, {}) if isinstance(profiles, Mapping) else {}
            if not isinstance(profile, Mapping):
                profile = {}
            recent = [
                dict(item)
                for item in observations
                if isinstance(item, Mapping) and item.get("normalized_name") == normalized
            ][-observations_per_lora:]
            hypotheses = profile.get("hypotheses", [])
            values.append({
                "name": name,
                "declared_effects": _strings(profile.get("declared_effects")),
                "trigger_terms": _strings(profile.get("trigger_terms")),
                "recommended_strength": profile.get("recommended_strength"),
                "minimum_strength": profile.get("minimum_strength"),
                "maximum_strength": profile.get("maximum_strength"),
                "compatible_checkpoints": _strings(profile.get("compatible_checkpoints")),
                "warnings": _strings(profile.get("warnings")),
                "model_hypotheses": [
                    dict(item) for item in hypotheses[-3:] if isinstance(item, Mapping)
                ] if isinstance(hypotheses, list) else [],
                "recent_observations": recent,
            })
        return tuple(values)

    def set_declared_profile(
        self,
        name: str,
        *,
        effects: Sequence[str] = (),
        trigger_terms: Sequence[str] = (),
        recommended_strength: float | None = None,
        minimum_strength: float | None = None,
        maximum_strength: float | None = None,
        compatible_checkpoints: Sequence[str] = (),
        warnings: Sequence[str] = (),
    ) -> None:
        """Persist explicit user/catalog knowledge without mixing it with model guesses."""

        with self._lock:
            state = self._load()
            profiles = state.setdefault("profiles", {})
            current = profiles.get(_normalized(name), {})
            hypotheses = current.get("hypotheses", []) if isinstance(current, Mapping) else []
            profiles[_normalized(name)] = {
                "name": _text(name, "name", 500),
                "declared_effects": list(_clean_strings(effects, "effects")),
                "trigger_terms": list(_clean_strings(trigger_terms, "trigger_terms")),
                "recommended_strength": _optional_strength(recommended_strength),
                "minimum_strength": _optional_strength(minimum_strength),
                "maximum_strength": _optional_strength(maximum_strength),
                "compatible_checkpoints": list(_clean_strings(compatible_checkpoints, "compatible_checkpoints")),
                "warnings": list(_clean_strings(warnings, "warnings")),
                "hypotheses": hypotheses if isinstance(hypotheses, list) else [],
            }
            self._save(state)

    def record_plan(
        self,
        *,
        job_id: str,
        checkpoint: str,
        plan: ProductionLoraPlan,
        timestamp: str | None = None,
    ) -> None:
        recorded_at = timestamp or _timestamp()
        with self._lock:
            state = self._load()
            profiles = state.setdefault("profiles", {})
            for choice in plan.choices:
                normalized = _normalized(choice.name)
                current = profiles.get(normalized, {})
                if not isinstance(current, dict):
                    current = {}
                hypotheses = current.get("hypotheses", [])
                if not isinstance(hypotheses, list):
                    hypotheses = []
                hypotheses.append({
                    "job_id": _text(job_id, "job_id", 128),
                    "timestamp": recorded_at,
                    "checkpoint": _text(checkpoint, "checkpoint", 500),
                    "strength": choice.strength,
                    "source": choice.source.value,
                    "expected_effect": choice.expected_effect,
                    "plan_rationale": plan.rationale,
                    "confidence": "hypothesis",
                })
                current.setdefault("name", choice.name)
                current.setdefault("declared_effects", [])
                current.setdefault("trigger_terms", [])
                current.setdefault("recommended_strength", None)
                current.setdefault("minimum_strength", None)
                current.setdefault("maximum_strength", None)
                current.setdefault("compatible_checkpoints", [])
                current.setdefault("warnings", [])
                current["hypotheses"] = hypotheses[-20:]
                profiles[normalized] = current
            self._save(state)

    def record_observation(
        self,
        *,
        job_id: str,
        attempt_id: str,
        checkpoint: str,
        prompt: str,
        seed: int,
        plan: ProductionLoraPlan,
        score: int | None,
        selection: str,
        timestamp: str | None = None,
    ) -> None:
        if score is not None and (isinstance(score, bool) or not 0 <= score <= 100):
            raise ValueError("score must be between 0 and 100")
        stack = [
            {"name": choice.name, "strength": choice.strength, "source": choice.source.value}
            for choice in plan.choices
        ]
        recorded_at = timestamp or _timestamp()
        with self._lock:
            state = self._load()
            observations = state.setdefault("observations", [])
            for choice in plan.choices:
                observations.append({
                    "observation_id": f"{job_id}:{attempt_id}:{_normalized(choice.name)}:{selection}",
                    "job_id": _text(job_id, "job_id", 128),
                    "attempt_id": _text(attempt_id, "attempt_id", 128),
                    "timestamp": recorded_at,
                    "name": choice.name,
                    "normalized_name": _normalized(choice.name),
                    "strength": choice.strength,
                    "checkpoint": _text(checkpoint, "checkpoint", 500),
                    "prompt_excerpt": _text(prompt, "prompt", 20_000)[:2_000],
                    "seed": int(seed),
                    "stack": stack,
                    "score": score,
                    "selection": _text(selection, "selection", 80),
                    "confidence": "low_observational",
                })
            deduplicated = {
                item["observation_id"]: item
                for item in observations
                if isinstance(item, dict) and isinstance(item.get("observation_id"), str)
            }
            state["observations"] = list(deduplicated.values())[-1_000:]
            self._save(state)

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"schema_version": 1, "profiles": {}, "observations": []}
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ValueError("unsupported Production LoRA memory schema")
            return value
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return {"schema_version": 1, "profiles": {}, "observations": []}

    def _save(self, state: Mapping[str, Any]) -> None:
        content = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        descriptor, temporary = tempfile.mkstemp(
            dir=self._path.parent,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path)
        finally:
            temporary_path.unlink(missing_ok=True)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalized(value: str) -> str:
    return _text(value, "LoRA name", 500).replace("\\", "/").casefold()


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _clean_strings(values: Sequence[str], label: str) -> tuple[str, ...]:
    return tuple(_text(value, f"{label} item", 1_000) for value in values)


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _optional_strength(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not -20 <= number <= 20:
        raise ValueError("LoRA profile strength must be between -20 and 20")
    return number


__all__ = ["LocalProductionLoraMemory"]
