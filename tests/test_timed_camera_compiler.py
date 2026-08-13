import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application.timed_camera_compiler import (
    TimedCameraContext,
    TimedCameraPlacement,
    decode_timed_camera_context,
    encode_timed_camera_context,
    insert_i2v_camera_clauses,
    insert_ref2v_camera_clauses,
    remove_i2v_camera_clauses,
    remove_ref2v_camera_clauses,
)
from panelforge.domain import H3CameraDirective, H3CameraMotion


class TimedCameraCompilerTest(unittest.TestCase):
    def placements(self):
        return (
            TimedCameraPlacement(
                H3CameraDirective("camera_1", H3CameraMotion.PUSH_IN),
                0,
            ),
            TimedCameraPlacement(
                H3CameraDirective("camera_2", H3CameraMotion.TILT_DOWN),
                2500,
            ),
        )

    def test_context_round_trip_keeps_timing_and_optional_header(self):
        context = TimedCameraContext(
            mode="ref2v",
            header="<Picture 1>: exact frame.",
            placements=self.placements(),
        )
        self.assertEqual(decode_timed_camera_context(encode_timed_camera_context(context)), context)

    def test_i2v_insertion_is_deterministic_and_reversible(self):
        writer = (
            "[Shot 1] The target video is one continuous 5-second shot. "
            "The subject raises her hand. At 00:02.500, She lowers it."
        )
        compiled = insert_i2v_camera_clauses(writer, self.placements())
        self.assertIn("shot. The camera pushes in. The subject", compiled)
        self.assertIn(
            "At 00:02.500, The camera tilts down. She lowers it.",
            compiled,
        )
        self.assertEqual(remove_i2v_camera_clauses(compiled, self.placements()), writer)

    def test_lowercase_subject_after_landmark_is_canonicalized(self):
        writer = (
            "[Shot 1] The target video is one continuous 5-second shot. "
            "the subject raises her hand. At 00:02.500, she lowers it."
        )
        compiled = insert_i2v_camera_clauses(writer, self.placements())
        self.assertIn("shot. The camera pushes in. The subject", compiled)
        self.assertIn(
            "At 00:02.500, The camera tilts down. She lowers it.",
            compiled,
        )
        restored = remove_i2v_camera_clauses(compiled, self.placements())
        self.assertIn("shot. The subject raises", restored)
        self.assertIn("At 00:02.500, She lowers", restored)

    def test_context_rejects_two_directives_at_the_same_start(self):
        duplicate_start = (
            self.placements()[0],
            TimedCameraPlacement(
                H3CameraDirective("camera_2", H3CameraMotion.TILT_DOWN),
                0,
            ),
        )
        with self.assertRaisesRegex(ValueError, "distinct start times"):
            TimedCameraContext(mode="i2v", placements=duplicate_start)

    def test_ref2v_insertion_is_deterministic_and_reversible(self):
        writer = "She raises her hand. At 00:02.500, She lowers it."
        compiled = insert_ref2v_camera_clauses(writer, self.placements())
        self.assertTrue(compiled.startswith("The camera pushes in. She"))
        self.assertIn(
            "At 00:02.500, The camera tilts down. She lowers it.",
            compiled,
        )
        self.assertEqual(remove_ref2v_camera_clauses(compiled, self.placements()), writer)

    def test_writer_placeholder_and_missing_landmark_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "must not output"):
            insert_ref2v_camera_clauses(
                "[[camera:camera_1]] She moves.",
                self.placements(),
            )
        with self.assertRaisesRegex(ValueError, "exactly one landmark"):
            insert_ref2v_camera_clauses("She moves.", self.placements())

    def test_dynamic_camera_paraphrases_fail_closed(self):
        for writer in (
            "The camera initiates a slow push-in as she moves.",
            "The framing gradually tightens while she moves.",
            "A slow pull-out begins as she moves.",
        ):
            with self.subTest(writer=writer):
                with self.assertRaisesRegex(ValueError, "movement prose"):
                    insert_ref2v_camera_clauses(writer, self.placements()[:1])

    def test_all_canonical_camera_families_fail_closed(self):
        for writer in (
            "The camera holds a static shot. The subject waits.",
            "The shot adopts the subject's POV. The subject waits.",
            "The camera shakes slightly. The subject waits.",
            "The camera rolls clockwise. The subject waits.",
            "The camera trucks left. The subject waits.",
            "The camera pedestals up. The subject waits.",
        ):
            with self.subTest(writer=writer):
                with self.assertRaisesRegex(ValueError, "movement prose"):
                    insert_ref2v_camera_clauses(writer, ())

    def test_static_scene_language_is_not_mistaken_for_camera_motion(self):
        for writer in (
            "The framing remains stable while she moves.",
            "A security camera remains fixed on the wall.",
            "Within the continuous shot, the subject moves toward the door.",
            "The framing remains stable as her eyes track the parcel.",
        ):
            with self.subTest(writer=writer):
                compiled = insert_ref2v_camera_clauses(writer, self.placements()[:1])
                self.assertIn(writer, compiled)

    def test_rehydrate_rejects_a_moved_camera_clause(self):
        misplaced = (
            "She raises her hand. The camera pushes in. "
            "At 00:02.500, The camera tilts down. She lowers it."
        )
        with self.assertRaisesRegex(ValueError, "0 ms"):
            remove_ref2v_camera_clauses(misplaced, self.placements())


if __name__ == "__main__":
    unittest.main()
