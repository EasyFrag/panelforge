"""Thin FastAPI adapter for the first PanelForge Lab vertical slice."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Callable

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from panelforge.application import (
    ChangeViewRunRequest,
    ChangeViewRunner,
    CompositionStreamEvent,
    H3RenderService,
    H3RenderStreamEvent,
    Krea2AssistedService,
    Krea2AssistedStreamEvent,
    Krea2LabRunRequest,
    Krea2LabRunner,
    Krea2BatchRequest,
    Krea2BatchService,
    Krea2BatchStreamEvent,
    Krea2EditAttemptRequest,
    Krea2EditService,
    Krea2EditStreamEvent,
    ModelRuntimeControl,
    NewReference,
    PromptCompositionService,
    PromptLabService,
    PromptLabStreamEvent,
    SocialLabService,
    SocialLabStreamEvent,
    SUPER_FAST_REF2V_COOKBOOK_ID,
    SUPER_FAST_REF2V_COOKBOOK_VERSION,
    VideoLabRunRequest,
    VideoLabRunner,
    composition_picture_mapping,
    creative_axes_from_legacy,
    parse_krea2_assisted_recipe_draft,
)
from panelforge.domain import (
    CompositionStage,
    ControlKind,
    CookbookBinding,
    CreativeFreedomAxes,
    H3RenderInputMode,
    H3RenderProject,
    Krea2AssistedProject,
    Krea2AssistedTurnMode,
    Krea2AspectRatio,
    Krea2Batch,
    Krea2BatchSettings,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
    Krea2LoraSelection,
    Krea2PromptLanguage,
    Krea2ReviewDecision,
    Krea2LabRun,
    PromptComposition,
    PromptLabSession,
    ReferenceEvidencePolicy,
    ReferenceUse,
    RunRecord,
    RunReview,
    SocialChannelProfile,
    SocialLanguage,
    SocialProject,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabSettings,
    normalize_krea2_model_name,
)
from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)
from panelforge.infrastructure.comfy import ComfyBusyError
from panelforge.infrastructure.krea2_resources import (
    Krea2ResourcePrecision,
    Krea2ResourceSafety,
    serialize_krea2_resource,
)
from panelforge.infrastructure.krea2_image_metadata import recover_krea2_metadata


MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_SOCIAL_VIDEO_BYTES = 250 * 1024 * 1024
MAX_PROMPT_REFERENCES = 9
_STATIC_DIRECTORY = Path(__file__).with_name("static")

_AZIMUTH_LABELS = {
    CameraAzimuth.FRONT: "Face",
    CameraAzimuth.FRONT_RIGHT_QUARTER: "Trois-quarts droit",
    CameraAzimuth.RIGHT_SIDE: "Profil droit",
    CameraAzimuth.BACK_RIGHT_QUARTER: "Dos trois-quarts droit",
    CameraAzimuth.BACK: "Dos",
    CameraAzimuth.BACK_LEFT_QUARTER: "Dos trois-quarts gauche",
    CameraAzimuth.LEFT_SIDE: "Profil gauche",
    CameraAzimuth.FRONT_LEFT_QUARTER: "Trois-quarts gauche",
}
_ELEVATION_LABELS = {
    CameraElevation.LOW: "Contre-plongée",
    CameraElevation.EYE_LEVEL: "À hauteur des yeux",
    CameraElevation.ELEVATED: "Caméra surélevée",
    CameraElevation.HIGH: "Plongée",
}
_SHOT_SIZE_LABELS = {
    ShotSize.CLOSE_UP: "Gros plan",
    ShotSize.MEDIUM: "Plan moyen",
    ShotSize.WIDE: "Plan large",
}


class PreviewBody(BaseModel):
    azimuth: str
    elevation: str
    shot_size: str


class ReviewBody(BaseModel):
    decision: str


class PromptEditBody(BaseModel):
    content: str


class PromptRevisionBody(BaseModel):
    instruction: str


class CreativeAxesBody(BaseModel):
    scene_life: int = Field(ge=0, le=3)
    camera: int = Field(ge=0, le=3)
    extra_motion: int = Field(ge=0, le=3)

    def domain_value(self) -> CreativeFreedomAxes:
        return CreativeFreedomAxes(
            scene_life=self.scene_life,
            camera=self.camera,
            extra_motion=self.extra_motion,
        )


class BriefStructureBody(BaseModel):
    source_text: str
    creative_freedom: int = Field(default=35, ge=0, le=100)
    creative_axes: CreativeAxesBody | None = None


class PromptSessionForkBody(BaseModel):
    model_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None


class CompositionConfigureBody(BaseModel):
    cookbook_id: str
    cookbook_version: str
    bindings: dict[str, list[str]]


class PlanArbitrationBody(BaseModel):
    decisions: dict[str, str]
    instruction: str | None = None


class SuperFastRef2VBody(BaseModel):
    source_text: str
    creative_freedom: int = Field(default=35, ge=0, le=100)
    creative_axes: CreativeAxesBody | None = None


class Krea2CreateBody(BaseModel):
    prompt: str
    preset_id: str = "krea2-base"
    model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    seed: str | int | None = None
    seed_locked: bool = False


class Krea2BatchLoraBody(BaseModel):
    name: str
    strength: float


class Krea2BatchCreateBody(BaseModel):
    recipe_id: str
    recipe_version: str
    image_count: int
    model_id: str
    direction: str = ""
    render_model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    loras: list[Krea2BatchLoraBody] | None = None


class Krea2ResourcePreferenceBody(BaseModel):
    favorite: bool | None = None
    safety: str | None = None
    precision: str | None = None


class Krea2BatchReviewBody(BaseModel):
    decision: str
    comment: str = ""


class Krea2BatchRecipeRevisionBody(BaseModel):
    instruction: str
    draft: str | None = None
    model_id: str | None = None
    render_model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    loras: list[Krea2BatchLoraBody] | None = None
    prompt_language: str | None = None


class Krea2BatchRecipeDraftBody(BaseModel):
    draft: str
    render_model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    loras: list[Krea2BatchLoraBody] | None = None
    prompt_language: str | None = None


class Krea2BatchRecipeTestBody(Krea2BatchRecipeDraftBody):
    image_count: int = 3
    model_id: str
    direction: str = ""


class Krea2BatchRecipePublishBody(BaseModel):
    draft: str | None = None
    render_model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    loras: list[Krea2BatchLoraBody] | None = None
    prompt_language: str | None = None


class Krea2EditPromptBody(BaseModel):
    instruction: str
    model_id: str
    base_prompt: str | None = None
    feedback_attempt_id: str | None = None
    prompt_language: str | None = None


class Krea2EditAttemptBody(BaseModel):
    prompt: str
    model_id: str
    aspect_ratio: str
    megapixels: float
    seed: str | int
    ref_boost: float = 2.5
    steps: int = 10
    loras: list[Krea2BatchLoraBody] | None = None


class Krea2EditSourceStateBody(BaseModel):
    state: str


class Krea2EditPromotionBody(BaseModel):
    project_name: str | None = None
    step_name: str | None = None


class Krea2AssistedChatBody(BaseModel):
    message: str
    mode: str = "creation"
    feedback_attempt_id: str | None = None
    prompt_language: str | None = None
    guidance_asset_id: str | None = None
    guidance_filename: str | None = None


class Krea2AssistedAttemptBody(BaseModel):
    prompt: str
    model_id: str
    aspect_ratio: str
    megapixels: float
    seed: str | int | None = None
    loras: list[Krea2BatchLoraBody] | None = None


class Krea2AssistedFeedbackBody(BaseModel):
    attempt_id: str | None = None


class Krea2AssistedRecipeDraftBody(BaseModel):
    recipe_id: str
    display_name: str
    description: str
    identity: str
    invariants: list[str]
    variables: list[str]
    risks: list[str]
    canonical_prompt: str


class Krea2AssistedRecipePublishBody(BaseModel):
    draft: Krea2AssistedRecipeDraftBody | None = None


class H3RenderChatBody(BaseModel):
    message: str
    feedback_attempt_id: str | None = None
    revision_version: str | None = None


class H3RenderAttemptBody(BaseModel):
    prompt: str
    aspect_ratio: str
    megapixels: float
    duration_seconds: float
    steps: int
    seed: str | int | None = None
    seed_locked: bool = False
    music_enabled: bool = False


class H3RenderFeedbackBody(BaseModel):
    attempt_id: str | None = None


class SocialProfileBody(BaseModel):
    name: str
    language: str = "en"
    mood: str = ""
    vibe: str = ""
    example: str = ""
    instructions: str = ""


class SocialChatBody(BaseModel):
    message: str
    model_id: str | None = None
    language: str | None = None
    variant_count: int | None = Field(default=None, ge=1, le=8)
    mood: str | None = None
    vibe: str | None = None
    example: str | None = None
    instructions: str | None = None
    channel_profile_id: str | None = None
    update_profile: bool = False


def create_app(
    runner: ChangeViewRunner,
    *,
    prompt_lab: PromptLabService | None = None,
    prompt_composition: PromptCompositionService | None = None,
    video_lab: VideoLabRunner | None = None,
    h3_render: H3RenderService | None = None,
    krea2_lab: Krea2LabRunner | None = None,
    krea2_batch: Krea2BatchService | None = None,
    krea2_edit: Krea2EditService | None = None,
    krea2_assisted: Krea2AssistedService | None = None,
    social_lab: SocialLabService | None = None,
    model_runtime: ModelRuntimeControl | None = None,
    comfy_runtime: Any | None = None,
    local_gpu_monitor: Any | None = None,
    static_directory: Path | None = None,
    video_preview_connector: Callable[[str], Any] | None = None,
    runtime_monitor_connector: Callable[[str], Any] | None = None,
) -> FastAPI:
    """Create an app around injected application services."""
    static_root = (static_directory or _STATIC_DIRECTORY).resolve()
    index_path = static_root / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(index_path)

    app = FastAPI(title="PanelForge Lab", version="0.1.0")
    krea2_models = (
        _Krea2ModelDiscovery(krea2_lab)
        if krea2_lab is not None
        else None
    )

    @app.middleware("http")
    async def disable_lab_asset_cache(request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", StaticFiles(directory=static_root), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})

    @app.post("/api/model-runtime/unload")
    def unload_model_runtime() -> dict[str, str]:
        if model_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="Le contrôle du serveur LLM n’est pas configuré.",
            )
        try:
            model_runtime.unload_all()
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail=f"Impossible de décharger les modèles LLM : {error}",
            ) from error
        return {
            "status": "unloaded",
            "message": "Modèles LLM déchargés.",
        }

    @app.get("/api/runtime/status")
    def runtime_status() -> dict[str, object]:
        """Return partial runtime data even when one service is offline."""
        return _runtime_status(
            model_runtime=model_runtime,
            comfy_runtime=comfy_runtime,
            local_gpu_monitor=local_gpu_monitor,
        )

    @app.post("/api/comfy-runtime/free")
    def free_comfy_runtime() -> dict[str, str]:
        if comfy_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="Le contrôle ComfyUI n’est pas configuré.",
            )
        try:
            comfy_runtime.free_vram()
        except ComfyBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail="Impossible de joindre ComfyUI pour libérer sa VRAM.",
            ) from error
        return {
            "status": "unloaded",
            "message": "Modèles et caches ComfyUI déchargés.",
        }

    @app.websocket("/api/runtime/events")
    async def runtime_events(websocket: WebSocket) -> None:
        await websocket.accept()
        upstream_url = getattr(comfy_runtime, "websocket_url", None)
        if not isinstance(upstream_url, str) or not upstream_url.strip():
            await websocket.send_json(
                {
                    "type": "panelforge_runtime_status",
                    "data": {"status": "unavailable"},
                }
            )
            await websocket.close(code=1000)
            return
        connector = runtime_monitor_connector or _connect_video_preview
        try:
            async with connector(upstream_url) as upstream:
                await websocket.send_json(
                    {
                        "type": "panelforge_runtime_status",
                        "data": {"status": "connected"},
                    }
                )
                await _relay_runtime_monitor(websocket, upstream)
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await websocket.send_json(
                    {
                        "type": "panelforge_runtime_status",
                        "data": {"status": "unavailable"},
                    }
                )
                await websocket.close(code=1011, reason="Runtime monitor unavailable")
            except (RuntimeError, WebSocketDisconnect):
                pass

    @app.get("/api/change-view/spec")
    def change_view_spec() -> dict[str, object]:
        policy = runner.recipe.variation_policy
        controls: dict[str, object] = {}
        for control in policy.controls:
            serialized = {
                "id": control.control_id,
                "label": control.label,
                "kind": control.kind.value,
                "method": control.method.value,
                "default": (
                    str(control.default)
                    if control.control_id == "seed"
                    else control.default
                ),
                "advanced": control.advanced,
            }
            if control.kind is ControlKind.CHOICE:
                serialized["options"] = _choice_options(control.control_id)
            else:
                serialized.update(
                    {
                        "minimum": (
                            str(control.minimum)
                            if control.control_id == "seed"
                            else control.minimum
                        ),
                        "maximum": (
                            str(control.maximum)
                            if control.control_id == "seed"
                            else control.maximum
                        ),
                        "step": control.step,
                    }
                )
            controls[control.control_id] = serialized

        default_prompt = runner.recipe.render_prompt(
            ChangeView(
                source_asset_id="preview",
                azimuth=CameraAzimuth.FRONT,
                elevation=CameraElevation.EYE_LEVEL,
                shot_size=ShotSize.MEDIUM,
            )
        )
        lora_control = controls["multiple_angles_lora_strength"]
        controls["lora_strength"] = lora_control
        return {
            "operation_id": runner.recipe.reference.operation_id,
            "recipe": {
                "id": runner.recipe.reference.recipe_id,
                "version": runner.recipe.reference.version,
                "workflow_sha256": runner.recipe.reference.workflow_sha256,
                "status": "experimental",
            },
            "prompt_policy": runner.recipe.prompt_policy.value,
            "variation_method_order": [
                method.value for method in policy.method_order
            ],
            "controls": controls,
            "compiled_prompt": default_prompt,
        }

    @app.post("/api/change-view/preview")
    def preview_prompt(body: PreviewBody) -> dict[str, str]:
        try:
            change = ChangeView(
                source_asset_id="preview",
                azimuth=CameraAzimuth(body.azimuth),
                elevation=CameraElevation(body.elevation),
                shot_size=ShotSize(body.shot_size),
            )
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "compiled_prompt": runner.recipe.render_prompt(change),
            "prompt_policy": runner.recipe.prompt_policy.value,
        }

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
    async def create_run(
        background_tasks: BackgroundTasks,
        source_image: Annotated[UploadFile | None, File()] = None,
        source_asset_id: Annotated[str | None, Form()] = None,
        azimuth: Annotated[str, Form()] = CameraAzimuth.FRONT.value,
        elevation: Annotated[str, Form()] = CameraElevation.EYE_LEVEL.value,
        shot_size: Annotated[str, Form()] = ShotSize.MEDIUM.value,
        lora_strength: Annotated[str, Form()] = "1.0",
        seed: Annotated[str, Form()] = "151020854543467",
    ) -> dict[str, object]:
        if (source_image is None) == (source_asset_id is None):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one source_image or source_asset_id",
            )
        try:
            parsed_azimuth = CameraAzimuth(azimuth)
            parsed_elevation = CameraElevation(elevation)
            parsed_shot_size = ShotSize(shot_size)
            parsed_lora_strength = float(lora_strength)
            parsed_seed = _parse_seed(seed)
            runner.recipe.is_experimental_lora_override(parsed_lora_strength)

            if source_image is not None:
                content = await source_image.read(MAX_IMAGE_BYTES + 1)
                await source_image.close()
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("source image exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                source = runner.assets.create(content, media_type=media_type)
                resolved_asset_id = source.asset_id
            else:
                assert source_asset_id is not None
                source = runner.assets.get(source_asset_id)
                resolved_asset_id = source.asset_id

            request = ChangeViewRunRequest(
                source_asset_id=resolved_asset_id,
                azimuth=parsed_azimuth,
                elevation=parsed_elevation,
                shot_size=parsed_shot_size,
                lora_strength=parsed_lora_strength,
                seed=parsed_seed,
            )
            run = runner.prepare(request)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="source asset not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        background_tasks.add_task(runner.execute, run.run_id)
        return serialize_run(run)

    @app.get("/api/runs")
    def list_runs(limit: int = 20) -> dict[str, object]:
        try:
            records = runner.runs.list(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"runs": [serialize_run(run) for run in records]}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        return serialize_run(_get_run_or_404(runner, run_id))

    @app.post("/api/runs/{run_id}/review")
    def review_run(run_id: str, body: ReviewBody) -> dict[str, object]:
        try:
            decision = RunReview(body.decision)
            if decision is RunReview.PENDING:
                raise ValueError("decision must be kept or rejected")
            return serialize_run(runner.review(run_id, decision))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/reuse")
    def reuse_run(run_id: str) -> dict[str, str]:
        try:
            asset = runner.reusable_asset(run_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "source_asset_id": asset.asset_id,
            "content_url": f"/api/assets/{asset.asset_id}/content",
        }

    @app.get("/api/assets/{asset_id}/content")
    def asset_content(asset_id: str, request: Request) -> Response:
        try:
            asset = runner.assets.get(asset_id)
            content = runner.assets.read_bytes(asset_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="asset not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=31536000, immutable",
        }
        try:
            byte_range = _parse_byte_range(
                request.headers.get("range"),
                len(content),
            )
        except ValueError:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={
                    **headers,
                    "Content-Range": f"bytes */{len(content)}",
                },
            )
        if byte_range is not None:
            start, end = byte_range
            return Response(
                content=content[start : end + 1],
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=asset.media_type,
                headers={
                    **headers,
                    "Content-Range": f"bytes {start}-{end}/{len(content)}",
                },
            )
        return Response(
            content=content,
            media_type=asset.media_type,
            headers=headers,
        )

    @app.get("/api/social-lab/spec")
    def social_lab_spec() -> dict[str, object]:
        service = _require_social_lab(social_lab)
        return {
            "llm_models": [
                _serialize_llm_model(model) for model in service.list_models()
            ],
            "languages": [
                {"id": SocialLanguage.ENGLISH.value, "label": "English"},
                {"id": SocialLanguage.FRENCH.value, "label": "Français"},
            ],
            "defaults": {
                "language": SocialLanguage.ENGLISH.value,
                "variant_count": 3,
                "keyframe_positions": [10, 35, 65, 90],
            },
            "limits": {
                "video_bytes": MAX_SOCIAL_VIDEO_BYTES,
                "keyframe_bytes": MAX_IMAGE_BYTES,
                "variant_count": {"minimum": 1, "maximum": 8},
            },
        }

    @app.get("/api/social-lab/profiles")
    def list_social_profiles(limit: int = 100) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "profiles": [
                    serialize_social_profile(profile)
                    for profile in service.list_profiles(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/social-lab/profiles",
        status_code=status.HTTP_201_CREATED,
    )
    def create_social_profile(body: SocialProfileBody) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "profile": serialize_social_profile(service.save_profile(
                    profile_id=None,
                    name=body.name,
                    language=SocialLanguage(body.language),
                    mood=body.mood,
                    vibe=body.vibe,
                    example=body.example,
                    instructions=body.instructions,
                ))
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.put("/api/social-lab/profiles/{profile_id}")
    def update_social_profile(
        profile_id: str,
        body: SocialProfileBody,
    ) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            service.get_profile(profile_id)
            return {
                "profile": serialize_social_profile(service.save_profile(
                    profile_id=profile_id,
                    name=body.name,
                    language=SocialLanguage(body.language),
                    mood=body.mood,
                    vibe=body.vibe,
                    example=body.example,
                    instructions=body.instructions,
                ))
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="channel profile not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/social-lab/projects",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_social_project(
        name: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        language: Annotated[str, Form()],
        variant_count: Annotated[int, Form()],
        video: Annotated[UploadFile, File()],
        keyframes: Annotated[list[UploadFile], File()],
        mood: Annotated[str, Form()] = "",
        vibe: Annotated[str, Form()] = "",
        example: Annotated[str, Form()] = "",
        instructions: Annotated[str, Form()] = "",
        channel_profile_id: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            video_content = await video.read(MAX_SOCIAL_VIDEO_BYTES + 1)
            if len(video_content) > MAX_SOCIAL_VIDEO_BYTES:
                raise ValueError("video exceeds the 250 MiB Social Lab limit")
            video_media_type = detect_video_media_type(video_content)
            if len(keyframes) != 4:
                raise ValueError("provide exactly four video keyframes")
            frame_values: list[tuple[bytes, str]] = []
            for keyframe in keyframes:
                content = await keyframe.read(MAX_IMAGE_BYTES + 1)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("a Social Lab keyframe exceeds 25 MiB")
                frame_values.append((content, detect_image_media_type(content)))
            video_asset = service.assets.create(
                video_content,
                media_type=video_media_type,
            )
            frame_assets = tuple(
                service.assets.create(content, media_type=media_type).asset_id
                for content, media_type in frame_values
            )
            project = service.create_project(
                name=name,
                model_id=model_id,
                language=SocialLanguage(language),
                variant_count=variant_count,
                video_asset_id=video_asset.asset_id,
                video_filename=video.filename or "video",
                keyframe_asset_ids=frame_assets,
                mood=mood,
                vibe=vibe,
                example=example,
                instructions=instructions,
                channel_profile_id=channel_profile_id or None,
            )
            return {"project": serialize_social_project(project)}
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await video.close()
            await _close_uploads(keyframes)

    @app.get("/api/social-lab/projects")
    def list_social_projects(limit: int = 30) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "projects": [
                    serialize_social_project(project)
                    for project in service.list_projects(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/social-lab/projects/{project_id}")
    def get_social_project(project_id: str) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "project": serialize_social_project(
                    service.get_project(project_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Social Lab project not found") from error

    @app.post("/api/social-lab/projects/{project_id}/chat/stream")
    def stream_social_chat(
        project_id: str,
        body: SocialChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_social_lab(social_lab)
        try:
            language = (
                SocialLanguage(body.language)
                if body.language is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _social_lab_stream_response(service.stream_chat(
            project_id,
            body.message,
            model_id=body.model_id,
            language=language,
            variant_count=body.variant_count,
            mood=body.mood,
            vibe=body.vibe,
            example=body.example,
            instructions=body.instructions,
            channel_profile_id=body.channel_profile_id,
            update_profile=body.update_profile,
            include_reasoning=include_reasoning,
        ))

    @app.get("/api/image-lab/krea2/spec")
    def krea2_lab_spec() -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        discovery = _require_krea2_discovery(krea2_models)
        presets = [
            {
                "id": preset.preset_id,
                "preset_id": preset.preset_id,
                "label": preset.label,
                "model_id": preset.model_name,
                "aspect_ratio": preset.aspect_ratio.value,
                "megapixels": preset.megapixels,
            }
            for preset in service.recipe.presets.values()
        ]
        default_preset = service.recipe.presets.get("krea2-base")
        if default_preset is None:
            raise HTTPException(
                status_code=503,
                detail="The current KREA2 base preset is not installed",
            )
        model_snapshot = discovery.snapshot()
        default_model = next(
            (
                str(model["id"])
                for model in model_snapshot["models"]
                if isinstance(model, dict) and model.get("default") is True
            ),
            service.recipe.default_model,
        )
        return {
            "operation_id": service.recipe.reference.operation_id,
            "recipe": {
                "id": service.recipe.reference.recipe_id,
                "version": service.recipe.reference.version,
                "workflow_sha256": service.recipe.reference.workflow_sha256,
                "status": service.recipe.status,
            },
            "presets": presets,
            "defaults": {
                "preset_id": default_preset.preset_id,
                "model_id": default_model,
                "aspect_ratio": default_preset.aspect_ratio.value,
                "megapixels": default_preset.megapixels,
            },
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "megapixels": [0.5, 1.0, 2.0, 3.0, 4.0],
            "limits": {
                "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
            },
            **model_snapshot,
        }

    @app.post("/api/image-lab/krea2/models/refresh")
    def refresh_krea2_models() -> dict[str, object]:
        _require_krea2_lab(krea2_lab)
        discovery = _require_krea2_discovery(krea2_models)
        return discovery.snapshot(refresh=True)

    @app.post(
        "/api/image-lab/krea2/runs",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_krea2_run(body: Krea2CreateBody) -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        discovery = _require_krea2_discovery(krea2_models)
        try:
            model_name = discovery.resolve(body.model_id)
            aspect_ratio = (
                Krea2AspectRatio(body.aspect_ratio)
                if body.aspect_ratio is not None
                else None
            )
            seed = _parse_json_seed(body.seed)
            run = service.prepare(
                Krea2LabRunRequest(
                    prompt=body.prompt,
                    preset_id=body.preset_id,
                    model_name=model_name,
                    aspect_ratio=aspect_ratio,
                    megapixels=body.megapixels,
                    seed=seed,
                    seed_locked=body.seed_locked,
                )
            )
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 resource not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return serialize_krea2_run(run)

    @app.post(
        "/api/image-lab/krea2/runs/{run_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_krea2_run(
        run_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        try:
            run = service.queue(run_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 run not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.execute, run.run_id)
        return serialize_krea2_run(run)

    @app.get("/api/image-lab/krea2/runs")
    def list_krea2_runs(limit: int = 30) -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        try:
            runs = service.list(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"runs": [serialize_krea2_run(run) for run in runs]}

    @app.get("/api/image-lab/krea2/runs/{run_id}")
    def get_krea2_run(run_id: str) -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        try:
            return serialize_krea2_run(service.get(run_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2/runs/{run_id}/cancel")
    def cancel_krea2_run(run_id: str) -> dict[str, object]:
        service = _require_krea2_lab(krea2_lab)
        try:
            return serialize_krea2_run(service.cancel(run_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 run not found") from error
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-batch/spec")
    def krea2_batch_spec() -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        models = service.resources.list_models()
        loras = service.resources.list_loras()
        return {
            "recipes": [serialize_krea2_visual_recipe(recipe) for recipe in service.recipes.current()],
            "llm_models": [_serialize_llm_model(model) for model in service.list_models()],
            "render_models": [serialize_krea2_resource(resource) for resource in models],
            "loras": [serialize_krea2_resource(resource) for resource in loras],
            "resource_warnings": list(
                getattr(service.resources, "inventory_warnings", lambda: ())()
            ),
            "limits": {"image_count": {"minimum": 1, "maximum": 10}, "lora_count": 4},
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
            "workflow": {
                "sampler": "er_sde",
                "scheduler": "simple",
                "first_pass": {"steps": 8, "cfg": 1.1, "denoise": 1.0},
                "latent_upscale": {"method": "bislerp", "scale_by": 1.5},
                "second_pass": {"steps": 2, "cfg": 1.0, "denoise": 0.3},
            },
        }

    @app.post("/api/image-lab/krea2-batch/resources/{resource_id}/preference")
    def update_krea2_resource_preference(
        resource_id: str,
        body: Krea2ResourcePreferenceBody,
    ) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            safety = Krea2ResourceSafety(body.safety) if body.safety is not None else None
            reset_precision = body.precision == "auto"
            precision = (
                None
                if body.precision is None or reset_precision
                else Krea2ResourcePrecision(body.precision)
            )
            resource = service.resources.set_preference(
                resource_id,
                favorite=body.favorite,
                safety=safety,
                precision=precision,
                reset_precision=reset_precision,
            )
            return serialize_krea2_resource(resource)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="KREA2 resource not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/resources/{resource_id}/refresh")
    def refresh_krea2_resource(resource_id: str) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            return serialize_krea2_resource(service.resources.refresh_remote(resource_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="KREA2 resource not found") from error

    @app.post("/api/image-lab/krea2-batch/batches", status_code=status.HTTP_201_CREATED)
    def create_krea2_batch(body: Krea2BatchCreateBody) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            recipe = service.recipes.get(body.recipe_id, body.recipe_version)
            settings = None
            if any(value is not None for value in (body.render_model_id, body.aspect_ratio, body.megapixels, body.loras)):
                settings = Krea2BatchSettings(
                    model_name=body.render_model_id or recipe.settings.model_name,
                    aspect_ratio=(Krea2AspectRatio(body.aspect_ratio) if body.aspect_ratio is not None else recipe.settings.aspect_ratio),
                    megapixels=body.megapixels if body.megapixels is not None else recipe.settings.megapixels,
                    loras=(
                        tuple(Krea2LoraSelection(name=item.name, strength=item.strength) for item in body.loras)
                        if body.loras is not None
                        else recipe.settings.loras
                    ),
                )
            batch = service.prepare(Krea2BatchRequest(
                recipe_id=body.recipe_id,
                recipe_version=body.recipe_version,
                image_count=body.image_count,
                model_id=body.model_id,
                direction=body.direction,
                settings=settings,
            ))
            return {"batch": serialize_krea2_batch(batch)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="KREA2 batch recipe not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/prompts/stream")
    def stream_krea2_batch_prompts(
        batch_id: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_krea2_batch(krea2_batch)
        return _krea2_batch_stream_response(service.stream_generate_prompts(batch_id, include_reasoning=include_reasoning))

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/start", status_code=status.HTTP_202_ACCEPTED)
    def start_krea2_batch(batch_id: str, background_tasks: BackgroundTasks) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            batch = service.start_rendering(batch_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.render, batch_id)
        return {"batch": serialize_krea2_batch(batch)}

    @app.get("/api/image-lab/krea2-batch/batches")
    def list_krea2_batches(limit: int = 20) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            return {"batches": [serialize_krea2_batch(batch) for batch in service.list(limit)]}
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-batch/batches/{batch_id}")
    def get_krea2_batch(batch_id: str) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            return {"batch": serialize_krea2_batch(service.get(batch_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/cancel")
    def cancel_krea2_batch(batch_id: str) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            return {"batch": serialize_krea2_batch(service.cancel(batch_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/items/{item_id}/review")
    def review_krea2_batch_item(batch_id: str, item_id: str, body: Krea2BatchReviewBody) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            batch = service.review_item(batch_id, item_id, Krea2ReviewDecision(body.decision), body.comment)
            return {"batch": serialize_krea2_batch(batch)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch or image not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision")
    def propose_krea2_recipe_revision(batch_id: str, body: Krea2BatchRecipeRevisionBody) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            settings = _krea2_revision_settings(body)
            return {"batch": serialize_krea2_batch(service.propose_recipe_revision(
                batch_id,
                body.instruction,
                draft=body.draft,
                settings=settings,
                model_id=body.model_id,
                prompt_language=_krea2_prompt_language(body.prompt_language),
            ))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision/draft")
    def save_krea2_recipe_revision_draft(batch_id: str, body: Krea2BatchRecipeDraftBody) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            batch = service.save_recipe_revision_draft(
                batch_id,
                body.draft,
                settings=_krea2_revision_settings(body),
                prompt_language=_krea2_prompt_language(body.prompt_language),
            )
            return {"batch": serialize_krea2_batch(batch)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision/test",
        status_code=status.HTTP_201_CREATED,
    )
    def test_krea2_recipe_revision(batch_id: str, body: Krea2BatchRecipeTestBody) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            batch, workshop = service.prepare_recipe_revision_test(
                batch_id,
                image_count=body.image_count,
                direction=body.direction,
                model_id=body.model_id,
                draft=body.draft,
                settings=_krea2_revision_settings(body),
                prompt_language=_krea2_prompt_language(body.prompt_language),
            )
            return {
                "batch": serialize_krea2_batch(batch),
                "workshop_batch": serialize_krea2_batch(workshop),
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision/accept")
    def accept_krea2_recipe_revision(
        batch_id: str,
        body: Krea2BatchRecipePublishBody | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_batch(krea2_batch)
        try:
            return {"recipe": serialize_krea2_visual_recipe(service.accept_recipe_revision(
                batch_id,
                draft=body.draft if body is not None else None,
                settings=_krea2_revision_settings(body) if body is not None else None,
                prompt_language=(
                    _krea2_prompt_language(body.prompt_language)
                    if body is not None
                    else None
                ),
            ))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 batch not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-assisted/spec")
    def krea2_assisted_spec() -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        models = service.resources.list_models()
        loras = service.resources.list_loras()
        return {
            "llm_models": [_serialize_llm_model(model) for model in service.list_models()],
            "render_models": [serialize_krea2_resource(resource) for resource in models],
            "loras": [serialize_krea2_resource(resource) for resource in loras],
            "resource_warnings": list(
                getattr(service.resources, "inventory_warnings", lambda: ())()
            ),
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "defaults": {
                "aspect_ratio": Krea2AspectRatio.PORTRAIT_WIDESCREEN.value,
                "megapixels": 2.1,
            },
            "limits": {
                "reference_bytes": MAX_IMAGE_BYTES,
                "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
                "lora_count": 4,
            },
            "workflow": {
                "recipe_id": getattr(service.workflow.reference, "recipe_id"),
                "version": getattr(service.workflow.reference, "version"),
                "sampler": "er_sde",
                "scheduler": "simple",
                "first_pass": {"steps": 8, "cfg": 1.1, "denoise": 1.0},
                "latent_upscale": {"method": "bislerp", "scale_by": 1.5},
                "second_pass": {"steps": 2, "cfg": 1.0, "denoise": 0.3},
            },
            "exports": {"enabled": service.export_root is not None, "root": service.export_root},
        }

    @app.post(
        "/api/image-lab/krea2-assisted/projects",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_krea2_assisted_project(
        name: Annotated[str, Form()],
        intention: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        reference: Annotated[UploadFile | None, File()] = None,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        asset_id = None
        try:
            if reference is not None:
                content = await reference.read(MAX_IMAGE_BYTES + 1)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("reference image exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                asset_id = runner.assets.create(content, media_type=media_type).asset_id
            project = service.create_project(
                name=name,
                intention=intention,
                model_id=model_id,
                reference_asset_id=asset_id,
                reference_filename=(reference.filename if reference is not None else None),
            )
            return {"project": serialize_krea2_assisted_project(project)}
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            if reference is not None:
                await reference.close()

    @app.get("/api/image-lab/krea2-assisted/projects")
    def list_krea2_assisted_projects(limit: int = 30) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "projects": [
                    serialize_krea2_assisted_project(project)
                    for project in service.list(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-assisted/projects/{project_id}")
    def get_krea2_assisted_project(project_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {"project": serialize_krea2_assisted_project(service.get(project_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project not found") from error

    @app.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/guidance-images",
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_krea2_assisted_guidance(
        project_id: str,
        image: Annotated[UploadFile, File()],
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            service.get(project_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="KREA2 assisted project not found",
            ) from error
        try:
            content = await image.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("guidance image exceeds the 25 MiB limit")
            media_type = detect_image_media_type(content)
            asset = runner.assets.create(
                content,
                media_type=media_type,
                source_run_id=project_id,
            )
            filename = image.filename or "guidance-image"
            return {
                "guidance": {
                    "asset_id": asset.asset_id,
                    "filename": filename,
                    "url": f"/api/assets/{asset.asset_id}/content",
                }
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await image.close()

    @app.post("/api/image-lab/krea2-assisted/projects/{project_id}/chat/stream")
    def stream_krea2_assisted_chat(
        project_id: str,
        body: Krea2AssistedChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            mode = Krea2AssistedTurnMode(body.mode)
            prompt_language = (
                Krea2PromptLanguage(body.prompt_language)
                if body.prompt_language is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _krea2_assisted_stream_response(service.stream_chat(
            project_id,
            body.message,
            mode=mode,
            feedback_attempt_id=body.feedback_attempt_id,
            prompt_language=prompt_language,
            guidance_asset_id=body.guidance_asset_id,
            guidance_filename=body.guidance_filename,
            include_reasoning=include_reasoning,
        ))

    @app.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_krea2_assisted_attempt(
        project_id: str,
        body: Krea2AssistedAttemptBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            seed = None if body.seed is None or str(body.seed).strip() == "" else _parse_json_seed(body.seed)
            project = service.prepare_attempt(
                project_id,
                prompt=body.prompt,
                settings=Krea2BatchSettings(
                    model_name=body.model_id,
                    aspect_ratio=Krea2AspectRatio(body.aspect_ratio),
                    megapixels=body.megapixels,
                    loras=tuple(
                        Krea2LoraSelection(name=value.name, strength=value.strength)
                        for value in (body.loras or [])
                    ),
                ),
                seed=seed,
            )
            return {"project": serialize_krea2_assisted_project(project)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_krea2_assisted_attempt(
        project_id: str,
        attempt_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            project = service.queue_attempt(project_id, attempt_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.execute_attempt, project_id, attempt_id)
        return {"project": serialize_krea2_assisted_project(project)}

    @app.post("/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/cancel")
    def cancel_krea2_assisted_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "project": serialize_krea2_assisted_project(
                    service.cancel_attempt(project_id, attempt_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-assisted/projects/{project_id}/feedback")
    def select_krea2_assisted_feedback(
        project_id: str,
        body: Krea2AssistedFeedbackBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "project": serialize_krea2_assisted_project(
                    service.select_feedback(project_id, body.attempt_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/save")
    def save_krea2_assisted_image(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "project": serialize_krea2_assisted_project(
                    service.save_image(project_id, attempt_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.put("/api/image-lab/krea2-assisted/projects/{project_id}/recipe-draft")
    def update_krea2_assisted_recipe_draft(
        project_id: str,
        body: Krea2AssistedRecipeDraftBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            draft = parse_krea2_assisted_recipe_draft(body.model_dump())
            return {
                "project": serialize_krea2_assisted_project(
                    service.set_recipe_draft(project_id, draft)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-assisted/projects/{project_id}/recipe/publish")
    def publish_krea2_assisted_recipe(
        project_id: str,
        body: Krea2AssistedRecipePublishBody | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            draft = (
                parse_krea2_assisted_recipe_draft(body.draft.model_dump())
                if body is not None and body.draft is not None
                else None
            )
            project, recipe = service.publish_recipe(project_id, draft)
            return {
                "project": serialize_krea2_assisted_project(project),
                "recipe": serialize_krea2_visual_recipe(recipe),
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-edit/spec")
    def krea2_edit_spec() -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        render_models: list[object] = []
        loras: list[object] = []
        if krea2_batch is not None:
            render_models = [
                serialize_krea2_resource(resource)
                for resource in krea2_batch.resources.list_models()
            ]
            loras = [
                serialize_krea2_resource(resource)
                for resource in krea2_batch.resources.list_loras()
            ]
        resource_warnings = (
            list(
                getattr(
                    krea2_batch.resources,
                    "inventory_warnings",
                    lambda: (),
                )()
            )
            if krea2_batch is not None
            else []
        )
        return {
            "recipe": {
                "id": service.workflow.reference.recipe_id,
                "version": service.workflow.reference.version,
                "workflow_sha256": service.workflow.reference.workflow_sha256,
                "status": service.workflow.status,
            },
            "llm_models": [_serialize_llm_model(model) for model in service.list_models()],
            "render_models": render_models,
            "loras": loras,
            "resource_warnings": resource_warnings,
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "defaults": {
                "model_id": "Krea2/kroma-v0.2-turbo.safetensors",
                "aspect_ratio": Krea2AspectRatio.PORTRAIT_WIDESCREEN.value,
                "megapixels": 1.0,
                "ref_boost": 2.5,
                "steps": 10,
            },
            "limits": {
                "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
                "ref_boost": {"minimum": 0.0, "maximum": 10.0, "step": 0.1},
                "steps": {"minimum": 1, "maximum": 100},
                "lora_count": 4,
            },
            "fixed": {
                "identity_lora": "krea2/krea2_identity_edit_v1_2.safetensors",
                "identity_lora_strength": 1.0,
                "cfg": 1.0,
                "sampler": "euler",
                "scheduler": "simple",
                "grounding_px": 768,
            },
            "project_exports": {
                "enabled": service.project_export_root is not None,
                "root": service.project_export_root,
            },
        }

    @app.post("/api/image-lab/krea2-edit/sources", status_code=status.HTTP_201_CREATED)
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

    @app.get("/api/image-lab/krea2-edit/sources")
    def list_krea2_edit_sources(
        limit: int = 100,
        include_hidden: bool = False,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {
                "sources": [
                    serialize_krea2_edit_source(source)
                    for source in service.list(limit, include_hidden=include_hidden)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/image-lab/krea2-edit/sources/{source_id}")
    def get_krea2_edit_source(source_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {"source": serialize_krea2_edit_source(service.get(source_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source not found") from error

    @app.post("/api/image-lab/krea2-edit/sources/{source_id}/prompt/stream")
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
        return _krea2_edit_stream_response(
            service.stream_prepare_prompt(
                source_id,
                body.instruction,
                body.model_id,
                base_prompt=body.base_prompt,
                feedback_attempt_id=body.feedback_attempt_id,
                prompt_language=prompt_language,
                include_reasoning=include_reasoning,
            )
        )

    @app.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_krea2_edit_attempt(
        source_id: str,
        body: Krea2EditAttemptBody,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source = service.prepare_attempt(
                source_id,
                Krea2EditAttemptRequest(
                    prompt=body.prompt,
                    settings=Krea2EditSettings(
                        model_name=body.model_id,
                        aspect_ratio=Krea2AspectRatio(body.aspect_ratio),
                        megapixels=body.megapixels,
                        seed=_parse_json_seed(body.seed),
                        ref_boost=body.ref_boost,
                        steps=body.steps,
                        loras=tuple(
                            Krea2LoraSelection(name=value.name, strength=value.strength)
                            for value in (body.loras or [])
                        ),
                    ),
                ),
            )
            return {"source": serialize_krea2_edit_source(source)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_krea2_edit_attempt(
        source_id: str,
        attempt_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source = service.queue_attempt(source_id, attempt_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.execute_attempt, source_id, attempt_id)
        return {"source": serialize_krea2_edit_source(source)}

    @app.post("/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/cancel")
    def cancel_krea2_edit_attempt(source_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {
                "source": serialize_krea2_edit_source(
                    service.cancel_attempt(source_id, attempt_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/promote",
        status_code=status.HTTP_201_CREATED,
    )
    def promote_krea2_edit_attempt(
        source_id: str,
        attempt_id: str,
        body: Krea2EditPromotionBody | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
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
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="KREA2 edit source or attempt not found",
            ) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-edit/sources/{source_id}/export")
    def retry_krea2_edit_project_export(source_id: str) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            return {
                "source": serialize_krea2_edit_source(
                    service.retry_project_export(source_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="KREA2 edit project not found",
            ) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/image-lab/krea2-edit/sources/{source_id}/state")
    def update_krea2_edit_source_state(
        source_id: str,
        body: Krea2EditSourceStateBody,
    ) -> dict[str, object]:
        service = _require_krea2_edit(krea2_edit)
        try:
            source = service.set_state(source_id, Krea2EditSourceState(body.state))
            return {"source": serialize_krea2_edit_source(source)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 edit source not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/video-lab/spec")
    def video_lab_spec() -> dict[str, object]:
        service = _require_video_lab(video_lab)
        presets: list[dict[str, object]] = []
        for preset in service.recipe.presets.values():
            settings = VideoLabSettings(
                aspect_ratio=preset.aspect_ratio,
                megapixels=preset.megapixels,
                duration_seconds=preset.duration_seconds,
                steps=preset.steps,
                seed=0,
            )
            presets.append(
                {
                    "id": preset.preset_id,
                    "preset_id": preset.preset_id,
                    "label": preset.label,
                    "aspect_ratio": preset.aspect_ratio.value,
                    "megapixels": preset.megapixels,
                    "duration_seconds": preset.duration_seconds,
                    "steps": preset.steps,
                    "frames": settings.frame_count,
                    "effective_duration_seconds": (
                        settings.effective_duration_seconds
                    ),
                    "preview": {
                        "frames": preset.preview_frames,
                        "fps": preset.preview_fps,
                        "jpeg_quality": preset.preview_jpeg_quality,
                        "max_resolution": preset.preview_max_resolution,
                    },
                }
            )
        return {
            "operation_id": service.recipe.reference.operation_id,
            "recipe": {
                "id": service.recipe.reference.recipe_id,
                "version": service.recipe.reference.version,
                "workflow_sha256": service.recipe.reference.workflow_sha256,
                "status": service.recipe.status,
            },
            "presets": presets,
            "defaults": {"preset_id": presets[0]["id"]},
            "aspect_ratios": [ratio.value for ratio in VideoAspectRatio],
            "megapixels": [0.3, 0.6, 1.0, 1.2],
            "fps": 24,
            "limits": {
                "reference_images": {"minimum": 1, "maximum": 3},
                "megapixels": {"minimum": 0.1, "maximum": 16.0, "step": 0.1},
                "duration_seconds": {"minimum": 5.0, "maximum": 15.0},
                "steps": {"minimum": 1, "maximum": 100},
            },
            "preview_ws_url": "/api/video-lab/runs/{run_id}/events",
            "preview_transport": "same-origin-relay",
        }

    @app.websocket("/api/video-lab/runs/{run_id}/events")
    async def video_lab_events(websocket: WebSocket, run_id: str) -> None:
        if video_lab is None:
            await websocket.close(code=4403, reason="Video Lab is not configured")
            return
        try:
            video_lab.runs.get(run_id)
        except (KeyError, FileNotFoundError, ValueError):
            await websocket.close(code=4404, reason="Video Lab run not found")
            return

        upstream_url = getattr(video_lab.comfy, "websocket_url", None)
        if not isinstance(upstream_url, str) or not upstream_url.strip():
            await websocket.close(code=1011, reason="Preview relay is not configured")
            return

        await websocket.accept()
        connector = video_preview_connector or _connect_video_preview
        try:
            async with connector(upstream_url) as upstream:
                await websocket.send_json(
                    {
                        "type": "panelforge_preview_status",
                        "data": {"status": "connected", "run_id": run_id},
                    }
                )
                await _relay_video_preview(websocket, upstream)
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await websocket.send_json(
                    {
                        "type": "panelforge_preview_status",
                        "data": {
                            "status": "error",
                            "run_id": run_id,
                            "message": (
                                "Preview live indisponible : PanelForge ne peut "
                                "pas joindre le WebSocket ComfyUI."
                            ),
                        },
                    }
                )
                await websocket.close(code=1011, reason="Preview relay unavailable")
            except (RuntimeError, WebSocketDisconnect):
                pass

    @app.post("/api/video-lab/runs", status_code=status.HTTP_201_CREATED)
    async def prepare_video_lab_run(
        images: Annotated[list[UploadFile] | None, File()] = None,
        source_asset_ids: Annotated[list[str] | None, Form()] = None,
        source_labels: Annotated[list[str] | None, Form()] = None,
        prompt: Annotated[str, Form()] = "",
        preset_id: Annotated[str, Form()] = "h3-balanced",
        aspect_ratio: Annotated[str | None, Form()] = None,
        megapixels: Annotated[float | None, Form()] = None,
        duration_seconds: Annotated[float | None, Form()] = None,
        steps: Annotated[int | None, Form()] = None,
        seed: Annotated[str | None, Form()] = None,
        seed_locked: Annotated[bool, Form()] = False,
    ) -> dict[str, object]:
        service = _require_video_lab(video_lab)
        uploads = images or []
        asset_ids = source_asset_ids or []
        if bool(uploads) == bool(asset_ids):
            await _close_uploads(uploads)
            raise HTTPException(
                status_code=422,
                detail=(
                    "provide either 1-3 images or 1-3 source_asset_ids, "
                    "but not both"
                ),
            )
        if not 1 <= len(uploads or asset_ids) <= 3:
            await _close_uploads(uploads)
            raise HTTPException(
                status_code=422,
                detail="Video Lab requires between 1 and 3 source images",
            )

        try:
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("prompt must not be empty")
            parsed_ratio = (
                VideoAspectRatio(aspect_ratio)
                if aspect_ratio is not None
                else None
            )
            parsed_seed = _parse_seed(seed) if seed is not None else None
            preset = service.recipe.presets.get(preset_id)
            if preset is None:
                raise ValueError(f"unknown Video Lab preset {preset_id!r}")
            # Validate all controls before persisting uploaded assets. The runner
            # repeats this at the application boundary.
            VideoLabSettings(
                aspect_ratio=parsed_ratio or preset.aspect_ratio,
                megapixels=(preset.megapixels if megapixels is None else megapixels),
                duration_seconds=(
                    preset.duration_seconds
                    if duration_seconds is None
                    else duration_seconds
                ),
                steps=preset.steps if steps is None else steps,
                seed=0 if parsed_seed is None else parsed_seed,
                seed_locked=seed_locked,
            )
            if uploads:
                buffered: list[tuple[bytes, str, str]] = []
                for index, upload in enumerate(uploads):
                    content = await upload.read(MAX_IMAGE_BYTES + 1)
                    if len(content) > MAX_IMAGE_BYTES:
                        raise ValueError("source image exceeds the 25 MiB limit")
                    media_type = detect_image_media_type(content)
                    label = (
                        source_labels[index]
                        if source_labels and index < len(source_labels)
                        else upload.filename or f"Picture {index + 1}"
                    )
                    buffered.append((content, media_type, label))
                if source_labels and len(source_labels) != len(buffered):
                    raise ValueError("source_labels must align with uploaded images")
                created = [
                    service.assets.create(content, media_type=media_type)
                    for content, media_type, _ in buffered
                ]
                resolved_asset_ids = tuple(asset.asset_id for asset in created)
                resolved_labels = tuple(label for _, _, label in buffered)
            else:
                resolved_asset_ids = tuple(asset_ids)
                resolved_labels = tuple(source_labels or ())

            request = VideoLabRunRequest(
                source_asset_ids=resolved_asset_ids,
                source_labels=resolved_labels,
                prompt=prompt,
                preset_id=preset_id,
                aspect_ratio=parsed_ratio,
                megapixels=megapixels,
                duration_seconds=duration_seconds,
                steps=steps,
                seed=parsed_seed,
                seed_locked=seed_locked,
            )
            run = service.prepare(request)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="source asset not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await _close_uploads(uploads)
        return serialize_video_lab_run(run)

    @app.post(
        "/api/video-lab/runs/{run_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_video_lab_run(
        run_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_video_lab(video_lab)
        try:
            run = service.queue(run_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="video run not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.execute, run.run_id)
        return serialize_video_lab_run(run)

    @app.get("/api/video-lab/runs")
    def list_video_lab_runs(limit: int = 30) -> dict[str, object]:
        service = _require_video_lab(video_lab)
        try:
            runs = service.list(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"runs": [serialize_video_lab_run(run) for run in runs]}

    @app.get("/api/video-lab/runs/{run_id}")
    def get_video_lab_run(run_id: str) -> dict[str, object]:
        service = _require_video_lab(video_lab)
        try:
            return serialize_video_lab_run(service.get(run_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="video run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/video-lab/runs/{run_id}/cancel")
    def cancel_video_lab_run(run_id: str) -> dict[str, object]:
        service = _require_video_lab(video_lab)
        try:
            return serialize_video_lab_run(service.cancel(run_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="video run not found") from error
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/h3-render/spec")
    def h3_render_spec(mode: str = "h3-base") -> dict[str, object]:
        service = _require_h3_render(h3_render)
        input_mode = (
            H3RenderInputMode.REF2VA
            if mode == "ref2va"
            else H3RenderInputMode.T2VA
        )
        recipe = service.workflow_for_mode(
            input_mode
        )
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
        if hasattr(recipe, "maximum_reference_images"):
            limits["reference_images"] = {
                "minimum": recipe.minimum_reference_images,
                "maximum": recipe.maximum_reference_images,
            }
        return {
            "operation_id": recipe.reference.operation_id,
            "recipe": {
                "id": recipe.reference.recipe_id,
                "version": recipe.reference.version,
                "workflow_sha256": recipe.reference.workflow_sha256,
                "status": recipe.status,
            },
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
                        "Stable 0.2.0 · caméra compilée"
                        if version.value == "0.2.0"
                        else "Legacy 0.1.0"
                    ),
                }
                for version in service.revision_versions_for_mode(input_mode)
            ],
            "default_revision_version": service.default_revision_version(
                input_mode
            ).value,
        }

    @app.post(
        "/api/h3-render/projects/from-session/{session_id}",
        status_code=status.HTTP_201_CREATED,
    )
    def create_h3_render_project(session_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            return {"project": serialize_h3_render_project(service.get_or_create_from_session(session_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 prompt session not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/h3-render/projects/{project_id}")
    def get_h3_render_project(project_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            return {"project": serialize_h3_render_project(service.get(project_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/h3-render/projects/{project_id}/chat/stream")
    def stream_h3_render_chat(
        project_id: str,
        body: H3RenderChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_h3_render(h3_render)
        return _h3_render_stream_response(service.stream_chat(
            project_id,
            body.message,
            feedback_attempt_id=body.feedback_attempt_id,
            revision_version=body.revision_version,
            include_reasoning=include_reasoning,
        ))

    @app.post(
        "/api/h3-render/projects/{project_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_h3_render_attempt(
        project_id: str,
        body: H3RenderAttemptBody,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            seed = _parse_json_seed(body.seed)
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
            )
            return {"project": serialize_h3_render_project(project)}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/h3-render/projects/{project_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_h3_render_attempt(
        project_id: str,
        attempt_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            project = service.queue_attempt(project_id, attempt_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        background_tasks.add_task(service.execute_attempt, project_id, attempt_id)
        return {"project": serialize_h3_render_project(project)}

    @app.post("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/cancel")
    def cancel_h3_render_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            return {"project": serialize_h3_render_project(service.cancel_attempt(project_id, attempt_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project or attempt not found") from error
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/resume")
    def resume_h3_render_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            return {"project": serialize_h3_render_project(service.resume_attempt(project_id, attempt_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/h3-render/projects/{project_id}/feedback")
    def select_h3_render_feedback(
        project_id: str,
        body: H3RenderFeedbackBody,
    ) -> dict[str, object]:
        service = _require_h3_render(h3_render)
        try:
            return {"project": serialize_h3_render_project(service.select_feedback(project_id, body.attempt_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="H3 render project or attempt not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.websocket("/api/h3-render/projects/{project_id}/attempts/{attempt_id}/events")
    async def h3_render_events(websocket: WebSocket, project_id: str, attempt_id: str) -> None:
        if h3_render is None:
            await websocket.close(code=4403, reason="H3 renderer is not configured")
            return
        try:
            h3_render.get(project_id).attempt(attempt_id)
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
                await _relay_video_preview(websocket, upstream)
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

    @app.get("/api/prompt-lab/spec")
    def prompt_lab_spec() -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return {
            "max_references": MAX_PROMPT_REFERENCES,
            "max_image_bytes": MAX_IMAGE_BYTES,
            "profiles": [
                {
                    "id": profile.profile_id,
                    "version": profile.version,
                    "display_name": profile.display_name,
                    "target_model_family": profile.target_model_family,
                    "session_mode": profile.session_mode.value,
                    "supports_interpretation": (
                        profile.interpretation_system_prompt is not None
                    ),
                    "supports_brief": profile.brief_system_prompt is not None,
                }
                for profile in service.list_profiles()
            ],
        }

    @app.get("/api/prompt-lab/models")
    def prompt_lab_models() -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return {
            "models": [
                _serialize_llm_model(model)
                for model in service.list_models()
            ]
        }

    @app.post("/api/prompt-lab/sessions", status_code=status.HTTP_201_CREATED)
    async def create_prompt_lab_session(
        model_id: Annotated[str, Form()],
        profile_id: Annotated[str, Form()],
        profile_version: Annotated[str, Form()],
        images: Annotated[list[UploadFile] | None, File()] = None,
        roles: Annotated[list[str] | None, Form()] = None,
        usages: Annotated[list[str] | None, Form()] = None,
        evidence_policies: Annotated[list[str] | None, Form()] = None,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        images = images or []
        roles = roles or []
        if len(images) > MAX_PROMPT_REFERENCES:
            raise HTTPException(
                status_code=422,
                detail=f"provide at most {MAX_PROMPT_REFERENCES} images",
            )
        if len(images) != len(roles):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one role for each image",
            )
        if usages is not None and len(images) != len(usages):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one usage set for each image",
            )
        if evidence_policies is not None and len(images) != len(evidence_policies):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one evidence policy for each image",
            )

        uploaded: list[
            tuple[
                bytes,
                str,
                str,
                str,
                tuple[ReferenceUse, ...],
                ReferenceEvidencePolicy,
            ]
        ] = []
        try:
            service.get_profile(profile_id, profile_version)
            usage_values = usages or [ReferenceUse.SUBJECT.value] * len(images)
            policy_values = evidence_policies or [
                ReferenceEvidencePolicy.FULL.value
            ] * len(images)
            for index, (image, role, raw_uses, raw_policy) in enumerate(
                zip(images, roles, usage_values, policy_values, strict=True),
                1,
            ):
                content = await image.read(MAX_IMAGE_BYTES + 1)
                await image.close()
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError(f"image {index} exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                label = (image.filename or "").strip() or f"Image {index}"
                uploaded.append(
                    (
                        content,
                        media_type,
                        role,
                        label,
                        _parse_reference_uses(raw_uses),
                        ReferenceEvidencePolicy(raw_policy),
                    )
                )

            references = tuple(
                NewReference(
                    asset_id=service.create_asset(content, media_type).asset_id,
                    role=role,
                    label=label,
                    uses=reference_uses,
                    evidence_policy=evidence_policy,
                )
                for (
                    content,
                    media_type,
                    role,
                    label,
                    reference_uses,
                    evidence_policy,
                ) in uploaded
            )
            session = service.create_session(
                model_id=model_id,
                profile_id=profile_id,
                profile_version=profile_version,
                references=references,
            )
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="prompt profile not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return serialize_prompt_session(session)

    @app.get("/api/prompt-lab/sessions")
    def list_prompt_lab_sessions(limit: int = 20) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            sessions = service.list_sessions(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "sessions": [serialize_prompt_session(session) for session in sessions]
        }

    @app.get("/api/prompt-lab/sessions/{session_id}")
    def get_prompt_lab_session(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            return serialize_prompt_session(service.get_session(session_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="prompt session not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/fork",
        status_code=status.HTTP_201_CREATED,
    )
    def fork_prompt_lab_session(
        session_id: str,
        body: PromptSessionForkBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            return serialize_prompt_session(
                service.fork_session(
                    session_id,
                    model_id=body.model_id,
                    profile_id=body.profile_id,
                    profile_version=body.profile_version,
                )
            )
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="prompt session or reference asset not found",
            ) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/structure")
    def structure_prompt_brief(
        session_id: str,
        body: BriefStructureBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.structure_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
                body.creative_axes.domain_value() if body.creative_axes else None,
            )
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/structure/stream")
    def stream_prompt_brief(
        session_id: str,
        body: BriefStructureBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_structure_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
                creative_axes=(
                    body.creative_axes.domain_value() if body.creative_axes else None
                ),
                include_reasoning=include_reasoning,
            )
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/edit")
    def edit_prompt_brief(
        session_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.edit_brief(session_id, body.content))

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/revise")
    def revise_prompt_brief(
        session_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_brief(session_id, body.instruction)
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/revise/stream")
    def stream_prompt_brief_revision(
        session_id: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_brief(
                session_id,
                body.instruction,
                include_reasoning=include_reasoning,
            )
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/approve")
    def approve_prompt_brief(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.approve_brief(session_id))

    @app.get("/api/prompt-lab/cookbooks")
    def list_prompt_cookbooks() -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        return {
            "cookbooks": [
                {
                    "id": cookbook.reference.cookbook_id,
                    "version": cookbook.reference.version,
                    "display_name": cookbook.display_name,
                    "description": cookbook.description,
                    "target_mode": cookbook.target_mode,
                    "output_contract": cookbook.output_contract,
                    "preset": cookbook.preset,
                    "invalid_camera_target_policy": (
                        cookbook.invalid_camera_target_policy
                    ),
                    "writer_projection": cookbook.writer_projection,
                    "stages": list(cookbook.stages),
                    "supports_plan_reconciliation": bool(
                        cookbook.beat_sheet_reconcile_system_prompt
                        and cookbook.beat_sheet_reconcile_user_prompt
                    ),
                    "sources": list(cookbook.sources),
                    "engine_contract": {
                        "id": cookbook.reference.engine_contract_id,
                        "version": cookbook.reference.engine_contract_version,
                    },
                    "slots": [
                        {
                            "id": slot.slot_id,
                            "label": slot.label,
                            "description": slot.description,
                            "evidence_policy": slot.evidence_policy.value,
                            "subject_label": slot.subject_label,
                            "accepted_uses": list(slot.accepted_uses),
                            "required_uses": list(slot.required_uses),
                            "required_shots": list(slot.required_shots),
                            "minimum_references": slot.minimum_references,
                            "maximum_references": slot.maximum_references,
                        }
                        for slot in cookbook.slots
                    ],
                }
                for cookbook in service.list_cookbooks()
            ]
        }

    @app.get("/api/prompt-lab/sessions/{session_id}/composition")
    def get_prompt_composition(session_id: str) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        try:
            composition = service.get(session_id)
        except (KeyError, FileNotFoundError):
            return {"composition": None}
        return {"composition": serialize_prompt_composition(composition, service)}

    @app.post("/api/prompt-lab/sessions/{session_id}/composition")
    def configure_prompt_composition(
        session_id: str,
        body: CompositionConfigureBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        public_cookbooks = {
            (cookbook.reference.cookbook_id, cookbook.reference.version)
            for cookbook in service.list_cookbooks()
        }
        if (body.cookbook_id, body.cookbook_version) not in public_cookbooks:
            raise HTTPException(
                status_code=422,
                detail="cookbook is not available for manual configuration",
            )
        return _composition_action(
            service,
            lambda: service.configure(
                session_id,
                body.cookbook_id,
                body.cookbook_version,
                tuple(
                    CookbookBinding(
                        slot_id=slot_id,
                        reference_ids=tuple(reference_ids),
                    )
                    for slot_id, reference_ids in body.bindings.items()
                ),
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/super-fast/stream")
    def stream_super_fast_ref2v(
        session_id: str,
        body: SuperFastRef2VBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        lab_service = _require_prompt_lab(prompt_lab)
        composition_service = _require_prompt_composition(prompt_composition)
        try:
            source_session = lab_service.get_session(session_id)
            if (
                source_session.profile_id != "minimax.h3.ref2v.direct"
                or source_session.profile_version not in {"0.1.0", "0.4.0"}
                or source_session.session_mode.value != "direct_multimodal"
            ):
                raise ValueError(
                    "super-fast generation is only available for Ref2V Direct sessions"
                )
            try:
                existing_composition = composition_service.get(session_id)
            except (KeyError, FileNotFoundError):
                existing_composition = None
            cookbook_version = SUPER_FAST_REF2V_COOKBOOK_VERSION
            if existing_composition is not None:
                if (
                    existing_composition.cookbook.cookbook_id
                    != SUPER_FAST_REF2V_COOKBOOK_ID
                    or existing_composition.cookbook.version not in {"0.1.0", "0.2.0"}
                ):
                    raise ValueError(
                        "this session already uses a non-super-fast cookbook"
                    )
                cookbook_version = existing_composition.cookbook.version
            session = lab_service.create_super_fast_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
                creative_axes=(
                    body.creative_axes.domain_value() if body.creative_axes else None
                ),
                legacy_plan=cookbook_version == "0.1.0",
            )
            composition_service.configure(
                session_id,
                SUPER_FAST_REF2V_COOKBOOK_ID,
                cookbook_version,
                (
                    CookbookBinding(
                        slot_id="references",
                        reference_ids=tuple(
                            reference.reference_id
                            for reference in session.references
                        ),
                    ),
                ),
            )
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="prompt session or internal cookbook not found",
            ) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _composition_stream_action(
            composition_service,
            lambda: composition_service.stream_generate_super_fast(
                session_id,
                include_reasoning=include_reasoning,
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/generate/stream")
    def stream_composition_generation(
        session_id: str,
        stage: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_generate(
                session_id,
                composition_stage,
                include_reasoning=include_reasoning,
            ),
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/beat-sheet/reconcile/stream"
    )
    def stream_action_plan_reconciliation(
        session_id: str,
        body: PlanArbitrationBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        return _composition_stream_action(
            service,
            lambda: service.stream_reconcile_action_plan(
                session_id,
                body.decisions,
                body.instruction,
                include_reasoning=include_reasoning,
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/edit")
    def edit_composition_stage(
        session_id: str,
        stage: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_action(
            service,
            lambda: service.edit(session_id, composition_stage, body.content),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/revise/stream")
    def stream_composition_revision(
        session_id: str,
        stage: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_revise(
                session_id,
                composition_stage,
                body.instruction,
                include_reasoning=include_reasoning,
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/approve")
    def approve_composition_stage(
        session_id: str,
        stage: str,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_action(
            service,
            lambda: service.approve(session_id, composition_stage),
        )

    return app


def _serialize_llm_model(model) -> dict[str, object]:
    model_id = model.model_id
    display_name = getattr(model, "display_name", None) or model_id
    source = getattr(model, "source", "server") or "server"
    return {
        "id": model_id,
        "label": display_name,
        "source": source,
    }


def serialize_run(run: RunRecord) -> dict[str, object]:
    controls = {
        control.control_id: (
            str(control.value) if control.control_id == "seed" else control.value
        )
        for control in run.controls
    }
    output_asset_id = run.output_asset_ids[0] if run.output_asset_ids else None
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "status": run.status.value,
        "decision": run.review_status.value,
        "recipe": {
            "id": run.recipe.recipe_id,
            "version": run.recipe.version,
            "workflow_sha256": run.recipe.workflow_sha256,
        },
        "source_asset_id": run.source_asset_ids[0],
        "source_url": f"/api/assets/{run.source_asset_ids[0]}/content",
        "output_asset_id": output_asset_id,
        "result_asset_id": output_asset_id,
        "result_url": (
            f"/api/assets/{output_asset_id}/content" if output_asset_id else None
        ),
        "parent_run_id": run.parent_run_id,
        "controls": controls,
        "compiled_prompt": run.prompt.positive,
        "negative_prompt": run.prompt.negative,
        "prompt_policy": run.prompt.policy.value,
        "experimental_overrides": list(run.experimental_overrides),
        "execution_id": run.execution_id,
        "compiled_workflow_sha256": run.compiled_workflow_sha256,
        "error": run.error,
    }


def serialize_krea2_run(run: Krea2LabRun) -> dict[str, object]:
    """Expose a KREA2 render without local paths or workflow internals."""
    settings = {
        "model_id": run.settings.model_name,
        "model_name": run.settings.model_name,
        "aspect_ratio": run.settings.aspect_ratio.value,
        "megapixels": run.settings.megapixels,
        "seed": str(run.settings.seed),
        "seed_locked": run.settings.seed_locked,
    }
    output_url = (
        f"/api/assets/{run.output_asset_id}/content"
        if run.output_asset_id is not None
        else None
    )
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "status": run.status.value,
        "recipe": {
            "id": run.recipe.recipe_id,
            "version": run.recipe.version,
            "workflow_sha256": run.recipe.workflow_sha256,
        },
        "preset_id": run.preset_id,
        "prompt": run.prompt,
        "model_id": run.settings.model_name,
        "model_name": run.settings.model_name,
        "aspect_ratio": run.settings.aspect_ratio.value,
        "megapixels": run.settings.megapixels,
        "seed": str(run.settings.seed),
        "seed_locked": run.settings.seed_locked,
        "settings": settings,
        "parameters": settings,
        "resolution": {
            "width": run.settings.resolution[0],
            "height": run.settings.resolution[1],
        },
        "source_storyboard_run_id": run.source_storyboard_run_id,
        "source_prompt_sha256": run.source_prompt_sha256,
        "execution_id": run.execution_id,
        "compiled_workflow_sha256": run.compiled_workflow_sha256,
        "output_asset_id": run.output_asset_id,
        "output_url": output_url,
        "output_content_url": output_url,
        "result_url": output_url,
        "error": run.error,
    }


def serialize_video_lab_run(run: VideoLabRun) -> dict[str, object]:
    """Expose one Video Lab record without leaking local filesystem paths."""
    references = [
        {
            "asset_id": asset_id,
            "label": label,
            "name": label,
            "content_url": f"/api/assets/{asset_id}/content",
        }
        for asset_id, label in zip(run.source_asset_ids, run.source_labels)
    ]
    settings = {
        "aspect_ratio": run.settings.aspect_ratio.value,
        "megapixels": run.settings.megapixels,
        "duration_seconds": run.settings.duration_seconds,
        "steps": run.settings.steps,
        "seed": str(run.settings.seed),
        "seed_locked": run.settings.seed_locked,
    }
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "status": run.status.value,
        "recipe": {
            "id": run.recipe.recipe_id,
            "version": run.recipe.version,
            "workflow_sha256": run.recipe.workflow_sha256,
        },
        "preset_id": run.preset_id,
        "references": references,
        "source_asset_ids": list(run.source_asset_ids),
        "source_labels": list(run.source_labels),
        "prompt": run.prompt,
        "settings": settings,
        "parameters": settings,
        "seed": str(run.settings.seed),
        "frames": run.settings.frame_count,
        "frame_count": run.settings.frame_count,
        "effective_duration_seconds": run.settings.effective_duration_seconds,
        "resolution": {
            "width": run.settings.resolution[0],
            "height": run.settings.resolution[1],
        },
        "execution_id": run.execution_id,
        "events_url": f"/api/video-lab/runs/{run.run_id}/events",
        "compiled_workflow_sha256": run.compiled_workflow_sha256,
        "output_asset_id": run.output_asset_id,
        "output_url": (
            f"/api/assets/{run.output_asset_id}/content"
            if run.output_asset_id is not None
            else None
        ),
        "error": run.error,
    }


def serialize_h3_render_project(project: H3RenderProject) -> dict[str, object]:
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
        settings = {
            "aspect_ratio": attempt.settings.aspect_ratio.value,
            "megapixels": attempt.settings.megapixels,
            "duration_seconds": attempt.settings.duration_seconds,
            "effective_duration_seconds": attempt.settings.effective_duration_seconds,
            "steps": attempt.settings.steps,
            "seed": str(attempt.settings.seed),
            "seed_locked": attempt.settings.seed_locked,
            "resolution": {
                "width": attempt.settings.resolution[0],
                "height": attempt.settings.resolution[1],
            },
            "frames": attempt.settings.frame_count,
        }
        attempts.append({
            "id": attempt.attempt_id,
            "attempt_id": attempt.attempt_id,
            "index": attempt.index,
            "status": attempt.status.value,
            "prompt": attempt.prompt,
            "effective_prompt": attempt.effective_prompt,
            "music_enabled": attempt.music_enabled,
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
        "project_id": project.project_id,
        "source_session_id": project.source_session_id,
        "source_prompt_revision_id": project.source_prompt_revision_id,
        "model_id": project.model_id,
        "input_mode": project.input_mode.value,
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
            }
            for turn in project.turns
        ],
        "attempts": attempts,
        "feedback_attempt_id": project.feedback_attempt_id,
        "warnings": list(project.warnings),
    }


def _runtime_status(
    *,
    model_runtime: Any | None,
    comfy_runtime: Any | None,
    local_gpu_monitor: Any | None,
) -> dict[str, object]:
    observed_at = datetime.now(UTC).isoformat()
    gpu: dict[str, object] = {
        "available": False,
        "name": None,
        "total_bytes": None,
        "free_bytes": None,
        "used_bytes": None,
        "used_percent": None,
    }
    comfy: dict[str, object] = {
        "available": False,
        "queue_running": None,
        "queue_pending": None,
        "cleanup_allowed": False,
        "warning": None,
    }
    if comfy_runtime is None:
        comfy["warning"] = "ComfyUI non configuré."
    else:
        stats_ok = False
        queue_ok = False
        try:
            stats = comfy_runtime.get_system_stats()
            stats_ok = True
            devices = tuple(getattr(stats, "devices", ()))
            if devices:
                device = devices[0]
                total = int(device.vram_total)
                free = int(device.vram_free)
                used = max(0, total - free)
                gpu.update(
                    {
                        "available": True,
                        "name": device.name,
                        "total_bytes": total,
                        "free_bytes": free,
                        "used_bytes": used,
                        "used_percent": round((used / total) * 100, 1) if total else 0.0,
                    }
                )
        except Exception:
            pass
        try:
            queue = comfy_runtime.get_queue()
            queue_ok = True
            running = len(queue.running)
            pending = len(queue.pending)
            comfy.update(
                {
                    "queue_running": running,
                    "queue_pending": pending,
                    "cleanup_allowed": running == 0 and pending == 0,
                }
            )
        except Exception:
            pass
        comfy["available"] = stats_ok or queue_ok
        if not comfy["available"]:
            comfy["warning"] = "ComfyUI indisponible."
        elif not stats_ok or not queue_ok:
            comfy["warning"] = "Statut ComfyUI partiel."

    llm: dict[str, object] = {
        "available": False,
        "running_models": [],
        "warning": None,
    }
    if model_runtime is None:
        llm["warning"] = "llama.swap non configuré."
    else:
        try:
            llm["running_models"] = list(model_runtime.running_models())
            llm["available"] = True
        except Exception:
            llm["warning"] = "llama.swap indisponible."
    local_gpu: dict[str, object] = {
        "available": False,
        "name": None,
        "total_bytes": None,
        "free_bytes": None,
        "used_bytes": None,
        "used_percent": None,
        "temperature_c": None,
        "warning": None,
    }
    if local_gpu_monitor is None:
        local_gpu["warning"] = "GPU local non configuré."
    else:
        try:
            local_stats = local_gpu_monitor.get_stats()
            local_gpu.update(
                {
                    "available": True,
                    "name": local_stats.name,
                    "total_bytes": local_stats.total_bytes,
                    "free_bytes": local_stats.free_bytes,
                    "used_bytes": local_stats.used_bytes,
                    "used_percent": local_stats.used_percent,
                    "temperature_c": local_stats.temperature_c,
                }
            )
        except Exception:
            local_gpu["warning"] = "GPU local indisponible."
    return {
        "observed_at": observed_at,
        "gpu": gpu,
        "local_gpu": local_gpu,
        "comfy": comfy,
        "llm": llm,
    }


def serialize_krea2_visual_recipe(recipe) -> dict[str, object]:
    return {
        "id": recipe.recipe_id,
        "recipe_id": recipe.recipe_id,
        "version": recipe.version,
        "display_name": recipe.display_name,
        "description": recipe.description,
        "identity": recipe.identity,
        "invariants": list(recipe.invariants),
        "variables": list(recipe.variables),
        "risks": list(recipe.risks),
        "canonical_prompt": recipe.canonical_prompt,
        "prompt_language": recipe.prompt_language.value,
        "content_sha256": recipe.content_sha256,
        "parent_version": recipe.parent_version,
        "status": recipe.status,
        "settings": {
            "model_id": recipe.settings.model_name,
            "aspect_ratio": recipe.settings.aspect_ratio.value,
            "megapixels": recipe.settings.megapixels,
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in recipe.settings.loras
            ],
        },
    }


def _krea2_prompt_language(value: str | None) -> Krea2PromptLanguage | None:
    return Krea2PromptLanguage(value) if value is not None else None


def _krea2_revision_settings(body: object) -> Krea2BatchSettings | None:
    model_name = getattr(body, "render_model_id", None)
    aspect_ratio = getattr(body, "aspect_ratio", None)
    megapixels = getattr(body, "megapixels", None)
    loras = getattr(body, "loras", None)
    if all(value is None for value in (model_name, aspect_ratio, megapixels, loras)):
        return None
    if model_name is None or aspect_ratio is None or megapixels is None:
        raise ValueError("checkpoint, ratio and megapixels must be provided together")
    return Krea2BatchSettings(
        model_name=model_name,
        aspect_ratio=Krea2AspectRatio(aspect_ratio),
        megapixels=megapixels,
        loras=tuple(
            Krea2LoraSelection(name=item.name, strength=item.strength)
            for item in (loras or [])
        ),
    )


def serialize_krea2_batch(batch: Krea2Batch) -> dict[str, object]:
    return {
        "id": batch.batch_id,
        "batch_id": batch.batch_id,
        "recipe_id": batch.recipe_id,
        "recipe_version": batch.recipe_version,
        "recipe_sha256": batch.recipe_sha256,
        "model_id": batch.model_id,
        "image_count": batch.image_count,
        "direction": batch.direction,
        "status": batch.status.value,
        "settings": {
            "model_id": batch.settings.model_name,
            "aspect_ratio": batch.settings.aspect_ratio.value,
            "megapixels": batch.settings.megapixels,
            "resolution": {
                "width": batch.settings.resolution[0],
                "height": batch.settings.resolution[1],
            },
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in batch.settings.loras
            ],
        },
        "items": [
            {
                "id": item.item_id,
                "item_id": item.item_id,
                "index": item.index,
                "prompt": item.prompt,
                "variation_signature": item.variation_signature,
                "seed": str(item.seed),
                "status": item.status.value,
                "execution_id": item.execution_id,
                "output_asset_id": item.output_asset_id,
                "output_url": (
                    f"/api/assets/{item.output_asset_id}/content"
                    if item.output_asset_id is not None
                    else None
                ),
                "error": item.error,
                "review": item.review.value,
                "comment": item.comment,
            }
            for item in batch.items
        ],
        "warnings": list(batch.warnings),
        "error": batch.error,
        "recipe_revision_draft": batch.recipe_revision_draft,
        "recipe_workshop": (
            json.loads(batch.recipe_workshop)
            if batch.recipe_workshop is not None
            else None
        ),
        "workshop_source_batch_id": batch.workshop_source_batch_id,
    }


def serialize_social_profile(profile: SocialChannelProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "language": profile.language.value,
        "mood": profile.mood,
        "vibe": profile.vibe,
        "example": profile.example,
        "instructions": profile.instructions,
    }


def serialize_social_project(project: SocialProject) -> dict[str, object]:
    return {
        "project_id": project.project_id,
        "id": project.project_id,
        "name": project.name,
        "model_id": project.model_id,
        "language": project.language.value,
        "variant_count": project.variant_count,
        "video_asset_id": project.video_asset_id,
        "video_filename": project.video_filename,
        "video_url": f"/api/assets/{project.video_asset_id}/content",
        "keyframes": [
            {
                "asset_id": asset_id,
                "position_percent": (10, 35, 65, 90)[index],
                "content_url": f"/api/assets/{asset_id}/content",
            }
            for index, asset_id in enumerate(project.keyframe_asset_ids)
        ],
        "mood": project.mood,
        "vibe": project.vibe,
        "example": project.example,
        "instructions": project.instructions,
        "channel_profile_id": project.channel_profile_id,
        "source_prompt_found": project.source_prompt is not None,
        "turns": [
            {
                "turn_id": turn.turn_id,
                "role": turn.role.value,
                "content": turn.content,
                "variants": [
                    {
                        "angle": variant.angle,
                        "hook": variant.hook,
                        "caption": variant.caption,
                        "hashtags": list(variant.hashtags),
                        "emojis": list(variant.emojis),
                    }
                    for variant in turn.variants
                ],
            }
            for turn in project.turns
        ],
        "latest_variants": [
            {
                "angle": variant.angle,
                "hook": variant.hook,
                "caption": variant.caption,
                "hashtags": list(variant.hashtags),
                "emojis": list(variant.emojis),
            }
            for variant in project.latest_variants
        ],
    }


def serialize_krea2_assisted_project(project: Krea2AssistedProject) -> dict[str, object]:
    draft = project.recipe_draft
    return {
        "id": project.project_id,
        "project_id": project.project_id,
        "name": project.name,
        "intention": project.intention,
        "model_id": project.model_id,
        "prompt_language": project.prompt_language.value,
        "reference_asset_id": project.reference_asset_id,
        "reference_filename": project.reference_filename,
        "reference_url": (
            f"/api/assets/{project.reference_asset_id}/content"
            if project.reference_asset_id is not None
            else None
        ),
        "turns": [
            {
                "turn_id": turn.turn_id,
                "mode": turn.mode.value,
                "role": turn.role.value,
                "content": turn.content,
                "guidance_asset_id": turn.guidance_asset_id,
                "guidance_filename": turn.guidance_filename,
                "guidance_url": (
                    f"/api/assets/{turn.guidance_asset_id}/content"
                    if turn.guidance_asset_id is not None
                    else None
                ),
                "questions": list(turn.questions),
                "prompt": turn.prompt,
                "recommendations": list(turn.recommendations),
            }
            for turn in project.turns
        ],
        "current_prompt": project.current_prompt,
        "attempts": [
            {
                "id": attempt.attempt_id,
                "attempt_id": attempt.attempt_id,
                "index": attempt.index,
                "prompt": attempt.prompt,
                "seed": str(attempt.seed),
                "status": attempt.status.value,
                "execution_id": attempt.execution_id,
                "output_asset_id": attempt.output_asset_id,
                "output_url": (
                    f"/api/assets/{attempt.output_asset_id}/content"
                    if attempt.output_asset_id is not None
                    else None
                ),
                "error": attempt.error,
                "accepted": attempt.accepted,
                "settings": {
                    "model_id": attempt.settings.model_name,
                    "aspect_ratio": attempt.settings.aspect_ratio.value,
                    "megapixels": attempt.settings.megapixels,
                    "resolution": {
                        "width": attempt.settings.resolution[0],
                        "height": attempt.settings.resolution[1],
                    },
                    "loras": [
                        {"name": value.name, "strength": value.strength}
                        for value in attempt.settings.loras
                    ],
                },
            }
            for attempt in project.attempts
        ],
        "feedback_attempt_id": project.feedback_attempt_id,
        "accepted_attempt_id": project.accepted_attempt_id,
        "recipe_draft": (
            {
                "recipe_id": draft.recipe_id,
                "display_name": draft.display_name,
                "description": draft.description,
                "identity": draft.identity,
                "invariants": list(draft.invariants),
                "variables": list(draft.variables),
                "risks": list(draft.risks),
                "canonical_prompt": draft.canonical_prompt,
                "prompt_language": draft.prompt_language.value,
            }
            if draft is not None
            else None
        ),
        "published_recipe": (
            {
                "recipe_id": project.published_recipe_id,
                "version": project.published_recipe_version,
            }
            if project.published_recipe_id is not None
            else None
        ),
        "export": {
            "status": (
                "failed"
                if project.export_error is not None
                else "exported"
                if project.export_path is not None
                else "pending"
            ),
            "path": project.export_path,
            "error": project.export_error,
        },
        "warnings": list(project.warnings),
    }


def serialize_krea2_edit_source(source: Krea2EditSource) -> dict[str, object]:
    metadata = source.metadata
    return {
        "id": source.source_id,
        "source_id": source.source_id,
        "source_asset_id": source.source_asset_id,
        "source_url": f"/api/assets/{source.source_asset_id}/content",
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
            "version": source.recipe.version,
            "workflow_sha256": source.recipe.workflow_sha256,
        },
        "metadata": {
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
            }
            for revision in source.revisions
        ],
        "attempts": [
            {
                "id": attempt.attempt_id,
                "attempt_id": attempt.attempt_id,
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
                "settings": {
                    "model_id": attempt.settings.model_name,
                    "aspect_ratio": attempt.settings.aspect_ratio.value,
                    "megapixels": attempt.settings.megapixels,
                    "seed": str(attempt.settings.seed),
                    "ref_boost": attempt.settings.ref_boost,
                    "steps": attempt.settings.steps,
                    "resolution": {
                        "width": attempt.settings.resolution[0],
                        "height": attempt.settings.resolution[1],
                    },
                    "loras": [
                        {"name": value.name, "strength": value.strength}
                        for value in attempt.settings.loras
                    ],
                },
            }
            for attempt in source.attempts
        ],
    }


def _connect_video_preview(url: str):
    """Open the ComfyUI preview channel used by the same-origin relay."""
    try:
        from websockets.asyncio.client import connect
    except ImportError as error:  # pragma: no cover - installation failure
        raise RuntimeError(
            "The 'websockets' dependency is required for Video Lab previews"
        ) from error
    return connect(
        url,
        open_timeout=10,
        close_timeout=5,
        max_size=None,
    )


async def _relay_video_preview(websocket: WebSocket, upstream: Any) -> None:
    """Forward ComfyUI text/binary events until either peer disconnects."""

    async def forward_upstream() -> None:
        while True:
            message = await upstream.recv()
            if isinstance(message, str):
                await websocket.send_text(message)
            else:
                await websocket.send_bytes(bytes(message))

    async def watch_browser() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    upstream_task = asyncio.create_task(forward_upstream())
    browser_task = asyncio.create_task(watch_browser())
    done, pending = await asyncio.wait(
        {upstream_task, browser_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()


async def _relay_runtime_monitor(websocket: WebSocket, upstream: Any) -> None:
    """Forward only Crystools telemetry, never ComfyUI prompt events."""

    async def forward_upstream() -> None:
        while True:
            message = await upstream.recv()
            if not isinstance(message, str):
                continue
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("type") != "crystools.monitor":
                continue
            data = payload.get("data")
            if isinstance(data, dict):
                await websocket.send_json({"type": "crystools.monitor", "data": data})

    async def watch_browser() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    upstream_task = asyncio.create_task(forward_upstream())
    browser_task = asyncio.create_task(watch_browser())
    done, pending = await asyncio.wait(
        {upstream_task, browser_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()


async def _close_uploads(uploads: list[UploadFile]) -> None:
    for upload in uploads:
        await upload.close()


def _parse_byte_range(value: str | None, content_length: int) -> tuple[int, int] | None:
    """Parse one HTTP bytes range, rejecting malformed or unsatisfiable ranges."""
    if value is None:
        return None
    if content_length < 0:
        raise ValueError("content_length must not be negative")
    unit, separator, raw_range = value.partition("=")
    if separator != "=" or unit.strip().lower() != "bytes":
        raise ValueError("unsupported range unit")
    raw_range = raw_range.strip()
    if not raw_range or "," in raw_range:
        raise ValueError("exactly one byte range is supported")
    raw_start, dash, raw_end = raw_range.partition("-")
    if dash != "-":
        raise ValueError("invalid byte range")
    raw_start = raw_start.strip()
    raw_end = raw_end.strip()

    if raw_start:
        if not raw_start.isdecimal() or (raw_end and not raw_end.isdecimal()):
            raise ValueError("invalid byte range")
        start = int(raw_start)
        if start >= content_length:
            raise ValueError("unsatisfiable byte range")
        end = content_length - 1 if not raw_end else int(raw_end)
        if end < start:
            raise ValueError("invalid byte range")
        return start, min(end, content_length - 1)

    if not raw_end or not raw_end.isdecimal():
        raise ValueError("invalid suffix byte range")
    suffix_length = int(raw_end)
    if suffix_length <= 0 or content_length == 0:
        raise ValueError("unsatisfiable suffix byte range")
    return max(content_length - suffix_length, 0), content_length - 1


def detect_image_media_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise ValueError("source must be a PNG, JPEG or WebP image")


def detect_video_media_type(content: bytes) -> str:
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "video/mp4"
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    raise ValueError("source must be an MP4 or WebM video")


def serialize_prompt_session(session: PromptLabSession) -> dict[str, object]:
    def creative_axes_payload(revision) -> dict[str, int]:
        axes = revision.creative_axes or creative_axes_from_legacy(
            revision.creative_freedom
        )
        return {
            "scene_life": axes.scene_life,
            "camera": axes.camera,
            "extra_motion": axes.extra_motion,
        }

    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "model_id": session.model_id,
        "session_mode": session.session_mode.value,
        "profile": {
            "id": session.profile_id,
            "version": session.profile_version,
        },
        "analysis_complete": session.analysis_complete,
        "interpretation_complete": session.interpretation_complete,
        "brief_complete": session.brief_complete,
        "brief_is_stale": session.brief_is_stale,
        "active_brief_revision_id": session.active_brief_revision_id,
        "approved_brief_revision_id": session.approved_brief_revision_id,
        "active_brief": (
            {
                "id": session.active_brief_revision.revision_id,
                "revision_id": session.active_brief_revision.revision_id,
                "source_text": session.active_brief_revision.source_text,
                "content": session.active_brief_revision.content,
                "creative_freedom": (
                    session.active_brief_revision.creative_freedom
                ),
                "creative_axes": creative_axes_payload(
                    session.active_brief_revision
                ),
                "origin": session.active_brief_revision.origin.value,
                "parent_revision_id": (
                    session.active_brief_revision.parent_revision_id
                ),
                "instruction": session.active_brief_revision.instruction,
            }
            if session.active_brief_revision is not None
            else None
        ),
        "brief_revisions": [
            {
                "id": revision.revision_id,
                "revision_id": revision.revision_id,
                "source_text": revision.source_text,
                "content": revision.content,
                "creative_freedom": revision.creative_freedom,
                "creative_axes": creative_axes_payload(revision),
                "origin": revision.origin.value,
                "parent_revision_id": revision.parent_revision_id,
                "instruction": revision.instruction,
                "references": [
                    {
                        "reference_id": reference.reference_id,
                        "analysis_revision_id": reference.analysis_revision_id,
                        "uses": [use.value for use in reference.uses],
                        "evidence_policy": reference.evidence_policy.value,
                    }
                    for reference in revision.references
                ],
            }
            for revision in session.brief_revisions
        ],
        "references": [
            {
                "id": reference.reference_id,
                "reference_id": reference.reference_id,
                "asset_id": reference.asset_id,
                "content_url": f"/api/assets/{reference.asset_id}/content",
                "role": reference.role,
                "label": reference.label,
                "evidence_policy": reference.evidence_policy.value,
                "review_status": reference.review_status.value,
                "uses": [use.value for use in reference.uses],
                "active_revision_id": reference.active_revision_id,
                "approved_revision_id": reference.approved_revision_id,
                "active_content": (
                    reference.active_revision.content
                    if reference.active_revision is not None
                    else None
                ),
                "revisions": [
                    {
                        "id": revision.revision_id,
                        "revision_id": revision.revision_id,
                        "content": revision.content,
                        "origin": revision.origin.value,
                        "parent_revision_id": revision.parent_revision_id,
                        "instruction": revision.instruction,
                    }
                    for revision in reference.revisions
                ],
                "interpretation_review_status": (
                    reference.interpretation_review_status.value
                ),
                "interpretation_is_stale": reference.interpretation_is_stale,
                "active_interpretation_id": reference.active_interpretation_id,
                "approved_interpretation_id": (
                    reference.approved_interpretation_id
                ),
                "active_interpretation": (
                    reference.active_interpretation.content
                    if reference.active_interpretation is not None
                    else None
                ),
                "interpretations": [
                    {
                        "id": interpretation.revision_id,
                        "revision_id": interpretation.revision_id,
                        "content": interpretation.content,
                        "origin": interpretation.origin.value,
                        "source_analysis_revision_id": (
                            interpretation.source_analysis_revision_id
                        ),
                        "uses": [use.value for use in interpretation.uses],
                        "parent_revision_id": interpretation.parent_revision_id,
                        "instruction": interpretation.instruction,
                    }
                    for interpretation in reference.interpretations
                ],
            }
            for reference in session.references
        ],
    }


class _Krea2ModelDiscovery:
    """Small lazy cache around ComfyUI's read-only model inventory."""

    def __init__(self, service: Krea2LabRunner) -> None:
        self._service = service
        self._lock = Lock()
        self._initialized = False
        self._installed: tuple[str, ...] | None = None
        self._status = "unavailable"
        self._refreshed_at: str | None = None
        self._error: str | None = None

    def snapshot(self, *, refresh: bool = False) -> dict[str, object]:
        with self._lock:
            if refresh or not self._initialized:
                self._refresh_locked()
            installed = self._installed
            status_value = self._status
            refreshed_at = self._refreshed_at
            error = self._error
        return {
            "models": self._model_entries(installed),
            "model_discovery": {
                "status": status_value,
                "refreshed_at": refreshed_at,
                "error": error,
            },
        }

    def resolve(self, requested_model: str | None) -> str:
        requested = requested_model or self._service.recipe.default_model
        if not isinstance(requested, str) or not requested.strip():
            raise ValueError("model_id must not be empty")
        requested_key = normalize_krea2_model_name(requested)
        canonical = next(
            (
                model
                for model in self._service.recipe.qualified_models
                if normalize_krea2_model_name(model) == requested_key
            ),
            None,
        )
        if canonical is None:
            raise ValueError(f"unqualified KREA2 model {requested!r}")

        snapshot = self.snapshot()
        entry = next(
            item
            for item in snapshot["models"]
            if isinstance(item, dict)
            and normalize_krea2_model_name(str(item.get("id", "")))
            == normalize_krea2_model_name(canonical)
        )
        if entry["installed"] is False:
            raise ValueError(f"KREA2 model {canonical!r} is not installed")
        return str(entry["id"])

    def _refresh_locked(self) -> None:
        self._initialized = True
        try:
            installed = tuple(self._service.comfy.list_unet_models())
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            self._status = "stale" if self._installed is not None else "unavailable"
            self._error = str(error) or error.__class__.__name__
            return
        self._installed = installed
        self._status = "available"
        self._refreshed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self._error = None

    def _model_entries(
        self,
        installed: tuple[str, ...] | None,
    ) -> list[dict[str, object]]:
        installed_by_key: dict[str, str] | None = None
        if installed is not None:
            installed_by_key = {}
            for model in installed:
                installed_by_key.setdefault(
                    normalize_krea2_model_name(model),
                    model,
                )
        entries: list[dict[str, object]] = []
        qualified_keys: set[str] = set()
        for model in self._service.recipe.qualified_models:
            key = normalize_krea2_model_name(model)
            qualified_keys.add(key)
            exact_model = (
                model
                if installed_by_key is None
                else installed_by_key.get(key, model)
            )
            is_installed = (
                None if installed_by_key is None else key in installed_by_key
            )
            entries.append(
                {
                    "id": exact_model,
                    "label": exact_model,
                    "installed": is_installed,
                    "qualified": True,
                    "selectable": is_installed is not False,
                    "default": (
                        key
                        == normalize_krea2_model_name(
                            self._service.recipe.default_model
                        )
                    ),
                }
            )

        if installed is not None:
            discovered = sorted(installed, key=str.casefold)
            for model in discovered:
                key = normalize_krea2_model_name(model)
                if key in qualified_keys or "krea2" not in key:
                    continue
                entries.append(
                    {
                        "id": model,
                        "label": model,
                        "installed": True,
                        "qualified": False,
                        "selectable": False,
                        "default": False,
                    }
                )
        return entries

