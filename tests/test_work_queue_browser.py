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
          local_cooldown_temperature_c:80,local_cooldown_seconds:80,
          remote_video_cooldown_seconds:30,pause_after_failure:false,history_limit:30};
        const status={settings,recent:[{resource:'local_gpu',operation:'Ancien prompt',status:'failed',
          error_type:'RuntimeError',error:'Serveur LLM indisponible'}],
          temperature_history:{window_seconds:3600,bucket_seconds:15,series:{
            local_gpu:[{age_seconds:15,max_temperature_c:78},{age_seconds:0,max_temperature_c:81}],
            remote_gpu:[{age_seconds:15,max_temperature_c:64},{age_seconds:0,max_temperature_c:66}]}},
          machines:{
          local_gpu:{state:'busy',temperature_c:81,paused:false,active:{operation:'ScÃ©nario long',workload:'llm',
            stage:'GÃ©nÃ©ration en cours',progress:.5,llm_metrics:{tokens_per_second:42.7,thinking_tokens:22000,writing_tokens:100,estimated:true}},
            queue_count:1,queue:[{position:1,operation:'Prompt scÃ¨ne 2',workload:'llm'}]},
          remote_gpu:{state:'paused',temperature_c:66,paused:true,active:null,queue_count:1,
            queue:[{position:1,operation:'KREA2 Â· LÃ©a',workload:'image_render'}]},
        }};
        const thermal24={window_seconds:86400,bucket_seconds:15,
          from:'2026-09-24T12:00:00Z',to:'2026-09-25T12:00:00Z',persistent:true,error:null,
          series:{
            local_gpu:[{timestamp:'2026-09-25T10:00:00Z',max_temperature_c:76},{timestamp:'2026-09-25T10:00:15Z',max_temperature_c:82}],
            remote_gpu:[{timestamp:'2026-09-25T09:00:00Z',max_temperature_c:68},{timestamp:'2026-09-25T09:00:15Z',max_temperature_c:73}]},
          events:{
            local_gpu:[{id:'p1',marker:'P',workload:'llm',operation:'Synopsis',started_at:'2026-09-25T10:00:00Z',finished_at:'2026-09-25T10:02:00Z',status:'completed',peak_temperature_c:82}],
            remote_gpu:[{id:'v1',marker:'V',workload:'video_render',operation:'H3 scene 1',started_at:'2026-09-25T09:00:00Z',finished_at:'2026-09-25T09:12:00Z',status:'completed',peak_temperature_c:73}]}};
        window.fetch=async(url,options={})=>{
          calls.push({url,method:options.method||'GET',body:options.body?JSON.parse(options.body):null});
          const value=url==='/api/work-scheduler/thermal-history'?thermal24:url.endsWith('/pause')?{...status,machines:{...status.machines,
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
          check(!floating.hidden&&floating.textContent.includes('ScÃ©nario long'),'active local work is visible');
          check(floating.textContent.includes('Working')&&floating.textContent.includes('50 %'),'working state and progress are visible');
          check(floating.textContent.includes('42,7 tok/s')&&floating.textContent.includes('Th : 22,0k')&&floating.textContent.includes('Wr : 0,1k'),'live LLM metrics are visible');
          check(floating.querySelectorAll('.work-queue-temperature-chart').length===2&&floating.textContent.includes('pic 81 °C'),'both one-hour temperature charts are visible');
          check(floating.textContent.includes('1 en attente')&&floating.querySelectorAll('[data-compact] progress').length===2,'both queue meters are visible');
          floating.querySelector('[data-minimize]').click();
          check(floating.classList.contains('minimized'),'monitor can be minimized');
          check(floating.querySelectorAll('.work-queue-minimized-lane svg').length===2,'minimized monitor shows local computer and server cloud icons');
          check(floating.querySelectorAll('.work-queue-minimized-dot').length===2&&floating.querySelector('[data-restore]').textContent.includes('50 %'),'minimized monitor keeps state dots and progress');
          check(floating.querySelector('[data-restore]').textContent.includes('+1'),'minimized monitor keeps the waiting count');
          floating.querySelector('[data-restore]').click();
          check(!floating.classList.contains('minimized'),'clicking the minimized monitor restores it');
          await window.PanelForgeWorkQueue.open();
          const dialog=document.querySelector('.work-queue-dialog');
          check(dialog.open&&dialog.querySelectorAll('.work-queue-lane').length===2,'both lanes open');
          check(dialog.querySelectorAll('.work-queue-long-temperature-chart').length===2,'two separate 24 hour charts are visible');
          check(dialog.querySelectorAll('.work-queue-event-markers button').length===2,'local and remote event markers are visible');
          check(dialog.textContent.includes('P = Prompt/LLM')&&dialog.textContent.includes('I = Image'),'event legends are visible');
          check(calls.some(call=>call.url==='/api/work-scheduler/thermal-history'),'24 hour history uses its dedicated request');
          check(dialog.textContent.includes('Prompt scÃ¨ne 2')&&dialog.textContent.includes('KREA2 Â· LÃ©a'),'upcoming jobs are described');
          check(dialog.textContent.includes('Serveur LLM indisponible'),'real failure detail is visible');
          dialog.querySelector('[data-resource=local_gpu]').click();
          await until(()=>calls.some(call=>call.url==='/api/work-scheduler/local_gpu/pause'));
          const form=dialog.querySelector('[data-settings-form]');
          form.elements.namedItem('remote_video_cooldown_seconds').value='45';
          form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
          await until(()=>calls.some(call=>call.url==='/api/work-scheduler/settings'&&call.method==='PUT'));
          const saved=calls.find(call=>call.url==='/api/work-scheduler/settings'&&call.method==='PUT').body;
          check(saved.remote_video_cooldown_seconds===45&&saved.thermal.stop_temperature_c===85&&
            saved.local_cooldown_temperature_c===80&&saved.local_cooldown_seconds===80,'global settings are posted');
          window.PanelForgeWorkQueue.notice('Admission DLSS interrompue',{id:'dlss:test'});
          check(floating.textContent.includes('Admission DLSS interrompue'),'client-side admission errors use the global monitor');
          window.dispatchEvent(new CustomEvent('panelforge:work-scheduler-status',{detail:{...status,machines:{
            local_gpu:{state:'idle',paused:false,active:null,queue_count:0,queue:[]},
            remote_gpu:{state:'unavailable',paused:false,active:null,queue_count:0,queue:[]},
          }}}));
          check(floating.textContent.includes('Ready')&&floating.textContent.includes('Unavailable'),'idle and unavailable lanes stay visible');
          check((floating.textContent.match(/0 en attente/g)||[]).length===2,'zero queue counts stay visible');
          window.dispatchEvent(new CustomEvent('panelforge:work-scheduler-status',{detail:{...status,machines:{
            ...status.machines,
            remote_gpu:{state:'busy',paused:false,queue_count:0,queue:[],active:{
              operation:'H3 scene 1',workload:'video_render',stage:'Envoi a ComfyUI',progress:.08,execution_id:'render-1'}},
          }}}));
          window.dispatchEvent(new CustomEvent('panelforge:render-progress',{detail:{
            prompt_id:'render-1',phase_label:'Premiere passe',percent:23.5,current_step:2,total_steps:4,
          }}));
          check(floating.textContent.includes('24 %')&&floating.textContent.includes('\u00e9tape 2/4'),'live H3 steps update the global meter');
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
