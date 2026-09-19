"""User-run browser check with a fake API and no Lab/LLM/media server."""
from pathlib import Path
import os
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class StoriesBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_next_episode_prefills_the_cumulative_memory_and_latest_scenario(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear();sessionStorage.clear();
          const pid='story-continuation-browser-fixture';localStorage.setItem('panelforge.stories.project',pid);
          const gemma='local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          const memory={series_summary:'Citron a découvert le détournement.',latest_ending:'Citron garde la preuve.',
            established_facts:['La reine connaît Citron.'],character_states:['Citron possède la preuve.'],
            unresolved_threads:['Les colis restent cachés.'],available_elements:['Une étiquette signée.']};
          const scenario={title:'La preuve',logline:'Citron découvre le vol.',
            characters:[{id:'citron',name:'Citron',description:'Citron anthropomorphe en jogging.'}],
            locations:[{id:'accueil',name:'Accueil',description:'Comptoir blanc.'}],
            scenes:[{title:'Découverte',location_id:'accueil',character_ids:['citron'],opening_state:'Citron attend.',
              action:'Citron retourne le colis et découvre le nom de la reine.',dialogue:[],ending_state:'Citron conserve l’étiquette.'}]};
          const project={project_id:pid,title:'La preuve',version:3,brief:'Un très ancien épisode qui ne doit pas remplacer la mémoire.',
            scene_count:3,clip_seconds:10,creation_mode:'continuation',proposal_count:1,dialogue_register:2,dialogue_language:'French',
            recipe:{id:'story.brainrot',version:'1.0.0'},architect_model_id:gemma,writer_model_id:gemma,model_id:gemma,
            document:{concepts:[],selected_id:'concept-1',scenario,continuity:memory,continuity_source:memory},
            turns:[],job:null,revisions:[{revision:1,label:'Scénario',document:{}}],diagnostics:[]};
          window.fetch=async(url)=>{
            if(url==='/api/stories/models')return new Response(JSON.stringify({models:[{id:gemma,label:'Gemma',source:'local'}]}));
            if(url==='/api/stories/spec')return new Response(JSON.stringify({recipes:[]}));
            if(url==='/api/stories/projects')return new Response(JSON.stringify({projects:[{project_id:pid,title:project.title}]}));
            if(url==='/api/stories/projects/'+pid)return new Response(JSON.stringify(project));
            throw new Error('Unexpected network '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);},settle=()=>new Promise(r=>setTimeout(r,250));
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            check(!document.getElementById('story-continuity').hidden,'cumulative memory is visible');
            check(document.getElementById('story-continuity-content').textContent.includes('Les colis restent cachés.'),'open thread displayed');
            document.getElementById('story-next-episode').click();
            const brief=document.getElementById('story-brief');
            check(document.getElementById('story-creation-mode').value==='continuation','next project uses continuation mode');
            check(brief.value.includes('MÉMOIRE CUMULATIVE VALIDÉE'),'cumulative memory carried forward');
            check(brief.value.includes('ÉPISODE LE PLUS RÉCENT'),'latest episode remains detailed');
            check(brief.value.includes('Citron retourne le colis'),'latest action preserved');
            check(brief.maxLength===60000&&brief.required,'continuation input contract restored');
            check(document.getElementById('story-scene-count').value==='3','episode format carried forward');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + '<script>' + setup + '</script><script>' + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'lab-core.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)

    def test_proposal_selector_and_script_mode_submit_the_right_operation(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear(); sessionStorage.clear();
          const gemma='local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          const writes=[],creates=[];let project=null;
          window.fetch=async(url,options={})=>{
            if(url==='/api/stories/models')return new Response(JSON.stringify({models:[{id:gemma,label:'Gemma',source:'local'}]}));
            if(url==='/api/stories/spec')return new Response(JSON.stringify({recipes:[]}));
            if(url==='/api/stories/projects'&&(!options.method||options.method==='GET'))return new Response(JSON.stringify({projects:[]}));
            if(url==='/api/stories/projects'&&options.method==='POST'){
              const body=JSON.parse(options.body);creates.push(body);project={project_id:'story-cccccccccccccccccccccccccccccccc',
                title:body.title,version:1,brief:body.brief,scene_count:body.scene_count,clip_seconds:body.clip_seconds,
                creation_mode:body.creation_mode,narrative_format:body.narrative_format,parent_story_id:body.parent_story_id,
                proposal_count:body.proposal_count,recipe:{id:body.recipe_id,version:body.recipe_version},
                dialogue_register:body.dialogue_register,dialogue_language:body.dialogue_language,
                architect_model_id:body.architect_model_id,writer_model_id:body.writer_model_id,model_id:body.writer_model_id,
                document:{concepts:[],selected_id:null,scenario:null},turns:[],job:null,revisions:[],diagnostics:[]};
              return new Response(JSON.stringify(project),{status:201});}
            if(url.endsWith('/write')){const body=JSON.parse(options.body);writes.push(body);project=structuredClone(project);project.version++;
              project.job={request_id:body.request_id,status:'running',operation:body.operation,phase:'Écriture…',draft:'',reasoning:''};
              return new Response(JSON.stringify(project),{status:202});}
            throw new Error('Unexpected network '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);},settle=()=>new Promise(r=>setTimeout(r,50));
            const change=e=>e.dispatchEvent(new Event('change',{bubbles:true}));
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            const formatLong=document.getElementById('story-format-long'),formatShort=document.getElementById('story-format-short');
            formatLong.checked=true;change(formatLong);
            check(document.getElementById('story-creation-mode').disabled,'long stories use their isolated arc pipeline');
            check(document.getElementById('story-mode-description').textContent.includes('quatre épisodes'),'long pipeline is explained');
            formatShort.checked=true;change(formatShort);
            check(!document.getElementById('story-creation-mode').disabled,'short stories keep the existing start modes');
            const recipes=document.getElementById('story-recipe');
            check([...recipes.options].some(option=>option.textContent==='Cru ++'),'explicit family available');
            check([...recipes.options].some(option=>option.textContent==='Chats de couple · muet'),'silent cat family available');
            recipes.value='story.silent-cats@1.0.0';change(recipes);
            check(document.getElementById('story-dialogue-register').disabled,'silent family disables dialogue register');
            check(document.getElementById('story-dialogue-language').disabled,'silent family disables spoken language');
            check(document.getElementById('story-dialogue-register-label').textContent==='Sans paroles','silent policy visible');
            recipes.value='story.brainrot@1.0.0';change(recipes);
            const count=document.getElementById('story-proposal-count'),mode=document.getElementById('story-creation-mode');
            const language=document.getElementById('story-dialogue-language');
            check(!language.disabled&&language.value==='French','French is the compatible default');
            language.value='Japanese';change(language);
            count.value='1';change(count);
            check(document.getElementById('story-create').textContent==='Proposer 1 histoire','one-story label');
            const register=document.getElementById('story-dialogue-register');register.value='3';register.dispatchEvent(new Event('input',{bubbles:true}));
            check(document.getElementById('story-dialogue-register-label').textContent==='Très cru / argot','register label');
            mode.value='continuation';change(mode);
            const brief=document.getElementById('story-brief');
            check(brief.required&&brief.maxLength===60000,'continuation requires a longer saga source');
            check(document.getElementById('story-create').textContent==='Proposer 1 suite','continuation label');
            check(document.getElementById('story-mode-description').textContent.includes('mémoire cumulative'),'cumulative memory explained');
            check(document.getElementById('story-create').disabled,'blank continuation blocks creation');
            brief.value='ÉPISODE 1 — Citron découvre la preuve.';brief.dispatchEvent(new Event('input',{bubbles:true}));
            check(!document.getElementById('story-create').disabled,'a previous episode enables continuation');
            mode.value='script';change(mode);
            brief.value='';brief.dispatchEvent(new Event('input',{bubbles:true}));
            const sceneCount=document.getElementById('story-scene-count');sceneCount.value='3';
            check(sceneCount.closest('label').textContent.includes('Nombre exact de micro-scènes'),'scene count is presented as exact');
            check(document.getElementById('story-proposal-count-row').hidden,'count hidden in script mode');
            check(!language.disabled,'faithful script still declares its actual language');
            check(document.getElementById('story-dialogue-language-description').textContent.includes('n’est pas traduit'),'script translation policy visible');
            check(brief.required,'script is required');
            check(document.getElementById('story-mode-description').textContent.includes('nombre exact'),'script explains grouping into the exact count');
            check(document.getElementById('story-create').disabled,'blank script blocks creation');
            brief.value='LÉA\nBonjour Tom.\n';brief.dispatchEvent(new Event('input',{bubbles:true}));
            check(!document.getElementById('story-create').disabled,'script enables creation');
            document.getElementById('story-create-form').requestSubmit();await settle();
            check(creates.length===1&&creates[0].creation_mode==='script','script mode persisted');
            check(creates[0].narrative_format==='short','existing short-story path remains selected');
            check(creates[0].scene_count===3,'exact selected scene count persisted');
            check(creates[0].proposal_count===1,'selected count persisted without affecting script');
            check(register.disabled&&creates[0].dialogue_register===0,'faithful script disables register');
            check(creates[0].dialogue_language==='Japanese','spoken language persisted');
            check(writes.length===1&&writes[0].operation==='script','script skips idea generation');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + '<script>' + setup + '</script><script>' + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'lab-core.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)

    def test_lazy_navigation_and_saved_projects_remain_usable_when_models_fail(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear(); sessionStorage.clear();
          const pid='story-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
          localStorage.setItem('panelforge.stories.project',pid);
          let finishModels;
          const calls=[];
          const concepts=[1,2,3].map(i=>({id:'concept-'+i,title:'Histoire '+i,hook:'<img src=x onerror=alert(1)>',
            protagonist:'Citron',antagonist:'Reine',escalation:'Accusation',reveal:'Étiquette',ending:'Retour du colis'}));
          const doc={concepts,selected_id:null,scenario:null};
          let project={project_id:pid,title:'Histoire enregistrée',version:2,brief:'Une reine avare.',scene_count:6,clip_seconds:10,
            model_id:'local::fixture',document:doc,turns:[{role:'assistant',text:'Voici les pistes.'}],job:null,
            revisions:[{revision:1,label:'Propositions',document:doc}]};
          window.fetch=async(url,options={})=>{
            calls.push(String(url));
            if(url==='/api/stories/models') return await new Promise(resolve=>{finishModels=()=>resolve(new Response(JSON.stringify({detail:'Serveur LLM indisponible'}),{status:503}));});
            if(url==='/api/stories/projects')return new Response(JSON.stringify({projects:[{project_id:pid,title:project.title}]}));
            if(url==='/api/stories/projects/'+pid)return new Response(JSON.stringify(project));
            if(url.endsWith('/select')){
              const body=JSON.parse(options.body);project=structuredClone(project);project.version++;
              project.document.selected_id=body.concept_id;project.revisions.push({revision:2,label:'Choix',document:project.document});
              return new Response(JSON.stringify(project));
            }
            throw new Error('Unexpected network '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);};
            const settle=()=>new Promise(r=>setTimeout(r,30));
            await settle();check(calls.length===0,'hidden stories must not query model server');
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            check(!document.getElementById('stories-workspace').hidden,'stories navigation visible');
            check(sessionStorage.getItem('panelforge.lab.last-view.v1')==='stories','refresh remembers Stories');
            check(document.querySelectorAll('.story-concept').length===3,'saved ideas loaded before model discovery finishes');
            check(document.querySelectorAll('#story-concepts img').length===0,'LLM text never becomes HTML');
            finishModels();await settle();
            check(document.getElementById('story-model-message').textContent.includes('indisponible'),'offline model status visible');
            document.querySelector('.story-concept button').click();await settle();
            check(document.querySelectorAll('.story-concept.selected').length===1,'selection works without model');
            check(document.getElementById('story-develop').disabled,'generation unavailable without model');
            const instruction=document.getElementById('story-instruction');instruction.value='Garde cette idée.';instruction.dispatchEvent(new Event('input'));
            window.PanelForgeLabNavigation.switchView('krea2-assisted-lab');
            window.PanelForgeLabNavigation.switchView('stories');await settle();
            check(instruction.value==='Garde cette idée.','navigation preserves unsent feedback');
            check(calls.filter(u=>u==='/api/stories/models').length===1,'navigation does not repeatedly discover models');
            project=structuredClone(project);project.version++;project.job={status:'running',phase:'Écriture de la réponse structurée…',
              reasoning:'Je construis trois trajectoires distinctes.',draft:'{"reply":"Je compare les pistes"'};
            document.getElementById('story-refresh-projects').click();await settle();
            check(!document.getElementById('story-live-panel').hidden,'live model trace is visible');
            check(document.getElementById('story-reasoning').textContent.includes('trois trajectoires'),'reasoning streams separately');
            check(document.getElementById('story-draft').textContent.includes('Je compare'),'JSON draft streams separately');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + '<script>' + setup + '</script><script>' + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'lab-core.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)

    def test_local_gemma_default_source_preferences_and_delayed_catalog(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear(); sessionStorage.clear();
          const gemma='local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          const pid='story-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
          let catalog=[{id:'server-qwen',label:'Qwen3.8-27B',source:'server'},
            {id:'server-other',label:'Autre serveur',source:'server'},
            {id:'local::qwen',label:'Qwen3.8-27B',source:'local'},
            {id:gemma,label:'Gemma 4 Hauhau',source:'local'}];
          let finishModels;
          const project={project_id:pid,title:'Ancienne histoire',version:1,brief:'Un conflit.',scene_count:6,clip_seconds:10,
            model_id:'server-other',document:{concepts:[],selected_id:null,scenario:null},turns:[],job:null,revisions:[]};
          window.fetch=async(url)=>{
            if(url==='/api/stories/models')return await new Promise(resolve=>{finishModels=()=>resolve(new Response(JSON.stringify({models:catalog})));});
            if(url==='/api/stories/projects')return new Response(JSON.stringify({projects:[{project_id:pid,title:project.title}]}));
            if(url==='/api/stories/projects/'+pid)return new Response(JSON.stringify(project));
            throw new Error('Unexpected network '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);}, settle=()=>new Promise(r=>setTimeout(r,30));
            const model=document.getElementById('story-architect-model'),local=document.getElementById('story-architect-local');
            const change=element=>element.dispatchEvent(new Event('change',{bubbles:true}));
            const source=value=>{local.checked=value;change(local);};
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            check(local.checked,'local is checked before discovery');
            finishModels();await settle();
            check(model.value===gemma,'Gemma Hauhau takes priority over shared Qwen default');
            check([...model.options].every(o=>o.value.startsWith('local::')),'only local options');
            source(false);check(model.value==='server-qwen','server source is selectable');
            model.value='server-other';change(model);
            source(true);check(model.value===gemma,'returning to local restores Gemma');
            model.value='local::qwen';change(model);
            source(false);check(model.value==='server-other','server choice remembered');
            source(true);check(model.value==='local::qwen','local choice remembered');
            document.getElementById('story-new').click();
            check(local.checked&&model.value==='local::qwen','new story respects explicit preference');
            check(localStorage.getItem('panelforge.stories.architect.model.local')==='local::qwen','preference persisted');
            document.getElementById('story-refresh-models').click();await settle();
            const projects=document.getElementById('story-projects');projects.value=pid;change(projects);await settle();
            finishModels();await settle();
            check(!local.checked&&model.value==='server-other','late catalog preserves reopened project model and source');
            localStorage.removeItem('panelforge.stories.architect.model-source');localStorage.removeItem('panelforge.stories.architect.model.local');
            document.getElementById('story-new').click();
            catalog=catalog.filter(m=>m.id!==gemma);
            document.getElementById('story-refresh-models').click();await settle();finishModels();await settle();
            check(local.checked&&model.selectedOptions[0].dataset.missing==='true','missing default stays identifiable');
            check(document.getElementById('story-create').disabled,'no silent switch to another LLM');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + '<script>' + setup + '</script><script>' + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'lab-core.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)
