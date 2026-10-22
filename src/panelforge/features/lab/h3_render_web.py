"""H3 render web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from typing import TypedDict
from .http_support import http_errors
from panelforge.domain.h3_render import H3VideoLoraStack
import asyncio
from dataclasses import asdict
from panelforge.domain.h3_bunny import BUNNY_RECIPE_ID, H3BunnySettings, bunny_geometry
from panelforge.domain.h3_render import H3RenderSetup, h3_upscale_plan
import hashlib
from typing import Annotated, Any, Callable, Literal
from fastapi import BackgroundTasks, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from panelforge.application import H3RenderService
from panelforge.domain import H3RenderInputMode, H3RenderProject, H3VideoLoraSelection, VideoAspectRatio, VideoLabSettings
from panelforge.infrastructure.krea2_resources import serialize_krea2_resource
from fastapi import APIRouter
from .http_streaming import stream_response
from .http_support import _parse_json_seed, _serialize_llm_model
from .krea2_resources_web import Krea2ResourcePreferenceBody
from .media_http import MAX_IMAGE_BYTES, detect_image_media_type
from .render_events import _connect_video_preview, _relay_video_preview, _report_machine_render_progress


class H3RenderChatBody(BaseModel):
    message: str
    dialogue_level: int | None = Field(default=None, ge=0, le=3, strict=True)
    model_id: str | None = None
    feedback_attempt_id: str | None = None
    revision_version: str | None = None
    revision_audacity: int = Field(default=0, ge=0, le=3)
    repair_rejected: bool = False


class H3VideoLoraBody(BaseModel):
    name: str
    strength: float = Field(default=0.5, ge=0, le=1)
    clip_last_layer: int | None = -2


class H3BunnyBody(BaseModel):
    turbo_enabled: bool = Field(default=True, strict=True)
    base_steps: int = Field(default=9, ge=2, le=100, strict=True)
    coarse_steps: int = Field(default=4, ge=1, le=99, strict=True)
    refine_steps: int = Field(default=5, ge=3, le=5, strict=True)
    lora_second_strength: float = Field(default=0.2, ge=0, le=1, allow_inf_nan=False, strict=True)
    preview_enabled: bool = Field(default=True, strict=True)


class H3VideoLoraSlotBody(BaseModel):
    name: str
    strength: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False, strict=True)
    second_strength: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False, strict=True)
    enabled: bool = Field(default=True, strict=True)


class H3VideoLoraStackBody(BaseModel):
    entries: list[H3VideoLoraSlotBody] = Field(default_factory=list, max_length=4)
    enabled: bool = Field(default=True, strict=True)
    clip_last_layer: int | None = Field(default=-2, strict=True)
    version: str = "0.2.0"


class H3RenderAttemptBody(BaseModel):
    dance_stage: Literal["full", "draft"] = "full"
    prompt: str
    aspect_ratio: str
    megapixels: float
    duration_seconds: float
    steps: int
    seed: str | int | None = None
    seed_locked: bool = True
    music_enabled: bool = False
    spectrum_enabled: bool = False
    video_lora: H3VideoLoraBody | None = None
    initial_megapixels: float = Field(default=0.2, ge=0.1, le=16, allow_inf_nan=False, strict=True)
    force_upscale: bool = Field(default=False, strict=True)
    recipe_id: str | None = None
    recipe_version: str | None = None
    bunny: H3BunnyBody | None = None
    checkpoint: str | None = Field(default=None, max_length=512)
    video_loras: H3VideoLoraStackBody | None = None


class H3RenderFeedbackBody(BaseModel):
    attempt_id: str | None = None


class H3Ref2VConversionBody(H3RenderAttemptBody):
    request_id: str
    model_id: str
    extra_reference_asset_id: str | None = None
    extra_reference_label: str = "Référence ajoutée"


class H3RenderProjectPayload(TypedDict):
    id: str
    dance_reference: dict[str, object] | None
    project_id: str
    source_session_id: str
    source_prompt_revision_id: str
    prompt_language: str
    model_id: str
    revision_model_id: str | None
    input_mode: str
    preparation: dict[str, object]
    cinematic_settings: dict[str, object] | None
    sensual_settings: dict[str, object] | None
    combat_settings: dict[str, object] | None
    combat_shot_count: int | None
    revision_versions: list[dict[str, object]]
    dialogue_level: int
    adaptation: dict[str, object] | None
    current_prompt: str
    revision_version: str | None
    camera_clauses: list[str]
    revision_draft: str | None
    revision_error: str | None
    revision_draft_version: str | None
    planned_cut_times_ms: list[int]
    first_frame: dict[str, object] | None
    last_frame: dict[str, object] | None
    references: list[dict[str, object] | None]
    turns: list[dict[str, object]]
    attempts: list[dict[str, object]]
    feedback_attempt_id: str | None
    warnings: list[str]


def serialize_h3_render_project(project: H3RenderProject) -> H3RenderProjectPayload:
    adaptation = asdict(project.adaptation) if project.adaptation is not None else None
    if adaptation is not None:
        adaptation["render_setup"]["settings"]["seed"] = str(project.adaptation.render_setup.settings.seed)
    def reference(asset_id: str | None, label: str | None, role: str) -> dict[str, object] | None:
        if asset_id is None:
            return None
        return {
            "asset_id": asset_id,
            "label": label,
            "role": role,
            "content_url": f"/api/assets/{asset_id}/content",
        }

    attempts = []
    for attempt in project.attempts:
        geometry = bunny_geometry(attempt.settings, attempt.initial_megapixels) if attempt.bunny else None
        upscale = None if attempt.bunny else h3_upscale_plan(
            attempt.settings,
            attempt.initial_megapixels,
            force_upscale=attempt.force_upscale,
        )
        effective_resolution = (
            geometry["width"], geometry["height"]
        ) if geometry else (
            upscale["initial_resolution"]
            if attempt.upscale_bypassed
            else upscale["target_resolution"]
        )
        if attempt.dance_stage == "draft":
            effective_resolution = (geometry["initial_width"], geometry["initial_height"]) if geometry else upscale["initial_resolution"]
        settings = {
            "aspect_ratio": attempt.settings.aspect_ratio.value,
            "megapixels": attempt.settings.megapixels,
            "duration_seconds": attempt.settings.duration_seconds,
            "effective_duration_seconds": attempt.settings.effective_duration_seconds,
            "steps": attempt.settings.steps,
            "seed": str(attempt.settings.seed),
            "seed_locked": attempt.settings.seed_locked,
            "resolution": {
                "width": effective_resolution[0],
                "height": effective_resolution[1],
            },
            "requested_resolution": {
                "width": attempt.settings.resolution[0],
                "height": attempt.settings.resolution[1],
            },
            "frames": attempt.settings.frame_count,
        }
        attempts.append({
            "id": attempt.attempt_id,
            "dance_stage": attempt.dance_stage,
            "source_attempt_id": attempt.source_attempt_id,
            "can_finalize": attempt.dance_stage == "draft" and attempt.status.value == "succeeded" and len(attempt.latent_asset_ids) == 2,
            "recipe": asdict(attempt.recipe) if attempt.recipe else None,
            "bunny": asdict(attempt.bunny) if attempt.bunny else None,
            "checkpoint": attempt.checkpoint,
            "video_loras": asdict(attempt.video_loras) if attempt.video_loras is not None else None,
            "model_loading": asdict(attempt.model_loading) if attempt.model_loading else None,
            "initial_megapixels": attempt.initial_megapixels,
            "force_upscale": attempt.force_upscale,
            "upscale_bypassed": attempt.upscale_bypassed,
            "bunny_geometry": geometry,
            "attempt_id": attempt.attempt_id,
            "index": attempt.index,
            "dlss": asdict(attempt.dlss) if attempt.dlss else None,
            "status": attempt.status.value,
            "prompt": attempt.prompt,
            "effective_prompt": attempt.effective_prompt,
            "music_enabled": attempt.music_enabled,
            "spectrum_enabled": attempt.spectrum_enabled,
            "video_lora": (
                {
                    "name": attempt.video_lora.name,
                    "strength": attempt.video_lora.strength,
                    "clip_last_layer": attempt.video_lora.clip_last_layer,
                    "overlay_version": attempt.video_lora.overlay_version,
                }
                if attempt.video_lora is not None
                else None
            ),
            "settings": settings,
            "execution_id": attempt.execution_id,
            "compiled_workflow_sha256": attempt.compiled_workflow_sha256,
            "output_asset_id": attempt.output_asset_id,
            "output_url": (
                f"/api/assets/{attempt.output_asset_id}/content"
                if attempt.output_asset_id else None
            ),
            "events_url": (
                f"/api/h3-render/projects/{project.project_id}/attempts/"
                f"{attempt.attempt_id}/events"
            ),
            "keyframe_timestamps_ms": list(attempt.keyframe_timestamps_ms),
            "keyframes": [
                {
                    "asset_id": frame.asset_id,
                    "timestamp_ms": frame.timestamp_ms,
                    "label": frame.label,
                    "content_url": f"/api/assets/{frame.asset_id}/content",
                }
                for frame in attempt.keyframes
            ],
            "error": attempt.error,
            "warnings": list(attempt.warnings),
        })
    return {
        "id": project.project_id,
        "dance_reference": asdict(project.dance_reference) if project.dance_reference else None,
        "project_id": project.project_id,
        "source_session_id": project.source_session_id,
        "source_prompt_revision_id": project.source_prompt_revision_id,
        "prompt_language": (
            "zh" if project.source_prompt_revision_id.startswith("zh:") else "en"
        ),
        "model_id": project.model_id,
        "revision_model_id": project.revision_model_id,
        "input_mode": project.input_mode.value,
        "preparation": project.preparation.as_dict(),
        "cinematic_settings": project.cinematic_settings.as_dict() if project.cinematic_settings else None,
        "sensual_settings": project.sensual_settings.as_dict() if project.sensual_settings else None,
        "combat_settings": project.combat_settings.as_dict() if project.combat_settings else None,
        "combat_shot_count": len(project.planned_cut_times_ms) + 1 if project.combat_settings else None,
        "revision_versions": [
            {"version": version.value, "label": (
                "Classique Mise en scène 1.0 · expérimental" if project.preparation.is_classic_cinematic else
                "Sensuel 1.0 · explicite maximal" if project.preparation.is_sensual else
                f"Combat {version.value} · chorégraphie, dialogues et caméra")}
            for version in H3RenderService.revision_versions_for_mode(project.input_mode, project.preparation)
        ] if project.preparation.is_combat or project.preparation.is_classic_cinematic or project.preparation.is_sensual else None,
        "dialogue_level": project.dialogue_level,
        "adaptation": adaptation,
        "current_prompt": project.current_prompt,
        "revision_version": (
            project.revision_version.value if project.revision_version else None
        ),
        "camera_clauses": list(project.camera_clauses),
        "revision_draft": project.revision_draft,
        "revision_error": project.revision_error,
        "revision_draft_version": (
            project.revision_draft_version.value
            if project.revision_draft_version else None
        ),
        "planned_cut_times_ms": list(project.planned_cut_times_ms),
        "first_frame": reference(
            project.first_frame_asset_id,
            project.first_frame_label,
            "first_frame",
        ),
        "last_frame": reference(
            project.last_frame_asset_id,
            project.last_frame_label,
            "last_frame",
        ),
        "references": [
            reference(asset_id, label, "reference")
            for asset_id, label in zip(
                project.reference_asset_ids,
                project.reference_labels,
                strict=True,
            )
        ],
        "turns": [
            {
                "id": turn.turn_id,
                "turn_id": turn.turn_id,
                "role": turn.role.value,
                "content": turn.content,
                "prompt": turn.prompt,
                "questions": list(turn.questions),
                "recommendations": list(turn.recommendations),
                "revision_version": (
                    turn.revision_version.value if turn.revision_version else None
                ),
                "model_id": turn.model_id,
            }
            for turn in project.turns
        ],
        "attempts": attempts,
        "feedback_attempt_id": project.feedback_attempt_id,
        "warnings": list(project.warnings),
    }


def _require_h3_render(value: H3RenderService | None) -> H3RenderService:
    if value is None:
        raise HTTPException(status_code=503, detail="H3 Base renderer is not configured")
    return value


def h3_render_router(*, h3_conversion, h3_lora_resources, h3_render: H3RenderService | None, machine_work, video_preview_connector: Callable[[str], Any] | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/h3-render/video-loras")
    def h3_render_video_loras(refresh: bool = False) -> dict:
        service = _require_h3_render(h3_render)
        models, warning = service.video_lora_inventory(refresh=refresh)
        return {"models": list(models), "warning": warning}

    def require_h3_lora_resources():
        if h3_lora_resources is None:
            raise HTTPException(503, "Les fiches LoRA vidéo sont indisponibles.")
        return h3_lora_resources

    @router.get("/api/h3-render/video-loras/resources")
    def h3_lora_resource(name: str) -> dict:
        with http_errors('LoRA vidéo absent de l’inventaire.', missing=(KeyError,), invalid=(ValueError,)):
            return serialize_krea2_resource(require_h3_lora_resources().get_by_name(name))

    @router.post("/api/h3-render/video-loras/resources/{resource_id}/preference")
    def update_h3_lora_resource(resource_id: str, body: Krea2ResourcePreferenceBody) -> dict:
        catalog = require_h3_lora_resources()
        annotations = {key: getattr(body, key) for key in ("display_name", "strength_min", "strength_max", "notes")
                       if key in body.model_fields_set}
        with http_errors('Fiche LoRA vidéo introuvable.', missing=(KeyError,)):
            if body.model_fields_set - {"favorite", *annotations}:
                raise ValueError("Annotation LoRA vidéo non prise en charge.")
            resource = catalog.set_annotations(resource_id, annotations) if annotations else catalog.get(resource_id)
            if body.favorite is not None:
                resource = catalog.set_preference(resource_id, favorite=body.favorite)
            return serialize_krea2_resource(resource)

    @router.post("/api/h3-render/video-loras/resources/{resource_id}/refresh")
    def refresh_h3_lora_resource(resource_id: str) -> dict:
        with http_errors('Fiche LoRA vidéo introuvable.', missing=(KeyError,), invalid=(ValueError,)):
            return serialize_krea2_resource(require_h3_lora_resources().refresh_remote(resource_id))

    @router.get("/api/h3-render/checkpoints")
    def h3_render_checkpoints(mode: str = "h3-base", refresh: bool = False) -> dict:
        service = _require_h3_render(h3_render)
        if mode not in {"h3-base", "ref2va"}:
            raise HTTPException(422, "Mode vidéo inconnu.")
        if service.checkpoints is None:
            return {"models": [], "warning": "Le catalogue des checkpoints est indisponible."}
        input_mode = H3RenderInputMode.REF2VA if mode == "ref2va" else H3RenderInputMode.T2VA
        return service.checkpoints.inventory(input_mode, refresh=refresh)

    @router.get("/api/h3-render/spec")
    def h3_render_spec(mode: str = "h3-base", recipe_id: str | None = None,
                       recipe_version: str | None = None, purpose: str = "") -> dict[str, object]:
        service = _require_h3_render(h3_render)
        input_mode = (
            H3RenderInputMode.REF2VA
            if mode == "ref2va"
            else H3RenderInputMode.T2VA
        )
        try:
            if purpose == "dance" and recipe_id is None:
                available = getattr(service, "reference_video_workflows", ())
                if not available:
                    raise ValueError("Les recettes Danse sont indisponibles.")
                recipe_id, recipe_version = available[0].reference.recipe_id, available[0].reference.version
            recipe = service.workflow_for_mode(input_mode, recipe_id, recipe_version)
            if (purpose == "dance") != bool(getattr(recipe, "supports_reference_video", False)):
                raise ValueError("Cette recette n’est pas disponible dans cet atelier.")
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        presets = [
            {
                "id": preset.preset_id,
                "label": preset.label,
                "aspect_ratio": preset.aspect_ratio.value,
                "megapixels": preset.megapixels,
                "duration_seconds": preset.duration_seconds,
                "steps": preset.steps,
            }
            for preset in recipe.presets.values()
        ]
        limits = {
            "megapixels": {"minimum": 0.1, "maximum": 16.0, "step": 0.1},
            "duration_seconds": {"minimum": 5.0, "maximum": 15.0},
            "steps": {"minimum": 1, "maximum": 100},
            "keyframes": {"maximum": recipe.maximum_keyframes},
        }
        if getattr(recipe, "supports_initial_megapixels", False):
            limits["initial_megapixels"] = {"minimum": 0.1, "maximum": 16.0, "step": 0.1}
            for item, preset in zip(presets, recipe.presets.values()):
                item["initial_megapixels"] = preset.initial_megapixels
        for item in presets:
            item["seed_locked"] = True
        if hasattr(recipe, "maximum_reference_images"):
            limits["reference_images"] = {
                "minimum": recipe.minimum_reference_images,
                "maximum": recipe.maximum_reference_images,
            }
        video_lora_models: tuple[str, ...] = ()
        video_lora_warning: str | None = None
        video_lora_supported = recipe.supports_video_lora
        if video_lora_supported:
            video_lora_models, video_lora_warning = service.video_lora_inventory()
        return {
            "operation_id": recipe.reference.operation_id,
            "render_recipes": [
                {"id": value.reference.recipe_id, "version": value.reference.version,
                 "label": ("BUNNY · expérimental" if getattr(value, "supports_video_lora_stack", False) else "BUNNY · historique") if value.reference.recipe_id == BUNNY_RECIPE_ID
                    else "Rendu actuel" if value.reference == service.workflow_for_mode(input_mode).reference
                    else "REF2V" if getattr(value, "supports_reference_video", False) else "Historique"}
                for value in service.recipes_for_mode(input_mode)
                if bool(getattr(value, "supports_reference_video", False)) == (purpose == "dance")
            ],
            "video_lora_stack": recipe.video_lora_stack_spec() if getattr(recipe, "supports_video_lora_stack", False) else {"supported": False},
            "checkpoint_selection": recipe.checkpoint_spec(input_mode) if getattr(recipe, "supports_checkpoint_selection", False) else {"supported": False},
            "bunny": recipe.controls_spec(input_mode) if recipe.reference.recipe_id == BUNNY_RECIPE_ID else None,
            "llm_models": [
                _serialize_llm_model(model) for model in service.list_models()
            ],
            "recipe": {
                "id": recipe.reference.recipe_id,
                "version": recipe.reference.version,
                "workflow_sha256": recipe.reference.workflow_sha256,
                "status": recipe.status,
            },
            "supports_upscale_bypass": getattr(recipe, "supports_upscale_bypass", False),
            "presets": presets,
            "defaults": presets[0],
            "aspect_ratios": [ratio.value for ratio in VideoAspectRatio],
            "megapixels": [0.3, 0.6, 1.0, 1.2],
            "fps": 24,
            "limits": limits,
            "revision_versions": [
                {
                    "version": version.value,
                    "label": (
                        "0.3.0 · dialogues et caméra compilée"
                        if version.value == "0.3.0" else "Stable 0.2.0 · caméra compilée"
                        if version.value == "0.2.0"
                        else "Legacy 0.1.0"
                    ),
                }
                for version in service.revision_versions_for_mode(input_mode)
            ],
            "default_revision_version": service.default_revision_version(
                input_mode
            ).value,
            "video_lora": {
                "supported": video_lora_supported,
                "overlay_version": "0.1.0",
                "models": list(video_lora_models),
                "warning": video_lora_warning,
                "defaults": {"strength": 0.5, "clip_last_layer": -2},
                "limits": {
                    "strength": {"minimum": 0, "maximum": 1, "step": 0.05}
                },
            },
        }

    @router.post(
        "/api/h3-render/projects/from-session/{session_id}",
        status_code=status.HTTP_201_CREATED,
    )
    def create_h3_render_project(
        session_id: str,
        prompt_language: str = "en",
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 prompt session not found'):
            return {"project": serialize_h3_render_project(
                service.get_or_create_from_session(
                    session_id,
                    prompt_language=prompt_language,
                )
            )}

    @router.get("/api/h3-render/projects/{project_id}")
    def get_h3_render_project(project_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project not found'):
            return {"project": serialize_h3_render_project(service.get(project_id))}

    @router.get("/api/h3-render/adaptations")
    def list_h3_adaptations() -> dict[str, object]:
        service = _require_h3_render(h3_render)
        return {"projects": [serialize_h3_render_project(p) for p in service.projects.list(200)
                             if p.adaptation is not None][:30]}

    @router.post("/api/h3-render/projects/{project_id}/adaptation-reference")
    async def upload_h3_adaptation_reference(project_id: str, image: Annotated[UploadFile, File()]) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('Atelier introuvable.'):
            service.projects.get(project_id)
            content = await image.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("Image trop volumineuse : 25 Mio maximum.")
            media_type = detect_image_media_type(content)
            asset = service.assets.create(content, media_type=media_type, source_run_id=project_id)
            return {"asset_id": asset.asset_id, "label": image.filename or "Référence ajoutée"}

    @router.post("/api/h3-render/projects/{project_id}/adapt-ref2v", status_code=201)
    def prepare_h3_adaptation(project_id: str, body: H3Ref2VConversionBody) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('Atelier ou référence introuvable.'):
            source = service.projects.get(project_id)
            selected = service.workflow_for_mode(source.input_mode, body.recipe_id, body.recipe_version)
            bunny = H3BunnySettings(**body.bunny.model_dump()) if body.bunny else None
            if selected.reference.recipe_id == BUNNY_RECIPE_ID:
                destination = service.workflow_for_mode(H3RenderInputMode.REF2VA, BUNNY_RECIPE_ID, selected.reference.version)
                bunny = bunny or H3BunnySettings()
            else:
                if bunny is not None:
                    raise ValueError("Les paramètres BUNNY ne correspondent pas à la recette choisie.")
                destination = service.workflow_for_mode(H3RenderInputMode.REF2VA)
            seed = _parse_json_seed(body.seed)
            if seed is None:
                seed = int(hashlib.sha256(body.request_id.encode()).hexdigest()[:16], 16)
            setup = H3RenderSetup(
                settings=VideoLabSettings(VideoAspectRatio(body.aspect_ratio), body.megapixels, body.duration_seconds,
                    bunny.coarse_steps + bunny.refine_steps if bunny else body.steps, seed, body.seed_locked),
                initial_megapixels=body.initial_megapixels if getattr(destination, "supports_initial_megapixels", False) else 0.2,
                music_enabled=body.music_enabled, spectrum_enabled=body.spectrum_enabled,
                video_lora=H3VideoLoraSelection(**body.video_lora.model_dump()) if body.video_lora else None,
                recipe=destination.reference, bunny=bunny, checkpoint=body.checkpoint,
                force_upscale=body.force_upscale,
                video_loras=H3VideoLoraStack.from_dict(body.video_loras.model_dump()) if body.video_loras else None,
                model_loading=service.resolve_model_loading(destination, H3RenderInputMode.REF2VA, body.checkpoint)
                    if body.checkpoint is not None or getattr(destination, "supports_checkpoint_selection", False) else None)
            assert h3_conversion is not None
            project = h3_conversion.prepare(project_id, request_id=body.request_id, prompt=body.prompt,
                model_id=body.model_id, setup=setup,
                extra_reference=(body.extra_reference_asset_id, body.extra_reference_label) if body.extra_reference_asset_id else None)
            warnings = []
            if setup.initial_megapixels != body.initial_megapixels:
                warnings.append("La recette REF2V actuelle fixe la première passe à 0,2 MP ; les autres réglages sont repris.")
            return {"project": serialize_h3_render_project(project), "warnings": warnings}

    @router.post("/api/h3-render/projects/{project_id}/adapt-ref2v/stream")
    def stream_h3_adaptation(project_id: str, include_reasoning: bool = False) -> StreamingResponse:
        _require_h3_render(h3_render)
        assert h3_conversion is not None
        return stream_response(h3_conversion.stream(project_id, include_reasoning=include_reasoning), serialize=serialize_h3_render_project)

    @router.post("/api/h3-render/projects/{project_id}/chat/stream")
    def stream_h3_render_chat(
        project_id: str,
        body: H3RenderChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_h3_render(h3_render)
        return stream_response(service.stream_chat(project_id, body.message, model_id=body.model_id, feedback_attempt_id=body.feedback_attempt_id, revision_version=body.revision_version, creative_audacity=None if body.revision_audacity == 0 else body.revision_audacity, include_reasoning=include_reasoning, repair_rejected=body.repair_rejected, dialogue_level=body.dialogue_level), serialize=serialize_h3_render_project)

    @router.post(
        "/api/h3-render/projects/{project_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_h3_render_attempt(
        project_id: str,
        body: H3RenderAttemptBody,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project not found'):
            seed = _parse_json_seed(body.seed)
            video_lora = (
                H3VideoLoraSelection(
                    name=body.video_lora.name,
                    strength=body.video_lora.strength,
                    clip_last_layer=body.video_lora.clip_last_layer,
                )
                if body.video_lora is not None
                else None
            )
            project = service.prepare_attempt(
                project_id,
                prompt=body.prompt,
                settings=VideoLabSettings(
                    aspect_ratio=VideoAspectRatio(body.aspect_ratio),
                    megapixels=body.megapixels,
                    duration_seconds=body.duration_seconds,
                    steps=body.steps,
                    seed=service.new_seed() if seed is None else seed,
                    seed_locked=body.seed_locked,
                ),
                music_enabled=body.music_enabled,
                spectrum_enabled=body.spectrum_enabled,
                initial_megapixels=body.initial_megapixels,
                force_upscale=body.force_upscale,
                recipe_id=body.recipe_id,
                recipe_version=body.recipe_version,
                **({"dance_stage": body.dance_stage} if body.dance_stage != "full" else {}),
                bunny=H3BunnySettings(**body.bunny.model_dump()) if body.bunny else None,
                **({"checkpoint": body.checkpoint} if body.checkpoint is not None else {}),
                **({"video_loras": H3VideoLoraStack.from_dict(body.video_loras.model_dump())} if body.video_loras is not None else {}),
                **(
                    {"video_lora": video_lora}
                    if video_lora is not None
                    else {}
                ),
            )
            return {"project": serialize_h3_render_project(project)}

    @router.post(
        "/api/h3-render/projects/{project_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_h3_render_attempt(
        project_id: str,
        attempt_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project or attempt not found'):
            project = service.queue_attempt(project_id, attempt_id)
        background_tasks.add_task(service.execute_attempt, project_id, attempt_id)
        return {"project": serialize_h3_render_project(project)}

    @router.post("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/cancel")
    def cancel_h3_render_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project or attempt not found', invalid=(OSError, RuntimeError, TypeError, ValueError)):
            return {"project": serialize_h3_render_project(service.cancel_attempt(project_id, attempt_id))}

    @router.post("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/resume")
    def resume_h3_render_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project or attempt not found'):
            return {"project": serialize_h3_render_project(service.resume_attempt(project_id, attempt_id))}

    @router.post("/api/h3-render/projects/{project_id}/feedback")
    def select_h3_render_feedback(
        project_id: str,
        body: H3RenderFeedbackBody,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        with http_errors('H3 render project or attempt not found'):
            return {"project": serialize_h3_render_project(service.select_feedback(project_id, body.attempt_id))}

    @router.websocket("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/events")
    async def h3_render_events(websocket: WebSocket, project_id: str, attempt_id: str) -> None:
        if h3_render is None:
            await websocket.close(code=4403, reason="H3 renderer is not configured")
            return
        try:
            project = h3_render.get(project_id)
            attempt = project.attempt(attempt_id)
        except (KeyError, FileNotFoundError, ValueError):
            await websocket.close(code=4404, reason="H3 render attempt not found")
            return
        upstream_url = getattr(h3_render.comfy, "websocket_url", None)
        if not isinstance(upstream_url, str) or not upstream_url.strip():
            await websocket.close(code=1011, reason="Preview relay is not configured")
            return
        await websocket.accept()
        connector = video_preview_connector or _connect_video_preview
        try:
            async with connector(upstream_url) as upstream:
                await websocket.send_json({
                    "type": "panelforge_preview_status",
                    "data": {"status": "connected", "attempt_id": attempt_id},
                })
                await _relay_video_preview(
                    websocket,
                    upstream,
                    progress_profile=h3_render.progress_for_attempt(project, attempt),
                    execution_id=lambda: h3_render.get(project_id)
                    .attempt(attempt_id)
                    .execution_id,
                    configured_steps=(
                        None if attempt.spectrum_enabled else attempt.settings.steps
                    ),
                    progress_reporter=lambda event: _report_machine_render_progress(
                        machine_work,
                        f"h3:{project_id}:{attempt_id}",
                        event,
                    ),
                )
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await websocket.send_json({
                    "type": "panelforge_preview_status",
                    "data": {
                        "status": "error",
                        "attempt_id": attempt_id,
                        "message": "Preview live indisponible : connexion ComfyUI impossible.",
                    },
                })
                await websocket.close(code=1011, reason="Preview relay unavailable")
            except (RuntimeError, WebSocketDisconnect):
                pass

    return router
