import unittest

from panelforge.domain import (
    RecipeRef,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabRunStatus,
    VideoLabSettings,
)


class VideoLabDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio.PORTRAIT_PHOTO,
            megapixels=0.6,
            duration_seconds=10.0,
            steps=32,
            seed=7,
        )
        self.recipe = RecipeRef(
            operation_id="video.generate.ref2v",
            recipe_id="minimax-h3-ref2v",
            version="0.1.0",
            workflow_sha256="a" * 64,
        )

    def test_balanced_settings_derive_resolution_and_effective_duration(self) -> None:
        self.assertEqual(self.settings.resolution, (640, 960))
        self.assertEqual(self.settings.frame_count, 243)
        self.assertEqual(self.settings.effective_duration_seconds, 10.125)

    def test_h3_duration_range_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 5 and 15"):
            VideoLabSettings(
                aspect_ratio=VideoAspectRatio.SQUARE,
                megapixels=0.6,
                duration_seconds=16.0,
                steps=32,
                seed=1,
            )

    def test_run_lifecycle_keeps_source_labels(self) -> None:
        run = VideoLabRun.create(
            run_id="video-1",
            recipe=self.recipe,
            preset_id="h3-balanced",
            source_asset_ids=("asset-1", "asset-2"),
            source_labels=("first.png", "second.png"),
            prompt="A simple movement.",
            settings=self.settings,
        )
        queued = run.queue()
        running = queued.start("prompt-1", "b" * 64)
        succeeded = running.succeed("asset-video")

        self.assertEqual(queued.status, VideoLabRunStatus.QUEUED)
        self.assertEqual(succeeded.status, VideoLabRunStatus.SUCCEEDED)
        self.assertEqual(succeeded.source_labels, ("first.png", "second.png"))

    def test_failed_remote_cancellation_stays_active_and_retryable(self) -> None:
        run = VideoLabRun.create(
            run_id="video-1",
            recipe=self.recipe,
            preset_id="h3-balanced",
            source_asset_ids=("asset-1",),
            source_labels=("first.png",),
            prompt="A simple movement.",
            settings=self.settings,
        ).queue().start("prompt-1", "b" * 64)

        pending = run.mark_cancel_pending("ComfyUI is unreachable")
        cancelled = pending.cancel()

        self.assertEqual(pending.status, VideoLabRunStatus.CANCEL_PENDING)
        self.assertEqual(pending.execution_id, "prompt-1")
        self.assertEqual(cancelled.status, VideoLabRunStatus.CANCELLED)
        self.assertIsNone(cancelled.error)

    def test_run_requires_one_to_three_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 3"):
            VideoLabRun.create(
                run_id="video-1",
                recipe=self.recipe,
                preset_id="h3-balanced",
                source_asset_ids=(),
                source_labels=(),
                prompt="A simple movement.",
                settings=self.settings,
            )


if __name__ == "__main__":
    unittest.main()
