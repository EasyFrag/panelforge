# Historique des fonctionnalités retirées

Ces sources documentent les ateliers qui ne sont plus accessibles depuis les menus.
Elles ne sont ni importées, ni servies par HTTP, ni découvertes par les tests de `tests/`.
Le packaging Python reste limité à `src/`. Le fichier `.ignore` les exclut des recherches
ordinaires avec `rg` ; utiliser `rg --no-ignore historique/` pour les consulter.

## Nettoyage du 19 octobre 2026

Le dossier [2026-10-19-menus](2026-10-19-menus/manifest.json) contient un inventaire avec
les chemins d'origine, les empreintes SHA-256, les routes retirées et les mesures avant/après.
`original/` conserve les fichiers complets avant modification, y compris les tests retirés
et les versions antérieures des fichiers partiellement nettoyés. Il ne constitue pas une
seconde application à démarrer. Les données et médias du workspace utilisateur sont inchangés.

| Ancienne fonctionnalité | Sources principales dans `2026-10-19-menus/original/` | Dépendances encore nécessaires |
| --- | --- | --- |
| Production automatique V1/V2 | `src/panelforge/application/production*.py`, `domain/production_v2.py`, stockage et JS associés | Ordonnanceur GPU, contrats thermiques et ressources conservés |
| Générateur KREA2 direct | `application/krea2_lab.py`, stockage des runs, `presets/krea2_t2i.py`, `workflows/image.generate.t2i/krea2/` | Ratios et réglages KREA2 partagés conservés |
| Batch autonome KREA2 | `application/krea2_batch.py`, `static/krea2-batch-lab.js` | Catalogue de modèles/LoRA et recettes partagées conservés ; ancien historique lu par KREA2 Edit |
| Ancien générateur Video Lab | `application/video_lab.py`, `static/video-lab.js` | Moteurs H3/Ref2V et extraction des sorties conservés ; lecture des anciens prompts pour Texte Instagram |

Les anciens écrans Histoire restent actifs : l'Usine permet encore d'y accéder.
Les menus Video Lab / Texte Instagram / Analyse des médias sont conservés.

Avant de réintroduire une feature, consulter sa fiche et le commit de référence dans
le manifeste, puis porter uniquement le comportement nécessaire avec ses tests.
Ne pas recopier globalement les anciens fichiers d'intégration : ils contiennent aussi
des contrats désormais remplacés. Les tests archivés décrivent l'ancien comportement ;
ils ne font plus partie de la suite active.

## Mesure et vérification

Le gain porte sur les lignes de fichiers `.py`, `.js`, `.css` et `.html` de `src/` et `scripts/`,
hors historique. Les tests sont mesurés séparément ; archiver ne réduit pas les lignes totales du dépôt.
Les imports, la syntaxe Python/JavaScript, les liens statiques et la conservation des cibles des menus
ont été contrôlés sans exécuter l'application. Les dépendances Python du projet restent nécessaires.
Les tests fonctionnels sont à lancer par l'utilisateur : `python -m unittest discover -s tests`.
Aucun appel LLM, rendu, test ou redémarrage de service n'a été lancé pour ce nettoyage.
