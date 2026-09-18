"""Small JSON boundary; LLM work continues in the background across refreshes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.stories import StoryConflict
from panelforge.domain.stories import DEFAULT_DIALOGUE_LANGUAGE, RECIPE_ID, RECIPE_VERSION


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Nouvelle histoire", min_length=1, max_length=160)
    brief: str = Field(default="", max_length=60000)
    clip_seconds: int = Field(default=10, ge=5, le=15, strict=True)
    scene_count: int = Field(default=6, ge=1, le=12, strict=True)
    recipe_id: str = Field(default=RECIPE_ID, min_length=1, max_length=128)
    recipe_version: str = Field(default=RECIPE_VERSION, min_length=1, max_length=64)
    architect_model_id: str = Field(default="", max_length=300)
    writer_model_id: str = Field(default="", max_length=300)
    creation_mode: str = Field(default="ideas", pattern="^(ideas|script|continuation)$")
    proposal_count: int = Field(default=3, ge=1, le=3, strict=True)
    dialogue_register: int = Field(default=0, ge=0, le=3, strict=True)
    dialogue_language: str = Field(default=DEFAULT_DIALOGUE_LANGUAGE,
        pattern="^(French|English|Korean|Japanese|Russian)$")


class StoryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    instruction: str = Field(default="", max_length=12000)
    model_id: str | None = Field(default=None, min_length=1, max_length=300)
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


class StoryDialogue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaker_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=1500)
    dialogue_id: str | None = Field(default=None, min_length=1, max_length=120)
    delivery: str | None = Field(default=None, pattern="^(spoken|voice_over|off_screen|thought|mediated)$")
    delivery_note: str | None = Field(default=None, min_length=1, max_length=240)


class StoryVisualTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before: str = Field(min_length=1, max_length=1500)
    trigger: str = Field(min_length=1, max_length=1500)
    visible_change: str = Field(min_length=1, max_length=1500)
    after: str = Field(min_length=1, max_length=1500)


class StorySceneEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1, max_length=6000)
    opening_state: str = Field(min_length=1, max_length=6000)
    action: str = Field(min_length=1, max_length=6000)
    dialogue: list[StoryDialogue] = Field(max_length=10)
    ending_state: str = Field(min_length=1, max_length=6000)
    relationship_state: str | None = Field(default=None, min_length=1, max_length=3000)
    appearance_state: str | None = Field(default=None, min_length=1, max_length=3000)
    sexual_state: str | None = Field(default=None, min_length=1, max_length=3000)
    visual_transition: StoryVisualTransition | None = None


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

    @router.get("/spec")
    def spec():
        return invoke(lambda: {"recipes": current().recipe_specs()})

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

    @router.patch("/projects/{project_id}/scenes/{index}")
    def edit_scene(project_id: str, index: int, body: StorySceneEdit):
        values = body.model_dump(exclude_none=True)
        expected_version = values.pop("expected_version")
        # Fruit/legacy scenes do not acquire sensual-only empty fields.
        changes = {key: value for key, value in values.items() if value is not None}
        return invoke(lambda: current().edit_scene(project_id, index, expected_version, changes))

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
