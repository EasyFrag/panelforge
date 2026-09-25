(() => {
  "use strict";
  const gridFormat = {width: 1080, height: 1440, aspect_ratio: "3:4"};
  const legacyFormat = {width: 1080, height: 1920, aspect_ratio: "9:16"};
  const formatLabel = format => `PNG ${format.width} × ${format.height} · ${format.aspect_ratio}`;
  const active = value => ["queued", "running"].includes(value?.status);
  const assetUrl = id => `/api/assets/${encodeURIComponent(id)}/content`;
  const node = (tag, text = "", cls = "") => {
    const item = document.createElement(tag); item.textContent = text; item.className = cls; return item;
  };
  const button = (text, action) => {
    const item = node("button", text); item.type = "button"; item.addEventListener("click", action); return item;
  };
  function create({request}) {
    let identity = "", value = null, busy = false, fetching = false, timer = null, lastFetch = 0, chain = null, requestEpoch = 0;
    const card = node("article", "", "episode-thumbnail-card");
    const title = node("h3", "Miniature de l’épisode"), status = node("p", "À préparer", "episode-thumbnail-status");
    status.setAttribute("role", "status");
    const cover = node("a", "", "episode-thumbnail-preview"); cover.target = "_blank"; cover.rel = "noopener";
    const image = node("img"); image.alt = "Miniature de l’épisode"; image.loading = "lazy"; cover.append(image);
    const empty = node("div", "", "episode-thumbnail-empty");
    empty.append(node("span", "ÉPISODE"), node("strong", "01"), node("small", "Un même modèle pour toute la série"));
    const note = node("p", "Modèle partagé · numéro automatique", "muted");
    const error = node("p", "", "episode-thumbnail-error"); error.setAttribute("role", "alert");
    const actions = node("div", "", "episode-thumbnail-actions");
    const prepare = button("Préparer la miniature", () => run({request_id: crypto.randomUUID(), expected_revision: value.revision}));
    const modify = button("Modifier le modèle", openEditor);
    const layoutEditor = PanelForgeThumbnailLayout.create({request, onSaved: next => { requestEpoch++; accept(next); }});
    const positionBadge = button("Déplacer le bandeau", () => layoutEditor.open(value));
    const download = node("a", "Télécharger le PNG", "episode-thumbnail-download");
    const refresh = button("Actualiser", () => fetchValue(true));
    actions.append(prepare, positionBadge, modify, download, refresh); card.append(title, status, cover, empty, note, error, actions);

    const dialog = document.getElementById("episode-thumbnail-dialog");
    const el = name => document.getElementById(`episode-thumbnail-${name}`);
    let editing = null, selectedTemplateId = null;
    el("close").addEventListener("click", () => dialog.close());
    el("source").addEventListener("change", sourceChanged);
    el("gallery-refresh").addEventListener("click", async () => {
      if (!editing || busy) return;
      const captured = identity; requestEpoch++; busy = true; el("gallery-refresh").disabled = true; el("submit").disabled = true; drawGallery(); draw();
      try {
        const next = await request(`/api/episodes/${encodeURIComponent(captured)}/thumbnail`);
        if (captured !== identity) return;
        accept(next); editing = structuredClone(value); sourceChanged();
      } catch (error) { if (captured === identity) el("editor-error").textContent = error.message; }
      finally { busy = false; el("gallery-refresh").disabled = false; el("submit").disabled = false; if (captured === identity) { drawGallery(); draw(); schedule(); } else fetchValue(); }
    });
    for (const name of ["gallery-filter", "gallery-sort", "gallery-search"]) el(name).addEventListener(name === "gallery-search" ? "input" : "change", drawGallery);
    el("gallery-search").addEventListener("keydown", event => { if (event.key === "Enter") event.preventDefault(); });
    el("title-style").addEventListener("change", updateTitleSample);
    el("title-mode").addEventListener("change", updateTitleSample);
    el("title").addEventListener("input", updateTitleSample);
    el("form").addEventListener("submit", event => { event.preventDefault(); saveEditor(); });

    function draw() {
      const labels = {missing: "À préparer", queued: "◷ Planifiée · attente du GPU", running: "● En cours · Qwen",
        ready: "✓ Prête", failed: "× Erreur · les scènes peuvent continuer"};
      status.textContent = value ? labels[value.status] || "À préparer" : "Chargement…";
      status.dataset.state = value?.status || "missing";
      cover.hidden = !value?.asset_id; empty.hidden = !!value?.asset_id;
      if (value?.asset_id) {
        if (image.dataset.assetId !== value.asset_id) { image.src = assetUrl(value.asset_id); image.dataset.assetId = value.asset_id; }
        cover.href = image.src;
        image.alt = `Miniature · épisode ${value.asset_number || value.number}`;
      }
      empty.querySelector("strong").textContent = String(value?.number || 1).padStart(2, "0");
      const displayedFormat = value?.asset_format || (value?.asset_id && value?.status !== "ready" ? legacyFormat : value?.output_format) || gridFormat;
      note.textContent = value ? `${value.title} · épisode ${value.number} · ${formatLabel(displayedFormat)}`
        : "Modèle partagé · numéro automatique";
      if (value?.asset_id && value.status !== "ready") note.textContent += " · ancienne miniature conservée ci-dessus";
      error.textContent = value?.error || chain?.thumbnail_error || ""; error.hidden = !error.textContent;
      prepare.hidden = !!value?.asset_id;
      prepare.textContent = value?.status === "failed" ? "Réessayer la miniature" : "Préparer la miniature";
      prepare.disabled = busy || !value || active(value); modify.disabled = busy || !value || active(value);
      positionBadge.hidden = value?.status !== "ready" || !value?.badge; positionBadge.disabled = busy;
      download.hidden = !value?.asset_id;
      download.href = `/api/episodes/${encodeURIComponent(identity)}/thumbnail/download`;
      refresh.hidden = !error.textContent; refresh.disabled = busy || fetching;
    }
    function accept(next) {
      if (next.episode_id !== identity || (value && value.revision > next.revision)) return;
      value = next; draw(); schedule();
    }
    function schedule() {
      clearTimeout(timer);
      if (card.closest("[hidden]")) return;
      if (active(value) || ["running", "pausing"].includes(chain?.status))
        timer = setTimeout(() => fetchValue(), 2000);
    }
    async function fetchValue(force = false) {
      if (!identity || fetching || busy || (!force && card.closest("[hidden]"))) return;
      const captured = identity, epoch = requestEpoch;
      fetching = true; lastFetch = Date.now();
      try { const next = await request(`/api/episodes/${encodeURIComponent(captured)}/thumbnail`); if (captured === identity && epoch === requestEpoch) accept(next); }
      catch (e) { if (captured === identity && epoch === requestEpoch) { error.textContent = e.message; error.hidden = false; refresh.hidden = false; } }
      finally { fetching = false; refresh.disabled = false; if (captured !== identity) fetchValue(); else schedule(); }
    }
    async function run(body, file = null) {
      if (busy) return;
      const captured = identity;
      requestEpoch++; busy = true; draw(); el("submit").disabled = true; el("editor-error").textContent = "";
      try {
        const options = file ? new FormData() : null;
        if (file) { options.append("options", JSON.stringify(body)); options.append("image", file); }
        const next = await request(`/api/episodes/${encodeURIComponent(captured)}/thumbnail${file ? "/import" : ""}`,
          file ? {method: "POST", body: options} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
        if (captured === identity) {
          accept(next);
          if (editing?.episode_id === captured) editing = structuredClone(next);
          if (next.status === "failed") el("editor-error").textContent = next.error;
          else dialog.close();
        }
      } catch (e) {
        if (captured === identity) { error.textContent = e.message; error.hidden = false; el("editor-error").textContent = e.message; }
      } finally {
        busy = false; el("submit").disabled = false;
        if (captured === identity) { draw(); schedule(); }
        else fetchValue();
      }
    }
    function openEditor() {
      if (!value || busy) return;
      editing = structuredClone(value);
      const select = el("source"); select.replaceChildren();
      const option = (id, label) => { const item = node("option", label); item.value = id; select.append(item); };
      if (value.series_template_id && value.templates.some(t => t.id === value.series_template_id && !t.archived_at)) option("series", "Modèle actuel de cette série");
      option("library", "Choisir un modèle dans la galerie");
      if (value.qwen_available) option("generate", "Nouveau modèle avec Qwen");
      option("upload", "Importer une image modèle");
      selectedTemplateId = value.series_template_id || null;
      select.value = value.series_template_id && value.templates.some(t => t.id === value.series_template_id && !t.archived_at)
        ? "series" : value.qwen_available ? "generate" : "upload";
      el("gallery-filter").value = "series"; el("gallery-sort").value = "recent"; el("gallery-search").value = "";
      el("number").value = value.number; el("title").value = value.title;
      el("direction").value = value.template?.direction || "";
      el("file").value = ""; el("editor-error").textContent = "";
      el("references").replaceChildren(...value.references.map(ref => {
        const card = node("article", "", "episode-thumbnail-reference"), label = node("label"), check = node("input"), img = node("img");
        check.type = "checkbox"; check.value = ref.id;
        check.checked = (value.template?.reference_ids || value.default_reference_ids).includes(ref.id);
        img.src = assetUrl(ref.asset_id); img.alt = ""; img.loading = "lazy";
        label.append(check, img, node("span", ref.name));
        const roleLabel = node("label", "Rôle dans l’affiche"), select = node("select"); select.dataset.referenceRole = ref.id;
        for (const [role, name] of [["foreground", "Premier plan"], ["background", "Arrière-plan"], ["environment", "Décor"], ["object", "Objet important"], ["style", "Style seulement"]]) {
          const option = node("option", name); option.value = role; select.append(option);
        }
        select.value = value.template?.reference_roles?.[ref.id]
          || value.template?.references?.find(r => r.id === ref.id)?.placement
          || ({location: "environment", object: "object"}[ref.kind] || "foreground");
        select.setAttribute("aria-label", `Rôle de ${ref.name}`);
        check.addEventListener("change", updateReferenceCount); select.addEventListener("change", updateReferenceCount);
        roleLabel.append(select); card.append(label, roleLabel); return card;
      }));
      updateReferenceCount();
      sourceChanged(); dialog.showModal();
    }
    function sourceChanged() {
      if (!editing) return;
      const source = el("source").value, generate = source === "generate", upload = source === "upload";
      const template = editing.templates.find(t => !t.archived_at && t.id === (source === "series" ? editing.series_template_id : source === "library" ? selectedTemplateId : null));
      el("gallery").hidden = generate || upload;
      drawGallery();
      el("generation").hidden = !generate; el("upload").hidden = !upload;
      el("title").disabled = !!template; el("title-mode").disabled = !!template; el("title-style").disabled = !!template;
      el("title-style").parentElement.hidden = !!template; el("title-sample").hidden = !!template;
      el("title").value = template?.title || editing.title;
      el("title-mode").value = template?.title_mode || "artwork";
      el("title-style").value = template?.title_style || editing.template?.title_style || "pop";
      el("artwork-option").textContent = upload ? "Conserver le titre présent dans l’image" : "Qwen · titre stylisé dans l’image";
      const format = template ? template.output_format || legacyFormat : gridFormat;
      el("format-note").textContent = `${formatLabel(format)}. Numéro en Outfit gras. Ce fichier reste séparé de la vidéo.`;
      el("template-preview").hidden = true;
      if (template) el("template-preview").src = assetUrl(template.asset_id);
      el("submit").textContent = generate ? "Créer le modèle et la miniature" : "Appliquer et préparer la miniature";
      el("editor-note").textContent = template
        ? "Le fond et le titre seront réutilisés à l’identique. Seul le numéro est ajouté, sans appel IA."
        : upload ? "Choisis un visuel vertical sans ancien numéro. Il sera centré au format 3:4 ; le numéro est ajouté avec une marge sous le bandeau."
        : "Le modèle est composé au format 3:4, avec des marges autour du titre et du numéro. Les rôles des images et l’habillage sont envoyés directement à Qwen, sans appel au LLM de rédaction. Les épisodes suivants réutilisent le modèle.";
      updateTitleSample();
      if (template) el("title-help").textContent = "Ce modèle conserve son habillage. Choisis Nouveau modèle avec Qwen pour modifier les personnages, leurs rôles ou le titre.";
    }
    function drawGallery() {
      if (!editing) return;
      const filter = el("gallery-filter").value, sort = el("gallery-sort").value;
      const search = el("gallery-search").value.trim().toLocaleLowerCase("fr");
      const selected = el("source").value === "series" ? editing.series_template_id : selectedTemplateId;
      const templates = editing.templates.filter(t => {
        if ((filter === "trash") !== !!t.archived_at) return false;
        if (["series", "unused"].includes(filter) && t.group_id !== editing.group_id) return false;
        if (filter === "unused" && !t.can_archive) return false;
        return !search || t.title.toLocaleLowerCase("fr").includes(search);
      }).sort((a, b) => {
        const current = Number(b.id === editing.series_template_id) - Number(a.id === editing.series_template_id);
        if (current) return current;
        if (sort === "title") return a.title.localeCompare(b.title, "fr");
        return (sort === "oldest" ? 1 : -1) * (a.created_at || "").localeCompare(b.created_at || "");
      });
      el("gallery-refresh").disabled = busy;
      el("gallery-count").textContent = `${templates.length} modèle${templates.length > 1 ? "s" : ""}${filter === "trash" ? " dans la corbeille" : ""}`;
      el("gallery-items").replaceChildren(...templates.map(template => {
        const item = node("article", "", "episode-thumbnail-model"); item.dataset.templateId = template.id;
        item.dataset.selected = String(template.id === selected && !template.archived_at);
        const choose = button("", () => {
          if (busy || template.archived_at) return;
          selectedTemplateId = template.id;
          el("source").value = template.id === editing.series_template_id ? "series" : "library";
          el("editor-error").textContent = ""; sourceChanged();
        });
        choose.className = "episode-thumbnail-model-choice"; choose.disabled = busy || !!template.archived_at;
        choose.setAttribute("aria-pressed", String(template.id === selected && !template.archived_at));
        choose.setAttribute("aria-label", `Choisir ${template.title}`);
        const img = node("img"); img.src = assetUrl(template.asset_id); img.alt = template.title; img.loading = "lazy";
        choose.append(img, node("strong", template.title));
        const status = template.archived_at ? "Dans la corbeille" : template.id === editing.series_template_id ? "✓ Actuel pour cette série"
          : template.episode_count ? `Utilisé par ${template.episode_count} épisode${template.episode_count > 1 ? "s" : ""}`
          : template.series_count ? "Retenu pour une série" : "Essai non retenu";
        const date = template.created_at ? new Date(template.created_at).toLocaleString("fr-FR", {dateStyle: "short", timeStyle: "short"}) : "";
        item.append(choose, node("span", status, "episode-thumbnail-model-state"), node("small", `${date} · ${template.output_format?.aspect_ratio || "9:16"}`, "muted"));
        const remove = button(template.archived_at ? "Restaurer" : "Mettre à la corbeille", () => archiveTemplate(template, !template.archived_at));
        remove.disabled = busy || (!template.archived_at && !template.can_archive);
        if (remove.disabled && !busy) remove.title = "Ce modèle est utilisé. Choisis d’abord un autre modèle pour les épisodes et séries concernés.";
        item.append(remove); return item;
      }));
      if (!templates.length) el("gallery-items").append(node("p", filter === "trash" ? "La corbeille est vide." : "Aucun modèle ici. Essaie Toutes les séries ou crée un nouveau modèle.", "muted"));
    }
    async function archiveTemplate(template, archived) {
      if (!editing || busy) return;
      const captured = identity; requestEpoch++; busy = true; el("submit").disabled = true; el("editor-error").textContent = ""; drawGallery(); draw();
      try {
        const next = await request(`/api/episodes/${encodeURIComponent(captured)}/thumbnail/templates/${encodeURIComponent(template.id)}/archive`, {
          method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({archived, expected_revision: template.revision || 0})});
        if (captured !== identity) return;
        accept(next); editing = structuredClone(next);
        if (archived && selectedTemplateId === template.id) { selectedTemplateId = editing.series_template_id || null; }
        sourceChanged();
      } catch (e) { if (captured === identity) el("editor-error").textContent = e.message; }
      finally {
        busy = false; el("submit").disabled = false;
        if (captured === identity) { drawGallery(); draw(); schedule(); } else fetchValue();
      }
    }
    function updateTitleSample() {
      const style = el("title-style").value, generated = el("title-mode").value === "artwork";
      el("title-sample").dataset.style = style; el("title-sample").textContent = el("title").value.trim() || "GLOW UP";
      el("title-help").textContent = generated
        ? "Direction typographique illustrative : Qwen interprète l’habillage. Pour une police et un placement exacts, choisis Police intégrée."
        : `Police intégrée : ${style === "cinema" ? "Barlow Condensed Black" : "Outfit Black"}. Titre et numéro éloignés des bords ; composition locale sans appel IA pour le texte.`;
    }
    function updateReferenceCount() {
      const cards = [...el("references").querySelectorAll(".episode-thumbnail-reference")];
      const selected = cards.filter(c => c.querySelector("input").checked), limit = editing?.max_references || 16;
      const count = role => selected.filter(c => c.querySelector("select").value === role).length;
      el("reference-count").textContent = `${selected.length} / ${limit} images · ${count("foreground")} au premier plan · ${count("background")} à l’arrière-plan`;
      for (const card of cards) {
        const check = card.querySelector("input"); check.disabled = !check.checked && selected.length >= limit;
        card.querySelector("select").disabled = !check.checked;
      }
    }
    async function saveEditor() {
      if (!editing || editing.episode_id !== identity || busy) return;
      if (!el("form").reportValidity()) return;
      const selected = el("source").value;
      if (selected === "library" && !editing.templates.some(t => t.id === selectedTemplateId && !t.archived_at)) {
        el("editor-error").textContent = "Choisis un modèle dans la galerie."; return;
      }
      const body = {request_id: crypto.randomUUID(), expected_revision: editing.revision, replace: true,
        source: ["series", "generate", "upload"].includes(selected) ? selected : "template",
        template_id: selected === "library" ? selectedTemplateId : null,
        title: el("title").value.trim(), number: Number(el("number").value), title_mode: el("title-mode").value, title_style: el("title-style").value,
        reference_ids: selected === "generate" ? [...el("references").querySelectorAll("input:checked")].map(n => n.value) : null,
        reference_roles: selected === "generate" ? Object.fromEntries([...el("references").querySelectorAll(".episode-thumbnail-reference")]
          .filter(n => n.querySelector("input").checked).map(n => [n.querySelector("input").value, n.querySelector("select").value])) : null,
        direction: selected === "generate" ? el("direction").value.trim() : ""};
      const file = selected === "upload" ? el("file").files[0] : null;
      if (selected === "upload" && !file) { el("editor-error").textContent = "Choisis une image à importer."; return; }
      await run(body, file);
    }
    return {
      mount(container, data) {
        if (card.parentNode !== container) container.prepend(card);
        chain = data.video_chain;
        if (identity !== data.episode_id) {
          identity = data.episode_id; requestEpoch++; value = null; editing = null; clearTimeout(timer); dialog.close(); layoutEditor.close(); lastFetch = 0;
          draw();
        }
        if (!fetching && !busy && Date.now() - lastFetch > 1500) fetchValue();
        schedule();
      },
      close() { clearTimeout(timer); dialog.close(); layoutEditor.close(); },
    };
  }
  window.PanelForgeEpisodeThumbnails = {create};
})();
