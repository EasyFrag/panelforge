(() => {
  "use strict";

  const core = window.PanelForgeLabCore;
  const quickPipeline = window.PanelForgeQuickPipeline;
  if (!core || !quickPipeline) return;
  const $ = (selector) => document.querySelector(selector);
  const profileId = "minimax.h3.ref2v.direct";
  const profileVersion = "0.4.0";
  const experimentalProfileVersion = "0.5.0";
  const cookbookId = "minimax.h3.ref2v.direct";
  const multishotCookbookId = "minimax.h3.ref2v.direct.multishot";
  const superFastCookbookId = "minimax.h3.ref2v.direct.multishot.superfast";
  const superFastCookbookVersion = "0.2.0";
  const preferredCookbookValue = "minimax.h3.ref2v.direct.guided@1.1.0";
  const creativeBriefVariant = { id: "creative-direction", version: "0.2.0" };
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
    forkSource: null,
    session: null,
    composition: null,
    busy: false,
    quickRunning: false,
    superFastRunning: false,
    compoundRunning: false,
    quickRecord: null,
    superFastRecord: null,
    openRequestId: 0,
    openingSessionId: null,
    rolesConfirmed: false,
    arbitrationDecisions: {},
    arbitrationRevisionId: null,
  };

  const elements = {
    form: $("#ref2vd-session-form"),
    model: $("#ref2vd-model"),
    refreshModels: $("#ref2vd-refresh-models"),
    cookbook: $("#ref2vd-cookbook"),
    preparationFamily: $("#ref2vd-preparation-family"),
    activeCookbook: $("#ref2vd-active-cookbook"),
    imageInput: $("#ref2vd-image-input"),
    referenceList: $("#ref2vd-reference-list"),
    roleHelpBody: $("#ref2vd-role-help-body"),
    roleSummary: $("#ref2vd-role-summary"),
    roleWarning: $("#ref2vd-role-warning"),
    roleConfirmation: $("#ref2vd-role-confirmation"),
    intention: $("#ref2vd-intention"),
    creativeSceneLife: $("#ref2vd-creative-scene-life"),
    creativeSceneLifeValue: $("#ref2vd-creative-scene-life-value"),
    creativeCamera: $("#ref2vd-creative-camera"),
    creativeCameraValue: $("#ref2vd-creative-camera-value"),
    creativeExtraMotion: $("#ref2vd-creative-extra-motion"),
    creativeExtraMotionValue: $("#ref2vd-creative-extra-motion-value"),
    creativeDialogue: $("#ref2vd-creative-dialogue"),
    creativeDialogueValue: $("#ref2vd-creative-dialogue-value"),
    creativeAudacityControl: $("#ref2vd-creative-audacity-control"),
    creativeAudacity: $("#ref2vd-creative-audacity"),
    creativeAudacityValue: $("#ref2vd-creative-audacity-value"),
    creativeDirectionOption: $("#ref2vd-creative-direction-option"),
    creativeDirection: $("#ref2vd-creative-direction"),
    start: $("#ref2vd-start"),
    setupMessage: $("#ref2vd-setup-message"),
    executionModeControl: $("#ref2vd-execution-mode-control"),
    executionMode: $("#ref2vd-execution-mode"),
    executionModeHint: $("#ref2vd-execution-mode-hint"),
    quickStatus: $("#ref2vd-quick-status"),
    quickStatusLabel: $("#ref2vd-quick-status-label"),
    quickResume: $("#ref2vd-quick-resume"),
    showReasoning: $("#ref2vd-show-reasoning"),
    reasoningPanel: $("#ref2vd-reasoning-panel"),
    reasoningLabel: $("#ref2vd-reasoning-label"),
    reasoningOutput: $("#ref2vd-reasoning-output"),
    reasoningEmpty: $("#ref2vd-reasoning-empty"),
    modeWarning: $("#ref2vd-mode-warning"),
    refreshSessions: $("#ref2vd-refresh-sessions"),
    sessionList: $("#ref2vd-session-list"),
    empty: $("#ref2vd-empty"),
    editor: $("#ref2vd-editor"),
    sessionTitle: $("#ref2vd-session-title"),
    sessionConfig: $("#ref2vd-session-config"),
    progress: $("#ref2vd-session-progress"),
    newSession: $("#ref2vd-new-session"),
    forkSession: $("#ref2vd-fork-session"),
    dock: $("#ref2vd-reference-dock"),
    steps: {
      brief: $("#ref2vd-brief-step"),
      plan: $("#ref2vd-plan-step"),
      prompt: $("#ref2vd-prompt-step"),
    },
    chips: {
      brief: $("#ref2vd-chip-brief"),
      plan: $("#ref2vd-chip-plan"),
      prompt: $("#ref2vd-chip-prompt"),
    },
    brief: stage("brief"),
    plan: stage("plan"),
    prompt: stage("prompt"),
    copyPrompt: $("#ref2vd-copy-prompt"),
    sendVideoLab: $("#ref2vd-send-video-lab"),
    promptReferences: $("#ref2vd-prompt-references"),
    arbitrations: $("#ref2vd-arbitrations"),
    arbitrationList: $("#ref2vd-arbitration-list"),
    arbitrationInstruction: $("#ref2vd-arbitration-instruction"),
    acceptAllArbitrations: $("#ref2vd-accept-all-arbitrations"),
    applyArbitrations: $("#ref2vd-apply-arbitrations"),
    applyApproveArbitrations: $("#ref2vd-apply-approve-arbitrations"),
    multishotSummary: $("#ref2vd-multishot-summary"),
    multishotSummaryBadge: $("#ref2vd-multishot-summary-badge"),
    multishotSummaryList: $("#ref2vd-multishot-summary-list"),
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
      review: $(`#ref2vd-${name}-review`),
      generate: $(`#ref2vd-generate-${name}`),
      save: $(`#ref2vd-save-${name}`),
      approve: $(`#ref2vd-approve-${name}`),
      content: $(`#ref2vd-${name}-content`),
      message: $(`#ref2vd-${name}-message`),
      instruction: $(`#ref2vd-${name}-instruction`),
      rewrite: $(`#ref2vd-rewrite-${name}`),
      rewriteApprove: $(`#ref2vd-rewrite-approve-${name}`),
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

  function profileReference(cookbook = state.cookbook) {
    if (cookbook?.profile) return cookbook.profile;
    return { id: profileId, version: cookbook?.id === cookbookId && cookbook.version === experimentalProfileVersion
      ? experimentalProfileVersion : profileVersion };
  }

  function selectedProfile() {
    const reference = state.session?.profile || profileReference();
    return state.spec && (state.spec.profiles || []).find(
      (item) => item.id === reference.id && item.version === reference.version,
    );
  }

  function directCookbooks() {
    const available = state.cookbooks.filter(
      (item) => (item.profile || [cookbookId, multishotCookbookId, superFastCookbookId].includes(item.id))
        && item.target_mode === "ref2v_direct",
    );
    if (!available.some(isDirectSuperFastReference)) {
      available.push(superFastCookbookSpec());
    }
    return available;
  }

  function cookbookValue(cookbook) {
    return `${cookbook.id}@${cookbook.version}`;
  }

  function isMultishotCookbook(cookbook) {
    return Boolean(cookbook && [multishotCookbookId, superFastCookbookId].includes(cookbook.id));
  }

  function preparationSteps() {
    return (activeCookbookSpec() || state.cookbook)?.preparation_steps ?? 3;
  }

  function preparationInput() {
    return state.composition?.preparation_intent || state.session?.active_brief || null;
  }

  function renderPreparationCopy(cookbook) {
    const copy = elements.emptyCopy || elements.empty;
    const nodes = [copy.querySelector("b"), copy.querySelector("p"),
      elements.steps.plan.querySelector(".cookbook-step-copy small"),
      elements.steps.prompt.querySelector(".cookbook-step-copy small")];
    nodes.forEach((node) => { if (!("preparationDefault" in node.dataset)) node.dataset.preparationDefault = node.textContent; });
    if (!cookbook?.profile) {
      nodes[2].textContent = nodes[2].dataset.preparationDefault;
      return;
    }
    copy.querySelector("b").textContent = cookbook.display_name;
    copy.querySelector("p").textContent = cookbook.description;
    elements.steps.plan.querySelector(".cookbook-step-copy small").textContent = preparationSteps() === 2
      ? "Interpréter l’intention et organiser les actions, contacts et risques."
      : "Vérifier les actions, contacts, durée et risques du Brief.";
    elements.steps.prompt.querySelector(".cookbook-step-copy small").textContent = preparationSteps() === 1
      ? "Préparer le prompt depuis l’intention et les images. Un mouvement caméra principal ; 8 s si aucune durée n’est demandée."
      : "Rédiger depuis le Plan validé, puis compiler le prompt H3.";
  }

  function creativeBriefAvailable(cookbook = state.cookbook) {
    const profile = selectedProfile();
    return Boolean(
      cookbook && (cookbook.id === cookbookId || (cookbook.profile && cookbook.preparation_steps === 3))
      && profile && (profile.brief_variants || []).some(
        (value) => value.id === creativeBriefVariant.id
          && value.version === creativeBriefVariant.version,
      ),
    );
  }

  const combatControls = window.PanelForgeCombatControls.create({ prefix: "ref2vd", state, elements, recipes: directCookbooks, render, busy: interactionLocked, steps: preparationSteps });
  const cinematicControls = window.PanelForgeClassicCinematicControls.create({ prefix: "ref2vd", state, elements, recipes: directCookbooks, render, busy: interactionLocked, steps: preparationSteps });

  function preparationFamily(value = state.session || activeCookbookSpec() || state.cookbook) {
    return value?.preparation?.family || "classic";
  }

  function changePreparationFamily() {
    if (state.session || interactionLocked()) return render();
    const family = elements.preparationFamily.value;
    if (family === "combat") return combatControls.choose("combat", "1.3.0");
    const choices = directCookbooks().filter((item) => preparationFamily(item) === family
      && !item.preparation?.version
      && core.recipeTier(cookbookValue(item)) === "standard");
    const next = choices.find((item) => item.preparation_steps === preparationSteps()) || choices[0];
    if (!next) return render();
    state.cookbook = next;
    elements.creativeDirection.checked = false;
    render();
  }

  function creativeBriefPayload() {
    return creativeBriefAvailable() && elements.creativeDirection.checked
      ? {
        brief_variant_id: creativeBriefVariant.id,
        brief_variant_version: creativeBriefVariant.version,
      }
      : { brief_variant_id: null, brief_variant_version: null };
  }

  function isSuperFastReference(reference) {
    return Boolean(reference && reference.id === superFastCookbookId);
  }

  function isDirectSuperFastReference(reference) {
    return Boolean(isSuperFastReference(reference)
      && reference.version === superFastCookbookVersion);
  }

  function superFastCookbookSpec(reference = null) {
    return {
      id: superFastCookbookId,
      version: reference && reference.version ? reference.version : superFastCookbookVersion,
      display_name: "Ref2V multi-plan direct",
      target_mode: "ref2v_direct",
      supports_plan_reconciliation: false,
    };
  }

  function cookbookLabel(cookbook) {
    if (cookbook.profile) return `${cookbook.display_name} (${cookbook.version})`;
    if (cookbook.id === cookbookId && cookbook.version === experimentalProfileVersion) return `Mono-plan · compact · expérimental (${cookbook.version})`;
    if (isDirectSuperFastReference(cookbook)) {
      return `Multi-plan direct · 1 appel · expérimental (${cookbook.version})`;
    }
    if (cookbook.id === multishotCookbookId && cookbook.version === "0.2.0") {
      return `Multi-plan structuré · 2–6 plans (${cookbook.version})`;
    }
    if (cookbook.id === cookbookId && cookbook.version === profileVersion) {
      return `Mono-plan · standard (${cookbook.version})`;
    }
    if (isMultishotCookbook(cookbook)) {
      const qualifier = cookbook.version === "0.2.0"
        ? "2–6 plans automatiques · caméra compilée · expérimental"
        : "3 plans · placeholders · témoin";
      return `${cookbook.id}@${cookbook.version} — ${qualifier}`;
    }
    const qualifier = cookbook.version === "0.3.2" ? "Mono-plan · placeholders · témoin"
        : cookbook.version === "0.3.1" ? "Compacte · témoin"
        : cookbook.version === "0.3.0" ? "Verrouillée · témoin"
        : cookbook.version === "0.2.0" ? "Témoin V2" : "Historique";
    return `${cookbook.id}@${cookbook.version} — ${qualifier}`;
  }

  function orderedDirectCookbooks() {
    const order = new Map([
      [cookbookId, 0],
      [multishotCookbookId, 1],
      [superFastCookbookId, 2],
    ]);
    return [...directCookbooks()].sort((left, right) => {
      if (left.id !== right.id) return (left.profile ? -left.preparation_steps : order.get(left.id) ?? 9) - (right.profile ? -right.preparation_steps : order.get(right.id) ?? 9);
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
      option.dataset.preparationFamily = preparationFamily(cookbook);
        option.dataset.preparationVersion = cookbook.preparation?.version || "";
        option.dataset.classicVersion = cookbook.preparation?.family === "combat" ? "" : cookbook.preparation?.version || "legacy";
      option.textContent = cookbookLabel(cookbook);
      elements.cookbook.append(option);
    });
    resetCookbookSelection();
    core.refreshRecipeVisibility(elements.cookbook);
  }

  function showCookbookSelection(reference) {
    if (!reference) return;
    const value = cookbookValue(reference);
    const previousHistorical = elements.cookbook.querySelector("option[data-historical-cookbook]");
    if (previousHistorical && previousHistorical.value !== value) previousHistorical.remove();
    let option = [...elements.cookbook.options].find((item) => item.value === value);
    if (!option) {
      option = document.createElement("option");
      option.value = value;
      option.dataset.historicalCookbook = "true";
      option.textContent = `${reference.id}@${reference.version} — recette historique verrouillée`;
      elements.cookbook.append(option);
    }
    elements.cookbook.value = value;
    core.refreshRecipeVisibility(elements.cookbook);
  }

  function activeCookbookSpec() {
    const reference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    if (!reference) return null;
    if (isSuperFastReference(reference)) return superFastCookbookSpec(reference);
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
        && item.profile && ((item.profile.id === profileId
          && [profileVersion, experimentalProfileVersion, "0.6.0"].includes(item.profile.version))
          || ["minimax.h3.ref2v.combat", "minimax.h3.ref2v.classic.cinematic"].includes(item.profile.id)),
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
      title.textContent = (preparationFamily(session) === "combat" ? "Combat \u00b7 " : window.PanelForgeClassicCinematicControls.isCinematic(session) ? "Mise en scène \u00b7 " : "") + session.references.map((item) => item.label).join(" + ");
      const detail = document.createElement("small");
      detail.textContent = `${session.references.length} image${session.references.length > 1 ? "s" : ""} · ${session.brief_complete ? "Brief validé" : "Préparation vidéo"}`;
      button.append(title, detail);
      core.decorateSessionLink(button, session.references);
      button.addEventListener("click", () => openSession(session));
      elements.sessionList.append(button);
    });
  }

  function selectModel(modelId) {
    if (!modelId) return;
    window.PanelForgeModelPicker.select(elements.model, modelId, "modèle du parcours");
  }

  async function openSession(sessionSummary) {
    if (state.quickRunning || state.superFastRunning) return;
    const sessionId = sessionSummary.id;
    const requestId = ++state.openRequestId;
    let openedSuperFast = false;
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
      openedSuperFast = Boolean(
        state.composition && isSuperFastReference(state.composition.cookbook),
      );
      const openedCookbook = state.composition && state.composition.cookbook;
      const matchingCookbook = openedCookbook && directCookbooks().find(
        (item) => item.id === openedCookbook.id && item.version === openedCookbook.version,
      );
      if (openedSuperFast) state.cookbook = superFastCookbookSpec();
      else if (matchingCookbook) state.cookbook = matchingCookbook;
      else state.cookbook = directCookbooks().find((item) => item.profile?.id === session.profile?.id
        && item.profile.version === session.profile?.version && item.preparation_steps === 3)
        || directCookbooks().find((item) => item.id === cookbookId && item.version === session.profile?.version)
        || null;
      state.superFastRecord = null;
      elements.executionMode.value = "supervised";
      releaseDraftPreviews();
      state.drafts = session.references.map((reference) => ({
        sourceReferenceId: reference.id,
        label: reference.label,
        previewUrl: reference.content_url,
        role: reference.role,
      }));
      state.rolesConfirmed = true;
      renderDraftReferences();
      selectModel(session.model_id);
      const input = preparationInput();
      if (input) {
        elements.intention.value = input.source_text || "";
        setCreativeAxes(
          input.creative_axes,
          input.creative_freedom ?? 35,
        );
        setCreativeAudacity(input.creative_audacity ?? 0);
      } else {
        elements.intention.value = "";
        setCreativeAxes(null, 0);
        setCreativeAudacity(2);
      }
      elements.creativeDirection.checked = Boolean(
        session.brief_variant
        && session.brief_variant.id === creativeBriefVariant.id,
      );
      if (openedSuperFast) {
        const completed = superFastRunApproved();
        state.superFastRecord = {
          status: completed ? "completed" : "stopped",
          error: completed ? "" : "Parcours interrompu avant la validation du Prompt.",
        };
      }
    } catch (error) {
      if (requestId === state.openRequestId) showSetupMessage(error.message);
    } finally {
      if (requestId === state.openRequestId) {
        state.openingSessionId = null;
        render();
        if (openedSuperFast) revealSuperFastPrompt();
      }
    }
  }

  function prepareFork() {
    if (!state.session || state.openingSessionId || interactionLocked()) return;
    const source = state.session;
    const input = preparationInput();
    const sourceCookbook = state.composition && state.composition.cookbook;
    const matchingCookbook = sourceCookbook && directCookbooks().find(
      (item) => item.id === sourceCookbook.id && item.version === sourceCookbook.version,
    );
    if (isSuperFastReference(sourceCookbook)) state.cookbook = superFastCookbookSpec();
    else if (matchingCookbook) state.cookbook = matchingCookbook;
    releaseDraftPreviews();
    state.drafts = source.references.map((reference) => ({
      sourceReferenceId: reference.id,
      label: reference.label,
      previewUrl: reference.content_url,
      role: reference.role,
    }));
    state.forkSource = source;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    state.superFastRecord = null;
    state.rolesConfirmed = true;
    resetArbitrations();
    selectModel(source.model_id);
    const brief = input;
    elements.intention.value = brief ? brief.source_text || "" : "";
    setCreativeAxes(brief && brief.creative_axes, brief ? brief.creative_freedom ?? 35 : 0);
    setCreativeAudacity(brief ? brief.creative_audacity ?? 0 : 2);
    elements.creativeDirection.checked = Boolean(
      source.brief_variant
      && source.brief_variant.id === creativeBriefVariant.id,
    );
    elements.executionMode.value = "supervised";
    clearStageDrafts();
    showSetupMessage("");
    renderDraftReferences();
    render();
    elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function addFiles(fileList) {
    const available = Math.max(0, 9 - state.drafts.length);
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
      showSetupMessage("Ref2V Direct accepte neuf images au maximum.");
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
      heading.textContent = `<Picture ${index + 1}> · ${draft.file ? draft.file.name : draft.label}`;
      const select = document.createElement("select");
      select.setAttribute("aria-label", `Rôle de Picture ${index + 1}`);
      roleOptions.forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      });
      select.value = draft.role;
      const reusedReference = Boolean(draft.sourceReferenceId);
      select.disabled = Boolean(state.session) || reusedReference;
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
      up.disabled = Boolean(state.session) || reusedReference || index === 0;
      down.disabled = Boolean(state.session) || reusedReference || index === state.drafts.length - 1;
      remove.disabled = Boolean(state.session) || reusedReference;
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
    elements.roleConfirmation.disabled = interactionLocked() || Boolean(state.session)
      || Boolean(state.forkSource) || !state.drafts.length;
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
    if (!state.session && isDirectSuperFastReference(state.cookbook)) {
      elements.modeWarning.textContent = "Cette recette multi-plan directe rédige et valide le Prompt MiniMax en un seul appel LLM, sans Plan intermédiaire affiché.";
      elements.modeWarning.hidden = false;
      return;
    }
    const recipeMismatch = !state.session && !combatControls.current() && !cinematicControls.current()
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
    if (state.drafts.length > 9) return "Neuf images au maximum.";
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
    const forkSource = state.forkSource;
    const requestedMode = elements.executionMode.value;
    const requestedDirectRecipe = isDirectSuperFastReference(state.cookbook);
    let created = false;
    setBusy(true);
    try {
      if (state.session) {
        if (!state.cookbook?.profile || state.composition) throw new Error("Ce run est d\u00e9j\u00e0 configur\u00e9.");
        // Retry only recipe persistence after a failed configuration request.
      } else if (forkSource) {
        state.session = await core.request(
          `/api/prompt-lab/sessions/${forkSource.id}/fork`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              model_id: elements.model.value,
              profile_id: selectedProfile().id,
              profile_version: selectedProfile().version,
              ...creativeBriefPayload(),
              combat_settings: combatControls.payload(),
              cinematic_settings: cinematicControls.payload(),
              inherit_brief_variant: false,
            }),
          },
        );
      } else {
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
        if (combatControls.payload()) body.append("combat_settings", JSON.stringify(combatControls.payload()));
        if (cinematicControls.payload()) body.append("cinematic_settings", JSON.stringify(cinematicControls.payload()));
        if (elements.creativeDirection.checked) {
          body.append("brief_variant_id", creativeBriefVariant.id);
          body.append("brief_variant_version", creativeBriefVariant.version);
        }
        state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      }
      state.forkSource = null;
      state.composition = null;
      state.quickRecord = null;
      state.superFastRecord = null;
      if (state.cookbook?.profile) await ensureComposition();
      created = true;
      renderDraftReferences();
      render();
      await loadSessions();
      elements[preparationSteps() === 1 ? "prompt" : preparationSteps() === 2 ? "plan" : "brief"].message.textContent = "Parcours créé. Lancez la première étape quand vous êtes prêt.";
    } catch (creationError) {
      showSetupMessage(creationError.message);
    } finally {
      setBusy(false);
    }
    if (created && requestedDirectRecipe) await runSuperFastMode();
    else if (created && requestedMode === "quick") await runQuickMode();
  }

  function legacyCreativeLevel(value) {
    const normalized = Number(value);
    if (!Number.isFinite(normalized)) return 1;
    return normalized <= 20 ? 0 : normalized <= 45 ? 1 : normalized <= 70 ? 2 : 3;
  }

  function currentCreativeAxes() {
    return {
      scene_life: Number(elements.creativeSceneLife.value),
      camera: Number(elements.creativeCamera.value),
      extra_motion: Number(elements.creativeExtraMotion.value),
      dialogue: state.cookbook?.vocal_policy_version ? Number(elements.creativeDialogue.value) : 0,
    };
  }

  function creativeAggregate(axes = currentCreativeAxes()) {
    const anchors = [0, 35, 65, 90];
    return Math.round((anchors[axes.scene_life] + anchors[axes.camera] + anchors[axes.extra_motion]) / 3);
  }

  function setCreativeAxes(axes, legacyFreedom = 35) {
    const fallback = legacyCreativeLevel(legacyFreedom);
    const resolved = axes || { scene_life: fallback, camera: fallback, extra_motion: fallback };
    elements.creativeSceneLife.value = String(resolved.scene_life ?? fallback);
    elements.creativeCamera.value = String(resolved.camera ?? fallback);
    elements.creativeExtraMotion.value = String(resolved.extra_motion ?? fallback);
    elements.creativeDialogue.value = String(resolved.dialogue ?? 0);
    updateCreativeAxes();
  }

  function updateCreativeAxes() {
    elements.creativeSceneLifeValue.value = elements.creativeSceneLife.value;
    elements.creativeCameraValue.value = elements.creativeCamera.value;
    elements.creativeExtraMotionValue.value = elements.creativeExtraMotion.value;
    elements.creativeDialogueValue.value = elements.creativeDialogue.value;
    elements.creativeDialogue.closest("label").hidden = !state.cookbook?.vocal_policy_version;
  }

  function setCreativeAudacity(value = 2) {
    const resolved = Number(value);
    elements.creativeAudacity.value = String(
      Number.isInteger(resolved) ? Math.max(0, Math.min(3, resolved)) : 2,
    );
    elements.creativeAudacityValue.value = elements.creativeAudacity.value;
  }

  function creativeAxesMatch(brief) {
    if (!brief) return false;
    const expected = brief.creative_axes || (() => {
      const level = legacyCreativeLevel(brief.creative_freedom ?? 35);
      return { scene_life: level, camera: level, extra_motion: level };
    })();
    const current = currentCreativeAxes();
    return expected.scene_life === current.scene_life
      && expected.camera === current.camera
      && expected.extra_motion === current.extra_motion
      && Number(expected.dialogue ?? 0) === current.dialogue;
  }

  function creativeAudacityMatch(brief) {
    if (!brief) return false;
    return Number(brief.creative_audacity ?? 0) === Number(
      (preparationFamily() === "combat" || preparationSteps() < 3 || elements.creativeDirection.checked) ? elements.creativeAudacity.value : 0,
    );
  }

  function creativePayload() {
    const creative_axes = currentCreativeAxes();
    return {
      creative_freedom: creativeAggregate(creative_axes),
      creative_axes,
      creative_audacity: (preparationFamily() === "combat" || preparationSteps() < 3 || elements.creativeDirection.checked)
        ? Number(elements.creativeAudacity.value)
        : 0,
    };
  }

  function interactionLocked() {
    return state.busy || state.quickRunning || state.superFastRunning || state.compoundRunning
      || Boolean(state.openingSessionId);
  }

  function currentBriefInputs() {
    const brief = preparationInput();
    return Boolean(brief
      && (brief.source_text || "").trim() === elements.intention.value.trim()
      && creativeAxesMatch(brief)
      && creativeAudacityMatch(brief));
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
    const inputReady = preparationSteps() < 3 ? currentBriefInputs() : briefApproved;
    const planGenerated = Boolean(inputReady && generatedDocument(plan));
    const planApproved = Boolean(planGenerated && plan.complete);
    const promptGenerated = Boolean((preparationSteps() === 1 ? inputReady : planApproved) && generatedDocument(prompt));
    return {
      briefGenerated,
      briefApproved,
      planGenerated,
      planApproved,
      promptGenerated,
      promptApproved: Boolean(promptGenerated && prompt.complete),
    };
  }

  function directSuperFastModeActive() {
    const reference = state.composition && state.composition.cookbook;
    return reference ? isDirectSuperFastReference(reference)
      : isDirectSuperFastReference(state.cookbook);
  }

  function superFastPromptApproved() {
    const documents = state.composition ? state.composition.documents || {} : {};
    const prompt = documents.final_prompt || null;
    return Boolean(generatedDocument(prompt) && prompt.complete);
  }

  function superFastRunApproved() {
    return directSuperFastModeActive()
      ? superFastPromptApproved() : quickSnapshot().promptApproved;
  }

  function renderWorkflowShape(superFast) {
    const planWasHidden = elements.steps.plan.hidden;
    elements.steps.plan.hidden = superFast;
    elements.chips.plan.hidden = superFast;
    if (elements.chips.plan.previousElementSibling) {
      elements.chips.plan.previousElementSibling.hidden = false;
    }
    if (elements.chips.plan.nextElementSibling) {
      elements.chips.plan.nextElementSibling.hidden = superFast;
    }
    if (superFast) elements.steps.plan.open = false;
    else if (planWasHidden) elements.steps.plan.open = true;

    const promptNumber = superFast ? "2" : "3";
    elements.chips.prompt.querySelector("b").textContent = promptNumber;
    elements.steps.prompt.querySelector(".cookbook-step-index").textContent = promptNumber;
    elements.steps.prompt.querySelector(".cookbook-step-copy small").textContent = superFast
      ? "Rédiger directement le prompt H3 depuis les références et l’intention."
      : "Compiler références, plan et caméra canonique.";
    elements.empty.querySelector("b").textContent = superFast
      ? "Deux étapes, génération directe du prompt"
      : "Trois étapes, aucune observation séparée";
    elements.empty.querySelector("p").textContent = superFast
      ? "Ajoutez les références, attribuez leur rôle, puis décrivez simplement la vidéo. La recette multi-plan directe rédige le Prompt MiniMax sans afficher de Plan intermédiaire."
      : "Ajoutez les références, attribuez leur rôle, puis décrivez simplement la vidéo. Les mêmes pixels restent disponibles pendant vos révisions du Brief et la création du Plan.";
  }

  function revealSuperFastPrompt() {
    elements.steps.prompt.open = true;
    window.requestAnimationFrame(() => {
      elements.steps.prompt.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function renderQuickStatus() {
    const recipeOwnsExecution = isSuperFastReference(
      state.composition && state.composition.cookbook
        ? state.composition.cookbook : state.cookbook,
    );
    elements.executionModeControl.hidden = recipeOwnsExecution;
    elements.executionMode.disabled = interactionLocked() || Boolean(state.session)
      || recipeOwnsExecution;
    const modeDescriptions = {
      supervised: "Étapes manuelles et arbitrages humains.",
      quick: "3 appels LLM · génération et validation automatiques.",
    };
    elements.executionModeHint.textContent = modeDescriptions[elements.executionMode.value]
      || modeDescriptions.supervised;
    if (state.superFastRecord) {
      const record = state.superFastRecord;
      const completedBecameIncomplete = record.status === "completed"
        && state.session && !superFastRunApproved();
      const visibleStatus = completedBecameIncomplete ? "interrupted" : record.status;
      elements.quickStatus.hidden = false;
      elements.quickStatus.className = `quick-mode-status ${visibleStatus}`;
      elements.quickResume.hidden = !["stopped", "interrupted"].includes(visibleStatus);
      elements.quickResume.textContent = completedBecameIncomplete ? "Régénérer" : "Réessayer";
      elements.quickResume.disabled = interactionLocked();
      elements.quickStatusLabel.textContent = completedBecameIncomplete
        ? "Recette directe modifiée · validation manuelle ou régénération disponible."
        : record.status === "running"
        ? "Recette directe · analyse des références et rédaction du Prompt MiniMax…"
        : record.status === "completed"
          ? "Recette directe terminée · Prompt validé."
          : `Recette directe arrêtée${record.error ? ` · ${record.error}` : ""}`;
      return;
    }
    const record = state.quickRecord;
    elements.quickStatus.hidden = !record;
    if (!record) return;
    const completedBecameIncomplete = record.status === "completed"
      && state.session && !quickSnapshot().promptApproved;
    const visibleStatus = completedBecameIncomplete ? "interrupted" : record.status;
    elements.quickStatus.className = `quick-mode-status ${visibleStatus === "retrying" ? "running" : visibleStatus}`;
    elements.quickResume.hidden = !["stopped", "interrupted"].includes(visibleStatus);
    elements.quickResume.textContent = "Reprendre";
    elements.quickResume.disabled = interactionLocked();
    if (completedBecameIncomplete) {
      elements.quickStatusLabel.textContent = "Parcours modifié après le mode rapide · reprise disponible.";
    } else if (record.status === "running") {
      const attempt = record.attempt ? ` · tentative ${record.attempt}/${record.maxAttempts}` : "";
      elements.quickStatusLabel.textContent = `Mode rapide · ${record.stepLabel}${attempt}…`;
    } else if (record.status === "retrying") {
      elements.quickStatusLabel.textContent = `Mode rapide · ${record.stepLabel} · tentative ${record.attempt}/${record.maxAttempts} échouée, nouvelle tentative…`;
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
        stages: core.preparationStages(activeCookbookSpec() || state.cookbook),
        isCurrent: () => Boolean(state.session && state.session.id === sessionId),
        actions: {
          generateBrief: () => streamBrief(false),
          approveBrief: () => briefAction("approve"),
          generatePlan: () => streamCompositionStage("beat-sheet"),
          approvePlan: () => documentAction("beat-sheet", "approve"),
          generatePrompt: () => streamCompositionStage("final-prompt"),
          approvePrompt: () => documentAction("final-prompt", "approve"),
        },
        onAttemptOutcome: (_step, succeeded) => {
          if (succeeded) core.playCompletionTone();
          else core.playFailureTone();
        },
        onState: (record) => { state.quickRecord = record; render(); },
      });
    } finally {
      state.quickRunning = false;
      render();
    }
  }

  async function runSuperFastMode() {
    if (!state.session || state.superFastRunning) return false;
    const sessionId = state.session.id;
    const directToPrompt = directSuperFastModeActive();
    const streamView = directToPrompt ? elements.prompt : elements.plan;
    state.superFastRunning = true;
    state.superFastRecord = { status: "running", error: "" };
    state.quickRecord = null;
    const outcomeTone = core.createLlmOutcomeTone();
    render();
    if (directToPrompt) revealSuperFastPrompt();
    try {
      outcomeTone.start();
      const completed = await streamResult(
        `/api/prompt-lab/sessions/${sessionId}/super-fast/stream`,
        {
          source_text: elements.intention.value.trim(),
          ...creativePayload(),
        },
        streamView,
        (event) => { if (event.composition) state.composition = event.composition; },
        directToPrompt ? "Prompt H3 rédigé et validé directement."
          : "Plan automatique compilé en prompt H3.",
        { notifyOutcome: false },
      );
      if (!completed) {
        outcomeTone.failure();
        state.superFastRecord = {
          status: "stopped",
          error: streamView.message.textContent
            || "La génération par la recette directe ne s’est pas terminée.",
        };
        return false;
      }
      if (!state.session || state.session.id !== sessionId) {
        throw new Error("La génération par la recette directe ne s’est pas terminée.");
      }
      state.session = await core.request(`/api/prompt-lab/sessions/${sessionId}`);
      await refreshComposition();
      if (!superFastRunApproved()) {
        throw new Error("Le prompt final n’a pas pu être validé automatiquement.");
      }
      state.superFastRecord = { status: "completed", error: "" };
      elements.prompt.message.className = "message";
      elements.prompt.message.textContent = "Prompt H3 compilé et validé en un appel LLM.";
      if (directToPrompt) revealSuperFastPrompt();
      outcomeTone.success();
      return true;
    } catch (error) {
      outcomeTone.failure();
      state.superFastRecord = { status: "stopped", error: error.message };
      showStageError(streamView, error, Boolean(streamView.content.value.trim()));
      if (directToPrompt) revealSuperFastPrompt();
      return false;
    } finally {
      state.superFastRunning = false;
      render();
    }
  }

  function resumeAutomaticMode() {
    if (state.superFastRecord) {
      runSuperFastMode();
      return;
    }
    runQuickMode();
  }

  function generateSuperFastOrStage(stage) {
    const reference = state.composition && state.composition.cookbook;
    if ((reference && isSuperFastReference(reference))
      || (!reference && isDirectSuperFastReference(state.cookbook))) {
      runSuperFastMode();
      return;
    }
    streamCompositionStage(stage);
  }

  function render() {
    const session = state.session;
    const compositionReference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : null;
    const selectedCookbook = compositionReference || state.cookbook;
    const activeCookbook = activeCookbookSpec();
    const combat = preparationFamily() === "combat";
    elements.preparationFamily.value = preparationFamily();
    elements.preparationFamily.disabled = interactionLocked() || Boolean(session);
    elements.cookbook.dataset.preparationFamily = preparationFamily();
    core.refreshRecipeVisibility(elements.cookbook);
    const audacityHint = elements.creativeAudacityControl?.querySelector("small");
    if (audacityHint) {
      if (!audacityHint.dataset.classicText) audacityHint.dataset.classicText = audacityHint.textContent;
      audacityHint.textContent = combat ? "Initiative et richesse de la chor\u00e9graphie" : audacityHint.dataset.classicText;
    }
    combatControls.draw(activeCookbook || state.cookbook);
    cinematicControls.draw(activeCookbook || state.cookbook);
    core.refreshRecipeVisibility(elements.cookbook);
    const locked = interactionLocked();
    const directSuperFast = directSuperFastModeActive();
    const creativeBriefVisible = creativeBriefAvailable(activeCookbook || state.cookbook);
    if (!creativeBriefVisible && !session) elements.creativeDirection.checked = false;
    elements.creativeDirectionOption.hidden = !creativeBriefVisible;
    const shortRoute = preparationSteps() < 3;
    const intentLocked = Boolean(shortRoute && state.composition?.preparation_intent);
    elements.creativeAudacityControl.hidden = !combat && !creativeBriefVisible && !shortRoute;
    elements.creativeDirection.disabled = locked || !creativeBriefVisible
      || Boolean(session && session.active_brief);
    elements.creativeAudacity.disabled = locked || intentLocked || (combat ? Boolean(session && session.active_brief)
      : (!shortRoute && (!creativeBriefVisible || !elements.creativeDirection.checked || Boolean(session && session.active_brief))));
    renderWorkflowShape(directSuperFast);
    core.renderPreparationStages(elements, directSuperFast ? ["brief", "prompt"] : core.preparationStages(activeCookbook));
    renderPreparationCopy(activeCookbook);
    renderQuickStatus();
    renderRoleReview();
    renderSetupWarnings();
    if (selectedCookbook) showCookbookSelection(selectedCookbook);
    elements.cookbook.disabled = locked || Boolean(session);
    elements.activeCookbook.textContent = activeCookbook
      ? compositionReference
        ? `${activeCookbook.display_name} · ${activeCookbook.id}@${activeCookbook.version} verrouillée`
        : `${activeCookbook.display_name} · verrouillée ${directSuperFast ? "au lancement" : "à la création du Plan"}`
      : "Cookbook indisponible";
    if (activeCookbook?.profile) elements.activeCookbook.textContent = `${activeCookbook.display_name} (${activeCookbook.version})`
      + (compositionReference ? " \u00b7 Pour changer de parcours ou d\u2019intention, utilisez Repartir de ce run." : " \u00b7 Recette fix\u00e9e \u00e0 la cr\u00e9ation du run.");
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    const needsConfiguration = Boolean(session && state.cookbook?.profile && !state.composition);
    elements.start.textContent = needsConfiguration ? "Reprendre la pr\u00e9paration du run" : state.forkSource ? "Cr\u00e9er le nouveau parcours" : "Cr\u00e9er le parcours";
    elements.start.disabled = locked || Boolean(state.openingSessionId)
      || (Boolean(state.session) && !needsConfiguration) || Boolean(setupValidationError());
    elements.imageInput.disabled = locked || Boolean(state.session)
      || Boolean(state.forkSource) || state.drafts.length >= 9;
    elements.model.disabled = locked || Boolean(state.session);
    window.PanelForgeModelPicker.setDisabled(elements.model, elements.model.disabled);
    elements.refreshModels.disabled = locked;
    elements.refreshSessions.disabled = locked;
    elements.sessionList.querySelectorAll(".session-link").forEach((button) => { button.disabled = locked; });
    elements.intention.disabled = locked || intentLocked;
    for (const control of [elements.creativeSceneLife, elements.creativeCamera, elements.creativeExtraMotion, elements.creativeDialogue]) {
      control.disabled = locked || intentLocked;
    }
    elements.showReasoning.disabled = locked;
    elements.newSession.disabled = locked || Boolean(state.openingSessionId);
    elements.newSession.hidden = !session && !state.forkSource;
    elements.forkSession.hidden = !session;
    elements.forkSession.disabled = locked || Boolean(state.openingSessionId) || !session;
    if (!session) {
      elements.promptReferences.hidden = true;
      window.dispatchEvent(new CustomEvent("panelforge:ref2v-context", {
        detail: { session_id: null, prompt_revision_id: null, ready: false },
      }));
      return;
    }

    renderDock();
    const brief = preparationInput();
    const briefInputsCurrent = !brief || (
      (brief.source_text || "").trim() === elements.intention.value.trim()
      && creativeAxesMatch(brief)
      && creativeAudacityMatch(brief)
    );
    const documents = state.composition ? state.composition.documents || {} : {};
    const plan = documents.beat_sheet || null;
    const prompt = documents.final_prompt || null;
    const briefState = shortRoute ? { ready: currentBriefInputs(), draft: false } : renderBrief(
      brief,
      Boolean(session.brief_complete && briefInputsCurrent),
      briefInputsCurrent,
    );
    const planState = directSuperFast ? { draft: false, ready: false, stale: false, diagnostics: [] }
      : renderDocument(
        elements.plan,
        plan,
        briefState.ready,
        briefState.draft ? "Brief modifié" : "Brief requis",
      );
    if (!directSuperFast && preparationSteps() > 1) {
      renderMultishotSummary();
      renderArbitrations(plan, planState, briefState.ready);
    }
    const promptPrerequisite = directSuperFast || preparationSteps() === 1 ? briefState.ready : planState.ready;
    const promptState = renderDocument(
      elements.prompt,
      prompt,
      promptPrerequisite,
      directSuperFast ? (briefState.draft ? "Brief modifié" : "Brief requis")
        : (planState.draft ? "Plan modifié" : "Plan requis"),
    );
    elements.sessionTitle.textContent = session.references.map((item) => item.label).join(" + ");
    const recipeReference = compositionReference || (directSuperFast ? activeCookbook : state.cookbook);
    const recipeLabel = recipeReference
      ? `${recipeReference.id}@${recipeReference.version}${compositionReference ? "" : " · à verrouiller"}`
        : "non sélectionnée";
    const audacityLabel = brief
      ? brief.creative_audacity ?? 0
      : Number(elements.creativeAudacity.value);
    const briefLabel = combat ? `${shortRoute ? "Intention" : "Brief"} Combat ${session.preparation.version} \u00b7 audace ${audacityLabel}/3`
      : shortRoute ? `Intention directe · audace ${audacityLabel}/3` : session.brief_variant
      ? `Brief : direction créative ${session.brief_variant.version} · audace ${audacityLabel}/3`
      : `Brief : standard ${session.profile.version}`;
    elements.sessionConfig.textContent = `Modèle : ${session.model_id} · ${briefLabel} · Recette : ${recipeLabel}`;
    elements.progress.textContent = !briefState.ready ? (shortRoute ? "Intention requise" : "Brief requis")
      : !directSuperFast && preparationSteps() > 1 && !planState.ready ? "Plan requis"
        : !promptState.ready ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptState.ready ? "success" : "active"}`;
    setChip(elements.chips.brief, briefState.ready, !briefState.ready);
    if (!directSuperFast) setChip(elements.chips.plan, planState.ready, briefState.ready && !planState.ready);
    setChip(elements.chips.prompt, promptState.ready, promptPrerequisite && !promptState.ready);
    elements.copyPrompt.disabled = locked || !promptState.ready;
    elements.sendVideoLab.disabled = locked || !prompt
      || !prompt.active_revision_id || !elements.prompt.content.value.trim();
    renderPromptReferences(prompt);
    window.dispatchEvent(new CustomEvent("panelforge:ref2v-context", {
      detail: {
        session_id: session.id,
        prompt_revision_id: prompt ? prompt.active_revision_id : null,
        ready: Boolean(generatedDocument(prompt) && !promptState.draft),
      },
    }));
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

  function renderPromptReferences(documentState) {
    const active = documentState && documentState.active_revision_id;
    const visible = Boolean(active || elements.prompt.content.value.trim());
    elements.promptReferences.hidden = !visible;
    if (!visible) return;
    const key = `${state.session.id}:${active}:${state.session.references
      .map((reference) => reference.label).join("|")}`;
    if (elements.promptReferences.dataset.renderKey === key) return;
    elements.promptReferences.replaceChildren();
    const title = document.createElement("small");
    title.className = "prompt-reference-copy-title";
    title.textContent = "Références à ajouter au prompt";
    elements.promptReferences.append(title);
    state.session.references.forEach((reference, index) => {
      const row = document.createElement("div");
      row.className = "prompt-reference-copy-row";
      const label = document.createElement("code");
      label.textContent = `<Picture ${index + 1}> · ${reference.label}`;
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Copier le nom";
      button.setAttribute("aria-label", `Copier le nom ${reference.label}`);
      button.addEventListener("click", async () => {
        const copied = await copyText(reference.label);
        button.textContent = copied ? "Copié" : "Échec de copie";
        window.setTimeout(() => { button.textContent = "Copier le nom"; }, 1400);
      });
      row.append(label, button);
      elements.promptReferences.append(row);
    });
    elements.promptReferences.dataset.renderKey = key;
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_) {
      const fallback = document.createElement("textarea");
      try {
        fallback.value = value;
        fallback.setAttribute("readonly", "");
        fallback.style.position = "fixed";
        fallback.style.opacity = "0";
        document.body.append(fallback);
        fallback.select();
        return document.execCommand("copy");
      } catch (_) {
        return false;
      } finally {
        fallback.remove();
      }
    }
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

  function planDurationSeconds(documentState) {
    if (!documentState || !documentState.active_content) return null;
    let plan = null;
    try { plan = JSON.parse(documentState.active_content); } catch (_) { return null; }
    const derived = plan.derived_timing || {};
    const directMilliseconds = finiteNumber(derived.duration_ms, plan.duration_ms);
    if (directMilliseconds !== null) return directMilliseconds / 1000;
    const directSeconds = finiteNumber(derived.duration_seconds, plan.duration_seconds);
    if (directSeconds !== null) return directSeconds;
    const hold = finiteNumber(plan.final_state && plan.final_state.final_hold_ms) || 0;
    if (Array.isArray(plan.shots) && plan.shots.length) {
      const durations = plan.shots.map((shot) => finiteNumber(shot && shot.duration_ms));
      if (durations.every((duration) => duration !== null)) {
        return (durations.reduce((total, duration) => total + duration, 0) + hold) / 1000;
      }
    }
    if (Array.isArray(plan.beats) && plan.beats.length) {
      const lastEnd = Math.max(...plan.beats.map((beat) => finiteNumber(beat && beat.end_ms) || 0));
      if (lastEnd > 0) return (lastEnd + hold) / 1000;
    }
    return null;
  }

  function sendToVideoLab() {
    const documents = state.composition ? state.composition.documents || {} : {};
    const prompt = documents.final_prompt || null;
    const visiblePrompt = elements.prompt.content.value.trim();
    if (!state.session || !prompt || !prompt.active_revision_id || !visiblePrompt) return;
    if (!window.PanelForgeVideoLab) {
      elements.prompt.message.textContent = "Video Lab n’est pas disponible.";
      return;
    }
    window.PanelForgeVideoLab.prefill({
      source: "ref2v",
      references: state.session.references.slice(0, 3).map((reference) => ({
        asset_id: reference.asset_id,
        content_url: reference.content_url,
        label: reference.label,
      })),
      prompt: visiblePrompt,
      duration_seconds: planDurationSeconds(documents.beat_sheet || null)
        || Number(visiblePrompt.match(/one continuous ([\d.]+)-second shot/i)?.[1]) || null,
    });
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
    const multishot = isMultishotCookbook(activeCookbookSpec()) || ((combatControls.current() || cinematicControls.current()) && preparationSteps() > 1);
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
        ? summaryText(shot.phases?.flatMap(phase => phase.exchanges || []) || shot.exchanges || shot.actions || shot.primary_action || shot.dominant_action || shot.action || shot.purpose || shot.objective || shot.description) || "Action non résumée."
        : "Plan manquant.";
      card.append(header, description);
      if (shot) {
        const details = [
          ["Entrée", summaryText(shot.entry_state)],
          ["Cadrage", summaryText(shot.opening_composition)],
          ["Raccord", summaryText(shot.transition || shot.continuity_from_previous)],
          ["Sortie", summaryText(shot.end_state || shot.observable_end_state || shot.exit_state)],
          ["Références", summaryText(shot.active_picture_labels || shot.active_references || shot.references)],
          ["Rythme", shot.pacing],
          ["Caméra", shot.phases?.map(phase => [phase.cue, cameraSummary(phase.camera)].filter(Boolean).join(" ")).join(" → ") || shot.camera_motion || cameraSummary(shot.camera)],
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
    elements.brief.rewriteApprove.disabled = elements.brief.rewrite.disabled;
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
    elements.applyApproveArbitrations.disabled = elements.applyArbitrations.disabled;
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
      : { source_text: elements.intention.value.trim(), ...creativePayload() };
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/brief/${revision ? "revise" : "structure"}/stream`,
      payload,
      elements.brief,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Brief révisé à partir des images." : "Brief multimodal généré.",
      { notifyOutcome: !state.quickRunning },
    );
    if (completed) {
      if (revision) elements.brief.instruction.value = "";
      await refreshComposition();
    }
    return completed;
  }

  async function reviseAndApproveBrief() {
    if (!state.session || state.compoundRunning) return false;
    state.compoundRunning = true;
    render();
    try {
      const sessionId = state.session.id;
      const previousRevisionId = state.session.active_brief_revision_id;
      if (!await streamBrief(true)) return false;
      const currentRevisionId = state.session && state.session.active_brief_revision_id;
      if (!state.session || state.session.id !== sessionId
        || !currentRevisionId || currentRevisionId === previousRevisionId
        || !currentBriefInputs()) {
        showStageError(elements.brief, new Error("La nouvelle version du Brief n’a pas pu être confirmée ; elle n’a pas été validée."), false);
        return false;
      }
      return briefAction("approve");
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
    if (!state.cookbook) throw new Error("Choisissez une recette Ref2V Direct.");
    const response = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: state.cookbook.id,
          cookbook_version: state.cookbook.version,
          preparation_intent: preparationSteps() < 3 ? { source_text: elements.intention.value.trim(), ...creativePayload() } : null,
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
        { notifyOutcome: !state.quickRunning },
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
    if (completed) {
      resetArbitrations();
      render();
    }
    return completed;
  }

  async function reconcileAndApprovePlan() {
    if (!state.session || !state.composition || state.compoundRunning) return false;
    state.compoundRunning = true;
    render();
    try {
      const sessionId = state.session.id;
      const documents = state.composition.documents || {};
      const previousRevisionId = documents.beat_sheet
        ? documents.beat_sheet.active_revision_id : null;
      if (!await reconcilePlan()) return false;
      const currentDocuments = state.composition ? state.composition.documents || {} : {};
      const currentRevisionId = currentDocuments.beat_sheet
        ? currentDocuments.beat_sheet.active_revision_id : null;
      const currentPlan = currentDocuments.beat_sheet || null;
      if (!state.session || state.session.id !== sessionId || !generatedDocument(currentPlan)
        || !currentRevisionId || currentRevisionId === previousRevisionId) {
        showStageError(elements.plan, new Error("Le nouveau Plan n’a pas pu être confirmé ; il n’a pas été validé."), false);
        return false;
      }
      return documentAction("beat-sheet", "approve");
    } finally {
      state.compoundRunning = false;
      render();
    }
  }

  async function streamResult(url, payload, view, onEvent, successMessage, { notifyOutcome = true } = {}) {
    const previous = view.content.value;
    const outcomeTone = core.createLlmOutcomeTone();
    let received = false;
    let completed = false;
    let truncationError = "";
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
      outcomeTone.start();
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
          truncationError = core.truncationMessage(event);
          view.message.className = "message warning-text";
          view.message.textContent = truncationError;
        }
      });
      if (!completed) throw new Error(truncationError || "Le flux s’est terminé sans résultat persistant.");
      view.message.className = "message";
      view.message.textContent = successMessage;
      if (notifyOutcome) outcomeTone.success();
      return true;
    } catch (error) {
      if (!received) view.content.value = previous;
      showStageError(view, error, received);
      core.failStreamState(view.stream, error.message);
      if (notifyOutcome) outcomeTone.failure();
      return false;
    } finally {
      reasoningTrace.finish();
      setBusy(false);
    }
  }

  async function briefAction(action, payload = null) {
    let succeeded = false;
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
      succeeded = true;
      return true;
    } catch (error) {
      showStageError(elements.brief, error, false);
      return false;
    } finally {
      setBusy(false);
      if (succeeded && action === "approve") revealNextStage("brief");
    }
  }

  async function documentAction(stageName, action, payload = null) {
    const view = stageName === "beat-sheet" ? elements.plan : elements.prompt;
    let succeeded = false;
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
      succeeded = true;
      return true;
    } catch (error) {
      showStageError(view, error, false);
      return false;
    } finally {
      setBusy(false);
      if (succeeded && action === "approve") revealNextStage(stageName);
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

  function releaseDraftPreviews() {
    state.drafts.forEach((draft) => {
      if (draft.file && draft.previewUrl) URL.revokeObjectURL(draft.previewUrl);
    });
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
    if (state.quickRunning || state.superFastRunning) return;
    state.openRequestId += 1;
    state.openingSessionId = null;
    const preservedCookbook = activeCookbookSpec() || state.cookbook;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    state.superFastRecord = null;
    state.forkSource = null;
    combatControls.restore(null);
    cinematicControls.restore(null);
    state.cookbook = isSuperFastReference(preservedCookbook)
      ? superFastCookbookSpec()
      : preservedCookbook && directCookbooks().find(
        (item) => cookbookValue(item) === cookbookValue(preservedCookbook),
      ) || null;
    if (!state.cookbook) resetCookbookSelection();
    else elements.cookbook.value = cookbookValue(state.cookbook);
    resetArbitrations();
    releaseDraftPreviews();
    state.drafts = [];
    invalidateRoleConfirmation();
    renderDraftReferences();
    elements.intention.value = "";
    setCreativeAxes(null, 0);
    setCreativeAudacity(2);
    elements.creativeDirection.checked = false;
    elements.executionMode.value = "supervised";
    clearStageDrafts();
    render();
  }

  function prefillAnalysis({ intention, references }) {
    if (!state.spec || !state.cookbook) throw new Error("REF2V est encore en cours de chargement.");
    if (interactionLocked()) throw new Error("Une préparation REF2V est en cours. L’analyse reste disponible pour le transfert.");
    if (!intention?.trim() || !Array.isArray(references) || !references.length || references.length > 9) throw new Error("Choisissez une intention et 1 à 9 références.");
    if (references.some(r => !r.file || !roleOptions.some(([role]) => role === r.role))) throw new Error("Référence ou rôle indisponible.");
    if (["first_frame", "last_frame"].some(role => references.filter(r => r.role === role).length > 1)) throw new Error("Une seule première et une seule dernière frame exactes sont autorisées.");
    if (!state.session && (elements.intention.value.trim() || state.drafts.length || state.forkSource)) {
      throw new Error("Un brouillon REF2V est déjà ouvert. Conservez-le ou ouvrez un nouvel atelier avant de transférer l’analyse.");
    }
    resetSession();
    state.drafts = references.map(({ file, role }) => ({ file, role, previewUrl: URL.createObjectURL(file) }));
    invalidateRoleConfirmation(); renderDraftReferences();
    elements.intention.value = intention.trim(); render();
    showSetupMessage("Intention issue de l’analyse. Vérifiez les rôles des références avant de lancer la préparation.");
    window.PanelForgeLabNavigation?.switchView("ref2v-direct");
    elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
    elements.intention.focus({ preventScroll: true });
  }
  window.PanelForgeRef2V = Object.freeze({ prefillAnalysis });

  elements.imageInput.addEventListener("change", () => addFiles(elements.imageInput.files || []));
  elements.form.addEventListener("submit", createSession);
  elements.refreshModels.addEventListener("click", () => loadModels().catch((error) => showSetupMessage(error.message)));
  elements.preparationFamily.addEventListener("change", changePreparationFamily);
  elements.refreshSessions.addEventListener("click", () => loadSessions().catch((error) => showSetupMessage(error.message)));
  elements.cookbook.addEventListener("change", () => {
    const next = directCookbooks().find(
      (item) => cookbookValue(item) === elements.cookbook.value,
    ) || null;
    const expected = profileReference(next);
    if (state.session && (expected.version === experimentalProfileVersion || state.session.profile?.version === experimentalProfileVersion)
      && state.session.profile?.version !== expected.version) {
      showSetupMessage("Pour changer de recette expérimentale, utilisez Repartir de ce run : le Brief et le Plan doivent garder la même version.");
      return render();
    }
    state.cookbook = next;
    render();
  });
  elements.intention.addEventListener("input", render);
  elements.model.addEventListener("change", render);
  elements.creativeDirection.addEventListener("change", async () => {
    if (!state.session) return render();
    if (state.session.active_brief) return render();
    setBusy(true);
    try {
      state.session = await core.request(
        `/api/prompt-lab/sessions/${state.session.id}/brief/variant`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(creativeBriefPayload()),
        },
      );
      elements.brief.message.textContent = elements.creativeDirection.checked
        ? "Direction créative Ref2V 0.2.0 activée pour le Brief."
        : `Brief Ref2V standard ${state.session.profile.version} activé.`;
      await loadSessions();
    } catch (error) {
      elements.creativeDirection.checked = Boolean(state.session.brief_variant);
      showSetupMessage(error.message);
    } finally {
      setBusy(false);
    }
  });
  for (const control of [elements.creativeSceneLife, elements.creativeCamera, elements.creativeExtraMotion, elements.creativeDialogue]) {
    control.addEventListener("input", () => { updateCreativeAxes(); render(); });
  }
  elements.creativeAudacity.addEventListener("input", () => {
    elements.creativeAudacityValue.value = elements.creativeAudacity.value;
    render();
  });
  elements.roleConfirmation.addEventListener("change", () => {
    state.rolesConfirmed = elements.roleConfirmation.checked;
    render();
  });
  elements.newSession.addEventListener("click", resetSession);
  elements.forkSession.addEventListener("click", prepareFork);
  elements.quickResume.addEventListener("click", resumeAutomaticMode);
  elements.executionMode.addEventListener("change", render);

  elements.brief.content.addEventListener("input", render);
  elements.brief.instruction.addEventListener("input", render);
  elements.brief.generate.addEventListener("click", () => streamBrief(false));
  elements.brief.save.addEventListener("click", () => briefAction("edit", { content: elements.brief.content.value.trim() }));
  elements.brief.approve.addEventListener("click", () => briefAction("approve"));
  elements.brief.rewrite.addEventListener("click", () => streamBrief(true));
  elements.brief.rewriteApprove.addEventListener("click", reviseAndApproveBrief);

  elements.plan.content.addEventListener("input", render);
  elements.plan.generate.addEventListener("click", () => generateSuperFastOrStage("beat-sheet"));
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
  elements.applyApproveArbitrations.addEventListener("click", reconcileAndApprovePlan);

  elements.prompt.content.addEventListener("input", render);
  elements.prompt.instruction.addEventListener("input", render);
  elements.prompt.generate.addEventListener("click", () => generateSuperFastOrStage("final-prompt"));
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
  elements.sendVideoLab.addEventListener("click", sendToVideoLab);

  updateCreativeAxes();
  setCreativeAudacity(2);
  renderRoleHelp();
  renderDraftReferences();
  render();
  initialize();
})();
