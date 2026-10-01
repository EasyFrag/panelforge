# User-run browser regression; mocked HTTP, no services or model generations.
import json
import os
from pathlib import Path
import unittest
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC
from tests.test_story_v2 import screenplay, settings

class StoryV2BrowserTest(unittest.TestCase):
    run_browser=MediaAnalysisBrowserTest.run_browser

    def test_manual_reader_edits_and_reference_fiches_without_generation(self):
        browsers=sorted((Path(os.environ.get("LOCALAPPDATA",""))/"ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers and Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe").is_file():
            browsers=[Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")]
        if not browsers:self.skipTest("local Chromium not installed")
        html=(STATIC/"index.html").read_text(encoding="utf-8")
        start=html.index('  <main id="story-v2-workspace"');end=html.index('</main>',start)+len('</main>')
        markup='<meta charset="utf-8"><pre id="result">PENDING</pre><button data-lab-view="story-v2">V2</button>'+html[start:end]
        project=dict(id="storyv2-"+"a"*32,version=1,status="awaiting_review",script=screenplay(),settings=settings(),history=[],review=dict(issues=[]),approved=None,episode_id=None,factory_ids=[],videos=[],error=None)
        project["script"]["sequences"][0]["dialogue"][0].update(addressee_ids=["marc"],
            address_cue="Mia se tourne vers Marc pour lui répondre.")
        fixture='const original='+json.dumps(project,ensure_ascii=False)+';'+r'''
          let current=structuredClone(original),requests=[];
          localStorage.setItem('panelforge.story-v2.last-settings.v2',JSON.stringify({...original.settings,
            universe:'Univers mémorisé',image_model:'old-checkpoint',dlss:false,
            images:{...original.settings.images,style_preset_id:null},
            video:{...original.settings.video,render:{...original.settings.video.render,recipe:{id:'old-recipe',version:'missing'}}}}));
          const response=value=>({ok:true,status:200,json:async()=>structuredClone(value)});
          window.PanelForgeLabNavigation={switchView:()=>{document.getElementById('story-v2-workspace').hidden=false;}};
          window.fetch=async(url,options={})=>{
            requests.push([url,options.method||'GET']);
            if(url==='/api/stories/models')return response({models:[{id:'fake',label:'Fake'}]});
            if(url==='/api/stories-v2/preferences')return response({settings:original.settings});
            if(url==='/api/image-lab/krea2-assisted/style-presets')return response({presets:[{preset_id:'style-642721e10d124d5a83ad6bb907ef8fd3',name:'Bananita fresh',category:'work',prompt_language:'en',settings:{model_id:'Krea2/kroma-v0.3-turbo.safetensors',loras:[]},art_direction:null},{preset_id:'test-style',name:'Style test',category:'work',prompt_language:'en',settings:{model_id:'preset-checkpoint',loras:[{name:'style.safetensors',strength:.6}],aspect_ratio:'9:16 (Portrait Widescreen)',megapixels:2.1},art_direction:{style_id:'art-test',name:'Test'}}]});
            if(url==='/api/image-lab/krea2-assisted/spec')return response({render_models:[],workflows:[{id:'krea2-flux-klein@1.0.0',label:'KREA2 + Flux Klein'}],aspect_ratios:['9:16 (Portrait Widescreen)'],assistance_recipes:[{version:'6.0.0',label:'V6'}],sampling:{presets:[{id:'finish_4',label:'Finition 4 steps · 8 + 4',settings:original.settings.images.sampling}]}});
            if(url.startsWith('/api/h3-render/spec')){
              const query=new URL(url,'http://fixture').searchParams;
              if(query.get('mode')!=='ref2va'||query.get('recipe_id')!==original.settings.video.render.recipe.id||![original.settings.video.render.recipe.version,'0.1.3'].includes(query.get('recipe_version')))
                return {ok:false,status:422,json:async()=>({detail:'Recette de rendu ou version indisponible pour ce mode.'})};
              return response({recipe:original.settings.video.render.recipe,render_recipes:[{...original.settings.video.render.recipe,label:'BUNNY'}],aspect_ratios:['9:16 (Portrait Widescreen)'],presets:[{id:'default',label:'Default',steps:9}],defaults:{steps:9},bunny:{turbo_profiles:{on:{base_steps:9,coarse_steps:4,refine_steps:5},off:{base_steps:30,coarse_steps:25,refine_steps:5}}},video_lora_stack:{supported:false},checkpoint_selection:{supported:false}});
            }
            if(url==='/api/stories-v2/projects')return response({projects:[{id:current.id,title:current.script.title,status:current.status}]});
            if(url.endsWith('/approve')){
              current.version++;current.approved='approved';current.episode_id='episode-fake';current.status='references_ready';
              current.episode={episode_id:'episode-fake',reference_batch:null,references:[{id:'character-1',name:'Mia',description:'Personnage adulte',revision:1,images:[],image_asset_id:null,krea_project_id:null,prompt:'',model_id:'fake',render_settings:null}]};
              return response({project:current});
            }
            if(url==='/api/stories-v2/projects/'+current.id){
              if(options.method==='PUT'){const b=JSON.parse(options.body);current.script=b.script;current.settings=b.settings;current.version++;}
              return response({project:current});
            }
            throw Error('Unexpected request '+url);
          };
        '''
        scenario=r'''
        (async()=>{try{
          const check=(v,m)=>{if(!v)throw Error(m);};const el=id=>document.getElementById('sv2-'+id);
          const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
          document.querySelector('[data-lab-view="story-v2"]').click();await settle();
          check(!el('message').textContent&&!el('model-note').textContent,'initial settings load without an error banner');
          check(el('universe').value==='Univers mémorisé','cache migration preserves narrative settings');
          check(el('scene-duration').value==='10','new scene duration defaults to ten seconds');
          check(!el('final-review-enabled').checked,'final control off by default');
          check(el('reader-model').parentElement.parentElement.contains(el('final-review-enabled')),'final control placed below reader model');
          check(!el('polish-enabled').checked&&el('polish-model-field').hidden,'polish optional and compact by default');
          check(el('polish-model').value===original.settings.polish_model,'independent prose model initialized');
          el('polish-enabled').checked=true;el('polish-enabled').dispatchEvent(new Event('change',{bubbles:true}));
          check(!el('polish-model-field').hidden&&!el('polish-model').disabled,'prose selector enabled on a new story');
          el('polish-enabled').checked=false;el('polish-enabled').dispatchEvent(new Event('change',{bubbles:true}));
          check(el('image-model').value===original.settings.image_model&&el('dlss').checked,'old image/video cache does not mask new defaults');
          check(el('image-style-preset').selectedOptions[0].textContent==='Bananita fresh','default personal preset is readable');
          check(el('video-ratio').value==='9:16 (Portrait Widescreen)'&&el('video-mp').value==='0.9','video format and resolution loaded');
          check([...el('projects').options].some(o=>o.value===current.id),'project catalog loads after settings');
          check(el('video-plan-model').value===original.settings.video.plan_model,'video plan model initialized');
          check(el('video-prompt-model').value===original.settings.video.prompt_model,'video writer model initialized');
          check(el('video-shots').value==='','automatic shot count initialized');
          const recipe=el('video-recipe'),chosenRecipe=recipe.value;
          recipe.add(new Option('Unavailable recipe','missing@0.0.0'));recipe.value='missing@0.0.0';recipe.dispatchEvent(new Event('change',{bubbles:true}));await settle();
          check(el('model-note').textContent.includes('indisponible'),'unavailable video recipe reported');
          recipe.value=chosenRecipe;recipe.dispatchEvent(new Event('change',{bubbles:true}));await settle();
          check(!el('model-note').textContent,'successful video load clears stale recipe error');
          el('projects').value=current.id;el('projects').dispatchEvent(new Event('change'));await settle();

          current.status='polishing';current.version++;
          current.progress={id:'call-polish',index:3,total:4,label:'Retouche des dialogues',model:'local::unsloth/gemma-4-31B-it-qat-GGUF',status:'running',started_at:new Date(Date.now()-2200).toISOString()};
          el('refresh').click();await settle();
          check(!el('progress').hidden&&el('progress-label').textContent.includes('Appel 3/4'),'real call count displayed');
          check(el('progress-label').textContent.includes('Gemma 4'),'compact active model name');
          check(el('polish-enabled').disabled&&el('final-review-enabled').disabled,'polishing locks both independent options');
          const beforeTimer=el('progress-time').textContent;await new Promise(r=>setTimeout(r,1150));
          check(el('progress-time').textContent!==beforeTimer,'timer advances between server polls');
          current.status='awaiting_review';current.progress.status='succeeded';current.progress.elapsed_seconds=2.4;current.version++;
          el('refresh').click();await settle();
          check(el('progress-time').textContent.includes('00:02'),'finished call duration is frozen');
          el('polish-enabled').checked=true;el('polish-enabled').dispatchEvent(new Event('change',{bubbles:true}));
          check(!el('polish-model-field').hidden&&!el('polish-model').disabled,'prose selector appears when enabled');
          check(!el('final-review-enabled').checked,'enabling prose does not enable final control');
          el('final-review-enabled').checked=true;el('final-review-enabled').dispatchEvent(new Event('change',{bubbles:true}));
          check(el('polish-enabled').checked,'final control does not change prose option');
          check(el('writer-model').value===original.settings.writer_model&&el('reader-model').value===original.settings.reader_model,'prose option preserves author and reader');
          check(el('image-recipe').value==='6.0.0'&&!el('image-inspirations').checked,'V6 without local inspirations');
          check(el('image-mp').value==='2.1'&&el('edit-engine').value==='minimax','image defaults');
          check(el('axis-audacity').value==='3'&&el('axis-dialogue').value==='1','creative defaults');
          check(el('produce').textContent==='Envoyer en préparation','factory action explicit');
          check(document.querySelectorAll('.sv2-sequence').length===2,'all sequences readable');
          check(el('summary').textContent===current.script.summary.join(' '),'short episode summary');
          check(document.querySelectorAll('.sv2-intention').length===2,'one intention per sequence');
          check(document.querySelectorAll('.sv2-dialogue').length===2,'dialogue readable');
          const edit=document.querySelector('.sv2-sequence button');check(!edit.disabled,'edit enabled after loading');edit.click();
          check(!el('sequences').textContent.includes('se tourne vers Marc'),'address metadata stays invisible');
          el('edit-form').dispatchEvent(new Event('submit',{cancelable:true}));
          el('save').click();await settle();
          check(current.script.sequences[0].dialogue[0].addressee_ids[0]==='marc','unchanged edit keeps recipient');
          check(current.script.sequences[0].dialogue[0].address_cue.includes('se tourne'),'unchanged edit keeps cue');
          document.querySelector('.sv2-sequence button').click();
          el('edit-action').value='Mia annonce la naissance prochaine à Marc.';
          el('edit-form').dispatchEvent(new Event('submit',{cancelable:true}));
          check(!el('save').disabled,'local correction marked dirty');el('save').click();await settle();
          check(current.script.sequences[0].action.includes('annonce'),'edit saved');
          check(current.script.sequences[0].dialogue[0].addressee_ids[0]==='marc','action edit keeps recipient');
          check(!current.script.sequences[0].dialogue[0].address_cue,'changed staging clears stale gaze cue');
          document.querySelector('.sv2-sequence button').click();
          el('edit-dialogues').querySelector('textarea').value='Je voudrais te parler.';
          el('edit-form').dispatchEvent(new Event('submit',{cancelable:true}));
          el('save').click();await settle();
          check(!current.script.sequences[0].dialogue[0].addressee_ids&&!current.script.sequences[0].dialogue[0].address_cue,'changed line clears hidden addressing');
          check(current.settings.final_review_enabled&&current.settings.polish_enabled,'independent options persisted');
          el('approve').click();await settle();
          check(!el('references').hidden,'manual approval opens references');
          check(!requests.some(([u])=>u.endsWith('/references')),'approval does not generate images in manual mode');
          const fiche=[...el('ref-list').querySelectorAll('button')].find(b=>b.textContent==='Ouvrir la fiche');
          check(fiche,'fiche exists before any image generation');fiche.click();await settle();
          check(el('ref-editor').open&&el('ref-description').value==='Personnage adulte','blank reference editable');
          check(!requests.some(([u])=>u.endsWith('/produce')),'videos never launched implicitly in manual mode');
          el('ref-close').click();
          el('image-style-preset').value='test-style';el('image-style-preset').dispatchEvent(new Event('change',{bubbles:true}));
          check(el('image-model').value==='preset-checkpoint','preset checkpoint applied');
          check(el('art-name').textContent==='Test','preset art direction applied');
          el('save').click();await settle();el('new').click();await settle();
          check(el('idea').value===''&&el('image-model').value==='preset-checkpoint','new story retains latest settings but clears idea');
          check(el('final-review-enabled').checked&&el('polish-enabled').checked,'new story keeps latest independent choices');
          check(!requests.some(([u,m])=>m!=='GET'&&(/minimax|qwen|h3-render|launch/.test(u))),'no generation from setting changes');
          document.getElementById('result').textContent='PASS';
        }catch(e){document.getElementById('result').textContent='FAIL: '+e.stack;}})();
        '''
        source=(STATIC/'story-v2-settings.js').read_text(encoding='utf-8')+'\n'+(STATIC/'story-v2.js').read_text(encoding='utf-8')
        self.run_browser(browsers[-1],markup+'<script>'+fixture+'</script><script>'+source+'</script><script>'+scenario+'</script>')
