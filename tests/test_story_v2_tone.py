"""User-run tone regressions: fake gateways and temporary stores, no real generations."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application import story_v2_prompting as prompts, story_v21_prompting as dense_prompts
from panelforge.application.story_v2 import StoryV2Service
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.domain.story_v2 import Settings, default_settings
from panelforge.features.lab.story_v2_web import story_v2_router
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from tests.test_story_v2 import Gateway, Production, screenplay, settings
from tests.test_story_v21 import dense_settings, dense_script, retouch, GOOD


SKETCH = "provocative_sketch"


class StoryV2ToneTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalStoryV2Store(self.temp.name)
        self.gateway, self.production = Gateway([]), Production()
        self.service = StoryV2Service(self.store, self.gateway, self.production)

    def test_default_keeps_original_prompts_and_unknown_profile_is_rejected(self):
        self.assertEqual(default_settings()["tone_profile"], "from_idea")
        for version, source in (("2.0", prompts), ("2.1", dense_prompts)):
            with self.subTest(version=version):
                original = dict(version=source.VERSION, write=source.WRITER, repair=source.WRITER,
                                review=source.READER, polish=source.POLISH)
                self.assertEqual(prompts.for_version(version), original)
                self.assertEqual(prompts.for_version(version, "from_idea"), original)
                with self.assertRaises(ValueError): prompts.for_version(version, "unknown")
        with self.assertRaises(ValueError): Settings.model_validate({**settings(), "tone_profile":"unknown"})

    def test_full_cycle_keeps_five_call_limit_and_tone_in_repair_polish_and_final_review(self):
        for version in ("2.0", "2.1"):
            with self.subTest(version=version):
                source = screenplay() if version == "2.0" else dense_script()
                polished = (dict(sequences=[dict(id=q["id"], action=q["action"],
                    dialogue=[d["text"] for d in q["dialogue"]]) for q in source["sequences"]])
                    if version == "2.0" else retouch(source))
                config = settings() if version == "2.0" else dense_settings()
                config.update(tone_profile=SKETCH, mode="automatic", polish_enabled=True,
                              final_review_enabled=True, writer_model="author", reader_model="reader", polish_model="prose")
                gateway = Gateway([source, dict(understood="Une scène manque de clarté.", issues=["Clarifier la réaction."]),
                                   source, polished, GOOD])
                production = Production()
                service = StoryV2Service(self.store, gateway, production)
                p = service.create("tone-cycle-"+version, config)
                service.tick(p["id"])
                out = self.store.get(p["id"])
                self.assertEqual(out["status"], "references", out.get("error"))
                self.assertEqual([c["step"] for c in out["calls"]], ["write", "review", "repair", "polish", "final_review"])
                self.assertEqual([r.model_id for r in gateway.requests], ["author", "reader", "author", "prose", "reader"])
                recipe = prompts.for_version(version, SKETCH)
                for call, request in zip(out["calls"], gateway.requests):
                    self.assertEqual(call["tone_profile"], SKETCH)
                    self.assertEqual(request.system_prompt, recipe[call["role"]])
                    self.assertEqual(json.loads(request.user_prompt)["brief"]["tone_profile"], SKETCH)
                    self.assertTrue(request.operation_id.endswith("+sketch-1.0.0"))
                self.assertEqual([q["duration"] for q in out["script"]["sequences"]], [q["duration"] for q in source["sequences"]])
                self.assertEqual(out["settings"]["video"], config["video"])
                self.assertEqual(out["settings"]["images"], config["images"])
                self.assertEqual(len(production.started), 1)
                production.ready = True
                service.tick(p["id"])
                self.assertEqual(self.store.get(p["id"])["status"], "prepared")
                self.assertEqual(len(gateway.requests), 5)
                self.assertFalse(production.launched)

    def test_no_final_control_still_uses_three_calls_and_persists_last_choice(self):
        config = {**dense_settings(), "tone_profile":SKETCH}
        self.gateway.values = [dense_script(), GOOD, retouch(dense_script())]
        p = self.service.create("tone-three-calls", config)
        self.service.tick(p["id"])
        out = self.store.get(p["id"])
        self.assertEqual(out["status"], "awaiting_review", out.get("error"))
        self.assertEqual([c["step"] for c in out["calls"]], ["write", "review", "polish"])
        fresh = StoryV2Service(LocalStoryV2Store(self.temp.name), Gateway([]), Production())
        self.assertEqual(fresh.preferences()["tone_profile"], SKETCH)
        self.assertEqual(fresh.preferences()["idea"], "")
        self.assertEqual(fresh.get(p["id"])["settings"]["tone_profile"], SKETCH)

    def test_old_story_ignores_remembered_sketch_without_migrating_on_read(self):
        config = settings()
        p = self.service.create("tone-legacy-story", config)
        p["settings"].pop("tone_profile")
        p["scenario"].pop("tone_profile")
        self.store.save(p)
        self.store.save_preferences({**config, "tone_profile":SKETCH})
        public = self.service.get(p["id"])
        self.assertEqual(public["settings"]["tone_profile"], "from_idea")
        self.assertNotIn("tone_profile", self.store.get(p["id"])["settings"])
        self.gateway.values = [screenplay(), GOOD]
        self.service.tick(p["id"])
        out = self.store.get(p["id"])
        self.assertEqual(out["status"], "awaiting_review", out.get("error"))
        self.assertEqual(self.gateway.requests[0].system_prompt, prompts.WRITER)
        self.assertNotIn("tone_profile", json.loads(self.gateway.requests[0].user_prompt)["brief"])
        self.assertEqual(self.service.preferences()["tone_profile"], SKETCH)

    def test_http_omitted_tone_preserves_existing_choice_for_retry_and_update(self):
        app = FastAPI(); app.include_router(story_v2_router(self.service))
        client = TestClient(app)
        config = {**dense_settings(), "tone_profile":SKETCH, "polish_enabled":False}
        body = dict(command="tone-http-command", settings=config)
        response = client.post("/api/stories-v2/projects", json=body)
        self.assertEqual(response.status_code, 202, response.text)
        identity = response.json()["project"]["id"]
        old_client = deepcopy(body);old_client["settings"].pop("tone_profile")
        replay = client.post("/api/stories-v2/projects", json=old_client)
        self.assertEqual(replay.status_code, 202, replay.text)
        self.assertEqual(replay.json()["project"]["settings"]["tone_profile"], SKETCH)
        different = deepcopy(body);different["settings"]["tone_profile"] = "from_idea"
        self.assertEqual(client.post("/api/stories-v2/projects", json=different).status_code, 409)
        self.gateway.values = [dense_script(), GOOD]
        self.service.tick(identity)
        p = self.store.get(identity)
        update = dict(version=p["version"], settings=old_client["settings"], script=p["script"])
        saved = client.put("/api/stories-v2/projects/"+identity, json=update)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["project"]["settings"]["tone_profile"], SKETCH)
        invalid = deepcopy(body);invalid["command"] = "tone-http-invalid";invalid["settings"]["tone_profile"] = "unknown"
        self.assertEqual(client.post("/api/stories-v2/projects", json=invalid).status_code, 422)

    def test_restore_legacy_history_does_not_inherit_current_tone(self):
        for missing_settings in (False, True):
            with self.subTest(missing_settings=missing_settings):
                config = {**dense_settings(), "polish_enabled":False}
                self.gateway.values = [dense_script(), GOOD]
                p = self.service.create("tone-restore-"+str(missing_settings), config)
                self.service.tick(p["id"])
                p = self.store.get(p["id"])
                p = self.service.update(p["id"], p["version"], p["script"], {**config, "tone_profile":SKETCH})
                if missing_settings:
                    p["history"][0].pop("settings")
                else:
                    p["history"][0]["settings"].pop("tone_profile")
                self.store.save(p)
                restored = self.service.restore(p["id"], p["version"], 0)
                self.assertEqual(restored["settings"]["tone_profile"], "from_idea")
                self.assertEqual(self.service.preferences()["tone_profile"], "from_idea")

    def test_neutral_and_selected_tone_do_not_recreate_production_for_unchanged_script(self):
        episodes = LocalEpisodeStore(self.temp.name)
        adapter = StoryV2Production(NS(store=episodes), None)
        for version in ("2.0", "2.1"):
            with self.subTest(version=version):
                config = settings() if version == "2.0" else dense_settings()
                config.pop("tone_profile")
                source = screenplay() if version == "2.0" else dense_script()
                project = dict(id="storyv2-"+("a" if version == "2.0" else "b")*32,
                               version=1, settings=config, script=source, episode_id=None)
                identity = adapter.export(project)
                before = episodes.get(identity)
                for tone in ("from_idea", SKETCH):
                    project["settings"]["tone_profile"] = tone
                    self.assertEqual(adapter.export(project), identity)
                    self.assertEqual(episodes.get(identity), before)


if __name__ == "__main__":
    unittest.main()
