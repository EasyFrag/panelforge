"""HTTP commands for the image-transition workshop."""
from typing import Annotated, Literal
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.image_transitions import TransitionConflict
from panelforge.domain.image_transitions import defaults, KINDS, MAX_IMAGES
from panelforge.domain.video_lab import VideoAspectRatio


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="Transitions d’images", max_length=120)


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)


class UpdateBody(RevisionBody):
    changes: dict


class SelectionBody(RevisionBody):
    ids: list[str] = Field(min_length=1, max_length=100)


class ProposalBody(SelectionBody):
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class OrderBody(RevisionBody):
    ids: list[str] = Field(max_length=100)


class ImportBody(RevisionBody):
    engine: Literal["krea", "qwen", "minimax"]
    project_id: str = Field(max_length=150)
    keys: list[str] = Field(min_length=1, max_length=100)
    replace_id: str | None = None


def image_transitions_router(service):
    router = APIRouter(prefix="/api/image-transitions", tags=["image-transitions"])

    def invoke(callback, public=False):
        if service is None:
            raise HTTPException(503, "L’atelier de transitions sera disponible au prochain démarrage de PanelForge.")
        try:
            value = callback()
            return {"project": service.public(value)} if public else value
        except TransitionConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Projet, transition ou image introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except (OSError, RuntimeError) as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/spec")
    def spec():
        return invoke(lambda: dict(defaults=defaults(), kinds=KINDS, max_images=MAX_IMAGES,
                                    aspect_ratios=[r.value for r in VideoAspectRatio]))

    @router.get("/models")
    def models():
        return invoke(lambda: dict(models=[dict(id=m.model_id, label=m.display_name or m.model_id, source=m.source)
                                           for m in service.gateway.list_models()]))

    @router.get("/library/{engine}")
    def library(engine: str):
        return invoke(lambda: dict(projects=service.sources.projects(engine)))

    @router.get("/library/{engine}/{project_id}")
    def choices(engine: str, project_id: str):
        return invoke(lambda: dict(images=service.sources.choices(engine, project_id)))

    @router.get("/projects")
    def projects():
        return invoke(lambda: dict(projects=service.list()))

    @router.post("/projects", status_code=201)
    def create(body: CreateBody):
        return invoke(lambda: service.create(body.name), True)

    @router.get("/projects/{identity}")
    def get(identity: str):
        return invoke(lambda: service.get(identity), True)

    @router.patch("/projects/{identity}")
    def update(identity: str, body: UpdateBody):
        return invoke(lambda: service.update(identity, body.version, body.changes), True)

    @router.post("/projects/{identity}/frames/upload", status_code=201)
    async def upload(identity: str, image: Annotated[UploadFile, File()],
                     version: Annotated[int, Form(ge=0)],
                     replace_id: Annotated[str | None, Form()] = None):
        try:
            content = await image.read(25 * 1024 * 1024 + 1)
            if len(content) > 25 * 1024 * 1024:
                raise HTTPException(413, "Une image est limitée à 25 Mio.")
            return invoke(lambda: service.upload(identity, version, content, image.filename or "", replace_id), True)
        finally:
            await image.close()

    @router.post("/projects/{identity}/frames/import", status_code=201)
    def import_images(identity: str, body: ImportBody):
        return invoke(lambda: service.add_frames(identity, body.version,
            service.sources.select(body.engine, body.project_id, body.keys), body.replace_id), True)

    @router.put("/projects/{identity}/order")
    def order(identity: str, body: OrderBody):
        return invoke(lambda: service.order(identity, body.version, body.ids), True)

    @router.patch("/projects/{identity}/transitions/{transition_id}")
    def edit(identity: str, transition_id: str, body: UpdateBody):
        return invoke(lambda: service.edit(identity, body.version, transition_id, body.changes), True)

    @router.post("/projects/{identity}/review")
    def review(identity: str, body: SelectionBody):
        return invoke(lambda: service.review(identity, body.version, body.ids), True)

    @router.post("/projects/{identity}/transitions/{transition_id}/suggestion")
    def suggestion(identity: str, transition_id: str, body: RevisionBody):
        return invoke(lambda: service.apply_suggestion(identity, body.version, transition_id), True)

    @router.post("/projects/{identity}/proposals", status_code=202)
    def propose(identity: str, body: ProposalBody, tasks: BackgroundTasks):
        def start():
            project, job_id = service.begin_proposals(identity, body.version, body.ids, body.request_id)
            tasks.add_task(service.execute_proposals, identity, job_id)
            return project
        return invoke(start, True)

    @router.post("/projects/{identity}/send")
    def send(identity: str, body: SelectionBody):
        def work():
            project, ids, added = service.send(identity, body.version, body.ids)
            return dict(project=service.public(project), ids=ids, added=added)
        return invoke(work)

    return router
