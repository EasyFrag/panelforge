"""User-run speech tests: fake engines/processes only, no model or service calls."""
import asyncio
from dataclasses import asdict, replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from panelforge.application.media_analysis import MediaAnalysisService
from panelforge.application.media_transcription import MediaTranscriptionService, TranscriptionCancelled, TranscriptionBusy
from panelforge.domain.media_analysis import SpeechInput, MediaTranscript, MediaAnalysisInput, AnalysisFrame
from panelforge.features.lab.media_analysis_web import media_analysis_router
from panelforge.infrastructure.media_transcription import PurfviewTranscriber, parse_transcript
from panelforge.infrastructure.media_analysis_images import MediaAnalysisImages
from panelforge.infrastructure.storage import LocalAssetStore
from panelforge.infrastructure.storage.media_analysis import LocalMediaAnalysisStore
from tests.test_media_analysis import Gateway, picture, ROOT, PROMPTS


def transcript(request=None):
    return parse_transcript(dict(language="en", segments=[dict(start=.5, end=2, text="Don't touch it!")]), request or SpeechInput(12, 20))


class FakeEngine:
    def __init__(self):
        self.calls, self.paths = [], []
        self.fail = False

    def availability(self):
        return dict(available=True, message="Fixture")

    def transcribe(self, source, request, cancelled, progress):
        self.calls.append(request); self.paths.append(source)
        assert source.read_bytes() == b"fixture-video"
        progress("transcribing", "Fixture")
        if self.fail:
            raise ValueError("Fixture audio indisponible")
        return transcript(request)


