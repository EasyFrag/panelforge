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
    PromptCompositionService,
    PromptLabService,
    VideoLabRunner,
)
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.comfy import ComfyHttpClient
from panelforge.infrastructure.llm import (
    LlamaSwapAdminClient,
    LoggedMultimodalGateway,
    OpenAICompatibleGateway,
)
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    VideoLabPresetRecipe,
    load_change_view_preset,
    load_video_lab_workflow,
)
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalLlmCallStore,
    LocalPromptSessionStore,
    LocalPromptCompositionStore,
    LocalRunStore,
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
    parser.add_argument("--run-timeout", type=float, default=600.0)
    parser.add_argument("--video-run-timeout", type=float, default=3600.0)
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
    assets = LocalAssetStore(args.workspace)
    runs = LocalRunStore(args.workspace)
    video_runs = LocalVideoRunStore(args.workspace)
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
    gateway = LoggedMultimodalGateway(
        OpenAICompatibleGateway(
            args.llm_base_url,
            api_key=args.llm_api_key,
            timeout=args.llm_timeout,
        ),
        llm_calls,
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
    return create_app(
        runner,
        prompt_lab=prompt_lab,
        prompt_composition=prompt_composition,
        video_lab=video_lab,
        model_runtime=LlamaSwapAdminClient(
            args.llm_base_url,
            api_key=args.llm_api_key,
        ),
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
