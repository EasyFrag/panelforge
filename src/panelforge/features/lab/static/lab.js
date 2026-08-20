"use strict";

const $ = (id) => document.getElementById(id);
const preferredPromptModelId = "Qwen3.8-27B";
window.PanelForgeModelPicker = Object.freeze({
  preferredModelId: preferredPromptModelId,
  populate(select, models, currentValue = "") {
    const identifiers = (models || []).map((model) => model.id);
    select.replaceChildren();
    (models || []).forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.id;
      select.append(option);
    });
    const preferredLower = preferredPromptModelId.toLowerCase();
    const preferred = identifiers.find((id) => id.toLowerCase() === preferredLower)
      || identifiers.find((id) => id.toLowerCase().includes("qwen3.8-27b"))
      || identifiers.find((id) => id.toLowerCase().includes("qwen3.6-27b"))
      || identifiers[0]
      || "";
    select.value = identifiers.includes(currentValue) ? currentValue : preferred;
    return select.value;
  },
});
const ui = {};
const state = {
  spec: null,
  file: null,
  sourceAssetId: null,
  sourceUrl: null,
  objectUrl: null,
  runId: null,
  busy: false,
  previewRequest: 0,
  pollFailures: 0,
  runtimeMessageTimer: null,
  runtimeStatus: null,
  runtimePollTimer: null,
  runtimePollActive: false,
  runtimeSocket: null,
  runtimeSocketTimer: null,
  runtimeTelemetryAt: 0,
};

const angleIcons = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"];
const terminal = new Set(["succeeded", "failed"]);

document.addEventListener("DOMContentLoaded", async () => {
  for (const id of [
    "recipe-version", "run-form", "source-image", "dropzone", "drop-empty",
    "drop-preview", "source-thumb", "source-kind", "source-name", "azimuths",
    "elevation", "shot-size", "lora-strength", "lora-value", "lora-warning",
    "seed", "compiled-prompt", "form-error", "generate", "run-status",
    "source-caption", "source-empty", "source-large", "result-caption",
    "result-empty", "result-loading", "result-image", "run-message", "keep",
    "reject", "reuse", "refresh", "history-empty", "history-list",
    "release-llm-vram", "release-comfy-vram", "runtime-message",
    "runtime-monitor", "runtime-vram", "runtime-temp",
    "runtime-services",
  ]) ui[id] = $(id);

  bindEvents();
  startRuntimeMonitor();
  await Promise.allSettled([loadSpec(), loadHistory()]);
});

function bindEvents() {
  ui["source-image"].addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) selectFile(file);
  });
  for (const name of ["dragenter", "dragover", "dragleave", "drop"]) {
    ui.dropzone.addEventListener(name, (event) => event.preventDefault());
  }
  for (const name of ["dragenter", "dragover"]) {
    ui.dropzone.addEventListener(name, () => ui.dropzone.classList.add("dragging"));
  }
  for (const name of ["dragleave", "drop"]) {
    ui.dropzone.addEventListener(name, () => ui.dropzone.classList.remove("dragging"));
  }
  ui.dropzone.addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    if (file) selectFile(file);
  });
  ui.azimuths.addEventListener("change", previewPrompt);
  ui.elevation.addEventListener("change", previewPrompt);
  ui["shot-size"].addEventListener("change", previewPrompt);
  ui["lora-strength"].addEventListener("input", renderLora);
  ui["run-form"].addEventListener("submit", startRun);
  ui.keep.addEventListener("click", () => review("kept"));
  ui.reject.addEventListener("click", () => review("rejected"));
  ui.reuse.addEventListener("click", reuseResult);
  ui.refresh.addEventListener("click", loadHistory);
  ui["release-llm-vram"].addEventListener("click", releaseLlmVram);
  ui["release-comfy-vram"].addEventListener("click", releaseComfyVram);
  document.addEventListener("visibilitychange", handleRuntimeVisibility);
  window.addEventListener("beforeunload", () => {
    stopRuntimeMonitor();
    revokeObjectUrl();
  });
}

async function releaseLlmVram() {
  await releaseRuntime({
    button: ui["release-llm-vram"],
    url: "/api/model-runtime/unload",
    busyLabel: "LLM…",
    idleLabel: "VRAM LLM",
  });
}

