import unittest

from panelforge.application.direct_ref2v_multishot_prompt import (
    encode_direct_ref2v_multishot_context,
)
from panelforge.application.direct_ref2v_multishot_prompt_v2 import (
    compile_direct_ref2v_multishot_document_v2,
    decode_direct_ref2v_multishot_context_v2,
    direct_ref2v_multishot_editable_contract_v2,
    direct_ref2v_multishot_editable_fields_v2,
    encode_direct_ref2v_multishot_context_v2,
    is_direct_ref2v_multishot_context_v2,
    lint_direct_ref2v_multishot_prompt_v2,
    rehydrate_direct_ref2v_multishot_editable_document_v2,
)
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


def camera(number: int, motion=H3CameraMotion.PUSH_IN) -> H3CameraDirective:
    return H3CameraDirective(
        directive_id=f"camera_{number}",
        motion=motion,
        amplitude=H3CameraAmplitude.SMALL,
        speed=H3CameraSpeed.SLOW,
        target_clause="following the subject",
    )


def starts(shot_count: int) -> tuple[int, ...]:
    return tuple(number * 3_000 for number in range(shot_count))


def context(shot_count: int, cameras=()) -> str:
    shot_starts = starts(shot_count)
    camera_numbers = set(cameras)
    return encode_direct_ref2v_multishot_context_v2(
        HEADER,
        shot_starts,
        shot_starts[1:],
        tuple(
            camera(number) if number in camera_numbers else None
            for number in range(1, shot_count + 1)
        ),
        shot_starts[-1] + 2_500,
        shot_starts[-1] + 3_500,
    )


def editable(shot_count: int) -> str:
    sections = [
        "scene_setup:\nA moonlit courtyard establishes one subject and a stone arch."
    ]
    for number in range(1, shot_count + 1):
        sections.append(
            f"shot_{number}:\n"
            f"The subject performs action {number} and reaches a distinct visible state."
        )
    sections.extend(
        (
            "overall_soundscape:\nNight ambience, footsteps, cloth, and a gate hinge.",
            "non_diegetic_music:\nN/A",
        )
    )
    return "\n\n".join(sections)


