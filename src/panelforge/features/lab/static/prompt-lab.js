(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const referenceUses = [
    ["subject", "Sujet"],
    ["first_frame", "Première frame"],
    ["keyframe", "Keyframe"],
    ["last_frame", "Dernière frame"],
    ["composition", "Composition"],
    ["environment", "Décor"],
    ["style", "Style"],
  ];
  const state = {
    initialized: false,
    spec: null,
    files: [],
    session: null,
    selectedReferenceId: null,
    busy: false,
  };

  const elements = {
    changeView: $("#change-view-workspace"),
    promptLab: $("#prompt-lab-workspace"),
    recipeBadge: $("#recipe-badge"),
    nav: [...document.querySelectorAll("[data-lab-view]")],
    form: $("#prompt-session-form"),
    model: $("#prompt-model"),
    profile: $("#prompt-profile"),
    images: $("#prompt-images"),
    pending: $("#pending-references"),
    create: $("#create-prompt-session"),
    setupError: $("#prompt-setup-error"),
    refreshModels: $("#prompt-refresh-models"),
    refreshSessions: $("#prompt-refresh-sessions"),
    sessionList: $("#prompt-session-list"),
    empty: $("#prompt-empty"),
    editor: $("#prompt-editor"),
    sessionTitle: $("#prompt-session-title"),
    progress: $("#prompt-session-progress"),
    rail: $("#reference-rail"),
    referenceLabel: $("#reference-label"),
    referenceRole: $("#reference-role"),
    referenceImage: $("#reference-image"),
    analysisTitle: $("#analysis-title"),
    review: $("#analysis-review"),
    content: $("#analysis-content"),
    analyze: $("#analyze-reference"),
    save: $("#save-analysis"),
    approve: $("#approve-analysis"),
    message: $("#analysis-message"),
    rewriteInstruction: $("#rewrite-instruction"),
    rewrite: $("#rewrite-analysis"),
    revisionCount: $("#revision-count"),
    revisionList: $("#revision-list"),
    uses: $("#reference-uses"),
    saveUses: $("#save-reference-uses"),
    interpretationTitle: $("#interpretation-title"),
    interpretationReview: $("#interpretation-review"),
    interpretationContent: $("#interpretation-content"),
    interpret: $("#interpret-reference"),
    saveInterpretation: $("#save-interpretation"),
    approveInterpretation: $("#approve-interpretation"),
    interpretationMessage: $("#interpretation-message"),
    interpretationRewriteInstruction: $("#interpretation-rewrite-instruction"),
    rewriteInterpretation: $("#rewrite-interpretation"),
    interpretationRevisionCount: $("#interpretation-revision-count"),
    interpretationRevisionList: $("#interpretation-revision-list"),
  };

  function switchView(view) {
    const promptActive = view === "prompt-lab";
    elements.changeView.hidden = promptActive;
    elements.promptLab.hidden = !promptActive;
    elements.recipeBadge.hidden = promptActive;
    elements.nav.forEach((button) => {
      button.classList.toggle("active", button.dataset.labView === view);
    });
    if (promptActive && !state.initialized) initialize();
  }

  elements.nav.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.labView));
  });

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty response */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
    }
    return payload;
  }

  async function initialize() {
    state.initialized = true;
    showSetupError("");
    try {
      const [spec] = await Promise.all([loadSpec(), loadModels(), loadSessions()]);
      state.spec = spec;
      updateCreateButton();
    } catch (error) {
      showSetupError(error.message);
    }
  }

  async function loadSpec() {
    const spec = await request("/api/prompt-lab/spec");
    elements.profile.replaceChildren();
    spec.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = `${profile.id}@${profile.version}`;
      option.dataset.profileId = profile.id;
      option.dataset.profileVersion = profile.version;
      option.dataset.supportsInterpretation = String(profile.supports_interpretation);
      option.textContent = `${profile.display_name} · ${profile.version}`;
      elements.profile.append(option);
    });
    const preferred = [...elements.profile.options].reverse().find(
      (option) => option.dataset.supportsInterpretation === "true",
    );
    if (preferred) elements.profile.value = preferred.value;
    return spec;
  }

  async function loadModels() {
    elements.refreshModels.disabled = true;
    try {
      const payload = await request("/api/prompt-lab/models");
      const current = elements.model.value;
      elements.model.replaceChildren();
      payload.models.forEach(({ id }) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = id;
        elements.model.append(option);
      });
      const identifiers = payload.models.map((model) => model.id);
      elements.model.value = identifiers.includes(current)
        ? current
        : preferredModel(identifiers);
      updateCreateButton();
    } finally {
      elements.refreshModels.disabled = false;
    }
  }

  function preferredModel(identifiers) {
    return identifiers.find((id) => id.toLowerCase().includes("qwen3.6-27b"))
      || identifiers.find((id) => id.toLowerCase().includes("qwen3.6-35b-a3b"))
      || identifiers[0]
      || "";
  }

  elements.refreshModels.addEventListener("click", async () => {
    showSetupError("");
    try { await loadModels(); } catch (error) { showSetupError(error.message); }
  });

  elements.images.addEventListener("change", () => {
    const maximum = state.spec ? state.spec.max_references : 8;
    const existingKeys = new Set(state.files.map((item) => item.key));
    [...elements.images.files].forEach((file) => {
      if (state.files.length >= maximum) return;
      const key = `${file.name}:${file.size}:${file.lastModified}:${file.type}`;
      if (existingKeys.has(key)) return;
      const index = state.files.length;
      state.files.push({
        key,
        file,
        role: index === 0 ? "character_1" : `reference_${index + 1}`,
        uses: index === 0 ? ["subject", "first_frame"] : ["subject"],
        preview: URL.createObjectURL(file),
      });
      existingKeys.add(key);
    });
    elements.images.value = "";
    renderPendingReferences();
    updateCreateButton();
  });

  function renderPendingReferences() {
    elements.pending.replaceChildren();
    state.files.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "pending-reference";
      const image = document.createElement("img");
      image.src = item.preview;
      image.alt = "";
      const name = document.createElement("span");
      name.textContent = item.file.name || `Image ${index + 1}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-reference";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Retirer ${name.textContent}`);
      remove.addEventListener("click", () => {
        URL.revokeObjectURL(item.preview);
        state.files.splice(index, 1);
        renderPendingReferences();
        updateCreateButton();
      });
      const role = document.createElement("input");
      role.value = item.role;
      role.setAttribute("aria-label", `Rôle de ${name.textContent}`);
      role.placeholder = "character_1";
      role.addEventListener("input", () => {
        item.role = role.value;
        updateCreateButton();
      });
      const uses = createUsageOptions(item.uses, (value, checked) => {
        item.uses = checked
          ? [...item.uses, value]
          : item.uses.filter((use) => use !== value);
        updateCreateButton();
      });
      row.append(image, name, remove, role, uses);
      elements.pending.append(row);
    });
  }

  function createUsageOptions(selected, onChange) {
    const container = document.createElement("div");
    container.className = "usage-options";
    referenceUses.forEach(([value, label]) => {
      const option = document.createElement("label");
      option.className = "usage-option";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.checked = selected.includes(value);
      input.addEventListener("change", () => onChange(value, input.checked));
      const text = document.createElement("span");
      text.textContent = label;
      option.append(input, text);
      container.append(option);
    });
    return container;
  }

  function updateCreateButton() {
    elements.create.disabled = state.busy
      || !state.files.length
      || !elements.model.value
      || !elements.profile.value
      || state.files.some((item) => !item.role.trim() || !item.uses.length);
  }

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showSetupError("");
    const selectedProfile = elements.profile.selectedOptions[0];
    if (!selectedProfile || !state.files.length) return;
    const body = new FormData();
    body.append("model_id", elements.model.value);
    body.append("profile_id", selectedProfile.dataset.profileId);
    body.append("profile_version", selectedProfile.dataset.profileVersion);
    state.files.forEach((item) => {
      body.append("images", item.file, item.file.name);
      body.append("roles", item.role.trim());
      body.append("usages", item.uses.join(","));
    });
    setBusy(true);
    try {
      state.session = await request("/api/prompt-lab/sessions", { method: "POST", body });
      state.selectedReferenceId = state.session.references[0].id;
      renderSession();
      await loadSessions();
    } catch (error) {
      showSetupError(error.message);
    } finally {
      setBusy(false);
    }
  });

  async function loadSessions() {
    const payload = await request("/api/prompt-lab/sessions?limit=8");
    elements.sessionList.replaceChildren();
    if (!payload.sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucune session enregistrée.";
      elements.sessionList.append(empty);
      return;
    }
    payload.sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = `${session.references.length} référence${session.references.length > 1 ? "s" : ""}`;
      const detail = document.createElement("small");
      const approved = session.references.filter((reference) => reference.review_status === "approved").length;
      const interpreted = session.references.filter(
        (reference) => reference.interpretation_review_status === "approved",
      ).length;
      detail.textContent = `${approved}/${session.references.length} observée · ${interpreted}/${session.references.length} interprétée · ${session.model_id}`;
      button.append(title, detail);
      button.addEventListener("click", () => {
        state.session = session;
        state.selectedReferenceId = session.references[0].id;
        renderSession();
      });
      elements.sessionList.append(button);
    });
  }

  elements.refreshSessions.addEventListener("click", async () => {
    try { await loadSessions(); } catch (error) { showSetupError(error.message); }
  });

  function selectedReference() {
    if (!state.session) return null;
    return state.session.references.find((reference) => reference.id === state.selectedReferenceId)
      || state.session.references[0];
  }

  function renderSession() {
    const session = state.session;
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    if (!session) return;
    const approved = session.references.filter((reference) => reference.review_status === "approved").length;
    const interpreted = session.references.filter(
      (reference) => reference.interpretation_review_status === "approved",
    ).length;
    elements.sessionTitle.textContent = `${session.references.length} référence${session.references.length > 1 ? "s" : ""} · ${session.profile.id}@${session.profile.version}`;
    elements.progress.textContent = `${approved}/${session.references.length} observée · ${interpreted}/${session.references.length} interprétée`;
    elements.progress.className = `run-status ${interpreted === session.references.length ? "success" : "active"}`;
    elements.rail.replaceChildren();
    session.references.forEach((reference) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `reference-tab${reference.id === selectedReference().id ? " active" : ""}`;
      const image = document.createElement("img");
      image.src = reference.content_url;
      image.alt = "";
      const label = document.createElement("b");
      label.textContent = reference.label;
      const role = document.createElement("small");
      role.textContent = `${reference.role} · ${reference.uses.join(" + ")}`;
      const status = document.createElement("em");
      status.className = reference.interpretation_review_status === "approved" ? "approved" : "";
      button.append(image, label, role, status);
      button.addEventListener("click", () => {
        state.selectedReferenceId = reference.id;
        elements.message.textContent = "";
        elements.interpretationMessage.textContent = "";
        renderSession();
      });
      elements.rail.append(button);
    });
    renderReference(selectedReference());
  }

  function renderReference(reference) {
    elements.referenceLabel.textContent = reference.label;
    elements.referenceRole.textContent = reference.role;
    elements.referenceImage.src = reference.content_url;
    elements.content.value = reference.active_content || "";
    elements.analysisTitle.textContent = reference.active_content ? "Fiche active" : "Analyse non lancée";
    const approved = reference.review_status === "approved";
    elements.review.textContent = approved ? "Validée" : "À valider";
    elements.review.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.analyze.textContent = reference.active_content ? "Relancer l’analyse" : "Analyser cette image";
    elements.analyze.disabled = state.busy;
    elements.content.disabled = state.busy;
    elements.approve.disabled = state.busy || !reference.active_content || approved;
    elements.rewrite.disabled = state.busy || !reference.active_content || !elements.rewriteInstruction.value.trim();
    elements.revisionCount.textContent = reference.revisions.length;
    elements.revisionList.replaceChildren();
    [...reference.revisions].reverse().forEach((revision) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = `${revision.origin} · ${revision.id.slice(-8)}`;
      const content = document.createElement("p");
      content.textContent = revision.instruction || revision.content.slice(0, 180);
      item.append(title, content);
      elements.revisionList.append(item);
    });
    renderInterpretation(reference);
    updateEditButton();
  }

  function currentProfileSupportsInterpretation() {
    if (!state.spec || !state.session) return false;
    const profile = state.spec.profiles.find(
      (item) => item.id === state.session.profile.id && item.version === state.session.profile.version,
    );
    return Boolean(profile && profile.supports_interpretation);
  }

  function renderInterpretation(reference) {
    const visualApproved = reference.review_status === "approved";
    const supported = currentProfileSupportsInterpretation();
    const stale = reference.interpretation_is_stale;
    const approved = reference.interpretation_review_status === "approved";
    elements.uses.replaceChildren(
      createUsageOptions(reference.uses, updateUsesButton),
    );
    if (!supported) {
      elements.interpretationTitle.textContent = "Disponible avec le profil 0.2.0";
    } else if (!visualApproved) {
      elements.interpretationTitle.textContent = "Validez d’abord l’observation visuelle";
    } else if (stale) {
      elements.interpretationTitle.textContent = "Interprétation obsolète — à régénérer";
    } else {
      elements.interpretationTitle.textContent = reference.active_interpretation
        ? "Interprétation active"
        : "Prête à être générée";
    }
    elements.interpretationReview.textContent = approved
      ? "Validée"
      : stale ? "Obsolète" : reference.active_interpretation ? "À valider" : "À générer";
    elements.interpretationReview.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.interpretationContent.value = reference.active_interpretation || "";
    elements.interpretationContent.disabled = state.busy || !visualApproved || !supported;
    elements.interpret.textContent = reference.active_interpretation
      ? "Régénérer l’interprétation"
      : "Interpréter pour MiniMax";
    elements.interpret.disabled = state.busy || !visualApproved || !supported;
    elements.approveInterpretation.disabled = state.busy || !reference.active_interpretation || stale || approved;
    elements.rewriteInterpretation.disabled = state.busy || !reference.active_interpretation || stale
      || !elements.interpretationRewriteInstruction.value.trim();
    elements.interpretationRevisionCount.textContent = reference.interpretations.length;
    elements.interpretationRevisionList.replaceChildren();
    [...reference.interpretations].reverse().forEach((revision) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = `${revision.origin} · ${revision.id.slice(-8)} · ${revision.uses.join(" + ")}`;
      const content = document.createElement("p");
      content.textContent = revision.instruction || revision.content.slice(0, 180);
      item.append(title, content);
      elements.interpretationRevisionList.append(item);
    });
    updateUsesButton();
    updateInterpretationEditButton();
  }

  function selectedEditorUses() {
    return [...elements.uses.querySelectorAll("input:checked")].map((input) => input.value);
  }

  function updateUsesButton() {
    const reference = selectedReference();
    if (!reference) return;
    const selected = selectedEditorUses();
    elements.saveUses.disabled = state.busy || !selected.length
      || JSON.stringify(selected) === JSON.stringify(reference.uses);
  }

  elements.content.addEventListener("input", updateEditButton);
  function updateEditButton() {
    const reference = selectedReference();
    elements.save.disabled = state.busy || !reference || !elements.content.value.trim()
      || elements.content.value === (reference.active_content || "");
  }

  elements.rewriteInstruction.addEventListener("input", () => {
    const reference = selectedReference();
    elements.rewrite.disabled = state.busy || !reference || !reference.active_content
      || !elements.rewriteInstruction.value.trim();
  });

  elements.interpretationContent.addEventListener("input", updateInterpretationEditButton);
  function updateInterpretationEditButton() {
    const reference = selectedReference();
    elements.saveInterpretation.disabled = state.busy || !reference
      || reference.review_status !== "approved"
      || !elements.interpretationContent.value.trim()
      || elements.interpretationContent.value === (reference.active_interpretation || "");
  }

  elements.interpretationRewriteInstruction.addEventListener("input", () => {
    const reference = selectedReference();
    elements.rewriteInterpretation.disabled = state.busy || !reference
      || !reference.active_interpretation
      || reference.interpretation_is_stale
      || !elements.interpretationRewriteInstruction.value.trim();
  });

  async function referenceAction(action, payload = null) {
    const reference = selectedReference();
    if (!state.session || !reference) return;
    elements.message.className = "message";
    elements.message.textContent = "Traitement en cours…";
    setBusy(true);
    try {
      state.session = await request(
        `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/${action}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      elements.message.textContent = action === "approve" ? "Fiche validée." : "Nouvelle révision enregistrée.";
      if (action === "revise") elements.rewriteInstruction.value = "";
      renderSession();
      await loadSessions();
    } catch (error) {
      elements.message.className = "message error-text";
      elements.message.textContent = error.message;
    } finally {
      setBusy(false);
      renderSession();
    }
  }

  elements.analyze.addEventListener("click", () => referenceAction("analyze"));
  elements.save.addEventListener("click", () => referenceAction("edit", { content: elements.content.value.trim() }));
  elements.approve.addEventListener("click", () => referenceAction("approve"));
  elements.rewrite.addEventListener("click", () => referenceAction("revise", { instruction: elements.rewriteInstruction.value.trim() }));

  async function interpretationAction(path, payload = null) {
    const reference = selectedReference();
    if (!state.session || !reference) return;
    elements.interpretationMessage.className = "message";
    elements.interpretationMessage.textContent = "Traitement en cours…";
    setBusy(true);
    try {
      state.session = await request(
        `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/${path}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      elements.interpretationMessage.textContent = path.endsWith("approve")
        ? "Interprétation validée."
        : path === "uses" ? "Usages enregistrés." : "Nouvelle interprétation enregistrée.";
      if (path.endsWith("revise")) elements.interpretationRewriteInstruction.value = "";
      renderSession();
      await loadSessions();
    } catch (error) {
      elements.interpretationMessage.className = "message error-text";
      elements.interpretationMessage.textContent = error.message;
    } finally {
      setBusy(false);
      renderSession();
    }
  }

  elements.saveUses.addEventListener("click", () => interpretationAction(
    "uses",
    { uses: selectedEditorUses() },
  ));
  elements.interpret.addEventListener("click", () => interpretationAction("interpret"));
  elements.saveInterpretation.addEventListener("click", () => interpretationAction(
    "interpretation/edit",
    { content: elements.interpretationContent.value.trim() },
  ));
  elements.approveInterpretation.addEventListener("click", () => interpretationAction("interpretation/approve"));
  elements.rewriteInterpretation.addEventListener("click", () => interpretationAction(
    "interpretation/revise",
    { instruction: elements.interpretationRewriteInstruction.value.trim() },
  ));

  function setBusy(value) {
    state.busy = value;
    elements.analyze.disabled = value;
    elements.images.disabled = value;
    updateCreateButton();
    if (state.session) renderReference(selectedReference());
  }

  function showSetupError(message) {
    elements.setupError.textContent = message;
    elements.setupError.hidden = !message;
  }
})();
