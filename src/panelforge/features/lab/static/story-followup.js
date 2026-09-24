(() => {
  "use strict";
  const dialog = document.getElementById("story-followup"), core = window.PanelForgeLabCore;
  if (!dialog || !core) return;
  const el = id => document.getElementById(`sf-${id}`), fields = ["start", "beats", "ending", "constraints"];
  const state = {draft: null, models: [], busy: false, dirty: false, saving: false, sequence: 0,
    token: 0, saveTimer: null, pollTimer: null, saveChain: Promise.resolve(), onWritten: null, pendingMessage: null};
  const cached = {get(key) { try { return localStorage.getItem(`panelforge.followup.${key}`) || ""; } catch (_) { return ""; } },
    set(key, value) { try { localStorage.setItem(`panelforge.followup.${key}`, value); } catch (_) {} }};
  const api = (suffix = "") => `/api/stories/followups/${encodeURIComponent(state.draft.id)}${suffix}`;
  const request = (url, method = "GET", data) => core.request(url, data === undefined ? undefined : {
    method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  const running = () => ["running", "cancelling"].includes(state.draft?.job?.status);
  const status = (text, error = false) => { el("status").textContent = text; el("status").classList.toggle("error", error); };
  const available = id => state.models.some(m => m.id === id);

  function modelOptions(id, selected) {
    const input = el(id);
    input.replaceChildren(new Option("Choisir un modèle…", ""));
    for (const source of ["local", "server"]) {
      const models = state.models.filter(m => (m.source === "local" ? "local" : "server") === source);
      if (!models.length) continue;
      const group = document.createElement("optgroup"); group.label = source === "local" ? "Local" : "Serveur";
      for (const m of models) group.append(new Option(m.label || m.id, m.id));
      input.append(group);
    }
    if (selected && !available(selected)) {
      const option = new Option(`${selected} · indisponible`, selected); option.disabled = true; input.append(option);
    }
    input.value = selected || "";
  }

  function fill() {
    const draft = state.draft;
    for (const key of fields) el(key).value = draft.direction[key] || "";
    modelOptions("model", draft.model_id);
    modelOptions("architect", draft.settings.architect_model_id);
    modelOptions("writer", draft.settings.writer_model_id);
    el("language").value = draft.settings.dialogue_language;
    el("mode").value = draft.settings.workflow_mode;
    el("scenes").value = draft.settings.scene_count;
    el("seconds").value = draft.settings.clip_seconds;
    el("target").value = draft.settings.target_seconds;
    state.dirty = false;
  }

  function controls() {
    const draft = state.draft, working = running(), existing = draft?.context.next_written;
    const locked = !draft || state.busy || working || Boolean(draft.result) || existing;
    for (const key of [...fields, "model", "message", "language", "mode", "scenes", "seconds", "target", "architect", "writer"]) el(key).disabled = locked;
    if (draft?.context.next_unit) for (const key of ["language", "scenes", "seconds", "target"]) el(key).disabled = true;
    const blocked = locked || state.saving || draft?.source_changed || !available(el("model").value);
    el("send").disabled = blocked || !el("message").value.trim(); el("suggest").disabled = blocked;
    const directionReady = fields.some(key => el(key).value.trim());
    el("write").disabled = !draft || state.busy || working || state.saving || (!draft.result && !existing &&
      (!directionReady || draft.source_changed || !available(el("architect").value) || !available(el("writer").value)));
    el("write").textContent = draft?.result || existing ? "Ouvrir l’épisode" : "Écrire cet épisode";
    el("close").disabled = state.busy; el("reload").disabled = state.busy || state.saving || working;
    el("refresh-source").disabled = !draft || state.busy || working || Boolean(draft.result);
    el("cancel").disabled = !working || draft?.job?.status === "cancelling";
    el("model-refresh").disabled = state.busy || working;
    el("working").hidden = !working;
    el("saved").textContent = state.saving ? "Enregistrement…" : state.dirty ? "Modifications à enregistrer" : draft ? "Préparation enregistrée" : "";
    el("budget").textContent = `${el("target").value} s visées · budget maximal : ${Number(el("scenes").value) * Number(el("seconds").value)} s · univers et registre conservés`;
  }

  function paint() {
    const draft = state.draft;
    if (!draft) { controls(); return; }
    el("source").textContent = `À partir de « ${draft.context.source_label} » · ${draft.context.next_unit ? `Épisode prévu : ${draft.context.next_unit.title}` : "Nouvelle suite liée à cette histoire"}`;
    el("source-warning").hidden = !draft.source_changed || Boolean(draft.result);
    el("existing").hidden = !draft.context.next_written || Boolean(draft.result);
    el("format-note").textContent = draft.context.next_unit ? "Le format reste celui de l’arc existant." : "Une nouvelle suite, avec les personnages et leur état final. La durée peut être ajustée ici.";
    const log = el("turns");
    if (log.dataset.key !== JSON.stringify(draft.turns)) {
      log.dataset.key = JSON.stringify(draft.turns); log.replaceChildren();
      if (!draft.turns.length) {
        const hint = document.createElement("p"); hint.className = "muted";
        hint.textContent = "Donne une direction, pose une question, ou demande une proposition. Tu peux aussi remplir directement la carte à droite."; log.append(hint);
      }
      for (const turn of draft.turns) {
        const article = document.createElement("article"); article.className = `sf-turn${turn.role === "user" ? " sf-user" : ""}`;
        const label = document.createElement("strong"); label.textContent = turn.role === "user" ? "Toi" : "Préparation de la suite";
        article.append(label, document.createTextNode(turn.text)); log.append(article);
      }
      log.scrollTop = log.scrollHeight;
    }
    const failed = ["failed", "interrupted", "cancelled"].includes(draft.job?.status);
    el("raw-panel").hidden = !failed || !draft.job?.draft;
    el("raw").textContent = failed ? draft.job?.draft || "" : "";
    if (failed) status(draft.job.error || "Échange interrompu ; la direction est conservée.", true);
    else if (draft.result?.notice) status(draft.result.notice);
    else if (running()) status("Discussion en cours…");
    controls();
  }

  function payload() {
    return {direction: Object.fromEntries(fields.map(key => [key, el(key).value])), model_id: el("model").value,
      settings: {dialogue_language: el("language").value, workflow_mode: el("mode").value,
        scene_count: Number(el("scenes").value), clip_seconds: Number(el("seconds").value),
        target_seconds: Number(el("target").value),
        architect_model_id: el("architect").value, writer_model_id: el("writer").value}};
  }

  function save() {
    clearTimeout(state.saveTimer);
    const token = state.token;
    state.saveChain = state.saveChain.catch(() => {}).then(async () => {
      if (token !== state.token || !state.dirty || !state.draft || running() || state.draft.result) return;
      const sequence = state.sequence, body = {...payload(), expected_revision: state.draft.revision};
      state.saving = true; controls();
      try {
        const draft = await request(api(), "PUT", body);
        if (token !== state.token) return;
        state.draft = draft;
        if (sequence === state.sequence) state.dirty = false;
      } finally { if (token === state.token) { state.saving = false; controls(); } }
    });
    return state.saveChain;
  }
  function changed() {
    state.sequence++; state.dirty = true; controls(); clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => save().catch(error => status(error.message, true)), 700);
  }
  async function flush() {
    await state.saveChain.catch(() => {});
    if (state.dirty) await save();
  }

  function schedule() {
    clearTimeout(state.pollTimer);
    if (!dialog.open || !running()) return;
    const token = state.token;
    state.pollTimer = setTimeout(async () => {
      try {
        const draft = await request(api());
        if (token !== state.token) return;
        state.draft = draft;
        if (!running()) { fill(); status("Direction mise à jour. Tu peux poursuivre la discussion ou lancer l’écriture."); }
        paint();
      } catch (error) { if (token === state.token) status(`${error.message} La discussion reste enregistrée.`, true); }
      finally { if (token === state.token) schedule(); }
    }, 1200);
  }

  async function action(work) {
    if (state.busy || !state.draft) return;
    state.busy = true; controls();
    try { await flush(); await work(); }
    catch (error) { status(error.message, true); }
    finally { state.busy = false; controls(); schedule(); }
  }

  async function open({project, models, architect, writer, onWritten}) {
    if (dialog.open) return;
    const token = ++state.token; state.draft = null; state.models = models || []; state.busy = true;
    state.dirty = false; state.saveChain = Promise.resolve(); state.onWritten = onWritten; state.pendingMessage = null;
    el("source").textContent = project.title; el("turns").replaceChildren(); el("turns").dataset.key = "";
    el("source-warning").hidden = true; el("existing").hidden = true; el("raw-panel").hidden = true;
    for (const key of fields) el(key).value = "";
    dialog.showModal(); status("Chargement de la préparation…"); controls();
    try {
      const draft = await request(`/api/stories/projects/${encodeURIComponent(project.project_id)}/followup`, "POST", {
        source_unit_id: project.document.selected_episode_id || null, expected_version: project.version});
      if (token !== state.token) return;
      state.draft = draft;
      if (!state.models.length) {
        try { state.models = (await request("/api/stories/models")).models; }
        catch (error) { status(error.message, true); }
      }
      let defaultsChanged = false;
      if (!draft.model_id) {
        const remembered = cached.get("model"), qwen = state.models.find(m => /qwen/i.test(m.id + " " + m.label) && m.source === "local")
          || state.models.find(m => /qwen/i.test(m.id + " " + m.label));
        draft.model_id = available(remembered) ? remembered : qwen?.id || "";
        defaultsChanged = Boolean(draft.model_id);
      }
      for (const [key, value] of [["architect_model_id", architect], ["writer_model_id", writer]]) {
        if (!draft.settings[key] && value) { draft.settings[key] = value; defaultsChanged = true; }
      }
      fill(); el("message").value = cached.get(`${draft.id}.message`);
      status(draft.model_id ? "Discute de la suite ou demande une proposition." : "Qwen indisponible dans le catalogue : choisis un modèle de discussion.");
      paint();
      if (defaultsChanged && !draft.result && !running() && !draft.context.next_written) { changed(); await save(); }
    } catch (error) { status(error.message, true); }
    finally { state.busy = false; controls(); schedule(); }
  }

  async function close() {
    if (state.busy) return;
    await action(async () => { dialog.close(); clearTimeout(state.pollTimer); });
    if (!state.draft) dialog.close();
  }
  async function discuss(automatic) {
    await action(async () => {
      const instruction = el("message").value.trim();
      const key = JSON.stringify([instruction, automatic]);
      if (state.pendingMessage?.key !== key) state.pendingMessage = {key, id: crypto.randomUUID()};
      state.draft = await request(api("/messages"), "POST", {instruction, automatic,
        expected_revision: state.draft.revision, request_id: state.pendingMessage.id});
      state.pendingMessage = null; el("message").value = ""; cached.set(`${state.draft.id}.message`, "");
      status("Discussion en cours…"); paint();
    });
  }
  el("chat-form").addEventListener("submit", event => { event.preventDefault(); if (!el("send").disabled) discuss(false); });
  el("suggest").addEventListener("click", () => discuss(true));
  el("message").addEventListener("input", () => { if (state.draft) cached.set(`${state.draft.id}.message`, el("message").value); controls(); });
  el("message").addEventListener("keydown", event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); if (!el("send").disabled) discuss(false); } });
  for (const id of [...fields, "scenes", "seconds", "target"]) el(id).addEventListener("input", changed);
  for (const id of ["model", "language", "mode", "architect", "writer"]) el(id).addEventListener("change", () => {
    if (id === "model") cached.set("model", el("model").value); changed();
  });
  el("close").addEventListener("click", close);
  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  el("cancel").addEventListener("click", () => action(async () => { state.draft = await request(api("/cancel"), "POST", {}); paint(); }));
  el("refresh-source").addEventListener("click", () => action(async () => {
    state.draft = await request(api("/refresh"), "POST", {expected_revision: state.draft.revision});
    fill(); status("Contexte actualisé. Vérifie que la direction convient toujours."); paint();
  }));
  el("reload").addEventListener("click", async () => {
    if (state.busy || !state.draft) return;
    if (state.dirty && !window.confirm("Recharger la préparation enregistrée et remplacer les modifications locales non enregistrées ?")) return;
    state.busy = true; clearTimeout(state.saveTimer); controls();
    try { state.draft = await request(api()); fill(); status("Préparation rechargée."); paint(); }
    catch (error) { status(error.message, true); }
    finally { state.busy = false; controls(); schedule(); }
  });
  el("model-refresh").addEventListener("click", () => action(async () => {
    state.models = (await request("/api/stories/models")).models;
    for (const key of ["model", "architect", "writer"]) modelOptions(key, el(key).value);
    status("Catalogue des modèles actualisé.");
  }));
  el("write").addEventListener("click", () => action(async () => {
    const result = await request(api("/commit"), "POST", {expected_revision: state.draft.revision});
    state.draft = result.draft;
    await state.onWritten?.(result.project);
    if (result.draft.result?.notice) { status(result.draft.result.notice, true); paint(); }
    else dialog.close();
  }));
  window.PanelForgeStoryFollowup = Object.freeze({open});
})();
