(() => {
  "use strict";

  const modelGroups = Object.freeze({
    favorite_bf16: "Favoris · BF16",
    favorite_int8: "Favoris · INT8",
    favorite_unknown: "Favoris · précision inconnue",
    bf16: "BF16",
    int8: "INT8",
    unknown: "ComfyUI · précision inconnue",
  });
  const loraGroups = Object.freeze({
    favorite: "Favoris",
    sfw_utility: "SFW · Utility",
    sfw_style: "SFW · Style",
    sfw_sliders: "SFW · Sliders",
    nsfw_utility: "NSFW · Utility",
    nsfw_global: "NSFW · Global",
    nsfw_sliders: "NSFW · Sliders",
    nsfw_details: "NSFW · Details",
    nsfw_poses: "NSFW · Poses",
    unclassified: "Non classés",
  });
  const loraManagerGroups = Object.freeze([
    ["sfw_utility", "SFW · Utility"],
    ["sfw_style", "SFW · Style"],
    ["sfw_sliders", "SFW · Sliders"],
    ["nsfw_utility", "NSFW · Utility"],
    ["nsfw_global", "NSFW · Global"],
    ["nsfw_sliders", "NSFW · Sliders"],
    ["nsfw_details", "NSFW · Details"],
    ["nsfw_poses", "NSFW · Poses"],
    ["excluded_krea_edit", "Other · KREA EDIT — ne pas utiliser"],
    ["unclassified", "Non classé"],
  ]);
  const modelPickerBindings = new WeakMap();

  function appendGroupedOptions(select, resources, labels, { includeEmpty = false } = {}) {
    select.replaceChildren();
    if (includeEmpty) {
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Aucun";
      select.append(empty);
    }
    Object.entries(labels).forEach(([category, label]) => {
      const values = resources.filter(
        (resource) => resource.selectable !== false && resource.category === category,
      );
      if (!values.length) return;
      const group = document.createElement("optgroup");
      group.label = label;
      values.forEach((resource) => {
        const option = document.createElement("option");
        option.value = resource.comfy_name;
        option.textContent = resource.display_name || resource.filename || resource.comfy_name;
        option.title = resource.relative_path || resource.comfy_name;
        group.append(option);
      });
      select.append(group);
    });
  }

  function resourceName(resource) {
    return resource && (resource.display_name || resource.filename || resource.comfy_name) || "Ressource inconnue";
  }

  function categoryLabel(resource) {
    return loraManagerGroups.find(([value]) => value === resource?.lora_category)?.[1] || "Non classé";
  }

  function formatSize(resource) {
    const gib = Number(resource?.size_gib);
    if (Number.isFinite(gib) && gib > 0) return `${gib.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} Gio`;
    const bytes = Number(resource?.size_bytes);
    if (Number.isFinite(bytes) && bytes > 0) return `${(bytes / 1024 ** 2).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mio`;
    return null;
  }

  function normalizeSearch(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("fr");
  }

  function preferenceForLoraCategory(category) {
    return { category };
  }

  function updateResource(resource, updated) {
    if (!resource || !updated || updated.resource_id !== resource.resource_id) return resource;
    Object.assign(resource, updated);
    return resource;
  }

  function favoriteButton(resource, updatePreference, onUpdate = () => {}) {
    const favorite = document.createElement("button");
    favorite.type = "button";
    favorite.className = "resource-icon-button krea2-resource-favorite";
    const paint = () => {
      favorite.textContent = resource?.favorite ? "★" : "☆";
      favorite.title = resource?.favorite ? "Retirer des favoris" : "Ajouter aux favoris";
      favorite.setAttribute("aria-label", `${favorite.title} : ${resourceName(resource)}`);
    };
    paint();
    favorite.disabled = !resource;
    if (resource) favorite.addEventListener("click", async () => {
      favorite.disabled = true;
      try {
        const updated = await updatePreference(resource, { favorite: !resource.favorite });
        if (updated && updated.resource_id) {
          updateResource(resource, updated);
          onUpdate(resource);
          paint();
        }
      } finally {
        favorite.disabled = false;
      }
    });
    return favorite;
  }

  function infoButton(resource, updatePreference, refreshResource, compact = true, onUpdate = () => {}) {
    const info = document.createElement("button");
    info.type = "button";
    info.className = `krea2-resource-info${compact ? " compact" : ""}`;
    info.textContent = "i";
    info.title = resource ? "Afficher la fiche locale et les aperçus" : "Fiche indisponible";
    info.setAttribute("aria-label", resource ? `Informations sur ${resourceName(resource)}` : "Fiche indisponible");
    info.disabled = !resource;
    if (resource) info.addEventListener("click", () => openResourceInfo(
      resource, updatePreference, refreshResource, onUpdate,
    ));
    return info;
  }

  function openResourceInfo(
    resource,
    updatePreference = () => Promise.resolve(false),
    refreshResource = null,
    onUpdate = () => {},
  ) {
    const dialog = document.createElement("dialog");
    dialog.className = "krea2-resource-dialog";
    const panel = document.createElement("section");
    const header = document.createElement("header");
    const title = document.createElement("h3");
    title.textContent = resourceName(resource);
    const dismiss = () => {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.remove();
    };
    const favorite = favoriteButton(resource, updatePreference, onUpdate);
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fermer";
    close.addEventListener("click", dismiss);
    const headerActions = document.createElement("div");
    headerActions.className = "krea2-resource-dialog-header-actions";
    headerActions.append(favorite, close);
    header.append(title, headerActions);

    const facts = document.createElement("dl");
    const addFact = (label, value, editableField = "") => {
      const term = document.createElement("dt");
      term.textContent = label;
      const description = document.createElement("dd");
      const text = document.createElement("span");
      text.textContent = value ?? "Non renseigné";
      description.append(text);
      if (editableField) {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "krea2-resource-edit-button";
        edit.textContent = "✎";
        edit.title = `Modifier ${label.toLocaleLowerCase("fr")}`;
        edit.setAttribute("aria-label", edit.title);
        edit.addEventListener("click", () => openEditor(editableField));
        description.append(edit);
      }
      facts.append(term, description);
    };
    addFact("Fichier", resource.relative_path || resource.comfy_name);
    addFact("Taille", formatSize(resource));
    if (resource.kind === "model") {
      const precision = resource.precision && resource.precision !== "unknown"
        ? resource.precision.toUpperCase()
        : "Inconnue";
      const source = ({ size: "taille", filename: "nom", manual: "manuel" })[resource.precision_source];
      addFact("Précision", `${precision}${source ? ` · ${source}` : ""}`);
    }
    if (resource.sha256) addFact("Hash fourni par la sidecar", resource.sha256);
    addFact("Nom", resource.display_name, "display-name");
    addFact("Modèle de base", resource.base_model);
    if ((resource.trained_words || []).length) addFact("Mots entraînés", resource.trained_words.join(", "));
    if (resource.kind === "lora") {
      addFact("Force minimale", resource.strength_min, "strength-min");
      addFact("Force maximale", resource.strength_max, "strength-max");
      addFact("Catégorie", categoryLabel(resource));
    }
    addFact("Notes additionnelles", resource.notes, "notes");

    const editor = document.createElement("form");
    editor.className = "krea2-resource-dialog-editor";
    editor.hidden = true;
    const nameInput = document.createElement("input");
    nameInput.id = `krea2-resource-display-name-${resource.resource_id}`;
    nameInput.type = "text";
    nameInput.maxLength = 200;
    nameInput.value = resource.display_name || "";
    const nameLabel = document.createElement("label");
    nameLabel.htmlFor = nameInput.id;
    nameLabel.textContent = "Nom affiché";
    nameLabel.append(nameInput);
    const strengthFields = document.createElement("div");
    if (resource.kind === "lora") {
      [
        ["Minimum", "strength-min", resource.strength_min],
        ["Maximum", "strength-max", resource.strength_max],
      ].forEach(([label, suffix, value]) => {
        const input = document.createElement("input");
        input.id = `krea2-resource-${suffix}-${resource.resource_id}`;
        input.type = "number";
        input.min = "-1";
        input.max = "1";
        input.step = "0.05";
        input.value = value ?? "";
        const field = document.createElement("label");
        field.htmlFor = input.id;
        field.textContent = `Force ${label.toLocaleLowerCase("fr")}`;
        field.append(input);
        strengthFields.append(field);
      });
    }
    const notesInput = document.createElement("textarea");
    notesInput.id = `krea2-resource-notes-${resource.resource_id}`;
    notesInput.maxLength = 4000;
    notesInput.rows = 5;
    notesInput.value = resource.notes || "";
    const notesLabel = document.createElement("label");
    notesLabel.htmlFor = notesInput.id;
    notesLabel.textContent = "Notes additionnelles";
    notesLabel.append(notesInput);
    const editorError = document.createElement("p");
    editorError.className = "error-text";
    editorError.hidden = true;
    const editorActions = document.createElement("div");
    const save = document.createElement("button");
    save.type = "submit";
    save.textContent = "Enregistrer";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Annuler";
    cancel.addEventListener("click", () => { editor.hidden = true; });
    editorActions.append(save, cancel);
    editor.append(nameLabel);
    if (resource.kind === "lora") editor.append(strengthFields);
    editor.append(notesLabel, editorError, editorActions);

    function openEditor(field) {
      editor.hidden = false;
      const target = editor.querySelector(`#krea2-resource-${field}-${resource.resource_id}`);
      if (target) target.focus();
      editor.scrollIntoView({ block: "nearest" });
    }

    editor.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = {
        display_name: nameInput.value.trim() || null,
        notes: notesInput.value.trim() || null,
      };
      if (resource.kind === "lora") {
        const strengthInputs = strengthFields.querySelectorAll("input");
        const strengthMin = strengthInputs[0].value.trim() === "" ? null : Number(strengthInputs[0].value);
        const strengthMax = strengthInputs[1].value.trim() === "" ? null : Number(strengthInputs[1].value);
        if (strengthMin !== null && strengthMax !== null && strengthMin > strengthMax) {
          editorError.textContent = "La force minimale doit être inférieure ou égale à la force maximale.";
          editorError.hidden = false;
          return;
        }
        values.strength_min = strengthMin;
        values.strength_max = strengthMax;
      }
      editorError.hidden = true;
      save.disabled = true;
      let saved = false;
      try {
        saved = await updatePreference(resource, values);
      } finally {
        save.disabled = false;
      }
      if (saved === false) {
        editorError.textContent = "Les informations n’ont pas pu être enregistrées.";
        editorError.hidden = false;
        return;
      }
      dismiss();
    });

    const descriptionTitle = document.createElement("h4");
    descriptionTitle.textContent = "Description";
    const description = document.createElement("p");
    description.textContent = resource.description || resource.warning || "Aucune description locale ou CivitAI disponible.";
    const actions = document.createElement("div");
    actions.className = "krea2-resource-dialog-actions";
    if (resource.source_url) {
      const source = document.createElement("a");
      source.href = resource.source_url;
      source.target = "_blank";
      source.rel = "noreferrer";
      source.textContent = "Ouvrir la fiche ou la recherche CivitAI";
      actions.append(source);
    }
    if (typeof refreshResource === "function") {
      const refresh = document.createElement("button");
      refresh.type = "button";
      refresh.textContent = resource.remote_checked_at ? "Actualiser depuis CivitAI" : "Rechercher la fiche CivitAI";
      refresh.title = "Recherche par hash de sidecar s’il existe, sinon par nom de fichier puis par famille, y compris sur CivitAI.red pour le NSFW. Aucun fichier modèle n’est hashé.";
      refresh.addEventListener("click", async () => {
        refresh.disabled = true;
        refresh.textContent = "Recherche en cours…";
        try {
          const updated = await refreshResource(resource);
          if (updated && updated.resource_id) {
            dismiss();
            updateResource(resource, updated);
            onUpdate(resource);
            openResourceInfo(resource, updatePreference, refreshResource, onUpdate);
          } else if (updated === false) {
            refresh.textContent = "Recherche indisponible";
            refresh.disabled = false;
          } else {
            refresh.textContent = "Recherche terminée · rouvrir la fiche";
          }
        } catch (_) {
          refresh.textContent = "Recherche indisponible";
          refresh.disabled = false;
        }
      });
      actions.append(refresh);
    }
    if (resource.remote_checked_at) {
      const checked = document.createElement("small");
      checked.className = "muted";
      checked.textContent = `Vérifié : ${resource.remote_checked_at}`;
      actions.append(checked);
    }
    panel.append(header, facts, editor, descriptionTitle, description, actions);
    let previewLoading = null;
    if ((resource.preview_urls || []).length) {
      const gallery = document.createElement("div");
      gallery.className = "krea2-resource-dialog-gallery";
      resource.preview_urls.slice(0, 3).forEach((url) => {
        const image = document.createElement("img");
        image.src = url;
        image.alt = `Aperçu de ${title.textContent}`;
        image.loading = "eager";
        image.decoding = "async";
        image.referrerPolicy = "no-referrer";
        gallery.append(image);
      });
      panel.append(gallery);
    } else if (typeof refreshResource === "function" && !resource.remote_checked_at) {
      previewLoading = document.createElement("p");
      previewLoading.className = "krea2-resource-dialog-loading muted";
      previewLoading.textContent = "Recherche des aperçus disponibles…";
      panel.append(previewLoading);
    }
    dialog.append(panel);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dismiss();
    });
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    if (previewLoading) {
      Promise.resolve(refreshResource(resource)).then((updated) => {
        if (!dialog.isConnected) return;
        if (!updated || !updated.resource_id) {
          previewLoading.textContent = "Aucun aperçu fiable trouvé.";
          return;
        }
        dismiss();
        updateResource(resource, updated);
        onUpdate(resource);
        openResourceInfo(resource, updatePreference, refreshResource, onUpdate);
      }).catch(() => {
        if (previewLoading.isConnected) {
          previewLoading.textContent = "Aucun aperçu fiable trouvé.";
        }
      });
    }
  }

  function modelCategoryLabel(resource) {
    return modelGroups[resource?.category] || "Précision inconnue";
  }

  function openModelPicker({
    resources,
    selectedName = "",
    onSelect,
    updatePreference,
    refreshResource,
    title = "Choisir un checkpoint KREA2",
  }) {
    const dialog = document.createElement("dialog");
    dialog.className = "krea2-model-picker-dialog krea2-lora-picker-dialog";
    const panel = document.createElement("section");
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = title;
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fermer";
    close.addEventListener("click", () => dialog.close());
    header.append(heading, close);
    const filters = document.createElement("div");
    filters.className = "krea2-lora-picker-filters";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Rechercher un checkpoint, une note…";
    search.setAttribute("aria-label", "Rechercher un checkpoint KREA2");
    const category = document.createElement("select");
    category.setAttribute("aria-label", "Filtrer les checkpoints");
    category.append(
      new Option("Tous les checkpoints", "all"),
      new Option("Favoris", "favorite"),
      new Option("BF16", "bf16"),
      new Option("INT8", "int8"),
      new Option("Précision inconnue", "unknown"),
    );
    filters.append(search, category);
    const resultCount = document.createElement("small");
    resultCount.className = "muted";
    const list = document.createElement("div");
    list.className = "krea2-model-picker-results krea2-lora-picker-results";

    function replaceLocalResource(updated) {
      const current = resources.find((item) => item.resource_id === updated?.resource_id);
      if (current) updateResource(current, updated);
      renderResults();
    }

    function renderResults() {
      const query = normalizeSearch(search.value);
      const categoryValue = category.value;
      const values = resources
        .filter((resource) => resource.selectable !== false)
        .filter((resource) => {
          if (categoryValue === "all") return true;
          if (categoryValue === "favorite") return Boolean(resource.favorite);
          return resource.precision === categoryValue;
        })
        .filter((resource) => !query || normalizeSearch([
          resource.display_name,
          resource.filename,
          resource.relative_path,
          resource.precision,
          resource.notes,
          resource.description,
        ].filter(Boolean).join(" ")).includes(query))
        .sort((left, right) => {
          const groups = Object.keys(modelGroups);
          const groupDifference = groups.indexOf(left.category) - groups.indexOf(right.category);
          if (groupDifference) return groupDifference;
          return resourceName(left).localeCompare(resourceName(right), "fr");
        });
      list.replaceChildren();
      resultCount.textContent = `${values.length} checkpoint${values.length > 1 ? "s" : ""} disponible${values.length > 1 ? "s" : ""}`;
      if (!values.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Aucun checkpoint ne correspond à ces filtres.";
        list.append(empty);
        return;
      }
      values.forEach((resource) => {
        const categoryKey = resource.category || "unknown";
        let group = list.querySelector(`[data-model-category="${categoryKey}"]`);
        if (!group) {
          group = document.createElement("section");
          group.className = "krea2-lora-picker-group";
          group.dataset.modelCategory = categoryKey;
          const groupTitle = document.createElement("h4");
          groupTitle.textContent = modelCategoryLabel(resource);
          group.append(groupTitle, document.createElement("div"));
          list.append(group);
        }
        const row = document.createElement("article");
        if (resource.comfy_name === selectedName) row.classList.add("selected");
        const identity = document.createElement("div");
        const name = document.createElement("b");
        name.textContent = resourceName(resource);
        name.title = resource.relative_path || resource.comfy_name;
        const metadata = document.createElement("small");
        metadata.textContent = `${resource.favorite ? "★ · " : ""}${modelCategoryLabel(resource)}`;
        identity.append(name, metadata);
        const favorite = favoriteButton(resource, updatePreference, replaceLocalResource);
        const info = infoButton(resource, updatePreference, refreshResource, true, replaceLocalResource);
        const choose = document.createElement("button");
        choose.type = "button";
        choose.className = resource.comfy_name === selectedName ? "" : "primary";
        choose.textContent = resource.comfy_name === selectedName ? "Sélectionné" : "Choisir";
        choose.disabled = resource.comfy_name === selectedName;
        choose.addEventListener("click", () => {
          onSelect(resource);
          dialog.close();
        });
        row.append(identity, favorite, info, choose);
        group.lastElementChild.append(row);
      });
    }

    search.addEventListener("input", renderResults);
    category.addEventListener("change", renderResults);
    panel.append(header, filters, resultCount, list);
    dialog.append(panel);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    renderResults();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    search.focus();
  }

  function syncModelPicker(select) {
    const binding = modelPickerBindings.get(select);
    if (!binding) return;
    const { container, resources, updatePreference, refreshResource } = binding;
    const resource = resources.find((item) => item.comfy_name === select.value) || null;
    container.replaceChildren();
    const choose = document.createElement("button");
    choose.type = "button";
    choose.className = "krea2-model-picker-current";
    choose.textContent = resource ? resourceName(resource) : (select.selectedOptions[0]?.textContent || "Choisir un checkpoint");
    choose.title = resource?.relative_path || select.value || "Choisir un checkpoint KREA2";
    choose.disabled = select.disabled;
    choose.addEventListener("click", () => openModelPicker({
      resources,
      selectedName: select.value,
      updatePreference,
      refreshResource,
      onSelect: (next) => {
        select.value = next.comfy_name;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncModelPicker(select);
      },
    }));
    const repaint = () => syncModelPicker(select);
    const favorite = favoriteButton(resource, updatePreference, repaint);
    favorite.disabled = select.disabled || !resource;
    const info = infoButton(resource, updatePreference, refreshResource, true, repaint);
    info.disabled = select.disabled || !resource;
    container.append(choose, favorite, info);
  }

  function renderModelPicker(select, {
    resources = [],
    updatePreference = () => Promise.resolve(false),
    refreshResource = null,
  } = {}) {
    if (!select) return;
    appendGroupedOptions(select, resources, modelGroups);
    let binding = modelPickerBindings.get(select);
    if (!binding) {
      const container = document.createElement("div");
      container.className = "krea2-model-picker-control";
      select.hidden = true;
      select.insertAdjacentElement("afterend", container);
      const observer = new MutationObserver(() => syncModelPicker(select));
      observer.observe(select, { attributes: true, attributeFilter: ["disabled"] });
      binding = { container, observer, resources, updatePreference, refreshResource };
      modelPickerBindings.set(select, binding);
    } else {
      binding.resources = resources;
      binding.updatePreference = updatePreference;
      binding.refreshResource = refreshResource;
    }
    syncModelPicker(select);
  }

  function openLoraPicker({
    resources,
    selectedNames = [],
    onSelect,
    updatePreference,
    refreshResource,
    title = "Ajouter une LoRA KREA2",
  }) {
    const dialog = document.createElement("dialog");
    dialog.className = "krea2-lora-picker-dialog";
    const panel = document.createElement("section");
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = title;
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fermer";
    close.addEventListener("click", () => dialog.close());
    header.append(heading, close);
    const filters = document.createElement("div");
    filters.className = "krea2-lora-picker-filters";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Rechercher un nom, un mot entraîné ou une note…";
    search.setAttribute("aria-label", "Rechercher une LoRA");
    const category = document.createElement("select");
    category.setAttribute("aria-label", "Filtrer par catégorie");
    category.append(new Option("Toutes les catégories", "all"), new Option("Favoris", "favorite"));
    loraManagerGroups.filter(([value]) => value !== "excluded_krea_edit").forEach(([value, label]) => {
      category.append(new Option(label, value));
    });
    filters.append(search, category);
    const resultCount = document.createElement("small");
    resultCount.className = "muted";
    const list = document.createElement("div");
    list.className = "krea2-lora-picker-results";
    const selected = new Set(selectedNames.filter(Boolean));

    function replaceLocalResource(updated) {
      const current = resources.find((item) => item.resource_id === updated?.resource_id);
      if (current) updateResource(current, updated);
      renderResults();
    }

    function renderResults() {
      const query = normalizeSearch(search.value);
      const categoryValue = category.value;
      const values = resources
        .filter((resource) => resource.selectable !== false)
        .filter((resource) => !selected.has(resource.comfy_name))
        .filter((resource) => categoryValue === "all"
          || (categoryValue === "favorite" ? resource.favorite : resource.lora_category === categoryValue))
        .filter((resource) => {
          if (!query) return true;
          return normalizeSearch([
            resource.display_name,
            resource.filename,
            resource.relative_path,
            resource.lora_category,
            ...(resource.trained_words || []),
            resource.notes,
            resource.description,
          ].filter(Boolean).join(" ")).includes(query);
        })
        .sort((left, right) => {
          const categoryOrder = new Map(loraManagerGroups.map(([value], index) => [value, index]));
          const categoryDifference = (
            (categoryOrder.get(left.lora_category || "unclassified") ?? 99)
            - (categoryOrder.get(right.lora_category || "unclassified") ?? 99)
          );
          if (categoryDifference) return categoryDifference;
          const favorite = Number(Boolean(right.favorite)) - Number(Boolean(left.favorite));
          if (favorite) return favorite;
          return resourceName(left).localeCompare(resourceName(right), "fr");
        });
      list.replaceChildren();
      resultCount.textContent = `${values.length} LoRA disponible${values.length > 1 ? "s" : ""}`;
      if (!values.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Aucune LoRA ne correspond à ces filtres.";
        list.append(empty);
        return;
      }
      values.forEach((resource) => {
        const categoryKey = resource.lora_category || "unclassified";
        let group = list.querySelector(`[data-lora-category="${categoryKey}"]`);
        if (!group) {
          group = document.createElement("section");
          group.className = "krea2-lora-picker-group";
          group.dataset.loraCategory = categoryKey;
          const groupTitle = document.createElement("h4");
          groupTitle.textContent = categoryLabel(resource);
          const groupRows = document.createElement("div");
          group.append(groupTitle, groupRows);
          list.append(group);
        }
        const row = document.createElement("article");
        const identity = document.createElement("div");
        const name = document.createElement("b");
        name.textContent = resourceName(resource);
        name.title = resource.relative_path || resource.comfy_name;
        const metadata = document.createElement("small");
        const hasForce = resource.strength_min !== null && resource.strength_min !== undefined
          || resource.strength_max !== null && resource.strength_max !== undefined;
        const force = hasForce ? ` · force ${resource.strength_min ?? "?"} à ${resource.strength_max ?? "?"}` : "";
        metadata.textContent = `${resource.favorite ? "★ · " : ""}${categoryLabel(resource)}${force}`;
        identity.append(name, metadata);
        const favorite = favoriteButton(resource, updatePreference, replaceLocalResource);
        const info = infoButton(resource, updatePreference, refreshResource, true, replaceLocalResource);
        const add = document.createElement("button");
        add.type = "button";
        add.className = "primary";
        add.textContent = "Ajouter";
        add.addEventListener("click", () => {
          onSelect(resource);
          dialog.close();
        });
        row.append(identity, favorite, info, add);
        group.lastElementChild.append(row);
      });
    }

    search.addEventListener("input", renderResults);
    category.addEventListener("change", renderResults);
    panel.append(header, filters, resultCount, list);
    dialog.append(panel);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    renderResults();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    search.focus();
  }

  function renderLoraStack(container, {
    resources = [],
    selections = [],
    maximum = 10,
    minimumStrength = -1,
    maximumStrength = 1,
    defaultStrength = 1,
    disabled = false,
    draggable = false,
    rowClass = "krea2-lora-row",
    onChange = () => {},
    updatePreference = () => Promise.resolve(false),
    refreshResource = null,
  } = {}) {
    if (!container) return;
    const values = selections
      .filter((selection) => selection && selection.name)
      .slice(0, maximum)
      .map((selection) => ({ name: selection.name, strength: Number(selection.strength) || 0 }));
    const resourceFor = (name) => resources.find((resource) => resource.comfy_name === name) || null;
    const emit = (next) => onChange(next.map((value) => ({ ...value })));
    let dragIndex = null;
    container.replaceChildren();
    values.forEach((selection, index) => {
      const resource = resourceFor(selection.name);
      const row = document.createElement("div");
      row.className = `${rowClass} krea2-lora-active-row`;
      row.dataset.index = String(index);
      if (draggable && values.length > 1 && !disabled) row.draggable = true;
      const grip = document.createElement("span");
      grip.className = "krea2-lora-grip";
      grip.textContent = draggable ? "⋮⋮" : String(index + 1);
      grip.title = draggable ? "Glisser pour réordonner" : `LoRA ${index + 1}`;
      const choose = document.createElement("button");
      choose.type = "button";
      choose.className = "krea2-lora-name-button";
      choose.textContent = resource ? resourceName(resource) : `${selection.name} · absent`;
      choose.title = resource?.relative_path || selection.name;
      choose.disabled = disabled;
      choose.addEventListener("click", () => openLoraPicker({
        resources,
        selectedNames: values.filter((_, valueIndex) => valueIndex !== index).map((value) => value.name),
        title: "Remplacer cette LoRA KREA2",
        updatePreference,
        refreshResource,
        onSelect: (nextResource) => {
          const next = values.map((value) => ({ ...value }));
          next[index].name = nextResource.comfy_name;
          emit(next);
        },
      }));
      const strength = document.createElement("input");
      strength.type = "number";
      strength.min = String(minimumStrength);
      strength.max = String(maximumStrength);
      strength.step = "0.05";
      strength.value = String(selection.strength);
      strength.disabled = disabled;
      strength.setAttribute("aria-label", `Force LoRA ${index + 1}`);
      strength.addEventListener("change", () => {
        const raw = Number(strength.value);
        const value = Number.isFinite(raw) ? Math.max(minimumStrength, Math.min(maximumStrength, raw)) : 0;
        const next = values.map((item) => ({ ...item }));
        next[index].strength = value;
        strength.value = String(value);
        emit(next);
      });
      const info = infoButton(resource, updatePreference, refreshResource);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "krea2-lora-remove";
      remove.textContent = "×";
      remove.title = `Retirer ${resourceName(resource)}`;
      remove.setAttribute("aria-label", remove.title);
      remove.disabled = disabled;
      remove.addEventListener("click", () => emit(values.filter((_, valueIndex) => valueIndex !== index)));
      if (draggable) {
        row.addEventListener("dragstart", () => { dragIndex = index; row.classList.add("dragging"); });
        row.addEventListener("dragend", () => { dragIndex = null; row.classList.remove("dragging"); });
        row.addEventListener("dragover", (event) => event.preventDefault());
        row.addEventListener("drop", (event) => {
          event.preventDefault();
          if (dragIndex === null || dragIndex === index) return;
          const next = values.map((value) => ({ ...value }));
          const [moved] = next.splice(dragIndex, 1);
          next.splice(index, 0, moved);
          emit(next);
        });
      }
      row.append(grip, choose, strength, info, remove);
      container.append(row);
    });
    if (values.length < maximum) {
      const add = document.createElement("button");
      add.type = "button";
      add.className = "krea2-lora-add";
      add.textContent = values.length ? `+ Ajouter une LoRA · ${values.length}/${maximum}` : "+ Ajouter une LoRA";
      add.disabled = disabled;
      add.addEventListener("click", () => openLoraPicker({
        resources,
        selectedNames: values.map((value) => value.name),
        updatePreference,
        refreshResource,
        onSelect: (resource) => emit([
          ...values,
          {
            name: resource.comfy_name,
            strength: Math.max(minimumStrength, Math.min(maximumStrength, defaultStrength)),
          },
        ]),
      }));
      container.append(add);
    }
  }

  function renderCatalogManager(
    container,
    {
      models = [],
      loras = [],
      updatePreference = () => Promise.resolve(false),
      refreshResource = null,
    } = {},
  ) {
    if (!container) return;
    container.replaceChildren();

    const modelSection = document.createElement("section");
    modelSection.className = "krea2-catalog-models";
    const modelTitle = document.createElement("h4");
    modelTitle.textContent = "Checkpoints";
    const modelHint = document.createElement("p");
    modelHint.className = "muted";
    modelHint.textContent = "La fiche i rassemble taille, précision, annotations locales et métadonnées CivitAI recherchées explicitement, sans calculer le hash du modèle.";
    const modelList = document.createElement("div");
    models.forEach((resource) => {
      const row = document.createElement("div");
      row.className = "krea2-catalog-model-row";
      const name = document.createElement("b");
      name.textContent = resource.display_name || resource.filename || resource.comfy_name;
      name.title = resource.relative_path || resource.comfy_name;
      const precision = document.createElement("select");
      precision.setAttribute("aria-label", `Précision de ${name.textContent}`);
      const automatic = document.createElement("option");
      automatic.value = "auto";
      const sourceLabel = ({ size: "taille", filename: "nom", unavailable: "indéterminée" })[resource.precision_source] || "automatique";
      const detected = resource.precision && resource.precision !== "unknown" ? resource.precision.toUpperCase() : "inconnue";
      automatic.textContent = `Auto · ${detected} (${sourceLabel})`;
      precision.append(automatic);
      [["bf16", "Forcer BF16"], ["int8", "Forcer INT8"]].forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        precision.append(option);
      });
      precision.value = resource.precision_source === "manual" ? resource.precision : "auto";
      precision.addEventListener("change", () => updatePreference(resource, { precision: precision.value }));
      const favorite = document.createElement("button");
      favorite.type = "button";
      favorite.className = "resource-icon-button";
      favorite.textContent = resource.favorite ? "★" : "☆";
      favorite.title = resource.favorite ? "Retirer des favoris" : "Ajouter aux favoris";
      favorite.addEventListener("click", () => updatePreference(resource, { favorite: !resource.favorite }));
      row.append(name, precision, favorite, infoButton(resource, updatePreference, refreshResource));
      modelList.append(row);
    });
    modelSection.append(modelTitle, modelHint, modelList);

    const loraSection = document.createElement("section");
    loraSection.className = "krea2-catalog-loras";
    const loraTitle = document.createElement("h4");
    loraTitle.textContent = "LoRA";
    const loraHint = document.createElement("p");
    loraHint.className = "muted";
    loraHint.textContent = "Le favori reste indépendant de la catégorie. Le bouton i ouvre les sidecars sans charger leurs aperçus avant le clic.";
    const list = document.createElement("div");
    list.className = "krea2-catalog-lora-list";
    const categoryOrder = new Map(loraManagerGroups.map(([value], index) => [value, index]));
    [...loras]
      .sort((left, right) => {
        const favoriteDifference = Number(Boolean(right.favorite)) - Number(Boolean(left.favorite));
        if (favoriteDifference) return favoriteDifference;
        const categoryDifference = (
          (categoryOrder.get(left.lora_category) ?? 99)
          - (categoryOrder.get(right.lora_category) ?? 99)
        );
        if (categoryDifference) return categoryDifference;
        return resourceName(left).localeCompare(resourceName(right), "fr");
      })
      .forEach((resource) => {
        const row = document.createElement("div");
        row.className = "krea2-catalog-lora-row";
        const name = document.createElement("b");
        name.textContent = resource.display_name || resource.filename || resource.comfy_name;
        name.title = resource.relative_path || resource.comfy_name;
        const classification = document.createElement("select");
        classification.setAttribute("aria-label", `Classer ${name.textContent}`);
        loraManagerGroups.forEach(([value, optionLabel]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = optionLabel;
          classification.append(option);
        });
        classification.value = resource.lora_category || "unclassified";
        classification.addEventListener("change", () => {
          updatePreference(resource, preferenceForLoraCategory(classification.value));
        });
        const favorite = document.createElement("button");
        favorite.type = "button";
        favorite.className = "resource-icon-button";
        favorite.textContent = resource.favorite ? "★" : "☆";
        favorite.title = resource.favorite ? "Retirer des favoris" : "Ajouter aux favoris";
        favorite.setAttribute("aria-label", `${favorite.title} : ${name.textContent}`);
        favorite.addEventListener("click", () => {
          updatePreference(resource, { favorite: !resource.favorite });
        });
        row.append(name, classification, favorite, infoButton(resource, updatePreference, refreshResource));
        list.append(row);
      });
    loraSection.append(loraTitle, loraHint, list);
    container.append(modelSection, loraSection);
  }

  window.PanelForgeKrea2ResourceUi = Object.freeze({
    modelGroups,
    loraGroups,
    appendGroupedOptions,
    renderModelPicker,
    syncModelPicker,
    openResourceInfo,
    renderCatalogManager,
    renderLoraStack,
  });
})();
