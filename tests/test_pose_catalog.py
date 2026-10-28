"""User-run catalogue adapter tests; no requests reach the public site."""
from io import BytesIO
import hashlib
import json
import tempfile
import unittest

from PIL import Image

from panelforge.infrastructure.pose_catalog import LocalPoseCatalog, SOURCE_URL, parse_catalog
from panelforge.infrastructure.pose_catalog_fr import display_entry
from panelforge.infrastructure.storage.local import _json_bytes


def entry(identity="standard_P001_front"):
    return {"id": identity, "系統":"全身1人・標準系", "ポーズ番号":"P001", "分類":"立ち",
            "ポーズ名":"Catalogue fixture", "アングル":"正面", "サムネ":f"thumbs/{identity}.jpg", "原寸":f"img/{identity}.png"}


def html(values):
    return ("<script>const D=" + json.dumps(values, ensure_ascii=False) + ";</script>").encode()


def image_bytes(format):
    target = BytesIO()
    Image.new("RGB", (4, 4), "grey").save(target, format)
    return target.getvalue()


def install_personal_fixture(catalog, **overrides):
    data = image_bytes("PNG")
    item = dict(id="personal_fixture_front", pose_id="personal_fixture", number="PF001",
                name="Genoux repliés", family="Mes poses", category="Allongé", angle="Face",
                original="img/personal_fixture_front.png", thumbnail="img/personal_fixture_front.png",
                sha256=hashlib.sha256(data).hexdigest())
    item.update(overrides)
    root = catalog.root / "personal"
    (root / "img").mkdir(parents=True, exist_ok=True)
    (root / "img/personal_fixture_front.png").write_bytes(data)
    index = dict(schema_version=1, source="personal", entries=[item],
                 revision=hashlib.sha256(_json_bytes([item])).hexdigest())
    (root / "catalog.json").write_bytes(_json_bytes(index))
    return item, data


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

    def test_installed_japanese_index_is_localized_without_reinstall_or_revision_changes(self):
        item = entry("full_sexy_P062_front")
        item.update({"系統": "全身1人・セクシー系", "分類": "膝立ち・四つん這い", "ポーズ名": "仰向けで両膝を胸に引き寄せる"})
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=lambda *args: self.fail("No network needed to translate an installed index"))
            catalog.root.mkdir(parents=True)
            index = parse_catalog(html([item]))
            path = catalog.root / "catalog.json"
            path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            original = path.read_bytes()
            public = catalog.entries()[0]
            self.assertEqual(public["name"], "Sur le dos, genoux ramenés à la poitrine")
            self.assertEqual(public["source_name"], item["ポーズ名"])
            self.assertEqual(public["family"], "Corps entier · NSFW")
            self.assertEqual(public["category"], "À genoux ou à quatre pattes")
            self.assertEqual(public["catalog_revision"], index["revision"])
            self.assertEqual(catalog.get(item["id"]), public)
            self.assertEqual(catalog.status()["categories"], [public["category"]])
            self.assertEqual(path.read_bytes(), original)

    def test_unknown_future_pose_keeps_source_metadata_but_no_japanese_display_labels(self):
        raw = dict(id="new_P999_front", pose_id="new_P999", number="P999", name="未知の名前",
                   family="新しい系統", category="新しい分類", angle="Face")
        public = display_entry(raw)
        self.assertEqual((public["name"], public["family"], public["category"]), ("Pose P999", "Autres", "Autres"))
        self.assertEqual(raw["name"], public["source_name"])

    def test_personal_reference_keeps_supplied_bytes_and_survives_gallery_refresh(self):
        calls = []
        def download(url, limit):
            calls.append(url)
            return html([entry()])
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=download)
            catalog.install()
            gallery_before = (catalog.root / "catalog.json").read_bytes()
            item, data = install_personal_fixture(catalog)
            personal_before = (catalog.root / "personal/catalog.json").read_bytes()
            self.assertEqual(catalog.status()["pose_count"], 2)
            self.assertEqual(catalog.status()["personal_pose_count"], 1)
            self.assertEqual(len(catalog.entries()), 2)
            preview = catalog.image_path(item["id"], thumbnail=True)
            self.assertEqual(preview.read_bytes(), data)
            metadata, reference = catalog.reference(item["id"])
            self.assertEqual(reference, data)
            self.assertEqual(metadata["source_kind"], "personal")
            self.assertIsNone(metadata["source_url"])
            self.assertEqual(calls, [SOURCE_URL])
            self.assertEqual((catalog.root / "catalog.json").read_bytes(), gallery_before)
            catalog.downloader = lambda *args: html([entry("standard_P002_front")])
            catalog.install(force=True)
            self.assertEqual(catalog.reference(item["id"]), (metadata, data))
            self.assertEqual((catalog.root / "personal/catalog.json").read_bytes(), personal_before)

    def test_personal_poses_work_before_installing_the_remote_gallery(self):
        calls = []
        def download(url, limit):
            calls.append(url)
            return html([entry()])
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=download)
            item, data = install_personal_fixture(catalog)
            self.assertEqual(catalog.status()["state"], "ready")
            self.assertEqual(catalog.status()["pose_count"], 1)
            self.assertEqual(catalog.reference(item["id"])[1], data)
            self.assertEqual(calls, [])
            catalog.install()
            self.assertEqual(calls, [SOURCE_URL])
            self.assertEqual(catalog.status()["pose_count"], 2)

    def test_personal_paths_and_modified_image_bytes_are_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = LocalPoseCatalog(directory, downloader=lambda *args: self.fail("Personal images are local"))
            item, _ = install_personal_fixture(catalog, original="../outside.png")
            with self.assertRaises(ValueError): catalog.get(item["id"])
            item, _ = install_personal_fixture(catalog)
            (catalog.root / "personal" / item["original"]).write_bytes(b"modified")
            with self.assertRaises(ValueError): catalog.image_path(item["id"])
