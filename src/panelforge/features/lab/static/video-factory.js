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
  const state = {data:null,tab:"preparation",resultSort:"chronological",selected:new Set(),focus:null,busy:false,dirty:false,draft:null,revision:null,undo:null,refreshing:false};
  const uploads = new WeakMap();
  let noticeTimer;
  const topbar = document.querySelector(".topbar");
  const stickyHeader = root.querySelector(".vf-sticky-header");
  const stickyToolbar = root.querySelector(".vf-toolbar");
  const syncStickyGeometry = () => {
    for (const [element, property] of [[topbar, "--vf-sticky-top"], [stickyHeader, "--vf-sticky-header-height"], [stickyToolbar, "--vf-sticky-toolbar-height"]]) {
      const height = Math.ceil(element?.getBoundingClientRect().height || 0);
      if (height) root.style.setProperty(property, `${height}px`);
    }
  };
  syncStickyGeometry();
  if ("ResizeObserver" in window) {
    const stickyObserver = new ResizeObserver(syncStickyGeometry);
    [topbar, stickyHeader, stickyToolbar].filter(Boolean).forEach(element => stickyObserver.observe(element));
  } else {
    window.addEventListener("resize", syncStickyGeometry);
  }
  const api = (path,method="GET",body) => core.request("/api/video-factory" + path, {method,...(body===undefined?{}:{headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  const current = () => state.data?.items.find(item=>item.id===state.focus);
  const group = item => item.source.kind === "episode" ? item.source.id : "";
  const tab = item => item.remove_requested ? "production" : item.archived_at ? "archives" : item.status === "preparation" ? "preparation" : ["queued","active"].includes(item.status) ? "production" : "results";
  const errors = item => Object.values(item.steps).some(step=>step.status==="failed") || item.delivery?.status==="failed";
  const canRetry = item => !item.archived_at && !item.remove_requested && !item.recover_stage &&
    (["failed","cancelled"].includes(item.status) || item.status==="succeeded" && item.delivery?.status==="failed");
  const canArchive = item => !item.archived_at && item.can_archive===true;
  const assetUrl = id => "/api/assets/" + encodeURIComponent(id) + "/content";
  const selected = () => (state.data?.items || []).filter(item=>state.selected.has(item.id));
  const selection = items => ({ids:items.map(item=>item.id), revisions:Object.fromEntries(items.map(item=>[item.id,item.revision]))});
  const monitoring=window.PanelForgeFactoryMonitor?.create({root,escape,request:api,getState:()=>state,getSelection:selected});
  function resultDate(item) {
    const completed=[item.delivery?.finished_at,...Object.values(item.steps).map(step=>step.finished_at)]
      .map(value=>Date.parse(value)).filter(Number.isFinite);
    return completed.length?Math.max(...completed):Date.parse(item.launched_at||item.created_at)||0;
  }
  function visible() {
    const filter = $("filter").value;
    const items=(state.data?.items || []).filter(item=>tab(item)===state.tab && (
      filter==="all" || filter==="ready" && item.status==="preparation" && item.ready ||
      filter==="incomplete" && item.status==="preparation" && !item.ready || filter==="failed" && errors(item) ||
      filter==="archivable" && canArchive(item)));
    if(state.tab!=="results"||state.resultSort!=="newest")return items;
    // Sort display blocks, keeping each story together and its scene order intact.
    const blocks=new Map();
    items.forEach((item,index)=>{
      const key=group(item)?"episode:"+group(item):"item:"+item.id;
      if(!blocks.has(key))blocks.set(key,{items:[],date:0,index});
      const block=blocks.get(key);block.items.push(item);block.date=Math.max(block.date,resultDate(item));
    });
    return [...blocks.values()].sort((a,b)=>b.date-a.date||a.index-b.index).flatMap(block=>block.items);
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
    // A GET begun before a preset edit must not restore the previous revision.
    if(state.data&&data.revision<state.data.revision)return;
    state.data=data;
    monitoring?.received();
    const ids=new Set(data.items.map(item=>item.id));
    state.selected=new Set([...state.selected].filter(id=>ids.has(id) && tab(data.items.find(item=>item.id===id))===state.tab));
    if(state.focus&&(!ids.has(state.focus)||!state.dirty&&tab(current())!==state.tab)){state.focus=null;state.dirty=false;}
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
    if(ids.length){const item=state.data?.items.find(item=>item.id===ids[0]);if(item){state.focus=item.id;state.tab=tab(item);$("filter").value="all";state.selected=new Set(ids.filter(id=>state.data.items.some(i=>i.id===id&&tab(i)===state.tab)));}}
    render();
  }
  async function send(payload,button) {
    if(button?.dataset.factorySending)return;
    if(button){button.dataset.factorySending="true";button.disabled=true;}
    try {
      const result=await api("/receive","POST",payload);accept(result.state);
      const existing=result.existing||[],statusNames={preparation:"Préparation",queued:"Production · en attente",active:"Production · en cours",succeeded:"Résultats · terminé",failed:"Résultats · en erreur",cancelled:"Résultats · annulé"};
      let receipt=result.added ? result.added+" élément"+(result.added>1?"s ajoutés":" ajouté")+" à l’usine" : existing.length&&existing.every(item=>item.archived_at)?"Déjà archivé":"Déjà dans l’usine";
      if(existing.length)receipt+=". Déjà présent : "+existing.slice(0,5).map(item=>
        (item.scene_index==null?item.name:"scène "+(item.scene_index+1))+" ("+(item.remove_requested?"suppression en cours":item.archived_at?"Archives":statusNames[item.status]||item.status)+")").join(" ; ")+(existing.length>5?"…":"");
      showNotice(receipt,()=>open(result.ids));
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
  function titleMarkup(item) {
    const language=item.runtime?.episode_inputs?.localization?.language;
    const english=item.source.kind==="episode" && ["en","english"].includes(String(language||"").toLowerCase());
    return escape(item.name)+(english?' <span class="vf-language" title="Répliques anglaises dans le prompt vidéo" aria-label="Répliques en anglais">EN</span>':"");
  }
  function progressRatio(value,key) {
    if(key==="dlss" && value && typeof value==="object"){
      const {stage_index:index,stage_count:count,percent}=value;
      if(!Number.isInteger(index)||!Number.isInteger(count)||index<0||index>=count)return null;
      if(percent!=null&&!Number.isFinite(percent))return null;
      value=(index+(percent==null?0:Math.min(100,Math.max(0,percent))/100))/count;
    }
    return Number.isFinite(value)?Math.min(1,Math.max(0,value)):null;
  }
  function stageLabel(item,key) {
    const step=item.steps[key];
    if(step.status==="skipped")return key==="plan"?"Fourni":"Off";
    if(step.status==="succeeded")return "✓ Prêt";
    if(step.status==="running"){
      if(key==="dlss" && /Finalisation|DLSS.*(?:receiving|importing)/i.test(step.message||""))return "Finalisation";
      const ratio=progressRatio(step.progress,key);
      return ratio===null?"En cours":Math.round(ratio*100)+" %";
    }
    if(step.status==="failed")return "Erreur";
    if(step.status==="cancelled")return "À reprendre";
    return key==="social" ? item.config.social.language.toUpperCase()+" · "+item.config.social.variant_count : "À suivre";
  }
  function stageDuration(step, now=Date.now()) {
    if(!["running","succeeded","failed","cancelled"].includes(step.status)||!step.started_at)return "";
    const start=Date.parse(step.started_at),end=step.status==="running"?now:Date.parse(step.finished_at);
    if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return "";
    const seconds=(end-start)/1000;
    return seconds<1?"<1 s":Math.round(seconds)+" s";
  }
  function durationMarkup(item,key) {
    return state.tab==="preparation"?"":'<small class="vf-stage-duration" data-vf-duration="'+key+'">'+escape(stageDuration(item.steps[key]))+'</small>'+(monitoring?.step(item,key)||"");
  }
  function updateDurations() {
    if(root.hidden||!state.data)return;
    monitoring?.tick();
    for(const node of $("rows").querySelectorAll("[data-vf-duration]")){
      const item=state.data.items.find(i=>i.id===node.closest("[data-vf-id]").dataset.vfId);
      if(item)node.textContent=stageDuration(item.steps[node.dataset.vfDuration]);
    }
  }
  function imagePreview(ref,label) {
    const name=label||ref.label||"Image";
    return '<button type="button" class="vf-image-open" data-vf-preview="'+escape(ref.asset_id)+'" data-vf-image-label="'+escape(name)+'" aria-label="Agrandir '+escape(name)+'" title="Agrandir l’image">'+
      '<img src="'+assetUrl(ref.asset_id)+'" alt="'+escape(name)+'" loading="lazy"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6M10 7v6"/></svg></button>';
  }
  function openImage(button) {
    $("image-title").textContent=button.dataset.vfImageLabel;
    $("image-content").src=assetUrl(button.dataset.vfPreview);
    $("image-content").alt=button.dataset.vfImageLabel;
    if(!$("image-dialog").open)$("image-dialog").showModal();
  }
  async function resumeChain(items) {
    await itemAction("retry",items);
    state.tab=state.data.items.some(item=>items.some(old=>old.id===item.id)&&tab(item)==="production")?"production":"results";
    state.selected.clear();render();
  }
  function render() {
    if(!state.data)return;
    root.dataset.vfView=state.tab;
    const counts={preparation:0,production:0,results:0,archives:0};state.data.items.forEach(item=>counts[tab(item)]++);
    document.querySelectorAll("[data-vf-tab]").forEach(button=>{button.classList.toggle("active",button.dataset.vfTab===state.tab);button.querySelector("span").textContent=counts[button.dataset.vfTab];});
    const errorCount=state.data.items.filter(item=>!item.archived_at&&errors(item)).length;
    $("nav-errors").hidden=!errorCount;$("nav-errors").textContent=errorCount;
    $("nav-errors").title=errorCount+" traitement(s) avec une étape en erreur";
    $("pause").textContent=state.data.paused?"Reprendre":"Pause";
    $("pause").title=state.data.paused?"Reprendre la file":"Mettre la file en pause après les étapes actives";
    if(state.data.scheduler_error)$("message").textContent=state.data.scheduler_error;
    const rows=visible();
    $("rows").innerHTML=rows.map((item,index)=>{
      const groupId=group(item),first=groupId&&(!index||group(rows[index-1])!==groupId);
      const last=groupId&&(index===rows.length-1||group(rows[index+1])!==groupId);
      let header="";
      if(first){
        const members=rows.filter(i=>group(i)===groupId),count=members.length;
        header='<tr class="vf-group"><td colspan="8"><label><input type="checkbox" data-vf-group="'+escape(groupId)+'" '+(members.every(i=>state.selected.has(i.id))?"checked":"")+">"+escape(item.source.group)+' <span class="vf-group-count">· '+count+' scène'+(count>1?'s':'')+'</span></label></td></tr>';
      }
      const rowClasses=[state.focus===item.id?"selected":"",groupId?"vf-group-member":"",last?"vf-group-end":""].filter(Boolean).join(" ");
      const spacer=last&&index<rows.length-1?'<tr class="vf-group-gap" aria-hidden="true"><td colspan="8"></td></tr>':"";
      const image=item.config.references[0];
      const stateLabel=item.remove_requested?"Suppression en cours":item.archived_at?"Archivé":item.cancel_requested&&item.status==="active"?"Annulation demandée":item.status==="preparation"?(item.ready?"Prêt":"À compléter"):({queued:"En attente",active:"En cours",succeeded:"Terminé",failed:"En erreur",cancelled:"Annulé"}[item.status]);
      const reason=item.status==="preparation"?item.issues.join(" "):item.waiting_reason || (errors(item)?"Une étape est à reprendre":"");
      return header+'<tr data-vf-id="'+item.id+'" class="'+rowClasses+'"><td><label class="vf-select"><input type="checkbox" data-vf-select '+(state.selected.has(item.id)?"checked":"")+' aria-label="Sélectionner '+escape(item.name)+'"><span>'+String(state.data.items.indexOf(item)+1).padStart(2,"0")+'</span></label></td><td><div class="vf-video-title">'+(image?imagePreview(image,item.name):"")+'<div><button type="button" data-vf-open>'+titleMarkup(item)+'</button><small>'+escape(state.data.presets[item.config.preset])+' · '+escape(item.config.mode.toUpperCase())+(item.source.kind==="episode"?" · scène "+(item.source.index+1):"")+'</small></div></div></td>'+
        stages.map(key=>'<td><button type="button" data-vf-stage="'+key+'" class="vf-stage '+item.steps[key].status+'" title="'+escape(labels[key]+" · "+(item.steps[key].message||item.steps[key].error||stageLabel(item,key)))+'">'+escape(stageLabel(item,key))+'</button>'+durationMarkup(item,key)+'</td>').join("")+
        '<td class="vf-state">'+stateCell(item,stateLabel,reason)+'</td></tr>'+spacer;
    }).join("");
    $("empty").hidden=visible().length>0;
    $("empty").textContent=state.tab==="preparation"?"Envoie une image, un parcours H3 / REF2V ou les scènes d’une histoire à l’usine.":state.tab==="production"?"Aucune vidéo en production. Lance les lignes prêtes depuis Préparation.":state.tab==="archives"?"Les résultats que tu archives restent consultables ici, avec leurs fichiers.":"Les vidéos terminées, annulées et les erreurs apparaîtront ici.";
    renderToolbar();
    if (!root.hidden) syncStickyGeometry();
    const inspectorKey=current() ? current().id+":"+current().revision : "empty";
    if(!state.dirty && state.inspectorKey!==inspectorKey){renderInspector();state.inspectorKey=inspectorKey;}
    monitoring?.render();
  }
  function stateCell(item,label,reason) {
    const status='<strong class="'+(!item.ready&&item.status==="preparation"?"warning":errors(item)?"failed":item.status==="preparation"&&item.ready&&!item.remove_requested&&!item.archived_at?"vf-preparation-ready":"")+'">'+escape(label)+'</strong>';
    const forecast=monitoring?.row(item)||"";
    if(!["results","archives"].includes(state.tab))return status+escape(reason)+forecast;
    return resultActions(item,status,reason)+forecast;
  }
  function archiveButton(item,attribute="data-vf-archive") {
    return item.status==="succeeded"&&!item.archived_at?'<button type="button" '+attribute+' '+(canArchive(item)?'':'disabled title="Attendre la fin de toutes les étapes et du rangement des fichiers, sans erreur."')+'>Archiver</button>':"";
  }
  function resultActions(item,status,reason) {
    const delivery=item.delivery,hasVideo=!!item.steps.video.output.asset_id;
    let html='<div class="vf-result-actions">'+status;
    if(hasVideo)html+='<button type="button" data-vf-result="'+(item.steps.dlss.output.asset_id?"dlss":"video")+'">'+(item.steps.dlss.output.asset_id?"Voir le DLSS":"Voir la vidéo")+'</button>';
    if(delivery?.folder)html+='<button type="button" data-vf-folder title="'+escape(delivery.folder)+'">Ouvrir le dossier</button>';
    if(item.steps.social.output.variants?.length)html+='<button type="button" data-vf-result="social">Texte IG · copier</button>';
    if(item.archived_at)html+='<button type="button" data-vf-restore title="Restaurer dans Résultats sans relancer">Restaurer</button>';
    else html+=archiveButton(item);
    if(canRetry(item))html+='<button type="button" data-vf-retry>Reprendre la chaîne</button>';
    html+='<button type="button" class="vf-remove" data-vf-delete>Supprimer</button>';
    if(reason)html+='<small class="vf-result-note">'+escape(reason)+'</small>';
    if(delivery?.status==="failed")html+='<small class="vf-export-error" title="'+escape(delivery.error)+'">Export à reprendre</small>';
    else if(delivery?.status==="copying"||delivery?.status==="queued"||item.status==="succeeded"&&!item.archived_at&&!canArchive(item))html+='<small class="vf-result-note">Rangement des fichiers…</small>';
    return html+'</div>';
  }
  async function copyText(text,button) {
    try {
      await navigator.clipboard.writeText(text);
      const previous=button.textContent;button.textContent="Copié";
      setTimeout(()=>button.textContent=previous,1500);
    } catch (_) {
      const field=document.createElement("textarea");field.className="vf-copy-fallback";field.value=text;field.readOnly=true;
      button.parentNode.append(field);field.focus();field.select();
      showNotice("Texte sélectionné : utilise Ctrl+C pour le copier.");
    }
  }
  async function openFolder(item) {
    await api("/items/"+encodeURIComponent(item.id)+"/open-folder","POST",{});
  }
  function resultFiles(item,body) {
    const delivery=item.delivery;
    if(!delivery?.folder)return;
    const section=document.createElement("section");section.className="vf-result-files";
    const path=document.createElement("p");path.textContent=delivery.folder;
    const open=document.createElement("button");open.type="button";open.textContent="Ouvrir le dossier sur ce PC";
    open.onclick=()=>busy(()=>openFolder(item));
    const copy=document.createElement("button");copy.type="button";copy.textContent="Copier le chemin";
    copy.onclick=()=>copyText(delivery.folder,copy);
    section.append(path,open,copy);
    if(delivery.status==="failed"){
      const error=document.createElement("p");error.className="vf-export-error";error.textContent=delivery.error;
      const retry=document.createElement("button");retry.type="button";retry.textContent="Reprendre la chaîne";
      retry.disabled=!canRetry(item);
      retry.onclick=()=>busy(async()=>{await resumeChain([item]);$("detail-dialog").close();});
      section.append(error,retry);
    }
    body.append(section);
  }
  function renderToolbar() {
    if(!state.data)return;
    const items=selected(),preparation=state.tab==="preparation";
    root.querySelectorAll(".vf-preparation-ready").forEach(node=>{
      node.hidden=preparation&&state.selected.has(node.closest("[data-vf-id]").dataset.vfId);
    });
    $("results-sort").hidden=state.tab!=="results";$("results-sort").value=state.resultSort;
    $("results-sort").disabled=state.busy;
    $("selected-count").textContent=items.length+" sélectionné"+(items.length>1?"s":"");
    $("select-all").checked=visible().length>0&&visible().every(item=>state.selected.has(item.id));
    $("select-all").indeterminate=!$("select-all").checked&&visible().some(item=>state.selected.has(item.id));
    for(const id of ["bulk-preset","bulk-settings","launch"])$(id).hidden=!preparation;
    $("cancel").hidden=state.tab!=="production";$("retry").hidden=state.tab!=="results";
    $("archive").hidden=state.tab!=="results";$("restore").hidden=state.tab!=="archives";
    for(const id of ["up","down"])$(id).hidden=!["preparation","production"].includes(state.tab);
    for(const option of $("filter").options){
      option.hidden=["ready","incomplete"].includes(option.value)?!preparation:option.value==="archivable"?state.tab!=="results":option.value==="failed"?state.tab==="archives":false;
    }
    $("archive").disabled=state.busy||!items.length||items.some(item=>!canArchive(item));
    $("archive").textContent="Archiver la sélection"+(items.length?" ("+items.length+")":"");
    $("archive").title="Archiver les résultats terminés et exportés. Le filtre À archiver permet de les sélectionner.";
    $("restore").disabled=state.busy||!items.length||items.some(item=>!item.archived_at);
    $("restore").textContent="Restaurer dans Résultats"+(items.length?" ("+items.length+")":"");
    for(const id of ["bulk-preset","bulk-settings","up","down","cancel","retry","remove"])$(id).disabled=state.busy||!items.length;
    $("remove").textContent="Supprimer la sélection"+(items.length?" ("+items.length+")":"");
    $("remove").disabled=state.busy||!items.length||items.some(item=>item.remove_requested);
    $("launch").disabled=state.busy||state.dirty||!items.length||items.some(item=>!item.ready||item.status!=="preparation");
    $("launch").textContent="Lancer la sélection"+(items.length?" ("+items.length+")":"");
    $("launch").title=state.dirty?"Enregistre les modifications en cours.":items.some(item=>!item.ready)?"La sélection contient des éléments à compléter. Utilise le filtre Prêts.":"Ajouter explicitement à la production";
    $("retry").disabled=state.busy||!items.length||items.some(item=>!canRetry(item));
    $("pause").disabled=state.busy;$("refresh").disabled=state.busy;
    monitoring?.previewSelection();
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
  function localizedThanks(item,config,disabled) {
    if((config.preset_origin||config.preset)!=="little_men_experimental")return "";
    const languages={...(state.data.thanks_languages||{auto:"Automatique · pays et ambiance"})};
    if(config.little_men_language==="Hindi")languages.Hindi="Hindi (ancien choix)";
    const selection=item.runtime?.thanks_selection;
    let summary="Pays connu, sinon choix varié selon l’ambiance parmi les 11 langues. Le choix est conservé pour cette fiche.";
    if(selection?.language)summary="Langue retenue : "+(languages[selection.language]||selection.language)+" · "+selection.reason;
    const contexts=config.references.map(ref=>ref.scene_context).filter(context=>context&&(context.intention||context.prompt));
    const provenance=contexts.length?'<details class="vf-source"><summary>Contexte récupéré de l’image</summary>'+contexts.map(context=>
      '<p>'+escape(context.origin)+' · '+escape((context.intention||context.prompt).slice(0,1600))+'</p>').join("")+'</details>':"";
    try {
      const plan=JSON.parse(item.steps.plan.output.text);
      if(Array.isArray(plan.spoken_lines)&&Array.isArray(plan.spoken_languages)&&plan.spoken_lines.length)
        summary="Remerciement prévu : "+plan.spoken_lines.map((line,i)=>(languages[plan.spoken_languages[i]]||plan.spoken_languages[i]||"Langue non précisée")+" · "+line).join(" / ");
    } catch (_) {}
    return '<section data-vf-localized-thanks><h3>Remerciement</h3><label>Langue parlée<select data-vf-field="little_men_language" '+disabled+'>'+Object.entries(languages).map(([key,label])=>'<option value="'+key+'" '+((config.little_men_language||"auto")===key?"selected":"")+">"+escape(label)+"</option>").join("")+'</select></label>'+
      provenance+'<label>Lieu / contexte de la scène<textarea data-vf-field="little_men_context" maxlength="2000" rows="2" '+disabled+'>'+escape(config.little_men_context||"")+'</textarea></label><p class="vf-source">'+escape(summary)+'</p><small class="vf-source">La langue du texte Instagram se règle séparément. Les gestes utiles à une solution durable, puis le résultat et le remerciement.</small></section>';
  }
  function renderInspector() {
    const item=current();if(!item){$("inspector").innerHTML='<p class="vf-empty">Sélectionne une vidéo pour voir ses réglages.</p>';return;}
    state.draft={name:item.name,...clone(item.config)};state.revision=item.revision;
    const config=item.config,disabled=item.status!=="preparation"?"disabled":"";
    $("inspector").innerHTML='<div class="vf-inspector-title"><h2>'+titleMarkup(item)+'</h2><button type="button" data-vf-action="duplicate">Dupliquer</button></div><p class="vf-source">'+escape(item.source.group||({image:"Image Lab",h3:"H3",ref2v:"REF2V",session:"Parcours"}[item.source.kind]||"Source"))+' <button type="button" data-vf-source>Ouvrir la source</button></p>'+
      (item.issues.length?'<p class="vf-errors">'+item.issues.map(escape).join("<br>")+"</p>":"")+
      '<div class="vf-inspector-actions">'+(!item.archived_at&&item.status!=="preparation"&&item.status!=="active"?'<button type="button" data-vf-action="edit">Modifier · remettre en préparation</button>':"")+
      '<button type="button" class="vf-remove" data-vf-action="remove" '+(item.remove_requested?'disabled':"")+'>'+(item.remove_requested?"Suppression en cours…":"Supprimer")+'</button>'+
      (item.archived_at?'<button type="button" data-vf-action="restore">Restaurer dans Résultats</button>':archiveButton(item,'data-vf-action="archive"'))+
      (canRetry(item)?'<button type="button" data-vf-action="retry">Reprendre la chaîne</button>':"")+
      (item.source.kind==="episode"&&item.status==="preparation"?'<button type="button" data-vf-refresh-source>Recharger depuis l’histoire</button>':"")+'</div>'+
      '<section>'+field("Nom","name")+'<label>Preset<select id="vf-item-preset" '+disabled+'>'+Object.entries(state.data.presets).map(([key,label])=>'<option value="'+key+'" '+(key===config.preset?"selected":"")+">"+escape(label)+"</option>").join("")+'</select></label>'+
      (config.preset==="custom"&&config.preset_origin?'<small class="vf-source">Basé sur '+escape(state.data.presets[config.preset_origin])+"</small>":"")+'</section>'+
      '<section><h3>Images et rôles</h3>'+config.references.map((ref,index)=>'<div class="vf-reference">'+imagePreview(ref,ref.label)+'<div><small>'+escape(ref.label||"Image")+'</small><select data-vf-role="'+index+'" '+disabled+' aria-label="Rôle de '+escape(ref.label||"l’image")+'">'+Object.entries(roles).filter(([key])=>config.mode==="ref2v"||["unassigned","first_frame","last_frame",ref.role].includes(key)).map(([key,label])=>'<option value="'+key+'" '+(ref.role===key?"selected":"")+">"+label+"</option>").join("")+'</select></div><button type="button" data-vf-remove-ref="'+index+'" aria-label="Retirer cette image" '+disabled+'>×</button></div>').join("")+
      '<label>Associer une image<input id="vf-add-reference" type="file" accept="image/png,image/jpeg,image/webp" multiple '+disabled+'></label></section>'+
      '<section><div class="vf-fields"><label>Mode<select data-vf-field="mode" '+disabled+'><option value="h3" '+(config.mode==="h3"?"selected":"")+'>H3 / FL2V</option><option value="ref2v" '+(config.mode==="ref2v"?"selected":"")+'>REF2V</option></select></label><label>Nombre de plans<select data-vf-field="shot_count" '+disabled+'><option value="auto">Auto</option>'+[1,2,3,4,5,6].map(n=>'<option '+(config.shot_count===n?"selected":"")+">"+n+"</option>").join("")+'</select></label></div>'+
      '<label>Intention<textarea data-vf-field="intention" rows="5" '+disabled+'>'+escape(config.intention)+'</textarea></label><details><summary>Prompt final déjà préparé</summary><p class="vf-source">Un prompt final renseigné est utilisé directement, sans refaire le plan.</p><textarea data-vf-field="final_prompt" aria-label="Prompt final" rows="6" '+disabled+'>'+escape(config.final_prompt)+'</textarea></details></section>'+
      localizedThanks(item,config,disabled)+
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
    // A discarded line need not save an invalid or unfinished settings draft.
    if(action!=="remove" || !items.some(item=>item.id===state.focus))await saveDraft();
    const fresh=state.data.items.filter(item=>items.some(old=>old.id===item.id));
    const previousIds=new Set(state.data.items.map(item=>item.id));
    accept(await api("/actions/"+action,"POST",selection(fresh)));
    if(action==="archive")showNotice(fresh.length+" résultat"+(fresh.length>1?"s archivés":" archivé"),()=>open(fresh.map(item=>item.id)),"Voir les archives");
    if(action==="restore"){
      state.tab="results";$("filter").value="all";state.selected=new Set(fresh.map(item=>item.id));state.focus=fresh[0]?.id||null;render();
      showNotice("Résultats restaurés, sans relance.");
    }
    if(action==="duplicate"){
      const copies=state.data.items.filter(item=>!previousIds.has(item.id));
      state.tab="preparation";$("filter").value="all";state.selected=new Set(copies.map(item=>item.id));state.focus=copies[0]?.id||null;render();
    }
  }
  async function source(item) {
    const detail=clone(item.source);
    if (detail.kind === "image_transition") return window.PanelForgeImageTransitions?.open(detail.id, detail.transition_id, detail.version);
    if (detail.kind === "image") return window.PanelForgeKrea2AssistedLab?.open(detail.id);
    if (detail.story_v2_id) return window.PanelForgeStoryV2?.open(detail.story_v2_id);
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
      const article=document.createElement("article"),title=document.createElement("strong"),text=document.createElement("p"),copy=document.createElement("button");
      title.textContent="Variante "+((step.output.variants||[]).indexOf(variant)+1)+(variant.angle?" · "+variant.angle:"");
      const content=variant.copy_text||[variant.hook,variant.caption,(variant.emojis||[]).join(" "),(variant.hashtags||[]).join(" ")].filter(Boolean).join("\n\n");
      text.className="vf-social-text";text.textContent=content;copy.type="button";copy.textContent="Copier cette variante";
      copy.onclick=()=>copyText(content,copy);article.append(title,text,copy);body.append(article);
    }
    if(step.output.variants?.length){
      const download=document.createElement("a");download.href="/api/video-factory/items/"+encodeURIComponent(item.id)+"/instagram.txt";
      download.textContent="Télécharger les variantes Instagram (.txt)";download.download="Instagram.txt";body.append(download);
    }
    if(["video","dlss","social"].includes(key))resultFiles(item,body);
    if(!body.children.length){const p=document.createElement("p");p.textContent=step.output.note||step.message||stageLabel(item,key);body.append(p);}
    $("detail-dialog").showModal();
  }
  document.querySelectorAll("[data-vf-tab]").forEach(button=>button.addEventListener("click",()=>busy(async()=>{await saveDraft();state.tab=button.dataset.vfTab;state.selected.clear();state.focus=null;$("filter").value="all";render();})));
  document.querySelector('[data-lab-view="video-factory"]')?.addEventListener("click",()=>refresh());
  $("refresh").onclick=()=>refresh();
  $("filter").onchange=()=>{state.selected.clear();render();};
  $("results-sort").onchange=event=>{state.resultSort=event.target.value==="newest"?"newest":"chronological";render();};
  $("select-all").onchange=event=>{visible().forEach(item=>event.target.checked?state.selected.add(item.id):state.selected.delete(item.id));render();};
  $("rows").addEventListener("change",event=>{
    if(event.target.matches("[data-vf-group]"))visible().filter(item=>group(item)===event.target.dataset.vfGroup).forEach(item=>event.target.checked?state.selected.add(item.id):state.selected.delete(item.id));
    if(event.target.matches("[data-vf-select]")){const id=event.target.closest("[data-vf-id]").dataset.vfId;event.target.checked?state.selected.add(id):state.selected.delete(id);}
    renderToolbar();
  });
  $("rows").addEventListener("click",event=>{
    const tr=event.target.closest("[data-vf-id]");if(!tr)return;
    const item=state.data.items.find(item=>item.id===tr.dataset.vfId);
    const resultButton=event.target.closest("[data-vf-result]");
    if(resultButton)return detail(item,resultButton.dataset.vfResult);
    if(event.target.closest("[data-vf-folder]"))return busy(()=>openFolder(item));
    const preview=event.target.closest("[data-vf-preview]");
    if(preview)return openImage(preview);
    if(event.target.closest("[data-vf-retry]"))return busy(()=>resumeChain([item]));
    if(event.target.closest("[data-vf-delete]"))return busy(()=>itemAction("remove",[item]));
    if(event.target.closest("[data-vf-archive]"))return busy(()=>itemAction("archive",[item]));
    if(event.target.closest("[data-vf-restore]"))return busy(()=>itemAction("restore",[item]));
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
    if(button.dataset.vfPreview)return openImage(button);
    if(button.dataset.vfAction)busy(()=>button.dataset.vfAction==="retry"?resumeChain([current()]):itemAction(button.dataset.vfAction,[current()]));
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
  $("archive").onclick=()=>busy(()=>itemAction("archive"));
  $("restore").onclick=()=>busy(()=>itemAction("restore"));
  $("remove").onclick=()=>busy(()=>itemAction("remove"));
  $("cancel").onclick=()=>busy(()=>itemAction("cancel"));
  $("retry").onclick=()=>busy(()=>resumeChain(selected()));
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
  $("image-dialog").addEventListener("click",event=>{if(event.target===$("image-dialog"))$("image-dialog").close();});
  $("image-dialog").addEventListener("close",()=>$("image-content").removeAttribute("src"));
  setInterval(updateDurations,1000);
  setInterval(()=>refresh(),5000);
  refresh();
})();
