"""Launch the local PanelForge Lab against one ComfyUI server."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    ChangeViewRunner,
    Krea2AssistedService,
    Krea2BatchService,
    Krea2EditService,
    Krea2LabRunner,
    PromptCompositionService,
    PromptLabService,
    StoryboardLabService,
    VideoLabRunner,
)
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.comfy import ComfyHttpClient
from panelforge.infrastructure.llm import (
    LlamaSwapAdminClient,
    LoggedMultimodalGateway,
    OpenAICompatibleGateway,
    RoutedMultimodalGateway,
)
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    Krea2T2IRecipe,
    VideoLabPresetRecipe,
    load_change_view_preset,
    load_krea2_batch_workflow,
    load_krea2_edit_workflow,
    load_krea2_t2i_workflow,
    load_video_lab_workflow,
)
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storyboard_recipes import LocalStoryboardRecipeCatalog
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalKrea2AssistedProjectStore,
    LocalLlmCallStore,
    LocalKrea2BatchStore,
    LocalKrea2EditStore,
    LocalKrea2RunStore,
    LocalPromptSessionStore,
    LocalPromptCompositionStore,
    LocalRunStore,
    LocalStoryboardRunStore,
    LocalVideoRunStore,
)


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
VIDEO_PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.1.0"
)
KREA2_PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "image.generate.t2i"
    / "krea2"
    / "0.1.0"
)
KREA2_BATCH_WORKFLOW_DIRECTORY = (
    PROJECT_ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"
)
KREA2_BATCH_RECIPE_DIRECTORY = PROJECT_ROOT / "krea2_batch_recipes"
KREA2_EDIT_WORKFLOW_DIRECTORY = (
    PROJECT_ROOT / "workflows" / "image.edit" / "krea2-identity" / "0.1.0"
)
DEFAULT_KREA2_MODELS_ROOT = Path(
    r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion\_models\Krea2"
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
    return parser.parse_args()


def build_app(args: argparse.Namespace):
    recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
    video_recipe = VideoLabPresetRecipe(
        load_video_lab_workflow(VIDEO_PRESET_DIRECTORY)
    )
    krea2_recipe = Krea2T2IRecipe(
        load_krea2_t2i_workflow(KREA2_PRESET_DIRECTORY)
    )
    krea2_batch_workflow = load_krea2_batch_workflow(KREA2_BATCH_WORKFLOW_DIRECTORY)
    krea2_edit_workflow = load_krea2_edit_workflow(KREA2_EDIT_WORKFLOW_DIRECTORY)
    assets = LocalAssetStore(args.workspace)
    runs = LocalRunStore(args.workspace)
    video_runs = LocalVideoRunStore(args.workspace)
    krea2_runs = LocalKrea2RunStore(args.workspace)
    krea2_batches = LocalKrea2BatchStore(args.workspace)
    krea2_assisted_projects = LocalKrea2AssistedProjectStore(args.workspace)
    krea2_edits = LocalKrea2EditStore(args.workspace)
    storyboard_runs = LocalStoryboardRunStore(args.workspace)
    prompt_sessions = LocalPromptSessionStore(args.workspace)
    prompt_compositions = LocalPromptCompositionStore(args.workspace)
    llm_calls = LocalLlmCallStore(args.workspace, capacity=20)
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
    runner = ChangeViewRunner(
        recipe=recipe,
        comfy=comfy,
        assets=assets,
        runs=runs,
        run_timeout=args.run_timeout,
        poll_interval=args.poll_interval,
    )
    video_lab = VideoLabRunner(
        recipe=video_recipe,
        comfy=video_comfy,
        assets=assets,
        runs=video_runs,
        run_timeout=args.video_run_timeout,
        poll_interval=args.poll_interval,
    )
    krea2_lab = Krea2LabRunner(
        recipe=krea2_recipe,
        comfy=krea2_comfy,
        assets=assets,
        runs=krea2_runs,
        run_timeout=args.krea2_run_timeout,
        poll_interval=args.poll_interval,
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
        routed_gateway,
        llm_calls,
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
    )
    krea2_assisted = Krea2AssistedService(
        gateway=gateway,
        recipes=krea2_visual_recipes,
        workflow=krea2_batch_workflow,
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
    )
    krea2_edit = Krea2EditService(
        gateway=gateway,
        workflow=krea2_edit_workflow,
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
    )
    prompt_lab = PromptLabService(
        gateway=gateway,
        profiles=LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles"),
        assets=assets,
        sessions=prompt_sessions,
    )
    prompt_composition = PromptCompositionService(
        gateway=gateway,
        cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
        sessions=prompt_sessions,
        compositions=prompt_compositions,
        application_outcomes=gateway,
        assets=assets,
    )
    storyboard_lab = StoryboardLabService(
        gateway=gateway,
        recipes=LocalStoryboardRecipeCatalog(PROJECT_ROOT / "storyboard_recipes"),
        runs=storyboard_runs,
        application_outcomes=gateway,
    )
    return create_app(
        runner,
        prompt_lab=prompt_lab,
        prompt_composition=prompt_composition,
        video_lab=video_lab,
        krea2_lab=krea2_lab,
        krea2_batch=krea2_batch,
        krea2_edit=krea2_edit,
        krea2_assisted=krea2_assisted,
        storyboard_lab=storyboard_lab,
        model_runtime=LlamaSwapAdminClient(
            args.llm_base_url,
            api_key=args.llm_api_key,
            timeout=args.runtime_timeout,
        ),
        comfy_runtime=runtime_comfy,
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
