"""Krea2 edit web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from typing import TypedDict
from .http_support import http_errors
import base64
from dataclasses import asdict
from typing import Annotated, Literal
from panelforge.domain.krea2_edit import KREA2_EDIT_REF_BOOST_MAX, Krea2EditCrop
from panelforge.domain.firered_edit import FireRedEditSettings
from panelforge.domain.edit_settings import edit_engine, edit_settings_record, edit_render_dimensions, edit_output_dimensions
from fastapi import BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from panelforge.application.krea2_edit import RetouchConflictError
from panelforge.application import ChangeViewRunner, Krea2EditAttemptRequest, Krea2EditService
from panelforge.domain import Krea2AspectRatio, Krea2EditSettings, Krea2EditSource, Krea2EditSourceState, Krea2LoraSelection, Krea2PromptLanguage
from panelforge.infrastructure.krea2_image_metadata import recover_krea2_metadata
from fastapi import APIRouter
from .http_streaming import stream_response
from .http_support import _parse_json_seed, _serialize_llm_model
from .krea2_resources_web import Krea2LoraBody
from .media_http import MAX_IMAGE_BYTES, detect_image_media_type


class Krea2EditPromptBody(BaseModel):
    instruction: str
    model_id: str
    base_prompt: str | None = None
    feedback_attempt_id: str | None = None
    prompt_language: str | None = None
    assistance_version: str = "1.0.0"
    render_engine: Literal["krea2", "firered"] = "krea2"


class Krea2EditAttemptBody(BaseModel):
    prompt: str
    model_id: str
    aspect_ratio: str | None = None
    megapixels: float
    seed: str | int
    ref_boost: float | None = None
    steps: int | None = None
    loras: list[Krea2LoraBody] | None = None
    workflow_version: str | None = None
    workflow_id: str | None = None
    engine: Literal["krea2", "firered"] = "krea2"
    mode: Literal["lightning", "standard"] | None = None
    cfg: float | None = None


class Krea2EditSourceStateBody(BaseModel):
    state: str


class Krea2EditUpscaleBody(BaseModel):
    model_name: str = Field(min_length=1, max_length=512)
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$", strict=True)


class Krea2EditResumeBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$", strict=True)


class Krea2EditRestartBody(BaseModel):
    expected_restart_count: int = Field(ge=0, strict=True)


class Krea2EditPromotionBody(BaseModel):
    project_name: str | None = None
    step_name: str | None = None


class Krea2EditCropBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$", strict=True)
    source_asset_id: str = Field(min_length=1, max_length=128, strict=True)
    restart_count: int = Field(ge=0, strict=True)
    source_width: int = Field(gt=0, strict=True)
    source_height: int = Field(gt=0, strict=True)
    x: int = Field(ge=0, strict=True)
    y: int = Field(ge=0, strict=True)
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    project_name: str | None = Field(default=None, max_length=120)


def _serialize_edit_settings(settings, dimensions=None) -> dict[str, object]:
    record = edit_settings_record(settings)
    record["model_id"] = record.pop("model_name")
    if dimensions is None and isinstance(settings, Krea2EditSettings):
        dimensions = settings.resolution
    record["resolution"] = {"width": dimensions[0], "height": dimensions[1]} if dimensions else None
    return record


def _serialize_edit_dimensions(dimensions):
    return {"width": dimensions[0], "height": dimensions[1]} if dimensions else None


class Krea2EditSourcePayload(TypedDict):
    id: str
    source_id: str
    restart_count: int
    revision: dict[str, object] | None
    copied_from_source_id: str | None
    revision_activation: int
    resume_attempt_id: str | None
    source_asset_id: str
    source_url: str
    subject_reference: dict[str, object] | None
    filename: str
    project_id: str | None
    stage_index: int
    parent_source_id: str | None
    parent_attempt_id: str | None
    accepted_attempt_id: str | None
    project_name: str | None
    accepted_label: str | None
    export: dict[str, object]
    source_batch_id: str | None
    source_batch_item_id: str | None
    prompt_language: str
    state: str
    recipe: dict[str, object]
    metadata: dict[str, object]
    prompt_status: str
    instruction: str
    generated_prompt: str | None
    raw_prompt_response: str | None
    prompt_model_id: str | None
    prompt_error: str | None
    revisions: list[dict[str, object]]
    attempts: list[dict[str, object]]


def serialize_krea2_edit_source(source: Krea2EditSource) -> Krea2EditSourcePayload:
    metadata = source.metadata
    return {
        "id": source.source_id,
        "source_id": source.source_id,
        "restart_count": source.restart_count,
        "revision": asdict(source.revision) if source.revision else None,
        "copied_from_source_id": source.copied_from_source_id,
        "revision_activation": source.revision_activation,
        "resume_attempt_id": (source.revision.attempt_id if source.revision
                              and source.accepted_attempt_id is None
                              and source.copied_from_source_id == source.revision.source_id
                              and len(source.attempts) == source.revision.attempt_count
                              and not source.restart_count else None),
        "source_asset_id": source.source_asset_id,
        "source_url": f"/api/assets/{source.source_asset_id}/content",
        "subject_reference": ({**asdict(source.subject_reference),
                               "url": f"/api/assets/{source.subject_reference.asset_id}/content"}
                              if source.subject_reference else None),
        "filename": source.filename,
        "project_id": source.project_id,
        "stage_index": source.stage_index,
        "parent_source_id": source.parent_source_id,
        "parent_attempt_id": source.parent_attempt_id,
        "accepted_attempt_id": source.accepted_attempt_id,
        "project_name": source.project_name,
        "accepted_label": source.accepted_label,
        "export": {
            "status": (
                "failed"
                if source.export_error is not None
                else "exported"
                if source.export_path is not None
                else "pending"
            ),
            "path": source.export_path,
            "error": source.export_error,
        },
        "source_batch_id": source.source_batch_id,
        "source_batch_item_id": source.source_batch_item_id,
        "prompt_language": source.prompt_language.value,
        "state": source.state.value,
        "recipe": {
            "id": source.recipe.recipe_id,
            "engine": "firered" if source.recipe.recipe_id == "firered.image_edit" else "krea2",
            "version": source.recipe.version,
            "workflow_sha256": source.recipe.workflow_sha256,
        },
        "metadata": {
            "engine": "firered" if metadata.firered_settings else "krea2",
            "firered_settings": _serialize_edit_settings(metadata.firered_settings) if metadata.firered_settings else None,
            "prompt": metadata.prompt,
            "model_id": metadata.model_name,
            "aspect_ratio": metadata.aspect_ratio.value if metadata.aspect_ratio else None,
            "megapixels": metadata.megapixels,
            "seed": str(metadata.seed) if metadata.seed is not None else None,
            "loras": [
                {"name": value.name, "strength": value.strength}
                for value in metadata.loras
            ],
            "origin": metadata.origin,
            "warnings": list(metadata.warnings),
            "ref_boost": metadata.ref_boost,
            "steps": metadata.steps,
        },
        "prompt_status": source.prompt_status.value,
        "instruction": source.instruction,
        "generated_prompt": source.generated_prompt,
        "raw_prompt_response": source.raw_prompt_response,
        "prompt_model_id": source.prompt_model_id,
        "prompt_error": source.prompt_error,
        "revisions": [
            {
                "revision_id": revision.revision_id,
                "instruction": revision.instruction,
                "base_prompt": revision.base_prompt,
                "prompt": revision.prompt,
                "model_id": revision.model_id,
                "prompt_language": revision.prompt_language.value,
                "feedback_attempt_id": revision.feedback_attempt_id,
                "assistant_message": revision.assistant_message,
                "assistance_version": revision.assistance_version,
                "render_engine": revision.render_engine,
            }
            for revision in source.revisions
        ],
        "attempts": [
            {
                "id": attempt.attempt_id,
                "attempt_id": attempt.attempt_id,
                "kind": attempt.kind,
                "label": source.attempt_label(attempt.attempt_id),
                "crop": asdict(attempt.crop) if attempt.crop else None,
                "workflow_version": (attempt.recipe or source.recipe).version,
                "workflow_id": (attempt.recipe or source.recipe).recipe_id,
                "engine": edit_engine(attempt.settings),
                "output_dimensions": _serialize_edit_dimensions(edit_output_dimensions(attempt)),
                "workflow_sha256": (attempt.recipe or source.recipe).workflow_sha256,
                "retouch": asdict(attempt.retouch) if attempt.retouch else None,
                "upscale": asdict(attempt.upscale) if attempt.upscale else None,
                "dlss": asdict(attempt.dlss) if attempt.dlss else None,
                "prompt": attempt.prompt,
                "status": attempt.status.value,
                "execution_id": attempt.execution_id,
                "output_asset_id": attempt.output_asset_id,
                "output_url": (
                    f"/api/assets/{attempt.output_asset_id}/content"
                    if attempt.output_asset_id is not None
                    else None
                ),
                "error": attempt.error,
                "accepted": attempt.attempt_id == source.accepted_attempt_id,
                "settings": _serialize_edit_settings(attempt.settings, edit_render_dimensions(source, attempt)),
            }
            for attempt in source.attempts
        ],
    }


def _require_krea2_edit(value: Krea2EditService | None) -> Krea2EditService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Edit Lab is not configured",
        )
    return value


def krea2_edit_router(*, image_catalogs, krea2_edit: Krea2EditService | None, krea2_resources, runner: ChangeViewRunner) -> APIRouter:
    router = APIRouter()

    @router.get("/api/image-lab/krea2-edit/spec")
    def krea2_edit_spec(refresh: bool = False) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        return {
            "recipe": {
                "id": service.workflow.reference.recipe_id,
                "engine": service.workflow.engine,
                "version": service.workflow.reference.version,
                "workflow_sha256": service.workflow.reference.workflow_sha256,
                "status": service.workflow.status,
            },
            **image_catalogs.read(krea2_resources, service,
                                  _serialize_llm_model, refresh=refresh),
            "engines": [{"id": name, "name": "FireRed 1.1" if name == "firered" else "KREA2"}
                        for name in dict.fromkeys(item.engine for item in service.workflows)],
            "workflows": [{"id": item.reference.recipe_id, "engine": item.engine,
                           "requires_subject_reference": bool(getattr(item, "requires_subject_reference", False)),
                           "version": item.reference.version, "name": item.display_name,
                           "workflow_sha256": item.reference.workflow_sha256, "defaults": item.defaults}
                          for item in service.workflows],
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "defaults": service.workflow.defaults,
            "limits": {
                "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
                "ref_boost": {"minimum": 0.0, "maximum": KREA2_EDIT_REF_BOOST_MAX, "step": 0.1},
                "steps": {"minimum": 1, "maximum": 100},
                "lora_count": 10,
            },
            "fixed": {
                "identity_lora": "krea2/krea2_identity_edit_v1_2.safetensors",
                "identity_lora_strength": 1.0,
                "cfg": 1.0,
                "sampler": "euler",
                "scheduler": "simple",
                "grounding_px": 768,
            },
            "retouch": {"enabled": service.retouch_compositor is not None,
                        "version": "1.0.0", "max_pixels": 16_000_000},
            "upscale": {"enabled": service.upscale_workflow is not None and service.upscale_images is not None},
            "project_exports": {
                "enabled": service.project_export_root is not None,
                "root": service.project_export_root,
            },
        }

    @router.get("/api/image-lab/krea2-edit/upscalers")
    def list_krea2_edit_upscalers() -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        if service.upscale_workflow is None:
            raise HTTPException(status_code=503, detail="L’amélioration des détails n’est pas configurée.")
        try:
            models = service.comfy.list_upscale_models()
        except Exception as error:
            raise HTTPException(status_code=503, detail="Impossible de lire les upscalers de ComfyUI. Réessaie.") from error
        preferred = service.upscale_workflow.preferred_model
        return {"models": list(models), "default": preferred if preferred in models else next(iter(models), None)}

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/upscale", status_code=202)
    def upscale_krea2_edit_attempt(source_id: str, attempt_id: str, body: Krea2EditUpscaleBody,
                                  background_tasks: BackgroundTasks) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source, candidate, should_start = service.queue_upscale(source_id, attempt_id,
                model_name=body.model_name, request_id=body.request_id)
            # A retried POST must never resubmit a queued, running or finished job.
            if should_start:
                background_tasks.add_task(service.execute_attempt, source_id, candidate.attempt_id)
            return {"source": serialize_krea2_edit_source(source), "attempt_id": candidate.attempt_id}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Image ou essai introuvable.") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail="L’amélioration n’a pas pu être lancée. Réessaie sans changer de sélection.") from error

    @router.post("/api/image-lab/krea2-edit/sources", status_code=status.HTTP_201_CREATED)
    async def create_krea2_edit_source(
        source_image: Annotated[UploadFile, File()],
        sidecar: Annotated[UploadFile | None, File()] = None,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            content = await source_image.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("source image exceeds the 25 MiB limit")
            media_type = detect_image_media_type(content)
            sidecar_content = None
            if sidecar is not None:
                sidecar_content = await sidecar.read(2 * 1024 * 1024 + 1)
                if len(sidecar_content) > 2 * 1024 * 1024:
                    raise ValueError("metadata sidecar exceeds the 2 MiB limit")
            asset = runner.assets.create(content, media_type=media_type)
            metadata = recover_krea2_metadata(content, sidecar=sidecar_content)
            source = service.add_source(
                asset_id=asset.asset_id,
                filename=source_image.filename or "source.png",
                metadata=metadata,
            )
            return {"source": serialize_krea2_edit_source(source)}
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await source_image.close()
            if sidecar is not None:
                await sidecar.close()

    @router.get("/api/image-lab/krea2-edit/sources")
    def list_krea2_edit_sources(
        limit: int = 100,
        include_hidden: bool = False,
        project_limit: int | None = None,
        project_id: str | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            if project_limit is not None:
                backlog = service.backlog(project_limit, project_id=project_id)
                return {
                    "sources": [serialize_krea2_edit_source(source) for source in backlog.sources],
                    "versions": backlog.versions,
                    "backlog_project_ids": list(backlog.project_ids),
                    "project_count": backlog.project_count,
                }
            return {
                "sources": [
                    serialize_krea2_edit_source(source)
                    for source in service.list(limit, include_hidden=include_hidden)
                ],
                "versions": service.project_versions(),
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/image-lab/krea2-edit/sources/{source_id}")
    def get_krea2_edit_source(source_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {"source": serialize_krea2_edit_source(service.get(source_id)),
                    "versions": service.project_versions()}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source not found") from error

    @router.get("/api/image-lab/krea2-edit/projects/{project_id}")
    def get_krea2_edit_project(project_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {"sources": [serialize_krea2_edit_source(s) for s in service.project_stages(project_id)],
                    "versions": service.project_versions()}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Version introuvable.") from error

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/resume")
    def resume_krea2_edit_stage(source_id: str, body: Krea2EditResumeBody) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source = service.resume_stage(source_id, request_id=body.request_id)
            return {"source": serialize_krea2_edit_source(source), "versions": service.project_versions()}
        except RetouchConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Étape ou image introuvable.") from error
        except OSError as error:
            raise HTTPException(status_code=500, detail="Impossible d’enregistrer la reprise. L’ancienne version est conservée ; réessaie.") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/restart")
    def restart_krea2_edit_stage(source_id: str, body: Krea2EditRestartBody) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source = service.restart_stage(source_id, expected_restart_count=body.expected_restart_count)
            return {"source": serialize_krea2_edit_source(source)}
        except RetouchConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Étape introuvable.") from error
        except OSError as error:
            raise HTTPException(status_code=500, detail="Impossible d’enregistrer la reprise. L’étape est conservée ; réessaie.") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/prompt/stream")
    def stream_krea2_edit_prompt(
        source_id: str,
        body: Krea2EditPromptBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_krea2_edit(krea2_edit)
        try:
            prompt_language = (
                Krea2PromptLanguage(body.prompt_language)
                if body.prompt_language is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return stream_response(service.stream_prepare_prompt(source_id, body.instruction, body.model_id, base_prompt=body.base_prompt, feedback_attempt_id=body.feedback_attempt_id, prompt_language=prompt_language, include_reasoning=include_reasoning, assistance_version=body.assistance_version, render_engine=body.render_engine), serialize=serialize_krea2_edit_source, entity='source', fields=())

    @router.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_krea2_edit_attempt(
        source_id: str,
        body: Krea2EditAttemptBody,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit source not found'):
            if body.engine == "firered":
                if body.ref_boost is not None or body.loras or body.aspect_ratio not in {None, "source"}:
                    raise ValueError("FireRed conserve le ratio source et n’utilise pas Ref boost ni les LoRA KREA2.")
                settings = FireRedEditSettings(model_name=body.model_id, megapixels=body.megapixels,
                    seed=_parse_json_seed(body.seed), mode=body.mode or "lightning", steps=body.steps, cfg=body.cfg)
            else:
                if body.mode is not None or body.cfg is not None:
                    raise ValueError("Mode FireRed et CFG ne s’appliquent pas au workflow KREA2.")
                settings = Krea2EditSettings(model_name=body.model_id,
                    aspect_ratio=Krea2AspectRatio(body.aspect_ratio), megapixels=body.megapixels,
                    seed=_parse_json_seed(body.seed), ref_boost=body.ref_boost if body.ref_boost is not None else 2.5,
                    steps=body.steps if body.steps is not None else 10,
                    loras=tuple(Krea2LoraSelection(name=value.name, strength=value.strength) for value in (body.loras or [])))
            source = service.prepare_attempt(
                source_id,
                Krea2EditAttemptRequest(
                    prompt=body.prompt,
                    workflow_version=body.workflow_version,
                    workflow_id=body.workflow_id,
                    settings=settings,
                ),
            )
            return {"source": serialize_krea2_edit_source(source)}

    @router.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_krea2_edit_attempt(
        source_id: str,
        attempt_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit source or attempt not found'):
            source = service.queue_attempt(source_id, attempt_id)
        background_tasks.add_task(service.execute_attempt, source_id, attempt_id)
        return {"source": serialize_krea2_edit_source(source)}

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/cancel")
    def cancel_krea2_edit_attempt(source_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit source or attempt not found'):
            return {
                "source": serialize_krea2_edit_source(
                    service.cancel_attempt(source_id, attempt_id)
                )
            }

    @router.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/promote",
        status_code=status.HTTP_201_CREATED,
    )
    def promote_krea2_edit_attempt(
        source_id: str,
        attempt_id: str,
        body: Krea2EditPromotionBody | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit source or attempt not found'):
            return {
                "source": serialize_krea2_edit_source(
                    service.promote_attempt(
                        source_id,
                        attempt_id,
                        project_name=body.project_name if body else None,
                        step_name=body.step_name if body else None,
                    )
                )
            }

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/crop", status_code=201)
    def crop_krea2_edit_source(source_id: str, body: Krea2EditCropBody) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            crop = Krea2EditCrop(**body.model_dump(exclude={"project_name"}))
            return {"source": serialize_krea2_edit_source(
                service.crop_source(source_id, crop, project_name=body.project_name))}
        except RetouchConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Image à recadrer introuvable.") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/retouch")
    def prepare_krea2_edit_retouch(source_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('Image de retouche introuvable.'):
            result = service.prepare_retouch(source_id, attempt_id)
            for name in ("source", "generated", "harmonized", "mask"):
                content = result.pop(f"{name}_png")
                result[f"{name}_url"] = (
                    "data:image/png;base64," + base64.b64encode(content).decode("ascii")
                    if content is not None else None
                )
            return result

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/retouch",
              status_code=status.HTTP_201_CREATED)
    async def save_krea2_edit_retouch(
        source_id: str, attempt_id: str,
        mask: Annotated[UploadFile, File()],
        request_id: Annotated[str, Form(min_length=1, max_length=80)],
        harmonize: Annotated[bool, Form()] = False,
        harmonize_strength: Annotated[int, Form(ge=0, le=100)] = 100,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            content = await mask.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("Le masque dépasse 25 Mio.")
            source, candidate = await run_in_threadpool(
                service.save_retouch, source_id, attempt_id, content, request_id=request_id,
                harmonize=harmonize, harmonize_strength=harmonize_strength,
            )
            return {"source": serialize_krea2_edit_source(source), "attempt_id": candidate.attempt_id}
        except RetouchConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Image de retouche introuvable.") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await mask.close()

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/export")
    def retry_krea2_edit_project_export(source_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit project not found'):
            return {
                "source": serialize_krea2_edit_source(
                    service.retry_project_export(source_id)
                )
            }

    @router.post("/api/image-lab/krea2-edit/sources/{source_id}/state")
    def update_krea2_edit_source_state(
        source_id: str,
        body: Krea2EditSourceStateBody,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        with http_errors('KREA2 edit source not found'):
            source = service.set_state(source_id, Krea2EditSourceState(body.state))
            return {"source": serialize_krea2_edit_source(source)}

    return router
