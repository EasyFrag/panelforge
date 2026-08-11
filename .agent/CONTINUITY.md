# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, révisions, approbations et journal borné des appels LLM.
  - `Ref2V Direct` réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.0` est le défaut : timings V2 dérivés via `final_hold_ms`, arbitrages individuels/globaux avec relecture des images, puis writer H3. `0.2.0` reste le témoin V2.
  - Le compilateur récupère deux variantes caméra purement formelles, mais rejette toujours les placeholders réellement enchâssés dans la prose.
  - Suite complète : 301 tests verts.
- Broken / missing:
  - La 0.3.0 doit encore être qualifiée visuellement sur plusieurs familles d’actions et avec 1/2/3 références.
  - Direct reste mono-plan; une vraie coupe/multi-shot exige un contrat distinct.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables et une composition existante conserve sa version.
- Le LLM décide sémantique, route physique et timings; le code dérive seulement les relations déterministes et compile les contrats exacts.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.

## Next steps

1. Rejouer le cas couple + chat avec Direct 0.3.0 et tester les trois modes d’arbitrage.
2. Comparer 0.3.0 à 0.2.0 sur physique, rythme, clipping, décor et respect des décisions.
3. Concevoir séparément le contrat multi-shot si les demandes de coupe se répètent.

## Risks / open questions

- Un plan cohérent et arbitré ne garantit pas à lui seul la fidélité du moteur vidéo.
- Brief, Plan et arbitrage multimodaux coûtent davantage mais réduisent la perte de preuve visuelle.
