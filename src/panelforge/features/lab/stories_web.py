"""Small JSON boundary; LLM work continues in the background across refreshes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.stories import StoryConflict


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Nouvelle histoire", min_length=1, max_length=160)
    brief: str = Field(default="", max_length=12000)
    clip_seconds: int = Field(default=10, ge=5, le=15, strict=True)
    scene_count: int = Field(default=6, ge=2, le=12, strict=True)


class StoryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    instruction: str = Field(default="", max_length=12000)
    model_id: str = Field(min_length=1, max_length=300)
    expected_version: int = Field(ge=1, strict=True)
    request_id: str = Field(min_length=8, max_length=100)


class StorySelect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_id: str
    expected_version: int = Field(ge=1, strict=True)


class StoryRestore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    expected_version: int = Field(ge=1, strict=True)


def stories_router(service):
    router = APIRouter(prefix="/api/stories")

    def current():
        if service is None:
            raise HTTPException(503, "L’atelier Histoires n’est pas configuré. Redémarrez le Lab avec le lanceur à jour.")
        return service

    def invoke(action):
        try:
            return action()
        except FileNotFoundError as error:
            raise HTTPException(404, "Histoire introuvable.") from error
        except StoryConflict as error:
            raise HTTPException(409, str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/models")
    def models():
        try:
            return {"models": [dict(id=m.model_id, label=m.display_name or m.model_id, source=m.source) for m in current().gateway.list_models()]}
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(503, f"Liste des modèles indisponible : {error}") from error

    @router.get("/projects")
    def projects():
        return invoke(lambda: {"projects": current().store.list()})

    @router.post("/projects", status_code=201)
    def create(body: StoryCreate):
        return invoke(lambda: current().create(**body.model_dump()))

    @router.get("/projects/{project_id}")
    def get(project_id: str):
        return invoke(lambda: current().get(project_id))

    @router.post("/projects/{project_id}/write", status_code=202)
    def write(project_id: str, body: StoryWrite):
        return invoke(lambda: current().start(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/select")
    def select(project_id: str, body: StorySelect):
        return invoke(lambda: current().select(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/restore")
    def restore(project_id: str, body: StoryRestore):
        return invoke(lambda: current().restore(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/cancel")
    def cancel(project_id: str):
        return invoke(lambda: current().cancel(project_id))

    @router.get("/projects/{project_id}/export")
    def export(project_id: str, include_duration: bool = True):
        return invoke(lambda: current().export(project_id, include_duration=include_duration))

    @router.get("/projects/{project_id}/calls")
    def calls(project_id: str):
        def load():
            value = current()
            value.get(project_id)
            return dict(calls=value.traces.list(project_id=project_id) if value.traces else [], scope="Échanges de cette histoire")
        return invoke(load)

    return router
