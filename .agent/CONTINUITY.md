# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - Les onglets produits sont désormais `I2V` et `Ref2V`, fondés sur les parcours Direct ; les anciens I2V simple et Ref2V spécialisé sont relégués dans une vue Archives en lecture seule sans supprimer leurs cookbooks ni leurs compositions.
  - Ref2V réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.3` est le mono-plan robuste par défaut. Son writer ne reçoit que `camera_landmarks_ms`; PanelForge insère les clauses caméra depuis le Plan. La `0.3.2` reste le témoin historique à placeholders.
  - `minimax.h3.ref2v.direct.multishot@0.2.0` ajoute séparément 2 à 6 plans et leurs coupes franches, avec le même Brief, Plan et arbitrage ; la `0.1.0` à trois plans reste un témoin immuable.
  - Le Plan multi V2 dérive les IDs, coupes, durée et `camera_N` depuis l’ordre du tableau, structure la composition d’ouverture et le raccord spatial/motion de chaque plan, et avertit sur les répétitions exactes entre plans adjacents.
  - Le writer multi V2 reçoit une projection dynamique sans caméra ni placeholder ; PanelForge compile ensuite les champs `shot_1` à `shot_N`, les headings, les timestamps et les phrases caméra canoniques. Arbitrage et révision conservent le nombre de plans approuvé.
  - I2V réalise une première frame native → Brief multimodal → Plan V2 arbitrable → prompt I2VA compilé avec `minimax.h3.i2v.direct@0.2.0`; la `0.1.0` reste le témoin à placeholders.
  - Pour I2V `0.2.0` et Ref2V mono `0.3.3`, le contexte persiste directive et horaire, le writer ne voit aucun mouvement/placeholder, et génération, édition ou révision réinsèrent déterministiquement la phrase canonique au bon jalon.
  - Les recettes restent sélectionnables par `id@version` avant le Plan puis verrouillées dans la composition; le multi-plan dérive headings, coupes, durée et caméra sans horloge redondante du LLM.
  - Ref2V conserve la recette sélectionnée après `Nouveau`, avertit sans bloquer si une intention multi-plan utilise le mono-plan et exige une confirmation explicite du mapping des rôles, invalidée à chaque modification.
  - Les archives neutralisent création et écritures mais laissent ouvrir et copier tout prompt actif, même non approuvé ou obsolète ; leurs listes chargent jusqu’à 200 sessions avant filtrage.
  - Validation locale : 422 tests passent.
- Broken / missing:
  - Le dialogue traversant une coupe et les transitions stylisées ne sont pas couverts par la recette multi-plan flexible.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.
  - Les contrôleurs UI I2V Direct et Ref2V Direct partagent le backend mais gardent encore du code JavaScript dupliqué.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.
- I2V et Ref2V restent deux produits et deux contrôleurs séparés ; seuls streaming, stockage, son et protocole H3 sont partagés.
- Les cookbooks legacy publiés restent immuables et chargeables, mais ne sont plus proposés pour créer un parcours depuis l’interface.
- I2V accepte exactement une première frame : I2VA uniquement. FL2VA reste hors périmètre.

## Next steps

1. Qualifier le multi-plan `0.2.0` en A/B sur 2, 3, 4 et 6 plans, notamment la variété des cadrages et les raccords de trajectoire.
2. Qualifier les nouvelles recettes camera-owned avec Qwen et Gemma, notamment les révisions et les plans sans caméra.
3. Traiter ensuite, séparément, transitions stylisées et dialogue cross-cut.

## Risks / open questions

- Le garde-fou rejette exhaustivement les formulations caméra canoniques et garde une détection volontairement étroite des paraphrases libres pour ne pas confondre mouvement du sujet et caméra ; qualifier ses faux positifs/négatifs sur des sorties réelles.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
- FL2VA n’entre pas dans ce parcours : ne pas laisser une seconde image modifier silencieusement le contrat I2VA.
- Les Archives chargent aujourd’hui 200 sessions avant filtrage client ; une pagination ou un filtre serveur sera nécessaire si le volume dépasse ce seuil.
