"""User-run shared widget scenario, with no server or render calls."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class MinimaxLorasBrowserTests(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_refresh_missing_files_and_readonly_preserve_selections(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        if not browsers and chrome.is_file():
            browsers = [chrome]
        if not browsers:
            self.skipTest("local Chromium or Chrome not installed")
        source = (STATIC / "minimax-loras.js").read_text(encoding="utf-8")
        scenario = r"""
        (async()=>{try{
          const check=(value,label)=>{if(!value)throw new Error(label);};
          const name='minmax_nsfw/style.safetensors', missing='minmax_nsfw/old.safetensors';
          const extras=['minmax_nsfw/portrait.safetensors','minmax_nsfw/light.safetensors','minmax_nsfw/fabric.safetensors'];
          let changes=0, fail=false, count=0;
          const root=document.getElementById('loras');
          const widget=PanelForgeMinimaxLoras.mount(root,{api:'/fake',onChange:()=>changes++,
            request:async()=>{count++;if(fail)throw new Error('offline');return {models:[name,...extras],supported:true};}});
          const entries=[{name,strength:.375,enabled:true},{name:missing,strength:.85,enabled:false}];
          widget.setValue(entries);await widget.refresh();
          check(JSON.stringify(widget.getValue())===JSON.stringify(entries),'refresh preserves exact saved values and missing files');
          check(root.querySelectorAll('.minimax-lora-row').length===2,'only selected adapters have rows');
          check(root.querySelectorAll('[data-lora-choose]')[1].textContent.includes('indisponible'),'missing selection is visible');
          check(changes===0,'restore and refresh never mark the draft dirty');
          fail=true;await widget.refresh(true);
          check(root.textContent.includes('offline'),'catalogue error is visible');
          check(JSON.stringify(widget.getValue())===JSON.stringify(entries),'offline refresh never drops selections');
          const strength=root.querySelector('input[type=number]');strength.value='.625';strength.dispatchEvent(new Event('input'));
          check(widget.getValue()[0].strength===.625&&changes===1,'precise force updates selected strength');
          strength.value='';strength.dispatchEvent(new Event('input'));strength.dispatchEvent(new Event('change'));
          check(strength.value==='0.625'&&widget.getValue()[0].strength===.625,'invalid input preserves the last valid force');
          widget.setDisabled(true);
          check([...root.querySelectorAll('input,select,button')].every(el=>el.disabled),'locked stage disables controls');
          widget.setDisabled(false);
          check(!root.querySelector('[data-lora-choose]').disabled&&!strength.disabled,'editable stage restores controls');
          check(root.querySelectorAll('input[type=number]')[1].disabled,'disabled adapter retains its inactive force');
          check(count===2,'project polling does not query catalogue');
          root.querySelector('[data-lora-add]').click();
          let dialog=document.querySelector('.minimax-lora-picker');
          check(dialog.open&&dialog.querySelectorAll('[data-lora-select]').length===3,'picker excludes already selected adapters');
          const search=dialog.querySelector('input[type=search]');search.value='PORTRAIT';search.dispatchEvent(new Event('input'));
          check(dialog.querySelectorAll('[data-lora-select]').length===1,'catalogue searches case insensitively');
          dialog.querySelector('[data-lora-select]').click();
          check(widget.getValue()[2].name===extras[0],'picker adds chosen adapter');
          root.querySelectorAll('[data-lora-up]')[2].click();
          check(widget.getValue()[1].name===extras[0]&&widget.getValue()[2].enabled===false,'reordering preserves activation and force');
          root.querySelector('[data-lora-add]').click();
          dialog=[...document.querySelectorAll('.minimax-lora-picker')].find(d=>d.open);
          dialog.querySelector('[data-lora-select]').click();
          check(widget.getValue().length===4&&root.querySelector('[data-lora-add]').disabled,'four adapters maximum');
          root.querySelectorAll('[data-lora-remove]')[1].click();
          check(widget.getValue().length===3&&!root.querySelector('[data-lora-add]').disabled,'removing frees a slot');
          root.querySelector('[data-lora-choose]').click();
          widget.setDisabled(true);
          check(![...document.querySelectorAll('.minimax-lora-picker')].some(d=>d.open),'locking closes an open picker');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browsers[-1], '<meta charset="utf-8"><pre id="result">PENDING</pre><div id="loras"></div>'
                         + '<script>' + source + scenario + '</script>')
