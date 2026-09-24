"""User-run multilingual UI fixture. All API calls are fakes."""
import os
from pathlib import Path
import unittest
from tests import test_media_analysis_browser as browser


class EpisodeLocalizationBrowserTest(unittest.TestCase):
    run_browser = browser.MediaAnalysisBrowserTest.run_browser

    def test_create_translate_review_and_guard_unsaved_changes(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        setup = r"""
          const calls=[];
          const source={episode_id:'source',title:'Original',scenes:[]};let current=source, module;
          const copy={episode_id:'copy',title:'Original — English',localization:{language:'English',model_id:'local::gemma',revision:1,job:null},
            scenes:[{id:'scene',title:'Présentation',localization:{slots:[{id:'scene:d1',text:'Bonjour !'}],translations:{},status:'pending'}}]};
          const selected={preparation_id:'prep',project_id:'render',attempt_id:'video',token:'a'.repeat(64),label:'Essai 3',duration:8,dialogue_count:1};
          function catalog(){return {default_model:'local::gemma',languages:{French:'Français',English:'English'},
            sources:[{episode_id:'source',title:'Original',story_revision:1,available:true,scenes:[{id:'scene',title:'Présentation',choices:[selected]}]}],
            groups:current===source?[]:[{group_id:'group',label:'English',language:'English',episodes:[{episode_id:'copy',title:copy.title,
              revision:copy.localization.revision,ready:copy.scenes[0].localization.status==='ready',job:copy.localization.job,scenes:[{
                id:'scene',title:'Présentation',translation:copy.scenes[0].localization.status,video:null,dlss:{status:null}}]}]}]};}
          window.PanelForgeLabCore={request:async(url,options)=>{
            const body=options?.body?JSON.parse(options.body):null; calls.push({url,body});
            if(options?.method==='POST'&&url.endsWith('/localizations/start')){
              copy.localization.revision++;copy.localization.job={status:'succeeded',phase:'Traduction prête'};
              copy.scenes[0].localization.status='ready';copy.scenes[0].localization.translations={'scene:d1':'Hello!'};
              return {episode_ids:['copy']};
            }
            if(options?.method==='POST'&&url.endsWith('/localizations'))return {episode_ids:['copy'],group_id:'group'};
            if(options?.method==='PUT'){
              if(body.expected_revision!==copy.localization.revision)throw Error('stale revision');
              copy.localization.revision++;copy.scenes[0].localization.translations={'scene:d1':body.lines[0].text};return structuredClone(copy);
            }
            if(url.includes('/localizations'))return structuredClone(catalog());
            if(url==='/api/episodes/copy')return structuredClone(copy);
            throw Error('Unexpected request '+url);
          }};
        """
        checks = r"""
          const check=(value,message)=>{if(!value)throw Error(message);};
          const settle=()=>new Promise(resolve=>setTimeout(resolve,40));
          const find=text=>[...document.querySelectorAll('button')].find(b=>b.textContent===text);
          (async()=>{try{
            module=window.PanelForgeEpisodeLocalization.mount({current:()=>current,models:()=>[{id:'local::gemma'}],
              visible:()=>true,refresh:async()=>{},open:async()=>{current=copy;await module.open();}});
            await module.open();
            check(document.querySelector('input[type=checkbox]').checked,'current source preselected');
            find('Créer la copie').click();await settle();await settle();
            const create=calls.find(c=>c.body?.selections);
            check(create.body.selections[0].scenes[0].attempt_id==='video','selected video identity sent');
            check(current===copy,'independent variant opened');
            find('Traduire pour relire').click();await settle();await settle();
            const input=document.querySelector('.localization-review textarea');
            check(input.value==='Hello!','translation displayed beside original');
            input.value='Hi there!';input.dispatchEvent(new Event('input',{bubbles:true}));
            let guarded=false;try{module.guardDirty();}catch(e){guarded=true;}check(guarded,'unsaved edits protected');
            const before=calls.filter(c=>c.url.endsWith('/localizations/start')).length;
            find('Tout lancer').click();await settle();
            check(calls.filter(c=>c.url.endsWith('/localizations/start')).length===before,'unsaved edits do not launch work');
            find('Enregistrer ces répliques').click();await settle();await settle();
            module.guardDirty();
            check(copy.scenes[0].localization.translations['scene:d1']==='Hi there!','author correction saved');
            check(document.querySelector('blockquote').textContent==='Bonjour !','original preserved');
            check(source.scenes.length===0,'source document untouched');
            check(calls.filter(c=>c.url.endsWith('/localizations/start')).length===1,'review save has no LLM call');
            module.close();document.getElementById('result').textContent='PASS';
          }catch(error){module?.close();document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre><section id="episode-localization"></section><script>'
                + setup + '</script><script>' + (browser.STATIC / 'episode-localization.js').read_text(encoding='utf-8')
                + '</script><script>' + checks + '</script>')
        self.run_browser(browsers[-1], html)
