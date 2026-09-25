"""User-run browser fixture; fake library API only, no live service or generation."""
import os
from pathlib import Path
import unittest
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class StoryLibraryBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_search_favorites_languages_trash_restore_and_organization(self):
        browsers = sorted((Path(os.environ.get('LOCALAPPDATA',''))/'ms-playwright').glob('chromium-*/chrome-win64/chrome.exe'))
        if not browsers:
            self.skipTest('local Chromium not installed')
        index = (STATIC/'index.html').read_text(encoding='utf8')
        markup = '<dialog id="story-library"'+index.split('<dialog id="story-library"',1)[1].split('</dialog>',1)[0]+'</dialog>'
        setup = r"""
          const a='story-'+'a'.repeat(32),b='story-'+'b'.repeat(32),c='story-'+'c'.repeat(32);
          const calls=[],opens=[];let current={project_id:a,title:'Le Glow-up de Pêchette'};
          const counts=(done)=>({references:4,reference_total:4,prompts:6,videos:done,dlss:0,scenes:6,stale:0,errors:0,active:false,complete_units:true});
          const item=(id,title,number,done)=>({project_id:id,title,episode_number:number,episode_count:1,updated_at:'2026-09-24',trashed:false,active:false,progress_error:null,
            stages:{intention:'done',story:'done',scenario:'done',references:'done',videos:done===6?'done':'planned'},completed:done===6,
            variants:[{language:'French',counts:counts(done),fabrication_ids:['episode-fake']}]});
          const root=item(a,'Le Glow-up de Pêchette',1,3),child=item(b,'Le jus acide',2,0),other=item(c,'Un vieux test',1,6);
          child.active=true;root.variants.push({language:'English',counts:counts(1),fabrication_ids:['episode-english']});
          let data={revision:0,unreadable:0,groups:[{id:a,title:'GLOW UP',favorite:false,items:[root,child]},{id:c,title:'Autre histoire',favorite:false,items:[other]}]};
          window.PanelForgeStories={current:()=>current,canSwitch:()=>true,refreshList:async()=>{},createNew:()=>{current=null;},open:async id=>{opens.push(id);current={project_id:id};}};
          window.PanelForgeEpisodes={prepareLibraryNavigation:async()=>{},openFromLibrary:async(...args)=>opens.push(args)};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options.method||'GET']);
            if(url==='/api/stories/library')return structuredClone(data);
            if(options.method!=='PATCH')throw new Error('Unexpected action '+url);
            const body=JSON.parse(options.body);if(body.expected_revision!==data.revision)throw new Error('Conflict');
            const id=url.split('/').at(-1);
            if(url.includes('/groups/'))Object.assign(data.groups.find(g=>g.id===id),body);
            else Object.assign(data.groups.flatMap(g=>g.items).find(i=>i.project_id===id),body);
            data.revision++;return structuredClone(data);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(v,m)=>{if(!v)throw new Error(m);},el=id=>document.getElementById('sl-'+id),settle=()=>new Promise(r=>setTimeout(r,60));
            const action=key=>[...el('list').querySelectorAll('[data-focus-key]')].find(n=>n.dataset.focusKey===key);
            document.getElementById('story-library-open').click();await settle();
            check(document.getElementById('story-library').open,'library opens');
            check(el('list').textContent.includes('Ép. 02')&&el('list').textContent.includes('Vidéos 3/6'),'episode prefix and current counts');
            action('favorite:'+a).click();await settle();check(data.groups[0].favorite,'favorite saved');
            el('filter').value='favorites';el('filter').dispatchEvent(new Event('change'));
            check(!el('list').textContent.includes('Un vieux test'),'favorites filter');
            const lang=action('language:'+a);lang.value='English';lang.dispatchEvent(new Event('change'));
            check(el('list').textContent.includes('Vidéos 1/6'),'languages remain in the same episode with independent counts');
            el('search').value='pechette';el('search').dispatchEvent(new Event('input'));
            check(el('list').textContent.includes('Pêchette')&&!el('list').textContent.includes('Le jus acide'),'accent tolerant search');
            el('search').value='';el('search').dispatchEvent(new Event('input'));
            check(action('trash:'+b).disabled,'active work cannot be removed');
            action('trash:'+a).click();await settle();check(root.trashed&&!el('undo-bar').hidden,'soft trash with undo');
            el('filter').value='trash';el('filter').dispatchEvent(new Event('change'));
            check(action('restore:'+a)&&!action('open:'+a),'trash only offers restore');
            el('undo').click();await settle();check(!root.trashed&&el('empty').hidden===false,'undo restores the entry');
            el('filter').value='all';el('filter').dispatchEvent(new Event('change'));
            action('organize:'+a).click();el('group').value=c;el('number').value='7';el('editor').requestSubmit();await settle();
            check(root.group_id===c&&root.episode_number===7,'explicit organization action');
            action('rename:'+a).click();el('title').value='GLOW UP – Saison 1';el('editor').requestSubmit();await settle();
            check(data.groups[0].title==='GLOW UP – Saison 1','series title edited without changing episode title');
            check(root.title==='Le Glow-up de Pêchette','narrative title preserved');
            el('close').click();
            check(calls.every(([url])=>url.startsWith('/api/stories/library')),'browsing and organizing never call writing or generation');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre><label id="story-library-label"></label>'
                '<button id="story-library-open" hidden></button><select id="story-projects"></select>'+markup
                +'<script>'+setup+'</script><script>'+(STATIC/'story-library.js').read_text(encoding='utf8')
                +'</script><script>'+scenario+'</script>')
        self.run_browser(browsers[-1], html)
