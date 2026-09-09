"""Backlog navigation using the real UI functions and fake responses only."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EditBacklogBrowserTest(unittest.TestCase):
    def test_recent_workshops_expand_collapse_and_keep_open_work(self):
        browser_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        browsers = list(browser_root.glob("chromium-*/chrome-win/chrome.exe"))
        browsers += list(browser_root.glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("Chromium local non installé")
        edit = (ROOT / "src/panelforge/features/lab/static/krea2-edit-lab.js").read_text(encoding="utf-8")
        functions = ""
        for start, end in (
            ("  async function loadSources(", "  function setMessage("),
            ("  function projectStages(", "  function renderVersions("),
            ("  function activeProjects(", "  function assistanceVersionFor("),
        ):
            functions += start + edit.split(start, 1)[1].split(end, 1)[0]
        script = r"""
        (async () => { try {
          const check = (value, message) => { if (!value) throw new Error(message); };
          const sources = [5,4,3,2,1].map(n => ({source_id:'p'+n, project_id:'p'+n,
            stage_index:n===3?9:1, state:'pending', filename:'Image '+n,
            source_url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
            attempts:[{attempt_id:'original-'+n}], revisions:[{instruction:'memory-'+n}]}));
          const versions = sources.map(s => ({project_id:s.project_id, family_id:s.project_id, number:1, status:'active'}));
          const state = {sources:[], versions:[], source:null, contextEpoch:0, sourceListEpoch:0, busy:false,
            backlogProjectIds:[], backlogTotal:0, backlogExpanded:false, backlogLoading:false,
            drafts:new Map([['p1',{prompt:'unsent prompt',mask:'unsaved mask'}]])};
          const elements = {backlog:document.createElement('ul'), backlogEmpty:document.createElement('p'), backlogMore:document.createElement('button')};
          document.body.append(elements.backlog, elements.backlogEmpty, elements.backlogMore);
          const retouchEditor = {saving:false};
          let errorMessage='', failed=false, delay=false, release, available=sources;
          const calls=[];
          const setMessage = text => { errorMessage=text; };
          const openSource = source => { state.source=source; state.contextEpoch++; renderBacklog(); };
          const request = async url => {
            calls.push(url);
            if (failed) throw new Error('offline');
            const query=new URL(url,'http://fixture').searchParams;
            const visible=available.slice(0,Number(query.get('project_limit')));
            const pinned=sources.find(s=>s.project_id===query.get('project_id'));
            const selected=[...visible];
            if (pinned && !selected.includes(pinned)) selected.push(pinned);
            const payload={sources:selected, versions, backlog_project_ids:visible.map(s=>s.project_id),project_count:available.length};
            if (delay) return new Promise(resolve=>{release=()=>resolve(payload);});
            return payload;
          };
          __FUNCTIONS__
          await loadSources();
          check(elements.backlog.children.length===3 && state.sources.length===3, 'only three projects loaded and rendered');
          check(state.source.source_id==='p5', 'opens most recently modified project, not highest stage number');
          check(elements.backlogMore.textContent.includes('(2)') && !elements.backlogMore.hidden, 'older project count');
          await toggleBacklog();
          check(elements.backlog.children.length===5 && elements.backlogMore.getAttribute('aria-expanded')==='true', 'expands on demand');
          elements.backlog.lastElementChild.querySelector('button').click();
          check(state.source.source_id==='p1', 'old project can be opened');
          const count=calls.length, selected=state.source, draft=state.drafts.get('p1');
          await toggleBacklog();
          check(calls.length===count && elements.backlog.children.length===3, 'collapse does not request data');
          check(state.source===selected && state.drafts.get('p1')===draft, 'collapse preserves open project and drafts');
          await loadSources();
          check(calls.at(-1).includes('project_id=p1') && state.sources.length===4, 'refresh keeps older open project in addition to three recent projects');
          check(state.source.attempts[0].attempt_id==='original-1' && state.source.revisions[0].instruction==='memory-1', 'attempts and conversation preserved');
          failed=true; await toggleBacklog();
          check(errorMessage==='offline' && !state.backlogExpanded && !state.backlogLoading && state.source===selected, 'failure preserves collapsed list and editor');
          failed=false; delay=true;
          const pending=loadSources({expanded:true});
          state.contextEpoch++; release(); await pending;
          check(!state.backlogExpanded && !state.backlogLoading && state.source===selected, 'stale response cannot replace current context');
          delay=false; available=sources.slice(0,2); await loadSources();
          check(elements.backlogMore.hidden && elements.backlog.children.length===2, 'no expansion button when nothing is hidden');
          document.getElementById('result').textContent='PASS';
        } catch(error) { document.getElementById('result').textContent='FAIL: '+error.stack; } })();
        """
        script = script.replace("__FUNCTIONS__", functions)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            page = directory / "test.html"
            page.write_text('<meta charset="utf-8"><pre id="result">PENDING</pre><script>' + script + '</script>', encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", "--virtual-time-budget=5000", f"--user-data-dir={directory / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
