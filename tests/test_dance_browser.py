"""User-run browser checks with fake APIs and a fake shared renderer; no server."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'src/panelforge/features/lab/static'


class DanceBrowserTest(unittest.TestCase):
    def test_sources_prompt_and_selected_draft_flow(self):
        chrome = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
        if not chrome.is_file():
            self.skipTest('Chrome local non installé')
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        marker = '<main id="ref2vd-workspace"'
        page = marker + html.split(marker,1)[1].split('</main>',1)[0] + '</main>'
        fixture = r"""
        const el=id=>document.getElementById(id), check=(v,m)=>{if(!v)throw Error(m);};
        const wait=async test=>{for(let i=0;i<200;i++){if(test())return;await new Promise(r=>setTimeout(r,5));}throw Error('timeout');};
        localStorage.clear();
        let project=null, hooks=null, imports=0, calls=[];
        window.PanelForgeH3Render={mount(prefix,event,mode,options){
          hooks=options;check(prefix==='dancer'&&mode==='ref2va','shared REF2V renderer required');
          check(options.specPurpose==='dance','recipe catalog must be scoped');
          return {refreshControls(){el("dancer-render").textContent=options.renderActionState().label;options.onRenderControls({disabled:false});},close(){el('dancer-lab').hidden=true;}, async open({project_id}){
            check(project_id===project.project_id,'wrong project');el('dancer-lab').hidden=false;
            el('dancer-ratio').replaceChildren(new Option('Portrait','9:16 (Portrait Widescreen)'),new Option('Landscape','16:9 (Widescreen)'));
            el('dancer-initial-megapixels').value='0.9';el('dancer-megapixels').value='0.9';
            el('dancer-prompt').value=project.current_prompt;
            el('dancer-revision-model').replaceChildren(new Option('Gemma','local::gemma-4'));
            el('dancer-revision-model').value='local::gemma-4';
            el('dancer-attempts').replaceChildren();
            for(const attempt of project.attempts){const card=document.createElement('article');options.attemptActions(attempt,card,project);el('dancer-attempts').append(card);}
            options.onProjectChange(project);
          }};
        }};
        window.fetch=async(url,init={})=>{
          const method=init.method||'GET';calls.push([url,method,init.body]);
          let result={};
          if(url==='/api/dance/projects'&&method==='GET')result={available:true,projects:project?[{id:project.project_id,title:'Danse test'}]:[]};
          else if(url==='/api/dance/videos'){
            check(init.body.get('file') instanceof File,'missing video');imports++;
            result={asset_id:'source',duration_seconds:20,has_audio:true};
          }else if(url==='/api/dance/projects'&&method==='POST'){
            check(init.body.get('image') instanceof File,'missing photo');
            check(init.body.get('video_asset_id')==='source','wrong source');
            check(init.body.get('keep_audio')==='true','source audio must be on');
            project={project_id:'dance-test',references:[{content_url:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='}],
              dance_reference:{label:'Danse test',clip_asset_id:'clip',duration_seconds:8,keep_audio:true,has_audio:true},current_prompt:'original',attempts:[]};
            result={project};
          }else if(url.endsWith('/polish')){
            check(JSON.parse(init.body).model_id==='local::gemma-4','wrong writer');result={prompt:'proposed'};
          }else if(url.endsWith('/prompt')){
            project.current_prompt=JSON.parse(init.body).prompt;result={project};
          }else if(url.endsWith('/finalize')){
            check(url.includes('/attempts/chosen/'),'must finalize selected draft');
            check(JSON.parse(init.body).megapixels===1.2,'wrong target resolution');
            project.attempts.push({attempt_id:'refined',index:2,status:'created'});result={project};
          }else if(url.endsWith('/refined/start')){project.attempts.at(-1).status='running';result={project};}
          else if(url.endsWith('/attempts')){result={project};}
          else throw Error('Unexpected API: '+method+' '+url);
          return {ok:true,json:async()=>structuredClone(result)};
        };
        const upload=(id,name,type)=>{const transfer=new DataTransfer();transfer.items.add(new File(['fake'],name,{type}));el(id).files=transfer.files;el(id).dispatchEvent(new Event('change'));};
        """
        scenario = r"""
        (async()=>{try{
          check(el('ref2vr-prompt')&&el('dancer-prompt'),'source or cloned renderer missing');
          const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
          check(new Set(ids).size===ids.length,'duplicate DOM ids');
          check(el('ref2vr-revision-model').closest('#ref2vr-lab'),'original model moved');
          document.querySelector('[data-ref-mode-button="dance"]').click();
          await wait(()=>!el('dance-new').disabled);
          upload('dance-image','photo.png','image/png');upload('dance-video','dance.mp4','video/mp4');
          await wait(()=>imports===1&&!el('dance-create').disabled);
          const creates=()=>calls.filter(c=>c[0]==='/api/dance/projects'&&c[1]==='POST').length;
          el('dance-start').value='9';el('dance-start').dispatchEvent(new Event('input'));
          el('dance-duration').value='5';el('dance-duration').dispatchEvent(new Event('input'));
          check(el('dance-create').disabled,'five seconds must be rejected before upload');
          check(el('dance-excerpt-note').textContent.includes('5,2'),'minimum duration must be visible');
          check(el('dance-duration').getAttribute('aria-invalid')==='true','invalid duration not marked');
          el('dance-create').click();check(creates()===0,'invalid excerpt reached the API');
          el('dance-duration').value='5.2';el('dance-duration').dispatchEvent(new Event('input'));
          check(!el('dance-create').disabled,'minimum usable excerpt still blocked');
          el('dance-start').value='18';el('dance-start').dispatchEvent(new Event('input'));
          check(el('dance-create').disabled,'excerpt past the video end must be blocked');
          el('dance-start').value='9';el('dance-start').dispatchEvent(new Event('input'));
          el('dance-duration').value='12';el('dance-duration').dispatchEvent(new Event('input'));
          check(el('dance-create').disabled,'duration past the video end must be blocked');
          el('dance-duration').value='';el('dance-duration').dispatchEvent(new Event('input'));
          check(el('dance-create').disabled,'empty duration must not become zero');
          el('dance-duration').value='5.2';el('dance-duration').dispatchEvent(new Event('input'));
          el('dance-create').click();await wait(()=>project&&!el('dance-new').disabled);
          const sent=calls.find(c=>c[0]==='/api/dance/projects'&&c[1]==='POST')[2];
          check(sent.get('start')==='9'&&sent.get('duration')==='5.2','corrected values must reach the API unchanged');
          check(el('dance-inputs').hidden&&!el('dance-sources').hidden,'saved sources not visible');
          check(el('dancer-initial-megapixels').value==='0.9'&&el('dancer-megapixels').value==='0.9','recipe MP defaults must be preserved');
          check(!el('dance-quick-preview').checked&&hooks.danceStage()==='full','normal render must be the default');
          check(el('dancer-render').textContent==='Générer la danse','direct action label');
          check(el('dance-quick-preview').closest('details')&&!el('dance-quick-preview').closest('details').open,'preview option must be folded');
          check(el('dance-clip-preview').getAttribute('src').includes('/clip/'),'prepared excerpt missing');
          const lastRender=()=>JSON.parse(calls.filter(c=>c[0].endsWith('/attempts')).at(-1)[2]);
          await hooks.prepareAttempt({prompt:'original',initial_megapixels:.9,megapixels:.9});
          check(lastRender().dance_stage==='full'&&lastRender().megapixels===.9,'direct equal-resolution request changed');
          el('dance-quick-preview').checked=true;el('dance-quick-preview').dispatchEvent(new Event('change'));
          check(el('dancer-render').textContent==='Générer un aperçu'&&hooks.danceStage()==='draft','optional preview label/stage');
          await hooks.prepareAttempt({prompt:'original',initial_megapixels:.9,megapixels:.9});
          check(lastRender().dance_stage==='draft','preview request must save the first pass');
          hooks.onRenderControls({disabled:true});check(el('dance-quick-preview').disabled,'preview mode must lock during rendering');
          hooks.onRenderControls({disabled:false});
          el('dance-quick-preview').checked=false;el('dance-quick-preview').dispatchEvent(new Event('change'));
          check(el('dancer-render').textContent==='Générer la danse','direct label not restored');
          el('dance-instruction').value='Keep the outfit';el('dance-polish').click();
          await wait(()=>!el('dance-proposal').hidden&&!el('dance-polish').disabled);
          check(el('dancer-prompt').value==='original','writer must propose before replacing');
          el('dance-apply').click();check(el('dancer-prompt').value==='proposed','proposal not applied');
          el('dance-save-prompt').click();await wait(()=>project.current_prompt==='proposed'&&!el('dance-new').disabled);
          project.attempts=[{attempt_id:'chosen',index:1,status:'succeeded',can_finalize:true}];
          const card=document.createElement('article');hooks.attemptActions(project.attempts[0],card,project);el('dancer-attempts').append(card);
          check(card.querySelector('button').textContent==='Finaliser cet aperçu','legacy draft action lost');
          el('dancer-megapixels').value='1.2';card.querySelector('button').click();
          await wait(()=>project.attempts.at(-1).status==='running');
          check(calls.some(c=>c[0].endsWith('/chosen/finalize')),'no finalize request');
          check(!calls.some(c=>c[0].includes('from-session')),'dance must not invent a story session');
          document.body.innerHTML='<pre id="result">DANCE_BROWSER_OK</pre>';
        }catch(error){document.body.innerHTML='<pre id="result"></pre>';el('result').textContent=error.stack;}})();
        """
        code = (STATIC/'dance.js').read_text(encoding='utf-8')
        content = '<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="connect-src \'none\'">' + page
        content += '<script>' + fixture + '</script><script>' + code + '</script><script>' + scenario + '</script>'
        with tempfile.TemporaryDirectory(prefix='panelforge-dance-browser-') as temp:
            path=Path(temp)/'test.html';path.write_text(content,encoding='utf-8')
            result=subprocess.run([str(chrome),'--headless','--disable-gpu','--no-sandbox','--disable-background-networking',
                '--no-first-run','--no-default-browser-check','--user-data-dir='+str(Path(temp)/'profile'),
                '--virtual-time-budget=8000','--dump-dom',path.as_uri()],capture_output=True,text=True,
                encoding='utf-8',errors='replace',timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertIn('<pre id="result">DANCE_BROWSER_OK</pre>',result.stdout,result.stdout[-4000:])


if __name__=='__main__':
    unittest.main()
