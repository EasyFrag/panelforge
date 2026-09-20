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
  function focusFeedback(unitId, sceneIndex = null) {
    el("feedback-target").value = unitId + (sceneIndex == null ? "" : `:${sceneIndex}`);
    paintFeedbackHint(); el("instruction").scrollIntoView({behavior: "smooth", block: "center"}); el("instruction").focus();
  }
  function paintFeedbackHint() {
    const target = feedbackTarget();
    el("feedback-context").textContent = `Cible : ${targetLabel(target)}. ${running() ? "Ton texte reste en brouillon. Reprends la main pour l’envoyer après l’appel actif." : "Appliquer modifie le texte ; poser une question ouvre une discussion."}`;
    el("instruction").placeholder = target.unit_id === "outline" ? "Garde cette idée, mais change la fin : je veux que la trahison soit découverte…"
      : target.scene_index == null ? "Dans cette séquence, rends la négociation plus tendue, en gardant la fin prévue…"
      : "Garde les personnages, mais montre plus clairement le refus dans cette scène…";
  }
  function paintWorkflow() {
    const project = state.project, guided = longV2(), doc = project?.document;
    root.classList.toggle("story-guided", !!guided); root.classList.toggle("story-is-new", !project);
    el("guided-tools").hidden = !guided;
    el("feedback-target-row").hidden = !guided; el("feedback-context").hidden = !guided;
    el("question").hidden = !guided;
    el("send").textContent = guided ? "Appliquer mon retour" : "Envoyer";
    if (!guided) return;
    const flow = project.workflow;
    if (document.activeElement !== el("active-mode")) el("active-mode").value = flow?.mode || "manual";
    const written = Object.keys(doc.episode_scenarios || {}).length > 0;
    const directionPending = flow?.status === "awaiting_author" && flow.wait_target === "outline";
    el("workflow-message").textContent = directionPending && written
      ? "Des scènes sont déjà écrites. Valide la direction de l’histoire pour poursuivre les vérifications ; les scènes à jour seront conservées."
      : flow?.message || "Active le parcours guidé pour poursuivre cette histoire existante.";
    const issues = flow?.status === "blocked" ? doc.reviews?.[flow.wait_target || "outline"]?.issues?.filter(item => item.severity === "blocking") || [] : [];
    el("workflow-issues").hidden = !issues.length;
    el("workflow-issues").replaceChildren(...issues.map(item => node("li", `${item.problem} ${item.suggestion}`)));
    el("progress").textContent = !doc.series_outline ? "① Histoire → ② Scénario → ③ Prêt à fabriquer"
      : flow?.status === "ready" ? "✓ Histoire → ✓ Scénario → ✓ Prêt à fabriquer" : "✓ Histoire → ② Scénario → ③ Prêt à fabriquer";
    el("advance").textContent = flow?.status === "awaiting_author" ? (flow.wait_target === "outline" ? (written ? "Valider l’histoire et continuer" : "Développer le scénario") : "Valider et continuer")
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
    el("feedback-target").value = state.feedbackKey === key && options.some(item => item.value === previous) ? previous : selected;
    state.feedbackKey = key;
    paintFeedbackHint();
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
      if (clearFeedback) { el("instruction").value = ""; storage.set(`draft.${id}`, ""); }
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
    el("revalidate").disabled = busy;
    el("running").hidden = !running();
    el("retry").hidden = !["failed", "interrupted", "cancelled"].includes(project?.job?.status);
    el("revalidate").hidden = project?.job?.status !== "failed" || !project?.job?.draft?.trim();
    el("concepts").querySelectorAll("button").forEach(item => { item.disabled = busy || item.dataset.selected === "true"; });
    el("series-episodes").querySelectorAll("button,input").forEach(item => { item.disabled = busy || item.dataset.locked === "true"; });
    el("scenes").querySelectorAll("button").forEach(item => { item.disabled = busy; });
    if (el("validate")) el("validate").disabled = busy || !doc?.scenario || (longV2() && !project.long_status?.fabrication_ready);
    if (el("next-episode")) el("next-episode").disabled = busy || !doc?.scenario || (longV2() && !project.long_status?.fabrication_ready);
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
    el("format-short").checked = true; el("format-long").checked = false;
    el("dialogue-register").value = "0"; el("dialogue-language").value = "French";
    for (const role of roles) preferredModel(role);
    refreshStartMode(); paint(); el("brief").focus();
  }
  function paint() {
    const project = state.project, doc = project?.document;
    paintWorkflow();
    const longProject = project?.narrative_format === "long";
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
    if (longProject) {
      const episodes = doc.series_outline?.episodes || [];
      const currentEpisode = episodes.findIndex(item => item.id === doc.selected_episode_id);
      const hasNextEpisode = currentEpisode >= 0 && currentEpisode < episodes.length - 1;
      el("next-episode").hidden = !hasNextEpisode;
      el("next-episode").textContent = unitLabel() === "Séquence" ? "Développer la séquence suivante" : "Développer l’épisode suivant";
    } else {
      el("next-episode").hidden = false;
      el("next-episode").textContent = "Créer l’épisode suivant";
    }
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
    const key = `${project.project_id}:${project.revisions.length}:${doc.selected_episode_id || ""}`;
    if (state.paintKey !== key) {
      state.paintKey = key;
      el("versions").replaceChildren(...[...project.revisions].reverse().map(revision => new Option(`v${revision.revision} · ${revision.label}`, revision.revision)));
      paintConcepts(doc); paintSeries(doc); paintScenario(doc.scenario); paintDiagnostics(project.diagnostics || []);
    }
    const job = project.job;
    if (job) message(job.error || [job.phase, ...(job.normalizations || [])].filter(Boolean).join(" · "), !!job.error);
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
      el("reasoning-panel").hidden = !reasoning; el("reasoning").textContent = reasoning;
      el("draft-panel").hidden = !draft; el("draft").textContent = draft;
      el("draft-title").textContent = live ? "Réponse JSON en cours"
        : job?.status === "succeeded" ? "Réponse JSON du dernier échange"
        : "Réponse JSON reçue · non appliquée";
      el("live-empty").hidden = !!reasoning || !!draft;
    }
    paintLongReview();
    controls();
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
      const card = node("article", "", `story-series-episode${selected ? " selected" : ""}${complete ? " complete" : ""}`);
      const unitState = state.project.long_status?.units?.[episode.id];
      const progress = unitState?.stale ? "À RÉÉCRIRE · PASSÉ MODIFIÉ" : unitState?.ready ? "RELU" : complete ? "À RELIRE" : "PLANIFIÉ";
      card.append(node("small", `${unitLabel().toUpperCase()} ${index + 1} · ${longV2() ? progress : complete ? "DÉVELOPPÉ" : "PLANIFIÉ"}`),
        node("h3", episode.title), node("p", episode.promise), node("p", `Obstacle : ${episode.conflict}`));
      const details = node("details"), list = node("ol"); details.append(node("summary", "Étapes et payoff"));
      if (longV2()) episode.events.forEach(event => list.append(node("li", `${event.id} · ${event.trigger}\nChangement : ${event.change}\nÀ montrer ou entendre : ${event.evidence}\nPréparé par : ${event.depends_on.join(", ") || "situation initiale"}`)));
      else episode.beats.forEach(beat => list.append(node("li", beat)));
      details.append(list, node("p", `Payoff local : ${episode.local_payoff}`),
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

  function continuationSource(project) {
    const scenario = project.document?.scenario, memory = project.document?.continuity;
    const latest = JSON.stringify(scenario, null, 2);
    let history = memory ? `MÉMOIRE CUMULATIVE VALIDÉE\n${JSON.stringify(memory, null, 2)}`
      : `HISTORIQUE ANTÉRIEUR FOURNI AU PROJET PRÉCÉDENT\n${project.brief || "Aucun résumé disponible."}`;
    const suffix = `\n\nRÈGLE DE PRIORITÉ — en cas d’écart, l’épisode détaillé ci-dessous prévaut sur la mémoire résumée.\n\nÉPISODE LE PLUS RÉCENT — SOURCE DÉTAILLÉE\n${latest}`;
    const maximum = 60000, available = maximum - suffix.length;
    if (history.length > available) history = `[… historique ancien tronqué pour respecter la limite …]\n${history.slice(-Math.max(0, available - 64))}`;
    return (history + suffix).slice(0, maximum);
  }

  function prepareNextEpisode() {
    const source = state.project;
    if (!source?.document?.scenario || blocked()) return;
    if (source.narrative_format === "long" && source.document.series_outline) {
      const episodes = source.document.series_outline.episodes;
      const current = episodes.findIndex(item => item.id === source.document.selected_episode_id);
      const next = episodes[current + 1];
      if (!next) return;
      const format = source.document.episode_formats?.[next.id]
        || {scene_count: source.scene_count, clip_seconds: source.clip_seconds};
      openSeriesEpisode(next.id, format.scene_count, format.clip_seconds,
        !source.document.episode_scenarios?.[next.id]);
      return;
    }
    const values = {recipe: recipeKey(source.recipe), title: `${source.title} · suite`, brief: continuationSource(source),
      scenes: source.scene_count, duration: source.clip_seconds,
      register: source.dialogue_register || 0, language: source.dialogue_language || "French",
      architect: el("architect-model").value, writer: el("writer-model").value};
    newProject();
    state.parentStoryId = source.project_id;
    el("recipe").value = values.recipe; el("creation-mode").value = "continuation";
    el("title").value = values.title; el("brief").value = values.brief;
    el("scene-count").value = values.scenes; el("duration").value = values.duration;
    el("dialogue-register").value = values.register;
    el("dialogue-language").value = values.language;
    chooseModel("architect", values.architect); chooseModel("writer", values.writer);
    paintRecipeDescription(); refreshStartMode(); paint(); el("brief").focus();
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
  el("chat-form").addEventListener("submit", event => { event.preventDefault(); if (longV2()) sendFeedback(); else write("revise", el("instruction").value.trim()); });
  el("question").addEventListener("click", () => sendFeedback(true));
  el("feedback-target").addEventListener("change", paintFeedbackHint);
  el("advance").addEventListener("click", () => workflowAction("advance", {mode: el("active-mode").value,
    architect_model_id: selectedModel("architect"), writer_model_id: selectedModel("writer")}));
  el("fabrication-next").addEventListener("click", () => {
    const action = el("fabrication-next").dataset.action;
    if (action === "advance") return el("advance").click();
    if (action === "feedback") return focusFeedback(state.project.workflow.wait_target);
    const target = action === "models" ? el("model-settings")
      : !el("revalidate").hidden ? el("revalidate") : el("retry");
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
  el("instruction").addEventListener("input", () => { if (state.project) storage.set(`draft.${state.project.project_id}`, el("instruction").value); controls(); });
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
  window.PanelForgeStories = Object.freeze({current: () => state.project});
  for (const role of roles) preferredModel(role);
  refreshStartMode(); paint(); activate();
})();
