"""Global work-queue UI with fake HTTP only."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src" / "panelforge" / "features" / "lab" / "static"


class WorkQueueBrowserTest(unittest.TestCase):
    def test_monitor_renders_both_lanes_and_saves_global_settings(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob(
            "chromium-*/chrome-win64/chrome.exe"
        ))
        if not browsers:
            self.skipTest("local Chromium not installed")
        script = (STATIC / "work-queue.js").read_text(encoding="utf-8")
        css = (STATIC / "lab.css").read_text(encoding="utf-8")
        scenario = r"""
        const calls=[];
        const settings={thermal:{stop_temperature_c:85,resume_temperature_c:40,cooldown_seconds:120,
          monitor_local:true,monitor_remote:true,pause_when_unavailable:false},
          remote_video_cooldown_seconds:30,pause_after_failure:false,history_limit:30};
        const status={settings,recent:[],machines:{
          local_gpu:{state:'busy',paused:false,active:{operation:'DLSS vidÃ©o',workload:'dlss',stage:'Upscale',progress:.5},
            queue_count:1,queue:[{position:1,operation:'Prompt scÃ¨ne 2',workload:'llm'}]},
          remote_gpu:{state:'paused',paused:true,active:null,queue_count:1,
            queue:[{position:1,operation:'KREA2 Â· LÃ©a',workload:'image_render'}]},
        }};
        window.fetch=async(url,options={})=>{
          calls.push({url,method:options.method||'GET',body:options.body?JSON.parse(options.body):null});
          const value=url.endsWith('/pause')?{...status,machines:{...status.machines,
            local_gpu:{...status.machines.local_gpu,paused:true}}}:url==='/api/work-scheduler/settings'&&options.method==='PUT'
            ? options.body?JSON.parse(options.body):settings:status;
          return {ok:true,json:async()=>value};
        };
        window.dispatchEvent(new CustomEvent('panelforge:work-scheduler-status',{detail:status}));
        (async()=>{try{
          const check=(value,message)=>{if(!value)throw new Error(message);};
          const pause=()=>new Promise(resolve=>setTimeout(resolve,20));
          const until=async fn=>{for(let i=0;i<80&&!fn();i++)await pause();check(fn(),'timed out');};
          const floating=document.querySelector('.work-queue-background');
          check(!floating.hidden&&floating.textContent.includes('DLSS vidÃ©o'),'active local work is visible');
          check(floating.textContent.includes('50 %')&&floating.querySelectorAll('[data-compact] p').length===2,'progress and queue are visible');
          await window.PanelForgeWorkQueue.open();
          const dialog=document.querySelector('.work-queue-dialog');
          check(dialog.open&&dialog.querySelectorAll('.work-queue-lane').length===2,'both lanes open');
          check(dialog.textContent.includes('Prompt scÃ¨ne 2')&&dialog.textContent.includes('KREA2 Â· LÃ©a'),'upcoming jobs are described');
          dialog.querySelector('[data-resource=local_gpu]').click();
          await until(()=>calls.some(call=>call.url==='/api/work-scheduler/local_gpu/pause'));
          const form=dialog.querySelector('[data-settings-form]');
          form.elements.namedItem('remote_video_cooldown_seconds').value='45';
          form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
          await until(()=>calls.some(call=>call.url==='/api/work-scheduler/settings'&&call.method==='PUT'));
          const saved=calls.find(call=>call.url==='/api/work-scheduler/settings'&&call.method==='PUT').body;
          check(saved.remote_video_cooldown_seconds===45&&saved.thermal.stop_temperature_c===85,'global settings are posted');
          window.PanelForgeWorkQueue.notice('Admission DLSS interrompue',{id:'dlss:test'});
          check(floating.textContent.includes('Admission DLSS interrompue'),'client-side admission errors use the global monitor');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        html = '<meta charset="utf-8"><div id="runtime-monitor"></div><pre id="result">PENDING</pre>'
        html += f"<style>{css}</style><script>{script}</script><script>{scenario}</script>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            page = path / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [str(browsers[-1]), "--headless", "--window-size=1400,1000", "--disable-gpu",
                 "--disable-background-networking", "--no-first-run", "--virtual-time-budget=5000",
                 f"--user-data-dir={path / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)


if __name__ == "__main__":
    unittest.main()
