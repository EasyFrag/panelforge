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
    composition_picture_mapping,
    lint_composition_document,
)
from panelforge.domain import (
    AnalysisRevision,
    BriefReferenceSnapshot,
    BriefRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    PromptComposition,
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


COOKBOOK_ROOT = PROJECT_ROOT / "prompt_cookbooks"
SUBJECT_DEFINITIONS = """subject_definitions:
<Subject 1> is fighter A from <Picture 1>.
<Subject 2> is fighter B from <Picture 2>.
<Subject 3> is the arena from <Picture 3>."""
REFERENCE_PLAN = SUBJECT_DEFINITIONS + """
retention_policy:
Keep the identity and costume of <Subject 1> fully preserved while pose and action may change.
Keep the identity and costume of <Subject 2> fully preserved while pose and action may change.
Keep the environment identity of <Subject 3> fully preserved while lighting may react."""
FINAL_BODY = """summary:
[reference generation] A readable six-shot arcade duel in <Subject 3>.
retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved and kept visually distinct from <Subject 2>
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved
detailed_description:
Live-action dark fantasy with restrained contrast and precise arcade readability.
[Shot 1] <Subject 1> faces <Subject 2> inside <Subject 3>.
[Shot 2] At 00:02.500, <Subject 1> and <Subject 2> hold position as <Subject 3> is revealed.
[Shot 3] At 00:05.000, <Subject 1> strikes <Subject 2> once inside <Subject 3>.
[Shot 4] At 00:07.500, <Subject 2> blocks <Subject 1> and counters inside <Subject 3>.
[Shot 5] At 00:10.000, <Subject 1> and <Subject 2> reverse momentum inside <Subject 3>.
[Shot 6] At 00:13.000, <Subject 1> and <Subject 2> meet in one final clash inside <Subject 3>.
overall_soundscape:
Arena ambience, cloth movement, footwork and synchronized impacts.
non_diegetic_music:
Tense arcade percussion builds toward the final clash."""
BEAT_SHEET = """production_settings:
15 seconds, 16:9, six shots.
continuity_rules:
Fighter A stays screen-left and fighter B screen-right until the reversal.
beat_sheet:
[Shot 1] <Subject 1> and <Subject 2> face off inside <Subject 3>.
[Shot 2] At 00:02.500, <Subject 1> and <Subject 2> hold as <Subject 3> is revealed.
[Shot 3] At 00:05.000, <Subject 1> strikes <Subject 2> inside <Subject 3>.
[Shot 4] At 00:07.500, <Subject 2> blocks <Subject 1> and counters inside <Subject 3>.
[Shot 5] At 00:10.000, <Subject 1> and <Subject 2> reverse momentum inside <Subject 3>.
[Shot 6] At 00:13.000, <Subject 1> and <Subject 2> clash inside <Subject 3>."""


class FakeGateway:
    def __init__(self) -> None:
        self.requests: list[CompletionRequest] = []

    def list_models(self):
        return (ModelDescriptor("vision-model"),)

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self._content(request.operation_id),
        )

    def stream(self, request):
        self.requests.append(request)
        content = self._content(request.operation_id)
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.GENERATING,
            text="Génération…",
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=content,
            result=CompletionResult(model_id=request.model_id, content=content),
        )

    @staticmethod
    def _content(operation_id):
        if operation_id.startswith("reference_plan"):
            return REFERENCE_PLAN
        if operation_id.startswith("beat_sheet"):
            return BEAT_SHEET
        return FINAL_BODY


class MutatingGateway(FakeGateway):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def complete(self, request):
        result = super().complete(request)
        self.callback()
        return result


def approved_session() -> PromptLabSession:
    references = []
    snapshots = []
    for index, role in enumerate(("fighter_a", "fighter_b", "arena"), start=1):
        revision = AnalysisRevision(
            revision_id=f"analysis-{index}",
            content=f"Approved visual facts for {role}.",
            origin=RevisionOrigin.MODEL,
        )
        reference = PromptReference(
            reference_id=f"reference-{index}",
            asset_id=f"asset-{index}",
            role=role,
            label=f"Image {index}",
            revisions=(revision,),
            active_revision_id=revision.revision_id,
            approved_revision_id=revision.revision_id,
            uses=(
                (ReferenceUse.ENVIRONMENT,)
                if role == "arena"
                else (ReferenceUse.SUBJECT,)
            ),
        )
        references.append(reference)
        snapshots.append(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=revision.revision_id,
                uses=reference.uses,
            )
        )
    session = PromptLabSession(
        session_id="session-1",
        model_id="vision-model",
        profile_id="minimax.h3.reference",
        profile_version="0.3.0",
        references=tuple(references),
    )
    return session.add_brief_revision(
        BriefRevision(
            revision_id="brief-1",
            source_text="A and B fight in the arena.",
            content="A clear duel ending in a final clash.",
            creative_freedom=50,
            origin=RevisionOrigin.MODEL,
            references=tuple(snapshots),
        )
    ).approve_brief()


