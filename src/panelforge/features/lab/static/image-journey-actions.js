(() => {
  "use strict";
  window.PanelForgeJourneyActions = {
    attach(bridge) {
      const $ = id => document.getElementById("ij-" + id);
      const dialog = $("operation"), terminal = op => ["completed", "cancelled"].includes(op.status);
      const phases = {planning:"Préparation de la transformation", prompting:"Préparation du prompt", queueing:"Mise en file",
        rendering:"Génération", protecting:"Préservation du décor", reviewing:"Relecture", completed:"Terminé", cancelled:"Abandonné"};
      let selection = null, busy = false, command = null, selectedOperation = null, resultKey = "";
      const operations = () => bridge.project()?.image_operations || [];
      const pending = () => operations().some(op => !terminal(op));
      const editable = () => bridge.project()?.can_edit_sequence ??
        (["paused", "completed"].includes(bridge.project()?.status) && !pending());
      const url = id => "/projects/" + encodeURIComponent(id) + "/image-operations";
      const error = message => { $("operation-error").textContent = message || ""; $("operation-error").hidden = !message; };

      function image(frame, caption) {
        const figure = document.createElement("figure"), button = document.createElement("button");
        const img = document.createElement("img"), label = document.createElement("figcaption");
        button.type = "button"; button.className = "ij-operation-image";
        button.setAttribute("aria-label", "Agrandir · " + caption); button.title = "Agrandir l’image";
        img.src = bridge.asset(frame.asset_id); img.alt = caption;
        button.append(img); label.textContent = caption; figure.append(button, label);
        button.onclick = () => bridge.showImage({...frame, title:caption, detailTitle:caption});
        return figure;
      }
      function reset() {
        if (dialog.open) dialog.close();
        selection = null; selectedOperation = null; command = null; resultKey = "";
      }
      function open(kind, frame, following=null, operation=null) {
        const project = bridge.project();
        if (!project || busy) return;
        bridge.hidePreview();
        selection = {projectId:project.id, kind, frame, following};
        selectedOperation = operation?.id || null; command = null; resultKey = ""; error("");
        $("operation-title").textContent = kind === "hq" ? "Essai HQ ×2" : kind === "insert" ? "Insérer une étape" : "Ajouter une étape";
        $("operation-input-label").textContent = kind === "hq" ? "Prompt MiniMax" : "État souhaité";
        $("operation-input").maxLength = kind === "hq" ? 24000 : 6000;
        $("operation-input").value = operation ? (kind === "hq" ? operation.prompt : operation.intention)
          : kind === "hq" ? bridge.spec()?.hq_prompt || "" : "";
        $("operation-input").placeholder = kind === "insert" ? "Le deck seul, avant l’installation de la porte…"
          : "Ajouter un petit escalier en bois pour accéder au deck…";
        const dims = frame.step?.output_dimensions || (frame.index === 0 ? project.source_dimensions : null);
        $("operation-hint").textContent = kind === "hq"
          ? `Copie HQ ×2${dims ? ` · ${dims[0] * 2} × ${dims[1] * 2} px` : ""}. L’original est conservé.`
          : kind === "insert" ? "Une image entre ces deux états. La suite est conservée." : "Une nouvelle image depuis cet état.";
        $("operation-images").replaceChildren(image(frame, kind === "hq" ? "Original" : kind === "insert" ? "État précédent" : "Dernière image"),
          ...(following ? [image(following, "État suivant conservé")] : []));
        $("operation-result").replaceChildren();
        paintDialog();
        if (!dialog.open) dialog.showModal();
        if (!operation) $("operation-input").focus();
      }
      function openOperation(operation) {
        const frames = bridge.frames(), frame = frames.find(f => f.key === operation.after_frame_id);
        if (!frame) return;
        const following = operation.before_frame_id ? frames.find(f => f.key === operation.before_frame_id) : null;
        open(operation.kind, frame, following, operation);
      }
      function paintDialog() {
        if (!selection) return;
        if (selection.projectId !== bridge.project()?.id) return reset();
        const op = operations().find(op => op.id === selectedOperation);
        const active = op && !terminal(op), blocked = pending() || selection.kind !== "hq" && !editable();
        $("operation-input").readOnly = !!active || busy || selection.kind === "hq";
        $("operation-generate").hidden = selection.kind === "hq" || !!active || !!op;
        $("operation-generate").disabled = busy || blocked;
        $("operation-generate").textContent = "Générer";
        $("operation-resume").hidden = op?.status !== "paused";
        $("operation-cancel").hidden = op?.status !== "paused";
        $("operation-resume").disabled = busy;
        $("operation-cancel").disabled = busy || op?.phase === "rendering";
        $("operation-close").disabled = busy;
        $("operation-status").textContent = op ? (op.status === "paused" ? "Suspendu · " : "") + (phases[op.phase] || op.phase) : "";
        if (op?.error) error(op.error);
        const key = op?.output_asset_id || "";
        if (key !== resultKey) {
          resultKey = key;
          $("operation-result").replaceChildren();
          if (!key) {
            $("operation-images").replaceChildren(image(selection.frame, selection.kind === "hq" ? "Original" : selection.following ? "État précédent" : "Dernière image"),
              ...(selection.following ? [image(selection.following, "État suivant conservé")] : []));
          }
          if (key) {
            const frame = {asset_id:key, index:0, title:selection.kind === "hq" ? "Version HQ" : "Nouvelle image"};
            if (selection.kind === "hq") {
              $("operation-images").replaceChildren(image(selection.frame, "Original"), image(frame, "Version HQ ×2"));
            } else {
              $("operation-result").append(image(frame, "Nouvelle image"));
            }
            const link = document.createElement("a");
            link.href = bridge.asset(key); link.download = `${selection.kind}-${op.id}.png`;
            link.textContent = selection.kind === "hq" ? "Télécharger la version HQ" : "Télécharger l’image";
            $("operation-result").append(link);
          }
        }
        $("operation-review").textContent = op?.review?.observation || "";
        const history = selection.kind === "hq" ? operations().filter(o => o.kind === "hq" && o.after_frame_id === selection.frame.key) : [];
        $("operation-history").hidden = history.length < 2;
        const previous = $("operation-history").value;
        $("operation-history").replaceChildren(...history.map((o, i) => new Option(`Essai ${i + 1} · ${phases[o.phase] || o.phase}`, o.id)));
        $("operation-history").value = selectedOperation || previous;
      }
      function paint() {
        document.querySelectorAll("#ij-frieze [data-ij-add]").forEach(b => {
          b.disabled = bridge.busy() || busy || !editable();
          b.title = editable() ? b.getAttribute("aria-label") : "Suspends le parcours et termine l’opération en cours pour ajouter une image";
        });
        const rows = operations().filter(op => !terminal(op));
        const journal = $("operations");
        journal.hidden = !rows.length;
        journal.replaceChildren(...rows.map(op => {
          const row = document.createElement("div"), button = document.createElement("button"), caption = document.createElement("span");
          row.className = "ij-operation-line";
          caption.textContent = `${op.kind === "hq" ? "Essai HQ" : op.kind === "insert" ? "Insertion" : "Ajout"} · ${op.action.title || op.intention} · ${op.status === "paused" ? "Suspendu" : phases[op.phase]}`;
          button.type = "button"; button.textContent = op.status === "paused" ? "Reprendre…" : "Voir";
          button.onclick = () => openOperation(op); row.append(caption, button); return row;
        }));
        paintDialog();
      }
      function card(frame, following, thumbnail) {
        const card = document.createElement("div"), plus = document.createElement("button");
        card.className = "ij-card"; card.append(thumbnail);
        plus.type = "button"; plus.className = "ij-add"; plus.dataset.ijAdd = ""; plus.textContent = "+";
        plus.setAttribute("aria-label", following ? `Insérer une étape après ${frame.title}` : "Ajouter une étape à la fin");
        plus.onclick = () => open(following ? "insert" : "append", frame, following);
        card.append(plus); return card;
      }
      async function submit(event) {
        event.preventDefault();
        if (busy || !selection || selection.kind === "hq") return;
        const target = {...selection}, value = $("operation-input").value.trim();
        if (!value) return error(target.kind === "hq" ? "Renseigne le prompt MiniMax." : "Décris l’état souhaité.");
        busy = true; error(""); command ||= bridge.commandId(); paint();
        try {
          const response = await bridge.api(url(target.projectId), "POST", {
            version:bridge.project().version, command, kind:target.kind, after_frame_id:target.frame.key,
            before_frame_id:target.following?.key || null, intention:target.kind === "hq" ? "" : value,
            prompt:target.kind === "hq" ? value : ""});
          if (bridge.project()?.id !== target.projectId) return;
          selectedOperation = response.project.image_operations.find(op => op.command === command)?.id || null;
          command = null; bridge.accept(response.project);
        } catch (e) {
          try {
            const response = await bridge.api("/projects/" + encodeURIComponent(target.projectId));
            if (bridge.project()?.id === target.projectId) bridge.accept(response.project);
          } catch (_) {}
          error(e.message);
        } finally { busy = false; paint(); }
      }
      async function control(action) {
        if (busy || !selection || !selectedOperation) return;
        const target = selection.projectId;
        busy = true; error(""); paint();
        try {
          const response = await bridge.api(url(target) + "/" + encodeURIComponent(selectedOperation) + "/" + action, "POST");
          if (bridge.project()?.id === target) bridge.accept(response.project);
        } catch (e) { error(e.message); }
        finally { busy = false; paint(); }
      }
      $("operation-form").addEventListener("submit", submit);
      $("operation-input").addEventListener("input", () => { command = null; });
      $("operation-close").onclick = () => dialog.close();
      $("operation-resume").onclick = () => control("resume");
      $("operation-cancel").onclick = () => control("cancel");
      $("operation-history").onchange = () => {
        const op = operations().find(o => o.id === $("operation-history").value);
        if (op) openOperation(op);
      };
      dialog.addEventListener("cancel", event => { if (busy) event.preventDefault(); });
      dialog.addEventListener("click", event => { if (event.target === dialog && !busy) dialog.close(); });
      return {card, paint, reset, pendingSequence:() => operations().some(op => op.kind !== "hq" && !terminal(op))};
    }
  };
})();
