# Préparation vidéo : trois parcours versionnés

H3 Base propose aussi trois nouveaux parcours **multi-plan 1.0.0**, via **Type de séquence → Multi-plan** : mêmes nombres d'appels, avec 2 à 4 plans et des coupes possibles au même cadrage. First seule, last seule, first+last et texte seul sont disponibles. Voir [le guide multi-plan et états successifs](h3-multishot-preparation.md) pour les contrats, limites et tests. L'ancienne multi-plan `0.1.0` reste dans les versions historiques. Les paragraphes ci-dessous décrivent les parcours mono-plan.

H3 Base propose désormais les trois recettes mono-plan **1.1.0**, avec **Exploration guidée · 3 étapes (1.1.0)** sélectionnée par défaut. Les trois recettes H3 `1.0.0` et l'ancienne compacte `0.4.0` restent dans **Autres recettes → Versions historiques**. Ref2V garde ses recettes `1.0.0` et son défaut compact expérimental `0.5.0`. Réouvrir un run conserve sa recette enregistrée, visible même si elle est historique.

| Parcours | Appels pour une préparation réussie | Responsabilités |
| --- | --- | --- |
| Exploration guidée · 3 étapes | Brief → Plan → Prompt H3 | Le Brief choisit la direction, le Plan organise les actions, le writer rédige. |
| Intention directe · 2 étapes | Plan → Prompt H3 | Le Plan interprète directement l'intention et les images, puis le même writer rédige. |
| Prompt direct · 1 étape | Prompt H3 | Un seul appel choisit une séquence simple et rédige son texte. |

Chaque étape présente peut être générée, discutée et validée. Le mode rapide enchaîne uniquement les étapes de la recette ; sa politique existante autorise une seconde tentative après un échec, donc le nombre d'appels réel peut dépasser celui du tableau. Aucun rendu n'est déclenché par la création d'un parcours.

La recette est enregistrée à la création du nouveau run. Pour les parcours courts, l'intention, les trois axes de liberté et l'audace sont conservés séparément dans la composition : aucun Brief synthétique n'est créé ou approuvé. L'intention reste visible dans le formulaire. « Repartir de ce run » reprend les images et l'intention et permet de choisir un autre parcours ; le run source reste intact. Le bouton de reprise depuis la dernière frame reste disponible et conserve la recette H3 mono déjà sélectionnée, y compris un parcours court.

## Contrats et limites

Les parcours à deux et trois étapes partagent la structure de Plan V4 et exactement les mêmes prompts du writer dans chaque famille/version. H3 `1.1.0` utilise le contrat applicatif `minimax.h3.fl2va.direct_compact_h3_v5`, qui change la validation de fin sans ajouter de champ JSON. H3 `1.0.0` et Ref2V conservent leurs validateurs. Les instructions de Plan diffèrent : interprétation créative directe sans Brief, ou conversion d'un Brief approuvé. Images natives au Plan, puis projection compacte au writer ; pas d'appel intermédiaire ajouté.

Le parcours à une étape utilise le contrat distinct `minimax.h3.mono.prompt_direct_v1`. Sa réponse contient quatre champs JSON : un type de mouvement caméra et les trois textes vidéo. Ce n'est pas un Plan caché. L'application compile les références, le heading, la durée et la phrase caméra canonique ; elle vérifie la structure, les paroles explicites, les jalons et les labels. La sortie devient le même prompt H3 éditable et rejoint le même espace de rendu/conversation.

Cette première version directe accepte **un mouvement caméra principal pour tout le clip**, sans vitesse ou amplitude distincte. La durée correspond à la durée demandée lorsqu'elle est non ambiguë, sinon **8 secondes**. Ces limites apparaissent dans l'aide du parcours. Les contrats de contacts, risques et comportement de fin ne sont pas représentés par un Plan dans ce parcours : leur qualité dépend de la réponse du modèle et de la revue humaine. Aucun gain de latence ou de qualité n'a encore été mesuré.

H3 Base conserve ses modes T2VA, I2VA, L2VA et FL2VA selon les rôles first/last présents. Ref2V conserve son mapping de rôles ; dans les parcours courts, ses règles se réfèrent à l'intention utilisateur et ne prétendent pas qu'un Brief existe.

## Versions et maintenance

Les IDs sont `minimax.h3.fl2va.direct.{guided,planned,prompt}` (versions `1.0.0` et `1.1.0`) et `minimax.h3.ref2v.direct.{guided,planned,prompt}` (`1.0.0`).