class DirectRef2VMultiShotPromptV2Test(unittest.TestCase):
    def test_dynamic_fields_and_context_round_trip_for_two_shots(self):
        fields = direct_ref2v_multishot_editable_fields_v2(2)
        encoded = context(2, cameras=(2,))
        decoded = decode_direct_ref2v_multishot_context_v2(encoded)

        self.assertEqual(
            fields,
            (
                "scene_setup",
                "shot_1",
                "shot_2",
                "overall_soundscape",
                "non_diegetic_music",
            ),
        )
        self.assertEqual(
            direct_ref2v_multishot_editable_contract_v2(2).markers,
            tuple(f"{field}:" for field in fields),
        )
        self.assertTrue(is_direct_ref2v_multishot_context_v2(encoded))
        self.assertEqual(decoded.header, HEADER)
        self.assertEqual(decoded.shot_starts_ms, (0, 3_000))
        self.assertEqual(decoded.hard_cut_times_ms, (3_000,))
        self.assertEqual(decoded.shot_count, 2)
        self.assertIsNone(decoded.camera_for(1))
        self.assertEqual(decoded.camera_for(2).directive_id, "camera_2")

        v1 = encode_direct_ref2v_multishot_context(
            HEADER,
            (),
            {},
            (0, 3_000, 6_000),
            8_500,
            9_500,
        )
        with self.assertRaisesRegex(ValueError, "V2 compiler context"):
            decode_direct_ref2v_multishot_context_v2(v1)

    def test_compiles_two_shots_with_owned_camera_and_exact_cut(self):
        encoded = context(2, cameras=(1, 2))
        compiled = compile_direct_ref2v_multishot_document_v2(editable(2), encoded)

        clause = (
            "The camera pushes in with small amplitude at slow speed, "
            "following the subject."
        )
        self.assertTrue(compiled.startswith(HEADER + "\n\n"))
        self.assertIn(f"[Shot 1] {clause} The subject performs action 1", compiled)
        self.assertIn(
            f"[Shot 2] At 00:03.000, {clause} The subject performs action 2",
            compiled,
        )
        self.assertNotIn("[[", compiled)
        self.assertNotIn("shot_1:", compiled)
        self.assertEqual(lint_direct_ref2v_multishot_prompt_v2(compiled, encoded), ())

    def test_three_shot_gap_round_trip_never_exposes_camera(self):
        encoded = context(3, cameras=(2,))
        source = editable(3)
        compiled = compile_direct_ref2v_multishot_document_v2(source, encoded)
        rehydrated = rehydrate_direct_ref2v_multishot_editable_document_v2(
            compiled, encoded
        )

        self.assertNotIn("The camera", rehydrated)
        self.assertNotIn("[[camera:", rehydrated)
        self.assertIn("shot_2:\nThe subject performs action 2", rehydrated)
        self.assertEqual(
            compile_direct_ref2v_multishot_document_v2(rehydrated, encoded),
            compiled,
        )

    def test_six_shots_support_gaps_and_identical_camera_clauses(self):
        encoded = context(6, cameras=(1, 3, 6))
        compiled = compile_direct_ref2v_multishot_document_v2(editable(6), encoded)

        clause = (
            "The camera pushes in with small amplitude at slow speed, "
            "following the subject."
        )
        self.assertEqual(compiled.count(clause), 3)
        self.assertIn("[Shot 5] At 00:12.000, The subject performs action 5", compiled)
        self.assertIn(f"[Shot 6] At 00:15.000, {clause}", compiled)
        self.assertEqual(lint_direct_ref2v_multishot_prompt_v2(compiled), ())
        self.assertEqual(lint_direct_ref2v_multishot_prompt_v2(compiled, encoded), ())
        rehydrated = rehydrate_direct_ref2v_multishot_editable_document_v2(
            compiled, encoded
        )
        self.assertEqual(
            compile_direct_ref2v_multishot_document_v2(rehydrated, encoded),
            compiled,
        )

    def test_compiles_with_zero_cameras(self):
        encoded = context(3)
        compiled = compile_direct_ref2v_multishot_document_v2(editable(3), encoded)

        self.assertNotIn("The camera", compiled)
        self.assertIn("[Shot 1] The subject performs action 1", compiled)
        self.assertIn("[Shot 3] At 00:06.000, The subject performs action 3", compiled)
        self.assertEqual(lint_direct_ref2v_multishot_prompt_v2(compiled, encoded), ())

    def test_context_rejects_range_cut_mismatch_and_wrong_camera_owner(self):
        with self.assertRaisesRegex(ValueError, "between 2 and 6"):
            direct_ref2v_multishot_editable_fields_v2(1)
        with self.assertRaisesRegex(ValueError, "between 2 and 6"):
            context(7)
        with self.assertRaisesRegex(ValueError, "must equal"):
            encode_direct_ref2v_multishot_context_v2(
                HEADER,
                (0, 3_000, 6_000),
                (3_100, 6_000),
                (None, None, None),
                8_000,
                9_000,
            )
        with self.assertRaisesRegex(ValueError, "owning shot"):
            encode_direct_ref2v_multishot_context_v2(
                HEADER,
                (0, 3_000),
                (3_000,),
                (None, camera(1)),
                5_000,
                6_000,
            )

    def test_writer_rejects_wrong_fields_order_and_number(self):
        encoded = context(3)
        missing = editable(3).replace(
            "\n\nshot_2:\nThe subject performs action 2 and reaches a distinct visible state.",
            "",
        )
        with self.assertRaisesRegex(ValueError, "missing marker: shot_2"):
            compile_direct_ref2v_multishot_document_v2(missing, encoded)

        extra = editable(3).replace(
            "overall_soundscape:",
            "shot_4:\nAn unplanned shot.\n\noverall_soundscape:",
        )
        with self.assertRaisesRegex(ValueError, "wrong number or order"):
            compile_direct_ref2v_multishot_document_v2(extra, encoded)

        unknown = editable(3).replace(
            "overall_soundscape:",
            "notes:\nAn unplanned section.\n\noverall_soundscape:",
        )
        with self.assertRaisesRegex(ValueError, "wrong number or order"):
            compile_direct_ref2v_multishot_document_v2(unknown, encoded)

        swapped = editable(3).replace("shot_1:", "shot_x:").replace(
            "shot_2:", "shot_1:"
        ).replace("shot_x:", "shot_2:")
        with self.assertRaisesRegex(ValueError, "markers are out of order"):
            compile_direct_ref2v_multishot_document_v2(swapped, encoded)

    def test_writer_rejects_placeholder_heading_timestamp_and_camera_prose(self):
        encoded = context(3, cameras=(1,))
        cases = (
            ("The subject performs action 1", "[[camera:camera_1]] The subject performs action 1", "placeholders"),
            ("The subject performs action 1", "[Shot 1] The subject performs action 1", "shot headings"),
            ("The subject performs action 1", "At 00:01.000, The subject performs action 1", "timestamps"),
            ("The subject performs action 1", "The camera slowly pushes in. The subject performs action 1", "camera movement prose"),
        )
        for old, new, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    compile_direct_ref2v_multishot_document_v2(
                        editable(3).replace(old, new), encoded
                    )

    def test_writer_rejects_unplanned_canonical_camera_with_no_camera_context(self):
        for cameras in ((), (2,)):
            encoded = context(3, cameras=cameras)
            for camera_sentence in (
                "The camera holds a static shot.",
                "The shot adopts the subject's POV.",
                "The camera rolls clockwise.",
            ):
                with self.subTest(
                    cameras=cameras,
                    camera_sentence=camera_sentence,
                ):
                    writer = editable(3).replace(
                        "The subject performs action 1",
                        f"{camera_sentence} The subject performs action 1",
                    )
                    with self.assertRaisesRegex(ValueError, "movement prose"):
                        compile_direct_ref2v_multishot_document_v2(writer, encoded)

    def test_contextual_lint_rejects_moved_camera_clause(self):
        encoded = context(3, cameras=(2,))
        compiled = compile_direct_ref2v_multishot_document_v2(editable(3), encoded)
        clause = (
            "The camera pushes in with small amplitude at slow speed, "
            "following the subject."
        )
        moved = compiled.replace(
            f"[Shot 2] At 00:03.000, {clause} The subject performs action 2",
            f"[Shot 2] At 00:03.000, The subject moves. {clause} The subject performs action 2",
        )

        self.assertTrue(
            any(
                "Shot 2" in error and "start" in error
                for error in lint_direct_ref2v_multishot_prompt_v2(moved, encoded)
            )
        )
        with self.assertRaisesRegex(ValueError, "Shot 2"):
            rehydrate_direct_ref2v_multishot_editable_document_v2(moved, encoded)

    def test_contextual_lint_rejects_missing_duplicate_and_wrong_shot_camera(self):
        encoded = context(3, cameras=(1, 3))
        compiled = compile_direct_ref2v_multishot_document_v2(editable(3), encoded)
        clause = (
            "The camera pushes in with small amplitude at slow speed, "
            "following the subject."
        )

        missing = compiled.replace(f"[Shot 1] {clause} ", "[Shot 1] ", 1)
        duplicate = compiled.replace(
            f"[Shot 1] {clause} ", f"[Shot 1] {clause} {clause} ", 1
        )
        wrong_shot = compiled.replace(f"[Shot 1] {clause} ", "[Shot 1] ", 1).replace(
            "[Shot 2] At 00:03.000, ",
            f"[Shot 2] At 00:03.000, {clause} ",
            1,
        )
        for altered in (missing, duplicate, wrong_shot):
            with self.subTest():
                self.assertTrue(
                    any(
                        "camera clause occurrence count" in error
                        for error in lint_direct_ref2v_multishot_prompt_v2(
                            altered, encoded
                        )
                    )
                )

    def test_lint_rejects_wrong_heading_timestamp_and_extra_clock(self):
        encoded = context(3)
        compiled = compile_direct_ref2v_multishot_document_v2(editable(3), encoded)

        wrong_cut = compiled.replace("[Shot 2] At 00:03.000,", "[Shot 2] At 00:03.500,")
        self.assertIn(
            "Compiled multi-shot V2 cut timestamps must match the derived shot starts.",
            lint_direct_ref2v_multishot_prompt_v2(wrong_cut, encoded),
        )
        extra_clock = compiled.replace(
            "The subject performs action 1",
            "At 00:01.000, The subject performs action 1",
        )
        self.assertTrue(lint_direct_ref2v_multishot_prompt_v2(extra_clock, encoded))


if __name__ == "__main__":
    unittest.main()
