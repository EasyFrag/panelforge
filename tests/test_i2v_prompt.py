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


if __name__ == "__main__":
    unittest.main()
