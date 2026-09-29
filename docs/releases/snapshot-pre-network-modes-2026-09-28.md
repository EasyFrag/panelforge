# Snapshot avant les modes réseau — 28 septembre 2026

- Branche de sauvegarde : snapshots/pre-network-modes-2026-09-28.
- Tag : snapshot-pre-network-modes-2026-09-28.
- Source : état courant de D:/Code/panelforge-krea2-flux,
  branche de travail feature/krea2-v6-style-catalog-2026-09-26.
- Parent : snapshot pré-mobile c4389c62aa8d7317ca0f5f7180c75b6a74984f92.

La sauvegarde inclut l'application actuelle, les évolutions Écriture/KREA2/Usine,
l'Usine mobile et le correctif d'affichage de l'adresse du Lab au démarrage.
Les deux audits réseau et le guide de lancement LAN/Tailscale sont inclus.

Les arguments --network-mode et le badge Local/Tailscale ne sont pas implémentés.
Ce snapshot fige l'état avant cette modification ; il ne certifie pas une recette
complète hors Internet.

Publication demandée explicitement par l'utilisateur. Construction avec un index
Git temporaire : aucune bascule de branche ni modification de l'index de travail.
Workspace, environnements, médias, diagnostics privés et lanceur contenant une clé
ne font pas partie de cette version.

Contrôles de publication : périmètre des fichiers, recherche de secrets usuels,
comparaison du snapshot avec les fichiers source, vérification des références
distantes après push. Aucun test fonctionnel, appel LLM, génération ni redémarrage
n'est effectué dans cette tâche.

Guide : [Lancement LAN ou Tailscale](../proposals/network-mode-launch-commands-2026-09-28.md).
