(() => {
  "use strict";
  const root = document.getElementById("recipes-workspace");
  if (!root) return;
  const $ = id => document.getElementById(`rc-${id}`);
  const api = "/api/recipes";
  const asset = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const uid = () => crypto.randomUUID().replaceAll("-", "");
  const fields = ["intention", "target_duration", "aspect_ratio", "world", "cook", "camera", "audio", "model_id", "edit_model_id", "plan_model_id", "writer_model_id", "style_preset_id"];
  const shotFields = ["id", "title", "action", "framing", "opening", "ending", "duration", "mode", "purpose", "scene", "mode_reason", "image_engine"];
  const names = {queued:"En file", working:"Préparation", waiting:"Rendu en cours", active:"En cours", preparation:"En préparation dans l’Usine", succeeded:"Terminé", failed:"Échec", cancelled:"Abandonné", paused:"En pause"};
  const state = {project:null, defaults:null, shots:[], tab:"universe", dirty:false, busy:false,
    selection:new Set(), notes:new Map(), timer:null, initialized:false, initializing:null, newCommand:uid(), load:0, recoveryDraft:null};

  function element(tag, text, className) {
    const e=document.createElement(tag); if(text!==undefined)e.textContent=text;
    if(className)e.className=className; return e;
  }
  function button(text, fn, disabled=false) {
    const b=element("button",text); b.type="button"; b.disabled=disabled;
    b.addEventListener("click",()=>act(fn)); return b;
  }
  function message(text="", error=false) { $("message").textContent=text; $("message").classList.toggle("rc-error",error); }
  async function request(path, body, method="POST") {
    const response=await fetch(path, body===undefined?{}:{method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!response.ok){const data=await response.json().catch(()=>({})); throw new Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail||`Erreur ${response.status}`));}
    return response.json();
  }
  async function act(fn) {
    if(state.busy)return;
    state.busy=true;controls();message();
    try{await fn();}catch(error){message(error.message,true);}
    finally{state.busy=false;controls();schedule();}
  }
  function cleanShots(){return state.shots.map(s=>Object.fromEntries(shotFields.map(k=>[k,s[k]])));}
  function settings(){return Object.fromEntries(fields.map(k=>[k,k==="target_duration"?Number($(k).value):k==="style_preset_id"?($(k).value||null):$(k).value]));}
  function fillSettings(value){for(const k of fields){if(k==="style_preset_id"&&value[k]&&![...$(k).options].some(o=>o.value===value[k]))$(k).add(new Option("Preset enregistré · indisponible",value[k]));$(k).value=value[k]??"";}}
  function changed(){state.dirty=true;controls();}
  function show(tab){hideImageHover();state.tab=tab;root.querySelectorAll("[data-rc-panel]").forEach(p=>p.hidden=p.dataset.rcPanel!==tab);root.querySelectorAll("[data-rc-tab]").forEach(b=>b.classList.toggle("active",b.dataset.rcTab===tab));controls();}
  function apply(p, reset=false){
    state.project=p;state.shots=p.shots.map(s=>({...s}));state.dirty=false;
    $("name").value=p.name;fillSettings(p.settings);
    const ids=new Set(p.shots.map(s=>s.id));
    if(reset)state.selection=new Set(ids);else state.selection=new Set([...state.selection].filter(id=>ids.has(id)));
    try{localStorage.setItem("panelforge.recipes.current",p.id);}catch(_){}
    draw();schedule();
  }
  async function catalog(){const data=await request(`${api}/projects`);$("projects").replaceChildren(new Option("Choisir une recette", ""),...data.projects.map(p=>new Option(p.name,p.id)));$("projects").value=state.project?.id||"";}
  async function load(id){const token=++state.load;const data=await request(`${api}/projects/${encodeURIComponent(id)}`);if(token!==state.load)return;state.notes.clear();apply(data.project,true);$("projects").value=id;}
  async function ensure(){
    if(state.project)return;
    const name=$("name").value.trim()||"Nouvelle recette", chosenSettings=settings();
    const key=JSON.stringify({name,settings:chosenSettings});
    try{const previous=JSON.parse(sessionStorage.getItem("panelforge.recipes.create")||"null");if(previous?.key===key)state.newCommand=previous.command;else{state.newCommand=uid();sessionStorage.setItem("panelforge.recipes.create",JSON.stringify({key,command:state.newCommand}));}}catch(_){}
    const data=await request(`${api}/projects`,{command:state.newCommand,name,settings:chosenSettings});
    try{sessionStorage.removeItem("panelforge.recipes.create");}catch(_){}
    apply(data.project,true);await catalog();
  }
  async function save(){
    if(!$("form").reportValidity()){show("universe");throw new Error("Complète les réglages du projet.");}
    const initialShots=!state.project?cleanShots():[];
    await ensure();if(initialShots.length){state.shots=initialShots;state.dirty=true;}if(!state.dirty)return;
    const data=await request(`${api}/projects/${state.project.id}`,{version:state.project.version,name:$("name").value.trim(),settings:settings(),shots:state.shots.length?cleanShots():null},"PUT");
    apply(data.project);await catalog();
  }
  function pendingCommand(kind, ids, feedback, imagePart="all", imageEngine=null){
    const key=JSON.stringify({id:state.project.id,kind,ids,feedback,...(imagePart!=="all"?{image_part:imagePart}:{}),...(imageEngine?{image_engine:imageEngine}:{})});
    try{const p=JSON.parse(sessionStorage.getItem("panelforge.recipes.command")||"null");if(p?.key===key)return p.command;const command=uid();sessionStorage.setItem("panelforge.recipes.command",JSON.stringify({key,command}));return command;}catch(_){return uid();}
  }
  async function enqueue(kind, ids=[], feedback="", imagePart="all", imageEngine=null){
    if(kind==="image"&&state.shots.some(s=>ids.includes(s.id)&&(imageEngine||s.image_engine)==="krea2")&&!$("style_preset_id").value){
      show("universe");setTimeout(()=>$("style_preset_id").focus(),0);throw new Error("Choisis le preset KREA2 dans Univers, puis relance la génération des plans.");
    }
    await save();
    if(kind==="image"&&!imageEngine&&!state.project.approved_current){
      const data=await request(`${api}/projects/${state.project.id}/approve`,{version:state.project.version});apply(data.project);
    }
    const data=await request(`${api}/projects/${state.project.id}/generate/${kind}`,{version:state.project.version,command:pendingCommand(kind,ids,feedback,imagePart,imageEngine),ids,feedback,image_part:imagePart,...(imageEngine?{image_engine:imageEngine}:{})});
    try{sessionStorage.removeItem("panelforge.recipes.command");}catch(_){}
    apply(data.project);show(kind==="plan"?"breakdown":kind==="image"?"images":"universe");
    message(imagePart==="end"?"Correction de l’arrivée enregistrée. L’image de départ est conservée.":imageEngine==="krea2"?"Plans validés en animation à une image. Génération KREA2 + Flux Klein enregistrée avec le preset d’Univers.":"Préparation enregistrée. Les résultats apparaîtront ici.");
  }
  async function reviewImages(ids, approved=true){
    await save();
    const data=await request(`${api}/projects/${state.project.id}/review-images`,{version:state.project.version,ids,approved});
    apply(data.project);message(approved?"Revue des images enregistrée. Ces plans peuvent être envoyés à l’Usine.":"Validation retirée. Revois les images avant un nouvel envoi.");
  }
  async function sendToFactory(ids, feedback=""){
    await save();
    if(!state.project.approved_current){
      const data=await request(`${api}/projects/${state.project.id}/approve`,{version:state.project.version});apply(data.project);
    }
    let data;
    const feedbacks=Object.fromEntries(ids.map(id=>[id,state.notes.get(id+"-clip")||feedback]));
    try{data=await request(`${api}/projects/${state.project.id}/send`,{version:state.project.version,ids,feedbacks});}
    catch(error){
      // Recover the saved reservations after an interrupted acknowledgement.
      try{const current=await request(`${api}/projects/${state.project.id}`);apply(current.project);}catch(_){}
      throw error;
    }
    apply(data.project);show("clips");
    message(data.added?`${data.added} fiche(s) créée(s) en préparation. Lance Plan, Prompt et vidéo depuis l’Usine.`:"Ces versions sont déjà envoyées à l’Usine. Aucune fiche supplémentaire créée.");
  }
  async function chooseMaster(id){await save();const data=await request(`${api}/projects/${state.project.id}/master`,{version:state.project.version,asset_id:id});apply(data.project);$("source-dialog").close();}
  async function choose(shot,kind,id){await save();const data=await request(`${api}/projects/${state.project.id}/choose`,{version:state.project.version,shot_id:shot,kind,attempt_id:id});apply(data.project);}
  const lightbox=$("lightbox"), lightboxImage=$("lightbox-image"), lightboxStatus=$("lightbox-status");
  function fitLightbox(){
    if(!lightbox.open||!lightboxImage.naturalWidth||lightboxImage.hidden)return;
    const availableWidth=Math.max(1,document.documentElement.clientWidth-58);
    const availableHeight=Math.max(1,window.innerHeight-$("lightbox-head").getBoundingClientRect().height-58);
    const scale=Math.min(1,availableWidth/lightboxImage.naturalWidth,availableHeight/lightboxImage.naturalHeight);
    const width=Math.floor(lightboxImage.naturalWidth*scale), height=Math.floor(lightboxImage.naturalHeight*scale);
    lightbox.style.width=`${Math.min(document.documentElement.clientWidth-32,Math.max(280,width+26))}px`;
    lightboxImage.style.width=`${width}px`;lightboxImage.style.height=`${height}px`;
  }
  function imageReady(){
    if(!lightbox.open||!lightboxImage.naturalWidth)return;
    lightboxStatus.hidden=true;lightboxImage.hidden=false;fitLightbox();
  }
  function preview(id,label="Aperçu de l’image"){
    hideImageHover();
    $("lightbox-title").textContent=label;lightboxImage.alt=label;
    lightboxImage.hidden=true;lightboxStatus.hidden=false;lightboxStatus.textContent="Chargement de l’image…";
    lightbox.style.removeProperty("width");lightboxImage.src=asset(id);
    if(!lightbox.open)lightbox.showModal();
    if(lightboxImage.complete&&lightboxImage.naturalWidth)imageReady();
  }
  lightboxImage.addEventListener("load",imageReady);
  lightboxImage.addEventListener("error",()=>{
    if(!lightbox.open)return;
    lightboxImage.hidden=true;lightboxStatus.hidden=false;lightboxStatus.textContent="L’image n’a pas pu être chargée. Ferme cet aperçu et réessaie.";
  });
  lightbox.addEventListener("close",()=>{lightboxImage.removeAttribute("src");hideImageHover();});
  function frame(id,label){
    const b=element("button");b.type="button";b.className="rc-frame";
    b.addEventListener("click",()=>preview(id,label));b.setAttribute("aria-label",`Agrandir · ${label}`);b.setAttribute("aria-haspopup","dialog");
    const img=element("img");img.src=asset(id);img.alt=label;img.loading="lazy";b.append(img);return b;
  }

  const imageHover=$("hover-preview"), hoverImage=$("hover-image");
  const hoverSelector=".rc-frame, .rc-master, .rc-thumbs button";
  let hoverTimer=null, hoverAnchor=null;
  function hideImageHover(){
    clearTimeout(hoverTimer);hoverTimer=null;
    if(hoverAnchor){
      const ids=(hoverAnchor.getAttribute("aria-describedby")||"").split(/\s+/).filter(id=>id&&id!==imageHover.id);
      if(ids.length)hoverAnchor.setAttribute("aria-describedby",ids.join(" "));else hoverAnchor.removeAttribute("aria-describedby");
    }
    hoverAnchor=null;
    if(typeof imageHover.hidePopover==="function"&&imageHover.matches(":popover-open"))imageHover.hidePopover();
    imageHover.hidden=true;
  }
  function placeImageHover(){
    const anchor=hoverAnchor, source=anchor?.querySelector("img");
    if(!anchor?.isConnected||root.hidden||lightbox.open||!source)return hideImageHover();
    if(!source.complete||!source.naturalWidth)return;
    const rect=source.getBoundingClientRect(), margin=12;
    if(rect.width<=0||rect.height<=0)return hideImageHover();
    // Measure the contained image, excluding the thumbnail's letterboxing.
    const fit=Math.min(rect.width/source.naturalWidth,rect.height/source.naturalHeight);
    let width=source.naturalWidth*fit*2, height=source.naturalHeight*fit*2;
    const vw=document.documentElement.clientWidth, vh=window.innerHeight;
    const scale=Math.min(1,(vw-2*margin-14)/width,(vh-2*margin-38)/height);
    if(!Number.isFinite(scale)||scale<=0)return hideImageHover();
    width=Math.floor(width*scale);height=Math.floor(height*scale);
    hoverImage.src=source.currentSrc||source.src;hoverImage.alt=source.alt;
    $("hover-caption").textContent=`${source.alt||"Aperçu"} · ${scale<1?"adapté à l’écran":"×2"}`;
    imageHover.style.width=`${width}px`;hoverImage.style.height=`${height}px`;
    imageHover.hidden=false;
    if(typeof imageHover.showPopover==="function"&&!imageHover.matches(":popover-open"))imageHover.showPopover();
    const box=imageHover.getBoundingClientRect();
    let left=rect.right+margin;
    if(left+box.width>vw-margin)left=rect.left-box.width-margin;
    imageHover.style.left=`${Math.max(margin,Math.min(left,vw-box.width-margin))}px`;
    imageHover.style.top=`${Math.max(margin,Math.min(rect.top+(rect.height-box.height)/2,vh-box.height-margin))}px`;
    const ids=new Set((anchor.getAttribute("aria-describedby")||"").split(/\s+/).filter(Boolean));
    ids.add(imageHover.id);anchor.setAttribute("aria-describedby",[...ids].join(" "));
  }
  function scheduleImageHover(anchor){
    if(hoverAnchor===anchor||lightbox.open)return;
    hideImageHover();hoverAnchor=anchor;
    hoverTimer=setTimeout(()=>{hoverTimer=null;placeImageHover();},180);
  }
  root.addEventListener("pointerover",event=>{
    if(event.pointerType==="touch")return;
    const anchor=event.target.closest(hoverSelector);
    if(anchor&&!anchor.contains(event.relatedTarget))scheduleImageHover(anchor);
  });
  root.addEventListener("pointerout",event=>{
    const anchor=event.target.closest(hoverSelector);
    if(anchor&&!anchor.contains(event.relatedTarget))hideImageHover();
  });
  root.addEventListener("focusin",event=>{
    const anchor=event.target.closest(hoverSelector);
    if(anchor?.matches(":focus-visible"))scheduleImageHover(anchor);
  });
  root.addEventListener("focusout",event=>{if(hoverAnchor?.contains(event.target)&&!hoverAnchor.contains(event.relatedTarget))hideImageHover();});
  root.addEventListener("load",event=>{if(hoverAnchor?.contains(event.target)&&!hoverTimer)placeImageHover();},true);
  root.addEventListener("pointerdown",hideImageHover);
  document.addEventListener("scroll",hideImageHover,true);
  document.addEventListener("keydown",event=>{if(event.key==="Escape")hideImageHover();});
  window.addEventListener("resize",()=>{hideImageHover();fitLightbox();});
  window.addEventListener("blur",hideImageHover);
  function controls(){
    const p=state.project, locked=state.busy||!!p?.active;
    $("status").textContent=p?(p.paused?"En pause":p.active?"Préparation en cours":"Projet enregistré")+(state.dirty?" · modifications à enregistrer":""):"Nouveau projet";
    const failures=p?.jobs.filter(j=>j.status==="failed").length||0;if(failures)$("status").textContent+=` · ${failures} préparation(s) en échec`;
    for(const id of ["save","create-master","propose","save-shots","add","all-animate","revise","approve-images","approve-krea-images","sources","upload"])$(id).disabled=locked;
    $("restore-draft").hidden=state.recoveryDraft?.id!==p?.id||!state.recoveryDraft;$("restore-draft").disabled=locked;
    $("create-master").disabled=locked||!$("style_preset_id").value||!$("intention").value.trim();
    $("propose").disabled=locked||!p?.master_asset_id;
    $("approve-images").disabled=locked||!state.shots.length;
    $("approve-krea-images").disabled=locked||!state.shots.length;
    $("revise").disabled=locked||!p?.master_asset_id;
    $("pause").hidden=!p?.active||p.paused;$("resume").hidden=!p?.paused;
    $("abandon").hidden=!p?.active||!p.paused;
    $("pause").disabled=state.busy;$("resume").disabled=state.busy;$("abandon").disabled=state.busy;
    for(const id of ["generate-images","generate-clips"])$(id).disabled=locked||!state.selection.size;
    $("export").disabled=state.busy||state.dirty||!state.selection.size;
    root.querySelectorAll("#rc-form input,#rc-form textarea,#rc-form select,[data-rc-edit]").forEach(e=>e.disabled=locked);
    root.querySelectorAll("[data-rc-mode]").forEach(e=>e.disabled=locked||state.shots.find(s=>s.id===e.dataset.rcMode)?.image_engine==="krea2");
    root.querySelectorAll("[data-rc-mutate]").forEach(e=>e.disabled=locked);
    const selectedShots=state.shots.filter(s=>state.selection.has(s.id));
    const missing=selectedShots.filter(s=>!s.image_ready);
    const unreviewed=selectedShots.filter(s=>s.image_ready&&!s.image_reviewed);
    $("generate-clips").disabled=state.busy||state.dirty||!selectedShots.length||!!missing.length||!!unreviewed.length;
    $("review-images").disabled=state.busy||state.dirty||!selectedShots.length||!!missing.length||!unreviewed.length;
    $("send-hint").textContent=state.dirty?"Enregistre les modifications avant l’envoi.":missing.length?`${missing.length} plan(s) sélectionné(s) attendent leurs images. Décoche-les pour envoyer les plans prêts.`:unreviewed.length?`${unreviewed.length} plan(s) à revoir et valider avant l’envoi.`:"";
    root.querySelectorAll("[data-rc-send]").forEach(e=>e.disabled=state.busy||state.dirty||!state.shots.find(s=>s.id===e.dataset.rcSend)?.image_reviewed);
    root.querySelectorAll("[data-rc-review]").forEach(e=>e.disabled=state.busy||state.dirty||!state.shots.find(s=>s.id===e.dataset.rcReview)?.image_ready);
    root.querySelectorAll("[data-rc-end]").forEach(e=>{const s=state.shots.find(s=>s.id===e.dataset.rcEnd);e.disabled=locked||state.dirty||!s?.start_ready||s.mode!=="endpoints";});
    $("new").disabled=state.busy;$("projects").disabled=state.busy;$("refresh").disabled=state.busy;
  }
  function drawMaster(){
    hideImageHover();
    const master=$("master-preview");master.replaceChildren();
    if(state.project?.master_asset_id){const img=element("img");img.src=asset(state.project.master_asset_id);img.alt="Plat terminé choisi";master.append(img);}else master.append(element("span","Choisir ou créer l’image du plat"));
    $("master-trials").replaceChildren();
    for(const trial of state.project?.master_images||[]){const b=button("",()=>chooseMaster(trial.asset_id));b.dataset.rcMutate="1";const img=element("img");img.src=asset(trial.asset_id);img.alt=trial.label;b.append(img);b.setAttribute("aria-label",`Choisir ce plat · ${trial.label}`);b.classList.toggle("rc-selected",trial.asset_id===state.project.master_asset_id);$("master-trials").append(b);}
  }
  function field(card,shot,key,label,type="textarea"){
    const wrap=element("label",label), input=element(type==="number"?"input":type);
    input.dataset.rcEdit="1";
    if(type==="number"){input.type="number";input.min="5";input.max="15";input.step="0.5";}
    if(type==="textarea"){input.rows=key==="action"||key==="scene"?3:2;input.maxLength=["framing","mode_reason"].includes(key)?1000:3000;}
    if(type==="select"){
      const options=key==="image_engine"?[["H3 · référence / édition","h3"],["KREA2 + Flux Klein · nouvelle image","krea2"]]:key==="purpose"?[["Selon le geste (ancien plan)","auto"],["Préparation du plat","preparation"],["Présentation du plat terminé","presentation"]]:[["Animer une image (par défaut)","animate"],["Départ et arrivée précis","endpoints"]];
      for(const [label,value] of options)input.add(new Option(label,value));
    }
    if(key==="title")input.maxLength=160;
    if(key==="mode")input.dataset.rcMode=shot.id;
    input.value=shot[key]??(key==="image_engine"?"h3":"");input.addEventListener("input",()=>{
      shot[key]=type==="number"?Number(input.value):input.value;
      if(key==="image_engine"&&shot.image_engine==="krea2"){
        shot.mode="animate";card.querySelector("[data-rc-mode]").value="animate";
      }
      changed();timing();
    });
    wrap.append(input);card.append(wrap);
  }
  function timing(){$("timing").textContent=`${state.shots.length} plans · ${state.shots.reduce((n,s)=>n+(Number(s.duration)||0),0)} s prévues · cible ${$("target_duration").value} s. Clips de 5 à 15 s.`;}
  function drawShots(){
    const list=$("shots");list.replaceChildren();timing();
    for(const [i,s] of state.shots.entries()){
      const card=element("article",undefined,"rc-card");card.append(element("h3",`Plan ${i+1}`));
      field(card,s,"title","Titre","input");field(card,s,"action","Geste à montrer");field(card,s,"framing","Cadrage");
      field(card,s,"purpose","Rôle du plan","select");field(card,s,"scene","Scène : aliments, récipient et outils");
      field(card,s,"image_engine","Moteur des images et régénérations","select");
      field(card,s,"opening","Image au début du geste");field(card,s,"ending","État à la fin du geste");field(card,s,"duration","Durée (secondes)","number");field(card,s,"mode","Préparation des images","select");
      field(card,s,"mode_reason","Pourquoi deux images seraient nécessaires (si applicable)");
      const row=element("div",undefined,"rc-actions");
      for(const [text,delta] of [["↑",-1],["↓",1]]){const b=button(text,()=>{const n=i+delta;if(n<0||n>=state.shots.length)return;[state.shots[i],state.shots[n]]=[state.shots[n],state.shots[i]];changed();drawShots();controls();});b.dataset.rcMutate="1";b.title="Déplacer le plan";row.append(b);}
      const remove=button("Retirer",()=>{if(state.shots.length===1)throw new Error("Conserve au moins un plan.");state.shots.splice(i,1);state.selection.delete(s.id);changed();drawShots();});remove.dataset.rcMutate="1";row.append(remove);card.append(row);list.append(card);
    }
    if(!state.shots.length)list.append(element("p","Le découpage apparaîtra ici après sa préparation.","muted"));
  }
  function cardTitle(card,s,index){const label=element("label",undefined,"rc-check"), c=element("input");c.type="checkbox";c.checked=state.selection.has(s.id);c.addEventListener("change",()=>{c.checked?state.selection.add(s.id):state.selection.delete(s.id);root.querySelectorAll(`[data-rc-shot-check="${s.id}"]`).forEach(e=>e.checked=c.checked);controls();});c.dataset.rcShotCheck=s.id;label.append(c,element("strong",`${index+1}. ${s.title}`));card.append(label);}
  function engineLabel(engine){return engine==="krea2"?"KREA2 + Flux Klein":"H3";}
  function modeLabel(shot){return element("p",`${shot.mode==="endpoints"?"Départ + arrivée · 2 images":"Animation · 1 image"} · ${engineLabel(shot.image_engine)}`,"rc-mode");}
  function imagePair(image,label,mode="endpoints"){
    const pair=element("div",undefined,"rc-pair");
    for(const [id,role] of [[image.start_asset_id,"Départ"],[mode==="endpoints"?image.end_asset_id:null,"Arrivée"]]){
      if(!id)continue;const item=element("div");item.append(element("small",role),frame(id,`${label} · ${role}`));pair.append(item);
    }
    return pair;
  }
  function note(card,shot,caption="Correction pour le prochain essai"){const label=element("label",caption), input=element("textarea");input.rows=2;input.maxLength=4000;input.value=state.notes.get(shot)||"";input.dataset.rcEdit="1";input.addEventListener("input",()=>state.notes.set(shot,input.value));label.append(input);card.append(label);}
  function reviewControl(card,s){
    if(!s.image_ready)return;
    card.append(element("p",s.image_reviewed?"Images revues et validées":"Images générées · à revoir",s.image_reviewed?"rc-reviewed":"rc-warning"));
    if(!s.image_reviewed)card.append(element("p","Vérifie le plat, le début du geste et, s’il y en a une, la cohérence de l’arrivée.","muted"));
    const review=button(s.image_reviewed?"Retirer la validation":"J’ai revu les images · valider",()=>reviewImages([s.id],!s.image_reviewed));
    review.dataset.rcReview=s.id;card.append(review);
  }
  function imageTrials(card,s,holder){
    for(const archived of [false,true]){
      const attempts=(holder.images||[]).filter(a=>!!a.stale===archived);
      if(!attempts.length&&archived)continue;
      const trials=element("details",undefined,archived?"rc-archives":"");
      trials.append(element("summary",archived?`Archives · ${attempts.length} ancien(s) essai(s)`:`${attempts.length} essai(s) du plan actuel`));
      for(const [n,a] of attempts.entries()){
        const title=`${archived?(a.label||"Ancienne version"):`${s.title} · essai ${n+1}`} · ${engineLabel(a.image_engine)}`;
        const row=element("div",undefined,"rc-actions");
        trials.append(element("p",title,"muted"));
        row.append(button(`Voir départ ${n+1}`,()=>preview(a.start_asset_id,title+" · départ")));
        if(a.end_asset_id)row.append(button("Voir arrivée",()=>preview(a.end_asset_id,title+" · arrivée")));
        if(!archived){const b=button(a.id===holder.selected_image?"Retenu ✓":"Retenir",()=>choose(s.id,"image",a.id));b.dataset.rcMutate="1";row.append(b);}
        trials.append(row);
        const details=element("details");details.append(element("summary","Instructions de l’essai"));
        for(const [role,out] of Object.entries(a.outputs||{}))details.append(element("p",`${role==="end"?"Arrivée":"Départ"} : ${out.prompt||""}`,"muted"));
        trials.append(details);
      }
      card.append(trials);
    }
  }
  function drawImages(){
    hideImageHover();
    const list=$("images");list.replaceChildren();
    for(const [i,s] of state.shots.entries()){
      const h=state.project?.media[s.id]||{}, chosen=h.images?.find(a=>a.id===h.selected_image&&!a.stale);
      const job=s.image_job;
      const card=element("article",undefined,"rc-card");cardTitle(card,s,i);card.append(modeLabel(s));
      if(chosen)card.append(imagePair(chosen,s.title,s.mode));
      else if(s.start_asset_id){card.append(frame(s.start_asset_id,s.title+" · départ"),element("p",s.mode==="endpoints"?"Départ conservé · arrivée à générer ou à reprendre.":"Départ disponible · retiens un essai compatible dans l’historique.","muted"));}
      else card.append(element("div",job?names[job.status]||job.status:"Image à préparer","rc-placeholder"));
      if(job?.error)card.append(element("p",job.error,"rc-error"));
      if(s.image_stale&&!s.start_ready)card.append(element("p","Le plan a changé. Ses anciens essais sont conservés dans les archives.","rc-warning"));
      reviewControl(card,s);imageTrials(card,s,h);note(card,s.id);
      const actions=element("div",undefined,"rc-actions");
      const retry=button(chosen||s.start_ready?"Régénérer ce plan":"Générer ce plan",()=>enqueue("image",[s.id],state.notes.get(s.id)||""));retry.dataset.rcMutate="1";actions.append(retry);
      if(s.mode==="endpoints"&&s.start_ready){
        const end=button(chosen?.end_asset_id?"Corriger l’arrivée seule":"Générer l’arrivée seule",()=>enqueue("image",[s.id],state.notes.get(s.id)||"","end"));end.dataset.rcEnd=s.id;actions.append(end);
      }
      card.append(actions);
      if(s.mode==="endpoints"&&s.start_ready)card.append(element("small","L’arrivée seule réutilise le départ affiché sans le régénérer.","muted"));
      list.append(card);
    }
  }
  function clipTrials(card,s,index,holder){
    for(const archived of [false,true]){
      const attempts=(holder.clips||[]).filter(c=>!!c.stale===archived);
      if(!attempts.length&&archived)continue;
      const trials=element("details",undefined,archived?"rc-archives":"");
      trials.append(element("summary",archived?`Archives · ${attempts.length} ancien(s) envoi(s)`:`${attempts.length} envoi(s) du plan actuel`));
      for(const [n,c] of attempts.entries()){
        const row=element("div",undefined,"rc-actions");row.append(element("small",`${archived?(c.entry?.name||"Ancien plan"):`Envoi ${n+1}`} · ${names[c.status]||c.status}`));
        if(c.asset_id){
          const a=element("a","Télécharger");a.href=asset(c.asset_id);a.download=`${String(index+1).padStart(2,"0")}_${s.id}_${c.id}.mp4`;row.append(a);
          if(!archived){const b=button(c.id===holder.selected_clip?"Retenu ✓":"Retenir",()=>choose(s.id,"clip",c.id));b.dataset.rcMutate="1";row.append(b);}
        }
        if(c.factory_id&&!c.factory_missing)row.append(button("Voir dans l’Usine",()=>window.PanelForgeVideoFactory?.open([c.factory_id])));
        trials.append(row);
      }
      card.append(trials);
    }
  }
  function drawClips(){
    hideImageHover();
    const list=$("clips");list.replaceChildren();
    for(const [i,s] of state.shots.entries()){
      const holder=state.project?.media[s.id]||{}, clips=(holder.clips||[]).filter(c=>!c.stale);
      const selected=clips.find(c=>c.id===holder.selected_clip), latest=clips.at(-1), shown=selected||latest;
      const card=element("article",undefined,"rc-card");cardTitle(card,s,i);card.append(modeLabel(s));
      const images=holder.images?.find(a=>a.id===holder.selected_image&&!a.stale);
      if(shown?.asset_id){const video=element("video");video.src=asset(shown.asset_id);video.controls=true;video.preload="metadata";card.append(video);}
      else if(images)card.append(imagePair(images,s.title,s.mode));
      else card.append(element("div","Images à préparer","rc-placeholder"));
      if(shown?.asset_id&&shown.id!==holder.selected_clip){const retain=button("Retenir ce clip pour l’export",()=>choose(s.id,"clip",shown.id));retain.dataset.rcMutate="1";card.append(retain);}
      const current=clips.findLast(c=>c.factory_id&&!c.factory_missing);
      if(current){
        card.append(element("p",`Envoyé à l’Usine · ${names[current.status]||current.status}`,"rc-delivery-status"));
        card.append(button("Ouvrir dans l’Usine",()=>window.PanelForgeVideoFactory?.open([current.factory_id])));
      }
      // Review actual images, not the video, when this source has not been approved.
      if(shown?.asset_id&&images&&!s.image_reviewed)card.append(imagePair(images,s.title,s.mode));
      reviewControl(card,s);
      if(latest&&latest!==shown)card.append(element("p",`Dernier envoi : ${names[latest.status]||latest.status}`,"muted"));
      if(latest?.error)card.append(element("p",latest.error,"rc-error"));
      if(!s.image_ready)card.append(element("p",s.start_ready?"Le départ est disponible. Prépare l’arrivée dans Images.":"Prépare les images du plan actuel dans Images avant l’envoi.","rc-warning"));
      clipTrials(card,s,i,holder);note(card,s.id+"-clip","Correction pour le prochain envoi");
      const send=button("Envoyer à l’Usine",()=>sendToFactory([s.id],state.notes.get(s.id+"-clip")||""));send.dataset.rcSend=s.id;card.append(send);list.append(card);
    }
  }
  function drawJobs(){const list=$("jobs");list.replaceChildren();for(const job of [...(state.project?.jobs||[])].reverse().slice(0,50)){const title=job.label||({master:"Plat KREA2",plan:"Découpage"}[job.kind]||job.kind);list.append(element("p",`${title} · ${names[job.status]||job.status}${job.phase==="end"?" · image d’arrivée":""}${job.error?" — "+job.error:""}`,job.error?"rc-error":""));}}
  function draw(){drawMaster();drawShots();drawImages();drawClips();drawJobs();controls();}
  function needsPoll(){return state.project&&(state.project.active||Object.values(state.project.media).some(h=>h.clips.some(c=>!c.stale&&c.factory_id&&!c.factory_missing&&["queued","active","preparation"].includes(c.status))));}
  function schedule(){clearTimeout(state.timer);if(root.hidden||!needsPoll())return;state.timer=setTimeout(poll,2500);}
  async function poll(){
    if(root.hidden)return;
    if(state.busy||state.dirty){schedule();return;}
    const id=state.project?.id;if(!id)return;
    try{const data=await request(`${api}/projects/${id}`);if(state.project?.id!==id||state.busy||state.dirty)return;
      if(data.project.version!==state.project.version){const planFinished=data.project.shots.length&&!state.shots.length;apply(data.project);if(planFinished){state.selection=new Set(state.shots.map(s=>s.id));drawImages();drawClips();controls();}}}
    catch(error){message(error.message,true);}finally{schedule();}
  }
  async function sources(){await save();const data=await request(`${api}/sources`);const list=$("source-list");list.replaceChildren();for(const item of data.images){const card=element("article",undefined,"rc-card");card.append(frame(item.asset_id,item.label),element("p",item.label),button("Choisir ce plat",()=>chooseMaster(item.asset_id)));list.append(card);}if(!data.images.length)list.append(element("p","Aucune image terminée. Tu peux importer une image ou créer le plat avec KREA2."));$("source-dialog").showModal();}
  async function fresh(){if(state.dirty)await save();state.load++;state.project=null;state.shots=[];state.selection.clear();state.notes.clear();state.newCommand=uid();state.dirty=false;fillSettings(state.defaults);$("name").value="Nouvelle recette";$("projects").value="";draw();show("universe");}
  async function initialize(){
    if(state.initialized)return;if(state.initializing)return state.initializing;
    state.initializing=(async()=>{
      const results=await Promise.allSettled([request(`${api}/spec`),request("/api/stories/models")]);
      if(results[0].status!=="fulfilled")throw results[0].reason;
      const spec=results[0].value;state.defaults=spec.settings;
      $("style_preset_id").replaceChildren(new Option("Choisir un preset",""),...spec.presets.map(p=>new Option(p.name,p.id)));
      const wool=spec.presets.find(p=>/wool|laine|crochet/i.test(p.name));if(wool)state.defaults.style_preset_id=wool.id;
      if(results[1].status==="fulfilled")$("models").replaceChildren(...results[1].value.models.map(m=>{const o=element("option");o.value=m.id;o.label=m.label;return o;}));
      fillSettings(state.defaults);$("name").value="Nouvelle recette";await catalog();
      let last;try{last=localStorage.getItem("panelforge.recipes.current");}catch(_){}
      if(last&&[...$("projects").options].some(o=>o.value===last))await load(last);else draw();
      state.initialized=true;
    })();
    try{await state.initializing;}finally{state.initializing=null;}
  }

  root.querySelectorAll("[data-rc-tab]").forEach(b=>b.addEventListener("click",()=>show(b.dataset.rcTab)));
  root.querySelectorAll("[data-rc-select]").forEach(b=>b.addEventListener("click",()=>{state.selection=b.dataset.rcSelect==="all"?new Set(state.shots.map(s=>s.id)):new Set();drawImages();drawClips();controls();}));
  $("form").addEventListener("input",changed);$("form").addEventListener("change",changed);
  $("form").addEventListener("submit",e=>{e.preventDefault();act(save);});
  $("form").addEventListener("invalid",e=>{for(let n=e.target.parentElement;n&&n!==$("form");n=n.parentElement)if(n.tagName==="DETAILS")n.open=true;},true);
  $("new").addEventListener("click",()=>act(fresh));
  $("projects").addEventListener("change",()=>{const id=$("projects").value;if(id)act(async()=>{if(state.dirty)await save();await load(id);});});
  $("refresh").addEventListener("click",()=>act(async()=>{if(state.dirty&&state.project)state.recoveryDraft={id:state.project.id,name:$("name").value,settings:settings(),shots:cleanShots()};if(state.project)await load(state.project.id);await catalog();if(state.recoveryDraft)message("La version enregistrée est affichée. Ton brouillon reste disponible avec Réappliquer mon brouillon.");}));
  $("restore-draft").addEventListener("click",()=>{const d=state.recoveryDraft;if(!d||d.id!==state.project?.id)return;$("name").value=d.name;fillSettings(d.settings);state.shots=d.shots;state.recoveryDraft=null;state.dirty=true;drawShots();controls();message("Brouillon réappliqué. Enregistre-le pour le conserver.");});
  $("sources").addEventListener("click",()=>act(sources));
  $("master-preview").addEventListener("click",()=>{if(state.project?.master_asset_id)preview(state.project.master_asset_id,"Plat terminé choisi");});
  $("upload").addEventListener("change",()=>act(async()=>{const file=$("upload").files[0];if(!file)return;await save();const form=new FormData();form.append("version",state.project.version);form.append("file",file);const response=await fetch(`${api}/projects/${state.project.id}/upload`,{method:"POST",body:form});const data=await response.json();if(!response.ok)throw new Error(data.detail||"Import impossible.");apply(data.project);$("upload").value="";}));
  $("create-master").addEventListener("click",()=>act(()=>enqueue("master")));
  $("propose").addEventListener("click",()=>act(()=>enqueue("plan")));
  $("revise").addEventListener("click",()=>act(()=>enqueue("plan",[],$("feedback").value)));
  $("save-shots").addEventListener("click",()=>act(save));
  $("add").addEventListener("click",()=>{state.shots.push({id:"shot-"+uid(),title:"Nouveau geste",action:"Décrire le geste",framing:"Gros plan, caméra stable",opening:"Décrire le départ",ending:"",duration:6,mode:"animate",purpose:"preparation",scene:"",mode_reason:""});state.selection.add(state.shots.at(-1).id);changed();drawShots();controls();});
  $("all-animate").addEventListener("click",()=>{for(const s of state.shots){s.mode="animate";s.mode_reason="";}changed();drawShots();controls();message("Tous les plans sont en animation à une image. Enregistre le découpage pour conserver les départs utilisables.");});
  $("approve-images").addEventListener("click",()=>act(()=>enqueue("image",state.shots.map(s=>s.id),"","all","h3")));
  $("approve-krea-images").addEventListener("click",()=>act(()=>enqueue("image",state.shots.map(s=>s.id),"","all","krea2")));
  $("generate-images").addEventListener("click",()=>act(()=>enqueue("image",[...state.selection])));
  $("review-images").addEventListener("click",()=>act(()=>reviewImages([...state.selection])));
  $("to-clips").addEventListener("click",()=>show("clips"));
  $("generate-clips").addEventListener("click",()=>act(()=>sendToFactory([...state.selection])));
  for(const action of ["pause","resume","abandon"])$(action).addEventListener("click",()=>act(async()=>{const data=await request(`${api}/projects/${state.project.id}/control/${action}`,{});apply(data.project);}));
  $("export").addEventListener("click",()=>act(async()=>{const response=await fetch(`${api}/projects/${state.project.id}/export`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({version:state.project.version,ids:[...state.selection]})});if(!response.ok){const data=await response.json();throw new Error(data.detail||"Export impossible.");}const url=URL.createObjectURL(await response.blob()), a=element("a");a.href=url;a.download="recette_clips.zip";a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);message("Clips exportés dans l’ordre du découpage.");}));
  $("source-close").addEventListener("click",()=>$("source-dialog").close());$("lightbox-close").addEventListener("click",()=>lightbox.close());
  $("source-dialog").addEventListener("close",hideImageHover);
  for(const id of ["source-dialog","lightbox"]){
    const dialog=$(id);let startedOutside=false;
    const outside=event=>{const rect=dialog.getBoundingClientRect();return event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;};
    dialog.addEventListener("pointerdown",event=>{startedOutside=event.target===dialog&&outside(event);});
    dialog.addEventListener("click",event=>{if(startedOutside&&event.target===dialog&&outside(event))dialog.close();startedOutside=false;});
  }
  document.querySelector('[data-lab-view="recipes"]')?.addEventListener("click",()=>act(initialize));
  new MutationObserver(()=>{if(root.hidden){clearTimeout(state.timer);hideImageHover();if(lightbox.open)lightbox.close();}else if(!state.initialized)act(initialize);else{poll();schedule();}}).observe(root,{attributes:true,attributeFilter:["hidden"]});
  window.addEventListener("beforeunload",e=>{clearTimeout(state.timer);if(state.dirty){e.preventDefault();e.returnValue="";}});
  window.PanelForgeRecipes=Object.freeze({
    open:async(id=null)=>act(async()=>{window.PanelForgeLabNavigation?.switchView("recipes");await initialize();if(id){if(state.dirty)await save();await load(id);}}),
    fromImage:async(assetId,name)=>act(async()=>{window.PanelForgeLabNavigation?.switchView("recipes");await initialize();await fresh();$("name").value=(name||"Nouvelle recette").slice(0,120);await ensure();await chooseMaster(assetId);show("universe");}),
  });
  if(!root.hidden)act(initialize);
})();
