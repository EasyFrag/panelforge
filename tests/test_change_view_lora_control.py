import copy
import json
import math
import sys
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
    MULTIPLE_ANGLES_LORA_STRENGTH,
    PresetValidationError,
    build_change_view_workflow,
    load_change_view_preset,
    validate_change_view_preset,
)


RECIPE_ROOT = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
)
PRESET_V1_DIRECTORY = RECIPE_ROOT / "0.1.0"
PRESET_V2_DIRECTORY = RECIPE_ROOT / "0.2.0"


class ChangeViewLoraControlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preset = load_change_view_preset(PRESET_V2_DIRECTORY)
        cls.manifest = json.loads(
            (PRESET_V2_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
        )
        cls.workflow = json.loads(
            (PRESET_V2_DIRECTORY / "workflow_api.json").read_text(encoding="utf-8")
        )
        cls.prompt_template = (
            (PRESET_V2_DIRECTORY / "prompt.txt")
            .read_text(encoding="utf-8")
            .rstrip("\r\n")
        )
        cls.change = ChangeView(
            "asset-1",
            CameraAzimuth.BACK,
            CameraElevation.LOW,
            ShotSize.WIDE,
        )

    def test_v2_keeps_v1_workflow_and_prompt_snapshots(self):
        self.assertEqual(self.preset.version, "0.2.0")
        self.assertEqual(
            (PRESET_V2_DIRECTORY / "workflow_api.json").read_bytes(),
            (PRESET_V1_DIRECTORY / "workflow_api.json").read_bytes(),
        )
        self.assertEqual(
            (PRESET_V2_DIRECTORY / "prompt.txt").read_bytes(),
            (PRESET_V1_DIRECTORY / "prompt.txt").read_bytes(),
        )

    def test_loads_explicit_multiple_angles_lora_control(self):
        control = self.preset.controls[MULTIPLE_ANGLES_LORA_STRENGTH]

        self.assertEqual(control.workflow_assertion_id, "multiple_angles_lora")
        self.assertEqual(control.node_id, "115")
        self.assertEqual(control.input_name, "lora_6")
        self.assertEqual(control.value_path, ("strength",))
        self.assertEqual(control.minimum, 0.0)
        self.assertEqual(control.maximum, 2.0)
        self.assertEqual(control.step, 0.05)
        self.assertEqual(control.default, 1.0)
        self.assertEqual(control.validated_values, (1.0,))

    def test_classifies_every_non_default_qualified_step_as_experimental(self):
        control = self.preset.controls[MULTIPLE_ANGLES_LORA_STRENGTH]

        for step_index in range(41):
            value = round(step_index * 0.05, 2)
            with self.subTest(value=value):
                self.assertEqual(
                    control.is_experimental_override(value),
                    value != 1.0,
                )

    def test_builder_changes_only_the_declared_nested_strength(self):
        original = copy.deepcopy(self.preset.workflow)
        expected = copy.deepcopy(original)
        expected["115"]["inputs"]["lora_6"]["strength"] = 1.25

        built = build_change_view_workflow(
            self.change,
            self.preset,
            source_image="ComfyUI_00010_.png",
            seed=151020854543467,
            multiple_angles_lora_strength=1.25,
        )

        self.assertEqual(built, expected)
        self.assertEqual(self.preset.workflow, original)

    def test_builder_uses_the_validated_default_when_control_is_omitted(self):
        built = build_change_view_workflow(
            self.change,
            self.preset,
            source_image="ComfyUI_00010_.png",
            seed=151020854543467,
        )

        self.assertEqual(built["115"]["inputs"]["lora_6"]["strength"], 1.0)

    def test_control_rejects_bool_non_finite_out_of_range_and_off_step(self):
        control = self.preset.controls[MULTIPLE_ANGLES_LORA_STRENGTH]
        invalid_values = (
            True,
            False,
            math.nan,
            math.inf,
            -math.inf,
            10**400,
            -0.05,
            2.05,
            1.03,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    control.validate_value(value)
                with self.assertRaises(ValueError):
                    build_change_view_workflow(
                        self.change,
                        self.preset,
                        source_image="ComfyUI_00010_.png",
                        seed=151020854543467,
                        multiple_angles_lora_strength=value,
                    )

    def test_v1_does_not_silently_accept_the_new_control(self):
        preset_v1 = load_change_view_preset(PRESET_V1_DIRECTORY)

        self.assertEqual(dict(preset_v1.controls), {})
        with self.assertRaisesRegex(ValueError, "does not expose"):
            build_change_view_workflow(
                self.change,
                preset_v1,
                source_image="ComfyUI_00010_.png",
                seed=151020854543467,
                multiple_angles_lora_strength=1.25,
            )

    def test_validation_rejects_a_control_targeting_another_assertion(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["controls"][MULTIPLE_ANGLES_LORA_STRENGTH]["target"][
            "workflow_assertion_id"
        ] = "lightning_lora"

        with self.assertRaisesRegex(PresetValidationError, "multiple_angles_lora"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )

    def test_validation_rejects_a_default_different_from_the_snapshot(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["controls"][MULTIPLE_ANGLES_LORA_STRENGTH]["default"] = 1.25
        manifest["controls"][MULTIPLE_ANGLES_LORA_STRENGTH][
            "validated_values"
        ] = [1.25]

        with self.assertRaisesRegex(PresetValidationError, "asserted workflow value"):
            validate_change_view_preset(
                manifest,
                self.workflow,
                self.prompt_template,
            )


if __name__ == "__main__":
    unittest.main()
