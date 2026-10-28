"""User-run real loader/navigation with script downloads and public APIs faked.

No application server, media, model calls or generation are used.
"""
import os
from pathlib import Path
import re
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class WorkshopLoaderBrowserTests(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def scenario(self, scenario, saved="krea2-assisted-lab"):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        if not browsers and chrome.is_file():
            browsers = [chrome]
        if not browsers:
            self.skipTest("local Chromium or Chrome not installed")
        templates = "".join(re.findall(r"<template\b.*?</template>", (STATIC / "index.html").read_text(encoding="utf-8"), re.S))
        modes = ["krea2-assisted-lab", "mh-assisted-lab", "krea2-edit-lab", "qwen-edit-lab", "minimax-edit-lab", "image-journey", "creation-batch"]
        markup = '<meta charset="utf-8">' + templates + '<header class="topbar"></header><pre id="result">PENDING</pre>'
        markup += '<button data-lab-view="change-view">Image</button><button data-lab-view="recipes">Recipes</button>'
        markup += ''.join(f'<button data-image-lab-mode="{mode}">{mode}</button><main id="{mode}-workspace" hidden></main>' for mode in modes)
        markup += '<main id="recipes-workspace" hidden></main><main id="stories-workspace" hidden></main>'
        bootstrap = r"""
          window.fetch=()=>{throw new Error('Network forbidden in loader fixture');};
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setTimeout(r,0));};
          const downloads=[], waiting=[], calls=[], ready=[];
          document.addEventListener('panelforge:workshop-ready',e=>ready.push(e.detail.view));
          const exports={
            'krea2-edit-lab.js':{PanelForgeKrea2Edit:['openSourceId']},
            'qwen-edit-v2.js':{PanelForgeQwenEdit:['open'],PanelForgeMinimaxEdit:['open']},
            'recipes.js':{PanelForgeRecipes:['open','fromImage']},
            'i2v-direct.js':{PanelForgeH3Base:['open','prefillFirstFrame','prefillAnalysis']},
            'ref2v-direct.js':{PanelForgeRef2V:['open','prefillAnalysis']},
            'stories.js':{PanelForgeStories:['open']},
            'episodes.js':{PanelForgeEpisodes:['prepareLibraryNavigation','openFromLibrary']},
          };
          const append=document.head.append.bind(document.head);
          document.head.append=(node)=>{
            if(node.tagName!=='SCRIPT')return append(node);
            const file=new URL(node.src).pathname.split('/').pop();downloads.push(file);waiting.push({file,node});
          };
          const finish=async(fail=false)=>{
            const entry=waiting.shift();check(entry,'a download is pending');
            if(fail)entry.node.onerror();
            else {
              for(const [name,methods] of Object.entries(exports[entry.file]||{})) {
                window[name]=Object.fromEntries(methods.map(method=>[method,async(...args)=>{
                  calls.push([name,method,args]);return args[0];
                }]));
              }
              entry.node.onload();
            }
            await settle();return entry.file;
          };
          const drain=async()=>{for(let i=0;i<60&&waiting.length;i++)await finish();};
        """
        source = (STATIC / "workshop-loader.js").read_text(encoding="utf-8")
        core = (STATIC / "lab-core.js").read_text(encoding="utf-8")
        setup = f"sessionStorage.setItem('panelforge.lab.last-view.v1','{saved}');"
        harness = "document.addEventListener('DOMContentLoaded',async()=>{try{await settle();" + scenario + ";document.querySelector('#result').textContent='PASS';}catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}});"
        self.run_browser(browsers[-1], markup + '<script>' + setup + bootstrap + source + core + harness + '</script>')

    def test_mh_loads_once_without_loading_edit_or_video_workshops(self):
        self.scenario(r"""
          check(downloads.join(',')==='mh-assisted.js','only MH is downloaded on restoration');
          const root=document.querySelector('#mh-assisted-lab-workspace');
          check(!root.hidden&&root.inert,'restored MH waits for its bindings');
          await drain();check(!root.inert,'MH becomes interactive');
          document.querySelector('[data-image-lab-mode="krea2-assisted-lab"]').click();
          document.querySelector('[data-image-lab-mode="mh-assisted-lab"]').click();await settle();
          check(downloads.length===1,'returning to MH does not execute its script twice');
        """, saved="mh-assisted-lab")

    def test_first_click_blocks_unbound_controls_and_concurrent_clicks_share_downloads(self):
        self.scenario(r"""
          check(downloads.length===0,'unvisited workshops do not download');
          const root=document.querySelector('#krea2-edit-lab-workspace');
          const button=document.querySelector('[data-image-lab-mode="krea2-edit-lab"]');
          button.click();button.click();await settle();
          check(root.inert&&!root.hidden,'unbound controls cannot lose clicks');
          check(downloads.join(',')==='krea2-retouch.js','shared in-flight request');
          await drain();
          check(downloads.join(',')==='krea2-retouch.js,image-crop.js,krea2-edit-lab.js','dependency order');
          check(!root.inert&&ready.join(',')==='krea2-edit-lab','first click activates once');
          button.click();await settle();check(downloads.length===3,'loaded files never execute twice');
        """)

    def test_failed_download_retries_only_missing_file_and_preserves_navigation(self):
        self.scenario(r"""
          const root=document.querySelector('#krea2-edit-lab-workspace');
          document.querySelector('[data-image-lab-mode="krea2-edit-lab"]').click();await settle();
          await finish();await finish(true);
          check(root.inert&&!root.previousElementSibling.querySelector('button').hidden,'failure offers retry');
          root.previousElementSibling.querySelector('button').click();await settle();
          document.querySelector('[data-image-lab-mode="krea2-assisted-lab"]').click();
          await drain();
          check(root.hidden&&!root.inert&&ready.length===0,'late completion cannot change selected view');
          check(downloads.filter(x=>x==='krea2-retouch.js').length===1,'successful dependency is retained');
          check(downloads.filter(x=>x==='image-crop.js').length===2,'only failed download retried');
        """)

    def test_restored_workshop_loads_and_shared_qwen_bundle_only_runs_once(self):
        self.scenario(r"""
          const qwen=document.querySelector('#qwen-edit-lab-workspace');
          check(!qwen.hidden&&qwen.inert,'restored workshop waits for bindings');
          document.querySelector('[data-image-lab-mode="minimax-edit-lab"]').click();await settle();
          await drain();
          check(downloads.join(',')==='qwen-edit-v2.js','both views share their implementation');
          check(qwen.hidden&&!document.querySelector('#minimax-edit-lab-workspace').inert,'latest navigation wins');
          check(ready.join(',')==='minimax-edit-lab','stale restored view not activated');
        """, saved="qwen-edit-lab")

    def test_partial_execution_failure_requires_reload_without_duplicate_handlers(self):
        self.scenario(r"""
          document.querySelector('[data-image-lab-mode="krea2-edit-lab"]').click();await settle();
          await finish();await finish();
          const entry=waiting.shift();
          window.dispatchEvent(new ErrorEvent('error',{filename:entry.node.src,message:'fixture failure'}));
          entry.node.onload();await settle();
          const root=document.querySelector('#krea2-edit-lab-workspace');
          check(root.inert&&root.previousElementSibling.textContent.includes('Rechargez'),'partial execution is explicit');
          root.previousElementSibling.querySelector('button').click();await settle();
          check(downloads.length===3&&waiting.length===0,'partly executed script is never executed twice');
        """)

    def test_transfers_forward_once_and_retry_does_not_replay_user_action(self):
        self.scenario(r"""
          const original=window.PanelForgeRecipes;
          const failed=original.fromImage('asset-a','name').catch(e=>e.message);await settle();
          await finish(true);check((await failed).includes('recipes.js'),'download error is reported');
          check(calls.length===0,'failed load cannot send transfer');
          document.querySelector('[role="alert"] button').click();await settle();await finish();
          check(calls.length===0,'retry loads scripts without replaying the action');
          check(await original.fromImage('asset-a','name')==='asset-a','cached facade still forwards');
          check(calls.length===1&&calls[0][2][1]==='name','arguments and one command preserved');
        """)

    def test_legacy_story_dependencies_load_before_open_without_replaying_navigation(self):
        self.scenario(r"""
          const promise=window.PanelForgeStories.open('story-a');await settle();await drain();await promise;
          check(downloads.indexOf('h3-render-lab.js')<downloads.indexOf('stories.js'),'video renderer before episodes');
          check(downloads.indexOf('stories.js')<downloads.indexOf('episodes.js'),'story API before episodes');
          check(downloads.indexOf('episodes.js')<downloads.indexOf('story-library.js'),'library last');
          check(calls.length===1&&calls[0][2][0]==='story-a','open forwarded exactly once');
          check(!document.querySelector('#krea2-assisted-lab-workspace').hidden,'loading alone does not navigate');
        """)

    def test_video_public_transfer_waits_for_the_shared_initial_discovery(self):
        blocks = []
        for filename, name in [("i2v-direct.js", "PanelForgeH3Base"), ("ref2v-direct.js", "PanelForgeRef2V")]:
            source = (STATIC / filename).read_text(encoding="utf-8")
            initializer = source[source.index("  let initialization = null;"):source.index("  async function initializeWorkshop()")]
            start = source.index("  window." + name + " = Object.freeze(")
            public_api = source[start:source.index("  } });", start) + len("  } });")]
            blocks.append(r"""{
              const state={spec:null,cookbook:null};let discoveries=0,release;
              const transfers=[];
              async function initializeWorkshop(){discoveries++;await new Promise(r=>release=r);state.spec={};state.cookbook={};}
              const prefillAnalysis=value=>{transfers.push(value);return value;};
              const prefillFirstFrame=prefillAnalysis;
            """ + initializer + public_api + r"""
              const initial=initialize(), payload={intention:'preserved input'};
            """ + f"const api=window.{name};" + r"""
              const transfer=api.prefillAnalysis(payload);await settle();
              check(discoveries===1&&transfers.length===0,'first transfer waits for the existing discovery');
              release();await initial;check(await transfer===payload,'same transfer payload forwarded');
              check(transfers.length===1,'transfer performed once');
              await api.prefillAnalysis(payload);
              check(discoveries===1,'ready destination does not repeat discovery');
            }""")
        self.scenario("\n".join(blocks))


if __name__ == "__main__":
    unittest.main()
