"""User-run browser scenario with mocked HTTP, images, prompts and renders."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class MhAssistedBrowserTests(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_pose_preset_language_creation_retry_and_frozen_result_choices(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        if not browsers and chrome.is_file(): browsers = [chrome]
        if not browsers: self.skipTest("local Chromium or Chrome not installed")
        source = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="mh-assisted-lab-workspace"' + source.split('<main id="mh-assisted-lab-workspace"', 1)[1].split('<main id="creation-batch-workspace"', 1)[0]
        markup = markup.replace('class="krea2-assisted-lab-workspace" hidden>', 'class="krea2-assisted-lab-workspace">', 1)
        model_picker = (STATIC / "lab.js").read_text(encoding="utf-8").split("const ui = {};", 1)[0]
        bootstrap = r"""
          const calls=[], timers=new Map(), nativeTimeout=window.setTimeout.bind(window), nativeClear=window.clearTimeout.bind(window);
          window.setTimeout=(fn,ms,...args)=>{if(ms===2000){const id=nativeTimeout(()=>{},100000);timers.set(id,fn);return id;}return nativeTimeout(fn,ms,...args);};
          window.clearTimeout=id=>{timers.delete(id);nativeClear(id);};
          const imageUrl='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="90" height="120"><rect width="90" height="120" fill="teal"/></svg>');
          const imageSrc=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
          Object.defineProperty(HTMLImageElement.prototype,'src',{get(){return imageSrc.get.call(this);},set(value){this.dataset.requestedSrc=value;imageSrc.set.call(this,imageUrl);},configurable:true});
          try{sessionStorage.removeItem('panelforge.mh-assisted.current.v1');}catch(_){}
          const clone=value=>JSON.parse(JSON.stringify(value));
          const model='local::unsloth/gemma-4-31B-it-qat-GGUF';
          const settings={aspect_ratio:'9:16',resolution:'2',steps:18,seed:'18446744073709551610',reuse_seed:false,
            reference_megapixels:1,reference_mode:'resize',color_finish:'raw'};
          const art={style_id:'art-one',name:'Jewels',category:'Matières',prompt:'Gemstones',thumbnail_url:imageUrl};
          const preset={preset_id:'preset-one',revision:2,name:'Personal style',prompt_language:'zh',art_direction:art,image_url:imageUrl};
          const pose=(id,angle)=>({id,pose_id:'pose-one',number:'P001',name:'<img src=x onerror=window.pwned=true>',
            category:'Debout',family:'Corps entier',angle,catalog_revision:'r1'});
          const poses=[pose('pose_front','Face'),pose('pose_side','Profil')];
          const filterPoses=[
            {id:'duo_seated',pose_id:'duo-seated',number:'P002',name:'Assis enlacés',source_name:'寄り添う',family:'Duo',category:'Assis',angle:'Face'},
            {id:'duo_standing',pose_id:'duo-standing',number:'P003',name:'Debout enlacés',family:'Duo',category:'Debout enlacés',angle:'Trois-quarts'},
            {id:'solo_nsfw',pose_id:'solo-nsfw',number:'P062',name:'Genoux à la poitrine',family:'Corps entier · NSFW',category:'Allongé',angle:'Profil'}
          ];
          let filterFixtures=false;
          const personalPoses=[
            {id:'personal_v1',pose_id:'personal-group',number:'K001',name:'Posture revue',family:'Mes poses',category:'Assis',angle:'Face',elevation:'Plongée',view_label:'Face · plongée · ligne 1 · rendu 1'},
            {id:'personal_v2',pose_id:'personal-group',number:'K001',name:'Posture revue',family:'Mes poses',category:'Assis',angle:'Face',elevation:'Hauteur du sujet',view_label:'Face · ligne 2 · rendu 2'},
            {id:'personal_back',pose_id:'personal-group',number:'K001',name:'Posture revue',family:'Mes poses',category:'Assis',angle:'Dos',view_label:'Dos · ligne 3 · rendu 1',confidence:'low',review_note:'Appuis masqués.'}
          ];
          let project=null, lostRender=true, lostReferences=true;
          const current=()=>project.stages[0];
          function applyPose(id){
            const p=poses.find(p=>p.id===id);current().creative.pose=p?{...p,asset_id:id,reference_id:'mh-pose'}:null;
            current().references=current().references.filter(r=>r.id!=='mh-pose');
            if(p)current().references.unshift({id:'mh-pose',asset_id:id,name:'Pose',role:'Posture',usage:'render',active:true});
          }
          window.fetch=async(url,options={})=>{
            calls.push([url,options]);const method=options.method||'GET';let data;
            if(url.endsWith('/spec')) data={defaults:settings,aspect_ratios:['9:16','1:1'],default_model_id:model,pose_catalog:{state:'ready'}};
            else if(url.endsWith('/models'))data={models:[{id:model,source:'local'},{id:'server-model',source:'server'}]};
            else if(url.includes('/loras'))data={models:['minmax_nsfw/style.safetensors'],supported:true,maximum:4};
            else if(url.endsWith('/style-presets'))data={presets:[preset]};
            else if(url.endsWith('/art-styles'))data={styles:[art]};
            else if(url.endsWith('/poses'))data={entries:filterFixtures?[...poses,...filterPoses,...personalPoses]:poses,catalog:{state:'ready',original_previews:true,pose_count:1,image_count:2,categories:['Debout'],families:['Corps entier'],angles:['Face','Profil','Trois-quarts','Plongée','Dos']}};
            else if(url.endsWith('/projects')&&method==='GET')data={projects:project?[{id:project.id,name:project.name,thumbnail_asset_id:'pose_side'}]:[]};
            else if(url.endsWith('/projects')&&method==='POST'){
              const f=options.body;
              project={id:'mh-'+f.get('request_id').replaceAll('-',''),name:f.get('name'),version:1,active_stage_id:'stage-one',stages:[{
                id:'stage-one',revision:0,mode:'composition',source_asset_id:null,settings:clone(settings),model_id:f.get('model_id'),
                draft:f.get('intention'),prompt:'',prompt_ready:false,render_dimensions:[1088,1920],references:[],messages:[],attempts:[],feedback_attempt_id:null,
                creative:{prompt_language:f.get('prompt_language'),style_preset:f.get('preset_id')?preset:null,art_direction:f.get('art_style_id')?art:null,pose:null}}]};
              current().references=JSON.parse(f.get('reference_details')||'[]').map((m,i)=>({...m,id:'ref-'+i,asset_id:'asset-'+i,active:true}));
              applyPose(f.get('pose_id'));data={project:clone(project)};
            }else if(url.endsWith('/references/batch')){
              const f=options.body,s=current(),id=f.get('request_id');s.reference_commands||=[];
              if(!s.reference_commands.some(r=>r.request_id===id)){
                if(f.get('replace_id'))s.references.find(r=>r.id===f.get('replace_id')).active=false;
                s.references.push(...JSON.parse(f.get('reference_details')).map((m,i)=>({...m,id:'added-'+id+'-'+i,asset_id:'added-asset-'+id+'-'+i,active:true})));
                s.reference_commands.push({request_id:id});s.revision++;s.prompt_ready=false;project.version++;
              }
              if(lostReferences){lostReferences=false;throw new TypeError('Lost reference response');}
              data={project:clone(project)};
            }else if(url.endsWith('/creative')){
              const body=JSON.parse(options.body),c=current().creative;
              if('prompt_language' in body.changes)c.prompt_language=body.changes.prompt_language;
              if('pose_id' in body.changes)applyPose(body.changes.pose_id);
              if('art_style_id' in body.changes)c.art_direction=body.changes.art_style_id?art:null;
              current().prompt_ready=false;current().revision++;project.version++;data={project:clone(project)};
            }else if(url.endsWith('/messages')){
              const body=JSON.parse(options.body),s=current();
              if(!s.messages.some(m=>m.request_id===body.request_id))s.messages.push({id:'message-'+s.messages.length,request_id:body.request_id,text:s.draft,reply:'Prompt prêt',status:'succeeded',applied:true});
              s.draft='';s.prompt='Use <Picture 1> for posture.';s.prompt_ready=true;s.revision++;project.version++;data={project:clone(project)};
            }else if(url.endsWith('/attempts')){
              const body=JSON.parse(options.body),s=current();
              if(!s.attempts.some(a=>a.request_id===body.request_id))s.attempts.push({id:'attempt-one',request_id:body.request_id,status:'queued',settings:clone(s.settings),
                dimensions:[1088,1920],context:{creative:clone(s.creative),references:clone(s.references)},prompt:s.prompt});
              s.revision++;project.version++;
              if(lostRender){lostRender=false;throw new TypeError('Lost render response');}
              data={project:clone(project)};
            }else if(method==='PATCH'){
              const changes=JSON.parse(options.body).changes;Object.assign(current(),changes);
              if(changes.references)current().prompt_ready=false;
              current().revision++;project.version++;data={project:clone(project)};
            }else if(project&&url.endsWith('/projects/'+project.id))data={project:clone(project)};
            else throw new Error('Unexpected request '+method+' '+url);
            return {ok:true,status:200,json:async()=>clone(data)};
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const el=id=>document.getElementById('mh-'+id);
            const settle=async()=>{for(let i=0;i<18;i++)await new Promise(r=>nativeTimeout(r,0));};
            const change=(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event('change',{bubbles:true}));};
            await settle();
            check(el('create').disabled,'reference required in UI');
            check(el('new-model').value===model,'local Gemma default');
            change('new-preset','preset-one');
            check(el('new-language').value==='zh'&&el('new-art-name').textContent==='Jewels','preset language and direction retained');
            el('new-pose-choose').click();await settle();
            check(el('picker').open&&el('picker-grid').children.length===1,'poses grouped across angles');
            const card=el('picker-grid').firstElementChild,angle=card.querySelector('select');
            angle.value='pose_side';angle.dispatchEvent(new Event('change'));
            card.querySelector('button').click();await settle();
            check(el('new-pose-name').textContent.includes('Profil'),'chosen angle visible');
            check(!window.pwned,'catalogue strings are rendered as text');
            check(!el('create').disabled,'pose alone permits creation');
            filterFixtures=true;el('new-pose-choose').click();await settle();
            const options=id=>[...el(id).options].map(o=>o.value).filter(Boolean);
            change('picker-family','Duo');
            check(JSON.stringify(options('picker-category'))===JSON.stringify(['Assis','Debout enlacés']),'Duo categories exclude solo and bust categories');
            change('picker-category','Assis');
            check(JSON.stringify(options('picker-angle'))===JSON.stringify(['Face']),'angles follow the selected category');
            change('picker-family','Corps entier');
            check(el('picker-category').value===''&&options('picker-category').join()==='Debout','incompatible category resets on family change');
            change('picker-angle','Profil');change('picker-family','Duo');
            check(el('picker-angle').value===''&&options('picker-angle').join()==='Face,Trois-quarts','unavailable angle resets on family change');
            el('picker-search').value='enlaces';el('picker-search').dispatchEvent(new Event('input'));
            check(el('picker-grid').children.length===2,'French search ignores accents');
            el('picker-search').value='寄り添う';el('picker-search').dispatchEvent(new Event('input'));
            check(el('picker-grid').children.length===1,'original catalogue names remain searchable');
            el('picker-search').value='';el('picker-search').dispatchEvent(new Event('input'));
            change('picker-family','Corps entier · NSFW');
            check(el('picker-grid').children.length===1&&options('picker-category').join()==='Allongé','NSFW family is discoverable and filtered');
            el('picker-search').value='no-match';el('picker-search').dispatchEvent(new Event('input'));
            check(el('picker-grid').children.length===0&&options('picker-category').length===0&&options('picker-angle').length===0,'empty results clear unavailable filter options');
            el('picker-search').value='';el('picker-search').dispatchEvent(new Event('input'));
            change('picker-family','Mes poses');
            check(el('picker-grid').children.length===1,'reviewed views share a pose card');
            const personalCard=el('picker-grid').firstElementChild,personalViews=personalCard.querySelector('select');
            check(new Set([...personalViews.options].map(o=>o.textContent)).size===3,'same-angle versions have distinct labels');
            personalViews.value='personal_v2';personalViews.dispatchEvent(new Event('change'));
            personalCard.querySelector('img').click();
            check(el('image-full').dataset.requestedSrc.endsWith('/personal_v2/original'),'preview opens selected original, not thumbnail');
            el('image-close').click();
            personalViews.value='personal_back';personalViews.dispatchEvent(new Event('change'));
            check(personalCard.textContent.includes('Classement à confirmer')&&personalCard.textContent.includes('Appuis masqués'),'uncertain classification is visible');
            change('picker-angle','Plongée');
            check(el('picker-grid').firstElementChild.querySelector('select').options.length===1,'height filter finds frontal overhead view');
            change('picker-angle','Dos');
            check(el('picker-grid').firstElementChild.querySelector('select').value==='personal_back','back angle filter is usable');
            el('picker-close').click();filterFixtures=false;
            const selectFiles=(input,names)=>{
              const transfer=new DataTransfer();names.forEach(name=>transfer.items.add(new File(['fixture'],name,{type:'image/png'})));
              input.files=transfer.files;input.dispatchEvent(new Event('change'));
            };
            selectFiles(el('new-reference'),['identity.png','wardrobe.png']);
            check(el('new-references').querySelectorAll('img').length===2,'immediate previews before creation');
            check(el('new-reference-count').textContent.includes('3/9'),'pose counts toward the reference limit');
            const role=el('new-references').querySelector('input[type=text]');role.value='Identity only';role.dispatchEvent(new Event('input'));
            el('new-references').querySelector('img').click();check(el('image-dialog').open,'preview can be enlarged');el('image-close').click();
            selectFiles(el('new-reference'),Array.from({length:7},(_,i)=>'extra-'+i+'.png'));
            check(el('create').disabled,'nine images plus a pose exceed the limit');
            for(const card of [...el('new-references').children].slice(2)) [...card.querySelectorAll('button')].find(b=>b.textContent==='Retirer').click();
            check(!el('create').disabled,'removing pending images restores valid selection');
            change('new-name','MH reference fixture');change('new-intention','Create a portrait');
            el('create').click();el('create').click();await settle();
            const creations=calls.filter(([u,o])=>u.endsWith('/projects')&&o.method==='POST');
            check(creations.length===1,'double click creates one project');
            const form=creations[0][1].body;
            check(form.get('pose_id')==='pose_side'&&form.get('preset_id')==='preset-one'&&form.get('prompt_language')==='zh'&&form.get('art_style_id')==='art-one','all selections transmitted');
            check(form.getAll('references').length===2&&JSON.parse(form.get('reference_details'))[0].role==='Identity only','all images and roles travel with creation');
            check(!el('editor').hidden&&el('conversation').textContent.includes('Prompt prêt'),'prompt and discussion shown');
            check(!el('render').disabled,'prepared prompt ready');
            const activeRole=el('references').querySelector('input[type=text]');activeRole.value='Face only';activeRole.dispatchEvent(new Event('input'));
            el('refresh').click();await settle();
            check(el('references').querySelector('input[type=text]').value==='Face only','refresh preserves role draft');
            el('save').click();await settle();check(current().references.find(r=>r.id==='ref-0').role==='Face only','role edits persist');
            selectFiles(el('reference-file'),['scene.png','light.png']);
            check(el('pending-references').children.length===2,'existing project previews a selection');
            el('reference-add').click();await settle();
            check(el('pending-references').children.length===0&&current().references.length===5,'lost batch response reconciles without duplicates');
            check(calls.filter(([u])=>u.endsWith('/references/batch')).length===1,'one atomic upload for the selection');
            change('active-language','en');await settle();check(el('render').disabled,'language change invalidates prompt');
            el('chat').click();await settle();check(!el('render').disabled,'new prompt allows render');
            change('ratio','1:1');change('seed','18446744073709551610');
            el('loras').querySelector('[data-lora-add]').click();
            document.querySelector('.minimax-lora-picker [data-lora-select]').click();
            const strength=el('loras').querySelector('input[type=number]');
            strength.value='.375';strength.dispatchEvent(new Event('input'));
            el('refresh').click();await settle();
            check(el('loras').querySelector('[data-lora-choose]').textContent.includes('style.safetensors')&&strength.value==='0.375','refresh retains unsaved LoRA settings');
            el('render').click();el('render').click();await settle();
            check(calls.filter(([u,o])=>u.endsWith('/attempts')&&o.method==='POST').length===1,'lost render receipt never duplicates submission');
            check(el('attempts').children.length===1&&el('render').disabled,'queued attempt reconciled after lost response');
            check(current().attempts[0].settings.seed==='18446744073709551610','uint64 seed remains text');
            check(current().attempts[0].settings.loras[0].strength===.375,'attempt pins selected LoRA strength');
            check(current().attempts[0].context.creative.pose.id==='pose_side','attempt pins pose');
            const originalReferences=JSON.stringify(current().attempts[0].context.references);
            selectFiles(el('references').querySelector('input[type=file]'),['replacement.png']);await settle();
            check(current().references.some(r=>r.active&&r.name==='replacement.png'),'individual replacement works in an existing project');
            check(current().references.filter(r=>r.active).length===5,'replacement keeps the same active reference count');
            check(JSON.stringify(current().attempts[0].context.references)===originalReferences,'replacement preserves previous attempt references');
            el('active-pose-choose').click();await settle();
            const nextCard=el('picker-grid').firstElementChild;nextCard.querySelector('button').click();await settle();
            check(current().creative.pose.id==='pose_front','active pose changed');
            check(current().attempts[0].context.creative.pose.id==='pose_side','previous attempt unchanged');
            change('message','Unsaved correction');change('ratio','9:16');
            el('refresh').click();await settle();
            check(el('message').value==='Unsaved correction'&&el('ratio').value==='9:16','refresh preserves unsaved fields');
            current().attempts[0].status='succeeded';current().attempts[0].output_asset_id='result-one';project.version++;
            el('refresh').click();await settle();
            check(el('attempts').querySelector('img'),'result preview available');
            check([...el('attempts').querySelectorAll('button')].some(b=>b.textContent.includes('retour visuel')),'feedback action present');
            el('save').click();await settle();check(current().draft==='Unsaved correction','explicit save preserves draft');
            current().attempts[0].status='running';project.version++;el('refresh').click();await settle();
            document.getElementById('mh-assisted-lab-workspace').hidden=true;await settle();
            check(timers.size===0,'hidden workshop stops polling');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        css = (STATIC / "lab.css").read_text(encoding="utf-8") + (STATIC / "mh-assisted.css").read_text(encoding="utf-8")
        app = (STATIC / "minimax-loras.js").read_text(encoding="utf-8") + (STATIC / "mh-assisted.js").read_text(encoding="utf-8")
        self.run_browser(browsers[-1], '<meta charset="utf-8"><style>' + css + '</style><pre id="result">PENDING</pre>'
                         + markup + '<script>' + model_picker + bootstrap + app + scenario + '</script>')
