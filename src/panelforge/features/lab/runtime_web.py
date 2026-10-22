"""Runtime web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
import asyncio
from datetime import UTC, datetime
from typing import Any, Callable
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from panelforge.application import H3RenderService, ModelRuntimeControl
from panelforge.domain import ComputeResource, ThermalPolicy, WorkSchedulerSettings
from panelforge.infrastructure.comfy import ComfyBusyError
from panelforge.infrastructure.presets import RenderProgressProfile
from fastapi import APIRouter
from .render_events import _connect_video_preview, _relay_runtime_monitor, _report_machine_render_progress


class WorkSchedulerThermalBody(BaseModel):
    stop_temperature_c: float = Field(default=85.0, ge=30, le=110, allow_inf_nan=False)
    resume_temperature_c: float = Field(default=40.0, ge=15, le=109, allow_inf_nan=False)
    cooldown_seconds: int = Field(default=120, ge=0, le=86_400, strict=True)
    monitor_local: bool = True
    monitor_remote: bool = True
    pause_when_unavailable: bool = False


class WorkSchedulerSettingsBody(BaseModel):
    thermal: WorkSchedulerThermalBody = Field(default_factory=WorkSchedulerThermalBody)
    local_cooldown_temperature_c: float = Field(default=80.0, ge=30, le=110, allow_inf_nan=False)
    local_cooldown_seconds: int = Field(default=80, ge=0, le=3_600, strict=True)
    remote_non_video_cooldown_temperature_c: float = Field(default=80.0, ge=30, le=110, allow_inf_nan=False)
    remote_non_video_cooldown_seconds: int = Field(default=80, ge=0, le=3_600, strict=True)
    remote_video_cooldown_seconds: int = Field(default=30, ge=0, le=3_600, strict=True)
    pause_after_failure: bool = False
    history_limit: int = Field(default=30, ge=5, le=200, strict=True)


def _comfy_active_operations(queue: Any) -> list[str]:
    operations: list[str] = []
    for entry in (*tuple(getattr(queue, "running", ())), *tuple(getattr(queue, "pending", ()))):
        client_id = str(getattr(entry, "client_id", "") or "").lower()
        if "krea2" in client_id or client_id.startswith("panelforge-lab-"):
            operation = "KREA2"
        elif "h3-render" in client_id or "video-lab" in client_id:
            operation = "H3"
        else:
            operation = "Comfy"
        if operation not in operations:
            operations.append(operation)
    return operations


def _active_llm_calls(monitor: Any | None) -> list[dict[str, str]]:
    if monitor is None:
        return []
    try:
        calls = tuple(monitor.active_calls())
    except Exception:
        return []
    values: list[dict[str, str]] = []
    for call in calls:
        call_id = str(getattr(call, "call_id", "") or "")
        operation_id = str(getattr(call, "operation_id", "") or "")
        model_id = str(getattr(call, "model_id", "") or "")
        source = model_id.partition("::")[0] if "::" in model_id else "server"
        values.append({
            "call_id": call_id,
            "source": "local" if source == "local" else "server",
            "operation": operation_id,
            "label": _llm_activity_label(operation_id),
        })
    return values


def _llm_activity_label(operation_id: str) -> str:
    normalized = operation_id.strip().lower()
    if normalized.startswith("krea2.") or ".krea2" in normalized:
        return "KREA2"
    if normalized.startswith((
        "reference.",
        "brief.",
        "action_plan.",
        "prompt.",
        "ref2v.",
        "h3.",
        "minimax.h3.",
    )):
        return "H3_plan"
    return "LLM"


def _runtime_status(
    *,
    model_runtime: Any | None,
    llm_activity_monitor: Any | None = None,
    comfy_runtime: Any | None,
    local_gpu_monitor: Any | None,
) -> dict[str, object]:
    observed_at = datetime.now(UTC).isoformat()
    gpu: dict[str, object] = {
        "available": False,
        "name": None,
        "total_bytes": None,
        "free_bytes": None,
        "used_bytes": None,
        "used_percent": None,
    }
    comfy: dict[str, object] = {
        "available": False,
        "queue_running": None,
        "queue_pending": None,
        "active_operations": [],
        "cleanup_allowed": False,
        "warning": None,
    }
    if comfy_runtime is None:
        comfy["warning"] = "ComfyUI non configuré."
    else:
        stats_ok = False
        queue_ok = False
        try:
            stats = comfy_runtime.get_system_stats()
            stats_ok = True
            devices = tuple(getattr(stats, "devices", ()))
            if devices:
                device = devices[0]
                total = int(device.vram_total)
                free = int(device.vram_free)
                used = max(0, total - free)
                gpu.update(
                    {
                        "available": True,
                        "name": device.name,
                        "total_bytes": total,
                        "free_bytes": free,
                        "used_bytes": used,
                        "used_percent": round((used / total) * 100, 1) if total else 0.0,
                    }
                )
        except Exception:
            pass
        try:
            queue = comfy_runtime.get_queue()
            queue_ok = True
            running = len(queue.running)
            pending = len(queue.pending)
            comfy.update(
                {
                    "queue_running": running,
                    "queue_pending": pending,
                    "active_operations": _comfy_active_operations(queue),
                    "cleanup_allowed": running == 0 and pending == 0,
                }
            )
        except Exception:
            pass
        comfy["available"] = stats_ok or queue_ok
        if not comfy["available"]:
            comfy["warning"] = "ComfyUI indisponible."
        elif not stats_ok or not queue_ok:
            comfy["warning"] = "Statut ComfyUI partiel."

    llm: dict[str, object] = {
        "available": False,
        "running_models": [],
        "active_calls": _active_llm_calls(llm_activity_monitor),
        "warning": None,
    }
    if model_runtime is None:
        llm["warning"] = "llama.swap non configuré."
    else:
        try:
            llm["running_models"] = list(model_runtime.running_models())
            llm["available"] = True
        except Exception:
            llm["warning"] = "llama.swap indisponible."
    local_gpu: dict[str, object] = {
        "available": False,
        "name": None,
        "total_bytes": None,
        "free_bytes": None,
        "used_bytes": None,
        "used_percent": None,
        "temperature_c": None,
        "warning": None,
    }
    if local_gpu_monitor is None:
        local_gpu["warning"] = "GPU local non configuré."
    else:
        try:
            local_stats = local_gpu_monitor.get_stats()
            local_gpu.update(
                {
                    "available": True,
                    "name": local_stats.name,
                    "total_bytes": local_stats.total_bytes,
                    "free_bytes": local_stats.free_bytes,
                    "used_bytes": local_stats.used_bytes,
                    "used_percent": local_stats.used_percent,
                    "temperature_c": local_stats.temperature_c,
                }
            )
        except Exception:
            local_gpu["warning"] = "GPU local indisponible."
    return {
        "observed_at": observed_at,
        "gpu": gpu,
        "local_gpu": local_gpu,
        "comfy": comfy,
        "llm": llm,
    }


def runtime_router(*, comfy_runtime: Any | None, h3_render: H3RenderService | None, llm_activity_monitor: Any | None, local_gpu_monitor: Any | None, machine_work, model_runtime: ModelRuntimeControl | None, runtime_monitor_connector: Callable[[str], Any] | None) -> APIRouter:
    router = APIRouter()

    @router.post("/api/model-runtime/unload")
    def unload_model_runtime() -> dict[str, str]:
        if model_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="Le contrôle du serveur LLM n’est pas configuré.",
            )
        try:
            model_runtime.unload_all()
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail=f"Impossible de décharger les modèles LLM : {error}",
            ) from error
        return {
            "status": "unloaded",
            "message": "Modèles LLM déchargés.",
        }

    @router.get("/api/runtime/status")
    def runtime_status() -> dict[str, object]:
        """Return partial runtime data even when one service is offline."""
        payload = _runtime_status(
            model_runtime=model_runtime,
            llm_activity_monitor=llm_activity_monitor,
            comfy_runtime=comfy_runtime,
            local_gpu_monitor=local_gpu_monitor,
        )
        if machine_work is not None:
            try:
                scheduler = machine_work.public_status()
                payload["work_scheduler"] = scheduler
                payload["production_resources"] = [
                    {
                        "resource": resource,
                        "state": value["state"],
                        "temperature_c": value["temperature_c"],
                        "owner_job_id": value["owner_id"],
                        "operation": value["operation"],
                        "error": None,
                        "queue_count": value["queue_count"],
                        "paused": value["paused"],
                    }
                    for resource, value in scheduler["machines"].items()
                ]
            except Exception:
                payload["work_scheduler"] = None
                payload["production_resources"] = []
        else:
            payload["production_resources"] = []
        return payload

    @router.get("/api/work-scheduler/status")
    def work_scheduler_status() -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        return machine_work.public_status()

    @router.get("/api/work-scheduler/thermal-history")
    def work_scheduler_thermal_history() -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        return machine_work.thermal_history()

    @router.get("/api/work-scheduler/settings")
    def work_scheduler_settings() -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        return machine_work.public_status()["settings"]

    @router.put("/api/work-scheduler/settings")
    def update_work_scheduler_settings(body: WorkSchedulerSettingsBody) -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        try:
            settings = WorkSchedulerSettings(
                thermal=ThermalPolicy(**body.thermal.model_dump()),
                local_cooldown_temperature_c=body.local_cooldown_temperature_c,
                local_cooldown_seconds=body.local_cooldown_seconds,
                remote_non_video_cooldown_temperature_c=body.remote_non_video_cooldown_temperature_c,
                remote_non_video_cooldown_seconds=body.remote_non_video_cooldown_seconds,
                remote_video_cooldown_seconds=body.remote_video_cooldown_seconds,
                pause_after_failure=body.pause_after_failure,
                history_limit=body.history_limit,
            )
            machine_work.update_settings(settings)
            return machine_work.public_status()["settings"]
        except (OSError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/work-scheduler/{resource}/pause")
    def pause_work_scheduler(resource: str) -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        try:
            machine_work.pause(ComputeResource(resource))
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Machine inconnue.") from error
        return machine_work.public_status()

    @router.post("/api/work-scheduler/{resource}/resume")
    def resume_work_scheduler(resource: str) -> dict[str, object]:
        if machine_work is None:
            raise HTTPException(status_code=503, detail="Ordonnanceur global indisponible.")
        try:
            machine_work.resume(ComputeResource(resource))
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Machine inconnue.") from error
        return machine_work.public_status()

    @router.post("/api/comfy-runtime/free")
    def free_comfy_runtime() -> dict[str, str]:
        if comfy_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="Le contrôle ComfyUI n’est pas configuré.",
            )
        try:
            comfy_runtime.free_vram()
        except ComfyBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail="Impossible de joindre ComfyUI pour libérer sa VRAM.",
            ) from error
        return {
            "status": "unloaded",
            "message": "Modèles et caches ComfyUI déchargés.",
        }

    @router.websocket("/api/runtime/events")
    async def runtime_events(websocket: WebSocket) -> None:
        await websocket.accept()
        telemetry_url = getattr(comfy_runtime, "websocket_url", None)
        h3_progress_url = getattr(getattr(h3_render, "comfy", None), "websocket_url", None)
        # ComfyUI routes sampler progress to the client_id which submitted the
        # prompt. Crystools telemetry is broadcast, so the H3 client carries both
        # streams while the generic runtime client only carries telemetry.
        upstream_url = h3_progress_url or telemetry_url
        if not isinstance(upstream_url, str) or not upstream_url.strip():
            await websocket.send_json(
                {
                    "type": "panelforge_runtime_status",
                    "data": {"status": "unavailable"},
                }
            )
            await websocket.close(code=1000)
            return
        connector = runtime_monitor_connector or _connect_video_preview

        def active_render_progress():
            if machine_work is None or h3_render is None:
                return None
            try:
                remote = machine_work.public_status()["machines"][ComputeResource.REMOTE_GPU.value]
                owner_id = remote.get("owner_id")
                if not isinstance(owner_id, str) or not owner_id.startswith("h3:"):
                    return None
                _, project_id, attempt_id = owner_id.split(":", 2)
                project = h3_render.get(project_id)
                attempt = project.attempt(attempt_id)
                profile = h3_render.progress_for_attempt(project, attempt)
                if not isinstance(profile, RenderProgressProfile):
                    return None
                return (
                    owner_id,
                    profile,
                    lambda: h3_render.get(project_id).attempt(attempt_id).execution_id,
                    # Spectrum can forecast/skips diffusion evaluations: ComfyUI
                    # then reports the effective counter (for example 2/4), not
                    # the configured scheduler count (for example 25). Keeping
                    # the strict count would discard every useful progress event.
                    None if attempt.spectrum_enabled else attempt.settings.steps,
                )
            except (KeyError, FileNotFoundError, TypeError, ValueError):
                return None

        def report_render_progress(owner_id: str, event: dict[str, object]) -> None:
            _report_machine_render_progress(machine_work, owner_id, event)

        try:
            async with connector(upstream_url) as upstream:
                await websocket.send_json(
                    {
                        "type": "panelforge_runtime_status",
                        "data": {"status": "connected"},
                    }
                )
                await _relay_runtime_monitor(
                    websocket,
                    upstream,
                    progress_tracker_factory=active_render_progress,
                    progress_reporter=report_render_progress,
                )
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await websocket.send_json(
                    {
                        "type": "panelforge_runtime_status",
                        "data": {"status": "unavailable"},
                    }
                )
                await websocket.close(code=1011, reason="Runtime monitor unavailable")
            except (RuntimeError, WebSocketDisconnect):
                pass

    return router
