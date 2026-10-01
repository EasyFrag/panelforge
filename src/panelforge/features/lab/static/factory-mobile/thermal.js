(() => {
  "use strict";
  const finite=v=>typeof v==="number"&&Number.isFinite(v);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const L=30,R=328,T=16,B=146,LOW=60,HIGH=90;
  const y=v=>B-(Math.max(LOW,Math.min(HIGH,v))-LOW)/(HIGH-LOW)*(B-T);
  const fmt=v=>Number(v).toLocaleString("fr-FR",{maximumFractionDigits:1});
  const clock=t=>new Date(t*1000).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});
  function recentExceedances(points,limit,gap){
    const episodes=[];let current=null;
    for(const point of points){
      if(point[1]<limit){current=null;continue;}
      if(!current||point[0]-current.last>gap){
        current={last:point[0],peakAt:point[0],peak:point[1]};episodes.push(current);
      }else{
        current.last=point[0];
        if(point[1]>=current.peak){current.peak=point[1];current.peakAt=point[0];}
      }
    }
    return episodes.slice(-3).reverse();
  }
  function render(container,history,thresholds={}){
    const end=history?.end_at||Date.now()/1000,start=history?.start_at||end-7200;
    const x=t=>L+(t-start)/(end-start)*(R-L);
    const gap=Math.max(45,(history?.bucket_seconds||15)*3);
    const series=new Map((history?.machines||[]).map(m=>[m.id,m]));
    const specs=[["remote_gpu","Serveur",84],["local_gpu","PC local",80]];
    const datasets=new Map();
    container.innerHTML=specs.map(([id,name,fallback])=>{
      const limit=finite(thresholds[id])?thresholds[id]:fallback;
      const points=(series.get(id)?.points||[]).filter(p=>Array.isArray(p)&&finite(p[0])&&finite(p[1])&&p[0]>=start&&p[0]<=end);
      datasets.set(id,points);
      const maximum=points.length?Math.max(...points.map(p=>p[1])):null;
      const exceedances=recentExceedances(points,limit,gap);
      const paths={cool:"",warm:"",hot:"",outside:""};
      const tone=v=>v<LOW?"outside":v>=limit?"hot":v>=limit-4?"warm":"cool";
      let dots="";
      points.forEach((p,i)=>{
        const px=x(p[0]).toFixed(2),py=y(p[1]).toFixed(2),previous=points[i-1];
        if(previous&&p[0]-previous[0]<=gap){
          const color=p[1]<LOW&&previous[1]<LOW?"outside":tone(Math.max(p[1],previous[1]));
          paths[color]+="M"+x(previous[0]).toFixed(2)+","+y(previous[1]).toFixed(2)+"L"+px+","+py;
        }else dots+='<circle class="thermal-line '+tone(p[1])+'" cx="'+px+'" cy="'+py+'" r="1.5"/>';
      });
      const grid=[60,70,80,90].map(v=>'<line class="thermal-grid" x1="'+L+'" x2="'+R+'" y1="'+y(v)+'" y2="'+y(v)+'"/><text x="23" y="'+(y(v)+3)+'" text-anchor="end">'+v+'</text>').join("");
      const ticks=[["−2 h",L,"start"],["−1 h",(L+R)/2,"middle"],["maint.",R,"end"]].map(([label,at,anchor])=>'<text x="'+at+'" y="166" text-anchor="'+anchor+'">'+label+'</text>').join("");
      const caption=points.length?"Pic "+fmt(maximum)+" °C · seuil "+fmt(limit)+" °C":"Aucune mesure sur cette période";
      const warning=history?.warning?" · historique partiel":"";
      const exceedanceList=exceedances.length?'<ul>'+exceedances.map(value=>'<li><time>'+clock(value.peakAt)+'</time><strong>'+fmt(value.peak)+'°</strong></li>').join("")+'</ul>':'<span>Aucun sur 2 h</span>';
      return '<article class="card thermal-card" data-thermal="'+id+'"><div class="thermal-heading"><h3>'+name+'</h3><span>'+(points.length?"Pic "+fmt(maximum)+" °C":"2 heures")+'</span></div>'+
        '<div class="thermal-chart"><svg viewBox="0 0 340 174" role="img" tabindex="0" aria-label="'+esc(name+' : températures des deux dernières heures, de 60 à 90 degrés. '+caption+warning+'. Touchez la courbe ou utilisez les flèches pour lire une mesure.')+'">'+
        '<rect class="thermal-band cool" x="'+L+'" y="'+T+'" width="'+(R-L)+'" height="'+(B-T)+'"/>'+
        '<rect class="thermal-band warm" x="'+L+'" y="'+y(limit)+'" width="'+(R-L)+'" height="'+(y(limit-4)-y(limit))+'"/>'+
        '<rect class="thermal-band hot" x="'+L+'" y="'+T+'" width="'+(R-L)+'" height="'+(y(limit)-T)+'"/>'+grid+
        (limit>=LOW&&limit<=HIGH?'<line class="thermal-limit" x1="'+L+'" x2="'+R+'" y1="'+y(limit)+'" y2="'+y(limit)+'"/>':"")+
        Object.entries(paths).map(([color,d])=>'<path class="thermal-line '+color+'" d="'+d+'"/>').join("")+dots+
        '<g class="thermal-cursor" hidden><line y1="'+T+'" y2="'+B+'"/><circle r="3"/></g>'+ticks+'</svg></div>'+
        '<div class="thermal-caption"><span>Seuil '+fmt(limit)+' °C</span></div>'+
        '<div class="thermal-exceedances"><b>Derniers dépassements</b>'+exceedanceList+'</div>'+
        '<p class="thermal-reading" aria-live="polite">'+(points.length?"Touchez la courbe pour lire une mesure":"L’historique apparaîtra avec les premières mesures.")+'</p></article>';
    }).join("");
    container.querySelectorAll("[data-thermal]").forEach(card=>{
      const points=datasets.get(card.dataset.thermal),svg=card.querySelector("svg"),cursor=card.querySelector(".thermal-cursor"),reading=card.querySelector(".thermal-reading");
      let index=Math.max(0,points.length-1);
      function choose(next){
        if(!points.length)return;
        index=Math.max(0,Math.min(points.length-1,next));
        const p=points[index],px=x(p[0]),py=y(p[1]);
        cursor.removeAttribute("hidden");
        const line=cursor.querySelector("line"),dot=cursor.querySelector("circle");
        line.setAttribute("x1",px);line.setAttribute("x2",px);
        dot.setAttribute("cx",px);dot.setAttribute("cy",py);
        reading.textContent=clock(p[0])+" · "+fmt(p[1])+" °C";
      }
      function point(event){
        if(!points.length)return;
        const bounds=svg.getBoundingClientRect(),at=start+((event.clientX-bounds.left)/bounds.width*340-L)/(R-L)*(end-start);
        let nearest=0;
        for(let i=1;i<points.length;i++)if(Math.abs(points[i][0]-at)<Math.abs(points[nearest][0]-at))nearest=i;
        choose(nearest);
      }
      svg.addEventListener("pointerdown",point);
      svg.addEventListener("pointermove",event=>{if(event.pointerType==="mouse"||event.buttons)point(event);});
      svg.addEventListener("keydown",event=>{
        if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;
        event.preventDefault();choose(event.key==="Home"?0:event.key==="End"?points.length-1:index+(event.key==="ArrowRight"?1:-1));
      });
    });
  }
  window.PanelForgeMobileThermal=Object.freeze({render});
})();