def serialize_prompt_composition(
    composition: PromptComposition,
    service: PromptCompositionService,
) -> dict[str, object]:
    statuses = {status.stage: status for status in service.status(composition)}
    documents: dict[str, object] = {}
    for stage in CompositionStage:
        document = composition.document(stage)
        stage_status = statuses[stage]
        documents[stage.value] = {
            "stage": stage.value,
            "active_revision_id": document.active_revision_id,
            "approved_revision_id": document.approved_revision_id,
            "stale": stage_status.stale,
            "complete": stage_status.complete,
            "blocked_reason": stage_status.blocked_reason,
            "validation_errors": list(stage_status.validation_errors),
            "validation_warnings": list(stage_status.validation_warnings),
            "active_content": (
                document.active_revision.content
                if document.active_revision is not None
                else None
            ),
            "revisions": [
                {
                    "id": revision.revision_id,
                    "revision_id": revision.revision_id,
                    "content": revision.content,
                    "origin": revision.origin.value,
                    "source_ids": list(revision.source_ids),
                    "parent_revision_id": revision.parent_revision_id,
                    "instruction": revision.instruction,
                }
                for revision in document.revisions
            ],
        }
    return {
        "source_session_id": composition.source_session_id,
        "cookbook": {
            "id": composition.cookbook.cookbook_id,
            "version": composition.cookbook.version,
            "engine_contract": {
                "id": composition.cookbook.engine_contract_id,
                "version": composition.cookbook.engine_contract_version,
            },
        },
        "bindings": {
            binding.slot_id: list(binding.reference_ids)
            for binding in composition.bindings
        },
        "picture_mapping": [
            {"reference_id": reference_id, "picture_number": picture_number}
            for reference_id, picture_number in composition_picture_mapping(composition)
        ],
        "documents": documents,
    }


