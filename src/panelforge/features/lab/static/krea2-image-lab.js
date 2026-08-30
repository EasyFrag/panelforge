(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["succeeded", "completed", "failed", "cancelled", "canceled"]);
  const activeStatuses = new Set(["queued", "running", "cancel_pending"]);
  const preferredModelId = "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors";
  const preferredModelFragment = "krea2gptgrandpussytruth_gptint4int8convrot";
  const seedStorageKey = "panelforge.krea2.seed-locked";
  const aspectRatioEnum = Object.freeze([
    "1:1 (Square)",
    "2:3 (Portrait Photo)",
    "3:2 (Photo)",
    "3:4 (Portrait Standard)",
    "4:3 (Standard)",
    "9:16 (Portrait Widescreen)",
    "16:9 (Widescreen)",
    "21:9 (Ultrawide)",
  ]);

  const elements = {
    workspace: $("krea2-image-lab-workspace"),
    form: $("krea2-image-lab-form"),
    prompt: $("krea2-image-lab-prompt"),
    model: $("krea2-image-lab-model"),
    refreshModels: $("krea2-image-lab-refresh-models"),
    ratio: $("krea2-image-lab-ratio"),
    megapixels: $("krea2-image-lab-megapixels"),
    resolution: $("krea2-image-lab-resolution"),
    seed: $("krea2-image-lab-seed"),
    seedLock: $("krea2-image-lab-seed-lock"),
    randomizeSeed: $("krea2-image-lab-randomize-seed"),
    formMessage: $("krea2-image-lab-form-message"),
    generate: $("krea2-image-lab-generate"),
    status: $("krea2-image-lab-status"),
    outputCaption: $("krea2-image-lab-output-caption"),
    outputEmpty: $("krea2-image-lab-output-empty"),
    outputLoading: $("krea2-image-lab-output-loading"),
    output: $("krea2-image-lab-output"),
    progress: $("krea2-image-lab-progress"),
    progressLabel: $("krea2-image-lab-progress-label"),
    metadata: $("krea2-image-lab-metadata"),
    runMessage: $("krea2-image-lab-run-message"),
    cancel: $("krea2-image-lab-cancel"),
    reuseSeed: $("krea2-image-lab-reuse-seed"),
    download: $("krea2-image-lab-download"),
    refresh: $("krea2-image-lab-refresh"),
    historyEmpty: $("krea2-image-lab-history-empty"),
    historyList: $("krea2-image-lab-history-list"),
    modeButtons: [...document.querySelectorAll("[data-image-lab-mode]")],
  };
  if (!elements.workspace) return;

  const state = {
    initialized: false,
    initializing: null,
    initializationError: null,
    spec: null,
    runs: [],
    activeRun: null,
    busy: false,
    pollToken: 0,
    pollTimer: null,
    outputUrl: "",
  };

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty response */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      const message = typeof detail === "string" ? detail
        : detail && detail.message ? detail.message
          : `Erreur HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload;
  }

  function unwrapRun(payload) {
    return payload && payload.run ? payload.run : payload;
  }

  function runId(run) {
    return run && (run.run_id || run.id);
  }

  function runStatus(run) {
    return String((run && run.status) || "").toLowerCase();
  }

  function isActive(run) {
    return Boolean(run && activeStatuses.has(runStatus(run)));
  }

  function runParameter(run, name) {
    if (!run) return null;
    if (run[name] !== undefined && run[name] !== null) return run[name];
    for (const container of [run.parameters, run.settings, run.controls]) {
      if (container && container[name] !== undefined && container[name] !== null) return container[name];
    }
    return null;
  }

  function runOutputUrl(run) {
    if (!run) return "";
    const asset = run.output_asset || run.result_asset || {};
    return String(run.result_url || run.output_url || run.output_content_url || run.image_url || asset.content_url || asset.url || "");
  }

  function randomSeed() {
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
      const values = new Uint32Array(2);
      window.crypto.getRandomValues(values);
      if (typeof BigInt === "function") return ((BigInt(values[0]) << 32n) | BigInt(values[1])).toString();
      return String((values[0] * 0x200000 + (values[1] >>> 11)) % Number.MAX_SAFE_INTEGER);
    }
    return String(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER));
  }

  function validSeed(value) {
    if (!/^\d+$/.test(String(value || ""))) return false;
    try { return BigInt(value) <= 18446744073709551615n; } catch (_) { return false; }
  }

  function showFormMessage(message, failed = true) {
    elements.formMessage.textContent = message || "";
    elements.formMessage.classList.toggle("status-info", !failed);
    elements.formMessage.hidden = !message;
  }

  function showRunMessage(message, failed = false) {
    elements.runMessage.textContent = message || "";
    elements.runMessage.className = failed ? "message error-text" : "message";
  }

  function statusLabel(status) {
    return ({
      created: "Préparé",
      prepared: "Préparé",
      submitted: "Soumis",
      queued: "En file",
      running: "Génération…",
      executing: "Génération…",
      cancel_pending: "Annulation…",
      succeeded: "Terminé",
      completed: "Terminé",
      failed: "Échec",
      cancelled: "Annulé",
      canceled: "Annulé",
    })[status] || "Prêt";
  }

  function modelValues() {
    return [...elements.model.options]
      .filter((option) => !option.disabled && option.value)
      .map((option) => option.value);
  }

  function ratioValues() {
    return [...elements.ratio.options]
      .filter((option) => !option.disabled && option.value)
      .map((option) => option.value);
  }

  function validationError() {
    if (!elements.prompt.value.trim()) return "Saisissez un prompt KREA2.";
    if (!elements.model.value || !modelValues().includes(elements.model.value)) return "Choisissez un modèle KREA2 installé.";
    if (!aspectRatioEnum.includes(elements.ratio.value) || !ratioValues().includes(elements.ratio.value)) {
      return "Choisissez un ratio KREA2 disponible.";
    }
    const megapixels = Number(elements.megapixels.value);
    if (!Number.isFinite(megapixels) || megapixels < Number(elements.megapixels.min) || megapixels > Number(elements.megapixels.max)) {
      return `Les mégapixels doivent rester entre ${elements.megapixels.min} et ${elements.megapixels.max}.`;
    }
    if (Math.abs(megapixels * 10 - Math.round(megapixels * 10)) > Number.EPSILON * 10) {
      return "Les mégapixels se règlent par pas de 0,1.";
    }
    if (!validSeed(elements.seed.value.trim())) return "La seed doit être un entier positif représentable sans arrondi.";
    return "";
  }

  function renderControls() {
    const blocked = state.busy || isActive(state.activeRun);
    elements.prompt.disabled = blocked;
    elements.model.disabled = blocked;
    elements.ratio.disabled = blocked;
    elements.megapixels.disabled = blocked;
    elements.seed.disabled = blocked;
    elements.seedLock.disabled = blocked;
    elements.randomizeSeed.disabled = blocked;
    elements.refreshModels.disabled = blocked;
    elements.generate.disabled = blocked || Boolean(validationError());
    elements.cancel.disabled = state.busy || !isActive(state.activeRun);
    elements.reuseSeed.disabled = state.busy || runParameter(state.activeRun, "seed") === null;
    elements.refresh.disabled = state.busy;
    elements.historyList.querySelectorAll("button").forEach((button) => { button.disabled = blocked; });
  }

  function parseRatio(value) {
    const match = String(value || "").match(/(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)/);
    if (!match) return null;
    const width = Number(match[1]);
    const height = Number(match[2]);
    return width > 0 && height > 0 ? { width, height } : null;
  }

  function roundedDimension(value) {
    return Math.max(64, Math.round(value / 8) * 8);
  }

  function updateResolution(run = null) {
    const exact = run && run.resolution;
    if (typeof exact === "string" && exact) {
      elements.resolution.textContent = `Résolution du run : ${exact}`;
      return;
    }
    if (exact && exact.width && exact.height) {
      elements.resolution.textContent = `Résolution du run : ${exact.width} × ${exact.height} px`;
      return;
    }
    const ratio = parseRatio(elements.ratio.value);
    const megapixels = Number(elements.megapixels.value);
    if (!ratio || !Number.isFinite(megapixels) || megapixels <= 0) {
      elements.resolution.textContent = "La résolution exacte sera calculée par le workflow.";
      return;
    }
    const area = megapixels * 1024 * 1024;
    const scale = Math.sqrt(area / (ratio.width * ratio.height));
    const width = roundedDimension(ratio.width * scale);
    const height = roundedDimension(ratio.height * scale);
    elements.resolution.textContent = `Environ ${width.toLocaleString("fr-FR")} × ${height.toLocaleString("fr-FR")} px`;
  }

  function appendMetadata(label) {
    const chip = document.createElement("span");
    chip.textContent = label;
    elements.metadata.append(chip);
  }

  function resetOutput() {
    state.outputUrl = "";
    elements.output.removeAttribute("src");
    elements.output.hidden = true;
    elements.outputEmpty.hidden = false;
    elements.outputLoading.hidden = true;
    elements.outputCaption.textContent = "Aucun rendu";
    elements.download.hidden = true;
    elements.download.removeAttribute("href");
    elements.progress.value = 0;
    elements.progressLabel.textContent = "En attente";
  }

  function setOutput(url, label) {
    const canonicalUrl = new URL(url, window.location.href).href;
    if (canonicalUrl !== state.outputUrl) {
      state.outputUrl = canonicalUrl;
      const displayUrl = new URL(canonicalUrl);
      displayUrl.searchParams.set("_pf_media", String(Date.now()));
      elements.output.src = displayUrl.href;
    }
    elements.output.hidden = false;
    elements.outputEmpty.hidden = true;
    elements.outputLoading.hidden = true;
    elements.outputCaption.textContent = label || "PNG final";
    elements.download.href = canonicalUrl;
    elements.download.download = label && label.toLowerCase().endsWith(".png") ? label : "krea2-output.png";
    elements.download.hidden = false;
  }

  function renderRun(run) {
    state.activeRun = run || null;
    const status = runStatus(run);
    elements.status.textContent = `● ${statusLabel(status)}`;
    elements.status.className = "run-status";
    if (activeStatuses.has(status)) elements.status.classList.add("active");
    if (["succeeded", "completed"].includes(status)) elements.status.classList.add("success");
    if (["failed", "cancelled", "canceled"].includes(status)) elements.status.classList.add("failed");

    const active = isActive(run);
    const outputUrl = runOutputUrl(run);
    elements.outputLoading.hidden = !active || Boolean(outputUrl);
    elements.outputEmpty.hidden = active || Boolean(outputUrl);
    if (outputUrl) setOutput(outputUrl, run.output_filename || run.filename || "krea2-output.png");

    const progress = Number(run && (run.progress ?? run.progress_ratio));
    if (Number.isFinite(progress)) elements.progress.value = Math.max(0, Math.min(1, progress > 1 ? progress / 100 : progress));
    else if (["succeeded", "completed"].includes(status)) elements.progress.value = 1;
    const step = run && (run.current_step ?? run.step);
    const total = run && (run.total_steps ?? run.steps);
    elements.progressLabel.textContent = step && total ? `Step ${step} / ${total}` : statusLabel(status);

    elements.metadata.replaceChildren();
    if (run) {
      if (runParameter(run, "aspect_ratio")) appendMetadata(String(runParameter(run, "aspect_ratio")));
      if (runParameter(run, "megapixels")) appendMetadata(`${Number(runParameter(run, "megapixels")).toLocaleString("fr-FR")} MP`);
      if (runParameter(run, "model_id")) appendMetadata(String(runParameter(run, "model_id")));
      if (runParameter(run, "seed") !== null) appendMetadata(`Seed ${runParameter(run, "seed")}`);
    }
    updateResolution(run);
    showRunMessage((run && (run.error || run.message)) || "", status === "failed");
    renderControls();
  }

  function normalizedModels(values) {
    return (values || []).map((model) => typeof model === "string"
      ? { id: model, label: model, installed: true, qualified: true, selectable: true }
      : {
        ...model,
        id: model && (model.id || model.model_id || model.name),
        label: model && (model.label || model.id || model.model_id || model.name),
      }).filter((model) => model.id);
  }

  function preferredModel(models, requested = "") {
    const selectable = models.filter((model) => model.selectable !== false && model.installed !== false);
    const ids = selectable.map((model) => model.id);
    if (ids.includes(requested)) return requested;
    const configured = state.spec && state.spec.defaults && state.spec.defaults.model_id;
    if (ids.includes(configured)) return configured;
    const exactPreferred = ids.find((id) => id.replace(/\\/g, "/").toLowerCase() === preferredModelId.toLowerCase());
    if (exactPreferred) return exactPreferred;
    return ids.find((id) => id.toLowerCase().includes(preferredModelFragment.toLowerCase())) || ids[0] || "";
  }

  function populateModels(values, requested = "") {
    const models = normalizedModels(values);
    elements.model.replaceChildren();
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      const qualifiers = [];
      if (model.installed === false) qualifiers.push("non installé");
      if (model.qualified === false) qualifiers.push("non qualifié");
      option.textContent = `${model.label || model.id}${qualifiers.length ? ` · ${qualifiers.join(", ")}` : ""}`;
      option.disabled = model.selectable === false || model.installed === false;
      elements.model.append(option);
    });
    const selected = preferredModel(models, requested);
    if (selected) elements.model.value = selected;
    if (!models.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Aucun modèle KREA2 détecté";
      elements.model.append(option);
    }
  }

  function ratioValue(value) {
    if (typeof value === "string") return value;
    return value && (value.value || value.id || value.aspect_ratio || value.label);
  }

  function populateRatios(values, requested = "") {
    const advertised = new Set((values || []).map(ratioValue).filter(Boolean));
    const ratios = aspectRatioEnum.filter((ratio) => advertised.has(ratio));
    elements.ratio.replaceChildren();
    ratios.forEach((ratio) => {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio;
      elements.ratio.append(option);
    });
    const configured = state.spec && state.spec.defaults && state.spec.defaults.aspect_ratio;
    const selected = ratios.includes(requested) ? requested : ratios.includes(configured) ? configured : ratios[0] || "";
    if (selected) elements.ratio.value = selected;
    if (!ratios.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Aucun ratio disponible";
      elements.ratio.append(option);
    }
  }

  function megapixelLimits(spec) {
    const limits = spec && spec.limits;
    const control = limits && (limits.megapixels || limits.megapixel);
    const values = (spec && spec.megapixels || []).map(Number).filter(Number.isFinite);
    const valuesMinimum = values.length ? Math.min(...values) : 0.5;
    const valuesMaximum = values.length ? Math.max(...values) : 4;
    return {
      minimum: Number(control && (control.minimum ?? control.min)) || valuesMinimum,
      maximum: Number(control && (control.maximum ?? control.max)) || valuesMaximum,
      step: Number(control && control.step) || 0.1,
    };
  }

  function applySpec(spec, { preserve = true } = {}) {
    const previousModel = preserve ? elements.model.value : "";
    const previousRatio = preserve ? elements.ratio.value : "";
    const previousMegapixels = preserve ? elements.megapixels.value : "";
    state.spec = { ...(state.spec || {}), ...(spec || {}) };
    populateModels(state.spec.models, previousModel);
    populateRatios(state.spec.aspect_ratios || state.spec.ratios, previousRatio);
    const limits = megapixelLimits(state.spec);
    elements.megapixels.min = String(limits.minimum);
    elements.megapixels.max = String(limits.maximum);
    elements.megapixels.step = String(limits.step);
    const defaultMp = state.spec.defaults && state.spec.defaults.megapixels;
    if (!previousMegapixels) elements.megapixels.value = String(defaultMp ?? 3);
    updateResolution();
    renderControls();
  }

  async function loadSpec({ preserve = true } = {}) {
    applySpec(await request("/api/image-lab/krea2/spec"), { preserve });
  }

  async function refreshModels() {
    if (state.busy || isActive(state.activeRun)) return;
    elements.refreshModels.disabled = true;
    showFormMessage("");
    try {
      const payload = await request("/api/image-lab/krea2/models/refresh", { method: "POST" });
      if (payload && payload.models) applySpec({ models: payload.models, model_discovery: payload.model_discovery });
      else await loadSpec();
      const discovery = payload && payload.model_discovery;
      showFormMessage(discovery && discovery.error ? discovery.error : "Liste des modèles actualisée.", Boolean(discovery && discovery.error));
    } catch (error) {
      showFormMessage(error.message);
    } finally {
      renderControls();
    }
  }

  function createBody() {
    const defaults = state.spec && state.spec.defaults || {};
    const body = {
      prompt: elements.prompt.value.trim(),
      preset_id: defaults.preset_id,
      model_id: elements.model.value,
      aspect_ratio: elements.ratio.value,
      megapixels: Number(elements.megapixels.value),
      seed: elements.seed.value.trim(),
      seed_locked: elements.seedLock.checked,
    };
    if (!body.preset_id) delete body.preset_id;
    return body;
  }

  function stopPolling() {
    state.pollToken += 1;
    if (state.pollTimer !== null) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function startPolling(id) {
    stopPolling();
    const token = state.pollToken;
    const poll = async () => {
      try {
        const run = unwrapRun(await request(`/api/image-lab/krea2/runs/${encodeURIComponent(id)}`));
        if (token !== state.pollToken) return;
        renderRun(run);
        if (terminalStatuses.has(runStatus(run))) {
          await loadHistory({ followActive: false });
          return;
        }
      } catch (error) {
        if (token === state.pollToken) showRunMessage(error.message, true);
      }
      if (token === state.pollToken) state.pollTimer = window.setTimeout(poll, 1500);
    };
    poll();
  }

  async function startRun(event) {
    event.preventDefault();
    if (state.busy || isActive(state.activeRun)) return;
    const error = validationError();
    if (error) return showFormMessage(error);
    state.busy = true;
    showFormMessage("");
    showRunMessage("");
    stopPolling();
    resetOutput();
    try {
      if (!elements.seedLock.checked) elements.seed.value = randomSeed();
      persistSeedLock();
      const prepared = unwrapRun(await request("/api/image-lab/krea2/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createBody()),
      }));
      if (!prepared || !runId(prepared)) throw new Error("Image Lab a renvoyé un run KREA2 invalide.");
      renderRun(prepared);
      const started = unwrapRun(await request(`/api/image-lab/krea2/runs/${encodeURIComponent(runId(prepared))}/start`, { method: "POST" }));
      renderRun(started ? { ...prepared, ...started } : prepared);
      if (terminalStatuses.has(runStatus(state.activeRun))) await loadHistory({ followActive: false });
      else startPolling(runId(state.activeRun));
    } catch (runError) {
      showFormMessage(runError.message);
    } finally {
      state.busy = false;
      renderControls();
    }
  }

  async function cancelRun() {
    if (state.busy || !isActive(state.activeRun)) return;
    state.busy = true;
    renderControls();
    try {
      const run = unwrapRun(await request(`/api/image-lab/krea2/runs/${encodeURIComponent(runId(state.activeRun))}/cancel`, { method: "POST" }));
      if (run) renderRun(run);
      if (!isActive(run)) stopPolling();
      await loadHistory({ followActive: false });
    } catch (error) {
      showRunMessage(error.message, true);
    } finally {
      state.busy = false;
      renderControls();
    }
  }

  function historyItem(run) {
    const item = document.createElement("li");
    const copy = document.createElement("div");
    const title = document.createElement("b");
    const prompt = String(run.prompt || "").replace(/\s+/g, " ").trim();
    title.textContent = prompt || `Run ${String(runId(run) || "").slice(0, 8)}`;
    const detail = document.createElement("small");
    detail.textContent = [
      statusLabel(runStatus(run)),
      runParameter(run, "aspect_ratio"),
      runParameter(run, "megapixels") ? `${Number(runParameter(run, "megapixels")).toLocaleString("fr-FR")} MP` : "",
      runParameter(run, "seed") !== null ? `seed ${runParameter(run, "seed")}` : "",
    ].filter(Boolean).join(" · ");
    copy.append(title, detail);

    const open = document.createElement("button");
    open.type = "button";
    open.textContent = "Ouvrir";
    open.addEventListener("click", () => openRun(runId(run)));
    const relaunch = document.createElement("button");
    relaunch.type = "button";
    relaunch.textContent = "Relancer";
    relaunch.addEventListener("click", () => prepareFromRun(runId(run)));
    item.append(copy, open, relaunch);
    return item;
  }

  async function loadHistory({ followActive = true } = {}) {
    try {
      const payload = await request("/api/image-lab/krea2/runs?limit=30");
      state.runs = Array.isArray(payload) ? payload : (payload && (payload.runs || payload.items)) || [];
      elements.historyList.replaceChildren();
      elements.historyEmpty.hidden = Boolean(state.runs.length);
      state.runs.forEach((run) => elements.historyList.append(historyItem(unwrapRun(run))));
      if (followActive && !isActive(state.activeRun)) {
        const active = state.runs.map(unwrapRun).find(isActive);
        if (active) {
          renderRun(active);
          startPolling(runId(active));
        }
      }
    } catch (error) {
      elements.historyEmpty.hidden = false;
      elements.historyEmpty.textContent = `Historique indisponible : ${error.message}`;
    }
    renderControls();
  }

  async function openRun(id) {
    if (!id || state.busy || isActive(state.activeRun)) return;
    state.busy = true;
    renderControls();
    try {
      const run = unwrapRun(await request(`/api/image-lab/krea2/runs/${encodeURIComponent(id)}`));
      resetOutput();
      renderRun(run);
      if (isActive(run)) startPolling(runId(run));
      else stopPolling();
      elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showRunMessage(error.message, true);
    } finally {
      state.busy = false;
      renderControls();
    }
  }

  function selectStoredValue(select, value) {
    if (value === null || value === undefined || value === "") return false;
    let option = [...select.options].find((candidate) => candidate.value === String(value));
    if (!option) {
      option = document.createElement("option");
      option.value = String(value);
      option.textContent = `${String(value)} · indisponible`;
      option.disabled = true;
      select.append(option);
    }
    select.value = String(value);
    return !option.disabled;
  }

  function applyRunToForm(run) {
    elements.prompt.value = String(run.prompt || "");
    const modelAvailable = selectStoredValue(elements.model, runParameter(run, "model_id"));
    const ratioAvailable = selectStoredValue(elements.ratio, runParameter(run, "aspect_ratio"));
    if (runParameter(run, "megapixels") !== null) elements.megapixels.value = String(runParameter(run, "megapixels"));
    if (runParameter(run, "seed") !== null) elements.seed.value = String(runParameter(run, "seed"));
    elements.seedLock.checked = true;
    persistSeedLock();
    updateResolution();
    renderControls();
    return { modelAvailable, ratioAvailable };
  }

  async function prepareFromRun(id) {
    if (!id || state.busy || isActive(state.activeRun)) return;
    state.busy = true;
    renderControls();
    try {
      const run = unwrapRun(await request(`/api/image-lab/krea2/runs/${encodeURIComponent(id)}`));
      const availability = applyRunToForm(run);
      const unavailable = [
        availability.modelAvailable ? "" : "le modèle",
        availability.ratioAvailable ? "" : "le ratio",
      ].filter(Boolean).join(" et ");
      showFormMessage(
        unavailable
          ? `Réglages repris. Valeurs indisponibles : ${unavailable}. Choisissez une valeur disponible avant de relancer.`
          : "Réglages repris. Vérifiez-les avant de relancer.",
        Boolean(unavailable),
      );
      elements.prompt.focus();
    } catch (error) {
      showFormMessage(error.message);
    } finally {
      state.busy = false;
      renderControls();
    }
  }

  function persistSeedLock() {
    try {
      if (!elements.seedLock.checked) {
        window.localStorage.removeItem(seedStorageKey);
        return;
      }
      if (validSeed(elements.seed.value.trim())) {
        window.localStorage.setItem(seedStorageKey, JSON.stringify({ locked: true, seed: elements.seed.value.trim() }));
      }
    } catch (_) { /* private mode */ }
  }

  function restoreSeedLock() {
    try {
      const stored = window.localStorage.getItem(seedStorageKey);
      if (stored === "1") {
        elements.seedLock.checked = true;
        return;
      }
      const parsed = JSON.parse(stored || "null");
      elements.seedLock.checked = Boolean(parsed && parsed.locked);
      if (elements.seedLock.checked && validSeed(parsed.seed)) elements.seed.value = String(parsed.seed);
    } catch (_) { elements.seedLock.checked = false; }
  }

  async function initialize() {
    if (state.initialized) return true;
    if (state.initializing) return state.initializing;
    state.initializing = Promise.allSettled([loadSpec({ preserve: false }), loadHistory()]).then((results) => {
      const specFailure = results[0].status === "rejected" ? results[0].reason : null;
      state.initialized = !specFailure;
      state.initializationError = specFailure;
      if (specFailure) showFormMessage(`Image Lab KREA2 indisponible : ${specFailure.message}`);
      if (!elements.seed.value) elements.seed.value = randomSeed();
      renderControls();
      return !specFailure;
    }).finally(() => { state.initializing = null; });
    return state.initializing;
  }

  elements.form.addEventListener("submit", startRun);
  elements.prompt.addEventListener("input", renderControls);
  elements.model.addEventListener("change", renderControls);
  elements.ratio.addEventListener("change", () => { updateResolution(); renderControls(); });
  elements.megapixels.addEventListener("input", () => { updateResolution(); renderControls(); });
  elements.seed.addEventListener("input", () => { persistSeedLock(); renderControls(); });
  elements.seedLock.addEventListener("change", persistSeedLock);
  elements.randomizeSeed.addEventListener("click", () => { elements.seed.value = randomSeed(); persistSeedLock(); renderControls(); });
  elements.refreshModels.addEventListener("click", refreshModels);
  elements.cancel.addEventListener("click", cancelRun);
  elements.reuseSeed.addEventListener("click", () => {
    const seed = runParameter(state.activeRun, "seed");
    if (seed === null) return;
    elements.seed.value = String(seed);
    elements.seedLock.checked = true;
    persistSeedLock();
    showFormMessage("Seed du run réutilisée et verrouillée.", false);
    renderControls();
  });
  elements.refresh.addEventListener("click", () => loadHistory());
  elements.modeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.imageLabMode;
      if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView(view);
      if (view === "krea2-image-lab") initialize();
    });
  });

  elements.seed.value = randomSeed();
  restoreSeedLock();
  window.PanelForgeKrea2ImageLab = Object.freeze({
    open: async () => {
      if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView("krea2-image-lab");
      return initialize();
    },
  });
  resetOutput();
  renderRun(null);
})();
