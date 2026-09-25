(() => {
  "use strict";
  // Presentation only: all writes still use the existing workflow and validation gates.
  const statuses = Object.freeze({pending: ["○", "À préparer"], planned: ["◷", "Planifié"],
    running: ["●", "En cours"], approval: ["!", "À valider"], done: ["✓", "Terminé"],
    error: ["✕", "Erreur"], attention: ["!", "À examiner"]});
  const operationLabels = {compose: "Construction de l’histoire", edit_outline: "Relecture et ajustement de l’histoire",
    review_outline: "Relecture de l’histoire", repair_outline: "Correction de l’histoire", revise_outline: "Modification de l’histoire",
    develop: "Écriture des scènes", review_block: "Relecture des scènes et de leurs raccords",
    review_episode: "Relecture du scénario", repair_episode: "Correction du scénario", rewrite_episode: "Réécriture du scénario",
    discuss: "Réponse à ta question", revise: "Modification demandée"};
  function describe(project) {
    const doc = project?.document || {}, flow = project?.workflow || {}, job = project?.job || {};
    const status = project?.long_status || {}, outline = doc.series_outline, units = outline?.episodes || [];
    const unitName = project?.long_options?.delivery === "continuous" ? "Séquence" : "Épisode";
    const name = id => id === "outline" ? "L’histoire complète" : (() => {
      const index = units.findIndex(unit => unit.id === id);
      return index < 0 ? "Le scénario" : `${unitName} ${index + 1} · ${units[index].title}`;
    })();
    const approved = id => flow.mode !== "manual" || flow.status === "ready" ||
      (!!doc.reviews?.[id]?.source_hash && flow.approvals?.[id] === doc.reviews[id].source_hash);
    const storyDone = !!status.outline_reviewed && (approved("outline") ||
      (!doc.reviews?.outline?.source_hash && flow.wait_target !== "outline"));
    const unitStates = units.map(unit => ({id: unit.id, label: name(unit.id),
      written: !!doc.episode_scenarios?.[unit.id], ...status.units?.[unit.id]}));
    const allReady = units.length > 0 && unitStates.every(unit => unit.ready && approved(unit.id));
    const target = flow.wait_target || job.feedback_target?.unit_id ||
      (!storyDone ? "outline" : unitStates.find(unit => !unit.ready || !approved(unit.id))?.id || doc.selected_episode_id || "outline");
    const currentReview = status.reviews?.[target]?.current === true;
    const issues = currentReview ? (doc.reviews?.[target]?.issues || []).filter(issue => issue.severity === "blocking") : [];
    const active = ["running", "cancelling"].includes(job.status), running = active || flow.status === "running";
    let stage = !project ? "intention" : !storyDone ? "story" : "scenario";
    if (flow.wait_target) stage = flow.wait_target === "outline" ? "story" : "scenario";
    if (active && job.operation !== "discuss") {
      stage = ["compose", "outline", "edit_outline", "review_outline", "repair_outline", "revise_outline"].includes(job.operation)
        || job.feedback_target?.unit_id === "outline" ? "story" : "scenario";
    }
    const steps = {intention: project ? "done" : "pending", story: storyDone ? "done" : outline ? "planned" : "pending",
      scenario: allReady && storyDone ? "done" : unitStates.some(unit => unit.written) ? "planned" : "pending"};
    let title = "Ton intention", message = "Décris ce que tu veux raconter. L’histoire puis ses scènes seront développées à partir de ce point de départ.";
    let action = null, label = "", kind = "pending", secondary = null;
    if (project) {
      action = "advance"; label = !outline ? "Construire l’histoire" : !storyDone ? "Relire et poursuivre l’histoire" : "Poursuivre le scénario";
      title = !outline ? "Prêt à construire l’histoire" : !storyDone ? "La direction de l’histoire" : "Développer et vérifier les scènes";
      message = outline ? "Les textes sont enregistrés. Reprends le parcours pour effectuer les étapes encore nécessaires." : "La conception et sa relecture précèdent l’écriture des scènes.";
    }
    if (running) {
      kind = active ? "running" : "planned";
      if (job.operation !== "discuss" || !active) steps[stage] = kind;
      title = active ? operationLabels[job.operation] || "Écriture en cours" : "Prochaine étape planifiée";
      message = active ? job.phase || flow.message || "Le traitement continue en arrière-plan." : "Le parcours prépare le prochain traitement. Aucune validation n’est attendue.";
      if (active && job.phase === "Écriture du plan…" && job.reasoning && !job.draft) {
        message = "Le modèle raisonne ; le texte de l’histoire n’a pas encore été reçu.";
      }
      if (flow.pause_requested) message += " La pause prendra effet à la fin de l’appel actif.";
      action = null;
    } else if (["failed", "interrupted", "cancelled"].includes(job.status)) {
      kind = "error";
      if (job.operation !== "discuss") steps[stage] = "error";
      title = job.operation === "discuss" ? "L’échange s’est interrompu" : "Une étape s’est interrompue";
      message = job.revalidation_error || job.error || flow.message || "Le traitement n’a pas abouti.";
      if (!job.revalidation_error && job.error === "model returned an empty text response" && job.reasoning && !job.draft) {
        message = "Le modèle a transmis du raisonnement, puis le flux s’est terminé sans réponse finale. Aucune histoire n’a été reçue ; le raisonnement reste consultable ci-dessous.";
      }
      const recoverable = job.status === "failed" && !!job.draft?.trim() && job.can_revalidate !== false;
      action = recoverable ? "revalidate" : "retry";
      label = recoverable ? "Récupérer le brouillon · sans appel LLM" : "Relancer cette étape · appel LLM";
      secondary = "details";
    } else if (flow.status === "blocked") {
      kind = "attention"; steps[stage] = "attention";
      const unit = status.units?.[target];
      const canCorrect = target !== "outline" && issues.length > 0 && !!doc.episode_scenarios?.[target]
        && status.outline_reviewed && unit?.previous_ready && !unit.stale;
      title = issues.length ? `${issues.length} point${issues.length > 1 ? "s" : ""} à corriger pour continuer` : "Le parcours est arrêté";
      message = issues.length ? `${name(target)}. ${flow.repairs?.[target] ? "La correction précédente n’a pas suffi. " : ""}`
        + (canCorrect ? "Le bouton lance une correction des blocages, puis une relecture. Si tout est bon, le parcours reprend. Les observations facultatives ne sont pas à corriger automatiquement."
          : "Prépare la correction, puis envoie-la avec « Demander une modification ». Relire seul ne change pas le texte.")
        : flow.message || "Consulte les détails du dernier traitement avant de poursuivre.";
      action = canCorrect ? "correct-and-continue" : issues.length ? "feedback" : "advance";
      label = canCorrect ? "Corriger et continuer" : issues.length ? "Préparer la correction" : "Reprendre le parcours";
      secondary = canCorrect ? "feedback" : issues.length ? target === "outline" ? "review-outline" : "review-episode" : "details";
    } else if (flow.status === "awaiting_author") {
      kind = "approval"; steps[stage] = "approval";
      title = target === "outline" ? "La direction te convient ?" : `${name(target)} : à valider`;
      message = target === "outline" ? "Lis la progression et la fin. Tu peux en discuter, demander une modification ou valider cette direction."
        : "Cette séquence a été relue. Valide-la pour poursuivre, ou adresse un retour à une scène précise.";
      label = target === "outline" ? "Valider l’histoire et poursuivre" : "Valider cette séquence et poursuivre";
    } else if (allReady && storyDone) {
      kind = "done"; title = "Le scénario est prêt";
      message = "L’écriture et les vérifications sont terminées. Tu peux passer aux références et à la fabrication.";
      action = "validate"; label = "Préparer la fabrication";
    } else if (flow.status === "paused") {
      title = "Le parcours est en pause";
      message = "Tes textes sont conservés. Tu peux les parcourir, en discuter ou reprendre les étapes restantes.";
    }
    return {stage, steps, title, message, kind, action, label, secondary, target, issues, units: unitStates,
      saved: project ? job.draft && kind === "error" ? "Le brouillon reçu et les versions précédentes sont conservés."
        : "Les résultats reçus sont enregistrés. Changer d’étape ne lance aucun appel." : "",
      unitStatus(unit) {
        if (unit.stale) return ["attention", "À actualiser"];
        if (flow.wait_target === unit.id && kind === "approval") return ["approval", "À valider"];
        if (flow.wait_target === unit.id && kind === "attention") return ["attention", "À examiner"];
        const activeUnit = job.review_unit_ids?.includes(unit.id) || (!job.review_unit_ids?.length && doc.selected_episode_id === unit.id);
        if (active && stage === "scenario" && job.operation !== "discuss" && activeUnit) return ["running", operationLabels[job.operation] || "En cours"];
        if (kind === "error" && stage === "scenario" && job.operation !== "discuss" && activeUnit) return ["error", "Étape interrompue"];
        if (unit.ready) return ["done", "Relue"];
        return unit.written ? ["planned", "Écrite · à relire"] : [running ? "planned" : "pending", running ? "Planifiée" : "À écrire"];
      }};
  }
  window.PanelForgeStoryWriting = Object.freeze({describe, statuses});
})();
