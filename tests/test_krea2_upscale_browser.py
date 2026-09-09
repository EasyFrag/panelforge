"""User-run browser checks with mocked requests; no model endpoint or service."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class UpscaleBrowserTest(unittest.TestCase):
    def test_optional_action_preserves_selection_and_retries_same_request(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        edit = (STATIC / "krea2-edit-lab.js").read_text(encoding="utf-8")
        functions = edit[edit.index("  function canUpscale("):edit.index("  function setComparisonPosition(")]
        script = r"""
        (async () => { try {
          const check = (ok, msg) => { if (!ok) throw new Error(msg); };
          const older = {attempt_id:'older',status:'succeeded',output_url:'old.png',label:'Older'};
          const later = {...older,attempt_id:'later',label:'Later'};
          const source = {source_id:'stage',state:'pending',attempts:[older,later]};
          const state = {source,contextEpoch:0,busy:false,spec:{upscale:{enabled:true}},upscaleRequests:new Map(),upscaleCatalogEpoch:0};
          const retouchEditor = {saving:false};
          const elements = {compareAfter:{value:'older'},upscalePanel:document.createElement('div'),
            upscaleAfter:document.createElement('button'),
            upscaleTarget:document.createElement('b'),upscaleNote:document.createElement('small'),
            upscaleModel:document.createElement('select')};
          const draft = {prompt:'unsent correction',mask:'unsaved mask'};
          let active = null, fail = true, posts = [], polls = 0, resolveCatalogue;
          const isEditable = () => state.source.state === 'pending', activeAttempt = () => active;
          const updateComparisonActions = () => {}, render = () => {}, setMessage = () => {};
          const sourceOf = payload => payload.source, startPolling = () => { polls++; };
          const request = async (url, options) => {
            if (!options) return {models:['photo.pth','other.pth'],default:'photo.pth'};
            posts.push({url,body:JSON.parse(options.body)});
            await Promise.resolve();
            if (fail) throw new Error('network interrupted');
            return {source:{...source,attempts:[...source.attempts,{attempt_id:'enhanced',status:'queued'}]},attempt_id:'enhanced'};
          };
          __FUNCTIONS__
          await openUpscale();
          check(posts.length===0 && state.upscaleSelection.attemptId==='older', 'opening does not render and targets selected older image');
          check(elements.upscaleModel.value==='photo.pth' && !elements.upscalePanel.hidden, 'default model is available in optional panel');
          elements.compareAfter.value='later';
          await startUpscale();
          check(posts[0].url.includes('/older/upscale') && !elements.upscalePanel.hidden, 'visible panel keeps original target and survives failure');
          const requestId=posts[0].body.request_id;
          fail=false;
          const first=startUpscale(); const duplicate=startUpscale(); await Promise.all([first,duplicate]);
          check(posts.length===2 && posts[1].body.request_id===requestId, 'double click does not launch twice and retry keeps identity');
          check(polls===1 && elements.upscalePanel.hidden && !state.busy, 'render progress uses existing polling without locking navigation');
          check(draft.prompt==='unsent correction' && draft.mask==='unsaved mask', 'unrelated drafts preserved');
          active={status:'running'};
          check(!canUpscale(older), 'active render prevents second job');
          active=null;state.source.state='advanced';
          check(!canUpscale(older), 'validated stage immutable');
          state.source.state='pending';
          const opening=openUpscale('older');closeUpscale();await opening;
          check(elements.upscalePanel.hidden && state.upscaleSelection===null, 'late catalogue cannot reopen closed panel');
          document.getElementById('result').textContent='PASS';
        } catch(error) {document.getElementById('result').textContent='FAIL: '+error.stack;} })();
        """.replace("__FUNCTIONS__", functions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "test.html"
            page.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre><script>'+script+'</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--virtual-time-budget=5000", f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
