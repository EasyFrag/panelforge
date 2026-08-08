import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    ChangeViewRunner,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    PromptLabService,
    StreamEventKind,
    StreamPhase,
)
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptSessionStore,
    LocalRunStore,
)


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
PROFILE_ROOT = PROJECT_ROOT / "prompt_profiles"
PNG = b"\x89PNG\r\n\x1a\nimage-content"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str = "panelforge/uploaded.png"


class UnusedComfy:
    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded()


class FakeGateway:
    def __init__(self) -> None:
        self.requests = []
        self.truncate_next = False

    def list_models(self):
        return (
            ModelDescriptor("Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct"),
            ModelDescriptor("vision-small"),
        )

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=f"Analyse {len(self.requests)}",
        )

    def stream(self, request):
        self.requests.append(request)
        content = f"Analyse {len(self.requests)}"
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.GENERATING,
            text="Génération…",
        )
        for part in ("Analyse ", str(len(self.requests))):
            yield CompletionStreamEvent(
                kind=StreamEventKind.DELTA,
                phase=StreamPhase.GENERATING,
                text=part,
            )
        if self.truncate_next:
            self.truncate_next = False
            yield CompletionStreamEvent(
                kind=StreamEventKind.TRUNCATED,
                phase=StreamPhase.TRUNCATED,
                text=content,
                result=CompletionResult(
                    model_id=request.model_id,
                    content=content,
                    finish_reason="length",
                ),
            )
            return
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=content,
            progress=1.0,
            result=CompletionResult(
                model_id=request.model_id,
                content=content,
            ),
        )


class PromptLabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.temporary_directory.name)
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY)),
            comfy=UnusedComfy(),
            assets=assets,
            runs=LocalRunStore(self.temporary_directory.name),
        )
        self.gateway = FakeGateway()
        prompt_lab = PromptLabService(
            gateway=self.gateway,
            profiles=LocalPromptProfileCatalog(PROFILE_ROOT),
            assets=assets,
            sessions=LocalPromptSessionStore(self.temporary_directory.name),
        )
        self.client = TestClient(create_app(runner, prompt_lab=prompt_lab))

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def create_session(self, profile_version="0.1.0"):
        response = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["character_1", "background"],
                "model_id": "Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct",
                "profile_id": "minimax.h3.reference",
                "profile_version": profile_version,
            },
            files=[
                ("images", ("hero.png", PNG + b"hero", "image/png")),
                ("images", ("room.png", PNG + b"room", "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_exposes_dynamic_models_and_versioned_profiles(self):
        page = self.client.get("/")
        script = self.client.get("/static/prompt-lab.js")
        models = self.client.get("/api/prompt-lab/models")
        spec = self.client.get("/api/prompt-lab/spec")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Prompt Lab", page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/prompt-lab/sessions", script.text)
        self.assertIn("analyze-all-references", page.text)
        self.assertIn("brief-reference-grid", page.text)
        self.assertEqual(models.status_code, 200)
        self.assertEqual(len(models.json()["models"]), 2)
        self.assertEqual(spec.status_code, 200)
        profile = spec.json()["profiles"][0]
        self.assertEqual(profile["id"], "minimax.h3.reference")
        self.assertEqual(profile["version"], "0.1.0")
        self.assertTrue(spec.json()["profiles"][-1]["supports_brief"])

    def test_runs_supervised_reference_actions_independently(self):
        session = self.create_session()
        session_id = session["id"]
        first, second = session["references"]

        analyzed = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{first['id']}/analyze"
        )
        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        session = analyzed.json()
        self.assertEqual(session["references"][0]["active_content"], "Analyse 1")
        self.assertIsNone(session["references"][1]["active_content"])

        approved = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{first['id']}/approve"
        )
        self.assertEqual(approved.json()["references"][0]["review_status"], "approved")

        revised = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{first['id']}/revise",
            json={"instruction": "Précise la couleur du manteau."},
        )
        self.assertEqual(revised.status_code, 200, revised.text)
        self.assertEqual(revised.json()["references"][0]["review_status"], "pending")
        self.assertEqual(revised.json()["references"][0]["active_content"], "Analyse 2")

        edited = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{first['id']}/edit",
            json={"content": "Version corrigée manuellement."},
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(len(edited.json()["references"][0]["revisions"]), 3)

        fetched = self.client.get(f"/api/prompt-lab/sessions/{session_id}")
        listed = self.client.get("/api/prompt-lab/sessions?limit=1")
        self.assertEqual(fetched.json(), edited.json())
        self.assertEqual(listed.json()["sessions"][0], edited.json())
        self.assertEqual(second["review_status"], "pending")

    def test_streams_and_persists_reference_analysis(self):
        session = self.create_session()
        session_id = session["id"]
        reference_id = session["references"][0]["id"]

        response = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze/stream"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertIn('event: delta\ndata: {"kind": "delta"', response.text)
        self.assertIn('"text": "Analyse "', response.text)
        self.assertIn('event: completed', response.text)
        persisted = self.client.get(
            f"/api/prompt-lab/sessions/{session_id}"
        ).json()
        self.assertEqual(
            persisted["references"][0]["active_content"],
            "Analyse 1",
        )

    def test_streams_truncated_text_without_persisting_it(self):
        session = self.create_session()
        session_id = session["id"]
        reference_id = session["references"][0]["id"]
        self.gateway.truncate_next = True

        response = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze/stream"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("event: truncated", response.text)
        self.assertIn('"finish_reason": "length"', response.text)
        self.assertIn('"max_tokens": 32768', response.text)
        persisted = self.client.get(
            f"/api/prompt-lab/sessions/{session_id}"
        ).json()
        self.assertIsNone(persisted["references"][0]["active_content"])

    def test_rejects_mismatched_roles_before_creating_session(self):
        response = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["character_1"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.reference",
                "profile_version": "0.1.0",
            },
            files=[
                ("images", ("one.png", PNG, "image/png")),
                ("images", ("two.png", PNG, "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 422)

    def test_structures_streams_and_invalidates_an_approved_brief(self):
        session = self.create_session("0.3.0")
        session_id = session["id"]
        for reference in session["references"]:
            analyzed = self.client.post(
                f"/api/prompt-lab/sessions/{session_id}/references/{reference['id']}/analyze"
            )
            self.assertEqual(analyzed.status_code, 200, analyzed.text)
            approved = self.client.post(
                f"/api/prompt-lab/sessions/{session_id}/references/{reference['id']}/approve"
            )
            self.assertEqual(approved.status_code, 200, approved.text)

        streamed = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/brief/structure/stream",
            json={
                "source_text": "<Image 1> entre dans <Image 2>.",
                "creative_freedom": 35,
            },
        )

        self.assertEqual(streamed.status_code, 200, streamed.text)
        self.assertIn("event: completed", streamed.text)
        brief = self.client.get(
            f"/api/prompt-lab/sessions/{session_id}"
        ).json()
        self.assertEqual(brief["active_brief"]["source_text"], "<Image 1> entre dans <Image 2>.")
        self.assertEqual(brief["active_brief"]["creative_freedom"], 35)
        self.assertFalse(brief["brief_complete"])

        approved_brief = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/brief/approve"
        )
        self.assertTrue(approved_brief.json()["brief_complete"])
        first = brief["references"][0]
        changed = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/references/{first['id']}/uses",
            json={"uses": ["subject", "first_frame"]},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertFalse(changed.json()["brief_complete"])
        self.assertTrue(changed.json()["brief_is_stale"])


if __name__ == "__main__":
    unittest.main()
