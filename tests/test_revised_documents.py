import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application.revised_documents import RevisedDocumentContract


class RevisedDocumentContractTest(unittest.TestCase):
    def setUp(self):
        self.contract = RevisedDocumentContract(
            "brief",
            ("INTENTION CENTRALE", "CONTRAINTES STRICTES", "QUESTIONS OU AMBIGUÏTÉS"),
        )
        self.document = """INTENTION CENTRALE
Une action révisée.

CONTRAINTES STRICTES
Conserver le sujet.

QUESTIONS OU AMBIGUÏTÉS
N/A"""

    def test_extracts_only_the_document_from_an_echoed_context(self):
        response = "CONTEXTE EN LECTURE SEULE\nDétails source\n\n" + self.document

        self.assertEqual(self.contract.extract(response), self.document)

    def test_rejects_two_complete_documents_as_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "multiple documents"):
            self.contract.extract(self.document + "\n\n" + self.document)

    def test_rejects_missing_or_reordered_sections(self):
        with self.assertRaisesRegex(ValueError, "missing marker"):
            self.contract.extract("INTENTION CENTRALE\nIncomplet")
        with self.assertRaisesRegex(ValueError, "out of order"):
            self.contract.extract(
                "CONTRAINTES STRICTES\nX\nINTENTION CENTRALE\nY\n"
                "QUESTIONS OU AMBIGUÏTÉS\nN/A"
            )

    def test_can_preserve_unstructured_legacy_revisions(self):
        self.assertEqual(
            self.contract.extract("Révision libre", strict=False),
            "Révision libre",
        )

    def test_legacy_fallback_does_not_accept_a_partial_structured_document(self):
        with self.assertRaisesRegex(ValueError, "missing marker"):
            self.contract.extract(
                "INTENTION CENTRALE\nIncomplet",
                strict=False,
            )


if __name__ == "__main__":
    unittest.main()
