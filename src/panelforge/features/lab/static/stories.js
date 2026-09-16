(() => {
  "use strict";
  const root = document.getElementById("stories-workspace"), core = window.PanelForgeLabCore, picker = window.PanelForgeModelPicker;
  if (!root || !core || !picker) return;
  const el = id => document.getElementById(`story-${id}`);
  const defaultLocalModel = "local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP";
  const state = { project: null, initialized: false, loading: false, saving: false, models: [], modelsReady: false,
    wantedModel: "", modelChoice: 0, modelError: "", token: 0, timer: null, paintKey: "", turnKey: "" };
  const storage = { get(key) { try { return localStorage.getItem(`panelforge.stories.${key}`); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(`panelforge.stories.${key}`, value); } catch (_) { /* Server persistence remains available. */ } } };
  const path = (id, suffix = "") => `/api/stories/projects/${encodeURIComponent(id)}${suffix}`;
  const json = body => ({method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const request = (url, options) => core.request(url, options);
  const node = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, action) => { const b = node("button", text); b.type = "button"; b.addEventListener("click", action); return b; };
  const running = () => ["running", "cancelling"].includes(state.project?.job?.status);
  const blocked = () => state.saving || state.loading || running();
  const selectedModel = () => state.models.some(m => m.id === el("model").value) ? el("model").value : "";
  const modelSource = id => state.models.find(m => m.id === id)?.source || (id.startsWith("local::") ? "local" : "server");
  function chooseModel(id) {
    state.wantedModel = id || "";
    if (id) el("local").checked = modelSource(id) === "local";
    if (!state.modelsReady) return;
    if (id) picker.select(el("model"), id);
    else picker.populate(el("model"), state.models);
    const source = el("local").checked ? "local" : "server";
    el("model-message").textContent = state.modelError || (state.models.some(m => modelSource(m.id) === source) ? "" :
      `Aucun modèle ${source === "local" ? "local" : "serveur"} disponible. Actualise après avoir démarré ton serveur LLM.`);
  }
  function preferredModel() {
    const source = storage.get("model-source") === "server" ? "server" : "local";
    el("local").checked = source === "local";
    chooseModel(storage.get(`model.${source}`) || (source === "local" ? defaultLocalModel : ""));
  }
  function rememberModel() {
    const source = el("local").checked ? "local" : "server";
    storage.set("model-source", source);
    if (selectedModel()) { storage.set(`model.${source}`, selectedModel()); storage.set("model", selectedModel()); }
  }
  function message(text, error = false) { el("message").textContent = text; el("message").classList.toggle("error", error); }
  function controls() {
    const project = state.project, busy = blocked(), doc = project?.document;
    el("create").disabled = state.saving || !selectedModel();
    el("send").disabled = busy || !doc?.concepts.length || !el("instruction").value.trim() || !selectedModel();
    el("ideas").disabled = busy || !project || !selectedModel();
    el("develop").disabled = busy || !doc?.selected_id || !selectedModel();
    el("restore").disabled = busy || !project?.revisions.length;
    el("cancel").disabled = !running() || project.job.status === "cancelling";
    el("retry").disabled = busy || !selectedModel();
    el("running").hidden = !running();
    el("retry").hidden = !["failed", "interrupted", "cancelled"].includes(project?.job?.status);
    el("concepts").querySelectorAll("button").forEach(b => { b.disabled = busy || b.dataset.selected === "true"; });
    if (el("validate")) el("validate").disabled = busy || !doc?.scenario;
  }
  async function models() {
    el("refresh-models").disabled = true; el("model-message").textContent = "Lecture des modèles…";
    try {
      const data = await request("/api/stories/models");
      state.models = data.models; state.modelsReady = true; state.modelError = "";
      picker.populate(el("model"), state.models, state.wantedModel);
      chooseModel(state.wantedModel);
    } catch (error) { state.modelError = error.message; el("model-message").textContent = error.message; }
    finally { el("refresh-models").disabled = false; controls(); }
  }
  async function recent() {
    const data = await request("/api/stories/projects");
    el("projects").replaceChildren(new Option("Nouvelle histoire", ""), ...data.projects.map(p => new Option(p.title, p.project_id)));
    if (state.project && !data.projects.some(p => p.project_id === state.project.project_id)) el("projects").add(new Option(state.project.title, state.project.project_id));
    el("projects").value = state.project?.project_id || "";
  }
  function schedule() {
    clearTimeout(state.timer);
    if (!running() || root.hidden) return;
    const id = state.project.project_id, token = state.token;
    state.timer = setTimeout(async () => {
      try {
        const result = await request(path(id));
        if (token !== state.token || state.project?.project_id !== id) return;
        state.project = result; paint();
        if (!running()) recent().catch(() => {});
      } catch (error) { if (token === state.token) message(`${error.message} L’écriture reste enregistrée côté serveur ; nouvelle vérification…`, true); }
      finally { if (token === state.token) schedule(); }
    }, 1600);
  }
  async function openProject(id) {
    const restoreModel = state.project?.project_id !== id, modelChoice = state.modelChoice;
    const token = ++state.token; state.loading = true; controls(); clearTimeout(state.timer);
    try {
      const project = await request(path(id));
      if (token !== state.token) return;
      state.project = project; state.paintKey = ""; state.turnKey = "";
      storage.set("project", id); el("instruction").value = storage.get(`draft.${id}`) || "";
      if (restoreModel && modelChoice === state.modelChoice && project.model_id) chooseModel(project.model_id);
      paint();
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { if (token === state.token) { state.loading = false; controls(); schedule(); } }
  }
  function newProject() {
    ++state.token; clearTimeout(state.timer); state.project = null; state.paintKey = ""; state.turnKey = "";
    state.loading = false; storage.set("project", ""); el("projects").value = "";
    el("title").value = ""; el("brief").value = ""; preferredModel(); paint(); el("brief").focus();
  }
  function paint() {
    const p = state.project, doc = p?.document;
    window.dispatchEvent(new CustomEvent("panelforge:story", {detail: p}));
    el("create-form").hidden = !!p; el("conversation-panel").hidden = !p;
    el("empty").hidden = !!doc?.concepts.length;
    el("versions-panel").hidden = !p?.revisions.length;
    el("develop").hidden = !doc?.selected_id;
    el("scenario").hidden = !doc?.scenario;
    if (!p) {
      el("concepts").replaceChildren(); message(""); controls(); return;
    }
    el("projects").value = p.project_id;
    el("project-brief").textContent = `${p.brief || "Idées libres"}\n${p.scene_count} micro-scènes visées · ${p.clip_seconds} s par clip`;
    const turnKey = `${p.project_id}:${p.turns.length}`;
    if (state.turnKey !== turnKey) {
      state.turnKey = turnKey;
      el("turns").replaceChildren(...p.turns.map(turn => {
        const item = node("div", "", `story-turn ${turn.role}`);
        item.append(node("strong", turn.role === "user" ? "Toi" : "Scénariste"), node("span", turn.text)); return item;
      }));
      el("turns").scrollTop = el("turns").scrollHeight;
    }
    const key = `${p.project_id}:${p.revisions.length}`;
    if (state.paintKey !== key) {
      state.paintKey = key;
      el("versions").replaceChildren(...[...p.revisions].reverse().map(r => new Option(`v${r.revision} · ${r.label}`, r.revision)));
      paintConcepts(doc); paintScenario(doc.scenario);
    }
    const job = p.job;
    if (job) message(job.error || job.phase || "", !!job.error);
    else message("Histoire enregistrée. Tu peux demander tes trois premières propositions.");
    const draft = job?.draft && ["failed", "interrupted", "cancelled"].includes(job.status);
    el("draft-panel").hidden = !draft; if (draft) el("draft").textContent = job.draft;
    controls();
  }
  function paintConcepts(doc) {
    const labels = {protagonist: "Personnage principal", antagonist: "Antagoniste", escalation: "Escalade", reveal: "Révélation", ending: "Fin"};
    el("concepts").replaceChildren(...doc.concepts.map((c, i) => {
      const chosen = doc.selected_id === c.id;
      const card = node("article", "", `story-concept${chosen ? " selected" : ""}`);
      card.append(node("small", chosen ? "HISTOIRE CHOISIE" : `PISTE ${i+1}`), node("h3", c.title), node("p", c.hook));
      const details = node("details"); details.append(node("summary", "Conflit et dénouement"));
      const dl = node("dl"); Object.entries(labels).forEach(([key, label]) => dl.append(node("dt", label), node("dd", c[key])));
      details.append(dl); card.append(details);
      const choose = button(chosen ? "Sélectionnée" : "Choisir cette histoire", () => mutate("select", {concept_id: c.id}));
      choose.dataset.selected = String(chosen); choose.setAttribute("aria-pressed", String(chosen)); card.append(choose);
      return card;
    }));
  }
  function paintScenario(scenario) {
    if (!scenario) return;
    el("scenario-title").textContent = scenario.title; el("logline").textContent = scenario.logline;
    el("cast").replaceChildren();
    for (const [title, items] of [["Personnages", scenario.characters], ["Décors", scenario.locations]]) {
      el("cast").append(node("h3", title));
      for (const item of items) { const p = node("p"); p.append(node("strong", `${item.name} — `), node("span", item.description)); el("cast").append(p); }
    }
    const names = new Map(scenario.characters.map(c => [c.id, c.name]));
    const places = new Map(scenario.locations.map(l => [l.id, l.name]));
    el("scenes").replaceChildren(...scenario.scenes.map((scene, i) => {
      const card = node("article", "", "story-scene"), head = node("div", "", "story-actions");
      head.append(node("h3", `${i+1}. ${scene.title}`), button("Copier l’intention", () => exportScenario("copy", i)));
      card.append(head, node("small", `${places.get(scene.location_id)} · ${scene.character_ids.map(id => names.get(id)).join(", ")}`), node("p", scene.action));
      if (scene.dialogue.length) card.append(node("p", scene.dialogue.map(d => `${names.get(d.speaker_id)} : « ${d.text} »`).join("\n"), "story-dialogue"));
      const states = node("details"); states.append(node("summary", "Continuité"), node("p", `Début : ${scene.opening_state}`), node("p", `Fin : ${scene.ending_state}`)); card.append(states);
      return card;
    }));
  }
  async function mutate(action, body) {
    if (blocked() || !state.project) return;
    const id = state.project.project_id, token = state.token;
    state.saving = true; controls();
    try {
      const result = await request(path(id, `/${action}`), json({...body, expected_version: state.project.version}));
      if (token !== state.token) return;
      state.project = result; paint(); recent().catch(() => {});
    } catch (error) { if (token === state.token) { message(error.message, true); } }
    finally { state.saving = false; controls(); }
  }
  async function write(operation, instruction = "") {
    if (blocked() || !state.project || !selectedModel()) return;
    const id = state.project.project_id, token = state.token;
    state.saving = true; controls();
    try {
      const result = await request(path(id, "/write"), json({operation, instruction, model_id: el("model").value,
        expected_version: state.project.version, request_id: crypto.randomUUID()}));
      if (token !== state.token) return;
      state.project = result;
      if (instruction === el("instruction").value.trim()) { el("instruction").value = ""; storage.set(`draft.${id}`, ""); }
      paint(); schedule();
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  }
  async function exportScenario(action, index = 0) {
    const id = state.project?.project_id;
    if (!id) return;
    try {
      const data = await request(path(id, `/export?include_duration=${el("include-duration").checked}`));
      if (action === "copy") {
        const text = data.intentions[index];
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
        else {
          const area = node("textarea"); area.value = text; area.style.position = "fixed"; area.style.left = "-9999px";
          document.body.append(area); area.select(); const ok = document.execCommand("copy"); area.remove(); if (!ok) throw new Error("Copie indisponible dans ce navigateur. Télécharge le scénario.");
        }
        message("Intention copiée, dialogues inclus. Ajoute les références de personnages dans l’atelier vidéo.");
      } else {
        const url = URL.createObjectURL(new Blob([data.text], {type: "text/plain;charset=utf-8"}));
        const a = node("a"); a.href = url; a.download = `${id}.txt`; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (error) { message(error.message, true); }
  }
  async function activate() {
    if (root.hidden) { clearTimeout(state.timer); return; }
    if (!state.initialized) {
      state.initialized = true;
      // Recent projects do not wait for the model server, and remain usable offline.
      const tasks = [models(), (async () => {
        try { await recent(); const saved = storage.get("project"); if (saved && !state.project) await openProject(saved); }
        catch (error) { message(error.message, true); }
      })()];
      await Promise.allSettled(tasks);
    } else if (state.project && !state.saving) {
      // Resume polling without discarding a locally typed message.
      schedule();
    }
    controls();
  }
  el("create-form").addEventListener("submit", async event => {
    event.preventDefault(); if (state.saving || !selectedModel()) return;
    state.saving = true; controls(); const token = ++state.token;
    try {
      const project = await request("/api/stories/projects", json({title: el("title").value.trim() || "Nouvelle histoire", brief: el("brief").value,
        clip_seconds: Number(el("duration").value), scene_count: Number(el("scene-count").value)}));
      if (token !== state.token) return;
      state.project = project; storage.set("project", project.project_id); state.paintKey = ""; state.turnKey = "";
      el("instruction").value = ""; paint(); await recent();
      state.saving = false; await write("ideas");
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  });
  el("chat-form").addEventListener("submit", event => { event.preventDefault(); write("revise", el("instruction").value.trim()); });
  el("instruction").addEventListener("input", () => { if (state.project) storage.set(`draft.${state.project.project_id}`, el("instruction").value); controls(); });
  el("model").addEventListener("change", () => { ++state.modelChoice; state.wantedModel = el("model").value; rememberModel(); controls(); });
  el("local").addEventListener("change", event => {
    // Keep the common picker, with source-specific preferences for Stories only.
    event.stopPropagation(); ++state.modelChoice;
    const source = el("local").checked ? "local" : "server";
    chooseModel(storage.get(`model.${source}`) || (source === "local" ? defaultLocalModel : ""));
    rememberModel(); controls();
  });
  el("new").addEventListener("click", newProject);
  el("projects").addEventListener("change", () => el("projects").value ? openProject(el("projects").value) : newProject());
  el("refresh-projects").addEventListener("click", async () => { try { await recent(); if (state.project) await openProject(state.project.project_id); } catch (e) { message(e.message, true); } });
  el("refresh-models").addEventListener("click", models);
  el("ideas").addEventListener("click", () => write("ideas", el("instruction").value.trim()));
  el("develop").addEventListener("click", () => write("develop", el("instruction").value.trim()));
  el("restore").addEventListener("click", () => mutate("restore", {revision: Number(el("versions").value)}));
  el("retry").addEventListener("click", () => write(state.project.job.operation, [...state.project.turns].reverse().find(t => t.role === "user")?.text || ""));
  el("cancel").addEventListener("click", async () => {
    if (!running()) return; const token = state.token;
    try { const result = await request(path(state.project.project_id, "/cancel"), json({})); if (token === state.token) { state.project = result; paint(); schedule(); } }
    catch (error) { message(error.message, true); }
  });
  el("export").addEventListener("click", () => exportScenario("download"));
  el("recipes").addEventListener("click", () => window.PanelForgePromptRecipes?.open({key: "story.brainrot", version: "1.0.0"}));
  el("calls").addEventListener("click", () => { if (state.project) window.PanelForgePromptRecipes?.showHistory(path(state.project.project_id, "/calls")); });
  new MutationObserver(activate).observe(root, {attributes: true, attributeFilter: ["hidden"]});
  window.PanelForgeStories = Object.freeze({ current: () => state.project });
  preferredModel(); paint(); activate();
})();
