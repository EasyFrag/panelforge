from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain import Krea2AspectRatio, Krea2LabSettings
from panelforge.infrastructure.presets import (
    DEFAULT_KREA2_PRESET_ID,
    KREA2_OPERATION_ID,
    KREA2_RECIPE_ID,
    Krea2PresetValidationError,
    Krea2T2IRecipe,
    build_krea2_t2i_workflow,
    load_krea2_t2i_workflow,
    validate_krea2_t2i_workflow,
)


PRESET_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "image.generate.t2i"
    / "krea2"
    / "0.1.0"
)
DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)


class Krea2T2IPresetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.preset = load_krea2_t2i_workflow(PRESET_DIRECTORY)
        self.manifest = json.loads(
            (PRESET_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
        )
        self.settings = Krea2LabSettings(
            model_name=DEFAULT_MODEL,
            aspect_ratio=Krea2AspectRatio.PORTRAIT_PHOTO,
            megapixels=3.0,
            seed=123,
            seed_locked=True,
        )

    def test_loads_immutable_recipe_with_current_gpt_as_default(self) -> None:
        recipe = Krea2T2IRecipe(self.preset)

        self.assertEqual(recipe.reference.operation_id, KREA2_OPERATION_ID)
        self.assertEqual(recipe.reference.recipe_id, KREA2_RECIPE_ID)
        self.assertEqual(recipe.reference.version, "0.1.0")
        self.assertEqual(recipe.default_model, DEFAULT_MODEL)
        self.assertEqual(
            recipe.presets[DEFAULT_KREA2_PRESET_ID].model_name,
            DEFAULT_MODEL,
        )
        self.assertEqual(recipe.output_node_id, "29")
        self.assertEqual(recipe.output_history_field, "images")

    def test_published_workflow_has_no_lora_refine_or_orphan_nodes(self) -> None:
        workflow = self.preset.workflow
        serialized = json.dumps(workflow).casefold()

        self.assertNotIn("lora", serialized)
        self.assertNotIn("refine prompt", serialized)
        self.assertTrue(
            {"30:15", "30:22", "30:23", "30:24"}.isdisjoint(workflow)
        )
        self.assertEqual(workflow["30:3"]["inputs"]["model"], ["30:10", 0])

    def test_compiles_only_declared_inputs_and_keeps_fixed_sampling(self) -> None:
        workflow = build_krea2_t2i_workflow(
            self.preset,
            prompt="STRICT FORMAT: six separate portrait frames.",
            settings=self.settings,
            output_filename_prefix="image/krea2/run-1",
        )

        self.assertEqual(
            workflow["30:19"]["inputs"]["value"],
            "STRICT FORMAT: six separate portrait frames.",
        )
        self.assertEqual(
            workflow["49"]["inputs"],
            {
                "aspect_ratio": "2:3 (Portrait Photo)",
                "megapixels": 3.0,
                "multiple": 8,
            },
        )
        self.assertEqual(workflow["30:10"]["inputs"]["unet_name"], DEFAULT_MODEL)
        self.assertEqual(workflow["30:3"]["inputs"]["seed"], 123)
        self.assertEqual(workflow["30:3"]["inputs"]["steps"], 8)
        self.assertEqual(workflow["30:3"]["inputs"]["cfg"], 1)
        self.assertEqual(workflow["30:3"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["30:3"]["inputs"]["scheduler"], "simple")
        self.assertEqual(workflow["29"]["inputs"]["filename_prefix"], "image/krea2/run-1")

    def test_compilation_preserves_the_exact_qualified_server_model_path(self) -> None:
        server_model = (
            "kREA2\\KREA2gptgrandpussytruth_gptint4int8convrot.safetensors"
        )
        settings = Krea2LabSettings(
            server_model,
            Krea2AspectRatio.SQUARE,
            1.0,
            9,
        )

        workflow = build_krea2_t2i_workflow(
            self.preset,
            prompt="A square storyboard.",
            settings=settings,
            output_filename_prefix="image/krea2/run-server-path",
        )

        self.assertEqual(workflow["30:10"]["inputs"]["unet_name"], server_model)

    def test_each_compilation_starts_from_a_fresh_snapshot(self) -> None:
        first = build_krea2_t2i_workflow(
            self.preset,
            prompt="First prompt.",
            settings=self.settings,
            output_filename_prefix="image/krea2/first",
        )
        second = build_krea2_t2i_workflow(
            self.preset,
            prompt="Second prompt.",
            settings=self.settings,
            output_filename_prefix="image/krea2/second",
        )

        self.assertEqual(first["30:19"]["inputs"]["value"], "First prompt.")
        self.assertEqual(second["30:19"]["inputs"]["value"], "Second prompt.")
        self.assertEqual(
            self.preset.workflow["30:19"]["inputs"]["value"],
            "PANELFORGE_PROMPT_REQUIRED",
        )

    def test_rejects_orphan_nodes_and_changes_to_fixed_controls(self) -> None:
        orphaned = deepcopy(self.preset.workflow)
        orphaned["999"] = {
            "class_type": "PrimitiveString",
            "inputs": {"value": "unused"},
        }
        with self.assertRaisesRegex(Krea2PresetValidationError, "orphan"):
            validate_krea2_t2i_workflow(self.manifest, orphaned)

        changed = deepcopy(self.preset.workflow)
        changed["30:3"]["inputs"]["steps"] = 12
        with self.assertRaisesRegex(Krea2PresetValidationError, "steps"):
            validate_krea2_t2i_workflow(self.manifest, changed)

    def test_rejects_qualified_models_that_collide_after_normalization(self) -> None:
        manifest = deepcopy(self.manifest)
        manifest["models"]["qualified"].append(DEFAULT_MODEL.upper().replace("/", "\\"))

        with self.assertRaisesRegex(Krea2PresetValidationError, "duplicates"):
            validate_krea2_t2i_workflow(manifest, self.preset.workflow)

    def test_loader_verifies_the_published_workflow_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "manifest.json").write_bytes(
                (PRESET_DIRECTORY / "manifest.json").read_bytes()
            )
            (target / "workflow_api.json").write_text(
                json.dumps({"changed": True}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(Krea2PresetValidationError, "hash mismatch"):
                load_krea2_t2i_workflow(target)


if __name__ == "__main__":
    unittest.main()
