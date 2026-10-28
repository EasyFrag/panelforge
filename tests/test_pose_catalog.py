"""User-run catalogue adapter tests; no requests reach the public site."""
from io import BytesIO
import json
import tempfile
import unittest

from PIL import Image

from panelforge.infrastructure.pose_catalog import LocalPoseCatalog, SOURCE_URL, parse_catalog


def entry(identity="standard_P001_front"):
    return {"id": identity, "系統":"全身1人・標準系", "ポーズ番号":"P001", "分類":"立ち",
            "ポーズ名":"Catalogue fixture", "アングル":"正面", "サムネ":f"thumbs/{identity}.jpg", "原寸":f"img/{identity}.png"}


def html(values):
    return ("<script>const D=" + json.dumps(values, ensure_ascii=False) + ";</script>").encode()


def image_bytes(format):
    target = BytesIO()
    Image.new("RGB", (4, 4), "grey").save(target, format)
    return target.getvalue()


class PoseCatalogTests(unittest.TestCase):
    def test_explicit_catalogue_ids_angles_and_paths_are_parsed_without_running_javascript(self):
        first = entry(); second = entry("standard_P001_side"); second["アングル"] = "横"
        parsed = parse_catalog(html([first, second]) + b"<script>throw new Error('never executed')</script>")
        self.assertEqual({p["pose_id"] for p in parsed["entries"]}, {"standard_P001"})
        self.assertEqual([p["angle"] for p in parsed["entries"]], ["Face", "Profil"])
        self.assertEqual(parsed["entries"][0]["category"], "Debout")
        self.assertEqual(parsed["revision"], parse_catalog(html([first, second]))["revision"])

    def test_duplicate_ids_arbitrary_paths_or_scripts_instead_of_json_are_rejected(self):
        for field, value in (("原寸","https://example.test/private.png"), ("サムネ","../secret.jpg"), ("id","../private")):
            item = entry(); item[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_catalog(html([item]))
        with self.assertRaises(ValueError): parse_catalog(html([entry(), entry()]))
        with self.assertRaises(ValueError): parse_catalog(b"const D = fetch('private');")
        with self.assertRaises(ValueError): parse_catalog(b"const D = [];")

    def test_install_is_local_atomic_and_images_are_cached_only_when_used(self):
        calls = []
        def download(url, limit):
            calls.append(url)
            if url == SOURCE_URL: return html([entry()])
            return image_bytes("JPEG" if "/thumbs/" in url else "PNG")
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=download)
            self.assertEqual(catalog.status()["state"], "unavailable")
            self.assertEqual(calls, [])
            catalog.install(); catalog.install()
            self.assertEqual(calls, [SOURCE_URL])
            self.assertEqual(catalog.status()["pose_count"], 1)
            thumb = catalog.image_path(entry()["id"], thumbnail=True)
            self.assertTrue(thumb.is_file())
            self.assertEqual(catalog.image_path(entry()["id"], thumbnail=True), thumb)
            metadata, data = catalog.reference(entry()["id"])
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(metadata["sha256"]), 64)
            self.assertTrue(data.startswith(b"\x89PNG"))
            before = (catalog.root / "catalog.json").read_bytes()
            catalog.downloader = lambda url, limit: b"invalid"
            with self.assertRaises(ValueError): catalog.install(force=True)
            self.assertEqual((catalog.root / "catalog.json").read_bytes(), before)
            self.assertEqual(catalog.status()["state"], "ready")

    def test_cache_does_not_persist_html_instead_of_an_image(self):
        def download(url, limit): return html([entry()]) if url == SOURCE_URL else b"<html>Error</html>"
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=download); catalog.install()
            with self.assertRaises(ValueError): catalog.image_path(entry()["id"])
            self.assertEqual(list(catalog.root.rglob("*.png")), [])
