import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ImageInput,
    ModelDescriptor,
    NewReference,
    PromptLabService,
    PromptProfile,
    StreamEventKind,
    StreamPhase,
)
from panelforge.application.prompt_lab import _brief_inputs, project_reference_evidence
from panelforge.domain import (
    AnalysisRevision,
    BriefReferenceSnapshot,
    BriefRevision,
    PromptLabSession,
    PromptReference,
    PromptSessionMode,
    ReferenceEvidencePolicy,
    ReferenceReview,
    ReferenceUse,
    RevisionOrigin,
)
from panelforge.infrastructure.llm import OpenAICompatibleGateway
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptSessionStore,
    StorageCorruptionError,
)


PROFILE_ROOT = PROJECT_ROOT / "prompt_profiles"
PNG = b"\x89PNG\r\n\x1a\nreference"
START = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)
BRIEF_DOCUMENT = """- INTENTION CENTRALE
Action initiale.
- RÉFÉRENCES CITÉES ET RÔLES
<Image 1> est la première frame.
- SUJETS ET IDENTITÉS À PRÉSERVER
Préserver le sujet.
- DÉCOR ET ÉTAT INITIAL
Décor initial.
- CHRONOLOGIE ET ACTIONS DEMANDÉES
Action initiale.
- CAMÉRA, LUMIÈRE ET MISE EN SCÈNE
Caméra stable.
- CONTRAINTES STRICTES
Conserver l’identité.
- LIBERTÉS AUTORISÉES
Lumière secondaire.
- QUESTIONS OU AMBIGUÏTÉS
N/A"""


class SequenceClock:
    def __init__(self) -> None:
        self.value = START

    def __call__(self) -> datetime:
        value = self.value
        self.value += timedelta(seconds=1)
        return value


def sample_session() -> PromptLabSession:
    first = AnalysisRevision(
        revision_id="revision-1",
        content="Personnage en veste rouge.",
        origin=RevisionOrigin.MODEL,
    )
    return PromptLabSession(
        session_id="prompt-session-1",
        model_id="Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct",
        profile_id="minimax.h3.reference",
        profile_version="0.1.0",
        references=(
            PromptReference(
                reference_id="reference-1",
                asset_id="asset-1",
                role="character_1",
                label="Image 1",
                revisions=(first,),
                active_revision_id=first.revision_id,
                approved_revision_id=first.revision_id,
            ),
        ),
    )


