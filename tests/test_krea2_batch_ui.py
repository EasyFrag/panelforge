from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Krea2BatchUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "src/panelforge/features/lab/static/index.html").read_text(encoding="utf-8")
        cls.script = (ROOT / "src/panelforge/features/lab/static/krea2-batch-lab.js").read_text(encoding="utf-8")
        cls.resources = (ROOT / "src/panelforge/features/lab/static/krea2-resource-ui.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "src/panelforge/features/lab/static/lab.css").read_text(encoding="utf-8")
        cls.navigation = (ROOT / "src/panelforge/features/lab/static/lab-core.js").read_text(encoding="utf-8")

    def test_exposes_recipe_batch_as_third_image_lab_mode(self):
        self.assertIn('id="krea2-batch-lab-workspace"', self.page)
        self.assertIn('data-image-lab-mode="krea2-batch-lab"', self.page)
        self.assertIn('/static/krea2-resource-ui.js?v=20260822.1', self.page)
        self.assertIn('/static/krea2-batch-lab.js?v=20260830.2', self.page)
        self.assertIn('"krea2-batch-lab"', self.navigation)

    def test_ui_supports_grouped_models_four_reorderable_loras_and_feedback(self):
        for label in ("Favoris · BF16", "Favoris · INT8", "BF16", "INT8", "SFW", "NSFW"):
            self.assertIn(label, self.resources)
        self.assertIn("appendGroupedOptions", self.script)
        self.assertIn("Array.from({ length: 4 }", self.script)
        self.assertIn('row.addEventListener("drop"', self.script)
        self.assertIn("update_available", self.script)
        self.assertIn("CivitAI", self.script)
        self.assertIn("saveReview", self.script)
        self.assertIn("proposeRevision", self.script)
        self.assertIn("testRevision", self.script)
        self.assertIn("saveRevision", self.script)
        self.assertIn('id="krea2-batch-revision-conversation"', self.page)
        self.assertIn('id="krea2-batch-test-revision"', self.page)
        self.assertIn('id="krea2-batch-save-revision"', self.page)
        self.assertIn('id="krea2-batch-recipe-language"', self.page)
        self.assertIn('id="krea2-batch-revision-language"', self.page)
        self.assertIn("prompt_language: elements.revisionLanguage.value", self.script)
        self.assertIn("playCompletionTone", self.script)
        self.assertIn("completionTone: false", self.script)
        self.assertGreaterEqual(self.script.count("core.createLlmOutcomeTone()"), 3)
        self.assertGreaterEqual(self.script.count("outcomeTone.success()"), 3)
        self.assertGreaterEqual(self.script.count("outcomeTone.failure()"), 3)
        self.assertIn('id="krea2-batch-catalog-manager"', self.page)
        self.assertIn("renderCatalogManager", self.script)
        self.assertIn("preferenceForLoraCategory", self.resources)
        self.assertIn('column.addEventListener("drop"', self.resources)
        self.assertIn('Forcer BF16', self.resources)

    def test_images_are_naturally_bounded_in_responsive_cards(self):
        self.assertIn(".krea2-batch-card-media img", self.styles)
        self.assertIn("object-fit: contain", self.styles)
        self.assertIn("grid-template-columns: repeat(auto-fill", self.styles)


if __name__ == "__main__":
    unittest.main()
