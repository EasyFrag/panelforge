"""CSV intake and inexpensive current-batch monitoring."""
from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.creation_batch import CreationBatchConflict
from panelforge.application.creation_batch_csv import parse_intentions_csv
from panelforge.domain.creation_batch import MAX_BATCH_ITEMS, MAX_CSV_BYTES
from .krea2_assisted_web import _serialize_krea2_art_direction


class CreationIntentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    intention: str = Field(min_length=1, max_length=12000)


class CreationBatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    name: str = Field(min_length=1, max_length=120)
    intentions: list[CreationIntentBody] = Field(min_length=1, max_length=MAX_BATCH_ITEMS)
    model_id: str = Field(min_length=1, max_length=300)
    recipe_version: str = "6.0.0"
    language: Literal["en", "zh"] = "en"
    local_inspiration: bool = False
    preset_id: str = Field(min_length=1, max_length=128)
    preset_revision: int = Field(ge=1)
    art_style_id: str | None = Field(default=None, max_length=200)


class CreationVariantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    source_render_id: str = Field(default="initial", max_length=64)
    kind: Literal["render", "art", "preset"]
    preset_id: str | None = Field(default=None, max_length=128)
    preset_revision: int | None = Field(default=None, ge=1)
    art_style_id: str | None = Field(default=None, max_length=200)


def serialize_batch(batch, *, statuses_only=False):
    if batch is None:
        return None
    items = []
    for item in batch.items:
        value = {key: getattr(item, key) for key in ("item_id", "name", "intention", "project_id", "attempt_id",
            "prompt_status", "image_status", "message", "error", "output_asset_id", "parent_id", "factory_item_id")}
        if statuses_only:
            value.pop("intention")
            value.pop("name")
        base = f"/api/image-lab/creation-batch/batches/{batch.batch_id}/items/{item.item_id}"
        value["thumbnail_url"] = base + "/thumbnail" if item.output_asset_id else None
        value["image_url"] = f"/api/assets/{item.output_asset_id}/content" if item.output_asset_id else None
        config = item.config or batch.config
        value["variant_label"] = config.art_direction.display_name if config.art_direction else config.preset.name
        value["renders"] = [dict(render_id="initial", label="Original", status=item.image_status,
            project_id=item.project_id, attempt_id=item.attempt_id, output_asset_id=item.output_asset_id,
            error=item.error, factory_item_id=item.factory_item_id, thumbnail_url=value["thumbnail_url"],
            hover_url=base + "/thumbnail?large=true" if item.output_asset_id else None, image_url=value["image_url"])]
        for render in item.renders:
            asset = render.output_asset_id
            thumb = base + f"/renders/{render.render_id}/thumbnail"
            value["renders"].append(dict(render_id=render.render_id, label=render.label, status=render.status,
                project_id=render.project_id, attempt_id=render.attempt_id, error=render.error,
                output_asset_id=asset, factory_item_id=render.factory_item_id,
                thumbnail_url=thumb if asset else None, hover_url=thumb + "?large=true" if asset else None,
                image_url=f"/api/assets/{asset}/content" if asset else None))
        items.append(value)
    images = [render for item in items for render in item["renders"]]
    return {
        "batch_id": batch.batch_id, "name": batch.name, "revision": batch.revision,
        "created_at": batch.created_at, "terminal": batch.terminal, "statuses_only": statuses_only,
        "counts": {"total": len(images), "finished": sum(r["status"] in {"succeeded", "failed", "cancelled"} for r in images),
                   "succeeded": sum(r["status"] == "succeeded" for r in images),
                   "failed": sum(r["status"] == "failed" for r in images)},
        "preset_name": batch.config.preset.name, "items": items,
        "config": {"model_id": batch.config.model_id, "recipe_version": batch.config.recipe_version,
                   "language": batch.config.language.value, "local_inspiration": batch.config.local_inspiration,
                   "preset_id": batch.config.preset.preset_id,
                   "art_direction": _serialize_krea2_art_direction(batch.config.art_direction)},
    }


def creation_batch_router(service):
    router = APIRouter(prefix="/api/image-lab/creation-batch")

    def require():
        if service is None:
            raise HTTPException(503, "Création batch n'est pas configurée.")
        return service

    @router.post("/csv")
    async def import_creation_csv(file: Annotated[UploadFile, File()]):
        require()
        try:
            content = await file.read(MAX_CSV_BYTES + 1)
            intentions, ignored = parse_intentions_csv(content)
            return {"intentions": [asdict(item) for item in intentions], "count": len(intentions), "ignored": ignored}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            await file.close()

    @router.post("/batches", status_code=201)
    def launch_creation_batch(body: CreationBatchBody):
        try:
            values = body.model_dump()
            values["request_id"] = str(body.request_id)
            return {"batch": serialize_batch(require().create(**values))}
        except CreationBatchConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, TypeError, KeyError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/current")
    def current_creation_batch():
        active = require()
        batch = active.latest()
        return {"batch": serialize_batch(batch), "monitor": active.monitoring(batch) if batch else {}, "worker_error": active.worker_error}

    @router.get("/batches/{batch_id}")
    def get_creation_batch(batch_id: str, known_revision: int | None = None, known_count: int | None = None):
        active = require()
        try:
            batch = active.get(batch_id)
            monitor = active.monitoring(batch)
            if known_revision == batch.revision:
                return {"unchanged": True, "monitor": monitor, "worker_error": active.worker_error}
            compact = known_revision is not None and (known_count == len(batch.items) or not any(i.parent_id for i in batch.items))
            return {"batch": serialize_batch(batch, statuses_only=compact), "monitor": monitor,
                    "worker_error": active.worker_error}
        except FileNotFoundError as error:
            raise HTTPException(404, "Batch introuvable.") from error

    @router.get("/batches/{batch_id}/items/{item_id}/thumbnail")
    def creation_batch_thumbnail(batch_id: str, item_id: str, large: bool = False):
        try:
            return Response(require().thumbnail(batch_id, item_id, large=large), media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=86400"})
        except (FileNotFoundError, KeyError) as error:
            raise HTTPException(404, "Aperçu indisponible.") from error

    @router.get("/batches/{batch_id}/items/{item_id}/renders/{render_id}/thumbnail")
    def render_thumbnail(batch_id: str, item_id: str, render_id: str, large: bool = False):
        try:
            return Response(require().thumbnail(batch_id, item_id, render_id, large=large), media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=86400"})
        except (FileNotFoundError, KeyError) as error:
            raise HTTPException(404, "Aperçu indisponible.") from error

    def mutate(operation):
        try:
            batch = operation(require())
            return {"batch": serialize_batch(batch), "monitor": require().monitoring(batch)}
        except CreationBatchConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError) as error:
            raise HTTPException(404, "Image ou configuration introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, "Enregistrement non confirmé. Réessaie cette même action.") from error

    @router.post("/batches/{batch_id}/items/{item_id}/variants", status_code=201)
    def add_variant(batch_id: str, item_id: str, body: CreationVariantBody):
        return mutate(lambda active: active.add_variant(batch_id, item_id, **body.model_dump()))

    @router.post("/batches/{batch_id}/items/{item_id}/renders/{render_id}/factory")
    def send_factory(batch_id: str, item_id: str, render_id: str):
        return mutate(lambda active: active.send_to_factory(batch_id, item_id, render_id))

    return router
