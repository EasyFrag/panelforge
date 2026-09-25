/* Standalone design prototype. No backend, network requests or real generation. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const lipsPrompt = "Gros plan sur les lèvres. Un mouvement lent et naturel, une caméra stable. Un seul plan continu. Rejoindre l’image de fin en conservant l’identité, la lumière et les textures.";
  const defaults = {mode:"H3", plans:1, duration:8, ratio:"9:16", megapixels:0.9, steps:9, seed:0, strength:0.6, second:0.2, music:false, social:false, language:"", variants:3};
  const presets = {
    source:{label:"Réglages source"},
    lips:{label:"Lèvres", settings:{...defaults,prompt:lipsPrompt},roles:["last_frame"]},
    first:{label:"Image de départ",settings:{...defaults,prompt:"Animer la scène à partir de l’image, avec un mouvement naturel et une caméra stable."},roles:["first_frame"]},
    ref:{label:"Références",settings:{...defaults,mode:"REF2V",prompt:"Créer un plan continu en préservant l’identité du sujet et le décor de référence."},roles:["subject","environment"]}
  };
  let rows, selected, filter = "all", paused = false, workers, events, nextId = 7, toastTimer;
  function image(name,role="last_frame"){return {name,role};}
  function item(id,name,kind,extra={}){
    const row={id,name,kind,...copy(defaults),prompt:lipsPrompt,preset:"lips",images:[image(`image-${id}.png`)],enqueued:false,done:false,cursor:0,stepsList:[],...extra};
    row.sourceSettings={};
    for(const field of [...Object.keys(defaults),"prompt"])row.sourceSettings[field]=row[field];
    row.sourceRoles=row.images.map((img)=>img.role);
    return row;
  }
  function reset(){
    rows = [
      item(1,"Le jardin des secrets · Ép. 03","story",{preset:"source",mode:"REF2V",duration:24,scenes:["Le rendez-vous","La découverte","Le retour"],images:[image("Personnage principal","subject"),image("Le jardin","environment")],prompt:"Prompts des 3 scènes préparés dans Histoires."}),
      item(2,"Lèvres · lumière dorée","lips"),
      item(3,"Lèvres · rose poudré","lips",{preset:"source",prompt:""}),
      item(4,"Le petit voyage · Ép. 01","story",{preset:"source",mode:"REF2V",duration:16,scenes:["Le départ","L’arrivée"],images:[image("Personnage principal","subject")],prompt:"Prompts des 2 scènes préparés dans Histoires."}),
      item(5,"Portrait · atelier","ref",{preset:"ref",mode:"REF2V",prompt:presets.ref.settings.prompt,images:[image("Portrait","subject"),image("Atelier","environment")]}),
      item(6,"Lèvres · lumière de studio","lips",{done:true})
    ];
    selected = 2; workers = {remote:null,local:null}; events = []; paused = false; filter = "all"; render();
  }
  function current(){return rows.find((row)=>row.id===selected);}
  function locked(row){return row.enqueued || row.done;}
  function problem(row){
    if(!row.prompt.trim()) return "Prompt à renseigner";
    if(!row.images.length) return "Image manquante";
    if(row.mode==="H3" && row.images.some((img)=>!["first_frame","last_frame"].includes(img.role))) return "Rôle incompatible avec H3";
    if(row.mode==="H3" && new Set(row.images.map((img)=>img.role)).size!==row.images.length) return "Un seul visuel par frame";
    if(row.mode==="REF2V" && !row.images.some((img)=>["subject","first_frame"].includes(img.role))) return "Référence sujet ou départ manquante";
    if(row.social && !row.language) return "Langue Instagram à choisir";
    return "";
  }
  function running(row){return Object.values(workers).some((worker)=>worker?.id===row.id);}
  function status(row){
    if(row.done) return ["done","✓ Terminée","Vidéo disponible"];
    if(problem(row)) return ["attention","À compléter",problem(row)];
    if(running(row)) return ["running","● En cours",row.stepsList[row.cursor].label];
    if(row.enqueued) return ["waiting",paused?"En pause":"En attente",paused?"Reprise manuelle":`Attend ${row.stepsList[row.cursor].lane==="remote"?"le serveur":"le local"}`];
    return ["ready","✓ Prête",row.kind==="story"?`${row.scenes.length} scènes configurées`:"Tout est renseigné"];
  }
  function thumb(row){
    if(row.kind==="story") return '<span class="thumb story" aria-hidden="true"><svg viewBox="0 0 44 56"><path fill="#c5cfae" d="M0 0h44v56H0z"/><circle cx="33" cy="12" r="7" fill="#f6e2a4"/><path d="M0 36 16 17 40 56H0z" fill="#7e9976"/><path d="m20 56 15-28 9 9v19" fill="#456f56"/><path d="m15 56 5-22 5 22" fill="#e4cb9f"/></svg></span>';
    if(row.kind==="ref") return '<span class="thumb ref" aria-hidden="true"><svg viewBox="0 0 44 56"><path d="M0 0h44v56H0z" fill="#d2dcda"/><circle cx="22" cy="20" r="9" fill="#acbdb4"/><path d="M6 56V43a16 16 0 0 1 32 0v13" fill="#718e81"/><path d="M14 15q8-18 17 0" fill="#526e64"/></svg></span>';
    return '<span class="thumb" aria-hidden="true"><svg viewBox="0 0 44 56"><path fill="#ead3cb" d="M0 0h44v56H0z"/><path d="M3 29q12-17 19-9 7-8 19 9-13 18-24 6z" fill="#b26f70"/><path d="M3 29q12-5 19-2 8-3 19 2-19 6-38 0" fill="#794447"/><path d="M12 32q11 6 21-1" stroke="#df9d94" stroke-width="2" fill="none"/></svg></span>';
  }
  function options(row){return Object.entries(presets).map(([key,preset])=>`<option value="${key}" ${row.preset===key?"selected":""}>${esc(preset.label)}</option>`).join("");}
  function displayRows(){
    const visible=rows.filter((row)=>filter==="all" || status(row)[0]===filter);
    $("rows").innerHTML=visible.map((row)=>{
      const index=rows.indexOf(row),[state,label,sub]=status(row);
      return `<tr class="${selected===row.id?"selected":""}" data-id="${row.id}"><td><div class="order"><span>${String(index+1).padStart(2,"0")}</span><div><button data-move="-1" aria-label="Monter ${esc(row.name)}" ${index===0?"disabled":""}>↑</button><button data-move="1" aria-label="Descendre ${esc(row.name)}" ${index===rows.length-1?"disabled":""}>↓</button></div></div></td><td><div class="video-cell">${thumb(row)}<div><button class="title-button" data-open aria-pressed="${selected===row.id}">${esc(row.name)}</button><small>${row.kind==="story"?`Histoire · ${row.scenes.length} scènes`:`Image Lab · ${row.mode} · ${row.duration} s`}${row.custom?" · modifié":""}</small></div></div></td><td><select data-preset aria-label="Preset de ${esc(row.name)}" ${locked(row)||row.kind==="story"?"disabled":""}>${options(row)}</select></td><td><span class="badge ${state}">${label}</span><small class="status-sub">${esc(sub)}</small></td><td><button class="ig-button ${row.social?"on":""}" data-social aria-label="Texte Instagram pour ${esc(row.name)}" aria-pressed="${row.social}" ${locked(row)?"disabled":""}>${row.social?`${row.variants} · ${row.language?row.language.toUpperCase():"?"}`:"Off"}</button></td></tr>`;
    }).join("");
    $("empty").hidden=visible.length>0;
    $("count").textContent=`${rows.length} vidéos`;
    document.querySelectorAll("[data-filter]").forEach((button)=>button.classList.toggle("active",button.dataset.filter===filter));
  }
  function roleOptions(img,row){
    const roles=row.mode==="H3"?{first_frame:"Première frame",last_frame:"Dernière frame"}:{subject:"Sujet / identité",environment:"Décor",style:"Style",first_frame:"Première frame",last_frame:"Dernière frame"};
    if(!roles[img.role]) roles[img.role]="Rôle à réattribuer";
    return Object.entries(roles).map(([key,label])=>`<option value="${key}" ${img.role===key?"selected":""}>${label}</option>`).join("");
  }
  function field(label,name,value,type="number",attrs=""){
    return `<label class="field">${label}<input data-field="${name}" type="${type}" value="${esc(value)}" ${attrs} ${locked(current()) || (current().kind==="story" && name!=="variants")?"disabled":""}></label>`;
  }
  function inspector(){
    const row=current(),[state,label]=status(row),disabled=locked(row)?"disabled":"";
    const story=row.kind==="story";
    $("inspector").innerHTML=`
      <div class="inspector-head"><div class="inspector-heading"><div class="eyebrow">VIDÉO ${String(rows.indexOf(row)+1).padStart(2,"0")}</div><span class="badge ${state}">${label}</span></div><h2>${esc(row.name)}</h2><p>${story?"Réglages et références hérités de l’histoire.":"Une image, un preset, une vidéo."}</p></div>
      <div class="inspector-body">
        ${story?`<section><div class="section-label"><h3>Scènes de l’épisode</h3><small>${row.duration} s au total</small></div><ol class="scene-list">${row.scenes.map((name,index)=>`<li><span>0${index+1}</span><div>${esc(name)}<small>Références et prompt conservés</small></div><b>✓</b></li>`).join("")}</ol><p class="helper">Les scènes sont rendues puis assemblées en une seule vidéo. Le détail se retrouve dans la fabrication de l’histoire.</p></section>`:`<section><div class="section-label"><h3>Preset de lancement</h3><button class="text-button" id="save-preset" ${disabled}>Enregistrer…</button></div><select id="detail-preset" aria-label="Preset de lancement" ${disabled}>${options(row)}</select><p class="helper">${row.custom?"Réglages personnalisés pour cette vidéo.":row.preset==="lips"?"H3 · image de fin · 1 plan · prompt réutilisable":"Les réglages sont propres à cette vidéo."}</p></section>
        <section><div class="section-label"><h3>Images & rôles</h3><small>${row.images.length} image${row.images.length>1?"s":""}</small></div>${row.images.map((img,index)=>`<div class="source-row">${thumb(row)}<div><strong>${esc(img.name)}</strong><select data-role="${index}" aria-label="Rôle de ${esc(img.name)}" ${disabled}>${roleOptions(img,row)}</select></div><button class="remove" data-remove="${index}" aria-label="Retirer ${esc(img.name)}" ${disabled}>×</button></div>`).join("")}<button id="add-reference" class="text-button" ${disabled}>＋ Associer une image exemple</button></section>
        <section><div class="field-grid"><label class="field">Mode de préparation<select data-field="mode" ${disabled}><option ${row.mode==="H3"?"selected":""}>H3</option><option ${row.mode==="REF2V"?"selected":""}>REF2V</option></select></label>${field("Nombre de plans","plans",row.plans,"number",'min="1" max="8"')}</div><div class="section-label" style="margin-top:16px"><h3>Intention / prompt</h3><small>Modifiable</small></div><textarea data-field="prompt" aria-label="Intention ou prompt" rows="4" ${disabled}>${esc(row.prompt)}</textarea><p class="helper">Le parcours actuel prépare le prompt vidéo automatiquement à partir de cette intention.</p></section>`}
        <section><div class="section-label"><h3>Rendu vidéo</h3><small>${story?"Hérité de l’histoire":"Défauts actuels"}</small></div><div class="recipe-summary"><span>◈</span><div>Bunny + Motion Repair<small>${row.ratio} · ${row.megapixels} MP · ${story?"durée par scène":`${row.duration} s`}</small></div></div><details class="advanced"><summary>Réglages avancés</summary><p class="helper">Valeurs illustratives de la démo. En production : copie des réglages effectifs de la source, puis des valeurs du preset.</p><div class="field-grid">${field(story?"Durée totale (s)":"Durée (s)","duration",row.duration,"number",'min="1" max="120"')}${field("Résolution (MP)","megapixels",row.megapixels,"number",'min="0.1" max="4" step="0.1"')}${field("Steps","steps",row.steps,"number",'min="2" max="100"')}${field("Seed","seed",row.seed,"number",'min="0" step="1"')}${field("Motion Repair · passe 1","strength",row.strength,"number",'min="0" max="1" step="0.05"')}${field("Motion Repair · passe 2","second",row.second,"number",'min="0" max="1" step="0.05"')}</div><label class="toggle-line" style="margin-top:12px"><input data-field="music" type="checkbox" ${row.music?"checked":""} ${disabled||story?"disabled":""}> Musique</label></details></section>
        <section><label class="toggle-line"><input id="social-toggle" type="checkbox" ${row.social?"checked":""} ${disabled}> Préparer le texte Instagram</label><p class="helper">${row.social?"Après la vidéo, automatiquement.":"Désactivé · active-le uniquement si nécessaire."}</p><div class="social-settings" ${row.social?"":"hidden"}><div class="field-grid"><label class="field">Langue<select data-field="language" ${disabled}><option value="">À choisir</option><option value="fr" ${row.language==="fr"?"selected":""}>Français</option><option value="en" ${row.language==="en"?"selected":""}>English</option></select></label>${field("Variantes","variants",row.variants,"number",'min="1" max="6"')}</div><p class="helper"><span class="chip">Gemma 4 · local</span><span class="chip">${row.variants} variantes</span></p><div class="source-note">Vidéo : ${story?"épisode assemblé":"sortie H3 de cette ligne"}, associée automatiquement.</div></div></section>
      </div><div class="inspector-foot"><span class="readiness ${problem(row)?"invalid":""}">${row.done?"✓ Vidéo terminée":row.enqueued?"Réglages figés pour ce lancement":problem(row)?esc(problem(row)):"✓ Tout est renseigné"}</span><button id="duplicate">Dupliquer</button></div>`;
  }
  function machineView(){
    for(const lane of ["remote","local"]){
      const worker=workers[lane],row=worker&&rows.find((r)=>r.id===worker.id);
      $(`${lane}-state`).textContent=row?`#${rows.indexOf(row)+1} · ${row.stepsList[row.cursor].label}`:paused?"En pause":"Disponible";
      $(`${lane}-led`).classList.toggle("busy",Boolean(row));
    }
    const launchable=rows.filter((r)=>!locked(r)&&!problem(r)).length;
    $("launch").textContent=`▶ Lancer les ${launchable} vidéos prêtes`;
    $("launch").disabled=!launchable;
    const unfinished=rows.some((r)=>r.enqueued&&!r.done);
    $("pause").disabled=!unfinished;
    $("pause").textContent=paused?"▶ Reprendre":"Ⅱ Mettre en pause";
    $("step").disabled=!Object.values(workers).some(Boolean);
    $("scheduler-message").textContent=paused?"Les étapes engagées peuvent finir. Aucune nouvelle étape ne démarre avant la reprise.":unfinished?"À chaque étape terminée, on repart du haut de la liste pour chaque machine disponible.":events.length?"Toutes les vidéos lancées sont terminées. Les lignes à compléter restent dans la liste.":"Lance les lignes prêtes pour voir les deux machines travailler ensemble.";
    $("events").innerHTML=events.slice(-5).reverse().map((line)=>`<li>${esc(line)}</li>`).join("");
  }
  function render(){displayRows();inspector();machineView();}
  function toast(message){$("toast").textContent=message;$("toast").classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").classList.remove("show"),3500);}
  function applyPreset(row,key){
    if(locked(row)||row.kind==="story") return;
    if(key==="source"){
      Object.assign(row,copy(row.sourceSettings||{...defaults,prompt:""}));
      row.images.forEach((img,index)=>{img.role=row.sourceRoles[index] || (row.mode==="H3"?"first_frame":"subject");});
    } else {
      Object.assign(row,copy(presets[key].settings));
      row.images.forEach((img,index)=>{img.role=presets[key].roles[index] || (row.mode==="H3"?"first_frame":"subject");});
    }
    row.preset=key;row.custom=false;render();toast(`Preset « ${presets[key].label} » appliqué à cette vidéo.`);
  }
  function buildSteps(row){
    const result=row.kind==="story"?row.scenes.map((_,i)=>({lane:"remote",label:`Scène ${i+1}/${row.scenes.length} · Bunny`})):[{lane:"local",label:`Préparation du prompt ${row.mode}`},{lane:"remote",label:"Rendu Bunny"}];
    if(row.kind==="story")result.push({lane:"local",label:"Assemblage de l’épisode"});
    if(row.social)result.push({lane:"local",label:`Instagram · ${row.variants} variantes ${row.language.toUpperCase()}`});
    return result;
  }
  function schedule(){
    if(paused)return;
    for(const lane of ["remote","local"]){
      if(workers[lane])continue;
      const row=rows.find((r)=>r.enqueued&&!r.done&&!running(r)&&r.stepsList[r.cursor]?.lane===lane);
      if(row){workers[lane]={id:row.id};events.push(`${lane==="remote"?"Serveur":"Local"} → #${rows.indexOf(row)+1} ${row.name} : ${row.stepsList[row.cursor].label}.`);}
    }
  }
  $("rows").addEventListener("click",(event)=>{
    const tr=event.target.closest("tr");if(!tr)return;
    const row=rows.find((r)=>r.id===Number(tr.dataset.id));
    if(event.target.closest("[data-move]")){
      const index=rows.indexOf(row),next=index+Number(event.target.closest("[data-move]").dataset.move);
      if(next<0||next>=rows.length)return;
      [rows[index],rows[next]]=[rows[next],rows[index]];schedule();render();return;
    }
    if(event.target.closest("[data-social]")){
      if(locked(row))return;row.social=!row.social;row.custom=true;selected=row.id;render();return;
    }
    if(!event.target.closest("select")){selected=row.id;render();}
  });
  $("rows").addEventListener("change",(event)=>{if(event.target.matches("[data-preset]")){const row=rows.find((r)=>r.id===Number(event.target.closest("tr").dataset.id));selected=row.id;applyPreset(row,event.target.value);}});
  document.querySelectorAll("[data-filter]").forEach((button)=>button.addEventListener("click",()=>{filter=button.dataset.filter;displayRows();}));
  $("inspector").addEventListener("change",(event)=>{
    const row=current(),target=event.target;if(locked(row))return;
    if(target.id==="detail-preset"){applyPreset(row,target.value);return;}
    if(target.id==="social-toggle"){row.social=target.checked;row.custom=true;render();return;}
    if(target.matches("[data-role]")){row.images[Number(target.dataset.role)].role=target.value;row.custom=true;render();return;}
    if(target.matches("[data-field]")){
      if(!target.checkValidity()){target.reportValidity();target.value=row[target.dataset.field];return;}
      row[target.dataset.field]=target.type==="checkbox"?target.checked:target.type==="number"?Number(target.value):target.value;
      row.custom=true;
      if(["mode","language","variants"].includes(target.dataset.field)){render();return;}
      displayRows();machineView();
      const readiness=$("inspector").querySelector(".readiness");readiness.textContent=problem(row)||"✓ Tout est renseigné";readiness.classList.toggle("invalid",Boolean(problem(row)));
    }
  });
  $("inspector").addEventListener("click",(event)=>{
    const row=current(),button=event.target.closest("button");if(!button)return;
    if(button.id==="duplicate"){
      const next={...copy(row),id:nextId++,name:`${row.name} · copie`,done:false,enqueued:false,cursor:0,stepsList:[]};
      rows.push(next);selected=next.id;filter="all";render();toast("Copie ajoutée à la fin de la liste.");return;
    }
    if(locked(row))return;
    if(button.id==="save-preset"){$("preset-name").value="";$("preset-dialog").showModal();return;}
    if(button.id==="add-reference"){row.images.push(image(`référence-${row.images.length+1}.png`,row.mode==="H3"?"first_frame":"subject"));row.custom=true;render();return;}
    if(button.matches("[data-remove]")){row.images.splice(Number(button.dataset.remove),1);row.custom=true;render();}
  });
  $("preset-form").addEventListener("submit",(event)=>{
    event.preventDefault();const row=current(),name=$("preset-name").value.trim();if(!name)return;
    const key=`custom-${Object.keys(presets).length}`,settings={};
    for(const field of [...Object.keys(defaults),"prompt"])settings[field]=row[field];
    presets[key]={label:name,settings:copy(settings),roles:row.images.map((img)=>img.role)};
    row.preset=key;row.custom=false;$("preset-dialog").close();render();toast("Preset ajouté au menu pour la durée de cette démo.");
  });
  $("cancel-preset").addEventListener("click",()=>$("preset-dialog").close());
  $("add").addEventListener("click",()=>{const id=nextId++;rows.push(item(id,`Image à préparer ${id}`,"lips",{preset:"source",prompt:"",images:[image(`image-${id}.png`,"first_frame")]}));selected=id;filter="all";render();toast("Image exemple reçue depuis Image Lab. Choisis un preset pour la préparer.");});
  $("launch").addEventListener("click",()=>{
    for(const row of rows.filter((r)=>!locked(r)&&!problem(r))){row.enqueued=true;row.stepsList=buildSteps(row);row.cursor=0;}
    schedule();render();toast(paused?"Vidéos ajoutées. Reprends la file pour les lancer.":"Simulation lancée. Utilise « Faire avancer d’une étape ».");
  });
  $("step").addEventListener("click",()=>{
    for(const lane of ["remote","local"]){
      const worker=workers[lane];if(!worker)continue;
      const row=rows.find((r)=>r.id===worker.id);row.cursor++;workers[lane]=null;
      if(row.cursor>=row.stepsList.length){row.done=true;events.push(`✓ ${row.name} : vidéo${row.social?" et textes":""} terminée${row.social?"s":""}.`);}
    }
    schedule();render();
  });
  $("pause").addEventListener("click",()=>{paused=!paused;schedule();render();toast(paused?"Pause des prochains départs. Les calculs engagés peuvent se terminer.":"La file reprend dans l’ordre des lignes.");});
  $("reset").addEventListener("click",()=>{reset();toast("Scénario de démonstration réinitialisé.");});
  reset();
})();
