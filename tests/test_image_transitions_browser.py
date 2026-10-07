"""User-run browser interaction test with an in-page fake API only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from panelforge.domain.image_transitions import defaults, KINDS, pace_presets
from panelforge.domain.image_transition_references import crew_catalog

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class ImageTransitionBrowserTest(unittest.TestCase):
    def test_direct_send_drafts_disabled_states_and_factory_handoff(self):
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        browsers = [*cache.glob("chromium-*/chrome-win/chrome.exe"),
                    *cache.glob("chromium-*/chrome-win64/chrome.exe")]
        chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        if not browsers and chrome.is_file():
            browsers = [chrome]
        if not browsers:
            self.skipTest("Chromium local non installé")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        marker = '<main id="image-transitions-workspace"'
        markup = marker + html.split(marker, 1)[1].split('<main id="video-factory-workspace"', 1)[0]
        markup = markup.replace('class="vf-workspace it-workspace" hidden', 'class="vf-workspace it-workspace"', 1)
        code = (STATIC / "image-transitions.js").read_text(encoding="utf-8").replace(
            'const asset = id => "/api/assets/" + encodeURIComponent(id) + "/content";',
            'const asset = id => window.fixtureImage;')
        references_code = (STATIC / "image-transition-references.js").read_text(encoding="utf-8")
        fixture = r"""
        const check=(value,text)=>{if(!value)throw Error(text);};
        window.fixtureImage="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
        const settings=__SETTINGS__, kinds=__KINDS__, pacePresets=__PACE_PRESETS__, crews=__CREWS__;
        const pristineDefaults=structuredClone(settings);
        const worker={asset_id:"worker1",label:"Ouvrier sauvegardé",dimensions:[100,400]};
        const calls=[],opened=[];
        const frames=[1,2,3].map(i=>({id:"f"+i,asset_id:"asset-"+i,label:"Image "+i,dimensions:[1600,900],origin:{engine:"upload"}}));
        const transitions=[1,2].map(i=>({id:"t"+i,left:"f"+i,right:"f"+(i+1),
          action:"",note:"",intention:"",kind:"work",duration:null,camera:"",state:"empty",
          effective:settings,observations:"",uncertainties:"",factory_ids:[],manual:false,suggestion:null}));
        let p={id:"frieze-fixture",name:"Arbre",version:1,settings,frames,transitions,jobs:[],factory_items:[]};
        const oldProject=structuredClone(p);oldProject.id="frieze-old";oldProject.name="Ancienne frise";oldProject.settings.worker="";
        sessionStorage.setItem("panelforge.transitions.project",oldProject.id);
        let restorationStarted=false,releaseRestore;
        const restoreGate=new Promise(resolve=>releaseRestore=resolve);
        window.PanelForgeLabNavigation={switchView:()=>true};
        window.PanelForgeVideoFactory={open:async(ids=[])=>opened.push(ids)};
        window.PanelForgeLabCore={request:async(url,options={})=>{
          const method=options.method||"GET",body=options.body?JSON.parse(options.body):null;
          calls.push({url,method,body});
          const result=value=>structuredClone(value);
          if(url.endsWith("/spec"))return result({defaults:pristineDefaults,kinds,pace_presets:pacePresets,crews,visual_references:true,direct_send:true,aspect_ratios:["16:9 (Widescreen)"]});
          if(url.endsWith("/models"))return result({models:[{id:settings.model_id,source:"local",label:"Fake vision"}]});
          if(url.endsWith("/projects")&&method==="GET")return result({projects:[
            {id:p.id,name:p.name,image_count:p.frames.length},{id:oldProject.id,name:oldProject.name,image_count:oldProject.frames.length}]});
          if(url.endsWith("/projects")&&method==="POST"){
            p={id:"frieze-created",name:body.name,version:1,settings:structuredClone(pristineDefaults),
              frames:[],transitions:[],jobs:[],factory_items:[]};
            return result({project:p});
          }
          if(url.includes("/library/krea")&&!url.includes("/krea/source"))return result({projects:[{id:"source",name:"KREA project"}]});
          if(url.endsWith("/library/krea/source"))return result({images:[
            {key:"stage:attempt1",asset_id:"asset-version1",label:"Version 1",accepted:false},
            {key:"stage:attempt2",asset_id:"asset-version2",label:"Version 2",accepted:true}]});
          if(url.endsWith("/worker-library"))return result({saved:[worker],recent:[],warnings:[]});
          if(method==="GET"&&url.endsWith("/projects/"+oldProject.id)){
            restorationStarted=true;await restoreGate;return result({project:oldProject});
          }
          if(method==="GET")return result({project:p});
          check(body.version===p.version,"every mutation uses current revision");
          if(url.endsWith("/worker")){
            p.worker_reference=body.asset_id?worker:null;
            p.transitions.forEach(t=>{t.visual_references={worker:p.worker_reference};});
          }else if(url.endsWith("/scale")){
            const scale={id:"scale1",asset_id:"scale-image",dimensions:[1600,900],label:"Échelle",placement:body.position};
            p.scale_setups={scale1:scale};
            p.transitions.forEach(t=>{t.scale_setup_id=scale.id;t.visual_references={worker,scale,mode:"ref2v"};});
          }else if(method==="PATCH"&&url.includes("/transitions/")){
            const t=p.transitions.find(t=>url.endsWith("/"+t.id));Object.assign(t,body.changes);
            t.state=t.intention?"review":"empty";
          }else if(url.endsWith("/proposals")){
            for(const id of body.ids){const t=p.transitions.find(t=>t.id===id);t.intention="Travail proposé pour "+id;t.action="Poser une porte";t.state="review";}
          }else if(url.endsWith("/review")){
            throw Error("The UI must never request a separate review");
          }else if(url.endsWith("/send")){
            let added=0;
            const ids=body.ids.map(id=>{
              const t=p.transitions.find(t=>t.id===id);check(!!t.intention.trim(),"send needs an intention");
              if(t.state!=="sent"){
                added++;t.factory_ids.push("factory-"+id+(t.factory_ids.length?"-v"+(t.factory_ids.length+1):""));
              }
              t.state="sent";return t.factory_ids.at(-1);
            });
            p.version++;return result({project:p,ids,added});
          }else if(url.endsWith("/order")){
            p.frames=body.ids.map(id=>p.frames.find(f=>f.id===id));
          }else if(url.endsWith("/frames/import")){
            check(body.keys[0]==="stage:attempt1","specific attempt, not latest/accepted");
            p.frames.push({id:"f4",asset_id:"asset-version1",label:"Version 1",dimensions:[1600,900]});
          }else if(method==="PATCH"){
            if(body.changes.settings)Object.assign(p.settings,body.changes.settings);
            if(body.changes.name)p.name=body.changes.name;
          }
          else throw Error("Unexpected command: "+url);
          p.version++;return result({project:p});
        }};
        """
        fixture = fixture.replace("__SETTINGS__", json.dumps(defaults(), ensure_ascii=True)).replace(
            "__KINDS__", json.dumps(KINDS, ensure_ascii=True)).replace("__PACE_PRESETS__", json.dumps(pace_presets(), ensure_ascii=True)).replace("__CREWS__", json.dumps(crew_catalog(), ensure_ascii=True))
        scenario = r"""
        (async()=>{
          const el=id=>document.getElementById("it-"+id);
          const wait=async(test)=>{for(let i=0;i<300;i++){if(test())return;await new Promise(r=>setTimeout(r,10));}throw Error("Timeout");};
          try{
            await wait(()=>restorationStarted);
            const opening=window.PanelForgeImageTransitions.open(p.id);
            releaseRestore();await opening;
            await wait(()=>el("rows").children.length===2&&!el("propose").disabled);
            check(el("projects").value===p.id,"opening requested frieze waits for pending restoration");
            const workerField=()=>document.querySelector('[data-it-setting="worker"]');
            check(workerField().value===pristineDefaults.worker,"new frieze worker default replaces old empty display");
            check(calls.every(c=>c.method==="GET"),"opening must not generate");
            check(!el("review")&&!el("inspector").querySelector("[data-it-review-one]"),"no validation buttons");
            check(el("send").disabled&&el("send-status").title.includes("intention"),"empty selection content blocks send with reason");
            el("frieze-toggle").click();
            check(!el("frieze-panel").open,"horizontal strip collapses");
            check(el("frieze-toggle").getAttribute("aria-expanded")==="false","accessible fold state");
            const pairImage=el("rows").querySelector(".it-pair img");
            check(parseFloat(getComputedStyle(pairImage).height)>=76,"pair image at least twice previous height");
            check(parseFloat(getComputedStyle(pairImage).width)>=68,"pair image at least twice previous width");
            el("people").open=true;
            el("crew").value="industrial";el("crew").dispatchEvent(new Event("input",{bubbles:true}));
            el("worker-choose").click();
            await wait(()=>el("worker-saved").querySelector("[data-it-worker-asset]")&&!el("worker-choose").disabled);
            el("worker-saved").querySelector("[data-it-worker-asset]").click();
            await wait(()=>p.worker_reference&&!el("worker-dialog").open&&!el("worker-choose").disabled);
            check(p.settings.crew_size==="industrial","crew saved before choosing reference");
            el("inspector").querySelector("[data-it-scale]").click();
            await wait(()=>el("scale-dialog").open&&!el("scale-save").disabled);
            el("scale-height").value="5";el("scale-height").dispatchEvent(new Event("input",{bubbles:true}));
            check(Math.abs(parseFloat(el("scale-piece").style.height)-5)<.01,"worker preview follows relative height");
            el("scale-save").click();
            await wait(()=>p.scale_setups&&!el("scale-dialog").open&&!el("propose").disabled);
            const scaleCall=calls.find(c=>c.url.endsWith("/scale"));
            check(scaleCall.body.position.height===.05,"normalized visual height saved");
            check(scaleCall.body.scope==="following","reuse placement by default");
            check(p.transitions.every(t=>t.scale_setup_id==="scale1"),"shared placement returned to all pairs");
            check(!el("frieze-panel").open,"fold preserved after save and repaint");
            check(el("inspector").querySelector(".it-scale-summary [data-it-zoom]"),"composition reference has zoom");
            check(!calls.some(c=>c.url.endsWith("/proposals")||c.url.endsWith("/send")),"reference setup never generates");
            const paceSelect=el("pace-preset"), paceText=document.querySelector('[data-it-setting="pace"]');
            check(paceSelect.value==="fast","new frieze defaults to Fast");
            paceSelect.value="slow";paceSelect.dispatchEvent(new Event("input",{bubbles:true}));
            check(paceText.value===pacePresets.find(p=>p.id==="slow").pace,"Slow fills canonical pace");
            paceText.value="Un rythme personnel";paceText.dispatchEvent(new Event("input",{bubbles:true}));
            check(paceSelect.value==="custom","editing pace selects Custom without losing text");
            check(paceText.value==="Un rythme personnel","custom pace preserved");
            paceSelect.value="fast";paceSelect.dispatchEvent(new Event("input",{bubbles:true}));
            check(paceText.value===pacePresets.find(p=>p.id==="fast").pace,"Fast replaces old slow text");
            paceSelect.value="slow";paceSelect.dispatchEvent(new Event("input",{bubbles:true}));
            check(!calls.some(c=>c.url.endsWith("/proposals")||c.url.endsWith("/send")),"choosing a preset does not start analysis or rendering");
            const note=el("inspector").querySelector('[data-it-field="note"]');
            note.value="Utiliser une tronçonneuse";note.dispatchEvent(new Event("input",{bubbles:true}));
            el("propose").click();
            await wait(()=>p.transitions[0].intention&&!el("send").disabled);
            check(p.transitions[0].note==="Utiliser une tronçonneuse","draft saved before analysis");
            check(p.settings.pace_preset==="slow","pace preset saved before proposal");
            check(p.settings.pace===pacePresets.find(p=>p.id==="slow").pace,"pace text and ID stay consistent");
            check(el("inspector").querySelector("[data-it-pace-summary]").textContent.includes("Slow"),"effective pace shown for review");
            check(!calls.some(c=>c.url.endsWith("/send")),"analysis cannot auto-send");
            const intention=el("inspector").querySelector('[data-it-field="intention"]');
            intention.value="Mon intention corrigée";intention.dispatchEvent(new Event("input",{bubbles:true}));
            check(!el("send").disabled,"optional correction can be sent directly");
            el("send").click();
            await wait(()=>p.transitions.every(t=>t.state==="sent")&&el("send").classList.contains("it-sent"));
            check(p.transitions[0].intention==="Mon intention corrigée","send saves the correction");
            check(p.transitions[1].intention==="Travail proposé pour t2","untouched proposal is sent directly");
            check(el("send").disabled&&el("send").querySelector(".it-send-check"),"sent selection has disabled green check");
            check(getComputedStyle(el("send").querySelector(".it-send-check")).color==="rgb(35, 128, 68)","check is green");
            check(!calls.some(c=>c.url.endsWith("/review")),"no hidden review request");
            const send=calls.find(c=>c.url.endsWith("/send"));
            check(send.body.ids.join(",")==="t1,t2","ordered selection handed off");
            el("message").querySelector("button").click();
            await wait(()=>opened.length>0);
            check(opened[0][0]==="factory-t1","opens exact factory units");
            const original=p.transitions[0].intention;
            let edit=el("inspector").querySelector('[data-it-field="intention"]');
            edit.value=" ";edit.dispatchEvent(new Event("input",{bubbles:true}));
            check(el("send").disabled&&!el("send").classList.contains("it-sent"),"blank draft blocks send and clears sent check");
            edit.value=original;edit.dispatchEvent(new Event("input",{bubbles:true}));
            check(el("send").disabled&&el("send").classList.contains("it-sent"),"reverting restores already sent version");
            edit.value=original+" Avec un petit treuil.";edit.dispatchEvent(new Event("input",{bubbles:true}));
            check(!el("send").disabled&&!el("send").classList.contains("it-sent"),"unsaved change enables new version");
            const firstCheck=el("rows").querySelector('[data-it-row="t1"] [data-it-select]');
            firstCheck.checked=false;firstCheck.dispatchEvent(new Event("change",{bubbles:true}));
            check(el("send").disabled&&el("send").classList.contains("it-sent"),"unselected draft does not change selected sent status");
            firstCheck.checked=true;firstCheck.dispatchEvent(new Event("change",{bubbles:true}));
            const duration=document.querySelector('[data-it-setting="duration"]');
            duration.value="4";duration.dispatchEvent(new Event("input",{bubbles:true}));
            check(el("send").disabled&&el("send-status").title.includes("invalides"),"invalid settings block send");
            duration.value="7";duration.dispatchEvent(new Event("input",{bubbles:true}));
            check(!el("send").disabled,"valid mixed selection enables send");
            el("send").click();
            await wait(()=>p.transitions[0].factory_ids.length===2&&el("send").classList.contains("it-sent"));
            check(p.transitions[1].factory_ids.length===1,"unchanged version not duplicated");
            check(el("message").textContent.includes("1 unité"),"mixed selection adds only missing version");
            const sends=calls.filter(c=>c.url.endsWith("/send")).length;
            el("send").click();
            check(calls.filter(c=>c.url.endsWith("/send")).length===sends,"disabled repeated send does nothing");
            el("name").value="Nouveau nom";el("name").dispatchEvent(new Event("input",{bubbles:true}));
            check(el("send").disabled&&el("send").classList.contains("it-sent"),"rename alone does not create a version");
            el("save").click();await wait(()=>p.name==="Nouveau nom"&&el("save").disabled&&!el("refresh").disabled);
            el("all").checked=false;el("all").dispatchEvent(new Event("change"));
            check(el("send").disabled&&el("send-status").title.includes("Sélectionne"),"empty selection has reason");
            el("all").checked=true;el("all").dispatchEvent(new Event("change"));
            p.transitions[0].visual_references.error="Le décor de référence a changé.";
            el("refresh").click();await wait(()=>!el("refresh").disabled&&el("send-status").title.includes("décor"));
            check(el("send").disabled,"obsolete scale blocks send");
            p.transitions[0].visual_references.error=null;
            p.transitions[0].needs_visual_refresh=true;
            el("refresh").click();await wait(()=>!el("refresh").disabled&&el("send-status").title.includes("Repropose"));
            check(el("send").disabled,"old visual intention blocks send");
            p.transitions[0].needs_visual_refresh=false;
            p.jobs=[{status:"running",completed:0,total:2}];
            el("refresh").click();await wait(()=>!el("refresh").disabled&&el("send-status").title.includes("fin de l’analyse"));
            check(el("send").disabled,"active analysis blocks send");
            p.jobs=[];
            el("refresh").click();await wait(()=>!el("refresh").disabled&&el("send").classList.contains("it-sent"));
            el("inspector").querySelector("[data-it-zoom]").click();
            check(el("image-dialog").open,"large comparison image available");
            el("image-dialog").close();
            el("library").click();
            await wait(()=>el("library-images").querySelectorAll("input").length===2&&!el("library-add").disabled);
            el("library-images").querySelector("input").checked=true;
            el("library-add").click();
            await wait(()=>p.frames.length===4&&!el("library-dialog").open);
            check(p.frames[3].asset_id==="asset-version1","exact version retained");
            el("worker-clear").click();
            await wait(()=>!p.worker_reference&&!workerField().disabled&&!el("worker-choose").disabled);
            check(workerField().value===pristineDefaults.worker,"removing image restores saved text default");
            workerField().value="";workerField().dispatchEvent(new Event("input",{bubbles:true}));
            el("save").click();await wait(()=>p.settings.worker===""&&el("save").disabled&&!el("refresh").disabled);
            el("refresh").click();await wait(()=>!el("refresh").disabled);
            check(workerField().value==="","an explicitly emptied saved field stays empty");
            delete p.settings.worker;
            el("refresh").click();await wait(()=>!el("refresh").disabled&&workerField().value===pristineDefaults.worker);
            check(!el("save").disabled,"missing-field fallback is a visible draft to persist");
            el("save").click();await wait(()=>p.settings.worker===pristineDefaults.worker&&el("save").disabled&&!el("refresh").disabled);
            workerField().value="Une équipe de menuisiers selon ma description.";
            workerField().dispatchEvent(new Event("input",{bubbles:true}));
            el("save").click();await wait(()=>p.settings.worker.startsWith("Une équipe")&&el("save").disabled&&!el("refresh").disabled);
            el("refresh").click();await wait(()=>!el("refresh").disabled);
            check(workerField().value===p.settings.worker,"personal worker description survives reopening");
            el("new").click();await wait(()=>p.id==="frieze-created"&&!el("new").disabled);
            check(workerField().value===pristineDefaults.worker,"new frieze gets server default without previous custom draft");
            document.body.innerHTML='<pre id="result">IMAGE_TRANSITIONS_BROWSER_OK</pre>';
          }catch(error){
            document.body.innerHTML='<pre id="result"></pre>';
            document.getElementById("result").textContent=error.stack;
          }
        })();
        """
        css = (STATIC / "image-transitions.css").read_text(encoding="utf-8")
        document = ('<!doctype html><html><head><meta charset="utf-8"><style>' + css +
                    '</style></head><body>' + markup + '<script>' + fixture +
                    '</script><script>' + references_code + '</script><script>' + code + '</script><script>' + scenario + '</script></body></html>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transitions.html"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run([str(browsers[0]), "--headless", "--disable-gpu", "--no-sandbox",
                "--disable-background-networking", "--allow-file-access-from-files",
                "--user-data-dir=" + str(Path(directory) / "browser-profile"),
                "--window-size=1440,1100", "--virtual-time-budget=15000", "--dump-dom", path.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        self.assertIn('<pre id="result">IMAGE_TRANSITIONS_BROWSER_OK</pre>', result.stdout)
