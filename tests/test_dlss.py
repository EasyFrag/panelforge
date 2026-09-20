"""DLSS contracts: all render/process gateways are fake. Run by the user only."""

from dataclasses import asdict, replace
from contextlib import contextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from panelforge.application.dlss import DlssService
from panelforge.application.dlss_candidates import DlssCandidates
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.h3_render import H3RenderProject, H3RenderInputMode, H3RenderAttempt, H3RenderAttemptStatus
from panelforge.domain.video_lab import VideoLabSettings, VideoAspectRatio
from panelforge.features.lab.dlss_web import register_dlss_routes
from panelforge.infrastructure.comfy import ComfyImageRef
from panelforge.infrastructure.dlss_media import DlssMedia
from panelforge.infrastructure.dlss_outputs import DlssOutputs
from panelforge.infrastructure.dlss_video_exports import DlssVideoExporter
from panelforge.infrastructure.dlss_runtime import LocalDlssRuntime
from panelforge.infrastructure.presets.dlss import DlssWorkflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore
from panelforge.infrastructure.storage.h3_render_projects import LocalH3RenderProjectStore, _serialize as h3_dict, _deserialize as h3_load
from panelforge.infrastructure.storage.krea2_assisted import _serialize as assisted_dict, _deserialize as assisted_load
from panelforge.infrastructure.storage.krea2_edits import _to_dict as edit_dict, _from_dict as edit_load
from panelforge.infrastructure.storage.dlss_jobs import LocalDlssJobs
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from tests.test_krea2_assisted_branches import fixture
from tests.test_krea2_retouch import RetouchServiceTest


ROOT = Path(__file__).resolve().parents[1]


def png(size=(64, 96), color="red", mode="RGB", **kwargs):
    stream = BytesIO()
    Image.new(mode, size, color).save(stream, format="PNG", **kwargs)
    return stream.getvalue()


class FakeComfy:
    base_url = "http://127.0.0.1:18188"

    def __init__(self):
        self.submissions = []
        self.uploads = []
        self.history = {}
        self.output = png((128, 192))
        self.fail_download = False
        self.ambiguous = False
        self.output_root = None

    def upload_image(self, content, *, filename):
        self.uploads.append(content)
        return ComfyImageRef(filename, "", "input")

    def submit_workflow(self, graph, *, prompt_id):
        self.submissions.append((prompt_id, graph))
        outputs = {}
        for node, value in graph.items():
            if value["class_type"] in {"SaveImage", "SaveVideo"}:
                extension = ".mp4" if value["class_type"] == "SaveVideo" else ".png"
                filename = (prompt_id if self.output_root else "output") + extension
                if self.output_root:
                    self.output_root.mkdir(parents=True, exist_ok=True)
                    (self.output_root / filename).write_bytes(self.output)
                outputs[node] = {"images": [{"filename": filename, "type": "output", "subfolder": ""}]}
            if value["class_type"] == "PreviewAny":
                outputs[node] = {"text": [json.dumps({"nr_upscaling_active": True})]}
        self.history[prompt_id] = {"status": {"completed": True, "status_str": "success"}, "outputs": outputs}
        if self.ambiguous:
            raise TimeoutError("POST reply lost")
        return prompt_id

    def get_history(self, prompt_id):
        return {prompt_id: self.history[prompt_id]} if prompt_id in self.history else {}

    def get_queue(self):
        return SimpleNamespace(running=(), pending=())

    def download_output(self, **kwargs):
        if self.fail_download:
            raise OSError("download interrupted")
        return self.output


class DlssTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = LocalAssetStore(self.root, external_roots=(self.root / "dlss-output",))
        self.store = LocalKrea2AssistedProjectStore(self.root)
        self.asset = self.assets.create(png(), "image/png")
        base = fixture()
        self.project = self.store.create(replace(base, attempts=(replace(base.attempts[0], output_asset_id=self.asset.asset_id),)))
        self.assisted = SimpleNamespace(projects=self.store, _lock=RLock())
        self.candidates = DlssCandidates(edit=None, assisted=self.assisted, h3=None)
        self.comfy = FakeComfy()
        self.runtime = Mock()
        self.runtime.ready.return_value = True
        self.runtime.status.return_value = {"state": "ready", "owned": True}
        self.jobs = LocalDlssJobs(self.root)
        self.workflows = {"image": DlssWorkflow(ROOT / "workflows/image.upscale/dlss/0.1.0"),
                          "video": DlssWorkflow(ROOT / "workflows/video.upscale/dlss/0.1.0"),
                          "video-smooth": DlssWorkflow(ROOT / "workflows/video.upscale/dlss-smooth/0.1.0")}
        self.media = DlssMedia(ffmpeg="never-run", ffprobe="never-run")
        self.service = self.make_service()

    def make_service(self):
        service = DlssService(jobs=self.jobs, runtime=self.runtime, comfy=self.comfy, assets=self.assets, media=self.media,
                              workflows=self.workflows, candidates=self.candidates, poll_interval=0, run_timeout=1)
        service.wake = Mock()  # Tests explicitly drain the fake worker; no background process.
        return service

    def queue(self, request_id="first", **kwargs):
        return self.service.queue(owner="assisted", owner_id=self.project.project_id,
            attempt_id=self.project.attempts[0].attempt_id, settings=DlssSettings(**kwargs), request_id=request_id)

    def complete(self, job):
        self.service._drain()
        result = self.jobs.get(job["job_id"])
        self.assertEqual(result["status"], "succeeded", result.get("error"))
        return result

    def test_preview_and_queue_never_start_runtime_and_duplicate_request_is_stable(self):
        job = self.queue()
        self.assertEqual(job, self.queue())
        self.assertEqual(len(self.jobs.list()), 1)
        self.runtime.ensure_ready.assert_not_called()
        self.assertEqual(self.comfy.submissions, [])
        with self.assertRaises(ValueError):
            self.queue(intensity=0.5)
        result = self.complete(job)
        project = self.store.get(self.project.project_id)
        self.assertEqual(project.turns, self.project.turns)
        self.assertEqual(project.attempts[0], self.project.attempts[0])
        attempt = project.attempts[-1]
        self.assertEqual(attempt.dlss.width, 128)
        self.assertEqual(attempt.kind, "dlss")
        self.assertIsNone(attempt.execution_id)
        self.assertEqual(assisted_load(assisted_dict(project)), project)
        self.assertEqual(self.candidates.attach(result, self.workflows["image"]), attempt.attempt_id)
        self.assertEqual(len(self.store.get(project.project_id).attempts), 2)
        fork = project.branch_from_attempt(attempt.attempt_id, "dlss-branch")
        self.assertEqual(fork.feedback_attempt_id, attempt.attempt_id)
        self.assertNotEqual(fork.turns, project.turns)
        exporter = LocalKrea2CreationExporter(self.root / "exports")
        exporter.export(project, project.attempts[0], self.assets)
        directory = Path(exporter.export(project, attempt, self.assets))
        self.assertEqual((directory / "creation_001.png").read_bytes(), self.assets.read_bytes(self.asset.asset_id))
        self.assertEqual((directory / f"creation_001_{job['job_id']}.png").read_bytes(), self.assets.read_bytes(attempt.output_asset_id))
        self.assertTrue((directory / f"creation_001_{job['job_id']}_dlss.json").is_file())

    def test_progress_subscription_precedes_submission_and_does_not_change_the_result(self):
        watching = []

        @contextmanager
        def watch(execution_id, stages, publish):
            self.assertEqual(self.comfy.submissions, [])
            self.assertTrue(stages)
            watching.append(execution_id)
            yield
            self.assertEqual(self.comfy.submissions[0][0], execution_id)

        self.service.progress = Mock(watch=watch)
        result = self.complete(self.queue())
        self.assertEqual(watching, [result["execution_id"]])
        self.assertIsNone(result["progress"])
        self.assertIsNotNone(result["finished_at"])

    def test_dlss_phase_progress_is_reported_as_global_queue_progress(self):
        job = self.queue()
        job.update(status="running", execution_id="execution")
        self.jobs.save(job)
        coordinator = SimpleNamespace(report_progress=Mock())
        self.service.work_coordinator = coordinator

        self.service._record_progress(job["job_id"], "execution", {
            "stage": "interpolation",
            "label": "Fluidification 60 FPS",
            "stage_index": 1,
            "stage_count": 3,
            "percent": 10,
        })

        coordinator.report_progress.assert_called_once_with(
            f"dlss:{job['job_id']}",
            (1 + .1) / 3,
            "Fluidification 60 FPS",
        )

    def test_assisted_references_the_original_dlss_png_without_a_second_media_file(self):
        directory = self.root / "dlss-output"
        self.comfy.output_root = directory
        self.service.outputs = DlssOutputs(directory, self.assets)
        result = self.complete(self.queue())
        candidate = self.store.get(self.project.project_id).attempts[-1]
        asset = self.assets.get(candidate.output_asset_id)
        self.assertEqual(asset.storage_key, f"external/{asset.asset_id}")
        self.assertFalse((self.root / "assets" / asset.asset_id / "content.bin").exists())
        self.assertEqual(Path(result["local_output_path"]).read_bytes(), self.comfy.output)
        self.assertEqual(self.assets.read_bytes(asset.asset_id), self.comfy.output)
        self.assertEqual(len(list(directory.rglob("*.png"))), 1)
        exporter = LocalKrea2CreationExporter(self.root / "exports")
        exported = Path(exporter.export(self.store.get(self.project.project_id), candidate, self.assets))
        self.assertEqual((exported / f"creation_001_{result['job_id']}.png").read_bytes(), self.comfy.output)

    def test_lost_post_reply_then_new_lab_recovers_without_resubmission(self):
        job = self.queue()
        self.comfy.ambiguous = True
        self.service._drain()
        self.assertEqual(self.jobs.get(job["job_id"])["status"], "failed")
        self.service = self.make_service()
        self.service.retry(job["job_id"])
        self.complete(job)
        self.assertEqual(len(self.comfy.submissions), 1)

    def test_failed_download_retry_and_missing_execution_never_regenerate(self):
        job = self.queue()
        self.comfy.fail_download = True
        self.service._drain()
        self.comfy.fail_download = False
        self.service.retry(job["job_id"])
        self.complete(job)
        self.assertEqual(len(self.comfy.submissions), 1)
        other = self.queue("second")
        other.update(status="running", execution_id="missing")
        self.jobs.save(other)
        self.service._drain()
        self.assertEqual(self.jobs.get(other["job_id"])["status"], "failed")
        self.assertEqual(len(self.comfy.submissions), 1)

    def test_changing_settings_on_variant_restarts_from_original_and_keeps_output(self):
        first = self.complete(self.queue())
        variant = self.store.get(self.project.project_id).attempts[-1]
        job = self.service.queue(owner="assisted", owner_id=self.project.project_id, attempt_id=variant.attempt_id,
                                 settings=DlssSettings(intensity=0.5), request_id="variant")
        self.assertEqual(job["snapshot"]["input_asset_id"], self.asset.asset_id)
        self.complete(job)
        self.assertEqual(self.assets.read_bytes(first["output_asset_id"]), self.comfy.output)

    def test_output_dimension_mismatch_fails_without_attaching(self):
        job = self.queue()
        self.comfy.output = png((130, 192))
        self.service._drain()
        self.assertEqual(self.jobs.get(job["job_id"])["status"], "failed")
        self.assertEqual(self.store.get(self.project.project_id), self.project)

    def test_instance_control_blocked_by_queued_jobs_and_foreign_endpoint(self):
        job = self.queue()
        with self.assertRaises(ValueError):
            self.service.control("stop")
        self.runtime.control.assert_not_called()
        job["endpoint"] = "http://bucket:8188"
        self.jobs.save(job)
        self.service._drain()
        self.runtime.ensure_ready.assert_not_called()
        self.assertEqual(self.comfy.submissions, [])

    def test_http_retries_invalid_settings_and_no_runtime_on_spec(self):
        app = FastAPI()
        register_dlss_routes(app, self.service)
        with TestClient(app) as client:
            self.assertTrue(client.get("/api/dlss/spec").json()["enabled"])
            self.runtime.ensure_ready.assert_not_called()
            body = dict(owner="assisted", owner_id=self.project.project_id, attempt_id=self.project.attempts[0].attempt_id,
                        settings={"size": "2"}, request_id="http")
            first = client.post("/api/dlss/jobs", json=body)
            self.assertEqual(first.status_code, 202, first.text)
            self.assertEqual(first.json()["settings"]["size"], "2")  # explicit size is preserved
            self.assertEqual(first.json()["settings"]["skin"], -1)
            self.assertEqual(first.json()["settings"]["intensity"], 1)
            self.assertEqual(client.post("/api/dlss/jobs", json=body).json()["job_id"], first.json()["job_id"])
            body["settings"]["size"] = "source"
            self.assertEqual(client.post("/api/dlss/preview", json=body).status_code, 422)
            self.assertEqual(client.post("/api/dlss/runtime/stop").status_code, 422)

    def test_all_workflows_have_durable_output_and_smooth_saves_interpolated_video(self):
        for key, workflow in self.workflows.items():
            graph = workflow.build("test.png" if key == "image" else "test.mp4", "test", DlssSettings())
            classes = {v["class_type"] for v in graph.values()}
            self.assertNotIn("ImageCompare", classes)
            self.assertFalse(any("Sampler" in c for c in classes))
            output = graph[workflow.manifest["output_node"]]
            self.assertIn(output["class_type"], {"SaveImage", "SaveVideo"})
            if key != "image":
                upstream = graph[output["inputs"]["video"][0]]["class_type"]
                self.assertEqual(upstream, "NvidiaDLSSFrameInterpolation" if key.endswith("smooth") else "NvidiaDLSSVideoUpscale")

    def test_video_modes_import_their_own_frames_audio_and_actual_dimensions(self):
        self.comfy.output_root = self.root / "dlss-output"
        self.service.outputs = DlssOutputs(self.comfy.output_root, self.assets)
        self.service.video_exporter = DlssVideoExporter(self.root / "server" / "Upscale")
        (self.root / "server").mkdir()
        self.service.wake_exports = Mock()
        store = LocalH3RenderProjectStore(self.root)
        h3 = SimpleNamespace(projects=store, _lock=RLock())
        self.candidates.services.update(h3=h3, ref2v=h3)
        original_video = self.assets.create(b"original-video", "video/mp4")
        settings = VideoLabSettings(aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN, megapixels=0.2, duration_seconds=5, steps=25, seed=1)
        for owner, mode, smooth in (("h3", H3RenderInputMode.T2VA, False), ("ref2v", H3RenderInputMode.REF2VA, True)):
            with self.subTest(owner=owner):
                original = H3RenderAttempt(attempt_id="video-original", index=1, prompt="A moving scene.", effective_prompt="A moving scene.",
                    settings=settings, music_enabled=False, keyframe_timestamps_ms=(0, 2500, 4990),
                    status=H3RenderAttemptStatus.SUCCEEDED, execution_id="original-render", compiled_workflow_sha256="a" * 64,
                    output_asset_id=original_video.asset_id)
                project = store.create(H3RenderProject(project_id=owner, source_session_id="session", source_prompt_revision_id="revision",
                    model_id="local", input_mode=mode, current_prompt="A moving scene.", attempts=(original,),
                    reference_asset_ids=(self.asset.asset_id,) if owner == "ref2v" else (), reference_labels=("subject",) if owner == "ref2v" else ()))
                for version in (1, 2, 3):
                    self.assertIsNone(h3_load(dict(h3_dict(project), schema_version=version)).attempts[0].dlss)
                before = {"width": 64, "height": 96, "fps": 24, "duration_seconds": 5, "audio": True}
                after = dict(before, width=96, height=144, fps=60 if smooth else 24)
                self.comfy.output = b"processed-video"
                with patch.object(self.media, "probe", side_effect=lambda content: before if content == b"original-video" else after), \
                     patch.object(self.media, "frames", side_effect=lambda content, timestamps: [png((96, 144), "green") for _ in timestamps]) as frames:
                    job = self.service.queue(owner=owner, owner_id=owner, attempt_id=original.attempt_id,
                        settings=DlssSettings(size="1.5", interpolate=smooth), request_id="video")
                    result = self.complete(job)
                    candidate = store.get(owner).attempts[-1]
                    self.assertEqual(candidate.dlss.fps, 60 if smooth else 24)
                    self.assertEqual(candidate.dlss.width, 96)
                    self.assertEqual(frames.call_args.args[0], b"processed-video")
                    self.assertTrue(candidate.keyframes)
                    self.assertEqual(candidate.keyframes[-1].timestamp_ms, int((5 - 1 / after["fps"]) * 1000))
                    self.assertEqual(h3_load(h3_dict(store.get(owner))), store.get(owner))
                    self.assertEqual(store.get(owner).use_feedback(candidate.attempt_id).feedback_attempt_id, candidate.attempt_id)
                    self.assertEqual(result["output_metadata"]["audio"], True)
                    self.assertFalse((self.root / "assets" / candidate.output_asset_id / "content.bin").exists())
                    self.assertEqual(self.assets.read_bytes(candidate.output_asset_id), b"processed-video")
                    self.service._drain_exports()
                    saved = self.jobs.get(result["job_id"])
                    self.assertEqual(saved["video_export"]["status"], "succeeded")
                    self.assertEqual(Path(saved["video_export"]["path"]).read_bytes(), b"processed-video")

    def test_legacy_assisted_schemas_load_without_treatment_and_cancel_is_local(self):
        data = assisted_dict(self.project)
        for version in range(1, 9):
            old = dict(data, schema_version=version)
            self.assertIsNone(assisted_load(old).attempts[0].dlss)
        job = self.queue()
        self.service.cancel(job["job_id"])
        self.service._drain()
        self.assertEqual(self.jobs.get(job["job_id"])["status"], "cancelled")
        self.runtime.ensure_ready.assert_not_called()

    def test_cancelled_unsubmitted_job_can_be_retried_explicitly(self):
        job = self.queue()
        self.service.cancel(job["job_id"])
        self.service.retry(job["job_id"])
        self.complete(job)
        self.assertEqual(len(self.comfy.submissions), 1)

    def test_cancel_queued_never_marks_submitted_work_for_cancellation(self):
        queued = self.queue()
        cancelled = self.service.cancel_queued(queued["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["cancel_requested"])

        submitted = self.queue(request_id="submitted")
        saved = self.jobs.get(submitted["job_id"])
        saved.update(status="running", execution_id="already-submitted")
        self.jobs.save(saved)
        untouched = self.service.cancel_queued(submitted["job_id"])
        self.assertEqual(untouched["status"], "running")
        self.assertFalse(untouched.get("cancel_requested", False))

    def test_worker_lease_prevents_a_second_executor(self):
        job = self.queue()
        with self.jobs.lease("worker"):
            self.service._drain()
        self.assertEqual(self.jobs.get(job["job_id"])["status"], "queued")
        self.assertEqual(self.comfy.submissions, [])

    def test_orientation_native_rounding_limits_and_strict_options(self):
        exif = Image.Exif(); exif[274] = 6
        self.assertEqual(self.media.dimensions(png(exif=exif)), (96, 64))
        self.assertEqual(self.media.target((66, 100), DlssSettings(size="1.5"))[0], (100, 150))
        for dimensions in ((10, 64), (4000, 4000), (5000, 1000)):
            with self.assertRaises(ValueError):
                self.media.target(dimensions, DlssSettings(size="3"))
        with self.assertRaises(ValueError):
            DlssSettings(intensity=float("nan"))


class DlssEditTest(unittest.TestCase):
    def setUp(self):
        RetouchServiceTest.setUp(self)
        self.addCleanup(self.temp.cleanup)
        self.source_bytes = png((64, 96), "blue")
        source = self.assets.create(self.source_bytes, "image/png")
        generated = self.assets.create(png((64, 96), "red"), "image/png")
        self.original = replace(self.original, output_asset_id=generated.asset_id)
        self.source = self.store.save(replace(self.source, source_asset_id=source.asset_id, attempts=(self.original,)))
        self.comfy = FakeComfy()
        self.jobs = LocalDlssJobs(self.root)
        self.runtime = Mock(); self.runtime.ready.return_value = True
        self.workflow = DlssWorkflow(ROOT / "workflows/image.upscale/dlss/0.1.0")
        self.candidates = DlssCandidates(edit=self.service, assisted=None, h3=None)
        self.dlss = DlssService(jobs=self.jobs, runtime=self.runtime, comfy=self.comfy, assets=self.assets,
            media=DlssMedia(ffmpeg="never-run", ffprobe="never-run"), candidates=self.candidates, workflows={"image": self.workflow}, poll_interval=0)
        self.dlss.wake = Mock()

    def finish(self, parent, *, size="source", request_id="one"):
        job = self.dlss.queue(owner="edit", owner_id=self.source.source_id, attempt_id=parent, settings=DlssSettings(size=size), request_id=request_id)
        self.dlss._drain()
        result = self.jobs.get(job["job_id"])
        self.assertEqual(result["status"], "succeeded", result.get("error"))
        return self.store.get(self.source.source_id).attempts[-1]

    def test_source_size_mask_pixels_reopen_and_final_size(self):
        directory = self.root / "dlss-output"
        self.assets = LocalAssetStore(self.root, external_roots=(directory,))
        self.service.assets = self.dlss.assets = self.assets
        self.comfy.output_root = directory
        self.dlss.outputs = DlssOutputs(directory, self.assets)
        mask = Image.new("L", (64, 96), 0)
        mask.paste(128, (20, 20, 40, 40)); stream = BytesIO(); mask.save(stream, format="PNG")
        _, retouch = self.service.save_retouch(self.source.source_id, "original", stream.getvalue(), request_id="mask")
        enhanced = self.finish(retouch.attempt_id)
        image = Image.open(BytesIO(self.assets.read_bytes(enhanced.output_asset_id)))
        self.assertEqual(image.size, (64, 96))
        self.assertEqual(image.convert("RGB").getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(image.convert("RGB").getpixel((25, 25)), (128, 0, 127))
        self.assertFalse((self.root / "assets" / enhanced.output_asset_id / "content.bin").exists())
        self.assertTrue(any(directory.rglob("*_result.png")))
        reopened = self.service.prepare_retouch(self.source.source_id, enhanced.attempt_id)
        self.assertEqual(reopened["mask_png"], self.assets.read_bytes(retouch.retouch.mask_asset_id))
        final = self.finish(retouch.attempt_id, size="2", request_id="finish")
        self.assertEqual(final.output_dimensions, (128, 192))
        self.assertIsNone(final.upscale.mask_asset_id)
        self.assertFalse(final.upscale.preserve_source_size)
        project = self.store.get(self.source.source_id)
        self.assertEqual(edit_load(edit_dict(project)), project)
        self.assertEqual(project.generated_prompt, "CURRENT EDITOR PROMPT")
        child = self.service.promote_attempt(self.source.source_id, final.attempt_id, project_name="DLSS wall", step_name="Finished")
        self.assertEqual(child.source_asset_id, final.output_asset_id)
        accepted = self.store.get(self.source.source_id)
        self.assertEqual(accepted.accepted_attempt_id, final.attempt_id)
        self.assertIsNone(accepted.export_error)
        exported = list((self.root / "exports").rglob("dlss-report.json"))
        self.assertTrue(exported)
        self.assertEqual(exported[0].read_bytes(), self.assets.read_bytes(final.dlss.report_asset_id))

    def test_old_edit_projects_remain_readable(self):
        data = edit_dict(self.source)
        for version in range(1, 11):
            self.assertIsNone(edit_load(dict(data, schema_version=version)).attempts[0].dlss)

    def test_restarted_stage_keeps_result_downloadable_without_mutating_new_stage(self):
        job = self.dlss.queue(owner="edit", owner_id=self.source.source_id, attempt_id="original", settings=DlssSettings(size="source"), request_id="restart")
        original_attach = self.candidates.attach
        def restart_then_attach(*args):
            current = self.store.get(self.source.source_id)
            self.store.save(current.restart())
            return original_attach(*args)
        self.candidates.attach = restart_then_attach
        self.dlss._drain()
        result = self.jobs.get(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIsNotNone(result["output_asset_id"])
        self.assertEqual(self.store.get(self.source.source_id).attempts, ())


class DlssRuntimeTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows lifecycle adapter")
    def test_start_is_hidden_uses_portable_environment_and_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("python_embeded/python.exe", "ComfyUI/main.py", "tools/ffmpeg.exe", "tools/ffprobe.exe"):
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.touch()
            runtime = LocalDlssRuntime(root=root, base_url="http://127.0.0.1:18188", journal=LocalDlssJobs(root / "journal"), comfy=Mock(), output_root=root / "LocalOutput")
            process = Mock(pid=3456); process.poll.return_value = None
            identity = {"pid": 3456, "created": 1234, "executable": str((root / "python_embeded/python.exe").resolve()).casefold()}
            with patch.object(runtime, "ready", side_effect=[False, True, True]), patch.object(runtime, "_json", return_value={"SaveImage": {}}), \
                 patch("panelforge.infrastructure.dlss_runtime.windows_process_identity", return_value=identity), \
                 patch("panelforge.infrastructure.dlss_runtime.subprocess.Popen", return_value=process) as launch:
                runtime.ensure_ready(["SaveImage"])
                runtime.ensure_ready(["SaveImage"])
                launch.assert_called_once()
                command = launch.call_args.args[0]
                self.assertIn("18188", command)
                self.assertEqual(command[command.index("--output-directory") + 1], str(root / "LocalOutput"))
                self.assertEqual(launch.call_args.kwargs["env"]["DLSS_FFMPEG_PATH"], str(root / "tools/ffmpeg.exe"))
                self.assertTrue(launch.call_args.kwargs["creationflags"])
                self.assertNotIn("shell", launch.call_args.kwargs)

    def test_external_instance_reused_and_never_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            comfy = Mock(); comfy.get_queue.return_value = SimpleNamespace(running=(), pending=())
            runtime = LocalDlssRuntime(root=directory, base_url="http://127.0.0.1:8188", journal=LocalDlssJobs(directory), comfy=comfy)
            with patch.object(runtime, "ready", return_value=True), patch.object(runtime, "_json", return_value={"SaveImage": {}}), patch("subprocess.Popen") as launch:
                runtime.ensure_ready(["SaveImage"])
                launch.assert_not_called()
                with self.assertRaises(ValueError):
                    runtime.control("stop")
                runtime.control("free")
                comfy.free_vram.assert_called_once()

    def test_nonlocal_url_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                LocalDlssRuntime(root=directory, base_url="http://bucket:8188", journal=LocalDlssJobs(directory), comfy=Mock())

    def test_queue_guard_and_exact_owned_process_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            comfy = Mock(); comfy.get_queue.return_value = SimpleNamespace(running=("job",), pending=())
            runtime = LocalDlssRuntime(root=directory, base_url="http://127.0.0.1:8188", journal=LocalDlssJobs(directory), comfy=comfy)
            with patch.object(runtime, "ready", return_value=True), patch.object(runtime, "ownership", return_value={"pid": 3456}), patch("subprocess.run") as stop:
                with self.assertRaises(ValueError):
                    runtime.control("stop")
                stop.assert_not_called()
                comfy.get_queue.return_value = SimpleNamespace(running=(), pending=())
                with patch("panelforge.infrastructure.dlss_runtime.subprocess.CREATE_NO_WINDOW", 0, create=True):
                    runtime.control("stop")
                self.assertEqual(stop.call_args.args[0], ["taskkill.exe", "/PID", "3456", "/T", "/F"])


if __name__ == "__main__":
    unittest.main()
