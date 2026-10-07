"""HTTP commands for the autonomous image journey workshop."""
from typing import Annotated, Literal
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain.image_journeys import JOURNEY_PRESETS, DEFAULT_IMAGES, MAX_IMAGES, DEFAULT_MASK_MODEL_ID, DEFAULT_JOURNEY_VERSION, DEFAULT_JOURNEY_DIRECTION
from panelforge.domain.minimax_edit import DEFAULT_ASSISTANT_MODEL


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    command: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    intention: str = Field(default="", max_length=6000)
    progression_model_id: str = Field(min_length=1, max_length=300)
    prompt_model_id: str = Field(min_length=1, max_length=300)
    mask_model_id: str | None = Field(default=None, min_length=1, max_length=300)


class TransitionSelectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_order: Literal["generation", "reverse_generation"] = "generation"
    frame_ids: list[Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]] = Field(min_length=2)


class CompareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0, strict=True)
    command: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    step_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    reference_megapixels: int = Field(ge=1, le=2, strict=True)


class TrialBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0, strict=True)
    command: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    count: int = Field(ge=1, le=MAX_IMAGES, strict=True)


class ImageOperationBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0, strict=True)
    command: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    kind: Literal['append', 'insert', 'hq']
    after_frame_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    before_frame_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    intention: str = Field(default='', max_length=6000)
    prompt: str = Field(default='', max_length=24000)


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

    @router.post('/projects/{identity}/image-operations', status_code=202)
    def image_operation(identity: str, body: ImageOperationBody):
        return invoke(lambda: service.edits.start(identity, **body.model_dump()), True)

    @router.post('/projects/{identity}/image-operations/{operation_id}/{action}', status_code=202)
    def image_operation_control(identity: str, operation_id: str, action: str):
        return invoke(lambda: service.edits.control(identity, operation_id, action=action), True)

    @router.get("/spec")
    def spec():
        from panelforge.domain.image_journey_edits import HQ_PROMPT
        return invoke(lambda: dict(journey_presets=JOURNEY_PRESETS, default_journey_preset="miniature", default_journey_direction=DEFAULT_JOURNEY_DIRECTION, default_journey_version=DEFAULT_JOURNEY_VERSION, default_images=DEFAULT_IMAGES, max_images=MAX_IMAGES, hq_prompt=HQ_PROMPT,
                                  default_model_id=DEFAULT_ASSISTANT_MODEL, default_mask_model_id=DEFAULT_MASK_MODEL_ID,
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
                     count: Annotated[int, Form(ge=1, le=MAX_IMAGES)] = DEFAULT_IMAGES,
                     auto_mask: Annotated[bool, Form()] = False,
                     mask_model_id: Annotated[str | None, Form(min_length=1, max_length=300)] = None,
                     journey_version: Annotated[str | None, Form(pattern=r"^[12]$")] = None,
                     journey_direction: Annotated[str | None, Form(pattern=r"^(forward|reverse)$")] = None,
                     journey_preset: Annotated[str | None, Form(pattern=r"^(miniature|realistic)$")] = None):
        try:
            content = await source_image.read(25 * 1024**2 + 1)
            if len(content) > 25 * 1024**2:
                raise HTTPException(413, "Une image est limitée à 25 Mio.")
            return await run_in_threadpool(lambda: invoke(lambda: service.create(command=command, content=content,
                intention=intention, count=count, progression_model_id=progression_model_id,
                prompt_model_id=prompt_model_id, auto_mask=auto_mask, mask_model_id=mask_model_id,
                journey_version=journey_version, journey_direction=journey_direction, journey_preset=journey_preset), True))
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

    @router.post("/projects/{identity}/fixed-trials", status_code=202)
    def fixed_trial(identity: str, body: TrialBody):
        return invoke(lambda: service.trials.start(identity, **body.model_dump()), True)

    @router.post("/projects/{identity}/fixed-trials/{trial_id}/{action}", status_code=202)
    def trial_control(identity: str, trial_id: str, action: str):
        return invoke(lambda: service.trials.control(identity, trial_id, action=action), True)

    @router.get("/projects/{identity}/sequence")
    def sequence(identity: str):
        return invoke(lambda: service.sequence(identity))

    @router.post("/projects/{identity}/transitions")
    def transitions(identity: str, body: TransitionSelectionBody | None = None):
        return invoke(lambda: service.prepare_transitions(identity, frame_ids=body.frame_ids if body else None,
                                                          frame_order=body.frame_order if body else "generation"))

    return router
