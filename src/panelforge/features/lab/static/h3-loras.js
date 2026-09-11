(() => {
  "use strict";
  const copy = value => structuredClone(value);
  window.PanelForgeH3Loras = {
    summary(stack) {
      if (!stack) return "";
      if (!stack.enabled) return "LoRA désactivés";
      if (!stack.entries.length) return "Aucun LoRA";
      return stack.entries.map((entry, i) => `${i + 1}. ${entry.name} ${entry.enabled
        ? `× ${entry.strength}${entry.second_strength == null ? "" : ` / ${entry.second_strength}`}` : "· désactivé"}`).join(" → ");
    },
    mount(prefix, { request, onChange }) {
      const root = document.getElementById(`${prefix}-lora-stack`);
      if (!root) return null;
      let config = {}, data = null, models = [], warning = "", disabled = false, loading = false, token = 0;
      const perPass = () => config.mode === "per_pass";
      const maximum = () => config.maximum ?? 2;
      const restoreData = value => ({ ...copy(value), version: config.defaults?.version || value.version });
      const validForce = value => Number.isFinite(value) && value >= 0 && value <= 1;
      function error() {
        if (!config.supported || !data) return "";
        if (data.entries.length > maximum()) return `Cette recette accepte ${maximum()} LoRA au maximum. Choisissez une recette plus récente ou retirez des lignes.`;
        const names = new Set();
        for (const entry of data.entries) {
          if (!entry.name || names.has(entry.name.toLowerCase())) return "Choisissez des fichiers LoRA distincts.";
          names.add(entry.name.toLowerCase());
          if (!validForce(entry.strength) || (perPass() && !validForce(entry.second_strength))) return "Chaque force LoRA doit être comprise entre 0 et 1.";
          if (data.enabled && entry.enabled && !models.includes(entry.name)) return `LoRA indisponible : ${entry.name}. Actualisez ou désactivez cette ligne.`;
        }
        return "";
      }
      function note() {
        const element = root.querySelector("[data-lora-note]");
        if (element) element.textContent = loading ? "Lecture des LoRA sur ComfyUI…" : error() || warning || (
          `${data.entries.length}/${maximum()} LoRA · ` + (perPass() ? "Ordre identique dans les deux passes. Chaque passe utilise ses propres forces." : "Les LoRA s’appliquent dans l’ordre des lignes."));
      }
      function controls() {
        root.querySelectorAll("input, select, button").forEach(el => {
          const row = el.closest("[data-lora-row]");
          const inactive = row && !data.entries[Number(row.dataset.loraRow)].enabled;
          el.disabled = disabled || (inactive && el.matches("select, input[type=number]"));
          if (el.matches("[data-lora-add]")) el.disabled ||= data.entries.length >= maximum() || !models.some(name => !data.entries.some(e => e.name === name));
          if (el.matches("[data-lora-swap]")) el.disabled ||= data.entries.length < 2;
          if (el.matches("[data-lora-up]")) el.disabled ||= Number(row.dataset.loraRow) === 0;
          if (el.matches("[data-lora-down]")) el.disabled ||= Number(row.dataset.loraRow) === data.entries.length - 1;
          if (el.matches("[data-lora-refresh]")) el.disabled ||= loading;
          if (el.matches("[data-lora-info]")) el.disabled = el.dataset.loading === "true";
        });
      }
      function changed() { note(); controls(); onChange(); }
      function add() {
        const name = models.find(value => !data.entries.some(entry => entry.name === value));
        if (!name || data.entries.length >= maximum()) return;
        data.entries.push({ name, strength: perPass() ? 0.6 : 0.5, second_strength: perPass() ? 0.2 : null, enabled: true });
        paint(); onChange();
      }
      async function refresh() {
        const current = ++token; loading = true; note(); controls();
        try {
          const result = await request("/api/h3-render/video-loras?refresh=true");
          if (current !== token) return;
          models = result.models || []; warning = result.warning || "";
        } catch (err) { if (current === token) warning = err.message; }
        finally { if (current === token) { loading = false; paint(); onChange(); } }
      }
      function paint() {
        root.hidden = !config.supported || !data?.enabled;
        if (!config.supported || !data) return;
        root.replaceChildren();
        const rows = document.createElement("div"); rows.className = "h3-lora-rows";
        data.entries.forEach((entry, index) => {
          const row = document.createElement("div"); row.className = "h3-lora-row"; row.dataset.loraRow = index;
          const enabled = document.createElement("label"); enabled.className = "h3-lora-enabled";
          const check = document.createElement("input"); check.type = "checkbox"; check.checked = entry.enabled;
          check.dataset.loraEnabled = ""; check.setAttribute("aria-label", `Activer le LoRA ${index + 1}`);
          check.addEventListener("change", () => { entry.enabled = check.checked; changed(); });
          enabled.append(check, document.createTextNode(String(index + 1))); row.append(enabled);
          const label = document.createElement("label"); label.className = "h3-lora-model"; label.append(document.createTextNode("LoRA vidéo"));
          const select = document.createElement("select"); select.dataset.loraModel = ""; select.setAttribute("aria-label", `Fichier LoRA ${index + 1}`);
          const choices = models.includes(entry.name) ? models : [entry.name, ...models];
          choices.forEach(name => {
            const option = document.createElement("option"); option.value = name;
            option.textContent = models.includes(name) ? name : `${name} · indisponible`;
            option.disabled = !models.includes(name) || data.entries.some((e, i) => i !== index && e.name === name);
            select.append(option);
          });
          select.value = entry.name; select.title = entry.name;
          select.addEventListener("change", () => { entry.name = select.value; paint(); onChange(); });
          label.append(select); row.append(label);
          for (const [key, title] of [["strength", perPass() ? "Passe 1" : "Force"], ...(perPass() ? [["second_strength", "Passe 2"]] : [])]) {
            const force = document.createElement("label"); force.className = "h3-lora-force"; force.textContent = title;
            const field = document.createElement("input"); field.type = "number"; field.min = "0"; field.max = "1"; field.step = "0.05";
            field.value = String(entry[key]); field.dataset.loraForce = key; field.setAttribute("aria-label", `${title} du LoRA ${index + 1}`);
            field.addEventListener("input", () => { entry[key] = field.value === "" ? NaN : Number(field.value); changed(); });
            force.append(field); row.append(force);
          }
          const rowActions = document.createElement("div"); rowActions.className = "h3-lora-actions";
          for (const [name, text, direction] of [["Up", "↑", -1], ["Down", "↓", 1]]) {
            const button = document.createElement("button"); button.type = "button"; button.textContent = text;
            button.dataset[`lora${name}`] = "";
            button.title = `${direction < 0 ? "Monter" : "Descendre"} le LoRA ${index + 1}`; button.setAttribute("aria-label", button.title);
            button.addEventListener("click", () => {
              const target = index + direction;
              if (disabled || target < 0 || target >= data.entries.length) return;
              [data.entries[index], data.entries[target]] = [data.entries[target], data.entries[index]];
              paint(); onChange();
            });
            rowActions.append(button);
          }
          const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×"; remove.title = "Retirer ce LoRA";
          const info = document.createElement("button"); info.type = "button"; info.textContent = "i";
          info.className = "resource-icon-button"; info.dataset.loraInfo = "";
          info.title = "Ouvrir la fiche du LoRA"; info.setAttribute("aria-label", `Informations sur le LoRA ${index + 1}`);
          info.addEventListener("click", async () => {
            info.dataset.loading = "true"; controls();
            try { await window.PanelForgeH3LoraInfo.open(entry.name); }
            catch (err) { warning = `Fiche LoRA indisponible : ${err.message}`; note(); }
            finally { info.dataset.loading = "false"; controls(); }
          });
          rowActions.append(info);
          remove.dataset.loraRemove = ""; remove.setAttribute("aria-label", `Retirer le LoRA ${index + 1}`);
          remove.addEventListener("click", () => { data.entries.splice(index, 1); paint(); onChange(); }); rowActions.append(remove); row.append(rowActions); rows.append(row);
        });
        root.append(rows);
        const actions = document.createElement("div"); actions.className = "h3-lora-actions";
        for (const [name, label, action] of [["Add", "+ Ajouter un LoRA", add], ["Swap", "Inverser l’ordre", () => { data.entries.reverse(); paint(); onChange(); }], ["Refresh", "Actualiser la liste", refresh]]) {
          const button = document.createElement("button"); button.type = "button"; button.textContent = label; button.dataset[`lora${name}`] = "";
          button.addEventListener("click", action); if (name === "Add") button.hidden = data.entries.length >= maximum(); actions.append(button);
        }
        if (!perPass()) {
          const label = document.createElement("label"); label.className = "h3-lora-clip";
          const check = document.createElement("input"); check.type = "checkbox"; check.checked = data.clip_last_layer === -2; check.dataset.loraClip = "";
          check.addEventListener("change", () => { data.clip_last_layer = check.checked ? -2 : null; changed(); });
          label.append(check, document.createTextNode("CLIP Last Layer · -2")); actions.append(label);
        }
        root.append(actions);
        const message = document.createElement("small"); message.dataset.loraNote = ""; message.setAttribute("role", "status"); root.append(message);
        note(); controls();
      }
      return {
        get supported() { return Boolean(config.supported); },
        get value() { return config.supported ? copy(data) : null; },
        get error() { return error(); },
        configure(spec, inventory) {
          ++token; loading = false; config = spec || {}; models = inventory?.models || []; warning = inventory?.warning || "";
          data = config.supported ? copy(config.defaults) : null; paint();
        },
        restore(value) { if (config.supported && value) { data = restoreData(value); paint(); } },
        restoreAttempt(attempt) {
          if (!config.supported) return;
          data = attempt.video_loras ? restoreData(attempt.video_loras) : {
            version: config.defaults?.version || "0.1.0", enabled: Boolean(attempt.video_lora), clip_last_layer: perPass() ? null : attempt.video_lora?.clip_last_layer ?? -2,
            entries: attempt.video_lora ? [{ name: attempt.video_lora.name, strength: attempt.video_lora.strength,
              second_strength: perPass() ? attempt.bunny?.lora_second_strength ?? 0.2 : null, enabled: true }] : [],
          };
          // An explicit null CLIP setting is distinct from an absent legacy value.
          if (!perPass() && attempt.video_lora && "clip_last_layer" in attempt.video_lora) data.clip_last_layer = attempt.video_lora.clip_last_layer;
          paint();
        },
        setEnabled(enabled) {
          if (!config.supported) return;
          const activated = !data.enabled && enabled; data.enabled = enabled;
          if (activated && data.entries.length === 0) add();
          root.hidden = !enabled; controls(); note();
        },
        setDisabled(value) { disabled = value; if (config.supported) controls(); },
      };
    },
  };
})();
