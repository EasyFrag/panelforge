from argparse import Namespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts import run_lab


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
            Path(r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion\_models\Krea2"),
        )
        self.assertEqual(
            args.krea2_loras_root,
            Path(r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2"),
        )
        self.assertEqual(args.local_llm_base_url, "http://127.0.0.1:8888/v1")
        self.assertEqual(args.local_llm_api_key, "")

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
                    history = client.get("/api/image-lab/krea2/runs?limit=1")

            self.assertEqual(spec.status_code, 200)
            self.assertEqual(spec.json()["defaults"]["model_id"], DEFAULT_MODEL)
            self.assertEqual(h3_render_spec.status_code, 200)
            self.assertEqual(
                h3_render_spec.json()["recipe"]["workflow_sha256"],
                "b7527b1b9ef5b3cee661c81440274b096652a35d54e36a1f5001b5d75dacac0c",
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
            self.assertEqual(len(BuildComfyClient.instances), 8)
            clients = {client.client_id: client for client in BuildComfyClient.instances}
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


if __name__ == "__main__":
    unittest.main()
