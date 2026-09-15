(() => {
  "use strict";

  function mount(prefix, contextEvent, specMode) {

  const $ = (id) => document.getElementById(id);
  const activeStatuses = new Set(["queued", "running", "cancel_pending"]);
  const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
  const elements = {
    lab: $(`${prefix}-lab`), status: $(`${prefix}-status`), warnings: $(`${prefix}-warnings`),
    prompt: $(`${prefix}-prompt`), ratio: $(`${prefix}-ratio`), megapixels: $(`${prefix}-megapixels`),
    initialMegapixels: $(`${prefix}-initial-megapixels`),
    recipe: $(`${prefix}-render-recipe`), bunnyControls: $(`${prefix}-bunny-controls`),
    preset: $(`${prefix}-preset`), presetSummary: $(`${prefix}-preset-summary`),
    loraEnabled: $(`${prefix}-lora-enabled`), loraSummary: $(`${prefix}-lora-summary`),
    bunnyModel: $(`${prefix}-bunny-model`), bunnyGeometry: $(`${prefix}-bunny-geometry`),
    bunnyTurbo: $(`${prefix}-bunny-turbo`), bunnyBase: $(`${prefix}-bunny-base`),
    bunnyTurboNote: $(`${prefix}-bunny-turbo-note`),
    bunnyCoarse: $(`${prefix}-bunny-coarse`), bunnyRefine: $(`${prefix}-bunny-refine`),
    bunnyPreview: $(`${prefix}-bunny-preview`), bunnySecond: $(`${prefix}-bunny-lora-second`),
    bunnySecondLabel: $(`${prefix}-bunny-lora-second-label`),
    duration: $(`${prefix}-duration`), steps: $(`${prefix}-steps`), seed: $(`${prefix}-seed`),
    seedLock: $(`${prefix}-seed-lock`), music: $(`${prefix}-music`), spectrum: $(`${prefix}-spectrum`), render: $(`${prefix}-render`),
    cancel: $(`${prefix}-cancel`), mode: $(`${prefix}-mode`), live: $(`${prefix}-live-preview`),
    liveEmpty: $(`${prefix}-live-empty`), final: $(`${prefix}-final-video`),
    finalEmpty: $(`${prefix}-final-empty`), turns: $(`${prefix}-turns`), message: $(`${prefix}-message`),
    reasoning: $(`${prefix}-reasoning`), refine: $(`${prefix}-refine`), trace: $(`${prefix}-trace`),
    attempts: $(`${prefix}-attempts`), revisionVersion: $(`${prefix}-revision-version`),
    revisionModel: $(`${prefix}-revision-model`),
    revisionAudacity: $(`${prefix}-revision-audacity`),
    dialogue: $(`${prefix}-dialogue`), dialogueValue: $(`${prefix}-dialogue-value`), dialogueControl: $(`${prefix}-dialogue-control`),
    revisionAudacityValue: $(`${prefix}-revision-audacity-value`),
    convert: $(`${prefix}-convert-ref2v`),
    revisionDraft: $(`${prefix}-revision-draft`), revisionError: $(`${prefix}-revision-error`),
    revisionDraftContent: $(`${prefix}-revision-draft-content`),
    revisionRetry: $(`${prefix}-revision-retry`),
    videoLoraProfile: $(`${prefix}-video-lora-profile`),
    videoLoraFields: $(`${prefix}-video-lora-fields`),
    videoLoraModel: $(`${prefix}-video-lora-model`),
    videoLoraInfo: $(`${prefix}-video-lora-info`),
    videoLoraStrength: $(`${prefix}-video-lora-strength`),
    videoLoraStrengthValue: $(`${prefix}-video-lora-strength-value`),
    videoLoraClip: $(`${prefix}-video-lora-clip`),
    videoLoraWarning: $(`${prefix}-video-lora-warning`),
    renderProgress: $(`${prefix}-render-progress`),
    renderProgressPhase: $(`${prefix}-render-progress-phase`),
    renderProgressMeta: $(`${prefix}-render-progress-meta`),
    renderProgressBar: $(`${prefix}-render-progress-bar`),
  };
  if (!elements.lab) return;

  const core = window.PanelForgeLabCore;
  const state = {
    spec: null,
    context: null,
    project: null,
    busy: false,
    openingKey: "",
    pollTimer: null,
    pollToken: 0,
    socket: null,
    previewUrl: null,
    finalUrl: "",
    selectedRevisionVersion: "",
    renderProgressAttemptId: "",
    renderProgressStartedAt: 0,
    renderProgressTimer: null,
    renderProgressData: null,
    specCache: new Map(), recipeDrafts: new Map(), defaultRecipeKey: "",
    recipeLoading: false, recipeToken: 0, contextToken: 0, bunnyError: "",
  };

  const checkpointPicker = window.PanelForgeH3Checkpoints?.mount(prefix, {
    request, mode: specMode, onChange: () => { syncBunny(); renderControls(); },
  });
  const loraEditor = window.PanelForgeH3Loras?.mount(prefix, {
    request, onChange: () => renderControls(),
  });

  const recipeKey = (recipe) => recipe ? `${recipe.recipe_id || recipe.id}@${recipe.version}` : state.defaultRecipeKey;
  const bunnyActive = () => Boolean(state.spec?.bunny);
  const draftFields = ["ratio", "megapixels", "initialMegapixels", "duration", "steps", "seed", "seedLock", "music", "spectrum",
    "videoLoraProfile", "videoLoraModel", "videoLoraStrength", "videoLoraClip", "bunnyTurbo", "bunnyBase", "bunnyCoarse", "bunnyRefine", "bunnyPreview", "bunnySecond"];
  function captureControls(fields = draftFields) {
    return Object.fromEntries(fields.filter(k => elements[k]).map(k => [k,
      elements[k].type === "checkbox" ? elements[k].checked : elements[k].value]));
  }
  function restoreControls(values) {
    for (const [key, value] of Object.entries(values)) {
      const field = elements[key]; if (!field) continue;
      if (field.type === "checkbox") field.checked = value; else field.value = value;
    }
  }
  function rememberRecipe() {
    if (!state.spec || !state.project) return;
    state.recipeDrafts.set(`${projectId()}:${recipeKey(state.spec.recipe)}`, {
      checkpoint: checkpointPicker?.value || null,
      video_loras: loraEditor?.value || null,
      fields: captureControls(),
    });
  }
  function showLora(name) {
    if (name && ![...elements.videoLoraModel.options].some(o => o.value === name)) {
      const option = document.createElement("option"); option.value = name;
      option.textContent = `${name} · indisponible`; option.disabled = true;
      elements.videoLoraModel.append(option);
    }
    elements.videoLoraModel.value = name || "";
  }
  function syncBunny() {
    if (!elements.bunnyControls) return;
    const enabled = bunnyActive();
    elements.bunnyControls.hidden = !enabled;
    elements.bunnyGeometry.hidden = !enabled;
    elements.bunnySecondLabel.hidden = !enabled;
    elements.steps.closest("label").hidden = enabled;
    elements.spectrum.closest("label").hidden = enabled;
    elements.videoLoraClip.closest("label").hidden = enabled;
    const forceLabel = elements.videoLoraStrength.closest("label");
    if (forceLabel?.firstChild?.nodeType === Node.TEXT_NODE) forceLabel.firstChild.textContent = enabled ? "Force passe 1 " : "Force ";
    if (elements.initialMegapixels) {
      const label = elements.initialMegapixels.closest("label");
      label.hidden = false;
      const note = label.querySelector("[data-initial-note]");
      if (note) note.textContent = state.spec?.limits?.initial_megapixels ? "" : "Fixé à 0,2 MP par cette recette";
    }
    state.bunnyError = "";
    if (!enabled) return;
    if (elements.bunnyTurboNote) elements.bunnyTurboNote.textContent = elements.bunnyTurbo.checked
      ? `Turbo supplémentaire actif${state.spec.bunny.turbo_strength != null ? ` · force ${Number(state.spec.bunny.turbo_strength).toFixed(2)}` : ""}. Décochez si votre checkpoint intègre déjà Turbo. Les steps restent indépendants.`
      : "Turbo supplémentaire désactivé. Les steps sont conservés ; adaptez-les aux recommandations du checkpoint.";
    elements.bunnyModel.textContent = checkpointPicker?.value ? `${checkpointPicker.label} · chargement direct` : state.spec.bunny.model_label;
    const base = Number(elements.bunnyBase.value), coarse = Number(elements.bunnyCoarse.value), refine = Number(elements.bunnyRefine.value);
    elements.steps.value = String(coarse + refine);
    if (!Number.isInteger(base) || !Number.isInteger(coarse) || base < 2 || base > 100 || coarse < 1 || coarse >= base || ![3, 4, 5].includes(refine) || coarse + refine > 100) {
      state.bunnyError = "Steps : base 2–100, première passe inférieure à la base, seconde passe 3–5, total ≤ 100.";
    }
    const initial = Number(elements.initialMegapixels.value), target = Number(elements.megapixels.value);
    const [rw, rh] = elements.ratio.value.split(" ")[0].split(":").map(Number);
    // ResolutionSelector uses Python round; preserve half-to-even at the grid boundary.
    const round = x => x % 1 === 0.5 ? (Math.floor(x) % 2 === 0 ? Math.floor(x) : Math.ceil(x)) : Math.round(x);
    const size = mp => {
      const scale = Math.sqrt(mp * 1024 * 1024 / (rw * rh));
      return [round(rw * scale / 32) * 32, round(rh * scale / 32) * 32];
    };
    const [w, h] = size(initial), [tw, th] = size(target), ratio = w / h;
    const iw = Math.sqrt(tw * th * ratio), ih = iw / ratio;
    const candidates = [];
    for (const cw of new Set([Math.floor(iw / 32) * 32, Math.ceil(iw / 32) * 32])) {
      for (const ch of new Set([Math.floor(ih / 32) * 32, Math.ceil(ih / 32) * 32])) {
        const ow = Math.max(32, cw), oh = Math.max(32, ch);
        candidates.push({w: ow, h: oh, aspect: Math.abs(Math.log((ow / oh) / ratio)), size: Math.hypot((ow - iw) / iw, (oh - ih) / ih)});
      }
    }
    candidates.sort((a, b) => a.aspect - b.aspect || a.size - b.size);
    const out = candidates[0], sx = out.w / w, sy = out.h / h;
    if (![initial, target].every(v => Number.isFinite(v) && v >= 0.1 && v <= 16 && Math.abs(v * 10 - Math.round(v * 10)) < 1e-8)
        || Math.min(sx, sy) < 1 || Math.max(sx, sy) > 4 || Math.max(sx, sy) / Math.min(sx, sy) > 1.05 || Math.max(tw, th) > 4096) {
      state.bunnyError = "Résolution : MP par pas de 0,1 ; sortie de ×1 à ×4, sans réduction, cible ≤ 4096 px.";
    }
    elements.bunnyGeometry.textContent = state.bunnyError || `${w} × ${h} → ${out.w} × ${out.h} · upscale ×${Math.sqrt(sx * sy).toFixed(3)} · ${coarse} + ${refine} steps exécutés`;
  }
  async function switchRecipe(key, { restoreDraft = true, remember = true } = {}) {
    if (!key) return;
    if (remember) rememberRecipe();
    const previous = recipeKey(state.spec?.recipe);
    const token = ++state.recipeToken, project = projectId();
    const common = captureControls(["ratio", "duration", "seed", "seedLock", "music"]);
    state.recipeLoading = true; renderControls();
    try {
      if (!state.specCache.has(key)) {
        const at = key.lastIndexOf("@");
        const spec = await request(`/api/h3-render/spec?mode=${encodeURIComponent(specMode)}&recipe_id=${encodeURIComponent(key.slice(0, at))}&recipe_version=${encodeURIComponent(key.slice(at + 1))}`);
        state.specCache.set(key, spec);
      }
      if (token !== state.recipeToken || project !== projectId()) return;
      state.spec = state.specCache.get(key);
      hydrateDefaults({ renderOnly: true });
      const draft = restoreDraft && state.recipeDrafts.get(`${project}:${key}`);
      if (draft) {
        checkpointPicker?.set(draft.checkpoint);
        showLora(draft.fields.videoLoraModel);
        restoreControls(draft.fields);
        loraEditor?.restore(draft.video_loras);
      } else restoreControls(common);
      elements.recipe.value = key;
      syncBunny(); syncVideoLoraControls(); renderWarnings();
    } catch (error) {
      if (token === state.recipeToken) { elements.recipe.value = previous; setStatus(error.message, "error"); }
      throw error;
    } finally {
      if (token === state.recipeToken) { state.recipeLoading = false; renderControls(); }
    }
  }

  async function request(url, options = {}) {
    if (core && core.request) return core.request(url, options);
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty */ }
    if (!response.ok) throw new Error(payload?.detail || `Erreur HTTP ${response.status}`);
    return payload;
  }

  function randomSeed() {
    if (window.crypto?.getRandomValues && typeof BigInt === "function") {
      const words = new Uint32Array(2);
      window.crypto.getRandomValues(words);
      return ((BigInt(words[0]) << 32n) | BigInt(words[1])).toString();
    }
    return String(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER));
  }

  function projectId() { return state.project?.project_id; }
  function latestAttempt() { return [...(state.project?.attempts || [])].reverse().find(a => !a.dlss) || null; }
  function activeAttempt() {
    return [...(state.project?.attempts || [])].reverse().find((item) => activeStatuses.has(item.status)) || null;
  }

  function setStatus(message, tone = "active") {
    elements.status.textContent = message;
    elements.status.className = `run-status ${tone}`;
  }

  function inferredDuration(prompt, fallback) {
    const matches = [
      /\btarget video lasts\s+([0-9]+(?:\.[0-9]+)?)\s+seconds?\b/i,
      /aligns with the\s+([0-9]+(?:\.[0-9]+)?)-second mark of the target video/i,
      /one continuous(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)-second shot/i,
      /target video is(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)[ -]second/i,
    ];
    for (const pattern of matches) {
      const match = String(prompt || "").match(pattern);
      const value = match ? Number(match[1]) : NaN;
      if (Number.isFinite(value) && value >= 5 && value <= 15) return value;
    }
    return fallback;
  }

  function renderWarnings() {
    const warnings = [...(state.project?.warnings || [])];
    const promptDuration = inferredDuration(elements.prompt?.value || state.project?.current_prompt, NaN);
    const renderDuration = Number(elements.duration?.value);
    if (
      Number.isFinite(promptDuration)
      && Number.isFinite(renderDuration)
      && Math.abs(promptDuration - renderDuration) >= 0.001
    ) {
      warnings.push(
        `Prompt compilé pour ${promptDuration} s · rendu configuré pour ${renderDuration} s. `
        + "Les timestamps et l’ancre finale ne sont pas réécrits automatiquement.",
      );
    }
    elements.warnings.hidden = !warnings.length;
    elements.warnings.textContent = warnings.join(" · ");
  }

  function syncVideoLoraControls() {
    if (!elements.videoLoraProfile) return;
    const enabled = elements.videoLoraProfile.value === "lora";
    elements.videoLoraFields.hidden = !enabled || Boolean(loraEditor?.supported);
    loraEditor?.setEnabled(enabled);
    if (elements.videoLoraStrengthValue) {
      elements.videoLoraStrengthValue.textContent = Number(elements.videoLoraStrength.value || 0.5).toFixed(2);
    }
    renderControls();
  }

  function syncRevisionAudacity() {
    if (!elements.revisionAudacity || !elements.revisionAudacityValue) return;
    elements.revisionAudacityValue.textContent = `${elements.revisionAudacity.value}/3`;
  }

  function hydrateDefaults({ renderOnly = false } = {}) {
    if (!state.spec) return;
    checkpointPicker?.configure(state.spec.checkpoint_selection);
    loraEditor?.configure(state.spec.video_lora_stack, state.spec.video_lora);
    const defaults = state.spec.defaults;
    elements.ratio.replaceChildren(...state.spec.aspect_ratios.map((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      return option;
    }));
    elements.ratio.value = defaults.aspect_ratio;
    elements.megapixels.value = String(defaults.megapixels);
    if (elements.initialMegapixels) {
      elements.initialMegapixels.value = String(defaults.initial_megapixels ?? 0.2);
      elements.initialMegapixels.closest("label").hidden = false;
    }
    elements.duration.value = String(inferredDuration(state.project?.current_prompt, defaults.duration_seconds));
    elements.steps.value = String(defaults.steps);
    elements.seed.value = randomSeed();
    elements.seedLock.checked = defaults.seed_locked ?? true;
    elements.music.value = "off";
    elements.spectrum.checked = false;
    if (elements.videoLoraProfile) {
      const config = state.spec.video_lora || {};
      const models = config.models || [];
      elements.videoLoraModel.replaceChildren(...models.map((name) => {
        const option = document.createElement("option"); option.value = name; option.textContent = name; return option;
      }));
      const loraOption = elements.videoLoraProfile.querySelector('option[value="lora"]');
      if (loraOption) loraOption.disabled = !config.supported || (!models.length && !loraEditor?.supported);
      elements.videoLoraProfile.value = "standard";
      elements.videoLoraStrength.value = String(config.defaults?.strength ?? 0.5);
      elements.videoLoraClip.checked = (config.defaults?.clip_last_layer ?? -2) === -2;
      elements.videoLoraWarning.textContent = config.warning || (!models.length ? "Aucun LoRA MiniMax trouvé dans minmax_nsfw/." : "");
      elements.videoLoraWarning.hidden = !elements.videoLoraWarning.textContent;
    }
    if (elements.recipe) {
      elements.recipe.replaceChildren(...(state.spec.render_recipes || []).map(item => {
        const option = document.createElement("option"); option.value = recipeKey(item); option.textContent = `${item.label} (${item.version})`; return option;
      }));
      elements.recipe.value = recipeKey(state.spec.recipe);
    }
    if (bunnyActive()) {
      const config = state.spec.bunny;
      elements.bunnyTurbo.checked = true; elements.bunnyPreview.checked = true;
      elements.bunnyBase.value = "9"; elements.bunnyCoarse.value = "4"; elements.bunnyRefine.value = "5";
      elements.bunnySecond.value = String(config.lora_second_strength);
      elements.videoLoraProfile.value = "lora";
      showLora(config.default_lora); elements.videoLoraStrength.value = String(config.lora_first_strength);
      elements.videoLoraClip.checked = false;
    }
    if (loraEditor?.supported) {
      elements.videoLoraProfile.value = loraEditor.value.enabled ? "lora" : "standard";
      elements.videoLoraWarning.hidden = true;
    }
    syncBunny(); syncVideoLoraControls();
    if (!renderOnly && elements.revisionVersion) {
      elements.revisionVersion.replaceChildren(...(state.project?.revision_versions || state.spec.revision_versions || []).map((item) => {
        const option = document.createElement("option");
        option.value = item.version; option.textContent = item.label;
        return option;
      }));
      state.selectedRevisionVersion = state.project?.revision_version || state.spec.default_revision_version || "0.2.0";
      elements.revisionVersion.value = state.selectedRevisionVersion;
    }
    if (!renderOnly && elements.revisionModel) {
      const selectedModel = state.project?.revision_model_id || state.project?.model_id || "";
      window.PanelForgeModelPicker.populate(
        elements.revisionModel,
        state.spec.llm_models || [],
        selectedModel,
      );
      if (selectedModel) {
        window.PanelForgeModelPicker.select(
          elements.revisionModel,
          selectedModel,
          "modèle historique indisponible",
        );
      }
    }
    renderWarnings();
  }

  async function fillSettings(attempt) {
    if (!attempt) return;
    const owner = projectId(), key = recipeKey(attempt.recipe);
    await switchRecipe(recipeKey(attempt.recipe), { restoreDraft: false });
    if (owner !== projectId() || (elements.recipe && recipeKey(state.spec.recipe) !== key)) return;
    checkpointPicker?.set(attempt.checkpoint);
    const settings = attempt.settings;
    elements.ratio.value = settings.aspect_ratio;
    elements.megapixels.value = String(settings.megapixels);
    if (elements.initialMegapixels) elements.initialMegapixels.value = String(attempt.initial_megapixels ?? 0.2);
    elements.duration.value = String(settings.duration_seconds);
    elements.steps.value = String(settings.steps);
    elements.seed.value = String(settings.seed);
    elements.seedLock.checked = true;
    elements.music.value = attempt.music_enabled ? "on" : "off";
    elements.spectrum.checked = Boolean(attempt.spectrum_enabled);
    if (elements.videoLoraProfile) {
      elements.videoLoraProfile.value = attempt.video_lora ? "lora" : "standard";
      if (attempt.video_lora) {
        showLora(attempt.video_lora.name);
        elements.videoLoraStrength.value = String(attempt.video_lora.strength);
        elements.videoLoraClip.checked = attempt.video_lora.clip_last_layer === -2;
      }
    }
    if (attempt.bunny) {
      const b = attempt.bunny;
      elements.bunnyTurbo.checked = b.turbo_enabled;
      elements.bunnyBase.value = String(b.base_steps); elements.bunnyCoarse.value = String(b.coarse_steps); elements.bunnyRefine.value = String(b.refine_steps);
      elements.bunnySecond.value = String(b.lora_second_strength); elements.bunnyPreview.checked = b.preview_enabled;
    }
    loraEditor?.restoreAttempt(attempt);
    if (loraEditor?.supported) elements.videoLoraProfile.value = loraEditor.value.enabled ? "lora" : "standard";
    syncVideoLoraControls();
    syncBunny(); renderControls();
    renderWarnings();
  }

  function setPreviewBlob(blob) {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(blob);
    elements.live.src = state.previewUrl;
    elements.live.hidden = false;
    elements.liveEmpty.hidden = true;
  }

  function binaryPreview(buffer) {
    const view = new DataView(buffer);
    if (buffer.byteLength >= 8 && view.getUint32(0, false) !== 1) return;
    const format = buffer.byteLength >= 8 ? view.getUint32(4, false) : 1;
    const mime = format === 2 ? "image/png" : format === 3 ? "image/webp" : "image/jpeg";
    setPreviewBlob(new Blob([buffer.byteLength > 8 ? buffer.slice(8) : buffer], { type: mime }));
  }

  function base64Preview(value, mime = "image/jpeg") {
    let encoded = String(value || "").trim();
    const dataUrl = encoded.match(/^data:([^;,]+);base64,(.*)$/s);
    if (dataUrl) { mime = dataUrl[1]; encoded = dataUrl[2]; }
    encoded = encoded.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    while (encoded.length % 4) encoded += "=";
    const decoded = window.atob(encoded);
    const bytes = new Uint8Array(decoded.length);
    for (let index = 0; index < decoded.length; index += 1) bytes[index] = decoded.charCodeAt(index);
    setPreviewBlob(new Blob([bytes], { type: mime }));
  }

  function closeSocket() {
    const socket = state.socket;
    state.socket = null;
    if (socket) socket.close();
  }

  function elapsedLabel(startedAt) {
    const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function paintRenderProgress() {
    const data = state.renderProgressData;
    if (!data || !elements.renderProgress) return;
    const percent = Math.max(0, Math.min(100, Number(data.percent) || 0));
    const steps = Number(data.current_step) > 0 && Number(data.total_steps) > 0
      ? `step ${data.current_step} / ${data.total_steps} · ` : "";
    const estimate = data.estimated === false ? "" : " estimé";
    elements.renderProgress.hidden = false;
    elements.renderProgressPhase.textContent = data.phase_label || "Rendu en cours";
    elements.renderProgressBar.value = percent;
    elements.renderProgressMeta.textContent = `${steps}${Math.round(percent)} %${estimate} · écoulé ${elapsedLabel(state.renderProgressStartedAt || Date.now())}`;
  }

  function stopRenderProgressClock() {
    if (state.renderProgressTimer !== null) window.clearInterval(state.renderProgressTimer);
    state.renderProgressTimer = null;
  }

  function beginRenderProgress(attempt) {
    if (!attempt || !elements.renderProgress) return;
    if (state.renderProgressAttemptId !== attempt.attempt_id) {
      state.renderProgressAttemptId = attempt.attempt_id;
      state.renderProgressStartedAt = Date.now();
      state.renderProgressData = {
        phase_label: "Préparation des modèles",
        percent: 0,
        estimated: true,
      };
    }
    stopRenderProgressClock();
    state.renderProgressTimer = window.setInterval(paintRenderProgress, 1000);
    paintRenderProgress();
  }

  function finishRenderProgress(attempt) {
    if (!attempt || state.renderProgressAttemptId !== attempt.attempt_id) return;
    stopRenderProgressClock();
    if (attempt.status === "succeeded") {
      state.renderProgressData = {
        phase_label: "Terminé",
        percent: 100,
        estimated: false,
      };
    } else if (terminalStatuses.has(attempt.status)) {
      state.renderProgressData = {
        ...(state.renderProgressData || {}),
        phase_label: attempt.status === "cancelled" ? "Rendu annulé" : "Rendu interrompu",
      };
    }
    paintRenderProgress();
  }

  function connectPreview(attempt) {
    if (attempt?.bunny?.preview_enabled === false) {
      elements.live.hidden = true; elements.liveEmpty.hidden = false;
      elements.liveEmpty.textContent = "Preview désactivée · suivi du rendu actif.";
    }
    closeSocket();
    if (!attempt?.events_url) return;
    beginRenderProgress(attempt);
    const target = new URL(attempt.events_url, window.location.href);
    target.protocol = target.protocol === "https:" ? "wss:" : "ws:";
    try {
      const socket = new WebSocket(target.href);
      socket.binaryType = "arraybuffer";
      state.socket = socket;
      socket.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) { binaryPreview(event.data); return; }
        let payload;
        try { payload = JSON.parse(event.data); } catch (_) { return; }
        const data = payload.data || payload;
        const eventExecutionId = data.prompt_id || payload.prompt_id || data.execution_id;
        if (eventExecutionId && attempt.execution_id && eventExecutionId !== attempt.execution_id) return;
        if (payload.type === "panelforge_render_progress") {
          state.renderProgressData = data;
          paintRenderProgress();
        } else if (payload.type === "kj_preview_override" && data.image) base64Preview(data.image, data.mime);
        else if (payload.type === "preview" && (data.preview_url || data.url || data.data_url)) {
          elements.live.src = data.preview_url || data.url || data.data_url;
          elements.live.hidden = false;
          elements.liveEmpty.hidden = true;
        } else if (payload.type === "panelforge_preview_status" && data.status === "error") {
          elements.liveEmpty.textContent = data.message || "Preview live indisponible ; le rendu continue.";
        }
      });
    } catch (_) {
      elements.liveEmpty.textContent = "Preview live indisponible ; le rendu continue.";
    }
  }

  function stopPolling() {
    state.pollToken += 1;
    if (state.pollTimer !== null) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function startPolling() {
    stopPolling();
    const token = state.pollToken;
    const poll = async () => {
      try {
        const payload = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}`);
        if (token !== state.pollToken) return;
        renderProject(payload.project, { preservePrompt: true });
        if (activeAttempt()) state.pollTimer = window.setTimeout(poll, 1100);
        else { closeSocket(); setStatus(latestAttempt()?.status === "succeeded" ? "Terminé" : "Prêt", latestAttempt()?.status === "succeeded" ? "success" : "active"); }
      } catch (error) {
        if (token === state.pollToken) setStatus(error.message, "error");
      }
    };
    state.pollTimer = window.setTimeout(poll, 700);
  }

  function renderTurns() {
    elements.turns.replaceChildren();
    const turns = state.project?.turns || [];
    if (!turns.length) {
      const empty = document.createElement("p"); empty.className = "muted";
      empty.textContent = "Le premier échange apparaîtra ici."; elements.turns.append(empty); return;
    }
    turns.forEach((turn) => {
      const article = document.createElement("article"); article.className = `h3-render-turn ${turn.role}`;
      const head = document.createElement("b"); head.textContent = turn.role === "user" ? "Vous" : "LLM";
      const body = document.createElement("p"); body.textContent = turn.content;
      article.append(head);
      if (turn.revision_version) {
        const version = document.createElement("small");
        version.className = "h3-render-revision-badge";
        version.textContent = `Révision ${turn.revision_version}`;
        article.append(version);
      }
      if (turn.model_id) {
        const model = document.createElement("small");
        model.className = "h3-render-revision-badge";
        model.textContent = `Modèle ${turn.model_id.replace(/^[^:]+::/, "")}`;
        article.append(model);
      }
      article.append(body);
      if (turn.questions?.length) {
        const questions = document.createElement("small"); questions.textContent = `Questions : ${turn.questions.join(" · ")}`; article.append(questions);
      }
      elements.turns.append(article);
    });
  }

  function settingsSummary(attempt) {
    const s = attempt.settings;
    const lora = attempt.video_loras ? ` · ${window.PanelForgeH3Loras.summary(attempt.video_loras)}` : attempt.video_lora
      ? ` · LoRA ${attempt.video_lora.name} × ${Number(attempt.video_lora.strength).toFixed(2)}${attempt.video_lora.clip_last_layer === -2 ? " · CLIP -2" : ""}`
      : " · Standard";
    if (attempt.bunny) {
      const b = attempt.bunny, g = attempt.bunny_geometry;
      return `BUNNY ${attempt.recipe.version} · ${s.aspect_ratio.split(" ")[0]} · ${attempt.initial_megapixels} MP → ${s.megapixels} MP${g ? ` · ${g.width} × ${g.height} · ×${g.scale.toFixed(3)}` : ""} · ${s.duration_seconds} s · Turbo ${b.turbo_enabled ? "ON" : "OFF"} · ${b.base_steps}/${b.coarse_steps}/${b.refine_steps} steps · seed ${s.seed}${attempt.video_loras ? lora : attempt.video_lora ? ` · ${attempt.video_lora.name} · forces ${attempt.video_lora.strength}/${b.lora_second_strength}` : " · Aucun LoRA"}`;
    }
    const initial = ` · ${attempt.initial_megapixels ?? 0.2} MP avant upscale`;
    return `${s.aspect_ratio.split(" ")[0]} · ${s.megapixels} MP sortie${initial} · ${s.duration_seconds} s · ${s.steps} steps · seed ${s.seed} · musique ${attempt.music_enabled ? "ON" : "OFF"} · Spectrum ${attempt.spectrum_enabled ? "ON" : "OFF"}${lora}`;
  }

  window.addEventListener("panelforge:dlss-complete", async event => {
    const job = event.detail, project = state.project;
    if (job.snapshot.owner !== (specMode === "ref2va" ? "ref2v" : "h3") || project?.project_id !== job.snapshot.owner_id) return;
    if (!job.select_result) return;
    if (state.busy) { setTimeout(() => window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: job })), 1000); return; }
    try {
      const data = await request(`/api/h3-render/projects/${encodeURIComponent(project.project_id)}`);
      if (state.project === project && !state.busy) {
        state.project = { ...state.project, attempts: data.project.attempts };
        renderAttempts();
      }
    } catch (error) { setStatus(error.message, "error"); }
  });

  function renderAttempts() {
    elements.attempts.replaceChildren();
    const scope = `${specMode === "ref2va" ? "ref2v" : "h3"}:${projectId()}`;
    const attempts = [...(window.PanelForgeDlss?.groups(state.project?.attempts || [], scope, state.project?.feedback_attempt_id)
      || (state.project?.attempts || []).map(attempt => ({ attempt })))].reverse();
    if (!attempts.length) {
      const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "Aucun essai."; elements.attempts.append(empty); return;
    }
    attempts.forEach(group => {
      const attempt = group.attempt;
      const card = document.createElement("article");
      card.className = `h3-render-attempt ${attempt.attempt_id === state.project.feedback_attempt_id ? "feedback" : ""}`;
      const header = document.createElement("div"); header.className = "h3-render-attempt-head";
      const title = document.createElement("b"); title.textContent = `Essai ${attempt.index}${attempt.dlss ? " · DLSS" : ""}`;
      const status = document.createElement("span"); status.textContent = attempt.status;
      header.append(title, status); card.append(header);
      if (group.variants) card.append(window.PanelForgeDlss.picker(group, renderAttempts));
      if (attempt.output_url) {
        const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.src = attempt.output_url; card.append(video);
      }
      const summary = document.createElement("small"); summary.textContent = attempt.dlss
        ? `DLSS · ${attempt.dlss.width} × ${attempt.dlss.height} · ${Number(attempt.dlss.fps).toFixed(2)} FPS · ${Number(attempt.dlss.duration_seconds).toFixed(2)} s` : settingsSummary(attempt); card.append(summary);
      if (attempt.model_loading) {
        const model = document.createElement("small"), loading = attempt.model_loading;
        model.textContent = `Modèle : ${loading.checkpoint}${loading.overlay ? ` + ${loading.overlay}` : ""} · ${attempt.checkpoint ? "chargement direct" : "par défaut"}`;
        model.style.overflowWrap = "anywhere"; card.append(model);
      }
      if (attempt.error) { const error = document.createElement("p"); error.className = "error-text"; error.textContent = attempt.error; card.append(error); }
      if (attempt.warnings?.length) { const warning = document.createElement("p"); warning.className = "warning-text"; warning.textContent = attempt.warnings.join(" · "); card.append(warning); }
      if (attempt.keyframes?.length) {
        const frames = document.createElement("div"); frames.className = "h3-render-keyframes";
        attempt.keyframes.forEach((frame) => {
          const figure = document.createElement("figure"); const image = document.createElement("img");
          image.src = frame.content_url; image.alt = `${frame.label} ${frame.timestamp_ms / 1000}s`;
          const caption = document.createElement("figcaption"); caption.textContent = `${frame.label} · ${(frame.timestamp_ms / 1000).toFixed(2)} s`;
          figure.append(image, caption); frames.append(figure);
        }); card.append(frames);
      }
      if (attempt.status === "succeeded") {
        const actions = document.createElement("div"); actions.className = "h3-render-card-actions";
        const resume = document.createElement("button"); resume.type = "button"; resume.textContent = "Reprendre prompt + réglages";
        resume.addEventListener("click", () => resumeAttempt(attempt));
        const feedback = document.createElement("button"); feedback.type = "button";
        feedback.textContent = attempt.attempt_id === state.project.feedback_attempt_id ? "Retirer le feedback" : "Utiliser comme feedback";
        feedback.addEventListener("click", () => selectFeedback(attempt));
        actions.append(resume, feedback);
        if (window.PanelForgePromptRecipes) {
          actions.append(window.PanelForgePromptRecipes.historyButton(projectId(), attempt.attempt_id));
        }
        if (window.PanelForgeDlss) {
          const target = { owner: specMode === "ref2va" ? "ref2v" : "h3", ownerId: projectId(), attempt };
          actions.append(window.PanelForgeDlss.button(target), window.PanelForgeDlss.button(target, { advanced: true }));
        }
        const download = document.createElement("a"); download.href = attempt.output_url; download.download = `${attempt.attempt_id}.mp4`; download.textContent = "Télécharger"; actions.append(download);
        card.append(actions);
        const continuation = document.createElement("button");
        continuation.type = "button";
        continuation.className = "h3-render-continue";
        continuation.textContent = "Repartir de la dernière frame";
        const timestamps = attempt.keyframe_timestamps_ms || [];
        const finalTimestamp = timestamps.length ? Math.max(...timestamps) : null;
        const lastFrame = finalTimestamp === null ? null : (attempt.keyframes || []).find(
          (frame) => frame.timestamp_ms === finalTimestamp && frame.asset_id,
        );
        continuation.disabled = !lastFrame || !window.PanelForgeH3Base;
        continuation.title = lastFrame
          ? "Préparer la suite dans H3 Base avec cette image en première frame"
          : "La frame de fin n'a pas été importée pour cet essai";
        const continuationError = document.createElement("p");
        continuationError.className = "error-text";
        continuationError.hidden = true;
        continuation.addEventListener("click", async () => {
          continuation.disabled = true;
          continuationError.hidden = true;
          try {
            await window.PanelForgeH3Base.prefillFirstFrame({
              assetId: lastFrame.asset_id,
              label: `Suite essai ${attempt.index} - dernière frame`,
              sourceSessionId: state.project.source_session_id,
              preparation: state.project.preparation,
              combatSettings: state.project.combat_settings,
              cinematicSettings: state.project.cinematic_settings,
              sensualSettings: state.project.sensual_settings,
            });
          } catch (error) {
            continuationError.textContent = error.message;
            continuationError.hidden = false;
          } finally {
            continuation.disabled = false;
          }
        });
        card.append(continuation, continuationError);
      }
      if (window.PanelForgeDlss && attempt.status === "succeeded") {
        card.append(window.PanelForgeDlss.inlineStatus({ owner: specMode === "ref2va" ? "ref2v" : "h3", ownerId: projectId(), attempt }));
      }
      elements.attempts.append(card);
    });
  }

  function renderOutput() {
    const latest = [...(state.project?.attempts || [])].reverse().find((item) => item.output_url && !item.dlss);
    if (!latest) return;
    const canonical = new URL(latest.output_url, window.location.href).href;
    if (state.finalUrl !== canonical) {
      state.finalUrl = canonical;
      const playback = new URL(canonical); playback.searchParams.set("_pf_media", String(Date.now()));
      elements.final.src = playback.href; elements.final.load();
    }
    elements.final.hidden = false; elements.finalEmpty.hidden = true;
  }

  function renderProject(project, { preservePrompt = false } = {}) {
    window.PanelForgeLabCore?.observeRenderAttempts?.(project.attempts || [], `h3:${project.project_id}`);
    const changed = state.project?.project_id !== project.project_id;
    if (changed) {
      stopRenderProgressClock();
      state.renderProgressAttemptId = "";
      state.renderProgressStartedAt = 0;
      state.renderProgressData = null;
      if (elements.renderProgress) elements.renderProgress.hidden = true;
    }
    state.project = project;
    elements.lab.hidden = false;
    if (changed || !preservePrompt) elements.prompt.value = project.current_prompt;
    if (elements.dialogue && changed) elements.dialogue.value = String(project.dialogue_level ?? 0);
    if (elements.revisionVersion && changed) {
      elements.revisionVersion.replaceChildren(...(project.revision_versions || state.spec?.revision_versions || []).map((item) => {
        const option = document.createElement("option");
        option.value = item.version; option.textContent = item.label;
        return option;
      }));
      state.selectedRevisionVersion = project.revision_version || state.spec?.default_revision_version || "0.2.0";
      elements.revisionVersion.value = state.selectedRevisionVersion;
    }
    if (elements.revisionModel && changed) {
      window.PanelForgeModelPicker.select(
        elements.revisionModel,
        project.revision_model_id || project.model_id,
        "modèle historique indisponible",
      );
    }
    if (elements.revisionDraft) {
      const rejected = Boolean(project.revision_error);
      elements.revisionDraft.hidden = !rejected;
      elements.revisionError.textContent = project.revision_error || "";
      elements.revisionDraftContent.value = project.revision_draft || "";
      if (rejected) elements.revisionDraft.open = true;
    }
    elements.mode.textContent = `Mode ${project.input_mode.toUpperCase()} · modèle initial ${project.model_id}`;
    if (project.preparation?.family === "combat") elements.mode.textContent += ` · Combat ${project.preparation.version}`;
    if (project.preparation?.family === "classic" && project.preparation.version === "1.0.0") elements.mode.textContent += " · Classique Mise en scène 1.0";
    if (project.preparation?.family === "sensual") elements.mode.textContent += " · Sensuel 1.0 · explicite maximal";
    if (project.combat_settings?.orientation) elements.mode.textContent += ` · ${window.PanelForgeCombatControls?.orientationLabel(project.combat_settings.orientation) || project.combat_settings.orientation}`;
    renderWarnings();
    renderTurns(); renderAttempts(); renderOutput(); renderControls();
    finishRenderProgress(latestAttempt());
  }

  function renderPreset(disabled) {
    if (!elements.preset || !state.spec) return;
    const profiles = bunnyActive() ? state.spec.bunny.turbo_profiles || {} : {};
    const keys = bunnyActive() ? ["on", "off"] : ["default"];
    const identity = `${recipeKey(state.spec.recipe)}:${keys.join()}`;
    if (elements.preset.dataset.recipe !== identity) {
      elements.preset.replaceChildren();
      for (const key of [...keys, "custom"]) {
        const option = document.createElement("option"); option.value = key;
        option.textContent = {on: "Rapide · 9 / 4 / 5", off: "Classique · 30 / 25 / 5",
          default: "Réglages de la recette", custom: "Personnalisé"}[key];
        option.disabled = key === "custom" || (bunnyActive() && !profiles[key]);
        elements.preset.append(option);
      }
      elements.preset.dataset.recipe = identity;
    }
    let selected = "custom";
    if (bunnyActive()) {
      selected = keys.find(key => profiles[key] && Number(elements.bunnyBase.value) === profiles[key].base_steps
        && Number(elements.bunnyCoarse.value) === profiles[key].coarse_steps
        && Number(elements.bunnyRefine.value) === profiles[key].refine_steps) || "custom";
      elements.presetSummary.textContent = `Sampling BUNNY natif · ${elements.bunnyCoarse.value} + ${elements.bunnyRefine.value} steps · `
        + (elements.bunnyTurbo.checked ? `Turbo ${Number(state.spec.bunny.turbo_strength).toFixed(2)}` : "Turbo supplémentaire désactivé");
    } else {
      if (Number(elements.steps.value) === state.spec.defaults.steps) selected = "default";
      elements.presetSummary.textContent = `Sampling de la recette · ${elements.steps.value} steps`;
    }
    elements.preset.value = selected; elements.preset.disabled = disabled;
    const stack = loraEditor?.supported ? loraEditor.value : null;
    elements.loraEnabled.checked = elements.videoLoraProfile.value === "lora";
    elements.loraEnabled.disabled = disabled || elements.videoLoraProfile.querySelector('[value="lora"]')?.disabled;
    const entries = stack?.enabled ? stack.entries.filter(entry => entry.enabled) : [];
    const names = entries.map(entry => entry.name.split(/[\\/]/).pop());
    const summary = stack ? `${entries.length} LoRA actif(s)${names.length ? " · " + names.join(" → ") : ""}`
      : elements.loraEnabled.checked ? `LoRA · ${elements.videoLoraModel.value || "à choisir"}` : "LoRA · aucun actif";
    elements.loraSummary.textContent = summary;
    elements.loraSummary.title = window.PanelForgeH3Loras?.summary(stack) || summary;
    elements.loraSummary.classList.toggle("error-text", Boolean(loraEditor?.error));
  }

  function renderControls() {
    const active = activeAttempt();
    const incomplete = state.project?.adaptation && state.project.adaptation.status !== "ready";
    const disabled = state.busy || state.recipeLoading || Boolean(active) || Boolean(incomplete);
    renderPreset(disabled);
    const missingLora = loraEditor?.supported ? Boolean(loraEditor.error) : elements.videoLoraProfile?.value === "lora" && (!elements.videoLoraModel?.value || !(state.spec?.video_lora?.models || []).includes(elements.videoLoraModel.value));
    if (loraEditor?.supported) {
      elements.videoLoraWarning.textContent = loraEditor.error;
      elements.videoLoraWarning.hidden = elements.videoLoraProfile.value === "lora" || !loraEditor.error;
    }
    if (elements.convert) elements.convert.disabled = state.busy || state.recipeLoading || !state.project || !elements.prompt.value.trim() || !elements.revisionModel?.value || Boolean(state.bunnyError) || missingLora;
    elements.render.disabled = disabled || !state.project || !elements.prompt.value.trim() || missingLora || Boolean(state.bunnyError);
    if (elements.recipe) elements.recipe.disabled = state.busy || state.recipeLoading;
    checkpointPicker?.setDisabled(disabled);
    loraEditor?.setDisabled(disabled);
    for (const field of [elements.bunnyTurbo, elements.bunnyBase, elements.bunnyCoarse, elements.bunnyRefine, elements.bunnyPreview, elements.bunnySecond]) {
      if (field) field.disabled = disabled || !bunnyActive();
    }
    elements.bunnyControls?.querySelectorAll("[data-bunny-sampling]").forEach(button => {
      button.disabled = disabled || !bunnyActive();
    });
    elements.cancel.disabled = !active || state.busy;
    elements.refine.disabled = disabled || !state.project || !elements.message.value.trim() || !elements.revisionModel?.value;
    if (elements.revisionRetry) {
      elements.revisionRetry.disabled = disabled || !state.project?.revision_error || !elements.revisionModel?.value;
    }
    for (const field of [elements.prompt, elements.ratio, elements.megapixels, elements.duration, elements.steps, elements.seed, elements.seedLock, elements.music, elements.spectrum]) field.disabled = disabled;
    if (elements.initialMegapixels) elements.initialMegapixels.disabled = disabled || !state.spec?.limits?.initial_megapixels;
    for (const field of [elements.videoLoraProfile, elements.videoLoraModel, elements.videoLoraStrength, elements.videoLoraClip]) {
      if (field) field.disabled = disabled || (field !== elements.videoLoraProfile && elements.videoLoraProfile.value !== "lora");
    }
    if (elements.videoLoraInfo) elements.videoLoraInfo.disabled = !elements.videoLoraModel.value || elements.videoLoraInfo.dataset.loading === "true";
    if (elements.dialogue) {
      elements.dialogue.disabled = disabled;
      elements.dialogueControl.hidden = !["0.3.0", "0.4.0", "1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.3.0"].includes(elements.revisionVersion?.value);
      elements.dialogueValue.textContent = `${elements.dialogue.value}/3`;
    }
    if (elements.revisionVersion) elements.revisionVersion.disabled = disabled;
    if (elements.revisionAudacity) elements.revisionAudacity.disabled = disabled;
    if (elements.revisionModel) {
      elements.revisionModel.disabled = disabled;
      window.PanelForgeModelPicker.setDisabled(elements.revisionModel, disabled);
    }
    if (active) setStatus(active.status === "cancel_pending" ? "Annulation…" : "Rendu…", "active");
  }

  async function openContext(detail) {
    state.context = detail;
    if (!detail?.project_id && (!detail?.ready || !detail.session_id || !detail.prompt_revision_id)) {
      rememberRecipe(); ++state.contextToken; ++state.recipeToken; state.recipeLoading = false;
      elements.lab.hidden = true; state.project = null; stopPolling(); closeSocket(); stopRenderProgressClock(); return;
    }
    const key = detail.project_id || `${detail.session_id}:${detail.prompt_revision_id}`;
    if (state.openingKey === key || (!detail.project_id && state.project?.source_session_id === detail.session_id && state.project?.source_prompt_revision_id === detail.prompt_revision_id)) return;
    const contextToken = ++state.contextToken;
    state.openingKey = key;
    try {
      rememberRecipe();
      ++state.recipeToken; state.recipeLoading = false;
      if (!state.defaultRecipeKey) {
        state.spec = await request(`/api/h3-render/spec?mode=${encodeURIComponent(specMode)}`);
        state.defaultRecipeKey = recipeKey(state.spec.recipe); state.specCache.set(state.defaultRecipeKey, state.spec);
      }
      if (contextToken !== state.contextToken) return;
      const payload = detail.project_id
        ? await request(`/api/h3-render/projects/${encodeURIComponent(detail.project_id)}`)
        : await request(`/api/h3-render/projects/from-session/${encodeURIComponent(detail.session_id)}`, { method: "POST" });
      if (contextToken !== state.contextToken) return;
      const changed = state.project?.project_id !== payload.project.project_id;
      renderProject(payload.project);
      if (changed) {
        state.spec = state.specCache.get(state.defaultRecipeKey);
        hydrateDefaults();
        if (latestAttempt()) await fillSettings(latestAttempt());
        else if (payload.project.adaptation) await fillSettings(payload.project.adaptation.render_setup);
      }
      if (activeAttempt()) { connectPreview(activeAttempt()); startPolling(); }
    } catch (error) {
      elements.lab.hidden = false; setStatus(error.message, "error");
    } finally { if (state.openingKey === key) state.openingKey = ""; renderControls(); }
  }

  function renderParameters() {
    return {
          recipe_id: state.spec.recipe.id, recipe_version: state.spec.recipe.version,
          checkpoint: checkpointPicker?.value || null,
          bunny: bunnyActive() ? {
            turbo_enabled: elements.bunnyTurbo.checked, base_steps: Number(elements.bunnyBase.value),
            coarse_steps: Number(elements.bunnyCoarse.value), refine_steps: Number(elements.bunnyRefine.value),
            lora_second_strength: Number(elements.bunnySecond.value), preview_enabled: elements.bunnyPreview.checked,
          } : null,
          prompt: elements.prompt.value.trim(), aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value), duration_seconds: Number(elements.duration.value),
          ...(elements.initialMegapixels && state.spec?.limits?.initial_megapixels
            ? { initial_megapixels: Number(elements.initialMegapixels.value) } : {}),
          steps: Number(elements.steps.value), seed: elements.seedLock.checked ? elements.seed.value.trim() : null,
          seed_locked: elements.seedLock.checked, music_enabled: elements.music.value === "on",
          spectrum_enabled: bunnyActive() ? false : elements.spectrum.checked,
          ...(loraEditor?.supported ? { video_loras: loraEditor.value } : {}),
          video_lora: !loraEditor?.supported && elements.videoLoraProfile?.value === "lora" ? {
            name: elements.videoLoraModel.value,
            strength: Number(elements.videoLoraStrength.value),
            clip_last_layer: !bunnyActive() && elements.videoLoraClip.checked ? -2 : null,
          } : null,
        };
  }

  async function renderAttempt() {
    if (!state.project || state.busy || state.recipeLoading || state.bunnyError || loraEditor?.error) return;
    state.busy = true; renderControls();
    elements.live.hidden = true; elements.liveEmpty.hidden = false; elements.liveEmpty.textContent = "Connexion à la preview ComfyUI…";
    try {
      const prepared = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/attempts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(renderParameters()),
      });
      renderProject(prepared.project, { preservePrompt: true });
      const attempt = prepared.project.attempts.at(-1);
      const started = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/attempts/${encodeURIComponent(attempt.attempt_id)}/start`, { method: "POST" });
      renderProject(started.project, { preservePrompt: true });
      connectPreview(started.project.attempts.at(-1)); startPolling();
      if (!elements.seedLock.checked) elements.seed.value = randomSeed();
    } catch (error) { setStatus(error.message, "error"); }
    finally { state.busy = false; renderControls(); }
  }

  async function cancelAttempt() {
    const attempt = activeAttempt(); if (!attempt || state.busy) return;
    state.busy = true; renderControls();
    try {
      const payload = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/attempts/${encodeURIComponent(attempt.attempt_id)}/cancel`, { method: "POST" });
      renderProject(payload.project, { preservePrompt: true }); stopPolling(); closeSocket();
    } catch (error) { setStatus(error.message, "error"); }
    finally { state.busy = false; renderControls(); }
  }

  async function selectFeedback(attempt) {
    const selected = attempt.attempt_id === state.project.feedback_attempt_id ? null : attempt.attempt_id;
    try {
      const payload = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ attempt_id: selected }),
      }); renderProject(payload.project, { preservePrompt: true });
    } catch (error) { setStatus(error.message, "error"); }
  }

  async function resumeAttempt(attempt) {
    try {
      const payload = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/attempts/${encodeURIComponent(attempt.attempt_id)}/resume`, { method: "POST" });
      renderProject(payload.project); await fillSettings(attempt); elements.prompt.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) { setStatus(error.message, "error"); }
  }

  async function submitPromptRevision(message, { repairRejected = false } = {}) {
    if (!message || state.busy || !state.project) return;
    state.busy = true; elements.trace.textContent = ""; elements.trace.hidden = !elements.reasoning.checked; renderControls();
    let streamError = "";
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      let url = `/api/h3-render/projects/${encodeURIComponent(projectId())}/chat/stream`;
      if (elements.reasoning.checked) url += "?include_reasoning=true";
      outcomeTone.start();
      await core.streamRequest(url, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          message,
          model_id: elements.revisionModel?.value || state.project.revision_model_id || state.project.model_id,
          feedback_attempt_id: state.project.feedback_attempt_id,
          revision_version: elements.revisionVersion?.value || state.project.revision_version || null,
          revision_audacity: Number(elements.revisionAudacity?.value || 0),
          dialogue_level: ["0.3.0", "0.4.0", "1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.3.0"].includes(elements.revisionVersion?.value) ? Number(elements.dialogue?.value || 0) : 0,
          repair_rejected: repairRejected,
        }),
      }, (event) => {
        if (event.kind === "reasoning" && event.text) { elements.trace.textContent += event.text; elements.trace.scrollTop = elements.trace.scrollHeight; }
        if (event.error) streamError = event.error;
        if (event.project) renderProject(event.project);
      }, { completionTone: false });
      if (streamError) throw new Error(streamError);
      outcomeTone.success();
      if (!repairRejected) elements.message.value = "";
      setStatus(repairRejected ? "Structure corrigée" : "Prompt ajusté", "success");
    } catch (error) { outcomeTone.failure(); setStatus(error.message, "error"); }
    finally { state.busy = false; renderControls(); }
  }

  async function refinePrompt() {
    await submitPromptRevision(elements.message.value.trim());
  }

  async function retryRejectedRevision() {
    await submitPromptRevision(
      "Corrige la structure de la dernière proposition refusée sans changer mon intention.",
      { repairRejected: true },
    );
  }

  if (elements.convert) elements.convert.addEventListener("click", () => {
    if (!state.project || elements.convert.disabled) return;
    window.dispatchEvent(new CustomEvent("panelforge:convert-h3", { detail: {
      project: state.project, settings: renderParameters(),
      model_id: elements.revisionModel.value, include_reasoning: elements.reasoning.checked,
    }}));
  });
  elements.render.addEventListener("click", renderAttempt);
  elements.videoLoraInfo?.addEventListener("click", async () => {
    elements.videoLoraInfo.dataset.loading = "true"; renderControls();
    try { await window.PanelForgeH3LoraInfo.open(elements.videoLoraModel.value); }
    catch (error) { setStatus(`Fiche LoRA indisponible : ${error.message}`, "error"); }
    finally { elements.videoLoraInfo.dataset.loading = "false"; renderControls(); }
  });
  if (elements.recipe) elements.recipe.addEventListener("change", () => { switchRecipe(elements.recipe.value).catch(() => {}); });
  if (elements.bunnyTurbo) elements.bunnyTurbo.addEventListener("change", () => {
    // A checkpoint may already contain Turbo: bypassing the extra LoRA must
    // not silently replace a distilled schedule with 30/25/5 steps.
    syncBunny(); renderControls();
  });
  elements.preset?.addEventListener("change", () => {
    if (elements.preset.disabled || !state.spec) return;
    if (bunnyActive()) {
      const profile = state.spec.bunny.turbo_profiles?.[elements.preset.value];
      if (!profile) return;
      elements.bunnyBase.value = String(profile.base_steps);
      elements.bunnyCoarse.value = String(profile.coarse_steps);
      elements.bunnyRefine.value = String(profile.refine_steps);
    } else if (elements.preset.value === "default") {
      elements.steps.value = String(state.spec.defaults.steps);
    }
    syncBunny(); renderControls();
  });
  elements.loraEnabled?.addEventListener("change", () => {
    elements.videoLoraProfile.value = elements.loraEnabled.checked ? "lora" : "standard";
    syncVideoLoraControls(); renderControls();
  });
  elements.steps.addEventListener("input", renderControls);
  for (const field of [elements.ratio, elements.initialMegapixels, elements.megapixels, elements.bunnyBase, elements.bunnyCoarse, elements.bunnyRefine, elements.bunnySecond]) {
    if (field) field.addEventListener("input", () => { syncBunny(); renderControls(); });
  }
  elements.cancel.addEventListener("click", cancelAttempt);
  elements.refine.addEventListener("click", refinePrompt);
  if (elements.revisionRetry) elements.revisionRetry.addEventListener("click", retryRejectedRevision);
  elements.message.addEventListener("input", renderControls);
  elements.prompt.addEventListener("input", () => { renderWarnings(); renderControls(); });
  elements.duration.addEventListener("input", renderWarnings);
  if (elements.videoLoraProfile) elements.videoLoraProfile.addEventListener("change", syncVideoLoraControls);
  if (elements.videoLoraModel) elements.videoLoraModel.addEventListener("change", renderControls);
  if (elements.videoLoraStrength) elements.videoLoraStrength.addEventListener("input", syncVideoLoraControls);
  if (elements.revisionVersion) elements.revisionVersion.addEventListener("change", () => {
    state.selectedRevisionVersion = elements.revisionVersion.value; renderControls();
  });
  if (elements.dialogue) elements.dialogue.addEventListener("input", renderControls);
  if (elements.revisionAudacity) elements.revisionAudacity.addEventListener("input", syncRevisionAudacity);
  if (elements.revisionModel) elements.revisionModel.addEventListener("change", renderControls);
  window.addEventListener(contextEvent, (event) => openContext(event.detail));
  window.addEventListener("beforeunload", () => { stopPolling(); closeSocket(); if (state.previewUrl) URL.revokeObjectURL(state.previewUrl); });
  }

  mount("h3r", "panelforge:h3-base-context", "h3-base");
  mount("ref2vr", "panelforge:ref2v-context", "ref2va");
})();
