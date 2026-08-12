(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  if (!core) return;
  const $ = (selector) => document.querySelector(selector);
  const profileId = "minimax.h3.i2v.direct";
  const profileVersion = "0.1.0";
  const cookbookId = "minimax.h3.i2v.direct";
  const preferredCookbookVersion = "0.1.0";

  const state = {
    spec: null,
    cookbooks: [],
    cookbook: null,
    file: null,
    previewUrl: null,
    session: null,
    composition: null,
    busy: false,
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
    intention: $("#i2vd-intention"),
    freedom: $("#i2vd-freedom"),
    freedomValue: $("#i2vd-freedom-value"),
    freedomLabel: $("#i2vd-freedom-label"),
    start: $("#i2vd-start"),
    setupMessage: $("#i2vd-setup-message"),
    refreshSessions: $("#i2vd-refresh-sessions"),
    sessionList: $("#i2vd-session-list"),
    empty: $("#i2vd-empty"),
    editor: $("#i2vd-editor"),
    sessionTitle: $("#i2vd-session-title"),
    progress: $("#i2vd-session-progress"),
    newSession: $("#i2vd-new-session"),
    dock: $("#i2vd-reference-dock"),
    chips: {
      brief: $("#i2vd-chip-brief"),
      plan: $("#i2vd-chip-plan"),
      prompt: $("#i2vd-chip-prompt"),
    },
    brief: stage("brief"),
    plan: stage("plan"),
    prompt: stage("prompt"),
    copyPrompt: $("#i2vd-copy-prompt"),
    arbitrations: $("#i2vd-arbitrations"),
    arbitrationList: $("#i2vd-arbitration-list"),
    arbitrationInstruction: $("#i2vd-arbitration-instruction"),
    acceptAllArbitrations: $("#i2vd-accept-all-arbitrations"),
    applyArbitrations: $("#i2vd-apply-arbitrations"),
  };

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
      if (!selectedProfile()) throw new Error("Profil I2V Direct indisponible.");
      if (!state.cookbook) throw new Error("Cookbook I2V Direct indisponible.");
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
      (item) => item.id === cookbookId && item.target_mode === "i2v_direct",
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
      (item) => item.session_mode === "direct_multimodal"
        && item.profile && item.profile.id === profileId
        && item.profile.version === profileVersion,
    );
    elements.sessionList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun parcours I2V Direct enregistré.";
      elements.sessionList.append(empty);
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-link";
      const title = document.createElement("b");
      title.textContent = session.references[0] ? session.references[0].label : "Première frame";
      const detail = document.createElement("small");
      detail.textContent = session.brief_complete ? "Brief validé" : "Brief à préparer";
      button.append(title, detail);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  async function openSession(session) {
    state.session = session;
    state.composition = null;
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

  function selectFile() {
    const file = elements.imageInput.files && elements.imageInput.files[0];
    if (!file) return;
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.file = file;
    state.previewUrl = URL.createObjectURL(file);
    elements.uploadPreview.src = state.previewUrl;
    elements.uploadPreview.hidden = false;
    elements.uploadTitle.textContent = file.name;
    elements.uploadCaption.textContent = `${Math.ceil(file.size / 1024)} Kio · cliquer pour remplacer`;
    showSetupMessage("");
    render();
  }

  function setupValidationError() {
    if (!selectedProfile() || !state.cookbook) return "Le profil Direct est encore en cours de chargement.";
    if (!state.file) return "Ajoutez la première frame.";
    if (!elements.model.value) return "Choisissez un modèle multimodal.";
    if (!elements.intention.value.trim()) return "Décrivez votre intention.";
    return "";
  }

  async function createSession(event) {
    event.preventDefault();
    const error = setupValidationError();
    if (error) return showSetupMessage(error);
    const profile = selectedProfile();
    const body = new FormData();
    body.append("images", state.file, state.file.name);
    body.append("roles", "first_frame");
    body.append("usages", "first_frame");
    body.append("evidence_policies", "full");
    body.append("model_id", elements.model.value);
    body.append("profile_id", profile.id);
    body.append("profile_version", profile.version);
    setBusy(true);
    try {
      state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      state.composition = null;
      render();
      await loadSessions();
      elements.brief.message.textContent = "Parcours créé. Lancez le Brief quand vous êtes prêt.";
    } catch (creationError) {
      showSetupMessage(creationError.message);
    } finally {
      setBusy(false);
    }
  }

  function updateFreedom() {
    const value = Number(elements.freedom.value);
    elements.freedomValue.value = String(value);
    elements.freedomLabel.textContent = value <= 20
      ? "Très factuelle" : value <= 45 ? "Encadrée" : value <= 70 ? "Cinématographique" : "Très libre";
  }

  function render() {
    const session = state.session;
    const compositionReference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : null;
    const activeCookbook = activeCookbookSpec();
    if (compositionReference) elements.cookbook.value = compositionReference.version;
    elements.cookbook.disabled = state.busy || Boolean(compositionReference);
    elements.activeCookbook.textContent = activeCookbook
      ? compositionReference
        ? `${activeCookbook.display_name} · ${activeCookbook.id}@${activeCookbook.version} verrouillée`
        : `${activeCookbook.display_name} · verrouillée à la création du Plan`
      : "Cookbook indisponible";
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    elements.start.disabled = state.busy || Boolean(session) || Boolean(setupValidationError());
    elements.imageInput.disabled = state.busy || Boolean(session);
    elements.model.disabled = state.busy || Boolean(session);
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
    renderArbitrations(plan, planState, briefState.ready);
    const promptState = renderDocument(
      elements.prompt,
      prompt,
      planState.ready,
      planState.draft ? "Plan modifié" : "Plan requis",
    );
    elements.sessionTitle.textContent = session.references[0]
      ? session.references[0].label : "Première frame";
    elements.progress.textContent = !briefState.ready ? "Brief requis"
      : !planState.ready ? "Plan requis" : !promptState.ready ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptState.ready ? "success" : "active"}`;
    setChip(elements.chips.brief, briefState.ready, !briefState.ready);
    setChip(elements.chips.plan, planState.ready, briefState.ready && !planState.ready);
    setChip(elements.chips.prompt, promptState.ready, planState.ready && !promptState.ready);
    elements.copyPrompt.disabled = state.busy || !promptState.ready;
  }

  function renderDock() {
    elements.dock.replaceChildren();
    const reference = state.session.references[0];
    if (!reference) return;
    const card = document.createElement("figure");
    const image = document.createElement("img");
    image.src = reference.content_url;
    image.alt = reference.label;
    const caption = document.createElement("figcaption");
    caption.textContent = "<Image 1> → <Picture 1> · Première frame exacte";
    card.append(image, caption);
    elements.dock.append(card);
  }

  function renderBrief(brief, complete, inputsCurrent) {
    hydrate(elements.brief.content, `brief:${brief ? brief.id : "none"}`, brief && brief.content);
    const draft = Boolean(brief) && elements.brief.content.value.trim() !== brief.content.trim();
    const ready = complete && !draft;
    elements.brief.review.textContent = ready ? "Validé"
      : brief && !inputsCurrent ? "Intention modifiée" : brief ? "À valider" : "À générer";
    elements.brief.review.className = `review-pill ${ready ? "approved" : "pending"}`;
    elements.brief.generate.disabled = state.busy || !elements.intention.value.trim();
    elements.brief.content.disabled = state.busy;
    elements.brief.save.disabled = state.busy || !brief || !draft || !elements.brief.content.value.trim();
    elements.brief.approve.disabled = state.busy || !brief || complete || draft || !inputsCurrent;
    elements.brief.instruction.disabled = state.busy || !brief || !inputsCurrent || draft;
    elements.brief.rewrite.disabled = state.busy || !brief || !inputsCurrent || draft
      || !elements.brief.instruction.value.trim();
    return { draft, ready };
  }

  const arbitrationCategoryLabels = {
    temporal: "Rythme et durée",
    spatial: "Espace et trajectoire",
    identity: "Identité",
    object: "Objet et continuité",
    physical: "Plausibilité physique",
    reference: "Influence de la première frame",
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
      !state.busy && prerequisite && !planState.draft && !planState.stale
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
    view.generate.disabled = state.busy || !prerequisite;
    view.content.disabled = state.busy || !prerequisite || !state.composition;
    view.save.disabled = state.busy || !state.composition || !prerequisite || stale
      || !draft || !view.content.value.trim();
    view.approve.disabled = state.busy || !prerequisite || !active || complete || stale
      || draft || Boolean(diagnostics.length);
    if (view.instruction) {
      view.instruction.disabled = state.busy || !prerequisite || !active || stale || draft;
      view.rewrite.disabled = state.busy || !prerequisite || !active || stale || draft
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
      revision ? "Brief révisé à partir de la première frame." : "Brief multimodal généré.",
    );
    if (completed) {
      if (revision) elements.brief.instruction.value = "";
      await refreshComposition();
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
    if (!state.cookbook) throw new Error("Choisissez une recette I2V Direct.");
    const reference = state.session.references[0];
    if (!reference) throw new Error("La première frame de la session est introuvable.");
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
    } catch (error) {
      showStageError(view, error, false);
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
    } catch (error) {
      showStageError(elements.brief, error, false);
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
    } catch (error) {
      showStageError(view, error, false);
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
    state.session = null;
    state.composition = null;
    resetArbitrations();
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.file = null;
    state.previewUrl = null;
    elements.imageInput.value = "";
    elements.uploadPreview.removeAttribute("src");
    elements.uploadPreview.hidden = true;
    elements.uploadTitle.textContent = "Choisir une image";
    elements.uploadCaption.textContent = "PNG, JPEG ou WebP · 25 Mio maximum";
    elements.intention.value = "";
    elements.freedom.value = "35";
    updateFreedom();
    for (const view of [elements.brief, elements.plan, elements.prompt]) {
      view.message.textContent = "";
      if (view.instruction) view.instruction.value = "";
      view.content.dataset.hydrationKey = "";
    }
    render();
  }

  elements.imageInput.addEventListener("change", selectFile);
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
  elements.freedom.addEventListener("input", () => { updateFreedom(); render(); });
  elements.newSession.addEventListener("click", resetSession);

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
  render();
  initialize();
})();
