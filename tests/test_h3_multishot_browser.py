"""User-run local DOM fixtures for family choice and continuation. No server."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class H3MultiShotBrowserTest(unittest.TestCase):
    def test_family_selection_and_continuation_restore_source_recipe_without_losing_draft_on_error(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (STATIC / "i2v-direct.js").read_text(encoding="utf-8")
        functions = []
        for name in ("sequenceKind", "changeSequenceKind", "prefillFirstFrame"):
            marker = ("  async function " if name == "prefillFirstFrame" else "  function ") + name + "("
            start = source.index(marker)
            end = source.index("\n  }", start) + len("\n  }")
            functions.append(source[start:end])
        script = """
        (async () => { try {
          const check = (condition, message) => { if (!condition) throw new Error(message); };
          const monoCookbookId = 'minimax.h3.fl2va.direct';
          const multishotCookbookId = monoCookbookId + '.multishot';
          const preferredCookbookKey = monoCookbookId + '.guided@1.1.0';
          const choices = [];
          for (const multi of [false, true]) for (const [route, count] of [['guided',3],['planned',2],['prompt',1]]) {
            const base = multi ? multishotCookbookId : monoCookbookId;
            choices.push({id:base+'.'+route,version:multi?'1.0.0':'1.1.0',preparation_steps:count,profile:{id:base,version:multi?'0.2.0':'0.5.0'}});
          }
          const cookbookKey = c => c ? c.id+'@'+c.version : '';
          const state = {spec:{},cookbook:choices[1],session:null,openRequestId:0,busy:false,lastFile:'old-last'};
          const elements = {sequenceKind:document.createElement('select'),intention:document.createElement('textarea'),form:document.createElement('form')};
          elements.sequenceKind.add(new Option('Mono','mono')); elements.sequenceKind.add(new Option('Multi','multi'));
          elements.form.scrollIntoView = () => {};
          const directCookbooks = () => choices;
          const preparationSteps = () => state.cookbook.preparation_steps;
          const interactionLocked = () => state.busy;
          const render = () => { elements.sequenceKind.value = sequenceKind(state.cookbook); };
          const setBusy = value => { state.busy = value; render(); };
          let resets = 0, failure = false, unavailable = false, stale = false, selectedFile = null, lastMessage = '';
          const resetSession = () => { resets++; state.session=null; state.lastFile=null; elements.intention.value=''; };
          const setSelectedFile = (role,file) => { check(role==='first','first frame role'); selectedFile=file; };
          const showSetupMessage = value => { lastMessage=value; };
          const core = {...window.PanelForgeLabCore,request:async url => {
            check(url==='/api/prompt-lab/sessions/source/composition','only reads source composition');
            if (failure) throw new Error('offline');
            return {composition:{cookbook:unavailable?{id:multishotCookbookId+'.prompt',version:'missing'}:choices[5]}};
          }};
          window.fetch = async url => { check(url==='/api/assets/frame/content','only reads chosen frame');
            if(stale) state.openRequestId++;
            return {ok:true,blob:async()=>new Blob(['fixture'],{type:'image/png'})}; };
          window.PanelForgeLabNavigation = {switchView:view=>check(view==='i2v-direct','opens H3 preparation')};
          __FUNCTIONS__
          elements.sequenceKind.value='multi'; changeSequenceKind();
          check(state.cookbook===choices[4], 'family change retains two preparation calls');
          state.session={id:'locked'}; elements.sequenceKind.value='mono'; changeSequenceKind();
          check(state.cookbook===choices[4] && elements.sequenceKind.value==='multi','saved run stays on its family');
          state.session=null; state.cookbook=choices[0]; elements.intention.value='unsent';
          failure=true;
          try { await prefillFirstFrame({assetId:'frame',label:'Next',sourceSessionId:'source'}); throw new Error('expected failure'); }
          catch(error) { check(error.message==='offline','network failure surfaced'); }
          check(resets===0 && elements.intention.value==='unsent' && selectedFile===null,'failed lookup preserves work');
          failure=false; unavailable=true;
          try { await prefillFirstFrame({assetId:'frame',sourceSessionId:'source'}); throw new Error('expected failure'); }
          catch(error) { check(error.message.includes('indisponible'),'missing version surfaced'); }
          check(resets===0,'missing recipe never silently falls back to mono');
          unavailable=false; stale=true;
          try { await prefillFirstFrame({assetId:'frame',sourceSessionId:'source'}); throw new Error('expected failure'); }
          catch(error) { check(error.message.includes('changé'),'stale navigation surfaced'); }
          check(resets===0,'stale completion preserves work');
          stale=false;
          await prefillFirstFrame({assetId:'frame',label:'Next',sourceSessionId:'source'});
          check(state.cookbook===choices[5] && elements.sequenceKind.value==='multi','source recipe wins over currently selected recipe');
          check(resets===1 && selectedFile instanceof File && selectedFile.type==='image/png','continuation sets selected saved frame');
          check(state.lastFile===null && elements.intention.value==='' && lastMessage.includes('suite'),'clears former target and lets user describe next state');
          document.getElementById('result').textContent='PASS';
        } catch(error) { document.getElementById('result').textContent='FAIL: '+error.stack; } })();
        """
        script = script.replace("__FUNCTIONS__", "\n".join(functions))
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre><script>'
        html += (STATIC / "lab-core.js").read_text(encoding="utf-8") + '</script><script>' + script + '</script>'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "test.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--no-first-run",
                                     f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
