"""User-run browser fixture for independent Combat controls. No server or generation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class CombatControlsBrowserTest(unittest.TestCase):
    def test_version_selection_settings_reopen_and_payload(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        html = """<meta charset="utf-8"><pre id="result">PENDING</pre>
        <label><select id="test-combat-version"><option>1.3.0</option><option>1.2.0</option><option>1.1.1</option><option>1.1.0</option><option>1.0.0</option></select></label>
        <div id="test-combat-controls"><input id="test-combat-action" type="range" min="0" max="3" value="1">
        <label><select id="test-combat-orientation"><option value="mixed">Mixed</option><option value="hand_to_hand">Close</option><option value="weapons">Weapons</option><option value="magic">Magic</option></select><small id="test-combat-orientation-hint"></small></label>
        <output id="test-combat-action-value"></output><select id="test-combat-shots">
        <option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option><option>auto</option>
        </select><p id="test-combat-summary"></p></div>
        <label><select id="recipe"></select></label><label><select id="sequence"></select></label>
        <label><input id="motion"></label><div id="audacity"><small></small></div>
        """
        script = """
        try {
          const check = (value, message) => { if (!value) throw new Error(message); };
          const recipes = ['1.0.0', '1.1.0', '1.1.1', '1.2.0'].flatMap(version => [1,2,3].map(preparation_steps => ({
            id:'combat.'+preparation_steps, version, preparation_steps, preparation:{family:'combat',version}, profile:{id:'combat'}
          })));
          recipes.push({id:"combat.2",version:"1.3.0",preparation_steps:2,preparation:{family:"combat",version:"1.3.0"},profile:{id:"combat"}});
          const state = {cookbook:recipes[1], session:null};
          const elements = {cookbook:document.querySelector('#recipe'),sequenceKind:document.querySelector('#sequence'),
            creativeExtraMotion:document.querySelector('#motion'), creativeDirection:{checked:false}, creativeAudacityControl:document.querySelector('#audacity')};
          let locked=false, controller;
          const render = () => controller.draw(state.cookbook);
          controller = window.PanelForgeCombatControls.create({prefix:'test',state,elements,recipes:()=>recipes,render,busy:()=>locked,steps:()=>state.cookbook.preparation_steps});
          render(); check(controller.payload()===null,'legacy has no new controls');
          controller.choose('combat','1.1.0');
          check(state.cookbook===recipes[4],'version change retains two calls');
          check(elements.sequenceKind.closest('label').hidden,'no duplicate mono/multi control');
          const action=document.querySelector('#test-combat-action'), shots=document.querySelector('#test-combat-shots');
          action.value='3'; action.dispatchEvent(new Event('input'));
          check(controller.payload().shot_count===1,'action does not create cuts');
          shots.value='6'; shots.dispatchEvent(new Event('change'));
          check(controller.payload().action_level===3,'cuts do not change action');
          shots.value='auto'; check(controller.payload().shot_count===null,'Auto persisted explicitly');
          state.session={id:'saved',preparation:{family:'combat',version:'1.1.0'},combat_settings:{action_level:0,shot_count:5}};
          state.composition={combat_sequence:{shot_count:5}};
          render(); check(action.value==='0' && shots.value==='5','reopening restores both settings');
          check(action.disabled && shots.disabled && document.querySelector('#test-combat-version').disabled,'saved workshop locked');
          controller.choose('combat','1.0.0'); check(state.cookbook===recipes[4],'cannot change saved version');
          check(document.querySelector('#test-combat-summary').textContent.includes('5 plan(s) retenu(s)'), 'actual count visible');
          state.session=null; state.composition=null; controller.restore(null); render();
          check(action.value==='1' && shots.value==='1','new workshop defaults');
          state.forkSource={id:'forked',combat_settings:{action_level:2,shot_count:null}}; render();
          check(action.value==='2' && shots.value==='auto' && !action.disabled,'fork inherits editable values');
          controller.choose('combat','1.1.1');
          check(state.cookbook===recipes[7] && controller.payload().action_level===2 && controller.payload().shot_count===null,'1.1.1 keeps route and independent controls');
          state.session={id:'patched',preparation:{family:'combat',version:'1.1.1'},combat_settings:{action_level:3,shot_count:4}};
          render(); check(controller.payload().shot_count===4 && action.disabled,'1.1.1 reopens its saved settings');
          controller.choose('combat','1.1.0'); check(state.cookbook===recipes[7],'saved 1.1.1 is not downgraded');
          state.session=null; render();
          const orientation=document.querySelector('#test-combat-orientation');
          check(orientation.closest('label').hidden && !('orientation' in controller.payload()),'old versions keep their original contract');
          controller.choose('combat','1.2.0');
          check(state.cookbook===recipes[10] && controller.payload().orientation==='mixed','new orientation defaults to mixed and retains two calls');
          orientation.value='weapons'; orientation.dispatchEvent(new Event('change'));
          check(controller.payload().orientation==='weapons' && controller.payload().action_level===2 && controller.payload().shot_count===null,'orientation does not alter action or cuts');
          check(document.querySelector('#test-combat-orientation-hint').textContent.includes('Weapon Combat'),'LoRA advice visible');
          state.session={id:'specialized',preparation:{family:'combat',version:'1.2.0'},combat_settings:{action_level:3,shot_count:4,orientation:'hand_to_hand'}};
          render(); check(orientation.value==='hand_to_hand' && orientation.disabled,'saved orientation restored and locked');
          controller.choose('combat','1.1.1'); check(state.cookbook===recipes[10],'cannot change saved orientation version');
          state.session=null; state.forkSource={id:'specialized-fork',combat_settings:{action_level:1,shot_count:2,orientation:'weapons'}};
          render(); check(orientation.value==='weapons' && !orientation.disabled,'fork restores editable orientation');
          controller.choose('combat','1.0.0');
          check(controller.payload()===null && !elements.sequenceKind.closest('label').hidden,'legacy mode retains original controls');
          controller.choose('combat','1.3.0');
          check(state.cookbook.preparation_steps===2 && state.cookbook.version==='1.3.0','1.3 offers only two calls');
          orientation.value='magic'; orientation.dispatchEvent(new Event('change'));
          check(controller.payload().orientation==='magic','magic saved for new version');
          check(!orientation.querySelector('option[value="magic"]').disabled,'magic enabled on 1.3');
          state.session={id:'cinematic',preparation:{family:'combat',version:'1.3.0'},combat_settings:{action_level:3,shot_count:6,orientation:'magic'}};
          render(); check(orientation.disabled && controller.payload().shot_count===6,'1.3 restores and locks its settings');
          state.session=null; state.forkSource=null; controller.choose('combat','1.2.0');
          check(controller.payload().orientation==='mixed' && orientation.querySelector('option[value="magic"]').disabled,'1.2 cannot receive magic');
          controller.choose('combat','1.0.0');
          locked=true; controller.choose('combat','1.1.0'); check(state.cookbook.version==='1.0.0','busy cannot switch');
          document.querySelector('#result').textContent='PASS';
        } catch(error) { document.querySelector('#result').textContent='FAIL: '+error.stack; }
        """
        html += '<script>' + (STATIC / 'combat-controls.js').read_text(encoding='utf-8') + '</script><script>' + script + '</script>'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); page = root / 'test.html'; page.write_text(html, encoding='utf-8')
            result = subprocess.run([str(browsers[-1]), '--headless', '--disable-gpu', '--no-first-run',
                f'--user-data-dir={root / "profile"}', '--dump-dom', page.as_uri()], capture_output=True,
                text=True, encoding='utf-8', errors='replace', timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
