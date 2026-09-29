"""User-run browser fixture for edition selection; all endpoints are synthetic."""
import os
from pathlib import Path
import unittest
from tests import test_media_analysis_browser as fixture
STATIC = fixture.STATIC


class StoryEditionsBrowserTest(unittest.TestCase):
    run_browser = fixture.MediaAnalysisBrowserTest.run_browser

    def test_default_pinned_reopening_switch_without_generation_and_running_lock(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear();sessionStorage.clear();
          const ref={id:'reference-2026-09-27',label:'Référence · v1',date:'2026-09-27',summary:'Version conservée',fingerprint:'ref',policy_version:1};
          const exp={id:'experimental-2026-09-27',label:'Expérimentale · v2',date:'2026-09-27',summary:'Fidélité et langue',fingerprint:'exp',policy_version:2};
          const qwen='local::Qwen3.8-27B-fixture', requests=[];let fail=false,created=null;
          let project={project_id:'story-'+'a'.repeat(32),title:'Histoire conservée',version:1,brief:'Une idée courte.',
            recipe:{id:'story.brainrot',version:'1.0.0'},narrative_format:'long',narrative_engine:{id:'story.long',version:'2.0.0'},
            creation_mode:'ideas',clip_seconds:10,scene_count:5,dialogue_language:'French',dialogue_register:0,
            architect_model_id:qwen,writer_model_id:qwen,model_id:qwen,
            long_options:{profile:'social',delivery:'continuous',narration:'dialogue',ending_type:'resolution',unit_count:1},
            document:{concepts:[],selected_id:null,scenario:null,series_outline:null,selected_episode_id:null,episode_scenarios:{},episode_formats:{},reviews:{}},
            workflow:{mode:'automatic',status:'paused',message:'Prêt.',approvals:{},repairs:{},calls:0},
            long_status:{outline_reviewed:false,units:{},fabrication_ready:false},diagnostics:[],turns:[],revisions:[],job:null,
            writing_edition:ref,writing_edition_info:{selected:ref,error:null,result_edition:ref,result_fingerprint:'ref'}};
          window.fetch=async(url,options={})=>{
            requests.push([url,options.method||'GET']);
            const response=value=>new Response(JSON.stringify(value));
            if(url==='/api/stories/models')return response({models:[{id:qwen,source:'local'}]});
            if(url==='/api/stories/spec')return response({recipes:[],writing_editions:{latest:exp.id,editions:[exp,ref]}});
            if(url==='/api/stories/projects'&&options.method==='POST'){
              created=JSON.parse(options.body);return new Response(JSON.stringify({detail:'Captured; no worker.'}),{status:422});
            }
            if(url==='/api/stories/projects')return response({projects:[project]});
            if(url.endsWith('/writing-edition')){
              if(fail)return new Response(JSON.stringify({detail:'Une chaîne est en cours.'}),{status:409});
              const body=JSON.parse(options.body);project.writing_edition=body.edition_id===ref.id?ref:exp;
              project.writing_edition_info.selected=project.writing_edition;project.version++;return response(project);
            }
            if(url==='/api/stories/projects/'+project.project_id)return response(project);
            throw new Error('Unexpected endpoint: '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);},el=id=>document.getElementById('story-'+id);
            const settle=()=>new Promise(r=>setTimeout(r,300));
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            check(el('edition').value===exp.id,'latest experimental selected for new story');
            check(!el('edition').disabled,'catalog available');
            check(el('edition-control').previousElementSibling.classList.contains('story-project-control'),'selector beside library');
            el('edition').value=ref.id;el('edition').dispatchEvent(new Event('change'));await settle();
            check(requests.every(r=>r[1]==='GET'),'changing new-story preference does not call LLM or create project');
            el('brief').value='Une idée.';el('create-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle();
            check(created.writing_edition_id===ref.id,'chosen reference in creation request');
            await window.PanelForgeStories.open(project.project_id);await settle();
            check(el('edition').value===ref.id,'reopened story keeps pinned edition');
            const documentBefore=JSON.stringify(project.document);
            el('edition').value=exp.id;el('edition').dispatchEvent(new Event('change'));await settle();
            check(el('edition').value===exp.id,'selection persisted');
            check(JSON.stringify(project.document)===documentBefore,'no story rewrite');
            check(el('edition-note').textContent.includes('Texte actuel'),'result provenance distinct from next-call edition');
            check(!requests.some(r=>/\/(write|advance|retry)$/.test(r[0])),'no generation from edition selection');
            fail=true;el('edition').value=ref.id;el('edition').dispatchEvent(new Event('change'));await settle();
            check(el('edition').value===exp.id,'failed save restores recorded selection');
            fail=false;project.workflow.status='running';await window.PanelForgeStories.open(project.project_id);await settle();
            check(el('edition').disabled,'running chain locks selector');
            project.workflow.status='paused';await window.PanelForgeStories.open(project.project_id);await settle();
            el('new').click();await settle();check(el('edition').value===exp.id,'new story returns to latest');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        scripts = [(STATIC / 'lab.js').read_text(encoding='utf-8').split('const ui = {};')[0]]
        scripts += [(STATIC / name).read_text(encoding='utf-8') for name in ('lab-core.js', 'story-writing.js', 'stories.js')]
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre>'
                '<button data-lab-view="change-view">Image</button><button data-lab-view="stories">Histoires</button>'
                '<section id="krea2-assisted-lab-workspace"></section>' + markup
                + ''.join('<script>'+script+'</script>' for script in [setup, *scripts, scenario]))
        self.run_browser(browsers[-1], html)


if __name__ == "__main__":
    unittest.main()
