import unittest

from panelforge.application.direct_fl2va_prompt import (
    DirectFL2VAContext,
    H3BaseInputMode,
    compile_direct_fl2va_document,
    compile_h3_base_header,
    decode_direct_fl2va_context,
    derive_h3_base_input_mode,
    encode_direct_fl2va_context,
    lint_direct_fl2va_prompt,
    requested_h3_base_duration_ms,
    rehydrate_direct_fl2va_document,
)
from panelforge.domain import (
    PromptLabSession,
    PromptReference,
    PromptSessionMode,
    ReferenceUse,
)


BODY = (
    "integrated_multimodal_description:\n"
    "[Shot 1] The target video is one continuous 6-second shot. A runner crosses "
    "the room and settles into the requested final state.\n"
    "overall_soundscape:\n"
    "Footsteps cross a quiet room.\n"
    "non_diegetic_music:\n"
    "N/A"
)


def session_for(*roles: str) -> PromptLabSession:
    references = tuple(
        PromptReference(
            reference_id=f"reference-{index}",
            asset_id=f"asset-{index}",
            role=role,
            label=f"{role}.png",
            uses=(ReferenceUse(role),),
        )
        for index, role in enumerate(roles, 1)
    )
    return PromptLabSession(
        session_id="session-1",
        model_id="vision-model",
        profile_id="minimax.h3.fl2va.direct",
        profile_version="0.1.0",
        references=references,
        session_mode=PromptSessionMode.H3_BASE,
    )


class DirectFL2VAPromptTest(unittest.TestCase):
    def test_extracts_one_explicit_french_or_english_total_duration(self):
        self.assertEqual(
            requested_h3_base_duration_ms("Plan unique de 7 secondes."),
            7000,
        )
        self.assertEqual(
            requested_h3_base_duration_ms("One continuous 6.5-second shot."),
            6500,
        )
        self.assertEqual(
            requested_h3_base_duration_ms(
                "At 0.00 seconds, begin one continuous 7-second shot."
            ),
            7000,
        )
        self.assertIsNone(requested_h3_base_duration_ms("A short continuous shot."))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            requested_h3_base_duration_ms("Use 6 seconds, not 7 seconds.")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            requested_h3_base_duration_ms(
                "Plan de 6 secondes. Durée totale : 7 secondes."
            )

    def test_explicit_total_ignores_a_different_duration_in_a_pasted_bad_output(self):
        source = (
            "Plan unique de 12 secondes.\n\n"
            "Le dernier run n'était pas bon, il ressemblait à ça :\n"
            "The target video is one continuous 13-second shot.\n"
            "At 00:12.000, the final state appears."
        )
        self.assertEqual(requested_h3_base_duration_ms(source), 12000)

    def test_derives_all_four_modes_from_ordered_optional_frames(self):
        cases = (
            ((), (), H3BaseInputMode.T2VA),
            (("first_frame",), (("reference-1", 1),), H3BaseInputMode.I2VA),
            (("last_frame",), (("reference-1", 1),), H3BaseInputMode.L2VA),
            (
                ("first_frame", "last_frame"),
                (("reference-1", 1), ("reference-2", 2)),
                H3BaseInputMode.FL2VA,
            ),
        )
        for roles, mapping, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(derive_h3_base_input_mode(session_for(*roles), mapping), expected)

    def test_compiles_the_exact_official_header_for_each_mode(self):
        expected = {
            H3BaseInputMode.T2VA: "",
            H3BaseInputMode.I2VA: (
                "For the target video, at 0.00 seconds into the target video, "
                "<Picture 1> (from [Shot 1]) is fully referenced."
            ),
            H3BaseInputMode.L2VA: (
                "How the reference pictures align with the target video — "
                "<Picture 1> (from [Shot 1]) aligns with the 6.00-second mark "
                "of the target video."
            ),
            H3BaseInputMode.FL2VA: (
                "How the reference pictures align with the target video — Picture 1 "
                "(from Shot 1) aligns with the 0.00-second mark of the target video; "
                "Picture 2 (from Shot 1) aligns with the 6.00-second mark of the target video."
            ),
        }
        for mode, header in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(compile_h3_base_header(mode, 6000), header)

    def test_compiles_lints_rehydrates_and_round_trips_context_for_every_mode(self):
        for mode in H3BaseInputMode:
            with self.subTest(mode=mode):
                context = DirectFL2VAContext(
                    mode=mode,
                    header=compile_h3_base_header(mode, 6000),
                    duration_ms=6000,
                    placements=(),
                )
                compiled = compile_direct_fl2va_document(BODY, context)
                self.assertEqual(lint_direct_fl2va_prompt(compiled, context), ())
                self.assertEqual(rehydrate_direct_fl2va_document(compiled, context), BODY)
                self.assertEqual(decode_direct_fl2va_context(encode_direct_fl2va_context(context)), context)

    def test_only_reserved_dialogue_placeholders_can_cross_the_intermediate_lint(self):
        context = DirectFL2VAContext(
            mode=H3BaseInputMode.T2VA,
            header="",
            duration_ms=6000,
            placements=(),
        )
        pending = BODY.replace(
            "A runner crosses",
            "[[dialogue:dialogue_1]] A runner crosses",
        )

        with self.assertRaisesRegex(ValueError, "unresolved camera placeholder"):
            compile_direct_fl2va_document(pending, context)
        compiled = compile_direct_fl2va_document(
            pending,
            context,
            allow_dialogue_placeholders=True,
        )

        self.assertIn("[[dialogue:dialogue_1]]", compiled)
        self.assertEqual(
            lint_direct_fl2va_prompt(
                compiled,
                context,
                allow_dialogue_placeholders=True,
            ),
            (),
        )
        self.assertTrue(lint_direct_fl2va_prompt(compiled, context))
        malformed = pending.replace("dialogue_1", "unknown")
        with self.assertRaisesRegex(ValueError, "unresolved camera placeholder"):
            compile_direct_fl2va_document(
                malformed,
                context,
                allow_dialogue_placeholders=True,
            )

    def test_rejects_reversed_first_and_last_frame_bindings(self):
        session = session_for("first_frame", "last_frame")
        with self.assertRaisesRegex(ValueError, "first frame before last frame"):
            derive_h3_base_input_mode(
                session,
                (("reference-2", 1), ("reference-1", 2)),
            )


if __name__ == "__main__":
    unittest.main()
