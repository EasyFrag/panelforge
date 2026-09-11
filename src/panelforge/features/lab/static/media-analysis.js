(() => {
  "use strict";
  const core = window.PanelForgeLabCore, media = window.PanelForgeAnalysisMedia;
  const root = document.querySelector("#media-analysis-workspace");
  if (!root || !core || !media) return;
  const el = id => document.getElementById(`ma-${id}`);
  const state = { initialized: false, initializing: null, busy: false, frames: [], video: null, videoUrl: null,
    sourceKind: "images", sourceName: "Images", clip: null, extractedClip: null, record: null, signature: null, extraRefs: [], controller: null };
  const speech = window.PanelForgeAnalysisSpeech.create({ el, context: () => state, onChange: update, setBusy: busy, message });
  const roles = [["", "Ne pas utiliser"], ["subject_reference", "Sujet / identité"], ["first_frame", "Première frame exacte"],
    ["last_frame", "Dernière frame exacte"], ["environment_reference", "Décor"], ["composition_reference", "Composition"],
    ["style_reference", "Style"], ["motion_reference", "Mouvement"], ["keyframe_reference", "Keyframe"]];
  const assetUrl = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const pools = () => [...state.frames, ...state.extraRefs];
  function message(text, error = false) { el("message").textContent = text; el("message").classList.toggle("error", error); }
  function revoke(frame) { if (frame.url?.startsWith("blob:")) URL.revokeObjectURL(frame.url); }
  function frameFor(file, time = null) { return { id: crypto.randomUUID(), file, label: file.name.slice(0,240), url: URL.createObjectURL(file), time, role: "" }; }
  function metadata() {
    return { frames: state.frames.map(f => ({ label: f.label, time_seconds: f.time })), model_id: el("model").value,
      instruction: el("instruction").value.trim(), source_kind: state.sourceKind, source_name: state.sourceName,
      duration_seconds: Number(el("duration").value), clip_start_seconds: state.clip?.start ?? null,
      clip_end_seconds: state.clip?.end ?? null, source_duration_seconds: state.clip?.duration ?? null, transcript: speech.metadata() };
  }
  function fingerprint() { return JSON.stringify({ ...metadata(), images: state.frames.map(f => f.id), speech: speech.signature() }); }
  function currentResult() { return state.record?.status === "succeeded" && state.signature === fingerprint(); }
  function validation() {
    const speechError = speech.validation(); if (speechError) return speechError;
    if (state.sourceKind === "video" && (!state.clip || JSON.stringify(state.clip) !== state.extractedClip)) return "Actualisez les captures pour analyser l’extrait sélectionné.";
    return media.timelineError(state.frames, Number(el("duration").value), state.clip ? state.clip.end - state.clip.start : null);
  }
  function update() {
    const error = validation(); el("timeline-error").textContent = error;
    el("count").textContent = `${state.frames.length} / 16 images`;
    el("analyze").disabled = state.busy || Boolean(error) || !el("model").value;
    for (const id of ["save", "h3", "ref2v"]) el(id).disabled = state.busy || !currentResult() || !el("intention").value.trim();
    el("copy").disabled = !el("intention").value.trim();
    el("stale").hidden = !el("intention").value || currentResult();
    el("capture").disabled = state.busy || !state.video;
    el("capture-current").disabled = state.busy || !state.video || state.frames.length >= 16;
    el("add-images-control").hidden = state.sourceKind !== "images" || !state.frames.length;
    speech.update(state.busy);
  }
  function busy(value, label = "") {
    state.busy = value;
    root.querySelectorAll("[data-ma-input] input, [data-ma-input] textarea, [data-ma-input] select, [data-ma-input] button").forEach(e => { e.disabled = value || e.dataset.fixedDisabled === "true"; });
    el("cancel").disabled = !value; el("progress").hidden = !value;
    el("intention").readOnly = value;
    if (value) { el("progress").removeAttribute("value"); if (label) message(label); }
    update();
  }
  async function initialize() {
    if (state.initialized) return;
    if (state.initializing) return state.initializing;
    state.initializing = (async () => {
      const [spec] = await Promise.all([core.request("/api/media-analysis/spec"), history()]);
      window.PanelForgeModelPicker.populate(el("model"), spec.llm_models || [], el("model").value);
      speech.setSpec(spec.transcription);
      state.initialized = true; update();
    })();
    try { await state.initializing; } finally { state.initializing = null; }
  }
  async function history() {
    const result = await core.request("/api/media-analysis/analyses?limit=3");
    el("history").replaceChildren();
    for (const record of result.analyses || []) {
      const button = document.createElement("button"); button.type = "button";
      button.textContent = `${record.request.source_name} · ${record.status === "succeeded" ? "Terminée" : "À reprendre"}`;
      button.addEventListener("click", () => openRecord(record)); el("history").append(button);
    }
  }
  function clearMedia() {
    speech.reset();
    state.frames.forEach(revoke); state.extraRefs.forEach(revoke); state.frames = []; state.extraRefs = [];
    if (state.videoUrl) URL.revokeObjectURL(state.videoUrl);
    state.videoUrl = null; state.video = null; state.clip = null; state.extractedClip = null;
    el("video").removeAttribute("src"); el("video").load(); el("video-controls").hidden = true;
  }
  async function selectFiles() {
    if (state.busy) return;
    const files = [...el("files").files]; el("files").value = "";
    if (!files.length) return;
    const video = files.find(f => f.type.startsWith("video/") || /\.(mp4|webm|mov|m4v)$/i.test(f.name));
    if ((video && files.length !== 1) || files.length > 16) return message("Choisissez une vidéo seule, ou jusqu’à 16 images.", true);
    if (!video && files.some(f => !["image/jpeg", "image/png", "image/webp"].includes(f.type))) return message("Utilisez des images PNG, JPEG ou WebP.", true);
    busy(true, "Lecture du média…"); state.controller = new AbortController();
    try {
      clearMedia(); state.sourceKind = video ? "video" : "images"; state.sourceName = video ? video.name.slice(0,240) : files.length === 1 ? files[0].name.slice(0,240) : `${files.length} images`;
      if (video) {
        state.video = video; state.videoUrl = URL.createObjectURL(video); el("video-controls").hidden = false;
        const loaded = media.wait(el("video"), "loadedmetadata", state.controller.signal);
        el("video").src = state.videoUrl; el("video").load(); await loaded;
        const duration = el("video").duration;
        if (!Number.isFinite(duration) || duration < .1 || duration > 86400) throw new Error("Durée vidéo illisible ou non prise en charge.");
        state.clip = { start: 0, end: Math.min(duration, 10), duration }; setRange();
        el("duration").value = String(Math.max(5, Math.min(duration, 10)));
      } else state.frames = files.map(f => frameFor(f));
      drawFrames(); drawReferences(); message(video ? "Choisissez l’extrait, puis préparez ses captures." : "Vous pouvez réordonner les images et préciser leurs temps.");
    } catch (error) { message(error.message, true); }
    finally { busy(false); }
  }
  function setRange() {
    if (!state.clip) return;
    for (const kind of ["start", "end"]) for (const suffix of ["", "-range"]) {
      el(kind + suffix).max = String(state.clip.duration); el(kind + suffix).value = String(state.clip[kind]);
    }
    el("range-label").textContent = `Extrait ${state.clip.start.toFixed(2)} → ${state.clip.end.toFixed(2)} s · durée ${(state.clip.end-state.clip.start).toFixed(2)} s`;
    el("selection").style.left = `${100*state.clip.start/state.clip.duration}%`;
    el("selection").style.width = `${100*(state.clip.end-state.clip.start)/state.clip.duration}%`;
  }
  function changeRange(kind, value) {
    if (state.busy || !state.clip || !Number.isFinite(value)) return;
    const before = state.clip.end - state.clip.start;
    state.clip[kind] = Math.max(0, Math.min(state.clip.duration, value));
    if (kind === "start" && state.clip.start >= state.clip.end) state.clip.start = Math.max(0, state.clip.end - .1);
    if (kind === "end" && state.clip.end <= state.clip.start) state.clip.end = Math.min(state.clip.duration, state.clip.start + .1);
    if (Math.abs(Number(el("duration").value) - Math.max(5, Math.min(15, before))) < .01) el("duration").value = String(Math.max(5, Math.min(15, Number((state.clip.end-state.clip.start).toFixed(3)))));
    el("video").pause(); el("video").currentTime = state.clip[kind]; setRange(); update();
  }
  async function extract(currentOnly = false) {
    if (state.busy || !state.video || !state.clip) return;
    const clip = { ...state.clip };
    try {
      if (currentOnly && state.extractedClip !== JSON.stringify(clip)) throw new Error("Préparez d’abord les captures de cet extrait.");
      let times = media.sampleTimes(clip.start, clip.end, Number(el("samples").value), clip.duration);
      if (currentOnly) {
        const time = el("video").currentTime;
        if (time < clip.start || time > clip.end) throw new Error("Placez le lecteur dans l’extrait.");
        if (state.frames.some(f => Math.abs(f.time - (time - clip.start)) < .01)) throw new Error("Une capture existe déjà à cet instant.");
        times = [time];
      }
      busy(true, "Extraction des captures…"); state.controller = new AbortController();
      const contents = await media.capture(state.video, times, (i, count) => {
        el("progress").value = i / count; message(`Extraction : ${i} / ${count} images`);
      }, state.controller.signal);
      const frames = contents.map((blob,i) => frameFor(new File([blob], `Capture ${(times[i]-clip.start).toFixed(3)} s.jpg`, { type: blob.type }), Number((times[i]-clip.start).toFixed(3))));
      if (currentOnly) state.frames.push(...frames); else { state.frames.forEach(revoke); state.frames = frames; }
      state.frames.sort((a,b) => a.time-b.time); state.extractedClip = JSON.stringify(clip);
      drawFrames(); drawReferences(); message("Captures prêtes. Vous pouvez en retirer ou en ajouter depuis le lecteur.");
    } catch (error) { message(error.name === "AbortError" ? "Extraction annulée. Le brouillon est conservé." : error.message, true); }
    finally { busy(false); }
  }
  function drawFrames() {
    el("frames").replaceChildren();
    state.frames.forEach((frame, i) => {
      const card = document.createElement("article"); card.className = "ma-frame"; card.dataset.frameId = frame.id;
      const zoom = document.createElement("a"); zoom.href = frame.url; zoom.target = "_blank"; zoom.rel = "noopener"; zoom.title = "Agrandir l’image";
      const image = document.createElement("img"); image.src = frame.url; image.alt = frame.label; zoom.append(image); card.append(zoom);
      const caption = document.createElement("b"); caption.textContent = `${i+1}. ${frame.label}`; card.append(caption);
      const label = document.createElement("label"); label.textContent = "Temps (s) — facultatif";
      const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.step = "any"; input.placeholder = "Non précisé";
      input.value = frame.time == null ? "" : String(frame.time); input.readOnly = state.sourceKind === "video";
      input.addEventListener("input", () => { frame.time = input.value === "" ? null : Number(input.value); update(); }); label.append(input); card.append(label);
      const actions = document.createElement("div"); actions.className = "ma-actions";
      for (const [text, offset] of [["←", -1], ["→", 1]]) {
        const button = document.createElement("button"); button.type = "button"; button.textContent = text; button.title = offset < 0 ? "Déplacer avant" : "Déplacer après";
        button.disabled = state.sourceKind === "video" || i+offset<0 || i+offset>=state.frames.length;
        button.dataset.fixedDisabled = String(button.disabled);
        button.addEventListener("click", () => { if (state.busy || state.sourceKind === "video" || i+offset<0 || i+offset>=state.frames.length) return; [state.frames[i],state.frames[i+offset]] = [state.frames[i+offset],state.frames[i]]; drawFrames(); drawReferences(); update(); }); actions.append(button);
      }
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Retirer";
      remove.addEventListener("click", () => { if (state.busy) return; state.frames.splice(i,1); revoke(frame); drawFrames(); drawReferences(); update(); }); actions.append(remove); card.append(actions);
      el("frames").append(card);
    }); update();
  }
  function drawReferences() {
    for (const id of ["first", "last"]) {
      const select = el(id), old = select.value; select.replaceChildren(new Option("Aucune", ""));
      pools().forEach((f,i) => select.add(new Option(`${i+1}. ${f.label}`, f.id))); select.value = pools().some(f=>f.id===old) ? old : "";
    }
    el("ref-list").replaceChildren();
    pools().forEach(frame => {
      const row = document.createElement("label"); row.className = "ma-reference";
      const image = document.createElement("img"); image.src=frame.url; image.alt=frame.label;
      const text=document.createElement("span"); text.textContent=frame.label;
      const select=document.createElement("select"); select.setAttribute("aria-label", `Rôle REF2V : ${frame.label}`);
      roles.forEach(([value,label])=>select.add(new Option(label,value))); select.value=frame.role;
      select.addEventListener("change",()=>{frame.role=select.value;}); row.append(image,text,select);
      if(state.extraRefs.includes(frame)) {
        const remove=document.createElement("button"); remove.type="button"; remove.textContent="Retirer cette référence";
        remove.addEventListener("click",()=>{if(state.busy)return;state.extraRefs=state.extraRefs.filter(f=>f!==frame);revoke(frame);drawReferences();}); row.append(remove);
      }
      el("ref-list").append(row);
    });
  }
  async function fileFor(frame) {
    if (frame.file) return frame.file;
    const response=await fetch(assetUrl(frame.assetId)); if(!response.ok) throw new Error(`Image indisponible : ${frame.label}`);
    const blob=await response.blob(); if(!blob.type.startsWith("image/")) throw new Error("La référence n’est pas une image.");
    return new File([blob],frame.label,{type:blob.type});
  }
  async function analyze() {
    if(state.busy) return;
    try {
      await initialize(); const error=validation(); if(error) throw new Error(error);
      if(!el("model").value) throw new Error("Choisissez un modèle multimodal.");
      busy(true,"Envoi des images…"); state.controller=new AbortController();
      const signature=fingerprint();
      if(!state.record || state.signature!==signature || state.record.status==="succeeded") {
        const form=new FormData(); form.append("metadata",JSON.stringify(metadata()));
        for(const frame of state.frames) form.append("files",await fileFor(frame),frame.label);
        state.record=await core.request("/api/media-analysis/analyses",{method:"POST",body:form,signal:state.controller.signal}); state.signature=signature;
      }
      message("Analyse visuelle en cours… Vous pouvez utiliser les autres ateliers."); el("trace").textContent="";
      let result=null;
      await core.streamRequest(`/api/media-analysis/analyses/${state.record.analysis_id}/stream?include_reasoning=${el("reasoning").checked}`,{
        method:"POST",signal:state.controller.signal
      },event=>{
        if(event.kind==="reasoning" && el("reasoning").checked) el("trace").textContent+=event.text||"";
        if(event.kind==="status") message(event.text || "Analyse en cours…");
        if(event.kind==="completed") { if(event.error) throw new Error(event.error); result=event.record; }
      },{completionTone:true});
      if(!result) throw new Error("L’analyse s’est interrompue. Réessayez avec les mêmes images.");
      state.record=result; showResult(); message(result.intention_warning || "Intention prête. Relisez-la, puis choisissez H3 ou REF2V.", Boolean(result.intention_warning)); await history();
    } catch(error) { message(error.name==="AbortError" ? "Analyse annulée. Vos images et votre consigne sont conservées." : error.message,true); }
    finally { busy(false); }
  }
  function showResult() {
    el("intention").value=state.record?.intention||"";
    for(const [id,key] of [["observations","observations"],["uncertainties","uncertainties"]]) {
      el(id).replaceChildren(); for(const text of state.record?.[key]||[]) { const li=document.createElement("li"); li.textContent=text; el(id).append(li); }
    }
    el("result").hidden=false; update();
  }
  async function save() {
    if(!currentResult()) throw new Error("L’analyse doit correspondre aux médias, temps et consigne actuels.");
    state.record=await core.request(`/api/media-analysis/analyses/${state.record.analysis_id}/intention`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({intention:el("intention").value.trim()})});
    // The server can remove old parenthetical analysis citations. Transfer the
    // saved text, never the unsanitized textarea that preceded this response.
    el("intention").value=state.record.intention;
  }
  function openRecord(record) {
    if(state.busy) return;
    clearMedia(); const request=record.request; state.sourceKind=request.source_kind; state.sourceName=request.source_name;
    state.frames=request.frames.map(f=>({id:crypto.randomUUID(),assetId:f.asset_id,label:f.label,time:f.time_seconds,url:assetUrl(f.asset_id),role:""}));
    if(request.source_kind==="video") { state.clip={start:request.clip_start_seconds,end:request.clip_end_seconds,duration:request.source_duration_seconds}; state.extractedClip=JSON.stringify(state.clip); }
    el("instruction").value=request.instruction; el("duration").value=String(request.duration_seconds);
    speech.restore(request.transcript);
    if(![...el("model").options].some(o=>o.value===request.model_id)) el("model").add(new Option(`${request.model_id} · modèle enregistré`,request.model_id));
    el("model").value=request.model_id; state.record=record; state.signature=fingerprint(); drawFrames(); drawReferences(); showResult();
    message(record.intention_warning || (request.source_kind==="video" ? "Analyse rouverte avec ses captures. Réimportez la vidéo pour sélectionner un nouvel extrait." : "Analyse rouverte avec les images et leurs temps."), Boolean(record.intention_warning));
  }
  async function transfer(target) {
    if(state.busy) return;
    try {
      busy(true,"Préparation du transfert…"); await save();
      const intention=el("intention").value.trim();
      if(target==="h3") {
        const first=pools().find(f=>f.id===el("first").value), last=pools().find(f=>f.id===el("last").value);
        await window.PanelForgeH3Base.prefillAnalysis({intention,firstFile:first?await fileFor(first):null,lastFile:last?await fileFor(last):null});
      } else {
        const chosen=pools().filter(f=>f.role);
        if(!chosen.length || chosen.length>9) throw new Error("Choisissez entre 1 et 9 références REF2V, ou ajoutez vos propres images.");
        if(chosen.filter(f=>f.role==="first_frame").length>1 || chosen.filter(f=>f.role==="last_frame").length>1) throw new Error("REF2V accepte une seule première et une seule dernière frame exactes.");
        const references=[]; for(const f of chosen) references.push({file:await fileFor(f),role:f.role});
        await window.PanelForgeRef2V.prefillAnalysis({intention,references});
      }
      message("Intention et références transférées. La génération reste à lancer dans l’atelier.");
    } catch(error) { message(error.message,true); }
    finally { busy(false); }
  }
  document.querySelectorAll('[data-video-lab-mode="media-analysis"]').forEach(button=>button.addEventListener("click",()=>initialize().catch(e=>message(e.message,true))));
  el("files").addEventListener("change",selectFiles);
  el("add-images").addEventListener("change",()=>{
    if(state.busy || state.sourceKind!=="images") return;
    const files=[...el("add-images").files]; el("add-images").value="";
    if(files.some(f=>!["image/jpeg","image/png","image/webp"].includes(f.type)) || state.frames.length+files.length>16) return message("Ajoutez des images PNG, JPEG ou WebP, jusqu’à 16 au total.",true);
    state.frames.push(...files.map(f=>frameFor(f))); state.sourceName=`${state.frames.length} images`; drawFrames(); drawReferences();
  });
  for(const kind of ["start","end"]) for(const suffix of ["","-range"]) el(kind+suffix).addEventListener("input",e=>changeRange(kind,Number(e.target.value)));
  el("play").addEventListener("click",()=>{if(state.clip){el("video").currentTime=state.clip.start; el("video").play().catch(e=>message(e.message,true));}});
  el("video").addEventListener("timeupdate",()=>{if(state.clip && el("video").currentTime>=state.clip.end && !el("video").paused) el("video").pause();});
  el("capture").addEventListener("click",()=>extract()); el("capture-current").addEventListener("click",()=>extract(true));
  el("analyze").addEventListener("click",analyze); el("cancel").addEventListener("click",()=>{ if (!speech.cancel()) state.controller?.abort(); });
  for(const id of ["instruction","duration","model","intention"]) el(id).addEventListener("input",update);
  el("model").addEventListener("change",update);
  el("refresh-models").addEventListener("click",()=>{state.initialized=false; initialize().catch(e=>message(e.message,true));});
  el("save").addEventListener("click",()=>save().then(()=>message("Intention enregistrée.")).catch(e=>message(e.message,true)));
  el("copy").addEventListener("click",()=>navigator.clipboard.writeText(el("intention").value).then(()=>message("Intention copiée.")).catch(e=>message(e.message,true)));
  el("h3").addEventListener("click",()=>transfer("h3")); el("ref2v").addEventListener("click",()=>transfer("ref2v"));
  el("extra-refs").addEventListener("change",()=>{
    const files=[...el("extra-refs").files]; el("extra-refs").value="";
    if(files.some(f=>!["image/jpeg","image/png","image/webp"].includes(f.type)) || state.extraRefs.length+files.length>9) return message("Ajoutez jusqu’à 9 références PNG, JPEG ou WebP.",true);
    state.extraRefs.push(...files.map(f=>frameFor(f))); drawReferences();
  });
  update();
})();
