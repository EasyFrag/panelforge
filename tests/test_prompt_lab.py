import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    ImageInput,
    ModelDescriptor,
    NewReference,
    PromptLabService,
)
from panelforge.domain import (
    AnalysisRevision,
    PromptLabSession,
    PromptReference,
    ReferenceReview,
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


class LocalPromptSessionStoreTest(unittest.TestCase):
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
        parts = completions.kwargs["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "image_url", "text", "image_url"])
        self.assertIn("data:image/png;base64,", parts[2]["image_url"]["url"])
        self.assertIn("data:image/jpeg;base64,", parts[4]["image_url"]["url"])


class RecordingGateway:
    def __init__(self) -> None:
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("vision-model"),)

    def complete(self, request):
        self.requests.append(request)
        content = "Analyse initiale" if len(self.requests) == 1 else "Analyse corrigée"
        return CompletionResult(model_id=request.model_id, content=content)


class PromptLabServiceTest(unittest.TestCase):
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


class PromptProfileCatalogTest(unittest.TestCase):
    def test_loads_first_versioned_minimax_profile(self):
        catalog = LocalPromptProfileCatalog(PROFILE_ROOT)
        profile = catalog.get("minimax.h3.reference", "0.1.0")

        self.assertEqual(profile.target_model_family, "MiniMax H3")
        self.assertIn("{role}", profile.analysis_user_prompt)
        self.assertIn("{current_analysis}", profile.revision_user_prompt)
        self.assertEqual(catalog.list(), (profile,))


if __name__ == "__main__":
    unittest.main()
