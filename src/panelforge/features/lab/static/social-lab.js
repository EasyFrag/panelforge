(() => {
  "use strict";

  const core = window.PanelForgeLabCore;
  if (!core) return;
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    form: $("#social-new-form"),
    file: $("#social-video-file"),
    fileName: $("#social-video-file-name"),
    preview: $("#social-video-preview"),
    projectName: $("#social-project-name"),
    model: $("#social-llm"),
    localModel: $("#social-local-llm"),
    refreshModels: $("#social-refresh-models"),
    showReasoning: $("#social-show-reasoning"),
    language: $("#social-language"),
    variantCount: $("#social-variant-count"),
    profile: $("#social-profile"),
    profileName: $("#social-profile-name"),
    newProfile: $("#social-new-profile"),
    saveProfile: $("#social-save-profile"),
    profileMessage: $("#social-profile-message"),
    mood: $("#social-mood"),
    vibe: $("#social-vibe"),
    example: $("#social-example"),
    instructions: $("#social-instructions"),
    formMessage: $("#social-form-message"),
    create: $("#social-create"),
    refreshProjects: $("#social-refresh-projects"),
    projectList: $("#social-project-list"),
    empty: $("#social-empty"),
    project: $("#social-project"),
    projectTitle: $("#social-project-title"),
    projectState: $("#social-project-state"),
    projectVideo: $("#social-project-video"),
    sourcePromptState: $("#social-source-prompt-state"),
    keyframes: $("#social-keyframes"),
    turns: $("#social-turns"),
    message: $("#social-message"),
    refine: $("#social-refine"),
    chatMessage: $("#social-chat-message"),
    variants: $("#social-variants"),
    stream: {
      container: $("#social-stream-state"),
      label: $("#social-stream-label"),
      percent: $("#social-stream-percent"),
      progress: $("#social-stream-progress"),
    },
    tracePanel: $("#social-trace-panel"),
    traceLabel: $("#social-trace-label"),
    traceOutput: $("#social-trace-output"),
    traceEmpty: $("#social-trace-empty"),
  };
  if (!elements.form) return;

  const state = {
    initialized: false,
    initializing: null,
    spec: null,
    profiles: [],
    projects: [],
    project: null,
    videoFile: null,
    previewUrl: null,
    busy: false,
  };

  const reasoningTrace = core.createReasoningTrace({
    toggle: elements.showReasoning,
    panel: elements.tracePanel,
    label: elements.traceLabel,
    output: elements.traceOutput,
    empty: elements.traceEmpty,
  });

  document.querySelectorAll('[data-lab-view="video-lab"], [data-video-lab-mode="social-lab"]').forEach((button) => {
    button.addEventListener("click", () => initialize().catch((error) => {
      showError(elements.formMessage, error.message);
    }));
  });
  elements.form.addEventListener("submit", createProject);
  elements.file.addEventListener("change", selectVideo);
  elements.refreshModels.addEventListener("click", refreshModels);
  elements.refreshProjects.addEventListener("click", () => loadProjects().catch((error) => {
    showError(elements.formMessage, error.message);
  }));
  elements.profile.addEventListener("change", applySelectedProfile);
  elements.newProfile.addEventListener("click", clearProfile);
  elements.saveProfile.addEventListener("click", saveProfile);
  elements.refine.addEventListener("click", refineProject);
  window.addEventListener("beforeunload", revokePreviewUrl);

  async function initialize() {
    if (state.initialized) return;
    if (state.initializing) return state.initializing;
    state.initializing = (async () => {
      const [spec, profiles, projects] = await Promise.all([
        core.request("/api/social-lab/spec"),
        core.request("/api/social-lab/profiles"),
        core.request("/api/social-lab/projects?limit=30"),
      ]);
      state.spec = spec;
      state.profiles = profiles.profiles || [];
      state.projects = projects.projects || [];
      populateModels("");
      renderProfiles();
      renderProjects();
      state.initialized = true;
    })();
    try {
      await state.initializing;
    } finally {
      state.initializing = null;
    }
  }

  async function refreshModels() {
    const current = elements.model.value;
    elements.refreshModels.disabled = true;
    try {
      state.spec = await core.request("/api/social-lab/spec");
      populateModels(current);
      showError(elements.formMessage, "");
    } catch (error) {
      showError(elements.formMessage, error.message);
    } finally {
      elements.refreshModels.disabled = false;
    }
  }

  function populateModels(current) {
    const models = state.spec?.llm_models || [];
    window.PanelForgeModelPicker.populate(elements.model, models, current);
    if (!elements.model.value && models.length) {
      showError(elements.formMessage, "Aucun modèle n’est disponible pour la source sélectionnée.");
    }
  }

  function selectVideo(event) {
    const file = event.target.files?.[0] || null;
    state.videoFile = file;
    revokePreviewUrl();
    if (!file) {
      elements.preview.hidden = true;
      elements.preview.removeAttribute("src");
      elements.fileName.textContent = "4 images seront extraites à 10, 35, 65 et 90 %.";
      return;
    }
    state.previewUrl = URL.createObjectURL(file);
    elements.preview.src = state.previewUrl;
    elements.preview.hidden = false;
    elements.fileName.textContent = `${file.name} · ${formatBytes(file.size)}`;
    if (!elements.projectName.value.trim()) {
      elements.projectName.value = file.name.replace(/\.[^.]+$/, "").slice(0, 120);
    }
  }

  async function createProject(event) {
    event.preventDefault();
    if (state.busy) return;
    try {
      await initialize();
      const file = state.videoFile;
      if (!file) throw new Error("Choisissez une vidéo MP4 ou WebM.");
      if (!elements.model.value) throw new Error("Choisissez un modèle LLM disponible.");
      setBusy(true, "Extraction des 4 images clés…");
      showError(elements.formMessage, "");
      const frames = await extractKeyframes(file);
      setBusy(true, "Création du projet…");
      const data = new FormData();
      data.append("name", elements.projectName.value.trim());
      data.append("model_id", elements.model.value);
      data.append("language", elements.language.value);
      data.append("variant_count", elements.variantCount.value);
      data.append("mood", elements.mood.value.trim());
      data.append("vibe", elements.vibe.value.trim());
      data.append("example", elements.example.value.trim());
      data.append("instructions", elements.instructions.value.trim());
      if (elements.profile.value) data.append("channel_profile_id", elements.profile.value);
      data.append("video", file, file.name);
      frames.forEach((frame, index) => data.append("keyframes", frame, `keyframe-${index + 1}.jpg`));
      const payload = await core.request("/api/social-lab/projects", { method: "POST", body: data });
      renderProject(payload.project);
      await loadProjects();
      await sendMessage("Propose les premières variantes Instagram à partir de cette vidéo et du brief éditorial.");
    } catch (error) {
      showError(elements.formMessage, error.message);
    } finally {
      setBusy(false);
    }
  }

  async function refineProject() {
    if (state.busy || !state.project) return;
    const message = elements.message.value.trim();
    if (!message) {
      showError(elements.chatMessage, "Écrivez la modification souhaitée.");
      return;
    }
    try {
      setBusy(true, "Ajustement des propositions…");
      showError(elements.chatMessage, "");
      await sendMessage(message);
      elements.message.value = "";
      await loadProjects();
    } catch (error) {
      showError(elements.chatMessage, error.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(message) {
    if (!state.project) throw new Error("Aucun projet Social Lab n’est ouvert.");
    reasoningTrace.begin("Texte Instagram");
    elements.stream.container.hidden = false;
    let terminalError = "";
    const outcomeTone = core.createLlmOutcomeTone();
    try {
      outcomeTone.start();
      await core.streamRequest(
        reasoningTrace.streamUrl(`/api/social-lab/projects/${encodeURIComponent(state.project.project_id)}/chat/stream`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            model_id: elements.model.value,
            language: elements.language.value,
            variant_count: Number(elements.variantCount.value),
            mood: elements.mood.value.trim(),
            vibe: elements.vibe.value.trim(),
            example: elements.example.value.trim(),
            instructions: elements.instructions.value.trim(),
            channel_profile_id: elements.profile.value || null,
            update_profile: true,
          }),
        },
        (streamEvent) => {
          reasoningTrace.handle(streamEvent);
          core.updateStreamState(elements.stream, streamEvent);
          if (streamEvent.project) renderProject(streamEvent.project);
          if (streamEvent.error) terminalError = streamEvent.error;
          if (streamEvent.kind === "completed" || streamEvent.kind === "truncated") {
            reasoningTrace.finish();
          }
        },
        { completionTone: false },
      );
      if (terminalError) {
        core.failStreamState(elements.stream, terminalError);
        throw new Error(terminalError);
      }
      outcomeTone.success();
    } catch (error) {
      outcomeTone.failure();
      reasoningTrace.finish();
      throw error;
    }
  }

  async function loadProjects() {
    const payload = await core.request("/api/social-lab/projects?limit=30");
    state.projects = payload.projects || [];
    renderProjects();
  }

  function renderProjects() {
    elements.projectList.replaceChildren();
    if (!state.projects.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucun projet.";
      elements.projectList.append(empty);
      return;
    }
    state.projects.forEach((project) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "social-project-link";
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = project.name;
      const detail = document.createElement("small");
      detail.textContent = `${project.latest_variants?.length || 0} proposition(s) · ${project.turns?.length || 0} message(s)`;
      copy.append(title, detail);
      const thumbnail = document.createElement("img");
      thumbnail.src = project.keyframes?.[0]?.content_url || "";
      thumbnail.alt = "";
      thumbnail.loading = "lazy";
      button.append(copy, thumbnail);
      button.addEventListener("click", () => openProject(project.project_id));
      elements.projectList.append(button);
    });
  }

  async function openProject(projectId) {
    if (state.busy) return;
    setBusy(true, "Ouverture du projet…");
    try {
      const payload = await core.request(`/api/social-lab/projects/${encodeURIComponent(projectId)}`);
      renderProject(payload.project);
      showError(elements.formMessage, "");
    } catch (error) {
      showError(elements.formMessage, error.message);
    } finally {
      setBusy(false);
    }
  }

  function renderProject(project) {
    state.project = project;
    elements.empty.hidden = true;
    elements.project.hidden = false;
    elements.projectTitle.textContent = project.name;
    elements.projectState.textContent = "● Prêt";
    elements.projectVideo.src = project.video_url;
    elements.sourcePromptState.textContent = project.source_prompt_found
      ? "Prompt source retrouvé"
      : "Analyse visuelle uniquement";
    elements.keyframes.replaceChildren();
    (project.keyframes || []).forEach((keyframe) => {
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.src = keyframe.content_url;
      image.alt = `Image clé à ${keyframe.position_percent} %`;
      image.loading = "lazy";
      const caption = document.createElement("figcaption");
      caption.textContent = `${keyframe.position_percent} %`;
      figure.append(image, caption);
      elements.keyframes.append(figure);
    });
    elements.projectName.value = project.name;
    elements.language.value = project.language;
    elements.variantCount.value = project.variant_count;
    elements.mood.value = project.mood || "";
    elements.vibe.value = project.vibe || "";
    elements.example.value = project.example || "";
    elements.instructions.value = project.instructions || "";
    window.PanelForgeModelPicker.select(elements.model, project.model_id, "modèle du projet indisponible");
    elements.profile.value = project.channel_profile_id || "";
    renderTurns(project.turns || []);
    renderVariants(project.latest_variants || []);
  }

  function renderTurns(turns) {
    elements.turns.replaceChildren();
    if (!turns.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Le premier échange apparaîtra ici.";
      elements.turns.append(empty);
      return;
    }
    turns.forEach((turn) => {
      const article = document.createElement("article");
      article.className = `social-turn ${turn.role}`;
      const role = document.createElement("small");
      role.textContent = turn.role === "user" ? "Vous" : "Assistant éditorial";
      const content = document.createElement("p");
      content.textContent = turn.content;
      article.append(role, content);
      elements.turns.append(article);
    });
    elements.turns.scrollTop = elements.turns.scrollHeight;
  }

  function renderVariants(variants) {
    elements.variants.replaceChildren();
    if (!variants.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Aucune proposition pour le moment.";
      elements.variants.append(empty);
      return;
    }
    variants.forEach((variant, index) => {
      const card = document.createElement("article");
      card.className = "social-variant-card";
      const head = document.createElement("div");
      const angle = document.createElement("small");
      angle.textContent = `ANGLE ${index + 1} · ${variant.angle}`;
      const emojis = document.createElement("span");
      emojis.textContent = (variant.emojis || []).join(" ");
      head.append(angle, emojis);
      const hook = document.createElement("h3");
      hook.textContent = variant.hook;
      const caption = document.createElement("p");
      caption.className = "social-caption";
      caption.textContent = variant.caption;
      const hashtags = document.createElement("p");
      hashtags.className = "social-hashtags";
      hashtags.textContent = (variant.hashtags || []).join(" ");
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Tout copier";
      copy.addEventListener("click", async () => {
        const text = [
          variant.hook,
          variant.caption,
          (variant.emojis || []).join(" "),
          (variant.hashtags || []).join(" "),
        ].filter(Boolean).join("\n\n");
        try {
          await navigator.clipboard.writeText(text);
          copy.textContent = "Copié";
          window.setTimeout(() => { copy.textContent = "Tout copier"; }, 1400);
        } catch (_) {
          copy.textContent = "Copie impossible";
        }
      });
      card.append(head, hook, caption, hashtags, copy);
      elements.variants.append(card);
    });
  }

  function renderProfiles() {
    const selected = elements.profile.value;
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Sans profil";
    const options = state.profiles.map((profile) => {
      const option = document.createElement("option");
      option.value = profile.profile_id;
      option.textContent = profile.name;
      return option;
    });
    elements.profile.replaceChildren(empty, ...options);
    if (state.profiles.some((profile) => profile.profile_id === selected)) {
      elements.profile.value = selected;
    }
  }

  function applySelectedProfile() {
    const profile = state.profiles.find((item) => item.profile_id === elements.profile.value);
    if (!profile) return;
    elements.profileName.value = profile.name;
    elements.language.value = profile.language;
    elements.mood.value = profile.mood || "";
    elements.vibe.value = profile.vibe || "";
    elements.example.value = profile.example || "";
    elements.instructions.value = profile.instructions || "";
    showMessage(elements.profileMessage, `Profil « ${profile.name} » appliqué.`);
  }

  function clearProfile() {
    elements.profile.value = "";
    elements.profileName.value = "";
    showMessage(elements.profileMessage, "Nouveau profil : ajustez les champs puis enregistrez.");
  }

  async function saveProfile() {
    const name = elements.profileName.value.trim();
    if (!name) {
      showMessage(elements.profileMessage, "Donnez un nom au profil.", true);
      return;
    }
    elements.saveProfile.disabled = true;
    try {
      const profileId = elements.profile.value;
      const payload = await core.request(
        profileId
          ? `/api/social-lab/profiles/${encodeURIComponent(profileId)}`
          : "/api/social-lab/profiles",
        {
          method: profileId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            language: elements.language.value,
            mood: elements.mood.value.trim(),
            vibe: elements.vibe.value.trim(),
            example: elements.example.value.trim(),
            instructions: elements.instructions.value.trim(),
          }),
        },
      );
      const saved = payload.profile;
      const existing = state.profiles.findIndex((profile) => profile.profile_id === saved.profile_id);
      if (existing >= 0) state.profiles.splice(existing, 1, saved);
      else state.profiles.unshift(saved);
      renderProfiles();
      elements.profile.value = saved.profile_id;
      showMessage(elements.profileMessage, `Profil « ${saved.name} » enregistré.`);
    } catch (error) {
      showMessage(elements.profileMessage, error.message, true);
    } finally {
      elements.saveProfile.disabled = false;
    }
  }

  async function extractKeyframes(file) {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.src = url;
    try {
      await waitFor(video, "loadedmetadata");
      if (!Number.isFinite(video.duration) || video.duration <= 0 || !video.videoWidth || !video.videoHeight) {
        throw new Error("Le navigateur ne peut pas lire les dimensions ou la durée de cette vidéo.");
      }
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("Extraction des images indisponible dans ce navigateur.");
      const frames = [];
      for (const position of [0.10, 0.35, 0.65, 0.90]) {
        const target = Math.min(Math.max(0, video.duration * position), Math.max(0, video.duration - 0.001));
        if (Math.abs(video.currentTime - target) > 0.001) {
          video.currentTime = target;
          await waitFor(video, "seeked");
        }
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        frames.push(await canvasBlob(canvas));
      }
      return frames;
    } finally {
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
    }
  }

  function waitFor(target, eventName) {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        target.removeEventListener(eventName, complete);
        target.removeEventListener("error", fail);
      };
      const complete = () => { cleanup(); resolve(); };
      const fail = () => { cleanup(); reject(new Error("Cette vidéo ne peut pas être décodée par le navigateur.")); };
      target.addEventListener(eventName, complete, { once: true });
      target.addEventListener("error", fail, { once: true });
    });
  }

  function canvasBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => blob ? resolve(blob) : reject(new Error("Une image clé n’a pas pu être extraite.")),
        "image/jpeg",
        0.88,
      );
    });
  }

  function setBusy(busy, label = "") {
    state.busy = busy;
    elements.create.disabled = busy;
    elements.refine.disabled = busy || !state.project;
    elements.projectState.textContent = busy ? "● Traitement…" : "● Prêt";
    if (busy && label) elements.create.textContent = label;
    else elements.create.textContent = "Analyser et proposer";
  }

  function showError(element, message) {
    element.textContent = message || "";
    element.hidden = !message;
  }

  function showMessage(element, message, failed = false) {
    element.textContent = message || "";
    element.classList.toggle("error", failed);
  }

  function revokePreviewUrl() {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
  }

  function formatBytes(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} Kio`;
    return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} Mio`;
  }

  window.PanelForgeSocialLab = Object.freeze({
    open: async () => {
      window.PanelForgeLabNavigation?.switchView("social-lab");
      await initialize();
    },
  });
})();
