"""Web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager, nullcontext
from copy import deepcopy
from panelforge.application.h3_ref2v_conversion import H3Ref2VConversionService
from .media_analysis_web import media_analysis_router
from pathlib import Path
from typing import Any, Callable, Literal
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from .static_assets import LabAssets
from panelforge import __version__
from panelforge.application import ChangeViewRunner, H3RenderService, Krea2AssistedService, Krea2EditService, ModelRuntimeControl, PromptCompositionService, PromptLabService, SocialLabService
from .change_view_web import change_view_router
from .creation_batch_web import creation_batch_router
from .h3_render_web import H3RenderAttemptBody, h3_render_router, serialize_h3_render_project
from .krea2_assisted_web import Krea2AssistedAttemptBody, krea2_assisted_router, serialize_krea2_assisted_project
from .krea2_edit_web import krea2_edit_router
from .krea2_resources_web import krea2_resources_router
from .media_http import detect_image_media_type, media_router
from .prompt_lab_web import prompt_lab_router
from .runtime_web import runtime_router
from .social_lab_web import social_lab_router


_STATIC_DIRECTORY = Path(__file__).with_name("static")


def create_app(
    runner: ChangeViewRunner,
    *,
    prompt_lab: PromptLabService | None = None,
    prompt_composition: PromptCompositionService | None = None,
    prompt_recipes=None,
    llm_traces=None,
    h3_render: H3RenderService | None = None,
    h3_lora_resources=None,
    krea2_resources=None,
    krea2_edit: Krea2EditService | None = None,
    qwen_edit=None,
    minimax_edit=None,
    image_journeys=None,
    story_v2=None,
    cooking_recipes=None,
    krea2_assisted: Krea2AssistedService | None = None,
    creation_batch=None,
    dlss=None,
    social_lab: SocialLabService | None = None,
    media_analysis=None,
    stories=None,
    episodes=None,
    machine_work=None,
    video_factory=None,
    image_transitions=None,
    mobile_server=None,
    network_mode: Literal["lan", "tailscale"] | None = None,
    model_runtime: ModelRuntimeControl | None = None,
    llm_activity_monitor: Any | None = None,
    comfy_runtime: Any | None = None,
    local_gpu_monitor: Any | None = None,
    static_directory: Path | None = None,
    video_preview_connector: Callable[[str], Any] | None = None,
    runtime_monitor_connector: Callable[[str], Any] | None = None,
    instance_info: dict[str, Any] | None = None,
    startup_timings=None,
) -> FastAPI:
    """Create an app around injected application services."""

    if network_mode not in (None, "lan", "tailscale"):
        raise ValueError("Mode réseau inconnu.")

    static_root = (static_directory or _STATIC_DIRECTORY).resolve()

    index_path = static_root / "index.html"

    if not index_path.is_file():
        raise FileNotFoundError(index_path)

    instance_snapshot = deepcopy(instance_info) if instance_info is not None else None

    @asynccontextmanager
    async def lifespan(_app):
        starters = (
            ("thermal", machine_work, "start_temperature_sampling"),
            ("krea2", krea2_assisted, "start_render_worker"),
            ("creation_batch", creation_batch, "start_worker"),
            ("qwen", qwen_edit, "start_worker"), ("minimax", minimax_edit, "start_worker"),
            ("image_journeys", image_journeys, "start_worker"),
            ("factory", video_factory, "start"), ("story_v2", story_v2, "start_worker"),
            ("recipes", cooking_recipes, "start_worker"), ("mobile", mobile_server, "start"),
        )
        try:
            for name, service, method in starters:
                if service is not None:
                    with startup_timings.phase("startup."+name) if startup_timings else nullcontext():
                        getattr(service, method)()
        except BaseException:
            if startup_timings:
                startup_timings.finish("failed")
            raise
        if startup_timings:
            startup_timings.finish("ready")
        try:
            yield
        finally:
            if creation_batch is not None:
                await asyncio.to_thread(creation_batch.stop_worker)
            if cooking_recipes is not None:
                await asyncio.to_thread(cooking_recipes.stop_worker)
            if story_v2 is not None:
                await asyncio.to_thread(story_v2.stop_worker)
            if image_journeys is not None:
                await asyncio.to_thread(image_journeys.stop_worker)
            if mobile_server is not None:
                await asyncio.to_thread(mobile_server.stop)
            if video_factory is not None:
                await asyncio.to_thread(video_factory.stop)
            if machine_work is not None:
                await asyncio.to_thread(machine_work.stop_temperature_sampling)
            if qwen_edit is not None:
                await asyncio.to_thread(qwen_edit.stop_worker)
            if minimax_edit is not None:
                await asyncio.to_thread(minimax_edit.stop_worker)
            if krea2_assisted is not None:
                await asyncio.to_thread(krea2_assisted.stop_render_worker)

    app = FastAPI(title="PanelForge Lab", version=__version__, lifespan=lifespan)

    from .story_v2_web import story_v2_router

    app.include_router(story_v2_router(story_v2))

    from .cooking_recipes_web import cooking_recipes_router

    app.include_router(cooking_recipes_router(cooking_recipes))

    from .image_transitions_web import image_transitions_router

    app.include_router(image_transitions_router(image_transitions))

    from .video_factory_web import video_factory_router

    from .dance_web import dance_router

    app.include_router(dance_router(h3_render, serialize_h3_render_project))

    app.include_router(video_factory_router(video_factory, validate_image=detect_image_media_type))

    from .qwen_edit_web import qwen_edit_router

    app.include_router(qwen_edit_router(qwen_edit))

    from .minimax_edit_web import minimax_edit_router

    app.include_router(minimax_edit_router(minimax_edit))

    from .image_journeys_web import image_journeys_router

    app.include_router(image_journeys_router(image_journeys))

    from .prompt_recipes_web import prompt_recipes_router

    app.include_router(prompt_recipes_router(prompt_recipes, llm_traces, prompt_composition, h3_render, stories=stories))

    from .stories_web import stories_router

    app.include_router(stories_router(stories))

    from .story_library_web import story_library_router

    app.include_router(story_library_router(stories, episodes))

    from .episodes_web import episodes_router

    from .episode_thumbnails_web import episode_thumbnails_router

    app.include_router(episode_thumbnails_router(episodes))

    app.include_router(episodes_router(episodes, serialize_image_project=serialize_krea2_assisted_project,
        validate_image=detect_image_media_type, image_body=Krea2AssistedAttemptBody,
        render_body=H3RenderAttemptBody, serialize_render_project=serialize_h3_render_project))

    from .image_catalog import ImageLabCatalogs

    image_catalogs = ImageLabCatalogs()

    app.include_router(media_analysis_router(media_analysis))

    h3_conversion = H3Ref2VConversionService(h3_render) if h3_render is not None else None

    from .dlss_web import register_dlss_routes

    register_dlss_routes(app, dlss)

    assets = LabAssets(static_root)
    app.mount("/static", assets, name="static")

    @app.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        return assets.index()

    @app.get("/api/instance")
    def instance_identity(response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return {**(instance_snapshot or {}), "available": instance_snapshot is not None}

    @app.get("/api/network-mode")
    def network_configuration() -> dict[str, str | None]:
        # Configuration only: no credentials, network probes, or availability claim.
        return {"mode": network_mode, "label": {"lan": "Local", "tailscale": "Tailscale"}.get(network_mode)}

    app.include_router(runtime_router(comfy_runtime=comfy_runtime, h3_render=h3_render, llm_activity_monitor=llm_activity_monitor, local_gpu_monitor=local_gpu_monitor, machine_work=machine_work, model_runtime=model_runtime, runtime_monitor_connector=runtime_monitor_connector))

    app.include_router(change_view_router(runner=runner))

    app.include_router(media_router(runner=runner))

    app.include_router(social_lab_router(social_lab=social_lab))

    app.include_router(krea2_resources_router(krea2_resources=krea2_resources))

    app.include_router(krea2_assisted_router(image_catalogs=image_catalogs, krea2_assisted=krea2_assisted, krea2_edit=krea2_edit, runner=runner))
    app.include_router(creation_batch_router(creation_batch))

    app.include_router(krea2_edit_router(image_catalogs=image_catalogs, krea2_edit=krea2_edit, krea2_resources=krea2_resources, runner=runner))

    app.include_router(h3_render_router(h3_conversion=h3_conversion, h3_lora_resources=h3_lora_resources, h3_render=h3_render, machine_work=machine_work, video_preview_connector=video_preview_connector))

    app.include_router(prompt_lab_router(prompt_composition=prompt_composition, prompt_lab=prompt_lab))

    return app
