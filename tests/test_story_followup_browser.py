"""User-run UI regression; isolated page, fake API, no LLM or running Lab."""
from pathlib import Path
import os
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class StoryFollowupBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_saved_chat_manual_direction_and_explicit_handoff(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<dialog id="story-followup"' + index.split('<dialog id="story-followup"', 1)[1].split('</dialog>', 1)[0] + '</dialog>'
        setup = r"""
        localStorage.clear();
        const source={project_id:'story-parent',title:'La preuve',version:4,document:{selected_episode_id:null}};
        const models=[{id:'local::other',label:'Autre modèle',source:'local'},{id:'local::qwen',label:'Qwen',source:'local'}];
        let saved={id:'followup-fixture',revision:1,source_changed:false,source_story_id:source.project_id,
          context:{source_label:'La preuve',next_unit:null,next_written:false},model_id:'',turns:[],job:null,result:null,
          direction:{start:'',beats:'',ending:'',constraints:''},settings:{dialogue_language:'French',workflow_mode:'manual',
            scene_count:6,clip_seconds:10,target_seconds:60,architect_model_id:'local::other',writer_model_id:'local::other'}};
        let delivered=null, requestLog=[],pending=null;
        window.PanelForgeLabCore={async request(url,options){
          const body=options?.body?JSON.parse(options.body):null;
          const method=options?.method||'GET'; requestLog.push({url,method,body});
          if(url.endsWith('/followup'))return structuredClone(saved);
          if(url.endsWith('/models'))return {models};
          if(url.endsWith('/messages')){
            pending=body; saved.turns.push({role:'user',text:body.instruction||'Propose-moi une suite'});
            saved.job={status:'running',request_id:body.request_id};saved.revision++;return structuredClone(saved);
          }
          if(url.endsWith('/refresh')){saved.source_changed=false;saved.revision++;return structuredClone(saved);}
          if(url.endsWith('/commit')){
            saved.result={project_id:'story-child'};saved.revision++;
            return {draft:structuredClone(saved),project:{project_id:'story-child'}};
          }
          if(method==='PUT'){
            if(body.expected_revision!==saved.revision)throw new Error('revision conflict');
            saved={...saved,direction:body.direction,model_id:body.model_id,settings:body.settings,revision:saved.revision+1};
            return structuredClone(saved);
          }
          if(method==='GET'){
            if(pending){
              if(pending.automatic)saved.direction={start:'Citronito possède la preuve.',beats:'Il ouvre le placard.',ending:'Les colis sont retrouvés.',constraints:'Deux personnages.'};
              saved.turns.push({role:'assistant',text:'Une suite claire. <img src=x onerror=alert(1)>'});
              saved.job={status:'succeeded'};saved.revision++;pending=null;
            }
            return structuredClone(saved);
          }
          throw new Error('Unexpected request '+method+' '+url);
        }};
        const options={project:source,models,architect:'local::other',writer:'local::other',onWritten:p=>{delivered=p;}};
        """
        scenario = r"""
        (async()=>{try {
          const e=id=>document.getElementById('sf-'+id), dialog=document.getElementById('story-followup');
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const settle=ms=>new Promise(r=>setTimeout(r,ms||100));
          const change=(id,value)=>{e(id).value=value;e(id).dispatchEvent(new Event('input'));};
          await window.PanelForgeStoryFollowup.open(options);
          check(dialog.open,'preparation opens');
          check(e('model').value==='local::qwen','Qwen is selected by default');
          check(!requestLog.some(r=>r.url.endsWith('/messages')||r.url.endsWith('/commit')),'opening does not generate anything');
          change('beats','Mon orientation manuelle');change('ending','Conserver une fin ouverte');
          change('message','Pourquoi cette fin ?');e('chat-form').dispatchEvent(new Event('submit',{cancelable:true}));
          await settle(1500);
          check(saved.direction.beats==='Mon orientation manuelle','manual changes saved before chat');
          check(e('beats').value==='Mon orientation manuelle','question preserves direction');
          check(!document.querySelector('#sf-turns img'),'model content is rendered as text');
          check(!delivered&&!requestLog.some(r=>r.url.endsWith('/commit')),'chat does not start writing');
          e('close').click();await settle();check(!dialog.open,'close works');
          await window.PanelForgeStoryFollowup.open(options);
          check(e('beats').value==='Mon orientation manuelle','direction survives reopening');
          check(e('turns').textContent.includes('Pourquoi cette fin'),'chat survives reopening');
          e('suggest').click();await settle(1500);
          check(e('ending').value==='Les colis sont retrouvés.','one automatic proposal updates card');
          check(requestLog.filter(r=>r.url.endsWith('/messages')).length===2,'one call per exchange');
          e('close').click();await settle();saved.source_changed=true;
          await window.PanelForgeStoryFollowup.open(options);
          check(!e('source-warning').hidden&&e('write').disabled,'changed source requires acknowledgement');
          e('refresh-source').click();await settle();
          check(e('source-warning').hidden&&e('ending').value==='Les colis sont retrouvés.','refresh keeps direction');
          e('write').click();e('write').click();await settle();
          check(delivered?.project_id==='story-child','explicit button opens created episode');
          check(requestLog.filter(r=>r.url.endsWith('/commit')).length===1,'double click produces one handoff');
          check(source.version===4,'source snapshot unchanged');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre><style>'
                + (STATIC / 'story-followup.css').read_text(encoding='utf-8') + '</style>' + markup
                + '<script>' + setup + '</script><script>'
                + (STATIC / 'story-followup.js').read_text(encoding='utf-8') + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)


if __name__ == '__main__':
    unittest.main()
