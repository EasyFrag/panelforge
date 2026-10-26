"""User-run regressions for the Lab's coherent, versioned static snapshot."""
from hashlib import sha256
from pathlib import Path
import re
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount, Route

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from panelforge.features.lab.static_assets import LabAssets


class LabStaticAssetsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "main.js").write_bytes(b"window.example = 1;")
        (self.root / "main.css").write_bytes(b"body { color: blue; }")
        (self.root / "other.txt").write_bytes(b"not immutable")
        (self.root / "index.html").write_text(
            '<link href="/static/main.css?v=manual" rel="stylesheet">'
            '<template data-lab-script="main.js"><script src="/static/main.js?v=manual" defer></script></template>',
            encoding="utf-8")
        self.assets, self.client = self.client_for_snapshot()

    def client_for_snapshot(self):
        assets = LabAssets(self.root)
        app = Starlette(routes=[Route("/", lambda request: assets.index()), Mount("/static", assets)])
        client = TestClient(app)
        self.addCleanup(client.close)
        return assets, client

    def versioned(self, name):
        digest = sha256((self.root / name).read_bytes()).hexdigest()
        return f"/static/{name}?v={digest}"

    def test_html_remains_uncached_and_versions_include_inert_scripts(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn(self.versioned("main.js"), response.text)
        self.assertIn(self.versioned("main.css"), response.text)
        self.assertIn('<template data-lab-script="main.js">', response.text)
        self.assertNotIn("v=manual", response.text)

    def test_exact_version_is_immutable_and_supports_conditional_get_and_head(self):
        url = self.versioned("main.js")
        response = self.client.get(url)
        self.assertEqual(response.content, (self.root / "main.js").read_bytes())
        self.assertEqual(response.headers["cache-control"], "private, max-age=31536000, immutable")
        for tag in [response.headers["etag"], "W/" + response.headers["etag"], '"other", ' + response.headers["etag"]]:
            cached = self.client.get(url, headers={"If-None-Match": tag})
            self.assertEqual(cached.status_code, 304)
            self.assertEqual(cached.content, b"")
        head = self.client.head(url)
        self.assertEqual(head.content, b"")
        self.assertEqual(head.headers["content-length"], str(len(response.content)))

    def test_unversioned_and_unlisted_assets_are_revalidated(self):
        for url in ["/static/main.js", "/static/main.css", "/static/other.txt?v=arbitrary"]:
            self.assertEqual(self.client.get(url).headers["cache-control"], "no-cache")

    def test_bad_or_ambiguous_versions_never_receive_immutable_bytes(self):
        for url in ["/static/main.js?v=old", self.versioned("main.js") + "&v=other"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_same_instance_keeps_old_bytes_and_new_instance_changes_version(self):
        old_url = self.versioned("main.js")
        old_content = self.client.get(old_url).content
        old_html = self.client.get("/").text
        (self.root / "main.js").write_bytes(b"window.example = 2;")
        self.assertEqual(self.client.get(old_url).content, old_content)
        self.assertEqual(self.client.get("/").text, old_html)
        _, fresh = self.client_for_snapshot()
        self.assertIn(self.versioned("main.js"), fresh.get("/").text)
        self.assertNotEqual(self.versioned("main.js"), old_url)
        self.assertEqual(fresh.get(old_url).status_code, 409)

    def test_real_manifest_is_complete_unique_and_keeps_cross_tab_handshake_eager(self):
        root = ROOT / "src/panelforge/features/lab/static"
        assets = LabAssets(root)
        loader = (root / "workshop-loader.js").read_text(encoding="utf-8")
        groups = loader.split("const views =", 1)[0]
        names = re.findall(r'"([a-z0-9-]+\.js)"', groups)
        declared = re.findall(r'<template data-lab-script="([^"]+)">', assets.html)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(declared))
        eager = re.sub(r"<template\b.*?</template>", "", assets.html, flags=re.S)
        for name in names:
            self.assertNotIn(f'/static/{name}?', eager)
        for name in ["lab-core.js", "krea2-assisted-lab.js", "video-factory.js", "dlss-lab.js"]:
            self.assertIn(f'/static/{name}?', eager)
        self.assertLess(eager.index("workshop-loader.js"), eager.index("lab-core.js"))
        for name, (content, digest, _) in assets.assets.items():
            self.assertEqual(digest, sha256(content).hexdigest())
            self.assertIn(f"/static/{name}?v={digest}", assets.html)


if __name__ == "__main__":
    unittest.main()
