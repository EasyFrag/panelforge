"""User-run HTTP and browser fixtures, with fake services only."""
import json
import os
from pathlib import Path
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.video_factory import configuration, PRESETS, new_item, apply_preset
from panelforge.domain.localized_speech import THANKS_LANGUAGES
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

    def test_monitor_keeps_indicative_times_at_expiry_during_waits_and_stale_updates(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        markup = """<meta charset="utf-8"><main id="video-factory-workspace">
          <div id="vf-monitor-summary"></div><div data-vf-monitor-row="A"></div>
          <small data-vf-monitor-item="A" data-vf-monitor-step="video"></small>
          </main><pre id="result">PENDING</pre>"""
        scenario = r"""
          try {
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            let clock=0;
            Object.defineProperty(performance,"now",{configurable:true,value:()=>clock});
            const item={id:"A",status:"active",steps:{video:{status:"running"}}};
            const m={generated_at:1800000000,stale:false,status:"running",
              cycle:{id:"cycle"},counts:{total:7,delivered:5,active:1,queued:1,exporting:0,failed:0},
              remaining_seconds:2,low_seconds:1,high_seconds:5,
              items:{A:{remaining_seconds:2,low_seconds:1,high_seconds:5,steps:{
                video:{seconds:2,low:1,high:5,reason:"Comparable",samples:12}}}}};
            const state={data:{items:[item],monitoring:m},tab:"production"};
            const root=document.getElementById("video-factory-workspace");
            const monitor=window.PanelForgeFactoryMonitor.create({
              root,escape:s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;"),
              request:()=>{throw new Error("Unexpected request");},getState:()=>state,getSelection:()=>[]
            });
            const summary=document.getElementById("vf-monitor-summary");
            const step=root.querySelector("[data-vf-monitor-step]");
            monitor.received();monitor.render();
            clock=3000;monitor.tick();
            check(summary.textContent.includes("≈ < 1 min"),"expired forecast retains a numeric indication");
            check(step.textContent.includes("≈ < 1 min"),"active step keeps indication between polls");
            check(!root.textContent.includes("réévalu")&&!root.textContent.includes("À préciser"),"expiry never erases a known ETA");
            clock=25000;monitor.tick();
            check(summary.textContent.includes("À actualiser"),"stale connection remains visible");
            check(summary.textContent.includes("≈ < 1 min"),"stale connection keeps last indication");
            check(summary.textContent.includes("Fin —"),"no live finish time from stale data");
            m.remaining_seconds=450;m.retained=true;
            m.items.A.remaining_seconds=450;m.items.A.retained=true;
            m.items.A.steps.video.seconds=120;m.items.A.steps.video.retained=true;
            monitor.received();monitor.render();
            clock+=10000;monitor.tick();
            check(summary.textContent.includes("≈ 8 min")&&summary.textContent.includes("Fin —"),"wait freezes budget without promising an end time");
            check(root.querySelector("[data-vf-monitor-row]").textContent.includes("Estimation conservée"),"row explains retained reference");
            check(step.textContent.includes("≈ 2 min"),"waiting step does not count down");
            m.status="paused";monitor.render();
            check(summary.textContent.includes("En pause")&&summary.textContent.includes("≈ 8 min"),"pause retains work budget");
            m.status="running";m.retained=false;m.remaining_seconds=null;monitor.render();
            check(summary.textContent.includes("À préciser"),"unknown first forecast stays unknown");
            m.status="complete";m.remaining_seconds=0;m.cycle.finished_at="2026-09-28T12:00:00Z";
            item.status="succeeded";item.steps.video.status="succeeded";
            m.items.A.remaining_seconds=0;monitor.render();
            check(summary.textContent.includes("Terminé"),"only actual completion shows finished");
            check(root.querySelector("[data-vf-monitor-row]").textContent.includes("Livré"),"delivery supersedes retained forecast");
            document.getElementById("result").textContent="PASS";
          } catch(error) { document.getElementById("result").textContent="FAIL: "+error.stack; }
        """
        self.run_browser(browsers[-1], markup + "<script>" +
            (STATIC / "video-factory-monitor.js").read_text(encoding="utf-8") + scenario + "</script>")


    def test_experimental_preset_language_override_and_planned_thanks(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        source = configuration()
        source["references"] = [dict(asset_id="asset-image", role="unassigned", label="Corée")]
        config = apply_preset(source, "little_men_experimental", source, name="Corée")
        config["references"][0]["scene_context"] = dict(asset_id="asset-image", origin="PNG KREA",
            prompt="A Korean village", intention="Pays : Corée", style="Wool")
        item = new_item("Corée", config, {"kind": "image"}, "key")
        item.update(ready=True, issues=[])
        item["steps"]["plan"].update(status="succeeded",
            output={"text": json.dumps({"spoken_lines": ["감사합니다!"], "spoken_languages": ["Korean"]})})
        fixture = dict(items=[item], presets=PRESETS, thanks_languages=THANKS_LANGUAGES,
                       revision=1, paused=False, machines={}, scheduler_error=None)
        bootstrap = 'let data=' + json.dumps(fixture, ensure_ascii=False) + r''';
          const calls=[];
          window.PanelForgeLabNavigation={switchView(){}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);
            if(options.method==='PATCH'){
              const body=JSON.parse(options.body),item=data.items[0];
              Object.assign(item.config,body.changes);delete item.config.name;
              item.config.preset='custom';item.revision++;
              item.steps.plan={status:'pending',output:{}};
              return {state:structuredClone(data),undo:{},revisions:{}};
            }
            if(url==='/api/video-factory')return structuredClone(data);
            throw new Error('Unexpected URL '+url);
          }};
        '''
        scenario = r'''
          (async()=>{try{
            const check=(value,label)=>{if(!value)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
            await settle();await window.PanelForgeVideoFactory.open([data.items[0].id]);await settle();
            check(document.querySelector('#vf-bulk-preset option[value="little_men_experimental"]'),'bulk preset');
            check(document.querySelector('#vf-item-preset').value==='little_men_experimental','individual preset');
            const section=document.querySelector('[data-vf-localized-thanks]');
            check(section.textContent.includes('Coréen · 감사합니다!'),'resolved native thanks visible');
            check(section.textContent.includes('Pays : Corée'),'recovered image context visible');
            check(section.querySelectorAll('[data-vf-field="little_men_language"] option').length===12,'auto plus eleven languages');
            check(!section.textContent.includes('En cas de doute : anglais'),'no English fallback hint');
            check(document.querySelector('[data-vf-field="render.settings.duration_seconds"]').value==='10','ten seconds');
            const language=section.querySelector('[data-vf-field="little_men_language"]');
            check(language.value==='auto','automatic default');
            language.value='French';language.dispatchEvent(new Event('input',{bubbles:true}));
            document.getElementById('vf-refresh').click();await settle();
            check(document.querySelector('[data-vf-field="little_men_language"]').value==='French','draft survives refresh');
            check(document.querySelector('[data-vf-field="social.language"]').value==='en','IG independent');
            document.getElementById('vf-save').click();await settle();
            check(data.items[0].config.little_men_language==='French','override saved');
            check(document.querySelector('[data-vf-localized-thanks]'),'controls survive custom preset');
            check(!document.querySelector('[data-vf-localized-thanks]').textContent.includes('감사합니다!'),'invalidated thanks cleared');
            check(!calls.some(([url])=>/launch|generate/.test(url)),'no automatic launch');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        '''
        self.run_browser(browsers[-1], '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup +
                         '<pre id="result">PENDING</pre><script>' + bootstrap +
                         (STATIC / "video-factory.js").read_text(encoding="utf-8") + scenario + '</script>')

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
            if(url.endsWith('/actions/remove')) {
              const body=JSON.parse(options.body);data.items=data.items.filter(item=>!body.ids.includes(item.id));
              return structuredClone(data);
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
          document.getElementById('vf-discard').click();
          const second=structuredClone(data.items[0]);second.id='factory-second';data.items.push(second);
          document.getElementById('vf-refresh').click();await settle();
          const all=document.getElementById('vf-select-all');all.checked=true;all.dispatchEvent(new Event('change'));
          const remove=document.getElementById('vf-remove');
          check(!remove.hidden&&!remove.disabled&&remove.textContent.includes('(2)'),'bulk remove shows selection count');
          const draft=document.querySelector('[data-vf-field="intention"]');draft.value='';draft.dispatchEvent(new Event('input',{bubbles:true}));
          const patchesBefore=calls.filter(([,options])=>options.method==='PATCH').length;
          remove.click();await settle();
          check(data.items.length===0,'all selected preparation rows removed');
          check(calls.filter(([,options])=>options.method==='PATCH').length===patchesBefore,'deleting a draft does not save it');
          check(document.getElementById('vf-remove').disabled,'remove disabled after clearing selection');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        '''
        source = (STATIC / "video-factory.js").read_text(encoding="utf-8")
        self.run_browser(browsers[-1], '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup +
                         '<pre id="result">PENDING</pre><script>' + bootstrap + source + scenario + '</script>')


    def test_timing_image_zoom_unique_retry_and_removal_across_tabs(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers: self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + index.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        config = configuration(); config['intention'] = 'Intent'
        config['references'] = [dict(asset_id='test-image', role='first_frame', label='Image')]
        item = new_item('Result <image>', config, {'kind':'h3'}, 'result')
        item.update(status='failed', ready=True, issues=[])
        for stage, seconds in [('plan', 55), ('prompt', 33), ('video', 200), ('dlss', .1)]:
            from datetime import datetime, timedelta, timezone
            start = datetime(2026, 9, 26, 8, tzinfo=timezone.utc)
            item['steps'][stage].update(status='failed' if stage=='dlss' else 'succeeded',
                started_at=start.isoformat(), finished_at=(start+timedelta(seconds=seconds)).isoformat())
        draft = new_item('Draft', config, {'kind':'h3'}, 'draft'); draft.update(ready=True, issues=[])
        data = dict(items=[item,draft], presets=PRESETS, revision=1, paused=False, machines={}, scheduler_error=None)
        bootstrap = 'let data=' + json.dumps(data, ensure_ascii=False) + r""";
          const calls=[],timers={},mainId=data.items[0].id,draftId=data.items[1].id;
          let now=Date.parse('2026-09-26T09:00:00Z');Date.now=()=>now;
          window.setInterval=(fn,ms)=>{timers[ms]=fn;return ms;};
          window.PanelForgeLabNavigation={switchView(){document.getElementById("video-factory-workspace").hidden=false;}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);const body=options.body?JSON.parse(options.body):{};
            if(url.endsWith('/receive'))return {state:structuredClone(data),added:2,ids:[mainId],
              existing:[{id:mainId,name:'Scene',scene_index:0,status:'cancelled'}]};
            if(url.endsWith('/actions/retry')){
              const item=data.items.find(i=>i.id===body.ids[0]);item.status='queued';item.revision++;
              Object.values(item.steps).forEach(step=>{if(step.status==='failed')Object.assign(step,{status:'pending',started_at:null,finished_at:null});});
            } else if(url.endsWith('/actions/remove'))data.items=data.items.filter(i=>!body.ids.includes(i.id));
            else if(url!=='/api/video-factory')throw new Error('Unexpected URL '+url);
            return structuredClone(data);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
            const duration=stage=>document.querySelector('[data-vf-duration="'+stage+'"]').textContent;
            await settle();await window.PanelForgeVideoFactory.open([mainId]);await settle();
            check(duration('plan')==='55 s'&&duration('video')==='200 s','completed duration in seconds');
            check(duration('dlss')==='<1 s'&&duration('social')==='','short failure and disabled stage');
            const zoom=async()=>{
              const selected=document.getElementById('vf-selected-count').textContent;
              document.querySelector('#vf-rows [data-vf-preview]').click();
              check(document.getElementById('vf-image-dialog').open,'image opens large');
              check(document.getElementById('vf-image-content').getAttribute('src').includes('test-image'),'source image');
              check(document.getElementById('vf-selected-count').textContent===selected,'zoom does not change selection');
              document.querySelector('#vf-image-dialog [data-vf-close]').click();await settle();
            };
            await zoom();
            const rowRetry=document.querySelector('[data-vf-retry]');
            check(rowRetry.textContent==='Reprendre la chaîne','one retry label');rowRetry.click();await settle();
            check(document.querySelector('[data-vf-tab="production"]').classList.contains('active'),'retry returns to production');
            check(duration('dlss')===''&&duration('video')==='200 s','retry clears failed timing only');
            check(document.querySelector('#vf-inspector [data-vf-action="remove"]'),'delete in production inspector');
            data.items[0].status='active';Object.assign(data.items[0].steps.dlss,{status:'running',started_at:new Date(now-5000).toISOString()});
            document.getElementById('vf-refresh').click();await settle();check(duration('dlss')==='5 s','running time');
            now+=4000;timers[1000]();check(duration('dlss')==='9 s','running counter without replacing inspector');
            await zoom();
            await window.PanelForgeVideoFactory.open([draftId]);await settle();await zoom();
            check(document.querySelectorAll('[data-vf-duration]').length===0,'no times in preparation');
            await window.PanelForgeVideoFactory.send({source_kind:'episode',source_id:'episode'});
            check(document.getElementById('vf-notice').textContent.includes('scène 1 (Résultats · annulé)'),'partial send explains the cancelled duplicate');
            data.items[0].status='cancelled';data.items[0].steps.dlss.status='cancelled';
            await window.PanelForgeVideoFactory.open([mainId]);await settle();
            const remove=document.getElementById('vf-remove');check(!remove.hidden&&!remove.disabled,'bulk removal in results');
            document.querySelector('#vf-inspector [data-vf-action="remove"]').click();await settle();
            check(data.items.length===1&&data.items[0].id===draftId,'remove cancelled result only');
            check(calls.filter(([url])=>url.endsWith('/actions/retry')).length===1,'single retry request');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browsers[-1], '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup +
            '<pre id="result">PENDING</pre><script>' + bootstrap +
            (STATIC / 'video-factory.js').read_text(encoding='utf-8') + scenario + '</script>')


    def test_episode_boundaries_english_marker_and_legacy_dlss_progress(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers: self.skipTest("local Chromium not installed")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        items = []
        for number in range(4):
            config = configuration()
            config["intention"] = "Description française et répliques originales."
            config["final_prompt"] = "<d>[English] Thank you.</d>"
            source = (dict(kind="episode", id="english-copy", group="Séance privée — English", index=number)
                      if number < 3 else dict(kind="image", id="lips"))
            item = new_item("Scene " + str(number+1) if number < 3 else "Lips English", config, source, str(number))
            item.update(ready=True, issues=[])
            if number < 3:
                item["runtime"] = dict(episode_inputs=dict(localization=dict(language="English")))
            items.append(item)
        data = dict(items=items, presets=PRESETS, revision=1, paused=False, machines={}, scheduler_error=None)
        bootstrap = 'let data=' + json.dumps(data, ensure_ascii=False) + r""";
          const calls=[];window.setInterval=()=>0;
          window.PanelForgeLabNavigation={switchView(){document.getElementById('video-factory-workspace').hidden=false;}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);
            if(url!=='/api/video-factory'||options.method!=='GET')throw new Error('Unexpected mutation '+url);
            return structuredClone(data);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
            const refresh=async()=>{document.getElementById('vf-refresh').click();await settle();};
            const row=id=>document.querySelector('[data-vf-id="'+id+'"]');
            const ids=data.items.map(item=>item.id),original=data.items.map(item=>JSON.stringify(item.config));
            await settle();
            for(const [status,tab] of [['preparation','preparation'],['active','production'],['succeeded','results']]){
              data.items.forEach(item=>{item.status=status;item.revision++;});
              await window.PanelForgeVideoFactory.open([ids[0]]);await settle();
              check(document.querySelector('[data-vf-tab="'+tab+'"]').classList.contains('active'),'expected tab');
              check(document.querySelectorAll('#vf-rows .vf-group-member').length===3,'exactly three episode scenes');
              check(document.querySelector('.vf-group-count').textContent.includes('3 scènes'),'visible scene count');
              check(row(ids[2]).classList.contains('vf-group-end'),'third scene closes the episode');
              check(row(ids[2]).nextElementSibling.classList.contains('vf-group-gap'),'space after the episode');
              check(row(ids[2]).nextElementSibling.nextElementSibling===row(ids[3]),'lips outside the closed group');
              check(!row(ids[3]).classList.contains('vf-group-member'),'standalone lips not a member');
              check(row(ids[0]).querySelector('.vf-language').textContent==='EN','English marker on row');
              check(document.querySelector('#vf-inspector h2 .vf-language').textContent==='EN','English marker in inspector');
              check(!row(ids[3]).querySelector('.vf-language'),'English title or IG alone does not imply translated dialogue');
              const checkbox=document.querySelector('[data-vf-group]');checkbox.checked=true;
              checkbox.dispatchEvent(new Event('change',{bubbles:true}));await settle();
              check(ids.slice(0,3).every(id=>row(id).querySelector('[data-vf-select]').checked),'group selects its three scenes');
              check(!row(ids[3]).querySelector('[data-vf-select]').checked,'group selection excludes lips');
              check(document.querySelector('[data-vf-field="intention"]').value===data.items[0].config.intention,'original intention retained');
            }
            check(data.items.every((item,i)=>JSON.stringify(item.config)===original[i]),'view never changes intent or prepared prompt');
            // A priority change can split an episode; each segment still closes without reordering.
            data.items=[data.items[0],data.items[3],data.items[1],data.items[2]];
            await refresh();
            check([...document.querySelectorAll('#vf-rows [data-vf-id]')].map(r=>r.dataset.vfId).join()===data.items.map(i=>i.id).join(),'priority order retained');
            check(document.querySelectorAll('.vf-group-end').length===2,'both separated segments close');
            data.items.forEach(item=>item.status='active');
            await window.PanelForgeVideoFactory.open([ids[0]]);await settle();
            const item=data.items[0],step=item.steps.dlss;
            step.status='running';
            for(const [progress,expected] of [
              [{stage_index:1,stage_count:3,percent:50},'50 %'],
              [{stage_index:2,stage_count:3,percent:null},'67 %'],
              [{stage_index:2,stage_count:3,percent:120},'100 %'],
              [.42,'42 %'],[NaN,'En cours'],[Infinity,'En cours'],[true,'En cours'],
              ['50','En cours'],[null,'En cours'],[{},'En cours'],
              [{stage_index:0,stage_count:0,percent:50},'En cours'],
              [{stage_index:0,stage_count:3,percent:'50'},'En cours']]){
              step.progress=progress;step.message='DLSS · running';await refresh();
              check(row(item.id).querySelector('[data-vf-stage="dlss"]').textContent===expected,'progress '+expected);
            }
            for(const message of ['DLSS · receiving','DLSS · importing','Finalisation DLSS']){
              step.progress=.99;step.message=message;await refresh();
              check(row(item.id).querySelector('[data-vf-stage="dlss"]').textContent==='Finalisation','no stale percentage during finalization');
            }
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browsers[-1], '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup +
            '<pre id="result">PENDING</pre><script>' + bootstrap +
            (STATIC / 'video-factory.js').read_text(encoding='utf-8') + scenario + '</script>')


    def test_archive_tab_bulk_restore_duplicate_receipt_and_compact_grid(self):
        from tests.test_video_factory_archives import delivered
        from panelforge.domain.video_factory_results import delivery_material
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers: self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + index.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        items = [delivered(name) for name in ("First", "Second", "Failed", "Old archive")]
        for item in items:
            item["steps"]["social"].update(status="succeeded", output={"variants":[{"caption":"Ready 🌱", "copy_text":"Ready 🌱"}]})
            item["delivery"]["key"] = delivery_material(item)["key"]
        items[2]["status"] = "failed"
        items[2]["steps"]["dlss"]["status"] = "failed"
        items[3]["archived_at"] = "2026-09-26T09:00:00Z"
        store = MemoryStore();store.value["items"] = items
        data = VideoFactoryService(store=store, adapter=FakeWorkflows()).snapshot()
        bootstrap = 'let data=' + json.dumps(data, ensure_ascii=False) + r""";
          const calls=[],ids=data.items.map(item=>item.id);window.setInterval=()=>0;
          window.PanelForgeLabNavigation={switchView(){document.getElementById('video-factory-workspace').hidden=false;}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);
            const body=options.body?JSON.parse(options.body):{};
            if(url.endsWith('/open-folder'))return {opened:true};
            if(url.endsWith('/receive')){
              const item=data.items.find(item=>item.id===ids[0]);
              return {state:structuredClone(data),ids:[item.id],added:0,existing:[{id:item.id,name:item.name,status:item.status,archived_at:item.archived_at}]};
            }
            if(url.includes('/actions/')){
              const action=url.split('/').pop(),selected=data.items.filter(item=>body.ids.includes(item.id));
              if(selected.some(item=>body.revisions[item.id]!==item.revision))throw new Error('Stale revision');
              for(const item of selected){
                if(action==='archive'){if(!item.can_archive)throw new Error('Not archivable');item.archived_at='2026-09-26T12:00:00Z';item.can_archive=false;}
                else if(action==='restore'){item.archived_at=null;item.can_archive=true;}
                else if(action==='duplicate'){
                  const copy=structuredClone(item);copy.id='factory-new-copy';copy.status='preparation';copy.archived_at=null;copy.can_archive=false;
                  delete copy.delivery;data.items.push(copy);
                }else throw new Error('Unexpected action '+action);
                item.revision++;
              }
            }else if(url!=='/api/video-factory')throw new Error('Unexpected URL '+url);
            return structuredClone(data);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
            const row=id=>document.querySelector('[data-vf-id="'+id+'"]');
            const count=tab=>document.querySelector('[data-vf-tab="'+tab+'"] span').textContent;
            const selectAll=()=>{const all=document.getElementById('vf-select-all');all.checked=true;all.dispatchEvent(new Event('change'));};
            const original=JSON.stringify(data.items[0].steps);
            await settle();await window.PanelForgeVideoFactory.open([ids[0]]);await settle();
            const stickyHeader=document.querySelector('.vf-sticky-header');
            check(getComputedStyle(stickyHeader).position==='sticky','factory heading and tabs stay sticky');
            check(stickyHeader.contains(document.getElementById('vf-refresh'))&&stickyHeader.contains(document.querySelector('.vf-tabs')),'sticky scope excludes list controls');
            const stickyToolbar=document.querySelector('.vf-toolbar');
            check(getComputedStyle(stickyToolbar).position==='sticky','selection and preset toolbar stays sticky');
            check(parseFloat(getComputedStyle(stickyToolbar).top)>parseFloat(getComputedStyle(stickyHeader).top),'selection toolbar stacks below heading');
            check(!document.getElementById('vf-machines')&&!document.getElementById('vf-monitor-alerts'),'factory temperature panels removed');
            check(stickyHeader.contains(document.getElementById('vf-monitor-summary'))&&stickyHeader.contains(document.getElementById('vf-monitor-preview')),'compact forecasts share the heading');
            check(document.querySelectorAll('.vf-tabs [data-vf-tab]').length===4,'four main tabs');
            check(count('results')==='3'&&count('archives')==='1','separate initial counters');
            const grid=row(ids[0]).querySelector('.vf-result-actions');
            check(getComputedStyle(grid).display==='grid','compact action grid');
            check(getComputedStyle(grid).gridTemplateColumns.split(/\s+/).length===(innerWidth>700?3:2),'responsive columns');
            check(grid.firstElementChild.tagName==='STRONG','status shares the first row');
            check(!row(ids[2]).querySelector('[data-vf-archive]'),'failure has no archive action');
            selectAll();check(document.getElementById('vf-archive').disabled,'mixed selection cannot hide failures');
            const filter=document.getElementById('vf-filter');filter.value='archivable';filter.dispatchEvent(new Event('change'));
            check(document.querySelectorAll('#vf-rows [data-vf-id]').length===2,'archivable filter');
            selectAll();document.getElementById('vf-archive').click();await settle();
            check(count('results')==='1'&&count('archives')==='3','archiving clears results counter');
            check(!document.querySelector('#vf-inspector [data-vf-action="archive"]'),'archived inspector leaves current results');
            document.querySelector('[data-vf-tab="results"]').click();await settle();
            check(row(ids[2])&&!row(ids[0]),'only failure remains in results');
            await window.PanelForgeVideoFactory.send({source_kind:'episode',source_id:'english-copy'});await settle();
            check(document.getElementById('vf-notice').textContent.includes('Déjà archivé'),'explicit archived duplicate');
            document.querySelector('#vf-notice button').click();await settle();
            check(document.querySelector('[data-vf-tab="archives"]').classList.contains('active'),'receipt opens archives');
            check(document.getElementById('vf-filter').value==='all','old results filter cleared');
            check(row(ids[0]).querySelectorAll('[data-vf-duration]').length===5,'durations preserved in archives');
            check(!document.querySelector('#vf-inspector [data-vf-action="edit"]'),'restore first before changing archived record');
            row(ids[0]).querySelector('[data-vf-result="social"]').click();await settle();
            check(document.getElementById('vf-detail-content').textContent.includes('Ready 🌱'),'IG text accessible in archives');
            document.querySelector('#vf-detail-dialog [data-vf-close]').click();
            row(ids[0]).querySelector('[data-vf-folder]').click();await settle();
            check(calls.some(([url])=>url.endsWith('/open-folder')),'folder stays accessible');
            row(ids[0]).querySelector('[data-vf-restore]').click();await settle();
            check(document.querySelector('[data-vf-tab="results"]').classList.contains('active'),'restore opens results');
            check(count('results')==='2'&&count('archives')==='2','restore updates both counters');
            check(JSON.stringify(data.items[0].steps)===original,'restoration does not reset chain');
            document.querySelector('[data-vf-tab="archives"]').click();await settle();selectAll();
            document.getElementById('vf-restore').click();await settle();
            check(count('archives')==='0'&&count('results')==='4','bulk restore');
            row(ids[0]).querySelector('[data-vf-archive]').click();await settle();
            await window.PanelForgeVideoFactory.open([ids[0]]);await settle();
            document.querySelector('#vf-inspector [data-vf-action="duplicate"]').click();await settle();
            check(document.querySelector('[data-vf-tab="preparation"]').classList.contains('active'),'duplicate opens preparation');
            check(row('factory-new-copy'),'duplicate is selected and visible');
            check(data.items.find(item=>item.id===ids[0]).archived_at,'original stays archived');
            check(!calls.some(([url])=>/launch|generate|retry/.test(url)),'archive restore duplicate never launch generation');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        css = (STATIC / 'video-factory.css').read_text(encoding='utf-8') + (STATIC / 'video-factory-monitor.css').read_text(encoding='utf-8')
        self.run_browser(browsers[-1], '<meta charset="utf-8"><style>'+css+'</style><span id="vf-nav-errors"></span>' + markup +
            '<pre id="result">PENDING</pre><script>' + bootstrap +
            (STATIC / 'video-factory.js').read_text(encoding='utf-8') + scenario + '</script>')


if __name__ == "__main__": unittest.main()
