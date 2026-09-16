(() => {
  "use strict";
  const node = (tag, text, className) => {
    const el = document.createElement(tag); if (text) el.textContent = text;
    if (className) el.className = className; return el;
  };
  const button = text => { const el = node("button", text); el.type = "button"; return el; };
  const request = async (url, options = {}) => {
    const response = await fetch(url.startsWith("/api/") ? url : `/api/prompt-recipes${url}`, options);
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Erreur HTTP ${response.status}`);
    return data;
  };
  const json = (method, data) => ({ method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data) });
  const label = (text, field) => { const el = node("label", text); el.append(field); return el; };
  const option = (value, text) => { const el = node("option", text); el.value = value; return el; };
  const mainFields = {"plan.system": "Plan · consignes système", "writer.system": "Rédaction · consignes système",
    "revision.system": "Ajuster le prompt avant rendu", "render.system": "Ajuster après rendu · consignes système"};
  const familyLabels = {prompt_lab: "Libertés créatives", vocal_policy: "Dialogue", classic_cinematic: "Mise en scène Classique",
    sensual_cinematic: "Mise en scène Sensuel", combat_cinematic_policy: "Mise en scène Combat", combat_preparation: "Libertés Combat"};
  let modal, recipeSelect, revisions, components, editor, status, scope, note, save, activate, preview, history, extras, lifecycleNote;
  let packageData = null, fields = {}, component = "plan.system", dirty = false, busy = false, token = 0, context = null;

  function discard() { return !dirty || window.confirm("Abandonner les modifications non enregistrées ?"); }
  function message(text, error = false) { status.textContent = text; status.classList.toggle("error-text", error); }
  function controls() {
    recipeSelect.disabled = busy;
    for (const el of [revisions, components, editor, note, extras]) el.disabled = busy || !packageData;
    save.disabled = busy || !packageData || !dirty;
    activate.disabled = busy || !packageData || packageData.revision === packageData.active || dirty;
    preview.disabled = busy || dirty || !context?.sessionId || !packageData
      || context.key !== packageData.cookbook_id || context.version !== packageData.version
      || !["plan.system", "writer.system"].includes(component);
    history.disabled = busy || !context?.sessionId;
  }
  function mount() {
    if (modal) return;
    modal = node("dialog", "", "prompt-recipes-dialog"); modal.setAttribute("aria-labelledby", "prompt-recipes-title");
    const head = node("div", "", "prompt-recipes-heading");
    const title = node("h2", "Recettes LLM"); title.id = "prompt-recipes-title";
    const close = button("Fermer"); close.addEventListener("click", () => { if (!busy && discard()) modal.close(); });
    head.append(title, close); modal.append(head);
    scope = node("p", "", "muted"); modal.append(scope);
    const selectors = node("div", "", "prompt-recipes-selectors");
    recipeSelect = node("select"); revisions = node("select"); components = node("select");
    selectors.append(label("Recette", recipeSelect), label("Révision", revisions), label("Consignes", components)); modal.append(selectors);
    extras = node("input"); extras.type = "checkbox";
    const extraLabel = node("label", "", "prompt-recipes-extra"); extraLabel.append(extras, document.createTextNode("Afficher aussi les règles conditionnelles")); modal.append(extraLabel);
    editor = node("textarea"); editor.rows = 17; editor.spellcheck = false; editor.setAttribute("aria-label", "Texte des consignes sélectionnées"); modal.append(editor);
    modal.append(node("small", "Les variables entre accolades sont remplies par l’application. Conservez-les. Le contexte et le schéma restent calculés.", "muted"));
    note = node("input"); note.maxLength = 200; note.placeholder = "Ex. caméra clarifiée"; modal.append(label("Note de version (facultative)", note));
    const actions = node("div", "", "prompt-recipes-actions");
    save = button("Enregistrer et appliquer"); save.className = "primary";
    activate = button("Appliquer cette version"); preview = button("Voir le prochain appel"); history = button("Échanges de cet atelier");
    actions.append(save, activate, preview, history); modal.append(actions);
    status = node("p"); status.setAttribute("role", "status"); modal.append(status);
    lifecycleNote = node("small", "", "muted"); modal.append(lifecycleNote);
    document.body.append(modal);
    modal.addEventListener("cancel", event => { if (busy || !discard()) event.preventDefault(); });
    modal.addEventListener("close", () => { ++token; });
    editor.addEventListener("input", () => { fields[component] = editor.value; dirty = true; message("Modifications non enregistrées."); controls(); });
    components.addEventListener("change", () => { component = components.value; editor.value = fields[component] || ""; controls(); });
    extras.addEventListener("change", fillComponents);
    recipeSelect.addEventListener("change", () => {
      if (!discard()) { recipeSelect.value = `${packageData.cookbook_id}@${packageData.version}`; return; }
      load().catch(error => message(error.message, true));
    });
    revisions.addEventListener("change", () => {
      if (!discard()) { revisions.value = String(packageData.revision); return; }
      load(Number(revisions.value)).catch(error => message(error.message, true));
    });
    save.addEventListener("click", () => mutate("save")); activate.addEventListener("click", () => mutate("activate"));
    preview.addEventListener("click", async () => {
      busy = true; controls();
      try {
        const stage = component === "plan.system" ? "beat_sheet" : "final_prompt";
        const data = await request(`/preview/${encodeURIComponent(context.sessionId)}/${stage}`);
        showText("Prochain appel · aperçu sans envoi", [
          ["Modèle et version réellement retenus", `${data.model} · révision ${data.context?.recipe_revision ?? "historique"} · ${data.image_count} image(s)`],
          ["Système assemblé", data.system_prompt], ["Message utilisateur, contexte et schéma", data.user_prompt],
        ]);
      } catch (error) { message(error.message, true); }
      finally { busy = false; controls(); }
    });
    history.addEventListener("click", () => showHistory(`/history/session/${encodeURIComponent(context.sessionId)}`));
  }
  function fillComponents() {
    const story = packageData?.cookbook_id === "story.brainrot";
    extras.parentElement.hidden = story; preview.hidden = story; history.hidden = story;
    note.placeholder = story ? "Ex. antagonistes plus excessifs" : "Ex. caméra clarifiée";
    const labels = story ? {"plan.system": "Proposer trois histoires", "writer.system": "Développer le scénario", "revision.system": "Discuter et réviser"} : mainFields;
    const keys = Object.keys(fields).filter(key => story ? labels[key] : mainFields[key] || extras.checked);
    components.replaceChildren(...keys.map(key => option(key, labels[key] || (key === "camera_contract" ? "Contrat caméra · correctif technique"
      : `${familyLabels[key.split(".")[0]] || key.split(".")[0]} · ${key.split(".").slice(1).join(" · ")}`))));
    if (!keys.includes(component)) component = "plan.system";
    components.value = component; editor.value = fields[component] || ""; controls();
  }
  function paint(data) {
    packageData = data.recipe; fields = {...packageData.fields}; dirty = false; note.value = "";
    revisions.replaceChildren(...data.history.map(item => option(String(item.revision),
      `r${item.revision}${item.revision === packageData.active ? " · active" : ""} · ${item.note}`)));
    revisions.value = String(packageData.revision);
    scope.textContent = `${recipeSelect.selectedOptions[0]?.textContent || ""} · active : r${packageData.active}. Les modifications concernent uniquement cette recette.`;
    lifecycleNote.textContent = packageData.cookbook_id === "story.brainrot"
      ? "Chaque nouvel échange utilise les consignes actives. Les scénarios et les échanges déjà enregistrés restent conservés."
      : "Les nouveaux cycles utilisent la révision active. Un Plan déjà commencé conserve ses consignes pour la Rédaction. Relancer une vidéo seule conserve son prompt déjà écrit.";
    fillComponents();
  }
  async function load(revision) {
    const mine = ++token; busy = true; dirty = false; packageData = null; controls(); message("Lecture des consignes…");
    try {
      const [key, version] = recipeSelect.value.split("@");
      const data = await request(`/recipe/${encodeURIComponent(key)}/${encodeURIComponent(version)}${revision ? `?revision=${revision}` : ""}`);
      if (mine !== token) return;
      paint(data); message(`Révision r${data.recipe.revision} chargée.`);
    } finally { if (mine === token) { busy = false; controls(); } }
  }
  async function mutate(action) {
    if (busy || !packageData) return;
    busy = true; controls(); message("Enregistrement…");
    try {
      const url = `/recipe/${encodeURIComponent(packageData.cookbook_id)}/${encodeURIComponent(packageData.version)}`;
      const payload = action === "save" ? {base_revision: packageData.revision, expected_active: packageData.active, fields, note: note.value}
        : {revision: packageData.revision, expected_active: packageData.active};
      const data = await request(url + (action === "save" ? "" : "/activate"), json(action === "save" ? "PUT" : "POST", payload));
      paint(data); message(`Révision r${data.recipe.active} active pour les prochains cycles de cette recette.`);
    } catch (error) { message(error.message, true); }
    finally { busy = false; controls(); }
  }
  async function open(options = {}) {
    mount(); if (modal.open && !discard()) return;
    context = options; if (!modal.open) modal.showModal();
    busy = true; controls(); message("Chargement des recettes…");
    try {
      const data = await request("");
      recipeSelect.replaceChildren(...data.recipes.map(recipe => option(`${recipe.id}@${recipe.version}`, `${recipe.label} · ${recipe.version}`)));
      const key = `${options.key}@${options.version}`;
      if ([...recipeSelect.options].some(item => item.value === key)) recipeSelect.value = key;
      component = "plan.system"; extras.checked = false; await load();
    } catch (error) { message(error.message, true); }
    finally { busy = false; controls(); }
  }
  function textSection(title, text) {
    const details = node("details"); details.append(node("summary", title));
    const pre = node("pre", text || "Aucun contenu enregistré."); details.append(pre); return details;
  }
  function viewer(title) {
    const dialog = node("dialog", "", "prompt-recipes-dialog prompt-recipes-viewer");
    dialog.setAttribute("aria-label", title);
    const head = node("div", "", "prompt-recipes-heading"); const close = button("Fermer");
    close.addEventListener("click", () => dialog.close()); head.append(node("h2", title), close); dialog.append(head);
    dialog.addEventListener("close", () => dialog.remove()); document.body.append(dialog); dialog.showModal(); return dialog;
  }
  function showText(title, sections) {
    const dialog = viewer(title); sections.forEach(([name, text]) => dialog.append(textSection(name, text)));
  }
  async function showHistory(url) {
    const dialog = viewer("Échanges LLM"); const status = node("p", "Chargement…"); dialog.append(status);
    try {
      const data = await request(url); if (!dialog.isConnected) return;
      status.textContent = data.scope;
      if (data.manual_prompt) dialog.append(node("p", "Le prompt de ce rendu a été modifié manuellement. Ces échanges retracent sa préparation, pas ces modifications manuelles."));
      if (data.historical) dialog.append(node("p", "Ancien rendu : les traces disponibles sont partielles. Les échanges disparus du journal ne peuvent pas être reconstruits."));
      if (!data.calls.length) dialog.append(node("p", "Aucun appel archivé associé. Une préparation bloquée avant l’appel LLM ne produit aucun échange envoyé."));
      for (const record of data.calls) {
        const call = record.call, context = record.context;
        const item = node("article", "", "prompt-trace-call");
        const stage = {beat_sheet: "Plan", final_prompt: "Rédaction", render_adjustment: "Ajustement après rendu",
          story_ideas: "Propositions d’histoires", story_develop: "Scénario", story_revise: "Discussion / révision"}[context.stage] || context.stage;
        item.append(node("h3", `${stage} · ${context.recipe_revision ? `r${context.recipe_revision}` : "recette historique"}`));
        if (!call) { item.append(node("p", "Appel démarré ; résultat pas encore archivé. Une interruption du service peut laisser cette trace incomplète.")); }
        else {
          item.append(node("p", `${call.actual_model_id || call.requested_model_id} · ${new Date(call.started_at).toLocaleString("fr-FR")} · ${call.application_outcome || call.status}`));
          if (call.application_error_message || call.error_message) item.append(node("p", call.application_error_message || call.error_message, "error-text"));
          item.append(textSection("Système envoyé", call.system_prompt), textSection("Message utilisateur, contexte et schéma", call.user_prompt),
            textSection("Réponse", call.response_text));
          if (call.reasoning_text) item.append(textSection("Raisonnement fourni par le modèle", call.reasoning_text));
          if (call.images?.length) item.append(textSection("Références envoyées", call.images.map(image => `${image.label} · ${image.media_type} · ${image.sha256}`).join("\n")));
        }
        dialog.append(item);
      }
    } catch (error) { if (dialog.isConnected) status.textContent = error.message; }
  }
  const globalButton = button("Recettes LLM"); globalButton.addEventListener("click", () => open());
  document.querySelector(".topbar-actions")?.append(globalButton);
  window.PanelForgePromptRecipes = {open, showHistory, historyButton(projectId, attemptId) {
    const el = button("Échanges LLM"); el.addEventListener("click", () => showHistory(`/history/render/${encodeURIComponent(projectId)}/${encodeURIComponent(attemptId)}`)); return el;
  }};
})();