async function releaseComfyVram() {
  await releaseRuntime({
    button: ui["release-comfy-vram"],
    url: "/api/comfy-runtime/free",
    busyLabel: "Comfy…",
    idleLabel: "VRAM Comfy",
  });
}

async function releaseRuntime({ button, url, busyLabel, idleLabel }) {
  button.disabled = true;
  button.textContent = busyLabel;
  try {
    const result = await json(url, { method: "POST" });
    showRuntimeMessage(result.message || "Nettoyage demandé.");
  } catch (error) {
    showRuntimeMessage(error.message, "warning");
  } finally {
    button.textContent = idleLabel;
    await refreshRuntimeStatus();
  }
}

function showRuntimeMessage(message, tone = "success") {
  const view = ui["runtime-message"];
  if (state.runtimeMessageTimer !== null) {
    window.clearTimeout(state.runtimeMessageTimer);
  }
  view.textContent = message;
  view.classList.toggle("failed", tone === "failed");
  view.classList.toggle("warning", tone === "warning");
  view.hidden = false;
  state.runtimeMessageTimer = window.setTimeout(() => {
    view.hidden = true;
    state.runtimeMessageTimer = null;
  }, tone === "success" ? 5000 : 8000);
}

function startRuntimeMonitor() {
  refreshRuntimeStatus();
  connectRuntimeMonitor();
}

function stopRuntimeMonitor() {
  if (state.runtimePollTimer !== null) window.clearTimeout(state.runtimePollTimer);
  if (state.runtimeSocketTimer !== null) window.clearTimeout(state.runtimeSocketTimer);
  state.runtimePollTimer = null;
  state.runtimeSocketTimer = null;
  if (state.runtimeSocket) state.runtimeSocket.close();
  state.runtimeSocket = null;
}

function handleRuntimeVisibility() {
  if (document.visibilityState !== "visible") return;
  refreshRuntimeStatus();
  if (!state.runtimeSocket || state.runtimeSocket.readyState > WebSocket.OPEN) {
    connectRuntimeMonitor();
  }
}

async function refreshRuntimeStatus() {
  if (state.runtimePollActive) return;
  if (state.runtimePollTimer !== null) window.clearTimeout(state.runtimePollTimer);
  state.runtimePollTimer = null;
  if (document.visibilityState !== "visible") {
    scheduleRuntimePoll();
    return;
  }
  state.runtimePollActive = true;
  try {
    state.runtimeStatus = await json("/api/runtime/status");
    renderRuntimeStatus();
  } catch (_) {
    state.runtimeStatus = null;
    renderRuntimeStatus();
  } finally {
    state.runtimePollActive = false;
    scheduleRuntimePoll();
  }
}

function scheduleRuntimePoll() {
  if (state.runtimePollTimer !== null) window.clearTimeout(state.runtimePollTimer);
  state.runtimePollTimer = window.setTimeout(refreshRuntimeStatus, 1000);
}

function renderRuntimeStatus() {
  const snapshot = state.runtimeStatus;
  const gpu = snapshot && snapshot.gpu;
  const comfy = snapshot && snapshot.comfy;
  const llm = snapshot && snapshot.llm;
  const liveTelemetry = Date.now() - state.runtimeTelemetryAt < 5000;
  if (!liveTelemetry) {
    ui["runtime-temp"].textContent = "Temp —";
    setRuntimeMeter(ui["runtime-temp"], 0, null);
  }
  if (gpu && gpu.available) {
    const used = formatBytes(gpu.used_bytes);
    const total = formatBytes(gpu.total_bytes);
    const percent = Number(gpu.used_percent);
    ui["runtime-vram"].textContent = `VRAM ${percent.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}% · ${used}/${total}`;
    renderVramMeter(percent);
    ui["runtime-monitor"].title = `${gpu.name} · VRAM globale, sans attribution par processus.`;
  } else {
    ui["runtime-vram"].textContent = "VRAM —";
    setRuntimeMeter(ui["runtime-vram"], 0, null);
  }
  const serviceWarnings = [];
  if (!comfy?.available) serviceWarnings.push("Comfy indisponible");
  if (!llm?.available) serviceWarnings.push("LLM indisponible");
  ui["runtime-services"].textContent = serviceWarnings.join(" · ");
  ui["runtime-services"].hidden = serviceWarnings.length === 0;
  ui["release-comfy-vram"].disabled = !comfy?.available || !comfy.cleanup_allowed;
  ui["release-comfy-vram"].title = !comfy?.available
    ? "ComfyUI indisponible."
    : !comfy.cleanup_allowed
      ? "Nettoyage indisponible pendant un rendu ComfyUI actif ou en attente."
      : "Décharge les modèles et caches ComfyUI.";
  ui["release-llm-vram"].disabled = !llm?.available;
  ui["release-llm-vram"].title = llm?.available
    ? "Décharge les modèles actuellement chargés par llama.swap."
    : "llama.swap indisponible.";
}

