(() => {
  "use strict";
  const core = window.PanelForgeLabCore, stories = window.PanelForgeStories;
  const dialog = document.getElementById("story-library"), trigger = document.getElementById("story-library-open");
  if (!core || !stories || !dialog || !trigger) return;
  const el = id => document.getElementById(`sl-${id}`);
  const state = {data: null, busy: false, loading: false, request: 0, timer: null, editor: null, undo: null, expanded: new Map(), languages: new Map()};
  const sortStorageKey = "panelforge.storyLibrary.sort";
  try {
    const saved = localStorage.getItem(sortStorageKey);
    if ([...el("sort").options].some(option => option.value === saved)) el("sort").value = saved;
  } catch (_) { /* Sorting remains available when browser storage is disabled. */ }
  const names = {French: "Français", English: "English", Korean: "Coréen", Japanese: "Japonais", Russian: "Russe"};
  const statuses = {done: ["✓", "Terminé"], running: ["●", "En cours"], planned: ["◷", "Planifié"],
    error: ["✕", "Erreur"], attention: ["!", "À examiner"], approval: ["!", "À valider"], pending: ["○", "À préparer"]};
  const node = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; n.className = cls; return n; };
  const button = (text, title, action, key) => {
    const b = node("button", text); b.type = "button"; b.title = title; b.setAttribute("aria-label", title); b.disabled = state.busy;
    if (key) b.dataset.focusKey = key;
    b.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); action(); }); return b;
  };
  const fold = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
  const notice = (text, error = false) => { el("status").textContent = text; el("status").classList.toggle("error", error); };
  function variant(item) { return item.variants.find(v => v.language === state.languages.get(item.project_id)) || item.variants[0]; }
  function stageView(item) {
    const stages = {...item.stages}, value = variant(item), c = value?.counts;
    if (c && value !== item.variants[0]) {
      stages.references = c.complete_units && c.reference_total && c.references === c.reference_total ? "done" : "pending";
      stages.videos = c.complete_units && c.scenes && c.videos === c.scenes ? "done" : c.errors ? "error" : c.stale ? "attention" : c.active ? "running" : c.queued ? "planned" : "pending";
    }
    return stages;
  }
  function matches(item, group, query, filter) {
    if (!!item.trashed !== (filter === "trash")) return false;
    if (filter === "favorites" && !group.favorite) return false;
    const complete = Object.values(stageView(item)).every(s => s === "done");
    if (filter === "completed" && !complete) return false;
    if (filter === "active" && complete && !item.active) return false;
    return !query || fold(`${group.title} ${item.title} épisode ${item.episode_number}`).includes(query);
  }
  function itemCard(item, group) {
    const card = node("article", "", "sl-item"), head = node("div", "", "sl-item-head"), title = node("div");
    const last = item.episode_number + item.episode_count - 1;
    const number = item.episode_count > 1 ? `Épisodes ${item.episode_number}–${last}` : `Ép. ${String(item.episode_number).padStart(2, "0")}`;
    const parallel = group.items.some(other => other.project_id !== item.project_id && !other.trashed && other.episode_number === item.episode_number);
    title.append(node("small", number + (parallel ? " · Variante" : "")), node("h3", item.title)); head.append(title);
    if (stories.current()?.project_id === item.project_id) head.append(node("span", "Ouverte", "sl-badge"));
    if (item.active && !item.progress_error) head.append(node("span", "● Traitement actif", "sl-badge sl-active"));
    const actions = node("div", "", "sl-actions");
    if (item.trashed) actions.append(button("Restaurer", `Restaurer ${item.title}`, () => archive(item, false), `restore:${item.project_id}`));
    else {
      actions.append(button("⋯", `Organiser ${item.title}`, () => editProject(item, group), `organize:${item.project_id}`));
      const remove = button("×", `Mettre ${item.title} à la corbeille`, () => archive(item, true), `trash:${item.project_id}`);
      remove.disabled ||= item.active;
      if (item.active) remove.title = item.progress_error ? "L’activité doit être vérifiée avant le retrait." : "Attends la fin du traitement ou mets-le en pause.";
      actions.append(remove);
    }
    head.append(actions); card.append(head);
    const progress = node("ol", "", "sl-stages"), stages = stageView(item);
    for (const [key, label] of [["intention", "Intention"], ["story", "Histoire"], ["scenario", "Scénario"], ["references", "Références"], ["videos", "Vidéos"]]) {
      const value = stages[key] || "pending", [symbol, text] = statuses[value] || statuses.pending;
      const li = node("li", `${symbol} ${label}`); li.dataset.state = value; li.title = `${label} : ${text}`; li.setAttribute("aria-label", li.title); progress.append(li);
    }
    card.append(progress);
    const current = variant(item), counts = current?.counts;
    if (item.variants.length > 1) {
      const label = node("label", "Avancement par langue", "sl-language"), select = document.createElement("select");
      select.replaceChildren(...item.variants.map(v => new Option(names[v.language] || v.language, v.language)));
      select.value = current.language; select.disabled = state.busy; select.dataset.focusKey = `language:${item.project_id}`;
      select.addEventListener("change", () => { state.languages.set(item.project_id, select.value); paint(); }); label.append(select); card.append(label);
    } else if (current) card.append(node("small", names[current.language] || current.language, "muted"));
    if (counts) {
      card.append(node("p", `Références ${counts.reference_total ? `${counts.references}/${counts.reference_total}` : "—"} · Prompts ${counts.scenes ? `${counts.prompts}/${counts.scenes}` : "—"} · Vidéos ${counts.scenes ? `${counts.videos}/${counts.scenes}` : "—"} · DLSS ${counts.scenes ? `${counts.dlss}/${counts.scenes}` : "—"}`, "sl-counts"));
      if (counts.stale) card.append(node("p", `${counts.stale} scène(s) à actualiser.`, "sl-warning"));
      if (counts.errors) card.append(node("p", `${counts.errors} incident(s) dans la fabrication suivie.`, "error"));
      if (!counts.complete_units && current.fabrication_ids.length) card.append(node("p", "Certaines séquences n’ont pas encore de fabrication dans cette langue.", "muted"));
    }
    if (item.progress_error) card.append(node("p", item.progress_error, "sl-warning"));
    if (!item.trashed) {
      const footer = node("div", "", "sl-actions");
      const canProduce = current?.fabrication_ids.length && ["intention", "story", "scenario"].every(key => stages[key] === "done");
      const primary = button(canProduce ? "Ouvrir la fabrication" : "Ouvrir l’histoire", `Ouvrir ${item.title}`, () => openItem(item, canProduce ? current.fabrication_ids : null), `open:${item.project_id}`);
      primary.classList.add("primary"); footer.append(primary);
      if (canProduce) footer.append(button("Écriture", `Relire l’écriture de ${item.title}`, () => openItem(item), `write:${item.project_id}`));
      card.append(footer);
    }
    return card;
  }
  const activity = item => Date.parse(item.last_activity_at || item.updated_at) || 0;
  const groupActivity = items => Math.max(0, ...items.map(activity));
  function sortedGroups(query, filter) {
    const groups = state.data.groups.map(group => ({group, items: group.items.filter(item => matches(item, group, query, filter))})).filter(row => row.items.length);
    const order = el("sort").value;
    return groups.sort((a, b) => {
      const title = a.group.title.localeCompare(b.group.title, "fr", {sensitivity: "base", numeric: true}) || a.group.id.localeCompare(b.group.id);
      const recent = groupActivity(b.items) - groupActivity(a.items);
      if (order === "title") return title;
      if (order === "oldest") return -recent || title;
      if (order === "favorites") return Number(b.group.favorite) - Number(a.group.favorite) || recent || title;
      return recent || title;
    });
  }
  function groupInfo(items) {
    const lines = [`${items.length} ${items.length > 1 ? "entrées" : "entrée"}`];
    const counts = items.map(item => variant(item)?.counts).filter(Boolean);
    const scenes = counts.reduce((total, count) => total + count.scenes, 0);
    if (scenes) lines.push(`${counts.reduce((total, count) => total + count.videos, 0)}/${scenes} vidéos prêtes`);
    if (items.some(item => item.active && !item.progress_error)) lines.push("● Traitement actif");
    if (items.some(item => item.progress_error)) lines.push("Avancement partiel");
    const info = node("div", "", "sl-group-info");
    info.append(node("small", lines.join(" · ")));
    const date = groupActivity(items);
    if (date) {
      const time = node("time", `Dernière activité : ${new Intl.DateTimeFormat("fr-FR", {dateStyle: "short", timeStyle: "short"}).format(date)}`);
      time.dateTime = new Date(date).toISOString(); info.append(time);
    }
    return info;
  }
  function groupPortraits(items) {
    const strip = node("div", "", "sl-portraits"), seenNames = new Set(), seenAssets = new Set();
    strip.setAttribute("role", "group"); strip.setAttribute("aria-label", "Personnages de l’histoire");
    for (const item of [...items].sort((a, b) => activity(b) - activity(a))) {
      for (const character of variant(item)?.characters || []) {
        const name = fold(character.name).trim();
        if (!character.asset_id || seenNames.has(name) || seenAssets.has(character.asset_id)) continue;
        seenNames.add(name); seenAssets.add(character.asset_id);
        const figure = node("figure", "", "sl-portrait"), image = document.createElement("img");
        image.src = `/api/assets/${encodeURIComponent(character.asset_id)}/content`;
        image.alt = character.name; image.loading = "lazy"; image.decoding = "async"; image.width = 64; image.height = 76;
        figure.title = character.name;
        image.addEventListener("error", () => { image.hidden = true; figure.classList.add("sl-portrait-missing"); figure.title = `${character.name} — aperçu indisponible`; }, {once: true});
        figure.append(image, node("figcaption", character.name)); strip.append(figure);
        if (strip.children.length === 3) return strip;
      }
    }
    if (!strip.children.length) strip.append(node("small", "Personnages à préparer", "muted"));
    return strip;
  }
  function paint() {
    if (!state.data) return;
    const focus = document.activeElement?.dataset.focusKey, scroll = el("list").scrollTop;
    const query = fold(el("search").value.trim()), filter = el("filter").value;
    el("trash-help").hidden = filter !== "trash";
    const contents = [];
    for (const {group, items} of sortedGroups(query, filter)) {
      const details = node("details", "", "sl-group"), summary = node("summary"), heading = node("div", "", "sl-group-title");
      const star = button(group.favorite ? "★" : "☆", group.favorite ? `Retirer ${group.title} des favoris` : `Ajouter ${group.title} aux favoris`,
        () => update("groups", group.id, {favorite: !group.favorite}), `favorite:${group.id}`);
      star.classList.add("sl-star"); star.setAttribute("aria-pressed", String(group.favorite));
      const text = node("div", "", "sl-group-text");
      text.append(node("strong", group.title), groupInfo(items));
      heading.append(star, text);
      summary.append(heading, groupPortraits(items), button("Renommer", `Renommer la série ${group.title}`, () => editGroup(group), `rename:${group.id}`));
      details.append(summary, ...items.map(item => itemCard(item, group)));
      details.open = !!query || (state.expanded.get(group.id) ?? (group.favorite || group.items.some(item => item.project_id === stories.current()?.project_id) || contents.length === 0));
      details.addEventListener("toggle", () => { if (details.isConnected && !query) state.expanded.set(group.id, details.open); }); contents.push(details);
    }
    el("list").replaceChildren(...contents); el("empty").hidden = contents.length > 0;
    el("list").scrollTop = scroll;
    if (focus) [...el("list").querySelectorAll("[data-focus-key]")].find(n => n.dataset.focusKey === focus)?.focus({preventScroll: true});
    for (const id of ["refresh", "undo", "save", "editor-cancel", "new"]) el(id).disabled = state.busy;
  }
  function schedule() {
    clearTimeout(state.timer);
    if (dialog.open && !state.editor && state.data?.groups.some(g => g.items.some(i => i.active && !i.progress_error))) {
      state.timer = setTimeout(() => load(false), 8000);
    }
  }
  async function load(announce = true) {
    if (state.busy || state.editor) return;
    const token = ++state.request; state.loading = true; el("refresh").disabled = true;
    if (announce) notice("Lecture de la bibliothèque…");
    try {
      const data = await core.request("/api/stories/library"); if (token !== state.request) return;
      state.data = data; document.getElementById("story-projects").hidden = true; paint();
      if (announce || data.unreadable) notice(data.unreadable ? `${data.unreadable} document(s) illisible(s) n’ont pas pu être chargés. Les autres histoires restent disponibles.` : "");
    } catch (error) {
      if (token === state.request) {
        const unavailable = /Not Found|HTTP 404/i.test(error.message);
        notice(unavailable ? "Le backend de la bibliothèque n’est pas encore chargé. À la fin des traitements, redémarre le Lab puis actualise la page. La liste habituelle reste disponible." : error.message, true);
        if (!state.data) document.getElementById("story-projects").hidden = false;
      }
    }
    finally { if (token === state.request) { state.loading = false; el("refresh").disabled = state.busy; schedule(); } }
  }
  async function update(collection, id, values) {
    if (state.busy || !state.data) return false;
    ++state.request; state.busy = true; clearTimeout(state.timer); paint();
    try {
      state.data = await core.request(`/api/stories/library/${collection}/${encodeURIComponent(id)}`, {method: "PATCH", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({expected_revision: state.data.revision, ...values})});
      notice("Bibliothèque enregistrée."); await stories.refreshList(); return true;
    } catch (error) {
      notice(error.message, true);
      try { state.data = await core.request("/api/stories/library"); } catch (_) { /* Keep the last visible library; never retry a mutation implicitly. */ }
      return false;
    } finally { state.busy = false; state.loading = false; paint(); schedule(); }
  }
  async function archive(item, trashed) {
    if (stories.current()?.project_id === item.project_id) {
      try { await window.PanelForgeEpisodes?.prepareLibraryNavigation(); } catch (error) { notice(error.message, true); return; }
    }
    if (!await update("projects", item.project_id, {trashed})) return;
    state.undo = {project_id: item.project_id, trashed: !trashed};
    el("undo-text").textContent = `${item.title} ${trashed ? "a été placé dans la corbeille." : "a été restauré."}`; el("undo-bar").hidden = false;
    if (trashed && stories.current()?.project_id === item.project_id) stories.createNew();
  }
  async function openItem(item, fabrications = null) {
    if (state.busy) return;
    if (!stories.canSwitch()) { notice("Attends la fin de l’enregistrement en cours.", true); return; }
    state.busy = true; clearTimeout(state.timer); paint();
    try {
      await window.PanelForgeEpisodes?.prepareLibraryNavigation();
      await stories.open(item.project_id);
      if (stories.current()?.project_id !== item.project_id) throw new Error("L’histoire n’a pas pu être ouverte.");
      if (fabrications?.length && window.PanelForgeEpisodes) await window.PanelForgeEpisodes.openFromLibrary(item.project_id, fabrications[0]);
      dialog.close();
    } catch (error) { notice(error.message, true); }
    finally { state.busy = false; paint(); schedule(); }
  }
  function editGroup(group) {
    state.editor = {kind: "groups", id: group.id}; clearTimeout(state.timer);
    el("editor-title").textContent = "Renommer la série"; el("title").value = group.title;
    el("title-row").hidden = false; el("group-row").hidden = el("number-row").hidden = true;
    el("editor-help").textContent = "Le titre commun change dans la bibliothèque. Les titres d’épisode et les scénarios sont conservés.";
    el("editor").hidden = false; el("title").focus();
  }
  function editProject(item, group) {
    state.editor = {kind: "projects", id: item.project_id}; clearTimeout(state.timer);
    el("editor-title").textContent = `Organiser · ${item.title}`; el("title-row").hidden = true; el("group-row").hidden = el("number-row").hidden = false;
    el("group").replaceChildren(...state.data.groups.map(g => new Option(g.title, g.id)));
    if (!state.data.groups.some(g => g.id === item.project_id)) el("group").add(new Option(`Série indépendante · ${item.title}`, item.project_id));
    el("group").value = group.id; el("number").value = item.episode_number;
    el("editor-help").textContent = "Ce rangement concerne cette entrée. Ses suites conservent leur série et leur numéro. Un numéro déjà utilisé permet de conserver une autre version du même épisode.";
    el("editor").hidden = false; el("group").focus();
  }
  function closeEditor() { state.editor = null; el("editor").hidden = true; schedule(); }
  el("editor").addEventListener("submit", async event => {
    event.preventDefault(); const edit = state.editor; if (!edit) return;
    const values = edit.kind === "groups" ? {title: el("title").value.trim()} : {group_id: el("group").value, episode_number: Number(el("number").value)};
    if (await update(edit.kind, edit.id, values)) closeEditor();
  });
  el("group").addEventListener("change", () => {
    const items = state.data.groups.find(g => g.id === el("group").value)?.items || [];
    el("number").value = Math.max(0, ...items.filter(i => i.project_id !== state.editor.id).map(i => i.episode_number + i.episode_count - 1)) + 1;
  });
  el("editor-cancel").addEventListener("click", closeEditor);
  el("search").addEventListener("input", paint); el("filter").addEventListener("change", paint);
  el("sort").addEventListener("change", () => {
    try { localStorage.setItem(sortStorageKey, el("sort").value); } catch (_) { /* Optional preference only. */ }
    paint();
  });
  el("refresh").addEventListener("click", () => load());
  el("undo").addEventListener("click", async () => { const value = state.undo; if (value && await update("projects", value.project_id, {trashed: value.trashed})) { state.undo = null; el("undo-bar").hidden = true; } });
  el("close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { clearTimeout(state.timer); closeEditor(); trigger.focus(); });
  el("new").addEventListener("click", async () => {
    if (!stories.canSwitch()) return;
    try { await window.PanelForgeEpisodes?.prepareLibraryNavigation(); stories.createNew(); dialog.close(); }
    catch (error) { notice(error.message, true); }
  });
  trigger.hidden = false; document.getElementById("story-projects").hidden = true;
  document.getElementById("story-library-label").htmlFor = "story-library-open";
  trigger.addEventListener("click", () => { dialog.showModal(); load(); });
  const caption = () => { trigger.textContent = stories.current()?.title ? `${stories.current().title} ▾` : "Parcourir mes histoires ▾"; };
  window.addEventListener("panelforge:story", caption); caption();
})();
