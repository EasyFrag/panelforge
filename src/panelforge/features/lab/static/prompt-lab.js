(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
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
      option.textContent = `${profile.display_name} · ${profile.version}`;
      elements.profile.append(option);
    });
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
    state.files.forEach((item) => URL.revokeObjectURL(item.preview));
    const maximum = state.spec ? state.spec.max_references : 8;
    state.files = [...elements.images.files].slice(0, maximum).map((file, index) => ({
      file,
      role: index === 0 ? "character_1" : `reference_${index + 1}`,
      preview: URL.createObjectURL(file),
    }));
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
      const role = document.createElement("input");
      role.value = item.role;
      role.setAttribute("aria-label", `Rôle de ${name.textContent}`);
      role.placeholder = "character_1";
      role.addEventListener("input", () => {
        item.role = role.value;
        updateCreateButton();
      });
      row.append(image, name, role);
      elements.pending.append(row);
    });
  }

  function updateCreateButton() {
    elements.create.disabled = state.busy
      || !state.files.length
      || !elements.model.value
      || !elements.profile.value
      || state.files.some((item) => !item.role.trim());
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
      detail.textContent = `${approved}/${session.references.length} validée · ${session.model_id}`;
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
    elements.sessionTitle.textContent = `${session.references.length} référence${session.references.length > 1 ? "s" : ""} · ${session.profile.id}@${session.profile.version}`;
    elements.progress.textContent = `${approved} / ${session.references.length} validée${approved > 1 ? "s" : ""}`;
    elements.progress.className = `run-status ${approved === session.references.length ? "success" : "active"}`;
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
      role.textContent = reference.role;
      const status = document.createElement("em");
      status.className = reference.review_status === "approved" ? "approved" : "";
      button.append(image, label, role, status);
      button.addEventListener("click", () => {
        state.selectedReferenceId = reference.id;
        elements.message.textContent = "";
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
    updateEditButton();
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