function connectRuntimeMonitor() {
  if (document.visibilityState !== "visible") return;
  if (state.runtimeSocket && state.runtimeSocket.readyState <= WebSocket.OPEN) return;
  if (state.runtimeSocketTimer !== null) window.clearTimeout(state.runtimeSocketTimer);
  state.runtimeSocketTimer = null;
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${scheme}//${window.location.host}/api/runtime/events`);
  state.runtimeSocket = socket;
  socket.addEventListener("message", (event) => {
    let payload;
    try { payload = JSON.parse(event.data); } catch (_) { return; }
    if (payload.type !== "crystools.monitor" || !payload.data) return;
    renderCrystools(payload.data);
  });
  socket.addEventListener("close", () => {
    if (state.runtimeSocket === socket) state.runtimeSocket = null;
    scheduleRuntimeReconnect();
  });
  socket.addEventListener("error", () => socket.close());
}

function scheduleRuntimeReconnect() {
  if (state.runtimeSocketTimer !== null || document.visibilityState !== "visible") return;
  state.runtimeSocketTimer = window.setTimeout(() => {
    state.runtimeSocketTimer = null;
    connectRuntimeMonitor();
  }, 4000);
}

function renderCrystools(data) {
  const gpus = Array.isArray(data.gpus) ? data.gpus : [];
  const gpu = gpus[0];
  if (!gpu) return;
  const temperature = Number(gpu.gpu_temperature);
  if (Number.isFinite(temperature)) {
    state.runtimeTelemetryAt = Date.now();
    renderTemperatureMeter(temperature);
  }
}

function renderVramMeter(percent) {
  setRuntimeMeter(ui["runtime-vram"], percent, percent > 30 ? "yellow" : "green");
}

function renderTemperatureMeter(temperature) {
  const gaugePercent = ((temperature - 25) / (100 - 25)) * 100;
  const tone = temperature <= 60 ? "green" : temperature <= 80 ? "orange" : "red";
  ui["runtime-temp"].textContent = `Temp ${Math.round(temperature)}°C`;
  setRuntimeMeter(ui["runtime-temp"], gaugePercent, tone);
}

function setRuntimeMeter(element, percent, tone) {
  const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
  element.style.setProperty("--runtime-meter-percent", `${clamped}%`);
  element.classList.remove("meter-green", "meter-yellow", "meter-orange", "meter-red");
  if (tone) element.classList.add(`meter-${tone}`);
}

function formatBytes(value) {
  const gib = Number(value) / (1024 ** 3);
  if (!Number.isFinite(gib)) return "—";
  return `${gib.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Gio`;
}

async function loadSpec() {
  try {
    state.spec = await json("/api/change-view/spec");
    ui["recipe-version"].textContent = `v${state.spec.recipe.version}`;
    const controls = state.spec.controls;
    renderAzimuths(controls.azimuth);
    renderSelect(ui.elevation, controls.elevation);
    renderSelect(ui["shot-size"], controls.shot_size);
    const lora = controls.multiple_angles_lora_strength;
    Object.assign(ui["lora-strength"], {
      min: lora.minimum, max: lora.maximum, step: lora.step, value: lora.default,
    });
    ui.seed.value = String(controls.seed.default);
    renderLora();
    await previewPrompt();
  } catch (error) {
    showError(`Impossible de charger la recette : ${error.message}`);
  }
  updateGenerate();
}

