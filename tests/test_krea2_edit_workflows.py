"""Imported base graph, optional LoRAs and immutable per-attempt workflow routing."""

from dataclasses import replace
import hashlib
import json
import tempfile
import unittest

from panelforge.application import Krea2EditAttemptRequest, Krea2EditService
from panelforge.application.krea2_edit import _sidecar
from panelforge.domain import Krea2AspectRatio, Krea2EditMetadata, Krea2EditSettings
from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.features.lab.web import serialize_krea2_edit_source
from panelforge.infrastructure.krea2_project_exports import _accepted_sidecar
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore
from panelforge.infrastructure.storage.krea2_edits import _to_dict, _from_dict
from tests.test_krea2_edit import FakeComfy, FakeGateway, PNG, WORKFLOW


BASE = WORKFLOW.parent / "0.2.0"
PROMPT = "Replace the paint with brown soil."


class EditWorkflowVersionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.assets = LocalAssetStore(self.temp.name)
        self.asset = self.assets.create(PNG, media_type="image/png")
        self.store = LocalKrea2EditStore(self.temp.name)
        self.old = load_krea2_edit_workflow(WORKFLOW)
        self.new = load_krea2_edit_workflow(BASE)
        self.comfy = FakeComfy()
        self.service = Krea2EditService(
            gateway=FakeGateway(), workflow=self.new, historical_workflows=(self.old,),
            comfy=self.comfy, assets=self.assets, sources=self.store, poll_interval=0.001,
        )
        self.source = self.service.add_source(asset_id=self.asset.asset_id, filename="source.png", metadata=Krea2EditMetadata())
        self.source = self.store.save(replace(self.source, recipe=self.old.reference))
        self.settings = Krea2EditSettings(
            model_name=self.new.defaults["model_id"], aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1, seed=42, ref_boost=4, steps=10,
        )

    def build(self, settings=None):
        return self.new.build(source_image="input.png", prompt=PROMPT, settings=settings or self.settings,
                              output_prefix="test/image", sidecar_text="local provenance")

    def test_import_is_frozen_and_compiles_exact_original_when_controls_match(self):
        raw = (BASE / "workflow_api.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "7f9e066f4ac3bee9b9aa5aa1cb2765d724b8851bc18b11303d5f673912184a19")
        self.assertEqual(self.old.reference.workflow_sha256, "fca18ce2912f630b482efda55a0b42fa522055598bc0477aae617a2a0cbdfab3")
        original = json.loads(raw)
        settings = replace(self.settings, aspect_ratio=Krea2AspectRatio.SQUARE,
                           megapixels=1, seed=1088049369132323)
        compiled = self.new.build(source_image="example.png", prompt="Change her outfit to a red raincoat.",
                                  settings=settings, output_prefix="krea2_identity_edit", sidecar_text="local only")
        self.assertEqual(compiled, original)
        self.assertEqual(compiled["56"]["inputs"]["clip_name"], "qwen3vl_4b_bf16.safetensors")
        self.assertEqual(compiled["29"]["class_type"], "SaveImage")
        self.assertNotIn("113", compiled)

    def test_user_controls_are_applied_without_changing_geometry_or_sampler(self):
        compiled = self.build(replace(self.settings, ref_boost=25.5))
        self.assertEqual(compiled["79"]["inputs"]["ref_boost"], 25.5)
        self.assertEqual(compiled["83"]["inputs"], {"aspect_ratio": self.settings.aspect_ratio.value, "megapixels": 2.1, "multiple": 8})
        self.assertEqual(compiled["53"]["inputs"]["seed"], 42)
        self.assertEqual(compiled["53"]["inputs"]["cfg"], 1)
        self.assertEqual(compiled["53"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(compiled["79"]["inputs"]["fit_mode"], "fit")
        self.assertEqual(compiled["79"]["inputs"]["source_image"], ["72", 0])
        self.assertEqual(compiled["79"]["inputs"]["target_latent"], ["82", 0])
        self.assertEqual(compiled["84"]["inputs"]["grounding_px"], 768)
        self.assertEqual(compiled["84"]["inputs"]["prompt"], PROMPT)

    def test_optional_loras_only_insert_the_extension_when_selected(self):
        for count in (1, 10):
            settings = replace(self.settings, loras=tuple(Krea2LoraSelection(f"style-{i}.safetensors", 0.5) for i in range(count)))
            compiled = self.build(settings)
            self.assertIn("113", compiled)
            self.assertEqual(compiled["71"]["inputs"]["model"], ["113", 0])
            self.assertEqual(compiled["84"]["inputs"]["clip"], ["113", 1])
            self.assertEqual(compiled["85"]["inputs"]["clip"], ["113", 1])
            self.assertEqual(compiled["113"]["inputs"][f"lora_{count}"]["lora"], f"style-{count-1}.safetensors")
            self.assertEqual(compiled["71"]["inputs"]["strength_model"], 1)
        self.assertNotIn("113", self.build())
        self.assertNotIn("113", self.new.workflow)

    def test_new_attempts_use_new_base_in_old_workshops_and_can_explicitly_use_old(self):
        for version, encoder in ((None, "qwen3vl_4b_bf16.safetensors"), ("0.1.0", "qwen3-vl-4b-heretic.safetensors")):
            source = self.service.prepare_attempt(self.source.source_id, Krea2EditAttemptRequest(PROMPT, self.settings, version))
            attempt = source.attempts[-1]
            self.assertEqual(attempt.recipe.version, version or "0.2.0")
            self.service.queue_attempt(source.source_id, attempt.attempt_id)
            result = self.service.execute_attempt(source.source_id, attempt.attempt_id)
            self.assertEqual(result.attempts[-1].status.value, "succeeded")
            self.assertEqual(self.comfy.workflow["56"]["inputs"]["clip_name"], encoder)
        self.assertEqual(self.store.get(self.source.source_id).recipe, self.old.reference)
        self.assertEqual([a["workflow_version"] for a in serialize_krea2_edit_source(result)["attempts"]], ["0.2.0", "0.1.0"])

    def test_legacy_attempts_resolve_source_recipe_and_pinned_attempts_survive_default_change(self):
        source = self.service.prepare_attempt(self.source.source_id, Krea2EditAttemptRequest(PROMPT, self.settings))
        pinned = source.attempts[-1]
        legacy = replace(pinned, recipe=None)
        self.assertIs(self.service.workflow_for_attempt(source, legacy), self.old)
        restored = _from_dict(_to_dict(source))
        self.assertEqual(restored.attempts[-1].recipe, self.new.reference)
        self.service.workflow = self.old
        self.assertIs(self.service.workflow_for_attempt(restored, restored.attempts[-1]), self.new)
        for schema in range(1, 7):
            raw = _to_dict(source)
            raw["schema_version"] = schema
            raw["attempts"][0].pop("recipe")
            loaded = _from_dict(raw)
            self.assertIsNone(loaded.attempts[0].recipe)
            self.assertIs(self.service.workflow_for_attempt(loaded, loaded.attempts[0]), self.old)

    def test_promoted_source_and_export_retain_the_selected_attempt_recipe(self):
        source = self.service.prepare_attempt(self.source.source_id, Krea2EditAttemptRequest(PROMPT, self.settings))
        attempt = source.attempts[-1].queue().start("fixture", "a" * 64).succeed(self.asset.asset_id)
        source = self.store.save(source.replace_attempt(attempt))
        self.assertEqual(json.loads(_sidecar(source, attempt, "test"))["workflow"]["version"], "0.2.0")
        self.assertEqual(_accepted_sidecar("Project", source, attempt)["workflow"]["version"], "0.2.0")
        child = self.service.promote_attempt(source.source_id, attempt.attempt_id)
        self.assertEqual(child.recipe, self.new.reference)
        self.assertEqual(child.source_asset_id, attempt.output_asset_id)
        self.assertEqual(child.metadata.megapixels, 2.1)

    def test_unknown_workflow_is_rejected_before_creating_an_attempt(self):
        with self.assertRaisesRegex(ValueError, "not loaded"):
            self.service.prepare_attempt(self.source.source_id, Krea2EditAttemptRequest(PROMPT, self.settings, "99.0.0"))
        self.assertEqual(self.store.get(self.source.source_id).attempts, ())
        self.assertIsNone(self.comfy.workflow)
