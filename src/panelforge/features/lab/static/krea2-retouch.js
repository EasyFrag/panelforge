/* Local mask editor. No network requests occur while drawing or navigating. */
(() => {
  "use strict";
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const requestId = () => crypto.randomUUID ? crypto.randomUUID()
    : `retouch-${Array.from(crypto.getRandomValues(new Uint8Array(16)), (value) => value.toString(16).padStart(2, "0")).join("")}`;
  const imageFrom = (url) => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Impossible de charger une image de retouche."));
    image.src = url;
  });
  function pixels(image, width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(image, 0, 0);
    return ctx.getImageData(0, 0, width, height);
  }
  function create({ root, load, save, onOpenChange, onSaved }) {
    const role = (name) => root.querySelector(`[data-role="${name}"]`);
    const action = (name) => root.querySelector(`[data-action="${name}"]`);
    const before = role("before"), after = role("after");
    const beforeView = role("before-view"), afterView = role("after-view");
    const beforeCtx = before.getContext("2d"), afterCtx = after.getContext("2d");
    const drafts = new Map();
    let current = null, serial = 0, saving = false, loading = false, frame = 0;
    let tool = "paint", pointer = null, scale = 1, x = 0, y = 0, dirty = null;

    function message(text, error = false) {
      role("message").textContent = text;
      role("message").classList.toggle("error", error);
    }
    function controls() {
      const editable = current?.meta.editable && !saving && !loading;
      for (const name of ["paint", "erase", "save"]) action(name).disabled = !editable;
      for (const name of ["pan", "fit", "zoom-in", "zoom-out"]) action(name).disabled = !current || saving || loading;
      action("close").disabled = saving;
      for (const name of ["size", "softness"]) role(name).disabled = !editable;
      role("harmonize").disabled = role("strength").disabled = !editable;
      role("harmonize").checked = Boolean(current?.draft.harmonize);
      role("strength").value = String(current?.draft.strength ?? 100);
      role("strength-control").hidden = !current?.draft.harmonize;
      role("strength-value").textContent = `${role("strength").value} %`;
      role("show-mask").disabled = role("left-image").disabled = !current || saving || loading;
      role("left-image").value = current?.draft.leftImage || "generated";
      action("undo").disabled = !editable || !current.draft.position;
      action("redo").disabled = !editable || current.draft.position >= current.draft.commands.length;
      for (const name of ["paint", "erase", "pan"]) action(name).setAttribute("aria-pressed", String(tool === name));
      role("size-value").textContent = `${role("size").value} px`;
      role("softness-value").textContent = `${role("softness").value} %`;
      role("draft-state").textContent = !current ? "" : !current.meta.editable
        ? "Étape validée · consultation du masque"
        : `${current.meta.width} × ${current.meta.height} · ${current.draft.changed ? "Brouillon non enregistré" : "Prêt à retoucher"}`;
      root.classList.toggle("is-panning", tool === "pan");
    }
    function transform() {
      for (const canvas of [before, after]) canvas.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      role("zoom").textContent = `${Math.round(scale * 100)} %`;
    }
    function fit() {
      if (!current) return;
      const width = Math.min(beforeView.clientWidth, afterView.clientWidth);
      const height = Math.min(beforeView.clientHeight, afterView.clientHeight);
      if (width < 1 || height < 1) return;
      scale = Math.min(width / before.width, height / before.height);
      x = (width - before.width * scale) / 2;
      y = (height - before.height * scale) / 2;
      transform();
    }
    function zoom(factor, anchorX = beforeView.clientWidth / 2, anchorY = beforeView.clientHeight / 2) {
      if (!current || saving) return;
      const next = clamp(scale * factor, 0.02, 8);
      x = anchorX - (anchorX - x) * next / scale;
      y = anchorY - (anchorY - y) * next / scale;
      scale = next;
      transform();
    }
    function drawRegion() {
      frame = 0;
      if (!current || !dirty) return;
      const rect = dirty; dirty = null;
      const { source, generated, harmonized, left, result, draft } = current;
      const width = before.width;
      const colorLevel = draft.harmonize ? Math.floor((draft.strength * 255 + 50) / 100) : 0;
      const showMask = role("show-mask").checked;
      const showingSource = draft.leftImage === "source";
      role("left-label").textContent = showingSource ? current.meta.source_label || "Source de l’étape" : colorLevel ? "Image 2 · harmonisée" : "Image 2 · génération";
      before.setAttribute("aria-label", showingSource ? "Dessiner le masque sur la source" : "Dessiner le masque sur l’image générée");
      for (let py = rect.top; py < rect.bottom; py++) {
        for (let px = rect.left; px < rect.right; px++) {
          const p = py * width + px, i = p * 4, m = draft.mask[p];
          // Same integer interpolation as Pillow Image.composite, including alpha.
          for (let channel = 0; channel < 4; channel++) {
            const value = Math.floor((harmonized.data[i + channel] * colorLevel + generated.data[i + channel] * (255 - colorLevel) + 127) / 255);
            result.data[i + channel] = Math.floor((value * m + source.data[i + channel] * (255 - m) + 127) / 255);
            left.data[i + channel] = showingSource ? source.data[i + channel] : value;
          }
          const opacity = showMask ? m / 255 * 0.4 : 0;
          left.data[i] = Math.round(left.data[i] * (1 - opacity) + 235 * opacity);
          left.data[i + 1] = Math.round(left.data[i + 1] * (1 - opacity) + 35 * opacity);
          left.data[i + 2] = Math.round(left.data[i + 2] * (1 - opacity) + 45 * opacity);
        }
      }
      for (const [ctx, image] of [[beforeCtx, left], [afterCtx, result]]) {
        ctx.putImageData(image, 0, 0, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top);
      }
    }
    function invalidate(rect = { left: 0, top: 0, right: before.width, bottom: before.height }) {
      dirty = dirty ? {
        left: Math.min(dirty.left, rect.left), top: Math.min(dirty.top, rect.top),
        right: Math.max(dirty.right, rect.right), bottom: Math.max(dirty.bottom, rect.bottom),
      } : rect;
      if (!frame) frame = requestAnimationFrame(drawRegion);
    }
    function stamp(command, px, py) {
      const radius = command.size / 2;
      const bounds = { left: Math.max(0, Math.floor(px - radius)), top: Math.max(0, Math.floor(py - radius)),
        right: Math.min(before.width, Math.ceil(px + radius)), bottom: Math.min(before.height, Math.ceil(py + radius)) };
      if (bounds.right <= bounds.left || bounds.bottom <= bounds.top) return;
      const feather = Math.max(0.5, radius * command.softness);
      for (let row = bounds.top; row < bounds.bottom; row++) {
        for (let col = bounds.left; col < bounds.right; col++) {
          const distance = Math.hypot(col + 0.5 - px, row + 0.5 - py);
          const coverage = Math.round(255 * clamp((radius - distance) / feather, 0, 1));
          const index = row * before.width + col;
          const old = current.draft.mask[index];
          current.draft.mask[index] = command.erase ? Math.min(old, 255 - coverage) : Math.max(old, coverage);
        }
      }
      invalidate(bounds);
    }
    function segment(command, from, to) {
      const distance = Math.hypot(to[0] - from[0], to[1] - from[1]);
      const steps = Math.max(1, Math.ceil(distance / Math.max(1, command.size / 8)));
      for (let step = 1; step <= steps; step++) {
        stamp(command, from[0] + (to[0] - from[0]) * step / steps, from[1] + (to[1] - from[1]) * step / steps);
      }
    }
    function changed() {
      current.draft.changed = true;
      current.draft.request = null;
      controls();
    }
    function replay() {
      if (!current) return;
      current.draft.mask.set(current.draft.initial);
      for (const command of current.draft.commands.slice(0, current.draft.position)) {
        stamp(command, ...command.points[0]);
        for (let i = 1; i < command.points.length; i++) segment(command, command.points[i - 1], command.points[i]);
      }
      invalidate(); changed();
    }
    function point(event, viewport) {
      const rect = viewport.getBoundingClientRect();
      return [clamp((event.clientX - rect.left - x) / scale, -600, before.width + 600),
        clamp((event.clientY - rect.top - y) / scale, -600, before.height + 600)];
    }
    function endPointer() {
      if (!pointer) return;
      if (pointer.viewport.hasPointerCapture(pointer.id)) pointer.viewport.releasePointerCapture(pointer.id);
      pointer = null;
      controls();
    }
    for (const viewport of [beforeView, afterView]) {
      viewport.addEventListener("pointerdown", (event) => {
        if (!current || saving || loading || pointer || ![0, 1].includes(event.button)) return;
        const pan = tool === "pan" || event.button === 1 || viewport === afterView || !current.meta.editable;
        const p = point(event, viewport);
        if (!pan && (p[0] < 0 || p[1] < 0 || p[0] >= before.width || p[1] >= before.height)) return;
        event.preventDefault(); before.focus({ preventScroll: true }); viewport.setPointerCapture(event.pointerId);
        pointer = { id: event.pointerId, viewport, pan, client: [event.clientX, event.clientY] };
        if (!pan) {
          const draft = current.draft;
          draft.commands.length = draft.position;
          const command = { erase: tool === "erase", size: Number(role("size").value), softness: Number(role("softness").value) / 100, points: [p] };
          draft.commands.push(command); draft.position++;
          pointer.command = command;
          stamp(command, ...p); changed();
        }
      });
      viewport.addEventListener("pointermove", (event) => {
        if (!current) return;
        if (viewport === beforeView) {
          const cursor = role("cursor"), rect = viewport.getBoundingClientRect();
          cursor.hidden = tool === "pan" || !current.meta.editable || saving;
          const diameter = Number(role("size").value) * scale;
          cursor.style.width = `${diameter}px`; cursor.style.height = `${diameter}px`;
          cursor.style.left = `${event.clientX - rect.left}px`; cursor.style.top = `${event.clientY - rect.top}px`;
        }
        if (!pointer || pointer.id !== event.pointerId) return;
        if (pointer.pan) {
          x += event.clientX - pointer.client[0]; y += event.clientY - pointer.client[1];
          pointer.client = [event.clientX, event.clientY]; transform();
        } else {
          const command = pointer.command, p = point(event, viewport);
          segment(command, command.points.at(-1), p); command.points.push(p);
        }
      });
      viewport.addEventListener("pointerup", endPointer);
      viewport.addEventListener("pointercancel", endPointer);
      viewport.addEventListener("lostpointercapture", () => { pointer = null; });
      viewport.addEventListener("pointerleave", () => { role("cursor").hidden = true; });
      viewport.addEventListener("wheel", (event) => {
        if (!current || saving) return;
        event.preventDefault(); endPointer();
        const rect = viewport.getBoundingClientRect();
        zoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, event.clientX - rect.left, event.clientY - rect.top);
      }, { passive: false });
    }
    function close() {
      if (saving) return;
      endPointer(); serial++; loading = false;
      if (frame) cancelAnimationFrame(frame);
      frame = 0; dirty = null; current = null;
      role("cursor").hidden = true;
      before.width = after.width = 1; before.height = after.height = 1;
      root.hidden = true; onOpenChange(false);
    }
    async function open(sourceId, attemptId, { draftKey = "" } = {}) {
      if (saving) return;
      close();
      const mine = ++serial, key = `${sourceId}/${attemptId}${draftKey ? `/${draftKey}` : ""}`;
      loading = true; root.hidden = false; onOpenChange(true); controls();
      root.scrollIntoView({ block: "start" });
      role("title").textContent = "Préparation de la retouche…";
      message("Chargement des deux images…");
      try {
        const meta = await load(sourceId, attemptId);
        if (mine !== serial) return;
        const [sourceImage, generatedImage, harmonizedImage, maskImage] = await Promise.all([
          imageFrom(meta.source_url), imageFrom(meta.generated_url), imageFrom(meta.harmonized_url),
          meta.mask_url ? imageFrom(meta.mask_url) : null,
        ]);
        if (mine !== serial) return;
        const { width, height } = meta;
        for (const image of [sourceImage, generatedImage, harmonizedImage, ...(maskImage ? [maskImage] : [])]) {
          if (image.naturalWidth !== width || image.naturalHeight !== height) throw new Error("Dimensions de retouche incohérentes.");
        }
        before.width = after.width = width; before.height = after.height = height;
        // A validated stage always displays its saved mask, never a local draft.
        let draft = meta.editable ? drafts.get(key) : null;
        if (!draft) {
          const initial = new Uint8ClampedArray(width * height);
          if (maskImage) {
            const saved = pixels(maskImage, width, height).data;
            for (let i = 0; i < initial.length; i++) initial[i] = saved[i * 4];
          }
          draft = { initial, mask: initial.slice(), commands: [], position: 0, changed: false, request: null,
            harmonize: Boolean(meta.harmonize), strength: meta.harmonize_strength ?? 100, leftImage: "generated" };
          if (meta.editable) drafts.set(key, draft);
        }
        current = { key, meta, source: pixels(sourceImage, width, height), generated: pixels(generatedImage, width, height),
          harmonized: pixels(harmonizedImage, width, height),
          left: new ImageData(width, height), result: new ImageData(width, height), draft };
        loading = false;
        role("title").textContent = `${meta.label} · ${meta.editor_title || "Retoucher"}`;
        message(meta.editable ? "Peins à gauche les zones où conserver l’image 2. Le résultat reste à la taille de la source." : "Cette étape est figée. Tu peux inspecter son masque et ses couleurs.");
        invalidate(); fit(); controls();
      } catch (error) {
        if (mine === serial) { loading = false; message(error.message, true); controls(); }
      }
    }
    function maskBlob() {
      const canvas = document.createElement("canvas");
      canvas.width = before.width; canvas.height = before.height;
      const ctx = canvas.getContext("2d"), image = ctx.createImageData(canvas.width, canvas.height);
      for (let i = 0; i < current.draft.mask.length; i++) {
        image.data[i * 4] = image.data[i * 4 + 1] = image.data[i * 4 + 2] = 255;
        image.data[i * 4 + 3] = current.draft.mask[i];
      }
      ctx.putImageData(image, 0, 0);
      return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Impossible d’encoder le masque.")), "image/png"));
    }
    async function persist() {
      if (!current || !current.meta.editable || saving) return;
      endPointer(); saving = true; controls();
      const editing = current;
      message("Enregistrement de la retouche…");
      const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 45000);
      try {
        if (!editing.draft.request) editing.draft.request = { id: requestId(), mask: await maskBlob(),
          harmonize: editing.draft.harmonize, strength: editing.draft.strength };
        const result = await save(editing.meta.source_id, editing.meta.attempt_id, editing.draft.request, abort.signal, editing.meta);
        // Server acknowledgement is the boundary: later UI failures must not invite a duplicate save.
        drafts.delete(editing.key);
        saving = false; close();
        await onSaved(result, editing.meta.source_id);
      } catch (error) {
        if (current === editing) message(error.name === "AbortError" ? "Réponse trop lente. Le brouillon est conservé ; réessayer ne créera pas de doublon." : error.message, true);
      } finally {
        clearTimeout(timeout); saving = false; controls();
      }
    }
    for (const name of ["paint", "erase", "pan"]) action(name).addEventListener("click", () => { endPointer(); tool = name; controls(); });
    for (const name of ["size", "softness"]) role(name).addEventListener("input", controls);
    function colorChanged() {
      if (!current?.meta.editable || saving || loading) return;
      endPointer();
      current.draft.harmonize = role("harmonize").checked;
      current.draft.strength = Number(role("strength").value);
      changed(); invalidate();
    }
    role("harmonize").addEventListener("change", colorChanged);
    role("strength").addEventListener("input", colorChanged);
    role("show-mask").addEventListener("change", () => invalidate());
    role("left-image").addEventListener("change", () => {
      if (!current || saving || loading) return;
      endPointer(); current.draft.leftImage = role("left-image").value;
      role("cursor").hidden = true;
      invalidate();
    });
    action("undo").addEventListener("click", () => { endPointer(); if (current?.draft.position && !saving) { current.draft.position--; replay(); } });
    action("redo").addEventListener("click", () => { endPointer(); if (current && current.draft.position < current.draft.commands.length && !saving) { current.draft.position++; replay(); } });
    action("fit").addEventListener("click", fit);
    action("zoom-in").addEventListener("click", () => zoom(1.25));
    action("zoom-out").addEventListener("click", () => zoom(0.8));
    action("close").addEventListener("click", close);
    action("save").addEventListener("click", persist);
    root.addEventListener("keydown", (event) => {
      if (!current || saving || !current.meta.editable || /INPUT|TEXTAREA/.test(event.target.tagName)) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault(); action(event.shiftKey ? "redo" : "undo").click();
      }
    });
    new ResizeObserver(() => { if (current && !pointer) fit(); }).observe(beforeView);
    window.addEventListener("beforeunload", (event) => {
      if (saving || [...drafts.values()].some((draft) => draft.changed)) { event.preventDefault(); event.returnValue = ""; }
    });
    function discardSource(sourceId) {
      if (saving) return;
      if (loading || current?.meta.source_id === sourceId) close();
      for (const key of drafts.keys()) if (key.startsWith(`${sourceId}/`)) drafts.delete(key);
    }
    return { open, close, discardSource, get saving() { return saving; }, get isOpen() { return !root.hidden; } };
  }
  window.PanelForgeKrea2Retouch = Object.freeze({ create });
})();
