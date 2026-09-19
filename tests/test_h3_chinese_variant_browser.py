"""Browser contract for the optional Chinese H3 prompt variant."""

import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class H3ChineseVariantBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_variant_is_opt_in_and_opens_a_distinct_render_source(self):
        browsers = sorted(
            (Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright")
            .glob("chromium-*/chrome-win64/chrome.exe")
        )
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (STATIC / "chinese-prompt-variant.js").read_text(encoding="utf-8")
        script = r"""
        (async () => { try {
          const check = (ok, message) => { if (!ok) throw new Error(message); };
          const state = {session: {id: 'session-1'}, composition: {
            writer_model_id: 'writer-model', prompt_variants: [],
            documents: {final_prompt: {active_revision_id: 'final-1'}}
          }};
          const gemma = 'local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP';
          let renders = 0; const requests = [];
          const render = () => { renders += 1; };
          const setComposition = value => { state.composition = value; };
          const core = {
            streamRequest: async (url, options, onEvent) => {
              requests.push({url, body: JSON.parse(options.body)});
              const composition = {...state.composition, prompt_variants: [{
                variant_id: 'zh-1', source_revision_id: 'final-1', language: 'zh',
                content: '中文描述', model_id: 'writer-model', llm_call_id: 'call-1'
              }]};
              onEvent({kind: 'delta', text: '中文'});
              onEvent({kind: 'completed', text: '中文描述', composition});
            },
            truncationMessage: () => 'truncated', playFailureTone: () => {}
          };
          window.PanelForgeModelPicker = {
            populate(select, models, selected) {
              select.replaceChildren(...models.map(model => {
                const option = document.createElement('option'); option.value = model.id;
                option.textContent = model.id; return option;
              }));
              if (models.some(model => model.id === selected)) select.value = selected;
            },
            setDisabled() {}
          };
          __COMPONENT__
          const component = window.PanelForgeChinesePromptVariant.create({
            prefix: 'test', state, core, render, setComposition
          });
          component.populate([{id: 'other-model'}, {id: 'writer-model'}, {id: gemma, source: 'local'}]);
          component.draw({locked: false, ready: true});
          check(document.querySelector('#test-chinese-model').value === gemma,
            'the local uncensored Gemma is the default translator');
          check(component.selection().language === 'en', 'English is canonical by default');
          document.querySelector('#test-generate-chinese').click();
          await new Promise(resolve => setTimeout(resolve, 0));
          component.draw({locked: false, ready: true});
          const selection = component.selection();
          check(requests.length === 1 && requests[0].body.model_id === gemma,
            'one explicit translator call uses the selected model');
          check(selection.language === 'zh' && selection.variantId === 'zh-1',
            'generated Chinese becomes the opt-in selection');
          check(selection.renderRevisionId === 'zh:final-1:zh-1',
            'Chinese uses a distinct render source');
          check(state.composition.documents.final_prompt.active_revision_id === 'final-1',
            'the canonical English revision is unchanged');
          state.composition = {...state.composition,
            documents: {final_prompt: {active_revision_id: 'final-2'}}};
          component.draw({locked: false, ready: true});
          check(component.selection().language === 'en',
            'a new English revision resets selection instead of silently reusing Chinese');
          check(renders > 0, 'the host view is refreshed');
          document.querySelector('#result').textContent = 'PASS';
        } catch (error) {
          document.querySelector('#result').textContent = 'FAIL: ' + error.stack;
        } })();
        """.replace("__COMPONENT__", source)
        html = """<meta charset="utf-8">
        <pre id="result">PENDING</pre>
        <details id="test-chinese-panel" hidden></details>
        <select id="test-prompt-language"><option value="en">English</option><option value="zh" disabled>中文</option></select>
        <select id="test-chinese-model"></select>
        <label><input type="checkbox" data-llm-local-for="test-chinese-model" checked>Local</label>
        <button id="test-generate-chinese"></button><button id="test-copy-chinese"></button>
        <p id="test-chinese-status"></p><textarea id="test-chinese-content"></textarea>
        <script>""" + script + "</script>"
        self.run_browser(browsers[-1], html)

    def test_direct_workshops_forward_the_language_selection(self):
        for filename in ("i2v-direct.js", "ref2v-direct.js"):
            source = (STATIC / filename).read_text(encoding="utf-8")
            self.assertIn("PanelForgeChinesePromptVariant.create", source)
            self.assertIn("prompt_language:", source)
            self.assertIn("renderRevisionId", source)


if __name__ == "__main__":
    unittest.main()
