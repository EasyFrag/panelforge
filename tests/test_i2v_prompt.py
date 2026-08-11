import tempfile
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    PromptCompositionService,
    StreamEventKind,
    StreamPhase,
    lint_i2v_prompt,
)
from panelforge.application.prompt_composition import (
    _instruction_requests_camera_change,
)
from panelforge.domain import (
    AnalysisRevision,
    BriefReferenceSnapshot,
    BriefRevision,
    CompositionStage,
    CookbookBinding,
    PromptLabSession,
    PromptReference,
    ReferenceUse,
    RevisionOrigin,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import (
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)


I2V_PROMPT = """For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the football player shown in <Picture 1> preserves his identity, blue uniform, planted left foot, ball position, stadium composition, and late-afternoon light. He drives his right foot through the ball; grass blades lift from the turf as the ball accelerates toward the upper corner, and the camera pans right with small amplitude at fast speed to follow its flight. The goalkeeper reacts late and extends both hands as the ball reaches the net.

overall_soundscape: Stadium ambience continues under the sharp kick, displaced grass, the ball cutting through the air, and the net snapping taut.

non_diegetic_music: A sparse low percussion pulse accelerates once after the kick, then stops at the net impact."""

I2V_CANONICAL_DRAFT = """camera_directives:
[{"id":"camera_1","motion":"pan.right","amplitude":"small","speed":"fast","target_clause":"following the ball"}]
integrated_multimodal_description:
[Shot 1] The football player shown in <Picture 1> strikes the ball. [[camera:camera_1]] The player shouts <d>[FR] Maintenant!</d> as the ball reaches the net.
overall_soundscape:
The kick, shout, and net impact remain synchronized with the stadium ambience.
non_diegetic_music:
N/A"""

I2V_REPEATED_CAMERA_DRAFT = """camera_directives:
[{"id":"camera_1","motion":"pan.right"},{"id":"camera_2","motion":"pan.right"}]
integrated_multimodal_description:
[Shot 1] The runner shown in <Picture 1> enters the straight. [[camera:camera_1]] After the bend, the runner accelerates again. [[camera:camera_2]]
overall_soundscape:
Footsteps and crowd ambience follow the action.
non_diegetic_music:
N/A"""


class I2VGateway:
    def __init__(self) -> None:
        self.requests: list[CompletionRequest] = []

    def list_models(self):
        return (ModelDescriptor("vision-model"),)

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(model_id=request.model_id, content=I2V_PROMPT)

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=I2V_PROMPT,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=I2V_PROMPT,
            result=CompletionResult(model_id=request.model_id, content=I2V_PROMPT),
        )


class EnvelopeI2VGateway(I2VGateway):
    def complete(self, request):
        self.requests.append(request)
        content = I2V_PROMPT
        if request.operation_id == "final_prompt.revise":
            content = "SOURCE CONTEXT — READ ONLY\nDo not persist this.\n\n" + content
        return CompletionResult(model_id=request.model_id, content=content)


class CanonicalI2VGateway(I2VGateway):
    def __init__(self, content=I2V_CANONICAL_DRAFT) -> None:
        super().__init__()
        self.content = content

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(model_id=request.model_id, content=self.content)


def approved_i2v_session() -> PromptLabSession:
    analysis = AnalysisRevision(
        revision_id="analysis-i2v-1",
        content=(
            "A football player in a blue uniform plants his left foot beside the "
            "ball and draws his right leg back on a stadium pitch."
        ),
        origin=RevisionOrigin.MODEL,
    )
    reference = PromptReference(
        reference_id="reference-i2v-1",
        asset_id="asset-i2v-1",
        role="i2v_first_frame",
        label="kick.png",
        revisions=(analysis,),
        active_revision_id=analysis.revision_id,
        approved_revision_id=analysis.revision_id,
        uses=(ReferenceUse.FIRST_FRAME,),
    )
    session = PromptLabSession(
        session_id="session-i2v-1",
        model_id="vision-model",
        profile_id="minimax.h3.reference",
        profile_version="0.3.0",
        references=(reference,),
    )
    brief = BriefRevision(
        revision_id="brief-i2v-1",
        source_text="Le joueur tire et marque dans la lucarne.",
        content="Animate the visible player taking the shot and scoring.",
        creative_freedom=35,
        origin=RevisionOrigin.MODEL,
        references=(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=analysis.revision_id,
                uses=reference.uses,
            ),
        ),
    )
    return session.add_brief_revision(brief).approve_brief()


