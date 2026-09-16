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
        markup = '<main id="stories-workspace"' + (STATIC / "index.html").read_text(encoding="utf8").split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = "const story=" + json.dumps(story, ensure_ascii=False) + ";let episode=" + json.dumps(episode, ensure_ascii=False) + ";"
        setup += r"""
          const calls=[], mounts=[];let currentContext=null;
          const model={comfy_name:'krea2_turbo_bf16.safetensors',resource_id:'checkpoint-1',display_name:'KREA2',category:'bf16',favorite:false};
          const model2={...model,resource_id:'checkpoint-2',comfy_name:'other.safetensors',display_name:'Other'};
          const lora={resource_id:'lora-1',comfy_name:'pastel.safetensors',display_name:'Pastel',category:'sfw_style',lora_category:'sfw_style'};
          const stylePreset={preset_id:'style-1',revision:1,name:'Pastel 3D'};
          localStorage.clear();
          window.PanelForgeStories={current:()=>story};
          window.PanelForgeH3Render={mount:(prefix,event,mode,options)=>{
            mounts.push({prefix,mode,options});return {busy:false,open:async context=>{currentContext=context;},close:async()=>{currentContext=null;},parameters:()=>({})};}};
          window.PanelForgePromptRecipes={showHistory:()=>{},open:()=>{}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push({url,options});const body=options.body?JSON.parse(options.body):null;
            if(url.startsWith('/api/episodes/stories/'))return {episodes:[episode]};
            if(url==='/api/stories/models')return {models:[{id:episode.scenes[0].plan_model_id,label:'Qwen local',source:'local'},
              {id:episode.scenes[0].writer_model_id,label:'Gemma local',source:'local'}]};
            if(url.startsWith('/api/image-lab/krea2-assisted/spec'))return {render_models:[model,model2],loras:[lora],
              aspect_ratios:['9:16 (Portrait Widescreen)'],defaults:{aspect_ratio:'9:16 (Portrait Widescreen)'},sampling:{presets:[{id:'current',label:'Actuel',settings:episode.image_defaults.sampling}]}};
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
            if(url.endsWith('/project'))return {project:null};
            const sceneId=url.match(/\/scenes\/(scene-\d+)/)?.[1];
            if(sceneId&&options.method==='PUT'){
              const scene=episode.scenes.find(s=>s.id===sceneId);Object.assign(scene,body);scene.revision++;scene.render_revision++;
              scene.render_setup.settings.duration_seconds=scene.duration;return structuredClone(episode);
            }
            if(sceneId&&url.endsWith('/prompt')){
              const scene=episode.scenes.find(s=>s.id===sceneId);scene.job={status:'succeeded'};
              scene.preparations.push({id:'prep-one',session_id:'session-one',render_project_id:'render-one',status:'ready',render_setup:structuredClone(scene.render_setup)});
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
            const checkpoint=get('common-model').nextElementSibling;
            check(checkpoint.querySelector('.krea2-resource-favorite')&&checkpoint.querySelector('.krea2-resource-info'),'shared checkpoint favorites and info');
            checkpoint.querySelector('.krea2-resource-favorite').click();await settle();
            check(model.favorite&&calls.some(c=>c.url.endsWith('/preference')),'favorite persists through shared catalog endpoint');
            get('style-preset').value='style-1';get('apply-preset').click();await settle();await settle();
            check(episode.style_preset.revision===1&&!get('style-preview').hidden,'style preset applied and preview shown');
            check(get('common-loras').querySelector('input').value==='0.6','preset lora strength shown');
            get('image-toggle-settings').click();get('image-model').value='other.safetensors';change(get('image-model'));
            get('reference').value='character-2';change(get('reference'));await settle();
            check(episode.references[0].inherit_image_settings===false&&episode.references[0].render_settings.model_id==='other.safetensors','personal checkpoint survives navigation');
            check(get('image-custom').hidden,'next fiche inherits common settings');
            get('reference').value='character-1';change(get('reference'));await settle();
            check(!get('image-custom').hidden&&get('image-model').value==='other.safetensors','personalized controls restored');
            get('image-toggle-settings').click();get('save-reference').click();await settle();
            check(episode.references[0].inherit_image_settings&&get('image-custom').hidden,'return to common settings persists');
            get('tab-scenes').click();await settle();
            check(get('reference-limit').textContent==='4 / 9 images','no three-reference restriction');
            check(get('plan-local').checked&&get('writer-local').checked,'both models default local');
            check(get('plan-model').value.includes('Qwen')&&get('writer-model').value.includes('gemma'),'Qwen then Gemma');
            check(get('dialogues').textContent.includes('Victor : « Vous avez pris mon portefeuille ! »'),'exact attributed dialogue');
            check(get('scenes').querySelectorAll('.creative-axes-control input[type=range]').length===5,'five independent sliders');
            get('creative-camera').value='3';get('creative-camera').dispatchEvent(new Event('input'));
            get('creative-extra-motion').value='2';get('creative-extra-motion').dispatchEvent(new Event('input'));
            check(get('creative-camera-value').value==='3'&&get('creative-dialogue').value==='0','live outputs and dialogue default');
            get('intention').value='Victor recule et Lila montre la poche.';get('intention').dispatchEvent(new Event('input'));
            get('writer-model').value=episode.scenes[0].plan_model_id;get('writer-model').dispatchEvent(new Event('input'));change(get('writer-model'));
            get('scene').value='scene-2';change(get('scene'));await settle();
            check(episode.scenes[0].intention==='Victor recule et Lila montre la poche.','scene edits persist before navigation');
            check(episode.scenes[0].writer_model_id===episode.scenes[0].plan_model_id,'custom writer saved per scene');
            check(episode.scenes[0].creative_axes.camera===3&&episode.scenes[0].creative_axes.extra_motion===2&&episode.scenes[0].creative_axes.dialogue===0,'all axes persist independently');
            check(get('creative-camera').value==='2','other scene retains its own creative axes');
            check(get('scene').value==='scene-2'&&get('duration').value==='8','scene picker and duration stay in sync');
            check(get('writer-model').value.includes('gemma'),'other scene retains its own model');
            get('prepare').click();await settle();await settle();
            check(currentContext?.scene_id==='scene-2'&&currentContext?.project_id==='render-one','renderer belongs to selected scene');
            check(currentContext.render_setup.settings.duration_seconds===8,'scene duration passed to renderer');
            check(currentContext.render_setup.recipe.id==='minimax-h3-bunny','BUNNY default');
            check(currentContext.render_setup.video_loras.entries.length===1&&currentContext.render_setup.video_loras.entries[0].name.includes('Motion_Repair'),'only Motion Repair');
            check(document.getElementById('episoder-lab')&&document.getElementById('ref2vr-lab'),'renderer DOM isolated from existing REF2V');
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
