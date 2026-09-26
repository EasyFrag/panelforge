"""HTTP boundary for the video factory; enqueueing never executes a workflow."""
from typing import Any
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.video_factory import FactoryConflict
from panelforge.domain.video_factory import configuration, merge_settings


class FactoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: str = "image"
    source_id: str | None = None
    session_id: str | None = None
    asset_id: str | None = None
    name: str = Field(default="Vidéo à préparer", max_length=160)
    config: dict[str, Any] = Field(default_factory=dict)
    scene_ids: list[str] | None = None
    auto_dlss: bool | None = None


class FactorySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(default_factory=list, max_length=500)
    revisions: dict[str, int] | None = None
    changes: dict[str, Any] | None = None
    preset: str | None = None
    replacements: dict[str, Any] | None = None


class FactoryOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(max_length=10000)
    revision: int


def video_factory_router(service, *, validate_image):
    router = APIRouter(prefix="/api/video-factory", tags=["video-factory"])

    def invoke(fn):
        if service is None:
            raise HTTPException(503, "L’usine n’est pas configurée.")
        try:
            return fn()
        except FactoryConflict as error:
            raise HTTPException(409, str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(404, str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("")
    def state():
        return invoke(service.snapshot if service else lambda: None)

    @router.post("/receive")
    def receive(body: FactoryBody):
        def work():
            adapter = service.adapter
            if body.source_kind == "episode":
                entries = adapter.capture_episode(body.source_id, body.scene_ids, body.auto_dlss)
            elif body.session_id:
                entries = [adapter.capture_session(body.session_id, body.config)]
            else:
                config = merge_settings(configuration(body.config.get("mode", "h3")), body.config)
                if body.source_kind == "image":
                    if not body.asset_id:
                        raise ValueError("Choisissez une image.")
                    config["references"] = [dict(asset_id=body.asset_id, role="unassigned", label=body.name)]
                elif body.source_kind not in {"h3", "ref2v"}:
                    raise ValueError("Source inconnue.")
                entries = [dict(name=body.name, config=config, source=dict(
                    kind=body.source_kind, id=body.source_id or body.asset_id,
                    view="krea2-assisted-lab" if body.source_kind == "image" else
                         "ref2v-direct" if body.source_kind == "ref2v" else "i2v-direct"))]
            return service.receive(entries)
        return invoke(work)

    @router.post("/assets")
    async def upload(image: UploadFile = File()):
        try:
            content = await image.read(25 * 1024 * 1024 + 1)
            if len(content) > 25 * 1024 * 1024:
                raise HTTPException(413, "Image limitée à 25 Mio.")
            def work():
                media_type = validate_image(content)
                asset = service.adapter.assets.create(content, media_type=media_type)
                return dict(asset_id=asset.asset_id, label=image.filename or "Image")
            return invoke(work)
        finally:
            await image.close()

    @router.patch("/items")
    def update(body: FactorySelection):
        return invoke(lambda: service.update(body.ids, body.revisions, body.changes, body.preset, body.replacements))

    @router.post("/launch")
    def launch(body: FactorySelection):
        return invoke(lambda: service.launch(body.ids, body.revisions))

    @router.post("/actions/{action}")
    def action(action: str, body: FactorySelection):
        return invoke(lambda: service.action(action, body.ids, body.revisions))

    @router.put("/order")
    def order(body: FactoryOrder):
        return invoke(lambda: service.reorder(body.ids, body.revision))

    @router.post("/items/{identity}/refresh-source")
    def refresh_source(identity: str, body: FactorySelection):
        return invoke(lambda: service.refresh_source(identity, body.revisions))

    return router
