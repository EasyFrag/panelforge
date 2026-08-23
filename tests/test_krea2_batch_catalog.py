import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from panelforge.domain import (
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2AspectRatio,
    Krea2AssistedRecipeDraft,
    Krea2BatchSettings,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.krea2_resources import CivitaiMetadataClient, LocalKrea2ResourceCatalog
from panelforge.infrastructure.presets import load_krea2_batch_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"
LEGACY_WORKFLOW = ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.1.0"
RECIPES = ROOT / "krea2_batch_recipes"


class Krea2BatchCatalogTest(unittest.TestCase):
    def test_civitai_check_is_informational_and_detects_a_newer_version(self):
        def open_request(request, _timeout):
            if "/model-versions/by-hash/" in request.full_url:
                return json.dumps({"id": 10, "modelId": 22, "name": "installed"}).encode()
            if "/models/22" in request.full_url:
                return json.dumps({"modelVersions": [
                    {"id": 11, "name": "new release", "status": "Published"},
                    {"id": 10, "name": "installed", "status": "Published"},
                ]}).encode()
            raise AssertionError(request.full_url)

        value = CivitaiMetadataClient(opener=open_request).inspect(
            filename="model.safetensors",
            sha256="a" * 64,
        )
        self.assertTrue(value["update_available"])
        self.assertEqual(value["latest_version_id"], 11)
        self.assertEqual(value["latest_version_name"], "new release")
        self.assertIn("modelVersionId=10", value["source_url"])

    def test_loads_six_recipe_families_with_kroma_for_jewelry(self):
        with tempfile.TemporaryDirectory() as workspace:
            catalog = LocalKrea2VisualRecipeCatalog(RECIPES, workspace_root=workspace)
            recipes = catalog.current()
        self.assertEqual(len(recipes), 6)
        jewelry = next(value for value in recipes if value.recipe_id == "high_jewelry_animal_bust_v1")
        self.assertEqual(jewelry.settings.model_name, "Krea2/kroma-v0.2-turbo.safetensors")
        self.assertEqual(jewelry.settings.aspect_ratio, Krea2AspectRatio.PORTRAIT_WIDESCREEN)
        self.assertEqual(jewelry.settings.megapixels, 2.1)
        self.assertEqual(jewelry.settings.loras, ())

    def test_workflow_compiles_four_ordered_loras_and_keeps_sampling_fixed(self):
        recipe = load_krea2_batch_workflow(WORKFLOW)
        settings = Krea2BatchSettings(
            model_name="Krea2/model.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1,
            loras=(
                Krea2LoraSelection("krea2/first.safetensors", 0.4),
                Krea2LoraSelection("krea2/second.safetensors", -0.2),
            ),
        )
        sidecar = '{"prompt":"vertical 9:16 test prompt"}'
        workflow = recipe.build(
            prompt="vertical 9:16 test prompt",
            settings=settings,
            seed=7,
            output_prefix="image/test",
            sidecar_text=sidecar,
        )
        self.assertEqual(workflow["280"]["inputs"]["text"], "vertical 9:16 test prompt")
        self.assertEqual(workflow["293"]["inputs"]["unet_name"], "Krea2/model.safetensors")
        self.assertEqual(workflow["418"]["inputs"]["lora_01"], "krea2/first.safetensors")
        self.assertEqual(workflow["418"]["inputs"]["strength_01"], 0.4)
        self.assertEqual(workflow["418"]["inputs"]["lora_02"], "krea2/second.safetensors")
        self.assertEqual(workflow["418"]["inputs"]["lora_03"], "None")
        self.assertEqual(workflow["296"]["inputs"]["sampler_name"], "er_sde")
        self.assertEqual(workflow["296"]["inputs"]["scheduler"], "simple")
        self.assertEqual(workflow["296"]["inputs"]["steps"], 8)
        self.assertEqual(workflow["301"]["inputs"]["steps"], 2)
        self.assertEqual(workflow["297"]["inputs"]["scale_by"], 1.5)
        self.assertEqual(workflow["299"]["class_type"], "SaveImageKJ")
        self.assertEqual(workflow["299"]["inputs"]["caption"], sidecar)
        self.assertEqual(workflow["299"]["inputs"]["caption_file_extension"], ".txt")

    def test_workflow_uses_the_live_rgthree_seed_limit(self):
        recipe = load_krea2_batch_workflow(WORKFLOW)
        settings = Krea2BatchSettings(
            model_name="Krea2/model.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1,
        )

        workflow = recipe.build(
            prompt="vertical 9:16 test prompt",
            settings=settings,
            seed=KREA2_BATCH_RGTHREE_MAX_SEED,
            output_prefix="image/test",
            sidecar_text="metadata",
        )
        self.assertEqual(
            workflow["287"]["inputs"]["seed"],
            KREA2_BATCH_RGTHREE_MAX_SEED,
        )
        with self.assertRaisesRegex(ValueError, str(KREA2_BATCH_RGTHREE_MAX_SEED)):
            recipe.build(
                prompt="vertical 9:16 test prompt",
                settings=settings,
                seed=KREA2_BATCH_RGTHREE_MAX_SEED + 1,
                output_prefix="image/test",
                sidecar_text="metadata",
            )

    def test_legacy_workflow_remains_loadable_without_a_sidecar(self):
        recipe = load_krea2_batch_workflow(LEGACY_WORKFLOW)
        settings = Krea2BatchSettings(
            model_name="Krea2/model.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1,
        )

        workflow = recipe.build(
            prompt="vertical 9:16 legacy prompt",
            settings=settings,
            seed=7,
            output_prefix="image/legacy",
            sidecar_text="ignored for the immutable legacy workflow",
        )

        self.assertEqual(recipe.reference.version, "0.1.0")
        self.assertEqual(workflow["299"]["class_type"], "SaveImage")
        self.assertNotIn("caption", workflow["299"]["inputs"])

    def test_identical_technical_settings_reuse_the_same_recipe_revision(self):
        with tempfile.TemporaryDirectory() as workspace:
            catalog = LocalKrea2VisualRecipeCatalog(RECIPES, workspace_root=workspace)
            base = catalog.get("space_megastructure_photoreal_v1", "0.1.0")
            changed = Krea2BatchSettings(
                model_name="Krea2/alternate.safetensors",
                aspect_ratio=base.settings.aspect_ratio,
                megapixels=base.settings.megapixels,
                loras=base.settings.loras,
            )
            first = catalog.create_technical_revision(base, changed)
            second = catalog.create_technical_revision(base, changed)
            self.assertEqual(first.version, "0.1.1")
            self.assertEqual(second, first)
            self.assertEqual(len(catalog.list()), 7)

    def test_prompt_contract_tracks_the_selected_recipe_ratio(self):
        with tempfile.TemporaryDirectory() as workspace:
            catalog = LocalKrea2VisualRecipeCatalog(RECIPES, workspace_root=workspace)
            base = catalog.get("space_megastructure_photoreal_v1", "0.1.0")
            square = replace(base, settings=replace(base.settings, aspect_ratio=Krea2AspectRatio.SQUARE))
            _system, user = square.build_generation_prompts(image_count=1, direction="", recent_signatures=())
            self.assertIn("RENDER FORMAT", user)
            self.assertIn("1:1 (Square)", user)
            self.assertIn("Square 1:1", user)
            self.assertNotIn("Vertical 9:16", user)
            prompt = "1:1 square image. " + ("Complete standalone visual direction with layered details. " * 9)
            self.assertEqual(square.parse_prompts(json.dumps({"prompts": [{"signature": "square", "prompt": prompt}]}), 1)[0][0], "square")

    def test_chinese_recipe_keeps_its_language_in_generation_and_dense_prompt_validation(self):
        with tempfile.TemporaryDirectory() as workspace:
            catalog = LocalKrea2VisualRecipeCatalog(RECIPES, workspace_root=workspace)
            base = catalog.get("space_megastructure_photoreal_v1", "0.1.0")
            chinese = catalog.publish_new(Krea2AssistedRecipeDraft(
                recipe_id="chinese_space_test",
                display_name="Espace chinois",
                description="Recette de test en chinois.",
                identity="Une mégastructure spatiale cinématographique.",
                invariants=("Composition verticale 9:16",),
                variables=("Architecture de la station",),
                risks=("Échelle trop petite",),
                canonical_prompt="竖版9:16电影感太空巨构，巨大的环形空间站悬浮在行星上空。",
                prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
            ), base.settings)
            chinese = catalog.get(chinese.recipe_id, chinese.version)
            self.assertEqual(chinese.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            system, _user = chinese.build_generation_prompts(
                image_count=1,
                direction="",
                recent_signatures=(),
            )
            self.assertIn("Simplified Chinese (简体中文)", system)
            prompt = (
                "竖版9:16电影感太空巨构，巨大的环形空间站悬浮在行星上空，前景是精密金属结构，"
                "中景布满发光舷窗与飞船航道，远景可见云层和星海，冷蓝色主光配合金色轮廓光，"
                "材质真实，尺度宏大，深度层次清晰，无文字，无水印。"
            )
            parsed = chinese.parse_prompts(json.dumps({
                "prompts": [{"signature": "环形空间站", "prompt": prompt}],
            }, ensure_ascii=False), 1)
            self.assertEqual(parsed[0], ("环形空间站", prompt))

    def test_local_catalog_classifies_models_and_reads_lora_civitai_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            loras = root / "loras"
            workspace = root / "workspace"
            models.mkdir()
            loras.mkdir()
            (models / "large.safetensors").write_bytes(b"x" * 20)
            (models / "small.safetensors").write_bytes(b"x" * 4)
            lora = loras / "style.safetensors"
            lora.write_bytes(b"lora")
            lora.with_name(f"{lora.name}.rgthree-info.json").write_text(json.dumps({
                "links": ["https://civitai.com/models/123?modelVersionId=456"],
                "sha256": "a" * 64,
                "raw": {"civitai": {"id": 456, "modelId": 123, "nsfwLevel": 4}},
            }), encoding="utf-8")
            with patch("panelforge.infrastructure.krea2_resources._BF16_THRESHOLD_BYTES", 10):
                catalog = LocalKrea2ResourceCatalog(models_root=models, loras_root=loras, workspace_root=workspace)
                by_name = {value.filename: value for value in catalog.list_models()}
                self.assertEqual(by_name["large.safetensors"].category, "bf16")
                self.assertEqual(by_name["small.safetensors"].category, "int8")
                classified = catalog.list_loras()[0]
                self.assertEqual(classified.safety.value, "nsfw")
                self.assertIn("civitai.red/models/123", classified.source_url)
                classified = catalog.set_preference(classified.resource_id, favorite=True)
                self.assertEqual(classified.category, "favorite")

    def test_comfy_inventory_fills_missing_local_roots_and_stays_krea2_only(self):
        class ComfyInventory:
            def list_unet_models(self):
                return (
                    "Krea2/remote-model.safetensors",
                    "flux/ignored.safetensors",
                )

            def list_lora_models(self):
                return (
                    "krea2/portraits/remote-style.safetensors",
                    "other/ignored.safetensors",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = LocalKrea2ResourceCatalog(
                models_root=root / "missing-models",
                loras_root=root / "missing-loras",
                workspace_root=root / "workspace",
                comfy=ComfyInventory(),
            )

            models = catalog.list_models()
            loras = catalog.list_loras()

            self.assertEqual(
                [value.comfy_name for value in models],
                ["Krea2/remote-model.safetensors"],
            )
            self.assertEqual(models[0].category, "unknown")
            self.assertEqual(models[0].size_bytes, 0)
            self.assertEqual(
                [value.comfy_name for value in loras],
                ["krea2/portraits/remote-style.safetensors"],
            )
            self.assertEqual(loras[0].category, "unclassified")
            self.assertIn("fichier local inaccessible", loras[0].warning)
            self.assertEqual(catalog.inventory_warnings(), ())

            favorite = catalog.set_preference(models[0].resource_id, favorite=True)
            self.assertEqual(favorite.category, "favorite_unknown")
            classified_model = catalog.set_preference(
                models[0].resource_id,
                precision=type(models[0].precision).BF16,
            )
            self.assertEqual(classified_model.category, "favorite_bf16")
            self.assertEqual(classified_model.precision_source, "manual")
            automatic_model = catalog.set_preference(
                models[0].resource_id,
                reset_precision=True,
            )
            self.assertEqual(automatic_model.category, "favorite_unknown")
            classified = catalog.set_preference(
                loras[0].resource_id,
                safety=type(loras[0].safety).NSFW,
            )
            self.assertEqual(classified.category, "nsfw")

    def test_missing_local_root_remains_visible_when_comfy_has_no_fallback(self):
        class EmptyComfyInventory:
            def list_unet_models(self):
                return ()

            def list_lora_models(self):
                return ()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = LocalKrea2ResourceCatalog(
                models_root=root / "missing-models",
                loras_root=root / "missing-loras",
                workspace_root=root / "workspace",
                comfy=EmptyComfyInventory(),
            )

            self.assertEqual(catalog.list_models(), ())
            self.assertEqual(catalog.list_loras(), ())
            warnings = catalog.inventory_warnings()
            self.assertTrue(any("checkpoints inaccessible" in value for value in warnings))
            self.assertTrue(any("LoRA inaccessible" in value for value in warnings))
            self.assertTrue(any("Aucun checkpoint" in value for value in warnings))
            self.assertTrue(any("Aucun LoRA" in value for value in warnings))

    def test_comfy_only_models_use_unambiguous_filename_precision(self):
        class ComfyInventory:
            def list_unet_models(self):
                return (
                    "Krea2/turbo_bf16.safetensors",
                    "Krea2/quantized_INT8.safetensors",
                    "Krea2/ambiguous.safetensors",
                )

            def list_lora_models(self):
                return ()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = LocalKrea2ResourceCatalog(
                models_root=root / "missing-models",
                loras_root=root / "missing-loras",
                workspace_root=root / "workspace",
                comfy=ComfyInventory(),
            )

            models = {value.filename: value for value in catalog.list_models()}

            self.assertEqual(models["turbo_bf16.safetensors"].category, "bf16")
            self.assertEqual(models["quantized_INT8.safetensors"].category, "int8")
            self.assertEqual(models["ambiguous.safetensors"].category, "unknown")
            self.assertEqual(models["turbo_bf16.safetensors"].precision_source, "filename")


if __name__ == "__main__":
    unittest.main()