class MediaTranscriptionTest(unittest.TestCase):
    def test_cpu_default_bounds_original_text_and_relative_times(self):
        self.assertEqual(SpeechInput(12,20).device, "cpu")
        result = transcript()
        self.assertIn("[0.50 → 2.00 s] Don't touch it!", result.text)
        self.assertEqual(MediaTranscript.from_dict(asdict(result)), result)
        changed = replace(result, text="[0.50 → 2.00 s] Stay here!", keep_dialogue=True)
        self.assertEqual(changed.original_text, result.text)
        for values in ((0,61), (20,12), (True,2), (float("nan"),3)):
            with self.subTest(values=values), self.assertRaises(ValueError): SpeechInput(*values)
        for kwargs in (dict(language="--help"), dict(device="other")):
            with self.assertRaises(ValueError): SpeechInput(0,8,**kwargs)
        with self.assertRaises(ValueError): MediaTranscript.from_dict({})
        with self.assertRaises(ValueError): replace(result, keep_dialogue="false")
        with self.assertRaises(ValueError): replace(result, text="x"*12001)
        for bad in ({}, {"segments":[dict(start=9,end=10,text="outside")]}, {"segments":[dict(start=True,end=2,text="invalid")]}):
            with self.assertRaises(ValueError): parse_transcript(bad, SpeechInput(12,20))
        empty = parse_transcript(dict(segments=[],language="en"), SpeechInput(12,20))
        self.assertEqual(empty.text, "")
        self.assertEqual(empty.segments, ())

    def test_cli_reuses_install_extracts_only_clip_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = PurfviewTranscriber(executable=root/"faster-whisper-xxl.exe", ffmpeg=root/"ffmpeg.exe", model_directory=root/"_models")
            self.assertFalse(engine.availability()["available"])
            for path in (engine.executable,engine.ffmpeg,engine.model_directory/"faster-whisper-large-v3-turbo/model.bin"):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"fixture")
            self.assertTrue(engine.availability()["available"])
            source = root/"source with spaces.mp4"; source.write_bytes(b"fixture-video")
            calls=[]; scratch=[]
            def fake_run(command, directory, cancelled, label, **kwargs):
                calls.append(command);scratch.append(directory)
                if label=="Extraction audio":
                    with wave.open(str(directory/"excerpt.wav"),"wb") as output:
                        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(b"\0\0"*16000)
                else:
                    (directory/"excerpt.json").write_text(json.dumps(dict(language="en",segments=[dict(start=.5,end=2,text="Hello!")])),encoding="utf-8")
            with patch.object(engine,"_run",side_effect=fake_run):
                result=engine.transcribe(source,SpeechInput(12,20),Event(),lambda *args:None)
            self.assertEqual(result.device,"cpu")
            self.assertEqual(calls[0][calls[0].index("-ss")+1],"12.000000")
            self.assertEqual(calls[0][calls[0].index("-t")+1],"8.000000")
            self.assertEqual(calls[0][calls[0].index("-i")+1],str(source))
            self.assertEqual(calls[1][calls[1].index("--task")+1],"transcribe")
            self.assertEqual(calls[1][calls[1].index("--device")+1],"cpu")
            self.assertEqual(calls[1][calls[1].index("--compute_type")+1],"int8")
            self.assertEqual(calls[1][calls[1].index("--model_dir")+1],str(engine.model_directory))
            self.assertTrue(all(not path.exists() for path in scratch))
            self.assertTrue(source.exists())
            calls.clear()
            with patch.object(engine,"_run",side_effect=fake_run):
                engine.transcribe(source,SpeechInput(12,20,language="auto",device="cuda"),Event(),lambda *args:None)
            self.assertNotIn("--language",calls[1])
            self.assertEqual(calls[1][calls[1].index("--device")+1],"cuda")

    def test_cancellation_terminates_only_owned_process_and_releases_lock(self):
        engine=PurfviewTranscriber(executable="fixture.exe",ffmpeg="fixture-ffmpeg.exe",model_directory="fixture-models")
        process=MagicMock();process.poll.return_value=None
        cancellation=MagicMock();cancellation.is_set.return_value=False;cancellation.wait.return_value=True
        with patch("panelforge.infrastructure.media_transcription.subprocess.Popen",return_value=process) as launch:
            with self.assertRaises(TranscriptionCancelled): engine._run(["fixture.exe"],Path("."),cancellation,"Fixture",timeout=2)
        process.terminate.assert_called_once();process.wait.assert_called_once()
        self.assertFalse(launch.call_args.kwargs["shell"])
        self.assertEqual(launch.call_args.kwargs["env"]["HF_HUB_OFFLINE"],"1")
        service=MediaTranscriptionService(FakeEngine())
        service._lock.acquire()
        with self.assertRaises(TranscriptionBusy): service.transcribe(None,SpeechInput(0,8),Event(),lambda *a:None)
        service._lock.release()
        stopped=Event();stopped.set()
        with self.assertRaises(TranscriptionCancelled): service.transcribe(None,SpeechInput(0,8),stopped,lambda *a:None)
        self.assertTrue(service._lock.acquire(blocking=False));service._lock.release()

    def test_missing_audio_gpu_error_and_timeout_are_explicit(self):
        engine=PurfviewTranscriber(executable="fixture.exe",ffmpeg="fixture-ffmpeg.exe",model_directory="fixture-models")
        for detail, expected in ((b"Stream map '0:a:0' matches no streams.","piste audio"),
                                 (b"CUDA out of memory", "mode CPU")):
            process=MagicMock();process.poll.return_value=1;process.returncode=1
            def launch(*args, **kwargs):
                kwargs["stdout"].write(detail);return process
            with self.subTest(detail=detail), patch("panelforge.infrastructure.media_transcription.subprocess.Popen",side_effect=launch):
                with self.assertRaisesRegex(ValueError,expected): engine._run(["fixture.exe"],Path("."),Event(),"Fixture",timeout=1)
            process.terminate.assert_not_called()
        process=MagicMock();process.poll.return_value=None
        cancellation=MagicMock();cancellation.is_set.return_value=False;cancellation.wait.return_value=False
        with patch("panelforge.infrastructure.media_transcription.subprocess.Popen",return_value=process), patch("panelforge.infrastructure.media_transcription.time.monotonic",side_effect=[0,3]):
            with self.assertRaisesRegex(ValueError,"délai"): engine._run(["fixture.exe"],Path("."),cancellation,"Fixture",timeout=1)
        process.terminate.assert_called_once()

    def test_http_speech_and_analysis_preserve_edits_old_records_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            assets=LocalAssetStore(directory);store=LocalMediaAnalysisStore(directory);gateway=Gateway();engine=FakeEngine()
            service=MediaAnalysisService(gateway=gateway,assets=assets,store=store,images=MediaAnalysisImages(),prompt_directory=PROMPTS,
                speech_prompt_directory=ROOT/"prompt_profiles/media.analyze/visual-intention/1.1.1",transcription=MediaTranscriptionService(engine))
            app=FastAPI();app.include_router(media_analysis_router(service))
            with TestClient(app) as client:
                def post_speech(body):
                    return client.post("/api/media-analysis/transcriptions/stream",data=dict(metadata=json.dumps(body)),files=dict(file=("private name.mp4",b"fixture-video","video/mp4")))
                self.assertTrue(client.get("/api/media-analysis/spec").json()["transcription"]["available"])
                self.assertEqual(engine.calls,[])
                self.assertEqual(post_speech(dict(clip_start_seconds=12,clip_end_seconds=80)).status_code,422)
                self.assertEqual(engine.calls,[])
                response=post_speech(dict(clip_start_seconds=12,clip_end_seconds=20))
                self.assertEqual(response.status_code,200,response.text)
                events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
                evidence=events[-1]["transcript"]
                self.assertEqual(evidence["device"],"cpu")
                self.assertEqual(gateway.requests,[])
                self.assertTrue(all(not path.exists() for path in engine.paths))
                evidence["text"]="[0.50 → 2.00 s] Stay here!";evidence["keep_dialogue"]=True
                body=dict(frames=[dict(label="Frame",time_seconds=0)],model_id="local::vision",source_kind="video",
                    clip_start_seconds=12,clip_end_seconds=20,source_duration_seconds=50,transcript=evidence)
                def analyze_body(value):
                    return client.post("/api/media-analysis/analyses",data=dict(metadata=json.dumps(value)),files=[("files",("frame.png",picture(),"image/png"))])
                self.assertEqual(analyze_body({**body,"clip_end_seconds":21}).status_code,422)
                self.assertEqual(analyze_body({**body,"transcript":{}}).status_code,422)
                saved=analyze_body(body);self.assertEqual(saved.status_code,201,saved.text)
                record=saved.json();path=f"/api/media-analysis/analyses/{record['analysis_id']}"
                response=client.post(path+"/stream");self.assertIn('"completed"',response.text)
                self.assertEqual(len(gateway.requests),1)
                request=gateway.requests[0];context=json.loads(request.user_prompt)
                self.assertEqual(request.operation_id,"media.visual-intention@1.1.1")
                self.assertEqual(context["transcript"]["text"],evidence["text"])
                self.assertNotIn("original_text",context["transcript"])
                self.assertNotIn("segments",context["transcript"])
                self.assertTrue(context["transcript"]["keep_dialogue"])
                restored=client.get(path).json()
                self.assertEqual(restored["request"]["transcript"],evidence)
                self.assertEqual(restored["schema_version"],2)
                # Existing schema 1 records lack transcript and use the visual recipe.
                image=assets.create(picture(),media_type="image/png")
                old=service.create(MediaAnalysisInput(frames=(AnalysisFrame(image.asset_id,"Old"),),model_id="local::vision"))
                old["schema_version"]=1;old["request"].pop("transcript")
                store._path(old["analysis_id"]).write_text(json.dumps(old),encoding="utf-8")
                list(service.stream(old["analysis_id"]))
                self.assertEqual(gateway.requests[-1].operation_id,"media.visual-intention@1.0.1")
                self.assertNotIn("transcript",json.loads(gateway.requests[-1].user_prompt))
                engine.fail=True
                failed=post_speech(dict(clip_start_seconds=12,clip_end_seconds=20))
                self.assertIn('"kind": "error"',failed.text)
                self.assertTrue(all(not path.exists() for path in engine.paths))
                self.assertEqual(client.get(path).json()["request"]["transcript"],evidence)

    def test_stream_disconnect_cancels_worker_and_cleans_upload(self):
        async def scenario():
            ended=Event(); paths=[]
            class BlockingEngine(FakeEngine):
                def transcribe(self, source, request, cancelled, progress):
                    paths.append(source);progress("transcribing","Fixture")
                    if not cancelled.wait(3): raise AssertionError("No cancellation received")
                    ended.set();raise TranscriptionCancelled()
            service=SimpleNamespace(transcription=MediaTranscriptionService(BlockingEngine()))
            router=media_analysis_router(service)
            endpoint=next(route.endpoint for route in router.routes if route.path.endswith("/transcriptions/stream"))
            class Connected:
                async def is_disconnected(self): return False
            response=await endpoint(Connected(),json.dumps(dict(clip_start_seconds=12,clip_end_seconds=20)),UploadFile(BytesIO(b"fixture-video"),filename="source.mp4"))
            await anext(response.body_iterator)
            await response.body_iterator.aclose()
            await response.background()
            for _ in range(100):
                if ended.is_set() and paths and not paths[0].exists(): break
                await asyncio.sleep(.01)
            self.assertTrue(ended.is_set())
            self.assertFalse(paths[0].exists())
        asyncio.run(scenario())
