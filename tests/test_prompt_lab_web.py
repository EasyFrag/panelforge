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
BRIEF_DOCUMENT = """INTENTION CENTRALE
Action centrale.
RÉFÉRENCES CITÉES ET RÔLES
Deux références.
SUJETS ET IDENTITÉS À PRÉSERVER
Le sujet.
DÉCOR ET ÉTAT INITIAL
Le décor initial.
CHRONOLOGIE ET ACTIONS DEMANDÉES
Une action.
CAMÉRA, LUMIÈRE ET MISE EN SCÈNE
Caméra stable.
CONTRAINTES STRICTES
Préserver le sujet.
LIBERTÉS AUTORISÉES
Variations mineures.
QUESTIONS OU AMBIGUÏTÉS
N/A"""


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
            ModelDescriptor(
                "local::Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
                source="local",
                display_name="Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
            ),
        )

    def complete(self, request):
        self.requests.append(request)
        content = (
            BRIEF_DOCUMENT
            if request.operation_id == "brief.structure"
            else f"Analyse {len(self.requests)}"
        )
        return CompletionResult(
            model_id=request.model_id,
            content=content,
        )

    def stream(self, request):
        self.requests.append(request)
        is_brief = request.operation_id == "brief.structure"
        content = BRIEF_DOCUMENT if is_brief else f"Analyse {len(self.requests)}"
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.GENERATING,
            text="Génération…",
        )
        for part in ((content,) if is_brief else ("Analyse ", str(len(self.requests)))):
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

    def test_h3_base_session_accepts_zero_or_optional_boundary_frames(self):
        text_only = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "model_id": "vision-small",
                "profile_id": "minimax.h3.fl2va.direct",
                "profile_version": "0.1.0",
            },
        )
        self.assertEqual(text_only.status_code, 201, text_only.text)
        self.assertEqual(text_only.json()["session_mode"], "h3_base")
        self.assertEqual(text_only.json()["references"], [])
        structured = self.client.post(
            f"/api/prompt-lab/sessions/{text_only.json()['id']}/brief/structure",
            json={
                "source_text": "A runner crosses a quiet room.",
                "creative_axes": {
                    "scene_life": 3,
                    "camera": 0,
                    "extra_motion": 2,
                },
            },
        )
        self.assertEqual(structured.status_code, 200, structured.text)
        self.assertIsNotNone(structured.json()["active_brief"])
        self.assertEqual(structured.json()["active_brief"]["creative_freedom"], 52)
        self.assertEqual(
            structured.json()["active_brief"]["creative_axes"],
            {"scene_life": 3, "camera": 0, "extra_motion": 2},
        )
        self.assertEqual(structured.json()["brief_revisions"][-1]["references"], [])
        self.assertEqual(self.gateway.requests[-1].images, ())
        self.assertIn("Vie de la scène 3/3", self.gateway.requests[-1].user_prompt)
        self.assertIn("Caméra 0/3", self.gateway.requests[-1].user_prompt)

        both = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["first_frame", "last_frame"],
                "usages": ["first_frame", "last_frame"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.fl2va.direct",
                "profile_version": "0.1.0",
            },
            files=[
                ("images", ("first.png", PNG + b"first", "image/png")),
                ("images", ("last.png", PNG + b"last", "image/png")),
            ],
        )
        self.assertEqual(both.status_code, 201, both.text)
        self.assertEqual(
            [reference["role"] for reference in both.json()["references"]],
            ["first_frame", "last_frame"],
        )

    def test_exposes_dynamic_models_and_versioned_profiles(self):
        page = self.client.get("/")
        script = self.client.get("/static/prompt-lab.js")
        ref2v_script = self.client.get("/static/ref2v-prompt.js")
        models = self.client.get("/api/prompt-lab/models")
        spec = self.client.get("/api/prompt-lab/spec")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Prompt Lab", page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/prompt-lab/sessions", script.text)
        self.assertIn("PanelForgeModelPicker.populate", script.text)
        self.assertIn('body.append("evidence_policies"', ref2v_script.text)
        self.assertIn("selectCookbookForSessionEvidence", ref2v_script.text)
        self.assertIn("analyze-all-references", page.text)
        self.assertIn("brief-reference-grid", page.text)
        self.assertEqual(models.status_code, 200)
        self.assertEqual(len(models.json()["models"]), 3)
        self.assertEqual(
            models.json()["models"][-1],
            {
                "id": "local::Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
                "label": "Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
                "source": "local",
            },
        )
        self.assertEqual(spec.status_code, 200)
        profiles = spec.json()["profiles"]
        profile = next(
            item
            for item in profiles
            if item["id"] == "minimax.h3.reference"
            and item["version"] == "0.1.0"
        )
        self.assertEqual(profile["id"], "minimax.h3.reference")
        self.assertEqual(profile["version"], "0.1.0")
        self.assertEqual(profile["session_mode"], "analyzed")
        direct_profile = next(
            item
            for item in profiles
            if item["id"] == "minimax.h3.ref2v.direct"
            and item["version"] == "0.1.0"
        )
        self.assertEqual(direct_profile["session_mode"], "direct_multimodal")
        self.assertTrue(direct_profile["supports_brief"])

    def test_direct_multimodal_structures_brief_without_observations(self):
        created = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": [
                    "first_frame",
                    "subject_reference",
                    "environment_reference",
                ],
                "usages": ["first_frame", "subject", "environment"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.ref2v.direct",
                "profile_version": "0.1.0",
            },
            files=[
                ("images", ("start.png", PNG + b"start", "image/png")),
                ("images", ("subject.png", PNG + b"subject", "image/png")),
                ("images", ("room.png", PNG + b"room", "image/png")),
            ],
        )

        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["session_mode"], "direct_multimodal")
        self.assertFalse(session["analysis_complete"])
        self.assertTrue(
            all(
                reference["active_content"] is None
                for reference in session["references"]
            )
        )

        structured = self.client.post(
            f"/api/prompt-lab/sessions/{session['id']}/brief/structure",
            json={
                "source_text": "Le sujet traverse la pièce en un plan continu.",
                "creative_freedom": 20,
            },
        )

        self.assertEqual(structured.status_code, 200, structured.text)
        brief = structured.json()
        self.assertIsNotNone(brief["active_brief"])
        self.assertEqual(
            [
                reference["analysis_revision_id"]
                for reference in brief["brief_revisions"][-1]["references"]
            ],
            [None, None, None],
        )
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, "brief.structure")
        self.assertEqual(
            [image.label for image in request.images],
            [
                "<Image 1> · start.png",
                "<Image 2> · subject.png",
                "<Image 3> · room.png",
            ],
        )

    def test_session_creation_accepts_one_explicit_evidence_policy_per_image(self):
        response = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["dressed_start", "body_reference"],
                "usages": ["first_frame,subject", "subject"],
                "evidence_policies": ["full", "appearance_only_v1"],
                "model_id": "Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct",
                "profile_id": "minimax.h3.reference",
                "profile_version": "0.3.0",
            },
            files=[
                ("images", ("start.png", PNG + b"start", "image/png")),
                ("images", ("body.png", PNG + b"body", "image/png")),
            ],
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            [item["evidence_policy"] for item in response.json()["references"]],
            ["full", "appearance_only_v1"],
        )

        invalid = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["one", "two"],
                "evidence_policies": ["full"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.reference",
                "profile_version": "0.3.0",
            },
            files=[
                ("images", ("one.png", PNG + b"one", "image/png")),
                ("images", ("two.png", PNG + b"two", "image/png")),
            ],
        )
        self.assertEqual(invalid.status_code, 422)

    def test_forks_a_direct_session_without_copying_generated_state(self):
        created = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["first_frame"],
                "usages": ["first_frame"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.i2v.direct",
                "profile_version": "0.1.0",
            },
            files=[("images", ("opening-frame.png", PNG + b"opening", "image/png"))],
        )
        self.assertEqual(created.status_code, 201, created.text)
        source = created.json()
        structured = self.client.post(
            f"/api/prompt-lab/sessions/{source['id']}/brief/structure",
            json={"source_text": "Walk forward.", "creative_freedom": 20},
        )
        self.assertEqual(structured.status_code, 200, structured.text)
        approved = self.client.post(
            f"/api/prompt-lab/sessions/{source['id']}/brief/approve"
        )
        self.assertEqual(approved.status_code, 200, approved.text)

        response = self.client.post(
            f"/api/prompt-lab/sessions/{source['id']}/fork",
            json={"model_id": "Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        forked = response.json()
        self.assertNotEqual(forked["id"], source["id"])
        self.assertEqual(
            forked["model_id"],
            "Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct",
        )
        self.assertEqual(forked["profile"], source["profile"])
        self.assertEqual(
            [reference["asset_id"] for reference in forked["references"]],
            [reference["asset_id"] for reference in source["references"]],
        )
        self.assertNotEqual(
            [reference["id"] for reference in forked["references"]],
            [reference["id"] for reference in source["references"]],
        )
        self.assertIsNone(forked["active_brief"])
        self.assertFalse(forked["brief_complete"])
        self.assertTrue(
            self.client.get(
                f"/api/prompt-lab/sessions/{source['id']}"
            ).json()["brief_complete"]
        )

        migrated_response = self.client.post(
            f"/api/prompt-lab/sessions/{source['id']}/fork",
            json={
                "profile_id": "minimax.h3.fl2va.direct",
                "profile_version": "0.1.0",
            },
        )
        self.assertEqual(migrated_response.status_code, 201, migrated_response.text)
        migrated = migrated_response.json()
        self.assertEqual(migrated["profile"]["id"], "minimax.h3.fl2va.direct")
        self.assertEqual(migrated["session_mode"], "h3_base")
        self.assertEqual(
            [reference["asset_id"] for reference in migrated["references"]],
            [reference["asset_id"] for reference in source["references"]],
        )

        missing = self.client.post(
            "/api/prompt-lab/sessions/prompt-missing/fork",
            json={},
        )
        self.assertEqual(missing.status_code, 404)

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
