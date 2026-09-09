"""Local UI fixtures only. Prepared for user execution, no Lab/model calls."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class RestagingBrowserTest(unittest.TestCase):
    def test_scene_selection_draft_retry_and_stale_upload(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        dialog = '<dialog id="krea2-assisted-restaging-dialog"' + index.split('<dialog id="krea2-assisted-restaging-dialog"', 1)[1].split("</dialog>", 1)[0] + "</dialog>"
        script = r"""
        (async () => { try {
          const check=(value,message)=>{if(!value)throw new Error(message);};
          const pause=()=>new Promise(resolve=>setTimeout(resolve,30));
          const until=async fn=>{for(let i=0;i<100;i++){if(fn())return;await pause();}throw new Error('timeout');};
          const dialog=document.getElementById('krea2-assisted-restaging-dialog');
          const el=name=>dialog.querySelector(`[data-restage="${name}"]`);
          const subject={attempt_id:'subject',index:2,output_asset_id:'subject-image',output_url:'subject.png',status:'succeeded'};
          const base={attempt_id:'scene',index:1,output_asset_id:'scene-image',status:'succeeded'};
          let project={project_id:'p',attempts:[base,subject]}, fail=true, prepared=null, releaseUpload=null;
          const calls=[];
          window.fetch=()=>{throw new Error('unexpected network call');};
          const controller=window.PanelForgeAssistedRestaging.create({
            getProject:()=>project, getInstruction:()=> 'Place subject 2 into scene 1.',
            request:async (url,options)=>{
              if(url.endsWith('/scene-images')) return new Promise(resolve=>{releaseUpload=resolve;});
              check(url.endsWith('/subject/restage'), 'only prepare a restaging workshop');
              const body=JSON.parse(options.body);calls.push(body);
              if(fail)throw new Error('simulated failure');
              return {source:{source_id:'edit-workshop',source_asset_id:body.scene_asset_id,attempts:[]}};
            },
            onPrepared:async source=>{prepared=source;},
          });
          controller.open(project,subject);
          check(dialog.open && el('start').disabled,'opening does not generate and needs a scene');
          check(calls.length===0 && el('subject-preview').src.endsWith('subject.png'),'exact Assisted image preview');
          check(el('scene').options.length===2,'only other successful images offered as scene');
          el('scene').value='scene-image';el('scene').dispatchEvent(new Event('change'));
          el('instruction').value='Preserve the room and bring her diamonds.';el('instruction').dispatchEvent(new Event('input'));
          controller.close();controller.open(project,subject);
          check(el('scene').value==='scene-image' && el('instruction').value.includes('diamonds'),'draft survives close');
          el('start').click();await until(()=>calls.length===1&&!controller.saving);
          check(dialog.open && el('note').textContent==='simulated failure','failure retains inputs');
          el('start').click();await until(()=>calls.length===2&&!controller.saving);
          check(calls[0].request_id===calls[1].request_id,'retry preserves request identity');
          el('instruction').value+=' Adapt shadows.';el('instruction').dispatchEvent(new Event('input'));
          fail=false;el('start').click();await until(()=>prepared&&!controller.saving);
          check(calls[2].request_id!==calls[1].request_id,'changed instruction gets a new request identity');
          check(prepared.source_asset_id==='scene-image'&&prepared.attempts.length===0&&!dialog.open,'opens prepared Edit source without starting a render');
          controller.open(project,subject);
          const transfer=new DataTransfer();transfer.items.add(new File(['fixture'],'new-scene.png',{type:'image/png'}));
          el('file').files=transfer.files;el('file').dispatchEvent(new Event('change'));await until(()=>releaseUpload);
          controller.close();project={project_id:'other',attempts:[base,subject]};controller.open(project,subject);
          releaseUpload({image:{asset_id:'stale-scene',filename:'old upload'}});await pause();
          check(![...el('scene').options].some(o=>o.value==='stale-scene'),'stale import cannot leak to another project');
          document.getElementById('result').textContent='PASS';
        } catch(error) {document.getElementById('result').textContent='FAIL: '+error.stack;} })();
        """
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>' + dialog
        html += "<style>" + (STATIC / "lab.css").read_text(encoding="utf-8") + "</style>"
        html += "<script>" + (STATIC / "krea2-assisted-restaging.js").read_text(encoding="utf-8") + "</script><script>" + script + "</script>"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            page = directory / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--window-size=1500,1200", "--virtual-time-budget=10000",
                f"--user-data-dir={directory / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
            self.assertEqual(result.returncode,0,result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>',result.stdout)
