"""User-run local Chromium fixture; no server, real LLM or render invocation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class MediaAnalysisBrowserTest(unittest.TestCase):
    def test_lazy_import_order_optional_times_review_and_explicit_transfer(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        markup = (STATIC / "index.html").read_text(encoding="utf-8").split('<main id="media-analysis-workspace"',1)[1].split('</main>',1)[0]
        markup = '<main id="media-analysis-workspace"' + markup + '</main>'
        bootstrap = """
        const requests=[], transfers=[]; let record=null, fail=false;
        window.PanelForgeModelPicker={populate(select,models,current){select.replaceChildren(...models.map(m=>new Option(m.label,m.id)));}};
        window.PanelForgeH3Base={prefillAnalysis(value){transfers.push(['h3',value]);}};
        window.PanelForgeRef2V={prefillAnalysis(value){transfers.push(['ref2v',value]);}};
        window.PanelForgeLabCore={
          async request(url,options={}) {
            requests.push([url,options]);
            if(url.endsWith('/spec')) return {llm_models:[{id:'vision',label:'Vision',source:'local'}]};
            if(url.includes('?limit=3')) return {analyses:record?[record]:[]};
            if(options.method==='PATCH') {record.intention=JSON.parse(options.body).intention.replace(' (images 8-10)',''); return structuredClone(record);}
            if(options.method==='POST') {
              const request=JSON.parse(options.body.get('metadata'));
              record={analysis_id:'analysis-fixture',status:'draft',request,intention:'',observations:[],uncertainties:[]};
              return structuredClone(record);
            }
            throw new Error('Unexpected request: '+url);
          },
          async streamRequest(url,options,onEvent) {
            requests.push([url,options]);
            if(fail) throw new Error('Transport indisponible');
            record={...record,status:'succeeded',intention:'Durée cible : 8 secondes. Une personne marche.',observations:['Visible dans les images.'],uncertainties:['Transition inconnue.']};
            onEvent({kind:'completed',record:structuredClone(record)});
          }
        };
        """
        scenario = """
        (async()=>{try {
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const el=id=>document.getElementById('ma-'+id);
          const settle=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setTimeout(r,0));};
          const change=(input,value)=>{input.value=value;input.dispatchEvent(new Event('input'));};
          check(requests.length===0,'no discovery until opening the analysis tab');
          document.querySelector('[data-video-lab-mode="media-analysis"]').click(); await settle();
          check(requests.length===2,'only spec and three recent analyses loaded');
          const canvas=document.createElement('canvas');canvas.width=32;canvas.height=24;
          canvas.getContext('2d').fillRect(0,0,32,24);
          const blob=await new Promise(r=>canvas.toBlob(r));
          const files=new DataTransfer();for(let i=0;i<3;i++)files.items.add(new File([blob],`image-${i}.png`,{type:'image/png'}));
          el('files').files=files.files;el('files').dispatchEvent(new Event('change'));await settle();
          const cards=()=>[...el('frames').querySelectorAll('article')];
          check(cards().length===3 && cards().every(c=>c.querySelector('input').value===''),'unknown times stay empty');
          [0,1,3].forEach((t,i)=>change(cards()[i].querySelector('input'),String(t)));
          cards()[1].querySelectorAll('button')[1].click();
          check(cards().map(c=>c.querySelector('input').value).join(',')==='0,3,1','timestamps follow reordered images');
          check(el('analyze').disabled,'inconsistent order cannot be sent');
          cards()[2].querySelectorAll('button')[0].click();
          check(!el('analyze').disabled,'fixing order enables analysis');
          fail=true;el('analyze').click();await settle();
          check(cards().length===3 && el('message').textContent.includes('indisponible'),'failed analysis keeps draft');
          fail=false;el('analyze').click();await settle();
          check(el('intention').value.includes('personne marche'),'French intention shown');
          check(record.request.frames.map(f=>f.time_seconds).join(',')==='0,1,3','server receives the temporal anchors');
          check(requests.filter(([url,o])=>url.endsWith('/analyses')&&o.method==='POST').length===1,'retry reuses stored analysis');
          check(el('first').value==='' && el('last').value==='','no H3 anchors implicitly selected');
          check([...el('ref-list').querySelectorAll('select')].every(s=>s.value===''),'no REF2V references implicitly selected');
          check(cards()[0].querySelectorAll('button')[0].disabled && cards()[2].querySelectorAll('button')[1].disabled,'busy refresh preserves reorder boundaries');
          change(el('intention'),'Mon intention corrigée.');
          el('first').selectedIndex=1;el('last').selectedIndex=3;
          el('h3').click();await settle();
          check(transfers[0][0]==='h3' && transfers[0][1].intention==='Mon intention corrigée.','edited intention transferred');
          check(transfers[0][1].firstFile.name==='image-0.png' && transfers[0][1].lastFile.name==='image-2.png','only chosen H3 files transferred');
          const roles=el('ref-list').querySelectorAll('select');
          roles[1].value='subject_reference';roles[1].dispatchEvent(new Event('change'));
          el('ref2v').click();await settle();
          check(transfers[1][1].references.length===1 && transfers[1][1].references[0].file.name==='image-1.png','only selected REF2V image transferred');
          check(transfers[1][1].references[0].role==='subject_reference','role preserved');
          change(el('intention'),'Mon intention corrigée (images 8-10).');
          el('h3').click();await settle();
          check(transfers[2][1].intention==='Mon intention corrigée.','transfer uses server-normalized text, not old analysis citations');
          check(el('intention').value==='Mon intention corrigée.','normalized saved intention is visible');
          change(el('duration'),'10');
          check(el('h3').disabled && !el('stale').hidden,'duration changes invalidate old result before transfer');
          const m=window.PanelForgeAnalysisMedia;
          check(m.sampleTimes(12,20,3,30).join(',')==='12,16,20','sample only selected clip');
          check(m.sampleTimes(12,20,3,20).at(-1)<20,'safe final-frame seek');
          check(!m.timelineError([{time:0},{time:null},{time:3}],8),'partial timestamps accepted');
          check(m.timelineError([{time:3},{time:1}],8),'contradictory timestamps rejected');
          check(m.timelineError([{time:null}],8,8),'video captures require relative timestamps');
          check(requests.every(([url])=>url.startsWith('/api/media-analysis/')),'analysis never submits to render or prompt generation endpoints');
          document.querySelector('#result').textContent='PASS';
        }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        source = '\n'.join((STATIC/name).read_text(encoding='utf-8') for name in ('media-analysis-media.js','media-analysis-speech.js','media-analysis.js'))
        html='<meta charset="utf-8"><pre id="result">PENDING</pre>'+markup+'<script>'+bootstrap+'</script><script>'+source+'</script><script>'+scenario+'</script>'
        self.run_browser(browsers[-1],html)

    def test_actual_handoff_functions_preserve_recipe_and_never_start_preparation(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        bodies=[]
        for filename, export in (("i2v-direct.js","PanelForgeH3Base"),("ref2v-direct.js","PanelForgeRef2V")):
            text=(STATIC/filename).read_text(encoding="utf-8")
            function='function prefillAnalysis('+text.split('function prefillAnalysis(',1)[1].split('  window.'+export,1)[0]
            bodies.append("""{
              const recipe={id:'chosen-recipe'}, state={spec:{},cookbook:recipe,session:{id:'saved'},drafts:[]};
              let locked=false, resets=0; const navigation=[];
              const elements={intention:{value:'',focus(){}},form:{scrollIntoView(){}}};
              const roleOptions=[['subject_reference'],['first_frame'],['last_frame']];
              const interactionLocked=()=>locked;
              const resetSession=()=>{resets++;state.session=null;};
              const render=()=>{}, showSetupMessage=()=>{}, invalidateRoleConfirmation=()=>{}, renderDraftReferences=()=>{};
              const setSelectedFile=(slot,file)=>{state[slot+'File']=file;};
              window.PanelForgeLabNavigation={switchView(value){navigation.push(value);}};
            """+function+"""
              const file=new File(['bytes'],'chosen.png',{type:'image/png'});
              const payload={intention:'Mon intention en français',firstFile:file,lastFile:null,references:[{file,role:'subject_reference'}]};
              prefillAnalysis(payload);
              check(elements.intention.value===payload.intention,'intention unchanged');
              check(state.cookbook===recipe && resets===1 && navigation.length===1,'selected recipe retained and setup only');
              if(state.firstFile) check(state.firstFile===file && !state.lastFile,'H3 anchors unchanged');
              else check(state.drafts.length===1 && state.drafts[0].file===file && state.drafts[0].role==='subject_reference','REF2V role and file unchanged');
              let rejected=false;try{prefillAnalysis(payload);}catch(error){rejected=true;}
              check(rejected && resets===1,'unfinished setup is never overwritten');
              state.session={id:'saved-again'};locked=true;rejected=false;
              try{prefillAnalysis(payload);}catch(error){rejected=true;}
              check(rejected && resets===1,'active preparation is never reset');
            }""")
        script="try {const check=(ok,label)=>{if(!ok)throw new Error(label);};"+'\n'.join(bodies)+"document.querySelector('#result').textContent='PASS';} catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}"
        self.run_browser(browsers[-1],'<meta charset="utf-8"><pre id="result">PENDING</pre><script>'+script+'</script>')

    def run_browser(self,browser,html):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);page=root/'analysis.html';page.write_text(html,encoding='utf-8')
            result=subprocess.run([str(browser),'--headless','--disable-gpu','--disable-background-networking','--no-first-run',
                '--virtual-time-budget=10000',f'--user-data-dir={root / "profile"}','--dump-dom',page.as_uri()],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertEqual(result.returncode,0,result.stderr[-1500:])
            self.assertIn('<pre id="result">PASS</pre>',result.stdout)
