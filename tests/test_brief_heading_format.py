"""Regression coverage for complete Briefs returned with bold headings."""

import unittest

from panelforge.application.prompt_lab import _BRIEF_CONTRACT, _normalize_brief_document


class BriefHeadingFormatTest(unittest.TestCase):
    def test_bold_headings_preserve_body_and_normalize_to_existing_contract(self):
        body = "Keep **this emphasis** and the user's exact wording."
        canonical = "\n\n".join(f"{marker}\n{body}" for marker in _BRIEF_CONTRACT.markers)
        for prefix in ("", "- "):
            with self.subTest(prefix=prefix):
                formatted = "\n\n".join(
                    f"{prefix}**{marker.removeprefix('- ')}**\n{body}"
                    for marker in _BRIEF_CONTRACT.markers
                )
                self.assertEqual(_normalize_brief_document(formatted), _normalize_brief_document(canonical))

    def test_bold_format_does_not_make_an_incomplete_brief_valid(self):
        first_heading = _BRIEF_CONTRACT.markers[0].removeprefix("- ")
        with self.assertRaises(ValueError):
            _normalize_brief_document(f"**{first_heading}**\nOnly one section.")
