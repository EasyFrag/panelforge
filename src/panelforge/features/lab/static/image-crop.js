(() => {
  "use strict";

  // The browser selects coordinates only. The server crops the original pixels.
  function open({ url, save }) {
    const dialog = document.createElement("dialog");
    dialog.className = "image-crop-dialog";
    dialog.setAttribute("aria-label", "Recadrer la source");
    dialog.innerHTML = `<h2>Recadrer la source</h2>
      <p>Trace un rectangle, puis déplace-le ou ajuste ses bords. L’original reste dans l’historique.</p>
      <div class="image-crop-stage"><canvas aria-label="Image à recadrer : tracer un rectangle à la souris"></canvas></div>
      <p class="image-crop-info" role="status" aria-live="polite">Chargement de l’image…</p>
      <p class="image-crop-error" role="alert"></p>
      <div class="image-crop-actions"><button type="button" data-cancel>Annuler</button>
        <button type="button" data-save disabled>Valider et continuer</button></div>`;
    document.body.append(dialog);
    const canvas = dialog.querySelector("canvas"), ctx = canvas.getContext("2d");
    const info = dialog.querySelector(".image-crop-info"), error = dialog.querySelector(".image-crop-error");
    const accept = dialog.querySelector("[data-save]"), cancel = dialog.querySelector("[data-cancel]");
    const image = new Image();
    let rect = null, drag = null, ready = false, busy = false, scale = 1;
    let result = null;
    const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
    const handles = () => rect ? [
      ["nw", rect.x, rect.y], ["n", rect.x + rect.width / 2, rect.y],
      ["ne", rect.x + rect.width, rect.y], ["e", rect.x + rect.width, rect.y + rect.height / 2],
      ["se", rect.x + rect.width, rect.y + rect.height], ["s", rect.x + rect.width / 2, rect.y + rect.height],
      ["sw", rect.x, rect.y + rect.height], ["w", rect.x, rect.y + rect.height / 2],
    ] : [];

    function draw() {
      if (!ready) return;
      const w = image.naturalWidth, h = image.naturalHeight;
      scale = Math.min(1, Math.max(120, window.innerWidth - 96) / w, Math.max(120, window.innerHeight - 260) / h);
      const pixelRatio = window.devicePixelRatio || 1;
      const cw = Math.max(1, Math.round(w * scale * pixelRatio)), ch = Math.max(1, Math.round(h * scale * pixelRatio));
      if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
      canvas.style.width = `${w * scale}px`;
      canvas.style.height = `${h * scale}px`;
      ctx.setTransform(cw / w, 0, 0, ch / h, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.drawImage(image, 0, 0);
      ctx.fillStyle = "rgba(0,0,0,.55)";
      if (rect) {
        const { x, y, width: rw, height: rh } = rect;
        ctx.fillRect(0, 0, w, y); ctx.fillRect(0, y + rh, w, h - y - rh);
        ctx.fillRect(0, y, x, rh); ctx.fillRect(x + rw, y, w - x - rw, rh);
        ctx.strokeStyle = "white"; ctx.lineWidth = 2 / scale;
        ctx.strokeRect(x, y, rw, rh);
        const size = 8 / scale;
        ctx.fillStyle = "white";
        for (const [, hx, hy] of handles()) ctx.fillRect(hx - size / 2, hy - size / 2, size, size);
      } else ctx.fillRect(0, 0, w, h);
      info.textContent = busy ? "Enregistrement du recadrage…" : rect
        ? `Sélection : ${rect.width} × ${rect.height} px · source : ${w} × ${h} px`
        : "Clique et glisse sur l’image pour délimiter la zone à conserver.";
      accept.disabled = busy || !rect || rect.width < 1 || rect.height < 1;
    }

    function position(event) {
      const box = canvas.getBoundingClientRect();
      return { x: clamp(Math.round((event.clientX - box.left) * image.naturalWidth / box.width), 0, image.naturalWidth),
        y: clamp(Math.round((event.clientY - box.top) * image.naturalHeight / box.height), 0, image.naturalHeight) };
    }
    function hit(p) {
      const handle = handles().find(([, x, y]) => Math.abs(p.x - x) <= 9 / scale && Math.abs(p.y - y) <= 9 / scale);
      if (handle) return handle[0];
      return rect && p.x >= rect.x && p.x <= rect.x + rect.width && p.y >= rect.y && p.y <= rect.y + rect.height ? "move" : "draw";
    }
    canvas.addEventListener("pointerdown", event => {
      if (!ready || busy || event.button !== 0 || drag) return;
      event.preventDefault();
      const p = position(event);
      drag = { id: event.pointerId, start: p, mode: hit(p), initial: rect && { ...rect } };
      if (drag.mode === "draw") rect = { x: p.x, y: p.y, width: 0, height: 0 };
      canvas.setPointerCapture(event.pointerId);
      error.textContent = "";
      draw();
    });
    canvas.addEventListener("pointermove", event => {
      if (!ready || busy) return;
      const p = position(event);
      if (!drag) {
        const mode = hit(p);
        canvas.style.cursor = mode === "draw" ? "crosshair" : mode === "move" ? "move" : `${mode}-resize`;
        return;
      }
      if (event.pointerId !== drag.id) return;
      if (drag.mode === "draw") {
        rect = { x: Math.min(drag.start.x, p.x), y: Math.min(drag.start.y, p.y),
          width: Math.abs(p.x - drag.start.x), height: Math.abs(p.y - drag.start.y) };
      } else if (drag.mode === "move") {
        const r = drag.initial;
        rect = { ...r, x: clamp(r.x + p.x - drag.start.x, 0, image.naturalWidth - r.width),
          y: clamp(r.y + p.y - drag.start.y, 0, image.naturalHeight - r.height) };
      } else {
        const r = drag.initial;
        let left = r.x, top = r.y, right = r.x + r.width, bottom = r.y + r.height;
        if (drag.mode.includes("w")) left = clamp(p.x, 0, right - 1);
        if (drag.mode.includes("e")) right = clamp(p.x, left + 1, image.naturalWidth);
        if (drag.mode.includes("n")) top = clamp(p.y, 0, bottom - 1);
        if (drag.mode.includes("s")) bottom = clamp(p.y, top + 1, image.naturalHeight);
        rect = { x: left, y: top, width: right - left, height: bottom - top };
      }
      draw();
    });
    function end(event) {
      if (!drag || event.pointerId !== drag.id) return;
      drag = null;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      if (!rect?.width || !rect?.height) rect = null;
      draw();
    }
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    cancel.addEventListener("click", () => { if (!busy) dialog.close(); });
    dialog.addEventListener("cancel", event => { if (busy) event.preventDefault(); });
    accept.addEventListener("click", async () => {
      if (busy || !rect?.width || !rect?.height) return;
      busy = true; cancel.disabled = true; error.textContent = ""; draw();
      try {
        result = await save({ ...rect, source_width: image.naturalWidth, source_height: image.naturalHeight });
        dialog.close();
      } catch (failure) {
        error.textContent = failure.message || "Le recadrage n’a pas pu être enregistré.";
      } finally { busy = false; cancel.disabled = false; draw(); }
    });
    image.onload = () => { ready = true; draw(); };
    image.onerror = () => { info.textContent = ""; error.textContent = "Impossible de charger l’image source."; };
    window.addEventListener("resize", draw);
    const completion = new Promise(resolve => dialog.addEventListener("close", () => {
      window.removeEventListener("resize", draw);
      image.onload = image.onerror = null;
      dialog.remove();
      resolve(result);
    }, { once: true }));
    dialog.showModal();
    image.src = url;
    return completion;
  }
  window.PanelForgeImageCrop = { open };
})();
