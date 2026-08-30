(() => {
  "use strict";

  const core = window.PanelForgeLabCore;
  const resourceUi = window.PanelForgeKrea2ResourceUi;
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    form: $("#production-form"), source: $("#production-source"), sourceName: $("#production-source-name"), sourcePreview: $("#production-source-preview"),
    name: $("#production-name"), intention: $("#production-intention"), mode: $("#production-mode"),
    llm: $("#production-llm"), renderModel: $("#production-render-model"), ratio: $("#production-ratio"),
    imageMp: $("#production-image-mp"), loras: $("#production-loras"), loraAssisted: $("#production-lora-assisted"), refresh: $("#production-refresh"),
    catalogManager: $("#production-catalog-manager"),
    h3VideoLoraProfile: $("#production-h3-video-lora-profile"), h3VideoLoraFields: $("#production-h3-video-lora-fields"),
    h3VideoLoraModel: $("#production-h3-video-lora-model"), h3VideoLoraStrength: $("#production-h3-video-lora-strength"),
    h3VideoLoraClip: $("#production-h3-video-lora-clip"), h3VideoLoraWarning: $("#production-h3-video-lora-warning"),
    creativeDirection: $("#production-creative-direction"),
    creativeAudacity: $("#production-audacity"), creativeAudacityValue: $("#production-audacity-value"),
    sceneLife: $("#production-scene-life"), camera: $("#production-camera"), extraMotion: $("#production-extra-motion"),
    stopTemp: $("#production-stop-temp"), resumeTemp: $("#production-resume-temp"), cooldown: $("#production-cooldown"),
    previewLimit: $("#production-preview-limit"), monitorLocal: $("#production-monitor-local"),
    monitorRemote: $("#production-monitor-remote"), pauseUnavailable: $("#production-pause-unavailable"), music: $("#production-music"),
    formMessage: $("#production-form-message"), start: $("#production-start"), refreshJobs: $("#production-refresh-jobs"),
    jobList: $("#production-job-list"), empty: $("#production-empty"), job: $("#production-job"),
    title: $("#production-job-title"), status: $("#production-job-status"), stage: $("#production-stage-label"),
    progress: $("#production-progress-bar"), message: $("#production-job-message"), cancel: $("#production-cancel"), retry: $("#production-retry"),
    images: $("#production-images"), imageRecommendation: $("#production-image-recommendation"), imageReview: $("#production-image-review"), approveImage: $("#production-approve-image"),
    h3Audit: $("#production-h3-audit"), h3AuditStatus: $("#production-h3-audit-status"),
    h3Contract: $("#production-h3-contract"), h3Documents: $("#production-h3-documents"),
    previews: $("#production-previews"), videoReview: $("#production-video-review"),
    instruction: $("#production-video-instruction"), acceptVideo: $("#production-accept-video"), reviseVideo: $("#production-revise-video"),
    final: $("#production-final"), events: $("#production-events"),
    imageDialog: $("#production-image-dialog"), imageDialogTitle: $("#production-image-dialog-title"),
    imageDialogContent: $("#production-image-dialog-content"), imageDialogClose: $("#production-image-dialog-close"),
  };
  if (!elements.form || !core) return;

  const state = {
    spec: null, job: null, selectedImage: null, selectedPreview: null, timer: null, lastTerminal: null,
    h3Audit: null, h3AuditKey: null, h3AuditError: null,
    sourcePreviewUrl: null, previewRenderKey: null, finalRenderKey: null,
    revisionSuggestionJobId: null, revisionSuggestionAttemptId: null, revisionSuggestionText: "",
  };
  const stages = ["setup", "image_generation", "image_selection", "h3_prompt", "video_preview", "video_evaluation", "video_final", "complete"];
  const stageLabels = {
    setup: "PRÉPARATION", image_generation: "RECHERCHE KREA2", image_selection: "SÉLECTION IMAGE",
    h3_prompt: "COMPILATION H3", video_preview: "PREVIEW H3", video_evaluation: "ÉVALUATION",
    video_final: "RENDU FINAL", complete: "TERMINÉ",
  };

  function option(value, label) {
    const item = document.createElement("option"); item.value = value; item.textContent = label; return item;
  }

  function preferredRenderModel(models) {
    return models.find((item) => /krea2gptgrandpussytruth/i.test(item.comfy_name))
      || models.find((item) => /krea2_turbo_bf16/i.test(item.comfy_name))
      || models[0]
      || null;
  }

  function showError(message = "") {
    elements.formMessage.textContent = message; elements.formMessage.hidden = !message;
  }

  async function loadSpec() {
    const nextSpec = await core.request("/api/production/spec");
    const previousLlm = elements.llm.value;
    const previousModel = elements.renderModel.value;
    const previousRatio = elements.ratio.value;
    const previousH3Lora = elements.h3VideoLoraModel.value;
    state.spec = nextSpec;
    if (window.PanelForgeModelPicker) {
      window.PanelForgeModelPicker.populate(elements.llm, state.spec.llm_models || [], previousLlm);
    } else {
      elements.llm.replaceChildren(...(state.spec.llm_models || []).map((model) => option(model.model_id, model.display_name || model.model_id)));
    }
    if (resourceUi) {
      resourceUi.appendGroupedOptions(elements.renderModel, state.spec.render_models || [], resourceUi.modelGroups);
    } else {
      elements.renderModel.replaceChildren(...(state.spec.render_models || []).map((model) => option(model.comfy_name, model.filename || model.comfy_name)));
    }
    const renderDefault = preferredRenderModel(state.spec.render_models || []);
    elements.renderModel.value = previousModel && [...elements.renderModel.options].some((item) => item.value === previousModel)
      ? previousModel
      : (renderDefault?.comfy_name || "");
    elements.ratio.replaceChildren(...(state.spec.aspect_ratios || []).map((ratio) => option(ratio, ratio)));
    elements.ratio.value = previousRatio && [...elements.ratio.options].some((item) => item.value === previousRatio)
      ? previousRatio
      : state.spec.defaults.aspect_ratio;
    renderLoras();
    renderCatalogManager();
    elements.h3VideoLoraModel.replaceChildren(...(state.spec.h3_video_loras || []).map((name) => option(name, name)));
    if (previousH3Lora && [...elements.h3VideoLoraModel.options].some((item) => item.value === previousH3Lora)) {
      elements.h3VideoLoraModel.value = previousH3Lora;
    }
    const loraOption = elements.h3VideoLoraProfile.querySelector('option[value="lora"]');
    if (loraOption) loraOption.disabled = !(state.spec.h3_video_loras || []).length;
    elements.h3VideoLoraWarning.textContent = state.spec.h3_video_lora_warning || (!(state.spec.h3_video_loras || []).length ? "Aucun LoRA MiniMax trouvé dans minmax_nsfw/." : "");
    elements.h3VideoLoraWarning.hidden = !elements.h3VideoLoraWarning.textContent;
    renderH3VideoLoraControls();
  }

  function renderH3VideoLoraControls() {
    const enabled = elements.h3VideoLoraProfile.value === "lora";
    elements.h3VideoLoraFields.hidden = !enabled;
    elements.h3VideoLoraModel.disabled = !enabled;
    elements.h3VideoLoraStrength.disabled = !enabled;
    elements.h3VideoLoraClip.disabled = !enabled;
  }

  function renderLoras() {
    const values = [...elements.loras.querySelectorAll(".production-lora-row")].map((row) => ({
      name: row.querySelector("select").value, strength: row.querySelector("input").value,
    }));
    elements.loras.replaceChildren();
    for (let index = 0; index < 4; index += 1) {
      const row = document.createElement("div"); row.className = "production-lora-row";
      const select = document.createElement("select");
      if (resourceUi) {
        resourceUi.appendGroupedOptions(select, state.spec.loras || [], resourceUi.loraGroups, { includeEmpty: true });
      } else {
        select.append(option("", "Aucun"));
        (state.spec.loras || []).forEach((lora) => select.append(option(lora.comfy_name, lora.filename || lora.comfy_name)));
      }
      const strength = document.createElement("input"); strength.type = "number"; strength.min = "-1"; strength.max = "1"; strength.step = "0.05"; strength.value = values[index]?.strength || "0";
      if (values[index]?.name) select.value = values[index].name;
      select.addEventListener("change", () => { if (!select.value) strength.value = "0"; });
      strength.addEventListener("change", () => {
        const value = Number(strength.value);
        strength.value = String(Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0);
      });
      row.append(select, strength); elements.loras.append(row);
    }
  }

  function selectedLoras() {
    return [...elements.loras.querySelectorAll(".production-lora-row")].map((row) => {
      const name = row.querySelector("select").value;
      const strength = Number(row.querySelector("input").value);
      if (name && (!Number.isFinite(strength) || strength < -1 || strength > 1)) {
        throw new Error("La force de chaque LoRA Production doit être comprise entre -1 et 1.");
      }
      return { name, strength };
    }).filter((value) => value.name);
  }

  async function updatePreference(resource, values) {
    try {
      await core.request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadSpec();
      showError();
    } catch (error) { showError(error.message); }
  }

  function renderCatalogManager() {
    if (!resourceUi || !elements.catalogManager) return;
    resourceUi.renderCatalogManager(elements.catalogManager, {
      models: state.spec?.render_models || [],
      loras: state.spec?.loras || [],
      updatePreference,
    });
  }

  async function submit(event) {
    event.preventDefault(); showError();
    elements.start.disabled = true;
    try {
      const data = new FormData();
      data.set("source", elements.source.files[0]); data.set("name", elements.name.value); data.set("intention", elements.intention.value);
      data.set("model_id", elements.llm.value); data.set("render_model_id", elements.renderModel.value); data.set("aspect_ratio", elements.ratio.value);
      data.set("image_megapixels", elements.imageMp.value); data.set("loras_json", JSON.stringify(selectedLoras())); data.set("mode", elements.mode.value);
      data.set("scene_life", elements.sceneLife.value); data.set("camera", elements.camera.value);
      data.set("extra_motion", elements.extraMotion.value); data.set("video_preview_limit", elements.previewLimit.value);
      data.set("video_acceptance_score", "80"); data.set("duration_seconds", "10"); data.set("video_steps", "25");
      data.set("music_enabled", String(elements.music.checked)); data.set("stop_temperature_c", elements.stopTemp.value);
      data.set("resume_temperature_c", elements.resumeTemp.value); data.set("cooldown_seconds", elements.cooldown.value);
      data.set("monitor_local", String(elements.monitorLocal.checked)); data.set("monitor_remote", String(elements.monitorRemote.checked));
      data.set("pause_when_unavailable", String(elements.pauseUnavailable.checked));
      data.set("assisted_lora_selection", String(elements.loraAssisted.checked));
      data.set("creative_direction_enabled", String(elements.creativeDirection.checked));
      data.set("creative_audacity", elements.creativeAudacity.value);
      data.set("h3_video_lora_enabled", String(elements.h3VideoLoraProfile.value === "lora"));
      data.set("h3_video_lora_name", elements.h3VideoLoraModel.value);
      data.set("h3_video_lora_strength", elements.h3VideoLoraStrength.value);
      data.set("h3_video_lora_clip_last_layer", String(elements.h3VideoLoraClip.checked));
      let payload = await core.request("/api/production/jobs", { method: "POST", body: data });
      state.job = payload.job; state.selectedImage = null; state.selectedPreview = null; state.revisionSuggestionJobId = null; renderJob();
      payload = await core.request(`/api/production/jobs/${state.job.job_id}/start`, { method: "POST" });
      state.job = payload.job; renderJob(); startPolling(); await loadJobs();
    } catch (error) { showError(error.message); core.playFailureTone(); }
    finally { elements.start.disabled = false; }
  }

  async function loadJobs() {
    const payload = await core.request("/api/production/jobs?limit=30");
    elements.jobList.replaceChildren();
    if (!payload.jobs.length) { elements.jobList.innerHTML = '<p class="muted">Aucun job.</p>'; return; }
    payload.jobs.forEach((job) => {
      const button = document.createElement("button"); button.type = "button"; button.className = "production-job-link";
      button.append(document.createTextNode(job.name), Object.assign(document.createElement("small"), { textContent: `${stageLabels[job.stage] || job.stage} · ${job.status}` }));
      button.addEventListener("click", () => { state.job = job; state.selectedImage = null; state.selectedPreview = null; state.revisionSuggestionJobId = null; renderJob(); if (!isTerminal(job)) startPolling(); });
      elements.jobList.append(button);
    });
  }

  function isTerminal(job) { return ["succeeded", "failed", "cancelled", "waiting_for_review"].includes(job.status); }

  function startPolling() {
    if (state.timer) clearTimeout(state.timer);
    const poll = async () => {
      if (!state.job) return;
      try {
        const payload = await core.request(`/api/production/jobs/${state.job.job_id}`); state.job = payload.job; renderJob();
        if (!isTerminal(state.job)) state.timer = setTimeout(poll, 2000); else loadJobs().catch(() => {});
      } catch (error) { elements.message.textContent = error.message; state.timer = setTimeout(poll, 4000); }
    };
    state.timer = setTimeout(poll, 800);
  }

  function renderJob() {
    const job = state.job; if (!job) return;
    elements.empty.hidden = true; elements.job.hidden = false; elements.title.textContent = job.name;
    elements.stage.textContent = stageLabels[job.stage] || job.stage; elements.status.textContent = `● ${job.status}`;
    elements.status.className = `run-status ${job.status}`; elements.progress.style.width = `${Math.max(2, (stages.indexOf(job.stage) + 1) / stages.length * 100)}%`;
    elements.message.textContent = job.error || job.pause_reason || job.events.at(-1)?.message || "Traitement en cours…";
    elements.cancel.disabled = ["succeeded", "failed", "cancelled"].includes(job.status) || job.cancel_requested;
    elements.cancel.textContent = job.cancel_requested ? "Arrêt demandé…" : "Arrêter le flux";
    elements.retry.hidden = job.status !== "failed"; elements.retry.disabled = job.status !== "failed";
    renderImages(job); renderH3Audit(job); renderPreviews(job); renderFinal(job); renderEvents(job); renderRevisionSuggestion(job);
    if (["succeeded", "failed", "cancelled"].includes(job.status) && state.lastTerminal !== `${job.job_id}:${job.status}`) {
      state.lastTerminal = `${job.job_id}:${job.status}`;
      if (job.status === "succeeded") core.playCompletionTone(); else core.playFailureTone();
    }
  }

  function renderImages(job) {
    elements.images.replaceChildren();
    renderImageRecommendation(job);
    const recommendation = [...(job.decisions || [])].reverse().find((value) => value.kind === "image_selection");
    const assessmentByAttempt = new Map((recommendation?.assessments || []).map((value) => [value.attempt_id, value]));
    const recommendedId = recommendation?.attempt_id || null;
    const canSelect = job.status === "waiting_for_review" && job.stage === "image_selection";
    const cards = [{ attempt_id: "source", output_url: job.source_url, index: 0, status: "immutable" }, ...(job.image_attempts || [])];
    cards.forEach((attempt) => {
      const figure = document.createElement("figure");
      const selected = attempt.attempt_id === (state.selectedImage || job.selected_image_attempt_id);
      figure.classList.toggle("selected", selected); figure.classList.toggle("recommended", attempt.attempt_id === recommendedId);
      const image = document.createElement("img"); image.src = attempt.output_url || ""; image.alt = attempt.index ? `Candidat ${attempt.index}` : "Source immuable"; image.loading = "lazy";
      const open = document.createElement("button"); open.type = "button"; open.className = "production-image-open"; open.title = "Agrandir l’image";
      open.setAttribute("aria-label", `Agrandir ${image.alt}`); open.append(image);
      open.addEventListener("click", () => openImageDialog(attempt.output_url, image.alt));
      const caption = document.createElement("figcaption");
      const label = document.createElement("span"); label.className = "production-image-caption";
      const assessment = assessmentByAttempt.get(attempt.attempt_id);
      label.textContent = attempt.index
        ? `Essai ${attempt.index} · ${attempt.status}${assessment ? ` · ${assessment.score}/100` : ""}`
        : "Source immuable";
      caption.append(label);
      if (attempt.index && attempt.status === "succeeded" && canSelect) {
        const choose = document.createElement("button"); choose.type = "button"; choose.className = "production-image-select";
        choose.textContent = selected ? "Image choisie" : "Choisir cet essai"; choose.disabled = selected;
        choose.addEventListener("click", () => { state.selectedImage = attempt.attempt_id; renderImages(job); });
        caption.append(choose);
      }
      figure.append(open, caption);
      elements.images.append(figure);
    });
    elements.imageReview.hidden = !(job.status === "waiting_for_review" && job.stage === "image_selection");
  }

  function renderImageRecommendation(job) {
    const decision = [...(job.decisions || [])].reverse().find((value) => value.kind === "image_selection");
    const plan = job.lora_plan;
    if (!decision && !plan) { elements.imageRecommendation.hidden = true; elements.imageRecommendation.replaceChildren(); return; }
    elements.imageRecommendation.hidden = false; elements.imageRecommendation.replaceChildren();
    if (decision) {
      const attempts = new Map((job.image_attempts || []).map((attempt) => [attempt.attempt_id, attempt]));
      const recommended = attempts.get(decision.attempt_id);
      const currentId = state.selectedImage || job.selected_image_attempt_id;
      const current = attempts.get(currentId);
      const head = document.createElement("div"); head.className = "production-recommendation-head";
      const title = document.createElement("strong"); title.textContent = `Recommandation LLM · Essai ${recommended?.index || "?"} · ${decision.score}/100`;
      const currentLabel = document.createElement("span");
      currentLabel.textContent = currentId && currentId !== decision.attempt_id ? `Choix actuel : Essai ${current?.index || "?"} (manuel)` : "Choix actuel : recommandation LLM";
      head.append(title, currentLabel); elements.imageRecommendation.append(head);
      const scores = document.createElement("div"); scores.className = "production-score-list";
      if ((decision.assessments || []).length) {
        decision.assessments.forEach((assessment) => {
          const attempt = attempts.get(assessment.attempt_id); const score = document.createElement("span");
          score.className = "production-score"; score.classList.toggle("recommended", assessment.attempt_id === decision.attempt_id);
          score.textContent = `Essai ${attempt?.index || "?"} · ${assessment.score}/100`; scores.append(score);
        });
      } else {
        const score = document.createElement("span"); score.className = "production-score recommended";
        score.textContent = `Essai ${recommended?.index || "?"} · ${decision.score}/100 · autres non évalués`; scores.append(score);
      }
      elements.imageRecommendation.append(scores);
      const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Voir l’analyse"; details.append(summary);
      if ((decision.assessments || []).length) {
        const list = document.createElement("ol"); list.className = "production-recommendation-analysis";
        decision.assessments.forEach((assessment) => {
          const item = document.createElement("li"); const attempt = attempts.get(assessment.attempt_id);
          item.textContent = `Essai ${attempt?.index || "?"} · ${assessment.score}/100 — ${assessment.summary}`; list.append(item);
        });
        details.append(list);
      }
      const rationale = document.createElement("p"); rationale.textContent = decision.rationale; details.append(rationale); elements.imageRecommendation.append(details);
    }
    if (plan) {
      const lora = document.createElement("div"); lora.className = "production-lora-plan-summary";
      lora.textContent = `LoRA expérimentales : ${plan.choices?.length ? plan.choices.map((value) => `${value.name} × ${value.strength}`).join(" · ") : "aucune"} — ${plan.rationale}`;
      elements.imageRecommendation.append(lora);
    }
  }

  function openImageDialog(url, title) {
    if (!url || !elements.imageDialog) return;
    elements.imageDialogContent.src = url; elements.imageDialogContent.alt = title; elements.imageDialogTitle.textContent = title;
    if (!elements.imageDialog.open) elements.imageDialog.showModal();
  }

  function auditDocument(title, value) {
    const details = document.createElement("details"); details.className = "production-h3-document";
    const summary = document.createElement("summary");
    summary.textContent = `${title} · ${value?.status === "approved" ? "approuvé" : value?.status === "draft" ? "brouillon" : "en attente"}`;
    details.append(summary);
    if (value?.content) {
      const pre = document.createElement("pre"); pre.textContent = value.content; details.append(pre);
    } else {
      const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "Pas encore généré."; details.append(empty);
    }
    return details;
  }

  function promptDetails(title, prompt) {
    if (!prompt) return null;
    const details = document.createElement("details"); details.className = "production-render-prompt";
    const summary = document.createElement("summary"); summary.textContent = title;
    const pre = document.createElement("pre"); pre.textContent = prompt;
    details.append(summary, pre);
    details.addEventListener("click", (event) => event.stopPropagation());
    return details;
  }

  function renderH3Audit(job) {
    if (!elements.h3Audit) return;
    const visible = Boolean(job.selected_image_asset_id || job.prompt_session_id || job.h3_project_id);
    elements.h3Audit.hidden = !visible;
    if (!visible) return;

    const loaded = state.h3Audit?.job_id === job.job_id ? state.h3Audit.audit : null;
    const input = loaded?.input || {};
    const selected = (job.image_attempts || []).find((value) => value.attempt_id === job.selected_image_attempt_id);
    const mode = input.mode || (job.selected_image_asset_id ? "i2va" : "pending");
    const first = input.first_frame;
    const pills = [
      `Mode ${String(mode).toUpperCase()}`,
      `First frame : ${first?.attempt_index ? `Essai ${first.attempt_index}` : selected?.index ? `Essai ${selected.index}` : "en attente"}`,
      `Last frame : ${input.last_frame ? "présente" : "aucune"}`,
      `Ratio : ${input.aspect_ratio || job.config.image_settings.aspect_ratio}`,
      `${input.duration_seconds ?? job.config.duration_seconds} s`,
      `${input.steps ?? job.config.video_steps ?? "?"} steps`,
      `Preview ${input.preview_megapixels ?? job.config.preview_megapixels} MP → final ${input.final_megapixels ?? job.config.final_megapixels} MP`,
      `Seed : ${input.seed || job.video_seed || "à créer"}${input.seed_locked || job.video_seed ? " · verrouillée" : ""}`,
      `Musique ${(input.music_enabled ?? job.config.music_enabled) ? "ON" : "OFF"}`,
      (input.h3_video_lora || job.config.h3_video_lora)
        ? `LoRA vidéo H3 ${(input.h3_video_lora || job.config.h3_video_lora).name} × ${Number((input.h3_video_lora || job.config.h3_video_lora).strength).toFixed(2)}${(input.h3_video_lora || job.config.h3_video_lora).clip_last_layer === -2 ? " · CLIP -2" : ""}`
        : "LoRA vidéo H3 Standard",
      `Direction créative ${job.config.creative_direction_enabled ? `ON · Brief 0.2.0 · audace ${loaded?.brief_audacity ?? job.config.creative_audacity}/3` : "OFF · Brief standard"}`,
    ];
    elements.h3Contract.replaceChildren(...pills.map((text) => {
      const pill = document.createElement("span"); pill.textContent = text; return pill;
    }));

    const thinking = job.stage === "h3_prompt" && ["queued", "running", "waiting_resource"].includes(job.status);
    elements.h3AuditStatus.textContent = thinking ? "● thinking" : job.h3_project_id ? "● Compilé" : "● En attente";
    elements.h3AuditStatus.className = `run-status${thinking ? " thinking" : ""}`;

    elements.h3Documents.replaceChildren();
    if (state.h3AuditError && !loaded) {
      const error = document.createElement("p"); error.className = "error"; error.textContent = state.h3AuditError; elements.h3Documents.append(error);
    } else if (loaded) {
      const profile = document.createElement("small"); profile.className = "muted";
      const briefVariant = loaded.brief_variant
        ? `Brief ${loaded.brief_variant.id}@${loaded.brief_variant.version}`
        : `Brief standard ${loaded.profile.version}`;
      profile.textContent = `${briefVariant} · Plan/Writer ${loaded.profile.id}@${loaded.profile.version}`; elements.h3Documents.append(profile);
      elements.h3Documents.append(
        auditDocument("Brief compact", loaded.documents?.brief),
        auditDocument("Plan JSON", loaded.documents?.beat_sheet),
        auditDocument("Prompt H3 final", loaded.documents?.final_prompt),
      );
      const current = promptDetails("Prompt courant réellement utilisé par l’atelier H3", loaded.current_prompt);
      if (current) elements.h3Documents.append(current);
    } else {
      const waiting = document.createElement("p"); waiting.className = "muted"; waiting.textContent = "Chargement de la trace H3…"; elements.h3Documents.append(waiting);
    }

    if (!job.prompt_session_id) return;
    const lastEventId = job.events?.at(-1)?.event_id || "none";
    const key = `${job.job_id}:${lastEventId}:${job.h3_project_id || "none"}`;
    if (state.h3AuditKey === key) return;
    state.h3AuditKey = key; state.h3AuditError = null;
    core.request(`/api/production/jobs/${job.job_id}/h3-audit`).then((payload) => {
      if (state.job?.job_id !== job.job_id) return;
      state.h3Audit = { job_id: job.job_id, audit: payload.audit }; renderH3Audit(state.job);
    }).catch((error) => {
      if (state.job?.job_id !== job.job_id) return;
      state.h3AuditError = error.message; renderH3Audit(state.job);
    });
  }

  function renderPreviews(job) {
    const reviewVisible = job.status === "waiting_for_review" && job.stage === "video_evaluation";
    elements.videoReview.hidden = !reviewVisible;
    const key = JSON.stringify({
      job_id: job.job_id,
      selected: state.selectedPreview || job.selected_preview_attempt_id,
      previews: (job.previews || []).map((attempt) => ({
        id: attempt.attempt_id, status: attempt.status, output: attempt.output_url,
        prompt: attempt.effective_prompt || attempt.prompt, settings: attempt.settings,
        score: (job.decisions || []).find((value) => value.kind === "video_evaluation" && value.attempt_id === attempt.attempt_id)?.score,
      })),
    });
    if (state.previewRenderKey === key) return;
    state.previewRenderKey = key;
    elements.previews.replaceChildren();
    (job.previews || []).forEach((attempt) => {
      const card = document.createElement("article"); card.className = "production-video-card";
      card.classList.toggle("selected", attempt.attempt_id === (state.selectedPreview || job.selected_preview_attempt_id));
      if (attempt.output_url) { const video = document.createElement("video"); video.src = attempt.output_url; video.controls = true; video.preload = "metadata"; card.append(video); }
      const decision = (job.decisions || []).find((value) => value.kind === "video_evaluation" && value.attempt_id === attempt.attempt_id);
      const summary = document.createElement("small");
      summary.textContent = `Essai ${attempt.index} · ${attempt.settings.aspect_ratio} · ${attempt.settings.megapixels} MP · ${attempt.settings.steps} steps${decision ? ` · score ${decision.score}/100` : ""}`;
      card.append(summary);
      const prompt = promptDetails("Voir le prompt H3 réellement envoyé", attempt.effective_prompt || attempt.prompt);
      if (prompt) card.append(prompt);
      card.addEventListener("click", () => { state.selectedPreview = attempt.attempt_id; renderPreviews(job); }); elements.previews.append(card);
    });
  }

  function renderFinal(job) {
    const key = JSON.stringify({ job_id: job.job_id, attempt: job.final_attempt || null });
    if (state.finalRenderKey === key) return;
    state.finalRenderKey = key;
    elements.final.replaceChildren();
    if (!job.final_attempt?.output_url) { elements.final.innerHTML = '<p class="muted">En attente du meilleur preview.</p>'; return; }
    const video = document.createElement("video"); video.src = job.final_attempt.output_url; video.controls = true; video.preload = "metadata"; elements.final.append(video);
    const settings = job.final_attempt.settings;
    const summary = document.createElement("small"); summary.className = "production-final-settings";
    summary.textContent = `${settings.aspect_ratio} · ${settings.resolution.width}×${settings.resolution.height} · ${settings.megapixels} MP · ${settings.duration_seconds} s · ${settings.steps} steps · seed ${settings.seed}`;
    elements.final.append(summary);
    const prompt = promptDetails("Voir le prompt H3 réellement envoyé", job.final_attempt.effective_prompt || job.final_attempt.prompt);
    if (prompt) elements.final.append(prompt);
  }

  function renderRevisionSuggestion(job) {
    if (state.revisionSuggestionJobId !== job.job_id) {
      state.revisionSuggestionJobId = job.job_id;
      state.revisionSuggestionAttemptId = null;
      state.revisionSuggestionText = "";
      elements.instruction.value = "";
    }
    const decision = [...(job.decisions || [])].reverse().find((value) =>
      value.kind === "video_evaluation" && value.outcome === "revise" && value.revision_instruction
    );
    if (!decision || state.revisionSuggestionAttemptId === decision.attempt_id) return;
    const current = elements.instruction.value.trim();
    if (!current || current === state.revisionSuggestionText.trim()) {
      elements.instruction.value = decision.revision_instruction;
    }
    state.revisionSuggestionAttemptId = decision.attempt_id;
    state.revisionSuggestionText = decision.revision_instruction;
  }

  function renderEvents(job) {
    elements.events.replaceChildren();
    [...(job.events || [])].reverse().forEach((event) => {
      const item = document.createElement("li"); item.className = event.level;
      if (event.message.includes("· thinking ·")) item.classList.add("thinking");
      const time = new Date(event.timestamp).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      item.textContent = `${time} · ${stageLabels[event.stage] || event.stage} · ${event.message}`; elements.events.append(item);
    });
    (job.decisions || []).slice().reverse().forEach((decision) => {
      const item = document.createElement("li");
      const time = new Date(decision.timestamp).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      item.textContent = `${time} · Décision ${decision.kind} · ${decision.outcome} · ${decision.score}/100 — ${decision.rationale}`; elements.events.append(item);
    });
  }

  async function postReview(path, body) {
    const payload = await core.request(`/api/production/jobs/${state.job.job_id}/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    state.job = payload.job; renderJob(); startPolling();
  }

  elements.form.addEventListener("submit", submit);
  elements.source.addEventListener("change", () => {
    if (state.sourcePreviewUrl) URL.revokeObjectURL(state.sourcePreviewUrl);
    state.sourcePreviewUrl = null;
    const file = elements.source.files[0];
    elements.sourceName.textContent = file?.name || "PNG, JPEG ou WebP";
    if (!file) {
      elements.sourcePreview.removeAttribute("src"); elements.sourcePreview.hidden = true; return;
    }
    state.sourcePreviewUrl = URL.createObjectURL(file);
    elements.sourcePreview.src = state.sourcePreviewUrl; elements.sourcePreview.hidden = false;
  });
  function renderCreativeDirectionControls() {
    elements.creativeAudacity.disabled = !elements.creativeDirection.checked;
    elements.creativeAudacityValue.textContent = elements.creativeAudacity.value;
  }
  elements.creativeDirection.addEventListener("change", renderCreativeDirectionControls);
  elements.creativeAudacity.addEventListener("input", renderCreativeDirectionControls);
  elements.h3VideoLoraProfile.addEventListener("change", renderH3VideoLoraControls);
  elements.refresh.addEventListener("click", () => loadSpec().catch((error) => showError(error.message)));
  elements.refreshJobs.addEventListener("click", () => loadJobs().catch((error) => showError(error.message)));
  elements.cancel.addEventListener("click", async () => {
    if (!state.job || state.job.cancel_requested) return;
    elements.cancel.disabled = true; elements.cancel.textContent = "Arrêt demandé…";
    try {
      state.job = (await core.request(`/api/production/jobs/${state.job.job_id}/cancel`, { method: "POST" })).job;
      renderJob(); startPolling();
    } catch (error) {
      elements.message.textContent = error.message; elements.cancel.disabled = false; elements.cancel.textContent = "Arrêter le flux"; core.playFailureTone();
    }
  });
  elements.retry.addEventListener("click", async () => {
    if (!state.job || state.job.status !== "failed") return;
    elements.retry.disabled = true;
    try {
      state.job = (await core.request(`/api/production/jobs/${state.job.job_id}/retry`, { method: "POST" })).job;
      renderJob(); startPolling(); await loadJobs();
    } catch (error) { elements.message.textContent = error.message; core.playFailureTone(); }
  });
  elements.approveImage.addEventListener("click", () => postReview("image-review", { attempt_id: state.selectedImage || state.job.selected_image_attempt_id }).catch((error) => { elements.message.textContent = error.message; core.playFailureTone(); }));
  elements.acceptVideo.addEventListener("click", () => postReview("video-review", { accept: true, attempt_id: state.selectedPreview || state.job.selected_preview_attempt_id }).catch((error) => { elements.message.textContent = error.message; core.playFailureTone(); }));
  elements.reviseVideo.addEventListener("click", () => postReview("video-review", { accept: false, attempt_id: state.selectedPreview || state.job.selected_preview_attempt_id, instruction: elements.instruction.value }).then(() => { elements.instruction.value = ""; }).catch((error) => { elements.message.textContent = error.message; core.playFailureTone(); }));
  elements.imageDialogClose.addEventListener("click", () => elements.imageDialog.close());
  elements.imageDialog.addEventListener("click", (event) => { if (event.target === elements.imageDialog) elements.imageDialog.close(); });
  window.addEventListener("beforeunload", () => { if (state.sourcePreviewUrl) URL.revokeObjectURL(state.sourcePreviewUrl); });

  renderCreativeDirectionControls();
  renderH3VideoLoraControls();
  Promise.all([loadSpec(), loadJobs()]).catch((error) => showError(error.message));
})();
