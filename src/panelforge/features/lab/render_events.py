"""Render events for the PanelForge Lab HTTP interface."""

from __future__ import annotations
import asyncio
import json
from typing import Any, Callable
from fastapi import WebSocket, status
from panelforge.infrastructure.presets import RenderProgressPhase, RenderProgressProfile


class _RenderProgressTracker:
    """Translate workflow-specific ComfyUI nodes into one stable UI event."""

    def __init__(
        self,
        profile: RenderProgressProfile,
        execution_id: Callable[[], str | None],
        *,
        configured_steps: int | None = None,
    ) -> None:
        self.profile = profile
        self.execution_id = execution_id
        self.current_node_id: str | None = None
        self.percent = 0.0
        self.phase_id = profile.initial_phase_id
        self.phase_label = profile.initial_label
        self.configured_steps = configured_steps

    def initial_event(self) -> dict[str, object]:
        return self._event(status="running")

    def consume(self, payload: object) -> dict[str, object] | None:
        if not isinstance(payload, dict):
            return None
        event_type = payload.get("type") or payload.get("event")
        data = payload.get("data")
        if not isinstance(event_type, str) or not isinstance(data, dict):
            return None
        expected_id = self._expected_execution_id()
        event_id = data.get("prompt_id") or payload.get("prompt_id") or data.get("execution_id")
        if expected_id is None:
            return None
        if isinstance(event_id, str) and event_id != expected_id:
            return None

        if event_type == "execution_start":
            return self._event(prompt_id=expected_id, status="running")
        if event_type == "executing":
            node_id = data.get("node")
            if node_id is None:
                return None
            self.current_node_id = str(node_id)
            return self._node_event(
                self.current_node_id,
                completed=False,
                prompt_id=expected_id,
            )
        if event_type == "progress":
            node_id = data.get("node")
            if node_id is not None:
                self.current_node_id = str(node_id)
            return self._step_event(data, prompt_id=expected_id)
        if event_type == "progress_state":
            nodes = data.get("nodes")
            if not isinstance(nodes, dict):
                return None
            result = None
            for node_id, state in nodes.items():
                if not isinstance(state, dict) or state.get("state") == "pending":
                    continue
                state_prompt_id = state.get("prompt_id")
                if isinstance(state_prompt_id, str) and state_prompt_id != expected_id:
                    continue
                node_id = str(node_id)
                if self.profile.phase_for_node(node_id) is None:
                    continue
                self.current_node_id = node_id
                snapshot = dict(state)
                snapshot["node"] = node_id
                candidate = self._step_event(snapshot, prompt_id=expected_id)
                if candidate is not None:
                    result = candidate
            return result
        if event_type == "executed":
            node_id = data.get("node")
            if node_id is None:
                return None
            self.current_node_id = str(node_id)
            return self._node_event(
                self.current_node_id,
                completed=True,
                prompt_id=expected_id,
            )
        if event_type == "execution_cached":
            result = None
            nodes = data.get("nodes")
            if isinstance(nodes, list):
                for node_id in nodes:
                    result = self._node_event(
                        str(node_id),
                        completed=True,
                        prompt_id=expected_id,
                    ) or result
            return result
        if event_type in {"execution_success", "execution_complete"}:
            self.percent = 100.0
            self.phase_id = "complete"
            self.phase_label = "Terminé"
            return self._event(prompt_id=expected_id, status="succeeded")
        if event_type in {"execution_error", "execution_interrupted"}:
            return self._event(prompt_id=expected_id, status="failed")
        return None

    def _step_event(
        self,
        data: dict[str, object],
        *,
        prompt_id: str,
    ) -> dict[str, object] | None:
        phase = self.profile.phase_for_node(self.current_node_id)
        if phase is None:
            return None
        current = data.get("value")
        maximum = data.get("max")
        if (
            not phase.tracks_steps
            or isinstance(current, bool)
            or isinstance(maximum, bool)
            or not isinstance(current, (int, float))
            or not isinstance(maximum, (int, float))
            or maximum <= 0
        ):
            return self._node_event(
                self.current_node_id or "",
                completed=False,
                prompt_id=prompt_id,
            )
        expected_steps = phase.expected_steps
        if expected_steps == "configured":
            expected_steps = self.configured_steps
        if expected_steps is not None and int(maximum) != expected_steps:
            # ComfyUI can publish nested loading or preview progress on the
            # sampler node. Those counters are not diffusion steps.
            return None
        ratio = max(0.0, min(1.0, float(current) / float(maximum)))
        candidate = (
            phase.start_percent
            + ((phase.end_percent - phase.start_percent) * ratio)
        )
        if candidate < self.percent:
            return None
        self._select_phase(phase)
        self.percent = candidate
        return self._event(
            prompt_id=prompt_id,
            status="running",
            current_step=current,
            total_steps=maximum,
        )

    def _node_event(
        self,
        node_id: str,
        *,
        completed: bool,
        prompt_id: str,
    ) -> dict[str, object] | None:
        phase = self.profile.phase_for_node(node_id)
        if phase is None:
            return None
        node_index = phase.node_ids.index(node_id)
        fraction = (node_index + (1 if completed else 0)) / len(phase.node_ids)
        candidate = (
            phase.start_percent
            + ((phase.end_percent - phase.start_percent) * fraction)
        )
        if candidate < self.percent:
            return None
        self._select_phase(phase)
        self.percent = candidate
        return self._event(prompt_id=prompt_id, status="running")

    def _select_phase(self, phase: RenderProgressPhase) -> None:
        self.phase_id = phase.phase_id
        self.phase_label = phase.label

    def _expected_execution_id(self) -> str | None:
        try:
            value = self.execution_id()
        except (KeyError, FileNotFoundError, ValueError):
            return None
        return value if isinstance(value, str) and value else None

    def _event(
        self,
        *,
        prompt_id: str | None = None,
        status: str,
        current_step: object | None = None,
        total_steps: object | None = None,
    ) -> dict[str, object]:
        return {
            "type": "panelforge_render_progress",
            "data": {
                "prompt_id": prompt_id,
                "phase_id": self.phase_id,
                "phase_label": self.phase_label,
                "percent": round(self.percent, 2),
                "estimated": self.percent < 100,
                "current_step": current_step,
                "total_steps": total_steps,
                "status": status,
            },
        }


