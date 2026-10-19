import hashlib
import unittest

from panelforge.domain import (
    KREA2_RESOLUTION_MULTIPLE,
    Krea2AspectRatio,
    Krea2LabRun,
    Krea2LabRunStatus,
    Krea2LabSettings,
    RecipeRef,
    normalize_krea2_model_name,
)


DEFAULT_MODEL = (
    "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"
)


class Krea2LabDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Krea2LabSettings(
            model_name=DEFAULT_MODEL,
            aspect_ratio=Krea2AspectRatio.PORTRAIT_PHOTO,
            megapixels=3.0,
            seed=2**63,
            seed_locked=True,
        )
        self.recipe = RecipeRef(
            operation_id="image.generate.t2i",
            recipe_id="krea2",
            version="0.1.0",
            workflow_sha256="a" * 64,
        )

    def test_default_portrait_settings_derive_expected_resolution(self) -> None:
        self.assertEqual(self.settings.resolution, (1448, 2176))
        self.assertEqual(self.settings.resolution[0] % KREA2_RESOLUTION_MULTIPLE, 0)
        self.assertEqual(self.settings.resolution[1] % KREA2_RESOLUTION_MULTIPLE, 0)

    def test_every_ratio_stays_aligned_and_keeps_its_orientation(self) -> None:
        for ratio in Krea2AspectRatio:
            with self.subTest(ratio=ratio.value):
                settings = Krea2LabSettings(DEFAULT_MODEL, ratio, 1.0, 7)
                width, height = settings.resolution
                expected_width, expected_height = ratio.dimensions
                self.assertEqual(width % 8, 0)
                self.assertEqual(height % 8, 0)
                self.assertEqual(
                    (width > height) - (width < height),
                    (expected_width > expected_height)
                    - (expected_width < expected_height),
                )

    def test_megapixels_are_bounded_and_use_tenths(self) -> None:
        for value in (0.4, 4.1, 1.25, float("nan")):
            with self.subTest(megapixels=value):
                with self.assertRaises(ValueError):
                    Krea2LabSettings(
                        DEFAULT_MODEL,
                        Krea2AspectRatio.SQUARE,
                        value,
                        1,
                    )

    def test_model_normalization_does_not_rewrite_the_stored_name(self) -> None:
        server_name = (
            "kREA2\\KREA2gptgrandpussytruth_gptint4int8convrot.safetensors"
        )
        settings = Krea2LabSettings(
            server_name,
            Krea2AspectRatio.SQUARE,
            1.0,
            1,
        )

        self.assertEqual(
            normalize_krea2_model_name(server_name),
            normalize_krea2_model_name(DEFAULT_MODEL),
        )
        self.assertEqual(settings.model_name, server_name)

    def test_storyboard_provenance_requires_the_exact_prompt_hash(self) -> None:
        prompt = "STRICT FORMAT: a 3x2 storyboard page."
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        run = Krea2LabRun.create(
            run_id="krea2-1",
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt=prompt,
            settings=self.settings,
            source_storyboard_run_id="storyboard-1",
            source_prompt_sha256=prompt_hash,
        )

        self.assertEqual(run.source_storyboard_run_id, "storyboard-1")
        self.assertEqual(run.source_prompt_sha256, prompt_hash)
        with self.assertRaisesRegex(ValueError, "does not match prompt"):
            Krea2LabRun.create(
                run_id="krea2-2",
                recipe=self.recipe,
                preset_id="krea2-base",
                prompt=prompt + " changed",
                settings=self.settings,
                source_storyboard_run_id="storyboard-1",
                source_prompt_sha256=prompt_hash,
            )

    def test_lifecycle_keeps_recipe_execution_and_output_lineage(self) -> None:
        created = Krea2LabRun.create(
            run_id="krea2-1",
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt="A six-panel storyboard.",
            settings=self.settings,
        )
        queued = created.queue()
        running = queued.start("prompt-1", "b" * 64)
        succeeded = running.succeed("asset-1")

        self.assertEqual(created.status, Krea2LabRunStatus.CREATED)
        self.assertEqual(queued.status, Krea2LabRunStatus.QUEUED)
        self.assertEqual(running.status, Krea2LabRunStatus.RUNNING)
        self.assertEqual(succeeded.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(succeeded.execution_id, "prompt-1")
        self.assertEqual(succeeded.compiled_workflow_sha256, "b" * 64)
        self.assertEqual(succeeded.output_asset_id, "asset-1")

    def test_failed_remote_cancellation_remains_active_and_retryable(self) -> None:
        running = Krea2LabRun.create(
            run_id="krea2-1",
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt="A storyboard.",
            settings=self.settings,
        ).queue().start("prompt-1", "b" * 64)

        pending = running.mark_cancel_pending("ComfyUI is unavailable")
        cancelled = pending.cancel()

        self.assertEqual(pending.status, Krea2LabRunStatus.CANCEL_PENDING)
        self.assertEqual(pending.execution_id, "prompt-1")
        self.assertEqual(cancelled.status, Krea2LabRunStatus.CANCELLED)
        self.assertIsNone(cancelled.error)

    def test_cancel_pending_can_resolve_to_late_success_or_failure(self) -> None:
        running = Krea2LabRun.create(
            run_id="krea2-1",
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt="A storyboard.",
            settings=self.settings,
        ).queue().start("prompt-1", "b" * 64)
        pending = running.mark_cancel_pending("Cancellation unavailable")

        succeeded = pending.succeed("asset-late-output")
        failed = pending.fail("GPU failure")

        self.assertEqual(succeeded.status, Krea2LabRunStatus.SUCCEEDED)
        self.assertEqual(succeeded.output_asset_id, "asset-late-output")
        self.assertIsNone(succeeded.error)
        self.assertEqual(failed.status, Krea2LabRunStatus.FAILED)
        self.assertEqual(failed.error, "GPU failure")

    def test_terminal_states_refuse_invalid_transitions(self) -> None:
        run = Krea2LabRun.create(
            run_id="krea2-1",
            recipe=self.recipe,
            preset_id="krea2-base",
            prompt="A storyboard.",
            settings=self.settings,
        ).queue().start("prompt-1", "b" * 64).succeed("asset-1")

        with self.assertRaisesRegex(ValueError, "cannot cancel"):
            run.cancel()
        with self.assertRaisesRegex(ValueError, "cannot fail"):
            run.fail("late failure")


if __name__ == "__main__":
    unittest.main()
