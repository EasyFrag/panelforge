"""Image comparisons with fake workers only. Prepared for user-run verification."""

from dataclasses import asdict
from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from panelforge.application.dlss_image_comparison import queue_image_comparison
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.dlss_image_presets import image_presets, selected_image_presets
from panelforge.features.lab.dlss_web import register_dlss_routes
from panelforge.infrastructure.storage.dlss_jobs import LocalDlssJobs
from tests import test_dlss as support


class DlssImageComparisonTest(unittest.TestCase):
    setUp = support.DlssTest.setUp
    make_service = support.DlssTest.make_service

    def compare(self, **overrides):
        arguments = dict(owner="assisted", owner_id=self.project.project_id,
                         attempt_id=self.project.attempts[0].attempt_id,
                         settings=DlssSettings(size="2", skin=-1), request_id="comparison",
                         preset_ids=[p["preset_id"] for p in image_presets(DlssSettings())])
        return queue_image_comparison(self.service, **{**arguments, **overrides})

    def test_shared_source_dimensions_and_five_persisted_results_without_generation_changes(self):
        with patch.object(self.service, "preview", wraps=self.service.preview) as preview:
            jobs = self.compare()
            preview.assert_called_once()
        self.assertEqual(len(jobs), 5)
        self.assertEqual(len({j["snapshot"]["input_asset_id"] for j in jobs}), 1)
        self.assertEqual({tuple(j["output_dimensions"]) for j in jobs}, {(128, 192)})
        base = jobs[0]["settings"]
        for job in jobs[1:]:
            self.assertEqual(sum(job["settings"][k] != v for k, v in base.items()), 1)
            self.assertEqual(job["settings"]["skin"], -1)
        self.runtime.ensure_ready.assert_not_called()
        self.assertEqual(self.comfy.submissions, [])
        self.service._drain()  # All runtime/process/media gateways are the existing fakes.
        stored = LocalDlssJobs(self.root).list()
        self.assertEqual({j["status"] for j in stored}, {"succeeded"})
        self.assertEqual({j["comparison"]["total"] for j in stored}, {5})
        project = self.store.get(self.project.project_id)
        self.assertEqual(project.attempts[0], self.project.attempts[0])
        self.assertEqual(project.turns, self.project.turns)
        self.assertEqual(len(project.attempts), 6)
        self.assertEqual({a.dlss.root_attempt_id for a in project.attempts[1:]}, {project.attempts[0].attempt_id})
        with patch.object(self.service, "preview", side_effect=AssertionError("retry must not re-probe")):
            retried = self.compare()
        self.assertEqual([j["job_id"] for j in retried], [j["job_id"] for j in jobs])
        self.assertEqual(len(self.comfy.submissions), 5)
        # A new comparison from a DLSS variant still uses the original pixels.
        new = self.compare(attempt_id=project.attempts[-1].attempt_id, request_id="second")
        self.assertEqual({j["snapshot"]["input_asset_id"] for j in new}, {self.asset.asset_id})

    def test_interrupted_admission_resumes_only_missing_jobs(self):
        save = self.jobs.save
        count = 0
        def interrupted(job):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("disk temporarily unavailable")
            return save(job)
        with patch.object(self.jobs, "save", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.compare()
        existing = self.jobs.list()
        self.assertEqual(len(existing), 2)
        jobs = self.compare()
        self.assertEqual(len(jobs), 5)
        for job in existing:
            self.assertEqual(self.jobs.get(job["job_id"]), job)
        with self.assertRaises(ValueError):
            self.compare(preset_ids=["current"])
        with self.assertRaises(ValueError):
            self.compare(settings=DlssSettings(size="1.5", skin=-1))
        self.assertEqual(len(self.jobs.list()), 5)

    def test_invalid_profiles_and_video_are_rejected_before_work(self):
        for overrides in ({"owner": "h3"}, {"owner": "ref2v"}, {"preset_ids": []},
                          {"preset_ids": ["current", "current"]}, {"preset_ids": ["unknown"]},
                          {"settings": DlssSettings(interpolate=True)}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.compare(**overrides)
        self.assertEqual(self.jobs.list(), [])
        at_limit = DlssSettings(intensity=0, tone=0, detail=2, structure=2)
        self.assertEqual([p["preset_id"] for p in image_presets(at_limit) if p["available"]], ["current"])
        with self.assertRaises(ValueError):
            selected_image_presets(at_limit, ["soft"])
        custom = DlssSettings(size="source", style="Natural", skin=0.4, strict_neural=True)
        for preset in image_presets(custom):
            self.assertEqual(preset["settings"]["size"], "source")
            self.assertEqual(preset["settings"]["skin"], 0.4)
            self.assertEqual(preset["settings"]["style"], "Natural")
            self.assertTrue(preset["settings"]["strict_neural"])

    def test_cancelling_one_variant_does_not_block_the_other_results(self):
        jobs = self.compare(preset_ids=["current", "detail", "soft"])
        self.service.cancel(jobs[1]["job_id"])
        self.service._drain()
        self.assertEqual([self.jobs.get(j["job_id"])["status"] for j in jobs], ["succeeded", "cancelled", "succeeded"])
        self.assertEqual(len(self.comfy.submissions), 2)

    def test_image_http_contract_and_existing_single_video_admission(self):
        app = FastAPI(); register_dlss_routes(app, self.service)
        body = dict(owner="assisted", owner_id=self.project.project_id,
                    attempt_id=self.project.attempts[0].attempt_id, settings={}, request_id="http-comparison")
        with TestClient(app) as client:
            preview = client.post("/api/dlss/preview", json=body)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(len(preview.json()["image_presets"]), 5)
            response = client.post("/api/dlss/image-comparisons", json={**body, "preset_ids": ["current", "detail"]})
            self.assertEqual(response.status_code, 202, response.text)
            jobs = response.json()["jobs"]
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0]["settings"]["size"], "1.5")
            self.assertEqual(jobs[0]["settings"]["skin"], -1)
            self.assertEqual(jobs[0]["comparison"]["label"], "Réglages actuels")
            for owner in ("h3", "ref2v"):
                self.assertEqual(client.post("/api/dlss/image-comparisons", json={**body, "owner": owner, "preset_ids": ["current"]}).status_code, 422)
            # The original video route still forwards exactly the provided settings.
            video_settings = DlssSettings(size="1.724", interpolate=True, skin=-1)
            with patch.object(self.service, "queue", return_value={"job_id": "fake-video"}) as queue:
                response = client.post("/api/dlss/jobs", json={**body, "owner": "h3", "settings": asdict(video_settings)})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(queue.call_args.kwargs["settings"], video_settings)
            self.assertNotIn("comparison", response.json())


