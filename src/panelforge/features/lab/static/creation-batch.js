(() => {
  "use strict";
  const root = document.getElementById("creation-batch-workspace");
  if (!root) return;
  const el = id => document.getElementById("cb-" + id);
  const api = "/api/image-lab/creation-batch";
  const assisted = "/api/image-lab/krea2-assisted";
  const storageKey = "panelforge.creation-batch.current.v1";
  const pendingKey = "panelforge.creation-batch.pending.v1";
  const state = {presets: [], spec: null, intentions: [], art: null, batch: null, rows: new Map(),
    loading: null, submitting: false, importing: false, importSerial: 0, initialized: false,
    poll: null, pollAbort: null, pending: null, styles: [], modelTouched: false, activating: null,
    monitor: {}, actions: new Set(), artTarget: null, factorySending: null};
  const getStored = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const setStored = (key, value) => { try { value ? localStorage.setItem(key, value) : localStorage.removeItem(key); } catch (_) { /* in-memory operation remains available */ } };
  const visible = () => !root.hidden && document.visibilityState !== "hidden";
  const message = text => { el("message").textContent = text || ""; el("message").hidden = !text; };
  const labels = {waiting: "À venir", queued: "En file", starting: "Préparation", running: "En cours", submitting: "Envoi à KREA2",
    succeeded: "Terminé", failed: "En erreur", cancelled: "Annulé", cancel_pending: "Annulation en cours"};
  async function request(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(typeof data.detail === "string" ? data.detail : `Erreur HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return data;
  }
  function updateControls() {
    const active = state.batch && !state.batch.terminal;
    el("fields").disabled = state.submitting || Boolean(active);
    el("launch").disabled = state.submitting || active || state.importing || !state.intentions.length
      || !el("preset").value || !el("model").value || !state.spec || !state.initialized;
    if (el("model").selectedOptions[0]?.dataset.missing) el("launch").disabled = true;
    el("launch").textContent = state.submitting ? "Enregistrement…" : active ? "Batch en cours" : "Lancer le batch";
    el("refresh").disabled = Boolean(state.loading);
    el("art-control").hidden = el("recipe").value !== "6.0.0";
    const localSupported = ["4.0.0", "5.0.0", "6.0.0"].includes(el("recipe").value);
    el("inspiration").disabled = !localSupported;
    updateFactoryButton();
  }
  function updateFactoryButton() {
    const images = (state.batch?.items || []).flatMap(item => item.renders
      || [{...item, status: item.image_status}]).filter(render => render.status === "succeeded" && render.output_asset_id);
    const available = images.filter(render => !render.factory_item_id).length;
    const busy = state.factorySending === state.batch?.batch_id;
    const sent = images.length > 0 && !available;
    const button = el("factory-all");
    button.disabled = Boolean(state.factorySending) || !available;
    button.dataset.sent = String(sent && !busy);
    button.setAttribute("aria-busy", String(busy));
    button.textContent = busy ? "Envoi à l’usine…" : available ? `Envoyer tout à l’usine (${available})`
      : sent ? "✓ Images envoyées" : "Envoyer tout à l’usine";
    button.title = available ? `${available} image(s) disponible(s) non encore envoyée(s), originales et variantes incluses.`
      : "Les nouvelles images terminées pourront être envoyées au prochain clic.";
  }
  function factoryMessage(text, error = false) {
    el("factory-state").textContent = text || "";
    el("factory-state").hidden = !text;
    el("factory-state").dataset.error = String(error);
  }
  async function sendAllToFactory() {
    if (!state.batch || state.factorySending || el("factory-all").disabled) return;
    const batchId = state.batch.batch_id;
    state.factorySending = batchId; updateFactoryButton();
    factoryMessage("Envoi des images disponibles à l’usine…");
    schedulePoll();
    try {
      const result = await request(`${api}/batches/${encodeURIComponent(batchId)}/factory`, {method: "POST"});
      if (state.batch?.batch_id !== batchId) return;
      renderBatch(result.batch); renderMonitoring(result.monitor || {});
      const report = result.factory_delivery;
      let text = `${report.sent} image(s) envoyée(s) · ${report.already_sent} déjà envoyée(s).`;
      if (report.failed) text += ` ${report.failed} échec(s) : réessaie pour les images restantes.`
        + "\n" + report.errors.slice(0, 3).map(e => `${e.item_id} · ${e.render_id === "initial" ? "Original" : "Variante"} : ${e.message}`).join("\n");
      factoryMessage(text, Boolean(report.failed));
    } catch (error) {
      if (state.batch?.batch_id !== batchId) return;
      // A lost response may hide durable receipts; refresh them before retrying.
      try {
        const result = await request(`${api}/batches/${encodeURIComponent(batchId)}`);
        if (state.batch?.batch_id === batchId) { renderBatch(result.batch); renderMonitoring(result.monitor || {}); }
      } catch (_) { /* Per-image server receipts still protect the next request. */ }
      if (state.batch?.batch_id === batchId)
        factoryMessage(error.message + " · Tu peux réessayer : les images déjà reçues ne seront pas renvoyées.", true);
    } finally {
      state.factorySending = null; updateFactoryButton(); schedulePoll();
    }
  }
  function renderArt() {
    el("art-name").textContent = state.art?.display_name || state.art?.name || "Sans direction artistique";
    el("art-image").hidden = !state.art;
    el("art-clear").hidden = !state.art;
    if (state.art) el("art-image").src = state.art.thumbnail_url;
    else el("art-image").removeAttribute("src");
  }
  function presetChanged(applyDefaults = true) {
    const preset = state.presets.find(p => p.preset_id === el("preset").value);
    el("preset-note").textContent = preset
      ? `${preset.settings.model_id} · ${preset.settings.loras.length} LoRA · ${preset.settings.aspect_ratio} · ${preset.settings.megapixels} MP`
      : "Choisissez le preset qui déterminera les réglages KREA2.";
    if (applyDefaults) {
      state.art = preset?.art_direction || null;
      if (preset) el("language").value = preset.prompt_language || "en";
      renderArt();
    }
    updateControls();
  }
  async function loadResources(refresh = false) {
    if (state.loading) return state.loading;
    state.loading = (async () => {
      const [spec, presets] = await Promise.all([
        request(assisted + "/spec" + (refresh ? "?refresh=true" : "")), request(assisted + "/style-presets"),
      ]);
      state.spec = spec;
      state.presets = presets.presets || [];
      const selected = el("preset").value;
      el("preset").replaceChildren(new Option("Choisir un preset", ""));
      for (const [category, name] of [["work", "Work"], ["fun", "Fun"], ["nsfw", "NSFW"], ["archive", "Archive"]]) {
        const values = state.presets.filter(p => (p.category || "work") === category);
        if (!values.length) continue;
        const group = document.createElement("optgroup"); group.label = name;
        values.forEach(p => group.append(new Option(p.name, p.preset_id)));
        el("preset").append(group);
      }
      if (state.presets.some(p => p.preset_id === selected)) el("preset").value = selected;
      else if (selected && state.batch && !state.batch.terminal && state.batch.config?.preset_id === selected) {
        el("preset").append(new Option(state.batch.preset_name + " · copie du batch", selected));
        el("preset").value = selected;
      }
      const recipe = el("recipe").value || "6.0.0";
      el("recipe").replaceChildren(...(spec.assistance_recipes || []).map(r => new Option(r.label, r.version)));
      el("recipe").value = recipe;
      const currentModel = el("model").value;
      const preferred = (spec.llm_models || []).find(m => (m.source === "local" || m.id.startsWith("local::"))
        && m.id.toLowerCase().includes("unsloth/gemma-4-31b-it-qat-gguf"));
      window.PanelForgeModelPicker.populate(el("model"), spec.llm_models || [],
        state.modelTouched ? currentModel : preferred?.id || "");
      if (state.modelTouched && currentModel) window.PanelForgeModelPicker.select(el("model"), currentModel);
      if (!state.modelTouched && !preferred) {
        el("model").prepend(new Option("Gemma 4 local indisponible · choisir un modèle", ""));
        el("model").value = "";
      }
      presetChanged(false);
    })();
    updateControls();
    try { await state.loading; }
    finally { state.loading = null; updateControls(); }
  }
  async function importCsv() {
    const serial = ++state.importSerial;
    const file = el("file").files[0];
    state.intentions = [];
    state.pending = null;
    state.importing = Boolean(file);
    message(""); updateControls();
    if (!file) { el("import-state").textContent = "Aucun fichier chargé."; return; }
    el("import-state").textContent = "Lecture du CSV…";
    try {
      if (file.size > 8 * 1024 * 1024) throw new Error("Le CSV dépasse 8 Mio.");
      const form = new FormData(); form.set("file", file);
      const payload = await request(api + "/csv", {method: "POST", body: form});
      if (serial !== state.importSerial) return;
      state.intentions = payload.intentions;
      el("import-state").textContent = `${payload.count} intention${payload.count > 1 ? "s" : ""} identifiée${payload.count > 1 ? "s" : ""}`
        + (payload.ignored ? ` · ${payload.ignored} entrée(s) vide(s) ignorée(s)` : "");
      if (!el("name").value.trim()) el("name").value = file.name.replace(/\.csv$/i, "").slice(0, 120);
    } catch (error) {
      if (serial === state.importSerial) { el("import-state").textContent = "CSV non chargé."; message(error.message); }
    } finally {
      if (serial === state.importSerial) { state.importing = false; updateControls(); }
    }
  }
  function stage(element, status, tracking = {}) {
    status = tracking.status || status;
    element.dataset.state = status;
    if (!element._label) {
      element._label = document.createElement("span");
      element._bar = document.createElement("progress"); element._bar.max = 1;
      element._bar.setAttribute("aria-label", "Avancement");
      element.append(element._label, element._bar);
    }
    const value = status === "succeeded" ? 1 : ["waiting", "queued"].includes(status) ? 0 : tracking.progress;
    const measurable = Number.isFinite(value);
    element._label.textContent = (labels[status] || status)
      + (tracking.position ? ` · position ${tracking.position}` : "")
      + (measurable && !["waiting", "queued", "failed", "cancelled"].includes(status) ? ` · ${Math.round(value * 100)} %` : "");
    if (measurable) element._bar.value = Math.max(0, Math.min(1, value));
    else element._bar.removeAttribute("value");
    element._bar.hidden = ["failed", "cancelled"].includes(status);
    element.title = tracking.message || "";
  }
  const hover = document.createElement("img"); hover.className = "cb-hover"; hover.hidden = true; hover.alt = "Aperçu agrandi";
  document.body.append(hover);
  function preview(button, url) {
    const rect = button.getBoundingClientRect();
    hover.src = url; hover.hidden = false;
    const position = () => {
      const width = hover.offsetWidth || Math.min(840, window.innerWidth - 24);
      const height = hover.offsetHeight || Math.min(840, window.innerHeight * .88);
      hover.style.left = `${Math.max(12, Math.min(rect.left - width - 12, window.innerWidth - width - 12))}px`;
      hover.style.top = `${Math.max(12, Math.min(rect.top, window.innerHeight - height - 12))}px`;
    };
    hover.onload = position; position();
  }
  const newId = () => crypto.randomUUID ? crypto.randomUUID() :
    "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (Number(c) ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> Number(c) / 4).toString(16));
  function actionButton(label, title, action) {
    const button = document.createElement("button"); button.type = "button";
    button.textContent = label; button.title = title; button.setAttribute("aria-label", title);
    button.addEventListener("click", () => action(button)); return button;
  }
  async function imageAction(itemId, renderId, body, button) {
    const batchId = state.batch.batch_id;
    const base = `${api}/batches/${encodeURIComponent(batchId)}/items/${encodeURIComponent(itemId)}`;
    const url = body ? base + "/variants" : base + `/renders/${encodeURIComponent(renderId)}/factory`;
    const command = body ? {...body, source_render_id: renderId} : null;
    const key = "panelforge.creation-batch.action:" + url + ":" + JSON.stringify(command);
    if (state.actions.has(key)) return;
    let payload;
    if (command) {
      try { payload = JSON.parse(getStored(key) || "null"); } catch (_) { payload = null; }
      payload ||= {...command, request_id: newId()}; setStored(key, JSON.stringify(payload));
    }
    state.actions.add(key); button.disabled = true; button.dataset.busy = "true";
    stopPolling(); message("");
    try {
      const result = await request(url, {method: "POST", headers: {"Content-Type": "application/json"},
        ...(payload ? {body: JSON.stringify(payload)} : {})});
      setStored(key, null);
      if (state.batch?.batch_id === batchId) {
        renderBatch(result.batch); renderMonitoring(result.monitor || {});
      }
    } catch (error) {
      if ([404, 409, 422].includes(error.status)) setStored(key, null);
      message(error.message + " · Tu peux réessayer cette même action.");
    } finally {
      state.actions.delete(key); delete button.dataset.busy;
      button.disabled = button.dataset.sent === "true";
      schedulePoll();
    }
  }
  const presetDialog = document.createElement("dialog"); presetDialog.className = "cb-dialog cb-variant-dialog";
  presetDialog.id = "cb-variant-dialog";
  const presetTitle = document.createElement("h2"), presetSelect = document.createElement("select");
  presetSelect.setAttribute("aria-label", "Preset créatif de la variante");
  let presetTarget = null;
  const applyPreset = actionButton("Appliquer et générer", "Créer une variante avec ce preset", async button => {
    const preset = state.presets.find(p => p.preset_id === presetSelect.value);
    if (!preset || !presetTarget) return;
    const target = presetTarget; presetDialog.close();
    await imageAction(target.itemId, target.renderId, {kind: "preset", preset_id: preset.preset_id, preset_revision: preset.revision}, button);
  });
  presetDialog.append(presetTitle, presetSelect, applyPreset, actionButton("Fermer", "Fermer", () => presetDialog.close()));
  document.body.append(presetDialog, el("art-dialog"), el("image-dialog"));
  function choosePreset(itemId, renderId) {
    presetTarget = {itemId, renderId}; presetTitle.textContent = `Preset créatif · ligne ${itemId}`;
    presetSelect.replaceChildren(...state.presets.map(p => new Option(p.name, p.preset_id)));
    applyPreset.disabled = !state.presets.length; presetDialog.showModal();
  }
  async function chooseArt(target = null) {
    state.artTarget = target;
    el("art-dialog").querySelector("h2").textContent = target ? `Direction artistique · ligne ${target.itemId}` : "Direction artistique";
    el("art-dialog").showModal(); el("art-state").textContent = "Chargement…";
    try { const payload = await request(assisted + "/art-styles"); state.styles = payload.styles || []; renderStyles(); }
    catch (error) { el("art-state").textContent = error.message; }
  }
  function renderImages(refs, item) {
    const renders = item.renders || [{...item, render_id: "initial", label: "Original", status: item.image_status}];
    for (const render of renders) {
      let card = refs.cards.get(render.render_id);
      if (!card) {
        const node = document.createElement("div"); node.className = "cb-image-card";
        const label = document.createElement("small"), status = document.createElement("span"); status.className = "cb-stage";
        node.append(label, status); refs.output.append(node);
        card = {node, label, status, asset: null}; refs.cards.set(render.render_id, card);
      }
      card.label.textContent = render.label || "Original";
      stage(card.status, render.status);
      if (render.output_asset_id && card.asset !== render.output_asset_id) {
        card.asset = render.output_asset_id;
        const button = document.createElement("button"); button.type = "button"; button.className = "cb-preview";
        button.setAttribute("aria-label", `Agrandir l’image ${item.item_id} · ${render.label || "Original"}`);
        const image = document.createElement("img"); image.src = render.thumbnail_url; image.loading = "lazy"; image.alt = "Image générée";
        button.append(image); card.node.insertBefore(button, card.status);
        button.addEventListener("mouseenter", () => preview(button, render.hover_url || render.thumbnail_url));
        button.addEventListener("focus", () => preview(button, render.hover_url || render.thumbnail_url));
        ["mouseleave", "blur"].forEach(type => button.addEventListener(type, () => { hover.hidden = true; }));
        button.addEventListener("click", () => { hover.hidden = true; el("image-full").src = render.image_url; el("image-dialog").showModal(); });
        const actions = document.createElement("div"); actions.className = "cb-image-actions";
        card.factory = actionButton("+", "Envoyer à l’usine", b => imageAction(item.item_id, render.render_id, null, b));
        card.factory.className = "cb-factory";
        actions.append(card.factory,
          actionButton("8 + 4", "Régénérer · Finition 4 steps · 8 + 4", b => imageAction(item.item_id, render.render_id, {kind: "render"}, b)),
          actionButton("DA", "Appliquer une direction artistique et générer", () => chooseArt({itemId: item.item_id, renderId: render.render_id})),
          actionButton("Preset", "Appliquer un preset créatif et générer", () => choosePreset(item.item_id, render.render_id)));
        card.node.append(actions);
      }
      card.status.hidden = Boolean(render.output_asset_id);
      if (card.factory) {
        const sent = Boolean(render.factory_item_id);
        card.factory.dataset.sent = String(sent); card.factory.textContent = sent ? "✓" : "+";
        card.factory.title = sent ? "Envoyé à l’usine" : "Envoyer à l’usine";
        card.factory.setAttribute("aria-label", card.factory.title);
        card.factory.disabled = sent || card.factory.dataset.busy === "true";
      }
      card.node.title = render.error || "";
    }
  }
  function addRow(item) {
    const row = document.createElement("tr"); row.dataset.itemId = item.item_id;
    const number = document.createElement("td"); number.textContent = item.item_id;
    const intention = document.createElement("td");
    const title = document.createElement("b"); title.textContent = item.name;
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "Voir l’intention";
    const text = document.createElement("p"); text.textContent = item.intention;
    details.append(summary, text); intention.append(title, details);
    const promptCell = document.createElement("td"), imageCell = document.createElement("td"), output = document.createElement("td");
    const prompt = document.createElement("span"), image = document.createElement("span"), error = document.createElement("small");
    prompt.className = image.className = "cb-stage"; error.className = "cb-error";
    promptCell.append(prompt); imageCell.append(image, error);
    row.append(number, intention, promptCell, imageCell, output); el("rows").append(row);
    output.className = "cb-images"; row.classList.toggle("cb-child-row", Boolean(item.parent_id));
    const refs = {row, prompt, image, error, output, cards: new Map()}; state.rows.set(item.item_id, refs);
    return refs;
  }
  function renderBatch(batch) {
    if (!batch) return;
    if (state.batch?.batch_id === batch.batch_id && state.batch.revision > batch.revision) return;
    if (batch.statuses_only && state.batch?.batch_id === batch.batch_id) {
      const previous = new Map(state.batch.items.map(i => [i.item_id, i]));
      batch = {...batch, items: batch.items.map(i => ({...previous.get(i.item_id), ...i}))};
    }
    const changed = state.batch?.batch_id !== batch.batch_id;
    if (state.batch?.batch_id !== batch.batch_id) {
      state.rows.clear(); el("rows").replaceChildren(); hover.hidden = true;
      factoryMessage("");
    }
    state.batch = batch;
    if (changed && !batch.terminal && batch.config) {
      el("name").value = batch.name;
      el("recipe").value = batch.config.recipe_version;
      el("language").value = batch.config.language;
      el("inspiration").checked = batch.config.local_inspiration;
      if (![...el("preset").options].some(o => o.value === batch.config.preset_id))
        el("preset").append(new Option(batch.preset_name + " · copie du batch", batch.config.preset_id));
      el("preset").value = batch.config.preset_id;
      window.PanelForgeModelPicker.select(el("model"), batch.config.model_id);
      state.modelTouched = true;
      state.art = batch.config.art_direction; renderArt(); presetChanged(false);
    }
    setStored(storageKey, batch.batch_id);
    el("empty").hidden = true; el("table-wrap").hidden = false;
    el("title").textContent = batch.name;
    const c = batch.counts;
    el("count").textContent = `${c.finished}/${c.total} terminées · ${c.succeeded} réussies${c.failed ? ` · ${c.failed} en erreur` : ""}`;
    const ordered = [...batch.items].sort((a, b) => {
      const x = a.item_id.split(".").map(Number), y = b.item_id.split(".").map(Number);
      return x[0] - y[0] || (x[1] || 0) - (y[1] || 0);
    });
    for (const [index, item] of ordered.entries()) {
      const refs = state.rows.get(item.item_id) || addRow(item);
      if (el("rows").children[index] !== refs.row) el("rows").insertBefore(refs.row, el("rows").children[index] || null);
      stage(refs.prompt, item.prompt_status); stage(refs.image, item.image_status);
      refs.error.textContent = item.error || ""; refs.error.hidden = !item.error;
      refs.prompt.title = item.message || "";
      renderImages(refs, item);
    }
    updateControls();
  }
  function renderMonitoring(monitor) {
    state.monitor = monitor;
    for (const item of state.batch?.items || []) {
      const refs = state.rows.get(item.item_id), value = monitor[item.item_id];
      if (!refs || !value) continue;
      stage(refs.prompt, item.prompt_status, value.prompt);
      const images = Object.entries(value.images || {});
      const current = images.find(([, v]) => ["running", "submitting", "starting"].includes(v.status))
        || images.find(([, v]) => !["succeeded", "failed", "cancelled"].includes(v.status)) || images.at(-1);
      stage(refs.image, item.image_status, current?.[1] || {});
      for (const [id, tracking] of images) {
        const card = refs.cards.get(id); if (card) stage(card.status, tracking.status, tracking);
      }
    }
  }
  function workerMessage(text) {
    el("worker-error").textContent = text ? `Suivi du batch : ${text}` : "";
    el("worker-error").hidden = !text;
  }
  async function restoreBatch() {
    const pending = getStored(pendingKey);
    const id = pending ? "creation-batch-" + pending.replaceAll("-", "") : getStored(storageKey);
    let payload;
    try { payload = await request(id ? `${api}/batches/${encodeURIComponent(id)}` : api + "/current"); }
    catch (error) {
      if (error.status !== 404) throw error;
      if (pending) message("Le lancement précédent n’est pas confirmé. Rechargez son CSV pour réessayer avec le même identifiant.");
      payload = await request(api + "/current");
    }
    if (payload.batch) {
      renderBatch(payload.batch);
      renderMonitoring(payload.monitor || {});
      if (pending && payload.batch.batch_id === "creation-batch-" + pending.replaceAll("-", "")) setStored(pendingKey, null);
    }
    workerMessage(payload.worker_error);
  }
  function stopPolling() {
    clearTimeout(state.poll); state.poll = null;
    state.pollAbort?.abort(); state.pollAbort = null; hover.hidden = true;
  }
  function schedulePoll() {
    clearTimeout(state.poll);
    if (visible() && state.batch && (!state.batch.terminal || state.factorySending === state.batch.batch_id))
      state.poll = setTimeout(pollBatch, 2500);
  }
  async function pollBatch() {
    if (!visible() || !state.batch || state.pollAbort) return;
    const batchId = state.batch.batch_id;
    const controller = new AbortController(); state.pollAbort = controller;
    try {
      const payload = await request(`${api}/batches/${encodeURIComponent(batchId)}?known_revision=${state.batch.revision}&known_count=${state.batch.items.length}`, {signal: controller.signal});
      if (!visible() || controller.signal.aborted || state.batch?.batch_id !== batchId) return;
      if (payload.batch) renderBatch(payload.batch);
      renderMonitoring(payload.monitor || {});
      workerMessage(payload.worker_error);
    } catch (error) { if (error.name !== "AbortError") workerMessage(error.message); }
    finally { if (state.pollAbort === controller) state.pollAbort = null; schedulePoll(); }
  }
  async function launch(event) {
    event.preventDefault();
    if (state.submitting || state.importing || (state.batch && !state.batch.terminal) || !el("form").reportValidity()) return;
    const preset = state.presets.find(p => p.preset_id === el("preset").value);
    if (!preset || !state.intentions.length) return;
    if (!state.pending) {
      const requestId = getStored(pendingKey) || (crypto.randomUUID ? crypto.randomUUID() :
        "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (Number(c) ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> Number(c) / 4).toString(16)));
      state.pending = {request_id: requestId, name: el("name").value.trim(), intentions: state.intentions,
        model_id: el("model").value, recipe_version: el("recipe").value, language: el("language").value,
        local_inspiration: !el("inspiration").disabled && el("inspiration").checked,
        preset_id: preset.preset_id, preset_revision: preset.revision,
        art_style_id: el("recipe").value === "6.0.0" ? state.art?.style_id || null : null};
    }
    state.submitting = true; setStored(pendingKey, state.pending.request_id); message(""); updateControls();
    try {
      const payload = await request(api + "/batches", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(state.pending)});
      renderBatch(payload.batch); state.pending = null; setStored(pendingKey, null); schedulePoll();
    } catch (error) {
      if ([409, 422, 503].includes(error.status)) { state.pending = null; setStored(pendingKey, null); }
      message(error.message + (state.pending ? " · Cliquez à nouveau sur Lancer le batch pour vérifier ce même lancement." : ""));
    } finally { state.submitting = false; updateControls(); }
  }
  function renderStyles() {
    const query = el("art-search").value.trim().toLocaleLowerCase();
    const values = state.styles.filter(s => `${s.name} ${s.display_name || ""} ${s.category}`.toLocaleLowerCase().includes(query));
    el("art-grid").replaceChildren();
    el("art-state").textContent = values.length ? `${values.length} directions` : "Aucune direction disponible. Le catalogue se gère dans Création assistée.";
    for (const style of values) {
      const button = document.createElement("button"); button.type = "button";
      const img = document.createElement("img"); img.src = style.thumbnail_url; img.alt = ""; img.loading = "lazy";
      const title = document.createElement("span"); title.textContent = style.display_name || style.name;
      button.append(img, title); button.title = style.prompt;
      button.addEventListener("click", () => {
        const target = state.artTarget;
        el("art-dialog").close();
        if (target) imageAction(target.itemId, target.renderId, {kind: "art", art_style_id: style.style_id}, button);
        else { state.art = style; renderArt(); }
      });
      el("art-grid").append(button);
    }
  }
  async function refresh() {
    if (state.submitting || state.importing) return;
    message("");
    try {
      await loadResources(true);
      if (state.batch) {
        const payload = await request(`${api}/batches/${encodeURIComponent(state.batch.batch_id)}`);
        renderBatch(payload.batch); renderMonitoring(payload.monitor || {}); workerMessage(payload.worker_error);
      } else await restoreBatch();
      state.initialized = true; updateControls();
      schedulePoll();
    } catch (error) { message(error.message); }
  }
  async function activate() {
    if (!visible()) {
      stopPolling();
      if (root.hidden) [presetDialog, el("art-dialog"), el("image-dialog")].forEach(dialog => { if (dialog.open) dialog.close(); });
      return;
    }
    if (state.activating) return state.activating;
    if (!state.initialized) {
      state.activating = (async () => { await loadResources(); await restoreBatch(); state.initialized = true; })();
      try { await state.activating; }
      catch (error) { message(error.message); }
      finally { state.activating = null; updateControls(); }
    }
    schedulePoll();
  }
  el("file").addEventListener("change", importCsv);
  el("form").addEventListener("submit", launch);
  el("preset").addEventListener("change", () => presetChanged());
  el("recipe").addEventListener("change", updateControls);
  el("factory-all").addEventListener("click", sendAllToFactory);
  el("model").addEventListener("change", () => { state.modelTouched = true; updateControls(); });
  el("refresh").addEventListener("click", refresh);
  document.getElementById("krea2-assisted-preset-manager")?.addEventListener("close", () => {
    if (visible()) loadResources().catch(error => message(error.message));
  });
  el("art-clear").addEventListener("click", () => { state.art = null; renderArt(); });
  el("art-choose").addEventListener("click", () => chooseArt());
  el("art-search").addEventListener("input", renderStyles);
  el("art-close").addEventListener("click", () => el("art-dialog").close());
  el("image-close").addEventListener("click", () => el("image-dialog").close());
  el("image-dialog").addEventListener("close", () => el("image-full").removeAttribute("src"));
  document.addEventListener("visibilitychange", activate);
  new MutationObserver(activate).observe(root, {attributes: true, attributeFilter: ["hidden"]});
  activate();
})();
