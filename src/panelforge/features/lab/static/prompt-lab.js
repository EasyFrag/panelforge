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
    i2v: $("#i2v-workspace"),
    ref2v: $("#ref2v-workspace"),
    ref2vDirect: $("#ref2vd-workspace"),
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
    analyzeAll: $("#analyze-all-references"),
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
    analysisStream: {
      container: $("#analysis-stream-state"),
      label: $("#analysis-stream-label"),
      percent: $("#analysis-stream-percent"),
      progress: $("#analysis-stream-progress"),
    },
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
    interpretationStream: {
      container: $("#interpretation-stream-state"),
      label: $("#interpretation-stream-label"),
      percent: $("#interpretation-stream-percent"),
      progress: $("#interpretation-stream-progress"),
    },
    briefReferences: $("#brief-reference-grid"),
    briefSource: $("#brief-source"),
    briefFreedom: $("#brief-freedom"),
    briefFreedomValue: $("#brief-freedom-value"),
    briefFreedomLabel: $("#brief-freedom-label"),
    structureBrief: $("#structure-brief"),
    saveBrief: $("#save-brief"),
    approveBrief: $("#approve-brief"),
    briefReview: $("#brief-review"),
    briefContent: $("#brief-content"),
    briefMessage: $("#brief-message"),
    briefRewriteInstruction: $("#brief-rewrite-instruction"),
    rewriteBrief: $("#rewrite-brief"),
    briefRevisionCount: $("#brief-revision-count"),
    briefRevisionList: $("#brief-revision-list"),
    briefStream: {
      container: $("#brief-stream-state"),
      label: $("#brief-stream-label"),
      percent: $("#brief-stream-percent"),
      progress: $("#brief-stream-progress"),
    },
  };

  function switchView(view) {
    const promptActive = view === "prompt-lab";
    elements.changeView.hidden = view !== "change-view";
    elements.promptLab.hidden = !promptActive;
    elements.i2v.hidden = view !== "i2v";
    elements.ref2v.hidden = view !== "ref2v";
    elements.ref2vDirect.hidden = view !== "ref2v-direct";
    elements.recipeBadge.hidden = view !== "change-view";
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

  async function streamRequest(url, options, onEvent) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = `Erreur HTTP ${response.status}`;
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") detail = payload.detail;
      } catch (_) { /* non-JSON error */ }
      throw new Error(detail);
    }
    if (!response.body) throw new Error("Le navigateur ne fournit pas le flux de réponse.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      buffer = buffer.replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = block.split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) {
          const event = JSON.parse(data);
          if (event.kind === "error") throw new Error(event.message || "Le flux LLM a échoué.");
          onEvent(event);
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
  }

  function updateStreamState(view, event) {
    view.container.hidden = false;
    const terminalClass = ["completed", "truncated"].includes(event.phase)
      ? ` ${event.phase}`
      : "";
    view.container.className = `stream-state${terminalClass}`;
    const lines = event.kind === "status"
      ? String(event.text || "").split(/\r?\n/).filter(Boolean)
      : [];
    const labels = {
      preparing: "Préparation ou chargement du modèle…",
      loading: "Chargement du modèle…",
      generating: "Génération…",
      completed: "Terminé",
      truncated: "Réponse tronquée — budget de tokens épuisé",
    };
    view.label.textContent = lines.at(-1) || labels[event.phase] || "Traitement…";
    if (typeof event.progress === "number") {
      view.progress.value = event.progress;
      view.percent.textContent = `${Math.round(event.progress * 100)} %`;
    } else {
      view.progress.removeAttribute("value");
      view.percent.textContent = "";
    }
  }

  function failStreamState(view, message) {
    view.container.hidden = false;
    view.container.className = "stream-state failed";
    view.label.textContent = message;
    view.percent.textContent = "";
    view.progress.removeAttribute("value");
  }

  async function initialize() {
    state.initialized = true;
    showSetupError("");
    try {
      const [spec] = await Promise.all([
        loadSpec(),
        loadModels(),
        loadSessions(),
      ]);
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
      option.dataset.supportsBrief = String(profile.supports_brief);
      option.textContent = `${profile.display_name} · ${profile.version}`;
      elements.profile.append(option);
    });
    const preferred = [...elements.profile.options].reverse().find(
      (option) => option.dataset.supportsBrief === "true",
    );
    if (preferred) elements.profile.value = preferred.value;
    return spec;
  }

  async function loadModels() {
    elements.refreshModels.disabled = true;
    try {
      const payload = await request("/api/prompt-lab/models");
      const current = elements.model.value;
      window.PanelForgeModelPicker.populate(elements.model, payload.models, current);
      updateCreateButton();
    } finally {
      elements.refreshModels.disabled = false;
    }
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
        uses: ["subject"],
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
      row.append(image, name, remove, role);
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
      const brief = session.brief_complete ? "brief validé" : "brief à préparer";
      detail.textContent = `${approved}/${session.references.length} observée · ${brief} · ${session.model_id}`;
      button.append(title, detail);
      button.addEventListener("click", async () => {
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
    const briefState = session.brief_complete ? "brief validé" : "brief en attente";
    elements.progress.textContent = `${approved}/${session.references.length} observée · ${briefState}`;
    elements.progress.className = `run-status ${session.brief_complete ? "success" : "active"}`;
    const missingAnalyses = session.references.filter((reference) => !reference.active_content).length;
    elements.analyzeAll.hidden = session.references.length < 2;
    elements.analyzeAll.disabled = state.busy || missingAnalyses === 0;
    elements.analyzeAll.textContent = missingAnalyses
      ? (missingAnalyses === session.references.length
        ? `Analyser toutes les images (${missingAnalyses})`
        : `Analyser les images restantes (${missingAnalyses})`)
      : "Toutes les images sont analysées";
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
        elements.analysisStream.container.hidden = true;
        elements.interpretationStream.container.hidden = true;
        renderSession();
      });
      elements.rail.append(button);
    });
    renderReference(selectedReference());
    renderBrief();
    emitPromptSessionState();
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

  function currentProfileSupportsBrief() {
    if (!state.spec || !state.session) return false;
    const profile = state.spec.profiles.find(
      (item) => item.id === state.session.profile.id && item.version === state.session.profile.version,
    );
    return Boolean(profile && profile.supports_brief);
  }

  function renderInterpretation(reference) {
    const visualApproved = reference.review_status === "approved";
    const supported = currentProfileSupportsInterpretation();
    const stale = reference.interpretation_is_stale;
    const approved = reference.interpretation_review_status === "approved";
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
    updateInterpretationEditButton();
  }

  function renderBrief() {
    const session = state.session;
    if (!session) return;
    const active = session.active_brief;
    const supported = currentProfileSupportsBrief();
    const sessionChanged = elements.briefSource.dataset.sessionId !== session.id;
    const revisionChanged = active
      && elements.briefSource.dataset.revisionId !== active.id;
    if (sessionChanged || revisionChanged) {
      elements.briefSource.value = active ? active.source_text : "";
      elements.briefFreedom.value = active ? String(active.creative_freedom) : "50";
      elements.briefContent.value = active ? active.content : "";
      elements.briefSource.dataset.sessionId = session.id;
      elements.briefSource.dataset.revisionId = active ? active.id : "";
    }
    elements.briefContent.disabled = state.busy || !active || !supported;
    elements.briefSource.disabled = state.busy || !supported;
    elements.briefFreedom.disabled = state.busy || !supported;
    renderFreedomLabel();

    const approved = session.brief_complete;
    const stale = session.brief_is_stale;
    elements.briefReview.textContent = approved
      ? "Validé"
      : stale ? "Obsolète" : active ? "À valider" : "À générer";
    elements.briefReview.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.briefReferences.replaceChildren();
    session.references.forEach((reference, index) => {
      const card = document.createElement("article");
      card.className = "brief-reference-card";
      const head = document.createElement("div");
      const image = document.createElement("img");
      image.src = reference.content_url;
      image.alt = "";
      const identity = document.createElement("div");
      const token = document.createElement("button");
      token.type = "button";
      token.className = "reference-token";
      token.textContent = `<Image ${index + 1}>`;
      token.disabled = state.busy || !supported;
      token.title = "Insérer cet identifiant dans le brief";
      token.addEventListener("click", () => insertBriefToken(token.textContent));
      const label = document.createElement("small");
      label.textContent = reference.label;
      identity.append(token, label);
      head.append(image, identity);

      const selected = new Set(reference.uses);
      const options = createUsageOptions(reference.uses, (value, checked) => {
        if (checked) selected.add(value); else selected.delete(value);
        if (!selected.size) {
          selected.add(value);
          renderBrief();
          elements.briefMessage.className = "message warning-text";
          elements.briefMessage.textContent = "Une image doit conserver au moins un usage.";
          return;
        }
        updateReferenceUses(reference.id, [...selected]);
      });
      options.querySelectorAll("input").forEach((input) => { input.disabled = state.busy; });
      card.append(head, options);
      elements.briefReferences.append(card);
    });

    elements.structureBrief.textContent = active ? "Régénérer le brief" : "Structurer le brief";
    elements.structureBrief.disabled = state.busy || !supported || !session.analysis_complete
      || !elements.briefSource.value.trim();
    elements.saveBrief.disabled = state.busy || !active || !elements.briefContent.value.trim()
      || elements.briefContent.value === (active ? active.content : "");
    const draftChanged = active && (
      elements.briefSource.value.trim() !== active.source_text
      || Number(elements.briefFreedom.value) !== active.creative_freedom
      || elements.briefContent.value !== active.content
    );
    elements.approveBrief.disabled = state.busy || !active || stale || approved || draftChanged;
    elements.rewriteBrief.disabled = state.busy || !active || stale || draftChanged
      || !elements.briefRewriteInstruction.value.trim();
    elements.briefRevisionCount.textContent = session.brief_revisions.length;
    elements.briefRevisionList.replaceChildren();
    [...session.brief_revisions].reverse().forEach((revision) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = `${revision.origin} · ${revision.id.slice(-8)} · liberté ${revision.creative_freedom}`;
      const content = document.createElement("p");
      content.textContent = revision.instruction || revision.content.slice(0, 180);
      item.append(title, content);
      elements.briefRevisionList.append(item);
    });
    if (!supported) {
      elements.briefMessage.className = "message warning-text";
      elements.briefMessage.textContent = "Cette ancienne session utilise un profil sans Brief structuré. Créez une session avec le profil 0.3.0.";
    }
  }

  function insertBriefToken(token) {
    const target = elements.briefSource;
    const start = target.selectionStart;
    const end = target.selectionEnd;
    const before = start > 0 && !/\s/.test(target.value[start - 1]) ? " " : "";
    const after = end < target.value.length && !/\s/.test(target.value[end]) ? " " : "";
    target.setRangeText(`${before}${token}${after}`, start, end, "end");
    target.focus();
    target.dispatchEvent(new Event("input"));
  }

  function renderFreedomLabel() {
    const value = Number(elements.briefFreedom.value);
    elements.briefFreedomValue.textContent = String(value);
    elements.briefFreedomLabel.textContent = value <= 20 ? "Factuelle"
      : value <= 40 ? "Conservatrice"
        : value <= 60 ? "Équilibrée"
          : value <= 80 ? "Cinématographique"
            : "Exploratoire";
  }

  async function updateReferenceUses(referenceId, uses) {
    if (!state.session) return;
    elements.briefMessage.className = "message";
    elements.briefMessage.textContent = "Enregistrement des usages…";
    setBusy(true);
    try {
      state.session = await request(
        `/api/prompt-lab/sessions/${state.session.id}/references/${referenceId}/uses`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uses }),
        },
      );
      elements.briefMessage.textContent = "Usages enregistrés. Le Brief devra être revalidé s’il existait déjà.";
      await loadSessions();
    } catch (error) {
      elements.briefMessage.className = "message error-text";
      elements.briefMessage.textContent = error.message;
    } finally {
      setBusy(false);
      renderSession();
    }
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

  elements.analyze.addEventListener("click", () => streamGeneration({
    path: "analyze/stream",
    target: elements.content,
    streamView: elements.analysisStream,
    message: elements.message,
    completedMessage: "Observation générée et enregistrée.",
  }));
  elements.save.addEventListener("click", () => referenceAction("edit", { content: elements.content.value.trim() }));
  elements.approve.addEventListener("click", () => referenceAction("approve"));
  elements.rewrite.addEventListener("click", () => streamGeneration({
    path: "revise/stream",
    payload: { instruction: elements.rewriteInstruction.value.trim() },
    target: elements.content,
    streamView: elements.analysisStream,
    message: elements.message,
    completedMessage: "Observation révisée et enregistrée.",
    clearInstruction: elements.rewriteInstruction,
  }));

  elements.analyzeAll.addEventListener("click", analyzeMissingReferences);

  async function streamGeneration({
    path,
    payload = null,
    target,
    streamView,
    message,
    completedMessage,
    clearInstruction = null,
  }) {
    const reference = selectedReference();
    if (!state.session || !reference) return;
    let result = null;
    setBusy(true);
    try {
      result = await streamEditorRequest({
        url: `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/${path}`,
        payload,
        target,
        streamView,
        message,
        completedMessage,
        clearInstruction,
      });
      if (!result.truncated) await loadSessions();
    } catch (_) {
      // streamEditorRequest already exposes the actionable error in the editor.
    } finally {
      setBusy(false);
      if (result && result.truncated) {
        target.value = result.partialContent;
        target.dispatchEvent(new Event("input"));
      } else {
        renderSession();
      }
    }
  }

  async function streamEditorRequest({
    url,
    payload = null,
    target,
    streamView,
    message,
    completedMessage,
    clearInstruction = null,
    onCompleted = null,
  }) {
    const previousContent = target.value;
    let completed = false;
    let truncated = false;
    let partialContent = "";
    let truncation = null;
    message.className = "message";
    message.textContent = "";
    target.value = "";
    updateStreamState(streamView, {
      phase: "preparing",
      text: "Préparation ou chargement du modèle…",
      progress: null,
    });
    try {
      await streamRequest(
        url,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
        (event) => {
          updateStreamState(streamView, event);
          if (event.kind === "delta" && event.text) {
            target.value += event.text;
            target.scrollTop = target.scrollHeight;
          }
          if (event.kind === "completed" && event.session) {
            state.session = event.session;
            completed = true;
          }
          if (event.kind === "completed" && event.composition && onCompleted) {
            onCompleted(event.composition);
            completed = true;
          }
          if (event.kind === "truncated") {
            truncated = true;
            truncation = event;
            partialContent = target.value || event.text || "";
          }
        },
      );
      if (truncated) {
        const budget = Number.isInteger(truncation && truncation.max_tokens)
          ? truncation.max_tokens.toLocaleString("fr-FR")
          : "configuré";
        message.className = "message warning-text";
        message.textContent = `Réponse tronquée : le budget de ${budget} tokens a été épuisé. Le texte partiel n’a pas été enregistré automatiquement.`;
        return { truncated: true, partialContent };
      }
      if (!completed) {
        throw new Error("Le flux s’est terminé sans résultat persisté.");
      }
      target.scrollTop = 0;
      if (clearInstruction) clearInstruction.value = "";
      message.textContent = completedMessage;
      return { truncated: false, partialContent: "" };
    } catch (error) {
      target.value = previousContent;
      message.className = "message error-text";
      message.textContent = error.message;
      failStreamState(streamView, error.message);
      throw error;
    }
  }

  async function analyzeMissingReferences() {
    if (!state.session) return;
    const pendingIds = state.session.references
      .filter((reference) => !reference.active_content)
      .map((reference) => reference.id);
    if (!pendingIds.length) return;
    let lastResult = null;
    let generated = 0;
    setBusy(true);
    try {
      for (const [index, referenceId] of pendingIds.entries()) {
        state.selectedReferenceId = referenceId;
        renderSession();
        const reference = selectedReference();
        elements.message.textContent = `Analyse ${index + 1}/${pendingIds.length} · ${reference.label}`;
        lastResult = await streamEditorRequest({
          url: `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/analyze/stream`,
          target: elements.content,
          streamView: elements.analysisStream,
          message: elements.message,
          completedMessage: `Observation ${index + 1}/${pendingIds.length} générée.`,
        });
        if (lastResult.truncated) break;
        generated += 1;
        renderSession();
      }
      if (!lastResult || !lastResult.truncated) {
        elements.message.textContent = `${generated} observation${generated > 1 ? "s" : ""} générée${generated > 1 ? "s" : ""}. Validez chaque fiche avant le Brief.`;
      }
      await loadSessions();
    } catch (_) {
      // The failing image stays selected and displays its error.
    } finally {
      setBusy(false);
      if (lastResult && lastResult.truncated) {
        elements.content.value = lastResult.partialContent;
        elements.content.dispatchEvent(new Event("input"));
      } else {
        renderSession();
      }
    }
  }

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

  elements.interpret.addEventListener("click", () => streamGeneration({
    path: "interpret/stream",
    target: elements.interpretationContent,
    streamView: elements.interpretationStream,
    message: elements.interpretationMessage,
    completedMessage: "Interprétation générée et enregistrée.",
  }));
  elements.saveInterpretation.addEventListener("click", () => interpretationAction(
    "interpretation/edit",
    { content: elements.interpretationContent.value.trim() },
  ));
  elements.approveInterpretation.addEventListener("click", () => interpretationAction("interpretation/approve"));
  elements.rewriteInterpretation.addEventListener("click", () => streamGeneration({
    path: "interpretation/revise/stream",
    payload: { instruction: elements.interpretationRewriteInstruction.value.trim() },
    target: elements.interpretationContent,
    streamView: elements.interpretationStream,
    message: elements.interpretationMessage,
    completedMessage: "Interprétation révisée et enregistrée.",
    clearInstruction: elements.interpretationRewriteInstruction,
  }));

  elements.briefSource.addEventListener("input", updateBriefButtons);
  elements.briefContent.addEventListener("input", updateBriefButtons);
  elements.briefRewriteInstruction.addEventListener("input", updateBriefButtons);
  elements.briefFreedom.addEventListener("input", () => {
    renderFreedomLabel();
    updateBriefButtons();
  });

  function updateBriefButtons() {
    const session = state.session;
    if (!session) return;
    const active = session.active_brief;
    const supported = currentProfileSupportsBrief();
    elements.structureBrief.disabled = state.busy || !supported || !session.analysis_complete
      || !elements.briefSource.value.trim();
    elements.saveBrief.disabled = state.busy || !active || !elements.briefContent.value.trim()
      || elements.briefContent.value === active.content;
    const draftChanged = active && (
      elements.briefSource.value.trim() !== active.source_text
      || Number(elements.briefFreedom.value) !== active.creative_freedom
      || elements.briefContent.value !== active.content
    );
    elements.approveBrief.disabled = state.busy || !active || session.brief_is_stale
      || session.brief_complete || draftChanged;
    elements.rewriteBrief.disabled = state.busy || !active || session.brief_is_stale || draftChanged
      || !elements.briefRewriteInstruction.value.trim();
  }

  async function briefAction(path, payload = null) {
    if (!state.session) return;
    elements.briefMessage.className = "message";
    elements.briefMessage.textContent = "Traitement en cours…";
    setBusy(true);
    try {
      state.session = await request(
        `/api/prompt-lab/sessions/${state.session.id}/brief/${path}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      elements.briefMessage.textContent = path === "approve"
        ? "Brief validé."
        : "Nouvelle révision du Brief enregistrée.";
      await loadSessions();
    } catch (error) {
      elements.briefMessage.className = "message error-text";
      elements.briefMessage.textContent = error.message;
    } finally {
      setBusy(false);
      renderSession();
    }
  }

  async function streamBrief(path, payload, completedMessage, clearInstruction = null) {
    if (!state.session) return;
    let result = null;
    setBusy(true);
    try {
      result = await streamEditorRequest({
        url: `/api/prompt-lab/sessions/${state.session.id}/brief/${path}`,
        payload,
        target: elements.briefContent,
        streamView: elements.briefStream,
        message: elements.briefMessage,
        completedMessage,
        clearInstruction,
      });
      if (!result.truncated) await loadSessions();
    } catch (_) {
      // streamEditorRequest already exposes the actionable error in the editor.
    } finally {
      setBusy(false);
      if (result && result.truncated) {
        elements.briefContent.value = result.partialContent;
        elements.briefContent.dispatchEvent(new Event("input"));
      } else {
        renderSession();
      }
    }
  }

  elements.structureBrief.addEventListener("click", () => streamBrief(
    "structure/stream",
    {
      source_text: elements.briefSource.value.trim(),
      creative_freedom: Number(elements.briefFreedom.value),
    },
    "Brief structuré et enregistré.",
  ));
  elements.saveBrief.addEventListener("click", () => briefAction(
    "edit",
    { content: elements.briefContent.value.trim() },
  ));
  elements.approveBrief.addEventListener("click", () => briefAction("approve"));
  elements.rewriteBrief.addEventListener("click", () => streamBrief(
    "revise/stream",
    { instruction: elements.briefRewriteInstruction.value.trim() },
    "Brief révisé et enregistré.",
    elements.briefRewriteInstruction,
  ));

  function setBusy(value) {
    state.busy = value;
    elements.analyze.disabled = value;
    elements.images.disabled = value;
    updateCreateButton();
    if (state.session) {
      renderReference(selectedReference());
      renderBrief();
    }
    emitPromptSessionState();
  }

  function emitPromptSessionState() {
    window.dispatchEvent(new CustomEvent("panelforge:prompt-session", {
      detail: { session: state.session, busy: state.busy },
    }));
  }

  function showSetupError(message) {
    elements.setupError.textContent = message;
    elements.setupError.hidden = !message;
  }

  window.PanelForgePromptLab = {
    request,
    streamRequest,
    updateStreamState,
    failStreamState,
    setBusy,
  };
})();
