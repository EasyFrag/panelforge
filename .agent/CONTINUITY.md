# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, signal sonore de fin, révisions, approbations et journal borné des appels LLM.
  - `Ref2V Direct` réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.0` est le défaut : timings V2 dérivés via `final_hold_ms`, arbitrages individuels/globaux avec relecture des images, puis writer H3. `0.2.0` reste le témoin V2.
  - Le premier run 0.3.0 couple + chat a validé Plan, arbitrage multimodal et Prompt sans erreur caméra; les deux décisions ont été persistées.
  - Le compilateur récupère deux variantes caméra purement formelles, mais rejette toujours les placeholders réellement enchâssés dans la prose.
  - Suite complète : 301 tests verts.
- Broken / missing:
  - Sur ce run, l’arbitrage a surtout annoté les risques : il n’a ni allongé la poursuite dans l’eau ni résolu le lancement physiquement improbable du petit chat.
  - Le writer a soit traduit le dialogue français en anglais, soit conservé le français sans tag `[French]`; la seconde tentative a été rejetée correctement.
  - Direct reste mono-plan; une vraie coupe/multi-shot exige un contrat distinct.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables et une composition existante conserve sa version.
- Le LLM décide sémantique, route physique et timings; le code dérive seulement les relations déterministes et compile les contrats exacts.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.

## Next steps

1. Corriger génériquement le contrat de dialogue : texte exact + nom anglais réel de la langue (`[French]`, `[English]`, etc.).
2. Décider comment vérifier qu’un arbitrage modifie réellement la chronologie ou la route physique concernée.
3. Qualifier la 0.3.0 sur rendu vidéo puis avec 1 et 3 références; garder le multi-shot séparé.

## Risks / open questions

- Un plan cohérent et arbitré ne garantit pas à lui seul la fidélité du moteur vidéo.
- Brief, Plan et arbitrage multimodaux coûtent davantage mais réduisent la perte de preuve visuelle.
