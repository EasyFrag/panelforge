import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    PromptCompositionService,
    StreamEventKind,
    StreamPhase,
    lint_compiled_ref2v_single_shot_prompt,
    lint_ref2v_single_shot_prompt,
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


VALID_PROMPT = """subject_definitions:
<Subject 1> is the same person grounded in <Picture 1> and <Picture 2>, preserving identity, face, hair, and body proportions.
<Picture 1> is the fully preserved concrete first frame, including the dressed pose, framing, room, and light.
summary:
[keyframe completion + reference generation] A single continuous shot follows <Subject 1> removing the requested shirt from the exact starting frame.
retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved for identity and stable appearance while pose, clothing state, and action evolve.
detailed_description:
Naturalistic live-action with soft indoor light and restrained handheld camera drift.
[Shot 1] The opening state exactly follows <Picture 1>: <Subject 1> stands centered in the same shirt, pose, room, framing, and light. Both hands grip the shirt hem, pull it upward across the torso, guide the fabric clear of the shoulders and head, then release it beside the body. Weight shifts naturally between the feet, breathing and hair respond to the motion, and the shot ends with the removed shirt visible beside the same person.
overall_soundscape:
Quiet room tone, cloth friction, breathing, and the soft landing of fabric remain synchronized with the movement.
non_diegetic_music:
N/A"""

V2_EDITABLE = """scene_setup:
The setting is a quiet white-walled room with diffuse light. The target video is one continuous shot, and the subject smiles softly while the camera remains gently attentive.
shot_1:
The scene begins from the exact dressed state in the starting frame. Both hands grasp the shirt hem and lift it steadily across the torso. At 00:03.000, the fabric clears the shoulders and head. At 00:06.500, the subject releases the shirt beside the body, shifts weight naturally, and ends in the requested stable state with the removed garment visible.
overall_soundscape:
Quiet indoor room tone, soft cloth movement, natural breathing, and a light fabric landing.
non_diegetic_music:
N/A"""

V2_COMPILED_PROMPT = """<Picture 1>: the exact fully preserved starting frame at 0.00 seconds, containing the subject in the dressed starting state and defining pose, framing, room, lighting, and visible composition.
Use <Picture 2> only as a body and appearance reference for the same subject shown in <Picture 1>; do not use it as a frame, pose, background, composition, or target state.

The setting is a quiet white-walled room with diffuse light. The target video is one continuous shot, and the subject smiles softly while the camera remains gently attentive.

Shot 1: The scene begins from the exact dressed state in the starting frame. Both hands grasp the shirt hem and lift it steadily across the torso. At 00:03.000, the fabric clears the shoulders and head. At 00:06.500, the subject releases the shirt beside the body, shifts weight naturally, and ends in the requested stable state with the removed garment visible.

overall_soundscape: Quiet indoor room tone, soft cloth movement, natural breathing, and a light fabric landing.

non_diegetic_music: N/A"""


class Gateway:
    def __init__(self, content=VALID_PROMPT):
        self.requests: list[CompletionRequest] = []
        self.content = content

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(model_id=request.model_id, content=self.content)

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=self.content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            result=CompletionResult(model_id=request.model_id, content=self.content),
        )


def approved_session() -> PromptLabSession:
    references = []
    snapshots = []
    definitions = (
        (
            "start",
            "dressed_start",
            (ReferenceUse.FIRST_FRAME, ReferenceUse.SUBJECT),
            "The same person stands centered, wearing a shirt in a softly lit room.",
        ),
        (
            "body",
            "body_reference",
            (ReferenceUse.SUBJECT,),
            "A body reference of the same person with matching facial and body traits.",
        ),
    )
    for key, role, uses, content in definitions:
        revision = AnalysisRevision(
            revision_id=f"analysis-{key}",
            content=content,
            origin=RevisionOrigin.MODEL,
        )
        reference = PromptReference(
            reference_id=f"reference-{key}",
            asset_id=f"asset-{key}",
            role=role,
            label=f"{key}.png",
            revisions=(revision,),
            active_revision_id=revision.revision_id,
            approved_revision_id=revision.revision_id,
            uses=uses,
        )
        references.append(reference)
        snapshots.append(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=revision.revision_id,
                uses=uses,
            )
        )
    session = PromptLabSession(
        session_id="session-ref2v-1",
        model_id="vision-model",
        profile_id="minimax.h3.reference",
        profile_version="0.3.0",
        references=tuple(references),
    )
    return session.add_brief_revision(
        BriefRevision(
            revision_id="brief-ref2v-1",
            source_text="Retire le haut en un geste continu pendant une vidéo de dix secondes.",
            content=(
                "Ten-second single shot. Remove the shirt sequentially, show the "
                "physical path clearly, and finish with the removed garment visible."
            ),
            creative_freedom=35,
            origin=RevisionOrigin.MODEL,
            references=tuple(snapshots),
        )
    ).approve_brief()


