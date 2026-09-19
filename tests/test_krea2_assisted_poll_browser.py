"""User-run browser regression: fake images/transport, no services or generators."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class AssistedPollingBrowserTest(unittest.TestCase):
    def test_poll_preserves_loaded_images_and_enqueue_releases_button_without_queue_get(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (STATIC / "krea2-assisted-lab.js").read_text(encoding="utf-8")
        gallery = source[source.index("  const galleryCards ="):source.index("  function renderProject(")]
        enqueue = source[source.index("  async function renderAttempt("):source.index("  async function startPreparedAttempt(")]
        dlss = (STATIC / "dlss-lab.js").read_text(encoding="utf-8")
        dlss = dlss[dlss.index("  function groups("):dlss.index("  function button(")]
        script = r"""
        (async () => { try {
          const check = (ok, message) => { if (!ok) throw new Error(message); };
          const elements = {gallery: document.getElementById('gallery'), prompt: {value: 'A photograph'},
            model: {value: 'Krea2/a'}, ratio: {value: '9:16'}, megapixels: {value: '0.8'}, seed: {value: '0'},
            promptLanguage: {value: 'en'}, workflow: {value: 'krea2-sampling@1.0.0'}};
          const base = {attempt_id: 'a', index: 1, status: 'succeeded', output_url: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
            output_asset_id: 'asset-a', settings: {aspect_ratio: '9:16', model_id: 'Krea2/a', megapixels: 0.8, resolution: {width: 688, height: 1224}},
            prompt: 'Photo A', seed: '0', can_restore_conversation: true};
          const waiting = {...base, attempt_id: 'b', index: 2, status: 'queued', output_url: null, output_asset_id: null};
          const state = {project: {project_id: 'project', active_branch_id: 'main', branches: [], attempts: [base, waiting]},
            busy: false, spec: {}, navigationSerial: 0};
          const activeStatuses = new Set(['queued', 'running', 'submitting', 'cancel_pending']);
          let position = 1;
          const attemptStatus = a => a.status === 'queued' ? `queued ${position}` : a.status;
          const compactResourceName = value => value, strengthLabel = String;
          const workflowSpec = () => ({label: 'KREA2', recipe_id: 'krea2-sampling'});
          const samplingSummary = () => '8 + 2 steps';
          const validateSamplingInputs = () => true, readSampling = () => ({preset_id: 'current'});
          const imageFigure = (url, caption) => { const figure = document.createElement('figure');
            const img = document.createElement('img'); img.src = url; img.alt = caption; img.loading = 'lazy'; figure.append(img); return figure; };
          let reused = null, feedback = null;
          const loadAttemptSettings = a => { reused = a; }, selectFeedback = id => { feedback = id; };
          const startPreparedAttempt = () => {}, cancelAttempt = () => {}, saveImage = () => {}, openPresetDialog = () => {}, changeBranch = () => {};
          const selections = new Map(), jobs = [];
          __DLSS__
          window.PanelForgeDlss = {groups, picker, button: () => document.createElement('button')};
          __GALLERY__
          renderGallery();
          const original = elements.gallery.querySelector('[data-attempt-id="a"]'), originalImage = original.querySelector('img');
          const pending = elements.gallery.querySelector('[data-attempt-id="b"]');
          const observer = new MutationObserver(() => {}); observer.observe(elements.gallery, {childList: true, subtree: true});
          state.project = JSON.parse(JSON.stringify(state.project)); renderGallery();
          check(observer.takeRecords().length === 0, 'unchanged polling must not mutate gallery DOM');
          position = 2; renderGallery();
          check(elements.gallery.querySelector('[data-attempt-id="a"]') === original, 'queue position preserves finished card');
          check(elements.gallery.querySelector('[data-attempt-id="b"]') !== pending, 'queue position updates pending card');
          state.project.attempts.push({...waiting, attempt_id: 'c', index: 3}); renderGallery();
          check(elements.gallery.children[0].dataset.attemptId === 'c' && originalImage.isConnected, 'new entry precedes existing images');
          state.project.attempts[1] = {...base, attempt_id: 'b', index: 2}; renderGallery();
          check(elements.gallery.querySelector('[data-attempt-id="b"] img'), 'completed entry gets its output');
          check(original.querySelector('img') === originalImage, 'another completion preserves decoded image');
          state.project.feedback_attempt_id = 'a'; renderGallery();
          check(elements.gallery.querySelector('[data-attempt-id="a"] img') === originalImage, 'feedback changes preserve image node');
          const selectedCard = elements.gallery.querySelector('[data-attempt-id="a"]');
          selectedCard.querySelector('[aria-pressed="true"]').click(); check(feedback === null, 'feedback toggle uses new selection');
          selectedCard.querySelector('.actions button').click(); check(reused.attempt_id === 'a', 'reuse acts on correct attempt');
          state.project.attempts.push({...base, attempt_id: 'up', output_asset_id: 'asset-up', dlss: {root_attempt_id: 'a', width: 1000, height: 1600}});
          renderGallery();
          const pickerElement = elements.gallery.querySelector('[data-attempt-id="a"] select');
          pickerElement.value = 'up'; pickerElement.dispatchEvent(new Event('change'));
          check(elements.gallery.querySelector('[data-attempt-id="up"]'), 'DLSS picker replaces only selected variant');
          const up = elements.gallery.querySelector('[data-attempt-id="up"]'); renderGallery();
          check(elements.gallery.querySelector('[data-attempt-id="up"]') === up, 'polling keeps DLSS selection');
          state.project = {...state.project, project_id: 'other', attempts: []}; renderGallery();
          check(!originalImage.isConnected && elements.gallery.textContent.includes('Aucune image'), 'navigation removes old images');
          const selectedLoras = () => [], stopPolling = () => {}, schedulePoll = () => {};
          const setBusy = value => {state.busy = value;};
          let message = '', queueReads = 0;
          const setMessage = text => {message = text;};
          const loadRenderQueue = () => {queueReads++; return new Promise(() => {});};
          const renderProject = project => {state.project = project; renderGallery();};
          window.fetch = () => {throw new Error('unexpected real network');};
          let sent = 0;
          const request = async (url, options) => {
            check(url.endsWith('/attempts?enqueue=true'), 'only atomic enqueue request');
            const body = JSON.parse(options.body); check(body.seed === '0', 'seed zero preserved');
            sent++; return {project: {...state.project, attempts: [...state.project.attempts, {...waiting, attempt_id: `queued-${sent}`, index: sent}]}};
          };
          __ENQUEUE__
          await renderAttempt(); await renderAttempt();
          check(!state.busy && sent === 2 && queueReads === 0, 'button releases without awaiting a separate queue GET');
          check(state.navigationSerial === 2, 'pre-enqueue polls invalidated');
          check(message.includes('Essai 2'), 'enqueue confirms latest entry');
          document.getElementById('result').textContent = 'PASS';
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.stack; } })();
        """
        script = script.replace("__DLSS__", dlss).replace("__GALLERY__", gallery).replace("__ENQUEUE__", enqueue)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "poll.html"
            path.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre><div id="gallery"></div><script>' + script + '</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking", "--no-first-run",
                "--virtual-time-budget=5000", f"--user-data-dir={root / 'profile'}", "--dump-dom", path.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
