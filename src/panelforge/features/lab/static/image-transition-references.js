/* Worker selection and deterministic placement; no renderer or LLM calls here. */
(() => {
  "use strict";
  window.PanelForgeTransitionReferenceUI = context => {
    const {state,$,api,endpoint,withVersion,run,accept,asset,esc,imageButton,current,transitions,message,isBlocked} = context;
    let draft=null, dragging=null, librarySerial=0;
    const enabled=()=>!!state.p && !!state.spec?.visual_references;
    const dialogs=[$("worker-dialog"),$("scale-dialog")];
    function showError(text) {
      if($("worker-dialog").open)$("worker-message").textContent=text;
      if($("scale-dialog").open)$("scale-message").textContent=text;
    }
    function controls() {
      const blocked=isBlocked();
      for(const id of ["worker-choose","worker-upload","worker-clear"])
        $(id).disabled=blocked||!enabled();
      $("crew").disabled=blocked||!state.p||!state.spec?.crews?.length;
      for(const dialog of dialogs) dialog.querySelectorAll("input,select,button").forEach(input=>{
        if(input.matches("[data-it-close],[data-it-zoom]"))return;
        input.disabled=blocked||!enabled();
      });
      document.querySelectorAll("[data-it-scale]").forEach(button=>{
        button.disabled=blocked||!enabled()||!state.p?.worker_reference;
      });
      const ready=draft && $("scale-base").complete && $("scale-base").naturalWidth &&
        $("scale-worker").complete && $("scale-worker").naturalWidth;
      $("scale-save").disabled=blocked||!enabled()||!ready;
      $("scale-remove").disabled=blocked||!enabled()||!draft?.scaleId;
    }
    function paint() {
      const worker=state.p?.worker_reference;
      $("worker-preview").innerHTML=worker?imageButton(worker,""):"";
      $("worker-clear").hidden=!worker;
      $("worker-label").textContent=worker?worker.label:"Aucune référence choisie · description textuelle utilisée.";
      $("people-summary").textContent=worker?" · "+worker.label+" · REF2VA":" · facultatif";
    }
    function inspector(transition) {
      const visual=transition.visual_references||{}, scale=visual.scale;
      if(!state.p?.worker_reference && !scale)return "";
      const count=transitions().filter(t=>t.scale_setup_id && t.scale_setup_id===transition.scale_setup_id).length;
      return '<div class="it-scale-summary">'+
        (scale?imageButton(scale,"Échelle"):"")+
        '<div><b>Ouvriers et échelle</b><p class="it-help">'+
        esc(visual.error || (scale?"Placement partagé par "+count+" paire(s).":"Place l’ouvrier pour montrer sa taille dans le décor."))+
        '</p><button type="button" data-it-scale="'+esc(transition.id)+'">'+(scale?"Ajuster l’échelle":"Régler l’échelle")+
        '</button></div></div>';
    }
    function cards(images) {
      return images.map(value=>'<article class="it-worker-card">'+imageButton(value,"")+
        '<small title="'+esc(value.label)+'">'+esc(value.label)+'</small>'+
        '<button type="button" data-it-worker-asset="'+esc(value.asset_id)+'" data-it-worker-label="'+esc(value.label)+'">Choisir</button></article>').join("");
    }
    async function openLibrary() {
      const serial=++librarySerial;
      $("worker-message").textContent="Chargement…";
      $("worker-saved").replaceChildren();$("worker-recent").replaceChildren();
      $("worker-dialog").showModal();
      const data=await api("/worker-library");
      if(serial!==librarySerial||!$("worker-dialog").open)return;
      $("worker-saved").innerHTML=cards(data.saved)||'<p class="it-help">Les ouvriers choisis apparaîtront ici.</p>';
      const saved=new Set(data.saved.flatMap(v=>[v.asset_id,v.source_asset_id]));
      $("worker-recent").innerHTML=cards(data.recent.filter(v=>!saved.has(v.asset_id)))||'<p class="it-help">Importe une image pour commencer.</p>';
      $("worker-message").textContent=(data.warnings||[]).join(" · ");
      controls();
    }
    $("worker-choose").onclick=()=>run(openLibrary);
    const chooseFile=()=>{$("worker-file").value="";$("worker-file").click();};
    $("worker-upload").onclick=chooseFile;
    $("worker-import-dialog").onclick=chooseFile;
    $("worker-dialog").addEventListener("close",()=>{librarySerial++;});
    $("worker-dialog").addEventListener("click",event=>{
      const button=event.target.closest("[data-it-worker-asset]");if(!button)return;
      run(async()=>{
        accept((await api(endpoint("/worker"),"PUT",withVersion({
          asset_id:button.dataset.itWorkerAsset,label:button.dataset.itWorkerLabel}))).project);
        $("worker-dialog").close();$("people").open=true;
        message("Ouvrier choisi. Règle son échelle depuis la paire, puis propose les transitions.");
      });
    });
    $("worker-file").onchange=()=>{
      const file=$("worker-file").files[0];if(!file)return;
      run(async()=>{
        const body=new FormData();body.set("version",String(state.p.version));body.set("image",file);
        const result=await context.upload("/api/image-transitions"+endpoint("/worker/upload"),{method:"POST",body});
        accept(result.project);$("worker-dialog").close();$("people").open=true;
        message("Ouvrier importé. Il sera aussi disponible dans Mes ouvriers.");
      });
    };
    $("worker-clear").onclick=()=>run(async()=>{
      accept((await api(endpoint("/worker"),"PUT",withVersion({asset_id:null}))).project);
      message("Référence retirée. Les anciennes unités restent dans l’usine.");
    });
    function normalize() {
      if(!draft)return;
      const [sw,sh]=draft.scene.dimensions,[ww,wh]=draft.worker.dimensions,p=draft.position;
      const max=Math.min(.85,sw/sh*wh/ww);
      p.height=Math.min(max,Math.max(.005,p.height));
      const width=p.height*sh*ww/wh/sw;
      p.x=Math.max(width/2,Math.min(1-width/2,p.x));
      p.y=Math.max(p.height,Math.min(1,p.y));
      $("scale-height").max=String(Math.floor(max*1000)/10);
      return width;
    }
    function draw() {
      const width=normalize();if(!draft)return;
      const p=draft.position,piece=$("scale-piece");
      piece.style.left=(p.x-width/2)*100+"%";
      piece.style.top=(p.y-p.height)*100+"%";
      piece.style.width=width*100+"%";piece.style.height=p.height*100+"%";
      $("scale-height").value=String(p.height*100);
      $("scale-size").textContent=(p.height*100).toFixed(1)+" %";
      controls();
    }
    async function openScale(identity) {
      const transition=transitions().find(t=>t.id===identity),worker=state.p.worker_reference;
      if(!transition||!worker)return;
      const scene=state.p.frames.find(f=>f.id===transition.left);
      if(scene.dimensions[0]/scene.dimensions[1]*worker.dimensions[1]/worker.dimensions[0]<.005)
        throw Error("Cette image est trop large pour ce décor. Choisis une vue en pied de l’ouvrier.");
      const scale=transition.visual_references?.scale;
      draft={projectId:state.p.id,transitionId:identity,worker:{...worker},scene:{...scene},
        scaleId:scale?.id,position:{...(scale?.placement||{x:.5,y:.9,height:.12})}};
      $("scale-title").textContent="Échelle · transition "+(transitions().indexOf(transition)+1)+" → "+(transitions().indexOf(transition)+2);
      $("scale-message").textContent="";
      $("scale-scope").value=transition.kind==="camera"?"pair":"following";
      $("scale-base").src=asset(scene.asset_id);$("scale-worker").src=asset(worker.asset_id);
      const [width,height]=scene.dimensions;
      $("scale-stage").style.aspectRatio=width+" / "+height;
      $("scale-stage").style.width="min(100%, "+Math.round(520*width/height)+"px)";
      $("scale-dialog").showModal();draw();
    }
    $("inspector").addEventListener("click",event=>{
      const button=event.target.closest("[data-it-scale]");
      if(button)run(()=>openScale(button.dataset.itScale));
    });
    $("scale-base").onload=draw;$("scale-worker").onload=draw;
    for(const id of ["scale-base","scale-worker"])$(id).onerror=()=>{
      $("scale-message").textContent="Impossible de charger l’image. Ferme puis rouvre le placement.";controls();
    };
    $("scale-height").oninput=()=>{
      if(!draft||isBlocked())return;
      draft.position.height=Number($("scale-height").value)/100;draw();
    };
    $("scale-stage").addEventListener("pointerdown",event=>{
      if(!draft||isBlocked()||event.button!==0)return;
      event.preventDefault();
      const rect=$("scale-stage").getBoundingClientRect();
      if(!event.target.closest("#it-scale-piece")){
        draft.position.x=(event.clientX-rect.left)/rect.width;
        draft.position.y=(event.clientY-rect.top)/rect.height;draw();
      }
      dragging={id:event.pointerId,x:event.clientX,y:event.clientY,rect,
        position:{...draft.position},resize:!!event.target.closest("#it-scale-handle")};
      $("scale-stage").setPointerCapture(event.pointerId);$("scale-piece").focus({preventScroll:true});
    });
    $("scale-stage").addEventListener("pointermove",event=>{
      if(!draft||!dragging||event.pointerId!==dragging.id||isBlocked())return;
      const dx=(event.clientX-dragging.x)/dragging.rect.width,dy=(event.clientY-dragging.y)/dragging.rect.height;
      if(dragging.resize)draft.position.height=dragging.position.height-dy;
      else {draft.position.x=dragging.position.x+dx;draft.position.y=dragging.position.y+dy;}
      draw();
    });
    for(const kind of ["pointerup","pointercancel","lostpointercapture"])
      $("scale-stage").addEventListener(kind,()=>{dragging=null;});
    $("scale-piece").addEventListener("keydown",event=>{
      if(!draft||isBlocked()||!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key))return;
      event.preventDefault();const step=event.shiftKey ? .02 : .005;
      if(event.key==="ArrowLeft")draft.position.x-=step;
      if(event.key==="ArrowRight")draft.position.x+=step;
      if(event.key==="ArrowUp")draft.position.y-=step;
      if(event.key==="ArrowDown")draft.position.y+=step;
      draw();
    });
    function validateDraft() {
      if(!draft||draft.projectId!==state.p.id||draft.worker.asset_id!==state.p.worker_reference?.asset_id ||
        !state.p.frames.some(f=>f.id===draft.scene.id&&f.asset_id===draft.scene.asset_id))
        throw Error("Le décor ou l’ouvrier a changé. Rouvre le placement.");
    }
    function saveScale(remove=false) {
      run(async()=>{
        validateDraft();
        const result=await api(endpoint("/transitions/"+encodeURIComponent(draft.transitionId)+"/scale"),"PUT",
          withVersion({position:remove?null:{...draft.position},scope:$("scale-scope").value}));
        accept(result.project);$("scale-dialog").close();
        message(remove?"Échelle retirée.":"Référence d’échelle enregistrée. Propose puis relis les transitions concernées.");
      });
    }
    $("scale-save").onclick=()=>saveScale();
    $("scale-remove").onclick=()=>saveScale(true);
    $("scale-dialog").addEventListener("close",()=>{draft=null;dragging=null;});
    return {paint,controls,inspector,dialogs,showError,editing:()=>$("scale-dialog").open};
  };
})();
