"""Full Qwen page interactions against a fake in-page API; no live service."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class QwenEditBrowserTest(unittest.TestCase):
    def test_upload_roles_prompt_edit_autosave_and_contained_layout(self):
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        browsers = [*cache.glob("chromium-*/chrome-win/chrome.exe"), *cache.glob("chromium-*/chrome-win64/chrome.exe")]
        if not browsers:
            self.skipTest("Chromium local non installé")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        page = '<main id="qwen-edit-lab-workspace"' + html.split('<main id="qwen-edit-lab-workspace"', 1)[1].split('<main id="krea2-edit-lab-workspace"', 1)[0]
        page = page.replace('class="qwen-workspace" hidden', 'class="qwen-workspace"', 1)
        code = (STATIC / "qwen-edit.js").read_text(encoding="utf-8")
        code = code.replace('const media = id => `/api/assets/${encodeURIComponent(id)}/content`;', 'const media = id => window.fixtureImage;')
        css = (STATIC / "lab.css").read_text(encoding="utf-8") + (STATIC / "qwen-edit.css").read_text(encoding="utf-8")
        fixture = r"""
        const check = (value, message) => {if(!value) throw Error(message);};
        window.fixtureImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
        window.PanelForgeLabNavigation={switchView:()=>true};
        window.PanelForgeModelPicker={populate:(select,models,current)=>{select.replaceChildren(...models.map(m=>new Option(m.label,m.id)));select.value=current||models[0]?.id||'';},select:(select,id)=>{select.value=id;},setDisabled:()=>{}};
        const settings={resolution:'source',aspect_ratio:'1:1',steps:25,cfg:1,seed:'18446744073709551615',reuse_seed:true,negative_prompt:''};
        const current={id:'stage-1',index:1,mode:'edit',source_asset_id:'source',source_dimensions:[160,96],label:'Modification 1',revision:0,
          settings,model_id:'fake',draft:'',prompt:'',prompt_fingerprint:null,prompt_ready:false,summary:'',references:[],messages:[],attempts:[],accepted_attempt_id:null,feedback_attempt_id:null,
          render_inputs:[{id:'source',asset_id:'source',name:'Source',role:'Image à modifier',tag:'<image1>'}],render_dimensions:[160,96]};
        const project={id:'qwen-fixture',name:'Projet test',version:1,active_stage_id:'stage-1',stages:[current],export_path:null,export_error:null};
        const sent=[]; let patchCount=0;
        window.fetch=async(url,options={})=>{
          const method=options.method||'GET'; sent.push([url,method,options.body]);
          const out=(data,status=200)=>({ok:status<400,status,json:async()=>structuredClone(data)});
          if(url.endsWith('/spec'))return out({enabled:true});
          if(url.endsWith('/models'))return out({models:[{id:'fake',label:'Fake vision',source:'server'}]});
          if(url.endsWith('/projects')&&method==='GET')return out({projects:[{id:project.id,name:project.name}]});
          if(url.endsWith('/projects/'+project.id)&&method==='GET')return out({project});
          if(method==='PATCH'){
            const data=JSON.parse(options.body); check(data.revision===current.revision,'stale UI revision');
            const oldRefs=JSON.stringify(current.references);
            for(const [key,value]of Object.entries(data.changes)){if(key==='name')project.name=value;else current[key]=value;}
            current.render_inputs=[{id:'source',asset_id:'source',name:'Source',role:'base',tag:'<image1>'},...current.references.filter(r=>r.active&&r.usage==='render').map((r,i)=>({...r,tag:`<image${i+2}>`}))];
            if(JSON.stringify(current.references)!==oldRefs)current.prompt_ready=false;
            if(Object.hasOwn(data.changes,'prompt'))current.prompt_ready=true;
            current.revision++;project.version++;patchCount++;return out({project});
          }
          if(url.endsWith('/references')&&method==='POST'){
            const f=options.body;check(Number(f.get('revision'))===current.revision,'upload revision');
            current.references.push({id:'ref-'+current.references.length,asset_id:'image-'+current.references.length,name:f.get('name'),role:'',usage:f.get('usage'),active:true});
            current.revision++;project.version++;return out({project},201);
          }
          throw Error('Unexpected request '+method+' '+url);
        };
        """
        scenario = r"""
        (async()=>{try{
          const wait=async fn=>{for(let i=0;i<150;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw Error('UI timeout');};
          const el=id=>document.getElementById('qw-'+id);
          await wait(()=>!el('editor').hidden);
          check(el('seed').value==='18446744073709551615','64 bit seed altered by browser');
          el('steps').value='28';el('steps').dispatchEvent(new Event('change',{bubbles:true}));
          await wait(()=>current.settings.steps===28 && el('save-state').textContent.includes('Enregistré'));
          el('draft').value='Reprends les couleurs de mon inspiration.';el('draft').dispatchEvent(new Event('input',{bubbles:true}));
          await wait(()=>current.draft.includes('inspiration'));
          const transfer=new DataTransfer();transfer.items.add(new File(['fake image'],'palette.png',{type:'image/png'}));
          el('attachment-files').files=transfer.files;el('attachment-files').dispatchEvent(new Event('change',{bubbles:true}));
          await wait(()=>current.references.length===1 && !el('add-assistant').disabled);
          check(current.references[0].usage==='assistant','chat image leaked to render by default');
          check(el('assistant-images').querySelectorAll('.qw-ref').length===1,'inspiration thumbnail missing');
          check(el('render-images').querySelectorAll('.qw-ref').length===1,'assistant image leaked into render strip');
          el('assistant-images').querySelector('.qw-ref-edit').click();
          const usage=el('dialog-body').querySelector('select');usage.value='render';
          [...el('dialog-body').querySelectorAll('button')].find(b=>b.textContent==='Enregistrer').click();
          await wait(()=>current.references[0].usage==='render' && !el('dialog').open);
          check(el('render-images').querySelectorAll('.qw-ref').length===2,'promoted reference not shown');
          check(el('assistant-images').querySelectorAll('.qw-ref').length===0,'promoted reference duplicated');
          el('draft').value='';el('draft').dispatchEvent(new Event('input',{bubbles:true}));
          await wait(()=>current.draft==='');
          el('prompt-details').open=true;
          el('prompt').value='Use <image1> as the base and <image2> for colors only.';
          el('prompt').dispatchEvent(new Event('input',{bubbles:true}));
          check(el('generate').disabled,'unsaved prompt could be generated');
          el('save-prompt').click();
          await wait(()=>current.prompt_ready && !el('generate').disabled);
          check(sent.filter(r=>r[0].endsWith('/messages')).length===0,'editing UI silently called the LLM');
          check(sent.filter(r=>r[0].endsWith('/attempts')).length===0,'editing UI silently generated');
          check(document.documentElement.scrollWidth<=window.innerWidth+2,'page overflows horizontally');
          check(patchCount>=4,'autosave did not persist edits');
          document.body.innerHTML='<pre id="result">QWEN_BROWSER_OK</pre>';
        }catch(error){document.body.innerHTML='<pre id="result"></pre>';document.getElementById('result').textContent=error.stack;}})();
        """
        document = '<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>' + page
        document += '<script>' + fixture + '</script><script>' + code + '</script><script>' + scenario + '</script></body></html>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qwen.html"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run([str(browsers[0]), "--headless", "--disable-gpu", "--no-sandbox",
                "--disable-background-networking", "--allow-file-access-from-files", "--window-size=1440,1100",
                "--virtual-time-budget=12000", "--dump-dom", path.as_uri()], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=40)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('<pre id="result">QWEN_BROWSER_OK</pre>', result.stdout)
