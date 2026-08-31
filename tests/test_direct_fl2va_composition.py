import json
import tempfile
import unittest

from panelforge.application import PromptCompositionService
from panelforge.application import StreamEventKind
from panelforge.application.direct_fl2va_prompt import (
    H3BaseInputMode,
    compile_h3_base_header,
    decode_direct_fl2va_context,
    lint_direct_fl2va_prompt,
)
from panelforge.domain import (
    BriefReferenceSnapshot,
    BriefRevision,
    CompositionStage,
    CookbookBinding,
    PromptLabSession,
    PromptReference,
    PromptSessionMode,
    ReferenceUse,
    RevisionOrigin,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)
from tests.test_direct_i2v_composition import DirectI2VGateway, action_plan


from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKBOOK_ROOT = PROJECT_ROOT / "prompt_cookbooks"
PNG = b"\x89PNG\r\n\x1a\nh3-base-frame"


def configured_service(
    directory: str,
    roles: tuple[str, ...],
    *,
    source_text: str = "A runner crosses the room and settles.",
    profile_version: str = "0.1.0",
    cookbook_version: str = "0.1.0",
):
    asset_numbers = iter(range(1, len(roles) + 1))
    assets = LocalAssetStore(
        directory,
        id_factory=lambda: f"asset-{next(asset_numbers)}",
    )
    references = []
    for index, role in enumerate(roles, 1):
        asset = assets.create(PNG + str(index).encode("ascii"), "image/png")
        references.append(
            PromptReference(
                reference_id=f"reference-{index}",
                asset_id=asset.asset_id,
                role=role,
                label=f"{role}.png",
                uses=(ReferenceUse(role),),
            )
        )
    references_tuple = tuple(references)
    session = PromptLabSession(
        session_id="h3-base-session",
        model_id="vision-model",
        profile_id="minimax.h3.fl2va.direct",
        profile_version=profile_version,
        references=references_tuple,
        session_mode=PromptSessionMode.H3_BASE,
    )
    brief = BriefRevision(
        revision_id="brief-1",
        source_text=source_text,
        content="BRIEF_SENTINEL. One continuous visible action.",
        creative_freedom=35,
        origin=RevisionOrigin.MODEL,
        references=tuple(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=None,
                uses=reference.uses,
                evidence_policy=reference.evidence_policy,
            )
            for reference in references_tuple
        ),
    )
    session = session.add_brief_revision(brief).approve_brief()
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = DirectI2VGateway(with_camera=False, camera_owned=True)
    service = PromptCompositionService(
        gateway=gateway,
        cookbooks=LocalPromptCookbookCatalog(COOKBOOK_ROOT),
        sessions=sessions,
        compositions=LocalPromptCompositionStore(directory),
        assets=assets,
    )
    by_role = {reference.role: reference.reference_id for reference in references_tuple}
    service.configure(
        session.session_id,
        "minimax.h3.fl2va.direct",
        cookbook_version,
        (
            CookbookBinding("first_frame", ((by_role["first_frame"],) if "first_frame" in by_role else ())),
            CookbookBinding("last_frame", ((by_role["last_frame"],) if "last_frame" in by_role else ())),
        ),
    )
    return service, gateway