def _report_machine_render_progress(machine_work, owner_id: str, event: dict[str, object]) -> None:
    """Apply normalized H3 progress regardless of which preview relay owns ComfyUI's client channel."""
    if machine_work is None:
        return
    data = event.get("data")
    if not isinstance(data, dict):
        return
    percent = data.get("percent")
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        return
    stage = str(data.get("phase_label") or "Rendu H3")
    current = data.get("current_step")
    total = data.get("total_steps")
    if (
        not isinstance(current, bool)
        and not isinstance(total, bool)
        and isinstance(current, (int, float))
        and isinstance(total, (int, float))
        and total > 0
    ):
        stage += f" · étape {int(current)}/{int(total)}"
    machine_work.report_progress(owner_id, float(percent) / 100, stage)


def _connect_video_preview(url: str):
    """Open the ComfyUI preview channel used by the same-origin relay."""
    try:
        from websockets.asyncio.client import connect
    except ImportError as error:  # pragma: no cover - installation failure
        raise RuntimeError(
            "The 'websockets' dependency is required for Video Lab previews"
        ) from error
    return connect(
        url,
        open_timeout=10,
        close_timeout=5,
        max_size=None,
    )


async def _relay_video_preview(
    websocket: WebSocket,
    upstream: Any,
    *,
    progress_profile: RenderProgressProfile | None = None,
    execution_id: Callable[[], str | None] | None = None,
    configured_steps: int | None = None,
    progress_reporter: Callable[[dict[str, object]], None] | None = None,
) -> None:
    """Forward ComfyUI text/binary events until either peer disconnects."""

    tracker = (
        _RenderProgressTracker(
            progress_profile,
            execution_id,
            configured_steps=configured_steps,
        )
        if progress_profile is not None and execution_id is not None
        else None
    )
    async def forward_upstream() -> None:
        while True:
            message = await upstream.recv()
            if isinstance(message, str):
                await websocket.send_text(message)
                if tracker is not None:
                    try:
                        normalized = tracker.consume(json.loads(message))
                    except json.JSONDecodeError:
                        normalized = None
                    if normalized is not None:
                        if progress_reporter is not None:
                            progress_reporter(normalized)
                        await websocket.send_json(normalized)
            else:
                await websocket.send_bytes(bytes(message))

    async def watch_browser() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    upstream_task = asyncio.create_task(forward_upstream())
    browser_task = asyncio.create_task(watch_browser())
    done, pending = await asyncio.wait(
        {upstream_task, browser_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()


async def _relay_runtime_monitor(
    websocket: WebSocket,
    upstream: Any,
    *,
    progress_tracker_factory: Callable[[], tuple[str, RenderProgressProfile, Callable[[], str | None], int | None] | None] | None = None,
    progress_reporter: Callable[[str, dict[str, object]], None] | None = None,
) -> None:
    """Forward telemetry and normalized progress for PanelForge's active H3 job."""

    async def forward_upstream() -> None:
        tracker_key: str | None = None
        tracker: _RenderProgressTracker | None = None
        while True:
            message = await upstream.recv()
            if not isinstance(message, str):
                continue
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "crystools.monitor":
                data = payload.get("data")
                if isinstance(data, dict):
                    await websocket.send_json({"type": "crystools.monitor", "data": data})
                continue
            if progress_tracker_factory is None:
                continue
            candidate = progress_tracker_factory()
            if candidate is None:
                tracker_key = None
                tracker = None
                continue
            key, profile, execution_id, configured_steps = candidate
            if key != tracker_key:
                tracker_key = key
                tracker = _RenderProgressTracker(
                    profile,
                    execution_id,
                    configured_steps=configured_steps,
                )
            normalized = tracker.consume(payload) if tracker is not None else None
            if normalized is not None:
                if progress_reporter is not None and tracker_key is not None:
                    progress_reporter(tracker_key, normalized)
                await websocket.send_json(normalized)

    async def watch_browser() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    upstream_task = asyncio.create_task(forward_upstream())
    browser_task = asyncio.create_task(watch_browser())
    done, pending = await asyncio.wait(
        {upstream_task, browser_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()
