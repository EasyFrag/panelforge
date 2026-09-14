"""User-run offline checks for recipe edits, pinned cycles and durable traces."""
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panelforge.application import LlmCallApplicationOutcome
from panelforge.application.direct_fl2va_prompt import requested_h3_base_duration_ms
from panelforge.domain import CompositionStage
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage.prompt_recipes import LocalPromptRecipeStore, CAMERA_CONTRACT
from panelforge.infrastructure.storage.llm_traces import LocalLlmTraceStore
from panelforge.infrastructure.storage.llm_calls import LocalLlmCallStore
from tests.test_classic_cinematic import fixture
from tests.test_video_preparation_recipes import preparation_service
from tests.test_llm_call_logs import sample_record


H3 = ("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0")
REF = ("minimax.h3.ref2v.classic.cinematic.planned", "1.0.0")
COMBAT = ("minimax.h3.fl2va.combat.planned", "1.3.0")


def store(directory):
    return LocalPromptRecipeStore(directory, LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks"),
                                 ROOT / "prompt_sources/_defaults")


class PromptRecipeTest(unittest.TestCase):
    def test_duration_target_and_action_timestamps_are_distinct(self):
        for total in ("12.95", "12,95"):
            self.assertEqual(requested_h3_base_duration_ms(
                f"Durée cible : {total} secondes. À 6,66 s la boîte s'ouvre ; à 9,16 s elle se referme."), 12950)
        with self.assertRaisesRegex(ValueError, "conflicting explicit durations"):
            requested_h3_base_duration_ms("Durée cible : 10 secondes. Durée totale : 12 secondes.")
        self.assertEqual(requested_h3_base_duration_ms("An eight-second shot lasting 8 seconds."), 8000)

    def test_edit_reopen_rollback_and_family_and_mode_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            recipes = store(directory)
            current = recipes.get(*H3)
            other, combat = recipes.get(*REF), recipes.get(*COMBAT)
            self.assertEqual(current["active"], 2)
            self.assertEqual(recipes.get(*H3, revision=1)["fields"]["camera_contract"], "")
            changed = {**current["fields"], "plan.system": current["fields"]["plan.system"] + "\nA neutral marker."}
            saved = recipes.save(*H3, base_revision=2, expected_active=2, fields=changed)
            self.assertEqual(saved["revision"], 3)
            reopened = store(directory)
            self.assertEqual(reopened.get(*H3)["fields"], changed)
            self.assertEqual(reopened.get(*REF)["fields"], other["fields"])
            self.assertEqual(reopened.get(*COMBAT)["fields"], combat["fields"])
            reopened.activate(*H3, 1, 3)
            self.assertEqual(store(directory).get(*H3)["revision"], 1)
            self.assertEqual(reopened.get(*H3, revision=3)["fields"], changed)
            with self.assertRaisesRegex(ValueError, "active a changé"):
                reopened.save(*H3, base_revision=3, expected_active=3, fields=changed)
            with self.assertRaises(KeyError):
                reopened.get("../escape", "1.0.0")

    def test_template_variables_and_archived_bytes_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            recipes = store(directory); package = recipes.get(*H3)
            template = package["templates"][0]
            fields = {**package["fields"], template: "Removed every substitution."}
            with self.assertRaisesRegex(ValueError, "variables"):
                recipes.save(*H3, base_revision=2, expected_active=2, fields=fields)
            archive = recipes.root / H3[0] / H3[1] / "revisions/2/plan.system.txt"
            archive.write_text("Changed outside the editor", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "archivée"):
                recipes.get(*H3)

    def test_plan_and_writer_pin_package_across_edit_and_reopen(self):
        for mode, key in (("fl2va", H3), ("ref2v", REF)):
            for streamed in (False, True):
                with self.subTest(mode=mode, streamed=streamed), tempfile.TemporaryDirectory() as directory:
                    plan, writer, _ = fixture()
                    service, gateway, session, _ = preparation_service(directory, mode, "planned",
                        [json.dumps(plan), json.dumps(writer), json.dumps(plan)], version="1.0.0",
                        cinematic_settings=ClassicCinematicSettings(), source_text="A quiet object reveal lasting 8 seconds. No music or speech.")
                    service.prompt_recipes = store(directory)
                    def generate(stage):
                        if streamed:
                            list(service.stream_generate(session.session_id, stage))
                        else:
                            service.generate(session.session_id, stage)
                    generate(CompositionStage.BEAT_SHEET)
                    current = service.get(session.session_id).beat_sheet.active_revision
                    self.assertEqual(current.prompt_recipe_revision, 2)
                    self.assertIn(CAMERA_CONTRACT, gateway.requests[0].system_prompt)
                    self.assertIn("never 'alongside'", gateway.requests[0].user_prompt)
                    service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                    package = service.prompt_recipes.get(*key)
                    fields = {**package["fields"], "writer.system": package["fields"]["writer.system"] + "\nNEXT_CYCLE_ONLY"}
                    service.prompt_recipes.save(*key, base_revision=2, expected_active=2, fields=fields)
                    service.prompt_recipes = store(directory)
                    generate(CompositionStage.FINAL_PROMPT)
                    self.assertNotIn("NEXT_CYCLE_ONLY", gateway.requests[1].system_prompt)
                    self.assertEqual(service.get(session.session_id).final_prompt.active_revision.prompt_recipe_revision, 2)
                    generate(CompositionStage.BEAT_SHEET)
                    self.assertEqual(service.get(session.session_id).beat_sheet.active_revision.prompt_recipe_revision, 3)
                    self.assertEqual(len(gateway.requests), 3)

    def test_baseline_package_preserves_assembled_request_and_preview_makes_no_call(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "planned", [], version="1.0.0",
                cinematic_settings=ClassicCinematicSettings(), source_text="A quiet object reveal lasting 8 seconds.")
            original = service.preview_request(session.session_id, CompositionStage.BEAT_SHEET)
            service.prompt_recipes = store(directory)
            service.prompt_recipes.activate(*H3, 1, 2)
            editable = service.preview_request(session.session_id, CompositionStage.BEAT_SHEET)
            self.assertEqual(editable.system_prompt, original.system_prompt)
            self.assertEqual(editable.user_prompt, original.user_prompt)
            self.assertEqual(gateway.requests, [])

    def test_exact_lookup_does_not_parse_an_unrelated_broken_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            import shutil
            target = Path(directory) / "cookbooks"
            shutil.copytree(ROOT / "prompt_cookbooks", target)
            broken = target / "unrelated.old/1.0.0"; broken.mkdir(parents=True)
            (broken / "manifest.json").write_text("broken", encoding="utf-8")
            recipe = LocalPromptCookbookCatalog(target).get(*H3)
            self.assertEqual(recipe.reference.cookbook_id, H3[0])


