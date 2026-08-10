(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  if (!core) return;
  const $ = (selector) => document.querySelector(selector);
  const state = {
    spec: null,
    cookbook: null,
    files: { start: null, body: null },
    previews: { start: null, body: null },
    session: null,
    composition: null,
    actionPlanDraft: "",
    actionPlanLive: false,
    busy: false,
  };
  const elements = {
    form: $("#ref2v-session-form"),
    activeCookbook: $("#ref2v-active-cookbook"),
    model: $("#ref2v-model"),
    refreshModels: $("#ref2v-refresh-models"),
    intention: $("#ref2v-intention"),
    freedom: $("#ref2v-freedom"),
    freedomValue: $("#ref2v-freedom-value"),
    freedomLabel: $("#ref2v-freedom-label"),
    start: $("#ref2v-start"),
    setupError: $("#ref2v-setup-error"),
    refreshSessions: $("#ref2v-refresh-sessions"),
    sessionList: $("#ref2v-session-list"),
    empty: $("#ref2v-empty"),
    editor: $("#ref2v-editor"),
    sessionTitle: $("#ref2v-session-title"),
    progress: $("#ref2v-session-progress"),
    newSession: $("#ref2v-new-session"),
    analyzeAll: $("#ref2v-analyze-all"),
    observationReview: $("#ref2v-observation-review"),
    activeIntention: $("#ref2v-active-intention"),
    actionPlan: $("#ref2v-action-plan"),
    actionPlanContent: $("#ref2v-action-plan-content"),
    actionPlanDuration: $("#ref2v-action-plan-duration"),
    actionPlanWarning: $("#ref2v-action-plan-warning"),
    chips: {
      observation: $("#ref2v-chip-observation"),
      brief: $("#ref2v-chip-brief"),
      prompt: $("#ref2v-chip-prompt"),
    },
    brief: stage("brief"),
    prompt: stage("prompt"),
    observations: {
      start: observationStage("start", "ref2v_dressed_start"),
      body: observationStage("body", "ref2v_body_reference"),
    },
  };

  function stage(name) {
    return {
      review: $(`#ref2v-${name}-review`),
      generate: $(`#ref2v-generate-${name}`),
      save: $(`#ref2v-save-${name}`),
      approve: $(`#ref2v-approve-${name}`),
      content: $(`#ref2v-${name}-content`),
      message: $(`#ref2v-${name}-message`),
      instruction: $(`#ref2v-${name}-instruction`),
      rewrite: $(`#ref2v-rewrite-${name}`),
      stream: streamElements(name),
    };
  }

  function observationStage(name, role) {
    return {
      ...stage(name),
      role,
      imageInput: $(`#ref2v-${name}-image`),
      uploadPreview: $(`#ref2v-${name}-preview`),
      uploadTitle: $(`#ref2v-${name}-title`),
      uploadCaption: $(`#ref2v-${name}-caption`),
      referenceImage: $(`#ref2v-${name}-reference`),
    };
  }

  function streamElements(name) {
    return {
      container: $(`#ref2v-${name}-stream-state`),
      label: $(`#ref2v-${name}-stream-label`),
      percent: $(`#ref2v-${name}-stream-percent`),
      progress: $(`#ref2v-${name}-stream-progress`),
    };
  }

  function selectedProfile() {
    if (!state.spec) return null;
    return (state.spec.profiles || []).find(
      (profile) => profile.id === "minimax.h3.reference" && profile.version === "0.3.0",
    ) || (state.spec.profiles || []).find((profile) => profile.supports_brief) || null;
  }

  async function initialize() {
    try {
      const [spec, cookbooks] = await Promise.all([
        core.request("/api/prompt-lab/spec"),
        core.request("/api/prompt-lab/cookbooks"),
      ]);
      state.spec = spec;
      state.cookbook = (cookbooks.cookbooks || []).find(
        (item) => item.id === "undressing.single_shot" && item.version === "0.7.1",
      ) || null;
      if (!state.cookbook) throw new Error("Cookbook Ref2V undressing indisponible.");
      renderCookbookVersion();
      await Promise.all([loadModels(), loadSessions()]);
      updateStartButton();
    } catch (error) {
      showSetupError(error.message);
    }
  }

  async function loadModels() {
    const selected = elements.model.value;
    const payload = await core.request("/api/prompt-lab/models");
    window.PanelForgeModelPicker.populate(elements.model, payload.models || [], selected);
    updateStartButton();
  }

  async function loadSessions() {
    const payload = await core.request("/api/prompt-lab/sessions?limit=20");
    const sessions = (payload.sessions || []).filter((session) => {
      const roles = new Set((session.references || []).map((reference) => reference.role));
      return session.references.length === 2
        && roles.has("ref2v_dressed_start")
        && roles.has("ref2v_body_reference");
    });
    elements.sessionList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun parcours Ref2V enregistré.";
      elements.sessionList.append(empty);
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = referenceByRole(session, "ref2v_dressed_start").label;
      const detail = document.createElement("small");
      const approved = session.references.filter(
        (reference) => reference.review_status === "approved",
      ).length;
      detail.textContent = `${approved}/2 observations validées · ${session.brief_complete ? "brief validé" : "brief à préparer"}`;
      button.append(title, detail);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  async function openSession(session) {
    state.session = session;
    state.composition = null;
    state.actionPlanDraft = "";
    state.actionPlanLive = false;
    if (session.active_brief) {
      elements.intention.value = session.active_brief.source_text;
      elements.freedom.value = String(session.active_brief.creative_freedom);
    }
    updateFreedom();
    try {
      const payload = await core.request(`/api/prompt-lab/sessions/${session.id}/composition`);
      state.composition = payload.composition;
    } catch (error) {
      showStageError(elements.prompt, error);
    }
    render();
  }

  function referenceByRole(session, role) {
    return session.references.find((reference) => reference.role === role);
  }

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showSetupError("");
    const profile = selectedProfile();
    if (!state.files.start || !state.files.body || !profile || !state.cookbook) return;
    const body = new FormData();
    body.append("images", state.files.start, state.files.start.name);
    body.append("roles", "ref2v_dressed_start");
    body.append("usages", "first_frame,subject");
    body.append("images", state.files.body, state.files.body.name);
    body.append("roles", "ref2v_body_reference");
    body.append("usages", "subject");
    body.append("model_id", elements.model.value);
    body.append("profile_id", profile.id);
    body.append("profile_version", profile.version);
    setBusy(true);
    try {
      state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      state.composition = null;
      state.actionPlanDraft = "";
      state.actionPlanLive = false;
      render();
      await loadSessions();
    } catch (error) {
      showSetupError(error.message);
    } finally {
      setBusy(false);
    }
  });

  for (const name of ["start", "body"]) {
    const view = elements.observations[name];
    view.imageInput.addEventListener("change", () => {
      const file = view.imageInput.files && view.imageInput.files[0];
      if (!file) return;
      if (state.previews[name]) URL.revokeObjectURL(state.previews[name]);
      state.files[name] = file;
      state.previews[name] = URL.createObjectURL(file);
      view.uploadPreview.src = state.previews[name];
      view.uploadPreview.hidden = false;
      view.uploadTitle.textContent = file.name;
      view.uploadCaption.textContent = `${Math.ceil(file.size / 1024)} Kio · cliquer pour remplacer`;
      updateStartButton();
    });
  }

  function updateFreedom() {
    const value = Number(elements.freedom.value);
    elements.freedomValue.value = String(value);
    elements.freedomLabel.textContent = value <= 20
      ? "Très factuelle" : value <= 45 ? "Encadrée" : value <= 70 ? "Cinématographique" : "Très libre";
  }

  function updateStartButton() {
    elements.start.disabled = state.busy
      || !state.files.start || !state.files.body
      || !elements.model.value || !elements.intention.value.trim()
      || !selectedProfile() || !state.cookbook;
  }

  function render() {
    const session = state.session;
    renderCookbookVersion();
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    updateStartButton();
    if (!session) {
      elements.actionPlan.hidden = true;
      elements.actionPlanContent.value = "";
      return;
    }
    const refs = {
      start: referenceByRole(session, "ref2v_dressed_start"),
      body: referenceByRole(session, "ref2v_body_reference"),
    };
    const observationsApproved = Object.values(refs).every(
      (reference) => reference.review_status === "approved",
    );
    const activeBrief = session.active_brief;
    const briefInputsCurrent = !activeBrief || (
      activeBrief.source_text.trim() === elements.intention.value.trim()
      && Number(activeBrief.creative_freedom) === Number(elements.freedom.value)
    );
    const briefApproved = session.brief_complete && briefInputsCurrent;
    const promptDocument = state.composition && state.composition.documents
      ? state.composition.documents.final_prompt : null;
    const promptApproved = Boolean(promptDocument && promptDocument.complete);
    elements.sessionTitle.textContent = `${refs.start.label} + ${refs.body.label}`;
    elements.observations.start.referenceImage.src = refs.start.content_url;
    elements.observations.body.referenceImage.src = refs.body.content_url;
    elements.activeIntention.textContent = (activeBrief && activeBrief.source_text)
      || elements.intention.value.trim() || "À renseigner";
    elements.progress.textContent = !observationsApproved ? "Observations requises"
      : !briefApproved ? "Brief requis" : !promptApproved ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptApproved ? "success" : "active"}`;
    setChip(elements.chips.observation, observationsApproved, !observationsApproved);
    setChip(elements.chips.brief, briefApproved, observationsApproved && !briefApproved);
    setChip(elements.chips.prompt, promptApproved, briefApproved && !promptApproved);
    elements.observationReview.textContent = observationsApproved ? "Validées" : "À compléter";
    elements.observationReview.className = `review-pill ${observationsApproved ? "approved" : "pending"}`;
    elements.analyzeAll.disabled = state.busy;
    renderObservation(elements.observations.start, refs.start);
    renderObservation(elements.observations.body, refs.body);
    renderBrief(session, observationsApproved, briefInputsCurrent);
    renderPrompt(promptDocument, briefApproved);
    renderActionPlan();
  }

  function renderCookbookVersion() {
    const cookbook = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    elements.activeCookbook.textContent = cookbook
      ? `${cookbook.id}@${cookbook.version}` : "indisponible";
  }

  function setChip(chip, complete, active) {
    chip.classList.toggle("active", active || complete);
    chip.classList.toggle("future", !active && !complete);
  }

  function hydrate(target, key, value) {
    if (target.dataset.hydrationKey !== key) {
      target.value = value || "";
      target.dataset.hydrationKey = key;
    }
  }

  function renderObservation(view, reference) {
    const active = reference.active_revision_id;
    hydrate(view.content, `observation:${active || "none"}`, reference.active_content);
    const draft = view.content.value.trim() !== (reference.active_content || "").trim();
    const approved = reference.review_status === "approved";
    view.generate.disabled = state.busy;
    view.generate.textContent = active ? "Relancer" : "Analyser";
    view.content.disabled = state.busy;
    view.save.disabled = state.busy || !draft || !view.content.value.trim();
    view.approve.disabled = state.busy || !active || approved || draft;
    view.instruction.disabled = state.busy || !active;
    view.rewrite.disabled = state.busy || !active || !view.instruction.value.trim();
  }

  function renderBrief(session, observationsApproved, inputsCurrent) {
    const active = session.active_brief;
    hydrate(elements.brief.content, `brief:${active ? active.id : "none"}`, active && active.content);
    const draft = elements.brief.content.value.trim() !== (active ? active.content : "").trim();
    const approved = session.brief_complete && inputsCurrent;
    elements.brief.review.textContent = approved ? "Validé"
      : active && !inputsCurrent ? "Intention modifiée"
        : active ? "À valider" : "Observations requises";
    elements.brief.review.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.brief.generate.disabled = state.busy || !observationsApproved || !elements.intention.value.trim();
    elements.brief.content.disabled = state.busy || !observationsApproved;
    elements.brief.save.disabled = state.busy || !observationsApproved || !draft || !elements.brief.content.value.trim();
    elements.brief.approve.disabled = state.busy || !active || approved || draft || !inputsCurrent;
    elements.brief.instruction.disabled = state.busy || !active || !inputsCurrent;
    elements.brief.rewrite.disabled = state.busy || !active || !inputsCurrent || !elements.brief.instruction.value.trim();
  }

  function renderPrompt(documentState, briefApproved) {
    const active = documentState && documentState.active_revision_id;
    hydrate(elements.prompt.content, `prompt:${active || "none"}`, documentState && documentState.active_content);
    const draft = Boolean(documentState)
      && elements.prompt.content.value.trim() !== (documentState.active_content || "").trim();
    const complete = Boolean(documentState && documentState.complete);
    const stale = Boolean(documentState && documentState.stale);
    const errors = documentState ? documentState.validation_errors : [];
    const warnings = documentState ? documentState.validation_warnings : [];
    elements.prompt.review.textContent = complete ? "Validé" : stale ? "Obsolète"
      : active ? "À valider" : briefApproved ? "À générer" : "Brief requis";
    elements.prompt.review.className = `review-pill ${complete ? "approved" : "pending"}`;
    elements.prompt.generate.disabled = state.busy || !briefApproved;
    elements.prompt.content.disabled = state.busy || !briefApproved || !state.composition;
    elements.prompt.save.disabled = state.busy || !state.composition || !briefApproved
      || !draft || !elements.prompt.content.value.trim();
    elements.prompt.approve.disabled = state.busy || !active || stale || complete || draft || Boolean(errors.length);
    elements.prompt.instruction.disabled = state.busy || !active || stale;
    elements.prompt.rewrite.disabled = state.busy || !active || stale || !elements.prompt.instruction.value.trim();
    const lint = $("#ref2v-prompt-lint");
    lint.replaceChildren();
    const result = document.createElement(errors.length || warnings.length ? "ul" : "small");
    if (draft) result.textContent = "Brouillon local non enregistré : validation à recalculer.";
    else if (!active) result.textContent = "Le format Ref2V compilé sera contrôlé après génération.";
    else if (!errors.length && !warnings.length) result.textContent = "Format Ref2V valide : mapping verrouillé, deux références et un plan continu.";
    else {
      errors.forEach((error) => {
        const item = document.createElement("li");
        item.textContent = error;
        result.append(item);
      });
      warnings.forEach((warning) => {
        const item = document.createElement("li");
        item.textContent = `Avertissement : ${warning}`;
        result.append(item);
      });
    }
    lint.append(result);
    $("#ref2v-copy-prompt").disabled = state.busy || !complete || stale || draft || Boolean(errors.length);
  }

  function renderActionPlan() {
    const cookbook = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    const documentState = state.composition && state.composition.documents
      ? state.composition.documents.beat_sheet : null;
    const visible = Boolean(
      cookbook && ["0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.7.1"].includes(cookbook.version),
    );
    const persisted = documentState && documentState.active_content
      ? documentState.active_content : "";
    elements.actionPlan.hidden = !visible;
    elements.actionPlanContent.value = !visible ? ""
      : state.actionPlanLive
        ? state.actionPlanDraft || "Planification en cours…"
        : persisted || state.actionPlanDraft || "Aucun plan validé pour le moment.";
    const warnings = documentState && documentState.validation_warnings
      ? documentState.validation_warnings : [];
    elements.actionPlanWarning.textContent = warnings.join(" ");
    elements.actionPlanWarning.hidden = !visible || !warnings.length;
    let durationLabel = "";
    if (persisted) {
      try {
        const plan = JSON.parse(persisted);
        if (plan.requested_duration_seconds && plan.duration_seconds) {
          durationLabel = `Durée demandée : ${plan.requested_duration_seconds} s · durée planifiée : ${plan.duration_seconds} s`;
        }
      } catch (_) {
        durationLabel = "";
      }
    }
    elements.actionPlanDuration.textContent = durationLabel;
    elements.actionPlanDuration.hidden = !visible || !durationLabel;
  }

  async function sessionAction(url, payload, view, success) {
    setBusy(true);
    try {
      state.session = await core.request(url, {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      view.message.className = "message";
      view.message.textContent = success;
    } catch (error) {
      showStageError(view, error);
    } finally {
      setBusy(false);
    }
  }

  async function promptAction(action, payload = null) {
    setBusy(true);
    try {
      const response = await core.request(
        `/api/prompt-lab/sessions/${state.session.id}/final-prompt/${action}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      state.composition = response.composition;
      elements.prompt.message.className = "message";
      elements.prompt.message.textContent = action === "approve" ? "Prompt validé." : "Correction enregistrée.";
    } catch (error) {
      showStageError(elements.prompt, error);
    } finally {
      setBusy(false);
    }
  }

  async function streamReference(view, action = "analyze") {
    const reference = referenceByRole(state.session, view.role);
    const revision = action === "revise";
    const payload = revision ? { instruction: view.instruction.value.trim() } : null;
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/${action}/stream`,
      payload,
      view,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Révision enregistrée." : "Observation générée et enregistrée.",
    );
    if (completed && revision) view.instruction.value = "";
    return completed;
  }

  async function streamBrief(revision = false) {
    const payload = revision
      ? { instruction: elements.brief.instruction.value.trim() }
      : { source_text: elements.intention.value.trim(), creative_freedom: Number(elements.freedom.value) };
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/brief/${revision ? "revise" : "structure"}/stream`,
      payload,
      elements.brief,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Révision du brief enregistrée." : "Brief généré et enregistré.",
    );
    if (completed && revision) elements.brief.instruction.value = "";
  }

  async function streamPrompt(revision = false) {
    try {
      if (!state.composition) await configureRef2V();
      if (!revision) {
        state.actionPlanDraft = "";
        state.actionPlanLive = true;
        elements.actionPlan.open = true;
        renderActionPlan();
      }
      const payload = revision ? { instruction: elements.prompt.instruction.value.trim() } : null;
      const completed = await streamResult(
        `/api/prompt-lab/sessions/${state.session.id}/final-prompt/${revision ? "revise" : "generate"}/stream`,
        payload,
        elements.prompt,
        (event) => { if (event.composition) state.composition = event.composition; },
        revision ? "Révision du prompt enregistrée." : "Prompt Ref2V compilé et enregistré.",
      );
      if (completed && revision) elements.prompt.instruction.value = "";
    } catch (error) {
      showStageError(elements.prompt, error);
      setBusy(false);
    }
  }

  async function configureRef2V() {
    const start = referenceByRole(state.session, "ref2v_dressed_start");
    const body = referenceByRole(state.session, "ref2v_body_reference");
    const response = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: state.cookbook.id,
          cookbook_version: state.cookbook.version,
          bindings: { dressed_start: [start.id], body_reference: [body.id] },
        }),
      },
    );
    state.composition = response.composition;
  }

  async function streamResult(url, payload, view, onEvent, success) {
    const previous = view.content.value;
    let received = false;
    let receivedActionPlan = false;
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
        if (event.composition || event.session) {
          onEvent(event);
          if (event.composition && event.document_stage === "beat_sheet") {
            state.actionPlanLive = false;
          }
          render();
          if (event.composition && event.document_stage === "beat_sheet") {
            elements.actionPlanContent.scrollTop = 0;
          }
        }
        if (event.kind === "delta" && event.text) {
          if (event.document_stage === "beat_sheet") {
            receivedActionPlan = true;
            state.actionPlanDraft += event.text;
            elements.actionPlan.hidden = false;
            elements.actionPlanContent.value = state.actionPlanDraft;
            elements.actionPlanContent.scrollTop = elements.actionPlanContent.scrollHeight;
          } else {
            received = true;
            view.content.value += event.text;
            view.content.scrollTop = view.content.scrollHeight;
          }
        }
        if (event.kind === "completed") {
          completed = true;
        }
        if (event.kind === "truncated") {
          if (event.document_stage === "beat_sheet") {
            receivedActionPlan = true;
            if (!state.actionPlanDraft && event.text) state.actionPlanDraft = event.text;
            renderActionPlan();
          } else {
            received = true;
          }
          view.message.className = "message warning-text";
          view.message.textContent = "Réponse tronquée : le brouillon partiel reste éditable.";
        }
      });
      if (!completed) throw new Error("Le flux s’est terminé sans résultat persistant.");
      state.actionPlanLive = false;
      view.content.scrollTop = 0;
      view.message.textContent = success;
      return true;
    } catch (error) {
      if (!received) view.content.value = previous;
      showStageError(view, error, received);
      if (!received && receivedActionPlan) {
        view.message.textContent = `${error.message} Le plan candidat rejeté reste visible pour diagnostic.`;
      }
      core.failStreamState(view.stream, error.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  function showStageError(view, error, preserved = false) {
    view.message.className = "message error-text";
    view.message.textContent = preserved
      ? `${error.message} Le candidat reçu reste disponible comme brouillon.`
      : error.message;
  }

  function setBusy(value) {
    state.busy = value;
    render();
  }

  function showSetupError(message) {
    elements.setupError.textContent = message;
    elements.setupError.hidden = !message;
  }

  elements.refreshModels.addEventListener("click", () => loadModels().catch((error) => showSetupError(error.message)));
  elements.refreshSessions.addEventListener("click", () => loadSessions().catch((error) => showSetupError(error.message)));
  elements.model.addEventListener("change", updateStartButton);
  elements.intention.addEventListener("input", () => { updateStartButton(); render(); });
  elements.freedom.addEventListener("input", () => { updateFreedom(); render(); });
  elements.newSession.addEventListener("click", () => {
    state.session = null;
    state.composition = null;
    state.actionPlanDraft = "";
    state.actionPlanLive = false;
    render();
  });
  elements.analyzeAll.addEventListener("click", async () => {
    for (const name of ["start", "body"]) {
      const reference = referenceByRole(state.session, elements.observations[name].role);
      if (reference.review_status !== "approved") await streamReference(elements.observations[name]);
    }
  });

  for (const name of ["start", "body"]) {
    const view = elements.observations[name];
    view.content.addEventListener("input", render);
    view.instruction.addEventListener("input", render);
    view.generate.addEventListener("click", () => streamReference(view));
    view.save.addEventListener("click", () => {
      const reference = referenceByRole(state.session, view.role);
      return sessionAction(
        `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/edit`,
        { content: view.content.value.trim() }, view, "Observation corrigée.",
      );
    });
    view.approve.addEventListener("click", () => {
      const reference = referenceByRole(state.session, view.role);
      return sessionAction(
        `/api/prompt-lab/sessions/${state.session.id}/references/${reference.id}/approve`,
        null, view, "Observation validée.",
      );
    });
    view.rewrite.addEventListener("click", () => streamReference(view, "revise"));
  }

  elements.brief.content.addEventListener("input", render);
  elements.brief.instruction.addEventListener("input", render);
  elements.brief.generate.addEventListener("click", () => streamBrief(false));
  elements.brief.save.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/brief/edit`,
    { content: elements.brief.content.value.trim() }, elements.brief, "Brief corrigé.",
  ));
  elements.brief.approve.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/brief/approve`, null, elements.brief, "Brief validé.",
  ));
  elements.brief.rewrite.addEventListener("click", () => streamBrief(true));

  elements.prompt.content.addEventListener("input", render);
  elements.prompt.instruction.addEventListener("input", render);
  elements.prompt.generate.addEventListener("click", () => streamPrompt(false));
  elements.prompt.save.addEventListener("click", () => promptAction("edit", { content: elements.prompt.content.value.trim() }));
  elements.prompt.approve.addEventListener("click", () => promptAction("approve"));
  elements.prompt.rewrite.addEventListener("click", () => streamPrompt(true));
  $("#ref2v-copy-prompt").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(elements.prompt.content.value);
      elements.prompt.message.className = "message";
      elements.prompt.message.textContent = "Prompt copié.";
    } catch (_) {
      elements.prompt.content.select();
      elements.prompt.message.className = "message warning-text";
      elements.prompt.message.textContent = "Utilisez Ctrl+C pour copier le prompt.";
    }
  });

  updateFreedom();
  render();
  initialize();
})();
