"""User-run browser regressions. No application server, models or media network."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class NavigationAndResourcePreviewBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def browser(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        return browsers[-1]

    def test_reload_keeps_workshop_submode_and_initializes_only_the_restored_mode(self):
        markup = '''<meta charset="utf-8"><pre id="result">PENDING</pre>
        <button data-lab-view="change-view">Image</button><button data-lab-view="i2v-direct">H3</button>
        <button data-lab-view="ref2v-direct">REF</button><button data-lab-view="video-lab">Video</button>
        <button data-image-lab-mode="krea2-assisted-lab">Assisted</button>
        <button data-image-lab-mode="krea2-edit-lab">Edit</button>
        <button data-video-lab-mode="media-analysis">Analysis</button>
        <button data-video-lab-mode="social-lab">Social</button>
        <section id="krea2-assisted-lab-workspace"></section><section id="krea2-edit-lab-workspace" hidden></section>
        <section id="i2vd-workspace" hidden></section><section id="ref2vd-workspace" hidden></section>
        <section id="media-analysis-workspace" hidden></section><section id="social-lab-workspace" hidden></section>
        <section id="video-lab-workspace" hidden></section>'''
        source = (STATIC / "lab-core.js").read_text(encoding="utf8")
        scenario = """
          const key='panelforge.lab.last-view.v1', phase=Number(sessionStorage.getItem('test.phase')||0);
          const visits=[];
          // Mimic modules registering their lazy initialization after lab-core.
          document.querySelectorAll('[data-image-lab-mode],[data-video-lab-mode]').forEach(button=>{
            button.addEventListener('click',()=>{
              const view=button.dataset.imageLabMode||button.dataset.videoLabMode;
              window.PanelForgeLabNavigation.switchView(view); visits.push(view);
            });
          });
          const visible=()=>[...document.querySelectorAll('section')].filter(s=>!s.hidden).map(s=>s.id);
          const expected=['krea2-assisted-lab-workspace','krea2-edit-lab-workspace','media-analysis-workspace','ref2vd-workspace','krea2-assisted-lab-workspace'][phase];
          const early=visible().join(',')===expected;
          document.addEventListener('DOMContentLoaded',()=>{try{
            const check=(value,message)=>{if(!value)throw new Error(message);};
            check(early,'restored visibility is set before workshop scripts initialize');
            check(visible().join(',')===expected,'only expected workspace visible after reload');
            check(visits.join(',')===['krea2-assisted-lab','krea2-edit-lab','media-analysis','','krea2-assisted-lab'][phase], 'only restored lazy mode initialized; no extra H3 or REF refresh');
            if(phase===0) document.querySelector('[data-image-lab-mode="krea2-edit-lab"]').click();
            if(phase===1) document.querySelector('[data-video-lab-mode="media-analysis"]').click();
            if(phase===2) {
              check(document.querySelector('[data-lab-view="video-lab"]').classList.contains('active'),'Video Lab parent active');
              check(document.querySelector('[data-video-lab-mode="media-analysis"]').classList.contains('active'),'analysis submode active');
              window.PanelForgeLabNavigation.switchView('ref2v-direct');
            }
            if(phase===3) {
              check(sessionStorage.getItem(key)==='ref2v-direct','programmatic navigation persisted');
              window.PanelForgeLabNavigation.switchView('nonexistent-page');
              check(visible().join(',')===expected,'unknown navigation never blanks the page');
              sessionStorage.setItem(key,'removed-page');
            }
            if(phase<4) {sessionStorage.setItem('test.phase',String(phase+1));location.reload();return;}
            Object.defineProperty(window,'sessionStorage',{get(){throw new Error('storage blocked');},configurable:true});
            window.PanelForgeLabNavigation.switchView('i2v-direct');
            check(visible().join(',')==='i2vd-workspace','navigation still works when storage writes fail');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}});
        """
        self.run_browser(self.browser(), markup + '<script>' + source + '</script><script>' + scenario + '</script>')

    def test_resource_card_uses_video_players_for_cached_mp4s_and_releases_them(self):
        source = (STATIC / "krea2-resource-ui.js").read_text(encoding="utf8")
        scenario = """
        (async()=>{try {
          const check=(value,message)=>{if(!value)throw new Error(message);};
          window.fetch=()=>{throw new Error('No network from the fixture');};
          const released=[];
          HTMLMediaElement.prototype.pause=function(){released.push(this);};
          HTMLMediaElement.prototype.load=function(){};
          const resource={resource_id:'fixture',kind:'lora',comfy_name:'minmax_nsfw/Motion.safetensors',
            favorite:false,display_name:'Motion fixture',preview_urls:[
              'https://example.com/first.MP4?token=fixture','https://example.com/still.jpg',
              'https://example.com/second.webm','https://example.com/ignored.mp4']};
          window.PanelForgeKrea2ResourceUi.openResourceInfo(resource);
          let dialog=document.querySelector('dialog');
          const videos=[...dialog.querySelectorAll('video')];
          check(videos.length===2 && dialog.querySelectorAll('img').length===1,'old URL-only cache supports mixed images/videos, three previews max');
          check(videos.every(v=>v.controls && v.playsInline && v.muted && !v.autoplay && v.preload==='metadata'),'video controls, inline, muted, no autoplay or eager full download');
          check(videos[0].src.endsWith('first.MP4?token=fixture'),'case and query string preserved');
          videos[0].dispatchEvent(new Event('error'));
          check(!videos[0].parentElement.querySelector('[role=status]').hidden,'failed media has a visible explanation');
          check(videos[0].parentElement.querySelector('a').href===videos[0].src,'direct video link remains available');
          [...dialog.querySelectorAll('button')].find(b=>b.textContent==='Fermer').click();
          await new Promise(resolve=>setTimeout(resolve,0));
          check(videos.every(v=>released.includes(v) && !v.hasAttribute('src')),'close pauses videos and releases media sources');
          window.PanelForgeKrea2ResourceUi.openResourceInfo({...resource,preview_urls:['https://example.com/still.webp']});
          dialog=document.querySelector('dialog');
          check(dialog.querySelectorAll('img').length===1 && !dialog.querySelector('video'),'KREA still-image previews preserved');
          dialog.close();await new Promise(resolve=>setTimeout(resolve,0));
          window.PanelForgeKrea2ResourceUi.openResourceInfo({...resource,preview_urls:['javascript:alert(1)']});
          check(!document.querySelector('dialog img,dialog video'),'invalid preview scheme ignored');
          document.querySelector('#result').textContent='PASS';
        }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = '<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; img-src \'none\'; media-src \'none\'"><pre id="result">PENDING</pre>'
        self.run_browser(self.browser(), html + '<script>' + source + '</script><script>' + scenario + '</script>')
