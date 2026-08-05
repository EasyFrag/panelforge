import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.domain import (
    Asset,
    ControlKind,
    ControlSpec,
    ControlValue,
    PromptPolicy,
    PromptSnapshot,
    RecipeRef,
    RunRecord,
    RunReview,
    RunStatus,
    VariationMethod,
    VariationPolicy,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def recipe_ref() -> RecipeRef:
    return RecipeRef(
        operation_id="character.change_view",
        recipe_id="qwen-edit-2511-multiple-angles",
        version="0.1.0",
        workflow_sha256=SHA_A,
    )


def prompt_snapshot() -> PromptSnapshot:
    return PromptSnapshot(
        positive="<sks> back view low-angle shot wide shot",
        negative="text, watermark",
        policy=PromptPolicy.LOCKED,
    )


def run_record() -> RunRecord:
    return RunRecord.create(
        run_id="run-1",
        recipe=recipe_ref(),
        source_asset_ids=("asset-source",),
        prompt=prompt_snapshot(),
        controls=(ControlValue("seed", 42),),
    )


class AssetContractTest(unittest.TestCase):
    def test_asset_has_opaque_storage_metadata_and_lineage(self):
        asset = Asset(
            asset_id="asset-output",
            media_type="image/png",
            content_sha256=SHA_A,
            size_bytes=123,
            storage_key="assets/asset-output/content.png",
            source_run_id="run-1",
        )

        self.assertEqual(asset.source_run_id, "run-1")
        self.assertFalse(hasattr(asset, "path"))
        with self.assertRaises(FrozenInstanceError):
            asset.size_bytes = 456  # type: ignore[misc]

    def test_asset_rejects_invalid_content_metadata(self):
        with self.assertRaisesRegex(ValueError, "content_sha256"):
            Asset("asset", "image/png", "not-a-hash", 1, "asset/content")
        with self.assertRaisesRegex(ValueError, "size_bytes"):
            Asset("asset", "image/png", SHA_A, 0, "asset/content")


class RecipeContractTest(unittest.TestCase):
    def test_protected_prompt_requires_present_fragments(self):
        snapshot = PromptSnapshot(
            positive="<sks> front view",
            negative="",
            policy=PromptPolicy.PROTECTED,
            protected_fragments=("<sks>",),
        )

        self.assertEqual(snapshot.protected_fragments, ("<sks>",))
        with self.assertRaisesRegex(ValueError, "must occur"):
            PromptSnapshot(
                positive="front view",
                negative="",
                policy=PromptPolicy.PROTECTED,
                protected_fragments=("<sks>",),
            )

    def test_locked_and_mutable_prompt_boundaries_are_explicit(self):
        self.assertEqual(prompt_snapshot().policy, PromptPolicy.LOCKED)
        with self.assertRaisesRegex(ValueError, "mutable"):
            PromptSnapshot(
                positive="portrait with freckles",
                negative="",
                policy=PromptPolicy.MUTABLE,
                protected_fragments=("freckles",),
            )

    def test_variation_policy_validates_values_and_fills_defaults(self):
        angle = ControlSpec(
            control_id="azimuth",
            label="Angle",
            kind=ControlKind.CHOICE,
            method=VariationMethod.SEMANTIC,
            default="front",
            options=("front", "back"),
        )
        lora = ControlSpec(
            control_id="angle_lora_strength",
            label="Angle LoRA",
            kind=ControlKind.FLOAT,
            method=VariationMethod.LORA_STRENGTH,
            default=1.0,
            minimum=0.0,
            maximum=1.5,
            step=0.05,
        )
        seed = ControlSpec(
            control_id="seed",
            label="Seed",
            kind=ControlKind.INTEGER,
            method=VariationMethod.SEED,
            default=0,
            minimum=0,
            maximum=2**64 - 1,
            step=1,
            advanced=True,
        )
        policy = VariationPolicy(
            method_order=(
                VariationMethod.SEMANTIC,
                VariationMethod.LORA_STRENGTH,
                VariationMethod.SEED,
            ),
            controls=(angle, lora, seed),
        )

        values = policy.validate_values(
            (ControlValue("azimuth", "back"), ControlValue("seed", 42))
        )

        self.assertEqual(
            values,
            (
                ControlValue("azimuth", "back"),
                ControlValue("angle_lora_strength", 1.0),
                ControlValue("seed", 42),
            ),
        )

    def test_control_rejects_values_outside_curated_range(self):
        control = ControlSpec(
            control_id="strength",
            label="Strength",
            kind=ControlKind.FLOAT,
            method=VariationMethod.LORA_STRENGTH,
            default=1.0,
            minimum=0.0,
            maximum=1.5,
            step=0.05,
        )

        with self.assertRaisesRegex(ValueError, "above"):
            control.validate_value(2.0)


class RunLifecycleTest(unittest.TestCase):
    def test_successful_run_records_compiled_workflow_and_review(self):
        created = run_record()
        submitted = created.submit("comfy-prompt-1", SHA_B)
        succeeded = submitted.succeed(("asset-output",))
        kept = succeeded.review(RunReview.KEPT)

        self.assertEqual(created.status, RunStatus.CREATED)
        self.assertIsNone(created.compiled_workflow_sha256)
        self.assertEqual(submitted.status, RunStatus.SUBMITTED)
        self.assertEqual(submitted.compiled_workflow_sha256, SHA_B)
        self.assertEqual(succeeded.review_status, RunReview.PENDING)
        self.assertEqual(kept.review_status, RunReview.KEPT)
        self.assertEqual(succeeded.review_status, RunReview.PENDING)

    def test_run_can_fail_before_or_after_submission(self):
        failed_upload = run_record().fail("upload failed")
        failed_execution = run_record().submit("prompt-1", SHA_B).fail(
            "execution failed"
        )

        self.assertEqual(failed_upload.status, RunStatus.FAILED)
        self.assertIsNone(failed_upload.execution_id)
        self.assertEqual(failed_execution.execution_id, "prompt-1")

    def test_run_records_experimental_control_overrides_explicitly(self):
        run = RunRecord.create(
            run_id="run-experimental",
            recipe=recipe_ref(),
            source_asset_ids=("asset-source",),
            prompt=prompt_snapshot(),
            controls=(ControlValue("multiple_angles_lora_strength", 1.2),),
            experimental_overrides=("multiple_angles_lora_strength",),
        )

        self.assertEqual(
            run.experimental_overrides,
            ("multiple_angles_lora_strength",),
        )

        with self.assertRaisesRegex(ValueError, "experimental_overrides"):
            RunRecord.create(
                run_id="run-invalid",
                recipe=recipe_ref(),
                source_asset_ids=("asset-source",),
                prompt=prompt_snapshot(),
                experimental_overrides=("",),
            )

    def test_illegal_run_transitions_are_rejected(self):
        created = run_record()
        with self.assertRaisesRegex(ValueError, "cannot succeed"):
            created.succeed(("asset-output",))
        with self.assertRaisesRegex(ValueError, "cannot review"):
            created.review(RunReview.KEPT)

        succeeded = created.submit("prompt-1", SHA_B).succeed(("asset-output",))
        with self.assertRaisesRegex(ValueError, "cannot fail"):
            succeeded.fail("too late")
        with self.assertRaisesRegex(ValueError, "kept or rejected"):
            succeeded.review(RunReview.PENDING)


if __name__ == "__main__":
    unittest.main()
