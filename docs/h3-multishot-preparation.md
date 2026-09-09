# H3 Base — multi-plan et états successifs

Implémenté le 2026-09-08. Les nouveaux parcours préparent un seul clip de 2 à 4 plans, avec une progression visible des états. Une coupe peut conserver la position, l'angle et le cadrage de la caméra, par exemple pour passer du versement d'une matière à son étalement avec un autre outil. La fiabilité visuelle des transitions et des transformations reste à expérimenter par l'utilisateur.

## Utilisation

Dans H3 Base, choisir **Type de séquence → Multi-plan**, puis la préparation :

| Recette | Préparation réussie sans relance |
| --- | --- |
| Exploration guidée | Brief → Plan → Prompt H3, 3 appels |
| Intention directe | Plan depuis l'intention et les images → Prompt H3, 2 appels |
| Prompt direct | Découpage compact et rédaction en un appel |

Le nombre d'appels est indépendant du nombre de plans. Le mode rapide suit les étapes de la recette ; sa politique de relance existante peut ajouter un appel après une erreur. La création d'un parcours ne déclenche pas un rendu.

Les trois recettes acceptent **first seule, last seule, first + last et aucune image**. Une first seule sert à inventer l'état suivant décrit dans l'intention. La last, lorsqu'elle existe, appartient à la fin du dernier plan ; aucune image intermédiaire n'est exigée ou ajoutée. La durée est celle demandée explicitement, sinon 8 secondes.

Exemple d'intention pour un premier essai :

> Vidéo de 8 secondes en deux plans. Même femme, robe rose, pièce, lumière et cadrage frontal fixe. Elle termine de verser la matière rose scintillante sur le sol. Une coupe temporelle conserve exactement le cadrage : elle tient maintenant une raclette sertie de diamants et étale la flaque existante. Les passages de la raclette produisent progressivement une couche rose continue sur le sol. Le changement d'outil peut être omis, mais l'étalement doit être visible. Pas de musique.

**Repartir de la dernière frame** lit la recette du rendu d'origine, préselectionne sa dernière frame comme première image, et ouvre une nouvelle préparation avec cette recette. L'ancienne last et l'ancienne intention ne deviennent pas des contraintes de la suite. La nouvelle intention reste à écrire. Un échec de lecture ou une navigation périmée conserve le travail courant ; une recette multi-plan manquante n'est pas remplacée silencieusement par une mono-plan. Il n'y a pas de nouvelle chaîne automatique de rendus ni de montage ajouté.

Le choix Mono/Multi conserve le nombre d'étapes de préparation lorsque possible. Dans chaque famille, seules les trois recettes courantes apparaissent par défaut ; les recettes spécialisées et historiques restent accessibles avec le sélecteur existant. Un run rouvert conserve sa recette enregistrée. L'ancienne multi-plan `0.1.0` est désormais historique. Le défaut des nouveaux ateliers reste la mono-plan guidée `1.1.0`.

## Versionnement et contrats

- Nouveaux IDs `minimax.h3.fl2va.direct.multishot.{guided,planned,prompt}@1.0.0` ; profil `minimax.h3.fl2va.direct.multishot@0.2.0`, variante Direction créative `0.3.0`.
- Blocs versionnés dans `prompt_cookbooks/_blocks/h3-multishot/1.0.0`. Les principes de progression sont partagés ; Brief, Plan depuis intention, Plan depuis Brief et rédaction directe ont des consignes adaptées. Les deux parcours avec Plan partagent exactement le même rédacteur final. Le bloc causal `video-preparation/1.1.0` est réutilisé au stade de décision.
- Contrat des parcours avec Plan : `minimax.h3.fl2va.direct_multishot_compact_h3_v2`. Le schéma du Plan reste celui de l'ancienne multi-plan : durées, composition initiale, actions, résultat, continuité et caméra par plan. Les changements voulus d'outil ou de matière sont distingués des invariants. Un cadrage répété ne déclenche plus l'ancien avertissement, ni une fin sans pause l'avertissement de tenue finale.
- Si nécessaire, les durées des plans, la tenue explicitement prévue et les départs de dialogues sont ajustés proportionnellement au total demandé. Une tenue n'est pas inventée pour remplir la durée. L'ajustement du Plan est enregistré et signalé.
- Contrat direct : `minimax.h3.multishot.prompt_direct_v1`. JSON `shots` (2–4 éléments : `duration_ms`, `opening_composition`, `camera_motion`, `description`), `final_state`, `dialogue_cues` et deux champs sonores. Un mouvement caméra par plan, sans amplitude/vitesse distinctes dans ce parcours. Aucun Plan synthétique n'est créé ou approuvé. Les durées proposées sont réparties proportionnellement sur le total demandé ; les dialogues utilisent cette horloge globale.
- Le compilateur partagé calcule les headings, les coupes, les caméras, les références et les dialogues. Son contexte V2 utilise `cut_policy: neutral` : il compile « the camera cuts. », sans imposer une nouvelle vue. Le cadrage et l'ellipse souhaités sont décrits dans la composition initiale du plan. Le contexte V1 reste lisible et garde sa phrase historique, avec son encodage inchangé.
- Une révision du prompt conserve la structure du découpage, les compositions initiales, les caméras, les horloges, les paroles et l'état final compilés. Elle modifie les champs de prose. Pour changer ces décisions : modifier/régénérer le Plan en deux ou trois étapes, ou régénérer le prompt direct. Une régénération directe peut choisir un autre nombre de plans ; une réponse invalide ne remplace pas la révision enregistrée précédente.

Les recettes/profils anciens et les workflows ComfyUI restent inchangés. Stockage des compositions existant, contexte enregistré avec la révision, journaux et thinking habituels. Le rendu reçoit le même format de prompt H3 et extrait les coupes pour les vignettes. Caches `lab-core.js`, `i2v-direct.js` et `h3-render-lab.js` : **20260908.1**.

## Vérification à la main de l'utilisateur

Tests préparés **non exécutés**. Aucun appel LLM, génération, annulation, redémarrage ou donnée runtime modifiée pendant l'implémentation. Contrôles statiques : syntaxe Python/JS, lecture des JSON et dépendances de templates, IDs HTML/cache, revue du diff. Le tag `stable-avant-masque-2026-09-06` reste le point de restauration.

Depuis `D:\Code\localQ\.panelpatch` :

```powershell
$env:PYTHONPATH = "D:\Code\localQ\.panelpatch\src"
& "D:\Code\panelforge\.venv\Scripts\python.exe" -m unittest tests.test_h3_multishot_preparation tests.test_h3_multishot_browser tests.test_h3_base_multishot tests.test_video_preparation_recipes tests.test_recipe_picker_browser
```

Les fixtures n'utilisent que des réponses simulées ; les tests navigateur requièrent le Chromium local et simulent les lectures de recette/frame. Ils couvrent les quatre entrées dans les trois parcours, la réouverture, la compilation/révision, les horloges et dialogues protégés, les échecs conservant la révision antérieure, la régénération directe avec un autre nombre de plans, les durées sans gel automatique, les anciens contextes et le sélecteur/reprise de frame.

Après redémarrage et rechargement à sa convenance, l'utilisateur peut commencer par first seule et deux plans au même cadrage en préparation à deux étapes, inspecter le découpage puis la vidéo, et reprendre sa dernière frame pour demander l'ajout de diamants. Comparer ensuite les parcours et les modes d'ancrage. Aucune capacité de transformation forte ou stabilité parfaite entre clips n'est déduite des seuls contrôles statiques.
