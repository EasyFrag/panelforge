"""Small JSON boundary; LLM work continues in the background across refreshes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.stories import StoryConflict
from panelforge.domain.stories import (
    DEFAULT_DIALOGUE_LANGUAGE, DEFAULT_NARRATIVE_FORMAT, RECIPE_ID, RECIPE_VERSION,
)


class LongStoryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str = Field(default="melodrama", pattern="^(auto|melodrama|social|transformation|suspense|fantasy)$")
    delivery: str = Field(default="serial", pattern="^(serial|continuous)$")
    narration: str = Field(default="dialogue", pattern="^(auto|dialogue|audio|visual)$")
    unit_count: int = Field(default=4, ge=1, le=12, strict=True)
    ending_type: str = Field(default="resolution", pattern="^(auto|resolution|open|reversal|cost)$")


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Nouvelle histoire", min_length=1, max_length=160)
    brief: str = Field(default="", max_length=60000)
    prior_story: str = Field(default="", max_length=60000)
    clip_seconds: int = Field(default=10, ge=5, le=15, strict=True)
    scene_count: int = Field(default=6, ge=1, le=12, strict=True)
    recipe_id: str = Field(default=RECIPE_ID, min_length=1, max_length=128)
    recipe_version: str = Field(default=RECIPE_VERSION, min_length=1, max_length=64)
    architect_model_id: str = Field(default="", max_length=300)
    writer_model_id: str = Field(default="", max_length=300)
    creation_mode: str = Field(default="ideas", pattern="^(ideas|script|continuation|adapt)$")
    dialogue_register: int = Field(default=0, ge=0, le=3, strict=True)
    dialogue_language: str = Field(default=DEFAULT_DIALOGUE_LANGUAGE,
        pattern="^(French|English|Korean|Japanese|Russian)$")
    narrative_format: str = Field(default=DEFAULT_NARRATIVE_FORMAT, pattern="^(short|long)$")
    parent_story_id: str | None = Field(default=None, pattern="^story-[a-f0-9]{32}$")
    long_options: LongStoryOptions | None = None
    workflow_mode: str | None = Field(default=None, pattern="^(manual|automatic)$")
    visual_universe: str = Field(default="", max_length=1000)
    target_seconds: int | None = Field(default=None, ge=10, le=2160, strict=True)


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


class StoryVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)


class StoryContinuityEdit(StoryVersion):
    visual_continuity: dict


class StoryAdvance(StoryVersion):
    mode: str | None = Field(default=None, pattern="^(manual|automatic)$")
    architect_model_id: str | None = Field(default=None, min_length=1, max_length=300)
    writer_model_id: str | None = Field(default=None, min_length=1, max_length=300)


class StoryFeedback(StoryVersion):
    unit_id: str = Field(pattern="^(outline|episode-([1-9]|1[0-2]))$")
    scene_index: int | None = Field(default=None, ge=0, le=11, strict=True)
    instruction: str = Field(min_length=1, max_length=12000)
    question: bool = False


class StoryRetry(StoryVersion):
    model_id: str | None = Field(default=None, min_length=1, max_length=300)


class StorySeriesEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_id: str = Field(pattern="^episode-([1-9]|1[0-2])$")
    scene_count: int = Field(ge=1, le=12, strict=True)
    clip_seconds: int = Field(ge=5, le=15, strict=True)
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


class FollowupOpen(StoryVersion):
    source_unit_id: str | None = Field(default=None, pattern="^(standalone|episode-([1-9]|1[0-2]))$")


class FollowupVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class FollowupSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dialogue_language: str
    scene_count: int = Field(ge=1, le=12, strict=True)
    clip_seconds: int = Field(ge=5, le=15, strict=True)
    target_seconds: int = Field(ge=10, le=2160, strict=True)
    workflow_mode: str = Field(pattern="^(automatic|manual)$")
    architect_model_id: str = Field(max_length=300)
    writer_model_id: str = Field(max_length=300)


class FollowupEdit(FollowupVersion):
    direction: dict
    model_id: str = Field(max_length=300)
    settings: FollowupSettings


class FollowupMessage(FollowupVersion):
    instruction: str = Field(default="", max_length=12000)
    automatic: bool = False
    request_id: str = Field(min_length=8, max_length=100)


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

    @router.post("/projects/{project_id}/followup")
    def open_followup(project_id: str, body: FollowupOpen):
        return invoke(lambda: current().followups.open(project_id, **body.model_dump()))

    @router.get("/followups/{identity}")
    def get_followup(identity: str):
        return invoke(lambda: current().followups.get(identity))

    @router.put("/followups/{identity}")
    def edit_followup(identity: str, body: FollowupEdit):
        return invoke(lambda: current().followups.update(identity, **body.model_dump()))

    @router.post("/followups/{identity}/refresh")
    def refresh_followup(identity: str, body: FollowupVersion):
        return invoke(lambda: current().followups.refresh(identity, **body.model_dump()))

    @router.post("/followups/{identity}/messages", status_code=202)
    def discuss_followup(identity: str, body: FollowupMessage):
        return invoke(lambda: current().followups.start(identity, **body.model_dump()))

    @router.post("/followups/{identity}/cancel")
    def cancel_followup(identity: str):
        return invoke(lambda: current().followups.cancel(identity))

    @router.post("/followups/{identity}/commit")
    def commit_followup(identity: str, body: FollowupVersion):
        return invoke(lambda: current().followups.commit(identity, **body.model_dump()))

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

    @router.post("/projects/{project_id}/advance", status_code=202)
    def advance(project_id: str, body: StoryAdvance):
        return invoke(lambda: current().workflow.advance(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/pause")
    def pause(project_id: str):
        return invoke(lambda: current().workflow.pause(project_id))

    @router.post("/projects/{project_id}/feedback", status_code=202)
    def feedback(project_id: str, body: StoryFeedback):
        return invoke(lambda: current().workflow.feedback(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/select")
    def select(project_id: str, body: StorySelect):
        return invoke(lambda: current().select(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/restore")
    def restore(project_id: str, body: StoryRestore):
        return invoke(lambda: current().restore(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/revalidate")
    def revalidate(project_id: str, body: StoryVersion):
        return invoke(lambda: current().revalidate(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/retry", status_code=202)
    def retry(project_id: str, body: StoryRetry):
        return invoke(lambda: current().retry(project_id, **body.model_dump()))

    @router.post("/projects/{project_id}/series-episode")
    def select_series_episode(project_id: str, body: StorySeriesEpisode):
        values = body.model_dump()
        episode_id = values.pop("episode_id")
        expected_version = values.pop("expected_version")
        return invoke(lambda: current().select_series_episode(
            project_id, episode_id, expected_version, **values))

    @router.put("/projects/{project_id}/continuity")
    def edit_continuity(project_id: str, body: StoryContinuityEdit):
        return invoke(lambda: current().edit_continuity(project_id, body.expected_version, body.visual_continuity))

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
