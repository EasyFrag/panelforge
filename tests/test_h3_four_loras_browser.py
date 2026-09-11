"""User-run DOM checks, no application server or model invocation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class FourLoraBrowserTest(unittest.TestCase):
    def test_capacity_order_strengths_polling_and_old_stack_restoration(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static/h3-loras.js").read_text(encoding="utf-8")
        scenario = """
        try {
          const check = (ok, message) => { if (!ok) throw new Error(message); };
          const names = ['combat', 'motion', 'third', 'fourth', 'fifth'].map(n => 'minmax_nsfw/'+n+'.safetensors');
          const root = document.querySelector('#test-lora-stack');
          let changes = 0;
          const infos=[];
          window.PanelForgeH3LoraInfo={open:name=>{infos.push(name);return Promise.resolve();}};
          const editor = window.PanelForgeH3Loras.mount('test', {
            request: () => { throw new Error('No network during editing'); }, onChange: () => changes++
          });
          const spec = {supported:true, maximum:4, mode:'per_pass', defaults:{version:'0.2.0', enabled:true,
            clip_last_layer:null, entries:names.slice(0,2).map(name => ({name,strength:.6,second_strength:.2,enabled:true}))}};
          const find = selector => root.querySelector(selector);
          const rows = () => root.querySelectorAll('[data-lora-row]');
          editor.configure(spec, {models:names});
          check(rows().length===2 && !editor.error, 'two default slots only');
          find('[data-lora-add]').click(); find('[data-lora-add]').click();
          check(rows().length===4 && editor.value.entries.length===4, 'add up to four');
          check(find('[data-lora-add]').hidden && find('[data-lora-add]').disabled, 'fifth slot unavailable');
          find('[data-lora-add]').click(); check(rows().length===4, 'fifth click cannot add');
          check(find('[data-lora-note]').textContent.includes('4/4'), 'capacity visible');
          const beforeInfo=JSON.stringify(editor.value), beforeChanges=changes;
          editor.setDisabled(true);
          rows()[2].querySelector('[data-lora-info]').click();
          check(infos.join(',')===names[2], 'info opens exact selected LoRA even during rendering');
          check(JSON.stringify(editor.value)===beforeInfo && changes===beforeChanges, 'info never changes strengths, order or render draft');
          editor.setDisabled(false);
          const field = rows()[3].querySelector('[data-lora-force="second_strength"]');
          field.value='.35'; field.dispatchEvent(new Event('input'));
          rows()[3].querySelector('[data-lora-up]').click();
          check(editor.value.entries[2].name===names[3] && editor.value.entries[2].second_strength===.35, 'up moves file with both strengths');
          rows()[2].querySelector('[data-lora-down]').click();
          check(editor.value.entries[3].name===names[3] && editor.value.entries[3].second_strength===.35, 'down preserves strength');
          check(rows()[0].querySelector('[data-lora-up]').disabled && rows()[3].querySelector('[data-lora-down]').disabled, 'order boundaries');
          const toggle = rows()[2].querySelector('[data-lora-enabled]');
          toggle.checked=false; toggle.dispatchEvent(new Event('change'));
          check(!editor.value.entries[2].enabled && rows()[2].querySelector('[data-lora-model]').disabled, 'inactive slot retained');
          const saved = editor.value, rowBefore = rows()[0];
          editor.setDisabled(true); check(find('[data-lora-up]').disabled, 'busy state');
          editor.setDisabled(false); check(rows()[0]===rowBefore, 'polling does not rebuild rows');
          editor.configure(spec, {models:names}); editor.restoreAttempt({video_loras:saved});
          check(JSON.stringify(editor.value)===JSON.stringify(saved), 'all four restore exactly');
          const old = {...saved, version:'0.1.0', entries:saved.entries.slice(0,2)};
          editor.restoreAttempt({video_loras:old});
          check(editor.value.version==='0.2.0', 'old attempt upgraded only in current editor draft');
          find('[data-lora-add]').click(); find('[data-lora-add]').click();
          check(editor.value.entries.length===4 && old.entries.length===2 && old.version==='0.1.0', 'old snapshot unchanged');
          editor.configure({...spec, maximum:2, defaults:old}, {models:names});
          check(find('[data-lora-add]').hidden, 'historical recipe remains limited to two');
          editor.restore(saved);
          check(editor.error && editor.value.entries.length===4, 'over-capacity restoration is explicit, never truncated');
          rows()[3].querySelector('[data-lora-remove]').click(); rows()[2].querySelector('[data-lora-remove]').click();
          check(!editor.error && editor.value.entries.length===2, 'can resolve capacity error');
          editor.configure({...spec, mode:'shared', defaults:{version:'0.2.0',enabled:false,clip_last_layer:-2,entries:[]}}, {models:names});
          check(root.hidden, 'basic Standard default');
          editor.setEnabled(true);
          for(let i=0;i<3;i++) find('[data-lora-add]').click();
          check(editor.value.entries.length===4 && editor.value.entries.every(e=>e.second_strength===null), 'basic single force per file');
          check(!find('[data-lora-force="second_strength"]') && changes>0, 'basic UI has no second pass controls');
          document.querySelector('#result').textContent='PASS';
        } catch (error) { document.querySelector('#result').textContent='FAIL: '+error.stack; }
        """
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre><div id="test-lora-stack"></div>'
        html += '<script>' + source + '</script><script>' + scenario + '</script>'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "loras.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking", "--no-first-run",
                f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
