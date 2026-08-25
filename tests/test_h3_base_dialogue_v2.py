import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application.direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan_v3,
    direct_ref2v_action_plan_schema_v3,
    direct_ref2v_action_plan_warnings_v3,
    explicit_dialogue_ledger,
    extract_explicit_dialogues,
)
from panelforge.application.direct_i2v_prompt import compile_direct_i2v_dialogue_cues
from panelforge.application import (
    CompletionResult,
    PromptCompositionService,
    PromptLabService,
)
from panelforge.application.prompt_composition import _compact_json_schema
from panelforge.domain import CompositionStage, CookbookBinding
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)
from tests.test_direct_fl2va_composition import configured_service
from tests.test_direct_i2v_composition import action_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BRIEF_DOCUMENT = """- INTENTION CENTRALE
Deux personnes échangent quelques mots dans une même pièce.
- RÉFÉRENCES CITÉES ET RÔLES
Mode texte seul, sans frame native.
- SUJETS ET IDENTITÉS À PRÉSERVER
Les deux interlocuteurs restent identifiables.
- DÉCOR ET ÉTAT INITIAL
Ils se tiennent dans une pièce calme.
- CHRONOLOGIE ET ACTIONS DEMANDÉES
dialogue_1: «Bonjour !» puis dialogue_2: «Bienvenue.»
- CAMÉRA, LUMIÈRE ET MISE EN SCÈNE
Un mouvement continu accompagne leur échange.
- CONTRAINTES STRICTES
Conserver les citations mot pour mot.
- LIBERTÉS AUTORISÉES
Liaisons visuelles sobres.
- QUESTIONS OU AMBIGUÏTÉS
N/A"""


def writer_body() -> str:
    return (
        "integrated_multimodal_description:\n"
        "[Shot 1] The target video is one continuous 12-second shot. "
        "The two speakers remain in the same room and exchange a look. "
        "At 00:03.600, their joined hands enter the frame. Finally, "
        "they settle in place.\n"
        "overall_soundscape:\nQuiet room tone and natural voices.\n"
        "non_diegetic_music:\nN/A"
    )


class FullJourneyGateway:
    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if request.operation_id == "brief.structure":
            content = BRIEF_DOCUMENT
        elif request.operation_id == "action_plan.generate":
            content = json.dumps(dialogue_plan())
        else:
            content = writer_body()
        return CompletionResult(
            model_id=request.model_id,
            content=content,
            call_id=f"call-{len(self.requests)}",
        )


def dialogue_plan() -> dict:
    plan = action_plan(with_camera=False)
    plan["camera_directives"] = [
        {
            "directive_id": "camera_1",
            "start_ms": 0,
            "end_ms": 7600,
            "motion": "push.in",
            "amplitude": "small",
            "speed": "slow",
            "target_clause": "toward the two speakers",
            "visible_change": "Their expressions become more readable.",
        },
        {
            "directive_id": "camera_2",
            "start_ms": 3600,
            "end_ms": 7600,
            "motion": "tilt.down",
            "amplitude": "small",
            "speed": "slow",
            "target_clause": "toward their joined hands",
            "visible_change": "Their hand contact enters the frame.",
        },
    ]
    plan["dialogue_cues"] = [
        {
            "cue_id": "dialogue_1",
            "speaker_id": "S1",
            "speaker": "the woman",
            "start_ms": 1000,
            "language": "French",
            "delivery": "warmly",
            "text": "A paraphrase that must not survive.",
        }
    ]
    return plan


