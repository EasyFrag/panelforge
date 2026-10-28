(() => {
  "use strict";
  const root = document.getElementById("mh-assisted-lab-workspace");
  if (!root) return;
  const el = name => document.getElementById("mh-" + name);
  const api = "/api/image-lab/mh-assisted", artApi = "/api/image-lab/krea2-assisted";
  const storageKey = "panelforge.mh-assisted.current.v1";
  const state = {project:null, spec:null, models:[], presets:[], styles:[], poses:[], catalog:null,
    newArt:null, newPose:null, busy:false, initialized:false, loading:null, poll:null, pollAbort:null,
    dirty:new Set(), picker:null, page:0, createId:null, pending:new Map(), historySignature:"", pollFailed:false};
  const activeStatuses = new Set(["queued", "running", "submitting", "submitted", "cancel_pending"]);
  const stage = () => state.project?.stages.find(s => s.id === state.project.active_stage_id);
  const assetUrl = id => "/api/assets/" + encodeURIComponent(id) + "/content";
  const stageUrl = () => `${api}/projects/${state.project.id}/stages/${stage().id}`;
  const visible = () => !root.hidden && !document.hidden;
  const uuid = () => crypto.randomUUID();
  const node = (tag, text, className) => {
    const item = document.createElement(tag);
    if (text != null) item.textContent = text;
    if (className) item.className = className;
    return item;
  };
  const button = (text, fn) => {
    const b = node("button", text); b.type = "button"; b.addEventListener("click", fn); return b;
  };
  const message = text => { el("error").textContent = text || ""; el("error").hidden = !text; };
  function image(src, alt, lazy=true) {
    const img = document.createElement("img"); img.src = src; img.alt = alt || "";
    if (lazy) img.loading = "lazy";
    img.addEventListener("click", () => preview(src, alt));
    return img;
  }
  function preview(src, alt) {
    el("image-full").src = src; el("image-full").alt = alt || "Aperçu";
    if (!el("image-dialog").open) el("image-dialog").showModal();
  }
  async function request(url, options={}) {
    const response = await fetch(url, options);
    let value; try { value = await response.json(); } catch (_) { value = null; }
    if (!response.ok) {
      const detail = value?.detail;
      const text = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(x => x.msg).join(" · ") : `Erreur HTTP ${response.status}`;
      const error = new Error(text); error.status = response.status; throw error;
    }
    if (!value) throw new Error("Réponse incomplète du serveur. Actualise le projet avant de réessayer.");
    return value;
  }
  const jsonRequest = (url, value, method="POST") => request(url, {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(value)});
  const loras = window.PanelForgeMinimaxLoras.mount(el("loras"), {api, request,
    onChange:() => { state.dirty.add("settings"); updateControls(); }});
  function updateControls() {
    el("new-fields").disabled = state.busy || !state.spec;
    el("editor-fields").disabled = state.busy;
    loras.setDisabled(state.busy || !stage());
    el("create").disabled = state.busy || !state.spec || !el("new-model").value
      || (!state.newPose && !el("new-reference").files.length);
    const s = stage(), generating = s?.attempts.some(a => activeStatuses.has(a.status));
    const prompting = s?.messages.some(m => activeStatuses.has(m.status));
    el("chat").disabled = state.busy || !s || prompting;
    el("render").disabled = state.busy || !s || generating || prompting || (!s.prompt_ready && !state.dirty.has("prompt"));
    root.querySelectorAll(".mh-attempt button, #mh-history button, .mh-picker-card button, .mh-picker-card select").forEach(b => { b.disabled = state.busy; });
    el("picker-install").disabled = state.busy;
  }
  async function perform(fn) {
    if (state.busy) return;
    state.busy = true; stopPoll(); updateControls(); message("");
    try { await fn(); }
    catch (error) {
      message(error.message);
      if (state.project) {
        try { await reloadProject(); } catch (_) { /* Preserve local edits and command identities after a lost response. */ }
      }
    } finally { state.busy = false; updateControls(); schedulePoll(); }
  }
  function choices(select, values, selected="", empty="Tous") {
    select.replaceChildren(new Option(empty, ""));
    values.forEach(value => select.append(new Option(value, value)));
    select.value = values.includes(selected) ? selected : "";
  }
  function presetOptions(select, selected, snapshot=null) {
    select.replaceChildren(new Option("Sans preset", ""));
    state.presets.forEach(p => select.append(new Option(p.name, p.preset_id)));
    if (selected && !state.presets.some(p => p.preset_id === selected))
      select.append(new Option((snapshot?.name || selected) + " · conservé dans le projet", selected));
    select.value = selected || "";
  }
  function displayChoice(target, kind, value) {
    const img = el(`${target}-${kind}-image`), name = el(`${target}-${kind}-name`);
    name.textContent = value ? kind === "pose" ? `${value.number} · ${value.name} · ${value.angle}`
      : value.display_name || value.name : kind === "pose" ? "Sans pose" : "Sans direction artistique";
    img.hidden = !value; el(`${target}-${kind}-clear`).hidden = !value;
    if (value) img.src = kind === "pose" ? value.asset_id ? assetUrl(value.asset_id) : `${api}/poses/${encodeURIComponent(value.id)}/thumbnail`
      : value.thumbnail_url || `${artApi}/art-styles/thumbnail?style_id=${encodeURIComponent(value.style_id)}`;
    else img.removeAttribute("src");
  }
  async function loadResources() {
    const draftModel = state.dirty.has("model_id") ? el("model").value : null;
    const draftRatio = state.dirty.has("settings") ? el("ratio").value : null;
    const results = await Promise.allSettled([
      request(`${api}/spec`), request(`${api}/models`), request(`${artApi}/style-presets`),
    ]);
    if (results[0].status !== "fulfilled") throw results[0].reason;
    state.spec = results[0].value; state.catalog = state.spec.pose_catalog;
    const notes = [];
    if (results[1].status === "fulfilled") state.models = results[1].value.models;
    else notes.push("Modèles indisponibles : " + results[1].reason.message);
    if (results[2].status === "fulfilled") state.presets = results[2].value.presets;
    else notes.push("Presets indisponibles : " + results[2].reason.message);
    const model = el("new-model").value || state.spec.default_model_id;
    window.PanelForgeModelPicker.populate(el("new-model"), state.models, model);
    window.PanelForgeModelPicker.populate(el("model"), state.models, stage()?.model_id || model);
    if (stage()) window.PanelForgeModelPicker.select(el("model"), stage().model_id);
    if (draftModel) window.PanelForgeModelPicker.select(el("model"), draftModel);
    presetOptions(el("new-preset"), el("new-preset").value);
    el("ratio").replaceChildren(...state.spec.aspect_ratios.map(r => new Option(r, r)));
    if (draftRatio) el("ratio").value = draftRatio;
    if (state.project) renderProject(state.project);
    el("status").textContent = notes.join(" · ") || "Images fixes · au moins une référence";
    updateControls();
  }
  async function history() {
    const result = await request(`${api}/projects`);
    el("history").replaceChildren(); el("history-empty").hidden = result.projects.length > 0;
    for (const p of result.projects) {
      const li = node("li"), b = button("", () => perform(async () => { await save(); await openProject(p.id); }));
      if (p.thumbnail_asset_id) {
        const img = document.createElement("img"); img.src = assetUrl(p.thumbnail_asset_id); img.alt = ""; img.loading = "lazy"; b.append(img);
      }
      b.append(node("span", p.name)); li.append(b); el("history").append(li);
    }
    updateControls();
  }
  async function openProject(id) {
    const result = await request(`${api}/projects/${encodeURIComponent(id)}`);
    state.dirty.clear(); renderProject(result.project, true); el("new-project").open = false;
    try { sessionStorage.setItem(storageKey, id); } catch (_) { /* Optional navigation persistence. */ }
  }
  async function reloadProject(signal) {
    const id = state.project?.id;
    if (!id) return;
    const result = await request(`${api}/projects/${id}`, {signal});
    if (state.project?.id !== id || result.project.version < state.project.version) return;
    renderProject(result.project);
  }
  function renderProject(project, reset=false) {
    if (reset) state.pollFailed = false;
    state.project = project;
    const s = stage(), c = s.creative;
    el("editor").hidden = false; el("welcome").hidden = true; el("title").textContent = project.name;
    el("download").href = `${api}/projects/${project.id}/download`;
    presetOptions(el("active-preset"), c.style_preset?.preset_id, c.style_preset);
    el("active-language").value = c.prompt_language;
    displayChoice("active", "pose", c.pose); displayChoice("active", "art", c.art_direction);
    if (reset || !state.dirty.has("draft")) el("message").value = s.draft;
    if (reset || !state.dirty.has("prompt")) el("prompt").value = s.prompt;
    if (reset || !state.dirty.has("model_id")) window.PanelForgeModelPicker.select(el("model"), s.model_id);
    if (reset || !state.dirty.has("settings")) {
      for (const [id, key] of [["ratio","aspect_ratio"],["resolution","resolution"],["steps","steps"],
        ["seed","seed"],["reference-mp","reference_megapixels"]]) el(id).value = s.settings[key];
      el("reuse-seed").checked = s.settings.reuse_seed;
      loras.setValue(s.settings.loras || []);
    }
    el("prompt-state").textContent = s.prompt_ready ? "Prompt prêt pour le rendu." : "Prépare ou actualise le prompt avec les choix actuels.";
    const working = s.attempts.find(a => activeStatuses.has(a.status));
    el("render-state").textContent = working ? `${statusLabel(working.status)} · ${working.dimensions.join(" × ")}`
      : `Prochain rendu : ${s.render_dimensions.join(" × ")} · MiniMax H3 Still`;
    el("feedback").hidden = el("feedback-clear").hidden = !s.feedback_attempt_id;
    el("feedback").textContent = "Un essai est sélectionné comme retour visuel pour le prochain échange.";
    renderReferences(s); renderConversation(s); renderAttempts(s);
    for (const [key, id] of state.pending) if ([...s.messages, ...s.attempts].some(x => x.request_id === id)) state.pending.delete(key);
    updateControls();
  }
  function renderReferences(s) {
    el("references").replaceChildren();
    for (const ref of s.references.filter(r => r.active)) {
      const card = node("article"); card.append(image(assetUrl(ref.asset_id), ref.name), node("b", ref.name),
        node("small", ref.usage === "render" ? "Transmise à MiniMax" : "Assistant uniquement"));
      card.title = ref.role;
      if (!ref.id.startsWith("mh-")) card.append(button("Retirer", () => perform(async () => {
        await save(); const refs = stage().references.map(r => r.id === ref.id ? {...r, active:false} : r);
        const result = await jsonRequest(stageUrl(), {revision:stage().revision, changes:{references:refs}}, "PATCH");
        renderProject(result.project);
      })));
      el("references").append(card);
    }
  }
  function statusLabel(value) {
    return ({queued:"En file", running:"En cours", submitting:"Envoi au moteur", submitted:"Rendu en cours", succeeded:"Terminé",
      failed:"Échec", cancelled:"Annulé", cancel_pending:"Annulation demandée"})[value] || value;
  }
  function renderConversation(s) {
    const box = el("conversation"), nearEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    box.replaceChildren();
    for (const m of s.messages) {
      const row = node("article", null, "mh-message");
      row.append(node("b", "Vous"), node("p", m.text), node("b", "Assistant"), node("p", m.reply || statusLabel(m.status)));
      if (m.error) row.append(node("p", m.error, "error"));
      if (m.applied === false) row.append(node("small", "Ce prompt correspond à des choix antérieurs ; il n’a pas remplacé le prompt courant."));
      if (m.can_recover && m.status === "failed") row.append(button("Récupérer le prompt", () => perform(async () => {
        await save(); const result = await jsonRequest(`${stageUrl()}/messages/${m.id}/recover`, {revision:stage().revision});
        renderProject(result.project);
      })));
      if (m.has_reasoning || m.has_draft) row.append(button("Voir la trace", async () => {
        try {
          const result = await request(`${stageUrl()}/messages/${m.id}`);
          el("trace").textContent = result.message.reasoning || result.message.raw || "Aucune trace disponible.";
          el("trace-dialog").showModal();
        } catch (error) { message(error.message); }
      }));
      box.append(row);
    }
    if (nearEnd) box.scrollTop = box.scrollHeight;
  }
  function renderAttempts(s) {
    el("attempts").replaceChildren();
    for (const [index, a] of [...s.attempts].entries()) {
      const card = node("article", null, "mh-attempt");
      card.append(node("b", `Essai ${index+1} · ${statusLabel(a.status)}`));
      if (a.output_asset_id) {
        card.append(image(assetUrl(a.output_asset_id), "Résultat de l’essai " + (index+1)));
        const link = node("a", "Télécharger l’image"); link.href = assetUrl(a.output_asset_id); link.download = `MH-${index+1}.png`; card.append(link);
        card.append(button("Utiliser comme retour visuel", () => perform(async () => {
          await save(); const result = await jsonRequest(stageUrl(), {revision:stage().revision, changes:{feedback_attempt_id:a.id}}, "PATCH");
          renderProject(result.project);
        })));
      }
      if (activeStatuses.has(a.status) && a.status !== "cancel_pending") card.append(button("Annuler", () => perform(async () => {
        const result = await jsonRequest(`${stageUrl()}/attempts/${a.id}/cancel`, {}); renderProject(result.project);
      })));
      card.append(node("small", `${a.dimensions.join(" × ")} · seed ${a.settings.seed}`));
      if (a.settings.loras?.length) card.append(node("small", "LoRA : " + window.PanelForgeMinimaxLoras.summary(a.settings.loras)));
      const creative = a.context.creative;
      card.append(node("small", [creative.prompt_language, creative.style_preset?.name, creative.art_direction?.name,
        creative.pose ? `${creative.pose.number} · ${creative.pose.angle}` : null].filter(Boolean).join(" · ")));
      if (a.error) card.append(node("p", a.error, "error"));
      const details = node("details"); details.append(node("summary", "Prompt de cet essai"), node("pre", a.prompt)); card.append(details);
      if (!activeStatuses.has(a.status)) card.append(button("Reprendre ces choix", () => perform(async () => {
        await save(); const result = await jsonRequest(`${stageUrl()}/attempts/${a.id}/restore`, {revision:stage().revision});
        state.dirty.clear(); renderProject(result.project, true);
      })));
      el("attempts").prepend(card);
    }
  }
  async function save() {
    if (!state.project || !state.dirty.size) return;
    const changes = {};
    if (state.dirty.has("draft")) changes.draft = el("message").value;
    if (state.dirty.has("prompt")) changes.prompt = el("prompt").value;
    if (state.dirty.has("model_id")) changes.model_id = el("model").value;
    if (state.dirty.has("settings")) changes.settings = {...stage().settings,
      aspect_ratio:el("ratio").value, resolution:el("resolution").value, steps:Number(el("steps").value),
      seed:el("seed").value.trim(), reuse_seed:el("reuse-seed").checked, reference_megapixels:Number(el("reference-mp").value),
      loras:loras.getValue()};
    const result = await jsonRequest(stageUrl(), {revision:stage().revision, changes}, "PATCH");
    state.dirty.clear(); renderProject(result.project);
  }
  async function configure(changes) {
    await save();
    const result = await jsonRequest(`${stageUrl()}/creative`, {revision:stage().revision, changes}, "PATCH");
    renderProject(result.project);
  }
  async function command(kind) {
    await save();
    if (kind === "messages" && !stage().draft.trim()) {
      const result = await jsonRequest(stageUrl(), {revision:stage().revision,
        changes:{draft:"Actualise le prompt avec les références et les choix artistiques actuels."}}, "PATCH");
      renderProject(result.project);
    }
    const key = state.project.id + "/" + kind;
    if (!state.pending.has(key)) state.pending.set(key, uuid());
    try {
      const result = await jsonRequest(`${stageUrl()}/${kind}`, {revision:stage().revision, request_id:state.pending.get(key)});
      state.pending.delete(key); renderProject(result.project); await history();
    } catch (error) {
      if (error.status >= 400 && error.status < 500) state.pending.delete(key);
      throw error;
    }
  }
  async function create(event) {
    event.preventDefault();
    if (!el("new-form").reportValidity()) return;
    await perform(async () => {
      await save();
      const form = new FormData(); state.createId ||= uuid();
      form.set("request_id", state.createId); form.set("name", el("new-name").value);
      form.set("intention", el("new-intention").value); form.set("model_id", el("new-model").value);
      form.set("prompt_language", el("new-language").value); form.set("preset_id", el("new-preset").value);
      form.set("art_style_id", state.newArt?.style_id || ""); form.set("pose_id", state.newPose?.id || "");
      if (el("new-reference").files[0]) form.set("reference", el("new-reference").files[0]);
      const result = await request(`${api}/projects`, {method:"POST", body:form});
      state.createId = null; state.dirty.clear(); renderProject(result.project, true); el("new-project").open = false;
      try { sessionStorage.setItem(storageKey, result.project.id); } catch (_) { /* Optional. */ }
      await history(); await command("messages");
    });
  }
  async function loadPickerData() {
    const picker = state.picker;
    if (picker.kind === "pose") {
      const result = await request(`${api}/poses`);
      if (state.picker !== picker || !el("picker").open) return;
      state.poses = result.entries; state.catalog = result.catalog;
    } else {
      let styles;
      try { styles = (await request(`${artApi}/art-styles`)).styles; }
      catch (error) { if (error.status !== 422 && error.status !== 404) throw error; styles = []; }
      if (state.picker !== picker || !el("picker").open) return;
      state.styles = styles;
      choices(el("picker-category"), [...new Set(state.styles.map(s => s.category))].sort());
    }
    renderPicker();
  }
  async function openPicker(kind, target) {
    if (state.busy) return;
    state.picker = {kind, target, projectId:state.project?.id}; state.page = 0;
    el("picker-title").textContent = kind === "pose" ? "Choisir une pose" : "Direction artistique";
    el("picker-search").value = ""; el("picker-grid").replaceChildren(); el("picker-state").textContent = "Chargement…";
    for (const id of ["picker-category", "picker-family", "picker-angle"]) el(id).replaceChildren(new Option("Tous", ""));
    el("picker-family").hidden = el("picker-angle").hidden = el("picker-source").hidden = kind !== "pose";
    el("picker").showModal();
    try { await loadPickerData(); } catch (error) { el("picker-state").textContent = error.message; }
  }
  const searchable = value => String(value || "").normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
  function matchesPose(p, query) {
    const text = searchable(`${p.id} ${p.number} ${p.name} ${p.source_name || ""} ${p.category} ${p.family} ${p.angle}`);
    return query.split(/\s+/).every(word => text.includes(word));
  }
  function syncPoseFilters(query) {
    const unique = (poses, key) => [...new Set(poses.map(p => p[key]))].sort((a,b) => a.localeCompare(b, "fr"));
    choices(el("picker-family"), unique(state.poses, "family"), el("picker-family").value, "Toutes les familles");
    const family = el("picker-family").value;
    const available = state.poses.filter(p => (!family || p.family === family) && matchesPose(p, query));
    choices(el("picker-category"), unique(available, "category"), el("picker-category").value, "Toutes les catégories");
    const category = el("picker-category").value;
    const angles = new Set(available.filter(p => !category || p.category === category).map(p => p.angle));
    choices(el("picker-angle"), (state.catalog?.angles || []).filter(angle => angles.has(angle)), el("picker-angle").value, "Tous les angles");
  }
  function renderPicker() {
    if (!state.picker) return;
    const isPose = state.picker.kind === "pose", query = searchable(el("picker-search").value.trim());
    if (isPose) syncPoseFilters(query);
    const category = el("picker-category").value, family = el("picker-family").value, angle = el("picker-angle").value;
    let values;
    if (isPose) {
      const groups = new Map();
      for (const p of state.poses) {
        if ((category && p.category !== category) || (family && p.family !== family) || (angle && p.angle !== angle)) continue;
        if (!matchesPose(p, query)) continue;
        if (!groups.has(p.pose_id)) groups.set(p.pose_id, []); groups.get(p.pose_id).push(p);
      }
      values = [...groups.values()];
    } else values = state.styles.filter(s => (!category || s.category === category)
      && (!query || searchable(`${s.name} ${s.display_name || ""} ${s.category}`).includes(query)));
    const pages = Math.max(1, Math.ceil(values.length / 24)); state.page = Math.min(state.page, pages-1);
    el("picker-grid").replaceChildren();
    el("picker-state").textContent = isPose && state.catalog?.state !== "ready"
      ? state.catalog?.error || "Installe le catalogue du site pour parcourir les poses. Les images seront conservées au fil de leur utilisation."
      : `${values.length} ${isPose ? "poses" : "directions artistiques"}`;
    el("picker-install").textContent = (isPose ? state.catalog?.state === "ready" : state.styles.length > 0) ? "Actualiser le catalogue" : "Installer le catalogue";
    for (const value of values.slice(state.page*24, state.page*24+24)) {
      const card = node("article", null, "mh-picker-card"); let selected = isPose ? value.find(p => p.angle === "Face") || value[0] : value;
      const src = p => isPose ? `${api}/poses/${encodeURIComponent(p.id)}/thumbnail` : p.thumbnail_url;
      const img = document.createElement("img"); img.src = src(selected); img.alt = selected.name; img.loading = "lazy";
      img.addEventListener("click", () => preview(src(selected), selected.name));
      card.append(img, node("b", isPose ? `${selected.number} · ${selected.name}` : selected.display_name || selected.name),
        node("small", isPose ? `${selected.family} · ${selected.category}` : selected.category));
      if (isPose) {
        const angles = document.createElement("select"); angles.setAttribute("aria-label", "Angle de la pose " + selected.number);
        value.forEach(p => angles.append(new Option(p.angle, p.id))); angles.value = selected.id;
        angles.addEventListener("change", () => { selected = value.find(p => p.id === angles.value); img.src = src(selected); }); card.append(angles);
      }
      card.append(button("Choisir", () => choosePicker(selected))); el("picker-grid").append(card);
    }
    el("picker-page").textContent = `${state.page+1} / ${pages}`;
    el("picker-prev").disabled = state.page === 0; el("picker-next").disabled = state.page >= pages-1;
  }
  async function choosePicker(value) {
    const picker = {...state.picker};
    if (picker.target === "new") {
      if (picker.kind === "pose") state.newPose = value; else state.newArt = value;
      displayChoice("new", picker.kind, value); el("picker").close(); updateControls(); return;
    }
    await perform(async () => {
      if (state.project?.id !== picker.projectId) throw new Error("Le projet actif a changé. Rouvre le sélecteur.");
      await configure(picker.kind === "pose" ? {pose_id:value.id} : {art_style_id:value.style_id}); el("picker").close();
    });
  }
  function stopPoll() {
    clearTimeout(state.poll); state.poll = null; state.pollAbort?.abort(); state.pollAbort = null;
  }
  function schedulePoll() {
    if (!visible() || state.busy || !stage() || state.poll || state.pollAbort || state.pollFailed) return;
    if (![...stage().messages, ...stage().attempts].some(x => activeStatuses.has(x.status))) return;
    state.poll = setTimeout(async () => {
      state.poll = null; const abort = new AbortController(); state.pollAbort = abort;
      try {
        await reloadProject(abort.signal);
        const signature = stage()?.attempts.map(a => a.id + a.status).join("|");
        if (signature !== state.historySignature) { state.historySignature = signature; await history(); }
      } catch (error) { if (error.name !== "AbortError") { state.pollFailed = true; message("Suivi interrompu : " + error.message + " · Utilise Actualiser pour reprendre."); } }
      finally { if (state.pollAbort === abort) { state.pollAbort = null; schedulePoll(); } }
    }, 2000);
  }
  async function activate() {
    if (!visible()) { stopPoll(); for (const id of ["picker", "image-dialog", "trace-dialog"]) if (el(id).open) el(id).close(); return; }
    if (state.loading) return state.loading;
    if (!state.initialized) {
      state.loading = (async () => {
        await loadResources(); void loras.refresh(); await history();
        let previous; try { previous = sessionStorage.getItem(storageKey); } catch (_) { /* Optional. */ }
        if (previous) { try { await openProject(previous); } catch (error) { message(error.message); } }
        state.initialized = true;
      })();
      try { await state.loading; } catch (error) { message(error.message); }
      finally { state.loading = null; updateControls(); }
    }
    schedulePoll();
  }
  el("new-form").addEventListener("submit", create);
  ["new-reference", "new-model"].forEach(id => el(id).addEventListener("change", updateControls));
  el("new-preset").addEventListener("change", () => {
    const preset = state.presets.find(p => p.preset_id === el("new-preset").value);
    if (preset) { el("new-language").value = preset.prompt_language; state.newArt = preset.art_direction; displayChoice("new", "art", state.newArt); }
  });
  el("active-preset").addEventListener("change", () => {
    const preset = state.presets.find(p => p.preset_id === el("active-preset").value);
    const changes = {preset_id:el("active-preset").value};
    if (preset) changes.prompt_language = preset.prompt_language;
    perform(() => configure(changes));
  });
  el("active-language").addEventListener("change", () => perform(() => configure({prompt_language:el("active-language").value})));
  for (const target of ["new", "active"]) for (const kind of ["pose", "art"]) {
    el(`${target}-${kind}-choose`).addEventListener("click", () => openPicker(kind, target));
    el(`${target}-${kind}-image`).addEventListener("click", event => preview(event.target.src, event.target.alt));
    el(`${target}-${kind}-clear`).addEventListener("click", () => {
      if (target === "new") {
        if (kind === "pose") state.newPose = null; else state.newArt = null;
        displayChoice(target, kind, null); updateControls();
      } else perform(() => configure(kind === "pose" ? {pose_id:""} : {art_style_id:""}));
    });
  }
  for (const [id, field] of [["message","draft"],["prompt","prompt"],["model","model_id"],
    ...["ratio","resolution","steps","seed","reuse-seed","reference-mp"].map(id => [id,"settings"])]) {
    for (const event of ["input", "change"]) el(id).addEventListener(event, () => { state.dirty.add(field); updateControls(); });
  }
  el("save").addEventListener("click", () => perform(save));
  el("chat").addEventListener("click", () => perform(() => command("messages")));
  el("render").addEventListener("click", () => perform(() => command("attempts")));
  el("copy").addEventListener("click", () => navigator.clipboard.writeText(el("prompt").value).catch(e => message(e.message)));
  el("reference-add").addEventListener("click", () => perform(async () => {
    const file = el("reference-file").files[0]; if (!file) throw new Error("Choisis une image à ajouter.");
    await save(); const form = new FormData(); form.set("image", file); form.set("revision", stage().revision);
    form.set("name", file.name.slice(0,70)); form.set("usage", el("reference-usage").value); form.set("role", el("reference-role").value);
    const result = await request(`${stageUrl()}/references`, {method:"POST", body:form});
    renderProject(result.project); el("reference-file").value = ""; el("reference-role").value = "";
  }));
  el("feedback-clear").addEventListener("click", () => perform(async () => {
    await save(); const result = await jsonRequest(stageUrl(), {revision:stage().revision, changes:{feedback_attempt_id:null}}, "PATCH"); renderProject(result.project);
  }));
  el("refresh").addEventListener("click", () => perform(async () => { await loadResources(); await reloadProject(); await history(); state.initialized = true; state.pollFailed = false; }));
  el("picker-close").addEventListener("click", () => el("picker").close());
  el("image-close").addEventListener("click", () => el("image-dialog").close());
  el("image-dialog").addEventListener("close", () => el("image-full").removeAttribute("src"));
  el("trace-close").addEventListener("click", () => el("trace-dialog").close());
  for (const id of ["picker-search", "picker-category", "picker-family", "picker-angle"])
    el(id).addEventListener(id === "picker-search" ? "input" : "change", () => { state.page = 0; renderPicker(); });
  el("picker-prev").addEventListener("click", () => { state.page--; renderPicker(); });
  el("picker-next").addEventListener("click", () => { state.page++; renderPicker(); });
  el("picker-install").addEventListener("click", () => perform(async () => {
    el("picker-state").textContent = "Installation du catalogue…";
    await request(state.picker.kind === "pose" ? `${api}/poses/install?force=true` : `${artApi}/art-styles/install?force=true`, {method:"POST"});
    await loadPickerData();
  }));
  document.getElementById("krea2-assisted-preset-manager")?.addEventListener("close", () => {
    if (visible() && !state.busy) loadResources().catch(error => message(error.message));
  });
  document.addEventListener("visibilitychange", activate);
  new MutationObserver(activate).observe(root, {attributes:true, attributeFilter:["hidden"]});
  window.addEventListener("beforeunload", event => { if (state.dirty.size) { event.preventDefault(); event.returnValue = ""; } });
  activate();
})();
