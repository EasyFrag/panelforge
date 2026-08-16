from datetime import datetime, timezone
import tempfile
import unittest

from panelforge.domain import (
    RecipeRef,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabSettings,
)
from panelforge.infrastructure.storage.video_runs import LocalVideoRunStore


class VideoLabStorageTest(unittest.TestCase):
    def test_round_trip_uses_separate_video_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalVideoRunStore(
                directory,
                clock=lambda: datetime(2026, 8, 16, tzinfo=timezone.utc),
            )
            run = VideoLabRun.create(
                run_id="video-1",
                recipe=RecipeRef(
                    operation_id="video.generate.ref2v",
                    recipe_id="minimax-h3-ref2v",
                    version="0.1.0",
                    workflow_sha256="a" * 64,
                ),
                preset_id="h3-balanced",
                source_asset_ids=("asset-1",),
                source_labels=("source.png",),
                prompt="A simple movement.",
                settings=VideoLabSettings(
                    aspect_ratio=VideoAspectRatio.PORTRAIT_PHOTO,
                    megapixels=0.6,
                    duration_seconds=10.0,
                    steps=32,
                    seed=2**63,
                    seed_locked=True,
                ),
            )
            store.create(run)

            self.assertEqual(store.get("video-1"), run)
            self.assertEqual(store.list(), [run])
            self.assertTrue(
                __import__("pathlib").Path(directory, "video_runs", "video-1", "run.json").is_file()
            )
            self.assertFalse(__import__("pathlib").Path(directory, "runs", "video-1").exists())

    def test_compiled_workflow_is_verified_after_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalVideoRunStore(directory)
            run = VideoLabRun.create(
                run_id="video-1",
                recipe=RecipeRef("op", "recipe", "1", "a" * 64),
                preset_id="preset",
                source_asset_ids=("asset-1",),
                source_labels=("source.png",),
                prompt="Prompt.",
                settings=VideoLabSettings(
                    VideoAspectRatio.SQUARE,
                    0.6,
                    10.0,
                    32,
                    1,
                ),
            )
            store.create(run)
            workflow_hash = store.save_compiled_workflow("video-1", {"1": {}})
            running = run.queue().start("prompt-1", workflow_hash)
            store.save(running)
            self.assertEqual(store.get("video-1"), running)


if __name__ == "__main__":
    unittest.main()
