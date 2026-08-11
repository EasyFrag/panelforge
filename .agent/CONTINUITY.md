# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, révisions, approbations et journal borné des appels LLM.
  - `Ref2V Direct` propose 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3 textuel, sans étape Observation.
  - `minimax.h3.ref2v.direct@0.2.0` est le défaut : le LLM produit les actions et `final_hold_ms`; le code dérive le début de l’état final et la durée, sans retiming. `0.1.0` reste le témoin immuable.
  - Les faibles holds, durées dérivées >15 s, risques non arbitrés et cibles caméra récupérables restent des warnings.
  - Suite complète : 298 tests verts.
- Broken / missing:
  - La 0.2.0 n’a pas encore été rejouée sur le cas réel couple + chat ni qualifiée sur un rendu MiniMax H3.
  - Direct reste mono-plan; une vraie coupe/multi-shot exige un contrat séparé.
  - Une référence secondaire brute peut encore influencer visuellement le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables; une session existante conserve sa version.
- Le LLM décide la sémantique, la route physique et les timings d’action; le code dérive uniquement les relations déterministes et compile les contrats exacts.
- Chaque étape reste déclenchable, éditable et approuvable séparément.

## Next steps

1. Rejouer le run couple + chat avec Direct 0.2.0, puis tester 1 et 3 images.
2. Comparer 0.2.0 à 0.1.0 sur rythme, physique, clipping et stabilité du décor.
3. Concevoir séparément le contrat multi-shot si les demandes de coupe se répètent.

## Risks / open questions

- Un contrat temporel cohérent ne garantit pas à lui seul la physique ni la fidélité du moteur vidéo.
- Le Brief/Plan multimodal coûte plus cher, mais limite la perte d’information des observations intermédiaires.
