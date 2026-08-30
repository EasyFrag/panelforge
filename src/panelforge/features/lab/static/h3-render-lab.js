(() => {
  "use strict";

  function mount(prefix, contextEvent, specMode) {

  const $ = (id) => document.getElementById(id);
  const activeStatuses = new Set(["queued", "running", "cancel_pending"]);
  const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
  const elements = {
    lab: $(`${prefix}-lab`), status: $(`${prefix}-status`), warnings: $(`${prefix}-warnings`),
    prompt: $(`${prefix}-prompt`), ratio: $(`${prefix}-ratio`), megapixels: $(`${prefix}-megapixels`),
    duration: $(`${prefix}-duration`), steps: $(`${prefix}-steps`), seed: $(`${prefix}-seed`),
    seedLock: $(`${prefix}-seed-lock`), music: $(`${prefix}-music`), render: $(`${prefix}-render`),
    cancel: $(`${prefix}-cancel`), mode: $(`${prefix}-mode`), live: $(`${prefix}-live-preview`),
    liveEmpty: $(`${prefix}-live-empty`), final: $(`${prefix}-final-video`),
    finalEmpty: $(`${prefix}-final-empty`), turns: $(`${prefix}-turns`), message: $(`${prefix}-message`),
    reasoning: $(`${prefix}-reasoning`), refine: $(`${prefix}-refine`), trace: $(`${prefix}-trace`),
    attempts: $(`${prefix}-attempts`), revisionVersion: $(`${prefix}-revision-version`),
    revisionDraft: $(`${prefix}-revision-draft`), revisionError: $(`${prefix}-revision-error`),
    revisionDraftContent: $(`${prefix}-revision-draft-content`),
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
  };

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
  function latestAttempt() { return state.project?.attempts?.at(-1) || null; }
  function activeAttempt() {
    return [...(state.project?.attempts || [])].reverse().find((item) => activeStatuses.has(item.status)) || null;
  }

  function setStatus(message, tone = "active") {
    elements.status.textContent = message;
    elements.status.className = `run-status ${tone}`;
  }

  function inferredDuration(prompt, fallback) {
    const matches = [
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

  function hydrateDefaults() {
    if (!state.spec) return;
    const defaults = state.spec.defaults;
    elements.ratio.replaceChildren(...state.spec.aspect_ratios.map((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      return option;
    }));
    elements.ratio.value = defaults.aspect_ratio;
    elements.megapixels.value = String(defaults.megapixels);
    elements.duration.value = String(inferredDuration(state.project?.current_prompt, defaults.duration_seconds));
    elements.steps.value = String(defaults.steps);
    elements.seed.value = randomSeed();
    elements.seedLock.checked = false;
    elements.music.value = "off";
    if (elements.revisionVersion) {
      elements.revisionVersion.replaceChildren(...(state.spec.revision_versions || []).map((item) => {
        const option = document.createElement("option");
        option.value = item.version; option.textContent = item.label;
        return option;
      }));
      state.selectedRevisionVersion = state.project?.revision_version || state.spec.default_revision_version || "0.2.0";
      elements.revisionVersion.value = state.selectedRevisionVersion;
    }
  }

  function fillSettings(attempt) {
    if (!attempt) return;
    const settings = attempt.settings;
    elements.ratio.value = settings.aspect_ratio;
    elements.megapixels.value = String(settings.megapixels);
    elements.duration.value = String(settings.duration_seconds);
    elements.steps.value = String(settings.steps);
    elements.seed.value = String(settings.seed);
    elements.seedLock.checked = true;
    elements.music.value = attempt.music_enabled ? "on" : "off";
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

  function connectPreview(attempt) {
    closeSocket();
    if (!attempt?.events_url) return;
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
        if (payload.type === "kj_preview_override" && data.image) base64Preview(data.image, data.mime);
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
      article.append(body);
      if (turn.questions?.length) {
        const questions = document.createElement("small"); questions.textContent = `Questions : ${turn.questions.join(" · ")}`; article.append(questions);
      }
      elements.turns.append(article);
    });
  }

  function settingsSummary(attempt) {
    const s = attempt.settings;
    return `${s.aspect_ratio.split(" ")[0]} · ${s.megapixels} MP · ${s.duration_seconds} s · ${s.steps} steps · seed ${s.seed} · musique ${attempt.music_enabled ? "ON" : "OFF"}`;
  }

  function renderAttempts() {
    elements.attempts.replaceChildren();
    const attempts = [...(state.project?.attempts || [])].reverse();
    if (!attempts.length) {
      const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "Aucun essai."; elements.attempts.append(empty); return;
    }
    attempts.forEach((attempt) => {
      const card = document.createElement("article");
      card.className = `h3-render-attempt ${attempt.attempt_id === state.project.feedback_attempt_id ? "feedback" : ""}`;
      const header = document.createElement("div"); header.className = "h3-render-attempt-head";
      const title = document.createElement("b"); title.textContent = `Essai ${attempt.index}`;
      const status = document.createElement("span"); status.textContent = attempt.status;
      header.append(title, status); card.append(header);
      if (attempt.output_url) {
        const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.src = attempt.output_url; card.append(video);
      }
      const summary = document.createElement("small"); summary.textContent = settingsSummary(attempt); card.append(summary);
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
        actions.append(resume, feedback); card.append(actions);
      }
      elements.attempts.append(card);
    });
  }

  function renderOutput() {
    const latest = [...(state.project?.attempts || [])].reverse().find((item) => item.output_url);
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
    const changed = state.project?.project_id !== project.project_id;
    state.project = project;
    elements.lab.hidden = false;
    if (changed || !preservePrompt || document.activeElement !== elements.prompt) elements.prompt.value = project.current_prompt;
    if (elements.revisionVersion && changed) {
      state.selectedRevisionVersion = project.revision_version || state.spec?.default_revision_version || "0.2.0";
      elements.revisionVersion.value = state.selectedRevisionVersion;
    }
    if (elements.revisionDraft) {
      const rejected = Boolean(project.revision_error);
      elements.revisionDraft.hidden = !rejected;
      elements.revisionError.textContent = project.revision_error || "";
      elements.revisionDraftContent.value = project.revision_draft || "";
      if (rejected) elements.revisionDraft.open = true;
    }
    elements.mode.textContent = `Mode ${project.input_mode.toUpperCase()} · modèle LLM ${project.model_id}`;
    const warnings = project.warnings || [];
    elements.warnings.hidden = !warnings.length;
    elements.warnings.textContent = warnings.join(" · ");
    renderTurns(); renderAttempts(); renderOutput(); renderControls();
  }

  function renderControls() {
    const active = activeAttempt();
    const disabled = state.busy || Boolean(active);
    elements.render.disabled = disabled || !state.project || !elements.prompt.value.trim();
    elements.cancel.disabled = !active || state.busy;
    elements.refine.disabled = disabled || !state.project || !elements.message.value.trim();
    for (const field of [elements.prompt, elements.ratio, elements.megapixels, elements.duration, elements.steps, elements.seed, elements.seedLock, elements.music]) field.disabled = disabled;
    if (elements.revisionVersion) elements.revisionVersion.disabled = disabled;
    if (active) setStatus(active.status === "cancel_pending" ? "Annulation…" : "Rendu…", "active");
  }

  async function openContext(detail) {
    state.context = detail;
    if (!detail?.ready || !detail.session_id || !detail.prompt_revision_id) {
      elements.lab.hidden = true; state.project = null; stopPolling(); closeSocket(); return;
    }
    const key = `${detail.session_id}:${detail.prompt_revision_id}`;
    if (state.openingKey === key || (state.project?.source_session_id === detail.session_id && state.project?.source_prompt_revision_id === detail.prompt_revision_id)) return;
    state.openingKey = key;
    try {
      if (!state.spec) state.spec = await request(`/api/h3-render/spec?mode=${encodeURIComponent(specMode)}`);
      const payload = await request(`/api/h3-render/projects/from-session/${encodeURIComponent(detail.session_id)}`, { method: "POST" });
      const changed = state.project?.project_id !== payload.project.project_id;
      renderProject(payload.project);
      if (changed) {
        hydrateDefaults();
        if (latestAttempt()) fillSettings(latestAttempt());
      }
      if (activeAttempt()) { connectPreview(activeAttempt()); startPolling(); }
    } catch (error) {
      elements.lab.hidden = false; setStatus(error.message, "error");
    } finally { if (state.openingKey === key) state.openingKey = ""; renderControls(); }
  }

  async function renderAttempt() {
    if (!state.project || state.busy) return;
    state.busy = true; renderControls();
    elements.live.hidden = true; elements.liveEmpty.hidden = false; elements.liveEmpty.textContent = "Connexion à la preview ComfyUI…";
    try {
      const prepared = await request(`/api/h3-render/projects/${encodeURIComponent(projectId())}/attempts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: elements.prompt.value.trim(), aspect_ratio: elements.ratio.value,
          megapixels: Number(elements.megapixels.value), duration_seconds: Number(elements.duration.value),
          steps: Number(elements.steps.value), seed: elements.seedLock.checked ? elements.seed.value.trim() : null,
          seed_locked: elements.seedLock.checked, music_enabled: elements.music.value === "on",
        }),
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
      renderProject(payload.project); fillSettings(attempt); elements.prompt.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) { setStatus(error.message, "error"); }
  }

  async function refinePrompt() {
    const message = elements.message.value.trim(); if (!message || state.busy || !state.project) return;
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
          feedback_attempt_id: state.project.feedback_attempt_id,
          revision_version: elements.revisionVersion?.value || state.project.revision_version || null,
        }),
      }, (event) => {
        if (event.kind === "reasoning" && event.text) { elements.trace.textContent += event.text; elements.trace.scrollTop = elements.trace.scrollHeight; }
        if (event.error) streamError = event.error;
        if (event.project) renderProject(event.project);
      }, { completionTone: false });
      if (streamError) throw new Error(streamError);
      outcomeTone.success();
      elements.message.value = ""; setStatus("Prompt ajusté", "success");
    } catch (error) { outcomeTone.failure(); setStatus(error.message, "error"); }
    finally { state.busy = false; renderControls(); }
  }

  elements.render.addEventListener("click", renderAttempt);
  elements.cancel.addEventListener("click", cancelAttempt);
  elements.refine.addEventListener("click", refinePrompt);
  elements.message.addEventListener("input", renderControls);
  elements.prompt.addEventListener("input", renderControls);
  if (elements.revisionVersion) elements.revisionVersion.addEventListener("change", () => {
    state.selectedRevisionVersion = elements.revisionVersion.value;
  });
  window.addEventListener(contextEvent, (event) => openContext(event.detail));
  window.addEventListener("beforeunload", () => { stopPolling(); closeSocket(); if (state.previewUrl) URL.revokeObjectURL(state.previewUrl); });
  }

  mount("h3r", "panelforge:h3-base-context", "h3-base");
  mount("ref2vr", "panelforge:ref2v-context", "ref2va");
})();
