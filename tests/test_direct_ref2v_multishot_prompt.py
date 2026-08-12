import unittest

from panelforge.application.direct_ref2v_multishot_prompt import (
    MULTISHOT_EDITABLE_FIELDS,
    compile_direct_ref2v_multishot_document,
    decode_direct_ref2v_multishot_context,
    encode_direct_ref2v_multishot_context,
    is_direct_ref2v_multishot_context,
    lint_direct_ref2v_multishot_prompt,
    normalize_direct_ref2v_multishot_camera_placeholders,
    rehydrate_direct_ref2v_multishot_editable_document,
)
from panelforge.application.direct_ref2v_prompt import encode_direct_ref2v_context
from panelforge.domain import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
)


HEADER = (
    "<Picture 1>: exact opening-frame evidence.\n"
    "Use <Picture 2> only for subject appearance."
)


def camera(number: int, motion: H3CameraMotion) -> H3CameraDirective:
    return H3CameraDirective(
        directive_id=f"camera_{number}",
        motion=motion,
        amplitude=H3CameraAmplitude.SMALL,
        speed=H3CameraSpeed.SLOW,
        target_clause="following the subject",
    )


def context(*, cameras=(1, 3)) -> str:
    motions = {
        1: H3CameraMotion.PUSH_IN,
        2: H3CameraMotion.PAN_RIGHT,
        3: H3CameraMotion.PULL_OUT,
    }
    directives = tuple(camera(number, motions[number]) for number in cameras)
    return encode_direct_ref2v_multishot_context(
        HEADER,
        directives,
        {directive.directive_id: int(directive.directive_id[-1]) for directive in directives},
        (0, 3200, 7000),
        11_500,
        12_500,
    )


