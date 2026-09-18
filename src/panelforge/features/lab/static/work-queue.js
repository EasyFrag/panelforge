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

  const floating = document.createElement("details");
  floating.className = "work-queue-background";
  floating.hidden = true;
  floating.innerHTML = `<summary data-summary>Traitements</summary><div data-compact></div><button type="button" data-open>Ouvrir le suivi complet</button>`;
  document.body.append(floating);

  const form = dialog.querySelector("[data-settings-form]");
  const field = name => form.elements.namedItem(name);
  const error = dialog.querySelector("[data-error]");

  const activityName = activity => activity?.operation || labels[activity?.workload] || "Traitement";
  const percent = activity => activity?.progress == null ? null : Math.round(Number(activity.progress) * 100);
  const stateLabel = machine => machine?.paused ? "File suspendue"
    : machine?.state === "cooling" ? `Refroidissement${machine.cooldown_remaining_seconds ? ` · ${machine.cooldown_remaining_seconds} s` : ""}`
    : machine?.state === "hot" ? "Température trop élevée"
    : machine?.state === "unavailable" ? "Télémétrie indisponible"
    : machine?.active ? activityName(machine.active) : "Disponible";

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
    stage.textContent = queued ? "En attente de la machine" : activity.stage || "Traitement en cours";
    const progress = document.createElement("progress");
    progress.max = 1;
    const value = percent(activity);
    if (value == null || queued) progress.removeAttribute("value");
    else progress.value = Math.max(0, Math.min(1, Number(activity.progress)));
    const progressLabel = document.createElement("span");
    progressLabel.textContent = queued ? "En file" : value == null ? "Progression non mesurable" : `${value} %`;
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
    badge.className = `work-queue-state ${machine?.state || "idle"}`;
    badge.textContent = stateLabel(machine);
    head.append(heading, badge);
    section.append(head);
    if (machine?.active) section.append(activityView(machine.active));
    else {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = machine?.paused ? "Les nouvelles tâches attendent la reprise." : "Aucun traitement en cours.";
      section.append(empty);
    }
    const queue = machine?.queue || [];
    if (queue.length) {
      const title = document.createElement("h4");
      title.textContent = `À venir · ${queue.length}`;
      section.append(title, ...queue.map(value => activityView(value, {queued: true})));
    }
    const action = document.createElement("button");
    action.type = "button";
    action.dataset.resource = resource;
    action.dataset.action = machine?.paused ? "resume" : "pause";
    action.textContent = machine?.paused ? "Reprendre la file" : "Pause après le traitement en cours";
    section.append(action);
    return section;
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
    if (!status?.machines) {
      floating.hidden = !notices.length;
      floating.querySelector("[data-summary]").textContent = notices.length ? "Traitements · attention requise" : "Traitements";
      floating.querySelector("[data-compact]").replaceChildren(...notices.map(noticeView));
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
      const row = document.createElement("p");
      row.textContent = `${labels[value.resource] || value.resource} · ${activityName(value)} · ${value.status === "completed" ? "terminé" : value.status}`;
      return row;
    }));
    if (!recent.length) history.append(Object.assign(document.createElement("p"), {textContent: "Aucun traitement récent."}));

    const machines = Object.values(status.machines);
    const visible = notices.length || machines.some(machine => machine.active || machine.queue_count || machine.paused);
    floating.hidden = !visible;
    const summaries = machines.filter(machine => machine.active || machine.queue_count || machine.paused).map(machine => {
      const name = machine === status.machines.local_gpu ? "Local" : "Serveur";
      const value = percent(machine.active);
      return `${name} · ${stateLabel(machine)}${value == null ? "" : ` · ${value} %`}${machine.queue_count ? ` · +${machine.queue_count}` : ""}`;
    });
    floating.querySelector("[data-summary]").textContent = notices.length
      ? `Traitements · ${notices.length} alerte${notices.length > 1 ? "s" : ""}`
      : `Traitements · ${summaries.join(" / ")}`;
    const compact = floating.querySelector("[data-compact]");
    compact.replaceChildren(...notices.map(noticeView), ...machines.filter(machine => machine.active || machine.queue_count).map(machine => {
      const row = document.createElement("p");
      row.textContent = `${machine === status.machines.local_gpu ? "Local" : "Serveur"} · ${stateLabel(machine)}${machine.queue_count ? ` · ${machine.queue_count} à venir` : ""}`;
      return row;
    }));
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
  });
  window.PanelForgeWorkQueue = Object.freeze({
    open,
    notice,
  });
})();
