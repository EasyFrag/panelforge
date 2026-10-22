(() => {
  const button = document.getElementById("instance-info-open");
  const dialog = document.getElementById("instance-info");
  if (!button || !dialog) return;
  const status = document.getElementById("instance-info-status");
  const fields = document.getElementById("instance-info-fields");
  let loading = false;

  button.addEventListener("click", async () => {
    if (!dialog.open) dialog.showModal();
    if (loading) return;
    loading = true;
    status.textContent = "Chargement…";
    fields.replaceChildren();
    try {
      const response = await fetch("/api/instance", { cache: "no-store" });
      if (!response.ok) throw new Error("Informations d’instance indisponibles.");
      const info = await response.json();
      if (!info.available) throw new Error("Cette instance ne fournit pas ses informations de démarrage.");
      const modified = info.git_modified === null ? "Indisponible" : info.git_modified ? "Oui" : "Non";
      const rows = [
        ["Version", info.version], ["Démarrage", new Date(info.started_at).toLocaleString()],
        ["Processus", info.pid], ["Dossier du code", info.source_root], ["Workspace", info.workspace],
        ["Branche Git", info.git_branch], ["Commit Git", info.git_commit],
        ["Modifications applicatives locales", modified], ["Empreinte du code (SHA-256)", info.source_sha256],
      ];
      for (const [label, value] of rows) {
        const term = document.createElement("dt");
        const description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value ?? "Indisponible";
        fields.append(term, description);
      }
      status.textContent = "État du code sur disque au démarrage. Les modifications ultérieures nécessitent un redémarrage pour être prises en compte par le serveur.";
    } catch (error) {
      status.textContent = error.message || "Impossible de lire les informations d’instance.";
    } finally {
      loading = false;
    }
  });
})();
