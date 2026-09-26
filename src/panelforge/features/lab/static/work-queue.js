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
  let thermalHistory24h = null;
  let thermalHistoryLoading = false;
  let thermalHistoryLoadedAt = 0;
  let thermalHistoryError = "";
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
    <section class="work-queue-thermal-history">
      <div class="work-queue-thermal-history-head">
        <div><h3>Températures · dernières 24 heures</h3><p>Maxima par tranche de 15 secondes. Les interruptions de mesure restent visibles.</p></div>
        <button type="button" data-refresh-thermal-history>Actualiser</button>
      </div>
      <p class="error-text" data-thermal-history-error role="alert"></p>
      <div data-thermal-history aria-live="polite"></div>
    </section>
    <details class="work-queue-settings">
      <summary>Paramètres globaux des machines</summary>
      <form data-settings-form>
        <div class="work-queue-machine-settings">
          <section>
            <h3>Local</h3>
            <p class="muted">Après une tâche ayant atteint le seuil, la suivante attend le cooldown indiqué.</p>
            <div class="work-queue-settings-grid">
              <label>Cooldown à partir de °C<input name="local_cooldown_temperature_c" type="number" min="30" max="110" step="1" value="80" required></label>
              <label>Durée du cooldown<input name="local_cooldown_seconds" type="number" min="0" max="3600" step="1" value="80" required><small>secondes</small></label>
            </div>
            <div class="work-queue-checks">
              <label><input name="monitor_local" type="checkbox"> Surveiller la température locale</label>
            </div>
          </section>
          <section>
            <h3>Serveur</h3>
            <p class="muted">La reprise attend une température sûre et stable avant d’admettre la tâche.</p>
            <div class="work-queue-settings-grid">
              <label>Pause thermique à partir de °C<input name="stop_temperature_c" type="number" min="30" max="110" step="1" required></label>
              <label>Reprise sous °C<input name="resume_temperature_c" type="number" min="15" max="109" step="1" required></label>
              <label>Stabilisation thermique<input name="cooldown_seconds" type="number" min="0" max="86400" step="1" required><small>secondes</small></label>
              <label>Repos entre vidéos<input name="remote_video_cooldown_seconds" type="number" min="0" max="3600" step="1" required><small>secondes</small></label>
            </div>
            <div class="work-queue-checks">
              <label><input name="monitor_remote" type="checkbox"> Surveiller la température distante</label>
              <label><input name="pause_when_unavailable" type="checkbox"> Suspendre si la température est indisponible</label>
            </div>
          </section>
        </div>
        <div class="work-queue-general-settings">
          <label>Historique visible<input name="history_limit" type="number" min="5" max="200" step="1" required><small>traitements</small></label>
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
    <div class="work-queue-compact-body">
      <div class="work-queue-compact-lanes" data-compact></div>
      <section class="work-queue-temperatures" aria-label="Températures GPU de la dernière heure">
        <div class="work-queue-temperature-head">
          <strong>Températures</strong><small>max. / 15 s · 1 h</small>
        </div>
        <div data-temperature-charts></div>
      </section>
    </div>
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

  const temperatureColor = value => value >= 90 ? "#7f1d1d"
    : value >= 80 ? "#d13b2e" : value >= 70 ? "#c47b08" : "#23895a";

  function temperatureChart(resource, machine) {
    const history = status?.temperature_history || {};
    const windowSeconds = Number(history.window_seconds || 3600);
    const values = Array.isArray(history?.series?.[resource])
      ? history.series[resource].filter(value => Number.isFinite(Number(value.max_temperature_c)))
      : [];
    const current = machine?.temperature_c == null
      ? Number.NaN
      : Number(machine.temperature_c);
    const temperatures = values.map(value => Number(value.max_temperature_c));
    if (Number.isFinite(current)) temperatures.push(current);
    const peak = temperatures.length ? Math.max(...temperatures) : null;

    const article = document.createElement("article");
    article.className = "work-queue-temperature-chart";
    const head = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = resource === "local_gpu" ? "Local" : "Serveur";
    const reading = document.createElement("span");
    reading.textContent = Number.isFinite(current)
      ? `${Math.round(current)} °C · pic ${Math.round(peak)} °C`
      : peak == null ? "Température indisponible" : `— · pic ${Math.round(peak)} °C`;
    if (Number.isFinite(current)) reading.style.color = temperatureColor(current);
    head.append(name, reading);

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 330 108");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `Historique thermique ${name.textContent}, de 0 à 100 degrés sur une heure`);
    const node = (tag, attributes, text = null) => {
      const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
      if (text != null) element.textContent = text;
      svg.append(element);
      return element;
    };
    const left = 28;
    const right = 324;
    const top = 5;
    const bottom = 81;
    for (let temperature = 0; temperature <= 100; temperature += 20) {
      const y = bottom - (temperature / 100) * (bottom - top);
      node("line", {x1: left, y1: y, x2: right, y2: y, class: "work-queue-temperature-grid"});
      node("text", {x: left - 4, y: y + 3, "text-anchor": "end"}, temperature);
    }
    for (const minutes of [60, 45, 30, 15, 0]) {
      const x = left + ((60 - minutes) / 60) * (right - left);
      node("line", {x1: x, y1: top, x2: x, y2: bottom, class: "work-queue-temperature-grid vertical"});
      node("text", {x, y: 101, "text-anchor": minutes === 60 ? "start" : minutes === 0 ? "end" : "middle"},
        minutes === 0 ? "maint." : `-${minutes} min`);
    }
    const points = values.map(value => {
      const age = Math.max(0, Math.min(windowSeconds, Number(value.age_seconds || 0)));
      const temperature = Math.max(0, Math.min(100, Number(value.max_temperature_c)));
      return {
        x: left + (1 - age / windowSeconds) * (right - left),
        y: bottom - (temperature / 100) * (bottom - top),
        temperature,
        age,
      };
    }).sort((a, b) => b.age - a.age);
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const point = points[index];
      if (previous.age - point.age > Number(history.bucket_seconds || 15) * 2.5) continue;
      node("line", {
        x1: previous.x, y1: previous.y, x2: point.x, y2: point.y,
        stroke: temperatureColor(Math.max(previous.temperature, point.temperature)),
        class: "work-queue-temperature-segment",
      });
    }
    if (!points.length) node("text", {x: (left + right) / 2, y: 47, "text-anchor": "middle", class: "empty"}, "En attente de relevés");
    article.append(head, svg);
    return article;
  }

  function renderTemperatures() {
    const unavailable = {temperature_c: null};
    floating.querySelector("[data-temperature-charts]").replaceChildren(
      temperatureChart("local_gpu", status?.machines?.local_gpu || unavailable),
      temperatureChart("remote_gpu", status?.machines?.remote_gpu || unavailable),
    );
  }

  const eventStatusLabel = status => ({
    completed: "terminé",
    failed: "échec",
    cancelled: "annulé",
    interrupted: "interrompu par un arrêt",
    running: "en cours",
  }[status] || status || "état inconnu");

  function eventDescription(value) {
    const started = Date.parse(value.started_at);
    const finished = Date.parse(value.finished_at);
    const time = Number.isFinite(started)
      ? new Date(started).toLocaleString("fr-FR", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"})
      : "heure inconnue";
    const duration = Number.isFinite(started) && Number.isFinite(finished) && finished >= started
      ? Math.max(1, Math.round((finished - started) / 60000)) : null;
    const peak = value.peak_temperature_c == null ? Number.NaN : Number(value.peak_temperature_c);
    return `${time} · ${value.marker || "?"} ${labels[value.workload] || value.workload || "Traitement"}`
      + ` · ${value.operation || "Traitement sans libellé"}`
      + `${duration == null ? "" : ` · ${duration} min`}`
      + ` · ${eventStatusLabel(value.status)}`
      + `${Number.isFinite(peak) ? ` · pic ${Math.round(peak)} °C` : ""}`;
  }

  function clusteredEvents(values, from, to) {
    const width = Math.max(1, to - from);
    const clusterDuration = 30 * 60 * 1000;
    const groups = new Map();
    values.forEach(value => {
      const started = Date.parse(value.started_at);
      if (!Number.isFinite(started) || started < from || started > to) return;
      const slot = Math.floor((started - from) / clusterDuration);
      if (!groups.has(slot)) groups.set(slot, []);
      groups.get(slot).push(value);
    });
    return [...groups.values()].map(events => ({
      events,
      ratio: Math.max(0, Math.min(1,
        (events.reduce((sum, value) => sum + Date.parse(value.started_at), 0) / events.length - from) / width)),
    }));
  }

  function longTemperatureChart(resource, history) {
    const from = Date.parse(history?.from);
    const to = Date.parse(history?.to);
    const windowEnd = Number.isFinite(to) ? to : Date.now();
    const windowStart = Number.isFinite(from) ? from : windowEnd - 24 * 60 * 60 * 1000;
    const values = Array.isArray(history?.series?.[resource])
      ? history.series[resource].map(value => ({
        timestamp: Date.parse(value.timestamp),
        temperature: Number(value.max_temperature_c),
      })).filter(value => Number.isFinite(value.timestamp) && Number.isFinite(value.temperature)
        && value.timestamp >= windowStart && value.timestamp <= windowEnd)
        .sort((a, b) => a.timestamp - b.timestamp)
      : [];
    const events = Array.isArray(history?.events?.[resource]) ? history.events[resource] : [];
    const article = document.createElement("article");
    article.className = "work-queue-long-temperature-chart";

    const head = document.createElement("div");
    const heading = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = resource === "local_gpu" ? "Machine locale" : "Serveur distant";
    const legend = document.createElement("small");
    legend.textContent = resource === "local_gpu" ? "P = Prompt/LLM · D = DLSS" : "I = Image · V = Vidéo";
    heading.append(title, legend);
    const reading = document.createElement("strong");
    const peak = values.length ? Math.max(...values.map(value => value.temperature)) : null;
    const latest = values.length ? values[values.length - 1].temperature : null;
    reading.textContent = latest == null ? "Aucun relevé"
      : `${Math.round(latest)} °C · pic ${Math.round(peak)} °C`;
    if (latest != null) reading.style.color = temperatureColor(latest);
    head.append(heading, reading);

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 1200 250");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `Température de ${title.textContent}, de 0 à 100 degrés sur les dernières 24 heures`);
    const svgNode = (tag, attributes, text = null) => {
      const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
      if (text != null) element.textContent = text;
      svg.append(element);
      return element;
    };
    const left = 48;
    const right = 1188;
    const top = 8;
    const bottom = 205;
    const y = temperature => bottom - (temperature / 100) * (bottom - top);
    for (const [minimum, maximum, fill] of [
      [0, 70, "#eaf6ef"], [70, 80, "#fff2d7"], [80, 90, "#fde5e0"], [90, 100, "#f4ceca"],
    ]) {
      svgNode("rect", {x: left, y: y(maximum), width: right - left, height: y(minimum) - y(maximum), fill});
    }
    for (let temperature = 0; temperature <= 100; temperature += 20) {
      const lineY = y(temperature);
      svgNode("line", {x1: left, y1: lineY, x2: right, y2: lineY, class: "work-queue-temperature-grid"});
      svgNode("text", {x: left - 8, y: lineY + 4, "text-anchor": "end"}, temperature);
    }
    for (const hours of [24, 18, 12, 6, 0]) {
      const x = left + ((24 - hours) / 24) * (right - left);
      svgNode("line", {x1: x, y1: top, x2: x, y2: bottom, class: "work-queue-temperature-grid vertical"});
      svgNode("text", {x, y: 235, "text-anchor": hours === 24 ? "start" : hours === 0 ? "end" : "middle"},
        hours === 0 ? "maint." : `-${hours} h`);
    }
    const width = Math.max(1, windowEnd - windowStart);
    const points = values.map(value => ({
      x: left + ((value.timestamp - windowStart) / width) * (right - left),
      y: y(Math.max(0, Math.min(100, value.temperature))),
      ...value,
    }));
    const maximumGap = Number(history?.bucket_seconds || 15) * 1600;
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const point = points[index];
      if (point.timestamp - previous.timestamp > maximumGap) continue;
      svgNode("line", {
        x1: previous.x, y1: previous.y, x2: point.x, y2: point.y,
        stroke: temperatureColor(Math.max(previous.temperature, point.temperature)),
        class: "work-queue-long-temperature-segment",
      });
    }
    if (!points.length) svgNode("text", {x: (left + right) / 2, y: 108, "text-anchor": "middle", class: "empty"}, "Aucun relevé enregistré sur cette période");

    const track = document.createElement("div");
    track.className = "work-queue-event-track";
    const trackLabel = document.createElement("span");
    trackLabel.textContent = "Evt";
    trackLabel.title = "Événements";
    trackLabel.setAttribute("aria-label", "Événements");
    const markers = document.createElement("div");
    markers.className = "work-queue-event-markers";
    const detail = document.createElement("p");
    detail.className = "work-queue-event-detail";
    detail.textContent = events.length
      ? "Survole, sélectionne ou clique sur un marqueur pour afficher son traitement."
      : "Aucun traitement enregistré sur cette période.";
    for (const cluster of clusteredEvents(events, windowStart, windowEnd)) {
      const button = document.createElement("button");
      button.type = "button";
      button.style.left = `${cluster.ratio * 100}%`;
      const kinds = [...new Set(cluster.events.map(value => value.marker).filter(Boolean))];
      button.textContent = kinds.length === 1
        ? `${kinds[0]}${cluster.events.length > 1 ? `×${cluster.events.length}` : ""}`
        : kinds.join("/");
      const descriptions = cluster.events.map(eventDescription);
      button.title = descriptions.join("\n");
      button.setAttribute("aria-label", descriptions.join(". "));
      const show = () => { detail.textContent = descriptions.join(" | "); };
      button.addEventListener("mouseenter", show);
      button.addEventListener("focus", show);
      button.addEventListener("click", show);
      markers.append(button);
    }
    track.append(trackLabel, markers);
    article.append(head, svg, track, detail);
    return article;
  }

  function renderThermalHistory24h() {
    const host = dialog.querySelector("[data-thermal-history]");
    const errorHost = dialog.querySelector("[data-thermal-history-error]");
    errorHost.textContent = thermalHistoryError;
    if (thermalHistoryLoading && !thermalHistory24h) {
      host.replaceChildren(Object.assign(document.createElement("p"), {className: "muted", textContent: "Chargement de l’historique thermique…"}));
      return;
    }
    if (!thermalHistory24h) {
      host.replaceChildren(Object.assign(document.createElement("p"), {className: "muted", textContent: "L’historique sera chargé à l’ouverture de cette fenêtre."}));
      return;
    }
    host.replaceChildren(
      longTemperatureChart("local_gpu", thermalHistory24h),
      longTemperatureChart("remote_gpu", thermalHistory24h),
    );
  }

  async function loadThermalHistory24h({force = false} = {}) {
    if (thermalHistoryLoading) return;
    if (!force && thermalHistory24h && Date.now() - thermalHistoryLoadedAt < 60_000) return;
    thermalHistoryLoading = true;
    thermalHistoryError = "";
    renderThermalHistory24h();
    try {
      thermalHistory24h = await request("/api/work-scheduler/thermal-history");
      thermalHistoryLoadedAt = Date.now();
      thermalHistoryError = thermalHistory24h?.error
        ? `Certaines mesures n’ont pas pu être enregistrées : ${thermalHistory24h.error}` : "";
    } catch (reason) {
      thermalHistoryError = reason.message;
    } finally {
      thermalHistoryLoading = false;
      renderThermalHistory24h();
    }
  }

  function activityStage(activity, queued = false) {
    return queued ? "◷ Planifié · en attente de la machine" : ({queued: "Planifié · en attente du LLM",
      starting: "Démarrage du LLM", preparing: "Préparation de l’appel", loading: "Chargement du modèle",
      generating: "Génération en cours"}[activity.stage] || activity.stage || "Traitement en cours");
  }
  const tokenAmount = value => `${(Math.max(0, Number(value) || 0) / 1000).toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}k`;
  function llmMetricsView(activity) {
    const metrics = activity?.llm_metrics;
    if (!metrics) return null;
    const row = document.createElement("p");
    row.className = "work-queue-llm-metrics";
    const speed = Math.max(0, Number(metrics.tokens_per_second) || 0).toLocaleString("fr-FR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
    row.textContent = `${speed} tok/s · Th : ${tokenAmount(metrics.thinking_tokens)} · Wr : ${tokenAmount(metrics.writing_tokens)}`;
    if (metrics.estimated) row.title = "Répartition thinking/writing estimée depuis les événements du flux ; total réconcilié à la fin.";
    return row;
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
    item.append(title, stage);
    const metrics = llmMetricsView(activity);
    if (metrics) item.append(metrics);
    item.append(progress, progressLabel);
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
    lane.append(head, operation);
    const metrics = resource === "local_gpu" ? llmMetricsView(machine?.active) : null;
    if (metrics) lane.append(metrics);
    lane.append(meter);
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
    for (const name of ["local_cooldown_temperature_c", "local_cooldown_seconds",
      "remote_video_cooldown_seconds", "history_limit", "pause_after_failure"]) {
      if (settings[name] === undefined) continue;
      if (field(name).type === "checkbox") field(name).checked = Boolean(settings[name]);
      else field(name).value = String(settings[name]);
    }
  }

  function render() {
    renderMinimized();
    renderTemperatures();
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
    await loadThermalHistory24h();
  }

  dialog.addEventListener("click", event => {
    const button = event.target.closest("[data-resource][data-action]");
    if (button) control(button.dataset.resource, button.dataset.action);
  });
  dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-refresh-thermal-history]").addEventListener("click", () => loadThermalHistory24h({force: true}));
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
          local_cooldown_temperature_c: Number(field("local_cooldown_temperature_c").value),
          local_cooldown_seconds: Number(field("local_cooldown_seconds").value),
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
  window.setInterval(() => {
    if (dialog.open) loadThermalHistory24h();
  }, 60_000);
  renderThermalHistory24h();
  render();
})();
