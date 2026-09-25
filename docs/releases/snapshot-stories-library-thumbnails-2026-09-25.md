# PanelForge — bibliothèque, écriture, miniatures et reprise multilangue

Instantané du code existant au 25 septembre 2026, depuis 9b52feb.

- Branche de publication : snapshots/stories-library-thumbnails-2026-09-25
- Tag : snapshot-stories-library-thumbnails-2026-09-25

## Contenu

- Bibliothèque d’histoires et épisodes : regroupement, favoris, archivage/restauration, renommage, tris, portraits et compteurs de progression.
- Écriture : Intention / Histoire / Scénario avec état réel, navigation vers les scènes et diagnostics dédupliqués ; action explicite de correction des blocages suivie d’une relecture.
- Miniatures d’épisodes indépendantes du montage : modèles de série Qwen, références avec rôles, typographies intégrées ou titre dessiné, format 3:4, numéro ajouté localement, déplacement manuel du bandeau, galerie et corbeille protégée pour les essais inutilisés.
- Ordonnancement : suivi du débit LLM, compteurs de réflexion/rédaction, historique thermique local/serveur et refroidissement local configurable après traitement chaud.
- Reprise H3/multilangue : libération des réservations abandonnées sans tâche locale ni exécution ComfyUI, affichage du motif d’attente et des traductions déjà injectées.
- Tests associés, documentation et polices Outfit / Barlow Condensed avec licences SIL OFL.

Les évolutions futures de détection/préparation des états visuels requis sont uniquement décrites dans la [proposition](../proposals/story-required-visual-states-2026-09-25.md). Elles ne sont pas implémentées dans cette version. Aucun ancien épisode n’est réparé ou migré pour ce snapshot.

## Vérification et limites

Vérification statique du contenu sélectionné : syntaxe Python/JavaScript, JSON/TOML, espaces et sélection des fichiers. Les tests fonctionnels restent à lancer par l’utilisateur ; aucun appel LLM, génération ou redémarrage n’est effectué pour la publication. Les notes de diagnostic décrivent les observations réalisées lors des tâches précédentes, pas une nouvelle campagne de tests.

Code, tests, documentation et polices applicatives uniquement. Les données workspace, médias générés, modèles IA et configurations de lancement personnelles ne sont pas inclus dans ce commit. Publication sur une branche et un tag dédiés ; master reste inchangée.

## Notes

- [Bibliothèque](../diagnostics/story-library-2026-09-24.md)
- [Parcours d’écriture](../diagnostics/story-writing-ux-2026-09-24.md)
- [Miniatures](../episode-thumbnails.md)
- [Blocage multilangue](../diagnostics/multilang-queue-orphan-2026-09-25.md)
