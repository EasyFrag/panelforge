(() => {
  "use strict";
  const summary = entries => (entries || []).map(entry =>
    `${entry.name.replace(/^minmax_nsfw\//i, "")} · ${entry.enabled && entry.strength > 0 ? entry.strength : "désactivé"}`).join(" ; ");

  function mount(container, {api, request, onChange}) {
    if (!container) return null;
    let models = [], disabled = false, supported = true, loading = null, loaded = false;
    const make = (tag, text) => {
      const value = document.createElement(tag);
      if (text !== undefined) value.textContent = text;
      return value;
    };
    container.classList.add("minimax-loras");
    const heading = make("div"), title = make("b", "LoRA MiniMax · optionnels");
    const refreshButton = make("button", "↻");
    refreshButton.type = "button"; refreshButton.title = "Actualiser les LoRA";
    refreshButton.setAttribute("aria-label", "Actualiser les LoRA MiniMax");
    heading.append(title, refreshButton);
    const hint = make("small", "Jusqu’à 4 LoRA. Force de 0 à 1 ; 0 désactive l’effet. Les choix sont conservés avec chaque essai.");
    const status = make("small"); status.setAttribute("role", "status");
    const rows = Array.from({length:4}, (_, index) => {
      const row = make("div"); row.className = "minimax-lora-row";
      const enabledLabel = make("label"), enabled = make("input"); enabled.type = "checkbox";
      enabled.setAttribute("aria-label", `Activer le LoRA ${index + 1}`);
      enabledLabel.append(enabled, make("span", String(index + 1)));
      const select = make("select"); select.setAttribute("aria-label", `LoRA MiniMax ${index + 1}`);
      select.append(new Option("Sans LoRA", ""));
      const strengthLabel = make("label", "Force"), strength = make("input"), value = make("output", "0.5");
      strength.type = "range"; strength.min = "0"; strength.max = "1"; strength.step = "any"; strength.value = "0.5";
      strength.setAttribute("aria-label", `Force du LoRA ${index + 1}`);
      strengthLabel.append(strength, value);
      const changed = () => { controls(); onChange(); };
      select.addEventListener("change", () => { enabled.checked = Boolean(select.value); changed(); });
      enabled.addEventListener("change", changed);
      strength.addEventListener("input", () => { value.value = strength.value; changed(); });
      row.append(enabledLabel, select, strengthLabel);
      return {row, select, enabled, strength, value};
    });
    container.append(heading, hint, ...rows.map(r => r.row), status);

    function options(row, selected) {
      if (row.select.dataset.catalog === JSON.stringify([models, selected])) return;
      row.select.replaceChildren(new Option("Sans LoRA", ""));
      for (const name of models) row.select.append(new Option(name.replace(/^minmax_nsfw\//i, ""), name));
      if (selected && !models.includes(selected))
        row.select.append(new Option(selected.replace(/^minmax_nsfw\//i, "") + (loaded ? " · indisponible" : " · enregistré"), selected));
      row.select.value = selected;
      row.select.dataset.catalog = JSON.stringify([models, selected]);
    }
    function controls() {
      refreshButton.disabled = disabled || Boolean(loading);
      for (const row of rows) {
        row.select.disabled = disabled || !supported;
        row.enabled.disabled = disabled || !supported || !row.select.value;
        row.strength.disabled = disabled || !supported || !row.select.value || !row.enabled.checked;
      }
    }
    function setValue(entries=[]) {
      rows.forEach((row, index) => {
        const entry = entries[index];
        options(row, entry?.name || "");
        row.enabled.checked = Boolean(entry?.enabled);
        row.strength.value = String(entry?.strength ?? 0.5); row.value.value = row.strength.value;
      });
      controls();
    }
    function getValue() {
      return rows.filter(row => row.select.value).map(row => ({name:row.select.value,
        enabled:row.enabled.checked, strength:Number(row.strength.value)}));
    }
    async function refresh(force=false) {
      if (loading) return loading;
      status.textContent = "Chargement des LoRA…";
      loading = (async () => {
        try {
          const result = await request(`${api}/loras${force ? "?refresh=true" : ""}`);
          if (!Array.isArray(result.models)) throw new Error("Catalogue incomplet.");
          models = result.models; supported = result.supported !== false; loaded = true;
          status.textContent = !supported ? "Les LoRA image nécessitent une mise à jour du workflow MiniMax."
            : result.warning || (models.length ? `${models.length} LoRA disponibles.` : "Aucun LoRA MiniMax disponible.");
          rows.forEach(row => { delete row.select.dataset.catalog; options(row, row.select.value); });
        } catch (error) {
          status.textContent = "Catalogue indisponible. Les choix enregistrés sont conservés. " + error.message;
        }
      })();
      controls();
      try { await loading; } finally { loading = null; controls(); }
    }
    refreshButton.addEventListener("click", () => refresh(true));
    controls();
    return {setValue, getValue, refresh, setDisabled(value) { disabled = value; controls(); }};
  }
  window.PanelForgeMinimaxLoras = {mount, summary};
})();
