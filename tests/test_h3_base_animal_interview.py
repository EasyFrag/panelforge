import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application import PromptCompositionService
from panelforge.application.direct_i2v_prompt import (
    apply_direct_i2v_timing,
    compile_animal_interview_dialogue_cues,
    compile_direct_i2v_dialogue_cues,
    lint_animal_interview_action_plan,
)
from panelforge.application.direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan_v4,
    direct_ref2v_animal_interview_writer_plan,
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
from panelforge.application.direct_fl2va_prompt import (
    H3BaseInputMode,
    compile_h3_base_header,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)
from tests.test_direct_i2v_composition import DirectI2VGateway


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\nanimal-interview-frame"


def interview_plan() -> dict:
    steps = [
        ("question_1", 0, 2300, "S1 delivers dialogue_1 while S2 listens with its mouth closed."),
        ("pause_1", 2300, 2650, "Both speakers remain silent; S2 looks thoughtful with its mouth closed."),
        ("answer_1", 2650, 5100, "Only S2 delivers dialogue_2 while S1 remains silent."),
        ("pause_2", 5100, 5450, "Both speakers remain silent and S2 closes its mouth."),
        ("question_2", 5450, 7500, "S1 delivers dialogue_3 while S2 listens with its mouth closed."),
        ("pause_3", 7500, 7850, "Both speakers remain silent; S2 blinks with its mouth closed."),
        ("answer_2", 7850, 11200, "Only S2 delivers dialogue_4 while S1 remains silent."),
        ("writing", 11200, 14000, "S2 closes its mouth and writes clumsily with the oversized pencil."),
    ]
    return {
        "scene_setup": (
            "A hyper-realistic baby tabby kitten sits at a school desk while a "
            "softly blurred interviewer is partially visible in side profile at the left edge."
        ),
        "continuity_invariants": [
            "S1 remains at the left edge with one stable microphone.",
            "S2 remains the sharp primary subject behind the desk.",
        ],
        "motion_contract": {
            "primary_motion": "The kitten keeps subtle natural body motion and finishes by writing clumsily.",
            "end_behavior": "continue_motion",
        },
        "beats": [
            {
                "beat_id": "interview",
                "start_ms": 0,
                "end_ms": 14000,
                "primary_action": "S1 and S2 alternate a short interview before S2 writes.",
                "participants": ["S1", "S2"],
                "observable_end_state": "S2 is mid-writing while S1 keeps the microphone stable.",
                "steps": [
                    {
                        "step_id": step_id,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "action": action,
                        "continuity_after": "The desk, microphone, subjects and props remain spatially stable.",
                    }
                    for step_id, start_ms, end_ms, action in steps
                ],
            }
        ],
        "final_state": {
            "description": "The kitten is mid-clumsy pencil stroke with the interviewer still at frame left.",
            "final_hold_ms": 0,
        },
        "camera_directives": [
            {
                "directive_id": "camera_1",
                "start_ms": 0,
                "end_ms": 14000,
                "motion": "push.in",
                "amplitude": "small",
                "speed": "slow",
                "target_clause": None,
                "visible_change": "The kitten's expression and pencil become slightly more prominent.",
            }
        ],
        "dialogue_cues": [
            {
                "cue_id": "dialogue_1",
                "speaker_id": "S1",
                "speaker": "the adult female interviewer",
                "start_ms": 0,
                "language": "French",
                "delivery": "warmly and curiously",
                "text": "Pourquoi tu étudies si dur, si jeune ?",
            },
            {
                "cue_id": "dialogue_2",
                "speaker_id": "S2",
                "speaker": "the kitten",
                "start_ms": 2650,
                "language": "French",
                "delivery": "innocently but determinedly",
                "text": "Je veux entrer à Harvard quand je serai grand.",
            },
            {
                "cue_id": "dialogue_3",
                "speaker_id": "S1",
                "speaker": "the adult female interviewer",
                "start_ms": 5450,
                "language": "French",
                "delivery": "gently",
                "text": "Et qu’est-ce que tu veux y apprendre ?",
            },
            {
                "cue_id": "dialogue_4",
                "speaker_id": "S2",
                "speaker": "the kitten",
                "start_ms": 7850,
                "language": "French",
                "delivery": "with complete seriousness",
                "text": "À construire une machine qui distribue des croquettes toute seule.",
            },
        ],
        "risks": [],
        "technical_adjustments": [],
        "overall_soundscape": "Quiet room tone, separated left-side adult voice and centered kitten voice, then pencil scratching.",
        "non_diegetic_music": "N/A",
    }


