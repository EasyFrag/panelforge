# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - Ref2V Direct réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.2` est le défaut. Elle conserve intégralement le Plan V2 compact `0.3.1` et interdit seulement au writer de répéter les labels `<Picture N>` appartenant à l’en-tête compilé.
  - I2V Direct réalise une première frame native → Brief multimodal → Plan V2 arbitrable → prompt I2VA compilé. `minimax.h3.i2v.direct@0.1.0` est expérimental; l’ancien I2V simple reste le témoin.
  - Toutes les versions restent sélectionnables avant le Plan puis verrouillées dans la composition; `0.3.1` est le témoin compact et `0.3.0` le témoin complet.
  - Validation locale : 320 tests passent.
- Broken / missing:
  - Direct reste mono-plan; une vraie coupe ou un second plan exige un contrat distinct.
  - Les dialogues H3 exacts et l’efficacité sémantique des arbitrages restent à qualifier.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.
  - Les contrôleurs UI I2V Direct et Ref2V Direct partagent le backend mais gardent encore du code JavaScript dupliqué.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.
- I2V Direct reste parallèle au parcours actuel pendant sa qualification et accepte exactement une première frame : I2VA uniquement. FL2VA est hors périmètre.

## Next steps

1. Qualifier I2V Direct face à l’ancien I2V simple sur les mêmes frames et intentions avant toute substitution.
2. Extraire un contrôleur UI Direct partagé seulement après stabilisation des deux UX.
3. Reprendre ensuite le multi-shot Ref2V comme contrat séparé avec coupes et transitions H3 explicites.

## Risks / open questions

- Le correctif Gemma repose encore sur peu de cas; ne pas élargir les instructions sans défaut reproduit.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
- FL2VA n’entre pas dans ce parcours : ne pas laisser une seconde image modifier silencieusement le contrat I2VA.
