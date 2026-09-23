(() => {
  "use strict";
  const node = (tag, text = "", cls = "") => {const n=document.createElement(tag); n.textContent=text; n.className=cls; return n;};
  const button = (text, action) => {const n=node("button",text); n.type="button"; n.addEventListener("click",action); return n;};
  const field = (label, control, help) => {const n=node("label",label); n.append(control); if(help)n.append(node("small",help)); return n;};
  const input = (value="", area=false) => {const n=node(area ? "textarea" : "input"); n.value=value ?? ""; if(area)n.rows=2; return n;};
  const select = (entries, value) => {const n=node("select"); for(const [id,label] of entries)n.append(new Option(label,id)); n.value=String(value); return n;};
  const freshState = () => ({id:`state-${crypto.randomUUID()}`,scene_index:0,at:"start",appearance:null,clothing:null,holder_id:null,reference:false});
  const labelState = (state, characters) => [state.appearance,state.clothing,
    state.holder_id ? (state.holder_id === "none" ? "Sans détenteur" : `Chez ${characters.find(c=>c.id===state.holder_id)?.name || state.holder_id}`) : ""].filter(Boolean).join(" · ");

  function dialog(title) {
    const box=node("dialog","","pf-continuity-dialog"), heading=node("h2",title), form=node("form"), error=node("p","","pf-continuity-error");
    const id=`continuity-title-${crypto.randomUUID()}`; heading.id=id; box.setAttribute("aria-labelledby",id);
    error.setAttribute("role","alert"); box.append(heading,form,error); document.body.append(box);
    box.addEventListener("close",()=>box.remove()); box.showModal();
    return {box,form,error,async save(work) {const controls=[...form.querySelectorAll("button,input,textarea,select")];
      const was=controls.map(c=>c.disabled); controls.forEach(c=>c.disabled=true); error.textContent="";
      try {await work(); box.close();} catch(e) {error.textContent=e.message || String(e); controls.forEach((c,i)=>c.disabled=was[i]);}
    }};
  }

  function editElement(options, data, element, isNew=false) {
    const d=dialog(isNew ? "Suivre un élément important" : `Continuité · ${element.name}`), e=structuredClone(element);
    const name=input(e.name), description=input(e.description,true), reason=input(e.reason,true);
    name.required=true; name.maxLength=120; name.readOnly=e.kind==="character";
    description.required=true; description.maxLength=3000; reason.required=true; reason.maxLength=1500;
    const tracking=select([["text","Suivi textuel"],["reference","Image de référence"]],e.tracking);
    d.form.append(field("Nom",name),field("Identité visuelle stable",description,"Forme et attributs à reconnaître. Les changements se règlent ci-dessous."),
      field("Pourquoi le suivre ?",reason,"Ex. : reconnaître l'invention volée ; conserver la carrure après la transformation."),
      field("Niveau de suivi",tracking,"Le texte suffit pour les accessoires simples. Une image sert aux objets distinctifs et aux grandes transformations."));
    const presence=node("fieldset"), legend=node("legend","Visible dans ces scènes"); presence.append(legend);
    const sceneChecks=options.scenes.map((scene,i)=>{const c=input(); c.type="checkbox"; c.checked=e.scene_indices.includes(i);
      presence.append(field(`${i+1} · ${scene.title}`,c)); return c;});
    presence.className="pf-continuity-presence"; d.form.append(presence);
    const states=node("div","","pf-continuity-states"); let stateFields=[];
    function collectStates() {return stateFields.map(({value,date,at,appearance,clothing,holder,reference})=>({...value,
      scene_index:Number(date.value),at:at.value,appearance:appearance.value.trim() || null,
      clothing:clothing?.value.trim() || null,holder_id:holder?.value || null,
      reference:tracking.value==="reference" && reference.checked}));}
    function drawStates() {
      states.replaceChildren(); stateFields=[];
      e.states.forEach((value,index)=>{
        const row=node("fieldset"), legend=node("legend",index ? "Changement d'état" : "État de départ"); row.append(legend);
        const date=select(options.scenes.map((s,i)=>[i,`${i+1} · ${s.title}`]),value.scene_index),
          at=select([["start","Déjà acquis au début"],["end","Acquis pendant la scène"]],value.at),
          appearance=input(value.appearance,true), clothing=e.kind==="character" ? input(value.clothing,true) : null,
          holder=e.kind==="object" ? select([["","Détenteur inchangé"],["none","Sans détenteur"],...options.characters.map(c=>[c.id,c.name])],value.holder_id || "") : null,
          reference=input(); reference.type="checkbox"; reference.checked=value.reference; reference.disabled=tracking.value!=="reference";
        appearance.maxLength=1500; if(clothing)clothing.maxLength=1500;
        const dates=node("div","","pf-continuity-actions"); dates.append(field("À partir de",date),field("Moment",at)); row.append(dates);
        row.append(field(e.kind==="character" ? "Physique / apparence" : "Aspect / état de l'objet",appearance,"Laisser vide conserve l'état précédent."));
        if(clothing)row.append(field("Tenue",clothing,"Indépendante du physique : une déchirure reste acquise jusqu'à un changement explicite."));
        if(holder)row.append(field("Détenteur",holder));
        row.append(field("Préparer une image pour cet état",reference,"Réserver aux changements importants qui doivent rester reconnaissables. Aucun rendu n'est lancé ici."));
        const remove=button("Retirer ce changement",()=>{e.states=collectStates(); e.states.splice(index,1); drawStates();}); remove.disabled=e.states.length===1;
        row.append(remove); states.append(row); stateFields.push({value,date,at,appearance,clothing,holder,reference});
      });
    }
    drawStates(); tracking.addEventListener("change",()=>stateFields.forEach(row=>row.reference.disabled=tracking.value!=="reference"));
    const add=button("Ajouter un changement",()=>{
      e.states=collectStates(); const next=freshState(); const used=new Set(e.states.map(s=>`${s.scene_index}:${s.at}`));
      let found=false; for(let i=0;i<options.scenes.length && !found;i++)for(const at of ["start","end"])if(!used.has(`${i}:${at}`)) {next.scene_index=i; next.at=at; found=true; break;}
      if(found) {e.states.push(next); drawStates();}
    });
    const actions=node("div","","pf-continuity-actions"), save=node("button","Enregistrer"); save.type="submit";
    actions.append(button("Annuler",()=>d.box.close()),save); d.form.append(states,add,actions);
    d.form.addEventListener("submit",event=>{event.preventDefault(); if(!d.form.reportValidity())return;
      const changed={...e,name:name.value.trim(),description:description.value.trim(),reason:reason.value.trim(),tracking:tracking.value,
        scene_indices:sceneChecks.flatMap((c,i)=>c.checked ? [i] : []),states:collectStates()};
      const next=structuredClone(data); const i=next.elements.findIndex(x=>x.id===changed.id);
      if(i<0)next.elements.push(changed); else next.elements[i]=changed;
      d.save(()=>options.onSave(next,options.revision));
    });
  }

  function addElement(options,data) {
    const d=dialog("Quel élément suivre ?");
    d.form.append(node("p","Choisis un personnage dont l'apparence change, ou un objet important pour comprendre l'histoire."));
    const pick=select([["object","Un objet important"],...options.characters.filter(c=>!data.elements.some(e=>e.id===c.id)).map(c=>[c.id,c.name])],"object");
    d.form.append(field("Élément",pick));
    const actions=node("div","","pf-continuity-actions"); actions.append(button("Annuler",()=>d.box.close()),button("Continuer",()=>{
      const c=options.characters.find(c=>c.id===pick.value), e={id:c?.id || `object-${crypto.randomUUID()}`,kind:c ? "character" : "object",
        name:c?.name || "",description:c?.description || "",reason:"",tracking:"text",
        scene_indices:c ? options.scenes.flatMap((s,i)=>s.character_ids?.includes(c.id) ? [i] : []) : [],states:[freshState()]};
      d.box.close(); editElement(options,data,e,true);
    })); d.form.append(actions);
  }

  function render(host,options) {
    if(!host)return;
    const data=structuredClone(options.data || {version:1,dramatic_summary:"",elements:[]});
    const key=JSON.stringify([options.identity,options.revision,data,options.disabled,options.references?.map(r=>[r.id,r.revision,r.image_asset_id,r.qwen_variant])]);
    if(host._continuityKey===key)return; host._continuityKey=key;
    const wasOpen=host.querySelector("details")?.open;
    host.replaceChildren(); host.classList.add("pf-continuity");
    if(data.dramatic_summary)host.append(node("p",data.dramatic_summary,"pf-continuity-drama"));
    for(const note of data.warnings || [])host.append(node("p",note,"episode-duration-note"));
    const details=node("details"), count=data.elements.filter(e=>e.enabled!==false).length;
    details.open=!!wasOpen; details.append(node("summary",`Continuité · ${count ? `${count} élément${count>1 ? "s" : ""} suivi${count>1 ? "s" : ""}` : "aucun suivi particulier"}`));
    details.append(node("p",options.disabled ? "Les traitements en cours conservent leurs références. Les modifications seront possibles à leur fin."
      : "Les états acquis se conservent d'une scène à l'autre. Ajoute une image seulement si elle aide à reconnaître un élément important.","pf-continuity-help"));
    if(options.references)details.append(node("p","Les variantes ne sont pas cochées dans le lot initial : choisis d'abord l'image d'identité, puis prépare la transformation avec Qwen ou importe une image. Les ajustements ici concernent cette fabrication.","pf-continuity-help"));
    const message=node("p","","pf-continuity-error"); message.setAttribute("role","alert");
    const invoke=work=>async()=>{message.textContent=""; try {await work();} catch(e) {message.textContent=e.message || String(e);}};
    for(const e of data.elements) {
      const row=node("article","",`pf-continuity-row${e.enabled===false ? " pf-continuity-ignored" : ""}`);
      row.append(node("strong",`${e.name} · ${e.enabled===false ? "ignoré" : e.tracking==="reference" ? "avec référence" : "suivi textuel"}`));
      row.append(node("p",e.reason,"pf-continuity-help"));
      for(const s of e.states)row.append(node("p",`Scène ${s.scene_index+1}, ${s.at==="end" ? "à la fin" : "au début"} : ${labelState(s,options.characters) || "état précédent conservé"}`));
      const actions=node("div","","pf-continuity-actions");
      actions.append(button("Corriger",()=>editElement(options,data,e)),button(e.enabled===false ? "Réactiver" : "Ignorer",invoke(async()=>{
        const next=structuredClone(data); next.elements.find(x=>x.id===e.id).enabled=e.enabled===false;
        await options.onSave(next,options.revision);
      })));
      if(e.enabled!==false && e.tracking==="reference") {
        const refs=(options.references || []).filter(r=>r.continuity_element_id===e.id && !r.continuity_archived);
        for(const r of refs) {
          const label=r.continuity_state_id ? "Variante" : "Objet";
          const a=button(`${r.image_asset_id ? "✓" : "+"} ${label} · choisir une image`,invoke(()=>options.onReference?.(r)));
          a.title=r.name; actions.append(a);
          if(r.continuity_state_id && options.onVariant)actions.append(button("Modifier avec Qwen",invoke(()=>options.onVariant(r))));
          if(r.qwen_variant && options.onResults)actions.append(button("Résultats Qwen",invoke(()=>options.onResults(r))));
        }
        if(!options.references)row.append(node("small","Les fiches et variantes seront disponibles dans Fabrication."));
      }
      actions.querySelectorAll("button").forEach(b=>b.disabled=!!options.disabled); row.append(actions); details.append(row);
    }
    const actions=node("div","","pf-continuity-actions"); actions.append(button("Suivre un élément",()=>addElement(options,data)),button("Préciser le drame",()=>{
      const d=dialog("Ce que le public doit comprendre"), text=input(data.dramatic_summary,true); text.maxLength=1500;
      d.form.append(field("En une phrase",text,"Ex. : le fils croit à une visite ; le public comprend que sa copine le trompe avec son père."));
      const save=node("button","Enregistrer"); save.type="submit"; d.form.append(button("Annuler",()=>d.box.close()),save);
      d.form.addEventListener("submit",event=>{event.preventDefault(); d.save(()=>options.onSave({...data,dramatic_summary:text.value.trim()},options.revision));});
    })); actions.querySelectorAll("button").forEach(b=>b.disabled=!!options.disabled);
    details.append(actions,message); host.append(details);
  }

  function resultsDialog(results,onSelect) {
    const d=dialog("Choisir une variante Qwen"), grid=node("div","","pf-continuity-results");
    if(!results.length)grid.append(node("p","Aucun résultat terminé. Génère la variante dans l'atelier Qwen, puis reviens ici."));
    for(const result of results) {const row=node("article"), image=node("img"); image.src=`/api/assets/${encodeURIComponent(result.asset_id)}/content`; image.alt=result.label; image.loading="lazy";
      row.append(image,button(`Utiliser · ${result.label}`,()=>d.save(()=>onSelect(result.asset_id)))); grid.append(row);}
    d.form.append(grid,button("Fermer",()=>d.box.close()));
  }
  window.PanelForgeContinuity={render,resultsDialog};
})();
