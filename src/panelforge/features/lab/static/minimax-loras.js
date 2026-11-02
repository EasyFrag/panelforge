(() => {
  "use strict";
  const summary = entries => (entries || []).map(entry =>
    `${entry.name.replace(/^minmax_nsfw\//i, "")} · ${entry.enabled && entry.strength > 0 ? entry.strength : "désactivé"}`).join(" ; ");

  function mount(container, {api, request, onChange}) {
    if (!container) return null;
    let models = [], entries = [], rows = [], disabled = false, supported = true, loading = null, loaded = false;
    let maximum = 4, picker = null;
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
    const stack = make("div"); stack.className = "minimax-lora-stack";
    const add = make("button", "+ Ajouter un LoRA"); add.type = "button"; add.dataset.loraAdd = "";
    add.addEventListener("click", () => openPicker());
    container.append(heading, hint, stack, add, status);
    const label = name => name.replace(/^minmax_nsfw\//i, "");
    const normalize = value => value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
    const action = (text, title, handler) => {
      const b = make("button", text); b.type = "button"; b.title = title; b.setAttribute("aria-label", title);
      b.addEventListener("click", handler); return b;
    };
    async function info(name, target=status) {
      try { await window.PanelForgeH3LoraInfo.open(name); }
      catch (error) { target.textContent = "Fiche LoRA indisponible : " + error.message; }
    }
    function changed() { controls(); onChange(); }
    function paint() {
      stack.replaceChildren();
      rows = entries.map((entry, index) => {
        const row = make("div"); row.className = "minimax-lora-row";
        const enabledLabel = make("label"), enabled = make("input"); enabled.type = "checkbox";
        enabled.checked = entry.enabled; enabled.setAttribute("aria-label", `Activer le LoRA ${index + 1}`);
        enabledLabel.append(enabled, make("span", String(index + 1)));
        const choose = action(label(entry.name) + (loaded && !models.includes(entry.name) ? " · indisponible" : ""),
          `Remplacer ${label(entry.name)}`, () => openPicker(index));
        choose.className = "krea2-lora-name-button"; choose.dataset.loraChoose = "";
        const strengthLabel = make("label", "Force"), strength = make("input");
        strength.type = "number"; strength.min = "0"; strength.max = "1"; strength.step = "any";
        strength.value = String(entry.strength); strength.required = true;
        strength.setAttribute("aria-label", `Force du LoRA ${index + 1}`);
        strengthLabel.append(strength);
        enabled.addEventListener("change", () => { entry.enabled = enabled.checked; changed(); });
        strength.addEventListener("input", () => {
          if (!strength.validity.valid) { status.textContent = "La force doit être comprise entre 0 et 1."; return; }
          entry.strength = strength.valueAsNumber; changed();
        });
        strength.addEventListener("change", () => { if (!strength.validity.valid) strength.value = String(entry.strength); });
        const actions = make("div"); actions.className = "minimax-lora-actions";
        const move = offset => {
          if (disabled || index + offset < 0 || index + offset >= entries.length) return;
          [entries[index], entries[index + offset]] = [entries[index + offset], entries[index]];
          paint(); onChange();
        };
        const up = action("↑", `Monter le LoRA ${index + 1}`, () => move(-1));
        const down = action("↓", `Descendre le LoRA ${index + 1}`, () => move(1));
        up.dataset.loraUp = ""; down.dataset.loraDown = "";
        const details = action("i", `Informations sur ${label(entry.name)}`, () => info(entry.name));
        const remove = action("×", `Retirer ${label(entry.name)}`, () => {
          if (disabled) return;
          entries.splice(index, 1); paint(); onChange(); add.focus();
        });
        remove.dataset.loraRemove = "";
        actions.append(up, down, details, remove); row.append(enabledLabel, choose, strengthLabel, actions); stack.append(row);
        return {enabled, choose, strength, up, down, details, remove};
      });
      add.textContent = `+ Ajouter un LoRA · ${entries.length}/${maximum}`;
      controls();
    }

    function openPicker(index=null) {
      if (disabled || !supported || (index === null && entries.length >= maximum)) return;
      picker?.dialog.close();
      const dialog = make("dialog"); dialog.className = "krea2-lora-picker-dialog minimax-lora-picker";
      dialog.setAttribute("aria-label", index === null ? "Ajouter un LoRA MiniMax" : "Remplacer un LoRA MiniMax");
      const panel = make("section"), header = make("header");
      const close = action("Fermer", "Fermer le catalogue LoRA", () => dialog.close());
      header.append(make("h3", dialog.getAttribute("aria-label")), close);
      const search = make("input"); search.type = "search"; search.placeholder = "Rechercher un LoRA…";
      search.setAttribute("aria-label", "Rechercher un LoRA MiniMax");
      const count = make("small"), list = make("div"), note = make("small"); note.setAttribute("role", "status");
      list.className = "minimax-lora-picker-results";
      const render = () => {
        list.replaceChildren();
        const used = new Set(entries.filter((_, i) => i !== index).map(e => e.name.toLowerCase()));
        const values = models.filter(name => !used.has(name.toLowerCase()) && normalize(name).includes(normalize(search.value.trim())));
        count.textContent = `${values.length} LoRA disponible${values.length > 1 ? "s" : ""}`;
        if (!values.length) list.append(make("p", "Aucun LoRA ne correspond à cette recherche."));
        for (const name of values) {
          const row = make("article"), identity = make("div");
          identity.append(make("b", label(name)), make("small", name));
          const choose = action(index === null ? "Ajouter" : "Choisir", `Choisir ${label(name)}`, () => {
            if (disabled || !supported || (index === null && entries.length >= maximum)) return;
            if (entries.some((e, i) => i !== index && e.name.toLowerCase() === name.toLowerCase())) return;
            if (index === null) entries.push({name, strength:0.5, enabled:true});
            else entries[index] = {...entries[index], name};
            dialog.close(); paint(); onChange();
          });
          choose.className = "primary"; choose.dataset.loraSelect = "";
          row.append(identity, action("i", `Informations sur ${label(name)}`, () => info(name, note)), choose); list.append(row);
        }
      };
      picker = {dialog, render}; search.addEventListener("input", render);
      panel.append(header, search, count, list, note); dialog.append(panel); document.body.append(dialog);
      dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
      dialog.addEventListener("close", () => { if (picker?.dialog === dialog) picker = null; dialog.remove(); });
      render(); dialog.showModal(); search.focus();
    }
    function controls() {
      refreshButton.disabled = disabled || Boolean(loading);
      add.disabled = disabled || !supported || entries.length >= maximum || !models.length;
      rows.forEach((row, index) => {
        for (const field of Object.values(row)) field.disabled = disabled || !supported;
        row.strength.disabled ||= !entries[index].enabled;
        row.up.disabled ||= index === 0; row.down.disabled ||= index === entries.length - 1;
      });
      if (disabled || !supported) picker?.dialog.close();
    }
    function setValue(value=[]) {
      if (JSON.stringify(entries) === JSON.stringify(value)) return;
      picker?.dialog.close(); entries = value.map(entry => ({...entry})); paint();
    }
    function getValue() {
      if (entries.some(e => !Number.isFinite(e.strength) || e.strength < 0 || e.strength > 1))
        throw new Error("Chaque force LoRA doit être comprise entre 0 et 1.");
      return entries.map(entry => ({...entry}));
    }
    async function refresh(force=false) {
      if (loading) return loading;
      status.textContent = "Chargement des LoRA…";
      loading = (async () => {
        try {
          const result = await request(`${api}/loras${force ? "?refresh=true" : ""}`);
          if (!Array.isArray(result.models)) throw new Error("Catalogue incomplet.");
          models = result.models; supported = result.supported !== false; loaded = true;
          maximum = Math.min(4, result.maximum || 4);
          status.textContent = !supported ? "Les LoRA image nécessitent une mise à jour du workflow MiniMax."
            : result.warning || (models.length ? `${models.length} LoRA disponibles.` : "Aucun LoRA MiniMax disponible.");
          paint(); picker?.render();
        } catch (error) {
          status.textContent = "Catalogue indisponible. Les choix enregistrés sont conservés. " + error.message;
        }
      })();
      controls();
      try { await loading; } finally { loading = null; controls(); }
    }
    refreshButton.addEventListener("click", () => refresh(true));
    paint();
    return {setValue, getValue, refresh, setDisabled(value) { disabled = value; controls(); }};
  }
  window.PanelForgeMinimaxLoras = {mount, summary};
})();
