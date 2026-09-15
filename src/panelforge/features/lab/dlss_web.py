"""Shared HTTP surface for local DLSS, independent of generation endpoints."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.dlss_image_comparison import queue_image_comparison
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.dlss_image_presets import image_presets


class DlssOptionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: str = "2"
    intensity: float = Field(default=1, ge=0, le=2, allow_inf_nan=False)
    tone: float = Field(default=1, ge=0, le=2, allow_inf_nan=False)
    structure: float = Field(default=1, ge=0, le=2, allow_inf_nan=False)
    skin: float = Field(default=1, ge=-1, le=2, allow_inf_nan=False)
    style: str = "Default"
    detail: float = Field(default=1, ge=1, le=2, allow_inf_nan=False)
    strict_neural: bool = False
    interpolate: bool = False
    hdr: bool = False
    codec: str = "H.264 (NVIDIA NVENC)"


class DlssRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner: str
    owner_id: str
    attempt_id: str
    settings: DlssOptionsBody
    request_id: str = Field(default="preview", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")

    def resolved_settings(self):
        # Owner-specific defaults apply only to omitted fields. Explicit choices
        # and persisted jobs keep their settings, including size/cadence/HDR.
        defaults = {}
        if self.owner in {"assisted", "edit"}:
            defaults = {"size": "1.5", "skin": -1}
        elif self.owner in {"h3", "ref2v"}:
            defaults = {"intensity": 0.2, "tone": 0, "structure": 0.2, "skin": 0, "detail": 1, "style": "Natural"}
        return DlssSettings(**{**defaults, **self.settings.model_dump(exclude_unset=True)})


class DlssImageComparisonBody(DlssRequestBody):
    owner: Literal["assisted", "edit"]
    preset_ids: list[str] = Field(min_length=1, max_length=5)


def register_dlss_routes(app, service):
    router = APIRouter(prefix="/api/dlss")

    def require():
        if service is None:
            raise HTTPException(503, "DLSS local n’est pas configuré.")
        return service

    def action(callback):
        require()
        try:
            return callback()
        except FileNotFoundError as error:
            raise HTTPException(404, "Tâche ou média DLSS introuvable.") from error
        except BlockingIOError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, RuntimeError, TimeoutError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, "Comfy local ou un fichier nécessaire est indisponible : " + str(error)) from error

    @router.get("/spec")
    def spec():
        return {"enabled": service is not None}

    @router.get("/runtime")
    def runtime():
        return action(lambda: service.runtime.status())

    @router.post("/runtime/{operation}")
    def control(operation: str):
        return action(lambda: service.control(operation))

    @router.get("/runtime-log", response_class=PlainTextResponse)
    def log():
        def read():
            path = service.jobs.root / "comfy-local.log"
            if not path.is_file():
                return "Aucun démarrage local enregistré."
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                return stream.read().decode("utf-8", errors="replace")
        return action(read)

    @router.post("/preview")
    def preview(body: DlssRequestBody):
        def read():
            settings = body.resolved_settings()
            value = service.preview(body.owner, body.owner_id, body.attempt_id, settings)
            if body.owner in {"assisted", "edit"}:
                value["image_presets"] = image_presets(settings)
            return value
        return action(read)

    @router.post("/image-comparisons", status_code=202)
    def comparison(body: DlssImageComparisonBody):
        return action(lambda: {"jobs": [public_job(job) for job in queue_image_comparison(
            service, owner=body.owner, owner_id=body.owner_id, attempt_id=body.attempt_id,
            settings=body.resolved_settings(), preset_ids=body.preset_ids, request_id=body.request_id)]})

    @router.post("/jobs", status_code=202)
    def queue(body: DlssRequestBody):
        return action(lambda: public_job(service.queue(owner=body.owner, owner_id=body.owner_id, attempt_id=body.attempt_id,
                           settings=body.resolved_settings(), request_id=body.request_id)))

    @router.get("/jobs")
    def jobs(owner: str | None = None, owner_id: str | None = None):
        return action(lambda: {"jobs": [public_job(j) for j in service.list(owner, owner_id)]})

    @router.post("/jobs/{job_id}/retry", status_code=202)
    def retry(job_id: str):
        return action(lambda: public_job(service.retry(job_id)))

    @router.post("/jobs/{job_id}/cancel", status_code=202)
    def cancel(job_id: str):
        return action(lambda: public_job(service.cancel(job_id)))

    @router.post("/jobs/{job_id}/export", status_code=202)
    def export(job_id: str):
        return action(lambda: public_job(service.retry_export(job_id)))

    app.include_router(router)


def public_job(job):
    keys = ("job_id", "status", "error", "created_at", "started_at", "candidate_id", "settings", "snapshot",
            "input_metadata", "output_dimensions", "output_metadata", "warnings", "cancel_requested",
            "progress", "finished_at", "video_export", "local_output_path")
    value = {k: job.get(k) for k in keys}
    if job.get("comparison"):
        value["comparison"] = job["comparison"]
    for name in ("output", "report"):
        asset_id = job.get(name + "_asset_id")
        value[name + "_url"] = f"/api/assets/{asset_id}/content" if asset_id else None
    return value