class H3BaseDialogueV2Test(unittest.TestCase):
    def test_extracts_straight_curly_and_french_quotes_in_source_order(self):
        source = 'Elle dit «Bonjour !», puis “Reste ici” et enfin "A demain."'
        self.assertEqual(
            extract_explicit_dialogues(source),
            ("Bonjour !", "Reste ici", "A demain."),
        )
        self.assertEqual(
            json.loads(explicit_dialogue_ledger(source))[0],
            {"cue_id": "dialogue_1", "text": "Bonjour !"},
        )
        self.assertEqual(
            extract_explicit_dialogues(
                '{"scene_setup":"A former prompt example with spaces."}'
            ),
            (),
        )

    def test_speaker_prefixed_quotes_are_dialogue_not_json_values(self):
        source = (
            'S1: "Why are you studying so hard?"\n'
            'S2 Animal: "Because I want to learn."\n'
            '{"speaker": "This remains structural JSON."}'
        )
        self.assertEqual(
            extract_explicit_dialogues(source),
            (
                "Why are you studying so hard?",
                "Because I want to learn.",
            ),
        )

    def test_plan_restores_quotes_and_sequentializes_only_later_start_camera(self):
        canonical = canonical_direct_ref2v_action_plan_v3(
            json.dumps(dialogue_plan()),
            recover_invalid_target=True,
            recover_parallel_steps=True,
            recover_camera_overlaps=True,
            expected_dialogues=("Bonjour !", "Bienvenue."),
        )
        plan = json.loads(canonical)
        self.assertEqual(plan["camera_directives"][0]["end_ms"], 3600)
        self.assertEqual(plan["camera_directives"][1]["start_ms"], 3600)
        self.assertEqual(
            [cue["text"] for cue in plan["dialogue_cues"]],
            ["Bonjour !", "Bienvenue."],
        )
        self.assertIn(
            "camera_overlap_sequentialized:camera_1:7600:3600",
            plan["technical_adjustments"],
        )
        self.assertIn(
            "dialogue_text_restored:dialogue_1",
            plan["technical_adjustments"],
        )
        self.assertIn(
            "dialogue_cue_recovered:dialogue_2",
            plan["technical_adjustments"],
        )
        warnings = direct_ref2v_action_plan_warnings_v3(canonical)
        self.assertTrue(any("sequentialise" in warning for warning in warnings))
        self.assertTrue(any("dialogue_2" in warning for warning in warnings))

    def test_invalid_dialogue_metadata_is_recovered_without_another_call(self):
        plan = dialogue_plan()
        plan["dialogue_cues"][0].update(
            {
                "speaker_id": "speaker-one",
                "speaker": "",
                "start_ms": 99_000,
                "language": "",
                "delivery": None,
            }
        )

        canonical = json.loads(
            canonical_direct_ref2v_action_plan_v3(
                json.dumps(plan),
                recover_camera_overlaps=True,
                expected_dialogues=("Bonjour !",),
            )
        )

        cue = canonical["dialogue_cues"][0]
        self.assertEqual(cue["speaker_id"], "S1")
        self.assertEqual(cue["language"], "French")
        self.assertLessEqual(cue["start_ms"], 8000)
        self.assertIn(
            "dialogue_metadata_recovered:dialogue_1",
            canonical["technical_adjustments"],
        )

    def test_equal_start_camera_overlap_remains_ambiguous_and_rejected(self):
        plan = dialogue_plan()
        plan["camera_directives"][1]["start_ms"] = 0
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            canonical_direct_ref2v_action_plan_v3(
                json.dumps(plan),
                recover_camera_overlaps=True,
                expected_dialogues=("Bonjour !",),
            )

    def test_dialogue_placeholder_timing_is_compiler_owned(self):
        plan = canonical_direct_ref2v_action_plan_v3(
            json.dumps(dialogue_plan()),
            recover_camera_overlaps=True,
            expected_dialogues=("Bonjour !",),
        )
        body = writer_body().replace(
            "Finally, they settle in place.",
            "At 00:06.000, [[dialogue:dialogue_1]]. Finally, they settle in place.",
        )

        compiled, recovered = compile_direct_i2v_dialogue_cues(body, plan)

        self.assertEqual(recovered, ())
        self.assertNotIn("00:06.000", compiled)
        self.assertIn(
            "At 00:01.000, the woman (S1) says warmly: "
            "<d>[French] Bonjour !</d>.",
            compiled,
        )

    def test_plan_and_writer_compile_omitted_dialogue_and_final_landmark(self):
        source = (
            "Plan unique de 8 secondes. Elle dit «Bonjour !» puis il répond "
            '"Bienvenue."'
        )
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame",),
                source_text=source,
                profile_version="0.2.0",
                cookbook_version="0.2.0",
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(dialogue_plan())
                return writer_body()

            gateway._content = response
            planned = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            self.assertEqual(len(gateway.requests), 1)
            plan = json.loads(planned.beat_sheet.active_revision.content)
            self.assertEqual(plan["camera_directives"][0]["end_ms"], 3600)
            self.assertEqual(
                [cue["text"] for cue in plan["dialogue_cues"]],
                ["Bonjour !", "Bienvenue."],
            )
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            final = service.generate(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
            )
            self.assertEqual(len(gateway.requests), 2)
            content = final.final_prompt.active_revision.content
            self.assertIn(
                "the woman (S1) says warmly: <d>[French] Bonjour !</d>",
                content,
            )
            self.assertIn("<d>[French] Bienvenue.</d>", content)
            self.assertEqual(content.count("Bonjour !"), 1)
            self.assertEqual(content.count("Bienvenue."), 1)
            self.assertIn("At 00:08.000,", content)

    def test_writer_placeholders_and_inline_field_values_compile_before_final_lint(self):
        source = (
            "Plan unique de 8 secondes. Elle dit Â«Bonjour !Â» puis il rÃ©pond "
            '"Bienvenue."'
        )
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame",),
                source_text=source,
                profile_version="0.2.0",
                cookbook_version="0.2.0",
            )
            compact_writer = (
                writer_body()
                .replace(
                    "integrated_multimodal_description:\n",
                    "integrated_multimodal_description:",
                )
                .replace(
                    "The two speakers remain",
                    "[[dialogue:dialogue_1]] The two speakers remain",
                )
                .replace(
                    "their joined hands enter the frame.",
                    "their joined hands enter the frame. [[dialogue:dialogue_2]]",
                )
                .replace("overall_soundscape:\n", "overall_soundscape:")
                .replace("non_diegetic_music:\n", "non_diegetic_music:")
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(dialogue_plan())
                return compact_writer

            gateway._content = response
            service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            completed = service.generate(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
            )

            content = completed.final_prompt.active_revision.content
            self.assertNotIn("[[", content)
            self.assertEqual(content.count("<d>"), 2)
            self.assertEqual(content.count("Bonjour !"), 1)
            self.assertEqual(content.count("Bienvenue."), 1)
            self.assertIn("The camera pushes in", content)
            self.assertIn("The camera tilts down", content)

    def test_complete_journey_stays_at_three_llm_calls_and_revision_recompiles(self):
        source = 'Elle dit «Bonjour !» puis il répond "Bienvenue."'
        with tempfile.TemporaryDirectory() as directory:
            gateway = FullJourneyGateway()
            assets = LocalAssetStore(directory)
            sessions = LocalPromptSessionStore(directory)
            prompt_lab = PromptLabService(
                gateway=gateway,
                profiles=LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles"),
                assets=assets,
                sessions=sessions,
            )
            session = prompt_lab.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.fl2va.direct",
                profile_version="0.2.0",
                references=(),
            )
            session = prompt_lab.structure_brief(session.session_id, source, 35)
            self.assertIn(
                '[{"cue_id":"dialogue_1","text":"Bonjour !"},'
                '{"cue_id":"dialogue_2","text":"Bienvenue."}]',
                gateway.requests[0].user_prompt,
            )
            prompt_lab.approve_brief(session.session_id)

            composition = PromptCompositionService(
                gateway=gateway,
                cookbooks=LocalPromptCookbookCatalog(
                    PROJECT_ROOT / "prompt_cookbooks"
                ),
                sessions=sessions,
                compositions=LocalPromptCompositionStore(directory),
                assets=assets,
            )
            composition.configure(
                session.session_id,
                "minimax.h3.fl2va.direct",
                "0.2.0",
                (
                    CookbookBinding("first_frame", ()),
                    CookbookBinding("last_frame", ()),
                ),
            )
            composition.generate(session.session_id, CompositionStage.BEAT_SHEET)
            composition.approve(session.session_id, CompositionStage.BEAT_SHEET)
            completed = composition.generate(
                session.session_id,
                CompositionStage.FINAL_PROMPT,
            )

            self.assertEqual(
                [request.operation_id for request in gateway.requests],
                ["brief.structure", "action_plan.generate", "final_prompt.generate"],
            )
            final = completed.final_prompt.active_revision.content
            self.assertEqual(final.count("Bonjour !"), 1)
            self.assertEqual(final.count("Bienvenue."), 1)
            self.assertIn("At 00:08.000,", final)

            revised = composition.revise(
                session.session_id,
                CompositionStage.FINAL_PROMPT,
                "Rends la description plus concise.",
            )
            revised_content = revised.final_prompt.active_revision.content
            self.assertEqual(revised_content.count("Bonjour !"), 1)
            self.assertEqual(revised_content.count("Bienvenue."), 1)
            self.assertIn("At 00:08.000,", revised_content)

    def test_manual_plan_edit_cannot_change_source_owned_dialogue(self):
        source = "Elle dit «Bonjour !»."
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                (),
                source_text=source,
                profile_version="0.2.0",
                cookbook_version="0.2.0",
            )
            gateway._content = lambda request: json.dumps(dialogue_plan())
            planned = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            edited = json.loads(planned.beat_sheet.active_revision.content)
            edited["dialogue_cues"][0]["text"] = "Une paraphrase."

            with self.assertRaisesRegex(ValueError, "preserve every explicit"):
                service.edit(
                    "h3-base-session",
                    CompositionStage.BEAT_SHEET,
                    json.dumps(edited),
                )

    def test_empty_ledger_is_canonicalized_without_dialogue_adjustment(self):
        plan = action_plan(with_camera=False)
        canonical = json.loads(
            canonical_direct_ref2v_action_plan_v3(
                json.dumps(plan),
                expected_dialogues=(),
            )
        )
        self.assertEqual(canonical["dialogue_cues"], [])
        self.assertNotIn(
            "dialogue_cues_compiler_owned",
            canonical["technical_adjustments"],
        )

    def test_compact_schema_keeps_real_description_property(self):
        raw = direct_ref2v_action_plan_schema_v3()
        compact = _compact_json_schema(raw, prune_metadata=True)
        decoded = json.loads(compact)

        self.assertIn(
            "description",
            decoded["$defs"]["DirectContinuityRisk"]["properties"],
        )
        self.assertLess(len(compact), len(raw))

    def test_v1_and_v2_are_both_loadable_but_v2_is_the_dialogue_contract(self):
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        legacy = cookbooks.get("minimax.h3.fl2va.direct", "0.1.0")
        current = cookbooks.get("minimax.h3.fl2va.direct", "0.2.0")
        self.assertEqual(legacy.output_contract, "minimax.h3.fl2va.direct_compact_h3_v1")
        self.assertEqual(current.output_contract, "minimax.h3.fl2va.direct_compact_h3_v2")
        self.assertEqual(current.writer_projection, "compact_dialogue_v2")
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        self.assertEqual(
            profiles.get("minimax.h3.fl2va.direct", "0.2.0").session_mode.value,
            "h3_base",
        )


if __name__ == "__main__":
    unittest.main()