class DlssEditComparisonTest(unittest.TestCase):
    setUp = support.DlssEditTest.setUp

    def test_all_source_size_variants_keep_the_mask_and_source_pixels(self):
        mask = Image.new("L", (64, 96), 0)
        mask.paste(255, (20, 20, 40, 40))
        stream = BytesIO(); mask.save(stream, format="PNG")
        _, retouch = self.service.save_retouch(self.source.source_id, "original", stream.getvalue(), request_id="comparison-mask")
        jobs = queue_image_comparison(self.dlss, owner="edit", owner_id=self.source.source_id,
            attempt_id=retouch.attempt_id, settings=DlssSettings(size="source", skin=-1),
            preset_ids=["current", "detail"], request_id="masked-comparison")
        self.assertEqual({j["snapshot"]["mask_asset_id"] for j in jobs}, {retouch.retouch.mask_asset_id})
        self.assertEqual({tuple(j["output_dimensions"]) for j in jobs}, {(64, 96)})
        self.dlss._drain()
        for job in jobs:
            result = self.jobs.get(job["job_id"])
            self.assertEqual(result["status"], "succeeded", result.get("error"))
            image = Image.open(BytesIO(self.assets.read_bytes(result["output_asset_id"]))).convert("RGB")
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
            self.assertEqual(image.getpixel((25, 25)), (255, 0, 0))
