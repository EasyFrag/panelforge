from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "panelforge" / "features" / "lab" / "static"


class Krea2AssistedUiTest(unittest.TestCase):
    def setUp(self):
        self.page = (STATIC / "index.html").read_text(encoding="utf-8")
        self.script = (STATIC / "krea2-assisted-lab.js").read_text(encoding="utf-8")
        self.css = (STATIC / "lab.css").read_text(encoding="utf-8")

    def test_exposes_a_distinct_assisted_creation_mode(self):
        self.assertIn('id="krea2-assisted-lab-workspace"', self.page)
        self.assertIn('data-image-lab-mode="krea2-assisted-lab"', self.page)
        self.assertIn('/static/krea2-assisted-lab.js?v=20260903.2', self.page)
        self.assertIn('"krea2-assisted-lab"', (STATIC / "lab-core.js").read_text(encoding="utf-8"))

    def test_initial_visible_assisted_view_loads_its_catalog_automatically(self):
        self.assertIn(
            "if (!elements.workspace.hidden) initialize();",
            self.script,
        )
        self.assertIn("if (state.initializing) return state.initializing;", self.script)

    def test_chat_reports_the_validated_llm_outcome_with_distinct_tones(self):
        self.assertIn("core.createLlmOutcomeTone()", self.script)
        self.assertIn("outcomeTone.start()", self.script)
        self.assertIn("outcomeTone.success()", self.script)
        self.assertIn("outcomeTone.failure()", self.script)
        self.assertIn("{ completionTone: false }", self.script)

    def test_keeps_the_same_mode_order_in_every_image_lab_workspace(self):
        expected = [
            "krea2-assisted-lab",
            "change-view",
            "krea2-image-lab",
            "krea2-batch-lab",
            "krea2-edit-lab",
        ]
        modebars = re.findall(
            r'<nav class="image-lab-modebar"[^>]*>(.*?)</nav>',
            self.page,
            flags=re.DOTALL,
        )
        self.assertEqual(len(modebars), 5)
        for modebar in modebars:
            self.assertEqual(
                re.findall(r'data-image-lab-mode="([^"]+)"', modebar),
                expected,
            )

    def test_displays_the_change_view_recipe_in_its_vertical_panel(self):
        change_view_start = self.page.index('<main id="change-view-workspace"')
        topbar = self.page[:change_view_start]
        change_view = self.page[
            change_view_start :
            self.page.index('<main id="krea2-image-lab-workspace"')
        ]
        self.assertNotIn('id="recipe-badge"', topbar)
        self.assertIn(
            '<span id="recipe-badge" class="experimental">character.change_view · '
            '<span id="recipe-version">…</span></span>',
            change_view,
        )

    def test_keeps_conversation_and_settings_before_the_bottom_gallery(self):
        conversation = self.page.index('id="krea2-assisted-conversation"')
        settings = self.page.index('id="krea2-assisted-model"')
        gallery = self.page.index('id="krea2-assisted-gallery"')
        self.assertLess(conversation, settings)
        self.assertLess(settings, gallery)
        self.assertIn('id="krea2-assisted-reference"', self.page)
        self.assertIn('id="krea2-assisted-recipe-draft"', self.page)
        self.assertIn('id="krea2-assisted-lightbox"', self.page)
        self.assertIn("[...(project.attempts || [])].reverse().forEach", self.script)

    def test_reuses_grouped_resources_and_never_calls_the_edit_workflow(self):
        self.assertIn("resourceUi.renderModelPicker", self.script)
        self.assertIn("resourceUi.renderLoraStack", self.script)
        self.assertIn("maximum: 10", self.script)
        self.assertIn("GENERATED RESULT", (ROOT / "src" / "panelforge" / "application" / "krea2_assisted.py").read_text(encoding="utf-8"))
        self.assertNotIn("/api/image-lab/krea2-edit", self.script)
        self.assertIn(".krea2-assisted-gallery", self.css)
        self.assertIn("max-height: 72vh", self.css)

    def test_render_primary_button_keeps_a_contrasted_background_inside_actions(self):
        self.assertIn('id="krea2-assisted-render" class="primary"', self.page)
        self.assertIn(".actions button.primary {", self.css)
        self.assertIn("color: white; background: var(--green);", self.css)

    def test_reopening_a_persisted_project_reenables_its_actions(self):
        open_project = self.script[
            self.script.index("async function openProject") :
            self.script.index("async function createProject")
        ]
        self.assertIn("if (state.busy) return;", open_project)
        self.assertIn("setBusy(true);", open_project)
        self.assertIn("finally {\n      setBusy(false);\n    }", open_project)

    def test_attempt_cards_summarize_render_settings_and_loras(self):
        self.assertIn("settings.resolution || {}", self.script)
        self.assertIn("`Modèle · ${compactResourceName(settings.model_id)}", self.script)
        self.assertIn("`LoRA · ${loraSummary}`", self.script)
        self.assertIn("strengthLabel(lora.strength)", self.script)

    def test_attempt_actions_are_compact_and_feedback_is_a_toggle(self):
        self.assertIn('reuse.textContent = "Reprendre réglages"', self.script)
        self.assertIn('feedback.textContent = feedbackSelected ? "Feedback ✓" : "Feedback"', self.script)
        self.assertIn("selectFeedback(feedbackSelected ? null : attempt.attempt_id)", self.script)
        self.assertIn('save.textContent = attempt.accepted ? "Enregistrée ✓" : "Enregistrer"', self.script)
        self.assertIn("grid-template-columns: 1.35fr .8fr .9fr", self.css)

    def test_lora_stack_uses_compact_single_line_rows(self):
        self.assertIn(
            "#krea2-assisted-loras { grid-template-columns: 1fr",
            self.css,
        )
        self.assertIn(
            "#krea2-assisted-loras .krea2-lora-active-row",
            self.css,
        )
        self.assertNotIn('row.draggable = true', self.script)
        self.assertNotIn('row.addEventListener("dragstart"', self.script)
        self.assertIn("0 à 10 · seuls les emplacements utilisés sont affichés", self.page)

    def test_prompt_language_can_switch_between_iterations(self):
        self.assertIn('id="krea2-assisted-prompt-language"', self.page)
        self.assertIn('<option value="en" selected>English</option>', self.page)
        self.assertIn('<option value="zh">中文</option>', self.page)
        self.assertIn('project.prompt_language || "en"', self.script)
        self.assertIn('prompt_language: elements.promptLanguage.value', self.script)
        self.assertIn("elements.promptLanguage.disabled = value || !state.project", self.script)

    def test_revision_model_is_independent_and_sent_with_each_chat(self):
        self.assertIn('id="krea2-assisted-revision-llm"', self.page)
        self.assertIn(
            'data-llm-local-for="krea2-assisted-revision-llm"',
            self.page,
        )
        self.assertIn(
            "project.revision_model_id || project.model_id",
            self.script,
        )
        self.assertIn(
            "model_id: elements.revisionLlm.value",
            self.script,
        )

    def test_turn_guidance_image_is_compact_persisted_and_reusable(self):
        self.assertIn('id="krea2-assisted-guidance-file"', self.page)
        self.assertIn('id="krea2-assisted-guidance-preview"', self.page)
        self.assertIn("guidance_asset_id: guidance?.asset_id || null", self.script)
        self.assertIn('reuse.textContent = "Réutiliser"', self.script)
        self.assertIn("async function resolveGuidance()", self.script)
        self.assertIn(".krea2-assisted-turn-guidance", self.css)
        self.assertIn(".krea2-assisted-guidance-preview", self.css)
        self.assertIn('id="krea2-assisted-guidance-dock"', self.page)
        self.assertIn('id="krea2-assisted-guidance-dock-image"', self.page)
        self.assertIn(
            'elements.conversationLayout.classList.toggle("has-guidance", Boolean(conversationPreview))',
            self.script,
        )
        self.assertIn(
            'elements.guidanceDockOpen.addEventListener("click", openCurrentGuidance)',
            self.script,
        )
        self.assertIn(
            ".krea2-assisted-conversation-layout.has-guidance",
            self.css,
        )
        self.assertIn("function selectedFeedbackPreview()", self.script)
        self.assertIn("value.attempt_id === project.feedback_attempt_id && value.output_url", self.script)
        self.assertIn('kind: "FEEDBACK VISUEL"', self.script)
        self.assertIn("const conversationPreview = currentConversationPreview();", self.script)
        self.assertIn('id="krea2-assisted-guidance-dock-kind"', self.page)


if __name__ == "__main__":
    unittest.main()
