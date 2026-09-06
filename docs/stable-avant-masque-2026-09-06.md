# Point de restauration avant masque — 2026-09-06

Tag : `stable-avant-masque-2026-09-06`.

Ce snapshot fige l'état courant demandé par l'utilisateur avant le chantier du masque dessinable. Le nom « stable » identifie cette version de référence ; les tests et la validation fonctionnelle restent à la main de l'utilisateur.

## Contenu

- KREA2 Assisted : assistance versionnée, inspiration importée, branches de conversation, presets révisables et file persistante de rendus successifs.
- KREA2 Edit : conversation visible par étape, comparateur superposé, frise avec zoom, validation d'une image comme source de l'étape suivante et conservation des réglages.
- H3 Base / Ref2V : recettes de préparation en une, deux ou trois étapes, corrections de validation et de révision, journalisation du raisonnement et reprise depuis la dernière frame d'une vidéo.
- Prompts versionnés, audits, documentation et tests préparés avec ces évolutions.

Le masque dessinable et le compositing après génération ne sont pas implémentés. Leur conception reste : pinceau pour révéler le résultat généré, gomme pour restaurer la source, aperçu local en direct, conservation des deux originaux et du masque, puis utilisation du composite validé comme nouvelle source.

## Nouveaux checkpoints

Lecture seule de ComfyUI `UNETLoader` et de l'API Assisted du Lab : 30 modèles sous `Krea2/`. Les deux ajouts suivants sont exposés et sélectionnables :

- `Krea2/sickOllie_krea2.safetensors`
- `Krea2/sinoxKrea2Aesthetics_visionV10Uncen.safetensors`

Leur détection est automatique. La précision reste inconnue : le chemin local des poids est inaccessible et les métadonnées disponibles ne permettent pas de la confirmer. Les réponses du cache rgthree sont vides pour ces fichiers. Aucun poids n'a été lu, haché, déplacé ou chargé par l'agent.

Assisted emploie le workflow partagé `image.generate.batch/krea2-community@0.2.0` : ER-SDE/Simple, 8 steps et CFG 1.1, puis agrandissement latent ×1.5 et seconde passe de 2 steps, CFG 1, denoise 0.3. Choisir un checkpoint ne sélectionne pas une recette de sampling particulière.

La [fiche de l'auteur Sick Ollie](https://civitai.red/models/2676616/sick-ollie), consultée le 2026-09-06, recommande pour sa version Krea2 Euler/Beta, 9 steps, CFG 1 et une résolution de 1440×1920. Ces recommandations diffèrent du workflow actuel ; leur bénéfice ici n'a pas été évalué. Le nom local seul ne permet pas d'identifier sa variante de précision avec certitude. Aucune recommandation propre à Sinox n'a été confirmée dans cet audit.

## Vérifications et périmètre de sauvegarde

- Syntaxe : AST de 47 fichiers Python, lecture de 13 JSON et compilation syntaxique de 7 JavaScript modifiés, sans exécution de leur code.
- `git diff --check` réussi sur les fichiers déjà suivis. Après ajout des nouveaux fichiers à l'index, `git diff --cached --check` signale neuf lignes vierges finales dans les prompts FL2VA 0.4.0. Elles sont conservées pour sauvegarder leur contenu actuel ; aucun autre avertissement de whitespace.
- Revue des 137 fichiers candidats avant ajout de ce document : code, prompts, tests et documentation ; aucun fichier de plus de 1 Mo.
- Aucun test, appel LLM, génération image/vidéo, annulation ou redémarrage de service.

Le tag sauvegarde le code et les ressources versionnées du dépôt. Le workspace actif `D:\Code\panelforge\workspace`, ses runs, ses médias et les poids des modèles restent locaux ; ils ne sont pas inclus dans Git. Les schémas de stockage ont évolué depuis les anciens tags : cette sauvegarde du code ne remplace pas une sauvegarde du workspace.
