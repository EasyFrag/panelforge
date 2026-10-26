"""User-run catalogue regressions; temporary YAML only, no model calls."""
from collections import Counter
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from panelforge.infrastructure.krea2_wildcards import LocalKrea2WildcardLibrary, _source_lines


class CatalogueStartupTests(unittest.TestCase):
    def test_each_yaml_is_read_once_and_source_lines_stay_correct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shared-common.yaml").write_text("shared:\n  light:\n  - natural light\n", encoding="utf-8")
            expected = {}
            for prefix in ("portraits", "landscapes"):
                lines = [prefix + ":", "  template:"]
                for i in range(40):
                    name = f"scene-{i}"
                    expected[f"{prefix}/template/{name}"] = len(lines) + 1
                    lines += [f"    {name}:", "    - An adult photographer outdoors in __shared/light__. [3:4]"]
                (root / (prefix + ".yaml")).write_text("\n".join(lines), encoding="utf-8")
            reads = Counter()
            original = Path.read_text

            def read(path, *args, **kwargs):
                if path.parent == root and path.suffix == ".yaml":
                    reads[path.name] += 1
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", read):
                library = LocalKrea2WildcardLibrary(root, seed_factory=lambda: 42)
                self.assertEqual(library.status()["state"], "ready")
                self.assertEqual(library.status()["template_count"], 80)
                self.assertEqual({t.template_id: t.source_line for t in library._templates}, expected)
                first = library.search("adult photographer outdoors", limit=3)
                second = library.search("adult photographer outdoors", limit=3)
                self.assertEqual(first, second)
                self.assertTrue(first)
                self.assertTrue(all("__" not in example.prompt for example in first))
                self.assertEqual(reads, {"shared-common.yaml": 1, "portraits.yaml": 1, "landscapes.yaml": 1})

    def test_line_index_preserves_legacy_literal_matching_and_fallback(self):
        # This is the previous public audit-line behavior, including its first
        # match rule and fallback for quoted/commented YAML keys.
        content = "\n".join([
            "outside:", "root:", "  template:", "    duplicate:", "    - first",
            "    a.b[1]+:", "    - value", "\tunicode-é:\t", "    - value",
            "    duplicate:", "    - second", "    'quoted':", "    - value",
            "    commented: # comment", "    spaced :", "    colon:key:", "    :",
        ])
        index = _source_lines(content)
        for key in ["outside", "template", "duplicate", "a.b[1]+", "unicode-é", "quoted",
                    "commented", "spaced", "spaced ", "colon:key", " duplicate", "", " ", "missing"]:
            with self.subTest(key=key):
                pattern = re.compile(rf"^\s+{re.escape(key)}:\s*$")
                expected = next((n for n, line in enumerate(content.splitlines(), 1) if pattern.match(line)), 1)
                self.assertEqual(index.get(key, 1), expected)

    def test_reopening_catalogue_reads_new_content_and_keeps_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "landscapes.yaml"
            source.write_text("landscapes:\n  template:\n    outdoors:\n    - An adult photographer outdoors.\n", encoding="utf-8")
            first = LocalKrea2WildcardLibrary(root)
            self.assertEqual(first.status()["state"], "ready")
            source.write_text("# moved\nlandscapes:\n  template:\n    outdoors:\n    - An adult photographer outdoors.\n", encoding="utf-8")
            second = LocalKrea2WildcardLibrary(root)
            self.assertEqual(second.status()["state"], "ready")
            self.assertEqual(second._templates[0].source_line, first._templates[0].source_line + 1)
            source.write_text("landscapes:\n  template:\n    outdoors:\n    - __missing/light__\n", encoding="utf-8")
            invalid = LocalKrea2WildcardLibrary(root)
            self.assertEqual(invalid.status()["state"], "failed")
            self.assertEqual(invalid.status()["template_count"], 0)


if __name__ == "__main__":
    unittest.main()
