(() => {
  "use strict";
  const root = document.getElementById("recipes-workspace");
  if (!root) return;
  const $ = id => document.getElementById(`rc-${id}`);
  const api = "/api/recipes";
  const asset = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const uid = () => crypto.randomUUID().replaceAll("-", "");
  const fields = ["intention", "target_duration", "aspect_ratio", "world", "cook", "camera", "audio", "model_id", "edit_model_id", "plan_model_id", "writer_model_id", "style_preset_id"];
  const shotFields = ["id", "title", "action", "framing", "opening", "ending", "duration", "mode"];
  const names = {queued:"En file", working:"Préparation", waiting:"Rendu en cours", active:"En cours", preparation:"Prêt dans l’usine", succeeded:"Terminé", failed:"Échec", cancelled:"Abandonné", paused:"En pause"};
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
  function show(tab){state.tab=tab;root.querySelectorAll("[data-rc-panel]").forEach(p=>p.hidden=p.dataset.rcPanel!==tab);root.querySelectorAll("[data-rc-tab]").forEach(b=>b.classList.toggle("active",b.dataset.rcTab===tab));controls();}
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
  function pendingCommand(kind, ids, feedback){
    const key=JSON.stringify({id:state.project.id,kind,ids,feedback});
    try{const p=JSON.parse(sessionStorage.getItem("panelforge.recipes.command")||"null");if(p?.key===key)return p.command;const command=uid();sessionStorage.setItem("panelforge.recipes.command",JSON.stringify({key,command}));return command;}catch(_){return uid();}
  }
  async function enqueue(kind, ids=[], feedback=""){
    await save();
    if(["image","clip"].includes(kind)&&!state.project.approved_current){
      const data=await request(`${api}/projects/${state.project.id}/approve`,{version:state.project.version});apply(data.project);
    }
    const data=await request(`${api}/projects/${state.project.id}/generate/${kind}`,{version:state.project.version,command:pendingCommand(kind,ids,feedback),ids,feedback});
    try{sessionStorage.removeItem("panelforge.recipes.command");}catch(_){}
    apply(data.project);show(kind==="plan"?"breakdown":kind==="image"?"images":kind==="clip"?"clips":"universe");
    message(kind==="clip"?"Les clips sélectionnés sont envoyés à la file de production.":"Préparation enregistrée. Les résultats apparaîtront ici.");
  }
  async function chooseMaster(id){await save();const data=await request(`${api}/projects/${state.project.id}/master`,{version:state.project.version,asset_id:id});apply(data.project);$("source-dialog").close();}
  async function choose(shot,kind,id){await save();const data=await request(`${api}/projects/${state.project.id}/choose`,{version:state.project.version,shot_id:shot,kind,attempt_id:id});apply(data.project);}
  function preview(id){$("lightbox-image").src=asset(id);$("lightbox").showModal();}
  function frame(id,label){const b=button("",()=>preview(id));b.className="rc-frame";const img=element("img");img.src=asset(id);img.alt=label;img.loading="lazy";b.append(img);b.title="Agrandir";return b;}
  function controls(){
    const p=state.project, locked=state.busy||!!p?.active;
    $("status").textContent=p?(p.paused?"En pause":p.active?"Préparation en cours":"Projet enregistré")+(state.dirty?" · modifications à enregistrer":""):"Nouveau projet";
    const failures=p?.jobs.filter(j=>j.status==="failed").length||0;if(failures)$("status").textContent+=` · ${failures} préparation(s) en échec`;
    for(const id of ["save","create-master","propose","save-shots","add","revise","approve-images","sources","upload"])$(id).disabled=locked;
    $("restore-draft").hidden=state.recoveryDraft?.id!==p?.id||!state.recoveryDraft;$("restore-draft").disabled=locked;
    $("create-master").disabled=locked||!$("style_preset_id").value||!$("intention").value.trim();
    $("propose").disabled=locked||!p?.master_asset_id;
    $("approve-images").disabled=locked||!state.shots.length;
    $("revise").disabled=locked||!p?.master_asset_id;
    $("pause").hidden=!p?.active||p.paused;$("resume").hidden=!p?.paused;
    $("abandon").hidden=!p?.active||!p.paused;
    $("pause").disabled=state.busy;$("resume").disabled=state.busy;$("abandon").disabled=state.busy;
    for(const id of ["generate-images","generate-clips"])$(id).disabled=locked||!state.selection.size;
    $("export").disabled=state.busy||state.dirty||!state.selection.size;
    root.querySelectorAll("#rc-form input,#rc-form textarea,#rc-form select,[data-rc-edit]").forEach(e=>e.disabled=locked);
    root.querySelectorAll("[data-rc-mutate]").forEach(e=>e.disabled=locked);
    $("new").disabled=state.busy;$("projects").disabled=state.busy;$("refresh").disabled=state.busy;
  }
  function drawMaster(){
    const master=$("master-preview");master.replaceChildren();
    if(state.project?.master_asset_id){const img=element("img");img.src=asset(state.project.master_asset_id);img.alt="Plat terminé choisi";master.append(img);}else master.append(element("span","Choisir ou créer l’image du plat"));
    $("master-trials").replaceChildren();
    for(const trial of state.project?.master_images||[]){const b=button("",()=>chooseMaster(trial.asset_id));b.dataset.rcMutate="1";const img=element("img");img.src=asset(trial.asset_id);img.alt=trial.label;b.append(img);b.title="Choisir ce plat";b.classList.toggle("rc-selected",trial.asset_id===state.project.master_asset_id);$("master-trials").append(b);}
  }
  function field(card,shot,key,label,type="textarea"){
    const wrap=element("label",label), input=element(type==="number"?"input":type);
    input.dataset.rcEdit="1";
    if(type==="number"){input.type="number";input.min="5";input.max="15";input.step="0.5";}
    if(type==="textarea"){input.rows=key==="action"?3:2;input.maxLength=key==="framing"?1000:3000;}
    if(type==="select"){input.add(new Option("Animer une image","animate"));input.add(new Option("Départ et arrivée précis","endpoints"));}
    if(key==="title")input.maxLength=160;
    input.value=shot[key];input.addEventListener("input",()=>{shot[key]=type==="number"?Number(input.value):input.value;changed();timing();});
    wrap.append(input);card.append(wrap);
  }
  function timing(){$("timing").textContent=`${state.shots.length} plans · ${state.shots.reduce((n,s)=>n+(Number(s.duration)||0),0)} s prévues · cible ${$("target_duration").value} s. Clips de 5 à 15 s.`;}
  function drawShots(){
    const list=$("shots");list.replaceChildren();timing();
    for(const [i,s] of state.shots.entries()){
      const card=element("article",undefined,"rc-card");card.append(element("h3",`Plan ${i+1}`));
      field(card,s,"title","Titre","input");field(card,s,"action","Geste à montrer");field(card,s,"framing","Cadrage");
      field(card,s,"opening","Image au début du geste");field(card,s,"ending","État à la fin du geste");field(card,s,"duration","Durée (secondes)","number");field(card,s,"mode","Préparation des images","select");
      const row=element("div",undefined,"rc-actions");
      for(const [text,delta] of [["↑",-1],["↓",1]]){const b=button(text,()=>{const n=i+delta;if(n<0||n>=state.shots.length)return;[state.shots[i],state.shots[n]]=[state.shots[n],state.shots[i]];changed();drawShots();controls();});b.dataset.rcMutate="1";b.title="Déplacer le plan";row.append(b);}
      const remove=button("Retirer",()=>{if(state.shots.length===1)throw new Error("Conserve au moins un plan.");state.shots.splice(i,1);state.selection.delete(s.id);changed();drawShots();});remove.dataset.rcMutate="1";row.append(remove);card.append(row);list.append(card);
    }
    if(!state.shots.length)list.append(element("p","Le découpage apparaîtra ici après sa préparation.","muted"));
  }
  function cardTitle(card,s,index){const label=element("label",undefined,"rc-check"), c=element("input");c.type="checkbox";c.checked=state.selection.has(s.id);c.addEventListener("change",()=>{c.checked?state.selection.add(s.id):state.selection.delete(s.id);root.querySelectorAll(`[data-rc-shot-check="${s.id}"]`).forEach(e=>e.checked=c.checked);controls();});c.dataset.rcShotCheck=s.id;label.append(c,element("strong",`${index+1}. ${s.title}`));card.append(label);}
  function note(card,shot){const label=element("label","Correction pour le prochain essai"), input=element("textarea");input.rows=2;input.maxLength=4000;input.value=state.notes.get(shot)||"";input.dataset.rcEdit="1";input.addEventListener("input",()=>state.notes.set(shot,input.value));label.append(input);card.append(label);}
  function drawImages(){
    const list=$("images");list.replaceChildren();
    for(const [i,s] of state.shots.entries()){
      const h=state.project?.media[s.id]||{}, chosen=h.images?.find(a=>a.id===h.selected_image);
      const job=[...(state.project?.jobs||[])].reverse().find(j=>j.shot_id===s.id&&j.kind==="image");
      const card=element("article",undefined,"rc-card");cardTitle(card,s,i);
      if(chosen){const pair=element("div",undefined,"rc-pair");for(const [id,label] of [[chosen.start_asset_id,"Départ"],[chosen.end_asset_id,"Arrivée"]]){if(!id)continue;const f=element("div");f.append(element("small",label),frame(id,label));pair.append(f);}card.append(pair);}
      else if(job?.outputs?.start?.asset_id){card.append(frame(job.outputs.start.asset_id,"Image de départ"),element("p","Image de départ disponible · arrivée en attente ou à reprendre.","muted"));}
      else{card.append(element("div",job?names[job.status]||job.status:"Image à préparer","rc-placeholder"));}
      if(job?.error)card.append(element("p",job.error,"rc-error"));
      if(s.image_stale)card.append(element("p","Ces images correspondent à une ancienne version du plan.","rc-warning"));
      const trials=element("details");trials.append(element("summary",`${h.images?.length||0} essai(s)`));
      for(const [n,a] of (h.images||[]).entries()){
        const row=element("div",undefined,"rc-actions");row.append(button(`Voir essai ${n+1}`,()=>preview(a.start_asset_id)));
        const chooseButton=button(a.id===h.selected_image?"Retenu ✓":"Retenir",()=>choose(s.id,"image",a.id));chooseButton.dataset.rcMutate="1";row.append(chooseButton);trials.append(row);
        const details=element("details");details.append(element("summary","Instructions de l’essai"));for(const out of Object.values(a.outputs||{}))details.append(element("p",out.prompt,"muted"));trials.append(details);
      }
      card.append(trials);note(card,s.id);
      const retry=button(chosen?"Régénérer ce plan":"Générer ce plan",()=>enqueue("image",[s.id],state.notes.get(s.id)||""));retry.dataset.rcMutate="1";card.append(retry);list.append(card);
    }
  }
  function drawClips(){
    const list=$("clips");list.replaceChildren();
    for(const [i,s] of state.shots.entries()){
      const holder=state.project?.media[s.id]||{}, clips=holder.clips||[];
      const selected=clips.find(c=>c.id===holder.selected_clip), latest=clips.at(-1), shown=selected||latest;
      const card=element("article",undefined,"rc-card");cardTitle(card,s,i);
      if(shown?.asset_id){const video=element("video");video.src=asset(shown.asset_id);video.controls=true;video.preload="metadata";card.append(video);}
      else card.append(element("div",shown?(names[shown.status]||shown.status):"Clip à préparer","rc-placeholder"));
      if(shown?.stale)card.append(element("p","Ancien clip : les images ou l’action ont changé.","rc-warning"));
      if(latest&&latest!==shown)card.append(element("p",`Dernier essai : ${names[latest.status]||latest.status}`,"muted"));
      if(latest?.error)card.append(element("p",latest.error,"rc-error"));
      if(!s.image_ready)card.append(element("p","Prépare les images actuelles de ce plan avant de l’animer.","rc-warning"));
      const trials=element("details");trials.append(element("summary",`${clips.length} essai(s)`));
      for(const [n,c] of clips.entries()){
        const row=element("div",undefined,"rc-actions");row.append(element("small",`Essai ${n+1} · ${names[c.status]||c.status}${c.stale?" · ancienne version":""}`));
        if(c.asset_id){const a=element("a","Télécharger");a.href=asset(c.asset_id);a.download=`${String(i+1).padStart(2,"0")}_${s.id}_essai_${n+1}.mp4`;row.append(a);const b=button(c.id===holder.selected_clip?"Retenu ✓":"Retenir",()=>choose(s.id,"clip",c.id));b.dataset.rcMutate="1";row.append(b);}
        if(c.factory_id)row.append(button("Voir dans l’usine",()=>window.PanelForgeVideoFactory?.open([c.factory_id])));
        trials.append(row);
      }
      card.append(trials);note(card,s.id+"-clip");
      const retry=button(clips.length?"Nouvel essai vidéo":"Animer ce plan",()=>enqueue("clip",[s.id],state.notes.get(s.id+"-clip")||""));retry.dataset.rcMutate="1";card.append(retry);list.append(card);
    }
  }
  function drawJobs(){const list=$("jobs");list.replaceChildren();for(const job of [...(state.project?.jobs||[])].reverse().slice(0,50)){const title=state.shots.find(s=>s.id===job.shot_id)?.title||({master:"Plat KREA2",plan:"Découpage"}[job.kind]||job.kind);list.append(element("p",`${title} · ${names[job.status]||job.status}${job.phase==="end"?" · image d’arrivée":""}${job.error?" — "+job.error:""}`,job.error?"rc-error":""));}}
  function draw(){drawMaster();drawShots();drawImages();drawClips();drawJobs();controls();}
  function needsPoll(){return state.project&&(state.project.active||Object.values(state.project.media).some(h=>h.clips.some(c=>["queued","active","preparation"].includes(c.status))));}
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
  $("master-preview").addEventListener("click",()=>{if(state.project?.master_asset_id)preview(state.project.master_asset_id);});
  $("upload").addEventListener("change",()=>act(async()=>{const file=$("upload").files[0];if(!file)return;await save();const form=new FormData();form.append("version",state.project.version);form.append("file",file);const response=await fetch(`${api}/projects/${state.project.id}/upload`,{method:"POST",body:form});const data=await response.json();if(!response.ok)throw new Error(data.detail||"Import impossible.");apply(data.project);$("upload").value="";}));
  $("create-master").addEventListener("click",()=>act(()=>enqueue("master")));
  $("propose").addEventListener("click",()=>act(()=>enqueue("plan")));
  $("revise").addEventListener("click",()=>act(()=>enqueue("plan",[],$("feedback").value)));
  $("save-shots").addEventListener("click",()=>act(save));
  $("add").addEventListener("click",()=>{state.shots.push({id:"shot-"+uid(),title:"Nouveau geste",action:"Décrire le geste",framing:"Gros plan, caméra stable",opening:"Décrire le départ",ending:"",duration:6,mode:"animate"});state.selection.add(state.shots.at(-1).id);changed();drawShots();controls();});
  $("approve-images").addEventListener("click",()=>act(()=>enqueue("image",state.shots.map(s=>s.id))));
  $("generate-images").addEventListener("click",()=>act(()=>enqueue("image",[...state.selection])));
  $("to-clips").addEventListener("click",()=>show("clips"));
  $("generate-clips").addEventListener("click",()=>act(()=>enqueue("clip",[...state.selection])));
  for(const action of ["pause","resume","abandon"])$(action).addEventListener("click",()=>act(async()=>{const data=await request(`${api}/projects/${state.project.id}/control/${action}`,{});apply(data.project);}));
  $("export").addEventListener("click",()=>act(async()=>{const response=await fetch(`${api}/projects/${state.project.id}/export`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({version:state.project.version,ids:[...state.selection]})});if(!response.ok){const data=await response.json();throw new Error(data.detail||"Export impossible.");}const url=URL.createObjectURL(await response.blob()), a=element("a");a.href=url;a.download="recette_clips.zip";a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);message("Clips exportés dans l’ordre du découpage.");}));
  $("source-close").addEventListener("click",()=>$("source-dialog").close());$("lightbox-close").addEventListener("click",()=>$("lightbox").close());
  for(const id of ["source-dialog","lightbox"])$(id).addEventListener("click",e=>{if(e.target===$(id))$(id).close();});
  document.querySelector('[data-lab-view="recipes"]')?.addEventListener("click",()=>act(initialize));
  new MutationObserver(()=>{if(root.hidden)clearTimeout(state.timer);else if(!state.initialized)act(initialize);else{poll();schedule();}}).observe(root,{attributes:true,attributeFilter:["hidden"]});
  window.addEventListener("beforeunload",e=>{clearTimeout(state.timer);if(state.dirty){e.preventDefault();e.returnValue="";}});
  window.PanelForgeRecipes=Object.freeze({
    open:async(id=null)=>act(async()=>{window.PanelForgeLabNavigation?.switchView("recipes");await initialize();if(id){if(state.dirty)await save();await load(id);}}),
    fromImage:async(assetId,name)=>act(async()=>{window.PanelForgeLabNavigation?.switchView("recipes");await initialize();await fresh();$("name").value=(name||"Nouvelle recette").slice(0,120);await ensure();await chooseMaster(assetId);show("universe");}),
  });
  if(!root.hidden)act(initialize);
})();
