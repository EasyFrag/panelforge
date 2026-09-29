"""HTTP commands for the autonomous image journey workshop."""
from typing import Annotated
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain.image_journeys import DEFAULT_IMAGES, MAX_IMAGES
from panelforge.domain.minimax_edit import DEFAULT_ASSISTANT_MODEL


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    command: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    intention: str = Field(default="", max_length=6000)
    progression_model_id: str = Field(min_length=1, max_length=300)
    prompt_model_id: str = Field(min_length=1, max_length=300)


class CompareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0, strict=True)
    command: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    step_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    reference_megapixels: int = Field(ge=1, le=2, strict=True)


def image_journeys_router(service):
    router = APIRouter(prefix="/api/image-lab/journeys", tags=["image-journeys"])

    def invoke(callback, public=False):
        if service is None:
            raise HTTPException(503, "Le parcours autonome sera disponible au prochain démarrage de PanelForge.")
        try:
            value = callback()
            return {"project": service.public(value)} if public else value
        except JourneyConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Parcours ou image introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except (OSError, RuntimeError) as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/spec")
    def spec():
        return invoke(lambda: dict(default_images=DEFAULT_IMAGES, max_images=MAX_IMAGES,
                                  default_model_id=DEFAULT_ASSISTANT_MODEL,
                                  transitions_available=service.transitions is not None))

    @router.get("/models")
    def models():
        return invoke(lambda: dict(models=[dict(id=m.model_id, label=m.display_name or m.model_id, source=m.source)
                                           for m in service.gateway.list_models()]))

    @router.get("/projects")
    def projects():
        return invoke(lambda: dict(projects=service.list()))

    @router.post("/projects", status_code=201)
    async def create(source_image: Annotated[UploadFile, File()],
                     command: Annotated[str, Form(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")],
                     progression_model_id: Annotated[str, Form(min_length=1, max_length=300)],
                     prompt_model_id: Annotated[str, Form(min_length=1, max_length=300)],
                     intention: Annotated[str, Form(max_length=6000)] = "",
                     count: Annotated[int, Form(ge=1, le=MAX_IMAGES)] = DEFAULT_IMAGES):
        try:
            content = await source_image.read(25 * 1024**2 + 1)
            if len(content) > 25 * 1024**2:
                raise HTTPException(413, "Une image est limitée à 25 Mio.")
            return await run_in_threadpool(lambda: invoke(lambda: service.create(command=command, content=content,
                intention=intention, count=count, progression_model_id=progression_model_id,
                prompt_model_id=prompt_model_id), True))
        finally:
            await source_image.close()

    @router.get("/projects/{identity}")
    def get(identity: str):
        return invoke(lambda: service.get(identity), True)

    @router.post("/projects/{identity}/pause")
    def pause(identity: str):
        return invoke(lambda: service.pause(identity), True)

    @router.post("/projects/{identity}/resume", status_code=202)
    def resume(identity: str, body: ResumeBody):
        return invoke(lambda: service.resume(identity, **body.model_dump()), True)

    @router.post("/projects/{identity}/comparisons", status_code=202)
    def compare(identity: str, body: CompareBody):
        return invoke(lambda: service.compare(identity, **body.model_dump()), True)

    @router.get("/projects/{identity}/sequence")
    def sequence(identity: str):
        return invoke(lambda: service.sequence(identity))

    @router.post("/projects/{identity}/transitions")
    def transitions(identity: str):
        return invoke(lambda: service.prepare_transitions(identity))

    return router
