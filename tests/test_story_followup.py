"""User-run sequel preparation regressions. Fake gateway, temporary storage only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.stories import StoryService, StoryConflict
from panelforge.domain import long_stories as narrative
from panelforge.domain import story_followup as contract
from panelforge.features.lab.stories_web import stories_router
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore
from tests.test_stories import Gateway, SCENARIO

ROOT = Path(__file__).resolve().parents[1]
DIRECTION = dict(start="Citronito garde la preuve.", beats="Il demande les autres colis.\nPechetta refuse.\nIl ouvre le placard.",
                 ending="Les colis sont retrouvés.", constraints="Ne pas ajouter de nouveau personnage.")


class StoryFollowupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gateway = Gateway()
        self.addCleanup(self.gateway.release.set)
        self.store = LocalStoryStore(self.temp.name)
        self.recipes = LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0")
        self.long_recipes = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0")
        self.service = self.make_service()
        self.followups = self.service.followups

    def make_service(self):
        return StoryService(gateway=self.gateway, store=self.store, recipes=self.recipes, long_recipes=self.long_recipes)

    def parent(self, *, long=False, units=1):
        args = dict(title="La preuve", scene_count=1, clip_seconds=10,
                    architect_model_id="local::fixture", writer_model_id="local::fixture")
        if long:
            args.update(narrative_format="long", target_seconds=units * 10, workflow_mode="manual",
                        long_options=dict(profile="suspense", narration="dialogue", delivery="serial", unit_count=units, ending_type="open"))
        project = self.service.create(**args)
        scenario = deepcopy(SCENARIO["scenario"])
        scenario["visual_continuity"] = dict(version=1, dramatic_summary="Citronito a changé.", elements=[dict(
            id="c2", kind="character", name="Citronito", description="Citron", reason="Transformation acquise",
            tracking="text", scene_indices=[0], states=[dict(id="muscles", scene_index=0, at="end",
                appearance="Corps musclé", clothing="Veste bleue", holder_id=None, reference=False)])])
        project["document"]["scenario"] = scenario
        if long:
            outline = narrative.outline_example(project)["series_outline"]
            outline["characters"] = deepcopy(scenario["characters"])
            project["document"].update(series_outline=outline, selected_episode_id="episode-1",
                episode_scenarios={"episode-1": scenario},
                episode_formats={f"episode-{i}": dict(scene_count=1, clip_seconds=10) for i in range(1, units + 1)})
            example = deepcopy(project)
            example["job"] = dict(operation="develop")
            project["document"]["episode_states"] = {"episode-1": narrative.episode_example(example)["episode_state"]}
            project["document"]["episode_provenance"] = {"episode-1": narrative.dependency_hash(project, "episode-1")}
        return self.store.save(project)

    def open(self, parent):
        return self.followups.open(parent["project_id"], expected_version=parent["version"])

    def edit(self, draft, direction=None):
        return self.followups.update(draft["id"], expected_revision=draft["revision"],
            direction=direction or DIRECTION, model_id="local::fixture", settings=draft["settings"])

    def wait(self, identity):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with self.service._lock:
                if identity not in self.followups._active:
                    return self.followups.get(identity)
            sleep(.005)
        self.fail("Le worker fictif ne s’est pas terminé.")

    def chat(self, draft, response, *, automatic=False, instruction="Et ensuite ?", request_id="request-fixture-1"):
        self.gateway.response = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        self.followups.start(draft["id"], expected_revision=draft["revision"], instruction=instruction,
                             automatic=automatic, request_id=request_id)
        return self.wait(draft["id"])

    def test_open_is_saved_without_llm_or_parent_changes(self):
        parent = self.parent()
        before = self.store._path(parent["project_id"]).read_bytes()
        draft = self.open(parent)
        self.assertEqual([], self.gateway.requests)
        self.assertEqual(before, self.store._path(parent["project_id"]).read_bytes())
        self.assertEqual("Corps musclé", draft["context"]["visual_state"]["elements"][0]["states"][0]["appearance"])
        self.assertEqual(draft["id"], self.open(parent)["id"])

    def test_direction_and_model_survive_reopening_and_service_restart(self):
        draft = self.edit(self.open(self.parent()))
        reopened = self.make_service().followups.get(draft["id"])
        self.assertEqual(DIRECTION, reopened["direction"])
        self.assertEqual("local::fixture", reopened["model_id"])
        self.assertEqual([], reopened["turns"])
        self.assertEqual([], self.gateway.requests)

    def test_question_preserves_direction_and_parent(self):
        parent = self.parent()
        draft = self.edit(self.open(parent))
        result = self.chat(draft, dict(reply="Il connaît déjà le vol.", direction=None))
        self.assertEqual("succeeded", result["job"]["status"])
        self.assertEqual(DIRECTION, result["direction"])
        self.assertEqual(parent["version"], self.store.get(parent["project_id"])["version"])
        self.assertEqual(1, len(self.gateway.requests))
        self.assertEqual("local::fixture", self.gateway.requests[0].model_id)

    def test_automatic_proposal_uses_one_call_and_sees_manual_direction(self):
        draft = self.edit(self.open(self.parent()))
        updated = {**DIRECTION, "ending": "Pechetta rend le colis."}
        result = self.chat(draft, dict(reply="Voici une piste.", direction=updated), automatic=True, instruction="")
        self.assertEqual(updated, result["direction"])
        self.assertEqual(1, len(self.gateway.requests))
        payload = json.loads(self.gateway.requests[0].user_prompt)
        self.assertEqual(DIRECTION, payload["direction"])
        self.assertIsNotNone(self.gateway.requests[0].output_schema)
        self.assertFalse(self.gateway.requests[0].include_reasoning)

    def test_bad_response_keeps_raw_and_last_direction_without_retry(self):
        draft = self.edit(self.open(self.parent()))
        result = self.chat(draft, '{"reply": "réponse coupée')
        self.assertEqual("failed", result["job"]["status"])
        self.assertIn("réponse coupée", result["job"]["draft"])
        self.assertEqual(DIRECTION, result["direction"])
        self.assertEqual(1, len(self.gateway.requests))

    def test_duplicate_chat_request_does_not_call_again(self):
        draft = self.edit(self.open(self.parent()))
        result = self.chat(draft, dict(reply="Une réponse.", direction=None))
        again = self.followups.start(draft["id"], expected_revision=draft["revision"], instruction="Et ensuite ?",
                                     automatic=False, request_id="request-fixture-1")
        self.assertEqual(result["turns"], again["turns"])
        self.assertEqual(1, len(self.gateway.requests))
        with self.assertRaises(StoryConflict):
            self.followups.start(draft["id"], expected_revision=again["revision"], instruction="Autre message",
                                 automatic=False, request_id="request-fixture-1")

    def test_truncation_preserves_the_previous_direction(self):
        draft = self.edit(self.open(self.parent()))
        self.gateway.truncated = True
        result = self.chat(draft, dict(reply="Une réponse.", direction=DIRECTION))
        self.assertEqual("failed", result["job"]["status"])
        self.assertEqual(DIRECTION, result["direction"])
        self.assertEqual(1, len(self.gateway.requests))

    def test_cancel_and_restart_keep_work(self):
        draft = self.edit(self.open(self.parent()))
        self.gateway.release.clear()
        self.gateway.response = json.dumps(dict(reply="Terminé.", direction=None))
        self.followups.start(draft["id"], expected_revision=draft["revision"], instruction="Une idée ?",
                             automatic=False, request_id="cancel-fixture")
        self.assertTrue(self.gateway.entered.wait(2))
        self.followups.cancel(draft["id"])
        self.gateway.release.set()
        result = self.wait(draft["id"])
        self.assertEqual("cancelled", result["job"]["status"])
        self.assertEqual(DIRECTION, result["direction"])
        result["job"]["status"] = "running"
        self.store.save_followup(result)
        recovered = self.make_service().followups.get(result["id"])
        self.assertEqual("interrupted", recovered["job"]["status"])
        self.assertEqual(DIRECTION, recovered["direction"])

    def test_source_change_blocks_commit_then_refresh_keeps_choices(self):
        parent = self.parent()
        draft = self.edit(self.open(parent))
        parent["document"]["scenario"]["scenes"][0]["ending_state"] = "Pechetta reprend la preuve."
        self.store.save(parent)
        self.assertTrue(self.followups.get(draft["id"])["source_changed"])
        with self.assertRaises(StoryConflict):
            self.followups.commit(draft["id"], expected_revision=draft["revision"])
        refreshed = self.followups.refresh(draft["id"], expected_revision=draft["revision"])
        self.assertFalse(refreshed["source_changed"])
        self.assertEqual(DIRECTION, refreshed["direction"])
        self.assertEqual("Pechetta reprend la preuve.", refreshed["context"]["latest_scenario"]["scenes"][0]["ending_state"])

    def test_commit_creates_one_child_from_validated_direction(self):
        parent = self.parent(long=True)
        before = self.store._path(parent["project_id"]).read_bytes()
        draft = self.edit(self.open(parent))
        with patch.object(self.service.workflow, "advance", side_effect=lambda identity, *args, **kw: self.service.get(identity)) as advance:
            first = self.followups.commit(draft["id"], expected_revision=draft["revision"])
            second = self.followups.commit(draft["id"], expected_revision=draft["revision"])
        self.assertEqual(first["project"]["project_id"], second["project"]["project_id"])
        self.assertEqual(1, advance.call_count)
        self.assertEqual(2, len(self.store.list()))
        child = first["project"]
        self.assertEqual(parent["project_id"], child["parent_story_id"])
        self.assertEqual(contract.brief(DIRECTION), child["brief"])
        self.assertEqual(parent["document"]["scenario"], child["document"]["prior_story_snapshot"])
        self.assertEqual(1, child["long_options"]["unit_count"])
        self.assertIsNone(child["document"]["scenario"])
        self.assertEqual(before, self.store._path(parent["project_id"]).read_bytes())

    def test_planned_episode_uses_existing_story_and_preserves_prior_episode(self):
        parent = self.parent(long=True, units=2)
        original = deepcopy(parent["document"]["episode_scenarios"]["episode-1"])
        old_hash = narrative.dependency_hash(parent, "episode-1")
        draft = self.edit(self.open(parent))
        with patch.object(self.service.workflow, "advance", side_effect=lambda identity, *args, **kw: self.service.get(identity)) as advance:
            result = self.followups.commit(draft["id"], expected_revision=draft["revision"])
        project = result["project"]
        self.assertEqual(parent["project_id"], project["project_id"])
        self.assertEqual("episode-2", project["document"]["selected_episode_id"])
        self.assertEqual(original, project["document"]["episode_scenarios"]["episode-1"])
        self.assertEqual(old_hash, narrative.dependency_hash(project, "episode-1"))
        self.assertEqual(parent["document"]["series_outline"], project["document"]["series_outline"])
        self.assertEqual(contract.brief(DIRECTION), project["document"]["continuation_directions"]["episode-2"]["brief"])
        self.assertEqual(1, advance.call_count)
        project["job"] = dict(operation="develop", instruction="", request_id="writer-check")
        project["model_id"] = "local::fixture"
        request = self.service._request(project, self.long_recipes.snapshot())
        self.assertEqual(contract.brief(DIRECTION), json.loads(request.user_prompt)["author_episode_directions"]["episode-2"])

    def test_future_written_scenes_are_not_past_facts_and_existing_next_is_opened(self):
        parent = self.parent(long=True, units=2)
        later = deepcopy(SCENARIO["scenario"])
        later["scenes"][0]["action"] = "FUTURE_ACTION_MARKER"
        parent["document"]["episode_scenarios"]["episode-2"] = later
        parent = self.store.save(parent)
        draft = self.open(parent)
        self.assertTrue(draft["context"]["next_written"])
        self.assertNotIn("FUTURE_ACTION_MARKER", json.dumps(draft["context"]["written_episodes"]))
        self.assertEqual(["episode-1"], [u["unit_id"] for u in draft["context"]["written_episodes"]])
        with patch.object(self.service.workflow, "advance") as advance, patch.object(self.service, "start") as start:
            result = self.followups.commit(draft["id"], expected_revision=draft["revision"])
        self.assertEqual(later, result["project"]["document"]["scenario"])
        advance.assert_not_called(); start.assert_not_called()

    def test_crash_between_saves_recovers_same_child_without_launching_again(self):
        parent = self.parent(long=True)
        draft = self.edit(self.open(parent))
        save = self.store.save_followup
        def fail_destination_record(value):
            if value.get("result"):
                raise OSError("Simulated interruption after child save")
            return save(value)
        with patch.object(self.store, "save_followup", side_effect=fail_destination_record):
            with self.assertRaises(OSError):
                self.followups.commit(draft["id"], expected_revision=draft["revision"])
        self.assertEqual(2, len(self.store.list()))
        with patch.object(self.service.workflow, "advance") as advance:
            recovered = self.followups.commit(draft["id"], expected_revision=draft["revision"])
        advance.assert_not_called()
        self.assertEqual(2, len(self.store.list()))
        self.assertIn("interruption", recovered["draft"]["result"]["notice"])

    def test_revision_conflict_preserves_first_edit(self):
        draft = self.open(self.parent())
        saved = self.edit(draft)
        with self.assertRaises(StoryConflict):
            self.edit(draft, {**DIRECTION, "ending": "Autre fin"})
        self.assertEqual(saved["direction"], self.followups.get(draft["id"])["direction"])

    def test_api_open_save_and_missing_storage(self):
        parent = self.parent()
        app = FastAPI(); app.include_router(stories_router(self.service))
        with TestClient(app) as client:
            opened = client.post(f"/api/stories/projects/{parent['project_id']}/followup", json={"expected_version": parent["version"]})
            self.assertEqual(200, opened.status_code, opened.text)
            draft = opened.json()
            saved = client.put(f"/api/stories/followups/{draft['id']}", json=dict(expected_revision=draft["revision"],
                direction=DIRECTION, model_id="local::fixture", settings=draft["settings"]))
            self.assertEqual(200, saved.status_code, saved.text)
            self.assertEqual(422, client.post(f"/api/stories/followups/{draft['id']}/commit", json={"expected_revision": True}).status_code)
            missing = client.get("/api/stories/followups/followup-" + "a" * 32)
            self.assertEqual(404, missing.status_code)
        self.assertEqual([], self.gateway.requests)


if __name__ == "__main__":
    unittest.main()
