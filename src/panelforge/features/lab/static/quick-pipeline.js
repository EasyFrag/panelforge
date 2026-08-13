(() => {
  "use strict";

  const storagePrefix = "panelforge.quick-mode.v1:";
  const directSteps = [
    { id: "brief-generate", label: "Génération du Brief", complete: "briefGenerated", action: "generateBrief" },
    { id: "brief-approve", label: "Validation du Brief", complete: "briefApproved", action: "approveBrief" },
    { id: "plan-generate", label: "Génération du Plan", complete: "planGenerated", action: "generatePlan" },
    { id: "plan-approve", label: "Validation du Plan", complete: "planApproved", action: "approvePlan" },
    { id: "prompt-generate", label: "Génération du Prompt MiniMax", complete: "promptGenerated", action: "generatePrompt" },
    { id: "prompt-approve", label: "Validation du Prompt MiniMax", complete: "promptApproved", action: "approvePrompt" },
  ];

  function storageKey(sessionId) {
    return `${storagePrefix}${sessionId}`;
  }

  function persist(record) {
    try { window.localStorage.setItem(storageKey(record.sessionId), JSON.stringify(record)); } catch (_) { /* optional recovery */ }
    return record;
  }

  function publish(sessionId, status, step, error, onState) {
    const record = persist({
      sessionId,
      status,
      stepId: step ? step.id : null,
      stepLabel: step ? step.label : null,
      error: error || null,
      updatedAt: new Date().toISOString(),
    });
    if (onState) onState(record);
    return record;
  }

  function load(sessionId) {
    let record = null;
    try { record = JSON.parse(window.localStorage.getItem(storageKey(sessionId)) || "null"); } catch (_) { record = null; }
    if (!record || record.sessionId !== sessionId) return null;
    if (record.status === "running") {
      return persist({
        ...record,
        status: "interrupted",
        error: "Le parcours a été interrompu avant la fin de cette étape.",
        updatedAt: new Date().toISOString(),
      });
    }
    return record;
  }

  async function runDirect({ sessionId, snapshot, actions, isCurrent, onState }) {
    for (const step of directSteps) {
      if (!isCurrent()) {
        return publish(sessionId, "stopped", step, "La session active a changé.", onState);
      }
      if (snapshot()[step.complete]) continue;
      publish(sessionId, "running", step, null, onState);
      try {
        if (typeof actions[step.action] !== "function") {
          throw new Error(`Action Quick mode absente : ${step.action}`);
        }
        const succeeded = await actions[step.action]();
        if (succeeded !== true) throw new Error(`${step.label} a échoué.`);
        if (!isCurrent()) throw new Error("La session active a changé.");
        if (!snapshot()[step.complete]) {
          throw new Error(`${step.label} n’a pas produit un état persistant valide.`);
        }
      } catch (error) {
        return publish(
          sessionId,
          "stopped",
          step,
          error instanceof Error ? error.message : String(error),
          onState,
        );
      }
    }
    return publish(sessionId, "completed", null, null, onState);
  }

  window.PanelForgeQuickPipeline = Object.freeze({
    load,
    runDirect,
  });
})();
