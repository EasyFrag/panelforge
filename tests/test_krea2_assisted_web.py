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
from panelforge.infrastructure.storage.krea2_style_presets import LocalKrea2StylePresetStore


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
            presets=LocalKrea2StylePresetStore(root),
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
        self.service = service
        self.client = TestClient(create_app(runner, krea2_assisted=service))

    def tearDown(self):
        self.service.stop_render_worker()
        self.client.close()
        self.temporary.cleanup()

    def test_atomic_enqueue_accepts_multiple_requests_and_cancel_keeps_the_others(self):
        from itertools import count
        from unittest.mock import patch

        project = self.service.create_project(name="Queue", intention="Photo", model_id="local")
        numbers = count(1)
        self.service._attempt_id_factory = lambda: f"queued-{next(numbers)}"
        url = f"/api/image-lab/krea2-assisted/projects/{project.project_id}/attempts"
        body = {"prompt": PROMPT, "model_id": "Krea2/krea2_turbo_bf16.safetensors",
                "aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": 0.8,
                "seed": "0", "loras": [], "expected_branch_id": "main"}
        with patch.object(self.service, "start_render_worker") as wake:
            first = self.client.post(url + "?enqueue=true", json=body)
            second = self.client.post(url + "?enqueue=true", json={**body, "prompt": PROMPT + " Blue background.", "seed": "17"})
            self.assertEqual(first.status_code, 201, first.text)
            self.assertRegex(first.headers["server-timing"], r"prepare;dur=\d+\.\d, worker;dur=\d+\.\d, serialize;dur=\d+\.\d")
            self.assertEqual(second.status_code, 201, second.text)
            self.assertEqual(first.json()["project"]["attempts"][0]["status"], "queued")
            self.assertEqual(wake.call_count, 2)
            repeated = self.client.post(url + "/queued-1/start")
            self.assertEqual(repeated.status_code, 202)
            items = self.client.get("/api/image-lab/krea2-assisted/render-queue").json()["items"]
            self.assertEqual([item["attempt_id"] for item in items], ["queued-1", "queued-2"])
            cancelled = self.client.post(url + "/queued-1/cancel")
            self.assertEqual(cancelled.status_code, 200)
            self.assertEqual(cancelled.json()["project"]["attempts"][1]["status"], "queued")
            rejected = self.client.post(url + "?enqueue=true", json={**body, "model_id": "missing.safetensors"})
            self.assertEqual(rejected.status_code, 422)
            self.assertEqual(len(self.service.projects.get(project.project_id).attempts), 2)
            self.assertEqual(self.service.comfy.workflows, [])
            self.assertEqual(self.gateway.requests, [])

    def test_presets_can_be_saved_selected_at_creation_and_updated_without_a_generation(self):
        from dataclasses import replace
        from tests.test_krea2_assisted_branches import fixture

        project = fixture()
        asset = self.service.assets.create(PNG, media_type="image/png")
        project = project.replace_attempt(replace(project.attempt("image-1"), output_asset_id=asset.asset_id))
        self.service.projects.create(project)
        url = "/api/image-lab/krea2-assisted/style-presets"
        body = {"project_id": project.project_id, "attempt_id": "image-1", "name": "Photo"}
        saved = self.client.post(url, json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        preset = saved.json()["preset"]
        self.assertEqual(self.client.get(url).json()["presets"][0]["preset_id"], preset["preset_id"])
        created = self.client.post("/api/image-lab/krea2-assisted/projects", data={
            "name": "Shoe", "intention": "A shoe", "model_id": "local", "style_preset_id": preset["preset_id"],
        })
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()["project"]
        self.assertTrue(value["preset_pending"])
        self.assertIsNone(value["current_prompt"])
        self.assertIsNone(value["render_seed"])
        updated = self.client.post(url, json={**body, "preset_id": preset["preset_id"], "expected_revision": 1})
        self.assertEqual(updated.json()["preset"]["revision"], 2)
        reopened = self.client.get(f'/api/image-lab/krea2-assisted/projects/{value["project_id"]}').json()["project"]
        self.assertEqual(reopened["style_preset"]["revision"], 1)
        changed = self.client.post(f'/api/image-lab/krea2-assisted/projects/{value["project_id"]}/style-preset', json={
            "preset_id": preset["preset_id"], "expected_branch_id": "main",
            "draft": {"prompt": PROMPT, "model_id": preset["settings"]["model_id"],
                      "aspect_ratio": preset["settings"]["aspect_ratio"], "megapixels": .8, "seed": "0"},
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()["project"]["current_prompt"], PROMPT)
        self.assertEqual(changed.json()["project"]["render_seed"], "0")
        self.assertEqual(changed.json()["project"]["style_preset"]["revision"], 2)
        self.assertEqual(self.gateway.requests, [])

    def test_branch_route_restores_memory_without_a_model_or_render_call(self):
        from dataclasses import replace
        from tests.test_krea2_assisted_branches import fixture

        project = fixture()
        asset = self.service.assets.create(PNG, media_type="image/png")
        project = project.replace_attempt(replace(project.attempt("image-1"), output_asset_id=asset.asset_id))
        self.service.projects.create(project)
        url = f"/api/image-lab/krea2-assisted/projects/{project.project_id}"
        created = self.client.post(url + "/branches", json={
            "expected_branch_id": "main", "attempt_id": "image-1",
            "draft": {"prompt": PROMPT + " UNSENT_EDIT", "model_id": "krea2_turbo_bf16.safetensors",
                      "aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": 2.1, "seed": None},
        })
        self.assertEqual(created.status_code, 200, created.text)
        fork = created.json()["project"]
        self.assertEqual(len(fork["turns"]), 2)
        self.assertEqual(fork["render_seed"], "0")
        self.assertEqual(fork["feedback_attempt_id"], "image-1")
        self.assertEqual(self.client.get(url).json()["project"]["active_branch_id"], fork["active_branch_id"])
        stale = self.client.post(url + "/branches", json={"expected_branch_id": "main", "branch_id": "main"})
        self.assertEqual(stale.status_code, 422)
        returned = self.client.post(url + "/branches", json={"expected_branch_id": fork["active_branch_id"], "branch_id": "main"})
        self.assertEqual(returned.status_code, 200, returned.text)
        self.assertEqual(len(returned.json()["project"]["turns"]), 4)
        self.assertEqual(returned.json()["project"]["current_prompt"], PROMPT + " UNSENT_EDIT")
        missing = self.client.post(url + "/branches", json={"expected_branch_id": "main", "branch_id": "missing"})
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.service.comfy.workflows, [])

    def test_unknown_assistance_recipe_is_rejected_before_project_creation(self):
        response = self.client.post(
            "/api/image-lab/krea2-assisted/projects",
            data={"name": "Dragon", "intention": "A dragon", "model_id": "local",
                  "assistance_recipe_version": "99.0.0"},
        )
        self.assertEqual(response.status_code, 422)
        projects = self.client.get("/api/image-lab/krea2-assisted/projects").json()["projects"]
        self.assertEqual(projects, [])

    def test_reference_image_without_intention_creates_a_reopenable_project(self):
        response = self.client.post(
            "/api/image-lab/krea2-assisted/projects",
            data={"name": "Reference", "model_id": "fake", "assistance_recipe_version": "2.0.0"},
            files={"reference": ("reference.png", PNG, "image/png")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()["project"]
        self.assertTrue(project["reference_asset_id"])
        self.assertIn("reproduit fidèlement le sujet", project["intention"])
        self.assertEqual(project["assistance_recipe_version"], "2.0.0")
        reopened = self.client.get(
            f"/api/image-lab/krea2-assisted/projects/{project['project_id']}"
        ).json()["project"]
        self.assertEqual(reopened["intention"], project["intention"])
        self.assertEqual(reopened["reference_asset_id"], project["reference_asset_id"])
        self.assertEqual(self.gateway.requests, [])

    def test_empty_intention_without_image_is_rejected(self):
        for intention in (None, "", "   "):
            with self.subTest(intention=intention):
                data = {"name": "Empty", "model_id": "fake"}
                if intention is not None:
                    data["intention"] = intention
                response = self.client.post("/api/image-lab/krea2-assisted/projects", data=data)
                self.assertEqual(response.status_code, 422)
        projects = self.client.get("/api/image-lab/krea2-assisted/projects").json()["projects"]
        self.assertEqual(projects, [])
        self.assertEqual(self.gateway.requests, [])

    def test_v2_chat_pins_recipe_on_project_and_turns(self):
        self._assert_chat_pins_recipe("2.0.0")

    def test_v3_chat_pins_recipe_on_project_and_turns(self):
        self._assert_chat_pins_recipe("3.0.0")

    def _assert_chat_pins_recipe(self, version):
        created = self.client.post(
            "/api/image-lab/krea2-assisted/projects",
            data={"name": "Shoe", "intention": "A glass shoe", "model_id": "fake",
                  "assistance_recipe_version": version},
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["project"]["project_id"]
        streamed = self.client.post(
            f"/api/image-lab/krea2-assisted/projects/{project_id}/chat/stream",
            json={"message": "Keep the red glass and change the pose", "mode": "creation"},
        )
        terminal = decode_sse(streamed.text)[-1]
        self.assertEqual(terminal["project"]["assistance_recipe_version"], version)
        self.assertEqual(len(terminal["project"]["turns"]), 2)
        self.assertTrue(all(turn["assistance_recipe_version"] == version
                            for turn in terminal["project"]["turns"]))
        self.assertEqual(self.gateway.requests[-1].operation_id,
                         f"krea2.assisted.creation_chat@{version}")
        restored = self.client.get(
            f"/api/image-lab/krea2-assisted/projects/{project_id}"
        ).json()["project"]
        self.assertEqual(restored["assistance_recipe_version"], version)
        self.assertEqual(self.service.comfy.workflows, [])

    def test_project_chat_and_single_t2i_render(self):
        spec = self.client.get("/api/image-lab/krea2-assisted/spec")
        self.assertEqual(spec.status_code, 200)
        self.assertEqual([item["version"] for item in spec.json()["assistance_recipes"]], ["1.0.0", "2.0.0", "3.0.0"])
        self.assertEqual(spec.json()["limits"]["lora_count"], 10)
        model = spec.json()["render_models"][0]["comfy_name"]
        lora = spec.json()["loras"][0]["comfy_name"]

        created = self.client.post(
            "/api/image-lab/krea2-assisted/projects",
            data={"name": "Zodiaque", "intention": "Un tigre céleste", "model_id": "Qwen3.8-27B"},
            files={"reference": ("tiger.png", PNG, "image/png")},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["project"]["assistance_recipe_version"], "1.0.0")
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
                "model_id": "local::revision-qwen",
                "prompt_language": "en",
                "guidance_asset_id": guidance_value["asset_id"],
                "guidance_filename": guidance_value["filename"],
            },
        )
        self.assertEqual(streamed.status_code, 200)
        terminal = decode_sse(streamed.text)[-1]
        self.assertTrue(all(turn["assistance_recipe_version"] == "1.0.0" for turn in terminal["project"]["turns"]))
        self.assertEqual(terminal["project"]["current_prompt"], PROMPT)
        self.assertEqual(terminal["project"]["prompt_language"], "en")
        self.assertEqual(
            terminal["project"]["revision_model_id"],
            "local::revision-qwen",
        )
        self.assertEqual(
            terminal["project"]["turns"][-1]["model_id"],
            "local::revision-qwen",
        )
        self.assertEqual(self.gateway.requests[0].model_id, "local::revision-qwen")
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
        self.service.execute_attempt(project_id, attempt_id)  # Wait for the fake queue worker.
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
