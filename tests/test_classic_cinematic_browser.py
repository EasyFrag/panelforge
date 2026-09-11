"""User-run local DOM fixture; no app server, LLM or video generation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class ClassicCinematicBrowserTest(unittest.TestCase):
    def test_opt_in_auto_reopen_and_isolation_from_old_recipes(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        html = """<meta charset="utf-8"><pre id="result">PENDING</pre>
        <label><select id="test-classic-version"><option value="legacy">Current</option><option value="1.0.0">Experimental</option></select></label>
        <div id="test-cinematic-controls"><select id="test-cinematic-shots"><option value="auto">Auto</option>
          <option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select>
          <small id="test-cinematic-summary"></small></div>
        <label><select id="recipe"></select></label><label><select id="sequence"></select></label>
        """
        script = """
        try {
          const check = (value,message) => { if (!value) throw new Error(message); };
          const core = window.PanelForgeLabCore;
          const legacy = [1,2,3].map((preparation_steps,i) => ({id:'minimax.h3.fl2va.direct.'+['prompt','planned','guided'][i],
            version:'1.2.0',preparation_steps,preparation:{family:'classic',version:null}}));
          const experimental = {id:'minimax.h3.fl2va.classic.cinematic.planned',version:'1.0.0',preparation_steps:2,
            preparation:{family:'classic',version:'1.0.0'}};
          const combat = {id:'minimax.h3.fl2va.combat.planned',version:'1.3.0',preparation_steps:2,
            preparation:{family:'combat',version:'1.3.0'}};
          const recipes = [...legacy,experimental,combat];
          const state = {cookbook:legacy[2],session:null};
          const elements = {cookbook:document.querySelector('#recipe'),sequenceKind:document.querySelector('#sequence'),creativeDirection:{checked:false}};
          const key = item => item.id+'@'+item.version;
          recipes.forEach(item => {
            const option = new Option(key(item),key(item));
            option.dataset.preparationFamily=item.preparation.family;
            option.dataset.classicVersion=item.preparation.family==='classic' ? item.preparation.version || 'legacy' : '';
            elements.cookbook.add(option);
          });
          let controller, locked=false;
          const render = () => {
            elements.cookbook.value=key(state.cookbook);
            elements.cookbook.dataset.preparationFamily=(state.session || state.cookbook).preparation.family;
            controller.draw(state.cookbook); core.refreshRecipeVisibility(elements.cookbook);
          };
          controller=window.PanelForgeClassicCinematicControls.create({prefix:'test',state,elements,recipes:()=>recipes,render,busy:()=>locked,steps:()=>state.cookbook.preparation_steps});
          render();
          check(!controller.current() && controller.payload()===null,'legacy default retained');
          check([...elements.cookbook.options].filter(o=>!o.hidden).length===3,'old three routes visible');
          const version=document.querySelector('#test-classic-version'), shots=document.querySelector('#test-cinematic-shots');
          version.value='1.0.0'; version.dispatchEvent(new Event('change'));
          check(state.cookbook===experimental && state.cookbook.preparation_steps===2,'explicit opt-in selects two calls');
          check(controller.payload().shot_count===null,'Auto default');
          check(elements.sequenceKind.closest('label').hidden,'no duplicate mono/multi choice');
          check([...elements.cookbook.options].filter(o=>!o.hidden).length===1,'only pinned experimental recipe visible');
          shots.value='4'; shots.dispatchEvent(new Event('change'));
          check(controller.payload().shot_count===4 && document.querySelector('#test-cinematic-summary').textContent.includes('même si'),'explicit count priority is visible');
          state.session={id:'saved',preparation:experimental.preparation,cinematic_settings:{shot_count:null}};
          state.composition={cinematic_sequence:{shot_count:3}}; render();
          check(shots.value==='auto' && shots.disabled && version.disabled,'reopen preserves Auto and locks settings');
          check(document.querySelector('#test-cinematic-summary').textContent.includes('3 plan(s) retenu(s)'), 'resolved plan count displayed');
          version.value='legacy'; controller.choose(); check(state.cookbook===experimental,'saved workshop version cannot change');
          state.session=null; state.composition=null; state.forkSource={id:'fork',cinematic_settings:{shot_count:5}}; render();
          check(shots.value==='5' && !shots.disabled,'fork restores editable count');
          version.value='legacy'; controller.choose(); check(state.cookbook===legacy[1] && controller.payload()===null,'return to current two-step route');
          state.cookbook=combat; render();
          check(version.closest('label').hidden && controller.payload()===null,'Combat never gets Classic settings');
          state.cookbook=experimental; state.forkSource=null; controller.restore(null); render();
          check(controller.payload().shot_count===null,'new workshop resets to Auto');
          locked=true; version.value='legacy'; controller.choose(); check(state.cookbook===experimental,'busy transition blocked');
          document.querySelector('#result').textContent='PASS';
        } catch(error) { document.querySelector('#result').textContent='FAIL: '+error.stack; }
        """
        for name in ("lab-core.js", "classic-cinematic-controls.js"):
            html += "<script>" + (STATIC / name).read_text(encoding="utf-8") + "</script>"
        html += "<script>" + script + "</script>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--no-first-run",
                f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
