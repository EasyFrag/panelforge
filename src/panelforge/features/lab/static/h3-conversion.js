(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const core = window.PanelForgeLabCore;
  if (!$('h3r-convert-ref2v') || !core) return;
  const panel = $('h3-conversion-panel'), status = $('h3-conversion-status');
  const file = $('h3-conversion-image'), start = $('h3-conversion-start');
  const open = $('h3-conversion-open'), draft = $('h3-conversion-draft');
  let snapshot = null, pending = null, busy = false, target = null;
  const mounts = {};
  for (const [prefix, event] of [['ref2vd', 'panelforge:ref2v-context'], ['i2vd', 'panelforge:h3-base-context']]) {
    const lab = $(prefix === 'ref2vd' ? 'ref2vr-lab' : 'h3r-lab');
    mounts[prefix] = {lab, parent: lab.parentNode, next: lab.nextSibling};
    window.addEventListener(event, e => {
      if (e.detail?.project_id) return;
      const mount = mounts[prefix];
      mount.parent.insertBefore(lab, mount.next);
      $(prefix + '-adapted-host').hidden = true;
    });
  }
  async function json(url, body) {
    return core.request(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  }
  function showProject(project, source = false) {
    const prefix = source ? 'i2vd' : 'ref2vd', mount = mounts[prefix];
    const host = $(prefix + '-adapted-host');
    // This host is independent of any selected Brief or Plan.
    host.replaceChildren(); host.hidden = false;
    const title = document.createElement('h2');
    title.textContent = source ? 'Atelier H3 d’origine' : 'Atelier adapté en REF2V'; host.append(title);
    if (project.adaptation) {
      const info = document.createElement('p');
      info.textContent = 'Les rôles début / fin guident REF2V ; ils ne verrouillent pas les frames comme FL2VA.';
      host.append(info);
      const back = document.createElement('button'); back.type = 'button'; back.textContent = 'Ouvrir l’atelier H3 d’origine';
      back.addEventListener('click', async () => {
        try { showProject((await core.request(`/api/h3-render/projects/${encodeURIComponent(project.adaptation.source_project_id)}`)).project, true); }
        catch (error) { info.textContent = error.message; }
      }); host.append(back);
      const refs = document.createElement('div'); refs.className = 'h3-adaptation-references';
      for (const [i, ref] of (project.references || []).entries()) {
        const figure = document.createElement('figure'), img = document.createElement('img'), label = document.createElement('figcaption');
        img.src = ref.url || ref.content_url || `/api/assets/${encodeURIComponent(ref.asset_id)}/content`;
        img.alt = ref.label || `Image ${i + 1}`; img.loading = 'lazy';
        label.textContent = `${ref.label || `Image ${i + 1}`} · ${project.adaptation.reference_roles[i]}`;
        figure.append(img, label); refs.append(figure);
      } host.append(refs);
      if (project.adaptation.status !== 'ready') {
        const error = document.createElement('p');
        error.textContent = `${project.adaptation.error || `Adaptation ${project.adaptation.status}.`} Le prompt source est conservé. Retournez à H3 et cliquez sur Adapter en REF2V pour demander un nouvel appel.`;
        const raw = document.createElement('pre'); raw.className = 'trace-output'; raw.textContent = project.adaptation.raw_response || '';
        host.append(error, raw);
      }
    }
    host.append(mount.lab);
    document.querySelector(`[data-lab-view="${source ? 'i2v-direct' : 'ref2v-direct'}"]`)?.click();
    window.dispatchEvent(new CustomEvent(source ? 'panelforge:h3-base-context' : 'panelforge:ref2v-context', {detail: {project_id: project.project_id}}));
    host.scrollIntoView({block: 'start', behavior: 'smooth'});
  }
  async function refresh() {
    const list = $('h3-adaptations-list');
    try {
      const payload = await core.request('/api/h3-render/adaptations');
      list.replaceChildren();
      for (const project of payload.projects) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'h3-adaptation-entry';
        const label = (project.references || []).map(ref => ref.label).filter(Boolean).join(' / ');
        button.textContent = `${label || project.project_id} · ${project.adaptation.status}`;
        button.addEventListener('click', async () => {
          try { showProject((await core.request(`/api/h3-render/projects/${encodeURIComponent(project.project_id)}`)).project); }
          catch (error) { button.textContent = error.message; }
        }); list.append(button);
      }
    } catch (error) { list.textContent = error.message; }
  }
  async function convert() {
    if (busy || !snapshot) return;
    busy = true; start.disabled = true; target = null; open.hidden = true; draft.textContent = '';
    const current = snapshot;
    try {
      if (!current.project.first_frame && !current.project.last_frame && !pending.extra_reference_asset_id) {
        if (!file.files[0]) throw new Error('Choisissez une image de référence.');
        const body = new FormData(); body.append('image', file.files[0]);
        const uploaded = await core.request(`/api/h3-render/projects/${encodeURIComponent(current.project.project_id)}/adaptation-reference`, {method: 'POST', body});
        pending.extra_reference_asset_id = uploaded.asset_id; pending.extra_reference_label = uploaded.label;
      }
      status.textContent = 'Préparation de l’atelier REF2V…';
      const prepared = await json(`/api/h3-render/projects/${encodeURIComponent(current.project.project_id)}/adapt-ref2v`, pending);
      target = prepared.project;
      status.textContent = prepared.warnings?.join(" ") || 'Adaptation du prompt en cours… Vous pouvez continuer dans les autres ateliers.';
      await core.streamRequest(`/api/h3-render/projects/${encodeURIComponent(target.project_id)}/adapt-ref2v/stream?include_reasoning=${current.include_reasoning}`, {method: 'POST'}, event => {
        if (event.text) draft.textContent += event.text;
        if (event.project) target = event.project;
      }, {completionTone: true});
      if (target.adaptation.status !== 'ready') throw new Error(target.adaptation.error || 'Adaptation non terminée. Le candidat reste conservé.');
      status.textContent = ['Adaptation prête. Aucun rendu vidéo lancé.', ...(prepared.warnings || [])].join(' ');
      open.hidden = false; start.hidden = true;
    } catch (error) {
      status.textContent = error.message;
      if (target) {
        try { target = (await core.request(`/api/h3-render/projects/${encodeURIComponent(target.project_id)}`)).project; } catch (_) { /* keep known draft */ }
        open.hidden = false;
      }
      start.hidden = false; start.textContent = 'Reprendre l’enregistrement';
      // Reuse the same ID. The server never repeats an already started LLM call.
    } finally { busy = false; start.disabled = false; refresh(); }
  }
  window.addEventListener('panelforge:convert-h3', event => {
    panel.hidden = false;
    if (busy) { status.textContent = 'Une adaptation est déjà en cours ; son résultat restera dans la liste REF2V.'; return; }
    snapshot = structuredClone(event.detail);
    pending = {...snapshot.settings, model_id: snapshot.model_id, request_id: crypto.randomUUID()};
    const needsImage = !snapshot.project.first_frame && !snapshot.project.last_frame;
    $('h3-conversion-image-label').hidden = !needsImage;
    start.hidden = !needsImage; start.textContent = 'Adapter avec cette référence';
    open.hidden = true; target = null; draft.textContent = '';
    if (needsImage) status.textContent = 'Le prompt et les réglages courants sont prêts. Ajoutez une référence pour REF2V.';
    else convert();
  });
  start.addEventListener('click', convert);
  open.addEventListener('click', () => { if (target) showProject(target); });
  $('h3-adaptations-refresh').addEventListener('click', refresh);
  document.querySelector('[data-lab-view="ref2v-direct"]')?.addEventListener('click', refresh);
})();
