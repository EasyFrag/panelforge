"""User-run Chromium regression for the actual paginated factory protocol."""
import json
import os
from pathlib import Path
import unittest

from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.video_factory import configuration, new_item
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_archives import delivered


class FactoryViewsBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def browser(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            chrome = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
            if chrome.is_file():
                browsers = [chrome]
        if not browsers:
            self.skipTest("local Chromium or Chrome not installed")
        return browsers[-1]

    def test_visibility_pagination_selection_detail_and_draft(self):
        browser = self.browser()
        service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
        service._state["items"] = [new_item("Item " + str(i), configuration(), {"kind": "image", "id": str(i)}, str(i)) for i in range(125)]
        fixture = dict(pages=[service.browse(offset=i) for i in (0, 50, 100)],
                       details=[service.item_detail(i["id"]) for i in service._state["items"]],
                       summary=service.summary())
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        bootstrap = "const fixture=" + json.dumps(fixture, ensure_ascii=False).replace("<", "\\u003c") + r""";
          const calls=[],polls=new Map(),nativeTimeout=window.setTimeout.bind(window);
          window.setTimeout=(fn,delay,...args)=>{
            if(delay===5000||delay===15000){polls.set(delay,fn);return nativeTimeout(()=>{},100000);}
            return nativeTimeout(fn,delay,...args);
          };
          let visibility='visible',revision=fixture.summary.revision,hold=false,release,failView=false;
          Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>visibility});
          const root=document.getElementById('video-factory-workspace');root.hidden=true;
          window.PanelForgeLabNavigation={switchView(){root.hidden=false;}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options]);
            const request=new URL(url,'http://fixture'),path=request.pathname,q=request.searchParams;
            if(path==='/api/video-factory/summary')return {...fixture.summary,revision};
            if(path==='/api/video-factory/browse'){
              if(failView){failView=false;throw new Error('offline fixture');}
              const offset=Number(q.get('offset')||0),page=structuredClone(fixture.pages[offset/50]);
              page.revision=revision;
              page.inventory.forEach(i=>i.revision=fixture.details.find(d=>d.id===i.id).revision);
              page.items.forEach(i=>Object.assign(i,{name:fixture.details.find(d=>d.id===i.id).name,revision:fixture.details.find(d=>d.id===i.id).revision}));
              const detail=fixture.details.find(i=>i.id===q.get('focus'));
              if(detail&&detail.revision!==Number(q.get('detail_revision')))page.detail=structuredClone(detail);
              if(q.get('known_revision')===String(revision)){page.unchanged=true;delete page.items;delete page.inventory;}
              if(hold){hold=false;await new Promise(resolve=>release=resolve);}
              return page;
            }
            if((options.method||'GET')==='GET'&&path.startsWith('/api/video-factory/items/'))
              return structuredClone(fixture.details.find(i=>i.id===decodeURIComponent(path.split('/').at(-1))));
            if(options.method==='PATCH'){
              if(q.get('compact')!=='true')throw new Error('Mutation must request compact receipt');
              const body=JSON.parse(options.body);
              body.ids.forEach(id=>{const item=fixture.details.find(i=>i.id===id);item.revision++;if(body.changes?.name)item.name=body.changes.name;});
              revision++;
              return {state:{...fixture.summary,revision},undo:{},revisions:{}};
            }
            if(options.method==='PUT'){revision++;return {...fixture.summary,revision};}
            throw new Error('Unexpected request '+url);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<12;i++)await new Promise(r=>nativeTimeout(r,0));};
            const el=id=>document.getElementById('vf-'+id);
            const browseCount=()=>calls.filter(([url])=>url.includes('/browse?')).length;
            await settle();
            check(calls.length===1&&calls[0][0].endsWith('/summary'),'hidden workshop only loads counters');
            root.hidden=false;await settle();
            check(el('rows').querySelectorAll('[data-vf-id]').length===50,'only one page rendered');
            check(!el('page-next').disabled&&el('page-previous').disabled,'pagination enabled after request');
            failView=true;el('page-next').click();await settle();
            check(el('rows').querySelector('[data-vf-id]').dataset.vfId===fixture.details[0].id&&el('page-previous').disabled,'failed navigation retains previous page');
            check(el('message').textContent.includes('offline fixture'),'failed navigation is explicit');
            const select=()=>{const checkbox=el('rows').querySelector('[data-vf-select]');checkbox.checked=true;checkbox.dispatchEvent(new Event('change',{bubbles:true}));};
            select();el('rows').querySelector('[data-vf-open]').click();await settle();
            check(calls.some(([url])=>url.includes('/items/'+fixture.details[0].id)),'inspector loads full detail on demand');
            const name=el('inspector').querySelector('[data-vf-field="name"]');
            name.value='Unsaved draft';name.dispatchEvent(new Event('input',{bubbles:true}));
            el('page-next').click();await settle();select();
            check(el('rows').querySelector('[data-vf-id]').dataset.vfId===fixture.details[50].id,'second page starts at row 51');
            check(el('selected-count').textContent.startsWith('2 '),'selection spans pages');
            check(el('inspector').querySelector('[data-vf-field="name"]').value==='Unsaved draft','off-page draft preserved');
            check(!el('page-previous').disabled&&!el('page-next').disabled,'page buttons reenabled');
            visibility='hidden';document.dispatchEvent(new Event('visibilitychange'));await settle();
            const count=calls.length;el('refresh').click();await settle();
            check(calls.length===count,'hidden browser does not poll');
            visibility='visible';document.dispatchEvent(new Event('visibilitychange'));await settle();
            check(calls.length>count,'visible browser refreshes immediately');
            check(el('inspector').querySelector('[data-vf-field="name"]').value==='Unsaved draft','return does not overwrite draft');
            el('save').click();await settle();
            check(fixture.details[0].name==='Unsaved draft','off-page save targets original ID');
            const preset=el('bulk-preset');preset.value='auto';preset.dispatchEvent(new Event('change'));await settle();
            const patch=calls.filter(([,options])=>options.method==='PATCH').at(-1);
            check(JSON.parse(patch[1].body).ids.join(',')===[fixture.details[0].id,fixture.details[50].id].join(','),'bulk edit keeps off-page IDs');
            el('down').click();await settle();
            const order=JSON.parse(calls.find(([,options])=>options.method==='PUT')[1].body);
            check(order.ids.length===125&&order.ids[1]===fixture.details[0].id&&order.ids[51]===fixture.details[50].id,'reorder preserves complete global order');
            hold=true;el('refresh').click();await settle();
            const before=browseCount();root.hidden=true;await settle();release();await settle();
            check(browseCount()===before&&calls.at(-1)[0].endsWith('/summary'),'late full response discarded after hiding');
            root.hidden=false;await settle();check(browseCount()===before+1,'return refreshes without waiting for next timer');
            check(!calls.some(([url])=>url==='/api/video-factory'),'no full snapshots requested');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browser, '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup + '<pre id="result">PENDING</pre><script>' + bootstrap +
                         (STATIC / "video-factory.js").read_text(encoding="utf-8") + scenario + '</script>')

    def test_archive_removal_shows_progress_and_keeps_selection_across_pages(self):
        browser = self.browser()
        service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
        service._state["items"] = [delivered("Archive " + str(i)) for i in range(55)]
        for item in service._state["items"]:
            item["archived_at"] = "2026-10-26T10:00:00Z"
        pages = [service.browse(tab="archives", offset=offset) for offset in (0, 50)]
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split('<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]
        bootstrap = "const fixture=" + json.dumps(pages, ensure_ascii=False).replace("<", "\\u003c") + r""";
          const root=document.getElementById('video-factory-workspace');root.hidden=false;
          let rows=fixture.flatMap(page=>page.items),inventory=fixture[0].inventory,revision=fixture[0].revision;
          let finishRemoval,failRemoval=false,failView=false;
          const removals=[],counts=()=>({...fixture[0].counts,archives:rows.length});
          window.PanelForgeLabCore={request:async(url,options={})=>{
            const request=new URL(url,'http://fixture'),q=request.searchParams;
            if(request.pathname.endsWith('/browse')){
              if(failView){failView=false;throw new Error('Refresh unavailable');}
              const tab=q.get('tab'),visible=tab==='archives'?rows:[],offset=Math.min(Number(q.get('offset')||0),Math.max(0,Math.floor((visible.length-1)/50)*50));
              return {...fixture[0],revision,counts:counts(),inventory,items:visible.slice(offset,offset+50),page:{...fixture[0].page,tab,offset,total:visible.length}};
            }
            if(request.pathname.endsWith('/actions/remove')&&options.method==='POST'){
              if(q.get('compact')!=='true')throw new Error('Compact receipt required');
              const body=JSON.parse(options.body);removals.push(body);
              await new Promise(resolve=>finishRemoval=resolve);
              if(failRemoval){failRemoval=false;throw new Error('Removal unavailable');}
              const ids=new Set(body.ids);rows=rows.filter(i=>!ids.has(i.id));inventory=inventory.filter(i=>!ids.has(i.id));revision++;
              return {compact:true,revision,counts:counts(),error_count:0};
            }
            if(request.pathname.endsWith('/summary'))return {compact:true,revision,counts:counts(),error_count:0};
            throw new Error('Unexpected request '+url);
          }};
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setTimeout(r,0));};
            const el=id=>document.getElementById('vf-'+id);
            const select=count=>[...el('rows').querySelectorAll('[data-vf-select]')].slice(0,count).forEach(box=>{box.checked=true;box.dispatchEvent(new Event('change',{bubbles:true}));});
            await settle();root.querySelector('[data-vf-tab="archives"]').click();await settle();
            select(1);el('page-next').click();await settle();select(4);
            const expected=[fixture[0].items[0],...fixture[1].items.slice(0,4)].map(i=>i.id);
            el('remove').click();await settle();
            check(el('message').textContent.includes('5 fiches en cours'),'pending removal is visible');
            check(el('remove').disabled,'duplicate submission disabled');
            check(removals.length===1&&removals[0].ids.join(',')===expected.join(','),'all five IDs include off-page selection');
            check(expected.every(id=>removals[0].revisions[id]===fixture[0].inventory.find(i=>i.id===id).revision),'selected revisions submitted');
            finishRemoval();await settle();
            check(rows.length===50&&el('rows').querySelectorAll('[data-vf-id]').length===50,'empty last page returns to previous page');
            check(el('page-previous').disabled&&el('selected-count').textContent.startsWith('0 '),'page and selection updated');
            check(el('message').textContent==='5 fiches supprimées.','completion is visible');
            select(1);failRemoval=true;el('remove').click();await settle();finishRemoval();await settle();
            check(el('message').textContent==='Removal unavailable'&&!el('remove').disabled,'error visible and retry enabled');
            check(rows.length===50&&el('selected-count').textContent.startsWith('1 '),'failed removal retains selection');
            failView=true;el('remove').click();await settle();finishRemoval();await settle();
            check(rows.length===49&&removals.length===3,'successful mutation is not resubmitted after failed refresh');
            check(el('message').textContent.includes('Actualise la liste'),'receipt without refreshed view does not claim a verified count');
            document.getElementById('result').textContent='PASS';
          }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        self.run_browser(browser, '<meta charset="utf-8"><span id="vf-nav-errors"></span>' + markup + '<pre id="result">PENDING</pre><script>' + bootstrap +
                         (STATIC / "video-factory.js").read_text(encoding="utf-8") + scenario + '</script>')
