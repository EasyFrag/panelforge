(() => {
  "use strict";
  const levels = ["Modéré", "Dynamique", "Intense", "Déchaîné"];
  const orientations = { mixed: "Libre / mixte", hand_to_hand: "Corps à corps", weapons: "Armes", magic: "Pouvoirs / magie" };
  const orientationLabel = (value) => orientations[value] || "";
  const loraHint = (value) => value === "weapons"
    ? "Au rendu, Weapon Combat peut servir de point de départ. Le LoRA et ses forces restent à ton choix."
    : "Au rendu, Combat V2 peut servir de point de départ. Le LoRA et ses forces restent à ton choix.";
  function create({ prefix, state, elements, recipes, render, busy, steps }) {
    const get = (id) => document.querySelector(`#${prefix}-${id}`);
    const version = get("combat-version"), controls = get("combat-controls");
    const action = get("combat-action"), actionValue = get("combat-action-value"), shots = get("combat-shots");
    const orientation = get("combat-orientation"), orientationHint = get("combat-orientation-hint");
    let hydrated = null;
    const active = () => state.session?.preparation || state.cookbook?.preparation;
    const current = () => active()?.family === "combat" && ["1.1.0", "1.1.1", "1.2.0", "1.3.0"].includes(active()?.version);
    function restore(settings) {
      action.value = String(settings?.action_level ?? 1);
      shots.value = settings?.shot_count === null ? "auto" : String(settings?.shot_count ?? 1);
      actionValue.value = levels[Number(action.value)];
      if (orientation) orientation.value = settings?.orientation || "mixed";
    }
    function payload() {
      if (!current()) return null;
      const settings = { action_level: Number(action.value), shot_count: shots.value === "auto" ? null : Number(shots.value) };
      if (["1.2.0", "1.3.0"].includes(active()?.version)) settings.orientation = orientation?.value || "mixed";
      return settings;
    }
    function choose(family = "combat", wantedVersion = version.value) {
      if (state.session || busy()) return render();
      const choices = recipes().filter(item => item.preparation?.family === family && item.preparation.version === wantedVersion);
      const oldMulti = Boolean(state.cookbook?.profile?.id?.endsWith(".multishot"));
      const next = choices.find(item => item.preparation_steps === steps() && Boolean(item.profile?.id?.endsWith(".multishot")) === oldMulti)
        || choices.find(item => item.preparation_steps === steps()) || choices[0];
      if (!next) return;
      state.cookbook = next;
      elements.creativeDirection.checked = false;
      render();
    }
    function draw(cookbook) {
      const preparation = state.session?.preparation || cookbook?.preparation;
      const combat = preparation?.family === "combat";
      const modern = combat && ["1.1.0", "1.1.1", "1.2.0", "1.3.0"].includes(preparation.version);
      const specialized = combat && ["1.2.0", "1.3.0"].includes(preparation.version);
      version.closest("label").hidden = !combat;
      if (combat) version.value = preparation.version;
      version.disabled = Boolean(state.session) || busy();
      controls.hidden = !modern;
      const origin = state.session || state.forkSource;
      if (origin && hydrated !== origin.id) { restore(origin.combat_settings); hydrated = origin.id; }
      if (!origin) hydrated = null;
      action.disabled = shots.disabled = Boolean(state.session) || busy();
      if (orientation) {
        const magic = orientation.querySelector('option[value="magic"]');
        if (magic) magic.hidden = magic.disabled = preparation?.version !== "1.3.0";
        if (preparation?.version !== "1.3.0" && orientation.value === "magic") orientation.value = "mixed";
        orientation.closest("label").hidden = !specialized;
        orientation.disabled = !specialized || Boolean(state.session) || busy();
        if (orientationHint) orientationHint.textContent = loraHint(orientation.value);
      }
      actionValue.value = levels[Number(action.value)];
      elements.cookbook.dataset.preparationVersion = combat ? preparation.version : "";
      if (elements.sequenceKind) elements.sequenceKind.closest("label").hidden = modern;
      // Existing extra-motion keeps its original value and remains visible for old recipes.
      if (elements.creativeExtraMotion) elements.creativeExtraMotion.closest("label").hidden = modern;
      const hint = elements.creativeAudacityControl?.querySelector("small");
      if (modern && hint) hint.textContent = "Liberté d’invention tactique · distincte de la quantité d’action";
      const summary = get("combat-summary");
      if (modern && summary) {
        const chosen = state.composition?.combat_sequence?.shot_count;
        summary.textContent = `${levels[Number(action.value)]} · ${shots.value === "auto" ? "Plans : Auto" : `${shots.value} plan(s)`}`
          + (specialized ? ` · ${orientationLabel(orientation?.value || "mixed")}` : "")
          + (preparation.version === "1.3.0" ? " · 2 appels : Plan puis rédaction." : "")
          + (chosen ? ` · ${chosen} plan(s) retenu(s)` : "")
          + (state.session ? " · Réglages conservés dans cet atelier." : " · Chaque plan peut contenir plusieurs combinaisons.");
      }
    }
    version.addEventListener("change", () => choose());
    action.addEventListener("input", render);
    shots.addEventListener("change", render);
    orientation?.addEventListener("change", render);
    return Object.freeze({ payload, draw, choose, restore, current });
  }
  window.PanelForgeCombatControls = Object.freeze({ create, orientationLabel });
})();
