"""User-run browser coverage with mocked HTTP; no service or generation calls."""
import json
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class CreationBatchBrowserTests(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_import_launch_retry_refresh_visibility_and_preview(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        if not browsers and chrome.is_file():
            browsers = [chrome]
        if not browsers:
            self.skipTest("local Chromium or Chrome not installed")
        source = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="creation-batch-workspace"' + source.split('<main id="creation-batch-workspace"', 1)[1].split('<main id="krea2-assisted-lab-workspace"', 1)[0]
        model_picker = (STATIC / "lab.js").read_text(encoding="utf-8").split("const ui = {};", 1)[0]
        bootstrap = r"""
          const calls=[],timers=new Map(),nativeTimeout=window.setTimeout.bind(window);
          window.setTimeout=(fn,ms,...args)=>{
            if(ms===2500){const id=nativeTimeout(()=>{},100000);timers.set(id,fn);return id;}
            return nativeTimeout(fn,ms,...args);
          };
          const nativeClear=window.clearTimeout.bind(window);
          window.clearTimeout=id=>{timers.delete(id);nativeClear(id);};
          let visibility='visible',batch=null,failReceipt=true,failVariant=true;
          const variantReceipts=new Map();let liveMonitor={},failBulk=false;
          let bulkGate=null,releaseBulk=null;
          const imageUrl='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640"><rect width="360" height="640" fill="teal"/></svg>');
          Object.defineProperty(document,'visibilityState',{get:()=>visibility,configurable:true});
          const gemma='local::unsloth/gemma-4-31b-it-qat-GGUF';
          const spec={llm_models:[{id:'server::other',source:'server'},{id:gemma,source:'local'}],
            assistance_recipes:[{version:'6.0.0',label:'V6'},{version:'3.0.0',label:'V3'}]};
          const preset={preset_id:'style-fixture',revision:1,name:'Lips',category:'work',prompt_language:'en',
            settings:{model_id:'Krea2/test',loras:[],aspect_ratio:'9:16',megapixels:2.1}};
          const intentions=[{name:'First',intention:'<img src=x onerror=alert(1)> Rubis'},
            {name:'Second',intention:'Emeraudes\nOr jaune'}];
          try{localStorage.removeItem('panelforge.creation-batch.current.v1');localStorage.removeItem('panelforge.creation-batch.pending.v1');}catch(_){}
          window.fetch=async(url,options={})=>{
            calls.push([url,options]);const method=options.method||'GET';let data;
            if(url.includes('/spec'))data=spec;
            else if(url.endsWith('/style-presets'))data={presets:[preset]};
            else if(url.endsWith('/current'))data={batch};
            else if(url.endsWith('/csv'))data={intentions,count:2,ignored:1};
            else if(url.endsWith('/batches')&&method==='POST'){
              const body=JSON.parse(options.body);
              batch={batch_id:'creation-batch-'+body.request_id.replaceAll('-',''),name:body.name,revision:1,
                config:{...body,art_direction:null},preset_name:preset.name,
                terminal:false,counts:{total:2,finished:0,succeeded:0,failed:0},items:intentions.map((item,i)=>({
                  ...item,item_id:String(i+1),prompt_status:'queued',image_status:'waiting',error:null}))};
              if(failReceipt){failReceipt=false;throw new TypeError('Lost response fixture');}
              data={batch};
            }else if(url.endsWith('/factory')&&!url.includes('/items/')){
              if(bulkGate)await bulkGate;
              const report={sent:0,already_sent:0,failed:0,errors:[]};
              for(const item of batch.items){
                const renders=item.renders||[{...item,render_id:'initial',status:item.image_status}];
                for(const render of renders){
                  if(render.status!=='succeeded'||!render.output_asset_id)continue;
                  if(render.factory_item_id){report.already_sent++;continue;}
                  render.factory_item_id='factory-'+item.item_id+'-'+render.render_id;
                  if(render.render_id==='initial')item.factory_item_id=render.factory_item_id;
                  report.sent++;
                }
              }
              batch.revision++;
              if(failBulk){failBulk=false;throw new TypeError('Lost bulk response');}
              data={batch,factory_delivery:report};
            }else if(url.endsWith('/factory')){
              batch.items[0].factory_item_id='factory-one';batch.revision++;
              if(batch.items[0].renders)batch.items[0].renders[0].factory_item_id='factory-one';
              data={batch};
            }else if(url.endsWith('/variants')){
              const body=JSON.parse(options.body),item=batch.items[0];
              if(!variantReceipts.has(body.request_id)){
                if(body.kind==='render'){
                  item.renders||=[{render_id:'initial',label:'Original',status:'succeeded',output_asset_id:item.output_asset_id,
                    thumbnail_url:imageUrl,hover_url:imageUrl,image_url:imageUrl,factory_item_id:item.factory_item_id}];
                  item.renders.push({render_id:body.request_id,label:'Finition 4 steps · 8 + 4',status:'succeeded',
                    output_asset_id:'variant-asset',thumbnail_url:imageUrl,hover_url:imageUrl,image_url:imageUrl});
                }else{
                  const number=batch.items.filter(i=>i.parent_id==='1').length+1;
                  batch.items.push({item_id:'1.'+number,parent_id:'1',name:'Style '+number,intention:'Jewels',
                    prompt_status:body.kind==='art'?'succeeded':'queued',image_status:'waiting',renders:[]});
                }
                variantReceipts.set(body.request_id,true);batch.revision++;
              }
              if(body.kind==='render'&&failVariant){failVariant=false;throw new TypeError('Lost variant receipt');}
              data={batch};
            }else if(url.endsWith('/art-styles'))data={styles:[{style_id:'art-one',name:'Art deco',category:'Art',thumbnail_url:imageUrl,prompt:'Fine art'}]};
            else if(url.includes('/batches/'))data=url.includes('known_revision='+batch.revision+'&')?{unchanged:true,monitor:liveMonitor}:{batch,monitor:liveMonitor};
            else throw new Error('Unexpected request '+url);
            return {ok:true,status:200,json:async()=>structuredClone(data)};
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>nativeTimeout(r,0));};
            const el=id=>document.getElementById('cb-'+id),root=document.getElementById('creation-batch-workspace');
            await settle();check(calls.length===0,'no hidden discovery');
            root.hidden=false;await settle();
            check(el('recipe').value==='6.0.0'&&!el('inspiration').checked,'batch defaults');
            check(el('render-mode').value==='krea2-flux-klein','Flux Klein is the default render mode');
            check([...el('render-mode').options].map(o=>o.value).join(',')==='krea2-sampling,krea2-flux-klein','two supported modes');
            check(el('render-mode-note').textContent.includes('Moody Beta'),'fixed Moody Beta is visible');
            check(el('model').value===gemma&&el('local').checked,'local Gemma default');
            check(el('factory-all').disabled,'bulk send disabled before images');
            check(el('factory-all').parentElement.contains(el('count')),'bulk button beside global count');
            check(getComputedStyle(el('factory-all')).backgroundColor==='rgb(105, 69, 144)','factory purple');
            check(!root.querySelector('aside details'),'form always expanded');
            const nav=[...root.querySelectorAll('[data-image-lab-mode]')];
            check(nav[0].dataset.imageLabMode==='krea2-assisted-lab'&&nav.some(n=>n.dataset.imageLabMode==='creation-batch'),'batch navigation');
            const files=new DataTransfer();files.items.add(new File(['intention\ntext'],'lips.csv',{type:'text/csv'}));
            el('file').files=files.files;el('file').dispatchEvent(new Event('change'));await settle();
            check(el('import-state').textContent.includes('2 intentions'),'parsed count');
            check(el('name').value==='lips','filename supplies batch name');
            el('render-mode').value='krea2-sampling';
            el('preset').value='style-fixture';el('preset').dispatchEvent(new Event('change'));
            check(el('render-mode').value==='krea2-sampling','preset selection preserves render mode');
            el('name').value='My batch';el('language').value='zh';
            el('refresh').click();await settle();
            check(el('name').value==='My batch'&&el('language').value==='zh'&&el('import-state').textContent.includes('2 intentions'),'refresh preserves draft');
            check(el('render-mode').value==='krea2-sampling','refresh preserves draft render mode');
            el('launch').click();await settle();
            check(el('message').textContent.includes('Lost response'),'uncertain receipt is visible');
            el('render-mode').value='krea2-flux-klein';
            el('launch').click();await settle();
            const launches=calls.filter(([url,o])=>url.endsWith('/batches')&&o.method==='POST').map(([,o])=>JSON.parse(o.body));
            check(launches.length===2&&launches[0].request_id===launches[1].request_id,'retry uses same request ID');
            check(launches[0].language==='zh'&&!launches[0].local_inspiration,'explicit choices reach server');
            check(launches.every(body=>body.render_mode==='krea2-sampling'),'retry preserves the submitted mode');
            check(el('render-mode').value==='krea2-sampling','active batch restores its saved mode');
            check(!('settings' in launches[0])&&!('model_name' in launches[0]),'no client render override');
            check(el('rows').children.length===2&&!el('rows').querySelector('img'),'one safe text row per intention');
            check(el('fields').disabled,'active settings are frozen');
            check(el('render-mode').matches(':disabled'),'active render mode is frozen');
            batch.revision=2;batch.items[0]={...batch.items[0],prompt_status:'succeeded',image_status:'succeeded',
              output_asset_id:'asset-fixture',thumbnail_url:imageUrl,hover_url:imageUrl,image_url:imageUrl};
            batch.counts={total:2,finished:1,succeeded:1,failed:0};
            el('refresh').click();await settle();
            const preview=el('rows').querySelector('.cb-preview');check(preview,'result preview');
            check(!el('factory-all').disabled&&el('factory-all').textContent.includes('(1)'),'one available image');
            preview.dispatchEvent(new MouseEvent('mouseenter'));await settle();check(!document.querySelector('.cb-hover').hidden,'hover enlargement');
            check(document.querySelector('.cb-hover').getBoundingClientRect().height>420,'larger hover uses available space');
            preview.click();await settle();check(el('image-dialog').open,'full image opens on click');
            const rect=el('image-dialog').getBoundingClientRect();
            check(Math.abs(rect.left+rect.width/2-innerWidth/2)<3,'image dialog horizontally centered');
            check(Math.abs(rect.top+rect.height/2-innerHeight/2)<3,'image dialog vertically centered');
            check(rect.width<innerWidth*.8,'portrait dialog does not fill width');el('image-close').click();
            const factory=el('rows').querySelector('.cb-factory');check(factory.textContent==='+','compact factory plus');
            factory.click();await settle();check(factory.textContent==='✓'&&factory.disabled,'confirmed receipt');
            check(el('factory-all').disabled,'individual receipt removes image from bulk send');
            el('refresh').click();await settle();check(factory.textContent==='✓','receipt survives refresh');
            check(el('rows').querySelector('.cb-stage').textContent.includes('Terminé'),'completed prompt label');
            const regen=[...el('rows').querySelectorAll('button')].find(b=>b.textContent==='8 + 4');
            regen.click();await settle();check(el('message').textContent.includes('Lost variant receipt'),'variant uncertainty shown');
            regen.click();await settle();
            const variants=calls.filter(([u,o])=>u.endsWith('/variants')&&o.method==='POST').map(([,o])=>JSON.parse(o.body));
            check(variants.length===2&&variants[0].request_id===variants[1].request_id,'variant retry keeps command ID');
            check(el('rows').children[0].querySelectorAll('.cb-preview').length===2,'render beside original');
            check(el('rows').querySelector('.cb-preview')===preview,'original preview node preserved');
            const da=[...el('rows').children[0].querySelectorAll('button')].find(b=>b.textContent==='DA');
            da.click();await settle();el('art-grid').querySelector('button').click();await settle();
            check([...el('rows').children].map(r=>r.dataset.itemId).join(',')==='1,1.1,2','art child ordered after parent');
            const presetButton=[...el('rows').children[0].querySelectorAll('button')].find(b=>b.textContent==='Preset');
            presetButton.click();el('variant-dialog').querySelector('button').click();await settle();
            check([...el('rows').children].map(r=>r.dataset.itemId).join(',')==='1,1.1,1.2,2','creative preset child');
            const art=batch.items.find(i=>i.item_id==='1.1');
            art.image_status='succeeded';art.output_asset_id='asset-art';
            art.renders=[{render_id:'initial',label:'Original',status:'succeeded',output_asset_id:'asset-art',
              thumbnail_url:imageUrl,hover_url:imageUrl,image_url:imageUrl}];
            batch.revision++;el('refresh').click();await settle();
            check(el('factory-all').textContent.includes('(2)'),'regeneration and DA included');
            bulkGate=new Promise(resolve=>{releaseBulk=resolve;});
            const bulkCalls=()=>calls.filter(([url,o])=>url.endsWith('/factory')&&!url.includes('/items/')&&o.method==='POST');
            el('factory-all').click();el('factory-all').click();await settle();
            check(el('factory-all').disabled&&el('factory-all').getAttribute('aria-busy')==='true','bulk busy state');
            check(bulkCalls().length===1,'double click sends only one bulk request');
            root.hidden=true;await settle();releaseBulk();bulkGate=null;await settle();
            root.hidden=false;await settle();
            check(el('factory-all').disabled&&el('factory-all').textContent.includes('Images envoyées'),'bulk receipts shown');
            check([...el('rows').querySelectorAll('.cb-factory')].every(b=>b.textContent==='✓'),'all available cards checked');
            check(el('factory-state').textContent.includes('2 image(s) envoyée(s)'),'bulk summary');
            const second=batch.items.find(i=>i.item_id==='2');
            Object.assign(second,{image_status:'succeeded',output_asset_id:'asset-second',thumbnail_url:imageUrl,image_url:imageUrl});
            batch.revision++;el('refresh').click();await settle();
            check(!el('factory-all').disabled&&el('factory-all').textContent.includes('(1)'),'new image enables another send');
            failBulk=true;el('factory-all').click();await settle();
            check(el('factory-state').textContent.includes('Lost bulk response'),'uncertain bulk response shown');
            check(el('factory-all').disabled,'receipt refreshed after lost response');
            check(bulkCalls().length===2,'no automatic duplicate send after uncertainty');
            el('refresh').click();await settle();check(el('factory-all').disabled,'bulk receipts survive refresh');
            liveMonitor={'2':{prompt:{status:'queued',position:2,progress:0},images:{initial:{status:'waiting'}}},
              '1':{prompt:{status:'succeeded',progress:1},images:{initial:{status:'running',progress:.5,message:'Sampling'}}}};
            const tick=[...timers.values()][0];if(tick){timers.clear();await tick();await settle();}
            check(el('rows').querySelector('[data-item-id="2"] .cb-stage').textContent.includes('position 2'),'shared queue position');
            check(el('rows').children[0].children[3].querySelector('progress').value===.5,'live progress without durable revision change');
            visibility='hidden';document.dispatchEvent(new Event('visibilitychange'));await settle();
            check(timers.size===0,'hidden tab stops polling');
            visibility='visible';document.dispatchEvent(new Event('visibilitychange'));await settle();
            check(timers.size===1,'visible active batch resumes polling');
            root.hidden=true;await settle();check(timers.size===0,'other workshop stops polling');
            check(!calls.some(([url])=>url.includes('/projects')),'no project history loaded');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        html = '<meta charset="utf-8"><style>' + (STATIC / "creation-batch.css").read_text(encoding="utf-8") + '</style><pre id="result">PENDING</pre>' + markup
        for script in (bootstrap, model_picker, (STATIC / "creation-batch.js").read_text(encoding="utf-8"), scenario):
            html += '<script>' + script.replace('</script', '<\\/script') + '</script>'
        self.run_browser(browsers[-1], html)
