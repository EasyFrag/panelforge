(() => {
  "use strict";
  const root = document.getElementById("image-transitions-workspace");
  const core = window.PanelForgeLabCore;
  if (!root || !core) return;
  const $ = id => document.getElementById("it-" + id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const asset = id => "/api/assets/" + encodeURIComponent(id) + "/content";
  const state = {p:null, spec:null, projects:[], models:[], selected:new Set(), focus:null,
    busy:false, loading:null, drafts:{}, settings:{}, name:null, replace:null, library:[], librarySerial:0};
  const labels = {empty:"À préparer",review:"À relire",ready:"Prête",sent:"Envoyée"};
  const factoryStates = {preparation:"Préparation",queued:"En attente",active:"En cours",
    succeeded:"Terminée",failed:"Erreur",cancelled:"Annulée"};
  const api = (path, method="GET", body) => core.request("/api/image-transitions" + path,
    {method,...(body===undefined ? {} : {headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  const dirty = () => state.name !== null || Object.keys(state.settings).length || Object.keys(state.drafts).length;
  const job = () => state.p?.jobs.find(j => ["queued","running"].includes(j.status));
  const transitions = () => state.p?.transitions || [];
  const selected = () => transitions().filter(t => state.selected.has(t.id));
  const current = () => transitions().find(t => t.id === state.focus);
  const endpoint = suffix => "/projects/" + encodeURIComponent(state.p.id) + suffix;
  const withVersion = body => ({version:state.p.version,...body});
  function message(text, ids) {
    $("message").textContent = text;
    if (ids?.length) {
      const button = document.createElement("button");
      button.type="button"; button.textContent="Voir dans l’usine";
      button.onclick=() => window.PanelForgeVideoFactory?.open(ids);
      $("message").append(" ",button);
    }
  }
  function accept(project, selectNew=false) {
    const previous = new Set(transitions().map(t=>t.id));
    state.p = project;
    const available = new Set(transitions().map(t=>t.id));
    state.selected = new Set([...state.selected].filter(id=>available.has(id)));
    if(selectNew) transitions().filter(t=>!previous.has(t.id)).forEach(t=>state.selected.add(t.id));
    if(!available.has(state.focus)) state.focus=transitions()[0]?.id || null;
    try { sessionStorage.setItem("panelforge.transitions.project",project.id); } catch (_) {}
  }
  function controls() {
    const blocked = state.busy || !!job(), has=!!state.p;
    $("editor").disabled=!has;
    $("editor").querySelectorAll("input,select,textarea,button").forEach(control=>{
      if(control.matches("[data-it-zoom]")) {control.disabled=false;return;}
      let edge=false;
      if(control.dataset.itMove) {
        const id=control.closest("[data-it-frame]").dataset.itFrame;
        const target=(state.p?.frames.findIndex(f=>f.id===id) ?? -1)+Number(control.dataset.itMove);
        edge=target<0 || target>=(state.p?.frames.length || 0);
      }
      control.disabled=blocked || edge;
    });
    for(const id of ["upload","library"]) $(id).disabled=blocked || !has;
    for(const id of ["new","projects","refresh"]) $(id).disabled=state.busy;
    for(const id of ["propose","review","send"]) $(id).disabled=blocked || !selected().length;
    $("save").disabled=blocked || !dirty();
    $("all").disabled=blocked || !transitions().length;
    $("all").checked=transitions().length>0 && selected().length===transitions().length;
    $("all").indeterminate=selected().length>0 && selected().length<transitions().length;
    $("count").textContent=selected().length + " sélectionnée" + (selected().length>1?"s":"");
    $("dirty").textContent=dirty()?" · modifications à enregistrer":"";
    const running=job();
    $("progress").textContent=running ? "Analyse · " + running.completed + "/" + running.total :
      state.busy?"Enregistrement…":"";
  }
  async function saveDraft() {
    if(!state.p || !dirty()) return;
    const changes={};
    if(state.name!==null) changes.name=state.name;
    if(Object.keys(state.settings).length) changes.settings={...state.settings};
    if(Object.keys(changes).length) {
      accept((await api(endpoint(""),"PATCH",withVersion({changes}))).project);
      state.name=null; state.settings={};
    }
    for(const [id, changes] of Object.entries(state.drafts)) {
      accept((await api(endpoint("/transitions/"+encodeURIComponent(id)),"PATCH",withVersion({changes}))).project);
      delete state.drafts[id];
    }
  }
  async function run(action, save=true) {
    if(state.busy) return;
    state.busy=true; controls();
    try { if(save) await saveDraft(); await action(); }
    catch(error) { message(error.message); if($("library-dialog").open)$("library-message").textContent=error.message; }
    finally { state.busy=false; paint(); }
  }
  function options(select, values, chosen) {
    select.innerHTML=values.map(v=>'<option value="'+esc(v.id)+'">'+esc(v.label)+'</option>').join("");
    if(chosen && !values.some(v=>v.id===chosen)) {
      const option=document.createElement("option"); option.value=chosen; option.textContent=chosen+" · hors catalogue";
      select.append(option);
    }
    select.value=chosen || "";
  }
  function paintSettings() {
    if(!state.p || !state.spec) return;
    $("name").value=state.name ?? state.p.name;
    root.querySelectorAll("[data-it-setting]").forEach(input=>{
      const key=input.dataset.itSetting, value=state.settings[key] ?? state.p.settings[key];
      if(key.endsWith("model_id")) options(input,state.models.map(m=>({id:m.id,label:(m.source==="local"?"Local · ":"Serveur · ")+m.label})),value);
      else if(key==="aspect_ratio") options(input,[{id:"auto",label:"Selon la première image"},...state.spec.aspect_ratios.map(id=>({id,label:id}))],value);
      else if(input.type==="checkbox") input.checked=value;
      else input.value=value;
    });
  }
  function imageButton(frame, caption, focus=false) {
    const name=frame.label || caption || "Image";
    const reference=' data-it-zoom="'+esc(frame.asset_id)+'" data-it-title="'+esc(name)+'"';
    const icon='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6M10 7v6"/></svg>';
    return '<span class="it-thumb" data-it-thumbnail>'+
      '<button type="button" class="it-image-open" '+(focus?'data-it-focus aria-label="Voir la transition"':reference+' aria-label="Agrandir '+esc(name)+'"')+'>'+
      '<img src="'+asset(frame.asset_id)+'" alt="'+esc(name)+'" draggable="false">'+
      (caption?'<span class="it-image-caption">'+esc(caption)+'</span>':"")+'</button>'+
      '<button type="button" class="it-zoom"'+reference+' aria-label="Agrandir '+esc(name)+'" title="Agrandir l’image">'+icon+'</button></span>';
  }
  function paintFrames() {
    hidePreview();
    $("frieze").innerHTML=(state.p?.frames||[]).map((f,i)=>
      '<article class="it-frame" draggable="'+(!job()&&!state.busy)+'" data-it-frame="'+esc(f.id)+'">'+
      imageButton(f,"")+'<small title="'+esc(f.label)+'">'+(i+1)+'. '+esc(f.label)+'</small>'+
      '<div class="it-frame-actions"><button type="button" data-it-move="-1" title="Déplacer à gauche" '+(i===0?'disabled':'')+'>←</button>'+
      '<button type="button" data-it-move="1" title="Déplacer à droite" '+(i===state.p.frames.length-1?'disabled':'')+'>→</button>'+
      '<button type="button" data-it-replace title="Remplacer cette image">↻</button>'+
      '<button type="button" data-it-remove title="Retirer de la frise">×</button></div></article>').join("");
  }
  function paintRows() {
    hidePreview();
    const frames=new Map((state.p?.frames||[]).map(f=>[f.id,f]));
    $("rows").innerHTML=transitions().map((t,i)=>{
      const draft=state.drafts[t.id]||{}, first=frames.get(t.left), last=frames.get(t.right);
      return '<tr class="'+(state.focus===t.id?"active":"")+'" data-it-row="'+esc(t.id)+'">'+
        '<td><input type="checkbox" data-it-select '+(state.selected.has(t.id)?"checked":"")+' aria-label="Sélectionner la transition '+(i+1)+'"></td>'+
        '<td><div class="it-pair">'+imageButton(first,"",true)+
        '<button type="button" data-it-focus aria-label="Voir la transition '+(i+1)+' vers '+(i+2)+'">'+(i+1)+' → '+(i+2)+'</button>'+
        imageButton(last,"",true)+'</div></td>'+
        '<td><input data-it-action maxlength="240" aria-label="Action '+(i+1)+'" value="'+esc(draft.action??t.action)+'" placeholder="Indiquer une action ou laisser proposer"></td>'+
        '<td>'+esc(t.effective.duration)+' s</td><td><span class="it-state '+t.state+'">'+labels[t.state]+'</span></td></tr>';
    }).join("");
    $("empty").hidden=transitions().length>0;
  }
  function paintInspector() {
    hidePreview();
    const original=current();
    if(!original) { $("inspector").innerHTML='<p class="vf-empty">Sélectionne une paire pour comparer les images et relire l’intention.</p>'; return; }
    const t={...original,...(state.drafts[original.id]||{})}, index=transitions().indexOf(original);
    const first=state.p.frames.find(f=>f.id===t.left), last=state.p.frames.find(f=>f.id===t.right);
    $("inspector").innerHTML='<h2>Transition '+(index+1)+' → '+(index+2)+'</h2>'+
      '<div class="it-comparison">'+imageButton(first,"Départ")+imageButton(last,"Arrivée")+'</div>'+
      '<label>Ton indication<textarea data-it-field="note" rows="2" maxlength="4000" placeholder="Par exemple : travail à la tronçonneuse">'+esc(t.note)+'</textarea></label>'+
      '<label>Intention à relire<textarea data-it-field="intention" rows="8" maxlength="14000" placeholder="Le LLM proposera une intention ; tu peux aussi la rédiger ici.">'+esc(t.intention)+'</textarea></label>'+
      '<div class="it-detail-grid"><label>Type<select data-it-field="kind">'+Object.entries(state.spec.kinds).map(([id,label])=>'<option value="'+id+'" '+(t.kind===id?"selected":"")+'>'+esc(label)+'</option>').join("")+'</select></label>'+
      '<label>Durée spécifique (s)<input data-it-field="duration" type="number" min="5" max="15" step="0.5" placeholder="'+esc(t.effective.duration)+'" value="'+esc(t.duration??"")+'"></label></div>'+
      '<label>Caméra spécifique<textarea data-it-field="camera" rows="2" maxlength="2000" placeholder="Utiliser le réglage commun">'+esc(t.camera)+'</textarea></label>'+
      '<label>Rythme spécifique<textarea data-it-field="pace" rows="2" maxlength="2000" placeholder="Utiliser le réglage commun">'+esc(t.pace)+'</textarea></label>'+
      (t.stale?'<p class="it-evidence">Cette transition a changé depuis la proposition. Relis l’intention avant de la valider.</p>':"")+
      (t.observations?'<details><summary>Différences observées</summary><p class="it-evidence">'+esc(t.observations)+'</p></details>':"")+
      (t.uncertainties?'<p class="it-evidence">'+esc(t.uncertainties)+'</p>':"")+
      (t.suggestion?'<div class="it-suggestion"><b>Nouvelle proposition</b><p>'+esc(t.suggestion.value.intention)+'</p><button type="button" data-it-apply>Remplacer par cette proposition</button></div>':"")+
      '<div class="it-links"><button type="button" data-it-review-one>Valider cette transition</button>'+
      t.factory_ids.map(id=>{const item=state.p.factory_items.find(v=>v.id===id);return '<button type="button" data-it-factory-id="'+esc(id)+'">'+esc(item?(item.archived?"Archivée":factoryStates[item.status]||item.status):"Unité indisponible")+'</button>';}).join("")+'</div>';
  }
  function paint() {
    options($("projects"),[{id:"",label:"Choisir une frise"},...state.projects.map(p=>({id:p.id,label:p.name+" · "+p.image_count+" images"}))],state.p?.id);
    paintSettings(); paintFrames(); paintRows(); paintInspector(); controls();
  }
  async function updateProjects() { state.projects=(await api("/projects")).projects; }
  async function open(identity, transitionId, expectedVersion) {
    await initialize();
    await run(async()=>{
      const project=(await api("/projects/"+encodeURIComponent(identity))).project;
      state.selected=new Set(); state.focus=transitionId||null; accept(project,true);
      const target=transitions().find(t=>t.id===transitionId);
      if(transitionId&&!target)state.focus=null;
      window.PanelForgeLabNavigation?.switchView("image-transitions");
      message(transitionId&&!target ? "Cette transition ne fait plus partie de la frise. Sa version reste dans l’usine." :
        expectedVersion&&target?.context_key!==expectedVersion ? "La frise a évolué depuis cet envoi. La version envoyée reste conservée dans l’usine." : "");
    });
  }
  async function initialize() {
    if(state.spec) return;
    if(state.loading) return state.loading;
    state.busy=true; controls();
    state.loading=(async()=>{
      const [spec,list]=await Promise.all([api("/spec"),api("/projects")]);
      state.spec=spec; state.projects=list.projects;
      let previous=null; try { previous=sessionStorage.getItem("panelforge.transitions.project"); } catch (_) {}
      if(previous && !state.projects.some(p=>p.id===previous)) previous=null;
      const id=previous||state.projects[0]?.id;
      if(id) accept((await api("/projects/"+encodeURIComponent(id))).project,true);
      const lastJob=state.p?.jobs[state.p.jobs.length-1];
      if(lastJob?.status==="failed"&&lastJob.error)message(lastJob.error);
      paint();
      api("/models").then(data=>{state.models=data.models;if(!dirty()&&!state.busy)paintSettings();})
        .catch(error=>message("Catalogue LLM indisponible : "+error.message));
    })();
    try { await state.loading; } finally { state.loading=null; state.busy=false; if(state.spec)paint();else controls(); }
  }
  async function setOrder(ids) { accept((await api(endpoint("/order"),"PUT",withVersion({ids}))).project,true); }
  function showImage(assetId,title) {
    hidePreview();
    $("image-title").textContent=title||"Image";
    $("image-content").src=asset(assetId);$("image-content").alt=title||"Image";
    if(!$("image-dialog").open)$("image-dialog").showModal();
  }
  function chooseFiles(replace=null) { state.replace=replace;$("files").multiple=!replace;$("files").value="";$("files").click(); }
  async function libraryImages(serial) {
    hidePreview();
    const engine=$("library-engine").value, id=$("library-project").value;
    state.library=[]; $("library-images").replaceChildren(); $("library-add").disabled=true;
    if(!id) { $("library-message").textContent="Aucun projet dans cet atelier.";return; }
    const result=await api("/library/"+engine+"/"+encodeURIComponent(id));
    if(serial!==state.librarySerial)return;
    state.library=result.images;
    $("library-images").innerHTML=result.images.map(image=>
      '<div class="it-library-card">'+imageButton(image,"")+
      '<label><input type="checkbox" value="'+esc(image.key)+'"><span>'+esc(image.label)+(image.accepted?" · validée":"")+'</span></label></div>').join("");
    $("library-message").textContent=result.images.length?"Choisis les versions à reprendre, dans l’ordre affiché.":"Aucune image terminée.";
    $("library-add").disabled=!result.images.length;
  }
  async function loadLibrary(reloadProjects=true) {
    const serial=++state.librarySerial;
    state.library=[]; $("library-images").replaceChildren();
    $("library-message").textContent="Chargement…"; $("library-add").disabled=true; $("library-chain").disabled=true;
    try {
      if(reloadProjects) {
        const result=await api("/library/"+$("library-engine").value);
        if(serial!==state.librarySerial)return;
        options($("library-project"),result.projects.map(p=>({id:p.id,label:p.name})),result.projects[0]?.id);
      }
      await libraryImages(serial);
    } catch(error) { if(serial===state.librarySerial)$("library-message").textContent=error.message; }
    finally { if(serial===state.librarySerial)$("library-chain").disabled=!state.library.length || !!state.replace; }
  }
  async function openLibrary(replace=null) {
    state.replace=replace;
    $("library-title").textContent=replace?"Remplacer une image":"Choisir des versions d’images";
    $("library-add").textContent=replace?"Remplacer l’image":"Ajouter la sélection";
    $("library-dialog").showModal();
    await loadLibrary();
  }
  $("new").onclick=()=>run(async()=>{
    accept((await api("/projects","POST",{name:"Nouvelle frise"})).project);
    state.selected.clear(); await updateProjects(); message("Ajoute les images dans l’ordre de la progression.");
  });
  $("projects").onchange=()=>{const id=$("projects").value;if(id)open(id);};
  $("save").onclick=()=>run(async()=>{await updateProjects();message("Modifications enregistrées.");});
  $("refresh").onclick=()=>{
    if(dirty() && !window.confirm("Recharger la frise et abandonner les champs non enregistrés ?"))return;
    run(async()=>{
      state.drafts={};state.settings={};state.name=null;
      await updateProjects();
      if(state.p)accept((await api(endpoint(""))).project);
      message("");
    },false);
  };
  $("upload").onclick=()=>chooseFiles();
  $("library").onclick=()=>run(()=>openLibrary());
  $("factory").onclick=()=>run(()=>window.PanelForgeVideoFactory?.open());
  $("files").onchange=()=>{
    const files=[...$("files").files],replace=state.replace;
    run(async()=>{
      for(const file of files) {
        const form=new FormData();form.set("image",file);form.set("version",String(state.p.version));
        if(replace)form.set("replace_id",replace);
        accept((await core.request("/api/image-transitions"+endpoint("/frames/upload"),{method:"POST",body:form})).project,true);
      }
      await updateProjects(); message(files.length+" image(s) importée(s).");
    });
  };
  $("all").onchange=()=>{state.selected=new Set($("all").checked?transitions().map(t=>t.id):[]);paintRows();controls();};
  $("name").oninput=()=>{state.name=$("name").value;controls();};
  root.querySelectorAll("[data-it-setting]").forEach(input=>input.addEventListener("input",()=>{
    state.settings[input.dataset.itSetting]=input.type==="checkbox"?input.checked:input.type==="number"?Number(input.value):input.value;controls();
  }));
  $("rows").addEventListener("change",event=>{
    const row=event.target.closest("[data-it-row]"); if(!row)return;
    if(event.target.matches("[data-it-select]")) {
      if(event.target.checked)state.selected.add(row.dataset.itRow);else state.selected.delete(row.dataset.itRow);
      controls();
    }
  });
  $("rows").addEventListener("input",event=>{
    if(!event.target.matches("[data-it-action]"))return;
    const id=event.target.closest("[data-it-row]").dataset.itRow;
    state.drafts[id]={...(state.drafts[id]||{}),action:event.target.value};controls();
  });
  $("rows").addEventListener("click",event=>{
    if(event.target.closest("[data-it-focus]")) {
      const id=event.target.closest("[data-it-row]").dataset.itRow;
      run(async()=>{state.focus=id;});
    }
  });
  $("inspector").addEventListener("input",event=>{
    const field=event.target.dataset.itField; if(!field)return;
    const value=field==="duration"?(event.target.value===""?null:Number(event.target.value)):event.target.value;
    state.drafts[state.focus]={...(state.drafts[state.focus]||{}),[field]:value};controls();
  });
  $("inspector").addEventListener("click",event=>{
    const factory=event.target.closest("[data-it-factory-id]");
    if(factory)run(()=>window.PanelForgeVideoFactory?.open([factory.dataset.itFactoryId]));
    if(event.target.closest("[data-it-review-one]"))run(async()=>accept((await api(endpoint("/review"),"POST",withVersion({ids:[state.focus]}))).project));
    if(event.target.closest("[data-it-apply]"))run(async()=>accept((await api(endpoint("/transitions/"+state.focus+"/suggestion"),"POST",withVersion({}))).project));
  });
  $("propose").onclick=()=>run(async()=>{
    const requestId=window.crypto?.randomUUID?.()||("request-"+Date.now()+"-"+Math.random().toString(16).slice(2));
    accept((await api(endpoint("/proposals"),"POST",withVersion({ids:selected().map(t=>t.id),request_id:requestId}))).project);
    message("Analyse en cours. Les propositions seront à relire ; tes intentions corrigées seront conservées.");
  });
  $("review").onclick=()=>run(async()=>{
    accept((await api(endpoint("/review"),"POST",withVersion({ids:selected().map(t=>t.id)}))).project);
    message("Sélection validée pour l’envoi.");
  });
  $("send").onclick=()=>run(async()=>{
    const result=await api(endpoint("/send"),"POST",withVersion({ids:selected().map(t=>t.id)}));
    accept(result.project);message(result.added?result.added+" unité(s) ajoutée(s) à la préparation de l’usine.":"Ces versions sont déjà dans l’usine.",result.ids);
  });
  for(const host of [root,$("library-dialog")]) host.addEventListener("click",event=>{
    const zoom=event.target.closest("[data-it-zoom]");
    if(zoom)showImage(zoom.dataset.itZoom,zoom.dataset.itTitle);
  });
  $("frieze").addEventListener("click",event=>{
    const frame=event.target.closest("[data-it-frame]");if(!frame)return;
    const id=frame.dataset.itFrame,index=state.p.frames.findIndex(f=>f.id===id);
    if(event.target.closest("[data-it-replace]"))return run(()=>openLibrary(id));
    if(event.target.closest("[data-it-remove]"))return run(()=>setOrder(state.p.frames.filter(f=>f.id!==id).map(f=>f.id)));
    const move=event.target.closest("[data-it-move]");
    if(move)run(async()=>{const ids=state.p.frames.map(f=>f.id),target=index+Number(move.dataset.itMove);if(target<0||target>=ids.length)return;[ids[index],ids[target]]=[ids[target],ids[index]];await setOrder(ids);});
  });
  let dragged=null;
  $("frieze").addEventListener("dragstart",event=>{
    if(job()||state.busy){event.preventDefault();return;}
    dragged=event.target.closest("[data-it-frame]")?.dataset.itFrame;
    if(dragged){hidePreview();event.dataTransfer.setData("text/plain",dragged);event.dataTransfer.effectAllowed="move";}
  });
  $("frieze").addEventListener("dragover",event=>{if(dragged)event.preventDefault();});
  $("frieze").addEventListener("drop",event=>{
    event.preventDefault();const target=event.target.closest("[data-it-frame]")?.dataset.itFrame,source=dragged;dragged=null;
    if(!target||!source||target===source)return;
    run(async()=>{const ids=state.p.frames.map(f=>f.id).filter(id=>id!==source);ids.splice(ids.indexOf(target),0,source);await setOrder(ids);});
  });
  $("frieze").addEventListener("dragend",()=>{dragged=null;});
  $("library-engine").onchange=()=>loadLibrary();
  $("library-project").onchange=()=>loadLibrary(false);
  $("library-chain").onclick=()=>{
    const chosen=new Set(state.library.filter(i=>i.accepted).map(i=>i.key));
    $("library-images").querySelectorAll("input").forEach(i=>{i.checked=chosen.has(i.value);});
  };
  $("library-images").addEventListener("change",event=>{
    if(state.replace && event.target.checked)$("library-images").querySelectorAll("input").forEach(i=>{if(i!==event.target)i.checked=false;});
  });
  $("library-add").onclick=()=>{
    const keys=[...$("library-images").querySelectorAll("input:checked")].map(i=>i.value);
    if(!keys.length){$("library-message").textContent="Sélectionne au moins une image.";return;}
    run(async()=>{
      accept((await api(endpoint("/frames/import"),"POST",withVersion({
        engine:$("library-engine").value,project_id:$("library-project").value,keys,replace_id:state.replace}))).project,true);
      $("library-dialog").close();await updateProjects();message("Versions importées. Tu peux ajuster leur ordre dans la frise.");
    });
  };
  const fileButton=document.createElement("button");
  fileButton.type="button";fileButton.textContent="Choisir un fichier…";
  fileButton.onclick=()=>{$("library-dialog").close();chooseFiles(state.replace);};
  $("library-dialog").querySelector(".it-library-controls").append(fileButton);
  document.querySelectorAll("[data-it-close]").forEach(button=>button.onclick=()=>button.closest("dialog").close());
  window.addEventListener("beforeunload",event=>{if(dirty()){event.preventDefault();event.returnValue="";}});
  new MutationObserver(()=>{hidePreview();if(!root.hidden)initialize().catch(error=>message(error.message));}).observe(root,{attributes:true,attributeFilter:["hidden"]});
  // A single floating preview serves every thumbnail, including the modal picker.
  const preview=$("image-preview"), previewImage=$("preview-content");
  let previewTimer=null, previewAnchor=null;
  function hidePreview() {
    clearTimeout(previewTimer);previewTimer=null;previewAnchor=null;
    if(typeof preview.hidePopover==="function" && preview.matches(":popover-open"))preview.hidePopover();
    preview.hidden=true;
  }
  function placePreview(thumb) {
    if(previewAnchor!==thumb || !thumb.isConnected || root.hidden || $("image-dialog").open)return hidePreview();
    const source=thumb.querySelector("img");
    if(!source?.complete || !source.naturalWidth)return;
    const rect=source.getBoundingClientRect(), margin=12, chromeWidth=14, chromeHeight=36;
    if(rect.width<=0 || rect.height<=0)return hidePreview();
    // Scale the visible image, excluding object-fit letterboxing.
    const fit=Math.min(rect.width/source.naturalWidth,rect.height/source.naturalHeight);
    let width=source.naturalWidth*fit*3, height=source.naturalHeight*fit*3;
    const viewportWidth=document.documentElement.clientWidth, viewportHeight=window.innerHeight;
    const scale=Math.min(1,(viewportWidth-margin*2-chromeWidth)/width,(viewportHeight-margin*2-chromeHeight)/height);
    if(!Number.isFinite(scale)||scale<=0)return hidePreview();
    width=Math.floor(width*scale);height=Math.floor(height*scale);
    const host=thumb.closest("dialog") || document.body;
    if(preview.parentNode!==host)host.append(preview);
    previewImage.src=source.currentSrc||source.src;previewImage.alt=source.alt;
    $("preview-caption").textContent=source.alt;
    preview.style.width=width+"px";previewImage.style.height=height+"px";
    preview.hidden=false;
    if(typeof preview.showPopover==="function" && !preview.matches(":popover-open"))preview.showPopover();
    const box=preview.getBoundingClientRect();
    let left=rect.right+margin;
    if(left+box.width>viewportWidth-margin)left=rect.left-box.width-margin;
    preview.style.left=Math.max(margin,Math.min(left,viewportWidth-box.width-margin))+"px";
    preview.style.top=Math.max(margin,Math.min(rect.top,viewportHeight-box.height-margin))+"px";
  }
  function schedulePreview(thumb) {
    if(previewAnchor===thumb)return;
    hidePreview();previewAnchor=thumb;
    previewTimer=setTimeout(()=>placePreview(thumb),160);
    const source=thumb.querySelector("img");
    if(source && !source.complete)source.addEventListener("load",()=>{
      if(previewAnchor===thumb)placePreview(thumb);
    },{once:true});
  }
  for(const host of [root,$("library-dialog")]) {
    host.addEventListener("pointerover",event=>{
      if(event.pointerType==="touch")return;
      const thumb=event.target.closest("[data-it-thumbnail]");
      if(thumb && !thumb.contains(event.relatedTarget))schedulePreview(thumb);
    });
    host.addEventListener("pointerout",event=>{
      const thumb=event.target.closest("[data-it-thumbnail]");
      if(thumb && !thumb.contains(event.relatedTarget))hidePreview();
    });
    host.addEventListener("focusin",event=>{
      const thumb=event.target.closest("[data-it-thumbnail]");
      if(thumb)schedulePreview(thumb);
    });
    host.addEventListener("focusout",event=>{
      const thumb=event.target.closest("[data-it-thumbnail]");
      if(thumb && !thumb.contains(event.relatedTarget))hidePreview();
    });
  }
  document.addEventListener("scroll",hidePreview,true);
  document.addEventListener("keydown",event=>{if(event.key==="Escape")hidePreview();});
  window.addEventListener("resize",hidePreview);
  window.addEventListener("blur",hidePreview);
  $("library-dialog").addEventListener("close",hidePreview);
  $("library-dialog").addEventListener("cancel",hidePreview);
  let polling=false;
  setInterval(async()=>{
    if(root.hidden||state.busy||dirty()||!state.p||polling)return;
    polling=true;
    const identity=state.p.id;
    try {
      const project=(await api("/projects/"+encodeURIComponent(identity))).project;
      if(state.p?.id!==identity||state.busy||dirty()||project.version<state.p.version)return;
      const wasRunning=!!job();
      if(project.version!==state.p.version) {accept(project);paint();}
      else if(JSON.stringify(state.p.factory_items)!==JSON.stringify(project.factory_items)) {state.p.factory_items=project.factory_items;paintInspector();controls();}
      if(wasRunning&&!job()) {
        const last=state.p.jobs[state.p.jobs.length-1];
        message(last?.error||"Propositions prêtes à relire.");
      }
    } catch(error) { message(error.message); } finally {polling=false;}
  },2500);
  window.PanelForgeImageTransitions=Object.freeze({open});
  if(!root.hidden)initialize().catch(error=>message(error.message));
})();
