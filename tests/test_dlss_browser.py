"""Shared DLSS panel in an isolated browser with fake HTTP only. Not run by the agent."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class DlssBrowserTest(unittest.TestCase):
    def test_optional_panel_retry_variants_and_stale_preview(self):
        bootstrap = r"""
        const calls=[], outcomes=[]; let failPost=true, delayed=null, delayPreview=false;
        window.PanelForgeLabCore={observeRenderOutcome:(id,state)=>outcomes.push([id,state])};
        window.fetch=async (url,options={})=>{
          const body=options.body?JSON.parse(options.body):null;calls.push({url,body});
          const ok=value=>({ok:true,json:async()=>value});
          if(url==='/api/dlss/jobs'&&!body)return ok({jobs:[]});
          if(url==='/api/dlss/runtime')return ok({state:'ready',owned:false});
          if(url==='/api/dlss/preview'){
            if(delayPreview){delayPreview=false;return new Promise(resolve=>{delayed=()=>resolve(ok({input_metadata:{width:1,height:1},output_dimensions:[9,9]}));});}
            return ok({input_metadata:{width:64,height:96},output_dimensions:body.settings.size==='source'?[64,96]:body.settings.size==='1.5'?[96,144]:[128,192]});
          }
          if(url==='/api/dlss/jobs'&&body){
            if(failPost)return {ok:false,status:503,json:async()=>({detail:'simulated network failure'})};
            return ok({job_id:'dlss-test',status:'queued'});
          }
          throw new Error('Unexpected URL '+url);
        };
        """
        scenario = r"""
        (async()=>{try{
          const check=(v,m)=>{if(!v)throw new Error(m);};
          const pause=()=>new Promise(resolve=>setTimeout(resolve,15));
          const until=async predicate=>{for(let i=0;i<150&&!predicate();i++)await pause();check(predicate(),'timed out');};
          const api=window.PanelForgeDlss,dialog=document.querySelector('.dlss-dialog'),form=dialog.querySelector('form');
          const el=name=>form.elements.namedItem(name),start=dialog.querySelector('[data-start]');
          const source={attempt_id:'original',index:1,status:'succeeded',output_url:'data:image/png;base64,',output_asset_id:'base'};
          api.open({owner:'edit',ownerId:'workshop',attempt:source});
          await until(()=>!start.disabled);
          const initial=()=>el('size').value==='1.5'&&['intensity','tone','structure','detail'].every(name=>Number(el(name).value)===1)&&Number(el('skin').value)===-1&&el('style').value==='Default'&&!el('strict_neural').checked;
          check(initial(),'Edit uses the native image defaults');
          check(!el('size').querySelector('[value=source]').hidden,'source size remains selectable for masked steps');
          form.querySelector('details').open=true;
          const help=dialog.querySelector('[aria-controls=dlss-help-intensity]');
          const submits=()=>calls.filter(c=>c.body&&c.url==='/api/dlss/jobs').length;
          const beforeHelp=submits();help.click();
          check(help.getAttribute('aria-expanded')==='true'&&!dialog.querySelector('#dlss-help-intensity').hidden,'image help opens inline');
          check(initial()&&submits()===beforeHelp,'reading help does not alter or submit settings');
          help.click();check(dialog.querySelector('#dlss-help-intensity').hidden,'help closes');
          el('size').value='source';el('size').dispatchEvent(new Event('input',{bubbles:true}));await until(()=>!start.disabled);
          check(!calls.some(c=>c.body&&c.url==='/api/dlss/jobs'),'opening never queues a treatment');
          check(dialog.querySelector('[data-control=stop]').disabled,'external instance cannot be stopped');
          el('intensity').value='0.5';el('intensity').dispatchEvent(new Event('input',{bubbles:true}));
          await until(()=>!start.disabled);
          start.click();await until(()=>dialog.querySelector('[data-error]').textContent==='simulated network failure'&&!start.disabled);
          start.click();await until(()=>calls.filter(c=>c.body&&c.url==='/api/dlss/jobs').length===2&&!start.disabled);
          const posts=calls.filter(c=>c.body&&c.url==='/api/dlss/jobs');
          check(posts[0].body.request_id===posts[1].body.request_id,'retry uses the same request id');
          check(el('intensity').value==='0.5','failure preserves settings');
          dialog.querySelector('[data-close]').click();
          api.open({owner:'edit',ownerId:'workshop',attempt:source});await until(()=>!start.disabled);
          check(el('intensity').value==='0.5'&&el('size').value==='source','explicit settings survive closing');
          dialog.querySelector('[data-reset-image]').click();await until(()=>!start.disabled);
          check(initial()&&submits()===2,'reset restores image defaults without submitting');
          delayPreview=true;api.open({owner:'assisted',ownerId:'old',attempt:source});await until(()=>delayed);
          api.open({owner:'assisted',ownerId:'new',attempt:source});await until(()=>!start.disabled);delayed();await pause();
          check(dialog.querySelector('[data-dimensions]').textContent.includes('144'),'stale preview cannot replace the current dimensions');
          check(initial(),'Assisted uses the same native defaults as Edit');
          const variant={...source,attempt_id:'enhanced',output_asset_id:'larger',dlss:{root_attempt_id:'original',width:128,height:192}};
          let selected=null;const group=api.groups([source,variant],'assisted:new')[0];
          check(group.variants.length===2&&group.attempt===source,'one card groups original and DLSS');
          const picker=api.picker(group,id=>{selected=id;});picker.value='enhanced';picker.dispatchEvent(new Event('change'));
          check(selected==='enhanced'&&api.groups([source,variant],'assisted:new')[0].attempt.output_asset_id==='larger','actions can target the exact selected variant');
          api.open({owner:'h3',ownerId:'video',attempt:source});await until(()=>!start.disabled);
          check(el('size').value==='1.724'&&el('interpolate').checked&&!el('hdr').checked,'video defaults to 1.724x and 60 FPS in SDR');
          const light=()=>el('style').value==='Natural'&&Number(el('intensity').value)===0.2&&Number(el('tone').value)===0&&Number(el('structure').value)===0.2&&Number(el('skin').value)===0&&Number(el('detail').value)===1;
          check(light(),'advanced video starts with the light profile');
          el('size').value='3';el('interpolate').checked=false;el('codec').value='H.265 (NVIDIA NVENC)';el('hdr').checked=true;
          el('intensity').value='1';el('tone').value='1';el('style').value='Cinematic';el('detail').value='1.4';
          const beforeReset=submits();dialog.querySelector('[data-reset-video]').click();await until(()=>!start.disabled);
          check(light()&&submits()===beforeReset,'video reset restores effects without queueing');
          check(el('size').value==='3'&&!el('interpolate').checked&&el('hdr').checked&&el('codec').value==='H.265 (NVIDIA NVENC)','video reset preserves geometry, cadence and explicit HDR');
          dialog.querySelector('[data-close]').click();api.open({owner:'h3',ownerId:'video',attempt:source});await until(()=>!start.disabled);
          check(light()&&el('size').value==='3','light profile and geometry survive reopening');
          check([...dialog.querySelectorAll('[data-image]')].every(node=>node.hidden),'image help and reset remain hidden for video');
          api.open({owner:'assisted',ownerId:'fresh-image',attempt:source});await until(()=>!start.disabled);
          check(initial()&&dialog.querySelector('[data-reset-video]').hidden,'video effects never become image defaults');
          check(!calls.some(c=>c.body&&c.url.startsWith('/api/dlss/runtime/')),'no lifecycle command runs automatically in the panel');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(bootstrap, scenario)

    def test_video_quick_launch_progress_completion_and_copy_retry_are_nonmodal(self):
        bootstrap = r"""
        const calls=[], events=[], outcomes=[], fakeJobs=[]; let failQuick=true;
        const nativeTimeout=window.setTimeout.bind(window);
        window.setTimeout=(callback,delay,...args)=>nativeTimeout(callback,delay===2500||delay===15000?25:delay,...args);
        window.PanelForgeLabCore={observeRenderOutcome:(id,state)=>outcomes.push([id,state])};
        window.addEventListener('panelforge:dlss-complete',e=>events.push(e.detail));
        window.fetch=async (url,options={})=>{
          const body=options.body?JSON.parse(options.body):null;calls.push({url,body});
          const ok=value=>({ok:true,json:async()=>JSON.parse(JSON.stringify(value))});
          if(url==='/api/dlss/jobs'&&!body)return ok({jobs:fakeJobs});
          if(url==='/api/dlss/runtime')return ok({state:'ready',owned:false});
          if(url==='/api/dlss/preview')return ok({input_metadata:{width:640,height:960},output_dimensions:[1104,1656]});
          if(url==='/api/dlss/jobs'&&body){
            if(failQuick){failQuick=false;return {ok:false,status:503,json:async()=>({detail:'network unavailable'})};}
            const job={job_id:'dlss-'+fakeJobs.length,status:'queued',settings:body.settings,
              snapshot:{owner:body.owner,owner_id:body.owner_id,root_attempt_id:body.attempt_id,media_type:'video/mp4'},
              created_at:new Date().toISOString(),started_at:new Date().toISOString(),warnings:[]};
            fakeJobs.push(job);return ok(job);
          }
          if(url.endsWith('/export')){
            const job=fakeJobs.find(j=>url.includes(j.job_id));job.video_export.status='succeeded';return ok(job);
          }
          throw new Error('Unexpected URL '+url);
        };
        """
        scenario = r"""
        (async()=>{try{
          const check=(v,m)=>{if(!v)throw new Error(m);};
          const pause=()=>new Promise(resolve=>setTimeout(resolve,20));
          const until=async predicate=>{for(let i=0;i<150&&!predicate();i++)await pause();check(predicate(),'timed out');};
          const api=window.PanelForgeDlss, dialog=document.querySelector('.dlss-dialog'), form=dialog.querySelector('form');
          const start=dialog.querySelector('[data-start]');
          const original={attempt_id:'original',index:1,status:'succeeded',output_url:'data:video/mp4,',output_asset_id:'source'};
          const source={owner:'h3',ownerId:'workshop',attempt:original};
          const panel=api.inlineStatus(source),quick=api.button(source),advanced=api.button(source,{advanced:true});
          const prompt=document.createElement('textarea');prompt.value='My next prompt';
          const generate=document.createElement('button');generate.textContent='Generate';let generations=0;generate.onclick=()=>generations++;
          document.body.append(panel,quick,advanced,prompt,generate);
          advanced.click();await until(()=>!start.disabled);
          form.elements.namedItem('size').value='2';form.elements.namedItem('interpolate').checked=false;
          form.dispatchEvent(new Event('input',{bubbles:true}));await until(()=>!start.disabled);
          dialog.querySelector('[data-close]').click();
          const previews=calls.filter(c=>c.url==='/api/dlss/preview').length;
          quick.click();await until(()=>panel.textContent.includes('network unavailable'));
          check(!dialog.open&&!quick.disabled,'quick failure stays inline and can be retried');
          quick.click();await until(()=>fakeJobs.length===1&&quick.disabled);
          check(!dialog.open,'quick launch is nonmodal');
          const posts=calls.filter(c=>c.url==='/api/dlss/jobs'&&c.body);
          check(posts[0].body.request_id===posts[1].body.request_id,'quick retry is idempotent');
          check(posts[1].body.settings.size==='1.724'&&posts[1].body.settings.interpolate&&!posts[1].body.settings.hdr,'quick defaults are independent from advanced settings');
          const effects={intensity:0.2,tone:0,structure:0.2,skin:0,detail:1,style:'Natural'};
          check(Object.entries(effects).every(([key,value])=>posts[1].body.settings[key]===value),'quick uses the light video profile');
          check(calls.filter(c=>c.url==='/api/dlss/preview').length===previews,'quick launch skips the options preview');
          const job=fakeJobs[0];job.status='running';job.progress={stage:'upscale',label:'Upscale',percent:50,updated_at:new Date().toISOString()};
          await until(()=>panel.querySelector('progress')?.value===50);
          job.progress={stage:'interpolation',label:'Fluidification 60 FPS',percent:10,updated_at:new Date().toISOString()};
          await until(()=>panel.querySelector('progress')?.value===10&&panel.textContent.includes('Fluidification'));
          job.progress={stage:'saving',label:'Enregistrement',percent:null,updated_at:new Date().toISOString()};
          await until(()=>!panel.querySelector('progress')&&panel.textContent.includes('Enregistrement'));
          check(!prompt.disabled&&!generate.disabled,'other workshop controls stay available');
          prompt.value='Draft written during upscale';generate.click();check(generations===1,'generation remains usable');
          const other=api.button({owner:'ref2v',ownerId:'other',attempt:original});document.body.append(other);other.click();
          await until(()=>fakeJobs.length===2);check(!dialog.open,'another workshop queues independently');
          job.status='succeeded';job.candidate_id='enhanced';job.output_url='/fake-output.mp4';job.finished_at=new Date().toISOString();
          job.local_output_path='D:\\AI\\PanelForge\\LocalOutput\\dlss\\video.mp4';
          job.video_export={status:'failed',path:'X:\\data\\ComfyUI\\output\\video\\Upscale\\2026-09-09\\video.mp4',error:'share offline'};
          await until(()=>panel.textContent.includes('Voir le résultat'));
          check(panel.textContent.includes(job.local_output_path),'the exact local result path is visible');
          check(events.length===0&&prompt.value==='Draft written during upscale','completion neither selects nor changes a draft');
          const variant={...original,attempt_id:'enhanced',dlss:{root_attempt_id:'original',width:1104,height:1656}};
          check(api.groups([original,variant],'h3:workshop')[0].attempt===original,'original remains selected on completion');
          const count=calls.filter(c=>c.url==='/api/dlss/jobs'&&c.body).length;
          [...panel.querySelectorAll('button')].find(b=>b.textContent==='Réessayer la copie').click();
          await until(()=>panel.textContent.includes('Copiée sur le serveur'));
          check(calls.filter(c=>c.url==='/api/dlss/jobs'&&c.body).length===count,'copy retry does not start another upscale');
          [...panel.querySelectorAll('button')].find(b=>b.textContent==='Voir le résultat').click();
          check(events.length===1&&events[0].select_result&&events[0].candidate_id==='enhanced','result selection is explicit');
          check(api.groups([original,variant],'h3:workshop')[0].attempt===variant,'explicit result targets exact variant');
          const third={owner:'h3',ownerId:'third',attempt:original};
          api.open(third);await until(()=>!start.disabled);start.click();
          await until(()=>fakeJobs.length===3&&!dialog.open);
          check(!document.querySelector('.dlss-background'),'legacy DLSS background is replaced by the global queue monitor');
          check(!calls.some(c=>c.url.startsWith('/api/dlss/runtime/')),'no lifecycle operation is triggered by the browser');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(bootstrap, scenario)

    def run_browser(self, bootstrap, scenario):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        html = '<meta charset="utf-8"><div class="runtime-maintenance"></div><pre id="result">PENDING</pre>'
        html += "<style>" + (STATIC / "lab.css").read_text(encoding="utf-8") + "</style>"
        html += "<script>" + bootstrap + "</script><script>" + (STATIC / "dlss-image-comparison.js").read_text(encoding="utf-8") + "</script>"
        html += "<script>" + (STATIC / "dlss-lab.js").read_text(encoding="utf-8") + "</script><script>" + scenario + "</script>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            page = path / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--window-size=1400,1000", "--disable-gpu", "--disable-background-networking", "--no-first-run",
                "--virtual-time-budget=10000", f"--user-data-dir={path / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)


if __name__ == "__main__":
    unittest.main()
