"""User-run isolated cover API checks, no image or LLM generation."""
from types import SimpleNamespace as NS
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.domain.episode_thumbnails import ThumbnailConflict
from panelforge.features.lab.episode_thumbnails_web import episode_thumbnails_router


class ThumbnailWebTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def prepare(identity, **values):
            if values["expected_revision"] == 99:
                raise ThumbnailConflict("Miniature modifiée")
            self.calls.append((identity, values))
            return {"status": "queued"}
        self.service = NS(prepare=prepare, get=lambda identity: {"asset_id": "cover-image", "number": 2},
                          assets=NS(read_bytes=lambda identity: b"png-file"), images=NS(font_bytes=lambda style: b"ttf-font"))
        app = FastAPI()
        app.include_router(episode_thumbnails_router(NS(thumbnails=self.service)))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.url = "/api/episodes/episode-test/thumbnail"
        self.body = {"request_id": "request-thumbnail", "expected_revision": 0}

    def test_manual_prepare_passes_only_explicit_thumbnail_options(self):
        response = self.client.post(self.url, json=self.body | {"number": 3})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1][1]["number"], 3)
        self.assertFalse(self.calls[-1][1]["replace"])

    def test_stale_edit_and_invalid_number_do_not_start_jobs(self):
        self.assertEqual(self.client.post(self.url, json=self.body | {"expected_revision": 99}).status_code, 409)
        for number in (0, 10000, True, 1.2):
            self.assertEqual(self.client.post(self.url, json=self.body | {"number": number}).status_code, 422)
        self.assertFalse(self.calls)

    def test_import_requires_upload_mode_and_limits_file_size(self):
        import json
        response = self.client.post(self.url + "/import", data={"options": json.dumps(self.body)},
                                    files={"image": ("model.png", b"png", "image/png")})
        self.assertEqual(response.status_code, 422)
        response = self.client.post(self.url + "/import", data={"options": json.dumps(self.body | {"source": "upload"})},
                                    files={"image": ("model.png", b"png", "image/png")})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1][1]["content"], b"png")

    def test_download_is_a_separate_png_attachment(self):
        response = self.client.get(self.url + "/download")
        self.assertEqual(response.content, b"png-file")
        self.assertIn("image/png", response.headers["content-type"])
        self.assertIn("episode-02-miniature.png", response.headers["content-disposition"])
        self.assertFalse(self.calls)


    def test_reference_roles_and_title_style_are_passed_through(self):
        references = [f"ref-{i}" for i in range(16)]
        body = self.body | {"reference_ids": references, "reference_roles": {references[0]: "foreground", references[1]: "background"}, "title_style": "cinema"}
        response = self.client.post(self.url, json=body)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.calls[-1][1]["reference_roles"], body["reference_roles"])
        self.assertEqual(self.calls[-1][1]["title_style"], "cinema")
        self.assertEqual(self.client.post(self.url, json=body | {"reference_ids": references + ["too-many"]}).status_code, 422)
        self.assertEqual(self.client.post(self.url, json=body | {"title_style": "unknown"}).status_code, 422)

    def test_font_preview_route_uses_only_whitelisted_styles(self):
        response = self.client.get("/api/episodes/thumbnail-fonts/cinema")
        self.assertEqual(response.content, b"ttf-font")
        self.assertEqual(response.headers["content-type"], "font/ttf")
        self.assertEqual(self.client.get("/api/episodes/thumbnail-fonts/unknown").status_code, 422)

    def test_badge_routes_validate_and_only_call_local_composition(self):
        self.service.reposition_badge = lambda identity, **values: self.calls.append((identity, values)) or {"status": "ready"}
        self.service.badge_preview = lambda identity, **values: b"preview-png"
        response = self.client.get(self.url + "/badge-preview/background?expected_revision=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = dict(self.body, position={"x": 50, "y": 8}, remember_series=True)
        self.assertEqual(self.client.post(self.url + "/badge", json=body).status_code, 200)
        self.assertEqual(self.calls[-1][1]["position"], {"x": 50, "y": 8})
        for invalid in ({"x": True, "y": 8}, {"x": 1, "y": 101}, {"x": 50}, {"x": "50", "y": 8}):
            self.assertEqual(self.client.post(self.url + "/badge", json=body | {"position": invalid}).status_code, 422)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.client.get(self.url + "/badge-preview/unknown?expected_revision=1").status_code, 422)

    def test_archive_route_validates_revision_and_surfaces_used_template_conflict(self):
        def archive(identity, template_id, **values):
            if template_id == "used":
                raise ThumbnailConflict("Modèle utilisé")
            self.calls.append((template_id, values))
            return {"templates": []}
        self.service.archive_template = archive
        body = {"expected_revision": 0, "archived": True}
        self.assertEqual(self.client.post(self.url + "/templates/unused/archive", json=body).status_code, 200)
        self.assertEqual(self.client.post(self.url + "/templates/used/archive", json=body).status_code, 409)
        self.assertEqual(self.client.post(self.url + "/templates/unused/archive", json=body | {"archived": "true"}).status_code, 422)
        self.assertEqual(self.calls, [("unused", body)])
