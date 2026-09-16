(() => {
  "use strict";
  const root = document.getElementById("stories-workspace"), core = window.PanelForgeLabCore, picker = window.PanelForgeModelPicker;
  if (!root || !core || !picker) return;
  const el = id => document.getElementById(`story-${id}`);
  const roles = ["architect", "writer"];
  const defaultLocalModel = "local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP";
  const fallbackRecipes = [{id: "story.brainrot", version: "1.0.0", label: "Mélodrame fruits",
    description: "Fruits anthropomorphes, conflits frontaux et retournements visuels.",
    concept_fields: [{id: "title", label: "Titre"}, {id: "hook", label: "Accroche"},
      {id: "protagonist", label: "Personnage principal"}, {id: "antagonist", label: "Antagoniste"},
      {id: "escalation", label: "Escalade"}, {id: "reveal", label: "Révélation"}, {id: "ending", label: "Fin"}], scene_fields: []},
    {id: "story.sensual-light", version: "1.0.0", label: "Sensuel light",
      description: "Désir, tension et proximité entre personnages clairement adultes, sans description sexuelle graphique.",
      concept_fields: [{id: "title", label: "Titre"}, {id: "hook", label: "Accroche"},
        {id: "characters_and_dynamic", label: "Personnages et dynamique"}, {id: "desire", label: "Désir"},
        {id: "obstacle", label: "Obstacle"}, {id: "sensual_escalation", label: "Montée sensuelle"},
        {id: "turning_point", label: "Bascule"}, {id: "ending", label: "Fin"}],
      scene_fields: [{id: "relationship_state", label: "Dynamique relationnelle"},
        {id: "appearance_state", label: "Tenues et continuité visuelle"}]},
    {id: "story.explicit-hard", version: "1.0.0", label: "Cru ++",
      description: "Scènes pornographiques explicites : actes, anatomie, contacts, mouvements et continuité physique décrits sans euphémisme.",
      concept_fields: [{id: "title", label: "Titre"}, {id: "hook", label: "Accroche"},
        {id: "participants_and_dynamic", label: "Participants et dynamique"},
        {id: "explicit_premise", label: "Situation sexuelle"},
        {id: "acts_and_progression", label: "Actes et progression"},
        {id: "physical_escalation", label: "Escalade physique"},
        {id: "turning_point", label: "Bascule"}, {id: "ending", label: "Fin"}],
      scene_fields: [{id: "relationship_state", label: "Dynamique entre participants"},
        {id: "appearance_state", label: "Nudité, tenues et accessoires"},
        {id: "sexual_state", label: "Position et contacts sexuels"}]}];
  const state = {project: null, initialized: false, loading: false, saving: false, models: [], modelsReady: false,
    recipes: fallbackRecipes, wantedModel: {architect: "", writer: ""}, modelChoice: {architect: 0, writer: 0},
    modelError: "", token: 0, timer: null, paintKey: "", turnKey: "", editScene: null};
  const storage = {get(key) { try { return localStorage.getItem(`panelforge.stories.${key}`); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(`panelforge.stories.${key}`, value); } catch (_) {} }};
  const path = (id, suffix = "") => `/api/stories/projects/${encodeURIComponent(id)}${suffix}`;
  const send = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const json = body => send("POST", body);
  const request = (url, options) => core.request(url, options);
  const node = (tag, text = "", cls = "") => { const item = document.createElement(tag); item.textContent = text; if (cls) item.className = cls; return item; };
  const button = (text, action) => { const item = node("button", text); item.type = "button"; item.addEventListener("click", action); return item; };
  const deliveryLabels = {spoken: "", voice_over: "voix off", off_screen: "hors champ",
    thought: "pensée / voix intérieure", mediated: "voix transmise"};
  function dialogueLabel(line, speaker) {
    const indication = line.delivery_note || deliveryLabels[line.delivery || "spoken"];
    return `${speaker}${indication ? ` — ${indication}` : ""} : « ${line.text} »`;
  }
  function dialogueEditorLine(line) {
    if (!line.dialogue_id && !line.delivery && !line.delivery_note) return `${line.speaker_id} | ${line.text}`;
    return `${line.dialogue_id || ""} | ${line.speaker_id} | ${line.delivery || "spoken"} | ${line.delivery_note || ""} | ${line.text}`;
  }
  const running = () => ["running", "cancelling"].includes(state.project?.job?.status);
  const blocked = () => state.saving || state.loading || running();
  const creationMode = () => el("creation-mode").value === "script" ? "script" : "ideas";
  const proposalCount = () => Math.max(1, Math.min(3, Number(el("proposal-count").value) || 3));
  const modelSource = id => state.models.find(model => model.id === id)?.source || (id?.startsWith("local::") ? "local" : "server");
  const selectedModel = role => state.models.some(model => model.id === el(`${role}-model`).value) ? el(`${role}-model`).value : "";
  const recipeKey = recipe => `${recipe.id}@${recipe.version}`;
  const currentRecipe = () => {
    const recipe = state.project?.recipe;
    const key = recipe ? recipeKey(recipe) : el("recipe").value;
    return state.recipes.find(item => recipeKey(item) === key) || fallbackRecipes[0];
  };

  function showModelMessage() {
    const unavailable = roles.filter(role => !state.models.some(model => modelSource(model.id) === (el(`${role}-local`).checked ? "local" : "server")));
    el("model-message").textContent = state.modelError || (unavailable.length ? "Aucun modèle disponible pour une des sources choisies. Actualise après avoir démarré le serveur LLM." : "");
  }
  function chooseModel(role, id) {
    state.wantedModel[role] = id || "";
    if (id) el(`${role}-local`).checked = modelSource(id) === "local";
    if (!state.modelsReady) return;
    if (id) picker.select(el(`${role}-model`), id);
    else picker.populate(el(`${role}-model`), state.models);
    showModelMessage();
  }
  function preferredModel(role) {
    const source = storage.get(`${role}.model-source`) || storage.get("model-source") || "local";
    el(`${role}-local`).checked = source !== "server";
    chooseModel(role, storage.get(`${role}.model.${source}`) || storage.get(`model.${source}`)
      || (source === "local" ? defaultLocalModel : ""));
  }
  function rememberModel(role) {
    const source = el(`${role}-local`).checked ? "local" : "server";
    storage.set(`${role}.model-source`, source);
    if (selectedModel(role)) storage.set(`${role}.model.${source}`, selectedModel(role));
  }
  function message(text, error = false) { el("message").textContent = text; el("message").classList.toggle("error", error); }
  function refreshStartMode() {
    const script = creationMode() === "script", count = proposalCount();
    el("proposal-count-row").hidden = script;
    el("brief-label").textContent = script ? "Script complet · obligatoire" : "Ton idée · facultative";
    el("brief").required = script;
    el("brief").placeholder = script
      ? "Colle ici le script complet avec ses scènes, actions, locuteurs et dialogues…"
      : "Un patron avocat odieux qui arnaque ses clients… Ou laisse le LLM te surprendre.";
    el("mode-description").textContent = script
      ? "Un seul appel au Rédacteur structure le texte en micro-scènes. Les dialogues détectés sont contrôlés mot pour mot."
      : "Le LLM propose une à trois histoires avant le développement du scénario.";
    el("create").textContent = script ? "Structurer fidèlement ce script" : `Proposer ${count} histoire${count > 1 ? "s" : ""}`;
    el("create-note").textContent = script
      ? "Le script prévaut sur le ton par défaut : aucun passage ni dialogue ne doit être réinventé."
      : "Conflits simples, personnages excessifs, retournements visuels. Tu peux orienter le ton dans ton idée.";
    el("empty-title").textContent = script ? "Un script prêt à structurer" : "Quelle histoire raconter ?";
    el("empty-copy").textContent = script
      ? "Le Rédacteur transformera le script en fiches et micro-scènes sans passer par des propositions intermédiaires."
      : `Le LLM proposera ${count} accroche${count > 1 ? "s" : ""} avec conflit, escalade et fin. ${count > 1 ? "Choisis une piste, discute-la" : "Tu pourras la discuter"}, puis développe le scénario.`;
  }
  function controls() {
    const project = state.project, busy = blocked(), doc = project?.document;
    const scriptStart = creationMode() === "script";
    el("create").disabled = state.saving || !selectedModel("writer") || (!scriptStart && !selectedModel("architect"))
      || (scriptStart && !el("brief").value.trim());
    el("send").disabled = busy || !(doc?.concepts.length || doc?.scenario) || !el("instruction").value.trim() || !selectedModel("writer");
    el("ideas").disabled = busy || !project || !selectedModel("architect");
    el("develop").disabled = busy || !doc?.selected_id || !selectedModel("writer");
    el("restore").disabled = busy || !project?.revisions.length;
    el("cancel").disabled = !running() || project.job.status === "cancelling";
    const retryRole = project?.job?.operation === "ideas" ? "architect" : "writer";
    el("retry").disabled = busy || !selectedModel(retryRole);
    el("running").hidden = !running();
    el("retry").hidden = !["failed", "interrupted", "cancelled"].includes(project?.job?.status);
    el("concepts").querySelectorAll("button").forEach(item => { item.disabled = busy || item.dataset.selected === "true"; });
    el("scenes").querySelectorAll("button").forEach(item => { item.disabled = busy; });
    if (el("validate")) el("validate").disabled = busy || !doc?.scenario;
  }
  async function specs() {
    try {
      const data = await request("/api/stories/spec");
      if (data.recipes?.length) state.recipes = data.recipes;
    } catch (_) { /* The embedded defaults keep saved projects usable offline. */ }
    const selected = state.project?.recipe ? recipeKey(state.project.recipe) : el("recipe").value;
    el("recipe").replaceChildren(...state.recipes.map(recipe => new Option(recipe.label, recipeKey(recipe))));
    el("recipe").value = state.recipes.some(recipe => recipeKey(recipe) === selected) ? selected : recipeKey(state.recipes[0]);
    paintRecipeDescription();
  }
  function paintRecipeDescription() {
    const recipe = currentRecipe();
    el("recipe-description").textContent = recipe.description;
  }
  async function models() {
    el("refresh-models").disabled = true; el("model-message").textContent = "Lecture des modèles…";
    try {
      const data = await request("/api/stories/models");
      state.models = data.models; state.modelsReady = true; state.modelError = "";
      for (const role of roles) {
        picker.populate(el(`${role}-model`), state.models, state.wantedModel[role]);
        chooseModel(role, state.wantedModel[role]);
      }
    } catch (error) { state.modelError = error.message; showModelMessage(); }
    finally { el("refresh-models").disabled = false; controls(); }
  }
  async function recent() {
    const data = await request("/api/stories/projects");
    el("projects").replaceChildren(new Option("Nouvelle histoire", ""), ...data.projects.map(project => new Option(project.title, project.project_id)));
    if (state.project && !data.projects.some(project => project.project_id === state.project.project_id)) el("projects").add(new Option(state.project.title, state.project.project_id));
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
        state.project = result; paint(); if (!running()) recent().catch(() => {});
      } catch (error) { if (token === state.token) message(`${error.message} L’écriture reste enregistrée côté serveur ; nouvelle vérification…`, true); }
      finally { if (token === state.token) schedule(); }
    }, 1600);
  }
  async function openProject(id) {
    const changed = state.project?.project_id !== id;
    const choices = {...state.modelChoice};
    const token = ++state.token; state.loading = true; controls(); clearTimeout(state.timer);
    try {
      const project = await request(path(id));
      if (token !== state.token) return;
      state.project = project; state.paintKey = ""; state.turnKey = "";
      storage.set("project", id); el("instruction").value = storage.get(`draft.${id}`) || "";
      if (changed) {
        if (choices.architect === state.modelChoice.architect && (project.architect_model_id || project.model_id)) chooseModel("architect", project.architect_model_id || project.model_id);
        if (choices.writer === state.modelChoice.writer && (project.writer_model_id || project.model_id)) chooseModel("writer", project.writer_model_id || project.model_id);
      }
      paint();
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { if (token === state.token) { state.loading = false; controls(); schedule(); } }
  }
  function newProject() {
    ++state.token; clearTimeout(state.timer); state.project = null; state.paintKey = ""; state.turnKey = "";
    state.loading = false; storage.set("project", ""); el("projects").value = "";
    el("title").value = ""; el("brief").value = ""; el("creation-mode").value = "ideas"; el("proposal-count").value = "3";
    for (const role of roles) preferredModel(role);
    refreshStartMode(); paint(); el("brief").focus();
  }
  function paint() {
    const project = state.project, doc = project?.document;
    window.dispatchEvent(new CustomEvent("panelforge:story", {detail: project}));
    el("create-form").hidden = !!project; el("conversation-panel").hidden = !project;
    el("empty").hidden = !!(doc?.concepts.length || doc?.scenario); el("versions-panel").hidden = !project?.revisions.length;
    el("develop").hidden = !doc?.selected_id; el("scenario").hidden = !doc?.scenario;
    paintRecipeDescription();
    if (!project) { el("concepts").replaceChildren(); message(""); controls(); return; }
    el("projects").value = project.project_id;
    const recipe = currentRecipe();
    const scriptProject = project.creation_mode === "script";
    const projectCount = project.proposal_count || 3;
    el("project-brief").textContent = `${recipe.label} · ${scriptProject ? "Script fidèle" : `${projectCount} proposition${projectCount > 1 ? "s" : ""}`}\n${project.brief || "Idées libres"}\n${project.scene_count} micro-scènes visées · ${project.clip_seconds} s par clip`;
    el("ideas").hidden = scriptProject;
    el("ideas").textContent = `${project.proposal_count || 3} nouvelle${(project.proposal_count || 3) > 1 ? "s" : ""} piste${(project.proposal_count || 3) > 1 ? "s" : ""}`;
    const turnKey = `${project.project_id}:${project.turns.length}`;
    if (state.turnKey !== turnKey) {
      state.turnKey = turnKey;
      el("turns").replaceChildren(...project.turns.map(turn => {
        const item = node("div", "", `story-turn ${turn.role}`);
        item.append(node("strong", turn.role === "user" ? "Toi" : "Scénariste"), node("span", turn.text)); return item;
      }));
      el("turns").scrollTop = el("turns").scrollHeight;
    }
    const key = `${project.project_id}:${project.revisions.length}`;
    if (state.paintKey !== key) {
      state.paintKey = key;
      el("versions").replaceChildren(...[...project.revisions].reverse().map(revision => new Option(`v${revision.revision} · ${revision.label}`, revision.revision)));
      paintConcepts(doc); paintScenario(doc.scenario); paintDiagnostics(project.diagnostics || []);
    }
    const job = project.job;
    if (job) message(job.error || job.phase || "", !!job.error);
    else message(scriptProject ? "Script enregistré. Tu peux lancer sa structuration fidèle."
      : `Histoire enregistrée. Tu peux demander ${projectCount} proposition${projectCount > 1 ? "s" : ""}.`);
    const reasoning = job?.reasoning || "", draft = job?.draft || "", live = running();
    const showTrace = live || !!reasoning || !!draft;
    el("live-panel").hidden = !showTrace;
    if (showTrace) {
      el("live-summary").textContent = live ? "Trace du modèle · en direct"
        : job?.status === "succeeded" ? "Trace du dernier échange"
        : "Dernière trace · réponse non appliquée";
      el("reasoning-panel").hidden = !reasoning; el("reasoning").textContent = reasoning;
      el("draft-panel").hidden = !draft; el("draft").textContent = draft;
      el("draft-title").textContent = live ? "Réponse JSON en cours"
        : job?.status === "succeeded" ? "Réponse JSON du dernier échange"
        : "Réponse JSON reçue · non appliquée";
      el("live-empty").hidden = !!reasoning || !!draft;
    }
    controls();
  }
  function paintConcepts(doc) {
    const fields = currentRecipe().concept_fields.filter(field => !["title", "hook"].includes(field.id));
    el("concepts").replaceChildren(...doc.concepts.map((concept, index) => {
      const chosen = doc.selected_id === concept.id;
      const card = node("article", "", `story-concept${chosen ? " selected" : ""}`);
      card.append(node("small", chosen ? "HISTOIRE CHOISIE" : `PISTE ${index + 1}`), node("h3", concept.title), node("p", concept.hook));
      const details = node("details"); details.append(node("summary", "Détails de la piste"));
      const list = node("dl"); fields.forEach(field => list.append(node("dt", field.label), node("dd", concept[field.id] || "—")));
      details.append(list); card.append(details);
      const choose = button(chosen ? "Sélectionnée" : "Choisir cette histoire", () => mutate("select", {concept_id: concept.id}));
      choose.dataset.selected = String(chosen); choose.setAttribute("aria-pressed", String(chosen)); card.append(choose);
      return card;
    }));
  }
  function paintDiagnostics(items) {
    el("diagnostics").hidden = !items.length;
    el("diagnostic-list").replaceChildren(...items.map(item => node("li", item.message, item.level || "info")));
  }
  function paintScenario(scenario) {
    if (!scenario) { paintDiagnostics([]); return; }
    el("scenario-title").textContent = scenario.title; el("logline").textContent = scenario.logline;
    el("cast").replaceChildren();
    for (const [title, items] of [["Personnages", scenario.characters], ["Décors", scenario.locations]]) {
      el("cast").append(node("h3", title));
      for (const item of items) { const paragraph = node("p"); paragraph.append(node("strong", `${item.name} — `), node("span", item.description)); el("cast").append(paragraph); }
    }
    const names = new Map(scenario.characters.map(character => [character.id, character.name]));
    const places = new Map(scenario.locations.map(location => [location.id, location.name]));
    el("scenes").replaceChildren(...scenario.scenes.map((scene, index) => {
      const card = node("article", "", "story-scene"), head = node("div", "", "story-actions");
      head.append(node("h3", `${index + 1}. ${scene.title}`), button("Modifier", () => openSceneEditor(index)),
        button("Copier l’intention", () => exportScenario("copy", index)));
      card.append(head, node("small", `${places.get(scene.location_id)} · ${scene.character_ids.map(id => names.get(id)).join(", ")}`), node("p", scene.action));
      if (scene.dialogue.length) card.append(node("p", scene.dialogue.map(line => dialogueLabel(line, names.get(line.speaker_id))).join("\n"), "story-dialogue"));
      const states = node("details"); states.append(node("summary", "Continuité"), node("p", `Début : ${scene.opening_state}`));
      if (scene.relationship_state) states.append(node("p", `Relation : ${scene.relationship_state}`));
      if (scene.appearance_state) states.append(node("p", `Tenues : ${scene.appearance_state}`));
      if (scene.sexual_state) states.append(node("p", `Position et contacts : ${scene.sexual_state}`));
      states.append(node("p", `Fin : ${scene.ending_state}`)); card.append(states);
      return card;
    }));
  }
  function openSceneEditor(index) {
    const scenario = state.project?.document?.scenario, scene = scenario?.scenes[index]; if (!scene) return;
    state.editScene = index; el("scene-editor-title").textContent = `Modifier la scène ${index + 1}`;
    el("edit-title").value = scene.title; el("edit-opening").value = scene.opening_state;
    el("edit-action").value = scene.action; el("edit-ending").value = scene.ending_state;
    el("edit-dialogue").value = scene.dialogue.map(dialogueEditorLine).join("\n");
    const sceneFields = new Set(currentRecipe().scene_fields.map(field => field.id));
    for (const field of ["relationship", "appearance", "sexual"]) {
      const enabled = sceneFields.has(`${field}_state`);
      el(`edit-${field}-row`).hidden = !enabled; el(`edit-${field}`).required = enabled;
    }
    el("edit-relationship").value = scene.relationship_state || ""; el("edit-appearance").value = scene.appearance_state || "";
    el("edit-sexual").value = scene.sexual_state || "";
    el("edit-speakers").textContent = "Identifiants autorisés : " + scenario.characters
      .filter(character => scene.character_ids.includes(character.id)).map(character => `${character.id} (${character.name})`).join(", ");
    el("scene-editor").showModal();
  }
  async function saveSceneEdit() {
    if (state.editScene === null || blocked()) return;
    const dialogue = el("edit-dialogue").value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
      const fields = line.split("|").map(value => value.trim());
      if (fields.length >= 2 && fields.length < 4 && fields[0]
          && !(fields.length === 3 && deliveryLabels[fields[1]] !== undefined)) {
        return {speaker_id: fields.shift(), text: fields.join("|").trim()};
      }
      if (fields.length === 3 && fields[0] && deliveryLabels[fields[1]] !== undefined && fields[2])
        return {speaker_id: fields[0], delivery: fields[1], text: fields[2]};
      if (fields.length >= 4) {
        const hasId = fields.length >= 5, dialogueId = hasId ? fields.shift() : "";
        const speakerId = fields.shift(), delivery = fields.shift(), note = fields.shift(), text = fields.join("|").trim();
        if (!speakerId || deliveryLabels[delivery] === undefined || !text)
          throw new Error("Mode de dialogue inconnu ou réplique incomplète.");
        return {...(dialogueId ? {dialogue_id: dialogueId} : {}), speaker_id: speakerId, delivery,
          ...(note ? {delivery_note: note} : {}), text};
      }
      throw new Error("Chaque réplique doit suivre le format identifiant | texte, ou id | personnage | mode | indication | texte.");
    });
    const changes = {title: el("edit-title").value.trim(), opening_state: el("edit-opening").value.trim(),
      action: el("edit-action").value.trim(), dialogue, ending_state: el("edit-ending").value.trim()};
    if (!el("edit-relationship-row").hidden) {
      changes.relationship_state = el("edit-relationship").value.trim();
    }
    if (!el("edit-appearance-row").hidden) changes.appearance_state = el("edit-appearance").value.trim();
    if (!el("edit-sexual-row").hidden) changes.sexual_state = el("edit-sexual").value.trim();
    const id = state.project.project_id, token = state.token; state.saving = true; controls();
    try {
      const result = await request(path(id, `/scenes/${state.editScene}`), send("PATCH", {...changes, expected_version: state.project.version}));
      if (token !== state.token) return;
      state.project = result; state.editScene = null; el("scene-editor").close(); paint(); recent().catch(() => {});
    } finally { state.saving = false; controls(); }
  }
  async function mutate(action, body) {
    if (blocked() || !state.project) return;
    const id = state.project.project_id, token = state.token; state.saving = true; controls();
    try {
      const result = await request(path(id, `/${action}`), json({...body, expected_version: state.project.version}));
      if (token !== state.token) return;
      state.project = result; paint(); recent().catch(() => {});
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  }
  async function write(operation, instruction = "") {
    const role = operation === "ideas" ? "architect" : "writer";
    if (blocked() || !state.project || !selectedModel(role)) return;
    const id = state.project.project_id, token = state.token; state.saving = true; controls();
    try {
      const result = await request(path(id, "/write"), json({operation, instruction, model_id: selectedModel(role),
        expected_version: state.project.version, request_id: crypto.randomUUID()}));
      if (token !== state.token) return;
      state.project = result;
      if (instruction === el("instruction").value.trim()) { el("instruction").value = ""; storage.set(`draft.${id}`, ""); }
      paint(); schedule();
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  }
  async function exportScenario(action, index = 0) {
    const id = state.project?.project_id; if (!id) return;
    try {
      const data = await request(path(id, `/export?include_duration=${el("include-duration").checked}`));
      if (action === "copy") {
        const text = data.intentions[index];
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
        else { const area = node("textarea"); area.value = text; area.style.position = "fixed"; area.style.left = "-9999px";
          document.body.append(area); area.select(); const ok = document.execCommand("copy"); area.remove(); if (!ok) throw new Error("Copie indisponible dans ce navigateur."); }
        message("Intention copiée, dialogues inclus.");
      } else {
        const url = URL.createObjectURL(new Blob([data.text], {type: "text/plain;charset=utf-8"}));
        const link = node("a"); link.href = url; link.download = `${id}.txt`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (error) { message(error.message, true); }
  }
  async function activate() {
    if (root.hidden) { clearTimeout(state.timer); return; }
    if (!state.initialized) {
      state.initialized = true;
      const tasks = [models(), specs(), (async () => {
        try { await recent(); const saved = storage.get("project"); if (saved && !state.project) await openProject(saved); }
        catch (error) { message(error.message, true); }
      })()];
      await Promise.allSettled(tasks);
    } else if (state.project && !state.saving) schedule();
    controls();
  }

  el("create-form").addEventListener("submit", async event => {
    event.preventDefault();
    const mode = creationMode();
    if (state.saving || !selectedModel("writer") || (mode === "ideas" && !selectedModel("architect"))
        || (mode === "script" && !el("brief").value.trim())) return;
    state.saving = true; controls(); const token = ++state.token;
    try {
      const recipe = currentRecipe();
      const project = await request("/api/stories/projects", json({title: el("title").value.trim() || "Nouvelle histoire", brief: el("brief").value,
        clip_seconds: Number(el("duration").value), scene_count: Number(el("scene-count").value), recipe_id: recipe.id,
        recipe_version: recipe.version, architect_model_id: selectedModel("architect"), writer_model_id: selectedModel("writer"),
        creation_mode: mode, proposal_count: proposalCount()}));
      if (token !== state.token) return;
      state.project = project; storage.set("project", project.project_id); state.paintKey = ""; state.turnKey = "";
      el("instruction").value = ""; paint(); await recent(); state.saving = false; await write(mode === "script" ? "script" : "ideas");
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  });
  el("chat-form").addEventListener("submit", event => { event.preventDefault(); write("revise", el("instruction").value.trim()); });
  el("scene-form").addEventListener("submit", event => { event.preventDefault(); saveSceneEdit().catch(error => message(error.message, true)); });
  el("scene-close").addEventListener("click", () => { state.editScene = null; el("scene-editor").close(); });
  el("instruction").addEventListener("input", () => { if (state.project) storage.set(`draft.${state.project.project_id}`, el("instruction").value); controls(); });
  el("brief").addEventListener("input", controls);
  el("creation-mode").addEventListener("change", () => { refreshStartMode(); controls(); });
  el("proposal-count").addEventListener("change", () => { refreshStartMode(); controls(); });
  el("recipe").addEventListener("change", paintRecipeDescription);
  for (const role of roles) {
    el(`${role}-model`).addEventListener("change", () => { ++state.modelChoice[role]; state.wantedModel[role] = el(`${role}-model`).value; rememberModel(role); controls(); });
    el(`${role}-local`).addEventListener("change", event => {
      event.stopPropagation(); ++state.modelChoice[role]; const source = el(`${role}-local`).checked ? "local" : "server";
      chooseModel(role, storage.get(`${role}.model.${source}`) || storage.get(`model.${source}`) || (source === "local" ? defaultLocalModel : ""));
      rememberModel(role); controls();
    });
  }
  el("new").addEventListener("click", newProject);
  el("projects").addEventListener("change", () => el("projects").value ? openProject(el("projects").value) : newProject());
  el("refresh-projects").addEventListener("click", async () => { try { await recent(); if (state.project) await openProject(state.project.project_id); } catch (error) { message(error.message, true); } });
  el("refresh-models").addEventListener("click", models);
  el("ideas").addEventListener("click", () => write("ideas", el("instruction").value.trim()));
  el("develop").addEventListener("click", () => write("develop", el("instruction").value.trim()));
  el("restore").addEventListener("click", () => mutate("restore", {revision: Number(el("versions").value)}));
  el("retry").addEventListener("click", () => write(state.project.job.operation, [...state.project.turns].reverse().find(turn => turn.role === "user")?.text || ""));
  el("cancel").addEventListener("click", async () => {
    if (!running()) return; const token = state.token;
    try { const result = await request(path(state.project.project_id, "/cancel"), json({})); if (token === state.token) { state.project = result; paint(); schedule(); } }
    catch (error) { message(error.message, true); }
  });
  el("export").addEventListener("click", () => exportScenario("download"));
  el("recipes").addEventListener("click", () => { const recipe = currentRecipe(); window.PanelForgePromptRecipes?.open({key: recipe.id, version: recipe.version}); });
  el("calls").addEventListener("click", () => { if (state.project) window.PanelForgePromptRecipes?.showHistory(path(state.project.project_id, "/calls")); });
  new MutationObserver(activate).observe(root, {attributes: true, attributeFilter: ["hidden"]});
  window.PanelForgeStories = Object.freeze({current: () => state.project});
  for (const role of roles) preferredModel(role);
  refreshStartMode(); paint(); activate();
})();
