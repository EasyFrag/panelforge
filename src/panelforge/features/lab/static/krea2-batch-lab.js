(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["completed", "failed", "cancelled"]);
  const activeStatuses = new Set(["generating_prompts", "rendering", "cancel_pending"]);
  const {
    modelGroups,
    appendGroupedOptions,
    renderModelPicker,
    syncModelPicker,
    renderCatalogManager,
    renderLoraStack: renderLoraPickerStack,
  } = window.PanelForgeKrea2ResourceUi;

  const elements = {
    workspace: $("krea2-batch-lab-workspace"),
    form: $("krea2-batch-form"),
    recipe: $("krea2-batch-recipe"),
    recipeDescription: $("krea2-batch-recipe-description"),
    recipeLanguage: $("krea2-batch-recipe-language"),
    count: $("krea2-batch-count"),
    llm: $("krea2-batch-llm"),
    direction: $("krea2-batch-direction"),
    model: $("krea2-batch-model"),
    modelMeta: $("krea2-batch-model-meta"),
    ratio: $("krea2-batch-ratio"),
    megapixels: $("krea2-batch-megapixels"),
    loraStack: $("krea2-batch-lora-stack"),
    catalogManager: $("krea2-batch-catalog-manager"),
    showReasoning: $("krea2-batch-show-reasoning"),
    generate: $("krea2-batch-generate"),
    formMessage: $("krea2-batch-form-message"),
    title: $("krea2-batch-title"),
    status: $("krea2-batch-status"),
    progress: $("krea2-batch-progress"),
    progressLabel: $("krea2-batch-progress-label"),
    reasoning: $("krea2-batch-reasoning"),
    reasoningLabel: $("krea2-batch-reasoning-label"),
    reasoningEmpty: $("krea2-batch-reasoning-empty"),
    reasoningContent: $("krea2-batch-reasoning-content"),
    warnings: $("krea2-batch-warnings"),
    grid: $("krea2-batch-grid"),
    message: $("krea2-batch-message"),
    cancel: $("krea2-batch-cancel"),
    revision: $("krea2-batch-revision"),
    revisionStatus: $("krea2-batch-revision-status"),
    revisionConversation: $("krea2-batch-revision-conversation"),
    revisionInstruction: $("krea2-batch-revision-instruction"),
    revisionLanguage: $("krea2-batch-revision-language"),
    proposeRevision: $("krea2-batch-propose-revision"),
    saveRevision: $("krea2-batch-save-revision"),
    testRevision: $("krea2-batch-test-revision"),
    acceptRevision: $("krea2-batch-accept-revision"),
    revisionCandidate: $("krea2-batch-revision-candidate"),
    revisionDraft: $("krea2-batch-revision-draft"),
    revisionTestNote: $("krea2-batch-revision-test-note"),
    refresh: $("krea2-batch-refresh"),
    historyEmpty: $("krea2-batch-history-empty"),
    historyList: $("krea2-batch-history-list"),
  };
  if (!elements.workspace) return;

  const state = {
    initialized: false,
    spec: null,
    recipes: [],
    models: [],
    loras: [],
    loraSlots: [],
    activeBatch: null,
    batches: [],
    workshopRoot: null,
    syncedDraftId: null,
    draftDirty: false,
    busy: false,
    pollTimer: null,
  };
  const core = window.PanelForgeLabCore;
  const reasoningTrace = core && typeof core.createReasoningTrace === "function"
    ? core.createReasoningTrace({
      toggle: elements.showReasoning,
      panel: elements.reasoning,
      label: elements.reasoningLabel,
      output: elements.reasoningContent,
      empty: elements.reasoningEmpty,
    })
    : Object.freeze({ begin: () => {}, handle: () => {}, finish: () => {}, reset: () => {}, streamUrl: (url) => url });

  function request(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      let payload = null;
      try { payload = await response.json(); } catch (_) { /* empty */ }
      if (!response.ok) {
        const detail = payload && payload.detail;
        throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
      }
      return payload;
    });
  }

  function batchOf(payload) {
    return payload && payload.batch ? payload.batch : payload;
  }

  function selectedRecipe() {
    return state.recipes.find((recipe) => `${recipe.recipe_id}@${recipe.version}` === elements.recipe.value) || null;
  }

  function selectedModelResource() {
    return state.models.find((resource) => resource.comfy_name === elements.model.value) || null;
  }

  function setFormMessage(message = "", isError = true) {
    elements.formMessage.textContent = message;
    elements.formMessage.hidden = !message;
    elements.formMessage.classList.toggle("error", isError);
    elements.formMessage.classList.toggle("message", !isError);
  }

  function setMessage(message = "", isError = false) {
    elements.message.textContent = message;
    elements.message.classList.toggle("error", isError);
  }

  function formatBytes(bytes) {
    const gib = Number(bytes) / (1024 ** 3);
    return Number.isFinite(gib) ? `${gib.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Gio` : "";
  }

  function ensureMissingOption(select, value, label) {
    if (!value || [...select.options].some((option) => option.value === value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${label} · absent`;
    option.dataset.missing = "true";
    select.prepend(option);
  }

  function resourceLink(resource, compact = false) {
    const anchor = document.createElement("a");
    anchor.className = compact ? "krea2-resource-info compact" : "krea2-resource-info";
    anchor.href = resource && resource.source_url ? resource.source_url : "#";
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.textContent = "i";
    anchor.title = "Ouvrir la fiche ou la recherche CivitAI";
    if (!resource || !resource.source_url) {
      anchor.removeAttribute("href");
      anchor.setAttribute("aria-disabled", "true");
    }
    return anchor;
  }

  async function updatePreference(resource, values) {
    if (!resource || state.busy) return false;
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadSpec({ preserve: true });
      return updated;
    } catch (error) { setFormMessage(error.message); return false; }
  }

  async function refreshResource(resource) {
    if (!resource || state.busy) return false;
    setFormMessage("Vérification CivitAI en cours…", false);
    try {
      const updated = await request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/refresh`, { method: "POST" });
      await loadSpec({ preserve: true });
      setFormMessage("Informations CivitAI actualisées.", false);
      return updated;
    } catch (error) { setFormMessage(`Vérification indisponible : ${error.message}`); return false; }
  }

  function renderModelMeta() {
    elements.modelMeta.replaceChildren();
    const resource = selectedModelResource();
    if (!resource) {
      const warning = document.createElement("span");
      warning.className = "resource-warning";
      warning.textContent = elements.model.value ? "Checkpoint absent : le batch restera préparé, sans rendu." : "Aucun checkpoint sélectionné.";
      elements.modelMeta.append(warning);
      return;
    }
    const summary = document.createElement("span");
    const precision = resource.precision && resource.precision !== "unknown"
      ? resource.precision.toUpperCase()
      : "Précision inconnue";
    const precisionSource = ({ size: "taille", filename: "nom", manual: "manuel" })[resource.precision_source];
    summary.textContent = `${precision}${precisionSource ? ` · ${precisionSource}` : ""}${resource.size_bytes ? ` · ${formatBytes(resource.size_bytes)}` : ""}`;
    elements.modelMeta.append(summary, resourceLink(resource));
    const favorite = document.createElement("button");
    favorite.type = "button";
    favorite.className = "resource-icon-button";
    favorite.textContent = resource.favorite ? "★" : "☆";
    favorite.title = resource.favorite ? "Retirer des favoris" : "Ajouter aux favoris";
    favorite.addEventListener("click", () => updatePreference(resource, { favorite: !resource.favorite }));
    const refresh = document.createElement("button");
    refresh.type = "button";
    refresh.className = "resource-icon-button";
    refresh.textContent = "↻";
    refresh.title = "Vérifier la fiche et les mises à jour CivitAI";
    refresh.addEventListener("click", () => refreshResource(resource));
    elements.modelMeta.append(favorite, refresh);
    if (resource.update_available === true) {
      const update = document.createElement("span");
      update.className = "resource-update";
      update.textContent = `Mise à jour disponible${resource.latest_version_name ? ` · ${resource.latest_version_name}` : ""}`;
      elements.modelMeta.append(update);
    } else if (resource.warning) {
      const warning = document.createElement("span");
      warning.className = "resource-warning";
      warning.textContent = resource.warning;
      elements.modelMeta.append(warning);
    }
  }

  function renderLoraStack() {
    renderLoraPickerStack(elements.loraStack, {
      resources: state.loras,
      selections: state.loraSlots,
      maximum: 10,
      minimumStrength: -20,
      maximumStrength: 20,
      draggable: true,
      disabled: state.busy,
      updatePreference,
      refreshResource,
      onChange: (values) => {
        state.loraSlots = values;
        renderLoraStack();
      },
    });
  }

  function setLoras(values) {
    state.loraSlots = (values || []).slice(0, 10).filter((value) => value && value.name).map((value) => ({
      name: value.name,
      strength: Number(value.strength) || 0,
    }));
    renderLoraStack();
  }

  function populateRecipeOptions(current = "") {
    elements.recipe.replaceChildren();
    state.recipes.forEach((recipe) => {
      const option = document.createElement("option");
      option.value = `${recipe.recipe_id}@${recipe.version}`;
      option.textContent = `${recipe.display_name} · v${recipe.version}`;
      elements.recipe.append(option);
    });
    elements.recipe.value = state.recipes.some((recipe) => `${recipe.recipe_id}@${recipe.version}` === current)
      ? current
      : elements.recipe.options[0] ? elements.recipe.options[0].value : "";
  }

  function populateModels(current = "") {
    renderModelPicker(elements.model, {
      resources: state.models,
      updatePreference,
      refreshResource,
    });
    ensureMissingOption(elements.model, current, current);
    if (current) elements.model.value = current;
    syncModelPicker(elements.model);
  }

  function populateRatios(current = "") {
    elements.ratio.replaceChildren();
    (state.spec.aspect_ratios || []).forEach((ratio) => {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio;
      elements.ratio.append(option);
    });
    if ([...elements.ratio.options].some((option) => option.value === current)) elements.ratio.value = current;
  }

  function applyRecipe(recipe, { preserveDirection = true } = {}) {
    if (!recipe) return;
    elements.recipeDescription.textContent = recipe.description || recipe.identity || "";
    elements.recipeLanguage.textContent = recipe.prompt_language === "zh" ? "中文" : "EN";
    const settings = recipe.settings || {};
    populateModels(settings.model_id || "");
    populateRatios(settings.aspect_ratio || "9:16 (Portrait)");
    elements.megapixels.value = String(settings.megapixels ?? 2.1);
    setLoras(settings.loras || []);
    if (!preserveDirection) elements.direction.value = "";
    renderModelMeta();
    renderControls();
  }

  function populateLlms(models, current = "") {
    const normalized = (models || []).map((model) => typeof model === "string" ? { id: model } : model).filter((model) => model.id);
    if (window.PanelForgeModelPicker) window.PanelForgeModelPicker.populate(elements.llm, normalized, current);
    else {
      elements.llm.replaceChildren(...normalized.map((model) => {
        const option = document.createElement("option"); option.value = model.id; option.textContent = model.id; return option;
      }));
    }
  }

  async function loadSpec({ preserve = false } = {}) {
    const prior = preserve ? {
      recipe: elements.recipe.value,
      llm: elements.llm.value,
      model: elements.model.value,
      ratio: elements.ratio.value,
      megapixels: elements.megapixels.value,
      loras: state.loraSlots.map((value) => ({ ...value })),
    } : null;
    const spec = await request("/api/image-lab/krea2-batch/spec");
    state.spec = spec || {};
    state.recipes = state.spec.recipes || [];
    state.models = state.spec.render_models || [];
    state.loras = state.spec.loras || [];
    populateRecipeOptions(prior && prior.recipe);
    populateLlms(state.spec.llm_models || [], prior && prior.llm);
    if (prior) {
      populateModels(prior.model);
      populateRatios(prior.ratio);
      elements.megapixels.value = prior.megapixels;
      setLoras(prior.loras);
      const recipe = selectedRecipe();
      elements.recipeDescription.textContent = recipe ? recipe.description : "";
      elements.recipeLanguage.textContent = recipe?.prompt_language === "zh" ? "中文" : "EN";
    } else applyRecipe(selectedRecipe());
    renderModelMeta();
    renderCatalogManager(elements.catalogManager, {
      models: state.models,
      loras: state.loras,
      updatePreference,
      refreshResource,
    });
    renderWarnings(state.activeBatch);
    renderControls();
  }

  function statusLabel(status) {
    return ({
      created: "Préparé", generating_prompts: "Création des variations", ready: "Prompts prêts",
      rendering: "Rendu ComfyUI", completed: "Terminé", cancel_pending: "Annulation à confirmer",
      cancelled: "Annulé", failed: "Échec",
    })[status] || status || "Prêt";
  }

  function renderWarnings(batch) {
    const warnings = [
      ...(state.spec?.resource_warnings || []),
      ...((batch && batch.warnings) || []),
    ];
    elements.warnings.hidden = !warnings.length;
    elements.warnings.replaceChildren(...warnings.map((warning) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = `⚠ ${warning}`;
      return paragraph;
    }));
  }

  function renderProgress(batch) {
    const items = (batch && batch.items) || [];
    const done = items.filter((item) => ["succeeded", "failed", "cancelled"].includes(item.status)).length;
    const total = Number(batch && batch.image_count) || items.length || 1;
    const status = batch && batch.status;
    elements.progress.max = total;
    elements.progress.value = status === "completed" ? total : done;
    elements.progressLabel.textContent = status === "generating_prompts"
      ? "Le LLM prépare les variations…"
      : items.length ? `${done} / ${total} rendus terminés` : "En attente";
  }

  function reviewButton(symbol, decision, item) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = symbol;
    button.className = `krea2-review-button${item.review === decision ? " active" : ""}`;
    button.title = decision === "like" ? "J’aime" : decision === "dislike" ? "Je n’aime pas" : "Sans avis";
    return button;
  }

  async function saveReview(item, decision, comment) {
    const batch = state.activeBatch;
    if (!batch || state.busy) return;
    try {
      const payload = await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.batch_id)}/items/${encodeURIComponent(item.item_id)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, comment }),
      });
      renderBatch(batchOf(payload));
    } catch (error) { setMessage(error.message, true); }
  }

  function renderItem(item) {
    const article = document.createElement("article");
    article.className = `krea2-batch-card ${item.status}`;
    const media = document.createElement("div");
    media.className = "krea2-batch-card-media";
    if (item.output_url) {
      const image = document.createElement("img");
      image.src = item.output_url;
      image.alt = item.variation_signature || `Variation ${item.index}`;
      image.loading = "lazy";
      image.decoding = "async";
      media.append(image);
    } else {
      const placeholder = document.createElement("span");
      placeholder.textContent = item.status === "running" ? "Rendu en cours…" : item.status === "failed" ? "Échec" : `Image ${item.index}`;
      media.append(placeholder);
    }
    const body = document.createElement("div");
    body.className = "krea2-batch-card-body";
    const heading = document.createElement("h3");
    heading.textContent = `${item.index}. ${item.variation_signature}`;
    const meta = document.createElement("small");
    meta.textContent = `${statusLabel(item.status)} · seed ${item.seed}`;
    body.append(heading, meta);
    if (item.error) {
      const error = document.createElement("p"); error.className = "error"; error.textContent = item.error; body.append(error);
    }
    const prompt = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "Prompt";
    const text = document.createElement("p"); text.textContent = item.prompt;
    prompt.append(summary, text);
    body.append(prompt);
    if (item.status === "succeeded") {
      const review = document.createElement("div");
      review.className = "krea2-batch-review";
      const comment = document.createElement("textarea");
      comment.rows = 2;
      comment.placeholder = "Commentaire facultatif…";
      comment.value = item.comment || "";
      const neutral = reviewButton("○", "neutral", item);
      const like = reviewButton("👍", "like", item);
      const dislike = reviewButton("👎", "dislike", item);
      neutral.addEventListener("click", () => saveReview(item, "neutral", comment.value));
      like.addEventListener("click", () => saveReview(item, "like", comment.value));
      dislike.addEventListener("click", () => saveReview(item, "dislike", comment.value));
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = "Enregistrer";
      save.addEventListener("click", () => saveReview(item, item.review || "neutral", comment.value));
      const buttons = document.createElement("span"); buttons.append(neutral, like, dislike, save);
      review.append(buttons, comment);
      body.append(review);
    }
    article.append(media, body);
    return article;
  }

  function renderGrid(batch) {
    const items = (batch && batch.items) || [];
    if (!items.length) {
      elements.grid.innerHTML = '<p class="muted">Les images du prochain batch apparaîtront ici.</p>';
      return;
    }
    elements.grid.replaceChildren(...items.map(renderItem));
  }

  function workshopRootFor(batch) {
    if (!batch) return null;
    if (batch.recipe_workshop) return batch;
    if (batch.workshop_source_batch_id) {
      if (state.workshopRoot && state.workshopRoot.batch_id === batch.workshop_source_batch_id) return state.workshopRoot;
      return state.batches.find((value) => value.batch_id === batch.workshop_source_batch_id) || null;
    }
    return batch;
  }

  function renderConversation(workshop) {
    const turns = (workshop && workshop.turns) || [];
    elements.revisionConversation.hidden = !turns.length;
    elements.revisionConversation.replaceChildren(...turns.map((turn) => {
      const paragraph = document.createElement("p");
      paragraph.className = `krea2-revision-turn ${turn.role === "user" ? "user" : "assistant"}`;
      paragraph.textContent = turn.message || "";
      return paragraph;
    }));
  }

  function syncCandidateControls(draft, draftId) {
    if (!draft || state.syncedDraftId === draftId) return;
    try {
      const candidate = JSON.parse(draft);
      const settings = candidate.settings || {};
      if (settings.model_name) populateModels(settings.model_name);
      if (settings.aspect_ratio) populateRatios(settings.aspect_ratio);
      if (settings.megapixels != null) elements.megapixels.value = String(settings.megapixels);
      setLoras(settings.loras || []);
      elements.revisionLanguage.value = candidate.prompt_language || "en";
      renderModelMeta();
      state.syncedDraftId = draftId;
    } catch (_) { /* the editable draft will surface its JSON error on save/test */ }
  }

  function syncSourceSettings(root) {
    const key = `source:${root.batch_id}`;
    if (state.syncedDraftId === key) return;
    const settings = root.settings || {};
    if (settings.model_id) populateModels(settings.model_id);
    if (settings.aspect_ratio) populateRatios(settings.aspect_ratio);
    if (settings.megapixels != null) elements.megapixels.value = String(settings.megapixels);
    setLoras(settings.loras || []);
    const recipe = state.recipes.find((value) => (
      value.recipe_id === root.recipe_id && value.version === root.recipe_version
    )) || state.recipes.find((value) => value.recipe_id === root.recipe_id);
    elements.revisionLanguage.value = recipe?.prompt_language || "en";
    renderModelMeta();
    state.syncedDraftId = key;
  }

  function loadWorkshopRoot(batch) {
    if (!batch || !batch.workshop_source_batch_id) return;
    if (state.workshopRoot && state.workshopRoot.batch_id === batch.workshop_source_batch_id) return;
    request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.workshop_source_batch_id)}`)
      .then((payload) => {
        if (!state.activeBatch || state.activeBatch.batch_id !== batch.batch_id) return;
        state.workshopRoot = batchOf(payload);
        renderRevision(state.activeBatch);
      })
      .catch((error) => setMessage(`Atelier temporairement indisponible : ${error.message}`, true));
  }

  function renderRevision(batch) {
    const root = workshopRootFor(batch);
    const visible = Boolean(batch && batch.status === "completed" && root && root.status === "completed");
    elements.revision.hidden = !visible;
    if (!visible) {
      if (batch && batch.workshop_source_batch_id) loadWorkshopRoot(batch);
      return;
    }
    const workshop = root.recipe_workshop;
    const draft = root.recipe_revision_draft || "";
    const draftId = workshop && workshop.active_draft_id;
    if (!state.draftDirty && elements.revisionDraft.value !== draft) elements.revisionDraft.value = draft;
    elements.revisionCandidate.hidden = !draft;
    elements.revisionTestNote.hidden = !draft;
    renderConversation(workshop);
    const tests = (workshop && workshop.test_batch_ids) || [];
    const label = workshop && workshop.status === "published"
      ? `Publié · v${workshop.published_version}`
      : `${draftId || "Nouveau"}${tests.length ? ` · ${tests.length} test${tests.length > 1 ? "s" : ""}` : ""}`;
    elements.revisionStatus.textContent = label;
    elements.saveRevision.disabled = state.busy || !draft;
    elements.testRevision.disabled = state.busy || !draft;
    elements.acceptRevision.disabled = state.busy || !draft || (workshop && workshop.status === "published");
    elements.proposeRevision.disabled = state.busy;
    elements.revisionLanguage.disabled = state.busy || Boolean(workshop && workshop.status === "published");
    if (draft) syncCandidateControls(draft, draftId);
    else syncSourceSettings(root);
  }

  function renderBatch(batch) {
    if (!batch) return;
    state.activeBatch = batch;
    if (batch.recipe_workshop) state.workshopRoot = batch;
    elements.title.textContent = `${batch.recipe_id} · ${batch.image_count} images${batch.workshop_source_batch_id ? " · test recette" : ""}`;
    elements.status.textContent = `● ${statusLabel(batch.status)}`;
    elements.status.className = `run-status ${batch.status}`;
    renderProgress(batch);
    renderWarnings(batch);
    renderGrid(batch);
    renderRevision(batch);
    if (batch.error) setMessage(batch.error, true);
    elements.cancel.disabled = state.busy || !activeStatuses.has(batch.status);
    renderControls();
  }

  function renderControls() {
    const recipe = selectedRecipe();
    const hasCoreInputs = Boolean(recipe && elements.llm.value && elements.model.value);
    elements.generate.disabled = state.busy || !hasCoreInputs || activeStatuses.has(state.activeBatch && state.activeBatch.status);
    [elements.recipe, elements.count, elements.llm, elements.direction, elements.model, elements.ratio, elements.megapixels]
      .forEach((element) => { element.disabled = state.busy || activeStatuses.has(state.activeBatch && state.activeBatch.status); });
    syncModelPicker(elements.model);
    renderRevision(state.activeBatch);
  }

  function setBusy(value) {
    state.busy = Boolean(value);
    renderControls();
  }

  async function refreshActive(batchId) {
    const payload = await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batchId)}`);
    const batch = batchOf(payload);
    renderBatch(batch);
    return batch;
  }

  function stopPolling() {
    if (state.pollTimer !== null) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function schedulePoll(batchId) {
    stopPolling();
    state.pollTimer = window.setTimeout(async () => {
      try {
        const batch = await refreshActive(batchId);
        if (!terminalStatuses.has(batch.status)) schedulePoll(batchId);
        else {
          if (batch.status === "completed") {
            const api = window.PanelForgeLabCore;
            if (api && typeof api.playCompletionTone === "function") api.playCompletionTone();
          }
          setMessage(batch.status === "completed" ? "Batch terminé. Vous pouvez noter les images ou arrêter ici." : batch.error || statusLabel(batch.status), batch.status === "failed");
          await loadHistory();
        }
      } catch (error) {
        setMessage(`Suivi temporairement indisponible : ${error.message}`, true);
        schedulePoll(batchId);
      }
    }, 1200);
  }

  function currentLoras() {
    return state.loraSlots.filter((slot) => slot.name).map((slot) => ({ name: slot.name, strength: Number(slot.strength) || 0 }));
  }

  async function generateBatch(event) {
    event.preventDefault();
    if (state.busy) return;
    const recipe = selectedRecipe();
    if (!recipe) return;
    setBusy(true);
    setFormMessage();
    setMessage();
    reasoningTrace.reset();
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      const createdPayload = await request("/api/image-lab/krea2-batch/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipe_id: recipe.recipe_id,
          recipe_version: recipe.version,
          image_count: Number(elements.count.value),
          model_id: elements.llm.value,
          direction: elements.direction.value.trim(),
          render_model_id: elements.model.value,
          aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value),
          loras: currentLoras(),
        }),
      });
      const created = batchOf(createdPayload);
      renderBatch(created);
      const api = window.PanelForgeLabCore;
      if (!api || typeof api.streamRequest !== "function") throw new Error("Le lecteur de flux LLM est indisponible.");
      reasoningTrace.begin("Variations KREA2");
      try {
        outcomeTone.start();
        await api.streamRequest(
          reasoningTrace.streamUrl(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(created.batch_id)}/prompts/stream`),
          { method: "POST", headers: { Accept: "text/event-stream" } },
          (streamEvent) => {
            reasoningTrace.handle(streamEvent);
            if (streamEvent.batch) renderBatch(streamEvent.batch);
          },
          { completionTone: false },
        );
      } finally { reasoningTrace.finish(); }
      const prepared = await refreshActive(created.batch_id);
      if (prepared.status !== "ready") throw new Error(prepared.error || "Les variations n’ont pas pu être préparées.");
      outcomeTone.success();
      if (!selectedModelResource()) {
        setMessage("Les prompts sont prêts, mais le checkpoint de la recette est absent. Choisissez un modèle installé pour lancer le rendu.", true);
        return;
      }
      const started = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(prepared.batch_id)}/start`, { method: "POST" }));
      renderBatch(started);
      setMessage("Prompts prêts. ComfyUI rend les images l’une après l’autre.");
      schedulePoll(started.batch_id);
    } catch (error) {
      outcomeTone.failure();
      setMessage(error.message, true);
    } finally {
      setBusy(false);
      try { await loadHistory(); } catch (_) { /* active batch remains visible */ }
    }
  }

  async function cancelBatch() {
    const batch = state.activeBatch;
    if (!batch || state.busy) return;
    setBusy(true);
    try {
      const cancelled = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.batch_id)}/cancel`, { method: "POST" }));
      renderBatch(cancelled);
      if (terminalStatuses.has(cancelled.status)) stopPolling();
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  function revisionTechnicalPayload() {
    return {
      render_model_id: elements.model.value,
      aspect_ratio: elements.ratio.value,
      megapixels: Number(elements.megapixels.value),
      loras: currentLoras(),
      prompt_language: elements.revisionLanguage.value,
    };
  }

  function adoptWorkshopRoot(batch) {
    state.workshopRoot = batch;
    state.draftDirty = false;
    state.syncedDraftId = null;
    const index = state.batches.findIndex((value) => value.batch_id === batch.batch_id);
    if (index >= 0) state.batches[index] = batch;
    else state.batches.unshift(batch);
    renderRevision(state.activeBatch || batch);
    renderHistory();
  }

  async function proposeRevision() {
    const batch = state.activeBatch;
    if (!batch || state.busy) return;
    const instruction = elements.revisionInstruction.value.trim();
    if (!instruction) { setMessage("Ajoutez d’abord votre message pour l’atelier.", true); return; }
    setBusy(true);
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      outcomeTone.start();
      const updated = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.batch_id)}/recipe-revision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction,
          draft: elements.revisionDraft.value.trim() || null,
          model_id: elements.llm.value,
          ...revisionTechnicalPayload(),
        }),
      }));
      elements.revisionInstruction.value = "";
      adoptWorkshopRoot(updated);
      outcomeTone.success();
      setMessage("Nouvelle candidate prête. Vous pouvez l’éditer, la tester ou poursuivre la discussion.");
    } catch (error) { outcomeTone.failure(); setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function saveRevision() {
    const batch = state.activeBatch;
    const draft = elements.revisionDraft.value.trim();
    if (!batch || state.busy || !draft) return;
    setBusy(true);
    try {
      const updated = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.batch_id)}/recipe-revision/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft, ...revisionTechnicalPayload() }),
      }));
      adoptWorkshopRoot(updated);
      setMessage("Brouillon enregistré. La recette publiée n’a pas été modifiée.");
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  async function testRevision() {
    const source = state.activeBatch;
    const draft = elements.revisionDraft.value.trim();
    if (!source || state.busy || !draft) return;
    setBusy(true);
    setMessage();
    reasoningTrace.reset();
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      const payload = await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(source.batch_id)}/recipe-revision/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          draft,
          image_count: Number(elements.count.value),
          model_id: elements.llm.value,
          direction: elements.direction.value.trim(),
          ...revisionTechnicalPayload(),
        }),
      });
      adoptWorkshopRoot(payload.workshop_batch);
      const created = batchOf(payload);
      renderBatch(created);
      const api = window.PanelForgeLabCore;
      if (!api || typeof api.streamRequest !== "function") throw new Error("Le lecteur de flux LLM est indisponible.");
      reasoningTrace.begin("Test de recette");
      try {
        outcomeTone.start();
        await api.streamRequest(
          reasoningTrace.streamUrl(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(created.batch_id)}/prompts/stream`),
          { method: "POST", headers: { Accept: "text/event-stream" } },
          (streamEvent) => {
            reasoningTrace.handle(streamEvent);
            if (streamEvent.batch) renderBatch(streamEvent.batch);
          },
          { completionTone: false },
        );
      } finally { reasoningTrace.finish(); }
      const prepared = await refreshActive(created.batch_id);
      if (prepared.status !== "ready") throw new Error(prepared.error || "Le test de recette n’a pas pu être préparé.");
      outcomeTone.success();
      if (!selectedModelResource()) {
        setMessage("Les prompts de test sont prêts, mais le checkpoint candidat est absent.", true);
        return;
      }
      const started = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(prepared.batch_id)}/start`, { method: "POST" }));
      renderBatch(started);
      setMessage("Candidate enregistrée. ComfyUI lance son batch d’essai.");
      schedulePoll(started.batch_id);
    } catch (error) { outcomeTone.failure(); setMessage(error.message, true); }
    finally {
      setBusy(false);
      try { await loadHistory(); } catch (_) { /* keep current workshop */ }
    }
  }

  async function acceptRevision() {
    const batch = state.activeBatch;
    if (!batch || state.busy) return;
    setBusy(true);
    try {
      const payload = await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(batch.batch_id)}/recipe-revision/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft: elements.revisionDraft.value.trim(), ...revisionTechnicalPayload() }),
      });
      await loadSpec({ preserve: true });
      const root = workshopRootFor(batch);
      if (root) {
        const refreshed = batchOf(await request(`/api/image-lab/krea2-batch/batches/${encodeURIComponent(root.batch_id)}`));
        adoptWorkshopRoot(refreshed);
      }
      setMessage(`Recette ${payload.recipe.display_name} publiée en version ${payload.recipe.version}.`);
    } catch (error) { setMessage(error.message, true); }
    finally { setBusy(false); }
  }

  function renderHistory() {
    elements.historyList.replaceChildren();
    elements.historyEmpty.hidden = state.batches.length > 0;
    state.batches.forEach((batch) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "krea2-batch-history-item";
      const title = document.createElement("b");
      title.textContent = `${batch.recipe_id} · ${batch.image_count} images${batch.workshop_source_batch_id ? " · test" : ""}`;
      const meta = document.createElement("small");
      const succeeded = (batch.items || []).filter((value) => value.status === "succeeded").length;
      meta.textContent = `${statusLabel(batch.status)} · ${succeeded}/${batch.image_count} sorties · ${batch.recipe_version}`;
      button.append(title, meta);
      const thumbs = document.createElement("span");
      thumbs.className = "krea2-batch-history-thumbs";
      (batch.items || []).filter((value) => value.output_url).slice(0, 4).forEach((value) => {
        const image = document.createElement("img"); image.src = value.output_url; image.alt = ""; image.loading = "lazy"; thumbs.append(image);
      });
      button.append(thumbs);
      button.addEventListener("click", () => {
        stopPolling();
        renderBatch(batch);
        if (!terminalStatuses.has(batch.status)) schedulePoll(batch.batch_id);
      });
      item.append(button);
      elements.historyList.append(item);
    });
  }

  async function loadHistory() {
    const payload = await request("/api/image-lab/krea2-batch/batches?limit=20");
    state.batches = payload.batches || [];
    if (state.workshopRoot) {
      state.workshopRoot = state.batches.find((value) => value.batch_id === state.workshopRoot.batch_id) || state.workshopRoot;
    }
    renderHistory();
  }

  async function initialize() {
    if (state.initialized) return;
    state.initialized = true;
    setBusy(true);
    try {
      await Promise.all([loadSpec(), loadHistory()]);
    } catch (error) {
      setFormMessage(`Batch KREA2 indisponible : ${error.message}`);
    } finally { setBusy(false); }
  }

  elements.form.addEventListener("submit", generateBatch);
  elements.recipe.addEventListener("change", () => applyRecipe(selectedRecipe()));
  elements.model.addEventListener("change", () => { renderModelMeta(); renderControls(); });
  elements.cancel.addEventListener("click", cancelBatch);
  elements.proposeRevision.addEventListener("click", proposeRevision);
  elements.saveRevision.addEventListener("click", saveRevision);
  elements.testRevision.addEventListener("click", testRevision);
  elements.acceptRevision.addEventListener("click", acceptRevision);
  elements.revisionDraft.addEventListener("input", () => {
    state.draftDirty = true;
    elements.saveRevision.disabled = state.busy || !elements.revisionDraft.value.trim();
  });
  elements.refresh.addEventListener("click", async () => {
    if (state.busy) return;
    setBusy(true);
    try { await Promise.all([loadSpec({ preserve: true }), loadHistory()]); }
    catch (error) { setFormMessage(error.message); }
    finally { setBusy(false); }
  });
  document.querySelectorAll('[data-image-lab-mode="krea2-batch-lab"]').forEach((button) => {
    button.addEventListener("click", () => {
      if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView("krea2-batch-lab");
      initialize();
    });
  });
  window.addEventListener("beforeunload", stopPolling);
  window.PanelForgeKrea2BatchLab = Object.freeze({ open: () => {
    if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView("krea2-batch-lab");
    return initialize();
  } });
})();
