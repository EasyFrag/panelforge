"""Offline DOM/audio mocks; no models, generation, server or real audio."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class RenderNotificationsTest(unittest.TestCase):
    def test_render_notifications_are_distinct_and_idempotent(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        setup = """
        const frequencies = [];
        const envelope = {setValueAtTime() {}, exponentialRampToValueAtTime() {}};
        window.AudioContext = class {
          constructor() { this.state = 'running'; this.currentTime = 0; this.destination = {}; }
          createOscillator() { return {frequency: {setValueAtTime(f) {frequencies.push(f);}},
            connect(gain) {return gain;}, start() {}, stop() {}}; }
          createGain() {return {gain: envelope, connect() {}};}
        };
        """
        script = """
        try {
          const core = window.PanelForgeLabCore;
          const check = (ok, message) => {if (!ok) throw new Error(message);};
          let count = 0;
          let callbacks = [];
          const flush = () => {const jobs = callbacks; callbacks = []; jobs.forEach(fn => fn());};
          const notifier = core.createRenderOutcomeNotifier({play: () => count++, schedule: cb => callbacks.push(cb)});
          notifier.observe('old', 'succeeded');
          notifier.observe('old', 'running');
          notifier.observe('old', 'succeeded');
          flush(); check(count === 0, 'old success and stale running response stay silent');
          notifier.observe('render-1', 'queued');
          notifier.observe('render-1', 'running');
          notifier.observe('render-1', 'succeeded');
          notifier.observe('render-1', 'succeeded');
          flush(); check(count === 1, 'one sound for a render despite repeated polling');
          for (const status of ['failed', 'cancelled', 'canceled']) {
            notifier.observe(status, 'running'); notifier.observe(status, status);
          }
          flush(); check(count === 1, 'no success sound for failed/cancelled renders');
          notifier.observe('render-2', 'pending'); notifier.observe('render-2', 'completed');
          notifier.observe('render-3', 'running'); notifier.observe('render-3', 'succeeded');
          flush(); check(count === 2, 'simultaneous completions are coalesced');
          notifier.observe('render-4', 'running'); notifier.observe('render-4', 'succeeded');
          flush(); check(count === 3, 'later image in queue gets its own sound');
          notifier.observeCollection('workshop', [{id: 'history', status: 'succeeded'}]);
          flush(); check(count === 3, 'initial collection is silent');
          notifier.observeCollection('workshop', [{id: 'history', status: 'succeeded'}, {id: 'fast', status: 'succeeded'}]);
          flush(); check(count === 4, 'fast render completing between polls is detected');
          notifier.observeCollection('other-view', [{id: 'fast', status: 'running'}]);
          notifier.observeCollection('other-view', [{id: 'fast', status: 'succeeded'}]);
          flush(); check(count === 4, 'same render in another view stays deduplicated');
          const brokenAudio = core.createRenderOutcomeNotifier({play: () => {throw new Error('audio unavailable');}, schedule: cb => callbacks.push(cb)});
          brokenAudio.observe('audio-blocked', 'running'); brokenAudio.observe('audio-blocked', 'succeeded'); flush();

          document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
          core.playCompletionTone();
          const llmNotes = frequencies.splice(0);
          const audible = core.createRenderOutcomeNotifier({schedule: cb => callbacks.push(cb)});
          audible.observe('sound', 'running'); audible.observe('sound', 'succeeded'); flush();
          check(llmNotes.length === 2 && frequencies.length === 3, 'different LLM and render melodies');
          check(JSON.stringify(llmNotes) !== JSON.stringify(frequencies), 'render melody distinct');
          frequencies.length = 0;
          window.setTimeout = cb => callbacks.push(cb);
          core.observeRenderAttempts([], 'edit');
          core.observeRenderAttempts([{attempt_id: 'mask', kind: 'retouch', status: 'succeeded'}], 'edit');
          flush(); check(frequencies.length === 0, 'saving a local retouch stays silent');
          core.observeRenderAttempts([{attempt_id: 'generated', kind: 'generation', status: 'queued'}], 'edit');
          core.observeRenderAttempts([{attempt_id: 'generated', kind: 'generation', status: 'succeeded'}], 'edit');
          flush(); check(frequencies.length === 3, 'real generation uses the new tone');
          document.querySelector('#result').textContent = 'PASS';
        } catch (error) {document.querySelector('#result').textContent = 'FAIL: ' + error.stack;}
        """
        core = (STATIC / "lab-core.js").read_text(encoding="utf-8")
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>'
        html += '<script>' + setup + core + script + '</script>'
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "notifications.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [str(browsers[-1]), "--headless", "--no-sandbox", "--disable-gpu",
                 f"--user-data-dir={Path(directory) / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('<pre id="result">PASS</pre>', result.stdout)
