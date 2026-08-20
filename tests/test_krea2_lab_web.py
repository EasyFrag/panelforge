from pathlib import Path
import hashlib
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner, Krea2LabRunner
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    Krea2T2IRecipe,
    load_change_view_preset,
    load_krea2_t2i_workflow,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalKrea2RunStore,
    LocalRunStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHANGE_VIEW_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
KREA2_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "image.generate.t2i"
    / "krea2"
    / "0.1.0"
)
DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)
ALTERNATE_MODEL = "Krea2/krea2_turbo_bf16.safetensors"
PNG = b"\x89PNG\r\n\x1a\nKREA2 image"


class ImmediateKrea2Comfy:
    def __init__(self) -> None:
        self.models = (DEFAULT_MODEL, ALTERNATE_MODEL, "Krea2/new.safetensors")
        self.submitted: list[dict[str, object]] = []
        self.cancelled: list[str] = []
        self.discovery_error: Exception | None = None

    def list_unet_models(self) -> tuple[str, ...]:
        if self.discovery_error is not None:
            raise self.discovery_error
        return self.models

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return f"krea-prompt-{len(self.submitted)}"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "29": {
                        "images": [
                            {
                                "filename": "PanelForge_KREA2_00001_.png",
                                "subfolder": "image/krea2",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return PNG

    def cancel_execution(self, prompt_id):
        self.cancelled.append(prompt_id)


class FakeStoryboardLab:
    def __init__(self) -> None:
        self.run_ids = {"storyboard-42"}

    def get(self, run_id):
        if run_id not in self.run_ids:
            raise KeyError(run_id)
        return object()


class Krea2LabWebTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(self.directory.name)
        self.comfy = ImmediateKrea2Comfy()
        change_runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(
                load_change_view_preset(CHANGE_VIEW_DIRECTORY)
            ),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalRunStore(self.directory.name),
        )
        self.krea2_lab = Krea2LabRunner(
            recipe=Krea2T2IRecipe(load_krea2_t2i_workflow(KREA2_DIRECTORY)),
            comfy=self.comfy,
            assets=self.assets,
            runs=LocalKrea2RunStore(self.directory.name),
            run_id_factory=iter(("krea2-1", "krea2-2", "krea2-3")).__next__,
            sleep=lambda _: None,
        )
        self.client = TestClient(
            create_app(
                change_runner,
                krea2_lab=self.krea2_lab,
                storyboard_lab=FakeStoryboardLab(),
            )
        )

    def tearDown(self) -> None:
        self.client.close()
        self.directory.cleanup()

    def test_spec_exposes_fixed_recipe_dynamic_models_and_no_preview(self):
        response = self.client.get("/api/image-lab/krea2/spec")

        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(value["operation_id"], "image.generate.t2i")
        self.assertEqual(value["recipe"]["id"], "krea2")
        self.assertEqual(value["recipe"]["version"], "0.1.0")
        self.assertEqual(value["defaults"]["model_id"], DEFAULT_MODEL)
        self.assertEqual(value["defaults"]["aspect_ratio"], "2:3 (Portrait Photo)")
        self.assertEqual(value["defaults"]["megapixels"], 3.0)
        self.assertEqual(value["model_discovery"]["status"], "available")
        models = {model["id"]: model for model in value["models"]}
        self.assertTrue(models[DEFAULT_MODEL]["installed"])
        self.assertTrue(models[DEFAULT_MODEL]["selectable"])
        self.assertFalse(models["Krea2/new.safetensors"]["qualified"])
        self.assertFalse(models["Krea2/new.safetensors"]["selectable"])
        self.assertNotIn("preview", value)
        self.assertNotIn("preview_ws_url", value)

    def test_prepare_start_and_final_png_keep_exact_controls_and_provenance(self):
        prompt = "A strict six-panel storyboard page."
        source_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        prepared_response = self.client.post(
            "/api/image-lab/krea2/runs",
            json={
                "prompt": prompt,
                "model_id": ALTERNATE_MODEL,
                "aspect_ratio": "1:1 (Square)",
                "megapixels": 4.0,
                "seed": "18446744073709551615",
                "seed_locked": True,
                "source_storyboard_run_id": "storyboard-42",
                "source_prompt_sha256": "f" * 64,
            },
        )

        self.assertEqual(prepared_response.status_code, 201)
        prepared = prepared_response.json()
        self.assertEqual(prepared["status"], "created")
        self.assertEqual(prepared["model_id"], ALTERNATE_MODEL)
        self.assertEqual(prepared["aspect_ratio"], "1:1 (Square)")
        self.assertEqual(prepared["megapixels"], 4.0)
        self.assertEqual(prepared["seed"], "18446744073709551615")
        self.assertEqual(prepared["source_storyboard_run_id"], "storyboard-42")
        self.assertEqual(prepared["source_prompt_sha256"], source_hash)
        self.assertEqual(self.comfy.submitted, [])

        started = self.client.post(
            f"/api/image-lab/krea2/runs/{prepared['run_id']}/start"
        )
        self.assertEqual(started.status_code, 202)
        completed = self.client.get(
            f"/api/image-lab/krea2/runs/{prepared['run_id']}"
        ).json()

        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["resolution"], {"width": 2048, "height": 2048})
        self.assertIsNotNone(completed["output_asset_id"])
        workflow = self.comfy.submitted[0]
        self.assertEqual(workflow["30:19"]["inputs"]["value"], prepared["prompt"])
        self.assertEqual(workflow["30:10"]["inputs"]["unet_name"], ALTERNATE_MODEL)
        self.assertEqual(workflow["49"]["inputs"]["aspect_ratio"], "1:1 (Square)")
        self.assertEqual(workflow["49"]["inputs"]["megapixels"], 4.0)
        self.assertEqual(
            workflow["30:3"]["inputs"]["seed"],
            18446744073709551615,
        )
        output = self.client.get(completed["output_url"])
        self.assertEqual(output.status_code, 200)
        self.assertEqual(output.headers["content-type"], "image/png")
        self.assertEqual(output.content, PNG)
        self.assertEqual(
            self.client.get(
                f"/api/image-lab/krea2/runs/{prepared['run_id']}/events"
            ).status_code,
            404,
        )

    def test_model_refresh_preserves_stale_inventory_and_rejects_absent_model(self):
        initial = self.client.get("/api/image-lab/krea2/spec")
        self.assertEqual(initial.status_code, 200)
        self.comfy.discovery_error = OSError("ComfyUI offline")

        refreshed = self.client.post("/api/image-lab/krea2/models/refresh")

        self.assertEqual(refreshed.status_code, 200)
        value = refreshed.json()
        self.assertEqual(value["model_discovery"]["status"], "stale")
        self.assertIn("offline", value["model_discovery"]["error"])
        missing = self.client.post(
            "/api/image-lab/krea2/runs",
            json={
                "prompt": "A prompt.",
                "model_id": "Krea2/artaix_v10Krea2.safetensors",
            },
        )
        self.assertEqual(missing.status_code, 422)
        self.assertIn("not installed", missing.json()["detail"])

    def test_history_created_cancellation_and_invalid_model(self):
        invalid = self.client.post(
            "/api/image-lab/krea2/runs",
            json={"prompt": "A prompt.", "model_id": "unsafe/model.safetensors"},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("unqualified", invalid.json()["detail"])

        prepared = self.client.post(
            "/api/image-lab/krea2/runs",
            json={"prompt": "Another prompt."},
        ).json()
        cancelled = self.client.post(
            f"/api/image-lab/krea2/runs/{prepared['run_id']}/cancel"
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        history = self.client.get("/api/image-lab/krea2/runs?limit=10")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["runs"][0]["run_id"], prepared["run_id"])

    def test_storyboard_provenance_requires_an_existing_source(self):
        unknown = self.client.post(
            "/api/image-lab/krea2/runs",
            json={
                "prompt": "An edited Storyboard prompt.",
                "source_storyboard_run_id": "storyboard-missing",
                "source_prompt_sha256": "0" * 64,
            },
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json()["detail"], "Storyboard source run not found")

        orphan_hash = self.client.post(
            "/api/image-lab/krea2/runs",
            json={"prompt": "A prompt.", "source_prompt_sha256": "0" * 64},
        )
        self.assertEqual(orphan_hash.status_code, 422)
        self.assertIn("requires source_storyboard_run_id", orphan_hash.json()["detail"])

    def test_unavailable_discovery_keeps_allowlist_usable_as_unknown(self):
        self.comfy.discovery_error = OSError("ComfyUI offline")

        response = self.client.get("/api/image-lab/krea2/spec")

        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(value["model_discovery"]["status"], "unavailable")
        default = next(
            model for model in value["models"] if model["id"] == DEFAULT_MODEL
        )
        self.assertIsNone(default["installed"])
        self.assertTrue(default["selectable"])

    def test_server_model_spelling_is_preserved_after_allowlist_matching(self):
        server_model = DEFAULT_MODEL.replace("/", "\\").upper()
        self.comfy.models = (server_model,)

        spec = self.client.get("/api/image-lab/krea2/spec").json()
        default = next(model for model in spec["models"] if model["default"])
        self.assertEqual(default["id"], server_model)

        prepared = self.client.post(
            "/api/image-lab/krea2/runs",
            json={"prompt": "A prompt.", "model_id": DEFAULT_MODEL},
        )
        self.assertEqual(prepared.status_code, 201)
        self.assertEqual(prepared.json()["model_id"], server_model)

        started = self.client.post(
            f"/api/image-lab/krea2/runs/{prepared.json()['run_id']}/start"
        )
        self.assertEqual(started.status_code, 202)
        self.assertEqual(
            self.comfy.submitted[0]["30:10"]["inputs"]["unet_name"],
            server_model,
        )


if __name__ == "__main__":
    unittest.main()
