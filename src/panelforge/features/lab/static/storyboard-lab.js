(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const fallbackLayouts = Object.freeze({
    2: Object.freeze({ panel_count: 2, columns: 2, rows: 1, page_aspect_ratio: "4:3", page_orientation: "landscape" }),
    4: Object.freeze({ panel_count: 4, columns: 2, rows: 2, page_aspect_ratio: "2:3", page_orientation: "portrait" }),
    6: Object.freeze({ panel_count: 6, columns: 3, rows: 2, page_aspect_ratio: "1:1", page_orientation: "square" }),
    9: Object.freeze({ panel_count: 9, columns: 3, rows: 3, page_aspect_ratio: "2:3", page_orientation: "portrait" }),
  });

  const elements = {
    workspace: $("storyboard-lab-workspace"),
    form: $("storyboard-lab-form"),
    source: $("storyboard-lab-source"),
    panelOptions: $("storyboard-lab-panel-options"),
    model: $("storyboard-lab-model"),
    recipe: $("storyboard-lab-recipe"),
    showReasoning: $("storyboard-lab-show-reasoning"),
    generate: $("storyboard-lab-generate"),
    formMessage: $("storyboard-lab-form-message"),
    refresh: $("storyboard-lab-refresh"),
    historyEmpty: $("storyboard-lab-history-empty"),
    historyList: $("storyboard-lab-history-list"),
    resultTitle: $("storyboard-lab-result-title"),
    status: $("storyboard-lab-status"),
    resultEmpty: $("storyboard-lab-result-empty"),
    resultEditor: $("storyboard-lab-result-editor"),
    metadata: $("storyboard-lab-metadata"),
    copy: $("storyboard-lab-copy"),
    sendToImageLab: $("storyboard-lab-send-to-image-lab"),
    relaunch: $("storyboard-lab-relaunch"),
    prompt: $("storyboard-lab-prompt"),
    runMessage: $("storyboard-lab-run-message"),
    warningPanel: $("storyboard-lab-warning-panel"),
    warnings: $("storyboard-lab-warnings"),
    variables: $("storyboard-lab-variables"),
    variablesContent: $("storyboard-lab-variables-content"),
    reasoningPanel: $("storyboard-lab-reasoning-panel"),
    reasoningLabel: $("storyboard-lab-reasoning-label"),
    reasoningOutput: $("storyboard-lab-reasoning-output"),
    reasoningEmpty: $("storyboard-lab-reasoning-empty"),
    stream: {
      container: $("storyboard-lab-stream-state"),
      label: $("storyboard-lab-stream-label"),
      percent: $("storyboard-lab-stream-percent"),
      progress: $("storyboard-lab-stream-progress"),
    },
  };
  if (!elements.workspace) return;

  const state = {
    initialized: false,
    spec: null,
    layouts: { ...fallbackLayouts },
    runs: [],
    activeRun: null,
    busy: false,
    openToken: 0,
  };
  const core = window.PanelForgePromptLab;
  const reasoningTrace = core && typeof core.createReasoningTrace === "function"
    ? core.createReasoningTrace({
      toggle: elements.showReasoning,
      panel: elements.reasoningPanel,
      label: elements.reasoningLabel,
      output: elements.reasoningOutput,
      empty: elements.reasoningEmpty,
    })
    : Object.freeze({
      begin: () => {}, handle: () => {}, finish: () => {}, reset: () => {},
      streamUrl: (url) => url,
    });

  function request(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      let payload = null;
      try { payload = await response.json(); } catch (_) { /* empty response */ }
      if (!response.ok) {
        const detail = payload && payload.detail;
        throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
      }
      return payload;
    });
  }

  function unwrapRun(payload) {
    return payload && payload.run ? payload.run : payload;
  }

  function runId(run) {
    return run && (run.run_id || run.id);
  }

  function runSource(run) {
    return String((run && (run.source_text || run.intention || run.story_text)) || "");
  }

  function runPrompt(run) {
    return String((run && (run.compiled_prompt || run.final_prompt || run.prompt || run.raw_response)) || "");
  }

  function hasCompiledPrompt(run) {
    return Boolean(run && (run.compiled_prompt || run.final_prompt || run.prompt));
  }

  function runVariables(run) {
    return run && (run.storyboard_spec || run.spec || run.variables || run.structured_output);
  }

  function normalizeModel(model) {
    if (typeof model === "string") return { id: model };
    return { ...(model || {}), id: model && (model.id || model.model_id || model.name) };
  }

  function selectedPanelCount() {
    const selected = elements.panelOptions.querySelector('input[name="storyboard-panel-count"]:checked');
    return Number(selected && selected.value) || 6;
  }

  function selectPanelCount(panelCount) {
    const input = elements.panelOptions.querySelector(`input[value="${Number(panelCount)}"]`);
    if (input) input.checked = true;
  }

  function normalizeLayout(value, panelCount) {
    const fallback = fallbackLayouts[panelCount] || fallbackLayouts[6];
    const columns = Number(value && (value.columns || value.column_count)) || fallback.columns;
    const rows = Number(value && (value.rows || value.row_count)) || fallback.rows;
    const gridLabel = `${columns} ${columns > 1 ? "colonnes" : "colonne"} × ${rows} ${rows > 1 ? "lignes" : "ligne"}`;
    return {
      panel_count: Number(value && value.panel_count) || panelCount,
      columns,
      rows,
      page_aspect_ratio: String((value && (value.page_aspect_ratio || value.aspect_ratio)) || fallback.page_aspect_ratio),
      page_orientation: String((value && value.page_orientation) || fallback.page_orientation),
      grid_label: gridLabel,
    };
  }

  function layoutFor(panelCount, run = null) {
    const embedded = run && (run.layout || run.geometry || run.storyboard_layout);
    return normalizeLayout(embedded || state.layouts[panelCount], panelCount);
  }

  function setFormMessage(message, failed = true) {
    elements.formMessage.textContent = message || "";
    elements.formMessage.classList.toggle("storyboard-info", !failed);
    elements.formMessage.hidden = !message;
  }

  function setRunMessage(message, failed = false) {
    elements.runMessage.textContent = message || "";
    elements.runMessage.className = failed ? "message error-text" : "message";
  }

  function setBusy(value) {
    state.busy = value;
    elements.source.disabled = value;
    elements.model.disabled = value;
    window.PanelForgeModelPicker.setDisabled(elements.model, value);
    elements.showReasoning.disabled = value;
    elements.panelOptions.querySelectorAll("input").forEach((input) => { input.disabled = value; });
    renderControls();
    renderHistory();
  }

  function renderControls() {
    elements.generate.disabled = state.busy
      || !elements.source.value.trim()
      || !elements.model.value;
    elements.copy.disabled = !runPrompt(state.activeRun);
    elements.sendToImageLab.disabled = state.busy
      || !hasCompiledPrompt(state.activeRun)
      || !elements.prompt.value.trim();
    elements.relaunch.disabled = state.busy || !state.activeRun;
    elements.refresh.disabled = state.busy;
  }

  function statusLabel(status) {
    return ({
      created: "Créé",
      generating: "Génération…",
      succeeded: "Terminé",
      completed: "Terminé",
      truncated: "Écourté",
      failed: "Échec",
      cancelled: "Annulé",
      canceled: "Annulé",
    })[status] || "Prêt";
  }

  function renderStatus(run) {
    const status = String((run && run.status) || "").toLowerCase();
    elements.status.textContent = `● ${statusLabel(status)}`;
    elements.status.className = "run-status";
    if (["created", "generating", "truncated"].includes(status)) elements.status.classList.add("active");
    if (["succeeded", "completed"].includes(status)) elements.status.classList.add("success");
    if (["failed", "cancelled", "canceled"].includes(status)) elements.status.classList.add("failed");
  }

  function appendMetadata(label) {
    const chip = document.createElement("span");
    chip.textContent = label;
    elements.metadata.append(chip);
  }

  function normalizeWarnings(run) {
    const values = run && run.warnings;
    if (!Array.isArray(values)) return [];
    return values.map((warning) => {
      if (typeof warning === "string") return warning;
      return String((warning && (warning.message || warning.detail || warning.code)) || "Avertissement non détaillé");
    });
  }

  function renderRun(run, { keepStream = false } = {}) {
    state.activeRun = run || null;
    const hasRun = Boolean(run);
    elements.resultEmpty.hidden = hasRun;
    elements.resultEditor.hidden = !hasRun;
    renderStatus(run);
    if (!hasRun) {
      elements.resultTitle.textContent = "Storyboard KREA2";
      renderControls();
      return;
    }

    const panelCount = Number(run.panel_count) || selectedPanelCount();
    const layout = layoutFor(panelCount, run);
    elements.resultTitle.textContent = `Storyboard · ${panelCount} panels`;
    elements.metadata.replaceChildren();
    appendMetadata(`${layout.grid_label}`);
    appendMetadata(`Planche ${layout.page_aspect_ratio}`);
    appendMetadata(run.model_id || elements.model.value || "Modèle inconnu");
    if (run.recipe_version) appendMetadata(`Recette ${run.recipe_version}`);
    const diagnosticDraft = !hasCompiledPrompt(run) && Boolean(run.raw_response);
    if (diagnosticDraft) appendMetadata("Brouillon diagnostic");

    elements.prompt.value = runPrompt(run);
    const warnings = normalizeWarnings(run);
    elements.warnings.replaceChildren();
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      elements.warnings.append(item);
    });
    elements.warningPanel.hidden = warnings.length === 0;

    const variables = runVariables(run);
    elements.variables.hidden = !variables;
    elements.variablesContent.textContent = variables ? JSON.stringify(variables, null, 2) : "";
    if (!keepStream) elements.stream.container.hidden = true;
    const error = run.error || run.error_message;
    const diagnosticMessage = diagnosticDraft
      ? "La compilation n’a pas abouti : la réponse brute du modèle reste disponible comme brouillon diagnostic."
      : "";
    setRunMessage(error || diagnosticMessage, Boolean(error));
    renderControls();
  }

  function recipeLabel(recipe) {
    if (!recipe) return "KREA2 Storyboard photo · v1";
    const name = recipe.display_name || recipe.label || recipe.name || "KREA2 Storyboard photo";
    const version = recipe.version || recipe.recipe_version;
    return version ? `${name} · ${version}` : name;
  }

  function applySpec(spec) {
    state.spec = spec || {};
    const options = state.spec.panel_options || state.spec.layouts || [];
    options.forEach((value) => {
      const count = Number(value.panel_count || value.count);
      if (fallbackLayouts[count]) state.layouts[count] = normalizeLayout(value, count);
    });
    Object.values(state.layouts).forEach((layout) => {
      const input = elements.panelOptions.querySelector(`input[value="${layout.panel_count}"]`);
      const description = input && input.parentElement.querySelector("small");
      if (description) description.textContent = `${layout.grid_label} · ${layout.page_aspect_ratio}`;
    });

    const models = (state.spec.models || state.spec.available_models || [])
      .map(normalizeModel)
      .filter((model) => model.id);
    const current = elements.model.value;
    if (window.PanelForgeModelPicker) {
      window.PanelForgeModelPicker.populate(elements.model, models, current);
    } else {
      elements.model.replaceChildren();
      models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.id;
        elements.model.append(option);
      });
    }
    if (!models.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Aucun modèle disponible";
      elements.model.replaceChildren(option);
    }
    elements.recipe.value = recipeLabel(state.spec.recipe);
    renderControls();
  }

  async function loadSpec() {
    const spec = await request("/api/storyboard-lab/spec");
    applySpec(spec);
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
  }

  function historyTitle(run) {
    const source = runSource(run).replace(/\s+/g, " ").trim();
    return source || `Storyboard ${runId(run) || "sans identifiant"}`;
  }

  function renderHistory() {
    elements.historyList.replaceChildren();
    elements.historyEmpty.hidden = state.runs.length > 0;
    state.runs.forEach((run) => {
      const item = document.createElement("li");
      item.className = "storyboard-history-item";
      const copy = document.createElement("div");
      copy.className = "storyboard-history-copy";
      const title = document.createElement("b");
      title.textContent = historyTitle(run);
      const detail = document.createElement("small");
      const detailParts = [
        `${Number(run.panel_count) || "?"} panels`,
        statusLabel(String(run.status || "").toLowerCase()),
      ];
      const dateLabel = formatDate(run.updated_at || run.created_at);
      if (dateLabel) detailParts.push(dateLabel);
      detail.textContent = detailParts.join(" · ");
      copy.append(title, detail);

      const actions = document.createElement("div");
      actions.className = "storyboard-history-actions";
      const open = document.createElement("button");
      open.type = "button";
      open.textContent = "Ouvrir";
      open.disabled = state.busy || !runId(run);
      open.addEventListener("click", () => openRun(runId(run)));
      const relaunch = document.createElement("button");
      relaunch.type = "button";
      relaunch.textContent = "Relancer";
      relaunch.disabled = state.busy;
      relaunch.addEventListener("click", () => relaunchRun(run));
      actions.append(open, relaunch);
      item.append(copy, actions);
      elements.historyList.append(item);
    });
  }

  async function loadRuns() {
    const payload = await request("/api/storyboard-lab/runs?limit=30");
    const values = Array.isArray(payload) ? payload : (payload && (payload.runs || payload.items)) || [];
    state.runs = values.map(unwrapRun).filter(Boolean);
    renderHistory();
  }

  function ensureModel(modelId) {
    if (!modelId) return;
    window.PanelForgeModelPicker.select(elements.model, modelId, "modèle du run");
  }

  function applyRunToForm(run) {
    elements.source.value = runSource(run);
    selectPanelCount(run.panel_count);
    ensureModel(run.model_id);
    renderControls();
  }

  async function openRun(id) {
    if (!id || state.busy) return;
    const token = ++state.openToken;
    reasoningTrace.reset();
    setFormMessage("");
    try {
      const payload = await request(`/api/storyboard-lab/runs/${encodeURIComponent(id)}`);
      if (token !== state.openToken) return;
      const run = unwrapRun(payload);
      applyRunToForm(run);
      renderRun(run);
      elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      if (token === state.openToken) setFormMessage(error.message);
    }
  }

  function streamApi() {
    const api = window.PanelForgePromptLab;
    if (!api || typeof api.streamRequest !== "function") {
      throw new Error("Le lecteur de flux SSE PanelForge est indisponible.");
    }
    return api;
  }

  function beginStream() {
    elements.stream.container.hidden = false;
    elements.stream.container.className = "stream-state";
    elements.stream.label.textContent = "Préparation…";
    elements.stream.percent.textContent = "";
    elements.stream.progress.removeAttribute("value");
  }

  async function refreshActiveRun(id) {
    const payload = await request(`/api/storyboard-lab/runs/${encodeURIComponent(id)}`);
    const run = unwrapRun(payload);
    renderRun(run, { keepStream: true });
    return run;
  }

  async function createAndGenerate() {
    if (state.busy) return;
    const sourceText = elements.source.value.trim();
    const modelId = elements.model.value;
    const panelCount = selectedPanelCount();
    if (!sourceText || !modelId) {
      renderControls();
      return;
    }

    state.openToken += 1;
    setBusy(true);
    setFormMessage("");
    setRunMessage("");
    let id = null;
    try {
      const payload = await request("/api/storyboard-lab/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_text: sourceText, panel_count: panelCount, model_id: modelId }),
      });
      const created = unwrapRun(payload);
      id = runId(created);
      if (!id) throw new Error("Le backend n’a pas retourné l’identifiant du storyboard.");
      renderRun(created, { keepStream: true });
      beginStream();
      reasoningTrace.begin("Storyboard");

      const api = streamApi();
      try {
        await api.streamRequest(
          reasoningTrace.streamUrl(`/api/storyboard-lab/runs/${encodeURIComponent(id)}/generate/stream`),
          { method: "POST", headers: { Accept: "text/event-stream" } },
          (event) => {
            api.updateStreamState(elements.stream, event);
            reasoningTrace.handle(event);
            const streamedRun = unwrapRun(event.run || event.storyboard_run);
            if (streamedRun && runId(streamedRun)) {
              state.activeRun = streamedRun;
              renderStatus(streamedRun);
              if (String(streamedRun.status || "").toLowerCase() === "failed") {
                throw new Error(streamedRun.error || "La compilation du storyboard a échoué.");
              }
            }
          },
        );
      } finally {
        reasoningTrace.finish();
      }
      const completed = await refreshActiveRun(id);
      if (["succeeded", "completed"].includes(String(completed.status || "").toLowerCase())
          && hasCompiledPrompt(completed)) {
        setRunMessage("Prompt compilé. Vous pouvez encore l’éditer avant de le copier.");
      }
    } catch (error) {
      try {
        if (id) await refreshActiveRun(id);
      } catch (_) { /* keep the actionable stream error */ }
      const api = window.PanelForgePromptLab;
      if (api && typeof api.failStreamState === "function") api.failStreamState(elements.stream, error.message);
      setRunMessage(error.message, true);
    } finally {
      setBusy(false);
      try { await loadRuns(); } catch (_) { /* result remains usable */ }
    }
  }

  async function relaunchRun(run) {
    if (!run || state.busy) return;
    applyRunToForm(run);
    await createAndGenerate();
  }

  async function copyPrompt() {
    const content = elements.prompt.value;
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
    } catch (_) {
      elements.prompt.focus();
      elements.prompt.select();
      document.execCommand("copy");
    }
    setRunMessage("Prompt copié dans le presse-papiers.");
  }

  async function sendToImageLab() {
    const prompt = elements.prompt.value.trim();
    if (!prompt || !hasCompiledPrompt(state.activeRun)) return;
    const bridge = window.PanelForgeKrea2ImageLab;
    if (!bridge || typeof bridge.prefill !== "function") {
      setRunMessage("Le module Image Lab KREA2 est indisponible.", true);
      return;
    }
    elements.sendToImageLab.disabled = true;
    try {
      await bridge.prefill({
        prompt,
        panel_count: Number(state.activeRun.panel_count) || selectedPanelCount(),
        source_storyboard_run_id: runId(state.activeRun),
      });
    } catch (error) {
      setRunMessage(error.message, true);
    } finally { renderControls(); }
  }

  async function initialize() {
    if (state.initialized) return;
    state.initialized = true;
    const results = await Promise.allSettled([loadSpec(), loadRuns()]);
    const failure = results.find((result) => result.status === "rejected");
    if (failure) {
      if (results[0].status === "rejected") state.initialized = false;
      setFormMessage(`Storyboard Lab indisponible : ${failure.reason.message}`);
    }
    renderControls();
  }

  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    createAndGenerate();
  });
  elements.source.addEventListener("input", renderControls);
  elements.model.addEventListener("change", renderControls);
  elements.panelOptions.addEventListener("change", renderControls);
  elements.refresh.addEventListener("click", async () => {
    setFormMessage("");
    try { await loadRuns(); } catch (error) { setFormMessage(error.message); }
  });
  elements.copy.addEventListener("click", copyPrompt);
  elements.sendToImageLab.addEventListener("click", sendToImageLab);
  elements.prompt.addEventListener("input", renderControls);
  elements.relaunch.addEventListener("click", () => relaunchRun(state.activeRun));
  const navButton = document.querySelector('[data-lab-view="storyboard-lab"]');
  if (navButton) navButton.addEventListener("click", initialize);

  window.PanelForgeStoryboardLab = Object.freeze({
    open: () => {
      if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView("storyboard-lab");
      return initialize();
    },
  });
  renderRun(null);
})();
