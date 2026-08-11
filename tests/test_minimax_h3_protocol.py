from __future__ import annotations

import unittest

from panelforge.application.minimax_h3_protocol import (
    H3IssueSeverity,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    UPSTREAM_BLOBS,
    UPSTREAM_COMMIT,
    compile_camera_draft,
    compile_camera_motion,
    compile_camera_placeholders,
    compile_dialogue_tag,
    compile_media_label,
    compile_shot_heading,
    lint_h3_prompt,
    normalize_dialogue_language_tags,
    parse_camera_directives,
)
from panelforge.domain.minimax_h3 import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
    H3MediaKind,
)


class MiniMaxH3ProtocolTest(unittest.TestCase):
    def test_protocol_provenance_is_pinned(self) -> None:
        self.assertEqual(PROTOCOL_ID, "minimax.h3.protocol")
        self.assertEqual(PROTOCOL_VERSION, "0.1.0")
        self.assertEqual(
            UPSTREAM_COMMIT,
            "05d91ff89f58b665e56424fd66db9ef0351b3015",
        )
        self.assertEqual(
            UPSTREAM_BLOBS,
            {
                "SKILL.md": "066429d78f72b080a52350a5b165e52cb31b0bca",
                "references/base-en.txt": "40cf586a634d677d6b7107b367cf0ec9621be728",
                "references/ref-en.txt": "7ae1b2d07d743fd2392258a96449be9e9e322d35",
            },
        )

    def test_all_twenty_camera_motions_have_stable_compiled_phrases(self) -> None:
        expected = {
            "zoom.in": "The camera zooms in.",
            "zoom.out": "The camera zooms out.",
            "push.in": "The camera pushes in.",
            "pull.out": "The camera pulls out.",
            "pan.left": "The camera pans left.",
            "pan.right": "The camera pans right.",
            "truck.left": "The camera trucks left.",
            "truck.right": "The camera trucks right.",
            "tilt.up": "The camera tilts up.",
            "tilt.down": "The camera tilts down.",
            "pedestal.up": "The camera pedestals up.",
            "pedestal.down": "The camera pedestals down.",
            "arc_shot": "The camera performs an arc shot.",
            "tracking_shot": "The camera performs a tracking shot.",
            "static_shot": "The camera holds a static shot.",
            "shake.slightly": "The camera shakes slightly.",
            "shake.strongly": "The camera shakes strongly.",
            "pov": "The shot adopts the subject's POV.",
            "roll.clockwise": "The camera rolls clockwise.",
            "roll.counterclockwise": "The camera rolls counterclockwise.",
        }

        actual = {
            motion.value: compile_camera_motion(
                H3CameraDirective("camera_1", motion)
            )
            for motion in H3CameraMotion
        }

        self.assertEqual(actual, expected)

    def test_compiler_uses_official_modifier_order_and_natural_target(self) -> None:
        directive = H3CameraDirective(
            "camera_1",
            H3CameraMotion.PAN_RIGHT,
            amplitude=H3CameraAmplitude.LARGE,
            speed=H3CameraSpeed.FAST,
            target_clause="revealing the open doorway",
        )

        self.assertEqual(
            compile_camera_motion(directive),
            "The camera pans right with large amplitude at fast speed, "
            "revealing the open doorway.",
        )

    def test_incompatible_modifiers_and_camera_text_in_target_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not accept"):
            H3CameraDirective(
                "camera_1",
                H3CameraMotion.STATIC_SHOT,
                speed=H3CameraSpeed.SLOW,
            )
        with self.assertRaisesRegex(ValueError, "camera terminology"):
            H3CameraDirective(
                "camera_1",
                H3CameraMotion.PAN_LEFT,
                target_clause="while the camera zooms in",
            )
        with self.assertRaisesRegex(ValueError, "spatial or visual"):
            H3CameraDirective(
                "camera_1",
                H3CameraMotion.TRACKING_SHOT,
                target_clause="the subject",
            )
        self.assertEqual(
            compile_camera_motion(
                H3CameraDirective(
                    "camera_1",
                    H3CameraMotion.STATIC_SHOT,
                    target_clause="as the runner exits the frame",
                )
            ),
            "The camera holds a static shot as the runner exits the frame.",
        )
        for target in (
            "to keep both fighters visible",
            "onto her face",
            "from above",
            "centered on the rose",
            "ending on the open doorway",
            "framing both subjects",
            "until the subject reaches the bed",
        ):
            with self.subTest(target=target):
                H3CameraDirective(
                    "camera_1",
                    H3CameraMotion.PUSH_IN,
                    target_clause=target,
                )

        for target in (
            "following her while tilting down",
            "revealing the doorway as the lens is zooming in",
            "maintaining the framing while panning right",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "camera terminology"):
                    H3CameraDirective(
                        "camera_1",
                        H3CameraMotion.TRACKING_SHOT,
                        target_clause=target,
                    )

    def test_placeholder_compiler_is_fail_closed(self) -> None:
        directive = H3CameraDirective("camera_1", H3CameraMotion.PUSH_IN)
        self.assertEqual(
            compile_camera_placeholders("Action. [[camera:camera_1]]", (directive,)),
            "Action. The camera pushes in.",
        )
        with self.assertRaisesRegex(ValueError, "exactly once"):
            compile_camera_placeholders("No placeholder.", (directive,))
        with self.assertRaisesRegex(ValueError, "unknown"):
            compile_camera_placeholders("[[camera:camera_2]]", (directive,))
        with self.assertRaisesRegex(ValueError, "malformed"):
            compile_camera_placeholders(
                "[[camera:camera_1]] then [[camera :camera_2]]",
                (directive,),
            )

    def test_placeholder_must_be_a_standalone_camera_sentence(self) -> None:
        directive = H3CameraDirective("camera_1", H3CameraMotion.PUSH_IN)
        for connector in ("while", "as", "and"):
            with self.subTest(connector=connector):
                with self.assertRaisesRegex(ValueError, "standalone sentence"):
                    compile_camera_placeholders(
                        f"The subject turns {connector} [[camera:camera_1]] The door opens.",
                        (directive,),
                    )
        with self.assertRaisesRegex(ValueError, "begin a new sentence"):
            compile_camera_placeholders(
                "At 00:03.000, [[camera:camera_1]] revealing the door.",
                (directive,),
            )

        self.assertEqual(
            compile_camera_placeholders(
                "At 00:03.000, [[camera:camera_1]] The door opens.",
                (directive,),
            ),
            "At 00:03.000, The camera pushes in. The door opens.",
        )

    def test_internal_i2v_draft_compiles_json_and_normalizes_french(self) -> None:
        draft = """camera_directives:
[{"id":"camera_1","motion":"static_shot"}]
integrated_multimodal_description:
[Shot 1] A woman says: <d>[FR] Bonjour.</d> [[camera:camera_1]]
overall_soundscape:
Quiet room tone.
non_diegetic_music:
N/A"""

        compiled, directives = compile_camera_draft(draft)

        self.assertEqual(directives[0].motion, H3CameraMotion.STATIC_SHOT)
        self.assertNotIn("camera_directives", compiled)
        self.assertNotIn("[[camera:", compiled)
        self.assertIn("<d>[French] Bonjour.</d>", compiled)
        self.assertIn("The camera holds a static shot.", compiled)

    def test_directive_json_is_strict(self) -> None:
        directives = parse_camera_directives(
            '[{"id":"camera_1","motion":"truck.right","speed":"slow"}]'
        )
        self.assertEqual(directives[0].speed, H3CameraSpeed.SLOW)
        with self.assertRaisesRegex(ValueError, "fields"):
            parse_camera_directives(
                '[{"id":"camera_1","motion":"truck.right","extra":true}]'
            )
        with self.assertRaisesRegex(ValueError, "invalid camera directive"):
            parse_camera_directives('[{"id":"camera_1","motion":"orbit"}]')
        with self.assertRaisesRegex(ValueError, "1 to 8"):
            parse_camera_directives("[]")

    def test_labels_shots_and_dialogue_are_compiled(self) -> None:
        self.assertEqual(compile_media_label(H3MediaKind.PICTURE, 2), "<Picture 2>")
        self.assertEqual(compile_shot_heading(1), "[Shot 1]")
        self.assertEqual(
            compile_shot_heading(2, 3500),
            "[Shot 2] At 00:03.500,",
        )
        self.assertEqual(
            compile_dialogue_tag("fr", "Bonjour !"),
            "<d>[French] Bonjour !</d>",
        )
        self.assertEqual(
            compile_dialogue_tag("Dutch", "Goedemorgen."),
            "<d>[Dutch] Goedemorgen.</d>",
        )
        self.assertEqual(
            normalize_dialogue_language_tags("<d>fr: Bonjour.</d>"),
            "<d>[French] Bonjour.</d>",
        )

    def test_linter_reports_unresolved_or_noncanonical_fragments(self) -> None:
        issues = lint_h3_prompt(
            "i2va",
            "<Image 1> [[camera:camera_1]] <d>[FR] Bonjour.",
        )
        self.assertTrue(issues)
        self.assertTrue(all(issue.severity is H3IssueSeverity.ERROR for issue in issues))
        self.assertEqual(
            {issue.code for issue in issues},
            {
                "camera_placeholder",
                "dialogue_balance",
                "dialogue_language",
                "legacy_image_label",
            },
        )

    def test_linter_rejects_free_camera_motion_but_accepts_compiled_motion(self) -> None:
        directive = H3CameraDirective("camera_1", H3CameraMotion.PAN_RIGHT)
        canonical = compile_camera_motion(directive)
        self.assertEqual(
            lint_h3_prompt("ref2va", canonical, expected_directives=(directive,)),
            (),
        )
        issues = lint_h3_prompt(
            "ref2va",
            canonical + " The camera orbits around her.",
            expected_directives=(directive,),
        )
        self.assertIn("free_camera_motion", {issue.code for issue in issues})
        for prose in (
            "A slow orbit reveals the room.",
            "The shot dollies in.",
            "The lens zooms in.",
            "A POV shot follows the runner.",
            "The camera pushes in with enormous amplitude.",
        ):
            with self.subTest(prose=prose):
                issues = lint_h3_prompt("ref2va", prose)
                self.assertIn(
                    "free_camera_motion",
                    {issue.code for issue in issues},
                )

    def test_linter_counts_identical_compiled_camera_clauses(self) -> None:
        directives = (
            H3CameraDirective("camera_1", H3CameraMotion.PAN_RIGHT),
            H3CameraDirective("camera_2", H3CameraMotion.PAN_RIGHT),
        )
        content = "The camera pans right. Later, The camera pans right."

        self.assertEqual(
            lint_h3_prompt(
                "i2va",
                content,
                expected_directives=directives,
            ),
            (),
        )
        issues = lint_h3_prompt(
            "i2va",
            "The camera pans right.",
            expected_directives=directives,
        )
        self.assertIn("camera_clause", {issue.code for issue in issues})

    def test_noncanonical_camera_modifiers_do_not_capture_subject_motion(self) -> None:
        for prose in (
            "The runner accelerates at moderate speed.",
            "The silk ripples with tiny amplitude.",
        ):
            with self.subTest(prose=prose):
                self.assertEqual(lint_h3_prompt("i2va", prose), ())

        directive = H3CameraDirective(
            "camera_1",
            H3CameraMotion.PAN_RIGHT,
            target_clause="following the runner at moderate speed",
        )
        compiled = compile_camera_motion(directive)
        self.assertEqual(
            lint_h3_prompt(
                "i2va",
                compiled,
                expected_directives=(directive,),
            ),
            (),
        )

        issues = lint_h3_prompt(
            "i2va",
            "The camera pushes in with enormous amplitude.",
        )
        self.assertIn("free_camera_motion", {issue.code for issue in issues})

    def test_linter_requires_a_language_tag_inside_every_dialogue_block(self) -> None:
        issues = lint_h3_prompt("i2va", "A woman says <d>Bonjour.</d>")
        self.assertIn("dialogue_format", {issue.code for issue in issues})

    def test_linter_checks_scene_transition_pairs_and_voiceover_lips(self) -> None:
        issues = lint_h3_prompt(
            "i2va",
            "A man says in an off-screen voiceover: <d>[English] Go.<scenetrans></d>",
        )
        by_code = {issue.code: issue for issue in issues}
        self.assertEqual(by_code["scenetrans_pair"].severity, H3IssueSeverity.ERROR)
        self.assertEqual(by_code["voiceover_lips"].severity, H3IssueSeverity.WARNING)


if __name__ == "__main__":
    unittest.main()
