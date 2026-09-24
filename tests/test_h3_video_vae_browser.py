"""User-run browser regression for restoring an old attempt through a VAE alias."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class H3VideoVaeBrowserTest(unittest.TestCase):
    def test_alias_preserves_all_restored_controls_and_ignores_stale_responses(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob(
            "chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (STATIC / "h3-render-lab.js").read_text(encoding="utf-8")
        switching = source[source.index("  async function switchRecipe("):source.index("  async function request(")]
        restoring = source[source.index("  async function fillSettings("):source.index("  function setPreviewBlob(")]
        bootstrap = r"""
        const check = (value, message) => { if (!value) throw new Error(message); };
        const state = {recipeToken: 0, project: 'p1', specCache: new Map(), recipeDrafts: new Map()};
        const specMode = 'h3-base', options = {restoreSetup: true};
        const projectId = () => state.project;
        const recipeKey = r => r ? (r.id || r.recipe_id) + '@' + r.version : '';
        const elements = Object.fromEntries(['recipe', 'ratio', 'megapixels', 'initialMegapixels',
          'forceUpscale', 'duration', 'steps', 'seed', 'seedLock', 'music', 'spectrum',
          'bunnyTurbo', 'bunnyBase', 'bunnyCoarse', 'bunnyRefine', 'bunnySecond', 'bunnyPreview']
          .map(k => [k, {value: '', checked: false}]));
        let checkpoint, restoredLoras, deferred;
        const checkpointPicker = {set: value => checkpoint = value};
        const loraEditor = {supported: false, restoreAttempt: a => restoredLoras = a.video_loras};
        const rememberRecipe = () => {}, captureControls = () => ({}), restoreControls = () => {};
        const hydrateDefaults = () => { elements.seed.value = '0'; elements.initialMegapixels.value = '0.2'; };
        const renderControls = () => {}, syncBunny = () => {}, syncVideoLoraControls = () => {};
        const renderWarnings = () => {}, setStatus = () => {}, showLora = () => {};
        const request = async raw => {
          const q = new URL(raw, 'http://fake').searchParams;
          const version = q.get('recipe_version');
          if (version === 'delayed') await new Promise(resolve => { deferred = resolve; });
          return {recipe: {id: q.get('recipe_id'), version: version + '+vae-int8-convrot.1'}};
        };
        """
        scenario = r"""
        (async () => { try {
          const attempt = {recipe: {recipe_id: 'minimax-h3-bunny', version: '0.1.3'},
            settings: {aspect_ratio: '9:16', megapixels: 1.2, duration_seconds: 12, steps: 30, seed: '9223372036854775813'},
            initial_megapixels: 0.6, seed_locked: false, music_enabled: true, spectrum_enabled: false,
            checkpoint: 'custom.safetensors', force_upscale: false,
            bunny: {turbo_enabled: false, base_steps: 30, coarse_steps: 25, refine_steps: 5, lora_second_strength: 0.37, preview_enabled: true},
            video_loras: {entries: [{name: 'motion.safetensors', strength: 0.43, second_strength: 0.37}]}};
          await fillSettings(attempt);
          check(elements.recipe.value === 'minimax-h3-bunny@0.1.3+vae-int8-convrot.1', 'canonical recipe selected');
          check(elements.seed.value === attempt.settings.seed, '64-bit seed restored without precision loss');
          check(elements.ratio.value === '9:16' && elements.duration.value === '12', 'ratio and duration');
          check(elements.megapixels.value === '1.2' && elements.initialMegapixels.value === '0.6', 'both resolutions');
          check(elements.steps.value === '30' && !elements.seedLock.checked && elements.music.value === 'on', 'steps and switches');
          check(checkpoint === attempt.checkpoint && restoredLoras === attempt.video_loras, 'checkpoint and LoRA stack');
          check(!elements.bunnyTurbo.checked && elements.bunnySecond.value === '0.37' && elements.bunnyPreview.checked, 'BUNNY controls');
          const waiting = fillSettings({...attempt, recipe: {...attempt.recipe, version: 'delayed'}});
          const newer = {...attempt, settings: {...attempt.settings, seed: '42'}};
          await fillSettings(newer);
          deferred(); await waiting;
          check(elements.seed.value === '42', 'stale response cannot overwrite newer settings');
          document.getElementById('result').textContent = 'PASS';
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.stack; } })();
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "vae.html"
            page.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre><script>'
                            + bootstrap + switching + restoring + scenario + '</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu",
                "--disable-background-networking", "--no-first-run", "--virtual-time-budget=5000",
                f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
