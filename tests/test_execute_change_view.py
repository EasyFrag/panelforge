import hashlib
import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import ChangeViewRunRequest, ChangeViewRunner
from panelforge.domain import Asset, RunReview, RunStatus
from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ShotSize,
)
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    PresetValidationError,
    load_change_view_preset,
)


PRESET_ROOT = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
)
PNG = b"\x89PNG\r\n\x1a\ncontent"


class MemoryAssetStore:
    def __init__(self):
        self.assets = {}
        self.contents = {}
        self.next_id = 1

    def add_source(self, asset_id="asset-source", content=b"source-image"):
        asset = Asset(
            asset_id=asset_id,
            media_type="image/png",
            content_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            storage_key=f"assets/{asset_id}/content.bin",
        )
        self.assets[asset_id] = asset
        self.contents[asset_id] = content
        return asset

    def create(self, content, *, media_type, source_run_id=None):
        asset_id = f"asset-output-{self.next_id}"
        self.next_id += 1
        asset = Asset(
            asset_id=asset_id,
            media_type=media_type,
            content_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            storage_key=f"assets/{asset_id}/content.bin",
            source_run_id=source_run_id,
        )
        self.assets[asset_id] = asset
        self.contents[asset_id] = content
        return asset

    def get(self, asset_id):
        return self.assets[asset_id]

    def read_bytes(self, asset_id):
        return self.contents[asset_id]


class MemoryRunStore:
    def __init__(self):
        self.runs = {}
        self.workflows = {}

    def create(self, run):
        if run.run_id in self.runs:
            raise FileExistsError(run.run_id)
        self.runs[run.run_id] = run

    def save(self, run):
        if run.run_id not in self.runs:
            raise FileNotFoundError(run.run_id)
        self.runs[run.run_id] = run

    def get(self, run_id):
        return self.runs[run_id]

    def list(self, limit=20):
        return list(self.runs.values())[-limit:]

    def save_compiled_workflow(self, run_id, workflow):
        content = json.dumps(
            workflow,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.workflows[run_id] = json.loads(content)
        return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class FakeUploadedImage:
    workflow_value: str = "panelforge/server-source.png"


class FakeComfy:
    def __init__(self, *, output=PNG, history=None):
        self.output = output
        self.uploads = []
        self.submitted_workflow = None
        self.downloaded = None
        self.history = history or {
            "prompt-1": {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "1": {
                        "images": [
                            {
                                "filename": "wrong.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    },
                    "9": {
                        "images": [
                            {
                                "filename": "expected.png",
                                "subfolder": "views",
                                "type": "output",
                            }
                        ]
                    },
                },
            }
        }

    def upload_image(self, content, *, filename, subfolder=""):
        self.uploads.append((content, filename, subfolder))
        return FakeUploadedImage()

    def submit_workflow(self, workflow):
        self.submitted_workflow = workflow
        return "prompt-1"

    def get_history(self, prompt_id):
        return self.history

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        self.downloaded = (filename, subfolder, folder_type)
        return self.output


class ChangeViewRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = ChangeViewPresetRecipe(
            load_change_view_preset(PRESET_ROOT / "0.2.0")
        )

    def setUp(self):
        self.assets = MemoryAssetStore()
        self.source = self.assets.add_source()
        self.runs = MemoryRunStore()
        self.comfy = FakeComfy()
        self.runner = ChangeViewRunner(
            recipe=self.recipe,
            comfy=self.comfy,
            assets=self.assets,
            runs=self.runs,
            run_id_factory=lambda: "run-1",
        )

    def request(self, *, lora_strength=1.25):
        return ChangeViewRunRequest(
            source_asset_id=self.source.asset_id,
            azimuth=CameraAzimuth.BACK,
            elevation=CameraElevation.LOW,
            shot_size=ShotSize.WIDE,
            lora_strength=lora_strength,
            seed=151020854543467,
        )

    def test_prepare_records_locked_prompt_controls_and_override(self):
        run = self.runner.prepare(self.request())

        self.assertEqual(run.status, RunStatus.CREATED)
        self.assertEqual(
            run.prompt.positive,
            "<sks> back view low-angle shot wide shot",
        )
        self.assertEqual(run.recipe.version, "0.2.0")
        self.assertEqual(
            run.experimental_overrides,
            ("multiple_angles_lora_strength",),
        )
        self.assertEqual(
            {control.control_id: control.value for control in run.controls},
            {
                "azimuth": "back",
                "elevation": "low",
                "shot_size": "wide",
                "multiple_angles_lora_strength": 1.25,
                "seed": 151020854543467,
            },
        )

    def test_executes_full_flow_and_uses_only_manifest_output(self):
        prepared = self.runner.prepare(self.request())

        completed = self.runner.execute(prepared.run_id)

        self.assertEqual(completed.status, RunStatus.SUCCEEDED)
        self.assertEqual(completed.execution_id, "prompt-1")
        self.assertEqual(
            completed.compiled_workflow_sha256,
            hashlib.sha256(
                json.dumps(
                    self.runs.workflows[prepared.run_id],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            self.comfy.uploads,
            [(b"source-image", "asset-source.png", "panelforge")],
        )
        self.assertEqual(
            self.comfy.submitted_workflow["115"]["inputs"]["lora_6"]["strength"],
            1.25,
        )
        self.assertEqual(
            self.comfy.submitted_workflow["104"]["inputs"]["prompt"],
            completed.prompt.positive,
        )
        self.assertEqual(
            self.comfy.downloaded,
            ("expected.png", "views", "output"),
        )
        output = self.assets.get(completed.output_asset_ids[0])
        self.assertEqual(output.source_run_id, completed.run_id)
        self.assertEqual(self.assets.read_bytes(output.asset_id), PNG)

    def test_default_lora_strength_is_not_an_experimental_override(self):
        run = self.runner.prepare(self.request(lora_strength=1.0))

        self.assertEqual(run.experimental_overrides, ())

    def test_invalid_output_is_persisted_as_a_failed_run(self):
        self.comfy.output = b"not-a-png"
        prepared = self.runner.prepare(self.request())

        failed = self.runner.execute(prepared.run_id)

        self.assertEqual(failed.status, RunStatus.FAILED)
        self.assertIn("not a PNG", failed.error)
        self.assertEqual(failed.output_asset_ids, ())
        self.assertEqual(self.runs.get(failed.run_id), failed)

    def test_success_can_be_reviewed_and_reused(self):
        completed = self.runner.execute(self.runner.prepare(self.request()).run_id)

        kept = self.runner.review(completed.run_id, RunReview.KEPT)
        reusable = self.runner.reusable_asset(completed.run_id)

        self.assertEqual(kept.review_status, RunReview.KEPT)
        self.assertEqual(reusable.asset_id, completed.output_asset_ids[0])

    def test_old_preset_without_control_cannot_power_the_lab(self):
        with self.assertRaisesRegex(PresetValidationError, "LoRA strength control"):
            ChangeViewPresetRecipe(load_change_view_preset(PRESET_ROOT / "0.1.0"))


if __name__ == "__main__":
    unittest.main()
