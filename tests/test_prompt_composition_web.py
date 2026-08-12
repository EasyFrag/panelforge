import json
from pathlib import Path
import json
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import ChangeViewRunner, PromptCompositionService
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
    LocalRunStore,
)
from tests.test_prompt_composition import FakeGateway, approved_session
from tests.test_i2v_prompt import I2VGateway, approved_i2v_session
from tests.test_ref2v_prompt import (
    SupervisedGateway,
    approved_session as approved_ref2v_session,
)


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)


class UnusedComfy:
    pass


def sse_payloads(response):
    values = []
    for block in response.text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].lstrip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if data:
            values.append(json.loads(data))
    return values


class PromptCompositionWebTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.directory.name)
        sessions = LocalPromptSessionStore(self.directory.name)
        sessions.create(approved_session())
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY)),
            comfy=UnusedComfy(),
            assets=assets,
            runs=LocalRunStore(self.directory.name),
        )
        service = PromptCompositionService(
            gateway=FakeGateway(),
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=sessions,
            compositions=LocalPromptCompositionStore(self.directory.name),
        )
        self.client = TestClient(
            create_app(runner, prompt_composition=service)
        )

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def configure(self):
        return self.client.post(
            "/api/prompt-lab/sessions/session-1/composition",
            json={
                "cookbook_id": "fighter.arcade_versus",
                "cookbook_version": "0.1.0",
                "bindings": {
                    "fighter_a": ["reference-1"],
                    "fighter_b": ["reference-2"],
                    "arena": ["reference-3"],
                },
            },
        )

    def stream_stage(self, stage):
        return self.client.post(
            f"/api/prompt-lab/sessions/session-1/{stage}/generate/stream"
        )

    def approve_stage(self, stage):
        return self.client.post(
            f"/api/prompt-lab/sessions/session-1/{stage}/approve"
        )

    def test_exposes_cookbook_and_runs_all_three_supervised_routes(self):
        catalog = self.client.get("/api/prompt-lab/cookbooks")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["cookbooks"][0]["id"], "fighter.arcade_versus")
        self.assertEqual(
            catalog.json()["cookbooks"][0]["slots"][0]["required_uses"],
            ["subject"],
        )
        configured = self.configure()
        self.assertEqual(configured.status_code, 200)
        self.assertEqual(
            configured.json()["composition"]["picture_mapping"],
            [
                {"reference_id": "reference-1", "picture_number": 1},
                {"reference_id": "reference-2", "picture_number": 2},
                {"reference_id": "reference-3", "picture_number": 3},
            ],
        )

        for stage in ("reference-plan", "beat-sheet", "final-prompt"):
            generated = self.stream_stage(stage)
            self.assertEqual(generated.status_code, 200, generated.text)
            payloads = sse_payloads(generated)
            self.assertEqual(payloads[-1]["kind"], "completed")
            self.assertIn("composition", payloads[-1])
            approved = self.approve_stage(stage)
            self.assertEqual(approved.status_code, 200, approved.text)

        loaded = self.client.get(
            "/api/prompt-lab/sessions/session-1/composition"
        ).json()["composition"]
        self.assertTrue(loaded["documents"]["reference_plan"]["complete"])
        self.assertTrue(loaded["documents"]["beat_sheet"]["complete"])
        self.assertTrue(loaded["documents"]["final_prompt"]["complete"])
        self.assertIn(
            "subject_definitions:",
            loaded["documents"]["final_prompt"]["active_content"],
        )

    def test_serves_the_modular_prompt_composition_frontend(self):
        page = self.client.get("/")
        script = self.client.get("/static/prompt-composition.js")
        i2v_script = self.client.get("/static/i2v-prompt.js")
        ref2v_script = self.client.get("/static/ref2v-prompt.js")
        direct_script = self.client.get("/static/ref2v-direct.js")
        catalog = self.client.get("/api/prompt-lab/cookbooks").json()["cookbooks"]

        self.assertEqual(page.status_code, 200)
        self.assertIn("prompt-composition.js", page.text)
        self.assertIn('data-lab-view="i2v"', page.text)
        self.assertIn('id="i2v-observation-step"', page.text)
        self.assertIn('id="i2v-brief-step"', page.text)
        self.assertIn('id="i2v-prompt-step"', page.text)
        self.assertIn('id="i2v-cookbook"', page.text)
        self.assertIn('i2v-prompt.js?v=20260811.1', page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("required_uses", script.text)
        self.assertEqual(i2v_script.status_code, 200)
        self.assertIn('minimax.h3.i2v.simple', i2v_script.text)
        self.assertIn('preferredCookbookVersion = "0.3.0"', i2v_script.text)
        self.assertIn('fallbackCookbookVersion = "0.2.0"', i2v_script.text)
        self.assertIn('core.request("/api/prompt-lab/cookbooks")', i2v_script.text)
        self.assertIn('Canonique expérimental', i2v_script.text)
        self.assertIn('Témoin de comparaison', i2v_script.text)
        self.assertIn("PanelForgeModelPicker.populate", i2v_script.text)
        self.assertEqual(ref2v_script.status_code, 200)
        self.assertIn('id="ref2v-cookbook"', page.text)
        self.assertIn('ref2v-prompt.js?v=20260811.2', page.text)
        self.assertIn('preferredCookbookVersion = "0.11.0"', ref2v_script.text)
        self.assertIn('fallbackCookbookVersion = "0.10.0"', ref2v_script.text)
        self.assertIn(
            'new Set(["0.8.0", "0.9.0", "0.10.0", "0.11.0"])',
            ref2v_script.text,
        )
        self.assertIn('const visible = Boolean(', ref2v_script.text)
        self.assertIn('supervised || (', ref2v_script.text)
        self.assertIn('core.request("/api/prompt-lab/cookbooks")', ref2v_script.text)
        self.assertIn('Continuité physique expérimentale', ref2v_script.text)
        self.assertIn('evidencePolicyForSlot', ref2v_script.text)
        self.assertIn('selectCookbookForSessionEvidence', ref2v_script.text)
        ref2v_v11 = next(
            item
            for item in catalog
            if item["id"] == "undressing.single_shot"
            and item["version"] == "0.11.0"
        )
        self.assertEqual(
            ref2v_v11["invalid_camera_target_policy"],
            "drop_with_warning",
        )
        self.assertIn("PanelForgeModelPicker.populate", ref2v_script.text)
        self.assertIn('id="ref2v-action-plan"', page.text)
        self.assertIn('id="ref2v-action-plan" class="cookbook-step" open hidden', page.text)
        self.assertIn('id="ref2v-generate-plan"', page.text)
        self.assertIn('id="ref2v-arbitrations"', page.text)
        self.assertIn('id="ref2v-apply-arbitrations"', page.text)
        self.assertIn("beat-sheet/reconcile/stream", ref2v_script.text)
        self.assertEqual(direct_script.status_code, 200)
        self.assertIn('ref2v-direct.js?v=20260812.1', page.text)
        self.assertIn('id="ref2vd-cookbook"', page.text)
        self.assertIn('preferredCookbookVersion = "0.3.1"', direct_script.text)
        self.assertNotIn('cookbookVersion = "0.3.0"', direct_script.text)
        self.assertIn("cookbook_version: state.cookbook.version", direct_script.text)
        self.assertIn('id="ref2vd-arbitrations"', page.text)
        self.assertIn('id="ref2vd-accept-all-arbitrations"', page.text)
        self.assertIn('id="ref2vd-apply-arbitrations"', page.text)
        self.assertIn("beat-sheet/reconcile/stream", direct_script.text)
        direct_v2 = next(
            item for item in catalog
            if item["id"] == "minimax.h3.ref2v.direct"
            and item["version"] == "0.2.0"
        )
        direct_v3 = next(
            item for item in catalog
            if item["id"] == "minimax.h3.ref2v.direct"
            and item["version"] == "0.3.0"
        )
        direct_compact = next(
            item for item in catalog
            if item["id"] == "minimax.h3.ref2v.direct"
            and item["version"] == "0.3.1"
        )
        self.assertFalse(direct_v2["supports_plan_reconciliation"])
        self.assertTrue(direct_v3["supports_plan_reconciliation"])
        self.assertTrue(direct_compact["supports_plan_reconciliation"])
        self.assertEqual(direct_compact["writer_projection"], "compact_v1")

    def test_rejects_duplicate_fighter_assignments(self):
        response = self.client.post(
            "/api/prompt-lab/sessions/session-1/composition",
            json={
                "cookbook_id": "fighter.arcade_versus",
                "cookbook_version": "0.1.0",
                "bindings": {
                    "fighter_a": ["reference-1"],
                    "fighter_b": ["reference-1"],
                    "arena": ["reference-3"],
                },
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("distinct references", response.json()["detail"])

    def test_unknown_stage_is_not_silently_accepted(self):
        response = self.client.post(
            "/api/prompt-lab/sessions/session-1/transition/generate/stream"
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_bindings_and_blocked_stream_are_client_errors(self):
        invalid_bindings = self.client.post(
            "/api/prompt-lab/sessions/session-1/composition",
            json={
                "cookbook_id": "fighter.arcade_versus",
                "cookbook_version": "0.1.0",
                "bindings": {"fighter_a": []},
            },
        )
        self.assertEqual(invalid_bindings.status_code, 422)

        self.assertEqual(self.configure().status_code, 200)
        blocked = self.stream_stage("beat-sheet")
        self.assertEqual(blocked.status_code, 422)
        self.assertIn("approve a current reference_plan", blocked.json()["detail"])


class I2VCompositionWebTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.directory.name)
        sessions = LocalPromptSessionStore(self.directory.name)
        sessions.create(approved_i2v_session())
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY)),
            comfy=UnusedComfy(),
            assets=assets,
            runs=LocalRunStore(self.directory.name),
        )
        service = PromptCompositionService(
            gateway=I2VGateway(),
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=sessions,
            compositions=LocalPromptCompositionStore(self.directory.name),
        )
        self.client = TestClient(create_app(runner, prompt_composition=service))

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def test_runs_the_direct_i2v_prompt_route_without_hidden_stages(self):
        catalog = self.client.get("/api/prompt-lab/cookbooks").json()["cookbooks"]
        i2v = next(item for item in catalog if item["id"] == "minimax.h3.i2v.simple")
        self.assertEqual(i2v["stages"], ["final_prompt"])
        self.assertEqual(i2v["output_contract"], "minimax.h3.i2va")

        configured = self.client.post(
            "/api/prompt-lab/sessions/session-i2v-1/composition",
            json={
                "cookbook_id": "minimax.h3.i2v.simple",
                "cookbook_version": "0.1.0",
                "bindings": {"first_frame": ["reference-i2v-1"]},
            },
        )
        self.assertEqual(configured.status_code, 200, configured.text)

        generated = self.client.post(
            "/api/prompt-lab/sessions/session-i2v-1/final-prompt/generate/stream"
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        payloads = sse_payloads(generated)
        self.assertEqual(payloads[-1]["kind"], "completed")
        approved = self.client.post(
            "/api/prompt-lab/sessions/session-i2v-1/final-prompt/approve"
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        final_document = approved.json()["composition"]["documents"]["final_prompt"]
        self.assertTrue(final_document["complete"])
        self.assertIn("integrated_multimodal_description:", final_document["active_content"])

        inactive = self.client.post(
            "/api/prompt-lab/sessions/session-i2v-1/beat-sheet/generate/stream"
        )
        self.assertEqual(inactive.status_code, 422)
        self.assertIn("not active", inactive.json()["detail"])


class Ref2VArbitrationWebTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.directory.name)
        sessions = LocalPromptSessionStore(self.directory.name)
        sessions.create(approved_ref2v_session())
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY)),
            comfy=UnusedComfy(),
            assets=assets,
            runs=LocalRunStore(self.directory.name),
        )
        service = PromptCompositionService(
            gateway=SupervisedGateway(),
            cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
            sessions=sessions,
            compositions=LocalPromptCompositionStore(self.directory.name),
        )
        self.client = TestClient(create_app(runner, prompt_composition=service))

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def test_reconciles_a_supervised_plan_through_the_stream_route(self):
        configured = self.client.post(
            "/api/prompt-lab/sessions/session-ref2v-1/composition",
            json={
                "cookbook_id": "undressing.single_shot",
                "cookbook_version": "0.8.0",
                "bindings": {
                    "dressed_start": ["reference-start"],
                    "body_reference": ["reference-body"],
                },
            },
        )
        self.assertEqual(configured.status_code, 200, configured.text)
        generated = self.client.post(
            "/api/prompt-lab/sessions/session-ref2v-1/beat-sheet/generate/stream"
        )
        self.assertEqual(generated.status_code, 200, generated.text)

        reconciled = self.client.post(
            "/api/prompt-lab/sessions/session-ref2v-1/beat-sheet/reconcile/stream",
            json={
                "decisions": {
                    "retained_garment_visibility": (
                        "Retain the garment and remove the incompatible visibility request."
                    )
                },
                "instruction": "Give the transition more time.",
            },
        )

        self.assertEqual(reconciled.status_code, 200, reconciled.text)
        payloads = sse_payloads(reconciled)
        self.assertEqual(payloads[-1]["kind"], "completed")
        self.assertEqual(payloads[-1]["document_stage"], "beat_sheet")
        document = payloads[-1]["composition"]["documents"]["beat_sheet"]
        self.assertFalse(document["complete"])
        self.assertIn("Retain the garment", document["active_content"])


if __name__ == "__main__":
    unittest.main()
