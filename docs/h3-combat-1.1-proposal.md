# Proposition Combat 1.1 — Chorégraphie et montage

Proposition du 10 septembre 2026, puis **implémentation autorisée et livrée dans `.panelpatch`** le même jour. Combat `1.1.0` est expérimental ; Combat `1.0.0` reste sélectionnable via Version Combat / Historique et conserve ses ateliers. Les tests et rendus de validation restent à exécuter par l'utilisateur.

## Fonctionnement proposé

- Deux réglages indépendants : **Quantité d'action** (Modéré / Dynamique / Intense / Déchaîné) et **Nombre de plans** (1 à 6, ou Auto). Un plan ne signifie pas une seule action. Auto délègue le nombre dans la plage prise en charge ; le nombre effectivement choisi est conservé avec le résultat.
- Couverture H3 et REF2V, mono/multi-plan, préparation en 1/2/3 appels. Le contrôle du nombre de plans remplace le choix structurel mono/multi redondant dans la nouvelle version, jamais le contrôle d'action. Audace et liberté de mouvement caméra gardent leurs sens distincts.
- L'utilisateur fournit les personnages, styles et arc global ; le LLM invente des combinaisons détaillées, réactions et déplacements. Le niveau Dynamique prend comme repère les essais utilisateur récemment appréciés, sans promettre une calibration identique pour tous les sujets.
- Reprendre les principes des exemples : trois combinaisons riches sur trois plans en dix secondes, coups reliés par défense/dégagement/reprise d'initiative, déplacements entre repères et coupes sur l'action. L'exemple au tachi en six plans motive la plage proposée. Ni quota de coups, ni événement obligatoire à intervalle fixe, ni magie/destruction ajoutée indépendamment de l'intention.
- Valeurs initiales proposées pour une exploration neuve : action Dynamique, un plan ; Auto ou un autre nombre restent explicites. Les anciens projets n'acquièrent aucun nouveau réglage implicitement. Désaccord explicite entre intention et nombre de plans à signaler avant génération du prompt, sans imposer simultanément des consignes incompatibles.

## Versionnement

Une version Combat représente un ensemble cohérent : règles de chorégraphie, définition des niveaux d'action, découpage, adaptation au nombre d'appels et règles des échanges après rendu. Les contrats techniques peuvent garder leurs versions propres, épinglées exactement dans cet ensemble. Le mode H3/REF2V, le nombre d'appels, l'action et le nombre de plans sont des choix d'utilisation, pas des versions créatives supplémentaires visibles.

Chaque atelier conserve la version exacte de préparation, les IDs/versions des recettes, les réglages d'action et le nombre de plans demandé/effectif. Révisions, réouverture, adaptation H3 vers REF2V et continuation doivent garder cette version. Pour comparer 1.0 et 1.1, ouvrir une nouvelle exploration avec les mêmes références/intention ; aucune migration silencieuse de la conversation. Les réglages de rendu BUNNY/LoRA/seed/MP restent indépendants.

Les prompts 1.0 et Classique ne sont pas réécrits. Un nouveau bloc partagé neutre est adopté explicitement par ses consommateurs ; aucun héritage `latest`. Pour une amélioration générale, examiner l'adoption par les deux familles dans le même patch et documenter un éventuel report. Les systèmes versionnés doivent être résolus par registre explicite, sans repli silencieux vers une autre version.

Convention proposée : `1.1.0` pour cette extension ; `1.1.1` pour une correction ciblée conservant les principes des contrôles ; `1.2.0` pour une nouvelle capacité ; `2.0.0` si le sens des contrôles ou l'approche de préparation est profondément modifié. Toute modification de consignes publiées produit de nouveaux fichiers/versionnements, même pour une correction.

## Portée technique à prévoir

Le stockage porte déjà `preparation.family/version`, les catalogues épinglent les recettes et blocs. Toutefois les politiques applicatives et les versions de révision Combat reconnaissent actuellement seulement 1.0.0 : les étendre explicitement, pas seulement ajouter des dossiers de prompts. Adapter aussi les contrats multi-plan nécessaires pour REF2V et la plage jusqu'à six, en conservant les anciens contrats utilisés par Classique et Combat 1.0.