def editable(*, cameras=(1, 3)) -> str:
    camera_lines = {
        number: f"[[camera:camera_{number}]] " if number in cameras else ""
        for number in (1, 2, 3)
    }
    return (
        "scene_setup:\n"
        "A stable moonlit courtyard establishes the subjects and stone arch.\n\n"
        "shot_1:\n"
        f"{camera_lines[1]}The first subject crosses the arch and stops beside the gate.\n\n"
        "shot_2:\n"
        f"{camera_lines[2]}A hard cut reveals the second subject holding the same gate.\n\n"
        "shot_3:\n"
        f"{camera_lines[3]}A hard cut shows both subjects meeting as their motion settles.\n\n"
        "overall_soundscape:\n"
        "Night ambience, footsteps, cloth movement, and the gate hinge.\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )


class DirectRef2VMultiShotPromptTest(unittest.TestCase):
    def test_context_round_trip_and_rejects_mono_context(self):
        encoded = context(cameras=(2,))
        decoded = decode_direct_ref2v_multishot_context(encoded)

        self.assertTrue(is_direct_ref2v_multishot_context(encoded))
        self.assertEqual(decoded.header, HEADER)
        self.assertEqual(tuple(item.directive_id for item in decoded.directives), ("camera_2",))
        self.assertEqual(decoded.directive_shots, (("camera_2", 2),))
        self.assertEqual(decoded.shot_starts_ms, (0, 3200, 7000))
        self.assertEqual(decoded.final_state_start_ms, 11_500)
        self.assertEqual(decoded.duration_ms, 12_500)

        mono = encode_direct_ref2v_context(HEADER, ())
        with self.assertRaisesRegex(ValueError, "multi-shot compiler context"):
            decode_direct_ref2v_multishot_context(mono)

    def test_context_requires_camera_id_to_match_owning_shot(self):
        with self.assertRaisesRegex(ValueError, "match their owning shot"):
            encode_direct_ref2v_multishot_context(
                HEADER,
                (camera(1, H3CameraMotion.PUSH_IN),),
                {"camera_1": 2},
                (0, 1000, 2000),
                3000,
                3500,
            )

    def test_compiles_exact_headings_timestamps_and_multiple_cameras(self):
        encoded = context(cameras=(1, 3))
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=(1, 3)), encoded
        )

        self.assertTrue(compiled.startswith(HEADER + "\n\n"))
        self.assertEqual(compiled.count("[Shot 1]"), 1)
        self.assertIn("[Shot 1] The camera pushes in", compiled)
        self.assertIn("[Shot 2] At 00:03.200, A hard cut reveals", compiled)
        self.assertIn("[Shot 3] At 00:07.000, The camera pulls out", compiled)
        self.assertNotIn("[[camera:", compiled)
        self.assertNotIn("scene_setup:", compiled)
        self.assertEqual(lint_direct_ref2v_multishot_prompt(compiled, encoded), ())

    def test_compiles_without_camera(self):
        encoded = context(cameras=())
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=()), encoded
        )

        self.assertNotIn("The camera ", compiled)
        self.assertIn("[Shot 3] At 00:07.000, A hard cut shows", compiled)
        self.assertEqual(lint_direct_ref2v_multishot_prompt(compiled, encoded), ())
        self.assertEqual(lint_direct_ref2v_multishot_prompt(compiled), ())

    def test_context_free_lint_rejects_heading_timing_and_internal_artifacts(self):
        encoded = context(cameras=())
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=()), encoded
        )

        shot_one_clock = compiled.replace("[Shot 1]", "[Shot 1] At 00:00.000,")
        self.assertTrue(lint_direct_ref2v_multishot_prompt(shot_one_clock))

        backwards = compiled.replace(
            "[Shot 3] At 00:07.000,",
            "[Shot 3] At 00:02.000,",
        )
        self.assertIn(
            "Shot 2 and Shot 3 timestamps must increase strictly.",
            lint_direct_ref2v_multishot_prompt(backwards),
        )

        internal = compiled.replace(
            "A stable moonlit courtyard",
            "scene_setup:\nA stable moonlit courtyard",
        )
        self.assertTrue(
            any(
                "internal field scene_setup" in error
                for error in lint_direct_ref2v_multishot_prompt(internal)
            )
        )

        placeholder = compiled.replace(
            "The first subject",
            "[[camera:camera_1]] The first subject",
        )
        self.assertTrue(
            any(
                "placeholder" in error
                for error in lint_direct_ref2v_multishot_prompt(placeholder)
            )
        )

    def test_context_free_lint_rejects_noncontiguous_or_repeated_picture_labels(self):
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=()), context(cameras=())
        )

        noncontiguous = compiled.replace("<Picture 2>", "<Picture 3>")
        self.assertTrue(
            any(
                "contiguous" in error
                for error in lint_direct_ref2v_multishot_prompt(noncontiguous)
            )
        )

        repeated = compiled.replace(
            "A stable moonlit courtyard",
            "<Picture 1> A stable moonlit courtyard",
        )
        self.assertTrue(
            any(
                "exactly once" in error
                for error in lint_direct_ref2v_multishot_prompt(repeated)
            )
        )

    def test_rejects_placeholder_in_wrong_shot_or_after_first_sentence(self):
        encoded = context(cameras=(2,))
        wrong_shot = editable(cameras=(1,)).replace("camera_1", "camera_2")
        with self.assertRaisesRegex(ValueError, "must remain in Shot 2"):
            compile_direct_ref2v_multishot_document(wrong_shot, encoded)

        late = editable(cameras=(2,)).replace(
            "[[camera:camera_2]] A hard cut reveals",
            "A hard cut reveals the gate. [[camera:camera_2]] It reveals",
        )
        with self.assertRaisesRegex(ValueError, "must begin Shot 2"):
            compile_direct_ref2v_multishot_document(late, encoded)

    def test_rejects_model_owned_heading_or_timestamp(self):
        encoded = context(cameras=())
        with_heading = editable(cameras=()).replace(
            "A hard cut reveals", "[Shot 2] A hard cut reveals"
        )
        with self.assertRaisesRegex(ValueError, "must not contain compiled shot headings"):
            compile_direct_ref2v_multishot_document(with_heading, encoded)

        with_timestamp = editable(cameras=()).replace(
            "A hard cut reveals", "At 00:03.200, A hard cut reveals"
        )
        with self.assertRaisesRegex(ValueError, "must not contain compiled timestamps"):
            compile_direct_ref2v_multishot_document(with_timestamp, encoded)

        timestamp_without_comma = editable(cameras=()).replace(
            "A hard cut reveals", "At 00:03.200 A hard cut reveals"
        )
        with self.assertRaisesRegex(ValueError, "must not contain compiled timestamps"):
            compile_direct_ref2v_multishot_document(
                timestamp_without_comma, encoded
            )

    def test_contextual_lint_rejects_a_manually_moved_camera_clause(self):
        encoded = context(cameras=(1,))
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=(1,)), encoded
        )
        clause = (
            "The camera pushes in with small amplitude at slow speed, "
            "following the subject."
        )
        moved = compiled.replace(
            f"[Shot 1] {clause} The first subject crosses the arch",
            f"[Shot 1] The first subject crosses the arch. {clause} The subject",
        )

        self.assertIn(
            "Compiled camera clause must begin Shot 1.",
            lint_direct_ref2v_multishot_prompt(moved, encoded),
        )
        with self.assertRaisesRegex(ValueError, "must begin Shot 1"):
            rehydrate_direct_ref2v_multishot_editable_document(moved, encoded)

    def test_context_free_lint_detects_an_extra_timestamp_without_comma(self):
        compiled = compile_direct_ref2v_multishot_document(
            editable(cameras=()), context(cameras=())
        )
        manually_edited = compiled.replace(
            "The first subject crosses",
            "At 00:01.500 the first subject crosses",
        )

        self.assertIn(
            "The compiled multi-shot prompt must contain only its two cut timestamps.",
            lint_direct_ref2v_multishot_prompt(manually_edited),
        )

    def test_rehydrate_round_trip_restores_six_fields_and_placeholders(self):
        encoded = context(cameras=(1, 3))
        source = editable(cameras=(1, 3))
        compiled = compile_direct_ref2v_multishot_document(source, encoded)
        rehydrated = rehydrate_direct_ref2v_multishot_editable_document(
            compiled, encoded
        )

        self.assertEqual(
            tuple(rehydrated.count(f"{field}:") for field in MULTISHOT_EDITABLE_FIELDS),
            (1, 1, 1, 1, 1, 1),
        )
        self.assertIn("shot_1:\n[[camera:camera_1]]", rehydrated)
        self.assertIn("shot_3:\n[[camera:camera_3]]", rehydrated)
        self.assertEqual(
            compile_direct_ref2v_multishot_document(rehydrated, encoded),
            compiled,
        )

    def test_identical_camera_clauses_in_different_shots_round_trip(self):
        directives = (
            camera(1, H3CameraMotion.PUSH_IN),
            camera(3, H3CameraMotion.PUSH_IN),
        )
        encoded = encode_direct_ref2v_multishot_context(
            HEADER,
            directives,
            {"camera_1": 1, "camera_3": 3},
            (0, 3200, 7000),
            11_500,
            12_500,
        )
        source = editable(cameras=(1, 3))

        compiled = compile_direct_ref2v_multishot_document(source, encoded)
        rehydrated = rehydrate_direct_ref2v_multishot_editable_document(
            compiled, encoded
        )

        clause = "The camera pushes in with small amplitude at slow speed, following the subject."
        self.assertEqual(compiled.count(clause), 2)
        self.assertEqual(lint_direct_ref2v_multishot_prompt(compiled, encoded), ())
        self.assertIn("shot_1:\n[[camera:camera_1]]", rehydrated)
        self.assertIn("shot_3:\n[[camera:camera_3]]", rehydrated)
        self.assertEqual(
            compile_direct_ref2v_multishot_document(rehydrated, encoded),
            compiled,
        )

    def test_normalizer_only_repairs_harmless_layout(self):
        value = editable(cameras=(2,)).replace(
            "shot_2:\n[[camera:camera_2]]",
            "shot_2: [[camera:camera_2]].",
        )
        normalized = normalize_direct_ref2v_multishot_camera_placeholders(value)

        self.assertIn("shot_2:\n[[camera:camera_2]]", normalized)
        self.assertNotIn("[[camera:camera_2]].", normalized)


if __name__ == "__main__":
    unittest.main()
