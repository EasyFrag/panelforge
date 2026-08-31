import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (  # noqa: E402
    ChangeViewRunner,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    PromptLabService,
    StreamEventKind,
    StreamPhase,
)
from panelforge.features.lab.web import create_app  # noqa: E402
from panelforge.infrastructure.presets import (  # noqa: E402
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog  # noqa: E402
from panelforge.infrastructure.storage import (  # noqa: E402
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
BRIEF_DOCUMENT = """- INTENTION CENTRALE
Action centrale.
- R\u00c9F\u00c9RENCES CIT\u00c9ES ET R\u00d4LES
Les references utiles.
- SUJETS ET IDENTIT\u00c9S \u00c0 PR\u00c9SERVER
Le sujet.
- D\u00c9COR ET \u00c9TAT INITIAL
Le decor initial.
- CHRONOLOGIE ET ACTIONS DEMAND\u00c9ES
Une action.
- CAM\u00c9RA, LUMI\u00c8RE ET MISE EN SC\u00c8NE
Camera stable.
- CONTRAINTES STRICTES
Preserver le sujet.
- LIBERT\u00c9S AUTORIS\u00c9ES
Variations mineures.
- QUESTIONS OU AMBIGU\u00cfT\u00c9S
N/A"""


class UnusedComfy:
    def upload_image(self, content, *, filename, subfolder=""):
        raise AssertionError("Prompt sessions do not upload to ComfyUI")


class FakeGateway:
    def __init__(self) -> None:
        self.requests = []

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
        return CompletionResult(model_id=request.model_id, content=BRIEF_DOCUMENT)

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=BRIEF_DOCUMENT,
            progress=1.0,
            result=CompletionResult(model_id=request.model_id, content=BRIEF_DOCUMENT),
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
        self.assertEqual(structured.json()["active_brief"]["creative_freedom"], 52)
        self.assertEqual(self.gateway.requests[-1].images, ())

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

    def test_exposes_shared_models_and_only_current_profiles(self):
        page = self.client.get("/")
        core = self.client.get("/static/lab-core.js")
        models = self.client.get("/api/prompt-lab/models")
        spec = self.client.get("/api/prompt-lab/spec")

        self.assertNotIn('data-lab-view="prompt-lab"', page.text)
        self.assertEqual(core.status_code, 200)
        self.assertIn("window.PanelForgeLabCore", core.text)
        self.assertEqual(len(models.json()["models"]), 3)
        self.assertEqual(
            models.json()["models"][-1],
            {
                "id": "local::Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
                "label": "Qwen3.8-27B-UD-Q6_K_XL-Dynamic-V3",
                "source": "local",
            },
        )
        profile_ids = {item["id"] for item in spec.json()["profiles"]}
        self.assertIn("minimax.h3.fl2va.direct", profile_ids)
        self.assertIn("minimax.h3.ref2v.direct", profile_ids)
        self.assertNotIn("minimax.h3.reference", profile_ids)
        mono = next(
            item for item in spec.json()["profiles"]
            if item["id"] == "minimax.h3.fl2va.direct"
            and item["version"] == "0.3.3"
        )
        self.assertEqual(mono["brief_variants"], [
            {
                "id": "creative-direction",
                "version": "0.1.0",
                "display_name": "Direction créative — expérimental",
            },
            {
                "id": "creative-direction",
                "version": "0.2.0",
                "display_name": "Direction créative avec audace — expérimental",
            },
        ])

    def test_configures_creative_brief_before_generation_and_locks_afterward(self):
        created = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "model_id": "vision-small",
                "profile_id": "minimax.h3.fl2va.direct",
                "profile_version": "0.3.3",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["id"]

        configured = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/brief/variant",
            json={
                "brief_variant_id": "creative-direction",
                "brief_variant_version": "0.2.0",
            },
        )
        self.assertEqual(configured.status_code, 200, configured.text)
        self.assertEqual(configured.json()["brief_variant"], {
            "id": "creative-direction",
            "version": "0.2.0",
        })
        structured = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/brief/structure",
            json={
                "source_text": "A priestess advances.",
                "creative_freedom": 100,
                "creative_audacity": 3,
            },
        )
        self.assertEqual(structured.status_code, 200, structured.text)
        self.assertEqual(
            self.gateway.requests[-1].operation_id,
            "brief.structure.creative-direction.0.2.0",
        )
        self.assertEqual(structured.json()["active_brief"]["creative_audacity"], 3)
        self.assertIn("AUDACE CRÉATIVE : 3/3", self.gateway.requests[-1].user_prompt)
        locked = self.client.post(
            f"/api/prompt-lab/sessions/{session_id}/brief/variant",
            json={"brief_variant_id": None, "brief_variant_version": None},
        )
        self.assertEqual(locked.status_code, 422, locked.text)

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
        self.assertTrue(
            all(reference["active_content"] is None for reference in session["references"])
        )

        structured = self.client.post(
            f"/api/prompt-lab/sessions/{session['id']}/brief/structure",
            json={
                "source_text": "The subject crosses the room in one shot.",
                "creative_freedom": 20,
            },
        )
        self.assertEqual(structured.status_code, 200, structured.text)
        self.assertEqual(self.gateway.requests[-1].operation_id, "brief.structure")
        self.assertEqual(len(self.gateway.requests[-1].images), 3)

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
        self.assertEqual(
            self.client.post(
                f"/api/prompt-lab/sessions/{source['id']}/brief/approve"
            ).status_code,
            200,
        )

        response = self.client.post(
            f"/api/prompt-lab/sessions/{source['id']}/fork",
            json={"model_id": "Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        forked = response.json()
        self.assertNotEqual(forked["id"], source["id"])
        self.assertEqual(
            [reference["asset_id"] for reference in forked["references"]],
            [reference["asset_id"] for reference in source["references"]],
        )
        self.assertIsNone(forked["active_brief"])

    def test_rejects_mismatched_roles_before_creating_session(self):
        response = self.client.post(
            "/api/prompt-lab/sessions",
            data={
                "roles": ["first_frame"],
                "model_id": "vision-small",
                "profile_id": "minimax.h3.fl2va.direct",
                "profile_version": "0.1.0",
            },
            files=[
                ("images", ("one.png", PNG, "image/png")),
                ("images", ("two.png", PNG, "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
