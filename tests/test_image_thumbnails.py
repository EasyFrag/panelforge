"""User-run thumbnail/cache checks using synthetic local assets only."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from panelforge.features.lab.media_http import media_router
from panelforge.infrastructure.image_thumbnails import CachedImageThumbnails
from panelforge.infrastructure.storage import LocalAssetStore


def png(color="blue"):
    output = BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", "Private source prompt")
    Image.new("RGBA", (640, 320), color).save(output, format="PNG", pnginfo=info)
    return output.getvalue()


class ImageThumbnailsTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.assets = LocalAssetStore(Path(directory.name))
        self.original = png()
        self.asset = self.assets.create(self.original, "image/png")

    def test_verified_once_small_preview_has_no_source_metadata_and_original_is_unchanged(self):
        read = Mock(wraps=self.assets.read_verified)
        cache = CachedImageThumbnails(read)
        first = cache.get(self.asset.asset_id)
        with Image.open(BytesIO(first.content)) as image:
            self.assertEqual(image.size, (320, 160))
            self.assertNotIn("prompt", image.info)
        self.assertIs(cache.get(self.asset.asset_id), first)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(self.assets.read_bytes(self.asset.asset_id), self.original)

    def test_new_asset_and_conversion_version_use_distinct_cache_entries(self):
        read = Mock(wraps=self.assets.read_verified)
        cache = CachedImageThumbnails(read)
        first = cache.get(self.asset.asset_id)
        changed = self.assets.create(png("red"), "image/png")
        self.assertNotEqual(cache.get(changed.asset_id).etag, first.etag)
        cache.VERSION += 1
        cache.get(self.asset.asset_id)
        self.assertEqual(read.call_count, 3)

    def test_cache_is_bounded_by_bytes_and_entry_count(self):
        read = Mock(wraps=self.assets.read_verified)
        cache = CachedImageThumbnails(read, max_entries=1)
        cache.get(self.asset.asset_id)
        other = self.assets.create(png("red"), "image/png")
        cache.get(other.asset_id)
        cache.get(self.asset.asset_id)
        self.assertEqual(read.call_count, 3)
        read.reset_mock()
        tiny_cache = CachedImageThumbnails(read, max_bytes=1)
        tiny_cache.get(self.asset.asset_id)
        tiny_cache.get(self.asset.asset_id)
        self.assertEqual(read.call_count, 2)

    def test_concurrent_requests_for_one_asset_share_verification_and_conversion(self):
        entered, release = Event(), Event()
        read = Mock(wraps=self.assets.read_verified)

        def slow(identity):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("read not released")
            return read(identity)

        cache = CachedImageThumbnails(slow)
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(cache.get, self.asset.asset_id) for _ in range(5)]
            try:
                self.assertTrue(entered.wait(2))
            finally:
                release.set()
            rows = [f.result(3) for f in futures]
        self.assertEqual(read.call_count, 1)
        self.assertTrue(all(row is rows[0] for row in rows))

    def test_failed_read_is_not_cached_and_can_be_retried(self):
        read = Mock(side_effect=[ValueError("integrity"), self.assets.read_verified(self.asset.asset_id)])
        cache = CachedImageThumbnails(read)
        with self.assertRaisesRegex(ValueError, "integrity"):
            cache.get(self.asset.asset_id)
        self.assertTrue(cache.get(self.asset.asset_id).content)
        self.assertEqual(read.call_count, 2)

    def test_http_cache_validation_missing_image_and_original_download(self):
        app = FastAPI()
        read = Mock(wraps=self.assets.read_verified)
        app.include_router(media_router(runner=SimpleNamespace(assets=SimpleNamespace(read_verified=read))))
        with TestClient(app) as client:
            url = f"/api/assets/{self.asset.asset_id}/thumbnail?v=1"
            first = client.get(url)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.headers["content-type"], "image/png")
            self.assertIn("immutable", first.headers["cache-control"])
            second = client.get(url, headers={"If-None-Match": first.headers["etag"]})
            self.assertEqual(second.status_code, 304)
            self.assertFalse(second.content)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(client.get(url.replace("v=1", "v=2")).status_code, 422)
            self.assertEqual(client.get("/api/assets/missing/thumbnail?v=1").status_code, 404)
            broken = self.assets.create(b"not an image", "image/png")
            self.assertEqual(client.get(f"/api/assets/{broken.asset_id}/thumbnail").status_code, 422)
            self.assertEqual(client.get(f"/api/assets/{self.asset.asset_id}/content").content, self.original)

    def test_conversion_queue_does_not_block_other_http_requests(self):
        entered, release = Event(), Event()
        lock = Lock()
        active = 0
        maximum = 0

        def slow_read(identity):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                if active == 2:
                    entered.set()
            try:
                if not release.wait(4):
                    raise TimeoutError("fixture not released")
                return self.assets.read_verified(identity)
            finally:
                with lock:
                    active -= 1

        app = FastAPI()
        app.include_router(media_router(runner=SimpleNamespace(assets=SimpleNamespace(read_verified=slow_read))))

        @app.get("/command-ready")
        async def ready():
            return {"ready": True}

        assets = [self.assets.create(self.original, "image/png") for _ in range(6)]
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=6) as pool:
            pending = [pool.submit(client.get, f"/api/assets/{asset.asset_id}/thumbnail") for asset in assets]
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(client.get("/command-ready").json(), {"ready": True})
            finally:
                release.set()
            self.assertTrue(all(future.result(4).status_code == 200 for future in pending))
        self.assertEqual(maximum, 2)
