import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application import CompletionResult, PromptCompositionService
from panelforge.application.direct_fl2va_multishot_plan import (
    canonical_direct_fl2va_multishot_plan,
    direct_fl2va_multishot_writer_plan,
    parse_direct_fl2va_multishot_plan,
)
from panelforge.application.direct_fl2va_multishot_prompt import (
    DirectFL2VAMultiShotCompilerContext,
    compile_direct_fl2va_multishot_document,
    compile_h3_base_multishot_header,
    decode_direct_fl2va_multishot_context,
    encode_direct_fl2va_multishot_context,
    lint_direct_fl2va_multishot_prompt,
    rehydrate_direct_fl2va_multishot_document,
)
from panelforge.application.direct_fl2va_prompt import (
    H3BaseInputMode,
    normalize_h3_base_model_labels,
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
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def multishot_plan() -> dict:
    return {
        "scene_setup": "A woman waits inside a quiet apartment.",
        "continuity_invariants": [
            "The same two adults, apartment geometry and warm lighting persist."
        ],
        "shots": [
            {
                "duration_ms": 3500,
                "opening_composition": "A medium view frames the woman by the door",
                "purpose": "Establish the waiting woman and the closed door.",
                "new_information": "The handle begins to turn from outside.",
                "continuity_from_previous": None,
                "actions": ["She looks up as the handle turns."],
                "observable_end_state": "The door is partly open.",
                "camera": {
                    "motion": "push.in",
                    "amplitude": "small",
                    "speed": "slow",
                    "target_clause": "toward her alert expression",
                    "visible_change": "Her expression becomes readable.",
                },
            },
            {
                "duration_ms": 3500,
                "opening_composition": "A wider reverse view reveals the man entering",
                "purpose": "Reveal who opened the door.",
                "new_information": "The man offers his hand and she accepts it.",
                "continuity_from_previous": "The door continues the same opening motion.",
                "actions": ["He enters and she takes his hand."],
                "observable_end_state": "They face one another with joined hands.",
                "camera": None,
            },
        ],
        "final_state": {
            "description": "They remain together beside the open door",
            "final_hold_ms": 1000,
        },
        "dialogue_cues": [
            {
                "cue_id": "dialogue_1",
                "speaker_id": "S1",
                "speaker": "the woman",
                "start_ms": 1000,
                "language": "French",
                "delivery": "softly",
                "text": "Wrong draft text",
            }
        ],
        "risks": [],
        "technical_adjustments": [],
        "overall_soundscape": "Quiet room tone, door hardware and natural voices.",
        "non_diegetic_music": "N/A",
    }


def writer_body() -> str:
    return (
        "shot_1:\nShe looks up. [[dialogue:dialogue_1]]\n\n"
        "shot_2:\nHe enters, offers his hand, and she accepts it.\n\n"
        "overall_soundscape:\nQuiet room tone, door hardware and natural voices.\n\n"
        "non_diegetic_music:\nN/A"
    )


class Gateway:
    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        content = (
            json.dumps(multishot_plan())
            if request.operation_id == "action_plan.generate"
            else writer_body()
        )
        return CompletionResult(
            model_id=request.model_id,
            content=content,
            call_id=f"call-{len(self.requests)}",
        )


class H3BaseMultiShotTest(unittest.TestCase):
    def test_catalog_exposes_separate_profile_and_cookbook(self):
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        profile = profiles.get("minimax.h3.fl2va.direct.multishot", "0.1.0")
        self.assertEqual(profile.session_mode, PromptSessionMode.H3_BASE)
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        cookbook = cookbooks.get("minimax.h3.fl2va.direct.multishot", "0.1.0")
        self.assertEqual(cookbook.target_mode, "fl2va_direct")
        self.assertEqual(cookbook.writer_projection, "compact_multishot_dialogue_v1")

    def test_plan_restores_explicit_dialogue_and_derives_cuts(self):
        canonical = canonical_direct_fl2va_multishot_plan(
            json.dumps(multishot_plan()),
            recover_invalid_target=True,
            expected_dialogues=("Bonsoir",),
        )
        plan = parse_direct_fl2va_multishot_plan(canonical)
        self.assertEqual(plan.shot_starts_ms, (0, 3500))
        self.assertEqual(plan.hard_cut_times_ms, (3500,))
        self.assertEqual(plan.duration_ms, 8000)
        self.assertEqual(plan.dialogue_cues[0].text, "Bonsoir")
        projection = json.loads(direct_fl2va_multishot_writer_plan(canonical))
        self.assertEqual(projection["derived_timing"]["cut_times_ms"], [3500])
        self.assertNotIn("camera", json.dumps(projection))

    def test_compiler_owns_shots_cuts_cameras_frames_and_dialogue(self):
        canonical = canonical_direct_fl2va_multishot_plan(
            json.dumps(multishot_plan()),
            expected_dialogues=("Bonsoir",),
        )
        plan = parse_direct_fl2va_multishot_plan(canonical)
        context = DirectFL2VAMultiShotCompilerContext(
            mode=H3BaseInputMode.FL2VA,
            shot_starts_ms=plan.shot_starts_ms,
            shot_cameras=tuple(
                shot.camera.directive(number) if shot.camera else None
                for number, shot in enumerate(plan.shots, 1)
            ),
            opening_compositions=tuple(shot.opening_composition for shot in plan.shots),
            final_state_description=plan.final_state.description,
            final_state_start_ms=plan.final_state_start_ms,
            duration_ms=plan.duration_ms,
            dialogue_cues=plan.dialogue_cues,
        )
        encoded = encode_direct_fl2va_multishot_context(context)
        self.assertEqual(decode_direct_fl2va_multishot_context(encoded), context)
        compiled = compile_direct_fl2va_multishot_document(writer_body(), encoded)
        self.assertIn("Picture 2 (from Shot 2)", compiled)
        self.assertIn("[Shot 2] At 00:03.500, the camera cuts", compiled)
        self.assertIn("The camera pushes in with small amplitude at slow speed", compiled)
        self.assertIn("<d>[French] Bonsoir</d>", compiled)
        self.assertEqual(lint_direct_fl2va_multishot_prompt(compiled, encoded), ())
        self.assertEqual(
            rehydrate_direct_fl2va_multishot_document(compiled, encoded),
            writer_body(),
        )

    def test_fl2va_compiler_allows_canonical_picture_anchors_in_body(self):
        canonical = canonical_direct_fl2va_multishot_plan(
            json.dumps(multishot_plan()),
            expected_dialogues=("Bonsoir",),
        )
        plan = parse_direct_fl2va_multishot_plan(canonical)
        context = DirectFL2VAMultiShotCompilerContext(
            mode=H3BaseInputMode.FL2VA,
            shot_starts_ms=plan.shot_starts_ms,
            shot_cameras=(None, None),
            opening_compositions=(
                "Exact lock to Picture 1 at 0.00 seconds",
                "A wider throne-room view begins",
            ),
            final_state_description=(
                "The final composition settles exactly onto Picture 2"
            ),
            final_state_start_ms=plan.final_state_start_ms,
            duration_ms=plan.duration_ms,
            dialogue_cues=plan.dialogue_cues,
        )

        compiled = compile_direct_fl2va_multishot_document(writer_body(), context)

        self.assertEqual(lint_direct_fl2va_multishot_prompt(compiled, context), ())
        self.assertEqual(compiled.count("Picture 1"), 2)
        self.assertEqual(compiled.count("Picture 2"), 2)
        self.assertNotIn("<Image", compiled)

    def test_h3_base_label_normalization_is_mode_aware_and_preserves_dialogue(self):
        source = (
            "Exact lock to <Image 1>, then land on @image 2. "
            "<d>[English] Keep <Image 1> exactly.</d>"
        )
        self.assertEqual(
            normalize_h3_base_model_labels(source, H3BaseInputMode.FL2VA),
            (
                "Exact lock to Picture 1, then land on Picture 2. "
                "<d>[English] Keep <Image 1> exactly.</d>"
            ),
        )
        self.assertEqual(
            normalize_h3_base_model_labels("Land on <Image 1>", H3BaseInputMode.L2VA),
            "Land on <Picture 1>",
        )

    def test_headers_attach_last_frame_to_last_shot(self):
        self.assertEqual(compile_h3_base_multishot_header(H3BaseInputMode.T2VA, 8000, 3), "")
        self.assertIn(
            "<Picture 1> (from [Shot 1])",
            compile_h3_base_multishot_header(H3BaseInputMode.I2VA, 8000, 3),
        )
        self.assertIn(
            "<Picture 1> (from [Shot 3])",
            compile_h3_base_multishot_header(H3BaseInputMode.L2VA, 8000, 3),
        )
        self.assertIn(
            "Picture 2 (from Shot 3)",
            compile_h3_base_multishot_header(H3BaseInputMode.FL2VA, 8000, 3),
        )

        canonical = canonical_direct_fl2va_multishot_plan(
            json.dumps(multishot_plan()),
            expected_dialogues=("Bonsoir",),
        )
        plan = parse_direct_fl2va_multishot_plan(canonical)
        for mode in H3BaseInputMode:
            with self.subTest(mode=mode.value):
                context = DirectFL2VAMultiShotCompilerContext(
                    mode=mode,
                    shot_starts_ms=plan.shot_starts_ms,
                    shot_cameras=tuple(
                        shot.camera.directive(number) if shot.camera else None
                        for number, shot in enumerate(plan.shots, 1)
                    ),
                    opening_compositions=tuple(
                        shot.opening_composition for shot in plan.shots
                    ),
                    final_state_description=plan.final_state.description,
                    final_state_start_ms=plan.final_state_start_ms,
                    duration_ms=plan.duration_ms,
                    dialogue_cues=plan.dialogue_cues,
                )
                compiled = compile_direct_fl2va_multishot_document(
                    writer_body(),
                    context,
                )
                self.assertEqual(
                    lint_direct_fl2va_multishot_prompt(compiled, context),
                    (),
                )

    def test_service_keeps_two_generation_calls_after_an_approved_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            sessions = LocalPromptSessionStore(directory)
            session = PromptLabSession(
                session_id="base-multi",
                model_id="vision-model",
                profile_id="minimax.h3.fl2va.direct.multishot",
                profile_version="0.1.0",
                references=(),
                session_mode=PromptSessionMode.H3_BASE,
            )
            brief = BriefRevision(
                revision_id="brief-1",
                source_text='Deux personnes se retrouvent. Elle dit "Bonsoir".',
                content="Brief compact multi-plan avec dialogue_1 verbatim.",
                creative_freedom=35,
                origin=RevisionOrigin.MODEL,
                references=(),
            )
            sessions.create(session.add_brief_revision(brief).approve_brief())
            gateway = Gateway()
            service = PromptCompositionService(
                gateway=gateway,
                cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
                sessions=sessions,
                compositions=LocalPromptCompositionStore(directory),
                assets=LocalAssetStore(directory),
            )
            service.configure(
                "base-multi",
                "minimax.h3.fl2va.direct.multishot",
                "0.1.0",
                (
                    CookbookBinding("first_frame", ()),
                    CookbookBinding("last_frame", ()),
                ),
            )
            service.generate("base-multi", CompositionStage.BEAT_SHEET)
            service.approve("base-multi", CompositionStage.BEAT_SHEET)
            final = service.generate("base-multi", CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)
            self.assertIn("[Shot 2] At 00:03.500,", final.final_prompt.active_revision.content)
            self.assertEqual(
                final.final_prompt.active_revision.compiler_context.startswith(
                    "__PANELFORGE_FL2VA_MULTISHOT_CONTEXT_V1__:"
                ),
                True,
            )

    def test_service_canonicalizes_plan_image_aliases_for_the_compiled_fl2va_body(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = LocalAssetStore(directory)
            first_asset = assets.create(b"first", "image/png")
            last_asset = assets.create(b"last", "image/png")
            references = (
                PromptReference(
                    "reference-first",
                    first_asset.asset_id,
                    "first_frame",
                    "first.png",
                    uses=(ReferenceUse.FIRST_FRAME,),
                ),
                PromptReference(
                    "reference-last",
                    last_asset.asset_id,
                    "last_frame",
                    "last.png",
                    uses=(ReferenceUse.LAST_FRAME,),
                ),
            )
            session = PromptLabSession(
                session_id="base-multi-labels",
                model_id="vision-model",
                profile_id="minimax.h3.fl2va.direct.multishot",
                profile_version="0.1.0",
                references=references,
                session_mode=PromptSessionMode.H3_BASE,
            )
            brief = BriefRevision(
                revision_id="brief-labels",
                source_text="Relier exactement la première et la dernière frame.",
                content="Brief compact multi-plan sans dialogue.",
                creative_freedom=35,
                origin=RevisionOrigin.MODEL,
                references=tuple(
                    BriefReferenceSnapshot(
                        reference.reference_id,
                        None,
                        reference.uses,
                    )
                    for reference in references
                ),
            )
            sessions = LocalPromptSessionStore(directory)
            sessions.create(session.add_brief_revision(brief).approve_brief())

            class LabelGateway(Gateway):
                def complete(self, request):
                    self.requests.append(request)
                    if request.operation_id == "action_plan.generate":
                        plan = multishot_plan()
                        plan["dialogue_cues"] = []
                        plan["shots"][0]["opening_composition"] = (
                            "Exact lock to <Image 1> at 0.00 seconds"
                        )
                        plan["final_state"]["description"] = (
                            "The final composition settles exactly onto <Image 2>"
                        )
                        content = json.dumps(plan)
                    else:
                        content = writer_body().replace(
                            " [[dialogue:dialogue_1]]",
                            "",
                        )
                    return CompletionResult(
                        model_id=request.model_id,
                        content=content,
                        call_id=f"call-{len(self.requests)}",
                    )

            gateway = LabelGateway()
            service = PromptCompositionService(
                gateway=gateway,
                cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
                sessions=sessions,
                compositions=LocalPromptCompositionStore(directory),
                assets=assets,
            )
            service.configure(
                session.session_id,
                "minimax.h3.fl2va.direct.multishot",
                "0.1.0",
                (
                    CookbookBinding("first_frame", ("reference-first",)),
                    CookbookBinding("last_frame", ("reference-last",)),
                ),
            )
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            final = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            content = final.final_prompt.active_revision.content

            self.assertNotIn("<Image", content)
            self.assertEqual(content.count("Picture 1"), 2)
            self.assertEqual(content.count("Picture 2"), 2)


if __name__ == "__main__":
    unittest.main()
