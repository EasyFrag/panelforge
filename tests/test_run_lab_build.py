from argparse import Namespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts import run_lab
from panelforge.infrastructure.storage.local import LocalAssetStore


DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)


class BuildComfyClient:
    instances: list["BuildComfyClient"] = []

    def __init__(self, base_url, *, client_id, timeout=30.0) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.timeout = timeout
        self.instances.append(self)

    def list_unet_models(self):
        return (DEFAULT_MODEL,)

    def list_lora_models(self):
        return (
            "krea2/ignored.safetensors",
            "minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
        )

    @property
    def websocket_url(self):
        return f"ws://gpu.test:8188/ws?clientId={self.client_id}"


class BuildProjectExporter:
    instances: list["BuildProjectExporter"] = []

    def __init__(self, root) -> None:
        self.root = Path(root).resolve()
        self.instances.append(self)

    def export(self, stages, assets):
        raise AssertionError("the build test must not export a project")


class BuildCreationExporter:
    instances: list["BuildCreationExporter"] = []

    def __init__(self, root) -> None:
        self.root = Path(root).resolve()
        self.instances.append(self)

    def export(self, project, attempt, assets):
        raise AssertionError("the build test must not export an assisted creation")


class RunLabBuildTest(unittest.TestCase):
    def test_default_krea2_resource_roots_match_the_server_layout(self):
        with (
            patch.object(run_lab.sys, "argv", ["run_lab.py"]),
            patch.dict(run_lab.os.environ, {}, clear=True),
        ):
            args = run_lab.parse_args()

        self.assertEqual(
            args.krea2_models_root,
            Path(r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion_models\Krea2"),
        )
        self.assertEqual(
            args.krea2_loras_root,
            Path(r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2"),
        )
        self.assertEqual(args.local_llm_base_url, "http://127.0.0.1:8888/v1")
        self.assertEqual(args.dlss_video_export_root, Path(r"X:\data\ComfyUI\output\video\Upscale"))
        self.assertEqual(args.dlss_output_root, Path(r"D:\AI\PanelForge\LocalOutput"))
        self.assertEqual(args.local_llm_api_key, "")
        self.assertFalse(hasattr(args, "vllm_base_url"))
        self.assertFalse(hasattr(args, "vllm_api_key"))
        self.assertFalse(hasattr(args, "vllm_max_output_tokens"))

    def test_local_unsloth_connection_can_be_configured_from_the_environment(self):
        with (
            patch.object(run_lab.sys, "argv", ["run_lab.py"]),
            patch.dict(
                run_lab.os.environ,
                {
                    "PANELFORGE_LOCAL_LLM_URL": "http://workstation:8888/v1",
                    "PANELFORGE_LOCAL_LLM_API_KEY": "test-unsloth-key",
                },
                clear=True,
            ),
        ):
            args = run_lab.parse_args()

        self.assertEqual(
            args.local_llm_base_url,
            "http://workstation:8888/v1",
        )
        self.assertEqual(args.local_llm_api_key, "test-unsloth-key")

    def test_build_app_configures_krea2_recipe_store_and_dedicated_transport(self):
        with tempfile.TemporaryDirectory() as workspace:
            args = Namespace(
                base_url="http://gpu.test:8188",
                host="127.0.0.1",
                port=7860,
                http_timeout=12.0,
                runtime_timeout=2.5,
                run_timeout=600.0,
                video_run_timeout=3600.0,
                krea2_run_timeout=2400.0,
                krea2_batch_run_timeout=2500.0,
                krea2_models_root=Path(workspace) / "models",
                krea2_loras_root=Path(workspace) / "loras",
                krea2_projects_root=Path(workspace) / "KREA2 Projects",
                poll_interval=0.5,
                llm_base_url="http://llm.test:8083/v1",
                llm_api_key="local-test",
                llm_timeout=300.0,
                local_llm_base_url="http://local.test:8888/v1",
                local_llm_api_key="local-unsloth-test",
                dlss_video_export_root=Path(workspace) / "unmounted-server" / "video" / "Upscale",
                dlss_output_root=Path(workspace) / "LocalOutput",
                workspace=workspace,
            )
            BuildComfyClient.instances = []
            BuildProjectExporter.instances = []
            BuildCreationExporter.instances = []
            with (
                patch.object(run_lab, "ComfyHttpClient", BuildComfyClient),
                patch.object(
                    run_lab,
                    "LocalKrea2ProjectExporter",
                    BuildProjectExporter,
                ),
                patch.object(
                    run_lab,
                    "LocalKrea2CreationExporter",
                    BuildCreationExporter,
                ),
            ):
                app = run_lab.build_app(args)
                with TestClient(app) as client:
                    spec = client.get("/api/image-lab/krea2/spec")
                    h3_render_spec = client.get("/api/h3-render/spec")
                    ref2v_render_spec = client.get("/api/h3-render/spec?mode=ref2va")
                    old_recipe_spec = client.get("/api/h3-render/spec?mode=ref2va&recipe_id=minimax-h3-ref2v&recipe_version=0.2.1")
                    video_spec = client.get("/api/video-lab/spec")
                    edit_spec = client.get("/api/image-lab/krea2-edit/spec")
                    history = client.get("/api/image-lab/krea2/runs?limit=1")
                    args.dlss_output_root.mkdir()
                    media = args.dlss_output_root / "reference.mp4"
                    media.write_bytes(b"sample-video-content")
                    catalogue = LocalAssetStore(workspace, external_roots=(args.dlss_output_root,))
                    referenced = catalogue.register_file(media, "video/mp4")
                    playback = client.get(f"/api/assets/{referenced.asset_id}/content", headers={"Range": "bytes=0-5"})

            self.assertEqual(playback.status_code, 206)
            self.assertEqual(playback.content, b"sample")
            self.assertEqual(playback.headers["content-type"], "video/mp4")
            self.assertFalse((Path(workspace) / "assets" / referenced.asset_id / "content.bin").exists())
            self.assertEqual(spec.status_code, 200)
            self.assertEqual(edit_spec.status_code, 200)
            self.assertEqual(edit_spec.json()["recipe"]["version"], "0.2.0")
            self.assertEqual([(w["engine"], w["version"]) for w in edit_spec.json()["workflows"]],
                             [("krea2", "0.2.0"), ("krea2", "0.1.0"), ("krea2", "0.3.0"), ("firered", "0.1.0")])
            self.assertEqual(spec.json()["defaults"]["model_id"], DEFAULT_MODEL)
            self.assertEqual(h3_render_spec.status_code, 200)
            self.assertEqual(ref2v_render_spec.status_code, 200)
            self.assertEqual(old_recipe_spec.status_code, 200)
            self.assertEqual(old_recipe_spec.json()["recipe"]["version"], "0.2.1+vae-int8-convrot.1")
            self.assertEqual(video_spec.status_code, 200)
            self.assertEqual(video_spec.json()["recipe"]["version"], "0.2.1+vae-int8-convrot.1")
            self.assertEqual(
                h3_render_spec.json()["revision_versions"],
                [
                    {
                        "version": "0.2.0",
                        "label": "Stable 0.2.0 · caméra compilée",
                    },
                    {
                        "version": "0.1.0",
                        "label": "Legacy 0.1.0",
                    },
                ],
            )
            self.assertEqual(
                h3_render_spec.json()["default_revision_version"],
                "0.2.0",
            )
            self.assertEqual(
                h3_render_spec.json()["video_lora"]["models"],
                ["minmax_nsfw/MysticXXX_MMH3-V2.safetensors"],
            )
            self.assertTrue(h3_render_spec.json()["video_lora"]["supported"])
            self.assertTrue(ref2v_render_spec.json()["video_lora"]["supported"])
            self.assertEqual(
                ref2v_render_spec.json()["video_lora"]["models"],
                ["minmax_nsfw/MysticXXX_MMH3-V2.safetensors"],
            )
            self.assertEqual(
                ref2v_render_spec.json()["revision_versions"],
                [
                    {
                        "version": "0.2.0",
                        "label": "Stable 0.2.0 · caméra compilée",
                    },
                    {"version": "0.1.0", "label": "Legacy 0.1.0"},
                ],
            )
            self.assertEqual(
                ref2v_render_spec.json()["limits"]["reference_images"],
                {"minimum": 1, "maximum": 9},
            )
            self.assertEqual(ref2v_render_spec.json()["recipe"]["version"], "0.2.5+vae-int8-convrot.1")
            self.assertEqual(ref2v_render_spec.json()["defaults"]["megapixels"], 0.2)
            self.assertEqual(ref2v_render_spec.json()["defaults"]["initial_megapixels"], 0.2)
            self.assertTrue(ref2v_render_spec.json()["defaults"]["seed_locked"])
            self.assertEqual(ref2v_render_spec.json()["defaults"]["duration_seconds"], 10.0)
            self.assertEqual(h3_render_spec.json()["recipe"]["version"], "0.1.7+vae-int8-convrot.1")
            self.assertEqual([item["id"] for item in h3_render_spec.json()["render_recipes"]],
                             ["minimax-h3-latent-speed", *(["minimax-h3-bunny"] * 4), *(["minimax-h3-latent-speed"] * 4)])
            self.assertEqual([item["id"] for item in ref2v_render_spec.json()["render_recipes"]],
                             ["minimax-h3-ref2v", *(["minimax-h3-bunny"] * 4), *(["minimax-h3-ref2v"] * 5)])
            self.assertTrue(h3_render_spec.json()["video_lora_stack"]["supported"])
            self.assertTrue(ref2v_render_spec.json()["video_lora_stack"]["supported"])
            self.assertFalse(h3_render_spec.json()["video_lora_stack"]["defaults"]["enabled"])
            self.assertEqual(ref2v_render_spec.json()["render_recipes"][-1]["label"], "Historique")
            self.assertEqual(ref2v_render_spec.json()["render_recipes"][-1]["version"], "0.2.0+vae-int8-convrot.1")
            self.assertTrue(h3_render_spec.json()["checkpoint_selection"]["supported"])
            self.assertTrue(ref2v_render_spec.json()["checkpoint_selection"]["supported"])
            self.assertEqual(h3_render_spec.json()["defaults"]["megapixels"], 0.2)
            self.assertEqual(h3_render_spec.json()["defaults"]["initial_megapixels"], 0.2)
            self.assertTrue(h3_render_spec.json()["defaults"]["seed_locked"])
            self.assertIn("initial_megapixels", h3_render_spec.json()["limits"])
            self.assertIn("initial_megapixels", ref2v_render_spec.json()["limits"])
            self.assertEqual(
                h3_render_spec.json()["recipe"]["workflow_sha256"],
                "ebbcc11094decbd691aa23f49dfc42db4137e29b70bf94555b234b32ea692515",
            )
            self.assertNotIn("preview_ws_url", spec.json())
            self.assertEqual(len(BuildProjectExporter.instances), 1)
            self.assertEqual(
                BuildProjectExporter.instances[0].root,
                (Path(workspace) / "KREA2 Projects").resolve(),
            )
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json(), {"runs": []})
            self.assertTrue((Path(workspace) / "krea2_runs").is_dir())
            self.assertEqual(len(BuildCreationExporter.instances), 1)
            self.assertEqual(
                BuildCreationExporter.instances[0].root,
                Path(r"D:\AI\PanelForge\KREA2 Creations").resolve(),
            )
            self.assertEqual(len(BuildComfyClient.instances), 10)
            clients = {client.client_id: client for client in BuildComfyClient.instances}
            self.assertEqual(clients["panelforge-dlss"].base_url, "http://127.0.0.1:8188")
            self.assertFalse((Path(workspace) / "unmounted-server").exists(), "startup must not access or create the export share")
            h3_render_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-h3-render-")
            ]
            self.assertEqual(len(h3_render_ids), 1)
            self.assertEqual(clients[h3_render_ids[0]].timeout, 12.0)
            self.assertTrue((Path(workspace) / "h3_render_projects").is_dir())
            krea2_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-krea2-lab-")
            ]
            self.assertEqual(len(krea2_ids), 1)
            self.assertEqual(clients[krea2_ids[0]].timeout, 12.0)
            batch_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-krea2-batch-")
            ]
            self.assertEqual(len(batch_ids), 1)
            self.assertEqual(clients[batch_ids[0]].timeout, 12.0)
            edit_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-krea2-edit-")
            ]
            self.assertEqual(len(edit_ids), 1)
            self.assertEqual(clients[edit_ids[0]].timeout, 12.0)
            self.assertTrue((Path(workspace) / "krea2_edits").is_dir())
            assisted_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-krea2-assisted-")
            ]
            self.assertEqual(len(assisted_ids), 1)
            self.assertEqual(clients[assisted_ids[0]].timeout, 12.0)
            self.assertTrue((Path(workspace) / "krea2_assisted").is_dir())
            runtime_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-runtime-")
            ]
            self.assertEqual(len(runtime_ids), 1)
            self.assertEqual(clients[runtime_ids[0]].timeout, 2.5)
            production_monitor_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-production-monitor-")
            ]
            self.assertEqual(len(production_monitor_ids), 1)
            self.assertEqual(clients[production_monitor_ids[0]].timeout, 2.5)
            self.assertTrue((Path(workspace) / "production_jobs").is_dir())


if __name__ == "__main__":
    unittest.main()
