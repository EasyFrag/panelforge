(() => {
  "use strict";

  function create({ prefix, state, core, render, setComposition }) {
    const byId = suffix => document.getElementById(`${prefix}-${suffix}`);
    const elements = {
      panel: byId("chinese-panel"), language: byId("prompt-language"),
      model: byId("chinese-model"), generate: byId("generate-chinese"),
      copy: byId("copy-chinese"), status: byId("chinese-status"),
      content: byId("chinese-content"),
    };
    let running = false;
    let modelIds = new Set();
    let modelChosenByUser = false;
    let sourceRevisionId = null;

    function activePrompt() {
      return state.composition?.documents?.final_prompt || null;
    }

    function variant() {
      const revisionId = activePrompt()?.active_revision_id;
      if (!revisionId) return null;
      return [...(state.composition?.prompt_variants || [])].reverse().find(
        item => item.language === "zh" && item.source_revision_id === revisionId,
      ) || null;
    }

    function populate(models) {
      const selected = elements.model.value
        || state.composition?.writer_model_id
        || "local::unsloth/gemma-4-31B-it-qat-GGUF";
      modelIds = new Set(models.map(item => item.id));
      window.PanelForgeModelPicker.populate(elements.model, models, selected);
      if (!elements.model.value && models[0]) elements.model.value = models[0].id;
    }

    function selection() {
      const current = variant();
      const language = elements.language.value === "zh" && current ? "zh" : "en";
      const revisionId = activePrompt()?.active_revision_id || null;
      return {
        language,
        variantId: language === "zh" ? current.variant_id : null,
        renderRevisionId: language === "zh"
          ? `zh:${revisionId}:${current.variant_id}` : revisionId,
      };
    }

    function draw({ locked, ready }) {
      const prompt = activePrompt();
      const current = variant();
      const nextRevisionId = prompt?.active_revision_id || null;
      if (nextRevisionId !== sourceRevisionId) {
        sourceRevisionId = nextRevisionId;
        elements.language.value = "en";
        elements.status.className = "message";
        elements.status.textContent = "";
        if (!modelChosenByUser) {
          const writerModel = state.composition?.writer_model_id;
          if (writerModel && modelIds.has(writerModel)) elements.model.value = writerModel;
        }
      }
      elements.panel.hidden = !prompt?.active_revision_id;
      const option = elements.language.querySelector('option[value="zh"]');
      option.disabled = !current;
      if (!current && elements.language.value === "zh") elements.language.value = "en";
      elements.generate.disabled = locked || running || !ready || !elements.model.value;
      elements.model.disabled = locked || running || !ready;
      window.PanelForgeModelPicker.setDisabled(elements.model, elements.model.disabled);
      elements.language.disabled = locked || running || !ready;
      elements.copy.disabled = !current || running;
      elements.content.hidden = !current;
      if (current && !running) elements.content.value = current.content;
      elements.generate.textContent = current ? "Régénérer la variante chinoise" : "Générer la variante chinoise";
      if (current && !running && !elements.status.textContent) {
        elements.status.textContent = `Variante prête · ${current.model_id}`;
      }
    }

    async function generate() {
      const sessionId = state.session?.id;
      if (!sessionId || running || !elements.model.value) return;
      running = true;
      elements.status.className = "message";
      elements.status.textContent = "Transcompilation chinoise en cours…";
      elements.content.hidden = false;
      elements.content.value = "";
      render();
      let completed = false;
      try {
        await core.streamRequest(
          `/api/prompt-lab/sessions/${encodeURIComponent(sessionId)}/composition/final-prompt/variants/zh/stream`,
          {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model_id: elements.model.value }),
          },
          event => {
            if (event.kind === "delta" && event.text) elements.content.value += event.text;
            if (event.composition) setComposition(event.composition);
            if (event.kind === "completed") {
              completed = true;
              elements.content.value = event.text || variant()?.content || "";
            }
            if (event.kind === "truncated") throw new Error(core.truncationMessage(event));
          },
          { completionTone: true },
        );
        if (!completed) throw new Error("La transcompilation chinoise ne s’est pas terminée.");
        elements.language.value = "zh";
        elements.status.className = "message success";
        elements.status.textContent = "Variante chinoise prête et sélectionnée pour le rendu.";
      } catch (error) {
        elements.status.className = "message error";
        elements.status.textContent = error.message;
        core.playFailureTone();
      } finally {
        running = false;
        render();
      }
    }

    elements.generate.addEventListener("click", generate);
    elements.language.addEventListener("change", render);
    elements.model.addEventListener("change", () => { modelChosenByUser = true; });
    elements.copy.addEventListener("click", async () => {
      const current = variant();
      if (!current) return;
      try {
        await navigator.clipboard.writeText(current.content);
        elements.copy.textContent = "Copié";
      } catch (_) {
        elements.copy.textContent = "Échec de copie";
      }
      setTimeout(() => { elements.copy.textContent = "Copier 中文"; }, 1200);
    });

    return Object.freeze({ populate, draw, selection, busy: () => running });
  }

  window.PanelForgeChinesePromptVariant = Object.freeze({ create });
})();
