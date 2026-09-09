"""Exercise recipe disclosure and saved selections in a real local Chromium DOM."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class RecipePickerBrowserTest(unittest.TestCase):
    def test_disclosure_keeps_standard_and_saved_historical_selection(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        script = """
        (async () => { try {
          const select = document.querySelector('select');
          const core = window.PanelForgeLabCore;
          const keys = [
            'minimax.h3.fl2va.direct.guided@1.1.0',
            'minimax.h3.fl2va.direct.planned@1.1.0',
            'minimax.h3.fl2va.direct.prompt@1.1.0',
            'minimax.h3.ref2v.direct.guided@1.0.0',
            'minimax.h3.ref2v.direct.planned@1.0.0',
            'minimax.h3.ref2v.direct.prompt@1.0.0',
            'minimax.h3.fl2va.direct@0.3.3',
            'minimax.h3.fl2va.direct@0.3.2',
            'minimax.h3.fl2va.direct.multishot@0.1.0',
            'minimax.h3.base.animal-interview@0.2.0',
            'minimax.h3.ref2v.direct@0.4.0',
            'minimax.h3.ref2v.direct@0.3.3',
            'minimax.h3.ref2v.direct.multishot@0.2.0',
            'minimax.h3.ref2v.direct.multishot.superfast@0.2.0',
            'minimax.h3.fl2va.direct@0.4.0',
            'minimax.h3.ref2v.direct@0.5.0',
            'minimax.h3.fl2va.direct.guided@1.0.0',
            'minimax.h3.fl2va.direct.planned@1.0.0',
            'minimax.h3.fl2va.direct.prompt@1.0.0',
          ];
          keys.forEach(key => { const option = new Option(key, key); select.add(option); });
          const visible = () => [...select.options].filter(option => !option.hidden).map(option => option.value);
          const check = (condition, message) => { if (!condition) throw new Error(message); };
          core.refreshRecipeVisibility(select);
          check(visible().length === 7, 'three routes per family and Ref2V experimental');
          check(core.recipeTier(keys[14]) === 'historical' && !visible().includes(keys[14]), 'H3 compact recipe archived');
          check(keys.slice(16).every(key => core.recipeTier(key) === 'historical' && !visible().includes(key)), 'H3 1.0 routes archived');
          const advanced = document.querySelector('[data-recipe-tier="advanced"]');
          advanced.checked = true;
          advanced.dispatchEvent(new Event('change'));
          check(visible().length === 10, 'advanced recipes revealed; old H3 multi-shot is historical');
          const historical = document.querySelector('[data-recipe-tier="historical"]');
          historical.checked = true;
          historical.dispatchEvent(new Event('change'));
          check(visible().length === 19, 'history revealed');
          select.value = keys[16];
          historical.checked = false;
          advanced.checked = false;
          core.refreshRecipeVisibility(select);
          check(select.value === keys[16] && visible().includes(keys[16]), 'saved 1.0 guided version retained');
          select.disabled = true;
          core.refreshRecipeVisibility(select);
          check(select.disabled && select.value === keys[16], 'locked run unchanged');
          select.disabled = false;
          select.value = keys[0];
          select.dispatchEvent(new Event('change'));
          check(visible().length === 7, 'old version hidden after returning to standard');
          check(document.querySelectorAll('details').length === 1, 'no duplicate disclosures');
          const familySelect = document.createElement('select');
          familySelect.id = 'h3-family';
          const familyLabel = document.createElement('label');
          familyLabel.append(familySelect); document.body.append(familyLabel);
          for (const family of ['mono', 'multi']) {
            for (const route of ['guided', 'planned', 'prompt']) {
              const key = family === 'mono' ? `minimax.h3.fl2va.direct.${route}@1.1.0`
                : `minimax.h3.fl2va.direct.multishot.${route}@1.0.0`;
              const option = new Option(key, key); option.dataset.recipeFamily = family; familySelect.add(option);
            }
          }
          const familyVisible = () => [...familySelect.options].filter(o => !o.hidden);
          familySelect.dataset.recipeFamily = 'mono'; core.refreshRecipeVisibility(familySelect);
          check(familyVisible().length === 3 && familyVisible().every(o => o.dataset.recipeFamily === 'mono'), 'three mono routes only');
          familySelect.value = 'minimax.h3.fl2va.direct.multishot.planned@1.0.0';
          familySelect.dataset.recipeFamily = 'multi'; core.refreshRecipeVisibility(familySelect);
          check(familyVisible().length === 3 && familyVisible().every(o => o.dataset.recipeFamily === 'multi'), 'three multi routes only');
          const oldMulti = new Option('old multi', 'minimax.h3.fl2va.direct.multishot@0.1.0');
          oldMulti.dataset.recipeFamily = 'multi'; familySelect.add(oldMulti); familySelect.value = oldMulti.value;
          core.refreshRecipeVisibility(familySelect);
          check(!oldMulti.hidden && core.recipeTier(oldMulti.value) === 'historical', 'saved old multi remains selectable');
          const elements = { steps: {}, chips: {} };
          for (const name of ['brief', 'plan', 'prompt']) {
            const chip = document.createElement('div');
            chip.innerHTML = '<b></b>';
            const step = document.createElement('details');
            step.innerHTML = '<span class="cookbook-step-index"></span>';
            elements.chips[name] = chip;
            elements.steps[name] = step;
            document.body.append(chip, document.createElement('i'), step);
          }
          for (const count of [1, 2, 3, 1]) {
            const stages = core.preparationStages({ preparation_steps: count });
            core.renderPreparationStages(elements, stages);
            check(Object.values(elements.steps).filter(step => !step.hidden).length === count, 'only real stages visible');
            check(elements.chips.prompt.querySelector('b').textContent === String(count), 'prompt numbered by route');
            const snapshot = {};
            const actions = {};
            const calls = [];
            for (const name of ['Brief', 'Plan', 'Prompt']) {
              actions['generate' + name] = async () => { calls.push(name); snapshot[name.toLowerCase() + 'Generated'] = true; return true; };
              actions['approve' + name] = async () => { snapshot[name.toLowerCase() + 'Approved'] = true; return true; };
            }
            const record = await window.PanelForgeQuickPipeline.runDirect({ sessionId: 'fixture-' + count, stages,
              snapshot: () => snapshot, actions, isCurrent: () => true });
            check(record.status === 'completed', 'quick route completes');
            check(calls.join(',').toLowerCase() === stages.join(','), 'quick route invokes only its model stages');
          }
          document.querySelector('#result').textContent = 'PASS';
        } catch (error) { document.querySelector('#result').textContent = 'FAIL: ' + error.stack; } })();
        """
        core = (STATIC / "lab-core.js").read_text(encoding="utf-8")
        core += "\n" + (STATIC / "quick-pipeline.js").read_text(encoding="utf-8")
        # Parse changed application scripts in Chromium without starting application requests.
        syntax = "\n".join("new Function(" + json.dumps((STATIC / name).read_text(encoding="utf-8")) + ");"
                           for name in ("i2v-direct.js", "ref2v-direct.js", "krea2-assisted-lab.js"))
        html = '<meta charset="utf-8"><label>Recipe<select id="recipe"></select></label><pre id="result">PENDING</pre>'
        html += "<script>" + core + "</script><script>" + syntax + script + "</script>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [str(browsers[-1]), "--headless", "--disable-gpu", "--no-first-run",
                 f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
