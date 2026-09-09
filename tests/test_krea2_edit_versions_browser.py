"""Browser contract for resume/navigation with fake local responses only."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/panelforge/features/lab/static"


class EditVersionsBrowserTest(unittest.TestCase):
    def test_resume_preserves_drafts_restores_selected_settings_and_navigates_history(self):
        browsers = list((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win/chrome.exe"))
        browsers += list((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("Chromium local non installé")
        edit = (STATIC / "krea2-edit-lab.js").read_text(encoding="utf-8")
        functions = ""
        for start, end in (
            ("  async function loadSources(", "  function setMessage("),
            ("  function projectStages(", "  function activeProjects("),
            ("  function assistanceVersionFor(", "  function renderLoras("),
            ("  function applyWorkflowDefaults(", "  function renderSettingsComplete("),
            ("  async function buildPrompt(", "  async function renderAttempt("),
            ("  async function openVersion(", "  async function restartStage("),
        ):
            functions += start + edit.split(start, 1)[1].split(end, 1)[0]
        script = r"""
        (async () => { try {
          const check = (condition, message) => { if (!condition) throw new Error(message); };
          const accepted = {attempt_id:'accepted', status:'succeeded', settings:{model_id:'chosen', megapixels:0.8, seed:'12', loras:[{name:'style',strength:0.4}]}};
          const later = {attempt_id:'later', status:'succeeded', settings:{model_id:'wrong', megapixels:1.2, seed:'99'}};
          const old = {source_id:'old', project_id:'old', stage_index:1, state:'advanced', accepted_attempt_id:'accepted',
            filename:'tree.png', metadata:{}, generated_prompt:'chosen prompt', attempts:[accepted,later]};
          const future = {...old, source_id:'old-next', stage_index:2, state:'pending', accepted_attempt_id:null, attempts:[]};
          const resumed = {...old, source_id:'new', project_id:'new', state:'pending', accepted_attempt_id:null, resume_attempt_id:'accepted'};
          let versions = [{project_id:'old', family_id:'old', number:1, status:'active'},
            {project_id:'new', family_id:'old', number:2, status:'draft', resumed_stage_index:1}];
          const state = {sources:[old,future], source:old, versions:[], busy:false, contextEpoch:0, resumeRequests:new Map(),
            sourceListEpoch:0, backlogProjectIds:[], backlogTotal:0, backlogExpanded:false, backlogLoading:false,
            drafts:new Map([['other',{prompt:'protected'}]]), assistanceChoices:new Map(),
            spec:{recipe:{version:'0.2.0'},defaults:{},workflows:[{version:'0.2.0',defaults:{model_id:'base-turbo',ref_boost:4,steps:10}}]}, feedbackAttemptId:'later'};
          const input = (value='') => ({value, dataset:{}, closest:()=>document.body});
          const label = document.createElement('label'), selector = document.createElement('select'); label.append(selector);
          const assistance = document.createElement('select');
          assistance.innerHTML='<option value="3.0.0">V3</option><option value="2.0.0">V2</option><option value="1.0.0" hidden>V1</option>';
          const elements = {version:selector, versionNote:document.createElement('small'), assistanceVersion:assistance, prompt:input('unsent'), instruction:input(),
            promptLanguage:input('en'), llm:input('fake'), workflow:input('0.2.0'), projectName:input(), stepName:input()};
          const maskDrafts = new Map([['old','mask pixels']]);
          const retouchEditor = {saving:false, close:()=>{}};
          const closeUpscale = () => {};
          const rememberRenderSettings = () => {}, isFireRed = () => false;
          const startPolling = () => {};
          let settings = {}, fail = true, calls = [], message = '';
          const renderSettings = () => settings, applyRenderSettings = value => {settings=value;};
          const latestAttempt = source => source.attempts.at(-1), activeAttempt = () => null;
          const defaultProjectName = () => 'Tree', defaultStepName = () => 'Opening', randomSeed = () => 'random';
          const renderBacklog = () => {}, sourceOf = payload => payload.source, setMessage = value => {message=value;};
          const render = () => renderVersions();
          const request = async (url, options) => {
            if (url.endsWith('/resume')) {
              calls.push(JSON.parse(options.body).request_id);
              if (fail) throw new Error('offline');
              return {source:resumed,versions};
            }
            if (url.endsWith('/projects/old')) return {sources:[old,future],versions};
            if (url.endsWith('/projects/new')) return {sources:[resumed],versions};
            if (url.includes('/sources?')) {
              const query = new URL(url, 'http://fixture').searchParams;
              check(query.get('project_limit')==='3', 'initial backlog requests only three projects');
              check(query.get('project_id')==='new', 'resume loads the entire new project');
              return {sources:[old,future,resumed],versions,backlog_project_ids:['new'],project_count:1};
            }
            throw new Error('unexpected request '+url);
          };
          __FUNCTIONS__
          check(assistanceVersionFor(old)==='3.0.0', 'new stages default to V3');
          check(assistanceVersionFor({...old,revisions:[{assistance_version:'2.0.0'}]})==='2.0.0', 'existing V2 is restored');
          check(assistanceVersionFor({...old,revisions:[{}]})==='1.0.0', 'legacy revision is not silently relabeled');
          await resumeStage();
          check(state.source === old && state.drafts.has('other') && maskDrafts.get('old') === 'mask pixels', 'failed resume preserves old work');
          fail = false; await resumeStage();
          check(calls.length === 2 && calls[0] === calls[1], 'retry reuses identity');
          check(state.source.source_id === 'new' && selector.value === 'new', 'opens new draft version');
          check(settings.model_id === 'chosen' && settings.megapixels === 0.8 && settings.seed === '12', 'restores accepted settings, not later unused attempt');
          check(settings.loras[0].name === 'style' && state.feedbackAttemptId === 'accepted', 'preserves LoRA and exact feedback');
          check(state.drafts.get('old').prompt === 'unsent' && maskDrafts.has('old'), 'old drafts remain separate');
          const initialPrompt = elements.prompt.value, initialSettings = JSON.stringify(settings), callCount = calls.length;
          assistance.value='2.0.0'; changeAssistanceVersion();
          check(elements.prompt.value===initialPrompt && JSON.stringify(settings)===initialSettings && calls.length===callCount, 'version switch does not rewrite or generate');
          check(selector.options.length === 2 && !label.hidden, 'versions available in one selector');
          settings.megapixels = 2.1; elements.prompt.value = 'draft correction';
          await openVersion('old'); await openVersion('new');
          check(settings.megapixels === 2.1 && elements.prompt.value === 'draft correction', 'navigation preserves unsaved working settings');
          check(assistance.value==='2.0.0', 'navigation preserves chosen assistance');
          const submitted = [];
          const reasoningTrace = {begin:()=>{},finish:()=>{},handle:()=>{},streamUrl:url=>url};
          const refreshCurrent = async () => {};
          const core = {createLlmOutcomeTone:()=>({start:()=>{},success:()=>{},failure:()=>{}}),
            streamRequest:async (url, options, callback) => {
              const body=JSON.parse(options.body); submitted.push(body);
              callback({source:{...state.source,prompt_status:'ready',generated_prompt:'accepted '+body.assistance_version}});
            }};
          for (const version of ['2.0.0','3.0.0']) {
            assistance.value=version; changeAssistanceVersion(); elements.instruction.value='Replace the paint with soil';
            await buildPrompt();
            check(submitted.at(-1).assistance_version===version && elements.prompt.value==='accepted '+version, 'selected writer reaches request and accepted result');
          }
          const originalPrompt=elements.prompt.value;
          core.streamRequest=async()=>{throw new Error('offline');};
          elements.instruction.value='Unsent correction'; await buildPrompt();
          check(elements.prompt.value===originalPrompt && elements.instruction.value==='Unsent correction' && assistance.value==='3.0.0', 'failed exchange keeps prompt, instruction and chosen version');
          const beforeBase={...settings}, requestCount=calls.length;
          applyWorkflowDefaults();
          check(settings.model_id==='base-turbo' && settings.ref_boost===4 && settings.steps===10 && settings.loras.length===0, 'base settings use selected workflow');
          check(settings.megapixels===beforeBase.megapixels && settings.aspect_ratio===beforeBase.aspect_ratio && settings.seed===beforeBase.seed && elements.prompt.value===originalPrompt, 'base settings preserve MP, ratio, seed and prompt');
          check(calls.length===requestCount, 'base settings do not generate');
          versions = versions.map(v => ({...v,status:v.number===1?'historical':'active'}));
          await openVersion('old');
          check(!isEditable() && elements.versionNote.textContent.includes('lecture seule'), 'historical pending stage becomes read only');
          check(state.sources.some(s=>s.source_id==='old-next'), 'future old stage remains consultable');
          document.getElementById('result').textContent='PASS';
        } catch(error) { document.getElementById('result').textContent='FAIL: '+error.stack; } })();
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
