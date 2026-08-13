(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  const quickPipeline = window.PanelForgeQuickPipeline;
  if (!core || !quickPipeline) return;
  const $ = (selector) => document.querySelector(selector);
  const profileId = "minimax.h3.ref2v.direct";
  const profileVersion = "0.1.0";
  const cookbookId = "minimax.h3.ref2v.direct";
  const multishotCookbookId = "minimax.h3.ref2v.direct.multishot";
  const preferredCookbookVersion = "0.3.3";
  const preferredCookbookValue = `${cookbookId}@${preferredCookbookVersion}`;
  const roleOptions = [
    ["first_frame", "Première frame exacte", "first_frame", "État visible complet à 0,00 s : sujets, pose, cadrage, perspective, décor, lumière et composition."],
    ["subject_reference", "Sujet / identité", "subject", "Identité, apparence stable et attributs explicitement attribués."],
    ["keyframe_reference", "Keyframe", "keyframe", "État visuel d’un instant intermédiaire défini par le Brief et le Plan."],
    ["environment_reference", "Décor", "environment", "Environnement, matériaux, géométrie spatiale, lumière et atmosphère."],
    ["composition_reference", "Composition", "composition", "Composition, cadrage et équilibre spatial."],
    ["style_reference", "Style", "style", "Style visuel, palette, texture et traitement cinématographique."],
    ["motion_reference", "Mouvement", "motion", "Mécanique de l’action, dynamique corporelle et qualité du mouvement."],
    ["last_frame", "Dernière frame exacte", "last_frame", "État visuel final exact au temps prévu."],
  ];

  const state = {
    spec: null,
    cookbooks: [],
    cookbook: null,
    drafts: [],
    session: null,
    composition: null,
    busy: false,
    quickRunning: false,
    quickRecord: null,
    rolesConfirmed: false,
    arbitrationDecisions: {},
    arbitrationRevisionId: null,
  };

  const elements = {
    form: $("#ref2vd-session-form"),
    model: $("#ref2vd-model"),
    refreshModels: $("#ref2vd-refresh-models"),
    cookbook: $("#ref2vd-cookbook"),
    activeCookbook: $("#ref2vd-active-cookbook"),
    imageInput: $("#ref2vd-image-input"),
    referenceList: $("#ref2vd-reference-list"),
    roleHelpBody: $("#ref2vd-role-help-body"),
    roleSummary: $("#ref2vd-role-summary"),
    roleWarning: $("#ref2vd-role-warning"),
    roleConfirmation: $("#ref2vd-role-confirmation"),
    intention: $("#ref2vd-intention"),
    freedom: $("#ref2vd-freedom"),
    freedomValue: $("#ref2vd-freedom-value"),
    freedomLabel: $("#ref2vd-freedom-label"),
    start: $("#ref2vd-start"),
    setupMessage: $("#ref2vd-setup-message"),
    quickMode: $("#ref2vd-quick-mode"),
    quickStatus: $("#ref2vd-quick-status"),
    quickStatusLabel: $("#ref2vd-quick-status-label"),
    quickResume: $("#ref2vd-quick-resume"),
    modeWarning: $("#ref2vd-mode-warning"),
    refreshSessions: $("#ref2vd-refresh-sessions"),
    sessionList: $("#ref2vd-session-list"),
    empty: $("#ref2vd-empty"),
    editor: $("#ref2vd-editor"),
    sessionTitle: $("#ref2vd-session-title"),
    progress: $("#ref2vd-session-progress"),
    newSession: $("#ref2vd-new-session"),
    dock: $("#ref2vd-reference-dock"),
    chips: {
      brief: $("#ref2vd-chip-brief"),
      plan: $("#ref2vd-chip-plan"),
      prompt: $("#ref2vd-chip-prompt"),
    },
    brief: stage("brief"),
    plan: stage("plan"),
    prompt: stage("prompt"),
    copyPrompt: $("#ref2vd-copy-prompt"),
    arbitrations: $("#ref2vd-arbitrations"),
    arbitrationList: $("#ref2vd-arbitration-list"),
    arbitrationInstruction: $("#ref2vd-arbitration-instruction"),
    acceptAllArbitrations: $("#ref2vd-accept-all-arbitrations"),
    applyArbitrations: $("#ref2vd-apply-arbitrations"),
    multishotSummary: $("#ref2vd-multishot-summary"),
    multishotSummaryBadge: $("#ref2vd-multishot-summary-badge"),
    multishotSummaryList: $("#ref2vd-multishot-summary-list"),
  };

  function stage(name) {
    return {
      review: $(`#ref2vd-${name}-review`),
      generate: $(`#ref2vd-generate-${name}`),
      save: $(`#ref2vd-save-${name}`),
      approve: $(`#ref2vd-approve-${name}`),
      content: $(`#ref2vd-${name}-content`),
      message: $(`#ref2vd-${name}-message`),
      instruction: $(`#ref2vd-${name}-instruction`),
      rewrite: $(`#ref2vd-rewrite-${name}`),
      lint: $(`#ref2vd-${name}-lint`),
      stream: {
        container: $(`#ref2vd-${name}-stream-state`),
        label: $(`#ref2vd-${name}-stream-label`),
        percent: $(`#ref2vd-${name}-stream-percent`),
        progress: $(`#ref2vd-${name}-stream-progress`),
      },
    };
  }

  function renderRoleHelp() {
    elements.roleHelpBody.replaceChildren();
    roleOptions.forEach(([, label, , controls]) => {
      const row = document.createElement("tr");
      const role = document.createElement("th");
      role.scope = "row";
      role.textContent = label;
      const description = document.createElement("td");
      description.textContent = controls;
      row.append(role, description);
      elements.roleHelpBody.append(row);
    });
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
      if (!selectedProfile()) throw new Error("Profil Ref2V Direct indisponible.");
      if (!state.cookbook) throw new Error("Cookbook Ref2V Direct indisponible.");
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
      (item) => [cookbookId, multishotCookbookId].includes(item.id)
        && item.target_mode === "ref2v_direct",
    );
  }

  function cookbookValue(cookbook) {
    return `${cookbook.id}@${cookbook.version}`;
  }

  function isMultishotCookbook(cookbook) {
    return Boolean(cookbook && cookbook.id === multishotCookbookId);
  }

  function cookbookLabel(cookbook) {
    if (isMultishotCookbook(cookbook)) {
      const qualifier = cookbook.version === "0.2.0"
        ? "2–6 plans automatiques · caméra compilée · expérimental"
        : "3 plans · placeholders · témoin";
      return `${cookbook.id}@${cookbook.version} — ${qualifier}`;
    }
    const qualifier = cookbook.version === preferredCookbookVersion
      ? "Mono-plan · caméra compilée · défaut"
      : cookbook.version === "0.3.2" ? "Mono-plan · placeholders · témoin"
        : cookbook.version === "0.3.1" ? "Compacte · témoin"
        : cookbook.version === "0.3.0" ? "Verrouillée · témoin"
        : cookbook.version === "0.2.0" ? "Témoin V2" : "Historique";
    return `${cookbook.id}@${cookbook.version} — ${qualifier}`;
  }

  function orderedDirectCookbooks() {
    return [...directCookbooks()].sort((left, right) => {
      if (left.id !== right.id) return left.id === cookbookId ? -1 : 1;
      return right.version.localeCompare(left.version, undefined, { numeric: true });
    });
  }

  function resetCookbookSelection() {
    const available = orderedDirectCookbooks();
    state.cookbook = available.find(
      (item) => cookbookValue(item) === preferredCookbookValue,
    ) || available[0] || null;
    elements.cookbook.value = state.cookbook ? cookbookValue(state.cookbook) : "";
  }

  function populateCookbooks() {
    const available = orderedDirectCookbooks();
    elements.cookbook.replaceChildren();
    available.forEach((cookbook) => {
      const option = document.createElement("option");
      option.value = cookbookValue(cookbook);
      option.textContent = cookbookLabel(cookbook);
      elements.cookbook.append(option);
    });
    resetCookbookSelection();
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
      (item) => item.session_mode === "direct_multimodal"
        && item.profile && item.profile.id === profileId
        && item.profile.version === profileVersion,
    );
    elements.sessionList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun parcours Ref2V Direct enregistré.";
      elements.sessionList.append(empty);
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = session.references.map((item) => item.label).join(" + ");
      const detail = document.createElement("small");
      detail.textContent = `${session.references.length} image${session.references.length > 1 ? "s" : ""} · ${session.brief_complete ? "Brief validé" : "Brief à préparer"}`;
      button.append(title, detail);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  async function openSession(session) {
    if (state.quickRunning) return;
    state.session = session;
    state.composition = null;
    state.quickRecord = quickPipeline.load(session.id);
    if (session.active_brief) {
      elements.intention.value = session.active_brief.source_text || "";
      elements.freedom.value = String(session.active_brief.creative_freedom ?? 35);
    } else {
      elements.intention.value = "";
      elements.freedom.value = "35";
    }
    updateFreedom();
    try {
      const payload = await core.request(`/api/prompt-lab/sessions/${session.id}/composition`);
      state.composition = payload.composition;
    } catch (_) {
      state.composition = null;
    }
    render();
  }

  function addFiles(fileList) {
    const available = Math.max(0, 3 - state.drafts.length);
    const addedFiles = [...fileList].slice(0, available);
    addedFiles.forEach((file) => {
      const role = state.drafts.length === 0 ? "first_frame" : "subject_reference";
      state.drafts.push({
        file,
        previewUrl: URL.createObjectURL(file),
        role,
      });
    });
    if (addedFiles.length) invalidateRoleConfirmation();
    elements.imageInput.value = "";
    if (fileList.length > available) {
      showSetupMessage("Ref2V Direct accepte trois images au maximum.");
    } else {
      showSetupMessage("");
    }
    renderDraftReferences();
    render();
  }

  function renderDraftReferences() {
    elements.referenceList.replaceChildren();
    if (!state.drafts.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucune référence.";
      elements.referenceList.append(empty);
      return;
    }
    state.drafts.forEach((draft, index) => {
      const card = document.createElement("article");
      card.className = "ref2vd-reference-card";
      const image = document.createElement("img");
      image.src = draft.previewUrl;
      image.alt = `Aperçu Picture ${index + 1}`;
      const body = document.createElement("div");
      const heading = document.createElement("b");
      heading.textContent = `<Picture ${index + 1}> · ${draft.file.name}`;
      const select = document.createElement("select");
      select.setAttribute("aria-label", `Rôle de Picture ${index + 1}`);
      roleOptions.forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      });
      select.value = draft.role;
      select.disabled = Boolean(state.session);
      select.addEventListener("change", () => {
        draft.role = select.value;
        invalidateRoleConfirmation();
        render();
      });
      const actions = document.createElement("div");
      actions.className = "ref2vd-card-actions";
      const up = smallButton("↑", "Monter", () => moveDraft(index, -1));
      const down = smallButton("↓", "Descendre", () => moveDraft(index, 1));
      const remove = smallButton("Retirer", "Retirer", () => removeDraft(index));
      up.disabled = Boolean(state.session) || index === 0;
      down.disabled = Boolean(state.session) || index === state.drafts.length - 1;
      remove.disabled = Boolean(state.session);
      actions.append(up, down, remove);
      body.append(heading, select, actions);
      card.append(image, body);
      elements.referenceList.append(card);
    });
  }

  function smallButton(text, label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.setAttribute("aria-label", label);
    button.addEventListener("click", action);
    return button;
  }

  function moveDraft(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= state.drafts.length) return;
    [state.drafts[index], state.drafts[target]] = [state.drafts[target], state.drafts[index]];
    invalidateRoleConfirmation();
    renderDraftReferences();
    render();
  }

  function removeDraft(index) {
    const [removed] = state.drafts.splice(index, 1);
    if (removed) URL.revokeObjectURL(removed.previewUrl);
    invalidateRoleConfirmation();
    renderDraftReferences();
    render();
  }

  function roleUse(role) {
    const item = roleOptions.find(([value]) => value === role);
    return item ? item[2] : null;
  }

  function invalidateRoleConfirmation() {
    state.rolesConfirmed = false;
    elements.roleConfirmation.checked = false;
  }

  function renderRoleReview() {
    const references = state.session ? state.session.references : state.drafts;
    elements.roleSummary.replaceChildren();
    if (!references.length) {
      const item = document.createElement("li");
      item.textContent = "Aucun rôle à vérifier.";
      elements.roleSummary.append(item);
    } else {
      references.forEach((reference, index) => {
        const role = roleOptions.find(([value]) => value === reference.role);
        const item = document.createElement("li");
        item.textContent = `<Image ${index + 1}> → <Picture ${index + 1}> · ${role ? role[1] : reference.role}`;
        elements.roleSummary.append(item);
      });
    }
    const allAdditionalReferencesAreSubjects = references.length > 1
      && references.slice(1).every((reference) => reference.role === "subject_reference");
    elements.roleWarning.textContent = allAdditionalReferencesAreSubjects
      ? "Toutes les images supplémentaires utilisent « Sujet / identité ». Vérifiez si certaines servent plutôt de décor, composition, style ou mouvement."
      : "";
    elements.roleWarning.hidden = !elements.roleWarning.textContent;
    elements.roleConfirmation.checked = Boolean(state.session) || state.rolesConfirmed;
    elements.roleConfirmation.disabled = interactionLocked() || Boolean(state.session) || !state.drafts.length;
  }

  function intentionRequestsMultipleShots(value) {
    const text = String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
    if (/\b(?:multi[ -]?(?:plan|shot)s?|plusieurs plans?|multiple shots?)\b/.test(text)) return true;
    if (/\b(?:[2-9]|[1-9]\d+|deux|trois|quatre|cinq|six)\s+(?:plans?|shots?)\b/.test(text)) return true;
    return /\b(?:plan|shot)\s*1\b/.test(text) && /\b(?:plan|shot)\s*2\b/.test(text);
  }

  function renderSetupWarnings() {
    const recipeMismatch = !state.session
      && !isMultishotCookbook(activeCookbookSpec())
      && intentionRequestsMultipleShots(elements.intention.value);
    elements.modeWarning.textContent = recipeMismatch
      ? "L’intention décrit plusieurs plans, mais la recette active est mono-plan. Vous pouvez continuer ou sélectionner Multi-plan avant de générer le Plan."
      : "";
    elements.modeWarning.hidden = !elements.modeWarning.textContent;
  }

  function setupValidationError() {
    if (!selectedProfile() || !state.cookbook) return "Le profil Direct est encore en cours de chargement.";
    if (!state.drafts.length) return "Ajoutez au moins une image.";
    if (state.drafts.length > 3) return "Trois images au maximum.";
    if (!state.rolesConfirmed) return "Vérifiez et confirmez le rôle attribué à chaque image.";
    if (!elements.model.value) return "Choisissez un modèle multimodal.";
    if (!elements.intention.value.trim()) return "Décrivez votre intention.";
    for (const role of ["first_frame", "last_frame"]) {
      if (state.drafts.filter((item) => item.role === role).length > 1) {
        return `Le rôle ${role} ne peut être attribué qu’une fois.`;
      }
    }
    return "";
  }

  async function createSession(event) {
    event.preventDefault();
    const error = setupValidationError();
    if (error) return showSetupMessage(error);
    const profile = selectedProfile();
    const body = new FormData();
    state.drafts.forEach((draft) => {
      body.append("images", draft.file, draft.file.name);
      body.append("roles", draft.role);
      body.append("usages", roleUse(draft.role));
      body.append("evidence_policies", "full");
    });
    body.append("model_id", elements.model.value);
    body.append("profile_id", profile.id);
    body.append("profile_version", profile.version);
    const quickRequested = elements.quickMode.checked;
    let created = false;
    setBusy(true);
    try {
      state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      state.composition = null;
      state.quickRecord = null;
      created = true;
      renderDraftReferences();
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

  function updateFreedom() {
    const value = Number(elements.freedom.value);
    elements.freedomValue.value = String(value);
    elements.freedomLabel.textContent = value <= 20
      ? "Très factuelle" : value <= 45 ? "Encadrée" : value <= 70 ? "Cinématographique" : "Très libre";
  }

  function interactionLocked() {
    return state.busy || state.quickRunning;
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
    const selectedCookbook = compositionReference || state.cookbook;
    const activeCookbook = activeCookbookSpec();
    const locked = interactionLocked();
    renderQuickStatus();
    renderRoleReview();
    renderSetupWarnings();
    if (selectedCookbook) elements.cookbook.value = cookbookValue(selectedCookbook);
    elements.cookbook.disabled = locked || Boolean(compositionReference);
    elements.activeCookbook.textContent = activeCookbook
      ? compositionReference
        ? `${activeCookbook.display_name} · ${activeCookbook.id}@${activeCookbook.version} verrouillée`
        : `${activeCookbook.display_name} · verrouillée à la création du Plan`
      : "Cookbook indisponible";
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    elements.start.disabled = locked || Boolean(state.session) || Boolean(setupValidationError());
    elements.imageInput.disabled = locked || Boolean(state.session) || state.drafts.length >= 3;
    elements.model.disabled = locked || Boolean(state.session);
    elements.refreshModels.disabled = locked;
    elements.refreshSessions.disabled = locked;
    elements.sessionList.querySelectorAll(".session-link").forEach((button) => { button.disabled = locked; });
    elements.intention.disabled = locked;
    elements.freedom.disabled = locked;
    elements.newSession.disabled = locked;
    if (!session) return;

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
    renderMultishotSummary();
    renderArbitrations(plan, planState, briefState.ready);
    const promptState = renderDocument(
      elements.prompt,
      prompt,
      planState.ready,
      planState.draft ? "Plan modifié" : "Plan requis",
    );
    elements.sessionTitle.textContent = session.references.map((item) => item.label).join(" + ");
    elements.progress.textContent = !briefState.ready ? "Brief requis"
      : !planState.ready ? "Plan requis" : !promptState.ready ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptState.ready ? "success" : "active"}`;
    setChip(elements.chips.brief, briefState.ready, !briefState.ready);
    setChip(elements.chips.plan, planState.ready, briefState.ready && !planState.ready);
    setChip(elements.chips.prompt, promptState.ready, planState.ready && !promptState.ready);
    elements.copyPrompt.disabled = locked || !promptState.ready;
  }

  function renderDock() {
    elements.dock.replaceChildren();
    state.session.references.forEach((reference, index) => {
      const card = document.createElement("figure");
      const image = document.createElement("img");
      image.src = reference.content_url;
      image.alt = reference.label;
      const caption = document.createElement("figcaption");
      const role = roleOptions.find(([value]) => value === reference.role);
      caption.textContent = `<Image ${index + 1}> → <Picture ${index + 1}> · ${role ? role[1] : reference.role}`;
      card.append(image, caption);
      elements.dock.append(card);
    });
  }

  function finiteNumber(...values) {
    for (const value of values) {
      const number = Number(value);
      if (value !== null && value !== "" && Number.isFinite(number)) return number;
    }
    return null;
  }

  function milliseconds(value, unit = "milliseconds") {
    const number = finiteNumber(value);
    if (number === null) return null;
    return unit === "seconds" ? Math.round(number * 1000) : Math.round(number);
  }

  function shotTiming(shots) {
    let cursor = 0;
    return shots.map((shot) => {
      const explicitStart = finiteNumber(
        shot.start_ms,
        shot.start_time_ms,
        shot.cut_at_ms,
      );
      const start = explicitStart === null ? cursor : explicitStart;
      const duration = milliseconds(shot.duration_ms)
        ?? milliseconds(shot.duration_seconds, "seconds");
      const explicitEnd = finiteNumber(shot.end_ms, shot.end_time_ms);
      const end = explicitEnd ?? (duration === null ? null : start + duration);
      if (end !== null) cursor = end;
      return { start, end, duration: end === null ? duration : end - start };
    });
  }

  function formatClock(value) {
    if (!Number.isFinite(value)) return null;
    const minutes = Math.floor(value / 60000);
    const seconds = Math.floor((value % 60000) / 1000);
    const millis = Math.round(value % 1000);
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
  }

  function summaryText(value) {
    if (typeof value === "string") return value.trim();
    if (Array.isArray(value)) return value.filter(Boolean).join(", ");
    if (value && typeof value === "object") {
      const direct = value.description || value.directive || value.movement || value.type;
      if (direct) return direct;
      return Object.values(value).filter(
        (item) => typeof item === "string" && item.trim(),
      ).join(" · ");
    }
    return "";
  }

  function cameraSummary(camera) {
    if (!camera) return "";
    if (typeof camera === "string") return camera.trim();
    if (typeof camera !== "object") return "";
    return [
      camera.motion,
      camera.amplitude,
      camera.speed,
      camera.target_clause,
    ].filter(Boolean).join(" · ");
  }

  function renderMultishotSummary() {
    const multishot = isMultishotCookbook(activeCookbookSpec());
    elements.multishotSummary.hidden = !multishot;
    if (!multishot) return;

    elements.multishotSummaryList.replaceChildren();
    let plan = null;
    try { plan = JSON.parse(elements.plan.content.value); } catch (_) { plan = null; }
    let shots = plan && (
      (Array.isArray(plan.shots) && plan.shots)
      || (Array.isArray(plan.plans) && plan.plans)
      || (Array.isArray(plan.shot_plan) && plan.shot_plan)
    );
    if (shots && shots.some(
      (shot) => !shot || typeof shot !== "object" || Array.isArray(shot),
    )) shots = null;
    if (!shots) {
      elements.multishotSummaryBadge.textContent = "Plans à générer";
      const message = document.createElement("p");
      message.className = "muted";
      message.textContent = elements.plan.content.value.trim()
        ? "Le JSON est incomplet ou illisible ; la synthèse se recalculera après enregistrement."
        : "La frise apparaîtra dès que le Plan JSON sera généré.";
      elements.multishotSummaryList.append(message);
      return;
    }

    const timings = shotTiming(shots);
    const derived = plan.derived_timing || {};
    const lastEnd = timings.length ? timings[timings.length - 1].end : null;
    const finalHold = plan.final_state
      ? milliseconds(plan.final_state.final_hold_ms) : null;
    const derivedTotal = lastEnd === null ? null : lastEnd + (finalHold || 0);
    const total = finiteNumber(derived.duration_ms, plan.duration_ms)
      ?? milliseconds(derived.duration_seconds, "seconds")
      ?? milliseconds(plan.duration_seconds, "seconds")
      ?? derivedTotal;
    elements.multishotSummaryBadge.textContent = `${shots.length} plan${shots.length > 1 ? "s" : ""}${total === null ? "" : ` · ${(total / 1000).toFixed(total % 1000 ? 1 : 0)} s`}`;

    for (let index = 0; index < shots.length; index += 1) {
      const shot = shots[index];
      const card = document.createElement("article");
      card.className = "arbitration-card";
      const header = document.createElement("header");
      const title = document.createElement("h4");
      title.textContent = `Plan ${index + 1}`;
      const timing = timings[index];
      const badge = document.createElement("span");
      badge.className = `review-pill ${shot ? "approved" : "pending"}`;
      const cut = index > 0 && timing ? formatClock(timing.start) : null;
      badge.textContent = !shot ? "Manquant"
        : cut ? `Coupe à ${cut}`
          : timing && timing.duration !== null ? `${(timing.duration / 1000).toFixed(1)} s` : "Présent";
      header.append(title, badge);
      const description = document.createElement("p");
      description.textContent = shot
        ? summaryText(shot.actions || shot.primary_action || shot.dominant_action || shot.action || shot.purpose || shot.objective || shot.description) || "Action non résumée."
        : "Plan manquant.";
      card.append(header, description);
      if (shot) {
        const details = [
          ["Entrée", summaryText(shot.entry_state)],
          ["Cadrage", summaryText(shot.opening_composition)],
          ["Raccord", summaryText(shot.continuity_from_previous)],
          ["Sortie", summaryText(shot.observable_end_state || shot.exit_state)],
          ["Références", summaryText(shot.active_picture_labels || shot.active_references || shot.references)],
          ["Caméra", cameraSummary(shot.camera)],
        ].filter(([, value]) => value);
        if (details.length) {
          const metadata = document.createElement("p");
          metadata.className = "muted";
          metadata.textContent = details.map(([label, value]) => `${label} : ${value}`).join(" · ");
          card.append(metadata);
        }
      }
      elements.multishotSummaryList.append(card);
    }
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
    return { draft, ready };
  }

  const arbitrationCategoryLabels = {
    temporal: "Rythme et durée",
    spatial: "Espace et trajectoire",
    identity: "Identité",
    object: "Objet et continuité",
    physical: "Plausibilité physique",
    reference: "Influence des références",
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
    elements.applyArbitrations.disabled = !ready || (!hasDecision && !hasInstruction);
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

  async function streamBrief(revision) {
    const payload = revision
      ? { instruction: elements.brief.instruction.value.trim() }
      : { source_text: elements.intention.value.trim(), creative_freedom: Number(elements.freedom.value) };
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/brief/${revision ? "revise" : "structure"}/stream`,
      payload,
      elements.brief,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Brief révisé à partir des images." : "Brief multimodal généré.",
    );
    if (completed) {
      if (revision) elements.brief.instruction.value = "";
      await refreshComposition();
    }
    return completed;
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
    if (!state.cookbook) throw new Error("Choisissez une recette Ref2V Direct.");
    const response = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: state.cookbook.id,
          cookbook_version: state.cookbook.version,
          bindings: { references: state.session.references.map((item) => item.id) },
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

  async function reconcilePlan() {
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
    if (completed) resetArbitrations();
  }

  async function streamResult(url, payload, view, onEvent, successMessage) {
    const previous = view.content.value;
    let received = false;
    let completed = false;
    setBusy(true);
    view.content.value = "";
    view.message.className = "message";
    view.message.textContent = "";
    core.updateStreamState(view.stream, { phase: "preparing", text: "Préparation ou chargement du modèle…", progress: null });
    try {
      await core.streamRequest(url, {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      }, (event) => {
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

  function setBusy(value) {
    state.busy = value;
    render();
  }

  function resetSession() {
    if (state.quickRunning) return;
    const preservedCookbook = activeCookbookSpec() || state.cookbook;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    state.cookbook = preservedCookbook && directCookbooks().find(
      (item) => cookbookValue(item) === cookbookValue(preservedCookbook),
    ) || null;
    if (!state.cookbook) resetCookbookSelection();
    else elements.cookbook.value = cookbookValue(state.cookbook);
    resetArbitrations();
    state.drafts.forEach((draft) => URL.revokeObjectURL(draft.previewUrl));
    state.drafts = [];
    invalidateRoleConfirmation();
    renderDraftReferences();
    elements.intention.value = "";
    elements.freedom.value = "35";
    elements.quickMode.checked = false;
    updateFreedom();
    for (const view of [elements.brief, elements.plan, elements.prompt]) {
      view.message.textContent = "";
      if (view.instruction) view.instruction.value = "";
    }
    elements.brief.content.dataset.hydrationKey = "";
    elements.plan.content.dataset.hydrationKey = "";
    elements.prompt.content.dataset.hydrationKey = "";
    render();
  }

  elements.imageInput.addEventListener("change", () => addFiles(elements.imageInput.files || []));
  elements.form.addEventListener("submit", createSession);
  elements.refreshModels.addEventListener("click", () => loadModels().catch((error) => showSetupMessage(error.message)));
  elements.refreshSessions.addEventListener("click", () => loadSessions().catch((error) => showSetupMessage(error.message)));
  elements.cookbook.addEventListener("change", () => {
    state.cookbook = directCookbooks().find(
      (item) => cookbookValue(item) === elements.cookbook.value,
    ) || null;
    render();
  });
  elements.intention.addEventListener("input", render);
  elements.model.addEventListener("change", render);
  elements.freedom.addEventListener("input", () => { updateFreedom(); render(); });
  elements.roleConfirmation.addEventListener("change", () => {
    state.rolesConfirmed = elements.roleConfirmation.checked;
    render();
  });
  elements.newSession.addEventListener("click", resetSession);
  elements.quickResume.addEventListener("click", runQuickMode);

  elements.brief.content.addEventListener("input", render);
  elements.brief.instruction.addEventListener("input", render);
  elements.brief.generate.addEventListener("click", () => streamBrief(false));
  elements.brief.save.addEventListener("click", () => briefAction("edit", { content: elements.brief.content.value.trim() }));
  elements.brief.approve.addEventListener("click", () => briefAction("approve"));
  elements.brief.rewrite.addEventListener("click", () => streamBrief(true));

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
  elements.applyArbitrations.addEventListener("click", reconcilePlan);

  elements.prompt.content.addEventListener("input", render);
  elements.prompt.instruction.addEventListener("input", render);
  elements.prompt.generate.addEventListener("click", () => streamCompositionStage("final-prompt"));
  elements.prompt.save.addEventListener("click", () => documentAction("final-prompt", "edit", { content: elements.prompt.content.value.trim() }));
  elements.prompt.approve.addEventListener("click", () => documentAction("final-prompt", "approve"));
  elements.prompt.rewrite.addEventListener("click", () => streamCompositionStage("final-prompt", true));
  elements.copyPrompt.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(elements.prompt.content.value);
      elements.prompt.message.textContent = "Prompt copié.";
    } catch (_) {
      elements.prompt.content.select();
      elements.prompt.message.textContent = "Utilisez Ctrl+C pour copier le prompt.";
    }
  });

  updateFreedom();
  renderRoleHelp();
  renderDraftReferences();
  render();
  initialize();
})();
