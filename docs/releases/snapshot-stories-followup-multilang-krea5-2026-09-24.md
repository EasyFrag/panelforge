# PanelForge — suites, multilangue, KREA2 V5 et VAE INT8

Instantané du code actuel du 24 septembre 2026, depuis `e081adda`.

- Branche : `snapshots/stories-followup-multilang-krea5-2026-09-24`
- Tag : `snapshot-stories-followup-multilang-krea5-2026-09-24`

## Changements inclus

- **Préparer l'épisode suivant** : bouton visible depuis une histoire écrite, discussion avec Qwen proposé par défaut et modèle interchangeable, proposition automatique unique, direction éditable et sauvegardée. L'écriture reste un lancement explicite. La continuité narrative et visuelle est transmise ; les unités déjà écrites sont conservées.
- **Identifiants des suites** : distinction explicite entre les IDs locaux du nouveau projet et ceux du récit précédent dans le contexte et les consignes LLM. Le correctif préserve les contrôles de cohérence internes et les IDs déjà enregistrés. Une ancienne remarque de collision nécessite une nouvelle relecture ; elle n'est pas effacée automatiquement.
- **Fabrication multilangue** : copies indépendantes de fabrication, choix de langue et de modèle, traduction des dialogues et injection dans les prompts existants, relecture manuelle et traitement en chaîne vidéo/DLSS. Les scènes muettes réutilisent les médias compatibles. Références, réglages et essais sources restent traçables. Correction du faux message « invalid JSON » lorsqu'une copie n'existe pas encore.
- **KREA2 Assisted V5** : templates wildcard locaux, recherche hybride avec les exemples V4, aperçu complet des images, variante de template reproductible et classement structurel par action et participants. V3 devient `STABLE` et reste le défaut ; V4 et V5 sont disponibles explicitement. Nouveaux projets initialisés avec KREA2 + Flux Klein, preset de sampling Moody et checkpoint CielBleu disponible, tout en préservant les presets et projets existants. PyYAML devient une dépendance explicite.
- **VAE vidéo H3 INT8 ConvRot** : variantes versionnées de 18 recettes H3 Base, Ref2V et BUNNY pour les nouveaux essais, y compris Histoires et Video Lab. Les recettes et essais historiques sont préservés. La nouvelle installation requiert le fichier `minimax_h3_video_vae_int8_convrot.safetensors` ; aucun modèle n'est inclus dans Git.

## Alignements encore à implémenter

La refonte **Intention → Histoire → Scénario**, avec des états et actions plus explicites, reste une proposition. Les écrans Références / Scènes / Multilangue doivent conserver leur organisation.

Les références d'états persistants et l'envoi automatique des deux états avant/après pendant un clip de transformation restent également à construire. Le suivi d'états déjà existant ne suffit pas à garantir cette transition. La robe rose de Pêchette n'a pas été corrigée dans les données de production.

## Validation et limites

Contrôles réalisés sur le contenu exact préparé dans Git : syntaxe de 49 fichiers Python, compilation seule de 6 scripts JavaScript dans Chromium, lecture de 1 JSON et 1 TOML, vérification des 18 empreintes sources et variantes VAE, diff et sélection des 68 fichiers. Aucun motif de credential détecté dans les ajouts contrôlés. Les tests fonctionnels restent à la main de l'utilisateur, conformément aux consignes du worktree. Aucun appel LLM, rendu, modification du runtime ni redémarrage n'est nécessaire à la publication.

Les fonctionnalités récemment ajoutées disposent de tests ciblés préparés ; cette sauvegarde ne constitue pas une validation fonctionnelle complète. La qualité des traductions, des suites et des sorties vidéo reste à vérifier lors des essais réels.

## Données externes

Les histoires enregistrées, images, vidéos, traces complètes, modèles, caches et fichiers personnels de lancement sont exclus. Une sauvegarde Git ne remplace pas celle du workspace.

KREA2 V5 dépend du pack wildcard local, configurable par `PANELFORGE_KREA2_WILDCARDS_ROOT`, et de la bibliothèque/index V4. Ces données ne sont pas embarquées ; leur configuration est documentée dans la note V5.

## Reprise

Après les traitements en cours, redémarrer le Lab et actualiser le navigateur pour charger le code. Pour un ancien blocage d'identifiants de suite : **Détails de continuité et de vérification → Relire l'arc**, puis reprendre le parcours lorsque les remarques bloquantes sont levées.

Commandes ciblées à lancer par l'utilisateur dans le worktree :

```powershell
python -m unittest discover -s tests -p "test_story_followup*.py"
python -m unittest discover -s tests -p "test_story_identifier_scope.py"
python -m unittest discover -s tests -p "test_episode_localization*.py"
python -m unittest discover -s tests -p "test_episode_storage.py"
python -m unittest discover -s tests -p "test_krea2_assisted_v5.py"
python -m unittest discover -s tests -p "test_h3_video_vae*.py"
```

## Notes détaillées

- [Préparation des suites et correctif des identifiants](../diagnostics/story-followup-2026-09-24.md)
- [Fabrication multilangue](../diagnostics/story-multilanguage-2026-09-23.md)
- [KREA2 V5](../diagnostics/krea2-assisted-v5-wildcards-2026-09-24.md)
- [VAE vidéo INT8](../diagnostics/minimax-h3-int8-vae-2026-09-24.md)
