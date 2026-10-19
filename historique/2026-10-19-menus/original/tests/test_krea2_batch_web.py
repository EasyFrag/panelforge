import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner, Krea2BatchService
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.krea2_resources import LocalKrea2ResourceCatalog
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset, load_krea2_batch_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2BatchStore, LocalRunStore
from tests.test_krea2_batch_service import Comfy, Gateway, generated_response


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


class Krea2BatchWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        models = root / "models"
        loras = root / "loras"
        models.mkdir()
        loras.mkdir()
        (models / "krea2_turbo_bf16.safetensors").write_bytes(b"model")
        (models / "kroma-v0.2-turbo.safetensors").write_bytes(b"model")
        (loras / "detail.safetensors").write_bytes(b"lora")
        assets = LocalAssetStore(root)
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=UploadOnlyComfy(),
            assets=assets,
            runs=LocalRunStore(root),
        )
        self.gateway = Gateway(generated_response(2))
        self.comfy = Comfy()
        self.catalog = LocalKrea2VisualRecipeCatalog(ROOT / "krea2_batch_recipes", workspace_root=root)
        self.service = Krea2BatchService(
            gateway=self.gateway,
            recipes=self.catalog,
            workflow=load_krea2_batch_workflow(BATCH_WORKFLOW),
            comfy=self.comfy,
            assets=assets,
            batches=LocalKrea2BatchStore(root),
            resources=LocalKrea2ResourceCatalog(models_root=models, loras_root=loras, workspace_root=root),
            poll_interval=0.001,
            seed_factory=iter(range(10, 30)).__next__,
        )
        self.client = TestClient(create_app(runner, krea2_batch=self.service))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_spec_create_one_call_render_history_and_review(self):
        spec = self.client.get("/api/image-lab/krea2-batch/spec")
        self.assertEqual(spec.status_code, 200)
        value = spec.json()
        self.assertEqual(len(value["recipes"]), 6)
        self.assertEqual(len(value["render_models"]), 2)
        self.assertEqual(value["limits"], {"image_count": {"minimum": 1, "maximum": 10}, "lora_count": 10})

        model_resource = value["render_models"][0]
        classified = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{model_resource['resource_id']}/preference",
            json={"precision": "bf16"},
        )
        self.assertEqual(classified.status_code, 200)
        self.assertEqual(classified.json()["precision"], "bf16")
        self.assertEqual(classified.json()["precision_source"], "manual")
        annotated_model = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{model_resource['resource_id']}/preference",
            json={
                "display_name": "Checkpoint cinematic",
                "notes": "Direction visuelle validÃ©e localement.",
            },
        )
        self.assertEqual(annotated_model.status_code, 200)
        self.assertEqual(annotated_model.json()["display_name"], "Checkpoint cinematic")
        self.assertEqual(
            annotated_model.json()["notes"],
            "Direction visuelle validÃ©e localement.",
        )
        invalid_model_strength = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{model_resource['resource_id']}/preference",
            json={"strength_min": 0.2},
        )
        self.assertEqual(invalid_model_strength.status_code, 422)

        lora_resource = value["loras"][0]
        categorized = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{lora_resource['resource_id']}/preference",
            json={"category": "sfw_sliders", "favorite": True},
        )
        self.assertEqual(categorized.status_code, 200)
        self.assertEqual(categorized.json()["lora_category"], "sfw_sliders")
        self.assertEqual(categorized.json()["category"], "favorite")
        self.assertEqual(categorized.json()["safety"], "sfw")
        annotated = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{lora_resource['resource_id']}/preference",
            json={
                "display_name": "Detail helper",
                "strength_min": -0.2,
                "strength_max": 0.65,
                "notes": "Use for restrained texture detail.",
            },
        )
        self.assertEqual(annotated.status_code, 200)
        self.assertEqual(annotated.json()["display_name"], "Detail helper")
        self.assertEqual(annotated.json()["strength_min"], -0.2)
        self.assertEqual(annotated.json()["strength_max"], 0.65)
        self.assertEqual(
            annotated.json()["notes"],
            "Use for restrained texture detail.",
        )
        invalid_range = self.client.post(
            f"/api/image-lab/krea2-batch/resources/{lora_resource['resource_id']}/preference",
            json={"strength_min": 0.8, "strength_max": 0.2},
        )
        self.assertEqual(invalid_range.status_code, 422)

        created = self.client.post("/api/image-lab/krea2-batch/batches", json={
            "recipe_id": "space_megastructure_photoreal_v1",
            "recipe_version": "0.1.0",
            "image_count": 2,
            "model_id": "Qwen3.8-27B",
            "direction": "cooler atmosphere",
            "render_model_id": "Krea2/krea2_turbo_bf16.safetensors",
            "aspect_ratio": "9:16 (Portrait Widescreen)",
            "megapixels": 2.1,
            "loras": [{"name": "krea2/detail.safetensors", "strength": 0.3}],
        })
        self.assertEqual(created.status_code, 201)
        batch_id = created.json()["batch"]["batch_id"]
        streamed = self.client.post(f"/api/image-lab/krea2-batch/batches/{batch_id}/prompts/stream?include_reasoning=true")
        self.assertEqual(streamed.status_code, 200)
        events = decode_sse(streamed.text)
        self.assertTrue(any(event["kind"] == "reasoning" for event in events))
        self.assertEqual(events[-1]["batch"]["status"], "ready")
        self.assertEqual(len(self.gateway.requests), 1)

        started = self.client.post(f"/api/image-lab/krea2-batch/batches/{batch_id}/start")
        self.assertEqual(started.status_code, 202)
        completed = self.client.get(f"/api/image-lab/krea2-batch/batches/{batch_id}").json()["batch"]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(completed["items"]), 2)
        self.assertTrue(all(item["output_url"] for item in completed["items"]))
        reviewed = self.client.post(
            f"/api/image-lab/krea2-batch/batches/{batch_id}/items/image-01/review",
            json={"decision": "like", "comment": "keep this palette"},
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["batch"]["items"][0]["review"], "like")

    def test_recipe_workshop_api_keeps_candidate_private_until_publish(self):
        recipe = self.catalog.get("space_megastructure_photoreal_v1", "0.1.0")
        created = self.client.post("/api/image-lab/krea2-batch/batches", json={
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.version,
            "image_count": 2,
            "model_id": "Qwen3.8-27B",
        }).json()["batch"]
        batch_id = created["batch_id"]
        self.client.post(f"/api/image-lab/krea2-batch/batches/{batch_id}/prompts/stream")
        self.client.post(f"/api/image-lab/krea2-batch/batches/{batch_id}/start")
        self.client.get(f"/api/image-lab/krea2-batch/batches/{batch_id}")
        self.gateway.completion_content = json.dumps({
            "reply": "Candidate prête pour un test contrôlé.",
            "recipe": {
                "identity": recipe.identity + " Controlled evolution.",
                "invariants": list(recipe.invariants),
                "variables": list(recipe.variables),
                "risks": list(recipe.risks),
                "canonical_prompt": recipe.canonical_prompt,
            },
        })

        proposed = self.client.post(
            f"/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision",
            json={"instruction": "Propose une évolution légère", "prompt_language": "zh"},
        )
        self.assertEqual(proposed.status_code, 200)
        root = proposed.json()["batch"]
        self.assertEqual(root["recipe_workshop"]["active_draft_id"], "D1")
        self.assertEqual(json.loads(root["recipe_revision_draft"])["prompt_language"], "zh")
        self.assertFalse(any(
            value.recipe_id == recipe.recipe_id and value.version == "0.1.1"
            for value in self.catalog.list()
        ))

        tested = self.client.post(
            f"/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision/test",
            json={
                "draft": root["recipe_revision_draft"],
                "image_count": 2,
                "model_id": "Qwen3.8-27B",
                "direction": "test direction",
                "prompt_language": "zh",
            },
        )
        self.assertEqual(tested.status_code, 201)
        self.assertEqual(tested.json()["batch"]["workshop_source_batch_id"], batch_id)

        published = self.client.post(
            f"/api/image-lab/krea2-batch/batches/{batch_id}/recipe-revision/accept"
        )
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.json()["recipe"]["version"], "0.1.1")


if __name__ == "__main__":
    unittest.main()
