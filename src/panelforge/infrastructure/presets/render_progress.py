"""Versioned progress phases for long ComfyUI render workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar


_Error = TypeVar("_Error", bound=Exception)


@dataclass(frozen=True, slots=True)
class RenderProgressPhase:
    phase_id: str
    label: str
    node_ids: tuple[str, ...]
    start_percent: float
    end_percent: float
    tracks_steps: bool


@dataclass(frozen=True, slots=True)
class RenderProgressProfile:
    initial_phase_id: str
    initial_label: str
    phases: tuple[RenderProgressPhase, ...]

    def phase_for_node(self, node_id: str | None) -> RenderProgressPhase | None:
        if node_id is None:
            return None
        return next(
            (phase for phase in self.phases if node_id in phase.node_ids),
            None,
        )


def validate_render_progress_profile(
    value: Any,
    workflow: Mapping[str, Any],
    *,
    error_type: type[_Error] = ValueError,
) -> RenderProgressProfile | None:
    """Validate an optional manifest-owned node-to-phase mapping."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise error_type("progress must be an object")
    initial = value.get("initial")
    if not isinstance(initial, Mapping):
        raise error_type("progress.initial must be an object")
    initial_phase_id = _text(initial.get("id"), "progress.initial.id", error_type)
    initial_label = _text(initial.get("label"), "progress.initial.label", error_type)
    raw_phases = value.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise error_type("progress.phases must be a non-empty list")

    phases: list[RenderProgressPhase] = []
    seen_ids = {initial_phase_id}
    seen_nodes: set[str] = set()
    previous_end = 0.0
    for index, raw in enumerate(raw_phases):
        label = f"progress.phases[{index}]"
        if not isinstance(raw, Mapping):
            raise error_type(f"{label} must be an object")
        phase_id = _text(raw.get("id"), f"{label}.id", error_type)
        if phase_id in seen_ids:
            raise error_type(f"duplicate progress phase {phase_id!r}")
        seen_ids.add(phase_id)
        phase_label = _text(raw.get("label"), f"{label}.label", error_type)
        raw_nodes = raw.get("node_ids")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise error_type(f"{label}.node_ids must be a non-empty list")
        node_ids = tuple(
            _text(node_id, f"{label}.node_ids[{node_index}]", error_type)
            for node_index, node_id in enumerate(raw_nodes)
        )
        for node_id in node_ids:
            if node_id not in workflow:
                raise error_type(f"{label} references missing workflow node {node_id!r}")
            if node_id in seen_nodes:
                raise error_type(f"workflow node {node_id!r} belongs to two progress phases")
            seen_nodes.add(node_id)
        start = _percent(raw.get("start_percent"), f"{label}.start_percent", error_type)
        end = _percent(raw.get("end_percent"), f"{label}.end_percent", error_type)
        if start < previous_end or end <= start:
            raise error_type(f"{label} percentages must be ordered and non-overlapping")
        if end >= 100:
            raise error_type(f"{label}.end_percent must leave 100 for confirmed success")
        previous_end = end
        tracks_steps = raw.get("tracks_steps", False)
        if not isinstance(tracks_steps, bool):
            raise error_type(f"{label}.tracks_steps must be a boolean")
        phases.append(RenderProgressPhase(
            phase_id=phase_id,
            label=phase_label,
            node_ids=node_ids,
            start_percent=start,
            end_percent=end,
            tracks_steps=tracks_steps,
        ))
    return RenderProgressProfile(
        initial_phase_id=initial_phase_id,
        initial_label=initial_label,
        phases=tuple(phases),
    )


def _text(value: Any, label: str, error_type: type[_Error]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{label} must be a non-empty string")
    return value.strip()


def _percent(value: Any, label: str, error_type: type[_Error]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_type(f"{label} must be a number")
    result = float(value)
    if not 0 <= result <= 100:
        raise error_type(f"{label} must be between 0 and 100")
    return result


__all__ = [
    "RenderProgressPhase",
    "RenderProgressProfile",
    "validate_render_progress_profile",
]
