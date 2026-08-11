from __future__ import annotations

import unittest

from panelforge.infrastructure.prompt_cookbooks import _semantic_version_key


class PromptCookbookVersionTests(unittest.TestCase):
    def test_semantic_versions_are_sorted_numerically(self) -> None:
        versions = ("0.10.0", "0.9.0", "1.0.0-beta.1", "1.0.0")

        self.assertEqual(
            sorted(versions, key=_semantic_version_key),
            ["0.9.0", "0.10.0", "1.0.0-beta.1", "1.0.0"],
        )


if __name__ == "__main__":
    unittest.main()