function renderAzimuths(control) {
  ui.azimuths.replaceChildren();
  control.options.forEach((option, index) => {
    const label = document.createElement("label");
    label.className = "azimuth";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "azimuth";
    input.value = option.value;
    input.checked = option.value === control.default;
    const text = document.createElement("span");
    const icon = document.createElement("b");
    icon.textContent = angleIcons[index] || "•";
    text.append(icon, document.createTextNode(option.label));
    label.append(input, text);
    ui.azimuths.append(label);
  });
}

function renderSelect(select, control) {
  select.replaceChildren();
  for (const option of control.options) {
    const element = document.createElement("option");
    element.value = option.value;
    element.textContent = option.label;
    element.selected = option.value === control.default;
    select.append(element);
  }
}

async function previewPrompt() {
  if (!state.spec) return;
  const requestId = ++state.previewRequest;
  try {
    const result = await json("/api/change-view/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentView()),
    });
    if (requestId === state.previewRequest) {
      ui["compiled-prompt"].value = result.compiled_prompt;
    }
  } catch (error) {
    if (requestId === state.previewRequest) showError(error.message);
  }
}

function currentView() {
  const angle = ui.azimuths.querySelector("input:checked");
  return {
    azimuth: angle ? angle.value : "front",
    elevation: ui.elevation.value,
    shot_size: ui["shot-size"].value,
  };
}

