(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const workspace = $('ref2vd-workspace'), panel = $('dance-workshop');
  if (!workspace || !panel || !window.PanelForgeH3Render) return;
  const original = $('ref2vr-lab');
  const lab = original.cloneNode(true);
  for (const node of [lab, ...lab.querySelectorAll('*')]) {
    for (const attr of [...node.attributes]) {
      if (attr.value.includes('ref2vr')) node.setAttribute(attr.name, attr.value.replaceAll('ref2vr', 'dancer'));
    }
  }
  lab.hidden = true;
  $('dance-render-host').append(lab);
  lab.querySelector('.h3-render-heading h3').textContent = 'Essayer la danse';
  lab.querySelector('.h3-render-heading p').textContent = 'Le rendu complet de la recette choisie. Aperçu rapide facultatif dans les réglages.';
  lab.querySelector('.h3-render-conversation')?.setAttribute('hidden', '');
  lab.querySelector('.h3-render-history small').textContent = 'Chaque essai conserve son prompt, sa seed et sa recette.';
  $('dancer-duration').closest('label').hidden = true;
  $('dancer-music').closest('label').hidden = true;
  const advanced = document.createElement('details'); advanced.className = 'h3-render-fold';
  const summary = document.createElement('summary'); summary.textContent = 'Réglages du rendu'; advanced.append(summary);
  const setup = lab.querySelector('.h3-render-setup'); setup.after(advanced);
  for (const node of [setup.querySelector('.h3-checkpoint-panel'), setup.querySelector('.h3-preset-picker'),
    $('dancer-preset-summary'), $('dancer-bunny-geometry'), lab.querySelector('.h3-render-settings'),
    lab.querySelector('.h3-video-lora'), lab.querySelector('.h3-sampling-details')]) if (node) advanced.append(node);
  advanced.append($('dance-preview-option'));
  const quickPreview = $('dance-quick-preview');
  const promptBox = lab.querySelector('.h3-render-prompt');
  promptBox.append($('dance-prompt-tools'));
  const localModelToggle = lab.querySelector('[data-llm-local-for="dancer-revision-model"]');
  $('dance-model-host').append($('dancer-revision-model'));
  if (localModelToggle) $('dance-model-host').after(localModelToggle.closest('label'));

  let project = null, uploaded = null, busy = false, generation = 0;
  let imageUrl = null, videoUrl = null, sourceKey = '';
  const activeStatuses = new Set(['queued', 'running', 'cancel_pending']);
  const readMemory = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
  function status(message, error = false) { $('dance-status').textContent = message; $('dance-status').classList.toggle('error-text', error); }
  async function request(url, init = {}) {
    const response = await fetch(url, init);
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Les informations envoyées sont invalides.');
    return result;
  }
  const json = body => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  function excerptIssue() {
    const start = $('dance-start').valueAsNumber, duration = $('dance-duration').valueAsNumber;
    if (!Number.isFinite(start) || start < 0) return {field: 'dance-start', message: 'Indique un début d’extrait supérieur ou égal à 0.'};
    if (!Number.isFinite(duration) || duration < Number($('dance-duration').min) || duration > Number($('dance-duration').max)) {
      return {field: 'dance-duration', message: 'Choisis une durée de 5,2 à 15 secondes.'};
    }
    if (uploaded && start > uploaded.duration_seconds - 124 / 24) {
      return {field: 'dance-start', message: 'Ce début laisse moins de 5,2 secondes disponibles. Choisis une position plus tôt.'};
    }
    if (uploaded && start + duration > uploaded.duration_seconds + 0.05) {
      return {field: 'dance-duration', message: 'L’extrait dépasse la fin de la vidéo. Réduis la durée ou avance le début.'};
    }
    return null;
  }
  function controls() {
    const locked = busy || Boolean(project?.attempts.some(a => activeStatuses.has(a.status)));
    for (const id of ['dance-new','dance-history','dance-create','dance-save-prompt','dance-polish','dance-apply']) $(id).disabled = locked;
    for (const button of panel.querySelectorAll('[data-dance-finalize]')) button.disabled = locked;
    for (const id of ['dance-image','dance-video','dance-start','dance-duration','dance-title']) $(id).disabled = busy;
    const issue = excerptIssue(), note = $('dance-excerpt-note');
    for (const id of ['dance-start','dance-duration']) $(id).setAttribute('aria-invalid', String(issue?.field === id));
    note.textContent = issue?.message || 'De 5,2 à 15 s. La durée est ajustée légèrement à la grille du modèle, sans dépasser l’extrait choisi.';
    note.classList.toggle('error-text', Boolean(issue));
    $('dance-create').disabled ||= Boolean(issue) || !uploaded || !$('dance-image').files.length;
  }
  function displaySources(value) {
    const ref = value.dance_reference;
    const key = value.project_id;
    if (sourceKey !== key) {
      $('dance-photo-preview').src = value.references[0].content_url;
      $('dance-clip-preview').src = `/api/assets/${encodeURIComponent(ref.clip_asset_id)}/content`;
      sourceKey = key;
    }
    $('dance-sources').hidden = false; $('dance-inputs').hidden = true;
    $('dance-source-note').textContent = `${ref.label} · ${ref.duration_seconds.toFixed(2)} s · ${ref.keep_audio && ref.has_audio ? 'son de l’extrait' : 'sans son'}`;
  }
  const renderer = window.PanelForgeH3Render.mount('dancer', 'panelforge:dance-context', 'ref2va', {
    specPurpose: 'dance', raiseContextErrors: true,
    preferredRevisionModel(models) {
      const saved = readMemory('panelforge.dance.model');
      return models.find(m => m.id === saved)?.id || models.find(m => /gemma-4/i.test(m.id) && m.id.startsWith('local::'))?.id
        || models.find(m => /gemma-4/i.test(m.id))?.id || models[0]?.id || '';
    },
    danceStage: () => quickPreview.checked ? 'draft' : 'full',
    renderActionState: () => ({label: quickPreview.checked ? 'Générer un aperçu' : 'Générer la danse', disabled: busy}),
    onRenderControls: ({disabled}) => { quickPreview.disabled = disabled || busy; },
    prepareAttempt: (parameters) => request(`/api/h3-render/projects/${encodeURIComponent(project.project_id)}/attempts`, json({...parameters, dance_stage: quickPreview.checked ? 'draft' : 'full'})),
    onProjectChange(value) {
      project = value; displaySources(value); controls();
      $('dancer-mode').textContent = `Danse · ${value.dance_reference.duration_seconds.toFixed(2)} s`;
    },
    attemptActions(attempt, card, value) {
      if (!attempt.can_finalize || attempt.dlss) return;
      const button = document.createElement('button'); button.type = 'button'; button.dataset.danceFinalize = '';
      button.textContent = 'Finaliser cet aperçu';
      button.title = 'Réutilise ses latents, son prompt, sa seed et ses réglages. Seuls les MP finaux peuvent changer.';
      button.addEventListener('click', () => finalize(value.project_id, attempt)); card.append(button);
    }
  });
  quickPreview.addEventListener('change', () => {
    $('dancer-initial-megapixels').dispatchEvent(new Event('input'));
    renderer.refreshControls();
  });
  async function run(action) {
    if (busy) return;
    busy = true; controls(); renderer.refreshControls();
    try { await action(); } catch (error) { status(error.message, true); }
    finally { busy = false; controls(); renderer.refreshControls(); }
  }
  async function list() {
    const result = await request('/api/dance/projects');
    const select = $('dance-history'); select.replaceChildren(new Option('Ouvrir une danse…', ''));
    result.projects.forEach(p => select.add(new Option(p.title, p.id)));
    if (project) select.value = project.project_id;
    if (!result.available) status('FFmpeg est indisponible : la préparation des extraits doit être configurée.', true);
    return result.projects;
  }
  async function open(id) {
    $('dance-proposal').hidden = true;
    await renderer.open({project_id: id});
    $('dance-history').value = id; remember('panelforge.dance.project', id);
    const models = $('dancer-revision-model');
    if (!project.attempts.length) {
      const picture = $('dance-photo-preview');
      const setRatio = () => {
        if (project?.project_id !== id || !picture.naturalHeight) return;
        const ratio = picture.naturalWidth / picture.naturalHeight;
        const choices = [...$('dancer-ratio').options].map(o => {
          const [w,h] = o.value.split(' ')[0].split(':').map(Number);
          return {value:o.value, difference:Math.abs(Math.log((w/h)/ratio))};
        }).sort((a,b) => a.difference-b.difference);
        if (choices.length) $('dancer-ratio').value = choices[0].value;
        $('dancer-ratio').dispatchEvent(new Event('input'));
      };
      if (picture.complete) setRatio(); else picture.onload = setRatio;
    }
    renderer.refreshControls(); status('Photo et extrait prêts. Le prompt reste modifiable.');
  }
  async function finalize(id, attempt) {
    await run(async () => {
      const mp = Number($('dancer-megapixels').value);
      status(`Préparation de la finition de l’essai ${attempt.index}…`);
      const prepared = await request(`/api/dance/projects/${encodeURIComponent(id)}/attempts/${encodeURIComponent(attempt.attempt_id)}/finalize`, json({megapixels: mp}));
      const next = prepared.project.attempts.at(-1);
      await request(`/api/h3-render/projects/${encodeURIComponent(id)}/attempts/${encodeURIComponent(next.attempt_id)}/start`, {method:'POST'});
      await open(id); status(`Finition de l’essai ${attempt.index} en cours, depuis ses latents.`);
    });
  }
  async function selectMode(mode) {
    workspace.dataset.refMode = mode; remember('panelforge.ref2v.mode', mode);
    panel.hidden = mode !== 'dance';
    for (const button of workspace.querySelectorAll('[data-ref-mode-button]')) {
      const selected = button.dataset.refModeButton === mode;
      button.classList.toggle('active', selected); button.setAttribute('aria-pressed', String(selected));
    }
    if (mode === 'dance' && !project) await run(async () => {
      const items = await list(), previous = readMemory('panelforge.dance.project');
      if (items.some(p => p.id === previous)) await open(previous);
    });
  }
  workspace.querySelectorAll('[data-ref-mode-button]').forEach(button => button.addEventListener('click', () => selectMode(button.dataset.refModeButton)));
  window.addEventListener('panelforge:ref2v-context', event => { if (event.detail?.ready || event.detail?.project_id) selectMode('images'); });
  $('dance-history').addEventListener('change', event => { if (event.target.value) run(() => open(event.target.value)); });
  $('dance-new').addEventListener('click', () => {
    quickPreview.checked = false;
    ++generation; renderer.close(); project = null; uploaded = null; sourceKey = '';
    $('dance-inputs').hidden = false; $('dance-sources').hidden = true;
    $('dance-image').value = ''; $('dance-video').value = ''; $('dance-title').value = '';
    $('dance-start').value = '0'; $('dance-duration').value = '8'; $('dance-audio').checked = true; $('dance-audio').disabled = false;
    $('dance-image-preview').hidden = true;
    $('dance-history').value = ''; $('dance-import-preview').hidden = true;
    remember('panelforge.dance.project', ''); status('Choisis une photo avec le personnage en pied et son décor, puis un extrait de danse.'); controls();
  });
  $('dance-image').addEventListener('change', event => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    const file = event.target.files[0]; imageUrl = file ? URL.createObjectURL(file) : null;
    $('dance-image-preview').hidden = !file;
    if (file) $('dance-image-preview').src = imageUrl;
    controls();
  });
  $('dance-video').addEventListener('change', event => {
    const file = event.target.files[0]; uploaded = null;
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    if (!file) { controls(); return; }
    if (file.size > 256 * 1024 * 1024) { status('Vidéo trop volumineuse : 256 Mio maximum.', true); controls(); return; }
    videoUrl = URL.createObjectURL(file); const preview = $('dance-import-preview');
    preview.src = videoUrl; preview.hidden = false;
    const serial = ++generation;
    run(async () => {
      status('Import de la vidéo…');
      const form = new FormData(); form.append('file', file);
      const result = await request('/api/dance/videos', {method:'POST', body:form});
      if (serial !== generation) return;
      uploaded = result; $('dance-start').max = String(result.duration_seconds - 124 / 24);
      $('dance-duration').value = String(Math.min(8, result.duration_seconds));
      $('dance-audio').checked = result.has_audio; $('dance-audio').disabled = !result.has_audio;
      if (!$('dance-title').value) $('dance-title').value = file.name.replace(/\.[^.]+$/, '').slice(0,120);
      status(`${result.duration_seconds.toFixed(2)} s disponibles. Choisis le début et la durée de l’extrait.`);
    });
  });
  for (const id of ['dance-start','dance-duration']) $(id).addEventListener('input', controls);
  $('dance-use-position').addEventListener('click', () => { $('dance-start').value = $('dance-import-preview').currentTime.toFixed(2); controls(); });
  $('dance-preview-excerpt').addEventListener('click', () => {
    const video = $('dance-import-preview'); video.currentTime = Number($('dance-start').value); video.play().catch(() => {});
  });
  $('dance-import-preview').addEventListener('timeupdate', event => {
    if (event.target.currentTime >= Number($('dance-start').value) + Number($('dance-duration').value)) event.target.pause();
  });
  $('dance-create').addEventListener('click', () => run(async () => {
    const issue = excerptIssue();
    if (issue) throw new Error(issue.message);
    const image = $('dance-image').files[0];
    if (!image || !uploaded) throw new Error('Choisis une photo et importe une vidéo avant de préparer l’extrait.');
    const form = new FormData(); form.append('image', image); form.append('video_asset_id', uploaded.asset_id);
    form.append('start', $('dance-start').value); form.append('duration', $('dance-duration').value);
    form.append('keep_audio', String($('dance-audio').checked)); form.append('title', $('dance-title').value);
    status('Préparation de l’extrait et du prompt…');
    const result = await request('/api/dance/projects', {method:'POST', body:form});
    await list(); await open(result.project.project_id);
  }));
  $('dance-save-prompt').addEventListener('click', () => run(async () => {
    const result = await request(`/api/dance/projects/${encodeURIComponent(project.project_id)}/prompt`, {...json({prompt:$('dancer-prompt').value}),method:'PUT'});
    project = result.project; status('Prompt enregistré.');
  }));
  $('dance-polish').addEventListener('click', () => run(async () => {
    status('Ajustement du prompt en cours · 1 appel…');
    const result = await request(`/api/dance/projects/${encodeURIComponent(project.project_id)}/polish`, json({
      prompt: $('dancer-prompt').value, instruction: $('dance-instruction').value, model_id: $('dancer-revision-model').value}));
    $('dance-proposed-prompt').value = result.prompt; $('dance-proposal').hidden = false;
    status('Proposition prête. Tu peux l’appliquer ou conserver le prompt actuel.');
  }));
  $('dance-apply').addEventListener('click', () => {
    $('dancer-prompt').value = $('dance-proposed-prompt').value; $('dancer-prompt').dispatchEvent(new Event('input'));
    $('dance-proposal').hidden = true; status('Proposition appliquée au prochain essai.');
  });
  $('dance-discard').addEventListener('click', () => { $('dance-proposal').hidden = true; });
  $('dancer-revision-model').addEventListener('change', event => remember('panelforge.dance.model', event.target.value));
  controls();
  // Restore the compact mode without requesting catalogs until Ref2V is opened.
  if (readMemory('panelforge.ref2v.mode') === 'dance') {
    const observer = new MutationObserver(() => { if (!workspace.hidden) { observer.disconnect(); selectMode('dance'); } });
    observer.observe(workspace, {attributes:true, attributeFilter:['hidden']});
  }
})();
