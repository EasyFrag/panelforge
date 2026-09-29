from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from zipfile import ZipFile

from panelforge.infrastructure.krea2_style_catalog import LocalKrea2StyleCatalog


class LocalKrea2StyleCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.archive = self.root / "fixture.zip"
        styles = [
            {"name": "Cinematic Photography", "prompt": "Filmic light and deliberate framing", "section": "Photography"},
            {"name": "Soft Watercolor", "prompt": "Transparent pigment and soft paper texture", "section": "Painting"},
        ]
        manifest = {
            "sections": {
                "krea2": {
                    "images": [
                        {"style": "Cinematic Photography", "thumb": "krea2/thumbs/Cinematic Photography.jpg"},
                        {"style": "Soft Watercolor", "file": "krea2/thumbs/Soft Watercolor.jpg"},
                    ],
                },
            },
        }
        with ZipFile(self.archive, "w") as bundle:
            prefix = "clio-style-preview-fixture"
            bundle.writestr(f"{prefix}/styles.json", json.dumps(styles))
            bundle.writestr(f"{prefix}/gallery/manifest.json", json.dumps(manifest))
            bundle.writestr(f"{prefix}/gallery/krea2/thumbs/Cinematic Photography.jpg", b"cinematic")
            bundle.writestr(f"{prefix}/gallery/krea2/thumbs/Soft Watercolor.jpg", b"watercolor")
            bundle.writestr(f"{prefix}/LICENSE", "MIT fixture")
            bundle.writestr(f"{prefix}/__init__.py", "raise RuntimeError('must not be extracted')")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def catalog(self) -> LocalKrea2StyleCatalog:
        def downloader(_url: str, destination: Path) -> None:
            shutil.copyfile(self.archive, destination)

        return LocalKrea2StyleCatalog(
            self.root / "workspace",
            downloader=downloader,
            revision="fixture-revision",
            archive_url="https://example.invalid/fixture.zip",
        )

    def test_install_extracts_only_normalized_catalog_assets(self) -> None:
        catalog = self.catalog()
        self.assertEqual(catalog.status()["state"], "unavailable")
        status = catalog.install()
        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["style_count"], 2)
        self.assertEqual(status["revision"], "fixture-revision")
        installed = self.root / "workspace" / "catalogs" / "clio"
        self.assertTrue((installed / "LICENSE").is_file())
        self.assertFalse((installed / "__init__.py").exists())
        self.assertFalse((installed / "scripts").exists())

    def test_search_lookup_and_thumbnail_are_local(self) -> None:
        catalog = self.catalog()
        catalog.install()
        values = catalog.list_styles(query="watercolor", category="Painting")
        self.assertEqual([value.style_id for value in values], ["Soft Watercolor"])
        selected = catalog.get("Soft Watercolor")
        self.assertEqual(selected.catalog_revision, "fixture-revision")
        self.assertEqual(catalog.thumbnail_path(selected.style_id).read_bytes(), b"watercolor")

    def test_local_overlay_is_merged_and_survives_clio_reinstall(self) -> None:
        catalog = self.catalog()
        catalog.install()
        local = self.root / "workspace" / "catalogs" / "panelforge-local"
        (local / "thumbs").mkdir(parents=True)
        (local / "thumbs" / "wool.png").write_bytes(b"wool")
        (local / "catalog.json").write_text(json.dumps({
            "schema_version": 1,
            "provider_id": "panelforge-local",
            "revision": "2026-09-26.1",
            "styles": [{
                "style_id": "woolcraft-dreamscape",
                "name": "Woolcraft Dreamscape",
                "category": "3D Render",
                "prompt": "A tactile handcrafted world made from knitted wool and crochet.",
                "thumbnail": "thumbs/wool.png",
            }],
        }), encoding="utf-8")

        selected = catalog.get("woolcraft-dreamscape")
        self.assertEqual(selected.provider_id, "panelforge-local")
        self.assertEqual(catalog.thumbnail_path(selected.style_id).read_bytes(), b"wool")
        self.assertEqual(catalog.status()["local_style_count"], 1)

        catalog.install(force=True)
        self.assertEqual(catalog.get("woolcraft-dreamscape"), selected)


if __name__ == "__main__":
    unittest.main()
