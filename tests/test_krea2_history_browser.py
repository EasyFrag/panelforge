"""User-run browser checks of real launch/history functions with fake transport."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class Krea2HistoryBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def scenario(self, scenario):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
            if chrome.is_file():
                browsers = [chrome]
        if not browsers:
            self.skipTest("local Chromium or Chrome not installed")
        source = (STATIC / "krea2-assisted-lab.js").read_text(encoding="utf-8")
        sections = (
            ("  function renderHistory()", "  async function loadSpec("),
            ("  function scheduleHistory()", "  function scrollToGallery()"),
            ("  async function initialize()", "  async function refreshAllResources()"),
            ("  function validateNewProjectDraft(", "  function applyNewProjectDraft("),
            ("  async function createAndRenderProject(", "  async function createProject(event)"),
            ("  async function sendChat(", "  async function convertPromptLanguage()"),
            ("  async function renderAttempt()", "  async function startPreparedAttempt("),
            ("  async function loadRenderQueue()", "  function clearGuidance()"),
        )
        actual = "\n".join(source[source.index(start):source.index(end, source.index(start))] for start, end in sections)
        bootstrap = r"""
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const settle=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setTimeout(r,0));};
          let visibility='visible',ignoreAbort=false,failEssentials=false,holdRender=true,finishRender;
          Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>visibility});
          const elements={workspace:document.getElementById('workspace'),history:document.getElementById('history'),historyEmpty:document.getElementById('empty'),
            llm:{value:'local'},name:document.getElementById('name'),message:{value:''},messageState:{textContent:''},prompt:{value:'Prepared prompt'},
            revisionLlm:{value:'local'},promptLanguage:{value:'en'},model:{value:'Krea2/a'},ratio:{value:'9:16'},megapixels:{value:'0.8'},seed:{value:'0'},workflow:{value:'krea2-sampling@1.0.0'}};
          const state={initialized:false,initializing:null,busy:false,project:null,projects:[],navigationSerial:0,renderQueue:{items:[]}};
          let historyRequest=null,historyController=null,historyTimer=null,historySerial=0,historyDirty=true;
          const historyVisible=()=>!elements.workspace.hidden&&document.visibilityState==='visible';
          const historyCards=new Map(),historyReads=[];
          let creates=0,chats=0,enqueues=0,queueReads=0,newMessage='',historyMessage='';
          const setHistoryMessage=(message='')=>{historyMessage=message;};
          const setNewMessage=(message='')=>{newMessage=message;};
          const setMessage=(message='')=>{elements.messageState.textContent=message;};
          const setBusy=value=>{state.busy=value;if(!value)scheduleHistory();};
          const restagingEditor={saving:false};
          const preferredNewProjectLlm=()=>({id:'local'});
          window.PanelForgeModelPicker={select:(element,value)=>element.value=value};
          const clearGuidance=()=>{},resolveGuidance=async()=>null,renderStatus=()=>{},stopPolling=()=>{},schedulePoll=()=>{},openProject=()=>{};
          const validateSamplingInputs=()=>true,selectedLoras=()=>[],readSampling=()=>({});
          const renderProject=project=>{state.project=project;};
          const reasoningTrace={begin(){},finish(){},handle(){},streamUrl:url=>url};
          const core={createLlmOutcomeTone:()=>({start(){},success(){},failure(){}}),streamRequest:async(url,options,event)=>{chats++;event({project:{...state.project,current_prompt:'Prepared prompt'}});}};
          const loadSpec=async()=>{if(failEssentials)throw new Error('catalog offline');state.spec={llm_models:[{id:'local'}]};};
          const refreshCatalog=loadSpec,loadPresets=async()=>{};
          const request=async(url,options={})=>{
            if(url.includes('/project-summaries?'))return new Promise((resolve,reject)=>{
              historyReads.push({resolve,reject,signal:options.signal});
              if(!ignoreAbort)options.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true});
            });
            if(url.endsWith('/render-queue')){queueReads++;return new Promise(()=>{});}
            if(url.endsWith('/projects')&&options.method==='POST'){
              creates++;return {project:{project_id:'project-'+creates,name:options.body.get('name'),intention:options.body.get('intention'),active_branch_id:'main',model_id:'local',attempts:[]}};
            }
            if(url.includes('/attempts?enqueue=true')){
              enqueues++;const project={...state.project,attempts:[{attempt_id:'attempt-'+enqueues,index:enqueues,status:'queued'}]};
              if(holdRender)await new Promise(resolve=>finishRender=resolve);
              return {project};
            }
            throw new Error('Unexpected '+url);
          };
          const draft={name:'New project',intention:'A landscape',model_id:'local',assistance_recipe_version:'3.0.0',prompt_language:'en',local_inspiration_enabled:false};
        """
        script = "(async()=>{try{" + bootstrap + actual + scenario + "document.getElementById('result').textContent='PASS';}catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();"
        markup = '<meta charset="utf-8"><pre id="result">PENDING</pre><div id="workspace"><ul id="history"></ul><p id="empty"></p><input id="name" value="Draft untouched"></div>'
        self.run_browser(browsers[-1], markup + '<script>' + script + '</script>')

    def test_slow_or_failed_history_and_queue_display_never_gate_a_valid_launch(self):
        self.scenario(r"""
          check(await initialize(),'minimal initialization completes');await settle();
          check(historyReads.length===1&&queueReads===1,'display reads can remain pending');
          const launch=createAndRenderProject(draft);await settle();
          check(creates===1&&chats===1&&enqueues===1,'create -> prompt -> enqueue bypasses pending history');
          check(state.busy,'enqueue acknowledgement keeps controls busy');
          check(await createAndRenderProject(draft)===false&&creates===1,'second click cannot create while enqueue is pending');
          finishRender();check(await launch,'launch acknowledged');await settle();
          historyReads[0].resolve({projects:[]});await settle();
          check(historyReads.length===2,'mutations coalesce into one fresh history read');
          historyReads[1].reject(new Error('history offline'));await settle();
          check(historyMessage.includes('history offline'),'history failure stays in its own panel');
          check(elements.messageState.textContent.includes('ajouté à la file'),'history error does not replace launch receipt');
          holdRender=false;
          check(await createAndRenderProject(draft),'valid launch continues after history failure');
          check(creates===2&&chats===2&&enqueues===2,'failed history causes no retry or duplicate command');
          visibility='hidden';historyVisibilityChanged();await settle();
          const reads=historyReads.length;
          check(await createAndRenderProject(draft),'command in a background tab still completes');await settle();
          check(historyReads.length===reads,'background launch does not read history');
          failEssentials=true;state.initialized=false;
          check(!await initialize(),'required catalog failure still prevents readiness');
          check(!await createAndRenderProject(draft)&&creates===3,'missing essentials block creation, not just the button');
          check(newMessage.length>0,'required-resource failure is visible');
        """)

    def test_history_deduplicates_ignores_stale_reads_and_preserves_nodes_and_drafts(self):
        self.scenario(r"""
          state.initialized=true;
          const image='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
          const rows=[{project_id:'a',name:'A',turn_count:4,render_count:1,preview_url:image},{project_id:'b',name:'B',turn_count:2,render_count:0,preview_url:null}];
          const first=loadHistory(),duplicate=loadHistory();
          check(first===duplicate&&historyReads.length===1,'one shared in-flight read');
          historyReads[0].resolve({projects:rows});await first;await settle();
          const node=elements.history.firstElementChild,img=node.querySelector('img');
          const again=loadHistory();historyReads[1].resolve({projects:structuredClone(rows)});await again;
          check(elements.history.firstElementChild===node&&node.querySelector('img')===img,'unchanged history keeps decoded image and row nodes');
          check(elements.name.value==='Draft untouched','history refresh never resets a form draft');
          const stale=loadHistory();setBusy(true);invalidateHistory();
          historyReads[2].resolve({projects:[{...rows[0],name:'Old response'}]});await stale;
          check(elements.history.firstElementChild.textContent.startsWith('A'),'older response cannot overwrite history after mutation');
          setBusy(false);await settle();
          historyReads[3].resolve({projects:[rows[1]]});await settle();
          check(elements.history.children.length===1&&elements.history.firstElementChild.textContent.startsWith('B'),'fresh history removes obsolete rows');
          ignoreAbort=true;const late=loadHistory();
          visibility='hidden';historyVisibilityChanged();
          check(historyReads[4].signal.aborted,'hiding cancels only the history GET');
          const count=historyReads.length;
          visibility='visible';historyVisibilityChanged();
          historyReads[4].resolve({projects:[{...rows[0],name:'Hidden stale'}]});await late;await settle();
          check(historyReads.length===count+1,'return schedules one fresh read');
          historyReads[5].resolve({projects:rows});await settle();
          check(elements.history.firstElementChild.textContent.startsWith('A'),'hidden stale response was discarded');
          const thumbnail=elements.history.querySelector('img');thumbnail.dispatchEvent(new Event('error'));
          check(!elements.history.querySelector('img')&&elements.history.children.length===2,'failed thumbnail leaves history rows usable without downloading original');
          visibility='hidden';historyVisibilityChanged();await settle();
          const before=historyReads.length;await loadHistory();
          check(historyReads.length===before,'explicit history refresh does no work while browser is hidden');
        """)
