"""Reduced fixtures from the September 5 construction runs; no gateway calls."""

import unittest

from panelforge.application.direct_ref2v_prompt import lint_direct_ref2v_prompt
from panelforge.application.h3_render import (
    _revision_camera_clauses, canonicalize_h3_revision,
    compile_h3_revision_camera, protect_h3_revision_camera,
)
from panelforge.application.minimax_h3_protocol import extract_compiled_camera_clauses
from panelforge.domain import H3RenderInputMode


HEADER = (
    "<Picture 1>: the exact starting frame.\n"
    "<Picture 2>: a concrete keyframe anchor.\n"
    "<Picture 3>: a concrete keyframe anchor.\n"
    "<Picture 4>: a concrete keyframe anchor."
)
PUSH = "The camera pushes in with small amplitude at slow speed."
STATIC = "The camera holds a static shot."
TIMED_STATIC = "At 00:07.000, " + STATIC


def prompt(shot):
    return (
        HEADER + "\n\nThe target video is one continuous 10-second shot.\n\n"
        "Shot 1: " + shot + "\n\noverall_soundscape: Stream and wood scraping."
        "\n\nnon_diegetic_music: N/A"
    )


class Ref2VMappingRegressionTest(unittest.TestCase):
    def test_declared_keyframe_can_be_cited_again_in_compiled_final_state(self):
        value = prompt("At 00:00.000, the worker clears bark. At 00:10.000, the finished opening matches <Picture 2>.")
        self.assertEqual(lint_direct_ref2v_prompt(value), ())
        self.assertEqual(value.count("<Picture 2>"), 2)

    def test_duplicate_mapping_and_undeclared_prose_reference_still_fail(self):
        value = prompt("The worker clears bark.")
        duplicate = value.replace(HEADER, HEADER + "\nUse <Picture 2> for another role.")
        self.assertTrue(any("exactement une fois" in e for e in lint_direct_ref2v_prompt(duplicate)))
        unknown = value.replace("clears bark", "reaches the state of <Picture 5>")
        self.assertTrue(any("sans être déclaré" in e for e in lint_direct_ref2v_prompt(unknown)))
        missing = value.replace("<Picture 2>: a concrete keyframe anchor.\n", "")
        self.assertTrue(any("contigus" in e for e in lint_direct_ref2v_prompt(missing)))


class H3RevisionCameraRegressionTest(unittest.TestCase):
    def test_two_static_segments_are_not_miscounted_as_a_duplicate(self):
        # The user replaces the opening push-in with static; the 7 s segment is
        # already static. The second full clause contains the first as a suffix.
        current = prompt(f"{PUSH} The worker clears bark. {TIMED_STATIC} He sands the opening.")
        previous = extract_compiled_camera_clauses(current)
        directives = [
            {"id": f"camera_{i}", "start_ms": start, "motion": "static_shot",
             "amplitude": None, "speed": None, "target_clause": None}
            for i, start in ((1, 0), (2, 7000))
        ]
        expected = _revision_camera_clauses(directives, previous)
        editable = protect_h3_revision_camera(current, previous)
        compiled = compile_h3_revision_camera(editable, previous, expected)
        for mode in (H3RenderInputMode.REF2VA, H3RenderInputMode.T2VA):
            with self.subTest(mode=mode):
                original, candidate = current, compiled
                if mode is H3RenderInputMode.T2VA:
                    original = current.split("\n\n", 1)[1].replace("Shot 1:", "[Shot 1]")
                    candidate = compiled.split("\n\n", 1)[1].replace("Shot 1:", "[Shot 1]")
                    original = "integrated_multimodal_description: " + original
                    candidate = "integrated_multimodal_description: " + candidate
                result = canonicalize_h3_revision(original, candidate, mode, camera_clauses=expected)
                self.assertEqual(extract_compiled_camera_clauses(result), (STATIC, TIMED_STATIC))
                self.assertNotIn(PUSH, result)
        reeditable = protect_h3_revision_camera(compiled, expected)
        self.assertEqual(compile_h3_revision_camera(reeditable, expected, expected), compiled)

    def test_missing_changed_or_extra_directives_are_still_rejected(self):
        current = prompt(f"{STATIC} The worker clears bark. {TIMED_STATIC} He sands the opening.")
        expected = extract_compiled_camera_clauses(current)
        for changed in (
            current.replace(TIMED_STATIC, ""),
            current.replace("00:07.000", "00:08.000"),
            current.replace(TIMED_STATIC, TIMED_STATIC + " " + STATIC),
            current.replace("He sands", PUSH + " He sands"),
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "camera clause"):
                canonicalize_h3_revision(current, changed, H3RenderInputMode.REF2VA, camera_clauses=expected)

    def test_repair_can_remove_only_exact_adjacent_camera_expansions(self):
        previous = (PUSH, TIMED_STATIC)
        target = (STATIC, TIMED_STATIC)
        draft = prompt(
            f"[[camera:camera_1]] {PUSH} The worker clears bark. "
            f"[[camera:camera_2]] {TIMED_STATIC} He sands the opening."
        )
        compiled = compile_h3_revision_camera(draft, previous, target)
        self.assertEqual(extract_compiled_camera_clauses(compiled), target)
        self.assertIn("The worker clears bark.", compiled)
        self.assertIn("He sands the opening.", compiled)
        invalid = draft.replace(PUSH, "The camera pans right.")
        invalid = compile_h3_revision_camera(invalid, previous, target)
        with self.assertRaisesRegex(ValueError, "unexpected compiled camera clause"):
            canonicalize_h3_revision(compiled, invalid, H3RenderInputMode.REF2VA, camera_clauses=target)
        with self.assertRaisesRegex(ValueError, "unknown camera token"):
            compile_h3_revision_camera(draft + " [[camera:camera_3]]", previous, target)


if __name__ == "__main__":
    unittest.main()
