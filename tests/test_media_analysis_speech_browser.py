"""User-run browser checks with fake transcription; no real speech model."""
import os
from pathlib import Path
import unittest

from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class MediaAnalysisSpeechBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_optional_speech_cpu_default_edits_staleness_cancellation_and_reopen(self):
        browsers=sorted((Path(os.environ.get("LOCALAPPDATA",""))/"ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers: self.skipTest("local Chromium not installed")
        markup='<main id="media-analysis-workspace"'+(STATIC/"index.html").read_text(encoding="utf-8").split('<main id="media-analysis-workspace"',1)[1].split('</main>',1)[0]+'</main>'
        bootstrap="""
        const requests=[];let fail=false,block=false;
        const original={text:"[0.50 → 2.00 s] Don't touch it!",original_text:"[0.50 → 2.00 s] Don't touch it!",
          segments:[{start_seconds:.5,end_seconds:2,text:"Don't touch it!"}],language:'en',detected_language:'en',device:'cpu',
          engine:'purfview-faster-whisper-xxl',model:'large-v3-turbo',clip_start_seconds:12,clip_end_seconds:20,keep_dialogue:false};
        window.PanelForgeLabCore={async streamRequest(url,options,onEvent){
          const request=JSON.parse(options.body.get('metadata'));requests.push({url,request,file:options.body.get('file')});
          if(fail)throw new Error('GPU fixture unavailable');
          if(block)await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true}));
          onEvent({kind:'status',text:'Transcription fixture',phase:'transcribing'});
          onEvent({kind:'completed',transcript:{...structuredClone(original),...request}});
        }};
        """
        scenario="""
        (async()=>{try{
          const check=(ok,label)=>{if(!ok)throw new Error(label);};
          const el=id=>document.getElementById('ma-'+id);
          const settle=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setTimeout(r,0));};
          const context={sourceKind:'video',clip:{start:12,end:20,duration:40},video:new File(['fixture'],'private name.mp4',{type:'video/mp4'})};
          let busy=false,changes=0;
          const speech=PanelForgeAnalysisSpeech.create({el,context:()=>context,onChange(){changes++;speech.update(busy);},
            setBusy(value){busy=value;speech.update(value);},message(text){el('message').textContent=text;}});
          speech.setSpec({available:true,message:'Fixture',video_bytes:1024});speech.update(false);
          check(!el('speech-enabled').checked && speech.metadata()===null,'speech is optional by default');
          check(el('speech-device').value==='cpu','CPU default in markup');
          check(requests.length===0,'opening does not load a model');
          el('speech-enabled').checked=true;el('speech-enabled').dispatchEvent(new Event('change'));
          check(speech.validation(),'enabled speech requires a result');
          el('speech-transcribe').click();await settle();
          check(!busy && requests.length===1,'one explicit local transcription');
          check(requests[0].request.device==='cpu' && requests[0].request.language==='en','CPU and English defaults passed to server');
          check(requests[0].request.clip_start_seconds===12 && requests[0].request.clip_end_seconds===20,'only selected clip requested');
          check(requests[0].file.name==='private name.mp4','video passed only to local transcription route');
          check(!speech.validation() && !speech.metadata().keep_dialogue,'dialogue is context only by default');
          el('speech-text').value='[0.50 → 2.00 s] Stay here!';el('speech-text').dispatchEvent(new Event('input'));
          el('speech-keep').checked=true;el('speech-keep').dispatchEvent(new Event('change'));
          const edited=speech.metadata();
          check(edited.text.includes('Stay here') && edited.original_text===original.original_text && edited.keep_dialogue,'edited words and provenance stay separate');
          el('speech-enabled').checked=false;el('speech-enabled').dispatchEvent(new Event('change'));
          check(speech.metadata()===null && !speech.validation(),'visual-only analysis remains available');
          el('speech-enabled').checked=true;el('speech-enabled').dispatchEvent(new Event('change'));
          check(speech.metadata().text===edited.text,'toggle preserves corrected draft');
          context.clip.end=21;speech.update(false);
          check(speech.validation() && !el('speech-stale').hidden,'clip change prevents stale transcript');
          context.clip.end=20;speech.update(false);
          el('speech-language').value='fr';el('speech-language').dispatchEvent(new Event('change'));
          check(speech.validation(),'language change requires retranscription');
          el('speech-language').value='en';el('speech-language').dispatchEvent(new Event('change'));
          fail=true;el('speech-device').value='cuda';el('speech-transcribe').click();await settle();
          check(el('speech-text').value===edited.text && !busy,'failed GPU run preserves draft');
          fail=false;block=true;el('speech-transcribe').click();await settle();
          check(busy && el('cancel').textContent.includes('transcription'),'transcription has explicit cancel');
          check(speech.cancel(),'cancel targets speech');await settle();
          check(!busy && el('speech-text').value===edited.text,'cancellation preserves edited words');
          block=false;speech.reset();context.video=null;speech.restore(edited);speech.update(false);
          check(el('speech-transcribe').disabled && !el('speech-text').disabled,'reopen requires video only for retranscription');
          check(speech.metadata().text===edited.text && speech.metadata().keep_dialogue,'reopen restores text and dialogue option');
          el('speech-restore').click();
          check(el('speech-text').value===original.original_text,'original words can be restored');
          speech.reset();speech.update(false);
          check(el('speech-device').value==='cpu' && !el('speech-enabled').checked,'new source resets to CPU and speech off');
          context.sourceKind='images';speech.update(false);check(el('speech-panel').hidden,'no audio controls for image series');
          check(requests.every(r=>r.url==='/api/media-analysis/transcriptions/stream'),'no LLM or render calls');
          document.getElementById('result').textContent='PASS';
        }catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
        """
        source=(STATIC/"media-analysis-speech.js").read_text(encoding="utf-8")
        html='<meta charset="utf-8"><pre id="result">PENDING</pre>'+markup+'<script>'+bootstrap+'</script><script>'+source+'</script><script>'+scenario+'</script>'
        self.run_browser(browsers[-1],html)
