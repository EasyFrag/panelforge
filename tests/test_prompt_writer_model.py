"""User-run model-routing regressions. Scripted responses only, no inference."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner
from panelforge.application import StreamEventKind
from panelforge.domain import CompositionStage
from panelforge.domain.prompt_writer import WRITER_MODEL_RECIPES, supports_writer_model
from panelforge.domain.video_preparation import ClassicCinematicSettings, CombatSettings, SensualSettings
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from panelforge.infrastructure.storage import LocalRunStore
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset
from panelforge.features.lab.web import create_app
from tests.test_classic_cinematic import fixture
from tests.test_video_preparation_recipes import preparation_service

ROOT = Path(__file__).resolve().parents[1]


def classic_service(directory, mode="ref2v", *, writer_responses=2):
    plan, writer, _ = fixture()
    return preparation_service(
        directory, mode, "planned",
        [json.dumps(plan)] + [json.dumps(writer)] * writer_responses,
        cinematic_settings=ClassicCinematicSettings(),
        source_text="A quiet object reveal lasting 8 seconds. No music or speech.",
    )


class PromptWriterModelTest(unittest.TestCase):
    def test_http_configuration_reopen_and_restore_same_model(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, original = classic_service(directory)
            runner = ChangeViewRunner(
                recipe=ChangeViewPresetRecipe(load_change_view_preset(
                    ROOT / "workflows/character.change_view/qwen-edit-2511-multiple-angles/0.2.0")),
                comfy=object(), assets=service.assets, runs=LocalRunStore(directory),
            )
            client = TestClient(create_app(runner, prompt_composition=service))
            catalog = client.get("/api/prompt-lab/cookbooks").json()["cookbooks"]
            self.assertEqual({(c["id"], c["version"]) for c in catalog if c["supports_writer_model"]}, WRITER_MODEL_RECIPES)
            fork = replace(session, session_id="forked-session")
            service.sessions.create(fork)
            endpoint = f"/api/prompt-lab/sessions/{fork.session_id}/composition"
            response = client.post(endpoint, json={
                "cookbook_id": original.cookbook.cookbook_id,
                "cookbook_version": original.cookbook.version,
                "bindings": {b.slot_id: list(b.reference_ids) for b in original.bindings},
                "preparation_intent": {
                    "source_text": original.preparation_intent.source_text,
                    "creative_freedom": 35, "creative_audacity": 2,
                },
                "writer_model_id": "local::gemma",
            })
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()["composition"]
            self.assertTrue(saved["supports_writer_model"])
            self.assertEqual(saved["writer_model_id"], "local::gemma")
            self.assertEqual(client.get(endpoint).json()["composition"], saved)
            response = client.put(endpoint + "/writer-model", json={
                "writer_model_id": None, "expected_writer_model_id": "local::gemma",
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIsNone(response.json()["composition"]["writer_model_id"])
            self.assertEqual(client.put(endpoint + "/writer-model", json={
                "writer_model_id": "", "expected_writer_model_id": None,
            }).status_code, 422)
            self.assertEqual(gateway.requests, [])

    def test_exact_adoption_and_historical_isolation(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        adopted = set()
        for cookbook in catalog.list():
            ref = cookbook.reference
            if supports_writer_model(ref.cookbook_id, ref.version):
                adopted.add((ref.cookbook_id, ref.version))
                self.assertEqual(cookbook.preparation_steps, 2)
        self.assertEqual(adopted, WRITER_MODEL_RECIPES)
        self.assertEqual(len(adopted), 6)
        for identity, version in adopted:
            self.assertFalse(supports_writer_model(identity, "99.0.0"))
            self.assertFalse(supports_writer_model(identity.replace(".planned", ".guided"), version))
            self.assertFalse(supports_writer_model(identity.replace(".planned", ".prompt"), version))
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, composition = preparation_service(directory, "ref2v", "planned", [])
            with self.assertRaisesRegex(ValueError, "does not support"):
                replace(composition, writer_model_id="local::gemma")
            with self.assertRaisesRegex(ValueError, "does not support"):
                service.set_writer_model(session.session_id, "local::gemma", expected_writer_model_id=None)
            self.assertEqual(service.get(session.session_id), composition)
            self.assertEqual(gateway.requests, [])

    def test_all_six_recipes_keep_the_planner_model_and_request_identical(self):
        families = {
            "classic": {"cinematic_settings": ClassicCinematicSettings()},
            "combat": {"combat_settings": CombatSettings(orientation="mixed"), "version": "1.3.0"},
            "sensual": {"sensual_settings": SensualSettings()},
        }
        for mode in ("fl2va", "ref2v"):
            for family, options in families.items():
                with self.subTest(mode=mode, family=family), tempfile.TemporaryDirectory() as directory:
                    service, gateway, session, composition = preparation_service(
                        directory, mode, "planned", [], preparation_family=family,
                        source_text="A short scene lasting eight seconds.", **options,
                    )
                    before = service._request(session.session_id, CompositionStage.BEAT_SHEET, instruction=None)[4]
                    saved = service.set_writer_model(session.session_id, "local::gemma", expected_writer_model_id=None)
                    after = service._request(session.session_id, CompositionStage.BEAT_SHEET, instruction=None)[4]
                    self.assertEqual(before, after)
                    self.assertEqual(after.model_id, session.model_id)
                    self.assertEqual(saved, replace(composition, writer_model_id="local::gemma"))
                    self.assertEqual(gateway.requests, [])

    def test_two_calls_same_or_distinct_models_sync_and_stream(self):
        for mode in ("fl2va", "ref2v"):
            for streamed in (False, True):
                for planner, writer in (("server-qwen", None), ("local::gemma", None),
                                        ("local::qwen", "local::gemma"), ("local::qwen", "server-gemma")):
                    with self.subTest(mode=mode, streamed=streamed, planner=planner, writer=writer), tempfile.TemporaryDirectory() as directory:
                        service, gateway, session, initial = classic_service(directory, mode)
                        service.sessions.save(replace(session, model_id=planner))
                        service.set_writer_model(session.session_id, writer, expected_writer_model_id=None)
                        for stage in (CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT):
                            if streamed:
                                events = list(service.stream_generate(session.session_id, stage))
                                self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED, events[-1])
                            else:
                                service.generate(session.session_id, stage)
                            service.approve(session.session_id, stage)
                        self.assertEqual([r.model_id for r in gateway.requests], [planner, writer or planner])
                        self.assertTrue(gateway.requests[0].images)
                        self.assertEqual(gateway.requests[1].images, ())
                        self.assertIn("PLAN TO PRESERVE:", gateway.requests[1].user_prompt)
                        self.assertIn("REFERENCE ROLES:", gateway.requests[1].user_prompt)
                        saved = LocalPromptCompositionStore(directory).get(session.session_id)
                        self.assertEqual(saved.writer_model_id, writer)
                        # Changing the next writer neither invalidates nor rewrites approved output.
                        changed = service.set_writer_model(session.session_id, "new-writer", expected_writer_model_id=writer)
                        self.assertEqual(saved.beat_sheet, changed.beat_sheet)
                        self.assertEqual(saved.final_prompt, changed.final_prompt)
                        service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Keep the quiet observation.")
                        self.assertEqual(gateway.requests[-1].model_id, "new-writer")
                        self.assertEqual(len(gateway.requests), 3)

    def test_retry_final_after_gateway_failure_preserves_plan_and_constraints(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = classic_service(directory)
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            approved = service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            baseline = service._request(session.session_id, CompositionStage.FINAL_PROMPT, instruction=None)[4]
            service.set_writer_model(session.session_id, "offline-writer", expected_writer_model_id=None)
            with patch.object(gateway, "complete", side_effect=RuntimeError("offline")):
                with self.assertRaisesRegex(RuntimeError, "offline"):
                    service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(service.get(session.session_id).beat_sheet, approved.beat_sheet)
            service.set_writer_model(session.session_id, "local::gemma", expected_writer_model_id="offline-writer")
            routed = service._request(session.session_id, CompositionStage.FINAL_PROMPT, instruction=None)[4]
            self.assertEqual(replace(baseline, model_id="local::gemma"), routed)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(len(gateway.requests), 2)
            with self.assertRaisesRegex(ValueError, "concurrently"):
                service.set_writer_model(session.session_id, "another", expected_writer_model_id=None)
            self.assertEqual(service.get(session.session_id).writer_model_id, "local::gemma")

    def test_storage_reads_versions_one_to_four_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, composition = classic_service(directory)
            path = Path(directory) / "prompt_compositions" / session.session_id / "composition.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(original["schema_version"], 5)
            for version in (1, 2, 3, 4):
                with self.subTest(version=version):
                    raw = deepcopy(original)
                    raw["schema_version"] = version
                    raw.pop("writer_model_id")
                    if version < 3:
                        raw.pop("preparation_intent")
                    path.write_text(json.dumps(raw), encoding="utf-8")
                    before = path.read_bytes()
                    restored = service.get(session.session_id)
                    self.assertIsNone(restored.writer_model_id)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(restored.cookbook, composition.cookbook)
            path.write_text(json.dumps(original), encoding="utf-8")
            for invalid in ("", "  ", " gemma ", 42):
                with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                    replace(composition, writer_model_id=invalid)


if __name__ == "__main__":
    unittest.main()
