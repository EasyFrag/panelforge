"""User-run local DOM fixture for the independent Sensual controls."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class SensualControlsBrowserTest(unittest.TestCase):
    def test_selection_auto_reopen_and_cross_family_isolation(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        html = """<meta charset="utf-8"><pre id="result">PENDING</pre>
        <div id="test-sensual-controls" hidden><select id="test-sensual-shots"><option value="auto">Auto</option>
          <option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select>
          <small id="test-sensual-summary"></small></div>
        <label><select id="sequence"></select></label><select id="recipe"></select>
        """
        script = """
        try {
          const check=(value,message)=>{if(!value)throw new Error(message);};
          const classic={id:'minimax.h3.fl2va.direct.planned',version:'1.2.0',preparation_steps:2,preparation:{family:'classic',version:null}};
          const combat={id:'minimax.h3.fl2va.combat.planned',version:'1.3.0',preparation_steps:2,preparation:{family:'combat',version:'1.3.0'}};
          const sensual={id:'minimax.h3.fl2va.sensual.planned',version:'1.0.0',preparation_steps:2,preparation:{family:'sensual',version:'1.0.0'}};
          const recipes=[classic,combat,sensual], state={cookbook:classic,session:null,composition:null,forkSource:null};
          const elements={cookbook:document.querySelector('#recipe'),sequenceKind:document.querySelector('#sequence'),creativeDirection:{checked:true}};
          let controller,locked=false;
          const render=()=>controller.draw(state.cookbook);
          controller=window.PanelForgeSensualControls.create({prefix:'test',state,elements,recipes:()=>recipes,render,busy:()=>locked});
          controller.choose();
          check(state.cookbook===sensual && !elements.creativeDirection.checked,'selects the exact two-step family');
          check(controller.payload().explicitness==='explicit_maximal' && controller.payload().shot_count===null,'fixed maximal Auto payload');
          check(elements.sequenceKind.closest('label').hidden,'sequence selector hidden');
          const shots=document.querySelector('#test-sensual-shots'); shots.value='4'; shots.dispatchEvent(new Event('change'));
          check(controller.payload().shot_count===4,'manual count payload');
          state.session={id:'saved',preparation:sensual.preparation,sensual_settings:{explicitness:'explicit_maximal',shot_count:null}};
          state.composition={sensual_sequence:{shot_count:3}}; render();
          check(shots.value==='auto' && shots.disabled,'saved settings restored and locked');
          check(document.querySelector('#test-sensual-summary').textContent.includes('3 plan(s) retenu(s)'),'resolved count displayed');
          state.session=null; state.composition=null; state.forkSource={id:'fork',sensual_settings:{explicitness:'explicit_maximal',shot_count:5}}; render();
          check(shots.value==='5' && !shots.disabled,'fork settings editable');
          state.cookbook=combat; state.forkSource=null; render();
          check(controller.payload()===null && document.querySelector('#test-sensual-controls').hidden,'Combat receives no Sensual settings');
          state.cookbook=classic; render(); check(controller.payload()===null,'Classic receives no Sensual settings');
          state.cookbook=sensual; locked=true; controller.choose(); check(state.cookbook===sensual,'busy transition blocked');
          document.querySelector('#result').textContent='PASS';
        } catch(error) { document.querySelector('#result').textContent='FAIL: '+error.stack; }
        """
        html += "<script>" + (STATIC / "sensual-controls.js").read_text(encoding="utf-8") + "</script>"
        html += "<script>" + script + "</script>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [str(browsers[-1]), "--headless", "--disable-gpu", "--no-first-run",
                 f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)


if __name__ == "__main__":
    unittest.main()
