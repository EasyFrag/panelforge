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
        self.assertIn('/static/krea2-resource-ui.js?v=20260904.1', self.page)
        self.assertIn('/static/krea2-batch-lab.js?v=20260903.2', self.page)
        self.assertIn('"krea2-batch-lab"', self.navigation)

    def test_ui_supports_modern_models_ten_reorderable_loras_and_feedback(self):
        for label in (
            "Favoris · BF16", "Favoris · INT8", "BF16", "INT8",
            "SFW · Sliders", "NSFW · Sliders", "NSFW · Poses",
        ):
            self.assertIn(label, self.resources)
        self.assertIn("renderModelPicker", self.script)
        self.assertIn("renderLoraPickerStack", self.script)
        self.assertIn("maximum: 10", self.script)
        self.assertIn("draggable: true", self.script)
        self.assertIn("Rechercher une LoRA", self.resources)
        self.assertIn("+ Ajouter une LoRA", self.resources)
        self.assertIn("krea2-lora-picker-dialog", self.resources)
        self.assertIn("krea2-model-picker-dialog", self.resources)
        self.assertIn("Rechercher un checkpoint", self.resources)
        self.assertIn("krea2-resource-favorite", self.resources)
        self.assertIn("krea2-lora-picker-group", self.resources)
        self.assertIn("Recherche des aperçus disponibles", self.resources)
        self.assertNotIn('info.addEventListener("click", () => dialog.close()', self.resources)
        self.assertIn("!selected.has(resource.comfy_name)", self.resources)
        self.assertIn('row.addEventListener("drop"', self.resources)
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
        self.assertIn("krea2-catalog-lora-list", self.resources)
        self.assertIn("openResourceInfo", self.resources)
        self.assertIn("Recherche par hash de sidecar", self.resources)
        self.assertIn("sans calculer le hash du mod", self.resources)
        self.assertIn('edit.textContent = "✎"', self.resources)
        self.assertIn("resource.preview_urls.slice(0, 3)", self.resources)
        self.assertIn("display_name: nameInput.value.trim() || null", self.resources)
        self.assertIn("La force minimale doit être inférieure", self.resources)
        self.assertIn(".krea2-resource-dialog-editor", self.styles)
        self.assertIn("#krea2-assisted-loras { grid-template-columns: 1fr", self.styles)
        self.assertIn("Le favori reste indépendant de la catégorie", self.resources)
        self.assertNotIn('column.addEventListener("drop"', self.resources)
        self.assertIn('Forcer BF16', self.resources)

    def test_images_are_naturally_bounded_in_responsive_cards(self):
        self.assertIn(".krea2-batch-card-media img", self.styles)
        self.assertIn("object-fit: contain", self.styles)
        self.assertIn("grid-template-columns: repeat(auto-fill", self.styles)


if __name__ == "__main__":
    unittest.main()
