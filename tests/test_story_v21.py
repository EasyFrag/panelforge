"""User-run V2.1 regressions; fake gateways, no actual models or rendering."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.story_v2 import StoryV2Service, StoryV2Conflict
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.domain.story_v2 import default_settings, validate_script, validate_polish, writing_schema, polish_schema
from panelforge.features.lab.story_v2_web import story_v2_router
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from tests.test_story_v2 import settings, screenplay, Gateway, Production


def dense_settings(mode="manual"):
    return {**settings(mode), "writing_version":"2.1", "duration":16, "scene_duration":8,
            "polish_enabled":True, "final_review_enabled":False}


def line(speaker, text, target):
    return dict(speaker_id=speaker, text=text, delivery="spoken", addressee_ids=[target], address_cue="")


def dense_script():
    s = screenplay()
    s["visual_states"] = []
    for q in s["sequences"]:
        q.update(duration=8, appearances=[], dialogue=[
            line("mia", "Tu restes avec moi ?", "marc"), line("marc", "Oui, je reste.", "mia")])
    return s


def retouch(s):
    result = dict(sequences=[dict(id=q["id"], action=q["action"], dialogue=deepcopy(q["dialogue"])) for q in s["sequences"]])
    result["sequences"][0]["dialogue"] = [line("mia", "Tu restes avec moi ?", "marc"),
        line("marc", "Oui, je reste.", "mia"), line("mia", "Tu es sûr ?", "marc"), line("marc", "Oui, je suis là.", "mia")]
    return result


GOOD = dict(understood="Mia demande du soutien et Marc la rassure.", issues=[])


class StoryV21Test(unittest.TestCase):
    def test_new_default_and_separate_schemas_preserve_legacy_scripts(self):
        self.assertEqual(default_settings()["writing_version"], "2.1")
        legacy = screenplay()
        self.assertEqual(validate_script(legacy, settings()), legacy)
        old_schema = writing_schema(settings())
        self.assertNotIn("visual_states", old_schema["properties"])
        self.assertNotIn("state_id", old_schema["$defs"]["Appearance"]["properties"])
        schema = writing_schema(dense_settings())
        self.assertIn("visual_states", schema["required"])
        self.assertEqual(schema["properties"]["sequences"]["minItems"], 2)
        binding = schema["$defs"]["StateBinding"]
        self.assertEqual(set(binding["properties"]), {"character_id", "state_id"})
        self.assertIn("Dialogue", polish_schema(dense_settings())["$defs"])

    def test_performance_directions_create_no_variants_and_unused_objects_are_removed(self):
        s = dense_script()
        s["sequences"][0]["action"] = "Mia sourit puis parle doucement à Marc qui détourne le regard."
        s["objects"] = [dict(id="phone", name="Téléphone", description="Téléphone ordinaire")]
        parsed = validate_script(s, dense_settings())
        self.assertEqual(parsed["objects"], [])
        self.assertNotIn("visual_states", parsed)
        self.assertTrue(all(q["appearances"] == [] for q in parsed["sequences"]))
        with TemporaryDirectory() as folder:
            store = LocalEpisodeStore(folder)
            adapter = StoryV2Production(NS(store=store), None)
            eid = adapter.export(dict(id="storyv2-"+"1"*32, version=1, settings=dense_settings(), script=parsed, episode_id=None))
            episode = store.get(eid)
            self.assertEqual(len(episode["references"]), 4)  # Three cast members and one location.
            self.assertFalse(any(r.get("story_v2_state") for r in episode["references"]))
            self.assertEqual([q["render_setup"]["settings"]["duration_seconds"] for q in episode["scenes"]], [8,8])
            self.assertTrue(all(not q["preparations"] for q in episode["scenes"]))

    def test_material_state_is_shared_and_return_to_base_is_explicit(self):
        s = dense_script()
        s["visual_states"] = [dict(id="mia-wet", character_id="mia", kind="clothing", description="Robe claire trempée.")]
        for q in s["sequences"]:
            q["appearances"] = [dict(character_id="mia", state_id="mia-wet")]
        third = deepcopy(s["sequences"][-1]);third.update(id="seq-3", appearances=[]);s["sequences"].append(third)
        config = {**dense_settings(), "duration":24}
        parsed = validate_script(s, config)
        self.assertEqual(validate_script(parsed, config), parsed)
        with TemporaryDirectory() as folder:
            store = LocalEpisodeStore(folder);adapter = StoryV2Production(NS(store=store), None)
            project = dict(id="storyv2-"+"2"*32, version=1, settings=config, script=parsed, episode_id=None)
            eid = adapter.export(project);episode = store.get(eid)
            variants = [r for r in episode["references"] if r.get("story_v2_state")]
            self.assertEqual(len(variants), 1)
            ref = variants[0];self.assertEqual(ref["story_v2_state"]["state_id"], "mia-wet")
            for q in episode["scenes"][:2]:
                self.assertIn(ref["id"], [b["reference_id"] for b in q["references"]])
            self.assertIn(ref["story_v2_state"]["base_id"], [b["reference_id"] for b in episode["scenes"][2]["references"]])
            self.assertNotIn(ref["id"], [b["reference_id"] for b in episode["scenes"][2]["references"]])
            self.assertEqual(adapter.export(project), eid)

    def test_base_duplicates_and_duplicate_catalog_entries_do_not_generate_extra_images(self):
        s = dense_script()
        s["visual_states"] = [dict(id="base", character_id="mia", kind="clothing", description=s["characters"][0]["description"]),
            dict(id="wet-one", character_id="marc", kind="clothing", description="Veste bleue trempée."),
            dict(id="wet-two", character_id="marc", kind="clothing", description="  veste bleue trempée  ")]
        for i,q in enumerate(s["sequences"]):
            q["appearances"] = [dict(character_id="mia", state_id="base"), dict(character_id="marc", state_id=["wet-one","wet-two"][i])]
        parsed = validate_script(s, dense_settings())
        self.assertEqual([x["id"] for x in parsed["visual_states"]], ["wet-one"])
        self.assertTrue(all(len(q["appearances"]) == 1 and q["appearances"][0]["state_id"] == "wet-one" for q in parsed["sequences"]))

    def test_reference_contract_rejects_freeform_poses_unknown_states_and_wrong_owners(self):
        for kind in ("emotion", "pose", "voice"):
            s = dense_script();s["visual_states"] = [dict(id="look", character_id="mia", kind=kind, description="Regard fixe")]
            with self.subTest(kind=kind), self.assertRaises(ValueError):validate_script(s, dense_settings())
        for binding in (dict(character_id="mia", state="Sourire forcé"), dict(character_id="mia", state_id="unknown"), dict(character_id="marc", state_id="wet")):
            s = dense_script();s["visual_states"] = [dict(id="wet", character_id="mia", kind="clothing", description="Robe trempée")]
            s["sequences"][0]["appearances"] = [binding]
            with self.subTest(binding=binding), self.assertRaises(ValueError):validate_script(s, dense_settings())

    def test_gemma_can_develop_turns_while_preserving_timing_roles_and_appearance(self):
        source = validate_script(dense_script(), dense_settings());patch = retouch(source)
        out = validate_polish(patch, source, dense_settings())
        self.assertEqual(len(out["sequences"][0]["dialogue"]), 4)
        self.assertEqual(out["sequences"][0]["dialogue"][2]["addressee_ids"], ["marc"])
        frozen = deepcopy(out)
        for old,new in zip(source["sequences"], frozen["sequences"]):new["action"],new["dialogue"] = old["action"],old["dialogue"]
        self.assertEqual(frozen, source)
        self.assertEqual(len(source["sequences"][0]["dialogue"]), 2)
        self.assertEqual([q["duration"] for q in out["sequences"]], [8,8])

    def test_french_punctuation_does_not_reject_a_dense_polish(self):
        config = dense_settings()
        source = validate_script(dense_script(), config)
        patch = retouch(source)
        # Same 14 + 7 + 7 spoken-token distribution as the rejected three-turn scene.
        patch["sequences"][1]["dialogue"] = [
            line("mia", "Nan mais attends... Mama ! T'as un 69 sur le front ? C'est quoi ce délire ?!", "marc"),
            line("marc", "Je vais vraiment crever de honte, là.", "mia"),
            line("mia", "Et alors ? Ça me gêne pas, moi.", "marc")]
        out = validate_polish(patch, source, config)
        self.assertEqual([q["duration"] for q in out["sequences"]], [8,8])
        self.assertEqual([d["text"] for d in out["sequences"][1]["dialogue"]],
                         [d["text"] for d in patch["sequences"][1]["dialogue"]])
        patch["sequences"][1]["dialogue"][-1]["text"] += " Vraiment."
        with self.assertRaisesRegex(ValueError, r"29 mots, limite 28"):
            validate_polish(patch, source, config)

    def test_gemma_rejects_silent_new_speaker_changed_delivery_and_overfull_clip(self):
        source = validate_script(dense_script(), dense_settings())
        patches = []
        p = retouch(source);p["sequences"][1]["dialogue"].append(line("baby", "Bonjour", "mia"));patches.append(p)
        p = retouch(source);p["sequences"][0]["dialogue"][0]["delivery"] = "voice_over";patches.append(p)
        p = retouch(source);p["sequences"][0]["dialogue"][0]["text"] = "mot " * 35;patches.append(p)
        p = retouch(source);p["sequences"][0]["dialogue"][0]["addressee_ids"] = ["unknown"];patches.append(p)
        p = retouch(source);p["sequences"].reverse();patches.append(p)
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ValueError):validate_polish(patch, source, dense_settings())

    def test_dense_automatic_cycle_keeps_three_calls_and_stops_in_preparation(self):
        with TemporaryDirectory() as folder:
            store = LocalStoryV2Store(folder);source = dense_script()
            gateway = Gateway([source, GOOD, retouch(source)]);production = Production()
            service = StoryV2Service(store, gateway, production)
            p = service.create("dense-cycle-001", dense_settings("automatic"));service.tick(p["id"])
            out = store.get(p["id"])
            self.assertEqual(out["status"], "references", out.get("error"))
            self.assertEqual(out["scenario"]["writing_version"], "2.1")
            self.assertEqual([r.operation_id for r in gateway.requests], ["story.v2.write@2.1.0","story.v2.review@2.1.0","story.v2.polish@2.1.0"])
            self.assertTrue(all(c["writing_version"] == "2.1" for c in out["calls"]))
            self.assertEqual([c["total"] for c in out["calls"]], [3,3,3])
            self.assertEqual(len(out["history"]), 2)
            self.assertEqual(len(out["history"][0]["script"]["sequences"][0]["dialogue"]), 2)
            self.assertEqual(len(out["script"]["sequences"][0]["dialogue"]), 4)
            production.ready=True;production.episode["reference_batch"]={"status":"completed"};service.tick(p["id"])
            out=store.get(p["id"]);self.assertEqual(out["status"], "prepared")
            self.assertFalse(production.launched);self.assertEqual(len(gateway.requests), 3)
            service.restore(p["id"],out["version"],0)
            restored=store.get(p["id"])
            self.assertEqual(restored["settings"]["writing_version"], "2.1")
            self.assertEqual(len(restored["script"]["sequences"][0]["dialogue"]), 2)

    def test_optional_final_control_blocks_automatic_references_when_it_finds_an_issue(self):
        with TemporaryDirectory() as folder:
            store=LocalStoryV2Store(folder);source=dense_script();production=Production()
            bad=dict(understood="Un échange reste ambigu.",issues=["La conséquence de la révélation reste inexpliquée."])
            gateway=Gateway([source,GOOD,retouch(source),bad]);service=StoryV2Service(store,gateway,production)
            p=service.create("dense-final-control",{**dense_settings("automatic"),"final_review_enabled":True})
            service.tick(p["id"]);out=store.get(p["id"])
            self.assertEqual(out["status"],"awaiting_review",out.get("error"))
            self.assertEqual(out["review"]["issues"],bad["issues"])
            self.assertEqual([c["step"] for c in out["calls"]],["write","review","polish","final_review"])
            evidence=json.loads(gateway.requests[-1].user_prompt)
            self.assertEqual(len(evidence["pre_polish_scenes"][0]["dialogue"]),2)
            self.assertFalse(production.exported or production.started)

    def test_failed_dense_retouch_resumes_same_version_without_rewriting(self):
        with TemporaryDirectory() as folder:
            store=LocalStoryV2Store(folder);source=dense_script();production=Production()
            invalid=retouch(source);invalid["sequences"][0]["dialogue"][0]["speaker_id"]="baby"
            gateway=Gateway([source,GOOD,invalid,retouch(source)]);service=StoryV2Service(store,gateway,production)
            p=service.create("dense-resume-001",dense_settings());service.tick(p["id"])
            out=store.get(p["id"])
            self.assertEqual(out["status"],"failed")
            self.assertEqual(len(out["script"]["sequences"][0]["dialogue"]),2)
            self.assertFalse(production.exported)
            service.resume(p["id"],out["version"]);service.tick(p["id"]);out=store.get(p["id"])
            self.assertEqual(out["status"],"awaiting_review",out.get("error"))
            self.assertEqual([c["step"] for c in out["calls"]],["write","review","polish","polish"])
            self.assertTrue(all(r.operation_id.endswith("@2.1.0") for r in gateway.requests))
            self.assertEqual(len(out["script"]["sequences"][0]["dialogue"]),4)

    def test_old_pending_cycle_and_episode_identity_survive_loading(self):
        with TemporaryDirectory() as folder:
            store=LocalStoryV2Store(folder);gateway=Gateway([screenplay(),GOOD]);production=Production()
            service=StoryV2Service(store,gateway,production);p=service.create("legacy-cycle-001",settings())
            p["settings"].pop("writing_version");p["scenario"].pop("writing_version");store.save(p)
            original=store.get(p["id"])
            loaded=service.get(p["id"])
            self.assertEqual(loaded["settings"]["writing_version"], "2.0")
            self.assertEqual(store.get(p["id"]), original)
            self.assertEqual(service.preferences()["writing_version"], "2.1")
            episode_store=LocalEpisodeStore(folder);adapter=StoryV2Production(NS(store=episode_store),None)
            base=dict(id=p["id"],version=1,script=screenplay(),settings=p["settings"],episode_id=None)
            self.assertEqual(adapter.export(base), adapter.export({**base,"settings":loaded["settings"]}))
            service.tick(p["id"]);out=store.get(p["id"])
            self.assertEqual(out["status"], "awaiting_review",out.get("error"))
            self.assertTrue(all(r.operation_id.endswith("@1.2.0") for r in gateway.requests))
            with self.assertRaises(StoryV2Conflict):service.update(p["id"],out["version"],out["script"],{**out["settings"],"writing_version":"2.1"})

    def test_http_new_default_and_legacy_client_update_are_distinct(self):
        with TemporaryDirectory() as folder:
            store=LocalStoryV2Store(folder);service=StoryV2Service(store,Gateway([]),Production())
            app=FastAPI();app.include_router(story_v2_router(service));client=TestClient(app)
            raw=settings();raw.pop("writing_version")
            response=client.post("/api/stories-v2/projects",json=dict(command="default-version-001",settings=raw))
            self.assertEqual(response.status_code,202,response.text)
            self.assertEqual(response.json()["project"]["settings"]["writing_version"],"2.1")
            old=service.create("old-command-001",settings());old["settings"].pop("writing_version");old.update(status="draft");store.save(old)
            response=client.put("/api/stories-v2/projects/"+old["id"],json=dict(version=old["version"],settings=raw,script=None))
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["project"]["settings"]["writing_version"],"2.0")
            repeat=service.create("old-command-001",raw)
            self.assertEqual(repeat["id"],old["id"])


if __name__ == "__main__":
    unittest.main()
