"""User-run regressions: visual evidence, persistence and fake LLM responses."""
from dataclasses import asdict, replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from panelforge.application.media_analysis import MediaAnalysisService, MediaAnalysisConflict, parse_result
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, ModelDescriptor, StreamEventKind, StreamPhase
from panelforge.domain.media_analysis import AnalysisFrame, MediaAnalysisInput
from panelforge.features.lab.media_analysis_web import media_analysis_router
from panelforge.infrastructure.media_analysis_images import MediaAnalysisImages
from panelforge.infrastructure.storage import LocalAssetStore
from panelforge.infrastructure.storage.media_analysis import LocalMediaAnalysisStore

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompt_profiles/media.analyze/visual-intention/1.0.1"
RESULT = json.dumps(dict(intention="Une personne traverse la pièce, puis s’arrête devant une fenêtre.",
    observations=["L’image 1 montre la personne près de la porte."], uncertainties=["Le mouvement entre les images n’est pas directement visible."]))


def picture(size=(32, 24), orientation=None):
    image = Image.new("RGB", size, "green")
    output = BytesIO()
    if orientation:
        exif = Image.Exif(); exif[274] = orientation
        image.save(output, format="JPEG", exif=exif)
    else:
        image.save(output, format="PNG")
    return output.getvalue()


class Gateway:
    def __init__(self):
        self.requests = []
        self.response = RESULT
        self.kind = StreamEventKind.COMPLETED

    def list_models(self):
        return (ModelDescriptor("local::vision", "local", "Vision locale"),)

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(StreamEventKind.STATUS, StreamPhase.GENERATING, text="Lecture")
        yield CompletionStreamEvent(self.kind, StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, self.response, call_id="fixture-call"))


class MediaAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.assets = LocalAssetStore(self.temporary.name)
        self.store = LocalMediaAnalysisStore(self.temporary.name)
        self.gateway = Gateway()
        self.service = MediaAnalysisService(gateway=self.gateway, assets=self.assets, store=self.store,
            images=MediaAnalysisImages(), prompt_directory=PROMPTS)
        self.image = self.assets.create(picture(), media_type="image/png")
        self.frames = tuple(AnalysisFrame(self.image.asset_id, f"Image {i}", time) for i, time in enumerate((0, 1, 3)))

    def request(self, **kwargs):
        return MediaAnalysisInput(frames=self.frames, model_id="local::vision", **kwargs)

    def test_optional_times_preserve_order_and_reject_conflicts(self):
        request = self.request()
        self.assertEqual(MediaAnalysisInput.from_dict(asdict(request)), request)
        partial = replace(request, frames=(self.frames[0], replace(self.frames[1], time_seconds=None), self.frames[2]))
        self.assertIsNone(MediaAnalysisInput.from_dict(asdict(partial)).frames[1].time_seconds)
        for frames in (tuple(reversed(self.frames)), (*self.frames[:2], replace(self.frames[2], time_seconds=1))):
            with self.assertRaisesRegex(ValueError, "augmenter"):
                replace(request, frames=frames)
        for time in (-1, float("nan"), float("inf"), True):
            with self.subTest(time=time), self.assertRaises(ValueError):
                replace(self.frames[0], time_seconds=time)
        with self.assertRaises(ValueError): replace(request, duration_seconds=2)
        with self.assertRaises(ValueError): replace(request, frames=self.frames * 6)

    def test_video_clip_bounds_and_relative_capture_times(self):
        request = self.request(source_kind="video", clip_start_seconds=12, clip_end_seconds=20, source_duration_seconds=80)
        self.assertEqual([f.time_seconds for f in request.frames], [0,1,3])
        for changes in (dict(clip_end_seconds=81), dict(clip_end_seconds=12), dict(clip_start_seconds=-1),
                        dict(clip_start_seconds=0, clip_end_seconds=70), dict(frames=(replace(self.frames[0],time_seconds=12),)),
                        dict(frames=(replace(self.frames[0],time_seconds=None),))):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(request, **changes)
        self.assertEqual(replace(request,duration_seconds=6).duration_seconds,6)  # target can differ from source

    def test_one_call_reopen_edit_and_retry_do_not_generate_video(self):
        record = self.service.create(self.request(instruction="Conserver la caméra et changer le décor."))
        self.assertEqual(self.gateway.requests, [])
        done = list(self.service.stream(record["analysis_id"]))[-1]["record"]
        self.assertEqual(done["status"], "succeeded")
        self.assertTrue(done["intention"].startswith("Durée cible : 8 secondes."))
        request = self.gateway.requests[0]
        self.assertEqual(request.operation_id, "media.visual-intention@1.0.1")
        self.assertEqual(len(request.images), 3)
        context = json.loads(request.user_prompt)
        self.assertEqual([f["time_seconds"] for f in context["frames"]], [0,1,3])
        self.assertEqual(context["instruction"], "Conserver la caméra et changer le décor.")
        self.assertNotIn("source_name", context)
        for image in request.images:
            with Image.open(BytesIO(image.content)) as decoded:
                self.assertLessEqual(max(decoded.size),1280)
        edited = self.service.save_intention(record["analysis_id"], "Mon intention corrigée.")
        reopened = LocalMediaAnalysisStore(self.temporary.name).get(record["analysis_id"])
        self.assertEqual(reopened["intention"],"Mon intention corrigée.")
        self.assertEqual(reopened["generated_intention"],done["generated_intention"])
        self.assertEqual(reopened["request"],json.loads(json.dumps(asdict(self.request(instruction="Conserver la caméra et changer le décor.")))))
        self.assertEqual(list(self.service.stream(record["analysis_id"]))[-1]["record"]["intention"],edited["intention"])
        self.assertEqual(len(self.gateway.requests),1)

    def test_recovered_response_is_saved_once_and_logged_without_changing_raw_response(self):
        raw = RESULT[:-2] + "}"
        self.gateway.response = raw
        self.service.application_outcomes = Mock()
        record = self.service.create(self.request())
        with self.assertLogs("panelforge.application.media_analysis", level="WARNING") as logs:
            done = list(self.service.stream(record["analysis_id"]))[-1]["record"]
        self.assertEqual(done["status"], "succeeded")
        self.assertEqual(done["observations"], json.loads(RESULT)["observations"])
        self.assertEqual(done["uncertainties"], json.loads(RESULT)["uncertainties"])
        self.assertTrue(done["generated_intention"].endswith(json.loads(RESULT)["intention"]))
        self.assertIn("fixture-call", logs.output[0])
        self.assertEqual(self.gateway.response, raw)
        reported = self.service.application_outcomes.report_application_outcome.call_args
        self.assertEqual(reported.args[0], "fixture-call")
        self.assertEqual(reported.args[1].value, "accepted")
        self.assertEqual(LocalMediaAnalysisStore(self.temporary.name).get(record["analysis_id"]), done)
        with self.assertNoLogs("panelforge.application.media_analysis"):
            self.assertEqual(list(self.service.stream(record["analysis_id"]))[-1]["record"], done)
        self.assertEqual(len(self.gateway.requests), 1)

    def test_failure_truncation_and_disconnect_release_the_analysis(self):
        record = self.service.create(self.request())
        analysis_id = record["analysis_id"]
        unused = self.service.stream(analysis_id); unused.close()
        stream = self.service.stream(analysis_id); next(stream)
        with self.assertRaises(MediaAnalysisConflict): self.service.stream(analysis_id)
        stream.close()
        self.assertEqual(self.store.get(analysis_id)["status"],"failed")
        for kind, response in ((StreamEventKind.COMPLETED,"not JSON"),(StreamEventKind.TRUNCATED,RESULT),
                               (StreamEventKind.TRUNCATED,RESULT[:-2] + "}")):
            self.gateway.kind,self.gateway.response = kind,response
            with self.assertNoLogs("panelforge.application.media_analysis"):
                last = list(self.service.stream(analysis_id))[-1]
            self.assertEqual(last["kind"],"error")
            self.assertEqual(last["record"]["request"]["frames"][2]["time_seconds"],3)
        self.gateway.kind,self.gateway.response = StreamEventKind.COMPLETED,RESULT
        self.assertEqual(list(self.service.stream(analysis_id))[-1]["record"]["status"],"succeeded")

    def test_orientation_and_original_asset_preserved(self):
        raw = picture((2400,1200),6)
        kind, normalized = MediaAnalysisImages().prepare(raw)
        self.assertEqual(kind,"image/jpeg")
        with Image.open(BytesIO(normalized)) as image: self.assertEqual(image.size,(640,1280))
        self.assertEqual(self.assets.read_bytes(self.image.asset_id),picture())
        for bad in (b"not an image",b"<svg/>"):
            with self.assertRaises(ValueError): MediaAnalysisImages().prepare(bad)

    def test_response_structure_is_checked(self):
        self.assertEqual(parse_result(f"```json\n{RESULT}\n```"),json.loads(RESULT))
        for raw in ("{}", '["text"]', '{"intention":"test"}', RESULT[:-2]):
            with self.assertRaises(ValueError): parse_result(raw)

    def test_http_upload_spec_stream_edit_and_invalid_timeline(self):
        app = FastAPI(); app.include_router(media_analysis_router(self.service))
        with TestClient(app) as client:
            spec=client.get("/api/media-analysis/spec").json()
            self.assertEqual(spec["llm_models"][0],dict(id="local::vision",label="Vision locale",source="local"))
            body=dict(model_id="local::vision",frames=[dict(label="A",time_seconds=0),dict(label="B",time_seconds=3)],duration_seconds=8)
            def upload(metadata, second=picture()):
                return client.post("/api/media-analysis/analyses",data={"metadata":json.dumps(metadata)},
                    files=[("files",("a.png",picture(),"image/png")),("files",("b.png",second,"image/png"))])
            invalid={**body,"frames":[dict(label="A",time_seconds=3),dict(label="B",time_seconds=0)]}
            self.assertEqual(upload(invalid).status_code,422)
            self.assertEqual(upload(body,b"bad").status_code,422)
            self.assertEqual(self.gateway.requests,[])
            response=upload(body); self.assertEqual(response.status_code,201,response.text)
            path=f"/api/media-analysis/analyses/{response.json()['analysis_id']}"
            streamed=client.post(path+"/stream"); self.assertEqual(streamed.status_code,200,streamed.text)
            self.assertIn('"status": "succeeded"',streamed.text)
            saved=client.patch(path+"/intention",json=dict(intention="Une scène corrigée."))
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(client.get(path).json()["intention"],"Une scène corrigée.")
            self.assertEqual(len(client.get("/api/media-analysis/analyses").json()["analyses"]),1)
            client.post(path+"/stream"); self.assertEqual(len(self.gateway.requests),1)


