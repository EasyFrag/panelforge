"""User-run presentation regression; fixtures only, no server, model or rendering."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class StoryWritingBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_progress_approval_block_recovery_and_completed_units(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        scenario = r"""
          try {
            const check=(v,m)=>{if(!v)throw new Error(m);};
            const describe=window.PanelForgeStoryWriting.describe;
            const project=()=>({document:{series_outline:{episodes:[{id:'episode-1',title:'Le refus'},{id:'episode-2',title:'La réponse'}]},
                selected_episode_id:'episode-1',episode_scenarios:{},reviews:{}},
              long_status:{outline_reviewed:false,units:{},reviews:{}},workflow:{mode:'manual',status:'paused',approvals:{}},
              long_options:{delivery:'continuous'}});
            let p=project(), v=describe(p);
            check(v.stage==='story'&&v.steps.story!=='done','outline existence is not approval');
            p.document.reviews.outline={source_hash:'outline-v1',issues:[]};
            p.long_status.outline_reviewed=true;
            p.workflow={mode:'manual',status:'awaiting_author',wait_target:'outline',approvals:{}};
            v=describe(p);check(v.kind==='approval'&&v.steps.story==='approval'&&v.action==='advance','manual checkpoint');
            p.workflow={mode:'automatic',status:'running',approvals:{}};
            p.job={status:'running',operation:'develop'};
            v=describe(p);check(v.stage==='scenario'&&v.steps.story==='done'&&v.steps.scenario==='running','real writing phase');
            check(v.unitStatus(v.units[0])[0]==='running'&&v.unitStatus(v.units[1])[0]==='planned','only the active unit is running');
            p.job={status:'succeeded',operation:'develop'};
            v=describe(p);check(v.kind==='planned'&&v.action===null,'between calls is scheduled without an author action');
            p.workflow={mode:'automatic',status:'blocked',wait_target:'outline'};
            p.long_status.outline_reviewed=false;p.long_status.reviews.outline={current:true};
            p.document.reviews.outline.issues=[{severity:'blocking',problem:'IDs ambigus.',suggestion:'Relire.'},{severity:'warning',problem:'Suggestion facultative.'}];
            v=describe(p);check(v.kind==='attention'&&v.action==='feedback'&&v.secondary==='review-outline'&&v.issues.length===1,'review blocker and optional advice are separate');
            p.long_status.reviews.outline.current=false;
            check(describe(p).issues.length===0,'obsolete review does not become a current blocker');
            const saved=structuredClone(p);
            p.document.episode_scenarios['episode-1']={scenes:[{title:'Le refus'}]};
            p.document.reviews['episode-1']={issues:[{severity:'blocking',target_id:'scene-1',problem:'Refus manquant.'},{severity:'warning',target_id:'scene-1',problem:'Style.'}]};
            p.long_status.outline_reviewed=true;p.long_status.reviews['episode-1']={current:true};
            p.long_status.units['episode-1']={written:true,stale:false,previous_ready:true};
            p.workflow={mode:'automatic',status:'blocked',wait_target:'episode-1',repairs:{'episode-1':1}};
            v=describe(p);check(v.action==='correct-and-continue'&&v.secondary==='feedback'&&v.issues.length===1,'current scene blockers offer one correction action');
            p.long_status.units['episode-1'].stale=true;
            check(describe(p).action==='feedback','obsolete scenes cannot launch correction');
            p.long_status.units['episode-1'].stale=false;p.document.reviews['episode-1'].issues.shift();
            check(describe(p).action!=='correct-and-continue','warnings never offer automatic correction');
            p=saved;
            p.job={status:'failed',operation:'edit_outline',draft:'partial',can_revalidate:true,error:'JSON invalide.'};
            v=describe(p);check(v.kind==='error'&&v.action==='revalidate'&&v.steps.story==='error','recoverable technical error');
            p.job.can_revalidate=false;
            check(describe(p).action==='retry','unrecoverable draft calls out LLM retry');
            p=project();p.workflow={mode:'automatic',status:'paused'};p.long_status.outline_reviewed=true;
            p.document.episode_scenarios['episode-1']={scenes:[]};
            p.long_status.units['episode-1']={ready:true,written:true};
            v=describe(p);check(v.steps.scenario!=='done'&&v.action!=='validate','one finished unit is not a finished scenario');
            p.document.episode_scenarios['episode-2']={scenes:[]};p.long_status.units['episode-2']={ready:true,written:true};
            p.workflow.status='ready';v=describe(p);
            check(v.steps.scenario==='done'&&v.action==='validate','completed story reaches existing fabrication gate');
            p.workflow={mode:'manual',status:'awaiting_author',wait_target:'episode-2',approvals:{outline:'outline-v1','episode-1':'unit-v1'}};
            p.document.reviews={outline:{source_hash:'outline-v1'},'episode-1':{source_hash:'unit-v1'},'episode-2':{source_hash:'unit-v2'}};
            v=describe(p);check(v.steps.scenario==='approval'&&v.action==='advance','last manual approval precedes completion');
            p.workflow={mode:'automatic',status:'paused'};p.job={status:'failed',operation:'discuss',error:'Connexion interrompue.'};
            v=describe(p);check(v.kind==='error'&&v.steps.scenario==='done','chat failure preserves completed writing');
            document.querySelector('#result').textContent='PASS';
          } catch(error) {document.querySelector('#result').textContent='FAIL: '+error.stack;}
        """
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre><script>'
                + (STATIC / 'story-writing.js').read_text(encoding='utf8')
                + '</script><script>' + scenario + '</script>')
        self.run_browser(browsers[-1], html)