class DurableVideoTraceTest(unittest.TestCase):
    def test_calls_survive_rolling_journal_and_outcome_arrival_order(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = LocalLlmTraceStore(directory); journal = LocalLlmCallStore(directory)
            for index in range(25):
                record = sample_record(index)
                traces.begin(record.call_id, {"session_id": "session-1", "stage": "beat_sheet", "recipe_revision": 1})
                if index == 0:
                    traces.outcome(record.call_id, LlmCallApplicationOutcome.ACCEPTED, None, None)
                traces.finish(record); journal.append(record)
            traces.outcome("call-24", LlmCallApplicationOutcome.REJECTED, "ValueError", "Invalid output")
            records = LocalLlmTraceStore(directory).list(session_id="session-1")
            self.assertEqual(len(records), 25)
            self.assertEqual(len(journal.list()), 20)
            self.assertEqual(records[0]["call"]["system_prompt"], "System")
            self.assertEqual(records[0]["call"]["application_outcome"], "accepted")
            self.assertEqual(records[-1]["call"]["application_error_message"], "Invalid output")
            self.assertNotIn("content", records[0]["call"]["images"][0])

    def test_render_snapshot_excludes_future_adjustments_and_tracks_resumed_prompt(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            traces = LocalLlmTraceStore(directory)
            turns = [SimpleNamespace(turn_id="turn-1", prompt=None), SimpleNamespace(turn_id="turn-2", prompt="First"),
                     SimpleNamespace(turn_id="turn-3", prompt=None), SimpleNamespace(turn_id="turn-4", prompt="Second")]
            project = SimpleNamespace(project_id="project-1", source_session_id="session-1", source_prompt_revision_id="final-1",
                                      current_prompt="Second", turns=turns)
            traces.snapshot(project, SimpleNamespace(attempt_id="attempt-1", prompt="First"))
            snapshot = traces.render_snapshot("attempt-1")
            self.assertEqual(snapshot["turn_ids"], ["turn-1", "turn-2"])
            self.assertFalse(snapshot["manual_prompt"])


class PromptRecipeApiTest(unittest.TestCase):
    def test_save_activate_and_preview_without_gateway_call(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from panelforge.features.lab.prompt_recipes_web import prompt_recipes_router
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "planned", [], version="1.0.0",
                cinematic_settings=ClassicCinematicSettings(), source_text="A quiet observation lasting 8 seconds.")
            recipes = store(directory); service.prompt_recipes = recipes
            app = FastAPI(); app.include_router(prompt_recipes_router(recipes, LocalLlmTraceStore(directory), service, None))
            with TestClient(app) as client:
                url = f"/api/prompt-recipes/recipe/{H3[0]}/{H3[1]}"
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                package = response.json()["recipe"]
                fields = {**package["fields"], "plan.system": package["fields"]["plan.system"] + "\nAPI_MARKER"}
                saved = client.put(url, json={"base_revision": 2, "expected_active": 2, "fields": fields})
                self.assertEqual(saved.status_code, 200)
                preview = client.get(f"/api/prompt-recipes/preview/{session.session_id}/beat_sheet")
                self.assertEqual(preview.status_code, 200)
                self.assertFalse(preview.json()["sent"])
                self.assertIn("API_MARKER", preview.json()["system_prompt"])
                self.assertEqual(gateway.requests, [])
                stale = client.post(url + "/activate", json={"revision": 1, "expected_active": 2})
                self.assertEqual(stale.status_code, 409)
                activated = client.post(url + "/activate", json={"revision": 1, "expected_active": 3})
                self.assertEqual(activated.json()["recipe"]["active"], 1)
