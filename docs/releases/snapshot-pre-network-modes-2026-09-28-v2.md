# Snapshot avant les modes réseau — 28 septembre 2026, version 2

- Branche : snapshots/pre-network-modes-2026-09-28-v2.
- Tag : snapshot-pre-network-modes-2026-09-28-v2.
- Parent : f33db3050b01469c34d4aeda2e598f3d258a326d.
- Source : état courant de D:/Code/panelforge-krea2-flux.
- Branche de travail conservée : feature/krea2-v6-style-catalog-2026-09-26.

Sauvegarde demandée explicitement après le dernier alignement réseau.
Elle conserve l'application et l'Usine mobile de la version précédente, ainsi
que les changements présents dans l'interface de sélection et d'ouverture des
fiches de référence. Les derniers audits d'histoires et retours Petits hommes
sont également inclus, sans appliquer leurs propositions.

Les modes réseau et le badge restent non implémentés. L'intention convenue est
de conserver les arguments existants : les URL bucket du lancement historique
continueront à sélectionner les accès serveur Tailscale. Ce lancement dépend
encore de X: pour les exports ; le futur profil complet doit aussi traiter les
accès aux fichiers et préserver les chemins logiques.

Snapshot construit avec un index temporaire ; aucune bascule de branche ni
modification de l'index de travail. Workspace, diagnostics privés, environnements,
médias de production et lanceur contenant une clé ne sont pas publiés.

Vérifications de sauvegarde : comparaison des fichiers avec l'arbre Git, recherche
de motifs usuels de secrets et contrôle des références distantes après publication.
Aucun code applicatif modifié pour cette tâche ; aucun test fonctionnel, génération,
appel LLM ou redémarrage lancé.
