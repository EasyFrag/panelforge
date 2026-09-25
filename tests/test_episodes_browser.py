"""User-run DOM integration with fake APIs: no model, image or video generation."""
import json
import os
from pathlib import Path
import unittest
from copy import deepcopy

from tests.test_episodes import SCENARIO
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC
from panelforge.domain.episodes import initial_episode, scene_inputs


class EpisodesBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_video_overview_reports_prompt_and_video_progress_separately(self):
        script = (STATIC / "episodes.js").read_text(encoding="utf8")
        style = (STATIC / "episodes.css").read_text(encoding="utf8")
        overview = script.split("  function drawVideoOverview() {", 1)[1].split("  function imageRecord(", 1)[0]
        self.assertIn('Prompts ${promptReady}/${chainItems.length}', overview)
        self.assertIn(r'Vid\u00e9os ${videoDone}/${chainItems.length}', overview)
        self.assertIn('updateStage(refs.planStatus, "Plan", plan, stageText[plan] || plan)', script)
        self.assertIn('updateStage(refs.writerStatus, "Rédacteur", writer, stageText[writer] || writer)', script)
        self.assertIn('pauseVideoChain("after_active")', script)
        self.assertIn('pauseVideoChain("after_queue")', script)
        self.assertIn('Relancer les sc\u00e8nes incompl\u00e8tes', script)
        self.assertIn('videoRecoveryRunning()', script)
        self.assertIn('auto_dlss: true', script)
        self.assertIn('auto_dlss: false', script)
        self.assertIn('if (refs.media.dataset.assetId !== assetId)', script)
        self.assertNotIn('el("video-cards").replaceChildren', overview)
        self.assertIn('episode-video-card.processing', style)

    def test_scene_navigation_preserves_edits_and_passes_bunny_defaults(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        scenario = deepcopy(SCENARIO)
        scenario["scenes"].append({**deepcopy(scenario["scenes"][0]), "title": "Le retournement"})
        story = dict(project_id="story-" + "a" * 32, version=2, clip_seconds=10,
                     document={"scenario": scenario}, revisions=[{"revision": 1}])
        episode = initial_episode(story, "episode-" + "b" * 32)
        for i, ref in enumerate(episode["references"]): ref["image_asset_id"] = f"image-{i}"
        episode["scenes"][1]["duration"] = 8
        episode["scenes"][1]["render_setup"]["settings"]["duration_seconds"] = 8
        for scene in episode["scenes"]:
            scene.update(resolved_intention=scene_inputs(episode, scene)["source_text"], stale=False, input_error=None)
        episode["references"][0]["image_asset_id"] = None
        episode["references"][1]["image_asset_id"] = None
        episode["references"][0]["krea_project_id"] = "krea2-create-fixture"
        markup = '<main id="stories-workspace"' + (STATIC / "index.html").read_text(encoding="utf8").split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = "const story=" + json.dumps(story, ensure_ascii=False) + ";let episode=" + json.dumps(episode, ensure_ascii=False) + ";"
        setup += r"""
          const calls=[], mounts=[];let currentContext=null, renderBusy=false;
          const renderParameters=()=>{
            const s=currentContext.render_setup;
            return {recipe_id:s.recipe.id,recipe_version:s.recipe.version,checkpoint:s.checkpoint,
              initial_megapixels:s.initial_megapixels,...s.settings,
              duration_seconds:Number(document.getElementById('episoder-duration').value),
              seed_locked:s.seed_locked,music_enabled:s.music_enabled,spectrum_enabled:s.spectrum_enabled,
              force_upscale:s.force_upscale,bunny:s.bunny,video_loras:s.video_loras,video_lora:s.video_lora};
          };
          const openRender=async context=>{currentContext=context;
            document.getElementById('episoder-duration').value=context.render_setup.settings.duration_seconds;};
          const model={comfy_name:'krea2_turbo_bf16.safetensors',resource_id:'checkpoint-1',display_name:'KREA2',category:'bf16',favorite:false};
          const model2={...model,resource_id:'checkpoint-2',comfy_name:'other.safetensors',display_name:'Other'};
          const lora={resource_id:'lora-1',comfy_name:'pastel.safetensors',display_name:'Pastel',category:'sfw_style',lora_category:'sfw_style'};
          const stylePreset={preset_id:'style-1',revision:1,name:'Pastel 3D'};
          localStorage.clear();
          window.PanelForgeStories={current:()=>story};
          window.PanelForgeH3Render={mount:(prefix,event,mode,options)=>{
            mounts.push({prefix,mode,options});return {get busy(){return renderBusy;},open:openRender,openSetup:openRender,
              close:async()=>{currentContext=null;},parameters:renderParameters,refreshControls:()=>{}};}};
          window.PanelForgePromptRecipes={showHistory:()=>{},open:()=>{}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push({url,options});const body=options.body?JSON.parse(options.body):null;
            if(url.startsWith('/api/episodes/stories/'))return {episodes:[episode]};
            if(url==='/api/stories/models')return {models:[{id:episode.scenes[0].plan_model_id,label:'Qwen local',source:'local'},
              {id:episode.scenes[0].writer_model_id,label:'Gemma local',source:'local'},
              {id:'server-qwen',label:'Qwen serveur',source:'server'}]};
            if(url.startsWith('/api/image-lab/krea2-assisted/spec'))return {render_models:[model,model2],loras:[lora],
              aspect_ratios:['9:16 (Portrait Widescreen)'],defaults:{aspect_ratio:'9:16 (Portrait Widescreen)'},
              workflows:[{id:'krea2-sampling@1.0.0',label:'KREA2 · deux passes',default_sampling_preset_id:'current'},
                {id:'krea2-flux-klein@1.0.0',label:'KREA2 + Flux Klein',default_sampling_preset_id:'current'}],
              sampling:{presets:[{id:'current',label:'Actuel',settings:episode.image_defaults.sampling},
                {id:'moody',label:'Moody',settings:{...episode.image_defaults.sampling,preset_id:'moody'}}]}};
            if(url==='/api/image-lab/krea2-assisted/style-presets')return {presets:[stylePreset]};
            if(url.endsWith('/checkpoint-1/preference')){Object.assign(model,body,{category:body.favorite?'favorite_bf16':'bf16'});return {...model};}
            if(url.endsWith('/visual')){episode.style=body.style;episode.image_defaults=body.settings;episode.visual_revision++;return structuredClone(episode);}
            if(url.endsWith('/style-preset')){
              episode.style_preset=body.preset_id?stylePreset:null;episode.style_image=body.preset_id?{asset_id:'style-img',filename:'Pastel 3D'}:null;
              episode.image_defaults.model_id=model.comfy_name;episode.image_defaults.loras=[{name:lora.comfy_name,strength:0.6}];
              episode.visual_revision++;return structuredClone(episode);
            }
            const refId=url.match(/\/references\/(character-\d+|location-\d+)$/)?.[1];
            if(refId&&options.method==='PUT'){
              const ref=episode.references.find(r=>r.id===refId);Object.assign(ref,body);ref.revision++;return structuredClone(episode);
            }
            if(url.endsWith('/project'))return {project:{attempts:[{attempt_id:'attempt-one',index:1,label:'Essai 1',
              status:'succeeded',output_asset_id:'image-candidate',accepted:false}]}};
            const sceneId=url.match(/\/scenes\/(scene-\d+)/)?.[1];
            if(sceneId&&options.method==='PUT'&&url.endsWith('/'+sceneId)){
              const scene=episode.scenes.find(s=>s.id===sceneId);Object.assign(scene,body);scene.revision++;scene.render_revision++;
              return structuredClone(episode);
            }
            if(sceneId&&url.endsWith('/render-attempts')){
              const scene=episode.scenes.find(s=>s.id===sceneId);
              if(body.preparation_id!==scene.preparations.at(-1).id)throw new Error('latest preparation required');
              scene.preparations.push({...structuredClone(scene.preparations.at(-1)),id:'prep-new-images',render_project_id:'render-new-images',images_refreshed:true});
              scene.stale=false;scene.image_refresh_names=[];
              return {project:{project_id:'render-new-images',attempts:[]},preparation_id:'prep-new-images',episode:structuredClone(episode)};
            }
            if(sceneId&&url.endsWith('/prompt')){
              const scene=episode.scenes.find(s=>s.id===sceneId);scene.job={status:'succeeded'};
              scene.preparations.push({id:'prep-one',session_id:'session-one',render_project_id:'render-one',status:'ready',render_setup:structuredClone(scene.render_setup)});
              return structuredClone(episode);
            }
            const renderSceneId=url.match(/\/scenes\/(scene-\d+)\/render-setup$/)?.[1];
            if(renderSceneId){
              const scene=episode.scenes.find(s=>s.id===renderSceneId),p=body.parameters;
              if(body.expected_revision!==scene.render_revision)throw new Error('render revision matches saved scene');
              scene.render_setup={recipe:{id:p.recipe_id,version:p.recipe_version},checkpoint:p.checkpoint,
                initial_megapixels:p.initial_megapixels,settings:{aspect_ratio:p.aspect_ratio,megapixels:p.megapixels,
                  duration_seconds:p.duration_seconds,steps:p.steps,seed:p.seed},seed_locked:p.seed_locked,
                music_enabled:p.music_enabled,spectrum_enabled:p.spectrum_enabled,force_upscale:p.force_upscale,
                bunny:p.bunny,video_loras:p.video_loras,video_lora:p.video_lora};
              scene.effective_render_setup=structuredClone(scene.render_setup);scene.inherit_video_settings=false;
              return {render_revision:++scene.render_revision};
            }
            if(url.endsWith('/video-defaults')){
              episode.video_defaults={recipe:{id:body.parameters.recipe_id,version:body.parameters.recipe_version},
                checkpoint:body.parameters.checkpoint,initial_megapixels:body.parameters.initial_megapixels,
                settings:{aspect_ratio:body.parameters.aspect_ratio,megapixels:body.parameters.megapixels,
                  duration_seconds:body.parameters.duration_seconds,steps:body.parameters.steps,seed:Number(body.parameters.seed||0)},
                seed_locked:body.parameters.seed_locked,music_enabled:body.parameters.music_enabled,spectrum_enabled:body.parameters.spectrum_enabled,
                force_upscale:body.parameters.force_upscale,bunny:body.parameters.bunny,video_loras:body.parameters.video_loras};
              episode.video_revision++;return {video_revision:episode.video_revision,
                render_revisions:Object.fromEntries(episode.scenes.map(scene=>[scene.id,++scene.render_revision]))};
            }
            if(url.endsWith('/video-chain')){
              episode.video_chain={chain_id:'chain-one',status:'completed',phase:'Toutes les vidéos sont terminées',items:[{scene_id:body.scene_ids[0],status:'succeeded'}]};
              return structuredClone(episode);
            }
            if(url==='/api/episodes/'+episode.episode_id)return structuredClone(episode);
            throw new Error('Unexpected API '+url);
          }};
        """
        checks = r"""
          (async()=>{try{
            const check=(value,message)=>{if(!value)throw new Error(message);}, settle=()=>new Promise(r=>setTimeout(r,50));
            const get=id=>document.getElementById('episode-'+id), change=e=>e.dispatchEvent(new Event('change',{bubbles:true}));
            await settle();check(!calls.some(c=>c.url.includes('/spec')||c.url.includes('/models')),'catalog stays lazy before fabrication');
            document.getElementById('story-fabrication').click();await settle();await settle();
            check(!get('workshop').hidden,'fabrication opens');check(get('reference').options.length===4,'three characters and decor');
            const characterBatchLlm=get('batch-character-llm'),characterBatchLocal=get('batch-character-local');
            check(characterBatchLocal.checked&&characterBatchLlm.value===episode.scenes[0].plan_model_id,'batch character profile exposes the available local Unsloth model');
            check(get('batch-location-local').checked&&get('batch-location-llm').value===episode.scenes[0].plan_model_id,'batch location profile exposes the available local Unsloth model');
            check(!characterBatchLlm.selectedOptions[0].dataset.missing,'available local model is not marked missing');
            characterBatchLocal.checked=false;change(characterBatchLocal);
            check(characterBatchLlm.value==='server-qwen','batch profile can switch to the server catalogue');
            characterBatchLocal.checked=true;change(characterBatchLocal);
            check(characterBatchLlm.value===episode.scenes[0].plan_model_id,'batch profile can return to the local catalogue');
            check(document.querySelectorAll('#episode-visual-panel').length===1&&get('batch-character-custom').hidden,'one common visual block and inherited KREA2 profile');
            get('batch-character-toggle').click();
            check(!get('batch-character-custom').hidden&&get('batch-character-summary').textContent.includes('personnalisé'),'character profile can be customized explicitly');
            get('batch-character-toggle').click();
            check(get('batch-character-custom').hidden&&get('batch-character-summary').textContent.includes('commun'),'character profile can return to common settings');
            let choice=get('image-attempts').querySelector('button[data-image-choice]');
            check(choice&&choice.textContent==='Utiliser cette image'&&!choice.disabled,'finished image can be selected after opening fabrication');
            get('back').click();await settle();document.getElementById('story-fabrication').click();await settle();await settle();
            choice=get('image-attempts').querySelector('button[data-image-choice]');
            check(choice&&!choice.disabled,'finished image stays selectable after leaving and reopening fabrication');
            const checkpoint=get('common-model').nextElementSibling;
            check(checkpoint.querySelector('.krea2-resource-favorite')&&checkpoint.querySelector('.krea2-resource-info'),'shared checkpoint favorites and info');
            checkpoint.querySelector('.krea2-resource-favorite').click();await settle();
            check(model.favorite&&calls.some(c=>c.url.endsWith('/preference')),'favorite persists through shared catalog endpoint');
            get('common-workflow').value='krea2-flux-klein@1.0.0';change(get('common-workflow'));get('save-style').click();await settle();
            check(episode.image_defaults.workflow==='krea2-flux-klein@1.0.0','workflow family is saved with common image settings');
            get('style-preset').value='style-1';get('apply-preset').click();await settle();await settle();
            check(episode.style_preset.revision===1&&!get('style-preview').hidden,'style preset applied and preview shown');
            check(get('common-loras').querySelector('input').value==='0.6','preset lora strength shown');
            get('asset-model').value=episode.scenes[0].writer_model_id;get('asset-model').dispatchEvent(new Event('input'));
            get('image-toggle-settings').click();get('image-workflow').value='krea2-flux-klein@1.0.0';change(get('image-workflow'));
            get('image-model').value='other.safetensors';change(get('image-model'));
            get('image-preset').value='moody';get('image-preset').dispatchEvent(new Event('input'));
            get('image-mp').value='3';get('image-mp').dispatchEvent(new Event('input'));
            get('image-seed').value='42';get('image-seed').dispatchEvent(new Event('input'));
            get('reference').value='character-2';change(get('reference'));await settle();
            check(episode.references[0].inherit_image_settings===false&&episode.references[0].render_settings.model_id==='other.safetensors','personal checkpoint survives navigation');
            check(get('asset-model').value===episode.scenes[0].writer_model_id,'blank next character adopts the previous LLM');
            check(!get('image-custom').hidden&&get('image-workflow').value==='krea2-flux-klein@1.0.0'&&get('image-model').value==='other.safetensors','blank next character adopts workflow and checkpoint');
            check(get('image-preset').value==='moody'&&get('image-mp').value==='3'&&get('image-seed').value==='42','blank next character adopts preset, size and seed');
            check(get('message').textContent.includes('repris'),'copied settings are announced');
            get('reference').value='character-1';change(get('reference'));await settle();
            check(episode.references[1].model_id===episode.scenes[0].writer_model_id&&episode.references[1].render_settings.sampling.preset_id==='moody','adopted settings persist when leaving the next character');
            check(!get('image-custom').hidden&&get('image-model').value==='other.safetensors','personalized controls restored');
            get('image-toggle-settings').click();get('save-reference').click();await settle();
            check(episode.references[0].inherit_image_settings&&get('image-custom').hidden,'return to common settings persists');
            get('tab-scenes').click();await settle();
            check(get('reference-limit').textContent==='4 / 9 images','no three-reference restriction');
            check(currentContext?.scene_id==='scene-1'&&!currentContext.project_id,'render settings open before a prompt exists');
            check(typeof mounts[0].options.onSetupRender==='function','episode renderer exposes the deferred render action');
            const queuedScene=episode.scenes[1];
            queuedScene.job={status:'running',phase:'1/2 · Plan REF2V'};
            queuedScene.preparations=[{id:'queued-fixture',status:'running',prompt_stages:{plan:'queued',writer:'queued'}}];
            get('refresh').click();await settle();
            const queuedCard=get('video-cards').querySelector('[data-scene-id="scene-2"]');
            check(queuedCard.textContent.includes('◷ Plan : planifié'),'queued plan has a distinct visible state');
            check(!queuedCard.classList.contains('processing'),'queued scene does not pulse as active');
            queuedScene.preparations[0].prompt_stages.plan='running';
            get('refresh').click();await settle();
            check(queuedCard.textContent.includes('● Plan : en cours')&&queuedCard.classList.contains('processing'),'admitted plan becomes blue and active');
            queuedScene.job=null;queuedScene.preparations=[];get('refresh').click();await settle();
            const beforeChain=episode.video_chain;
            episode.video_chain={chain_id:'chain-wait',status:'running',phase:'Attente d’un rendu H3 déjà actif',items:[
              {scene_id:'scene-2',status:'prompt_ready',phase:'Attente d’un autre rendu H3',admission_wait:'Ancien atelier encore actif',error:null}]};
            get('refresh').click();await settle();
            check(queuedCard.textContent.includes('un autre rendu H3 est encore actif'),'admission wait is visible instead of falsely ready to start');
            episode.localization={language:'English',job:null};
            episode.scenes.forEach(s=>s.localization={status:'ready',slots:[],translations:{}});
            episode.video_chain.items[0].status='pending';episode.video_chain.items[0].admission_wait=null;
            get('refresh').click();await settle();
            check(queuedCard.textContent.includes('en attente du lancement')&&!queuedCard.textContent.includes('en attente du prompt'),'translated scenes do not pretend to await prompt writing');
            delete episode.localization;episode.scenes.forEach(s=>delete s.localization);episode.video_chain=beforeChain;
            get('refresh').click();await settle();
            const duration=document.getElementById('episoder-duration');
            duration.value='8';duration.dispatchEvent(new Event('input',{bubbles:true}));
            get('scene').value='scene-2';change(get('scene'));await settle();
            check(episode.scenes[0].duration===10&&episode.scenes[0].render_setup.settings.duration_seconds===8,'render duration saved without changing narrative duration');
            check(!calls.some(c=>c.url.endsWith('/video-defaults')),'editing a scene never writes common settings');
            get('scene').value='scene-1';change(get('scene'));await settle();
            check(document.getElementById('episoder-duration').value==='8','duration restored on reopening');
            check(get('video-cards').querySelector('[data-scene-id="scene-1"]').textContent.includes('8 s'),'card shows render duration');
            const common=episode.scenes[0].render_setup;
            duration.dispatchEvent(new Event('input',{bubbles:true}));renderBusy=true;
            await mounts[0].options.onSetupRender({recipe_id:common.recipe.id,recipe_version:common.recipe.version,
              checkpoint:common.checkpoint,initial_megapixels:common.initial_megapixels,...common.settings,
              seed:String(common.settings.seed),seed_locked:common.seed_locked,music_enabled:common.music_enabled,
              spectrum_enabled:common.spectrum_enabled,force_upscale:common.force_upscale,bunny:common.bunny,
              video_loras:common.video_loras,video_lora:null,prompt:''},currentContext);
            renderBusy=false;
            check(calls.some(c=>c.url.endsWith('/video-chain')&&JSON.parse(c.options.body).scene_ids[0]==='scene-1'&&JSON.parse(c.options.body).auto_dlss===false),'setup action snapshots settings and programs the selected scene without automatic DLSS');
            check(get('plan-local').checked&&get('writer-local').checked,'both models default local');
            check(get('plan-model').value.includes('Qwen')&&get('writer-model').value.includes('gemma'),'Qwen then Gemma');
            check(get('dialogues').textContent.includes('Victor : « Vous avez pris mon portefeuille ! »'),'exact attributed dialogue');
            check(get('scenes').querySelectorAll('.creative-axes-control input[type=range]').length===5,'five independent sliders');
            get('creative-camera').value='3';get('creative-camera').dispatchEvent(new Event('input'));
            get('creative-extra-motion').value='2';get('creative-extra-motion').dispatchEvent(new Event('input'));
            check(get('creative-camera-value').value==='3'&&get('creative-dialogue').value==='1','live outputs and dialogue default');
            get('intention').value='Victor recule et Lila montre la poche.';get('intention').dispatchEvent(new Event('input'));
            get('writer-model').value=episode.scenes[0].plan_model_id;get('writer-model').dispatchEvent(new Event('input'));change(get('writer-model'));
            get('scene').value='scene-2';change(get('scene'));await settle();
            check(episode.scenes[0].intention==='Victor recule et Lila montre la poche.','scene edits persist before navigation');
            check(episode.scenes[0].writer_model_id===episode.scenes[0].plan_model_id,'custom writer saved per scene');
            check(episode.scenes[0].creative_axes.camera===3&&episode.scenes[0].creative_axes.extra_motion===2&&episode.scenes[0].creative_axes.dialogue===1,'all axes persist independently');
            check(get('creative-camera').value==='3','other scene retains its own creative axes');
            check(get('scene').value==='scene-2'&&get('duration').value==='8','scene picker and duration stay in sync');
            check(get('writer-model').value.includes('gemma'),'other scene retains its own model');
            get('prepare').click();await settle();await settle();
            check(currentContext?.scene_id==='scene-2'&&currentContext?.project_id==='render-one','renderer belongs to selected scene');
            check(currentContext.render_setup.settings.duration_seconds===8,'scene duration passed to renderer');
            check(currentContext.render_setup.recipe.id==='minimax-h3-bunny','BUNNY default');
            check(currentContext.render_setup.video_loras.entries.length===1&&currentContext.render_setup.video_loras.entries[0].name.includes('Motion_Repair'),'only Motion Repair');
            check(document.getElementById('episoder-lab')&&document.getElementById('ref2vr-lab'),'renderer DOM isolated from existing REF2V');
            const refreshedScene=episode.scenes[1];
            refreshedScene.stale=true;refreshedScene.image_refresh_names=['Pêchette'];
            get('refresh').click();await settle();await settle();
            check(get('scene-state').textContent.includes('sans appel LLM'),'image-only refresh is explained');
            check(mounts[0].options.renderActionState(currentContext).label.includes('nouvelles images'),'render action announces current images');
            const previousPreparation=currentContext.preparation_id;
            const parameters={...renderParameters(),prompt:'My exact prompt'};
            await mounts[0].options.beforeRender(parameters,currentContext);
            const refreshed=await mounts[0].options.prepareAttempt(parameters,currentContext);
            check(refreshed.project.project_id==='render-new-images','manual launch uses the episode endpoint');
            check(currentContext.project_id==='render-new-images'&&currentContext.preparation_id==='prep-new-images','render context switches to new version');
            check(get('preparation').value==='prep-new-images','new preparation is selected');
            check(mounts[0].options.renderActionState({...currentContext,preparation_id:previousPreparation}).disabled,'historical version cannot silently render old images');
            refreshedScene.stale=true;refreshedScene.image_refresh_names=[];
            get('refresh').click();await settle();
            check(mounts[0].options.renderActionState(currentContext).disabled,'changed intention requires a new prompt');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>' + markup
                + '<section id="ref2vr-lab" hidden></section><script>' + setup + '</script><script>'
                + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'krea2-resource-ui.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'episodes.js').read_text(encoding='utf8')
                + '</script><script>' + checks + '</script>')
        self.run_browser(browsers[-1], html)
