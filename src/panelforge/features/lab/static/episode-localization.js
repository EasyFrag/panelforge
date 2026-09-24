/* Dialogue-only language variants of a fabrication project. */
(() => {
  "use strict";
  const core = window.PanelForgeLabCore;
  const node = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; n.className = cls; return n; };
  const send = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const api = (id, path = "") => `/api/episodes/${encodeURIComponent(id)}${path}`;
  const statusText = {pending: "à préparer", ready: "prêt", queued: "planifié", created: "prêt à lancer", running: "en cours",
    succeeded: "terminé", failed: "erreur", interrupted: "à reprendre", cancelled: "annulé", cancel_pending: "annulation"};
  const stage = (label, status, reused = false) => {
    const tone = ["ready", "succeeded"].includes(status) ? "done" : ["failed", "interrupted"].includes(status) ? "failed"
      : status === "running" ? "running" : status === "queued" ? "planned" : "pending";
    return node("span", `${{done: "✓ ", failed: "X ", running: "● ", planned: "◷ ", pending: ""}[tone]}${label} : ${reused ? "réutilisé" : statusText[status] || "à préparer"}`, `episode-stage ${tone}`);
  };
  window.PanelForgeEpisodeLocalization = {mount(hooks) {
    const host = document.getElementById("episode-localization");
    if (!host || !core) return null;
    let catalog = null, identity = null, token = 0, timer = null, busy = false, reviewId = null, reviewRevision = null;
    const choices = new Map(), checked = new Set(), dirty = new Set();
    const message = node("p", "", "muted"); message.setAttribute("role", "status");
    const head = node("div", "", "story-panel");
    head.append(node("h2", "Une autre langue, la même mise en scène"), node("p", "Crée une copie indépendante à partir des essais choisis. Seules les répliques changent ; les images, le découpage et les réglages sont conservés. Les scènes muettes réutilisent leurs vidéos et leur DLSS."));
    const settings = node("div", "", "episode-bar"), language = node("select"), model = node("select");
    language.setAttribute("aria-label", "Langue cible"); model.setAttribute("aria-label", "Modèle de traduction");
    const langLabel = node("label", "Langue cible"), modelLabel = node("label", "LLM de traduction");
    langLabel.append(language); modelLabel.append(model); settings.append(langLabel, modelLabel); head.append(settings);
    head.append(node("p", "Un appel LLM par épisode. Les nouvelles vidéos parlées peuvent varier visuellement, même avec la même seed. Le texte visible dans les images reste inchangé.", "muted"));
    const sources = node("div", "", "localization-sources"), sourceDetails = node("details");
    sourceDetails.open = true; sourceDetails.append(node("summary", "Épisodes et essais sources"), sources);
    head.append(sourceDetails);
    const create = button("Créer la copie", () => perform(async () => {
      if (!checked.size) throw new Error("Sélectionne au moins un épisode source.");
      requireModel();
      const selections = catalog.sources.filter(s => checked.has(s.episode_id)).map(source => ({episode_id: source.episode_id,
        scenes: source.scenes.map(scene => {
          const c = choices.get(`${source.episode_id}:${scene.id}`);
          if (!c) throw new Error("Choisis un essai pour chaque scène.");
          return {scene_id: scene.id, preparation_id: c.preparation_id, project_id: c.project_id, attempt_id: c.attempt_id, token: c.token};
        })}));
      const result = await core.request(api(identity, "/localizations"), send("POST", {
        language: language.value, model_id: model.value, request_id: crypto.randomUUID(), selections}));
      await hooks.open(result.episode_ids[0], "localization");
    }));
    create.className = "primary"; head.append(create);
    const groups = node("div", "", "localization-groups"), review = node("section", "", "story-panel localization-review"); review.hidden = true;
    host.replaceChildren(head, message, groups, review);
    function button(text, action) { const b = node("button", text); b.type = "button"; b.addEventListener("click", action); return b; }
    function requireModel() {
      if (!(hooks.models() || []).some(m => m.id === model.value)) throw new Error("Choisis un modèle de traduction disponible.");
    }
    async function perform(work) {
      if (busy) return;
      busy = true; message.textContent = "Traitement de la demande…"; controls();
      try { await work(); message.textContent = "Enregistré. L’original est conservé."; }
      catch (error) { message.textContent = error.message; message.className = "error"; }
      finally { busy = false; controls(); schedule(); }
    }
    function controls() {
      create.disabled = busy || !checked.size;
      groups.querySelectorAll("button").forEach(b => { b.disabled = busy || b.dataset.blocked === "true"; });
      review.querySelectorAll("button").forEach(b => { b.disabled = busy || b.dataset.blocked === "true"; });
    }
    function populateModels() {
      const selected = model.value || hooks.current()?.localization?.model_id || catalog.default_model;
      model.replaceChildren(...(hooks.models() || []).map(m => new Option(m.name || m.display_name || m.id, m.id)));
      if (![...model.options].some(o => o.value === selected)) model.add(new Option(`${selected} · indisponible`, selected));
      model.value = selected;
    }
    function drawSources() {
      for (const id of checked) if (!catalog.sources.some(s => s.episode_id === id && s.available)) checked.delete(id);
      sources.replaceChildren(...catalog.sources.map(source => {
        const card = node("article", "", "localization-source"), label = node("label", "", "localization-choice");
        const check = node("input"); check.type = "checkbox"; check.disabled = !source.available;
        const key = source.series_episode_id || "single";
        if (source.episode_id === identity && source.available) checked.add(source.episode_id);
        check.checked = checked.has(source.episode_id);
        label.append(check, node("b", `${source.title} · version ${source.story_revision}`)); card.append(label);
        check.addEventListener("change", () => {
          if (check.checked) {
            for (const other of catalog.sources) if ((other.series_episode_id || "single") === key) checked.delete(other.episode_id);
            checked.add(source.episode_id);
          } else checked.delete(source.episode_id);
          sources.querySelectorAll("input[data-source]").forEach(c => { c.checked = checked.has(c.dataset.source); }); controls();
        });
        check.dataset.source = source.episode_id;
        const details = node("details"); details.open = check.checked;
        details.append(node("summary", source.available ? "Essais retenus · dernier résultat réussi par défaut" : "Prépare tous les prompts avant de copier cet épisode"));
        source.scenes.forEach(scene => {
          const row = node("div", "", "localization-source-row"), select = node("select");
          select.setAttribute("aria-label", `Essai source · ${scene.title}`);
          scene.choices.forEach((c, i) => select.add(new Option(`${c.label} · ${c.duration} s · ${c.dialogue_count ? `${c.dialogue_count} réplique(s)` : "muette"}`, String(i))));
          const choiceKey = `${source.episode_id}:${scene.id}`;
          const selectedIndex = Math.max(0, scene.choices.findIndex(c => c.token === choices.get(choiceKey)?.token));
          choices.set(choiceKey, scene.choices[selectedIndex]); select.value = String(selectedIndex);
          const preview = node("video"); preview.controls = true; preview.preload = "none"; preview.playsInline = true;
          const update = () => { const c = scene.choices[Number(select.value)]; choices.set(choiceKey, c);
            if (c?.output_asset_id) { preview.src = `/api/assets/${encodeURIComponent(c.output_asset_id)}/content`; preview.hidden = false; }
            else { preview.removeAttribute("src"); preview.hidden = true; } };
          select.addEventListener("change", update); update();
          row.append(node("span", scene.title), select, preview); details.append(row);
          if (scene.error) details.append(node("p", scene.error, "error"));
        });
        card.append(details);
        return card;
      }));
    }
    async function runGroup(group, mode) {
      if (dirty.size) throw new Error("Enregistre tes répliques modifiées avant de lancer la production.");
      if (group.episodes.some(e => !e.ready)) requireModel();
      await core.request(api(group.episodes[0].episode_id, "/localizations/start"), send("POST", {
        expected_revisions: Object.fromEntries(group.episodes.map(e => [e.episode_id, e.revision])),
        model_id: model.value, mode, request_id: crypto.randomUUID()}));
      await poll(); await hooks.refresh();
    }
    function drawGroups() {
      groups.replaceChildren(...catalog.groups.map(group => {
        const panel = node("section", "", "story-panel"), running = group.episodes.some(e => ["running", "pausing"].includes(e.chain_status) || ["queued", "running"].includes(e.job?.status)
          || e.scenes.some(s => ["queued", "running", "cancel_pending"].includes(s.video)));
        panel.append(node("h3", `Copie ${group.label}`));
        const actions = node("div", "", "story-actions");
        for (const [text, mode] of [["Traduire pour relire", "translate"], ["Tout lancer", "all"], ["Produire vidéos + DLSS", "produce"]]) {
          const b = button(text, () => perform(() => runGroup(group, mode)));
          b.dataset.blocked = String(running || (mode === "produce" && group.episodes.some(e => !e.ready)));
          if (mode === "all") b.className = "primary";
          actions.append(b);
        }
        panel.append(actions);
        group.episodes.forEach(episode => {
          const row = node("article", "", "localization-episode"), bar = node("div", "", "episode-bar");
          bar.append(node("b", episode.title), button("Relire les dialogues", () => perform(() => loadReview(episode.episode_id))),
            button("Ouvrir les scènes", () => perform(async () => { guardDirty(); await hooks.open(episode.episode_id, "scenes"); })));
          row.append(bar);
          if (episode.job) row.append(node("p", episode.job.error || episode.job.phase, episode.job.error ? "error" : "muted"));
          episode.scenes.forEach(scene => {
            const stages = node("div", "", "localization-progress"), translation = scene.translation === "ready" ? "ready"
              : ["queued", "running", "failed", "interrupted"].includes(episode.job?.status) ? episode.job.status : "pending";
            stages.append(node("span", scene.title), stage(scene.silent ? "Prompt conservé" : "Traduction / injection", translation),
              stage("Vidéo", scene.video, scene.reused), stage("DLSS", scene.dlss?.status, scene.dlss?.reused)); row.append(stages);
            if (scene.dlss?.error) row.append(node("p", scene.dlss.error, "error"));
          }); panel.append(row);
        }); return panel;
      })); controls();
    }
    function guardDirty() { if (dirty.size) throw new Error("Enregistre ou annule les répliques modifiées avant de quitter cette relecture."); }
    async function loadReview(id, polling = false) {
      if (!polling) guardDirty();
      const own = token;
      const data = await core.request(api(id));
      if (own !== token || identity !== hooks.current()?.episode_id) return;
      if (polling && (dirty.size || (id === reviewId && data.localization.revision === reviewRevision))) return;
      reviewId = id; reviewRevision = data.localization.revision;
      const info = data.localization, working = ["queued", "running"].includes(info.job?.status);
      review.hidden = false; review.replaceChildren(node("h3", `Dialogues · ${data.title}`));
      review.append(button("Annuler mes modifications non enregistrées", () => perform(async () => {
        dirty.clear(); reviewRevision = null; await loadReview(id, true);
      })));
      review.append(node("p", "Enregistrer injecte les répliques sans appel LLM. Seule la scène modifiée devra être régénérée ; ses anciens essais restent consultables.", "muted"));
      data.scenes.forEach(scene => {
        const sc = scene.localization, section = node("section", "", "localization-lines"); section.append(node("h4", scene.title));
        if (!sc.slots.length) { section.append(node("p", "Scène muette · aucune traduction nécessaire.", "muted")); review.append(section); return; }
        const edits = [], table = node("div", "", "localization-dialogues");
        table.append(node("b", "Original"), node("b", `Traduction · ${catalog.languages[info.language]}`));
        sc.slots.forEach((slot, index) => {
          const original = node("blockquote", slot.text), input = node("textarea"); input.rows = 3; input.maxLength = 4000;
          input.value = sc.translations[slot.id] || ""; input.disabled = working;
          input.setAttribute("aria-label", `${scene.title} · traduction ${index + 1}`);
          input.addEventListener("input", () => { dirty.add(scene.id); message.textContent = "Répliques modifiées · à enregistrer"; });
          edits.push({slot, input}); table.append(original, input);
        });
        section.append(table);
        if (sc.warning) section.append(node("p", sc.warning, "muted"));
        const save = button("Enregistrer ces répliques", () => perform(async () => {
          const result = await core.request(api(id, `/scenes/${encodeURIComponent(scene.id)}/localized-dialogues`), send("PUT", {
            expected_revision: reviewRevision, lines: edits.map(({slot, input}) => ({id: slot.id, text: input.value}))}));
          dirty.delete(scene.id); reviewRevision = result.localization.revision;
          if (!dirty.size) { reviewRevision = null; await loadReview(id, true); }
          await poll(); await hooks.refresh();
        })); save.dataset.blocked = String(working); section.append(save); review.append(section);
      }); controls();
      if (!polling) review.scrollIntoView({behavior: "smooth", block: "start"});
    }
    async function poll() {
      const own = token, id = identity;
      const next = await core.request(api(id, "/localizations?include_sources=false"));
      if (own !== token || id !== identity) return;
      catalog = {...next, sources: catalog.sources}; drawGroups();
      if (reviewId) await loadReview(reviewId, true);
    }
    function schedule() {
      clearTimeout(timer);
      if (!identity || host.hidden || !hooks.visible()) return;
      timer = setTimeout(async () => {
        try { if (!busy && !host.hidden && hooks.visible()) await poll(); }
        catch (error) { message.textContent = error.message; }
        finally { schedule(); }
      }, 2500);
    }
    return {
      guardDirty,
      async open() {
        const id = hooks.current()?.episode_id; if (!id) return;
        if (id !== identity) { guardDirty(); identity = id; ++token; reviewId = reviewRevision = null; review.hidden = true; checked.clear(); choices.clear(); }
        const own = token; catalog = await core.request(api(id, "/localizations")); if (own !== token) return;
        const selected = language.value || "English";
        language.replaceChildren(...Object.entries(catalog.languages).map(([value, label]) => new Option(label, value))); language.value = selected;
        populateModels(); drawSources(); drawGroups(); message.className = "muted"; message.textContent = "";
        if (hooks.current()?.localization && !reviewId) await loadReview(id, true);
        schedule();
      },
      close() { clearTimeout(timer); },
    };
  }};
})();