def _require_prompt_lab(value: PromptLabService | None) -> PromptLabService:
    if value is None:
        raise HTTPException(status_code=503, detail="Prompt engine is not configured")
    return value


def _require_prompt_composition(
    value: PromptCompositionService | None,
) -> PromptCompositionService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="Prompt composition is not configured",
        )
    return value


def _require_video_lab(value: VideoLabRunner | None) -> VideoLabRunner:
    if value is None:
        raise HTTPException(status_code=503, detail="Video Lab is not configured")
    return value


def _require_krea2_lab(value: Krea2LabRunner | None) -> Krea2LabRunner:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Image Lab is not configured",
        )
    return value


def _require_h3_render(value: H3RenderService | None) -> H3RenderService:
    if value is None:
        raise HTTPException(status_code=503, detail="H3 Base renderer is not configured")
    return value


def _require_krea2_batch(value: Krea2BatchService | None) -> Krea2BatchService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Batch Lab is not configured",
        )
    return value


def _require_krea2_assisted(
    value: Krea2AssistedService | None,
) -> Krea2AssistedService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Assisted Creation is not configured",
        )
    return value


def _require_social_lab(value: SocialLabService | None) -> SocialLabService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="Social Lab is not configured",
        )
    return value


def _require_krea2_edit(value: Krea2EditService | None) -> Krea2EditService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Edit Lab is not configured",
        )
    return value


