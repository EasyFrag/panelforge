"""User-run queue regressions. In-memory Qwen/KREA/H3 fakes, no model services."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.features.lab.episodes_web import episodes_router

from panelforge.application.episodes import EpisodeConflict
from panelforge.domain import episode_continuity as continuity
from tests import test_episodes as fixtures
from tests.test_story_visual_continuity import scenario, change
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from tests.test_long_stories import OPTIONS


class FakeQwen:
    def __init__(self, assets):
        self.assets, self.projects, self.queued, self.sources, self.cancelled = assets, {}, [], [], []

    def create(self, *, name, content):
        self.sources.append(content)
        identity = f"qwen-{len(self.projects) + 1}"
        self.projects[identity] = dict(id=identity, stages=[dict(id="stage", revision=0, attempts=[], draft="")])
        return self.get(identity)

    def get(self, identity): return deepcopy(self.projects[identity])

    def update(self, identity, stage_id, *, revision, changes):
        stage = self.projects[identity]["stages"][0]
        assert stage["revision"] == revision
        stage.update(changes); stage["revision"] += 1
        return self.get(identity)

    def queue_attempt(self, identity, stage_id, *, revision, request_id):
        stage = self.projects[identity]["stages"][0]
        if any(a["request_id"] == request_id for a in stage["attempts"]): return self.get(identity)
        assert stage["revision"] == revision
        assert not stage["draft"] and "<image1>" in stage["prompt"]
        self.queued.append((identity, stage_id, request_id))
        asset = self.assets.create(b"fake-state", media_type="image/png")
        stage["attempts"].append(dict(id=f"attempt-{len(self.queued)}", request_id=request_id,
            status="succeeded", output_asset_id=asset.asset_id))
        stage["revision"] += 1
        return self.get(identity)

    def cancel_attempt(self, *args): self.cancelled.append(args)


class RequiredStateImagesTest(unittest.TestCase):
    create = fixtures.EpisodeTest.create

    def setUp(self):
        fixtures.EpisodeTest.setUp(self)
        self.assets.read_bytes = Mock(return_value=b"accepted-identity")
        self.service.qwen_edit = self.qwen = FakeQwen(self.assets)
        threads = patch("panelforge.application.episode_state_images.Thread", fixtures.InlineThread)
        threads.start(); self.addCleanup(threads.stop)
        self.story.update(visual_state_policy=1)
        source = scenario()
        source["visual_continuity"]["elements"][0]["scene_indices"] = [1, 2]
        source["visual_continuity"]["elements"][0]["states"] = [change("muscles", 1, appearance="Carrure musclée", reference=True)]
        self.story["document"]["scenario"] = source
        self.story["revisions"][0]["document"] = deepcopy(self.story["document"])
        self.story = self.stories.store.save(self.story)

    def start(self, value, request="states"):
        return self.service.start_reference_batch(value["episode_id"], expected_visual_revision=value["visual_revision"],
            request_id=request, reference_ids=[r["id"] for r in value["references"] if r.get("continuity_state_id")],
            profiles={}, thermal={})

    def image(self, value, ref):
        return self.service.import_image(value["episode_id"], ref["id"], ref["revision"], b"fake", "image/png", "chosen.png")

    def with_identities(self):
        value = self.create()
        for ref in value["references"]:
            if not ref.get("continuity_state_id"): value = self.image(value, ref)
        return value

    def test_qwen_waits_for_accepted_identity_then_resumes_without_prompt_llm(self):
        value = self.start(self.create())
        self.assertEqual(value["reference_batch"]["items"][0]["status"], "waiting_source")
        self.assertEqual(self.qwen.queued, [])
        base = next(r for r in value["references"] if r["source_id"] == "c1" and not r.get("continuity_state_id"))
        value = self.image(value, base)
        item = value["reference_batch"]["items"][0]
        self.assertEqual(item["status"], "ready_for_review")
        self.assertEqual(self.qwen.sources, [b"accepted-identity"])
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(self.krea.calls, [])
        self.assertEqual(self.krea.render_calls, [])
        for _ in range(3): self.service.get(value["episode_id"])
        self.assertEqual(len(self.qwen.queued), 1)  # reads never enqueue
        variant = next(r for r in value["references"] if r.get("continuity_state_id"))
        self.assertIsNone(variant["image_asset_id"])
        chosen = self.service.select_image(value["episode_id"], variant["id"], variant["revision"], item["output_asset_id"])
        self.assertEqual(chosen["reference_batch"]["status"], "completed")

    def test_saved_queue_reservation_is_recovered_after_interruption_without_duplicate(self):
        value = self.start(self.with_identities())
        stored = self.service.store.get(value["episode_id"])
        item = stored["reference_batch"]["items"][0]
        ref = next(r for r in stored["references"] if r.get("continuity_state_id"))
        item.pop("attempt_id"); ref["qwen_variant"].pop("batch_attempt_id")
        stored["reference_batch"]["status"] = "interrupted"
        self.service.store.save(stored)
        recovered = self.start(self.service.get(value["episode_id"]), "retry")
        self.assertEqual(recovered["reference_batch"]["items"][0]["status"], "ready_for_review")
        self.assertEqual(len(self.qwen.queued), 1)

    def test_old_qwen_result_cannot_be_selected_after_identity_replacement(self):
        value = self.start(self.with_identities())
        previous = value["reference_batch"]["items"][0]["output_asset_id"]
        base = next(r for r in value["references"] if r["source_id"] == "c1" and not r.get("continuity_state_id"))
        value = self.image(value, base)
        variant = next(r for r in value["references"] if r.get("continuity_state_id"))
        with self.assertRaises(EpisodeConflict):
            self.service.select_image(value["episode_id"], variant["id"], variant["revision"], previous)
        result = self.start(value, "new-source")
        self.assertEqual(len(self.qwen.sources), 2)
        self.assertNotEqual(previous, result["reference_batch"]["items"][0]["output_asset_id"])

    def test_independent_scene_finishes_then_resume_generates_only_waiting_scenes(self):
        value = self.with_identities()
        result = self.service.start_video_chain(value["episode_id"], expected_video_revision=value["video_revision"],
            request_id="chain", scene_ids=[s["id"] for s in value["scenes"]])
        self.assertEqual([i["status"] for i in result["video_chain"]["items"]], ["succeeded", "waiting_reference", "waiting_reference"])
        self.assertEqual(result["video_chain"]["status"], "paused")
        first = deepcopy(result["scenes"][0]["preparations"])
        variant = next(r for r in result["references"] if r.get("continuity_state_id"))
        result = self.image(result, variant)
        result = self.service.resume_video_chain(value["episode_id"], result["video_chain"]["chain_id"])
        self.assertEqual(result["video_chain"]["status"], "completed")
        self.assertEqual(result["scenes"][0]["preparations"], first)
        self.assertEqual([len(s["preparations"]) for s in result["scenes"]], [1, 1, 1])

    def test_inherited_identical_state_reuses_image_without_qwen_task(self):
        previous = self.with_identities()
        variant = next(r for r in previous["references"] if r.get("continuity_state_id"))
        previous = self.image(previous, variant)
        wanted = deepcopy(previous)
        target = next(r for r in wanted["references"] if r.get("continuity_state_id"))
        asset = target["image_asset_id"]; target.update(image_asset_id=None, images=[])
        self.assertEqual(self.service._inherit_state_image(wanted, target, [(1, 0, "now", True, previous)]), 1)
        self.assertEqual(target["image_asset_id"], asset)
        self.assertEqual(self.qwen.queued, [])
        self.assertFalse(continuity.variant_stale(wanted, target))

    def test_http_state_only_batch_accepts_no_krea_profiles_but_regular_reference_still_requires_them(self):
        value = self.with_identities()
        app = FastAPI()
        app.include_router(episodes_router(self.service, serialize_image_project=lambda p: p,
            validate_image=None, image_body=None, render_body=None, serialize_render_project=lambda p: p))
        with TestClient(app) as client:
            variant = next(r for r in value["references"] if r.get("continuity_state_id"))
            body = dict(expected_visual_revision=value["visual_revision"], request_id="state-only-batch",
                        reference_ids=[variant["id"]], profiles={})
            url = f"/api/episodes/{value['episode_id']}/reference-batches"
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()["reference_batch"]["items"][0]["status"], "ready_for_review")
            regular = next(r for r in value["references"] if not r.get("continuity_state_id"))
            response = client.post(url, json={**body, "request_id": "needs-krea-profile", "reference_ids": [regular["id"]]})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.qwen.queued), 1)

    def test_cancellation_uses_the_existing_qwen_queue_and_does_not_restart_on_selection(self):
        value = self.start(self.with_identities())
        identity = value["episode_id"]
        stored = self.service.store.get(identity)
        batch = stored["reference_batch"]; item = batch["items"][0]
        batch["status"] = "rendering"
        stage = self.qwen.projects[item["qwen_project_id"]]["stages"][0]
        stage["attempts"][0]["status"] = "queued"
        self.service.store.save(stored)
        self.service._active_batches.add(identity)
        try:
            self.service.cancel_reference_batch(identity, batch["batch_id"])
        finally:
            self.service._active_batches.discard(identity)
        self.assertEqual(self.qwen.cancelled, [(item["qwen_project_id"], item["qwen_stage_id"], item["attempt_id"])])
        self.service._resume_state_dependencies(identity)
        self.assertEqual(len(self.qwen.queued), 1)

    def test_new_long_stories_opt_in_and_old_story_reads_do_not_migrate(self):
        old = self.stories.create(title="Ancienne histoire")
        self.assertNotIn("visual_state_policy", self.stories.get(old["project_id"]))
        self.stories.long_recipes = LongStoryRecipes(Path(__file__).resolve().parents[1] / "prompt_sources/story.long/2.0.0")
        new = self.stories.create(title="Suite", narrative_format="long", long_options=deepcopy(OPTIONS))
        self.assertEqual(new["visual_state_policy"], 1)
        self.assertNotIn("visual_state_policy", self.stories.get(old["project_id"]))


if __name__ == "__main__":
    unittest.main()
