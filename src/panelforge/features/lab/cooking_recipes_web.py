"""HTTP boundary for culinary projects and explicit generation commands."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field
from typing import Annotated, Literal
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from panelforge.domain.cooking_recipes import Contract, Settings, Shot
from panelforge.application.cooking_recipes import RecipeConflict


class Version(Contract):
    version: int = Field(ge=1, strict=True)


class Create(Contract):
    command: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(default="Nouvelle recette", min_length=1, max_length=120)
    settings: Settings = Field(default_factory=Settings)
    master_asset_id: str | None = Field(default=None, pattern=r"^asset-[a-zA-Z0-9_-]+$")


class Update(Version):
    name: str = Field(min_length=1, max_length=120)
    settings: Settings
    shots: list[Shot] | None = Field(default=None, min_length=1, max_length=30)


class Master(Version):
    asset_id: str = Field(pattern=r"^asset-[a-zA-Z0-9_-]+$")


class Generate(Version):
    command: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    ids: list[str] = Field(default_factory=list, max_length=30)
    feedback: str = Field(default="", max_length=4000)
    image_part: Literal["all", "end"] = "all"
    image_engine: Literal["h3", "krea2"] | None = None


class Choose(Version):
    shot_id: str = Field(max_length=80)
    kind: str = Field(pattern=r"^(image|clip)$")
    attempt_id: str = Field(max_length=100)


class Export(Version):
    ids: list[str] = Field(min_length=1, max_length=30)


class Send(Export):
    feedback: str = Field(default="", max_length=4000)
    feedbacks: dict[str, Annotated[str, Field(max_length=4000)]] = Field(default_factory=dict, max_length=30)


class ImageReview(Export):
    approved: bool = Field(default=True, strict=True)


def cooking_recipes_router(service):
    router = APIRouter(prefix="/api/recipes", tags=["recipes"])

    def invoke(fn, project=False):
        if service is None:
            raise HTTPException(503, "Recettes sera disponible au prochain démarrage du backend.")
        try:
            value = fn()
            return dict(project=service.get(value["id"])) if project else value
        except RecipeConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Projet, plan ou résultat introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except (OSError, RuntimeError) as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/spec")
    def spec():
        return invoke(lambda:dict(settings=Settings().model_dump(mode="json"), presets=service.production.presets(),
                                  min_clip_duration=5, max_clip_duration=15))

    @router.get("/sources")
    def sources():
        return invoke(lambda:dict(images=service.production.recent_images()))

    @router.get("/projects")
    def projects():
        return invoke(lambda:dict(projects=service.list()))

    @router.post("/projects")
    def create(body:Create):
        return invoke(lambda:service.create(body.command, body.name, body.settings.model_dump(mode="json"), body.master_asset_id), True)

    @router.get("/projects/{identity}")
    def get(identity:str):
        return invoke(lambda:dict(project=service.get(identity)))

    @router.put("/projects/{identity}")
    def update(identity:str, body:Update):
        return invoke(lambda:service.update(identity, body.version, body.name, body.settings.model_dump(mode="json"),
            [s.model_dump() for s in body.shots] if body.shots is not None else None), True)

    @router.post("/projects/{identity}/master")
    def master(identity:str, body:Master):
        return invoke(lambda:service.set_master(identity, body.version, body.asset_id), True)

    @router.post("/projects/{identity}/upload")
    async def upload(identity:str, version:int=Form(...), file:UploadFile=File(...)):
        content = await file.read(25 * 1024 * 1024 + 1)
        if not content or len(content) > 25 * 1024 * 1024:
            raise HTTPException(422, "Choisis une image de moins de 25 Mio.")
        return await run_in_threadpool(invoke, lambda:service.set_master(identity, version, content=content), True)

    @router.post("/projects/{identity}/approve")
    def approve(identity:str, body:Version):
        return invoke(lambda:service.approve(identity, body.version), True)

    @router.post("/projects/{identity}/generate/{kind}", status_code=202)
    def generate(identity:str, kind:str, body:Generate):
        if kind == "clip":
            raise HTTPException(409, "Utilise « Envoyer à l’Usine » puis lance la production depuis l’Usine. Actualise la page.")
        return invoke(lambda:service.enqueue(identity, body.version, body.command, kind, body.ids, body.feedback,
            body.image_part, body.image_engine), True)

    @router.post("/projects/{identity}/review-images")
    def review_images(identity:str, body:ImageReview):
        return invoke(lambda:service.review_images(identity, body.version, body.ids, body.approved), True)

    @router.post("/projects/{identity}/send")
    def send(identity:str, body:Send):
        return invoke(lambda:service.send(identity, body.version, body.ids, body.feedback, body.feedbacks))

    @router.post("/projects/{identity}/choose")
    def choose(identity:str, body:Choose):
        return invoke(lambda:service.choose(identity, **body.model_dump()), True)

    @router.post("/projects/{identity}/control/{action}")
    def control(identity:str, action:str):
        if action not in {"pause", "resume", "abandon"}:
            raise HTTPException(422, "Action inconnue.")
        return invoke(lambda:service.pause(identity, paused=action != "resume", abandon=action == "abandon"), True)

    @router.post("/projects/{identity}/export")
    def export(identity:str, body:Export):
        path, filename = invoke(lambda:service.exporter.create(service.export_selection(identity, body.version, body.ids)))
        return FileResponse(path, filename=filename, media_type="application/zip", background=BackgroundTask(path.unlink, missing_ok=True))

    return router
