# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, signal sonore de fin, révisions, approbations et journal borné des appels LLM.
  - `Ref2V Direct` réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.0` est le défaut : timings V2 dérivés via `final_hold_ms`, arbitrages individuels/globaux avec relecture des images, puis writer H3. `0.2.0` reste le témoin V2.
  - Deux runs 0.3.0 ont validé Brief, Plan, arbitrage multimodal et Prompt sans rejet. Le run Bernard/gare confirme aussi le calcul V2 : 7 s d’actions + 1 s de tenue = 8 s.
  - Le compilateur récupère deux variantes caméra purement formelles, mais rejette toujours les placeholders réellement enchâssés dans la prose.
  - Les mouvements H3 à dynamique intégrée (`static_shot`, `shake.*`, `pov`) perdent désormais leurs modificateurs incompatibles avec warning; les trois plans auparavant rejetés sont récupérés.
  - Suite complète : 303 tests verts.
- Broken / missing:
  - Les arbitrages restent parfois superficiels : le run Bernard a reformulé le cadrage et prolongé le tracking, sans déplacer le zoom vers son beat naturel ni préserver la coupe demandée.
  - Le writer a soit traduit le dialogue français en anglais, soit conservé le français sans tag `[French]`; la seconde tentative a été rejetée correctement.
  - Direct reste mono-plan; une vraie coupe/multi-shot exige un contrat distinct.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables et une composition existante conserve sa version.
- Le LLM décide sémantique, route physique et timings; le code dérive seulement les relations déterministes et compile les contrats exacts.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.

## Next steps

1. Concevoir `minimax.h3.ref2v.direct@0.4.0` comme contrat multi-shot distinct, avec coupes/transitions et timings compilés selon la grammaire H3 officielle.
2. Structurer les dialogues exacts et vérifier par diff qu’un arbitrage appliqué modifie réellement les chemins du plan qu’il cible; une acceptation explicite du risque reste sans mutation.
3. Qualifier le nouveau contrat sur 1 à 3 références et plusieurs familles de transitions avant de modifier les défauts UI.

## Risks / open questions

- Un plan cohérent et arbitré ne garantit pas à lui seul la fidélité du moteur vidéo.
- Brief, Plan et arbitrage multimodaux coûtent davantage mais réduisent la perte de preuve visuelle.
