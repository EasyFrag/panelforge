(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["succeeded", "completed", "failed", "cancelled", "canceled"]);
  const seedStorageKey = "panelforge.video-lab.seed-lock";
  const fallbackPreset = Object.freeze({
    id: "h3-balanced",
    label: "H3 équilibré",
    aspect_ratio: "2:3 (Portrait Photo)",
    megapixels: 0.6,
    duration_seconds: 10,
    steps: 32,
  });

  const elements = {
    workspace: $("video-lab-workspace"),
    form: $("video-lab-form"),
    images: $("video-lab-images"),
    imageCount: $("video-lab-image-count"),
    references: $("video-lab-reference-list"),
    prompt: $("video-lab-prompt"),
    preset: $("video-lab-preset"),
    ratio: $("video-lab-ratio"),
    megapixels: $("video-lab-megapixels"),
    duration: $("video-lab-duration"),
    steps: $("video-lab-steps"),
    effectiveDuration: $("video-lab-effective-duration"),
    seed: $("video-lab-seed"),
    seedLock: $("video-lab-seed-lock"),
    randomizeSeed: $("video-lab-randomize-seed"),
    generate: $("video-lab-generate"),
    formMessage: $("video-lab-form-message"),
    status: $("video-lab-status"),
    preview: $("video-lab-preview"),
    previewVideo: $("video-lab-preview-video"),
    previewEmpty: $("video-lab-preview-empty"),
    previewCaption: $("video-lab-preview-caption"),
    output: $("video-lab-output"),
    outputEmpty: $("video-lab-output-empty"),
    outputCaption: $("video-lab-output-caption"),
    playWithSound: $("video-lab-play-with-sound"),
    outputDiagnostic: $("video-lab-output-diagnostic"),
    progress: $("video-lab-progress"),
    progressLabel: $("video-lab-progress-label"),
    runMessage: $("video-lab-run-message"),
    cancel: $("video-lab-cancel"),
    reuseSeed: $("video-lab-reuse-seed"),
    download: $("video-lab-download"),
    refresh: $("video-lab-refresh"),
    historyEmpty: $("video-lab-history-empty"),
    historyList: $("video-lab-history-list"),
  };
  if (!elements.workspace) return;

  const state = {
    spec: null,
    presets: [fallbackPreset],
    references: [],
    activeRun: null,
    busy: false,
    socket: null,
    pollTimer: null,
    pollToken: 0,
    previewObjectUrl: null,
    previewConnection: "idle",
    outputCanonicalUrl: null,
    outputPlaybackUrl: null,
    audioDiagnosticTimer: null,
    specReady: false,
    pendingPrefill: null,
  };

  function randomSeed() {
    if (window.crypto && window.crypto.getRandomValues && typeof BigInt === "function") {
      const words = new Uint32Array(2);
      window.crypto.getRandomValues(words);
      return (((BigInt(words[0]) << 32n) | BigInt(words[1])) & 0x7fffffffffffffffn).toString();
    }
    return String(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER));
  }

  function request(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      let payload = null;
      try { payload = await response.json(); } catch (_) { /* empty response */ }
      if (!response.ok) {
        const detail = payload && payload.detail;
        throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
      }
      return payload;
    });
  }

  function unwrapRun(payload) {
    return payload && payload.run ? payload.run : payload;
  }

  function runId(run) {
    return run && (run.id || run.run_id);
  }

  function restoreSeed() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(seedStorageKey) || "null");
      if (saved && saved.locked && /^\d+$/.test(String(saved.value || ""))) {
        elements.seed.value = String(saved.value);
        elements.seedLock.checked = true;
        return;
      }
    } catch (_) { /* invalid local preference */ }
    elements.seed.value = randomSeed();
    elements.seedLock.checked = false;
  }

  function persistSeedLock() {
    try {
      if (elements.seedLock.checked && /^\d+$/.test(elements.seed.value.trim())) {
        window.localStorage.setItem(seedStorageKey, JSON.stringify({
          locked: true,
          value: elements.seed.value.trim(),
        }));
      } else {
        window.localStorage.removeItem(seedStorageKey);
      }
    } catch (_) { /* storage may be unavailable */ }
  }

  function showFormMessage(message, failed = true) {
    elements.formMessage.textContent = message || "";
    elements.formMessage.classList.toggle("video-lab-info", !failed);
    elements.formMessage.hidden = !message;
  }

  function normalizePreset(value, index = 0) {
    return {
      id: value.id || value.preset_id || `preset-${index + 1}`,
      label: value.label || value.display_name || value.name || `Preset ${index + 1}`,
      aspect_ratio: value.aspect_ratio || value.ratio || fallbackPreset.aspect_ratio,
      megapixels: Number(value.megapixels ?? value.megapixel ?? fallbackPreset.megapixels),
      duration_seconds: Number(value.duration_seconds ?? value.duration ?? fallbackPreset.duration_seconds),
      steps: Number(value.steps ?? fallbackPreset.steps),
      frames: Number(value.frames ?? value.frame_count) || null,
      effective_duration_seconds: Number(value.effective_duration_seconds) || null,
    };
  }

  async function loadSpec() {
    try {
      const payload = await request("/api/video-lab/spec");
      state.spec = payload || {};
      const presets = Array.isArray(payload && payload.presets) ? payload.presets : [];
      state.presets = presets.length
        ? presets.map(normalizePreset)
        : [normalizePreset((payload && payload.preset) || fallbackPreset)];
      renderPresetOptions();
      applyPreset((payload && payload.defaults && payload.defaults.preset_id)
        || (payload && payload.default_preset_id)
        || state.presets[0].id);
      const durationLimits = payload.duration_seconds || (payload.limits && payload.limits.duration_seconds) || {};
      elements.duration.min = String(durationLimits.minimum ?? durationLimits.min ?? 5);
      elements.duration.max = String(durationLimits.maximum ?? durationLimits.max ?? 15);
    } catch (error) {
      state.presets = [fallbackPreset];
      renderPresetOptions();
      applyPreset(fallbackPreset.id);
      showFormMessage(`Video Lab indisponible : ${error.message}`);
    } finally {
      state.specReady = true;
      if (state.pendingPrefill) {
        const pending = state.pendingPrefill;
        state.pendingPrefill = null;
        applyPrefill(pending);
      }
    }
  }

  function unique(values) {
    return [...new Set(values.filter((value) => value !== null && value !== undefined && value !== ""))];
  }

  function optionValue(value) {
    return value && typeof value === "object"
      ? value.value ?? value.id ?? value.megapixels
      : value;
  }

  function renderSelect(select, values, current, label) {
    select.replaceChildren();
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = label(value);
      select.append(option);
    });
    if (!values.some((value) => String(value) === String(current))) {
      const custom = document.createElement("option");
      custom.value = String(current);
      custom.textContent = label(current);
      select.append(custom);
    }
    select.value = String(current);
  }

  function renderPresetOptions() {
    elements.preset.replaceChildren();
    state.presets.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.id;
      option.textContent = preset.label;
      elements.preset.append(option);
    });
    const ratios = unique([
      ...((state.spec && state.spec.aspect_ratios) || []).map(optionValue),
      ...state.presets.map((preset) => preset.aspect_ratio),
    ]);
    const megapixels = unique([
      ...((state.spec && state.spec.megapixels) || []).map(optionValue),
      ...state.presets.map((preset) => preset.megapixels),
    ]);
    renderSelect(elements.ratio, ratios.length ? ratios : [fallbackPreset.aspect_ratio], elements.ratio.value || fallbackPreset.aspect_ratio, String);
    renderSelect(elements.megapixels, megapixels.length ? megapixels : [fallbackPreset.megapixels], elements.megapixels.value || fallbackPreset.megapixels, (value) => `${Number(value).toLocaleString("fr-FR")} MP`);
  }

  function applyPreset(presetId) {
    const preset = state.presets.find((item) => item.id === presetId) || state.presets[0];
    if (!preset) return;
    elements.preset.value = preset.id;
    renderSelect(elements.ratio, unique([...elements.ratio.options].map((option) => option.value).concat(preset.aspect_ratio)), preset.aspect_ratio, String);
    renderSelect(elements.megapixels, unique([...elements.megapixels.options].map((option) => option.value).concat(String(preset.megapixels))), preset.megapixels, (value) => `${Number(value).toLocaleString("fr-FR")} MP`);
    elements.duration.value = String(preset.duration_seconds);
    elements.steps.value = String(preset.steps);
    renderEffectiveDuration();
    render();
  }

  function renderEffectiveDuration() {
    const duration = Number(elements.duration.value);
    const matching = state.presets.find((preset) => (
      Number(preset.duration_seconds) === duration
      && preset.aspect_ratio === elements.ratio.value
      && Number(preset.megapixels) === Number(elements.megapixels.value)
    ));
    if (matching && (matching.frames || matching.effective_duration_seconds)) {
      const fps = Number(state.spec && state.spec.fps) || 24;
      const parts = [`${duration.toLocaleString("fr-FR")} s demandées`];
      if (matching.frames) parts.push(`${matching.frames} frames / ${fps} fps`);
      if (matching.effective_duration_seconds) parts.push(`${matching.effective_duration_seconds.toLocaleString("fr-FR")} s effectives`);
      elements.effectiveDuration.textContent = parts.join(" · ");
    } else {
      const fps = Number(state.spec && state.spec.fps) || 24;
      const frameDivisor = Number(state.spec && state.spec.frame_divisor) || 17;
      const frameRemainder = Number(state.spec && state.spec.frame_remainder) || 5;
      const requestedFrames = Math.max(5, Math.round(duration * fps));
      const frames = requestedFrames + (frameRemainder - requestedFrames % frameDivisor + frameDivisor) % frameDivisor;
      const effective = frames / fps;
      elements.effectiveDuration.textContent = Number.isFinite(effective)
        ? `${duration.toLocaleString("fr-FR")} s demandées · ${frames} frames / ${fps} fps · ${effective.toLocaleString("fr-FR", { maximumFractionDigits: 3 })} s effectives`
        : "Durée effective et nombre de frames calculés à l’envoi.";
    }
  }

  function referenceName(reference, index) {
    return reference.name || reference.label || `Picture ${index + 1}`;
  }

  function renderReferences() {
    elements.references.replaceChildren();
    elements.imageCount.textContent = `${state.references.length} / 3`;
    elements.images.disabled = state.busy || isActive(state.activeRun) || state.references.length >= 3;
    if (!state.references.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Ajoutez au moins une image.";
      elements.references.append(empty);
      return;
    }
    state.references.forEach((reference, index) => {
      const card = document.createElement("article");
      card.className = "video-lab-reference-card";
      const image = document.createElement("img");
      image.src = reference.previewUrl || reference.content_url;
      image.alt = `Aperçu Picture ${index + 1}`;
      const copy = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = `<Picture ${index + 1}>`;
      const name = document.createElement("small");
      name.textContent = referenceName(reference, index);
      copy.append(title, name);
      const actions = document.createElement("div");
      actions.className = "video-lab-reference-actions";
      actions.append(
        referenceButton("↑", "Monter", () => moveReference(index, -1), index === 0),
        referenceButton("↓", "Descendre", () => moveReference(index, 1), index === state.references.length - 1),
        referenceButton("Retirer", "Retirer", () => removeReference(index)),
      );
      card.append(image, copy, actions);
      elements.references.append(card);
    });
  }

  function referenceButton(text, label, action, disabled = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = label;
    button.setAttribute("aria-label", label);
    button.disabled = state.busy || disabled;
    button.addEventListener("click", action);
    return button;
  }

  function moveReference(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= state.references.length) return;
    [state.references[index], state.references[target]] = [state.references[target], state.references[index]];
    render();
  }

  function removeReference(index) {
    const [removed] = state.references.splice(index, 1);
    if (removed && removed.objectUrl) URL.revokeObjectURL(removed.objectUrl);
    render();
  }

  async function materializeAssetReferences() {
    const remote = state.references.filter((reference) => reference.assetId && !reference.file);
    if (!remote.length) return;
    await Promise.all(remote.map(async (reference, index) => {
      const response = await fetch(reference.contentUrl || reference.content_url);
      if (!response.ok) throw new Error(`Impossible de relire ${referenceName(reference, index)}.`);
      const blob = await response.blob();
      reference.file = new File([blob], referenceName(reference, index), {
        type: blob.type || "application/octet-stream",
      });
      reference.assetId = null;
    }));
  }

  async function addFiles(fileList) {
    const files = [...fileList];
    elements.images.value = "";
    if (!files.length) return;
    try {
      if (state.references.some((reference) => reference.assetId)) {
        await materializeAssetReferences();
      }
      const available = Math.max(0, 3 - state.references.length);
      files.slice(0, available).forEach((file) => {
        const objectUrl = URL.createObjectURL(file);
        state.references.push({ file, name: file.name, previewUrl: objectUrl, objectUrl });
      });
      showFormMessage(files.length > available ? "Trois images maximum ; les fichiers supplémentaires ont été ignorés." : "", files.length > available);
    } catch (error) {
      showFormMessage(error.message);
    }
    render();
  }

  function validationError() {
    if (!state.references.length) return "Ajoutez au moins une image.";
    if (state.references.length > 3) return "Trois images maximum.";
    if (!elements.prompt.value.trim()) return "Saisissez le prompt H3.";
    if (!/^\d+$/.test(elements.seed.value.trim())) return "La seed doit être un entier positif.";
    try {
      if (BigInt(elements.seed.value.trim()) >= (1n << 64n)) return "La seed dépasse la limite 64 bits.";
    } catch (_) { return "La seed doit être un entier positif."; }
    const duration = Number(elements.duration.value);
    const minimumDuration = Number(elements.duration.min) || 5;
    const maximumDuration = Number(elements.duration.max) || 15;
    if (!Number.isFinite(duration) || duration < minimumDuration || duration > maximumDuration) {
      return `La durée doit rester entre ${minimumDuration} et ${maximumDuration} secondes.`;
    }
    const megapixels = Number(elements.megapixels.value);
    if (!Number.isFinite(megapixels) || megapixels < 0.1 || megapixels > 16
      || Math.abs(megapixels * 10 - Math.round(megapixels * 10)) > 1e-8) {
      return "Les mégapixels doivent rester entre 0,1 et 16 par pas de 0,1.";
    }
    const steps = Number(elements.steps.value);
    if (!Number.isInteger(steps) || steps < 1 || steps > 100) return "Les steps doivent rester entre 1 et 100.";
    return "";
  }

  function isActive(run) {
    return Boolean(run && !terminalStatuses.has(String(run.status || "").toLowerCase()));
  }

  function render() {
    renderReferences();
    const active = isActive(state.activeRun);
    const locked = state.busy || active;
    elements.generate.disabled = locked || Boolean(validationError());
    elements.prompt.disabled = locked;
    elements.preset.disabled = locked;
    elements.ratio.disabled = locked;
    elements.megapixels.disabled = locked;
    elements.duration.disabled = locked;
    elements.steps.disabled = locked;
    elements.seed.disabled = locked;
    elements.seedLock.disabled = locked;
    elements.randomizeSeed.disabled = locked;
    elements.cancel.disabled = !active || state.busy;
    elements.reuseSeed.disabled = !state.activeRun || !runSeed(state.activeRun);
    elements.historyList.querySelectorAll("button").forEach((button) => {
      button.disabled = locked;
    });
    elements.references.querySelectorAll("button").forEach((button) => {
      if (locked) button.disabled = true;
    });
    renderRun(state.activeRun);
  }

  function runSeed(run) {
    return run && (run.seed
      ?? (run.parameters && run.parameters.seed)
      ?? (run.settings && run.settings.seed));
  }

  function runParameter(run, name) {
    return run && (run[name]
      ?? (run.parameters && run.parameters[name])
      ?? (run.settings && run.settings[name]));
  }

  function statusLabel(status) {
    return {
      created: "Prêt à lancer",
      preparing: "Préparation",
      prepared: "Prêt à lancer",
      queued: "En file",
      running: "Génération",
      cancel_pending: "Annulation à confirmer",
      succeeded: "Terminé",
      completed: "Terminé",
      failed: "Échec",
      cancelled: "Annulé",
      canceled: "Annulé",
    }[status] || status || "Prêt";
  }

  function renderRun(run) {
    if (!run) {
      elements.status.textContent = "● Prêt";
      elements.status.className = "run-status";
      elements.progress.value = 0;
      elements.progressLabel.textContent = "En attente";
      return;
    }
    const status = String(run.status || "prepared").toLowerCase();
    elements.status.textContent = `● ${statusLabel(status)}`;
    elements.status.className = `run-status ${terminalStatuses.has(status) ? (status === "failed" ? "failed" : status.startsWith("cancel") ? "" : "success") : "active"}`;
    const progress = Number(run.progress ?? run.progress_ratio);
    if (Number.isFinite(progress)) elements.progress.value = Math.max(0, Math.min(1, progress > 1 ? progress / 100 : progress));
    const currentStep = run.current_step ?? run.step;
    const totalSteps = run.total_steps ?? runParameter(run, "steps");
    elements.progressLabel.textContent = currentStep && totalSteps
      ? `Step ${currentStep} / ${totalSteps}` : statusLabel(status);
    if (run.preview_url) setPreview(run.preview_url, run.preview_label || "Dernière preview", run.preview_mime);
    const outputUrl = run.output_url || run.output_content_url || run.final_url || run.video_url;
    if (outputUrl) setOutput(outputUrl, run.output_filename || run.filename || "Vidéo finale");
    const frames = run.frames || run.frame_count;
    const effectiveDuration = run.effective_duration_seconds;
    if (frames || effectiveDuration) {
      elements.outputCaption.textContent = [
        frames ? `${frames} frames` : "",
        effectiveDuration ? `${Number(effectiveDuration).toLocaleString("fr-FR")} s` : "",
      ].filter(Boolean).join(" · ");
    }
    elements.runMessage.textContent = run.error || run.message || "";
    elements.runMessage.classList.toggle("error-text", status === "failed");
  }

  function detachPreviewMedia() {
    elements.preview.removeAttribute("src");
    elements.preview.hidden = true;
    elements.previewVideo.pause();
    elements.previewVideo.removeAttribute("src");
    elements.previewVideo.load();
    elements.previewVideo.hidden = true;
  }

  function showPreviewMedia(url, mime, label, ownedObjectUrl = false) {
    if (!url) return;
    const previousObjectUrl = state.previewObjectUrl;
    detachPreviewMedia();
    state.previewObjectUrl = ownedObjectUrl ? url : null;
    if (String(mime || "").toLowerCase().startsWith("video/")) {
      elements.previewVideo.src = url;
      elements.previewVideo.hidden = false;
      elements.previewVideo.play().catch(() => {});
    } else {
      elements.preview.src = url;
      elements.preview.hidden = false;
    }
    elements.previewEmpty.hidden = true;
    elements.previewCaption.textContent = label;
    if (previousObjectUrl && previousObjectUrl !== url) URL.revokeObjectURL(previousObjectUrl);
  }

  function setPreview(url, label = "Preview reçue", mime = "image/jpeg") {
    showPreviewMedia(url, mime, label, false);
  }

  function setPreviewBlob(blob, label) {
    const objectUrl = URL.createObjectURL(blob);
    showPreviewMedia(objectUrl, blob.type, label, true);
  }

  function previewBlobFromBase64(value, declaredMime) {
    let encoded = String(value || "").trim();
    let mime = String(declaredMime || "application/octet-stream").toLowerCase();
    const dataUrl = encoded.match(/^data:([^;,]+);base64,(.*)$/s);
    if (dataUrl) {
      mime = dataUrl[1].toLowerCase();
      encoded = dataUrl[2];
    }
    encoded = encoded.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    while (encoded.length % 4) encoded += "=";
    const decoded = window.atob(encoded);
    const bytes = new Uint8Array(decoded.length);
    for (let index = 0; index < decoded.length; index += 1) {
      bytes[index] = decoded.charCodeAt(index);
    }
    return new Blob([bytes], { type: mime });
  }

  function setKjPreview(data) {
    if (!data) return;
    renderSocketProgress(data.step, data.total);
    if (!data.image) return;
    const mime = String(data.mime || "image/jpeg").toLowerCase();
    const resolution = data.w && data.h ? ` · ${data.w}×${data.h}` : "";
    setPreviewBlob(previewBlobFromBase64(data.image, mime), `Preview live${resolution}`);
  }

  function setBinaryPreview(buffer) {
    const view = new DataView(buffer);
    if (buffer.byteLength >= 8 && view.getUint32(0, false) !== 1) return;
    const imageFormat = buffer.byteLength >= 8 ? view.getUint32(4, false) : 1;
    const mime = imageFormat === 2 ? "image/png"
      : imageFormat === 3 ? "image/webp" : "image/jpeg";
    const bytes = buffer.byteLength > 8 ? buffer.slice(8) : buffer;
    setPreviewBlob(new Blob([bytes], { type: mime }), "Preview live");
  }

  function setOutput(url, label) {
    const canonicalUrl = new URL(url, window.location.href).href;
    if (state.outputCanonicalUrl !== canonicalUrl) {
      clearOutputAudioDiagnosticTimer();
      setOutputDiagnostic("");
      elements.output.pause();
      elements.output.removeAttribute("src");
      elements.output.load();
      const playbackUrl = new URL(canonicalUrl);
      playbackUrl.searchParams.set("_pf_media", `${Date.now()}`);
      state.outputCanonicalUrl = canonicalUrl;
      state.outputPlaybackUrl = playbackUrl.href;
      elements.output.src = state.outputPlaybackUrl;
      elements.output.load();
    }
    elements.output.removeAttribute("muted");
    elements.output.defaultMuted = false;
    elements.output.muted = false;
    if (elements.output.volume === 0) elements.output.volume = 1;
    elements.output.hidden = false;
    elements.outputEmpty.hidden = true;
    elements.playWithSound.hidden = false;
    elements.playWithSound.disabled = false;
    elements.playWithSound.textContent = "Lire avec le son";
    elements.outputCaption.textContent = label;
    elements.download.href = canonicalUrl;
    elements.download.hidden = false;
  }

  function setOutputDiagnostic(message, kind = "") {
    elements.outputDiagnostic.textContent = message || "";
    elements.outputDiagnostic.hidden = !message;
    elements.outputDiagnostic.dataset.kind = kind;
    elements.outputDiagnostic.classList.toggle("error-text", kind === "error");
  }

  function detectableAudioTrackState() {
    const tracks = elements.output.audioTracks;
    if (tracks && typeof tracks.length === "number") return tracks.length > 0;
    if (typeof elements.output.mozHasAudio === "boolean") return elements.output.mozHasAudio;
    return null;
  }

  function decodedAudioByteCount() {
    const value = Number(elements.output.webkitAudioDecodedByteCount);
    return Number.isFinite(value) ? value : null;
  }

  function clearOutputAudioDiagnosticTimer() {
    if (state.audioDiagnosticTimer !== null) window.clearTimeout(state.audioDiagnosticTimer);
    state.audioDiagnosticTimer = null;
  }

  function reportDecodedOutputAudio() {
    state.audioDiagnosticTimer = null;
    const decodedBytes = decodedAudioByteCount();
    if (decodedBytes !== null && decodedBytes > 0) {
      const muted = elements.output.muted || elements.output.volume === 0;
      setOutputDiagnostic(
        `Piste audio décodée (${decodedBytes.toLocaleString("fr-FR")} octets)${muted ? ", mais le lecteur est en sourdine." : " · son activé."}`,
        muted ? "audio" : "success",
      );
      return;
    }
    if (detectableAudioTrackState() === false) {
      setOutputDiagnostic("Aucune piste audio détectée dans la vidéo finale.", "audio");
      return;
    }
    if (!elements.output.paused && !elements.output.muted && elements.output.volume > 0) {
      setOutputDiagnostic(
        "La lecture est active, mais le navigateur ne confirme encore aucun octet audio décodé. Vérifiez aussi que ce site ou cet onglet n’est pas mis en sourdine.",
        "audio",
      );
    }
  }

  function scheduleDecodedOutputAudioReport() {
    clearOutputAudioDiagnosticTimer();
    state.audioDiagnosticTimer = window.setTimeout(reportDecodedOutputAudio, 1500);
  }

  async function playOutputWithSound() {
    if (!state.outputPlaybackUrl) return;
    clearOutputAudioDiagnosticTimer();
    elements.output.removeAttribute("muted");
    elements.output.defaultMuted = false;
    elements.output.muted = false;
    elements.output.volume = 1;
    const tracks = elements.output.audioTracks;
    if (tracks && typeof tracks.length === "number") {
      for (let index = 0; index < tracks.length; index += 1) tracks[index].enabled = true;
    }
    if (elements.output.ended) elements.output.currentTime = 0;
    try {
      await elements.output.play();
      elements.playWithSound.textContent = "Son activé";
      setOutputDiagnostic("Lecture avec son demandée au navigateur · vérification en cours.", "success");
      scheduleDecodedOutputAudioReport();
    } catch (error) {
      setOutputDiagnostic(`Le navigateur refuse la lecture avec son : ${error.message}`, "error");
    }
  }

  function diagnoseOutputAudio() {
    const hasAudioTrack = detectableAudioTrackState();
    if (hasAudioTrack === false) {
      setOutputDiagnostic("Aucune piste audio détectée dans la vidéo finale.", "audio");
    } else if (hasAudioTrack === true && elements.outputDiagnostic.dataset.kind === "audio") {
      setOutputDiagnostic("");
    }
    if (decodedAudioByteCount() > 0) reportDecodedOutputAudio();
  }

  function diagnoseOutputError() {
    const code = elements.output.error && elements.output.error.code;
    const detail = {
      1: "Lecture de la vidéo interrompue.",
      2: "Erreur réseau pendant le chargement de la vidéo.",
      3: "Le navigateur ne parvient pas à décoder la vidéo.",
      4: "Format vidéo non pris en charge par le navigateur.",
    }[code] || "La vidéo finale ne peut pas être lue.";
    setOutputDiagnostic(detail, "error");
  }

  function resetOutputs() {
    const previousObjectUrl = state.previewObjectUrl;
    state.previewObjectUrl = null;
    state.previewConnection = "idle";
    state.outputCanonicalUrl = null;
    state.outputPlaybackUrl = null;
    clearOutputAudioDiagnosticTimer();
    detachPreviewMedia();
    if (previousObjectUrl) URL.revokeObjectURL(previousObjectUrl);
    elements.previewEmpty.hidden = false;
    elements.previewEmpty.textContent = "La preview ComfyUI apparaîtra pendant le sampling.";
    elements.previewCaption.textContent = "En attente";
    elements.output.pause();
    elements.output.removeAttribute("src");
    elements.output.load();
    elements.output.hidden = true;
    elements.outputEmpty.hidden = false;
    elements.outputCaption.textContent = "Aucun rendu";
    elements.playWithSound.hidden = true;
    elements.playWithSound.disabled = true;
    elements.playWithSound.textContent = "Lire avec le son";
    setOutputDiagnostic("");
    elements.download.hidden = true;
    elements.progress.value = 0;
  }

  function formDataForRun() {
    const body = new FormData();
    const assetMode = state.references.every((reference) => reference.assetId && !reference.file);
    state.references.forEach((reference) => {
      if (assetMode) {
        body.append("source_asset_ids", reference.assetId);
        body.append("source_labels", reference.name || reference.label || reference.assetId);
      } else body.append("images", reference.file, reference.name || reference.file.name);
    });
    body.append("prompt", elements.prompt.value.trim());
    body.append("preset_id", elements.preset.value);
    body.append("aspect_ratio", elements.ratio.value);
    body.append("megapixels", elements.megapixels.value);
    body.append("duration_seconds", elements.duration.value);
    body.append("steps", elements.steps.value);
    body.append("seed", elements.seed.value.trim());
    body.append("seed_locked", String(elements.seedLock.checked));
    return body;
  }

  async function startRun(event) {
    event.preventDefault();
    if (state.busy || isActive(state.activeRun)) return;
    const error = validationError();
    if (error) {
      showFormMessage(error);
      return;
    }
    state.busy = true;
    showFormMessage("");
    resetOutputs();
    try {
      if (!elements.seedLock.checked) elements.seed.value = randomSeed();
      persistSeedLock();
      if (state.references.some((reference) => reference.assetId)
        && state.references.some((reference) => reference.file)) {
        await materializeAssetReferences();
      }
      const prepared = unwrapRun(await request("/api/video-lab/runs", {
        method: "POST",
        body: formDataForRun(),
      }));
      if (!prepared || !runId(prepared)) throw new Error("Video Lab a renvoyé un run invalide.");
      state.activeRun = prepared;
      render();
      await connectPreview(prepared);
      const started = unwrapRun(await request(`/api/video-lab/runs/${encodeURIComponent(runId(prepared))}/start`, { method: "POST" }));
      if (started) state.activeRun = { ...prepared, ...started };
      startPolling(runId(state.activeRun));
    } catch (runError) {
      showFormMessage(runError.message);
      if (state.activeRun && !state.activeRun.status) state.activeRun.status = "failed";
    } finally {
      state.busy = false;
      render();
    }
  }

  function websocketUrl(run) {
    let value = (run && (run.preview_ws_url || run.events_url || run.websocket_url))
      || (state.spec && state.spec.preview_ws_url)
      || `/api/video-lab/runs/${encodeURIComponent(runId(run))}/events`;
    value = String(value).replace("{run_id}", encodeURIComponent(runId(run)));
    if (value.startsWith("/")) {
      return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${value}`;
    }
    if (value.startsWith("http://")) return `ws://${value.slice(7)}`;
    if (value.startsWith("https://")) return `wss://${value.slice(8)}`;
    return value;
  }

  function closeSocket() {
    const socket = state.socket;
    state.socket = null;
    if (socket) socket.close();
  }

  function setPreviewConnection(status, message = "") {
    state.previewConnection = status;
    const noPreview = elements.preview.hidden && elements.previewVideo.hidden;
    if (status === "connecting") {
      if (noPreview) {
        elements.previewCaption.textContent = "Connexion…";
        elements.previewEmpty.textContent = "Connexion au relais de preview…";
      }
    } else if (status === "connected") {
      if (noPreview) {
        elements.previewCaption.textContent = "Connectée · en attente";
        elements.previewEmpty.textContent = "Preview connectée, en attente du sampling ComfyUI.";
      }
    } else if (status === "error") {
      elements.previewCaption.textContent = "Indisponible";
      if (noPreview) {
        elements.previewEmpty.hidden = false;
        elements.previewEmpty.textContent = message || "La preview live est indisponible ; le rendu continue.";
      }
    }
  }

  function connectPreview(run) {
    closeSocket();
    setPreviewConnection("connecting");
    return new Promise((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        resolve();
      };
      try {
        const socket = new WebSocket(websocketUrl(run));
        socket.binaryType = "arraybuffer";
        state.socket = socket;
        socket.addEventListener("error", () => {
          if (state.socket === socket) {
            setPreviewConnection("error", "Impossible d’ouvrir le relais de preview ; le rendu continue.");
          }
          finish();
        }, { once: true });
        socket.addEventListener("close", (event) => {
          if (state.socket === socket) {
            state.socket = null;
            if (state.previewConnection !== "error" && isActive(run)) {
              setPreviewConnection("error", event.reason || "Le relais de preview s’est déconnecté ; le rendu continue.");
            }
          }
          finish();
        });
        socket.addEventListener("message", (event) => {
          const eventType = handleSocketMessage(event);
          if (eventType === "panelforge_preview_status") finish();
        });
        window.setTimeout(finish, 12000);
      } catch (_) {
        setPreviewConnection("error", "Impossible d’initialiser la preview live ; le rendu continue.");
        finish();
      }
    });
  }

  function renderSocketProgress(value, maximum) {
    const step = Number(value);
    const total = Number(maximum);
    if (!Number.isFinite(step) || !Number.isFinite(total) || total <= 0) return;
    elements.progress.value = Math.max(0, Math.min(1, step / total));
    elements.progressLabel.textContent = `Step ${step} / ${total}`;
  }

  function handleSocketMessage(event) {
    if (event.data instanceof ArrayBuffer) {
      setBinaryPreview(event.data);
      return "binary_preview";
    }
    let payload = null;
    try { payload = JSON.parse(event.data); } catch (_) { return ""; }
    const type = payload.type || payload.event;
    const data = payload.data || payload;
    const eventExecutionId = data.prompt_id || payload.prompt_id || data.execution_id;
    const activeExecutionId = state.activeRun && state.activeRun.execution_id;
    if (eventExecutionId && activeExecutionId && eventExecutionId !== activeExecutionId) return "";
    if (type === "panelforge_preview_status") {
      if (data.status === "connected") setPreviewConnection("connected");
      else if (data.status === "error") {
        setPreviewConnection("error", data.message || "La preview live est indisponible ; le rendu continue.");
      }
    } else if (type === "kj_preview_override") {
      try {
        setKjPreview(data);
      } catch (_) {
        elements.runMessage.textContent = "La preview KJ reçue est illisible ; le rendu continue.";
        elements.runMessage.classList.add("error-text");
      }
    } else if (type === "preview" && (data.preview_url || data.url || data.data_url)) {
      setPreview(data.preview_url || data.url || data.data_url, "Preview live", data.mime);
    } else if (type === "progress") {
      renderSocketProgress(data.value, data.max);
    } else if (type === "execution_error") {
      elements.runMessage.textContent = data.exception_message || "ComfyUI a interrompu le rendu.";
      elements.runMessage.classList.add("error-text");
    } else if (payload.run) {
      state.activeRun = { ...(state.activeRun || {}), ...payload.run };
      render();
    }
    return type || "";
  }

  function stopPolling() {
    state.pollToken += 1;
    if (state.pollTimer !== null) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function startPolling(runId) {
    stopPolling();
    const token = state.pollToken;
    const poll = async () => {
      try {
        const run = unwrapRun(await request(`/api/video-lab/runs/${encodeURIComponent(runId)}`));
        if (token !== state.pollToken) return;
        state.activeRun = run;
        render();
        if (terminalStatuses.has(String(run.status || "").toLowerCase())) {
          closeSocket();
          await loadHistory();
          return;
        }
      } catch (error) {
        if (token === state.pollToken) elements.runMessage.textContent = error.message;
      }
      if (token === state.pollToken) state.pollTimer = window.setTimeout(poll, 1500);
    };
    poll();
  }

  async function cancelRun() {
    if (!isActive(state.activeRun) || state.busy) return;
    state.busy = true;
    render();
    try {
      const run = unwrapRun(await request(`/api/video-lab/runs/${encodeURIComponent(runId(state.activeRun))}/cancel`, { method: "POST" }));
      if (run) state.activeRun = run;
      stopPolling();
      closeSocket();
      await loadHistory();
    } catch (error) {
      elements.runMessage.textContent = error.message;
      elements.runMessage.classList.add("error-text");
    } finally {
      state.busy = false;
      render();
    }
  }

  async function loadHistory() {
    try {
      const payload = await request("/api/video-lab/runs?limit=30");
      const runs = Array.isArray(payload) ? payload : (payload && payload.runs) || [];
      elements.historyList.replaceChildren();
      elements.historyEmpty.hidden = Boolean(runs.length);
      runs.forEach((run) => elements.historyList.append(historyItem(run)));
      const activeRun = runs.find(isActive);
      if (activeRun && !isActive(state.activeRun)) {
        state.activeRun = activeRun;
        render();
        await connectPreview(activeRun);
        startPolling(runId(activeRun));
      }
    } catch (error) {
      elements.historyEmpty.hidden = false;
      elements.historyEmpty.textContent = `Historique indisponible : ${error.message}`;
    }
  }

  function historyItem(run) {
    const item = document.createElement("li");
    const copy = document.createElement("div");
    const title = document.createElement("b");
    title.textContent = run.output_filename || run.filename || `Run ${String(runId(run) || "").slice(0, 8)}`;
    const detail = document.createElement("small");
    detail.textContent = [
      statusLabel(String(run.status || "").toLowerCase()),
      runParameter(run, "aspect_ratio"),
      runParameter(run, "duration_seconds") ? `${runParameter(run, "duration_seconds")} s` : "",
      runSeed(run) ? `seed ${runSeed(run)}` : "",
    ].filter(Boolean).join(" · ");
    copy.append(title, detail);
    const open = document.createElement("button");
    open.type = "button";
    open.textContent = "Ouvrir";
    open.disabled = state.busy || isActive(state.activeRun);
    open.addEventListener("click", () => openRun(runId(run)));
    const rerun = document.createElement("button");
    rerun.type = "button";
    rerun.textContent = "Relancer";
    rerun.disabled = state.busy || isActive(state.activeRun);
    rerun.addEventListener("click", () => prepareFromRun(runId(run)));
    item.append(copy, open, rerun);
    return item;
  }

  async function openRun(runId) {
    if (state.busy || isActive(state.activeRun)) return;
    state.busy = true;
    render();
    try {
      const run = unwrapRun(await request(`/api/video-lab/runs/${encodeURIComponent(runId)}`));
      resetOutputs();
      state.activeRun = run;
      if (isActive(run)) {
        await connectPreview(run);
        startPolling(runId(run));
      } else {
        stopPolling();
        closeSocket();
      }
      render();
      elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      elements.runMessage.textContent = error.message;
      elements.runMessage.classList.add("error-text");
    } finally {
      state.busy = false;
      render();
    }
  }

  function runReferences(run) {
    const values = run.references || run.images || run.source_images || [];
    return values.slice(0, 3).map((reference, index) => ({
      assetId: reference.asset_id || reference.source_asset_id,
      contentUrl: reference.content_url || reference.url,
      previewUrl: reference.content_url || reference.url,
      name: reference.name || reference.label || reference.filename || `Picture ${index + 1}`,
    })).filter((reference) => reference.assetId && reference.contentUrl);
  }

  async function prepareFromRun(runId) {
    if (state.busy || isActive(state.activeRun)) return;
    state.busy = true;
    render();
    try {
      const run = unwrapRun(await request(`/api/video-lab/runs/${encodeURIComponent(runId)}`));
      prefill({
        references: runReferences(run),
        prompt: run.prompt,
        aspect_ratio: runParameter(run, "aspect_ratio"),
        megapixels: runParameter(run, "megapixels"),
        duration_seconds: runParameter(run, "duration_seconds"),
        steps: runParameter(run, "steps"),
        seed: runSeed(run),
        lock_seed: true,
        source: "history",
      });
    } catch (error) {
      showFormMessage(error.message);
    } finally {
      state.busy = false;
      render();
    }
  }

  function clearReferences() {
    state.references.forEach((reference) => {
      if (reference.objectUrl) URL.revokeObjectURL(reference.objectUrl);
    });
    state.references = [];
  }

  function ensureSelectValue(select, value, label = String) {
    if (value === null || value === undefined || value === "") return;
    if (![...select.options].some((option) => option.value === String(value))) {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = label(value);
      select.append(option);
    }
    select.value = String(value);
  }

  function applyPrefill(payload) {
    if (!payload) return;
    clearReferences();
    state.references = (payload.references || payload.images || []).slice(0, 3).map((reference, index) => ({
      assetId: reference.asset_id || reference.assetId || reference.source_asset_id,
      contentUrl: reference.content_url || reference.contentUrl || reference.url,
      previewUrl: reference.content_url || reference.contentUrl || reference.previewUrl || reference.url,
      name: reference.name || reference.label || reference.filename || `Picture ${index + 1}`,
    })).filter((reference) => reference.assetId && reference.contentUrl);
    if (typeof payload.prompt === "string") elements.prompt.value = payload.prompt;
    ensureSelectValue(elements.ratio, payload.aspect_ratio, String);
    ensureSelectValue(elements.megapixels, payload.megapixels, (value) => `${Number(value).toLocaleString("fr-FR")} MP`);
    const requestedDuration = Number(payload.duration_seconds);
    const minimumDuration = Number(elements.duration.min) || 5;
    const maximumDuration = Number(elements.duration.max) || 15;
    const durationOutsideRange = Number.isFinite(requestedDuration)
      && (requestedDuration < minimumDuration || requestedDuration > maximumDuration);
    if (Number.isFinite(requestedDuration) && !durationOutsideRange) {
      elements.duration.value = String(requestedDuration);
    }
    if (Number(payload.steps) > 0) elements.steps.value = String(payload.steps);
    if (payload.seed !== null && payload.seed !== undefined) elements.seed.value = String(payload.seed);
    if (payload.lock_seed !== undefined || payload.seed_locked !== undefined) {
      elements.seedLock.checked = Boolean(payload.lock_seed ?? payload.seed_locked);
      persistSeedLock();
    }
    renderEffectiveDuration();
    const message = payload.source === "ref2v"
      ? "Prérempli depuis Ref2V. Vérifiez les réglages puis lancez manuellement le rendu."
      : "Réglages du run recopiés. Modifiez-les ou relancez.";
    const durationWarning = durationOutsideRange
      ? ` La durée du Plan (${requestedDuration.toLocaleString("fr-FR")} s) est hors de la plage H3 ${minimumDuration}–${maximumDuration} s ; le preset a été conservé.`
      : "";
    showFormMessage(`${message}${durationWarning}`, false);
    render();
    if (window.PanelForgeLabNavigation) window.PanelForgeLabNavigation.switchView("video-lab");
    elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function prefill(payload) {
    if (!payload) return;
    if (!state.specReady) state.pendingPrefill = payload;
    applyPrefill(payload);
  }

  function reuseSeed() {
    const seed = runSeed(state.activeRun);
    if (seed === null || seed === undefined) return;
    elements.seed.value = String(seed);
    elements.seedLock.checked = true;
    persistSeedLock();
    showFormMessage(`Seed ${seed} verrouillée pour le prochain rendu.`, false);
    render();
  }

  elements.images.addEventListener("change", () => addFiles(elements.images.files || []));
  elements.form.addEventListener("submit", startRun);
  elements.prompt.addEventListener("input", render);
  elements.preset.addEventListener("change", () => applyPreset(elements.preset.value));
  [elements.ratio, elements.megapixels, elements.duration].forEach((input) => input.addEventListener("change", renderEffectiveDuration));
  [elements.ratio, elements.megapixels, elements.duration, elements.steps, elements.seed].forEach((input) => input.addEventListener("input", render));
  elements.randomizeSeed.addEventListener("click", () => {
    elements.seed.value = randomSeed();
    persistSeedLock();
    render();
  });
  elements.seedLock.addEventListener("change", () => { persistSeedLock(); render(); });
  elements.seed.addEventListener("input", persistSeedLock);
  elements.cancel.addEventListener("click", cancelRun);
  elements.reuseSeed.addEventListener("click", reuseSeed);
  elements.refresh.addEventListener("click", loadHistory);
  elements.playWithSound.addEventListener("click", playOutputWithSound);
  elements.output.addEventListener("loadedmetadata", diagnoseOutputAudio);
  elements.output.addEventListener("playing", scheduleDecodedOutputAudioReport);
  elements.output.addEventListener("error", diagnoseOutputError);
  window.addEventListener("beforeunload", () => {
    stopPolling();
    closeSocket();
    clearReferences();
    if (state.previewObjectUrl) URL.revokeObjectURL(state.previewObjectUrl);
    state.previewObjectUrl = null;
    clearOutputAudioDiagnosticTimer();
  });

  window.PanelForgeVideoLab = Object.freeze({ prefill, open: () => window.PanelForgeLabNavigation && window.PanelForgeLabNavigation.switchView("video-lab") });
  restoreSeed();
  render();
  loadSpec().finally(loadHistory);
})();
