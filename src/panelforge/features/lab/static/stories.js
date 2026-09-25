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
        {id: "sexual_state", label: "Position et contacts sexuels"}]},
    {id: "story.silent-cats", version: "1.0.0", label: "Chats de couple · muet",
      description: "Chats anthropomorphes photoréalistes, comédie de couple tendre et entièrement non verbale.",
      dialogue_policy: "forbidden",
      concept_fields: [{id: "title", label: "Titre"}, {id: "hook", label: "Accroche"},
        {id: "couple_and_dynamic", label: "Le couple et sa dynamique"},
        {id: "domestic_setup", label: "Situation quotidienne"},
        {id: "visual_gag", label: "Gag visuel"},
        {id: "comic_escalation", label: "Escalade comique"},
        {id: "tender_turn", label: "Bascule tendre"}, {id: "ending", label: "Fin"}],
      scene_fields: [{id: "relationship_state", label: "Dynamique relationnelle"},
        {id: "appearance_state", label: "Tenues, pelage et accessoires"}]}];
  const state = {project: null, initialized: false, loading: false, saving: false, models: [], modelsReady: false,
    recipes: fallbackRecipes, wantedModel: {architect: "", writer: ""}, modelChoice: {architect: 0, writer: 0},
    modelError: "", token: 0, timer: null, paintKey: "", turnKey: "", editScene: null, parentStoryId: null};
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
  const dialogueRegisters = [
    ["Actuel", "Aucun pilotage ajouté : comportement actuel."],
    ["Oral direct", "Langue quotidienne et moins littéraire, sans vulgarité forcée."],
    ["Cru", "Formulations franches, familières ou vulgaires naturelles dans la langue choisie."],
    ["Très cru / argot", "Argot et tournures de rue naturels dans la langue choisie, compatibles avec le personnage."],
  ];
  const dialogueLanguages = {French: "Français", English: "English", Korean: "한국어 · Coréen",
    Japanese: "日本語 · Japonais", Russian: "Русский · Russe"};
  function dialogueLabel(line, speaker) {
    const indication = line.delivery_note || deliveryLabels[line.delivery || "spoken"];
    return `${speaker}${indication ? ` — ${indication}` : ""} : « ${line.text} »`;
  }
  function dialogueEditorLine(line) {
    if (!line.dialogue_id && !line.delivery && !line.delivery_note) return `${line.speaker_id} | ${line.text}`;
    return `${line.dialogue_id || ""} | ${line.speaker_id} | ${line.delivery || "spoken"} | ${line.delivery_note || ""} | ${line.text}`;
  }
  const running = () => ["running", "cancelling"].includes(state.project?.job?.status) || state.project?.workflow?.status === "running";
  const blocked = () => state.saving || state.loading || running();
  const creationMode = () => ["script", "continuation", "adapt"].includes(el("creation-mode").value)
    ? el("creation-mode").value : "ideas";
  const narrativeFormat = () => document.querySelector('input[name="story-narrative-format"]:checked')?.value === "long"
    ? "long" : "short";
  const longV2 = () => state.project?.narrative_engine?.id === "story.long" && state.project?.narrative_engine?.version === "2.0.0";
  const unitLabel = () => state.project?.long_options?.delivery === "continuous" ? "Séquence" : "Épisode";
  const longOptions = () => ({profile: el("long-profile").value, delivery: el("long-delivery").value,
    narration: dialogueForbidden() ? "visual" : el("long-narration").value,
    unit_count: Number(el("long-units").value), ending_type: el("long-ending").value});
  const dialogueRegister = () => Math.max(0, Math.min(3, Number(el("dialogue-register").value) || 0));
  const dialogueLanguage = () => dialogueLanguages[el("dialogue-language").value] ? el("dialogue-language").value : "French";
  const modelSource = id => state.models.find(model => model.id === id)?.source || (id?.startsWith("local::") ? "local" : "server");
  const selectedModel = role => state.models.some(model => model.id === el(`${role}-model`).value) ? el(`${role}-model`).value : "";
  const recipeKey = recipe => `${recipe.id}@${recipe.version}`;
  const currentRecipe = () => {
    const recipe = state.project?.recipe;
    const key = recipe ? recipeKey(recipe) : el("recipe").value;
    return state.recipes.find(item => recipeKey(item) === key) || fallbackRecipes[0];
  };
  const dialogueForbidden = () => currentRecipe().dialogue_policy === "forbidden";

  function budgetSummary(derive = false) {
    const longStory = narrativeFormat() === "long";
    const seconds = Number(el("duration").value) || 10, desired = Number(el("target-seconds").value) || 80;
    if (longStory && derive) {
      const units = el("long-delivery").value === "serial" ? Number(el("long-units").value) || 1 : Math.min(12, Math.max(1, Math.ceil(desired / 90)));
      el("long-units").value = units;
      el("scene-count").value = Math.min(12, Math.max(1, Math.ceil(desired / (seconds * units))));
    }
    const units = Number(el("long-units").value) || 1, clips = Number(el("scene-count").value) || 6;
    el("budget-summary").hidden = !longStory;
    const maximum = units * clips * seconds;
    el("budget-summary").textContent = `${units} ${el("long-delivery").value === "serial" ? "épisode(s)" : "séquence(s)"} × ${clips} clips maximum × ${seconds} s = ${maximum} s maximum. ${maximum < desired ? "Ce plafond est inférieur à la durée souhaitée : augmente les clips, leur durée ou les séquences dans Production." : "Le récit peut utiliser moins de clips."}`;
  }

  function feedbackTarget() {
    const [unit_id, index] = el("feedback-target").value.split(":");
    return {unit_id: unit_id || "outline", scene_index: index === undefined ? null : Number(index)};
  }
  function targetLabel(target) {
    if (!target || target.unit_id === "outline") return "L’histoire complète";
    return `${unitLabel()} ${target.unit_id.replace("episode-", "")}${target.scene_index == null ? "" : ` · scène ${target.scene_index + 1}`}`;
  }
  function focusFeedback(unitId, sceneIndex = null, instruction = "") {
    const value = unitId + (sceneIndex == null ? "" : `:${sceneIndex}`);
    if (![...el("feedback-target").options].some(option => option.value === value)) return;
    chooseWritingStage(unitId === "outline" ? "story" : "scenario");
    el("feedback-target").value = value;
    syncFeedbackDraft();
    // A shortcut must never overwrite the author's unsent feedback for this target.
    if (instruction && !el("instruction").value.trim()) {
      el("instruction").value = instruction;
      el("instruction").dispatchEvent(new Event("input", {bubbles: true}));
    }
    paintFeedbackHint(); controls(); el("instruction").scrollIntoView({behavior: "smooth", block: "center"}); el("instruction").focus();
  }
  function issueSceneIndex(issue, unitId) {
    const match = /^scene-(\d+)$/.exec(issue.target_id || "");
    const index = Number.isInteger(issue.scene_index) ? issue.scene_index : match ? Number(match[1]) - 1 : null;
    const scenes = state.project?.document.episode_scenarios?.[unitId]?.scenes;
    return Number.isInteger(index) && index >= 0 && index < (scenes?.length || 0) ? index : null;
  }
  function correctionInstruction(unitId, sceneIndex, issues) {
    const scope = targetLabel({unit_id: unitId, scene_index: sceneIndex});
    const boundary = sceneIndex == null ? "Préserve les éléments qui ne sont pas concernés." : "Conserve les autres scènes inchangées.";
    return `Corrige uniquement les points bloquants suivants dans ${scope}. ${boundary}\n\n`
      + issues.map(issue => `${issue.problem}${issue.suggestion ? `\nProposition : ${issue.suggestion}` : ""}`).join("\n\n");
  }
  function feedbackShortcut(label, unitId, sceneIndex, instruction = "") {
    const action = button(label, () => focusFeedback(unitId, sceneIndex, instruction));
    action.dataset.feedbackShortcut = "true"; action.disabled = blocked();
    action.title = "Ouvrir le retour ciblé, sans appel LLM. La modification ne démarre qu’après ton envoi.";
    return action;
  }
  function syncFeedbackDraft() {
    if (!longV2()) return;
    const id = state.project.project_id, scope = el("feedback-target").value || "outline";
    const key = `draft.${id}.${scope}`, old = state.feedbackDraftKey;
    if (old !== key) {
      const sameProject = old?.startsWith(`draft.${id}.`);
      if (sameProject) storage.set(old, el("instruction").value);
      el("instruction").value = storage.get(key) ?? (sameProject ? "" : el("instruction").value);
      state.feedbackDraftKey = key;
    }
    storage.set(`feedback-target.${id}`, scope);
    storage.set(`draft.${id}`, el("instruction").value);
  }
  function paintFeedbackHint() {
    const target = feedbackTarget();
    el("feedback-context").textContent = `Cible : ${targetLabel(target)}. ${running() ? "Ton texte reste en brouillon. Reprends la main pour l’envoyer après l’appel actif." : "Une question conserve le texte et le mode choisi. Demander une modification réécrit la cible. Pour approuver, utilise le bouton Valider / Continuer dans le bandeau de l’étape."}`;
    el("instruction").placeholder = target.unit_id === "outline" ? "Question : pourquoi cette fin ? Modification : garde cette idée, mais change la fin…"
      : target.scene_index == null ? "Question : que comprend le public ici ? Modification : rends la négociation plus tendue…"
      : "Question : pourquoi ce refus ? Modification : montre plus clairement le refus dans cette scène…";
  }
  const writingPlacements = new Map();
  function arrangeWriting(guided) {
    // Move existing controls, retaining listeners and the legacy short-story layout.
    for (const id of ["recovery-panel", "retry-actions", "draft-history", "versions-panel", "continuity", "long-review", "live-panel", "calls", "call-summary"]) {
      const item = el(id);
      if (!writingPlacements.has(id)) {
        const anchor = document.createComment(`writing:${id}`);
        item.before(anchor); writingPlacements.set(id, anchor);
      }
      const anchor = writingPlacements.get(id);
      const destination = el(id === "live-panel" ? "writing-status" : "writing-details");
      if (guided && item.parentElement !== destination) {
        if (id === "live-panel") el("writing-issues").before(item);
        else destination.append(item);
      } else if (!guided && item.previousSibling !== anchor) anchor.after(item);
    }
  }
  function readingStage() {
    return state.writingView || window.PanelForgeStoryWriting.describe(state.project).stage;
  }
  function chooseWritingStage(stage, focus = false) {
    state.writingView = stage;
    if (state.project) storage.set(`reading.${state.project.project_id}`, stage || "");
    paintWriting();
    if (focus && !el("writing-reader").hidden) el("reading-title").focus({preventScroll: true});
  }
  function paintWriting() {
    const guided = longV2(), visible = guided || (!state.project && narrativeFormat() === "long");
    el("writing-header").hidden = !visible;
    el("writing-reader").hidden = !guided; el("writing-details").hidden = !guided;
    root.classList.toggle("story-writing-guided", guided);
    arrangeWriting(guided);
    if (!visible) {
      delete root.dataset.writingStage;
      el("chat-title").textContent = "Façonner l’histoire";
      el("validate").hidden = false; el("validate").classList.add("primary");
      el("validate").textContent = "Valider et préparer la fabrication";
      el("saved-intention").hidden = el("scenario-selector").hidden = true;
      return;
    }
    const project = state.project, view = window.PanelForgeStoryWriting.describe(project);
    const id = project?.project_id || "new";
    if (state.writingProject !== id) {
      state.writingProject = id;
      const stored = storage.get(`reading.${id}`);
      state.writingView = ["intention", "story", "scenario"].includes(stored) ? stored : null;
    }
    const stage = project ? readingStage() : "intention";
    root.dataset.writingStage = stage;
    const statuses = window.PanelForgeStoryWriting.statuses;
    const setText = (id, value) => { if (el(id).textContent !== value) el(id).textContent = value; };
    for (const item of el("writing-steps").querySelectorAll("button")) {
      const step = item.dataset.writingStage, status = view.steps[step], [symbol, label] = statuses[status];
      item.dataset.state = status; item.disabled = !project && step !== "intention";
      if (step === stage) item.setAttribute("aria-current", "step"); else item.removeAttribute("aria-current");
      const caption = `${symbol} ${label}`;
      if (item.querySelector("small").textContent !== caption) item.querySelector("small").textContent = caption;
    }
    el("writing-status").hidden = !project;
    if (!project) return;
    // Keep the existing ability to fabricate a ready unit before the entire serial story is complete.
    el("validate").hidden = el("validate").disabled || view.action === "validate";
    el("validate").classList.remove("primary"); el("validate").textContent = "Fabriquer cette séquence";
    el("writing-status").dataset.state = view.kind;
    setText("writing-state", `${statuses[view.kind][0]} ${statuses[view.kind][1]}`);
    setText("writing-title", view.title); setText("writing-message", view.message); setText("writing-saved", view.saved);
    const issueKey = JSON.stringify([project.project_id, view.target, view.issues]);
    if (state.writingIssueKey !== issueKey) {
      state.writingIssueKey = issueKey;
      el("writing-issues").replaceChildren(...view.issues.map(issue => {
        const item = node("li"); item.append(node("p", issue.problem || "Point signalé par la vérification."));
        if (issue.suggestion) item.append(node("p", `Proposition : ${issue.suggestion}`, "muted"));
        const index = issueSceneIndex(issue, view.target);
        if (index != null) item.append(feedbackShortcut(`Écrire ma consigne · scène ${index + 1}`, view.target, index,
          correctionInstruction(view.target, index, [issue])));
        return item;
      }));
    }
    el("writing-issues").hidden = !view.issues.length;
    const action = el("next-action");
    action.hidden = !view.action;
    action.dataset.action = view.action || ""; action.textContent = view.label;
    action.disabled = state.saving || state.loading || (view.action && el(view.action)?.disabled)
      || (view.action === "correct-and-continue" && (!selectedModel("architect") || !selectedModel("writer"))) || false;
    action.title = view.action === "correct-and-continue" ? "Lancer une correction ciblée et sa relecture avec les modèles choisis. Une seule tentative ; arrêt si un blocage subsiste." : "";
    if (view.action && action.disabled && !blocked() && ["advance", "retry", "correct-and-continue"].includes(view.action)
        && (!selectedModel("architect") || !selectedModel("writer"))) {
      action.dataset.action = "models"; action.textContent = "Choisir les modèles d’écriture"; action.disabled = false;
    }
    const secondary = el("writing-secondary");
    secondary.hidden = !view.secondary; secondary.dataset.action = view.secondary || "";
    secondary.textContent = view.secondary === "feedback" ? "Écrire ma consigne"
      : view.secondary === "details" ? "Voir le brouillon et les détails" : "Relire ce point · appel LLM";
    // A review of a sequence must target the open sequence, never an unrelated one.
    secondary.disabled = state.saving || state.loading || (view.secondary?.startsWith("review-") &&
      (el(view.secondary).disabled || (view.secondary === "review-episode" && project.document.selected_episode_id !== view.target)));
    secondary.title = view.secondary === "review-episode" && project.document.selected_episode_id !== view.target
      ? "Examine d’abord le point avec l’assistant pour ouvrir la séquence concernée." : "";
    el("writing-current").hidden = stage === view.stage;
    el("saved-intention").hidden = stage !== "intention";
    setText("intention-text", project.brief || "Intention libre : laisser le modèle proposer l’histoire.");
    setText("intention-settings", el("project-brief").textContent);
    const descriptions = {intention: ["Le point de départ", "Ton intention et les réglages enregistrés. Les retours sur la direction se font dans la discussion de l’histoire."],
      story: ["La progression de l’histoire", "Lis les événements, les personnages et la fin avant leur mise en scènes."],
      scenario: ["Les scènes et leurs dialogues", "Lis le déroulé concret. Le bouton « Commenter cette scène » cible directement ton retour."]};
    setText("reading-label", `${["intention", "story", "scenario"].indexOf(stage) + 1} / 3 · ${stage === "intention" ? "INTENTION" : stage === "story" ? "HISTOIRE" : "SCÉNARIO"}`);
    setText("reading-title", descriptions[stage][0]); setText("reading-help", descriptions[stage][1]);
    el("discuss-current").disabled = !project.document.series_outline && !project.document.scenario;
    setText("chat-title", "Discuter et ajuster");
    for (const card of el("series-episodes").querySelectorAll("[data-unit-id]")) {
      const unit = view.units.find(unit => unit.id === card.dataset.unitId);
      if (!unit) continue;
      const [kind, label] = view.unitStatus(unit), caption = card.querySelector("small");
      caption.classList.add("story-state-label"); caption.dataset.state = kind;
      caption.textContent = `${unit.label.split(" · ")[0]} · ${statuses[kind][0]} ${label}`;
    }
    const unitSelect = el("reading-unit"), unitKey = JSON.stringify([project.document.selected_episode_id, view.units]);
    el("scenario-selector").hidden = stage !== "scenario" || view.units.length < 2;
    if (state.readingUnitKey !== unitKey) {
      state.readingUnitKey = unitKey;
      unitSelect.replaceChildren(...view.units.map(unit => {
        const option = new Option(unit.label, unit.id); option.disabled = !unit.written; return option;
      }));
      unitSelect.value = project.document.selected_episode_id || "";
    }
    unitSelect.disabled = blocked();
    const selected = view.units.find(unit => unit.id === project.document.selected_episode_id);
    if (selected) {
      const [kind, label] = view.unitStatus(selected);
      el("reading-unit-status").dataset.state = kind;
      setText("reading-unit-status", `${statuses[kind][0]} ${label}`);
    }
    el("empty").hidden = stage === "intention" || (stage === "story" ? !!project.document.series_outline : !!project.document.scenario);
    if (!el("empty").hidden) {
      setText("empty-title", stage === "story" ? "L’histoire apparaîtra ici" : "Les scènes apparaîtront ici");
      setText("empty-copy", stage === "story" ? "Le bandeau ci-dessus indique la prochaine action." : "La direction de l’histoire doit être relue et validée avant le développement des scènes.");
    }
  }
  async function writingAction(action) {
    const projectId = state.project?.project_id;
    const view = window.PanelForgeStoryWriting.describe(state.project);
    if (action === "correct-and-continue") {
      chooseWritingStage(null);
      await workflowAction("correct-and-continue", {unit_id: view.target, mode: el("active-mode").value,
        architect_model_id: selectedModel("architect"), writer_model_id: selectedModel("writer")});
    } else if (action === "feedback") {
      chooseWritingStage(view.stage);
      if (view.target !== "outline" && view.target !== state.project.document.selected_episode_id
          && state.project.document.episode_scenarios?.[view.target] && !blocked()) {
        await openSeriesEpisode(view.target, state.project.scene_count, state.project.clip_seconds, false);
      }
      if (state.project?.project_id !== projectId) return;
      const index = view.issues.length === 1 ? issueSceneIndex(view.issues[0], view.target) : null;
      focusFeedback(view.target, index, view.issues.length ? correctionInstruction(view.target, index, view.issues) : "");
    } else if (action === "details") {
      el("writing-details").open = true;
      el("writing-details").scrollIntoView({behavior: "smooth", block: "start"});
      el("writing-details").querySelector("summary").focus();
    } else if (action === "models") {
      el("model-settings").open = true; el("model-settings").scrollIntoView({behavior: "smooth", block: "center"}); el(!selectedModel("architect") ? "architect-model" : "writer-model").focus();
    } else if (action && el(action) && !el(action).disabled) {
      chooseWritingStage(null);
      el(action).click();
    }
  }
  function paintWorkflow() {
    const project = state.project, guided = longV2(), doc = project?.document;
    root.classList.toggle("story-guided", !!guided); root.classList.toggle("story-is-new", !project);
    el("guided-tools").hidden = !guided;
    el("feedback-target-row").hidden = !guided; el("feedback-context").hidden = !guided;
    el("question").hidden = !guided;
    el("send").textContent = guided ? "Demander une modification" : "Envoyer";
    el("send").type = guided ? "button" : "submit";
    el("question").type = guided ? "submit" : "button";
    el("question").classList.toggle("primary", guided);
    el("send").classList.toggle("primary", !guided);
    el("question").title = "Obtenir une réponse sans modifier l’histoire ni changer de mode.";
    el("send").title = guided ? "Demander une réécriture de la cible sélectionnée." : "";
    if (!guided) return;
    const flow = project.workflow;
    const usage = project.llm_usage;
    el("call-summary").textContent = usage
      ? `${usage.calls} appel${usage.calls > 1 ? "s" : ""} enregistré${usage.calls > 1 ? "s" : ""} · ${Math.floor(usage.elapsed_ms / 60000)} min ${Math.round((usage.elapsed_ms % 60000) / 1000)} s cumulées · ${usage.repair_calls} récupération${usage.repair_calls > 1 ? "s" : ""}${usage.earlier_calls_unknown ? " · suivi depuis cette mise à jour" : ""}`
      : "Les échanges antérieurs sont disponibles dans Échanges LLM.";
    if (document.activeElement !== el("active-mode")) el("active-mode").value = flow?.mode || "manual";
    const written = Object.keys(doc.episode_scenarios || {}).length > 0;
    const directionPending = flow?.status === "awaiting_author" && flow.wait_target === "outline";
    el("workflow-message").textContent = directionPending && written
      ? "Des scènes sont déjà écrites. Valide la direction de l’histoire pour poursuivre les vérifications ; les scènes à jour seront conservées."
      : flow?.message || "Active le parcours guidé pour poursuivre cette histoire existante.";
    const issues = flow?.status === "blocked" ? doc.reviews?.[flow.wait_target || "outline"]?.issues?.filter(item => item.severity === "blocking") || [] : [];
    el("workflow-issues").hidden = !issues.length;
    el("workflow-issues").replaceChildren(...issues.map(item => node("li", `${item.problem} ${item.suggestion}`)));
    el("progress").textContent = "Intention → Histoire → Scénario";
    el("advance").textContent = flow?.status === "awaiting_author" ? (flow.wait_target === "outline" ? (written ? "Valider l’histoire et continuer" : "Valider et développer le scénario") : "Valider et continuer")
      : flow?.status === "ready" ? "Scénario terminé" : !doc.series_outline ? "Imaginer mon histoire" : "Continuer le parcours";
    el("pause").hidden = !running();
    const previous = el("feedback-target").value;
    const options = [new Option("L’histoire complète", "outline")];
    for (const unit of doc.series_outline?.episodes || []) {
      const scenario = doc.episode_scenarios?.[unit.id]; if (!scenario) continue;
      options.push(new Option(`${unitLabel()} ${unit.id.replace("episode-", "")} — ${unit.title}`, unit.id));
      scenario.scenes.forEach((scene, index) => options.push(new Option(`↳ Scène ${index + 1} — ${scene.title}`, `${unit.id}:${index}`)));
    }
    el("feedback-target").replaceChildren(...options);
    const selected = flow?.wait_target || (doc.scenario ? doc.selected_episode_id : "outline"), key = `${project.project_id}:${selected}`;
    el("feedback-target").value = (state.feedbackKey === key || (state.feedbackProject === project.project_id && el("instruction").value.trim())) && options.some(item => item.value === previous) ? previous : selected;
    const remembered = storage.get(`feedback-target.${project.project_id}`);
    if (state.feedbackProject !== project.project_id && options.some(item => item.value === remembered)) el("feedback-target").value = remembered;
    state.feedbackKey = key; state.feedbackProject = project.project_id;
    syncFeedbackDraft(); paintFeedbackHint();
  }
  function paintFabricationGate() {
    const project = state.project, doc = project?.document, status = project?.long_status;
    const holder = el("fabrication-gate"), action = el("fabrication-next"), validate = el("validate");
    holder.hidden = !longV2() || !doc?.scenario || (status?.fabrication_ready && !blocked());
    validate.title = "";
    if (holder.hidden) { el("fabrication-reason").textContent = ""; return; }
    const unit = status?.units?.[doc.selected_episode_id], flow = project.workflow;
    const review = doc.reviews?.[doc.selected_episode_id];
    const failure = ["failed", "interrupted", "cancelled"].includes(project.job?.status);
    const directionPending = flow?.status === "awaiting_author" && flow.wait_target === "outline";
    let reason, label = "Continuer les vérifications", target = "advance";
    if (blocked()) {
      reason = "Un traitement est en cours. La fabrication sera disponible lorsque les vérifications de cette séquence seront terminées.";
      target = "wait";
    } else if (failure) {
      reason = "Une étape s’est interrompue. Sa réponse doit être récupérée ou l’étape relancée avant de poursuivre.";
      label = "Voir l’étape interrompue"; target = "recovery";
    } else if (unit?.stale) {
      reason = "L’histoire ou une séquence précédente a changé. Cette séquence doit être remise à jour puis relue avant sa fabrication.";
      label = "Reprendre la mise à jour";
    } else if (!status?.outline_reviewed) {
      reason = "La progression de l’histoire doit être vérifiée avant de valider ses scènes.";
    } else if (!unit?.previous_ready) {
      reason = "Une séquence précédente doit encore être vérifiée ou corrigée avant de fabriquer celle-ci.";
    } else if (review?.issues?.some(issue => issue.severity === "blocking") && status?.reviews?.[doc.selected_episode_id]?.current) {
      reason = "La relecture signale un problème bloquant à corriger dans cette séquence.";
    } else {
      reason = review ? "Les scènes ont changé depuis leur dernière relecture. Une nouvelle vérification est nécessaire."
        : "Le scénario est écrit, mais sa relecture n’a pas encore été effectuée. Les remarques du diagnostic automatique ci-dessous ne remplacent pas cette relecture.";
      label = "Relire le scénario";
    }
    if (!blocked() && !failure && flow?.status === "blocked" && flow.wait_target) {
      reason += " Le parcours attend ton retour sur le point à clarifier.";
      label = "Préciser mon retour"; target = "feedback";
    } else if (!blocked() && !failure && directionPending) {
      reason += " Valide d’abord la direction de l’histoire pour poursuivre.";
      label = unit?.written && !unit.stale && status?.outline_reviewed && unit.previous_ready && !review
        ? "Valider l’histoire et relire le scénario" : "Valider l’histoire et continuer";
    }
    if (target === "advance" && (!selectedModel("architect") || !selectedModel("writer"))) {
      reason += " Choisis les modèles d’écriture pour continuer.";
      label = "Choisir les modèles"; target = "models";
    }
    el("fabrication-reason").textContent = reason;
    validate.title = reason;
    action.textContent = label; action.dataset.action = target;
    action.hidden = target === "wait"; action.disabled = blocked();
  }
  async function workflowAction(action, body = {}, clearFeedback = false) {
    if (!state.project || (blocked() && action !== "pause")) return;
    const id = state.project.project_id, token = state.token;
    state.saving = true; controls();
    try {
      const result = await request(path(id, `/${action}`), json(action === "pause" ? {} : {...body, expected_version: state.project.version}));
      if (token !== state.token) return;
      state.project = result;
      if (clearFeedback) { el("instruction").value = ""; storage.set(`draft.${id}`, ""); if (state.feedbackDraftKey) storage.set(state.feedbackDraftKey, ""); }
      paint(); schedule(); recent().catch(() => {});
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { if (token === state.token) { state.saving = false; controls(); } }
  }
  function sendFeedback(question = false) {
    if (!el("instruction").value.trim()) return;
    workflowAction("feedback", {...feedbackTarget(), question, instruction: el("instruction").value.trim()}, true);
  }

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
    const longStory = narrativeFormat() === "long";
    root.querySelectorAll("[data-story-long-only]").forEach(item => { item.hidden = !longStory; });
    for (const option of el("creation-mode").options) {
      option.hidden = longStory ? !["ideas", "adapt"].includes(option.value) : option.value === "adapt";
      option.disabled = option.hidden;
    }
    if (el("creation-mode").selectedOptions[0]?.hidden) el("creation-mode").value = "ideas";
    el("creation-mode").disabled = false;
    el("long-options").hidden = !longStory;
    const mode = creationMode(), script = mode === "script", continuation = mode === "continuation";
    const silent = dialogueForbidden();
    el("brief-label").textContent = script ? "Script complet · obligatoire"
      : continuation ? "Épisodes précédents ou résumé de la saga · obligatoire" : "Ton idée · facultative";
    el("brief").required = script || continuation;
    el("brief").maxLength = continuation ? 60000 : 12000;
    el("brief").placeholder = script
      ? silent ? "Colle ici le script complet de la scène muette, avec ses actions et réactions sans dialogue…"
      : "Colle ici le script complet avec ses scènes, actions, locuteurs et dialogues…"
      : continuation ? "Colle les épisodes précédents du plus ancien au plus récent, ou leur résumé puis le dernier épisode complet…"
      : silent ? "Deux chats préparent le petit-déjeuner ; l’un cherche un câlin pendant que l’autre veut finir sa recette…"
      : "Un patron avocat odieux qui arnaque ses clients… Ou laisse le LLM te surprendre.";
    el("mode-description").textContent = script
      ? silent ? "Un seul appel au Rédacteur regroupe les actions dans le nombre exact de micro-scènes ; le script reste entièrement sans paroles."
      : "Un seul appel au Rédacteur regroupe le texte dans le nombre exact de micro-scènes. Les dialogues détectés sont contrôlés mot pour mot."
      : continuation ? "L’Architecte condense toute la saga en mémoire cumulative, puis propose une suite causale sans redécouvrir les faits acquis."
      : "L’Architecte propose une histoire, puis le Rédacteur en développe les scènes.";
    el("create").textContent = script ? "Structurer fidèlement ce script"
      : continuation ? "Proposer une suite" : "Proposer une histoire";
    el("create-note").textContent = script
      ? silent ? "Le script est regroupé sans omission ; toute parole, voix off, narration et texte lisible restent interdits."
      : "Le script est regroupé sans omission dans le nombre choisi : aucun passage ni dialogue ne doit être réinventé."
      : continuation ? "Même si le dernier épisode avait déjà un passé, les faits durables et les conflits ouverts restent dans la mémoire de saga, sans appel LLM supplémentaire."
      : silent ? "Comédie de couple photoréaliste, tendre et compréhensible uniquement par les gestes."
      : "Conflits simples, personnages excessifs, retournements visuels. Tu peux orienter le ton dans ton idée.";
    el("empty-title").textContent = script ? "Un script prêt à structurer" : continuation ? "Comment poursuivre cette saga ?"
      : silent ? "Quelle scène muette raconter ?" : "Quelle histoire raconter ?";
    el("empty-copy").textContent = script
      ? "Le Rédacteur transformera le script en fiches et micro-scènes sans passer par des propositions intermédiaires."
      : continuation ? "Le LLM résumera le canon antérieur puis proposera une suite fondée sur une reprise, un obstacle et une conséquence préparée."
      : silent ? "Le LLM proposera une comédie de couple féline sans paroles, puis la développera en actions visuelles."
      : "Le LLM proposera une histoire avec conflit, progression et fin. Tu pourras l’ajuster, puis développer le scénario.";
    const register = script || silent ? 0 : dialogueRegister(), details = dialogueRegisters[register];
    el("dialogue-language").disabled = silent;
    el("dialogue-language-row").setAttribute("aria-disabled", String(silent));
    el("dialogue-language-description").textContent = silent
      ? "Désactivé : cette famille ne contient aucune parole."
      : script ? "Le script n’est pas traduit : choisis la langue réellement écrite et parlée."
      : "Les nouveaux dialogues sont écrits dans cette langue ; les descriptions restent en français.";
    el("dialogue-register").disabled = script || silent;
    el("dialogue-register-row").setAttribute("aria-disabled", String(script || silent));
    el("dialogue-register-label").textContent = silent ? "Sans paroles" : script ? "Script fidèle" : details[0];
    el("dialogue-register-value").textContent = silent ? "—" : `${register}/3`;
    el("dialogue-register-description").textContent = silent
      ? "Désactivé : dialogue, voix off, narration et texte lisible sont interdits dans cette famille."
      : script ? "Désactivé : les dialogues du script restent strictement inchangés."
      : details[1];
    el("scene-count-label").textContent = longStory ? "Plafond de clips par unité" : "Nombre exact de micro-scènes";
    el("format-help").textContent = longStory
      ? "De 1 à ce plafond de clips par épisode ou séquence. Le récit détermine le nombre utile ; la durée reste uniforme."
      : "Ce nombre est obligatoire. Plusieurs événements du brief ou du script peuvent être regroupés dans une même micro-scène.";
    el("long-unit-label").textContent = el("long-delivery").value === "continuous" ? "Nombre de séquences" : "Nombre d’épisodes";
    el("long-narration").disabled = silent;
    el("recipe-description").textContent = longStory && currentRecipe().id === "story.brainrot"
      ? "Fruits anthropomorphes par défaut. Le champ Univers peut préciser des gouttes, des humains ou d’autres personnages."
      : currentRecipe().description;
    if (longStory) {
      const adapt = creationMode() === "adapt";
      el("brief-label").textContent = adapt ? "Histoire à préserver et développer · obligatoire" : "Point de départ · facultatif";
      el("brief").required = adapt; el("brief").maxLength = adapt ? 60000 : 12000;
      el("brief").placeholder = adapt ? "Colle l’histoire, ses découvertes et sa fin. Précise les éléments à conserver et ce qui peut être inventé." : "Quelle promesse, quel conflit ou quelle découverte veux-tu explorer ?";
      el("mode-description").textContent = "Une histoire avec sa progression, puis des scènes vérifiées. Les pauses dépendent de ton accompagnement.";
      el("create").textContent = adapt ? "Développer mon histoire" : "Imaginer mon histoire";
      el("create-note").textContent = el("workflow-mode").value === "automatic" ? "Le moteur écrira et vérifiera le scénario. Tu peux reprendre la main ; les médias seront préparés ensuite."
        : "Une histoire te sera présentée pour discussion, puis tu valideras les séquences. Les vérifications s’enchaînent automatiquement.";
      el("empty-title").textContent = "Construire une histoire longue";
      el("empty-copy").textContent = "Le moteur peut choisir la progression et la fin à partir de ton idée. Tu peux lui adresser des retours à chaque pause.";
    }
    budgetSummary();
  }
  function controls() {
    const project = state.project, busy = blocked(), doc = project?.document;
    el("recipes").hidden = longV2() || (!project && narrativeFormat() === "long");
    el("next-episode").hidden = !doc?.scenario;
    el("next-episode").disabled = busy || !doc?.scenario;
    const mode = creationMode(), scriptStart = mode === "script", sourceRequired = ["script", "continuation", "adapt"].includes(mode);
    const conversationRole = project?.narrative_format === "long" && doc?.series_outline && !doc?.scenario
      ? "architect" : "writer";
    el("create").disabled = state.saving || !selectedModel("writer") || (!scriptStart && !selectedModel("architect"))
      || (sourceRequired && !el("brief").value.trim());
    el("send").disabled = busy || !(doc?.concepts.length || doc?.series_outline || doc?.scenario)
      || !el("instruction").value.trim() || !selectedModel(conversationRole);
    el("question").disabled = el("send").disabled;
    el("advance").disabled = busy || project?.workflow?.status === "ready" || !selectedModel("architect") || !selectedModel("writer");
    el("pause").disabled = state.saving || !running();
    el("active-mode").disabled = busy;
    el("feedback-target").disabled = busy;
    el("ideas").disabled = busy || !project || !selectedModel("architect");
    el("outline").disabled = busy || (!doc?.selected_id && project?.creation_mode !== "adapt") || !selectedModel("architect");
    el("develop").disabled = busy || !doc?.selected_id || !selectedModel("writer");
    el("restore").disabled = busy || !project?.revisions.length;
    el("cancel").disabled = !running() || project?.job?.status === "cancelling";
    const retryRole = ["ideas", "outline", "compose"].includes(project?.job?.operation)
      || project?.job?.operation?.includes("outline") || project?.job?.operation?.startsWith("review_")
      || project?.job?.feedback_target?.unit_id === "outline"
      || (project?.job?.operation === "revise" && conversationRole === "architect") ? "architect" : "writer";
    el("retry").disabled = busy || !selectedModel(retryRole);
    el("revalidate").disabled = busy || project?.job?.can_revalidate === false;
    el("revalidate").title = project?.job?.can_revalidate === false
      ? project.job.revalidation_error || "Le brouillon ne satisfait pas encore les contrôles locaux."
      : "Appliquer la réponse déjà reçue, sans demander une nouvelle rédaction.";
    el("running").hidden = !running();
    el("retry").hidden = !["failed", "interrupted", "cancelled"].includes(project?.job?.status);
    el("revalidate").hidden = project?.job?.status !== "failed" || !project?.job?.draft?.trim();
    el("concepts").querySelectorAll("button").forEach(item => { item.disabled = busy || item.dataset.selected === "true"; });
    el("series-episodes").querySelectorAll("button,input").forEach(item => { item.disabled = busy || item.dataset.locked === "true"; });
    el("scenes").querySelectorAll("button").forEach(item => { item.disabled = busy; });
    root.querySelectorAll("[data-feedback-shortcut]").forEach(item => { item.disabled = busy; });
    if (el("validate")) el("validate").disabled = busy || !doc?.scenario || (longV2() && !project.long_status?.fabrication_ready);
    if (el("next-episode")) el("next-episode").disabled = busy || !doc?.scenario;
    const unitState = project?.long_status?.units?.[doc?.selected_episode_id];
    for (const [id, locked, role] of [
      ["review-outline", !doc?.series_outline, "architect"],
      ["repair-outline", !doc?.reviews?.outline?.issues?.length || !project?.long_status?.reviews?.outline?.current, "architect"],
      ["revise-outline", !doc?.series_outline || !el("instruction").value.trim(), "architect"],
      ["review-episode", !doc?.scenario || unitState?.stale || !unitState?.previous_ready || !project?.long_status?.outline_reviewed, "architect"],
      ["repair-episode", !doc?.reviews?.[doc?.selected_episode_id]?.issues?.length || !project?.long_status?.reviews?.[doc?.selected_episode_id]?.current || !unitState?.previous_ready || !project?.long_status?.outline_reviewed, "writer"],
      ["rewrite-episode", !doc?.scenario || !unitState?.previous_ready || !project?.long_status?.outline_reviewed, "writer"],
    ]) el(id).disabled = busy || locked || !selectedModel(role);
    paintFabricationGate();
    paintWriting();
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
    if (!state.project) refreshStartMode();
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
    state.parentStoryId = null;
    state.loading = false; storage.set("project", ""); el("projects").value = "";
    el("title").value = ""; el("brief").value = ""; el("creation-mode").value = "ideas";
    el("prior-story").value = "";
    el("format-short").checked = true; el("format-long").checked = false;
    el("dialogue-register").value = "0"; el("dialogue-language").value = "French";
    for (const role of roles) preferredModel(role);
    refreshStartMode(); paint(); el("brief").focus();
  }
  function paintVisualContinuity(project) {
    const host = el("visual-continuity"), scenario = project?.document?.scenario;
    host.hidden = !scenario || project.narrative_format !== "long";
    if (host.hidden) { host.replaceChildren(); delete host._continuityKey; return; }
    const id = project.project_id;
    window.PanelForgeContinuity.render(host, {identity: id, revision: project.version,
      data: scenario.visual_continuity, characters: scenario.characters, scenes: scenario.scenes,
      disabled: blocked(), onSave: async (visual_continuity, expected_version) => {
        if (state.project?.project_id !== id) throw new Error("Cette histoire n’est plus ouverte.");
        if (blocked()) throw new Error("Attends la fin de l’écriture avant de modifier la continuité.");
        state.saving = true; controls();
        try {
          const result = await request(path(id, "/continuity"), send("PUT", {expected_version, visual_continuity}));
          if (state.project?.project_id === id) { state.project = result; state.paintKey = ""; }
        } finally { state.saving = false; paint(); }
      }});
  }
  function paint() {
    const project = state.project, doc = project?.document;
    paintWorkflow();
    const longProject = project?.narrative_format === "long";
    paintVisualContinuity(project);
    window.dispatchEvent(new CustomEvent("panelforge:story", {detail: project}));
    el("create-form").hidden = !!project; el("conversation-panel").hidden = !project;
    el("empty").hidden = !!(doc?.concepts.length || doc?.series_outline || doc?.scenario); el("versions-panel").hidden = !project?.revisions.length;
    el("outline").hidden = !longProject || (!doc?.selected_id && project?.creation_mode !== "adapt") || !!doc?.series_outline;
    el("outline").textContent = longV2() ? "Construire le contrat et l’arc" : "Construire l’arc en 4 épisodes";
    el("long-review").hidden = !longV2() || !doc?.series_outline;
    el("develop").hidden = longProject || !doc?.selected_id; el("scenario").hidden = !doc?.scenario;
    el("series").hidden = !longProject || !doc?.series_outline;
    paintRecipeDescription();
    if (!project) { el("concepts").replaceChildren(); el("series-episodes").replaceChildren(); paintContinuity(null); message(""); controls(); return; }
    el("projects").value = project.project_id;
    const recipe = currentRecipe();
    const scriptProject = project.creation_mode === "script", continuationProject = project.creation_mode === "continuation";
    const projectRegister = recipe.dialogue_policy === "forbidden" ? "Sans paroles"
      : dialogueRegisters[scriptProject ? 0 : (project.dialogue_register || 0)][0];
    const projectLanguage = recipe.dialogue_policy === "forbidden" ? "Sans paroles"
      : dialogueLanguages[project.dialogue_language || "French"] || dialogueLanguages.French;
    el("next-episode").hidden = !doc?.scenario;
    el("next-episode").textContent = "Créer l’épisode suivant";
    paintContinuity(doc?.continuity || doc?.continuity_source);
    const startLabel = scriptProject ? "Script fidèle" : continuationProject ? "Suite d’une histoire" : "Histoire proposée";
    el("project-brief").textContent = `${recipe.label} · ${longProject ? "Histoire longue · 4 épisodes" : "Histoire courte"} · ${startLabel} · Dialogues : ${projectLanguage} · ${projectRegister}\n${project.brief || "Idées libres"}\n${project.scene_count} micro-scènes par défaut · ${project.clip_seconds} s par clip`;
    if (longV2()) {
      const optionLabel = (id, value) => [...el(id).options].find(option => option.value === value)?.textContent || value;
      el("project-brief").textContent = `${project.visual_universe || (recipe.id === "story.brainrot" ? "Univers selon le brief · fruits par défaut" : recipe.label)} · ${project.long_options.unit_count} ${unitLabel().toLowerCase()}s · ${optionLabel("long-profile", project.long_options.profile)} · ${optionLabel("long-narration", project.long_options.narration)}\n${project.brief || "Idées libres"}\nAu maximum ${project.scene_count} clips de ${project.clip_seconds} s par unité · ${project.long_options.unit_count * project.scene_count * project.clip_seconds} s au total · Dialogues : ${projectLanguage}`;
    }
    el("ideas").hidden = scriptProject || project.creation_mode === "adapt";
    el("ideas").textContent = continuationProject ? "Proposer une autre suite" : "Proposer une autre histoire";
    const turnKey = `${project.project_id}:${project.turns.length}`;
    if (state.turnKey !== turnKey) {
      state.turnKey = turnKey;
      el("turns").replaceChildren(...project.turns.map(turn => {
        const item = node("div", "", `story-turn ${turn.role}`);
        item.append(node("strong", `${turn.role === "user" ? "Toi" : "Scénariste"}${turn.target ? ` · ${targetLabel(turn.target)}` : ""}`), node("span", turn.text)); return item;
      }));
      el("turns").scrollTop = el("turns").scrollHeight;
    }
    const key = `${project.project_id}:${project.revisions.length}:${doc.selected_episode_id || ""}:${JSON.stringify(project.long_status || {})}`;
    if (state.paintKey !== key) {
      state.paintKey = key;
      el("versions").replaceChildren(...[...project.revisions].reverse().map(revision => new Option(`v${revision.revision} · ${revision.label}`, revision.revision)));
      paintConcepts(doc); paintSeries(doc); paintScenario(doc.scenario); paintDiagnostics(project.diagnostics || []);
    }
    const job = project.job;
    paintRecovery(project);
    paintDiagnostics(project.diagnostics || []);
    if (longV2()) message("");
    else if (job) message(job.revalidation_error || job.error || [job.phase, ...(job.normalizations || [])].filter(Boolean).join(" · "), !!job.error);
    else message(scriptProject ? "Script enregistré. Tu peux lancer sa structuration fidèle."
      : continuationProject ? "Historique enregistré. L’Architecte peut maintenant construire la mémoire de saga et les suites."
      : "Histoire enregistrée. Tu peux maintenant demander sa création.");
    const reasoning = job?.reasoning || "", draft = job?.draft || "", live = running();
    const showTrace = live || !!reasoning || !!draft;
    el("live-panel").hidden = !showTrace;
    if (showTrace) {
      el("live-summary").textContent = live ? "Trace du modèle · en direct"
        : job?.status === "succeeded" ? "Trace du dernier échange"
        : "Dernière trace · réponse non appliquée";
      const traceKey = `${project.project_id}:${job?.request_id || job?.started_at || job?.operation || ""}`;
      const newTrace = state.liveTraceKey !== traceKey;
      if (newTrace) {
        state.liveTraceKey = traceKey;
        if (live && longV2()) el("live-panel").open = true;
      }
      const started = Date.parse(job?.started_at), ended = Date.parse(job?.finished_at);
      const seconds = Number.isFinite(started) ? Math.max(0, Math.floor(((live || !Number.isFinite(ended) ? Date.now() : ended) - started) / 1000)) : null;
      const duration = seconds === null ? "" : `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s · `;
      el("live-metrics").textContent = `${duration}${reasoning.length.toLocaleString("fr-FR")} caractères de raisonnement · ${draft.length.toLocaleString("fr-FR")} caractères de réponse`;
      el("reasoning-panel").hidden = !reasoning;
      el("draft-panel").hidden = !draft;
      for (const [id, text] of [["reasoning", reasoning], ["draft", draft]]) {
        const pre = el(id), follow = newTrace || pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
        if (pre.textContent !== text) {
          pre.textContent = text;
          if (live && follow) requestAnimationFrame(() => { if (state.liveTraceKey === traceKey) pre.scrollTop = pre.scrollHeight; });
        }
      }
      el("draft-title").textContent = live ? "Réponse JSON en cours"
        : job?.status === "succeeded" ? "Réponse JSON du dernier échange"
        : "Réponse JSON reçue · non appliquée";
      el("live-empty").hidden = !!reasoning || !!draft;
    }
    paintLongReview();
    controls();
  }
  function paintRecovery(project) {
    const job = project.job || {}, panel = el("recovery-panel");
    const actions = el(longV2() ? "recovery-actions" : "retry-actions");
    if (el("revalidate").parentElement !== actions) actions.prepend(el("revalidate"));
    const failed = job.status === "failed" && !!job.draft;
    panel.hidden = !failed;
    if (failed) {
      el("recovery-title").textContent = job.can_revalidate ? "Brouillon récupérable" : "Brouillon conservé · points à résoudre";
      el("recovery-help").textContent = job.can_revalidate
        ? "Récupère ce texte sans nouvel appel au modèle. Les vérifications éditoriales et de durée restent à effectuer avant fabrication."
        : "La récupération sans appel LLM est indisponible tant que les problèmes ci-dessous persistent. Le texte reçu est conservé ; relancer le LLM demande une nouvelle rédaction.";
      const unique = [...new Map((job.draft_diagnostics || []).map(item => [`${item.code}:${item.path}`, item])).values()];
      el("recovery-issues").replaceChildren(...unique.map(item => node("li", item.message, item.level || "warning")));
      const preview = job.draft_preview;
      el("readable-draft").hidden = !Array.isArray(preview?.scenes);
      if (Array.isArray(preview?.scenes)) {
        const names = Object.fromEntries((Array.isArray(preview.characters) ? preview.characters : []).filter(item => item && typeof item === "object").map(item => [item.id, item.name]));
        el("readable-scenes").replaceChildren(...preview.scenes.filter(scene => scene && typeof scene === "object").map((scene, index) => {
          const card = node("article", "", "story-scene");
          card.append(node("strong", `${index + 1} · ${scene.title || "Scène"}`), node("p", scene.action || ""));
          for (const line of Array.isArray(scene.dialogue) ? scene.dialogue : []) {
            if (line && typeof line.text === "string") card.append(node("p", `${names[line.speaker_id] || line.speaker_id || "Personnage"} : ${line.text}`, "story-dialogue"));
          }
          card.append(node("p", scene.ending_state || "", "muted")); return card;
        }));
      }
    }
    const history = project.draft_history || [];
    el("draft-history").hidden = !history.length;
    if (state.draftHistoryKey !== `${project.project_id}:${history.length}`) {
      state.draftHistoryKey = `${project.project_id}:${history.length}`;
      el("draft-history-items").replaceChildren(...history.map((item, index) => {
        const button = node("button", `Télécharger le brouillon ${index + 1} · ${item.operation} · ${item.status}`);
        button.type = "button";
        button.addEventListener("click", () => {
          const url = URL.createObjectURL(new Blob([JSON.stringify(item, null, 2)], {type: "application/json"}));
          const link = document.createElement("a"); link.href = url; link.download = `brouillon-${index + 1}.json`; link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }); return button;
      }));
    }
  }
  function paintLongReview() {
    if (!longV2() || !state.project.document.series_outline) return;
    const doc = state.project.document, outline = doc.series_outline, contract = outline.contract;
    const content = el("long-contract"); content.replaceChildren();
    for (const [label, value] of [["Promesse", contract.promise], ["Objectif", contract.protagonist_goal],
      ["Enjeux", contract.stakes], ["À préserver", contract.must_keep.join("\n")], ["Libertés", contract.freedoms.join("\n")]]) {
      const p = node("p"); p.append(node("strong", `${label} : `), node("span", value || "—")); content.append(p);
    }
    outline.world_rules.forEach(rule => content.append(node("p", `Règle · ${rule.rule}\nLimites · ${rule.limits ?? "Non précisées"}`)));
    outline.secrets.forEach(secret => content.append(node("p", `Secret · ${secret.truth}\nConnu par : ${secret.known_by.join(", ") || "personne"} · Révélation : ${secret.reveal_episode_id || "réservée après cette histoire"}`)));
    const canon = el("long-canon"), memory = doc.episode_states?.[doc.selected_episode_id]; canon.replaceChildren();
    if (!memory) canon.append(node("p", "Cette unité n’est pas encore rédigée."));
    else {
      memory.facts.forEach(fact => canon.append(node("p", `${fact.text} · source : ${fact.event_id}`)));
      memory.knowledge.forEach(item => canon.append(node("p", `${item.character_ids.join(", ")} apprend : ${item.secret_id} · source : ${item.event_id}`)));
      canon.append(node("p", `Fils ouverts : ${memory.open_threads.join(" · ") || "aucun"}`),
        node("p", `Fils résolus : ${memory.resolved_threads.join(" · ") || "aucun"}`));
    }
    const narrativeStatus = state.project.long_status || {};
    el("long-state").textContent = narrativeStatus.fabrication_ready ? "Cette unité est relue et prête pour Fabrication."
      : !narrativeStatus.outline_reviewed ? "Relis le contrat et l’arc avant de développer la suite."
      : "La rédaction doit être à jour et relue sans problème bloquant avant Fabrication.";
    for (const [id, key] of [["outline-review-result", "outline"], ["episode-review-result", doc.selected_episode_id]]) {
      const holder = el(id), review = doc.reviews?.[key]; holder.replaceChildren();
      if (!review) { holder.append(node("p", "Relecture à effectuer.", "muted")); continue; }
      holder.append(node("p", `${narrativeStatus.reviews?.[key]?.current ? "Relecture actuelle" : "À relire après modification"} · ${review.summary}`));
      const list = node("ul");
      review.issues.forEach(issue => list.append(node("li", `${issue.severity === "blocking" ? "À corriger" : "Suggestion"} · ${issue.target_id} : ${issue.problem}\n${issue.suggestion}`, issue.severity)));
      holder.append(list);
    }
  }
  function paintConcepts(doc) {
    const fields = currentRecipe().concept_fields.filter(field => !["title", "hook"].includes(field.id));
    el("concepts").replaceChildren(...doc.concepts.map((concept, index) => {
      const chosen = doc.selected_id === concept.id;
      const card = node("article", "", `story-concept${chosen ? " selected" : ""}`);
      card.append(node("small", doc.concepts.length === 1 ? "HISTOIRE PROPOSÉE" : chosen ? "HISTOIRE CHOISIE" : `PISTE ${index + 1}`), node("h3", concept.title), node("p", concept.hook));
      const details = node("details"); details.append(node("summary", "Détails de la piste"));
      const list = node("dl"); fields.forEach(field => list.append(node("dt", field.label), node("dd", concept[field.id] || "—")));
      if (concept.continuation_plan) {
        const plan = concept.continuation_plan;
        list.append(node("dt", "Reprise du canon"), node("dd", plan.carry_over),
          node("dt", "Nouvel obstacle"), node("dd", plan.obstacle),
          node("dt", "Conséquence préparée"), node("dd", plan.payoff),
          node("dt", "Éléments nouveaux annoncés"), node("dd", plan.introduced_elements.length ? plan.introduced_elements.join(" · ") : "Aucun"));
      }
      details.append(list); card.append(details);
      if (doc.concepts.length > 1 || !chosen) {
        const choose = button(chosen ? "Sélectionnée" : "Choisir cette histoire", () => mutate("select", {concept_id: concept.id}));
        choose.dataset.selected = String(chosen); choose.setAttribute("aria-pressed", String(chosen)); card.append(choose);
      }
      return card;
    }));
  }
  async function openSeriesEpisode(episodeId, sceneCount, clipSeconds, develop) {
    if (blocked() || !state.project) return;
    const id = state.project.project_id, token = state.token;
    state.saving = true; controls();
    try {
      const result = await request(path(id, "/series-episode"), json({episode_id: episodeId,
        scene_count: sceneCount, clip_seconds: clipSeconds, expected_version: state.project.version}));
      if (token !== state.token) return;
      state.project = result; state.paintKey = ""; paint();
    } catch (error) { if (token === state.token) message(error.message, true); return; }
    finally { state.saving = false; controls(); }
    if (develop && !state.project.document?.scenario) await write("develop");
  }
  function paintSeries(doc) {
    const outline = doc?.series_outline;
    if (!outline) { el("series-episodes").replaceChildren(); return; }
    el("series-title").textContent = outline.title;
    el("series-premise").textContent = outline.premise;
    el("series-arc").textContent = `Arc global : ${outline.overall_arc}`;
    el("series-ending").textContent = `Aboutissement prévu : ${outline.ending}`;
    el("series-characters").replaceChildren(...outline.characters.map(character => {
      const item = node("p"); item.append(node("strong", `${character.name} — `), node("span", character.description)); return item;
    }));
    const scenarios = doc.episode_scenarios || {}, formats = doc.episode_formats || {};
    el("series-episodes").replaceChildren(...outline.episodes.map((episode, index) => {
      const complete = !!scenarios[episode.id], selected = doc.selected_episode_id === episode.id;
      const unitState = state.project.long_status?.units?.[episode.id];
      const card = node("article", "", `story-series-episode${selected ? " selected" : ""}${(longV2() ? unitState?.ready : complete) ? " complete" : ""}`);
      card.dataset.unitId = episode.id;
      const progress = unitState?.stale ? "À RÉÉCRIRE · PASSÉ MODIFIÉ" : unitState?.ready ? "RELU" : complete ? "À RELIRE" : "PLANIFIÉ";
      card.append(node("small", `${unitLabel().toUpperCase()} ${index + 1} · ${longV2() ? progress : complete ? "DÉVELOPPÉ" : "PLANIFIÉ"}`),
        node("h3", episode.title), node("p", episode.promise), node("p", `Obstacle : ${episode.conflict}`));
      const details = node("details"), list = node("ol"); details.append(node("summary", "Aboutissement et raccord"));
      if (longV2()) episode.events.forEach(event => list.append(node("li", `${event.trigger}\n${event.change}\nÀ montrer : ${event.evidence}`)));
      else episode.beats.forEach(beat => list.append(node("li", beat)));
      if (longV2()) card.append(list); else details.append(list);
      details.append(node("p", `Aboutissement : ${episode.local_payoff}`),
        node("p", `Fin : ${episode.ending_state}`), node("p", `Suite : ${episode.carry_forward}`)); card.append(details);
      const format = formats[episode.id] || {scene_count: state.project.scene_count, clip_seconds: state.project.clip_seconds};
      const controls = node("div", "", "story-series-format");
      const scenesLabel = node("label", longV2() ? "Plafond de clips" : "Scènes"), scenes = document.createElement("input");
      scenes.type = "number"; scenes.min = "1"; scenes.max = "12"; scenes.step = "1"; scenes.value = format.scene_count;
      const durationLabel = node("label", "Secondes / clip"), duration = document.createElement("input");
      duration.type = "number"; duration.min = "5"; duration.max = "15"; duration.step = "1"; duration.value = format.clip_seconds;
      if (complete || longV2()) { scenes.dataset.locked = "true"; duration.dataset.locked = "true"; scenes.disabled = duration.disabled = true; }
      scenesLabel.append(scenes); durationLabel.append(duration); controls.append(scenesLabel, durationLabel); card.append(controls);
      if (state.project.workflow) controls.hidden = true;
      const label = unitLabel().toLowerCase(), article = label === "séquence" ? "cette" : "cet";
      const action = button(complete ? (selected ? `${unitLabel()} ouvert${label === "séquence" ? "e" : ""}` : `Ouvrir ${article} ${label}`) : `Développer ${article} ${label}`, () => {
        const sceneCount = Math.max(1, Math.min(12, Number(scenes.value) || state.project.scene_count));
        const clipSeconds = Math.max(5, Math.min(15, Number(duration.value) || state.project.clip_seconds));
        if (longV2()) chooseWritingStage("scenario");
        openSeriesEpisode(episode.id, sceneCount, clipSeconds, !complete);
      });
      action.dataset.selected = String(selected && complete);
      if (state.project.workflow && !complete) { action.hidden = true; card.append(node("p", "Cette séquence sera rédigée par le parcours.", "muted")); }
      if (selected && complete) { action.dataset.locked = "true"; action.disabled = true; }
      if (longV2() && !complete && (!unitState?.previous_ready || !state.project.long_status?.outline_reviewed)) {
        action.dataset.locked = "true"; action.disabled = true;
        if (!state.project.workflow) card.append(node("p", "Relis d’abord l’arc et les unités précédentes.", "muted"));
      }
      card.append(action); return card;
    }));
  }
  function paintDiagnostics(items) {
    // Older servers/projects may still return accumulated diagnostics until restarted.
    const unique = [...new Map(items.map(item => [JSON.stringify([item.code, item.path, item.scene_index, item.level, item.message]), item])).values()];
    const timedScenes = new Set(unique.filter(item => item.code === "clip_load").map(item => item.scene_index));
    const visible = unique.filter(item => item.level === "blocking" || item.code !== "dialogue_density" || !timedScenes.has(item.scene_index));
    const unitId = state.project?.document.selected_episode_id;
    const view = longV2() ? window.PanelForgeStoryWriting.describe(state.project) : null;
    const mainIssues = view?.target === unitId && view.kind === "attention" ? view.issues : [];
    const blockers = visible.filter(item => item.level === "blocking" && !mainIssues.some(issue => issue.problem === item.message));
    const observations = visible.filter(item => item.level !== "blocking");
    el("diagnostics").hidden = !blockers.length && !observations.length;
    const scope = `${state.project?.project_id}:${unitId}`;
    if (state.diagnosticScope !== scope) {
      state.diagnosticScope = scope; el("diagnostic-observations").open = false;
    }
    const key = JSON.stringify([scope, longV2(), blockers, observations]);
    if (state.diagnosticKey === key) return;
    state.diagnosticKey = key;
    el("diagnostic-blockers").hidden = !blockers.length;
    el("diagnostic-observations").hidden = !observations.length;
    el("diagnostics").classList.toggle("story-observations-only", !blockers.length);
    el("diagnostic-title").textContent = `Observations facultatives · ${observations.length}`;
    el("diagnostic-summary").textContent = "Ces indications ne déclenchent pas de correction automatique. Une mention de personnage ou une estimation de durée peut être normale."
      + (longV2() ? " Les points retenus comme bloquants par la relecture figurent dans le bandeau de l’étape." : "");
    const row = item => {
      const result = node("li", "", item.level || "info"); result.append(node("span", item.message));
      const index = longV2() ? issueSceneIndex(item, unitId) : null;
      if (index != null) result.append(feedbackShortcut(`Écrire un retour · scène ${index + 1}`, unitId, index));
      return result;
    };
    el("diagnostic-blocker-list").replaceChildren(...blockers.map(row));
    el("diagnostic-list").replaceChildren(...observations.map(row));
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
      if (longV2()) head.append(button("Commenter cette scène", () => focusFeedback(state.project.document.selected_episode_id, index)));
      card.append(head, node("small", `${places.get(scene.location_id)} · ${scene.character_ids.map(id => names.get(id)).join(", ")}`), node("p", scene.action));
      if (scene.dialogue.length) card.append(node("p", scene.dialogue.map(line => dialogueLabel(line, names.get(line.speaker_id))).join("\n"), "story-dialogue"));
      const states = node("details"); states.append(node("summary", "Continuité"), node("p", `Début : ${scene.opening_state}`));
      if (scene.relationship_state) states.append(node("p", `Relation : ${scene.relationship_state}`));
      if (scene.appearance_state) states.append(node("p", `Tenues : ${scene.appearance_state}`));
      if (scene.sexual_state) states.append(node("p", `Position et contacts : ${scene.sexual_state}`));
      states.append(node("p", `Fin : ${scene.ending_state}`)); card.append(states);
      const evidence = longV2() && state.project.document.episode_states?.[state.project.document.selected_episode_id]?.scene_events?.[index];
      if (evidence) states.append(node("p", `Information indispensable : ${evidence.evidence}`),
        node("small", `Événements : ${evidence.event_ids.join(", ")} · Actions successives estimées : ${evidence.action_seconds} s`));
      return card;
    }));
  }

  function paintContinuity(memory) {
    el("continuity").hidden = !memory;
    if (!memory) { el("continuity-content").replaceChildren(); return; }
    const content = document.createDocumentFragment();
    content.append(node("p", memory.series_summary), node("h4", "Dernier état connu"), node("p", memory.latest_ending));
    for (const [field, label] of [["established_facts", "Faits acquis"], ["character_states", "État des personnages"],
      ["unresolved_threads", "Fils encore ouverts"], ["available_elements", "Éléments encore mobilisables"]]) {
      content.append(node("h4", label));
      const list = node("ul");
      const items = memory[field] || [];
      if (items.length) items.forEach(item => list.append(node("li", item)));
      else list.append(node("li", "Aucun."));
      content.append(list);
    }
    el("continuity-content").replaceChildren(content);
  }

  function prepareNextEpisode() {
    if (!state.project?.document?.scenario || blocked()) return;
    window.PanelForgeStoryFollowup?.open({project: state.project, models: state.models,
      architect: selectedModel("architect"), writer: selectedModel("writer"),
      onWritten: async project => { await openProject(project.project_id); }});
  }
  function openSceneEditor(index) {
    const scenario = state.project?.document?.scenario, scene = scenario?.scenes[index]; if (!scene) return;
    state.editScene = index; el("scene-editor-title").textContent = `Modifier la scène ${index + 1}`;
    el("edit-title").value = scene.title; el("edit-opening").value = scene.opening_state;
    el("edit-action").value = scene.action; el("edit-ending").value = scene.ending_state;
    el("edit-dialogue").value = scene.dialogue.map(dialogueEditorLine).join("\n");
    const silent = currentRecipe().dialogue_policy === "forbidden";
    el("edit-dialogue-row").hidden = silent; el("edit-dialogue-help").hidden = silent;
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
    finally { state.saving = false; controls(); schedule(); }
  }
  async function write(operation, instruction = "") {
    const revisesOutline = operation === "revise" && state.project?.narrative_format === "long"
      && state.project.document?.series_outline && !state.project.document?.scenario;
    const role = ["ideas", "outline", "compose"].includes(operation) || revisesOutline || operation.includes("outline") || operation.startsWith("review_") ? "architect" : "writer";
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

  el("writing-steps").addEventListener("click", event => {
    const button = event.target.closest("button[data-writing-stage]");
    if (button && !button.disabled) chooseWritingStage(button.dataset.writingStage, true);
  });
  el("next-action").addEventListener("click", () => writingAction(el("next-action").dataset.action));
  el("writing-secondary").addEventListener("click", () => writingAction(el("writing-secondary").dataset.action));
  el("writing-current").addEventListener("click", () => chooseWritingStage(null, true));
  el("discuss-current").addEventListener("click", () => focusFeedback(readingStage() === "scenario" ? state.project.document.selected_episode_id || "outline" : "outline"));
  el("reading-unit").addEventListener("change", () => {
    const id = el("reading-unit").value;
    if (state.project?.document?.episode_scenarios?.[id] && !blocked()) openSeriesEpisode(id, state.project.scene_count, state.project.clip_seconds, false);
  });

  el("create-form").addEventListener("submit", async event => {
    event.preventDefault();
    const mode = creationMode();
    if (state.saving || !selectedModel("writer") || (mode !== "script" && !selectedModel("architect"))
        || (["script", "continuation", "adapt"].includes(mode) && !el("brief").value.trim())) return;
    state.saving = true; controls(); const token = ++state.token;
    try {
      const recipe = currentRecipe();
      const project = await request("/api/stories/projects", json({title: el("title").value.trim() || "Nouvelle histoire", brief: el("brief").value,
        clip_seconds: Number(el("duration").value), scene_count: Number(el("scene-count").value), recipe_id: recipe.id,
        recipe_version: recipe.version, architect_model_id: selectedModel("architect"), writer_model_id: selectedModel("writer"),
        creation_mode: mode, dialogue_register: mode === "script" || dialogueForbidden() ? 0 : dialogueRegister(),
        dialogue_language: dialogueLanguage(), narrative_format: narrativeFormat(), parent_story_id: state.parentStoryId,
        long_options: narrativeFormat() === "long" ? longOptions() : null,
        prior_story: narrativeFormat() === "long" ? el("prior-story").value.trim() : "",
        workflow_mode: narrativeFormat() === "long" ? el("workflow-mode").value : null,
        visual_universe: narrativeFormat() === "long" ? el("universe").value.trim() : "",
        target_seconds: narrativeFormat() === "long" ? Number(el("target-seconds").value) : null}));
      if (token !== state.token) return;
      state.project = project; storage.set("project", project.project_id); state.paintKey = ""; state.turnKey = "";
      el("instruction").value = ""; paint(); await recent(); state.saving = false;
      if (longV2()) await workflowAction("advance", {mode: el("workflow-mode").value});
      else await write(mode === "script" ? "script" : "ideas");
    } catch (error) { if (token === state.token) message(error.message, true); }
    finally { state.saving = false; controls(); }
  });
  el("chat-form").addEventListener("submit", event => { event.preventDefault(); if (longV2()) sendFeedback(true); else write("revise", el("instruction").value.trim()); });
  el("send").addEventListener("click", () => { if (longV2()) sendFeedback(false); });
  el("feedback-target").addEventListener("change", () => { syncFeedbackDraft(); paintFeedbackHint(); controls(); });
  el("advance").addEventListener("click", () => workflowAction("advance", {mode: el("active-mode").value,
    architect_model_id: selectedModel("architect"), writer_model_id: selectedModel("writer")}));
  el("fabrication-next").addEventListener("click", () => {
    const action = el("fabrication-next").dataset.action;
    if (action === "advance") return el("advance").click();
    if (action === "feedback") return focusFeedback(state.project.workflow.wait_target);
    const target = action === "models" ? el("model-settings")
      : !el("revalidate").hidden && !el("revalidate").disabled ? el("revalidate") : el("retry");
    if (action === "models") target.open = true;
    target.scrollIntoView({behavior: "smooth", block: "center"});
    (action === "models" ? el("architect-model") : target).focus();
  });
  el("pause").addEventListener("click", () => workflowAction("pause"));
  el("workflow-mode").addEventListener("change", refreshStartMode);
  el("target-seconds").addEventListener("change", () => budgetSummary(true));
  for (const id of ["long-units", "scene-count", "duration"]) el(id).addEventListener("input", () => budgetSummary());
  root.querySelectorAll("[data-story-example]").forEach(item => item.addEventListener("click", () => {
    const kind = item.dataset.storyExample;
    const examples = {
      social: {brief: "Un rendez-vous tourne au règlement de comptes quand arrive l’addition. Chaque tentative pour se défausser se retourne contre son auteur. Une joute verbale drôle et tendue, dans un seul restaurant, avec une chute ironique.", universe: "Fruits anthropomorphes", seconds: 80, narration: "dialogue", ending: "reversal"},
      melodrama: {brief: "Une trahison amoureuse entre des gouttes d’eau, avec une fin cruelle.", universe: "Gouttes d’eau anthropomorphes", seconds: 60, narration: "visual", ending: "reversal"},
      fantasy: {brief: "Des fruits portent leur temps de vie sur le front. Un garçon presque à zéro découvre un moyen interdit d’en gagner. L’urgence et la convoitise doivent aussi être compréhensibles dans les paroles.", universe: "Fruits anthropomorphes", seconds: 120, narration: "dialogue", ending: "open"}
    }, example = examples[kind];
    el("format-long").checked = true; el("format-short").checked = false; el("creation-mode").value = "ideas";
    el("recipe").value = "story.brainrot@1.0.0"; el("long-profile").value = kind; el("long-narration").value = example.narration;
    el("long-ending").value = example.ending; el("long-delivery").value = "continuous"; el("universe").value = example.universe;
    el("duration").value = "10";
    el("target-seconds").value = example.seconds; el("brief").value = example.brief; el("dialogue-register").value = "1";
    refreshStartMode(); budgetSummary(true); controls(); el("brief").focus();
  }));
  el("scene-form").addEventListener("submit", event => { event.preventDefault(); saveSceneEdit().catch(error => message(error.message, true)); });
  el("scene-close").addEventListener("click", () => { state.editScene = null; el("scene-editor").close(); });
  el("instruction").addEventListener("input", () => {
    if (state.project) storage.set(`draft.${state.project.project_id}`, el("instruction").value);
    if (longV2() && state.feedbackDraftKey) storage.set(state.feedbackDraftKey, el("instruction").value);
    controls();
  });
  el("brief").addEventListener("input", controls);
  el("creation-mode").addEventListener("change", () => { refreshStartMode(); controls(); });
  for (const input of document.querySelectorAll('input[name="story-narrative-format"]'))
    input.addEventListener("change", () => { refreshStartMode(); budgetSummary(true); controls(); });
  el("long-delivery").addEventListener("change", refreshStartMode);
  for (const [id, operation] of [["review-outline", "review_outline"], ["review-episode", "review_episode"],
    ["repair-outline", "repair_outline"], ["repair-episode", "repair_episode"], ["revise-outline", "revise_outline"],
    ["rewrite-episode", "develop"]]) el(id).addEventListener("click", () => write(operation, operation === "revise_outline" ? el("instruction").value.trim() : ""));
  el("dialogue-register").addEventListener("input", refreshStartMode);
  el("dialogue-language").addEventListener("change", refreshStartMode);
  el("recipe").addEventListener("change", () => { paintRecipeDescription(); controls(); });
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
  el("outline").addEventListener("click", () => write("outline", el("instruction").value.trim()));
  el("develop").addEventListener("click", () => write("develop", el("instruction").value.trim()));
  el("restore").addEventListener("click", () => mutate("restore", {revision: Number(el("versions").value)}));
  el("revalidate").addEventListener("click", () => mutate("revalidate", {}));
  el("retry").addEventListener("click", () => {
    if (!longV2()) return write(state.project.job.operation, [...state.project.turns].reverse().find(turn => turn.role === "user")?.text || "");
    const role = state.project.job.model_role === "architect_model_id" ? "architect" : "writer";
    workflowAction("retry", {model_id: selectedModel(role)});
  });
  el("cancel").addEventListener("click", async () => {
    if (!running()) return; const token = state.token;
    try { const result = await request(path(state.project.project_id, "/cancel"), json({})); if (token === state.token) { state.project = result; paint(); schedule(); } }
    catch (error) { message(error.message, true); }
  });
  el("export").addEventListener("click", () => exportScenario("download"));
  el("next-episode").addEventListener("click", prepareNextEpisode);
  el("recipes").addEventListener("click", () => { const recipe = currentRecipe(); window.PanelForgePromptRecipes?.open({key: recipe.id, version: recipe.version}); });
  el("calls").addEventListener("click", () => { if (state.project) window.PanelForgePromptRecipes?.showHistory(path(state.project.project_id, "/calls")); });
  new MutationObserver(activate).observe(root, {attributes: true, attributeFilter: ["hidden"]});
  window.PanelForgeStories = Object.freeze({current: () => state.project, open: openProject, createNew: newProject,
    refreshList: recent, canSwitch: () => !state.loading && !state.saving && !el("projects").disabled});
  for (const role of roles) preferredModel(role);
  refreshStartMode(); paint(); activate();
})();
