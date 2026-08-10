import json
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

V2_INLINE_EDITABLE = (
    V2_EDITABLE.replace("scene_setup:\n", "scene_setup: ")
    .replace("shot_1:\n", "shot_1: ")
    .replace("overall_soundscape:\n", "overall_soundscape: ")
    .replace("non_diegetic_music:\n", "non_diegetic_music: ")
)

V3_ACTION_PLAN = json.dumps(
    {
        "duration_seconds": 10,
        "reference_policy": {
            "picture_1": "exact_first_frame",
            "picture_2": "appearance_only",
        },
        "scene_setup": "A softly lit room and one adult subject.",
        "beats": [
            {
                "beat_id": "remove_top",
                "start_ms": 0,
                "end_ms": 3500,
                "action": "Remove the top in one continuous motion.",
                "object": "striped top",
                "motion_type": "over_head_removal",
                "hand_contact": "Both hands hold the hem until it clears the head.",
                "motion_path": "The hem travels over the torso, shoulders, arms, and head.",
                "required_end_state": "The top rests visibly on the floor.",
                "expression": "Playful eye contact resumes after the fabric clears the face.",
            },
            {
                "beat_id": "remove_skirt",
                "start_ms": 3500,
                "end_ms": 7000,
                "action": "Lower the skirt and step free of it.",
                "object": "black skirt",
                "motion_type": "step_out_removal",
                "hand_contact": "Both hands keep hold of the waistband while lowering it.",
                "motion_path": "The waistband passes the hips and thighs before each foot steps free.",
                "required_end_state": "The skirt lands beside the top.",
                "expression": "The subject keeps a playful expression.",
            },
        ],
        "final_pose": {
            "start_ms": 7000,
            "description": "Shift weight to one leg and hold the requested final pose.",
            "expression": "Direct playful eye contact.",
            "hold_until_end": True,
        },
        "camera": {
            "start_ms": 7500,
            "end_ms": 9500,
            "movement": "Pedestal down on the frontal axis while tilting upward.",
            "visible_perspective_change": "The lower body becomes more prominent against the rising background.",
            "frontal_axis": True,
            "during": "held_final_pose",
        },
        "overall_soundscape": "Quiet room tone, fabric friction, breathing, and soft landings.",
        "non_diegetic_music": "N/A",
    },
    ensure_ascii=False,
)

_V4_ACTION_PLAN_DATA = json.loads(V3_ACTION_PLAN)
for _beat in _V4_ACTION_PLAN_DATA["beats"]:
    _beat["complexity"] = "simple"
_V4_ACTION_PLAN_DATA["camera"].pop("frontal_axis")
_V4_ACTION_PLAN_DATA["camera"]["path_type"] = "pedestal"
V4_ACTION_PLAN = json.dumps(_V4_ACTION_PLAN_DATA, ensure_ascii=False)

_SUPERVISED_ACTION_PLAN_DATA = json.loads(V4_ACTION_PLAN)
for _beat in _SUPERVISED_ACTION_PLAN_DATA["beats"]:
    _beat["substeps"] = [
        {
            "substep_id": f'{_beat["beat_id"]}_continuous',
            "start_ms": _beat["start_ms"],
            "end_ms": _beat["end_ms"],
            "action": _beat["action"],
            "left_hand": "The left hand preserves its stated contact until release.",
            "right_hand": "The right hand preserves its stated contact until release.",
            "object_state_after": _beat["required_end_state"],
        }
    ]
_SUPERVISED_ACTION_PLAN_DATA["continuity_concerns"] = [
    {
        "concern_id": "retained_garment_visibility",
        "category": "state_visibility_conflict",
        "description": "A retained garment may cover a requested visible region.",
        "proposed_resolution": "Choose either garment retention or explicit repositioning.",
        "resolution": None,
    }
]
SUPERVISED_ACTION_PLAN = json.dumps(
    _SUPERVISED_ACTION_PLAN_DATA,
    ensure_ascii=False,
)
_ARBITRATION_DECISION = (
    "Retain the garment and remove the incompatible visibility request."
)
_RECONCILED_ACTION_PLAN_DATA = json.loads(SUPERVISED_ACTION_PLAN)
_RECONCILED_ACTION_PLAN_DATA["duration_seconds"] = 12
_RECONCILED_ACTION_PLAN_DATA["beats"][0]["action"] = (
    "Remove the top while preserving the retained garment coverage."
)
_RECONCILED_ACTION_PLAN_DATA["continuity_concerns"][0]["resolution"] = (
    _ARBITRATION_DECISION
)
RECONCILED_ACTION_PLAN = json.dumps(
    _RECONCILED_ACTION_PLAN_DATA,
    ensure_ascii=False,
)


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