def bindings() -> tuple[CookbookBinding, ...]:
    return (
        CookbookBinding("fighter_a", ("reference-1",)),
        CookbookBinding("fighter_b", ("reference-2",)),
        CookbookBinding("arena", ("reference-3",)),
    )


class PromptCookbookCatalogTest(unittest.TestCase):
    def test_loads_versioned_fighter_cookbook_and_templates(self):
        cookbook = LocalPromptCookbookCatalog(COOKBOOK_ROOT).get(
            "fighter.arcade_versus",
            "0.1.0",
        )

        self.assertEqual(cookbook.target_mode, "ref2va")
        self.assertEqual(cookbook.preset, "readable-v1")
        self.assertEqual(len(cookbook.sources), 2)
        self.assertEqual(cookbook.slots[0].accepted_uses, ("subject", "style"))
        self.assertEqual(cookbook.slots[0].required_uses, ("subject",))
        self.assertEqual(cookbook.slots[0].required_shots, (1, 2, 3, 4, 5, 6))
        self.assertEqual(
            [slot.slot_id for slot in cookbook.slots],
            ["fighter_a", "fighter_b", "arena"],
        )
        self.assertIn("subject_definitions:", cookbook.reference_plan_system_prompt)
        self.assertIn("detailed_description:", cookbook.final_prompt_system_prompt)

    def test_picture_mapping_is_local_contiguous_and_upload_ordered(self):
        composition = PromptComposition(
            source_session_id="session-local-map",
            cookbook=CookbookRef(
                cookbook_id="fighter.arcade_versus",
                version="0.1.0",
                engine_contract_id="minimax.h3.ref2va",
                engine_contract_version="1.0.0",
            ),
            bindings=(
                CookbookBinding("fighter_a", ("reference-2",)),
                CookbookBinding("fighter_b", ("reference-5",)),
                CookbookBinding("arena", ("reference-8",)),
            ),
        )

        self.assertEqual(
            composition_picture_mapping(composition),
            (("reference-2", 1), ("reference-5", 2), ("reference-8", 3)),
        )


class PromptCompositionServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.sessions = LocalPromptSessionStore(self.directory.name)
        self.sessions.create(approved_session())
        self.compositions = LocalPromptCompositionStore(self.directory.name)
        self.gateway = FakeGateway()
        self.service = PromptCompositionService(
            gateway=self.gateway,
            cookbooks=LocalPromptCookbookCatalog(COOKBOOK_ROOT),
            sessions=self.sessions,
            compositions=self.compositions,
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_runs_three_supervised_stages_and_compiles_locked_prefix(self):
        composition = self.service.configure(
            "session-1",
            "fighter.arcade_versus",
            "0.1.0",
            bindings(),
        )

        composition = self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)
        composition = self.service.approve("session-1", CompositionStage.REFERENCE_PLAN)
        composition = self.service.generate("session-1", CompositionStage.BEAT_SHEET)
        composition = self.service.approve("session-1", CompositionStage.BEAT_SHEET)
        composition = self.service.generate("session-1", CompositionStage.FINAL_PROMPT)
        composition = self.service.approve("session-1", CompositionStage.FINAL_PROMPT)

        final = composition.final_prompt.active_revision.content
        self.assertTrue(final.startswith(SUBJECT_DEFINITIONS))
        self.assertNotIn("retention_policy:", final)
        self.assertTrue(final.endswith(FINAL_BODY))
        self.assertTrue(all(status.complete for status in self.service.status(composition)))
        self.assertIn("<Picture 1>", self.gateway.requests[0].user_prompt)
        self.assertIn("Approved visual facts for fighter_a", self.gateway.requests[0].user_prompt)
        self.assertEqual(
            [request.operation_id for request in self.gateway.requests],
            [
                "reference_plan.generate",
                "beat_sheet.generate",
                "final_prompt.generate",
            ],
        )

    def test_upstream_brief_change_marks_history_stale_without_erasing_it(self):
        composition = self.service.configure(
            "session-1",
            "fighter.arcade_versus",
            "0.1.0",
            bindings(),
        )
        composition = self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)
        composition = self.service.approve("session-1", CompositionStage.REFERENCE_PLAN)
        old_revision_id = composition.reference_plan.active_revision_id
        session = self.sessions.get("session-1")
        changed = session.add_brief_revision(
            BriefRevision(
                revision_id="brief-2",
                source_text="A and B fight, with a quieter introduction.",
                content="Short introduction, then one readable duel.",
                creative_freedom=35,
                origin=RevisionOrigin.MANUAL,
                references=session.active_brief_revision.references,
                parent_revision_id="brief-1",
            )
        ).approve_brief()
        self.sessions.save(changed)

        statuses = {item.stage: item for item in self.service.status(composition)}

        self.assertTrue(statuses[CompositionStage.REFERENCE_PLAN].stale)
        self.assertFalse(statuses[CompositionStage.REFERENCE_PLAN].complete)
        self.assertEqual(
            self.service.get("session-1").reference_plan.active_revision_id,
            old_revision_id,
        )

    def test_final_edit_cannot_change_the_approved_reference_plan(self):
        self.service.configure(
            "session-1",
            "fighter.arcade_versus",
            "0.1.0",
            bindings(),
        )
        composition = self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)
        composition = self.service.approve("session-1", CompositionStage.REFERENCE_PLAN)
        composition = self.service.generate("session-1", CompositionStage.BEAT_SHEET)
        composition = self.service.approve("session-1", CompositionStage.BEAT_SHEET)
        composition = self.service.generate("session-1", CompositionStage.FINAL_PROMPT)
        changed = composition.final_prompt.active_revision.content.replace(
            "fighter A",
            "another fighter",
            1,
        )

        with self.assertRaisesRegex(ValueError, "locked"):
            self.service.edit("session-1", CompositionStage.FINAL_PROMPT, changed)

    def test_streaming_final_starts_with_the_locked_reference_plan(self):
        self.service.configure(
            "session-1",
            "fighter.arcade_versus",
            "0.1.0",
            bindings(),
        )
        self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)
        self.service.approve("session-1", CompositionStage.REFERENCE_PLAN)
        self.service.generate("session-1", CompositionStage.BEAT_SHEET)
        self.service.approve("session-1", CompositionStage.BEAT_SHEET)

        events = list(
            self.service.stream_generate("session-1", CompositionStage.FINAL_PROMPT)
        )

        deltas = [event.text for event in events if event.kind is StreamEventKind.DELTA]
        self.assertTrue(deltas[0].startswith("subject_definitions:"))
        self.assertIsNotNone(events[-1].composition)

    def test_does_not_persist_a_result_if_the_brief_changed_during_generation(self):
        def change_brief():
            session = self.sessions.get("session-1")
            self.sessions.save(
                session.add_brief_revision(
                    BriefRevision(
                        revision_id="brief-during-call",
                        source_text="The intention changed during generation.",
                        content="A different approved direction.",
                        creative_freedom=25,
                        origin=RevisionOrigin.MANUAL,
                        references=session.active_brief_revision.references,
                        parent_revision_id=session.active_brief_revision_id,
                    )
                ).approve_brief()
            )

        self.service = PromptCompositionService(
            gateway=MutatingGateway(change_brief),
            cookbooks=LocalPromptCookbookCatalog(COOKBOOK_ROOT),
            sessions=self.sessions,
            compositions=self.compositions,
        )
        self.service.configure(
            "session-1",
            "fighter.arcade_versus",
            "0.1.0",
            bindings(),
        )

        with self.assertRaisesRegex(ValueError, "upstream approval changed"):
            self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)

        self.assertEqual(
            self.service.get("session-1").reference_plan.revisions,
            (),
        )

    def test_rejects_frame_anchor_flags_instead_of_silently_ignoring_them(self):
        session = self.sessions.get("session-1")
        changed_reference = session.references[0].set_uses(
            (ReferenceUse.SUBJECT, ReferenceUse.FIRST_FRAME)
        )
        changed = session.update_reference(changed_reference)
        snapshots = tuple(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=reference.active_revision_id,
                uses=reference.uses,
            )
            for reference in changed.references
        )
        changed = changed.add_brief_revision(
            BriefRevision(
                revision_id="brief-with-anchor",
                source_text="Use the first fighter as the first frame.",
                content="A duel anchored by the first fighter image.",
                creative_freedom=30,
                origin=RevisionOrigin.MANUAL,
                references=snapshots,
                parent_revision_id=changed.active_brief_revision_id,
            )
        ).approve_brief()
        self.sessions.save(changed)

        with self.assertRaisesRegex(ValueError, "does not support uses first_frame"):
            self.service.configure(
                "session-1",
                "fighter.arcade_versus",
                "0.1.0",
                bindings(),
            )

    def test_requires_identity_and_environment_uses_for_slots(self):
        session = self.sessions.get("session-1")
        changed_reference = session.references[0].set_uses((ReferenceUse.STYLE,))
        changed = session.update_reference(changed_reference)
        snapshots = tuple(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=reference.active_revision_id,
                uses=reference.uses,
            )
            for reference in changed.references
        )
        changed = changed.add_brief_revision(
            BriefRevision(
                revision_id="brief-style-only",
                source_text="Use the first image as style only.",
                content="A duel with a style reference.",
                creative_freedom=30,
                origin=RevisionOrigin.MANUAL,
                references=snapshots,
                parent_revision_id=changed.active_brief_revision_id,
            )
        ).approve_brief()
        self.sessions.save(changed)

        with self.assertRaisesRegex(ValueError, "fighter_a requires uses subject"):
            self.service.configure(
                "session-1",
                "fighter.arcade_versus",
                "0.1.0",
                bindings(),
            )

    def test_rejects_final_retention_marker_outside_contract(self):
        class InvalidFinalGateway(FakeGateway):
            @staticmethod
            def _content(operation_id):
                content = FakeGateway._content(operation_id)
                if operation_id.startswith("final_prompt"):
                    return content.replace("fully_preserved", "invented_marker", 1)
                return content

        self.service.gateway = InvalidFinalGateway()
        self.service.configure(
            "session-1", "fighter.arcade_versus", "0.1.0", bindings()
        )
        self.service.generate("session-1", CompositionStage.REFERENCE_PLAN)
        self.service.approve("session-1", CompositionStage.REFERENCE_PLAN)
        self.service.generate("session-1", CompositionStage.BEAT_SHEET)
        self.service.approve("session-1", CompositionStage.BEAT_SHEET)

        with self.assertRaisesRegex(ValueError, "must use exactly one marker"):
            self.service.generate("session-1", CompositionStage.FINAL_PROMPT)


