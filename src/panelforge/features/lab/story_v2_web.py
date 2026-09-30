"""HTTP boundary for the short story V2 workshop."""
from fastapi import APIRouter, HTTPException
from pydantic import Field
from panelforge.domain.story_v2 import Contract, Settings, Script, DEFAULT_MODEL, DEFAULT_PROMPT_MODEL
from panelforge.application.story_v2 import StoryV2Conflict

class Create(Contract):
    command: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    settings: Settings
class Version(Contract):
    version: int = Field(ge=1, strict=True)
class Update(Version):
    script: Script | None = None
    settings: Settings
class Restore(Version):
    index: int = Field(ge=0, strict=True)
class Revise(Version):
    feedback: str = Field(min_length=1, max_length=6000)
    sequence_id: str | None = Field(default=None, pattern=r"^seq-[0-9]+$")
class Generate(Version):
    ids: list[str] = Field(min_length=0, max_length=180)
    command: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")

def story_v2_router(service):
    router = APIRouter(prefix="/api/stories-v2", tags=["stories-v2"])
    def invoke(fn, project=False):
        if service is None:
            raise HTTPException(503, "Histoire V2 sera disponible au prochain démarrage du backend.")
        try:
            value = fn()
            return {"project":service.get(value["id"])} if project else value
        except StoryV2Conflict as e: raise HTTPException(409, str(e)) from e
        except FileNotFoundError as e: raise HTTPException(404, "Histoire introuvable.") from e
        except (ValueError, TypeError, KeyError) as e: raise HTTPException(422, str(e)) from e
        except (OSError, RuntimeError) as e: raise HTTPException(503, str(e)) from e
    @router.get("/spec")
    def spec():
        return dict(writer_model=DEFAULT_MODEL, reader_model=DEFAULT_MODEL, prompt_model=DEFAULT_PROMPT_MODEL,
                    polish_model=DEFAULT_PROMPT_MODEL, scene_duration=10, max_duration=180, modes=["manual", "automatic"])
    @router.get("/preferences")
    def preferences(): return invoke(lambda:dict(settings=service.preferences()))
    @router.get("/projects")
    def projects(): return invoke(lambda:dict(projects=service.list()))
    @router.post("/projects", status_code=202)
    def create(body:Create): return invoke(lambda:service.create(body.command, body.settings.model_dump()), True)
    @router.get("/projects/{identity}")
    def get(identity:str): return invoke(lambda:dict(project=service.get(identity)))
    @router.put("/projects/{identity}")
    def update(identity:str, body:Update):
        return invoke(lambda:service.update(identity, body.version, body.script.model_dump() if body.script else None,
                                             body.settings.model_dump()), True)
    @router.post("/projects/{identity}/restore")
    def restore(identity:str, body:Restore):
        return invoke(lambda:service.restore(identity, body.version, body.index), True)
    @router.post("/projects/{identity}/revise", status_code=202)
    def revise(identity:str, body:Revise):
        return invoke(lambda:service.revise(identity, body.version, body.feedback, body.sequence_id), True)
    @router.post("/projects/{identity}/approve")
    def approve(identity:str, body:Version): return invoke(lambda:service.approve(identity, body.version), True)
    @router.post("/projects/{identity}/references", status_code=202)
    def references(identity:str, body:Generate):
        return invoke(lambda:service.generate_references(identity, body.version, body.ids, body.command), True)
    @router.post("/projects/{identity}/produce", status_code=202)
    def produce(identity:str, body:Version): return invoke(lambda:service.produce(identity, body.version), True)
    @router.post("/projects/{identity}/pause")
    def pause(identity:str): return invoke(lambda:service.pause(identity), True)
    @router.post("/projects/{identity}/resume", status_code=202)
    def resume(identity:str, body:Version): return invoke(lambda:service.resume(identity, body.version), True)
    return router
