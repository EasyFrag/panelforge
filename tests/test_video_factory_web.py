"""User-run HTTP and browser fixtures, with fake services only."""
import json
import os
from pathlib import Path
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.video_factory import configuration, PRESETS, new_item
from panelforge.features.lab.video_factory_web import video_factory_router
from tests.test_video_factory import MemoryStore, FakeWorkflows
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class VideoFactoryHttpTest(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeWorkflows()
        self.service = VideoFactoryService(store=MemoryStore(), adapter=self.adapter)
        app = FastAPI()
        app.include_router(video_factory_router(self.service, validate_image=lambda content: "image/png"))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_image_send_is_incomplete_unassigned_and_idempotent(self):
        payload = dict(source_kind="image", source_id="krea-project", asset_id="asset-image", name="Image choisie")
        first = self.client.post("/api/video-factory/receive", json=payload)
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/video-factory/receive", json=payload).json()
        self.assertEqual(first.json()["ids"], second["ids"])
        self.assertEqual(second["added"], 0)
        item = second["state"]["items"][0]
        self.assertEqual(item["config"]["references"][0]["role"], "unassigned")
        self.assertEqual(item["status"], "preparation")
        self.assertFalse(item["ready"])
        self.assertEqual(self.adapter.calls, [])

    def test_launch_requires_current_revision_and_all_inputs(self):
        response = self.client.post("/api/video-factory/receive", json=dict(source_kind="h3", config=configuration()))
        item = response.json()["state"]["items"][0]
        url = "/api/video-factory/launch"
        self.assertEqual(self.client.post(url, json={"ids": [item["id"]]}).status_code, 409)
        self.assertEqual(self.client.post(url, json={"ids": [item["id"]],
            "revisions": {item["id"]: item["revision"]}}).status_code, 422)
        self.assertEqual(self.adapter.calls, [])

    def test_unconfigured_factory_returns_explicit_503(self):
        app = FastAPI(); app.include_router(video_factory_router(None, validate_image=lambda content: "image/png"))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/video-factory").status_code, 503)


class VideoFactoryBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_send_stays_in_workshop_and_draft_survives_refresh(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers: self.skipTest("local Chromium not installed")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        config = configuration(); config["intention"] = "Intention initiale"
        item = new_item("Vidéo de test", config, {"kind": "h3", "view": "i2v-direct"}, "key")
        item.update(ready=True, issues=[])
        fixture = dict(items=[item], presets=PRESETS, revision=1, paused=False, machines={}, scheduler_error=None)
        bootstrap = 'let data=' + json.dumps(fixture, ensure_ascii=False) + r''';
          const calls=[], navigations=[];
          window.PanelForgeLabNavigation={switchView(view){navigations.push(view);}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);
            if(url.endsWith('/receive'))return {state:structuredClone(data),ids:[data.items[0].id],added:1};
            if(options.method==='PATCH') {
              const body=JSON.parse(options.body);Object.assign(data.items[0].config,body.changes);
              delete data.items[0].config.name;data.items[0].revision++;
              return {state:structuredClone(data),undo:{},revisions:{}};
            }
            if(url==='/api/video-factory')return structuredClone(data);
            throw new Error('Unexpected URL '+url);
          }};
        '''
        scenario = r'''
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
          await settle();
          const button=window.PanelForgeVideoFactory.imageButton({assetId:'asset-image',name:'Image',sourceId:'krea'});
          document.body.append(button);button.click();button.click();await settle();
          check(calls.filter(([url])=>url.endsWith('/receive')).length===1,'double click sends once');
          check(navigations.length===0,'sending remains in the original workshop');
          check(document.getElementById('vf-notice').textContent.includes('à l’usine'),'visible receipt');
          await window.PanelForgeVideoFactory.open([data.items[0].id]);await settle();
          check(document.querySelectorAll('#vf-rows .vf-stage').length===5,'five visible stages');
          const input=document.querySelector('[data-vf-field="intention"]');input.focus();
          document.getElementById('vf-refresh').click();await settle();
          check(document.activeElement===input,'refresh preserves focus in unchanged inspector');
          input.value='Mon brouillon non enregistré';input.dispatchEvent(new Event('input',{bubbles:true}));
          document.getElementById('vf-refresh').click();await settle();
          check(document.querySelector('[data-vf-field="intention"]').value===input.value,'unsaved draft retained');
          document.getElementById('vf-discard').click();
          const social=document.querySelector('[data-vf-field="social.enabled"]');
          social.checked=true;social.dispatchEvent(new Event('input',{bubbles:true}));
          check(document.querySelector('[data-vf-field="social.language"]').value==='en','IG defaults to English');
          check(document.querySelector('[data-vf-field="social.variant_count"]').value==='3','IG defaults to three variants');
          check(!document.getElementById('vf-social-fields').hidden,'IG settings visible');
          check(!calls.some(([url])=>/launch|generate|video-chain/.test(url)),'no launch during preparation');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        '''
        source = (STATIC / "video-factory.js").read_text(encoding="utf-8")
        self.run_browser(browsers[-1], '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup +
                         '<pre id="result">PENDING</pre><script>' + bootstrap + source + scenario + '</script>')


if __name__ == "__main__": unittest.main()