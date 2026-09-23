(() => {
  "use strict";

  const workspace = document.getElementById("qwen-edit-lab-workspace");
  if (!workspace) return;

  const $ = id => document.getElementById(`qv2-${id}`);
  const api = "/api/image-lab/qwen-edit";
  const activeStatuses = new Set(["queued", "submitting", "running", "cancel_pending"]);
  const imageTypes = new Set(["image/png", "image/jpeg", "image/webp"]);
  const state = {
    project: null, stageId: null, projects: [], models: [], selectedOutput: null, beforeId: null,
    view: "compare", attachmentUsage: "assistant", pending: {}, saving: null, saveTimer: null,
    promptDraft: null, busy: false, initialized: null, pollTimer: null,
  };
  const guide = {
    key: null, loading: null, source: null, base: document.createElement("canvas"),
    mask: document.createElement("canvas"), overlay: document.createElement("canvas"),
    commands: [], active: null, tool: "paint", frame: null,
  };
  const statusLabels = {
    queued: "◷ Planifié", submitting: "● Envoi à Qwen", running: "● Rendu en cours",
    cancel_pending: "● Annulation à vérifier", succeeded: "✓ Terminé",
    failed: "✕ Erreur", cancelled: "— Annulé",
  };

  const stage = () => state.project?.stages.find(item => item.id === state.stageId) || null;
  const editable = () => Boolean(stage() && state.project.active_stage_id === state.stageId && !stage().accepted_attempt_id);
  const stageUrl = () => `${api}/projects/${state.project.id}/stages/${state.stageId}`;
  const media = assetId => `/api/assets/${encodeURIComponent(assetId)}/content`;
  const requestId = () => typeof crypto.randomUUID === "function" ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");

  function element(tag, className = "", text = undefined) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text;
    return value;
  }

  function actionButton(text, callback, className = "") {
    const value = element("button", className, text);
    value.type = "button";
    value.addEventListener("click", callback);
    return value;
  }

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : Array.isArray(detail)
        ? detail.map(item => item.msg).join(" · ") : `Erreur HTTP ${response.status}`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  const json = (url, data, method = "POST") => request(url, {
    method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data),
  });

  function clearError() {
    for (const id of ["error", "sidebar-error"]) {
      $(id).hidden = true;
      $(id).textContent = "";
    }
  }

  function fail(error, sidebar = false) {
    const target = sidebar ? $("sidebar-error") : $("error");
    target.textContent = error?.message || String(error);
    target.hidden = false;
    if ($("dialog").open) {
      let warning = $("dialog-body").querySelector(".error");
      if (!warning) {
        warning = element("p", "error");
        $("dialog-body").append(warning);
      }
      warning.textContent = error?.message || String(error);
    }
  }

  async function run(callback, {save = true, sidebar = false} = {}) {
    if (state.busy) return;
    state.busy = true;
    clearError();
    renderControls();
    try {
      if (save) await flush();
      return await callback();
    } catch (error) {
      fail(error, sidebar);
      if (error.status === 409 && state.project) {
        try { apply((await request(`${api}/projects/${state.project.id}`)).project); }
        catch (_) { /* Keep the actionable conflict as the primary error. */ }
      }
      return undefined;
    } finally {
      state.busy = false;
      renderControls();
    }
  }

  function updateProjectSummary(project) {
    const summary = state.projects.find(item => item.id === project.id);
    if (!summary) return;
    Object.assign(summary, {
      name: project.name, updated_at: project.updated_at, active_stage_id: project.active_stage_id,
      stage_count: project.stages.length, thumbnail_asset_id: project.stages.at(-1)?.source_asset_id || null,
    });
  }

  function apply(project, {selectActive = false} = {}) {
    const previousId = stage()?.id;
    state.project = project;
    if (selectActive || !project.stages.some(item => item.id === state.stageId)) state.stageId = project.active_stage_id;
    const current = stage();
    if (!current) return;
    if (!state.beforeId || !project.stages.some(item => item.source_asset_id === state.beforeId)) state.beforeId = current.source_asset_id;
    const successfulIds = new Set(current.attempts.filter(item => item.status === "succeeded")
      .flatMap(item => [`attempt:${item.id}`, item.raw_output_asset_id ? `raw:${item.id}` : []]));
    if (!successfulIds.has(state.selectedOutput)) {
      const latest = [...current.attempts].reverse().find(item => item.status === "succeeded" && item.output_asset_id);
      state.selectedOutput = latest ? `attempt:${latest.id}` : null;
    }
    if (!previousId || previousId !== current.id) state.promptDraft = null;
    updateProjectSummary(project);
    render();
    if (state.view === "guide") ensureGuideLoaded().catch(fail);
  }

  function queueChanges(changes) {
    if (!editable()) return;
    state.pending = {...state.pending, ...changes};
    $("save-state").textContent = "Modifications…";
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => flush().catch(fail), 650);
    renderControls();
  }

  async function flush() {
    clearTimeout(state.saveTimer);
    if (state.saving) await state.saving;
    if (!state.project || !editable() || !Object.keys(state.pending).length) return;
    const changes = state.pending;
    state.pending = {};
    const revision = stage().revision;
    $("save-state").textContent = "Enregistrement…";
    state.saving = json(stageUrl(), {revision, changes}, "PATCH").then(({project}) => {
      apply(project);
      $("save-state").textContent = "✓ Enregistré";
    }).catch(error => {
      state.pending = {...changes, ...state.pending};
      $("save-state").textContent = "À réessayer";
      throw error;
    }).finally(() => { state.saving = null; });
    await state.saving;
  }

  async function refreshProjects() {
    const data = await request(`${api}/projects`);
    state.projects = data.projects || [];
    renderProjectCards();
  }

  async function openProject(projectId) {
    if (state.project?.id !== projectId && !confirmGuideDiscard()) return;
    if (state.project && state.project.id !== projectId) await flush();
    const {project} = await request(`${api}/projects/${projectId}`);
    const active = project.stages.find(item => item.id === project.active_stage_id);
    const firstGesture = active?.source_asset_id && !active.attempts.length && !active.prompt;
    Object.assign(state, {
      pending: {}, promptDraft: null, selectedOutput: null, beforeId: null,
      view: firstGesture ? "guide" : "compare",
    });
    resetGuide();
    apply(project, {selectActive: true});
    try { localStorage.setItem("panelforge.qwen.last-project", project.id); } catch (_) { /* Optional. */ }
  }

  function renderProjectCards() {
    const list = $("projects");
    list.replaceChildren();
    $("projects-empty").hidden = state.projects.length > 0;
    for (const project of state.projects) {
      const item = element("li");
      const control = actionButton("", () => run(() => openProject(project.id), {sidebar: true}));
      control.classList.toggle("active", project.id === state.project?.id);
      if (project.thumbnail_asset_id) {
        const image = element("img");
        image.src = media(project.thumbnail_asset_id);
        image.alt = "";
        control.append(image);
      } else {
        control.append(element("span", "qv2-project-placeholder", "＋"));
      }
      const copy = element("span");
      copy.append(element("b", "", project.name), element("small", "",
        `${project.stage_count} étape${project.stage_count > 1 ? "s" : ""}`));
      control.append(copy);
      item.append(control);
      list.append(item);
    }
  }

  function renderModels() {
    const select = $("model");
    const current = stage()?.model_id || select.value;
    if (window.PanelForgeModelPicker) {
      window.PanelForgeModelPicker.populate(select, state.models, current);
      return;
    }
    select.replaceChildren(new Option("Choisir un modèle…", ""));
    for (const model of state.models) {
      const option = new Option(model.label, model.id);
      option.dataset.source = model.source;
      select.add(option);
    }
    select.value = current;
  }

  function setValue(id, value, pendingKey = id) {
    const control = $(id);
    if (document.activeElement !== control && !Object.hasOwn(state.pending, pendingKey)) control.value = value ?? "";
  }

  function render() {
    renderProjectCards();
    const project = state.project;
    $("empty").hidden = Boolean(project);
    $("editor").hidden = !project;
    $("attempts-section").hidden = !project;
    if (!project || !stage()) return;

    const current = stage();
    setValue("name", project.name, "name");
    setValue("label", current.label, "label");
    if (!Object.hasOwn(state.pending, "draft")) setValue("draft", current.draft, "draft");
    setValue("resolution", current.settings.resolution, "settings");
    setValue("ratio", current.settings.aspect_ratio, "settings");
    setValue("steps", current.settings.steps, "settings");
    setValue("cfg", current.settings.cfg, "settings");
    setValue("seed", current.settings.seed, "settings");
    if (!Object.hasOwn(state.pending, "settings")) {
      $("reuse-seed").checked = current.settings.reuse_seed;
      $("negative").value = current.settings.negative_prompt;
      workspace.querySelector(`input[name="qv2-color-finish"][value="${current.settings.color_finish || "natural"}"]`).checked = true;
    }
    if (state.promptDraft === null && document.activeElement !== $("prompt")) $("prompt").value = current.prompt;
    if (!Object.hasOwn(state.pending, "model_id") && current.model_id) {
      if (window.PanelForgeModelPicker) window.PanelForgeModelPicker.select($("model"), current.model_id);
      else $("model").value = current.model_id;
    }

    $("title").textContent = `${project.name} · Étape ${current.index}`;
    $("metadata").textContent = `${current.mode === "composition" ? "Composition" : "Source à modifier"} · ${current.render_dimensions.join(" × ")} px · Qwen Image 2.1`;
    $("download").href = `${api}/projects/${project.id}/download`;
    $("export-note").textContent = project.export_error ? `Export : ${project.export_error}`
      : project.export_path ? `Copie : ${project.export_path}` : "";
    $("ratio-wrap").hidden = current.mode !== "composition";
    $("negative-wrap").hidden = Number(current.settings.cfg) === 1;
    $("settings-summary").textContent = `Qwen 2.1 · ${current.settings.color_finish === "raw" ? "couleurs brutes" : "harmonisation source"}`;
    $("guide-summary").textContent = current.guide ? "Guide visuel actif" : "Guide non défini";
    $("guide-summary").classList.toggle("ready", Boolean(current.guide));
    $("guide-dot").classList.toggle("ready", Boolean(current.guide));
    const activeReferences = current.references.filter(ref => ref.active);
    $("reference-summary").textContent = `${activeReferences.length} référence${activeReferences.length > 1 ? "s" : ""}`;
    $("context-summary").firstElementChild.textContent = current.mode === "composition" ? "Composition" : "Source <image1>";
    $("prompt-status").textContent = current.prompt_ready ? "Prêt" : current.prompt ? "À actualiser" : "À préparer";
    $("prompt-mapping").textContent = current.render_inputs.map(ref => `${ref.tag} ${ref.name}`).join(" · ");
    $("prompt-details").open = Boolean(current.prompt) && !current.prompt_ready;
    $("feedback").checked = Boolean(current.feedback_attempt_id);

    renderStatus();
    renderTimeline();
    renderCompare();
    renderMessages();
    renderReferences();
    renderAttempts();
    switchView(state.view, {load: false});
    renderControls();
  }

  function renderStatus() {
    const current = stage();
    const activeAttempt = [...current.attempts].reverse().find(item => activeStatuses.has(item.status));
    const activeMessage = [...current.messages].reverse().find(item => ["queued", "running"].includes(item.status));
    $("status").textContent = activeAttempt ? statusLabels[activeAttempt.status]
      : activeMessage ? "● Préparation du prompt" : "● Prêt";
  }

  function renderTimeline() {
    const timeline = $("timeline");
    timeline.replaceChildren();
    for (const item of state.project.stages) {
      const control = actionButton("", () => {
        if (item.id !== state.stageId && !confirmGuideDiscard()) return;
        Object.assign(state, {
          stageId: item.id, selectedOutput: null, beforeId: item.source_asset_id,
          promptDraft: null, view: "compare",
        });
        resetGuide();
        render();
      });
      control.classList.toggle("active", item.id === state.stageId);
      control.classList.toggle("accepted", Boolean(item.accepted_attempt_id));
      if (item.source_asset_id) {
        const image = element("img");
        image.src = media(item.source_asset_id);
        image.alt = "";
        control.append(image);
      } else {
        control.append(element("span", "qv2-project-placeholder", "＋"));
      }
      const text = element("span");
      text.append(element("b", "", item.index === 1 ? "Base" : `Étape ${item.index}`),
        element("small", "", item.accepted_attempt_id ? "Validée"
          : item.id === state.project.active_stage_id ? "En cours" : "Historique"));
      control.append(text);
      timeline.append(control);
    }
  }

  function outputChoice() {
    const current = stage();
    if (!current || !state.selectedOutput) return null;
    const [kind, id] = state.selectedOutput.split(":", 2);
    const attempt = current.attempts.find(item => item.id === id);
    if (!attempt) return null;
    return {
      attempt, raw: kind === "raw",
      assetId: kind === "raw" ? attempt.raw_output_asset_id : attempt.output_asset_id,
    };
  }

  function attemptName(attempt, index = null) {
    const actual = index ?? stage().attempts.indexOf(attempt);
    if (attempt.kind === "crop") return `Recadrage ${actual + 1}`;
    if (attempt.kind === "dlss") return `Upscale ${actual + 1}`;
    return `Essai ${actual + 1}`;
  }

  function hasNaturalFinish(attempt) {
    return attempt?.finish?.mode === "natural" && attempt.finish.status !== "fallback";
  }

  function setImage(image, assetId) {
    image.hidden = !assetId;
    if (assetId && image.dataset.asset !== assetId) {
      image.dataset.asset = assetId;
      image.src = media(assetId);
    }
    if (!assetId) {
      image.removeAttribute("src");
      delete image.dataset.asset;
    }
  }

  function renderCompare() {
    const current = stage();
    const before = $("before");
    before.replaceChildren();
    for (const item of state.project.stages) {
      if (!item.source_asset_id) continue;
      before.add(new Option(item.index === 1 ? "Image initiale" : `Source de l’étape ${item.index}`, item.source_asset_id));
    }
    if (state.beforeId && [...before.options].some(option => option.value === state.beforeId)) before.value = state.beforeId;
    else state.beforeId = before.value || null;

    const after = $("after");
    after.replaceChildren(new Option("Aucun résultat", ""));
    current.attempts.forEach((attempt, index) => {
      if (attempt.status !== "succeeded" || !attempt.output_asset_id) return;
      const finish = hasNaturalFinish(attempt) ? "harmonisé à la source"
        : attempt.finish?.status === "fallback" ? "Qwen brut · harmonisation indisponible" : "Qwen";
      after.add(new Option(`${attemptName(attempt, index)} · ${finish}`, `attempt:${attempt.id}`));
      if (attempt.raw_output_asset_id && attempt.raw_output_asset_id !== attempt.output_asset_id) {
        after.add(new Option(`${attemptName(attempt, index)} · Qwen brut`, `raw:${attempt.id}`));
      }
    });
    if (state.selectedOutput && [...after.options].some(option => option.value === state.selectedOutput)) after.value = state.selectedOutput;
    else after.value = "";

    const choice = outputChoice();
    setImage($("before-image"), state.beforeId);
    setImage($("after-image"), choice?.assetId);
    $("compare-placeholder").hidden = Boolean(choice?.assetId);
    $("compare-note").textContent = choice?.raw
      ? "Version brute sortie de Qwen. La version à finition naturelle reste disponible dans la liste."
      : choice?.attempt?.finish_error
        ? `Rendu Qwen conservé brut : l’harmonisation locale n’a pas pu être appliquée (${choice.attempt.finish_error}).`
      : hasNaturalFinish(choice?.attempt)
        ? "Harmonisé avec la source : la dominante est rapprochée doucement, sans masquer le brut Qwen archivé."
        : "";
  }

  function setComparisonPosition(value) {
    const position = Math.max(0, Math.min(100, Number(value)));
    $("split").value = String(position);
    $("compare-view").style.setProperty("--qv2-split", `${position}%`);
    $("split").setAttribute("aria-valuetext",
      `${Math.round(position)} % avant, ${Math.round(100 - position)} % après`);
  }

  function renderMessages() {
    const current = stage();
    const list = $("messages");
    list.replaceChildren();
    $("messages-empty").hidden = current.messages.length > 0;
    $("revision-count").textContent = current.messages.length
      ? `${current.messages.length} échange${current.messages.length > 1 ? "s" : ""}` : "Aucun échange";
    for (const message of current.messages) {
      const card = element("article", "qv2-message");
      card.append(element("div", "user", message.text));
      const response = message.reply || (message.status === "queued" ? "En attente…"
        : message.status === "running" ? "L’assistant rédige le prompt…"
          : message.error || "Aucune réponse.");
      card.append(element("div", "assistant", response));
      const footer = element("footer");
      footer.append(element("span", "", message.model_id || "Assistant"));
      if (message.has_draft || message.has_reasoning || message.error) {
        footer.append(actionButton("Voir le détail", () => viewMessage(message)));
      }
      if (message.can_recover && editable()) {
        footer.append(actionButton("Récupérer le prompt", () => recoverMessage(message)));
      }
      card.append(footer);
      list.append(card);
    }
  }

  function renderReferences() {
    const list = $("references");
    list.replaceChildren();
    const references = stage().references.filter(ref => ref.active);
    if (!references.length) list.append(element("p", "muted", "Aucune référence supplémentaire."));
    for (const ref of references) {
      const card = element("article", "qv2-reference");
      const image = element("img");
      image.src = media(ref.asset_id);
      image.alt = ref.name;
      const copy = element("div");
      copy.append(element("b", "", ref.name),
        element("small", "", ref.usage === "render" ? "Assistant + Qwen" : "Assistant uniquement"),
        actionButton("Usage et rôle", () => editReference(ref)));
      card.append(image, copy);
      list.append(card);
    }
  }

  function renderAttempts() {
    const current = stage();
    const list = $("attempts");
    list.replaceChildren();
    $("attempts-empty").hidden = current.attempts.length > 0;
    $("attempt-count").textContent = `${current.attempts.length} essai${current.attempts.length > 1 ? "s" : ""}`;
    [...current.attempts].map((attempt, index) => ({attempt, index})).reverse().forEach(({attempt, index}) => {
      const card = element("article", "qv2-attempt-card");
      card.classList.toggle("selected", outputChoice()?.attempt.id === attempt.id);
      const preview = actionButton("", () => selectAttempt(attempt), "preview");
      if (attempt.output_asset_id) {
        const image = element("img");
        image.src = media(attempt.output_asset_id);
        image.alt = attemptName(attempt, index);
        preview.append(image);
      } else {
        preview.append(element("span", "qv2-attempt-placeholder",
          activeStatuses.has(attempt.status) ? "◷" : attempt.status === "failed" ? "✕" : "—"));
      }
      const copy = element("div");
      copy.append(element("b", "", `${attemptName(attempt, index)} · ${statusLabels[attempt.status] || attempt.status}`));
      const dimensions = attempt.output_dimensions || attempt.dimensions;
      copy.append(element("small", "", [
        dimensions?.join(" × "), attempt.settings?.steps ? `${attempt.settings.steps} steps` : null,
        attempt.settings?.seed ? `seed ${attempt.settings.seed}` : null,
        hasNaturalFinish(attempt) ? "harmonisé source"
          : attempt.finish?.status === "fallback" ? "brut · finition indisponible" : null,
      ].filter(Boolean).join(" · ")));
      const actions = element("div", "qv2-attempt-actions");
      if (attempt.output_asset_id) actions.append(actionButton("Comparer", () => selectAttempt(attempt)));
      if (attempt.raw_output_asset_id && attempt.raw_output_asset_id !== attempt.output_asset_id) {
        actions.append(actionButton("Voir le brut", () => selectAttempt(attempt, true)));
      }
      if (editable() && attempt.context) {
        actions.append(actionButton("Reprendre réglages", () => restoreAttempt(attempt)));
      }
      if (editable() && attempt.status === "succeeded" && attempt.output_asset_id) {
        actions.append(actionButton(current.feedback_attempt_id === attempt.id
          ? "Retirer du feedback" : "Montrer à l’assistant", () => useAsFeedback(attempt)));
        if (attempt.kind !== "crop") actions.append(actionButton("Upscale DLSS", () => openDlss(attempt)));
        actions.append(actionButton("Valider et continuer", () => acceptAttempt(attempt), "primary"));
      }
      if (activeStatuses.has(attempt.status)) actions.append(actionButton("Annuler", () => cancelAttempt(attempt)));
      if (attempt.error) {
        actions.append(actionButton("Voir l’erreur", () => openDialog("Erreur du rendu",
          body => body.append(element("p", "error", attempt.error)))));
      }
      if (attempt.output_asset_id && window.PanelForgeDlss) {
        copy.append(window.PanelForgeDlss.inlineStatus({
          owner: "qwen", ownerId: state.project.id,
          attempt: {attempt_id: attempt.id, dlss: attempt.dlss || null},
        }));
      }
      copy.append(actions);
      card.append(preview, copy);
      list.append(card);
    });
  }

  function renderControls() {
    const current = stage();
    if (!current) return;
    const canEdit = editable() && !state.busy;
    const activeAttempt = current.attempts.find(item => activeStatuses.has(item.status));
    const activeMessage = current.messages.find(item => ["queued", "running"].includes(item.status));
    const choice = outputChoice();
    const locked = Boolean(activeAttempt || activeMessage);

    $("restart").disabled = !canEdit || locked
      || (!current.messages.length && !current.attempts.length && !current.references.some(ref => ref.active)
        && !current.guide && !current.prompt);
    $("restart").hidden = !editable();
    $("resume").hidden = editable();
    $("resume").disabled = state.busy;
    $("name").disabled = !canEdit;
    $("label").disabled = !canEdit;
    $("draft").disabled = !canEdit || Boolean(activeMessage);
    $("model").disabled = !canEdit || Boolean(activeMessage);
    window.PanelForgeModelPicker?.setDisabled($("model"), !canEdit || Boolean(activeMessage));
    $("send").disabled = !canEdit || guide.commands.length > 0
      || !$("draft").value.trim() || !$("model").value
      || Boolean(activeMessage) || state.promptDraft !== null;
    $("prompt").disabled = !canEdit;
    $("save-prompt").disabled = !canEdit || !$("prompt").value.trim() || state.promptDraft === null;
    $("render").textContent = guide.commands.length
      ? "Enregistre le guide avant le rendu" : "Lancer un rendu Qwen";
    $("render").disabled = !canEdit || locked || guide.commands.length > 0 || !current.prompt_ready
      || Boolean(current.draft.trim()) || state.promptDraft !== null;
    $("cancel").disabled = !activeAttempt || state.busy;
    $("cancel").hidden = !activeAttempt;
    $("accept").textContent = choice?.raw ? "Brut archivé" : "Valider et continuer";
    $("accept").title = choice?.raw
      ? "Le brut sert à comparer. Sélectionne la finition naturelle pour la valider."
      : "";
    $("accept").disabled = !canEdit || locked || guide.commands.length > 0
      || choice?.raw || choice?.attempt.status !== "succeeded";
    $("crop").disabled = !canEdit || locked || guide.commands.length > 0 || !current.source_asset_id;
    $("dlss").disabled = !canEdit || choice?.raw
      || choice?.attempt.status !== "succeeded" || choice?.attempt.kind === "crop";
    $("zoom-before").disabled = !state.beforeId;
    $("zoom-after").disabled = !choice?.assetId;
    $("feedback-wrap").hidden = !choice?.attempt || choice.raw || choice.attempt.status !== "succeeded";
    $("feedback").disabled = !canEdit;
    $("show-guide").disabled = !current.source_asset_id;
    $("guide-save").disabled = !canEdit || locked || !guide.commands.length || !guide.source;
    $("guide-remove").disabled = !canEdit || locked || !current.guide;
    $("guide-undo").disabled = !canEdit || !guide.commands.length;
    $("guide-clear").disabled = !canEdit || !guide.source;
    for (const id of ["tool-paint", "tool-box", "tool-erase", "brush-size"]) {
      $(id).disabled = !canEdit || locked || !guide.source;
    }
    for (const id of ["resolution", "ratio", "steps", "cfg", "seed", "reuse-seed", "negative",
      "new-seed", "add-render", "add-assistant", "reuse"]) {
      $(id).disabled = !canEdit || locked;
    }
    workspace.querySelectorAll('input[name="qv2-color-finish"]').forEach(control => {
      control.disabled = !canEdit || locked;
    });
    $("upload").disabled = state.busy;
    $("new-composition").disabled = state.busy;
    $("refresh").disabled = state.busy;
    $("export").disabled = state.busy;
  }

  function selectAttempt(attempt, raw = false) {
    if (!attempt.output_asset_id) return;
    state.selectedOutput = `${raw ? "raw" : "attempt"}:${attempt.id}`;
    state.view = "compare";
    renderCompare();
    renderAttempts();
    switchView("compare", {load: false});
    renderControls();
  }

  function openDialog(title, fill, {zoom = false} = {}) {
    $("dialog-title").textContent = title;
    $("dialog-body").replaceChildren();
    $("dialog").classList.toggle("qv2-zoom", zoom);
    fill($("dialog-body"));
    if (!$("dialog").open) $("dialog").showModal();
  }

  function zoomAsset(assetId, title) {
    if (!assetId) return;
    openDialog(title, body => {
      const image = element("img");
      image.src = media(assetId);
      image.alt = title;
      body.append(image);
    }, {zoom: true});
  }

  function viewMessage(message) {
    run(async () => {
      const {message: full} = await request(`${stageUrl()}/messages/${message.id}`);
      openDialog("Réponse complète de l’assistant", body => {
        body.append(element("p", "muted",
          `${full.model_id} · ${full.context?.render_inputs?.length || 0} image(s) envoyée(s) à Qwen`));
        body.append(element("h3", "", "Réponse reçue"), element("pre", "", full.raw || "Aucun texte reçu."));
        if (full.reasoning) {
          const details = element("details");
          details.append(element("summary", "", "Raisonnement reçu"), element("pre", "", full.reasoning));
          body.append(details);
        }
        if (full.error) body.append(element("p", "error", full.error));
      });
    }, {save: false});
  }

  function recoverMessage(message) {
    run(async () => {
      const {project} = await json(`${stageUrl()}/messages/${message.id}/recover`,
        {revision: stage().revision});
      state.promptDraft = null;
      apply(project);
    });
  }

  function editReference(ref) {
    openDialog(ref.name, body => {
      const image = element("img");
      image.src = media(ref.asset_id);
      image.alt = ref.name;
      image.style.maxHeight = "220px";
      const nameLabel = element("label", "", "Nom dans le prompt");
      const name = element("input");
      name.value = ref.name;
      name.maxLength = 80;
      nameLabel.append(name);
      const roleLabel = element("label", "", "Ce qu’il faut reprendre");
      const role = element("input");
      role.value = ref.role;
      role.maxLength = 300;
      role.placeholder = "Ex. identité, veste, palette, matériau…";
      roleLabel.append(role);
      const usageLabel = element("label", "", "Utilisation");
      const usage = element("select");
      usage.append(new Option("Assistant uniquement", "assistant"), new Option("Assistant + Qwen", "render"));
      usage.value = ref.usage;
      usageLabel.append(usage);
      const actions = element("div", "qv2-dialog-actions");
      actions.append(
        actionButton(`Citer @${ref.name}`, () => {
          $("draft").value += `${$("draft").value ? " " : ""}@${ref.name} `;
          queueChanges({draft: $("draft").value});
          $("dialog").close();
          $("draft").focus();
        }),
        actionButton("Retirer", () => run(async () => {
          await saveReference(ref.id, {active: false});
          $("dialog").close();
        })),
        actionButton("Enregistrer", () => run(async () => {
          await saveReference(ref.id, {name: name.value.trim(), role: role.value, usage: usage.value});
          $("dialog").close();
        }), "primary"),
      );
      for (const control of [name, role, usage]) control.disabled = !editable();
      body.append(image, nameLabel, roleLabel, usageLabel,
        element("p", "muted",
          "L’assistant peut comprendre @nom. Une référence Qwen est aussi injectée dans le workflow de génération."),
        actions);
    });
  }

  async function saveReference(id, changes) {
    const references = stage().references.map(ref => ref.id === id ? {...ref, ...changes} : ref);
    const {project} = await json(stageUrl(), {revision: stage().revision, changes: {references}}, "PATCH");
    apply(project);
  }

  function reuseDialog() {
    const candidates = state.project.stages.flatMap(item =>
      item.references.filter(ref => item.id !== state.stageId || !ref.active));
    openDialog("Réutiliser une image du projet", body => {
      if (!candidates.length) {
        body.append(element("p", "muted", "Aucune image retirée ou issue d’une étape précédente."));
      }
      const seen = new Set();
      for (const ref of candidates) {
        if (seen.has(ref.asset_id)) continue;
        seen.add(ref.asset_id);
        const row = element("div", "qv2-reference-choice");
        const image = element("img");
        image.src = media(ref.asset_id);
        image.alt = ref.name;
        row.append(image, element("b", "", ref.name));
        for (const [usage, label] of [["assistant", "Assistant"], ["render", "Assistant + Qwen"]]) {
          row.append(actionButton(label, () => run(async () => {
            const existing = stage().references.find(item => item.id === ref.id);
            if (existing) await saveReference(ref.id, {usage, active: true});
            else {
              apply((await json(`${stageUrl()}/reuse`,
                {reference_id: ref.id, usage, revision: stage().revision})).project);
            }
            $("dialog").close();
          })));
        }
        body.append(row);
      }
    });
  }

  async function uploadAttachments(files, usage) {
    if (!editable()) return;
    await run(async () => {
      for (const file of files) {
        if (!imageTypes.has(file.type)) throw new Error("Utilise une image PNG, JPEG ou WebP.");
        if (file.size > 25 * 1024 * 1024) throw new Error("Une image ne doit pas dépasser 25 Mo.");
        const form = new FormData();
        form.append("image", file);
        form.append("usage", usage);
        form.append("revision", String(stage().revision));
        form.append("name", file.name.replace(/\.[^.]+$/, "").slice(0, 70) || "Référence");
        apply((await request(`${stageUrl()}/references`, {method: "POST", body: form})).project);
      }
    });
  }

  function attach(usage) {
    state.attachmentUsage = usage;
    $("attachment-files").value = "";
    $("attachment-files").click();
  }

  async function createProject(file, composition = false) {
    if (!confirmGuideDiscard()) return;
    if (file) {
      if (!imageTypes.has(file.type)) throw new Error("Utilise une image PNG, JPEG ou WebP.");
      if (file.size > 25 * 1024 * 1024) throw new Error("L’image ne doit pas dépasser 25 Mo.");
    }
    const form = new FormData();
    form.append("name", file ? file.name.replace(/\.[^.]+$/, "").slice(0, 120) : "Nouvelle composition");
    form.append("composition", String(composition));
    if (file) form.append("source_image", file);
    const {project} = await request(`${api}/projects`, {method: "POST", body: form});
    Object.assign(state, {
      pending: {}, promptDraft: null, selectedOutput: null,
      view: file ? "guide" : "compare",
    });
    resetGuide();
    apply(project, {selectActive: true});
    await refreshProjects();
    if (!stage().model_id && $("model").value) queueChanges({model_id: $("model").value});
    try { localStorage.setItem("panelforge.qwen.last-project", project.id); } catch (_) { /* Optional. */ }
  }

  function readSettings() {
    return {
      resolution: $("resolution").value,
      aspect_ratio: $("ratio").value,
      steps: Number($("steps").value),
      cfg: Number($("cfg").value),
      seed: $("seed").value.trim(),
      reuse_seed: $("reuse-seed").checked,
      negative_prompt: $("negative").value,
      color_finish: workspace.querySelector('input[name="qv2-color-finish"]:checked')?.value || "natural",
    };
  }

  async function cropSource() {
    if (!confirmGuideDiscard()) return;
    const current = stage();
    if (!current?.source_asset_id || !window.PanelForgeImageCrop) {
      throw new Error("Le recadrage n’est pas disponible.");
    }
    await window.PanelForgeImageCrop.open({
      url: media(current.source_asset_id),
      save: async rect => {
        const {project} = await json(`${stageUrl()}/crop`, {
          revision: stage().revision, request_id: requestId(),
          source_asset_id: current.source_asset_id, ...rect,
        });
        Object.assign(state, {pending: {}, selectedOutput: null});
        state.view = "guide";
        resetGuide();
        apply(project, {selectActive: true});
        await refreshProjects();
        return project;
      },
    });
  }

  function openDlss(attempt) {
    if (!window.PanelForgeDlss) return fail(new Error("L’outil DLSS n’est pas chargé."));
    window.PanelForgeDlss.open({
      owner: "qwen",
      ownerId: state.project.id,
      attempt: {
        attempt_id: attempt.id, output_url: media(attempt.output_asset_id),
        label: attemptName(attempt), dlss: attempt.dlss || null,
      },
    });
  }

  function useAsFeedback(attempt) {
    const value = stage().feedback_attempt_id === attempt.id ? null : attempt.id;
    stage().feedback_attempt_id = value;
    queueChanges({feedback_attempt_id: value});
    state.selectedOutput = `attempt:${attempt.id}`;
    renderCompare();
    renderAttempts();
    renderControls();
  }

  function restoreAttempt(attempt) {
    if (!confirmGuideDiscard()) return;
    run(async () => {
      const {project} = await json(`${stageUrl()}/attempts/${attempt.id}/restore`,
        {revision: stage().revision});
      state.promptDraft = null;
      resetGuide();
      apply(project);
    });
  }

  function acceptAttempt(attempt) {
    if (!confirmGuideDiscard()) return;
    run(async () => {
      const {project} = await json(`${stageUrl()}/attempts/${attempt.id}/accept`,
        {revision: stage().revision});
      Object.assign(state, {pending: {}, promptDraft: null, selectedOutput: null, beforeId: null});
      state.view = "guide";
      resetGuide();
      apply(project, {selectActive: true});
      await refreshProjects();
    });
  }

  function cancelAttempt(attempt) {
    run(async () => apply((await json(`${stageUrl()}/attempts/${attempt.id}/cancel`, {})).project),
      {save: false});
  }

  function switchView(view, {load = true} = {}) {
    state.view = view;
    const isGuide = view === "guide";
    $("compare-panel").hidden = isGuide;
    $("guide-panel").hidden = !isGuide;
    $("show-compare").setAttribute("aria-selected", String(!isGuide));
    $("show-guide").setAttribute("aria-selected", String(isGuide));
    if (isGuide && load) ensureGuideLoaded().catch(fail);
  }

  function confirmGuideDiscard() {
    return !guide.commands.length
      || confirm("Le guide peint n’est pas encore enregistré. L’abandonner ?");
  }

  function resetGuide() {
    guide.key = null;
    guide.loading = null;
    guide.source = null;
    guide.commands = [];
    guide.active = null;
    for (const canvas of [guide.base, guide.mask, guide.overlay, $("guide-canvas")]) {
      canvas.width = 1;
      canvas.height = 1;
      canvas.getContext("2d").clearRect(0, 0, 1, 1);
    }
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Impossible de charger l’image du guide."));
      image.src = url;
    });
  }

  async function ensureGuideLoaded() {
    const current = stage();
    if (!current?.source_asset_id) return;
    const key = `${current.id}:${current.source_asset_id}:${current.guide?.mask_asset_id || "empty"}`;
    if (guide.key === key && guide.source) {
      renderGuideCanvas();
      return;
    }
    if (guide.loading?.key === key) return guide.loading.promise;
    const promise = (async () => {
      $("guide-state").textContent = "Chargement…";
      const source = await loadImage(media(current.source_asset_id));
      const latestKey = `${stage()?.id}:${stage()?.source_asset_id}:${stage()?.guide?.mask_asset_id || "empty"}`;
      if (latestKey !== key) return;
      const width = source.naturalWidth;
      const height = source.naturalHeight;
      for (const canvas of [guide.base, guide.mask, guide.overlay, $("guide-canvas")]) {
        canvas.width = width;
        canvas.height = height;
      }
      guide.base.getContext("2d").clearRect(0, 0, width, height);
      guide.mask.getContext("2d").clearRect(0, 0, width, height);
      if (current.guide?.mask_asset_id) {
        const saved = await loadImage(media(current.guide.mask_asset_id));
        const scratch = document.createElement("canvas");
        scratch.width = width;
        scratch.height = height;
        const scratchContext = scratch.getContext("2d", {willReadFrequently: true});
        scratchContext.drawImage(saved, 0, 0, width, height);
        const pixels = scratchContext.getImageData(0, 0, width, height);
        for (let index = 0; index < pixels.data.length; index += 4) {
          const coverage = Math.max(pixels.data[index], pixels.data[index + 1], pixels.data[index + 2]);
          pixels.data[index] = 255;
          pixels.data[index + 1] = 255;
          pixels.data[index + 2] = 255;
          pixels.data[index + 3] = coverage;
        }
        guide.base.getContext("2d").putImageData(pixels, 0, 0);
        guide.mask.getContext("2d").putImageData(pixels, 0, 0);
      }
      guide.source = source;
      guide.commands = [];
      guide.active = null;
      guide.key = key;
      renderGuideCanvas();
      renderControls();
    })();
    guide.loading = {key, promise};
    try { await promise; }
    finally { if (guide.loading?.key === key) guide.loading = null; }
  }

  function drawCommand(context, command) {
    if (command.tool === "clear") {
      context.clearRect(0, 0, guide.mask.width, guide.mask.height);
      return;
    }
    context.save();
    context.globalCompositeOperation = command.tool === "erase" ? "destination-out" : "source-over";
    context.fillStyle = "#fff";
    context.strokeStyle = "#fff";
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = command.size;
    if (command.tool === "box") {
      const left = Math.min(command.start.x, command.end.x);
      const top = Math.min(command.start.y, command.end.y);
      context.fillRect(left, top, Math.abs(command.end.x - command.start.x),
        Math.abs(command.end.y - command.start.y));
    } else if (command.points.length === 1) {
      context.beginPath();
      context.arc(command.points[0].x, command.points[0].y, command.size / 2, 0, Math.PI * 2);
      context.fill();
    } else {
      context.beginPath();
      context.moveTo(command.points[0].x, command.points[0].y);
      command.points.slice(1).forEach(point => context.lineTo(point.x, point.y));
      context.stroke();
    }
    context.restore();
  }

  function rebuildMask() {
    const context = guide.mask.getContext("2d");
    context.clearRect(0, 0, guide.mask.width, guide.mask.height);
    context.drawImage(guide.base, 0, 0);
    guide.commands.forEach(command => drawCommand(context, command));
  }

  function scheduleGuideRender() {
    if (guide.frame) return;
    guide.frame = requestAnimationFrame(() => {
      guide.frame = null;
      renderGuideCanvas();
    });
  }

  function renderGuideCanvas() {
    const canvas = $("guide-canvas");
    if (!guide.source || canvas.width < 2) return;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(guide.source, 0, 0, canvas.width, canvas.height);
    const overlay = guide.overlay.getContext("2d");
    overlay.clearRect(0, 0, guide.overlay.width, guide.overlay.height);
    overlay.drawImage(guide.mask, 0, 0);
    overlay.globalCompositeOperation = "source-in";
    overlay.fillStyle = "#ef3f4d";
    overlay.fillRect(0, 0, guide.overlay.width, guide.overlay.height);
    overlay.globalCompositeOperation = "source-over";
    context.save();
    context.globalAlpha = 0.58;
    context.drawImage(guide.overlay, 0, 0);
    if (guide.active?.tool === "box") {
      const {start, end} = guide.active;
      context.fillStyle = "#ef3f4d";
      context.fillRect(Math.min(start.x, end.x), Math.min(start.y, end.y),
        Math.abs(end.x - start.x), Math.abs(end.y - start.y));
    }
    context.restore();
    const dirty = guide.commands.length > 0;
    $("guide-state").textContent = dirty ? "Guide à enregistrer" : stage()?.guide ? "Guide actif" : "Aucun guide";
    $("guide-state").classList.toggle("ready", dirty || Boolean(stage()?.guide));
  }

  function guidePoint(event) {
    const canvas = $("guide-canvas");
    const box = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(canvas.width, (event.clientX - box.left) * canvas.width / box.width)),
      y: Math.max(0, Math.min(canvas.height, (event.clientY - box.top) * canvas.height / box.height)),
    };
  }

  function beginGuideStroke(event) {
    if (!editable() || !guide.source || event.button !== 0) return;
    event.preventDefault();
    try { $("guide-canvas").setPointerCapture(event.pointerId); }
    catch (_) { /* Synthetic events and older browsers may not expose pointer capture. */ }
    const point = guidePoint(event);
    const size = Number($("brush-size").value);
    guide.active = guide.tool === "box"
      ? {tool: "box", size, start: point, end: point}
      : {tool: guide.tool, size, points: [point]};
    if (guide.tool !== "box") {
      drawCommand(guide.mask.getContext("2d"), guide.active);
      scheduleGuideRender();
    }
  }

  function moveGuideStroke(event) {
    if (!guide.active) return;
    event.preventDefault();
    const point = guidePoint(event);
    if (guide.active.tool === "box") {
      guide.active.end = point;
    } else {
      const previous = guide.active.points.at(-1);
      guide.active.points.push(point);
      drawCommand(guide.mask.getContext("2d"), {...guide.active, points: [previous, point]});
    }
    scheduleGuideRender();
  }

  function endGuideStroke(event) {
    if (!guide.active) return;
    event.preventDefault();
    const command = guide.active;
    guide.active = null;
    if (command.tool === "box") {
      command.end = guidePoint(event);
      if (Math.abs(command.end.x - command.start.x) > 2
          && Math.abs(command.end.y - command.start.y) > 2) {
        drawCommand(guide.mask.getContext("2d"), command);
        guide.commands.push(command);
      }
    } else {
      guide.commands.push(command);
    }
    renderGuideCanvas();
    renderControls();
  }

  function setGuideTool(tool) {
    guide.tool = tool;
    for (const value of ["paint", "box", "erase"]) {
      $("tool-" + value).setAttribute("aria-pressed", String(value === tool));
    }
  }

  function undoGuide() {
    if (!guide.commands.length) return;
    guide.commands.pop();
    rebuildMask();
    renderGuideCanvas();
    renderControls();
  }

  function clearGuideCanvas() {
    if (!guide.source) return;
    guide.commands.push({tool: "clear"});
    rebuildMask();
    renderGuideCanvas();
    renderControls();
  }

  function maskBlob() {
    return new Promise((resolve, reject) => guide.mask.toBlob(blob =>
      blob ? resolve(blob) : reject(new Error("Impossible d’enregistrer le guide.")), "image/png"));
  }

  async function saveGuide() {
    const current = stage();
    if (!current?.source_asset_id || !guide.source || !guide.commands.length) return;
    const form = new FormData();
    form.append("mask", await maskBlob(), "zone.png");
    form.append("revision", String(current.revision));
    form.append("request_id", requestId());
    form.append("source_asset_id", current.source_asset_id);
    form.append("source_width", String(guide.source.naturalWidth));
    form.append("source_height", String(guide.source.naturalHeight));
    const {project} = await request(`${stageUrl()}/guide`, {method: "POST", body: form});
    state.promptDraft = null;
    resetGuide();
    apply(project);
    await ensureGuideLoaded();
  }

  async function removeGuide() {
    const {project} = await json(`${stageUrl()}/guide/clear`,
      {revision: stage().revision, request_id: requestId()});
    state.promptDraft = null;
    resetGuide();
    apply(project);
    await ensureGuideLoaded();
  }

  async function restartStage() {
    if (!confirm("Recommencer cette étape ? Le guide, la conversation, les références et les essais de cette étape seront retirés.")) return;
    const {project} = await json(`${stageUrl()}/restart`,
      {revision: stage().revision, request_id: requestId()});
    Object.assign(state, {pending: {}, promptDraft: null, selectedOutput: null});
    state.view = stage().source_asset_id ? "guide" : "compare";
    resetGuide();
    apply(project);
  }

  async function init() {
    if (state.initialized) return state.initialized;
    state.initialized = (async () => {
      const [projects, models] = await Promise.all([
        request(`${api}/projects`), request(`${api}/models`),
      ]);
      state.projects = projects.projects || [];
      state.models = models.models || [];
      renderProjectCards();
      renderModels();
      let preferred = null;
      try { preferred = localStorage.getItem("panelforge.qwen.last-project"); } catch (_) { /* Optional. */ }
      const first = state.projects.find(item => item.id === preferred) || state.projects[0];
      if (first) await openProject(first.id);
      if (!state.pollTimer) state.pollTimer = setInterval(poll, 2200);
    })().catch(error => {
      state.initialized = null;
      throw error;
    });
    return state.initialized;
  }

  async function poll() {
    if (!state.project || state.busy || state.saving || document.hidden) return;
    const current = stage();
    if (!current) return;
    const processing = current.attempts.some(item => activeStatuses.has(item.status))
      || current.messages.some(item => ["queued", "running"].includes(item.status));
    if (!processing) return;
    try {
      const {project} = await request(`${api}/projects/${state.project.id}`);
      apply(project);
      if (!stage().attempts.some(item => activeStatuses.has(item.status))
          && !stage().messages.some(item => ["queued", "running"].includes(item.status))) {
        await refreshProjects();
      }
    } catch (error) {
      fail(error);
    }
  }

  $("upload-form").addEventListener("submit", event => {
    event.preventDefault();
    const file = $("source-file").files[0];
    if (file) run(() => createProject(file), {sidebar: true});
  });
  $("source-file").addEventListener("change", () => {
    if (!$("source-file").files[0]) $("upload-form").reset();
  });
  $("empty-import").addEventListener("click", () => $("source-file").click());
  $("new-composition").addEventListener("click", () =>
    run(() => createProject(null, true), {sidebar: true}));
  $("refresh").addEventListener("click", () => run(async () => {
    await refreshProjects();
    const models = await request(`${api}/models`);
    state.models = models.models || [];
    renderModels();
    if (state.project) apply((await request(`${api}/projects/${state.project.id}`)).project);
  }, {sidebar: true}));

  $("name").addEventListener("input", () => queueChanges({name: $("name").value}));
  $("label").addEventListener("input", () => queueChanges({label: $("label").value}));
  $("draft").addEventListener("input", () => queueChanges({draft: $("draft").value}));
  $("draft").addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      $("send").click();
    }
  });
  $("model").addEventListener("change", () => queueChanges({model_id: $("model").value}));
  for (const id of ["resolution", "ratio", "steps", "cfg", "seed", "reuse-seed", "negative"]) {
    $(id).addEventListener("change", () => {
      queueChanges({settings: readSettings()});
      $("negative-wrap").hidden = Number($("cfg").value) === 1;
    });
  }
  workspace.querySelectorAll('input[name="qv2-color-finish"]').forEach(control =>
    control.addEventListener("change", () => {
      queueChanges({settings: readSettings()});
      $("settings-summary").textContent = `Qwen 2.1 · ${control.value === "raw" ? "couleurs brutes" : "harmonisation source"}`;
    }));
  $("new-seed").addEventListener("click", () => {
    const seed = new Uint32Array(2);
    crypto.getRandomValues(seed);
    $("seed").value = ((BigInt(seed[0]) << 32n) | BigInt(seed[1])).toString();
    queueChanges({settings: readSettings()});
  });
  $("prompt").addEventListener("input", () => {
    state.promptDraft = $("prompt").value;
    renderControls();
  });
  $("save-prompt").addEventListener("click", () => run(async () => {
    const {project} = await json(stageUrl(),
      {revision: stage().revision, changes: {prompt: $("prompt").value}}, "PATCH");
    state.promptDraft = null;
    apply(project);
  }));
  $("send").addEventListener("click", () => run(async () => {
    if (state.promptDraft !== null) {
      throw new Error("Enregistre d’abord le prompt Qwen que tu as modifié.");
    }
    if (!stage().model_id && $("model").value) {
      queueChanges({model_id: $("model").value});
      await flush();
    }
    const {project} = await json(`${stageUrl()}/messages`,
      {revision: stage().revision, request_id: requestId()});
    apply(project);
  }));
  $("render").addEventListener("click", () => run(async () => {
    apply((await json(`${stageUrl()}/attempts`,
      {revision: stage().revision, request_id: requestId()})).project);
  }));
  $("cancel").addEventListener("click", () => {
    const attempt = stage().attempts.find(item => activeStatuses.has(item.status));
    if (attempt) cancelAttempt(attempt);
  });

  $("before").addEventListener("change", () => {
    state.beforeId = $("before").value;
    renderCompare();
    renderControls();
  });
  $("after").addEventListener("change", () => {
    state.selectedOutput = $("after").value || null;
    renderCompare();
    renderAttempts();
    renderControls();
  });
  $("split").addEventListener("input", () => setComparisonPosition($("split").value));
  const moveComparison = event => {
    const bounds = $("compare-view").getBoundingClientRect();
    if (bounds.width) setComparisonPosition(100 * (event.clientX - bounds.left) / bounds.width);
  };
  let comparisonPointer = null;
  $("compare-view").addEventListener("pointerdown", event => {
    if (event.button !== 0 || comparisonPointer !== null) return;
    event.preventDefault();
    comparisonPointer = event.pointerId;
    try { $("compare-view").setPointerCapture(event.pointerId); }
    catch (_) { /* Synthetic events and older browsers may not expose pointer capture. */ }
    moveComparison(event);
  });
  $("compare-view").addEventListener("pointermove", event => {
    if (comparisonPointer === event.pointerId
        || ($("follow-pointer").checked && event.pointerType === "mouse")) moveComparison(event);
  });
  const releaseComparison = event => {
    if (comparisonPointer !== event.pointerId) return;
    comparisonPointer = null;
    try {
      if ($("compare-view").hasPointerCapture(event.pointerId)) {
        $("compare-view").releasePointerCapture(event.pointerId);
      }
    } catch (_) { /* The local pointer state also supports capture-less browsers. */ }
  };
  $("compare-view").addEventListener("pointerup", releaseComparison);
  $("compare-view").addEventListener("pointercancel", releaseComparison);
  $("compare-view").addEventListener("lostpointercapture", event => {
    if (comparisonPointer === event.pointerId) comparisonPointer = null;
  });
  $("zoom-before").addEventListener("click", () => zoomAsset(state.beforeId, "Image avant"));
  $("zoom-after").addEventListener("click", () =>
    zoomAsset(outputChoice()?.assetId, outputChoice()?.raw ? "Qwen brut" : "Résultat"));
  $("crop").addEventListener("click", () => run(cropSource));
  $("dlss").addEventListener("click", () => {
    const choice = outputChoice();
    if (choice) openDlss(choice.attempt);
  });
  $("accept").addEventListener("click", () => {
    const choice = outputChoice();
    if (choice) acceptAttempt(choice.attempt);
  });
  $("feedback").addEventListener("change", () => {
    const choice = outputChoice();
    if (choice) useAsFeedback(choice.attempt);
  });

  $("show-compare").addEventListener("click", () => switchView("compare"));
  $("show-guide").addEventListener("click", () => switchView("guide"));
  $("tool-paint").addEventListener("click", () => setGuideTool("paint"));
  $("tool-box").addEventListener("click", () => setGuideTool("box"));
  $("tool-erase").addEventListener("click", () => setGuideTool("erase"));
  $("brush-size").addEventListener("input", () => {
    $("brush-value").textContent = `${$("brush-size").value} px`;
  });
  $("guide-canvas").addEventListener("pointerdown", beginGuideStroke);
  $("guide-canvas").addEventListener("pointermove", moveGuideStroke);
  $("guide-canvas").addEventListener("pointerup", endGuideStroke);
  $("guide-canvas").addEventListener("pointercancel", () => {
    guide.active = null;
    rebuildMask();
    renderGuideCanvas();
  });
  $("guide-undo").addEventListener("click", undoGuide);
  $("guide-clear").addEventListener("click", clearGuideCanvas);
  $("guide-save").addEventListener("click", () => run(saveGuide));
  $("guide-remove").addEventListener("click", () => run(removeGuide));

  $("add-render").addEventListener("click", () => attach("render"));
  $("add-assistant").addEventListener("click", () => attach("assistant"));
  $("attachment-files").addEventListener("change", () =>
    uploadAttachments([...$("attachment-files").files], state.attachmentUsage));
  $("reuse").addEventListener("click", reuseDialog);
  $("restart").addEventListener("click", () => run(restartStage));
  $("resume").addEventListener("click", () => run(async () => {
    const {project} = await json(`${stageUrl()}/resume`, {request_id: requestId()});
    Object.assign(state, {pending: {}, promptDraft: null, selectedOutput: null});
    resetGuide();
    apply(project, {selectActive: true});
    await refreshProjects();
  }));
  $("export").addEventListener("click", () => run(async () =>
    apply((await json(`${api}/projects/${state.project.id}/export`, {})).project)));
  $("download").addEventListener("click", event => {
    event.preventDefault();
    if (state.project) window.location.assign(`${api}/projects/${state.project.id}/download`);
  });
  $("dialog-close").addEventListener("click", () => $("dialog").close());
  $("dialog").addEventListener("click", event => {
    if (event.target !== $("dialog")) return;
    const box = $("dialog").getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right
        || event.clientY < box.top || event.clientY > box.bottom) {
      $("dialog").close();
    }
  });

  window.addEventListener("panelforge:dlss-complete", async event => {
    const job = event.detail;
    if (job?.snapshot?.owner !== "qwen" || job.snapshot.owner_id !== state.project?.id) return;
    try {
      if (job.candidate_id) state.selectedOutput = `attempt:${job.candidate_id}`;
      apply((await request(`${api}/projects/${state.project.id}`)).project);
      await refreshProjects();
    } catch (error) {
      fail(error);
    }
  });
  window.addEventListener("beforeunload", event => {
    if (Object.keys(state.pending).length) flush().catch(() => {});
    if (guide.commands.length) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  window.PanelForgeQwenEdit = {
    open: async projectId => {
      await init();
      if (projectId) await openProject(projectId);
      window.PanelForgeLabNavigation.switchView("qwen-edit-lab");
    },
  };
  document.querySelectorAll('[data-image-lab-mode="qwen-edit-lab"]').forEach(control =>
    control.addEventListener("click", () => {
      window.PanelForgeLabNavigation.switchView("qwen-edit-lab");
      init().catch(error => fail(error, true));
    }));
  document.querySelectorAll("[data-image-lab-mode],[data-lab-view]").forEach(control =>
    control.addEventListener("click", () => {
      if (state.project) flush().catch(fail);
    }));
  if (!workspace.hidden) init().catch(error => fail(error, true));
})();
