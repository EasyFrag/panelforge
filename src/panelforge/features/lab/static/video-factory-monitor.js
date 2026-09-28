(() => {
  "use strict";
  const labels={plan:"Plan",prompt:"Prompt",video:"Vidéo",dlss:"DLSS",social:"Texte IG",export:"Export"};
  const finite=value=>typeof value==="number"&&Number.isFinite(value);
  const duration=value=>{
    if(!finite(value))return "À préciser";
    const seconds=Math.max(0,Math.ceil(value));
    if(seconds<60)return seconds+" s";
    const minutes=Math.ceil(seconds/60);
    return minutes<60?minutes+" min":Math.floor(minutes/60)+" h "+String(minutes%60).padStart(2,"0");
  };
  function create({root,escape,request,getState,getSelection}) {
    const $=id=>document.getElementById("vf-"+id);
    let receivedAt=performance.now(), previewAt=0, preview=null, previewKey="", requestId=0, timer;
    const data=()=>getState().data?.monitoring;
    const age=which=>(performance.now()-(which==="preview"?previewAt:receivedAt))/1000;
    const source=which=>which==="preview"?preview:data();
    const stale=which=>!source(which)||source(which).stale||age(which)>20;
    const time=(seconds,which="main")=>{
      const value=source(which);
      if(!value||!finite(seconds)||stale(which))return "—";
      const offset=seconds>0?Math.max(seconds,age(which)+1):seconds;
      const date=new Date((value.generated_at+offset)*1000),today=new Date(value.generated_at*1000);
      const clock=date.toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});
      return date.toDateString()===today.toDateString()?clock:date.toLocaleDateString("fr-FR",{day:"2-digit",month:"2-digit"})+" à "+clock;
    };
    const remaining=(seconds,which="main",frozen=false)=>{
      if(!finite(seconds))return "À préciser";
      // Waits retain a work budget; an expired estimate is never completion.
      const value=seconds-(frozen||source(which)?.stale?0:Math.min(age(which),20));
      return value<60?"≈ < 1 min":"≈ "+duration(value);
    };
    const range=(value,which)=>value.indicative_reason||(finite(value.low_seconds)&&finite(value.high_seconds)?
      time(value.low_seconds,which)+" – "+time(value.high_seconds,which):"Prévision en cours d’affinage");
    function rowContent(item) {
      const which=item.status==="preparation"?"preview":"main",value=source(which)?.items?.[item.id];
      if(!value||item.status==="preparation"&&!getSelection().some(i=>i.id===item.id))return "";
      if(["failed","cancelled"].includes(item.status)||item.remove_requested)return "";
      const complete=value.remaining_seconds===0&&item.status==="succeeded";
      if(complete)return '<small class="vf-eta-ready">Livré · export terminé</small>';
      const held=value.retained||stale(which);
      let html=finite(value.remaining_seconds)?'<strong title="'+escape(held?value.indicative_reason||"Dernière estimation connue":range(value,which))+'">'+escape(held?"Reste "+remaining(value.remaining_seconds,which,value.retained):"Prêt vers "+time(value.remaining_seconds,which))+'</strong><small>'+escape(held?"Estimation conservée":remaining(value.remaining_seconds,which))+'</small>':
        '<small class="vf-eta-muted">'+escape(value.reason||"Prévision à préciser")+'</small>';
      if(!held&&item.steps.video.status==="pending"&&finite(value.video_start_in))
        html+='<small>Rendu vers '+escape(time(value.video_start_in,which))+'</small>';
      if(source(which)?.conditional_on_resume)html+='<small>Si reprise maintenant</small>';
      return html;
    }
    function rows() {
      const state=getState(),items=new Map((state.data?.items||[]).map(i=>[i.id,i]));
      root.querySelectorAll("[data-vf-monitor-row]").forEach(node=>{
        const item=items.get(node.dataset.vfMonitorRow);node.innerHTML=item?rowContent(item):"";
      });
      root.querySelectorAll("[data-vf-monitor-step]").forEach(node=>{
        const item=items.get(node.dataset.vfMonitorItem),step=item?.steps[node.dataset.vfMonitorStep];
        const estimate=data()?.items?.[item?.id]?.steps?.[node.dataset.vfMonitorStep];
        node.textContent=step?.status==="running"&&estimate?
          (finite(estimate.seconds)?"Reste "+remaining(estimate.seconds,"main",estimate.retained):"À préciser"):"";
        node.title=estimate?(stale("main")?"Dernière estimation connue · ": "")+estimate.reason+" · "+estimate.samples+" mesure(s)":"";
      });
    }
    function summary() {
      const node=$("monitor-summary"),m=data();
      if(!node)return;
      node.hidden=!m?.counts?.total&&m?.available!==false;
      if(node.hidden)return;
      if(m.available===false){
        node.innerHTML='<span class="vf-monitor-state" title="'+escape(m.warning||"Prévisions indisponibles")+'">Prévision indisponible</span>';
        return;
      }
      const counts=m.counts,complete=m.status==="complete",paused=m.status==="paused",old=stale("main");
      const status=old?"À actualiser":({running:"Lot en cours",paused:"En pause",complete:"Lot livré",attention:"À vérifier"}[m.status]||"Lot");
      const left=complete?"Terminé":m.status==="attention"?"À reprendre":finite(m.remaining_seconds)?remaining(m.remaining_seconds,"main",m.retained):paused?"Suspendu":"À préciser";
      const finish=paused||old||m.retained||!finite(m.remaining_seconds)||m.status==="attention"?"—":complete?
        new Date(m.cycle.finished_at).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"}):time(m.remaining_seconds);
      const details=(counts.active+(counts.stopping||0))+" actives · "+counts.queued+" en attente · "+counts.exporting+" à exporter · "+counts.failed+" en erreur";
      const hint=m.warning||(old?"Dernière estimation connue · actualisation attendue":paused?"Temps indicatif conservé · fin recalculée à la reprise":range(m,"main"));
      node.innerHTML='<span class="vf-monitor-state" title="'+escape(details)+'"><i class="vf-monitor-dot '+(paused?"paused":old||m.status==="attention"?"warning":"")+'" aria-hidden="true"></i>'+escape(status)+'</span>'+
        '<span class="vf-monitor-value" title="'+escape(hint)+'">Reste <strong>'+escape(left)+'</strong></span>'+
        '<span class="vf-monitor-value" title="'+escape(hint)+'">Fin <strong>'+escape(finish)+'</strong></span>'+
        '<span class="vf-monitor-value" title="'+escape(details)+'"><strong>'+counts.delivered+'/'+counts.total+'</strong> livrées</span>';
    }
    function detail() {
      const state=getState(),item=state.data?.items.find(i=>i.id===state.focus),inspector=$("inspector");
      if(!inspector)return;
      let node=$("monitor-detail");
      const which=item?.status==="preparation"?"preview":"main",value=source(which)?.items?.[item?.id];
      const allowed=item&&value&&(which==="main"||getSelection().some(i=>i.id===item.id))&&!state.dirty;
      if(!allowed){node?.remove();return;}
      if(!node){node=document.createElement("section");node.id="vf-monitor-detail";node.className="vf-monitor-detail";inspector.querySelector(".vf-inspector-title")?.after(node);}
      const unfinished=Object.entries(value.steps).filter(([key])=>key==="export"?!item.can_archive:!["succeeded","skipped"].includes(item.steps[key].status));
      const fabrication=unfinished.every(([,s])=>finite(s.seconds))?unfinished.reduce((sum,[,s])=>sum+s.seconds,0):null;
      const starts=unfinished.map(([,s])=>s.start_in).filter(finite),wait=starts.length?Math.min(...starts):null;
      node.innerHTML='<h3>'+ (which==="preview"?"Si lancé maintenant":"Prévision de livraison")+'</h3><p><strong>'+escape(finite(value.remaining_seconds)?value.retained||stale(which)?"Reste "+remaining(value.remaining_seconds,which,value.retained):"Prêt vers "+time(value.remaining_seconds,which):value.reason||"À préciser")+'</strong><br><small>'+escape(range(value,which))+'</small></p>'+
        '<dl><dt>Attente avant la prochaine étape</dt><dd>'+escape(finite(wait)?duration(Math.max(0,wait-age(which))):"À préciser")+'</dd><dt>Étapes restantes, hors attentes</dt><dd>'+escape(duration(fabrication))+'</dd><dt>Vidéo brute disponible</dt><dd>'+escape(item.steps.video.status==="succeeded"?"Déjà prête":value.retained||stale(which)?"En attente":time(value.video_ready_in,which))+'</dd></dl>'+
        '<ul>'+unfinished.map(([key,s])=>'<li><span>'+labels[key]+'</span><strong>'+escape(duration(s.seconds))+'</strong><small>'+escape(s.source==="allowance"?"Provision export, sans mesure":s.samples+" mesure(s) · "+(s.confidence==="medium"?"comparable":"indicatif"))+'</small></li>').join("")+'</ul>'+
        '<small>La livraison inclut le DLSS et le texte IG activés, puis l’export. Les temps restent indicatifs.</small>';
    }
    function renderPreview() {
      const node=$("monitor-preview"),state=getState(),items=getSelection();if(!node)return;
      node.hidden=state.tab!=="preparation"||state.dirty||!data()||!items.length||
        items.some(i=>!i.ready||i.status!=="preparation");
      if(node.hidden){node.replaceChildren();return;}
      const label='<span class="vf-monitor-state">Sélection ('+items.length+')</span>';
      if(!preview){node.innerHTML=label+'<span>Estimation…</span>';return;}
      if(preview.error||preview.available===false){
        node.innerHTML=label+'<span title="'+escape(preview.error||preview.warning||"Prévision indisponible")+'">Indisponible</span>';
        return;
      }
      const old=stale("preview"),hint=preview.conditional_on_resume?"Si la file reprend maintenant":range(preview,"preview");
      node.innerHTML=label+
        '<span class="vf-monitor-value" title="'+escape(hint)+'"><strong>'+escape(old?"À actualiser":remaining(preview.remaining_seconds,"preview"))+'</strong></span>'+
        '<span class="vf-monitor-value" title="'+escape(hint)+'">Fin <strong>'+escape(time(preview.remaining_seconds,"preview"))+'</strong></span>'+
        (preview.conditional_on_resume?'<span class="vf-monitor-condition">si reprise</span>':"");
    }
    function previewSelection() {
      const state=getState(),items=getSelection(),m=data();
      const valid=state.tab==="preparation"&&!state.dirty&&items.length&&items.every(i=>i.ready&&i.status==="preparation")&&m;
      const key=valid?JSON.stringify([items.map(i=>[i.id,i.revision]),state.data.revision,Math.floor((m.generated_at||0)/5)]):"";
      if(key===previewKey){renderPreview();return;}
      previewKey=key;preview=null;requestId++;clearTimeout(timer);renderPreview();rows();detail();
      if(!key)return;
      const serial=requestId,body={ids:items.map(i=>i.id),revisions:Object.fromEntries(items.map(i=>[i.id,i.revision]))};
      timer=setTimeout(async()=>{
        try{
          const value=await request("/estimate","POST",body);
          if(serial!==requestId)return;
          preview=value;previewAt=performance.now();
        }catch(error){if(serial!==requestId)return;preview={error:error.message};}
        renderPreview();rows();detail();
      },300);
    }
    return Object.freeze({
      received(){receivedAt=performance.now();},
      render(){summary();rows();detail();},
      previewSelection,
      row(item){return '<div class="vf-eta-row" data-vf-monitor-row="'+escape(item.id)+'">'+rowContent(item)+'</div>';},
      step(item,key){return item.steps[key].status==="running"?'<small class="vf-stage-eta" data-vf-monitor-item="'+escape(item.id)+'" data-vf-monitor-step="'+key+'"></small>':"";},
      tick(){if(root.hidden)return;summary();rows();detail();renderPreview();}
    });
  }
  window.PanelForgeFactoryMonitor=Object.freeze({create});
})();
