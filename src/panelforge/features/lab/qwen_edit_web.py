"""HTTP endpoints for Qwen projects, references and explicit editing actions."""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.qwen_edit import QwenEditConflict
from panelforge.domain.qwen_edit import MAX_ASSISTANT_IMAGES, MAX_RENDER_IMAGES, QwenEditSettings, RATIOS
from panelforge.infrastructure.qwen_project_exports import project_zip


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)


class UpdateBody(RevisionBody):
    changes: dict


class RequestBody(RevisionBody):
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class ReuseBody(RevisionBody):
    reference_id: str
    usage: Literal["assistant", "render"]


class CropBody(RequestBody):
    source_asset_id: str
    source_width: int = Field(ge=1)
    source_height: int = Field(ge=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


def qwen_edit_router(service):
    router = APIRouter(prefix="/api/image-lab/qwen-edit")

    def require():
        if service is None:
            raise HTTPException(503, "L’atelier Qwen n’est pas configuré. Redémarre PanelForge après sa mise à jour.")

    def action(callback, *, public=True):
        require()
        try:
            value = callback()
            return {"project": service.public(value)} if public else value
        except QwenEditConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Projet, image ou essai introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, str(error)) from error

    async def image_bytes(upload):
        try:
            content = await upload.read(25 * 1024**2 + 1)
            if len(content) > 25 * 1024**2:
                raise HTTPException(422, "Une image ne doit pas dépasser 25 Mo.")
            return content
        finally:
            await upload.close()

    @router.get("/spec")
    def spec():
        require()
        return {"enabled": True, "defaults": QwenEditSettings().record(), "aspect_ratios": RATIOS,
                "max_render_images": MAX_RENDER_IMAGES, "max_assistant_images": MAX_ASSISTANT_IMAGES,
                "recipe": {"name": "Qwen Image 2.1", "version": service.workflow.reference.version},
                "features": {"visual_guide": True, "natural_color_finish": True},
                "fixed": {"sampler": "euler", "scheduler": "simple", "denoise": 1}}

    @router.get("/models")
    def models():
        return action(lambda: {"models": [{"id": m.model_id, "source": m.source,
                                           "label": m.display_name or m.model_id} for m in service.list_models()]}, public=False)

    @router.get("/projects")
    def projects():
        return action(lambda: {"projects": service.list()}, public=False)

    @router.post("/projects", status_code=201)
    async def create(name: Annotated[str, Form(max_length=120)] = "Projet Qwen",
                     composition: Annotated[bool, Form()] = False,
                     source_image: Annotated[UploadFile | None, File()] = None):
        require()
        content = await image_bytes(source_image) if source_image else None
        return action(lambda: service.create(name=name, content=content, composition=composition))

    @router.get("/projects/{project_id}")
    def get(project_id: str):
        return action(lambda: service.get(project_id))

    @router.patch("/projects/{project_id}/stages/{stage_id}")
    def update(project_id: str, stage_id: str, body: UpdateBody):
        return action(lambda: service.update(project_id, stage_id, revision=body.revision, changes=body.changes))

    @router.post("/projects/{project_id}/stages/{stage_id}/references", status_code=201)
    async def add_reference(project_id: str, stage_id: str, image: Annotated[UploadFile, File()],
                            revision: Annotated[int, Form(ge=0)],
                            usage: Annotated[Literal["assistant", "render"], Form()] = "assistant",
                            name: Annotated[str, Form(max_length=80)] = "Référence",
                            role: Annotated[str, Form(max_length=300)] = ""):
        require()
        content = await image_bytes(image)
        return action(lambda: service.add_reference(project_id, stage_id, revision=revision,
                      name=name, role=role, usage=usage, content=content))

    @router.post("/projects/{project_id}/stages/{stage_id}/reuse", status_code=201)
    def reuse(project_id: str, stage_id: str, body: ReuseBody):
        return action(lambda: service.add_reference(project_id, stage_id, revision=body.revision, name="",
                      usage=body.usage, reuse_id=body.reference_id))

    @router.post("/projects/{project_id}/stages/{stage_id}/messages", status_code=202)
    def message(project_id: str, stage_id: str, body: RequestBody, tasks: BackgroundTasks):
        def start():
            project, message_id = service.begin_message(project_id, stage_id, **body.model_dump())
            tasks.add_task(service.execute_message, project_id, stage_id, message_id)
            return project
        return action(start)

    @router.get("/projects/{project_id}/stages/{stage_id}/messages/{message_id}")
    def message_detail(project_id: str, stage_id: str, message_id: str):
        def detail():
            project = service.get(project_id)
            stage = next(s for s in project["stages"] if s["id"] == stage_id)
            value = next(m for m in stage["messages"] if m["id"] == message_id)
            return {"message": value}
        return action(detail, public=False)

    @router.post("/projects/{project_id}/stages/{stage_id}/messages/{message_id}/recover")
    def recover(project_id: str, stage_id: str, message_id: str, body: RevisionBody):
        return action(lambda: service.recover_message(project_id, stage_id, message_id, revision=body.revision))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts", status_code=202)
    def generate(project_id: str, stage_id: str, body: RequestBody):
        return action(lambda: service.queue_attempt(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts/{attempt_id}/cancel")
    def cancel(project_id: str, stage_id: str, attempt_id: str):
        return action(lambda: service.cancel_attempt(project_id, stage_id, attempt_id))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts/{attempt_id}/accept")
    def accept(project_id: str, stage_id: str, attempt_id: str, body: RevisionBody):
        return action(lambda: service.accept(project_id, stage_id, attempt_id, revision=body.revision))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts/{attempt_id}/restore")
    def restore(project_id: str, stage_id: str, attempt_id: str, body: RevisionBody):
        return action(lambda: service.restore_attempt(project_id, stage_id, attempt_id, revision=body.revision))

    @router.post("/projects/{project_id}/stages/{stage_id}/crop", status_code=201)
    def crop(project_id: str, stage_id: str, body: CropBody):
        return action(lambda: service.crop_source(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/guide", status_code=201)
    async def save_guide(project_id: str, stage_id: str, mask: Annotated[UploadFile, File()],
                         revision: Annotated[int, Form(ge=0)],
                         request_id: Annotated[str, Form(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")],
                         source_asset_id: Annotated[str, Form(min_length=1, max_length=100)],
                         source_width: Annotated[int, Form(ge=1)], source_height: Annotated[int, Form(ge=1)]):
        require()
        try:
            content = await mask.read(25 * 1024**2 + 1)
            if len(content) > 25 * 1024**2:
                raise HTTPException(422, "Le guide ne doit pas dépasser 25 Mo.")
            return action(lambda: service.save_guide(project_id, stage_id, content, revision=revision,
                          request_id=request_id, source_asset_id=source_asset_id,
                          source_width=source_width, source_height=source_height))
        except QwenEditConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Projet, image ou essai introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, str(error)) from error
        finally:
            await mask.close()

    @router.post("/projects/{project_id}/stages/{stage_id}/guide/clear")
    def clear_guide(project_id: str, stage_id: str, body: RequestBody):
        return action(lambda: service.clear_guide(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/restart")
    def restart(project_id: str, stage_id: str, body: RequestBody):
        return action(lambda: service.restart_stage(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/resume", status_code=201)
    def resume(project_id: str, stage_id: str, body: ResumeBody):
        return action(lambda: service.resume(project_id, stage_id, request_id=body.request_id))

    @router.post("/projects/{project_id}/export")
    def export(project_id: str):
        return action(lambda: service.export(project_id))

    @router.get("/projects/{project_id}/download")
    def download(project_id: str):
        data = action(lambda: project_zip(service.get(project_id), service.assets, service.projects), public=False)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'})

    return router
