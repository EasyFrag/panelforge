(() => {
  "use strict";
  const selections = new Map(), drafts = new Map(), knownJobs = new Map();
  const active = new Set(["queued", "starting", "submitting", "running", "receiving", "importing"]);
  const labels = { queued: "En attente", starting: "Démarrage de Comfy local", submitting: "Envoi à Comfy local", running: "Traitement DLSS", receiving: "Récupération du résultat", importing: "Enregistrement du résultat", succeeded: "Terminé", failed: "Erreur", unconfirmed: "À vérifier", cancelled: "Annulé" };
  const pending = new Map(), quickRequests = new Map(), inlinePanels = new Map(), unread = new Set();
  const videoEffects = Object.freeze({ intensity: 0.2, tone: 0, structure: 0.2, skin: 0, detail: 1, style: "Natural" });
  const videoOptions = Object.freeze({ ...videoEffects, size: "1.724", interpolate: true, hdr: false,
    strict_neural: false, codec: "H.264 (NVIDIA NVENC)" });
  const imageOptions = Object.freeze({ size: "1.5", interpolate: false, hdr: false, intensity: 1, tone: 1, structure: 1,
    skin: -1, detail: 1, style: "Default", strict_neural: false, codec: "H.264 (NVIDIA NVENC)" });
  const isVideo = value => ["h3", "ref2v"].includes(value?.owner);
  const rootKey = value => `${value.owner}:${value.ownerId}:${value.attempt.dlss?.root_attempt_id || value.attempt.attempt_id}`;
  const jobKey = job => `${job.snapshot.owner}:${job.snapshot.owner_id}:${job.snapshot.root_attempt_id}`;
  const requestId = () => globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  let context = null, epoch = 0, sending = false, polling = false, timer = null, previewTimer = null, previewReady = false, jobs = [];
  const request = async (url, body) => {
    const response = await fetch(url, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Erreur HTTP ${response.status}`);
    return data;
  };
  const dialog = document.createElement("dialog");
  dialog.className = "dlss-dialog";
  dialog.innerHTML = `<div class="dlss-head"><h2>Upscale DLSS</h2><button type="button" data-close aria-label="Fermer">×</button></div>
    <p data-target></p><div class="dlss-preview"></div>
    <form class="dlss-form"><div class="dlss-controls">
      <label>Taille de sortie<select name="size"><option value="source">Taille de la source · continuer l’étape</option><option value="1">×1 · taille native</option><option value="1.5">×1,5</option><option value="1.724">×1,724</option><option value="2">×2</option><option value="3">×3</option></select></label>
      <label data-video><input type="checkbox" name="interpolate"> Fluidifier à 60 FPS</label></div>
      <p data-dimensions aria-live="polite"></p><p data-size-note class="muted"></p>
      <details><summary>Réglages avancés</summary><div class="dlss-controls">
        <label>Style<select name="style"><option>Default</option><option>Natural</option><option>Cinematic</option></select></label>
        <label>Intensité NR<input name="intensity" type="number" min="0" max="2" step="0.1" value="1"></label>
        <label>Tonalité locale<input name="tone" type="number" min="0" max="2" step="0.1" value="1"></label>
        <label>Structure<input name="structure" type="number" min="0" max="2" step="0.1" value="1"></label>
        <label>Structure peau<input name="skin" type="number" min="-1" max="2" step="0.1" value="1"></label>
        <label>Détails de sortie<input name="detail" type="number" min="1" max="2" step="0.05" value="1"></label>
        <label><input name="strict_neural" type="checkbox"> Refuser le mode de repli</label>
        <label data-video>Encodage<select name="codec"><option>H.264 (NVIDIA NVENC)</option><option>H.264</option><option>H.265 (NVIDIA NVENC)</option></select></label>
        <label data-video><input name="hdr" type="checkbox"> Sortie HDR · source HDR uniquement</label>
      </div><p class="muted">Préréglages NR et modèle DLSS : Default · Masque automatique désactivé.</p>
      <button type="button" data-image data-reset-image>Réglages initiaux de l’image</button>
      <button type="button" data-video data-reset-video>Profil vidéo léger</button></details>
      <p data-error class="error-text" role="alert"></p><button data-start class="primary" type="submit">Lancer l’upscale</button>
    </form>
    <details class="dlss-runtime"><summary>Comfy local · <span data-runtime>état inconnu</span></summary>
      <div class="actions"><button type="button" data-control="free">Libérer la mémoire</button><button type="button" data-control="stop">Arrêter Comfy local</button><button type="button" data-control="restart">Redémarrer</button><a href="/api/dlss/runtime-log" target="_blank" rel="noopener">Journal local</a></div>
      <p class="muted">Comfy démarre au lancement d’un upscale. Unsloth reste chargé.</p><p data-runtime-note aria-live="polite"></p>
    </details><div class="dlss-jobs" aria-live="polite"></div>`;
  document.body.append(dialog);
  const $ = selector => dialog.querySelector(selector), form = $("form"), field = name => form.elements.namedItem(name);
  const imageComparison = window.PanelForgeDlssImageComparison?.setup({ dialog, onSelect: job => {
    selections.set(jobKey(job), job.candidate_id); unread.delete(job.job_id);
    window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: { ...job, select_result: true } }));
    if (dialog.open) close();
    updateBackground();
  } });
  const imageHelp = {
    size: "×1,5 (Quality) agrandit la largeur et la hauteur de 50 %. ×1 conserve les dimensions ; ×2 et ×3 agrandissent davantage. Dans Edit, Taille de la source retrouve les dimensions de l’étape et réapplique son masque.",
    style: "Choix de rendu du moteur : Default reprend son style standard ; Natural et Cinematic sont des variantes à comparer sur la même image. Le résultat dépend de l’image et du moteur.",
    intensity: "Force globale du rendu neuronal (NR), de 0 à 2. La valeur initiale est 1 ; monter vers 2 demande un traitement plus marqué. Ce réglage ne change pas la taille de l’image.",
    tone: "Force du traitement des tonalités locales, notamment les contrastes entre zones claires et sombres. Valeur initiale : 1 ; une valeur plus forte peut modifier davantage l’aspect de l’éclairage.",
    structure: "Force du traitement des structures et textures locales. Valeur initiale : 1. Une valeur plus forte peut transformer davantage les textures ; elle ne garantit pas plus de fidélité à l’original.",
    skin: "Force de structure dédiée à la peau. −1 conserve le comportement natif du moteur : ce n’est pas une intensité négative. Les valeurs de 0 à 2 imposent une force explicite ; leur effet dépend du traitement et du masquage du moteur.",
    detail: "À 1, conserve la sortie du moteur sans amplification supplémentaire. Au-dessus de 1, amplifie les écarts de luminosité entre la source et le résultat. Ce contrôle ne lance pas une seconde passe neuronale.",
    strict_neural: "Décoché par défaut : accepte le mode de repli si l’agrandissement neuronal n’est pas actif. Coché : le traitement échoue dans ce cas. Cette option contrôle l’acceptation du résultat, pas la force de l’effet."
  };
  Object.entries(imageHelp).forEach(([name, text]) => {
    const label = field(name).closest("label");
    const title = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    const wrapper = document.createElement("div"); wrapper.className = "dlss-field";
    label.before(wrapper); wrapper.append(label);
    const info = document.createElement("button"), help = document.createElement("span");
    info.type = "button"; info.textContent = "i"; info.className = "dlss-help-button"; info.dataset.image = "";
    info.title = text;
    info.setAttribute("aria-label", `À propos de ${title.textContent.trim()}`);
    info.setAttribute("aria-expanded", "false"); info.setAttribute("aria-controls", `dlss-help-${name}`);
    help.id = `dlss-help-${name}`; help.className = "dlss-field-help"; help.textContent = text; help.hidden = true;
    info.addEventListener("click", event => {
      event.preventDefault(); event.stopPropagation(); help.hidden = !help.hidden;
      info.setAttribute("aria-expanded", String(!help.hidden));
    });
    wrapper.append(info); label.append(help);
  });
  const serviceButton = document.createElement("button");
  serviceButton.type = "button"; serviceButton.className = "runtime-button"; serviceButton.textContent = "DLSS local";
  document.querySelector(".runtime-maintenance")?.append(serviceButton);
  serviceButton.addEventListener("click", () => open(null));
  const settings = () => Object.fromEntries(["size", "style", "codec", "intensity", "tone", "structure", "skin", "detail", "strict_neural", "interpolate", "hdr"].map(name => {
    const element = field(name);
    return [name, element.type === "checkbox" ? element.checked : element.type === "number" ? Number(element.value) : element.value];
  }));
  const payload = () => ({ owner: context.owner, owner_id: context.ownerId, attempt_id: context.attempt.attempt_id, settings: settings() });
  const draftKey = () => context ? `${context.owner}:${context.ownerId}:${context.attempt.attempt_id}` : null;
  function remember() { if (context) drafts.set(draftKey(), { settings: settings(), requests: context.requests, comparison: imageComparison?.draft() }); }
  async function open(value) {
    if (sending) return;
    remember(); epoch += 1; context = value ? { ...value, requests: new Map() } : null;
    $("[data-error]").textContent = ""; $(".dlss-preview").replaceChildren();
    form.hidden = !context; $("[data-target]").textContent = context ? context.attempt.label || `Essai ${context.attempt.index || ""}` : "Moteur local et tâches DLSS";
    if (context) {
      const saved = drafts.get(draftKey());
      imageComparison?.restore(context, saved?.comparison);
      context.requests = saved?.requests || new Map();
      const video = ["h3", "ref2v"].includes(context.owner);
      const defaults = video ? videoOptions : imageOptions;
      Object.entries(saved?.settings || defaults).forEach(([name, v]) => { if (field(name).type === "checkbox") field(name).checked = v; else field(name).value = v; });
      field("size").querySelector('[value="source"]').hidden = context.owner !== "edit";
      dialog.querySelectorAll("[data-video]").forEach(e => { e.hidden = !video; });
      dialog.querySelectorAll("[data-image]").forEach(e => { e.hidden = video; });
      dialog.querySelectorAll(".dlss-field-help").forEach(e => { e.hidden = true; });
      dialog.querySelectorAll(".dlss-help-button").forEach(e => e.setAttribute("aria-expanded", "false"));
      const media = document.createElement(video ? "video" : "img");
      media.src = context.attempt.output_url; if (video) { media.controls = true; media.preload = "metadata"; } else media.alt = "Résultat sélectionné";
      $(".dlss-preview").append(media); preview();
    }
    if (!dialog.open) dialog.showModal();
    renderJobs(); runtime(); poll();
  }
  function close() { if (sending && !isVideo(context) && !imageComparison?.batch()) return; remember(); epoch += 1; clearTimeout(previewTimer); dialog.close(); }
  $("[data-close]").addEventListener("click", close);
  dialog.addEventListener("cancel", e => { e.preventDefault(); close(); });
  form.addEventListener("input", event => {
    if (event.target.closest?.(".dlss-image-presets")) {
      remember(); $("[data-start]").disabled = sending || !previewReady || !imageComparison.valid(); return;
    }
    remember(); previewReady = false; $("[data-start]").disabled = true; epoch += 1;
    clearTimeout(previewTimer); previewTimer = setTimeout(preview, 350);
  });
  $("[data-reset-image]").addEventListener("click", () => {
    if (!context || isVideo(context) || sending) return;
    Object.entries(imageOptions).forEach(([name, value]) => {
      if (field(name).type === "checkbox") field(name).checked = value; else field(name).value = value;
    });
    form.dispatchEvent(new Event("input", { bubbles: true }));
  });
  $("[data-reset-video]").addEventListener("click", () => {
    if (!isVideo(context) || sending) return;
    Object.entries(videoEffects).forEach(([name, value]) => { field(name).value = value; });
    form.dispatchEvent(new Event("input", { bubbles: true }));
  });
  async function preview() {
    if (!context) return;
    const current = ++epoch; previewReady = false; $("[data-start]").disabled = true;
    $("[data-dimensions]").textContent = "Lecture des dimensions…";
    $("[data-size-note]").textContent = context.owner === "edit" ? (field("size").value === "source"
      ? "Le masque est réappliqué ; les pixels de la source hors masque sont conservés."
      : "Finition : toute l’image sélectionnée est traitée, y compris les zones issues de la source.") : "Une variante sera enregistrée à côté de l’original.";
    try {
      const data = await request("/api/dlss/preview", payload());
      if (current !== epoch) return;
      if (!isVideo(context)) imageComparison?.applyPreview(data);
      $("[data-dimensions]").textContent = `${data.input_metadata.width} × ${data.input_metadata.height} → ${data.output_dimensions.join(" × ")}`;
      if (context.attempt.dlss) $("[data-size-note]").textContent += " La nouvelle variante repart de l’original, sans empiler les passes DLSS.";
      $("[data-error]").textContent = ""; previewReady = true; $("[data-start]").disabled = sending || (imageComparison && !imageComparison.valid());
    } catch (error) { if (current === epoch) { $("[data-error]").textContent = error.message; $("[data-dimensions]").textContent = ""; } }
  }
  form.addEventListener("submit", async event => {
    event.preventDefault(); if (!context || sending || !previewReady || !form.reportValidity()) return;
    if (!isVideo(context) && imageComparison?.batch()) { await submitImageComparison(); return; }
    const body = payload(), key = JSON.stringify(body);
    if (!context.requests.has(key)) context.requests.set(key, requestId());
    body.request_id = context.requests.get(key); remember(); sending = true;
    const source = context, video = isVideo(source);
    if (video) { pending.set(rootKey(source), { sending: true, error: "" }); updateBackground(); }
    form.querySelectorAll("input,select,button").forEach(e => { e.disabled = true; });
    try {
      const job = await request("/api/dlss/jobs", body);
      trackQueued(job);
      if (video) { pending.delete(rootKey(source)); close(); }
      $("[data-error]").textContent = ""; await poll();
    } catch (error) {
      $("[data-error]").textContent = error.message;
      if (video) pending.set(rootKey(source), { sending: false, error: error.message });
    }
    finally { sending = false; form.querySelectorAll("input,select,button").forEach(e => { e.disabled = false; }); updateBackground(); }
  });

  async function submitImageComparison() {
    if (!imageComparison.valid()) return;
    const source = context, body = { ...payload(), preset_ids: imageComparison.batch() };
    const key = JSON.stringify(body);
    if (!source.requests.has(key)) source.requests.set(key, requestId());
    body.request_id = source.requests.get(key); remember(); sending = true;
    pending.set(rootKey(source), { sending: true, error: "" }); updateBackground();
    form.querySelectorAll("input,select,button").forEach(e => { e.disabled = true; });
    close();
    try {
      const data = await request("/api/dlss/image-comparisons", body);
      data.jobs.forEach(trackQueued); pending.delete(rootKey(source)); await poll();
    } catch (error) {
      pending.set(rootKey(source), { sending: false, error: `${error.message} Rouvre Upscale DLSS et relance la même sélection pour reprendre l’envoi sans doublon.` });
      $("[data-error]").textContent = error.message;
    } finally {
      sending = false; form.querySelectorAll("input,select,button").forEach(e => { e.disabled = false; });
      imageComparison.applyPreview({ image_presets: [] }); previewReady = false;
      updateBackground();
    }
  }

  function trackQueued(job) {
    if (!knownJobs.has(job.job_id)) {
      knownJobs.set(job.job_id, "queued");
      window.PanelForgeLabCore?.observeRenderOutcome?.(`dlss:${job.job_id}`, "queued");
    }
    jobs = [...jobs.filter(j => j.job_id !== job.job_id), job];
    updateBackground();
  }
  async function quick(value) {
    const scope = rootKey(value);
    if (pending.get(scope)?.sending || jobs.some(j => jobKey(j) === scope && active.has(j.status))) return;
    const body = { owner: value.owner, owner_id: value.ownerId,
      attempt_id: value.attempt.dlss?.root_attempt_id || value.attempt.attempt_id, settings: { ...videoOptions } };
    const key = JSON.stringify(body);
    if (!quickRequests.has(key)) quickRequests.set(key, requestId());
    body.request_id = quickRequests.get(key);
    pending.set(scope, { sending: true, error: "" }); updateBackground();
    try {
      const job = await request("/api/dlss/jobs", body);
      pending.delete(scope); trackQueued(job); await poll();
    } catch (error) { pending.set(scope, { sending: false, error: error.message }); }
    updateBackground();
  }

  function jobText(job) {
    const progress = job.status === "running" ? job.progress : null;
    const age = progress?.updated_at ? Date.now() - Date.parse(progress.updated_at) : 0;
    const percent = Number.isFinite(progress?.percent) ? Math.round(progress.percent) : null;
    const copying = ["queued", "copying"].includes(job.video_export?.status);
    const label = copying ? "Vidéo prête · copie serveur" : progress?.label || labels[job.status] || job.status;
    const from = Date.parse(job.started_at || job.created_at), until = Date.parse(job.finished_at || "") || Date.now();
    const seconds = Number.isFinite(from) ? Math.max(0, Math.floor((until - from) / 1000)) : 0;
    return `${label}${percent === null ? "" : ` · ${percent} %`}${age > 15000 ? " · en attente d’une mise à jour" : ""} · ${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s`;
  }
  function renderJob(job, { inline = false } = {}) {
    const item = document.createElement("article"); item.className = "dlss-job";
    const text = document.createElement("p"); text.className = "dlss-progress-label";
    text.textContent = jobText(job); item.append(text);
    const size = document.createElement("small");
    size.textContent = `${job.comparison ? job.comparison.label + " · " : ""}${job.settings.size === "source" ? "Taille source" : "×" + job.settings.size}${job.settings.interpolate ? " · 60 FPS" : ""}`; item.append(size);
    if (job.comparison) {
      const summary = document.createElement("p"); summary.textContent = imageComparison?.groupSummary(job) || ""; item.append(summary);
      const details = document.createElement("details"), title = document.createElement("summary"), params = document.createElement("p");
      title.textContent = "Réglages"; params.textContent = imageComparison?.describe(job.settings) || ""; details.append(title, params); item.append(details);
    }
    if (job.status === "running" && Number.isFinite(job.progress?.percent)) {
      const bar = document.createElement("progress"); bar.max = 100; bar.value = job.progress.percent;
      bar.setAttribute("aria-label", job.progress.label); item.append(bar);
    }
    const note = document.createElement("p"); note.textContent = job.error || (job.warnings || []).join(" · "); item.append(note);
    const actions = document.createElement("div"); actions.className = "dlss-job-actions"; item.append(actions);
    if (imageComparison && !job.snapshot.media_type.startsWith("video") && job.status === "succeeded") {
      actions.append(imageComparison.button({ owner: job.snapshot.owner, ownerId: job.snapshot.owner_id,
        preferredJobId: job.job_id, attempt: { attempt_id: job.snapshot.root_attempt_id } }));
    }
    for (const [url, label, extension] of [[job.output_url, "Télécharger", job.snapshot.media_type.startsWith("video") ? "mp4" : "png"], [job.report_url, "Diagnostic", "json"]]) {
      if (url) { const link = document.createElement("a"); link.href = url; link.textContent = label; link.download = `${job.job_id}.${extension}`; actions.append(link); }
    }
    function command(label, action) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = label;
      button.addEventListener("click", async () => {
        button.disabled = true;
        try { await request(`/api/dlss/jobs/${job.job_id}/${action}`, {}); await poll(); }
        catch (error) { note.textContent = error.message; button.disabled = false; }
      }); actions.append(button); return button;
    }
    if (["failed", "unconfirmed", "cancelled"].includes(job.status)) command("Reprendre cette tâche", "retry");
    if ((active.has(job.status) && !["receiving", "importing"].includes(job.status)) || job.status === "failed") {
      command(job.cancel_requested ? "Annulation demandée" : "Annuler", "cancel").disabled = Boolean(job.cancel_requested);
    }
    if ((inline || (dialog.open && context?.owner === job.snapshot.owner && context?.ownerId === job.snapshot.owner_id)) && job.status === "succeeded" && job.candidate_id) {
      const view = document.createElement("button"); view.type = "button"; view.textContent = "Voir le résultat";
      view.addEventListener("click", () => {
        selections.set(jobKey(job), job.candidate_id); unread.delete(job.job_id);
        window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: { ...job, select_result: true } }));
        if (dialog.open) close(); updateBackground();
      }); actions.append(view);
    }
    const exported = job.video_export;
    if (job.local_output_path) {
      const location = document.createElement("p"); location.className = "dlss-export";
      location.textContent = `Fichier local : ${job.local_output_path}`; item.append(location);
    }
    if (exported) {
      const copy = document.createElement("p"); copy.className = "dlss-export";
      copy.textContent = exported.status === "succeeded" ? `Copiée sur le serveur : ${exported.path}`
        : exported.status === "failed" ? `Vidéo disponible ici ; copie serveur à reprendre : ${exported.error}` : "Copie vers le serveur en cours…";
      item.append(copy);
      if (exported.status === "failed") command("Réessayer la copie", "export");
    }
    return item;
  }
  function updateBackground() {
    imageComparison?.refresh(jobs);
    for (const [panel, value] of inlinePanels) {
      if (!panel.isConnected) { inlinePanels.delete(panel); continue; }
      const scope = rootKey(value), items = jobs.filter(j => jobKey(j) === scope);
      panel.replaceChildren();
      const waiting = pending.get(scope);
      if (waiting) { const p = document.createElement("p"); p.textContent = waiting.sending ? "Préparation de l’upscale… Tu peux continuer à travailler." : waiting.error; panel.append(p); }
      const visible = [...items.filter(j => active.has(j.status)), ...items.filter(j => !active.has(j.status)).slice(-1)];
      visible.forEach(j => panel.append(renderJob(j, { inline: true })));
      panel.hidden = !waiting && !visible.length;
    }
    document.querySelectorAll("[data-dlss-quick]").forEach(button => {
      button.disabled = Boolean(pending.get(button.dataset.dlssQuick)?.sending || jobs.some(j => jobKey(j) === button.dataset.dlssQuick && active.has(j.status)));
    });
    const errors = [...pending.entries()].filter(([, v]) => !v.sending && v.error);
    for (const [key, value] of errors) {
      window.PanelForgeWorkQueue?.notice(value.error, {id: `dlss:${key}`});
    }
    window.dispatchEvent(new CustomEvent("panelforge:dlss-update"));
  }
  function progress(value) {
    const scope = rootKey(value), waiting = pending.get(scope);
    if (waiting) return {status: waiting.sending ? "starting" : "failed",
      label: waiting.sending ? "Préparation" : "Erreur", error: waiting.error};
    const items = jobs.filter(job => jobKey(job) === scope);
    const job = items.filter(job => active.has(job.status)).at(-1) || items.at(-1);
    return job ? {status: job.status, label: labels[job.status] || job.status, error: job.error} : null;
  }
  function inlineStatus(value) {
    const panel = document.createElement("section"); panel.className = "dlss-inline"; panel.hidden = true;
    panel.setAttribute("aria-label", "Suivi DLSS de cet essai"); inlinePanels.set(panel, value);
    queueMicrotask(updateBackground); return panel;
  }
  async function runtime() {
    try {
      const value = await request("/api/dlss/runtime");
      $("[data-runtime]").textContent = ({ ready: "prêt", stopped: "arrêté", error: "erreur" })[value.state] || value.state;
      $("[data-runtime-note]").textContent = value.error || (value.state === "ready" && !value.owned ? "Instance ouverte manuellement : nettoyage disponible, arrêt depuis son lanceur." : "");
      dialog.querySelectorAll("[data-control]").forEach(button => { button.disabled = jobs.some(j => active.has(j.status)) || (button.dataset.control !== "free" && !value.owned); });
    } catch (error) { $("[data-runtime-note]").textContent = error.message; }
  }
  dialog.querySelectorAll("[data-control]").forEach(button => button.addEventListener("click", async () => {
    dialog.querySelectorAll("[data-control]").forEach(b => { b.disabled = true; });
    try {
      await request(`/api/dlss/runtime/${button.dataset.control}`, {});
      await runtime();
      if (button.dataset.control === "free") $("[data-runtime-note]").textContent = "Nettoyage demandé. Comfy peut conserver une partie de sa mémoire GPU.";
    } catch (error) { await runtime(); $("[data-runtime-note]").textContent = error.message; }
  }));
  function renderJobs() {
    const panel = $(".dlss-jobs"); panel.replaceChildren();
    const scoped = jobs.filter(j => !context || (j.snapshot.owner === context.owner && j.snapshot.owner_id === context.ownerId));
    const values = [...scoped.filter(j => active.has(j.status)), ...scoped.filter(j => !active.has(j.status)).slice(-12).reverse()];
    for (const job of values) {
      panel.append(renderJob(job));
    }
  }
  async function poll() {
    if (polling) return;
    polling = true;
    clearTimeout(timer);
    try {
      const data = await request("/api/dlss/jobs"); jobs = data.jobs;
      for (const job of jobs) {
        window.PanelForgeLabCore?.observeRenderOutcome?.(`dlss:${job.job_id}`, active.has(job.status) ? "running" : job.status);
        if (job.status === "succeeded" && knownJobs.has(job.job_id) && knownJobs.get(job.job_id) !== "succeeded") {
          unread.add(job.job_id);
          if (!job.snapshot.media_type.startsWith("video") && !job.comparison) {
            selections.set(jobKey(job), job.candidate_id);
            window.dispatchEvent(new CustomEvent("panelforge:dlss-complete", { detail: job }));
          }
        }
        knownJobs.set(job.job_id, job.status);
      }
      const count = jobs.filter(j => active.has(j.status)).length; serviceButton.textContent = count ? `DLSS · ${count} tâche${count > 1 ? "s" : ""}` : "DLSS local";
      if (dialog.open) { renderJobs(); runtime(); }
      updateBackground();
    } catch (error) {
      if (dialog.open) $("[data-error]").textContent = error.message;
      window.PanelForgeWorkQueue?.notice(`Suivi DLSS indisponible : ${error.message}`, {id: "dlss:poll"});
    }
    polling = false;
    timer = setTimeout(poll, jobs.some(j => active.has(j.status) || ["queued", "copying"].includes(j.video_export?.status)) || dialog.open ? 2500 : 15000);
  }
  function groups(attempts, scope, preferredId = null) {
    return attempts.filter(a => !a.dlss).map(root => {
      const variants = [root, ...attempts.filter(a => a.dlss?.root_attempt_id === root.attempt_id)];
      const key = `${scope}:${root.attempt_id}`;
      const preferred = variants.find(a => a.attempt_id === preferredId);
      const attempt = variants.find(a => a.attempt_id === selections.get(key)) || preferred || root;
      return { root, variants, attempt, key };
    });
  }
  function picker(group, onChange) {
    const select = document.createElement("select"); select.className = "dlss-variant-picker"; select.setAttribute("aria-label", "Version du résultat");
    group.variants.forEach((v, i) => {
      const label = jobs.find(j => j.job_id === v.dlss?.job_id)?.comparison?.label;
      select.add(new Option(i ? `${label || `DLSS ${i}`} · ${v.dlss.width} × ${v.dlss.height}` : "Original", v.attempt_id));
    });
    select.value = group.attempt.attempt_id; select.hidden = group.variants.length < 2;
    select.addEventListener("change", () => { selections.set(group.key, select.value); onChange(select.value); }); return select;
  }
  function button(value, { advanced = false } = {}) {
    const button = document.createElement("button"); button.type = "button"; button.textContent = "Upscale DLSS";
    if (isVideo(value) && !advanced) {
      button.title = "Lancer en arrière-plan · ×1,724 · 60 FPS"; button.dataset.dlssQuick = rootKey(value);
      button.addEventListener("click", () => quick(value));
    } else {
      if (advanced) button.textContent = "Upscale avancé";
      button.addEventListener("click", () => open(value));
    }
    return button;
  }
  window.PanelForgeDlss = Object.freeze({ open, button, groups, picker, inlineStatus, progress,
    comparisonButton: value => imageComparison?.button(value) || document.createElement("span") });
  poll();
})();
