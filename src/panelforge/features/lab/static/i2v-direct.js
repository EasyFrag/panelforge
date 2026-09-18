(() => {
  "use strict";

  const core = window.PanelForgeLabCore;
  const quickPipeline = window.PanelForgeQuickPipeline;
  if (!core || !quickPipeline) return;
  const $ = (selector) => document.querySelector(selector);
  const monoProfile = { id: "minimax.h3.fl2va.direct", version: "0.3.3" };
  const experimentalMonoProfile = { id: "minimax.h3.fl2va.direct", version: "0.4.0" };
  const multishotProfile = { id: "minimax.h3.fl2va.direct.multishot", version: "0.1.0" };
  const animalInterviewProfile = { id: "minimax.h3.base.animal-interview", version: "0.1.0" };
  const legacyProfileId = "minimax.h3.i2v.direct";
  const monoCookbookId = "minimax.h3.fl2va.direct";
  const multishotCookbookId = "minimax.h3.fl2va.direct.multishot";
  const animalInterviewCookbookId = "minimax.h3.base.animal-interview";
  const creativeBriefVariant = { id: "creative-direction", version: "0.2.0" };
  const preferredCookbookKey = "minimax.h3.fl2va.classic.cinematic.planned@1.0.0";
  const defaultPlanModelId = "local::unsloth/Qwen3.8-27B-GGUF";
  const defaultWriterModelId = "local::unsloth/gemma-4-31B-it-qat-GGUF";

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
    writerSaving: false,
    quickRunning: false,
    compoundRunning: false,
    quickRecord: null,
    openRequestId: 0,
    openingSessionId: null,
    arbitrationDecisions: {},
    arbitrationRevisionId: null,
    modelRequestId: 0,
  };

  const elements = {
    form: $("#i2vd-session-form"),
    model: $("#i2vd-model"),
    refreshModels: $("#i2vd-refresh-models"),
    cookbook: $("#i2vd-cookbook"),
    preparationFamily: $("#i2vd-preparation-family"),
    sequenceKind: $("#i2vd-sequence-kind"),
    activeCookbook: $("#i2vd-active-cookbook"),
    imageInput: $("#i2vd-image-input"),
    uploadPreview: $("#i2vd-upload-preview"),
    uploadTitle: $("#i2vd-upload-title"),
    uploadCaption: $("#i2vd-upload-caption"),
    removeFirstImage: $("#i2vd-remove-first-image"),
    lastImageInput: $("#i2vd-last-image-input"),
    lastUploadPreview: $("#i2vd-last-upload-preview"),
    lastUploadTitle: $("#i2vd-last-upload-title"),
    lastUploadCaption: $("#i2vd-last-upload-caption"),
    removeLastImage: $("#i2vd-remove-last-image"),
    inputMode: $("#i2vd-input-mode"),
    intentionTitle: $("#i2vd-intention-title"),
    standardIntention: $("#i2vd-standard-intention"),
    intention: $("#i2vd-intention"),
    animalFields: $("#i2vd-animal-interview-fields"),
    animal: $("#i2vd-animal"),
    environment: $("#i2vd-environment"),
    dialogueLanguage: $("#i2vd-dialogue-language"),
    duration: $("#i2vd-duration"),
    durationGuide: $("#i2vd-duration-guide"),
    partialScript: $("#i2vd-partial-script"),
    postAction: $("#i2vd-post-action"),
    creativeSceneLife: $("#i2vd-creative-scene-life"),
    creativeSceneLifeValue: $("#i2vd-creative-scene-life-value"),
    creativeCamera: $("#i2vd-creative-camera"),
    creativeCameraValue: $("#i2vd-creative-camera-value"),
    creativeExtraMotion: $("#i2vd-creative-extra-motion"),
    creativeExtraMotionValue: $("#i2vd-creative-extra-motion-value"),
    creativeDialogue: $("#i2vd-creative-dialogue"),
    creativeDialogueValue: $("#i2vd-creative-dialogue-value"),
    creativeAudacityControl: $("#i2vd-creative-audacity-control"),
    creativeAudacity: $("#i2vd-creative-audacity"),
    creativeAudacityValue: $("#i2vd-creative-audacity-value"),
    creativeDirectionOption: $("#i2vd-creative-direction-option"),
    creativeDirection: $("#i2vd-creative-direction"),
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
    emptyCopy: $("#i2vd-empty-copy"),
    setupPreview: $("#i2vd-setup-preview"),
    setupFrames: {
      first: {
        figure: $("#i2vd-setup-first-frame"),
        image: $("#i2vd-setup-first-image"),
        name: $("#i2vd-setup-first-name"),
      },
      last: {
        figure: $("#i2vd-setup-last-frame"),
        image: $("#i2vd-setup-last-image"),
        name: $("#i2vd-setup-last-name"),
      },
    },
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
  const chineseVariant = window.PanelForgeChinesePromptVariant.create({
    prefix: "i2vd", state, core, render,
    setComposition: value => { state.composition = value; },
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
      const [modelsResult, sessionsResult] = await Promise.allSettled([
        loadModels(),
        loadSessions(),
      ]);
      render();
      const failures = [modelsResult, sessionsResult]
        .filter((result) => result.status === "rejected")
        .map((result) => result.reason && result.reason.message ? result.reason.message : String(result.reason));
      if (failures.length) showSetupMessage(failures.join(" · "));
    } catch (error) {
      showSetupMessage(error.message);
    }
  }

  function cookbookKey(cookbook) {
    return cookbook ? `${cookbook.id}@${cookbook.version}` : "";
  }

  function profileReference(cookbook = state.cookbook) {
    if (cookbook?.profile) return cookbook.profile;
    if (cookbook && cookbook.id === monoCookbookId && cookbook.version === experimentalMonoProfile.version) return experimentalMonoProfile;
    if (cookbook && cookbook.id === multishotCookbookId) return multishotProfile;
    if (cookbook && cookbook.id === animalInterviewCookbookId) return animalInterviewProfile;
    return monoProfile;
  }

  function selectedProfile(cookbook = state.cookbook) {
    const reference = state.session?.profile || profileReference(cookbook);
    return state.spec && (state.spec.profiles || []).find(
      (item) => item.id === reference.id && item.version === reference.version,
    );
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
      nodes.forEach((node) => { node.textContent = node.dataset.preparationDefault; });
      return;
    }
    copy.querySelector("b").textContent = cookbook.display_name;
    copy.querySelector("p").textContent = cookbook.description;
    elements.steps.plan.querySelector(".cookbook-step-copy small").textContent = preparationSteps() === 2
      ? "Interpréter l’intention et organiser les actions, contacts et risques."
      : "Vérifier les actions, contacts, durée et risques du Brief.";
    elements.steps.prompt.querySelector(".cookbook-step-copy small").textContent = preparationSteps() === 1
      ? sequenceKind(cookbook) === "multi"
        ? "Choisir 2 à 4 plans et rédiger en un appel. Une caméra par plan ; 8 s si aucune durée n’est demandée."
        : "Préparer le prompt depuis l’intention et les images. Un mouvement caméra principal ; 8 s si aucune durée n’est demandée."
      : "Rédiger depuis le Plan validé, puis compiler le prompt H3.";
    if (sequenceKind(cookbook) === "multi") {
      elements.steps.plan.querySelector(".cookbook-step-copy small").textContent =
        "Organiser les états successifs, les actions, les coupes et la continuité de 2 à 4 plans.";
    }
  }

  function creativeBriefAvailable(cookbook = state.cookbook) {
    const profile = selectedProfile(cookbook);
    return Boolean(
      cookbook && (cookbook.id === monoCookbookId || (cookbook.profile && cookbook.preparation_steps === 3))
      && profile && (profile.brief_variants || []).some(
        (value) => value.id === creativeBriefVariant.id
          && value.version === selectedCreativeBriefVariant(cookbook).version,
      ),
    );
  }

  function selectedCreativeBriefVariant(cookbook = state.cookbook) {
    // Pinned per profile: reopening an old run keeps its former Brief recipe.
    const profile = selectedProfile(cookbook);
    return (profile?.id === monoCookbookId && ["0.5.0", "0.6.0"].includes(profile.version))
      || (profile?.id === multishotCookbookId && ["0.2.0", "0.3.0"].includes(profile.version))
      ? { id: creativeBriefVariant.id, version: "0.3.0" }
      : creativeBriefVariant;
  }

  const writerModels = window.PanelForgePromptWriterModel.create({
    prefix: "i2vd", state, planner: elements.model,
    cookbook: () => activeCookbookSpec() || state.cookbook,
    request: core.request, render, busy: interactionLocked,
    defaultModelId: defaultWriterModelId, defaultEnabled: true,
  });
  const combatControls = window.PanelForgeCombatControls.create({ prefix: "i2vd", state, elements, recipes: directCookbooks, render, busy: interactionLocked, steps: preparationSteps });
  const cinematicControls = window.PanelForgeClassicCinematicControls.create({ prefix: "i2vd", state, elements, recipes: directCookbooks, render, busy: interactionLocked, steps: preparationSteps });
  const sensualControls = window.PanelForgeSensualControls.create({ prefix: "i2vd", state, elements, recipes: directCookbooks, render, busy: interactionLocked });

  function preparationFamily(value = state.session || activeCookbookSpec() || state.cookbook) {
    return value?.preparation?.family || "classic";
  }

  function changePreparationFamily() {
    if (state.session || interactionLocked()) return render();
    const family = elements.preparationFamily.value;
    if (family === "combat") return combatControls.choose("combat", "1.3.0");
    if (family === "sensual") return sensualControls.choose();
    const choices = directCookbooks().filter((item) => preparationFamily(item) === family
      && !item.preparation?.version
      && core.recipeTier(cookbookKey(item)) === "standard"
      && sequenceKind(item) === elements.sequenceKind.value);
    const next = choices.find((item) => item.preparation_steps === preparationSteps()) || choices[0];
    if (!next) return render();
    state.cookbook = next;
    elements.creativeDirection.checked = false;
    render();
  }

  function creativeBriefPayload() {
    const variant = selectedCreativeBriefVariant();
    return creativeBriefAvailable() && elements.creativeDirection.checked
      ? {
        brief_variant_id: variant.id,
        brief_variant_version: variant.version,
      }
      : { brief_variant_id: null, brief_variant_version: null };
  }

  function directCookbooks() {
    return state.cookbooks.filter(
      (item) => (item.profile || [monoCookbookId, multishotCookbookId, animalInterviewCookbookId].includes(item.id))
        && item.target_mode === "fl2va_direct",
    );
  }

  function sequenceKind(cookbook) {
    return cookbook?.profile?.id === "minimax.h3.fl2va.combat.multishot"
      || cookbook?.id === multishotCookbookId || cookbook?.id?.startsWith(`${multishotCookbookId}.`)
      ? "multi" : "mono";
  }

  function changeSequenceKind() {
    if (state.session || interactionLocked()) return render();
    const family = elements.sequenceKind.value;
    const choices = directCookbooks().filter((item) => sequenceKind(item) === family
      && preparationFamily(item) === preparationFamily()
      && (preparationFamily() !== "combat" || item.preparation.version === state.cookbook?.preparation?.version)
      && core.recipeTier(cookbookKey(item)) === "standard");
    const next = choices.find((item) => item.preparation_steps === preparationSteps()) || choices[0];
    if (next) state.cookbook = next;
    render();
  }

  function populateCookbooks() {
    const available = directCookbooks();
    elements.cookbook.replaceChildren();
    available
      .sort((left, right) => cookbookKey(left).localeCompare(cookbookKey(right)))
      .forEach((cookbook) => {
        const option = document.createElement("option");
        option.value = cookbookKey(cookbook);
        option.dataset.preparationFamily = preparationFamily(cookbook);
        option.dataset.preparationVersion = cookbook.preparation?.version || "";
        option.dataset.classicVersion = cookbook.preparation?.family === "classic" ? cookbook.preparation?.version || "legacy" : "";
        option.dataset.recipeFamily = sequenceKind(cookbook);
        option.textContent = cookbook.profile ? `${cookbook.display_name} (${cookbook.version})` : cookbook.id === multishotCookbookId
          ? `Multi-plan structuré · 2 à 4 plans (${cookbook.version})`
          : cookbook.id === animalInterviewCookbookId
            ? `Mono-plan · interview d’animal (${cookbook.version})`
            : cookbook.version === experimentalMonoProfile.version
              ? `Mono-plan · compact · historique (${cookbook.version})`
            : cookbook.id === monoCookbookId && cookbook.version === monoProfile.version
              ? `Mono-plan · standard (${cookbook.version})`
              : `Mono-plan · historique (${cookbook.version})`;
        elements.cookbook.append(option);
      });
    state.cookbook = available.find(
      (item) => cookbookKey(item) === preferredCookbookKey,
    ) || available.find((item) => cookbookKey(item) === "minimax.h3.fl2va.direct.guided@1.2.0")
      || available.at(-1) || null;
    elements.cookbook.value = cookbookKey(state.cookbook);
    core.refreshRecipeVisibility(elements.cookbook);
  }

  function activeCookbookSpec() {
    const reference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : state.cookbook;
    if (!reference) return null;
    return state.cookbooks.find(
      (item) => item.id === reference.id && item.version === reference.version,
    ) || null;
  }

  function cookbookForSession(session, composition = null) {
    const reference = composition && composition.cookbook;
    if (reference) {
      return directCookbooks().find(
        (item) => item.id === reference.id && item.version === reference.version,
      ) || null;
    }
    const profileId = session && session.profile && session.profile.id;
    const pinned = directCookbooks().find((item) => item.profile?.id === profileId
      && item.profile?.version === session?.profile?.version && item.preparation_steps === 3);
    if (pinned) return pinned;
    const expectedId = profileId === multishotProfile.id
      ? multishotCookbookId
      : profileId === animalInterviewProfile.id
        ? animalInterviewCookbookId : monoCookbookId;
    return directCookbooks().find((item) => item.id === expectedId && item.version === session?.profile?.version)
      || directCookbooks().find((item) => item.id === expectedId)
      || null;
  }

  async function loadModels() {
    const requestId = ++state.modelRequestId;
    const selected = elements.model.value || defaultPlanModelId;
    const hadModels = [...elements.model.options].some((option) => option.value);
    elements.refreshModels.disabled = true;
    try {
      const payload = await core.request("/api/prompt-lab/models");
      if (requestId !== state.modelRequestId) return;
      const models = (payload.models || []).filter(
        (model) => model && typeof model.id === "string" && model.id.trim(),
      );
      if (!models.length) throw new Error("llama.swap ne publie actuellement aucun modèle.");
      window.PanelForgeModelPicker.populate(elements.model, models, selected);
      writerModels.populate(models);
      chineseVariant.populate(models);
      render();
    } catch (error) {
      if (requestId === state.modelRequestId && !hadModels) {
        const unavailable = document.createElement("option");
        unavailable.value = "";
        unavailable.textContent = "Modèles indisponibles — réessayer";
        elements.model.replaceChildren(unavailable);
      }
      throw new Error(`Modèles H3 Base indisponibles : ${error.message}`);
    } finally {
      if (requestId === state.modelRequestId) elements.refreshModels.disabled = false;
    }
  }

  async function refreshModels() {
    try {
      await loadModels();
      showSetupMessage("");
    } catch (error) {
      showSetupMessage(error.message);
    }
  }

  async function loadSessions() {
    const payload = await core.request("/api/prompt-lab/sessions?limit=30");
    const sessions = (payload.sessions || []).filter(
      (item) => item.profile && (
        (item.session_mode === "h3_base"
          && [monoProfile.id, multishotProfile.id, animalInterviewProfile.id, "minimax.h3.fl2va.classic.cinematic", "minimax.h3.fl2va.combat", "minimax.h3.fl2va.combat.multishot", "minimax.h3.fl2va.sensual"].includes(item.profile.id))
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
      title.textContent = (preparationFamily(session) === "combat" ? "Combat \u00b7 " : preparationFamily(session) === "sensual" ? "Sensuel \u00b7 " : window.PanelForgeClassicCinematicControls.isCinematic(session) ? "Mise en scène \u00b7 " : "") + sessionInputModeLabel(session);
      const detail = document.createElement("small");
      detail.textContent = session.brief_complete ? "Brief validé" : "Préparation vidéo";
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

  function referenceForRole(session, role) {
    return session && (session.references || []).find((item) => item.role === role) || null;
  }

  function animalInterviewSelected(cookbook = state.cookbook) {
    return Boolean(cookbook && cookbook.id === animalInterviewCookbookId);
  }

  function animalInterviewSourceText() {
    const action = elements.postAction.value.trim() || "Choose one minimal species-appropriate action that continues through the final frame.";
    return [
      "PANELFORGE_ANIMAL_INTERVIEW_V1",
      `LANGUAGE: ${elements.dialogueLanguage.value}`,
      `TARGET DURATION: ${elements.duration.value} seconds`,
      `INTERVIEWED ANIMAL: ${elements.animal.value.trim()}`,
      `ENVIRONMENT: ${elements.environment.value.trim()}`,
      "INTERVIEWER FRAMING: Partially visible at the far left edge in softly blurred side profile, with shoulder, hand and microphone visible; her mouth remains secondary and out of focus, and the animal remains the sharp primary subject.",
      "PARTIAL SCRIPT:",
      elements.partialScript.value.trim(),
      "POST-INTERVIEW ACTION:",
      action,
    ].join("\n");
  }

  function currentSourceText() {
    return animalInterviewSelected() ? animalInterviewSourceText() : elements.intention.value.trim();
  }

  function countAnimalInterviewReplies(script) {
    const value = String(script || "");
    const labeledReplies = value.split(/\r?\n/).filter(
      (line) => /^\s*(?:S[12]|intervieweuse|interviewer|animal|chaton|kitten)\s*[:\-]/i.test(line),
    ).length;
    if (labeledReplies) return labeledReplies;
    return (value.match(/["“][^"”\n]+["”]/g) || []).length;
  }

  function renderAnimalInterviewDurationGuide(visible) {
    elements.durationGuide.hidden = !visible;
    if (!visible) return;
    const replyCount = countAnimalInterviewReplies(elements.partialScript.value);
    if (!replyCount) {
      elements.durationGuide.classList.remove("tight");
      elements.durationGuide.textContent = "Ajoutez des répliques pour estimer la durée.";
      return;
    }
    const selectedDuration = Number(elements.duration.value);
    const recommendedDuration = replyCount * 4;
    const tight = Number.isFinite(selectedDuration) && selectedDuration < recommendedDuration;
    const selectedLabel = Number.isInteger(selectedDuration)
      ? String(selectedDuration) : selectedDuration.toFixed(1);
    elements.durationGuide.classList.toggle("tight", tight);
    elements.durationGuide.textContent = tight
      ? `${replyCount} réplique${replyCount > 1 ? "s" : ""} · ${selectedLabel} s choisies · ${recommendedDuration} s conseillées`
      : `${replyCount} réplique${replyCount > 1 ? "s" : ""} · durée conseillée : ${recommendedDuration} s`;
  }

  function resetAnimalInterviewInputs() {
    elements.animal.value = "";
    elements.environment.value = "";
    elements.dialogueLanguage.value = "French";
    elements.duration.value = "14";
    elements.partialScript.value = "";
    elements.postAction.value = "";
  }

  function hydrateSourceInputs(sourceText) {
    const source = (sourceText || "").trim();
    if (!source.startsWith("PANELFORGE_ANIMAL_INTERVIEW_V1\n")) {
      elements.intention.value = source;
      return;
    }
    const scalar = (label, fallback = "") => {
      const match = source.match(new RegExp(`^${label}:\\s*(.+)$`, "m"));
      return match ? match[1].trim() : fallback;
    };
    elements.dialogueLanguage.value = scalar("LANGUAGE", "French") === "English" ? "English" : "French";
    elements.duration.value = scalar("TARGET DURATION", "14 seconds").replace(/\s*seconds?\s*$/i, "") || "14";
    elements.animal.value = scalar("INTERVIEWED ANIMAL");
    elements.environment.value = scalar("ENVIRONMENT");
    const scriptMatch = source.match(/PARTIAL SCRIPT:\n([\s\S]*?)\nPOST-INTERVIEW ACTION:\n([\s\S]*)$/);
    elements.partialScript.value = scriptMatch ? scriptMatch[1].trim() : "";
    const postAction = scriptMatch ? scriptMatch[2].trim() : "";
    elements.postAction.value = postAction.startsWith("Choose one minimal species-appropriate action") ? "" : postAction;
    elements.intention.value = "";
  }

  function sessionInputModeLabel(session) {
    const first = Boolean(referenceForRole(session, "first_frame"));
    const last = Boolean(referenceForRole(session, "last_frame"));
    const prefix = session && session.profile
      && session.profile.id === animalInterviewProfile.id ? "Interview animal · " : "";
    if (first && last) return `${prefix}Première + dernière frame · FL2VA`;
    if (first) return `${prefix}Première frame · I2VA`;
    if (last) return `${prefix}Dernière frame · L2VA`;
    return `${prefix}Texte seul · T2VA`;
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
      title.removeAttribute("title");
      captionNode.textContent = "Facultatif · PNG, JPEG ou WebP · 25 Mio maximum";
      return;
    }
    preview.src = reference.content_url;
    preview.hidden = false;
    title.textContent = reference.label;
    title.title = reference.label;
    captionNode.textContent = caption;
  }

  async function openSession(sessionSummary) {
    if (state.quickRunning || state.writerSaving) return;
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
      writerModels.restore(state.composition?.writer_model_id);
      state.cookbook = cookbookForSession(session, state.composition) || state.cookbook;
      state.quickRecord = quickPipeline.load(session.id);
      selectModel(session.model_id);
      showReferencePreview("first", referenceForRole(session, "first_frame"), "Première frame de ce parcours");
      showReferencePreview("last", referenceForRole(session, "last_frame"), "Dernière frame de ce parcours");
      resetAnimalInterviewInputs();
      const input = preparationInput();
      if (input) {
        hydrateSourceInputs(input.source_text || "");
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
    const input = preparationInput();
    const sourceCookbook = state.composition && state.composition.cookbook;
    const matchingCookbook = sourceCookbook
      ? directCookbooks().find(
        (item) => item.id === sourceCookbook.id && item.version === sourceCookbook.version,
      )
      : cookbookForSession(source);
    if (matchingCookbook) state.cookbook = matchingCookbook;
    state.forkSource = source;
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    resetArbitrations();
    selectModel(source.model_id);
    showReferencePreview("first", referenceForRole(source, "first_frame"), "Première frame réutilisée");
    showReferencePreview("last", referenceForRole(source, "last_frame"), "Dernière frame réutilisée");
    const brief = input;
    resetAnimalInterviewInputs();
    hydrateSourceInputs(brief ? brief.source_text || "" : "");
    setCreativeAxes(brief && brief.creative_axes, brief ? brief.creative_freedom ?? 35 : 0);
    setCreativeAudacity(brief ? brief.creative_audacity ?? 0 : 2);
    elements.creativeDirection.checked = Boolean(
      source.brief_variant
      && source.brief_variant.id === creativeBriefVariant.id,
    );
    elements.quickMode.checked = true;
    clearStageDrafts();
    showSetupMessage("");
    render();
    elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function selectFile(slot) {
    const input = slot === "first" ? elements.imageInput : elements.lastImageInput;
    const file = input.files && input.files[0];
    if (file) setSelectedFile(slot, file);
  }

  function setSelectedFile(slot, file) {
    const first = slot === "first";
    const preview = first ? elements.uploadPreview : elements.lastUploadPreview;
    const title = first ? elements.uploadTitle : elements.lastUploadTitle;
    const caption = first ? elements.uploadCaption : elements.lastUploadCaption;
    const urlKey = first ? "firstPreviewUrl" : "lastPreviewUrl";
    const fileKey = first ? "firstFile" : "lastFile";
    if (state[urlKey]) URL.revokeObjectURL(state[urlKey]);
    state[fileKey] = file;
    state[urlKey] = URL.createObjectURL(file);
    preview.src = state[urlKey];
    preview.hidden = false;
    title.textContent = file.name;
    title.title = file.name;
    caption.textContent = `${Math.ceil(file.size / 1024)} Kio · cliquer pour remplacer`;
    showSetupMessage("");
    render();
  }

  function removeSelectedFile(slot) {
    if (interactionLocked() || state.session || state.forkSource) return;
    showReferencePreview(slot, null, "");
    showSetupMessage("");
    render();
  }

  function setupPreviewItem(slot) {
    const first = slot === "first";
    const preview = first ? elements.uploadPreview : elements.lastUploadPreview;
    const title = first ? elements.uploadTitle : elements.lastUploadTitle;
    const src = preview.getAttribute("src");
    if (preview.hidden || !src) return null;
    return {
      src,
      name: title.textContent.trim(),
    };
  }

  function renderSetupPreview() {
    const previews = {
      first: setupPreviewItem("first"),
      last: setupPreviewItem("last"),
    };
    const count = Object.values(previews).filter(Boolean).length;
    const visible = !state.session && count > 0;
    elements.empty.classList.toggle("has-anchor-preview", visible);
    elements.emptyCopy.hidden = visible;
    elements.setupPreview.hidden = !visible;
    elements.setupPreview.dataset.count = String(count);
    Object.entries(previews).forEach(([slot, preview]) => {
      const target = elements.setupFrames[slot];
      target.figure.hidden = !preview;
      if (!preview) {
        target.image.removeAttribute("src");
        target.name.textContent = "";
        target.name.removeAttribute("title");
        return;
      }
      target.image.src = preview.src;
      target.name.textContent = preview.name;
      target.name.title = preview.name;
    });
  }

  function setupValidationError() {
    if (!selectedProfile() || !state.cookbook) return "Le profil Direct est encore en cours de chargement.";
    if (!elements.model.value) return "Choisissez un modèle multimodal.";
    if (animalInterviewSelected()) {
      if (!elements.animal.value.trim()) return "Décrivez l’animal interviewé.";
      if (!elements.environment.value.trim()) return "Décrivez l’environnement.";
      const duration = Number(elements.duration.value);
      if (!Number.isFinite(duration) || duration < 4 || duration > 30) return "La durée doit être comprise entre 4 et 30 secondes.";
      if (!elements.partialScript.value.trim()) return "Ajoutez un script, même incomplet.";
    } else if (!elements.intention.value.trim()) return "Décrivez votre intention.";
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
      writerModels.value();
      if (state.session) {
        if (!state.cookbook?.profile || state.composition) throw new Error("Ce run est d\u00e9j\u00e0 configur\u00e9.");
        // Retry only recipe persistence after a failed configuration request.
      } else if (forkSource) {
        const profile = selectedProfile();
        state.session = await core.request(
          `/api/prompt-lab/sessions/${forkSource.id}/fork`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              model_id: elements.model.value,
              profile_id: profile.id,
              profile_version: profile.version,
              inherit_brief_variant: false,
              ...creativeBriefPayload(),
              combat_settings: combatControls.payload(),
              cinematic_settings: cinematicControls.payload(),
              sensual_settings: sensualControls.payload(),
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
        if (combatControls.payload()) body.append("combat_settings", JSON.stringify(combatControls.payload()));
        if (cinematicControls.payload()) body.append("cinematic_settings", JSON.stringify(cinematicControls.payload()));
        if (sensualControls.payload()) body.append("sensual_settings", JSON.stringify(sensualControls.payload()));
        if (elements.creativeDirection.checked) {
          const variant = selectedCreativeBriefVariant();
          body.append("brief_variant_id", variant.id);
          body.append("brief_variant_version", variant.version);
        }
        state.session = await core.request("/api/prompt-lab/sessions", { method: "POST", body });
      }
      state.forkSource = null;
      state.composition = null;
      state.quickRecord = null;
      if (state.cookbook?.profile) await ensureComposition();
      created = true;
      render();
      await loadSessions();
      elements[preparationSteps() === 1 ? "prompt" : preparationSteps() === 2 ? "plan" : "brief"].message.textContent = "Parcours créé. Lancez la première étape quand vous êtes prêt.";
    } catch (creationError) {
      showSetupMessage(creationError.message);
    } finally {
      setBusy(false);
    }
    if (created && quickRequested) await runQuickMode();
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
    return state.busy || state.quickRunning || state.compoundRunning
      || state.writerSaving || chineseVariant.busy() || Boolean(state.openingSessionId);
  }

  function currentBriefInputs() {
    const brief = preparationInput();
    return Boolean(brief
      && (brief.source_text || "").trim() === currentSourceText()
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

  function renderQuickStatus() {
    elements.quickMode.disabled = interactionLocked() || Boolean(state.session);
    const record = state.quickRecord;
    elements.quickStatus.hidden = !record;
    if (!record) return;
    const completedBecameIncomplete = record.status === "completed"
      && state.session && !quickSnapshot().promptApproved;
    const visibleStatus = completedBecameIncomplete ? "interrupted" : record.status;
    elements.quickStatus.className = `quick-mode-status ${visibleStatus === "retrying" ? "running" : visibleStatus}`;
    elements.quickResume.hidden = !["stopped", "interrupted"].includes(visibleStatus);
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

  function render() {
    // Recipe metadata can arrive after the initial slider setup.
    updateCreativeAxes();
    const session = state.session;
    const compositionReference = state.composition && state.composition.cookbook
      ? state.composition.cookbook : null;
    const activeCookbook = activeCookbookSpec();
    elements.cookbook.value = cookbookKey(compositionReference || state.cookbook);
    elements.sequenceKind.value = sequenceKind(activeCookbook || state.cookbook);
    elements.cookbook.dataset.recipeFamily = elements.sequenceKind.value;
    core.refreshRecipeVisibility(elements.cookbook);
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
    if (elements.sequenceKind) elements.sequenceKind.closest("label").hidden = false;
    combatControls.draw(activeCookbook || state.cookbook);
    cinematicControls.draw(activeCookbook || state.cookbook);
    sensualControls.draw(activeCookbook || state.cookbook);
    core.refreshRecipeVisibility(elements.cookbook);
    const locked = interactionLocked();
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
    core.renderPreparationStages(elements, core.preparationStages(activeCookbook));
    renderPreparationCopy(activeCookbook);
    renderQuickStatus();
    elements.cookbook.disabled = locked || Boolean(session);
    elements.sequenceKind.disabled = locked || Boolean(session);
    elements.activeCookbook.textContent = activeCookbook
      ? compositionReference
        ? `${activeCookbook.display_name} · ${activeCookbook.id}@${activeCookbook.version} verrouillée`
        : `${activeCookbook.display_name} · verrouillée à la création du Plan`
      : "Cookbook indisponible";
    if (activeCookbook?.profile) elements.activeCookbook.textContent = `${activeCookbook.display_name} (${activeCookbook.version})`
      + (compositionReference ? " \u00b7 Pour changer de parcours ou d\u2019intention, utilisez Repartir de ce run." : " \u00b7 Recette fix\u00e9e \u00e0 la cr\u00e9ation du run.");
    elements.empty.hidden = Boolean(session);
    elements.editor.hidden = !session;
    renderSetupPreview();
    const needsConfiguration = Boolean(session && state.cookbook?.profile && !state.composition);
    elements.start.textContent = needsConfiguration ? "Reprendre la pr\u00e9paration du run" : state.forkSource ? "Cr\u00e9er le nouveau parcours" : "Cr\u00e9er le parcours";
    elements.start.disabled = locked || Boolean(state.openingSessionId)
      || (Boolean(session) && !needsConfiguration) || Boolean(setupValidationError());
    elements.imageInput.disabled = locked || Boolean(session) || Boolean(state.forkSource);
    elements.lastImageInput.disabled = locked || Boolean(session) || Boolean(state.forkSource);
    elements.removeFirstImage.hidden = !state.firstFile || Boolean(session) || Boolean(state.forkSource);
    elements.removeLastImage.hidden = !state.lastFile || Boolean(session) || Boolean(state.forkSource);
    elements.removeFirstImage.disabled = locked;
    elements.removeLastImage.disabled = locked;
    elements.inputMode.textContent = session
      ? `Mode verrouillé : ${sessionInputModeLabel(session)}`
      : currentInputModeLabel();
    elements.model.disabled = locked || Boolean(session);
    window.PanelForgeModelPicker.setDisabled(elements.model, elements.model.disabled);
    writerModels.draw();
    elements.refreshModels.disabled = locked;
    elements.refreshSessions.disabled = locked;
    elements.sessionList.querySelectorAll(".session-link").forEach((button) => { button.disabled = locked; });
    const animalRecipe = animalInterviewSelected(activeCookbook || state.cookbook);
    elements.intentionTitle.textContent = animalRecipe ? "Interview guidée" : "Intention simple";
    elements.standardIntention.hidden = animalRecipe;
    elements.animalFields.hidden = !animalRecipe;
    renderAnimalInterviewDurationGuide(animalRecipe);
    elements.intention.disabled = locked || animalRecipe || intentLocked;
    for (const control of [elements.animal, elements.environment, elements.dialogueLanguage, elements.duration, elements.partialScript, elements.postAction]) {
      control.disabled = locked || !animalRecipe;
    }
    for (const control of [elements.creativeSceneLife, elements.creativeCamera, elements.creativeExtraMotion, elements.creativeDialogue]) {
      control.disabled = locked || intentLocked;
    }
    elements.showReasoning.disabled = locked;
    elements.newSession.hidden = !session && !state.forkSource;
    elements.newSession.disabled = locked || Boolean(state.openingSessionId);
    elements.forkSession.hidden = !session;
    elements.forkSession.disabled = locked || Boolean(state.openingSessionId) || !session;
    if (!session) {
      elements.promptReferences.hidden = true;
      chineseVariant.draw({ locked, ready: false });
      emitH3RenderContext(null, null, false);
      return;
    }

    renderDock();
    const brief = preparationInput();
    const briefInputsCurrent = !brief || (
      (brief.source_text || "").trim() === currentSourceText()
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
    const planState = renderDocument(
      elements.plan,
      plan,
      briefState.ready,
      briefState.draft ? "Brief modifié" : "Brief requis",
    );
    if (preparationSteps() > 1) renderArbitrations(plan, planState, briefState.ready);
    const promptState = renderDocument(
      elements.prompt,
      prompt,
      preparationSteps() === 1 ? briefState.ready : planState.ready,
      planState.draft ? "Plan modifié" : "Plan requis",
    );
    elements.sessionTitle.textContent = sessionInputModeLabel(session);
    const recipeLabel = compositionReference
      ? `${compositionReference.id}@${compositionReference.version}`
      : state.cookbook ? `${state.cookbook.id}@${state.cookbook.version} · à verrouiller` : "non sélectionnée";
    const audacityLabel = brief
      ? brief.creative_audacity ?? 0
      : Number(elements.creativeAudacity.value);
    const briefLabel = combat ? `${shortRoute ? "Intention" : "Brief"} Combat ${session.preparation.version} \u00b7 audace ${audacityLabel}/3`
      : shortRoute ? `Intention directe · audace ${audacityLabel}/3` : session.brief_variant
      ? `Brief : direction créative ${session.brief_variant.version} · audace ${audacityLabel}/3`
      : `Brief : standard ${session.profile.version}`;
    elements.sessionConfig.textContent = `Modèle : ${session.model_id} · ${briefLabel} · Recette : ${recipeLabel}`;
    elements.progress.textContent = !briefState.ready ? (shortRoute ? "Intention requise" : "Brief requis")
      : preparationSteps() > 1 && !planState.ready ? "Plan requis" : !promptState.ready ? "Prompt requis" : "Parcours validé";
    elements.progress.className = `run-status ${promptState.ready ? "success" : "active"}`;
    setChip(elements.chips.brief, briefState.ready, !briefState.ready);
    setChip(elements.chips.plan, planState.ready, briefState.ready && !planState.ready);
    setChip(elements.chips.prompt, promptState.ready, (preparationSteps() === 1 ? briefState.ready : planState.ready) && !promptState.ready);
    elements.copyPrompt.disabled = locked || !promptState.ready;
    renderPromptReferences(prompt);
    chineseVariant.draw({ locked, ready: promptState.ready });
    emitH3RenderContext(
      session,
      prompt,
      Boolean(generatedDocument(prompt) && !promptState.draft),
    );
  }

  function emitH3RenderContext(session, prompt, ready) {
    const selection = chineseVariant.selection();
    window.dispatchEvent(new CustomEvent("panelforge:h3-base-context", {
      detail: {
        session_id: session ? session.id : null,
        prompt_revision_id: prompt ? selection.renderRevisionId : null,
        prompt_language: selection.language,
        prompt_variant_id: selection.variantId,
        ready: Boolean(ready),
      },
    }));
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
    elements.brief.generate.disabled = locked || Boolean(setupValidationError());
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
      : { source_text: currentSourceText(), ...creativePayload() };
    const completed = await streamResult(
      `/api/prompt-lab/sessions/${state.session.id}/brief/${revision ? "revise" : "structure"}/stream`,
      payload,
      elements.brief,
      (event) => { if (event.session) state.session = event.session; },
      revision ? "Brief révisé à partir des entrées." : "Brief H3 Base généré.",
      { notifyOutcome: !state.quickRunning },
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
    if (state.composition) {
      await writerModels.save();
      return;
    }
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
          writer_model_id: writerModels.value(),
          preparation_intent: preparationSteps() < 3 ? { source_text: currentSourceText(), ...creativePayload() } : null,
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
        { notifyOutcome: !state.quickRunning },
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
    if (state.quickRunning || state.writerSaving) return;
    state.openRequestId += 1;
    state.openingSessionId = null;
    const selectedCookbook = directCookbooks().find(
      (item) => cookbookKey(item) === elements.cookbook.value,
    );
    if (selectedCookbook) state.cookbook = selectedCookbook;
    state.forkSource = null;
    combatControls.restore(null);
    cinematicControls.restore(null);
    sensualControls.restore(null);
    writerModels.resetDefault();
    state.session = null;
    state.composition = null;
    state.quickRecord = null;
    resetArbitrations();
    showReferencePreview("first", null, "");
    showReferencePreview("last", null, "");
    elements.intention.value = "";
    resetAnimalInterviewInputs();
    setCreativeAxes(null, 0);
    setCreativeAudacity(2);
    elements.creativeDirection.checked = false;
    elements.quickMode.checked = true;
    clearStageDrafts();
    showSetupMessage("");
    render();
  }

  async function prefillFirstFrame({ assetId, label, sourceSessionId = null, preparation = null, combatSettings = null, cinematicSettings = null, sensualSettings = null }) {
    if (!state.spec || !state.cookbook) throw new Error("H3 Base est encore en cours de chargement.");
    if (interactionLocked()) throw new Error("Une préparation H3 Base est en cours. Réessayez après sa fin.");
    if (typeof assetId !== "string" || !assetId) throw new Error("La frame de fin est indisponible.");
    const requestId = state.openRequestId;
    setBusy(true);
    try {
      let sourceCookbook = null;
      let sourceWriterModel = null;
      if (sourceSessionId) {
        const payload = await core.request(`/api/prompt-lab/sessions/${encodeURIComponent(sourceSessionId)}/composition`);
        sourceWriterModel = payload.composition?.writer_model_id || null;
        const reference = payload.composition?.cookbook;
        sourceCookbook = directCookbooks().find((item) => cookbookKey(item) === cookbookKey(reference)) || null;
        const origin = state.cookbooks.find((item) => cookbookKey(item) === cookbookKey(reference));
        const pinnedPreparation = preparation || origin?.preparation;
        const fromRef2V = reference?.id?.startsWith("minimax.h3.ref2v.");
        if (pinnedPreparation?.family === "combat" && !sourceCookbook && fromRef2V) {
          sourceCookbook = directCookbooks().find((item) => item.preparation?.family === "combat"
            && item.preparation.version === pinnedPreparation.version
            && sequenceKind(item) === "mono" && item.preparation_steps === (origin?.preparation_steps ?? 3));
          if (!sourceCookbook) throw new Error("La version Combat de ce rendu est indisponible. Le parcours courant est conservé.");
        }
        if (pinnedPreparation?.family === "sensual" && !sourceCookbook && fromRef2V) {
          sourceCookbook = directCookbooks().find((item) => window.PanelForgeSensualControls.isSensual(item)
            && sequenceKind(item) === "mono" && item.preparation_steps === 2);
          if (!sourceCookbook) throw new Error("La préparation Sensuelle exacte est indisponible pour cette reprise.");
        }
        if (!sourceCookbook && fromRef2V && pinnedPreparation?.family === "classic") {
          sourceCookbook = directCookbooks().find((item) => preparationFamily(item) === "classic"
            && (item.preparation?.version || null) === (pinnedPreparation?.version || null)
            && sequenceKind(item) === "mono" && item.preparation_steps === (origin?.preparation_steps ?? 3)
            && core.recipeTier(cookbookKey(item)) === "standard");
          if (!sourceCookbook) throw new Error("La préparation Classique de destination est indisponible.");
        }
        if (!sourceCookbook && reference?.id?.startsWith("minimax.h3.fl2va.combat")) {
          throw new Error("La recette Combat exacte de ce rendu est indisponible. Le parcours courant est conservé.");
        }
        if (reference?.id?.startsWith(multishotCookbookId) && !sourceCookbook) {
          throw new Error("La recette multi-plan de ce rendu est indisponible. Le parcours courant est conservé.");
        }
      }
      if (preparation?.family === "combat" && (!sourceCookbook || sourceCookbook.preparation?.family !== "combat"
        || sourceCookbook.preparation.version !== preparation.version)) {
        throw new Error("La reprise doit conserver la version Combat du rendu.");
      }
      if (preparation?.family === "classic" && preparation.version === "1.0.0" && !window.PanelForgeClassicCinematicControls.isCinematic(sourceCookbook)) {
        throw new Error("La recette Classique Mise en scène exacte est indisponible pour cette reprise.");
      }
      if (preparation?.family === "sensual" && !window.PanelForgeSensualControls.isSensual(sourceCookbook)) {
        throw new Error("La reprise doit conserver la préparation Sensuelle 1.0.");
      }
      const response = await fetch(`/api/assets/${encodeURIComponent(assetId)}/content`);
      if (!response.ok) throw new Error("Impossible de charger la frame de fin.");
      const blob = await response.blob();
      if (!blob.size || !blob.type.startsWith("image/")) throw new Error("La frame de fin n'est pas une image utilisable.");
      if (requestId !== state.openRequestId) throw new Error("Le parcours H3 Base a changé pendant le chargement. Réessayez.");
      const extension = blob.type === "image/jpeg" ? "jpg" : blob.type === "image/webp" ? "webp" : "png";
      const file = new File([blob], `${label || "Dernière frame"}.${extension}`, { type: blob.type });
      // Only replace the setup after the saved image has loaded successfully.
      resetSession();
      if (sourceCookbook) {
        state.cookbook = sourceCookbook;
        if (sourceCookbook.supports_writer_model) writerModels.restore(sourceWriterModel);
      } else if (state.cookbook?.id !== monoCookbookId && !state.cookbook?.profile) {
        state.cookbook = directCookbooks().find((item) => cookbookKey(item) === preferredCookbookKey);
      }
      if (["1.1.0", "1.1.1", "1.2.0", "1.3.0"].includes(preparation?.version)) combatControls.restore(combatSettings);
      if (preparation?.family === "classic" && preparation.version === "1.0.0") cinematicControls.restore(cinematicSettings);
      if (preparation?.family === "sensual") sensualControls.restore(sensualSettings);
      setSelectedFile("first", file);
      showSetupMessage("Dernière frame sélectionnée comme première image. Décrivez la suite pour créer le nouveau parcours.");
      window.PanelForgeLabNavigation?.switchView("i2v-direct");
      elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
    } finally {
      setBusy(false);
    }
    elements.intention.focus({ preventScroll: true });
  }

  function prefillAnalysis({ intention, firstFile = null, lastFile = null }) {
    if (!state.spec || !state.cookbook) throw new Error("H3 Base est encore en cours de chargement.");
    if (interactionLocked()) throw new Error("Une préparation H3 Base est en cours. L’analyse reste disponible pour le transfert.");
    if (!intention?.trim()) throw new Error("L’intention est vide.");
    if (!state.session && (elements.intention.value.trim() || state.firstFile || state.lastFile || state.forkSource)) {
      throw new Error("Un brouillon H3 Base est déjà ouvert. Conservez-le ou ouvrez un nouvel atelier avant de transférer l’analyse.");
    }
    resetSession();
    if (firstFile) setSelectedFile("first", firstFile);
    if (lastFile) setSelectedFile("last", lastFile);
    elements.intention.value = intention.trim(); render();
    showSetupMessage("Intention issue de l’analyse. Vérifiez les références et choisissez votre parcours habituel.");
    window.PanelForgeLabNavigation?.switchView("i2v-direct");
    elements.form.scrollIntoView({ behavior: "smooth", block: "start" });
    elements.intention.focus({ preventScroll: true });
  }

  window.PanelForgeH3Base = Object.freeze({ prefillFirstFrame, prefillAnalysis });

  elements.imageInput.addEventListener("change", () => selectFile("first"));
  elements.lastImageInput.addEventListener("change", () => selectFile("last"));
  elements.removeFirstImage.addEventListener("click", () => removeSelectedFile("first"));
  elements.removeLastImage.addEventListener("click", () => removeSelectedFile("last"));
  elements.form.addEventListener("submit", createSession);
  elements.refreshModels.addEventListener("click", refreshModels);
  document.querySelectorAll('[data-lab-view="i2v-direct"]').forEach((button) => {
    button.addEventListener("click", refreshModels);
  });
  elements.preparationFamily.addEventListener("change", changePreparationFamily);
  elements.refreshSessions.addEventListener("click", () => loadSessions().catch((error) => showSetupMessage(error.message)));
  elements.sequenceKind.addEventListener("change", changeSequenceKind);
  elements.cookbook.addEventListener("change", () => {
    const next = directCookbooks().find(
      (item) => cookbookKey(item) === elements.cookbook.value,
    ) || null;
    const expected = profileReference(next);
    if (state.session && (next?.profile || state.cookbook?.profile || expected.version === experimentalMonoProfile.version || state.session.profile?.version === experimentalMonoProfile.version)
      && (state.session.profile?.id !== expected.id || state.session.profile?.version !== expected.version)) {
      showSetupMessage("Pour changer de recette expérimentale, utilisez Repartir de ce run : le Brief et le Plan doivent garder la même version.");
      return render();
    }
    state.cookbook = next;
    render();
  });
  elements.intention.addEventListener("input", render);
  for (const control of [elements.animal, elements.environment, elements.duration, elements.partialScript, elements.postAction]) {
    control.addEventListener("input", render);
  }
  elements.dialogueLanguage.addEventListener("change", render);
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
        ? `Direction créative ${state.session.brief_variant.version} activée pour le Brief.`
        : `Brief standard ${state.session.profile.version} activé.`;
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

  updateCreativeAxes();
  setCreativeAudacity(2);
  render();
  initialize();
})();