class I2VPromptTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.sessions = LocalPromptSessionStore(self.directory.name)
        self.sessions.create(approved_i2v_session())
        self.compositions = LocalPromptCompositionStore(self.directory.name)
        self.gateway = I2VGateway()
        self.service = PromptCompositionService(
            gateway=self.gateway,
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=self.sessions,
            compositions=self.compositions,
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_catalog_exposes_a_direct_i2v_pipeline(self):
        cookbook = self.service.cookbooks.get("minimax.h3.i2v.simple", "0.1.0")

        self.assertEqual(cookbook.output_contract, "minimax.h3.i2va")
        self.assertEqual(cookbook.stages, ("final_prompt",))
        self.assertEqual(cookbook.slots[0].required_uses, ("first_frame",))
        self.assertIsNone(cookbook.reference_plan_system_prompt)

    def test_v2_adds_only_generic_feasibility_guidance_to_the_writer(self):
        baseline = self.service.cookbooks.get("minimax.h3.i2v.simple", "0.1.0")
        revised = self.service.cookbooks.get("minimax.h3.i2v.simple", "0.2.0")

        self.assertEqual(revised.output_contract, baseline.output_contract)
        self.assertEqual(revised.stages, baseline.stages)
        self.assertNotIn("General feasibility rules", baseline.final_prompt_system_prompt)
        self.assertIn("General feasibility rules", revised.final_prompt_system_prompt)
        self.assertIn("every explicit duration", revised.final_prompt_system_prompt)
        self.assertIn("physically natural secondary motion", revised.final_prompt_system_prompt)
        self.assertIn("new sequential action beats", revised.final_prompt_system_prompt)

    def test_v3_pins_the_h3_protocol_and_compiles_the_internal_draft(self):
        cookbook = self.service.cookbooks.get("minimax.h3.i2v.simple", "0.3.0")
        self.assertEqual(cookbook.output_contract, "minimax.h3.i2va.canonical_v1")
        self.assertEqual(cookbook.reference.engine_contract_id, "minimax.h3.protocol")
        self.assertEqual(cookbook.reference.engine_contract_version, "0.1.0")
        self.assertTrue(all("05d91ff89f58" in source for source in cookbook.sources))

        self.gateway = CanonicalI2VGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )

        composition = self.service.generate(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        content = composition.final_prompt.active_revision.content

        self.assertTrue(content.startswith("For the target video, at 0.00 seconds"))
        self.assertNotIn("camera_directives:", content)
        self.assertNotIn("[[camera:", content)
        self.assertIn(
            "The camera pans right with small amplitude at fast speed, following the ball.",
            content,
        )
        self.assertIn("<d>[French] Maintenant!</d>", content)
        compiler_context = composition.final_prompt.active_revision.compiler_context
        self.assertIsNotNone(compiler_context)
        self.assertIn('"motion":"pan.right"', compiler_context)
        self.assertEqual(
            self.compositions.get("session-i2v-1")
            .final_prompt.active_revision.compiler_context,
            compiler_context,
        )

        edited = self.service.edit(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
            content.replace("stadium ambience", "stadium room tone"),
        )
        self.assertEqual(
            edited.final_prompt.active_revision.compiler_context,
            compiler_context,
        )

    def test_v3_rejects_an_unknown_camera_enum_without_persisting_it(self):
        invalid = I2V_CANONICAL_DRAFT.replace('"pan.right"', '"dolly"')
        self.gateway = CanonicalI2VGateway(invalid)
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )

        with self.assertRaisesRegex(ValueError, "invalid camera directive"):
            self.service.generate("session-i2v-1", CompositionStage.FINAL_PROMPT)

        stored = self.compositions.get("session-i2v-1")
        self.assertIsNone(stored.final_prompt.active_revision)

    def test_v3_rejects_an_embedded_camera_placeholder(self):
        invalid = I2V_CANONICAL_DRAFT.replace(
            ". [[camera:camera_1]] The player",
            " while [[camera:camera_1]] the player",
        )
        self.gateway = CanonicalI2VGateway(invalid)
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )

        with self.assertRaisesRegex(ValueError, "standalone sentence"):
            self.service.generate("session-i2v-1", CompositionStage.FINAL_PROMPT)

    def test_v3_revision_reuses_the_internal_camera_contract(self):
        self.gateway = CanonicalI2VGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )
        self.service.generate("session-i2v-1", CompositionStage.FINAL_PROMPT)

        revised = self.service.revise(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
            "Keep the action and make the soundscape shorter.",
        )

        self.assertNotIn("camera_directives:", revised.final_prompt.active_revision.content)
        self.assertIn(
            "The camera pans right with small amplitude at fast speed, following the ball.",
            revised.final_prompt.active_revision.content,
        )
        self.assertIn("camera_directives:", self.gateway.requests[-1].system_prompt)
        revision_prompt = self.gateway.requests[-1].user_prompt
        self.assertIn('"motion":"pan.right"', revision_prompt)
        self.assertIn("[[camera:camera_1]]", revision_prompt)
        self.assertNotIn(
            "The camera pans right with small amplitude at fast speed, following the ball.",
            revision_prompt,
        )
        self.assertNotIn(
            "For the target video, at 0.00 seconds into the target video",
            revision_prompt,
        )

    def test_v3_non_camera_revision_cannot_silently_change_camera_directives(self):
        self.gateway = CanonicalI2VGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )
        generated = self.service.generate(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        parent_id = generated.final_prompt.active_revision_id
        self.gateway.content = I2V_CANONICAL_DRAFT.replace(
            '"pan.right"',
            '"zoom.in"',
        )

        with self.assertRaisesRegex(ValueError, "explicitly mentions the camera"):
            self.service.revise(
                "session-i2v-1",
                CompositionStage.FINAL_PROMPT,
                "Shorten only the soundscape.",
            )

        self.assertEqual(
            self.compositions.get("session-i2v-1").final_prompt.active_revision_id,
            parent_id,
        )
        revised = self.service.revise(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
            "Change the camera angle to a zoom while preserving the action.",
        )
        self.assertIn(
            '"motion":"zoom.in"',
            revised.final_prompt.active_revision.compiler_context,
        )

    def test_v3_recognizes_the_supported_camera_revision_vocabulary(self):
        for instruction in (
            "Tilt upward.",
            "Use a truck left.",
            "Add a pedestal down.",
            "Roll clockwise.",
            "Switch to POV.",
            "Use a tracking shot.",
            "Fais un panoramique lent.",
            "Passe en contre-plong\u00e9e.",
            "Change la cam\u00e9ra en contre-plong\u00e9e.",
            "Change le point de vue.",
        ):
            with self.subTest(instruction=instruction):
                self.assertTrue(_instruction_requests_camera_change(instruction))

        self.assertFalse(
            _instruction_requests_camera_change("Shorten only the soundscape.")
        )

    def test_v3_rehydrates_two_identical_camera_clauses_in_directive_order(self):
        self.gateway = CanonicalI2VGateway(I2V_REPEATED_CAMERA_DRAFT)
        self.service.gateway = self.gateway
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.3.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )
        generated = self.service.generate(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(
            generated.final_prompt.active_revision.content.count(
                "The camera pans right."
            ),
            2,
        )
        revised = self.service.revise(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
            "Shorten only the soundscape.",
        )
        revision_prompt = self.gateway.requests[-1].user_prompt
        self.assertEqual(revision_prompt.count("[[camera:camera_1]]"), 1)
        self.assertEqual(revision_prompt.count("[[camera:camera_2]]"), 1)
        self.assertLess(
            revision_prompt.index("[[camera:camera_1]]"),
            revision_prompt.index("[[camera:camera_2]]"),
        )
        self.assertEqual(
            revised.final_prompt.active_revision.content.count(
                "The camera pans right."
            ),
            2,
        )

    def test_v2_generation_remains_on_the_legacy_uncompiled_contract(self):
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.2.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )

        composition = self.service.generate(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(composition.final_prompt.active_revision.content, I2V_PROMPT)

    def test_generates_and_approves_prompt_directly_from_observation_and_brief(self):
        self.service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.1.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )

        composition = self.service.generate(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        composition = self.service.approve(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(composition.final_prompt.active_revision.content, I2V_PROMPT)
        self.assertEqual(
            composition.final_prompt.approved_revision_id,
            composition.final_prompt.active_revision_id,
        )
        self.assertEqual(self.gateway.requests[0].operation_id, "final_prompt.generate")
        self.assertIn("football player in a blue uniform", self.gateway.requests[0].user_prompt)
        self.assertIn("Animate the visible player", self.gateway.requests[0].user_prompt)
        self.assertEqual(composition.reference_plan.revisions, ())
        self.assertEqual(composition.beat_sheet.revisions, ())

    def test_rejects_first_frame_without_the_declared_use(self):
        session = self.sessions.get("session-i2v-1")
        changed = session.update_reference(
            session.references[0].set_uses((ReferenceUse.SUBJECT,))
        )
        changed = changed.add_brief_revision(
            BriefRevision(
                revision_id="brief-i2v-subject-only",
                source_text="Animate the player.",
                content="Animate the visible player taking the shot.",
                creative_freedom=35,
                origin=RevisionOrigin.MANUAL,
                references=(
                    BriefReferenceSnapshot(
                        reference_id="reference-i2v-1",
                        analysis_revision_id="analysis-i2v-1",
                        uses=(ReferenceUse.SUBJECT,),
                    ),
                ),
                parent_revision_id=changed.active_brief_revision_id,
            )
        ).approve_brief()
        self.sessions.save(changed)

        with self.assertRaisesRegex(ValueError, "requires uses first_frame"):
            self.service.configure(
                "session-i2v-1",
                "minimax.h3.i2v.simple",
                "0.1.0",
                (CookbookBinding("first_frame", ("reference-i2v-1",)),),
            )

    def test_linter_rejects_wrong_picture_and_non_official_instruction(self):
        invalid = I2V_PROMPT.replace("<Picture 1>", "<Picture 2>")
        errors = lint_i2v_prompt(invalid)

        self.assertTrue(any("instruction I2VA officielle" in error for error in errors))
        self.assertTrue(any("uniquement <Picture 1>" in error for error in errors))

    def test_official_first_frame_instruction_is_sufficient_for_picture_anchor(self):
        prompt = I2V_PROMPT.replace(
            "the football player shown in <Picture 1>",
            "the visible football player",
        )

        self.assertEqual(lint_i2v_prompt(prompt), ())

    def test_revision_persists_only_the_revised_i2v_document(self):
        gateway = EnvelopeI2VGateway()
        service = PromptCompositionService(
            gateway=gateway,
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=self.sessions,
            compositions=self.compositions,
        )
        service.configure(
            "session-i2v-1",
            "minimax.h3.i2v.simple",
            "0.1.0",
            (CookbookBinding("first_frame", ("reference-i2v-1",)),),
        )
        service.generate("session-i2v-1", CompositionStage.FINAL_PROMPT)

        revised = service.revise(
            "session-i2v-1",
            CompositionStage.FINAL_PROMPT,
            "Keep the camera fixed.",
        )

        self.assertEqual(revised.final_prompt.active_revision.content, I2V_PROMPT)
        self.assertNotIn(
            "SOURCE CONTEXT",
            revised.final_prompt.active_revision.content,
        )


if __name__ == "__main__":
    unittest.main()
