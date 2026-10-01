"""User-run regressions: fake LLM/production, temporary stores, no real generations."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.domain.story_v2 import Settings, Script, audience_view, digest, validate_script
from panelforge.domain.episodes import scene_inputs
from panelforge.application.story_v2 import StoryV2Service, StoryV2Conflict
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.application.prompt_lab import StreamEventKind, CompletionResult
from panelforge.features.lab.story_v2_web import story_v2_router
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore


def settings(mode="manual"):
    return Settings(idea="Un couple prépare une naissance puis accueille son bébé.", universe="Humains adultes", style="Cinéma réaliste", duration=20, mode=mode, image_model="fake-image").model_dump()


def screenplay():
    return dict(title="La naissance", summary=["Un couple attend son bébé.", "Ils l'accueillent ensemble."],
        characters=[dict(id="mia", name="Mia", description="Adulte aux cheveux bruns, robe claire", relationship="Compagne de Marc"),
                    dict(id="marc", name="Marc", description="Adulte aux cheveux courts, veste bleue", relationship="Compagnon de Mia"),
                    dict(id="baby", name="Le bébé", description="Nouveau-né emmailloté", relationship="Enfant du couple")],
        locations=[dict(id="room", name="Chambre", description="Chambre familiale claire")], objects=[],
        sequences=[dict(id="seq-1",title="L'attente",setting="À la maison, avant la naissance",action="Mia montre son ventre à Marc qui lui prend la main.",intention="Mia cherche à partager sa joie et Marc veut la rassurer.",duration=10,location_id="room",character_ids=["mia","marc"],object_ids=[],appearances=[dict(character_id="mia",state="Ventre de grossesse avancée")],dialogue=[dict(speaker_id="mia",text="Notre bébé va bientôt naître.",delivery="spoken")]),
                   dict(id="seq-2",title="Bienvenue",setting="Après la naissance",action="Mia et Marc accueillent leur nouveau-né dans leurs bras.",intention="Ils veulent souhaiter la bienvenue à leur enfant.",duration=10,location_id="room",character_ids=["mia","marc","baby"],object_ids=[],appearances=[dict(character_id="mia",state="Après l'accouchement, robe ample")],dialogue=[dict(speaker_id="marc",text="Bienvenue à la maison, mon fils.",delivery="spoken")])])


class Gateway:
    def __init__(self, values): self.values=list(values); self.requests=[]; self.hook=None; self.truncated=False
    def stream(self, request):
        self.requests.append(request)
        if self.hook: self.hook()
        value=self.values.pop(0)
        yield NS(kind=StreamEventKind.TRUNCATED if self.truncated else StreamEventKind.COMPLETED,
                 text="",result=CompletionResult(model_id=request.model_id,content=json.dumps(value),call_id="fake-call"))

class Production:
    def __init__(self):
        self.exported=[]; self.started=[]; self.sent=[]; self.launched=[]; self.ready=False; self.rows=[]
        self.episode=dict(episode_id="episode-fake",references=[dict(id="character-1",image_asset_id=None)],reference_batch=None)
        self.episodes=NS(get=lambda _:deepcopy(self.episode))
        self.factory=NS(receive=self.receive)
    def export(self,p): self.exported.append(digest(p["script"]));return self.episode["episode_id"]
    def start_references(self,p,ids=None,request_id=None,*,retry_thumbnail=False,resume=False):
        self.started.append(request_id);self.episode["reference_batch"]={"status":"running"}
        self.episode["story_v2_selection"]={"ids":["character-1"],"request_id":request_id}
    def advance_images(self,p,automatic=False):
        if self.ready:self.episode["story_v2_thumbnail"]={"image_asset_id":"asset-thumbnail"}
        return False
    def references(self,p,automatic=False): return self.ready
    def send(self,p): self.sent.append(p["id"]);return [dict(name="Clip",config={})]
    def receive(self,entries):
        if not self.rows:self.rows=[dict(id="factory-1",status="preparation")]
        return dict(ids=["factory-1"],added=1)
    def launch(self,ids):
        for r in self.rows:
            if r["status"]=="preparation":r["status"]="queued";self.launched.append(r["id"])
    def results(self,p):return deepcopy(self.rows)

class StoryV2Test(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=LocalStoryV2Store(self.temp.name)
        self.gateway=Gateway([screenplay(),dict(understood="Le couple accueille son enfant.",issues=[])])
        self.production=Production();self.service=StoryV2Service(self.store,self.gateway,self.production)
    def create(self,mode="manual",*,final_review=False):
        self.project=self.service.create("command-12345678",{**settings(mode), "final_review_enabled":final_review});return self.project
    def latest(self):return self.store.get(self.project["id"])
    def tick(self):self.service.tick(self.project["id"])

    def test_manual_stops_with_compact_script_before_any_images(self):
        self.create();self.tick();p=self.latest()
        self.assertEqual(p["status"],"awaiting_review")
        self.assertEqual(len(p["script"]["summary"]),2)
        self.assertFalse(self.production.exported or self.production.started)
        self.assertEqual([r.operation_id for r in self.gateway.requests],["story.v2.write@1.2.0","story.v2.review@1.2.0"])
        self.service.approve(p["id"],p["version"])
        self.assertEqual(self.latest()["status"],"references_ready")
        self.assertFalse(self.production.started)

    def test_automatic_stops_in_preparation_without_launching_factory(self):
        self.create("automatic");self.tick()
        self.assertEqual(self.latest()["status"],"references")
        self.assertEqual(len(self.production.started),1)
        self.production.ready=True;self.production.episode["reference_batch"]={"status":"completed"}
        self.tick();self.tick()
        self.assertEqual(self.production.launched,[])
        self.assertEqual(self.production.rows[0]["status"],"preparation")
        self.assertEqual(self.latest()["status"],"prepared")
        self.assertEqual(len(self.production.sent),1)
        self.assertEqual(len(self.gateway.requests),2)

    def test_create_command_is_idempotent_and_rejects_changed_payload(self):
        p=self.create();self.assertEqual(self.service.create("command-12345678",settings())["id"],p["id"])
        with self.assertRaises(StoryV2Conflict):self.service.create("command-12345678",{**settings(),"idea":"Une autre histoire"})
        self.assertEqual(len(self.store.list()),1)

    def test_reader_gets_played_scene_without_author_intention_or_setting(self):
        self.create();self.tick();payload=json.loads(self.gateway.requests[1].user_prompt)
        self.assertNotIn("summary",payload)
        self.assertNotIn("intention",payload["scenes"][0])
        self.assertNotIn("situation",payload["scenes"][0])
        self.assertIn("visible",payload["scenes"][0])

    def test_repair_is_bounded_and_unresolved_story_never_auto_produces(self):
        bad=dict(understood="Le bébé apparaît sans préparation.",issues=["Introduire la naissance dans une réplique."])
        self.gateway.values=[screenplay(),bad,screenplay(),bad]
        self.create("automatic",final_review=True);self.tick()
        self.assertEqual(len(self.gateway.requests),4)
        self.assertEqual(self.latest()["status"],"awaiting_review")
        self.assertFalse(self.production.exported)

    def test_pause_after_writing_keeps_script_and_resume_only_reviews(self):
        self.create();self.gateway.hook=lambda:self.service.pause(self.project["id"])
        self.tick();p=self.latest()
        self.assertEqual(p["status"],"paused");self.assertIsNotNone(p["script"])
        self.gateway.hook=None;self.service.resume(p["id"],p["version"]);self.tick()
        self.assertEqual(len(self.gateway.requests),2)
        self.assertEqual(self.latest()["status"],"awaiting_review")

    def test_pause_after_reader_before_auto_export_can_resume(self):
        self.create("automatic")
        self.gateway.hook=lambda:self.service.pause(self.project["id"]) if len(self.gateway.requests)==2 else None
        self.tick();p=self.latest();self.assertEqual(p["status"],"paused")
        self.assertIsNone(p["episode_id"])
        self.gateway.hook=None;self.service.resume(p["id"],p["version"]);self.tick()
        self.assertTrue(self.production.exported);self.assertTrue(self.production.started)
        self.assertEqual(len(self.gateway.requests),2)

    def test_truncation_keeps_raw_and_cannot_be_approved(self):
        self.gateway.truncated=True;self.create();self.tick();p=self.latest()
        self.assertEqual(p["status"],"failed");self.assertTrue(p["raw"])
        with self.assertRaises(ValueError):self.service.approve(p["id"],p["version"])
        self.assertFalse(self.production.exported)

    def test_revision_conflict_and_restore_keep_previous_script(self):
        self.create();self.tick();p=self.latest();changed=deepcopy(p["script"]);changed["sequences"][0]["dialogue"][0]["text"]="Notre enfant arrive bientôt."
        self.service.update(p["id"],p["version"],changed,p["settings"])
        with self.assertRaises(StoryV2Conflict):self.service.update(p["id"],p["version"],p["script"],p["settings"])
        current=self.latest();self.service.restore(current["id"],current["version"],0)
        self.assertEqual(self.latest()["script"],p["script"])
        self.assertIsNone(self.latest()["approved"])

    def test_silent_presence_is_retained_and_offscreen_speech_is_explicit(self):
        s=screenplay();self.assertIn("marc",validate_script(s,settings())["sequences"][0]["character_ids"])
        s["sequences"][0]["character_ids"]=["marc"];s["sequences"][0]["appearances"]=[]
        with self.assertRaises(ValueError):validate_script(s,settings())
        s["sequences"][0]["dialogue"][0]["delivery"]="off_screen"
        validate_script(s,settings())

    def test_summary_action_and_dialogue_budget_are_bounded(self):
        s=screenplay();s["summary"].append("Encore une phrase.")
        with self.assertRaises(ValueError):Script.model_validate(s)
        s=screenplay();s["sequences"][0]["action"]="Une phrase. Une autre phrase."
        with self.assertRaises(ValueError):Script.model_validate(s)
        s=screenplay();s["sequences"][0]["dialogue"][0]["text"]="mot "*40
        with self.assertRaises(ValueError):Script.model_validate(s)

    def test_appearance_is_scoped_to_scene_and_render_export_is_repeatable(self):
        p=self.create();p["script"]=validate_script(screenplay(),settings())
        episodes=LocalEpisodeStore(self.temp.name)
        adapter=StoryV2Production(NS(store=episodes),None)
        identity=adapter.export(p);self.assertEqual(adapter.export(p),identity)
        ep=episodes.get(identity)
        self.assertIn("grossesse avancée",ep["scenes"][0]["intention"])
        self.assertNotIn("grossesse avancée",ep["scenes"][1]["intention"])
        self.assertIn("accouchement",ep["scenes"][1]["intention"])
        raw=scene_inputs(ep,ep["scenes"][1],require_images=False)["source_text"]
        self.assertNotIn("Conserver cet état pendant tout le clip",raw)
        self.assertNotIn("Invente une mise en scène créative",raw)
        self.assertEqual(ep["scenes"][0]["creative_axes"]["extra_motion"],3)

    def test_visual_settings_change_does_not_reuse_old_export(self):
        p=self.create();p["script"]=validate_script(screenplay(),settings())
        adapter=StoryV2Production(NS(store=LocalEpisodeStore(self.temp.name)),None)
        first=adapter.export(p);p["settings"]["style"]="Animation en volume"
        self.assertNotEqual(adapter.export(p),first)

    def test_storage_rejects_traversal(self):
        with self.assertRaises(ValueError):self.store.get("../outside")

    def test_http_rejects_invalid_mode_and_unknown_fields(self):
        app=FastAPI();app.include_router(story_v2_router(self.service));client=TestClient(app)
        body=dict(command="test-12345678",settings={**settings(),"mode":"silent"})
        self.assertEqual(client.post("/api/stories-v2/projects",json=body).status_code,422)
        body["settings"]=settings();body["unexpected"]=True
        self.assertEqual(client.post("/api/stories-v2/projects",json=body).status_code,422)
        self.assertFalse(self.store.list())

if __name__=="__main__":unittest.main()
