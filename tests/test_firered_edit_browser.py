"""Real editor control functions, fake responses, no renderer or LLM."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class FireRedBrowserTest(unittest.TestCase):
    def test_switch_reuse_hydration_and_request_preserve_engine_settings(self):
        browsers = list((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win/chrome.exe"))
        browsers += list((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("Chromium local non installé")
        edit = (STATIC / "krea2-edit-lab.js").read_text(encoding="utf-8")
        functions = ""
        for start, end in (
            ("  function isFireRed(", "  async function initialize("),
            ("  function assistanceVersionFor(", "  function renderLoras("),
            ("  function reuseAttempt(", "  async function promoteAttempt("),
            ("  async function renderAttempt(", "  function startPolling("),
        ):
            functions += start + edit.split(start, 1)[1].split(end, 1)[0]
        script = r"""
        (async () => { try {
          const check=(value, message)=>{if(!value)throw new Error(message);};
          const input=(value='')=>{const el=document.createElement('input');el.value=value;return el;};
          const select=values=>{const el=document.createElement('select');for(const value of values)el.add(new Option(value,value));return el;};
          const workspace=document.createElement('div'); document.body.append(workspace);
          const elements={workspace,engine:select(['krea2','firered']),fireRedMode:select(['lightning','standard']),
            fireRedCfg:input(),megapixels:input(),steps:input(),seed:input(),refBoost:input(),
            model:select(['turbo','old']),ratio:input(),workflow:select(['0.2.0','0.1.0']),
            assistanceVersion:select(['3.0.0','2.0.0','1.0.0']),fixedNote:document.createElement('small'),
            prompt:input('Keep my prompt'),instruction:input('Unsent edit'),promptLanguage:input('en'),
            llm:input('fake'),projectName:input(),stepName:input()};
          const label=document.createElement('label');label.append(elements.assistanceVersion);workspace.append(label);
          const note=document.createElement('small');note.id='krea2-edit-assistance-note';workspace.append(note);
          const boostLabel=document.createElement('span');boostLabel.id='krea2-edit-ref-boost-label';workspace.append(boostLabel);
          const $=id=>document.getElementById(id);
          const kreaGroup=document.createElement('div'),fireGroup=document.createElement('div');
          kreaGroup.dataset.editEngine='krea2';fireGroup.dataset.editEngine='firered';workspace.append(kreaGroup,fireGroup);
          const defaults={model_id:'turbo',megapixels:1,aspect_ratio:'square',ref_boost:4,steps:10};
          const fire={id:'firered.image_edit',engine:'firered',version:'0.1.0',defaults:{model_id:'FireRed',
            megapixels:1,mode:'lightning',steps:8,cfg:1,modes:{lightning:{steps:8,cfg:1},standard:{steps:40,cfg:4}}}};
          const source={source_id:'stage',project_id:'stage',filename:'source.png',state:'pending',metadata:{},attempts:[],revisions:[]};
          const state={source,sources:[source],renderEngine:'krea2',engineDrafts:new Map(),drafts:new Map(),assistanceChoices:new Map(),
            loraSlots:[],busy:false,contextEpoch:0,feedbackAttemptId:null,spec:{defaults,fixed:{},
              recipe:{id:'krea2.identity_edit',version:'0.2.0'},workflows:[
                {id:'krea2.identity_edit',engine:'krea2',version:'0.2.0',defaults},
                {id:'krea2.identity_edit',engine:'krea2',version:'0.1.0',defaults},fire]}};
          const masks=new Map([['stage','painted pixels']]);
          const retouchEditor={saving:false,close:()=>{}};
          const closeUpscale=()=>{},renderLoras=()=>{},syncModelPicker=()=>{},setMessage=()=>{},startPolling=()=>{};
          const ensureOption=(el,value)=>{if(![...el.options].some(o=>o.value===value))el.add(new Option(value,value));};
          const randomSeed=()=> '9007199254740993',isEditable=(value=state.source)=>value?.state==='pending';
          const projectStages=()=>[state.source],activeAttempt=()=>null,latestAttempt=(value=state.source)=>value.attempts.at(-1);
          const defaultProjectName=()=> 'Project',defaultStepName=()=> 'Edit',sourceOf=value=>value.source;
          const render=()=>renderEngineControls();
          const calls=[];
          const request=async (url,options)=>{
            calls.push({url,body:options.body?JSON.parse(options.body):null});
            if(url.endsWith('/attempts'))return {source:{...state.source,attempts:[{attempt_id:'new'}]}};
            if(url.endsWith('/start'))return {source:state.source};
            throw new Error('Unexpected request');
          };
          __FUNCTIONS__
          applyRenderSettings({...defaults,engine:'krea2',workflow_version:'0.1.0',model_id:'old',
            megapixels:2.1,ref_boost:25.5,seed:'18446744073709551615',loras:[{name:'style',strength:0.7}]});
          const original=JSON.stringify(renderSettings());
          elements.engine.value='firered';switchEngine();
          check(renderSettings().megapixels===1 && renderSettings().steps===8 && renderSettings().cfg===1,'FireRed starts at 1 MP / 8 / 1');
          check(kreaGroup.hidden && !fireGroup.hidden && label.hidden,'engine-specific controls only');
          check(elements.prompt.value==='Keep my prompt' && elements.instruction.value==='Unsent edit' && masks.get('stage')==='painted pixels','switch preserves creative work');
          check(calls.length===0,'switch makes no API or LLM call');
          elements.fireRedMode.value='standard';changeFireRedMode();
          check(renderSettings().steps===40 && renderSettings().cfg===4,'standard defaults');
          elements.megapixels.value='2.5';elements.fireRedCfg.value='0';elements.steps.value='31';
          check(renderSettingsComplete(),'CFG zero is allowed');
          const custom=JSON.stringify(renderSettings());
          elements.engine.value='krea2';switchEngine();
          check(JSON.stringify(renderSettings())===original,'KREA2 recipe, LoRAs and Ref boost restored');
          check(!kreaGroup.hidden && fireGroup.hidden && !label.hidden,'KREA2 controls restored');
          elements.engine.value='firered';switchEngine();
          check(JSON.stringify(renderSettings())===custom,'FireRed draft restored independently');
          await renderAttempt();
          const submitted=calls[0].body;
          check(submitted.engine==='firered' && submitted.workflow_id===fire.id && submitted.workflow_version==='0.1.0','full recipe identity sent');
          check(submitted.megapixels===2.5 && submitted.steps===31 && submitted.cfg===0 && submitted.mode==='standard','custom settings sent');
          check(!('ref_boost' in submitted) && !('loras' in submitted) && submitted.aspect_ratio==='source','KREA2 controls cannot leak');
          const previous={attempt_id:'old-fire',status:'succeeded',prompt:'Saved FireRed edit',workflow_id:fire.id,workflow_version:'0.1.0',
            settings:{engine:'firered',model_id:'FireRed',megapixels:1.7,steps:21,cfg:2,mode:'standard',seed:'123'}};
          reuseAttempt(previous);
          check(elements.prompt.value===previous.prompt && state.feedbackAttemptId==='old-fire' && renderSettings().steps===21,'reuse restores exact candidate');
          const imported={...source,source_id:'imported',project_id:'imported',recipe:{id:'krea2.identity_edit',engine:'krea2',version:'0.2.0'},
            metadata:{firered_settings:previous.settings},attempts:[]};
          state.sources.push(imported);openSource(imported,{hydrate:true});
          check(renderSettings().workflow_id===fire.id && renderSettings().workflow_version==='0.1.0','native FireRed metadata selects FireRed recipe despite new-source KREA2 default');
          check(renderSettings().megapixels===1.7 && renderSettings().mode==='standard','import retains settings');
          state.busy=true;elements.engine.value='krea2';switchEngine();
          check(state.renderEngine==='firered' && elements.engine.value==='firered','busy switch rejected');
          state.busy=false;
          state.spec.workflows.push({id:'krea2.identity_edit',engine:'krea2',version:'0.3.0',requires_subject_reference:true,defaults});
          elements.workflow.add(new Option('Scene + subject','0.3.0'));
          const restage={...source,source_id:'restage',project_id:'restage',subject_reference:{asset_id:'subject'},
            recipe:{id:'krea2.identity_edit',engine:'krea2',version:'0.3.0'},metadata:{prompt:'Place her in scene 1'},attempts:[]};
          state.sources.push(restage);openSource(restage,{hydrate:true});
          check(elements.workflow.value==='0.3.0'&&state.renderEngine==='krea2','restaging opens the two-input recipe');
          check(elements.engine.disabled && [...elements.workflow.options].filter(o=>!o.hidden).map(o=>o.value).join()==='0.3.0','restaging cannot silently use FireRed or a single-image graph');
          elements.engine.value='firered';switchEngine();check(state.renderEngine==='krea2','programmatic engine change also rejected');
          openSource(source,{hydrate:true});
          check(!elements.engine.disabled,'regular workshop still allows its engines');
          check([...elements.workflow.options].find(o=>o.value==='0.3.0').hidden,'two-input recipe hidden without subject');
          document.getElementById('result').textContent='PASS';
        } catch(error) {document.getElementById('result').textContent='FAIL: '+error.stack;} })();
        """
        script = script.replace("__FUNCTIONS__", functions)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            page = directory / "test.html"
            page.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre><script>' + script + '</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--virtual-time-budget=5000", f"--user-data-dir={directory / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
