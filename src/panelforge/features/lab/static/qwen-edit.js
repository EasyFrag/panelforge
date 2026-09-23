(() => {
  "use strict";
  const $ = id => document.getElementById(`qw-${id}`);
  const workspace = document.getElementById("qwen-edit-lab-workspace");
  if (!workspace) return;
  const api = "/api/image-lab/qwen-edit";
  const active = new Set(["queued", "submitting", "running", "cancel_pending"]);
  const state = {project:null, stageId:null, selectedAttempt:null, beforeId:null, projects:[], models:[],
    pending:{}, inFlightChanges:{}, saving:null, busy:false, loaded:false, initialized:null, attachmentUsage:"assistant",
    promptDraft:null, timer:null, saveTimer:null, localCandidate:null};
  const labels = {queued:["◷ Planifié", "qw-queued"], submitting:["• Envoi à Qwen", "qw-working"],
    running:["• En cours", "qw-working"], cancel_pending:["• Annulation à vérifier", "qw-working"],
    succeeded:["✓ Terminé", "qw-done"], failed:["✕ Erreur", "qw-failed"], cancelled:["Annulé", "qw-muted"]};
  const stage = () => state.project?.stages.find(s => s.id === state.stageId);
  const editable = () => Boolean(stage() && state.project.active_stage_id === state.stageId && !stage().accepted_attempt_id);
  const stageUrl = () => `${api}/projects/${state.project.id}/stages/${state.stageId}`;
  const media = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const localKey = () => state.project ? `panelforge.qwen.draft.${state.project.id}.${state.stageId}` : null;
  const requestId = () => typeof crypto.randomUUID === "function" ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2,"0")).join("");
  const node = (tag, className, text) => { const el = document.createElement(tag); if(className) el.className = className; if(text !== undefined) el.textContent = text; return el; };
  const button = (text, onClick, className="") => { const el = node("button",className,text); el.type="button"; el.addEventListener("click",onClick); return el; };

  async function request(url, options={}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(" · ") : `Erreur HTTP ${response.status}`;
      const error = new Error(message); error.status = response.status; throw error;
    }
    return data;
  }
  const json = (url, data, method="POST") => request(url, {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
  function fail(error) {
    $("error").textContent = error.message || String(error); $("error").hidden=false;
    if ($("dialog").open) {
      let warning = $("dialog-body").querySelector(".qw-error");
      if (!warning) { warning = node("p","qw-error"); $("dialog-body").append(warning); }
      warning.textContent = error.message || String(error);
    }
  }
  function clearError() { $("error").hidden=true; $("error").textContent=""; }
  function persistLocal() {
    if (!localKey()) return;
    try {
      const changes={...state.inFlightChanges,...state.pending};
      if (Object.keys(changes).length || state.promptDraft !== null) {
        localStorage.setItem(localKey(), JSON.stringify({revision:stage().revision, changes, promptDraft:state.promptDraft}));
      } else if (!state.localCandidate) localStorage.removeItem(localKey());
    } catch (_) { /* Server autosave still works when browser storage is unavailable. */ }
  }
  function pending(changes) {
    Object.assign(state.pending, changes); persistLocal();
    $("save-state").textContent="À enregistrer…";
    clearTimeout(state.saveTimer);
    state.saveTimer=setTimeout(() => flush().catch(fail),700);
    renderControls();
  }
  async function flush() {
    clearTimeout(state.saveTimer);
    if (state.saving) await state.saving;
    if (!Object.keys(state.pending).length || !editable()) return;
    const changes = {...state.pending}; state.pending={}; state.inFlightChanges=changes;
    const targetProject = state.project.id, targetStage = state.stageId;
    state.saving = (async () => {
      $("save-state").textContent="Enregistrement…";
      try {
        const data = await json(stageUrl(), {revision:stage().revision, changes}, "PATCH");
        if (state.project?.id === targetProject && state.stageId === targetStage) apply(data.project);
      } catch (error) {
        state.pending={...changes,...state.pending}; persistLocal();
        $("save-state").textContent="Non enregistré"; throw error;
      } finally {
        state.saving=null; state.inFlightChanges={}; persistLocal(); render();
      }
    })();
    await state.saving;
    if (Object.keys(state.pending).length) await flush();
  }
  async function run(action, {save=true}={}) {
    if (state.busy) return;
    state.busy=true; clearError(); renderControls();
    try { if (save) await flush(); await action(); }
    catch (error) { fail(error); }
    finally { state.busy=false; render(); }
  }
  function apply(project, {selectActive=false}={}) {
    if (project.id === state.project?.id && project.version < state.project.version) project=state.project;
    state.project=project;
    const listed=state.projects.find(item => item.id === project.id);
    if(listed) listed.name=project.name;
    const option=[...$("projects").options].find(item => item.value === project.id);
    if(option) option.textContent=project.name;
    if (selectActive || !project.stages.some(s => s.id === state.stageId)) {
      state.stageId=project.active_stage_id; state.selectedAttempt=null; state.beforeId=null; state.promptDraft=null;
    }
    if (state.selectedAttempt && !stage().attempts.some(a => a.id === state.selectedAttempt)) state.selectedAttempt=null;
    render();
  }
  function restoreLocalNotice() {
    state.localCandidate=null;
    try { state.localCandidate=JSON.parse(localStorage.getItem(localKey()) || "null"); } catch (_) { /* no valid draft */ }
    $("local-draft").hidden=!state.localCandidate || !editable();
    renderControls();
  }
  async function openProject(id) {
    await flush();
    persistLocal();
    const {project}=await request(`${api}/projects/${id}`);
    state.pending={}; state.stageId=null; state.promptDraft=null; state.localCandidate=null;
    apply(project,{selectActive:true});
    try { localStorage.setItem("panelforge.qwen.last-project",id); } catch (_) { /* optional */ }
    restoreLocalNotice();
  }
  async function refreshProjects() {
    const data=await request(`${api}/projects`); state.projects=data.projects;
    const picker=$("projects"), selected=state.project?.id || "";
    picker.replaceChildren(new Option("Mes projets…",""));
    state.projects.forEach(p => picker.append(new Option(p.name,p.id)));
    picker.value=selected;
  }
  async function init() {
    if (state.loaded) return;
    if (state.initialized) return state.initialized;
    state.initialized=(async () => {
      await request(`${api}/spec`).catch(error => {
        if(error.status === 404) throw new Error("Redémarre PanelForge pour activer le nouvel atelier Qwen, puis actualise cette page.");
        throw error;
      });
      await refreshProjects();
      const modelTask=request(`${api}/models`).then(data => {state.models=data.models; renderModels();}).catch(error => fail(new Error(`Catalogue LLM indisponible : ${error.message}`)));
      let last=null; try {last=localStorage.getItem("panelforge.qwen.last-project");} catch (_) { /* optional */ }
      if (state.projects.some(p => p.id === last)) await openProject(last);
      else if (state.projects.length) await openProject(state.projects[0].id);
      state.loaded=true; schedulePoll(); await modelTask;
    })();
    try {await state.initialized;} finally {state.initialized=null;}
  }
  function schedulePoll() {
    clearTimeout(state.timer);
    state.timer=setTimeout(async () => {
      try {
        if (!workspace.hidden && state.project && !state.busy && !state.saving) {
          const id=state.project.id;
          const {project}=await request(`${api}/projects/${id}`);
          if (state.project?.id === id && !state.busy && !state.saving && project.version > state.project.version) apply(project);
        }
      } catch(error) {fail(error);}
      finally {schedulePoll();}
    },1800);
  }
  function renderModels() {
    const select=$("model"), wanted=stage()?.model_id || select.value;
    window.PanelForgeModelPicker.populate(select,state.models,wanted);
    if (wanted) window.PanelForgeModelPicker.select(select,wanted);
    $("model-summary").textContent=select.selectedOptions[0]?.textContent || "Choisir un modèle";
  }
  function inputValue(id, value, field) {
    if (document.activeElement !== $(id) && !Object.hasOwn(state.pending,field)) $(id).value=value ?? "";
  }
  function chosenAttempt() {
    const s=stage(); if (!s) return null;
    return s.attempts.find(a => a.id === state.selectedAttempt) || [...s.attempts].reverse().find(a => a.status === "succeeded") || null;
  }
  function statusLabel(status, phase) {
    if (status === "running" && phase === "queued") return ["◷ Planifié", "qw-queued"];
    return labels[status] || [status,"qw-muted"];
  }
  function render() {
    $("empty").hidden=Boolean(state.project); $("editor").hidden=!state.project;
    if (!state.project) {renderControls(); return;}
    const s=stage();
    $("projects").value=state.project.id;
    inputValue("name",state.project.name,"name"); inputValue("label",s.label,"label"); inputValue("draft",s.draft,"draft");
    if (state.promptDraft === null && document.activeElement !== $("prompt")) $("prompt").value=s.prompt;
    const settings=state.pending.settings || s.settings;
    if (!state.pending.settings) {
      for (const [id,key] of [["resolution","resolution"],["ratio","aspect_ratio"],["steps","steps"],["cfg","cfg"],["seed","seed"],["negative","negative_prompt"]]) inputValue(id,settings[key],"settings");
      $("reuse-seed").checked=settings.reuse_seed;
    }
    if (s.model_id && $("model").value !== s.model_id && !state.pending.model_id) window.PanelForgeModelPicker.select($("model"),s.model_id);
    $("model-summary").textContent=$("model").selectedOptions[0]?.textContent || "Choisir un modèle";
    $("download").href=`${api}/projects/${state.project.id}/download`;
    $("history-notice").hidden=editable();
    const offset=state.project.stages[0].mode === "composition" ? 1 : 0;
    $("stage-number").textContent=s.mode === "composition" ? "Composition" : `Étape ${s.index-offset}`;
    renderTimeline(offset); renderPreview(); renderReferences(); renderMessages(); renderAttempts();
    $("summary").textContent=s.summary || "Décris ta modification à l’assistant, ou écris directement le prompt.";
    $("prompt-status").textContent=s.prompt_ready ? "✓ Prête" : s.prompt ? "À actualiser" : "À préparer";
    $("prompt-status").className=`qw-chip ${s.prompt_ready ? "qw-done" : "qw-queued"}`;
    $("prompt-mapping").textContent=s.render_inputs.map(r => `${r.tag} = ${r.name}`).join(" · ");
    $("ratio-wrap").hidden=s.mode !== "composition";
    $("resolution").querySelector('[value="source"]').disabled=s.mode === "composition";
    $("negative-wrap").hidden=Number(settings.cfg) === 1;
    $("settings-summary").textContent=`${s.render_dimensions.join(" × ")} · ${settings.steps} steps`;
    const renderRunning=s.attempts.find(a => active.has(a.status));
    const llmRunning=s.messages.find(m => ["queued","running"].includes(m.status));
    const currentStatus=renderRunning || llmRunning;
    const [text,cls]=currentStatus ? statusLabel(currentStatus.status,currentStatus.phase) : [s.accepted_attempt_id ? "✓ Étape validée" : "Prêt à travailler",s.accepted_attempt_id ? "qw-done" : "qw-muted"];
    $("stage-status").textContent=text; $("stage-status").className=cls;
    $("export-note").textContent=state.project.export_error ? `Copie à réessayer : ${state.project.export_error}` : state.project.export_path ? `Copie du projet : ${state.project.export_path}` : "Le projet et ses images sont sauvegardés automatiquement.";
    $("export").textContent=state.project.export_error ? "Réessayer la copie du projet" : "Enregistrer une copie du projet";
    if (!state.saving) $("save-state").textContent=Object.keys(state.pending).length || state.promptDraft !== null ? "Brouillon à enregistrer" : "✓ Enregistré";
    renderControls();
  }
  function renderTimeline(offset) {
    const timeline=$("timeline"); timeline.replaceChildren();
    const root=state.project.stages[0];
    if (root.source_asset_id) timeline.append(button("Base",() => zoom(root.source_asset_id,"Image de base")));
    state.project.stages.forEach((s,index) => {
      if (index || root.source_asset_id) timeline.append(node("span","","→"));
      const label=s.mode === "composition" ? "Base · composition" : `Étape ${s.index-offset}`;
      const el=button(`${s.accepted_attempt_id ? "✓ " : ""}${label}`,() => run(async () => {
        persistLocal(); state.stageId=s.id; state.selectedAttempt=null; state.beforeId=null; state.promptDraft=null;
        state.pending={}; state.localCandidate=null; render(); restoreLocalNotice();
      }));
      if (s.id === state.stageId) el.setAttribute("aria-current","step");
      if (s.accepted_attempt_id) el.classList.add("qw-done");
      el.title=s.label; timeline.append(el);
    });
  }
  function setImage(el,assetId) {el.hidden=!assetId; if(assetId && el.getAttribute("src") !== media(assetId)) el.src=media(assetId); if(!assetId) el.removeAttribute("src");}
  function renderPreview() {
    const s=stage(), attempt=chosenAttempt();
    const before=$("before"), after=$("after"); before.replaceChildren(); after.replaceChildren();
    const options=[];
    if(s.source_asset_id) options.push([s.source_asset_id,"Source de cette étape"]);
    state.project.stages.forEach(item => {if(item.source_asset_id && !options.some(o => o[0]===item.source_asset_id)) options.push([item.source_asset_id,item.index === 1 ? "Image de base" : `Source · ${item.label}`]);});
    options.forEach(([id,label]) => before.append(new Option(label,id)));
    if(!options.length) before.append(new Option("Nouvelle composition",""));
    if(!options.some(o => o[0]===state.beforeId)) state.beforeId=s.source_asset_id || options[0]?.[0] || null;
    before.value=state.beforeId || "";
    s.attempts.forEach((a,index) => {if(a.status === "succeeded") after.append(new Option(`Essai ${index+1}${a.id===s.accepted_attempt_id ? " · validé" : ""}`,a.id));});
    if(!after.options.length) after.append(new Option("Aucun résultat",""));
    after.value=attempt?.id || "";
    setImage($("before-image"),state.beforeId); setImage($("after-image"),attempt?.output_asset_id);
    const split=Boolean(state.beforeId && attempt?.output_asset_id);
    $("compare").classList.toggle("qw-split",split);
    $("divider").hidden=!split; $("slider-label").hidden=!split; $("before-tag").hidden=!state.beforeId; $("after-tag").hidden=!attempt?.output_asset_id;
    $("image-placeholder").hidden=Boolean(state.beforeId || attempt?.output_asset_id);
    $("preview-note").textContent=attempt ? `${attempt.output_dimensions?.join(" × ") || attempt.dimensions.join(" × ")} · seed ${attempt.settings.seed}` : "La source reste fixe pendant les essais de cette étape.";
    $("image-download").hidden=!attempt?.output_asset_id;
    $("image-download").href=attempt?.output_asset_id ? media(attempt.output_asset_id) : "#";
    $("feedback-wrap").hidden=!attempt?.output_asset_id;
    $("feedback").checked=s.feedback_attempt_id === attempt?.id && Boolean(attempt);
  }
  function referenceCard(ref,{source=false}={}) {
    const card=node("div","qw-ref"), image=node("img","qw-ref-image"); image.src=media(ref.asset_id); image.alt=ref.name;
    image.addEventListener("click",() => zoom(ref.asset_id,ref.name)); card.append(image);
    const content=node("div","qw-ref-content"), title=node("div","qw-ref-name",ref.name); title.title=ref.name; content.append(title);
    content.append(node("span",`qw-chip ${source || ref.usage === "render" ? "qw-render" : "qw-assistant"}`,source ? "Source" : ref.usage === "render" ? "▧ Qwen" : "◌ Assistant"));
    if(ref.role) {const role=node("small","qw-ref-role",ref.role); role.title=ref.role; content.append(role);}
    if(!source) content.append(button("Usage et rôle",() => editReference(ref),"qw-ref-edit"));
    card.append(content); return card;
  }
  function renderReferences() {
    const s=stage(), rendered=$("render-images"), inspirations=$("assistant-images"); rendered.replaceChildren(); inspirations.replaceChildren();
    if(s.source_asset_id) rendered.append(referenceCard({asset_id:s.source_asset_id,name:"Source de l’étape"},{source:true}));
    s.references.filter(r => r.active).forEach(ref => (ref.usage === "render" ? rendered : inspirations).append(referenceCard(ref)));
    $("render-count").textContent=`${s.render_inputs.length} image${s.render_inputs.length>1 ? "s" : ""} envoyée${s.render_inputs.length>1 ? "s" : ""} à Qwen · également visible${s.render_inputs.length>1 ? "s" : ""} par l’assistant`;
  }
  function renderMessages() {
    const list=$("messages"), oldScroll=list.scrollTop, bottom=list.scrollHeight-list.scrollTop-list.clientHeight<45;
    const s=stage(); list.replaceChildren();
    if(!s.messages.length) {
      list.append(node("div","qw-chat-empty",s.mode === "composition" ? "Ajoute tes personnages dans les références du rendu. Tu peux aussi joindre ici une ambiance pour guider le prompt." : "Que souhaites-tu changer ? Joins une image pour montrer une palette, une ambiance ou un exemple, puis explique ce que tu veux en tirer."));
    }
    for(const message of s.messages) {
      const block=node("article","qw-message"), user=node("div","qw-message-user",message.text);
      const refs=message.context.references;
      if(refs.length) {
        const thumbs=node("div","qw-message-thumbs");
        refs.forEach(ref => {const thumb=button("",() => zoom(ref.asset_id,`${ref.name} · ${ref.usage === "render" ? "Référence Qwen lors de cet appel" : "Assistant uniquement lors de cet appel"}`)); const img=node("img"); img.src=media(ref.asset_id); img.alt=ref.name; thumb.title=`${ref.name} · ${ref.usage === "render" ? "Qwen" : "Assistant uniquement"}`; thumb.append(img); thumbs.append(thumb);});
        user.append(thumbs);
      }
      block.append(user);
      if(message.reply) block.append(node("div","qw-message-reply",message.reply));
      if(message.status !== "succeeded") {const [label,cls]=statusLabel(message.status,message.phase); block.append(node("p",cls,label));}
      if(message.error) block.append(node("p","qw-failed",message.error));
      if(message.applied === false) block.append(node("p","qw-queued","Le contexte a changé pendant la réponse. Cette proposition reste dans l’historique."));
      const meta=node("div","qw-message-meta");
      if(message.has_draft || message.has_reasoning) meta.append(button("Réponse et raisonnement",() => viewMessage(message),"qw-link"));
      if(editable() && !["queued","running"].includes(message.status) && message.can_recover) {
        const recover=button(message.status === "failed" ? "Récupérer le brouillon · sans LLM" : "Reprendre ce prompt",() => run(async () => {
          apply((await json(`${stageUrl()}/messages/${message.id}/recover`,{revision:stage().revision})).project);
          state.promptDraft=null;
        }),"qw-link"); recover.disabled=state.busy; meta.append(recover);
      }
      if(editable() && message.status === "failed") {
        const retry=button("Reprendre ma demande",() => {$("draft").value=message.text; pending({draft:message.text}); $("draft").focus();},"qw-link");
        retry.disabled=state.busy; meta.append(retry);
      }
      block.append(meta); list.append(block);
    }
    list.scrollTop=bottom ? list.scrollHeight : oldScroll;
  }
  function renderAttempts() {
    const list=$("attempts"), s=stage(), chosen=chosenAttempt(); list.replaceChildren();
    $("attempt-count").textContent=`${s.attempts.length} essai${s.attempts.length>1 ? "s" : ""}`;
    if(!s.attempts.length) list.append(node("p","qw-muted","Tes résultats apparaîtront ici. Chaque essai conserve ses images et réglages."));
    s.attempts.forEach((attempt,index) => {
      const wrap=node("div"), tile=button("",() => {state.selectedAttempt=attempt.id; renderPreview(); renderAttempts(); renderControls();},"qw-attempt");
      tile.setAttribute("aria-pressed",String(chosen?.id === attempt.id));
      tile.title=`Essai ${index+1} · seed ${attempt.settings.seed}`;
      if(attempt.output_asset_id) {const img=node("img"); img.src=media(attempt.output_asset_id); img.alt=`Essai ${index+1}`; tile.append(img);}
      else tile.append(node("div","qw-attempt-placeholder",attempt.status === "failed" ? "✕" : attempt.status === "cancelled" ? "—" : "◷"));
      const [text,cls]=statusLabel(attempt.status); tile.append(node("small","",`Essai ${index+1}`),node("small",cls,text)); wrap.append(tile);
      if(attempt.error) wrap.append(button("Voir l’erreur",() => dialog("Erreur du rendu",body => body.append(node("p","",attempt.error))),"qw-link"));
      if(active.has(attempt.status) || attempt.status === "submitting") {
        const cancel=button(attempt.cancel_requested ? "Annulation demandée" : "Annuler",() => run(async () => apply((await json(`${stageUrl()}/attempts/${attempt.id}/cancel`,{})).project)),"qw-link");
        cancel.disabled=state.busy || attempt.cancel_requested; wrap.append(cancel);
      }
      list.append(wrap);
    });
  }
  function renderControls() {
    const s=stage(), canEdit=editable() && !state.busy;
    for(const id of ["name","label","model","draft","resolution","ratio","steps","cfg","seed","reuse-seed","negative","feedback","prompt"]) $(id).disabled=!canEdit;
    for(const id of ["add-assistant","add-render","reuse","new-seed"]) $(id).disabled=!canEdit;
    window.PanelForgeModelPicker?.setDisabled($("model"),!canEdit);
    const promptRunning=s?.messages.some(m => ["queued","running"].includes(m.status));
    const renderRunning=s?.attempts.some(a => active.has(a.status));
    $("send").disabled=!canEdit || promptRunning || !$("draft").value.trim() || !$("model").value;
    $("send").textContent=promptRunning ? "Préparation…" : "Envoyer ↑";
    const contextDirty=Object.keys(state.pending).some(k => ["references","settings"].includes(k));
    $("generate").disabled=!canEdit || renderRunning || promptRunning || !s?.prompt_ready || contextDirty || state.promptDraft !== null || Boolean(state.localCandidate) || Boolean($("draft").value.trim());
    $("generate").textContent=renderRunning ? "Rendu planifié / en cours" : "Générer l’image ✦";
    $("generate-note").textContent=state.promptDraft !== null ? "Enregistre le prompt modifié avant de générer." : $("draft").value.trim() ? "Envoie ta demande à l’assistant pour la prendre en compte." : s?.prompt_ready && !contextDirty ? "Utilise l’instruction prête · aucun nouvel appel LLM" : "Prépare ou actualise l’instruction avant de générer.";
    const attempt=chosenAttempt();
    $("accept").disabled=!canEdit || attempt?.status !== "succeeded" || renderRunning || promptRunning;
    $("restore-attempt").disabled=!canEdit || !attempt || promptRunning;
    $("save-prompt").disabled=!canEdit || !$("prompt").value.trim();
    $("zoom").disabled=!attempt?.output_asset_id && !state.beforeId;
    $("projects").disabled=state.busy || Boolean(state.saving); $("new").disabled=state.busy;
  }
  function dialog(title,fill,{zoomed=false}={}) {
    const modal=$("dialog"); $("dialog-title").textContent=title; $("dialog-body").replaceChildren();
    modal.classList.toggle("qw-zoom-dialog",zoomed); fill($("dialog-body")); if(!modal.open) modal.showModal();
  }
  function zoom(assetId,title) {if(!assetId)return; dialog(title,body => {const img=node("img"); img.src=media(assetId); img.alt=title; body.append(img);},{zoomed:true});}
  function editReference(ref) {
    dialog(ref.name,body => {
      const img=node("img"); img.src=media(ref.asset_id); img.alt=ref.name; img.style.maxHeight="200px"; body.append(img);
      const nameLabel=node("label","","Nom pour la conversation"), name=node("input"); name.value=ref.name; name.maxLength=80; nameLabel.append(name);
      const roleLabel=node("label","","Ce qu’il faut reprendre (facultatif)"), role=node("input"); role.value=ref.role; role.maxLength=300; role.placeholder="Ex. couleurs uniquement, identité du personnage, veste…"; roleLabel.append(role);
      const usageLabel=node("label","","Utilisation de cette image"), usage=node("select"); usage.append(new Option("Assistant uniquement · guider le prompt","assistant"),new Option("Assistant + Qwen · référence de génération","render")); usage.value=ref.usage; usageLabel.append(usage);
      body.append(nameLabel,roleLabel,usageLabel,node("p","qw-muted","Tu peux citer cette image avec @son nom. Le rôle indique ce qu’il faut reprendre, sans copier toute la scène."));
      const actions=node("div","qw-dialog-actions");
      const mention=button(`Citer @${ref.name}`,() => {$("dialog").close(); $("draft").value+=`${$("draft").value ? " " : ""}@${ref.name} `; pending({draft:$("draft").value}); $("draft").focus();});
      const remove=button("Retirer de cette étape",() => run(async () => {await saveReference(ref.id,{active:false}); $("dialog").close();}));
      const save=button("Enregistrer",() => run(async () => {await saveReference(ref.id,{name:name.value.trim(),role:role.value,usage:usage.value}); $("dialog").close();}),"qw-primary");
      if(ref.usage === "assistant") body.append(button("Utiliser aussi pour le rendu",() => {usage.value="render";},"qw-link"));
      for(const control of [name,role,usage,mention,remove,save]) control.disabled=!editable() || state.busy;
      actions.append(mention,remove,save); body.append(actions);
    });
  }
  async function saveReference(id,changes) {
    const refs=stage().references.map(ref => ref.id === id ? {...ref,...changes} : ref);
    apply((await json(stageUrl(),{revision:stage().revision,changes:{references:refs}},"PATCH")).project);
  }
  function reuseDialog() {
    const candidates=state.project.stages.flatMap(s => s.references.filter(r => s.id !== state.stageId || !r.active));
    dialog("Réutiliser une image du projet",body => {
      if(!candidates.length) body.append(node("p","qw-muted","Les images retirées et celles des étapes précédentes apparaîtront ici."));
      const seen=new Set();
      for(const ref of candidates) {
        if(seen.has(ref.asset_id))continue; seen.add(ref.asset_id);
        const row=node("div","qw-reference-choice"), img=node("img"); img.src=media(ref.asset_id); img.alt=ref.name; row.append(img,node("div","",ref.name));
        for(const [usage,label] of [["assistant","Assistant"],["render","Qwen"]]) row.append(button(label,() => run(async () => {
          const current=stage().references.find(r => r.id === ref.id);
          if(current) await saveReference(ref.id,{usage,active:true});
          else apply((await json(`${stageUrl()}/reuse`,{reference_id:ref.id,usage,revision:stage().revision})).project);
          $("dialog").close();
        })));
        body.append(row);
      }
    });
  }
  function viewMessage(message) {
    run(async () => {
      const {message:full}=await request(`${stageUrl()}/messages/${message.id}`);
      dialog("Réponse et raisonnement de l’assistant",body => {
        body.append(node("p","qw-muted",`${full.model_id} · ${full.context.render_inputs.length} image(s) pour Qwen · les inspirations restent réservées à l’assistant.`));
        body.append(node("h3","","Réponse reçue"),node("pre","",full.raw || "Aucun texte reçu."));
        if(full.reasoning) {const details=node("details"), summary=node("summary","","Raisonnement reçu"); details.append(summary,node("pre","",full.reasoning)); body.append(details);}
        if(full.error) body.append(node("p","qw-failed",full.error));
      });
    });
  }
  async function uploadAttachments(files,usage) {
    if(!editable())return;
    await run(async () => {
      for(const file of files) {
        if(!["image/png","image/jpeg","image/webp"].includes(file.type)) throw new Error("Utilise une image PNG, JPEG ou WebP.");
        if(file.size > 25*1024*1024) throw new Error("Une image ne doit pas dépasser 25 Mo.");
        const form=new FormData(); form.append("image",file); form.append("usage",usage); form.append("revision",String(stage().revision)); form.append("name",file.name.replace(/\.[^.]+$/,"").slice(0,70) || "Référence");
        apply((await request(`${stageUrl()}/references`,{method:"POST",body:form})).project);
      }
    });
  }
  function attach(usage) {state.attachmentUsage=usage; $("attachment-files").value=""; $("attachment-files").click();}
  function newDialog() {dialog("Nouveau projet Qwen",body => {
    body.append(node("p","","Pars d’une image à modifier, ou réunis plusieurs références dans une nouvelle composition."));
    const actions=node("div","qw-dialog-actions"); actions.append(button("Modifier une image",() => $("source-file").click(),"qw-primary"),button("Nouvelle composition",() => createProject(null,true))); body.append(actions);
  });}
  async function createProject(file,composition) {
    await run(async () => {
      const form=new FormData(); form.append("name",file ? file.name.replace(/\.[^.]+$/,"").slice(0,120) : "Nouvelle composition"); form.append("composition",String(composition));
      if(file) form.append("source_image",file);
      const {project}=await request(`${api}/projects`,{method:"POST",body:form});
      state.pending={}; state.promptDraft=null; state.localCandidate=null; state.stageId=null;
      apply(project,{selectActive:true}); $("local-draft").hidden=true; $("dialog").close();
      await refreshProjects(); renderModels();
      if($("model").value) pending({model_id:$("model").value});
      try {localStorage.setItem("panelforge.qwen.last-project",project.id);} catch(_) { /* optional */ }
    });
  }
  function readSettings() {
    return {resolution:$("resolution").value,aspect_ratio:$("ratio").value,steps:Number($("steps").value),cfg:Number($("cfg").value),seed:$("seed").value.trim(),reuse_seed:$("reuse-seed").checked,negative_prompt:$("negative").value};
  }
  const help = {
    assistant:["Une inspiration pour l’assistant","Joins une image pour montrer des couleurs, une ambiance ou un défaut. Le LLM la regarde et traduit ta demande en prompt. Qwen reçoit la source et le texte, sans cette pièce jointe.","Exemple : « Reprends les couleurs de cette photo, en conservant les meubles de mon salon. » Pour transmettre aussi l’image à Qwen, ouvre « Usage et rôle », puis « Utiliser aussi pour le rendu »."],
    render:["Une référence que Qwen voit","Ces images sont vues par l’assistant ET envoyées à Qwen. Utilise-les pour ajouter un personnage, reprendre un vêtement ou guider directement un aspect visuel. La source compte parmi les 16 images possibles.","Exemple : ajoute deux portraits, nomme-les Léa et Marc, puis écris « Place @Léa à gauche et @Marc à droite, dans ce décor ». Une référence guide la génération ; elle ne garantit pas une copie exacte."],
    resolution:["Résolution","« Taille de la source » conserve les dimensions de ton image, ajustées aux multiples de 32 nécessaires à Qwen. Les autres choix gardent ses proportions et fixent une surface d’environ 1, 2 ou 4 mégapixels.","Exemple : commence à 1 MP pour juger une composition, puis passe à 4 MP. Plus de pixels demandent davantage de mémoire et de temps. En nouvelle composition, choisis aussi le format."],
    steps:["Steps","Le nombre d’itérations du rendu. Le workflow fourni utilise 25 steps.","Exemple : garde 25 pour tes premiers essais. Augmenter prend plus de temps et ne garantit pas une meilleure image."],
    seed:["Seed et variations","La seed choisit le bruit de départ. La réutiliser aide à comparer deux prompts ou deux réglages. « Nouvelle variation » choisit une autre seed sans lancer de rendu.","Exemple : garde la même seed pendant que tu ajustes le placement de Léa. Puis essaie une nouvelle variation. Décoche « Réutiliser » pour une nouvelle seed à chaque rendu."],
    cfg:["CFG","Le workflow fourni utilise CFG 1. Ce réglage contrôle le guidage pendant la génération ; ce n’est pas un curseur de fidélité à l’image source.","À CFG 1, le prompt négatif n’intervient pas dans le guidage standard. Au-dessus de 1, son champ devient disponible. Commence avec la valeur du workflow avant d’expérimenter."]
  };
  workspace.querySelectorAll("[data-qw-help]").forEach(el => el.addEventListener("click",() => {const [title,...paragraphs]=help[el.dataset.qwHelp]; dialog(title,body => paragraphs.forEach(text => body.append(node("p","",text))));}));
  $("dialog-close").addEventListener("click",() => $("dialog").close());
  $("dialog").addEventListener("click",event => {if(event.target === $("dialog")) {const r=$("dialog").getBoundingClientRect(); if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) $("dialog").close();}});
  $("new").addEventListener("click",newDialog); $("start-edit").addEventListener("click",() => $("source-file").click());
  $("start-composition").addEventListener("click",() => createProject(null,true));
  $("source-file").addEventListener("change",() => {const file=$("source-file").files[0]; if(file) createProject(file,false); $("source-file").value="";});
  $("refresh").addEventListener("click",() => run(async () => {await refreshProjects(); if(state.project) apply((await request(`${api}/projects/${state.project.id}`)).project); const data=await request(`${api}/models`); state.models=data.models; renderModels();}));
  $("projects").addEventListener("change",() => {const id=$("projects").value; if(id) run(() => openProject(id));});
  $("name").addEventListener("input",() => pending({name:$("name").value})); $("label").addEventListener("input",() => pending({label:$("label").value}));
  $("draft").addEventListener("input",() => pending({draft:$("draft").value}));
  $("model").addEventListener("change",() => {pending({model_id:$("model").value}); $("model-summary").textContent=$("model").selectedOptions[0]?.textContent || "";});
  for(const id of ["resolution","ratio","steps","cfg","seed","reuse-seed","negative"]) $(id).addEventListener("change",() => {pending({settings:readSettings()}); $("negative-wrap").hidden=Number($("cfg").value)===1;});
  $("new-seed").addEventListener("click",() => {const seed=new Uint32Array(2); crypto.getRandomValues(seed); $("seed").value=((BigInt(seed[0])<<32n)|BigInt(seed[1])).toString(); pending({settings:readSettings()});});
  $("prompt").addEventListener("input",() => {state.promptDraft=$("prompt").value; persistLocal(); renderControls();});
  $("save-prompt").addEventListener("click",() => run(async () => {apply((await json(stageUrl(),{revision:stage().revision,changes:{prompt:$("prompt").value}},"PATCH")).project); state.promptDraft=null; persistLocal();}));
  $("send").addEventListener("click",() => run(async () => {
    if(state.promptDraft !== null) throw new Error("Enregistre d’abord le prompt que tu as modifié, pour que l’assistant le prenne en compte.");
    if(!stage().model_id && $("model").value) {pending({model_id:$("model").value}); await flush();}
    const {project}=await json(`${stageUrl()}/messages`,{revision:stage().revision,request_id:requestId()});
    $("draft").value=""; apply(project); persistLocal();
  }));
  $("draft").addEventListener("keydown",event => {if(event.key === "Enter" && (event.ctrlKey || event.metaKey)) {event.preventDefault(); $("send").click();}});
  $("generate").addEventListener("click",() => run(async () => {
    apply((await json(`${stageUrl()}/attempts`,{revision:stage().revision,request_id:requestId()})).project);
  }));
  $("before").addEventListener("change",() => {state.beforeId=$("before").value; renderPreview();});
  $("after").addEventListener("change",() => {state.selectedAttempt=$("after").value; renderPreview(); renderAttempts(); renderControls();});
  $("split").addEventListener("input",() => $("compare").style.setProperty("--qw-split",`${$("split").value}%`));
  $("zoom").addEventListener("click",() => zoom(chosenAttempt()?.output_asset_id || state.beforeId,"Image en grand"));
  $("feedback").addEventListener("change",() => pending({feedback_attempt_id:$("feedback").checked ? chosenAttempt()?.id : null}));
  $("restore-attempt").addEventListener("click",() => run(async () => {apply((await json(`${stageUrl()}/attempts/${chosenAttempt().id}/restore`,{revision:stage().revision})).project); state.promptDraft=null; persistLocal();}));
  $("accept").addEventListener("click",() => run(async () => {const {project}=await json(`${stageUrl()}/attempts/${chosenAttempt().id}/accept`,{revision:stage().revision}); persistLocal(); state.pending={}; state.localCandidate=null; apply(project,{selectActive:true}); restoreLocalNotice(); await refreshProjects();}));
  $("resume").addEventListener("click",() => run(async () => {const {project}=await json(`${stageUrl()}/resume`,{request_id:requestId()}); state.pending={}; state.localCandidate=null; apply(project,{selectActive:true}); await refreshProjects(); restoreLocalNotice();}));
  $("export").addEventListener("click",() => run(async () => apply((await json(`${api}/projects/${state.project.id}/export`,{})).project)));
  $("download").addEventListener("click",event => {event.preventDefault(); run(async () => {window.location.assign(`${api}/projects/${state.project.id}/download`);});});
  $("add-assistant").addEventListener("click",() => attach("assistant")); $("add-render").addEventListener("click",() => attach("render"));
  $("attachment-files").addEventListener("change",() => uploadAttachments([...$("attachment-files").files],state.attachmentUsage));
  $("reuse").addEventListener("click",reuseDialog);
  for(const [id,usage] of [["assistant-drop","assistant"],["render-drop","render"]]) {
    const target=$(id);
    target.addEventListener("dragover",event => {if(editable() && event.dataTransfer.types.includes("Files")) {event.preventDefault(); target.classList.add("qw-dragover");}});
    target.addEventListener("dragleave",event => {if(!target.contains(event.relatedTarget)) target.classList.remove("qw-dragover");});
    target.addEventListener("drop",event => {target.classList.remove("qw-dragover"); if(event.dataTransfer.files.length) {event.preventDefault(); uploadAttachments([...event.dataTransfer.files],usage);}});
  }
  $("assistant-drop").addEventListener("paste",event => {const images=[...event.clipboardData.items].filter(item => item.type.startsWith("image/")).map(item => item.getAsFile()).filter(Boolean); if(images.length) {event.preventDefault(); uploadAttachments(images,"assistant");}});
  $("local-restore").addEventListener("click",() => run(async () => {
    const candidate=state.localCandidate; state.localCandidate=null; state.pending={...candidate.changes}; state.promptDraft=candidate.promptDraft;
    for(const [key,id] of [["draft","draft"],["name","name"],["label","label"]]) if(Object.hasOwn(state.pending,key)) $(id).value=state.pending[key];
    if(state.promptDraft !== null) $("prompt").value=state.promptDraft;
    await flush(); $("local-draft").hidden=true; persistLocal();
  },{save:false}));
  $("local-dismiss").addEventListener("click",() => {state.localCandidate=null; try {localStorage.removeItem(localKey());} catch(_) {} $("local-draft").hidden=true; render();});
  window.addEventListener("beforeunload",persistLocal);
  window.PanelForgeQwenEdit = {open: async id => {
    await init(); await openProject(id); await refreshProjects();
    window.PanelForgeLabNavigation.switchView("qwen-edit-lab");
  }};
  document.querySelectorAll('[data-image-lab-mode="qwen-edit-lab"]').forEach(el => el.addEventListener("click",() => {
    window.PanelForgeLabNavigation.switchView("qwen-edit-lab"); init().catch(fail);
  }));
  document.querySelectorAll("[data-image-lab-mode],[data-lab-view]").forEach(el => el.addEventListener("click",() => {if(state.project) {persistLocal(); flush().catch(fail);}}));
  if(!workspace.hidden) init().catch(fail);
})();