class MediaAnalysisJsonRecoveryTest(unittest.TestCase):
    def test_valid_json_is_unchanged_and_not_logged_as_recovered(self):
        value = json.loads(RESULT)
        value["uncertainties"] = []
        for raw, expected in ((RESULT, json.loads(RESULT)), (json.dumps(value), value),
                              (f"```json\n{RESULT}\n```", json.loads(RESULT))):
            with self.subTest(raw=raw), self.assertNoLogs("panelforge.application.media_analysis"):
                self.assertEqual(parse_result(raw), expected)

    def test_only_missing_final_uncertainties_bracket_is_recovered(self):
        value = dict(intention='Elle regarde le panneau "Arrivée" puis avance.',
            observations=['Le panneau affiche {A} et [B].'],
            uncertainties=['Le texte "uncertainties": [ est visible.', 'Chemin C:\\notes ; suite inconnue.'])
        for indent in (None, 2):
            raw = json.dumps(value, ensure_ascii=False, indent=indent)
            index = raw.rfind("]")
            broken = raw[:index] + raw[index + 1:]
            for response in (broken, f" \n```json\n{broken}\n```\n "):
                with self.subTest(indent=indent), self.assertLogs("panelforge.application.media_analysis") as logs:
                    self.assertEqual(parse_result(response, call_id="recovery-fixture"), value)
                self.assertEqual(len(logs.output), 1)
                self.assertIn("recovery-fixture", logs.output[0])
                self.assertIn("raw response preserved", logs.output[0])

    def test_other_malformed_or_invalid_results_remain_rejected(self):
        value = json.loads(RESULT)
        invalid_values = [
            dict(intention=value["intention"], uncertainties=value["uncertainties"], observations=value["observations"]),
            {**value, "intention": ""}, {**value, "intention": "a" * 15_001},
            {**value, "observations": [1]}, {**value, "uncertainties": [1]},
            {**value, "uncertainties": [" "]}, {**value, "uncertainties": ["a" * 2_001]},
            {**value, "uncertainties": ["a"] * 25}, {**value, "uncertainties": [["a"]]},
            {**value, "uncertainties": [{"detail": "a"}]}, {**value, "uncertainties": []},
            dict(extra="a", **value),
        ]
        malformed = [RESULT[:-2], RESULT[:-3] + "}", RESULT[:-2] + "} trailing text",
            RESULT[:-2] + ",}", "prefix " + RESULT[:-2] + "}",
            '{"intention":"duplicate",' + RESULT[1:-2] + "}"]
        for invalid in invalid_values:
            raw = json.dumps(invalid)
            index = raw.rfind("]")
            malformed.append(raw[:index] + raw[index + 1:])
        for raw in malformed:
            with self.subTest(raw=raw), self.assertNoLogs("panelforge.application.media_analysis"):
                with self.assertRaises(ValueError):
                    parse_result(raw)
