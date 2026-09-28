from __future__ import annotations

import unittest

from panelforge.domain.krea2_art_direction import (
    Krea2ArtDirection,
    compile_krea2_art_direction,
    validate_art_sources,
)


class Krea2ArtDirectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.direction = Krea2ArtDirection(
            provider_id="clio",
            style_id="Beatrix Potter Style (2)",
            name="Beatrix Potter Style (2)",
            category="Drawing",
            prompt="Delicate watercolor washes and restrained ink contours",
            catalog_revision="fixture-revision",
        )

    def test_compiler_keeps_subject_separate_and_removes_catalog_suffix(self) -> None:
        self.assertEqual(
            compile_krea2_art_direction("A fox waits beside a stream", self.direction),
            "Style: Beatrix Potter Style: Delicate watercolor washes and restrained ink contours. "
            "Subject: A fox waits beside a stream",
        )

    def test_compiler_is_identity_without_direction(self) -> None:
        self.assertEqual(
            compile_krea2_art_direction("  A fox waits beside a stream  ", None),
            "A fox waits beside a stream",
        )

    def test_personal_preset_and_catalog_direction_can_be_composed(self) -> None:
        validate_art_sources(object(), self.direction)


if __name__ == "__main__":
    unittest.main()
