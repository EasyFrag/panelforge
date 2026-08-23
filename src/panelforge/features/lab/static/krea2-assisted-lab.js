(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
  const activeStatuses = new Set(["queued", "running", "cancel_pending"]);
  const elements = {
    workspace: $("krea2-assisted-lab-workspace"),
    newForm: $("krea2-assisted-new-form"),
    name: $("krea2-assisted-name"),
    intention: $("krea2-assisted-intention"),
    reference: $("krea2-assisted-reference"),
    llm: $("krea2-assisted-llm"),
    create: $("krea2-assisted-create"),
    newMessage: $("krea2-assisted-new-message"),
    refresh: $("krea2-assisted-refresh"),
    history: $("krea2-assisted-history"),
    historyEmpty: $("krea2-assisted-history-empty"),
    editor: $("krea2-assisted-editor"),
    title: $("krea2-assisted-title"),
    status: $("krea2-assisted-status"),
    warnings: $("krea2-assisted-warnings"),
    conversation: $("krea2-assisted-conversation"),
    message: $("krea2-assisted-message"),
    guidanceFile: $("krea2-assisted-guidance-file"),
    guidancePreview: $("krea2-assisted-guidance-preview"),
    guidanceImage: $("krea2-assisted-guidance-image"),
    guidanceName: $("krea2-assisted-guidance-name"),
    guidanceRemove: $("krea2-assisted-guidance-remove"),
    chat: $("krea2-assisted-chat"),
    recipeChat: $("krea2-assisted-recipe-chat"),
    showReasoning: $("krea2-assisted-show-reasoning"),
    promptLanguage: $("krea2-assisted-prompt-language"),
    reasoning: $("krea2-assisted-reasoning"),
    reasoningLabel: $("krea2-assisted-reasoning-label"),
    reasoningContent: $("krea2-assisted-reasoning-content"),
    reasoningEmpty: $("krea2-assisted-reasoning-empty"),
    prompt: $("krea2-assisted-prompt"),
    copyPrompt: $("krea2-assisted-copy-prompt"),
    model: $("krea2-assisted-model"),
    ratio: $("krea2-assisted-ratio"),
    megapixels: $("krea2-assisted-megapixels"),
    seed: $("krea2-assisted-seed"),
    loras: $("krea2-assisted-loras"),
    catalogManager: $("krea2-assisted-catalog-manager"),
    render: $("krea2-assisted-render"),
    cancel: $("krea2-assisted-cancel"),
    messageState: $("krea2-assisted-message-state"),
    recipePanel: $("krea2-assisted-recipe-panel"),
    recipeDraft: $("krea2-assisted-recipe-draft"),
    saveDraft: $("krea2-assisted-save-draft"),
    publishRecipe: $("krea2-assisted-publish-recipe"),
    recipeMessage: $("krea2-assisted-recipe-message"),
    gallery: $("krea2-assisted-gallery"),
    lightbox: $("krea2-assisted-lightbox"),
    lightboxTitle: $("krea2-assisted-lightbox-title"),
    lightboxImage: $("krea2-assisted-lightbox-image"),
    lightboxClose: $("krea2-assisted-lightbox-close"),
  };
  if (!elements.workspace) return;

  const resourceUi = window.PanelForgeKrea2ResourceUi;
  const core = window.PanelForgePromptLab;
  const state = {
    initialized: false,
    initializing: null,
    spec: null,
    projects: [],
    project: null,
    loraSlots: Array.from({ length: 4 }, () => ({ name: "", strength: 0 })),
    busy: false,
    pollTimer: null,
    draftSnapshot: "",
    guidanceFile: null,
    guidanceAsset: null,
    guidanceObjectUrl: null,
  };
  const reasoningTrace = core && typeof core.createReasoningTrace === "function"
    ? core.createReasoningTrace({
      toggle: elements.showReasoning,
      panel: elements.reasoning,
      label: elements.reasoningLabel,
      output: elements.reasoningContent,
      empty: elements.reasoningEmpty,
    })
    : Object.freeze({ begin: () => {}, handle: () => {}, finish: () => {}, reset: () => {}, streamUrl: (url) => url });

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
    }
    return payload;
  }

  function setBusy(value) {
    state.busy = value;
    elements.create.disabled = value || !state.spec;
    elements.chat.disabled = value || !state.project;
    elements.recipeChat.disabled = value || !state.project;
    elements.promptLanguage.disabled = value || !state.project;
    elements.guidanceFile.disabled = value || !state.project;
    elements.guidanceRemove.disabled = value || !state.project;
    elements.render.disabled = value || !state.project;
    elements.saveDraft.disabled = value || !state.project;
    elements.publishRecipe.disabled = value || !state.project;
    renderStatus();
  }

  function setNewMessage(message = "", error = true) {
    elements.newMessage.textContent = message;
    elements.newMessage.hidden = !message;
    elements.newMessage.classList.toggle("error", error);
    elements.newMessage.classList.toggle("message", !error);
  }

  function setMessage(message = "", error = false) {
    elements.messageState.textContent = message;
    elements.messageState.classList.toggle("error", error);
  }

  function preferredLlm(models) {
    return models.find((item) => /qwen3[._-]?8.*27b/i.test(item.id))
      || models.find((item) => /qwen.*27b/i.test(item.id))
      || models[0]
      || null;
  }

  function preferredRenderModel(models) {
    return models.find((item) => /krea2gptgrandpussytruth/i.test(item.comfy_name))
      || models.find((item) => /krea2_turbo_bf16/i.test(item.comfy_name))
      || models[0]
      || null;
  }

  function fillOptions() {
    const previousLlm = elements.llm.value;
    elements.llm.replaceChildren();
    (state.spec.llm_models || []).forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.id;
      elements.llm.append(option);
    });
    const preferred = preferredLlm(state.spec.llm_models || []);
    elements.llm.value = previousLlm && [...elements.llm.options].some((option) => option.value === previousLlm)
      ? previousLlm
      : (preferred ? preferred.id : "");

    const previousModel = elements.model.value;
    resourceUi.appendGroupedOptions(elements.model, state.spec.render_models || [], resourceUi.modelGroups);
    const renderDefault = preferredRenderModel(state.spec.render_models || []);
    elements.model.value = previousModel && [...elements.model.options].some((option) => option.value === previousModel)
      ? previousModel
      : (renderDefault ? renderDefault.comfy_name : "");

    const previousRatio = elements.ratio.value;
    elements.ratio.replaceChildren();
    (state.spec.aspect_ratios || []).forEach((ratio) => {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio;
      elements.ratio.append(option);
    });
    elements.ratio.value = previousRatio || state.spec.defaults.aspect_ratio;
    if (!elements.megapixels.value) elements.megapixels.value = String(state.spec.defaults.megapixels);
    renderLoraStack();
    renderCatalogManager();
  }

  function ensureMissingOption(select, value) {
    if (!value || [...select.options].some((option) => option.value === value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${value} · absent`;
    select.prepend(option);
  }

  function renderLoraStack() {
    elements.loras.replaceChildren();
    state.loraSlots.forEach((slot, index) => {
      const row = document.createElement("div");
      row.className = "krea2-lora-row";
      const select = document.createElement("select");
      select.setAttribute("aria-label", `LoRA ${index + 1}`);
      resourceUi.appendGroupedOptions(select, state.spec ? state.spec.loras || [] : [], resourceUi.loraGroups, { includeEmpty: true });
      ensureMissingOption(select, slot.name);
      select.value = slot.name;
      const strength = document.createElement("input");
      strength.type = "number";
      strength.min = "-20";
      strength.max = "20";
      strength.step = "0.05";
      strength.value = String(slot.strength);
      strength.setAttribute("aria-label", `Force LoRA ${index + 1}`);
      select.addEventListener("change", () => {
        slot.name = select.value;
        if (!slot.name) slot.strength = 0;
        renderLoraStack();
      });
      strength.addEventListener("change", () => { slot.strength = Number(strength.value) || 0; });
      row.append(select, strength);
      elements.loras.append(row);
    });
  }

  async function updatePreference(resource, values) {
    try {
      await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadSpec(true);
    } catch (error) { setMessage(error.message, true); }
  }

  function renderCatalogManager() {
    resourceUi.renderCatalogManager(elements.catalogManager, {
      models: state.spec ? state.spec.render_models || [] : [],
      loras: state.spec ? state.spec.loras || [] : [],
      updatePreference,
    });
  }

  function selectedLoras() {
    return state.loraSlots
      .filter((slot) => slot.name)
      .map((slot) => ({ name: slot.name, strength: Number(slot.strength) || 0 }));
  }

  function resourceFilename(value) {
    const normalized = String(value || "").replaceAll("\\", "/");
    return (normalized.split("/").at(-1) || normalized).replace(/\.(safetensors|ckpt|pt)$/i, "");
  }

  function compactResourceName(value, maximum = 30) {
    const label = resourceFilename(value);
    return label.length > maximum ? `${label.slice(0, maximum - 1)}…` : label;
  }

  function strengthLabel(value) {
    const number = Number(value);
    return Number.isFinite(number)
      ? number.toLocaleString("fr-FR", { maximumFractionDigits: 3 })
      : String(value);
  }

  function loadAttemptSettings(attempt) {
    if (!attempt) return;
    elements.prompt.value = attempt.prompt;
    elements.model.value = attempt.settings.model_id;
    ensureMissingOption(elements.model, attempt.settings.model_id);
    elements.model.value = attempt.settings.model_id;
    elements.ratio.value = attempt.settings.aspect_ratio;
    elements.megapixels.value = String(attempt.settings.megapixels);
    elements.seed.value = attempt.seed || "";
    state.loraSlots = Array.from({ length: 4 }, (_, index) => {
      const value = (attempt.settings.loras || [])[index];
      return value ? { name: value.name, strength: value.strength } : { name: "", strength: 0 };
    });
    renderLoraStack();
  }

  function draftText(draft) {
    return draft ? JSON.stringify(draft, null, 2) : "";
  }

  function renderStatus() {
    const project = state.project;
    const active = project && (project.attempts || []).find((attempt) => activeStatuses.has(attempt.status));
    elements.status.textContent = state.busy ? "● Traitement…" : active ? `● ${active.status}` : "● Prêt";
    elements.cancel.disabled = !active || state.busy;
  }

  function clearGuidance() {
    if (state.guidanceObjectUrl) URL.revokeObjectURL(state.guidanceObjectUrl);
    state.guidanceFile = null;
    state.guidanceAsset = null;
    state.guidanceObjectUrl = null;
    elements.guidanceFile.value = "";
    renderGuidanceCompose();
  }

  function renderGuidanceCompose() {
    const guidance = state.guidanceAsset;
    const source = state.guidanceObjectUrl || (guidance && guidance.url);
    const name = state.guidanceFile?.name || guidance?.filename || "";
    elements.guidancePreview.hidden = !source;
    if (source) {
      elements.guidanceImage.src = source;
      elements.guidanceName.textContent = name;
      elements.guidanceName.title = name;
    } else {
      elements.guidanceImage.removeAttribute("src");
      elements.guidanceName.textContent = "";
    }
  }

  function selectGuidanceFile() {
    const file = elements.guidanceFile.files[0];
    if (!file) return;
    if (state.guidanceObjectUrl) URL.revokeObjectURL(state.guidanceObjectUrl);
    state.guidanceFile = file;
    state.guidanceAsset = null;
    state.guidanceObjectUrl = URL.createObjectURL(file);
    renderGuidanceCompose();
  }

  function reuseGuidance(turn) {
    if (state.busy || !turn.guidance_asset_id || !turn.guidance_url) return;
    clearGuidance();
    state.guidanceAsset = {
      asset_id: turn.guidance_asset_id,
      filename: turn.guidance_filename || "guidance-image",
      url: turn.guidance_url,
    };
    renderGuidanceCompose();
    elements.message.focus();
  }

  async function resolveGuidance() {
    if (state.guidanceAsset) return state.guidanceAsset;
    if (!state.guidanceFile) return null;
    const data = new FormData();
    data.set("image", state.guidanceFile);
    const payload = await request(
      `/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/guidance-images`,
      { method: "POST", body: data },
    );
    return payload.guidance;
  }

  function renderConversation() {
    elements.conversation.replaceChildren();
    const turns = state.project ? state.project.turns || [] : [];
    if (!turns.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Le premier échange apparaîtra ici.";
      elements.conversation.append(empty);
      return;
    }
    turns.forEach((turn) => {
      const article = document.createElement("article");
      article.className = `krea2-assisted-turn ${turn.role} ${turn.mode}`;
      const label = document.createElement("small");
      label.textContent = `${turn.role === "user" ? "Vous" : "Assistant"} · ${turn.mode === "recipe" ? "recette" : "création"}`;
      const content = document.createElement("p");
      content.textContent = turn.content;
      article.append(label, content);
      if (turn.guidance_url) {
        const guidance = document.createElement("div");
        guidance.className = "krea2-assisted-turn-guidance";
        const image = document.createElement("img");
        image.src = turn.guidance_url;
        image.alt = turn.guidance_filename || "Image d’appoint";
        image.loading = "lazy";
        image.addEventListener("click", () => openLightbox(turn.guidance_url, image.alt));
        const copy = document.createElement("span");
        const name = document.createElement("b");
        name.textContent = turn.guidance_filename || "Image d’appoint";
        const note = document.createElement("small");
        note.textContent = "Image d’appoint de cet échange";
        copy.append(name, note);
        const reuse = document.createElement("button");
        reuse.type = "button";
        reuse.textContent = "Réutiliser";
        reuse.addEventListener("click", () => reuseGuidance(turn));
        guidance.append(image, copy, reuse);
        article.append(guidance);
      }
      if (turn.questions && turn.questions.length) {
        const list = document.createElement("ol");
        turn.questions.forEach((question) => { const item = document.createElement("li"); item.textContent = question; list.append(item); });
        article.append(list);
      }
      if (turn.recommendations && turn.recommendations.length) {
        const notes = document.createElement("small");
        notes.textContent = turn.recommendations.join(" · ");
        article.append(notes);
      }
      elements.conversation.append(article);
    });
    elements.conversation.scrollTop = elements.conversation.scrollHeight;
  }

  function openLightbox(url, title) {
    elements.lightboxTitle.textContent = title;
    elements.lightboxImage.src = url;
    elements.lightboxImage.alt = title;
    elements.lightbox.showModal();
  }

  function imageFigure(url, caption, className = "") {
    const figure = document.createElement("figure");
    figure.className = className;
    const figcaption = document.createElement("figcaption");
    figcaption.textContent = caption;
    const image = document.createElement("img");
    image.src = url;
    image.alt = caption;
    image.loading = "lazy";
    image.tabIndex = 0;
    image.addEventListener("click", () => openLightbox(url, caption));
    image.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openLightbox(url, caption); }
    });
    figure.append(figcaption, image);
    return figure;
  }

  function renderGallery() {
    elements.gallery.replaceChildren();
    const project = state.project;
    if (!project) return;
    if (project.reference_url) {
      elements.gallery.append(imageFigure(`${project.reference_url}?v=${encodeURIComponent(project.reference_asset_id)}`, "Référence LLM · non envoyée à ComfyUI", "reference"));
    }
    [...(project.attempts || [])].reverse().forEach((attempt) => {
      const card = document.createElement("article");
      card.className = `krea2-assisted-attempt ${attempt.accepted ? "accepted" : ""} ${project.feedback_attempt_id === attempt.attempt_id ? "feedback" : ""}`;
      if (attempt.output_url) {
        card.append(imageFigure(`${attempt.output_url}?v=${encodeURIComponent(attempt.output_asset_id)}`, `Essai ${attempt.index}`));
      } else {
        const pending = document.createElement("div");
        pending.className = "krea2-assisted-attempt-placeholder";
        pending.textContent = activeStatuses.has(attempt.status) ? "Rendu ComfyUI…" : attempt.error || attempt.status;
        card.append(pending);
      }
      const settings = attempt.settings || {};
      const resolution = settings.resolution || {};
      const resolutionLabel = resolution.width && resolution.height
        ? `${resolution.width}×${resolution.height}`
        : settings.aspect_ratio.split(" ")[0];
      const renderMeta = document.createElement("small");
      renderMeta.textContent = `Modèle · ${compactResourceName(settings.model_id)} · ${resolutionLabel} · ${settings.megapixels} MP`;
      renderMeta.title = `Checkpoint : ${settings.model_id}\nRésolution : ${resolutionLabel} · ${settings.aspect_ratio} · ${settings.megapixels} MP`;
      const loras = settings.loras || [];
      const loraSummary = loras.length
        ? loras.map((lora) => `${compactResourceName(lora.name, 22)} ×${strengthLabel(lora.strength)}`).join(" · ")
        : "aucune";
      const loraMeta = document.createElement("small");
      loraMeta.textContent = `LoRA · ${loraSummary}`;
      loraMeta.title = loras.length
        ? loras.map((lora) => `${lora.name} ×${strengthLabel(lora.strength)}`).join("\n")
        : "Aucune LoRA utilisée";
      const runMeta = document.createElement("small");
      runMeta.textContent = `${attempt.status} · ${settings.aspect_ratio.split(" ")[0]} · seed ${attempt.seed}`;
      card.append(renderMeta, loraMeta, runMeta);
      const actions = document.createElement("div");
      actions.className = "actions";
      const reuse = document.createElement("button");
      reuse.type = "button";
      reuse.textContent = "Reprendre réglages";
      reuse.title = "Reprendre le prompt et les réglages de cet essai";
      reuse.addEventListener("click", () => loadAttemptSettings(attempt));
      actions.append(reuse);
      if (attempt.status === "succeeded") {
        const feedbackSelected = project.feedback_attempt_id === attempt.attempt_id;
        const feedback = document.createElement("button");
        feedback.type = "button";
        feedback.textContent = feedbackSelected ? "Feedback ✓" : "Feedback";
        feedback.title = feedbackSelected ? "Retirer ce feedback" : "Utiliser comme feedback visuel";
        feedback.setAttribute("aria-pressed", String(feedbackSelected));
        feedback.addEventListener("click", () => selectFeedback(feedbackSelected ? null : attempt.attempt_id));
        const save = document.createElement("button");
        save.type = "button";
        save.textContent = attempt.accepted ? "Enregistrée ✓" : "Enregistrer";
        save.title = attempt.accepted ? "Image déjà enregistrée" : "Enregistrer cette image";
        save.addEventListener("click", () => saveImage(attempt.attempt_id));
        actions.append(feedback, save);
      }
      card.append(actions);
      elements.gallery.append(card);
    });
    if (!elements.gallery.children.length) {
      const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "Aucune image."; elements.gallery.append(empty);
    }
  }

  function renderProject(project, { preservePrompt = false } = {}) {
    state.project = project;
    elements.editor.hidden = false;
    elements.title.textContent = project.name;
    elements.promptLanguage.value = project.prompt_language || "en";
    if (!preservePrompt || !elements.prompt.value.trim()) elements.prompt.value = project.current_prompt || "";
    elements.warnings.replaceChildren();
    (project.warnings || []).forEach((warning) => { const item = document.createElement("p"); item.textContent = warning; elements.warnings.append(item); });
    elements.warnings.hidden = !(project.warnings || []).length;
    renderConversation();
    const serialized = draftText(project.recipe_draft);
    if (!elements.recipeDraft.value.trim() || elements.recipeDraft.value === state.draftSnapshot || serialized !== state.draftSnapshot) {
      elements.recipeDraft.value = serialized;
      state.draftSnapshot = serialized;
    }
    if (project.recipe_draft) elements.recipePanel.open = true;
    if (project.published_recipe) {
      elements.recipeMessage.textContent = `Recette publiée : ${project.published_recipe.recipe_id}@${project.published_recipe.version}`;
    } else if (project.export && project.export.error) {
      setMessage(`Image validée, mais export en échec : ${project.export.error}`, true);
    }
    renderGallery();
    renderStatus();
  }

  function renderHistory() {
    elements.history.replaceChildren();
    elements.historyEmpty.hidden = state.projects.length > 0;
    state.projects.forEach((project) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "krea2-assisted-history-item";
      const title = document.createElement("b"); title.textContent = project.name;
      const meta = document.createElement("small");
      const outputs = (project.attempts || []).filter((attempt) => attempt.status === "succeeded").length;
      meta.textContent = `${outputs} rendu(s) · ${(project.turns || []).length} message(s)`;
      button.append(title, meta);
      const latest = [...(project.attempts || [])].reverse().find((attempt) => attempt.output_url);
      if (latest) { const image = document.createElement("img"); image.src = latest.output_url; image.alt = ""; image.loading = "lazy"; button.append(image); }
      button.addEventListener("click", () => openProject(project.project_id));
      item.append(button);
      elements.history.append(item);
    });
  }

  async function loadSpec(preserve = false) {
    const previousModel = preserve ? elements.model.value : "";
    const previousSlots = state.loraSlots.map((slot) => ({ ...slot }));
    state.spec = await request("/api/image-lab/krea2-assisted/spec");
    fillOptions();
    if (preserve) {
      ensureMissingOption(elements.model, previousModel);
      if (previousModel) elements.model.value = previousModel;
      state.loraSlots = previousSlots;
      renderLoraStack();
    }
  }

  async function loadHistory() {
    const payload = await request("/api/image-lab/krea2-assisted/projects?limit=30");
    state.projects = payload.projects || [];
    renderHistory();
  }

  async function openProject(projectId) {
    if (state.busy) return;
    stopPolling();
    clearGuidance();
    setBusy(true);
    setMessage();
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(projectId)}`);
      renderProject(payload.project);
      const last = [...(payload.project.attempts || [])].reverse()[0];
      if (last) loadAttemptSettings(last);
      else if (payload.project.current_prompt) elements.prompt.value = payload.project.current_prompt;
      if ((payload.project.attempts || []).some((attempt) => activeStatuses.has(attempt.status))) schedulePoll();
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event) {
    event.preventDefault();
    if (state.busy) return;
    setBusy(true);
    setNewMessage();
    try {
      const data = new FormData();
      data.set("name", elements.name.value.trim());
      data.set("intention", elements.intention.value.trim());
      data.set("model_id", elements.llm.value);
      if (elements.reference.files[0]) data.set("reference", elements.reference.files[0]);
      const payload = await request("/api/image-lab/krea2-assisted/projects", { method: "POST", body: data });
      clearGuidance();
      renderProject(payload.project);
      await loadHistory();
      await sendChat("creation", payload.project.intention);
    } catch (error) { setNewMessage(error.message); }
    finally { setBusy(false); }
  }

  async function sendChat(mode, explicitMessage = null) {
    if (!state.project) return;
    const message = (explicitMessage || elements.message.value).trim()
      || (mode === "recipe" ? "Aide-moi à transformer le résultat sélectionné en recette Batch réutilisable. Pose les questions encore nécessaires." : "Affinons le prompt actuel.");
    setBusy(true);
    setMessage(mode === "recipe" ? "Préparation de la recette…" : "Le modèle affine le prompt…");
    reasoningTrace.begin(mode === "recipe" ? "Recette KREA2" : "Création KREA2");
    let streamError = "";
    try {
      const guidance = await resolveGuidance();
      await core.streamRequest(
        reasoningTrace.streamUrl(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/chat/stream`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({
            message,
            mode,
            feedback_attempt_id: state.project.feedback_attempt_id,
            prompt_language: elements.promptLanguage.value,
            guidance_asset_id: guidance?.asset_id || null,
            guidance_filename: guidance?.filename || null,
          }),
        },
        (event) => {
          reasoningTrace.handle(event);
          if (event.error) streamError = event.error;
          if (event.project) renderProject(event.project, { preservePrompt: false });
        },
        { completionTone: false },
      );
      clearGuidance();
      if (streamError) throw new Error(streamError);
      elements.message.value = "";
      setMessage(mode === "recipe" ? "Échange recette enregistré." : "Prompt mis à jour.");
      await loadHistory();
    } catch (error) { setMessage(error.message, true); }
    finally { reasoningTrace.finish(); setBusy(false); }
  }

  async function renderAttempt() {
    if (!state.project || state.busy) return;
    const prompt = elements.prompt.value.trim();
    if (!prompt) { setMessage("Préparez ou écrivez d’abord un prompt.", true); return; }
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          model_id: elements.model.value,
          aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value),
          seed: elements.seed.value.trim() || null,
          loras: selectedLoras(),
        }),
      });
      const attempt = payload.project.attempts.at(-1);
      renderProject(payload.project, { preservePrompt: true });
      const started = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts/${encodeURIComponent(attempt.attempt_id)}/start`, { method: "POST" });
      renderProject(started.project, { preservePrompt: true });
      setMessage("Rendu KREA2 lancé.");
      schedulePoll();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  function stopPolling() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function schedulePoll() {
    stopPolling();
    state.pollTimer = window.setTimeout(poll, 1000);
  }

  async function poll() {
    if (!state.project) return;
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}`);
      renderProject(payload.project, { preservePrompt: true });
      if ((payload.project.attempts || []).some((attempt) => activeStatuses.has(attempt.status))) {
        schedulePoll();
      } else {
        stopPolling();
        const last = (payload.project.attempts || []).at(-1);
        setMessage(last && last.status === "succeeded" ? "Rendu terminé. Vous pouvez le sélectionner comme feedback ou l’enregistrer." : (last && last.error) || "Rendu terminé.", last && last.status === "failed");
        await loadHistory();
      }
    } catch (error) { setMessage(error.message, true); schedulePoll(); }
  }

  async function cancelAttempt() {
    const active = state.project && (state.project.attempts || []).find((attempt) => activeStatuses.has(attempt.status));
    if (!active || state.busy) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts/${encodeURIComponent(active.attempt_id)}/cancel`, { method: "POST" });
      renderProject(payload.project, { preservePrompt: true });
      if (terminalStatuses.has(payload.project.attempts.find((value) => value.attempt_id === active.attempt_id).status)) stopPolling();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function selectFeedback(attemptId) {
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ attempt_id: attemptId }),
      });
      renderProject(payload.project, { preservePrompt: true });
      setMessage(attemptId === null
        ? "Feedback visuel retiré."
        : "Ce rendu sera montré au LLM lors du prochain échange.");
    } catch (error) { setMessage(error.message, true); }
  }

  async function saveImage(attemptId) {
    try {
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/attempts/${encodeURIComponent(attemptId)}/save`, { method: "POST" });
      renderProject(payload.project, { preservePrompt: true });
      setMessage(payload.project.export.error ? `Image validée, export en échec : ${payload.project.export.error}` : `Image enregistrée dans ${payload.project.export.path || "le projet"}.`, Boolean(payload.project.export.error));
      await loadHistory();
    } catch (error) { setMessage(error.message, true); }
  }

  function parsedDraft() {
    const value = JSON.parse(elements.recipeDraft.value);
    const keys = ["recipe_id", "display_name", "description", "identity", "invariants", "variables", "risks", "canonical_prompt"];
    const result = {};
    keys.forEach((key) => { result[key] = value[key]; });
    return result;
  }

  async function saveDraft() {
    try {
      const draft = parsedDraft();
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/recipe-draft`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft),
      });
      state.draftSnapshot = draftText(payload.project.recipe_draft);
      elements.recipeDraft.value = state.draftSnapshot;
      renderProject(payload.project, { preservePrompt: true });
      elements.recipeMessage.textContent = "Brouillon enregistré dans le projet.";
    } catch (error) { elements.recipeMessage.textContent = error.message; elements.recipeMessage.classList.add("error"); }
  }

  async function publishRecipe() {
    try {
      const draft = parsedDraft();
      const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(state.project.project_id)}/recipe/publish`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft }),
      });
      renderProject(payload.project, { preservePrompt: true });
      elements.recipeMessage.textContent = `Recette ${payload.recipe.display_name} publiée en ${payload.recipe.version}.`;
      elements.recipeMessage.classList.remove("error");
    } catch (error) { elements.recipeMessage.textContent = error.message; elements.recipeMessage.classList.add("error"); }
  }

  async function initialize() {
    if (state.initializing) return state.initializing;
    if (state.initialized) return;
    state.initializing = (async () => {
      setBusy(true);
      try {
        await Promise.all([loadSpec(), loadHistory()]);
        state.initialized = true;
      } catch (error) { setNewMessage(`Création assistée indisponible : ${error.message}`); }
      finally { state.initializing = null; setBusy(false); }
    })();
    return state.initializing;
  }

  elements.newForm.addEventListener("submit", createProject);
  elements.refresh.addEventListener("click", loadHistory);
  elements.chat.addEventListener("click", () => sendChat("creation"));
  elements.recipeChat.addEventListener("click", () => sendChat("recipe"));
  elements.guidanceFile.addEventListener("change", selectGuidanceFile);
  elements.guidanceRemove.addEventListener("click", clearGuidance);
  elements.render.addEventListener("click", renderAttempt);
  elements.cancel.addEventListener("click", cancelAttempt);
  elements.copyPrompt.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(elements.prompt.value); setMessage("Prompt copié."); }
    catch (_) { elements.prompt.select(); document.execCommand("copy"); }
  });
  elements.saveDraft.addEventListener("click", saveDraft);
  elements.publishRecipe.addEventListener("click", publishRecipe);
  elements.lightboxClose.addEventListener("click", () => elements.lightbox.close());
  elements.lightbox.addEventListener("click", (event) => { if (event.target === elements.lightbox) elements.lightbox.close(); });
  document.querySelectorAll('[data-image-lab-mode="krea2-assisted-lab"]').forEach((button) => {
    button.addEventListener("click", () => {
      window.PanelForgeLabNavigation?.switchView("krea2-assisted-lab");
      initialize();
    });
  });
  window.addEventListener("beforeunload", stopPolling);
  window.PanelForgeKrea2AssistedLab = Object.freeze({
    open: () => {
      window.PanelForgeLabNavigation?.switchView("krea2-assisted-lab");
      return initialize();
    },
  });
})();