class PromptLabDomainTest(unittest.TestCase):
    def test_appearance_only_evidence_keeps_only_age_and_stable_appearance(self):
        observation = """- SUJETS VISIBLES
One adult subject in a garden.
- ÂGE APPARENT ET INCERTITUDE
Adult, estimated between 25 and 35.
- APPARENCE ET TRAITS DISTINCTIFS
Oval face, brown eyes, dark hair, and stable body proportions.
- VÊTEMENTS, ACCESSOIRES ET OBJETS
A green top and a black skirt.
- POSE, EXPRESSION ET DIRECTION DU REGARD
Kneeling and looking left.
- COMPOSITION, CADRAGE ET CAMÉRA
High-angle close-up.
- DÉCOR, LUMIÈRE ET STYLE
Outdoor garden in warm light."""

        projected = project_reference_evidence(
            observation,
            ReferenceEvidencePolicy.APPEARANCE_ONLY_V1,
        )

        self.assertIn("estimated between 25 and 35", projected)
        self.assertIn("Oval face, brown eyes", projected)
        for excluded in ("garden", "green top", "Kneeling", "High-angle"):
            self.assertNotIn(excluded, projected)
        with self.assertRaisesRegex(ValueError, "missing required section"):
            project_reference_evidence(
                "- APPARENCE ET TRAITS DISTINCTIFS\nBrown eyes.",
                ReferenceEvidencePolicy.APPEARANCE_ONLY_V1,
            )

    def test_brief_context_and_snapshot_apply_the_reference_evidence_policy(self):
        revision = AnalysisRevision(
            revision_id="revision-appearance",
            content=(
                "- ÂGE APPARENT ET INCERTITUDE\nAdult.\n"
                "- APPARENCE ET TRAITS DISTINCTIFS\nBrown eyes and dark hair.\n"
                "- POSE, EXPRESSION ET DIRECTION DU REGARD\nKneeling.\n"
                "- DÉCOR, LUMIÈRE ET STYLE\nA garden."
            ),
            origin=RevisionOrigin.MODEL,
        )
        reference = PromptReference(
            reference_id="reference-appearance",
            asset_id="asset-appearance",
            role="body_reference",
            label="Body",
            evidence_policy=ReferenceEvidencePolicy.APPEARANCE_ONLY_V1,
            revisions=(revision,),
            active_revision_id=revision.revision_id,
            approved_revision_id=revision.revision_id,
        )
        session = PromptLabSession(
            session_id="prompt-appearance",
            model_id="vision-model",
            profile_id="minimax.h3.reference",
            profile_version="0.3.0",
            references=(reference,),
        )

        context, snapshots = _brief_inputs(session)

        self.assertIn("Brown eyes and dark hair", context)
        self.assertNotIn("Kneeling", context)
        self.assertNotIn("garden", context)
        self.assertEqual(
            snapshots[0].evidence_policy,
            ReferenceEvidencePolicy.APPEARANCE_ONLY_V1,
        )

    def test_revision_invalidates_only_its_reference_approval(self):
        approved = sample_session()
        second = approved.references[0].add_revision(
            AnalysisRevision(
                revision_id="revision-2",
                content="Personnage en manteau rouge.",
                origin=RevisionOrigin.MANUAL,
                parent_revision_id="revision-1",
            )
        )

        self.assertEqual(second.review_status, ReferenceReview.PENDING)
        self.assertEqual(second.active_revision.content, "Personnage en manteau rouge.")
        self.assertEqual(len(second.revisions), 2)

    def test_reference_history_must_be_linear(self):
        with self.assertRaisesRegex(ValueError, "linear"):
            PromptReference(
                reference_id="reference-1",
                asset_id="asset-1",
                role="character_1",
                label="Image 1",
                revisions=(
                    AnalysisRevision(
                        revision_id="revision-1",
                        content="Initial",
                        origin=RevisionOrigin.MODEL,
                    ),
                    AnalysisRevision(
                        revision_id="revision-2",
                        content="Changed",
                        origin=RevisionOrigin.REWRITE,
                        parent_revision_id=None,
                    ),
                ),
                active_revision_id="revision-2",
            )

    def test_brief_snapshots_approved_observations_and_becomes_stale(self):
        session = sample_session()
        brief = BriefRevision(
            revision_id="brief-1",
            source_text="<Image 1> marche.",
            content="INTENTION CENTRALE\nLe personnage marche.",
            creative_freedom=25,
            origin=RevisionOrigin.MODEL,
            references=(
                BriefReferenceSnapshot(
                    reference_id="reference-1",
                    analysis_revision_id="revision-1",
                    uses=(ReferenceUse.SUBJECT,),
                ),
            ),
        )

        approved = session.add_brief_revision(brief).approve_brief()
        changed = approved.update_reference(
            approved.references[0].set_uses(
                (ReferenceUse.SUBJECT, ReferenceUse.FIRST_FRAME)
            )
        )

        self.assertTrue(approved.brief_complete)
        self.assertFalse(changed.brief_complete)
        self.assertTrue(changed.brief_is_stale)
        self.assertIsNone(changed.approved_brief_revision_id)

    def test_direct_brief_snapshots_do_not_require_or_track_analyses(self):
        reference = PromptReference(
            reference_id="reference-direct",
            asset_id="asset-direct",
            role="first_frame",
            label="Opening frame",
            uses=(ReferenceUse.FIRST_FRAME,),
        )
        session = PromptLabSession(
            session_id="prompt-direct",
            model_id="vision-model",
            profile_id="direct.profile",
            profile_version="0.1.0",
            session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
            references=(reference,),
        )
        brief = BriefRevision(
            revision_id="brief-direct",
            source_text="Animate <Image 1>.",
            content=BRIEF_DOCUMENT,
            creative_freedom=25,
            origin=RevisionOrigin.MODEL,
            references=(
                BriefReferenceSnapshot(
                    reference_id=reference.reference_id,
                    analysis_revision_id=None,
                    uses=reference.uses,
                ),
            ),
        )

        approved = session.add_brief_revision(brief).approve_brief()

        self.assertFalse(approved.analysis_complete)
        self.assertTrue(approved.brief_complete)
        analyzed_reference = approved.references[0].add_revision(
            AnalysisRevision(
                revision_id="optional-analysis",
                content="Optional observation.",
                origin=RevisionOrigin.MODEL,
            )
        )
        self.assertTrue(
            approved.update_reference(analyzed_reference).brief_complete
        )

    def test_direct_reference_roles_and_uses_are_domain_invariants(self):
        def reference(role, uses):
            return PromptReference(
                reference_id=f"reference-{role}",
                asset_id=f"asset-{role}",
                role=role,
                label=role,
                uses=uses,
            )

        with self.assertRaisesRegex(ValueError, "unsupported direct reference role"):
            PromptLabSession(
                session_id="prompt-invalid-role",
                model_id="vision-model",
                profile_id="direct.profile",
                profile_version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
                references=(reference("other", (ReferenceUse.SUBJECT,)),),
            )
        with self.assertRaisesRegex(ValueError, "requires use motion"):
            PromptLabSession(
                session_id="prompt-invalid-use",
                model_id="vision-model",
                profile_id="direct.profile",
                profile_version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
                references=(
                    reference("motion_reference", (ReferenceUse.SUBJECT,)),
                ),
            )
        with self.assertRaisesRegex(ValueError, "at most one first_frame"):
            PromptLabSession(
                session_id="prompt-duplicate-first",
                model_id="vision-model",
                profile_id="direct.profile",
                profile_version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
                references=(
                    reference("first_frame", (ReferenceUse.FIRST_FRAME,)),
                    PromptReference(
                        reference_id="reference-first-2",
                        asset_id="asset-first-2",
                        role="first_frame",
                        label="first 2",
                        uses=(ReferenceUse.FIRST_FRAME,),
                    ),
                ),
            )


