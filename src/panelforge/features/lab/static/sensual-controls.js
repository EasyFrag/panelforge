(() => {
  "use strict";

  const isSensual = (value) => value?.preparation?.family === "sensual"
    && value.preparation.version === "1.0.0";

  function create({ prefix, state, elements, recipes, render, busy }) {
    const get = (name) => document.getElementById(`${prefix}-${name}`);
    const controls = get("sensual-controls");
    const shots = get("sensual-shots");
    const summary = get("sensual-summary");
    let hydrated = null;

    const current = () => isSensual(state.session || state.cookbook);

    function restore(settings) {
      shots.value = settings?.shot_count == null ? "auto" : String(settings.shot_count);
    }

    function payload() {
      return current() ? {
        explicitness: "explicit_maximal",
        shot_count: shots.value === "auto" ? null : Number(shots.value),
      } : null;
    }

    function choose() {
      if (state.session || busy()) return render();
      const next = recipes().find((item) => isSensual(item) && item.preparation_steps === 2);
      if (next) {
        state.cookbook = next;
        elements.creativeDirection.checked = false;
      }
      render();
    }

    function draw(cookbook) {
      const value = state.session || cookbook;
      const active = isSensual(value);
      controls.hidden = !active;
      shots.disabled = Boolean(state.session) || busy();
      const origin = state.session || state.forkSource;
      if (origin && hydrated !== origin.id) {
        restore(origin.sensual_settings);
        hydrated = origin.id;
      }
      if (!origin) hydrated = null;
      if (active) elements.cookbook.dataset.preparationVersion = "1.0.0";
      if (active && elements.sequenceKind) elements.sequenceKind.closest("label").hidden = true;
      const chosen = state.composition?.sensual_sequence?.shot_count;
      summary.textContent = (shots.value === "auto"
        ? "Auto suit le nombre demandé dans l’intention ; sinon le Plan choisit."
        : `${shots.value} plan(s) imposé(s), même si l’intention indique un autre nombre.`)
        + (chosen ? ` ${chosen} plan(s) retenu(s).` : "")
        + " Niveau fixe : explicite maximal. Deux appels indépendants : Plan puis rédaction.";
    }

    shots.addEventListener("change", render);
    return Object.freeze({ current, restore, payload, draw, choose });
  }

  window.PanelForgeSensualControls = Object.freeze({ create, isSensual });
})();
