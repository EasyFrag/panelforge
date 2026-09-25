"""Cover endpoints deliberately separate from scene/prompt mutation routes."""
import json
from typing import Literal
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from panelforge.domain.episode_thumbnails import ThumbnailConflict, MAX_RENDER_IMAGES


class ThumbnailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100)
    expected_revision: int = Field(ge=0, strict=True)
    source: Literal["series", "template", "generate", "upload"] = "series"
    template_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=80)
    number: int | None = Field(default=None, ge=1, le=9999, strict=True)
    title_mode: Literal["artwork", "overlay"] = "artwork"
    reference_ids: list[str] | None = Field(default=None, max_length=MAX_RENDER_IMAGES)
    reference_roles: dict[str, Literal["foreground", "background", "environment", "object", "style"]] | None = None
    title_style: Literal["pop", "cinema"] = "pop"
    direction: str = Field(default="", max_length=1500)
    replace: bool = Field(default=False, strict=True)


class BadgePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=100, strict=True, allow_inf_nan=False)
    y: float = Field(ge=0, le=100, strict=True, allow_inf_nan=False)


class BadgeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100)
    expected_revision: int = Field(ge=0, strict=True)
    position: BadgePosition
    remember_series: bool = Field(default=False, strict=True)


class TemplateArchiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    archived: bool = Field(strict=True)


def episode_thumbnails_router(service):
    router = APIRouter(prefix="/api/episodes")

    def current():
        thumbnails = getattr(service, "thumbnails", None)
        if thumbnails is None:
            raise HTTPException(503, "Les miniatures seront disponibles après le redémarrage du Lab à jour.")
        return thumbnails

    def invoke(action):
        try:
            return action()
        except (FileNotFoundError, KeyError) as error:
            raise HTTPException(404, "Miniature, modèle ou fabrication introuvable.") from error
        except ThumbnailConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/thumbnail-fonts/{style}")
    def font(style: Literal["pop", "cinema"]):
        return invoke(lambda: Response(current().images.font_bytes(style), media_type="font/ttf",
            headers={"Cache-Control": "public, max-age=31536000, immutable"}))

    @router.get("/{identity}/thumbnail")
    def get(identity: str):
        return invoke(lambda: current().get(identity))

    @router.post("/{identity}/thumbnail", status_code=202)
    def prepare(identity: str, body: ThumbnailBody):
        return invoke(lambda: current().prepare(identity, **body.model_dump()))

    @router.post("/{identity}/thumbnail/import", status_code=202)
    async def import_image(identity: str, options: str = Form(...), image: UploadFile = File(...)):
        try:
            body = ThumbnailBody.model_validate(json.loads(options))
        except (ValueError, ValidationError) as error:
            raise HTTPException(422, "Réglages de miniature invalides.") from error
        if body.source != "upload":
            raise HTTPException(422, "Choisis le mode Importer un modèle.")
        content = await image.read(32 * 1024 * 1024 + 1)
        if not content or len(content) > 32 * 1024 * 1024:
            raise HTTPException(422, "L’image doit peser au maximum 32 Mo.")
        return invoke(lambda: current().prepare(identity, content=content, **body.model_dump()))

    @router.get("/{identity}/thumbnail/badge-preview/{part}")
    def badge_preview(identity: str, part: Literal["background", "badge"], expected_revision: int = Query(ge=0)):
        return invoke(lambda: Response(current().badge_preview(identity, part=part, expected_revision=expected_revision),
                                      media_type="image/png", headers={"Cache-Control": "no-store"}))

    @router.post("/{identity}/thumbnail/badge")
    def reposition_badge(identity: str, body: BadgeBody):
        return invoke(lambda: current().reposition_badge(identity, **body.model_dump()))

    @router.post("/{identity}/thumbnail/templates/{template_id}/archive")
    def archive(identity: str, template_id: str, body: TemplateArchiveBody):
        return invoke(lambda: current().archive_template(identity, template_id, **body.model_dump()))

    @router.get("/{identity}/thumbnail/download")
    def download(identity: str):
        def result():
            value = current().get(identity)
            if not value.get("asset_id"):
                raise FileNotFoundError(identity)
            return Response(current().assets.read_bytes(value["asset_id"]), media_type="image/png", headers={
                "Content-Disposition": f'attachment; filename="episode-{value.get("asset_number") or value["number"]:02d}-miniature.png"',
                "Cache-Control": "no-store"})
        return invoke(result)

    return router
