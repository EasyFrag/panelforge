# Version locale — qualité Histoires et loupe des références — 2026-09-27

- Branche de sauvegarde : `snapshots/story-quality-reference-zoom-2026-09-27`.
- Tag : `snapshot-story-quality-reference-zoom-2026-09-27`.
- Le commit exact est consigné dans la continuité après création et dans le manifeste local de diagnostic.
- Snapshot de l’état courant du code, incluant les travaux déjà présents Histoires, KREA6 et usine vidéo ; aucune donnée runtime, image, vidéo ni trace brute LLM ajoutée.
- Branche de travail, HEAD et index courant conservés au moyen d’un index temporaire. Version locale, sans push GitHub.

Le petit patch du jour rend les images de l’onglet Références inspectables : bouton loupe sur l’image retenue, les propositions et les résultats du lot ; ouverture dans une visionneuse couvrant la fenêtre, proportions conservées ; fermeture avec Fermer ou Échap. Les miniatures offrent un aperçu agrandi au survol sur ordinateur. La sélection reste une action distincte. Lecture possible même pendant une génération ou sur une adaptation multilingue.

Vérification statique : compilation JavaScript sans exécution, identifiants HTML uniques, revue du diff et git diff --check. Aucun test fonctionnel, appel LLM, génération ni redémarrage lancé. La validation visuelle revient à l’utilisateur après rechargement de la page.

La proposition [ton et création simplifiée](../proposals/story-tone-simple-creation-2026-09-27.md) reste à aligner ; elle n’est pas implémentée dans cette version.
