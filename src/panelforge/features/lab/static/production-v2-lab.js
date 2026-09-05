(() => {
  "use strict";

  const core = window.PanelForgeLabCore;
  const resourceUi = window.PanelForgeKrea2ResourceUi;
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    createForm: $("#production-v2-create-form"), source: $("#production-v2-source"), sourcePreview: $("#production-v2-source-preview"), sourceName: $("#production-v2-source-name"),
    name: $("#production-v2-name"), intention: $("#production-v2-intention"), createMemory: $("#production-v2-create-memory"), createMemoryButton: $("#production-v2-create-memory-button"), createMemoryEditor: $("#production-v2-create-memory-editor"), createMemoryName: $("#production-v2-create-memory-name"), createMemorySave: $("#production-v2-create-memory-save"), createMemoryCancel: $("#production-v2-create-memory-cancel"), initialLlm: $("#production-v2-initial-llm"), createMusic: $("#production-v2-create-music"), createVideoLoraProfile: $("#production-v2-create-video-lora-profile"), createVideoLora: $("#production-v2-create-video-lora"), createVideoLoraStrength: $("#production-v2-create-video-lora-strength"), createVideoLoraClip: $("#production-v2-create-video-lora-clip"), createStopTemp: $("#production-v2-create-stop-temp"), createResumeTemp: $("#production-v2-create-resume-temp"), createCooldown: $("#production-v2-create-cooldown"), createError: $("#production-v2-create-error"),
    sidebar: $("#production-v2-sidebar"), newProject: $("#production-v2-new"), projectSection: $("#production-v2-project-section"), imageSection: $("#production-v2-image-section"), videoSection: $("#production-v2-video-section"),
    projectSummary: $("#production-v2-project-summary"), projectState: $("#production-v2-project-state"), projectSource: $("#production-v2-project-source"), projectIntention: $("#production-v2-project-intention"), memory: $("#production-v2-memory"),
    imageSummary: $("#production-v2-image-summary"), imageState: $("#production-v2-image-state"), recipeLock: $("#production-v2-recipe-lock"), role: $("#production-v2-role"), count: $("#production-v2-count"), imageMp: $("#production-v2-image-mp"), promptStrategy: $("#production-v2-prompt-strategy"), preserveSeed: $("#production-v2-preserve-seed"), preserveModel: $("#production-v2-preserve-model"), preserveLoras: $("#production-v2-preserve-loras"), renderModel: $("#production-v2-render-model"), renderModelLabel: $("#production-v2-render-model-label"), ratio: $("#production-v2-ratio"), loras: $("#production-v2-loras"), loraAssisted: $("#production-v2-lora-assisted"), loraInstruction: $("#production-v2-lora-instruction"), feedbackParent: $("#production-v2-feedback-parent"), newRecipeBranch: $("#production-v2-new-recipe-branch"), referenceMode: $("#production-v2-reference-mode"), guidanceCandidate: $("#production-v2-guidance-candidate"), guidanceField: $("#production-v2-guidance-field"), parentContext: $("#production-v2-parent-context"), parentImageButton: $("#production-v2-parent-image-button"), parentImage: $("#production-v2-parent-image"), parentTitle: $("#production-v2-parent-title"), parentMeta: $("#production-v2-parent-meta"), kreaChat: $("#production-v2-krea-chat"), kreaLlm: $("#production-v2-krea-llm"), imageInstruction: $("#production-v2-image-instruction"), batchCost: $("#production-v2-batch-cost"), generateImages: $("#production-v2-generate-images"),
    videoSummary: $("#production-v2-video-summary"), videoState: $("#production-v2-video-state"), videoContract: $("#production-v2-video-contract"), videoDurationWarning: $("#production-v2-video-duration-warning"), videoIntention: $("#production-v2-video-intention"), compileLlm: $("#production-v2-compile-llm"), creativeAudacity: $("#production-v2-creative-audacity"), creativeAudacityValue: $("#production-v2-creative-audacity-value"), compile: $("#production-v2-compile"), videoRatio: $("#production-v2-video-ratio"), videoDuration: $("#production-v2-video-duration"), videoSteps: $("#production-v2-video-steps"), videoPreviewMp: $("#production-v2-video-preview-mp"), videoFinalMp: $("#production-v2-video-final-mp"), videoSeed: $("#production-v2-video-seed"), videoNewSeed: $("#production-v2-video-new-seed"), videoSeedLocked: $("#production-v2-video-seed-locked"), videoSpectrum: $("#production-v2-video-spectrum"), videoMusic: $("#production-v2-video-music"), videoLoraProfile: $("#production-v2-video-lora-profile"), videoLora: $("#production-v2-video-lora"), videoLoraStrength: $("#production-v2-video-lora-strength"), videoLoraClip: $("#production-v2-video-lora-clip"), videoChat: $("#production-v2-video-chat"), videoRevisionDraft: $("#production-v2-video-revision-draft"), videoRevisionError: $("#production-v2-video-revision-error"), videoRevisionDraftContent: $("#production-v2-video-revision-draft-content"), videoRevisionRetry: $("#production-v2-video-revision-retry"), videoLlm: $("#production-v2-video-llm"), revisionAudacity: $("#production-v2-revision-audacity"), revisionAudacityValue: $("#production-v2-revision-audacity-value"), videoInstruction: $("#production-v2-video-instruction"), reviseVideo: $("#production-v2-revise-video"), renderPreview: $("#production-v2-render-preview"), renderFinal: $("#production-v2-render-final"),
    actionError: $("#production-v2-action-error"), thermalSummary: $("#production-v2-thermal-summary"), cancel: $("#production-v2-cancel"), refresh: $("#production-v2-refresh"), projectList: $("#production-v2-project-list"), landingRefresh: $("#production-v2-landing-refresh"), landingProjectList: $("#production-v2-landing-project-list"),
    empty: $("#production-v2-empty"), project: $("#production-v2-project"), stage: $("#production-v2-stage"), title: $("#production-v2-title"), status: $("#production-v2-status"), message: $("#production-v2-message"), llmTraces: $("#production-v2-llm-traces"), route: $("#production-v2-route"), anchors: $("#production-v2-anchors"), candidates: $("#production-v2-candidates"), h3Panel: $("#production-v2-h3-panel"), h3Prompt: $("#production-v2-h3-prompt"), renderProgress: $("#production-v2-render-progress"), renderProgressPhase: $("#production-v2-render-progress-phase"), renderProgressMeta: $("#production-v2-render-progress-meta"), renderProgressBar: $("#production-v2-render-progress-bar"), renderLivePreview: $("#production-v2-render-live-preview"), renderLiveEmpty: $("#production-v2-render-live-empty"), renderCancel: $("#production-v2-render-cancel"), previews: $("#production-v2-previews"), final: $("#production-v2-final"), archives: $("#production-v2-archives"), archivesList: $("#production-v2-archives-list"), events: $("#production-v2-events"),
    dialog: $("#production-v2-image-dialog"), dialogTitle: $("#production-v2-image-dialog-title"), dialogContent: $("#production-v2-image-dialog-content"), dialogClose: $("#production-v2-image-dialog-close"),
  };
  if (!core || !elements.createForm) return;

  const state = {
    spec: null,
    project: null,
    projects: [],
    sourceObjectUrl: null,
    pollTimer: null,
    lastStage: null,
    lastStatus: null,
    modelProjectId: null,
    candidateRenderSignature: null,
    llmTraceRenderSignature: null,
    feedbackDrafts: new Map(),
    appliedRecipeRevisionId: null,
    appliedVideoConfiguration: null,
    videoRenderSignature: null,
    openWorkshops: new Set(),
    renderSocket: null,
    renderAttemptId: null,
    renderProgressData: null,
    renderProgressStartedAt: null,
    renderProgressTimer: null,
    renderPreviewUrl: null,
    kreaLoras: [],
  };

  const option = (value, label) => Object.assign(document.createElement("option"), { value, textContent: label });
  const isBusy = () => state.project?.status === "busy";

  document.addEventListener("DOMContentLoaded", initialize);

  async function initialize() {
    bind();
    try {
      await loadSpec();
      await loadProjects();
    } catch (error) {
      showError(error.message, true);
    }
  }

  function bind() {
    elements.source.addEventListener("change", previewSource);
    elements.createForm.addEventListener("submit", createProject);
    elements.createMemoryButton.addEventListener("click", toggleMemoryProfileEditor);
    elements.createMemorySave.addEventListener("click", createMemoryProfile);
    elements.createMemoryCancel.addEventListener("click", closeMemoryProfileEditor);
    elements.createMemoryName.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); createMemoryProfile(); }
      if (event.key === "Escape") { event.preventDefault(); closeMemoryProfileEditor(); }
    });
    elements.createVideoLoraProfile.addEventListener("change", renderCreateVideoLora);
    elements.newProject.addEventListener("click", showCreateForm);
    elements.refresh.addEventListener("click", loadProjects);
    elements.landingRefresh.addEventListener("click", loadProjects);
    elements.memory.addEventListener("change", changeMemoryProfile);
    elements.promptStrategy.addEventListener("change", iterationControlChanged);
    elements.preserveSeed.addEventListener("change", iterationControlChanged);
    elements.preserveModel.addEventListener("change", iterationControlChanged);
    elements.preserveLoras.addEventListener("change", iterationControlChanged);
    elements.renderModel.addEventListener("change", iterationControlChanged);
    elements.count.addEventListener("input", iterationControlChanged);
    elements.imageMp.addEventListener("input", iterationControlChanged);
    elements.ratio.addEventListener("change", iterationControlChanged);
    elements.kreaLlm.addEventListener("change", iterationControlChanged);
    elements.role.addEventListener("change", () => {
      elements.feedbackParent.value = "";
      elements.guidanceCandidate.value = "";
      elements.referenceMode.value = "recipe";
      if (state.project?.active_recipe) applySettingsToControls(state.project.active_recipe.settings);
      resetIterationControls();
      state.openWorkshops.add(elements.role.value);
      state.candidateRenderSignature = null;
      renderFeedbackParents();
      renderGuidanceCandidates();
      renderParentContext();
      renderControls();
      renderCandidates();
    });
    elements.loraAssisted.addEventListener("change", configureAssistedLoraExploration);
    elements.feedbackParent.addEventListener("change", () => selectFeedbackParent(elements.feedbackParent.value, true));
    elements.newRecipeBranch.addEventListener("click", startNewRecipeBranch);
    elements.referenceMode.addEventListener("change", () => {
      iterationControlChanged();
      renderParentContext();
    });
    elements.guidanceCandidate.addEventListener("change", () => {
      iterationControlChanged();
      renderParentContext();
    });
    elements.generateImages.addEventListener("click", generateCandidates);
    elements.compile.addEventListener("click", compileVideo);
    elements.videoLoraProfile.addEventListener("change", renderVideoLoraControls);
    elements.videoDuration.addEventListener("input", renderVideoDurationWarning);
    elements.videoPreviewMp.addEventListener("input", renderControls);
    elements.creativeAudacity.addEventListener("input", renderAudacityValues);
    elements.revisionAudacity.addEventListener("input", renderAudacityValues);
    elements.videoNewSeed.addEventListener("click", regenerateVideoSeed);
    elements.videoInstruction.addEventListener("input", renderControls);
    elements.reviseVideo.addEventListener("click", reviseVideoPrompt);
    elements.videoRevisionRetry.addEventListener("click", retryRejectedVideoRevision);
    elements.renderPreview.addEventListener("click", renderPreview);
    elements.renderFinal.addEventListener("click", renderFinal);
    elements.cancel.addEventListener("click", cancelOperation);
    elements.renderCancel.addEventListener("click", cancelOperation);
    elements.dialogClose.addEventListener("click", () => elements.dialog.close());
    elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) elements.dialog.close(); });
    window.addEventListener("beforeunload", () => {
      if (state.sourceObjectUrl) URL.revokeObjectURL(state.sourceObjectUrl);
      if (state.pollTimer) window.clearTimeout(state.pollTimer);
      closeRenderSocket();
      stopRenderProgressClock();
      resetRenderPreview();
    });
  }

  async function loadSpec() {
    const previous = {
      initial: elements.initialLlm.value,
      krea: elements.kreaLlm.value,
      compile: elements.compileLlm.value,
      video: elements.videoLlm.value,
      model: elements.renderModel.value,
      ratio: elements.ratio.value,
      videoRatio: elements.videoRatio.value,
    };
    state.spec = await core.request("/api/production-v2/spec");
    for (const [select, value] of [[elements.initialLlm, previous.initial], [elements.kreaLlm, previous.krea], [elements.compileLlm, previous.compile], [elements.videoLlm, previous.video]]) {
      if (window.PanelForgeModelPicker) window.PanelForgeModelPicker.populate(select, state.spec.llm_models || [], value);
      else select.replaceChildren(...(state.spec.llm_models || []).map((item) => option(item.id, item.label || item.id)));
    }
    populateProfiles(elements.createMemory, elements.createMemory.value || "sfw");
    populateProfiles(elements.memory, state.project?.memory_profile_id || elements.memory.value || "sfw");
    if (resourceUi) resourceUi.renderModelPicker(elements.renderModel, {
      resources: state.spec.render_models || [],
      updatePreference: updateKreaResourcePreference,
      refreshResource: refreshKreaResource,
    });
    else elements.renderModel.replaceChildren(...(state.spec.render_models || []).map((item) => option(item.comfy_name, item.filename || item.comfy_name)));
    const models = eligibleRenderModels();
    elements.renderModel.value = models.some((item) => item.comfy_name === previous.model) ? previous.model : (models[0]?.comfy_name || elements.renderModel.value);
    resourceUi?.syncModelPicker(elements.renderModel);
    elements.ratio.replaceChildren(...(state.spec.aspect_ratios || []).map((value) => option(value, value)));
    elements.ratio.value = (state.spec.aspect_ratios || []).includes(previous.ratio) ? previous.ratio : state.spec.defaults.aspect_ratio;
    elements.videoRatio.replaceChildren(...(state.spec.video_aspect_ratios || state.spec.aspect_ratios || []).map((value) => option(value, value)));
    elements.videoRatio.value = [...elements.videoRatio.options].some((item) => item.value === previous.videoRatio) ? previous.videoRatio : "9:16 (Portrait Widescreen)";
    elements.createVideoLora.replaceChildren(...(state.spec.h3_video_loras || []).map((value) => option(value, shortName(value))));
    elements.videoLora.replaceChildren(...(state.spec.h3_video_loras || []).map((value) => option(value, shortName(value))));
    const loraChoice = elements.createVideoLoraProfile.querySelector('option[value="lora"]');
    if (loraChoice) loraChoice.disabled = !(state.spec.h3_video_loras || []).length;
    renderCreateVideoLora();
    renderVideoLoraControls();
    renderLoras();
  }

  function renderCreateVideoLora() {
    const enabled = elements.createVideoLoraProfile.value === "lora";
    elements.createVideoLora.disabled = !enabled;
    elements.createVideoLoraStrength.disabled = !enabled;
    elements.createVideoLoraClip.disabled = !enabled;
  }

  function renderVideoLoraControls() {
    const enabled = elements.videoLoraProfile.value === "lora";
    elements.videoLora.disabled = !enabled || isBusy();
    elements.videoLoraStrength.disabled = !enabled || isBusy();
    elements.videoLoraClip.disabled = !enabled || isBusy();
  }

  function populateProfiles(select, current) {
    select.replaceChildren(...(state.spec?.memory_profiles || []).map((item) => option(item.profile_id, `${item.name} · ${item.observation_count} retours`)));
    if ([...select.options].some((item) => item.value === current)) select.value = current;
  }

  function eligibleRenderModels() {
    const all = state.spec?.render_models || [];
    const bf16 = all.filter((item) => /bf16/i.test(`${item.precision || ""} ${item.comfy_name || ""} ${item.filename || ""}`));
    return bf16.length ? bf16 : all;
  }

  function renderLoras() {
    if (!resourceUi) return;
    resourceUi.renderLoraStack(elements.loras, {
      resources: state.spec?.loras || [],
      selections: state.kreaLoras,
      maximum: 10,
      rowClass: "production-v2-lora-row",
      disabled: isBusy(),
      updatePreference: updateKreaResourcePreference,
      refreshResource: refreshKreaResource,
      onChange: (values) => {
        state.kreaLoras = values;
        iterationControlChanged();
        renderLoras();
      },
    });
  }

  async function updateKreaResourcePreference(resource, values) {
    try {
      const updated = await core.request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadSpec();
      return updated;
    } catch (error) { showError(error.message, true); return false; }
  }

  async function refreshKreaResource(resource) {
    try {
      const updated = await core.request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/refresh`, { method: "POST" });
      await loadSpec();
      return updated;
    } catch (error) { showError(`Recherche CivitAI indisponible : ${error.message}`, true); return false; }
  }

  function configureAssistedLoraExploration() {
    if (elements.loraAssisted.checked) {
      elements.preserveLoras.checked = false;
      if (Number(elements.count.value) < 3) elements.count.value = "3";
    }
    renderControls();
  }

  function iterationSource() {
    const parent = state.project?.candidates.find((item) => item.candidate_id === elements.feedbackParent.value);
    if (parent) return parent;
    const recipeId = state.project?.active_recipe?.source_candidate_id;
    return state.project?.candidates.find((item) => item.candidate_id === recipeId) || null;
  }

  function iterationControlChanged() {
    if (elements.preserveLoras.checked) elements.loraAssisted.checked = false;
    const source = iterationSource();
    if (source && elements.preserveModel.checked && [...elements.renderModel.options].some((item) => item.value === source.settings.model_name)) {
      elements.renderModel.value = source.settings.model_name;
    }
    if (source && elements.preserveLoras.checked) applyLorasToControls(source.settings.loras || []);
    renderControls();
  }

  function resetIterationControls() {
    const hasSource = Boolean(iterationSource());
    elements.promptStrategy.value = "rewrite_once";
    elements.preserveSeed.checked = false;
    elements.preserveModel.checked = hasSource;
    elements.preserveLoras.checked = hasSource;
    elements.loraAssisted.checked = false;
    const parentId = elements.feedbackParent.value;
    elements.referenceMode.value = parentId ? "recipe_and_guidance" : "recipe";
    elements.guidanceCandidate.value = parentId;
    const source = iterationSource();
    if (source && elements.preserveModel.checked && [...elements.renderModel.options].some((item) => item.value === source.settings.model_name)) {
      elements.renderModel.value = source.settings.model_name;
    }
    if (source && elements.preserveLoras.checked) applyLorasToControls(source.settings.loras || []);
    renderControls();
  }

  function llmCost() {
    const count = Math.max(1, Math.min(6, Number(elements.count.value) || 3));
    const strategy = elements.promptStrategy.value;
    const promptCalls = strategy === "preserve_current"
      ? 0 : strategy === "rewrite_once" ? 1 : count;
    const loraCalls = elements.loraAssisted.checked ? 1 : 0;
    const details = [];
    let sequence = 0;
    if (strategy === "rewrite_once") {
      details.push(`Appel ${++sequence} : réécriture du prompt commun`);
    } else if (strategy === "evolve_between") {
      details.push(`Appel ${++sequence} : prompt du rendu 1`);
    }
    if (loraCalls) details.push(`Appel ${++sequence} : planification des variantes LoRA`);
    if (strategy === "evolve_between") {
      for (let index = 2; index <= count; index += 1) {
        details.push(`Appel ${++sequence} : prompt du rendu ${index}, après analyse du rendu ${index - 1}`);
      }
    }
    return { count, promptCalls, loraCalls, total: promptCalls + loraCalls, details };
  }

  function selectedLoras() {
    return state.kreaLoras.map((lora) => ({
      name: lora.name,
      strength: Math.max(-1, Math.min(1, Number(lora.strength) || 0)),
    })).filter((item) => item.name);
  }

  function applySettingsToControls(settings) {
    if (!settings) return;
    if ([...elements.renderModel.options].some((item) => item.value === settings.model_name)) {
      elements.renderModel.value = settings.model_name;
      resourceUi?.syncModelPicker(elements.renderModel);
    }
    if ([...elements.ratio.options].some((item) => item.value === settings.aspect_ratio)) {
      elements.ratio.value = settings.aspect_ratio;
    }
    elements.imageMp.value = String(settings.megapixels);
    applyLorasToControls(settings.loras || []);
  }

  function applyLorasToControls(loras) {
    state.kreaLoras = (loras || []).slice(0, 10).filter((lora) => lora && lora.name).map((lora) => ({
      name: lora.name,
      strength: Number(lora.strength) || 0,
    }));
    renderLoras();
  }

  function previewSource() {
    const file = elements.source.files[0];
    if (!file) return;
    if (state.sourceObjectUrl) URL.revokeObjectURL(state.sourceObjectUrl);
    state.sourceObjectUrl = URL.createObjectURL(file);
    elements.sourcePreview.src = state.sourceObjectUrl;
    elements.sourcePreview.hidden = false;
    elements.sourceName.textContent = file.name;
  }

  function toggleMemoryProfileEditor() {
    const show = elements.createMemoryEditor.hidden;
    elements.createMemoryEditor.hidden = !show;
    elements.createMemoryButton.setAttribute("aria-expanded", String(show));
    if (show) {
      elements.createMemoryName.value = "";
      elements.createMemoryName.focus();
    }
  }

  function closeMemoryProfileEditor() {
    elements.createMemoryEditor.hidden = true;
    elements.createMemoryButton.setAttribute("aria-expanded", "false");
    elements.createMemoryName.value = "";
  }

  async function createMemoryProfile() {
    if (elements.createMemorySave.disabled) return;
    const name = elements.createMemoryName.value.trim();
    if (!name) {
      elements.createMemoryName.setCustomValidity("Indiquez un nom de profil.");
      elements.createMemoryName.reportValidity();
      elements.createMemoryName.setCustomValidity("");
      return;
    }
    elements.createMemorySave.disabled = true;
    showError("", true);
    try {
      const payload = await core.request("/api/production-v2/memory-profiles", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      await loadSpec();
      elements.createMemory.value = payload.profile.profile_id;
      closeMemoryProfileEditor();
    } catch (error) { showError(error.message, true); }
    finally { elements.createMemorySave.disabled = false; }
  }

  async function createProject(event) {
    event.preventDefault();
    showError();
    try {
      const body = new FormData();
      body.set("source", elements.source.files[0]);
      body.set("name", elements.name.value);
      body.set("intention", elements.intention.value);
      body.set("initial_model_id", elements.initialLlm.value);
      body.set("memory_profile_id", elements.createMemory.value);
      body.set("music_enabled", String(elements.createMusic.checked));
      body.set("h3_video_lora_enabled", String(elements.createVideoLoraProfile.value === "lora"));
      body.set("h3_video_lora_name", elements.createVideoLora.value);
      body.set("h3_video_lora_strength", elements.createVideoLoraStrength.value);
      body.set("h3_video_lora_clip_last_layer", String(elements.createVideoLoraClip.checked));
      body.set("stop_temperature_c", elements.createStopTemp.value);
      body.set("resume_temperature_c", elements.createResumeTemp.value);
      body.set("cooldown_seconds", elements.createCooldown.value);
      const payload = await core.request("/api/production-v2/projects", { method: "POST", body });
      state.project = payload.project;
      state.lastStage = null;
      state.lastStatus = null;
      await loadProjects();
      render();
    } catch (error) { showError(error.message, true); core.playFailureTone(); }
  }

  async function loadProjects() {
    const payload = await core.request("/api/production-v2/projects?limit=30");
    state.projects = payload.projects || [];
    renderProjectList();
  }

  function renderProjectList() {
    elements.projectList.replaceChildren();
    elements.landingProjectList.replaceChildren();
    if (!state.projects.length) {
      for (const target of [elements.projectList, elements.landingProjectList]) target.append(Object.assign(document.createElement("p"), { className: "muted", textContent: "Aucun projet V2." }));
      return;
    }
    state.projects.forEach((project) => {
      for (const target of [elements.projectList, elements.landingProjectList]) {
        const button = document.createElement("button"); button.type = "button"; button.className = "production-job-link";
        button.append(document.createTextNode(project.name), Object.assign(document.createElement("small"), { textContent: `${project.route.toUpperCase()} · ${project.stage}` }));
        button.addEventListener("click", () => openProject(project.project_id));
        target.append(button);
      }
    });
  }

  async function openProject(projectId) {
    try {
      const payload = await core.request(`/api/production-v2/projects/${projectId}`);
      state.project = payload.project;
      state.lastStage = null;
      state.lastStatus = null;
      state.candidateRenderSignature = null;
      state.llmTraceRenderSignature = null;
      state.videoRenderSignature = null;
      state.feedbackDrafts.clear();
      state.appliedRecipeRevisionId = null;
      state.appliedVideoConfiguration = null;
      state.openWorkshops.clear();
      closeRenderSocket();
      stopRenderProgressClock();
      render();
      schedulePoll();
    } catch (error) { showError(error.message); }
  }

  function showCreateForm() {
    state.project = null;
    state.lastStage = null;
    state.lastStatus = null;
    state.candidateRenderSignature = null;
    state.llmTraceRenderSignature = null;
    state.videoRenderSignature = null;
    state.feedbackDrafts.clear();
    state.appliedRecipeRevisionId = null;
    state.appliedVideoConfiguration = null;
    state.openWorkshops.clear();
    closeRenderSocket();
    stopRenderProgressClock();
    render();
  }

  async function changeMemoryProfile() {
    if (!state.project || elements.memory.value === state.project.memory_profile_id) return;
    await action(`/api/production-v2/projects/${state.project.project_id}/memory-profile`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_id: elements.memory.value }),
    });
  }

  function batchSettings() {
    const count = Math.max(1, Math.min(6, Number(elements.count.value) || 3));
    const loras = selectedLoras();
    const chosen = elements.renderModel.value;
    return Array.from({ length: count }, () => ({
      model_name: chosen,
      aspect_ratio: elements.ratio.value,
      megapixels: Number(elements.imageMp.value),
      loras,
    }));
  }

  async function generateCandidates() {
    if (elements.loraAssisted.checked && Number(elements.count.value) < 3) {
      elements.count.value = "3";
    }
    const source = iterationSource();
    if (["preserve_current"].includes(elements.promptStrategy.value) && !source) {
      showError("Conserver le prompt nécessite un candidat parent ou une recette visuelle validée.");
      return;
    }
    if (elements.referenceMode.value === "recipe_and_guidance" && !elements.guidanceCandidate.value) {
      showError("Choisissez l’image utilisée comme guidage visuel.");
      return;
    }
    await action(`/api/production-v2/projects/${state.project.project_id}/candidates`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: elements.role.value,
        instruction: elements.imageInstruction.value,
        model_id: elements.kreaLlm.value,
        feedback_parent_id: elements.feedbackParent.value || null,
        technical_comparison: false,
        freeze_prompt_seed: null,
        prompt_strategy: elements.promptStrategy.value,
        preserve_seed: elements.preserveSeed.checked,
        preserve_model: elements.preserveModel.checked,
        explore_models: !elements.preserveModel.checked,
        preserve_loras: elements.preserveLoras.checked,
        reference_mode: elements.referenceMode.value,
        guidance_candidate_id: elements.guidanceCandidate.value || null,
        assisted_lora_selection: elements.loraAssisted.checked,
        lora_instruction: elements.loraInstruction.value,
        settings: batchSettings(),
      }),
    }, true);
  }

  async function reviewCandidate(candidateId, preference, comment) {
    await action(`/api/production-v2/projects/${state.project.project_id}/candidates/${candidateId}/review`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preference, comment }),
    });
  }

  async function validateRecipe(candidateId) {
    await action(`/api/production-v2/projects/${state.project.project_id}/visual-recipe/${candidateId}`, { method: "POST" });
  }

  function continueFromCandidate(candidate) {
    elements.feedbackParent.value = candidate.candidate_id;
    elements.role.value = candidate.role;
    applySettingsToControls(candidate.settings);
    renderFeedbackParents();
    renderGuidanceCandidates();
    elements.feedbackParent.value = candidate.candidate_id;
    elements.guidanceCandidate.value = candidate.candidate_id;
    resetIterationControls();
    state.openWorkshops.add(candidate.role);
    state.candidateRenderSignature = null;
    renderCandidates();
    renderParentContext();
    elements.imageSection.open = true;
    elements.imageInstruction.focus();
  }

  function selectFeedbackParent(candidateId, restoreSettings) {
    const candidate = state.project?.candidates.find((item) => item.candidate_id === candidateId);
    if (candidate && restoreSettings) {
      elements.role.value = candidate.role;
      applySettingsToControls(candidate.settings);
      state.openWorkshops.add(candidate.role);
      state.candidateRenderSignature = null;
      renderCandidates();
    }
    if (candidate) {
      renderGuidanceCandidates();
      elements.guidanceCandidate.value = candidate.candidate_id;
      elements.referenceMode.value = "recipe_and_guidance";
    } else {
      elements.guidanceCandidate.value = "";
      elements.referenceMode.value = "recipe";
    }
    renderParentContext();
    renderControls();
  }

  function startNewRecipeBranch() {
    if (!state.project?.active_recipe) return;
    elements.feedbackParent.value = "";
    elements.guidanceCandidate.value = "";
    elements.referenceMode.value = "recipe";
    applySettingsToControls(state.project.active_recipe.settings);
    resetIterationControls();
    state.openWorkshops.add(elements.role.value);
    state.candidateRenderSignature = null;
    renderParentContext();
    renderCandidates();
    elements.imageSection.open = true;
    elements.imageInstruction.focus();
  }

  async function cloneAtResolution(candidateId, megapixels) {
    await action(`/api/production-v2/projects/${state.project.project_id}/candidates/${candidateId}/resolution-clone`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ megapixels }),
    }, true);
  }

  async function directRef2v(candidateId) {
    if (!window.confirm("Valider cette image comme base et l’utiliser immédiatement comme première référence Ref2V ?")) return;
    await action(`/api/production-v2/projects/${state.project.project_id}/candidates/${candidateId}/direct-ref2v`, { method: "POST" });
  }

  async function unlockRecipe() {
    if (!window.confirm("Retirer la base active invalidera les ancres et rendus vidéo aval. L’historique restera disponible. Continuer ?")) return;
    await action(`/api/production-v2/projects/${state.project.project_id}/visual-recipe/current/unlock`, { method: "POST" });
  }

  async function promoteAnchor(candidateId, useSource = false, role = null) {
    await action(`/api/production-v2/projects/${state.project.project_id}/anchors`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: role || elements.role.value, candidate_id: candidateId, use_source: useSource }),
    });
  }

  async function removeAnchor(anchorId) {
    await action(`/api/production-v2/projects/${state.project.project_id}/anchors/${anchorId}`, { method: "DELETE" });
  }

  async function compileVideo() {
    if (state.project.h3 && !window.confirm("Recompiler archivera le prompt et les previews vidéo courants, puis lancera une nouvelle preview. Continuer ?")) return;
    showError();
    try {
      await persistVideoConfiguration(Boolean(state.project.h3));
      await action(`/api/production-v2/projects/${state.project.project_id}/video/compile`, { method: "POST" }, true);
    } catch (error) { showError(error.message); core.playFailureTone(); }
  }

  function videoConfigurationPayload(invalidateCompilation = false) {
    return {
      video_intention: elements.videoIntention.value,
      compile_model_id: elements.compileLlm.value,
      aspect_ratio: elements.videoRatio.value,
      duration_seconds: Number(elements.videoDuration.value),
      preview_megapixels: Number(elements.videoPreviewMp.value),
      final_megapixels: Number(elements.videoFinalMp.value),
      steps: Number(elements.videoSteps.value),
      seed_locked: elements.videoSeedLocked.checked,
      spectrum_enabled: elements.videoSpectrum.checked,
      music_enabled: elements.videoMusic.checked,
      video_lora_enabled: elements.videoLoraProfile.value === "lora",
      video_lora_name: elements.videoLora.value,
      video_lora_strength: Number(elements.videoLoraStrength.value),
      video_lora_clip_last_layer: elements.videoLoraClip.checked,
      creative_audacity: Number(elements.creativeAudacity.value),
      revision_audacity: Number(elements.revisionAudacity.value),
      invalidate_compilation: invalidateCompilation,
    };
  }

  async function persistVideoConfiguration(invalidateCompilation = false) {
    const payload = await core.request(`/api/production-v2/projects/${state.project.project_id}/video/configuration`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(videoConfigurationPayload(invalidateCompilation)),
    });
    state.project = payload.project;
    state.appliedVideoConfiguration = null;
    render();
  }

  async function regenerateVideoSeed() {
    showError();
    try {
      const payload = await core.request(`/api/production-v2/projects/${state.project.project_id}/video/seed`, { method: "POST" });
      state.project = payload.project;
      state.appliedVideoConfiguration = videoConfigurationSignature(state.project);
      elements.videoSeed.value = state.project.video_configuration.seed || "À créer";
      renderControls();
    } catch (error) { showError(error.message); core.playFailureTone(); }
  }

  async function reviseVideoPrompt() {
    if (!elements.videoInstruction.value.trim()) return;
    const payload = await action(`/api/production-v2/projects/${state.project.project_id}/video/revise`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruction: elements.videoInstruction.value,
        model_id: elements.videoLlm.value,
        feedback_attempt_id: state.project.selected_preview_attempt_id,
        revision_audacity: Number(elements.revisionAudacity.value),
      }),
    }, true);
    if (payload) elements.videoInstruction.value = "";
  }

  async function retryRejectedVideoRevision() {
    await action(`/api/production-v2/projects/${state.project.project_id}/video/revise`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruction: "",
        model_id: elements.videoLlm.value,
        feedback_attempt_id: state.project.selected_preview_attempt_id,
        revision_audacity: Number(elements.revisionAudacity.value),
        repair_rejected: true,
      }),
    }, true);
  }

  async function renderPreview() {
    showError();
    try {
      await persistVideoConfiguration(false);
      await action(`/api/production-v2/projects/${state.project.project_id}/video/previews`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: "",
          model_id: elements.videoLlm.value,
          feedback_attempt_id: state.project.selected_preview_attempt_id,
          revision_audacity: Number(elements.revisionAudacity.value),
        }),
      }, true);
    } catch (error) { showError(error.message); core.playFailureTone(); }
  }

  async function selectPreview(attemptId) {
    await action(`/api/production-v2/projects/${state.project.project_id}/video/previews/${attemptId}/select`, { method: "POST" });
  }

  async function renderFinal() {
    showError();
    try {
      await persistVideoConfiguration(false);
      await action(`/api/production-v2/projects/${state.project.project_id}/video/final`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attempt_id: state.project.selected_preview_attempt_id }),
      }, true);
    } catch (error) { showError(error.message); core.playFailureTone(); }
  }

  async function renderFinalFromPreview(attemptId) {
    const buttons = [...elements.previews.querySelectorAll("button")];
    buttons.forEach((button) => { button.disabled = true; });
    const payload = await action(`/api/production-v2/projects/${state.project.project_id}/video/final`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attempt_id: attemptId }),
    }, true);
    if (!payload) buttons.forEach((button) => { button.disabled = false; });
  }

  async function cancelOperation() {
    await action(`/api/production-v2/projects/${state.project.project_id}/cancel`, { method: "POST" });
  }

  async function action(url, options, poll = false) {
    showError();
    try {
      const payload = await core.request(url, options);
      state.project = payload.project;
      render();
      if (poll || isBusy()) schedulePoll();
      await loadProjects();
      return payload;
    } catch (error) {
      showError(error.message);
      core.playFailureTone();
    }
  }

  function schedulePoll() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = window.setTimeout(poll, isBusy() ? 1000 : 5000);
  }

  async function poll() {
    state.pollTimer = null;
    if (!state.project) return;
    try {
      const previousStatus = state.project.status;
      const payload = await core.request(`/api/production-v2/projects/${state.project.project_id}`);
      state.project = payload.project;
      render();
      if (previousStatus === "busy" && state.project.status === "ready") core.playCompletionTone();
      if (previousStatus === "busy" && ["failed", "cancelled"].includes(state.project.status)) core.playFailureTone();
    } catch (_) { /* a later poll can recover */ }
    schedulePoll();
  }

  function render() {
    const project = state.project;
    elements.createForm.hidden = Boolean(project);
    elements.sidebar.hidden = !project;
    elements.empty.hidden = Boolean(project);
    elements.project.hidden = !project;
    if (!project) return;

    elements.title.textContent = project.name;
    elements.stage.textContent = project.stage.replaceAll("_", " ").toUpperCase();
    const activeTrace = (project.llm_traces || []).find((item) => item.trace_id === project.active_llm_trace_id);
    elements.status.textContent = activeTrace
      ? `● LLM ${activeTrace.sequence}/${activeTrace.total} · ${activeTrace.label} · ${activeTrace.status}`
      : `● ${project.status === "busy" ? project.active_operation || "En cours" : project.status}`;
    elements.status.classList.toggle("failed", project.status === "failed");
    elements.message.textContent = project.error || project.events.at(-1)?.message || "Prêt.";
    elements.route.textContent = project.route.toUpperCase();
    elements.projectSummary.textContent = `${project.source_filename} · ${profileName(project.memory_profile_id)}`;
    elements.projectSource.src = project.source_url;
    elements.projectIntention.textContent = project.intention;
    populateProfiles(elements.memory, project.memory_profile_id);
    if (state.modelProjectId !== project.project_id) {
      window.PanelForgeModelPicker?.select(elements.kreaLlm, project.initial_model_id);
      window.PanelForgeModelPicker?.select(elements.compileLlm, project.video_configuration?.compile_model_id || project.initial_model_id);
      window.PanelForgeModelPicker?.select(elements.videoLlm, project.initial_model_id);
      state.modelProjectId = project.project_id;
    }

    renderStepState();
    renderRecipe();
    renderFeedbackParents();
    renderGuidanceCandidates();
    renderParentContext();
    renderControls();
    renderLlmTraces();
    renderAnchors();
    renderCandidates();
    renderVideo();
    elements.thermalSummary.innerHTML = `<b>Thermique serveur :</b> stop ${project.thermal.stop_temperature_c} °C · reprise ${project.thermal.resume_temperature_c} °C · attente ${project.thermal.cooldown_seconds} s${project.thermal.remote_thermal_latched ? " · refroidissement verrouillé" : ""}.`;
    renderEvents();
  }

  function profileName(profileId) {
    return state.spec?.memory_profiles?.find((item) => item.profile_id === profileId)?.name || profileId;
  }

  function renderStepState() {
    const project = state.project;
    const videoConfig = project.video_configuration || {};
    const recipeDone = Boolean(project.active_recipe);
    const videoActive = project.route !== "pending";
    elements.projectState.textContent = "Validé";
    elements.imageState.textContent = recipeDone ? "Base validée" : (isBusy() && project.active_operation?.startsWith("krea2_") ? "En cours" : "Actif");
    elements.videoState.textContent = videoActive ? (project.h3 ? "Prompt prêt" : "À compiler") : "En attente";
    elements.imageSummary.textContent = recipeDone
      ? `r${project.active_recipe.index} · ${shortName(project.active_recipe.settings.model_name)}`
      : `${project.candidates.length} candidat(s) · recette à calibrer`;
    elements.videoSummary.textContent = videoActive
      ? `${project.route.toUpperCase()} · ${videoConfig.duration_seconds ?? 6} s · Spectrum ${videoConfig.spectrum_enabled === false ? "OFF" : "ON"}`
      : "Ancres attendues";
    if (state.lastStage !== project.stage) {
      elements.projectSection.open = true;
      elements.imageSection.open = ["image_calibration", "anchor_workshop"].includes(project.stage);
      elements.videoSection.open = ["video_prompt", "video_preview", "complete"].includes(project.stage);
      state.lastStage = project.stage;
    }
  }

  function renderRecipe() {
    const recipe = state.project.active_recipe;
    elements.recipeLock.hidden = !recipe;
    if (!recipe) {
      elements.recipeLock.replaceChildren();
      state.appliedRecipeRevisionId = null;
      return;
    }
    if (state.appliedRecipeRevisionId !== recipe.revision_id) {
      applySettingsToControls(recipe.settings);
      state.appliedRecipeRevisionId = recipe.revision_id;
    }
    elements.recipeLock.replaceChildren();
    const copy = document.createElement("div");
    copy.innerHTML = `<b>Base visuelle r${recipe.index}</b><small>${escapeHtml(shortName(recipe.settings.model_name))} · ${escapeHtml(recipe.settings.aspect_ratio)} · ${recipe.settings.megapixels} MP · ${recipe.settings.loras.length} LoRA · réglages encore modifiables</small>`;
    const button = document.createElement("button"); button.type = "button"; button.textContent = "Changer la base"; button.addEventListener("click", unlockRecipe);
    elements.recipeLock.append(copy, button);
  }

  function renderFeedbackParents() {
    const current = elements.feedbackParent.value;
    const candidates = state.project.candidates.filter((item) => (
      item.status === "succeeded" && item.role === elements.role.value
    )).sort((left, right) => right.index - left.index);
    elements.feedbackParent.replaceChildren(option("", "Aucun · nouvelle branche"), ...candidates.map((item) => option(item.candidate_id, `Candidat ${item.index} · ${item.preference}`)));
    if (candidates.some((item) => item.candidate_id === current)) elements.feedbackParent.value = current;
  }

  function renderGuidanceCandidates() {
    const current = elements.guidanceCandidate.value;
    const candidates = state.project.candidates.filter((item) => item.status === "succeeded").sort((left, right) => right.index - left.index);
    elements.guidanceCandidate.replaceChildren(
      option("", "Choisir une image…"),
      ...candidates.map((item) => option(item.candidate_id, `Candidat ${item.index} · ${item.role}`)),
    );
    if (candidates.some((item) => item.candidate_id === current)) elements.guidanceCandidate.value = current;
  }

  function renderParentContext() {
    const parent = state.project?.candidates.find((item) => item.candidate_id === elements.feedbackParent.value);
    const guidance = elements.referenceMode.value === "recipe_and_guidance"
      ? state.project?.candidates.find((item) => item.candidate_id === elements.guidanceCandidate.value)
      : null;
    const preview = parent || guidance;
    elements.parentContext.hidden = !preview?.output_url;
    if (preview?.output_url) {
      elements.parentImage.src = preview.output_url;
      elements.parentTitle.textContent = `${parent ? "Départ" : "Guidage"} · candidat ${preview.index} · ${preview.role}`;
      elements.parentMeta.textContent = `${shortName(preview.settings.model_name)} · ${preview.settings.megapixels} MP`;
      elements.parentImageButton.onclick = () => openImage(preview.output_url, `Candidat ${preview.index}`);
    }
    elements.kreaChat.replaceChildren();
    if (!parent) {
      elements.kreaChat.append(Object.assign(document.createElement("p"), {
        className: "muted",
        textContent: guidance
          ? "Nouvelle branche : cette image est uniquement un guidage visuel explicite."
          : "Nouvelle branche sans historique narratif.",
      }));
      return;
    }
    const lineage = [];
    let current = parent;
    const visited = new Set();
    while (current && !visited.has(current.candidate_id)) {
      visited.add(current.candidate_id); lineage.unshift(current);
      current = state.project.candidates.find((item) => item.candidate_id === current.feedback_parent_id);
    }
    lineage.forEach((item) => {
      const user = document.createElement("article"); user.className = "production-v2-chat-turn user";
      user.innerHTML = `<b>Vous · candidat ${item.index}</b><p>${escapeHtml(item.instruction || (item.index === 1 ? state.project.intention : "Continuer cette direction."))}</p>`;
      elements.kreaChat.append(user);
      (item.conversation || []).forEach((turn) => elements.kreaChat.append(chatTurn(turn, "KREA2")));
    });
    elements.kreaChat.scrollTop = elements.kreaChat.scrollHeight;
  }

  function renderLlmTraces() {
    const traces = [...(state.project?.llm_traces || [])].sort((left, right) => {
      if (left.batch_id === right.batch_id) return left.sequence - right.sequence;
      return String(right.created_at).localeCompare(String(left.created_at));
    });
    const signature = JSON.stringify({
      active: state.project?.active_llm_trace_id || null,
      traces,
    });
    if (signature === state.llmTraceRenderSignature) return;
    state.llmTraceRenderSignature = signature;
    elements.llmTraces.hidden = !traces.length;
    elements.llmTraces.replaceChildren();
    if (!traces.length) return;

    const batches = new Map();
    traces.forEach((trace) => {
      if (!batches.has(trace.batch_id)) batches.set(trace.batch_id, []);
      batches.get(trace.batch_id).push(trace);
    });
    [...batches.values()].forEach((batch, batchIndex) => {
      const active = batch.some((trace) => ["pending", "thinking"].includes(trace.status));
      const videoCompilation = batch.some((trace) => String(trace.purpose || "").startsWith("video_"));
      const group = document.createElement("details");
      group.className = "production-v2-trace-batch";
      group.open = active || batchIndex === 0;
      const summary = document.createElement("summary");
      const succeeded = batch.filter((trace) => trace.status === "succeeded").length;
      summary.textContent = `${videoCompilation ? "Compilation vidéo" : "Appels LLM du batch"} · ${succeeded}/${batch.length} terminés${active ? " · en cours" : ""}`;
      group.append(summary);

      batch.forEach((trace) => {
        const call = document.createElement("details");
        call.className = `production-v2-llm-trace ${trace.status}`;
        call.open = trace.trace_id === state.project.active_llm_trace_id || trace.status === "failed";
        const heading = document.createElement("summary");
        heading.innerHTML = `<b>${trace.sequence}/${trace.total} · ${escapeHtml(trace.label)}</b><span>${escapeHtml(traceStatusLabel(trace.status))}</span>`;
        call.append(heading);

        const meta = document.createElement("small");
        meta.textContent = `Modèle : ${trace.model_id || "à déterminer"}${trace.candidate_id ? ` · candidat ${candidateIndex(trace.candidate_id)}` : ""}`;
        call.append(meta);
        if ((trace.reference_urls || []).length) {
          const references = document.createElement("div");
          references.className = "production-v2-trace-references";
          trace.reference_urls.forEach((url, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.title = `Ouvrir la référence ${index + 1}`;
            const image = document.createElement("img");
            image.src = url;
            image.alt = `Référence LLM ${index + 1}`;
            button.append(image);
            button.addEventListener("click", () => openImage(url, `Référence LLM ${index + 1}`));
            references.append(button);
          });
          call.append(references);
        }
        for (const [label, value] of [
          ["Entrée envoyée", trace.input_text],
          ["Thinking du modèle", trace.thinking],
          ["Output brut", trace.output],
        ]) {
          const content = document.createElement("details");
          content.open = label === "Thinking du modèle" && trace.trace_id === state.project.active_llm_trace_id;
          const contentSummary = document.createElement("summary");
          contentSummary.textContent = label;
          const pre = document.createElement("pre");
          pre.textContent = value || (trace.status === "pending" ? "En attente…" : "Non fourni par le modèle.");
          content.append(contentSummary, pre);
          call.append(content);
        }
        if (trace.error) {
          call.append(Object.assign(document.createElement("p"), {
            className: "error-message",
            textContent: trace.error,
          }));
        }
        group.append(call);
      });
      elements.llmTraces.append(group);
    });
  }

  function candidateIndex(candidateId) {
    return state.project?.candidates.find((item) => item.candidate_id === candidateId)?.index || "—";
  }

  function traceStatusLabel(status) {
    return ({
      pending: "En attente",
      thinking: "Thinking",
      succeeded: "Terminé",
      failed: "Erreur",
      cancelled: "Annulé",
    })[status] || status;
  }

  function chatTurn(turn, label) {
    const article = document.createElement("article");
    article.className = `production-v2-chat-turn ${turn.role || "assistant"}`;
    const heading = document.createElement("b");
    heading.textContent = `${turn.role === "user" ? "Vous" : label}${turn.model_id ? ` · ${shortName(turn.model_id)}` : ""}`;
    article.append(heading);
    if (turn.content) {
      const content = document.createElement("p");
      content.textContent = turn.content;
      article.append(content);
    }
    if ((turn.recommendations || []).length) {
      const section = document.createElement("section");
      const title = document.createElement("strong"); title.textContent = "Recommandations";
      const list = document.createElement("ul");
      turn.recommendations.forEach((value) => list.append(Object.assign(document.createElement("li"), { textContent: value })));
      section.append(title, list); article.append(section);
    }
    if ((turn.questions || []).length) {
      const section = document.createElement("section");
      const title = document.createElement("strong"); title.textContent = "Questions ouvertes";
      const list = document.createElement("ul");
      turn.questions.forEach((value) => list.append(Object.assign(document.createElement("li"), { textContent: value })));
      section.append(title, list); article.append(section);
    }
    if (turn.prompt) {
      const details = document.createElement("details");
      const summary = document.createElement("summary"); summary.textContent = "Voir le prompt proposé";
      const prompt = document.createElement("pre"); prompt.textContent = turn.prompt;
      details.append(summary, prompt); article.append(details);
    }
    return article;
  }

  function videoConfigurationSignature(project) {
    return JSON.stringify({
      configuration: project?.video_configuration || null,
      lora: project?.video_lora || null,
    });
  }

  function compiledVideoDuration(prompt) {
    const patterns = [
      /aligns with the\s+([0-9]+(?:\.[0-9]+)?)-second mark of the target video/i,
      /one continuous(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)-second shot/i,
      /target video is(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)[ -]second/i,
    ];
    for (const pattern of patterns) {
      const match = String(prompt || "").match(pattern);
      const value = match ? Number(match[1]) : NaN;
      if (Number.isFinite(value)) return value;
    }
    return NaN;
  }

  function renderVideoDurationWarning() {
    const compiled = compiledVideoDuration(state.project?.h3?.current_prompt);
    const configured = Number(elements.videoDuration.value);
    let warning = state.project?.h3?.duration_warning || "";
    if (Number.isFinite(compiled) && Number.isFinite(configured)) {
      warning = Math.abs(compiled - configured) < 0.001
        ? ""
        : `Prompt compilé pour ${compiled} s · rendu configuré pour ${configured} s. `
          + "Les timestamps et l’ancre finale ne sont pas réécrits automatiquement.";
    }
    elements.videoDurationWarning.textContent = warning;
    elements.videoDurationWarning.hidden = !warning;
  }

  function renderAudacityValues() {
    elements.creativeAudacityValue.textContent = elements.creativeAudacity.value;
    elements.revisionAudacityValue.textContent = elements.revisionAudacity.value;
  }

  function applyVideoConfiguration(project) {
    const signature = videoConfigurationSignature(project);
    if (state.appliedVideoConfiguration === signature) return;
    const config = project.video_configuration || {};
    elements.videoIntention.value = config.intention || project.intention || "";
    window.PanelForgeModelPicker?.select(elements.compileLlm, config.compile_model_id || project.initial_model_id);
    if ([...elements.videoRatio.options].some((item) => item.value === config.aspect_ratio)) {
      elements.videoRatio.value = config.aspect_ratio;
    }
    elements.videoDuration.value = String(config.duration_seconds ?? 6);
    elements.videoPreviewMp.value = String(config.preview_megapixels ?? 0.2);
    elements.videoFinalMp.value = String(config.final_megapixels ?? 1.2);
    elements.videoSteps.value = String(config.steps ?? 25);
    elements.videoSeed.value = config.seed || "À créer";
    elements.videoSeedLocked.checked = config.seed_locked !== false;
    elements.videoSpectrum.checked = config.spectrum_enabled !== false;
    elements.videoMusic.checked = Boolean(config.music_enabled);
    elements.creativeAudacity.value = String(config.creative_audacity ?? 3);
    elements.revisionAudacity.value = String(config.revision_audacity ?? 3);
    renderAudacityValues();
    elements.videoLoraProfile.value = project.video_lora ? "lora" : "standard";
    if (project.video_lora) {
      if ([...elements.videoLora.options].some((item) => item.value === project.video_lora.name)) {
        elements.videoLora.value = project.video_lora.name;
      }
      elements.videoLoraStrength.value = String(project.video_lora.strength);
      elements.videoLoraClip.checked = project.video_lora.clip_last_layer === -2;
    }
    state.appliedVideoConfiguration = signature;
    renderVideoLoraControls();
  }

  function renderControls() {
    const hasBase = Boolean(state.project?.active_recipe);
    const busy = isBusy();
    const source = iterationSource();
    if (!source && elements.promptStrategy.value === "preserve_current") {
      elements.promptStrategy.value = "rewrite_once";
    }
    const preservePrompt = elements.promptStrategy.value === "preserve_current";
    const loraPlanning = elements.loraAssisted.checked;
    const cost = llmCost();

    elements.promptStrategy.disabled = busy;
    elements.preserveSeed.disabled = busy;
    elements.preserveModel.disabled = busy;
    elements.preserveLoras.disabled = busy;
    elements.renderModel.disabled = busy || elements.preserveModel.checked;
    resourceUi?.syncModelPicker(elements.renderModel);
    elements.renderModelLabel.textContent = elements.preserveModel.checked
      ? "Checkpoint retenu pour tous les candidats"
      : "Checkpoint du candidat 1";
    elements.ratio.disabled = busy;
    elements.imageMp.disabled = busy;
    elements.loraAssisted.disabled = busy || elements.preserveLoras.checked;
    elements.loraInstruction.disabled = busy || !loraPlanning;
    for (const element of elements.loras.querySelectorAll("select,input")) {
      element.disabled = busy || elements.preserveLoras.checked;
    }
    for (const element of [elements.role, elements.count, elements.feedbackParent, elements.referenceMode, elements.guidanceCandidate]) element.disabled = busy;
    elements.guidanceField.hidden = elements.referenceMode.value !== "recipe_and_guidance";
    elements.newRecipeBranch.disabled = busy || !hasBase;
    elements.imageInstruction.disabled = preservePrompt;
    elements.imageInstruction.closest("label")?.classList.toggle("is-disabled", preservePrompt);
    elements.imageInstruction.title = preservePrompt
      ? "Le prompt est conservé strictement : choisissez une autre stratégie pour écrire une direction."
      : "";
    elements.generateImages.disabled = busy || (
      elements.referenceMode.value === "recipe_and_guidance" && !elements.guidanceCandidate.value
    );
    elements.generateImages.textContent = `Lancer · ${cost.count} rendu${cost.count > 1 ? "s" : ""} KREA2 · ${cost.total} appel${cost.total > 1 ? "s" : ""} LLM`;
    elements.generateImages.title = cost.details.length
      ? cost.details.join("\n")
      : "Aucun appel LLM : le prompt et la pile LoRA sont repris sans réécriture.";
    elements.batchCost.textContent = cost.details.length
      ? `${cost.total} appel${cost.total > 1 ? "s" : ""} LLM planifié${cost.total > 1 ? "s" : ""} · survolez pour le détail`
      : "0 appel LLM · prompt et LoRA conservés tels quels";
    elements.batchCost.title = elements.generateImages.title;
    elements.memory.disabled = isBusy();
    elements.compile.disabled = isBusy() || state.project.route === "pending";
    const compilePrefix = state.project.h3 ? "Recompiler" : "Compiler";
    const previewMp = Number(elements.videoPreviewMp.value || 0.2).toLocaleString("fr-FR");
    elements.compile.textContent = `${compilePrefix} Brief → Plan → Prompt + preview ${previewMp} MP`;
    for (const element of [elements.videoIntention, elements.compileLlm, elements.creativeAudacity, elements.revisionAudacity, elements.videoRatio, elements.videoDuration, elements.videoSteps, elements.videoPreviewMp, elements.videoFinalMp, elements.videoSeedLocked, elements.videoSpectrum, elements.videoMusic, elements.videoLoraProfile]) element.disabled = isBusy();
    elements.videoNewSeed.disabled = isBusy();
    renderVideoLoraControls();
    elements.reviseVideo.disabled = isBusy() || !state.project.h3 || !elements.videoInstruction.value.trim();
    elements.videoRevisionRetry.disabled = isBusy() || !state.project.h3?.revision_error;
    elements.renderPreview.disabled = isBusy() || !state.project.h3;
    elements.renderFinal.disabled = isBusy() || !state.project.selected_preview_attempt_id;
    elements.cancel.disabled = !isBusy();
    elements.renderCancel.disabled = !activeVideoAttempt(state.project);
    window.PanelForgeModelPicker?.setDisabled(elements.kreaLlm, busy || cost.total === 0);
    window.PanelForgeModelPicker?.setDisabled(elements.compileLlm, isBusy());
    window.PanelForgeModelPicker?.setDisabled(elements.videoLlm, isBusy());
  }

  function renderAnchors() {
    elements.anchors.replaceChildren();
    const recipe = state.project.active_recipe;
    if (recipe) {
      const candidate = state.project.candidates.find((item) => item.candidate_id === recipe.source_candidate_id);
      const url = recipe.asset_url || candidate?.output_url;
      if (url) {
        const base = document.createElement("figure"); base.className = "production-v2-anchor production-v2-base";
        const image = document.createElement("img"); image.src = url; image.alt = "Base visuelle validée"; image.addEventListener("click", () => openImage(url, "Base visuelle validée"));
        const caption = document.createElement("figcaption");
        caption.innerHTML = `<b>Base visuelle · r${recipe.index}</b><small>${escapeHtml(shortName(recipe.settings.model_name))} · ${recipe.settings.megapixels} MP</small>`;
        const actions = document.createElement("div"); actions.className = "production-v2-base-anchor-actions";
        const hasReferences = state.project.anchors.some((anchor) => anchor.role === "reference");
        for (const [role, label] of [["first_frame", "First frame"], ["last_frame", "Last frame"]]) {
          const alreadyAssigned = state.project.anchors.some((anchor) => anchor.role === role && anchor.asset_id === recipe.asset_id);
          const button = document.createElement("button"); button.type = "button";
          button.textContent = alreadyAssigned ? `✓ ${label}` : `→ ${label}`;
          button.disabled = isBusy() || hasReferences || alreadyAssigned;
          button.title = hasReferences
            ? "Retirez les références Ref2V avant de choisir une First ou Last frame."
            : `Utiliser directement la base visuelle comme ${label}.`;
          button.addEventListener("click", () => promoteAnchor(recipe.source_candidate_id, false, role));
          actions.append(button);
        }
        caption.append(actions);
        base.append(image, caption); elements.anchors.append(base);
      }
    }
    if (!recipe && !state.project.anchors.length) {
      elements.anchors.append(Object.assign(document.createElement("p"), { className: "muted", textContent: "Aucune base. Explorez les candidats puis validez l’image qui servira de socle." }));
      return;
    }
    state.project.anchors.forEach((anchor) => {
      const card = document.createElement("figure"); card.className = "production-v2-anchor";
      const image = document.createElement("img"); image.src = anchor.url; image.alt = anchor.label; image.addEventListener("click", () => openImage(anchor.url, anchor.label));
      const caption = document.createElement("figcaption"); caption.innerHTML = `<b>${escapeHtml(anchor.role)}</b><small>${escapeHtml(anchor.label)}</small>`;
      if (anchor.candidate_id) {
        const rework = document.createElement("button"); rework.type = "button"; rework.textContent = "Retravailler"; rework.disabled = isBusy();
        rework.addEventListener("click", () => {
          const candidate = state.project.candidates.find((item) => item.candidate_id === anchor.candidate_id);
          if (candidate) continueFromCandidate(candidate);
        });
        caption.append(rework);
      }
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Retirer"; remove.disabled = isBusy(); remove.addEventListener("click", () => removeAnchor(anchor.anchor_id));
      caption.append(remove); card.append(image, caption); elements.anchors.append(card);
    });
    const hasReferences = state.project.anchors.some((anchor) => anchor.role === "reference");
    if (recipe && !hasReferences) {
      for (const [role, label] of [["first_frame", "Créer une First frame"], ["last_frame", "Créer une Last frame"]]) {
        if (state.project.anchors.some((anchor) => anchor.role === role)) continue;
        const placeholder = document.createElement("article"); placeholder.className = "production-v2-anchor production-v2-anchor-empty";
        const button = document.createElement("button"); button.type = "button"; button.textContent = `＋ ${label}`; button.disabled = isBusy(); button.addEventListener("click", () => startRoleWorkshop(role));
        placeholder.append(button); elements.anchors.append(placeholder);
      }
    }
  }

  function startRoleWorkshop(role) {
    elements.role.value = role;
    elements.feedbackParent.value = "";
    elements.guidanceCandidate.value = "";
    elements.referenceMode.value = "recipe";
    if (state.project.active_recipe) applySettingsToControls(state.project.active_recipe.settings);
    resetIterationControls();
    state.openWorkshops.add(role);
    state.candidateRenderSignature = null;
    renderFeedbackParents();
    renderGuidanceCandidates();
    elements.imageSection.open = true;
    renderParentContext();
    renderControls();
    renderCandidates();
    elements.imageInstruction.focus();
  }

  function renderCandidates() {
    const signature = JSON.stringify({
      status: state.project.status,
      selectedRole: elements.role.value,
      activeRecipe: state.project.active_recipe || null,
      anchors: state.project.anchors.map((anchor) => ({ anchorId: anchor.anchor_id, role: anchor.role })),
      candidates: state.project.candidates.map((candidate) => ({
        candidateId: candidate.candidate_id,
        status: candidate.status,
        outputUrl: candidate.output_url,
        error: candidate.error,
        preference: candidate.preference,
        comment: candidate.comment,
        prompt: candidate.prompt,
        actualModelId: candidate.actual_model_id,
        seed: candidate.seed,
        kind: candidate.generation_kind,
        batchId: candidate.batch_id,
        promptStrategy: candidate.prompt_strategy,
        referenceMode: candidate.reference_mode,
        guidanceCandidateId: candidate.guidance_candidate_id,
        preserveSeed: candidate.preserve_seed,
        preserveModel: candidate.preserve_model,
        preserveLoras: candidate.preserve_loras,
        assistedLoraNames: candidate.assisted_lora_names,
        assistedLoraRationale: candidate.assisted_lora_rationale,
        instruction: candidate.instruction,
        settings: candidate.settings,
        conversation: candidate.conversation,
      })),
    });
    if (signature === state.candidateRenderSignature) return;

    const activeFeedback = document.activeElement?.matches?.("textarea[data-candidate-feedback]")
      ? {
          candidateId: document.activeElement.dataset.candidateFeedback,
          selectionStart: document.activeElement.selectionStart,
          selectionEnd: document.activeElement.selectionEnd,
        }
      : null;
    elements.candidates.querySelectorAll("textarea[data-candidate-feedback]").forEach((textarea) => {
      state.feedbackDrafts.set(textarea.dataset.candidateFeedback, textarea.value);
    });
    elements.candidates.querySelectorAll("details[data-workshop-role]").forEach((details) => {
      if (details.open) state.openWorkshops.add(details.dataset.workshopRole);
      else state.openWorkshops.delete(details.dataset.workshopRole);
    });
    state.candidateRenderSignature = signature;
    elements.candidates.replaceChildren();
    if (!state.project.candidates.length) {
      elements.candidates.append(Object.assign(document.createElement("p"), { className: "muted", textContent: "Lancez un premier batch pour comparer les checkpoints et LoRA." }));
      return;
    }
    const roleOrder = ["calibration", "first_frame", "last_frame", "reference"];
    const roleLabels = {
      calibration: "Recherche de la base visuelle",
      first_frame: "Recherche de la première frame",
      last_frame: "Recherche de la dernière frame",
      reference: "Recherche de références Ref2V",
    };
    roleOrder.forEach((role) => {
      const candidates = state.project.candidates.filter((candidate) => candidate.role === role).sort((left, right) => right.index - left.index);
      if (!candidates.length) return;
      const workshop = document.createElement("details"); workshop.className = "production-v2-candidate-workshop";
      const roleValidated = role === "calibration"
        ? Boolean(state.project.active_recipe)
        : role !== "reference" && state.project.anchors.some((anchor) => anchor.role === role);
      workshop.dataset.workshopRole = role;
      workshop.open = state.openWorkshops.has(role) || (elements.role.value === role && !roleValidated);
      workshop.addEventListener("toggle", () => {
        if (workshop.open) state.openWorkshops.add(role); else state.openWorkshops.delete(role);
      });
      const succeeded = candidates.filter((candidate) => candidate.status === "succeeded").length;
      const summary = document.createElement("summary");
      summary.innerHTML = `<span><b>${escapeHtml(roleLabels[role])}</b><small>${candidates.length} candidat(s) · ${succeeded} disponible(s)${roleValidated ? " · validé" : ""}</small></span>`;
      workshop.append(summary);
      const grid = document.createElement("div"); grid.className = "production-v2-candidate-grid";
      candidates.forEach((candidate) => {
      const card = document.createElement("article"); card.className = `production-v2-candidate ${candidate.preference}`;
      const head = document.createElement("div"); head.className = "production-v2-candidate-head";
      const kindLabel = candidate.generation_kind === "resolution_clone"
        ? `clone ${Number(candidate.settings.megapixels).toLocaleString("fr-FR")} MP`
        : candidate.generation_kind === "technical_lora"
          ? "comparaison LoRA"
          : candidate.prompt_strategy === "preserve_current"
            ? "comparaison technique"
            : candidate.prompt_strategy === "rewrite_once"
              ? "prompt commun"
              : "exploration chaînée";
      head.innerHTML = `<b>Candidat ${candidate.index} · round ${candidate.round_index}</b><small>${escapeHtml(kindLabel)} · ${escapeHtml(candidate.status)}</small>`;
      card.append(head);
      if (candidate.output_url) {
        const imageButton = document.createElement("button"); imageButton.type = "button"; imageButton.className = "production-v2-image-button";
        const previewRatio = cssAspectRatio(candidate.settings.aspect_ratio);
        if (previewRatio) imageButton.style.setProperty("--production-v2-image-ratio", previewRatio);
        const image = document.createElement("img"); image.src = candidate.output_url; image.alt = `Candidat ${candidate.index}`; imageButton.append(image);
        imageButton.addEventListener("click", () => openImage(candidate.output_url, `Candidat ${candidate.index}`)); card.append(imageButton);
      } else {
        const pending = document.createElement("div"); pending.className = "production-v2-pending"; pending.textContent = candidate.error || (candidate.status === "prompting" ? "LLM · création du prompt…" : candidate.status === "rendering" ? "KREA2 · rendu en cours…" : candidate.status);
        card.append(pending);
      }
      const meta = document.createElement("details");
      const metaSummary = document.createElement("summary");
      metaSummary.className = "production-v2-candidate-meta-summary";
      const recipeSummary = document.createElement("span");
      recipeSummary.className = "production-v2-candidate-recipe-summary";
      recipeSummary.textContent = `${shortName(candidate.settings.model_name)} · ${candidate.settings.megapixels} MP`;
      metaSummary.append(recipeSummary);
      if ((candidate.settings.loras || []).length) {
        const activeLoras = document.createElement("span");
        activeLoras.className = "production-v2-candidate-active-loras";
        (candidate.settings.loras || []).forEach((lora) => {
          const line = document.createElement("span");
          const name = document.createElement("span"); name.textContent = shortName(lora.name); name.title = lora.name;
          const strength = document.createElement("b"); strength.textContent = `: ${lora.strength}`;
          line.append(name, strength); activeLoras.append(line);
        });
        metaSummary.append(activeLoras);
      }
      const promptDetails = document.createElement("pre"); promptDetails.textContent = candidate.prompt || "Prompt en attente";
      const runDetails = document.createElement("small"); runDetails.textContent = `LLM : ${candidate.actual_model_id || candidate.requested_model_id} · seed ${candidate.seed || "—"} · profil ${profileName(candidate.memory_profile_id)}`;
      meta.append(metaSummary, promptDetails, runDetails);
      const policy = document.createElement("small");
      const promptPolicy = ({
        preserve_current: "conservé",
        rewrite_once: "réécrit une fois",
        evolve_between: "évolutif",
      })[candidate.prompt_strategy] || "historique";
      const referencePolicy = ({
        none: "aucune image",
        recipe: "source / R1",
        recipe_and_guidance: "R1 + image choisie",
      })[candidate.reference_mode] || "historique";
      policy.textContent = `Prompt ${promptPolicy} · guidage ${referencePolicy} · conserver seed ${candidate.preserve_seed ? "oui" : "non"}, modèle ${candidate.preserve_model ? "oui" : "non"}, LoRA ${candidate.preserve_loras ? "oui" : "non"}`;
      meta.append(policy);
      const loraList = document.createElement("div"); loraList.className = "production-v2-lora-summary";
      if (!(candidate.settings.loras || []).length) loraList.textContent = "LoRA : aucune";
      else (candidate.settings.loras || []).forEach((lora) => {
        const line = document.createElement("div");
        const name = document.createElement("span"); name.textContent = shortName(lora.name); name.title = lora.name;
        const strength = document.createElement("b"); strength.textContent = `: ${lora.strength}`;
        line.append(name, strength); loraList.append(line);
      });
      meta.append(loraList);
      if (candidate.assisted_lora_rationale) meta.append(Object.assign(document.createElement("small"), { textContent: `Choix assisté : ${candidate.assisted_lora_rationale}` }));
      card.append(meta);
      if (candidate.status === "succeeded") {
        const comment = document.createElement("textarea");
        comment.rows = 2;
        comment.placeholder = "Ce que vous aimez ou voulez corriger…";
        comment.dataset.candidateFeedback = candidate.candidate_id;
        comment.value = state.feedbackDrafts.has(candidate.candidate_id)
          ? state.feedbackDrafts.get(candidate.candidate_id)
          : (candidate.comment || "");
        comment.addEventListener("input", () => state.feedbackDrafts.set(candidate.candidate_id, comment.value));
        card.append(comment);
        const actions = document.createElement("div"); actions.className = "production-v2-card-actions";
        const like = document.createElement("button"); like.type = "button"; like.textContent = "👍 Like"; like.classList.toggle("active", candidate.preference === "like"); like.addEventListener("click", () => reviewCandidate(candidate.candidate_id, "like", comment.value));
        const dislike = document.createElement("button"); dislike.type = "button"; dislike.textContent = "👎 Dislike"; dislike.classList.toggle("active", candidate.preference === "dislike"); dislike.addEventListener("click", () => reviewCandidate(candidate.candidate_id, "dislike", comment.value));
        const parent = document.createElement("button"); parent.type = "button"; parent.textContent = "↳ Continuer depuis cette image"; parent.addEventListener("click", () => continueFromCandidate(candidate));
        actions.append(like, dislike, parent); card.append(actions);
        const promote = document.createElement("div"); promote.className = "production-v2-card-actions";
        [[2.1, "2,1"], [4, "4"]].forEach(([megapixels, label]) => {
          const resolution = document.createElement("button");
          resolution.type = "button";
          resolution.textContent = Number(candidate.settings.megapixels) === megapixels ? `✓ ${label} MP` : `Passer en ${label} MP`;
          resolution.disabled = isBusy() || Number(candidate.settings.megapixels) === megapixels;
          resolution.addEventListener("click", () => cloneAtResolution(candidate.candidate_id, megapixels));
          promote.append(resolution);
        });
        if (role === "calibration") {
          const recipe = document.createElement("button"); recipe.type = "button"; recipe.textContent = state.project.active_recipe?.source_candidate_id === candidate.candidate_id ? "✓ Base active" : "Valider comme base"; recipe.disabled = isBusy(); recipe.addEventListener("click", () => validateRecipe(candidate.candidate_id));
          const direct = document.createElement("button"); direct.type = "button"; direct.textContent = "Utiliser directement en Ref2V"; direct.disabled = isBusy(); direct.addEventListener("click", () => directRef2v(candidate.candidate_id));
          promote.append(recipe, direct);
        } else {
          const anchor = document.createElement("button"); anchor.type = "button";
          const startsDirectRef2v = role === "reference" && !state.project.active_recipe;
          anchor.textContent = startsDirectRef2v
            ? "Démarrer Ref2V avec cette référence"
            : role === "reference" ? "Ajouter aux références Ref2V" : role === "first_frame" ? "Valider First frame" : "Valider Last frame";
          anchor.disabled = isBusy() || (!state.project.active_recipe && !startsDirectRef2v);
          anchor.addEventListener("click", () => startsDirectRef2v
            ? directRef2v(candidate.candidate_id)
            : promoteAnchor(candidate.candidate_id, false, role));
          promote.append(anchor);
        }
        card.append(promote);
      }
      grid.append(card);
      });
      workshop.append(grid); elements.candidates.append(workshop);
    });
    if (activeFeedback) {
      const restored = [...elements.candidates.querySelectorAll("textarea[data-candidate-feedback]")]
        .find((textarea) => textarea.dataset.candidateFeedback === activeFeedback.candidateId);
      if (restored) {
        restored.focus({ preventScroll: true });
        const end = restored.value.length;
        restored.setSelectionRange(
          Math.min(activeFeedback.selectionStart ?? end, end),
          Math.min(activeFeedback.selectionEnd ?? end, end),
        );
      }
    }
  }

  function renderVideo() {
    const project = state.project;
    applyVideoConfiguration(project);
    const config = project.video_configuration || {};
    const ratio = config.aspect_ratio || "9:16 (Portrait Widescreen)";
    const duration = config.duration_seconds ?? 6;
    const previewMp = config.preview_megapixels ?? 0.2;
    const finalMp = config.final_megapixels ?? 1.2;
    const steps = config.steps ?? 25;
    elements.videoContract.innerHTML = `<b>Route ${escapeHtml(project.route.toUpperCase())}</b><span>${escapeHtml(ratio)} · ${duration} s · preview ${previewMp} MP · ${steps} + 3 steps · Spectrum ${config.spectrum_enabled === false ? "OFF" : "ON"} · musique ${config.music_enabled ? "ON" : "OFF"} · conception ${config.creative_audacity ?? 3}/3 · ajustement ${config.revision_audacity ?? 3}/3</span>`;
    elements.renderPreview.textContent = `Lancer un preview ${String(previewMp).replace(".", ",")} MP`;
    elements.renderFinal.textContent = `Rendu final ${String(finalMp).replace(".", ",")} MP`;
    elements.videoSummary.textContent = project.route === "pending"
      ? "Ancres attendues"
      : `${project.route.toUpperCase()} · ${duration} s · Spectrum ${config.spectrum_enabled === false ? "OFF" : "ON"}`;
    renderVideoDurationWarning();

    elements.videoChat.replaceChildren();
    const turns = project.h3?.turns || [];
    if (!turns.length) {
      elements.videoChat.append(Object.assign(document.createElement("p"), {
        className: "muted",
        textContent: "Le premier échange vidéo apparaîtra ici après la compilation.",
      }));
    } else {
      turns.forEach((turn) => elements.videoChat.append(chatTurn(turn, "Assistant vidéo")));
    }
    const rejected = Boolean(project.h3?.revision_error);
    elements.videoRevisionDraft.hidden = !rejected;
    elements.videoRevisionError.textContent = project.h3?.revision_error || "";
    elements.videoRevisionDraftContent.value = project.h3?.revision_draft || "";
    if (rejected) elements.videoRevisionDraft.open = true;

    elements.h3Panel.hidden = !project.h3 && !(project.previews || []).length && !project.final_attempt;
    elements.h3Prompt.textContent = project.h3?.current_prompt || "Compilation en attente.";
    syncRenderProgress(project);

    const mediaSignature = JSON.stringify({
      previews: (project.previews || []).map(videoAttemptSignature),
      final: project.final_attempt ? videoAttemptSignature(project.final_attempt) : null,
      archives: (project.archived_h3_projects || []).map((archive) => ({
        projectId: archive.project_id,
        inputMode: archive.input_mode,
        prompt: archive.current_prompt,
        attempts: (archive.attempts || []).map(videoAttemptSignature),
      })),
    });
    if (mediaSignature === state.videoRenderSignature) return;
    state.videoRenderSignature = mediaSignature;

    elements.previews.replaceChildren();
    [...(project.previews || [])].sort((left, right) => right.index - left.index).forEach((attempt) => {
      const card = document.createElement("article");
      card.className = `production-v2-video ${attempt.selected ? "selected" : ""}`;
      const head = document.createElement("div");
      const title = document.createElement("b"); title.textContent = `Preview ${attempt.index}`;
      const summary = document.createElement("small");
      summary.textContent = `${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps · Spectrum ${attempt.spectrum_enabled ? "ON" : "OFF"}`;
      head.append(title, summary); card.append(head);
      if (attempt.output_url) {
        const video = document.createElement("video");
        video.controls = true; video.preload = "metadata"; video.src = attempt.output_url;
        card.append(video);
        const choose = document.createElement("button"); choose.type = "button";
        choose.textContent = attempt.selected ? "✓ Preview sélectionné" : "Sélectionner";
        choose.disabled = isBusy();
        choose.addEventListener("click", () => selectPreview(attempt.attempt_id));
        const highResolution = document.createElement("button"); highResolution.type = "button";
        highResolution.textContent = `Générer en ${String(finalMp).replace(".", ",")} MP`;
        highResolution.disabled = isBusy();
        highResolution.title = "Reprend le prompt, la seed et tous les réglages de cette preview ; seuls les mégapixels passent au niveau final.";
        highResolution.addEventListener("click", () => renderFinalFromPreview(attempt.attempt_id));
        const actions = document.createElement("div"); actions.className = "production-v2-card-actions";
        actions.append(choose, highResolution); card.append(actions);
      } else {
        const pending = document.createElement("p"); pending.className = "muted";
        pending.textContent = attempt.error || videoAttemptStatus(attempt.status);
        card.append(pending);
      }
      card.append(videoAttemptDetails(attempt));
      elements.previews.append(card);
    });

    elements.final.replaceChildren();
    if (project.final_attempt) {
      const title = document.createElement("h3");
      title.textContent = `Livrable final · ${project.final_attempt.settings.megapixels || finalMp} MP`;
      elements.final.append(title);
      if (project.final_attempt.output_url) {
        const video = document.createElement("video");
        video.controls = true; video.preload = "metadata"; video.src = project.final_attempt.output_url;
        elements.final.append(video);
      } else {
        elements.final.append(Object.assign(document.createElement("p"), {
          className: "muted",
          textContent: project.final_attempt.error || videoAttemptStatus(project.final_attempt.status),
        }));
      }
      elements.final.append(videoAttemptDetails(project.final_attempt));
    }

    const archives = [...(project.archived_h3_projects || [])].reverse();
    elements.archives.hidden = !archives.length;
    elements.archivesList.replaceChildren();
    archives.forEach((archive, archiveIndex) => {
      const block = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = `Version vidéo archivée ${archives.length - archiveIndex} · ${archive.input_mode.toUpperCase()} · ${archive.attempts.length} rendu(s)`;
      const prompt = document.createElement("pre"); prompt.textContent = archive.current_prompt;
      const media = document.createElement("div"); media.className = "production-v2-archive-videos";
      [...archive.attempts].sort((left, right) => right.index - left.index).filter((attempt) => attempt.output_url).forEach((attempt) => {
        const video = document.createElement("video");
        video.controls = true; video.preload = "metadata"; video.src = attempt.output_url;
        media.append(video);
      });
      block.append(summary, prompt, media); elements.archivesList.append(block);
    });
  }

  function videoAttemptSignature(attempt) {
    return {
      id: attempt.attempt_id,
      index: attempt.index,
      status: attempt.status,
      output: attempt.output_url,
      error: attempt.error,
      selected: attempt.selected,
      settings: attempt.settings,
      music: attempt.music_enabled,
      spectrum: attempt.spectrum_enabled,
      lora: attempt.video_lora,
    };
  }

  function videoAttemptStatus(status) {
    return ({
      created: "Préparation du rendu…",
      queued: "Rendu placé en file…",
      running: "Génération H3 en cours…",
      cancel_pending: "Annulation demandée…",
      failed: "Le rendu a échoué.",
      cancelled: "Le rendu a été annulé.",
    })[status] || status;
  }

  function videoAttemptDetails(attempt) {
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "Réglages et prompt utilisés";
    const settings = document.createElement("small");
    settings.textContent = `${attempt.settings.aspect_ratio} · ${attempt.settings.duration_seconds} s · seed ${attempt.settings.seed} · musique ${attempt.music_enabled ? "ON" : "OFF"}`;
    details.append(summary, settings);
    if (attempt.video_lora) {
      const lora = document.createElement("small");
      lora.textContent = `LoRA ${shortName(attempt.video_lora.name)} : ${attempt.video_lora.strength}${attempt.video_lora.clip_last_layer === -2 ? " · CLIP −2" : ""}`;
      lora.title = attempt.video_lora.name;
      details.append(lora);
    }
    if (attempt.warnings?.length) {
      const warning = document.createElement("p");
      warning.className = "warning-text";
      warning.textContent = attempt.warnings.join(" · ");
      details.append(warning);
    }
    const promptLabel = document.createElement("strong"); promptLabel.textContent = "Prompt réellement envoyé";
    const prompt = document.createElement("pre");
    prompt.textContent = attempt.effective_prompt || attempt.prompt;
    details.append(promptLabel, prompt);
    return details;
  }

  function elapsedLabel(startedAt) {
    const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function resetRenderPreview() {
    if (state.renderPreviewUrl) URL.revokeObjectURL(state.renderPreviewUrl);
    state.renderPreviewUrl = null;
    elements.renderLivePreview.removeAttribute("src");
    elements.renderLivePreview.hidden = true;
    elements.renderLiveEmpty.hidden = false;
    elements.renderLiveEmpty.textContent = "En attente des premières images du rendu.";
  }

  function showRenderPreview(url, ownedObjectUrl = false) {
    if (state.renderPreviewUrl) URL.revokeObjectURL(state.renderPreviewUrl);
    state.renderPreviewUrl = ownedObjectUrl ? url : null;
    elements.renderLivePreview.src = url;
    elements.renderLivePreview.hidden = false;
    elements.renderLiveEmpty.hidden = true;
  }

  function setRenderPreviewBlob(blob) {
    showRenderPreview(URL.createObjectURL(blob), true);
  }

  function binaryRenderPreview(buffer) {
    const view = new DataView(buffer);
    if (buffer.byteLength >= 8 && view.getUint32(0, false) !== 1) return;
    const format = buffer.byteLength >= 8 ? view.getUint32(4, false) : 1;
    const mime = format === 2 ? "image/png" : format === 3 ? "image/webp" : "image/jpeg";
    setRenderPreviewBlob(new Blob([buffer.byteLength > 8 ? buffer.slice(8) : buffer], { type: mime }));
  }

  function base64RenderPreview(value, mime = "image/jpeg") {
    let encoded = String(value || "").trim();
    const dataUrl = encoded.match(/^data:([^;,]+);base64,(.*)$/s);
    if (dataUrl) { mime = dataUrl[1]; encoded = dataUrl[2]; }
    encoded = encoded.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    while (encoded.length % 4) encoded += "=";
    const decoded = window.atob(encoded);
    const bytes = new Uint8Array(decoded.length);
    for (let index = 0; index < decoded.length; index += 1) bytes[index] = decoded.charCodeAt(index);
    setRenderPreviewBlob(new Blob([bytes], { type: mime }));
  }

  function paintRenderProgress() {
    const data = state.renderProgressData;
    if (!data || !elements.renderProgress) return;
    const percent = Math.max(0, Math.min(100, Number(data.percent) || 0));
    const steps = Number(data.current_step) > 0 && Number(data.total_steps) > 0
      ? `step ${data.current_step} / ${data.total_steps} · ` : "";
    const estimate = data.estimated === false ? "" : " estimé";
    elements.renderProgress.hidden = false;
    elements.renderProgressPhase.textContent = data.phase_label || "Rendu H3 en cours";
    elements.renderProgressBar.value = percent;
    elements.renderProgressMeta.textContent = `${steps}${Math.round(percent)} %${estimate} · écoulé ${elapsedLabel(state.renderProgressStartedAt || Date.now())}`;
  }

  function stopRenderProgressClock() {
    if (state.renderProgressTimer !== null) window.clearInterval(state.renderProgressTimer);
    state.renderProgressTimer = null;
  }

  function closeRenderSocket() {
    const socket = state.renderSocket;
    state.renderSocket = null;
    if (socket) socket.close();
  }

  function beginRenderProgress(attempt) {
    if (state.renderAttemptId !== attempt.attempt_id) {
      closeRenderSocket();
      stopRenderProgressClock();
      resetRenderPreview();
      state.renderAttemptId = attempt.attempt_id;
      state.renderProgressStartedAt = Date.now();
      state.renderProgressData = { phase_label: "Préparation des modèles", percent: 0, estimated: true };
    }
    if (state.renderProgressTimer === null) state.renderProgressTimer = window.setInterval(paintRenderProgress, 1000);
    paintRenderProgress();
  }

  function finishRenderProgress(attempt) {
    if (!attempt || state.renderAttemptId !== attempt.attempt_id) return;
    stopRenderProgressClock();
    closeRenderSocket();
    if (attempt.status === "succeeded") {
      state.renderProgressData = { phase_label: "Terminé", percent: 100, estimated: false };
    } else if (["failed", "cancelled"].includes(attempt.status)) {
      state.renderProgressData = {
        ...(state.renderProgressData || {}),
        phase_label: attempt.status === "cancelled" ? "Rendu annulé" : "Rendu interrompu",
      };
    }
    paintRenderProgress();
  }

  function connectRenderProgress(attempt) {
    if (!attempt?.events_url || state.renderSocket) return;
    const target = new URL(attempt.events_url, window.location.href);
    target.protocol = target.protocol === "https:" ? "wss:" : "ws:";
    try {
      const socket = new WebSocket(target.href);
      socket.binaryType = "arraybuffer";
      state.renderSocket = socket;
      socket.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) {
          binaryRenderPreview(event.data);
          return;
        }
        if (typeof event.data !== "string") return;
        let payload = null;
        try { payload = JSON.parse(event.data); } catch (_) { return; }
        const data = payload.data || payload;
        const eventExecutionId = data.prompt_id || payload.prompt_id || data.execution_id;
        if (eventExecutionId && attempt.execution_id && eventExecutionId !== attempt.execution_id) return;
        if (payload.type === "panelforge_render_progress") {
          state.renderProgressData = data;
          paintRenderProgress();
        } else if (payload.type === "kj_preview_override" && data.image) {
          base64RenderPreview(data.image, data.mime);
        } else if (payload.type === "preview" && (data.preview_url || data.url || data.data_url)) {
          showRenderPreview(data.preview_url || data.url || data.data_url);
        } else if (payload.type === "panelforge_preview_status" && data.status === "error" && elements.renderLivePreview.hidden) {
          elements.renderLiveEmpty.textContent = data.message || "Aperçu live indisponible ; le rendu continue.";
        }
      });
      socket.addEventListener("close", () => { if (state.renderSocket === socket) state.renderSocket = null; });
      socket.addEventListener("error", () => { if (state.renderSocket === socket) state.renderSocket = null; });
    } catch (_) { state.renderSocket = null; }
  }

  function activeVideoAttempt(project) {
    if (!project) return null;
    const attempts = [...(project.previews || [])];
    if (project.final_attempt) attempts.push(project.final_attempt);
    return attempts.reverse().find((attempt) => ["created", "queued", "running", "cancel_pending"].includes(attempt.status)) || null;
  }

  function syncRenderProgress(project) {
    const active = activeVideoAttempt(project);
    if (active) {
      beginRenderProgress(active);
      connectRenderProgress(active);
      return;
    }
    const attempts = [...(project.previews || [])];
    if (project.final_attempt) attempts.push(project.final_attempt);
    const relevant = attempts.find((attempt) => attempt.attempt_id === state.renderAttemptId);
    if (relevant) {
      finishRenderProgress(relevant);
    } else {
      elements.renderProgress.hidden = true;
      closeRenderSocket();
      stopRenderProgressClock();
      state.renderAttemptId = null;
      state.renderProgressData = null;
      resetRenderPreview();
    }
  }

  function renderEvents() {
    elements.events.replaceChildren();
    [...state.project.events].reverse().forEach((event) => {
      const item = document.createElement("li"); item.className = event.level;
      const date = new Date(event.timestamp);
      item.innerHTML = `<small>${Number.isNaN(date.valueOf()) ? "" : date.toLocaleTimeString("fr-FR")} · ${escapeHtml(event.stage)}</small><span>${escapeHtml(event.message)}</span>`;
      elements.events.append(item);
    });
  }

  function openImage(url, title) {
    elements.dialogTitle.textContent = title;
    elements.dialogContent.src = url;
    elements.dialog.showModal();
  }

  function showError(message = "", creation = false) {
    const target = creation ? elements.createError : elements.actionError;
    target.textContent = message;
    target.hidden = !message;
  }

  function shortName(value) {
    return String(value || "").replaceAll("\\", "/").split("/").at(-1);
  }

  function cssAspectRatio(value) {
    const match = String(value || "").match(/(\d+(?:\.\d+)?)\s*[:x/]\s*(\d+(?:\.\d+)?)/i);
    if (!match || Number(match[1]) <= 0 || Number(match[2]) <= 0) return "";
    return `${Number(match[1])} / ${Number(match[2])}`;
  }

  function escapeHtml(value) {
    const span = document.createElement("span"); span.textContent = String(value ?? ""); return span.innerHTML;
  }
})();