class LocalPromptSessionStoreTest(unittest.TestCase):
    def test_round_trips_direct_mode_and_null_analysis_snapshots_in_schema_five(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            reference = PromptReference(
                reference_id="reference-direct",
                asset_id="asset-direct",
                role="first_frame",
                label="Opening frame",
                uses=(ReferenceUse.FIRST_FRAME,),
            )
            session = PromptLabSession(
                session_id="prompt-direct-store",
                model_id="vision-model",
                profile_id="direct.profile",
                profile_version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
                references=(reference,),
            ).add_brief_revision(
                BriefRevision(
                    revision_id="brief-direct",
                    source_text="Animate <Image 1>.",
                    content=BRIEF_DOCUMENT,
                    creative_freedom=35,
                    origin=RevisionOrigin.MODEL,
                    references=(
                        BriefReferenceSnapshot(
                            reference_id=reference.reference_id,
                            analysis_revision_id=None,
                            uses=reference.uses,
                        ),
                    ),
                )
            )

            store.create(session)

            self.assertEqual(store.get(session.session_id), session)
            raw = json.loads(
                (
                    Path(directory)
                    / "prompt_sessions"
                    / session.session_id
                    / "session.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(raw["schema_version"], 5)
            self.assertEqual(raw["session_mode"], "direct_multimodal")
            self.assertIsNone(
                raw["brief_revisions"][0]["references"][0][
                    "analysis_revision_id"
                ]
            )

    def test_schema_four_sessions_migrate_to_analyzed_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            session = sample_session()
            store.create(session)
            path = (
                Path(directory)
                / "prompt_sessions"
                / session.session_id
                / "session.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 4
            del raw["session_mode"]
            path.write_text(json.dumps(raw), encoding="utf-8")

            migrated = store.get(session.session_id)

            self.assertEqual(migrated.session_mode, PromptSessionMode.ANALYZED)
            self.assertEqual(migrated, session)

    def test_round_trips_an_explicit_appearance_evidence_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            source = sample_session()
            reference = source.references[0]
            session = PromptLabSession(
                session_id="prompt-appearance-store",
                model_id=source.model_id,
                profile_id=source.profile_id,
                profile_version=source.profile_version,
                references=(
                    PromptReference(
                        reference_id=reference.reference_id,
                        asset_id=reference.asset_id,
                        role=reference.role,
                        label=reference.label,
                        evidence_policy=(
                            ReferenceEvidencePolicy.APPEARANCE_ONLY_V1
                        ),
                        revisions=reference.revisions,
                        active_revision_id=reference.active_revision_id,
                        approved_revision_id=reference.approved_revision_id,
                    ),
                ),
            )

            store.create(session)

            self.assertEqual(store.get(session.session_id), session)

    def test_round_trip_save_list_and_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory, clock=SequenceClock())
            session = sample_session()

            store.create(session)
            changed = session.update_reference(
                session.references[0].add_revision(
                    AnalysisRevision(
                        revision_id="revision-2",
                        content="Correction manuelle.",
                        origin=RevisionOrigin.MANUAL,
                        parent_revision_id="revision-1",
                    )
                )
            )
            store.save(changed)

            self.assertEqual(store.get(session.session_id), changed)
            self.assertEqual(store.list(1), [changed])
            path = (
                Path(directory)
                / "prompt_sessions"
                / session.session_id
                / "session.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["created_at"], "2026-08-08T10:00:00Z")
            self.assertEqual(raw["updated_at"], "2026-08-08T10:00:01Z")
            self.assertEqual(raw["references"][0]["revisions"][1]["origin"], "manual")

    def test_round_trips_structured_brief_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            session = sample_session().add_brief_revision(
                BriefRevision(
                    revision_id="brief-1",
                    source_text="<Image 1> avance.",
                    content="INTENTION CENTRALE\nAvancer.",
                    creative_freedom=50,
                    origin=RevisionOrigin.MODEL,
                    references=(
                        BriefReferenceSnapshot(
                            reference_id="reference-1",
                            analysis_revision_id="revision-1",
                            uses=(ReferenceUse.SUBJECT,),
                        ),
                    ),
                )
            ).approve_brief()

            store.create(session)

            self.assertEqual(store.get(session.session_id), session)
            raw = json.loads(
                (
                    Path(directory)
                    / "prompt_sessions"
                    / session.session_id
                    / "session.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(raw["schema_version"], 5)
            self.assertEqual(raw["session_mode"], "analyzed")
            self.assertEqual(raw["brief_revisions"][0]["creative_freedom"], 50)
            self.assertEqual(raw["references"][0]["evidence_policy"], "full")
            self.assertEqual(
                raw["brief_revisions"][0]["references"][0]["evidence_policy"],
                "full",
            )

            raw["schema_version"] = 3
            del raw["session_mode"]
            del raw["references"][0]["evidence_policy"]
            del raw["brief_revisions"][0]["references"][0]["evidence_policy"]
            (
                Path(directory)
                / "prompt_sessions"
                / session.session_id
                / "session.json"
            ).write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(store.get(session.session_id), session)

    def test_reads_existing_schema_two_sessions_without_a_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            session = sample_session()
            store.create(session)
            path = (
                Path(directory)
                / "prompt_sessions"
                / session.session_id
                / "session.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 2
            del raw["session_mode"]
            del raw["brief_revisions"]
            del raw["active_brief_revision_id"]
            del raw["approved_brief_revision_id"]
            del raw["references"][0]["evidence_policy"]
            path.write_text(json.dumps(raw), encoding="utf-8")

            self.assertEqual(store.get(session.session_id), session)

    def test_rejects_traversal_and_corrupt_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                store.get("../escape")

            session = sample_session()
            store.create(session)
            path = (
                Path(directory)
                / "prompt_sessions"
                / session.session_id
                / "session.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["session_id"] = "another-session"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(StorageCorruptionError, "identity"):
                store.get(session.session_id)


class FakeModels:
    def list(self):
        return SimpleNamespace(
            data=[SimpleNamespace(id="vision-b"), SimpleNamespace(id="vision-a")]
        )


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("stream"):
            return iter(
                (
                    SimpleNamespace(
                        model="vision-a",
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    reasoning_content="━━━━━\n",
                                )
                            )
                        ],
                        usage=None,
                    ),
                    SimpleNamespace(
                        model="vision-a",
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    reasoning_content=(
                                        "llama-swap loading model: vision-a\n"
                                    ),
                                )
                            )
                        ],
                        usage=None,
                    ),
                    SimpleNamespace(
                        model="vision-a",
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    reasoning_content="private reasoning 98%",
                                )
                            )
                        ],
                        usage=None,
                    ),
                    SimpleNamespace(
                        model="vision-a",
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content="Bon",
                                    reasoning_content=None,
                                )
                            )
                        ],
                        usage=None,
                    ),
                    SimpleNamespace(
                        model="vision-a",
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content="jour",
                                    reasoning_content=None,
                                )
                            )
                        ],
                        usage=SimpleNamespace(
                            prompt_tokens=7,
                            completion_tokens=2,
                        ),
                    ),
                )
            )
        return SimpleNamespace(
            model="vision-a",
            choices=[SimpleNamespace(message=SimpleNamespace(content="  résultat  "))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3),
        )


