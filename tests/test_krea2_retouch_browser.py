"""Real Canvas interactions using local fixtures and fake save callbacks only.

Prepared for user execution. Does not start the Lab or contact a model server.
"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class RetouchBrowserTest(unittest.TestCase):
    def test_drawing_drafts_saved_masks_and_retry_in_local_chromium(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        editor = '<section id="krea2-edit-retouch"' + index.split('<section id="krea2-edit-retouch"', 1)[1].split("</section>", 1)[0] + "</section>"
        script = r"""
        (async () => { try {
          const check = (ok, message) => { if (!ok) throw new Error(message); };
          const pause = () => new Promise(resolve => setTimeout(resolve, 40));
          const until = async fn => { for (let i = 0; i < 100; i++) { if (fn()) return; await pause(); } throw new Error('timed out'); };
          const root = document.getElementById('krea2-edit-retouch');
          const role = name => root.querySelector(`[data-role="${name}"]`);
          const action = name => root.querySelector(`[data-action="${name}"]`);
          const before = role('before'), after = role('after'), left = role('before-view'), right = role('after-view');
          const pixel = (canvas, x = 20, y = 20) => Array.from(canvas.getContext('2d').getImageData(x, y, 1, 1).data);
          const picture = color => {
            const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 48;
            const ctx = canvas.getContext('2d'); ctx.fillStyle = color; ctx.fillRect(0, 0, 64, 48);
            return canvas.toDataURL('image/png');
          };
          const source = picture('rgb(20, 60, 100)'), generated = picture('rgb(200, 160, 40)');
          const harmonized = picture('rgb(100, 120, 80)');
          const gray = picture('rgb(128,128,128)');
          let loads = 0, saved = 0, fail = true, readonly = false;
          const requests = [];
          window.fetch = () => { throw new Error('drawing attempted a network call'); };
          const controller = window.PanelForgeKrea2Retouch.create({ root,
            load: async (sourceId, attemptId) => {
              loads++;
              return { source_id: sourceId, attempt_id: attemptId, label: 'Essai 1',
                editable: !readonly, width: 64, height: 48,
                source_url: source, generated_url: generated, harmonized_url: harmonized,
                harmonize: attemptId === 'color-saved', harmonize_strength: attemptId === 'color-saved' ? 50 : 100,
                mask_url: ['saved', 'color-saved'].includes(attemptId) ? gray : null };
            },
            save: async (sourceId, attemptId, request) => {
              requests.push(request);
              if (fail) throw new Error('simulated save error');
              return { attempt_id: 'retouch-new' };
            },
            onOpenChange: () => {}, onSaved: () => { saved++; },
          });
          // Synthetic pointer events cannot acquire native capture; real handlers still run.
          for (const view of [left, right]) { view.setPointerCapture = () => {}; view.hasPointerCapture = () => false; }
          const dispatch = (view, type, x, y) => view.dispatchEvent(new PointerEvent(type,
            { bubbles: true, pointerId: 1, button: 0, clientX: x, clientY: y }));
          const paint = async (x = 20, y = 20) => {
            const rect = before.getBoundingClientRect();
            const cx = rect.left + x * rect.width / 64, cy = rect.top + y * rect.height / 48;
            dispatch(left, 'pointerdown', cx, cy); dispatch(left, 'pointerup', cx, cy); await pause();
          };
          await controller.open('stage', 'original'); await pause();
          check(pixel(before).join() === '200,160,40,255', 'left shows generation before painting');
          check(!role('harmonize').checked && role('strength-control').hidden, 'harmonization starts off');
          check(pixel(after).join() === '20,60,100,255', 'empty mask shows source');
          check(before.getBoundingClientRect().width > 0 && after.getBoundingClientRect().width > 0, 'both views visible');
          role('size').value = '16'; role('softness').value = '100';
          await paint();
          const changed = pixel(after);
          check(changed[0] > 20 && changed[0] < 200, 'feather produces a partial mixture');
          check(pixel(before).join() !== changed.join(), 'red guide is separate from clean result');
          role('show-mask').checked = false; role('show-mask').dispatchEvent(new Event('change')); await pause();
          check(pixel(before).join() === '200,160,40,255', 'hide red guide without changing generated image');
          check(pixel(after).join() === changed.join(), 'hide guide does not change composition');
          const switchLeft = async value => { role('left-image').value = value; role('left-image').dispatchEvent(new Event('change')); await pause(); };
          const transformBeforeSwitch = before.style.transform;
          await switchLeft('source');
          check(pixel(before).join() === '20,60,100,255', 'selector shows source');
          check(pixel(after).join() === changed.join() && before.style.transform === transformBeforeSwitch, 'switch preserves mask and zoom');
          await paint(45, 20);
          check(pixel(after, 45, 20)[0] > 20, 'can paint while source is displayed');
          action('undo').click(); await pause();
          check(pixel(after, 45, 20).join() === '20,60,100,255' && pixel(after).join() === changed.join(), 'undo remains shared across views');
          await switchLeft('generated');
          check(pixel(before).join() === '200,160,40,255', 'selector restores generation');
          role('show-mask').checked = true; role('show-mask').dispatchEvent(new Event('change')); await pause();
          check(pixel(after, 0, 0).join() === '20,60,100,255', 'unpainted pixel protected');
          action('undo').click(); await pause();
          check(pixel(after).join() === '20,60,100,255', 'undo restores source');
          action('redo').click(); await pause();
          check(pixel(after).join() === changed.join(), 'redo restores stroke');
          action('erase').click(); role('softness').value = '0'; await paint();
          check(pixel(after).join() === '20,60,100,255', 'eraser restores source');
          action('undo').click(); await pause();
          action('zoom-in').click();
          check(before.style.transform === after.style.transform, 'zoom is synchronized');
          const oldTransform = before.style.transform, rect = right.getBoundingClientRect();
          dispatch(right, 'pointerdown', rect.left + 20, rect.top + 20);
          dispatch(right, 'pointermove', rect.left + 40, rect.top + 30);
          dispatch(right, 'pointerup', rect.left + 40, rect.top + 30);
          check(before.style.transform === after.style.transform && before.style.transform !== oldTransform, 'pan is synchronized');
          check(loads === 1 && requests.length === 0, 'drawing has no server calls');
          controller.close(); await controller.open('stage', 'original'); await pause();
          check(pixel(after).join() === changed.join(), 'unsaved draft survives mode change');
          action('save').click(); await until(() => !controller.saving);
          check(controller.isOpen && role('message').textContent.includes('simulated'), 'failed save leaves editor and draft');
          check(pixel(after).join() === changed.join(), 'failed save preserves pixels');
          await switchLeft('source');
          fail = false; action('save').click(); await until(() => saved === 1);
          check(requests.length === 2 && requests[0].id === requests[1].id && requests[0].mask === requests[1].mask, 'retry reuses request and mask');
          check(!controller.isOpen, 'success returns to comparer');
          await controller.open('stage', 'saved'); await pause();
          check(role('left-image').value === 'generated', 'newly opened retouch defaults to image 2');
          check(pixel(after).join() === '110,110,70,255', 'saved mask reuses original pair, not a previous composite');
          action('paint').click(); await paint();
          check(pixel(after).join() !== '110,110,70,255', 'new draft changes saved retouch');
          controller.close(); readonly = true; await controller.open('stage', 'saved'); await pause();
          check(action('save').disabled && action('paint').disabled && action('erase').disabled, 'validated stage is read only');
          await paint();
          check(pixel(after).join() === '110,110,70,255', 'read-only interaction cannot edit mask');
          controller.close();
          readonly = false; fail = true;
          await controller.open('stage', 'color-saved'); await pause();
          check(role('harmonize').checked && role('strength').value === '50', 'saved color settings restored');
          check(pixel(after).join() === '85,100,80,255', 'same two integer mixtures as server');
          role('show-mask').checked = false; role('show-mask').dispatchEvent(new Event('change')); await pause();
          check(pixel(before).join() === '150,140,60,255', 'left shows generation at selected color strength');
          role('strength').value = '0'; role('strength').dispatchEvent(new Event('input')); await pause();
          check(pixel(after).join() === '110,110,70,255', 'zero strength disables correction without touching mask');
          role('strength').value = '100'; role('strength').dispatchEvent(new Event('input')); await pause();
          check(pixel(after).join() === '60,90,90,255', 'full correction changes only generated side');
          controller.close(); await controller.open('stage', 'color-saved'); await pause();
          check(role('strength').value === '100' && pixel(after).join() === '60,90,90,255', 'color draft survives close');
          action('save').click(); await until(() => !controller.saving);
          const failedColor = requests.at(-1);
          check(failedColor.harmonize && failedColor.strength === 100, 'save includes color parameters');
          role('strength').value = '50'; role('strength').dispatchEvent(new Event('input')); await pause();
          action('save').click(); await until(() => !controller.saving);
          check(requests.at(-1).id !== failedColor.id && requests.at(-1).strength === 50, 'changed intensity gets new request identity');
          const retryColor = requests.at(-1);
          action('save').click(); await until(() => !controller.saving);
          check(requests.at(-1) === retryColor, 'unchanged color retry preserves request');
          role('harmonize').checked = false; role('harmonize').dispatchEvent(new Event('change')); await pause();
          check(pixel(after).join() === '110,110,70,255', 'disable harmonization retains mask');
          controller.close(); readonly = true; await controller.open('stage', 'color-saved'); await pause();
          check(role('harmonize').disabled && role('strength').disabled, 'validated color settings immutable');
          check(role('harmonize').checked && role('strength').value === '50' && pixel(after).join() === '85,100,80,255', 'readonly ignores dirty color draft');
          controller.close();
          readonly = false;
          await controller.open('discard-stage', 'original'); await pause();
          action('paint').click(); await paint();
          check(pixel(after).join() !== '20,60,100,255', 'draft exists before restart');
          controller.discardSource('discard-stage');
          await controller.open('discard-stage', 'original'); await pause();
          check(pixel(after).join() === '20,60,100,255', 'restart discards stage mask draft');
          controller.close();
          {
            // Exercise the actual comparer selection handler and shared validation path.
            const older = {attempt_id: 'older-retouch', kind: 'retouch', status: 'succeeded', output_url: 'chosen.png'};
            const newer = {attempt_id: 'newer', status: 'succeeded', output_url: 'newer.png'};
            const state = {source: {source_id: 'stage', state: 'pending', attempts: [older, newer]}, busy: false,
              feedbackAttemptId: newer.attempt_id, spec: {retouch: {enabled: true}}};
            const elements = {compareAfter: {value: older.attempt_id}, projectName: {value: 'Wall'}, stepName: {value: 'Opening'},
              promoteAfter: document.createElement('button'), retouchAfter: document.createElement('button'),
              upscaleAfter: document.createElement('button'), upscaleStart: document.createElement('button'),
              upscaleProgress: document.createElement('div'), upscaleProgressLabel: document.createElement('small'),
              upscaleModel: document.createElement('select')};
            let active = null, promoted = null;
            const activeAttempt = () => active;
            const retouchEditor = {saving: false, close: () => {}};
            const render = () => {}, setMessage = () => {}, loadSources = async () => {}, openSource = () => {};
            const sourceOf = value => value;
            const request = async (url, options) => { promoted = {url, options}; return {...state.source, stage_index: 2}; };
            __COMPARER_FUNCTIONS__
            updateComparisonActions(); check(!elements.promoteAfter.disabled, 'selected success can be promoted');
            elements.compareAfter.value = 'source'; updateComparisonActions();
            check(elements.promoteAfter.disabled, 'source itself cannot be promoted');
            elements.compareAfter.value = older.attempt_id; active = {status: 'running'}; updateComparisonActions();
            check(elements.promoteAfter.disabled, 'active render blocks promotion');
            active = null; elements.stepName.value = ''; updateComparisonActions();
            check(elements.promoteAfter.disabled, 'missing stage name blocks promotion');
            elements.stepName.value = 'Opening'; state.source.state = 'processed'; updateComparisonActions();
            check(elements.promoteAfter.hidden, 'validated stages hide promotion');
            state.source.state = 'pending'; updateComparisonActions();
            elements.promoteAfter.click(); await until(() => promoted && !state.busy);
            check(promoted.url.endsWith('/older-retouch/promote'), 'promotes exact After candidate despite newer feedback');
            check(JSON.parse(promoted.options.body).step_name === 'Opening', 'shared promotion receives stage metadata');
          }
          {
            const initial = {source_id: 'restart-stage', state: 'pending', restart_count: 0, prompt_status: 'ready', attempts: [{attempt_id: 'old'}], revisions: [{}]};
            const state = {source: initial, sources: [initial], busy: false, contextEpoch: 0, pollTimer: null,
              drafts: new Map([['restart-stage', {prompt: 'old prompt'}], ['other-stage', {prompt: 'keep'}]]), feedbackAttemptId: 'old'};
            const elements = {reasoning: {hidden: false}, reasoningContent: {textContent: 'old thinking'}, instruction: {focus: () => {}}};
            let active = null, allow = false, failRestart = true, calls = 0, discarded = null, opened = null;
            const activeAttempt = () => active, render = () => {}, setMessage = () => {}, sourceOf = value => value;
            const retouchEditor = {saving: false, close: () => {}, discardSource: id => { discarded = id; }};
            const openSource = (value, options) => { state.source = value; opened = options; };
            const request = async (url, options) => {
              calls++; check(url.endsWith('/restart-stage/restart'), 'restart targets current stage');
              check(JSON.parse(options.body).expected_restart_count === 0, 'restart retry uses expected counter');
              if (failRestart) throw new Error('offline');
              return {...initial, restart_count: 1, attempts: [], revisions: []};
            };
            __RESTART_FUNCTIONS__
            const oldConfirm = window.confirm; window.confirm = () => allow;
            try {
              await restartStage(); check(calls === 0 && state.drafts.has('restart-stage'), 'cancel leaves stage intact');
              allow = true; await restartStage();
              check(calls === 1 && state.drafts.has('restart-stage') && discarded === null, 'failed restart preserves drafts');
              failRestart = false; await restartStage();
              check(state.source.restart_count === 1 && opened.hydrate, 'success rehydrates starting state');
              check(!state.drafts.has('restart-stage') && state.drafts.has('other-stage') && discarded === 'restart-stage', 'only current stage drafts discarded');
              check(state.feedbackAttemptId === null && elements.reasoningContent.textContent === '', 'feedback and thinking cleared');
              check(state.contextEpoch === 1, 'old polling responses invalidated');
              active = {}; check(!canRestart(), 'active render blocks restart'); active = null;
              state.source.prompt_status = 'generating'; check(!canRestart(), 'active prompt blocks restart');
              state.source.prompt_status = 'ready'; state.source.state = 'advanced'; check(!canRestart(), 'validated stage blocks restart');
            } finally { window.confirm = oldConfirm; }
          }
          document.getElementById('result').textContent = 'PASS';
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.stack; } })();
        """
        edit_script = (STATIC / "krea2-edit-lab.js").read_text(encoding="utf-8")
        version_functions = "  function projectVersion(" + edit_script.split("  function projectVersion(", 1)[1].split("  function renderVersions(", 1)[0]
        functions = version_functions
        functions += "  function canPromote(" + edit_script.split("  function canPromote(", 1)[1].split("  function setComparisonPosition(", 1)[0]
        functions += "  async function promoteAttempt(" + edit_script.split("  async function promoteAttempt(", 1)[1].split("  async function buildPrompt(", 1)[0]
        functions += "  elements.promoteAfter.addEventListener(" + edit_script.split("  elements.promoteAfter.addEventListener(", 1)[1].split("  elements.uploadForm.addEventListener(", 1)[0]
        script = script.replace("__COMPARER_FUNCTIONS__", functions)
        restart_functions = version_functions
        restart_functions += "  function canRestart(" + edit_script.split("  function canRestart(", 1)[1].split("  async function updateState(", 1)[0]
        script = script.replace("__RESTART_FUNCTIONS__", restart_functions)
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>'
        html += "<style>" + (STATIC / "lab.css").read_text(encoding="utf-8") + "</style>" + editor
        html += "<script>" + (STATIC / "krea2-retouch.js").read_text(encoding="utf-8") + "</script><script>" + script + "</script>"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            page = directory / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                 "--no-first-run", "--window-size=1500,1200", "--virtual-time-budget=12000",
                 f"--user-data-dir={directory / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
