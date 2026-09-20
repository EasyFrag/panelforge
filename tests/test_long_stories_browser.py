"""User-run guided story browser regression with a fake API, no model or rendering."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class LongStoriesBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_creation_help_manual_feedback_and_takeover(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear();sessionStorage.clear();
          const model='local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          const creates=[],advances=[],feedbacks=[];let project=null;
          const cast=[{id:'c1',name:'Citronito',description:'Citron anthropomorphe.'}];
          const scene={title:'Le refus',location_id:'l1',character_ids:['c1'],opening_state:'La note arrive.',
            action:'Citronito refuse le partage.',dialogue:[],ending_state:'La serveuse conserve la note.'};
          const outline={title:'La note',premise:'Un rendez-vous se termine mal.',overall_arc:'Un refus change la négociation.',ending:'Chacun paie sa part.',
            characters:cast,contract:{promise:'Une joute verbale.',protagonist_goal:'Faire payer autrui.',stakes:'Perdre la face.',must_keep:[],freedoms:[]},
            world_rules:[],secrets:[],episodes:[{id:'episode-1',title:'La note',promise:'La négociation tourne.',conflict:'Qui paie ?',
              beats:['Un refus.'],events:[{id:'event-1',trigger:'La note arrive.',change:'Le partage est refusé.',evidence:'La carte reste dans la poche.',depends_on:[]}],
              local_payoff:'Le refus tient.',ending_state:'Chacun paie sa part.',carry_forward:'Aucun.',ending_type:'reversal'}]};
          const snap=()=>{project.version++;project.revisions.push({revision:project.revisions.length+1,label:'Résultat'});};
          window.fetch=async(url,options={})=>{
            if(url==='/api/stories/models')return new Response(JSON.stringify({models:[{id:model,label:'Gemma',source:'local'}]}));
            if(url==='/api/stories/spec')return new Response(JSON.stringify({recipes:[]}));
            if(url==='/api/stories/projects'&&options.method==='POST'){
              const body=JSON.parse(options.body);creates.push(body);
              project={...body,project_id:'story-cccccccccccccccccccccccccccccccc',version:1,
                recipe:{id:body.recipe_id,version:body.recipe_version},model_id:model,narrative_engine:{id:'story.long',version:'2.0.0'},
                workflow:{mode:body.workflow_mode,status:'paused',message:'Prêt.',wait_target:null},
                document:{concepts:[],selected_id:null,scenario:null,series_outline:null,episode_scenarios:{},episode_formats:{},episode_states:{},reviews:{}},
                long_status:{outline_reviewed:false,fabrication_ready:false,units:{},reviews:{}},turns:[],job:null,revisions:[],diagnostics:[]};
              return new Response(JSON.stringify(project),{status:201});
            }
            if(url==='/api/stories/projects')return new Response(JSON.stringify({projects:project?[{project_id:project.project_id,title:project.title}]:[]}));
            if(url.endsWith('/advance')){
              advances.push(JSON.parse(options.body));snap();
              project.job={status:'succeeded',operation:'edit_outline',draft:'',reasoning:''};
              if(!project.document.series_outline){
                project.document.series_outline=outline;project.document.selected_episode_id='episode-1';
                project.document.episode_formats['episode-1']={scene_count:8,clip_seconds:10};
                project.document.reviews.outline={summary:'Histoire vérifiée.',issues:[]};
                project.long_status={outline_reviewed:true,fabrication_ready:false,units:{'episode-1':{written:false,ready:false,previous_ready:true}},reviews:{outline:{current:true}}};
                project.workflow={mode:'manual',status:'awaiting_author',wait_target:'outline',message:'Valide la direction.'};
              }else{
                const scenario=project.document.scenario||{title:'La note',logline:'Une négociation échoue.',characters:cast,locations:[{id:'l1',name:'Restaurant',description:'Une table.'}],scenes:[structuredClone(scene)]};
                project.document.scenario=scenario;project.document.episode_scenarios['episode-1']=scenario;
                project.document.episode_states['episode-1']={scene_events:[{scene_index:0,event_ids:['event-1'],evidence:'Le refus est visible.',action_seconds:4,reveals:[]}],facts:[],knowledge:[],open_threads:[],resolved_threads:[]};
                project.long_status.fabrication_ready=true;project.long_status.units['episode-1']={written:true,ready:true,previous_ready:true};
                project.document.reviews['episode-1']={summary:'Refus visible.',issues:[]};project.long_status.reviews['episode-1']={current:true};
                project.workflow={mode:'manual',status:'awaiting_author',wait_target:'episode-1',message:'Séquence prête.'};
              }
              return new Response(JSON.stringify(project),{status:202});
            }
            if(url.endsWith('/feedback')){
              const body=JSON.parse(options.body);feedbacks.push(body);snap();
              const target={unit_id:body.unit_id,scene_index:body.scene_index};
              project.turns.push({role:'user',text:body.instruction,target},{role:'assistant',text:body.question?'La réplique pose une limite.':'Refus renforcé.',target});
              if(!body.question)project.document.scenario.scenes[0].action='Citronito refuse clairement et repousse la note.';
              return new Response(JSON.stringify(project),{status:202});
            }
            if(url.endsWith('/pause')){project.workflow={mode:'manual',status:'paused',message:'Tu as repris la main.'};project.job.status='succeeded';snap();return new Response(JSON.stringify(project));}
            if(project&&url==='/api/stories/projects/'+project.project_id)return new Response(JSON.stringify(project));
            throw new Error('Unexpected network '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);},settle=()=>new Promise(r=>setTimeout(r,150));
            const el=id=>document.getElementById('story-'+id),input=e=>e.dispatchEvent(new Event('input',{bubbles:true}));
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            el('duration').value='5';
            document.querySelector('[data-story-example="social"]').click();
            check(el('long-profile').value==='social'&&el('target-seconds').value==='80','reference preset');
            check(el('duration').value==='10'&&el('scene-count').value==='8','preset restores its clip budget');
            check(!el('proposal-count'),'only one story');
            el('long-profile').closest('label').querySelector('.story-info').click();
            check(el('help').open&&el('help-content').textContent.includes('addition'),'contextual examples');el('help').close();
            el('create-form').requestSubmit();await settle();
            check(creates.length===1&&advances.length===1,'creation with no job does not fail on removed projectCount');
            check(creates[0].workflow_mode==='manual'&&creates[0].visual_universe==='Fruits anthropomorphes','workflow and universe submitted');
            check(!el('guided-tools').hidden&&el('advance').textContent==='Développer le scénario','clear author checkpoint');
            check(el('feedback-target').value==='outline','feedback targets the story first');
            el('advance').click();await settle();
            check(advances.length===2&&el('feedback-target').value==='episode-1','sequence checkpoint');
            const comment=[...el('scenes').querySelectorAll('button')].find(b=>b.textContent==='Commenter cette scène');comment.click();
            check(el('feedback-target').value==='episode-1:0','comment selects exact scene');
            const before=project.document.scenario.scenes[0].action;
            el('instruction').value='Pourquoi refuse-t-il ?';input(el('instruction'));el('question').click();await settle();
            check(feedbacks[0].question&&feedbacks[0].scene_index===0,'question has explicit scope');
            check(project.document.scenario.scenes[0].action===before,'discussion does not rewrite');
            el('instruction').value='Rends le refus plus clair.';input(el('instruction'));el('chat-form').requestSubmit();await settle();
            check(!feedbacks[1].question&&el('scenes').textContent.includes('refuse clairement'),'targeted revision visible');
            project.workflow.status='running';project.job.status='running';project.version++;
            el('refresh-projects').click();await settle();
            el('instruction').value='Ne change pas la fin.';input(el('instruction'));el('pause').click();await settle();
            check(project.workflow.status==='paused'&&el('instruction').value==='Ne change pas la fin.','takeover retains draft');
            check(!el('question').disabled,'feedback becomes available');
            // Existing story: scenes are fresh, but their review has not happened yet.
            project.long_status.fabrication_ready=false;
            project.long_status.units['episode-1']={written:true,stale:false,reviewed:false,ready:false,previous_ready:true};
            delete project.document.reviews['episode-1'];delete project.long_status.reviews['episode-1'];
            project.workflow={mode:'manual',status:'awaiting_author',wait_target:'outline',message:'Développe les scènes.'};
            project.diagnostics=[{code:'estimated_clip_load',level:'warning',message:'Durée estimée à vérifier.'}];snap();
            el('refresh-projects').click();await settle();
            check(el('validate').disabled&&!el('fabrication-gate').hidden,'disabled fabrication has an explanation');
            check(el('fabrication-reason').textContent.includes('relecture n’a pas encore'),'missing review is explicit');
            check(el('advance').textContent==='Valider l’histoire et continuer','existing scenes are not presented as unwritten');
            check(el('fabrication-next').textContent==='Valider l’histoire et relire le scénario'&&!el('fabrication-next').disabled,'action next to fabrication');
            const existingAction=project.document.scenario.scenes[0].action,calls=advances.length;
            el('fabrication-next').click();await settle();
            check(advances.length===calls+1,'inline action resumes guided checks');
            check(project.document.scenario.scenes[0].action===existingAction,'resume preserves written scenes');
            check(!el('validate').disabled&&el('fabrication-gate').hidden,'review unlocks fabrication despite advisory diagnostic');
            check(!el('diagnostics').hidden,'advisory warning remains visible');
            document.querySelector('#result').textContent='PASS';
          }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + '<script>' + setup + '</script><script>' + (STATIC / 'lab.js').read_text(encoding='utf8').split('const ui = {};')[0]
                + '</script><script>' + (STATIC / 'lab-core.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories.js').read_text(encoding='utf8')
                + '</script><script>' + (STATIC / 'stories-help.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)
