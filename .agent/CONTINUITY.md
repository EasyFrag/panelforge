# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : observations par image, Brief `minimax.h3.reference@0.3.0`, streaming, édition/révision, approbations et journal borné des appels LLM.
  - Fighter : `fighter.arcade_versus@0.1.0` fournit le flux Ref2VA supervisé plan de références → beat sheet → prompt H3.
  - I2V simple : onglet dédié et cookbook `minimax.h3.i2v.simple@0.1.0`, limité à Observation → Brief → prompt H3 I2VA. Première frame `<Picture 1>` déterministe, writer et linter versionnés.
  - llama.swap garde la responsabilité GPU ; ComfyUI et LLM restent des services distants. Suite complète : 126 tests verts.
- Broken / missing:
  - I2V simple et Fighter ne sont pas encore qualifiés visuellement de bout en bout avec le LLM local puis MiniMax H3.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter. Aucun test navigateur automatisé.

## Decisions

- Les profils portent l’analyse/Brief LLM ; les cookbooks portent les slots, étapes et contrats vidéo. Les deux restent versionnés séparément.
- I2V réutilise l’orchestration existante mais déclare seulement `final_prompt` : aucune étape Fighter cachée.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement ; pas de chaîne d’agents autonome en V1.

## Next steps

1. Tester manuellement I2V simple avec le serveur local et plusieurs premières frames.
2. Versionner les corrections de recette/linter issues des sorties MiniMax H3 réelles.
3. Ajouter plusieurs compositions/forks par session avant le cookbook Transition.

## Risks / open questions

- La conformité du prompt ne garantit pas la qualité vidéo ; seuls les essais MiniMax H3 qualifient une recette.
- L’onglet I2V réutilise pour l’instant le profil générique d’observation/Brief `minimax.h3.reference@0.3.0` ; un profil I2V dédié ne se justifiera que si les tests montrent un manque.
- llama.swap ne fournit pas de pourcentage fiable de chargement ; un stream interrompu ne reprend pas après redémarrage.
