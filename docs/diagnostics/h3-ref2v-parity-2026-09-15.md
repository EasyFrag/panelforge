# État H3 Image-to-Video / REF2V — 15 septembre 2026

Audit du checkout du Lab, `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`, et des métadonnées du workspace `D:\Code\panelforge\workspace`. H3 doit faire référence pour les prochaines évolutions, selon la demande utilisateur. Aucun correctif, test applicatif, appel LLM, rendu ou redémarrage effectué.

## Conclusion

Les dernières recettes de préparation sont disponibles des deux côtés et utilisent les mêmes moteurs et blocs de base. Le principal écart constaté est un défaut du passage **REF2V Classique Mise en scène 1.0 → projet de rendu** : le nouveau profil n'est pas reconnu comme REF2V. Le défaut est observable dans le dernier projet enregistré, avant tout lancement de vidéo.

L'historique contient également des projets restés sur leurs anciennes recettes. Leur réouverture n'est pas une mise à niveau vers les dernières versions.

## Préparation du prompt

| Élément | H3 | REF2V | Constat |
| --- | --- | --- | --- |
| Classique Mise en scène | 1.0.0, deux appels | 1.0.0, deux appels | Même contrat et mêmes templates ; recette sélectionnée initialement des deux côtés |
| Combat | 1.3.0, deux appels | 1.3.0, deux appels | Même contrat et mêmes templates ; quantité d'action, plans et orientation communs |
| Sensuel | 1.0.0, deux appels | 1.0.0, deux appels | Même contrat et mêmes templates |
| Choix Plan / Rédaction | Deux LLM possibles | Deux LLM possibles | Les six recettes figurent dans le registre de sélection du rédacteur |
| Éditeur de consignes et traces | Disponible | Disponible | Même stockage et mêmes outils, paquets indépendants |
| Révision après rendu | Selon la famille/version | Selon la famille/version | Même service ; Classique Mise en scène utilise la révision technique 0.4.0 |

Sources : `application/prompt_recipes.py`, `domain/prompt_writer.py`, les six manifestes `prompt_cookbooks/minimax.h3.{fl2va,ref2v}.*.planned/`, `application/prompt_composition.py:_sequence_request`, `static/i2v-direct.js:17`, `static/ref2v-direct.js:15`.

### Consignes réellement actives

Comparaison des empreintes des fichiers `.txt` des révisions actives du workspace, et non seulement des numéros affichés :

- **Classique : H3 r2 / REF2V r2, 34 fichiers identiques.**
- **Sensuel : H3 r2 / REF2V r1, 35 fichiers identiques.** Les compteurs sont propres à chaque paquet : r1 ne signifie donc pas ici des consignes plus anciennes.
- **Combat : H3 r1 ; paquet workspace REF2V non initialisé lors de l'audit.** La recette REF2V 1.3.0 existe et ses templates pointent sur les mêmes blocs que H3. Le stockage initialise le paquet à son premier accès ; son absence ne prouve pas une fonctionnalité manquante. Pas de comparaison de révisions actives possible pour cette paire à cette date.

Les textes communs ne rendent pas les requêtes complètes identiques : la préparation injecte les rôles des images et le mode d'entrée appropriés. H3 utilise les frames de début/fin ; REF2V utilise une liste d'images avec leurs rôles. Cette différence doit être conservée.

Sources : `infrastructure/storage/prompt_recipes.py:37` et `:63`, `prompt_sources/README.md`, dossiers `workspace/prompt_recipes/`.

## Défaut confirmé : profil REF2V Classique omis du routage

Dans `application/h3_render.py:368`, `get_or_create_from_session` reconnaît uniquement les profils REF2V `direct`, `combat` et `sensual`. Il manque `minimax.h3.ref2v.classic.cinematic`.

Pour ce profil, la création de projet suit donc la branche H3 : extraction des éventuelles frames de début/fin, liste de références vide, mode calculé comme T2VA/I2VA/FL2VA selon les frames. Le bon sélecteur REF2V dans l'interface ne corrige pas le mode stocké par le serveur.

Cas observé le 15 septembre, préparation terminée vers **15 h 15, heure de Paris** :

- Session `prompt-b08c5a9d2ca4447abbbe38d61efed33f` : profil REF2V Classique 1.0.0, images avec rôles `first_frame` et `subject_reference`.
- Plan avec Qwen, rédacteur configuré sur Gemma ; Plan et Rédaction utilisent tous deux la révision de consignes r2.
- Projet `h3-render-22b2bdeb73a94092894086b85365d070` : **`input_mode: i2va`**, première frame conservée, **zéro image dans `reference_asset_ids`**. L'image du sujet n'est donc pas transmise comme référence au projet de rendu.
- **Zéro tentative de rendu** lors de la lecture : cela établit le défaut de configuration, sans prétendre qu'une vidéo a été produite avec ce défaut.

