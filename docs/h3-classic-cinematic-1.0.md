# Classique Mise en scène 1.0 — expérimental

Correctif du 11 septembre : langue des répliques explicitée dans le Plan, complétion locale des balises quand la langue est connue, faux positif caméra fixe corrigé ; [diagnostic et tests](media-h3-boundary-fixes-2026-09-11.md). Les deux appels et les anciennes recettes restent disponibles.

Patch du 10 septembre 2026, dans `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`.

Avant toute modification fonctionnelle, l’état précédent a été publié sur GitHub : commit [`2b68523`](https://github.com/EasyFrag/panelforge/commit/2b68523), tag [`snapshot-avant-classique-cinematique-2026-09-10`](https://github.com/EasyFrag/panelforge/tree/snapshot-avant-classique-cinematique-2026-09-10) et branche `snapshots/avant-classique-cinematique-2026-09-10`. Les tags de restauration antérieurs restent intacts, notamment `stable-avant-masque-2026-09-06`.

## Utilisation

Dans H3 Base ou REF2V, choisir **Préparation → Classique**, puis **Version Classique → Mise en scène 1.0 · 2 étapes · Expérimental**. Les recettes actuelles restent sélectionnées par défaut et leurs parcours 1/2/3 restent disponibles.

Le nouveau parcours comporte deux appels initiaux :

1. **Plan** : le LLM reçoit l’intention, les images et leurs rôles. Il prépare les identités, le cadrage initial, la progression des actions ou des états, le rythme, les états de sortie et les raccords. Un plan peut contenir une ou deux phases caméra continues, lorsque la scène le justifie. Les phases ne créent pas de coupures. Une scène calme peut rester simple et statique.
2. **Rédaction** : le LLM reçoit le Plan approuvé. Il rédige les actions de chaque phase. Le compilateur insère les cadrages, caméras, repères de temps et raccords approuvés. Les images ne sont pas renvoyées au rédacteur.

Le Plan reste consultable et modifiable avant rédaction. Le mode rapide existant enchaîne ces mêmes étapes. Une correction explicite ajoute son propre appel ; aucun troisième appel automatique, critique cachée ou réparation automatique n’est ajouté.

**Nombre de plans** :

- **Auto**, par défaut : suit une demande explicite dans l’intention ; sinon le Plan choisit entre 1 et 6 plans. L’interface montre le nombre retenu après préparation.
- **1 à 6** : le choix manuel a priorité sur un ancien nombre indiqué dans le texte. Cette priorité est indiquée sous le sélecteur.

Le nombre de plans ne mesure pas la quantité d’action. Les réglages sont fixés pour l’atelier créé ; une reprise dans un nouvel atelier permet de les changer. Les révisions du prompt final conservent la structure approuvée ; modifier les plans ou phases se fait dans le Plan puis par une nouvelle rédaction.

H3 accepte texte seul, première frame, dernière frame et les deux frames. REF2V conserve ses rôles de référence. Les modèles, checkpoints, LoRA, recettes de rendu, seeds et valeurs MP ne changent pas avec cette sélection.

## Contrats et indépendance

| Élément | Version / contrat |
| --- | --- |
| Préparation | `{"family":"classic","version":"1.0.0"}` ; Classique historique conserve `version: null` |
| Recettes | `minimax.h3.fl2va.classic.cinematic.planned@1.0.0` et `minimax.h3.ref2v.classic.cinematic.planned@1.0.0` |
| Contrat de sortie | `minimax.h3.classic.cinematic_planned_v1` |
| Consignes et exemples | `_blocks/h3-classic-cinematic/1.0.0` |
| Compilation neutre adoptée | `application/cinematic_core_v1.py`, version `1.0.0` |
| Révision après rendu | `0.4.0`, politique Classique Mise en scène 1.0 propre |
| Sessions | Schéma 14, lecture des schémas 1–13 |
| Projets H3/REF2V | Schéma 13, lecture des schémas 1–12 |
| Cache des fichiers JS modifiés | `20260910.9` |

La nouvelle recette possède son schéma `actions`, ses consignes, ses exemples et son marqueur de contexte. Elle n’importe aucun schéma, exemple, niveau d’action ou consigne Combat. Le petit compilateur neutre est extrait du comportement de Combat 1.3 ; Combat conserve son schéma `exchanges`, ses validations, ses exemples et son contexte. Les versions précédentes restent accessibles. L’adoption d’une future version commune doit être explicite pour chaque famille.

Le réglage `cinematic_settings.shot_count` est distinct des réglages Combat. Il suit la session, les forks, le projet de rendu, ses révisions, la conversion H3 → REF2V et la reprise depuis une dernière frame. Une conversion conserve les phases dans leur plan. Le réglage Auto reste enregistré comme Auto, même lorsque le Plan a choisi un nombre précis. Aucun fichier d’atelier existant n’est migré au démarrage.

## Vérification et expérimentation

Tests préparés dans `test_classic_cinematic.py` et `test_classic_cinematic_browser.py` : cinq modes d’entrée, Auto/priorité manuelle, 1/2/6 plans, durée, phases, références, paroles, deux appels avec réponses simulées, streaming, réouverture, fork, révisions, conversion, anciens schémas et isolation. Les suites Combat existantes couvrent également le compilateur partagé. Un inventaire de 591 empreintes protège les anciens prompts, profils et recettes. Les assertions de cache et de schéma existantes sont actualisées.

**Tests non exécutés**, conformément aux instructions du dépôt. Seuls des contrôles statiques ont été effectués : syntaxe Python/JavaScript sans exécution de l’application, JSON, références de blocs, identifiants HTML, empreintes et différences Git. Aucun appel LLM, rendu ou redémarrage de service.

Après redémarrage du Lab par l’utilisateur, comparer les deux recettes Classique avec les mêmes images, intention et réglages de rendu : une scène calme, une transformation d’objet ou de décor, un déplacement et une interaction ; essayer un plan puis plusieurs plans. Le bénéfice qualitatif doit être observé : ni davantage de champs ni deux appels ne garantissent à eux seuls une meilleure vidéo. Les exemples appris par le LLM peuvent encore influencer sa mise en scène.

L’analyse vidéo/images → prompt et le mode Sensualité / jeu d’acteur non explicite restent en backlog. Aucun travail sur la recherche de seeds ni sur ces deux chantiers dans ce patch.
