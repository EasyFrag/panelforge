"""User-run browser interaction test with an in-page fake API only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from panelforge.domain.image_transitions import defaults, KINDS

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class ImageTransitionBrowserTest(unittest.TestCase):
    def test_review_drafts_frozen_images_library_and_factory_handoff(self):
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
        fixture = r"""
        const check=(value,text)=>{if(!value)throw Error(text);};
        window.fixtureImage="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
        const settings=__SETTINGS__, kinds=__KINDS__;
        const calls=[],opened=[];
        const frames=[1,2,3].map(i=>({id:"f"+i,asset_id:"asset-"+i,label:"Image "+i,dimensions:[1600,900],origin:{engine:"upload"}}));
        const transitions=[1,2].map(i=>({id:"t"+i,left:"f"+i,right:"f"+(i+1),
          action:"",note:"",intention:"",kind:"work",duration:null,camera:"",state:"empty",
          effective:settings,observations:"",uncertainties:"",factory_ids:[],manual:false,suggestion:null}));
        const p={id:"frieze-fixture",name:"Arbre",version:1,settings,frames,transitions,jobs:[],factory_items:[]};
        window.PanelForgeLabNavigation={switchView:()=>true};
        window.PanelForgeVideoFactory={open:async(ids=[])=>opened.push(ids)};
        window.PanelForgeLabCore={request:async(url,options={})=>{
          const method=options.method||"GET",body=options.body?JSON.parse(options.body):null;
          calls.push({url,method,body});
          const result=value=>structuredClone(value);
          if(url.endsWith("/spec"))return result({defaults:settings,kinds,aspect_ratios:["16:9 (Widescreen)"]});
          if(url.endsWith("/models"))return result({models:[{id:settings.model_id,source:"local",label:"Fake vision"}]});
          if(url.endsWith("/projects")&&method==="GET")return result({projects:[{id:p.id,name:p.name,image_count:p.frames.length}]});
          if(url.includes("/library/krea")&&!url.includes("/krea/source"))return result({projects:[{id:"source",name:"KREA project"}]});
          if(url.endsWith("/library/krea/source"))return result({images:[
            {key:"stage:attempt1",asset_id:"asset-version1",label:"Version 1",accepted:false},
            {key:"stage:attempt2",asset_id:"asset-version2",label:"Version 2",accepted:true}]});
          if(method==="GET")return result({project:p});
          check(body.version===p.version,"every mutation uses current revision");
          if(method==="PATCH"&&url.includes("/transitions/")){
            const t=p.transitions.find(t=>url.endsWith("/"+t.id));Object.assign(t,body.changes);
            t.state=t.intention?"review":"empty";
          }else if(url.endsWith("/proposals")){
            for(const id of body.ids){const t=p.transitions.find(t=>t.id===id);t.intention="Travail proposé pour "+id;t.action="Poser une porte";t.state="review";}
          }else if(url.endsWith("/review")){
            body.ids.forEach(id=>{const t=p.transitions.find(t=>t.id===id);check(!!t.intention,"review needs intention");t.state="ready";});
          }else if(url.endsWith("/send")){
            body.ids.forEach(id=>{const t=p.transitions.find(t=>t.id===id);check(["ready","sent"].includes(t.state),"review before send");t.state="sent";t.factory_ids=["factory-"+id];});
            p.version++;return result({project:p,ids:body.ids.map(id=>"factory-"+id),added:body.ids.length});
          }else if(url.endsWith("/order")){
            p.frames=body.ids.map(id=>p.frames.find(f=>f.id===id));
          }else if(url.endsWith("/frames/import")){
            check(body.keys[0]==="stage:attempt1","specific attempt, not latest/accepted");
            p.frames.push({id:"f4",asset_id:"asset-version1",label:"Version 1",dimensions:[1600,900]});
          }else if(method==="PATCH"){Object.assign(p,body.changes);}
          else throw Error("Unexpected command: "+url);
          p.version++;return result({project:p});
        }};
        """
        fixture = fixture.replace("__SETTINGS__", json.dumps(defaults(), ensure_ascii=True)).replace(
            "__KINDS__", json.dumps(KINDS, ensure_ascii=True))
        scenario = r"""
        (async()=>{
          const el=id=>document.getElementById("it-"+id);
          const wait=async(test)=>{for(let i=0;i<300;i++){if(test())return;await new Promise(r=>setTimeout(r,10));}throw Error("Timeout");};
          try{
            await wait(()=>el("rows").children.length===2&&!el("propose").disabled);
            check(calls.every(c=>c.method==="GET"),"opening must not generate");
            const note=el("inspector").querySelector('[data-it-field="note"]');
            note.value="Utiliser une tronçonneuse";note.dispatchEvent(new Event("input",{bubbles:true}));
            el("propose").click();
            await wait(()=>p.transitions[0].intention&&!el("review").disabled);
            check(p.transitions[0].note==="Utiliser une tronçonneuse","draft saved before analysis");
            check(!calls.some(c=>c.url.endsWith("/send")),"analysis cannot auto-send");
            const intention=el("inspector").querySelector('[data-it-field="intention"]');
            intention.value="Mon intention corrigée";intention.dispatchEvent(new Event("input",{bubbles:true}));
            el("review").click();
            await wait(()=>p.transitions.every(t=>t.state==="ready")&&!el("send").disabled);
            check(p.transitions[0].intention==="Mon intention corrigée","review preserves correction");
            el("send").click();
            await wait(()=>p.transitions.every(t=>t.state==="sent")&&!el("send").disabled);
            const send=calls.find(c=>c.url.endsWith("/send"));
            check(send.body.ids.join(",")==="t1,t2","ordered selection handed off");
            el("message").querySelector("button").click();
            await wait(()=>opened.length>0);
            check(opened[0][0]==="factory-t1","opens exact factory units");
            el("inspector").querySelector("[data-it-zoom]").click();
            check(el("image-dialog").open,"large comparison image available");
            el("image-dialog").close();
            el("library").click();
            await wait(()=>el("library-images").querySelectorAll("input").length===2&&!el("library-add").disabled);
            el("library-images").querySelector("input").checked=true;
            el("library-add").click();
            await wait(()=>p.frames.length===4&&!el("library-dialog").open);
            check(p.frames[3].asset_id==="asset-version1","exact version retained");
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
                    '</script><script>' + code + '</script><script>' + scenario + '</script></body></html>')
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
