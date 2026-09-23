(() => {
  "use strict";
  const core = window.PanelForgeLabCore, picker = window.PanelForgeModelPicker, resources = window.PanelForgeKrea2ResourceUi;
  const root = document.getElementById("episode-workshop"), el = id => document.getElementById(`episode-${id}`);
  if (!root || !core || !picker || !resources || !window.PanelForgeH3Render) return;
  const state = { story: null, data: null, list: [], refId: "", sceneId: "", prepId: "", tab: "references",
    models: [], catalog: null, imageProject: null, busy: false, token: 0, timer: null,
    dirtyRef: false, dirtyScene: false, dirtyCommon: false, inheritImages: true, loras: [], commonLoras: [], presets: [],
    batchProfiles: {character: {loras: [], sampling: null, inheritTechnical: true}, location: {loras: [], sampling: null, inheritTechnical: true}},
    batchSelection: new Set(), batchProfileKey: "", batchThermalKey: "",
    renderContext: "", renderSaves: Promise.resolve(), renderRevision: new Map(), dlssPanels: new Map(),
    videoCards: new Map(), cooldownTicker: null };
  const axesIds = {scene_life: "creative-scene-life", camera: "creative-camera", extra_motion: "creative-extra-motion", dialogue: "creative-dialogue"};
  const initialAxes = {scene_life: 3, camera: 3, extra_motion: 3, dialogue: 1};
  const roles = {subject_reference: "Sujet / identité", environment_reference: "Décor", style_reference: "Style",
    composition_reference: "Composition", motion_reference: "Mouvement", keyframe_reference: "Keyframe", first_frame: "Première frame", last_frame: "Dernière frame"};
  const statuses = {ready: "Prompt prêt", running: "En cours", succeeded: "Terminé", failed: "Échec", interrupted: "À reprendre",
    queued: "En file", submitting: "Démarrage", cancel_pending: "Annulation", cancelled: "Annulé", created: "Prêt"};
  const deliveryLabels = {spoken: "", voice_over: "voix off", off_screen: "hors champ",
    thought: "pensée / voix intérieure", mediated: "voix transmise"};
  const dialogueLabel = (line, speaker) => {
    const indication = line.delivery_note || deliveryLabels[line.delivery || "spoken"];
    return `${speaker}${indication ? ` — ${indication}` : ""} : « ${line.text} »`;
  };
  const ref = () => state.data?.references.find(r => r.id === state.refId);
  const activeReferences = () => (state.data?.references || []).filter(r => !r.continuity_archived);
  const kindLabel = kind => ({character: "Personnage", location: "Décor", object: "Objet"}[kind] || kind);
  const scene = () => state.data?.scenes.find(s => s.id === state.sceneId);
  const prep = () => scene()?.preparations.find(p => p.id === state.prepId);
  const api = (suffix = "", id = state.data?.episode_id) => `/api/episodes/${encodeURIComponent(id)}${suffix}`;
  const send = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const node = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, action) => { const b = node("button", text); b.type = "button"; b.addEventListener("click", action); return b; };
  const assetUrl = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const jobRunning = item => item?.job?.status === "running";
  const renderDuration = value => value.effective_render_setup?.settings?.duration_seconds ?? value.render_setup?.settings?.duration_seconds ?? value.duration;
  const promptActivity = value => {
    const stages = value?.preparations?.at(-1)?.prompt_stages || {};
    const active = ["plan", "writer"].find(stage => ["starting", "running"].includes(stages[stage]));
    return active ? `${active === "plan" ? "Plan" : "Rédacteur"} · ${stages[active] === "starting" ? "démarrage" : "en cours"}`
      : "Planifié · en attente du LLM";
  };
  const batchRunning = () => ["running", "rendering", "cancelling"].includes(state.data?.reference_batch?.status);
  const videoRecoveryRunning = () => state.data?.scenes?.some(value => jobRunning(value)
    || ["queued", "running", "cancel_pending"].includes(value.video_status));
  const videoChainRunning = () => ["running", "pausing"].includes(state.data?.video_chain?.status)
    || videoRecoveryRunning();
  const imageRunning = () => state.imageProject?.attempts.some(a => ["queued", "submitting", "running", "cancel_pending"].includes(a.status));
  const knownModel = id => state.models.some(m => m.id === id);
  const memo = { get(key) { try { return localStorage.getItem(`panelforge.episodes.${key}`); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(`panelforge.episodes.${key}`, value); } catch (_) {} } };
  function message(text, error = false) { el("message").textContent = text; el("message").classList.toggle("error", error); }
  function storeContext() {
    if (state.data) memo.set(state.data.story_id, JSON.stringify({id: state.data.episode_id, tab: state.tab, ref: state.refId, scene: state.sceneId}));
  }
  function show(visible) {
    root.hidden = !visible; document.getElementById("story-writing").hidden = visible;
    document.querySelectorAll("#stories-workspace .story-model-control").forEach(control => { control.hidden = visible; });
    if (!visible) { clearTimeout(state.timer); renderer.close(); state.renderContext = ""; }
  }
  async function action(work) {
    if (state.busy) return;
    state.busy = true; controls();
    try { await work(); }
    catch (error) {
      if (state.data) { el("scene").value = state.sceneId; el("versions").value = state.data.episode_id; }
      message(error.message, true);
    }
    finally { state.busy = false; controls(); schedule(); }
  }
  function controls() {
    drawContinuity();
    const r = ref(), s = scene(), continuityBusy = state.data?.continuity_version === 1
      && (videoChainRunning() || batchRunning() || state.data.references.some(jobRunning));
    const busyRef = state.busy || jobRunning(r) || continuityBusy, busyScene = state.busy || jobRunning(s);
    for (const id of ["story-projects", "story-new", "story-fabrication"]) document.getElementById(id).disabled = state.busy;
    document.getElementById("story-validate").disabled = state.busy || !state.story?.document?.scenario
      || (state.story?.narrative_engine?.version === "2.0.0" && !state.story?.long_status?.fabrication_ready)
      || ["running", "cancelling"].includes(state.story?.job?.status);
    for (const id of ["description", "asset-model", "asset-local", "asset-feedback", "asset-text", "image-workflow", "image-model", "image-ratio", "image-mp", "image-seed", "image-preset", "image-import", "save-reference", "image-toggle-settings"])
      el(id).disabled = busyRef || !r;
    for (const id of ["style", "style-preset", "common-workflow", "common-model", "common-preset", "style-import", "save-style", "apply-preset", "refresh-presets"])
      el(id).disabled = state.busy || !state.data;
    el("style-use-reference").disabled = state.busy || !r?.image_asset_id;
    el("style-remove").disabled = state.busy || !state.data?.style_image;
    el("asset-prompt").disabled = busyRef || !r || !knownModel(el("asset-model").value);
    el("image-render").disabled = busyRef || !r || imageRunning() || !el("asset-text").value.trim()
      || !(state.catalog?.render_models || []).some(m => m.comfy_name === imageSettings().model_id);
    for (const id of ["intention", "duration", "plan-model", "writer-model", "plan-local", "writer-local", "shots", "audacity", ...Object.values(axesIds), "add-reference", "save-scene"])
      el(id).disabled = busyScene || !s;
    el("prepare").disabled = busyScene || !s || !knownModel(el("plan-model").value) || !knownModel(el("writer-model").value);
    el("add").disabled = busyScene || !el("add-reference").value || (state.bindings?.length || 0) >= 9;
    el("resume").hidden = !s?.preparations.length || !["failed", "interrupted"].includes(s.preparations.at(-1).status) || s.stale;
    el("resume").disabled = busyScene || state.dirtyScene;
    el("scene-calls").hidden = !prep()?.session_id;
    el("image-attempts").querySelectorAll("button[data-image-choice]").forEach(button => {
      button.disabled = state.busy || jobRunning(r) || button.dataset.selected === "true";
    });
    el("scene-references").querySelectorAll("button,select").forEach(n => { n.disabled = busyScene; });
    el("batch-panel").querySelectorAll("select,input").forEach(n => { n.disabled = state.busy || batchRunning(); });
    for (const kind of ["character", "location"]) el(`batch-${kind}-toggle`).disabled = state.busy || batchRunning();
    el("batch-start").disabled = state.busy || batchRunning() || !state.catalog || !state.models.length || !state.batchSelection.size;
    el("batch-cancel").hidden = !batchRunning();
    el("batch-cancel").disabled = state.busy || state.data?.reference_batch?.status === "cancelling";
    const chain = state.data?.video_chain, chainStatus = chain?.status;
    el("video-start").disabled = state.busy || videoChainRunning() || !state.data?.scenes?.length;
    el("video-pause").hidden = chainStatus !== "running";
    el("video-pause").disabled = state.busy;
    el("video-drain").hidden = chainStatus !== "running";
    el("video-drain").disabled = state.busy;
    el("video-resume").hidden = !["paused", "interrupted", "failed", "completed_with_errors"].includes(chainStatus);
    const incomplete = chain?.items?.filter(item => item.status !== "succeeded").length || 0;
    el("video-resume").textContent = chainStatus === "completed_with_errors"
      ? `Relancer les scènes incomplètes${incomplete ? ` (${incomplete})` : ""}` : "Reprendre la chaîne";
    el("video-resume").disabled = state.busy || videoRecoveryRunning();
    el("video-settings-toggle").disabled = state.busy || videoChainRunning() || !s;
    drawLoras();
    drawBatchLoras();
    renderer.refreshControls?.();
  }
  function fillModel(id, value) {
    const select = el(id);
    picker.populate(select, state.models, value);
    if (value) picker.select(select, value);
  }
  async function catalog(refresh = false) {
    el("catalog-message").textContent = "Lecture du catalogue…";
    const results = await Promise.allSettled([
      core.request(`/api/image-lab/krea2-assisted/spec${refresh ? "?refresh=true" : ""}`), core.request("/api/stories/models"),
      core.request("/api/image-lab/krea2-assisted/style-presets")]);
    if (results[1].status === "fulfilled") {
      state.models = results[1].value.models;
      fillModel("asset-model", state.dirtyRef ? el("asset-model").value : ref()?.model_id);
      fillModel("plan-model", state.dirtyScene ? el("plan-model").value : scene()?.plan_model_id);
      fillModel("writer-model", state.dirtyScene ? el("writer-model").value : scene()?.writer_model_id);
      hydrateBatchProfiles(true);
    }
    if (results[0].status === "fulfilled") {
      const current = state.dirtyRef ? imageSettings() : ref()?.effective_image_settings;
      state.catalog = results[0].value;
      drawVisual(); drawImageSettings(current); hydrateBatchProfiles(true);
    }
    if (results[2].status === "fulfilled") { state.presets = results[2].value.presets; drawStylePresets(); }
    el("catalog-message").textContent = results.filter(r => r.status === "rejected").map(r => r.reason.message).join(" · ") || "Catalogue chargé.";
    controls();
  }
  function modelPicker(id, selected) {
    const select = el(id), models = state.catalog?.render_models || [];
    resources.renderModelPicker(select, {resources: models, updatePreference, refreshResource});
    const chosen = selected || models.find(m => /krea2_turbo_bf16/i.test(m.comfy_name))?.comfy_name || models[0]?.comfy_name || "";
    if (chosen && ![...select.options].some(o => o.value === chosen)) select.add(new Option(`${chosen} · indisponible`, chosen));
    select.value = chosen; resources.syncModelPicker(select);
  }
  function drawSampling(id, saved) {
    const select = el(id), presets = state.catalog?.sampling.presets || [];
    select.replaceChildren(...presets.map(p => new Option(p.label, p.id)));
    const chosen = saved?.preset_id || "current";
    if (chosen && ![...select.options].some(o => o.value === chosen)) select.add(new Option("Personnalisé · réglages conservés", chosen));
    select.value = chosen;
  }
  const workflowKey = value => typeof value === "string" ? value
    : value?.recipe_id && value?.version ? `${value.recipe_id}@${value.version}` : "krea2-sampling@1.0.0";
  function drawWorkflow(id, saved) {
    const select = el(id), workflows = state.catalog?.workflows || [];
    select.replaceChildren(...workflows.map(workflow => new Option(workflow.label, workflow.id)));
    const chosen = workflowKey(saved);
    if (chosen && ![...select.options].some(option => option.value === chosen)) select.add(new Option(`${chosen} · indisponible`, chosen));
    select.value = chosen;
  }
  function commonSettings() {
    return {workflow: el("common-workflow").value, model_id: el("common-model").value, loras: structuredClone(state.commonLoras),
      sampling: state.catalog?.sampling.presets.find(p => p.id === el("common-preset").value)?.settings || state.commonSampling};
  }
  function drawVisual() {
    if (!state.data) return;
    if (!state.dirtyCommon) {
      const common = state.data.image_defaults;
      el("style").value = state.data.style; state.commonLoras = structuredClone(common?.loras || []);
      state.commonSampling = common?.sampling;
      if (state.catalog) { drawWorkflow("common-workflow", common?.workflow); modelPicker("common-model", common?.model_id); drawSampling("common-preset", common?.sampling); }
    }
    const img = state.data.style_image;
    el("style-preview").hidden = !img;
    if (img) el("style-preview").src = assetUrl(img.asset_id); else el("style-preview").removeAttribute("src");
    el("style-image-name").textContent = img?.filename || "Aucune image de style.";
    el("visual-status").textContent = state.dirtyCommon ? "Modifications à enregistrer" : "Enregistré";
    drawStylePresets();
  }
  function drawStylePresets() {
    const selected = el("style-preset").value, active = state.data?.style_preset;
    const select = el("style-preset");
    select.replaceChildren(new Option("Style personnalisé", ""));
    for (const [category, label] of [["work", "Work"], ["fun", "Fun"], ["nsfw", "NSFW"], ["archive", "Archive"]]) {
      const presets = state.presets.filter(p => (p.category || "work") === category);
      if (!presets.length) continue;
      const group = document.createElement("optgroup"); group.label = label;
      presets.forEach(p => group.append(new Option(p.name, p.preset_id))); select.append(group);
    }
    if (active && !state.presets.some(p => p.preset_id === active.preset_id))
      select.add(new Option(`${active.name} · copie de l’épisode`, active.preset_id));
    select.value = selected || active?.preset_id || "";
    const latest = state.presets.find(p => p.preset_id === active?.preset_id);
    el("style-preset-note").textContent = active
      ? `${active.name} · version ${active.revision} conservée dans cet épisode.${latest && latest.revision !== active.revision ? " Une nouvelle version est disponible : Appliquer pour la reprendre." : ""}`
      : "Choisir un preset puis Appliquer reprend son exemple visuel, son checkpoint et ses LoRA communs.";
  }
  function drawLoras() {
    for (const [id, slot, disabled] of [["common-loras", "commonLoras", state.busy], ["image-loras", "loras", state.busy || jobRunning(ref())]]) {
      resources.renderLoraStack(el(id), {resources: state.catalog?.loras || [], selections: state[slot], maximum: 10,
        minimumStrength: -20, maximumStrength: 20, draggable: true, disabled: disabled || !state.catalog,
        updatePreference, refreshResource, onChange(values) {
          state[slot] = values;
          if (slot === "commonLoras") commonChanged(); else { state.dirtyRef = true; controls(); }
        }});
    }
  }
  function drawBatchLoras() {
    for (const kind of ["character", "location"]) {
      const profile = state.batchProfiles[kind];
      resources.renderLoraStack(el(`batch-${kind}-loras`), {resources: state.catalog?.loras || [], selections: profile.loras, maximum: 10,
        minimumStrength: -20, maximumStrength: 20, draggable: true, disabled: state.busy || batchRunning() || !state.catalog,
        updatePreference, refreshResource, onChange(values) { profile.loras = values; drawBatch(); }});
    }
  }
  function batchSettings(kind) {
    const profile = state.batchProfiles[kind], prefix = `batch-${kind}`;
    const customSampling = state.catalog?.sampling.presets.find(p => p.id === el(`${prefix}-preset`).value)?.settings || profile.sampling;
    const technical = profile.inheritTechnical ? commonSettings() : {workflow: el(`${prefix}-workflow`).value,
      model_id: el(`${prefix}-model`).value, loras: structuredClone(profile.loras), sampling: customSampling};
    return {...technical,
      aspect_ratio: el(`${prefix}-ratio`).value, megapixels: Number(el(`${prefix}-mp`).value),
      seed: el(`${prefix}-seed`).value.trim() || null};
  }
  function hydrateBatchProfiles(force = false) {
    if (!state.data || !state.catalog || !state.models.length) return;
    const key = `${state.data.episode_id}:${JSON.stringify(state.data.reference_profiles || {})}`;
    if (!force && state.batchProfileKey === key) return;
    for (const kind of ["character", "location"]) {
      const stored = state.data.reference_profiles?.[kind];
      const sample = state.data.references.find(item => item.kind === kind);
      // Old saved profiles had no inheritance flag: keep them customized so a
      // newly selected preset never replaces their checkpoint/LoRA silently.
      const inheritTechnical = stored ? Boolean(stored.inherit_technical) : true;
      const settings = stored?.render_settings || sample?.effective_image_settings || state.data.image_defaults || {};
      const prefix = `batch-${kind}`;
      fillModel(`${prefix}-llm`, stored?.model_id || sample?.model_id);
      drawWorkflow(`${prefix}-workflow`, settings.workflow);
      modelPicker(`${prefix}-model`, settings.model_id);
      drawSampling(`${prefix}-preset`, settings.sampling);
      el(`${prefix}-ratio`).replaceChildren(...state.catalog.aspect_ratios.map(value => new Option(value, value)));
      const fallbackRatio = kind === "location" ? "16:9 (Landscape Widescreen)" : state.catalog.defaults.aspect_ratio;
      el(`${prefix}-ratio`).value = settings.aspect_ratio || fallbackRatio;
      if (!el(`${prefix}-ratio`).value) el(`${prefix}-ratio`).value = state.catalog.defaults.aspect_ratio;
      el(`${prefix}-mp`).value = String(settings.megapixels ?? 2.1);
      el(`${prefix}-seed`).value = settings.seed ?? "";
      state.batchProfiles[kind] = {loras: structuredClone(settings.loras || []), sampling: settings.sampling, inheritTechnical};
    }
    state.batchProfileKey = key;
    drawBatchLoras(); drawBatch();
  }
  function batchProfileSummary(kind) {
    if (kind === "object") kind = "character";
    if (!state.catalog || !state.models.length) return "Catalogue en cours de chargement";
    const prefix = `batch-${kind}`, settings = batchSettings(kind), workflowId = workflowKey(settings.workflow), modelId = settings.model_id;
    const workflow = state.catalog.workflows.find(item => item.id === workflowId);
    const model = state.catalog.render_models.find(item => item.comfy_name === modelId);
    const llm = state.models.find(item => item.id === el(`${prefix}-llm`).value);
    const preset = state.catalog.sampling.presets.find(item => item.id === settings.sampling?.preset_id);
    return `${llm?.label || llm?.display_name || el(`${prefix}-llm`).value} · ${state.batchProfiles[kind].inheritTechnical ? "KREA2 commun" : "KREA2 personnalisé"} · ${workflow?.label || workflowId} · ${model?.display_name || modelId} · ${preset?.label || settings.sampling?.preset_id || "sampling conservé"}`;
  }
  function drawBatch() {
    if (!state.data) return;
    const active = batchRunning(), batch = state.data.reference_batch;
    for (const kind of ["character", "location"]) {
      const inherited = state.batchProfiles[kind].inheritTechnical;
      el(`batch-${kind}-custom`).hidden = inherited;
      el(`batch-${kind}-toggle`).textContent = inherited ? "Personnaliser les réglages KREA2" : "Revenir aux réglages communs";
      el(`batch-${kind}-summary`).textContent = batchProfileSummary(kind);
    }
    const selectedItems = new Map((batch?.items || []).map(item => [item.reference_id, item]));
    el("batch-selection").replaceChildren(...activeReferences().map(reference => {
      const label = node("label"), checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = active ? selectedItems.has(reference.id) : state.batchSelection.has(reference.id);
      checkbox.disabled = active; checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.batchSelection.add(reference.id); else state.batchSelection.delete(reference.id);
        controls();
      });
      label.append(checkbox, node("b", `${reference.continuity_state_id ? "Variante" : kindLabel(reference.kind)} · ${reference.name}`),
        node("span", batchProfileSummary(reference.kind), "muted"));
      return label;
    }));
    const machine = state.data.machine_work?.machines || {};
    const machineText = key => { const value = machine[key]; if (!value) return `${key} indisponible`;
      return `${key === "local_gpu" ? "Local" : "Distant"} : ${value.state}${value.temperature_c == null ? "" : ` · ${value.temperature_c.toFixed(0)} °C`}${value.operation ? ` · ${value.operation}` : ""}`; };
    el("batch-machines").textContent = `${machineText("local_gpu")} · ${machineText("remote_gpu")}`;
    el("batch-progress").hidden = !batch;
    el("batch-status").textContent = batch ? `${batch.phase}${batch.error ? ` · ${batch.error}` : ""}` : "Vérifie les deux profils avant de lancer.";
    if (!batch) { el("batch-results").replaceChildren(); controls(); return; }
    const items = batch.items || [], total = Math.max(1, items.length);
    const promptDone = items.filter(item => !["pending", "prompting"].includes(item.status)).length;
    const imageDone = items.filter(item => ["ready_for_review", "validated", "failed"].includes(item.status)).length;
    const validated = items.filter(item => item.status === "validated").length;
    for (const [id, value, text] of [["prompt", promptDone, `${promptDone} / ${items.length}`], ["image", imageDone, `${imageDone} / ${items.length}`], ["validation", validated, `${validated} / ${items.length}`]]) {
      el(`batch-${id}-progress`).max = total; el(`batch-${id}-progress`).value = value; el(`batch-${id}-count`).textContent = text;
    }
    el("batch-results").replaceChildren(...items.map(item => {
      const card = node("article", "", "episode-batch-result");
      card.append(node("b", `${kindLabel(item.kind)} · ${item.name}`));
      if (item.output_asset_id) { const image = document.createElement("img"); image.src = assetUrl(item.output_asset_id); image.alt = item.name; card.append(image); }
      card.append(node("p", item.phase || item.status), node("p", item.error || "", item.error ? "error" : "muted"));
      const actions = node("div", "", "story-actions");
      actions.append(button("Ouvrir la fiche", () => action(async () => {
        await saveReference(); state.refId = item.reference_id; state.imageProject = null; state.dirtyRef = false;
        drawLists(); drawReference(true); await imageProject();
      })));
      if (item.output_asset_id && item.status !== "validated") actions.append(button("Valider cette image", () => action(async () => {
        const reference = state.data.references.find(value => value.id === item.reference_id);
        accept(await core.request(api(`/references/${reference.id}/select`), send("POST", {expected_revision: reference.revision, asset_id: item.output_asset_id})));
      })));
      card.append(actions); return card;
    }));
    controls();
  }
  async function changeResource(resource, suffix, body) {
    try {
      const updated = await core.request(`/api/image-lab/krea2-batch/resources/${encodeURIComponent(resource.resource_id)}/${suffix}`,
        body ? send("POST", body) : {method: "POST"});
      for (const item of [...(state.catalog?.render_models || []), ...(state.catalog?.loras || [])])
        if (item.resource_id === updated.resource_id) Object.assign(item, updated);
      modelPicker("common-model", el("common-model").value); modelPicker("image-model", el("image-model").value);
      for (const kind of ["character", "location"]) modelPicker(`batch-${kind}-model`, el(`batch-${kind}-model`).value);
      drawLoras(); drawBatchLoras();
      return updated;
    } catch (error) { message(error.message, true); return false; }
  }
  const updatePreference = (resource, values) => changeResource(resource, "preference", values);
  const refreshResource = resource => changeResource(resource, "refresh");
  function commonChanged() {
    state.dirtyCommon = true; el("visual-status").textContent = "Modifications à enregistrer";
    drawImageInheritance(); drawBatch(); controls();
  }
  function drawImageInheritance() {
    el("image-custom").hidden = state.inheritImages;
    el("image-toggle-settings").textContent = state.inheritImages ? "Personnaliser cette fiche" : "Revenir aux réglages communs";
    const s = state.inheritImages ? commonSettings() : {workflow: el("image-workflow").value, model_id: el("image-model").value, loras: state.loras};
    const model = state.catalog?.render_models.find(m => m.comfy_name === s.model_id);
    const workflow = state.catalog?.workflows?.find(item => item.id === workflowKey(s.workflow));
    el("image-settings-note").textContent = `${state.inheritImages ? "Réglages communs" : "Personnalisé pour cette fiche"} · ${workflow?.label || workflowKey(s.workflow)} · ${model?.display_name || s.model_id || "Checkpoint à choisir"} · ${s.loras.length} LoRA`;
  }
  function drawImageSettings(saved) {
    const catalog = state.catalog;
    if (!catalog) return;
    drawWorkflow("image-workflow", saved?.workflow);
    modelPicker("image-model", saved?.model_id);
    el("image-ratio").replaceChildren(...catalog.aspect_ratios.map(v => new Option(v, v)));
    el("image-ratio").value = saved?.aspect_ratio || (ref()?.kind === "location" ? "16:9 (Landscape Widescreen)" : catalog.defaults.aspect_ratio);
    if (!el("image-ratio").value) el("image-ratio").value = catalog.defaults.aspect_ratio;
    el("image-mp").value = String(saved?.megapixels ?? 2.1); el("image-seed").value = saved?.seed ?? "";
    state.loras = structuredClone(saved?.loras || []); state.imageSampling = saved?.sampling;
    drawSampling("image-preset", saved?.sampling); drawLoras(); drawImageInheritance();
  }
  function imageSettings() {
    const sampling = state.catalog?.sampling.presets.find(p => p.id === el("image-preset").value)?.settings || state.imageSampling;
    return {prompt: el("asset-text").value.trim(), workflow: el("image-workflow").value, model_id: el("image-model").value, aspect_ratio: el("image-ratio").value,
      megapixels: Number(el("image-mp").value), seed: el("image-seed").value.trim() || null,
      loras: structuredClone(state.loras), ...(sampling ? {sampling} : {}), ...(state.inheritImages ? commonSettings() : {})};
  }
  function referenceSettingsTemplate() {
    const r = ref();
    if (!r) return null;
    const settings = state.catalog ? imageSettings() : structuredClone(r.render_settings || r.effective_image_settings || {});
    delete settings.prompt;
    return {kind: r.kind, model_id: el("asset-model").value || r.model_id,
      inherit_image_settings: state.inheritImages, render_settings: settings};
  }
  function canAdoptReferenceSettings(r, template) {
    return Boolean(r && template && r.kind === template.kind && r.revision === 1 && !r.prompt
      && !r.render_settings && !r.krea_project_id && !r.image_asset_id && !(r.images || []).length
      && !(r.image_runs || []).length && !r.job);
  }
  function adoptReferenceSettings(template) {
    const r = ref();
    if (!canAdoptReferenceSettings(r, template)) return false;
    fillModel("asset-model", template.model_id);
    state.inheritImages = template.inherit_image_settings;
    drawImageSettings(template.render_settings);
    state.dirtyRef = true;
    return true;
  }
  async function continuityAction(id, work) {
    if (state.busy || id !== state.data?.episode_id) throw new Error("Attends la fin de l’action en cours, puis réessaie.");
    state.busy = true; controls();
    try {
      await flushRender(); await saveReference(); await saveScene();
      return await work();
    } finally { state.busy = false; controls(); schedule(); }
  }
  function drawContinuity() {
    const data = state.data, host = el("continuity");
    host.hidden = !data;
    if (!data) return;
    const id = data.episode_id;
    window.PanelForgeContinuity.render(host, {identity: id, revision: data.continuity_revision || 1,
      data: data.visual_continuity, characters: data.scenario.characters, scenes: data.scenario.scenes,
      references: data.references, disabled: state.busy || batchRunning() || videoChainRunning() || imageRunning()
        || data.references.some(jobRunning),
      onSave: (visual_continuity, expected_revision) => continuityAction(id, async () => {
        const previous = new Set(state.data.references.map(r => r.id));
        const result = await core.request(api("/continuity", id), send("PUT", {expected_revision, visual_continuity}));
        result.references.filter(r => !r.continuity_archived && !r.continuity_state_id && !previous.has(r.id)).forEach(r => state.batchSelection.add(r.id));
        accept(result); drawScene(true);
        message("Continuité enregistrée. Les préparations touchées sont signalées à actualiser.");
      }),
      onReference: r => continuityAction(id, async () => {
        state.refId = r.id; state.imageProject = null; state.dirtyRef = false;
        await tab("references"); drawLists(); drawReference(true); await imageProject(); storeContext();
        el("reference").scrollIntoView({behavior: "smooth", block: "center"});
      }),
      onVariant: data.qwen_variants_available ? r => continuityAction(id, async () => {
        if (!window.PanelForgeQwenEdit) throw new Error("Actualise la page pour charger l’atelier Qwen.");
        const latest = state.data.references.find(item => item.id === r.id);
        const result = await core.request(api(`/references/${r.id}/variant`, id), send("POST", {expected_revision: latest.revision}));
        accept(result.episode);
        await window.PanelForgeQwenEdit.open(result.project_id);
      }) : null,
      onResults: r => continuityAction(id, async () => {
        const result = await core.request(api(`/references/${r.id}/variant-results`, id));
        const revision = state.data.references.find(item => item.id === r.id).revision;
        window.PanelForgeContinuity.resultsDialog(result.results, asset_id => continuityAction(id, async () => {
          accept(await core.request(api(`/references/${r.id}/variant-select`, id), send("POST", {expected_revision: revision, asset_id})));
          message("Variante sélectionnée pour les scènes où cet état est acquis.");
        }));
      })});
  }
  function drawLists() {
    if (!state.data) return;
    el("versions").replaceChildren(...state.list.map(e => new Option(`Scénario v${e.story_revision} · ${e.title}`, e.episode_id)));
    el("versions").value = state.data.episode_id;
    el("source").textContent = `Scénario v${state.data.story_revision} · ${state.data.references.length} fiches · ${state.data.scenes.length} scènes.`
      + (state.data.story_changed ? " L’histoire a changé depuis cette validation ; cette fabrication conserve sa version." : "");
    el("reference").replaceChildren(...activeReferences().map(r => new Option(`${kindLabel(r.kind)} · ${r.name}${r.image_asset_id ? " ✓" : ""}${r.continuity_image_stale ? " · État à actualiser" : ""}${r.prompt_style_stale || r.image_style_status === "outdated" ? " · Style à actualiser" : ""}`, r.id)));
    el("reference").value = state.refId;
    el("reference-count").textContent = `${activeReferences().filter(r => r.image_asset_id).length} / ${activeReferences().length} images retenues`;
    el("scene").replaceChildren(...state.data.scenes.map(s => new Option(`${s.index + 1} · ${s.title} · ${renderDuration(s)} s · ${
      s.image_refresh_names?.length ? "Images à synchroniser" : s.stale ? "À actualiser" : jobRunning(s) ? promptActivity(s) : statuses[s.video_status] || statuses[s.preparations.at(-1)?.status] || "À préparer"}`, s.id)));
    el("scene").value = state.sceneId;
  }
  function createVideoCard(sceneId) {
    const card = node("article", "", "episode-video-card");
    card.dataset.sceneId = sceneId;
    const heading = node("div", "", "episode-video-card-heading");
    const title = node("b"), meta = node("span", "", "muted");
    heading.append(title, meta);
    const planStatus = node("p", "", "muted"), writerStatus = node("p", "", "muted");
    const videoStatus = node("p"), dlssStatus = node("p");
    const continuityNote = node("p", "", "episode-continuity-note"), durationNote = node("p", "", "episode-duration-note");
    const error = node("p", "", "error"); error.hidden = true;
    const media = node("div", "", "episode-video-media");
    const dlss = node("div", "", "episode-video-dlss");
    const actions = node("div", "", "story-actions");
    const open = button("Ouvrir la sc\u00e8ne", () => action(async () => {
      const sceneId = card.dataset.sceneId;
      if (sceneId === state.sceneId) return;
      await saveScene(); state.sceneId = sceneId; state.prepId = ""; state.dirtyScene = false;
      drawLists(); drawScene(true); drawVideoOverview(); await openRender(); storeContext();
    }));
    actions.append(open);
    card.append(heading, planStatus, writerStatus, videoStatus, dlssStatus, continuityNote, durationNote, error, media, dlss, actions);
    card._refs = {title, meta, planStatus, writerStatus, videoStatus, dlssStatus, continuityNote, durationNote, error, media, dlss, actions, open};
    return card;
  }
  function updateStage(element, label, status, text) {
    const tone = ["ready", "succeeded"].includes(status) ? "done"
      : ["failed", "interrupted", "unconfirmed"].includes(status) ? "failed"
      : ["queued", "planned"].includes(status) ? "planned"
      : ["starting", "submitting", "running", "receiving", "importing", "cancel_pending"].includes(status) ? "running" : "pending";
    const marker = {done: "✓ ", running: "● ", planned: "◷ ", failed: "X ", pending: ""}[tone];
    element.className = `episode-stage ${tone}`;
    element.textContent = `${marker}${label} : ${text}`;
  }
  function updateDlssStage(card, value, item) {
    const attempt = value.video_attempt;
    const live = attempt && window.PanelForgeDlss?.progress?.({owner: "ref2v",
      ownerId: value.preparations.at(-1)?.render_project_id, attempt});
    const paused = item?.dlss_resume_pending && (!live || live.status === "cancelled");
    const requested = item && state.data?.video_chain?.auto_dlss;
    const status = paused ? "paused" : live?.status || item?.dlss_status || (requested ? "planned" : "not_requested");
    const text = paused ? "en pause" : status === "queued" ? "planifié · en attente" : live?.label || ({not_requested: "non demandé", planned: "planifié · après la vidéo", pending: "à préparer", queued: "planifié · en attente",
      paused: "en pause", failed: "échec", succeeded: "terminé", cancelled: "annulé"}[status] || "en cours");
    updateStage(card._refs.dlssStatus, "DLSS", status, text);
    card._refs.dlssStatus.title = live?.error || item?.dlss_error || "";
  }
  window.addEventListener("panelforge:dlss-update", () => {
    if (!state.data) return;
    const items = new Map((state.data.video_chain?.items || []).map(item => [item.scene_id, item]));
    for (const value of state.data.scenes) {
      const card = state.videoCards.get(value.id);
      if (card) updateDlssStage(card, value, items.get(value.id));
    }
  });
  function cooldownRemaining(chain) {
    const deadline = Date.parse(chain?.cooldown_until || "");
    const persisted = Number.isFinite(deadline) ? Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) : 0;
    const machine = Number(state.data?.machine_work?.machines?.remote_gpu?.cooldown_remaining_seconds || 0);
    return Math.max(persisted, machine);
  }
  function updateVideoCard(card, value, item) {
    const refs = card._refs, attempt = value.video_attempt;
    refs.continuityNote.textContent = (value.continuity_warnings || []).join(" · ");
    if (!refs.continuityNote.textContent && value.continuity_states?.length)
      refs.continuityNote.textContent = "Continuité : " + value.continuity_states.map(row => row.name).join(" · ");
    refs.continuityNote.hidden = !refs.continuityNote.textContent;
    refs.continuityNote.title = (value.continuity_states || []).map(row => `${row.name} : ${row.start || row.description}`).join("\n");
    refs.durationNote.textContent = value.duration_warning || ""; refs.durationNote.hidden = !value.duration_warning;
    refs.title.textContent = `${value.index + 1} \u00b7 ${value.title}`;
    refs.meta.textContent = `${renderDuration(value)} s \u00b7 ${value.inherit_video_settings ? "r\u00e9glages communs" : "personnalis\u00e9s"}`;
    const preparation = value.preparations.at(-1);
    const explicitStages = preparation?.prompt_stages || {};
    const phase = value.job?.phase || item?.phase || "";
    const fallbackStage = stage => {
      if (preparation?.status === "ready" || (item && !["pending", "prompting", "prompt_failed"].includes(item.status))) return "ready";
      if (stage === "plan" && phase.startsWith("1/2")) return "queued";
      if (stage === "plan" && phase.startsWith("2/2")) return "ready";
      if (stage === "writer" && phase.startsWith("2/2")) return "queued";
      if (preparation?.status === "interrupted") return "interrupted";
      if (preparation?.status === "failed" || item?.status === "prompt_failed") return stage === "writer" ? "failed" : "unknown";
      return jobRunning(value) || ["pending", "prompting"].includes(item?.status) ? "queued" : "pending";
    };
    const stageText = {pending: "\u00e0 pr\u00e9parer", queued: "planifié", starting: "démarrage", running: "en cours", ready: "pr\u00eat",
      failed: "\u00e9chec", interrupted: "interrompu", unknown: "\u00e0 v\u00e9rifier"};
    const plan = explicitStages.plan || fallbackStage("plan");
    const writer = explicitStages.writer || fallbackStage("writer");
    const videoByStatus = {pending: "planifiée · en attente du prompt", prompting: "planifiée · en attente du prompt",
      prompt_ready: "planifiée · prête à démarrer", rendering: "planifiée · en attente du GPU", succeeded: "termin\u00e9e", video_failed: "\u00e9chec"};
    let videoText = videoByStatus[item?.status] || statuses[value.video_status] || "\u00e0 g\u00e9n\u00e9rer";
    if (item?.status === "rendering" && attempt?.status === "running") videoText = "rendu en cours";
    else if (item?.status === "rendering" && attempt?.status === "cancel_pending") videoText = "annulation en cours";
    const videoStage = item?.status === "video_failed" ? "failed"
      : item?.status === "succeeded" ? "succeeded"
      : ["pending", "prompting", "prompt_ready"].includes(item?.status) ? "planned"
      : attempt?.status || value.video_status || "pending";
    updateStage(refs.planStatus, "Plan", plan, stageText[plan] || plan);
    updateStage(refs.writerStatus, "Rédacteur", writer, stageText[writer] || writer);
    refs.planStatus.title = plan === "queued" ? "Demande enregistrée · en attente du LLM" : "";
    refs.writerStatus.title = writer === "queued" ? (plan === "ready" ? "En attente du LLM" : "Démarrera après le Plan") : "";
    const processing = [plan, writer, videoStage].some(status => ["starting", "submitting", "running", "receiving", "importing"].includes(status));
    card.className = `episode-video-card${value.id === state.sceneId ? " selected" : ""}${processing ? " processing" : ""}`;
    if (processing) card.setAttribute("aria-busy", "true"); else card.removeAttribute("aria-busy");
    updateStage(refs.videoStatus, "Vidéo", videoStage, videoText);
    updateDlssStage(card, value, item);
    const error = item?.error || value.job?.error;
    refs.error.hidden = !error; refs.error.textContent = error || "";
    const assetId = attempt?.output_asset_id || "";
    if (refs.media.dataset.assetId !== assetId) {
      refs.media.dataset.assetId = assetId;
      refs.media.replaceChildren();
      if (assetId) {
        const video = document.createElement("video"); video.controls = true; video.playsInline = true;
        video.preload = "metadata"; video.src = assetUrl(assetId); refs.media.append(video);
      }
    }
    refs.open.textContent = value.id === state.sceneId ? "Sc\u00e8ne ouverte" : "Ouvrir la sc\u00e8ne";
    refs.open.disabled = value.id === state.sceneId;
    const dlssKey = value.dlss_ready && attempt ? attempt.attempt_id : "";
    if (refs.dlss.dataset.attemptId !== dlssKey) {
      refs.dlss.dataset.attemptId = dlssKey;
      refs.dlss.replaceChildren();
      if (dlssKey && window.PanelForgeDlss) {
        const target = {owner: "ref2v", ownerId: value.preparations.at(-1)?.render_project_id,
          attempt: {...attempt, output_url: assetUrl(attempt.output_asset_id)}};
        let tracked = state.dlssPanels.get(value.id);
        if (!tracked || tracked.attemptId !== attempt.attempt_id) {
          tracked = {attemptId: attempt.attempt_id, panel: window.PanelForgeDlss.inlineStatus(target)};
          state.dlssPanels.set(value.id, tracked);
        }
        refs.dlss.append(window.PanelForgeDlss.button(target), tracked.panel);
      }
    }
  }
  function drawVideoOverview() {
    if (!state.data) return;
    const chain = state.data.video_chain, chainItems = chain?.items || [];
    const items = new Map(chainItems.map(item => [item.scene_id, item]));
    const total = chainItems.length || state.data.scenes.length || 1;
    const promptReadyStates = new Set(["prompt_ready", "rendering", "succeeded", "video_failed"]);
    const promptReady = chainItems.filter(item => promptReadyStates.has(item.status)).length;
    const videoDone = chainItems.filter(item => item.status === "succeeded").length;
    el("video-progress").hidden = !chain;
    el("video-prompt-progress-bar").max = total; el("video-prompt-progress-bar").value = promptReady;
    el("video-progress-bar").max = total; el("video-progress-bar").value = videoDone;
    if (chain) {
      const prompting = chainItems.find(item => item.status === "prompting");
      const rendering = chainItems.find(item => item.status === "rendering");
      const cooling = cooldownRemaining(chain);
      const promptNext = chainItems.find(item => item.status === "pending");
      el("video-prompt-lane").textContent = prompting
        ? `${promptActivity(state.data.scenes.find(value => value.id === prompting.scene_id))} · ${prompting.index + 1} · ${prompting.title}`
        : promptReady === chainItems.length ? "Tous les prompts sont pr\u00eats"
        : chain.status === "paused" ? "En pause"
        : promptNext ? `Prochain \u00b7 ${promptNext.index + 1} \u00b7 ${promptNext.title}` : "En attente";
      const cooled = chainItems.find(item => item.scene_id === chain.cooldown_scene_id);
      el("video-render-lane").textContent = cooling
        ? `Refroidissement apr\u00e8s ${cooled ? `${cooled.index + 1} \u00b7 ${cooled.title}` : "la vid\u00e9o"} \u00b7 ${cooling} s`
        : rendering ? `${rendering.index + 1} \u00b7 ${rendering.title} \u00b7 ${state.data.scenes.find(value => value.id === rendering.scene_id)?.video_attempt?.status === "running" ? "rendu en cours" : "en attente du GPU"}`
        : videoDone === chainItems.length ? "Toutes les vid\u00e9os sont termin\u00e9es" : chain.status === "paused" ? "En pause" : "En attente";
      const promptFailed = chainItems.filter(item => item.status === "prompt_failed").length;
      const videoFailed = chainItems.filter(item => item.status === "video_failed").length;
      const pause = chain.status === "pausing"
        ? "Pause demand\u00e9e : les t\u00e2ches nomm\u00e9es ci-dessus terminent ; aucune nouvelle t\u00e2che ne d\u00e9marrera."
        : chain.status === "paused" ? "Cha\u00eene en pause. Reprenez-la pour lancer la prochaine t\u00e2che." : chain.phase;
      el("video-chain-phase").textContent = `${pause} \u00b7 Prompts ${promptReady}/${chainItems.length} \u00b7 Vid\u00e9os ${videoDone}/${chainItems.length}`
        + (promptFailed ? ` \u00b7 ${promptFailed} erreur(s) prompt` : "")
        + (videoFailed ? ` \u00b7 ${videoFailed} erreur(s) vid\u00e9o` : "") + (chain.error ? ` \u00b7 ${chain.error}` : "");
    }
    const container = el("video-cards"), valid = new Set(state.data.scenes.map(value => value.id));
    for (const [sceneId, card] of state.videoCards) if (!valid.has(sceneId)) { card.remove(); state.videoCards.delete(sceneId); }
    for (const value of state.data.scenes) {
      let card = state.videoCards.get(value.id);
      if (!card) { card = createVideoCard(value.id); state.videoCards.set(value.id, card); container.append(card); }
      updateVideoCard(card, value, items.get(value.id));
    }
    controls();
  }
  function imageRecord(record) {
    const details = node("details"), visual = record.prompt_style, settings = record.settings;
    details.append(node("summary", "Style et réglages utilisés"));
    details.append(node("p", visual?.preset ? `${visual.preset.name} · version ${visual.preset.revision}`
      : visual ? "Style personnalisé" : "Style du prompt non documenté"));
    if (record.prompt_manually_edited) details.append(node("p", "Prompt modifié manuellement après sa rédaction. Le style indiqué est celui de la dernière rédaction LLM."));
    if (visual?.style) details.append(node("p", visual.style));
    if (visual?.image) {
      const link = node("a", "Voir l’image de style"); link.href = assetUrl(visual.image.asset_id); link.target = "_blank"; link.rel = "noopener";
      details.append(link);
    }
    const workflow = state.catalog?.workflows?.find(item => item.id === workflowKey(settings.workflow));
    details.append(node("p", `Workflow : ${workflow?.label || workflowKey(settings.workflow)}`));
    details.append(node("p", `Checkpoint : ${settings.model_name}`));
    details.append(node("p", `LoRA : ${settings.loras.map(l => `${l.name} (${l.strength})`).join(", ") || "aucune"}`));
    const sampling = settings.sampling;
    if (sampling) details.append(node("p", [sampling.first_pass, sampling.second_pass]
      .map((pass, i) => `Passe ${i + 1} : ${pass.steps} steps · ${pass.sampler} / ${pass.scheduler}`).join("\n")));
    details.append(node("p", `${settings.aspect_ratio} · ${settings.megapixels} MP · seed ${record.seed}`));
    const prompt = node("details"); prompt.append(node("summary", "Prompt de cet essai"), node("pre", record.prompt)); details.append(prompt);
    return details;
  }
  function drawReference(force = false) {
    const r = ref(); if (!r) return;
    if (force || !state.dirtyRef) {
      el("description").value = r.description; el("asset-text").value = r.prompt;
      state.inheritImages = r.inherit_image_settings ?? !r.render_settings;
      fillModel("asset-model", r.model_id); drawImageSettings(r.effective_image_settings || r.render_settings);
    }
    el("style-warning").hidden = !r.prompt_style_stale;
    el("style-warning").textContent = "Le style commun a changé depuis la dernière rédaction LLM. Vérifie le prompt ou propose un ajustement. L’image retenue reste conservée.";
    el("reference-preview").hidden = !r.image_asset_id; el("no-reference").hidden = !!r.image_asset_id;
    if (r.image_asset_id) el("reference-preview").src = assetUrl(r.image_asset_id); else el("reference-preview").removeAttribute("src");
    el("image-style-note").hidden = !r.image_asset_id;
    const inheritedNote = r.inherited_image
      ? `Référence héritée de l’épisode précédent pour ${r.inherited_image.name}. ` : "";
    el("image-style-note").textContent = inheritedNote + (r.image_style_status === "outdated"
      ? "Cette image provient d’une ancienne direction de style. Elle reste retenue jusqu’à ton prochain choix."
      : r.image_style_status === "current" ? "Image préparée avec le style commun actuel."
      : "Style de cette image non documenté : vérifie sa cohérence avec l’épisode.");
    if (r.continuity_image_stale) el("image-style-note").textContent = "L’état décrit a changé. Choisis une nouvelle image, ou confirme l’image existante si elle correspond encore. Vérifie aussi le prompt de la fiche.";
    el("asset-status").textContent = r.job?.error || (jobRunning(r) ? r.job.phase : imageRunning() ? "Image en cours de génération…" : "");
    el("image-calls").hidden = !r.krea_project_id; el("image-open").hidden = !r.krea_project_id;
    const items = [...r.images.map(i => ({...i, status: "succeeded", output_asset_id: i.asset_id})), ...(state.imageProject?.attempts || [])];
    el("image-attempts").replaceChildren(...items.slice().reverse().map(a => {
      const selected = a.output_asset_id === r.image_asset_id && !r.continuity_image_stale;
      const card = node("article", "", `episode-image-card${selected ? " selected" : ""}`);
      if (a.output_asset_id) {
        const link = node("a"), img = node("img"); link.href = assetUrl(a.output_asset_id); link.target = "_blank"; link.rel = "noopener";
        img.src = link.href; img.alt = a.label || "Proposition de référence"; img.loading = "lazy"; link.append(img); card.append(link);
      }
      card.append(node("p", `${a.label || `Essai ${a.index}`} · ${statuses[a.status] || a.status}`));
      if (a.pre_flux_url) {
        const preFlux = node("a", "Voir / télécharger la sortie KREA2 avant Flux");
        preFlux.href = a.pre_flux_url; preFlux.target = "_blank"; preFlux.rel = "noopener"; preFlux.download = "";
        card.append(preFlux);
      }
      if (a.error) card.append(node("p", a.error, "error"));
      const record = r.image_runs?.find(run => run.attempt_id === a.attempt_id);
      if (record) card.append(imageRecord(record));
      if (a.output_asset_id) { const b = button(selected ? "Image retenue" : "Utiliser cette image", () => action(async () => {
        const data = await core.request(api(`/references/${r.id}/select`), send("POST", {expected_revision: ref().revision, asset_id: a.output_asset_id}));
        accept(data); message("Référence retenue. Les nouvelles préparations utiliseront cette image.");
      })); b.dataset.imageChoice = "true"; b.dataset.selected = String(selected);
        b.disabled = selected || state.busy || jobRunning(r); card.append(b); }
      return card;
    }));
  }
  function drawBindings() {
    // Keep the editable identity bindings separate from the derived timeline.
    // Merely opening/saving a scene must not pin its current visual variant.
    const resolved = !state.dirtyScene ? (scene()?.resolved_references || state.bindings) : state.bindings;
    const used = new Set([...state.bindings, ...resolved].map(b => b.reference_id));
    el("add-reference").replaceChildren(...activeReferences().filter(r => !used.has(r.id)).map(r => new Option(r.name, r.id)));
    el("reference-limit").textContent = `${resolved.length} / 9 images${state.dirtyScene ? " · Enregistre pour recalculer la continuité" : ""}`;
    el("scene-references").replaceChildren(...resolved.map((binding, index) => {
      const r = state.data.references.find(r => r.id === binding.reference_id), card = node("article", "", "episode-reference-card");
      const original = state.bindings[index];
      const automatic = !original || original.reference_id !== binding.reference_id;
      if (r.image_asset_id) { const img = node("img"); img.src = assetUrl(r.image_asset_id); img.alt = r.name; card.append(img); }
      else card.append(node("p", "Image à préparer", "muted"));
      card.append(node("strong", `<Picture ${index + 1}> · ${r.name}`));
      if (automatic) {
        card.append(node("p", "Référence choisie par la continuité de cette scène.", "muted"), button("Ajuster dans Continuité", () => {
          const details = el("continuity").querySelector("details"); if (details) details.open = true;
          el("continuity").scrollIntoView({behavior: "smooth", block: "start"});
        }));
        return card;
      }
      const select = node("select"); select.setAttribute("aria-label", `Rôle de ${r.name}`);
      select.append(...Object.entries(roles).map(([key, label]) => new Option(label, key))); select.value = binding.role;
      select.addEventListener("change", () => { original.role = select.value; state.dirtyScene = true; controls(); }); card.append(select);
      const actions = node("div", "", "story-actions");
      const move = offset => { const target = index + offset; if (target < 0 || target >= state.bindings.length) return;
        [state.bindings[index], state.bindings[target]] = [state.bindings[target], state.bindings[index]]; state.dirtyScene = true; drawBindings(); };
      actions.append(button("↑", () => move(-1)), button("↓", () => move(1)), button("Retirer", () => {
        state.bindings.splice(index, 1); state.dirtyScene = true; drawBindings(); })); card.append(actions); return card;
    })); controls();
  }
  function drawScene(force = false) {
    const s = scene(); if (!s) return;
    if (force || !state.dirtyScene) {
      el("intention").value = s.intention; el("duration").value = s.duration; el("shots").value = s.shot_count ?? ""; el("audacity").value = s.audacity;
      for (const [axis, id] of Object.entries(axesIds)) el(id).value = (s.creative_axes || initialAxes)[axis];
      updateAxes();
      fillModel("plan-model", s.plan_model_id); fillModel("writer-model", s.writer_model_id);
      state.bindings = structuredClone(s.references); drawBindings();
    }
    const source = state.data.scenario.scenes[s.index], names = Object.fromEntries(state.data.scenario.characters.map(c => [c.id, c.name]));
    el("dialogues").textContent = source.dialogue.map(d => dialogueLabel(d, names[d.speaker_id])).join("\n") || "Aucun dialogue.";
    el("resolved-intention").textContent = s.resolved_intention || s.input_error;
    el("scene-state").textContent = s.input_error || (s.image_refresh_names?.length
      ? `Images modifiées : ${s.image_refresh_names.join(", ")}. Elles seront utilisées à la prochaine génération, avec le même prompt et sans appel LLM. Les anciens rendus restent dans leur préparation.`
      : s.stale ? "L’intention ou les références de la scène ont changé. Prépare un nouveau prompt avant de relancer le rendu ; les anciens rendus restent conservés."
      : "Les références sont prêtes. Les dialogues sont ajoutés automatiquement.");
    el("prompt-status").textContent = s.job?.error || (jobRunning(s) ? s.job.phase : "");
    el("preparation-label").hidden = !s.preparations.length;
    el("preparation").replaceChildren(...[...s.preparations].reverse().map((p, index) => new Option(`Préparation ${s.preparations.length - index} · ${p.images_refreshed ? "Images actualisées · prompt conservé" : statuses[p.status] || p.status}`, p.id)));
    if (!s.preparations.some(p => p.id === state.prepId)) state.prepId = s.preparations.at(-1)?.id || "";
    el("preparation").value = state.prepId;
    el("video-settings-note").textContent = s.inherit_video_settings
      ? "Cette scène utilise les réglages vidéo communs. Sa durée et sa seed restent propres à la scène."
      : "Cette scène possède ses propres réglages vidéo et ne sera pas modifiée par les réglages communs.";
    el("video-settings-toggle").textContent = s.inherit_video_settings ? "Personnaliser cette scène" : "Revenir aux réglages communs";
    controls();
  }
  function accept(data) {
    if (state.data?.episode_id === data.episode_id && (state.data.continuity_revision || 1) > (data.continuity_revision || 1)) return;
    if (state.data?.episode_id === data.episode_id) {
      // Preparations are append-only: ignore a poll started before a refresh.
      if (data.scenes.some(s => s.preparations.length < (state.data.scenes.find(old => old.id === s.id)?.preparations.length || 0))) return;
      const previous = scene(), incoming = data.scenes.find(s => s.id === state.sceneId);
      if (previous && incoming && state.prepId === previous.preparations.at(-1)?.id
          && incoming.preparations.length > previous.preparations.length)
        state.prepId = incoming.preparations.at(-1).id;
    }
    // A poll may have started just before a settings save completed. Keep the
    // newer local snapshot until the next response includes its revision.
    if (state.data?.episode_id === data.episode_id && state.data.visual_revision > (data.visual_revision || 1))
      for (const key of ["style", "style_image", "style_preset", "image_defaults", "visual_revision"]) data[key] = structuredClone(state.data[key]);
    if (state.data?.episode_id === data.episode_id && state.data.video_revision > (data.video_revision || 1))
      for (const key of ["video_defaults", "video_revision"]) data[key] = structuredClone(state.data[key]);
    if (state.data?.episode_id === data.episode_id) for (const s of data.scenes) {
      const local = state.data.scenes.find(old => old.id === s.id);
      if (local && local.render_revision > s.render_revision) {
        s.render_setup = structuredClone(local.render_setup); s.effective_render_setup = structuredClone(local.effective_render_setup);
        s.inherit_video_settings = local.inherit_video_settings; s.render_revision = local.render_revision;
      }
    }
    state.data = data;
    if (!activeReferences().some(r => r.id === state.refId)) { state.refId = activeReferences()[0]?.id || ""; state.dirtyRef = false; }
    state.batchSelection = new Set([...state.batchSelection].filter(id => activeReferences().some(r => r.id === id)));
    for (const s of data.scenes) { const key = `${data.episode_id}:${s.id}`;
      state.renderRevision.set(key, Math.max(s.render_revision, state.renderRevision.get(key) || 0)); }
    drawLists(); drawVisual(); drawReference(); drawScene(); hydrateBatchProfiles(); drawBatch(); drawVideoOverview(); controls();
  }
  async function imageProject() {
    const r = ref(), id = state.data?.episode_id; if (!r) return;
    const data = await core.request(api(`/references/${r.id}/project`, id));
    if (id === state.data?.episode_id && r.id === state.refId) { state.imageProject = data.project; drawReference(); controls(); }
  }
  async function refresh() {
    const id = state.data?.episode_id, token = state.token; if (!id) return;
    const data = await core.request(api("", id)); if (token !== state.token || id !== state.data?.episode_id) return;
    accept(data); await imageProject(); if (state.tab === "scenes") await openRender();
  }
  function schedule() {
    clearTimeout(state.timer);
    if (root.hidden || !state.data || document.getElementById("stories-workspace").hidden) return;
    const running = [...state.data.references, ...state.data.scenes].some(jobRunning) || imageRunning() || batchRunning() || videoChainRunning();
    if (!running) return;
    const token = state.token;
    state.timer = setTimeout(async () => { try { if (!state.busy) await refresh(); } catch (error) { message(error.message, true); }
      finally { if (token === state.token) schedule(); } }, 2000);
  }
  async function saveCommon() {
    if (!state.data || (!state.dirtyCommon && (state.data.image_defaults?.model_id || !state.catalog || !el("common-model").value))) return;
    if (!state.catalog || !el("common-model").value) throw new Error("Attends le catalogue ou choisis un checkpoint commun avant d’enregistrer.");
    const data = await core.request(api("/visual"), send("PUT", {expected_revision: state.data.visual_revision || 1,
      style: el("style").value.trim(), settings: commonSettings()}));
    state.dirtyCommon = false; accept(data);
  }
  async function saveReference() {
    await saveCommon();
    if (!state.dirtyRef) return;
    const r = ref(), payload = {expected_revision: r.revision, description: el("description").value.trim(),
      prompt: el("asset-text").value.trim(), model_id: el("asset-model").value,
      inherit_image_settings: state.inheritImages,
      render_settings: state.catalog && imageSettings().model_id && el("image-ratio").value ? imageSettings() : r.render_settings};
    const data = await core.request(api(`/references/${r.id}`), send("PUT", payload)); state.dirtyRef = false; accept(data);
  }
  async function startReferenceBatch() {
    await saveReference();
    const profiles = {};
    for (const kind of ["character", "location"]) {
      const prefix = `batch-${kind}`;
      if (!knownModel(el(`${prefix}-llm`).value)) throw new Error(`Choisis un LLM disponible pour le profil ${kind === "character" ? "Personnages" : "Décors"}.`);
      const settings = batchSettings(kind);
      if (!(state.catalog?.render_models || []).some(model => model.comfy_name === settings.model_id))
        throw new Error(`Choisis un checkpoint disponible pour le profil ${kind === "character" ? "Personnages" : "Décors"}.`);
      profiles[kind] = {model_id: el(`${prefix}-llm`).value, settings,
        inherit_technical: state.batchProfiles[kind].inheritTechnical};
    }
    const data = await core.request(api("/reference-batches"), send("POST", {
      expected_visual_revision: state.data.visual_revision, request_id: crypto.randomUUID(),
      reference_ids: [...state.batchSelection], profiles,
    }));
    accept(data); el("batch-panel").open = true;
  }
  async function saveScene() {
    await flushRender();
    if (!state.dirtyScene) return;
    const s = scene(), data = await core.request(api(`/scenes/${s.id}`), send("PUT", {expected_revision: s.revision,
      intention: el("intention").value.trim(), duration: Number(el("duration").value), references: state.bindings,
      plan_model_id: el("plan-model").value, writer_model_id: el("writer-model").value,
      shot_count: el("shots").value ? Number(el("shots").value) : null, audacity: Number(el("audacity").value),
      creative_axes: Object.fromEntries(Object.entries(axesIds).map(([axis, id]) => [axis, Number(el(id).value)]))}));
    state.dirtyScene = false; accept(data);
  }
  const template = document.getElementById("ref2vr-lab").cloneNode(true);
  for (const element of [template, ...template.querySelectorAll("*")]) for (const attr of [...element.attributes]) {
    if (attr.value.includes("ref2vr")) element.setAttribute(attr.name, attr.value.replaceAll("ref2vr", "episoder"));
  }
  el("render-host").append(template);
  const renderer = window.PanelForgeH3Render.mount("episoder", "panelforge:episode-render", "ref2va", {
    deferContextChanges: true,
    restoreSetup: true,
    raiseContextErrors: true,
    beforeRender: (parameters, context) => saveRenderAction(parameters, context),
    prepareAttempt: (parameters, context) => prepareSceneRender(parameters, context),
    renderActionState(context) {
      const s = state.data?.scenes.find(value => value.id === context?.scene_id);
      if (!s) return {};
      if (context.preparation_id !== s.preparations.at(-1)?.id)
        return {disabled: true, label: "Sélectionner la dernière préparation pour générer"};
      if (s.input_error || (s.stale && !s.image_refresh_names?.length))
        return {disabled: true, label: "Préparer un nouveau prompt avant le rendu"};
      if (s.image_refresh_names?.length) return {label: "Générer avec les nouvelles images"};
      return {};
    },
    onSetupRender: (parameters, context) => startSceneVideoChain(parameters, context),
    setupActionState(context) {
      const chain = state.data?.video_chain;
      const item = chain?.items?.find(value => value.scene_id === context?.scene_id);
      if (item?.status === "prompt_failed") {
        return {label: "Réessayer prompt + vidéo", status: item.error || "Le prompt a échoué ; le rendu programmé a été annulé.", tone: "error"};
      }
      if (!chain || !["running", "pausing"].includes(chain.status)) {
        return {label: "Générer dès que le prompt est prêt"};
      }
      return {label: item ? "Rendu programmé" : "Chaîne vidéo en cours", disabled: true,
        status: item?.phase || chain.phase, tone: "active"};
    },
    onProjectChange(project, context) { if (context?.episode_id !== state.data?.episode_id) return;
      const s = state.data.scenes.find(s => s.id === context.scene_id); if (s) { s.video_status = project.attempts.at(-1)?.status; drawLists(); drawVideoOverview(); } },
  });
  function videoSetup(parameters) {
    return {recipe: {id: parameters.recipe_id, version: parameters.recipe_version},
      checkpoint: parameters.checkpoint, initial_megapixels: parameters.initial_megapixels,
      settings: {aspect_ratio: parameters.aspect_ratio, megapixels: parameters.megapixels,
        duration_seconds: parameters.duration_seconds, steps: parameters.steps, seed: parameters.seed || 0},
      seed_locked: parameters.seed_locked, music_enabled: parameters.music_enabled, spectrum_enabled: parameters.spectrum_enabled,
      force_upscale: parameters.force_upscale,
      bunny: parameters.bunny, video_loras: parameters.video_loras, video_lora: parameters.video_lora};
  }
  function saveVideo(parameters, context) {
    if (!context?.episode_id) return Promise.resolve();
    parameters = structuredClone(parameters);
    const key = `${context.episode_id}:${context.scene_id}`;
    const task = state.renderSaves.catch(() => {}).then(async () => {
      el("render-save").textContent = "Enregistrement des réglages vidéo…";
      const selected = context.episode_id === state.data?.episode_id
        ? state.data.scenes.find(value => value.id === context.scene_id) : null;
      const setup = videoSetup(parameters);
      const signature = value => JSON.stringify(value, (key, entry) => key === "seed" ? String(entry)
        : entry && typeof entry === "object" && !Array.isArray(entry)
          ? Object.fromEntries(Object.keys(entry).sort().map(name => [name, entry[name]])) : entry);
      if (!selected || signature(setup) !== signature(selected.effective_render_setup || selected.render_setup)) {
        const result = await core.request(api(`/scenes/${context.scene_id}/render-setup`, context.episode_id), send("PUT", {
          expected_revision: state.renderRevision.get(key), parameters}));
        state.renderRevision.set(key, result.render_revision);
        if (selected) {
          selected.render_revision = result.render_revision; selected.render_setup = structuredClone(setup);
          selected.effective_render_setup = structuredClone(setup); selected.inherit_video_settings = false;
        }
      }
      el("render-save").textContent = "Enregistré ✓ · réglages de cette scène";
      if (selected && selected.id === state.sceneId) {
        el("video-settings-note").textContent = "Les modifications sont enregistrées uniquement pour cette scène.";
        el("video-settings-toggle").textContent = selected.inherit_video_settings ? "Personnaliser cette scène" : "Reprendre les réglages communs";
      }
      drawVideoOverview();
    });
    state.renderSaves = task; return task;
  }
  let renderSaveTimer = null;
  let renderDirty = false, renderEdit = 0;
  async function saveRenderAction(parameters, context) {
    const edit = renderEdit;
    clearTimeout(renderSaveTimer); renderSaveTimer = null;
    await saveVideo(parameters, context);
    if (edit === renderEdit) renderDirty = false;
  }
  async function prepareSceneRender(parameters, context) {
    // Save pending narrative edits before the server checks prompt compatibility.
    await saveScene();
    const result = await core.request(api(`/scenes/${context.scene_id}/render-attempts`, context.episode_id), send("POST", {
      preparation_id: context.preparation_id, render_project_id: context.project_id, parameters,
    }));
    context.project_id = result.project.project_id;
    context.preparation_id = result.preparation_id;
    if (context === state.activeRender && context.episode_id === state.data?.episode_id) {
      state.prepId = result.preparation_id; state.renderContext = context.project_id;
      accept(result.episode);
    }
    return result;
  }
  async function persistRender() {
    if (!renderDirty || !state.activeRender) return;
    const context = state.activeRender, edit = renderEdit;
    const deadline = Date.now() + 10000;
    while (renderer.busy) {
      if (Date.now() >= deadline) throw new Error("Les réglages sont encore en cours de chargement. Réessaie dans un instant.");
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    if (context !== state.activeRender) throw new Error("La scène a changé avant la sauvegarde des réglages.");
    await saveVideo(renderer.parameters(), context);
    if (edit === renderEdit) renderDirty = false;
  }
  function queueRenderSave(event) {
    if (event.type === "click" && !event.target.closest("button")) return;
    if (!event.target.closest(".h3-render-setup,.h3-render-settings,.h3-video-lora") && !event.target.id.startsWith("episoder-bunny")) return;
    clearTimeout(renderSaveTimer);
    renderDirty = true; renderEdit += 1;
    el("render-save").textContent = "Enregistrement des réglages vidéo…";
    const context = state.activeRender;
    const persist = async () => {
      renderSaveTimer = null;
      if (!context || context !== state.activeRender) return;
      if (renderer.busy) { renderSaveTimer = setTimeout(persist, 800); return; }
      try { await persistRender(); } catch (error) { el("render-save").textContent = `Non enregistré : ${error.message}`; }
    };
    renderSaveTimer = setTimeout(persist, 800);
  }
  template.addEventListener("change", queueRenderSave);
  template.addEventListener("input", queueRenderSave);
  template.addEventListener("click", queueRenderSave);
  async function flushRender() {
    clearTimeout(renderSaveTimer); renderSaveTimer = null;
    await persistRender();
    await state.renderSaves;
  }
  window.addEventListener("beforeunload", event => {
    if (renderDirty) { event.preventDefault(); event.returnValue = ""; }
  });
  async function openRender() {
    let p = prep(), s = scene();
    let key = p?.render_project_id || `setup:${s?.id || ""}`;
    if (key === state.renderContext) return;
    await flushRender();
    // A poll or navigation may have changed the selection during the save.
    p = prep(); s = scene(); key = p?.render_project_id || `setup:${s?.id || ""}`;
    if (key === state.renderContext) return;
    state.renderContext = key; el("render-save").textContent = "";
    if (!s) { state.activeRender = null; await renderer.close(); return; }
    const setup = p && p.id !== s.preparations.at(-1)?.id ? p.render_setup : (s.effective_render_setup || s.render_setup);
    const context = {project_id: key, preparation_id: p?.id, episode_id: state.data.episode_id, scene_id: s.id, render_setup: setup};
    state.activeRender = context;
    if (!p?.render_project_id && !renderer.openSetup) {
      state.activeRender = null; state.renderContext = ""; await renderer.close(); return;
    }
    try { if (p?.render_project_id) await renderer.open(context); else await renderer.openSetup({...context, project_id: null}); }
    catch (error) { state.renderContext = ""; throw error; }
  }
  async function tab(name) {
    await flushRender(); await saveReference(); await saveScene();
    state.tab = name; el("references").hidden = name !== "references"; el("scenes").hidden = name !== "scenes";
    el("tab-references").setAttribute("aria-pressed", String(name === "references")); el("tab-scenes").setAttribute("aria-pressed", String(name === "scenes"));
    if (name === "scenes") await openRender(); else { await renderer.close(); state.renderContext = ""; state.activeRender = null; }
    storeContext(); schedule();
  }
  async function openEpisode(id, saved = null) {
    await flushRender(); await renderer.close(); state.activeRender = null;
    const token = ++state.token; clearTimeout(state.timer);
    const data = await core.request(api("", id)); if (token !== state.token) return;
    state.dirtyRef = state.dirtyScene = state.dirtyCommon = false; state.data = data; state.imageProject = null; state.prepId = "";
    state.dlssPanels.clear();
    state.videoCards.clear(); el("video-cards").replaceChildren();
    state.batchProfileKey = ""; state.batchThermalKey = "";
    state.batchSelection = new Set(data.references.filter(reference => !reference.continuity_archived && !reference.continuity_state_id && !reference.image_asset_id).map(reference => reference.id));
    el("style-preset").value = "";
    state.refId = data.references.some(r => r.id === saved?.ref) ? saved.ref : data.references[0].id;
    state.sceneId = data.scenes.some(s => s.id === saved?.scene) ? saved.scene : data.scenes[0].id;
    state.renderContext = ""; state.bindings = [];
    accept(data); show(true);
    if (!state.catalog || !state.models.length) catalog().catch(error => message(error.message, true));
    await tab(saved?.tab === "scenes" ? "scenes" : "references"); await imageProject(); schedule();
  }
  async function storyChanged(project) {
    if (state.story?.project_id === project?.project_id) { state.story = project; return; }
    state.story = project; ++state.token; show(false); state.data = null; state.dirtyRef = state.dirtyScene = state.dirtyCommon = false;
    document.getElementById("story-fabrication").hidden = true;
    if (!project) return;
    const data = await core.request(`/api/episodes/stories/${encodeURIComponent(project.project_id)}`);
    if (state.story?.project_id !== project.project_id) return;
    state.list = data.episodes; document.getElementById("story-fabrication").hidden = !data.episodes.length;
  }
  document.getElementById("story-validate").addEventListener("click", () => action(async () => {
    const story = window.PanelForgeStories.current(); if (!story) return;
    const data = await core.request(`/api/episodes/stories/${encodeURIComponent(story.project_id)}`, send("POST", {expected_version: story.version}));
    state.list = (await core.request(`/api/episodes/stories/${encodeURIComponent(story.project_id)}`)).episodes;
    document.getElementById("story-fabrication").hidden = false;
    await openEpisode(data.episode_id); message("Scénario validé. Prépare les personnages et les décors, puis passe aux scènes.");
  }));
  document.getElementById("story-fabrication").addEventListener("click", () => action(async () => {
    let saved; try { saved = JSON.parse(memo.get(state.story.project_id)); } catch (_) {}
    const id = state.list.some(e => e.episode_id === saved?.id) ? saved.id : state.list[0]?.episode_id;
    if (id) await openEpisode(id, saved);
  }));
  el("back").addEventListener("click", () => action(async () => { await flushRender(); await saveReference(); await saveScene(); state.activeRender = null; show(false); }));
  el("refresh").addEventListener("click", () => action(refresh));
  el("versions").addEventListener("change", () => action(async () => { const id = el("versions").value; await saveReference(); await saveScene(); await openEpisode(id); }));
  el("tab-references").addEventListener("click", () => action(() => tab("references")));
  el("tab-scenes").addEventListener("click", () => action(() => tab("scenes")));
  el("reference").addEventListener("change", () => action(async () => { const id = el("reference").value, template = referenceSettingsTemplate();
    await saveReference(); state.refId = id;
    state.imageProject = null; state.dirtyRef = false; el("asset-feedback").value = ""; drawLists(); drawReference(true);
    if (adoptReferenceSettings(template)) message("Réglages LLM et image repris pour cette fiche vierge.");
    await imageProject(); storeContext(); }));
  el("scene").addEventListener("change", () => action(async () => { const id = el("scene").value; await saveScene(); state.sceneId = id;
    state.prepId = ""; state.dirtyScene = false; drawLists(); drawScene(true); await openRender(); storeContext(); }));
  el("preparation").addEventListener("change", () => action(async () => { state.prepId = el("preparation").value; controls(); await openRender(); }));
  el("save-style").addEventListener("click", () => action(async () => { await saveCommon(); message("Style et réglages communs enregistrés pour les prochaines préparations."); }));
  el("apply-preset").addEventListener("click", () => action(async () => {
    const id = el("style-preset").value; await saveReference();
    const data = await core.request(api("/style-preset"), send("PUT", {expected_revision: state.data.visual_revision, preset_id: id || null}));
    el("style-preset").value = id; accept(data); message("Style appliqué. Les fiches personnalisées gardent leurs réglages.");
  }));
  el("refresh-presets").addEventListener("click", () => action(async () => {
    state.presets = (await core.request("/api/image-lab/krea2-assisted/style-presets")).presets; drawStylePresets();
  }));
  el("style-import").addEventListener("change", () => action(async () => {
    const file = el("style-import").files[0]; if (!file) return;
    await saveReference(); const body = new FormData(); body.append("image", file); body.append("expected_revision", state.data.visual_revision);
    const data = await core.request(api("/style-image"), {method: "POST", body});
    el("style-preset").value = ""; accept(data); el("style-import").value = "";
    message("Image de style enregistrée pour les prochains échanges KREA2.");
  }));
  async function styleImage(referenceId) {
    await saveReference();
    const data = await core.request(api("/style-image"), send("PUT", {expected_revision: state.data.visual_revision, reference_id: referenceId}));
    el("style-preset").value = ""; accept(data);
  }
  el("style-use-reference").addEventListener("click", () => action(() => styleImage(state.refId)));
  el("style-remove").addEventListener("click", () => action(() => styleImage(null)));
  el("image-toggle-settings").addEventListener("click", () => {
    if (state.inheritImages) drawImageSettings(imageSettings());
    state.inheritImages = !state.inheritImages; state.dirtyRef = true; drawImageInheritance(); controls();
  });
  el("save-reference").addEventListener("click", () => action(async () => { await saveReference(); message("Fiche enregistrée."); }));
  el("save-scene").addEventListener("click", () => action(async () => { await saveScene(); message("Scène enregistrée."); }));
  el("asset-prompt").addEventListener("click", () => action(async () => { await saveReference(); const r = ref();
    accept(await core.request(api(`/references/${r.id}/prompt`), send("POST", {expected_revision: r.revision, expected_visual_revision: state.data.visual_revision,
      request_id: crypto.randomUUID(), instruction: el("asset-feedback").value.trim()})));
    el("prompt-panel").open = true;
  }));
  el("image-render").addEventListener("click", () => action(async () => { state.dirtyRef = true; await saveReference(); const r = ref();
    accept(await core.request(api(`/references/${r.id}/render`), send("POST", {expected_revision: r.revision, expected_visual_revision: state.data.visual_revision,
      request_id: crypto.randomUUID(), settings: imageSettings()}))); await imageProject(); }));
  el("image-import").addEventListener("change", () => action(async () => { const file = el("image-import").files[0]; if (!file) return;
    await saveReference(); const r = ref(), body = new FormData(); body.append("image", file); body.append("expected_revision", r.revision);
    accept(await core.request(api(`/references/${r.id}/image`), {method: "POST", body})); el("image-import").value = ""; message("Image importée et retenue."); }));
  el("add").addEventListener("click", () => { const r = state.data.references.find(r => r.id === el("add-reference").value); if (!r || state.bindings.length >= 9) return;
    state.bindings.push({reference_id: r.id, role: r.kind === "location" ? "environment_reference" : "subject_reference"}); state.dirtyScene = true; drawBindings(); });
  async function prepareScene(resume) {
    await saveScene(); const s = scene();
    accept(await core.request(api(`/scenes/${s.id}/prompt`), send("POST", {expected_revision: s.revision, request_id: crypto.randomUUID(), resume})));
    state.prepId = scene().preparations.at(-1).id; drawScene(); await openRender();
  }
  async function startVideoChain() {
    await saveScene(); await flushRender();
    const data = await core.request(api("/video-chain"), send("POST", {
      expected_video_revision: state.data.video_revision, request_id: crypto.randomUUID(),
      scene_ids: state.data.scenes.map(value => value.id),
      auto_dlss: true,
    }));
    accept(data); message("Chaîne lancée. Tu peux la mettre en pause après les tâches déjà en cours.");
  }
  async function startSceneVideoChain(parameters, context) {
    if (!context || context.episode_id !== state.data?.episode_id || context.scene_id !== scene()?.id) {
      throw new Error("La scène active a changé. Relance la programmation du rendu.");
    }
    // The render panel is already busy inside this callback; its captured
    // parameters can be saved without waiting for that same action to finish.
    await saveRenderAction(parameters, context);
    await saveScene();
    const wasRunning = jobRunning(scene());
    const data = await core.request(api("/video-chain"), send("POST", {
      expected_video_revision: state.data.video_revision,
      request_id: crypto.randomUUID(),
      scene_ids: [context.scene_id],
      auto_dlss: false,
    }));
    accept(data);
    message(wasRunning
      ? "Rendu armé : il démarrera automatiquement si le prompt aboutit."
      : "Prompt puis rendu vidéo programmés pour cette scène.");
  }
  async function pauseVideoChain(mode = "after_active") {
    const chain = state.data.video_chain; if (!chain) return;
    accept(await core.request(api(`/video-chains/${encodeURIComponent(chain.chain_id)}/pause`),
      send("POST", {mode})));
  }
  async function resumeVideoChain() {
    const chain = state.data.video_chain; if (!chain) return;
    accept(await core.request(api(`/video-chains/${encodeURIComponent(chain.chain_id)}/resume`), {method: "POST"}));
  }
  async function toggleVideoInheritance() {
    await flushRender(); const s = scene();
    const data = await core.request(api(`/scenes/${s.id}/render-inheritance`), send("PUT", {
      expected_revision: s.render_revision, inherit: !s.inherit_video_settings,
    }));
    state.renderContext = ""; accept(data); await openRender();
  }
  el("prepare").addEventListener("click", () => action(() => prepareScene(false)));
  el("resume").addEventListener("click", () => action(() => prepareScene(true)));
  el("refresh-catalog").addEventListener("click", () => action(() => catalog(true)));
  el("scene-calls").addEventListener("click", () => { if (prep()?.session_id) window.PanelForgePromptRecipes.showHistory(`/api/prompt-recipes/history/session/${encodeURIComponent(prep().session_id)}`); });
  el("prompt-recipes").addEventListener("click", () => window.PanelForgePromptRecipes.open({key: "minimax.h3.ref2v.classic.cinematic.planned", version: "1.0.0"}));
  el("image-calls").addEventListener("click", () => window.PanelForgePromptRecipes.showHistory(api(`/references/${ref().id}/calls`)));
  el("image-open").addEventListener("click", () => window.PanelForgeKrea2AssistedLab?.open(ref().krea_project_id));
  el("batch-start").addEventListener("click", () => action(startReferenceBatch));
  el("batch-global-settings").addEventListener("click", () => window.PanelForgeWorkQueue?.open());
  el("batch-cancel").addEventListener("click", () => action(async () => {
    const batch = state.data.reference_batch; if (!batch) return;
    accept(await core.request(api(`/reference-batches/${encodeURIComponent(batch.batch_id)}/cancel`), {method: "POST"}));
  }));
  el("video-start").addEventListener("click", () => action(startVideoChain));
  el("video-global-settings").addEventListener("click", () => window.PanelForgeWorkQueue?.open());
  el("video-pause").addEventListener("click", () => action(() => pauseVideoChain("after_active")));
  el("video-drain").addEventListener("click", () => action(() => pauseVideoChain("after_queue")));
  el("video-resume").addEventListener("click", () => action(resumeVideoChain));
  el("video-settings-toggle").addEventListener("click", () => action(toggleVideoInheritance));
  for (const kind of ["character", "location"]) {
    const prefix = `batch-${kind}`;
    for (const id of ["llm", "model", "preset", "ratio", "mp", "seed"])
      el(`${prefix}-${id}`).addEventListener(["llm", "model", "preset"].includes(id) ? "change" : "input", () => { drawBatch(); controls(); });
    el(`${prefix}-workflow`).addEventListener("change", () => {
      const workflow = state.catalog?.workflows?.find(item => item.id === el(`${prefix}-workflow`).value);
      if (workflow?.default_sampling_preset_id) el(`${prefix}-preset`).value = workflow.default_sampling_preset_id;
      drawBatch(); controls();
    });
    el(`${prefix}-toggle`).addEventListener("click", () => {
      const profile = state.batchProfiles[kind];
      profile.inheritTechnical = !profile.inheritTechnical;
      drawBatch(); controls();
    });
  }
  for (const id of ["description", "asset-model", "asset-local", "asset-text", "image-model", "image-ratio", "image-mp", "image-seed", "image-preset"])
    el(id).addEventListener("input", () => { state.dirtyRef = true; controls(); });
  // The shared checkpoint picker dispatches change rather than input.
  el("image-model").addEventListener("change", () => { state.dirtyRef = true; drawImageInheritance(); controls(); });
  el("image-workflow").addEventListener("change", () => {
    const workflow = state.catalog?.workflows?.find(item => item.id === el("image-workflow").value);
    if (workflow?.default_sampling_preset_id) el("image-preset").value = workflow.default_sampling_preset_id;
    state.dirtyRef = true; drawImageInheritance(); controls();
  });
  for (const id of ["style", "common-model", "common-preset"]) el(id).addEventListener(id === "style" ? "input" : "change", commonChanged);
  el("common-workflow").addEventListener("change", () => {
    const workflow = state.catalog?.workflows?.find(item => item.id === el("common-workflow").value);
    if (workflow?.default_sampling_preset_id) el("common-preset").value = workflow.default_sampling_preset_id;
    commonChanged();
  });
  function updateAxes() {
    for (const id of ["audacity", ...Object.values(axesIds)]) el(`${id}-value`).value = el(id).value;
  }
  for (const id of ["intention", "duration", "plan-model", "writer-model", "plan-local", "writer-local", "shots", "audacity", ...Object.values(axesIds)])
    el(id).addEventListener("input", () => { state.dirtyScene = true; updateAxes(); controls(); });
  window.addEventListener("panelforge:story", event => storyChanged(event.detail).catch(error => message(error.message, true)));
  new MutationObserver(() => { if (!document.getElementById("stories-workspace").hidden) schedule(); else clearTimeout(state.timer); })
    .observe(document.getElementById("stories-workspace"), {attributes: true, attributeFilter: ["hidden"]});
  state.cooldownTicker = setInterval(() => {
    if (state.data?.video_chain && cooldownRemaining(state.data.video_chain) > 0) drawVideoOverview();
  }, 1000);
  window.addEventListener("beforeunload", () => { clearTimeout(state.timer); clearTimeout(renderSaveTimer); clearInterval(state.cooldownTicker); });
  storyChanged(window.PanelForgeStories?.current()).catch(error => message(error.message, true));
})();
