"""Launch the local PanelForge Lab against one ComfyUI server."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.application.media_analysis import MediaAnalysisService
from panelforge.application.stories import StoryService
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore
from panelforge.infrastructure.storage.media_analysis import LocalMediaAnalysisStore
from panelforge.infrastructure.media_analysis_images import MediaAnalysisImages
from panelforge.application.media_transcription import MediaTranscriptionService
from panelforge.infrastructure.media_transcription import PurfviewTranscriber
from panelforge.infrastructure.presets.h3_checkpoint import CheckpointH3RenderRecipe
from panelforge.infrastructure.presets.h3_loras import MultiLoraH3RenderRecipe
from panelforge.application.h3_checkpoints import CachedH3Checkpoints

from panelforge.application import (
    ChangeViewRunner,
    H3RenderService,
    Krea2AssistedService,
    Krea2BatchService,
    Krea2EditService,
    Krea2LabRunner,
    PromptCompositionService,
    PromptLabService,
    ProductionService,
    ProductionV2Service,
    MachineWorkCoordinator,
    SocialLabService,
    VideoLabRunner,
)
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.comfy import ComfyHttpClient
from panelforge.infrastructure.llm import (
    LlamaSwapAdminClient,
    LoggedMultimodalGateway,
    OpenAICompatibleGateway,
    RoutedMultimodalGateway,
    CoordinatedMultimodalGateway,
)
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    Krea2T2IRecipe,
    VideoLabPresetRecipe,
    Ref2VH3RenderPresetRecipe,
    H3RenderPresetRecipe,
    load_change_view_preset,
    load_krea2_batch_workflow,
    load_krea2_edit_workflow,
    load_krea2_t2i_workflow,
    load_video_lab_workflow,
    load_h3_render_workflow,
)
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage.prompt_recipes import LocalPromptRecipeStore
from panelforge.infrastructure.storage.llm_traces import LocalLlmTraceStore
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.presets.krea2_assisted import load_krea2_assisted_workflow
from panelforge.infrastructure.presets.krea2_flux_klein import load_krea2_flux_klein_workflow
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.krea2_retouch import PillowRetouchCompositor
from panelforge.infrastructure.krea2_upscale import PillowUpscaleImages
from panelforge.application.dlss import DlssService
from panelforge.application.dlss_candidates import DlssCandidates
from panelforge.infrastructure.dlss_runtime import LocalDlssRuntime
from panelforge.infrastructure.dlss_media import DlssMedia
from panelforge.infrastructure.dlss_outputs import DlssOutputs
from panelforge.infrastructure.dlss_progress import ComfyDlssProgress
from panelforge.infrastructure.dlss_video_exports import DlssVideoExporter
from panelforge.infrastructure.storage.dlss_jobs import LocalDlssJobs
from panelforge.infrastructure.presets.dlss import DlssWorkflow
from panelforge.infrastructure.presets.image_upscale import load_image_upscale_workflow
from panelforge.infrastructure.presets.firered_edit import load_firered_edit_workflow
from panelforge.infrastructure.edit_images import PillowEditImages
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.h3_lora_resources import H3LoraResourceCatalog
from panelforge.infrastructure.local_gpu import NvidiaSmiMonitor
from panelforge.infrastructure.production_thermal import (
    CombinedProductionThermalMonitor,
    CrystoolsRemoteGpuMonitor,
)
from panelforge.infrastructure.storage.krea2_style_presets import LocalKrea2StylePresetStore
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalH3RenderProjectStore,
    LocalKrea2AssistedProjectStore,
    LocalLlmCallStore,
    LocalKrea2BatchStore,
    LocalKrea2EditStore,
    LocalKrea2RunStore,
    LocalPromptSessionStore,
    LocalPromptCompositionStore,
    LocalProductionLoraMemory,
    LocalProductionJobStore,
    LocalProductionV2Store,
    LocalRunStore,
    LocalSocialLabStore,
    LocalVideoRunStore,
)


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.3.0"
)
BUNNY_RENDER_WORKFLOW_DIRECTORY = PROJECT_ROOT / "workflows" / "video.generate.h3-base" / "minimax-h3-bunny" / "0.1.3"
VIDEO_PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.2.1"
)
REF2V_RENDER_WORKFLOW_DIRECTORY = VIDEO_PRESET_DIRECTORY.parent / "0.2.5"
HISTORICAL_REF2V_DIRECTORY = VIDEO_PRESET_DIRECTORY.parent / "0.2.0"
KREA2_PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "image.generate.t2i"
    / "krea2"
    / "0.1.0"
)
H3_RENDER_WORKFLOW_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "video.generate.h3-base"
    / "minimax-h3-latent-speed"
    / "0.1.7"
)
KREA2_BATCH_WORKFLOW_DIRECTORY = (
    PROJECT_ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"
)
KREA2_BATCH_RECIPE_DIRECTORY = PROJECT_ROOT / "krea2_batch_recipes"
KREA2_EDIT_WORKFLOW_DIRECTORY = (
    PROJECT_ROOT / "workflows" / "image.edit" / "krea2-identity" / "0.2.0"
)
KREA2_EDIT_HISTORICAL_WORKFLOW_DIRECTORY = KREA2_EDIT_WORKFLOW_DIRECTORY.parent / "0.1.0"
DEFAULT_KREA2_MODELS_ROOT = Path(
    r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion_models\Krea2"
)
DEFAULT_KREA2_LORAS_ROOT = Path(
    r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PanelForge Lab.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get(
            "PANELFORGE_COMFY_URL",
            "http://192.168.1.72:8188",
        ),
        help="ComfyUI base URL (default: %(default)s)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--http-timeout", type=float, default=30.0)
    parser.add_argument("--runtime-timeout", type=float, default=2.0)
    parser.add_argument("--run-timeout", type=float, default=600.0)
    parser.add_argument("--video-run-timeout", type=float, default=3600.0)
    parser.add_argument("--h3-render-run-timeout", type=float, default=3600.0)
    parser.add_argument("--krea2-run-timeout", type=float, default=3600.0)
    parser.add_argument("--krea2-batch-run-timeout", type=float, default=3600.0)
    parser.add_argument("--krea2-edit-run-timeout", type=float, default=3600.0)
    parser.add_argument("--krea2-assisted-run-timeout", type=float, default=3600.0)
    parser.add_argument(
        "--krea2-models-root",
        type=Path,
        default=Path(os.environ.get(
            "PANELFORGE_KREA2_MODELS_ROOT",
            str(DEFAULT_KREA2_MODELS_ROOT),
        )),
    )
    parser.add_argument(
        "--krea2-loras-root",
        type=Path,
        default=Path(os.environ.get(
            "PANELFORGE_KREA2_LORAS_ROOT",
            str(DEFAULT_KREA2_LORAS_ROOT),
        )),
    )
    parser.add_argument(
        "--krea2-projects-root",
        type=Path,
        default=Path(os.environ.get(
            "PANELFORGE_KREA2_PROJECTS_ROOT",
            r"D:\AI\PanelForge\KREA2 Projects",
        )),
        help="Human-readable KREA2 validated-project exports (default: %(default)s)",
    )
    parser.add_argument(
        "--krea2-creations-root",
        type=Path,
        default=Path(os.environ.get(
            "PANELFORGE_KREA2_CREATIONS_ROOT",
            r"D:\AI\PanelForge\KREA2 Creations",
        )),
        help="Human-readable assisted KREA2 image exports (default: %(default)s)",
    )
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument(
        "--llm-base-url",
        default=os.environ.get(
            "PANELFORGE_LLM_URL",
            "http://bucket:8083/v1",
        ),
        help="OpenAI-compatible llama.swap URL (default: %(default)s)",
    )
    parser.add_argument(
        "--llm-api-key",
        default=os.environ.get("PANELFORGE_LLM_API_KEY", "panelforge-local"),
        help="API key sent to the local OpenAI-compatible server",
    )
    parser.add_argument("--llm-timeout", type=float, default=300.0)
    parser.add_argument(
        "--local-llm-base-url",
        default=os.environ.get(
            "PANELFORGE_LOCAL_LLM_URL",
            "http://127.0.0.1:8888/v1",
        ),
        help="Local Unsloth Studio OpenAI-compatible URL (default: %(default)s)",
    )
    parser.add_argument(
        "--local-llm-api-key",
        default=os.environ.get("PANELFORGE_LOCAL_LLM_API_KEY", ""),
        help="Unsloth Studio API key; prefer PANELFORGE_LOCAL_LLM_API_KEY",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=PROJECT_ROOT / "workspace",
    )
    parser.add_argument("--dlss-root", type=Path, default=Path(r"D:\AI\ComfyUI_windows_portable"))
    parser.add_argument("--dlss-base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--dlss-output-root", type=Path, default=Path(r"D:\AI\PanelForge\LocalOutput"))
    parser.add_argument("--dlss-video-export-root", type=Path, default=Path(r"X:\data\ComfyUI\output\video\Upscale"))
    return parser.parse_args()


def build_app(args: argparse.Namespace):
    recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
    video_recipe = VideoLabPresetRecipe(
        load_video_lab_workflow(VIDEO_PRESET_DIRECTORY)
    )
    ref2v_render_recipe = MultiLoraH3RenderRecipe(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(
        load_video_lab_workflow(REF2V_RENDER_WORKFLOW_DIRECTORY))), REF2V_RENDER_WORKFLOW_DIRECTORY)
    h3_render_recipe = MultiLoraH3RenderRecipe(H3RenderPresetRecipe(
        load_h3_render_workflow(H3_RENDER_WORKFLOW_DIRECTORY)
    ), H3_RENDER_WORKFLOW_DIRECTORY)
    krea2_recipe = Krea2T2IRecipe(
        load_krea2_t2i_workflow(KREA2_PRESET_DIRECTORY)
    )
    krea2_batch_workflow = load_krea2_batch_workflow(KREA2_BATCH_WORKFLOW_DIRECTORY)
    krea2_edit_workflow = load_krea2_edit_workflow(KREA2_EDIT_WORKFLOW_DIRECTORY)
    dlss_root = Path(getattr(args, "dlss_root", r"D:\AI\ComfyUI_windows_portable"))
    dlss_output_root = Path(getattr(args, "dlss_output_root", r"D:\AI\PanelForge\LocalOutput"))
    dlss_fallback_roots = (dlss_root / "ComfyUI/output",)
    assets = LocalAssetStore(args.workspace, external_roots=(dlss_output_root, *dlss_fallback_roots))
    runs = LocalRunStore(args.workspace)
    video_runs = LocalVideoRunStore(args.workspace)
    h3_render_projects = LocalH3RenderProjectStore(args.workspace)
    social_projects = LocalSocialLabStore(args.workspace)
    krea2_runs = LocalKrea2RunStore(args.workspace)
    krea2_batches = LocalKrea2BatchStore(args.workspace)
    krea2_assisted_projects = LocalKrea2AssistedProjectStore(args.workspace)
    krea2_edits = LocalKrea2EditStore(args.workspace)
    prompt_sessions = LocalPromptSessionStore(args.workspace)
    prompt_compositions = LocalPromptCompositionStore(args.workspace)
    llm_calls = LocalLlmCallStore(args.workspace, capacity=20)
    llm_traces = LocalLlmTraceStore(args.workspace)
    production_jobs = LocalProductionJobStore(args.workspace)
    production_v2_store = LocalProductionV2Store(args.workspace)
    comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-lab-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    video_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-video-lab-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    krea2_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-krea2-lab-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    h3_render_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-h3-render-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    krea2_batch_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-krea2-batch-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    krea2_edit_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-krea2-edit-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    krea2_assisted_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-krea2-assisted-{uuid4().hex}",
        timeout=args.http_timeout,
    )
    runtime_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-runtime-{uuid4().hex}",
        timeout=args.runtime_timeout,
    )
    production_monitor_comfy = ComfyHttpClient(
        args.base_url,
        client_id=f"panelforge-production-monitor-{uuid4().hex}",
        timeout=args.runtime_timeout,
    )
    local_gpu_monitor = NvidiaSmiMonitor()
    production_thermal_monitor = CombinedProductionThermalMonitor(
        local=local_gpu_monitor,
        remote=CrystoolsRemoteGpuMonitor(production_monitor_comfy.websocket_url),
    )
    machine_work = MachineWorkCoordinator(
        thermal_monitor=production_thermal_monitor,
        monitor_interval=max(0.2, args.poll_interval),
    )
    runner = ChangeViewRunner(
        recipe=recipe,
        comfy=comfy,
        assets=assets,
        runs=runs,
        run_timeout=args.run_timeout,
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    video_lab = VideoLabRunner(
        recipe=video_recipe,
        comfy=video_comfy,
        assets=assets,
        runs=video_runs,
        run_timeout=args.video_run_timeout,
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    krea2_lab = Krea2LabRunner(
        recipe=krea2_recipe,
        comfy=krea2_comfy,
        assets=assets,
        runs=krea2_runs,
        run_timeout=args.krea2_run_timeout,
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    routed_gateway = RoutedMultimodalGateway(
        {
            "server": OpenAICompatibleGateway(
                args.llm_base_url,
                api_key=args.llm_api_key,
                timeout=args.llm_timeout,
            ),
            "local": OpenAICompatibleGateway(
                getattr(
                    args,
                    "local_llm_base_url",
                    "http://127.0.0.1:8888/v1",
                ),
                api_key=(
                    getattr(args, "local_llm_api_key", "")
                    or "panelforge-local-unconfigured"
                ),
                timeout=args.llm_timeout,
            ),
        }
    )
    gateway = LoggedMultimodalGateway(
        CoordinatedMultimodalGateway(routed_gateway, machine_work),
        llm_calls,
        trace_store=llm_traces,
    )
    krea2_resources = LocalKrea2ResourceCatalog(
        models_root=getattr(
            args,
            "krea2_models_root",
            DEFAULT_KREA2_MODELS_ROOT,
        ),
        loras_root=getattr(
            args,
            "krea2_loras_root",
            DEFAULT_KREA2_LORAS_ROOT,
        ),
        workspace_root=args.workspace,
        comfy=krea2_batch_comfy,
    )
    krea2_visual_recipes = LocalKrea2VisualRecipeCatalog(
        KREA2_BATCH_RECIPE_DIRECTORY,
        workspace_root=args.workspace,
    )
    krea2_batch = Krea2BatchService(
        gateway=gateway,
        recipes=krea2_visual_recipes,
        workflow=krea2_batch_workflow,
        comfy=krea2_batch_comfy,
        assets=assets,
        batches=krea2_batches,
        resources=krea2_resources,
        application_outcomes=gateway,
        run_timeout=getattr(args, "krea2_batch_run_timeout", 3600.0),
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    krea2_assisted_default_workflow = load_krea2_assisted_workflow(
        PROJECT_ROOT / "workflows" / "image.generate.assisted" / "krea2-sampling" / "1.0.0",
        krea2_batch_workflow,
    )
    krea2_assisted_flux_workflow = load_krea2_flux_klein_workflow(
        PROJECT_ROOT / "workflows" / "image.generate.assisted" / "krea2-flux-klein" / "1.0.0",
    )
    krea2_assisted = Krea2AssistedService(
        gateway=gateway,
        presets=LocalKrea2StylePresetStore(args.workspace),
        recipes=krea2_visual_recipes,
        workflow=krea2_assisted_default_workflow,
        workflows=(krea2_assisted_default_workflow, krea2_assisted_flux_workflow),
        comfy=krea2_assisted_comfy,
        assets=assets,
        projects=krea2_assisted_projects,
        resources=krea2_resources,
        exporter=LocalKrea2CreationExporter(
            getattr(
                args,
                "krea2_creations_root",
                Path(r"D:\AI\PanelForge\KREA2 Creations"),
            )
        ),
        application_outcomes=gateway,
        run_timeout=getattr(args, "krea2_assisted_run_timeout", 3600.0),
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    krea2_edit = Krea2EditService(
        retouch_compositor=PillowRetouchCompositor(),
        upscale_images=PillowUpscaleImages(),
        edit_images=PillowEditImages(),
        upscale_workflow=load_image_upscale_workflow(PROJECT_ROOT / "workflows/image.upscale/esrgan/0.1.0"),
        gateway=gateway,
        workflow=krea2_edit_workflow,
        historical_workflows=(load_krea2_edit_workflow(KREA2_EDIT_HISTORICAL_WORKFLOW_DIRECTORY),
                              load_krea2_edit_workflow(KREA2_EDIT_WORKFLOW_DIRECTORY.parent / "0.3.0"),
                              load_firered_edit_workflow(PROJECT_ROOT / "workflows/image.edit/firered/0.1.0")),
        comfy=krea2_edit_comfy,
        assets=assets,
        sources=krea2_edits,
        batches=krea2_batch,
        project_exporter=LocalKrea2ProjectExporter(
            getattr(
                args,
                "krea2_projects_root",
                Path(r"D:\AI\PanelForge\KREA2 Projects"),
            )
        ),
        application_outcomes=gateway,
        run_timeout=getattr(args, "krea2_edit_run_timeout", 3600.0),
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    prompt_lab = PromptLabService(
        gateway=gateway,
        profiles=LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles"),
        assets=assets,
        sessions=prompt_sessions,
    )
    from panelforge.application.prompt_recipes import EDITABLE_RECIPES
    from panelforge.application.classic_cinematic import REVISION_SYSTEM as classic_render_system
    from panelforge.application.sensual_cinematic import REVISION_SYSTEM as sensual_render_system
    combat_render_system = load_combat_revision_policy(PROJECT_ROOT / "prompt_cookbooks" / "_blocks", "1.3.0").system_prompt
    cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
    prompt_recipes = LocalPromptRecipeStore(args.workspace, cookbooks, PROJECT_ROOT / "prompt_sources" / "_defaults",
        render_systems={(key, version): classic_render_system if ".classic." in key else
            combat_render_system if ".combat." in key else sensual_render_system
            for key, version, _ in EDITABLE_RECIPES})
    prompt_composition = PromptCompositionService(
        gateway=gateway,
        cookbooks=cookbooks,
        prompt_recipes=prompt_recipes,
        sessions=prompt_sessions,
        compositions=prompt_compositions,
        application_outcomes=gateway,
        assets=assets,
    )
    h3_render = H3RenderService(
        prompt_recipes=prompt_recipes,
        llm_traces=llm_traces,
        combat_revision_policies=tuple(load_combat_revision_policy(PROJECT_ROOT / "prompt_cookbooks" / "_blocks", version)
                                      for version in ("1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.3.0")),
        gateway=gateway,
        workflow=h3_render_recipe,
        ref2v_workflow=ref2v_render_recipe,
        additional_workflows=(
            MultiLoraH3RenderRecipe(BunnyH3RenderRecipe(BUNNY_RENDER_WORKFLOW_DIRECTORY), BUNNY_RENDER_WORKFLOW_DIRECTORY),
            MultiLoraH3RenderRecipe(BunnyH3RenderRecipe(BUNNY_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.2"), BUNNY_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.2"),
            CheckpointH3RenderRecipe(BunnyH3RenderRecipe(BUNNY_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.1"), BUNNY_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.1"),
            BunnyH3RenderRecipe(BUNNY_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.0"),
        ),
        historical_h3_workflows=(
            MultiLoraH3RenderRecipe(H3RenderPresetRecipe(load_h3_render_workflow(H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.6")), H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.6"),
            MultiLoraH3RenderRecipe(H3RenderPresetRecipe(load_h3_render_workflow(H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.5")), H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.5"),
            CheckpointH3RenderRecipe(H3RenderPresetRecipe(load_h3_render_workflow(H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.4")), H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.4"),
            H3RenderPresetRecipe(load_h3_render_workflow(H3_RENDER_WORKFLOW_DIRECTORY.parent / "0.1.3")),
        ),
        historical_ref2v_workflows=(
            MultiLoraH3RenderRecipe(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(REF2V_RENDER_WORKFLOW_DIRECTORY.parent / "0.2.4"))), REF2V_RENDER_WORKFLOW_DIRECTORY.parent / "0.2.4"),
            MultiLoraH3RenderRecipe(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(REF2V_RENDER_WORKFLOW_DIRECTORY.parent / "0.2.3"))), REF2V_RENDER_WORKFLOW_DIRECTORY.parent / "0.2.3"),
            CheckpointH3RenderRecipe(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(VIDEO_PRESET_DIRECTORY.parent / "0.2.2"))), VIDEO_PRESET_DIRECTORY.parent / "0.2.2"),
            *(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(VIDEO_PRESET_DIRECTORY.parent / version)))
              for version in ("0.2.1", "0.2.0")),
        ),
        list_video_loras=runtime_comfy.list_lora_models,
        checkpoints=CachedH3Checkpoints(runtime_comfy.list_unet_models, tuple(json.loads(
            (SRC_ROOT / "panelforge/infrastructure/presets/h3_checkpoints.json").read_text(encoding="utf-8")))),
        comfy=h3_render_comfy,
        assets=assets,
        projects=h3_render_projects,
        sessions=prompt_sessions,
        compositions=prompt_compositions,
        application_outcomes=gateway,
        run_timeout=getattr(args, "h3_render_run_timeout", 3600.0),
        poll_interval=args.poll_interval,
        work_coordinator=machine_work,
    )
    def resolve_social_source_prompt(video_asset):
        for project in h3_render_projects.list(10_000):
            for attempt in reversed(project.attempts):
                if attempt.output_asset_id is None:
                    continue
                try:
                    candidate = assets.get(attempt.output_asset_id)
                except (KeyError, FileNotFoundError, ValueError):
                    continue
                if candidate.content_sha256 == video_asset.content_sha256:
                    return attempt.effective_prompt
        for run in video_runs.list(10_000):
            if run.output_asset_id is None:
                continue
            try:
                candidate = assets.get(run.output_asset_id)
            except (KeyError, FileNotFoundError, ValueError):
                continue
            if candidate.content_sha256 == video_asset.content_sha256:
                return run.prompt
        return None

    social_lab = SocialLabService(
        gateway=gateway,
        assets=assets,
        projects=social_projects,
        application_outcomes=gateway,
        source_prompt_resolver=resolve_social_source_prompt,
    )
    whisper_root = Path(os.environ.get("PANELFORGE_WHISPER_ROOT") or
        str(Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "Subtitle Edit/SpeechToText/Purfview-Faster-Whisper-XXL"))
    media_analysis = MediaAnalysisService(
        gateway=gateway, assets=assets, store=LocalMediaAnalysisStore(args.workspace),
        images=MediaAnalysisImages(), application_outcomes=gateway,
        prompt_directory=PROJECT_ROOT / "prompt_profiles/media.analyze/visual-intention/1.0.1",
        speech_prompt_directory=PROJECT_ROOT / "prompt_profiles/media.analyze/visual-intention/1.1.1",
        transcription=MediaTranscriptionService(PurfviewTranscriber(
            executable=whisper_root / "faster-whisper-xxl.exe",
            ffmpeg=whisper_root / "ffmpeg.exe", model_directory=whisper_root / "_models")),
    )
    stories = StoryService(gateway=gateway, store=LocalStoryStore(args.workspace),
        recipes=LocalStoryRecipeStore(args.workspace, {
            ("story.brainrot", "1.0.0"): PROJECT_ROOT / "prompt_sources/story.brainrot/1.0.0",
            ("story.sensual-light", "1.0.0"): PROJECT_ROOT / "prompt_sources/story.sensual-light/1.0.0",
            ("story.explicit-hard", "1.0.0"): PROJECT_ROOT / "prompt_sources/story.explicit-hard/1.0.0",
            ("story.silent-cats", "1.0.0"): PROJECT_ROOT / "prompt_sources/story.silent-cats/1.0.0",
        }),
        traces=llm_traces, application_outcomes=gateway)
    from panelforge.application.episodes import EpisodeService
    from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
    episodes = EpisodeService(stories=stories, store=LocalEpisodeStore(args.workspace),
        krea=krea2_assisted, prompt_lab=prompt_lab, composition=prompt_composition,
        render=h3_render, assets=assets, work_coordinator=machine_work)
    production_lora_memory = LocalProductionLoraMemory(args.workspace)
    production = ProductionService(
        gateway=gateway,
        assets=assets,
        jobs=production_jobs,
        krea2=krea2_assisted,
        prompt_lab=prompt_lab,
        composition=prompt_composition,
        h3_render=h3_render,
        thermal_monitor=production_thermal_monitor,
        lora_resources=krea2_resources,
        lora_memory=production_lora_memory,
    )
    production_v2 = ProductionV2Service(
        assets=assets,
        store=production_v2_store,
        krea2=krea2_assisted,
        prompt_lab=prompt_lab,
        composition=prompt_composition,
        h3_render=h3_render,
        thermal_monitor=production_thermal_monitor,
        gateway=gateway,
        lora_resources=krea2_resources,
        lora_memory=production_lora_memory,
    )
    dlss_url = getattr(args, "dlss_base_url", "http://127.0.0.1:8188")
    dlss_jobs = LocalDlssJobs(args.workspace)
    dlss_comfy = ComfyHttpClient(dlss_url, client_id="panelforge-dlss", timeout=30)
    dlss = DlssService(
        jobs=dlss_jobs, comfy=dlss_comfy, assets=assets,
        progress=ComfyDlssProgress(dlss_comfy.websocket_url),
        video_exporter=DlssVideoExporter(getattr(args, "dlss_video_export_root", r"X:\data\ComfyUI\output\video\Upscale")),
        outputs=DlssOutputs(dlss_output_root, assets, fallback_roots=dlss_fallback_roots),
        runtime=LocalDlssRuntime(root=dlss_root, base_url=dlss_url, journal=dlss_jobs, comfy=dlss_comfy, output_root=dlss_output_root),
        media=DlssMedia(ffmpeg=dlss_root / "tools/ffmpeg.exe", ffprobe=dlss_root / "tools/ffprobe.exe"),
        candidates=DlssCandidates(edit=krea2_edit, assisted=krea2_assisted, h3=h3_render),
        workflows={
            "image": DlssWorkflow(PROJECT_ROOT / "workflows/image.upscale/dlss/0.1.0"),
            "video": DlssWorkflow(PROJECT_ROOT / "workflows/video.upscale/dlss/0.1.0"),
            "video-smooth": DlssWorkflow(PROJECT_ROOT / "workflows/video.upscale/dlss-smooth/0.1.0"),
        },
        work_coordinator=machine_work,
    )
    return create_app(
        runner,
        prompt_recipes=prompt_recipes,
        llm_traces=llm_traces,
        dlss=dlss,
        prompt_lab=prompt_lab,
        prompt_composition=prompt_composition,
        video_lab=video_lab,
        h3_render=h3_render,
        h3_lora_resources=H3LoraResourceCatalog(workspace_root=args.workspace,
            inventory=h3_render.video_lora_inventory, comfy=krea2_batch_comfy),
        krea2_lab=krea2_lab,
        krea2_batch=krea2_batch,
        krea2_edit=krea2_edit,
        krea2_assisted=krea2_assisted,
        social_lab=social_lab,
        media_analysis=media_analysis,
        stories=stories,
        episodes=episodes,
        production=production,
        production_v2=production_v2,
        llm_activity_monitor=gateway,
        model_runtime=LlamaSwapAdminClient(
            args.llm_base_url,
            api_key=args.llm_api_key,
            timeout=args.runtime_timeout,
        ),
        comfy_runtime=runtime_comfy,
        local_gpu_monitor=local_gpu_monitor,
    )


def main() -> int:
    args = parse_args()
    import uvicorn

    uvicorn.run(
        build_app(args),
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
