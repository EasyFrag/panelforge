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
    sfw: "SFW",
    nsfw: "NSFW",
    unclassified: "Non classés",
  });

  function appendGroupedOptions(select, resources, labels, { includeEmpty = false } = {}) {
    select.replaceChildren();
    if (includeEmpty) {
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Aucun";
      select.append(empty);
    }
    Object.entries(labels).forEach(([category, label]) => {
      const values = resources.filter((resource) => resource.category === category);
      if (!values.length) return;
      const group = document.createElement("optgroup");
      group.label = label;
      values.forEach((resource) => {
        const option = document.createElement("option");
        option.value = resource.comfy_name;
        option.textContent = resource.filename || resource.comfy_name;
        option.title = resource.relative_path || resource.comfy_name;
        group.append(option);
      });
      select.append(group);
    });
  }

  const loraManagerGroups = Object.freeze([
    ["favorite", "Favoris"],
    ["sfw", "SFW"],
    ["nsfw", "NSFW"],
    ["unclassified", "Non classés"],
  ]);

  function preferenceForLoraCategory(category) {
    if (category === "favorite") return { favorite: true };
    return { favorite: false, safety: category };
  }

  function renderCatalogManager(
    container,
    { models = [], loras = [], updatePreference = () => Promise.resolve() } = {},
  ) {
    if (!container) return;
    container.replaceChildren();

    const modelSection = document.createElement("section");
    modelSection.className = "krea2-catalog-models";
    const modelTitle = document.createElement("h4");
    modelTitle.textContent = "Checkpoints";
    const modelHint = document.createElement("p");
    modelHint.className = "muted";
    modelHint.textContent = "La taille locale reste prioritaire. En son absence, le nom ou votre classement manuel est utilisé.";
    const modelList = document.createElement("div");
    models.forEach((resource) => {
      const row = document.createElement("div");
      row.className = "krea2-catalog-model-row";
      const name = document.createElement("b");
      name.textContent = resource.filename || resource.comfy_name;
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
      row.append(name, precision, favorite);
      modelList.append(row);
    });
    modelSection.append(modelTitle, modelHint, modelList);

    const loraSection = document.createElement("section");
    loraSection.className = "krea2-catalog-loras";
    const loraTitle = document.createElement("h4");
    loraTitle.textContent = "LoRA";
    const loraHint = document.createElement("p");
    loraHint.className = "muted";
    loraHint.textContent = "Glissez une LoRA dans une colonne, ou utilisez son menu de classement.";
    const board = document.createElement("div");
    board.className = "krea2-catalog-board";
    let draggedResource = null;
    loraManagerGroups.forEach(([category, label]) => {
      const column = document.createElement("div");
      column.className = "krea2-catalog-column";
      column.dataset.category = category;
      const heading = document.createElement("h5");
      const values = loras.filter((resource) => resource.category === category);
      heading.textContent = `${label} · ${values.length}`;
      const list = document.createElement("div");
      list.className = "krea2-catalog-column-list";
      column.addEventListener("dragover", (event) => {
        event.preventDefault();
        column.classList.add("drop-target");
      });
      column.addEventListener("dragleave", () => column.classList.remove("drop-target"));
      column.addEventListener("drop", (event) => {
        event.preventDefault();
        column.classList.remove("drop-target");
        if (draggedResource && draggedResource.category !== category) {
          updatePreference(draggedResource, preferenceForLoraCategory(category));
        }
        draggedResource = null;
      });
      values.forEach((resource) => {
        const card = document.createElement("article");
        card.className = "krea2-catalog-card";
        card.draggable = true;
        card.addEventListener("dragstart", () => {
          draggedResource = resource;
          card.classList.add("dragging");
        });
        card.addEventListener("dragend", () => {
          draggedResource = null;
          card.classList.remove("dragging");
          column.classList.remove("drop-target");
        });
        const name = document.createElement("b");
        name.textContent = resource.filename || resource.comfy_name;
        name.title = resource.relative_path || resource.comfy_name;
        const tools = document.createElement("span");
        const classification = document.createElement("select");
        classification.setAttribute("aria-label", `Classer ${name.textContent}`);
        loraManagerGroups.forEach(([value, optionLabel]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = optionLabel;
          classification.append(option);
        });
        classification.value = category;
        classification.addEventListener("change", () => {
          updatePreference(resource, preferenceForLoraCategory(classification.value));
        });
        tools.append(classification);
        if (resource.source_url) {
          const link = document.createElement("a");
          link.href = resource.source_url;
          link.target = "_blank";
          link.rel = "noreferrer";
          link.textContent = "i";
          link.title = "Ouvrir la fiche ou la recherche CivitAI";
          tools.append(link);
        }
        card.append(name, tools);
        list.append(card);
      });
      column.append(heading, list);
      board.append(column);
    });
    loraSection.append(loraTitle, loraHint, board);
    container.append(modelSection, loraSection);
  }

  window.PanelForgeKrea2ResourceUi = Object.freeze({
    modelGroups,
    loraGroups,
    appendGroupedOptions,
    renderCatalogManager,
  });
})();
