"""Prepared for user execution: real controls, fake transport, no model services."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class H3RenderControlsBrowserTest(unittest.TestCase):
    def test_defaults_independent_resolutions_and_seed_reuse(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        page = (STATIC / "index.html").read_text(encoding="utf-8")
        ratio_start = page.index('<label>Ratio<select id="h3r-ratio"')
        settings = '<div class="h3-render-settings">' + page[ratio_start:].split('</div>', 1)[0] + '</div>'
        script = r"""
        (async () => { try {
          const check = (ok, message) => { if (!ok) throw new Error(message); };
          const input = name => document.getElementById(`h3r-${name}`);
          const elements = {ratio: input('ratio'), megapixels: input('megapixels'), initialMegapixels: input('initial-megapixels'),
            duration: input('duration'), steps: input('steps'), seed: input('seed'), seedLock: input('seed-lock'),
            music: input('music'), spectrum: input('spectrum'), prompt: {value: 'A continuous shot.'}, live: {}, liveEmpty: {}};
          const state = {busy: false, project: {project_id: 'test', current_prompt: 'A shot.', attempts: []},
            spec: {defaults: {aspect_ratio: '9:16 (Portrait Widescreen)', megapixels: 0.2, initial_megapixels: 0.2,
              duration_seconds: 6, steps: 25, seed_locked: true}, aspect_ratios: ['9:16 (Portrait Widescreen)'], limits: {initial_megapixels: {minimum: 0.1}}}};
          const specMode = 'h3-base'; let nextSeed = 100;
          const randomSeed = () => String(++nextSeed), inferredDuration = (_, fallback) => fallback;
          const renderWarnings = () => {}, renderControls = () => {}, connectPreview = () => {}, startPolling = () => {};
          const projectId = () => state.project.project_id;
          const bunnyActive = () => false, syncBunny = () => {}, syncVideoLoraControls = () => {};
          const recipeKey = () => '', switchRecipe = async () => {};
          state.spec.recipe = {id: 'minimax-h3-latent-speed', version: '0.1.3'};
          const renderProject = project => { state.project = project; };
          let failure = ''; const setStatus = message => { failure = message; };
          const sent = [];
          window.fetch = () => { throw new Error('unexpected network call'); };
          const request = async (url, options) => {
            if (url.endsWith('/attempts')) {
              const body = JSON.parse(options.body); sent.push(body);
              return {project: {...state.project, attempts: [{attempt_id: 'attempt', settings: body, initial_megapixels: body.initial_megapixels}]}};
            }
            check(url.endsWith('/start'), 'only fake prepare/start accepted'); return {project: state.project};
          };
          __CONTROL_FUNCTIONS__
          hydrateDefaults();
          check(elements.megapixels.value === '0.2' && elements.initialMegapixels.value === '0.2', 'both MP defaults are 0.2');
          check(elements.seedLock.checked, 'reuse seed checked by default');
          check(!elements.megapixels.disabled && !elements.initialMegapixels.disabled && !elements.megapixels.readOnly && !elements.initialMegapixels.readOnly, 'both values editable');
          const seed = elements.seed.value;
          elements.initialMegapixels.value = '0.6';
          check(elements.megapixels.value === '0.2', 'initial resolution does not force output');
          elements.megapixels.value = '1.2';
          await renderAttempt(); await renderAttempt();
          check(!failure && sent.length === 2, 'render controls prepare attempts');
          check(sent.every(body => body.initial_megapixels === 0.6 && body.megapixels === 1.2 && body.seed === seed && body.seed_locked), 'both resolutions and identical seed sent on repeated renders');
          check(elements.seed.value === seed, 'locked seed unchanged after render');
          await fillSettings({settings: {aspect_ratio: state.spec.defaults.aspect_ratio, megapixels: 0.4, duration_seconds: 6, steps: 20, seed: '42'}, initial_megapixels: 0.8});
          check(elements.initialMegapixels.value === '0.8' && elements.megapixels.value === '0.4', 'reuse restores distinct resolutions');
          await fillSettings({settings: {aspect_ratio: state.spec.defaults.aspect_ratio, megapixels: 1.2, duration_seconds: 6, steps: 20, seed: '41'}});
          check(elements.initialMegapixels.value === '0.2' && elements.megapixels.value === '1.2', 'old attempt keeps output and assumes initial 0.2');
          elements.seedLock.checked = false; await renderAttempt();
          check(sent.at(-1).seed === null && !sent.at(-1).seed_locked && elements.seed.value !== '41', 'seed can still be randomized');
          state.spec.recipe = {id: 'minimax-h3-ref2v', version: '0.2.1'};
          delete state.spec.defaults.seed_locked; hydrateDefaults();
          check(elements.seedLock.checked, 'missing seed default also falls back to reuse');
          check(elements.megapixels.value === '0.2' && elements.initialMegapixels.value === '0.2', 'new REF2V uses the same resolution defaults');
          elements.initialMegapixels.value = '0.4'; elements.megapixels.value = '0.8';
          const refSeed = elements.seed.value; await renderAttempt(); await renderAttempt();
          check(sent.slice(-2).every(body => body.initial_megapixels === 0.4 && body.megapixels === 0.8 && body.seed === refSeed && body.seed_locked), 'REF2V sends both MP independently and reuses seed');
          document.getElementById('result').textContent = 'PASS';
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.stack; } })();
        """
        source = (STATIC / "h3-render-lab.js").read_text(encoding="utf-8")
        functions = "  function hydrateDefaults(" + source.split("  function hydrateDefaults(", 1)[1].split("  function setPreviewBlob(", 1)[0]
        functions += "  function renderParameters(" + source.split("  function renderParameters(", 1)[1].split("  async function cancelAttempt(", 1)[0]
        script = script.replace("__CONTROL_FUNCTIONS__", functions)
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>' + settings + '<script>' + script + '</script>'
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "controls.html"
            path.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--virtual-time-budget=5000", f"--user-data-dir={directory / 'profile'}", "--dump-dom", path.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
