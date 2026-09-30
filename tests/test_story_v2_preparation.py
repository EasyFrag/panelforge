"""User-run regressions for preparation only. All model/GPU clients are fakes."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from panelforge.domain.story_v2 import Settings, default_settings, digest
from panelforge.domain.episodes import scene_inputs
from panelforge.domain.minimax_edit import MinimaxEditSettings
from panelforge.application.minimax_edit import MinimaxEditService
from panelforge.application.qwen_edit import QwenEditService
from panelforge.application.story_v2_images import StoryV2Images
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.application.story_v2 import StoryV2Service
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from tests.test_story_v2 import screenplay, settings, Production, Gateway

ROOT = Path(__file__).resolve().parents[1]

class MemoryProjects:
    def __init__(self): self.values={}
    def get(self, identity):
        if identity not in self.values:raise FileNotFoundError(identity)
        return deepcopy(self.values[identity])
    def save(self, p):self.values[p["id"]]=deepcopy(p);return deepcopy(p)

def engine(cls=MinimaxEditService):
    return cls(gateway=Mock(), workflow=Mock(), comfy=Mock(), projects=MemoryProjects(),
        assets=NS(get=lambda _:NS(media_type="image/png"),read_bytes=lambda _:b"fake"),
        images=NS(dimensions=lambda _:(256,256)))

def image_request(count=3):
    return dict(key="story-test-thumbnail",name="Miniature",source_asset_id=None,
        references=[dict(asset_id="asset-"+str(i),name="Personnage "+str(i),role="Identity") for i in range(count)],
        draft="Compose a thumbnail from these identities.",model_id="fake-vision",settings=dict(resolution="2",aspect_ratio="9:16"))

class StoryV2PreparationTest(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=LocalEpisodeStore(self.temp.name)
        self.episodes=NS(store=self.store,_lock=RLock(),get=self.store.get)
        self.production=StoryV2Production(self.episodes,None)
        self.project=dict(id="storyv2-"+"b"*32,version=1,settings=settings(),script=screenplay(),episode_id=None,approved="approved")
        self.project["episode_id"]=self.production.export(self.project)

    def test_defaults_match_agreed_image_video_and_editing_choices(self):
        s=default_settings();i=s["images"];v=s["video"]
        self.assertEqual(s["image_model"],"Krea2/kroma-v0.3-turbo.safetensors");self.assertTrue(s["dlss"])
        self.assertEqual((i["assistance_recipe_version"],i["local_inspiration_enabled"],i["prompt_language"]),("6.0.0",False,"en"))
        self.assertEqual(i["style_preset_id"],"style-642721e10d124d5a83ad6bb907ef8fd3");self.assertIsNone(i["art_style_id"])
        self.assertEqual((i["workflow"]["recipe_id"],i["megapixels"],i["sampling"]["preset_id"]),("krea2-flux-klein",2.1,"finish_4"))
        self.assertEqual(i["edit_engine"],"minimax");self.assertTrue(i["thumbnail"])
        self.assertEqual([v["audacity"],*v["creative_axes"].values()],[3,3,3,3,1])
        r=v["render"];self.assertEqual(r["recipe"],{"id":"minimax-h3-bunny","version":"0.1.3+vae-int8-convrot.1"})
        self.assertEqual(r["settings"]["aspect_ratio"],"9:16 (Portrait Widescreen)")
        self.assertEqual(r["settings"]["megapixels"],.9);self.assertFalse(r["music_enabled"])
        self.assertEqual(r["video_loras"]["entries"][0]["name"],"minmax_nsfw/Motion_Repair.safetensors")

    def test_settings_reject_incompatible_recipe_art_and_bunny_spectrum(self):
        s=settings();s["images"]["assistance_recipe_version"]="3.0.0";s["images"]["art_style_id"]="chosen-style"
        with self.assertRaises(ValueError):Settings.model_validate(s)
        s=settings();s["video"]["render"]["spectrum_enabled"]=True
        with self.assertRaises(ValueError):Settings.model_validate(s)
        s=settings();s["video"]["creative_axes"]["camera"]=4
        with self.assertRaises(ValueError):Settings.model_validate(s)

    def test_reference_options_and_video_models_are_independent_of_writer(self):
        p=deepcopy(self.project);p["settings"]["images"]["style_preset_id"]="preset-style"
        p["settings"]["images"]["art_style_id"]="art-style"
        p["settings"]["video"]["plan_model"]="video-plan";p["settings"]["video"]["prompt_model"]="video-prompt"
        ep=self.store.get(self.production.export(p))
        self.assertEqual(ep["reference_assistance"]["style_preset_id"],"preset-style")
        self.assertEqual(ep["reference_assistance"]["art_style_id"],"art-style")
        self.assertFalse(ep["reference_assistance"]["local_inspiration_enabled"])
        self.assertEqual(ep["scenes"][0]["plan_model_id"],"video-plan")
        self.assertEqual(ep["scenes"][0]["writer_model_id"],"video-prompt")

    def test_each_state_uses_its_own_variant_of_the_identity(self):
        ep=self.store.get(self.project["episode_id"]);refs={r["id"]:r for r in ep["references"]}
        first=refs[ep["scenes"][0]["references"][0]["reference_id"]]
        second=refs[ep["scenes"][1]["references"][0]["reference_id"]]
        self.assertNotEqual(first["id"],second["id"])
        self.assertEqual(first["story_v2_state"]["base_id"],second["story_v2_state"]["base_id"])
        self.assertIn("grossesse",first["description"]);self.assertNotIn("grossesse",second["description"])
        self.assertEqual([r for r in ep["scenes"][0]["references"] if refs[r["reference_id"]]["source_id"]=="marc"][0]["role"],"subject_reference")

    def test_send_never_carries_an_old_plan_or_prompt_into_preparation(self):
        entry=dict(config={"final_prompt":"old prompt"},outputs={"plan":{},"prompt":{"text":"old prompt"}},
            runtime={"session_id":"old-session","episode_inputs":{"action":"current"}},source={})
        factory=NS(adapter=NS(capture_episode=lambda *a,**k:[deepcopy(entry)]),launch=Mock())
        production=StoryV2Production(self.episodes,factory)
        sent=production.send(self.project)[0]
        self.assertEqual(sent["config"]["final_prompt"],"");self.assertEqual(sent["outputs"],{})
        self.assertNotIn("session_id",sent["runtime"]);self.assertEqual(sent["runtime"]["episode_inputs"],{"action":"current"})
        factory.launch.assert_not_called()

    def test_old_selected_images_do_not_complete_a_new_reference_batch(self):
        ep=self.store.get(self.project["episode_id"])
        for r in ep["references"]:r["image_asset_id"]="asset-old"
        ep["story_v2_selection"]={"request_id":"new"}
        ep["reference_batch"]={"request_id":"new","status":"running","items":[{"reference_id":"character-1","status":"queued_render"}]}
        self.store.save(ep)
        self.assertFalse(self.production.references(self.project))

    def test_changed_identity_requires_a_new_variant_before_sending(self):
        ep=self.store.get(self.project["episode_id"])
        for r in ep["references"]:r["image_asset_id"]="asset-selected"
        state=next(r for r in ep["references"] if r.get("story_v2_state"))
        state["story_v2_edit"]={"output_asset_id":"asset-selected","reference_asset_ids":["asset-previous-identity"]}
        self.store.save(ep)
        self.assertFalse(self.production.references(self.project))

    def test_resume_waits_for_existing_batch_without_submitting_it_again(self):
        store=LocalStoryV2Store(self.temp.name);production=Production()
        service=StoryV2Service(store,Gateway([]),production)
        p=service.create("resume-existing",settings("automatic"))
        p.update(status="paused",resume_stage="references_ready",script=screenplay(),
                 approved=digest(screenplay()),episode_id=production.episode["episode_id"],watch_images=True)
        store.save(p)
        production.episode["story_v2_selection"]={"ids":["character-1"],"request_id":"existing"}
        production.episode["reference_batch"]={"status":"running","request_id":"existing"}
        service.resume(p["id"],p["version"]);service.tick(p["id"])
        self.assertEqual(production.started,[])
        self.assertTrue(store.get(p["id"])["retry_references"])
        production.ready=True;production.episode["reference_batch"]["status"]="completed"
        service.tick(p["id"])
        self.assertEqual(store.get(p["id"])["status"],"prepared")
        self.assertEqual(production.started,[]);self.assertEqual(production.launched,[])

    def test_resume_retries_failed_thumbnail_and_selected_variant_together(self):
        store=LocalStoryV2Store(self.temp.name);production=Production()
        service=StoryV2Service(store,Gateway([]),production)
        p=service.create("retry-images",settings())
        p.update(status="failed",resume_stage="references",script=screenplay(),
                 approved=digest(screenplay()),episode_id=production.episode["episode_id"])
        store.save(p)
        production.episode.update(references=[
            dict(id="base-ok",image_asset_id="asset-ok"),
            dict(id="state-failed",image_asset_id=None,story_v2_state={"base_id":"base-ok"}),
            dict(id="unselected",image_asset_id=None)],
            story_v2_thumbnail={},reference_batch={"status":"completed","items":[]},
            story_v2_selection={"ids":["base-ok","state-failed"],"request_id":"old"})
        production.failed_images=lambda _: ["state-failed","thumbnail"]
        with patch.object(production,"start_references",wraps=production.start_references) as start:
            service.resume(p["id"],p["version"]);service.tick(p["id"])
        self.assertEqual(start.call_args.kwargs["ids"],["state-failed"])
        self.assertTrue(start.call_args.kwargs["retry_thumbnail"])
        self.assertTrue(start.call_args.kwargs["resume"])
        self.assertEqual(production.launched,[])

    def test_preferences_remember_choices_without_reusing_the_idea(self):
        store=LocalStoryV2Store(self.temp.name);service=StoryV2Service(store,Gateway([]),Production())
        s=settings();s["images"]["edit_engine"]="qwen";s["video"]["shot_count"]=2
        service.create("preferences-command",s)
        remembered=service.preferences()
        self.assertEqual(remembered["idea"],"");self.assertEqual(remembered["images"]["edit_engine"],"qwen")
        self.assertEqual(remembered["video"]["shot_count"],2)

    def test_minimax_thumbnail_has_separate_reference_assets_and_stable_ids(self):
        mini=engine();request=image_request(4)
        first=mini.ensure_story_image(**request);again=mini.ensure_story_image(**request)
        self.assertEqual(first["id"],again["id"]);self.assertEqual(len(mini.projects.values),1)
        stage=first["stages"][0];inputs=mini.policy.render_inputs(stage)
        self.assertIsNone(stage["source_asset_id"])
        self.assertEqual([r["asset_id"] for r in inputs],[r["asset_id"] for r in request["references"]])
        self.assertEqual([r["tag"] for r in inputs],["<Picture 1>","<Picture 2>","<Picture 3>","<Picture 4>"])
        mini.gateway.stream.assert_not_called();mini.comfy.submit_workflow.assert_not_called()

    def test_minimax_manifest_receives_all_thumbnail_images_in_order(self):
        workflow=load_minimax_edit_workflow(ROOT/"workflows/image.edit/minimax-h3-still/1.2.0")
        filenames=["first.png","second.png","third.png"]
        graph=workflow.build(images=filenames,prompt="Compose <Picture 1>, <Picture 2> and <Picture 3>.",
            settings=MinimaxEditSettings(),dimensions=(768,1376),composition=True,output_prefix="fake")
        slots=workflow.manifest["image_slots"];encoder=graph[workflow.manifest["conditioning_node"]]["inputs"]
        self.assertEqual([graph[s["load_node"]]["inputs"]["image"] for s in slots[:3]],filenames)
        self.assertTrue(all(s["input"] in encoder for s in slots[:3]))
        self.assertTrue(all(s["input"] not in encoder for s in slots[3:]))

    def test_minimax_rejects_too_many_refs_and_qwen_keeps_its_contract(self):
        mini=engine()
        with self.assertRaises(ValueError):mini.ensure_story_image(**image_request(10))
        qwen=engine(QwenEditService);p=qwen.ensure_story_image(**image_request(3))
        self.assertEqual([r["tag"] for r in qwen.policy.render_inputs(p["stages"][0])],["<image1>","<image2>","<image3>"])

    def _prepare_image_chain(self, cls=MinimaxEditService):
        selected_engine = engine(cls)
        self.project["settings"]["images"]["edit_engine"] = selected_engine.engine
        self.production.images.engines[selected_engine.engine] = selected_engine
        patcher = patch.object(self.production.images, "_prompt")
        prompt = patcher.start()
        self.addCleanup(patcher.stop)
        episode = self.store.get(self.project["episode_id"])
        for ref in episode["references"]:
            if not ref.get("story_v2_state"):
                ref["image_asset_id"] = "base-" + ref["id"]
        episode["story_v2_selection"] = dict(ids=[r["id"] for r in episode["references"]], request_id="first")
        self.store.save(episode)
        self.production.advance_images(self.project)
        return selected_engine, prompt

    def _finish_story_image(self, selected_engine, holder, *, status="succeeded", lost_ack=False):
        link = holder["story_v2_edit"]
        project = selected_engine.get(link["project_id"])
        stage = next(s for s in project["stages"] if s["id"] == link["stage_id"])
        message = next(m for m in stage["messages"] if m["id"] == link["message_id"])
        attempt = dict(id="attempt-" + message["id"], request_id="prompt-" + message["id"],
            status=status, output_asset_id="output-" + message["id"] if status == "succeeded" else None)
        stage["attempts"].append(attempt)
        message["status"] = "succeeded"
        message["auto_render"] = {"status":"skipped"} if lost_ack else {"status":"queued", "attempt_id":attempt["id"]}
        selected_engine.projects.save(project)
        return attempt

    def test_manual_first_batch_chains_images_without_individual_approval(self):
        selected_engine = engine()
        self.production.images.engines["minimax"] = selected_engine
        episode = self.store.get(self.project["episode_id"])
        bases = [r for r in episode["references"] if not r.get("story_v2_state")]
        episode["story_v2_selection"] = dict(ids=[r["id"] for r in episode["references"]], request_id="first")
        episode["reference_batch"] = dict(request_id="first", status="waiting_review", items=[
            dict(reference_id=r["id"], status="ready_for_review", output_asset_id="base-" + r["id"])
            for r in bases])
        self.store.save(episode)

        def select(identity, ref_id, revision, asset_id):
            value = self.store.get(identity)
            ref = next(r for r in value["references"] if r["id"] == ref_id)
            self.assertEqual(ref["revision"], revision)
            ref.update(image_asset_id=asset_id, revision=revision+1)
            item = next(i for i in value["reference_batch"]["items"] if i["reference_id"] == ref_id)
            item["status"] = "validated"
            if all(i["status"] == "validated" for i in value["reference_batch"]["items"]):
                value["reference_batch"]["status"] = "completed"
            return self.store.save(value)

        self.episodes.select_image = Mock(side_effect=select)
        with patch.object(self.production.images, "_prompt"):
            self.production.advance_images(self.project, automatic=False)
            self.assertFalse(selected_engine.projects.values)  # A source image must exist first.
            self.assertFalse(self.production.references(self.project, automatic=False))
            self.assertEqual(self.episodes.select_image.call_count, len(bases))
            self.assertTrue(self.production.advance_images(self.project, automatic=False))
            current = self.store.get(episode["episode_id"])
            for holder in [*current["references"], current["story_v2_thumbnail"]]:
                if holder.get("story_v2_edit"):
                    self._finish_story_image(selected_engine, holder)
            self.assertFalse(self.production.advance_images(self.project, automatic=False))
        current = self.store.get(episode["episode_id"])
        self.assertTrue(all(r["image_asset_id"] for r in current["references"]))
        self.assertTrue(current["story_v2_thumbnail"]["image_asset_id"])
        self.assertTrue(self.production.references(self.project, automatic=False))
        selected_engine.gateway.stream.assert_not_called()
        selected_engine.comfy.submit_workflow.assert_not_called()

    def test_resume_recovers_exact_lost_ack_and_keeps_in_flight_children(self):
        for cls in (MinimaxEditService, QwenEditService):
            with self.subTest(engine=cls.__name__):
                # Each case uses its own exported episode and source links.
                self.project["episode_id"] = None
                self.project["settings"]["images"]["edit_engine"] = "minimax" if cls is MinimaxEditService else "qwen"
                self.project["episode_id"] = self.production.export(self.project)
                selected_engine, prompt = self._prepare_image_chain(cls)
                episode = self.store.get(self.project["episode_id"])
                states = [r for r in episode["references"] if r.get("story_v2_state")]
                completed = self._finish_story_image(selected_engine, states[0], lost_ack=True)
                pending = self._finish_story_image(selected_engine, states[1], status="running", lost_ack=True)
                self._finish_story_image(selected_engine, episode["story_v2_thumbnail"], lost_ack=True)
                children_before = set(selected_engine.projects.values)
                self.assertEqual(self.production.failed_images(self.project), [])
                self.production.start_references(self.project, ids=[r["id"] for r in states],
                    request_id="resume", resume=True)
                prompt.reset_mock()
                self.assertTrue(self.production.advance_images(self.project))
                current = self.store.get(self.project["episode_id"])
                first = next(r for r in current["references"] if r["id"] == states[0]["id"])
                second = next(r for r in current["references"] if r["id"] == states[1]["id"])
                self.assertEqual(first["image_asset_id"], completed["output_asset_id"])
                self.assertEqual(first["story_v2_edit"]["project_id"], states[0]["story_v2_edit"]["project_id"])
                self.assertEqual(second["story_v2_edit"]["attempt_id"], pending["id"])
                self.assertIsNone(second["image_asset_id"])
                self.assertEqual(set(selected_engine.projects.values), children_before)
                self.assertEqual([i["asset_id"] for i in first["images"]], [completed["output_asset_id"]])
                prompt.assert_not_called()
                selected_engine.gateway.stream.assert_not_called()
                selected_engine.comfy.submit_workflow.assert_not_called()

    def test_resume_retries_failed_child_but_not_successful_sibling(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        states = [r for r in episode["references"] if r.get("story_v2_state")]
        self._finish_story_image(selected_engine, states[0], lost_ack=True)
        self._finish_story_image(selected_engine, states[1], status="failed", lost_ack=True)
        self._finish_story_image(selected_engine, episode["story_v2_thumbnail"])
        self.assertEqual(self.production.failed_images(self.project), [states[1]["id"]])
        self.production.start_references(self.project, ids=[r["id"] for r in states], request_id="retry", resume=True)
        self.production.advance_images(self.project)
        current = self.store.get(self.project["episode_id"])
        current_states = [r for r in current["references"] if r.get("story_v2_state")]
        self.assertEqual(current_states[0]["story_v2_edit"]["project_id"], states[0]["story_v2_edit"]["project_id"])
        self.assertNotEqual(current_states[1]["story_v2_edit"]["project_id"], states[1]["story_v2_edit"]["project_id"])
        self.assertEqual(len(selected_engine.projects.values), 4)

    def test_missing_ack_does_not_attach_an_unrelated_successful_render(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        state = next(r for r in episode["references"] if r.get("story_v2_state"))
        attempt = self._finish_story_image(selected_engine, state, lost_ack=True)
        child = selected_engine.get(state["story_v2_edit"]["project_id"])
        child["stages"][0]["attempts"][0]["request_id"] = "different-request"
        selected_engine.projects.save(child)
        self.assertIn(state["id"], self.production.failed_images(self.project))
        current = next(r for r in self.store.get(episode["episode_id"])["references"] if r["id"] == state["id"])
        self.assertIsNone(current["image_asset_id"])
        self.assertNotIn(attempt["output_asset_id"], [i["asset_id"] for i in current["images"]])

    def test_explicit_retake_still_creates_one_new_child_and_keeps_previous_image(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        for holder in [*episode["references"], episode["story_v2_thumbnail"]]:
            if holder.get("story_v2_edit"):
                self._finish_story_image(selected_engine, holder)
        self.production.advance_images(self.project)
        before = self.store.get(episode["episode_id"])
        state = next(r for r in before["references"] if r.get("story_v2_state"))
        self.production.start_references(self.project, ids=[state["id"]], request_id="explicit-retake")
        self.production.advance_images(self.project)
        current = next(r for r in self.store.get(episode["episode_id"])["references"] if r["id"] == state["id"])
        self.assertNotEqual(current["story_v2_edit"]["project_id"], state["story_v2_edit"]["project_id"])
        self.assertEqual(current["images"], state["images"])
        self.assertEqual(current["image_asset_id"], state["image_asset_id"])
        self.assertEqual(len(selected_engine.projects.values), 4)

    def test_polling_recovered_output_preserves_a_later_manual_choice(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        state = next(r for r in episode["references"] if r.get("story_v2_state"))
        self._finish_story_image(selected_engine, state, lost_ack=True)
        self.production.failed_images(self.project)
        current = self.store.get(episode["episode_id"])
        state = next(r for r in current["references"] if r["id"] == state["id"])
        state["images"].append(dict(asset_id="manual-choice", label="Import"))
        state["image_asset_id"] = "manual-choice"
        self.store.save(current)
        self.production.failed_images(self.project)
        self.production.advance_images(self.project)
        selected = next(r for r in self.store.get(episode["episode_id"])["references"] if r["id"] == state["id"])
        self.assertEqual(selected["image_asset_id"], "manual-choice")

    def test_late_render_does_not_replace_a_manual_choice_made_while_paused(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        state = next(r for r in episode["references"] if r.get("story_v2_state"))
        state["images"].append(dict(asset_id="manual-choice", label="Import"))
        state["image_asset_id"] = "manual-choice"
        self.store.save(episode)
        attempt = self._finish_story_image(selected_engine, state, lost_ack=True)
        self.production.failed_images(self.project)
        current = next(r for r in self.store.get(episode["episode_id"])["references"] if r["id"] == state["id"])
        self.assertEqual(current["image_asset_id"], "manual-choice")
        self.assertIn(attempt["output_asset_id"], [i["asset_id"] for i in current["images"]])

    def test_recovered_variant_is_not_reused_when_its_source_identity_changes(self):
        selected_engine, _ = self._prepare_image_chain()
        episode = self.store.get(self.project["episode_id"])
        state = next(r for r in episode["references"] if r.get("story_v2_state"))
        self._finish_story_image(selected_engine, state, lost_ack=True)
        self.production.failed_images(self.project)
        current = self.store.get(episode["episode_id"])
        base = next(r for r in current["references"] if r["id"] == state["story_v2_state"]["base_id"])
        base["image_asset_id"] = "new-identity"
        self.store.save(current)
        self.production.start_references(self.project, ids=[state["id"]], request_id="new-source", resume=True)
        self.production.advance_images(self.project)
        updated = next(r for r in self.store.get(episode["episode_id"])["references"] if r["id"] == state["id"])
        self.assertNotEqual(updated["story_v2_edit"]["project_id"], state["story_v2_edit"]["project_id"])
        child = selected_engine.get(updated["story_v2_edit"]["project_id"])
        self.assertEqual(child["stages"][0]["source_asset_id"], "new-identity")
        self.assertIsNone(updated["image_asset_id"])

    def test_completed_manual_reference_batch_waits_before_factory_handoff(self):
        store=LocalStoryV2Store(self.temp.name);production=Production()
        service=StoryV2Service(store,Gateway([]),production)
        p=service.create("manual-complete",settings("manual"))
        p.update(status="references",script=screenplay(),approved=digest(screenplay()),
                 episode_id=production.episode["episode_id"])
        store.save(p)
        production.ready=True
        production.episode.update(story_v2_selection={"ids":["character-1"],"request_id":"done"},
                                  reference_batch={"status":"completed","request_id":"done"})
        service.tick(p["id"])
        self.assertEqual(store.get(p["id"])["status"], "references_ready")
        self.assertFalse(production.sent or production.launched)

    def test_variants_and_thumbnail_share_selected_engine_without_video_calls(self):
        mini=engine();qwen=engine(QwenEditService);images=StoryV2Images(self.episodes,minimax=mini,qwen=qwen)
        ep=self.store.get(self.project["episode_id"])
        for i,r in enumerate(ep["references"]):
            if not r.get("story_v2_state"):r["image_asset_id"]="asset-base-"+str(i)
        ep["story_v2_selection"]={"ids":[r["id"] for r in ep["references"]],"request_id":"selected"}
        self.store.save(ep)
        with patch.object(images,"_prompt"):
            self.assertTrue(images.advance(self.project,True))
        out=self.store.get(ep["episode_id"])
        self.assertEqual(out["story_v2_thumbnail"]["story_v2_edit"]["engine"],"minimax")
        self.assertGreater(len(out["story_v2_thumbnail"]["story_v2_edit"]["reference_asset_ids"]),1)
        self.assertTrue(all(r["story_v2_edit"]["engine"]=="minimax" for r in out["references"] if r.get("story_v2_state")))
        self.assertFalse(qwen.projects.values)
        mini.gateway.stream.assert_not_called();mini.comfy.submit_workflow.assert_not_called()

if __name__ == "__main__":unittest.main()
