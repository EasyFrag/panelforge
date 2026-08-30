(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const elements = {
    changeView: $("#change-view-workspace"),
    krea2ImageLab: $("#krea2-image-lab-workspace"),
    krea2AssistedLab: $("#krea2-assisted-lab-workspace"),
    krea2BatchLab: $("#krea2-batch-lab-workspace"),
    krea2EditLab: $("#krea2-edit-lab-workspace"),
    i2vDirect: $("#i2vd-workspace"),
    ref2vDirect: $("#ref2vd-workspace"),
    videoLab: $("#video-lab-workspace"),
    socialLab: $("#social-lab-workspace"),
    productionLab: $("#production-lab-workspace"),
    recipeBadge: $("#recipe-badge"),
    i2vDirectNewRun: $("#i2vd-topbar-new"),
    ref2vDirectNewRun: $("#ref2vd-topbar-new"),
    nav: [...document.querySelectorAll("[data-lab-view]")],
    imageLabModes: [...document.querySelectorAll("[data-image-lab-mode]")],
    videoLabModes: [...document.querySelectorAll("[data-video-lab-mode]")],
  };

  function switchView(view) {
    const imageLabActive = [
      "change-view",
      "krea2-image-lab",
      "krea2-assisted-lab",
      "krea2-batch-lab",
      "krea2-edit-lab",
    ].includes(view);
    const visibility = [
      [elements.changeView, view === "change-view"],
      [elements.krea2ImageLab, view === "krea2-image-lab"],
      [elements.krea2AssistedLab, view === "krea2-assisted-lab"],
      [elements.krea2BatchLab, view === "krea2-batch-lab"],
      [elements.krea2EditLab, view === "krea2-edit-lab"],
      [elements.i2vDirect, view === "i2v-direct"],
      [elements.ref2vDirect, view === "ref2v-direct"],
      [elements.videoLab, view === "video-lab"],
      [elements.socialLab, view === "social-lab"],
      [elements.productionLab, view === "production-lab"],
    ];
    visibility.forEach(([element, visible]) => {
      if (element) element.hidden = !visible;
    });
    if (elements.recipeBadge) elements.recipeBadge.hidden = view !== "change-view";
    if (elements.i2vDirectNewRun) elements.i2vDirectNewRun.hidden = view !== "i2v-direct";
    if (elements.ref2vDirectNewRun) elements.ref2vDirectNewRun.hidden = view !== "ref2v-direct";
    const baseTopLevelView = imageLabActive ? "change-view" : view;
    const topLevelView = view === "social-lab" ? "video-lab" : baseTopLevelView;
    elements.nav.forEach((button) => {
      button.classList.toggle(
        "active",
        button.dataset.labView === topLevelView,
      );
    });
    elements.imageLabModes.forEach((button) => {
      button.classList.toggle("active", button.dataset.imageLabMode === view);
    });
    elements.videoLabModes.forEach((button) => {
      button.classList.toggle("active", button.dataset.videoLabMode === view);
    });
  }

  window.PanelForgeLabNavigation = Object.freeze({ switchView });
  elements.nav.forEach((button) => {
    button.addEventListener("click", () => switchView(
      button.dataset.labView === "change-view"
        ? "krea2-assisted-lab"
        : button.dataset.labView,
    ));
  });
  elements.videoLabModes.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.videoLabMode));
  });

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* empty response */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
    }
    return payload;
  }

  let completionAudioContext = null;

  function prepareCompletionAudio() {
    if (!completionAudioContext) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      completionAudioContext = new AudioContext();
    }
    if (completionAudioContext.state === "suspended") {
      completionAudioContext.resume().catch(() => {});
    }
  }

  function playTone(notes) {
    if (!completionAudioContext || completionAudioContext.state !== "running") return;
    const now = completionAudioContext.currentTime;
    notes.forEach((note) => {
      const start = now + note.offset;
      const end = start + note.duration;
      const oscillator = completionAudioContext.createOscillator();
      const gain = completionAudioContext.createGain();
      oscillator.type = "triangle";
      oscillator.frequency.setValueAtTime(note.frequency, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.08, start + 0.02);
      gain.gain.setValueAtTime(0.06, end - 0.06);
      gain.gain.exponentialRampToValueAtTime(0.0001, end);
      oscillator.connect(gain).connect(completionAudioContext.destination);
      oscillator.start(start);
      oscillator.stop(end + 0.01);
    });
  }

  function playCompletionTone() {
    playTone([
      { frequency: 660, offset: 0, duration: 0.24 },
      { frequency: 880, offset: 0.22, duration: 0.34 },
    ]);
  }

  function playFailureTone() {
    playTone([
      { frequency: 440, offset: 0, duration: 0.2 },
      { frequency: 220, offset: 0.18, duration: 0.3 },
    ]);
  }

  function createLlmOutcomeTone() {
    let started = false;
    let settled = false;
    return Object.freeze({
      start() { started = true; },
      success() {
        if (!started || settled) return;
        settled = true;
        playCompletionTone();
      },
      failure() {
        if (!started || settled) return;
        settled = true;
        playFailureTone();
      },
    });
  }

  document.addEventListener("pointerdown", prepareCompletionAudio, { capture: true });
  document.addEventListener("keydown", prepareCompletionAudio, { capture: true });

  async function streamRequest(url, options, onEvent, { completionTone = false } = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = `Erreur HTTP ${response.status}`;
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") detail = payload.detail;
      } catch (_) { /* non-JSON error */ }
      throw new Error(detail);
    }
    if (!response.body) throw new Error("Le navigateur ne fournit pas le flux de réponse.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      buffer = buffer.replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = block.split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) {
          const event = JSON.parse(data);
          if (event.kind === "error") throw new Error(event.message || "Le flux LLM a échoué.");
          onEvent(event);
          if (event.kind === "completed" && completionTone) playCompletionTone();
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
  }

  function updateStreamState(view, event) {
    view.container.hidden = false;
    const terminalClass = ["completed", "truncated"].includes(event.phase)
      ? ` ${event.phase}`
      : "";
    view.container.className = `stream-state${terminalClass}`;
    const lines = event.kind === "status"
      ? String(event.text || "").split(/\r?\n/).filter(Boolean)
      : [];
    const labels = {
      preparing: "Préparation ou chargement du modèle…",
      loading: "Chargement du modèle…",
      generating: "Génération…",
      completed: "Terminé",
      truncated: "Réponse tronquée — budget de tokens épuisé",
    };
    view.label.textContent = lines.at(-1) || labels[event.phase] || "Traitement…";
    if (typeof event.progress === "number") {
      view.progress.value = event.progress;
      view.percent.textContent = `${Math.round(event.progress * 100)} %`;
    } else {
      view.progress.removeAttribute("value");
      view.percent.textContent = "";
    }
  }

  function failStreamState(view, message) {
    view.container.hidden = false;
    view.container.className = "stream-state failed";
    view.label.textContent = message;
    view.percent.textContent = "";
    view.progress.removeAttribute("value");
  }

  function createReasoningTrace({ toggle, panel, label, output, empty }) {
    const maximumCharacters = 100000;
    const preferenceKey = "panelforge.debug.show_reasoning";
    let buffer = "";
    let frame = null;
    let received = false;

    if (toggle) {
      try {
        const stored = window.localStorage.getItem(preferenceKey);
        if (stored !== null) toggle.checked = stored === "true";
      } catch (_) { /* optional preference */ }
    }

    const enabled = () => Boolean(toggle && toggle.checked);

    function flush() {
      frame = null;
      if (!output) return;
      output.textContent = buffer;
      output.scrollTop = output.scrollHeight;
    }

    function scheduleFlush() {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(flush);
    }

    function reset() {
      if (frame !== null) window.cancelAnimationFrame(frame);
      frame = null;
      buffer = "";
      received = false;
      if (output) output.textContent = "";
      if (empty) empty.hidden = false;
      if (panel) panel.hidden = true;
    }

    function begin(stageLabel, anchor = null) {
      if (!enabled()) {
        reset();
        return;
      }
      buffer = "";
      received = false;
      if (output) output.textContent = "";
      if (empty) {
        empty.textContent = "En attente d’une trace séparée du modèle…";
        empty.hidden = false;
      }
      if (label) label.textContent = `${stageLabel} · direct`;
      if (panel) {
        if (anchor && typeof anchor.before === "function") {
          anchor.open = true;
          anchor.before(panel);
        }
        panel.hidden = false;
        panel.open = true;
        if (anchor) {
          window.requestAnimationFrame(() => {
            panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
          });
        }
      }
    }

    function handle(event) {
      if (!enabled() || !event || event.kind !== "reasoning" || !event.text) return;
      received = true;
      buffer += event.text;
      if (buffer.length > maximumCharacters) {
        buffer = `[… trace limitée aux ${maximumCharacters.toLocaleString("fr-FR")} derniers caractères …]\n${buffer.slice(-maximumCharacters)}`;
      }
      if (empty) empty.hidden = true;
      scheduleFlush();
    }

    function finish() {
      if (!enabled()) return;
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
        flush();
      }
      if (!received && empty) {
        empty.textContent = "Aucune trace séparée transmise par ce modèle.";
        empty.hidden = false;
      }
    }

    function streamUrl(url) {
      if (!enabled()) return url;
      const target = new URL(url, window.location.href);
      target.searchParams.set("include_reasoning", "true");
      return `${target.pathname}${target.search}${target.hash}`;
    }

    if (toggle) toggle.addEventListener("change", () => {
      try {
        window.localStorage.setItem(preferenceKey, String(enabled()));
      } catch (_) { /* optional preference */ }
      if (!enabled()) reset();
    });

    return Object.freeze({ begin, handle, finish, reset, streamUrl, enabled });
  }

  function decorateSessionLink(button, references) {
    const items = (Array.isArray(references) ? references : [])
      .filter((reference) => reference && reference.content_url)
      .slice(0, 3);
    if (!items.length) return;
    const copy = document.createElement("span");
    copy.className = "session-link-copy";
    copy.append(...button.childNodes);
    const thumbnails = document.createElement("span");
    thumbnails.className = "session-link-thumbnails";
    thumbnails.setAttribute("aria-hidden", "true");
    items.forEach((reference) => {
      const image = document.createElement("img");
      image.className = "session-link-thumbnail";
      image.src = reference.content_url;
      image.alt = "";
      image.title = reference.label || "Image du parcours";
      image.loading = "lazy";
      image.decoding = "async";
      image.draggable = false;
      image.addEventListener("error", () => {
        image.remove();
        if (!thumbnails.childElementCount) {
          thumbnails.remove();
          button.classList.remove("has-session-thumbnails");
        }
      }, { once: true });
      thumbnails.append(image);
    });
    button.classList.add("has-session-thumbnails");
    button.append(copy, thumbnails);
  }

  window.PanelForgeLabCore = Object.freeze({
    request,
    streamRequest,
    updateStreamState,
    failStreamState,
    createReasoningTrace,
    playCompletionTone,
    playFailureTone,
    createLlmOutcomeTone,
    decorateSessionLink,
  });
})();
