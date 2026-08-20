(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  const quickPipeline = window.PanelForgeQuickPipeline;
  if (!core || !quickPipeline) return;
  const $ = (selector) => document.querySelector(selector);
  const profileId = "minimax.h3.fl2va.direct";
  const profileVersion = "0.1.0";
  const legacyProfileId = "minimax.h3.i2v.direct";
  const cookbookId = "minimax.h3.fl2va.direct";
  const preferredCookbookVersion = "0.1.0";

  const state = {
    spec: null,
    cookbooks: [],
    cookbook: null,
    firstFile: null,
    lastFile: null,
    firstPreviewUrl: null,
    lastPreviewUrl: null,
    forkSource: null,
    session: null,
    composition: null,
    busy: false,
    quickRunning: false,
    compoundRunning: false,
    quickRecord: null,
    openRequestId: 0,
    openingSessionId: null,
    arbitrationDecisions: {},
    arbitrationRevisionId: null,
  };

  const elements = {
    form: $("#i2vd-session-form"),
    model: $("#i2vd-model"),
    refreshModels: $("#i2vd-refresh-models"),
    cookbook: $("#i2vd-cookbook"),
    activeCookbook: $("#i2vd-active-cookbook"),
    imageInput: $("#i2vd-image-input"),
    uploadPreview: $("#i2vd-upload-preview"),
    uploadTitle: $("#i2vd-upload-title"),
    uploadCaption: $("#i2vd-upload-caption"),
    lastImageInput: $("#i2vd-last-image-input"),
    lastUploadPreview: $("#i2vd-last-upload-preview"),
    lastUploadTitle: $("#i2vd-last-upload-title"),
    lastUploadCaption: $("#i2vd-last-upload-caption"),
    inputMode: $("#i2vd-input-mode"),
    intention: $("#i2vd-intention"),
    freedom: $("#i2vd-freedom"),
    freedomLabel: $("#i2vd-freedom-label"),
    start: $("#i2vd-start"),
    setupMessage: $("#i2vd-setup-message"),
    quickMode: $("#i2vd-quick-mode"),
    quickStatus: $("#i2vd-quick-status"),
    quickStatusLabel: $("#i2vd-quick-status-label"),
    quickResume: $("#i2vd-quick-resume"),
    showReasoning: $("#i2vd-show-reasoning"),
    reasoningPanel: $("#i2vd-reasoning-panel"),
    reasoningLabel: $("#i2vd-reasoning-label"),
    reasoningOutput: $("#i2vd-reasoning-output"),
    reasoningEmpty: $("#i2vd-reasoning-empty"),
    refreshSessions: $("#i2vd-refresh-sessions"),
    sessionList: $("#i2vd-session-list"),
    empty: $("#i2vd-empty"),
    editor: $("#i2vd-editor"),
    sessionTitle: $("#i2vd-session-title"),
    sessionConfig: $("#i2vd-session-config"),
    progress: $("#i2vd-session-progress"),
    newSession: $("#i2vd-new-session"),
    forkSession: $("#i2vd-fork-session"),
    dock: $("#i2vd-reference-dock"),
    steps: {
      brief: $("#i2vd-brief-step"),
      plan: $("#i2vd-plan-step"),
      prompt: $("#i2vd-prompt-step"),
    },
    chips: {
      brief: $("#i2vd-chip-brief"),
      plan: $("#i2vd-chip-plan"),
      prompt: $("#i2vd-chip-prompt"),
    },
    brief: stage("brief"),
    plan: stage("plan"),
    prompt: stage("prompt"),
    copyPrompt: $("#i2vd-copy-prompt"),
    promptReferences: $("#i2vd-prompt-references"),
    arbitrations: $("#i2vd-arbitrations"),
    arbitrationList: $("#i2vd-arbitration-list"),
    arbitrationInstruction: $("#i2vd-arbitration-instruction"),
    acceptAllArbitrations: $("#i2vd-accept-all-arbitrations"),
    applyArbitrations: $("#i2vd-apply-arbitrations"),
    applyApproveArbitrations: $("#i2vd-apply-approve-arbitrations"),
  };

  const reasoningTrace = core.createReasoningTrace({
    toggle: elements.showReasoning,
    panel: elements.reasoningPanel,
    label: elements.reasoningLabel,
    output: elements.reasoningOutput,
    empty: elements.reasoningEmpty,
  });

  function stage(name) {
    return {
      review: $(`#i2vd-${name}-review`),
      generate: $(`#i2vd-generate-${name}`),
      save: $(`#i2vd-save-${name}`),
      approve: $(`#i2vd-approve-${name}`),
      content: $(`#i2vd-${name}-content`),
      message: $(`#i2vd-${name}-message`),
      instruction: $(`#i2vd-${name}-instruction`),
      rewrite: $(`#i2vd-rewrite-${name}`),
      rewriteApprove: $(`#i2vd-rewrite-approve-${name}`),
      lint: $(`#i2vd-${name}-lint`),
      stream: {
        container: $(`#i2vd-${name}-stream-state`),
        label: $(`#i2vd-${name}-stream-label`),
        percent: $(`#i2vd-${name}-stream-percent`),
        progress: $(`#i2vd-${name}-stream-progress`),
      },
    };
  }

  async function initialize() {
    try {
      const [spec, cookbooks] = await Promise.all([
        core.request("/api/prompt-lab/spec"),
        core.request("/api/prompt-lab/cookbooks"),
      ]);
      state.spec = spec;
      state.cookbooks = cookbooks.cookbooks || [];
      populateCookbooks();
      if (!selectedProfile()) throw new Error("Profil H3 Base indisponible.");
      if (!state.cookbook) throw new Error("Recette H3 Base indisponible.");
      await Promise.all([loadModels(), loadSessions()]);
      render();
    } catch (error) {
      showSetupMessage(error.message);
    }
  }

  function selectedProfile() {
    return state.spec && (state.spec.profiles || []).find(
      (item) => item.id === profileId && item.version === profileVersion,
    );
  }

  function directCookbooks() {
    return state.cookbooks.filter(
      (item) => item.id === cookbookId && item.target_mode === "fl2va_direct",
    );
  }

  function populateCookbooks() {
    const available = directCookbooks();
    elements.cookbook.replaceChildren();
    [...available].reverse().forEach((cookbook) => {
      const option = document.createElement("option");
      option.value = cookbook.version;
      option.textContent = `${cookbook.version} — ${cookbook.display_name}`;
      elements.cookbook.append(option);
    });
    state.cookbook = available.find(
      (item) => item.version === preferredCookbookVersion,
    ) || available.at(-1) || null;
    elements.cookbook.value = state.cookbook ? state.cookbook.version : "";
  }

  function activeCookbookSpec() {
    const reference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    if (!reference) return null;
    return state.cookbooks.find(
      (item) => item.id === reference.id && item.version === reference.version,
    ) || null;
  }

  async function loadModels() {
    const selected = elements.model.value;
    const payload = await core.request("/api/prompt-lab/models");
    window.PanelForgeModelPicker.populate(elements.model, payload.models || [], selected);
  }

  async function loadSessions() {
    const payload = await core.request("/api/prompt-lab/sessions?limit=30");
    const sessions = (payload.sessions || []).filter(
      (item) => item.profile && (
        (item.session_mode === "h3_base" && item.profile.id === profileId)
        || (item.session_mode === "direct_multimodal" && item.profile.id === legacyProfileId)
      ),
    );
    elements.sessionList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun parcours H3 Base enregistré.";
      elements.sessionList.append(empty);
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = sessionInputModeLabel(session);
      const detail = document.createElement("small");
      detail.textContent = session.brief_complete ? "Brief validé" : "Brief à préparer";
      button.append(title, detail);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  function selectModel(modelId) {
    if (!modelId) return;
    let option = [...elements.model.options].find((item) => item.value === modelId);
    if (!option) {
      option = document.createElement("option");
      option.value = modelId;
      option.textContent = `${modelId} · modèle du parcours`;
      option.dataset.sessionModel = "true";
      elements.model.append(option);
    }
    elements.model.value = modelId;
  }

  function referenceForRole(session, role) {
    return session && (session.references || []).find((item) => item.role === role) || null;
  }

  function sessionInputModeLabel(session) {
    const first = Boolean(referenceForRole(session, "first_frame"));
    const last = Boolean(referenceForRole(session, "last_frame"));
    if (first && last) return "Première + dernière frame · FL2VA";
    if (first) return "Première frame · I2VA";
    if (last) return "Dernière frame · L2VA";
    return "Texte seul · T2VA";
  }

  function currentInputModeLabel() {
    const source = state.forkSource;
    const first = Boolean(state.firstFile || referenceForRole(source, "first_frame"));
    const last = Boolean(state.lastFile || referenceForRole(source, "last_frame"));
    if (first && last) return "Mode détecté : FL2VA · première + dernière frame";
    if (first) return "Mode détecté : I2VA · première frame";
    if (last) return "Mode détecté : L2VA · dernière frame";
    return "Mode détecté : T2VA · texte seul";
  }

  function showReferencePreview(slot, reference, caption) {
    const first = slot === "first";
    const urlKey = first ? "firstPreviewUrl" : "lastPreviewUrl";
    const fileKey = first ? "firstFile" : "lastFile";
    const input = first ? elements.imageInput : elements.lastImageInput;
    const preview = first ? elements.uploadPreview : elements.lastUploadPreview;
    const title = first ? elements.uploadTitle : elements.lastUploadTitle;
    const captionNode = first ? elements.uploadCaption : elements.lastUploadCaption;
    if (state[urlKey]) URL.revokeObjectURL(state[urlKey]);
    state[urlKey] = null;
    state[fileKey] = null;
    input.value = "";
    if (!reference) {
      preview.removeAttribute("src");
      preview.hidden = true;
      title.textContent = first ? "Ajouter une première frame" : "Ajouter une dernière frame";
      captionNode.textContent = "Facultatif · PNG, JPEG ou WebP · 25 Mio maximum";
      return;
    }
    preview.src = reference.content_url;
    preview.hidden = false;
    title.textContent = reference.label;
    captionNode.textContent = caption;
  }

  async function openSession(sessionSummary) {
    if (state.quickRunning) return;
    const sessionId = sessionSummary.id;
    const requestId = ++state.openRequestId;
    state.openingSessionId = sessionId;
    render();
    try {
      const [session, compositionPayload] = await Promise.all([
        core.request(`/api/prompt-lab/sessions/${sessionId}`),
        core.request(`/api/prompt-lab/sessions/${sessionId}/composition`).catch(() => null),
      ]);
      if (requestId !== state.openRequestId) return;
      clearStageDrafts();
      state.forkSource = null;
      state.session = session;
      state.composition = compositionPayload ? compositionPayload.composition : null;
      state.quickRecord = quickPipeline.load(session.id);
      selectModel(session.model_id);
      showReferencePreview("first", referenceForRole(session, "first_frame"), "Première frame de ce parcours");
      showReferencePreview("last", referenceForRole(session, "last_frame"), "Dernière frame de ce parcours");
      if (session.active_brief) {
        elements.intention.value = session.active_brief.source_text || "";
        setFreedom(session.active_brief.creative_freedom ?? 35);
      } else {
        elements.intention.value = "";
        setFreedom(35);
      }
    } catch (error) {
      if (requestId === state.openRequestId) showSetupMessage(error.message);
    } finally {
      if (requestId === state.openRequestId) {
        state.openingSessionId = null;
        render();
      }
    }
  }

  function prepareFork() {
    if (!state.session || state.openingSessionId || interactionLocked()) return;
    const source = state.session;
    const sourceCookbook = state.composition && state.composition.cookbook;
    const matchingCookbook = sourceCookbook && directCookbooks().find(
      (item) => item.id === sourceCookbook.id && item.version === sourceCookbook.version,
    );
    if (matchingCookbook) state.cookbook = matchingCookbook;
    state.forkSource = source;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    resetArbitrations();
    selectModel(source.model_id);
    showReferencePreview("first", referenceForRole(source, "first_frame"), "Première frame réutilisée");
    showReferencePreview("last", referenceForRole(source, "last_frame"), "Dernière frame réutilisée");
    const brief = source.active_brief;
    elements.intention.value = brief ? brief.source_text || "" : "";
    setFreedom(brief ? brief.creative_freedom ?? 35 : 35);
    elements.quickMode.checked = false;
    clearStageDrafts();
    showSetupMessage("");
    render();
    elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function selectFile(slot) {
    const first = slot === "first";
    const input = first ? elements.imageInput : elements.lastImageInput;
    const preview = first ? elements.uploadPreview : elements.lastUploadPreview;
    const title = first ? elements.uploadTitle : elements.lastUploadTitle;
    const caption = first ? elements.uploadCaption : elements.lastUploadCaption;
    const urlKey = first ? "firstPreviewUrl" : "lastPreviewUrl";
    const fileKey = first ? "firstFile" : "lastFile";
    const file = input.files && input.files[0];
    if (!file) return;
    if (state[urlKey]) URL.revokeObjectURL(state[urlKey]);
    state[fileKey] = file;
    state[urlKey] = URL.createObjectURL(file);
    preview.src = state[urlKey];
    preview.hidden = false;
    title.textContent = file.name;
    caption.textContent = `${Math.ceil(file.size / 1024)} Kio · cliquer pour remplacer`;
    showSetupMessage("");
    render();
  }

  function setupValidationError() {
    if (!selectedProfile() || !state.cookbook) return "Le profil Direct est encore en cours de chargement.";
    if (!elements.model.value) return "Choisissez un modèle multimodal.";
    if (!elements.intention.value.trim()) return "Décrivez votre intention.";
    return "";
  }

  async function createSession(event) {
    event.preventDefault();
    const error = setupValidationError();
    if (error) return showSetupMessage(error);
    const forkSource = state.forkSource;
    const quickRequested = elements.quickMode.checked;
    let created = false;
    setBusy(true);
    try {
      if (forkSource) {
        state.session = await core.request(
          `/api/prompt-lab/sessions/${forkSource.id}/fork`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              model_id: elements.model.value,
              profile_id: profileId,
              profile_version: profileVersion,
            }),
          },
        );
      } else {
        const profile = selectedProfile();
        const body = new FormData();
        if (state.firstFile) {
          body.append("images", state.firstFile, state.firstFile.name);
          body.append("roles", "first_frame");
          body.append("usages", "first_frame");
          body.append("evidence_policies", "full");
        }
        if (state.lastFile) {
          body.append("images", state.lastFile, state.lastFile.name);
          body.append("roles", "last_frame");
          body.append("usages", "last_frame");
          body.append("evidence_policies", "full");
        }
        body.append("model_id", elements.model.value);
        body.append("profile_id", profile.id);
        body.append("profile_version", profile.version);
        state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      }
      state.forkSource = null;
      state.composition = null;
      state.quickRecord = null;
      created = true;
      render();
      await loadSessions();
      elements.brief.message.textContent = "Parcours créé. Lancez le Brief quand vous êtes prêt.";
    } catch (creationError) {
      showSetupMessage(creationError.message);
    } finally {
      setBusy(false);
    }
    if (created && quickRequested) await runQuickMode();
  }

  function freedomMode(value) {
    if (value <= 20) return ["Factuel strict", "N’ajoute aucun détail absent des entrées."];
    if (value <= 40) return ["Conservateur", "Seulement des liaisons minimales et évidentes."];
    if (value <= 60) return ["Équilibré", "Quelques propositions cinématographiques compatibles."];
    if (value <= 80) return ["Cinématographique", "Enrichit caméra, rythme et ambiance sans contredire les contraintes."];
    return ["Exploratoire", "Propose librement des détails compatibles et les signale comme libertés."];
  }

  function setFreedom(value) {
    const parsed = Number(value);
    const normalized = Number.isInteger(parsed) && parsed >= 0 && parsed <= 100 ? parsed : 35;
    const previousLegacy = elements.freedom.querySelector("option[data-legacy-freedom]");
    if (previousLegacy) previousLegacy.remove();
    const exactOption = [...elements.freedom.options].find((option) => Number(option.value) === normalized);
    if (!exactOption) {
      const [label, description] = freedomMode(normalized);
      const legacyOption = document.createElement("option");
      legacyOption.value = String(normalized);
      legacyOption.dataset.legacyFreedom = "true";
      legacyOption.dataset.description = description;
      legacyOption.textContent = `${label} · valeur historique ${normalized}/100`;
      elements.freedom.append(legacyOption);
    }
    elements.freedom.value = String(normalized);
    updateFreedom();
  }

  function updateFreedom() {
    const selected = elements.freedom.selectedOptions[0];
    const legacyOption = elements.freedom.querySelector("option[data-legacy-freedom]");
    if (legacyOption && legacyOption !== selected) legacyOption.remove();
    const [, fallback] = freedomMode(Number(elements.freedom.value));
    elements.freedomLabel.textContent = selected && selected.dataset.description
      ? selected.dataset.description : fallback;
  }

  function interactionLocked() {
    return state.busy || state.quickRunning || state.compoundRunning
      || Boolean(state.openingSessionId);
  }

  function currentBriefInputs() {
    const brief = state.session && state.session.active_brief;
    return Boolean(brief
      && (brief.source_text || "").trim() === elements.intention.value.trim()
      && Number(brief.creative_freedom) === Number(elements.freedom.value));
  }

  function generatedDocument(documentState) {
    return Boolean(documentState && documentState.active_revision_id
      && !documentState.stale && !documentState.blocked_reason
      && !(documentState.validation_errors || []).length);
  }

  function quickSnapshot() {
    const documents = state.composition ? state.composition.documents || {} : {};
    const plan = documents.beat_sheet || null;
    const prompt = documents.final_prompt || null;
    const briefGenerated = currentBriefInputs();
    const briefApproved = Boolean(briefGenerated && state.session.brief_complete);
    const planGenerated = Boolean(briefApproved && generatedDocument(plan));
    const planApproved = Boolean(planGenerated && plan.complete);
    const promptGenerated = Boolean(planApproved && generatedDocument(prompt));
    return {
      briefGenerated,
      briefApproved,
      planGenerated,
      planApproved,
      promptGenerated,
      promptApproved: Boolean(promptGenerated && prompt.complete),
    };
  }

  function renderQuickStatus() {
    elements.quickMode.disabled = interactionLocked() || Boolean(state.session);
    const record = state.quickRecord;
    elements.quickStatus.hidden = !record;
    if (!record) return;
    const completedBecameIncomplete = record.status === "completed"
      && state.session && !quickSnapshot().promptApproved;
    const visibleStatus = completedBecameIncomplete ? "interrupted" : record.status;
    elements.quickStatus.className = `quick-mode-status ${visibleStatus}`;
    elements.quickResume.hidden = !["stopped", "interrupted"].includes(visibleStatus);
    elements.quickResume.disabled = interactionLocked();
    if (completedBecameIncomplete) {
      elements.quickStatusLabel.textContent = "Parcours modifié après le mode rapide · reprise disponible.";
    } else if (record.status === "running") {
      elements.quickStatusLabel.textContent = `Mode rapide · ${record.stepLabel}…`;
    } else if (record.status === "completed") {
      elements.quickStatusLabel.textContent = "Mode rapide terminé · Prompt validé.";
    } else {
      elements.quickStatusLabel.textContent = `Mode rapide arrêté à « ${record.stepLabel} »${record.error ? ` · ${record.error}` : ""}`;
    }
  }

  async function runQuickMode() {
    if (!state.session || state.quickRunning) return;
    const sessionId = state.session.id;
    state.quickRunning = true;
    render();
    try {
      await quickPipeline.runDirect({
        sessionId,
        snapshot: quickSnapshot,
        isCurrent: () => Boolean(state.session && state.session.id === sessionId),
        actions: {
          generateBrief: () => streamBrief(false),
          approveBrief: () => briefAction("approve"),
          generatePlan: () => streamCompositionStage("beat-sheet"),
          approvePlan: () => documentAction("beat-sheet", "approve"),
          generatePrompt: () => streamCompositionStage("final-prompt"),
          approvePrompt: () => documentAction("final-prompt", "approve"),
        },
        onState: (record) => { state.quickRecord = record; render(); },
      });
    } finally {
      state.quickRunning = false;
      render();
    }
  }

  function render() {
    const session = state.session;
    const compositionReference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : null;
    const activeCookbook = activeCookbookSpec();
    elements.cookbook.value = compositionReference
      ? compositionReference.version
      : state.cookbook ? state.cookbook.version : "";
    const locked = interactionLocked();
    renderQuickStatus();
    elements.cookbook.disabled = locked || Boolean(compositionReference);
    elements.activeCookbook.textContent = activeCookbook
      ? compositionReference
        ? `${activeCookbook.display_name} · ${activeCookbook.id}@${activeCookbook.version} verrouillée`
        : `${activeCookbook.display_name} · verrouillée à la création du Plan`
      : "Cookbook indisponible";
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    elements.start.textContent = state.forkSource ? "Créer le nouveau parcours" : "Créer le parcours";
    elements.start.disabled = locked || Boolean(state.openingSessionId)
      || Boolean(session) || Boolean(setupValidationError());
    elements.imageInput.disabled = locked || Boolean(session) || Boolean(state.forkSource);
    elements.lastImageInput.disabled = locked || Boolean(session) || Boolean(state.forkSource);
    elements.inputMode.textContent = session
      ? `Mode verrouillé : ${sessionInputModeLabel(session)}`
      : currentInputModeLabel();
    elements.model.disabled = locked || Boolean(session);
    elements.refreshModels.disabled = locked;
    elements.refreshSessions.disabled = locked;
    elements.sessionList.querySelectorAll(".session-link").forEach((button) => { button.disabled = locked; });
    elements.intention.disabled = locked;
    elements.freedom.disabled = locked;
    elements.showReasoning.disabled = locked;
    elements.newSession.hidden = !session && !state.forkSource;
    elements.newSession.disabled = locked || Boolean(state.openingSessionId);
    elements.forkSession.hidden = !session;
    elements.forkSession.disabled = locked || Boolean(state.openingSessionId) || !session;
    if (!session) {
      elements.promptReferences.hidden = true;
      return;
    }

    renderDock();
    const brief = session.active_brief;
    const briefInputsCurrent = !brief || (
      (brief.source_text || "").trim() === elements.intention.value.trim()
      && Number(brief.creative_freedom) === Number(elements.freedom.value)
    );
    const documents = state.composition ? state.composition.documents || {} : {};
    const plan = documents.beat_sheet || null;
    const prompt = documents.final_prompt || null;
    const briefState = renderBrief(
      brief,
      Boolean(session.brief_complete && briefInputsCurrent),
      briefInputsCurrent,
    );
    const planState = renderDocument(
      elements.plan,
      plan,
      briefState.ready,
      briefState.draft ? "Brief modifié" : "Brief requis",
    );
    renderArbitrations(plan, planState, briefState.ready);
    const promptState = renderDocument(
      elements.prompt,
      prompt,
      planState.ready,
      planState.draft ? "Plan modifié" : "Plan requis",
    );
    elements.sessionTitle.textContent = sessionInputModeLabel(session);
    const recipeLabel = compositionReference
      ? `${compositionReference.id}@${compositionReference.version}`
      : state.cookbook ? `${state.cookbook.id}@${state.cookbook.version} · à verrouiller` : "non sélectionnée";
    elements.sessionConfig.textContent = `Modèle : ${session.model_id} · Recette : ${recipeLabel}`;
    elements.progress.textContent = !briefState.ready ? "Brief requis"
      : !planState.ready ? "Plan requis" : !promptState.ready ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptState.ready ? "success" : "active"}`;
    setChip(elements.chips.brief, briefState.ready, !briefState.ready);
    setChip(elements.chips.plan, planState.ready, briefState.ready && !planState.ready);
    setChip(elements.chips.prompt, promptState.ready, planState.ready && !promptState.ready);
    elements.copyPrompt.disabled = locked || !promptState.ready;
    renderPromptReferences(prompt);
  }

  function renderDock() {
    elements.dock.replaceChildren();
    const references = state.session.references || [];
    if (!references.length) {
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = "T2VA · aucune frame d’ancrage";
      elements.dock.append(note);
      return;
    }
    references.forEach((reference, index) => {
      const card = document.createElement("figure");
      const image = document.createElement("img");
      image.src = reference.content_url;
      image.alt = reference.label;
      const caption = document.createElement("figcaption");
      const role = reference.role === "last_frame" ? "Dernière frame exacte" : "Première frame exacte";
      caption.textContent = `<Image ${index + 1}> → <Picture ${index + 1}> · ${role}`;
      card.append(image, caption);
      elements.dock.append(card);
    });
  }

  function renderPromptReferences(documentState) {
    const visible = Boolean(
      (documentState && documentState.active_revision_id)
      || elements.prompt.content.value.trim(),
    );
    elements.promptReferences.hidden = !visible;
    if (!visible) return;
    const references = state.session.references || [];
    const renderKey = `${state.session.id}:${references.map((reference) => reference.label).join("|")}`;
    if (elements.promptReferences.dataset.renderKey === renderKey) return;
    elements.promptReferences.replaceChildren();
    const title = document.createElement("small");
    title.className = "prompt-reference-copy-title";
    title.textContent = "Noms des images";
    elements.promptReferences.append(title);
    references.forEach((reference, index) => {
      const row = document.createElement("div");
      row.className = "prompt-reference-copy-row";
      const label = document.createElement("code");
      label.textContent = `<Picture ${index + 1}> · ${reference.label}`;
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copier le nom";
      copy.setAttribute("aria-label", `Copier le nom ${reference.label}`);
      copy.addEventListener("click", async () => {
        const copied = await copyText(reference.label);
        copy.textContent = copied ? "Copié" : "Échec de copie";
        window.setTimeout(() => { copy.textContent = "Copier le nom"; }, 1400);
      });
      row.append(label, copy);
      elements.promptReferences.append(row);
    });
    elements.promptReferences.dataset.renderKey = renderKey;
  }

  function renderBrief(brief, complete, inputsCurrent) {
    hydrate(elements.brief.content, `brief:${brief ? brief.id : "none"}`, brief && brief.content);
    const draft = Boolean(brief) && elements.brief.content.value.trim() !== brief.content.trim();
    const ready = complete && !draft;
    elements.brief.review.textContent = ready ? "Validé"
      : brief && !inputsCurrent ? "Intention modifiée" : brief ? "À valider" : "À générer";
    elements.brief.review.className = `review-pill ${ready ? "approved" : "pending"}`;
    const locked = interactionLocked();
    elements.brief.generate.disabled = locked || !elements.intention.value.trim();
    elements.brief.content.disabled = locked;
    elements.brief.save.disabled = locked || !brief || !draft || !elements.brief.content.value.trim();
    elements.brief.approve.disabled = locked || !brief || complete || draft || !inputsCurrent;
    elements.brief.instruction.disabled = locked || !brief || !inputsCurrent || draft;
    elements.brief.rewrite.disabled = locked || !brief || !inputsCurrent || draft
      || !elements.brief.instruction.value.trim();
    elements.brief.rewriteApprove.disabled = elements.brief.rewrite.disabled;
    return { draft, ready };
  }

  const arbitrationCategoryLabels = {
    temporal: "Rythme et durée",
    spatial: "Espace et trajectoire",
    identity: "Identité",
    object: "Objet et continuité",
    physical: "Plausibilité physique",
    reference: "Influence des frames d’ancrage",
    other: "Autre point",
  };

  function resetArbitrations() {
    state.arbitrationDecisions = {};
    state.arbitrationRevisionId = null;
    elements.arbitrationInstruction.value = "";
    elements.arbitrationList.dataset.renderKey = "";
  }

  function updateArbitrationActions() {
    const ready = elements.arbitrations.dataset.ready === "true";
    const hasDecision = Object.values(state.arbitrationDecisions).some(
      (value) => value && value.trim(),
    );
    const hasInstruction = Boolean(elements.arbitrationInstruction.value.trim());
    const disabled = !ready || (!hasDecision && !hasInstruction);
    elements.applyArbitrations.disabled = disabled;
    elements.applyApproveArbitrations.disabled = disabled;
    elements.acceptAllArbitrations.disabled = !ready
      || elements.arbitrations.dataset.hasRecommendations !== "true";
  }

  function renderArbitrations(documentState, planState, prerequisite) {
    const cookbook = activeCookbookSpec();
    const active = documentState && documentState.active_revision_id;
    let plan = null;
    if (active && documentState.active_content) {
      try { plan = JSON.parse(documentState.active_content); } catch (_) { plan = null; }
    }
    const risks = plan && Array.isArray(plan.risks) ? plan.risks : null;
    const available = Boolean(
      cookbook && cookbook.supports_plan_reconciliation && active && risks,
    );
    elements.arbitrations.hidden = !available;
    if (!available) {
      elements.arbitrations.dataset.ready = "false";
      updateArbitrationActions();
      return;
    }
    if (state.arbitrationRevisionId !== active) {
      resetArbitrations();
      state.arbitrationRevisionId = active;
    }
    const renderKey = `${active}:${JSON.stringify(risks)}`;
    if (elements.arbitrationList.dataset.renderKey !== renderKey) {
      elements.arbitrationList.replaceChildren();
      if (!risks.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Aucun risque détecté. Vous pouvez néanmoins donner une instruction globale au planner.";
        elements.arbitrationList.append(empty);
      }
      risks.forEach((risk) => {
        const card = document.createElement("article");
        card.className = "arbitration-card";
        const header = document.createElement("header");
        const title = document.createElement("h4");
        title.textContent = `${arbitrationCategoryLabels[risk.category] || risk.category} · ${risk.risk_id}`;
        const badge = document.createElement("span");
        badge.className = `review-pill ${risk.resolution ? "approved" : "pending"}`;
        badge.textContent = risk.resolution ? "Résolu" : "À décider";
        header.append(title, badge);
        const description = document.createElement("p");
        description.textContent = risk.description;
        const recommendation = document.createElement("p");
        recommendation.className = "arbitration-recommendation";
        recommendation.textContent = `Recommandation : ${risk.recommendation}`;
        const decision = document.createElement("textarea");
        decision.rows = 2;
        decision.dataset.riskId = risk.risk_id;
        decision.setAttribute("aria-label", `Décision pour ${risk.risk_id}`);
        decision.placeholder = risk.resolution
          ? `Décision déjà appliquée : ${risk.resolution}`
          : "Écrivez votre décision, ou reprenez la recommandation.";
        decision.value = state.arbitrationDecisions[risk.risk_id] || "";
        decision.addEventListener("input", () => {
          state.arbitrationDecisions[risk.risk_id] = decision.value;
          updateArbitrationActions();
        });
        const actions = document.createElement("div");
        actions.className = "arbitration-card-actions";
        const useRecommendation = document.createElement("button");
        useRecommendation.type = "button";
        useRecommendation.textContent = "Reprendre la recommandation";
        useRecommendation.addEventListener("click", () => {
          decision.value = risk.recommendation;
          state.arbitrationDecisions[risk.risk_id] = decision.value;
          updateArbitrationActions();
        });
        const acceptRisk = document.createElement("button");
        acceptRisk.type = "button";
        acceptRisk.textContent = "Accepter le risque sans changement";
        acceptRisk.addEventListener("click", () => {
          decision.value = "Risque accepté : conserver le plan actuel sans modification pour ce point.";
          state.arbitrationDecisions[risk.risk_id] = decision.value;
          updateArbitrationActions();
        });
        actions.append(useRecommendation, acceptRisk);
        card.append(header, description, recommendation);
        if (risk.resolution) {
          const applied = document.createElement("p");
          applied.className = "muted";
          applied.textContent = `Décision appliquée : ${risk.resolution}`;
          card.append(applied);
        }
        card.append(decision, actions);
        elements.arbitrationList.append(card);
      });
      elements.arbitrationList.dataset.renderKey = renderKey;
    }
    const ready = Boolean(
      !interactionLocked() && prerequisite && !planState.draft && !planState.stale
      && !planState.diagnostics.length,
    );
    elements.arbitrations.dataset.ready = String(ready);
    elements.arbitrations.dataset.hasRecommendations = String(
      risks.some((risk) => !risk.resolution && risk.recommendation),
    );
    elements.arbitrationInstruction.disabled = !ready;
    elements.arbitrationList.querySelectorAll("textarea, button").forEach((control) => {
      control.disabled = !ready;
    });
    updateArbitrationActions();
  }

  function renderDocument(view, documentState, prerequisite, missingLabel) {
    const active = documentState && documentState.active_revision_id;
    hydrate(view.content, `${view === elements.plan ? "plan" : "prompt"}:${active || "none"}`, documentState && documentState.active_content);
    const draft = draftChanged(view.content, documentState);
    const complete = Boolean(documentState && documentState.complete);
    const stale = Boolean(documentState && documentState.stale);
    const errors = documentState ? documentState.validation_errors || [] : [];
    const warnings = documentState ? documentState.validation_warnings || [] : [];
    const diagnostics = documentState && documentState.blocked_reason
      ? [...errors, documentState.blocked_reason] : errors;
    const ready = Boolean(prerequisite && complete && !stale && !draft && !diagnostics.length);
    view.review.textContent = ready ? "Validé" : !prerequisite ? missingLabel
      : stale ? "Obsolète" : active ? "À valider" : "À générer";
    view.review.className = `review-pill ${ready ? "approved" : "pending"}`;
    const locked = interactionLocked();
    view.generate.disabled = locked || !prerequisite;
    view.content.disabled = locked || !prerequisite || !state.composition;
    view.save.disabled = locked || !state.composition || !prerequisite || stale
      || !draft || !view.content.value.trim();
    view.approve.disabled = locked || !prerequisite || !active || complete || stale
      || draft || Boolean(diagnostics.length);
    if (view.instruction) {
      view.instruction.disabled = locked || !prerequisite || !active || stale || draft;
      view.rewrite.disabled = locked || !prerequisite || !active || stale || draft
        || !view.instruction.value.trim();
    }
    renderDiagnostics(view.lint, diagnostics, warnings, draft);
    return { draft, ready, stale, diagnostics };
  }

  function renderDiagnostics(container, errors, warnings, draft) {
    if (!container) return;
    container.replaceChildren();
    const node = document.createElement(errors.length || warnings.length ? "ul" : "small");
    if (draft) node.textContent = "Brouillon local non enregistré : validation à recalculer.";
    else if (!errors.length && !warnings.length) node.textContent = "Contrat valide ou en attente de génération.";
    else {
      errors.forEach((message) => appendDiagnostic(node, `Erreur : ${message}`));
      warnings.forEach((message) => appendDiagnostic(node, `Avertissement : ${message}`));
    }
    container.append(node);
  }

  function appendDiagnostic(list, text) {
    const item = document.createElement("li");
    item.textContent = text;
    list.append(item);
  }

  function draftChanged(content, documentState) {
    return Boolean(documentState)
      && content.value.trim() !== (documentState.active_content || "").trim();
  }

  function hydrate(target, key, value) {
    if (target.dataset.hydrationKey !== key) {
      target.value = value || "";
      target.dataset.hydrationKey = key;
    }
  }

  function setChip(chip, complete, active) {
    chip.classList.toggle("active", active || complete);
    chip.classList.toggle("future", !active && !complete);
  }

  function revealNextStage(stageName) {
    const next = stageName === "brief" ? elements.steps.plan
      : stageName === "beat-sheet" ? elements.steps.prompt : null;
    if (!next) return;
    next.open = true;
    window.requestAnimationFrame(() => {
      next.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function streamBrief(revision) {
    const payload = revision
      ? { instruction: elements.brief.instruction.value.trim() }
      : { source_text: elements.intention.value.trim(), creative_freedom: Number(elements.freedom.value) };
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/brief/${revision ? "revise" : "structure"}/stream`,
      payload,
      elements.brief,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Brief révisé à partir des entrées." : "Brief H3 Base généré.",
    );
    if (completed) {
      if (revision) elements.brief.instruction.value = "";
      await refreshComposition();
    }
    return completed;
  }

  async function reviseAndApproveBrief() {
    if (state.compoundRunning) return false;
    state.compoundRunning = true;
    render();
    try {
      const sessionId = state.session && state.session.id;
      const previousRevisionId = state.session && state.session.active_brief_revision_id;
      if (!sessionId || !await streamBrief(true)) return false;
      const activeRevisionId = state.session && state.session.active_brief_revision_id;
      if (state.session.id !== sessionId || !activeRevisionId
        || activeRevisionId === previousRevisionId || !currentBriefInputs()) {
        showStageError(
          elements.brief,
          new Error("La nouvelle version du Brief n’a pas pu être confirmée ; elle n’a pas été validée."),
          false,
        );
        return false;
      }
      return briefAction("approve");
    } finally {
      state.compoundRunning = false;
      render();
    }
  }

  async function reconcileAndApprovePlan() {
    if (state.compoundRunning) return false;
    state.compoundRunning = true;
    render();
    try {
      return await reconcilePlan(true);
    } finally {
      state.compoundRunning = false;
      render();
    }
  }

  async function refreshComposition() {
    if (!state.session) return;
    try {
      const payload = await core.request(`/api/prompt-lab/sessions/${state.session.id}/composition`);
      state.composition = payload.composition;
    } catch (_) {
      state.composition = null;
    }
    render();
  }

  async function ensureComposition() {
    if (state.composition) return;
    if (!state.cookbook) throw new Error("Choisissez une recette H3 Base.");
    const first = referenceForRole(state.session, "first_frame");
    const last = referenceForRole(state.session, "last_frame");
    const response = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: state.cookbook.id,
          cookbook_version: state.cookbook.version,
          bindings: {
            first_frame: first ? [first.id] : [],
            last_frame: last ? [last.id] : [],
          },
        }),
      },
    );
    state.composition = response.composition;
  }

  async function streamCompositionStage(stageName, revision = false) {
    const view = stageName === "beat-sheet" ? elements.plan : elements.prompt;
    try {
      await ensureComposition();
      const payload = revision ? { instruction: view.instruction.value.trim() } : null;
      const completed = await streamResult(
        `/api/prompt-lab/sessions/${state.session.id}/${stageName}/${revision ? "revise" : "generate"}/stream`,
        payload,
        view,
        (event) => { if (event.composition) state.composition = event.composition; },
        revision ? "Révision enregistrée." : stageName === "beat-sheet" ? "Plan proposé." : "Prompt H3 compilé.",
      );
      if (completed && revision) view.instruction.value = "";
      return completed;
    } catch (error) {
      showStageError(view, error, false);
      return false;
    }
  }

  async function reconcilePlan(approveAfter = false) {
    const sessionId = state.session && state.session.id;
    const previousRevisionId = state.composition && state.composition.documents
      && state.composition.documents.beat_sheet
      ? state.composition.documents.beat_sheet.active_revision_id : null;
    const decisions = Object.fromEntries(
      Object.entries(state.arbitrationDecisions)
        .map(([riskId, value]) => [riskId, value.trim()])
        .filter(([, value]) => value),
    );
    const instruction = elements.arbitrationInstruction.value.trim() || null;
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/beat-sheet/reconcile/stream`,
      { decisions, instruction },
      elements.plan,
      (event) => { if (event.composition) state.composition = event.composition; },
      "Arbitrages appliqués au plan. Vérifiez puis validez cette nouvelle version.",
    );
    if (!completed) return false;
    resetArbitrations();
    render();
    if (!approveAfter) return true;
    const plan = state.composition && state.composition.documents
      ? state.composition.documents.beat_sheet : null;
    if (!state.session || state.session.id !== sessionId || !generatedDocument(plan)
      || !plan.active_revision_id || plan.active_revision_id === previousRevisionId) {
      showStageError(
        elements.plan,
        new Error("Le nouveau Plan n’a pas pu être confirmé ; il n’a pas été validé."),
        false,
      );
      return false;
    }
    return documentAction("beat-sheet", "approve");
  }

  async function streamResult(url, payload, view, onEvent, successMessage) {
    const previous = view.content.value;
    let received = false;
    let completed = false;
    setBusy(true);
    view.content.value = "";
    view.message.className = "message";
    view.message.textContent = "";
    const traceLabel = view === elements.brief ? "Brief"
      : view === elements.plan ? "Plan" : "Prompt H3";
    const traceStep = view === elements.brief ? elements.steps.brief
      : view === elements.plan ? elements.steps.plan : elements.steps.prompt;
    reasoningTrace.begin(traceLabel, traceStep);
    core.updateStreamState(view.stream, { phase: "preparing", text: "Préparation ou chargement du modèle…", progress: null });
    try {
      await core.streamRequest(reasoningTrace.streamUrl(url), {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      }, (event) => {
        reasoningTrace.handle(event);
        core.updateStreamState(view.stream, event);
        if (event.kind === "delta" && event.text) {
          received = true;
          view.content.value += event.text;
          view.content.scrollTop = view.content.scrollHeight;
        }
        if (event.session || event.composition) {
          onEvent(event);
          render();
        }
        if (event.kind === "completed") completed = true;
        if (event.kind === "truncated") {
          received = true;
          view.message.className = "message warning-text";
          view.message.textContent = "Réponse tronquée : le brouillon partiel reste éditable.";
        }
      });
      if (!completed) throw new Error("Le flux s’est terminé sans résultat persistant.");
      view.message.className = "message";
      view.message.textContent = successMessage;
      return true;
    } catch (error) {
      if (!received) view.content.value = previous;
      showStageError(view, error, received);
      core.failStreamState(view.stream, error.message);
      return false;
    } finally {
      reasoningTrace.finish();
      setBusy(false);
    }
  }

  async function briefAction(action, payload = null) {
    setBusy(true);
    try {
      state.session = await core.request(
        `/api/prompt-lab/sessions/${state.session.id}/brief/${action}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      await refreshComposition();
      elements.brief.message.textContent = action === "approve" ? "Brief validé." : "Brief enregistré.";
      if (action === "approve") revealNextStage("brief");
      return true;
    } catch (error) {
      showStageError(elements.brief, error, false);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function documentAction(stageName, action, payload = null) {
    const view = stageName === "beat-sheet" ? elements.plan : elements.prompt;
    setBusy(true);
    try {
      const response = await core.request(
        `/api/prompt-lab/sessions/${state.session.id}/${stageName}/${action}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      state.composition = response.composition;
      view.message.textContent = action === "approve" ? "Étape validée." : "Correction enregistrée.";
      if (action === "approve") revealNextStage(stageName);
      return true;
    } catch (error) {
      showStageError(view, error, false);
      return false;
    } finally {
      setBusy(false);
    }
  }

  function showStageError(view, error, preserved) {
    view.message.className = "message error-text";
    view.message.textContent = preserved
      ? `${error.message} Le candidat reçu reste disponible comme brouillon.`
      : error.message;
  }

  function showSetupMessage(message) {
    elements.setupMessage.textContent = message;
    elements.setupMessage.hidden = !message;
  }

  async function copyText(value) {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard indisponible");
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_) {
      const fallback = document.createElement("textarea");
      fallback.value = value;
      fallback.setAttribute("readonly", "");
      fallback.style.position = "fixed";
      fallback.style.opacity = "0";
      document.body.append(fallback);
      fallback.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      fallback.remove();
      return copied;
    }
  }

  function setBusy(value) {
    state.busy = value;
    render();
  }

  function clearStageDrafts() {
    reasoningTrace.reset();
    for (const view of [elements.brief, elements.plan, elements.prompt]) {
      view.message.textContent = "";
      if (view.instruction) view.instruction.value = "";
      view.content.dataset.hydrationKey = "";
      view.content.value = "";
    }
    elements.promptReferences.dataset.renderKey = "";
    elements.promptReferences.replaceChildren();
    elements.promptReferences.hidden = true;
  }

  function resetSession() {
    if (state.quickRunning) return;
    state.openRequestId += 1;
    state.openingSessionId = null;
    const selectedCookbook = directCookbooks().find(
      (item) => item.version === elements.cookbook.value,
    );
    if (selectedCookbook) state.cookbook = selectedCookbook;
    state.forkSource = null;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    resetArbitrations();
    showReferencePreview("first", null, "");
    showReferencePreview("last", null, "");
    elements.intention.value = "";
    setFreedom(35);
    elements.quickMode.checked = false;
    clearStageDrafts();
    showSetupMessage("");
    render();
  }

  elements.imageInput.addEventListener("change", () => selectFile("first"));
  elements.lastImageInput.addEventListener("change", () => selectFile("last"));
  elements.form.addEventListener("submit", createSession);
  elements.refreshModels.addEventListener("click", () => loadModels().catch((error) => showSetupMessage(error.message)));
  elements.refreshSessions.addEventListener("click", () => loadSessions().catch((error) => showSetupMessage(error.message)));
  elements.cookbook.addEventListener("change", () => {
    state.cookbook = directCookbooks().find(
      (item) => item.version === elements.cookbook.value,
    ) || null;
    render();
  });
  elements.intention.addEventListener("input", render);
  elements.model.addEventListener("change", render);
  elements.freedom.addEventListener("change", () => { updateFreedom(); render(); });
  elements.newSession.addEventListener("click", resetSession);
  elements.forkSession.addEventListener("click", prepareFork);
  elements.quickResume.addEventListener("click", runQuickMode);

  elements.brief.content.addEventListener("input", render);
  elements.brief.instruction.addEventListener("input", render);
  elements.brief.generate.addEventListener("click", () => streamBrief(false));
  elements.brief.save.addEventListener("click", () => briefAction("edit", { content: elements.brief.content.value.trim() }));
  elements.brief.approve.addEventListener("click", () => briefAction("approve"));
  elements.brief.rewrite.addEventListener("click", () => streamBrief(true));
  elements.brief.rewriteApprove.addEventListener("click", reviseAndApproveBrief);

  elements.plan.content.addEventListener("input", render);
  elements.plan.generate.addEventListener("click", () => streamCompositionStage("beat-sheet"));
  elements.plan.save.addEventListener("click", () => documentAction("beat-sheet", "edit", { content: elements.plan.content.value.trim() }));
  elements.plan.approve.addEventListener("click", () => documentAction("beat-sheet", "approve"));
  elements.arbitrationInstruction.addEventListener("input", updateArbitrationActions);
  elements.acceptAllArbitrations.addEventListener("click", () => {
    const documentState = state.composition && state.composition.documents
      ? state.composition.documents.beat_sheet : null;
    if (!documentState || !documentState.active_content) return;
    try {
      const plan = JSON.parse(documentState.active_content);
      (plan.risks || []).forEach((risk) => {
        if (!risk.resolution && risk.recommendation) {
          state.arbitrationDecisions[risk.risk_id] = risk.recommendation;
        }
      });
      elements.arbitrationList.dataset.renderKey = "";
      render();
    } catch (_) {
      elements.plan.message.className = "message error-text";
      elements.plan.message.textContent = "Le plan actif ne peut pas être relu pour l’arbitrage.";
    }
  });
  elements.applyArbitrations.addEventListener("click", () => reconcilePlan(false));
  elements.applyApproveArbitrations.addEventListener("click", reconcileAndApprovePlan);

  elements.prompt.content.addEventListener("input", render);
  elements.prompt.instruction.addEventListener("input", render);
  elements.prompt.generate.addEventListener("click", () => streamCompositionStage("final-prompt"));
  elements.prompt.save.addEventListener("click", () => documentAction("final-prompt", "edit", { content: elements.prompt.content.value.trim() }));
  elements.prompt.approve.addEventListener("click", () => documentAction("final-prompt", "approve"));
  elements.prompt.rewrite.addEventListener("click", () => streamCompositionStage("final-prompt", true));
  elements.copyPrompt.addEventListener("click", async () => {
    if (await copyText(elements.prompt.content.value)) {
      elements.prompt.message.textContent = "Prompt copié.";
    } else {
      elements.prompt.content.select();
      elements.prompt.message.textContent = "Utilisez Ctrl+C pour copier le prompt.";
    }
  });

  updateFreedom();
  render();
  initialize();
})();
