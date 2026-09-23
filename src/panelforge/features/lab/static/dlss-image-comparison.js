(() => {
  "use strict";
  const imageOwner = owner => ["assisted", "edit", "qwen"].includes(owner);
  const settingLabels = { intensity: "NR", tone: "Tonalité", structure: "Structure", skin: "Peau", detail: "Détails", style: "Style" };
  const describe = settings => Object.entries(settingLabels).map(([key, label]) => `${label} ${settings[key]}`).join(" · ");
  const scopeOf = value => `${value.owner}:${value.ownerId}:${value.attempt.dlss?.root_attempt_id || value.attempt.attempt_id}`;
  const scopeOfJob = job => `${job.snapshot?.owner}:${job.snapshot?.owner_id}:${job.snapshot?.root_attempt_id}`;

  function setup({ dialog, onSelect }) {
    let context = null, presets = [], selected = null, jobs = [], comparing = null;
    const buttons = new Map();
    const section = document.createElement("section");
    section.dataset.image = ""; section.className = "dlss-image-presets";
    section.innerHTML = `<label>Traitement de l’image<select data-image-mode>
      <option value="single">Upscale unique</option><option value="compare">Comparer des préréglages</option>
      </select></label><div data-preset-panel hidden><p class="muted">Même source et même taille pour toutes les variantes. Chaque profil modifie un seul réglage ; les autres restent ceux des réglages avancés.</p>
      <div data-preset-list></div><p data-preset-note class="muted" aria-live="polite"></p></div>`;
    dialog.querySelector("[data-size-note]").after(section);
    const mode = section.querySelector("select"), panel = section.querySelector("[data-preset-panel]");
    const list = section.querySelector("[data-preset-list]"), note = section.querySelector("[data-preset-note]");
    const isBatch = () => imageOwner(context?.owner) && mode.value === "compare";
    function paintPresets() {
      panel.hidden = !isBatch(); list.replaceChildren();
      for (const preset of presets) {
        const label = document.createElement("label"), check = document.createElement("input"), text = document.createElement("span");
        label.className = "dlss-preset-option"; check.type = "checkbox"; check.dataset.presetId = preset.preset_id;
        check.checked = selected.has(preset.preset_id) && preset.available; check.disabled = !preset.available;
        const title = document.createElement("strong"), detail = document.createElement("small");
        title.textContent = preset.label; detail.textContent = preset.available ? describe(preset.settings) : "Identique aux réglages actuels à cette limite — non proposé.";
        text.append(title, detail); label.append(check, text); list.append(label);
        check.addEventListener("input", () => {
          if (check.checked) selected.add(preset.preset_id); else selected.delete(preset.preset_id);
          updateCount();
        });
      }
      updateCount();
    }
    const ids = () => presets.filter(p => p.available && selected?.has(p.preset_id)).map(p => p.preset_id);
    function updateCount() {
      note.textContent = presets.length ? `${ids().length} variante(s) sélectionnée(s). Traitement en arrière-plan ; tu peux continuer à travailler.` : "Chargement des préréglages…";
      const start = dialog.querySelector("[data-start]");
      start.textContent = isBatch() ? `Lancer les ${ids().length} variantes` : "Lancer l’upscale";
    }
    mode.addEventListener("input", paintPresets);

    const compare = document.createElement("dialog"); compare.className = "dlss-image-compare";
    compare.innerHTML = `<div class="dlss-head"><h2>Comparer les images DLSS</h2><button type="button" data-close aria-label="Fermer le comparateur">×</button></div>
      <p data-comparison-state aria-live="polite"></p><div class="dlss-compare-toolbar">
      <label>Zoom commun <input data-zoom type="range" min="0.05" max="8" step="0.05" value="1"></label>
      <button type="button" data-fit>Vue entière</button><button type="button" data-native>100 % des pixels</button></div>
      <p class="muted">Déplace l’image dans un panneau : l’autre suit la même zone. Tu peux changer de variante en conservant le cadrage.</p>
      <div class="dlss-compare-panes"></div><p data-compare-error role="alert" class="error-text"></p>`;
    document.body.append(compare);
    const panes = [], zoom = compare.querySelector("[data-zoom]"), state = compare.querySelector("[data-comparison-state]");
    let choices = [], zoomFactor = 1, center = { x: 0.5, y: 0.5 }, syncing = false, syncFrame = null;
    let referenceWidth = 1, referenceHeight = 1;
    for (let i = 0; i < 2; i++) {
      const pane = document.createElement("section"); pane.className = "dlss-compare-pane";
      const select = document.createElement("select"); select.setAttribute("aria-label", `Image ${i ? "droite" : "gauche"}`);
      const details = document.createElement("details"), summary = document.createElement("summary"), params = document.createElement("p");
      summary.textContent = "Réglages de cette variante"; details.append(summary, params);
      const view = document.createElement("div"); view.className = "dlss-compare-viewport"; view.tabIndex = 0;
      view.setAttribute("aria-label", `Zone d’image ${i ? "droite" : "gauche"}, défilement synchronisé`);
      const img = document.createElement("img"); img.draggable = false; view.append(img);
      const use = document.createElement("button"); use.type = "button"; use.textContent = "Afficher cette variante dans l’atelier";
      pane.append(select, details, view, use); compare.querySelector(".dlss-compare-panes").append(pane);
      const item = { select, params, view, img, use }; panes.push(item);
      select.addEventListener("change", () => setImage(item));
      use.addEventListener("click", () => {
        const choice = choices.find(c => c.id === select.value);
        if (choice?.job) { onSelect(choice.job); compare.close(); }
      });
      img.addEventListener("load", layout);
      img.addEventListener("error", () => { compare.querySelector("[data-compare-error]").textContent = "Une image n’est plus accessible. Vérifie son fichier de sortie DLSS."; });
      view.addEventListener("scroll", () => {
        if (syncing) return;
        center = { x: img.width <= view.clientWidth ? 0.5 : (view.scrollLeft + view.clientWidth / 2) / img.width,
          y: img.height <= view.clientHeight ? 0.5 : (view.scrollTop + view.clientHeight / 2) / img.height };
        syncView();
      });
      let drag = null;
      view.addEventListener("pointerdown", event => {
        if (event.pointerType !== "mouse" || event.button !== 0) return;
        drag = { x: event.clientX, y: event.clientY, left: view.scrollLeft, top: view.scrollTop };
        view.setPointerCapture(event.pointerId); event.preventDefault();
      });
      view.addEventListener("pointermove", event => {
        if (drag) { view.scrollLeft = drag.left + drag.x - event.clientX; view.scrollTop = drag.top + drag.y - event.clientY; }
      });
      view.addEventListener("pointerup", () => { drag = null; });
      view.addEventListener("lostpointercapture", () => { drag = null; });
    }
    function fitWidth() {
      return Math.max(1, Math.min(...panes.map(p => Math.min(p.view.clientWidth, p.view.clientHeight * referenceWidth / referenceHeight))));
    }
    function syncView() {
      syncing = true; cancelAnimationFrame(syncFrame);
      for (const p of panes) {
        p.view.scrollLeft = center.x * p.img.width - p.view.clientWidth / 2;
        p.view.scrollTop = center.y * p.img.height - p.view.clientHeight / 2;
      }
      syncFrame = requestAnimationFrame(() => { syncing = false; });
    }
    function layout() {
      if (!compare.open) return;
      const width = fitWidth() * zoomFactor;
      for (const p of panes) {
        p.img.style.width = `${width}px`; p.img.style.height = `${width * referenceHeight / referenceWidth}px`;
      }
      syncView();
    }
    function setImage(pane) {
      const choice = choices.find(c => c.id === pane.select.value);
      if (!choice) return;
      pane.img.src = choice.url; pane.img.alt = choice.label;
      pane.params.textContent = choice.job ? describe(choice.job.settings) : "Image source avant le traitement DLSS.";
      pane.use.disabled = !choice.job; layout();
    }
    function groupSummary(job) {
      const group = jobs.filter(j => j.comparison?.group_id === job.comparison?.group_id);
      const done = group.filter(j => j.status === "succeeded").length;
      const failed = group.filter(j => ["failed", "unconfirmed", "cancelled"].includes(j.status)).length;
      return `${done}/${job.comparison.total} variantes terminées${failed ? ` · ${failed} en erreur ou annulée(s)` : ""}${group.length < job.comparison.total ? " · envoi incomplet : relancer la même demande" : ""}`;
    }
    function updateComparison() {
      if (!comparing) return;
      const scoped = jobs.filter(j => imageOwner(j.snapshot?.owner) && scopeOfJob(j) === comparing);
      const ready = scoped.filter(j => j.status === "succeeded" && j.output_url);
      if (!ready.length) { state.textContent = "Les premières variantes apparaîtront ici dès qu’elles seront prêtes."; return; }
      // Compare only images with the same final dimensions and source as the
      // selected series, including the source scaled for the visual comparison.
      const selectedJob = ready.find(j => j.job_id === panes[1].select.value) || ready.at(-1);
      referenceWidth = selectedJob.output_metadata?.width || selectedJob.output_dimensions?.[0] || 1;
      referenceHeight = selectedJob.output_metadata?.height || selectedJob.output_dimensions?.[1] || 1;
      choices = [{ id: "original", label: "Original", url: `/api/assets/${selectedJob.snapshot.input_asset_id}/content` },
        ...ready.filter(j => (j.output_metadata?.width || j.output_dimensions?.[0]) === referenceWidth
          && (j.output_metadata?.height || j.output_dimensions?.[1]) === referenceHeight
          && j.snapshot.input_asset_id === selectedJob.snapshot.input_asset_id).map((job, index) => ({
            id: job.job_id, job, url: job.output_url,
            label: `${job.comparison?.label || `DLSS ${index + 1}`} · ${new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` }))];
      state.textContent = selectedJob.comparison ? groupSummary(selectedJob) : `${choices.length - 1} variante(s) disponible(s)`;
      panes.forEach((p, index) => {
        const previous = p.select.value, before = [...p.select.options].map(o => o.value).join();
        if (before !== choices.map(c => c.id).join()) {
          p.select.replaceChildren(...choices.map(c => new Option(c.label, c.id)));
          p.select.value = choices.some(c => c.id === previous) ? previous : index ? selectedJob.job_id : "original";
          setImage(p);
        }
      });
    }
    function openCompare(value) {
      if (!imageOwner(value?.owner)) return;
      comparing = scopeOf(value); choices = []; center = { x: 0.5, y: 0.5 }; zoomFactor = 1; zoom.value = "1";
      panes.forEach(p => { p.select.replaceChildren(); p.img.removeAttribute("src"); });
      const preferred = value.preferredJobId || value.attempt.dlss?.job_id;
      if (preferred) panes[1].select.add(new Option("", preferred));
      compare.querySelector("[data-compare-error]").textContent = "";
      compare.showModal(); updateComparison(); layout();
    }
    compare.querySelector("[data-close]").addEventListener("click", () => compare.close());
    compare.addEventListener("close", () => { comparing = null; panes.forEach(p => p.img.removeAttribute("src")); });
    zoom.addEventListener("input", () => { zoomFactor = Number(zoom.value); layout(); });
    compare.querySelector("[data-fit]").addEventListener("click", () => { zoomFactor = 1; zoom.value = "1"; center = { x: 0.5, y: 0.5 }; layout(); });
    compare.querySelector("[data-native]").addEventListener("click", () => {
      zoomFactor = referenceWidth / fitWidth(); zoom.max = String(Math.max(8, zoomFactor)); zoom.value = String(zoomFactor); layout();
    });
    new ResizeObserver(layout).observe(compare.querySelector(".dlss-compare-panes"));
    function button(value) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = "Comparer DLSS";
      buttons.set(button, value); button.hidden = !jobs.some(j => scopeOfJob(j) === scopeOf(value) && j.status === "succeeded" && j.output_url);
      button.addEventListener("click", () => openCompare(value)); return button;
    }
    return {
      restore(value, saved) {
        context = value; presets = []; selected = new Set(saved?.selected || ["current", "soft", "detail", "structure", "tone"]);
        mode.value = saved?.mode || "single"; section.hidden = !imageOwner(value?.owner); paintPresets();
      },
      draft: () => ({ mode: mode.value, selected: [...(selected || [])] }),
      applyPreview(data) { presets = data.image_presets || []; paintPresets(); },
      valid: () => !isBatch() || ids().length > 0,
      batch: () => isBatch() ? ids() : null,
      refresh(values) {
        jobs = values;
        for (const [b, value] of buttons) {
          if (!b.isConnected) { buttons.delete(b); continue; }
          b.hidden = !jobs.some(j => scopeOfJob(j) === scopeOf(value) && j.status === "succeeded" && j.output_url);
        }
        if (compare.open) updateComparison();
      },
      button, groupSummary, openCompare, describe,
    };
  }
  window.PanelForgeDlssImageComparison = Object.freeze({ setup });
})();
