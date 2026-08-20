from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain.storyboard import (
    StoryboardCharacter,
    StoryboardEnvironment,
    StoryboardPanel,
    StoryboardSpec,
)
from panelforge.domain.storyboard_runs import StoryboardRun, StoryboardRunStatus
from panelforge.infrastructure.storage.local import StorageCorruptionError
from panelforge.infrastructure.storage.storyboard_runs import LocalStoryboardRunStore


def neutral_spec():
    return StoryboardSpec(
        sequence_context="A courier enters and crosses one workshop.",
        avoid_repeats=("Do not repeat the entrance.",),
        characters=(
            StoryboardCharacter(
                label="Courier",
                identity_lock="Adult courier with cropped brown hair.",
                wardrobe_lock="The same blue jacket and grey trousers.",
                allowed_progression="The jacket may gather dust.",
            ),
        ),
        environment=StoryboardEnvironment(
            location_lock="The same clockmaker workshop.",
            lighting_lock="Warm afternoon window light.",
            layout_lock="The workbench stays beside the north window.",
            props_lock=("canvas parcel", "brass clock"),
        ),
        panels=(
            StoryboardPanel(
                present_characters=("Courier",),
                framing="full-body portrait",
                camera_angle="eye level",
                visual_beat="The courier enters carrying the parcel.",
                emotional_beat="Alert curiosity.",
                continuity_from_previous=None,
                visible_anchors=("canvas parcel",),
            ),
            StoryboardPanel(
                present_characters=("Courier",),
                framing="three-quarter portrait",
                camera_angle="slightly high",
                visual_beat="The courier sets the parcel beside the clock.",
                emotional_beat="Careful concentration.",
                continuity_from_previous="The parcel remains in both hands.",
                visible_anchors=("canvas parcel", "brass clock"),
            ),
        ),
    )


def created_run(run_id="storyboard-1"):
    return StoryboardRun.create(
        run_id=run_id,
        intention="A courier delivers a mysterious parcel.",
        panel_count=2,
        model_id="local-model",
        recipe_id="krea2.storyboard.photorealistic",
        recipe_version="0.1.0",
        template_sha256="b" * 64,
    )


class StoryboardStorageTest(unittest.TestCase):
    def test_round_trip_uses_separate_storyboard_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStoryboardRunStore(
                directory,
                clock=lambda: datetime(2026, 8, 16, tzinfo=timezone.utc),
            )
            run = created_run()

            store.create(run)

            self.assertEqual(store.get(run.run_id), run)
            self.assertEqual(store.list(), [run])
            self.assertTrue(
                Path(directory, "storyboard_runs", run.run_id, "run.json").is_file()
            )
            self.assertFalse(Path(directory, "runs", run.run_id).exists())

    def test_completed_spec_prompt_warnings_and_raw_response_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStoryboardRunStore(directory)
            created = created_run()
            store.create(created)
            succeeded = created.start().succeed(
                raw_response='{"sequence_context":"draft"}',
                spec=neutral_spec(),
                compiled_prompt="STRICT FORMAT: exactly TWO panels.",
                warnings=("Adjacent framing is similar.",),
            )

            store.save(succeeded)

            loaded = store.get(created.run_id)
            self.assertEqual(loaded, succeeded)
            self.assertEqual(loaded.spec.to_payload(), neutral_spec().to_payload())

    def test_failed_and_truncated_runs_keep_the_model_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStoryboardRunStore(directory)
            first = created_run("storyboard-failed")
            second = created_run("storyboard-truncated")
            store.create(first)
            store.create(second)

            failed = first.start().fail(
                "ValueError: invalid JSON",
                raw_response="{unfinished",
            )
            truncated = second.start().truncate("{long unfinished response")
            store.save(failed)
            store.save(truncated)

            self.assertEqual(
                store.get(first.run_id).raw_response,
                "{unfinished",
            )
            self.assertEqual(
                store.get(second.run_id).status,
                StoryboardRunStatus.TRUNCATED,
            )
            self.assertEqual(
                store.get(second.run_id).raw_response,
                "{long unfinished response",
            )

    def test_unknown_metadata_field_is_rejected_as_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStoryboardRunStore(directory)
            run = created_run()
            store.create(run)
            path = Path(directory, "storyboard_runs", run.run_id, "run.json")
            value = json.loads(path.read_text(encoding="utf-8"))
            value["unexpected"] = True
            path.write_text(json.dumps(value), encoding="utf-8")

            with self.assertRaises(StorageCorruptionError):
                store.get(run.run_id)


if __name__ == "__main__":
    unittest.main()