Les manifests de cookbook en schéma 8 figent le nombre d'étapes, le profil et chaque dépendance. H3 `1.0.0` référence le profil `minimax.h3.fl2va.direct@0.4.0` ; H3 `1.1.0` référence `@0.5.0`, avec Brief standard actualisé et variante Direction créative `0.3.0`. Ref2V référence toujours `minimax.h3.ref2v.direct@0.5.0`. Les blocs de base restent sous `prompt_cookbooks/_blocks/video-preparation/1.0.0/` ; les règles causales nouvelles sont en `1.1.0/`. Le writer et les templates de révision/arbitrage réutilisés référencent explicitement un cookbook, une version numérique et une clé de template. Les références `latest`, les cycles et les chemins qui sortent de leur racine sont rejetés.

Les compositions passent au schéma 3 ; les schémas 1 et 2 restent lisibles sans intention directe. Les IDs de sources distinguent `intent:` de `brief:` et conservent les snapshots des bindings. Les nouvelles opérations Plan/Prompt consignent l'ID et la version de recette dans le journal LLM existant ; les durées et le thinking suivent la journalisation existante, toujours bornée à 20 appels.

## Vérification à effectuer par l'utilisateur

Aucun test, appel LLM, rendu ou redémarrage n'a été lancé pendant ce patch. La syntaxe Python a été lue avec `ast.parse` et le diff contrôlé. Les tests hors ligne ont été ajoutés/ajustés pour les parcours courts, les prérequis, la persistance, les en-têtes H3, le partage du writer, les dépendances et le sélecteur/mode rapide dans un DOM local.

Depuis le checkout actif `D:\Code\localQ\.panelpatch`, avec l'environnement Python du projet :

```powershell
$env:PYTHONPATH = "D:\Code\localQ\.panelpatch\src"
& "D:\Code\panelforge\.venv\Scripts\python.exe" -m unittest tests.test_h3_causal_recipes tests.test_h3_base_motion_v3 tests.test_video_preparation_recipes tests.test_prompt_composition_storage tests.test_recipe_picker_browser
```

Pour la suite complète, remplacer la liste des modules par `discover -s tests`.

Après ton redémarrage du serveur et rechargement de la page, comparer un même sujet avec les mêmes images, intention, modèle, axes et audace. Pour comparer à audace non nulle en trois étapes, activer la variante Direction créative. Vérifier d'abord la cohérence et le respect de l'intention, puis le nombre d'appels et la durée totale. Tester aussi la réouverture et « Repartir de ce run » avant de conclure sur les différences de qualité.

## H3 1.1.0 — transformations causales

Suite à l'[audit du mur](h3-travaux-audit-2026-09-07.md), le stade de décision compare les états visibles et déduit les opérations nécessaires : retirer, dégager, préparer et ajouter seulement lorsque la transformation l'exige. Le Brief prend cette décision en guidé, le Plan en deux étapes, le rédacteur direct en une étape. L'accélération compresse les gestes répétés sans effacer leurs prérequis. Les limites d'actions supplémentaires concernent les embellissements ; les éléments existants et les débris visibles à la fin restent conservés. Les demandes explicites de magie ou de travail hors champ priment. Aucun scénario de chantier obligatoire ni nombre fixe de phases n'est imposé.

Les deux writers avec Plan partagent la même consigne de conservation des phases. Les révisions et arbitrages reçoivent aussi les règles nouvelles. Le Brief reste compact, mais sa chronologie peut dépasser deux phrases si les phases le nécessitent. Les règles françaises de Brief sont figées dans le nouveau profil à partir de `brief-causal.system.txt` ; aucun assemblage runtime supplémentaire.

La validation V5 accepte la ressemblance d'un élément terminé avec la dernière frame avant la coupure. Elle peut afficher un avertissement, sans bloquer ni réécrire les actions. Les contrôles de structure/timing/caméra/dialogues et les corrections déterministes V4 sont conservés. Un arrêt explicite global à la fin, ou un arrêt du sujet nommé au début de `primary_motion`, reste bloquant en `continue_motion`. C'est un contrôle lexical volontairement limité, pas un moteur de compréhension physique : les paraphrases et coréférences ambiguës restent à relire. Les fins `natural_settle` et `intentional_hold` gardent leur sens.

Le parcours direct conserve son JSON à quatre champs et n'utilise pas le validateur de Plan. Il reçoit les mêmes principes de causalité/fin dans ses consignes. Les conversations après rendu H3, les workflows ComfyUI, les anciens projets, les réglages de génération et Ref2V sont inchangés. Caches core/H3 préparation : `20260907.3`.

Tests préparés, non exécutés : reprise du libellé rejeté à 6,2 s, formulation équivalente, ouvrier arrêté avec nuages actifs, gel global, arrêt du mouvement final, négations, arrêt d'une phase antérieure, fins demandées, timing invalide, chargement des trois versions, transmission des phases au writer, enregistrement/réouverture, conservation des anciens manifests et sélecteur historique. Aucun gain de qualité n'est revendiqué avant les essais utilisateur.
