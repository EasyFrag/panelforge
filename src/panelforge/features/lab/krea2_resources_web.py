"""Krea2 resources web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from .http_support import http_errors
from fastapi import HTTPException
from pydantic import BaseModel, Field
from panelforge.domain import Krea2PromptLanguage
from panelforge.infrastructure.krea2_resources import Krea2LoraCategory, Krea2ResourcePrecision, Krea2ResourceSafety, serialize_krea2_resource
from fastapi import APIRouter


class Krea2LoraBody(BaseModel):
    name: str
    strength: float


class Krea2ResourcePreferenceBody(BaseModel):
    favorite: bool | None = None
    safety: str | None = None
    category: str | None = None
    precision: str | None = None
    display_name: str | None = Field(default=None, max_length=200)
    strength_min: float | None = Field(default=None, ge=-1, le=1)
    strength_max: float | None = Field(default=None, ge=-1, le=1)
    notes: str | None = Field(default=None, max_length=4_000)


def _krea2_prompt_language(value: str | None) -> Krea2PromptLanguage | None:
    return Krea2PromptLanguage(value) if value is not None else None


def _require_krea2_resources(value):
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 resource catalog is not configured",
        )
    return value


def krea2_resources_router(*, krea2_resources) -> APIRouter:
    router = APIRouter()

    @router.get("/api/image-lab/krea2-batch/resources/{resource_id}")
    def krea2_resource_detail(resource_id: str) -> dict[str, object]:
        resources = _require_krea2_resources(krea2_resources)
        try:
            read = getattr(resources, "get_ui_detail", resources.get)
            return serialize_krea2_resource(read(resource_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Ressource introuvable dans le catalogue.") from error

    @router.post("/api/image-lab/krea2-batch/resources/{resource_id}/preference")
    def update_krea2_resource_preference(
        resource_id: str,
        body: Krea2ResourcePreferenceBody,
    ) -> dict[str, object]:
        resources = _require_krea2_resources(krea2_resources)
        with http_errors('KREA2 resource not found', missing=(KeyError,)):
            safety = Krea2ResourceSafety(body.safety) if body.safety is not None else None
            lora_category = (
                Krea2LoraCategory(body.category)
                if body.category is not None
                else None
            )
            reset_precision = body.precision == "auto"
            precision = (
                None
                if body.precision is None or reset_precision
                else Krea2ResourcePrecision(body.precision)
            )
            resource = resources.set_preference(
                resource_id,
                favorite=body.favorite,
                safety=safety,
                lora_category=lora_category,
                precision=precision,
                reset_precision=reset_precision,
            )
            annotation_fields = {
                "display_name", "strength_min", "strength_max", "notes",
            }
            annotations = {
                field: getattr(body, field)
                for field in annotation_fields
                if field in body.model_fields_set
            }
            if annotations:
                resource = resources.set_annotations(
                    resource_id,
                    annotations,
                )
            publish = getattr(resources, "publish_ui_resource", None)
            if callable(publish):
                publish(resource)
            return serialize_krea2_resource(resource)

    @router.post("/api/image-lab/krea2-batch/resources/{resource_id}/refresh")
    def refresh_krea2_resource(resource_id: str) -> dict[str, object]:
        resources = _require_krea2_resources(krea2_resources)
        try:
            resource = resources.refresh_remote(resource_id)
            publish = getattr(resources, "publish_ui_resource", None)
            if callable(publish):
                publish(resource)
            return serialize_krea2_resource(resource)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="KREA2 resource not found") from error

    return router