class OpenAICompatibleGatewayTest(unittest.TestCase):
    def test_lists_models_and_preserves_ordered_multimodal_parts(self):
        completions = FakeCompletions()
        client = SimpleNamespace(
            models=FakeModels(),
            chat=SimpleNamespace(completions=completions),
        )
        gateway = OpenAICompatibleGateway(
            "http://bucket:8083/v1",
            client=client,
        )

        models = gateway.list_models()
        result = gateway.complete(
            CompletionRequest(
                model_id="vision-a",
                system_prompt="Décris factuellement.",
                user_prompt="Analyse les références.",
                images=(
                    ImageInput("image/png", b"one", "Image 1"),
                    ImageInput("image/jpeg", b"two", "Image 2"),
                ),
            )
        )

        self.assertEqual(models, (ModelDescriptor("vision-a"), ModelDescriptor("vision-b")))
        self.assertEqual(result.content, "résultat")
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(completions.kwargs["max_tokens"], 32768)
        parts = completions.kwargs["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "image_url", "text", "image_url"])
        self.assertIn("data:image/png;base64,", parts[2]["image_url"]["url"])
        self.assertIn("data:image/jpeg;base64,", parts[4]["image_url"]["url"])

    def test_streams_text_and_only_exposes_verified_loading_state(self):
        completions = FakeCompletions()
        client = SimpleNamespace(
            models=FakeModels(),
            chat=SimpleNamespace(completions=completions),
        )
        gateway = OpenAICompatibleGateway(
            "http://bucket:8083/v1",
            client=client,
        )

        events = list(
            gateway.stream(
                CompletionRequest(
                    model_id="vision-a",
                    system_prompt="Réponds.",
                    user_prompt="Dis bonjour.",
                )
            )
        )

        self.assertEqual(events[0].phase, StreamPhase.PREPARING)
        self.assertEqual(events[1].phase, StreamPhase.LOADING)
        self.assertEqual(events[1].text, "Chargement du modèle vision-a…")
        self.assertNotIn("private reasoning", " ".join(event.text for event in events))
        self.assertEqual(
            [event.text for event in events if event.kind is StreamEventKind.DELTA],
            ["Bon", "jour"],
        )
        completed = events[-1]
        self.assertEqual(completed.kind, StreamEventKind.COMPLETED)
        self.assertEqual(completed.result.content, "Bonjour")
        self.assertEqual(completed.result.prompt_tokens, 7)
        self.assertEqual(completed.result.completion_tokens, 2)

    def test_reports_length_as_a_truncated_terminal_event(self):
        class TruncatedCompletions:
            def create(self, **kwargs):
                return iter(
                    (
                        SimpleNamespace(
                            model="thinking-model",
                            choices=[
                                SimpleNamespace(
                                    finish_reason=None,
                                    delta=SimpleNamespace(
                                        content="Réponse partielle",
                                        reasoning_content=None,
                                    ),
                                )
                            ],
                            usage=None,
                        ),
                        SimpleNamespace(
                            model="thinking-model",
                            choices=[
                                SimpleNamespace(
                                    finish_reason="length",
                                    delta=SimpleNamespace(
                                        content=None,
                                        reasoning_content=None,
                                    ),
                                )
                            ],
                            usage=None,
                        ),
                    )
                )

        gateway = OpenAICompatibleGateway(
            "http://bucket:8083/v1",
            client=SimpleNamespace(
                models=FakeModels(),
                chat=SimpleNamespace(completions=TruncatedCompletions()),
            ),
        )

        events = list(
            gateway.stream(
                CompletionRequest(
                    model_id="thinking-model",
                    system_prompt="Réponds.",
                    user_prompt="Une demande complexe.",
                )
            )
        )

        terminal = events[-1]
        self.assertEqual(terminal.kind, StreamEventKind.TRUNCATED)
        self.assertEqual(terminal.phase, StreamPhase.TRUNCATED)
        self.assertEqual(terminal.result.content, "Réponse partielle")
        self.assertEqual(terminal.result.finish_reason, "length")


class RecordingGateway:
    def __init__(self) -> None:
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("vision-model"),)

    def complete(self, request):
        self.requests.append(request)
        if request.operation_id in {"brief.structure", "brief.revise"}:
            content = BRIEF_DOCUMENT
        else:
            content = "Analyse initiale" if len(self.requests) == 1 else "Analyse corrigée"
        return CompletionResult(model_id=request.model_id, content=content)