Préparer des vérifications d'isolation 1.0/1.1/Classique, des différents parcours et de la conservation des réglages/versions après réouverture, révision, adaptation et continuation. Les tests et essais LLM/vidéo seront exécutés par l'utilisateur. Cette proposition n'a lancé aucun test, LLM, rendu ou service.


## Livraison

Dans H3 Base ou Ref2V, choisir **Combat**, puis **Version Combat 1.1** et le parcours 1/2/3 appels. Quantité d'action et nombre de plans restent indépendants ; valeurs initiales Dynamique et 1. Le nombre remplace le second sélecteur mono/multi uniquement dans 1.1. Les réglages sont conservés dès la création de l'atelier ; utiliser une nouvelle exploration pour les comparer. Auto conserve le nombre effectivement retenu avec le prompt. Un nombre explicitement incompatible dans l'intention est signalé avant l'appel ; Auto respecte aussi un nombre explicitement demandé dans le texte.

Six recettes `minimax.h3.{fl2va,ref2v}.combat.{prompt,planned,guided}@1.1.0` et deux profils propres partagent les blocs Combat 1.1 et des contrats neutres épinglés. Une passe choisit et rédige la séquence ; deux passes séparent Plan et rédaction ; trois commencent par le Brief. Le rédacteur suit le Plan approuvé. Aucun appel de planification caché dans le parcours direct.

Le module `application/combat_sequence.py` porte les nouveaux contrats 1–6 plans : durées pondérées ramenées à la durée totale, en-têtes de référence et caméras compilés, coupes conservées en révision. H3 accepte texte seul, first, last et first+last ; la last frame appartient au dernier plan choisi. REF conserve les rôles et son en-tête exact. Les contrats mono et multi historiques restent inchangés.

Stockage sessions **11** (lecture 1–10), projets H3 **8** (lecture 1–7). `combat_settings` contient `action_level` et `shot_count` (`null` pour Auto). La préparation, ses réglages, les coupures et la politique de révision 1.1 suivent les reprises et l'adaptation H3 vers REF2V. L'adaptation conserve frames et configuration de rendu. Les contrôles BUNNY, LoRA, MP et seed sont indépendants.

Cache interface **20260910.2** pour core, H3, REF et le module partagé `combat-controls.js`. Aucun commit, push, tag ou service n'a été modifié pour activer ce patch. Les tags pré-BUNNY et pré-masque restent intacts.

## Vérification à lancer par l'utilisateur

Tests préparés, **non exécutés** :

```powershell
python -m unittest tests.test_combat_sequence tests.test_combat_controls_browser tests.test_combat_preparation tests.test_h3_multishot_browser tests.test_recipe_picker_browser
```

Ces fixtures utilisent des réponses fixes et des ports locaux ; aucun appel de modèle ou rendu. Les tests navigateur ouvrent un Chromium local en mode headless s'il est installé. Les fixtures existantes de stockage/session et cache HTTP ont aussi été actualisées.

Vérifications effectuées uniquement par analyse statique : syntaxe Python/JavaScript, liaisons des manifestes et identifiants HTML, empreintes des **542** fichiers de prompts/profils préexistants identiques, `git diff --check`. Aucun import applicatif pour vérification, test, LLM, génération ou redémarrage. Activer au prochain démarrage habituel du Lab puis recharger la page.

Pour l'expérimentation, comparer d'abord la même intention, les mêmes images et les mêmes réglages de rendu avec action Dynamique puis Intense, un plan fixe ; comparer ensuite un et trois plans à intensité constante. Six plans et les niveaux élevés restent une plage à calibrer visuellement, pas une garantie de fidélité des gestes.

## Correctif du premier essai à quatre plans

Le 10 septembre, la réponse REF2V directe a été produite en 57,58 s avec une fin normale, puis rejetée par la comparaison des caméras. Le lecteur partagé conserve l'heure de coupe immédiatement placée avant une phrase caméra ; le contexte Combat conservait seulement la phrase. Le compilateur enregistre désormais la même phrase horodatée, construite à partir du mouvement et du temps décidés, sans assouplir la validation ni changer les prompts. La réponse reçue est conservée en fixture de régression pour les parcours direct et Plan/rédacteur, H3 et REF2V. Tests préparés uniquement ; aucune relance LLM ou modification du run utilisateur.
