(() => {
  "use strict";
  const root = document.getElementById("video-factory-workspace");
  const core = window.PanelForgeLabCore;
  if (!root || !core) return;
  const $ = id => document.getElementById("vf-" + id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const clone = value => JSON.parse(JSON.stringify(value));
  const stages = ["plan","prompt","video","dlss","social"];
  const labels = {plan:"Plan",prompt:"Prompt",video:"Vidéo",dlss:"DLSS",social:"Texte IG"};
  const roles = {unassigned:"Rôle à choisir",first_frame:"Première frame",last_frame:"Dernière frame",subject_reference:"Sujet / identité",environment_reference:"Décor",style_reference:"Style",composition_reference:"Composition",motion_reference:"Mouvement",keyframe_reference:"Keyframe"};
  const state = {data:null,tab:"preparation",selected:new Set(),focus:null,busy:false,dirty:false,draft:null,revision:null,undo:null,refreshing:false};
  const uploads = new WeakMap();
  let noticeTimer;
  const api = (path,method="GET",body) => core.request("/api/video-factory" + path, {method,...(body===undefined?{}:{headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  const current = () => state.data?.items.find(item=>item.id===state.focus);
  const group = item => item.source.kind === "episode" ? item.source.id : "";
  const tab = item => item.status === "preparation" ? "preparation" : ["queued","active"].includes(item.status) ? "production" : "results";
  const errors = item => Object.values(item.steps).some(step=>step.status==="failed");
  const assetUrl = id => "/api/assets/" + encodeURIComponent(id) + "/content";
  const selected = () => (state.data?.items || []).filter(item=>state.selected.has(item.id));
  const selection = items => ({ids:items.map(item=>item.id), revisions:Object.fromEntries(items.map(item=>[item.id,item.revision]))});
  function visible() {
    const filter = $("filter").value;
    return (state.data?.items || []).filter(item=>tab(item)===state.tab && (
      filter==="all" || filter==="ready" && item.status==="preparation" && item.ready ||
      filter==="incomplete" && item.status==="preparation" && !item.ready || filter==="failed" && errors(item)));
  }
  function showNotice(message, action, label="Ouvrir") {
    clearTimeout(noticeTimer); const node=$("notice"); node.replaceChildren(document.createTextNode(message));
    if(action){const button=document.createElement("button");button.type="button";button.textContent=label;button.onclick=action;node.append(button);}
    const close=document.createElement("button");close.type="button";close.textContent="×";close.setAttribute("aria-label","Fermer");close.onclick=()=>node.hidden=true;node.append(close);
    node.hidden=false;noticeTimer=setTimeout(()=>node.hidden=true,12000);
  }
  async function busy(work) {
    if(state.busy)return;
    state.busy=true;$("message").textContent="";renderToolbar();
    try {return await work();}
    catch(error){$("message").textContent=error.message;showNotice(error.message);}
    finally{state.busy=false;renderToolbar();}
  }
  function accept(data) {
    state.data=data;
    const ids=new Set(data.items.map(item=>item.id));
    state.selected=new Set([...state.selected].filter(id=>ids.has(id) && tab(data.items.find(item=>item.id===id))===state.tab));
    if(state.focus&&!ids.has(state.focus)){state.focus=null;state.dirty=false;}
    render();
  }
  async function refresh() {
    if(state.refreshing||state.busy)return;
    state.refreshing=true;
    try{accept(await api(""));}catch(error){$("message").textContent=error.message;}finally{state.refreshing=false;}
  }
  async function open(ids=[]) {
    await saveDraft();
    window.PanelForgeLabNavigation?.switchView("video-factory");
    await refresh();
    if(ids.length){const item=state.data?.items.find(item=>item.id===ids[0]);if(item){state.focus=item.id;state.tab=tab(item);state.selected=new Set(ids);}}
    render();
  }
  async function send(payload,button) {
    if(button?.dataset.factorySending)return;
    if(button){button.dataset.factorySending="true";button.disabled=true;}
    try {
      const result=await api("/receive","POST",payload);accept(result.state);
      showNotice(result.added ? result.added+" élément"+(result.added>1?"s ajoutés":" ajouté")+" à l’usine" : "Déjà dans l’usine",()=>open(result.ids));
      return result;
    }catch(error){showNotice(error.message);throw error;}
    finally{if(button){delete button.dataset.factorySending;button.disabled=false;}}
  }
  async function upload(file) {
    if(!uploads.has(file)){
      const body=new FormData();body.append("image",file,file.name);
      uploads.set(file,core.request("/api/video-factory/assets",{method:"POST",body}).catch(error=>{uploads.delete(file);throw error;}));
    }
    return uploads.get(file);
  }
  function renderSetup(mode, sessionId) {
    const parameters=window.PanelForgeH3Render?.factorySnapshot(mode, sessionId);
    if(!parameters)return {};
    const {recipe_id,recipe_version,prompt,aspect_ratio,megapixels,duration_seconds,steps,seed,...other}=parameters;
    return {final_prompt:prompt,render:{recipe:{id:recipe_id,version:recipe_version},
      settings:{aspect_ratio,megapixels,duration_seconds,steps,seed:seed || 0},...other}};
  }
  function imageButton({assetId,name,sourceId}) {
    const button=document.createElement("button");button.type="button";button.className="factory-button";button.textContent="Envoyer à l’usine";
    button.onclick=()=>send({source_kind:"image",asset_id:assetId,source_id:sourceId,name:name||"Image KREA2"},button).catch(()=>{});
    return button;
  }
  function stageLabel(item,key) {
    const step=item.steps[key];
    if(step.status==="skipped")return key==="plan"?"Fourni":"Off";
    if(step.status==="succeeded")return "✓ Prêt";
    if(step.status==="running")return step.progress==null?"En cours":Math.round(step.progress*100)+" %";
    if(step.status==="failed")return "Erreur";
    if(step.status==="cancelled")return "À reprendre";
    return key==="social" ? item.config.social.language.toUpperCase()+" · "+item.config.social.variant_count : "À suivre";
  }
  function render() {
    if(!state.data)return;
    const counts={preparation:0,production:0,results:0};state.data.items.forEach(item=>counts[tab(item)]++);
    document.querySelectorAll("[data-vf-tab]").forEach(button=>{button.classList.toggle("active",button.dataset.vfTab===state.tab);button.querySelector("span").textContent=counts[button.dataset.vfTab];});
    const errorCount=state.data.items.filter(errors).length;
    $("nav-errors").hidden=!errorCount;$("nav-errors").textContent=errorCount;
    $("nav-errors").title=errorCount+" traitement(s) avec une étape en erreur";
    const active=state.data.items.some(item=>item.status==="active");
    $("pause").textContent=state.data.paused?"Reprendre la file":"Pause après les étapes actives";
    $("machines").innerHTML=(state.data.paused?'<span class="vf-paused">'+(active?"Pause demandée · les étapes actives se terminent":"File en pause")+"</span>":"")+
      Object.entries(state.data.machines||{}).map(([key,machine])=>'<span>'+escape(key==="local_gpu"?"Local":"Serveur")+" · "+escape(machine.operation||({idle:"Disponible",busy:"Occupé",cooling:"Refroidissement",hot:"Refroidissement",paused:"En pause",unavailable:"Indisponible"}[machine.state]||machine.state))+"</span>").join("");
    if(state.data.scheduler_error)$("message").textContent=state.data.scheduler_error;
    let previousGroup=null;
    $("rows").innerHTML=visible().map(item=>{
      const groupId=group(item);let header="";
      if(groupId&&groupId!==previousGroup)header='<tr class="vf-group"><td colspan="8"><label><input type="checkbox" data-vf-group="'+escape(groupId)+'" '+(visible().filter(i=>group(i)===groupId).every(i=>state.selected.has(i.id))?"checked":"")+">"+escape(item.source.group)+"</label></td></tr>";
      previousGroup=groupId;
      const image=item.config.references[0];
      const stateLabel=item.cancel_requested&&item.status==="active"?"Annulation demandée":item.status==="preparation"?(item.ready?"Prêt":"À compléter"):({queued:"En attente",active:"En cours",succeeded:"Terminé",failed:"En erreur",cancelled:"Annulé"}[item.status]);
      const reason=item.status==="preparation"?item.issues.join(" "):item.waiting_reason || (errors(item)?"Une étape est à reprendre":"");
      return header+'<tr data-vf-id="'+item.id+'" class="'+(state.focus===item.id?"selected":"")+'"><td><label class="vf-select"><input type="checkbox" data-vf-select '+(state.selected.has(item.id)?"checked":"")+' aria-label="Sélectionner '+escape(item.name)+'"><span>'+String(state.data.items.indexOf(item)+1).padStart(2,"0")+'</span></label></td><td><div class="vf-video-title">'+(image?'<img src="'+assetUrl(image.asset_id)+'" alt="" loading="lazy">':"")+'<div><button type="button" data-vf-open>'+escape(item.name)+'</button><small>'+escape(state.data.presets[item.config.preset])+' · '+escape(item.config.mode.toUpperCase())+(item.source.kind==="episode"?" · scène "+(item.source.index+1):"")+'</small></div></div></td>'+
        stages.map(key=>'<td><button type="button" data-vf-stage="'+key+'" class="vf-stage '+item.steps[key].status+'" title="'+escape(labels[key]+" · "+(item.steps[key].message||item.steps[key].error||stageLabel(item,key)))+'">'+escape(stageLabel(item,key))+'</button></td>').join("")+
        '<td class="vf-state"><strong class="'+(!item.ready&&item.status==="preparation"?"warning":errors(item)?"failed":"")+'">'+stateLabel+'</strong>'+escape(reason)+'</td></tr>';
    }).join("");
    $("empty").hidden=visible().length>0;
    $("empty").textContent=state.tab==="preparation"?"Envoie une image, un parcours H3 / REF2V ou les scènes d’une histoire à l’usine.":state.tab==="production"?"Aucune vidéo en production. Lance les lignes prêtes depuis Préparation.":"Les vidéos terminées, annulées et les erreurs apparaîtront ici.";
    renderToolbar();
    const inspectorKey=current() ? current().id+":"+current().revision : "empty";
    if(!state.dirty && state.inspectorKey!==inspectorKey){renderInspector();state.inspectorKey=inspectorKey;}
  }
  function renderToolbar() {
    if(!state.data)return;
    const items=selected(),preparation=state.tab==="preparation";
    $("selected-count").textContent=items.length+" sélectionné"+(items.length>1?"s":"");
    $("select-all").checked=visible().length>0&&visible().every(item=>state.selected.has(item.id));
    $("select-all").indeterminate=!$("select-all").checked&&visible().some(item=>state.selected.has(item.id));
    for(const id of ["bulk-preset","bulk-settings","launch"])$(id).hidden=!preparation;
    $("cancel").hidden=state.tab!=="production";$("retry").hidden=state.tab!=="results";
    for(const id of ["bulk-preset","bulk-settings","up","down","cancel","retry"])$(id).disabled=state.busy||!items.length;
    $("launch").disabled=state.busy||state.dirty||!items.length||items.some(item=>!item.ready||item.status!=="preparation");
    $("launch").textContent="Lancer la sélection"+(items.length?" ("+items.length+")":"");
    $("launch").title=state.dirty?"Enregistre les modifications en cours.":items.some(item=>!item.ready)?"La sélection contient des éléments à compléter. Utilise le filtre Prêts.":"Ajouter explicitement à la production";
    $("retry").disabled=state.busy||!items.length||items.some(item=>!["failed","cancelled"].includes(item.status));
    $("pause").disabled=state.busy;$("refresh").disabled=state.busy;
  }
  function valueAt(object,path){return path.split(".").reduce((value,key)=>value?.[key],object);}
  function assign(object,path,value){const parts=path.split(".");const last=parts.pop();let target=object;for(const key of parts)target=target[key]??(target[key]={});target[last]=value;}
  function field(label,path,type="text",attributes="") {
    const value=valueAt(state.draft,path),disabled=current()?.status!=="preparation"?"disabled":"";
    return '<label>'+escape(label)+'<input data-vf-field="'+path+'" type="'+type+'" value="'+escape(value??"")+'" '+attributes+" "+disabled+"></label>";
  }
  function selectField(label,path,options) {
    return '<label>'+escape(label)+'<select data-vf-field="'+path+'" '+(current()?.status!=="preparation"?"disabled":"")+'>'+options.map(value=>
      '<option value="'+escape(value)+'" '+(valueAt(state.draft,path)===value?"selected":"")+'>'+escape(value)+'</option>').join("")+'</select></label>';
  }
  function check(label,path) {
    return '<label class="vf-check"><input type="checkbox" data-vf-field="'+path+'" '+(valueAt(state.draft,path)?"checked":"")+" "+(current()?.status!=="preparation"?"disabled":"")+">"+escape(label)+"</label>";
  }
  function renderInspector() {
    const item=current();if(!item){$("inspector").innerHTML='<p class="vf-empty">Sélectionne une vidéo pour voir ses réglages.</p>';return;}
    state.draft={name:item.name,...clone(item.config)};state.revision=item.revision;
    const config=item.config,disabled=item.status!=="preparation"?"disabled":"";
    $("inspector").innerHTML='<div class="vf-inspector-title"><h2>'+escape(item.name)+'</h2><button type="button" data-vf-action="duplicate">Dupliquer</button></div><p class="vf-source">'+escape(item.source.group||({image:"Image Lab",h3:"H3",ref2v:"REF2V",session:"Parcours"}[item.source.kind]||"Source"))+' <button type="button" data-vf-source>Ouvrir la source</button></p>'+
      (item.issues.length?'<p class="vf-errors">'+item.issues.map(escape).join("<br>")+"</p>":"")+
      '<div class="vf-inspector-actions">'+(item.status!=="preparation"&&item.status!=="active"?'<button type="button" data-vf-action="edit">Modifier · remettre en préparation</button>':"")+
      (item.status==="preparation"?'<button type="button" data-vf-action="remove">Retirer</button>':"")+
      (item.source.kind==="episode"&&item.status==="preparation"?'<button type="button" data-vf-refresh-source>Recharger depuis l’histoire</button>':"")+'</div>'+
      '<section>'+field("Nom","name")+'<label>Preset<select id="vf-item-preset" '+disabled+'>'+Object.entries(state.data.presets).map(([key,label])=>'<option value="'+key+'" '+(key===config.preset?"selected":"")+">"+escape(label)+"</option>").join("")+'</select></label>'+
      (config.preset==="custom"&&config.preset_origin?'<small class="vf-source">Basé sur '+escape(state.data.presets[config.preset_origin])+"</small>":"")+'</section>'+
      '<section><h3>Images et rôles</h3>'+config.references.map((ref,index)=>'<div class="vf-reference"><img src="'+assetUrl(ref.asset_id)+'" alt=""><div><small>'+escape(ref.label||"Image")+'</small><select data-vf-role="'+index+'" '+disabled+' aria-label="Rôle de '+escape(ref.label||"l’image")+'">'+Object.entries(roles).filter(([key])=>config.mode==="ref2v"||["unassigned","first_frame","last_frame",ref.role].includes(key)).map(([key,label])=>'<option value="'+key+'" '+(ref.role===key?"selected":"")+">"+label+"</option>").join("")+'</select></div><button type="button" data-vf-remove-ref="'+index+'" aria-label="Retirer cette image" '+disabled+'>×</button></div>').join("")+
      '<label>Associer une image<input id="vf-add-reference" type="file" accept="image/png,image/jpeg,image/webp" multiple '+disabled+'></label></section>'+
      '<section><div class="vf-fields"><label>Mode<select data-vf-field="mode" '+disabled+'><option value="h3" '+(config.mode==="h3"?"selected":"")+'>H3 / FL2V</option><option value="ref2v" '+(config.mode==="ref2v"?"selected":"")+'>REF2V</option></select></label><label>Nombre de plans<select data-vf-field="shot_count" '+disabled+'><option value="auto">Auto</option>'+[1,2,3,4,5,6].map(n=>'<option '+(config.shot_count===n?"selected":"")+">"+n+"</option>").join("")+'</select></label></div>'+
      '<label>Intention<textarea data-vf-field="intention" rows="5" '+disabled+'>'+escape(config.intention)+'</textarea></label><details><summary>Prompt final déjà préparé</summary><p class="vf-source">Un prompt final renseigné est utilisé directement, sans refaire le plan.</p><textarea data-vf-field="final_prompt" aria-label="Prompt final" rows="6" '+disabled+'>'+escape(config.final_prompt)+'</textarea></details></section>'+
      '<section><h3>Rendu vidéo</h3><p class="vf-source">'+escape(config.render.recipe.id)+" · "+escape(config.render.recipe.version)+'</p><div class="vf-fields">'+field("Durée (s)","render.settings.duration_seconds","number",'min="5" max="15" step="0.5"')+field("Résolution (MP)","render.settings.megapixels","number",'min="0.1" max="4" step="0.1"')+'</div><p class="vf-source">La durée de rendu ne réécrit pas un prompt déjà préparé.</p>'+
      '<details><summary>Réglages avancés</summary><div class="vf-fields">'+selectField("Ratio","render.settings.aspect_ratio",["9:16 (Portrait Widescreen)","16:9 (Widescreen)","1:1 (Square)","2:3 (Portrait Photo)","3:2 (Photo)","3:4 (Portrait Standard)","4:3 (Standard)","21:9 (Ultrawide)"])+field("Résolution initiale (MP)","render.initial_megapixels","number",'min="0.1" max="4" step="0.1"')+
      field("Steps","render.settings.steps","number",'min="2" max="100"')+field("Seed","render.settings.seed","text")+'</div>'+check("Conserver cette seed","render.seed_locked")+check("Musique","render.music_enabled")+field("Checkpoint (vide : défaut de la recette)","render.checkpoint")+
      (config.render.bunny?'<div class="vf-fields">'+field("Steps de base","render.bunny.base_steps","number",'min="2" max="100"')+field("Première passe","render.bunny.coarse_steps","number",'min="1" max="99"')+field("Seconde passe","render.bunny.refine_steps","number",'min="3" max="5"')+'</div>'+check("Turbo","render.bunny.turbo_enabled")+check("Preview","render.bunny.preview_enabled"):check("Spectrum","render.spectrum_enabled")+check("Forcer l’upscale","render.force_upscale"))+
      (config.render.video_loras?check("Activer les LoRA vidéo","render.video_loras.enabled")+(config.render.video_loras.entries||[]).map((entry,index)=>'<div class="vf-lora">'+field("LoRA","render.video_loras.entries."+index+".name")+'<div class="vf-fields">'+field("Force · passe 1","render.video_loras.entries."+index+".strength","number",'min="0" max="2" step="0.05"')+(config.render.bunny?field("Force · passe 2","render.video_loras.entries."+index+".second_strength","number",'min="0" max="2" step="0.05"'):"")+'</div>'+check("Activée","render.video_loras.entries."+index+".enabled")+'</div>').join(""):"")+
      field("Modèle du plan","plan_model_id")+field("Modèle du prompt","writer_model_id")+
      '<div class="vf-fields">'+field("Vie de la scène","creative_axes.scene_life","number",'min="0" max="3"')+field("Caméra","creative_axes.camera","number",'min="0" max="3"')+field("Mouvements","creative_axes.extra_motion","number",'min="0" max="3"')+field("Dialogues","creative_axes.dialogue","number",'min="0" max="3"')+field("Audace","creative_audacity","number",'min="0" max="3"')+'</div>' +'</details></section>'+
      '<section>'+check("Appliquer le DLSS","dlss.enabled")+check("Préparer le texte Instagram","social.enabled")+
      '<div id="vf-social-fields" '+(config.social.enabled?"":"hidden")+'><div class="vf-fields"><label>Langue<select data-vf-field="social.language" '+disabled+'><option value="en" '+(config.social.language==="en"?"selected":"")+'>Anglais</option><option value="fr" '+(config.social.language==="fr"?"selected":"")+'>Français</option></select></label>'+field("Variantes","social.variant_count","number",'min="1" max="6"')+'</div><p class="vf-source">Gemma 4 local · vidéo H3 associée automatiquement</p></div></section>'+
      ((item.history||[]).length?'<details><summary>Sorties précédentes ('+item.history.length+')</summary>'+item.history.map((entry,index)=>
        '<button type="button" data-vf-history="'+index+'">'+escape(labels[entry.stage])+" · "+escape(new Date(entry.at).toLocaleString())+'</button>').join("")+'</details>':"")+
      (disabled?"":'<div class="vf-dirty"><button type="button" id="vf-save" class="factory-button" disabled>Appliquer les modifications</button><button type="button" id="vf-discard" disabled>Annuler</button></div>');
  }
  function markDirty(){state.dirty=true;$("save")?.removeAttribute("disabled");$("discard")?.removeAttribute("disabled");renderToolbar();}
  async function saveDraft() {
    if(!state.dirty)return;
    for(const input of $("inspector").querySelectorAll("input,textarea,select")){
      if(!input.checkValidity()){input.reportValidity();throw new Error("Corrige le réglage indiqué avant d’enregistrer.");}
    }
    const item=current(),changes=clone(state.draft);
    if(!changes.render.checkpoint)changes.render.checkpoint=null;
    if(changes.render.bunny)changes.render.settings.steps=Number(changes.render.bunny.coarse_steps)+Number(changes.render.bunny.refine_steps);
    const result=await api("/items","PATCH",{ids:[item.id],revisions:{[item.id]:state.revision},changes});
    state.dirty=false;accept(result.state);rememberUndo(result);
  }
  function rememberUndo(result){
    state.undo=result;
    showNotice("Réglages enregistrés",()=>busy(async()=>{
      const undo=state.undo;if(!undo)return;
      const response=await api("/items","PATCH",{ids:Object.keys(undo.undo),revisions:undo.revisions,replacements:undo.undo});
      state.dirty=false;accept(response.state);state.undo=null;showNotice("Modification annulée");
    }),"Annuler");
  }
  async function patch(items,changes,preset) {
    await saveDraft();
    const ids=items.map(item=>item.id),fresh=state.data.items.filter(item=>ids.includes(item.id));
    const result=await api("/items","PATCH",{...selection(fresh),changes,preset});
    accept(result.state);rememberUndo(result);
  }
  async function itemAction(action,items=selected()) {
    await saveDraft();
    const fresh=state.data.items.filter(item=>items.some(old=>old.id===item.id));
    accept(await api("/actions/"+action,"POST",selection(fresh)));
  }
  async function source(item) {
    const detail=clone(item.source);
    if (detail.kind === "image") return window.PanelForgeKrea2AssistedLab?.open(detail.id);
    if (detail.kind === "episode") {
      await window.PanelForgeEpisodes?.prepareLibraryNavigation();
      window.PanelForgeLabNavigation?.switchView("stories");
      await window.PanelForgeStories?.open(detail.story_id);
      return window.PanelForgeEpisodes?.openFromLibrary(detail.story_id, detail.id);
    }
    const workshop = detail.view === "ref2v-direct" ? window.PanelForgeRef2V : window.PanelForgeH3Base;
    await workshop?.open(detail.kind === "session" ? detail.id : null);
  }
  function detail(item,key) {
    const step=item.steps[key],body=$("detail-content");body.replaceChildren();
    $("detail-title").textContent=item.name+" · "+labels[key];
    if(step.error){const p=document.createElement("p");p.textContent=step.error;body.append(p);}
    if(step.output.source_warning){const p=document.createElement("p");p.textContent=step.output.source_warning;body.append(p);}
    if(step.output.asset_id){
      const video=document.createElement("video");video.controls=true;video.preload="metadata";video.src=assetUrl(step.output.asset_id);body.append(video);
      const download=document.createElement("a");download.href=video.src;download.download=item.name+".mp4";download.textContent="Télécharger la vidéo";body.append(download);
    }
    if(step.output.project_id && key === "social") {
      const link=document.createElement("button");link.type="button";link.textContent="Ouvrir dans Texte IG";
      link.onclick=()=>{ $("detail-dialog").close();busy(()=>window.PanelForgeSocialLab?.open(step.output.project_id));};body.append(link);
    }
    if(step.output.text){const pre=document.createElement("pre");pre.textContent=step.output.text;body.append(pre);}
    for(const variant of step.output.variants||[]){
      const article=document.createElement("article"),title=document.createElement("strong"),text=document.createElement("p"),tags=document.createElement("p");
      title.textContent=variant.hook||variant.angle;text.textContent=variant.caption;tags.textContent=(variant.hashtags||[]).join(" ");article.append(title,text,tags);body.append(article);
    }
    if(!body.children.length){const p=document.createElement("p");p.textContent=step.output.note||step.message||stageLabel(item,key);body.append(p);}
    $("detail-dialog").showModal();
  }
  document.querySelectorAll("[data-vf-tab]").forEach(button=>button.addEventListener("click",()=>busy(async()=>{await saveDraft();state.tab=button.dataset.vfTab;state.selected.clear();state.focus=null;$("filter").value="all";render();})));
  document.querySelector('[data-lab-view="video-factory"]')?.addEventListener("click",()=>refresh());
  $("refresh").onclick=()=>refresh();
  $("filter").onchange=()=>{state.selected.clear();render();};
  $("select-all").onchange=event=>{visible().forEach(item=>event.target.checked?state.selected.add(item.id):state.selected.delete(item.id));render();};
  $("rows").addEventListener("change",event=>{
    if(event.target.matches("[data-vf-group]"))visible().filter(item=>group(item)===event.target.dataset.vfGroup).forEach(item=>event.target.checked?state.selected.add(item.id):state.selected.delete(item.id));
    if(event.target.matches("[data-vf-select]")){const id=event.target.closest("[data-vf-id]").dataset.vfId;event.target.checked?state.selected.add(id):state.selected.delete(id);}
    renderToolbar();
  });
  $("rows").addEventListener("click",event=>{
    const tr=event.target.closest("[data-vf-id]");if(!tr)return;
    const item=state.data.items.find(item=>item.id===tr.dataset.vfId);
    if(event.target.closest("[data-vf-stage]"))return detail(item,event.target.closest("[data-vf-stage]").dataset.vfStage);
    if(event.target.closest("[data-vf-open]"))busy(async()=>{await saveDraft();state.focus=item.id;render();});
  });
  $("inspector").addEventListener("input",event=>{
    const path=event.target.dataset.vfField;if(!path)return;
    const target=event.target;
    if(!target.checkValidity()){markDirty();return;}
    let value=target.type==="checkbox"?target.checked:target.type==="number"?Number(target.value):target.value;
    if(path==="shot_count")value=value==="auto"?null:Number(value);
    assign(state.draft,path,value);
    if(path.startsWith("creative_axes.")){
      const a=state.draft.creative_axes, levels=[0,35,65,90];
      state.draft.creative_freedom=Math.round((levels[a.scene_life]+levels[a.camera]+levels[a.extra_motion])/3);
    }
    markDirty();
    if(path==="social.enabled")$("social-fields").hidden=!value;
    if(path==="mode"){
      for(const select of $("inspector").querySelectorAll("[data-vf-role]")){
        const reference=state.draft.references[Number(select.dataset.vfRole)];
        select.innerHTML=Object.entries(roles).filter(([key])=>value==="ref2v"||["unassigned","first_frame","last_frame",reference.role].includes(key))
          .map(([key,label])=>'<option value="'+key+'" '+(key===reference.role?"selected":"")+'>'+label+'</option>').join("");
      }
    }
  });
  $("inspector").addEventListener("change",event=>{
    if(event.target.id==="vf-item-preset")busy(()=>patch([current()],null,event.target.value));
    if(event.target.dataset.vfRole!==undefined){state.draft.references[Number(event.target.dataset.vfRole)].role=event.target.value;markDirty();}
    if(event.target.id==="vf-add-reference")busy(async()=>{
      await saveDraft();const refs=clone(current().config.references);
      for(const file of event.target.files){const ref=await upload(file);refs.push({...ref,role:"unassigned"});}
      await patch([current()],{references:refs});
    });
  });
  $("inspector").addEventListener("click",event=>{
    const button=event.target.closest("button");if(!button)return;
    if(button.id==="vf-save")busy(saveDraft);
    if(button.id==="vf-discard"){state.dirty=false;state.inspectorKey=null;render();}
    if(button.dataset.vfRemoveRef!==undefined)busy(async()=>{await saveDraft();const refs=clone(current().config.references);refs.splice(Number(button.dataset.vfRemoveRef),1);await patch([current()],{references:refs});});
    if(button.dataset.vfHistory!==undefined){
      const item=current(),entry=item.history[Number(button.dataset.vfHistory)];
      detail({...item,steps:{...item.steps,[entry.stage]:{status:"succeeded",output:entry.output}}},entry.stage);
    }
    if(button.dataset.vfAction)busy(()=>itemAction(button.dataset.vfAction,[current()]));
    if(button.hasAttribute("data-vf-source"))busy(async()=>{await saveDraft();await source(current());});
    if(button.hasAttribute("data-vf-refresh-source"))busy(async()=>{await saveDraft();accept(await api("/items/"+current().id+"/refresh-source","POST",selection([current()])));});
  });
  $("bulk-preset").onchange=event=>{const preset=event.target.value;event.target.value="";if(preset)busy(()=>patch(selected(),null,preset));};
  $("bulk-settings").onclick=()=>{$("bulk-form").reset();$("bulk-summary").textContent=selected().length+" lignes sélectionnées. Les valeurs non renseignées, même différentes, sont conservées.";$("bulk-dialog").showModal();};
  $("bulk-form").onsubmit=event=>{event.preventDefault();busy(async()=>{
    const data=new FormData(event.target),changes={};
    if(data.get("duration"))changes.render={settings:{duration_seconds:Number(data.get("duration"))}};
    if(data.get("plans"))changes.shot_count=data.get("plans")==="auto"?null:Number(data.get("plans"));
    if(data.get("social"))changes.social=data.get("social")==="on"?{enabled:true,language:"en",variant_count:3}:{enabled:false};
    if(data.get("dlss"))changes.dlss={enabled:data.get("dlss")==="on"};
    await patch(selected(),changes);$("bulk-dialog").close();
  });};
  $("launch").onclick=()=>busy(async()=>{await saveDraft();accept(await api("/launch","POST",selection(selected())));state.tab="production";state.selected.clear();render();});
  $("cancel").onclick=()=>busy(()=>itemAction("cancel"));
  $("retry").onclick=()=>busy(async()=>{await itemAction("retry");state.tab="production";state.selected.clear();render();});
  $("pause").onclick=()=>busy(async()=>accept(await api("/actions/"+(state.data.paused?"resume":"pause"),"POST",{})));
  async function move(direction){
    await saveDraft();const ids=state.data.items.map(item=>item.id);
    const positions=ids.map((id,index)=>state.selected.has(id)?index:-1).filter(index=>index>=0);
    if(direction>0)positions.reverse();
    for(const index of positions){const other=index+direction;if(other>=0&&other<ids.length&&!state.selected.has(ids[other]))[ids[index],ids[other]]=[ids[other],ids[index]];}
    accept(await api("/order","PUT",{ids,revision:state.data.revision}));
  }
  $("up").onclick=()=>busy(()=>move(-1));$("down").onclick=()=>busy(()=>move(1));
  document.querySelectorAll("[data-vf-close]").forEach(button=>button.onclick=()=>button.closest("dialog").close());
  window.PanelForgeVideoFactory=Object.freeze({send,upload,renderSetup,imageButton,open});
  setInterval(()=>refresh(),5000);
  refresh();
})();
