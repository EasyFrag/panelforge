import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)
from panelforge.infrastructure.presets import (
    PresetValidationError,
    build_change_view_workflow,
    load_change_view_preset,
    render_change_view_prompt,
    validate_change_view_preset,
)


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.1.0"
)


class ChangeViewPresetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preset = load_change_view_preset(PRESET_DIRECTORY)
        cls.manifest = json.loads(
            (PRESET_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
        )
        cls.workflow = json.loads(
            (PRESET_DIRECTORY / "workflow_api.json").read_text(encoding="utf-8")
        )
        cls.prompt_template = (
            (PRESET_DIRECTORY / "prompt.txt")
            .read_text(encoding="utf-8")
            .rstrip("\r\n")
        )

    def test_loads_the_exact_versioned_workflow(self):
        workflow_content = (PRESET_DIRECTORY / "workflow_api.json").read_bytes()

        self.assertEqual(self.preset.recipe_id, "qwen-edit-2511-multiple-angles")
        self.assertEqual(self.preset.version, "0.1.0")
        self.assertEqual(
            self.preset.workflow_sha256,
            hashlib.sha256(workflow_content).hexdigest(),
        )
        self.assertEqual(self.preset.bindings["output_image"].node_id, "9")
        self.assertEqual(
            self.preset.bindings["output_image"].history_field,
            "images",
        )

    def test_renders_the_manually_validated_prompt_exactly(self):
        change = ChangeView(
            "asset-1",
            CameraAzimuth.BACK,
            CameraElevation.LOW,
            ShotSize.WIDE,
        )

        self.assertEqual(
            render_change_view_prompt(change, self.preset),
            "<sks> back view low-angle shot wide shot",
        )

    def test_renders_all_96_supported_combinations(self):
        prompts: set[str] = set()
        for azimuth in CameraAzimuth:
            for elevation in CameraElevation:
                for shot_size in ShotSize:
                    prompt = render_change_view_prompt(
                        ChangeView("asset-1", azimuth, elevation, shot_size),
                        self.preset,
                    )
                    self.assertTrue(prompt.startswith("<sks> "))
                    self.assertNotIn("{", prompt)
                    prompts.add(prompt)

        self.assertEqual(len(prompts), 96)

    def test_build_clones_workflow_and_binds_only_run_inputs(self):
        original_workflow = copy.deepcopy(self.preset.workflow)
        change = ChangeView(
            "asset-1",
            CameraAzimuth.RIGHT_SIDE,
            CameraElevation.ELEVATED,
            ShotSize.CLOSE_UP,
        )

        workflow = build_change_view_workflow(
            change,
            self.preset,
            source_image="characters/anna-v1.png",
            seed=1234,
        )

        self.assertEqual(workflow["41"]["inputs"]["image"], "characters/anna-v1.png")
        self.assertEqual(
            workflow["104"]["inputs"]["prompt"],
            "<sks> right side view elevated shot close-up",
        )
        self.assertEqual(workflow["101"]["inputs"]["prompt"], "")
        self.assertEqual(workflow["108"]["inputs"]["seed"], 1234)
        self.assertEqual(self.preset.workflow, original_workflow)

    def test_loaded_preset_cannot_be_contaminated_between_runs(self):
        workflow = self.preset.workflow
        workflow["41"]["inputs"]["image"] = "accidental.png"

        self.assertNotEqual(
            self.preset.workflow["41"]["inputs"]["image"],
            "accidental.png",
        )
        with self.assertRaises(TypeError):
            self.preset.azimuth_phrases["front"] = "wrong"  # type: ignore[index]

    def test_validation_rejects_a_missing_phrase(self):
        manifest = copy.deepcopy(self.manifest)
        del manifest["prompt"]["phrases"]["azimuth"]["back"]

        with self.assertRaisesRegex(PresetValidationError, "azimuth"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )

    def test_validation_rejects_a_missing_binding_node(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["bindings"]["source_image"]["node_id"] = "999"

        with self.assertRaisesRegex(PresetValidationError, "node 999"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )

    def test_validation_rejects_a_modified_required_lora(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["115"]["inputs"]["lora_6"]["on"] = False

        with self.assertRaisesRegex(PresetValidationError, "multiple_angles_lora"):
            validate_change_view_preset(
                self.manifest,
                workflow,
                self.prompt_template,
            )

    def test_validation_requires_supported_schema_and_trigger(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["schema_version"] = 999
        with self.assertRaisesRegex(PresetValidationError, "schema_version"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )

        with self.assertRaisesRegex(PresetValidationError, "prompt template"):
            validate_change_view_preset(
                self.manifest,
                self.workflow,
                "NOT_SKS {azimuth} {elevation} {shot_size}",
            )

    def test_validation_requires_the_angle_lora_assertion(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["workflow_assertions"] = [
            assertion
            for assertion in manifest["workflow_assertions"]
            if assertion["id"] != "multiple_angles_lora"
        ]

        with self.assertRaisesRegex(PresetValidationError, "multiple_angles_lora"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )

    def test_load_rejects_a_workflow_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_preset = Path(temporary_directory) / "preset"
            shutil.copytree(PRESET_DIRECTORY, copied_preset)
            workflow_path = copied_preset / "workflow_api.json"
            workflow_path.write_bytes(workflow_path.read_bytes() + b"\n")

            with self.assertRaisesRegex(PresetValidationError, "hash mismatch"):
                load_change_view_preset(copied_preset)

    def test_load_rejects_a_prompt_template_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_preset = Path(temporary_directory) / "preset"
            shutil.copytree(PRESET_DIRECTORY, copied_preset)
            prompt_path = copied_preset / "prompt.txt"
            prompt_path.write_text(
                "rewrite <sks> {azimuth} {elevation} {shot_size}\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PresetValidationError, "template hash mismatch"):
                load_change_view_preset(copied_preset)


if __name__ == "__main__":
    unittest.main()
