"""User-run browser regression for real Assisted sampling controls; no network."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from panelforge.domain.krea2_sampling import sampling_spec


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


def browser_fixture():
    source = (STATIC / "krea2-assisted-lab.js").read_text(encoding="utf-8")
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    start = page.index('<div class="krea2-assisted-sampling">')
    markup = page[start:page.index('<div class="section-title"><h3>LoRA</h3>', start)]
    controls = source[source.index("  const samplingPasses ="):source.index("  const resourceUi =")]
    restore = source[source.index("  function loadAttemptSettings("):source.index("  function draftText(")]
    restore_state = source[source.index("  function restoreRenderState("):source.index("  function renderBranches(")]
    enqueue = source[source.index("  async function renderAttempt("):source.index("  async function startPreparedAttempt(")]
    script = r"""
      (async () => { try {
        const check = (ok, why) => { if (!ok) throw new Error(why); };
        const $ = id => document.getElementById(id);
        const elements = {samplingPreset: $('krea2-assisted-sampling-preset'),
          samplingSummary: $('krea2-assisted-sampling-summary'), samplingDetails: $('krea2-assisted-sampling-details'),
          workflow: Object.assign(document.createElement('select'), {innerHTML:'<option value="krea2-sampling@1.0.0">Current</option>'}),
          workflowSummary: document.createElement('small'), samplingFirstNote: document.createElement('small'),
          samplingSecondNote: document.createElement('small'),
          prompt: {value: 'A studio photo'}, seed: {value:'0'}, megapixels: {value:'2.1'},
          model: document.createElement('select'), ratio: document.createElement('select'),
          promptLanguage: {value:'en'}};
        const ensureMissingOption = (select, value) => {
          if (![...select.options].some(o => o.value === value)) { const o = document.createElement('option');
            o.value=value; o.textContent=value; select.append(o); }
        };
        const resourceUi = {syncModelPicker: () => {}}, renderLoraStack = () => {};
        const state = {spec: {sampling: __SPEC__, workflows:[{id:'krea2-sampling@1.0.0',recipe_id:'krea2-sampling',description:'Current',default_sampling_preset_id:'current'}]}, project: {project_id:'project',active_branch_id:'main'},
          busy:false, navigationSerial:0, loraSlots:[]};
        __CONTROLS__
        __RESTORE__
        __RESTORE_STATE__
        configureSampling(state.spec.sampling);
        check(elements.samplingPreset.options.length === 4, 'three presets and custom');
        check(!elements.samplingDetails.open, 'advanced closed initially');
        check(readSampling().first_pass.steps === 8 && readSampling().second_pass.steps === 2, 'historical default');
        elements.samplingPreset.value='finish_4'; elements.samplingPreset.dispatchEvent(new Event('change'));
        check(readSampling().second_pass.steps === 4 && readSampling().first_pass.sampler === 'er_sde', 'finish preset');
        elements.samplingPreset.value='moody_beta'; elements.samplingPreset.dispatchEvent(new Event('change'));
        check(readSampling().first_pass.sampler === 'euler_ancestral' && readSampling().second_pass.scheduler === 'beta', 'both Moody passes');
        samplingPasses[1].steps.value='5'; samplingPasses[1].steps.dispatchEvent(new Event('input'));
        samplingPasses[1].sampler.value='er_sde'; samplingPasses[1].sampler.dispatchEvent(new Event('change'));
        check(readSampling().preset_id === 'custom' && readSampling().first_pass.steps === 8, 'independent manual change');
        const manual = readSampling();
        configureSampling(state.spec.sampling);
        check(JSON.stringify(readSampling()) === JSON.stringify(manual), 'catalogue preserves custom draft');
        const stopPolling = () => {}, schedulePoll = () => {}, setMessage = () => {};
        const setBusy = value => {state.busy=value;};
        const selectedLoras = () => [];
        const renderProject = project => {state.project=project;};
        let submitted;
        const request = async (url, options) => {
          submitted=JSON.parse(options.body);
          return {project:{...state.project, attempts:[{index:1,status:'queued'}]}};
        };
        window.fetch = () => {throw new Error('unexpected network');};
        __ENQUEUE__
        await renderAttempt();
        check(JSON.stringify(submitted.sampling) === JSON.stringify(manual) && submitted.seed === '0'
          && submitted.workflow === 'krea2-sampling@1.0.0', 'enqueue snapshots family, both passes and seed zero');
        const attempt={prompt:'Saved photo', seed:'12', settings:{workflow:'krea2-sampling@1.0.0',model_id:'saved-model',aspect_ratio:'9:16',megapixels:1.2,loras:[],sampling:manual}};
        loadSampling(null); loadAttemptSettings(attempt);
        check(JSON.stringify(readSampling()) === JSON.stringify(manual) && elements.seed.value==='12', 'reuse restores sampling');
        restoreRenderState({render_settings:attempt.settings,render_seed:'12',current_prompt:'Saved photo'});
        check(JSON.stringify(readSampling()) === JSON.stringify(manual), 'reopen restores draft');
        loadAttemptSettings({...attempt,settings:{...attempt.settings,sampling:undefined}});
        check(readSampling().preset_id==='current' && readSampling().second_pass.steps===2, 'legacy restores default');
        loadSampling(manual); restoreRenderState({attempts:[],active_branch_id:'main'});
        check(readSampling().preset_id==='current', 'empty project does not inherit previous project');
        samplingPasses[0].steps.value=''; samplingPasses[0].steps.dispatchEvent(new Event('input'));
        configureSampling({...state.spec.sampling, marker:1});
        check(samplingPasses[0].steps.value==='', 'refresh preserves incomplete input');
        check(!validateSamplingInputs() && elements.samplingDetails.open, 'invalid steps shown before enqueue');
        document.getElementById('result').textContent='PASS';
      } catch (error) { document.getElementById('result').textContent='FAIL: '+error.stack; } })();
    """
    script = script.replace("__SPEC__", json.dumps(sampling_spec(), ensure_ascii=True))
    for key, value in {"__CONTROLS__": controls, "__RESTORE__": restore,
                       "__RESTORE_STATE__": restore_state, "__ENQUEUE__": enqueue}.items():
        script = script.replace(key, value)
    return markup, script


class Krea2AssistedSamplingBrowserTest(unittest.TestCase):
    def test_presets_custom_restore_and_submission(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        markup, script = browser_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            page = root / "sampling.html"
            page.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre>'+markup+'<script>'+script+'</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--virtual-time-budget=5000", f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