def _require_krea2_discovery(
    value: _Krea2ModelDiscovery | None,
) -> _Krea2ModelDiscovery:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 model discovery is not configured",
        )
    return value


def _krea2_batch_stream_response(
    events: Iterator[Krea2BatchStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                }
                if event.batch is not None:
                    payload["batch"] = serialize_krea2_batch(event.batch)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {"kind": "error", "phase": "failed", "message": str(error)},
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _krea2_assisted_stream_response(
    events: Iterator[Krea2AssistedStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "error": event.error,
                }
                if event.project is not None:
                    payload["project"] = serialize_krea2_assisted_project(event.project)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {"kind": "error", "phase": "failed", "message": str(error)},
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _social_lab_stream_response(
    events: Iterator[SocialLabStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "error": event.error,
                }
                if event.project is not None:
                    payload["project"] = serialize_social_project(event.project)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {"kind": "error", "phase": "failed", "message": str(error)},
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _h3_render_stream_response(
    events: Iterator[H3RenderStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "error": event.error,
                }
                if event.project is not None:
                    payload["project"] = serialize_h3_render_project(event.project)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {"kind": "error", "phase": "failed", "message": str(error)},
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _krea2_edit_stream_response(
    events: Iterator[Krea2EditStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                }
                if event.source is not None:
                    payload["source"] = serialize_krea2_edit_source(event.source)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {"kind": "error", "phase": "failed", "message": str(error)},
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _prompt_action(action) -> dict[str, object]:
    try:
        return serialize_prompt_session(action())
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="prompt session or reference not found") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _prompt_stream_response(
    events: Iterator[PromptLabStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "finish_reason": event.finish_reason,
                    "max_tokens": event.max_tokens,
                }
                if event.session is not None:
                    payload["session"] = serialize_prompt_session(event.session)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {
                    "kind": "error",
                    "phase": "failed",
                    "message": str(error),
                },
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _composition_action(service: PromptCompositionService, action) -> dict[str, object]:
    try:
        composition = action()
        return {"composition": serialize_prompt_composition(composition, service)}
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail="prompt session, composition or cookbook not found",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _composition_stream_response(
    service: PromptCompositionService,
    events: Iterator[CompositionStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "finish_reason": event.finish_reason,
                    "max_tokens": event.max_tokens,
                    "document_stage": (
                        event.document_stage.value
                        if event.document_stage is not None
                        else None
                    ),
                }
                if event.composition is not None:
                    payload["composition"] = serialize_prompt_composition(
                        event.composition,
                        service,
                    )
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {
                    "kind": "error",
                    "phase": "failed",
                    "message": str(error),
                },
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _composition_stream_action(
    service: PromptCompositionService,
    action,
) -> StreamingResponse:
    try:
        events = action()
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail="prompt session, composition or cookbook not found",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _composition_stream_response(service, events)


def _parse_composition_stage(value: str) -> CompositionStage:
    try:
        return CompositionStage(value.replace("-", "_"))
    except ValueError as error:
        raise HTTPException(status_code=404, detail="composition stage not found") from error


def _encode_sse(event: str, payload: dict[str, object]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"
    )


def _parse_reference_uses(value: str) -> tuple[ReferenceUse, ...]:
    if not isinstance(value, str):
        raise TypeError("reference uses must be a string")
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("reference uses must not be empty")
    return tuple(ReferenceUse(part) for part in parts)


def _choice_options(control_id: str) -> list[dict[str, str]]:
    if control_id == "azimuth":
        return [
            {"value": value.value, "label": _AZIMUTH_LABELS[value]}
            for value in CameraAzimuth
        ]
    if control_id == "elevation":
        return [
            {"value": value.value, "label": _ELEVATION_LABELS[value]}
            for value in CameraElevation
        ]
    if control_id == "shot_size":
        return [
            {"value": value.value, "label": _SHOT_SIZE_LABELS[value]}
            for value in ShotSize
        ]
    return []


def _parse_seed(value: str) -> int:
    if not isinstance(value, str) or not value or not value.isdecimal():
        raise ValueError("seed must be an unsigned decimal integer")
    seed = int(value)
    if not 0 <= seed < 2**64:
        raise ValueError("seed must be between 0 and 2^64 - 1")
    return seed


def _parse_json_seed(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("seed must be an unsigned decimal integer")
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("seed must be an unsigned decimal integer")
    return _parse_seed(value)


def _get_run_or_404(runner: ChangeViewRunner, run_id: str) -> RunRecord:
    try:
        return runner.runs.get(run_id)
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="run not found") from error