class DirectFL2VACompositionTest(unittest.TestCase):
    def test_h3_base_silently_recovers_partial_parallel_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame",),
                source_text="Plan unique de 8 secondes.",
            )
            original_content = gateway._content

            def overlapping_plan(request):
                if request.operation_id != "action_plan.generate":
                    return original_content(request)
                plan = action_plan(with_camera=False)
                plan["beats"][0]["steps"] = [
                    {
                        "step_id": "boat_motion",
                        "start_ms": 0,
                        "end_ms": 5000,
                        "action": "The boat glides forward.",
                        "continuity_after": "The boat remains on the river axis.",
                    },
                    {
                        "step_id": "light_motion",
                        "start_ms": 3000,
                        "end_ms": 8000,
                        "action": "The lotus lights pulse.",
                        "continuity_after": "The lights remain reflected in the water.",
                    },
                ]
                return json.dumps(plan)

            gateway._content = overlapping_plan
            composition = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            plan = json.loads(composition.beat_sheet.active_revision.content)
            self.assertEqual(len(plan["beats"][0]["steps"]), 1)
            self.assertIn(
                "parallel_steps_merged:kick",
                plan["technical_adjustments"],
            )
            plan_status = next(
                item
                for item in service.status(composition)
                if item.stage is CompositionStage.BEAT_SHEET
            )
            self.assertFalse(
                any(
                    "paralle" in warning.lower()
                    for warning in plan_status.validation_warnings
                )
            )

    def test_explicit_duration_includes_the_hold_and_filenames_stay_out_of_llm_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("last_frame",),
                source_text="Plan unique de 8 secondes.",
            )
            planned = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            plan_request = gateway.requests[-1]
            self.assertEqual(plan_request.max_tokens, 262_144)
            self.assertNotIn("last_frame.png", plan_request.user_prompt)
            self.assertNotIn("last_frame.png", plan_request.images[0].label)
            plan = json.loads(planned.beat_sheet.active_revision.content)
            self.assertEqual(plan["beats"][-1]["end_ms"], 8000)
            self.assertEqual(plan["final_state"]["final_hold_ms"], 0)
            self.assertEqual(
                plan["technical_adjustments"],
                ["final_hold_adjusted:1500:0"],
            )

            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
            )
            writer_request = gateway.requests[-1]
            self.assertEqual(writer_request.max_tokens, 262_144)
            self.assertNotIn("last_frame.png", writer_request.user_prompt)
            final = composition.final_prompt.active_revision
            self.assertIn("aligns with the 8.00-second mark", final.content)
            self.assertIn("one continuous 8-second shot", final.content)
            self.assertNotIn("last_frame.png", final.content)

    def test_current_explicit_duration_wins_over_a_pasted_rejected_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _ = configured_service(
                directory,
                ("first_frame",),
                source_text=(
                    "Plan unique de 8 secondes.\n"
                    "Ancien résultat à ne pas reproduire :\n"
                    "The target video is one continuous 10-second shot."
                ),
            )
            composition = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            plan = json.loads(composition.beat_sheet.active_revision.content)
            self.assertEqual(plan["beats"][-1]["end_ms"], 8000)
            self.assertEqual(plan["final_state"]["final_hold_ms"], 0)

    def test_streaming_applies_the_same_explicit_total_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _ = configured_service(
                directory,
                ("first_frame",),
                source_text="Plan unique sans coupure de 8 secondes.",
            )
            events = list(
                service.stream_generate(
                    "h3-base-session",
                    CompositionStage.BEAT_SHEET,
                )
            )
            completed = next(
                event for event in events if event.kind is StreamEventKind.COMPLETED
            )
            plan = json.loads(completed.composition.beat_sheet.active_revision.content)
            self.assertEqual(plan["final_state"]["final_hold_ms"], 0)

    def test_h3_base_timing_errors_do_not_use_the_legacy_i2va_name(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame",),
                source_text="Plan unique de 8 secondes.",
            )
            service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            original_content = gateway._content

            def without_final_landmark(request):
                return original_content(request).replace("At 00:08.000,", "Finally,")

            gateway._content = without_final_landmark
            with self.assertRaisesRegex(ValueError, "H3 Base final prompt") as raised:
                service.generate("h3-base-session", CompositionStage.FINAL_PROMPT)
            self.assertNotIn("direct I2VA", str(raised.exception))

    def test_final_prompt_rejects_a_leaked_local_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(directory, ("first_frame",))
            service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            original_content = gateway._content

            def with_filename(request):
                return original_content(request).replace(
                    "The visible player",
                    "The visible player from first_frame.png",
                )

            gateway._content = with_filename
            with self.assertRaisesRegex(ValueError, "source filename"):
                service.generate("h3-base-session", CompositionStage.FINAL_PROMPT)

    def test_four_input_modes_share_one_compact_recipe_and_compile_exact_headers(self):
        cases = (
            ((), H3BaseInputMode.T2VA),
            (("first_frame",), H3BaseInputMode.I2VA),
            (("last_frame",), H3BaseInputMode.L2VA),
            (("first_frame", "last_frame"), H3BaseInputMode.FL2VA),
        )
        for roles, mode in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, gateway = configured_service(directory, roles)
                service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
                plan_request = gateway.requests[-1]
                self.assertEqual(len(plan_request.images), len(roles))
                self.assertIn(f"MODE: {mode.value.upper()}.", plan_request.user_prompt)
                self.assertIn("BRIEF_SENTINEL", plan_request.user_prompt)
                service.approve("h3-base-session", CompositionStage.BEAT_SHEET)

                composition = service.generate(
                    "h3-base-session",
                    CompositionStage.FINAL_PROMPT,
                )
                writer_request = gateway.requests[-1]
                self.assertEqual(writer_request.images, ())
                self.assertNotIn("BRIEF_SENTINEL", writer_request.user_prompt)
                self.assertIn(f"MODE: {mode.value.upper()}.", writer_request.user_prompt)
                final = composition.final_prompt.active_revision
                self.assertIsNotNone(final)
                expected_header = compile_h3_base_header(mode, 9500)
                if expected_header:
                    self.assertTrue(final.content.startswith(expected_header + "\n\n"))
                else:
                    self.assertTrue(final.content.startswith("integrated_multimodal_description:"))
                context = decode_direct_fl2va_context(final.compiler_context or "")
                self.assertEqual(context.mode, mode)
                self.assertEqual(lint_direct_fl2va_prompt(final.content, context), ())

    def test_h3_base_and_legacy_i2v_cookbooks_cannot_be_cross_wired(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _ = configured_service(directory, ("first_frame",))
            with self.assertRaisesRegex(ValueError, "H3 Base sessions require"):
                service.configure(
                    "h3-base-session",
                    "minimax.h3.i2v.direct",
                    "0.2.0",
                    (CookbookBinding("first_frame", ("reference-1",)),),
                )

    def test_last_frame_revision_preserves_the_compiled_mode_header(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _ = configured_service(directory, ("last_frame",))
            service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            generated = service.generate(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
            )
            generated_header = generated.final_prompt.active_revision.content.split("\n", 1)[0]

            revised = service.revise(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
                "Shorten only the soundscape.",
            )
            active = revised.final_prompt.active_revision
            self.assertEqual(active.content.split("\n", 1)[0], generated_header)
            context = decode_direct_fl2va_context(active.compiler_context or "")
            self.assertEqual(context.mode, H3BaseInputMode.L2VA)
            self.assertEqual(lint_direct_fl2va_prompt(active.content, context), ())


if __name__ == "__main__":
    unittest.main()
