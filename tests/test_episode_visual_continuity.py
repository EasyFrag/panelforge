"""User-run checks; isolated stores, fake media services, no LLM or renderer."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.episodes import EpisodeConflict
from panelforge.domain import story_continuity as ledger
from panelforge.features.lab.episodes_web import episodes_router
from tests import test_episodes as fixtures
from tests.test_story_visual_continuity import change, character


class EpisodeVisualContinuityTest(unittest.TestCase):
    setUp = fixtures.EpisodeTest.setUp
    create = fixtures.EpisodeTest.create

    def visual(self):
        element = character()
        element.update(scene_indices=[0], states=[change("muscles", appearance="Carrure musclée", clothing="T-shirt déchiré", reference=True)])
        return dict(version=1, dramatic_summary="Une transformation durable.", elements=[element])

    def test_author_update_preserves_existing_preparations_and_rejects_lost_updates(self):
        view = self.create(); identity = view["episode_id"]
        value = self.service.store.get(identity)
        old = dict(id="prep-before", status="ready", input_hash="original", render_project_id=None,
                   session_id=None, saved_prompt="Keep this recorded prompt")
        value["scenes"][0]["preparations"] = [old]
        self.service.store.save(value)
        updated = self.service.update_continuity(identity, 1, self.visual())
        self.assertEqual(updated["continuity_revision"], 2)
        self.assertEqual(self.service.store.get(identity)["scenes"][0]["preparations"], [old])
        self.assertTrue(updated["scenes"][0]["stale"])
        with self.assertRaises(EpisodeConflict):
            self.service.update_continuity(identity, 1, ledger.empty())
        self.assertEqual(self.krea.calls, [])
        self.assertEqual(self.krea.render_calls, [])

    def test_active_work_blocks_ledger_mutation_without_touching_the_saved_project(self):
        view = self.create(); identity = view["episode_id"]
        previous = deepcopy(self.service.store.get(identity))
        self.service._active.add((identity, "scenes", "scene-1"))
        with self.assertRaises(EpisodeConflict):
            self.service.update_continuity(identity, 1, self.visual())
        self.assertEqual(self.service.store.get(identity), previous)

    def test_continuation_keeps_previous_state_separate_from_the_new_intention(self):
        parent = self.stories.edit_continuity(self.story["project_id"], self.story["version"], self.visual())
        child = self.stories.create(title="Suite", brief="Banane se rapproche de Citron.",
            prior_story="La transformation a déjà eu lieu.", parent_story_id=parent["project_id"])
        self.assertEqual(child["brief"], "Banane se rapproche de Citron.")
        self.assertEqual(child["prior_story"], "La transformation a déjà eu lieu.")
        state = child["document"]["visual_state_inherited"]["elements"][0]["states"][0]
        self.assertEqual(state["clothing"], "T-shirt déchiré")
        self.assertEqual(state["at"], "start")

    def test_guided_qwen_project_neither_generates_nor_selects_an_image_implicitly(self):
        view = self.create(); identity = view["episode_id"]
        view = self.service.update_continuity(identity, 1, self.visual())
        base = next(r for r in view["references"] if r["source_id"] == "c1" and not r.get("continuity_state_id"))
        view = self.service.import_image(identity, base["id"], base["revision"], b"fake identity", "image/png", "Citron")
        variant = next(r for r in view["references"] if r.get("continuity_state_id"))
        qwen_project = dict(id="qwen-variant", stages=[dict(id="step", index=1, revision=0, attempts=[])])
        self.service.qwen_edit = NS(create=Mock(return_value=qwen_project), update=Mock(), get=Mock(return_value=qwen_project))
        self.assets.read_bytes = Mock(return_value=b"fake identity")
        result = self.service.create_continuity_variant(identity, variant["id"], variant["revision"])
        prepared = next(r for r in result["episode"]["references"] if r["id"] == variant["id"])
        self.assertIsNone(prepared["image_asset_id"])
        self.assertEqual(result["project_id"], "qwen-variant")
        self.assertIn("T-shirt déchiré", self.service.qwen_edit.update.call_args.kwargs["changes"]["draft"])
        self.assertEqual(self.krea.calls, [])
        self.assertEqual(self.krea.render_calls, [])
        # Reopening the same variant does not create another project.
        self.service.create_continuity_variant(identity, prepared["id"], prepared["revision"])
        self.service.qwen_edit.create.assert_called_once()
        qwen_project["stages"][0]["attempts"] = [dict(status="succeeded", output_asset_id="qwen-result")]
        with self.assertRaisesRegex(ValueError, "résultat terminé"):
            self.service.select_continuity_variant(identity, prepared["id"], prepared["revision"], "unrelated-asset")
        selected = self.service.select_continuity_variant(identity, prepared["id"], prepared["revision"], "qwen-result")
        self.assertEqual(next(r for r in selected["references"] if r["id"] == prepared["id"])["image_asset_id"], "qwen-result")
        self.assertEqual(selected["scenes"][0]["resolved_references"][0]["reference_id"], prepared["id"])

    def test_http_ledger_revision_conflict_is_actionable(self):
        view = self.create(); identity = view["episode_id"]
        app = FastAPI()
        app.include_router(episodes_router(self.service, serialize_image_project=lambda x: x,
            validate_image=None, image_body=None, render_body=None, serialize_render_project=lambda p: p))
        with TestClient(app) as client:
            url = f"/api/episodes/{identity}/continuity"
            body = dict(expected_revision=1, visual_continuity=self.visual())
            self.assertEqual(client.put(url, json=body).status_code, 200)
            self.assertEqual(client.put(url, json=body).status_code, 409)
            self.assertEqual(client.put(url, json={**body, "expected_revision": True}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
