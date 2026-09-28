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
        html = html.replace('<script src="/app.js?v=20260928.mobile1" defer></script>', "")
        html = html.replace('<link rel="stylesheet" href="/app.css?v=20260928.mobile1">', "<style>" + (directory / "app.css").read_text(encoding="utf-8") + "</style>")
        bootstrap = r"""
          const calls=[],intervals=[];let fail=false;
          Object.defineProperty(window,"isSecureContext",{value:false,configurable:true});
          window.setInterval=(fn,ms)=>{intervals.push([fn,ms]);return intervals.length;};
          let fixture={
            generated_at:1800000000,revision:3,paused:false,cycle_id:"lot",status:"running",
            counts:{delivered:5,total:7},remaining_seconds:900,retained:false,stale:false,finish_at:1800000900,
            machines:[{id:"local_gpu",name:"PC",temperature_c:44,threshold:80,state:"busy"},
                      {id:"remote_gpu",name:"Serveur",temperature_c:65,threshold:85,state:"busy"}],
            thresholds:{local_gpu:80,remote_gpu:85},alerts:[],
            work:[{id:"A",revision:3,active_run:"a-clock",name:"<em>La vidéo</em>",status:"active",remaining_seconds:400,retained:false,
                   steps:[{id:"video",label:"Vidéo",status:"running",remaining_seconds:100}],can_retry:false}],
            results:[{id:"R",name:"Vidéo produite",quality:"DLSS",delivered:true,video_url:"/api/items/R/video"}],
            result_total:1
          };
          window.fetch=async(url,options={})=>{
            calls.push([url,options]);
            if(fail)throw new Error("offline");
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
            check(document.querySelector('[data-play="R"]'),"produced video available");
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
            (directory / "app.js").read_text(encoding="utf-8") + scenario + "</script></body>")
        self.run_browser(browsers[-1], html)
