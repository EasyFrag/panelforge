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
        self.assertIn('/static/krea2-assisted-lab.js?v=20260919.1', self.page)
        self.assertIn('id="krea2-assisted-workflow"', self.page)
        self.assertIn('workflow: elements.workflow.value', self.script)
        self.assertIn('Image KREA2 avant Flux', self.script)
        self.assertIn('Télécharger l’image pré-Flux', self.script)
        self.assertIn('<option value="3.0.0" selected>V3', self.page)
        self.assertIn('id="krea2-assisted-new-preset"', self.page)
        self.assertIn('id="krea2-assisted-preset-dialog"', self.page)
        self.assertIn('id="krea2-assisted-preset-note"', self.page)
        self.assertIn('"krea2-assisted-lab"', (STATIC / "lab-core.js").read_text(encoding="utf-8"))

    def test_new_project_precedes_history_stays_collapsed_and_defaults_to_local_gemma(self):
        new_project = self.page.index('id="krea2-assisted-new-project"')
        history = self.page.index('class="krea2-assisted-recent-projects"')
        self.assertLess(new_project, history)
        details_tag = self.page[self.page.rfind("<details", 0, new_project):self.page.index(">", new_project) + 1]
        self.assertNotRegex(details_tag, r"\sopen(?:\s|=|>)")
        self.assertNotIn("!state.projects.length) elements.newProject.open = true", self.script)
        self.assertIn('const defaultNewProjectLlm = "unsloth/gemma-4-31b-it-qat-GGUF";', self.script)
        self.assertIn('data-llm-local-for="krea2-assisted-llm" checked', self.page)
        self.assertIn('model.source === "local"', self.script)

    def test_header_has_one_compact_refresh_for_all_assisted_resources(self):
        self.assertEqual(self.page.count('id="krea2-assisted-refresh-all"'), 1)
        self.assertNotIn('id="krea2-assisted-refresh-llms"', self.page)
        self.assertNotIn('id="krea2-assisted-refresh"', self.page)
        self.assertIn('title="Tout actualiser"', self.page)
        self.assertIn('elements.refreshAll.addEventListener("click", refreshAllResources);', self.script)
        refresh = self.script[
            self.script.index("async function refreshAllResources") :
            self.script.index('elements.newForm.addEventListener("submit"')
        ]
        self.assertIn('refreshCatalog(true, true)', refresh)
        self.assertIn('loadPresets()', refresh)
        self.assertIn('loadHistory()', refresh)
        self.assertIn('Promise.allSettled', refresh)
        self.assertIn('classList.add("refreshing")', refresh)
        self.assertIn('{ showRefresh: false }', self.script)
        self.assertIn('.krea2-assisted-refresh-all.refreshing svg', self.css)

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
        self.assertIn("[...groups].reverse().forEach", self.script)

    def test_reuses_grouped_resources_and_never_calls_the_edit_workflow(self):
        self.assertIn("resourceUi.renderModelPicker", self.script)
        self.assertIn("resourceUi.renderLoraStack", self.script)
        self.assertIn("maximum: 10", self.script)
        self.assertIn("GENERATED RESULT", (ROOT / "src" / "panelforge" / "application" / "krea2_assisted.py").read_text(encoding="utf-8"))
        self.assertNotIn("/api/image-lab/krea2-edit", self.script)
        self.assertIn(".krea2-assisted-gallery", self.css)
        self.assertIn("max-height: 72vh", self.css)

    def test_render_queue_has_atomic_enqueue_and_individual_actions(self):
        self.assertIn('id="krea2-assisted-queue-summary"', self.page)
        self.assertIn('id="krea2-assisted-queue-open"', self.page)
        render = self.script[self.script.index("async function renderAttempt") : self.script.index("async function startPreparedAttempt")]
        self.assertIn("/attempts?enqueue=true", render)
        self.assertNotIn("/start", render)
        self.assertIn("Ajouter cet essai à la file", self.script)
        self.assertIn("cancelAttempt(attempt.attempt_id)", self.script)
        self.assertIn("position ${item.position}", self.script)

    def test_render_primary_button_keeps_a_contrasted_background_inside_actions(self):
        self.assertIn('id="krea2-assisted-render" class="primary"', self.page)
        self.assertIn(".actions button.primary {", self.css)
        self.assertIn("color: white; background: var(--green);", self.css)

    def test_reopening_a_persisted_project_reenables_its_actions(self):
        open_project = self.script[
            self.script.index("async function openProject") :
            self.script.index("async function createProject")
        ]
        self.assertIn("state.busy && !state.projectRequest", open_project)
        self.assertIn("state.projectRequest?.abort()", open_project)
        self.assertIn("if (state.projectRequest !== controller) return;", open_project)
        self.assertIn("setBusy(true);", open_project)
        self.assertIn("state.projectRequest = null;\n        setBusy(false);", open_project)

    def test_attempt_cards_summarize_render_settings_and_loras(self):
        self.assertIn("settings.resolution || {}", self.script)
        self.assertIn(
            '`${workflowSpec(settings.workflow)?.label || "KREA2"} · '
            '${compactResourceName(settings.model_id)}',
            self.script,
        )
        self.assertIn('${settings.megapixels} MP${finalMp ? " final" : ""}', self.script)
        self.assertIn('"LoRA"} · ${loraSummary}`', self.script)
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
        self.assertIn('id="krea2-assisted-new-prompt-language"', self.page)
        self.assertIn('id="krea2-assisted-prompt-language"', self.page)
        self.assertIn('<option value="en" selected>English</option>', self.page)
        self.assertIn('<option value="zh">中文</option>', self.page)
        self.assertIn('project.prompt_language || "en"', self.script)
        self.assertIn('prompt_language: elements.promptLanguage.value', self.script)
        self.assertIn('data.set("prompt_language", elements.newPromptLanguage.value)', self.script)
        self.assertIn('id="krea2-assisted-convert-language"', self.page)
        self.assertIn('async function convertPromptLanguage()', self.script)
        self.assertIn("elements.promptLanguage.disabled = value || !state.project", self.script)

    def test_style_presets_are_grouped_manageable_and_keep_pinned_project_copies(self):
        self.assertIn('id="krea2-assisted-preset-manager"', self.page)
        self.assertIn('id="krea2-assisted-preset-category"', self.page)
        self.assertEqual(self.page.count('data-krea2-preset-manage'), 2)
        self.assertIn('["work", "Work"], ["fun", "Fun"], ["nsfw", "NSFW"], ["archive", "Archive"]', self.script)
        self.assertIn('method: "PATCH"', self.script)
        self.assertIn('method: "DELETE"', self.script)
        self.assertIn('copie conservée', self.script)
        self.assertIn('.krea2-preset-manager-row', self.css)

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
            'elements.conversationLayout.classList.toggle("has-guidance", Boolean(conversationPreview || feedback))',
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

    def test_feedback_and_inspiration_have_independent_cards(self):
        self.assertIn('id="krea2-assisted-feedback-card"', self.page)
        self.assertIn('id="krea2-assisted-inspiration-card"', self.page)
        self.assertIn('elements.feedbackCard.hidden = !feedback', self.script)
        self.assertIn('elements.inspirationCard.hidden = !conversationPreview', self.script)
        self.assertIn('!conversationPreview && !feedback', self.script)

    def test_branch_actions_are_optional_and_old_attempts_are_explicit(self):
        self.assertIn('id="krea2-assisted-branches"', self.page)
        self.assertIn('id="krea2-assisted-branch-tree"', self.page)
        self.assertIn('"Repartir d’ici" : "Nouvelle piste · image + prompt"', self.script)
        self.assertIn('expected_branch_id: state.project.active_branch_id', self.script)
        self.assertIn('image_prompt_only: !attempt.can_restore_conversation', self.script)
        self.assertIn('button.setAttribute("aria-current", String(active))', self.script)
        self.assertIn('serial !== state.navigationSerial', self.script)


if __name__ == "__main__":
    unittest.main()
