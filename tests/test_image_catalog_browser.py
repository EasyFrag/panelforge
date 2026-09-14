"""Local DOM fixtures; fake metadata only, never start PanelForge or a model."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests import test_media_analysis_browser as fixture

STATIC = fixture.STATIC


def function_block(filename, start, end):
    source = (STATIC / filename).read_text(encoding="utf-8")
    return start + source.split(start, 1)[1].split(end, 1)[0]


class ImageCatalogBrowserTest(unittest.TestCase):
    def run_browser(self, browser, html):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "catalog.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([
                str(browser), "--headless", "--disable-gpu", "--disable-background-networking", "--no-first-run",
                "--window-size=1500,1000", "--force-device-scale-factor=1", "--virtual-time-budget=10000",
                f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri(),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)

    def run_scenario(self, script):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        resources = (STATIC / "krea2-resource-ui.js").read_text(encoding="utf-8")
        wrapper = """(async()=>{try{const check=(ok,label)=>{if(!ok)throw new Error(label);};
        SCRIPT
        document.querySelector('#result').textContent='PASS';
        }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();"""
        self.run_browser(browsers[-1], '<meta charset="utf-8"><pre id="result">PENDING</pre><script>'
                         + resources + '</script><script>' + wrapper.replace("SCRIPT", script) + '</script>')

    def test_assisted_projects_open_while_spec_and_queue_are_pending(self):
        initialize = function_block("krea2-assisted-lab.js", "  async function initialize()", "  elements.newForm.addEventListener")
        navigate = function_block("krea2-assisted-lab.js", "  async function openProject(", "  async function createProject(")
        self.run_scenario(r"""
          const state={initializing:null,initialized:false,busy:false,spec:null,navigationSerial:0,renderQueue:{items:[]}};
          let releaseSpec, historyLoaded=false;
          const queueResolvers=[];
          const loadSpec=()=>new Promise(resolve=>{releaseSpec=resolve;});
          const loadRenderQueue=()=>new Promise(resolve=>{queueResolvers.push(resolve);});
          const loadHistory=async()=>{historyLoaded=true;},loadPresets=async()=>{};
          const setBusy=value=>{state.busy=value;};
          const setNewMessage=()=>{},setMessage=()=>{},setHistoryMessage=()=>{},stopPolling=()=>{},clearGuidance=()=>{},schedulePoll=()=>{};
          const restagingEditor={saving:false};
          const request=async url=>({project:{project_id:url.split('/').at(-1),attempts:[]}});
          const renderProject=project=>{state.project=project;},restoreRenderState=()=>{};
          __FUNCTIONS__
          const opening=initialize();
          await Promise.resolve();
          check(historyLoaded && !state.busy,'catalog loading does not globally lock navigation');
          await openProject('first');
          check(state.project.project_id==='first','first project opens before metadata');
          await openProject('second');
          check(state.project.project_id==='second','another project can be opened while queue is pending');
          state.busy=true; // A new user action started while initialization was pending.
          releaseSpec();
          queueResolvers.forEach(resolve=>resolve());
          await opening;
          check(state.busy,'late initialization never unlocks another active action');
        """.replace("__FUNCTIONS__", initialize + navigate))

    def test_edit_late_catalog_preserves_current_project_mask_draft_and_removed_model(self):
        fetch_catalog = function_block("krea2-edit-lab.js", "  async function fetchCatalog(force)", "  async function loadSources(")
        ensure_option = function_block("krea2-edit-lab.js", "  function ensureOption(", "  function isFireRed(")
        self.run_scenario(r"""
          const elements={};
          for(const key of ['model','llm','ratio','engine','workflow']){
            elements[key]=document.createElement('select');document.body.append(elements[key]);
            elements[key].append(new Option('old','old'));
          }
          elements.prompt=document.createElement('textarea');elements.prompt.value='unfinished draft';
          const mask={pixels:'uncommitted mask'}, slots=[{name:'krea2/removed',strength:1.7}];
          const state={busy:false,catalogStaticReady:true,spec:{render_models:[],loras:[],llm_models:[]},source:{source_id:'before'},loraSlots:slots};
          const retouchEditor={saving:false,mask};
          const catalogStatus={observe(){},retry(){}};
          let release;
          const request=()=>new Promise(resolve=>{release=resolve;});
          const renderLoras=()=>{},renderResourceManager=()=>{},render=()=>{};
          const updateResourcePreference=async()=>false,refreshResource=async()=>false;
          const {renderModelPicker,syncModelPicker}=window.PanelForgeKrea2ResourceUi;
          window.PanelForgeModelPicker={populate(select,models){select.replaceChildren(...models.map(m=>new Option(m.id,m.id)));},
            select(select,value){if(![...select.options].some(o=>o.value===value))select.append(new Option(value,value));select.value=value;}};
          __FUNCTIONS__
          const loading=fetchCatalog(false);
          state.source={source_id:'newly opened'};
          elements.model.append(new Option('chosen while waiting','chosen'));elements.model.value='chosen';
          elements.prompt.value='new unsent draft';
          release({render_models:[{resource_id:'other',comfy_name:'other',category:'unknown',display_name:'Other'}],loras:[],llm_models:[{id:'new llm'}]});
          await loading;
          check(elements.model.value==='chosen' && elements.model.selectedOptions[0].dataset.missing==='true','removed checkpoint remains selected and marked unavailable');
          check(elements.llm.value==='old','selected LLM never silently replaced');
          check(state.source.source_id==='newly opened' && elements.prompt.value==='new unsent draft','late response preserves navigation and current draft');
          check(state.loraSlots===slots && slots[0].strength===1.7 && retouchEditor.mask===mask,'LoRA strengths and mask preserved');
        """.replace("__FUNCTIONS__", ensure_option + fetch_catalog))

    def test_resource_details_are_requested_only_on_i_and_can_be_closed_while_loading(self):
        self.run_scenario(r"""
          let calls=0,release;
          window.fetch=()=>{calls++;return new Promise(resolve=>{release=resolve;});};
          const resource={resource_id:'a',kind:'lora',comfy_name:'krea2/a',category:'unclassified',display_name:'A',detail_url:'/fixture/a'};
          const ui=window.PanelForgeKrea2ResourceUi,host=document.createElement('div');document.body.append(host);
          ui.renderLoraStack(host,{resources:[resource],selections:[{name:'krea2/a',strength:1}],onChange(){}});
          check(calls===0,'listing resources never requests details');
          host.querySelector('.krea2-resource-info').click();
          check(calls===1 && document.querySelector('dialog[open]'),'i opens a loading card immediately');
          document.querySelector('dialog button').click();
          release({ok:true,json:async()=>({...resource,description:'Local details',preview_urls:[]})});
          await new Promise(resolve=>setTimeout(resolve,0));
          check(!document.querySelector('dialog[open]'),'closing during fetch does not reopen a late card');
          ui.openResourceInfo(resource);
          check(calls===1 && document.querySelector('dialog').textContent.includes('Local details'),'loaded card is reused');
        """)

    def test_real_assisted_markup_layout_navigation_and_repaint_recovery(self):
        """Use the real markup, CSS, model picker and entire Assisted module.

        Only HTTP and the unused retouch editor are fakes. Extracted functions
        with mocked paint helpers did not cover the previous grid regression.
        """
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        page = (STATIC / "index.html").read_text(encoding="utf-8")
        start = '<main id="krea2-assisted-lab-workspace"'
        markup = start + page.split(start, 1)[1].split('</main>', 1)[0] + '</main>'
        for dialog_id in ("krea2-assisted-preset-dialog", "krea2-assisted-lightbox"):
            start = f'<dialog id="{dialog_id}"'
            markup += start + page.split(start, 1)[1].split('</dialog>', 1)[0] + '</dialog>'
        picker = (STATIC / "lab.js").read_text(encoding="utf-8").split('const ui = {};', 1)[0]
        resources = (STATIC / "krea2-resource-ui.js").read_text(encoding="utf-8")
        assisted = (STATIC / "krea2-assisted-lab.js").read_text(encoding="utf-8")
        css = (STATIC / "lab.css").read_text(encoding="utf-8")
        bootstrap = r"""
          const fixtureErrors=[];
          window.addEventListener('error',event=>fixtureErrors.push(event.message));
          window.addEventListener('unhandledrejection',event=>fixtureErrors.push(String(event.reason)));
          window.PanelForgeAssistedRestaging={create:()=>({saving:false,close(){}})};
          let releaseCatalog, releaseSlowProject, delayCatalog=true, brokenPaint=false;
          const originalUi=window.PanelForgeKrea2ResourceUi;
          window.PanelForgeKrea2ResourceUi={...originalUi,renderModelPicker(...args){
            if(brokenPaint)throw new Error('fixture repaint failure');
            return originalUi.renderModelPicker(...args);
          }};
          const project=id=>({project_id:id,name:id,model_id:'fixture-llm',active_branch_id:'main',branches:[],
            attempts:[],turns:[],current_prompt:'Saved '+id,render_seed:'123',
            render_settings:{model_id:'Krea2/base',aspect_ratio:'9:16',megapixels:.8,loras:[]}});
          const spec={render_models:[{resource_id:'base',comfy_name:'Krea2/base',kind:'model',category:'unknown',display_name:'Base'}],
            loras:[],llm_models:[{id:'fixture-llm',label:'Fixture'}],aspect_ratios:['9:16'],defaults:{aspect_ratio:'9:16',megapixels:.8},
            assistance_recipes:[{version:'3.0.0',label:'V3'}],catalog_status:{resources:{ready:true},llm:{ready:true}}};
          const reply=value=>({ok:true,json:async()=>value});
          window.fetch=async(url,options={})=>{
            if(options.method && options.method!=='GET')throw new Error('No writes or generations in this fixture');
            if(url.includes('/spec'))return delayCatalog?new Promise(resolve=>{releaseCatalog=()=>resolve(reply(spec));}):reply(spec);
            if(url.includes('/projects?'))return reply({projects:[project('First'),project('Slow'),project('Last')]});
            if(url.endsWith('/projects/Slow'))return new Promise(resolve=>{releaseSlowProject=()=>resolve(reply({project:project('Slow')}));});
            if(url.includes('/projects/'))return reply({project:project(url.split('/').at(-1))});
            if(url.endsWith('/render-queue'))return reply({items:[]});
            if(url.endsWith('/style-presets'))return reply({presets:[]});
            throw new Error('Unexpected endpoint '+url);
          };
        """
        scenario = r"""
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const until=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10));}throw new Error('Fixture timed out');};
          const workspace=document.querySelector('main'), sidebar=workspace.querySelector('.controls'), editor=workspace.querySelector('.content');
          const history=workspace.querySelector('#krea2-assisted-history');
          const title=()=>workspace.querySelector('#krea2-assisted-title').textContent;
          await until(()=>history.querySelectorAll('button').length===3);
          check(!workspace.querySelector(':scope > .image-catalog-status'),'catalog must not occupy a grid column');
          check(sidebar.contains(workspace.querySelector('.image-catalog-status')),'compact status is inside sidebar');
          check(!workspace.querySelector('#krea2-assisted-new-project').open,'new-project form does not bury history');
          check(history.getBoundingClientRect().top < workspace.querySelector('#krea2-assisted-new-project').getBoundingClientRect().top,'recent projects come first');
          history.querySelector('button').click();await until(()=>title()==='First');
          check(Math.abs(sidebar.getBoundingClientRect().top-editor.getBoundingClientRect().top)<2,'editor stays beside sidebar');
          check(editor.getBoundingClientRect().left>sidebar.getBoundingClientRect().left,'editor is in the right column');
          history.querySelectorAll('button')[1].click();await until(()=>releaseSlowProject);
          history.querySelectorAll('button')[2].click();await until(()=>title()==='Last');
          releaseSlowProject();await new Promise(resolve=>setTimeout(resolve,0));
          check(title()==='Last','late project response never replaces the latest choice');
          // Force a DOM failure after the HTTP response was received, then retry identical metadata.
          brokenPaint=true;delayCatalog=false;releaseCatalog();
          await until(()=>workspace.querySelector('.image-catalog-status').textContent.includes('Affichage des modèles interrompu'));
          const prompt=workspace.querySelector('#krea2-assisted-prompt');prompt.value='Unsent draft';
          brokenPaint=false;workspace.querySelector('.image-catalog-status button').click();
          await until(()=>workspace.querySelector('.image-catalog-status').textContent.includes('1 modèles'));
          check(prompt.value==='Unsent draft' && title()==='Last','retry preserves draft and open project');
          check(!workspace.querySelector('#krea2-assisted-render').disabled,'retry completes control initialization');
          check(fixtureErrors.length===0,'no uncaught UI exception: '+fixtureErrors.join('; '));
          document.querySelector('#result').textContent='PASS';
        }catch(error){document.querySelector('#result').textContent='FAIL: '+error.stack;}})();
        """
        html = '<meta charset="utf-8"><style>' + css + '</style><pre id="result">PENDING</pre>' + markup
        html += '<script>' + picker + '</script><script>' + resources + '</script><script>' + bootstrap
        html += '</script><script>' + assisted + '</script><script>' + scenario + '</script>'
        self.run_browser(browsers[-1], html)