class DirectRecordingGateway(RecordingGateway):
    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            result=CompletionResult(
                model_id=request.model_id,
                content=BRIEF_DOCUMENT,
            ),
        )


class SingleProfileCatalog:
    def __init__(self, profile):
        self.profile = profile

    def list(self):
        return (self.profile,)

    def get(self, profile_id, version):
        if (profile_id, version) != (
            self.profile.profile_id,
            self.profile.version,
        ):
            raise KeyError((profile_id, version))
        return self.profile


class PromptLabServiceTest(unittest.TestCase):
    def test_i2v_direct_session_requires_one_first_frame_at_the_service_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PromptLabService(
                gateway=DirectRecordingGateway(),
                profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
                assets=LocalAssetStore(directory),
                sessions=LocalPromptSessionStore(directory),
            )
            first = NewReference(
                "asset-1",
                "first_frame",
                "Start",
                (ReferenceUse.FIRST_FRAME,),
            )

            with self.assertRaisesRegex(ValueError, "exactly one"):
                service.create_session(
                    model_id="vision-model",
                    profile_id="minimax.h3.i2v.direct",
                    profile_version="0.1.0",
                    references=(first, first),
                )
            with self.assertRaisesRegex(ValueError, "role and use first_frame"):
                service.create_session(
                    model_id="vision-model",
                    profile_id="minimax.h3.i2v.direct",
                    profile_version="0.1.0",
                    references=(
                        NewReference(
                            "asset-1",
                            "subject_reference",
                            "Subject",
                            (ReferenceUse.SUBJECT,),
                        ),
                    ),
                )

    def test_direct_brief_and_llm_revisions_receive_native_images_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            ids = iter(("asset-1", "asset-2", "asset-3"))
            assets = LocalAssetStore(directory, id_factory=lambda: next(ids))
            stored_assets = (
                assets.create(PNG + b"one", "image/png"),
                assets.create(PNG + b"two", "image/png"),
                assets.create(PNG + b"three", "image/png"),
            )
            base_profile = LocalPromptProfileCatalog(PROFILE_ROOT).get(
                "minimax.h3.reference",
                "0.3.0",
            )
            direct_profile = replace(
                base_profile,
                profile_id="minimax.h3.direct",
                version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
            )
            gateway = DirectRecordingGateway()
            service = PromptLabService(
                gateway=gateway,
                profiles=SingleProfileCatalog(direct_profile),
                assets=assets,
                sessions=LocalPromptSessionStore(directory),
            )
            session = service.create_session(
                model_id="vision-model",
                profile_id=direct_profile.profile_id,
                profile_version=direct_profile.version,
                references=(
                    NewReference(
                        stored_assets[0].asset_id,
                        "first_frame",
                        "Start",
                        (ReferenceUse.FIRST_FRAME,),
                    ),
                    NewReference(
                        stored_assets[1].asset_id,
                        "motion_reference",
                        "Motion",
                        (ReferenceUse.MOTION,),
                    ),
                    NewReference(
                        stored_assets[2].asset_id,
                        "last_frame",
                        "End",
                        (ReferenceUse.LAST_FRAME,),
                    ),
                ),
            )

            self.assertEqual(
                session.session_mode,
                PromptSessionMode.DIRECT_MULTIMODAL,
            )
            self.assertFalse(session.analysis_complete)
            session = service.structure_brief(
                session.session_id,
                "Move from <Image 1> to <Image 3> using <Image 2>.",
                35,
            )

            structure_request = gateway.requests[-1]
            self.assertEqual(structure_request.operation_id, "brief.structure")
            self.assertEqual(
                tuple(image.content for image in structure_request.images),
                (PNG + b"one", PNG + b"two", PNG + b"three"),
            )
            self.assertEqual(
                tuple(image.label for image in structure_request.images),
                (
                    "<Image 1> · Start",
                    "<Image 2> · Motion",
                    "<Image 3> · End",
                ),
            )
            self.assertLess(
                structure_request.user_prompt.index("<Image 1>"),
                structure_request.user_prompt.index("<Image 2>"),
            )
            self.assertLess(
                structure_request.user_prompt.index("<Image 2>"),
                structure_request.user_prompt.index("<Image 3>"),
            )
            self.assertIn(
                "NATIVE IMAGE ATTACHED TO THIS REQUEST",
                structure_request.user_prompt,
            )
            self.assertTrue(
                all(
                    snapshot.analysis_revision_id is None
                    for snapshot in session.active_brief_revision.references
                )
            )

            session = service.revise_brief(session.session_id, "Keep it factual.")
            revise_request = gateway.requests[-1]
            self.assertEqual(revise_request.operation_id, "brief.revise")
            self.assertEqual(
                tuple(image.content for image in revise_request.images),
                (PNG + b"one", PNG + b"two", PNG + b"three"),
            )

            events = list(
                service.stream_revise_brief(
                    session.session_id,
                    "Keep the same image mapping.",
                )
            )
            stream_request = gateway.requests[-1]
            self.assertEqual(stream_request.operation_id, "brief.revise")
            self.assertEqual(
                tuple(image.label for image in stream_request.images),
                (
                    "<Image 1> · Start",
                    "<Image 2> · Motion",
                    "<Image 3> · End",
                ),
            )
            self.assertTrue(events[-1].session.brief_complete is False)

    def test_direct_sessions_reject_more_than_three_references(self):
        with tempfile.TemporaryDirectory() as directory:
            base_profile = LocalPromptProfileCatalog(PROFILE_ROOT).get(
                "minimax.h3.reference",
                "0.3.0",
            )
            direct_profile = replace(
                base_profile,
                profile_id="minimax.h3.direct",
                version="0.1.0",
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
            )
            service = PromptLabService(
                gateway=DirectRecordingGateway(),
                profiles=SingleProfileCatalog(direct_profile),
                assets=LocalAssetStore(directory),
                sessions=LocalPromptSessionStore(directory),
            )

            with self.assertRaisesRegex(ValueError, "at most 3 references"):
                service.create_session(
                    model_id="vision-model",
                    profile_id=direct_profile.profile_id,
                    profile_version=direct_profile.version,
                    references=tuple(
                        NewReference(
                            f"asset-{index}",
                            "subject_reference",
                            f"Reference {index}",
                            (ReferenceUse.SUBJECT,),
                        )
                        for index in range(4)
                    ),
                )

    def test_each_reference_is_analyzed_revised_and_approved_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            ids = iter(("asset-1", "asset-2"))
            assets = LocalAssetStore(directory, id_factory=lambda: next(ids))
            first = assets.create(PNG + b"one", "image/png")
            second = assets.create(PNG + b"two", "image/png")
            sessions = LocalPromptSessionStore(directory)
            gateway = RecordingGateway()
            service = PromptLabService(
                gateway=gateway,
                profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
                assets=assets,
                sessions=sessions,
            )
            session = service.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.reference",
                profile_version="0.1.0",
                references=(
                    NewReference(first.asset_id, "character_1", "Image 1"),
                    NewReference(second.asset_id, "background", "Image 2"),
                ),
            )

            session = service.analyze_reference(
                session.session_id,
                session.references[0].reference_id,
            )
            self.assertEqual(session.references[0].active_revision.content, "Analyse initiale")
            self.assertIsNone(session.references[1].active_revision)
            self.assertEqual(gateway.requests[0].images[0].content, PNG + b"one")

            session = service.approve_reference(
                session.session_id,
                session.references[0].reference_id,
            )
            self.assertEqual(session.references[0].review_status, ReferenceReview.APPROVED)

            session = service.revise_reference(
                session.session_id,
                session.references[0].reference_id,
                "Remplace veste par manteau.",
            )
            self.assertEqual(session.references[0].review_status, ReferenceReview.PENDING)
            self.assertIn("Analyse initiale", gateway.requests[1].user_prompt)
            self.assertIn("Remplace veste", gateway.requests[1].user_prompt)
            self.assertEqual(session.references[0].active_revision.origin, RevisionOrigin.REWRITE)

            session = service.edit_reference(
                session.session_id,
                session.references[0].reference_id,
                "Correction finale",
            )
            self.assertEqual(session.references[0].active_revision.content, "Correction finale")
            self.assertEqual(session.references[0].active_revision.origin, RevisionOrigin.MANUAL)
            self.assertEqual(len(session.references[0].revisions), 3)

    def test_structures_revises_and_approves_a_brief_from_all_references(self):
        with tempfile.TemporaryDirectory() as directory:
            ids = iter(("asset-1", "asset-2"))
            assets = LocalAssetStore(directory, id_factory=lambda: next(ids))
            first = assets.create(PNG + b"one", "image/png")
            second = assets.create(PNG + b"two", "image/png")
            gateway = RecordingGateway()
            service = PromptLabService(
                gateway=gateway,
                profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
                assets=assets,
                sessions=LocalPromptSessionStore(directory),
            )
            session = service.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.reference",
                profile_version="0.3.0",
                references=(
                    NewReference(
                        first.asset_id,
                        "hero",
                        "Héros",
                        (ReferenceUse.SUBJECT, ReferenceUse.FIRST_FRAME),
                    ),
                    NewReference(
                        second.asset_id,
                        "arena",
                        "Arène",
                        (ReferenceUse.ENVIRONMENT,),
                    ),
                ),
            )
            for reference in session.references:
                session = service.analyze_reference(session.session_id, reference.reference_id)
                session = service.approve_reference(session.session_id, reference.reference_id)

            session = service.structure_brief(
                session.session_id,
                "<Image 1> court dans <Image 2>.",
                70,
            )
            request = gateway.requests[-1]

            self.assertEqual(request.operation_id, "brief.structure")
            self.assertEqual(request.images, ())
            self.assertIn("<Image 1>", request.user_prompt)
            self.assertIn("Usages : subject, first_frame", request.user_prompt)
            self.assertIn("<Image 2>", request.user_prompt)
            self.assertIn("Cinématographique", request.user_prompt)
            self.assertEqual(session.active_brief_revision.creative_freedom, 70)
            self.assertEqual(len(session.active_brief_revision.references), 2)

            session = service.revise_brief(session.session_id, "Rends la caméra fixe.")
            self.assertEqual(gateway.requests[-1].operation_id, "brief.revise")
            self.assertIn("Rends la caméra fixe", gateway.requests[-1].user_prompt)
            self.assertEqual(len(session.brief_revisions), 2)
            self.assertTrue(service.approve_brief(session.session_id).brief_complete)

    def test_brief_structure_normalizes_bare_headings(self):
        bare_brief = "\n".join(
            line.removeprefix("- ") if line.startswith("- ") else line
            for line in BRIEF_DOCUMENT.splitlines()
        )

        class BareBriefGateway(RecordingGateway):
            def __init__(self):
                super().__init__()
                self.brief_content = bare_brief

            def complete(self, request):
                self.requests.append(request)
                content = (
                    self.brief_content
                    if request.operation_id == "brief.structure"
                    else "Observation"
                )
                return CompletionResult(model_id=request.model_id, content=content)

        with tempfile.TemporaryDirectory() as directory:
            assets = LocalAssetStore(directory, id_factory=lambda: "asset-1")
            asset = assets.create(PNG, "image/png")
            gateway = BareBriefGateway()
            service = PromptLabService(
                gateway=gateway,
                profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
                assets=assets,
                sessions=LocalPromptSessionStore(directory),
            )
            session = service.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.reference",
                profile_version="0.3.0",
                references=(NewReference(asset.asset_id, "hero", "Héros"),),
            )
            session = service.analyze_reference(
                session.session_id,
                session.references[0].reference_id,
            )
            session = service.approve_reference(
                session.session_id,
                session.references[0].reference_id,
            )

            session = service.structure_brief(session.session_id, "Avance.", 35)

            self.assertEqual(session.active_brief_revision.content, BRIEF_DOCUMENT)
            gateway.brief_content = bare_brief.rsplit("QUESTIONS OU AMBIGUÏTÉS", 1)[0]
            with self.assertRaisesRegex(ValueError, "QUESTIONS OU AMBIGUÏTÉS"):
                service.structure_brief(session.session_id, "Avance.", 35)

    def test_brief_revision_discards_the_read_only_context_envelope(self):
        original = BRIEF_DOCUMENT
        revised = original.replace("Action initiale.", "Action révisée.")

        class BriefEnvelopeGateway(RecordingGateway):
            def __init__(self):
                super().__init__()
                self.revision_content = (
                    "NIVEAU DE LIBERTÉ : 35/100\n"
                    "CONTEXTE EN LECTURE SEULE\n\n"
                    + revised
                )

            def complete(self, request):
                self.requests.append(request)
                if request.operation_id == "brief.structure":
                    content = original
                elif request.operation_id == "brief.revise":
                    content = self.revision_content
                else:
                    content = "Observation factuelle."
                return CompletionResult(model_id=request.model_id, content=content)

            def stream(self, request):
                self.requests.append(request)
                yield CompletionStreamEvent(
                    kind=StreamEventKind.COMPLETED,
                    phase=StreamPhase.COMPLETED,
                    result=CompletionResult(
                        model_id=request.model_id,
                        content=self.revision_content,
                    ),
                )

        with tempfile.TemporaryDirectory() as directory:
            assets = LocalAssetStore(directory, id_factory=lambda: "asset-1")
            asset = assets.create(PNG, "image/png")
            gateway = BriefEnvelopeGateway()
            service = PromptLabService(
                gateway=gateway,
                profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
                assets=assets,
                sessions=LocalPromptSessionStore(directory),
            )
            session = service.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.reference",
                profile_version="0.3.0",
                references=(
                    NewReference(
                        asset.asset_id,
                        "i2v_first_frame",
                        "Image 1",
                        (ReferenceUse.FIRST_FRAME,),
                    ),
                ),
            )
            reference_id = session.references[0].reference_id
            session = service.analyze_reference(session.session_id, reference_id)
            service.approve_reference(session.session_id, reference_id)
            service.structure_brief(session.session_id, "Anime le sujet.", 35)

            session = service.revise_brief(
                session.session_id,
                "Révise seulement l’action.",
            )

            self.assertEqual(session.active_brief_revision.content, revised)
            self.assertNotIn("CONTEXTE EN LECTURE SEULE", session.active_brief_revision.content)

            gateway.revision_content = "Réponse libre sans les sections requises."
            with self.assertRaisesRegex(ValueError, "missing marker"):
                service.revise_brief(session.session_id, "Nouvelle révision.")
            persisted = service.sessions.get(session.session_id)
            self.assertEqual(len(persisted.brief_revisions), 2)
            self.assertEqual(persisted.active_brief_revision.content, revised)

            streamed_revision = revised.replace("Caméra stable.", "Caméra fixe.")
            gateway.revision_content = "CONTEXTE EN LECTURE SEULE\n\n" + streamed_revision
            events = list(
                service.stream_revise_brief(
                    session.session_id,
                    "Fixe la caméra.",
                )
            )
            streamed_session = events[-1].session
            self.assertIsNotNone(streamed_session)
            self.assertEqual(
                streamed_session.active_brief_revision.content,
                streamed_revision,
            )
            self.assertNotIn(
                "CONTEXTE EN LECTURE SEULE",
                streamed_session.active_brief_revision.content,
            )

            gateway.revision_content = "Réponse streaming sans sections."
            with self.assertRaisesRegex(ValueError, "missing marker"):
                list(
                    service.stream_revise_brief(
                        session.session_id,
                        "Nouvelle révision streaming.",
                    )
                )
            persisted = service.sessions.get(session.session_id)
            self.assertEqual(len(persisted.brief_revisions), 3)
            self.assertEqual(
                persisted.active_brief_revision.content,
                streamed_revision,
            )


