"""Versioned Edit chains; synthetic fixtures only, never call a renderer/LLM."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from panelforge.application.krea2_edit import Krea2EditAttemptRequest, RetouchConflictError
from panelforge.domain.krea2_edit import Krea2EditPromptRevision, Krea2EditPromptStatus
from panelforge.features.lab.web import serialize_krea2_edit_source
from panelforge.infrastructure.storage.krea2_edits import LocalKrea2EditStore
from panelforge.infrastructure.storage import krea2_edits as storage
from tests import test_krea2_retouch as fixtures


class EditVersionsTest(unittest.TestCase):
    def setUp(self):
        fixtures.RetouchServiceTest.setUp(self)
        self.original = replace(self.original, settings=replace(self.original.settings, megapixels=0.8))
        self.source = self.store.save(replace(self.source, attempts=(self.original,)))
        second = self.service.promote_attempt(self.source.source_id, self.original.attempt_id,
                                             project_name="Wall", step_name="Opening")
        self.second_result = replace(self.original, attempt_id="second-result")
        revision = Krea2EditPromptRevision("conversation", "Door instruction", self.original.prompt,
                                         self.original.prompt, "local", assistant_message="Door proposal")
        self.second = self.store.save(replace(second, attempts=(self.second_result,),
                                             revisions=(revision,), instruction="Door instruction"))
        self.third = self.service.promote_attempt(self.second.source_id, self.second_result.attempt_id,
                                                 step_name="Door")
        self.second = self.store.get(self.second.source_id)
        self.old = self.service.project_stages(self.source.project_id)

    def tearDown(self):
        fixtures.RetouchServiceTest.tearDown(self)

    def resume(self, request_id="resume"):
        return self.service.resume_stage(self.second.source_id, request_id=request_id)

    def test_backlog_counts_families_and_keeps_complete_stages_of_the_open_version(self):
        resumed = self.resume()
        page = self.service.backlog(1, project_id=self.source.project_id)
        self.assertEqual(page.project_count, 1)
        self.assertEqual(page.project_ids, (resumed.project_id,))
        self.assertEqual(len(page.sources), 5)  # Three original stages + two resumed stages.
        self.assertEqual(tuple(s for s in sorted(page.sources, key=lambda s: s.stage_index)
                               if s.project_id == self.source.project_id), self.old)
        self.service.promote_attempt(resumed.source_id, self.second_result.attempt_id, step_name="Corrected door")
        page = self.service.backlog(1, project_id=self.source.project_id)
        self.assertEqual(page.project_count, 1)
        self.assertEqual(page.project_ids, (resumed.project_id,))
        historical = next(v for v in page.versions if v["project_id"] == self.source.project_id)
        self.assertEqual(historical["status"], "historical")
        self.assertEqual(len([s for s in page.sources if s.project_id == self.source.project_id]), 3)
        self.assertEqual(self.service.project_stages(self.source.project_id), self.old)

    def test_resume_keeps_source_conversation_settings_and_original_chain(self):
        asset_files = sorted(p.name for p in (self.root / "assets").iterdir())
        resumed = self.resume()
        self.assertNotEqual(resumed.project_id, self.second.project_id)
        self.assertEqual(resumed.stage_index, 2)
        self.assertEqual(resumed.source_asset_id, self.second.source_asset_id)
        self.assertEqual(resumed.revisions, self.second.revisions)
        self.assertEqual(resumed.attempts, self.second.attempts)
        self.assertEqual(resumed.generated_prompt, self.second_result.prompt)
        self.assertIsNone(resumed.accepted_attempt_id)
        self.assertEqual(serialize_krea2_edit_source(resumed)["resume_attempt_id"], "second-result")
        self.assertEqual(resumed.attempts[0].settings.megapixels, 0.8)
        self.assertEqual(self.service.project_stages(self.source.project_id), self.old)
        self.assertEqual(len(self.service.project_stages(resumed.project_id)), 2)
        self.assertEqual(sorted(p.name for p in (self.root / "assets").iterdir()), asset_files)
        self.assertEqual({v["number"]: v["status"] for v in self.service.project_versions()}, {1: "active", 2: "draft"})
        self.assertEqual(LocalKrea2EditStore(self.root).get(resumed.source_id), resumed)

    def test_first_stage_and_historical_stage_can_both_be_resumed(self):
        resumed = self.service.resume_stage(self.source.source_id, request_id="root")
        self.assertEqual(resumed.source_id, resumed.project_id)
        self.assertIsNone(resumed.parent_source_id)
        self.service.promote_attempt(resumed.source_id, self.original.attempt_id, step_name="Opening")
        another = self.resume()
        self.assertEqual(another.revision.number, 3)
        self.assertEqual(another.revision.family_id, self.source.project_id)
        self.assertEqual(self.service.project_stages(self.source.project_id), self.old)

    def test_validation_uses_selected_candidate_and_exports_only_its_chain(self):
        old_manifest = (self.root / "exports").glob("*/project.json")
        old_path = next(old_manifest)
        old_bytes = old_path.read_bytes()
        resumed = self.resume()
        selected_asset = self.assets.create(self.source_bytes, media_type="image/png")
        selected = replace(self.second_result, attempt_id="higher-resolution",
                           settings=replace(self.second_result.settings, megapixels=2.1),
                           output_asset_id=selected_asset.asset_id)
        newer = replace(self.second_result, attempt_id="unused-newer")
        resumed = self.store.save(replace(resumed, attempts=(*resumed.attempts, selected, newer)))
        child = self.service.promote_attempt(resumed.source_id, selected.attempt_id, step_name="Door corrected")
        self.assertEqual(child.source_asset_id, selected.output_asset_id)
        self.assertEqual(child.metadata.megapixels, 2.1)
        self.assertEqual(child.revisions, ())
        self.assertEqual(child.attempts, ())
        self.assertEqual(child.parent_source_id, resumed.source_id)
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(self.service.project_stages(self.source.project_id), self.old)
        self.assertEqual({v["number"]: v["status"] for v in self.service.project_versions()}, {1: "historical", 2: "active"})
        exported = json.loads((Path(child.export_path) / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(len(exported["accepted_chain"]), 2)
        self.assertEqual(exported["accepted_chain"][-1]["output_asset_id"], selected.output_asset_id)
        self.assertEqual(exported["version_number"], 2)
        self.assertEqual(self.service.promote_attempt(resumed.source_id, selected.attempt_id), child)
        self.assertEqual(self.resume().source_id, resumed.source_id)
        with self.assertRaises(RetouchConflictError):
            self.service.prepare_attempt(self.third.source_id, Krea2EditAttemptRequest(selected.prompt, selected.settings))
        with self.assertRaises(RetouchConflictError):
            list(self.service.stream_prepare_prompt(self.third.source_id, "late", "local"))
        with self.assertRaises(RetouchConflictError):
            self.service.restart_stage(self.third.source_id, expected_restart_count=0)

    def test_latest_validation_wins_even_when_drafts_were_created_in_another_order(self):
        older_draft = self.resume("older")
        newer_draft = self.resume("newer")
        self.service.promote_attempt(newer_draft.source_id, "second-result", step_name="Door")
        self.service.promote_attempt(older_draft.source_id, "second-result", step_name="Door")
        versions = {v["number"]: v["status"] for v in self.service.project_versions()}
        self.assertEqual(versions, {1: "historical", 2: "active", 3: "historical"})

    def test_validating_an_existing_alternative_releases_the_initial_resume_selection(self):
        alternative = replace(self.second_result, attempt_id="alternative")
        self.store.save(replace(self.second, attempts=(*self.second.attempts, alternative)))
        resumed = self.resume()
        self.assertEqual(serialize_krea2_edit_source(resumed)["resume_attempt_id"], "second-result")
        self.service.promote_attempt(resumed.source_id, alternative.attempt_id, step_name="Alternative")
        serialized = serialize_krea2_edit_source(self.store.get(resumed.source_id))
        self.assertEqual(serialized["accepted_attempt_id"], "alternative")
        self.assertIsNone(serialized["resume_attempt_id"])

    def test_resume_is_idempotent_and_partial_storage_is_not_visible(self):
        original_write = storage._atomic_write
        def fail_root(path, content):
            data = json.loads(content)
            if data.get("revision") and data["stage_index"] == 1:
                raise OSError("disk unavailable")
            original_write(path, content)
        with patch.object(storage, "_atomic_write", side_effect=fail_root):
            with self.assertRaises(OSError):
                self.resume()
        self.assertEqual(len(self.store.list(999, include_hidden=True)), len(self.old))
        self.assertEqual(self.service.project_stages(self.source.project_id), self.old)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.resume(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.service.project_versions()), 2)

    def test_failed_validation_keeps_original_active_and_draft_reusable(self):
        resumed = self.resume()
        with patch.object(self.store, "create", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.service.promote_attempt(resumed.source_id, "second-result", step_name="Door")
        self.assertEqual(self.store.get(resumed.source_id), resumed)
        self.assertEqual({v["number"]: v["status"] for v in self.service.project_versions()}, {1: "active", 2: "draft"})
        busy = replace(self.third, prompt_status=Krea2EditPromptStatus.GENERATING)
        self.store.save(busy)
        with self.assertRaises(RetouchConflictError):
            self.service.promote_attempt(resumed.source_id, "second-result", step_name="Door")
        self.assertEqual(self.store.get(busy.source_id), busy)

    def test_resume_from_retouch_restores_original_pair_and_saved_mask(self):
        # Reuse a successful generation as a new stage fixture, without rendering.
        target = self.store.save(replace(self.third, attempts=(replace(self.original, attempt_id="retouch-origin"),)))
        dimensions = fixtures.decoded(self.assets.read_bytes(target.source_asset_id)).size
        mask = fixtures.png(fixtures.Image.new("L", dimensions, 128))
        target, retouch = self.service.save_retouch(target.source_id, "retouch-origin", mask,
                                                  request_id="mask", harmonize=True, harmonize_strength=50)
        self.service.promote_attempt(target.source_id, retouch.attempt_id, step_name="Masked")
        resumed = self.service.resume_stage(target.source_id, request_id="retouch-resume")
        prepared = self.service.prepare_retouch(resumed.source_id, retouch.attempt_id)
        self.assertTrue(prepared["editable"])
        self.assertEqual(prepared["mask_png"], self.assets.read_bytes(retouch.retouch.mask_asset_id))
        self.assertEqual(prepared["harmonize_strength"], 50)
        self.assertEqual(serialize_krea2_edit_source(resumed)["resume_attempt_id"], retouch.attempt_id)
        self.assertIsNone(self.store.get(resumed.source_id).attempts[-1].execution_id)

    def test_http_resume_retries_and_version_navigation(self):
        runner = fixtures.ChangeViewRunner(recipe=fixtures.ChangeViewPresetRecipe(fixtures.load_change_view_preset(
            fixtures.ROOT / "workflows/character.change_view/qwen-edit-2511-multiple-angles/0.2.0")),
            comfy=fixtures.NoExternal(), assets=self.assets, runs=fixtures.LocalRunStore(self.root))
        with fixtures.TestClient(fixtures.create_app(runner, krea2_edit=self.service)) as client:
            url = f"/api/image-lab/krea2-edit/sources/{self.second.source_id}/resume"
            self.assertEqual(client.post(url, json={"request_id": "../bad"}).status_code, 422)
            response = client.post(url, json={"request_id": "http"})
            self.assertEqual(response.status_code, 200, response.text)
            resumed = response.json()["source"]
            self.assertEqual(client.post(url, json={"request_id": "http"}).json(), response.json())
            draft = client.get(f"/api/image-lab/krea2-edit/projects/{resumed['project_id']}")
            self.assertEqual(len(draft.json()["sources"]), 2)
            old = client.get(f"/api/image-lab/krea2-edit/projects/{self.source.project_id}")
            self.assertEqual(len(old.json()["sources"]), 3)
            listed = client.get("/api/image-lab/krea2-edit/sources?limit=1").json()
            self.assertEqual(len(listed["versions"]), 2)
            self.assertEqual(len(listed["sources"]), 5)  # Complete draft and active chain of the selected family.
            self.assertEqual(client.post(f"/api/image-lab/krea2-edit/sources/{self.third.source_id}/resume",
                                         json={"request_id": "pending"}).status_code, 422)
