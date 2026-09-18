"""User-run DOM fixture using real controls and model picker; fake HTTP only."""
import os
from pathlib import Path
import re
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class PromptWriterModelBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def browser(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        return browsers[-1]

    def test_h3_and_ref2v_use_the_requested_local_defaults_for_new_runs(self):
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>'
        for prefix in ("i2vd", "ref2vd"):
            controls = re.search(rf'<div id="{prefix}-writer-model-controls".*?</small>\s*</div>', index, re.S)
            self.assertIsNotNone(controls)
            html += (
                f'<section><select id="{prefix}-model"></select>'
                f'<input type="checkbox" data-llm-local-for="{prefix}-model" checked>'
                f'{controls.group()}</section>'
            )
        picker = (STATIC / "lab.js").read_text(encoding="utf-8").split("const ui = {};")[0]
        component = (STATIC / "prompt-writer-model.js").read_text(encoding="utf-8")
        scenario = """
        (() => { try {
          const check=(ok,message)=>{if(!ok)throw new Error(message);};
          const plan='local::unsloth/Qwen3.8-27B-GGUF';
          const writer='local::unsloth/gemma-4-31B-it-qat-GGUF';
          const models=[{id:'server-qwen',label:'Server Qwen',source:'server'},
            {id:plan,label:'unsloth/Qwen3.8-27B-GGUF',source:'local'},
            {id:writer,label:'unsloth/gemma-4-31B-it-qat-GGUF',source:'local'}];
          for(const prefix of ['i2vd','ref2vd']){
            const planner=document.getElementById(prefix+'-model');
            PanelForgeModelPicker.populate(planner,models,plan);
            const state={session:null,composition:null,busy:false,writerSaving:false};
            let controls;
            controls=PanelForgePromptWriterModel.create({prefix,state,planner,
              cookbook:()=>({supports_writer_model:true}),request:async()=>{},
              render:()=>controls.draw(),busy:()=>false,
              defaultModelId:writer,defaultEnabled:true});
            controls.populate(models); controls.draw();
            const host=document.getElementById(prefix+'-writer-model-controls');
            check(planner.value===plan,'Qwen local must be the planning default');
            check(host.querySelector('[data-writer="enabled"]').checked,'separate writer must start enabled');
            check(controls.value()===writer,'Gemma local must be the writer default');
            check(host.querySelector('[data-llm-local-for]').checked,'writer source must be local');
            controls.restore(null); controls.draw();
            check(controls.value()===null,'a historical run with no writer override remains unchanged');
            controls.resetDefault(); controls.draw();
            check(controls.value()===writer,'new run restores the requested default');
          }
          document.querySelector('#result').textContent='PASS';
        } catch(error) { document.querySelector('#result').textContent='FAIL: '+error.stack; } })();
        """
        self.run_browser(self.browser(), html + '<script>' + picker + '</script><script>' + component + '</script><script>' + scenario + '</script>')

    def test_independent_sources_persistence_retry_and_historical_visibility(self):
        browser = self.browser()
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        html = '<meta charset="utf-8"><style>' + (STATIC / "lab.css").read_text(encoding="utf-8") + '</style><pre id="result">PENDING</pre>'
        for prefix in ("i2vd", "ref2vd"):
            controls = re.search(rf'<div id="{prefix}-writer-model-controls".*?</small>\s*</div>', index, re.S)
            self.assertIsNotNone(controls)
            html += f'<section style="width:320px"><select id="{prefix}-model"></select><input type="checkbox" data-llm-local-for="{prefix}-model">' + controls.group() + '</section>'
        picker = (STATIC / "lab.js").read_text(encoding="utf-8").split("const ui = {};")[0]
        html += '<script>' + picker + '</script><script>' + (STATIC / "prompt-writer-model.js").read_text(encoding="utf-8") + '</script>'
        script = """
        (async () => { try {
          const check=(ok,message)=>{if(!ok)throw new Error(message);};
          for (const prefix of ['i2vd','ref2vd']) {
            const state={session:null,composition:null,busy:false,writerSaving:false};
            let recipe={supports_writer_model:true}, controls, fail=false;
            const requests=[];
            const host=document.getElementById(prefix+'-writer-model-controls');
            const planner=document.getElementById(prefix+'-model');
            const model=host.querySelector('select'), enabled=host.querySelector('[data-writer="enabled"]');
            const local=host.querySelector('[data-llm-local-for]');
            const primaryLocal=document.querySelector('[data-llm-local-for="'+prefix+'-model"]');
            const catalogue=[{id:'server-qwen',label:'Server Qwen'},
              {id:'local::qwen',label:'Qwen local'},{id:'local::gemma',label:'Gemma local'}];
            PanelForgeModelPicker.populate(planner,catalogue,'server-qwen');
            controls=PanelForgePromptWriterModel.create({prefix,state,planner,cookbook:()=>recipe,
              busy:()=>state.busy||state.writerSaving,render:()=>controls.draw(),
              request:async(url,options)=>{
                const body=JSON.parse(options.body); requests.push({url,...body});
                if(fail)throw new Error('offline');
                check(body.expected_writer_model_id===(state.composition.writer_model_id??null),'compare saved model');
                return {composition:{...state.composition,writer_model_id:body.writer_model_id}};
              }});
            controls.populate(catalogue); controls.draw();
            check(!host.hidden && !enabled.checked && controls.value()===null,'same model by default');
            check(host.querySelector('[data-writer="fields"]').hidden,'second picker collapsed');
            enabled.click(); local.click(); model.value='local::gemma'; model.dispatchEvent(new Event('change'));
            check(controls.value()==='local::gemma' && planner.value==='server-qwen' && !primaryLocal.checked,'independent local/server sources');
            check(requests.length===0,'draft changes do not create server work');
            const documents={beat_sheet:{approved_revision_id:'plan-1'},final_prompt:{active_revision_id:'prompt-1'}};
            state.session={id:prefix+'-session'};
            state.composition={supports_writer_model:true,writer_model_id:null,documents};
            await controls.save();
            check(requests.length===1 && state.composition.writer_model_id==='local::gemma','save selected writer');
            check(state.composition.documents===documents,'approved plan and prompt preserved');
            controls.restore(state.composition.writer_model_id); controls.populate(catalogue.slice(0,2)); controls.draw();
            check(model.value==='local::gemma' && model.selectedOptions[0].dataset.missing==='true','refresh never substitutes a missing saved model');
            controls.populate(catalogue);
            enabled.click(); await controls.save();
            check(controls.value()===null && state.composition.writer_model_id===null,'uncheck persists planner fallback');
            check(state.composition.documents===documents,'no plan regeneration');
            fail=true; enabled.click();
            try { await controls.save(); } catch (_) {}
            check(!state.writerSaving && !enabled.checked && host.querySelector('[data-writer="status"]').textContent.includes('offline'),'failed save restores previous selection');
            fail=false;
            controls.restore('local::gemma'); state.session=null; state.composition=null; controls.draw();
            check(controls.value()==='local::gemma','fork preserves explicit writer');
            recipe={supports_writer_model:false}; controls.draw();
            check(host.hidden && controls.value()===null && model.disabled && !model.required,'old recipes ignore hidden choice');
            recipe={supports_writer_model:true}; controls.restore(null); controls.draw();
            check(!enabled.checked && controls.value()===null,'new workshop resets opt-in');
            state.busy=true; controls.draw();
            check(enabled.disabled && model.disabled && local.disabled,'running calls lock model settings');
            check(host.scrollWidth<=host.clientWidth+1,'controls fit the narrow sidebar');
          }
          document.querySelector('#result').textContent='PASS';
        } catch(error) { document.querySelector('#result').textContent='FAIL: '+error.stack; } })();
        """
        self.run_browser(browser, html + '<script>' + script + '</script>')
