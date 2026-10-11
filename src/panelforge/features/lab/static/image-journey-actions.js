(() => {
  "use strict";
  window.PanelForgeJourneyActions = {
    attach(bridge) {
      const $ = id => document.getElementById("ij-" + id);
      const dialog = $("operation"), terminal = op => ["completed", "cancelled"].includes(op.status);
      const phases = {planning:"Préparation de la transformation", prompting:"Préparation du prompt", queueing:"Mise en file",
        rendering:"Génération", protecting:"Préservation du décor", reviewing:"Relecture", completed:"Terminé", cancelled:"Abandonné"};
      let selection = null, busy = false, command = null, selectedOperation = null, resultKey = "";
      const resolutionCommands = new Map();
      const blockedImages = () => bridge.project()?.blocked_images || [];
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
      function inputImages(kind, frame, following) {
        if (kind === "hq") return [image(frame, "Original")];
        if (kind === "prepend") return [image(frame, bridge.reversedOrder() ? "Dernière image" : "Première image")];
        if (!following) return [image(frame, bridge.reversedOrder() ? "Première image" : "Dernière image")];
        const pair = bridge.reversedOrder() ? [following, frame] : [frame, following];
        return [image(pair[0], "État précédent conservé"), image(pair[1], "État suivant conservé")];
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
          : kind === "insert" ? "Une image entre ces deux états. La suite est conservée."
          : kind === "prepend" ? `Une nouvelle image placée ${bridge.reversedOrder() ? "après" : "avant"} cet état. L’image fournie reste intacte.`
          : bridge.reversedOrder() ? "Une nouvelle image placée avant cet état dans la frise." : "Une nouvelle image depuis cet état.";
        $("operation-images").replaceChildren(...inputImages(kind, frame, following));
        $("operation-result").replaceChildren();
        paintDialog();
        if (!dialog.open) dialog.showModal();
        if (!operation) $("operation-input").focus();
      }
      function openOperation(operation) {
        const frames = bridge.frames(), frame = frames.find(f => f.key === (operation.after_frame_id || operation.before_frame_id));
        if (!frame) return;
        const following = operation.kind === "insert" ? frames.find(f => f.key === operation.before_frame_id) : null;
        open(operation.kind, frame, following, operation);
      }
      function paintDialog() {
        if (!selection) return;
        if (selection.projectId !== bridge.project()?.id) return reset();
        let op = operations().find(op => op.id === selectedOperation);
        if (op?.replacement_id) {
          selectedOperation = op.replacement_id;
          op = operations().find(item => item.id === selectedOperation);
          resultKey = ""; $("operation-result").replaceChildren(); error("");
        }
        const resolving = blockedImages().some(item => item.step_id === op?.id);
        const active = op && !terminal(op), blocked = pending() || selection.kind !== "hq" && !editable();
        $("operation-input").readOnly = !!active || busy || bridge.busy() || selection.kind === "hq";
        $("operation-generate").hidden = selection.kind === "hq" || !!active || !!op;
        $("operation-generate").disabled = busy || bridge.busy() || blocked;
        $("operation-generate").textContent = "Générer";
        $("operation-resume").hidden = op?.status !== "paused" || resolving;
        $("operation-cancel").hidden = op?.status !== "paused";
        $("operation-resume").disabled = busy || bridge.busy();
        $("operation-cancel").disabled = busy || bridge.busy() || op?.phase === "rendering";
        $("operation-close").disabled = busy || bridge.busy();
        $("operation-status").textContent = op ? (op.status === "paused" ? "Suspendu · " : "") + (phases[op.phase] || op.phase) : "";
        if (op?.attempt_history?.length && !op.output_asset_id) {
          $("operation-status").textContent = op.status === "paused" ? "Correction suspendue" : "Correction en cours";
        }
        if (op?.error) error(op.error);
        else if (op) error("");
        paintResolution($("operation-resolution"), op?.id);
        const key = op?.output_asset_id || op?.attempt_history?.at(-1)?.output_asset_id || "";
        const resultSignature = JSON.stringify([key, op?.output_asset_id, op?.attempt_history?.length, op?.review]);
        if (resultSignature !== resultKey) {
          resultKey = resultSignature;
          $("operation-result").replaceChildren();
          if (!key) {
            $("operation-images").replaceChildren(...inputImages(selection.kind, selection.frame, selection.following));
          }
          if (key) {
            const frame = {key:op.id, step:op, asset_id:key, index:0, title:selection.kind === "hq" ? "Version HQ" : "Nouvelle image"};
            if (selection.kind === "hq") {
              $("operation-images").replaceChildren(image(selection.frame, "Original"), image(frame, "Version HQ ×2"));
            } else {
              $("operation-result").append(image(frame, "Nouvelle image"));
            }
            const link = document.createElement("a");
            link.href = bridge.asset(key); link.download = `${selection.kind}-${op.id}.png`;
            link.textContent = selection.kind === "hq" ? "Télécharger la version HQ" : "Télécharger l’image";
            $("operation-result").append(link);
            if (op.attempt_history?.length) {
              const trials = document.createElement("button");
              trials.type = "button"; trials.className = "ij-attempts-link";
              trials.textContent = `${op.attempt_history.length + (op.retained_attempt_index == null ? 1 : 0)} essais`;
              trials.onclick = () => bridge.showImage(frame);
              $("operation-result").append(trials);
            }
          }
        }
        $("operation-review").textContent = (op?.user_acceptance ? "Acceptée manuellement · " : "") + (op?.review?.observation || "");
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
        document.querySelectorAll("[data-ij-resolution-step]").forEach(node => paintResolution(node,
          node.dataset.ijResolutionStep, node.dataset.ijResolutionAsset || null));
        paintDialog();
      }
      function paintResolution(node, stepId, outputAssetId=null) {
        if (!node) return;
        let target = blockedImages().find(item => item.step_id === stepId);
        const previous = !!target && !!outputAssetId && target.output_asset_id !== outputAssetId;
        if (previous) {
          target = target.accept_previous_asset_ids?.includes(outputAssetId)
            ? {...target, output_asset_id:outputAssetId, accept_label:target.accept_label === "Accepter l’image"
                ? "Accepter cet essai" : target.accept_label.replace("Accepter", "Accepter cet essai")}
            : null;
        }
        const disabled = busy || bridge.busy() || !target?.available;
        const key = JSON.stringify([target, disabled]);
        node.dataset.ijResolutionStep = stepId || "";
        node.dataset.ijResolutionAsset = outputAssetId || "";
        if (node.dataset.resolutionState === key) return;
        node.dataset.resolutionState = key; node.replaceChildren(); node.hidden = !target;
        if (!target) return;
        const choices = previous ? [["accept", target.accept_label]] : [["regenerate", "Régénérer"], ["accept", target.accept_label]];
        for (const [action, label] of choices) {
          const button = document.createElement("button");
          button.type = "button"; button.textContent = label; button.dataset.ijResolve = action;
          button.disabled = disabled;
          button.title = !target.available ? "Termine ou abandonne l’opération en cours."
            : action === "regenerate" ? "Refaire cette étape depuis sa source, en corrigeant le motif du rejet." : "Conserver cette image malgré le diagnostic.";
          button.onclick = () => resolve(target, action); node.append(button);
        }
      }
      async function resolve(target, action) {
        if (busy || bridge.busy()) return;
        const projectId = bridge.project().id;
        const key = JSON.stringify([projectId, target.step_id, target.output_asset_id, action]);
        if (!resolutionCommands.has(key)) resolutionCommands.set(key, bridge.commandId());
        await bridge.run(async () => {
          try {
            const response = await bridge.api("/projects/" + encodeURIComponent(projectId) + "/image-resolutions", "POST", {
              version:bridge.project().version, command:resolutionCommands.get(key), action,
              step_id:target.step_id, output_asset_id:target.output_asset_id});
            resolutionCommands.delete(key);
            if (bridge.project()?.id !== projectId) return;
            if ($("detail").open) $("detail").close();
            bridge.accept(response.project);
          } catch (e) { if (dialog.open) error(e.message); throw e; }
        });
      }
      function card(frame, following, thumbnail, first=false) {
        const card = document.createElement("div"), plus = document.createElement("button");
        card.className = "ij-card"; card.append(thumbnail);
        plus.type = "button"; plus.className = "ij-add"; plus.dataset.ijAdd = ""; plus.textContent = "+";
        plus.setAttribute("aria-label", following ? `Insérer une étape entre ${frame.title} et ${following.title}`
          : bridge.reversedOrder() ? "Ajouter une étape au début de la frise" : "Ajouter une étape à la fin");
        plus.onclick = () => open(following ? "insert" : "append", frame, following);
        if (bridge.reversedOrder()) card.prepend(plus); else card.append(plus);
        if (first && bridge.spec()?.prepend_images) {
          const head = document.createElement("button");
          head.type = "button"; head.className = "ij-add ij-add-head";
          head.dataset.ijAdd = ""; head.dataset.ijBoundary = "head"; head.textContent = "+";
          head.setAttribute("aria-label", bridge.reversedOrder() ? "Ajouter une étape à la fin de la frise" : "Ajouter une étape au début de la frise");
          head.onclick = () => open("prepend", frame);
          card.classList.add("ij-head"); card.append(head);
        }
        const resolution = document.createElement("div");
        resolution.className = "ij-resolution";
        paintResolution(resolution, frame.key); card.append(resolution);
        return card;
      }
      async function submit(event) {
        event.preventDefault();
        if (busy || bridge.busy() || !selection || selection.kind === "hq") return;
        const target = {...selection}, value = $("operation-input").value.trim();
        if (!value) return error(target.kind === "hq" ? "Renseigne le prompt MiniMax." : "Décris l’état souhaité.");
        busy = true; error(""); command ||= bridge.commandId(); paint();
        try {
          const response = await bridge.api(url(target.projectId), "POST", {
            version:bridge.project().version, command, kind:target.kind, after_frame_id:target.kind === "prepend" ? null : target.frame.key,
            before_frame_id:target.kind === "prepend" ? target.frame.key : target.following?.key || null, intention:target.kind === "hq" ? "" : value,
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
        if (busy || bridge.busy() || !selection || !selectedOperation) return;
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
      return {card, paint, paintResolution, openOperation, reset, pendingSequence:() => operations().some(op => op.kind !== "hq" && !terminal(op))};
    }
  };
})();
