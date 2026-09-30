(() => {
  "use strict";
  const root = document.getElementById("image-journey-workspace");
  const core = window.PanelForgeLabCore;
  if (!root || !core) return;
  const $ = id => document.getElementById("ij-" + id);
  const asset = id => "/api/assets/" + encodeURIComponent(id) + "/content";
  const apiRoot = "/api/image-lab/journeys";
  const storageKey = "panelforge.image-journey.project";
  const phases = {planning:"Préparation du parcours",ready:"Prochaine transformation",prompting:"Préparation du prompt",
    queueing:"Mise en file",rendering:"Génération",protecting:"Masque automatique et préservation du décor",reviewing:"Relecture",completed:"Terminé"};
  const states = {running:"En cours",pausing:"Suspension…",paused:"Suspendu",completed:"Terminé"};
  const state = {p:null, spec:null, projects:[], models:[], busy:false, polling:false, loading:null,
    epoch:0, createCommand:null, resumeCommand:null, previewUrl:null, formDirty:false, galleryKey:""};
  const api = (path, method="GET", body) => core.request(apiRoot + path,
    {method, ...(body === undefined ? {} : {headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  const endpoint = suffix => "/projects/" + encodeURIComponent(state.p.id) + suffix;
  const commandId = () => {
    const bytes = new Uint32Array(4);
    crypto.getRandomValues(bytes);
    return [...bytes].map(value => value.toString(16).padStart(8,"0")).join("");
  };
  const actions = window.PanelForgeJourneyActions.attach({
    project:() => state.p, spec:() => state.spec, frames, asset, api, commandId, accept, showImage, hidePreview,
    busy:() => state.busy
  });
  function message(value) {
    $("message").textContent = value || "";
    $("message").hidden = !value;
  }
  function revokePreview() {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
  }
  function fillModels(select, selected) {
    const options = state.models.map(model => new Option(
      (model.source === "local" || model.id.startsWith("local::") ? "Local · " : "") + model.label, model.id));
    if (selected && !state.models.some(model => model.id === selected)) {
      options.unshift(new Option(selected + " · absent du catalogue", selected));
    }
    select.replaceChildren(...options);
    select.value = selected || "";
  }
  function paintProjects() {
    const options = [new Option("Nouveau parcours", "")];
    for (const project of state.projects) {
      options.push(new Option(`${project.name} · ${project.generated}/${project.count} · ${states[project.status] || project.status}`, project.id));
    }
    $("projects").replaceChildren(...options);
    $("projects").value = state.p?.id || "";
  }
  async function refreshProjects() {
    state.projects = (await api("/projects")).projects;
    paintProjects();
  }
  function controls() {
    const p = state.p, editable = !p || p.status === "paused";
    $("source").disabled = state.busy || !!p;
    $("source").hidden = !!p;
    $("count").disabled = state.busy || !!p;
    $("auto-mask").disabled = state.busy || !!p;
    $("intention").readOnly = !editable;
    $("intention").disabled = state.busy;
    for (const id of ["progression-model", "prompt-model"]) $(id).disabled = state.busy || !editable;
    $("start").hidden = !!p;
    $("start").disabled = state.busy || !state.spec;
    $("resume").hidden = !p || p.status !== "paused";
    $("resume").disabled = state.busy || actions.pendingSequence();
    $("pause").hidden = !p || !["running", "pausing"].includes(p.status);
    $("pause").disabled = state.busy || p?.status === "pausing";
    $("pause").textContent = p?.status === "pausing" ? "Suspension…" : "Suspendre";
    $("new").disabled = state.busy;
    $("projects").disabled = state.busy;
    $("transitions").hidden = !p || p.transferable_images < 2 || !p.transitions_available;
    $("transitions").disabled = state.busy;
    actions.paint();
  }
  function frames() {
    if (!state.p) return [];
    return [{key:"source",asset_id:state.p.source_asset_id,title:"Départ",index:0},
      ...(state.p.ordered_steps || state.p.steps).filter(step => step.output_asset_id).map((step, index) => ({key:step.id,
        asset_id:step.output_asset_id,title:step.action.title,index:index + 1,step}))];
  }
  function showImage(frame) {
    hidePreview();
    const url = frame.url || asset(frame.asset_id);
    $("detail-title").textContent = frame.detailTitle || (frame.index ? `Image ${frame.index} · ${frame.title}` : "Image de départ");
    $("detail").classList.remove("ij-native-zoom");
    $("detail-zoom").textContent = "Taille réelle";
    $("detail-zoom").setAttribute("aria-pressed", "false");
    $("detail-image").src = url;
    $("detail-image").alt = frame.title;
    $("detail-action").textContent = frame.step?.action.change || "";
    $("detail-review").textContent = frame.note ?? (frame.step?.review?.observation || (frame.step ? "Relecture à venir." : ""));
    $("detail-prompt").hidden = !frame.step;
    $("detail-prompt").open = false;
    $("detail-models").textContent = frame.step
      ? `Progression : ${frame.step.review?.model_id || state.p.progression_model_id}\nPrompt MiniMax : ${frame.step.prompt_model_id}` : "";
    $("prompt-text").textContent = frame.step?.prompt || "";
    $("download").href = url;
    $("download").download = frame.filename || `parcours-${frame.index}.png`;
    const protection = frame.step?.protection;
    $("detail-protection").hidden = !protection?.mask_asset_id;
    $("detail-protection").open = false;
    $("mask-views").replaceChildren();
    $("mask-note").textContent = protection?.mask_asset_id
      ? `${Math.round(protection.coverage * 100)} % de couverture · Blanc : rendu retenu ; noir : image précédente conservée.` : "";
    if (protection?.mask_asset_id) {
      for (const [label, identity] of [["Résultat protégé", frame.asset_id], ["Avant", frame.step.source_asset_id],
        ["Rendu brut", frame.step.raw_output_asset_id], ["Masque", protection.mask_asset_id]]) {
        const button = document.createElement("button");
        button.type = "button"; button.textContent = label;
        button.setAttribute("aria-pressed", String(label === "Résultat protégé"));
        button.onclick = () => {
          $("detail-image").src = asset(identity); $("detail-image").alt = label;
          $("download").href = asset(identity); $("download").download = `parcours-${frame.index}-${label}.png`;
          for (const item of $("mask-views").children) item.setAttribute("aria-pressed", String(item === button));
        };
        $("mask-views").append(button);
      }
    }
    if (!$("detail").open) $("detail").showModal();
  }
  function paint() {
    controls();
    const p = state.p;
    $("result").hidden = !p;
    if (!p) return;
    const index = p.phase === "reviewing" || p.phase === "completed" ? p.generated : Math.min(p.generated + 1, p.count);
    $("status").textContent = p.status === "completed" ? `${p.generated} nouvelles images${p.manual_generated ? ` + ${p.manual_generated} ajoutées` : ""} · Terminé`
      : p.status === "pausing" ? `Étape ${index}/${p.count} · L’opération en cours se termine…`
      : p.status === "paused" ? `Étape ${index}/${p.count} · Suspendu — tu peux modifier l’intention avant de reprendre.`
      : `Étape ${index}/${p.count} · ${phases[p.phase] || p.phase}`;
    if (p.manual_generated && p.status !== "completed") {
      $("status").textContent += ` · +${p.manual_generated} étape${p.manual_generated > 1 ? "s" : ""} ajoutée${p.manual_generated > 1 ? "s" : ""}`;
    }
    $("progress").max = p.count;
    $("progress").value = p.generated;
    $("destination").textContent = p.destination;
    $("plan").hidden = !p.milestones.length;
    $("milestones").replaceChildren(...p.milestones.map((milestone, index) => {
      const li = document.createElement("li");
      li.textContent = milestone + (index < p.completed_milestones ? " ✓" : "");
      li.classList.toggle("ij-done", index < p.completed_milestones);
      return li;
    }));
    $("warning").textContent = p.warning || "";
    $("warning").hidden = !p.warning;
    const entries = frames();
    const galleryKey = JSON.stringify(entries.map(f => [f.key, f.asset_id, f.title, f.step?.review?.assessment]));
    if (galleryKey !== state.galleryKey) {
      hidePreview();
      state.galleryKey = galleryKey;
      $("frieze").replaceChildren(...entries.map((frame, index) => {
        const button = document.createElement("button"), img = document.createElement("img");
        const title = document.createElement("span"), note = document.createElement("small");
        button.type = "button";
        button.title = "Agrandir l’image · " + frame.title;
        button.dataset.ijThumbnail = "";
        button.setAttribute("aria-label", frame.index ? `Ouvrir l’image ${frame.index} : ${frame.title}` : "Ouvrir l’image de départ");
        img.src = asset(frame.asset_id); img.alt = frame.title; img.loading = "lazy";
        title.textContent = frame.index ? `${frame.index} · ${frame.title}` : "Départ";
        note.textContent = !frame.step ? "Image d’origine" : frame.step.review?.assessment === "similar" ? "Changement faible"
          : frame.step.review?.assessment === "unusable" ? "Progression bloquée" : frame.step.review ? "Image relue" : "À relire";
        button.append(img, title, note, zoomBadge());
        button.onclick = () => showImage(frame);
        return actions.card(frame, entries[index + 1], button);
      }));
    }
    actions.paint();
  }
  function accept(project, syncForm=false) {
    if (state.p?.id === project.id && state.p.version > project.version) return;
    // Set the initial fold only once; polling must respect subsequent user toggles.
    if (state.p?.id !== project.id) $("setup").open = false;
    state.p = project;
    if (syncForm || !state.formDirty) {
      $("intention").value = project.intention;
      $("count").value = project.count;
      $("auto-mask").checked = project.auto_mask === true;
      const size = project.render_profile?.dimensions || project.source_dimensions;
      $("resolution").textContent = size ? `${size[0]} × ${size[1]} · ${project.render_profile?.settings?.steps || 18} passes` : "";
      fillModels($("progression-model"), project.progression_model_id);
      fillModels($("prompt-model"), project.prompt_model_id);
      state.formDirty = false;
    }
    revokePreview();
    $("source-preview").src = asset(project.source_asset_id);
    $("source-preview").hidden = false;
    $("source-open").hidden = false;
    try { sessionStorage.setItem(storageKey, project.id); } catch (_) {}
    message(project.error || "");
    paint();
  }
  async function open(identity) {
    actions.reset();
    const epoch = ++state.epoch;
    const response = await api("/projects/" + encodeURIComponent(identity));
    if (epoch !== state.epoch) return;
    message(""); state.galleryKey = ""; state.resumeCommand = null;
    accept(response.project, true); paintProjects();
  }
  function newJourney() {
    actions.reset();
    $("setup").open = true;
    hidePreview();
    state.epoch += 1;
    state.p = null; state.formDirty = false; state.galleryKey = "";
    state.createCommand = null; state.resumeCommand = null;
    revokePreview();
    $("form").reset();
    $("resolution").textContent = "≈ 3 MP · 18 passes";
    $("count").value = state.spec?.default_images || 5;
    $("source-preview").hidden = true;
    $("source-open").hidden = true;
    $("source-preview").removeAttribute("src");
    fillModels($("progression-model"), state.spec?.default_model_id);
    fillModels($("prompt-model"), state.spec?.default_model_id);
    $("models").open = false; $("plan").open = false;
    try { sessionStorage.removeItem(storageKey); } catch (_) {}
    message(""); paintProjects(); paint();
  }
  async function run(task) {
    if (state.busy) return;
    state.busy = true; message(""); controls();
    try { await task(); }
    catch (error) {
      message(error.message);
      if (state.p) {
        try { accept((await api(endpoint(""))).project); } catch (_) {}
      }
    } finally { state.busy = false; paint(); }
  }
  async function initialize() {
    if (state.loading) return state.loading;
    state.loading = (async () => {
      const results = await Promise.allSettled([api("/spec"), api("/projects"), api("/models")]);
      if (results[0].status === "rejected") throw results[0].reason;
      state.spec = results[0].value;
      $("count").max = state.spec.max_images;
      if (results[1].status === "fulfilled") state.projects = results[1].value.projects;
      else message(results[1].reason.message);
      if (results[2].status === "fulfilled") state.models = results[2].value.models;
      else $("model-note").textContent = "Catalogue des modèles indisponible. Le choix enregistré est conservé. " + results[2].reason.message;
      fillModels($("progression-model"), state.spec.default_model_id);
      fillModels($("prompt-model"), state.spec.default_model_id);
      paintProjects();
      let saved = null;
      try { saved = sessionStorage.getItem(storageKey); } catch (_) {}
      if (saved && state.projects.some(project => project.id === saved)) await open(saved);
      paint();
    })().catch(error => { state.loading = null; throw error; });
    return state.loading;
  }
  function zoomBadge() {
    const badge = document.createElement("span");
    badge.className = "ij-zoom-badge";
    badge.setAttribute("aria-hidden", "true");
    badge.innerHTML = '<svg viewBox="0 0 24 24"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6M10 7v6"/></svg>';
    return badge;
  }
  $("source-open").append(zoomBadge());
  $("source-open").onclick = () => showImage({index:0, title:"Image de départ",
    url:$("source-preview").src, filename:state.p ? null : $("source").files[0]?.name});
  const preview = $("image-preview"), previewImage = $("preview-content");
  document.body.append(preview);
  let previewTimer = null, previewAnchor = null;
  function hidePreview() {
    clearTimeout(previewTimer); previewTimer = null; previewAnchor = null;
    if (typeof preview.hidePopover === "function" && preview.matches(":popover-open")) preview.hidePopover();
    preview.hidden = true;
  }
  function placePreview(thumb) {
    if (previewAnchor !== thumb || !thumb.isConnected || root.hidden || $("detail").open || $("operation").open) return hidePreview();
    const source = thumb.querySelector("img");
    if (!source?.complete || !source.naturalWidth) return;
    const rect = source.getBoundingClientRect(), margin = 12;
    if (rect.width <= 0 || rect.height <= 0) return hidePreview();
    const fit = Math.min(rect.width / source.naturalWidth, rect.height / source.naturalHeight);
    let width = source.naturalWidth * fit * 3, height = source.naturalHeight * fit * 3;
    const viewportWidth = document.documentElement.clientWidth, viewportHeight = window.innerHeight;
    const scale = Math.min(1, (viewportWidth - 2 * margin - 14) / width, (viewportHeight - 2 * margin - 36) / height);
    if (!Number.isFinite(scale) || scale <= 0) return hidePreview();
    width = Math.floor(width * scale); height = Math.floor(height * scale);
    previewImage.src = source.currentSrc || source.src;
    previewImage.alt = source.alt;
    $("preview-caption").textContent = source.alt;
    preview.style.width = width + "px"; previewImage.style.height = height + "px";
    preview.hidden = false;
    if (typeof preview.showPopover === "function" && !preview.matches(":popover-open")) preview.showPopover();
    const box = preview.getBoundingClientRect();
    let left = rect.right + margin;
    if (left + box.width > viewportWidth - margin) left = rect.left - box.width - margin;
    preview.style.left = Math.max(margin, Math.min(left, viewportWidth - box.width - margin)) + "px";
    preview.style.top = Math.max(margin, Math.min(rect.top, viewportHeight - box.height - margin)) + "px";
  }
  function schedulePreview(thumb) {
    if (previewAnchor === thumb) return;
    hidePreview(); previewAnchor = thumb;
    previewTimer = setTimeout(() => placePreview(thumb), 160);
    const source = thumb.querySelector("img");
    if (source && !source.complete) source.addEventListener("load", () => {
      if (previewAnchor === thumb) placePreview(thumb);
    }, {once:true});
  }
  root.addEventListener("pointerover", event => {
    if (event.pointerType === "touch") return;
    const thumb = event.target.closest("[data-ij-thumbnail]");
    if (thumb && !thumb.contains(event.relatedTarget)) schedulePreview(thumb);
  });
  root.addEventListener("pointerout", event => {
    const thumb = event.target.closest("[data-ij-thumbnail]");
    if (thumb && !thumb.contains(event.relatedTarget)) hidePreview();
  });
  root.addEventListener("focusin", event => {
    const thumb = event.target.closest("[data-ij-thumbnail]");
    if (thumb) schedulePreview(thumb);
  });
  root.addEventListener("focusout", event => {
    const thumb = event.target.closest("[data-ij-thumbnail]");
    if (thumb && !thumb.contains(event.relatedTarget)) hidePreview();
  });
  document.addEventListener("scroll", hidePreview, true);
  document.addEventListener("keydown", event => { if (event.key === "Escape") hidePreview(); });
  window.addEventListener("resize", hidePreview);
  window.addEventListener("blur", hidePreview);
  $("setup").addEventListener("toggle", hidePreview);
  $("form").addEventListener("input", () => {
    state.formDirty = true; state.createCommand = null; state.resumeCommand = null;
  });
  $("source").addEventListener("change", () => {
    hidePreview();
    revokePreview();
    const file = $("source").files[0];
    if (file) { state.previewUrl = URL.createObjectURL(file); $("source-preview").src = state.previewUrl; }
    $("source-preview").hidden = !file;
    $("source-open").hidden = !file;
  });
  $("form").addEventListener("submit", event => {
    event.preventDefault();
    run(async () => {
      if (state.p) {
        if (state.p.status !== "paused") return;
        state.resumeCommand ||= commandId();
        const response = await api(endpoint("/resume"), "POST", {version:state.p.version, command:state.resumeCommand,
          intention:$("intention").value, progression_model_id:$("progression-model").value, prompt_model_id:$("prompt-model").value});
        state.resumeCommand = null; accept(response.project, true);
      } else {
        const file = $("source").files[0];
        if (!file) throw new Error("Choisis l’image de départ.");
        if (file.size > 25 * 1024 ** 2) throw new Error("Une image est limitée à 25 Mio.");
        state.createCommand ||= commandId();
        const body = new FormData();
        body.append("source_image", file); body.append("command", state.createCommand);
        body.append("intention", $("intention").value); body.append("count", $("count").value);
        body.append("progression_model_id", $("progression-model").value);
        body.append("prompt_model_id", $("prompt-model").value);
        body.append("auto_mask", String($("auto-mask").checked));
        const response = await core.request(apiRoot + "/projects", {method:"POST",body});
        accept(response.project, true); state.createCommand = null;
      }
      await refreshProjects();
    });
  });
  $("pause").onclick = () => run(async () => accept((await api(endpoint("/pause"), "POST")).project));
  $("new").onclick = () => newJourney();
  $("projects").onchange = () => {
    const identity = $("projects").value;
    if (identity) run(() => open(identity)); else newJourney();
  };
  $("transitions").onclick = () => run(async () => {
    const response = await api(endpoint("/transitions"), "POST");
    if (window.PanelForgeImageTransitions?.open) await window.PanelForgeImageTransitions.open(response.project_id);
    else message("La frise est enregistrée dans l’atelier Transitions.");
  });
  $("detail-zoom").onclick = () => {
    const native = $("detail").classList.toggle("ij-native-zoom");
    $("detail-zoom").textContent = native ? "Ajuster" : "Taille réelle";
    $("detail-zoom").setAttribute("aria-pressed", String(native));
  };
  $("detail-image").onclick = () => $("detail-zoom").click();
  $("close").onclick = () => $("detail").close();
  $("detail").addEventListener("click", event => { if (event.target === $("detail")) $("detail").close(); });
  new MutationObserver(() => {
    hidePreview();
    if (!root.hidden) initialize().catch(error => message(error.message));
  }).observe(root, {attributes:true,attributeFilter:["hidden"]});
  setInterval(async () => {
    if (root.hidden || document.hidden || state.busy || state.polling || !state.p) return;
    state.polling = true;
    const identity = state.p.id, epoch = state.epoch;
    try {
      const response = await api("/projects/" + encodeURIComponent(identity));
      if (epoch !== state.epoch || state.p?.id !== identity || state.busy) return;
      const previousStatus = state.p.status;
      if (response.project.version !== state.p.version) accept(response.project);
      if (previousStatus !== state.p.status) await refreshProjects();
    } catch (error) { if (epoch === state.epoch) message(error.message); }
    finally { state.polling = false; }
  }, 2000);
  if (!root.hidden) initialize().catch(error => message(error.message));
  paint();
})();
