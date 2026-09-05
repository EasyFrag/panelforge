(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const activeAttemptStatuses = new Set(["queued", "running", "cancel_pending"]);
  const {
    modelGroups,
    appendGroupedOptions,
    renderModelPicker,
    syncModelPicker,
    renderCatalogManager,
    renderLoraStack: renderLoraPickerStack,
  } = window.PanelForgeKrea2ResourceUi;
  const elements = {
    workspace: $("krea2-edit-lab-workspace"),
    uploadForm: $("krea2-edit-upload-form"),
    uploadImage: $("krea2-edit-upload-image"),
    uploadSidecar: $("krea2-edit-upload-sidecar"),
    upload: $("krea2-edit-upload"),
    uploadMessage: $("krea2-edit-upload-message"),
    refresh: $("krea2-edit-refresh"),
    backlog: $("krea2-edit-backlog"),
    backlogEmpty: $("krea2-edit-backlog-empty"),
    editor: $("krea2-edit-editor"),
    title: $("krea2-edit-title"),
    status: $("krea2-edit-status"),
    timeline: $("krea2-edit-timeline"),
    imageToolbar: $("krea2-edit-image-toolbar"),
    images: $("krea2-edit-images"),
    showOriginal: $("krea2-edit-show-original"),
    originalFigure: $("krea2-edit-original-figure"),
    originalImage: $("krea2-edit-original-image"),
    sourceImage: $("krea2-edit-source-image"),
    resultImage: $("krea2-edit-result-image"),
    resultCaption: $("krea2-edit-result-caption"),
    resultEmpty: $("krea2-edit-result-empty"),
    resultLoading: $("krea2-edit-result-loading"),
    lightbox: $("krea2-edit-lightbox"),
    lightboxTitle: $("krea2-edit-lightbox-title"),
    lightboxImage: $("krea2-edit-lightbox-image"),
    lightboxClose: $("krea2-edit-lightbox-close"),
    metadata: $("krea2-edit-metadata"),
    warnings: $("krea2-edit-warnings"),
    projectName: $("krea2-edit-project-name"),
    stepName: $("krea2-edit-step-name"),
    exportInfo: $("krea2-edit-export-info"),
    exportState: $("krea2-edit-export-info").closest(".krea2-edit-export-state"),
    retryExport: $("krea2-edit-retry-export"),
    instruction: $("krea2-edit-instruction"),
    llm: $("krea2-edit-llm"),
    promptLanguage: $("krea2-edit-prompt-language"),
    showReasoning: $("krea2-edit-show-reasoning"),
    buildPrompt: $("krea2-edit-build-prompt"),
    reasoning: $("krea2-edit-reasoning"),
    reasoningLabel: $("krea2-edit-reasoning-label"),
    reasoningEmpty: $("krea2-edit-reasoning-empty"),
    reasoningContent: $("krea2-edit-reasoning-content"),
    prompt: $("krea2-edit-prompt"),
    revisionCount: $("krea2-edit-revision-count"),
    revisionsEmpty: $("krea2-edit-revisions-empty"),
    revisions: $("krea2-edit-revisions"),
    model: $("krea2-edit-model"),
    ratio: $("krea2-edit-ratio"),
    megapixels: $("krea2-edit-megapixels"),
    refBoost: $("krea2-edit-ref-boost"),
    steps: $("krea2-edit-steps"),
    seed: $("krea2-edit-seed"),
    loras: $("krea2-edit-loras"),
    catalogManager: $("krea2-edit-catalog-manager"),
    fixedNote: $("krea2-edit-fixed-note"),
    message: $("krea2-edit-message"),
    render: $("krea2-edit-render"),
    cancel: $("krea2-edit-cancel"),
    processed: $("krea2-edit-processed"),
    hide: $("krea2-edit-hide"),
    attempts: $("krea2-edit-attempts"),
    attemptsEmpty: $("krea2-edit-attempts-empty"),
  };
  if (!elements.workspace) return;

  const state = {
    initialized: false,
    initializing: null,
    busy: false,
    spec: null,
    sources: [],
    source: null,
    feedbackAttemptId: null,
    loraSlots: [],
    pollTimer: null,
  };
  const core = window.PanelForgeLabCore;
  const showOriginalPreferenceKey = "panelforge.krea2Edit.showOriginal";
  try {
    elements.showOriginal.checked = localStorage.getItem(showOriginalPreferenceKey) === "true";
  } catch (_) { /* storage can be unavailable in private contexts */ }
  const reasoningTrace = core && core.createReasoningTrace
    ? core.createReasoningTrace({
      toggle: elements.showReasoning,
      panel: elements.reasoning,
      label: elements.reasoningLabel,
      output: elements.reasoningContent,
      empty: elements.reasoningEmpty,
    })
    : Object.freeze({ begin: () => {}, handle: () => {}, finish: () => {}, streamUrl: (url) => url });

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty */ }
    if (!response.ok) throw new Error(payload && payload.detail || `Erreur HTTP ${response.status}`);
    return payload;
  }

  function sourceOf(payload) { return payload && payload.source ? payload.source : payload; }

  function validationLabel(value, fallback) {
    const normalized = String(value || "")
      .replace(/[\u0000-\u001f\u007f]+/g, " ")
      .replace(/\s+/g, " ")
      .trim() || fallback;
    const characters = Array.from(normalized);
    if (characters.length <= 120) return normalized;
    return `${characters.slice(0, 119).join("").trimEnd()}…`;
  }

  function defaultProjectName(filename) {
    const basename = String(filename || "Projet KREA2").replaceAll("\\", "/").split("/").at(-1);
    const stem = basename.includes(".") ? basename.slice(0, basename.lastIndexOf(".")) : basename;
    return validationLabel(stem, "Projet KREA2");
  }

  function defaultStepName(source) {
    return validationLabel(
      source.accepted_label || source.instruction,
      `Modification ${source.stage_index}`,
    );
  }

  function openImageViewer(image, label) {
    const url = image?.currentSrc || image?.src;
    if (!url || image.hidden) return;
    elements.lightboxTitle.textContent = label || image.alt || "Image en taille réelle";
    elements.lightboxImage.src = url;
    elements.lightboxImage.alt = image.alt || label || "Image en taille réelle";
    if (typeof elements.lightbox.showModal === "function") {
      if (!elements.lightbox.open) elements.lightbox.showModal();
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }

  function makeZoomable(image, labelOf) {
    image.classList.add("krea2-edit-zoomable");
    image.tabIndex = 0;
    image.setAttribute("role", "button");
    image.setAttribute("aria-label", "Afficher l’image en taille réelle");
    const open = () => openImageViewer(image, typeof labelOf === "function" ? labelOf() : labelOf);
    image.addEventListener("click", open);
    image.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      open();
    });
  }

  function randomSeed() {
    const values = new BigUint64Array(1);
    crypto.getRandomValues(values);
    return values[0].toString();
  }

  function options(select, values, valueOf, labelOf) {
    select.replaceChildren();
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = valueOf(value);
      option.textContent = labelOf(value);
      select.append(option);
    });
  }

  function ensureOption(select, value, missingLabel) {
    [...select.options]
      .filter((option) => option.dataset.missing === "true" && option.value !== value)
      .forEach((option) => option.remove());
    if (!value || [...select.options].some((option) => option.value === value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${missingLabel} · indisponible`;
    option.dataset.missing = "true";
    select.prepend(option);
  }

  function applyRenderSettings(settings) {
    const model = settings.model_id || "";
    ensureOption(elements.model, model, model);
    elements.model.value = model;
    syncModelPicker(elements.model);
    elements.ratio.value = settings.aspect_ratio || "";
    elements.megapixels.value = String(settings.megapixels ?? "");
    elements.refBoost.value = String(settings.ref_boost ?? "");
    elements.steps.value = String(settings.steps ?? "");
    elements.seed.value = String(settings.seed ?? randomSeed());
    const loras = Array.isArray(settings.loras) ? settings.loras : [];
    state.loraSlots = loras.slice(0, 10).filter((value) => value && value.name).map((value) => ({
      name: value.name,
      strength: value.strength,
    }));
    renderLoras();
  }

  function applyDefaultRenderSettings() {
    const defaults = state.spec?.defaults || {};
    applyRenderSettings({ ...defaults, seed: randomSeed(), loras: [] });
  }

  function renderSettingsComplete() {
    return Boolean(
      elements.model.value
      && elements.ratio.value
      && elements.megapixels.value
      && elements.refBoost.value
      && elements.steps.value
      && elements.seed.value,
    );
  }

  async function initialize() {
    if (state.initializing) return state.initializing;
    state.initializing = (async () => {
      setMessage("Chargement…");
      try {
        if (!state.initialized) {
          state.spec = await request("/api/image-lab/krea2-edit/spec");
          window.PanelForgeModelPicker.populate(
            elements.llm,
            state.spec.llm_models || [],
            elements.llm.value,
          );
          renderModelPicker(elements.model, {
            resources: state.spec.render_models || [],
            updatePreference: updateResourcePreference,
            refreshResource,
          });
          options(elements.ratio, state.spec.aspect_ratios || [], (value) => value, (value) => value);
          applyDefaultRenderSettings();
          elements.fixedNote.textContent = `Fixe : ${state.spec.fixed.identity_lora} × ${state.spec.fixed.identity_lora_strength} · Euler / Simple · CFG ${state.spec.fixed.cfg}.`;
          renderResourceManager();
        }
        await loadSources();
        if (!renderSettingsComplete()) {
          if (state.source) openSource(state.source, { hydrate: true, force: true });
          else applyDefaultRenderSettings();
        }
        state.initialized = true;
        setMessage("");
      } catch (error) {
        state.initialized = false;
        setMessage(error.message, true);
      } finally {
        state.initializing = null;
        render();
      }
    })();
    return state.initializing;
  }

  async function loadSources({ preserve = true } = {}) {
    const payload = await request("/api/image-lab/krea2-edit/sources?limit=100");
    state.sources = payload.sources || [];
    if (preserve && state.source) {
      state.source = state.sources.find((source) => source.source_id === state.source.source_id) || state.source;
    }
    if (!state.source) {
      const active = state.sources
        .filter((source) => source.state === "pending")
        .sort((left, right) => right.stage_index - left.stage_index)[0];
      if (active) openSource(active, { hydrate: true });
    }
    renderBacklog();
  }

  function setMessage(message = "", error = false) {
    elements.message.textContent = message;
    elements.message.classList.toggle("error", error);
  }

  function projectStages(projectId = state.source?.project_id) {
    return state.sources
      .filter((source) => source.project_id === projectId)
      .sort((left, right) => left.stage_index - right.stage_index);
  }

  function activeProjects() {
    const groups = new Map();
    state.sources
      .filter((source) => source.state === "pending" || source.state === "advanced")
      .forEach((source) => {
        const values = groups.get(source.project_id) || [];
        values.push(source);
        groups.set(source.project_id, values);
      });
    return [...groups.values()]
      .map((stages) => stages.sort((left, right) => left.stage_index - right.stage_index))
      .filter((stages) => stages.some((source) => source.state === "pending"));
  }

  function renderBacklog() {
    elements.backlog.replaceChildren();
    const projects = activeProjects();
    elements.backlogEmpty.hidden = projects.length > 0;
    projects.forEach((stages) => {
      const root = stages[0];
      const source = [...stages].reverse().find((value) => value.state === "pending") || stages.at(-1);
      const attemptCount = stages.reduce((total, value) => total + (value.attempts || []).length, 0);
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = source.project_id === state.source?.project_id ? "active" : "";
      const image = document.createElement("img");
      image.src = source.source_url;
      image.alt = "";
      image.loading = "lazy";
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = root.project_name || root.filename;
      const meta = document.createElement("small");
      meta.textContent = `Étape ${source.stage_index} · ${attemptCount} essai${attemptCount > 1 ? "s" : ""}`;
      copy.append(title, meta);
      button.append(image, copy);
      button.addEventListener("click", () => openSource(source, { hydrate: true }));
      item.append(button);
      elements.backlog.append(item);
    });
  }

  function openSource(source, { hydrate = false, force = false } = {}) {
    if (!source || (state.busy && !force)) return;
    state.source = source;
    if (hydrate) {
      const metadata = source.metadata || {};
      const previous = latestAttempt(source);
      elements.instruction.value = "";
      elements.prompt.value = source.generated_prompt || metadata.prompt || "";
      elements.promptLanguage.value = source.prompt_language || "en";
      const root = projectStages(source.project_id)[0] || source;
      elements.projectName.value = source.project_name || root.project_name || defaultProjectName(root.filename);
      elements.stepName.value = defaultStepName(source);
      delete elements.stepName.dataset.edited;
      const defaults = state.spec.defaults;
      applyRenderSettings({
        model_id: previous?.settings.model_id || metadata.model_id || defaults.model_id,
        aspect_ratio: previous?.settings.aspect_ratio || metadata.aspect_ratio || defaults.aspect_ratio,
        megapixels: previous?.settings.megapixels ?? metadata.megapixels ?? defaults.megapixels,
        ref_boost: previous?.settings.ref_boost ?? defaults.ref_boost,
        steps: previous?.settings.steps ?? defaults.steps,
        seed: previous?.settings.seed || metadata.seed || randomSeed(),
        loras: previous?.settings.loras || metadata.loras || [],
      });
      const latestSuccess = [...(source.attempts || [])].reverse().find((attempt) => attempt.status === "succeeded");
      state.feedbackAttemptId = latestSuccess?.attempt_id || null;
    }
    render();
  }

  function renderLoras() {
    renderLoraPickerStack(elements.loras, {
      resources: state.spec?.loras || [],
      selections: state.loraSlots,
      maximum: 10,
      minimumStrength: -20,
      maximumStrength: 20,
      disabled: state.busy,
      updatePreference: updateResourcePreference,
      refreshResource,
      onChange: (values) => {
        state.loraSlots = values;
        renderLoras();
      },
    });
  }

  function renderResourceManager() {
    renderCatalogManager(elements.catalogManager, {
      models: state.spec?.render_models || [],
      loras: state.spec?.loras || [],
      updatePreference: updateResourcePreference,
      refreshResource,
    });
  }

  async function updateResourcePreference(resource, values) {
    if (!resource || state.busy) return false;
    const selectedModel = elements.model.value;
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      state.spec = await request("/api/image-lab/krea2-edit/spec");
      renderModelPicker(elements.model, {
        resources: state.spec.render_models || [],
        updatePreference: updateResourcePreference,
        refreshResource,
      });
      ensureOption(elements.model, selectedModel, selectedModel);
      elements.model.value = selectedModel;
      syncModelPicker(elements.model);
      renderLoras();
      renderResourceManager();
      render();
      setMessage("Classement du catalogue enregistré.");
      return updated;
    } catch (error) {
      setMessage(error.message, true);
      return false;
    }
  }

  async function refreshResource(resource) {
    if (!resource || state.busy) return false;
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/refresh`, { method: "POST" });
      const selectedModel = elements.model.value;
      state.spec = await request("/api/image-lab/krea2-edit/spec");
      renderModelPicker(elements.model, {
        resources: state.spec.render_models || [],
        updatePreference: updateResourcePreference,
        refreshResource,
      });
      ensureOption(elements.model, selectedModel, selectedModel);
      elements.model.value = selectedModel;
      syncModelPicker(elements.model);
      renderLoras();
      renderResourceManager();
      render();
      setMessage("Informations CivitAI actualisées.");
      return updated;
    } catch (error) {
      setMessage(`Recherche CivitAI indisponible : ${error.message}`, true);
      return false;
    }
  }

  function latestAttempt(source = state.source) {
    return source && source.attempts && source.attempts.length ? source.attempts.at(-1) : null;
  }

  function activeAttempt() {
    return (state.source?.attempts || []).find((attempt) => activeAttemptStatuses.has(attempt.status)) || null;
  }

  function feedbackAttempt() {
    return (state.source?.attempts || []).find(
      (attempt) => attempt.attempt_id === state.feedbackAttemptId && attempt.status === "succeeded",
    ) || null;
  }

  function renderTimeline() {
    elements.timeline.replaceChildren();
    projectStages().forEach((stage) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `krea2-edit-stage-link${stage.source_id === state.source?.source_id ? " active" : ""}`;
      const image = document.createElement("img");
      image.src = stage.source_url;
      image.alt = "";
      image.loading = "lazy";
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = `Étape ${stage.stage_index}`;
      const meta = document.createElement("small");
      meta.textContent = stage.state === "advanced"
        ? stage.accepted_label || "Validée"
        : "En cours";
      copy.append(title, meta);
      button.append(image, copy);
      button.addEventListener("click", () => openSource(stage, { hydrate: true }));
      elements.timeline.append(button);
    });
  }

  function renderRevisions() {
    const revisions = state.source?.revisions || [];
    elements.revisions.replaceChildren();
    elements.revisionsEmpty.hidden = revisions.length > 0;
    elements.revisionCount.textContent = revisions.length
      ? `${revisions.length} révision${revisions.length > 1 ? "s" : ""}`
      : "Aucune révision";
    [...revisions].reverse().forEach((revision, reverseIndex) => {
      const details = document.createElement("details");
      details.className = "krea2-edit-revision";
      const summary = document.createElement("summary");
      summary.textContent = `Modification ${revisions.length - reverseIndex} · ${revision.instruction}`;
      const meta = document.createElement("small");
      const language = revision.prompt_language === "zh" ? "中文" : "EN";
      meta.textContent = `${revision.model_id} · ${language}${revision.feedback_attempt_id ? " · avec feedback visuel" : " · source seule"}`;
      const prompt = document.createElement("pre");
      prompt.textContent = revision.prompt;
      details.append(summary, meta, prompt);
      elements.revisions.append(details);
    });
  }

  function render() {
    const source = state.source;
    elements.editor.hidden = !source;
    if (!source) {
      elements.attemptsEmpty.textContent = "Sélectionnez une image.";
      elements.attemptsEmpty.hidden = false;
      elements.attempts.replaceChildren();
      elements.timeline.replaceChildren();
      elements.revisions.replaceChildren();
      elements.imageToolbar.hidden = true;
      elements.originalFigure.hidden = true;
      elements.images.classList.remove("show-original");
      return;
    }
    elements.title.textContent = `${source.filename} · Étape ${source.stage_index}`;
    const rootSource = projectStages()[0];
    const canShowOriginal = source.stage_index > 1 && Boolean(rootSource?.source_url);
    const showOriginal = canShowOriginal && elements.showOriginal.checked;
    elements.imageToolbar.hidden = !canShowOriginal;
    elements.originalFigure.hidden = !showOriginal;
    elements.images.classList.toggle("show-original", showOriginal);
    if (canShowOriginal) elements.originalImage.src = rootSource.source_url;
    elements.sourceImage.src = source.source_url;
    const latest = latestAttempt(source);
    const active = activeAttempt();
    const feedback = feedbackAttempt();
    elements.resultLoading.hidden = !active;
    elements.resultImage.hidden = !feedback;
    elements.resultEmpty.hidden = Boolean(feedback || active);
    elements.resultCaption.textContent = feedback
      ? "Résultat utilisé comme feedback LLM"
      : "Résultat de feedback LLM";
    if (feedback) elements.resultImage.src = feedback.output_url;
    elements.status.textContent = active ? `● ${active.status}` : latest?.status === "failed" ? "● Échec" : "● Prêt";
    elements.metadata.textContent = `Projet ${source.project_id} · étape ${source.stage_index} · source ${source.metadata.origin} · ${source.metadata.model_id || "modèle inconnu"} · ${source.metadata.aspect_ratio || "ratio inconnu"} · ${source.metadata.megapixels ?? "?"} MP`;
    const exportState = source.export || {};
    const exportRoot = state.spec?.project_exports?.root;
    elements.exportState.classList.toggle("error", exportState.status === "failed");
    elements.exportInfo.textContent = exportState.status === "failed"
      ? `Export en attente : ${exportState.error}`
      : exportState.path
      ? `Chaîne validée : ${exportState.path}`
      : exportRoot
      ? `La chaîne validée sera copiée dans ${exportRoot}`
      : "Export humain non configuré.";
    elements.retryExport.hidden = exportState.status !== "failed";
    const warningValues = [
      ...(state.spec?.resource_warnings || []),
      ...(source.metadata.warnings || []),
    ];
    if (elements.model.selectedOptions[0]?.dataset.missing) warningValues.push("Le checkpoint historique est indisponible : choisissez un modèle installé avant le rendu.");
    state.loraSlots.filter((slot) => slot.name && !(state.spec.loras || []).some((value) => value.comfy_name === slot.name)).forEach((slot) => warningValues.push(`LoRA indisponible : ${slot.name}`));
    elements.warnings.hidden = !warningValues.length;
    elements.warnings.textContent = warningValues.join(" · ");
    const editable = source.state === "pending";
    elements.projectName.disabled = !editable || Boolean(source.project_name);
    elements.stepName.disabled = !editable;
    elements.buildPrompt.disabled = state.busy || !editable || !elements.instruction.value.trim() || !elements.llm.value;
    elements.promptLanguage.disabled = state.busy || !editable;
    elements.render.disabled = state.busy || !editable || Boolean(active) || !elements.prompt.value.trim() || !elements.model.value;
    elements.cancel.disabled = !active;
    elements.processed.disabled = state.busy || Boolean(active);
    elements.hide.disabled = state.busy || Boolean(active);
    renderTimeline();
    renderRevisions();
    renderAttempts();
    renderBacklog();
  }

  function renderAttempts() {
    elements.attempts.replaceChildren();
    const attempts = state.source?.attempts || [];
    elements.attemptsEmpty.hidden = attempts.length > 0;
    if (!attempts.length) elements.attemptsEmpty.textContent = "Aucun essai pour cette étape.";
    [...attempts].reverse().forEach((attempt) => {
      const card = document.createElement("article");
      card.className = `krea2-edit-attempt-card${attempt.accepted ? " accepted" : ""}`;
      if (attempt.output_url) {
        const image = document.createElement("img");
        image.src = attempt.output_url;
        image.alt = `Essai ${attempt.attempt_id}`;
        image.loading = "lazy";
        makeZoomable(image, `Essai · Ref boost ${attempt.settings.ref_boost}`);
        card.append(image);
      }
      const copy = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = `${attempt.status} · Ref boost ${attempt.settings.ref_boost}`;
      const meta = document.createElement("small");
      meta.textContent = attempt.accepted
        ? `Validé · ${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps`
        : attempt.error || `${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps`;
      const actions = document.createElement("span");
      actions.className = "krea2-edit-attempt-actions";
      const reuse = document.createElement("button");
      reuse.type = "button";
      reuse.textContent = "Reprendre prompt et réglages";
      reuse.addEventListener("click", () => reuseAttempt(attempt));
      actions.append(reuse);
      if (attempt.status === "succeeded") {
        const feedback = document.createElement("button");
        feedback.type = "button";
        feedback.textContent = attempt.attempt_id === state.feedbackAttemptId ? "Feedback sélectionné" : "Utiliser comme feedback";
        feedback.disabled = state.busy || attempt.attempt_id === state.feedbackAttemptId;
        feedback.addEventListener("click", () => {
          state.feedbackAttemptId = attempt.attempt_id;
          render();
        });
        actions.append(feedback);
        if (state.source.state === "pending") {
          const promote = document.createElement("button");
          promote.type = "button";
          promote.className = "promote";
          promote.textContent = "Valider et continuer";
          promote.disabled = state.busy
            || Boolean(activeAttempt())
            || !elements.projectName.value.trim()
            || !elements.stepName.value.trim();
          promote.addEventListener("click", () => promoteAttempt(attempt));
          actions.append(promote);
        }
      }
      copy.append(title, meta, actions);
      card.append(copy);
      elements.attempts.append(card);
    });
  }

  function reuseAttempt(attempt) {
    if (state.busy) return;
    elements.prompt.value = attempt.prompt;
    applyRenderSettings(attempt.settings);
    if (attempt.status === "succeeded") state.feedbackAttemptId = attempt.attempt_id;
    render();
  }

  async function promoteAttempt(attempt) {
    if (!state.source || state.busy || attempt.status !== "succeeded") return;
    state.busy = true;
    setMessage("Validation du résultat et création de l’étape suivante…");
    render();
    try {
      const payload = await request(
        `/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/attempts/${encodeURIComponent(attempt.attempt_id)}/promote`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_name: elements.projectName.value.trim(),
            step_name: elements.stepName.value.trim(),
          }),
        },
      );
      state.source = sourceOf(payload);
      state.feedbackAttemptId = null;
      await loadSources();
      state.busy = false;
      openSource(state.source, { hydrate: true });
      setMessage(state.source.export?.status === "failed"
        ? `Étape ${state.source.stage_index} créée. L’export externe pourra être réessayé.`
        : `Étape ${state.source.stage_index} créée. L’image validée est exportée et devient sa source immuable.`);
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  async function buildPrompt() {
    if (!state.source || state.busy) return;
    const instruction = elements.instruction.value.trim();
    if (!instruction) return setMessage("Décrivez la modification demandée.", true);
    const basePrompt = elements.prompt.value.trim();
    let completed = false;
    const outcomeTone = core.createLlmOutcomeTone();
    state.busy = true;
    elements.prompt.value = "";
    reasoningTrace.begin("Reconstruction / réécriture", elements.prompt.closest("section"));
    setMessage("Le modèle reconstruit et réécrit le prompt…");
    render();
    try {
      outcomeTone.start();
      await core.streamRequest(
        reasoningTrace.streamUrl(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/prompt/stream`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            instruction,
            model_id: elements.llm.value,
            base_prompt: basePrompt || null,
            feedback_attempt_id: state.feedbackAttemptId,
            prompt_language: elements.promptLanguage.value,
          }),
        },
        (event) => {
          reasoningTrace.handle(event);
          if (event.kind === "delta") elements.prompt.value += event.text || "";
          if (event.source) {
            state.source = event.source;
            if (event.source.prompt_status === "ready" && event.source.generated_prompt) {
              completed = true;
              elements.prompt.value = event.source.generated_prompt;
            }
          }
        },
        { completionTone: false },
      );
      reasoningTrace.finish();
      if (state.source.prompt_status !== "ready") throw new Error(state.source.prompt_error || "Le prompt n’a pas été validé.");
      completed = true;
      outcomeTone.success();
      elements.instruction.value = "";
      if (!elements.stepName.dataset.edited) {
        elements.stepName.value = defaultStepName(state.source);
      }
      setMessage("Prompt prêt. Vous pouvez le corriger puis lancer autant d’essais que nécessaire.");
    } catch (error) {
      reasoningTrace.finish();
      outcomeTone.failure();
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      await refreshCurrent();
      if (!completed) elements.prompt.value = basePrompt;
      render();
    }
  }

  async function renderAttempt() {
    if (!state.source || state.busy) return;
    state.busy = true;
    setMessage("Préparation du rendu…");
    render();
    try {
      const loras = state.loraSlots.filter((slot) => slot.name).map((slot) => ({ name: slot.name, strength: Number(slot.strength) }));
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: elements.prompt.value.trim(),
          model_id: elements.model.value,
          aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value),
          seed: elements.seed.value,
          ref_boost: Number(elements.refBoost.value),
          steps: Number(elements.steps.value),
          loras,
        }),
      });
      state.source = sourceOf(payload);
      const attempt = latestAttempt();
      const started = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/attempts/${encodeURIComponent(attempt.attempt_id)}/start`, { method: "POST" });
      state.source = sourceOf(started);
      setMessage("Rendu ComfyUI lancé.");
      startPolling();
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  function startPolling() {
    if (state.pollTimer) clearTimeout(state.pollTimer);
    const poll = async () => {
      try {
        await refreshCurrent();
        const active = activeAttempt();
        if (active) {
          render();
          state.pollTimer = setTimeout(poll, 1000);
        }
        else {
          state.pollTimer = null;
          const latestSuccess = [...(state.source?.attempts || [])].reverse().find((attempt) => attempt.status === "succeeded");
          if (latestSuccess) state.feedbackAttemptId = latestSuccess.attempt_id;
          setMessage(latestAttempt()?.status === "succeeded" ? "Rendu terminé." : latestAttempt()?.error || "Rendu terminé.", latestAttempt()?.status === "failed");
          await loadSources();
          render();
        }
      } catch (error) {
        setMessage(error.message, true);
        state.pollTimer = setTimeout(poll, 2500);
      }
    };
    state.pollTimer = setTimeout(poll, 800);
  }

  async function refreshCurrent() {
    if (!state.source) return;
    const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}`);
    state.source = sourceOf(payload);
    const index = state.sources.findIndex((source) => source.source_id === state.source.source_id);
    if (index >= 0) state.sources[index] = state.source;
    else state.sources.push(state.source);
  }

  async function updateState(value) {
    if (!state.source || state.busy) return;
    state.busy = true;
    try {
      await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: value }),
      });
      state.source = null;
      await loadSources({ preserve: false });
      render();
    } catch (error) { setMessage(error.message, true); }
    finally { state.busy = false; render(); }
  }

  async function retryProjectExport() {
    if (!state.source || state.busy) return;
    state.busy = true;
    setMessage("Nouvelle tentative d’export de la chaîne validée…");
    render();
    try {
      const payload = await request(
        `/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/export`,
        { method: "POST" },
      );
      state.source = sourceOf(payload);
      await loadSources();
      setMessage(
        state.source.export?.status === "exported"
          ? "Chaîne validée exportée."
          : "L’export reste indisponible.",
        state.source.export?.status === "failed",
      );
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  elements.uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !elements.uploadImage.files[0]) return;
    state.busy = true;
    elements.upload.disabled = true;
    elements.uploadMessage.hidden = true;
    try {
      const body = new FormData();
      body.append("source_image", elements.uploadImage.files[0]);
      if (elements.uploadSidecar.files[0]) body.append("sidecar", elements.uploadSidecar.files[0]);
      const payload = await request("/api/image-lab/krea2-edit/sources", { method: "POST", body });
      state.source = sourceOf(payload);
      elements.uploadForm.reset();
      await loadSources();
      openSource(state.source, { hydrate: true, force: true });
    } catch (error) {
      elements.uploadMessage.textContent = error.message;
      elements.uploadMessage.hidden = false;
    } finally {
      state.busy = false;
      elements.upload.disabled = false;
      render();
    }
  });

  elements.refresh.addEventListener("click", () => loadSources().catch((error) => setMessage(error.message, true)));
  elements.buildPrompt.addEventListener("click", buildPrompt);
  elements.render.addEventListener("click", renderAttempt);
  elements.cancel.addEventListener("click", async () => {
    const attempt = activeAttempt();
    if (!attempt || !state.source) return;
    try {
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/attempts/${encodeURIComponent(attempt.attempt_id)}/cancel`, { method: "POST" });
      state.source = sourceOf(payload);
      render();
    } catch (error) { setMessage(error.message, true); }
  });
  elements.processed.addEventListener("click", () => updateState("processed"));
  elements.hide.addEventListener("click", () => updateState("hidden"));
  elements.instruction.addEventListener("input", render);
  elements.prompt.addEventListener("input", render);
  elements.model.addEventListener("change", render);
  elements.projectName.addEventListener("input", render);
  elements.stepName.addEventListener("input", () => {
    elements.stepName.dataset.edited = "true";
    render();
  });
  elements.retryExport.addEventListener("click", retryProjectExport);
  elements.showOriginal.addEventListener("change", () => {
    try { localStorage.setItem(showOriginalPreferenceKey, String(elements.showOriginal.checked)); } catch (_) { /* optional preference */ }
    render();
  });
  makeZoomable(elements.originalImage, "Image initiale du projet");
  makeZoomable(elements.sourceImage, "Source immuable de l’étape");
  makeZoomable(elements.resultImage, () => elements.resultCaption.textContent);
  elements.lightboxClose.addEventListener("click", () => elements.lightbox.close());
  elements.lightbox.addEventListener("click", (event) => {
    if (event.target === elements.lightbox) elements.lightbox.close();
  });

  document.querySelectorAll('[data-image-lab-mode="krea2-edit-lab"]').forEach((button) => {
    button.addEventListener("click", () => {
      window.PanelForgeLabNavigation?.switchView("krea2-edit-lab");
      initialize();
    });
  });
})();
