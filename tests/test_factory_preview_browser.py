"""User-run browser regressions with synthetic data and no live Lab requests."""
import json
import os
from pathlib import Path
import unittest

from panelforge.domain.video_factory import configuration, new_item, PRESETS
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class FactoryPreviewBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def browser(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob(
            "chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        return browsers[-1]

    def test_preview_survives_polls_slow_requests_and_errors_but_invalidates_changed_selection(self):
        browser = self.browser()
        markup = """<meta charset="utf-8"><main id="video-factory-workspace">
          <div id="vf-monitor-summary"></div><div id="vf-monitor-preview"></div>
          <div data-vf-monitor-row="A"></div></main><pre id="result">PENDING</pre>"""
        scenario = r"""
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          let clock=0,nextTimer=0,chosen=true;
          const timers=new Map(),requests=[];
          Object.defineProperty(performance,"now",{configurable:true,value:()=>clock});
          window.setTimeout=fn=>{timers.set(++nextTimer,fn);return nextTimer;};
          window.clearTimeout=id=>timers.delete(id);
          const fire=()=>{
            check(timers.size===1,"one debounced request");
            const [id,fn]=timers.entries().next().value;timers.delete(id);fn();
          };
          const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
          const item={id:"A",revision:1,ready:true,status:"preparation",steps:{video:{status:"pending"}}};
          const state={data:{revision:1,items:[item],monitoring:{
            generated_at:1800000000,stale:false,counts:{total:0},items:{}}},
            tab:"preparation",dirty:false};
          const root=document.getElementById("video-factory-workspace");
          const monitor=window.PanelForgeFactoryMonitor.create({
            root,escape:s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;"),
            request:(path,method,body)=>new Promise((resolve,reject)=>requests.push({path,method,body,resolve,reject})),
            getState:()=>state,getSelection:()=>chosen?[item]:[]
          });
          const row=root.querySelector("[data-vf-monitor-row]");
          const summary=document.getElementById("vf-monitor-preview");
          const prediction=seconds=>({generated_at:1800000000+clock/1000,stale:false,
            remaining_seconds:seconds,low_seconds:seconds-60,high_seconds:seconds+60,
            items:{A:{remaining_seconds:seconds,low_seconds:seconds-60,high_seconds:seconds+60,
              video_start_in:60,steps:{}}}});
          const poll=()=>{
            clock+=5000;state.data.revision++;
            state.data.monitoring.generated_at+=5;monitor.received();monitor.previewSelection();monitor.render();
          };
          monitor.previewSelection();fire();
          requests[0].resolve(prediction(600));await settle();
          check(row.textContent.includes("Prêt vers"),"initial row estimate");
          check(summary.textContent.includes("10 min"),"initial selection estimate");
          poll();
          check(row.textContent.includes("Prêt vers"),"poll never clears previous rows");
          check(!summary.textContent.includes("Estimation…"),"poll never replaces estimate with a spinner");
          fire();poll();poll();
          check(requests.length===2&&timers.size===0,"slow request is not cancelled by unrelated progress");
          check(row.textContent.includes("Prêt vers"),"slow recalculation preserves layout");
          requests[1].resolve(prediction(540));await settle();
          check(summary.textContent.includes("9 min"),"slow response still accepted for unchanged selection");
          poll();fire();requests[2].reject(new Error("offline"));await settle();
          check(row.textContent.includes("Estimation conservée"),"refresh error keeps and labels prior estimate");
          check(summary.textContent.includes("9 min")&&!summary.textContent.includes("Indisponible"),"error keeps numeric header");
          check(summary.textContent.includes("Fin —"),"error does not promise a live end time");
          poll();fire();requests[3].resolve(prediction(480));await settle();
          check(row.textContent.includes("Prêt vers")&&summary.textContent.includes("8 min"),"recovery replaces retained estimate");

          poll();fire();
          item.revision++;monitor.previewSelection();fire();
          check(row.textContent==="","preset revision invalidates old forecast immediately");
          check(summary.textContent.includes("Estimation…"),"changed configuration awaits its own calculation");
          requests[4].resolve(prediction(60));await settle();
          check(row.textContent==="","late old-configuration response ignored");
          requests[5].resolve(prediction(1200));await settle();
          check(summary.textContent.includes("20 min"),"new preset gets its own forecast");
          check(requests[5].body.revisions.A===2,"new request uses current item revision");
          state.dirty=true;monitor.previewSelection();
          check(summary.hidden&&row.textContent==="","unsaved settings invalidate preview");
          state.dirty=false;monitor.previewSelection();fire();
          chosen=false;monitor.previewSelection();
          requests[6].resolve(prediction(1800));await settle();
          check(summary.hidden&&row.textContent==="","deselection rejects outstanding response");
          check(requests.every(r=>r.path==="/estimate"&&r.method==="POST"),"forecast-only requests");
          document.getElementById("result").textContent="PASS";
        }catch(error){document.getElementById("result").textContent="FAIL: "+error.stack;}})();
        """
        self.run_browser(browser, markup + "<script>" +
                         (STATIC / "video-factory-monitor.js").read_text(encoding="utf-8") +
                         scenario + "</script>")


    def test_unknown_production_wait_retains_each_known_preview_and_stable_row_height(self):
        browser = self.browser()
        markup = """<meta charset="utf-8"><main id="video-factory-workspace"
          class="vf-workspace" data-vf-view="preparation">
          <div id="vf-monitor-summary"></div><div id="vf-monitor-preview"></div>
          <table style="width:240px"><tbody>
            <tr><td class="vf-state"><div class="vf-eta-row" data-vf-monitor-row="A"></div></td></tr>
            <tr><td class="vf-state"><div class="vf-eta-row" data-vf-monitor-row="B"></div></td></tr>
          </tbody></table></main><pre id="result">PENDING</pre>"""
        scenario = r"""
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          let clock=0,timerId=0;const timers=new Map(),requests=[];
          Object.defineProperty(performance,"now",{configurable:true,value:()=>clock});
          window.setTimeout=fn=>{timers.set(++timerId,fn);return timerId;};
          window.clearTimeout=id=>timers.delete(id);
          const items=["A","B"].map(id=>({id,revision:1,ready:true,status:"preparation",
            steps:{video:{status:"pending"},dlss:{status:"pending"}}}));
          let selected=[...items];
          const state={data:{revision:1,items,monitoring:{
            generated_at:1800000000,stale:false,counts:{total:0},items:{}}},
            tab:"preparation",dirty:false};
          const root=document.getElementById("video-factory-workspace");
          const monitor=window.PanelForgeFactoryMonitor.create({
            root,escape:s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;"),
            request:(path,method,body)=>new Promise(resolve=>requests.push({path,method,body,resolve})),
            getState:()=>state,getSelection:()=>selected
          });
          const a=root.querySelector('[data-vf-monitor-row="A"]');
          const b=root.querySelector('[data-vf-monitor-row="B"]');
          const summary=document.getElementById("vf-monitor-preview");
          const prediction=(leftA,leftB)=>{
            const values={A:leftA,B:leftB},rows={};
            for(const [id,seconds] of Object.entries(values)){
              rows[id]={remaining_seconds:seconds,low_seconds:seconds,high_seconds:seconds,
                video_start_in:seconds===null?null:60,video_ready_in:seconds,
                reason:seconds===null?"En attente de la machine ou d’un traitement précédent":null,
                steps:{video:{seconds:120,low:100,high:150,reason:"Comparable",samples:12},
                       dlss:{seconds:60,low:50,high:80,reason:"Comparable",samples:8}}};
            }
            const total=selected.every(i=>Number.isFinite(values[i.id]))
              ?Math.max(...selected.map(i=>values[i.id])):null;
            return {generated_at:1800000000+clock/1000,stale:false,items:rows,
              remaining_seconds:total,low_seconds:total,high_seconds:total};
          };
          const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
          const respond=async(a,b)=>{
            clock+=5000;state.data.revision++;
            state.data.monitoring.generated_at=1800000000+clock/1000;
            monitor.received();monitor.previewSelection();monitor.render();
            check(timers.size===1,"one current request");
            const [id,fn]=timers.entries().next().value;timers.delete(id);fn();
            const value=prediction(a,b),before=JSON.stringify(value);
            requests.at(-1).resolve(value);await settle();
            check(JSON.stringify(value)===before,"response is never mutated by retention");
          };

          await respond(null,null);
          check(a.textContent.includes("En attente"),"initial unknown forecast stays unknown");
          check(summary.textContent.includes("À préciser"),"no total invented without history");
          await respond(1000,1200);
          const height=a.getBoundingClientRect().height;
          check(a.textContent.includes("Prêt vers")&&summary.textContent.includes("20 min"),"known forecast shown");
          await respond(null,600);
          check(a.textContent.includes("≈ 17 min")&&a.textContent.includes("Estimation conservée"),"unknown row retains known work budget");
          check(b.textContent.includes("Prêt vers")&&b.textContent.includes("10 min"),"known row continues updating");
          check(summary.textContent.includes("17 min")&&summary.textContent.includes("Fin —"),"mixed total uses known budgets without promising finish");
          check(a.getBoundingClientRect().height===height,"wait does not shrink the row");
          for(let i=0;i<3;i++)await respond(null,null);
          check(a.textContent.includes("17 min")&&b.textContent.includes("10 min"),"repeated unknown replies cannot erase or erode retained budgets");
          clock+=60000;monitor.tick();
          check(a.textContent.includes("17 min")&&summary.textContent.includes("17 min"),"retained budgets freeze through long waits");
          check(a.getBoundingClientRect().height===height,"stale wait keeps row height");
          await respond(300,600);
          check(!a.textContent.includes("conservée")&&a.textContent.includes("Prêt vers"),"fresh forecast supersedes retained values");
          check(summary.textContent.includes("10 min")&&!summary.textContent.includes("Fin —"),"live finish returns with valid forecast");

          items[0].revision++;
          await respond(null,null);
          check(!a.textContent.includes("conservée")&&summary.textContent.includes("À préciser"),"new preset cannot inherit a previous configuration budget");
          await respond(400,800);
          selected=[items[0]];
          await respond(null,null);
          check(!a.textContent.includes("conservée")&&b.textContent==="","changed selection invalidates retained context");
          check(requests.every(r=>r.path==="/estimate"&&r.method==="POST"),"only read-only forecast requests");
          document.getElementById("result").textContent="PASS";
        }catch(error){document.getElementById("result").textContent="FAIL: "+error.stack;}})();
        """
        css = (STATIC / "video-factory.css").read_text(encoding="utf-8") + (
            STATIC / "video-factory-monitor.css").read_text(encoding="utf-8")
        self.run_browser(browser, markup + "<style>" + css + "</style><script>" +
                         (STATIC / "video-factory-monitor.js").read_text(encoding="utf-8") +
                         scenario + "</script>")

    def test_result_sort_keeps_groups_selection_source_order_and_poll_updates(self):
        browser = self.browser()
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = '<main id="video-factory-workspace"' + html.split(
            '<main id="video-factory-workspace"', 1)[1].split('<main id="stories-workspace"', 1)[0]

        def result(identity, minute, episode=False, index=0):
            item = new_item(identity, configuration(), dict(kind="episode" if episode else "image",
                id="episode" if episode else identity, group="Histoire", index=index), identity)
            item.update(id=identity, status="succeeded", ready=True, issues=[], can_archive=True,
                        created_at="2026-09-28T08:00:00Z")
            for step in item["steps"].values():
                step["status"] = "succeeded"
            item["steps"]["video"]["finished_at"] = (
                f"2026-09-28T09:{minute:02d}:00Z" if minute is not None else "invalid")
            return item

        items = [result("A", 1), result("E1", 2, True, 0), result("E2", 4, True, 1),
                 result("B", 3), result("C", 3), result("unknown-date", None)]
        preparation = new_item("P", configuration(), dict(kind="image"), "P")
        preparation.update(id="P", ready=False, issues=["Image requise"])
        items.append(preparation)
        fixture = dict(items=items, presets=PRESETS, revision=1, paused=False, machines={}, scheduler_error=None)
        bootstrap = "let fixture=" + json.dumps(fixture, ensure_ascii=False) + r""";
          const calls=[],intervals=[];
          let nextResponse=null;
          window.setInterval=(fn,ms)=>{intervals.push([fn,ms]);return intervals.length;};
          window.fetch=()=>{throw new Error("Unexpected network request");};
          window.PanelForgeLabNavigation={switchView(){}};
          window.PanelForgeLabCore={request:async(url,options={})=>{
            calls.push([url,options.method||"GET"]);
            if(url!=="/api/video-factory"||(options.method||"GET")!=="GET")
              throw new Error("Unexpected mutation "+url);
            return structuredClone(nextResponse||fixture);
          }};
        """
        scenario = r"""
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const settle=async()=>{for(let i=0;i<15;i++)await new Promise(resolve=>setTimeout(resolve,0));};
          const rows=()=>[...document.querySelectorAll("#vf-rows [data-vf-id]")].map(n=>n.dataset.vfId).join(",");
          const sort=document.getElementById("vf-results-sort");
          const change=value=>{sort.value=value;sort.dispatchEvent(new Event("change"));};
          const chooseTab=async tab=>{
            document.querySelector('[data-vf-tab="'+tab+'"]').click();await settle();
          };
          await settle();
          check(sort.hidden,"sort is absent from preparation");
          await chooseTab("results");
          check(!sort.hidden&&sort.value==="chronological","default sort preserves habitual order");
          check(rows()==="A,E1,E2,B,C,unknown-date","default rows unchanged");
          const selected=document.querySelector('[data-vf-id="B"] [data-vf-select]');
          selected.checked=true;selected.dispatchEvent(new Event("change",{bubbles:true}));
          const original=fixture.items.map(i=>i.id).join(",");
          change("newest");
          check(rows()==="E1,E2,B,C,A,unknown-date","newest finished group first, stable ties and fallback dates");
          check(document.querySelectorAll("#vf-rows .vf-group").length===1,"story remains a single block");
          check(document.querySelector('[data-vf-id="B"] [data-vf-select]').checked,"sorting preserves selection");
          check(document.getElementById("vf-selected-count").textContent.includes("1"),"selection count stable");
          change("chronological");
          check(rows()==="A,E1,E2,B,C,unknown-date","original order can be restored");
          change("newest");
          const old=structuredClone(fixture);
          fixture.revision=2;fixture.items[0].steps.video.finished_at="2026-09-28T09:06:00Z";
          document.getElementById("vf-refresh").click();await settle();
          check(rows()==="A,E1,E2,B,C,unknown-date"&&sort.value==="newest","live arrivals keep chosen sort");
          nextResponse=old;document.getElementById("vf-refresh").click();await settle();nextResponse=null;
          check(rows()==="A,E1,E2,B,C,unknown-date","late older snapshot cannot roll back displayed state");
          await chooseTab("preparation");
          check(sort.hidden&&rows()==="P","preparation order is independent of result sorting");
          await chooseTab("results");
          check(sort.value==="newest","sort survives tab navigation");
          check(fixture.items.map(i=>i.id).join(",")===original,"source queue order is never changed");
          check(calls.every(([url,method])=>url==="/api/video-factory"&&method==="GET"),"sorting never sends production commands");
          document.getElementById("result").textContent="PASS";
        }catch(error){document.getElementById("result").textContent="FAIL: "+error.stack;}})();
        """
        self.run_browser(browser, '<meta charset="utf-8">' + markup +
            '<span id="vf-nav-errors"></span><pre id="result">PENDING</pre><script>' + bootstrap +
            (STATIC / "video-factory.js").read_text(encoding="utf-8") + scenario + "</script>")
