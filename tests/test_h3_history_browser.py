"""User-run history regression, real list renderer with an offline transport."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class H3HistoryBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_cinematic_classic_history_keeps_both_workshops_and_old_profiles(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        bodies = []
        for filename, scope in (("i2v-direct.js", "h3"), ("ref2v-direct.js", "ref")):
            source = (STATIC / filename).read_text(encoding="utf-8")
            start = source.index("  async function loadSessions()")
            function = source[start:source.index("  function selectModel(", start)]
            bodies.append("{" + f"const scope='{scope}';" + """
                const monoProfile={id:'minimax.h3.fl2va.direct'}, multishotProfile={id:'minimax.h3.fl2va.direct.multishot'},
                  animalInterviewProfile={id:'minimax.h3.base.animal-interview'}, legacyProfileId='minimax.h3.i2v.direct',
                  profileId='minimax.h3.ref2v.direct',profileVersion='0.4.0',experimentalProfileVersion='0.5.0';
                const make=(id,profile,mode,version='1.0.0')=>({id,profile:{id:profile,version},session_mode:mode,
                  references:[{label:id}],brief_complete:true,preparation:{family:profile.includes('combat')?'combat':'classic',
                  version:profile.includes('cinematic')?'1.0.0':null}});
                let sessions=[
                  make('h3-new','minimax.h3.fl2va.classic.cinematic','h3_base'),
                  make('ref-new','minimax.h3.ref2v.classic.cinematic','direct_multimodal'),
                  make('h3-old',monoProfile.id,'h3_base','0.6.0'),
                  make('ref-old',profileId,'direct_multimodal','0.6.0'),
                  make('h3-combat','minimax.h3.fl2va.combat','h3_base','1.3.0'),
                  make('ref-combat','minimax.h3.ref2v.combat','direct_multimodal','1.3.0'),
                  make('unrelated','other.profile','direct_multimodal'),{id:'unknown',profile:null}];
                const opened=[], requests=[], elements={sessionList:document.createElement('div')};
                const core={request:async url=>{requests.push(url);return {sessions};},decorateSessionLink() {}};
                const preparationFamily=s=>s.preparation?.family,sessionInputModeLabel=s=>s.id;
                window.PanelForgeClassicCinematicControls={isCinematic:s=>s.preparation?.version==='1.0.0'};
                const openSession=s=>opened.push(s.id);
            """ + function + """
                await loadSessions();
                const buttons=[...elements.sessionList.querySelectorAll('button')];
                check(buttons.length===3,'recent cinematic, old and combat workshops are all listed');
                check(buttons[0].textContent.includes('Mise en scène'),'new recipe has a clear label');
                buttons.forEach(b=>b.click());
                check(opened.join(',')===[scope+'-new',scope+'-old',scope+'-combat'].join(','),'click selects the exact saved session in the right workshop');
                check(requests.length===1 && requests[0].endsWith('limit=30'),'same bounded history request, no media-specific scan');
                sessions=[]; await loadSessions();
                check(!elements.sessionList.querySelector('button'),'empty refresh removes stale links');
              }""")
        script = "(async()=>{try{const check=(ok,message)=>{if(!ok)throw new Error(message);};" + "\n".join(bodies)
        script += "document.querySelector('#result').textContent='PASS';}catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();"
        self.run_browser(browsers[-1], '<meta charset="utf-8"><pre id="result">PENDING</pre><script>' + script + '</script>')
