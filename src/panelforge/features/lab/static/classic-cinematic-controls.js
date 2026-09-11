(() => {
  "use strict";
  const isCinematic = (value) => value?.preparation?.family === "classic" && value.preparation.version === "1.0.0";
  function create({ prefix, state, elements, recipes, render, busy, steps }) {
    const get = (name) => document.getElementById(`${prefix}-${name}`);
    const version = get("classic-version"), controls = get("cinematic-controls"), shots = get("cinematic-shots");
    const summary = get("cinematic-summary");
    let hydrated = null;
    const current = () => isCinematic(state.session || state.cookbook);
    function restore(settings) { shots.value = settings?.shot_count == null ? "auto" : String(settings.shot_count); }
    function payload() { return current() ? { shot_count: shots.value === "auto" ? null : Number(shots.value) } : null; }
    function choose() {
      if (state.session || busy()) return render();
      const experimental = version.value === "1.0.0";
      const choices = recipes().filter(item => (item.preparation?.family || "classic") === "classic"
        && isCinematic(item) === experimental && window.PanelForgeLabCore.recipeTier(`${item.id}@${item.version}`) !== "historical");
      const previousMulti = Boolean(state.cookbook?.id?.includes(".multishot"));
      const next = choices.find(item => item.preparation_steps === steps() && Boolean(item.id?.includes(".multishot")) === previousMulti)
        || choices.find(item => item.preparation_steps === steps()) || choices[0];
      if (next) { state.cookbook = next; elements.creativeDirection.checked = false; }
      render();
    }
    function draw(cookbook) {
      const value = state.session || cookbook;
      const classic = (value?.preparation?.family || "classic") === "classic";
      const experimental = isCinematic(value);
      version.closest("label").hidden = !classic;
      version.value = experimental ? "1.0.0" : "legacy";
      version.disabled = Boolean(state.session) || busy();
      controls.hidden = !experimental;
      shots.disabled = Boolean(state.session) || busy();
      const origin = state.session || state.forkSource;
      if (origin && hydrated !== origin.id) { restore(origin.cinematic_settings); hydrated = origin.id; }
      if (!origin) hydrated = null;
      elements.cookbook.dataset.classicVersion = classic ? version.value : "";
      if (experimental && elements.sequenceKind) elements.sequenceKind.closest("label").hidden = true;
      const chosen = state.composition?.cinematic_sequence?.shot_count;
      summary.textContent = (shots.value === "auto"
        ? "Auto suit le nombre demandé dans l’intention ; sinon le Plan choisit."
        : `${shots.value} plan(s) imposé(s), même si l’intention indique un autre nombre.`)
        + (chosen ? ` ${chosen} plan(s) retenu(s).` : "")
        + " Deux appels : Plan puis rédaction. Plusieurs actions peuvent partager un plan.";
    }
    version.addEventListener("change", choose);
    shots.addEventListener("change", render);
    return Object.freeze({ current, restore, payload, draw, choose });
  }
  window.PanelForgeClassicCinematicControls = Object.freeze({ create, isCinematic });
})();