class PlannedGateway(Gateway):
    def _content_for(self, request):
        if request.operation_id == "action_plan.generate":
            return V3_ACTION_PLAN
        return V2_EDITABLE

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self._content_for(request),
        )

    def stream(self, request):
        self.requests.append(request)
        content = self._content_for(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            result=CompletionResult(model_id=request.model_id, content=content),
        )


class PlannedV4Gateway(PlannedGateway):
    def _content_for(self, request):
        if request.operation_id == "action_plan.generate":
            return V4_ACTION_PLAN
        return V2_INLINE_EDITABLE


class SupervisedGateway(PlannedGateway):
    def _content_for(self, request):
        if request.operation_id == "action_plan.generate":
            return SUPERVISED_ACTION_PLAN
        if request.operation_id == "action_plan.reconcile":
            return RECONCILED_ACTION_PLAN
        return V2_INLINE_EDITABLE


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
            "- SUJETS VISIBLES\nThe same adult subject.\n"
            "- APPARENCE ET TRAITS DISTINCTIFS\nMatching face, skin, and body proportions.\n"
            "- POSE, EXPRESSION ET DIRECTION DU REGARD\nA kneeling side pose looking away.\n"
            "- COMPOSITION, CADRAGE ET CAMÉRA\nA high-angle close-up.\n"
            "- INCERTITUDES\nN/A",
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

    def test_catalog_exposes_the_elastic_v5_cookbook(self):
        cookbook = self.service.cookbooks.get("undressing.single_shot", "0.5.0")

        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.single_shot_elastic_v1",
        )
        self.assertIn("preferred target", cookbook.beat_sheet_system_prompt)
        self.assertIn("retimed", cookbook.final_prompt_user_prompt)

    def test_catalog_exposes_the_bounded_v6_without_changing_prompts(self):
        bounded = self.service.cookbooks.get("undressing.single_shot", "0.6.0")
        witness = self.service.cookbooks.get("undressing.single_shot", "0.5.0")

        self.assertEqual(
            bounded.output_contract,
            "minimax.h3.ref2v.single_shot_elastic_v2",
        )
        self.assertEqual(bounded.beat_sheet_system_prompt, witness.beat_sheet_system_prompt)
        self.assertEqual(bounded.beat_sheet_user_prompt, witness.beat_sheet_user_prompt)
        self.assertEqual(bounded.final_prompt_system_prompt, witness.final_prompt_system_prompt)
        self.assertEqual(bounded.final_prompt_user_prompt, witness.final_prompt_user_prompt)

    def test_catalog_exposes_the_advisory_v7(self):
        cookbook = self.service.cookbooks.get("undressing.single_shot", "0.7.0")

        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.single_shot_elastic_v3",
        )
        self.assertIn("beyond the requested duration", cookbook.beat_sheet_system_prompt)
        self.assertIn("over 15 seconds", cookbook.beat_sheet_system_prompt)

    def test_catalog_exposes_recoverable_v7_1_without_changing_prompts(self):
        recoverable = self.service.cookbooks.get("undressing.single_shot", "0.7.1")
        witness = self.service.cookbooks.get("undressing.single_shot", "0.7.0")

        self.assertEqual(
            recoverable.output_contract,
            "minimax.h3.ref2v.single_shot_elastic_v4",
        )
        self.assertEqual(recoverable.beat_sheet_system_prompt, witness.beat_sheet_system_prompt)
        self.assertEqual(recoverable.beat_sheet_user_prompt, witness.beat_sheet_user_prompt)
        self.assertEqual(recoverable.final_prompt_system_prompt, witness.final_prompt_system_prompt)
        self.assertEqual(recoverable.final_prompt_user_prompt, witness.final_prompt_user_prompt)

    def test_catalog_exposes_the_supervised_v8_contract(self):
        cookbook = self.service.cookbooks.get("undressing.single_shot", "0.8.0")

        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.single_shot_supervised_v1",
        )
        self.assertIn("contiguous substeps", cookbook.beat_sheet_system_prompt)
        self.assertIn("continuity_concern", cookbook.beat_sheet_system_prompt)
        self.assertIn(
            "human arbitration",
            cookbook.beat_sheet_reconcile_system_prompt,
        )
        self.assertIn("{{DECISIONS}}", cookbook.beat_sheet_reconcile_user_prompt)
        self.assertIn("human-approved", cookbook.final_prompt_system_prompt)

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
        shared_boundary = V2_COMPILED_PROMPT.replace(
            "At 00:06.500",
            "At 00:03.000",
        )
        exact_maximum = V2_COMPILED_PROMPT.replace(
            "At 00:06.500",
            "At 00:15.000",
        )
        over_maximum = V2_COMPILED_PROMPT.replace(
            "At 00:06.500",
            "At 00:15.001",
        )

        self.assertTrue(
            any(
                "mapping de références" in error
                for error in lint_compiled_ref2v_single_shot_prompt(changed_header)
            )
        )
        self.assertTrue(
            any(
                "non décroissants" in error
                for error in lint_compiled_ref2v_single_shot_prompt(reversed_timing)
            )
        )
        self.assertEqual(
            lint_compiled_ref2v_single_shot_prompt(shared_boundary),
            (),
        )
        self.assertEqual(
            lint_compiled_ref2v_single_shot_prompt(exact_maximum),
            (),
        )
        self.assertTrue(
            any(
                "durée maximale" in error
                for error in lint_compiled_ref2v_single_shot_prompt(over_maximum)
            )
        )

    def test_compiler_accepts_inline_editable_fields(self):
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.2.0",
            self.bindings(),
        )
        self.gateway.content = V2_INLINE_EDITABLE

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(
            composition.final_prompt.active_revision.content,
            V2_COMPILED_PROMPT,
        )

    def test_v3_plans_then_writes_and_compiles_with_two_llm_calls(self):
        self.gateway = PlannedGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.3.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            ["action_plan.generate", "final_prompt.generate"],
        )
        self.assertEqual(
            composition.beat_sheet.approved_revision_id,
            composition.beat_sheet.active_revision_id,
        )
        self.assertEqual(
            json.loads(composition.beat_sheet.active_revision.content),
            json.loads(V3_ACTION_PLAN),
        )
        self.assertEqual(
            composition.final_prompt.active_revision.content,
            V2_COMPILED_PROMPT,
        )
        planner_prompt = self.gateway.requests[0].user_prompt
        self.assertIn("Matching face, skin, and body proportions", planner_prompt)
        self.assertNotIn("kneeling side pose", planner_prompt)
        self.assertNotIn("high-angle close-up", planner_prompt)
        self.assertIn("appearance-only projection", planner_prompt)
        self.assertIn('"beat_id"', self.gateway.requests[1].user_prompt)

    def test_v3_stream_keeps_the_internal_json_out_of_the_prompt_deltas(self):
        self.gateway = PlannedGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.3.0",
            self.bindings(),
        )

        events = list(
            self.service.stream_generate(
                "session-ref2v-1",
                CompositionStage.FINAL_PROMPT,
            )
        )

        plan_deltas = "".join(
            event.text
            for event in events
            if event.kind is StreamEventKind.DELTA
            and event.document_stage is CompositionStage.BEAT_SHEET
        )
        prompt_deltas = "".join(
            event.text
            for event in events
            if event.kind is StreamEventKind.DELTA
            and event.document_stage is None
        )
        self.assertEqual(plan_deltas, V3_ACTION_PLAN)
        self.assertEqual(prompt_deltas, V2_EDITABLE)
        self.assertNotIn('"reference_policy"', prompt_deltas)
        plan_status = next(
            event
            for event in events
            if event.kind is StreamEventKind.STATUS and event.composition is not None
        )
        self.assertEqual(
            plan_status.composition.beat_sheet.approved_revision_id,
            plan_status.composition.beat_sheet.active_revision_id,
        )
        self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
        self.assertEqual(events[-1].text, V2_COMPILED_PROMPT)
        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            ["action_plan.generate", "final_prompt.generate"],
        )

    def test_v3_rejects_an_invalid_plan_before_calling_the_writer(self):
        self.gateway = PlannedGateway()
        self.gateway._content_for = lambda request: "{}"
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.3.0",
            self.bindings(),
        )

        with self.assertRaisesRegex(ValueError, "invalid Ref2V action plan"):
            self.service.generate(
                "session-ref2v-1",
                CompositionStage.FINAL_PROMPT,
            )

        self.assertEqual(len(self.gateway.requests), 1)
        composition = self.compositions.get("session-ref2v-1")
        self.assertIsNone(composition.beat_sheet.active_revision)
        self.assertIsNone(composition.final_prompt.active_revision)

    def test_v3_stream_exposes_a_rejected_plan_candidate_for_diagnostic(self):
        self.gateway = PlannedGateway()
        self.gateway._content_for = lambda request: "{}"
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.3.0",
            self.bindings(),
        )

        events = []
        with self.assertRaisesRegex(ValueError, "invalid Ref2V action plan"):
            for event in self.service.stream_generate(
                "session-ref2v-1",
                CompositionStage.FINAL_PROMPT,
            ):
                events.append(event)

        plan_candidate = "".join(
            event.text
            for event in events
            if event.kind is StreamEventKind.DELTA
            and event.document_stage is CompositionStage.BEAT_SHEET
        )
        self.assertEqual(plan_candidate, "{}")
        self.assertEqual(len(self.gateway.requests), 1)

    def test_v4_uses_the_camera_path_and_complexity_contract(self):
        self.gateway = PlannedV4Gateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.4.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            ["action_plan.generate", "final_prompt.generate"],
        )
        action_plan = composition.beat_sheet.active_revision.content
        self.assertIn('"complexity": "simple"', action_plan)
        self.assertIn('"path_type": "pedestal"', action_plan)
        self.assertNotIn("frontal_axis", action_plan)
        self.assertEqual(
            composition.final_prompt.active_revision.content,
            V2_COMPILED_PROMPT,
        )

    def test_v4_dense_timing_warns_but_still_calls_the_writer(self):
        dense_plan = json.loads(V4_ACTION_PLAN)
        for beat in dense_plan["beats"]:
            beat["complexity"] = "multi_step"
        self.gateway = PlannedV4Gateway()
        self.gateway._content_for = lambda request: (
            json.dumps(dense_plan, ensure_ascii=False)
            if request.operation_id == "action_plan.generate"
            else V2_INLINE_EDITABLE
        )
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.4.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        statuses = {status.stage: status for status in self.service.status(composition)}

        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            ["action_plan.generate", "final_prompt.generate"],
        )
        self.assertEqual(statuses[CompositionStage.BEAT_SHEET].validation_errors, ())
        self.assertTrue(
            any(
                "11 s" in warning and "sans blocage" in warning
                for warning in statuses[CompositionStage.BEAT_SHEET].validation_warnings
            )
        )

    def test_v5_retimes_a_dense_plan_before_calling_the_writer(self):
        dense_plan = json.loads(V4_ACTION_PLAN)
        dense_plan["beats"][0]["end_ms"] = 1500
        dense_plan["beats"][1]["start_ms"] = 1500
        dense_plan["beats"][1]["end_ms"] = 4500
        self.gateway = PlannedV4Gateway()
        self.gateway._content_for = lambda request: (
            json.dumps(dense_plan, ensure_ascii=False)
            if request.operation_id == "action_plan.generate"
            else V2_INLINE_EDITABLE
        )
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.5.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        plan = json.loads(composition.beat_sheet.active_revision.content)
        statuses = {status.stage: status for status in self.service.status(composition)}
        writer_prompt = self.gateway.requests[1].user_prompt

        self.assertEqual(plan["requested_duration_seconds"], 10)
        self.assertEqual(plan["duration_seconds"], 12)
        self.assertEqual(plan["beats"][0]["end_ms"], 3000)
        self.assertEqual(plan["beats"][1]["start_ms"], 3000)
        self.assertNotIn("requested_duration_seconds", writer_prompt)
        self.assertIn('"duration_seconds": 12', writer_prompt)
        self.assertTrue(
            any(
                "10 s à 12 s" in warning
                for warning in statuses[CompositionStage.BEAT_SHEET].validation_warnings
            )
        )

    def test_v6_absorbs_multi_step_expansion_before_extending_duration(self):
        dense_plan = json.loads(V4_ACTION_PLAN)
        dense_plan["beats"][1]["complexity"] = "multi_step"
        self.gateway = PlannedV4Gateway()
        self.gateway._content_for = lambda request: (
            json.dumps(dense_plan, ensure_ascii=False)
            if request.operation_id == "action_plan.generate"
            else V2_INLINE_EDITABLE
        )
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.6.0",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        plan = json.loads(composition.beat_sheet.active_revision.content)
        writer_prompt = self.gateway.requests[1].user_prompt

        self.assertEqual(plan["requested_duration_seconds"], 10)
        self.assertEqual(plan["duration_seconds"], 10)
        self.assertEqual(plan["beats"][1]["end_ms"], 8000)
        self.assertEqual(plan["final_pose"]["start_ms"], 8000)
        self.assertIn("final_hold_reduced", plan["timing_adjustments"])
        self.assertNotIn("timing_adjustments", writer_prompt)
        self.assertNotIn("requested_duration_seconds", writer_prompt)
        self.assertIn('"duration_seconds": 10', writer_prompt)

    def test_v7_normalizes_labels_and_keeps_contract_mismatches_as_warnings(self):
        plan = json.loads(V4_ACTION_PLAN)
        for beat in plan["beats"]:
            beat["complexity"] = "multi_step"
        editable = V2_INLINE_EDITABLE.replace(
            "The setting is a quiet white-walled room",
            "The supplied scene starts from <Image 1> in a quiet white-walled room",
        )
        self.gateway = PlannedV4Gateway()
        self.gateway._content_for = lambda request: (
            json.dumps(plan, ensure_ascii=False)
            if request.operation_id == "action_plan.generate"
            else editable
        )
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.7.0",
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
        prompt = composition.final_prompt.active_revision.content
        statuses = {status.stage: status for status in self.service.status(composition)}

        self.assertNotIn("<Image 1>", prompt)
        self.assertIn("the supplied starting frame", prompt)
        self.assertEqual(
            approved.final_prompt.approved_revision_id,
            approved.final_prompt.active_revision_id,
        )
        self.assertEqual(statuses[CompositionStage.FINAL_PROMPT].validation_errors, ())
        self.assertTrue(
            any(
                "Landmarks du plan absents" in warning
                for warning in statuses[CompositionStage.FINAL_PROMPT].validation_warnings
            )
        )

    def test_v7_1_repairs_a_pose_at_requested_end_without_retrying_the_planner(self):
        plan = json.loads(V4_ACTION_PLAN)
        plan["beats"][1]["end_ms"] = 10_000
        plan["final_pose"]["start_ms"] = 10_000
        plan["camera"] = None
        self.gateway = PlannedV4Gateway()
        self.gateway._content_for = lambda request: (
            json.dumps(plan, ensure_ascii=False)
            if request.operation_id == "action_plan.generate"
            else V2_INLINE_EDITABLE
        )
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.7.1",
            self.bindings(),
        )

        composition = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )
        action_plan = json.loads(composition.beat_sheet.active_revision.content)
        statuses = {status.stage: status for status in self.service.status(composition)}

        self.assertEqual(len(self.gateway.requests), 2)
        self.assertEqual(action_plan["duration_seconds"], 12)
        self.assertEqual(action_plan["final_pose"]["start_ms"], 10_000)
        self.assertIn("final_hold_repaired", action_plan["timing_adjustments"])
        self.assertIn('"duration_seconds": 12', self.gateway.requests[1].user_prompt)
        self.assertTrue(
            any(
                "2 s nécessaires" in warning
                for warning in statuses[CompositionStage.BEAT_SHEET].validation_warnings
            )
        )

    def test_v8_requires_human_plan_approval_before_the_writer(self):
        self.gateway = SupervisedGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.8.0",
            self.bindings(),
        )

        with self.assertRaisesRegex(ValueError, "approve"):
            self.service.generate(
                "session-ref2v-1",
                CompositionStage.FINAL_PROMPT,
            )
        planned = self.service.generate(
            "session-ref2v-1",
            CompositionStage.BEAT_SHEET,
        )
        statuses = {status.stage: status for status in self.service.status(planned)}

        self.assertEqual(len(self.gateway.requests), 1)
        self.assertIsNone(planned.beat_sheet.approved_revision_id)
        self.assertTrue(
            any(
                "state_visibility_conflict" in warning
                for warning in statuses[CompositionStage.BEAT_SHEET].validation_warnings
            )
        )

        edited_plan = json.loads(planned.beat_sheet.active_revision.content)
        edited_plan["continuity_concerns"][0]["resolution"] = (
            "Retain the garment and remove the incompatible visibility request."
        )
        edited = self.service.edit(
            "session-ref2v-1",
            CompositionStage.BEAT_SHEET,
            json.dumps(edited_plan, ensure_ascii=False),
        )
        edited_status = {
            status.stage: status for status in self.service.status(edited)
        }
        approved = self.service.approve(
            "session-ref2v-1",
            CompositionStage.BEAT_SHEET,
        )
        final = self.service.generate(
            "session-ref2v-1",
            CompositionStage.FINAL_PROMPT,
        )

        self.assertNotEqual(
            edited.beat_sheet.active_revision_id,
            planned.beat_sheet.active_revision_id,
        )
        self.assertFalse(
            any(
                "state_visibility_conflict" in warning
                for warning in edited_status[CompositionStage.BEAT_SHEET].validation_warnings
            )
        )
        self.assertEqual(
            approved.beat_sheet.approved_revision_id,
            approved.beat_sheet.active_revision_id,
        )
        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            ["action_plan.generate", "final_prompt.generate"],
        )
        writer_prompt = self.gateway.requests[-1].user_prompt
        self.assertIn("remove_top_continuous", writer_prompt)
        self.assertIn("Retain the garment", writer_prompt)
        self.assertIsNotNone(final.final_prompt.active_revision)

    def test_v8_reconciles_human_decisions_into_a_new_plan_revision(self):
        self.gateway = SupervisedGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.8.0",
            self.bindings(),
        )
        planned = self.service.generate(
            "session-ref2v-1",
            CompositionStage.BEAT_SHEET,
        )
        previous_revision_id = planned.beat_sheet.active_revision_id

        events = list(
            self.service.stream_reconcile_action_plan(
                "session-ref2v-1",
                {"retained_garment_visibility": _ARBITRATION_DECISION},
                "Give the physical transition more time.",
            )
        )

        reconciled = events[-1].composition
        self.assertIsNotNone(reconciled)
        self.assertEqual(events[-1].document_stage, CompositionStage.BEAT_SHEET)
        self.assertNotEqual(
            reconciled.beat_sheet.active_revision_id,
            previous_revision_id,
        )
        self.assertIsNone(reconciled.beat_sheet.approved_revision_id)
        self.assertEqual(
            reconciled.beat_sheet.active_revision.parent_revision_id,
            previous_revision_id,
        )
        revised_plan = json.loads(reconciled.beat_sheet.active_revision.content)
        self.assertEqual(revised_plan["duration_seconds"], 12)
        self.assertEqual(
            revised_plan["continuity_concerns"][0]["resolution"],
            _ARBITRATION_DECISION,
        )
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, "action_plan.reconcile")
        self.assertIn(_ARBITRATION_DECISION, request.user_prompt)
        self.assertIn("Give the physical transition more time", request.user_prompt)
        self.assertIn('"requested_duration_seconds": 10', request.user_prompt)

    def test_v8_rejects_an_arbitration_for_an_unknown_concern(self):
        self.gateway = SupervisedGateway()
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.8.0",
            self.bindings(),
        )
        self.service.generate("session-ref2v-1", CompositionStage.BEAT_SHEET)

        with self.assertRaisesRegex(ValueError, "unknown continuity concern"):
            self.service.stream_reconcile_action_plan(
                "session-ref2v-1",
                {"missing": "Apply this."},
            )

    def test_v8_does_not_persist_a_reconciliation_that_ignores_the_decision(self):
        self.gateway = SupervisedGateway()
        self.gateway._content_for = lambda request: SUPERVISED_ACTION_PLAN
        self.service.gateway = self.gateway
        self.service.configure(
            "session-ref2v-1",
            "undressing.single_shot",
            "0.8.0",
            self.bindings(),
        )
        planned = self.service.generate(
            "session-ref2v-1",
            CompositionStage.BEAT_SHEET,
        )
        previous_revision_id = planned.beat_sheet.active_revision_id

        with self.assertRaisesRegex(ValueError, "did not apply decision"):
            list(
                self.service.stream_reconcile_action_plan(
                    "session-ref2v-1",
                    {"retained_garment_visibility": _ARBITRATION_DECISION},
                )
            )

        stored = self.compositions.get("session-ref2v-1")
        self.assertEqual(stored.beat_sheet.active_revision_id, previous_revision_id)

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
