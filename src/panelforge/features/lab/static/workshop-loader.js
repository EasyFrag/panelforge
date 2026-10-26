(() => {
  "use strict";

  // Explicit groups preserve the synchronous helpers and event contracts within
  // each workshop. H3 and REF2V share their renderer and conversion events.
  const groups = {
    video: {files: ["quick-pipeline.js", "classic-cinematic-controls.js", "combat-controls.js",
      "sensual-controls.js", "prompt-writer-model.js", "chinese-prompt-variant.js",
      "h3-render-lab.js", "dance.js", "h3-conversion.js", "i2v-direct.js", "ref2v-direct.js"]},
    stories: {needs: ["video"], files: ["story-continuity.js", "story-followup.js", "story-writing.js",
      "stories.js", "stories-help.js", "episode-localization.js", "episode-thumbnail-layout.js",
      "episode-thumbnails.js", "episodes.js", "story-library.js"]},
    edit: {files: ["krea2-retouch.js", "image-crop.js", "krea2-edit-lab.js"]},
    qwen: {files: ["qwen-edit-v2.js"]},
    journey: {files: ["image-journey-actions.js", "image-journeys.js"]},
    transitions: {files: ["image-transition-references.js", "image-transitions.js"]},
    storyV2: {files: ["story-v2-settings.js", "story-v2.js"]},
    recipes: {files: ["recipes.js"]},
    social: {files: ["social-lab.js"]},
    analysis: {files: ["media-analysis-media.js", "media-analysis-speech.js", "media-analysis.js"]},
    batch: {files: ["creation-batch.js"]},
  };
  const views = {
    "i2v-direct": "video", "ref2v-direct": "video", stories: "stories",
    "krea2-edit-lab": "edit", "qwen-edit-lab": "qwen", "minimax-edit-lab": "qwen",
    "image-journey": "journey", "image-transitions": "transitions", "story-v2": "storyV2",
    recipes: "recipes", "social-lab": "social", "media-analysis": "analysis", "creation-batch": "batch",
  };
  // Only awaitable public actions are bridged. Synchronous rendering helpers
  // are eager, or loaded as explicit dependencies before their consumers.
  const bridges = {
    PanelForgeH3Base: ["video", ["open", "prefillFirstFrame", "prefillAnalysis"]],
    PanelForgeRef2V: ["video", ["open", "prefillAnalysis"]],
    PanelForgeStories: ["stories", ["open"]],
    PanelForgeEpisodes: ["stories", ["prepareLibraryNavigation", "openFromLibrary"]],
    PanelForgeKrea2Edit: ["edit", ["openSourceId"]],
    PanelForgeQwenEdit: ["qwen", ["open"]],
    PanelForgeMinimaxEdit: ["qwen", ["open"]],
    PanelForgeImageTransitions: ["transitions", ["open"]],
    PanelForgeStoryV2: ["storyV2", ["open"]],
    PanelForgeRecipes: ["recipes", ["open", "fromImage"]],
    PanelForgeSocialLab: ["social", ["open"]],
  };
  const files = new Map(), pending = new Map(), loaded = new Set(), stubs = new Map();
  const panels = new WeakMap();
  const boot = document.readyState === "complete" ? Promise.resolve() : new Promise(resolve =>
    document.addEventListener("DOMContentLoaded", resolve, {once: true}));

  function loadFile(name) {
    if (files.has(name)) return files.get(name);
    const promise = new Promise((resolve, reject) => {
      const template = document.querySelector(`template[data-lab-script="${name}"]`);
      const source = template?.content.querySelector("script")?.src;
      if (!source) { reject(new Error(`Fichier d’atelier absent : ${name}. Rechargez la page.`)); return; }
      const script = document.createElement("script");
      script.src = source;
      script.async = false;
      let executionError = null;
      const onError = event => {
        if (event.filename === source) executionError = new Error(`Erreur dans ${name}. Rechargez la page.`);
      };
      window.addEventListener("error", onError);
      script.onload = () => {
        window.removeEventListener("error", onError);
        // Retain execution failures: retrying a partly executed module could
        // register handlers twice. Only download failures may be retried.
        if (executionError) reject(executionError);
        else resolve();
      };
      script.onerror = () => {
        window.removeEventListener("error", onError);
        files.delete(name);
        script.remove();
        reject(new Error(`Chargement de ${name} impossible. Réessayez ou rechargez la page.`));
      };
      document.head.append(script);
    });
    files.set(name, promise);
    return promise;
  }

  function ensure(group) {
    if (loaded.has(group)) return Promise.resolve();
    if (pending.has(group)) return pending.get(group);
    const promise = (async () => {
      await boot; // shared eager helpers must finish before any workshop runs
      const definition = groups[group];
      if (!definition) throw new Error(`Atelier inconnu : ${group}`);
      await Promise.all((definition.needs || []).map(ensure));
      for (const file of definition.files) await loadFile(file);
      for (const [name, [owner, methods]] of Object.entries(bridges)) {
        if (owner !== group) continue;
        if (window[name] === stubs.get(name) || methods.some(method => typeof window[name]?.[method] !== "function")) {
          throw new Error(`Atelier incomplet : ${name}. Rechargez la page.`);
        }
      }
      loaded.add(group);
    })();
    pending.set(group, promise);
    promise.then(() => pending.delete(group), () => pending.delete(group));
    return promise;
  }

  function panelFor(root) {
    if (panels.has(root)) return panels.get(root);
    const panel = document.createElement("div");
    panel.className = "workshop-loading";
    panel.hidden = true;
    panel.setAttribute("role", "status");
    const text = document.createElement("span"), retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = "Réessayer";
    panel.append(text, retry);
    root.before(panel); // retry remains accessible while the workshop is inert
    const state = {panel, text, retry, task: null};
    panels.set(root, state);
    new MutationObserver(() => { panel.hidden = root.hidden || !root.inert; })
      .observe(root, {attributes: true, attributeFilter: ["hidden", "inert"]});
    return state;
  }

  function activate(view, root, isCurrent) {
    const group = views[view];
    if (!group || !root) return Promise.resolve();
    const state = panelFor(root);
    if (state.task) return state.task;
    if (loaded.has(group)) {
      if (root.inert) {
        root.inert = false;
        root.removeAttribute("aria-busy");
        state.panel.hidden = true;
        if (isCurrent()) document.dispatchEvent(new CustomEvent("panelforge:workshop-ready", {detail: {view}}));
      }
      return Promise.resolve();
    }
    root.inert = true;
    root.setAttribute("aria-busy", "true");
    state.panel.hidden = root.hidden;
    state.text.textContent = "Chargement de l’atelier…";
    state.retry.hidden = true;
    const task = ensure(group).then(() => {
      root.inert = false;
      root.removeAttribute("aria-busy");
      state.panel.hidden = true;
      if (isCurrent()) document.dispatchEvent(new CustomEvent("panelforge:workshop-ready", {detail: {view}}));
    }).catch(error => {
      root.removeAttribute("aria-busy");
      state.text.textContent = error.message;
      state.retry.hidden = false;
      state.retry.onclick = () => activate(view, root, isCurrent);
    }).finally(() => { state.task = null; });
    state.task = task;
    return task;
  }

  let actionNotice;
  function actionError(error, group) {
    if (!actionNotice) {
      actionNotice = document.createElement("div");
      actionNotice.className = "workshop-loading";
      actionNotice.setAttribute("role", "alert");
      document.querySelector(".topbar")?.after(actionNotice);
    }
    const text = document.createElement("span"), retry = document.createElement("button");
    text.textContent = error.message;
    retry.type = "button";
    retry.textContent = "Recharger l’atelier";
    retry.onclick = async () => {
      retry.disabled = true;
      try {
        await ensure(group);
        text.textContent = "Atelier prêt. Vous pouvez reprendre votre action.";
        retry.remove();
      } catch (failure) { text.textContent = failure.message; retry.disabled = false; }
    };
    actionNotice.replaceChildren(text, retry);
  }

  for (const [name, [group, methods]] of Object.entries(bridges)) {
    const stub = Object.fromEntries(methods.map(method => [method, async (...args) => {
      try { await ensure(group); }
      catch (error) { actionError(error, group); throw error; }
      // Forward exactly once. A failed transfer/mutation is never replayed by
      // the module loader, including when the user retries a script download.
      return window[name][method](...args);
    }]));
    stubs.set(name, stub);
    window[name] = stub;
  }
  window.PanelForgeWorkshops = Object.freeze({activate, load: view => ensure(views[view])});
})();
