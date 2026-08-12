# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - Ref2V Direct réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.2` reste le mono-plan robuste par défaut. `minimax.h3.ref2v.direct.multishot@0.1.0` ajoute séparément trois plans et deux coupes compilées, avec le même Brief, Plan et arbitrage.
  - I2V Direct réalise une première frame native → Brief multimodal → Plan V2 arbitrable → prompt I2VA compilé. `minimax.h3.i2v.direct@0.1.0` est expérimental; l’ancien I2V simple reste le témoin.
  - Les recettes restent sélectionnables par `id@version` avant le Plan puis verrouillées dans la composition; le multi-plan dérive headings, coupes, durée et caméra sans horloge redondante du LLM.
  - Validation locale : 366 tests passent.
- Broken / missing:
  - I2V Direct : Qwen rattache parfois une paraphrase au placeholder caméra; le compilateur la rejette correctement (2 cas sur 4 dans le dernier run).
  - Le dialogue traversant une coupe, les transitions stylisées et un nombre flexible de plans ne sont pas couverts par la V1 multi-plan.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.
  - Les contrôleurs UI I2V Direct et Ref2V Direct partagent le backend mais gardent encore du code JavaScript dupliqué.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.
- I2V Direct reste parallèle au parcours actuel pendant sa qualification et accepte exactement une première frame : I2VA uniquement. FL2VA est hors périmètre.

## Next steps

1. Qualifier I2V Direct face à l’ancien I2V simple et décider d’un repair ciblé du placeholder caméra avant toute substitution.
2. Comparer en A/B Ref2V Direct mono `0.3.2` et multi `0.1.0` sur plusieurs scènes et modèles.
3. N’ajouter transitions, dialogue cross-cut ou plans flexibles qu’après cette qualification.

## Risks / open questions

- Le correctif Gemma repose encore sur peu de cas; ne pas élargir les instructions sans défaut reproduit.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
- FL2VA n’entre pas dans ce parcours : ne pas laisser une seconde image modifier silencieusement le contrat I2VA.
