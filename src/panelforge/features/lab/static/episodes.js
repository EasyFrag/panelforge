(() => {
  "use strict";
  const core = window.PanelForgeLabCore, picker = window.PanelForgeModelPicker, resources = window.PanelForgeKrea2ResourceUi;
  const root = document.getElementById("episode-workshop"), el = id => document.getElementById(`episode-${id}`);
  if (!root || !core || !picker || !resources || !window.PanelForgeH3Render) return;
  const state = { story: null, data: null, list: [], refId: "", sceneId: "", prepId: "", tab: "references",
    models: [], catalog: null, imageProject: null, busy: false, token: 0, timer: null,
    dirtyRef: false, dirtyScene: false, dirtyCommon: false, inheritImages: true, loras: [], commonLoras: [], presets: [],
    batchProfiles: {character: {loras: [], sampling: null}, location: {loras: [], sampling: null}},
    batchSelection: new Set(), batchProfileKey: "", batchThermalKey: "",
    renderContext: "", renderSaves: Promise.resolve(), renderRevision: new Map() };
  const axesIds = {scene_life: "creative-scene-life", camera: "creative-camera", extra_motion: "creative-extra-motion", dialogue: "creative-dialogue"};
  const initialAxes = {scene_life: 1, camera: 2, extra_motion: 1, dialogue: 0};
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
  const scene = () => state.data?.scenes.find(s => s.id === state.sceneId);
  const prep = () => scene()?.preparations.find(p => p.id === state.prepId);
  const api = (suffix = "", id = state.data?.episode_id) => `/api/episodes/${encodeURIComponent(id)}${suffix}`;
  const send = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const node = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, action) => { const b = node("button", text); b.type = "button"; b.addEventListener("click", action); return b; };
  const assetUrl = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const jobRunning = item => item?.job?.status === "running";
  const batchRunning = () => ["running", "rendering", "cancelling"].includes(state.data?.reference_batch?.status);
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
    catch (error) { message(error.message, true); }
    finally { state.busy = false; controls(); schedule(); }
  }
  function controls() {
    const r = ref(), s = scene(), busyRef = state.busy || jobRunning(r), busyScene = state.busy || jobRunning(s);
    for (const id of ["story-projects", "story-new", "story-fabrication"]) document.getElementById(id).disabled = state.busy;
    document.getElementById("story-validate").disabled = state.busy || !state.story?.document?.scenario
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
    el("batch-start").disabled = state.busy || batchRunning() || !state.catalog || !state.models.length || !state.batchSelection.size;
    el("batch-cancel").hidden = !batchRunning();
    el("batch-cancel").disabled = state.busy || state.data?.reference_batch?.status === "cancelling";
    drawLoras();
    drawBatchLoras();
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
    el("style-preset").replaceChildren(new Option("Style personnalisé", ""), ...state.presets.map(p => new Option(p.name, p.preset_id)));
    if (active && !state.presets.some(p => p.preset_id === active.preset_id))
      el("style-preset").add(new Option(`${active.name} · copie de l’épisode`, active.preset_id));
    el("style-preset").value = selected || active?.preset_id || "";
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
    const sampling = state.catalog?.sampling.presets.find(p => p.id === el(`${prefix}-preset`).value)?.settings || profile.sampling;
    return {workflow: el(`${prefix}-workflow`).value, model_id: el(`${prefix}-model`).value,
      aspect_ratio: el(`${prefix}-ratio`).value, megapixels: Number(el(`${prefix}-mp`).value),
      seed: el(`${prefix}-seed`).value.trim() || null, loras: structuredClone(profile.loras), ...(sampling ? {sampling} : {})};
  }
  function hydrateBatchProfiles(force = false) {
    if (!state.data || !state.catalog || !state.models.length) return;
    const key = `${state.data.episode_id}:${JSON.stringify(state.data.reference_profiles || {})}`;
    if (!force && state.batchProfileKey === key) return;
    for (const kind of ["character", "location"]) {
      const stored = state.data.reference_profiles?.[kind];
      const sample = state.data.references.find(item => item.kind === kind);
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
      state.batchProfiles[kind] = {loras: structuredClone(settings.loras || []), sampling: settings.sampling};
    }
    state.batchProfileKey = key;
    const thermal = state.data.reference_batch?.thermal || state.data.machine_work?.policy;
    const thermalKey = `${state.data.episode_id}:${JSON.stringify(thermal || {})}`;
    if (thermal && (force || state.batchThermalKey !== thermalKey)) {
      el("batch-stop-temp").value = String(thermal.stop_temperature_c ?? 85);
      el("batch-resume-temp").value = String(thermal.resume_temperature_c ?? 40);
      el("batch-cooldown").value = String(thermal.cooldown_seconds ?? 120);
      state.batchThermalKey = thermalKey;
    }
    drawBatchLoras(); drawBatch();
  }
  function batchProfileSummary(kind) {
    if (!state.catalog || !state.models.length) return "Catalogue en cours de chargement";
    const prefix = `batch-${kind}`, workflowId = el(`${prefix}-workflow`).value, modelId = el(`${prefix}-model`).value;
    const workflow = state.catalog.workflows.find(item => item.id === workflowId);
    const model = state.catalog.render_models.find(item => item.comfy_name === modelId);
    const llm = state.models.find(item => item.id === el(`${prefix}-llm`).value);
    const preset = state.catalog.sampling.presets.find(item => item.id === el(`${prefix}-preset`).value);
    return `${llm?.label || llm?.display_name || el(`${prefix}-llm`).value} · ${workflow?.label || workflowId} · ${model?.display_name || modelId} · ${preset?.label || el(`${prefix}-preset`).value}`;
  }
  function drawBatch() {
    if (!state.data) return;
    const active = batchRunning(), batch = state.data.reference_batch;
    const selectedItems = new Map((batch?.items || []).map(item => [item.reference_id, item]));
    el("batch-selection").replaceChildren(...state.data.references.map(reference => {
      const label = node("label"), checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = active ? selectedItems.has(reference.id) : state.batchSelection.has(reference.id);
      checkbox.disabled = active; checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.batchSelection.add(reference.id); else state.batchSelection.delete(reference.id);
        controls();
      });
      label.append(checkbox, node("b", `${reference.kind === "character" ? "Personnage" : "Décor"} · ${reference.name}`),
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
      card.append(node("b", `${item.kind === "character" ? "Personnage" : "Décor"} · ${item.name}`));
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
    drawImageInheritance(); controls();
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
  function drawLists() {
    if (!state.data) return;
    el("versions").replaceChildren(...state.list.map(e => new Option(`Scénario v${e.story_revision} · ${e.title}`, e.episode_id)));
    el("versions").value = state.data.episode_id;
    el("source").textContent = `Scénario v${state.data.story_revision} · ${state.data.references.length} fiches · ${state.data.scenes.length} scènes.`
      + (state.data.story_changed ? " L’histoire a changé depuis cette validation ; cette fabrication conserve sa version." : "");
    el("reference").replaceChildren(...state.data.references.map(r => new Option(`${r.kind === "character" ? "Personnage" : "Décor"} · ${r.name}${r.image_asset_id ? " ✓" : ""}${r.prompt_style_stale || r.image_style_status === "outdated" ? " · Style à actualiser" : ""}`, r.id)));
    el("reference").value = state.refId;
    el("reference-count").textContent = `${state.data.references.filter(r => r.image_asset_id).length} / ${state.data.references.length} images retenues`;
    el("scene").replaceChildren(...state.data.scenes.map(s => new Option(`${s.index + 1} · ${s.title} · ${s.duration} s · ${
      s.stale ? "À actualiser" : statuses[s.video_status] || (jobRunning(s) ? "Prompt en cours" : statuses[s.preparations.at(-1)?.status]) || "À préparer"}`, s.id)));
    el("scene").value = state.sceneId;
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
    el("image-style-note").textContent = r.image_style_status === "outdated"
      ? "Cette image provient d’une ancienne direction de style. Elle reste retenue jusqu’à ton prochain choix."
      : r.image_style_status === "current" ? "Image préparée avec le style commun actuel."
      : "Style de cette image non documenté : vérifie sa cohérence avec l’épisode.";
    el("asset-status").textContent = r.job?.error || (jobRunning(r) ? r.job.phase : imageRunning() ? "Image en cours de génération…" : "");
    el("image-calls").hidden = !r.krea_project_id; el("image-open").hidden = !r.krea_project_id;
    const items = [...r.images.map(i => ({...i, status: "succeeded", output_asset_id: i.asset_id})), ...(state.imageProject?.attempts || [])];
    el("image-attempts").replaceChildren(...items.slice().reverse().map(a => {
      const selected = a.output_asset_id === r.image_asset_id;
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
    const used = new Set(state.bindings.map(b => b.reference_id));
    el("add-reference").replaceChildren(...state.data.references.filter(r => !used.has(r.id)).map(r => new Option(r.name, r.id)));
    el("reference-limit").textContent = `${state.bindings.length} / 9 images`;
    el("scene-references").replaceChildren(...state.bindings.map((binding, index) => {
      const r = state.data.references.find(r => r.id === binding.reference_id), card = node("article", "", "episode-reference-card");
      if (r.image_asset_id) { const img = node("img"); img.src = assetUrl(r.image_asset_id); img.alt = r.name; card.append(img); }
      else card.append(node("p", "Image à préparer", "muted"));
      card.append(node("strong", `<Picture ${index + 1}> · ${r.name}`));
      const select = node("select"); select.setAttribute("aria-label", `Rôle de ${r.name}`);
      select.append(...Object.entries(roles).map(([key, label]) => new Option(label, key))); select.value = binding.role;
      select.addEventListener("change", () => { binding.role = select.value; state.dirtyScene = true; controls(); }); card.append(select);
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
    el("scene-state").textContent = s.input_error || (s.stale ? "Les références ou l’intention ont changé. Les anciens prompts et rendus sont conservés ; prépare un nouveau prompt pour appliquer ces changements." : "Les références sont prêtes. Les dialogues sont ajoutés automatiquement.");
    el("prompt-status").textContent = s.job?.error || (jobRunning(s) ? s.job.phase : "");
    el("preparation-label").hidden = !s.preparations.length;
    el("preparation").replaceChildren(...[...s.preparations].reverse().map((p, index) => new Option(`Préparation ${s.preparations.length - index} · ${statuses[p.status] || p.status}`, p.id)));
    if (!s.preparations.some(p => p.id === state.prepId)) state.prepId = s.preparations.at(-1)?.id || "";
    el("preparation").value = state.prepId; controls();
  }
  function accept(data) {
    // A poll may have started just before a settings save completed. Keep the
    // newer local snapshot until the next response includes its revision.
    if (state.data?.episode_id === data.episode_id && state.data.visual_revision > (data.visual_revision || 1))
      for (const key of ["style", "style_image", "style_preset", "image_defaults", "visual_revision"]) data[key] = structuredClone(state.data[key]);
    if (state.data?.episode_id === data.episode_id) for (const s of data.scenes) {
      const local = state.data.scenes.find(old => old.id === s.id);
      if (local && local.render_revision > s.render_revision) {
        s.render_setup = structuredClone(local.render_setup); s.render_revision = local.render_revision;
      }
    }
    state.data = data;
    for (const s of data.scenes) { const key = `${data.episode_id}:${s.id}`;
      state.renderRevision.set(key, Math.max(s.render_revision, state.renderRevision.get(key) || 0)); }
    drawLists(); drawVisual(); drawReference(); drawScene(); hydrateBatchProfiles(); drawBatch(); controls();
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
    const running = [...state.data.references, ...state.data.scenes].some(jobRunning) || imageRunning() || batchRunning();
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
    const stop = Number(el("batch-stop-temp").value), resume = Number(el("batch-resume-temp").value);
    if (!(resume < stop)) throw new Error("La température de reprise doit être inférieure au seuil de pause.");
    const profiles = {};
    for (const kind of ["character", "location"]) {
      const prefix = `batch-${kind}`;
      if (!knownModel(el(`${prefix}-llm`).value)) throw new Error(`Choisis un LLM disponible pour le profil ${kind === "character" ? "Personnages" : "Décors"}.`);
      if (!(state.catalog?.render_models || []).some(model => model.comfy_name === el(`${prefix}-model`).value))
        throw new Error(`Choisis un checkpoint disponible pour le profil ${kind === "character" ? "Personnages" : "Décors"}.`);
      profiles[kind] = {model_id: el(`${prefix}-llm`).value, settings: batchSettings(kind)};
    }
    const data = await core.request(api("/reference-batches"), send("POST", {
      expected_visual_revision: state.data.visual_revision, request_id: crypto.randomUUID(),
      reference_ids: [...state.batchSelection], profiles,
      thermal: {stop_temperature_c: stop, resume_temperature_c: resume,
        cooldown_seconds: Number(el("batch-cooldown").value), monitor_local: true,
        monitor_remote: true, pause_when_unavailable: false},
    }));
    accept(data); el("batch-panel").open = true;
  }
  async function saveScene() {
    if (!state.dirtyScene) return;
    await flushRender();
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
    beforeRender: (parameters, context) => saveVideo(parameters, context),
    onProjectChange(project, context) { if (context?.episode_id !== state.data?.episode_id) return;
      const s = state.data.scenes.find(s => s.id === context.scene_id); if (s) { s.video_status = project.attempts.at(-1)?.status; drawLists(); } },
  });
  function saveVideo(parameters, context) {
    if (!context?.episode_id) return Promise.resolve();
    const key = `${context.episode_id}:${context.scene_id}`;
    const task = state.renderSaves.catch(() => {}).then(async () => {
      el("render-save").textContent = "Enregistrement des réglages vidéo…";
      const result = await core.request(api(`/scenes/${context.scene_id}/render-setup`, context.episode_id), send("PUT", {
        expected_revision: state.renderRevision.get(key), parameters}));
      state.renderRevision.set(key, result.render_revision);
      if (context.episode_id === state.data?.episode_id) {
        const s = state.data.scenes.find(s => s.id === context.scene_id);
        if (s) {
          s.render_revision = result.render_revision;
          s.render_setup = {recipe: {id: parameters.recipe_id, version: parameters.recipe_version},
            checkpoint: parameters.checkpoint, initial_megapixels: parameters.initial_megapixels,
            settings: {aspect_ratio: parameters.aspect_ratio, megapixels: parameters.megapixels,
              duration_seconds: parameters.duration_seconds, steps: parameters.steps, seed: parameters.seed || 0},
            seed_locked: parameters.seed_locked, music_enabled: parameters.music_enabled, spectrum_enabled: parameters.spectrum_enabled,
            bunny: parameters.bunny, video_loras: parameters.video_loras, video_lora: parameters.video_lora};
        }
      }
      el("render-save").textContent = "Réglages vidéo enregistrés pour cette scène.";
    });
    state.renderSaves = task; return task;
  }
  let renderSaveTimer = null;
  function queueRenderSave(event) {
    if (event.type === "click" && !event.target.closest("button")) return;
    if (!event.target.closest(".h3-render-setup,.h3-render-settings,.h3-video-lora") && !event.target.id.startsWith("episoder-bunny")) return;
    clearTimeout(renderSaveTimer);
    const context = state.activeRender;
    const persist = async () => {
      renderSaveTimer = null;
      if (!context || context !== state.activeRender) return;
      if (renderer.busy) { renderSaveTimer = setTimeout(persist, 800); return; }
      try { await saveVideo(renderer.parameters(), context); } catch (error) { el("render-save").textContent = error.message; }
    };
    renderSaveTimer = setTimeout(persist, 800);
  }
  template.addEventListener("change", queueRenderSave);
  template.addEventListener("click", queueRenderSave);
  async function flushRender() {
    if (renderSaveTimer !== null && state.activeRender && !renderer.busy) {
      clearTimeout(renderSaveTimer); renderSaveTimer = null;
      await saveVideo(renderer.parameters(), state.activeRender);
    }
    await state.renderSaves;
  }
  async function openRender() {
    const p = prep(), s = scene();
    const key = p?.render_project_id || "";
    if (key === state.renderContext) return;
    await flushRender();
    state.renderContext = key; el("render-save").textContent = "";
    if (!key) { state.activeRender = null; await renderer.close(); return; }
    const setup = p.id === s.preparations.at(-1)?.id ? s.render_setup : p.render_setup;
    const context = {project_id: key, episode_id: state.data.episode_id, scene_id: s.id, render_setup: setup};
    state.activeRender = context;
    try { await renderer.open(context); }
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
    state.batchProfileKey = ""; state.batchThermalKey = "";
    state.batchSelection = new Set(data.references.filter(reference => !reference.image_asset_id).map(reference => reference.id));
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
    state.bindings.push({reference_id: r.id, role: r.kind === "character" ? "subject_reference" : "environment_reference"}); state.dirtyScene = true; drawBindings(); });
  async function prepareScene(resume) {
    await saveScene(); const s = scene();
    accept(await core.request(api(`/scenes/${s.id}/prompt`), send("POST", {expected_revision: s.revision, request_id: crypto.randomUUID(), resume})));
    state.prepId = scene().preparations.at(-1).id; drawScene(); await openRender();
  }
  el("prepare").addEventListener("click", () => action(() => prepareScene(false)));
  el("resume").addEventListener("click", () => action(() => prepareScene(true)));
  el("refresh-catalog").addEventListener("click", () => action(() => catalog(true)));
  el("scene-calls").addEventListener("click", () => { if (prep()?.session_id) window.PanelForgePromptRecipes.showHistory(`/api/prompt-recipes/history/session/${encodeURIComponent(prep().session_id)}`); });
  el("prompt-recipes").addEventListener("click", () => window.PanelForgePromptRecipes.open({key: "minimax.h3.ref2v.classic.cinematic.planned", version: "1.0.0"}));
  el("image-calls").addEventListener("click", () => window.PanelForgePromptRecipes.showHistory(api(`/references/${ref().id}/calls`)));
  el("image-open").addEventListener("click", () => window.PanelForgeKrea2AssistedLab?.open(ref().krea_project_id));
  el("batch-start").addEventListener("click", () => action(startReferenceBatch));
  el("batch-cancel").addEventListener("click", () => action(async () => {
    const batch = state.data.reference_batch; if (!batch) return;
    accept(await core.request(api(`/reference-batches/${encodeURIComponent(batch.batch_id)}/cancel`), {method: "POST"}));
  }));
  for (const kind of ["character", "location"]) {
    const prefix = `batch-${kind}`;
    for (const id of ["llm", "model", "preset", "ratio", "mp", "seed"])
      el(`${prefix}-${id}`).addEventListener(id === "model" || id === "preset" ? "change" : "input", () => { drawBatch(); controls(); });
    el(`${prefix}-workflow`).addEventListener("change", () => {
      const workflow = state.catalog?.workflows?.find(item => item.id === el(`${prefix}-workflow`).value);
      if (workflow?.default_sampling_preset_id) el(`${prefix}-preset`).value = workflow.default_sampling_preset_id;
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
  window.addEventListener("beforeunload", () => { clearTimeout(state.timer); clearTimeout(renderSaveTimer); });
  storyChanged(window.PanelForgeStories?.current()).catch(error => message(error.message, true));
})();
