(() => {
  "use strict";

  const core = window.PanelForgePromptLab;
  if (!core) return;
  const $ = (selector) => document.querySelector(selector);
  const state = {
    cookbooks: [],
    session: null,
    composition: null,
    busy: false,
    coreBusy: false,
    sourceSignature: "",
  };
  const elements = {
    workflow: $("#fighter-workflow"),
    workflowStatus: $("#fighter-workflow-status"),
    cookbook: $("#fighter-cookbook"),
    fighterA: $("#fighter-a-reference"),
    fighterB: $("#fighter-b-reference"),
    arena: $("#arena-reference"),
    mapping: $("#reference-plan-mapping"),
    referencePlan: stageElements("reference-plan", "reference_plan"),
    beatSheet: stageElements("beat-sheet", "beat_sheet"),
    finalPrompt: stageElements("final-prompt", "final_prompt"),
  };
  const stages = [elements.referencePlan, elements.beatSheet, elements.finalPrompt];

  function stageElements(prefix, key) {
    return {
      key,
      path: prefix,
      review: $(`#${prefix}-review`),
      generate: $(`#generate-${prefix}`),
      save: $(`#save-${prefix}`),
      approve: $(`#approve-${prefix}`),
      content: $(`#${prefix}-content`),
      message: $(`#${prefix}-message`),
      instruction: $(`#${prefix}-rewrite-instruction`),
      rewrite: $(`#rewrite-${prefix}`),
      revisionCount: $(`#${prefix}-revision-count`),
      revisionList: $(`#${prefix}-revision-list`),
      stream: {
        container: $(`#${prefix}-stream-state`),
        label: $(`#${prefix}-stream-label`),
        percent: $(`#${prefix}-stream-percent`),
        progress: $(`#${prefix}-stream-progress`),
      },
      lint: key === "final_prompt" ? $("#final-prompt-lint") : null,
      copy: key === "final_prompt" ? $("#copy-final-prompt") : null,
    };
  }

  function isBusy() {
    return state.busy || state.coreBusy;
  }

  async function initialize() {
    try {
      const payload = await core.request("/api/prompt-lab/cookbooks");
      state.cookbooks = (payload.cookbooks || []).filter(
        (cookbook) => cookbook.output_contract === "minimax.h3.ref2va",
      );
      elements.cookbook.replaceChildren();
      state.cookbooks.forEach((cookbook) => {
        const option = document.createElement("option");
        option.value = `${cookbook.id}@${cookbook.version}`;
        option.textContent = `${cookbook.display_name} · ${cookbook.version}`;
        option.dataset.cookbookId = cookbook.id;
        option.dataset.cookbookVersion = cookbook.version;
        elements.cookbook.append(option);
      });
      render();
    } catch (error) {
      elements.workflowStatus.textContent = "Cookbooks indisponibles";
      elements.referencePlan.message.className = "message error-text";
      elements.referencePlan.message.textContent = error.message;
    }
  }

  window.addEventListener("panelforge:prompt-session", (event) => {
    const nextSession = event.detail.session;
    const changedSession = (state.session && state.session.id) !== (nextSession && nextSession.id);
    state.session = nextSession;
    state.coreBusy = Boolean(event.detail.busy);
    if (changedSession) {
      state.composition = null;
      state.sourceSignature = "";
      [elements.fighterA, elements.fighterB, elements.arena].forEach((select) => {
        select.dataset.sessionId = "";
        select.dataset.bound = "";
      });
    }
    const signature = sessionSourceSignature(nextSession);
    if (nextSession && signature !== state.sourceSignature) {
      state.sourceSignature = signature;
      loadComposition(nextSession.id);
    }
    render();
  });

  function sessionSourceSignature(session) {
    if (!session) return "";
    const references = session.references.map((reference) => (
      `${reference.id}@${reference.active_revision_id}:${reference.uses.join(",")}`
      + `:interpretation=${reference.approved_interpretation_id || "none"}`
    )).join("|");
    return `${session.id}:${session.approved_brief_revision_id || "none"}:${references}`;
  }

  async function loadComposition(sessionId) {
    const requestedSignature = state.sourceSignature;
    try {
      const payload = await core.request(`/api/prompt-lab/sessions/${sessionId}/composition`);
      if (
        state.session
        && state.session.id === sessionId
        && state.sourceSignature === requestedSignature
      ) {
        state.composition = payload.composition;
        render();
      }
    } catch (error) {
      if (state.session && state.session.id === sessionId) {
        state.sourceSignature = "";
        elements.referencePlan.message.className = "message error-text";
        elements.referencePlan.message.textContent = error.message;
      }
    }
  }

  function selectedCookbook() {
    const option = elements.cookbook.selectedOptions[0];
    if (!option) return null;
    return state.cookbooks.find(
      (cookbook) => cookbook.id === option.dataset.cookbookId
        && cookbook.version === option.dataset.cookbookVersion,
    ) || null;
  }

  function selectedSlots() {
    const cookbook = selectedCookbook();
    return [
      ["fighter_a", "Combattant A", elements.fighterA],
      ["fighter_b", "Combattant B", elements.fighterB],
      ["arena", "Arène", elements.arena],
    ].map(([slotId, label, select], index) => {
      const slot = cookbook && cookbook.slots.find((item) => item.id === slotId);
      const reference = state.session
        && state.session.references.find((item) => item.id === select.value);
      const requiredUses = !slot || !slot.required_uses
        ? []
        : Array.isArray(slot.required_uses) ? slot.required_uses : [slot.required_uses];
      const referenceUses = reference && Array.isArray(reference.uses) ? reference.uses : [];
      return {
        slotId,
        label,
        localPictureNumber: index + 1,
        slot,
        reference,
        referenceId: select.value,
        missingUses: requiredUses.filter((use) => !referenceUses.includes(use)),
      };
    });
  }

  function mappingState() {
    const cookbook = selectedCookbook();
    const slots = selectedSlots();
    const complete = Boolean(cookbook && slots.every((slot) => slot.referenceId));
    const distinct = complete && new Set(slots.map((slot) => slot.referenceId)).size === slots.length;
    const compatible = complete && slots.every((slot) => !slot.missingUses.length);
    return {
      cookbook,
      slots,
      complete,
      distinct,
      compatible,
      ready: complete && distinct && compatible,
    };
  }

  function binding(slotId) {
    const values = state.composition && state.composition.bindings
      ? state.composition.bindings[slotId]
      : null;
    return values && values.length ? values[0] : "";
  }

  function populateSlot(select, slotId, fallbackIndex) {
    if (!state.session) return;
    const bound = binding(slotId);
    const sessionChanged = select.dataset.sessionId !== state.session.id;
    const wrongSize = select.options.length !== state.session.references.length + 1;
    if (sessionChanged || wrongSize) {
      select.replaceChildren();
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Choisir une image…";
      select.append(empty);
      state.session.references.forEach((reference, index) => {
        const option = document.createElement("option");
        option.value = reference.id;
        option.textContent = `<Image ${index + 1}> · ${reference.label}`;
        select.append(option);
      });
      select.value = bound || (state.session.references[fallbackIndex] || {}).id || "";
      select.dataset.sessionId = state.session.id;
      select.dataset.bound = bound;
    } else if (select.dataset.bound !== bound) {
      if (bound) select.value = bound;
      select.dataset.bound = bound;
    }
  }

  function render() {
    if (!state.session || !elements.workflow) return;
    const busy = isBusy();
    const briefReady = state.session.brief_complete;
    const enoughReferences = state.session.references.length >= 3;
    if (state.composition) {
      const value = `${state.composition.cookbook.id}@${state.composition.cookbook.version}`;
      if (elements.cookbook.dataset.bound !== value) {
        elements.cookbook.value = value;
        elements.cookbook.dataset.bound = value;
      }
    }
    populateSlot(elements.fighterA, "fighter_a", 0);
    populateSlot(elements.fighterB, "fighter_b", 1);
    populateSlot(elements.arena, "arena", 2);
    elements.cookbook.disabled = busy || !briefReady || !state.cookbooks.length;
    [elements.fighterA, elements.fighterB, elements.arena].forEach((select) => {
      select.disabled = busy || !briefReady || !enoughReferences;
    });
    const mapping = mappingState();
    const mappingReady = mapping.ready;
    const mappingsMatch = Boolean(state.composition && mappingReady
      && state.composition.cookbook.id === mapping.cookbook.id
      && state.composition.cookbook.version === mapping.cookbook.version
      && binding("fighter_a") === elements.fighterA.value
      && binding("fighter_b") === elements.fighterB.value
      && binding("arena") === elements.arena.value);
    elements.workflowStatus.textContent = !briefReady
      ? "Brief requis"
      : !enoughReferences ? "3 images requises"
        : !mapping.complete ? "Affectations à compléter"
          : !mapping.distinct ? "Images distinctes requises"
            : !mapping.compatible ? "Usages incompatibles"
        : state.composition && !mappingsMatch ? "Affectations modifiées"
          : state.composition ? "Cookbook configuré" : "Prêt à configurer";
    elements.workflowStatus.className = `review-pill ${state.composition && mappingsMatch ? "approved" : "pending"}`;
    renderMapping(mapping);

    stages.forEach((stage, index) => {
      const stageDocument = state.composition && state.composition.documents
        ? state.composition.documents[stage.key]
        : null;
      const activeId = stageDocument ? stageDocument.active_revision_id : null;
      const hydrationKey = `${state.session.id}:${activeId || "none"}`;
      if (stage.content.dataset.hydrationKey !== hydrationKey) {
        stage.content.value = stageDocument ? (stageDocument.active_content || "") : "";
        stage.content.dataset.hydrationKey = hydrationKey;
      }
      const upstreamReady = index === 0
        ? briefReady && enoughReferences && mappingReady
        : Boolean(mappingsMatch && state.composition
          && state.composition.documents[stages[index - 1].key].complete);
      const activeContent = stageDocument ? (stageDocument.active_content || "") : "";
      const draftChanged = Boolean(stageDocument)
        && stage.content.value.trim() !== activeContent.trim();
      const stale = Boolean(stageDocument && stageDocument.stale);
      const complete = Boolean(stageDocument && stageDocument.complete);
      const errors = stageDocument ? stageDocument.validation_errors : [];
      stage.content.disabled = busy || !stageDocument || !upstreamReady || !mappingsMatch;
      stage.generate.disabled = busy || !upstreamReady;
      stage.generate.textContent = stageDocument && activeId
        ? (stage.key === "final_prompt" ? "Recompiler le prompt" : "Régénérer")
        : (stage.key === "reference_plan" ? "Générer le plan"
          : stage.key === "beat_sheet" ? "Générer la beat sheet" : "Compiler le prompt");
      stage.save.disabled = busy || !stageDocument || !upstreamReady || !mappingsMatch
        || !stage.content.value.trim() || !draftChanged;
      stage.approve.disabled = busy || !mappingsMatch || !stageDocument || !activeId || stale
        || complete || draftChanged || Boolean(errors.length);
      stage.instruction.disabled = busy || !mappingsMatch || !stageDocument || !activeId || stale;
      stage.rewrite.disabled = busy || !mappingsMatch || !stageDocument || !activeId || stale
        || draftChanged || !stage.instruction.value.trim();
      stage.review.textContent = complete ? "Validé"
        : stale ? "Obsolète"
          : activeId ? "À valider"
            : (stageDocument && stageDocument.blocked_reason ? "Étape précédente requise" : "À générer");
      stage.review.className = `review-pill ${complete ? "approved" : "pending"}`;
      stage.revisionCount.textContent = stageDocument ? String(stageDocument.revisions.length) : "0";
      stage.revisionList.replaceChildren();
      [...(stageDocument ? stageDocument.revisions : [])].reverse().forEach((revision) => {
        stage.revisionList.append(revisionItem(revision));
      });
    });
    renderFinalLint(mappingsMatch);
  }

  function revisionItem(revision) {
    const item = document.createElement("li");
    const title = document.createElement("b");
    title.textContent = `${revision.origin} · ${revision.id.slice(-8)}`;
    const content = document.createElement("p");
    content.textContent = revision.instruction || revision.content.slice(0, 180);
    item.append(title, content);
    return item;
  }

  function useLabel(use) {
    return ({ subject: "sujet", environment: "décor", style: "style" })[use] || use;
  }

  function renderMapping(mapping) {
    elements.mapping.replaceChildren();
    if (!mapping.complete || !state.session) {
      const hint = document.createElement("small");
      hint.textContent = "Choisissez trois images distinctes pour afficher le mapping déterministe.";
      elements.mapping.append(hint);
      return;
    }
    if (!mapping.distinct) {
      const hint = document.createElement("small");
      hint.className = "warning-text";
      hint.textContent = "Chaque rôle doit utiliser une image distincte.";
      elements.mapping.append(hint);
      return;
    }
    mapping.slots.forEach(({ referenceId, localPictureNumber, slot, label }) => {
      const globalImageNumber = state.session.references.findIndex((item) => item.id === referenceId) + 1;
      const subject = slot ? slot.subject_label : null;
      const line = document.createElement("code");
      line.textContent = subject
        ? `<Image ${globalImageNumber}> → <Picture ${localPictureNumber}> → ${subject} · ${label}`
        : `<Image ${globalImageNumber}> → <Picture ${localPictureNumber}> · ${label}`;
      elements.mapping.append(line);
    });
    mapping.slots.filter((slot) => slot.missingUses.length).forEach((slot) => {
      const globalImageNumber = state.session.references.findIndex(
        (item) => item.id === slot.referenceId,
      ) + 1;
      const warning = document.createElement("small");
      warning.className = "warning-text";
      const expectedUses = slot.missingUses
        .map((use) => `« ${useLabel(use)} »`)
        .join(" et ");
      warning.textContent = `${slot.label} : <Image ${globalImageNumber}> doit avoir l’usage ${expectedUses}. Modifiez ses usages dans le Brief ou choisissez une autre image.`;
      elements.mapping.append(warning);
    });
  }

  function renderFinalLint(mappingsMatch) {
    const stageDocument = state.composition && state.composition.documents
      ? state.composition.documents.final_prompt
      : null;
    const errors = stageDocument ? stageDocument.validation_errors : [];
    const warnings = stageDocument ? stageDocument.validation_warnings : [];
    const activeContent = stageDocument ? (stageDocument.active_content || "") : "";
    const draftChanged = Boolean(stageDocument)
      && elements.finalPrompt.content.value.trim() !== activeContent.trim();
    elements.finalPrompt.lint.replaceChildren();
    const line = document.createElement(errors.length || warnings.length ? "ul" : "small");
    if (draftChanged) {
      line.textContent = "Brouillon local non enregistré : la validation affichée ne sera recalculée qu’à l’enregistrement.";
    } else if (!stageDocument || !stageDocument.active_revision_id) {
      line.textContent = "Les contrôles de structure apparaîtront ici après compilation.";
    } else if (!errors.length && !warnings.length) {
      line.textContent = "Structure Ref2VA valide : sections, labels et timestamps contrôlés.";
    } else {
      errors.forEach((error) => {
        const item = document.createElement("li");
        item.textContent = error;
        line.append(item);
      });
      warnings.forEach((warning) => {
        const item = document.createElement("li");
        item.textContent = `Avertissement : ${warning}`;
        line.append(item);
      });
    }
    elements.finalPrompt.lint.append(line);
    elements.finalPrompt.copy.disabled = isBusy()
      || !mappingsMatch
      || draftChanged
      || !stageDocument
      || !stageDocument.complete
      || stageDocument.stale
      || Boolean(errors.length);
  }

  async function configure() {
    if (!state.session) throw new Error("Aucune session active.");
    const cookbook = selectedCookbook();
    if (!cookbook) throw new Error("Aucun cookbook disponible.");
    const payload = await core.request(
      `/api/prompt-lab/sessions/${state.session.id}/composition`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookbook_id: cookbook.id,
          cookbook_version: cookbook.version,
          bindings: {
            fighter_a: [elements.fighterA.value],
            fighter_b: [elements.fighterB.value],
            arena: [elements.arena.value],
          },
        }),
      },
    );
    state.composition = payload.composition;
  }

  async function action(stage, actionName, payload = null) {
    if (!state.session || !state.composition) return;
    stage.message.className = "message";
    stage.message.textContent = "Traitement en cours…";
    setBusy(true);
    try {
      const response = await core.request(
        `/api/prompt-lab/sessions/${state.session.id}/${stage.path}/${actionName}`,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
      );
      state.composition = response.composition;
      stage.message.textContent = actionName === "approve"
        ? "Étape validée."
        : "Nouvelle révision enregistrée.";
    } catch (error) {
      stage.message.className = "message error-text";
      stage.message.textContent = error.message;
    } finally {
      setBusy(false);
      render();
    }
  }

  async function streamStage(stage, revision = false) {
    if (!state.session) return;
    let result = null;
    setBusy(true);
    try {
      if (stage.key === "reference_plan" && !revision) await configure();
      if (!state.composition) throw new Error("Configurez d’abord le cookbook.");
      result = await streamEditor({
        url: `/api/prompt-lab/sessions/${state.session.id}/${stage.path}/${revision ? "revise" : "generate"}/stream`,
        payload: revision ? { instruction: stage.instruction.value.trim() } : null,
        stage,
        completedMessage: revision
          ? "Révision générée et enregistrée."
          : "Étape générée et enregistrée.",
      });
      if (revision && !result.truncated) stage.instruction.value = "";
    } catch (error) {
      stage.message.className = "message error-text";
      stage.message.textContent = error.message;
    } finally {
      setBusy(false);
      if (result && result.truncated) {
        stage.content.value = result.partialContent;
      }
      render();
    }
  }

  async function streamEditor({ url, payload, stage, completedMessage }) {
    const previousContent = stage.content.value;
    let completed = false;
    let truncated = false;
    let partialContent = "";
    let truncation = null;
    let receivedText = false;
    stage.message.className = "message";
    stage.message.textContent = "";
    stage.content.value = "";
    core.updateStreamState(stage.stream, {
      phase: "preparing",
      text: "Préparation ou chargement du modèle…",
      progress: null,
    });
    try {
      await core.streamRequest(
        url,
        {
          method: "POST",
          headers: payload ? { "Content-Type": "application/json" } : undefined,
          body: payload ? JSON.stringify(payload) : undefined,
        },
        (event) => {
          core.updateStreamState(stage.stream, event);
          if (event.kind === "delta" && event.text) {
            receivedText = true;
            stage.content.value += event.text;
            stage.content.scrollTop = stage.content.scrollHeight;
          }
          if (event.kind === "completed" && event.composition) {
            state.composition = event.composition;
            completed = true;
          }
          if (event.kind === "truncated") {
            truncated = true;
            truncation = event;
            partialContent = stage.content.value || event.text || "";
          }
        },
      );
      if (truncated) {
        const budget = Number.isInteger(truncation && truncation.max_tokens)
          ? truncation.max_tokens.toLocaleString("fr-FR")
          : "configuré";
        stage.message.className = "message warning-text";
        stage.message.textContent = `Réponse tronquée : le budget de ${budget} tokens a été épuisé. Le texte partiel n’a pas été enregistré automatiquement.`;
        return { truncated: true, partialContent };
      }
      if (!completed) throw new Error("Le flux s’est terminé sans composition persistée.");
      stage.content.scrollTop = 0;
      stage.message.textContent = completedMessage;
      return { truncated: false, partialContent: "" };
    } catch (error) {
      if (!receivedText) stage.content.value = previousContent;
      stage.message.className = "message error-text";
      stage.message.textContent = receivedText
        ? `${error.message} Le candidat imparfait reste disponible comme brouillon local.`
        : error.message;
      core.failStreamState(stage.stream, error.message);
      throw error;
    }
  }

  function setBusy(value) {
    state.busy = value;
    core.setBusy(value);
    render();
  }

  [elements.cookbook, elements.fighterA, elements.fighterB, elements.arena]
    .forEach((control) => control.addEventListener("change", render));
  stages.forEach((stage) => {
    stage.content.addEventListener("input", render);
    stage.instruction.addEventListener("input", render);
    stage.generate.addEventListener("click", () => streamStage(stage));
    stage.save.addEventListener("click", () => action(
      stage,
      "edit",
      { content: stage.content.value.trim() },
    ));
    stage.approve.addEventListener("click", () => action(stage, "approve"));
    stage.rewrite.addEventListener("click", () => streamStage(stage, true));
  });
  elements.finalPrompt.copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(elements.finalPrompt.content.value);
      elements.finalPrompt.message.className = "message";
      elements.finalPrompt.message.textContent = "Prompt copié dans le presse-papiers.";
    } catch (_) {
      elements.finalPrompt.content.select();
      elements.finalPrompt.message.className = "message warning-text";
      elements.finalPrompt.message.textContent = "Copie automatique indisponible : utilisez Ctrl+C.";
    }
  });

  initialize();
})();