class Ref2VPromptTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.sessions = LocalPromptSessionStore(self.directory.name)
        self.sessions.create(approved_session())
        self.compositions = LocalPromptCompositionStore(self.directory.name)
        self.gateway = Gateway()
        self.service = PromptCompositionService(
            gateway=self.gateway,
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=self.sessions,
            compositions=self.compositions,
        )

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def bindings():
        return (
            CookbookBinding("dressed_start", ("reference-start",)),
            CookbookBinding("body_reference", ("reference-body",)),
        )

    def test_catalog_exposes_direct_two_reference_cookbook(self):
        cookbook = self.service.cookbooks.get("undressing.single_shot", "0.1.0")

        self.assertEqual(cookbook.output_contract, "minimax.h3.ref2va.single_shot")
        self.assertEqual(cookbook.stages, ("final_prompt",))
        self.assertEqual(
            [slot.slot_id for slot in cookbook.slots],
            ["dressed_start", "body_reference"],
        )
        self.assertIn("about three seconds", cookbook.final_prompt_system_prompt)
        self.assertNotIn("adult", cookbook.final_prompt_system_prompt.lower())

    def test_v2_compiles_the_model_fields_into_the_fixed_minimax_format(self):
        cookbook = self.service.cookbooks.get("undressing.single_shot", "0.2.0")
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.single_shot_compiled",
        )
        self.assertEqual(cookbook.stages, ("final_prompt",))
        self.assertIn("scene_setup:", cookbook.final_prompt_system_prompt)

        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.2.0",
            self.bindings(),
        )
        self.gateway.content = "READ-ONLY CONTEXT\n\n" + V2_EDITABLE

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(
            composition.final_prompt.active_revision.content,
            V2_COMPILED_PROMPT,
        )
        self.assertEqual(
            lint_compiled_ref2v_single_shot_prompt(V2_COMPILED_PROMPT),
            (),
        )
        self.assertTrue(V2_COMPILED_PROMPT.startswith("<Picture 1>:"))
        self.assertNotIn("scene_setup:", V2_COMPILED_PROMPT)
        request = self.gateway.requests[-1]
        self.assertIn("<Picture 1> / start.png", request.user_prompt)
        self.assertIn("<Picture 2> / body.png", request.user_prompt)
        self.assertIn("Ten-second single shot", request.user_prompt)

    def test_v2_revision_is_recompiled_without_exposing_internal_fields(self):
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.2.0",
            self.bindings(),
        )
        self.gateway.content = V2_EDITABLE
        self.service.generate("session-ref2v-1", CompositionStage.FINAL_PROMPT)
        self.gateway.content = V2_EDITABLE.replace(
            "smiles softly",
            "keeps a calm expression",
        )

        composition = self.service.revise(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
            "Use a calmer expression.",
        )

        content = composition.final_prompt.active_revision.content
        self.assertTrue(content.startswith("<Picture 1>:"))
        self.assertIn("keeps a calm expression", content)
        self.assertNotIn("scene_setup:", content)
        self.assertIn("CURRENT COMPILED PROMPT", self.gateway.requests[-1].user_prompt)

    def test_v2_stream_persists_and_returns_only_the_compiled_result(self):
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.2.0",
            self.bindings(),
        )
        self.gateway.content = V2_EDITABLE

        events = list(
            self.service.stream_generate(
                "session-ref2v-1",
                CompositionStage.FINAL_PROMPT,
            )
        )

        self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
        self.assertEqual(events[-1].text, V2_COMPILED_PROMPT)
        self.assertEqual(
            events[-1].composition.final_prompt.active_revision.content,
            V2_COMPILED_PROMPT,
        )

    def test_v2_rejects_an_incomplete_model_document_before_persistence(self):
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.2.0",
            self.bindings(),
        )
        self.gateway.content = V2_EDITABLE.replace("non_diegetic_music:\nN/A", "")

        with self.assertRaisesRegex(ValueError, "missing marker"):
            self.service.generate("session-ref2v-1", CompositionStage.FINAL_PROMPT)

        composition = self.compositions.get("session-ref2v-1")
        self.assertIsNone(composition.final_prompt.active_revision)

    def test_v2_linter_locks_the_reference_header_and_timestamp_order(self):
        changed_header = V2_COMPILED_PROMPT.replace(
            "<Picture 1>: the exact fully preserved starting frame",
            "<Picture 1>: an approximate starting frame",
        )
        reversed_timing = V2_COMPILED_PROMPT.replace(
            "At 00:06.500",
            "At 00:02.000",
        )

        self.assertTrue(
            any(
                "mapping de références" in error
                for error in lint_compiled_ref2v_single_shot_prompt(changed_header)
            )
        )
        self.assertTrue(
            any(
                "strictement croissants" in error
                for error in lint_compiled_ref2v_single_shot_prompt(reversed_timing)
            )
        )

    def test_generates_directly_from_two_observations_and_approved_brief(self):
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.1.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        approved = self.service.approve(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(composition.final_prompt.active_revision.content, VALID_PROMPT)
        self.assertEqual(
            approved.final_prompt.approved_revision_id,
            approved.final_prompt.active_revision_id,
        )
        request = self.gateway.requests[0]
        self.assertIn("<Picture 1> / start.png", request.user_prompt)
        self.assertIn("<Picture 2> / body.png", request.user_prompt)
        self.assertIn("Ten-second single shot", request.user_prompt)

    def test_linter_rejects_second_picture_as_frame_and_extra_shot(self):
        invalid = VALID_PROMPT.replace(
            "summary:\n",
            "<Picture 2> is the final frame.\nsummary:\n",
        ).replace(
            "overall_soundscape:\n",
            "[Shot 2] At 00:05.000, a cut occurs.\noverall_soundscape:\n",
        )

        errors = lint_ref2v_single_shot_prompt(invalid)

        self.assertTrue(any("pas une frame autonome" in error for error in errors))
        self.assertTrue(any("exactement un [Shot 1]" in error for error in errors))

    def test_rejects_wrongly_tagged_reference_in_body_slot(self):
        with self.assertRaisesRegex(ValueError, "does not support uses first_frame"):
            self.service.configure(
                "session-ref2v-1",
                "undressing.single_shot",
                "0.1.0",
                (
                    CookbookBinding("dressed_start", ("reference-start",)),
                    CookbookBinding("body_reference", ("reference-start",)),
                ),
            )


if __name__ == "__main__":
    unittest.main()
