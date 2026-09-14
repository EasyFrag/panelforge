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
    backlogMore: $("krea2-edit-backlog-more"),
    editor: $("krea2-edit-editor"),
    title: $("krea2-edit-title"),
    status: $("krea2-edit-status"),
    timeline: $("krea2-edit-timeline"),
    compareBefore: $("krea2-edit-compare-before"),
    compareAfter: $("krea2-edit-compare-after"),
    compareBeforeImage: $("krea2-edit-compare-before-image"),
    compareAfterImage: $("krea2-edit-compare-after-image"),
    compareView: $("krea2-edit-compare-view"),
    compareSlider: $("krea2-edit-compare-slider"),
    compareHover: $("krea2-edit-compare-hover"),
    compareNote: $("krea2-edit-compare-note"),
    retouchAfter: $("krea2-edit-retouch-after"),
    upscaleAfter: $("krea2-edit-upscale-after"),
    upscalePanel: $("krea2-edit-upscale-panel"),
    upscaleTarget: $("krea2-edit-upscale-target"),
    upscaleModel: $("krea2-edit-upscale-model"),
    upscaleStart: $("krea2-edit-upscale-start"),
    upscaleClose: $("krea2-edit-upscale-close"),
    upscaleNote: $("krea2-edit-upscale-note"),
    upscaleProgress: $("krea2-edit-upscale-progress"),
    upscaleProgressLabel: $("krea2-edit-upscale-progress-label"),
    promoteAfter: $("krea2-edit-promote-after"),
    retouch: $("krea2-edit-retouch"),
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
    assistanceVersion: $("krea2-edit-assistance-version"),
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
    workflow: $("krea2-edit-workflow"),
    engine: $("krea2-edit-engine"),
    fireRedMode: $("krea2-edit-firered-mode"),
    fireRedCfg: $("krea2-edit-firered-cfg"),
    workflowDefaults: $("krea2-edit-workflow-defaults"),
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
    restart: $("krea2-edit-restart"),
    resume: $("krea2-edit-resume"),
    version: $("krea2-edit-version"),
    versionNote: $("krea2-edit-version-note"),
    hide: $("krea2-edit-hide"),
    attempts: $("krea2-edit-attempts"),
    attemptsEmpty: $("krea2-edit-attempts-empty"),
  };
  if (!elements.workspace) return;

  const state = {
    initialized: false,
    initializing: null,
    catalogSignature: null,
    catalogStaticReady: false,
    busy: false,
    spec: null,
    sources: [],
    versions: [],
    backlogProjectIds: [],
    backlogTotal: 0,
    backlogExpanded: false,
    backlogLoading: false,
    sourceListEpoch: 0,
    resumeRequests: new Map(),
    source: null,
    feedbackAttemptId: null,
    loraSlots: [],
    pollTimer: null,
    drafts: new Map(),
    assistanceChoices: new Map(),
    renderEngine: "krea2",
    engineDrafts: new Map(),
    fireRedRecipe: null,
    upscaleRequests: new Map(),
    upscaleSelection: null,
    upscaleCatalogEpoch: 0,
    comparisonKey: "",
    revisionsKey: "",
    pendingInstruction: "",
    contextEpoch: 0,
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

  const retouchEditor = window.PanelForgeKrea2Retouch.create({
    root: elements.retouch,
    load: (sourceId, attemptId) => request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(sourceId)}/attempts/${encodeURIComponent(attemptId)}/retouch`),
    save: (sourceId, attemptId, saving, signal) => {
      const body = new FormData();
      body.append("mask", saving.mask, "mask.png");
      body.append("request_id", saving.id);
      body.append("harmonize", String(saving.harmonize));
      body.append("harmonize_strength", String(saving.strength));
      return request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(sourceId)}/attempts/${encodeURIComponent(attemptId)}/retouch`, { method: "POST", body, signal });
    },
    onOpenChange: (open) => elements.workspace.classList.toggle("retouching", open),
    onSaved: async (payload, sourceId) => {
      const updated = sourceOf(payload);
      const index = state.sources.findIndex((value) => value.source_id === sourceId);
      if (index >= 0) state.sources[index] = updated;
      if (state.source?.source_id === sourceId) {
        state.source = updated;
        state.feedbackAttemptId = payload.attempt_id;
        state.comparisonKey = "";
        render();
        const attempt = updated.attempts.find((value) => value.attempt_id === payload.attempt_id);
        setMessage(`${attempt.label} enregistrée et sélectionnée dans Après.`);
        elements.compareView.closest("section").scrollIntoView({ block: "start" });
      }
    },
  });

  function openRetouch(attemptId) {
    if (!state.source || state.busy || retouchEditor.saving || !state.spec?.retouch?.enabled) return;
    retouchEditor.open(state.source.source_id, attemptId);
  }

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

  function isFireRed() {
    return state.renderEngine === "firered";
  }

  function fireRedWorkflow(settings = {}) {
    return state.spec?.workflows?.find((value) => value.engine === "firered"
      && (!settings.workflow_id || value.id === settings.workflow_id)
      && (!settings.workflow_version || value.version === settings.workflow_version));
  }

  function rememberRenderSettings() {
    if (state.source) state.engineDrafts.set(`${state.source.source_id}:${state.renderEngine}`, renderSettings());
  }

  function switchEngine() {
    if (!state.spec) return;
    if (state.source?.subject_reference) { elements.engine.value = "krea2"; return; }
    if (state.busy || retouchEditor.saving || !isEditable()) {
      elements.engine.value = state.renderEngine;
      return;
    }
    const engine = elements.engine.value;
    if (engine === state.renderEngine) return;
    if (!isFireRed()) state.assistanceChoices.set(state.source.source_id, elements.assistanceVersion.value);
    rememberRenderSettings();
    const saved = state.engineDrafts.get(`${state.source.source_id}:${engine}`);
    const workflow = engine === "firered" ? fireRedWorkflow() : state.spec.recipe;
    if (!workflow) { elements.engine.value = state.renderEngine; return; }
    const defaults = engine === "firered" ? workflow.defaults : state.spec.defaults;
    applyRenderSettings(saved || { ...defaults, engine, workflow_id: workflow.id,
      workflow_version: workflow.version, seed: elements.seed.value || randomSeed(), loras: [] });
    render();
    setMessage(`${engine === "firered" ? "FireRed" : "KREA2"} sélectionné pour le prochain essai et le prochain échange. Le prompt actuel est conservé.`);
  }

  function changeFireRedMode() {
    if (!isFireRed() || state.busy || !isEditable()) return;
    const defaults = fireRedWorkflow(state.fireRedRecipe || {})?.defaults.modes[elements.fireRedMode.value];
    if (!defaults) return;
    elements.steps.value = String(defaults.steps);
    elements.fireRedCfg.value = String(defaults.cfg);
    render();
    setMessage(`Mode ${elements.fireRedMode.value === "lightning" ? "Lightning" : "Standard"} : ${defaults.steps} steps, CFG ${defaults.cfg}.`);
  }

  function renderEngineControls() {
    if (!state.spec) return;
    elements.workspace.querySelectorAll("[data-edit-engine]").forEach((node) => {
      node.hidden = node.dataset.editEngine !== state.renderEngine;
    });
    elements.engine.value = state.renderEngine;
    elements.engine.disabled = state.busy || retouchEditor.saving || !isEditable() || Boolean(state.source?.subject_reference);
    const twoInputs = Boolean(state.source?.subject_reference);
    for (const option of elements.workflow.options) {
      const workflow = state.spec.workflows?.find(w => w.engine === "krea2" && w.version === option.value);
      option.hidden = option.disabled = Boolean(workflow?.requires_subject_reference) !== twoInputs;
    }
    $("krea2-edit-ref-boost-label").textContent = twoInputs ? "Ref boost · sujet" : "Ref boost";
    elements.fireRedMode.disabled = state.busy || !isEditable();
    elements.fireRedCfg.disabled = state.busy || !isEditable();
    elements.megapixels.min = isFireRed() ? "0.1" : "0.5";
    elements.megapixels.max = isFireRed() ? "16" : "4";
    elements.assistanceVersion.closest("label").hidden = isFireRed();
    $("krea2-edit-assistance-note").hidden = isFireRed();
    elements.fixedNote.textContent = isFireRed()
      ? "FireRed 1.1 · format de l’image source conservé · Lightning ou Standard."
      : `Fixe : ${state.spec.fixed.identity_lora} × ${state.spec.fixed.identity_lora_strength} · Euler / Simple · CFG ${state.spec.fixed.cfg}.`;
    if (twoInputs) elements.fixedNote.textContent += " Décor en image 1 (force 1), sujet en image 2 (Ref boost).";
  }

  function applyRenderSettings(settings) {
    state.renderEngine = settings.engine || "krea2";
    ensureOption(elements.engine, state.renderEngine, state.renderEngine);
    elements.engine.value = state.renderEngine;
    if (isFireRed()) {
      const workflow = fireRedWorkflow(settings);
      const defaults = workflow?.defaults || {};
      state.fireRedRecipe = { workflow_id: settings.workflow_id || workflow?.id,
        workflow_version: settings.workflow_version || workflow?.version,
        model_id: settings.model_id || defaults.model_id };
      elements.fireRedMode.value = settings.mode || defaults.mode || "lightning";
      const modeDefaults = defaults.modes?.[elements.fireRedMode.value] || {};
      elements.megapixels.value = String(settings.megapixels ?? defaults.megapixels ?? 1);
      elements.steps.value = String(settings.steps ?? modeDefaults.steps ?? "");
      elements.fireRedCfg.value = String(settings.cfg ?? modeDefaults.cfg ?? "");
      elements.seed.value = String(settings.seed ?? randomSeed());
      elements.assistanceVersion.value = "3.0.0";
      return;
    }
    if (state.source) elements.assistanceVersion.value = assistanceVersionFor(state.source);
    if (settings.workflow_version) {
      ensureOption(elements.workflow, settings.workflow_version, `Workflow ${settings.workflow_version} indisponible`);
      elements.workflow.value = settings.workflow_version;
    }
    const model = settings.model_id || "";
    ensureOption(elements.model, model, model);
    elements.model.value = model;
    syncModelPicker(elements.model);
    ensureOption(elements.ratio, settings.aspect_ratio, settings.aspect_ratio);
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

  function renderSettings() {
    if (isFireRed()) return {
      ...state.fireRedRecipe, engine: "firered", mode: elements.fireRedMode.value,
      megapixels: Number(elements.megapixels.value), seed: elements.seed.value,
      steps: Number(elements.steps.value), cfg: Number(elements.fireRedCfg.value), aspect_ratio: "source",
    };
    return {
      engine: "krea2",
      workflow_id: state.spec?.workflows?.find((w) => (w.engine || "krea2") === "krea2" && w.version === elements.workflow.value)?.id || state.spec?.recipe?.id,
      workflow_version: elements.workflow.value,
      model_id: elements.model.value, aspect_ratio: elements.ratio.value,
      megapixels: Number(elements.megapixels.value), seed: elements.seed.value,
      ref_boost: Number(elements.refBoost.value), steps: Number(elements.steps.value),
      loras: state.loraSlots.filter((slot) => slot.name).map((slot) => ({ name: slot.name, strength: Number(slot.strength) })),
    };
  }

  function applyDefaultRenderSettings() {
    const defaults = state.spec?.defaults || {};
    applyRenderSettings({ ...defaults, engine: "krea2", workflow_version: state.spec?.recipe?.version, seed: randomSeed(), loras: [] });
  }

  function applyWorkflowDefaults() {
    if (state.busy || !isEditable() || isFireRed()) return;
    const workflow = state.spec?.workflows?.find((value) => (value.engine || "krea2") === "krea2" && value.version === elements.workflow.value);
    if (!workflow) return;
    const defaults = workflow.defaults;
    applyRenderSettings({ ...renderSettings(), model_id: defaults.model_id,
      ref_boost: defaults.ref_boost, steps: defaults.steps, loras: [] });
    render();
    setMessage("Réglages de base repris : checkpoint, Ref boost et steps, sans LoRA ajouté. Prompt, ratio, MP et seed conservés.");
  }

  function renderSettingsComplete() {
    if (isFireRed()) return Boolean(fireRedWorkflow(state.fireRedRecipe || {})
      && elements.megapixels.value && elements.steps.value && elements.fireRedCfg.value && elements.seed.value);
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
        const results = await Promise.allSettled([loadCatalog(), loadSources()]);
        state.initialized = results.every(result => result.status === "fulfilled");
        const failed = results.find(result => result.status === "rejected");
        setMessage(failed ? failed.reason.message : "", Boolean(failed));
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

  const catalogStatus = window.PanelForgeKrea2ResourceUi.catalogStatus(elements.workspace,
    force => loadCatalog(force), () => !elements.workspace.hidden);
  let catalogRequest = null;
  function loadCatalog(force = false) {
    if (catalogRequest) return force ? catalogRequest.then(() => loadCatalog(true)) : catalogRequest;
    catalogRequest = fetchCatalog(force).catch(error => {
      catalogStatus.failed(error);
      throw error;
    }).finally(() => { catalogRequest = null; });
    return catalogRequest;
  }
  async function fetchCatalog(force) {
    let next;
    try {
      next = await request(`/api/image-lab/krea2-edit/spec${force ? "?refresh=true" : ""}`);
      if (!next || ![next.render_models, next.loras, next.llm_models].every(Array.isArray)) {
        throw new Error("Réponse de catalogue invalide.");
      }
    } catch (error) { error.catalogPhase = "request"; throw error; }
    if (state.busy || retouchEditor.saving) { catalogStatus.observe(next); catalogStatus.retry(); return; }
    state.spec = next;
    const signature = JSON.stringify([next.render_models, next.loras, next.llm_models]);
    if (state.catalogSignature === signature) { catalogStatus.observe(next); return; }
    const selected = { model: elements.model.value, llm: elements.llm.value,
      ratio: elements.ratio.value, engine: elements.engine.value, workflow: elements.workflow.value };
    window.PanelForgeModelPicker.populate(elements.llm, next.llm_models || [], selected.llm);
    if (selected.llm) window.PanelForgeModelPicker.select(elements.llm, selected.llm, "modèle indisponible");
    renderModelPicker(elements.model, { resources: next.render_models || [],
      updatePreference: updateResourcePreference, refreshResource });
    if (!state.catalogStaticReady) {
      options(elements.ratio, next.aspect_ratios || [], value => value, value => value);
      options(elements.engine, next.engines || [], value => value.id, value => value.name);
      options(elements.workflow, (next.workflows || [next.recipe]).filter(value => (value.engine || "krea2") === "krea2"),
        value => value.version, value => `${value.name || "Workflow"} (${value.version})`);
      if (!state.source) applyDefaultRenderSettings();
      else {
        // A workshop may open before even the static spec. Fill only empty inputs.
        const defaults = isFireRed() ? fireRedWorkflow(state.fireRedRecipe || {})?.defaults || {} : next.defaults || {};
        for (const [field, key] of [["megapixels", "megapixels"], ["steps", "steps"], ["refBoost", "ref_boost"]]) {
          if (!elements[field].value && defaults[key] != null) elements[field].value = String(defaults[key]);
        }
        if (!selected.workflow && !isFireRed()) selected.workflow = next.recipe?.version;
        if (!selected.ratio && !isFireRed()) selected.ratio = defaults.aspect_ratio;
        if (!selected.model && !isFireRed()) selected.model = defaults.model_id;
      }
    }
    for (const key of ["model", "ratio", "engine", "workflow"]) {
      if (selected[key]) {
        ensureOption(elements[key], selected[key], `${selected[key]} · indisponible`);
        elements[key].value = selected[key];
      }
    }
    syncModelPicker(elements.model);
    renderLoras();
    renderResourceManager();
    render();
    state.catalogStaticReady = true;
    state.catalogSignature = signature;
    catalogStatus.observe(next);
  }

  async function loadSources({ preserve = true, expanded = state.backlogExpanded, projectId = state.source?.project_id } = {}) {
    const epoch = state.contextEpoch;
    const requestEpoch = ++state.sourceListEpoch;
    const query = new URLSearchParams({ project_limit: expanded ? "2147483647" : "3" });
    if (projectId) query.set("project_id", projectId);
    state.backlogLoading = true;
    renderBacklog();
    try {
      const payload = await request(`/api/image-lab/krea2-edit/sources?${query}`);
      if (epoch !== state.contextEpoch || requestEpoch !== state.sourceListEpoch) return;
      state.sources = payload.sources || [];
      state.versions = payload.versions || [];
      state.backlogProjectIds = payload.backlog_project_ids || [];
      state.backlogTotal = payload.project_count || 0;
      state.backlogExpanded = Boolean(expanded);
      if (preserve && state.source) {
        state.source = state.sources.find((source) => source.source_id === state.source.source_id) || state.source;
      }
      if (!state.source) {
        const stages = projectStages(state.backlogProjectIds[0]);
        const active = [...stages].reverse().find((source) => isEditable(source));
        if (active) openSource(active, { hydrate: true, force: true });
      }
    } finally {
      if (requestEpoch === state.sourceListEpoch) state.backlogLoading = false;
      renderBacklog();
    }
  }

  async function toggleBacklog() {
    if (state.backlogLoading || state.busy || retouchEditor.saving) return;
    if (state.backlogExpanded) {
      state.backlogExpanded = false;
      renderBacklog();
      return;
    }
    try {
      await loadSources({ expanded: true });
    } catch (error) {
      setMessage(error.message, true);
    }
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

  function projectVersion(source = state.source) {
    return (state.versions || []).find((v) => v.project_id === source?.project_id)
      || { family_id: source?.project_id, number: 1, status: "active" };
  }

  function isEditable(source = state.source) {
    return source?.state === "pending" && projectVersion(source).status !== "historical";
  }

  function renderVersions() {
    const version = projectVersion();
    const versions = (state.versions || []).filter((v) => v.family_id === version.family_id)
      .sort((a, b) => b.number - a.number);
    const key = JSON.stringify(versions);
    if (elements.version.dataset.key !== key) {
      elements.version.replaceChildren();
      versions.forEach((v) => {
        const option = document.createElement("option");
        option.value = v.project_id;
        option.textContent = `Version ${v.number} · ${v.status === "draft" ? "brouillon" : v.status === "active" ? "active" : "historique"}`;
        elements.version.append(option);
      });
      elements.version.dataset.key = key;
    }
    elements.version.value = state.source.project_id;
    elements.version.disabled = state.busy || retouchEditor.saving;
    elements.version.closest("label").hidden = versions.length < 2;
    elements.versionNote.textContent = version.status === "draft"
      ? `Reprise de l’étape ${version.resumed_stage_index}. L’ancienne version reste active jusqu’à la validation de cette image ; sa suite sera conservée dans l’historique.`
      : version.status === "historical" ? "Version historique en lecture seule. Une étape validée peut servir de départ à une nouvelle version."
      : versions.length > 1 ? `Version ${version.number} active. Les anciennes versions restent consultables.` : "";
  }

  function activeProjects() {
    const groups = new Map();
    state.sources
      .filter((source) => (source.state === "pending" || source.state === "advanced")
        && projectVersion(source).status !== "historical")
      .forEach((source) => {
        const values = groups.get(source.project_id) || [];
        values.push(source);
        groups.set(source.project_id, values);
      });
    const candidates = [...groups.values()]
      .map((stages) => stages.sort((left, right) => left.stage_index - right.stage_index))
      .filter((stages) => stages.some((source) => source.state === "pending"));
    const families = new Map();
    candidates.forEach((stages) => {
      const version = projectVersion(stages[0]);
      const previous = families.get(version.family_id);
      if (!previous || version.number > projectVersion(previous[0]).number) families.set(version.family_id, stages);
    });
    return [...families.values()];
  }

  function renderBacklog() {
    elements.backlog.replaceChildren();
    const groups = new Map(activeProjects().map((stages) => [stages[0].project_id, stages]));
    const ids = state.backlogExpanded ? state.backlogProjectIds : state.backlogProjectIds.slice(0, 3);
    const projects = ids.map((id) => groups.get(id)).filter(Boolean);
    elements.backlogEmpty.hidden = projects.length > 0;
    elements.backlogMore.hidden = state.backlogTotal <= 3;
    elements.backlogMore.disabled = state.backlogLoading || state.busy || retouchEditor.saving;
    elements.backlogMore.setAttribute("aria-expanded", String(state.backlogExpanded));
    elements.backlogMore.textContent = state.backlogLoading ? "Chargement…"
      : state.backlogExpanded ? "Afficher seulement les 3 récents"
      : `Afficher les autres ateliers (${state.backlogTotal - 3})`;
    projects.forEach((stages) => {
      const root = stages[0];
      const source = [...stages].reverse().find((value) => value.state === "pending") || stages.at(-1);
      const attemptCount = stages.reduce((total, value) => total + (value.attempts || []).length, 0);
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = projectVersion(source).family_id === projectVersion().family_id ? "active" : "";
      const image = document.createElement("img");
      image.src = source.source_url;
      image.alt = "";
      image.loading = "lazy";
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = root.project_name || root.filename;
      const meta = document.createElement("small");
      const version = projectVersion(source);
      meta.textContent = `V${version.number}${version.status === "draft" ? " · brouillon" : ""} · Étape ${source.stage_index} · ${attemptCount} essai${attemptCount > 1 ? "s" : ""}`;
      copy.append(title, meta);
      button.append(image, copy);
      button.addEventListener("click", () => openSource(source, { hydrate: true }));
      item.append(button);
      elements.backlog.append(item);
    });
  }

  function assistanceVersionFor(source) {
    const chosen = state.assistanceChoices.get(source.source_id);
    if (chosen) return chosen;
    const last = source.revisions?.filter((r) => (r.render_engine || "krea2") === "krea2").at(-1);
    if (last) return last.assistance_version || "1.0.0";
    const parent = state.sources.find((s) => s.source_id === source.parent_source_id);
    return parent?.revisions?.filter((r) => (r.render_engine || "krea2") === "krea2").at(-1)?.assistance_version || "3.0.0";
  }

  function changeAssistanceVersion() {
    if (!state.source || state.busy || !isEditable()) return;
    state.assistanceChoices.set(state.source.source_id, elements.assistanceVersion.value);
    setMessage("Version choisie pour le prochain échange. Le prompt et les réglages actuels sont conservés.");
  }

  function openSource(source, { hydrate = false, force = false } = {}) {
    if (!source || retouchEditor.saving || (state.busy && !force)) return;
    if (source.source_id !== state.source?.source_id) {
      rememberRenderSettings();
      state.contextEpoch += 1;
      retouchEditor.close();
      closeUpscale();
    }
    if (state.source && state.source.source_id !== source.source_id) {
      state.drafts.set(state.source.source_id, {
        prompt: elements.prompt.value, instruction: elements.instruction.value,
        settings: renderSettings(), feedback: state.feedbackAttemptId,
      });
      state.pendingInstruction = "";
    }
    state.source = source;
    if (hydrate) {
      const metadata = source.metadata || {};
      const resumed = source.attempts?.find((a) => a.attempt_id === (source.resume_attempt_id || source.accepted_attempt_id));
      const previous = resumed || latestAttempt(source);
      elements.instruction.value = "";
      elements.prompt.value = resumed?.prompt || source.generated_prompt || metadata.prompt || "";
      elements.promptLanguage.value = source.prompt_language || "en";
      elements.assistanceVersion.value = assistanceVersionFor(source);
      elements.assistanceVersion.querySelector('[value="1.0.0"]').hidden = elements.assistanceVersion.value !== "1.0.0";
      if (source.prompt_model_id) {
        window.PanelForgeModelPicker.select(elements.llm, source.prompt_model_id, "modèle historique indisponible");
      }
      const root = projectStages(source.project_id)[0] || source;
      elements.projectName.value = source.project_name || root.project_name || defaultProjectName(root.filename);
      elements.stepName.value = defaultStepName(source);
      delete elements.stepName.dataset.edited;
      const defaults = state.spec?.defaults || {};
      const parent = state.sources.find((s) => s.source_id === source.parent_source_id);
      const inherited = parent?.attempts?.find((a) => a.attempt_id === source.parent_attempt_id)?.settings;
      const fireSettings = previous?.settings?.engine === "firered" ? previous.settings
        : !previous && (metadata.firered_settings || (inherited?.engine === "firered" ? inherited : null));
      applyRenderSettings(fireSettings ? {
        ...fireSettings, engine: "firered",
        workflow_id: previous?.workflow_id || (source.recipe?.engine === "firered" ? source.recipe.id : undefined),
        workflow_version: previous?.workflow_version || (source.recipe?.engine === "firered" ? source.recipe.version : undefined),
      } : {
        workflow_version: resumed?.workflow_version || (source.subject_reference || !isEditable(source) ? source.recipe?.version : state.spec?.recipe?.version),
        model_id: previous?.settings.model_id || metadata.model_id || defaults.model_id,
        aspect_ratio: previous?.settings.aspect_ratio || metadata.aspect_ratio || defaults.aspect_ratio,
        megapixels: previous?.settings.megapixels ?? metadata.megapixels ?? defaults.megapixels,
        ref_boost: previous?.settings.ref_boost ?? metadata.ref_boost ?? inherited?.ref_boost ?? defaults.ref_boost,
        steps: previous?.settings.steps ?? metadata.steps ?? inherited?.steps ?? defaults.steps,
        seed: previous?.settings.seed ?? metadata.seed ?? randomSeed(),
        loras: previous?.settings.loras || metadata.loras || [],
      });
      const latestSuccess = [...(source.attempts || [])].reverse().find((attempt) => attempt.status === "succeeded");
      state.feedbackAttemptId = resumed?.attempt_id || source.accepted_attempt_id || latestSuccess?.attempt_id || null;
      const draft = state.drafts.get(source.source_id);
      if (draft) {
        elements.prompt.value = draft.prompt;
        elements.instruction.value = draft.instruction;
        applyRenderSettings(draft.settings);
        state.feedbackAttemptId = draft.feedback;
      }
    }
    render();
    if (activeAttempt()) startPolling();
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
    const stages = projectStages();
    const entries = stages.length ? [{ stage: stages[0], original: true }, ...stages.map((stage) => ({ stage, original: false }))] : [];
    entries.forEach(({ stage, original }) => {
      const card = document.createElement("div");
      card.className = `krea2-edit-stage-link${!original && stage.source_id === state.source?.source_id ? " active" : ""}`;
      const button = document.createElement("button");
      button.type = "button";
      button.disabled = state.busy;
      const image = document.createElement("img");
      const accepted = stage.attempts?.find((a) => a.attempt_id === stage.accepted_attempt_id);
      image.src = original ? stage.source_url : accepted?.output_url || stage.source_url;
      image.alt = original ? "Image initiale" : accepted ? `Résultat validé de l’étape ${stage.stage_index}` : `Source de l’étape ${stage.stage_index}`;
      image.loading = "lazy";
      makeZoomable(image, image.alt);
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = original ? "Base" : `Étape ${stage.stage_index}`;
      const meta = document.createElement("small");
      meta.textContent = original ? "Image initiale" : stage.state === "advanced"
        ? stage.accepted_label || "Validée"
        : "En cours";
      copy.append(title, meta);
      button.append(copy);
      card.append(image, button);
      button.addEventListener("click", () => openSource(stage, { hydrate: true }));
      elements.timeline.append(card);
    });
  }

  function renderRevisions() {
    const revisions = state.source?.revisions || [];
    const key = JSON.stringify([state.source?.source_id, revisions.map((r) => r.revision_id), state.pendingInstruction]);
    if (key === state.revisionsKey) return;
    state.revisionsKey = key;
    elements.revisions.replaceChildren();
    elements.revisionsEmpty.hidden = revisions.length > 0;
    elements.revisionCount.textContent = revisions.length
      ? `${revisions.length} révision${revisions.length > 1 ? "s" : ""}`
      : "Aucune révision";
    revisions.forEach((revision, index) => {
      const exchange = document.createElement("article");
      exchange.className = "krea2-edit-chat-turn";
      const user = document.createElement("p");
      user.className = "krea2-edit-chat-user";
      user.textContent = revision.instruction;
      const assistant = document.createElement("p");
      assistant.textContent = revision.assistant_message || "Prompt proposé — ancien échange sans réponse conversationnelle.";
      const details = document.createElement("details");
      details.className = "krea2-edit-revision";
      const summary = document.createElement("summary");
      summary.textContent = revision.render_engine === "firered" ? `Voir le prompt ${index + 1} · FireRed`
        : `Voir le prompt ${index + 1} · V${(revision.assistance_version || "1.0.0").split(".")[0]}`;
      const meta = document.createElement("small");
      const language = revision.prompt_language === "zh" ? "中文" : "EN";
      meta.textContent = `${revision.model_id} · ${language}${revision.feedback_attempt_id ? " · avec feedback visuel" : " · source seule"}`;
      const prompt = document.createElement("pre");
      prompt.textContent = revision.prompt;
      details.append(summary, meta, prompt);
      exchange.append(user, assistant, details);
      elements.revisions.append(exchange);
    });
    if (state.pendingInstruction) {
      const pending = document.createElement("p");
      pending.className = "krea2-edit-chat-user";
      pending.textContent = `${state.pendingInstruction}\nEn cours…`;
      elements.revisions.append(pending);
      elements.revisionsEmpty.hidden = true;
    }
    elements.revisions.scrollTop = elements.revisions.scrollHeight;
  }

  function renderComparison() {
    const source = state.source;
    if (!source) return;
    const attempts = (source.attempts || []).filter((a) => a.status === "succeeded" && a.output_url);
    const choices = [{ id: "source", label: "Source de l’étape", url: source.source_url },
      ...attempts.map((a) => ({ id: a.attempt_id, label: a.label || `Essai ${(source.attempts || []).indexOf(a) + 1}`, url: a.output_url }))];
    const key = JSON.stringify([source.source_id, choices, state.feedbackAttemptId]);
    if (key === state.comparisonKey) return;
    const previousSource = elements.compareView.dataset.sourceId;
    const before = previousSource === source.source_id ? elements.compareBefore.value : "source";
    const after = state.feedbackAttemptId || attempts.at(-1)?.attempt_id || "source";
    for (const select of [elements.compareBefore, elements.compareAfter]) {
      select.replaceChildren(...choices.map((c) => new Option(c.label, c.id)));
    }
    elements.compareBefore.value = choices.some((c) => c.id === before) ? before : "source";
    elements.compareAfter.value = after;
    elements.compareView.dataset.sourceId = source.source_id;
    state.comparisonKey = key;
    updateComparisonImages();
  }

  function updateComparisonImages() {
    const source = state.source;
    if (!source) return;
    for (const [select, image] of [[elements.compareBefore, elements.compareBeforeImage], [elements.compareAfter, elements.compareAfterImage]]) {
      const url = select.value === "source" ? source.source_url
        : source.attempts.find((a) => a.attempt_id === select.value)?.output_url;
      if (url && image.getAttribute("src") !== url) image.src = url;
    }
    elements.compareNote.textContent = elements.compareBefore.value === elements.compareAfter.value
      ? "Même image des deux côtés. Choisis un essai pour le comparer à sa source."
      : "Glisse sur l’image ou utilise le curseur. Les proportions restent intactes.";
    updateComparisonActions();
  }

  function canPromote(attempt) {
    return Boolean(isEditable() && !state.busy && !retouchEditor.saving && state.source.prompt_status !== "generating"
      && !activeAttempt() && attempt?.status === "succeeded" && attempt.output_url
      && elements.projectName.value.trim() && elements.stepName.value.trim());
  }

  function updateComparisonActions() {
    const source = state.source;
    const candidate = source?.attempts.find((a) => a.attempt_id === elements.compareAfter.value);
    elements.retouchAfter.disabled = state.busy || !state.spec?.retouch?.enabled || !candidate
      || (!isEditable(source) && !candidate.retouch && !candidate.upscale?.mask_asset_id);
    elements.retouchAfter.textContent = isEditable(source) ? "Retoucher l’image Après" : "Voir le masque Après";
    elements.promoteAfter.hidden = !isEditable(source);
    elements.promoteAfter.disabled = !canPromote(candidate);
    elements.promoteAfter.title = !candidate ? "Choisis un essai réussi dans Après."
      : !elements.projectName.value.trim() || !elements.stepName.value.trim()
      ? "Renseigne le nom du projet et de l’étape pour continuer." : "";
    elements.upscaleAfter.hidden = !(window.PanelForgeDlss || state.spec?.upscale?.enabled) || !isEditable(source);
    elements.upscaleAfter.disabled = window.PanelForgeDlss ? !canDlss(candidate) : !canUpscale(candidate);
    const selected = source?.attempts.find((a) => a.attempt_id === state.upscaleSelection?.attemptId);
    elements.upscaleStart.disabled = !canUpscale(selected) || !elements.upscaleModel.value;
    elements.upscaleModel.disabled = state.busy || Boolean(activeAttempt());
    const active = activeAttempt();
    elements.upscaleProgress.hidden = active?.kind !== "upscale";
    if (active?.kind === "upscale") elements.upscaleProgressLabel.textContent = active.status === "queued"
      ? "Amélioration en attente dans ComfyUI…" : active.status === "cancel_pending"
      ? "Annulation de l’amélioration en cours…" : "Amélioration des détails en cours…";
  }

  function canDlss(attempt) {
    return Boolean(window.PanelForgeDlss && isEditable() && !state.busy && !retouchEditor.saving
      && attempt?.status === "succeeded" && attempt.output_url);
  }

  function canUpscale(attempt) {
    return Boolean(isEditable() && !state.busy && !retouchEditor.saving && !activeAttempt()
      && state.spec?.upscale?.enabled && attempt?.status === "succeeded" && attempt.output_url);
  }

  function closeUpscale() {
    state.upscaleCatalogEpoch += 1;
    state.upscaleSelection = null;
    elements.upscalePanel.hidden = true;
    elements.upscaleAfter.setAttribute("aria-expanded", "false");
  }

  async function openUpscale(attemptId = elements.compareAfter.value) {
    const candidate = state.source?.attempts.find((a) => a.attempt_id === attemptId);
    if (!canUpscale(candidate)) return;
    const epoch = ++state.upscaleCatalogEpoch;
    state.upscaleSelection = { sourceId: state.source.source_id, attemptId };
    elements.upscalePanel.hidden = false;
    elements.upscaleAfter.setAttribute("aria-expanded", "true");
    elements.upscaleTarget.textContent = `Améliorer ${candidate.label}`;
    elements.upscaleNote.textContent = "Chargement des modèles…";
    const previousModel = elements.upscaleModel.value;
    elements.upscaleModel.replaceChildren();
    updateComparisonActions();
    try {
      const catalog = await request("/api/image-lab/krea2-edit/upscalers");
      if (epoch !== state.upscaleCatalogEpoch) return;
      elements.upscaleModel.replaceChildren(...catalog.models.map((name) => new Option(name, name)));
      elements.upscaleModel.value = catalog.models.includes(previousModel) ? previousModel : catalog.default || "";
      elements.upscaleNote.textContent = catalog.models.length
        ? `Modèle : ${elements.upscaleModel.value}` : "Aucun upscaler disponible dans ComfyUI.";
    } catch (error) {
      if (epoch !== state.upscaleCatalogEpoch) return;
      elements.upscaleNote.textContent = error.message;
    }
    updateComparisonActions();
  }

  async function startUpscale() {
    const selection = state.upscaleSelection;
    const candidate = state.source?.attempts.find((a) => a.attempt_id === selection?.attemptId);
    if (!canUpscale(candidate) || !elements.upscaleModel.value || selection.sourceId !== state.source.source_id) return;
    const model = elements.upscaleModel.value;
    const key = JSON.stringify([selection.sourceId, selection.attemptId, model]);
    let requestId = state.upscaleRequests.get(key);
    if (!requestId) {
      requestId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      state.upscaleRequests.set(key, requestId);
    }
    const epoch = state.contextEpoch;
    state.busy = true;
    elements.upscaleNote.textContent = "Préparation de l’amélioration…";
    render();
    try {
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(selection.sourceId)}/attempts/${encodeURIComponent(selection.attemptId)}/upscale`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_name: model, request_id: requestId }),
      });
      if (epoch !== state.contextEpoch) return;
      state.source = sourceOf(payload);
      state.upscaleRequests.delete(key);
      closeUpscale();
      setMessage("Amélioration des détails lancée. Tu peux continuer à consulter tes images.");
      startPolling();
    } catch (error) {
      if (epoch !== state.contextEpoch) return;
      elements.upscaleNote.textContent = error.message;
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  function setComparisonPosition(value) {
    const position = Math.max(0, Math.min(100, Number(value)));
    elements.compareSlider.value = String(position);
    elements.compareView.style.setProperty("--split", `${position}%`);
    elements.compareSlider.setAttribute("aria-valuetext", `${Math.round(position)} % avant, ${Math.round(100 - position)} % après`);
  }

  function render() {
    const source = state.source;
    if (source) window.PanelForgeLabCore?.observeRenderAttempts?.(source.attempts || [], `edit:${source.source_id}`);
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
    renderVersions();
    renderEngineControls();
    const rootSource = projectStages()[0];
    const canShowOriginal = source.stage_index > 1 && Boolean(rootSource?.source_url);
    const showOriginal = canShowOriginal && elements.showOriginal.checked;
    elements.imageToolbar.hidden = !canShowOriginal;
    elements.originalFigure.hidden = !showOriginal;
    elements.images.classList.toggle("show-original", showOriginal);
    if (canShowOriginal) elements.originalImage.src = rootSource.source_url;
    elements.sourceImage.src = source.source_url;
    $("krea2-edit-reference-pair").hidden = !source.subject_reference;
    if (source.subject_reference) {
      $("krea2-edit-scene-reference").src = source.source_url;
      $("krea2-edit-subject-reference").src = source.subject_reference.url;
    }
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
    elements.metadata.textContent = `Projet ${source.project_id} · étape ${source.stage_index} · source ${source.metadata.origin} · ${source.metadata.model_id || "modèle inconnu"} · ${source.metadata.engine === "firered" ? "format source" : source.metadata.aspect_ratio || "ratio inconnu"} · ${source.metadata.megapixels ?? "?"} MP`;
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
    if (!isFireRed() && elements.model.selectedOptions[0]?.dataset.missing) warningValues.push("Le checkpoint historique est indisponible : choisissez un modèle installé avant le rendu.");
    if (!isFireRed()) state.loraSlots.filter((slot) => slot.name && !(state.spec?.loras || []).some((value) => value.comfy_name === slot.name)).forEach((slot) => warningValues.push(`LoRA indisponible : ${slot.name}`));
    if (isFireRed() && !fireRedWorkflow(state.fireRedRecipe || {})) warningValues.push("La recette FireRed de cet essai est indisponible.");
    elements.warnings.hidden = !warningValues.length;
    elements.warnings.textContent = warningValues.join(" · ");
    const editable = isEditable(source);
    elements.resume.hidden = !source.accepted_attempt_id;
    elements.resume.disabled = state.busy || retouchEditor.saving || Boolean(active)
      || source.prompt_status === "generating";
    elements.restart.hidden = !editable;
    elements.restart.disabled = !canRestart();
    elements.restart.title = "Repartir de la source de cette étape avec une conversation et des essais vides.";
    elements.projectName.disabled = !editable || Boolean(source.project_name);
    elements.stepName.disabled = !editable;
    elements.buildPrompt.disabled = state.busy || !editable || !elements.instruction.value.trim() || !elements.llm.value || !state.spec?.llm_models?.length;
    elements.promptLanguage.disabled = state.busy || !editable;
    elements.assistanceVersion.disabled = state.busy || !editable;
    elements.workflow.disabled = state.busy || !editable;
    elements.workflowDefaults.disabled = state.busy || !editable;
    elements.render.disabled = state.busy || !editable || Boolean(active) || !elements.prompt.value.trim()
      || (isFireRed() ? !fireRedWorkflow(state.fireRedRecipe || {})
        : !state.spec?.render_models?.some(m => m.comfy_name === elements.model.value)
          || state.loraSlots.some(slot => slot.name && !state.spec?.loras?.some(lora => lora.comfy_name === slot.name)));
    elements.cancel.disabled = !active;
    elements.processed.disabled = state.busy || Boolean(active) || projectVersion().status === "historical";
    elements.hide.disabled = state.busy || Boolean(active) || projectVersion().status === "historical";
    renderTimeline();
    renderRevisions();
    renderComparison();
    renderAttempts();
    renderBacklog();
    updateComparisonActions();
  }

  function renderAttempts() {
    elements.attempts.replaceChildren();
    const attempts = state.source?.attempts || [];
    elements.attemptsEmpty.hidden = attempts.length > 0;
    if (!attempts.length) elements.attemptsEmpty.textContent = "Aucun essai pour cette étape.";
    const groups = window.PanelForgeDlss?.groups(attempts, `edit:${state.source.source_id}`, elements.compareAfter.value) || attempts.map(attempt => ({ attempt }));
    [...groups].reverse().forEach(group => {
      const attempt = group.attempt;
      const card = document.createElement("article");
      card.className = `krea2-edit-attempt-card${attempt.accepted ? " accepted" : ""}`;
      if (group.variants) card.append(window.PanelForgeDlss.picker(group, value => { elements.compareAfter.value = value; renderComparison(); renderAttempts(); updateComparisonActions(); }));
      if (attempt.output_url) {
        const image = document.createElement("img");
        image.src = attempt.output_url;
        image.alt = attempt.label || `Essai ${attempt.attempt_id}`;
        image.loading = "lazy";
        makeZoomable(image, attempt.label || `Essai · Ref boost ${attempt.settings.ref_boost}`);
        card.append(image);
      }
      const copy = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = attempt.kind === "retouch"
        ? `${attempt.label} · composition locale`
        : attempt.upscale ? `${attempt.label} · ${attempt.status}`
        : attempt.engine === "firered" ? `${attempt.label} · ${attempt.status} · FireRed ${attempt.settings.mode === "lightning" ? "Lightning" : "Standard"}`
        : `${attempt.label || "Essai"} · ${attempt.status} · Ref boost ${attempt.settings.ref_boost}`;
      const meta = document.createElement("small");
      meta.textContent = attempt.accepted
        ? `Validé · ${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps`
        : attempt.error || `${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps`;
      if (attempt.retouch) meta.textContent = `${attempt.accepted ? "Validée · " : ""}${attempt.retouch.width} × ${attempt.retouch.height} · taille de la source`;
      if (attempt.upscale) meta.textContent = attempt.error || `${attempt.upscale.model_name} · ${attempt.upscale.width} × ${attempt.upscale.height} · ${attempt.upscale.preserve_source_size === false ? "finition agrandie" : "taille de la source"}`;
      else meta.textContent += ` · workflow ${attempt.workflow_version || state.source.recipe?.version || "historique"}`;
      if (attempt.engine === "firered" && attempt.kind === "generation") {
        meta.textContent += ` · CFG ${attempt.settings.cfg}`;
        if (attempt.output_dimensions) meta.textContent += ` · ${attempt.output_dimensions.width} × ${attempt.output_dimensions.height}`;
      }
      const actions = document.createElement("span");
      actions.className = "krea2-edit-attempt-actions";
      const reuse = document.createElement("button");
      reuse.type = "button";
      reuse.textContent = "Reprendre prompt et réglages";
      reuse.addEventListener("click", () => reuseAttempt(attempt));
      actions.append(reuse);
      if (attempt.status === "succeeded") {
        if (window.PanelForgeDlss && isEditable()) {
          const upscale = window.PanelForgeDlss.button({ owner: "edit", ownerId: state.source.source_id, attempt });
          upscale.disabled = !canDlss(attempt);
          actions.append(upscale);
        }
        if (window.PanelForgeDlss?.comparisonButton) actions.append(window.PanelForgeDlss.comparisonButton({ owner: "edit", ownerId: state.source.source_id, attempt }));
        if (state.spec?.retouch?.enabled && (isEditable() || attempt.retouch || attempt.upscale?.mask_asset_id)) {
          const retouch = document.createElement("button");
          retouch.type = "button";
          retouch.textContent = state.source.state !== "pending" ? "Voir le masque" : (attempt.retouch || attempt.upscale?.mask_asset_id) ? "Reprendre le masque" : "Retoucher";
          retouch.disabled = state.busy;
          retouch.addEventListener("click", () => openRetouch(attempt.attempt_id));
          actions.append(retouch);
        }
        const feedback = document.createElement("button");
        feedback.type = "button";
        feedback.textContent = attempt.attempt_id === state.feedbackAttemptId ? "Feedback sélectionné" : "Utiliser comme feedback";
        feedback.disabled = state.busy || attempt.attempt_id === state.feedbackAttemptId;
        feedback.addEventListener("click", () => {
          state.feedbackAttemptId = attempt.attempt_id;
          render();
        });
        actions.append(feedback);
        if (isEditable()) {
          const promote = document.createElement("button");
          promote.type = "button";
          promote.className = "promote";
          promote.textContent = "Valider et continuer";
          promote.disabled = !canPromote(attempt);
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
    rememberRenderSettings();
    elements.prompt.value = attempt.prompt;
    applyRenderSettings({ ...attempt.settings, workflow_id: attempt.workflow_id || state.source.recipe?.id,
      workflow_version: attempt.workflow_version || state.source.recipe?.version });
    if (attempt.status === "succeeded") state.feedbackAttemptId = attempt.attempt_id;
    render();
  }

  async function promoteAttempt(attempt) {
    if (!canPromote(attempt)) return;
    retouchEditor.close();
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
      state.contextEpoch += 1;
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
    state.pendingInstruction = instruction;
    reasoningTrace.begin("Préparation de la modification", elements.prompt.closest("section"));
    setMessage("Le modèle prépare le prompt de modification…");
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
            assistance_version: elements.assistanceVersion.value,
            render_engine: state.renderEngine,
          }),
        },
        (event) => {
          reasoningTrace.handle(event);
          // The conversational response is JSON; only an accepted prompt belongs in the editor.
          if (event.source) {
            state.source = event.source;
            state.pendingInstruction = "";
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
      state.pendingInstruction = "";
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
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(state.source.source_id)}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: elements.prompt.value.trim(),
          ...renderSettings(),
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
    const watchedSourceId = state.source?.source_id;
    const epoch = state.contextEpoch;
    const poll = async () => {
      if (epoch !== state.contextEpoch) return;
      try {
        await refreshCurrent();
        if (epoch !== state.contextEpoch) return;
        if (watchedSourceId !== state.source?.source_id) { state.pollTimer = null; return; }
        const active = activeAttempt();
        if (active) {
          render();
          state.pollTimer = setTimeout(poll, 1000);
        }
        else {
          state.pollTimer = null;
          const latestSuccess = [...(state.source?.attempts || [])].reverse().find((attempt) => attempt.status === "succeeded");
          if (latestSuccess) state.feedbackAttemptId = latestSuccess.attempt_id;
          if (latestSuccess?.upscale && latestSuccess === latestAttempt()) elements.compareBefore.value = latestSuccess.upscale.parent_attempt_id;
          setMessage(latestAttempt()?.status === "succeeded" ? "Rendu terminé." : latestAttempt()?.error || "Rendu terminé.", latestAttempt()?.status === "failed");
          await loadSources();
          render();
        }
      } catch (error) {
        if (epoch !== state.contextEpoch) return;
        setMessage(error.message, true);
        state.pollTimer = setTimeout(poll, 2500);
      }
    };
    state.pollTimer = setTimeout(poll, 800);
  }

  async function refreshCurrent() {
    if (!state.source) return;
    const epoch = state.contextEpoch;
    const requestedSource = state.source;
    const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(requestedSource.source_id)}`);
    if (epoch !== state.contextEpoch) return;
    if (payload.versions) state.versions = payload.versions;
    const refreshed = sourceOf(payload);
    if ((refreshed.restart_count || 0) < (state.sources.find((source) => source.source_id === refreshed.source_id)?.restart_count || 0)) return;
    if (state.source === requestedSource) state.source = refreshed;
    const index = state.sources.findIndex((source) => source.source_id === refreshed.source_id);
    if (index >= 0) state.sources[index] = refreshed;
    else state.sources.push(refreshed);
  }

  function canRestart() {
    return Boolean(isEditable() && !state.busy && !retouchEditor.saving
      && state.source.prompt_status !== "generating" && !activeAttempt());
  }

  async function openVersion(projectId) {
    if (!projectId || state.busy || retouchEditor.saving) return;
    state.busy = true;
    state.contextEpoch += 1;
    render();
    try {
      const payload = await request(`/api/image-lab/krea2-edit/projects/${encodeURIComponent(projectId)}`);
      const stages = payload.sources || [];
      if (!stages.length) throw new Error("Version introuvable.");
      const merged = new Map(state.sources.map((s) => [s.source_id, s]));
      stages.forEach((s) => merged.set(s.source_id, s));
      state.sources = [...merged.values()];
      state.versions = payload.versions || state.versions;
      state.busy = false;
      openSource([...stages].reverse().find((s) => s.state === "pending") || stages.at(-1), { hydrate: true });
      setMessage("");
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  async function resumeStage() {
    const source = state.source;
    if (!source?.accepted_attempt_id || state.busy || retouchEditor.saving || activeAttempt()) return;
    let requestId = state.resumeRequests.get(source.source_id);
    if (!requestId) {
      requestId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      state.resumeRequests.set(source.source_id, requestId);
    }
    state.busy = true;
    state.contextEpoch += 1;
    retouchEditor.close();
    setMessage("Préparation d’une version de travail ; l’ancienne chaîne est conservée…");
    render();
    try {
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(source.source_id)}/resume`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId }),
      });
      const resumed = sourceOf(payload);
      await loadSources({ projectId: resumed.project_id });
      state.busy = false;
      openSource(resumed, { hydrate: true });
      state.resumeRequests.delete(source.source_id);
      setMessage("Version de travail ouverte avec la source, la conversation et les réglages de l’essai validé. La nouvelle suite commencera à sa validation.");
    } catch (error) {
      // Keep the same request ID if the server saved but the response was lost.
      setMessage(error.message, true);
    } finally {
      state.busy = false;
      render();
    }
  }

  async function restartStage() {
    if (!canRestart()) return;
    if (!window.confirm("Recommencer cette étape depuis son image source ? Les échanges, prompts, essais et brouillons de retouche de cette étape seront retirés de l’atelier. Les réglages de rendu reviendront à ceux de départ. Les étapes validées sont conservées.")) return;
    const source = state.source;
    state.busy = true;
    retouchEditor.close();
    setMessage("Reprise de l’étape depuis sa source…"); render();
    try {
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(source.source_id)}/restart`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_restart_count: source.restart_count || 0 }),
      });
      const restarted = sourceOf(payload);
      state.contextEpoch++;
      if (state.pollTimer) clearTimeout(state.pollTimer);
      state.pollTimer = null;
      retouchEditor.discardSource(source.source_id);
      state.drafts.delete(source.source_id);
      for (const engine of ["krea2", "firered"]) state.engineDrafts.delete(`${source.source_id}:${engine}`);
      state.pendingInstruction = ""; state.feedbackAttemptId = null;
      state.comparisonKey = ""; state.revisionsKey = "";
      elements.reasoning.hidden = true; elements.reasoningContent.textContent = "";
      const index = state.sources.findIndex((value) => value.source_id === restarted.source_id);
      if (index >= 0) state.sources[index] = restarted; else state.sources.push(restarted);
      state.busy = false;
      openSource(restarted, { hydrate: true });
      elements.instruction.focus();
      setMessage(restarted.attempts.length || restarted.revisions.length
        ? "Étape rechargée : la reprise avait déjà été enregistrée."
        : "Étape recommencée. Décris à nouveau la modification souhaitée depuis sa source.");
    } catch (error) { setMessage(error.message, true); }
    finally { state.busy = false; render(); }
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

  elements.retouchAfter.addEventListener("click", () => openRetouch(elements.compareAfter.value));
  elements.upscaleAfter.addEventListener("click", () => {
    const attempt = state.source?.attempts.find(a => a.attempt_id === elements.compareAfter.value);
    if (window.PanelForgeDlss && attempt) window.PanelForgeDlss.open({ owner: "edit", ownerId: state.source.source_id, attempt });
    else openUpscale();
  });
  document.getElementById("krea2-edit-upscale-legacy")?.addEventListener("click", () => openUpscale());
  window.addEventListener("panelforge:dlss-complete", async event => {
    const job = event.detail, source = state.source;
    if (job.snapshot.owner !== "edit" || source?.source_id !== job.snapshot.owner_id) return;
    if (state.busy || retouchEditor.saving) { setTimeout(() => window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: job })), 1000); return; }
    try {
      await refreshCurrent();
      if (state.source?.source_id !== source.source_id) return;
      render();
      if (job.comparison && !job.select_result) return;
      elements.compareAfter.value = job.candidate_id;
      elements.compareBefore.value = job.snapshot.parent_attempt_id;
      renderComparison(); updateComparisonActions();
    } catch (error) { setMessage(error.message, true); }
  });
  elements.upscaleClose.addEventListener("click", closeUpscale);
  elements.upscaleStart.addEventListener("click", startUpscale);
  elements.upscaleModel.addEventListener("change", () => {
    elements.upscaleNote.textContent = `Modèle : ${elements.upscaleModel.value}`;
    updateComparisonActions();
  });
  elements.promoteAfter.addEventListener("click", () => {
    const candidate = state.source?.attempts.find((a) => a.attempt_id === elements.compareAfter.value);
    if (candidate) promoteAttempt(candidate);
  });

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
  elements.backlogMore.addEventListener("click", toggleBacklog);
  elements.compareBefore.addEventListener("change", updateComparisonImages);
  elements.compareAfter.addEventListener("change", () => {
    if (elements.compareAfter.value !== "source") {
      state.feedbackAttemptId = elements.compareAfter.value;
      render();
    }
    if (elements.compareAfter.value === "source") elements.retouchAfter.disabled = true;
    updateComparisonImages();
  });
  elements.compareSlider.addEventListener("input", () => setComparisonPosition(elements.compareSlider.value));
  const moveComparison = (event) => {
    const bounds = elements.compareView.getBoundingClientRect();
    if (bounds.width) setComparisonPosition(100 * (event.clientX - bounds.left) / bounds.width);
  };
  elements.compareView.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    elements.compareView.setPointerCapture(event.pointerId);
    moveComparison(event);
  });
  elements.compareView.addEventListener("pointermove", (event) => {
    if (elements.compareView.hasPointerCapture(event.pointerId) || (elements.compareHover.checked && event.pointerType === "mouse")) moveComparison(event);
  });
  elements.compareView.addEventListener("pointerup", (event) => {
    if (elements.compareView.hasPointerCapture(event.pointerId)) elements.compareView.releasePointerCapture(event.pointerId);
  });
  $("krea2-edit-compare-zoom-before").addEventListener("click", () => openImageViewer(elements.compareBeforeImage, "Avant"));
  $("krea2-edit-compare-zoom-after").addEventListener("click", () => openImageViewer(elements.compareAfterImage, "Après"));
  elements.buildPrompt.addEventListener("click", buildPrompt);
  elements.assistanceVersion.addEventListener("change", changeAssistanceVersion);
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
  elements.restart.addEventListener("click", restartStage);
  elements.resume.addEventListener("click", resumeStage);
  elements.version.addEventListener("change", () => openVersion(elements.version.value));
  elements.hide.addEventListener("click", () => updateState("hidden"));
  elements.instruction.addEventListener("input", render);
  elements.prompt.addEventListener("input", render);
  elements.model.addEventListener("change", render);
  elements.workflow.addEventListener("change", () => {
    render();
    setMessage("Workflow choisi pour le prochain rendu. Le prompt et les réglages affichés sont conservés.");
  });
  elements.workflowDefaults.addEventListener("click", applyWorkflowDefaults);
  elements.engine.addEventListener("change", switchEngine);
  elements.fireRedMode.addEventListener("change", changeFireRedMode);
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
  makeZoomable($("krea2-edit-scene-reference"), "Image 1 · décor");
  makeZoomable($("krea2-edit-subject-reference"), "Image 2 · sujet et action");
  makeZoomable(elements.resultImage, () => elements.resultCaption.textContent);
  elements.lightboxClose.addEventListener("click", () => elements.lightbox.close());
  elements.lightbox.addEventListener("click", (event) => {
    if (event.target === elements.lightbox) elements.lightbox.close();
  });

  window.PanelForgeKrea2Edit = {
    async openSourceId(sourceId) {
      if (state.busy || retouchEditor.saving) throw new Error("Attends la fin de l’opération en cours dans Edit, puis réessaie.");
      if (!state.initialized) await initialize();
      if (!state.initialized) throw new Error("L’atelier Edit n’a pas pu être chargé. Tu peux réessayer.");
      const payload = await request(`/api/image-lab/krea2-edit/sources/${encodeURIComponent(sourceId)}`);
      if (state.busy || retouchEditor.saving) throw new Error("L’atelier Edit est occupé. Réessaie après l’opération en cours.");
      window.PanelForgeLabNavigation?.switchView("krea2-edit-lab");
      openSource(sourceOf(payload), {hydrate: true});
      await loadSources({projectId: state.source.project_id});
      setMessage("Décor et sujet prêts. Ajuste l’instruction ou le prompt, puis lance un rendu quand tu le souhaites.");
    },
  };

  document.querySelectorAll('[data-image-lab-mode="krea2-edit-lab"]').forEach((button) => {
    button.addEventListener("click", () => {
      window.PanelForgeLabNavigation?.switchView("krea2-edit-lab");
      initialize();
    });
  });
})();
