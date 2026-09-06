# Préparation vidéo : trois parcours versionnés

Les onglets H3 Base et Ref2V proposent trois recettes mono-plan `1.0.0`. À la demande de l'utilisateur, les recettes « Mono-plan · compact · expérimental » H3 `0.4.0` et Ref2V `0.5.0` sont maintenant sélectionnées par défaut. Les trois nouveaux parcours restent visibles à côté ; les témoins précédents sont dans « Autres recettes ». Réouvrir un run conserve sa recette enregistrée.

| Parcours | Appels pour une préparation réussie | Responsabilités |
| --- | --- | --- |
| Exploration guidée · 3 étapes | Brief → Plan → Prompt H3 | Le Brief choisit la direction, le Plan organise les actions, le writer rédige. |
| Intention directe · 2 étapes | Plan → Prompt H3 | Le Plan interprète directement l'intention et les images, puis le même writer rédige. |
| Prompt direct · 1 étape | Prompt H3 | Un seul appel choisit une séquence simple et rédige son texte. |

Chaque étape présente peut être générée, discutée et validée. Le mode rapide enchaîne uniquement les étapes de la recette ; sa politique existante autorise une seconde tentative après un échec, donc le nombre d'appels réel peut dépasser celui du tableau. Aucun rendu n'est déclenché par la création d'un parcours.

La recette est enregistrée à la création du nouveau run. Pour les parcours courts, l'intention, les trois axes de liberté et l'audace sont conservés séparément dans la composition : aucun Brief synthétique n'est créé ou approuvé. L'intention reste visible dans le formulaire. « Repartir de ce run » reprend les images et l'intention et permet de choisir un autre parcours ; le run source reste intact. Le bouton de reprise depuis la dernière frame reste disponible et conserve la recette H3 mono déjà sélectionnée, y compris un parcours court.

## Contrats et limites

Les parcours à deux et trois étapes utilisent le même contrat de Plan V4, les mêmes validateurs et exactement les mêmes prompts du writer dans chaque famille. Leurs instructions de Plan diffèrent : interprétation créative directe sans Brief, ou conversion d'un Brief approuvé. Images natives au Plan, puis projection compacte au writer ; pas d'appel intermédiaire ajouté.

Le parcours à une étape utilise le contrat distinct `minimax.h3.mono.prompt_direct_v1`. Sa réponse contient quatre champs JSON : un type de mouvement caméra et les trois textes vidéo. Ce n'est pas un Plan caché. L'application compile les références, le heading, la durée et la phrase caméra canonique ; elle vérifie la structure, les paroles explicites, les jalons et les labels. La sortie devient le même prompt H3 éditable et rejoint le même espace de rendu/conversation.

Cette première version directe accepte **un mouvement caméra principal pour tout le clip**, sans vitesse ou amplitude distincte. La durée correspond à la durée demandée lorsqu'elle est non ambiguë, sinon **8 secondes**. Ces limites apparaissent dans l'aide du parcours. Les contrats de contacts, risques et comportement de fin ne sont pas représentés par un Plan dans ce parcours : leur qualité dépend de la réponse du modèle et de la revue humaine. Aucun gain de latence ou de qualité n'a encore été mesuré.

H3 Base conserve ses modes T2VA, I2VA, L2VA et FL2VA selon les rôles first/last présents. Ref2V conserve son mapping de rôles ; dans les parcours courts, ses règles se réfèrent à l'intention utilisateur et ne prétendent pas qu'un Brief existe.

## Versions et maintenance

Les IDs sont `minimax.h3.fl2va.direct.{guided,planned,prompt}` et `minimax.h3.ref2v.direct.{guided,planned,prompt}`, chacun en `1.0.0`.

Les manifests de cookbook en schéma 8 figent le nombre d'étapes, le profil (`minimax.h3.fl2va.direct@0.4.0` ou `minimax.h3.ref2v.direct@0.5.0`) et chaque dépendance de prompt. Les blocs communs sont sous `prompt_cookbooks/_blocks/video-preparation/1.0.0/`. Le writer et les templates de révision/arbitrage réutilisés référencent explicitement un cookbook, une version numérique et une clé de template. Les références `latest`, les cycles et les chemins qui sortent de leur racine sont rejetés. Pour faire évoluer les règles partagées, publier un nouveau bloc et une nouvelle version des recettes concernées.

Les compositions passent au schéma 3 ; les schémas 1 et 2 restent lisibles sans intention directe. Les IDs de sources distinguent `intent:` de `brief:` et conservent les snapshots des bindings. Les nouvelles opérations Plan/Prompt consignent l'ID et la version de recette dans le journal LLM existant ; les durées et le thinking suivent la journalisation existante, toujours bornée à 20 appels.

## Vérification à effectuer par l'utilisateur

Aucun test, appel LLM, rendu ou redémarrage n'a été lancé pendant ce patch. La syntaxe Python a été lue avec `ast.parse` et le diff contrôlé. Les tests hors ligne ont été ajoutés/ajustés pour les parcours courts, les prérequis, la persistance, les en-têtes H3, le partage du writer, les dépendances et le sélecteur/mode rapide dans un DOM local.

Depuis le checkout actif `D:\Code\localQ\.panelpatch`, avec l'environnement Python du projet :

```powershell
$env:PYTHONPATH = "D:\Code\localQ\.panelpatch\src"
& "D:\Code\panelforge\.venv\Scripts\python.exe" -m unittest tests.test_video_preparation_recipes tests.test_prompt_composition_storage tests.test_recipe_picker_browser
```

Pour la suite complète, remplacer la liste des modules par `discover -s tests`.

Après ton redémarrage du serveur et rechargement de la page, comparer un même sujet avec les mêmes images, intention, modèle, axes et audace. Pour comparer à audace non nulle en trois étapes, activer la variante Direction créative. Vérifier d'abord la cohérence et le respect de l'intention, puis le nombre d'appels et la durée totale. Tester aussi la réouverture et « Repartir de ce run » avant de conclure sur les différences de qualité.