Le relevé des projets directement issus de sessions REF2V, hors adaptations, trouve 21 projets Direct et 14 Combat en `ref2va`, et ce seul projet Classique Mise en scène en `i2va`. Les autres profils ne sont pas omis par cette condition.

Le test existant `tests/test_classic_cinematic.py:266` crée bien un projet de rendu, mais vérifie sa version de révision, ses réglages et sa persistance, sans vérifier `input_mode` ni la conservation des références. Ce cas n'est donc pas couvert par ces assertions.

Une correction future devra aussi traiter la reprise du projet déjà mal classé : la méthode retourne un projet existant avant de recalculer le mode. Ajouter le profil à la reconnaissance ne réparera donc pas à lui seul ce projet sauvegardé.

## Rendu et interface

Le panneau `static/h3-render-lab.js` est partagé par H3 et REF2V. Checkpoint, jusqu'à quatre LoRA, forces des passes BUNNY, Turbo désactivable, aperçu BUNNY, MP initiaux/finals, réutilisation du seed et DLSS vidéo utilisent les mêmes contrôles/services. Cela établit la présence du code commun, pas une validation visuelle ou un essai de rendu dans cet audit.

| Recette de rendu actuellement enregistrée dans `scripts/run_lab.py` | Version |
| --- | --- |
| H3 Base / Latent Speed | 0.1.6 |
| REF2V intégré | 0.2.4 |
| BUNNY, proposé aux deux modes | 0.1.3 |

Ces compteurs appartiennent à des familles de workflows distinctes : comparer 0.1.6 et 0.2.4 ne mesure pas une avance fonctionnelle.

Les derniers projets REF2V ayant des tentatives enregistrées datent du 10 septembre : Classique historique avec rendu REF2V 0.2.3, puis Combat 1.3 avec BUNNY 0.1.0 dans le relevé le plus récent. Le panneau reprend les réglages du dernier essai ; les anciennes versions restent volontairement chargeables. Cela contribue à l'impression de retard alors que les versions récentes sont présentes dans le catalogue.

La conversion dédiée H3 → REF2V construit explicitement un projet `REF2VA` et conserve les paramètres de la famille. Elle n'utilise pas la condition fautive pour créer sa destination (`application/h3_ref2v_conversion.py:171`). Cela ne constitue pas un test complet de cette conversion.

## Proposition d'alignement, non implémentée

Précision de l'utilisateur après l'audit : **H3 est la référence et doit rester strictement inchangé pour cet alignement.** Les adaptations doivent porter sur REF2V, y compris si sa variété d'entrées justifie des différences ciblées du Plan JSON ou de l'assemblage final.

Le deuxième appel reçoit déjà le Plan approuvé et les rôles REF2V des images (`prompt_composition.py:2320`). Le rédacteur produit un JSON de paragraphes par phase ; il ne produit pas seul toute la grammaire du prompt vidéo. Le compilateur applique ensuite le header REF2V et ses règles de sortie, notamment l'absence de `integrated_multimodal_description` et le titre mono-plan `Shot 1:` (`cinematic_core_v1.py:18`, `:68`, `:93`). Le Plan voit les images ; le rédacteur reçoit leur mapping textuel et le Plan. Le schéma de Plan est actuellement commun au sein de chaque famille : la sémantique des références dépend du contexte. Une future extension spécifique REF2V reste à définir selon le besoin, sans toucher au contrat H3.

1. Corriger d'abord le routage de Classique Mise en scène REF2V, vérifier le mode et toutes les références, et prévoir la reprise du projet affecté.
2. Clarifier la recette de préparation, sa révision de consignes et la recette de rendu d'un projet repris. Conserver les historiques sans migration silencieuse de leurs prompts ou réglages.
3. Prendre H3 comme référence pour les prochaines évolutions. Reprendre explicitement les améliorations dans la recette REF2V de la même famille, en conservant ses règles de références et l'isolation Classique / Combat / Sensuel.
4. Vérifier à chaque adoption la chaîne complète : choix de recette → Plan → Rédaction → création du projet → mode/références du rendu → réouverture.

Le stockage est volontairement indépendant : modifier un paquet H3 n'actualise pas automatiquement son équivalent REF2V. Modifier `_defaults/` n'actualise pas non plus les paquets déjà initialisés. C'est un risque futur de divergence à gérer par adoption explicite, pas une preuve de retard actuel des textes Classique ou Sensuel.

**P1 Mise en scène I2V 1.1** reste au backlog, pas encore livrée sur H3 : elle ne doit pas être comptée comme un retard REF2V. **P2 analyse vidéo adaptative** et **presets sampling EROS/BUNNY** restent également des travaux à venir.
