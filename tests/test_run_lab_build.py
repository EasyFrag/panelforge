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


class RunLabBuildTest(unittest.TestCase):
    def test_build_app_configures_krea2_recipe_store_and_dedicated_transport(self):
        with tempfile.TemporaryDirectory() as workspace:
            args = Namespace(
                base_url="http://gpu.test:8188",
                host="127.0.0.1",
                port=7860,
                http_timeout=12.0,
                run_timeout=600.0,
                video_run_timeout=3600.0,
                krea2_run_timeout=2400.0,
                poll_interval=0.5,
                llm_base_url="http://llm.test:8083/v1",
                llm_api_key="local-test",
                llm_timeout=300.0,
                workspace=workspace,
            )
            BuildComfyClient.instances = []
            with patch.object(run_lab, "ComfyHttpClient", BuildComfyClient):
                app = run_lab.build_app(args)
                with TestClient(app) as client:
                    spec = client.get("/api/image-lab/krea2/spec")
                    history = client.get("/api/image-lab/krea2/runs?limit=1")

            self.assertEqual(spec.status_code, 200)
            self.assertEqual(spec.json()["defaults"]["model_id"], DEFAULT_MODEL)
            self.assertNotIn("preview_ws_url", spec.json())
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json(), {"runs": []})
            self.assertTrue((Path(workspace) / "krea2_runs").is_dir())
            self.assertEqual(len(BuildComfyClient.instances), 3)
            clients = {client.client_id: client for client in BuildComfyClient.instances}
            krea2_ids = [
                client_id
                for client_id in clients
                if client_id.startswith("panelforge-krea2-lab-")
            ]
            self.assertEqual(len(krea2_ids), 1)
            self.assertEqual(clients[krea2_ids[0]].timeout, 12.0)


if __name__ == "__main__":
    unittest.main()
