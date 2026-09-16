(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
  const activeStatuses = new Set(["queued", "submitting", "running", "cancel_pending"]);
  const elements = {
    branches: $("krea2-assisted-branches"),
    branchTree: $("krea2-assisted-branch-tree"),
    activeBranch: $("krea2-assisted-active-branch"),
    feedbackCard: $("krea2-assisted-feedback-card"),
    feedbackImage: $("krea2-assisted-feedback-image"),
    feedbackName: $("krea2-assisted-feedback-name"),
    feedbackOpen: $("krea2-assisted-feedback-open"),
    inspirationCard: $("krea2-assisted-inspiration-card"),
    workspace: $("krea2-assisted-lab-workspace"),
    newForm: $("krea2-assisted-new-form"),
    newProject: $("krea2-assisted-new-project"),
    historyState: $("krea2-assisted-history-state"),
    name: $("krea2-assisted-name"),
    intention: $("krea2-assisted-intention"),
    reference: $("krea2-assisted-reference"),
    llm: $("krea2-assisted-llm"),
    assistanceRecipe: $("krea2-assisted-assistance-recipe"),
    activeRecipe: $("krea2-assisted-active-recipe"),
    newPreset: $("krea2-assisted-new-preset"),
    newPresetNote: $("krea2-assisted-new-preset-note"),
    preset: $("krea2-assisted-preset"),
    presetNote: $("krea2-assisted-preset-note"),
    presetImage: $("krea2-assisted-preset-image"),
    presetReapply: $("krea2-assisted-reapply-preset"),
    presetRemove: $("krea2-assisted-remove-preset"),
    presetDialog: $("krea2-assisted-preset-dialog"),
    presetForm: $("krea2-assisted-preset-form"),
    presetName: $("krea2-assisted-preset-name"),
    presetTarget: $("krea2-assisted-preset-target"),
    presetSource: $("krea2-assisted-preset-source"),
    presetError: $("krea2-assisted-preset-error"),
    presetSave: $("krea2-assisted-preset-save"),
    revisionLlm: $("krea2-assisted-revision-llm"),
    create: $("krea2-assisted-create"),
    newMessage: $("krea2-assisted-new-message"),
    refresh: $("krea2-assisted-refresh"),
    history: $("krea2-assisted-history"),
    historyEmpty: $("krea2-assisted-history-empty"),
    editor: $("krea2-assisted-editor"),
    title: $("krea2-assisted-title"),
    status: $("krea2-assisted-status"),
    warnings: $("krea2-assisted-warnings"),
    conversationLayout: $("krea2-assisted-conversation-layout"),
    conversation: $("krea2-assisted-conversation"),
    message: $("krea2-assisted-message"),
    guidanceFile: $("krea2-assisted-guidance-file"),
    guidancePreview: $("krea2-assisted-guidance-preview"),
    guidanceImage: $("krea2-assisted-guidance-image"),
    guidanceName: $("krea2-assisted-guidance-name"),
    guidanceRemove: $("krea2-assisted-guidance-remove"),
    guidanceDock: $("krea2-assisted-guidance-dock"),
    guidanceDockOpen: $("krea2-assisted-guidance-dock-open"),
    guidanceDockImage: $("krea2-assisted-guidance-dock-image"),
    guidanceDockName: $("krea2-assisted-guidance-dock-name"),
    guidanceDockKind: $("krea2-assisted-guidance-dock-kind"),
    guidanceDockNote: $("krea2-assisted-guidance-dock-note"),
    chat: $("krea2-assisted-chat"),
    recipeChat: $("krea2-assisted-recipe-chat"),
    showReasoning: $("krea2-assisted-show-reasoning"),
    promptLanguage: $("krea2-assisted-prompt-language"),
    reasoning: $("krea2-assisted-reasoning"),
    reasoningLabel: $("krea2-assisted-reasoning-label"),
    reasoningContent: $("krea2-assisted-reasoning-content"),
    reasoningEmpty: $("krea2-assisted-reasoning-empty"),
    prompt: $("krea2-assisted-prompt"),
    copyPrompt: $("krea2-assisted-copy-prompt"),
    model: $("krea2-assisted-model"),
    ratio: $("krea2-assisted-ratio"),
    megapixels: $("krea2-assisted-megapixels"),
    seed: $("krea2-assisted-seed"),
    workflow: $("krea2-assisted-workflow"),
    workflowSummary: $("krea2-assisted-workflow-summary"),
    samplingFirstNote: $("krea2-assisted-first-note"),
    samplingSecondNote: $("krea2-assisted-second-note"),
    samplingPreset: $("krea2-assisted-sampling-preset"),
    samplingSummary: $("krea2-assisted-sampling-summary"),
    samplingDetails: $("krea2-assisted-sampling-details"),
    loras: $("krea2-assisted-loras"),
    catalogManager: $("krea2-assisted-catalog-manager"),
    render: $("krea2-assisted-render"),
    cancel: $("krea2-assisted-cancel"),
    queueSummary: $("krea2-assisted-queue-summary"),
    queueOpen: $("krea2-assisted-queue-open"),
    messageState: $("krea2-assisted-message-state"),
    recipePanel: $("krea2-assisted-recipe-panel"),
    recipeDraft: $("krea2-assisted-recipe-draft"),
    saveDraft: $("krea2-assisted-save-draft"),
    publishRecipe: $("krea2-assisted-publish-recipe"),
    recipeMessage: $("krea2-assisted-recipe-message"),
    gallery: $("krea2-assisted-gallery"),
    lightbox: $("krea2-assisted-lightbox"),
    lightboxTitle: $("krea2-assisted-lightbox-title"),
    lightboxImage: $("krea2-assisted-lightbox-image"),
    lightboxClose: $("krea2-assisted-lightbox-close"),
  };
  if (!elements.workspace) return;

  const samplingPasses = ["first", "second"].map(stage => ({
    steps: $(`krea2-assisted-${stage}-steps`),
    sampler: $(`krea2-assisted-${stage}-sampler`),
    scheduler: $(`krea2-assisted-${stage}-scheduler`),
  }));
  let samplingVersion = "1.0.0";
  let samplingCatalogSignature = null;
  let activeWorkflowId = "krea2-sampling@1.0.0";
  const workflowSamplingDrafts = new Map();

  function defaultSampling() {
    return { preset_id: "current", version: "1.0.0",
      first_pass: { steps: 8, sampler: "er_sde", scheduler: "simple" },
      second_pass: { steps: 2, sampler: "er_sde", scheduler: "simple" } };
  }

  function readSampling() {
    const passes = samplingPasses.map(row => ({
      steps: Number(row.steps.value), sampler: row.sampler.value, scheduler: row.scheduler.value,
    }));
    return { preset_id: elements.samplingPreset.value, version: samplingVersion,
      first_pass: passes[0], second_pass: passes[1] };
  }

  function samplingSummary(value) {
    const config = value || defaultSampling();
    const first = config.first_pass, second = config.second_pass;
    return `${first.steps || "—"} + ${second.steps || "—"} steps · ${first.sampler} / ${first.scheduler}`
      + (first.sampler === second.sampler && first.scheduler === second.scheduler
        ? "" : ` → ${second.sampler} / ${second.scheduler}`);
  }

  function updateSamplingSummary() {
    const value = readSampling();
    elements.samplingSummary.textContent = samplingSummary(value)
      + (value.preset_id === "moody_beta" ? " · adaptation Moody à tester" : "");
  }

  function loadSampling(value) {
    const config = value || defaultSampling();
    samplingVersion = config.version;
    ensureMissingOption(elements.samplingPreset, config.preset_id);
    elements.samplingPreset.value = config.preset_id;
    [config.first_pass, config.second_pass].forEach((pass, index) => {
      const row = samplingPasses[index];
      row.steps.value = String(pass.steps);
      for (const field of ["sampler", "scheduler"]) {
        ensureMissingOption(row[field], pass[field]);
        row[field].value = pass[field];
      }
    });
    updateSamplingSummary();
  }

  function configureSampling(spec) {
    if (!spec) return;
    const signature = JSON.stringify(spec);
    if (signature === samplingCatalogSignature) return;
    const selected = readSampling();
    elements.samplingPreset.replaceChildren();
    for (const preset of spec.presets) {
      const option = document.createElement("option");
      option.value = preset.id; option.textContent = preset.label;
      elements.samplingPreset.append(option);
    }
    const custom = document.createElement("option");
    custom.value = "custom"; custom.textContent = "Personnalisé"; custom.disabled = true;
    elements.samplingPreset.append(custom);
    for (const row of samplingPasses) {
      for (const [field, choices] of [["sampler", spec.samplers], ["scheduler", spec.schedulers]]) {
        row[field].replaceChildren();
        for (const name of choices) {
          const option = document.createElement("option");
          option.value = name; option.textContent = name; row[field].append(option);
        }
      }
    }
    // Catalogue refreshes must preserve drafts, including incomplete step inputs.
    const rawSteps = samplingPasses.map(row => row.steps.value);
    loadSampling(selected);
    samplingPasses.forEach((row, index) => { row.steps.value = rawSteps[index]; });
    updateSamplingSummary();
    samplingCatalogSignature = signature;
  }

  function workflowSpec(id = elements.workflow.value) {
    return (state.spec?.workflows || []).find(item => item.id === id);
  }

  function updateWorkflowSummary() {
    const selected = workflowSpec();
    const flux = selected?.recipe_id === "krea2-flux-klein";
    elements.workflowSummary.textContent = (selected?.description || "Famille de workflow historique.")
      + (flux ? " Le sélecteur MP fixe la taille finale ; KREA2 est dimensionné automatiquement." : "");
    elements.samplingFirstNote.textContent = flux ? "CFG 1,0 · denoise 1,00" : "CFG 1,1 · denoise 1,00";
    elements.samplingSecondNote.textContent = flux ? "CFG 1,0 · denoise 0,39 · Flux fixe : 5 steps" : "CFG 1,0 · denoise 0,30";
  }

  function loadWorkflow(value) {
    const workflowId = value || "krea2-sampling@1.0.0";
    ensureMissingOption(elements.workflow, workflowId);
    elements.workflow.value = workflowId;
    activeWorkflowId = workflowId;
    updateWorkflowSummary();
  }

  function configureWorkflows(workflows) {
    if (!Array.isArray(workflows) || !workflows.length) return;
    const selected = elements.workflow.value || activeWorkflowId;
    elements.workflow.replaceChildren();
    for (const workflow of workflows) {
      const option = document.createElement("option");
      option.value = workflow.id; option.textContent = workflow.label;
      elements.workflow.append(option);
    }
    loadWorkflow(workflows.some(item => item.id === selected) ? selected : workflows[0].id);
  }

  function validateSamplingInputs() {
    const invalid = samplingPasses.find(row => !row.steps.checkValidity());
    if (!invalid) return true;
    elements.samplingDetails.open = true;
    invalid.steps.reportValidity(); invalid.steps.focus();
    return false;
  }

  elements.samplingPreset.addEventListener("change", () => {
    const preset = state.spec?.sampling?.presets.find(item => item.id === elements.samplingPreset.value);
    if (preset) loadSampling(preset.settings);
  });
  elements.workflow.addEventListener("change", () => {
    workflowSamplingDrafts.set(activeWorkflowId, readSampling());
    activeWorkflowId = elements.workflow.value;
    const saved = workflowSamplingDrafts.get(activeWorkflowId);
    const selected = workflowSpec(activeWorkflowId);
    const preset = state.spec?.sampling?.presets.find(
      item => item.id === selected?.default_sampling_preset_id,
    );
    loadSampling(saved || preset?.settings || defaultSampling());
    updateWorkflowSummary();
  });
  for (const row of samplingPasses) {
    for (const [field, control] of Object.entries(row)) {
      control.addEventListener(field === "steps" ? "input" : "change", () => {
        ensureMissingOption(elements.samplingPreset, "custom");
        elements.samplingPreset.value = "custom";
        updateSamplingSummary();
      });
    }
  }

  const resourceUi = window.PanelForgeKrea2ResourceUi;
  const core = window.PanelForgeLabCore;
  const state = {
    initialized: false,
    initializing: null,
    catalogSignature: null,
    projectRequest: null,
    spec: null,
    projects: [],
    project: null,
    loraSlots: [],
    busy: false,
    pollTimer: null,
    draftSnapshot: "",
    guidanceFile: null,
    guidanceAsset: null,
    guidanceObjectUrl: null,
    navigationSerial: 0,
    presets: [],
    presetSource: null,
    renderQueue: { items: [], error: null },
  };
  const reasoningTrace = core && typeof core.createReasoningTrace === "function"
    ? core.createReasoningTrace({
      toggle: elements.showReasoning,
      panel: elements.reasoning,
      label: elements.reasoningLabel,
      output: elements.reasoningContent,
      empty: elements.reasoningEmpty,
    })
    : Object.freeze({ begin: () => {}, handle: () => {}, finish: () => {}, reset: () => {}, streamUrl: (url) => url });

  const restagingEditor = window.PanelForgeAssistedRestaging.create({
    request, getProject: () => state.project,
    getInstruction: () => state.spec?.restaging?.default_instruction || "",
    onPrepared: async source => {
      await window.PanelForgeKrea2Edit.openSourceId(source.source_id);
    },
  });

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
    }
    return payload;
  }

  function setBusy(value) {
    state.busy = value;
    const samplingDisabled = value || !state.spec?.sampling;
    elements.workflow.disabled = value || !(state.spec?.workflows || []).length;
    elements.samplingPreset.disabled = samplingDisabled;
    samplingPasses.forEach(row => Object.values(row).forEach(control => { control.disabled = samplingDisabled; }));
    if (state.spec && !state.spec.sampling) {
      elements.samplingSummary.textContent = "Réglages actuels · redémarrez le Lab pour activer les presets.";
    }
    const llmReady = Boolean(state.spec?.llm_models?.length);
    const modelsReady = Boolean(state.spec?.render_models?.some(m => m.comfy_name === elements.model.value));
    const lorasReady = state.loraSlots.every(slot => !slot.name || state.spec?.loras?.some(lora => lora.comfy_name === slot.name));
    elements.create.disabled = value || !llmReady;
    elements.chat.disabled = value || !state.project || !llmReady;
    elements.recipeChat.disabled = value || !state.project || !llmReady;
    elements.revisionLlm.disabled = value || !state.project;
    window.PanelForgeModelPicker.setDisabled(elements.revisionLlm, value || !state.project);
    elements.promptLanguage.disabled = value || !state.project;
    elements.guidanceFile.disabled = value || !state.project;
    elements.guidanceRemove.disabled = value || !state.project;
    elements.render.disabled = value || !state.project || !modelsReady || !lorasReady;
    elements.saveDraft.disabled = value || !state.project;
    elements.publishRecipe.disabled = value || !state.project;
    elements.branchTree.querySelectorAll("button").forEach((button) => { button.disabled = value; });
    elements.newPreset.disabled = value;
    elements.preset.disabled = value || !state.project;
    elements.presetReapply.disabled = value || !state.project?.style_preset;
    elements.presetRemove.disabled = value || !state.project?.style_preset;
    elements.presetSave.disabled = value;
    elements.gallery.querySelectorAll("button").forEach((button) => { button.disabled = value; });
    renderStatus();
    if (!value && state.project && ((state.renderQueue.items || []).length
      || (state.project.attempts || []).some((attempt) => activeStatuses.has(attempt.status)))) schedulePoll();
  }

  function setNewMessage(message = "", error = true) {
    elements.newMessage.textContent = message;
    elements.newMessage.hidden = !message;
    elements.newMessage.classList.toggle("error", error);
    elements.newMessage.classList.toggle("message", !error);
  }

  function setMessage(message = "", error = false) {
    elements.messageState.textContent = message;
    elements.messageState.classList.toggle("error", error);
  }

  function preferredRenderModel(models) {
    return models.find((item) => /krea2gptgrandpussytruth/i.test(item.comfy_name))
      || models.find((item) => /krea2_turbo_bf16/i.test(item.comfy_name))
      || models[0]
      || null;
  }

  function fillOptions() {
    const previousLlm = elements.llm.value;
    window.PanelForgeModelPicker.populate(
      elements.llm,
      state.spec.llm_models || [],
      previousLlm,
    );
    if (previousLlm) window.PanelForgeModelPicker.select(elements.llm, previousLlm, "modèle indisponible");
    const previousRevisionLlm = elements.revisionLlm.value;
    window.PanelForgeModelPicker.populate(
      elements.revisionLlm,
      state.spec.llm_models || [],
      previousRevisionLlm,
    );
    if (previousRevisionLlm) window.PanelForgeModelPicker.select(elements.revisionLlm, previousRevisionLlm, "modèle indisponible");

    const previousModel = elements.model.value;
    resourceUi.renderModelPicker(elements.model, {
      resources: state.spec.render_models || [],
      updatePreference,
      refreshResource,
    });
    const renderDefault = preferredRenderModel(state.spec.render_models || []);
    elements.model.value = previousModel && [...elements.model.options].some((option) => option.value === previousModel)
      ? previousModel
      : (renderDefault ? renderDefault.comfy_name : "");
    resourceUi.syncModelPicker(elements.model);

    const previousRatio = elements.ratio.value;
    elements.ratio.replaceChildren();
    (state.spec.aspect_ratios || []).forEach((ratio) => {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio;
      elements.ratio.append(option);
    });
    elements.ratio.value = previousRatio || state.spec.defaults.aspect_ratio;
    if (!elements.megapixels.value) elements.megapixels.value = String(state.spec.defaults.megapixels);
    renderLoraStack();
    renderCatalogManager();
  }

  function ensureMissingOption(select, value) {
    if (!value || [...select.options].some((option) => option.value === value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${value} · absent`;
    select.prepend(option);
  }

  function renderLoraStack() {
    resourceUi.renderLoraStack(elements.loras, {
      resources: state.spec ? state.spec.loras || [] : [],
      selections: state.loraSlots,
      maximum: 10,
      minimumStrength: -20,
      maximumStrength: 20,
      updatePreference,
      refreshResource,
      onChange: (values) => {
        state.loraSlots = values;
        renderLoraStack();
        setBusy(state.busy);
      },
    });
  }

  async function updatePreference(resource, values) {
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadSpec(true);
      return updated;
    } catch (error) { setMessage(error.message, true); return false; }
  }

  async function refreshResource(resource) {
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/refresh`, { method: "POST" });
      await loadSpec(true);
      setMessage("Informations CivitAI actualisées.");
      return updated;
    } catch (error) {
      setMessage(`Recherche CivitAI indisponible : ${error.message}`, true);
      throw error;
    }
  }

  function renderCatalogManager() {
    resourceUi.renderCatalogManager(elements.catalogManager, {
      models: state.spec ? state.spec.render_models || [] : [],
      loras: state.spec ? state.spec.loras || [] : [],
      updatePreference,
      refreshResource,
    });
  }

  function selectedLoras() {
    return state.loraSlots
      .filter((slot) => slot.name)
      .map((slot) => ({ name: slot.name, strength: Number(slot.strength) || 0 }));
  }

  function resourceFilename(value) {
    const normalized = String(value || "").replaceAll("\\", "/");
    return (normalized.split("/").at(-1) || normalized).replace(/\.(safetensors|ckpt|pt)$/i, "");
  }

  function compactResourceName(value, maximum = 30) {
    const label = resourceFilename(value);
    return label.length > maximum ? `${label.slice(0, maximum - 1)}…` : label;
  }

  function strengthLabel(value) {
    const number = Number(value);
    return Number.isFinite(number)
      ? number.toLocaleString("fr-FR", { maximumFractionDigits: 3 })
      : String(value);
  }

  function loadAttemptSettings(attempt) {
    if (!attempt) return;
    loadWorkflow(attempt.settings.workflow);
    loadSampling(attempt.settings.sampling);
    elements.prompt.value = attempt.prompt;
    elements.model.value = attempt.settings.model_id;
    ensureMissingOption(elements.model, attempt.settings.model_id);
    elements.model.value = attempt.settings.model_id;
    resourceUi.syncModelPicker(elements.model);
    ensureMissingOption(elements.ratio, attempt.settings.aspect_ratio);
    elements.ratio.value = attempt.settings.aspect_ratio;
    elements.megapixels.value = String(attempt.settings.megapixels);
    elements.seed.value = attempt.seed ?? "";
    state.loraSlots = (attempt.settings.loras || []).slice(0, 10).map((value) => ({
      name: value.name,
      strength: value.strength,
    }));
    renderLoraStack();
  }

  function draftText(draft) {
    return draft ? JSON.stringify(draft, null, 2) : "";
  }

  function renderStatus() {
    const project = state.project;
    const active = project && (project.attempts || []).find((attempt) => activeStatuses.has(attempt.status));
    elements.status.textContent = state.busy ? "● Traitement…" : active ? `● ${attemptStatus(active)}` : "● Prêt";
    elements.cancel.disabled = !active || state.busy;
    const items = state.renderQueue.items || [];
    const queued = items.filter((item) => item.status === "queued").length;
    const running = items.find((item) => item.status !== "queued");
    elements.render.textContent = items.length ? "Ajouter un rendu à la file" : "Lancer un rendu";
    elements.cancel.textContent = active ? `Annuler l’essai ${active.index}` : "Annuler";
    const error = state.renderQueue.error || running?.error;
    elements.queueSummary.textContent = error ? `${running ? `${running.project_name}, essai ${running.index} · ` : ""}${error}` : (items.length
      ? `File Assisted · ${queued} en attente${running ? ` · ${running.project_name}, essai ${running.index} : ${attemptStatus(running)}` : ""}`
      : "Chaque clic conserve ses réglages. Les rendus passent l’un après l’autre.");
    elements.queueSummary.classList.toggle("error", Boolean(error));
    elements.queueOpen.hidden = !running || running.project_id === project?.project_id;
    elements.queueOpen.disabled = state.busy;
  }

  function attemptStatus(attempt) {
    const labels = { created: "Préparé · non lancé", queued: "En attente", submitting: "Envoi à ComfyUI",
      running: "En cours", cancel_pending: "Annulation en attente", succeeded: "Terminé", failed: "Échec", cancelled: "Annulé" };
    const item = (state.renderQueue.items || []).find((value) =>
      value.project_id === state.project?.project_id && value.attempt_id === attempt.attempt_id);
    return attempt.status === "queued" && item
      ? `En attente · position ${item.position}` : labels[attempt.status] || attempt.status;
  }

  async function loadRenderQueue() {
    state.renderQueue = await request("/api/image-lab/krea2-assisted/render-queue");
  }

  function clearGuidance() {
    if (state.guidanceObjectUrl) URL.revokeObjectURL(state.guidanceObjectUrl);
    state.guidanceFile = null;
    state.guidanceAsset = null;
    state.guidanceObjectUrl = null;
    elements.guidanceFile.value = "";
    renderGuidanceCompose();
  }

  function selectedFeedbackPreview() {
    const project = state.project;
    if (!project?.feedback_attempt_id) return null;
    const attempt = (project.attempts || []).find(
      (value) => value.attempt_id === project.feedback_attempt_id && value.output_url,
    );
    if (!attempt) return null;
    return {
      source: attempt.output_url,
      name: attempt.label || `Essai ${attempt.index}`,
      kind: "FEEDBACK VISUEL",
      note: "Prochain échange",
    };
  }

  function currentConversationPreview() {
    const guidance = state.guidanceAsset;
    const source = state.guidanceObjectUrl || (guidance && guidance.url);
    if (source) {
      return {
        source,
        name: state.guidanceFile?.name || guidance?.filename || "Image d’appoint",
        kind: "Image d’inspiration",
        note: "Prochain échange",
      };
    }
    return null;
  }

  function renderGuidanceCompose() {
    const guidance = state.guidanceAsset;
    const source = state.guidanceObjectUrl || (guidance && guidance.url);
    const name = state.guidanceFile?.name || guidance?.filename || "";
    const conversationPreview = currentConversationPreview();
    const feedback = selectedFeedbackPreview();
    elements.guidancePreview.hidden = !source;
    elements.guidanceDock.hidden = !conversationPreview && !feedback;
    elements.inspirationCard.hidden = !conversationPreview;
    elements.feedbackCard.hidden = !feedback;
    elements.conversationLayout.classList.toggle("has-guidance", Boolean(conversationPreview || feedback));
    if (feedback) {
      elements.feedbackImage.src = feedback.source;
      elements.feedbackName.textContent = feedback.name;
    } else {
      elements.feedbackImage.removeAttribute("src");
      elements.feedbackName.textContent = "";
    }
    if (source) {
      elements.guidanceImage.src = source;
      elements.guidanceName.textContent = name;
      elements.guidanceName.title = name;
    } else {
      elements.guidanceImage.removeAttribute("src");
      elements.guidanceName.textContent = "";
    }
    if (conversationPreview) {
      elements.guidanceDockImage.src = conversationPreview.source;
      elements.guidanceDockName.textContent = conversationPreview.name;
      elements.guidanceDockName.title = conversationPreview.name;
      elements.guidanceDockKind.textContent = conversationPreview.kind;
      elements.guidanceDockNote.textContent = conversationPreview.note;
    } else {
      elements.guidanceDockImage.removeAttribute("src");
      elements.guidanceDockName.textContent = "";
      elements.guidanceDockKind.textContent = "";
      elements.guidanceDockNote.textContent = "";
    }
  }

  function openCurrentGuidance() {
    const preview = currentConversationPreview();
    if (preview) openLightbox(preview.source, preview.name);
  }

  function selectGuidanceFile() {
    const file = elements.guidanceFile.files[0];
    if (!file) return;
    if (state.guidanceObjectUrl) URL.revokeObjectURL(state.guidanceObjectUrl);
    state.guidanceFile = file;
    state.guidanceAsset = null;
    state.guidanceObjectUrl = URL.createObjectURL(file);
    renderGuidanceCompose();
  }

  function reuseGuidance(turn) {
    if (state.busy || !turn.guidance_asset_id || !turn.guidance_url) return;
    clearGuidance();
    state.guidanceAsset = {
      asset_id: turn.guidance_asset_id,
      filename: turn.guidance_filename || "guidance-image",
      url: turn.guidance_url,
    };
    renderGuidanceCompose();
    elements.message.focus();
  }

  async function resolveGuidance() {
    if (state.guidanceAsset) return state.guidanceAsset;
    if (!state.guidanceFile) return null;
    const data = new FormData();
    data.set("image", state.guidanceFile);
    const payload = await request(
      `/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/guidance-images`,
      { method: "POST", body: data },
    );
    return payload.guidance;
  }

  function renderConversation() {
    elements.conversation.replaceChildren();
    const turns = state.project ? state.project.turns || [] : [];
    if (!turns.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Le premier échange apparaîtra ici.";
      elements.conversation.append(empty);
      return;
    }
    turns.forEach((turn) => {
      const article = document.createElement("article");
      article.className = `krea2-assisted-turn ${turn.role} ${turn.mode}`;
      const label = document.createElement("small");
      label.textContent = `${turn.role === "user" ? "Vous" : "Assistant"} · ${turn.mode === "recipe" ? "recette" : "création"}`;
      if (turn.model_id) {
        label.textContent += ` · ${turn.model_id.replace(/^[^:]+::/, "")}`;
      }
      const content = document.createElement("p");
      content.textContent = turn.content;
      article.append(label, content);
      if (turn.style_preset) {
        const presetNote = document.createElement("small");
        presetNote.textContent = `Exemple de style transmis : ${turn.style_preset.name}`;
        article.append(presetNote);
      }
      if (turn.guidance_url) {
        const guidance = document.createElement("div");
        guidance.className = "krea2-assisted-turn-guidance";
        const image = document.createElement("img");
        image.src = turn.guidance_url;
        image.alt = turn.guidance_filename || "Image d’appoint";
        image.loading = "lazy";
        image.addEventListener("click", () => openLightbox(turn.guidance_url, image.alt));
        const copy = document.createElement("span");
        const name = document.createElement("b");
        name.textContent = turn.guidance_filename || "Image d’appoint";
        const note = document.createElement("small");
        note.textContent = "Image d’appoint de cet échange";
        copy.append(name, note);
        const reuse = document.createElement("button");
        reuse.type = "button";
        reuse.textContent = "Réutiliser";
        reuse.addEventListener("click", () => reuseGuidance(turn));
        guidance.append(image, copy, reuse);
        article.append(guidance);
      }
      if (turn.questions && turn.questions.length) {
        const list = document.createElement("ol");
        turn.questions.forEach((question) => { const item = document.createElement("li"); item.textContent = question; list.append(item); });
        article.append(list);
      }
      if (turn.recommendations && turn.recommendations.length) {
        const notes = document.createElement("small");
        notes.textContent = turn.recommendations.join(" · ");
        article.append(notes);
      }
      elements.conversation.append(article);
    });
    elements.conversation.scrollTop = elements.conversation.scrollHeight;
  }

  function openLightbox(url, title) {
    elements.lightboxTitle.textContent = title;
    elements.lightboxImage.src = url;
    elements.lightboxImage.alt = title;
    elements.lightbox.showModal();
  }

  function imageFigure(url, caption, className = "") {
    const figure = document.createElement("figure");
    figure.className = className;
    const figcaption = document.createElement("figcaption");
    figcaption.textContent = caption;
    const image = document.createElement("img");
    image.src = url;
    image.alt = caption;
    image.loading = "lazy";
    image.tabIndex = 0;
    image.addEventListener("click", () => openLightbox(url, caption));
    image.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openLightbox(url, caption); }
    });
    figure.append(figcaption, image);
    return figure;
  }

  window.addEventListener("panelforge:dlss-complete", async event => {
    const job = event.detail, project = state.project;
    if (job.snapshot.owner !== "assisted" || project?.project_id !== job.snapshot.owner_id) return;
    if (state.busy) { setTimeout(() => window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: job })), 1000); return; }
    try {
      const data = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(project.project_id)}`);
      if (state.project === project) renderProject(data.project, { preservePrompt: true });
    } catch (error) { setMessage(error.message, true); }
  });

  const galleryCards = new Map();
  let galleryProjectId = null;
  let galleryReference = null;

  function renderGallery() {
    const project = state.project;
    if (galleryProjectId !== project?.project_id) {
      elements.gallery.replaceChildren();
      galleryCards.clear();
      galleryReference = null;
      galleryProjectId = project?.project_id;
    }
    if (!project) return;
    const visible = [];
    const keys = new Set();
    if (project.reference_url) {
      const url = `${project.reference_url}?v=${encodeURIComponent(project.reference_asset_id)}`;
      if (galleryReference?.url !== url) galleryReference = {
        url, card: imageFigure(url, "Référence LLM · non envoyée à ComfyUI", "reference"),
      };
      visible.push(galleryReference.card);
    }
    const groups = window.PanelForgeDlss?.groups(project.attempts || [], `assisted:${project.project_id}`, project.feedback_attempt_id)
      || (project.attempts || []).map(attempt => ({ attempt }));
    [...groups].reverse().forEach(group => {
      const attempt = group.attempt;
      const key = group.root?.attempt_id || attempt.attempt_id;
      keys.add(key);
      const originName = (project.branches || []).length > 1
        ? project.branches.find(b => b.branch_id === (attempt.conversation_branch_id || "main"))?.name || "Ancien essai" : null;
      const signature = JSON.stringify([attempt, project.feedback_attempt_id === attempt.attempt_id,
        originName, attemptStatus(attempt), group.variants, Boolean(state.spec?.restaging?.enabled)]);
      const previous = galleryCards.get(key);
      if (previous?.signature === signature) {
        visible.push(previous.card);
        return;
      }
      const card = document.createElement("article");
      card.dataset.attemptId = attempt.attempt_id;
      if (group.variants) card.append(window.PanelForgeDlss.picker(group, renderGallery));
      card.className = `krea2-assisted-attempt ${attempt.accepted ? "accepted" : ""} ${project.feedback_attempt_id === attempt.attempt_id ? "feedback" : ""}`;
      if (attempt.output_url) {
        const url = `${attempt.output_url}?v=${encodeURIComponent(attempt.output_asset_id)}`;
        const figure = previous?.card.querySelector("figure");
        card.append(figure?.querySelector("img")?.getAttribute("src") === url
          ? figure : imageFigure(url, attempt.label || `Essai ${attempt.index}`));
      } else {
        const pending = document.createElement("div");
        pending.className = "krea2-assisted-attempt-placeholder";
        pending.textContent = `Essai ${attempt.index} · ${attemptStatus(attempt)}`;
        card.append(pending);
      }
      if (attempt.pre_flux_url) {
        const intermediate = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "Image KREA2 avant Flux";
        const download = document.createElement("a");
        download.href = attempt.pre_flux_url;
        download.download = `krea2-assisted-${attempt.attempt_id}-pre-flux.png`;
        download.textContent = "Télécharger l’image pré-Flux";
        intermediate.append(summary, imageFigure(
          `${attempt.pre_flux_url}?v=${encodeURIComponent(attempt.pre_flux_asset_id)}`,
          `Essai ${attempt.index} · avant Flux Klein`,
        ), download);
        card.append(intermediate);
      }
      const settings = attempt.settings || {};
      const resolution = settings.resolution || {};
      const resolutionLabel = resolution.width && resolution.height
        ? `${resolution.width}×${resolution.height}`
        : settings.aspect_ratio.split(" ")[0];
      const renderMeta = document.createElement("small");
      const finalMp = workflowSpec(settings.workflow)?.recipe_id === "krea2-flux-klein";
      renderMeta.textContent = attempt.dlss ? `DLSS · ${attempt.dlss.width}×${attempt.dlss.height} · réglages de génération hérités` : attempt.composition
        ? `Composition locale · ${attempt.output_dimensions.width}×${attempt.output_dimensions.height} · taille de la base`
        : `${workflowSpec(settings.workflow)?.label || "KREA2"} · ${compactResourceName(settings.model_id)} · ${resolutionLabel} · ${settings.megapixels} MP${finalMp ? " final" : ""}`;
      renderMeta.title = `${attempt.composition ? "Génération d’origine\n" : ""}Checkpoint : ${settings.model_id}\nRésolution : ${resolutionLabel} · ${settings.aspect_ratio} · ${settings.megapixels} MP`;
      renderMeta.title += `\nSampling : ${samplingSummary(settings.sampling)}`;
      const loras = settings.loras || [];
      const loraSummary = loras.length
        ? loras.map((lora) => `${compactResourceName(lora.name, 22)} ×${strengthLabel(lora.strength)}`).join(" · ")
        : "aucune";
      const loraMeta = document.createElement("small");
      loraMeta.textContent = `${attempt.composition ? "LoRA de la génération d’origine" : "LoRA"} · ${loraSummary}`;
      loraMeta.title = loras.length
        ? loras.map((lora) => `${lora.name} ×${strengthLabel(lora.strength)}`).join("\n")
        : "Aucune LoRA utilisée";
      const runMeta = document.createElement("small");
      runMeta.textContent = `${attemptStatus(attempt)} · ${settings.aspect_ratio.split(" ")[0]} · ${attempt.composition ? "seed d’origine" : "seed"} ${attempt.seed}`;
      card.append(renderMeta, loraMeta, runMeta);
      if (attempt.error) {
        const error = document.createElement("small");
        error.className = "error";
        error.textContent = attempt.error;
        card.append(error);
      }
      (attempt.output_warnings || []).forEach(message => {
        const warning = document.createElement("small");
        warning.className = "muted"; warning.textContent = message; card.append(warning);
      });
      if (originName) {
        const origin = document.createElement("small");
        origin.textContent = originName;
        card.append(origin);
      }
      const actions = document.createElement("div");
      actions.className = "actions";
      const reuse = document.createElement("button");
      reuse.type = "button";
      reuse.textContent = "Reprendre réglages";
      reuse.title = "Reprendre le prompt et les réglages de cet essai";
      reuse.addEventListener("click", () => loadAttemptSettings(attempt));
      actions.append(reuse);
      if (attempt.status === "created") {
        const start = document.createElement("button");
        start.type = "button";
        start.textContent = "Ajouter cet essai à la file";
        start.addEventListener("click", () => startPreparedAttempt(attempt.attempt_id));
        actions.append(start);
      }
      if (activeStatuses.has(attempt.status) || attempt.status === "created") {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.textContent = attempt.status === "submitting" ? "Retirer de la file" : "Annuler cet essai";
        cancel.addEventListener("click", () => cancelAttempt(attempt.attempt_id));
        actions.append(cancel);
      }
      if (attempt.status === "succeeded") {
        const feedbackSelected = project.feedback_attempt_id === attempt.attempt_id;
        const feedback = document.createElement("button");
        feedback.type = "button";
        feedback.textContent = feedbackSelected ? "Feedback ✓" : "Feedback";
        feedback.title = feedbackSelected ? "Retirer ce feedback" : "Utiliser comme feedback visuel";
        feedback.setAttribute("aria-pressed", String(feedbackSelected));
        feedback.addEventListener("click", () => selectFeedback(feedbackSelected ? null : attempt.attempt_id));
        const save = document.createElement("button");
        save.type = "button";
        save.textContent = attempt.accepted ? "Enregistrée ✓" : "Enregistrer";
        save.title = attempt.accepted ? "Image déjà enregistrée" : "Enregistrer cette image";
        save.addEventListener("click", () => saveImage(attempt.attempt_id));
        actions.append(feedback, save);
        if (window.PanelForgeDlss) actions.append(window.PanelForgeDlss.button({ owner: "assisted", ownerId: project.project_id, attempt }));
        if (window.PanelForgeDlss?.comparisonButton) actions.append(window.PanelForgeDlss.comparisonButton({ owner: "assisted", ownerId: project.project_id, attempt }));
        if (state.spec?.restaging?.enabled) {
          const compose = document.createElement("button");
          compose.type = "button";
          compose.textContent = "Replacer dans un décor";
          compose.addEventListener("click", () => restagingEditor.open(state.project, attempt));
          actions.append(compose);
        }
        const preset = document.createElement("button");
        preset.type = "button";
        preset.textContent = "Créer un preset";
        preset.addEventListener("click", () => openPresetDialog(attempt));
        actions.append(preset);
        const restart = document.createElement("button");
        restart.type = "button";
        restart.className = "krea2-assisted-restart";
        restart.textContent = attempt.can_restore_conversation ? "Repartir d’ici" : "Nouvelle piste · image + prompt";
        restart.title = attempt.can_restore_conversation
          ? "Créer une branche avec la conversation, le prompt et les réglages au moment de cet essai"
          : "Ancien essai : point de conversation inconnu. Ouvrir une piste sans les anciens échanges, avec cette image et son prompt.";
        restart.addEventListener("click", () => changeBranch({
          attempt_id: attempt.attempt_id, image_prompt_only: !attempt.can_restore_conversation,
        }));
        actions.append(restart);
      }
      actions.querySelectorAll("button").forEach((button) => { button.disabled = state.busy; });
      card.append(actions);
      galleryCards.set(key, { signature, card });
      visible.push(card);
    });
    for (const key of galleryCards.keys()) if (!keys.has(key)) galleryCards.delete(key);
    if (!visible.length) {
      const empty = elements.gallery.querySelector("p.muted") || document.createElement("p");
      empty.className = "muted"; empty.textContent = "Aucune image."; visible.push(empty);
    }
    const retained = new Set(visible);
    for (const child of [...elements.gallery.children]) if (!retained.has(child)) child.remove();
    visible.forEach((card, index) => {
      // Leave existing images connected: reinserting lazy images causes blank frames while polling.
      if (elements.gallery.children[index] !== card) elements.gallery.insertBefore(card, elements.gallery.children[index] || null);
    });
  }

  function renderProject(project, { preservePrompt = false } = {}) {
    window.PanelForgeLabCore?.observeRenderAttempts?.((project.attempts || []).filter(a => a.kind !== "composition"), `assisted:${project.project_id}`);
    const previous = state.project;
    const changed = state.project?.project_id !== project.project_id
      || state.project?.active_branch_id !== project.active_branch_id;
    if (changed) restagingEditor.close();
    state.project = project;
    elements.editor.hidden = false;
    elements.title.textContent = project.name;
    const recipeVersion = project.assistance_recipe_version || "1.0.0";
    const recipe = (state.spec?.assistance_recipes || []).find((item) => item.version === recipeVersion);
    elements.activeRecipe.textContent = `Assistance : ${recipe?.label || recipeVersion} · liée au projet`;
    elements.activeRecipe.title = `Recette d’assistance ${recipeVersion}`;
    elements.promptLanguage.value = project.prompt_language || "en";
    if (changed) {
      workflowSamplingDrafts.clear();
      activeWorkflowId = "krea2-sampling@1.0.0";
      clearGuidance();
      elements.message.value = "";
      reasoningTrace.reset();
      window.PanelForgeModelPicker.select(
        elements.revisionLlm,
        project.revision_model_id || project.model_id,
        "modèle historique indisponible",
      );
    }
    if (changed) restoreRenderState(project);
    if (changed || !preservePrompt || !elements.prompt.value.trim()) elements.prompt.value = project.current_prompt || "";
    elements.warnings.replaceChildren();
    (project.warnings || []).forEach((warning) => { const item = document.createElement("p"); item.textContent = warning; elements.warnings.append(item); });
    elements.warnings.hidden = !(project.warnings || []).length;
    if (changed || JSON.stringify(previous?.turns) !== JSON.stringify(project.turns)) renderConversation();
    if (changed || JSON.stringify(previous?.branches) !== JSON.stringify(project.branches)) renderBranches();
    if (changed || previous?.preset_pending !== project.preset_pending
      || JSON.stringify(previous?.style_preset) !== JSON.stringify(project.style_preset)) renderPresetSelection();
    const serialized = draftText(project.recipe_draft);
    if (changed || !elements.recipeDraft.value.trim() || elements.recipeDraft.value === state.draftSnapshot || serialized !== state.draftSnapshot) {
      elements.recipeDraft.value = serialized;
      state.draftSnapshot = serialized;
    }
    if (project.recipe_draft) elements.recipePanel.open = true;
    else if (changed) elements.recipePanel.open = false;
    if (project.published_recipe) {
      elements.recipeMessage.textContent = `Recette publiée : ${project.published_recipe.recipe_id}@${project.published_recipe.version}`;
    } else if (project.export && project.export.error) {
      setMessage(`Image validée, mais export en échec : ${project.export.error}`, true);
    }
    renderGallery();
    renderGuidanceCompose();
    renderStatus();
  }

  function restoreRenderState(project) {
    if (project.render_settings) {
      loadAttemptSettings({ prompt: project.current_prompt || "", settings: project.render_settings, seed: project.render_seed });
      return;
    }
    const last = [...(project.attempts || [])].reverse().find(
      (a) => (a.conversation_branch_id || "main") === (project.active_branch_id || "main"),
    );
    if (last) loadAttemptSettings(last);
    else loadSampling(null);
    if (!last && !project.render_settings) loadWorkflow(null);
    // A newer conversational prompt can exist after the last render.
    elements.prompt.value = project.current_prompt || last?.prompt || "";
  }

  function renderBranches() {
    elements.branchTree.replaceChildren();
    const project = state.project;
    const branches = project?.branches || [];
    elements.activeBranch.textContent = branches.find((b) => b.branch_id === project.active_branch_id)?.name || "Exploration initiale";
    const lists = new Map();
    branches.forEach((branch) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "krea2-assisted-branch-button";
      const active = branch.branch_id === project.active_branch_id;
      button.setAttribute("aria-current", String(active));
      button.disabled = state.busy;
      if (branch.preview_url) {
        const image = document.createElement("img");
        image.src = branch.preview_url;
        image.alt = "";
        image.loading = "lazy";
        button.append(image);
      }
      const copy = document.createElement("span");
      const name = document.createElement("b");
      name.textContent = `${branch.name}${active ? " · active" : ""}`;
      const note = document.createElement("small");
      note.textContent = `${branch.turn_count} message(s)`;
      const source = (project.attempts || []).find((a) => a.attempt_id === branch.source_attempt_id);
      if (source) note.textContent += source.can_restore_conversation
        ? ` · reprise au moment de l’essai ${source.index}` : " · départ image + prompt, sans anciens échanges";
      copy.append(name, note);
      button.append(copy);
      button.addEventListener("click", () => { if (!active) changeBranch({ branch_id: branch.branch_id }); });
      const children = document.createElement("ul");
      children.hidden = !branches.some((b) => b.parent_branch_id === branch.branch_id);
      item.append(button, children);
      (lists.get(branch.parent_branch_id) || elements.branchTree).append(item);
      lists.set(branch.branch_id, children);
    });
  }

  async function changeBranch(target) {
    if (state.busy || !state.project || restagingEditor.saving) return;
    if (!validateSamplingInputs()) return;
    const projectId = state.project.project_id;
    const draft = elements.prompt.value.trim() ? {
      prompt: elements.prompt.value.trim(), model_id: elements.model.value,
      aspect_ratio: elements.ratio.value, megapixels: Number(elements.megapixels.value),
      seed: elements.seed.value.trim() || null, loras: selectedLoras(), sampling: readSampling(),
      workflow: elements.workflow.value,
    } : null;
    stopPolling();
    state.navigationSerial += 1;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}/branches`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...target, expected_branch_id: state.project.active_branch_id,
          draft, prompt_language: elements.promptLanguage.value,
          model_id: elements.revisionLlm.value || state.project.model_id }),
      });
      clearGuidance();
      elements.message.value = "";
      reasoningTrace.reset();
      renderProject(payload.project);
      elements.branches.open = true;
      elements.conversation.scrollIntoView({ behavior: "smooth", block: "center" });
      setMessage(target.image_prompt_only
        ? "Nouvelle piste créée avec l’image et son prompt. Les anciens échanges ne sont pas repris."
        : target.attempt_id ? "Nouvelle branche créée au point de conversation de cet essai."
          : "Branche retrouvée avec sa conversation et ses réglages.");
      await loadHistory();
    } catch (error) { setMessage(error.message, true); }
    finally {
      setBusy(false);
      if ((state.project?.attempts || []).some((a) => activeStatuses.has(a.status))) schedulePoll();
    }
  }

  function renderHistory() {
    elements.history.replaceChildren();
    elements.historyEmpty.hidden = state.projects.length > 0;
    state.projects.forEach((project) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "krea2-assisted-history-item";
      const title = document.createElement("b"); title.textContent = project.name;
      const meta = document.createElement("small");
      const outputs = (project.attempts || []).filter((attempt) => attempt.status === "succeeded").length;
      meta.textContent = `${outputs} rendu(s) · ${(project.turns || []).length} message(s)`;
      button.append(title, meta);
      const latest = [...(project.attempts || [])].reverse().find((attempt) => attempt.output_url);
      if (latest) { const image = document.createElement("img"); image.src = latest.output_url; image.alt = ""; image.loading = "lazy"; button.append(image); }
      button.addEventListener("click", () => openProject(project.project_id));
      item.append(button);
      elements.history.append(item);
    });
  }

  async function loadSpec(preserve = false) {
    return refreshCatalog(preserve);
  }

  const catalogStatus = resourceUi.catalogStatus(elements.workspace,
    force => refreshCatalog(true, force), () => !elements.workspace.hidden);
  let catalogRequest = null;
  async function refreshCatalog(preserve = true, force = false) {
    if (catalogRequest) return force ? catalogRequest.then(() => refreshCatalog(preserve, true)) : catalogRequest;
    catalogRequest = fetchCatalog(preserve, force).catch(error => {
      catalogStatus.failed(error);
      throw error;
    }).finally(() => { catalogRequest = null; });
    return catalogRequest;
  }
  async function fetchCatalog(preserve, force) {
    let next;
    try {
      next = await request(`/api/image-lab/krea2-assisted/spec${force ? "?refresh=true" : ""}`);
      if (!next || ![next.render_models, next.loras, next.llm_models].every(Array.isArray)) {
        throw new Error("Réponse de catalogue invalide.");
      }
    } catch (error) { error.catalogPhase = "request"; throw error; }
    if (state.busy && state.spec) { catalogStatus.observe(next); catalogStatus.retry(); return; }
    // Capture at application time: a user may have navigated during the request.
    preserve = preserve || Boolean(state.project);
    const previousModel = preserve ? elements.model.value : "";
    const previousRevisionLlm = preserve ? elements.revisionLlm.value : "";
    const previousSlots = state.loraSlots.map((slot) => ({ ...slot }));
    state.spec = next;
    configureSampling(next.sampling);
    configureWorkflows(next.workflows);
    const signature = JSON.stringify([next.render_models, next.loras, next.llm_models]);
    if (state.catalogSignature === signature) { catalogStatus.observe(next); return; }
    const previousRecipe = elements.assistanceRecipe.value || "3.0.0";
    elements.assistanceRecipe.replaceChildren();
    for (const recipe of state.spec.assistance_recipes || []) {
      const option = document.createElement("option");
      option.value = recipe.version;
      option.textContent = recipe.label;
      elements.assistanceRecipe.append(option);
    }
    if ([...elements.assistanceRecipe.options].some((item) => item.value === previousRecipe)) elements.assistanceRecipe.value = previousRecipe;
    fillOptions();
    if (preserve) {
      ensureMissingOption(elements.model, previousModel);
      if (previousModel) elements.model.value = previousModel;
      if (previousRevisionLlm) {
        window.PanelForgeModelPicker.select(
          elements.revisionLlm,
          previousRevisionLlm,
          "modèle historique indisponible",
        );
      }
      state.loraSlots = previousSlots;
      renderLoraStack();
      resourceUi.syncModelPicker(elements.model);
    }
    setBusy(state.busy);
    // A failed repaint must be retried even if the next HTTP payload is identical.
    state.catalogSignature = signature;
    catalogStatus.observe(next);
  }

  function setHistoryMessage(message = "", error = false) {
    if (!elements.historyState) return;
    elements.historyState.textContent = message;
    elements.historyState.hidden = !message;
    elements.historyState.classList.toggle("error", error);
  }

  async function loadHistory() {
    if (!state.projectRequest) setHistoryMessage("Chargement des projets…");
    try {
      const payload = await request("/api/image-lab/krea2-assisted/projects?limit=30");
      state.projects = payload.projects || [];
      renderHistory();
      if (elements.newProject && !state.projects.length) elements.newProject.open = true;
      if (!state.projectRequest) setHistoryMessage();
    } catch (error) {
      if (!state.projectRequest) setHistoryMessage(`Projets indisponibles : ${error.message}`, true);
      throw error;
    }
  }

  async function openProject(projectId) {
    if ((state.busy && !state.projectRequest) || restagingEditor.saving) return;
    state.projectRequest?.abort();
    const controller = new AbortController();
    state.projectRequest = controller;
    state.navigationSerial += 1;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      stopPolling();
      clearGuidance();
      setBusy(true);
      setMessage();
      setHistoryMessage("Ouverture du projet… Vous pouvez en choisir un autre.");
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}`, { signal: controller.signal });
      if (state.projectRequest !== controller) return;
      loadRenderQueue().catch(error => setMessage(error.message, true));
      renderProject(payload.project);
      restoreRenderState(payload.project);
      setHistoryMessage();
      if ((state.renderQueue.items || []).length) schedulePoll();
    } catch (error) {
      if (state.projectRequest !== controller) return;
      const message = error.name === "AbortError" ? "Le projet met trop longtemps à répondre. Réessayez ou choisissez un autre projet." : error.message;
      setHistoryMessage(message, true);
      setMessage(message, true);
    } finally {
      clearTimeout(timeout);
      if (state.projectRequest === controller) {
        state.projectRequest = null;
        setBusy(false);
      }
    }
  }

  async function createProject(event) {
    event.preventDefault();
    if (state.busy || restagingEditor.saving) return;
    if (!elements.intention.value.trim() && !elements.reference.files[0]) {
      setNewMessage("Ajoute une image de référence ou décris ton intention.");
      return;
    }
    setBusy(true);
    setNewMessage();
    try {
      const data = new FormData();
      data.set("name", elements.name.value.trim());
      data.set("intention", elements.intention.value.trim());
      data.set("model_id", elements.llm.value);
      data.set("assistance_recipe_version", elements.assistanceRecipe.value);
      if (elements.newPreset.value) data.set("style_preset_id", elements.newPreset.value);
      if (elements.reference.files[0]) data.set("reference", elements.reference.files[0]);
      const payload = await request("/api/image-lab/krea2-assisted/projects", { method: "POST", body: data });
      clearGuidance();
      renderProject(payload.project);
      await loadHistory();
      await sendChat("creation", payload.project.intention);
    } catch (error) { setNewMessage(error.message); }
    finally { setBusy(false); }
  }

  async function sendChat(mode, explicitMessage = null) {
    if (!state.project) return;
    const message = (explicitMessage || elements.message.value).trim()
      || (mode === "recipe" ? "Aide-moi à transformer le résultat sélectionné en recette Batch réutilisable. Pose les questions encore nécessaires." : "Affinons le prompt actuel.");
    setBusy(true);
    setMessage(mode === "recipe" ? "Préparation de la recette…" : "Le modèle affine le prompt…");
    reasoningTrace.begin(mode === "recipe" ? "Recette KREA2" : "Création KREA2");
    let streamError = "";
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      const guidance = await resolveGuidance();
      outcomeTone.start();
      await core.streamRequest(
        reasoningTrace.streamUrl(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/chat/stream`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({
            message,
            current_prompt: elements.prompt.value,
            expected_branch_id: state.project.active_branch_id,
            mode,
            model_id: elements.revisionLlm.value || state.project.revision_model_id || state.project.model_id,
            feedback_attempt_id: state.project.feedback_attempt_id,
            prompt_language: elements.promptLanguage.value,
            guidance_asset_id: guidance?.asset_id || null,
            guidance_filename: guidance?.filename || null,
          }),
        },
        (event) => {
          reasoningTrace.handle(event);
          if (event.error) streamError = event.error;
          if (event.project) renderProject(event.project, { preservePrompt: false });
        },
        { completionTone: false },
      );
      clearGuidance();
      if (streamError) throw new Error(streamError);
      outcomeTone.success();
      elements.message.value = "";
      setMessage(mode === "recipe" ? "Échange recette enregistré." : "Prompt mis à jour.");
      await loadHistory();
    } catch (error) { outcomeTone.failure(); setMessage(error.message, true); }
    finally { reasoningTrace.finish(); setBusy(false); }
  }

  async function renderAttempt() {
    if (!state.project || state.busy) return;
    if (!validateSamplingInputs()) return;
    const prompt = elements.prompt.value.trim();
    if (!prompt) { setMessage("Préparez ou écrivez d’abord un prompt.", true); return; }
    stopPolling();
    state.navigationSerial += 1; // Discard an in-flight poll predating this new attempt.
    setBusy(true);
    const projectId = state.project.project_id;
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}/attempts?enqueue=true`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          expected_branch_id: state.project.active_branch_id,
          model_id: elements.model.value,
          aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value),
          seed: elements.seed.value.trim() || null,
          loras: selectedLoras(),
          sampling: readSampling(),
          workflow: elements.workflow.value,
        }),
      });
      const attempt = payload.project.attempts.at(-1);
      renderProject(payload.project, { preservePrompt: true });
      if (attempt.status === "created") throw new Error("L’essai est préparé. Redémarrez le serveur pour activer la file de rendus.");
      setMessage(`Essai ${attempt.index} ajouté à la file. Vous pouvez préparer le suivant.`);
      schedulePoll();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function startPreparedAttempt(attemptId) {
    if (!state.project || state.busy) return;
    const projectId = state.project.project_id;
    stopPolling();
    state.navigationSerial += 1;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}/attempts/${encodeURIComponent(attemptId)}/start`, { method: "POST" });
      renderProject(payload.project, { preservePrompt: true });
      setMessage("Essai ajouté à la file avec ses réglages enregistrés.");
      schedulePoll();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  function stopPolling() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function schedulePoll() {
    stopPolling();
    state.pollTimer = window.setTimeout(poll, 1000);
  }

  async function poll() {
    if (!state.project) return;
    if (state.busy) { schedulePoll(); return; }
    const serial = state.navigationSerial;
    const projectId = state.project.project_id;
    try {
      const [payload] = await Promise.all([
        request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}`), loadRenderQueue(),
      ]);
      if (serial !== state.navigationSerial || projectId !== state.project?.project_id) return;
      if (state.busy) { schedulePoll(); return; }
      renderProject(payload.project, { preservePrompt: true });
      if ((state.renderQueue.items || []).length || (payload.project.attempts || []).some((attempt) => activeStatuses.has(attempt.status))) {
        schedulePoll();
      } else {
        stopPolling();
        const last = (payload.project.attempts || []).at(-1);
        setMessage(last?.status === "created" ? "La file est terminée. Les essais préparés restent à lancer."
          : last?.status === "succeeded" ? "Rendus terminés. Vous pouvez sélectionner un feedback ou enregistrer une image."
            : last?.error || "File terminée.", last?.status === "failed");
        await loadHistory();
      }
    } catch (error) {
      if (serial === state.navigationSerial) { setMessage(error.message, true); schedulePoll(); }
    }
  }

  async function cancelAttempt(attemptId = null) {
    const active = state.project && (state.project.attempts || []).find((attempt) =>
      attemptId ? attempt.attempt_id === attemptId : activeStatuses.has(attempt.status));
    if (!active || state.busy) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts/${encodeURIComponent(active.attempt_id)}/cancel`, { method: "POST" });
      await loadRenderQueue();
      renderProject(payload.project, { preservePrompt: true });
      if ((state.renderQueue.items || []).length) schedulePoll();
      else stopPolling();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function selectFeedback(attemptId) {
    if (state.busy || !state.project) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ attempt_id: attemptId }),
      });
      renderProject(payload.project, { preservePrompt: true });
      setMessage(attemptId === null
        ? "Feedback visuel retiré."
        : "Ce rendu sera montré au LLM lors du prochain échange.");
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function saveImage(attemptId) {
    if (state.busy || !state.project) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts/${encodeURIComponent(attemptId)}/save`, { method: "POST" });
      renderProject(payload.project, { preservePrompt: true });
      setMessage(payload.project.export.error ? `Image validée, export en échec : ${payload.project.export.error}` : `Image enregistrée dans ${payload.project.export.path || "le projet"}.`, Boolean(payload.project.export.error));
      await loadHistory();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  function parsedDraft() {
    const value = JSON.parse(elements.recipeDraft.value);
    const keys = ["recipe_id", "display_name", "description", "identity", "invariants", "variables", "risks", "canonical_prompt"];
    const result = {};
    keys.forEach((key) => { result[key] = value[key]; });
    return result;
  }

  async function saveDraft() {
    if (state.busy || !state.project) return;
    setBusy(true);
    try {
      const draft = parsedDraft();
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/recipe-draft`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft),
      });
      state.draftSnapshot = draftText(payload.project.recipe_draft);
      elements.recipeDraft.value = state.draftSnapshot;
      renderProject(payload.project, { preservePrompt: true });
      elements.recipeMessage.textContent = "Brouillon enregistré dans le projet.";
    } catch (error) { elements.recipeMessage.textContent = error.message; elements.recipeMessage.classList.add("error"); }
    finally { setBusy(false); }
  }

  async function publishRecipe() {
    if (state.busy || !state.project) return;
    setBusy(true);
    try {
      const draft = parsedDraft();
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/recipe/publish`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft }),
      });
      renderProject(payload.project, { preservePrompt: true });
      elements.recipeMessage.textContent = `Recette ${payload.recipe.display_name} publiée en ${payload.recipe.version}.`;
      elements.recipeMessage.classList.remove("error");
    } catch (error) { elements.recipeMessage.textContent = error.message; elements.recipeMessage.classList.add("error"); }
    finally { setBusy(false); }
  }

  async function loadPresets() {
    const payload = await request("/api/image-lab/krea2-assisted/style-presets");
    state.presets = payload.presets || [];
    for (const select of [elements.newPreset, elements.preset]) {
      const selected = select.value;
      select.replaceChildren(new Option("Sans preset", ""), ...state.presets.map((p) => new Option(p.name, p.preset_id)));
      if (state.presets.some((p) => p.preset_id === selected)) select.value = selected;
    }
    renderPresetSelection();
  }

  function renderPresetSelection() {
    const project = state.project;
    const preset = project?.style_preset;
    elements.presetImage.hidden = !preset;
    if (preset) elements.presetImage.src = preset.image_url;
    elements.preset.value = preset?.preset_id || "";
    const current = state.presets.find((p) => p.preset_id === preset?.preset_id);
    const update = current && current.revision !== preset.revision ? " Une mise à jour est disponible via Réappliquer." : "";
    elements.presetNote.textContent = preset
      ? `${preset.name} · ${project.preset_pending ? "inspiration au prochain échange" : "exemple déjà transmis"}.${update}`
      : "La sélection applique le modèle et les LoRA ; le prompt reste inchangé jusqu’au prochain échange.";
    elements.presetReapply.disabled = state.busy || !preset;
    elements.presetRemove.disabled = state.busy || !preset;
  }

  async function applyPreset(presetId) {
    if (!state.project || state.busy) return;
    if (!validateSamplingInputs()) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/style-preset`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: presetId, expected_branch_id: state.project.active_branch_id,
          draft: { prompt: elements.prompt.value, model_id: elements.model.value,
            aspect_ratio: elements.ratio.value, megapixels: Number(elements.megapixels.value),
            seed: elements.seed.value.trim() || null, loras: selectedLoras(), sampling: readSampling(),
            workflow: elements.workflow.value } }),
      });
      renderProject(payload.project, { preservePrompt: true });
      restoreRenderState(payload.project);
      setMessage(presetId ? "Modèle et LoRA appliqués. Le prompt d’exemple sera transmis au prochain échange."
        : "Preset retiré. Les réglages et le prompt courant restent disponibles.");
    } catch (error) {
      renderPresetSelection();
      setMessage(error.message, true);
    } finally { setBusy(false); }
  }

  function openPresetDialog(attempt) {
    if (state.busy || !state.project) return;
    state.presetSource = { project_id: state.project.project_id, attempt_id: attempt.attempt_id };
    elements.presetSource.textContent = `${attempt.label || `Essai ${attempt.index}`} · ${attempt.settings.model_id} · ${attempt.settings.loras.length} LoRA${attempt.composition ? " · réglages de la génération d’origine" : ""}`;
    elements.presetTarget.replaceChildren(new Option("Nouveau preset", ""), ...state.presets.map((p) => new Option(`Mettre à jour : ${p.name}`, p.preset_id)));
    elements.presetName.value = state.project.name;
    elements.presetError.textContent = "";
    elements.presetSave.textContent = "Enregistrer un nouveau preset";
    elements.presetDialog.showModal();
    elements.presetName.focus();
  }

  async function savePreset(event) {
    event.preventDefault();
    if (state.busy || !state.presetSource) return;
    setBusy(true);
    elements.presetError.textContent = "";
    try {
      const target = state.presets.find((p) => p.preset_id === elements.presetTarget.value);
      const payload = await request("/api/image-lab/krea2-assisted/style-presets", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...state.presetSource, name: elements.presetName.value.trim(),
          preset_id: target?.preset_id || null, expected_revision: target?.revision || null }),
      });
      await loadPresets();
      elements.presetDialog.close();
      setMessage(`Preset « ${payload.preset.name} » enregistré. Les projets existants conservent leur version.`);
    } catch (error) { elements.presetError.textContent = error.message; }
    finally { setBusy(false); }
  }

  async function initialize() {
    if (state.initializing) return state.initializing;
    if (state.initialized) return refreshCatalog(true);
    state.initializing = (async () => {
      setBusy(state.busy);
      try {
        const results = await Promise.allSettled([loadSpec(), loadHistory(), loadPresets(), loadRenderQueue()]);
        state.initialized = results.every(result => result.status === "fulfilled");
        results.filter(result => result.status === "rejected").forEach(result => setNewMessage(result.reason.message));
      } catch (error) { setNewMessage(`Création assistée indisponible : ${error.message}`); }
      finally { state.initializing = null; }
    })();
    return state.initializing;
  }

  elements.newForm.addEventListener("submit", createProject);
  elements.model.addEventListener("change", () => setBusy(state.busy));
  elements.newPreset.addEventListener("change", () => {
    const preset = state.presets.find((p) => p.preset_id === elements.newPreset.value);
    elements.newPresetNote.textContent = preset
      ? `${preset.settings.model_id} · ${preset.settings.loras.length} LoRA · exemple au premier échange.` : "";
  });
  elements.preset.addEventListener("change", () => applyPreset(elements.preset.value || null));
  elements.presetReapply.addEventListener("click", () => applyPreset(state.project?.style_preset?.preset_id));
  elements.presetRemove.addEventListener("click", () => applyPreset(null));
  elements.presetImage.addEventListener("click", () => {
    const preset = state.project?.style_preset;
    if (preset) openLightbox(preset.image_url, preset.name);
  });
  elements.presetTarget.addEventListener("change", () => {
    const preset = state.presets.find((p) => p.preset_id === elements.presetTarget.value);
    if (preset) elements.presetName.value = preset.name;
    elements.presetSave.textContent = preset ? "Mettre à jour ce preset" : "Enregistrer un nouveau preset";
  });
  elements.presetForm.addEventListener("submit", savePreset);
  $("krea2-assisted-preset-close").addEventListener("click", () => elements.presetDialog.close());
  elements.refresh.addEventListener("click", () => loadHistory().catch(() => {}));
  elements.chat.addEventListener("click", () => sendChat("creation"));
  elements.recipeChat.addEventListener("click", () => sendChat("recipe"));
  elements.guidanceFile.addEventListener("change", selectGuidanceFile);
  elements.guidanceRemove.addEventListener("click", clearGuidance);
  elements.guidanceImage.addEventListener("click", openCurrentGuidance);
  elements.guidanceDockOpen.addEventListener("click", openCurrentGuidance);
  elements.feedbackOpen.addEventListener("click", () => {
    const preview = selectedFeedbackPreview();
    if (preview) openLightbox(preview.source, preview.name);
  });
  elements.render.addEventListener("click", renderAttempt);
  elements.cancel.addEventListener("click", () => cancelAttempt());
  elements.queueOpen.addEventListener("click", () => {
    const running = (state.renderQueue.items || []).find((item) => item.status !== "queued");
    if (running) openProject(running.project_id);
  });
  elements.copyPrompt.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(elements.prompt.value); setMessage("Prompt copié."); }
    catch (_) { elements.prompt.select(); document.execCommand("copy"); }
  });
  elements.saveDraft.addEventListener("click", saveDraft);
  elements.publishRecipe.addEventListener("click", publishRecipe);
  elements.lightboxClose.addEventListener("click", () => elements.lightbox.close());
  elements.lightbox.addEventListener("click", (event) => { if (event.target === elements.lightbox) elements.lightbox.close(); });
  document.querySelectorAll('[data-image-lab-mode="krea2-assisted-lab"]').forEach((button) => {
    button.addEventListener("click", () => {
      window.PanelForgeLabNavigation?.switchView("krea2-assisted-lab");
      initialize();
    });
  });
  window.addEventListener("beforeunload", stopPolling);
  window.PanelForgeKrea2AssistedLab = Object.freeze({
    open: async (projectId = null) => {
      window.PanelForgeLabNavigation?.switchView("krea2-assisted-lab");
      await initialize();
      if (projectId) return openProject(projectId);
    },
  });
  if (!elements.workspace.hidden) initialize();
})();