class PromptProfileCatalogTest(unittest.TestCase):
    def test_schema_four_loads_direct_mode_without_interpretation_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_directory = Path(directory) / "direct" / "0.1.0"
            profile_directory.mkdir(parents=True)
            prompt_keys = (
                "analysis_system",
                "analysis_user",
                "revision_system",
                "revision_user",
                "brief_system",
                "brief_user",
                "brief_revision_system",
                "brief_revision_user",
            )
            bindings = {}
            for key in prompt_keys:
                filename = f"{key}.txt"
                bindings[key] = filename
                (profile_directory / filename).write_text(
                    f"Prompt for {key}.",
                    encoding="utf-8",
                )
            (profile_directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 4,
                        "profile_id": "minimax.h3.direct",
                        "version": "0.1.0",
                        "display_name": "Direct multimodal",
                        "target_model_family": "MiniMax H3",
                        "source_guides": [],
                        "prompts": bindings,
                        "status": "experimental",
                        "session_mode": "direct_multimodal",
                    }
                ),
                encoding="utf-8",
            )

            profile = LocalPromptProfileCatalog(directory).get(
                "minimax.h3.direct",
                "0.1.0",
            )

            self.assertEqual(
                profile.session_mode,
                PromptSessionMode.DIRECT_MULTIMODAL,
            )
            self.assertIsNone(profile.interpretation_system_prompt)
            self.assertIsNone(profile.interpretation_user_prompt)
            self.assertIn("brief_user", profile.brief_user_prompt)

    def test_loads_first_versioned_minimax_profile(self):
        catalog = LocalPromptProfileCatalog(PROFILE_ROOT)
        profile = catalog.get("minimax.h3.reference", "0.1.0")
        enriched = catalog.get("minimax.h3.reference", "0.2.0")
        brief = catalog.get("minimax.h3.reference", "0.3.0")

        self.assertEqual(profile.target_model_family, "MiniMax H3")
        self.assertIn("{role}", profile.analysis_user_prompt)
        self.assertIn("{current_analysis}", profile.revision_user_prompt)
        self.assertIsNone(profile.interpretation_system_prompt)
        self.assertIn("ACTIONS ET INTERACTIONS", enriched.analysis_system_prompt)
        self.assertIn("{uses}", enriched.interpretation_user_prompt)
        self.assertIn("{reference_context}", brief.brief_user_prompt)
        self.assertIn("<Image 1>", brief.brief_system_prompt)
        self.assertEqual(profile.session_mode, PromptSessionMode.ANALYZED)
        self.assertEqual(enriched.session_mode, PromptSessionMode.ANALYZED)
        self.assertEqual(brief.session_mode, PromptSessionMode.ANALYZED)
        self.assertEqual(
            tuple(
                item
                for item in catalog.list()
                if item.profile_id == "minimax.h3.reference"
            ),
            (profile, enriched, brief),
        )


if __name__ == "__main__":
    unittest.main()
