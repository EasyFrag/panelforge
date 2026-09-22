(() => {
  "use strict";

  const labels = {
    local_gpu: "Machine locale",
    remote_gpu: "Serveur distant",
    llm: "LLM",
    dlss: "DLSS",
    image_render: "Image",
    video_render: "Vidéo",
  };
  let status = null;
  let saving = false;
  let notices = [];
  const minimizedStorageKey = "panelforge.workQueue.minimized";
  let minimized = false;
  try {
    minimized = window.localStorage.getItem(minimizedStorageKey) === "true";
  } catch (_) {
    minimized = false;
  }

  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      ...options,
      headers: {Accept: "application/json", ...(options.headers || {})},
    });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : `Erreur HTTP ${response.status}`);
    return value;
  };

  const dialog = document.createElement("dialog");
  dialog.className = "work-queue-dialog";
  dialog.innerHTML = `
    <div class="work-queue-head">
      <div><small>ORDONNANCEUR PANELFORGE</small><h2>Traitements</h2></div>
      <button type="button" data-close aria-label="Fermer">×</button>
    </div>
    <p class="muted">Une tâche au maximum par machine. Les files locale et distante restent indépendantes.</p>
    <p data-error class="error-text" role="alert"></p>
    <div class="work-queue-lanes" data-lanes></div>
    <details class="work-queue-settings">
      <summary>Paramètres globaux des machines</summary>
      <form data-settings-form>
        <div class="work-queue-settings-grid">
          <label>Pause thermique à partir de °C<input name="stop_temperature_c" type="number" min="30" max="110" step="1" required></label>
          <label>Reprise sous °C<input name="resume_temperature_c" type="number" min="15" max="109" step="1" required></label>
          <label>Stabilisation thermique<input name="cooldown_seconds" type="number" min="0" max="86400" step="1" required><small>secondes</small></label>
          <label>Repos entre vidéos<input name="remote_video_cooldown_seconds" type="number" min="0" max="3600" step="1" required><small>secondes</small></label>
          <label>Historique visible<input name="history_limit" type="number" min="5" max="200" step="1" required><small>traitements</small></label>
        </div>
        <div class="work-queue-checks">
          <label><input name="monitor_local" type="checkbox"> Surveiller la température locale</label>
          <label><input name="monitor_remote" type="checkbox"> Surveiller la température distante</label>
          <label><input name="pause_when_unavailable" type="checkbox"> Suspendre si la température est indisponible</label>
          <label><input name="pause_after_failure" type="checkbox"> Suspendre la file après une erreur non interceptée</label>
        </div>
        <button class="primary" type="submit">Enregistrer les paramètres globaux</button>
      </form>
    </details>
    <details class="work-queue-history"><summary>Derniers traitements</summary><div data-history></div></details>`;
  document.body.append(dialog);

  const floating = document.createElement("aside");
  floating.className = "work-queue-background";
  floating.innerHTML = `
    <div class="work-queue-compact-head">
      <strong>Traitements</strong>
      <div class="work-queue-compact-actions">
        <button type="button" data-open>Détails</button>
        <button type="button" data-minimize aria-label="Minimiser le suivi des traitements" title="Minimiser">−</button>
      </div>
    </div>
    <div class="work-queue-compact-lanes" data-compact></div>
    <div data-notices></div>
    <button class="work-queue-minimized" type="button" data-restore aria-label="Agrandir le suivi des traitements" title="Agrandir le suivi"></button>`;
  document.body.append(floating);
  floating.classList.toggle("minimized", minimized);

  const form = dialog.querySelector("[data-settings-form]");
  const field = name => form.elements.namedItem(name);
  const error = dialog.querySelector("[data-error]");

  const activityName = activity => activity?.operation || labels[activity?.workload] || "Traitement";
  const percent = activity => activity?.progress == null ? null : Math.round(Number(activity.progress) * 100);
  const stateLabel = machine => machine?.state === "cooling" ? "Cooldown"
    : machine?.active || machine?.state === "busy" ? "Working"
    : machine?.paused ? "Paused"
    : machine?.state === "hot" ? "Hot"
    : machine?.state === "unavailable" ? "Unavailable"
    : Number(machine?.queue_count || 0) > 0 ? "Working" : "Ready";

  const stateTone = machine => machine?.state === "cooling" ? "cooling"
    : machine?.active || machine?.state === "busy" ? "busy"
    : machine?.paused ? "paused"
    : machine?.state === "hot" || machine?.state === "unavailable" ? "unavailable"
    : Number(machine?.queue_count || 0) > 0 ? "busy" : "idle";

  function setMinimized(value) {
    minimized = Boolean(value);
    floating.classList.toggle("minimized", minimized);
    try {
      window.localStorage.setItem(minimizedStorageKey, String(minimized));
    } catch (_) {
      // The monitor still works when storage is disabled by the browser.
    }
  }

  function minimizedIcon(resource) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    svg.innerHTML = resource === "local_gpu"
      ? '<rect x="3" y="4" width="18" height="13" rx="2"></rect><path d="M8 21h8M12 17v4"></path>'
      : '<path d="M7.5 18H18a4 4 0 0 0 .6-7.96A6.5 6.5 0 0 0 6.2 8.5 4.75 4.75 0 0 0 7.5 18Z"></path>';
    return svg;
  }

  function minimizedLaneView(resource, machine) {
    const tone = stateTone(machine);
    const queueCount = Number(machine?.queue_count || 0);
    const progress = percent(machine?.active);
    const value = progress == null ? (tone === "idle" ? "0 %" : "—") : `${progress} %`;
    const item = document.createElement("span");
    item.className = `work-queue-minimized-lane ${tone}`;
    item.append(minimizedIcon(resource));
    const dot = document.createElement("i");
    dot.className = "work-queue-minimized-dot";
    dot.setAttribute("aria-hidden", "true");
    const amount = document.createElement("strong");
    amount.textContent = value;
    item.append(dot, amount);
    if (queueCount > 0) {
      const waiting = document.createElement("small");
      waiting.textContent = `+${queueCount}`;
      item.append(waiting);
    }
    const name = resource === "local_gpu" ? "Local" : "Serveur";
    item.title = `${name} · ${stateLabel(machine)} · ${value}${queueCount ? ` · ${queueCount} en attente` : ""}`;
    return item;
  }

  function renderMinimized() {
    const unavailable = {state: "unavailable", active: null, queue_count: 0, queue: []};
    const local = status?.machines?.local_gpu || unavailable;
    const remote = status?.machines?.remote_gpu || unavailable;
    const summary = floating.querySelector("[data-restore]");
    summary.replaceChildren(
      minimizedLaneView("local_gpu", local),
      minimizedLaneView("remote_gpu", remote),
    );
    summary.setAttribute("aria-label", `Agrandir le suivi des traitements. Local ${stateLabel(local)}, serveur ${stateLabel(remote)}.`);
  }

  function activityStage(activity, queued = false) {
    return queued ? "◷ Planifié · en attente de la machine" : ({queued: "Planifié · en attente du LLM",
      starting: "Démarrage du LLM", preparing: "Préparation de l’appel", loading: "Chargement du modèle",
      generating: "Génération en cours"}[activity.stage] || activity.stage || "Traitement en cours");
  }
  function activityView(activity, {queued = false} = {}) {
    const item = document.createElement("article");
    item.className = `work-queue-item${queued ? " queued" : ""}`;
    const title = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = `${queued ? `${activity.position} · ` : ""}${activityName(activity)}`;
    const kind = document.createElement("small");
    kind.textContent = labels[activity.workload] || activity.workload || "Traitement";
    title.append(strong, kind);
    const stage = document.createElement("p");
    stage.textContent = activityStage(activity, queued);
    const progress = document.createElement("progress");
    progress.max = 1;
    const value = percent(activity);
    if (value == null || queued) progress.removeAttribute("value");
    else progress.value = Math.max(0, Math.min(1, Number(activity.progress)));
    const progressLabel = document.createElement("span");
    progressLabel.textContent = queued ? "Planifié" : value == null ? "Progression non mesurable" : `${value} %`;
    item.append(title, stage, progress, progressLabel);
    return item;
  }

  function laneView(resource, machine) {
    const section = document.createElement("section");
    section.className = "work-queue-lane";
    const head = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = labels[resource];
    const badge = document.createElement("span");
    badge.className = `work-queue-state ${stateTone(machine)}`;
    badge.textContent = stateLabel(machine);
    head.append(heading, badge);
    section.append(head);
    if (machine?.active) section.append(activityView(machine.active));
    else {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = machine?.paused ? "Les nouvelles tâches attendent la reprise."
        : machine?.queue_count ? "Le prochain traitement attend son admission." : "Aucun traitement en cours.";
      section.append(empty);
    }
    const queue = machine?.queue || [];
    const title = document.createElement("h4");
    title.textContent = `À venir · ${Number(machine?.queue_count || queue.length || 0)}`;
    section.append(title);
    if (queue.length) section.append(...queue.map(value => activityView(value, {queued: true})));
    else section.append(Object.assign(document.createElement("p"), {
      className: "muted work-queue-empty",
      textContent: "Aucun traitement en attente.",
    }));
    const action = document.createElement("button");
    action.type = "button";
    action.dataset.resource = resource;
    action.dataset.action = machine?.paused ? "resume" : "pause";
    action.textContent = machine?.paused ? "Reprendre la file" : "Pause après le traitement en cours";
    section.append(action);
    return section;
  }

  function compactLaneView(resource, machine) {
    const lane = document.createElement("section");
    const tone = stateTone(machine);
    lane.className = `work-queue-compact-lane ${tone}`;
    lane.dataset.resource = resource;

    const head = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = resource === "local_gpu" ? "Local" : "Serveur";
    const badge = document.createElement("span");
    badge.className = `work-queue-state ${tone}`;
    badge.textContent = stateLabel(machine);
    const waiting = document.createElement("small");
    const queueCount = Number(machine?.queue_count || 0);
    waiting.textContent = `${queueCount} en attente`;
    head.append(name, badge, waiting);

    const operation = document.createElement("p");
    if (machine?.state === "cooling") {
      const remaining = Number(machine?.cooldown_remaining_seconds || 0);
      operation.textContent = `${machine?.operation || "Refroidissement de la machine"}${remaining ? ` · ${remaining} s` : ""}`;
    } else if (machine?.active) {
      operation.textContent = `${activityName(machine.active)} · ${activityStage(machine.active)}`;
    } else if (machine?.paused) {
      operation.textContent = "Les nouveaux traitements attendent la reprise.";
    } else if (tone === "unavailable") {
      operation.textContent = "La machine ou sa télémétrie ne répond pas.";
    } else if (queueCount > 0) {
      operation.textContent = machine?.queue?.[0]
        ? `Prochain · ${activityName(machine.queue[0])}`
        : "Admission du prochain traitement…";
    } else {
      operation.textContent = "Aucun traitement en cours.";
    }

    const meter = document.createElement("div");
    meter.className = "work-queue-compact-progress";
    const progress = document.createElement("progress");
    progress.max = 1;
    const value = percent(machine?.active);
    if (tone === "busy" && value == null) progress.removeAttribute("value");
    else progress.value = value == null ? 0 : Math.max(0, Math.min(1, Number(machine.active.progress)));
    const progressLabel = document.createElement("span");
    progressLabel.textContent = tone === "busy" ? (value == null ? "—" : `${value} %`)
      : tone === "cooling" ? (machine?.cooldown_remaining_seconds ? `${machine.cooldown_remaining_seconds} s` : "—")
      : "0 %";
    meter.append(progress, progressLabel);
    lane.append(head, operation, meter);
    return lane;
  }

  function syncSettings(settings) {
    if (!settings || saving || form.contains(document.activeElement)) return;
    const thermal = settings.thermal || {};
    for (const name of ["stop_temperature_c", "resume_temperature_c", "cooldown_seconds", "monitor_local", "monitor_remote", "pause_when_unavailable"]) {
      if (thermal[name] === undefined) continue;
      if (field(name).type === "checkbox") field(name).checked = Boolean(thermal[name]);
      else field(name).value = String(thermal[name]);
    }
    for (const name of ["remote_video_cooldown_seconds", "history_limit", "pause_after_failure"]) {
      if (settings[name] === undefined) continue;
      if (field(name).type === "checkbox") field(name).checked = Boolean(settings[name]);
      else field(name).value = String(settings[name]);
    }
  }

  function render() {
    renderMinimized();
    if (!status?.machines) {
      const unavailable = {state: "unavailable", active: null, queue_count: 0, queue: []};
      floating.querySelector("[data-compact]").replaceChildren(
        compactLaneView("local_gpu", unavailable),
        compactLaneView("remote_gpu", unavailable),
      );
      floating.querySelector("[data-notices]").replaceChildren(...notices.map(noticeView));
      return;
    }
    const lanes = dialog.querySelector("[data-lanes]");
    lanes.replaceChildren(
      laneView("local_gpu", status.machines.local_gpu),
      laneView("remote_gpu", status.machines.remote_gpu),
    );
    syncSettings(status.settings);
    const history = dialog.querySelector("[data-history]");
    const recent = status.recent || [];
    history.replaceChildren(...recent.slice(0, 12).map(value => {
      const row = document.createElement("article");
      row.className = `work-queue-history-row ${value.status || ""}`;
      const summary = document.createElement("p");
      const statusLabel = value.status === "completed" ? "terminé"
        : value.status === "failed" ? "échec"
        : value.status === "cancelled" ? "annulé" : value.status;
      summary.textContent = `${labels[value.resource] || value.resource} · ${activityName(value)} · ${statusLabel}`;
      row.append(summary);
      if (value.error) {
        const detail = document.createElement("small");
        detail.textContent = `${value.error_type ? `${value.error_type} · ` : ""}${value.error}`;
        row.append(detail);
      }
      return row;
    }));
    if (!recent.length) history.append(Object.assign(document.createElement("p"), {textContent: "Aucun traitement récent."}));
    const compact = floating.querySelector("[data-compact]");
    compact.replaceChildren(
      compactLaneView("local_gpu", status.machines.local_gpu),
      compactLaneView("remote_gpu", status.machines.remote_gpu),
    );
    floating.querySelector("[data-notices]").replaceChildren(...notices.map(noticeView));
  }

  function noticeView(value) {
    const row = document.createElement("p");
    row.className = `work-queue-notice ${value.level || "error"}`;
    const message = document.createElement("span");
    message.textContent = value.message;
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.textContent = "Masquer";
    dismiss.addEventListener("click", () => {
      notices = notices.filter(notice => notice.id !== value.id);
      render();
    });
    row.append(message, dismiss);
    return row;
  }

  function notice(message, {id = null, level = "error"} = {}) {
    const text = String(message || "").trim();
    if (!text) return;
    const noticeId = id || `notice-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    notices = [...notices.filter(value => value.id !== noticeId), {id: noticeId, message: text, level}].slice(-5);
    render();
  }

  async function control(resource, action) {
    try {
      error.textContent = "";
      status = await request(`/api/work-scheduler/${resource}/${action}`, {method: "POST"});
      render();
    } catch (reason) {
      error.textContent = reason.message;
    }
  }

  async function open() {
    if (!status) {
      try {
        status = await request("/api/work-scheduler/status");
        render();
      } catch (reason) {
        notice(reason.message, {id: "scheduler:status"});
      }
    }
    if (!dialog.open) dialog.showModal();
  }

  dialog.addEventListener("click", event => {
    const button = event.target.closest("[data-resource][data-action]");
    if (button) control(button.dataset.resource, button.dataset.action);
  });
  dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("cancel", event => { event.preventDefault(); dialog.close(); });
  floating.querySelector("[data-open]").addEventListener("click", open);
  floating.querySelector("[data-minimize]").addEventListener("click", () => setMinimized(true));
  floating.querySelector("[data-restore]").addEventListener("click", () => setMinimized(false));

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving || !form.reportValidity()) return;
    const stop = Number(field("stop_temperature_c").value);
    const resume = Number(field("resume_temperature_c").value);
    if (!(resume < stop)) {
      error.textContent = "La température de reprise doit être inférieure au seuil de pause.";
      return;
    }
    saving = true;
    form.querySelector("button[type=submit]").disabled = true;
    try {
      await request("/api/work-scheduler/settings", {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          thermal: {
            stop_temperature_c: stop,
            resume_temperature_c: resume,
            cooldown_seconds: Number(field("cooldown_seconds").value),
            monitor_local: field("monitor_local").checked,
            monitor_remote: field("monitor_remote").checked,
            pause_when_unavailable: field("pause_when_unavailable").checked,
          },
          remote_video_cooldown_seconds: Number(field("remote_video_cooldown_seconds").value),
          pause_after_failure: field("pause_after_failure").checked,
          history_limit: Number(field("history_limit").value),
        }),
      });
      status = await request("/api/work-scheduler/status");
      error.textContent = "Paramètres enregistrés.";
      render();
    } catch (reason) {
      error.textContent = reason.message;
    } finally {
      saving = false;
      form.querySelector("button[type=submit]").disabled = false;
    }
  });

  window.addEventListener("panelforge:work-scheduler-status", event => {
    status = event.detail;
    render();
  });
  window.addEventListener("panelforge:render-progress", event => {
    const data = event.detail;
    const machine = status?.machines?.remote_gpu;
    const active = machine?.active;
    const value = Number(data?.percent);
    if (!active || !Number.isFinite(value) || value < 0 || value > 100) return;
    if (active.execution_id && data.prompt_id && active.execution_id !== data.prompt_id) return;
    const progress = Math.max(Number(active.progress || 0), value / 100);
    const current = Number(data.current_step);
    const total = Number(data.total_steps);
    const step = Number.isFinite(current) && Number.isFinite(total) && total > 0
      ? ` · étape ${Math.round(current)}/${Math.round(total)}` : "";
    status = {
      ...status,
      machines: {
        ...status.machines,
        remote_gpu: {
          ...machine,
          active: {
            ...active,
            progress,
            stage: `${data.phase_label || active.stage || "Rendu H3"}${step}`,
          },
        },
      },
    };
    render();
  });
  document.addEventListener("DOMContentLoaded", () => {
    const monitor = document.getElementById("runtime-monitor");
    if (!monitor) return;
    monitor.setAttribute("role", "button");
    monitor.setAttribute("tabindex", "0");
    monitor.setAttribute("aria-label", "Ouvrir le suivi global des traitements");
    monitor.addEventListener("click", open);
    monitor.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault(); open();
      }
    });
    request("/api/work-scheduler/status").then(value => {
      status = value;
      render();
    }).catch(() => render());
  });
  window.PanelForgeWorkQueue = Object.freeze({
    open,
    notice,
  });
  render();
})();
