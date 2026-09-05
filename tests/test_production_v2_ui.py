from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductionV2UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = (ROOT / "src/panelforge/features/lab/static/index.html").read_text(encoding="utf-8")
        cls.script = (ROOT / "src/panelforge/features/lab/static/production-v2-lab.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "src/panelforge/features/lab/static/lab.css").read_text(encoding="utf-8")
        cls.web = (ROOT / "src/panelforge/features/lab/web.py").read_text(encoding="utf-8")
        cls.resources = (ROOT / "src/panelforge/features/lab/static/krea2-resource-ui.js").read_text(encoding="utf-8")

    def test_is_a_dedicated_page_without_replacing_v1(self) -> None:
        self.assertIn('data-lab-view="production-v2-lab"', self.page)
        self.assertIn('id="production-v2-lab-workspace"', self.page)
        self.assertIn('id="production-lab-workspace"', self.page)
        self.assertIn("Validation humaine", self.page)

    def test_memory_profile_creation_uses_a_visible_inline_editor(self) -> None:
        for identifier in (
            "production-v2-create-memory-editor",
            "production-v2-create-memory-name",
            "production-v2-create-memory-save",
            "production-v2-create-memory-cancel",
        ):
            self.assertIn(f'id="{identifier}"', self.page)
        self.assertIn("function toggleMemoryProfileEditor()", self.script)
        self.assertIn("function closeMemoryProfileEditor()", self.script)
        self.assertIn("elements.createMemoryName.value.trim()", self.script)
        self.assertNotIn('window.prompt("Nom du nouveau profil', self.script)
        self.assertIn(".production-v2-memory-create[hidden]", self.styles)

    def test_progressive_sidebar_keeps_all_three_stages_reopenable(self) -> None:
        for identifier in (
            "production-v2-project-section",
            "production-v2-image-section",
            "production-v2-video-section",
        ):
            self.assertIn(f'id="{identifier}"', self.page)
        self.assertIn("state.lastStage !== project.stage", self.script)
        self.assertIn("Base visuelle r", self.script)

    def test_human_workshop_has_memory_feedback_and_anchor_routes(self) -> None:
        for value in ("calibration", "first_frame", "last_frame", "reference"):
            self.assertIn(f'value="{value}"', self.page)
        self.assertIn("Aucune recommandation LLM comparative", self.page)
        self.assertIn("/candidates/${candidateId}/review", self.script)
        self.assertIn("/visual-recipe/${candidateId}", self.script)
        self.assertIn("/anchors", self.script)
        self.assertIn("Continuer depuis cette image", self.script)
        self.assertIn("cloneAtResolution", self.script)
        self.assertIn('[[2.1, "2,1"], [4, "4"]]', self.script)
        self.assertIn("Passer en ${label} MP", self.script)
        self.assertIn("Utiliser directement en Ref2V", self.script)
        self.assertIn("Démarrer Ref2V avec cette référence", self.script)
        self.assertIn('role === "reference" && !state.project.active_recipe', self.script)
        self.assertIn('? directRef2v(candidate.candidate_id)', self.script)

    def test_base_is_soft_and_iteration_preservation_is_explicit(self) -> None:
        self.assertIn('id="production-v2-lora-assisted"', self.page)
        self.assertIn('id="production-v2-prompt-strategy"', self.page)
        self.assertIn('id="production-v2-preserve-seed"', self.page)
        self.assertIn('id="production-v2-preserve-model"', self.page)
        self.assertIn('id="production-v2-preserve-loras"', self.page)
        self.assertIn('value="preserve_current"', self.page)
        self.assertIn('value="rewrite_once"', self.page)
        self.assertIn('value="evolve_between"', self.page)
        self.assertIn("prompt_strategy: elements.promptStrategy.value", self.script)
        self.assertIn("réglages encore modifiables", self.script)
        self.assertNotIn("element.disabled = locked || isBusy()", self.script)
        self.assertIn("/resolution-clone", self.script)
        self.assertIn("/direct-ref2v", self.script)

    def test_visual_recipe_can_be_used_directly_as_first_or_last_frame(self) -> None:
        self.assertIn('actions.className = "production-v2-base-anchor-actions"', self.script)
        self.assertIn('[["first_frame", "First frame"], ["last_frame", "Last frame"]]', self.script)
        self.assertIn("promoteAnchor(recipe.source_candidate_id, false, role)", self.script)
        self.assertIn("anchor.asset_id === recipe.asset_id", self.script)
        self.assertIn(".production-v2-base-anchor-actions", self.styles)

    def test_iteration_is_always_custom_and_exposes_cost(self) -> None:
        self.assertNotIn('id="production-v2-iteration-preset"', self.page)
        self.assertNotIn("function applyIterationPreset(presetId)", self.script)
        self.assertIn("function resetIterationControls()", self.script)
        self.assertIn("function llmCost()", self.script)
        self.assertIn("rendu${cost.count > 1", self.script)
        self.assertIn("elements.generateImages.title", self.script)
        self.assertIn("elements.imageInstruction.disabled = preservePrompt", self.script)
        self.assertIn("explore_models: !elements.preserveModel.checked", self.script)
        self.assertIn('model_name: chosen', self.script)
        self.assertIn("Checkpoint du candidat 1", self.page)
        self.assertIn("tirés aléatoirement en favorisant les moins utilisés", self.page)

    def test_lora_selection_activates_and_assisted_mode_has_enough_candidates(self) -> None:
        self.assertIn("resourceUi.renderLoraStack", self.script)
        self.assertIn("defaultStrength = 1", self.resources)
        self.assertIn("function configureAssistedLoraExploration()", self.script)
        self.assertIn('if (Number(elements.count.value) < 3)', self.script)
        self.assertIn(
            'if (elements.loraAssisted.checked && Number(elements.count.value) < 3)',
            self.script,
        )
        self.assertIn("une baseline et des variantes distinctes", self.page)
        self.assertIn("font-size: .64rem; line-height: 1.45", self.styles)

    def test_candidate_history_is_grouped_into_collapsible_role_workshops(self) -> None:
        self.assertIn("production-v2-candidate-workshop", self.script)
        self.assertIn("Recherche de la base visuelle", self.script)
        self.assertIn("Recherche de la première frame", self.script)
        self.assertIn("Recherche de la dernière frame", self.script)
        self.assertIn("Recherche de références Ref2V", self.script)

    def test_video_defaults_are_visible_and_final_is_explicit(self) -> None:
        self.assertIn("6 s · 25 steps + 3 raffinement · Spectrum ON", self.page)
        self.assertIn("Rendu final 1,2 MP", self.page)
        self.assertIn("Envoyer au LLM", self.page)
        self.assertIn('id="production-v2-video-intention"', self.page)
        self.assertIn('id="production-v2-compile-llm"', self.page)
        self.assertIn('data-llm-local-for="production-v2-compile-llm"', self.page)
        self.assertIn('id="production-v2-video-spectrum"', self.page)
        self.assertIn('id="production-v2-video-lora"', self.page)
        self.assertIn("production-v2-video-llm", self.page)
        self.assertIn('id="production-v2-creative-audacity"', self.page)
        self.assertIn('id="production-v2-revision-audacity"', self.page)
        self.assertIn("0 standard historique", self.page)
        self.assertIn("creative_audacity: Number(elements.creativeAudacity.value)", self.script)
        self.assertIn("compile_model_id: elements.compileLlm.value", self.script)
        self.assertIn("revision_audacity: Number(elements.revisionAudacity.value)", self.script)
        self.assertIn("Brief → Plan → Prompt + preview ${previewMp} MP", self.script)
        self.assertIn("puis lancera une nouvelle preview", self.script)
        self.assertIn('videoPreviewMp.addEventListener("input", renderControls)', self.script)
        self.assertIn("queue_video_compile(project_id, render_preview=True)", self.web)
        self.assertIn("/video/revise", self.script)
        self.assertIn('instruction: ""', self.script)
        self.assertIn('id="production-v2-video-revision-draft"', self.page)
        self.assertIn('id="production-v2-video-revision-retry"', self.page)
        self.assertIn('id="production-v2-video-duration-warning"', self.page)
        self.assertIn("prompt courant n’a pas été modifié", self.page)
        self.assertIn("repair_rejected: true", self.script)
        self.assertIn("function renderVideoDurationWarning()", self.script)
        self.assertIn("Les timestamps et l’ancre finale ne sont pas réécrits automatiquement", self.script)

    def test_active_loras_remain_visible_when_candidate_details_are_collapsed(self) -> None:
        self.assertIn('metaSummary.className = "production-v2-candidate-meta-summary"', self.script)
        self.assertIn('activeLoras.className = "production-v2-candidate-active-loras"', self.script)
        self.assertIn("name.title = lora.name", self.script)
        self.assertIn(".production-v2-candidate-active-loras", self.styles)

    def test_video_progress_and_media_are_stable_during_polling(self) -> None:
        self.assertIn('id="production-v2-render-progress"', self.page)
        self.assertIn("panelforge_render_progress", self.script)
        self.assertIn('id="production-v2-render-live-preview"', self.page)
        self.assertIn('id="production-v2-render-cancel"', self.page)
        self.assertIn('socket.binaryType = "arraybuffer"', self.script)
        self.assertIn('payload.type === "kj_preview_override"', self.script)
        self.assertIn("binaryRenderPreview(event.data)", self.script)
        self.assertIn("mediaSignature === state.videoRenderSignature", self.script)
        self.assertIn("right.index - left.index", self.script)

    def test_each_preview_can_launch_its_own_final_snapshot(self) -> None:
        self.assertIn("Générer en ${String(finalMp)", self.script)
        self.assertIn("renderFinalFromPreview(attempt.attempt_id)", self.script)
        self.assertIn("attempt.effective_prompt || attempt.prompt", self.script)
        self.assertIn("Reprend le prompt, la seed et tous les réglages", self.script)

    def test_candidate_context_and_chat_stay_next_to_feedback(self) -> None:
        self.assertIn('class="production-v2-feedback-context"', self.page)
        self.assertIn('id="production-v2-parent-image"', self.page)
        self.assertIn('id="production-v2-krea-chat"', self.page)
        self.assertIn("candidate.conversation", self.script)
        self.assertIn("applySettingsToControls(candidate.settings)", self.script)

    def test_visual_guidance_and_role_branches_are_explicit(self) -> None:
        self.assertIn('id="production-v2-new-recipe-branch"', self.page)
        self.assertIn('id="production-v2-reference-mode"', self.page)
        self.assertIn('value="none"', self.page)
        self.assertIn('value="recipe_and_guidance"', self.page)
        self.assertIn("elements.guidanceCandidate.value = \"\"", self.script)
        self.assertIn("reference_mode: elements.referenceMode.value", self.script)

    def test_llm_calls_have_live_status_and_durable_collapsible_traces(self) -> None:
        self.assertIn('id="production-v2-llm-traces"', self.page)
        self.assertIn("active_llm_trace_id", self.script)
        self.assertIn("function renderLlmTraces()", self.script)
        self.assertIn("Thinking du modèle", self.script)
        self.assertIn("Output brut", self.script)
        self.assertIn('startsWith("video_")', self.script)
        self.assertIn("production-v2-llm-trace", self.styles)

    def test_candidate_feedback_survives_background_polling(self) -> None:
        self.assertIn("candidateRenderSignature", self.script)
        self.assertIn("feedbackDrafts: new Map()", self.script)
        self.assertIn('textarea[data-candidate-feedback]', self.script)
        self.assertIn("restored.focus({ preventScroll: true })", self.script)
        self.assertIn("production-v2-lab.js?v=20260903.3", self.page)

    def test_candidate_preview_height_follows_its_render_ratio(self) -> None:
        self.assertIn("cssAspectRatio(candidate.settings.aspect_ratio)", self.script)
        self.assertIn('--production-v2-image-ratio", previewRatio', self.script)
        self.assertIn("aspect-ratio: var(--production-v2-image-ratio, auto)", self.styles)
        self.assertIn(".production-v2-parent-context .production-v2-image-button { height: 150px; min-height: 0; aspect-ratio: auto; }", self.styles)
        self.assertIn("/static/lab.css?v=20260903.3", self.page)


if __name__ == "__main__":
    unittest.main()
