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
        window.setInterval=callback=>{window.pollJourney=callback;return 1;};
        const calls=[];let project=null,resumeConflict=true,opened=null,holdGet=false,releaseGet=null;
        window.PanelForgeImageTransitions={open:async identity=>{opened=identity;}};
        const clone=value=>structuredClone(value);
        window.PanelForgeLabCore={request:async(url,options={})=>{
          const method=options.method||'GET';calls.push([url,method,options.body]);
          if(url.endsWith('/spec'))return {default_images:5,max_images:30,default_model_id:'vision',transitions_available:true,hq_prompt:'Create a higher-resolution version of <Picture 1>. Preserve geometry and colors.'};
          if(url.endsWith('/models'))return {models:[{id:'vision',label:'Vision local',source:'local'},
            {id:'writer',label:'MiniMax writer',source:'server'}]};
          if(url.endsWith('/projects')&&method==='GET')return {projects:project?[clone(project)]:[]};
          if(url.endsWith('/projects')&&method==='POST'){
            check(options.body instanceof FormData,'creation must upload the selected image');
            check(options.body.get('source_image') instanceof File,'source image missing');
            check(options.body.get('auto_mask')==='true','mask default must reach the API');
            project={id:'journey-fixture',version:1,name:'Cave aménagée',source_asset_id:'source',status:'running',
              phase:'planning',intention:options.body.get('intention'),count:Number(options.body.get('count')),
              progression_model_id:options.body.get('progression_model_id'),prompt_model_id:options.body.get('prompt_model_id'),
              auto_mask:options.body.get('auto_mask')==='true',source_dimensions:[1344,2368],
              render_profile:{dimensions:[1344,2368],settings:{steps:18}},generated:0,milestones:[],destination:'',completed_milestones:0,steps:[],warning:null,error:null,
              transferable_images:1,transitions_available:true};
            return {project:clone(project)};
          }
          if(url.endsWith('/pause')){project.status='paused';project.version++;return {project:clone(project)};}
          if(url.endsWith('/resume')){
            const body=JSON.parse(options.body);
            if(resumeConflict){resumeConflict=false;project.version++;throw Error('Version modifiée');}
            check(body.version===project.version,'resume must use the refreshed revision');
            project.intention=body.intention;project.status='running';project.version++;
            return {project:clone(project)};
          }
          if(url.endsWith('/image-operations')&&method==='POST'){
            const body=JSON.parse(options.body);
            check(body.version===project.version,'manual operation must use the refreshed revision');
            const op={...body,id:'operation-'+((project.image_operations||[]).length+1),status:'running',phase:'rendering',
              action:{title:body.kind==='hq'?'Essai HQ':'Étape demandée',change:body.intention},error:null,output_asset_id:null};
            (project.image_operations||=[]).push(op);project.version++;return {project:clone(project)};
          }
          if(url.endsWith('/transitions'))return {project_id:'transitions-fixture'};
          if(url.endsWith('/projects/journey-fixture')&&method==='GET'){
            const result={project:clone(project)};
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
          check(el('auto-mask').checked,'mask should be enabled by default');
          check(!el('plan').open,'milestones should be collapsed');
          const dt=new DataTransfer();dt.items.add(new File(['fixture'],'start.png',{type:'image/png'}));
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('intention').value='Aménager la cave';el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          el('count').value='1';el('prompt-model').value='writer';
          el('start').click();await wait(()=>project&&!el('pause').disabled);
          check(!el('setup').open,'settings should fold after generation starts');
          el('setup').open=true;project.version++;await window.pollJourney();
          check(el('setup').open,'polling must preserve an explicitly opened panel');
          el('setup').open=false;project.version++;await window.pollJourney();
          check(!el('setup').open,'polling must preserve a folded panel');
          check(project.prompt_model_id==='writer','independent prompt model selection lost');
          check(el('intention').readOnly,'running intention should be read-only');
          check(calls.filter(row=>row[0].endsWith('/projects')&&row[1]==='POST').length===1,'duplicate create request');
          el('pause').click();await wait(()=>!el('resume').hidden&&!el('resume').disabled);
          el('setup').open=true;
          const draft='Créer une bibliothèque <img src=x onerror=alert(1)>';
          el('intention').value=draft;el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          await window.pollJourney();check(el('intention').value===draft,'poll erased a paused draft');
          el('resume').click();await wait(()=>el('message').textContent.includes('Version modifiée')&&!el('resume').disabled);
          check(el('intention').value===draft,'conflict erased the local intention');
          el('resume').click();await wait(()=>project.status==='running'&&el('resume').hidden);
          check(project.intention===draft,'updated intention was not submitted');
          project.steps=[{id:'journey-step-fixture',index:1,source_asset_id:'source',output_asset_id:'output',action:{title:'Isolation terminée',change:'Isoler les murs.'},
            prompt:'Edit <Picture 1>. Keep the camera fixed.',prompt_model_id:'writer',
            raw_output_asset_id:'raw',protection:{mask_asset_id:'mask',coverage:0.2,status:'completed'},
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
          check(!el('detail-protection').hidden&&el('mask-views').children.length===4,'mask comparison views missing');
          el('mask-views').children[2].click();
          check(el('detail-image').alt==='Rendu brut','raw view should use the raw image');
          el('mask-views').children[3].click();
          check(el('detail-image').alt==='Masque','mask view missing');
          el('mask-views').children[0].click();
          check(el('detail-image').alt==='Résultat protégé','protected view should remain the default result');
          el('close').click();
          check(!el('comparison')&&!el('fixed-trial'),'experimental controls must be removed');
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
          el('operation-close').click();plus().at(-1).click();
          check(el('operation-images').querySelectorAll('img').length===1,'append must show only the actual last image');
          el('operation-input').value='Ajouter un petit escalier';el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          el('operation-generate').click();await wait(()=>project.image_operations.length===2&&!el('operation-close').disabled);
          check(manualState().kind==='append'&&manualState().before_frame_id===null,'append should have no following image');
          finishManual();await window.pollJourney();el('operation-close').click();
          const sequenceBeforeHq=JSON.stringify(project.ordered_steps);
          el('frieze').querySelector('[data-ij-hq]').click();
          check(el('operation-input').value.includes('<Picture 1>'),'HQ prompt must be prefilled and literal');
          el('operation-input').value+=' Keep all deck boards.';
          el('operation-input').dispatchEvent(new Event('input',{bubbles:true}));
          el('operation-generate').click();await wait(()=>project.image_operations.length===3&&!el('operation-close').disabled);
          check(manualState().kind==='hq'&&manualState().prompt.includes('deck boards'),'edited HQ prompt was not submitted');
          Object.assign(manualState(),{status:'completed',phase:'completed',output_asset_id:'hq-result'});project.version++;
          await window.pollJourney();
          check(el('operation-images').querySelectorAll('img').length===2,'HQ comparison must show original and result');
          check(JSON.stringify(project.ordered_steps)===sequenceBeforeHq,'HQ changed the journey sequence');
          el('operation-images').querySelectorAll('button')[1].click();
          check(el('detail').open,'HQ result must open at larger size');
          el('detail-zoom').click();check(el('detail-zoom').getAttribute('aria-pressed')==='true','pixel zoom unavailable');
          el('close').click();el('operation-close').click();
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
          el('transitions').click();await wait(()=>opened==='transitions-fixture');
          check(!calls.some(row=>/\/messages|\/attempts|\/send/.test(row[0])),'browser must not orchestrate renders or send videos');
          check(document.documentElement.scrollWidth<=window.innerWidth+2,'workshop overflows horizontally');
          await wait(()=>!el('new').disabled);
          holdGet=true;const pending=window.pollJourney();await wait(()=>releaseGet);
          el('new').click();releaseGet();await pending;
          check(el('result').hidden&&!el('source').disabled&&el('setup').open,'stale poll replaced the new-project form');
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
