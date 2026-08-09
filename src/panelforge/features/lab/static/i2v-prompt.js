(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  if (!core) return;
  const $ = (selector) => document.querySelector(selector);
  const state = {
    spec: null,
    cookbook: null,
    file: null,
    previewUrl: null,
    session: null,
    composition: null,
    busy: false,
  };
  const elements = {
    form: $("#i2v-session-form"),
    activeCookbook: $("#i2v-active-cookbook"),
    model: $("#i2v-model"),
    refreshModels: $("#i2v-refresh-models"),
    image: $("#i2v-image"),
    uploadPreview: $("#i2v-upload-preview"),
    uploadTitle: $("#i2v-upload-title"),
    uploadCaption: $("#i2v-upload-caption"),
    intention: $("#i2v-intention"),
    freedom: $("#i2v-freedom"),
    freedomValue: $("#i2v-freedom-value"),
    freedomLabel: $("#i2v-freedom-label"),
    start: $("#i2v-start"),
    setupError: $("#i2v-setup-error"),
    refreshSessions: $("#i2v-refresh-sessions"),
    sessionList: $("#i2v-session-list"),
    empty: $("#i2v-empty"),
    editor: $("#i2v-editor"),
    sessionTitle: $("#i2v-session-title"),
    progress: $("#i2v-session-progress"),
    newSession: $("#i2v-new-session"),
    referenceImage: $("#i2v-reference-image"),
    activeIntention: $("#i2v-active-intention"),
    chips: {
      observation: $("#i2v-chip-observation"),
      brief: $("#i2v-chip-brief"),
      prompt: $("#i2v-chip-prompt"),
    },
    observation: stage("observation"),
    brief: stage("brief"),
    prompt: stage("prompt"),
  };

  function stage(name) {
    return {
      name,
      review: $(`#i2v-${name}-review`),
      generate: $(`#i2v-generate-${name}`),
      save: $(`#i2v-save-${name}`),
      approve: $(`#i2v-approve-${name}`),
      content: $(`#i2v-${name}-content`),
      message: $(`#i2v-${name}-message`),
      instruction: $(`#i2v-${name}-instruction`),
      rewrite: $(`#i2v-rewrite-${name}`),
      stream: {
        container: $(`#i2v-${name}-stream-state`),
        label: $(`#i2v-${name}-stream-label`),
        percent: $(`#i2v-${name}-stream-percent`),
        progress: $(`#i2v-${name}-stream-progress`),
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
      state.cookbook = (cookbooks.cookbooks || []).find(
        (item) => item.id === "minimax.h3.i2v.simple"
          && item.version === "0.2.0",
      ) || null;
      if (!state.cookbook) throw new Error("Cookbook MiniMax H3 I2V indisponible.");
      renderCookbookVersion();
      await Promise.all([loadModels(), loadSessions()]);
      updateStartButton();
    } catch (error) {
      showSetupError(error.message);
    }
  }

  function selectedProfile() {
    if (!state.spec) return null;
    return (state.spec.profiles || []).find(
      (profile) => profile.id === "minimax.h3.reference" && profile.version === "0.3.0",
    ) || (state.spec.profiles || []).find((profile) => profile.supports_brief) || null;
  }

  async function loadModels() {
    const selected = elements.model.value;
    const payload = await core.request("/api/prompt-lab/models");
    elements.model.replaceChildren();
    (payload.models || []).forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.id;
      elements.model.append(option);
    });
    if (selected && [...elements.model.options].some((option) => option.value === selected)) {
      elements.model.value = selected;
    }
    updateStartButton();
  }

  async function loadSessions() {
    const payload = await core.request("/api/prompt-lab/sessions?limit=20");
    const sessions = (payload.sessions || []).filter(
      (session) => session.references.length === 1
        && session.references[0].role === "i2v_first_frame",
    );
    elements.sessionList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun parcours I2V enregistré.";
      elements.sessionList.append(empty);
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = session.references[0].label;
      const detail = document.createElement("small");
      const observation = session.references[0].review_status === "approved"
        ? "observation validée" : "observation à préparer";
      detail.textContent = `${observation} · ${session.brief_complete ? "brief validé" : "brief à préparer"}`;
      button.append(title, detail);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  async function openSession(session) {
    state.session = session;
    state.composition = null;
    const activeBrief = session.active_brief;
    elements.intention.value = activeBrief ? activeBrief.source_text : "";
    if (activeBrief) elements.freedom.value = String(activeBrief.creative_freedom);
    updateFreedom();
    try {
      const payload = await core.request(
        `/api/prompt-lab/sessions/${session.id}/composition`,
      );
      state.composition = payload.composition;
    } catch (error) {
      elements.prompt.message.className = "message error-text";
      elements.prompt.message.textContent = error.message;
    }
    render();
  }

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showSetupError("");
    const profile = selectedProfile();
    if (!state.file || !profile || !state.cookbook) return;
    const body = new FormData();
    body.append("images", state.file, state.file.name);
    body.append("roles", "i2v_first_frame");
    body.append("usages", "first_frame");
    body.append("model_id", elements.model.value);
    body.append("profile_id", profile.id);
    body.append("profile_version", profile.version);
    setBusy(true);
    try {
      const session = await core.request("/api/prompt-lab/sessions", {
        method: "POST",
        body,
      });
      state.session = session;
      state.composition = null;
      render();
      await loadSessions();
    } catch (error) {
      showSetupError(error.message);
    } finally {
      setBusy(false);
    }
  });

  elements.image.addEventListener("change", () => {
    const file = elements.image.files && elements.image.files[0];
    if (!file) return;
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.file = file;
    state.previewUrl = URL.createObjectURL(file);
    elements.uploadPreview.src = state.previewUrl;
    elements.uploadPreview.hidden = false;
    elements.uploadTitle.textContent = file.name;
    elements.uploadCaption.textContent = `${Math.ceil(file.size / 1024)} Kio · cliquer pour remplacer`;
    updateStartButton();
  });

  function updateFreedom() {
    const value = Number(elements.freedom.value);
    elements.freedomValue.value = String(value);
    elements.freedomLabel.textContent = value <= 20
      ? "Très factuelle" : value <= 45 ? "Encadrée" : value <= 70 ? "Cinématographique" : "Très libre";
  }

  function updateStartButton() {
    elements.start.disabled = state.busy
      || !state.file
      || !elements.model.value
      || !elements.intention.value.trim()
      || !selectedProfile()
      || !state.cookbook;
  }

  function render() {
    const session = state.session;
    renderCookbookVersion();
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    updateStartButton();
    if (!session) return;
    const reference = session.references[0];
    const observationApproved = reference.review_status === "approved";
    const activeBrief = session.active_brief;
    const briefInputsCurrent = !activeBrief || (
      activeBrief.source_text.trim() === elements.intention.value.trim()
      && Number(activeBrief.creative_freedom) === Number(elements.freedom.value)
    );
    const briefApproved = session.brief_complete && briefInputsCurrent;
    const promptDocument = state.composition && state.composition.documents
      ? state.composition.documents.final_prompt : null;
    const promptApproved = Boolean(promptDocument && promptDocument.complete);
    elements.sessionTitle.textContent = reference.label;
    elements.referenceImage.src = reference.content_url;
    elements.activeIntention.textContent = (session.active_brief && session.active_brief.source_text)
      || elements.intention.value.trim() || "À renseigner";
    const currentStep = !observationApproved ? "Observation requise"
      : !briefApproved ? "Brief requis" : !promptApproved ? "Prompt requis" : "Parcours validé";
    elements.progress.textContent = currentStep;
    elements.progress.className = `run-status ${promptApproved ? "success" : "active"}`;
    setChip(elements.chips.observation, observationApproved, !observationApproved);
    setChip(elements.chips.brief, briefApproved, observationApproved && !briefApproved);
    setChip(elements.chips.prompt, promptApproved, briefApproved && !promptApproved);
    renderObservation(reference);
    renderBrief(session, briefInputsCurrent);
    renderPrompt(promptDocument, briefApproved);
  }

  function renderCookbookVersion() {
    const reference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    elements.activeCookbook.textContent = reference
      ? `${reference.id}@${reference.version}` : "indisponible";
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

  function renderObservation(reference) {
    const active = reference.active_revision_id;
    hydrate(elements.observation.content, `observation:${active || "none"}`, reference.active_content);
    const draft = elements.observation.content.value.trim() !== (reference.active_content || "").trim();
    const approved = reference.review_status === "approved";
    elements.observation.review.textContent = approved ? "Validée" : active ? "À valider" : "À générer";
    elements.observation.review.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.observation.generate.disabled = state.busy;
    elements.observation.generate.textContent = active ? "Relancer l’analyse" : "Analyser l’image";
    elements.observation.content.disabled = state.busy;
    elements.observation.save.disabled = state.busy || !draft || !elements.observation.content.value.trim();
    elements.observation.approve.disabled = state.busy || !active || approved || draft;
    elements.observation.instruction.disabled = state.busy || !active;
    elements.observation.rewrite.disabled = state.busy || !active || !elements.observation.instruction.value.trim();
  }

  function renderBrief(session, inputsCurrent) {
    const active = session.active_brief;
    hydrate(elements.brief.content, `brief:${active ? active.id : "none"}`, active && active.content);
    const draft = elements.brief.content.value.trim() !== (active ? active.content : "").trim();
    const approved = session.brief_complete && inputsCurrent;
    const observationApproved = session.references[0].review_status === "approved";
    elements.brief.review.textContent = approved ? "Validé"
      : active && !inputsCurrent ? "Intention modifiée"
        : active ? "À valider" : "Observation requise";
    elements.brief.review.className = `review-pill ${approved ? "approved" : "pending"}`;
    elements.brief.generate.disabled = state.busy || !observationApproved || !elements.intention.value.trim();
    elements.brief.content.disabled = state.busy || !observationApproved;
    elements.brief.save.disabled = state.busy || !observationApproved || !draft || !elements.brief.content.value.trim();
    elements.brief.approve.disabled = state.busy || !active || approved || draft || !inputsCurrent;
    elements.brief.instruction.disabled = state.busy || !active || !inputsCurrent;
    elements.brief.rewrite.disabled = state.busy || !active || !inputsCurrent || !elements.brief.instruction.value.trim();
  }

  function renderPrompt(stageDocument, briefApproved) {
    const active = stageDocument && stageDocument.active_revision_id;
    hydrate(elements.prompt.content, `prompt:${active || "none"}`, stageDocument && stageDocument.active_content);
    const draft = Boolean(stageDocument)
      && elements.prompt.content.value.trim() !== (stageDocument.active_content || "").trim();
    const complete = Boolean(stageDocument && stageDocument.complete);
    const stale = Boolean(stageDocument && stageDocument.stale);
    const errors = stageDocument ? stageDocument.validation_errors : [];
    elements.prompt.review.textContent = complete ? "Validé" : stale ? "Obsolète" : active ? "À valider" : "Brief requis";
    elements.prompt.review.className = `review-pill ${complete ? "approved" : "pending"}`;
    elements.prompt.generate.disabled = state.busy || !briefApproved;
    elements.prompt.content.disabled = state.busy || !briefApproved || !state.composition;
    elements.prompt.save.disabled = state.busy || !state.composition || !briefApproved
      || !draft || !elements.prompt.content.value.trim();
    elements.prompt.approve.disabled = state.busy || !active || stale || complete || draft || Boolean(errors.length);
    elements.prompt.instruction.disabled = state.busy || !active || stale;
    elements.prompt.rewrite.disabled = state.busy || !active || stale || !elements.prompt.instruction.value.trim();
    const lint = $("#i2v-prompt-lint");
    lint.replaceChildren();
    const result = window.document.createElement(errors.length ? "ul" : "small");
    if (draft) {
      result.textContent = "Brouillon local non enregistré : validation à recalculer.";
    } else if (!active) {
      result.textContent = "Le contrat I2VA sera contrôlé après génération.";
    } else if (!errors.length) {
      result.textContent = "Contrat I2VA valide : ancre Picture 1 et trois champs officiels.";
    } else {
      errors.forEach((error) => {
        const item = window.document.createElement("li");
        item.textContent = error;
        result.append(item);
      });
    }
    lint.append(result);
    $("#i2v-copy-prompt").disabled = state.busy || !complete || stale || draft || Boolean(errors.length);
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

  async function sessionAction(url, payload, targetStage, success) {
    setBusy(true);
    try {
      state.session = await core.request(url, {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      targetStage.message.className = "message";
      targetStage.message.textContent = success;
    } catch (error) {
      showStageError(targetStage, error);
    } finally {
      setBusy(false);
    }
  }

  async function streamSession(url, payload, targetStage, success) {
    await streamResult(url, payload, targetStage, (event) => {
      if (event.session) state.session = event.session;
    }, success);
  }

  async function streamPrompt(revision = false) {
    try {
      if (!state.composition) {
        setBusy(true);
        await configureI2V();
        setBusy(false);
      }
      const payload = revision
        ? { instruction: elements.prompt.instruction.value.trim() } : null;
      const completed = await streamResult(
        `/api/prompt-lab/sessions/${state.session.id}/final-prompt/${revision ? "revise" : "generate"}/stream`,
        payload,
        elements.prompt,
        (event) => { if (event.composition) state.composition = event.composition; },
        revision ? "Révision générée et enregistrée." : "Prompt I2VA généré et enregistré.",
      );
      if (revision && completed) elements.prompt.instruction.value = "";
    } catch (error) {
      showStageError(elements.prompt, error);
      setBusy(false);
    }
  }

  async function configureI2V() {
    const reference = state.session.references[0];
    const response = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: state.cookbook.id,
          cookbook_version: state.cookbook.version,
          bindings: { first_frame: [reference.id] },
        }),
      },
    );
    state.composition = response.composition;
  }

  async function streamResult(url, payload, targetStage, onEvent, success) {
    const previous = targetStage.content.value;
    let received = false;
    let completed = false;
    setBusy(true);
    targetStage.content.value = "";
    targetStage.message.className = "message";
    targetStage.message.textContent = "";
    core.updateStreamState(targetStage.stream, {
      phase: "preparing",
      text: "Préparation ou chargement du modèle…",
      progress: null,
    });
    try {
      await core.streamRequest(url, {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      }, (event) => {
        core.updateStreamState(targetStage.stream, event);
        if (event.kind === "delta" && event.text) {
          received = true;
          targetStage.content.value += event.text;
          targetStage.content.scrollTop = targetStage.content.scrollHeight;
        }
        if (event.kind === "completed") {
          onEvent(event);
          completed = true;
        }
        if (event.kind === "truncated") {
          received = true;
          targetStage.message.className = "message warning-text";
          targetStage.message.textContent = "Réponse tronquée : le brouillon partiel reste éditable mais n’est pas validé.";
        }
      });
      if (!completed) throw new Error("Le flux s’est terminé sans résultat persistant.");
      targetStage.message.textContent = success;
      return true;
    } catch (error) {
      if (!received) targetStage.content.value = previous;
      showStageError(targetStage, error, received);
      core.failStreamState(targetStage.stream, error.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  function showStageError(targetStage, error, preserved = false) {
    targetStage.message.className = "message error-text";
    targetStage.message.textContent = preserved
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
  elements.freedom.addEventListener("input", () => {
    updateFreedom();
    render();
  });
  elements.newSession.addEventListener("click", () => {
    state.session = null;
    state.composition = null;
    render();
  });

  elements.observation.content.addEventListener("input", render);
  elements.observation.instruction.addEventListener("input", render);
  elements.observation.generate.addEventListener("click", () => streamSession(
    `/api/prompt-lab/sessions/${state.session.id}/references/${state.session.references[0].id}/analyze/stream`,
    null,
    elements.observation,
    "Observation générée et enregistrée.",
  ));
  elements.observation.save.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/references/${state.session.references[0].id}/edit`,
    { content: elements.observation.content.value.trim() },
    elements.observation,
    "Observation corrigée.",
  ));
  elements.observation.approve.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/references/${state.session.references[0].id}/approve`,
    null,
    elements.observation,
    "Observation validée.",
  ));
  elements.observation.rewrite.addEventListener("click", () => streamSession(
    `/api/prompt-lab/sessions/${state.session.id}/references/${state.session.references[0].id}/revise/stream`,
    { instruction: elements.observation.instruction.value.trim() },
    elements.observation,
    "Révision de l’observation enregistrée.",
  ));

  elements.brief.content.addEventListener("input", render);
  elements.brief.instruction.addEventListener("input", render);
  elements.brief.generate.addEventListener("click", () => streamSession(
    `/api/prompt-lab/sessions/${state.session.id}/brief/structure/stream`,
    {
      source_text: elements.intention.value.trim(),
      creative_freedom: Number(elements.freedom.value),
    },
    elements.brief,
    "Brief généré et enregistré.",
  ));
  elements.brief.save.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/brief/edit`,
    { content: elements.brief.content.value.trim() },
    elements.brief,
    "Brief corrigé.",
  ));
  elements.brief.approve.addEventListener("click", () => sessionAction(
    `/api/prompt-lab/sessions/${state.session.id}/brief/approve`,
    null,
    elements.brief,
    "Brief validé.",
  ));
  elements.brief.rewrite.addEventListener("click", () => streamSession(
    `/api/prompt-lab/sessions/${state.session.id}/brief/revise/stream`,
    { instruction: elements.brief.instruction.value.trim() },
    elements.brief,
    "Révision du brief enregistrée.",
  ));

  elements.prompt.content.addEventListener("input", render);
  elements.prompt.instruction.addEventListener("input", render);
  elements.prompt.generate.addEventListener("click", () => streamPrompt(false));
  elements.prompt.save.addEventListener("click", () => promptAction(
    "edit",
    { content: elements.prompt.content.value.trim() },
  ));
  elements.prompt.approve.addEventListener("click", () => promptAction("approve"));
  elements.prompt.rewrite.addEventListener("click", () => streamPrompt(true));
  $("#i2v-copy-prompt").addEventListener("click", async () => {
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
