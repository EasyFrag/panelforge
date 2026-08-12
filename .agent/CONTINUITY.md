# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, signal sonore, révisions, approbations et journal borné des appels LLM.
  - Ref2V Direct réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.1` est la variante compacte par défaut; `0.3.0` reste sélectionnable comme témoin verrouillé. Les deux partagent le Plan V2, les arbitrages, le compilateur et les validations.
  - Le sélecteur vient du catalogue et se verrouille dès que la composition est créée. Le writer compact exclut seulement les risques et ajustements techniques; le Plan persistant reste complet.
  - Suite complète : 306 tests verts.
- Broken / missing:
  - Direct reste mono-plan; une vraie coupe ou un second plan exige un contrat distinct.
  - Les dialogues H3 exacts et l’efficacité sémantique des arbitrages restent à qualifier.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.

## Next steps

1. Comparer `0.3.1` à `0.3.0` sur les mêmes références et intentions, notamment taux de rejet, rythme, continuité et clipping.
2. Concevoir `0.4.0` comme contrat multi-shot distinct avec coupes et transitions H3 explicites.
3. Structurer les dialogues exacts et vérifier que chaque arbitrage accepté modifie réellement la partie ciblée du Plan.

## Risks / open questions

- La réduction d’instructions peut améliorer l’adhérence ou retirer un rappel utile; seuls les tests A/B vidéo permettront de trancher.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
