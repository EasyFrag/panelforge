(() => {
  "use strict";
  const $=id=>document.getElementById(id), finite=v=>typeof v==="number"&&Number.isFinite(v);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  let data=null,received=0,busy=false,loading=false,serial=0,tab="follow",limit=24,installPrompt=null,registration=null,push=null,dialogAction=null;
  const saved=(key,value)=>{try{if(value===undefined)return localStorage.getItem(key);if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);}catch{}return null;};
  let subscriptionId=saved("factory-mobile-subscription");
  const secondsAge=()=>Math.max(0,(performance.now()-received)/1000);
  const stale=()=>!data||secondsAge()>20;
  const duration=seconds=>{
    if(!finite(seconds))return "À préciser";
    if(seconds<60)return "< 1 min";
    const m=Math.ceil(seconds/60);return m<60?m+" min":Math.floor(m/60)+" h "+String(m%60).padStart(2,"0");
  };
  const remaining=(seconds,held=false)=>finite(seconds)?"≈ "+duration(Math.max(0,seconds-(held?0:Math.min(20,secondsAge())))):"À préciser";
  const hour=epoch=>finite(epoch)?new Date(epoch*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"}):"—";
  function message(text){$("message").textContent=text||"";$("message").hidden=!text;}
  async function request(path,method="GET",body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch(path,{method,cache:"no-store",signal:controller.signal,
        headers:method==="GET"?{}:{"Content-Type":"application/json","X-PanelForge-Mobile":"1"},
        body:body===undefined?undefined:JSON.stringify(body)});
      const value=await response.json();
      if(!response.ok)throw new Error(typeof value.detail==="string"?value.detail:"Impossible de traiter cette demande.");
      return value;
    }finally{clearTimeout(timer);}
  }
  async function refresh(){
    if(loading||busy)return;loading=true;const seq=++serial;
    try{
      const value=await request("/api/state?limit="+limit);
      if(seq!==serial)return;
      data=value;received=performance.now();message("");render();
    }catch(error){if(seq===serial){received=-Infinity;message("Connexion interrompue. Vérifiez Tailscale et le PC ; les dernières valeurs restent affichées.");tick();}}
    finally{loading=false;}
  }
  function safeMedia(url){return typeof url==="string"&&/^\/api\/items\/[a-zA-Z0-9_-]+\/(poster|video)$/.test(url)?url:"";}
  function poster(item){const url=safeMedia(item.poster_url);return url?'<img class="poster" src="'+esc(url)+'" loading="lazy" alt="">':'<span class="poster" aria-hidden="true"></span>';}
  const thresholdFor=m=>push?.registered&&push.thresholds?push.thresholds[m.id]:m.threshold;
  const stageLabel=item=>item.stopping?"Arrêt demandé":item.steps.find(s=>s.status==="running")?.label||({queued:"En attente",failed:"À vérifier",cancelled:"Interrompue",succeeded:"Export"}[item.status]||"En cours");
  function workCard(item,compact=false){
    const current=item.steps.find(s=>s.status==="running");
    return '<article class="card work-card"><div class="work-heading">'+poster(item)+'<div><small>'+esc(item.group||"Production")+'</small><h3>'+esc(item.name)+'</h3><p>'+esc(stageLabel(item))+
      (current&&finite(current.remaining_seconds)?' · <span data-step-seconds="'+current.remaining_seconds+'" data-held="'+Boolean(current.retained)+'">'+esc(remaining(current.remaining_seconds,current.retained))+'</span>':"")+'</p></div></div>'+
      (!compact?'<div class="steps">'+item.steps.map(s=>'<span class="step '+esc(s.status)+'">'+esc(s.label)+(s.status==="succeeded"?" ✓":s.status==="skipped"?" · off":"")+'</span>').join("")+'</div>':"")+
      '<p class="eta" title="'+esc(item.hint||"Estimation indicative")+'">'+(finite(item.remaining_seconds)?'<span data-seconds="'+item.remaining_seconds+'" data-held="'+Boolean(item.retained)+'">'+esc(remaining(item.remaining_seconds,item.retained))+'</span>'+(item.retained?" · estimation conservée":finite(item.finish_at)?" · vers "+esc(hour(item.finish_at)):""):esc(item.hint||"Prévision à préciser"))+'</p>'+
      (item.can_retry?'<button class="secondary" data-retry="'+esc(item.id)+'">Reprendre cette vidéo</button>':"")+'</article>';
  }
  function render(){
    if(!data)return;
    const active=data.work.filter(i=>i.status==="active"),queue=data.work.filter(i=>i.status==="queued");
    const attention=data.work.filter(i=>i.failed||i.status==="cancelled");
    $("active-count").textContent=active.length;$("queue-count").textContent=queue.length;
    $("active").innerHTML=active.map(i=>workCard(i)).join("")||'<p class="empty">'+(data.paused?"La file est en pause.":"Aucune étape active.")+'</p>';
    $("queue").innerHTML=queue.map(i=>workCard(i,true)).join("")||'<p class="empty">Aucune vidéo en attente.</p>';
    $("attention-section").hidden=!attention.length;$("attention-count").textContent="("+attention.length+")";
    $("attention").innerHTML=attention.map(i=>workCard(i)).join("");
    $("machines").innerHTML=data.machines.map(m=>'<article class="card machine '+(!data.stale&&finite(m.temperature_c)&&m.temperature_c>=thresholdFor(m)?"hot":"")+'"><span>'+esc(m.name)+'</span><strong>'+esc(data.stale?"—":finite(m.temperature_c)?Math.round(m.temperature_c)+" °C":"— °C")+'</strong><small>'+esc(data.stale?"Mesure ancienne":({idle:"Disponible",busy:"En activité",cooling:"Refroidissement",hot:"Température élevée",paused:"En pause",unavailable:"Mesure indisponible"}[m.state]||"Mesure indisponible"))+'</small></article>').join("");
    $("result-count").textContent=data.result_total;
    $("results").innerHTML=data.results.map(i=>'<article class="result"><button data-play="'+esc(i.id)+'" aria-label="Lire '+esc(i.name)+'">'+(safeMedia(i.poster_url)?'<img src="'+esc(i.poster_url)+'" loading="lazy" alt="">':"")+'<span class="play" aria-hidden="true">▷</span></button><div class="result-info"><h3>'+esc(i.name)+'</h3><small>'+esc(i.quality+(i.delivered?" · Livrée":" · Vidéo prête"))+'</small></div></article>').join("")||'<p class="empty">Les vidéos produites apparaîtront ici.</p>';
    $("more").hidden=data.results.length>=data.result_total||limit>=200;
    renderAlerts();tick();
  }
  function renderAlerts(){
    if(!data)return;
    const alerts=data.alerts.filter(a=>a.kind!=="complete"&&a.kind!=="temperature");
    if(!data.stale)for(const m of data.machines){
      if(finite(m.temperature_c)&&m.temperature_c>=thresholdFor(m))
        alerts.push({kind:"temperature",title:m.name+" : température élevée",body:m.temperature_c+" °C · seuil "+thresholdFor(m)+" °C"});
    }
    $("alerts").innerHTML=alerts.map(a=>'<article class="card alert"><h3>'+esc(a.title)+'</h3><p>'+esc(a.body)+'</p></article>').join("")||'<p class="empty">'+(data.stale?"Les températures attendent une mesure récente.":"Aucune alerte en cours.")+'</p>';
    $("alert-count").hidden=!alerts.length;$("alert-count").textContent=alerts.length;
  }
  function tick(){
    const old=stale();
    $("connection").textContent=old?data?"Connexion perdue":"Connexion…":"À jour";
    $("connection-dot").className=old?"old":"live";
    $("pause").disabled=busy||old;$("stop").disabled=busy||old||!data?.work.some(i=>i.status==="active"&&!i.stopping);
    document.querySelectorAll("[data-retry]").forEach(b=>b.disabled=busy||old);
    if(!data)return;
    if(old)document.querySelectorAll(".machine small").forEach(node=>node.textContent="Dernière mesure · hors connexion");
    const counts=data.counts;
    $("lot-status").textContent=old?"Hors connexion":({running:"Lot en cours",paused:"En pause",complete:"Lot livré",attention:"À vérifier",empty:"Disponible"}[data.status]||"Disponible");
    $("delivered").textContent=counts.delivered+" / "+counts.total+" livrées";
    $("progress").max=Math.max(1,counts.total);$("progress").value=counts.delivered;
    $("remaining").textContent=data.status==="complete"?"Terminé":data.status==="empty"?"—":remaining(data.remaining_seconds,data.retained);
    $("finish").textContent=old||data.stale||data.retained||data.paused||data.status==="complete"?"—":hour(data.finish_at);
    $("eta-hint").textContent=old?"Dernière estimation connue. Commandes indisponibles hors connexion.":data.paused?"La file est en pause. Les étapes déjà actives peuvent finir.":data.retained?"Dernière estimation conservée ; la fin sera recalculée à la reprise.":data.hint||"Prévision indicative, affinée pendant la production.";
    $("pause").textContent=busy?"Patientez…":data.paused?"Reprendre la file":"Pause";
    document.querySelectorAll("[data-seconds],[data-step-seconds]").forEach(node=>{
      node.textContent=remaining(Number(node.dataset.seconds??node.dataset.stepSeconds),node.dataset.held==="true");
    });
  }
  function switchTab(value){
    tab=value;
    for(const key of ["follow","videos","alerts"])$("panel-"+key).hidden=key!==tab;
    document.querySelectorAll("[data-tab]").forEach(b=>{if(b.dataset.tab===tab)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
    $("controls").hidden=tab!=="follow";
  }
  async function command(action,items=[]){
    if(busy||stale())return;
    busy=true;++serial;tick();
    try{
      const value=await request("/api/commands/"+action,"POST",{ids:items.map(i=>i.id),revisions:Object.fromEntries(items.map(i=>[i.id,i.revision])),active_runs:action==="stop"?Object.fromEntries(items.map(i=>[i.id,i.active_run])):null});
      data=value;received=performance.now();message(action==="stop"?"Arrêt demandé. La file reste en pause.":action==="retry"?"Vidéo remise en file. Reprenez la file lorsqu’elle est en pause.":"");render();
    }catch(error){message(error.name==="AbortError"?"Réponse interrompue. Actualisez pour vérifier si la commande a été appliquée.":error.message);received=-Infinity;}
    finally{busy=false;tick();}
  }
  function confirm(title,text,action){
    if($("confirm").open)return;
    $("confirm-title").textContent=title;$("confirm-text").textContent=text;dialogAction=action;$("confirm").returnValue="";$("confirm").showModal();
  }
  $("confirm").addEventListener("close",()=>{const fn=dialogAction;dialogAction=null;if($("confirm").returnValue==="confirm")fn?.();});
  $("pause").addEventListener("click",()=>command(data.paused?"resume":"pause"));
  $("stop").addEventListener("click",()=>{
    const items=data.work.filter(i=>i.status==="active"&&!i.stopping).map(i=>({...i}));
    confirm("Arrêter les étapes actives ?","La file sera mise en pause et "+items.length+" étape(s) seront interrompues. Les vidéos déjà produites sont conservées.",()=>command("stop",items));
  });
  document.addEventListener("click",event=>{
    const retry=event.target.closest("[data-retry]"),play=event.target.closest("[data-play]"),nav=event.target.closest("[data-tab]");
    if(nav){switchTab(nav.dataset.tab);return;}
    if(retry){
      const item=data.work.find(i=>i.id===retry.dataset.retry);
      if(item)confirm("Reprendre cette vidéo ?","Les étapes interrompues ou en erreur de « "+item.name+" » seront relancées. Les étapes terminées sont conservées.",()=>command("retry",[{...item}]));
    }
    if(play){
      const item=data.results.find(i=>i.id===play.dataset.play),url=safeMedia(item?.video_url);
      if(!url)return;
      $("player-title").textContent=item.name;$("player-error").textContent="";
      $("video").src=url;$("video").poster=safeMedia(item.poster_url);$("player").showModal();
      $("video").play().catch(()=>{});
    }
  });
  function closeVideo(){$("video").pause();$("video").removeAttribute("src");$("video").load();}
  $("close-player").onclick=()=>$("player").close();$("player").addEventListener("close",closeVideo);
  $("video").addEventListener("error",()=>{$("player-error").textContent="Lecture indisponible. Vérifiez la connexion ; vous pouvez réessayer.";});
  $("refresh").onclick=()=>refresh();
  $("more").onclick=()=>{limit=Math.min(200,limit+24);refresh();};
  function decodeKey(key){const raw=atob(key.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-key.length%4)%4));return Uint8Array.from(raw,c=>c.charCodeAt(0));}
  async function setupPush(){
    try{
      push=await request("/api/push"+(subscriptionId?"?id="+encodeURIComponent(subscriptionId):""));
      const supported=isSecureContext&&location.protocol==="https:"&&"serviceWorker" in navigator&&"PushManager" in window&&"Notification" in window;
      $("notifications").disabled=!supported||!push.available;
      $("notification-status").textContent=!isSecureContext||location.protocol!=="https:"?"Ouvrez l’adresse HTTPS Tailscale pour activer les notifications.":!supported?"Ce navigateur ne prend pas en charge les notifications.":push.warning||push.last_error||(push.registered?"Notifications activées sur ce téléphone.":"À activer une fois sur ce téléphone.");
      if(supported)registration=await navigator.serviceWorker.register("/sw.js");
      if(push.thresholds){$("threshold-local").value=push.thresholds.local_gpu;$("threshold-remote").value=push.thresholds.remote_gpu;}
      $("notifications").textContent=push.registered?"Enregistrer les seuils":"Activer les notifications";
      $("disable-notifications").hidden=!push.registered;
      if(supported&&Notification.permission==="denied")$("notification-status").textContent="Notifications bloquées dans le navigateur. Autorisez-les dans les paramètres du site.";
      if(data)render();
    }catch{$("notification-status").textContent="Réglages des notifications indisponibles ; actualisez la page.";}
  }
  $("notification-form").addEventListener("submit",async event=>{
    event.preventDefault();
    if(!push?.available)return;
    $("notifications").disabled=true;
    try{
      const permission=await Notification.requestPermission();
      if(permission!=="granted")throw new Error("Autorisation de notification non accordée.");
      registration=await navigator.serviceWorker.ready;
      let subscription=await registration.pushManager.getSubscription();
      if(subscription&&!push.registered&&subscriptionId){await subscription.unsubscribe();subscription=null;}
      if(subscription){
        const actual=subscription.options.applicationServerKey;
        const expected=decodeKey(push.public_key);
        if(actual&&([...new Uint8Array(actual)].join()!==[...expected].join())){await subscription.unsubscribe();subscription=null;}
      }
      subscription=subscription||await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decodeKey(push.public_key)});
      const response=await request("/api/push","POST",{subscription:subscription.toJSON(),thresholds:{local_gpu:Number($("threshold-local").value),remote_gpu:Number($("threshold-remote").value)}});
      subscriptionId=response.id;saved("factory-mobile-subscription",subscriptionId);await setupPush();
    }catch(error){$("notification-status").textContent=error.message;}
    finally{$("notifications").disabled=false;}
  });
  $("disable-notifications").onclick=async()=>{
    try{
      if(subscriptionId)await request("/api/push/"+encodeURIComponent(subscriptionId),"DELETE");
      const subscription=await registration?.pushManager.getSubscription();await subscription?.unsubscribe();
      subscriptionId=null;saved("factory-mobile-subscription",null);await setupPush();
    }catch(error){$("notification-status").textContent=error.message;}
  };
  window.addEventListener("beforeinstallprompt",event=>{event.preventDefault();installPrompt=event;$("install").hidden=false;});
  $("install").onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$("install").hidden=true;}};
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  window.addEventListener("online",()=>{refresh();setupPush();});
  refresh();setupPush();setInterval(()=>{if(!document.hidden)refresh();},5000);setInterval(tick,1000);
})();
