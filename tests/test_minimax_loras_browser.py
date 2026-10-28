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
          let changes=0, fail=false, count=0;
          const root=document.getElementById('loras');
          const widget=PanelForgeMinimaxLoras.mount(root,{api:'/fake',onChange:()=>changes++,
            request:async()=>{count++;if(fail)throw new Error('offline');return {models:[name],supported:true};}});
          const entries=[{name,strength:.375,enabled:true},{name:missing,strength:.85,enabled:false}];
          widget.setValue(entries);await widget.refresh();
          check(JSON.stringify(widget.getValue())===JSON.stringify(entries),'refresh preserves exact saved values and missing files');
          check(root.querySelectorAll('select').length===4,'four slots available');
          check(root.querySelectorAll('select')[1].selectedOptions[0].textContent.includes('indisponible'),'missing selection is visible');
          check(changes===0,'restore and refresh never mark the draft dirty');
          fail=true;await widget.refresh(true);
          check(root.textContent.includes('offline'),'catalogue error is visible');
          check(JSON.stringify(widget.getValue())===JSON.stringify(entries),'offline refresh never drops selections');
          const slider=root.querySelector('input[type=range]');slider.value='.625';slider.dispatchEvent(new Event('input'));
          check(widget.getValue()[0].strength===.625&&changes===1,'slider updates selected strength');
          widget.setDisabled(true);
          check([...root.querySelectorAll('input,select,button')].every(el=>el.disabled),'locked stage disables controls');
          widget.setDisabled(false);
          check(!root.querySelector('select').disabled&&!slider.disabled,'editable stage restores controls');
          check(root.querySelectorAll('input[type=range]')[1].disabled,'disabled adapter retains its inactive slider');
          check(count===2,'project polling does not query catalogue');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browsers[-1], '<meta charset="utf-8"><pre id="result">PENDING</pre><div id="loras"></div>'
                         + '<script>' + source + scenario + '</script>')
