(() => {
  "use strict";
  const badge = document.getElementById("network-mode");
  if (!badge) return;
  const labels = {lan: "Local", tailscale: "Tailscale"};
  fetch("/api/network-mode", {cache: "no-store"})
    .then(response => response.ok ? response.json() : null)
    .then(config => {
      if (!config || !Object.hasOwn(labels, config.mode)) return;
      badge.textContent = labels[config.mode];
      badge.dataset.mode = config.mode;
      badge.title = config.mode === "lan"
        ? "Accès au serveur et aux fichiers par le réseau local"
        : "Accès au serveur et aux fichiers par Tailscale";
      badge.setAttribute("aria-label", "Mode réseau : " + labels[config.mode]);
      badge.hidden = false;
    })
    .catch(() => {}); // No inferred mode on an older backend or a failed request.
})();
