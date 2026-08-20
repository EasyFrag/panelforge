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
from pydantic import BaseModel

from panelforge.application import (
    ChangeViewRunRequest,
    ChangeViewRunner,
    CompositionStreamEvent,
    Krea2LabRunRequest,
    Krea2LabRunner,
    ModelRuntimeControl,
    NewReference,
    PromptCompositionService,
    PromptLabService,
    PromptLabStreamEvent,
    StoryboardLabService,
    StoryboardRunRequest,
    StoryboardStreamEvent,
    SUPER_FAST_REF2V_COOKBOOK_ID,
    SUPER_FAST_REF2V_COOKBOOK_VERSION,
    VideoLabRunRequest,
    VideoLabRunner,
    composition_picture_mapping,
)
from panelforge.domain import (
    CompositionStage,
    ControlKind,
    CookbookBinding,
    Krea2AspectRatio,
    Krea2LabRun,
    PromptComposition,
    PromptLabSession,
    ReferenceEvidencePolicy,
    ReferenceUse,
    RunRecord,
    RunReview,
    StoryboardRun,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabSettings,
    normalize_krea2_model_name,
    storyboard_layout,
)
from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)
from panelforge.infrastructure.comfy import ComfyBusyError


MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_PROMPT_REFERENCES = 8
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


class ReferenceUsesBody(BaseModel):
    uses: list[str]


class BriefStructureBody(BaseModel):
    source_text: str
    creative_freedom: int


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
    creative_freedom: int


class StoryboardCreateBody(BaseModel):
    source_text: str
    panel_count: int
    model_id: str


class Krea2CreateBody(BaseModel):
    prompt: str
    preset_id: str = "krea2-base"
    model_id: str | None = None
    aspect_ratio: str | None = None
    megapixels: float | None = None
    seed: str | int | None = None
    seed_locked: bool = False
    source_storyboard_run_id: str | None = None
    source_prompt_sha256: str | None = None


_STORYBOARD_RECIPE_ID = "krea2.storyboard.from_text"
_STORYBOARD_RECIPE_VERSION = "0.1.0"


