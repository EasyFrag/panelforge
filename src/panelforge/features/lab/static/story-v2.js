(() => {
  "use strict";
  const root = document.getElementById("story-v2-workspace"); if (!root) return;
  const $ = id => document.getElementById(`sv2-${id}`);
  const state = {project:null, script:null, dirty:false, busy:false, tab:"scenario", selection:new Set(), edit:null, ref:null, epoch:0, loaded:false, toneSupported:false};
  const active = new Set(["queued","writing","reviewing","repairing","polishing","references","producing"]);
  const statusNames = {draft:"Brouillon",queued:"Écriture en attente",writing:"Écriture",reviewing:"Relecture",repairing:"Correction ciblée",polishing:"Retouche des dialogues",awaiting_review:"À relire",references_ready:"Références à préparer",references:"Préparation des références",producing:"Production vidéo",prepared:"Dans le bac Préparation",complete:"Terminé",paused:"En pause",failed:"À reprendre",preparation:"Prêt à lancer",succeeded:"Terminé",cancelled:"Annulé",active:"En cours"};
  const fields = ["writing-version","tone-profile","idea","universe","style","duration","scene-duration","mode","language","writer-model","reader-model","final-review-enabled","polish-enabled","polish-model"];
  const profileFields = ["universe","style"];
  const uid = () => globalThis.crypto?.randomUUID?.() || `sv2-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  const node = (tag,text,cls) => {const e=document.createElement(tag); if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
  const button = (text,fn) => {const b=node("button",text);b.type="button";b.addEventListener("click",fn);return b;};
  const json = value => ({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
  async function request(url,options={}) {const r=await fetch(url,options);let data;try{data=await r.json();}catch(_){throw Error(`Erreur HTTP ${r.status}`);}if(!r.ok)throw Error(typeof data.detail==="string"?data.detail:Array.isArray(data.detail)?data.detail.slice(0,3).map(x=>x.msg||String(x)).join(" · "):"La requête a échoué");return data;}
  const api = path => `/api/stories-v2/projects${state.project?"/"+encodeURIComponent(state.project.id):""}${path}`;
  const asset = id => `/api/assets/${encodeURIComponent(id)}/content`;
  function message(text,error=false){$("message").textContent=text||"";$("message").classList.toggle("error",error);}
  function running(){return !!state.project&&active.has(state.project.status);}
  const preferencesKey="panelforge.story-v2.last-settings.v3";
  const setup=window.PanelForgeStoryV2Settings.mount({request,onChange(){changedSettings();},onState(){controls();}});
  function rememberSettings(){
    try {const value=settings();delete value.idea;state.lastSettings=structuredClone(value);localStorage.setItem(preferencesKey,JSON.stringify(value));}catch(_){}
  }
  function profileValue(id){return $(id).value==="__custom__"?$(id+"-custom").value:$(id).value;}
  function paintProfile(id,value){
    const select=$(id),custom=$(id+"-custom");
    if(value!==undefined){
      const preset=[...select.options].some(o=>o.value!=="__custom__"&&o.value===value);
      select.value=preset?value:"__custom__";custom.value=preset?"":value;
    }
    const personalized=select.value==="__custom__";
    $(id+"-custom-field").hidden=!personalized;custom.required=personalized;
    custom.disabled=!personalized||state.busy||running();
  }
  function changedSettings(){profileFields.forEach(id=>paintProfile(id));rememberSettings();if(state.project)dirty();else modeHelp();}
  function controls(){
    const locked=state.busy||running();
    $("form").querySelectorAll("input,textarea,select").forEach(e=>e.disabled=locked);
    $("create").hidden=!!state.project;$("create").disabled=state.busy||setup.busy;
    $("save").hidden=!state.project;$("save").disabled=locked||setup.busy||!state.dirty;
    $("pause").hidden=!running();$("pause").disabled=state.busy||!!state.project?.pause_requested;
    $("resume").hidden=!["paused","failed"].includes(state.project?.status);$("resume").disabled=state.busy;
    const pendingTiming=needsTimingRewrite();
    $("approve").disabled=locked||setup.busy||!state.script||pendingTiming;
    $("feedback").required=!pendingTiming;
    $("revise").textContent=pendingTiming?"Actualiser le découpage":"Retravailler";
    $("revise").disabled=locked||!state.project;$("target").disabled=locked;
    $("produce").disabled=locked||state.dirty||!state.project?.approved||!state.project?.episode?.references.every(r=>r.image_asset_id)||!!state.project?.factory_ids?.length;
    $("generate").disabled=locked||state.dirty||!state.project?.approved||!state.selection.size;
    $("status").textContent=state.project?(statusNames[state.project.status]||state.project.status)+(state.project.pause_requested?" · pause demandée":""):"";
    $("ref-open-lab").disabled=!state.ref?.krea_project_id&&!state.ref?.story_v2_edit?.project_id;
    $("ref-save").disabled=locked;$("ref-upload").disabled=locked;
    $("new").disabled=state.busy;$("projects").disabled=state.busy;
    $("cancel-refs").hidden=!state.project?.episode?.reference_batch||!["running","rendering"].includes(state.project.episode.reference_batch.status);
    root.querySelectorAll("[data-sv2-editable]").forEach(b=>b.disabled=locked||b.dataset.sv2Retained==="1");
    root.querySelectorAll("[data-sv2-select-image]").forEach(b=>b.disabled=state.busy||b.dataset.sv2Retained==="1");
    root.querySelectorAll("[data-sv2-thumbnail-retry]").forEach(b=>b.disabled=locked||state.dirty||state.project?.episode?.references.some(r=>!r.story_v2_state&&!r.image_asset_id));
    $("writing-version").disabled=locked||!!state.project;
    $("writing-version").title=state.project?"Version conservée pour cette histoire. Nouvelle histoire pour comparer.":"";
    $("tone-profile").disabled=locked||!state.toneSupported;
    $("tone-profile").title=state.toneSupported?"Sketch provocateur : hook fort, langage cru, répartie et fin marquante.":"Disponible après le prochain démarrage du backend.";
    profileFields.forEach(id=>paintProfile(id));
    setup.setDisabled(locked);
    modeHelp();drawProgress();
  }
  function modeHelp(){$("polish-model").disabled=state.busy||running()||!$("polish-enabled").checked;$("duration").max=String(Math.min(180,(sceneDuration()||15)*18));$("polish-model-field").hidden=!$("polish-enabled").checked;const automatic=$("mode").value==="automatic";$("mode-help").textContent=automatic?"Automatique : scénario, références et miniature, puis envoi au bac Préparation. Les prompts et les vidéos se lancent dans l’usine.":"Manuel : relis le scénario, choisis les références, puis envoie les scènes au bac Préparation.";$("create").textContent=automatic?"Préparer l’histoire":"Écrire le scénario";}
  function sceneDuration(){return $("scene-duration").value===""?null:Number($("scene-duration").value);}
  function needsTimingRewrite(){return !!state.script&&(!!state.project?.timing_pending||Number($("duration").value)!==state.project.settings.duration||sceneDuration()!==(state.project.settings.scene_duration??null));}
  function settings(){
    const value={...Object.fromEntries(fields.map(k=>[k.replaceAll("-","_"),$(k).type==="checkbox"?$(k).checked:k==="duration"?Number($(k).value):k==="scene-duration"?sceneDuration():profileFields.includes(k)?profileValue(k):$(k).value])),...setup.read()};
    if(!state.toneSupported)delete value.tone_profile;
    return value;
  }
  function drawProgress(){
    const p=state.project?.progress,box=$("progress");box.hidden=!p;
    if(!p)return;
    const model=(p.model||"").split("::").pop().split("/").pop();
    const short=/gemma[- ]?4/i.test(model)?"Gemma 4":model.replace(/-GGUF$/i,"");
    const status=p.status==="running"?"":p.status==="succeeded"?" · terminé":p.status==="interrupted"?" · interrompu":" · erreur";
    const label=`Appel ${p.index}/${p.total} · ${p.label} · ${short}${status}`;
    if($("progress-label").textContent!==label)$("progress-label").textContent=label;
    const elapsed=p.status==="running"?(Date.now()-Date.parse(p.started_at))/1000:p.elapsed_seconds||0;
    const seconds=Math.max(0,Math.floor(Number.isFinite(elapsed)?elapsed:0));
    $("progress-time").textContent=` · ${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;
    box.title=`${p.model} — Temps écoulé de cet appel, attente comprise.`;
  }
  function option(select,value,label){if(![...select.options].some(o=>o.value===value))select.add(new Option(label||value,value));}
  function fillSettings(value){value={writing_version:"2.0",tone_profile:"from_idea",...value};for(const k of fields){const e=$(k),v=value[k.replaceAll("-","_")];if(profileFields.includes(k)){paintProfile(k,String(v??""));continue;}if(v==null){if(k==="scene-duration")e.value="";continue;}if(e.tagName==="SELECT")option(e,String(v));if(e.type==="checkbox")e.checked=v;else e.value=v;}setup.fill(value);modeHelp();}
  function selectTab(tab){state.tab=tab;for(const name of ["scenario","references","videos"])$(name).hidden=name!==tab;root.querySelectorAll("[data-sv2-tab]").forEach(b=>b.classList.toggle("active",b.dataset.sv2Tab===tab));}
  async function action(fn){if(state.busy)return;state.busy=true;controls();try{await fn();}catch(e){message(e.message,true);}finally{state.busy=false;controls();}}
  function apply(project){const changed=state.project?.episode_id!==project.episode_id;state.project=project;state.script=project.script?structuredClone(project.script):null;state.dirty=false;if(changed)state.selection=new Set((project.episode?.references||[]).filter(r=>!r.image_asset_id).map(r=>r.id));fillSettings(project.settings);try{localStorage.setItem("panelforge.story-v2.current",project.id);}catch(_){}draw();}
  async function load(id){const token=++state.epoch;const data=await request(`/api/stories-v2/projects/${encodeURIComponent(id)}`);if(token!==state.epoch)return;apply(data.project);$("brief").open=!data.project.script;$("projects").value=id;}
  async function catalog(){const data=await request("/api/stories-v2/projects");const current=state.project?.id||"";$("projects").replaceChildren(new Option("Ouvrir une histoire…",""),...data.projects.map(p=>new Option(p.title,p.id)));$("projects").value=current;}
  async function save(){if(!state.project||!state.dirty)return;rememberSettings();const data=await request(api(""),{...json({version:state.project.version,settings:settings(),script:state.script}),method:"PUT"});apply(data.project);}
  async function command(path,body={}){const data=await request(api(path),json({version:state.project.version,...body}));apply(data.project);}
  function draw(){
    const p=state.project,s=state.script;$("reader").hidden=!s;$("empty").hidden=!!s;
    if(p?.error)message(p.error,true);else message(state.dirty?"Modifications à enregistrer.":p?.timing_pending?"Nouvelle durée enregistrée. Clique sur Actualiser le découpage pour adapter le scénario.":"");
    $("sequences").replaceChildren();$("review").replaceChildren();$("review").hidden=!p?.review?.issues?.length;
    for(const issue of p?.review?.issues||[])$("review").append(node("p",issue));
    if(s){
      $("title").textContent=s.title;$("summary").textContent=s.summary.join(" ");$("timing").textContent=`${s.sequences.length} séquences · ${s.sequences.reduce((a,q)=>a+q.duration,0)} s`;
      const names=Object.fromEntries(s.characters.map(c=>[c.id,c.name]));
      const target=$("target").value;$("target").replaceChildren(new Option("Toute l’histoire",""),...s.sequences.map((q,i)=>new Option(`${i+1} · ${q.title}`,q.id)));$("target").value=target;
      for(const [i,q] of s.sequences.entries()){
        const card=node("article",null,"sv2-sequence"),head=node("div",null,"sv2-heading");head.append(node("h3",`${i+1} · ${q.title}`),node("small",`${q.duration} s`,"muted"));
        const edit=button("Modifier",()=>editSequence(q.id));edit.dataset.sv2Editable="1";edit.disabled=state.busy||running();head.append(edit);card.append(head,node("p",q.action),node("p",`Intention : ${q.intention}`,"sv2-intention"));
        for(const d of q.dialogue){const line=node("div",null,"sv2-dialogue");line.append(node("strong",`${names[d.speaker_id]}${d.delivery!=="spoken"?" · "+({off_screen:"hors champ",thought:"pensée",voice_over:"voix off",mediated:"à distance"}[d.delivery]||d.delivery):""} : `),document.createTextNode(d.text));card.append(line);}
        if(!q.dialogue.length)card.append(node("small","Sans dialogue","muted"));$("sequences").append(card);
      }
    }
    $("history").replaceChildren();
    for(const [index,h] of (p?.history||[]).entries()){const b=button(`${index+1} · ${h.reason} · ${new Date(h.at).toLocaleString()} — reprendre`,()=>action(()=>command("/restore",{index})));b.disabled=running()||state.dirty;$("history").append(b);}
    $("history-wrap").hidden=!p?.history?.length;
    drawReferences();drawVideos();controls();
  }
  function preview(id,name){const img=node("img");img.src=asset(id);img.alt=name;img.loading="lazy";img.tabIndex=0;const open=()=>{$("large-image").src=img.src;$("large-image").alt=name;$("image-viewer").showModal();};img.addEventListener("click",open);img.addEventListener("keydown",e=>{if(e.key==="Enter")open();});return img;}
  function drawReferences(){
    const ep=state.project?.episode,host=$("ref-list");host.replaceChildren();$("ref-empty").hidden=!!ep;
    const batch=ep?.reference_batch;$("ref-progress").textContent=ep?`${ep.references.filter(r=>r.image_asset_id).length}/${ep.references.length} images retenues${batch?" · "+batch.phase:""}`:"";
    for(const r of ep?.references||[]){
      const card=node("article",null,"sv2-ref-card"),label=node("label",null,"sv2-check"),check=node("input");check.type="checkbox";check.checked=state.selection.has(r.id);check.addEventListener("change",()=>{check.checked?state.selection.add(r.id):state.selection.delete(r.id);controls();});label.append(check,document.createTextNode(r.name));card.append(label);
      const item=batch?.items?.find(i=>i.reference_id===r.id),edit=r.story_v2_edit,id=r.image_asset_id||edit?.output_asset_id||item?.output_asset_id;
      card.append(id?preview(id,r.name):node("div","Image à préparer","sv2-placeholder"));
      card.append(node("p",r.image_asset_id?"Image retenue":edit?({queued:"Prompt en attente",running:"En cours",succeeded:"Image à choisir",failed:"À reprendre"}[edit.status]||"En préparation"):item?.phase||"Fiche disponible","muted"));
      const open=button("Ouvrir la fiche",()=>action(()=>openReference(r.id)));card.append(open);
      const proposed=edit?.output_asset_id||item?.output_asset_id;
      if(proposed&&r.image_asset_id!==proposed){const use=button("Retenir cette image",()=>action(async()=>{await selectImage(r,proposed);await refresh();}));use.dataset.sv2SelectImage="1";use.disabled=state.busy;card.append(use);}
      host.append(card);
    }
    const thumb=ep?.story_v2_thumbnail,box=$("thumbnail-card");box.replaceChildren();box.hidden=!ep||!state.project.settings.images.thumbnail;
    if(!box.hidden){const card=node("article",null,"sv2-ref-card");card.append(node("h3","Miniature"));const id=thumb?.image_asset_id||thumb?.story_v2_edit?.output_asset_id;
      card.append(id?preview(id,"Miniature de l’histoire"):node("p",thumb?.story_v2_edit?"Miniature en préparation…":"Après les images de référence.","muted"));
      if(thumb?.story_v2_edit?.reference_asset_ids)card.append(node("small",`${thumb.story_v2_edit.reference_asset_ids.length} références · ${thumb.story_v2_edit.engine==="minimax"?"MiniMax":"Qwen"}`,"muted"));
      const retry=button(id?"Refaire la miniature":"Préparer la miniature",()=>action(()=>command("/references",{ids:[],command:uid()})));
      retry.dataset.sv2ThumbnailRetry="1";retry.disabled=running()||state.busy||state.dirty||ep.references.some(r=>!r.story_v2_state&&!r.image_asset_id);card.append(retry);box.append(card);
    }
  }
  function drawVideos(){const host=$("video-list");host.replaceChildren();const rows=state.project?.videos||[];for(const id of state.project?.factory_ids||[]){const r=rows.find(v=>v.id===id);if(!r)continue;const card=node("article",null,"sv2-ref-card");card.append(node("h3",r.name),node("p",statusNames[r.status]||r.status));const media=r.steps?.dlss?.output?.asset_id||r.steps?.video?.output?.asset_id;if(media){const v=node("video");v.controls=true;v.preload="metadata";v.src=asset(media);card.append(v);}host.append(card);}if(!rows.length)host.append(node("p","Les scènes seront déposées dans Préparation, sans prompt vidéo rédigé. Les rendus terminés apparaîtront ici.","muted"));$("play-all").disabled=!host.querySelector("video");}
  function dirty(){state.dirty=true;message("Modifications à enregistrer.");controls();}
  function guard(){return !state.dirty||window.confirm("Abandonner les modifications non enregistrées ?");}
  async function refresh(){if(!state.project)return;if(state.dirty)throw Error("Enregistre tes modifications avant d’actualiser.");await load(state.project.id);}
  function lineEditor(line){const row=node("div",null,"sv2-line-edit"),left=node("div"),speaker=node("select"),delivery=node("select"),text=node("textarea");speaker.setAttribute("aria-label","Personnage qui parle");delivery.setAttribute("aria-label","Mode de parole");for(const c of state.script.characters)speaker.add(new Option(c.name,c.id));speaker.value=line.speaker_id;for(const [v,label] of Object.entries({spoken:"Dans la scène",off_screen:"Hors champ",thought:"Pensée",voice_over:"Voix off",mediated:"À distance"}))delivery.add(new Option(label,v));delivery.value=line.delivery||"spoken";text.value=line.text;text.rows=2;text.maxLength=450;text.required=true;text.setAttribute("aria-label","Réplique");left.append(speaker,delivery);row.append(left,text,button("Retirer",()=>row.remove()));row.read=()=>{
      const value={speaker_id:speaker.value,text:text.value,delivery:delivery.value};
      // Keep hidden story cues only while the original line is unchanged.
      return value.speaker_id===line.speaker_id&&value.text===line.text&&value.delivery===(line.delivery||"spoken")?{...line,...value}:value;
    };return row;}
  function editSequence(id){const q=state.script.sequences.find(x=>x.id===id);state.edit=id;$("edit-title").textContent=q.title;for(const k of ["action","intention","setting","duration"])$("edit-"+k).value=q[k];$("edit-dialogues").replaceChildren(...q.dialogue.map(lineEditor));$("edit-error").textContent="";$("editor").showModal();}
  function refApi(r,suffix=""){return `/api/episodes/${encodeURIComponent(state.project.episode_id)}/references/${encodeURIComponent(r.id)}${suffix}`;}
  async function selectImage(r,id){await request(refApi(r,"/select"),json({expected_revision:r.revision,asset_id:id}));}
  async function openReference(id){
    const r=state.project.episode.references.find(x=>x.id===id);state.ref=r;$("ref-title").textContent=r.name;$("ref-description").value=r.description;$("ref-error").textContent="";$("ref-images").replaceChildren();controls();if(!$("ref-editor").open)$("ref-editor").showModal();
    const candidates=new Map((r.images||[]).map(i=>[i.asset_id,i.label||"Image"]));if(r.image_asset_id)candidates.set(r.image_asset_id,"Image retenue");
    const item=state.project.episode.reference_batch?.items?.find(i=>i.reference_id===id);if(item?.output_asset_id)candidates.set(item.output_asset_id,"Dernière proposition");
    if(r.krea_project_id){try{const data=await request(refApi(r,"/project"));for(const a of data.project?.attempts||[])if(a.output_asset_id)candidates.set(a.output_asset_id,"Rendu");}catch(e){$("ref-error").textContent=e.message;}}
    if(state.ref?.id!==id)return;
    for(const [imageId,label] of candidates){const card=node("article",null,"sv2-ref-card");card.append(preview(imageId,r.name));const choose=button(imageId===r.image_asset_id?"Image retenue":"Retenir",()=>action(async()=>{await selectImage(state.ref,imageId);await refresh();await openReference(id);}));choose.dataset.sv2SelectImage="1";choose.dataset.sv2Retained=imageId===r.image_asset_id?"1":"0";choose.disabled=state.busy||imageId===r.image_asset_id;card.append(choose,node("small",label));$("ref-images").append(card);}
  }
  function createCommand(value){
    const key=JSON.stringify(value);let saved;
    try{saved=JSON.parse(sessionStorage.getItem("panelforge.story-v2.pending-create")||"null");}catch(_){}
    if(saved?.key===key)return saved.command;
    const command=uid();try{sessionStorage.setItem("panelforge.story-v2.pending-create",JSON.stringify({key,command}));}catch(_){}
    return command;
  }
  async function initialize(){
    if(state.loaded)return;state.loaded=true;
    const results=await Promise.allSettled([request("/api/stories-v2/preferences"),request("/api/stories/models")]);
    if(results[0].status==="rejected"){state.loaded=false;throw results[0].reason;}
    state.toneSupported=Object.prototype.hasOwnProperty.call(results[0].value.settings,"tone_profile");
    let defaults={scene_duration:10,final_review_enabled:false,polish_enabled:false,polish_model:"local::unsloth/gemma-4-31B-it-qat-GGUF",...results[0].value.settings};
    try{
      let local=JSON.parse(localStorage.getItem(preferencesKey)||"null");
      if(!local){
        const previous=JSON.parse(localStorage.getItem("panelforge.story-v2.last-settings.v2")||"null");
        if(previous)local=Object.fromEntries(fields.filter(k=>k!=="idea").map(k=>k.replaceAll("-","_")).filter(k=>k in previous).map(k=>[k,previous[k]]));
      }
      if(local)defaults={...defaults,...local,images:{...defaults.images,...local.images},video:{...defaults.video,...local.video}};
    }catch(_){}
    defaults.scene_duration??=10;
    defaults.writing_version="2.1";
    state.lastSettings=structuredClone(defaults);
    const models=results[1].status==="fulfilled"?results[1].value.models:[];
    for(const id of ["writer-model","reader-model","polish-model"]){$(id).replaceChildren(...models.map(m=>new Option(m.label,m.id)));}
    await setup.initialize(defaults,models);fillSettings(defaults);
    await catalog();let saved;try{saved=localStorage.getItem("panelforge.story-v2.current");}catch(_){}if(saved&&[...$("projects").options].some(o=>o.value===saved))await load(saved);controls();
  }
  root.querySelectorAll("[data-sv2-tab]").forEach(b=>b.addEventListener("click",()=>selectTab(b.dataset.sv2Tab)));
  $("form").addEventListener("input",changedSettings);
  $("form").addEventListener("change",changedSettings);
  $("form").addEventListener("invalid",e=>{for(let n=e.target.parentElement;n&&n!==$("form");n=n.parentElement)if(n.tagName==="DETAILS")n.open=true;},true);
  $("form").addEventListener("submit",e=>{e.preventDefault();action(async()=>{if(setup.busy||!$("form").reportValidity())return;rememberSettings();const data=await request("/api/stories-v2/projects",json({command:createCommand(settings()),settings:settings()}));apply(data.project);$("brief").open=false;await catalog();});});
  $("save").addEventListener("click",()=>action(save));
  $("approve").addEventListener("click",()=>action(async()=>{await save();await command("/approve");selectTab("references");}));
  $("feedback-form").addEventListener("submit",e=>{e.preventDefault();action(async()=>{await save();await command("/revise",{feedback:$("feedback").value.trim()||(state.project.timing_pending?"Adapte le découpage à la durée par scène choisie, en conservant les informations, les événements et la durée totale.":""),sequence_id:state.project.timing_pending?null:$("target").value||null});$("feedback").value="";});});
  $("projects").addEventListener("change",()=>{const id=$("projects").value;if(id&&guard())action(()=>load(id));else $("projects").value=state.project?.id||"";});
  $("new").addEventListener("click",()=>{if(!guard())return;++state.epoch;try{sessionStorage.removeItem("panelforge.story-v2.pending-create");}catch(_){}state.project=null;state.script=null;state.dirty=false;state.selection.clear();if(state.lastSettings)fillSettings({...state.lastSettings,writing_version:"2.1",scene_duration:state.lastSettings.scene_duration??10,idea:""});$("idea").value="";$("projects").value="";$("brief").open=true;$("idea-settings").open=true;selectTab("scenario");draw();});
  $("refresh").addEventListener("click",()=>action(async()=>{await refresh();await catalog();}));
  $("pause").addEventListener("click",()=>action(async()=>{const d=await request(api("/pause"),json({}));apply(d.project);}));
  $("resume").addEventListener("click",()=>action(()=>command("/resume")));
  $("generate").addEventListener("click",()=>action(()=>command("/references",{ids:[...state.selection],command:uid()})));
  $("select-all").addEventListener("click",()=>{const refs=state.project?.episode?.references||[];state.selection=state.selection.size===refs.length?new Set():new Set(refs.map(r=>r.id));drawReferences();controls();});
  $("cancel-refs").addEventListener("click",()=>action(async()=>{const ep=state.project.episode;await request(`/api/episodes/${ep.episode_id}/reference-batches/${ep.reference_batch.batch_id}/cancel`,json({}));await refresh();}));
  $("produce").addEventListener("click",()=>action(async()=>{await command("/produce");message("Scènes envoyées au bac Préparation. Lance les étapes depuis l’usine.");}));
  $("factory").addEventListener("click",()=>{window.PanelForgeLabNavigation?.switchView("video-factory");document.querySelector('[data-lab-view="video-factory"]')?.click();});
  $("play-all").addEventListener("click",()=>{const videos=[...$("video-list").querySelectorAll("video")];const play=i=>{if(!videos[i])return;videos[i].currentTime=0;videos[i].scrollIntoView({block:"center",behavior:"smooth"});videos[i].onended=()=>play(i+1);videos[i].play().catch(e=>message(e.message,true));};play(0);});
  $("edit-close").addEventListener("click",()=>$("editor").close());
  $("add-line").addEventListener("click",()=>{if($("edit-dialogues").children.length<6)$("edit-dialogues").append(lineEditor({speaker_id:state.script.characters[0].id,text:"",delivery:"spoken"}));});
  $("edit-form").addEventListener("submit",e=>{e.preventDefault();const q=state.script.sequences.find(s=>s.id===state.edit);
    const stagingChanged=["action","intention","setting"].some(k=>q[k]!==$("edit-"+k).value);
    q.action=$("edit-action").value;q.intention=$("edit-intention").value;q.setting=$("edit-setting").value;q.duration=Number($("edit-duration").value);q.dialogue=[...$("edit-dialogues").children].map(r=>r.read());
    if(stagingChanged)for(const line of q.dialogue)delete line.address_cue;
    $("editor").close();dirty();draw();});
  $("ref-close").addEventListener("click",()=>{$("ref-editor").close();state.ref=null;});
  $("ref-save").addEventListener("click",()=>action(async()=>{const r=state.ref;await request(refApi(r),{...json({expected_revision:r.revision,description:$("ref-description").value,prompt:r.prompt,model_id:r.model_id,render_settings:r.render_settings,inherit_image_settings:r.inherit_image_settings}),method:"PUT"});await refresh();await openReference(r.id);}));
  $("ref-upload").addEventListener("change",()=>action(async()=>{const r=state.ref,file=$("ref-upload").files[0];if(!file)return;const data=new FormData();data.set("expected_revision",String(r.revision));data.set("image",file);await request(refApi(r,"/image"),{method:"POST",body:data});$("ref-upload").value="";await refresh();await openReference(r.id);}));
  $("ref-open-lab").addEventListener("click",()=>{const r=state.ref;if(!r)return;$("ref-editor").close();if(r.story_v2_edit){const e=r.story_v2_edit;window[e.engine==="minimax"?"PanelForgeMinimaxEdit":"PanelForgeQwenEdit"]?.open(e.project_id);}else if(r.krea_project_id)window.PanelForgeKrea2AssistedLab?.open(r.krea_project_id);});
  $("image-close").addEventListener("click",()=>$("image-viewer").close());
  document.querySelector('[data-lab-view="story-v2"]')?.addEventListener("click",()=>action(initialize));
  const observer=new MutationObserver(()=>{if(!root.hidden&&!state.loaded)action(initialize);});observer.observe(root,{attributes:true,attributeFilter:["hidden"]});
  window.addEventListener("beforeunload",e=>{if(state.dirty){e.preventDefault();e.returnValue="";}});
  setInterval(()=>{if(!root.hidden)drawProgress();},1000);
  const displayKey=p=>JSON.stringify([p.version,p.episode?.updated_at,p.episode?.story_v2_thumbnail,(p.videos||[]).map(v=>[v.id,v.revision,v.status])]);
  setInterval(async()=>{
    if(root.hidden||state.polling||state.busy||state.dirty||!state.project||$("editor").open||$("ref-editor").open||[...$("video-list").querySelectorAll("video")].some(v=>!v.paused))return;
    const identity=state.project.id,epoch=state.epoch;state.polling=true;
    try{
      const data=await request(`/api/stories-v2/projects/${encodeURIComponent(identity)}`);
      if(state.epoch!==epoch||state.project?.id!==identity||state.busy||state.dirty||$("editor").open||$("ref-editor").open)return;
      if(displayKey(data.project)!==displayKey(state.project))apply(data.project);
    }catch(e){if(state.epoch===epoch&&!state.busy)message(e.message,true);}finally{state.polling=false;}
  },3500);
  window.PanelForgeStoryV2 = Object.freeze({async open(id){if(!guard())return;window.PanelForgeLabNavigation?.switchView("story-v2");await initialize();await load(id);selectTab("videos");}});
  if(!root.hidden)action(initialize);
})();
