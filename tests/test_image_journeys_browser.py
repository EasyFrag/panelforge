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
          if(url.endsWith('/spec'))return {default_images:5,max_images:30,default_model_id:'vision',transitions_available:true};
          if(url.endsWith('/models'))return {models:[{id:'vision',label:'Vision local',source:'local'},
            {id:'writer',label:'MiniMax writer',source:'server'}]};
          if(url.endsWith('/projects')&&method==='GET')return {projects:project?[clone(project)]:[]};
          if(url.endsWith('/projects')&&method==='POST'){
            check(options.body instanceof FormData,'creation must upload the selected image');
            check(options.body.get('source_image') instanceof File,'source image missing');
            project={id:'journey-fixture',version:1,name:'Cave aménagée',source_asset_id:'source',status:'running',
              phase:'planning',intention:options.body.get('intention'),count:Number(options.body.get('count')),
              progression_model_id:options.body.get('progression_model_id'),prompt_model_id:options.body.get('prompt_model_id'),
              generated:0,milestones:[],destination:'',completed_milestones:0,steps:[],warning:null,error:null,
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
          check(!el('models').open,'models should be collapsed');
          check(!el('plan').open,'milestones should be collapsed');
          const dt=new DataTransfer();dt.items.add(new File(['fixture'],'start.png',{type:'image/png'}));
          el('source').files=dt.files;el('source').dispatchEvent(new Event('change',{bubbles:true}));
          el('intention').value='Aménager la cave';el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          el('count').value='1';el('prompt-model').value='writer';
          el('start').click();await wait(()=>project&&!el('pause').disabled);
          check(project.prompt_model_id==='writer','independent prompt model selection lost');
          check(el('intention').readOnly,'running intention should be read-only');
          check(calls.filter(row=>row[0].endsWith('/projects')&&row[1]==='POST').length===1,'duplicate create request');
          el('pause').click();await wait(()=>!el('resume').hidden&&!el('resume').disabled);
          const draft='Créer une bibliothèque <img src=x onerror=alert(1)>';
          el('intention').value=draft;el('intention').dispatchEvent(new Event('input',{bubbles:true}));
          await window.pollJourney();check(el('intention').value===draft,'poll erased a paused draft');
          el('resume').click();await wait(()=>el('message').textContent.includes('Version modifiée')&&!el('resume').disabled);
          check(el('intention').value===draft,'conflict erased the local intention');
          el('resume').click();await wait(()=>project.status==='running'&&el('resume').hidden);
          check(project.intention===draft,'updated intention was not submitted');
          project.steps=[{index:1,output_asset_id:'output',action:{title:'Isolation terminée',change:'Isoler les murs.'},
            prompt:'Edit <Picture 1>. Keep the camera fixed.',prompt_model_id:'writer',
            review:{assessment:'similar',observation:'Changement faible, conservé.',model_id:'vision'}}];
          Object.assign(project,{generated:1,status:'completed',phase:'completed',destination:draft,
            milestones:['Préparation','Isolation'],completed_milestones:2,transferable_images:2,version:project.version+1});
          await window.pollJourney();
          check(el('frieze').querySelectorAll('button').length===2,'start plus one new image expected');
          check(el('destination').textContent===draft&&!el('destination').querySelector('img'),'destination must be escaped');
          el('frieze').querySelectorAll('button')[1].click();
          check(el('detail').open,'thumbnail should open the full image');
          check(el('detail-review').textContent.includes('Changement faible'),'real review missing');
          check(el('prompt-text').textContent.includes('<Picture 1>'),'prompt tags must remain literal');
          el('close').click();el('transitions').click();await wait(()=>opened==='transitions-fixture');
          check(!calls.some(row=>/\/messages|\/attempts|\/send/.test(row[0])),'browser must not orchestrate renders or send videos');
          check(document.documentElement.scrollWidth<=window.innerWidth+2,'workshop overflows horizontally');
          await wait(()=>!el('new').disabled);
          holdGet=true;const pending=window.pollJourney();await wait(()=>releaseGet);
          el('new').click();releaseGet();await pending;
          check(el('result').hidden&&!el('source').disabled,'stale poll replaced the new-project form');
          document.body.innerHTML='<pre id="result">IMAGE_JOURNEY_BROWSER_OK</pre>';
        }catch(error){document.body.innerHTML='<pre id="result"></pre>';document.getElementById('result').textContent=error.stack;}})();
        """
        document = ('<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>'
                    + page + '<script>' + fixture + '</script><script>' + code + '</script><script>'
                    + scenario + '</script></body></html>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image-journey.html"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run([str(browsers[0]), "--headless", "--disable-gpu", "--no-sandbox",
                "--user-data-dir=" + str(Path(directory) / "browser-profile"), "--disable-background-networking",
                "--allow-file-access-from-files", "--window-size=1440,1100", "--virtual-time-budget=15000", "--dump-dom",
                path.as_uri()], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('<pre id="result">IMAGE_JOURNEY_BROWSER_OK</pre>', result.stdout)
