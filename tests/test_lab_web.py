import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import ChangeViewRunner
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalRunStore


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
PNG = b"\x89PNG\r\n\x1a\nimage-content"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str = "panelforge/uploaded.png"


class ImmediateComfy:
    def __init__(self):
        self.submitted = []

    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded()

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return "prompt-1"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "result.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return PNG


class LabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.temporary_directory.name)
        runs = LocalRunStore(self.temporary_directory.name)
        recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
        self.comfy = ImmediateComfy()
        runner = ChangeViewRunner(
            recipe=recipe,
            comfy=self.comfy,
            assets=assets,
            runs=runs,
        )
        self.client = TestClient(create_app(runner))

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def test_serves_page_and_curated_recipe_spec(self):
        page = self.client.get("/")
        spec = self.client.get("/api/change-view/spec")

        self.assertEqual(page.status_code, 200)
        self.assertIn("PanelForge", page.text)
        self.assertEqual(spec.status_code, 200)
        payload = spec.json()
        self.assertEqual(payload["recipe"]["version"], "0.2.0")
        self.assertEqual(payload["prompt_policy"], "locked")
        self.assertEqual(
            payload["controls"]["multiple_angles_lora_strength"]["maximum"],
            2.0,
        )
        self.assertIsInstance(payload["controls"]["seed"]["default"], str)

    def test_preview_uses_the_protected_angle_grammar(self):
        response = self.client.post(
            "/api/change-view/preview",
            json={
                "azimuth": "back",
                "elevation": "low",
                "shot_size": "wide",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["compiled_prompt"],
            "<sks> back view low-angle shot wide shot",
        )

    def test_upload_generates_persists_and_serves_a_candidate(self):
        seed = "18446744073709551615"
        response = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={
                "azimuth": "back",
                "elevation": "low",
                "shot_size": "wide",
                "lora_strength": "1.25",
                "seed": seed,
            },
        )

        self.assertEqual(response.status_code, 202)
        created = response.json()
        self.assertEqual(created["status"], "created")
        self.assertEqual(created["controls"]["seed"], seed)
        self.assertEqual(
            created["experimental_overrides"],
            ["multiple_angles_lora_strength"],
        )

        completed = self.client.get(f"/api/runs/{created['run_id']}")
        self.assertEqual(completed.status_code, 200)
        run = completed.json()
        self.assertEqual(run["status"], "succeeded")
        self.assertIsNotNone(run["result_asset_id"])
        content = self.client.get(run["result_url"])
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.content, PNG)
        self.assertEqual(content.headers["content-type"], "image/png")
        self.assertEqual(
            self.comfy.submitted[0]["108"]["inputs"]["seed"],
            int(seed),
        )

    def test_review_and_reuse_create_explicit_lineage(self):
        first = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={"seed": "42", "lora_strength": "1.0"},
        ).json()
        completed = self.client.get(f"/api/runs/{first['run_id']}").json()

        review = self.client.post(
            f"/api/runs/{first['run_id']}/review",
            json={"decision": "kept"},
        )
        reuse = self.client.post(f"/api/runs/{first['run_id']}/reuse")
        second = self.client.post(
            "/api/runs",
            data={
                "source_asset_id": reuse.json()["source_asset_id"],
                "seed": "43",
                "lora_strength": "1.0",
            },
        )

        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["decision"], "kept")
        self.assertEqual(second.status_code, 202)
        self.assertEqual(second.json()["parent_run_id"], completed["run_id"])

    def test_rejects_unsupported_image_bytes_and_imprecise_seed_syntax(self):
        bad_image = self.client.post(
            "/api/runs",
            files={"source_image": ("fake.png", b"not-an-image", "image/png")},
            data={"seed": "42"},
        )
        bad_seed = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={"seed": "1e6"},
        )

        self.assertEqual(bad_image.status_code, 422)
        self.assertEqual(bad_seed.status_code, 422)


if __name__ == "__main__":
    unittest.main()
