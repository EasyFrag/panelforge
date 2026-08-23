import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner, Krea2AssistedService
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
    load_krea2_batch_workflow,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalKrea2AssistedProjectStore,
    LocalRunStore,
)
from tests.test_krea2_assisted import Comfy, Gateway, PNG, PROMPT


ROOT = Path(__file__).resolve().parents[1]
CHANGE_VIEW = ROOT / "workflows" / "character.change_view" / "qwen-edit-2511-multiple-angles" / "0.2.0"
BATCH_WORKFLOW = ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"


class UploadOnlyComfy:
    def upload_image(self, *_args, **_kwargs):
        return type("Uploaded", (), {"workflow_value": "unused.png"})()


def decode_sse(text):
    values = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if data:
            values.append(json.loads(data))
    return values


class Krea2AssistedWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        models = root / "models"
        loras = root / "loras"
        models.mkdir()
        loras.mkdir()
        (models / "krea2_turbo_bf16.safetensors").write_bytes(b"model")
        (loras / "detail.safetensors").write_bytes(b"lora")
        assets = LocalAssetStore(root)
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=UploadOnlyComfy(),
            assets=assets,
            runs=LocalRunStore(root),
        )
        creation = json.dumps({
            "message": "Une première proposition complète.",
            "questions": [],
            "prompt": PROMPT,
            "recommendations": [],
        })
        self.gateway = Gateway((creation,))
        service = Krea2AssistedService(
            gateway=self.gateway,
            recipes=LocalKrea2VisualRecipeCatalog(ROOT / "krea2_batch_recipes", workspace_root=root),
            workflow=load_krea2_batch_workflow(BATCH_WORKFLOW),
            comfy=Comfy(),
            assets=assets,
            projects=LocalKrea2AssistedProjectStore(root),
            resources=LocalKrea2ResourceCatalog(
                models_root=models,
                loras_root=loras,
                workspace_root=root,
            ),
            poll_interval=0.001,
            project_id_factory=lambda: "krea2-create-web",
            turn_id_factory=iter(("turn-1", "turn-2")).__next__,
            attempt_id_factory=lambda: "attempt-web",
            seed_factory=lambda: 91,
        )
        self.client = TestClient(create_app(runner, krea2_assisted=service))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_project_chat_and_single_t2i_render(self):
        spec = self.client.get("/api/image-lab/krea2-assisted/spec")
        self.assertEqual(spec.status_code, 200)
        self.assertEqual(spec.json()["limits"]["lora_count"], 4)
        model = spec.json()["render_models"][0]["comfy_name"]
        lora = spec.json()["loras"][0]["comfy_name"]

        created = self.client.post(
            "/api/image-lab/krea2-assisted/projects",
            data={"name": "Zodiaque", "intention": "Un tigre céleste", "model_id": "Qwen3.8-27B"},
            files={"reference": ("tiger.png", PNG, "image/png")},
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["project"]["project_id"]
        self.assertTrue(created.json()["project"]["reference_url"])
        self.assertEqual(created.json()["project"]["prompt_language"], "en")

        guidance = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/guidance-images",
            files={"image": ("pose.png", PNG, "image/png")},
        )
        self.assertEqual(guidance.status_code, 201, guidance.text)
        guidance_value = guidance.json()["guidance"]
        self.assertTrue(guidance_value["url"])

        streamed = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/chat/stream?include_reasoning=true",
            json={
                "message": "Un tigre céleste",
                "mode": "creation",
                "prompt_language": "en",
                "guidance_asset_id": guidance_value["asset_id"],
                "guidance_filename": guidance_value["filename"],
            },
        )
        self.assertEqual(streamed.status_code, 200)
        terminal = decode_sse(streamed.text)[-1]
        self.assertEqual(terminal["project"]["current_prompt"], PROMPT)
        self.assertEqual(terminal["project"]["prompt_language"], "en")
        user_turn = terminal["project"]["turns"][0]
        self.assertEqual(user_turn["guidance_asset_id"], guidance_value["asset_id"])
        self.assertEqual(user_turn["guidance_filename"], "pose.png")
        self.assertTrue(user_turn["guidance_url"])
        self.assertEqual(
            [image.label for image in self.gateway.requests[0].images],
            ["REFERENCE IMAGE", "TURN GUIDANCE IMAGE"],
        )

        prepared = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/attempts",
            json={
                "prompt": PROMPT,
                "model_id": model,
                "aspect_ratio": "9:16 (Portrait Widescreen)",
                "megapixels": 2.1,
                "seed": None,
                "loras": [{"name": lora, "strength": 0.25}],
            },
        )
        self.assertEqual(prepared.status_code, 201)
        attempt_id = prepared.json()["project"]["attempts"][0]["attempt_id"]
        started = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/start"
        )
        self.assertEqual(started.status_code, 202)
        project = self.client.get(
            f"/api/image-lab/krea2-assisted/projects/{project_id}"
        ).json()["project"]
        self.assertEqual(project["attempts"][0]["status"], "succeeded")
        self.assertTrue(project["attempts"][0]["output_url"])

        selected = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/feedback",
            json={"attempt_id": attempt_id},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["project"]["feedback_attempt_id"], attempt_id)

        deselected = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/feedback",
            json={"attempt_id": None},
        )
        self.assertEqual(deselected.status_code, 200)
        self.assertIsNone(deselected.json()["project"]["feedback_attempt_id"])


if __name__ == "__main__":
    unittest.main()
