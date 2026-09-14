(() => {
  "use strict";
  window.PanelForgeH3Checkpoints = {
    mount(prefix, { request, mode, onChange }) {
      const panel = document.getElementById(`${prefix}-checkpoint-panel`);
      if (!panel) return null;
      const select = document.getElementById(`${prefix}-checkpoint`);
      const summary = document.getElementById(`${prefix}-checkpoint-summary`);
      const refresh = document.getElementById(`${prefix}-checkpoint-refresh`);
      const note = document.getElementById(`${prefix}-checkpoint-note`);
      let value = null, config = {}, models = [], warning = "", loaded = false;
      let token = 0, loading = false, disabled = false;
      const label = () => models.find(m => m.name === value)?.label || value || "Par défaut";
      function paint() {
        select.replaceChildren();
        const add = (name, text) => {
          const option = document.createElement("option"); option.value = name; option.textContent = text;
          select.append(option); return option;
        };
        add("", "Par défaut — modèle de la recette");
        models.forEach(m => add(m.name, m.label));
        if (value && !models.some(m => m.name === value)) {
          add(value, `${value}${loaded && !warning ? " · indisponible" : " · à vérifier"}`).disabled = true;
        }
        select.value = value || "";
        select.disabled = disabled || !config.supported;
        refresh.disabled = disabled || loading || !config.supported;
        summary.textContent = `Modèle vidéo · ${label()}`;
        summary.title = value || config.default_label || "Modèle de la recette";
        note.textContent = loading ? "Lecture des checkpoints sur Bucket…" : warning || (
          value ? (loaded && !models.some(m => m.name === value)
            ? "Ce modèle est indisponible. Actualisez la liste ou choisissez un autre checkpoint."
            : "Chargement direct pour le prochain rendu. Les réglages et le prompt restent inchangés.")
          : `Par défaut : ${config.default_label || "modèle de la recette"}.`);
        panel.hidden = !config.supported;
      }
      async function load(force = false) {
        const current = ++token;
        loading = true; paint();
        try {
          const result = await request(`/api/h3-render/checkpoints?mode=${encodeURIComponent(mode)}&refresh=${force}`);
          if (current !== token) return;
          models = result.models || []; warning = result.warning || ""; loaded = true;
        } catch (error) {
          if (current !== token) return;
          warning = error.message; // Keep the choice, including when Bucket is unreachable.
        } finally {
          if (current === token) { loading = false; paint(); }
        }
      }
      select.addEventListener("change", () => { value = select.value || null; paint(); onChange(); });
      panel.addEventListener("toggle", () => { if ((panel.open || panel.tagName !== "DETAILS") && config.supported && !loaded) load(); });
      refresh.addEventListener("click", () => load(true));
      select.addEventListener("focus", () => { if (!loaded && !loading && config.supported) load(); });
      return {
        get value() { return value; },
        get label() { return label(); },
        set(valueToRestore) { value = valueToRestore || null; paint(); },
        configure(spec) {
          ++token; loading = false; config = spec || {}; value = null; warning = ""; paint();
          if ((panel.open || panel.tagName !== "DETAILS") && config.supported && !loaded) load();
        },
        setDisabled(next) { disabled = next; select.disabled = disabled || !config.supported;
          refresh.disabled = disabled || loading || !config.supported; },
      };
    },
  };
})();