def create_app(
    runner: ChangeViewRunner,
    *,
    prompt_lab: PromptLabService | None = None,
    prompt_composition: PromptCompositionService | None = None,
    video_lab: VideoLabRunner | None = None,
    storyboard_lab: StoryboardLabService | None = None,
    krea2_lab: Krea2LabRunner | None = None,
    model_runtime: ModelRuntimeControl | None = None,
    comfy_runtime: Any | None = None,
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

    @app.get("/api/storyboard-lab/spec")
    def storyboard_lab_spec() -> dict[str, object]:
        service = _require_storyboard_lab(storyboard_lab)
        recipe = _storyboard_recipe(service)
        return {
            "recipe": {
                "id": recipe.recipe_id,
                "version": recipe.version,
                "display_name": recipe.display_name,
                "description": recipe.description,
                "template_sha256": recipe.template_sha256,
            },
            "panel_options": [
                {
                    "panel_count": layout.panel_count,
                    "columns": layout.columns,
                    "rows": layout.rows,
                    "page_aspect_ratio": layout.page_aspect_ratio,
                    "page_orientation": layout.page_orientation,
                    "panel_aspect_ratio": "2:3",
                }
                for layout in (
                    storyboard_layout(panel_count)
                    for panel_count in recipe.panel_counts
                )
            ],
            "models": [
                {"id": model.model_id}
                for model in service.list_models()
            ],
        }

    @app.post("/api/storyboard-lab/runs", status_code=status.HTTP_201_CREATED)
    def create_storyboard_run(body: StoryboardCreateBody) -> dict[str, object]:
        service = _require_storyboard_lab(storyboard_lab)
        recipe = _storyboard_recipe(service)
        try:
            run = service.prepare(
                StoryboardRunRequest(
                    intention=body.source_text,
                    panel_count=body.panel_count,
                    model_id=body.model_id,
                    recipe_id=recipe.recipe_id,
                    recipe_version=recipe.version,
                )
            )
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"run": serialize_storyboard_run(run)}

    @app.get("/api/storyboard-lab/runs")
    def list_storyboard_runs(limit: int = 30) -> dict[str, object]:
        service = _require_storyboard_lab(storyboard_lab)
        try:
            return {
                "runs": [
                    serialize_storyboard_run(run)
                    for run in service.list(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/storyboard-lab/runs/{run_id}")
    def get_storyboard_run(run_id: str) -> dict[str, object]:
        service = _require_storyboard_lab(storyboard_lab)
        try:
            return {"run": serialize_storyboard_run(service.get(run_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="storyboard run not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/storyboard-lab/runs/{run_id}/generate/stream")
    def stream_storyboard_run(
        run_id: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_storyboard_lab(storyboard_lab)
        return _storyboard_stream_response(
            service.stream_generate(
                run_id,
                include_reasoning=include_reasoning,
            )
        )

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
        return _runtime_status(model_runtime=model_runtime, comfy_runtime=comfy_runtime)

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
            source_prompt_sha256: str | None = None
            if body.source_storyboard_run_id is not None:
                source_service = _require_storyboard_lab(storyboard_lab)
                try:
                    source_service.get(body.source_storyboard_run_id)
                except (KeyError, FileNotFoundError) as error:
                    raise HTTPException(
                        status_code=404,
                        detail="Storyboard source run not found",
                    ) from error
                source_prompt_sha256 = hashlib.sha256(
                    body.prompt.encode("utf-8")
                ).hexdigest()
            elif body.source_prompt_sha256 is not None:
                raise ValueError(
                    "source_prompt_sha256 requires source_storyboard_run_id"
                )
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
                    source_storyboard_run_id=body.source_storyboard_run_id,
                    source_prompt_sha256=source_prompt_sha256,
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
            "megapixels": [0.3, 0.6, 1.0],
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
                {"id": model.model_id}
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

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze"
    )
    def analyze_prompt_reference(session_id: str, reference_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.analyze_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze/stream"
    )
    def stream_prompt_reference_analysis(
        session_id: str,
        reference_id: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_analyze_reference(
                session_id,
                reference_id,
                include_reasoning=include_reasoning,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/edit"
    )
    def edit_prompt_reference(
        session_id: str,
        reference_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.edit_reference(session_id, reference_id, body.content)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/revise"
    )
    def revise_prompt_reference(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_reference(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/revise/stream"
    )
    def stream_prompt_reference_revision(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_reference(
                session_id,
                reference_id,
                body.instruction,
                include_reasoning=include_reasoning,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/approve"
    )
    def approve_prompt_reference(session_id: str, reference_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.approve_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/uses"
    )
    def set_prompt_reference_uses(
        session_id: str,
        reference_id: str,
        body: ReferenceUsesBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.set_reference_uses(
                session_id,
                reference_id,
                tuple(ReferenceUse(value) for value in body.uses),
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpret"
    )
    def interpret_prompt_reference(
        session_id: str,
        reference_id: str,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.interpret_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpret/stream"
    )
    def stream_prompt_reference_interpretation(
        session_id: str,
        reference_id: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_interpret_reference(
                session_id,
                reference_id,
                include_reasoning=include_reasoning,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/edit"
    )
    def edit_prompt_interpretation(
        session_id: str,
        reference_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.edit_interpretation(
                session_id,
                reference_id,
                body.content,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/revise"
    )
    def revise_prompt_interpretation(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_interpretation(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/revise/stream"
    )
    def stream_prompt_interpretation_revision(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_interpretation(
                session_id,
                reference_id,
                body.instruction,
                include_reasoning=include_reasoning,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/approve"
    )
    def approve_prompt_interpretation(
        session_id: str,
        reference_id: str,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.approve_interpretation(session_id, reference_id)
        )

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
                or source_session.profile_version != "0.1.0"
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


def _runtime_status(*, model_runtime: Any | None, comfy_runtime: Any | None) -> dict[str, object]:
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
    return {
        "observed_at": observed_at,
        "gpu": gpu,
        "comfy": comfy,
        "llm": llm,
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


def serialize_storyboard_run(run: StoryboardRun) -> dict[str, object]:
    layout = storyboard_layout(run.panel_count)
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "source_text": run.intention,
        "intention": run.intention,
        "panel_count": run.panel_count,
        "model_id": run.model_id,
        "recipe": {
            "id": run.recipe_id,
            "version": run.recipe_version,
            "template_sha256": run.template_sha256,
        },
        "recipe_id": run.recipe_id,
        "recipe_version": run.recipe_version,
        "template_sha256": run.template_sha256,
        "layout": {
            "panel_count": layout.panel_count,
            "columns": layout.columns,
            "rows": layout.rows,
            "page_aspect_ratio": layout.page_aspect_ratio,
            "page_orientation": layout.page_orientation,
            "panel_aspect_ratio": "2:3",
        },
        "status": run.status.value,
        "raw_response": run.raw_response,
        "spec": run.spec.to_payload() if run.spec is not None else None,
        "compiled_prompt": run.compiled_prompt,
        "warnings": list(run.warnings),
        "error": run.error,
    }


def serialize_prompt_session(session: PromptLabSession) -> dict[str, object]:
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
        raise HTTPException(status_code=503, detail="Prompt Lab is not configured")
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


def _require_krea2_discovery(
    value: _Krea2ModelDiscovery | None,
) -> _Krea2ModelDiscovery:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 model discovery is not configured",
        )
    return value


def _require_storyboard_lab(
    value: StoryboardLabService | None,
) -> StoryboardLabService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="Storyboard Lab is not configured",
        )
    return value


def _storyboard_recipe(service: StoryboardLabService):
    try:
        return service.get_recipe(
            _STORYBOARD_RECIPE_ID,
            _STORYBOARD_RECIPE_VERSION,
        )
    except KeyError as error:
        raise HTTPException(
            status_code=503,
            detail="The current Storyboard recipe is not installed",
        ) from error


def _storyboard_stream_response(
    events: Iterator[StoryboardStreamEvent],
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
                if event.run is not None:
                    payload["run"] = serialize_storyboard_run(event.run)
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
