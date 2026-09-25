(() => {
  "use strict";
  function create({request, onSaved}) {
    const el = name => document.getElementById(`episode-thumbnail-badge-${name}`);
    const dialog = el("dialog"), stage = el("stage"), handle = el("handle");
    let snapshot = null, position = null, saving = false, loaded = new Set(), drag = null;
    const clamp = n => Math.max(0, Math.min(100, n));
    function draw() {
      if (!snapshot) return;
      const g = snapshot.badge, c = g.canvas;
      handle.style.width = `${g.width / c.width * 100}%`;
      handle.style.left = `${Math.round(position.x / 100 * (c.width - g.width)) / c.width * 100}%`;
      handle.style.top = `${Math.round(position.y / 100 * (c.height - g.height)) / c.height * 100}%`;
      for (const axis of ["x", "y"]) el(axis).value = position[axis];
      handle.setAttribute("aria-label", `Bandeau : horizontal ${Math.round(position.x)} %, vertical ${Math.round(position.y)} %. Flèches pour déplacer.`);
    }
    function ready() {
      el("save").disabled = saving || loaded.size !== 2;
      handle.disabled = saving || loaded.size !== 2;
      for (const control of dialog.querySelectorAll("input, [data-badge-preset], #episode-thumbnail-badge-reset")) control.disabled = saving;
    }
    for (const part of ["background", "image"]) {
      el(part).addEventListener("load", () => {
        if (!snapshot || !el(part).src.includes(`expected_revision=${snapshot.revision}`)) return;
        loaded.add(part); el("status").textContent = loaded.size === 2 ? "Aperçu prêt. Déplace le bandeau puis enregistre." : "Préparation de l’aperçu…"; ready();
      });
      el(part).addEventListener("error", () => {
        loaded.delete(part); el("error").textContent = "Impossible de charger l’aperçu. Ferme puis rouvre ce réglage pour actualiser la miniature."; ready();
      });
    }
    for (const axis of ["x", "y"]) el(axis).addEventListener("input", () => { if (position && !saving) { position[axis] = Number(el(axis).value); draw(); } });
    for (const button of dialog.querySelectorAll("[data-badge-preset]")) button.addEventListener("click", () => {
      if (snapshot && !saving) { position = {x: 50, y: Number(button.dataset.badgePreset)}; draw(); }
    });
    el("reset").addEventListener("click", () => { if (snapshot && !saving) { position = {...snapshot.badge.default_position}; draw(); } });
    handle.addEventListener("pointerdown", event => {
      if (!snapshot || saving || handle.disabled || event.button !== 0) return;
      event.preventDefault(); drag = {id: event.pointerId, x: event.clientX, y: event.clientY, position: {...position}, rect: stage.getBoundingClientRect()};
      handle.setPointerCapture(event.pointerId); handle.focus();
    });
    handle.addEventListener("pointermove", event => {
      if (!drag || drag.id !== event.pointerId || !snapshot) return;
      const g = snapshot.badge;
      position = {x: clamp(drag.position.x + (event.clientX - drag.x) / drag.rect.width * g.canvas.width / (g.canvas.width - g.width) * 100),
        y: clamp(drag.position.y + (event.clientY - drag.y) / drag.rect.height * g.canvas.height / (g.canvas.height - g.height) * 100)};
      draw();
    });
    for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) handle.addEventListener(name, () => { drag = null; });
    handle.addEventListener("keydown", event => {
      const move = {ArrowLeft: ["x", -1], ArrowRight: ["x", 1], ArrowUp: ["y", -1], ArrowDown: ["y", 1]}[event.key];
      if (!move || !position || saving) return;
      event.preventDefault(); position[move[0]] = clamp(position[move[0]] + move[1] * (event.shiftKey ? 5 : 1)); draw();
    });
    el("close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { snapshot = null; drag = null; });
    el("form").addEventListener("submit", async event => {
      event.preventDefault(); if (!snapshot || saving || loaded.size !== 2) return;
      const captured = snapshot; saving = true; ready(); el("error").textContent = ""; el("status").textContent = "Enregistrement local…";
      try {
        const next = await request(`/api/episodes/${encodeURIComponent(captured.episode_id)}/thumbnail/badge`, {
          method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({request_id: crypto.randomUUID(),
            expected_revision: captured.revision, position, remember_series: el("remember").checked})});
        onSaved(next); if (snapshot === captured) dialog.close();
      } catch (error) { if (snapshot === captured) { el("error").textContent = error.message; el("status").textContent = "Position non enregistrée."; } }
      finally { saving = false; ready(); }
    });
    return {
      open(value) {
        if (!value?.badge || saving) return;
        snapshot = structuredClone(value); position = {...snapshot.badge.position}; loaded = new Set();
        el("error").textContent = ""; el("status").textContent = "Préparation de l’aperçu…"; el("remember").checked = true;
        stage.style.aspectRatio = `${value.badge.canvas.width} / ${value.badge.canvas.height}`;
        const path = `/api/episodes/${encodeURIComponent(value.episode_id)}/thumbnail/badge-preview/`;
        el("background").src = `${path}background?expected_revision=${value.revision}`;
        el("image").src = `${path}badge?expected_revision=${value.revision}`;
        draw(); ready(); dialog.showModal();
      },
      close() { dialog.close(); },
    };
  }
  window.PanelForgeThumbnailLayout = {create};
})();