def writer_body(*, duplicate_first: bool = False) -> str:
    duplicate = (
        " (S1) warmly and curiously <d>[French] Pourquoi tu étudies si dur, si jeune ?</d>;"
        if duplicate_first
        else ""
    )
    return (
        "integrated_multimodal_description:\n"
        "[Shot 1] The target video is one continuous 14-second shot. "
        "A warm miniature study keeps the kitten sharp while the interviewer's "
        "soft side profile, hand and microphone remain at the left edge. "
        f"[[dialogue:dialogue_1]]{duplicate} The kitten pauses thoughtfully. "
        "[[dialogue:dialogue_2]] Both remain silent for a short pause. "
        "[[dialogue:dialogue_3]] The kitten blinks once. "
        "[[dialogue:dialogue_4]] The kitten closes its mouth and writes clumsily.\n"
        "overall_soundscape:\nQuiet room tone, separated voices and pencil scratching.\n"
        "non_diegetic_music:\nN/A"
    )


class H3BaseAnimalInterviewTest(unittest.TestCase):
    def test_catalog_exposes_a_distinct_immutable_recipe(self):
        catalog = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        cookbook = catalog.get(
            "minimax.h3.base.animal-interview", "0.1.0"
        )
        juvenile = catalog.get(
            "minimax.h3.base.animal-interview", "0.2.0"
        )
        profile = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles").get(
            "minimax.h3.base.animal-interview", "0.1.0"
        )
        self.assertEqual(cookbook.target_mode, "fl2va_direct")
        self.assertEqual(cookbook.writer_projection, "animal_interview_v1")
        self.assertEqual(
            juvenile.output_contract,
            "minimax.h3.fl2va.animal_interview_compact_h3_v2",
        )
        self.assertIn("noticeably high-pitched", juvenile.beat_sheet_system_prompt)
        self.assertEqual(
            tuple((slot.slot_id, slot.minimum_references, slot.maximum_references) for slot in cookbook.slots),
            (("first_frame", 0, 1), ("last_frame", 0, 1)),
        )
        self.assertEqual(profile.session_mode, PromptSessionMode.H3_BASE)
        self.assertIn("profil latéral", profile.brief_system_prompt)
        self.assertIn("mouth ownership", cookbook.final_prompt_system_prompt)

    def test_compiler_derives_full_speech_intervals_and_repairs_inline_echo(self):
        exact = tuple(cue["text"] for cue in interview_plan()["dialogue_cues"])
        plan = canonical_direct_ref2v_action_plan_v4(
            json.dumps(interview_plan(), ensure_ascii=False),
            expected_dialogues=exact,
        )
        timed = apply_direct_i2v_timing(
            writer_body(duplicate_first=True),
            plan,
            dialogue_aware=True,
            motion_aware=True,
            camera_clean=True,
            insert_missing_final_landmark=True,
        )
        compiled, recovered = compile_animal_interview_dialogue_cues(timed, plan)
        self.assertIn("dialogue_1", recovered)
        self.assertIn(
            "From 00:00.000 to 00:02.300, the interviewed animal remains silent "
            "with its mouth closed while",
            compiled,
        )
        self.assertIn("From 00:02.650 to 00:05.100, only the kitten (S2) speaks", compiled)
        self.assertIn("Only the interviewed animal's mouth moves", compiled)
        self.assertLess(compiled.index(exact[0]), compiled.index("pauses thoughtfully"))
        self.assertLess(compiled.index("pauses thoughtfully"), compiled.index(exact[1]))
        self.assertLess(compiled.index(exact[1]), compiled.index(exact[2]))
        self.assertLess(compiled.index(exact[2]), compiled.index(exact[3]))
        for text in exact:
            self.assertEqual(compiled.count(text), 1)
        self.assertNotIn("[[dialogue:", compiled)

    def test_v2_compiler_locks_a_young_voice_without_replacing_emotion(self):
        exact = tuple(cue["text"] for cue in interview_plan()["dialogue_cues"])
        plan = canonical_direct_ref2v_action_plan_v4(
            json.dumps(interview_plan(), ensure_ascii=False),
            expected_dialogues=exact,
        )
        compiled, _ = compile_animal_interview_dialogue_cues(
            writer_body(),
            plan,
            juvenile_animal_voice=True,
        )
        self.assertEqual(compiled.count("unmistakably very young childlike voice"), 1)
        self.assertIn("noticeably high-pitched timbre", compiled)
        self.assertIn("never adult, deep or mature, innocently but determinedly", compiled)
        self.assertIn("again in the same very young", compiled)
        self.assertIn("with complete seriousness", compiled)

    def test_writer_projection_never_receives_spoken_text(self):
        projection = direct_ref2v_animal_interview_writer_plan(
            json.dumps(interview_plan(), ensure_ascii=False)
        )
        self.assertNotIn("Pourquoi tu étudies", projection)
        self.assertNotIn("croquettes", projection)
        self.assertIn('"cue_id": "dialogue_1"', projection)

    def test_standard_compiler_removes_placeholder_plus_inline_exact_echo(self):
        exact = tuple(cue["text"] for cue in interview_plan()["dialogue_cues"])
        plan = canonical_direct_ref2v_action_plan_v4(
            json.dumps(interview_plan(), ensure_ascii=False),
            expected_dialogues=exact,
        )
        compiled, _ = compile_direct_i2v_dialogue_cues(
            writer_body(duplicate_first=True),
            plan,
            motion_aware=True,
        )
        self.assertEqual(compiled.count(exact[0]), 1)
        self.assertNotIn("[[dialogue:dialogue_1]]", compiled)

    def test_recipe_lint_rejects_wrong_speaker_order(self):
        plan = interview_plan()
        plan["dialogue_cues"][0]["speaker_id"] = "S2"
        plan["dialogue_cues"][0]["speaker"] = "the kitten"
        plan["dialogue_cues"][1]["speaker_id"] = "S1"
        plan["dialogue_cues"][1]["speaker"] = "the adult female interviewer"
        errors = lint_animal_interview_action_plan(
            json.dumps(plan, ensure_ascii=False)
        )
        self.assertTrue(any("alternate S1" in error for error in errors))

    def test_full_t2va_flow_uses_dialogue_completed_in_the_brief(self):
        source = (
            "PANELFORGE_ANIMAL_INTERVIEW_V1\nLANGUAGE: French\n"
            "TARGET DURATION: 14 seconds\nPARTIAL SCRIPT:\n"
            'S1: "Pourquoi tu étudies si dur, si jeune ?"\nS2: [à compléter]'
        )
        completed_dialogue = tuple(
            cue["text"] for cue in interview_plan()["dialogue_cues"]
        )
        with tempfile.TemporaryDirectory() as directory:
            brief = BriefRevision(
                revision_id="brief-1",
                source_text=source,
                content="SCRIPT FINAL VERBATIM\n" + "\n".join(
                    f'{"S1 Interviewer" if index % 2 == 0 else "S2 Animal"}: "{text}"'
                    for index, text in enumerate(completed_dialogue)
                ),
                creative_freedom=35,
                origin=RevisionOrigin.MODEL,
                references=(),
            )
            session = PromptLabSession(
                session_id="animal-session",
                model_id="vision-model",
                profile_id="minimax.h3.base.animal-interview",
                profile_version="0.1.0",
                references=(),
                session_mode=PromptSessionMode.H3_BASE,
            ).add_brief_revision(brief).approve_brief()
            sessions = LocalPromptSessionStore(directory)
            sessions.create(session)
            gateway = DirectI2VGateway(with_camera=False, camera_owned=True)
            service = PromptCompositionService(
                gateway=gateway,
                cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
                sessions=sessions,
                compositions=LocalPromptCompositionStore(directory),
                assets=LocalAssetStore(directory),
            )
            service.configure(
                session.session_id,
                "minimax.h3.base.animal-interview",
                "0.2.0",
                (CookbookBinding("first_frame", ()), CookbookBinding("last_frame", ())),
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(interview_plan(), ensure_ascii=False)
                return writer_body()

            gateway._content = response
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            plan_request = gateway.requests[-1]
            self.assertIn("croquettes toute seule", plan_request.user_prompt)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            completed = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            final = completed.final_prompt.active_revision.content
            self.assertIn("From 00:07.850 to 00:11.200", final)
            self.assertIn("unmistakably very young childlike voice", final)
            self.assertIn("again in the same very young", final)
            self.assertIn("the interviewer", final)
            self.assertIn("non_diegetic_music:\nN/A", final)

    def test_all_four_h3_base_input_modes_share_the_interview_recipe(self):
        cases = (
            ((), H3BaseInputMode.T2VA),
            (("first_frame",), H3BaseInputMode.I2VA),
            (("last_frame",), H3BaseInputMode.L2VA),
            (("first_frame", "last_frame"), H3BaseInputMode.FL2VA),
        )
        source = (
            "PANELFORGE_ANIMAL_INTERVIEW_V1\nLANGUAGE: French\n"
            "TARGET DURATION: 14 seconds\nPARTIAL SCRIPT:\n"
            'S1: "Pourquoi tu Ã©tudies si dur, si jeune ?"\n'
            "S2: [Ã  complÃ©ter]\nS1: [Ã  complÃ©ter]\nS2: [Ã  complÃ©ter]"
        )
        completed_dialogue = tuple(
            cue["text"] for cue in interview_plan()["dialogue_cues"]
        )
        for roles, mode in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                asset_numbers = iter(range(1, len(roles) + 1))
                assets = LocalAssetStore(
                    directory,
                    id_factory=lambda: f"asset-{next(asset_numbers)}",
                )
                references = []
                for index, role in enumerate(roles, 1):
                    asset = assets.create(PNG + bytes((index,)), "image/png")
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
                brief = BriefRevision(
                    revision_id="brief-1",
                    source_text=source,
                    content="SCRIPT FINAL VERBATIM\n" + "\n".join(
                        f'{"S1 Interviewer" if index % 2 == 0 else "S2 Animal"}: "{text}"'
                        for index, text in enumerate(completed_dialogue)
                    ),
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
                session = PromptLabSession(
                    session_id="animal-session",
                    model_id="vision-model",
                    profile_id="minimax.h3.base.animal-interview",
                    profile_version="0.1.0",
                    references=references_tuple,
                    session_mode=PromptSessionMode.H3_BASE,
                ).add_brief_revision(brief).approve_brief()
                sessions = LocalPromptSessionStore(directory)
                sessions.create(session)
                gateway = DirectI2VGateway(with_camera=False, camera_owned=True)
                service = PromptCompositionService(
                    gateway=gateway,
                    cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
                    sessions=sessions,
                    compositions=LocalPromptCompositionStore(directory),
                    assets=assets,
                )
                by_role = {reference.role: reference.reference_id for reference in references_tuple}
                service.configure(
                    session.session_id,
                    "minimax.h3.base.animal-interview",
                    "0.1.0",
                    (
                        CookbookBinding("first_frame", ((by_role["first_frame"],) if "first_frame" in by_role else ())),
                        CookbookBinding("last_frame", ((by_role["last_frame"],) if "last_frame" in by_role else ())),
                    ),
                )

                def response(request):
                    if request.operation_id == "action_plan.generate":
                        return json.dumps(interview_plan(), ensure_ascii=False)
                    return writer_body()

                gateway._content = response
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                self.assertEqual(len(gateway.requests[-1].images), len(roles))
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                completed = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                final = completed.final_prompt.active_revision.content
                expected_header = compile_h3_base_header(mode, 14000)
                if expected_header:
                    self.assertTrue(final.startswith(expected_header + "\n\n"))
                else:
                    self.assertTrue(final.startswith("integrated_multimodal_description:"))


if __name__ == "__main__":
    unittest.main()
