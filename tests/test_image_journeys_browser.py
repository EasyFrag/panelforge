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
            'const asset = id => window.fixtureImage + "#" + encodeURIComponent(id);')
        css = (STATIC / "lab.css").read_text(encoding="utf-8") + (STATIC / "image-journeys.css").read_text(encoding="utf-8")
        actions = (STATIC / 'image-journey-actions.js').read_text(encoding='utf-8')
        fixture = r"""
        const check=(value,message)=>{if(!value)throw Error(message);};
        window.fixtureImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
        sessionStorage.removeItem('panelforge.image-journey.project');
        sessionStorage.removeItem('panelforge.image-journey.project.excluded.journey-fixture');
        sessionStorage.removeItem('panelforge.image-journey.project.order.journey-fixture');
        window.setInterval=callback=>{window.pollJourney=callback;return 1;};
        const journeySpec={prepend_images:true,image_resolutions:true,journey_presets:{miniature:'Miniature',realistic:'Aménagement réaliste'}};
        const calls=[];let project=null,resumeConflict=true,opened=null,holdGet=false,releaseGet=null,transferred=null;
        window.PanelForgeImageTransitions={open:async identity=>{opened=identity;}};
        const clone=value=>structuredClone(value);
        const publicProject=()=>{
          const steps=project.ordered_steps||project.steps;
          const accepted=s=>s.output_asset_id&&(['usable','similar'].includes(s.review?.assessment)||s.user_acceptance?.output_asset_id===s.output_asset_id);
          const ordered=project.ordered_frame_ids||['source',...steps.map(s=>s.id)];
          const available=new Set(['source',...steps.filter(accepted).map(s=>s.id)]);
          const candidates=project.status==='paused'&&project.phase==='reviewing'?[project.steps.at(-1)]:[];
          candidates.push(...(project.image_operations||[]).filter(op=>op.status==='paused'&&op.phase==='reviewing'));
          return {...clone(project),ordered_frame_ids:ordered,transferable_frame_ids:ordered.filter(id=>available.has(id)),
            blocked_images:candidates.filter(s=>s?.output_asset_id&&!accepted(s)&&s.review?.assessment==='unusable').map(s=>({
              step_id:s.id,output_asset_id:s.output_asset_id,reason:s.review.observation,available:true,manual:!!s.kind,
              accept_previous_asset_ids:(s.attempt_history||[]).filter(a=>a.output_asset_id&&a.review).map(a=>a.output_asset_id),
              accept_label:s.kind?'Accepter l’image':project.generated>=project.count?'Accepter et terminer':'Accepter et continuer'}))};
        };
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
          if(url.endsWith('/image-resolutions')&&method==='POST'){
            const body=JSON.parse(options.body);
            check(body.version===project.version,'resolution revision is stale');
            const manual=(project.image_operations||[]).find(op=>op.id===body.step_id);
            const step=manual||project.steps.find(s=>s.id===body.step_id);
            const previous=step?.attempt_history?.findIndex(a=>a.output_asset_id===body.output_asset_id)??-1;
            check(step&&(step.output_asset_id===body.output_asset_id||body.action==='accept'&&previous>=0),'resolution must identify exact pixels');
            if(body.action==='accept'){
              if(step.output_asset_id!==body.output_asset_id){
                const current=clone(step);delete current.attempt_history;
                const attempts=[...clone(step.attempt_history),current],logicalId=step.id;
                Object.assign(step,clone(attempts[previous]),{id:logicalId,attempt_history:attempts,retained_attempt_index:previous});
              }
              step.user_acceptance={output_asset_id:body.output_asset_id};
              if(!manual)project.current_asset_id=body.output_asset_id;
              if(manual){manual.status='completed';manual.phase='completed';}
              else{project.status=project.generated>=project.count?'completed':'running';project.phase=project.status==='completed'?'completed':'planning';}
            }else{
              const old=step.id;step.id='replacement-'+old;step.output_asset_id=null;step.review=null;
              step.regenerated_from_step_id=old;project.status='running';project.phase='prompting';project.generated--;
              if(project.ordered_frame_ids)project.ordered_frame_ids=project.ordered_frame_ids.map(id=>id===old?step.id:id);
            }
            project.error=null;project.version++;return {project:publicProject()};
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
          const galleryIds=()=>[...el('frieze').children].map(card=>card.dataset.ijFrame);
          const pendingTile=id=>[...el('frieze').querySelectorAll('[data-ij-pending]')].find(node=>node.dataset.ijPending===id);
          const scheduler=machine=>window.dispatchEvent(new CustomEvent('panelforge:work-scheduler-status',
            {detail:machine?{machines:{remote_gpu:machine}}:null}));
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
          // A pending frame occupies its true slot; queue rank belongs to the shared GPU queue.
          project.steps=[{id:'pending-auto',output_asset_id:null,attempt_id:'render-auto',
            action:{title:'Étape en attente',change:'Isoler les murs.'}}];
          project.phase='prompting';project.version++;await window.pollJourney();
          check(pendingTile('pending-auto')?.textContent.includes('Préparation du prompt'),'preparing step has no placeholder');
          check(!pendingTile('pending-auto').querySelector('img')&&!pendingTile('pending-auto').closest('.ij-card').querySelector('[data-ij-select]'),'pending frame must have no asset request or export checkbox');
          check(getComputedStyle(pendingTile('pending-auto').querySelector('.ij-pending-visual')).backgroundColor==='rgb(0, 0, 0)','placeholder must be black');
          project.phase='rendering';project.version++;await window.pollJourney();
          scheduler({queue:[{id:'other-project',position:1},{id:'render-auto',position:2}],owner_id:'video-active'});
          check(pendingTile('pending-auto').textContent.includes('En file · n° 2'),'rank must include jobs from other projects');
          const pendingVersion=project.version;
          scheduler({queue:[{id:'render-auto',position:1}]});
          check(project.version===pendingVersion&&pendingTile('pending-auto').textContent.includes('En file · n° 1'),'queue rank must refresh without a journey revision');
          el('reverse-order').click();
          check(galleryIds()[0]==='pending-auto','pending automatic step must follow reversal');
          scheduler({queue:[],owner_id:'render-auto',state:'cooling'});
          check(pendingTile('pending-auto').textContent.includes('Refroidissement'),'cooling is not active rendering');
          scheduler({queue:[],owner_id:'render-auto',state:'busy'});
          check(pendingTile('pending-auto').textContent.includes('Génération en cours')&&!pendingTile('pending-auto').textContent.includes('n°'),'active render must leave the waiting queue');
          scheduler(null);
          check(!pendingTile('pending-auto').textContent.includes('n°'),'unavailable scheduler must clear the old rank');
          project.status='paused';project.version++;await window.pollJourney();
          check(pendingTile('pending-auto').textContent.includes('Suspendu'),'paused placeholder must explain its state');
          el('reverse-order').click();
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
          const plus=()=>[...el('frieze').querySelectorAll('[data-ij-add]:not([data-ij-boundary])')];
          const manualState=()=>project.image_operations.at(-1);
          const finishManual=()=>{
            const op=manualState();Object.assign(op,{status:'completed',phase:'completed',output_asset_id:'output-'+op.id,
              review:{assessment:'usable',observation:'État demandé obtenu.'}});
            const existing=project.ordered_steps||clone(project.steps);
            const ids=project.ordered_frame_ids||['source',...existing.map(s=>s.id)];
            const index=op.after_frame_id===null?0:ids.indexOf(op.after_frame_id)+1;
            ids.splice(index,0,op.id);
            const lookup=new Map(existing.map(s=>[s.id,s]));
            lookup.set(op.id,{id:op.id,index:index+1,source_asset_id:'source',output_asset_id:op.output_asset_id,
              action:op.action,review:op.review,prompt:'Edit <Picture 1>.',prompt_model_id:'writer',manual:true});
            project.ordered_frame_ids=ids;project.ordered_steps=ids.filter(id=>id!=='source').map(id=>lookup.get(id));
            project.manual_generated=(project.manual_generated||0)+1;project.version++;
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
          check(JSON.stringify(galleryIds())===JSON.stringify(['source',manualState().id,'journey-step-fixture']),'queued insertion must occupy the intended gap');
          check(!box(manualState().id)&&checks().length===2,'queued insertion must not enter transition selection');
          manualState().attempt_id='render-manual';project.version++;await window.pollJourney();
          scheduler({queue:[{id:'render-manual',position:3}]});
          check(pendingTile(manualState().id).textContent.includes('n° 3'),'manual queue position missing');
          el('operation-close').click();pendingTile(manualState().id).click();
          check(el('operation').open&&el('operation-images').querySelectorAll('img').length===2,'pending insertion must reopen the existing operation with its real neighbors');
          finishManual();await window.pollJourney();
          check(el('frieze').querySelectorAll('[data-ij-thumbnail]').length===3,'inserted image missing from wrapped gallery');
          check(!pendingTile(manualState().id)&&galleryIds().filter(id=>id===manualState().id).length===1,'completed addition must replace its placeholder exactly once');
          check(project.steps.length===1&&project.count===1,'insertion changed the original generation budget');
          check(box(manualState().id).checked&&!box('journey-step-fixture').checked&&!box('source').checked,'insertion must preserve choices by identity');
          el('operation-close').click();plus().at(-1).click();
          check(el('operation-images').querySelectorAll('img').length===1,'append must show only the actual last image');
          el('operation-input').value='Ajouter un petit escalier';el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          el('operation-generate').click();await wait(()=>project.image_operations.length===2&&!el('operation-close').disabled);
          check(manualState().kind==='append'&&manualState().before_frame_id===null,'append should have no following image');
          check(galleryIds().at(-1)===manualState().id&&pendingTile(manualState().id),'queued tail must appear after the last image');
          finishManual();await window.pollJourney();el('operation-close').click();
          el('frieze').querySelectorAll('[data-ij-thumbnail]')[1].click();
          el('detail-zoom').click();check(el('detail-zoom').getAttribute('aria-pressed')==='true','pixel zoom unavailable');
          el('close').click();
          delete project.ordered_steps;delete project.ordered_frame_ids;project.image_operations=[];project.manual_generated=0;
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
          check(same(galleryIds(),['ground',manualState().id,'walls','roof','source']),'reversed pending insertion is in the wrong gap');
          check(!box(manualState().id),'pending reverse insertion must not be selectable');
          finishManual();await window.pollJourney();el('operation-close').click();
          check(same(identities(),['ground',manualState().id,'walls','roof','source']),'inserted frame is in the wrong visible gap');
          check(!box('walls').checked&&box(manualState().id).checked,'insert after reversal lost selection');
          check(el('frieze').scrollWidth<=el('frieze').clientWidth+2,'reverse gallery requires horizontal scrolling');
          // A reverse endpoint may be reached before the planned image budget; never claim all renders happened.
          project.steps=project.steps.slice(0,2);delete project.ordered_steps;delete project.ordered_frame_ids;
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
          // One logical frame keeps both attempts; rejected pixels never enter the selection.
          const beforeAutoRetry=clone(project), retryFrame=project.steps[0];
          const initialAttempt={...clone(retryFrame),prompt:'Initial prompt',
            review:{assessment:'unusable',observation:'Des personnes occupent la grotte.'}};
          Object.assign(retryFrame,{attempt_history:[initialAttempt],automatic_retry_count:1,
            output_asset_id:null,review:null,prompt:'Correction prompt'});
          Object.assign(project,{generated:0,status:'running',phase:'rendering'});
          project.version++;await window.pollJourney();
          const attemptLink=()=>el('frieze').querySelector('[data-ij-attempts="raw"]');
          check(attemptLink()?.textContent==='2 essais'&&pendingTile('raw')&&!box('raw'),'pending correction must retain access to the initial attempt without export');
          check(el('frieze').textContent.includes('Correction en cours'),'pending correction status missing');
          attemptLink().click();
          const trial=i=>el('detail-attempts').querySelector('[data-ij-trial="'+i+'"]');
          check(trial(0).textContent==='Initial'&&trial(1).textContent==='Correction'&&trial(1).disabled,'attempt controls should distinguish the unavailable correction');
          check(el('detail-image').src.endsWith('#raw-asset')&&el('prompt-text').textContent==='Initial prompt','pending view must show original pixels and prompt');
          check(el('detail-review').textContent.includes('Des personnes'),'initial diagnostic missing');
          trial(0).click();
          Object.assign(retryFrame,{output_asset_id:'corrected-asset',review:{assessment:'unusable',observation:'Encore des personnes.'}});
          Object.assign(project,{generated:1,status:'paused',phase:'reviewing'});
          project.version++;await window.pollJourney();
          check(el('detail-image').src.endsWith('#raw-asset'),'polling must keep the chosen initial view');
          check(el('detail-resolution').querySelector('[data-ij-resolve="accept"]')&&!el('detail-resolution').querySelector('[data-ij-resolve="regenerate"]'),'archived initial should offer acceptance only');
          trial(1).click();
          check(el('detail-image').src.endsWith('#corrected-asset')&&el('prompt-text').textContent==='Correction prompt','correction tab must change both image and prompt');
          check(el('detail-review').textContent.includes('Encore des personnes.')&&el('detail-attempt-status').textContent==='Essai rejeté','correction verdict missing');
          check(el('detail-resolution').querySelector('[data-ij-resolve="accept"]'),'only latest rejected image should offer acceptance');
          retryFrame.review={assessment:'usable',observation:'Grotte vide et fidèle.'};
          Object.assign(project,{status:'completed',phase:'completed'});project.version++;await window.pollJourney();
          check(el('detail-attempt-status').textContent==='Essai retenu'&&el('detail-review').textContent.includes('Grotte vide'),'accepted correction status not refreshed');
          check(box('raw').checked&&checks().length===2,'correction must reuse one selected logical frame');
          el('close').click();
          exported=exportCount();el('transitions').click();await wait(()=>exportCount()>exported&&!el('new').disabled);
          check(same(transferred,['raw','source']),'handoff must reference logical frames, not historical attempts');
          // A rejected correction can be replaced by the saved first attempt without another render.
          retryFrame.review={assessment:'unusable',observation:'Correction toujours inadéquate.'};
          Object.assign(project,{status:'paused',phase:'reviewing',count:2});project.version++;await window.pollJourney();
          attemptLink().click();trial(0).click();
          const chooseInitial=el('detail-resolution').querySelector('[data-ij-resolve="accept"]');
          check(chooseInitial.textContent==='Accepter cet essai et continuer','initial acceptance should explain continuation');
          const priorRequests=calls.filter(row=>row[0].endsWith('/image-resolutions')).length;
          chooseInitial.click();chooseInitial.click();
          await wait(()=>calls.filter(row=>row[0].endsWith('/image-resolutions')).length===priorRequests+1&&!el('new').disabled);
          const initialBody=JSON.parse(calls.filter(row=>row[0].endsWith('/image-resolutions')).at(-1)[2]);
          check(initialBody.output_asset_id==='raw-asset'&&initialBody.step_id==='raw','acceptance sent correction pixels instead of first attempt');
          check(project.current_asset_id==='raw-asset'&&project.steps[0].output_asset_id==='raw-asset','continuation must use the chosen image');
          check(attemptLink().textContent==='2 essais'&&box('raw').checked,'selection should keep one frame and exactly two attempts');
          attemptLink().click();
          check(trial(0).getAttribute('aria-pressed')==='true'&&el('detail-attempt-status').textContent==='Essai retenu','Initial must remain Initial and be marked retained');
          trial(1).click();
          check(el('detail-image').src.endsWith('#corrected-asset')&&el('detail-attempt-status').textContent==='Essai non retenu','correction must remain consultable at its original position');
          el('close').click();project.version++;await window.pollJourney();
          attemptLink().click();
          check(el('detail-image').src.endsWith('#raw-asset')&&el('detail-review').textContent.includes('Acceptée manuellement'),'reopening must default to accepted first attempt');
          el('close').click();
          // An automatic comparison can retain partial progress; expose evidence and choice without a human override.
          delete retryFrame.user_acceptance;
          retryFrame.review={assessment:'usable',observation:'Textile retiré au fond.',
            quality:{people_present:false,requested_change_complete:false,scene_preserved:true},
            progress:{level:'partial',visible_changes:'Paroi gauche dégagée.',remaining_work:'Textile au premier plan.',
              blocking_defects:[],destination_reached:false}};
          retryFrame.attempt_comparison={selected:'initial',reason:'Le premier essai conserve davantage de progrès.'};
          project.version++;await window.pollJourney();
          check(el('frieze').textContent.includes('Progrès partiel conservé')&&box('raw').checked,'useful partial image must remain selected');
          attemptLink().click();
          check(el('detail-attempt-status').textContent==='Essai retenu','automatic choice must indicate the retained attempt');
          check(el('detail-review').textContent.includes('Paroi gauche dégagée.')
            &&el('detail-review').textContent.includes('Textile au premier plan.')
            &&el('detail-review').textContent.includes('Le premier essai conserve davantage de progrès.'),'progress evidence and comparison reason missing');
          el('close').click();
          project={...beforeAutoRetry,version:project.version+1};await window.pollJourney();
          // Explicit rejected-image actions target pixels, avoid double submissions, and preserve the diagnostic.
          const rejected=project.steps[0];
          rejected.review={assessment:'unusable',observation:'Des ouvriers sont apparus.'};
          Object.assign(project,{status:'paused',phase:'reviewing',count:2,error:rejected.review.observation});
          project.version++;await window.pollJourney();
          const resolution=()=>el('frieze').querySelector('[data-ij-resolve="regenerate"]');
          check(resolution()&&!box(rejected.id).checked,'blocked image must offer decisions and stay unavailable');
          const resolutionCount=()=>calls.filter(row=>row[0].endsWith('/image-resolutions')).length;
          const oldId=rejected.id;const oldOutput=rejected.output_asset_id;const beforeDecisions=resolutionCount();
          const retry=resolution();retry.click();retry.click();
          await wait(()=>resolutionCount()===beforeDecisions+1&&!el('new').disabled);
          check(rejected.id!==oldId&&!box(oldId),'regeneration must remove the rejected frame from the active gallery');
          const payload=JSON.parse(calls.filter(row=>row[0].endsWith('/image-resolutions')).at(-1)[2]);
          check(payload.step_id===oldId&&payload.output_asset_id===oldOutput,'wrong rejected pixels submitted');
          Object.assign(rejected,{output_asset_id:'retried-image',review:{assessment:'unusable',observation:'Des ouvriers sont encore visibles.'}});
          Object.assign(project,{status:'paused',phase:'reviewing',generated:1,count:1});project.version++;await window.pollJourney();
          el('frieze').querySelector('[data-ij-thumbnail]').click();
          const accept=el('detail-resolution').querySelector('[data-ij-resolve="accept"]');
          check(accept.textContent==='Accepter et terminer','last image must explain that acceptance finishes the run');
          accept.click();await wait(()=>project.status==='completed'&&!el('new').disabled);
          check(box(rejected.id).checked&&el('frieze').textContent.includes('Acceptée manuellement'),'accepted image must become selectable');
          check(rejected.review.assessment==='unusable','manual acceptance must retain the original verdict');
          // Both visual endpoints, including beyond the supplied source; reversal keeps canonical anchors.
          const head=()=>el('frieze').querySelector('[data-ij-boundary="head"]');
          check(head()&&el('frieze').querySelectorAll('[data-ij-add]').length===checks().length+1,'a + is missing at an endpoint');
          check(head().getBoundingClientRect().left>=head().closest('.ij-card').querySelector('[data-ij-thumbnail]').getBoundingClientRect().right,'reverse head + must be right of supplied image');
          head().click();check(el('operation-images').querySelectorAll('img').length===1,'head popup needs exactly one neighbor');
          el('operation-input').value='Ajouter une terrasse devant la grotte';el('operation-input').dispatchEvent(new Event('input'));
          const opCount=(project.image_operations||[]).length;
          el('operation-generate').click();await wait(()=>project.image_operations.length===opCount+1&&!el('operation-close').disabled);
          check(manualState().kind==='prepend'&&manualState().after_frame_id===null&&manualState().before_frame_id==='source','source-side anchor is incorrect');
          check(galleryIds().at(-1)===manualState().id&&pendingTile(manualState().id),'reverse source-side placeholder must appear beyond the supplied image');
          el('reverse-order').click();
          check(galleryIds()[0]===manualState().id,'source-side placeholder did not follow reversal');
          el('reverse-order').click();
          const savedStatus=manualState().status;
          manualState().status='cancelled';project.version++;await window.pollJourney();
          check(!pendingTile(manualState().id)&&!galleryIds().includes(manualState().id),'cancelled addition left a phantom placeholder');
          manualState().status=savedStatus;project.version++;await window.pollJourney();
          finishManual();await window.pollJourney();el('operation-close').click();
          check(identities().at(-1)===manualState().id&&identities().at(-2)==='source','head addition moved the original reference');
          el('reverse-order').click();check(identities()[0]===manualState().id&&identities()[1]==='source','head did not follow reversal');
          check(head().getBoundingClientRect().right<=head().closest('.ij-card').querySelector('[data-ij-thumbnail]').getBoundingClientRect().left,'forward head + must be left of first image');
          head().click();el('operation-input').value='Une autre étape';el('operation-input').dispatchEvent(new Event('input'));
          el('operation-generate').click();await wait(()=>project.image_operations.length===opCount+2&&!el('operation-close').disabled);
          Object.assign(manualState(),{status:'paused',phase:'reviewing',output_asset_id:'manual-rejected',review:{assessment:'unusable',observation:'Personne visible.'}});
          project.version++;await window.pollJourney();
          check(el('operation-resume').hidden&&el('operation-resolution').querySelectorAll('button').length===2,'manual rejection needs explicit choices');
          el('operation-resolution').querySelector('[data-ij-resolve="accept"]').click();
          await wait(()=>manualState().status==='completed'&&!el('operation-close').disabled);
          check(el('operation-review').textContent.includes('Acceptée manuellement'),'manual override should be visible in the popup');
          el('operation-close').click();
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
