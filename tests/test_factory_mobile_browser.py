"""Offline browser fixture, executed only by the user; no live Lab requests."""
import json
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class FactoryMobileBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_controls_confirmation_offline_and_video_navigation(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        directory = STATIC / "factory-mobile"
        html = (directory / "index.html").read_text(encoding="utf-8")
        html = html.replace('<script src="/app.js?v=20260930.mobile-status1" defer></script>', "")
        html = html.replace('<script src="/thermal.js?v=20260930.mobile-status1" defer></script>', "")
        html = html.replace('<link rel="stylesheet" href="/app.css?v=20260930.mobile-status1">', "<style>" + (directory / "app.css").read_text(encoding="utf-8") + "</style>")
        bootstrap = r"""
          const calls=[],intervals=[];let fail=false,historyFail=false;
          Object.defineProperty(window,"isSecureContext",{value:false,configurable:true});
          window.setInterval=(fn,ms)=>{intervals.push([fn,ms]);return intervals.length;};
          let fixture={
            generated_at:1800000000,revision:3,paused:false,cycle_id:"lot",status:"running",
            counts:{delivered:5,total:7},remaining_seconds:900,retained:false,stale:false,finish_at:1800000900,
            machines:[{id:"local_gpu",name:"PC",temperature_c:44,threshold:80,state:"idle"},
                      {id:"remote_gpu",name:"Serveur",temperature_c:65,threshold:85,state:"cooling"}],
            thresholds:{local_gpu:80,remote_gpu:85},alerts:[],
            work:[{id:"A",revision:3,active_run:"a-clock",name:"<em>La vidéo</em>",status:"active",remaining_seconds:400,retained:false,
                   steps:[{id:"video",label:"Vidéo",status:"running",remaining_seconds:100}],can_retry:false}],
            results:[{id:"R",name:"Vidéo produite",quality:"Vidéo brute",delivered:true,video_url:"/api/items/R/video"},
                     {id:"U",name:"Brute absente",quality:"Vidéo brute",delivered:true,video_url:null}],
            result_total:2
          };
          window.fetch=async(url,options={})=>{
            calls.push([url,options]);
            if(fail)throw new Error("offline");
            if(url==="/api/thermal-history"){
              if(historyFail)throw new Error("history offline");
              const end=Date.now()/1000;
              return {ok:true,json:async()=>({available:true,generated_at:end,start_at:end-7200,end_at:end,bucket_seconds:15,
                machines:[{id:"remote_gpu",points:[[end-7200,58],[end-1800,86],[end-1785,82],[end-120,81],[end-105,96],[end-90,83]]},
                          {id:"local_gpu",points:[[end-30,79],[end-15,81],[end,78]]}]})};
            }
            if(url.startsWith("/api/push"))return {ok:true,json:async()=>({available:false,registered:false,warning:"fixture"})};
            if(url.includes("/commands/pause"))fixture.paused=true;
            if(url.includes("/commands/resume"))fixture.paused=false;
            if(url.includes("/commands/stop")){fixture.paused=true;fixture.work[0].stopping=true;}
            return {ok:true,json:async()=>structuredClone(fixture)};
          };
        """
        scenario = r"""
          (async()=>{try{
            const check=(ok,label)=>{if(!ok)throw new Error(label);};
            const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setTimeout(r,0));};
            const count=word=>calls.filter(([url])=>url.includes(word)).length;
            await settle();
            check(document.getElementById("delivered").textContent==="5 / 7 livrées","global KPI");
            check(document.querySelector("header #lot-status"),"lot status merged into top bar");
            check(!document.querySelector(".page-title")&&!document.getElementById("machines"),"redundant title and instant tiles stay removed");
            const indicators=[...document.querySelectorAll("[data-machine-status]")];
            check(indicators.length===2&&indicators.every(node=>node.querySelector("svg")),"two compact machine icons in top bar");
            check(indicators[0].textContent.includes("Local")&&indicators[0].textContent.includes("Idle")&&indicators[0].textContent.includes("44°"),"local live state and temperature");
            check(indicators[1].textContent.includes("Cloud")&&indicators[1].textContent.includes("Cooling Down")&&indicators[1].textContent.includes("65°"),"cloud live state and temperature");
            check(document.getElementById("threshold-remote").value==="84","default server alert threshold");
            const cards=[...document.querySelectorAll("[data-thermal]")];
            check(cards.map(n=>n.dataset.thermal).join()==="remote_gpu,local_gpu","server then local history");
            check(cards.every(card=>card.querySelector(".thermal-exceedances")),"both charts show recent exceedances");
            check(cards[0].querySelectorAll(".thermal-exceedances li").length===2&&cards[0].textContent.includes("96°"),"server exceedances are grouped by episode");
            check(cards[1].querySelectorAll(".thermal-exceedances li").length===1,"local exceedances use the same compact list");
            check(!cards.some(card=>card.textContent.includes("Min ")||card.textContent.includes("Sous 40")),"low-temperature summaries are removed");
            const chart=cards[0].querySelector("svg");
            const labels=[...chart.querySelectorAll("text")].map(node=>node.textContent);
            check(labels.includes("60")&&labels.includes("90")&&labels.includes("−2 h")&&!labels.includes("40"),"two-hour chart uses a 60 to 90 scale");
            chart.dispatchEvent(new KeyboardEvent("keydown",{key:"End",bubbles:true}));
            check(cards[0].querySelector(".thermal-reading").textContent.includes("83 °C"),"chart reads an actual sample");
            const path=cards[0].querySelector(".thermal-line.hot").getAttribute("d");
            historyFail=true;document.getElementById("refresh").click();await settle();
            check(document.getElementById("thermal-status").textContent.includes("Historique conservé"),"failed refresh preserves thermal history");
            check(document.querySelector('[data-thermal="remote_gpu"] .thermal-line.hot').getAttribute("d")===path,"failed refresh keeps the same peak path");
            historyFail=false;document.getElementById("refresh").click();await settle();
            check(document.getElementById("thermal-status").hidden,"thermal recovery clears warning");
            check(document.getElementById("active").textContent.includes("<em>La vidéo</em>"),"names rendered as text");
            check(!document.querySelector("#active em"),"no markup injection");
            document.getElementById("pause").click();await settle();
            check(count("/commands/pause")===1,"one pause request");
            check(document.getElementById("pause").textContent==="Reprendre la file","resume available");
            document.getElementById("pause").click();await settle();
            check(count("/commands/resume")===1,"one resume request");
            document.getElementById("stop").click();
            check(document.getElementById("confirm").open,"stop needs confirmation");
            check(count("/commands/stop")===0,"opening dialog cannot stop");
            document.getElementById("confirm").close("cancel");await settle();
            check(count("/commands/stop")===0,"cancel has no side effect");
            document.getElementById("stop").click();
            document.getElementById("confirm").close("confirm");await settle();
            check(count("/commands/stop")===1,"explicit stop sent once");
            const body=JSON.parse(calls.find(([url])=>url.includes("/commands/stop"))[1].body);
            check(body.ids.join()==="A"&&body.revisions.A===3&&body.active_runs.A==="a-clock","stop carries displayed identities and revisions");
            document.querySelector('[data-tab="videos"]').click();
            check(!document.getElementById("panel-videos").hidden,"video tab visible");
            check(document.getElementById("controls").hidden,"controls do not cover video gallery");
            check(!document.querySelector('[data-play="R"]').disabled,"raw produced video available");
            check(document.querySelector('[data-play="R"]').closest(".result").textContent.includes("Vidéo brute"),"raw quality label matches the stream");
            const unavailable=document.querySelector('[data-play="U"]');
            check(unavailable.disabled&&!unavailable.querySelector(".play"),"missing raw video has no play action");
            check(unavailable.closest(".result").textContent.includes("Vidéo brute indisponible"),"missing raw video stays visible with a clear explanation");
            unavailable.click();
            check(!document.getElementById("player").open,"missing raw video cannot open another quality");
            document.querySelector('[data-tab="follow"]').click();
            fail=true;document.getElementById("refresh").click();await settle();
            check(document.getElementById("pause").disabled&&document.getElementById("stop").disabled,"offline controls disabled");
            check(document.getElementById("remaining").textContent.includes("min"),"last known budget survives disconnection");
            const commands=calls.filter(([url])=>url.includes("/commands/")).length;
            fail=false;document.getElementById("refresh").click();await settle();
            check(calls.filter(([url])=>url.includes("/commands/")).length===commands,"reconnection never replays commands");
            check(!document.getElementById("pause").disabled,"fresh snapshot restores controls");
            document.getElementById("result").textContent="PASS";
          }catch(error){document.getElementById("result").textContent="FAIL: "+error.stack;}})();
        """
        html = html.replace("</body>", '<pre id="result">PENDING</pre><script>' + bootstrap +
            (directory / "thermal.js").read_text(encoding="utf-8") +
            (directory / "app.js").read_text(encoding="utf-8") + scenario + "</script></body>")
        self.run_browser(browsers[-1], html)
