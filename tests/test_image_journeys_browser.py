"""User-run browser interactions with an in-page fake API; no live server or model."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class ImageJourneyBrowserTest(unittest.TestCase):
    def test_compact_workshop_pause_draft_polling_and_transition_handoff(self):
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        browsers = [*cache.glob("chromium-*/chrome-win/chrome.exe"),
                    *cache.glob("chromium-*/chrome-win64/chrome.exe")]
        if not browsers:
            chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
            browsers = [chrome] if chrome.is_file() else []
        if not browsers:
            self.skipTest("Chromium local non installé")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        marker = '<main id="image-journey-workspace"'
        page = marker + html.split(marker, 1)[1].split("</main>", 1)[0] + "</main>"
        page = page.replace('class="ij-workspace" hidden', 'class="ij-workspace"', 1)
        code = (STATIC / "image-journeys.js").read_text(encoding="utf-8").replace(
            'const asset = id => "/api/assets/" + encodeURIComponent(id) + "/content";',
            'const asset = id => window.fixtureImage;')
        css = (STATIC / "lab.css").read_text(encoding="utf-8") + (STATIC / "image-journeys.css").read_text(encoding="utf-8")
        actions = (STATIC / 'image-journey-actions.js').read_text(encoding='utf-8')
        fixture = r"""
        const check=(value,message)=>{if(!value)throw Error(message);};
        window.fixtureImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
        sessionStorage.removeItem('panelforge.image-journey.project');
        sessionStorage.removeItem('panelforge.image-journey.project.excluded.journey-fixture');
        sessionStorage.removeItem('panelforge.image-journey.project.order.journey-fixture');
        window.setInterval=callback=>{window.pollJourney=callback;return 1;};
        const journeySpec={journey_presets:{miniature:'Miniature',realistic:'Aménagement réaliste'}};
        const calls=[];let project=null,resumeConflict=true,opened=null,holdGet=false,releaseGet=null,transferred=null;
        window.PanelForgeImageTransitions={open:async identity=>{opened=identity;}};
        const clone=value=>structuredClone(value);
        const publicProject=()=>({...clone(project),transferable_frame_ids:['source',
          ...(project.ordered_steps||project.steps).filter(s=>s.output_asset_id&&['usable','similar'].includes(s.review?.assessment)).map(s=>s.id)]});
        window.PanelForgeLabCore={request:async(url,options={})=>{
          const method=options.method||'GET';calls.push([url,method,options.body]);
          if(url.endsWith('/spec'))return Object.assign(journeySpec,{default_journey_version:'2',default_images:5,max_images:30,default_model_id:'vision',default_mask_model_id:'qwen-mask',transitions_available:true,hq_prompt:'Create a higher-resolution version of <Picture 1>. Preserve geometry and colors.'});
          if(url.endsWith('/models'))return {models:[{id:'vision',label:'Vision local',source:'local'},
            {id:'writer',label:'MiniMax writer',source:'server'}, {id:'qwen-mask',label:'Qwen vision',source:'local'}]};
          if(url.endsWith('/projects')&&method==='GET')return {projects:project?[clone(project)]:[]};
          if(url.endsWith('/projects')&&method==='POST'){
            check(options.body instanceof FormData,'creation must upload the selected image');
            check(options.body.get('source_image') instanceof File,'source image missing');
            check(['1','2'].includes(options.body.get('journey_version')),'journey version missing from creation');
            check(options.body.get('auto_mask')==='false','disabled mask default must reach the API');
            check(options.body.get('mask_model_id')==='qwen-mask','independent mask selection must reach the API');
            project={id:'journey-fixture',journey_preset:options.body.get('journey_preset')||'miniature',journey_direction:options.body.get('journey_direction'),journey_version:options.body.get('journey_version'),version:1,name:'Cave aménagée',source_asset_id:'source',status:'running',
              phase:'planning',intention:options.body.get('intention'),count:Number(options.body.get('count')),
              progression_model_id:options.body.get('progression_model_id'),prompt_model_id:options.body.get('prompt_model_id'),
              auto_mask:options.body.get('auto_mask')==='true',mask_model_id:options.body.get('mask_model_id'),source_dimensions:[1344,2368],
              render_profile:{dimensions:[1344,2368],settings:{steps:18}},generated:0,milestones:[],destination:'',completed_milestones:0,steps:[],warning:null,error:null,
              transferable_images:1,transitions_available:true};
            return {project:publicProject()};
          }
          if(url.endsWith('/pause')){project.status='paused';project.version++;return {project:publicProject()};}
          if(url.endsWith('/resume')){
            const body=JSON.parse(options.body);
            check(!('journey_version' in body),'resume must keep the saved journey version');
            check(!('journey_direction' in body),'resume must keep the saved direction');
            check(!('journey_preset' in body),'resume must keep the saved preset');
            if(resumeConflict){resumeConflict=false;project.version++;throw Error('Version modifiée');}
            check(body.version===project.version,'resume must use the refreshed revision');
            project.intention=body.intention;project.mask_model_id=body.mask_model_id;project.status='running';project.version++;
            return {project:publicProject()};
          }
          if(url.endsWith('/image-operations')&&method==='POST'){
            const body=JSON.parse(options.body);
            check(body.version===project.version,'manual operation must use the refreshed revision');
            const op={...body,id:'operation-'+((project.image_operations||[]).length+1),status:'running',phase:'rendering',
              action:{title:body.kind==='hq'?'Essai HQ':'Étape demandée',change:body.intention},error:null,output_asset_id:null};
            (project.image_operations||=[]).push(op);project.version++;return {project:publicProject()};
          }
          if(url.endsWith('/transitions')){
            transferred=JSON.parse(options.body).frame_ids;
            check(transferred.length>=2,'selection must contain at least two images');
            return {project_id:'transitions-fixture'};
          }
          if(url.endsWith('/projects/journey-fixture')&&method==='GET'){
            const result={project:publicProject()};
            if(holdGet)await new Promise(resolve=>{releaseGet=resolve;});
            return result;
          }
          throw Error('Unexpected API request '+method+' '+url);
        }};
        """
        scenario = r"""
        (async()=>{try{
          const el=id=>document.getElementById('ij-'+id);
          const wait=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw Error('Timed out');};
          await wait(()=>!el('start').disabled&&el('progression-model').value==='vision');
          check(el('setup').open,'new journey settings should be open');
          check(!el('models').open,'models should be collapsed');
          check(el('mask-model').value==='qwen-mask','Qwen should be the default mask model');
          check(!el('auto-mask').checked,'mask should be disabled by default');
          check(el('journey-version').value==='2'&&!el('journey-version').disabled,'new journey should default to selectable V2');
          check(el('journey-direction').value==='reverse','new journey should default to reverse');
          check(el('count').value==='3','new journey should default to three new images');
          const reverseDefault=el('intention').value;
          check(reverseDefault.includes('terrain plat'),'initial intention should match reverse mode');
          el('journey-direction').value='forward';el('journey-direction').dispatchEvent(new Event('change'));
          check(el('intention').value===el('intention').defaultValue,'construction should retain its default intention');
          el('intention').value='Mon chantier personnalisé';
          el('journey-direction').value='reverse';el('journey-direction').dispatchEvent(new Event('change'));
          check(el('intention').value.includes('terrain plat')&&el('source-label').textContent==='Image finale fournie','reverse labels and default missing');
          el('intention').value='';
          el('journey-direction').value='forward';el('journey-direction').dispatchEvent(new Event('change'));
          check(el('intention').value==='Mon chantier personnalisé','mode switch erased the forward draft');
          el('journey-direction').value='reverse';el('journey-direction').dispatchEvent(new Event('change'));
          check(el('intention').value==='','mode switch must preserve an intentionally empty draft');
          el('journey-direction').value='forward';el('journey-direction').dispatchEvent(new Event('change'));
          el('journey-version').value='1';el('journey-version').dispatchEvent(new Event('change'));
          check(!el('plan').open,'milestones should be collapsed');
          const dt=new DataTransfer();dt.items.add(new File(['fixture'],'start.png',{type:'image/png'}));
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('intention').value='Aménager la cave';el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          el('count').value='1';el('prompt-model').value='writer';
          el('start').click();await wait(()=>project&&!el('pause').disabled);
          check(!el('setup').open,'settings should fold after generation starts');
          check(project.journey_version==='1'&&el('journey-version').disabled,'selected V1 should be persisted and locked');
          check(el('transitions').disabled,'source alone cannot create a transition');
          el('setup').open=true;project.version++;await window.pollJourney();
          check(el('setup').open,'polling must preserve an explicitly opened panel');
          el('setup').open=false;project.version++;await window.pollJourney();
          check(!el('setup').open,'polling must preserve a folded panel');
          check(project.prompt_model_id==='writer','independent prompt model selection lost');
          check(project.mask_model_id==='qwen-mask'&&el('mask-model').disabled,'running mask selection should be persisted and locked');
          check(el('intention').readOnly,'running intention should be read-only');
          check(calls.filter(row=>row[0].endsWith('/projects')&&row[1]==='POST').length===1,'duplicate create request');
          el('pause').click();await wait(()=>!el('resume').hidden&&!el('resume').disabled);
          el('setup').open=true;
          check(!el('mask-model').disabled,'mask selection should be editable while paused');
          check(el('journey-version').value==='1'&&el('journey-version').disabled,'pause must not allow changing version');
          el('mask-model').value='vision';el('mask-model').dispatchEvent(new Event('input',{bubbles:true}));
          const draft='Créer une bibliothèque <img src=x onerror=alert(1)>';
          el('intention').value=draft;el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          await window.pollJourney();check(el('intention').value===draft,'poll erased a paused draft');
          el('resume').click();await wait(()=>el('message').textContent.includes('Version modifiée')&&!el('resume').disabled);
          check(el('intention').value===draft,'conflict erased the local intention');
          check(el('mask-model').value==='vision','poll or conflict erased the local mask selection');
          el('resume').click();await wait(()=>project.status==='running'&&el('resume').hidden);
          check(project.intention===draft,'updated intention was not submitted');
          check(project.mask_model_id==='vision'&&project.prompt_model_id==='writer','mask change was not independent at resume');
          project.steps=[{id:'journey-step-fixture',index:1,source_asset_id:'source',output_asset_id:'output',action:{title:'Isolation terminée',change:'Isoler les murs.'},
            prompt:'Edit <Picture 1>. Keep the camera fixed.',prompt_model_id:'writer',
            raw_output_asset_id:'raw',protection:{mask_asset_id:'mask',coverage:0.2,status:'completed',model_id:'qwen-mask'},
            review:{assessment:'similar',observation:'Changement faible, conservé.',model_id:'vision'}}];
          Object.assign(project,{generated:1,status:'completed',phase:'completed',destination:draft,
            milestones:['Préparation','Isolation'],completed_milestones:2,transferable_images:2,version:project.version+1});
          await window.pollJourney();
          check(el('frieze').querySelectorAll('[data-ij-thumbnail]').length===2,'start plus one new image expected');
          check(el('destination').textContent===draft&&!el('destination').querySelector('img'),'destination must be escaped');
          el('frieze').querySelectorAll('[data-ij-thumbnail]')[1].click();
          check(el('detail').open,'thumbnail should open the full image');
          check(el('detail-review').textContent.includes('Changement faible'),'real review missing');
          check(el('prompt-text').textContent.includes('<Picture 1>'),'prompt tags must remain literal');
          check(el('detail-models').textContent.includes('Analyse du masque : qwen-mask'),'detail must show the executed mask model');
          check(!el('detail-protection').hidden&&el('mask-views').children.length===4,'mask comparison views missing');
          el('mask-views').children[2].click();
          check(el('detail-image').alt==='Rendu brut','raw view should use the raw image');
          el('mask-views').children[3].click();
          check(el('detail-image').alt==='Masque','mask view missing');
          el('mask-views').children[0].click();
          check(el('detail-image').alt==='Résultat protégé','protected view should remain the default result');
          el('close').click();
          check(!el('comparison')&&!el('fixed-trial'),'experimental controls must be removed');
          check(!el('frieze').querySelector('[data-ij-hq]'),'HQ launch controls must be removed');
          const checks=()=>[...el('frieze').querySelectorAll('[data-ij-select]')];
          const checked=()=>checks().filter(c=>c.checked).map(c=>c.dataset.ijSelect);
          const box=id=>checks().find(c=>c.dataset.ijSelect===id);
          check(checks().length===2&&checks().every(c=>c.checked),'all reviewed images should start checked');
          check(!checks()[0].closest('button'),'checkbox must be separate from the zoom button');
          box('source').click();
          check(!el('detail').open&&el('transitions').disabled,'unchecking the source must not zoom or allow a single-frame handoff');
          box('journey-step-fixture').click();
          check(checked().length===0&&el('transitions').disabled,'empty selection must disable handoff');
          box('journey-step-fixture').click();
          project.steps[0].review=null;project.version++;await window.pollJourney();
          check(box('journey-step-fixture').disabled&&!box('journey-step-fixture').checked,'unreviewed image must be unavailable');
          project.steps[0].review={assessment:'usable',observation:'Image relue.'};project.version++;await window.pollJourney();
          check(box('journey-step-fixture').checked&&!box('source').checked,'review completion must preserve exclusions');
          box('journey-step-fixture').click();
          const plus=()=>[...el('frieze').querySelectorAll('[data-ij-add]')];
          const manualState=()=>project.image_operations.at(-1);
          const finishManual=()=>{
            const op=manualState();Object.assign(op,{status:'completed',phase:'completed',output_asset_id:'output-'+op.id,
              review:{assessment:'usable',observation:'État demandé obtenu.'}});
            const order=project.ordered_steps||clone(project.steps);
            const index=op.after_frame_id==='source'?0:order.findIndex(s=>s.id===op.after_frame_id)+1;
            order.splice(index,0,{id:op.id,index:index+1,source_asset_id:'source',output_asset_id:op.output_asset_id,
              action:op.action,review:op.review,prompt:'Edit <Picture 1>.',prompt_model_id:'writer',manual:true});
            project.ordered_steps=order;project.manual_generated=(project.manual_generated||0)+1;project.version++;
          };
          check(plus().length===2,'one discreet + after every frame expected');
          plus()[0].click();
          check(el('operation').open&&el('operation-images').querySelectorAll('img').length===2,'insertion must show both bounding images');
          el('operation-input').value='Le deck seul avant la porte <img src=x>';
          el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          project.version++;await window.pollJourney();
          check(el('operation-input').value.includes('deck seul'),'poll erased the insertion intention');
          el('operation-generate').click();await wait(()=>project.image_operations?.length===1&&!el('operation-close').disabled);
          check(manualState().kind==='insert'&&manualState().after_frame_id==='source'&&manualState().before_frame_id==='journey-step-fixture','insertion anchors lost');
          check(plus().every(b=>b.disabled),'another edit must wait for the current operation');
          finishManual();await window.pollJourney();
          check(el('frieze').querySelectorAll('[data-ij-thumbnail]').length===3,'inserted image missing from wrapped gallery');
          check(project.steps.length===1&&project.count===1,'insertion changed the original generation budget');
          check(box(manualState().id).checked&&!box('journey-step-fixture').checked&&!box('source').checked,'insertion must preserve choices by identity');
          el('operation-close').click();plus().at(-1).click();
          check(el('operation-images').querySelectorAll('img').length===1,'append must show only the actual last image');
          el('operation-input').value='Ajouter un petit escalier';el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          el('operation-generate').click();await wait(()=>project.image_operations.length===2&&!el('operation-close').disabled);
          check(manualState().kind==='append'&&manualState().before_frame_id===null,'append should have no following image');
          finishManual();await window.pollJourney();el('operation-close').click();
          el('frieze').querySelectorAll('[data-ij-thumbnail]')[1].click();
          el('detail-zoom').click();check(el('detail-zoom').getAttribute('aria-pressed')==='true','pixel zoom unavailable');
          el('close').click();
          delete project.ordered_steps;project.image_operations=[];project.manual_generated=0;
          // Many steps must wrap in the available width, never in a horizontal scroller.
          project.steps=Array.from({length:18},(_,i)=>({...clone(project.steps[0]),id:'step-'+i,index:i+1}));
          project.generated=18;project.count=18;project.version++;
          await window.pollJourney();
          const cards=[...el('frieze').querySelectorAll('[data-ij-thumbnail]')];
          check(cards.length===19,'all steps must remain visible');
          check(cards.at(-1).getBoundingClientRect().top>cards[0].getBoundingClientRect().top,'steps did not wrap');
          check(el('frieze').scrollWidth<=el('frieze').clientWidth+2,'gallery requires horizontal scrolling');
          check(document.getElementById('image-journey-workspace').getBoundingClientRect().width>=document.documentElement.clientWidth-4,'workspace is still width-limited');
          // Choose three nonconsecutive states and exclude the source.
          const wanted=['step-0','step-2','step-4'];
          for(const input of checks())if(input.checked!==wanted.includes(input.dataset.ijSelect))input.click();
          check(JSON.stringify(checked())===JSON.stringify(wanted),'selected states are incorrect');
          check(el('selection-count').textContent.includes('3 images')&&el('selection-count').textContent.includes('2 transitions'),'selection count is incorrect');
          project.steps[0].action={...project.steps[0].action,title:'Titre actualisé'};project.version++;await window.pollJourney();
          check(JSON.stringify(checked())===JSON.stringify(wanted),'gallery rebuild erased selection');
          el('new').click();
          el('projects').value='journey-fixture';el('projects').dispatchEvent(new Event('change'));
          await wait(()=>!el('result').hidden&&!el('transitions').disabled);
          check(JSON.stringify(checked())===JSON.stringify(wanted),'reopening the same project lost its selection');
          delete project.journey_version;delete project.journey_direction;project.version++;await window.pollJourney();
          check(el('journey-version').value==='1'&&el('journey-version').disabled,'legacy project must display locked V1');
          el('transitions').click();await wait(()=>opened==='transitions-fixture');
          check(JSON.stringify(transferred)===JSON.stringify(wanted),'handoff must send selected IDs in gallery order');
          check(JSON.parse(calls.filter(row=>row[0].endsWith('/transitions')).at(-1)[2]).frame_order==='generation','forward handoff must explicitly send gallery order');
          check(!calls.some(row=>/\/messages|\/attempts|\/send/.test(row[0])),'browser must not orchestrate renders or send videos');
          check(document.documentElement.scrollWidth<=window.innerWidth+2,'workshop overflows horizontally');
          await wait(()=>!el('new').disabled);
          holdGet=true;const pending=window.pollJourney();await wait(()=>releaseGet);
          el('new').click();releaseGet();await pending;holdGet=false;
          check(el('result').hidden&&!el('source').disabled&&el('setup').open,'stale poll replaced the new-project form');
          check(el('mask-model').value==='qwen-mask','new journey should restore the Qwen default');
          check(el('journey-version').value==='2'&&!el('journey-version').disabled,'new journey must restore V2 after a legacy project');
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('start').click();await wait(()=>project.journey_version==='2'&&!el('pause').disabled);
          check(el('journey-version').disabled,'default V2 creation should lock its version');
          check(project.journey_direction==='reverse'&&project.count===3,'new creation should send reverse and three images');
          el('new').click();
          check(el('intention').value===reverseDefault,'New must restore the reverse default');
          el('journey-direction').value='reverse';el('journey-direction').dispatchEvent(new Event('change'));
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('start').click();await wait(()=>project.journey_direction==='reverse'&&!el('pause').disabled);
          check(el('journey-direction').disabled&&el('journey-version').value==='2','direction must lock independently of V2');
          check(el('frieze').textContent.includes('Bâtiment terminé'),'reverse supplied image should be labelled');
          el('pause').click();await wait(()=>!el('resume').hidden&&!el('resume').disabled);
          check(el('journey-direction').disabled,'paused journey must keep direction locked');
          el('new').click();
          el('projects').value='journey-fixture';el('projects').dispatchEvent(new Event('change'));
          await wait(()=>!el('result').hidden&&!el('new').disabled);
          check(el('journey-direction').value==='reverse'&&el('intention').value===project.intention,'reopening must restore saved direction and intention');
          // Reverse generation opens as construction, including a subset export and manual + anchors.
          project.steps=['roof','walls','ground'].map((id,index)=>({id,index:index+1,source_asset_id:'source',
            output_asset_id:'asset-'+id,action:{title:id,change:'Remove '+id},prompt:'Edit <Picture 1>.',
            prompt_model_id:'writer',review:{assessment:'usable',observation:'Reviewed '+id}}));
          Object.assign(project,{generated:3,count:3,status:'completed',phase:'completed',image_operations:[]});
          project.version++;await window.pollJourney();
          const identities=()=>checks().map(c=>c.dataset.ijSelect);
          const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
          check(same(identities(),['ground','walls','roof','source']),'reverse must open with the supplied finished building at the right');
          check(el('order-label').textContent==='Construction → bâtiment terminé','construction order should be explicit');
          for(const input of checks())if(!input.checked)input.click();
          box('walls').click();
          check(same(checked(),['ground','roof','source']),'reverse subset order lost');
          const exportCount=()=>calls.filter(row=>row[0].endsWith('/transitions')).length;
          let exported=exportCount();
          el('transitions').click();await wait(()=>exportCount()>exported&&!el('new').disabled);
          check(same(transferred,['ground','roof','source']),'reverse handoff must follow the visible selected states');
          check(JSON.parse(calls.filter(row=>row[0].endsWith('/transitions')).at(-1)[2]).frame_order==='reverse_generation','API would silently restore generation order');
          el('reverse-order').click();
          check(same(identities(),['source','roof','walls','ground'])&&same(checked(),['source','roof','ground']),'one click must reverse without losing exclusions');
          check(el('order-label').textContent==='Bâtiment terminé → début du chantier','reversed label missing');
          project.version++;await window.pollJourney();
          check(same(identities(),['source','roof','walls','ground']),'poll reset the chosen order');
          el('new').click();el('projects').value='journey-fixture';el('projects').dispatchEvent(new Event('change'));
          await wait(()=>!el('result').hidden&&!el('new').disabled);
          check(same(identities(),['source','roof','walls','ground'])&&!box('walls').checked,'reopening lost order or selection');
          exported=exportCount();el('transitions').click();await wait(()=>exportCount()>exported&&!el('new').disabled);
          check(same(transferred,['source','roof','ground']),'second handoff must follow the new order');
          el('reverse-order').click();
          // The + at the left extends the generation tail. Inner + retain canonical anchor IDs.
          const firstCard=plus()[0].closest('.ij-card');
          check(plus()[0].getBoundingClientRect().right<=firstCard.querySelector('[data-ij-thumbnail]').getBoundingClientRect().left,'reverse tail + should sit before the first image');
          plus()[0].click();
          check(el('operation-images').querySelectorAll('img').length===1&&el('operation-hint').textContent.includes('avant cet état'),'reverse tail addition is ambiguous');
          el('operation-close').click();plus()[1].click();
          el('operation-images').querySelector('button').click();
          check(el('detail-action').textContent==='Remove ground','insertion popup must show neighbors in gallery order');
          el('close').click();
          el('operation-input').value='Un état entre le terrain et les murs';el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          el('operation-generate').click();await wait(()=>project.image_operations.length===1&&!el('operation-close').disabled);
          check(manualState().kind==='insert'&&manualState().after_frame_id==='walls'&&manualState().before_frame_id==='ground','reversal changed canonical insertion anchors');
          finishManual();await window.pollJourney();el('operation-close').click();
          check(same(identities(),['ground',manualState().id,'walls','roof','source']),'inserted frame is in the wrong visible gap');
          check(!box('walls').checked&&box(manualState().id).checked,'insert after reversal lost selection');
          check(el('frieze').scrollWidth<=el('frieze').clientWidth+2,'reverse gallery requires horizontal scrolling');
          // A reverse endpoint may be reached before the planned image budget; never claim all renders happened.
          project.steps=project.steps.slice(0,2);delete project.ordered_steps;
          Object.assign(project,{generated:2,count:3,manual_generated:0,image_operations:[],status:'completed',phase:'completed',
            completion_reason:'reverse_endpoint',warning:'Terrain dégagé atteint après 2 images sur 3 demandées.'});
          project.version++;await window.pollJourney();
          check(el('status').textContent.includes('2 nouvelles images sur 3 demandées')&&el('status').textContent.includes('Terrain dégagé'),'early completion hides the actual image count');
          check(el('progress').value===2&&el('progress').max===3,'early completion must not inflate the render counter');
          check(el('warning').textContent.includes('2 images sur 3')&&el('resume').hidden,'early completion should explain the stop without suggesting a no-op resume');
          // Independent preset drafts, locked direction, absent population controls, saved/reopened choice.
          el('new').click();
          const selectPreset=value=>{el('journey-preset').value=value;el('journey-preset').dispatchEvent(new Event('change'));};
          el('intention').value='Miniature personnalisée';
          el('journey-version').value='1';
          selectPreset('realistic');
          check(el('intention').value===''&&el('intention-label').textContent==='État de départ souhaité','realistic initial state should start blank and optional');
          check(el('journey-direction').value==='reverse'&&el('journey-direction').disabled,'realism must stay reverse');
          check(el('journey-version').hidden&&getComputedStyle(el('journey-version')).display==='none','life selector should not appear for realism');
          check(el('count').value==='3','realism changed the requested default budget');
          el('intention').value='Arbre intact, feuilles au sol.';
          selectPreset('miniature');
          check(el('intention').value==='Miniature personnalisée'&&!el('journey-version').hidden&&el('journey-version').value==='1','switching preset lost miniature draft or life version');
          selectPreset('realistic');
          check(el('intention').value==='Arbre intact, feuilles au sol.','switching erased desired initial state');
          el('intention').value='';selectPreset('miniature');selectPreset('realistic');
          check(el('intention').value==='','blank automatic initial state was overwritten');
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('count').value='5';el('start').click();
          await wait(()=>project.journey_preset==='realistic'&&!el('pause').disabled);
          check(project.intention===''&&project.count===5&&project.journey_direction==='reverse','realistic creation did not send exact preset, empty intention and budget');
          check(el('journey-preset').disabled,'saved preset should be locked');
          el('pause').click();await wait(()=>project.status==='paused'&&!el('resume').disabled);
          el('intention').value='Grotte vide, humide et austère.';el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          el('resume').click();await wait(()=>project.status==='running'&&!el('pause').disabled);
          check(project.intention==='Grotte vide, humide et austère.'&&project.journey_preset==='realistic','resume lost preset or new initial state');
          el('new').click();el('projects').value='journey-fixture';el('projects').dispatchEvent(new Event('change'));
          await wait(()=>!el('result').hidden&&!el('new').disabled);
          check(el('journey-preset').value==='realistic'&&el('journey-version').hidden&&el('intention').value===project.intention,'reopening lost real preset');
          check(el('frieze').textContent.includes('Aménagement terminé'),'finished scene still labelled building');
          project.steps=[{id:'raw',index:1,source_asset_id:'source',output_asset_id:'raw-asset',action:{title:'Grotte brute',change:'Déposer les parois'},review:{assessment:'usable',observation:'Grotte intacte'}}];
          Object.assign(project,{generated:1,status:'completed',phase:'completed',completion_reason:'reverse_endpoint'});
          project.version++;await window.pollJourney();
          check(el('status').textContent.includes('État de départ atteint')&&!el('status').textContent.includes('Terrain dégagé'),'realistic endpoint uses wrong target');
          check(el('order-label').textContent==='État initial → aménagement terminé','realistic construction order label missing');
          exported=exportCount();el('transitions').click();await wait(()=>exportCount()>exported&&!el('new').disabled);
          check(same(transferred,['raw','source']),'realistic transfer reversed the selected chronology');
          delete project.journey_preset;project.version++;await window.pollJourney();
          check(el('journey-preset').value==='miniature'&&!el('journey-version').hidden,'legacy project must retain the historical preset');
          delete journeySpec.journey_presets;el('new').click();
          check(el('journey-preset').querySelector('[value="realistic"]').disabled,'old backend must not silently generate miniature for realism');
          selectPreset('realistic');
          check(el('journey-preset').value==='miniature'&&el('message').textContent.includes('redémarrage'),'old backend needs a clear availability message');
          document.body.innerHTML='<pre id="result">IMAGE_JOURNEY_BROWSER_OK</pre>';
        }catch(error){document.body.innerHTML='<pre id="result"></pre>';document.getElementById('result').textContent=error.stack;}})();
        """
        document = ('<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>'
                    + page + '<script>' + fixture + '</script><script>' + actions + '</script><script>' + code + '</script><script>'
                    + scenario + '</script></body></html>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image-journey.html"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run([str(browsers[0]), "--headless", "--disable-gpu", "--no-sandbox",
                "--user-data-dir=" + str(Path(directory) / "browser-profile"), "--disable-background-networking",
                "--allow-file-access-from-files", "--window-size=1920,1100", "--virtual-time-budget=15000", "--dump-dom",
                path.as_uri()], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('<pre id="result">IMAGE_JOURNEY_BROWSER_OK</pre>', result.stdout)