class PromptCompositionLinterTest(unittest.TestCase):
    def test_rejects_an_unexpected_section(self):
        invalid = SUBJECT_DEFINITIONS + "\n\n" + FINAL_BODY + "\nextra_notes:\nNone."

        errors = lint_composition_document(CompositionStage.FINAL_PROMPT, invalid)

        self.assertIn("Section inattendue : extra_notes:", errors)

    def test_requires_exact_lowercase_section_headers(self):
        invalid = REFERENCE_PLAN.replace("retention_policy:", "## Retention_Policy:")

        errors = lint_composition_document(CompositionStage.REFERENCE_PLAN, invalid)

        self.assertTrue(any("retention_policy" in error for error in errors))

    def test_rejects_community_or_legacy_image_syntax_in_final_prompt(self):
        invalid = SUBJECT_DEFINITIONS + "\n\n" + FINAL_BODY.replace(
            "inside <Subject 3>",
            "inside <Subject 3> as shown by @image 3",
        )

        errors = lint_composition_document(CompositionStage.FINAL_PROMPT, invalid)

        self.assertTrue(any("jamais @image" in error for error in errors))

    def test_rejects_non_official_or_out_of_range_cut_times(self):
        invalid = SUBJECT_DEFINITIONS + "\n\n" + FINAL_BODY.replace(
            "[Shot 6] At 00:13.000,",
            "[Shot 6] At 00:16.000,",
        )

        errors = lint_composition_document(CompositionStage.FINAL_PROMPT, invalid)

        self.assertTrue(any("atteint ou dépasse" in error for error in errors))

    def test_requires_a_style_lead_before_the_first_final_shot(self):
        invalid = SUBJECT_DEFINITIONS + "\n\n" + FINAL_BODY.replace(
            "Live-action dark fantasy with restrained contrast and precise arcade readability.\n",
            "",
        )

        errors = lint_composition_document(CompositionStage.FINAL_PROMPT, invalid)

        self.assertTrue(any("établir le style" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
