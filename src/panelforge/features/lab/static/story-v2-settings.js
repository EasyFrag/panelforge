(() => {
  "use strict";
  const copy = v => structuredClone(v);
  const key = v => `${v?.id || v?.recipe_id}@${v?.version}`;
  window.PanelForgeStoryV2Settings = {mount({request, onChange, onState}) {
    const $ = id => document.getElementById(`sv2-${id}`);
    let value = null, imageSpec = {}, videoSpec = null, presets = [], art = null;
    let videoLoad = null, loras = [], disabled = false, loading = false, epoch = 0, artEpoch = 0, searchTimer;
    const notices = {image:"", video:""};
    const llmIds = ["prompt-model", "edit-model", "video-plan-model", "video-prompt-model"];
    const axes = [["audacity","Audace créative"],["scene_life","Vie de la scène"],["camera","Caméra"],["extra_motion","Mouvements additionnels"],["dialogue","Dialogues et réactions"]];
    function set(id, v) {
      const e=$(id); if(e.type==="checkbox") {e.checked=!!v;return;}
      if(e.tagName==="SELECT" && ![...e.options].some(o=>o.value===String(v??""))) e.add(new Option(v||"Par défaut",v??""));
      e.value=v??"";
    }
    function options(id, rows) { const selected=$(id).value; $(id).replaceChildren(...rows.map(r=>new Option(r[1],r[0]))); if(selected)set(id,selected); }
    function note(text, source="image") {notices[source]=text;$("model-note").textContent=Object.values(notices).filter(Boolean).join(" · ");}
    function changed() {summary();onChange();}
    const checkpoint = window.PanelForgeH3Checkpoints?.mount("sv2-video", {request,mode:"ref2va",onChange:changed});
    const videoLoras = window.PanelForgeH3Loras?.mount("sv2-video", {request,onChange:changed});
    for(const [id,label] of axes) {
      const row=document.createElement("label"), input=document.createElement("input"), out=document.createElement("output");
      input.type="range";input.min="0";input.max="3";input.step="1";input.id=`sv2-axis-${id}`;input.value=id==="dialogue"?"1":"3";
      out.id=`sv2-axis-${id}-value`;out.value=input.value;row.append(document.createTextNode(label),input,out);$("creative-axes").append(row);
      input.addEventListener("input",summary);
    }
    function imageLoras() {
      window.PanelForgeKrea2ResourceUi?.renderLoraStack($("image-loras"), {resources:imageSpec.loras||[], selections:loras,
        maximum:10, minimumStrength:-20, maximumStrength:20, disabled,
        onChange(next){loras=next;imageLoras();changed();}});
    }
    function paintArt() {
      const id=value?.images?.art_style_id;
      $("art-name").textContent=id?(art?.display_name||art?.name||id):"Sans direction artistique";
      $("art-clear").hidden=!id;$("art-choose").disabled=disabled||$("image-recipe").value!=="6.0.0";
      $("art-clear").disabled=disabled;
    }
    function summary() {
      for(const [id] of axes)$("axis-"+id+"-value").value=$("axis-"+id).value;
      $("creative-summary").textContent=axes.map(([id])=>$("axis-"+id).value).join(" / ");
      $("settings-summary").textContent=`${$("duration").value||60} s · ${$("edit-engine").value==="qwen"?"Qwen":"MiniMax"} · usine en préparation`;
      if(videoSpec?.bunny) {
        const profiles=videoSpec.bunny.turbo_profiles||{};
        const selected=Object.keys(profiles).find(k=>["base","coarse","refine"].every(n=>Number($("video-"+n).value)===profiles[k][n+"_steps"]));
        $("video-preset").value=selected||"custom";
      }
    }
    function fillVideo(r) {
      const s=r.settings;
      if(!s.aspect_ratio)s.aspect_ratio="9:16 (Portrait Widescreen)";
      set("video-recipe",key(r.recipe));set("video-ratio",s.aspect_ratio);set("video-mp",s.megapixels);set("video-initial-mp",r.initial_megapixels);
      set("video-music",r.music_enabled?"on":"off");set("video-seed",Number(s.seed)?String(s.seed):"");set("video-steps",s.steps);
      set("video-spectrum",r.spectrum_enabled);checkpoint?.set(r.checkpoint);
      const bunny=r.bunny;$("bunny-settings").hidden=!bunny;
      for(const n of ["base","coarse","refine"])set("video-"+n,bunny?.[n+"_steps"]??({base:9,coarse:4,refine:5}[n]));
      set("video-turbo",bunny?.turbo_enabled??true);set("video-preview",bunny?.preview_enabled??true);
      videoLoras?.restore(r.video_loras);summary();
    }
    async function loadVideo(r, switched=false) {
      const token=++epoch;loading=true;onState();
      try {
        const spec=await request(`/api/h3-render/spec?mode=ref2va&recipe_id=${encodeURIComponent(r.recipe.id)}&recipe_version=${encodeURIComponent(r.recipe.version)}`);
        if(token!==epoch)return;
        r.recipe={id:spec.recipe.id,version:spec.recipe.version};
        videoSpec=spec;options("video-recipe",spec.render_recipes.map(x=>[key(x),`${x.label} · ${x.version}`]));
        options("video-ratio",spec.aspect_ratios.map(x=>[x,x]));
        options("video-preset",spec.bunny?[["on","Rapide · 9 / 4 / 5"],["off","Classique · 30 / 25 / 5"],["custom","Personnalisé"]]:[...spec.presets.map(x=>[x.id,x.label]),["custom","Personnalisé"]]);
        checkpoint?.configure(spec.checkpoint_selection);videoLoras?.configure(spec.video_lora_stack,spec.video_lora);
        if(switched) {
          r.bunny=spec.bunny?{...copy(spec.bunny.turbo_profiles.on),turbo_enabled:true,preview_enabled:true,lora_second_strength:spec.bunny.lora_second_strength}:null;
          r.video_loras=spec.video_lora_stack?.supported?copy(spec.video_lora_stack.defaults):null;
          r.checkpoint=null;r.spectrum_enabled=false;r.settings.steps=spec.defaults.steps;
        }
        value.video.render=copy(r);fillVideo(r);note("", "video");
        if(switched)changed();
      } catch(e) {if(token===epoch)note(e.message, "video");}
      finally {if(token===epoch){loading=false;setDisabled(disabled);onState();}}
    }
    function fill(next) {
      value=copy(next);const i=value.images,v=value.video;
      if(value.image_model==="cielbleukrea2_v1bf16.safetensors"){
        const model=(imageSpec.render_models||[]).find(m=>/cielbleukrea2_v1bf16[.]safetensors$/i.test(m.comfy_name));
        if(model)value.image_model=model.comfy_name;
      }
      loras=copy(i.loras);art=presets.find(p=>p.art_direction?.style_id===i.art_style_id)?.art_direction||null;
      for(const [id,fieldValue] of Object.entries({"prompt-model":next.prompt_model,"image-model":value.image_model,"dlss":next.dlss,
        "image-recipe":i.assistance_recipe_version,"image-style-preset":i.style_preset_id,"image-language":i.prompt_language,
        "image-inspirations":i.local_inspiration_enabled,"image-workflow":key(i.workflow),"image-ratio":i.aspect_ratio,
        "image-mp":i.megapixels,"image-sampling":i.sampling.preset_id,"edit-engine":i.edit_engine,"edit-model":i.edit_model,"thumbnail":i.thumbnail,
        "video-plan-model":v.plan_model,"video-prompt-model":v.prompt_model,"video-shots":v.shot_count}))set(id,fieldValue);
      for(const [id] of axes)set("axis-"+id,id==="audacity"?v.audacity:v.creative_axes[id]);
      imageLoras();paintArt();fillVideo(v.render);
      if(!videoSpec||key(videoSpec.recipe)!==key(v.render.recipe))videoLoad=loadVideo(copy(v.render));
    }
    function read() {
      if(!value)throw Error("Les réglages se chargent.");
      const out=copy(value),i=out.images,v=out.video,r=v.render;
      Object.assign(out,{prompt_model:$("prompt-model").value,image_model:$("image-model").value,dlss:$("dlss").checked});
      const [recipe_id,version]=$("image-workflow").value.split("@");
      Object.assign(i,{assistance_recipe_version:$("image-recipe").value,local_inspiration_enabled:$("image-inspirations").checked,
        style_preset_id:$("image-style-preset").value||null,prompt_language:$("image-language").value,workflow:{recipe_id,version},
        aspect_ratio:$("image-ratio").value,megapixels:Number($("image-mp").value),loras:copy(loras),
        sampling:copy(imageSpec.sampling?.presets.find(p=>p.id===$("image-sampling").value)?.settings||i.sampling),
        edit_engine:$("edit-engine").value,edit_model:$("edit-model").value,thumbnail:$("thumbnail").checked});
      Object.assign(v,{plan_model:$("video-plan-model").value,prompt_model:$("video-prompt-model").value,
        shot_count:$("video-shots").value?Number($("video-shots").value):null,audacity:Number($("axis-audacity").value)});
      for(const [id] of axes)if(id!=="audacity")v.creative_axes[id]=Number($("axis-"+id).value);
      const [id,rv]=$("video-recipe").value.split("@");r.recipe={id,version:rv};
      Object.assign(r.settings,{aspect_ratio:$("video-ratio").value,megapixels:Number($("video-mp").value),seed:$("video-seed").value||"0",steps:Number($("video-steps").value)});
      Object.assign(r,{initial_megapixels:Number($("video-initial-mp").value),music_enabled:$("video-music").value==="on",
        spectrum_enabled:$("video-spectrum").checked,checkpoint:checkpoint?.value??r.checkpoint,
        video_loras:videoLoras?.supported?videoLoras.value:r.video_loras});
      if(r.bunny)for(const n of ["base","coarse","refine"])r.bunny[n+"_steps"]=Number($("video-"+n).value);
      if(r.bunny){r.bunny.turbo_enabled=$("video-turbo").checked;r.bunny.preview_enabled=$("video-preview").checked;r.settings.steps=r.bunny.base_steps;}
      return {prompt_model:out.prompt_model,image_model:out.image_model,dlss:out.dlss,images:i,video:v};
    }
    function setDisabled(next) {
      disabled=next;checkpoint?.setDisabled(next||loading);videoLoras?.setDisabled(next||loading);imageLoras();paintArt();
      $("video-spectrum").disabled=next||!!value?.video?.render?.bunny;
      $("video-recipe").disabled=next||loading;$("video-preset").disabled=next||loading;
    }
    async function initialize(initial, models) {
      value=copy(initial);
      for(const id of llmIds)options(id,models.map(m=>[m.id,m.label||m.id]));
      const results=await Promise.allSettled([request("/api/image-lab/krea2-assisted/spec"),request("/api/image-lab/krea2-assisted/style-presets")]);
      if(results[0].status==="fulfilled"){
        imageSpec=results[0].value;
        options("image-recipe",(imageSpec.assistance_recipes||[]).map(r=>[r.version,r.label||r.name||r.version]));
        options("image-workflow",imageSpec.workflows.map(w=>[w.id||key(w),w.label]));
        options("image-model",imageSpec.render_models.map(m=>[m.comfy_name,m.display_name||m.comfy_name]));
        options("image-ratio",imageSpec.aspect_ratios.map(r=>[r,r]));
        options("image-sampling",imageSpec.sampling.presets.map(r=>[r.id,r.label]));
      }
      if(results[1].status==="fulfilled"){
        presets=results[1].value.presets;options("image-style-preset",[["","Sans preset"],...presets.filter(p=>p.category!=="archive").map(p=>[p.preset_id,p.name])]);
      }
      note(results.filter(r=>r.status==="rejected").map(r=>r.reason.message).join(" · "));
      // Fill without firing a second competing recipe request.
      fill(initial);
      if(videoLoad)await videoLoad;
    }
    async function findArt() {
      const token=++artEpoch;$("art-status").textContent="Chargement…";
      try {
        const data=await request(`/api/image-lab/krea2-assisted/art-styles?query=${encodeURIComponent($("art-search").value)}`);
        if(token!==artEpoch)return;$("art-list").replaceChildren();
        for(const style of data.styles.slice(0,80)){
          const b=document.createElement("button"),img=document.createElement("img"),label=document.createElement("span");b.type="button";
          img.src=style.thumbnail_url;img.alt="";img.loading="lazy";label.textContent=style.display_name||style.name;b.append(img,label);
          b.addEventListener("click",()=>{if(disabled)return;art=style;value.images.art_style_id=style.style_id;$("art-picker").close();paintArt();changed();});$("art-list").append(b);
        }
        $("art-status").textContent=data.styles.length>80?"80 premiers styles · affine ta recherche":`${data.styles.length} styles`;
      }catch(e){if(token===artEpoch)$("art-status").textContent=e.message;}
    }
    $("art-choose").addEventListener("click",()=>{$("art-picker").showModal();findArt();});
    $("art-clear").addEventListener("click",()=>{value.images.art_style_id=null;art=null;paintArt();changed();});
    $("art-close").addEventListener("click",()=>{$("art-picker").close();++artEpoch;});
    $("art-search").addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(findArt,250);});
    $("image-recipe").addEventListener("change",()=>{if($("image-recipe").value!=="6.0.0"){value.images.art_style_id=null;art=null;}paintArt();changed();});
    $("image-style-preset").addEventListener("change",()=>{
      const p=presets.find(x=>x.preset_id===$("image-style-preset").value);if(!p){changed();return;}
      set("image-model",p.settings.model_id);loras=copy(p.settings.loras||[]);
      if(p.settings.workflow){set("image-workflow",typeof p.settings.workflow==="string"?p.settings.workflow:key(p.settings.workflow));if(p.settings.sampling){value.images.sampling=copy(p.settings.sampling);set("image-sampling",p.settings.sampling.preset_id);}}
      for(const [k,id] of [["aspect_ratio","image-ratio"],["megapixels","image-mp"]])if(p.settings[k]!=null)set(id,p.settings[k]);
      set("image-language",p.prompt_language||"en");
      if($("image-recipe").value==="6.0.0"){art=p.art_direction||null;value.images.art_style_id=art?.style_id||null;}
      imageLoras();paintArt();changed();
    });
    $("video-recipe").addEventListener("change",()=>{const r=read().video.render;loadVideo(r,true);});
    $("video-preset").addEventListener("change",()=>{
      const p=videoSpec?.bunny?.turbo_profiles?.[$("video-preset").value];
      if(p){for(const n of ["base","coarse","refine"])set("video-"+n,p[n+"_steps"]);set("video-steps",p.base_steps);set("video-turbo",$("video-preset").value==="on");}
      else {const p=videoSpec?.presets.find(p=>p.id===$("video-preset").value);if(p){set("video-steps",p.steps);set("video-ratio",p.aspect_ratio);set("video-mp",p.megapixels);set("video-initial-mp",p.initial_megapixels??p.megapixels);}}
      changed();
    });
    $("form").addEventListener("input",summary);
    return {initialize,fill,read,setDisabled,summary,get busy(){return loading;}};
  }};
})();
