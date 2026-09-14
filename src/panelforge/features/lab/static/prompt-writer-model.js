(() => {
  "use strict";

  // Capability is supplied by the backend's exact cookbook allowlist.
  function create({ prefix, state, planner, cookbook, request, render, busy }) {
    const host = document.getElementById(`${prefix}-writer-model-controls`);
    const enabled = host.querySelector('[data-writer="enabled"]');
    const fields = host.querySelector('[data-writer="fields"]');
    const model = host.querySelector("select");
    const summary = host.querySelector('[data-writer="summary"]');
    const status = host.querySelector('[data-writer="status"]');
    const picker = window.PanelForgeModelPicker;
    const recipesButton = document.createElement("button"); recipesButton.type = "button";
    recipesButton.textContent = "Consignes LLM"; recipesButton.className = "prompt-recipes-open";
    host.before(recipesButton);
    recipesButton.addEventListener("click", () => {
      const reference = state.composition?.cookbook || cookbook();
      window.PanelForgePromptRecipes?.open({key: reference?.id, version: reference?.version, sessionId: state.session?.id});
    });
    let selected = null;
    let saving = null;

    function supported() {
      return Boolean(state.composition
        ? state.composition.supports_writer_model : cookbook()?.supports_writer_model);
    }

    function restore(modelId) {
      selected = modelId || null;
      enabled.checked = Boolean(selected);
      status.textContent = "";
      if (selected) picker.select(model, selected, "modèle enregistré, absent du catalogue");
    }

    function value() {
      if (!supported() || !enabled.checked) return null;
      if (!selected) throw new Error("Choisissez le modèle du prompt final.");
      return selected;
    }

    function populate(models) {
      picker.populate(model, models, selected || planner.value);
      // Never silently replace a saved model when a refreshed catalogue omits it.
      if (selected) picker.select(model, selected, "modèle enregistré, absent du catalogue");
      draw();
    }

    function draw() {
      host.hidden = !supported();
      recipesButton.hidden = !supported();
      fields.hidden = !enabled.checked;
      enabled.disabled = host.hidden || busy();
      model.disabled = host.hidden || !enabled.checked || busy();
      model.required = !host.hidden && enabled.checked;
      picker.setDisabled(model, model.disabled);
      model.title = model.selectedOptions[0]?.textContent || "";
      const planName = planner.selectedOptions[0]?.textContent || "À choisir";
      const writerName = enabled.checked ? model.title || "À choisir" : planName;
      const shortName = (name) => {
        const basename = name.split("·").pop().trim().split("/").pop();
        return basename.length > 42 ? `${basename.slice(0, 39)}…` : basename;
      };
      summary.title = `Plan : ${planName} → Prompt : ${writerName}`;
      summary.textContent = enabled.checked
        ? `Plan : ${shortName(planName)} → Prompt : ${shortName(writerName)}`
        : "Plan et prompt final : même modèle.";
    }

    async function save() {
      if (saving) return saving;
      if (!state.composition || !supported()) return;
      const writerModelId = value();
      const expected = state.composition.writer_model_id ?? null;
      if (writerModelId === expected) return;
      const sessionId = state.session.id;
      state.writerSaving = true;
      status.textContent = "Enregistrement…";
      render();
      saving = (async () => {
        try {
          const response = await request(`/api/prompt-lab/sessions/${sessionId}/composition/writer-model`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ writer_model_id: writerModelId, expected_writer_model_id: expected }),
          });
          if (state.session?.id !== sessionId) return;
          state.composition = response.composition;
          status.textContent = "Enregistré pour la prochaine rédaction. Le plan validé est conservé.";
        } catch (error) {
          if (state.session?.id === sessionId) {
            restore(expected);
            status.textContent = `Choix non enregistré : ${error.message}`;
          }
          throw error;
        } finally {
          state.writerSaving = false;
          saving = null;
          render();
        }
      })();
      return saving;
    }

    enabled.addEventListener("change", () => {
      if (enabled.checked && !selected) {
        selected = planner.value || model.value || null;
        if (selected) picker.select(model, selected);
      }
      render();
      save().catch((error) => { if (!status.textContent) status.textContent = error.message; });
    });
    model.addEventListener("change", () => {
      selected = model.value || null;
      render();
      save().catch((error) => { status.textContent = error.message; });
    });
    return { restore, populate, draw, value, save };
  }

  window.PanelForgePromptWriterModel = Object.freeze({ create });
})();
