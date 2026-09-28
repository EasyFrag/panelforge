"""User-run UI regression, fake API only; never starts Lab or model services."""
import os
from pathlib import Path
import unittest
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class StoryQualityBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_long_story_defaults_controls_payload_and_manual_writer_choice(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="stories-workspace"' + index.split('<main id="stories-workspace"', 1)[1].split('</main>', 1)[0] + '</main>'
        setup = r"""
          localStorage.clear(); sessionStorage.clear();
          const gemma='local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          const qwen='local::Qwen3.8-27B-fixture'; let created=null;
          localStorage.setItem('panelforge.stories.writer.model.local',gemma);
          window.fetch=async(url, options={})=>{
            if(url==='/api/stories/models')return new Response(JSON.stringify({models:[{id:gemma,source:'local'},{id:qwen,source:'local'}]}));
            if(url==='/api/stories/spec')return new Response(JSON.stringify({recipes:[]}));
            if(url==='/api/stories/projects' && options.method==='POST'){
              created=JSON.parse(options.body); return new Response(JSON.stringify({detail:'Fixture captured; no worker launched.'}),{status:422});
            }
            if(url==='/api/stories/projects')return new Response(JSON.stringify({projects:[]}));
            throw new Error('Unexpected network: '+url);
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);};
            const el=id=>document.getElementById('story-'+id);
            const settle=()=>new Promise(r=>setTimeout(r,250));
            document.querySelector('[data-lab-view="stories"]').click();await settle();
            check(el('format-long').checked && el('workflow-mode').value==='automatic','guided automatic default');
            check(!el('customize').open,'one collapsed customization area');
            check(!el('tone-profile').closest('#story-customize'),'ambiance visible before customization');
            check(el('model-settings').parentElement===el('creation-models'),'model controls grouped in customization');
            el('format-long').click();await settle();
            check(el('architect-model').value===qwen && el('writer-model').value===qwen,'new long stories default to Qwen despite legacy Gemma default');
            check(el('dialogue-pace').value==='fast','fast pace default');
            el('long-ending').value='open';el('long-profile').value='fantasy';
            el('tone-profile').value='black_comedy_street_v1';el('tone-profile').dispatchEvent(new Event('change'));
            check(el('dialogue-style').value==='street' && el('dialogue-register').value==='3','preset aligns register and voice');
            check(el('long-narration').value==='dialogue','preset enables dialogue narration');
            check(el('long-ending').value==='open' && el('long-profile').value==='fantasy','no ending or plot imposed by tone');
            el('dialogue-pace').value='natural';el('dialogue-pace').dispatchEvent(new Event('input'));
            el('dialogue-language').dispatchEvent(new Event('change'));
            check(el('dialogue-pace').value==='natural','custom setting not overwritten by refresh');
            check(el('tone-description').textContent.includes('Personnalisée'),'customization made visible');
            el('glossary').value='Zulima = calme.';el('universe').value='Un univers à ne pas reporter au prochain essai.';
            el('dialogue-style').value='street';el('dialogue-notes').value='Exemple de ton, pas une obligation.';
            el('visual-render').value='live_action';el('visual-notes').value='Lumière de fin de journée.';
            el('protected-lines').value='Rends le portefeuille.';el('brief').value='Le cireur demande à Piccolo de rendre le portefeuille.';
            el('create-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle();
            check(created?.writing_direction.dialogue_style==='street','dialogue style sent');
            check(created.writing_direction.tone_profile==='black_comedy_street_v1','tone persisted');
            check(created.writing_direction.glossary==='Zulima = calme.','optional meanings sent');
            check(created.writing_direction.dialogue_pace==='natural','explicit pace override sent');
            check(created.writing_direction.visual_render==='live_action','live action sent');
            check(created.writing_direction.protected_lines.join('|')==='Rends le portefeuille.','only exact lines are protected');
            check(created.architect_model_id===qwen && created.writer_model_id===qwen,'same default model, distinct roles');
            el('recipe').value='story.silent-cats@1.0.0';el('recipe').dispatchEvent(new Event('change'));
            check(el('tone-profile').disabled && el('glossary').disabled,'silent family disables spoken tone');
            el('create-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle();
            check(created.writing_direction.tone_profile==='none' && created.writing_direction.glossary==='','silent request clears tone and lexicon');
            el('writer-model').value=gemma;el('writer-model').dispatchEvent(new Event('change'));
            el('new').click();el('format-long').click();await settle();
            check(el('writer-model').value===gemma,'explicit Gemma choice retained for subsequent trials');
            check(el('architect-model').value===qwen,'architect still Qwen');
            check(el('protected-lines').value==='','old exact lines do not leak into a new story');
            check(el('glossary').value==='' && el('tone-profile').value==='none','new story has no inherited glossary or tone');
            check(el('universe').value==='' && el('long-ending').value==='auto','old universe and ending do not leak');
            check(!el('customize').open,'customization closed on new story');
            const base={story_quality_version:1,document:{series_outline:{episodes:[]}},
              workflow:{mode:'manual',status:'paused',approvals:{}},long_status:{outline_reviewed:true,outline_approved:false,units:{}}};
            check(window.PanelForgeStoryWriting.describe(base).steps.story!=='done','paused manual arc is not falsely approved');
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
