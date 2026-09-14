"""Image-only comparison UI, using the actual modules/CSS and fake HTTP."""

import unittest
from tests import test_dlss_browser as support


class DlssImageComparisonBrowserTest(unittest.TestCase):
    run_browser = support.DlssBrowserTest.run_browser

    def test_batch_retry_background_comparison_and_explicit_choice(self):
        bootstrap = r"""
        const calls=[], events=[], fakeJobs=[]; let failBatch=true;
        const nativeTimeout=window.setTimeout.bind(window);
        window.setTimeout=(fn,delay,...args)=>nativeTimeout(fn,delay===2500||delay===15000?30:delay,...args);
        const image='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="192"><rect width="128" height="192" fill="teal"/></svg>');
        const src=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
        Object.defineProperty(HTMLImageElement.prototype,'src',{...src,set(value){src.set.call(this,value.startsWith('/api/assets/')?image:value);}});
        const profiles=[['current','Actuels',null,0],['soft','Doux','intensity',-0.25],['detail','Détails','detail',0.15],['structure','Structure','structure',0.2],['tone','Tonalité','tone',-0.2]];
        const presets=settings=>profiles.map(([preset_id,label,key,delta])=>({preset_id,label,available:true,settings:{...settings,...(key?{[key]:settings[key]+delta}:{})}}));
        window.addEventListener('panelforge:dlss-complete',e=>events.push(e.detail));
        window.fetch=async(url,options={})=>{
          const body=options.body?JSON.parse(options.body):null; calls.push({url,body});
          const ok=data=>({ok:true,json:async()=>data});
          if(url==='/api/dlss/jobs'&&!body)return ok({jobs:fakeJobs});
          if(url==='/api/dlss/runtime')return ok({state:'ready',owned:false});
          if(url==='/api/dlss/preview')return ok({input_metadata:{width:64,height:96},output_dimensions:[128,192],image_presets:presets(body.settings)});
          if(url==='/api/dlss/image-comparisons'){
            const selected=presets(body.settings).filter(p=>body.preset_ids.includes(p.preset_id));
            const admitted=failBatch?selected.slice(0,2):selected;
            admitted.forEach(p=>{
              if(fakeJobs.some(j=>j.comparison.preset_id===p.preset_id))return;
              fakeJobs.push({job_id:'job-'+p.preset_id,status:'queued',settings:p.settings,created_at:new Date().toISOString(),
                snapshot:{owner:body.owner,owner_id:body.owner_id,root_attempt_id:'original',parent_attempt_id:'original',input_asset_id:'base',media_type:'image/png'},
                output_dimensions:[128,192],comparison:{group_id:'group',preset_id:p.preset_id,label:p.label,total:selected.length}});
            });
            if(failBatch)return {ok:false,status:503,json:async()=>({detail:'Interrupted admission'})};
            return ok({jobs:fakeJobs});
          }
          throw new Error('Unexpected URL '+url);
        };
        """
        scenario = r"""
        (async()=>{try{
          const check=(value,message)=>{if(!value)throw new Error(message);};
          const pause=()=>new Promise(resolve=>nativeTimeout(resolve,20));
          const until=async fn=>{for(let n=0;n<180&&!fn();n++)await pause();check(fn(),'timed out');};
          const api=window.PanelForgeDlss,dialog=document.querySelector('.dlss-dialog'),form=dialog.querySelector('form');
          const start=dialog.querySelector('[data-start]'), mode=dialog.querySelector('[data-image-mode]');
          const source={owner:'assisted',ownerId:'workshop',attempt:{attempt_id:'original',index:3,output_url:image}};
          const prompt=document.createElement('textarea');document.body.append(prompt);prompt.value='Draft preserved';
          const compareButton=api.comparisonButton(source);document.body.append(compareButton);
          await api.open(source);await until(()=>!start.disabled);
          check(mode.value==='single','single mode stays the default');
          mode.value='compare';mode.dispatchEvent(new Event('input',{bubbles:true}));
          check(dialog.querySelectorAll('[data-preset-id]:checked').length===5,'five profiles start selected');
          check(start.textContent.includes('5'),'count is visible');
          dialog.querySelector('[data-preset-id=soft]').click();check(start.textContent.includes('4'),'checkbox controls the count');
          check(!calls.some(c=>c.url==='/api/dlss/image-comparisons'),'choosing profiles never submits');
          start.click();check(!dialog.open,'image batch closes immediately for background admission');
          prompt.value='Edited during admission';
          await until(()=>document.querySelector('.dlss-background').textContent.includes('Interrupted admission'));
          failBatch=false;await api.open(source);await until(()=>!start.disabled);
          check(mode.value==='compare'&&dialog.querySelectorAll('[data-preset-id]:checked').length===4,'failed launch preserves selection');
          start.click();await until(()=>fakeJobs.length===4&&!dialog.open);
          const posts=calls.filter(c=>c.url==='/api/dlss/image-comparisons');
          check(posts.length===2&&posts[0].body.request_id===posts[1].body.request_id,'retry reuses the same batch id');
          check(posts.every(p=>p.body.settings.size==='1.5'&&!p.body.settings.interpolate),'shared size and image options');
          fakeJobs.forEach((job,index)=>{
            job.status=index===3?'failed':'succeeded';job.output_url=index===3?null:image;
            job.candidate_id='candidate-'+index;job.output_metadata={width:128,height:192};
          });
          await until(()=>!compareButton.hidden&&document.querySelector('.dlss-background').textContent.includes('3/4'));
          check(events.length===0&&prompt.value==='Edited during admission','completion never changes the workshop or draft');
          compareButton.click();const comparison=document.querySelector('.dlss-image-compare');
          check(comparison.open,'comparison opens outside the upscale dialog');
          const selects=[...comparison.querySelectorAll('.dlss-compare-pane > select')];
          check(selects[0].options.length===4,'source plus three successful variants; failed result excluded');
          check(comparison.textContent.includes('3/4'),'series progress is available');
          const zoom=comparison.querySelector('[data-zoom]');zoom.value='3';zoom.dispatchEvent(new Event('input'));
          const views=[...comparison.querySelectorAll('.dlss-compare-viewport')];
          await pause();views[0].scrollTop=80;
          await until(()=>Math.abs(views[1].scrollTop-views[0].scrollTop)<2&&views[1].scrollTop>0);
          const before=views[0].scrollTop;selects[1].value='job-current';selects[1].dispatchEvent(new Event('change'));
          await pause();check(zoom.value==='3'&&Math.abs(views[0].scrollTop-before)<2,'switching keeps zoom and position');
          comparison.querySelectorAll('.dlss-compare-pane > button')[1].click();
          check(events.length===1&&events[0].select_result&&events[0].candidate_id==='candidate-0','exact winner selected explicitly');
          check(!comparison.open,'comparison closes after selection');
          await api.open({...source,owner:'h3'});await until(()=>!start.disabled);
          check(dialog.querySelector('.dlss-image-presets').hidden,'no comparison controls for video');
          check(form.elements.namedItem('size').value==='1.724'&&form.elements.namedItem('interpolate').checked,'video defaults unchanged');
          check(calls.filter(c=>c.url==='/api/dlss/image-comparisons').length===2,'no video batch');
          check(!calls.some(c=>c.url.startsWith('/api/dlss/runtime/')),'no lifecycle calls');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(bootstrap, scenario)
