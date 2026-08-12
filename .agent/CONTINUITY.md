# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - Ref2V Direct réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.2` est le défaut. Elle conserve intégralement le Plan V2 compact `0.3.1` et interdit seulement au writer de répéter les labels `<Picture N>` appartenant à l’en-tête compilé.
  - Toutes les versions restent sélectionnables avant le Plan puis verrouillées dans la composition; `0.3.1` est le témoin compact et `0.3.0` le témoin complet.
  - Validation locale : 307 tests passent.
- Broken / missing:
  - Direct reste mono-plan; une vraie coupe ou un second plan exige un contrat distinct.
  - Les dialogues H3 exacts et l’efficacité sémantique des arbitrages restent à qualifier.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.

## Next steps

1. Tester `0.3.2` avec Gemma 4 et les deux Qwen sur les mêmes références; vérifier particulièrement labels, placeholders caméra et taux de rejet.
2. Concevoir `0.4.0` comme contrat multi-shot distinct avec coupes et transitions H3 explicites.
3. Structurer les dialogues exacts et vérifier que chaque arbitrage accepté modifie réellement la partie ciblée du Plan.

## Risks / open questions

- Le correctif Gemma repose encore sur peu de cas; ne pas élargir les instructions sans défaut reproduit.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