function renderLora() {
  const value = Number(ui["lora-strength"].value);
  ui["lora-value"].textContent = value.toLocaleString("fr-FR", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
  const defaultValue = state.spec
    ? Number(state.spec.controls.multiple_angles_lora_strength.default)
    : 1;
  ui["lora-warning"].hidden = value === defaultValue;
}

function selectFile(file) {
  if (!new Set(["image/png", "image/jpeg", "image/webp"]).has(file.type)) {
    showError("Choisissez une image PNG, JPEG ou WebP.");
    return;
  }
  revokeObjectUrl();
  state.file = file;
  state.sourceAssetId = null;
  state.objectUrl = URL.createObjectURL(file);
  showSource(state.objectUrl, file.name, "Fichier local");
  updateGenerate();
}

function showSource(url, caption, kind) {
  state.sourceUrl = url;
  ui["source-thumb"].src = url;
  ui["source-large"].src = url;
  ui["source-thumb"].hidden = false;
  ui["source-large"].hidden = false;
  ui["drop-empty"].hidden = true;
  ui["drop-preview"].hidden = false;
  ui["source-empty"].hidden = true;
  ui["source-name"].textContent = caption;
  ui["source-caption"].textContent = caption;
  ui["source-kind"].textContent = kind;
}

async function startRun(event) {
  event.preventDefault();
  hideError();
  const seed = ui.seed.value.trim();
  if (!validSeed(seed)) return showError("La seed doit être un entier entre 0 et 2⁶⁴−1.");

  const data = new FormData();
  if (state.file) data.append("source_image", state.file, state.file.name);
  else data.append("source_asset_id", state.sourceAssetId);
  const view = currentView();
  for (const [key, value] of Object.entries(view)) data.append(key, value);
  data.append("lora_strength", ui["lora-strength"].value);
  data.append("seed", seed);

  setBusy(true);
  try {
    const run = await json("/api/runs", { method: "POST", body: data });
    state.runId = run.run_id;
    state.pollFailures = 0;
    renderRun(run);
    window.setTimeout(pollRun, 700);
  } catch (error) {
    setBusy(false);
    showError(error.message);
  }
}

async function pollRun() {
  const expected = state.runId;
  if (!expected) return;
  try {
    const run = await json(`/api/runs/${encodeURIComponent(expected)}`);
    if (run.run_id !== expected || state.runId !== expected) return;
    state.pollFailures = 0;
    renderRun(run);
    if (terminal.has(run.status)) {
      setBusy(false);
      await loadHistory();
    } else window.setTimeout(pollRun, 1200);
  } catch (error) {
    state.pollFailures += 1;
    ui["run-message"].textContent = `Suivi interrompu (${state.pollFailures}/5) : ${error.message}`;
    if (state.pollFailures < 5) window.setTimeout(pollRun, 1800);
    else setBusy(false);
  }
}

function renderRun(run) {
  state.runId = run.run_id;
  ui["compiled-prompt"].value = run.compiled_prompt;
  const active = run.status === "created" || run.status === "submitted";
  ui["run-status"].className = `run-status ${active ? "active" : run.status === "succeeded" ? "success" : "failed"}`;
  ui["run-status"].textContent = `● ${active ? "Génération" : run.status === "succeeded" ? "Terminé" : "Échec"}`;
  ui["result-loading"].hidden = !active;
  ui["result-empty"].hidden = active || run.status === "succeeded";
  ui["result-caption"].textContent = run.run_id.slice(0, 12);
  ui["run-message"].classList.toggle("error-text", run.status === "failed");
  ui["run-message"].textContent = run.error || (active ? "ComfyUI prépare le candidat…" : "Comparez puis conservez ou rejetez ce candidat.");
  if (run.result_url) {
    ui["result-image"].src = run.result_url;
    ui["result-image"].hidden = false;
  } else ui["result-image"].hidden = true;
  const ready = run.status === "succeeded";
  for (const button of [ui.keep, ui.reject, ui.reuse]) button.disabled = !ready;
  ui.keep.classList.toggle("selected", run.decision === "kept");
  ui.reject.classList.toggle("selected", run.decision === "rejected");
  if (run.source_url && !state.file && !state.sourceAssetId) {
    showSource(run.source_url, run.source_asset_id, "Asset");
  }
}

async function review(decision) {
  if (!state.runId) return;
  try {
    const run = await json(`/api/runs/${encodeURIComponent(state.runId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    renderRun(run);
    await loadHistory();
  } catch (error) { showError(error.message); }
}

async function reuseResult() {
  if (!state.runId) return;
  try {
    const result = await json(`/api/runs/${encodeURIComponent(state.runId)}/reuse`, { method: "POST" });
    revokeObjectUrl();
    state.file = null;
    state.sourceAssetId = result.source_asset_id;
    ui["source-image"].value = "";
    showSource(result.content_url, result.source_asset_id, "Candidat réutilisé");
    updateGenerate();
  } catch (error) { showError(error.message); }
}

async function loadHistory() {
  try {
    const result = await json("/api/runs?limit=20");
    ui["history-list"].replaceChildren();
    ui["history-empty"].hidden = result.runs.length > 0;
    for (const run of result.runs) {
      const item = document.createElement("li");
      const description = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = `${run.controls.azimuth} · ${run.controls.shot_size}`;
      const meta = document.createElement("small");
      meta.textContent = `${run.status} · ${run.decision}`;
      description.append(title, meta);
      const open = document.createElement("button");
      open.type = "button";
      open.textContent = "Voir";
      open.addEventListener("click", () => openRun(run.run_id));
      item.append(description, open);
      ui["history-list"].append(item);
    }
  } catch (error) {
    ui["history-empty"].hidden = false;
    ui["history-empty"].textContent = `Historique indisponible : ${error.message}`;
  }
}

async function openRun(runId) {
  try {
    const run = await json(`/api/runs/${encodeURIComponent(runId)}`);
    state.file = null;
    state.sourceAssetId = run.source_asset_id;
    showSource(run.source_url, run.source_asset_id, "Asset historique");
    renderRun(run);
  } catch (error) { showError(error.message); }
}

function setBusy(value) { state.busy = value; ui.generate.disabled = !canGenerate(); }
function updateGenerate() { ui.generate.disabled = !canGenerate(); }
function canGenerate() { return Boolean(!state.busy && state.spec && (state.file || state.sourceAssetId)); }
function validSeed(seed) {
  const max = "18446744073709551615";
  const normalized = seed.replace(/^0+(?=\d)/, "");
  return /^\d+$/.test(seed) && (normalized.length < max.length || (normalized.length === max.length && normalized <= max));
}
function showError(message) { ui["form-error"].textContent = message; ui["form-error"].hidden = false; }
function hideError() { ui["form-error"].hidden = true; ui["form-error"].textContent = ""; }
function revokeObjectUrl() { if (state.objectUrl) URL.revokeObjectURL(state.objectUrl); state.objectUrl = null; }

async function json(url, options = {}) {
  const { headers = {}, ...request } = options;
  const response = await fetch(url, { ...request, headers: { Accept: "application/json", ...headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `Erreur HTTP ${response.status}`);
  return payload;
}
