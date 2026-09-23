"""Full Qwen V2 interactions against a fake in-page API; no live service."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class QwenEditBrowserTest(unittest.TestCase):
    def test_guide_roles_prompt_autosave_and_contained_layout(self):
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        browsers = [*cache.glob("chromium-*/chrome-win/chrome.exe"),
                    *cache.glob("chromium-*/chrome-win64/chrome.exe")]
        if not browsers:
            self.skipTest("Chromium local non installé")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        page = '<main id="qwen-edit-lab-workspace"' + html.split(
            '<main id="qwen-edit-lab-workspace"', 1)[1].split(
            '<main id="krea2-edit-lab-workspace"', 1)[0]
        page = page.replace('class="qwen-v2-workspace" hidden',
                            'class="qwen-v2-workspace"', 1)
        code = (STATIC / "qwen-edit-v2.js").read_text(encoding="utf-8")
        code = code.replace(
            'const media = assetId => `/api/assets/${encodeURIComponent(assetId)}/content`;',
            'const media = assetId => window.fixtureImage;',
        )
        css = ((STATIC / "lab.css").read_text(encoding="utf-8")
               + (STATIC / "qwen-edit-v2.css").read_text(encoding="utf-8"))
        fixture = r"""
        const check = (value, message) => {if(!value) throw Error(message);};
        window.fixtureImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
        window.PanelForgeLabNavigation={switchView:()=>true};
        const settings={resolution:'source',aspect_ratio:'1:1',steps:25,cfg:1,
          seed:'18446744073709551615',reuse_seed:true,negative_prompt:'',color_finish:'natural'};
        const attempt={id:'attempt-1',status:'succeeded',kind:'generation',
          output_asset_id:'result-1',raw_output_asset_id:'raw-1',output_dimensions:[160,96],
          dimensions:[160,96],settings,finish:{mode:'natural',strength:55},
          summary:'Mur recoloré en vert.',prompt:'Recolor the wall green.',
          context:{references:[],render_inputs:[{id:'source'}]},error:null};
        const current={id:'stage-1',index:1,mode:'edit',source_asset_id:'source',
          source_dimensions:[160,96],label:'Modification 1',revision:0,settings,
          model_id:'fake',draft:'',prompt:'',prompt_fingerprint:null,prompt_ready:false,
          summary:'',guide:null,references:[],messages:[],attempts:[attempt],
          accepted_attempt_id:null,feedback_attempt_id:null,
          render_inputs:[{id:'source',asset_id:'source',name:'Source',role:'Image à modifier',tag:'<image1>'}],
          render_dimensions:[160,96]};
        const project={id:'qwen-fixture',name:'Projet test',version:1,
          active_stage_id:'stage-1',stages:[current],export_path:null,export_error:null};
        const sent=[]; let patchCount=0;
        const rebuildInputs=()=>{
          const values=[{id:'source',asset_id:'source',name:'Source',role:'base'}];
          if(current.guide)values.push({id:'guide',asset_id:current.guide.mask_asset_id,name:'Zone peinte',role:'zone'});
          values.push(...current.references.filter(r=>r.active&&r.usage==='render'));
          current.render_inputs=values.map((value,index)=>({...value,tag:`<image${index+1}>`}));
        };
        window.fetch=async(url,options={})=>{
          const method=options.method||'GET'; sent.push([url,method,options.body]);
          const out=(data,status=200)=>({ok:status<400,status,json:async()=>structuredClone(data)});
          if(url.endsWith('/models'))return out({models:[{id:'fake',label:'Fake vision',source:'server'}]});
          if(url.endsWith('/projects')&&method==='GET')return out({projects:[{
            id:project.id,name:project.name,stage_count:1,active_stage_id:current.id,
            thumbnail_asset_id:'source',updated_at:'2026-09-23T10:00:00Z'}]});
          if(url.endsWith('/projects/'+project.id)&&method==='GET')return out({project});
          if(method==='PATCH'){
            const data=JSON.parse(options.body);check(data.revision===current.revision,'stale UI revision');
            const oldContext=JSON.stringify([current.references,current.guide]);
            for(const [key,value]of Object.entries(data.changes)){
              if(key==='name')project.name=value;else current[key]=value;
            }
            rebuildInputs();
            if(JSON.stringify([current.references,current.guide])!==oldContext)current.prompt_ready=false;
            if(Object.hasOwn(data.changes,'prompt'))current.prompt_ready=true;
            current.revision++;project.version++;patchCount++;return out({project});
          }
          if(url.endsWith('/references')&&method==='POST'){
            const form=options.body;check(Number(form.get('revision'))===current.revision,'upload revision');
            current.references.push({id:'ref-'+current.references.length,
              asset_id:'image-'+current.references.length,name:form.get('name'),role:'',
              usage:form.get('usage'),active:true});
            rebuildInputs();current.prompt_ready=false;current.revision++;project.version++;
            return out({project},201);
          }
          if(url.endsWith('/guide')&&method==='POST'){
            const form=options.body;check(Number(form.get('revision'))===current.revision,'guide revision');
            check(form.get('mask') instanceof Blob,'guide mask missing');
            current.guide={mask_asset_id:'guide-1',source_asset_id:'source',width:1,height:1,
              request_id:form.get('request_id'),updated_at:'2026-09-23T10:00:00Z'};
            rebuildInputs();current.prompt_ready=false;current.revision++;project.version++;
            return out({project},201);
          }
          throw Error('Unexpected request '+method+' '+url);
        };
        """
        scenario = r"""
        (async()=>{try{
          const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw Error('UI timeout');};
          const el=id=>document.getElementById('qv2-'+id);
          await wait(()=>!el('editor').hidden);
          check(el('seed').value==='18446744073709551615','64 bit seed altered by browser');
          check(el('attempts').querySelectorAll('.qv2-attempt-card').length===1,'attempt card missing');
          check(el('attempts').textContent.includes('seed 18446744073709551615'),'seed hidden from history');
          check([...el('after').options].some(option=>option.textContent.includes('Qwen brut')),'raw Qwen result not archived in comparator');
          check(el('projects').querySelectorAll('button').length===1,'visual project navigation missing');
          check(!el('zoom-before').disabled&&!el('zoom-after').disabled,'comparison zoom actions unavailable');
          const compare=el('compare-view'),compareBox=compare.getBoundingClientRect();let captured=null;
          compare.setPointerCapture=id=>{captured=id;};
          compare.hasPointerCapture=id=>captured===id;
          compare.releasePointerCapture=id=>{if(captured===id)captured=null;};
          const comparePointer=(type,ratio)=>compare.dispatchEvent(new PointerEvent(type,{bubbles:true,
            clientX:compareBox.left+compareBox.width*ratio,clientY:compareBox.top+compareBox.height/2,
            button:0,pointerId:11,pointerType:'mouse'}));
          comparePointer('pointerdown',.2);comparePointer('pointermove',.76);comparePointer('pointerup',.76);
          check(Math.round(Number(el('split').value))===76,'image drag did not move comparator');
          check(compare.style.getPropertyValue('--qv2-split').startsWith('76'),'divider is not synchronized');
          check(el('split').getAttribute('aria-valuetext')==='76 % avant, 24 % après','accessible split value missing');

          el('steps').value='28';el('steps').dispatchEvent(new Event('change',{bubbles:true}));
          await wait(()=>current.settings.steps===28&&el('save-state').textContent.includes('Enregistré'));
          el('draft').value='Reprends les couleurs de mon inspiration.';
          el('draft').dispatchEvent(new Event('input',{bubbles:true}));
          await wait(()=>current.draft.includes('inspiration'));
          const transfer=new DataTransfer();
          transfer.items.add(new File(['fake image'],'palette.png',{type:'image/png'}));
          el('attachment-files').files=transfer.files;
          el('attachment-files').dispatchEvent(new Event('change',{bubbles:true}));
          await wait(()=>current.references.length===1&&!el('add-assistant').disabled);
          check(current.references[0].usage==='assistant','assistant image leaked to Qwen');
          check(el('references').querySelectorAll('.qv2-reference').length===1,'reference card missing');
          el('references').querySelector('.qv2-reference button').click();
          const usage=el('dialog-body').querySelector('select');usage.value='render';
          [...el('dialog-body').querySelectorAll('button')].find(button=>button.textContent==='Enregistrer').click();
          await wait(()=>current.references[0].usage==='render'&&!el('dialog').open);
          check(el('references').textContent.includes('Assistant + Qwen'),'promoted Qwen role not visible');

          el('show-guide').click();
          await wait(()=>!el('guide-panel').hidden&&el('guide-canvas').width===1);
          const canvas=el('guide-canvas'),box=canvas.getBoundingClientRect();
          const pointer={bubbles:true,clientX:box.left+box.width/2,clientY:box.top+box.height/2,button:0,pointerId:7};
          canvas.dispatchEvent(new PointerEvent('pointerdown',pointer));
          canvas.dispatchEvent(new PointerEvent('pointerup',pointer));
          await wait(()=>!el('guide-save').disabled);
          el('guide-save').click();
          await wait(()=>current.guide&&el('guide-summary').classList.contains('ready'));
          check(current.render_inputs[1].id==='guide','guide is not the second Qwen image');

          el('draft').value='';el('draft').dispatchEvent(new Event('input',{bubbles:true}));
          await wait(()=>current.draft==='');
          el('prompt-details').open=true;
          el('prompt').value='Use <image1> as the base, edit the region in <image2>, and use <image3> for colors.';
          el('prompt').dispatchEvent(new Event('input',{bubbles:true}));
          check(el('render').disabled,'unsaved prompt could be generated');
          el('save-prompt').click();
          await wait(()=>current.prompt_ready&&!el('render').disabled);
          check(sent.filter(row=>row[0].endsWith('/messages')).length===0,'editing silently called the LLM');
          check(sent.filter(row=>row[0].endsWith('/attempts')).length===0,'editing silently generated');
          check(document.documentElement.scrollWidth<=window.innerWidth+2,'page overflows horizontally');
          check(patchCount>=5,'autosave did not persist edits');
          document.body.innerHTML='<pre id="result">QWEN_V2_BROWSER_OK</pre>';
        }catch(error){
          document.body.innerHTML='<pre id="result"></pre>';
          document.getElementById('result').textContent=error.stack;
        }})();
        """
        document = ('<!doctype html><html><head><meta charset="utf-8"><style>' + css
                    + '</style></head><body>' + page + '<script>' + fixture
                    + '</script><script>' + code + '</script><script>' + scenario
                    + '</script></body></html>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qwen-v2.html"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run([
                str(browsers[0]), "--headless", "--disable-gpu", "--no-sandbox",
                "--disable-background-networking", "--allow-file-access-from-files",
                "--window-size=1440,1100", "--virtual-time-budget=15000", "--dump-dom",
                path.as_uri(),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('<pre id="result">QWEN_V2_BROWSER_OK</pre>', result.stdout)
