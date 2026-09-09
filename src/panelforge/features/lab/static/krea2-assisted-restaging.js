/* Scene + Assisted subject: prepare an Edit workshop, never auto-generate. */
(() => {
  "use strict";
  function create({ request, getProject, getInstruction, onPrepared }) {
    const dialog = document.getElementById("krea2-assisted-restaging-dialog");
    const el = name => dialog.querySelector(`[data-restage="${name}"]`);
    const scene = el("scene"), instruction = el("instruction"), file = el("file");
    const drafts = new Map(), imported = new Map();
    let selection = null, epoch = 0, uploading = false, saving = false;
    const newId = () => crypto.randomUUID?.() || `restage-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const storageKey = project => `panelforge.assisted.scene.${project}`;
    const draftKey = (project, attempt) => `${project.project_id}/${attempt.attempt_id}`;
    function remember() {
      if (!selection) return;
      const draft = drafts.get(selection.key);
      if (draft.scene !== scene.value || draft.instruction !== instruction.value) {
        draft.scene = scene.value; draft.instruction = instruction.value; draft.requestId = newId();
      }
    }
    function render() {
      const id = scene.value;
      el("scene-preview").hidden = !id;
      if (id) el("scene-preview").src = `/api/assets/${encodeURIComponent(id)}/content`;
      else el("scene-preview").removeAttribute("src");
      scene.disabled = file.disabled = saving || uploading;
      instruction.disabled = saving;
      el("start").disabled = saving || uploading || !id || !instruction.value.trim();
      el("cancel").disabled = saving;
    }
    function open(project, attempt) {
      if (saving) return;
      epoch++; uploading = false;
      selection = { project: project.project_id, attempt: attempt.attempt_id, key: draftKey(project, attempt) };
      let lastScene = null;
      try { lastScene = JSON.parse(localStorage.getItem(storageKey(project.project_id))); } catch (_) { /* optional */ }
      const choices = new Map();
      for (const a of project.attempts || []) if (a.status === "succeeded" && a.output_asset_id !== attempt.output_asset_id) {
        choices.set(a.output_asset_id, a.label || `Essai ${a.index}`);
      }
      if (project.reference_asset_id) choices.set(project.reference_asset_id, "Référence initiale de l’atelier");
      if (lastScene?.asset_id) choices.set(lastScene.asset_id, lastScene.filename || "Dernier décor choisi");
      for (const image of imported.get(project.project_id) || []) choices.set(image.asset_id, image.filename);
      let draft = drafts.get(selection.key);
      if (!draft) {
        draft = {scene: lastScene?.asset_id || "", instruction: getInstruction(), requestId: newId()};
        drafts.set(selection.key, draft);
      }
      if (draft.scene && !choices.has(draft.scene)) choices.set(draft.scene, "Décor du brouillon");
      scene.replaceChildren(new Option("Choisir le décor…", ""));
      for (const [id, label] of choices) scene.add(new Option(label, id));
      scene.value = draft.scene; instruction.value = draft.instruction; file.value = "";
      el("subject-preview").src = attempt.output_url;
      el("subject-label").textContent = `${attempt.label || `Essai ${attempt.index}`} · sujet et action`;
      el("note").textContent = "Un décor vide évite de conserver un ancien personnage. L’intégration sera une nouvelle génération Identity Edit ; sa qualité reste à comparer.";
      render(); if (!dialog.open) dialog.showModal();
    }
    function close() {
      if (saving) return;
      remember(); epoch++; uploading = false; selection = null;
      if (dialog.open) dialog.close();
    }
    dialog.addEventListener("cancel", event => { if (saving) event.preventDefault(); });
    dialog.addEventListener("close", () => {
      if (dialog.open) return; // An older close event may arrive after reopening.
      remember(); epoch++; uploading = false;
    });
    el("cancel").addEventListener("click", close);
    scene.addEventListener("change", () => { remember(); render(); });
    instruction.addEventListener("input", () => { remember(); render(); });
    file.addEventListener("change", async () => {
      const image = file.files[0]; if (!image || !selection || saving) return;
      const mine = ++epoch, project = selection.project;
      uploading = true; render(); el("note").textContent = "Import du décor…";
      try {
        const body = new FormData(); body.set("image", image);
        const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(project)}/scene-images`, {method:"POST", body});
        if (mine !== epoch || getProject()?.project_id !== project) return;
        imported.set(project, [...(imported.get(project) || []), payload.image]);
        scene.add(new Option(payload.image.filename, payload.image.asset_id)); scene.value = payload.image.asset_id;
        remember(); el("note").textContent = "Décor importé. Il sera l’image 1 d’Identity Edit.";
      } catch (error) { if (mine === epoch) el("note").textContent = error.message; }
      finally { if (mine === epoch) { uploading = false; render(); } }
    });
    el("start").addEventListener("click", async () => {
      if (!selection || saving || uploading || !scene.value || !instruction.value.trim()) return;
      if (getProject()?.project_id !== selection.project) { close(); return; }
      remember(); const target = {...selection}, draft = {...drafts.get(selection.key)};
      saving = true; render(); el("note").textContent = "Préparation de l’atelier Edit…";
      try {
        const payload = await request(`/api/image-lab/krea2-assisted/projects/${encodeURIComponent(target.project)}/attempts/${encodeURIComponent(target.attempt)}/restage`, {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({scene_asset_id:draft.scene, instruction:draft.instruction, request_id:draft.requestId}),
        });
        try { localStorage.setItem(storageKey(target.project), JSON.stringify({asset_id:draft.scene, filename:scene.selectedOptions[0]?.textContent})); } catch (_) { /* optional */ }
        await onPrepared(payload.source);
        saving = false; close();
      } catch (error) { el("note").textContent = error.message; }
      finally { saving = false; render(); }
    });
    return {open, close, get saving() { return saving; }};
  }
  window.PanelForgeAssistedRestaging = {create};
})();
